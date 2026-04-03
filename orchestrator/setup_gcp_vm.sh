#!/bin/bash
# =============================================================================
# GCP VM Setup for AlphaEarth COG Sampling
# =============================================================================
#
# This script creates a GCP VM optimized for reading AlphaEarth COGs from GCS.
# Data stays within Google's network = NO egress charges!
#
# Estimated cost: ~$1-2 total for full processing
#   - VM: e2-standard-4 @ $0.15/hr × 5 hrs = $0.75
#   - Storage: 20GB @ $0.04/GB/mo = negligible
#   - No egress (same network as GCS)
#
# Usage:
#   ./setup_gcp_vm.sh         # Create VM and upload files
#   ./setup_gcp_vm.sh run     # Run the sampler
#   ./setup_gcp_vm.sh delete  # Delete VM when done
#
# =============================================================================

set -e

PROJECT_ID="treekipedia-479918"
ZONE="us-central1-a"  # Same region as AlphaEarth GCS bucket
VM_NAME="alphaearth-sampler"
MACHINE_TYPE="e2-standard-8"  # 8 vCPU, 32GB RAM (~$0.27/hr) - allows 32+ parallel workers
DISK_SIZE="50GB"
NUM_WORKERS=32  # Parallel COG readers

# Files to upload
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OCC_FILE="$SCRIPT_DIR/../Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"
INDEX_FILE="$SCRIPT_DIR/aef_index.parquet"
SAMPLER_SCRIPT="$SCRIPT_DIR/gcp_vm_sampler.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_status() { echo -e "${GREEN}[✓]${NC} $1"; }
echo_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
echo_error() { echo -e "${RED}[✗]${NC} $1"; }

# =============================================================================
# FUNCTIONS
# =============================================================================

create_vm() {
    echo "============================================================"
    echo "CREATING GCP VM: $VM_NAME"
    echo "============================================================"
    echo "Project: $PROJECT_ID"
    echo "Zone: $ZONE"
    echo "Machine: $MACHINE_TYPE (4 vCPU, 16GB RAM)"
    echo "Disk: $DISK_SIZE"
    echo ""

    # Check if VM already exists
    if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        echo_warning "VM $VM_NAME already exists"
        read -p "Delete and recreate? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            delete_vm
        else
            return
        fi
    fi

    # Create VM with startup script
    gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --boot-disk-size="$DISK_SIZE" \
        --boot-disk-type="pd-ssd" \
        --image-family="debian-12" \
        --image-project="debian-cloud" \
        --scopes="https://www.googleapis.com/auth/cloud-platform" \
        --metadata=startup-script='#!/bin/bash
# Install dependencies
apt-get update
apt-get install -y python3-pip python3-venv libgdal-dev
pip3 install --break-system-packages rasterio pyproj geopandas shapely pandas numpy pandas-gbq google-cloud-bigquery pyarrow
echo "Dependencies installed!" > /tmp/startup_complete
'

    echo_status "VM created successfully"
    echo ""
    echo "Waiting for startup script to complete..."

    # Wait for VM to be ready
    sleep 30

    # Wait for dependencies to install
    for i in {1..20}; do
        if gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="test -f /tmp/startup_complete" &>/dev/null; then
            echo_status "Startup script completed"
            break
        fi
        echo "  Waiting... ($i/20)"
        sleep 15
    done
}

upload_files() {
    echo ""
    echo "============================================================"
    echo "UPLOADING FILES TO VM"
    echo "============================================================"

    # Create data directory on VM
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="mkdir -p /home/data"

    # Upload files
    echo "Uploading sampler script..."
    gcloud compute scp "$SAMPLER_SCRIPT" "$VM_NAME:/home/data/gcp_vm_sampler.py" --zone="$ZONE" --project="$PROJECT_ID"
    echo_status "Uploaded gcp_vm_sampler.py"

    echo "Uploading COG index (65MB)..."
    gcloud compute scp "$INDEX_FILE" "$VM_NAME:/home/data/aef_index.parquet" --zone="$ZONE" --project="$PROJECT_ID"
    echo_status "Uploaded aef_index.parquet"

    echo "Uploading occurrences file (this may take a while)..."
    gcloud compute scp "$OCC_FILE" "$VM_NAME:/home/data/occurrences.parquet" --zone="$ZONE" --project="$PROJECT_ID"
    echo_status "Uploaded occurrences.parquet"

    # Update script to look in /home/data
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="
cd /home/data
ln -sf aef_index.parquet \$(dirname gcp_vm_sampler.py)/aef_index.parquet 2>/dev/null || true
"

    echo ""
    echo_status "All files uploaded"
}

run_sampler() {
    echo ""
    echo "============================================================"
    echo "RUNNING ALPHAEARTH SAMPLER"
    echo "============================================================"

    # Run in tmux so it survives disconnection
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="
cd /home/data

# Check files exist
echo 'Checking files...'
ls -lh *.parquet gcp_vm_sampler.py

# Set up paths in script
export INDEX_FILE=/home/data/aef_index.parquet

# Run with nohup so it survives disconnection
echo 'Starting sampler (will run in background)...'
nohup python3 gcp_vm_sampler.py --all --workers $NUM_WORKERS > sampler.log 2>&1 &

echo 'Sampler started! PID:' \$!
echo ''
echo 'To monitor progress:'
echo '  gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"tail -f /home/data/sampler.log\"'
"

    echo ""
    echo_status "Sampler started on VM"
    echo ""
    echo "Monitor progress with:"
    echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command='tail -f /home/data/sampler.log'"
    echo ""
    echo "SSH into VM:"
    echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
}

check_status() {
    echo ""
    echo "============================================================"
    echo "CHECKING STATUS"
    echo "============================================================"

    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="
echo '=== Process Status ==='
ps aux | grep gcp_vm_sampler | grep -v grep || echo 'No sampler running'

echo ''
echo '=== Recent Log Output ==='
tail -30 /home/data/sampler.log 2>/dev/null || echo 'No log file yet'

echo ''
echo '=== BigQuery Row Count ==='
bq query --use_legacy_sql=false 'SELECT COUNT(*) as rows FROM \`$PROJECT_ID.species_data.alphaearth_embeddings\`' 2>/dev/null || echo 'Could not query BigQuery'
"
}

delete_vm() {
    echo ""
    echo "============================================================"
    echo "DELETING VM"
    echo "============================================================"

    read -p "Are you sure you want to delete $VM_NAME? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet
        echo_status "VM deleted"
    else
        echo "Cancelled"
    fi
}

ssh_vm() {
    echo "Connecting to VM..."
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID"
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-}" in
    create)
        create_vm
        ;;
    upload)
        upload_files
        ;;
    run)
        run_sampler
        ;;
    status)
        check_status
        ;;
    delete)
        delete_vm
        ;;
    ssh)
        ssh_vm
        ;;
    "")
        # Default: full setup
        echo "============================================================"
        echo "GCP VM SETUP FOR ALPHAEARTH COG SAMPLING"
        echo "============================================================"
        echo ""
        echo "This will:"
        echo "  1. Create a GCP VM (e2-standard-4, ~\$0.15/hr)"
        echo "  2. Install dependencies"
        echo "  3. Upload your data files"
        echo "  4. Ready to run the sampler"
        echo ""
        echo "Estimated total cost: ~\$1-2"
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled"
            exit 0
        fi

        create_vm
        upload_files

        echo ""
        echo "============================================================"
        echo "SETUP COMPLETE!"
        echo "============================================================"
        echo ""
        echo "Next steps:"
        echo "  1. Run the sampler:"
        echo "     ./setup_gcp_vm.sh run"
        echo ""
        echo "  2. Monitor progress:"
        echo "     ./setup_gcp_vm.sh status"
        echo ""
        echo "  3. When done, delete the VM:"
        echo "     ./setup_gcp_vm.sh delete"
        echo ""
        echo "Or SSH in directly:"
        echo "  ./setup_gcp_vm.sh ssh"
        ;;
    *)
        echo "Usage: $0 [create|upload|run|status|delete|ssh]"
        echo ""
        echo "Commands:"
        echo "  (no args)  - Full setup: create VM + upload files"
        echo "  create     - Create VM only"
        echo "  upload     - Upload files to existing VM"
        echo "  run        - Start the sampler"
        echo "  status     - Check sampler progress"
        echo "  delete     - Delete the VM"
        echo "  ssh        - SSH into the VM"
        exit 1
        ;;
esac
