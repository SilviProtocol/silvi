# SINR March 6 Cultivation + Introduced Signal Audit Handoff

Date: 2026-03-06
Owner: Codex execution handoff
Purpose: provide a strict, evidence-backed audit package for Claude/Gemini to diagnose why v3 still underperforms v2.2 on radiata despite richer signals.

## Benchmark Coordinate (canonical)

- `lat=-41.151583464812404`
- `lon=175.09968969862783`

Target species key:

- `GymPiPiPnCx50820-00` (radiata key used in current experiments)

## Ground Truth From Current Sampling at This Coordinate

Observed via point sampler + model input inspection:

- pre-alignment point sampler read `xiao_planted_forest=2` (decode mismatch)
- post-alignment point sampler now reads `xiao_planted_forest=0` at same coordinate
- `jrc_forest_type=20` (categorical mapped index `4`)
- `eco_id=171`, `biome_num=4`, `soil_texture_class=4`
- `ipcc_forest_class=0` (currently missing/zero fallback in point path)
- heuristic land-state input vector: `[2.0, 0.0, 1.0, 0.0, 0.1386]`

Land-state auxiliary prediction from latest no-phylo model:

- predicted land state class = `2` with probability `~0.9995` to `~0.9997` across intro modes

Interpretation:

- The model **does** detect cultivation-like land-state signature at this coordinate.
- Failure is downstream in species ranking objective/coupling, not complete absence of cultivation signal.

## Current Radiata Rankings (exact coordinate)

### v2_online56_freqw model

Model dir:

- `~/model_local_contract_v2_online56`

Result:

- native: rank `1,165 / 45,247`
- unknown: rank `1,171 / 45,247`
- introduced: rank `1,170 / 45,247`

### v3_nophylo_5m model (phylo leakage mitigation)

Model dir:

- `~/model_local_contract_v3_nophylo_5m`

Result:

- native: rank `71 / 45,247`
- unknown: rank `66 / 45,247`
- introduced: rank `67 / 45,247`

### v3_nophylo_5m + introduced-ratio contract enabled

Contract:

- `orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json`

Result:

- native: rank `67 / 45,247`
- unknown: rank `64 / 45,247`
- introduced: rank `67 / 45,247`

Interpretation:

- Boost path is no longer dead, but effect size at this coordinate is modest.
- Introduced conditioning remains underpowered relative to expectation.

### v4 gate-fix full run (introduced removed from gate routing)

Model dir:

- `~/model_local_contract_v4_gatefix_5m`

Run log:

- `orchestrator/local_contract_v4_gatefix_5m_20260306_1734.log`

Result:

- after Xiao parity alignment: radiata rank `16 / 45,247`

Interpretation:

- Gate ablation produced a strong recovery versus earlier v3 runs.
- Remaining gap is now confuser discrimination and contract-complete inference, not catastrophic collapse.

Direct internal diagnostics at benchmark coordinate (same model + intro-ratio contract):

- intro=0.0 -> `alpha=0.3807`, `planted_prob=0.1562`, `radiata_boost=0.2941`
- intro=0.5 -> `alpha=0.3124`, `planted_prob=0.0662`, `radiata_boost=0.1245`
- intro=1.0 -> `alpha=0.2512`, `planted_prob=0.0286`, `radiata_boost=0.0538`

This shows introduced input currently *reduces* planted score and therefore reduces boost, which is opposite intended behavior at plantation coordinates.

Interpretation:

- Massive improvement after removing train-time phylo leakage path.
- Still not at v2.2 expectation (top 20 / top 10 / occasional #1).
- Introduced/native delta is still too weak and unstable (only a few rank positions).

## Critical Confirmed Failure Modes (Evidence-backed)

## 1) Train/serve phylo mismatch was severe

`train_on_vm.py` trained with per-sample taxon phylo vectors in trunk input, while point inference had to use zero phylo.

Mitigation added:

- `--zero-phylo-input` flag in:
  - `orchestrator/train_on_vm.py`
  - `orchestrator/run_local_5m_shard_training.py`
  - `orchestrator/run_local_strict_full_overnight.py`

## 2) Introduced boost path is currently inert

From latest checkpoint inspection (`~/model_local_contract_v3_nophylo_5m/best_model.pt`):

- `species_intro_ratio` buffer min/max/mean = `0/0/0`
- nonzero count = `0`
- `boost_scale = 2.0` but multiplied by zeros -> no effect

Code location:

- `orchestrator/train_on_vm.py` (`SINRModelV3.forward`, boost lines)

Implication:

- Explicit introduced/planted boost mechanism is effectively dead.

Status update:

- Code now supports loading a versioned intro-ratio contract into the model buffer.
- Inference run with contract confirms boost activation path is no longer all-zero.
- Remaining issue: impact still too small for target ranking goals.

## 3) Introduced signal response is directionally wrong in aux planted output

At benchmark coordinate (latest model):

- intro=0.0 -> planted prob `0.1562`
- intro=0.5 -> planted prob `0.0662`
- intro=1.0 -> planted prob `0.0286`

Implication:

- As introduced input increases, planted probability decreases at a plantation coordinate.
- This is opposite desired behavior and indicates objective/gating misalignment.

Additional label-distribution context:

- Radiata intro mean in strict table: `0.831` (`n=9,616`).
- Major Pinus confusers have even higher intro means:
  - `GymPiPiPnCx50832-00`: `0.952` (`n=300,107`)
  - `GymPiPiPnCx50811-00`: `0.993` (`n=238,345`)
  - `GymPiPiPnCx50702-00`: `0.966` (`n=196,897`)

Implication: introduced flag alone cannot separate radiata from dominant Pinus confusers; architecture/loss must resolve congener discrimination.

## 4) Feature parity still incomplete under strict mode

Strict feature-contract check still fails for point inference due to missing:

- env: `aridity_index`, `et0_mm_yr`
- categorical: `ipcc_forest_class`

Even though v2.2 lacked these, this still matters because v3 was trained with the v3 feature contract and auxiliary coupling.

## Why “three ranks” (native/unknown/introduced) exist

The model takes `is_introduced` as an explicit input feature and uses it in gate input. Running all three values is a diagnostic sweep to see sensitivity and directionality.

Current issue is not that the sweep exists; it is that introduced conditioning is not producing expected ecological direction.

## Relevant Files to Audit

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/local_contract_v2_online56_20260306_1430.log`
- `orchestrator/local_contract_v3_nophylo_5m_20260306_1502.log`
- `docs/SINR March 6.md`
- `docs/SINR March 6 Recovery Iteration v2.md`
- `docs/SINR Versioning Registry.md`
- `.claude/project-management/GO.md`

## Versioned Artifacts Used in Latest Run

- Mapping: `orchestrator/contracts/sinr_v3/mapping_contract_v1.json`
- Feature contract: `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`
- Species frequency: `orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json`
- Stats: `orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz`
- Temporal stats: `orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz`

## Questions for External Auditors (Claude/Gemini)

1. Why does introduced conditioning fail to move radiata into top-20 despite plantation signatures being present?
2. Should `is_introduced` be removed from gate input and moved to a post-fusion residual path?
3. Should aux planted/land-state losses be decoupled from main species objective or reweighted dynamically?
4. Should explicit introduced boost be replaced with a real per-species/region prior (instead of zero buffer)?
5. What is the minimal architecture/loss change to recover v2.2-level radiata ranking quickly?

## New Forensic Clues From Occurrence Data (March 6 follow-up)

### 1) NZ introduced labels are not discriminative across top confusers

For the top ranked confusers at the benchmark coordinate, NZ-only introduced mean is `1.0` for all:

- `GymPiPiPnCx50820-00` (Pinus radiata): `n_nz=1107`
- `AngMaRoRsCx44234-00` (Crataegus monogyna): `n_nz=1062`
- `GymPiPiPnCx50850-00` (Pseudotsuga menziesii): `n_nz=833`
- `GymPiPiPnCx50804-00` (Pinus nigra): `n_nz=50`
- `GymPiPiPnCx50832-00` (Pinus sylvestris): `n_nz=25`

Implication: native vs introduced flag cannot separate radiata from these top local confusers in NZ.

### 2) Local density near coordinate favors confusers in some cases

Within 25km around benchmark coordinate:

- `Crataegus monogyna`: `47` rows (min distance ~`2.18 km`)
- `Pinus radiata`: `39` rows (min distance ~`6.33 km`)
- `Pseudotsuga menziesii`: `4` rows
- `Pinus nigra`: `1` row
- `Pinus sylvestris`: `0` rows

Implication: non-radiata species can have stronger local sample density and nearest-point evidence.

### 3) AlphaEarth nearest-neighbor context is not pine-dominant at this point

Across all occurrences within 25km, nearest AE embedding neighbors to the query point are largely non-pine taxa (various `AngMa*` IDs).

Implication: AE signal alone is not strongly pinus-specific here; ranking depends heavily on coupled trunk/aux objectives and class priors.

### 4) Critical categorical mismatch: `xiao_planted_forest=2` never appears in strict training table

Global strict-table distribution:

- `xiao_planted_forest=NULL`: `9,568,912`
- `xiao_planted_forest=0`: `7,549,445`
- `xiao_planted_forest=1`: `4,914,960`
- `xiao_planted_forest=2`: `0`

But at inference benchmark coordinate, live sampler returns `xiao_planted_forest=2` (plantation).

Implication: the model sees plantation class at inference that it never learned in training (OOV category behavior). This is a major clue for unstable plantation discrimination and should be treated as a data-contract bug.

Status update:

- Point inference Xiao decoding was aligned to extractor logic.
- At benchmark coordinate, sampled Xiao changed from `2` to `0` after alignment.
- Re-evaluation on same gate-fix model moved radiata from `#5` to `#16`.
- This indicates the prior top-5 had leakage from train/serve categorical mismatch; top-20 after alignment is more trustworthy.

## Suggested Prompt Snippet for Auditors

"Audit the attached SINR v3 files and logs. Assume benchmark coordinate `-41.151583464812404, 175.09968969862783` for radiata (`GymPiPiPnCx50820-00`). Include Xiao decode parity findings (pre-fix xiao=2 vs aligned xiao=0) and explain why radiata remains around top-20 rather than top-5 under contract-aligned inference. Prioritize fixes to congener discrimination, introduced conditioning, and objective coupling. Provide a ranked implementation plan with expected impact and minimal-risk order."
