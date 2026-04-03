# SINR v3.0 Strict Preview Runbook

Date: 2026-03-06

## Objective

Run a high-confidence preview training cycle while strict full re-extraction is still running.

Preview training table:

- `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean`

This table is HIT-only and has:

- canonical-key dedup completed
- required trainer columns present
- key carbon sentinels (`-9999`) converted to NULL for major carbon fields

## Quick Status Checks

### 1) Run data preflight

```bash
python3 orchestrator/check_v30_preview_readiness.py
```

Expected result: `Result: PASS`.

### 2) Confirm strict full extraction still running (parallel long job)

```bash
ps -p 74926 -o pid,etime,%cpu,%mem,command
```

### 3) Live extraction telemetry snapshot

```bash
python3 orchestrator/monitor_strict_extraction.py
```

This prints current strict-full rows, EE task states, and rolling ETA when enough progress deltas exist.

## Cloud GPU Training (recommended)

`orchestrator/train_on_gcp.sh` is now set to export from:

- `sinr_v3_unified_strict_train_v30_preview_clean`

Run sequence:

```bash
./orchestrator/train_on_gcp.sh launch
./orchestrator/train_on_gcp.sh export
./orchestrator/train_on_gcp.sh train
./orchestrator/train_on_gcp.sh download
```

Optional full one-shot:

```bash
./orchestrator/train_on_gcp.sh all
```

## Progress Visibility (training)

You will have real-time visibility of epochs and checkpoints via VM logs.

### Tail training logs live

```bash
gcloud compute ssh sinr-v3-training --zone=us-central1-c --project=treekipedia-479918 --command "tail -f ~/training.log"
```

### Check epoch-level artifacts during run

```bash
gcloud compute ssh sinr-v3-training --zone=us-central1-c --project=treekipedia-479918 --command "ls -lh ~/model/"
```

Look for:

- `best_model.pt` (updates when validation improves)
- `checkpoint_epochN.pt`
- `training_log.json`

### Start testing immediately after model is ready

As soon as `best_model.pt` exists and training ends, run:

```bash
./orchestrator/train_on_gcp.sh download
```

Then test with downloaded artifacts in:

- `orchestrator/sinr_model_v3/`

## Artifacts

Downloaded model artifacts go to:

- `orchestrator/sinr_model_v3/`

Use clear naming for preview outputs:

- `SINR_v3.0_strict_preview`

## Important Constraints

- Do not train from `sinr_v3_unified_v2_final`.
- Do not merge quarantine rows into preview training.
- Keep strict full extraction running; preview training is for early learning/tuning only.

## Versioned Contracts (Required Going Forward)

Contract registry:

- `docs/SINR Versioning Registry.md`

Mapping contract build (strict table -> versioned mapping):

```bash
python3 orchestrator/build_sinr_v3_mapping_contract.py --version v1
```

Train with explicit contract references:

```bash
python3 orchestrator/train_on_vm.py --train \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v1_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v1_preview4m.npz \
  --artifact-version v1_preview4m \
  --require-full-contract
```

Notes:

- Trainer now writes versioned artifacts and keeps stable latest aliases.
- Do not delete older `vN` files; create `vN+1` for changes.

Online-contract variant (current recovery branch):

```bash
python3 orchestrator/train_on_vm.py --train \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --artifact-version v2_online56_freqw \
  --require-full-contract
```

## Local Overnight 5M Shard Training (Apple Silicon)

Use the deterministic 5x ~1M shard tables to train sequentially without loading all 5M rows at once.

Script:

- `orchestrator/run_local_5m_shard_training.py`

Default tables used:

- `sinr_v3_unified_strict_train_v30_medium_5m_s0` ... `s4`

Example run:

```bash
python3 orchestrator/run_local_5m_shard_training.py \
  --batch-size 1536 \
  --model-dir ~/model_local_5m \
  --local-data-root ~/data_5m_shards
```

Resume from prior progress (example: already completed 2 epochs/shards):

```bash
python3 orchestrator/run_local_5m_shard_training.py \
  --start-shard 2 \
  --initial-epoch 2 \
  --batch-size 1536 \
  --model-dir ~/model_local_5m
```

Notes:

- The runner exports each shard table to GCS parquet, copies parquet locally, and calls `train_on_vm.py`.
- It increments total epochs per shard and resumes using `checkpoint_epoch_N.pt`.
- Use `--skip-export` only if local shard parquet files are already present.

## Known Launch Constraint (current)

If `launch` fails with GPU quota errors (`GPUS_PER_GPU_FAMILY` or `GPUS_ALL_REGIONS`), request/enable GPU quota before retrying.

## Next After Preview

1. Continue strict full re-extraction to completion.
2. Rebuild strict full unified training table.
3. Run `SINR_v3.1_strict_full` final training cycle.
