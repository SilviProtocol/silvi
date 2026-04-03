#!/usr/bin/env bash
# train_on_gcp.sh — Launch H100 VM, export data, train SINR v3.0, download results.
#
# One-command end-to-end:
#   ./train_on_gcp.sh launch     # Create VM + install deps
#   ./train_on_gcp.sh export     # Export BQ → GCS → VM
#   ./train_on_gcp.sh train      # Run training
#   ./train_on_gcp.sh download   # Download results to local
#   ./train_on_gcp.sh teardown   # Delete VM
#   ./train_on_gcp.sh all        # Do everything in sequence
#
# Cost: ~$3-4 total for H100 spot (~$3.30/hr × ~1 hour)

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="treekipedia-479918"
ZONE="us-central1-c"           # Good H100 availability
VM_NAME="sinr-v3-training"
MACHINE_TYPE="a3-highgpu-1g"   # 1× H100 80GB, 26 vCPU, 170GB RAM
GCS_BUCKET="gs://${PROJECT_ID}-sinr-v3"
BQ_DATASET="species_data"
UNIFIED_TABLE="sinr_v3_unified_strict_train_v30_preview_clean"  # strict HIT-only preview table (sentinels NULL-converted)
IMAGE_FAMILY="pytorch-2-7-cu128-ubuntu-2204-nvidia-570"
IMAGE_PROJECT="deeplearning-platform-release"

# Local paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="${SCRIPT_DIR}/sinr_model_v3"
DATA_DIR="${SCRIPT_DIR}/sinr_training_data"

# ── Helper ────────────────────────────────────────────────────────────────────
log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── Step 1: Launch VM ─────────────────────────────────────────────────────────
launch_vm() {
    log "Creating GCS bucket (if needed)..."
    gsutil mb -p "$PROJECT_ID" -l us-central1 "$GCS_BUCKET" 2>/dev/null || true

    log "Creating H100 VM: $VM_NAME..."

    # Try spot (preemptible) first for cost savings
    gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --accelerator=type=nvidia-h100-80gb,count=1 \
        --maintenance-policy=TERMINATE \
        --provisioning-model=SPOT \
        --image-family="$IMAGE_FAMILY" \
        --image-project="$IMAGE_PROJECT" \
        --boot-disk-size=200GB \
        --boot-disk-type=pd-ssd \
        --scopes=bigquery,storage-rw,compute-rw \
        --metadata="install-nvidia-driver=True" \
    || {
        log "Spot VM failed. Trying on-demand (costs ~3x more)..."
        gcloud compute instances create "$VM_NAME" \
            --project="$PROJECT_ID" \
            --zone="$ZONE" \
            --machine-type="$MACHINE_TYPE" \
            --accelerator=type=nvidia-h100-80gb,count=1 \
            --maintenance-policy=TERMINATE \
            --image-family="$IMAGE_FAMILY" \
            --image-project="$IMAGE_PROJECT" \
            --boot-disk-size=200GB \
            --boot-disk-type=pd-ssd \
            --scopes=bigquery,storage-rw,compute-rw \
            --metadata="install-nvidia-driver=True"
    }

    log "Waiting for VM to be ready..."
    sleep 30

    # Install Python dependencies
    log "Installing dependencies on VM..."
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command='
        pip install --quiet google-cloud-bigquery google-cloud-bigquery-storage \
            pyarrow pandas numpy torch torchvision scikit-learn
        nvidia-smi
    '

    log "VM ready! GPU info above."
}

# ── Step 2: Export BQ → GCS → VM ─────────────────────────────────────────────
export_data() {
    log "Exporting BQ table to GCS as parquet..."

    # Export from BQ to GCS (fastest path — internal Google network)
    bq extract \
        --destination_format=PARQUET \
        --compression=SNAPPY \
        "${PROJECT_ID}:${BQ_DATASET}.${UNIFIED_TABLE}" \
        "${GCS_BUCKET}/training_data/unified_*.parquet"

    log "BQ export complete. Copying to VM..."

    # Copy training scripts to VM
    gcloud compute scp \
        "${SCRIPT_DIR}/train_sinr_v3.py" \
        "${SCRIPT_DIR}/train_on_vm.py" \
        "$VM_NAME:~/" \
        --zone="$ZONE" --project="$PROJECT_ID"

    # Copy phylo embeddings and species mapping
    for f in species_phylo_embeddings.npz species_mapping.json; do
        if [ -f "${DATA_DIR}/$f" ]; then
            gcloud compute scp "${DATA_DIR}/$f" "$VM_NAME:~/" \
                --zone="$ZONE" --project="$PROJECT_ID"
            log "Copied $f"
        fi
    done

    # Download parquet from GCS to VM (fast — same datacenter)
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="
        mkdir -p ~/data ~/model
        gsutil -m cp '${GCS_BUCKET}/training_data/unified_*.parquet' ~/data/
        ls -lh ~/data/
    "

    log "Data ready on VM."
}

# ── Step 3: Train ─────────────────────────────────────────────────────────────
run_training() {
    log "Starting training on VM..."

    # Upload the training script
    gcloud compute scp \
        "${SCRIPT_DIR}/train_on_vm.py" \
        "$VM_NAME:~/" \
        --zone="$ZONE" --project="$PROJECT_ID"

    # Copy phylo + mapping files
    for f in species_phylo_embeddings.npz species_mapping.json; do
        if [ -f "${DATA_DIR}/$f" ]; then
            gcloud compute scp "${DATA_DIR}/$f" "$VM_NAME:~/" \
                --zone="$ZONE" --project="$PROJECT_ID"
        fi
    done

    # Run training (streams output to terminal)
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" -- \
        "cd ~ && python3 train_on_vm.py --train 2>&1 | tee training.log"

    log "Training complete!"
}

# ── Step 4: Download Results ──────────────────────────────────────────────────
download_results() {
    log "Downloading model artifacts..."

    mkdir -p "$MODEL_DIR"

    # Download all model files
    gcloud compute scp --recurse \
        "$VM_NAME:~/model/*" \
        "$MODEL_DIR/" \
        --zone="$ZONE" --project="$PROJECT_ID"

    # Download training log
    gcloud compute scp \
        "$VM_NAME:~/training.log" \
        "$MODEL_DIR/" \
        --zone="$ZONE" --project="$PROJECT_ID"

    log "Downloaded to $MODEL_DIR:"
    ls -lh "$MODEL_DIR/"
}

# ── Step 5: Teardown ─────────────────────────────────────────────────────────
teardown_vm() {
    log "Deleting VM $VM_NAME..."
    gcloud compute instances delete "$VM_NAME" \
        --zone="$ZONE" --project="$PROJECT_ID" --quiet

    log "VM deleted. GCS bucket preserved at $GCS_BUCKET"
    log "To delete GCS data: gsutil -m rm -r $GCS_BUCKET"
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "${1:-help}" in
    launch)   launch_vm ;;
    export)   export_data ;;
    train)    run_training ;;
    download) download_results ;;
    teardown) teardown_vm ;;
    all)
        launch_vm
        export_data
        run_training
        download_results
        teardown_vm
        log "ALL DONE! Model saved to $MODEL_DIR"
        ;;
    *)
        echo "Usage: $0 {launch|export|train|download|teardown|all}"
        echo ""
        echo "  launch    - Create H100 VM and install deps"
        echo "  export    - Export BQ → GCS → VM"
        echo "  train     - Run training on VM"
        echo "  download  - Download model artifacts"
        echo "  teardown  - Delete VM (saves money!)"
        echo "  all       - Do everything end-to-end"
        ;;
esac
