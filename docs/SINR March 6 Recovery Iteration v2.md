# SINR March 6 Recovery Iteration v2

Date: 2026-03-06
Purpose: execute anti-collapse recovery changes after forensic audits confirmed v3 train/serve drift and frequency-dominated taxonomic collapse.

## Inputs

- `docs/SINR March 6.md`
- `docs/SINR Versioning Registry.md`
- `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md`
- External forensic reviews (Gemini + Claude) aligned on:
  - missing-feature zero-fill distribution shift,
  - per-species class imbalance,
  - weak evaluation semantics,
  - introduced-species underperformance.

## What Changed in This Iteration

## 1) Versioned feature contract support

Code:

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/build_sinr_v3_global_stats.py`
- `orchestrator/run_local_5m_shard_training.py`
- `orchestrator/run_local_strict_full_overnight.py`

New behavior:

- Trainer can load `--feature-contract` and override `ENV_CONTINUOUS_COLS` at runtime.
- Inference can load the same feature contract for parity.
- Stats builder can compute normalization against a specific feature contract.
- Shard runners pass feature-contract flags through to trainer.

## 2) Versioned feature contract artifact

New script:

- `orchestrator/build_sinr_v3_feature_contract.py`

Generated:

- `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`
- `orchestrator/contracts/sinr_v3/feature_contract_latest.json`

Current online contract count:

- `num_env_continuous = 58` (online-servable subset mode)

## 3) Versioned species-frequency contract + weighted loss path

New script:

- `orchestrator/build_sinr_v3_species_frequency_contract.py`

Generated:

- `orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json`
- `orchestrator/contracts/sinr_v3/species_frequency_contract_latest.json`

Key observed distribution from strict table:

- min count: `1`
- median count: `8`
- max count: `415,050`

Trainer changes:

- `train_on_vm.py` now supports `--species-frequency-contract`.
- Uses species-frequency contract to compute per-species sample weighting.
- Uses weighted BCE path (`reduction='none'` + per-sample weighting) with clipped weights.

## 4) Versioned stats for online contract

Generated:

- `orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz`
- `orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz`
- `orchestrator/contracts/sinr_v3/stats_contract_v2_online56_preview4m.json`

Scope:

- built from local shard parquet root `~/data_5m_shards`
- rows seen: `5,001,204`

## 5) New training run (contract-aligned v2)

Started run:

- `orchestrator/local_contract_v2_online56_20260306_1430.log`

Command includes:

- mapping contract v1 (`45,247` species)
- feature contract `v2_online56`
- frozen stats `v2_online56_preview4m`
- species-frequency contract `v2_strict_full`
- strict contract checks enabled

Model output dir:

- `~/model_local_contract_v2_online56`

## Known Limitations Still Open

1. Land-state derivation parity is not fully solved (heuristic inference path still exists).
2. Point-time carbon/productivity fields are still not fully live-sampled in point inference.
3. Validation remains chunk-local random split in this path (global holdout suite still pending).

## Critical Root Cause Discovered After v2 Run

We identified a fundamental train/serve bug:

- Training used per-sample phylo vectors keyed by `taxon_id` (the true label) inside model input trunk.
- Point inference cannot know true species upfront, so inference path used zero phylo vector.

Impact:

- This is label-leakage-like behavior in train/val and a severe mismatch at inference.
- It explains why validation looked strong while real point ranking collapsed.

Evidence (same model family, same coordinate):

- v2 model (with phylo-in-train, zero-phylo-infer): radiata rank ~`1,165`.
- one-shard epoch1 retrain with `--zero-phylo-input`: radiata rank improved to ~`80-85`.

Immediate mitigation launched:

- Added `--zero-phylo-input` to `train_on_vm.py` and shard runners.
- Started full 5-shard run with no-phylo leakage path:
  - log: `orchestrator/local_contract_v3_nophylo_5m_20260306_1502.log`
  - model dir: `~/model_local_contract_v3_nophylo_5m`

## Next Mandatory Checks

1. Evaluate radiata at exact coordinate `-41.151583464812404, 175.09968969862783` after v2 run completes.
2. Compare introduced/native/unknown ranking deltas against prior v1 contract model.
3. Decide whether to proceed with full online-sampled feature restoration (rather than reduced online subset).
