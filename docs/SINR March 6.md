# SINR March 6

Date: 2026-03-06
Owner: Codex session handoff
Scope: strict v3 training/inference integrity, evaluation validity, and GEE extraction operating posture.

## Executive Context

We advanced strict v3 training throughput substantially (full local chunk pass completed), but uncovered critical train/serve contract drift that explains why behavior at key introduced coordinates (radiata NZ) is still not acceptable.

The core issue is not a single bad hyperparameter. It is a stack of mismatches across:

- target-space mapping,
- normalization strategy,
- training-vs-inference feature availability,
- land-state derivation consistency,
- and evaluation protocol.

These mismatches can produce apparently strong chunk validation metrics while still yielding poor ecological ranking behavior at point inference.

## What We Ran

### Local training

- Completed overnight strict-full local chunk run using `orchestrator/run_local_strict_full_overnight.py`.
- Processed full strict export via chunked parquet copies (24 chunks).
- Finished at epoch 27 (from resumed epoch 3 baseline), with final checkpoint in `~/model_local_5m/checkpoint_epoch_27.pt` and best model in `~/model_local_5m/best_model.pt`.

### GEE strict extraction

- Strict extractor remains active via `orchestrator/unified_gee_sampler_v3_strict.py`.
- Last observed monitor snapshot in-session: `new_rows=640,046`, `remaining=14,070,292`, states showed active queue/run/succeeded mix.

## What We Learned (Critical Findings)

## 1) Target-space mismatch (major)

- Current local training path loads `~/species_mapping.json` in `orchestrator/train_on_vm.py`.
- That mapping is 35,561 species, while strict-good table is ~45,247 species.
- Training filters rows to species present in mapping; out-of-mapping strict rows are dropped.

Impact:

- Large portion of strict taxonomy never trains.
- Introduced/edge taxa are disproportionately likely to be dropped.
- Confusion among nearest in-vocabulary taxa is amplified.

## 2) Normalization drift across chunk-resume training (major)

- `train_on_vm.py` recomputes normalization from each loaded chunk and overwrites stats.
- Chunked resume means the model sees shifting feature scales over time.
- Inference later uses the final written stats, which are not global-train stable.

Impact:

- Apparent chunk metrics can improve while deployment behavior remains unstable.
- Rank behavior at point inference can become inconsistent.

## 3) Inference feature contract is incomplete vs training (major)

- v3 training expects full feature contract:
  - continuous: AE64 + Env89,
  - temporal: AE512,
  - categorical: 6,
  - land-state: 5,
  - intro flag + phylo.
- Point inference currently cannot provide all train-time env fields; many missing fields default to `0.0`.
- Missing block includes major carbon/point-time features and other fields (roughly 33 env fields unavailable in current point path).

Impact:

- Inference distribution differs from training distribution.
- Plantation/introduced discrimination degrades.

## 4) Land-state and categorical inconsistencies (major)

- Inference land-state is heuristic and not guaranteed equivalent to training derivation.
- `ipcc_forest_class` is part of v3 categorical training config but not reliably supplied at point inference.

Impact:

- Gate and auxiliary interactions can be driven by contract mismatch.
- Introduced/native behavior can look contradictory at specific sites.

## 5) Evaluation protocol currently overstates confidence (major)

- Per-chunk random val split is not a fixed global holdout.
- Validation is recomputed per chunk and not comparable as a single global epoch metric.
- Best model selection in this workflow is chunk-local progression, not strict global-selection against a frozen validation partition.

Impact:

- Metrics can look strong while production point behavior remains poor.

## 6) Objective coupling risk exists (important)

- Main species objective, planted aux head, land-state aux head, and gate interactions can create shortcuts.
- Current configuration can yield overconfident wrong taxa under distribution shift.

Impact:

- High-confidence misranking is plausible even with improving chunk metrics.

## Radiata NZ Check (Current Reality)

Coordinate used:

- `lat=-41.15177045881628`, `lon=175.09861821938483`

With new v3 point script (`orchestrator/v3_point_inference.py`) and current model:

- native (`is_introduced=0.0`): rank ~27
- unknown (`0.5`): rank ~41
- introduced (`1.0`): rank ~54

This remains unacceptable for intended ecological behavior at that location.

Interpretation:

- The result is consistent with unresolved train/serve/eval contract drift.
- Not acceptable as production signal yet.

## Mistakes We Made

1. Treated chunk-epoch metrics as if they represented globally stable quality.
2. Advanced training without first hard-locking a strict feature + mapping contract.
3. Accepted partial point feature availability with silent zero-filling for many train-time fields.
4. Did not enforce global normalization and global held-out protocol before interpreting gains.

## Fix Plan (Now Canonical)

## P0 (must do first)

1. **Canonical mapping contract**
   - Generate mapping from strict-good source-of-truth.
   - Freeze and version (`mapping_contract_v1`), including alias/canonical rules.
   - Assert model output dimension matches contract.

2. **Global normalization contract**
   - Compute mean/std once from global train split only (streaming-safe).
   - Freeze artifacts and forbid per-chunk overwrite.

3. **Feature contract enforcement**
   - Define required v3 inference fields with units/ranges/provenance.
   - Hard-fail or explicit degraded-mode flag if required fields are missing.
   - No silent zero-fill for critical fields.

## P1 (production readiness)

4. Unify train and inference derivations for land-state and key env transforms.
5. Provide missing categorical/continuous fields (or retrain on online-available subset only).
6. Move to fixed global holdouts:
   - context-holdout,
   - location-holdout,
   - time-holdout.
7. Report introduced diagnostics explicitly (native/unknown/introduced sweeps and slice metrics).

## P2 (quality hardening)

8. Run objective ablations (BCE vs CE, aux coupling toggles, gate sensitivity).
9. Add calibration diagnostics (ECE/Brier/high-confidence-wrong rate).
10. Lock one canonical v3 inference endpoint; isolate/deprecate v2 path for v3 claims.

## Safety / Data Integrity Notes

### BigQuery/GEE destructive risk

Current strict extractor path is configured non-destructively:

- `ee.batch.Export.table.toBigQuery(..., append=True, overwrite=False)`
- Unsampleable ledger table is created with `CREATE TABLE IF NOT EXISTS` and appended to.

Implication:

- It should not overwrite existing strict tables.
- It can append new rows; duplicates are possible if retries/restarts are not deduped downstream, but overwrite/corruption risk from this path is low.

### GEE batching details

- Default `--batch-size` in strict sampler: `2000` contexts per batch.
- Current run command uses `--batch-size 2000 --pool-size 25`.
- So yes, we are doing many rows per batch, and up to 25 batches concurrently.

Operationally, that means each successful GEE export task typically contributes up to ~2000 sampled context rows (subject to task failures/retries/unsampleable contexts).

## Immediate Next Execution Order

1. Build and validate canonical mapping contract from strict-good.
2. Build global train-only normalization artifacts and freeze them.
3. Add strict feature contract validator to both training and point inference.
4. Re-run training with fixed contracts.
5. Re-evaluate radiata NZ and introduced-slice metrics under fixed protocol.

## Versioning Started (Preserve Previous Versions)

We started explicit artifact versioning and historical preservation.

Registry:

- `docs/SINR Versioning Registry.md`

Created contracts/artifacts:

- `orchestrator/contracts/sinr_v3/mapping_contract_v1.json`
- `orchestrator/contracts/sinr_v3/species_mapping_v1.json`
- `orchestrator/contracts/sinr_v3/mapping_contract_latest.json`
- `orchestrator/contracts/sinr_v3/species_mapping_latest.json`
- `orchestrator/contracts/sinr_v3/stats_contract_v1_preview4m.json`
- `orchestrator/contracts/sinr_v3/normalize_stats_v3_v1_preview4m.npz`
- `orchestrator/contracts/sinr_v3/normalize_temporal_v3_v1_preview4m.npz`
- `orchestrator/contracts/sinr_v3/stats_contract_latest.json`

Code now supports version-aware loading/writing:

- `orchestrator/train_on_vm.py`
  - supports mapping contracts + frozen stats + versioned artifact writes
- `orchestrator/v3_point_inference.py`
  - supports versioned artifact selection and mapping hash validation

## Recovery Iteration v2 (Versioned)

Detailed log:

- `docs/SINR March 6 Recovery Iteration v2.md`

New versioned contracts created:

- `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`
- `orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json`
- `orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz`
- `orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz`
- `orchestrator/contracts/sinr_v3/stats_contract_v2_online56_preview4m.json`

New scripts created:

- `orchestrator/build_sinr_v3_feature_contract.py`
- `orchestrator/build_sinr_v3_species_frequency_contract.py`

Trainer/inference changes (version-aware):

- `train_on_vm.py` now supports `--feature-contract` and `--species-frequency-contract`.
- `v3_point_inference.py` now supports `--feature-contract`.

Current benchmark reality (exact user coordinate):

- coord: `-41.151583464812404, 175.09968969862783`
- v1-contract model result remained unacceptable: radiata rank ~`4,131` to `4,276` / `45,247`.

Status:

- Started new local run with v2 contracts + frequency weighting:
  - log: `orchestrator/local_contract_v2_online56_20260306_1430.log`
  - model dir: `~/model_local_contract_v2_online56`

## Alignment to Master SINR Strategy (March 6 reality check)

Reference: `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md`

### Where we are aligned

- We are still executing the model progression intent (data-first -> stronger neural head), with strict extraction actively rebuilding temporal fidelity at context grain.
- We are preserving strict HIT/MISS separation and not training from known-bad exploded tables.
- We are continuing parallel extraction while training preview cycles, which is consistent with staged execution toward final strict-full candidate.

### Where we drifted off-plan

1. **Validation framework drift**
   - Master strategy requires spatially robust evaluation (spatial CV / geography-aware holdouts).
   - Current chunk-local random validation does not satisfy this and can overstate quality.

2. **Feature contract drift**
   - Master strategy assumes coherent multi-signal inputs and disturbance-aware consistency.
   - Current point inference cannot provide full v3 training contract; missing critical fields are currently imputed to zero.

3. **Target-space drift**
   - Master strategy trajectory assumes scaling toward broad species coverage.
   - Current local mapping in trainer reduced effective species space below strict table coverage.

4. **Endpoint/version drift**
   - Master file labels `location_predictor_FIXED.py` as v3 live, but operationally it still loads v2.2 model path for `/sinr-infer`.
   - This creates split-brain interpretation between expected and actual serving behavior.

### Back-on-track definition (must be true before “v3 improved over v2.2” claims)

- Canonical full strict species mapping is enforced in both train and inference.
- Global train-only normalization artifacts are frozen and reused (no per-chunk recompute overwrite).
- v3 inference contract is explicit and validated (no silent critical-field zero-fill).
- Evaluation uses fixed global holdouts (context + location + time), not per-chunk local val.
- Radiata benchmark and introduced-slice diagnostics are re-run under the fixed protocol.

### Re-alignment sequence (execution)

1. Lock mapping + normalization contracts.
2. Enforce feature contract validator in training and point inference.
3. Re-run strict training with fixed contracts.
4. Run master-strategy-consistent evaluation suite (spatial/time aware + introduced diagnostics).
5. Only then decide whether v3 candidate is better than v2.2 for promotion.
