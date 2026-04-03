# SINR March 7 Deep Root Cause + Action Plan

Date: 2026-03-07  
Owner: Codex deep-dive pass  
Scope: benchmark recovery for `GymPiPiPnCx50820-00` at `lat=-41.151583464812404`, `lon=175.09968969862783`

## 1) Executive outcome

Current trusted control remains:

- `v4_gatefix_5m` + Xiao parity-aligned inference: **rank #16 / 45,247**.

Deep-dive conclusion:

- This is not a single-cause failure.
- The strongest current blockers are:
  1. residual train/serve feature mismatch in point inference,
  2. land-state inference heuristic mismatch sensitivity,
  3. loss-function parity drift from v2.2 (especially AN-Full behavior),
  4. auxiliary objective coupling side effects.

## 2) Confirmed findings from code + runs

### A. Point inference still fails strict feature contract

Running `v3_point_inference.py` with `--strict-feature-contract` at the benchmark point throws:

- `ValueError: Missing required feature-contract fields: env_missing=2, cat_missing=1`

Missing fields are:

- env: `aridity_index`, `et0_mm_yr`
- categorical: `ipcc_forest_class`

Implication:

- default non-strict inference silently zero-fills missing fields, so point benchmarking still has non-trivial train/serve drift risk.

Primary references:

- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`

### B. Land-state path is materially affecting rank

Benchmark checks on fixed checkpoints:

- `v4_gatefix_5m`:
  - `land_state_mode=heuristic` -> rank `#16`
  - `land_state_mode=zero` -> rank `#12`
- `v5_anfull_5m`:
  - `land_state_mode=heuristic` (historical) -> rank `#23`
  - `land_state_mode=zero` -> rank `#19`

Implication:

- current heuristic land-state derivation can degrade benchmark rank even when model weights are fixed.

Primary references:

- `orchestrator/v3_point_inference.py`
- `orchestrator/land_state_engine.py`

### C. Introduced-mode invariance is expected under current flags

With trusted control settings (`--disable-intro-in-gate` and no intro residual path), changing `is_introduced` among `0.0/0.5/1.0` has no active forward-path consumer.

Implication:

- equal ranks across introduced slices are expected behavior, not necessarily a new bug.

Primary references:

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`

### D. AN-Full parity with v2.2 is not clean

Observed implementation divergence:

- v2.2 AN-Full correction term in `train_sinr_model.py` uses `-target_log_neg + pos_weight*(-target_log_pos)`.
- v3 branch in `train_on_vm.py` currently uses `t_log_neg + pos_weight*(-t_log_pos)`.

Implication:

- correction-term sign/definition mismatch is a high-probability regression vector for AN-Full experiments.

Primary references:

- `orchestrator/train_sinr_model.py`
- `orchestrator/train_on_vm.py`

### E. Planted-label-mode branch tested and failed in smoke

Single-variable smoke outcomes:

- `strict_planted3`: rank `#919`
- `land_state2`: rank `#256`

Implication:

- this planted-label semantic branch is currently regressive vs control `#16`; de-prioritize for now.

Primary references:

- `orchestrator/train_on_vm.py`
- `orchestrator/run_local_5m_shard_training.py`

## 3) Root-cause ranking (highest confidence first)

1. **Inference feature parity gap remains** (strict contract not actually satisfiable at point inference today).
2. **Land-state train/serve mismatch sensitivity** (heuristic inference path can move rank by multiple slots).
3. **Loss parity drift from v2.2** (AN-Full correction behavior, plus objective stack differences).
4. **Auxiliary coupling risk** (planted/land-state tasks can perturb main species ranking).
5. **Confuser ecology remains hard** (real congener/introduced confusers), but likely amplified by the above implementation issues.

## 4) Immediate low-risk plan (single-variable only)

## P0-1: Inference parity hardening (no retraining)

Goal:

- make `--strict-feature-contract` pass for benchmark inference.

Patch scope:

- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/v3_point_inference.py`

Add/derive:

- `aridity_index`
- `et0_mm_yr`
- categorical `ipcc_forest_class`

Verification:

- run benchmark command with `--strict-feature-contract` and confirm no missing-field error.

## P0-2: Land-state sensitivity gate (no retraining)

Goal:

- establish whether benchmark ranking should be reported under `land_state_mode=zero` until parity-equivalent land-state inference exists.

Verification:

- compare fixed checkpoint ranks under `heuristic` vs `zero` and log both.

## P0-3: AN-Full parity fix (single-variable retrain)

Goal:

- align AN-Full correction-term behavior with v2.2 intended implementation.

Patch scope:

- `orchestrator/train_on_vm.py` only.

Experiment:

- smoke on s0 first with control settings; only proceed to 5-shard if smoke beats its own paired BCE control.

## P1-1: Aux ablations (single-variable each)

Two independent runs:

1. `--aux-land-state-weight 0` (keep planted aux as-is)
2. `--aux-planted-weight 0` (keep land-state aux as-is)

Goal:

- isolate whether either auxiliary branch is harming benchmark rank.

## 5) Decision gates

Promote only if all are true:

1. benchmark rank improves vs trusted control (`#16`) or clearly improves on a robust paired protocol,
2. strict feature contract passes at inference,
3. results are stable across at least two re-runs with identical artifacts and commands.

Stop and rollback if:

- rank worsens by >5 places versus paired control,
- introduced slices become erratic without architectural justification,
- strict-feature-contract fails.

## 6) Useful commands (copy-ready)

v4 control, strict parity check:

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 \
  --lon 175.09968969862783 \
  --year 2023 \
  --model-dir ~/model_local_contract_v4_gatefix_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all \
  --top-k 20 \
  --disable-intro-in-gate \
  --strict-feature-contract
```

v4 land-state sensitivity check:

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 \
  --lon 175.09968969862783 \
  --year 2023 \
  --model-dir ~/model_local_contract_v4_gatefix_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all \
  --top-k 20 \
  --disable-intro-in-gate \
  --land-state-mode zero
```
