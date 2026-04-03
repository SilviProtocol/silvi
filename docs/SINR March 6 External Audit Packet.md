# SINR March 6 External Audit Packet

Date: 2026-03-06
Owner: Codex execution handoff
Audience: external AI auditors (Claude, Gemini, other specialist agents)
Objective: provide complete context to diagnose why SINR v3 still underperforms v2.2 on key introduced-species benchmarks despite strict-data improvements.

## 1) Mission and Non-Negotiables

Primary mission:

- Ship a strict-integrity SINR v3 model that beats v2.2 on real-world point inference, including introduced plantation cases.

Non-negotiables:

- Preserve strict HIT/MISS data integrity.
- No destructive operations on strict GEE extraction or BigQuery core tables.
- Version every meaningful experiment (mapping, features, stats, loss contracts, model artifacts).
- No hallucinated quality claims: benchmark claims must cite exact model/checkpoint/contract versions.

## 2) Where We Are Right Now

Strict extraction program status (live in this session):

- Process: `orchestrator/unified_gee_sampler_v3_strict.py`
- Monitor snapshot (session):
  - `new_rows=907,612`
  - `remaining=13,802,726`
  - states: `PENDING 24`, `RUNNING 1`, `SUCCEEDED 471`, `FAILED 5`, `CANCELLED 25`

Training status:

- Latest completed local contract run with phylo leakage mitigation:
  - model dir: `~/model_local_contract_v3_nophylo_5m`
  - log: `orchestrator/local_contract_v3_nophylo_5m_20260306_1502.log`
  - completed to `checkpoint_epoch_5.pt`

## 3) Data Program Context (BQ)

Core table counts (as validated in session):

- strict good train rows: `22,033,317`
  - table: `species_data.sinr_v3_unified_strict_train`
- strict quarantine rows: `9,640,797`
  - table: `species_data.sinr_v3_strict_unified_quarantine`
- strict good species: `45,247`

Preview/local medium tables used for rapid iteration:

- `species_data.sinr_v3_unified_strict_train_v30_medium_5m`
- deterministic shards:
  - `..._s0`, `..._s1`, `..._s2`, `..._s3`, `..._s4`

## 4) Current v3 Input/Output Schema (Model Contract)

Architecture file:

- `orchestrator/train_on_vm.py`

Current input blocks:

- continuous:
  - AE static embedding: `64`
  - environment continuous: contract-dependent (`58` in current online contract)
  - total continuous in current v3 online run: `122`
- AE temporal: `512` (`8 x 64` years)
- categorical: `6` fields
  - `jrc_forest_type`
  - `xiao_planted_forest`
  - `eco_id`
  - `biome_num`
  - `soil_texture_class`
  - `ipcc_forest_class`
- land-state numeric: `5`
- introduced scalar input: `is_introduced`
- phylo vector: `32` (currently disabled in latest recovery branch using `--zero-phylo-input`)

Output heads:

- primary species head: `num_species=45,247`
- aux planted head (binary)
- aux land-state head (6-class)

## 5) Benchmark Coordinate and Why It Matters

Canonical benchmark coordinate:

- `lat=-41.151583464812404`
- `lon=175.09968969862783`

Target species key:

- `GymPiPiPnCx50820-00` (radiata key in current mapping)

Why this benchmark is critical:

- It is known plantation context and historically performed far better in v2-v2.2 (top-50, often top-20, sometimes top-10/#1 in prior user-observed runs).
- Current v3 should not regress this hard after strict expansion.

## 6) Observed Results Timeline (Important)

### Before major fixes

- v3 variants produced catastrophic radiata ranks (`~4,000+` at benchmark coordinate).

### After mapping/stats/versioning fixes

- improved but still poor (`~1,165` range).

### After removing phylo train/serve mismatch (`--zero-phylo-input`)

- latest 5-shard v3 no-phylo model:
  - native: `#71 / 45,247`
  - unknown: `#66 / 45,247`
  - introduced: `#67 / 45,247`

### After activating introduced-ratio boost contract

- with `intro_ratio_contract_v1_strict_full.json` loaded at inference:
  - native: `#67`
  - unknown: `#64`
  - introduced: `#67`

Interpretation:

- Boost path is no longer dead, but introduced conditioning still has weak/incorrect effect size.

### After gate-routing ablation + full 5-shard training (`v4_gatefix_5m`)

- model: `~/model_local_contract_v4_gatefix_5m/best_model.pt`
- run log: `orchestrator/local_contract_v4_gatefix_5m_20260306_1734.log`
- benchmark result before Xiao parity fix in inference path: radiata `#5`
- benchmark result after Xiao parity fix in inference path: radiata `#16`

Interpretation:

- Removing `is_introduced` from gate materially improved ranking behavior.
- A portion of the top-5 performance was due to categorical contract drift in Xiao decoding.
- Contract-aligned result remains in top-20 and is considered the trusted baseline.

## 7) Confirmed Failure Modes (Evidence-backed)

## A) Train/serve phylo mismatch (major; mitigated)

Issue:

- Training previously used per-sample taxon phylo vectors keyed by true `taxon_id`; inference used zero phylo.

Impact:

- Severe mismatch and rank collapse.

Mitigation:

- `--zero-phylo-input` introduced; latest branch uses no phylo in both train/infer path.

## B) Introduced/planted boost was initially inert (fixed), still weak in behavior

Issue:

- `species_intro_ratio` buffer defaulted to zeros unless explicitly loaded.

Fix applied:

- intro-ratio contract support added and loaded.

Remaining problem:

- At benchmark coordinate, increasing `is_introduced` lowers aux planted probability and lowers boost magnitude.

Measured internal diagnostics (same model + intro-ratio contract):

- intro=0.0 -> `planted_prob=0.1562`, `radiata_boost=0.2941`
- intro=0.5 -> `planted_prob=0.0662`, `radiata_boost=0.1245`
- intro=1.0 -> `planted_prob=0.0286`, `radiata_boost=0.0538`

## C) Introduced label is not discriminative enough against dominant Pinus confusers

Strict-table label stats:

- radiata intro mean: `0.831` (`n=9,616`)
- confusers:
  - `GymPiPiPnCx50832-00`: `0.952` (`n=300,107`)
  - `GymPiPiPnCx50811-00`: `0.993` (`n=238,345`)
  - `GymPiPiPnCx50702-00`: `0.966` (`n=196,897`)

Implication:

- introduced scalar alone cannot separate radiata from heavy high-intro confusers.

## D) Feature parity gaps still exist in strict mode

Strict inference contract currently misses at point time:

- env: `aridity_index`, `et0_mm_yr`
- categorical: `ipcc_forest_class` (currently defaults to 0 fallback)

## E) Evaluation protocol still not final-quality

- current local loop still relies on per-shard random split dynamics.
- not yet a fixed global holdout suite (location/time/context) for final promotion decisions.

## 8) Cultivation/Land-State Signal Check at Benchmark Coordinate

Observed raw categorical / land-state signals:

- historical pre-fix point sampler read `xiao_planted_forest=2` (mismatched decode)
- current aligned point sampler reads `xiao_planted_forest=0` at same coordinate
- `jrc_forest_type=20`
- land-state heuristic input: `[2.0, 0.0, 1.0, 0.0, 0.1386]`
- aux land-state head predicts class `2` with ~`0.9996` confidence

Conclusion:

- model does detect cultivation-like state; ranking failure is downstream in species discrimination/coupling.

Top-20 composition follow-up (after Xiao parity, same benchmark):

- The top list is mixed; several locally supported taxa are introduced-labeled, and several are native-labeled.
- Radiata remains top-20 (`#16`), but introduced flag alone does not separate it from all confusers.

Top-20 local label mix evidence (strict table, local box around benchmark):

- introduced-labeled locally (examples): `Leptospermum scoparium`, `Ilex aquifolium`, `Acacia melanoxylon`, `Pinus radiata`
- native-labeled locally (examples): `Coprosma lucida`, `Pseudopanax crassifolius`, `Prumnopitys taxifolia`

Implication: the current top-20 is not a simple native/invader split; model is balancing mixed local signals, and introduced flag cannot be the sole separator.

## 9) Versioned Contracts and Artifacts (Current)

Contract directory:

- `orchestrator/contracts/sinr_v3/`

Key current versions:

- mapping: `mapping_contract_v1.json` (45,247 species)
- feature: `feature_contract_v2_online56.json` (58 env cols)
- frequency: `species_frequency_contract_v2_strict_full.json`
- intro ratio: `intro_ratio_contract_v1_strict_full.json`
- stats: `normalize_stats_v3_v2_online56_preview4m.npz`
- temporal stats: `normalize_temporal_v3_v2_online56_preview4m.npz`

Registry:

- `docs/SINR Versioning Registry.md`

## 10) Safety Constraints for Auditors (Critical)

Do not corrupt/overwrite strict extraction outputs.

Allowed:

- read-only BQ queries,
- creating new versioned artifact files,
- local training/eval runs,
- append-only or new-table writes if absolutely needed for diagnostics.

Disallowed unless explicitly approved:

- destructive BQ table operations,
- killing strict extractor process without explicit instruction,
- changes that alter strict extractor write destinations.

## 11) Exact Files to Audit

Core code:

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/run_local_5m_shard_training.py`

Contract builders:

- `orchestrator/build_sinr_v3_mapping_contract.py`
- `orchestrator/build_sinr_v3_feature_contract.py`
- `orchestrator/build_sinr_v3_species_frequency_contract.py`
- `orchestrator/build_sinr_v3_intro_ratio_contract.py`
- `orchestrator/build_sinr_v3_global_stats.py`

Operational docs:

- `docs/SINR March 6.md`
- `docs/SINR March 6 Recovery Iteration v2.md`
- `docs/SINR March 6 Cultivation Introduced Audit Handoff.md`
- `docs/SINR Versioning Registry.md`
- `.claude/project-management/GO.md`

Logs and model artifacts:

- `orchestrator/local_contract_v2_online56_20260306_1430.log`
- `orchestrator/local_contract_v3_nophylo_5m_20260306_1502.log`
- `~/model_local_contract_v2_online56/`
- `~/model_local_contract_v3_nophylo_5m/`

## 12) Questions External Auditors Must Answer

1. Why does introduced conditioning decrease planted probability at plantation coordinate?
2. Should `is_introduced` be removed from gate input and relocated to residual/post-fusion conditioning?
3. Should planted/land-state auxiliaries be reweighted or decoupled from primary species head?
4. What is the minimum-risk architecture change likely to recover top-20 radiata ranking quickly?
5. Do we need congener-focused contrastive/hard-negative objective for heavy Pinus confusion?
6. Should we disable or redesign boost path entirely and rely on direct objective shaping instead?

## 13) Required Audit Deliverables

External auditors should return:

- ranked root causes (with file:line evidence),
- concrete patch plan by priority (P0/P1/P2),
- expected directional impact on benchmark rank,
- rollback-safe implementation order,
- explicit verification protocol for the benchmark coordinate and introduced slices.

## 15) P0 Experiment Notes (Executed)

Test-time logit adjustment was implemented in `orchestrator/v3_point_inference.py` with:

- `--species-frequency-contract`
- `--logit-adjust-tau`

Observed at benchmark coordinate with model `~/model_local_contract_v3_nophylo_5m`:

- `tau=1.0` severely degraded radiata ranking to ~`#763-786`.
- `tau=0.1` produced near-neutral change (~`#69-72`), no meaningful recovery.

Interpretation:

- Frequency-only post-hoc correction is not sufficient here and can be harmful when too strong.
- Main failure remains architectural coupling of introduced signal and species discrimination.

Gate-routing ablation (introduced removed from gate) initial smoke:

- One-shard epoch1 smoke model:
  - model dir: `~/model_local_contract_v4_gatefix_s0`
  - flags: `--disable-intro-in-gate --zero-phylo-input`
- benchmark radiata result (same coordinate): rank ~`#970` for all intro modes (expected identical without intro gate path).

Interpretation:

- Single-shard epoch1 is not comparable to full 5-shard runs; ranking is currently poor.
- Full 5-shard gate-fix run launched for fair comparison:
  - log: `orchestrator/local_contract_v4_gatefix_5m_20260306_1734.log`
  - model dir: `~/model_local_contract_v4_gatefix_5m`

AN-Full loss ablation (iterative next step):

- Added `--loss-mode an_full` path in `orchestrator/train_on_vm.py` (SINR-style assumed-negative full loss).
- Smoke run (`v5_anfull_s0`, 1 shard, 1 epoch):
  - model dir: `~/model_local_contract_v5_anfull_s0`
  - benchmark radiata rank: `#311` (vs `#970` for earlier one-shard BCE gatefix smoke; not comparable to full 5-shard runs)
- Full 5-shard AN-Full run started:
  - log: `orchestrator/local_contract_v5_anfull_5m_20260306_1953.log`
  - model dir: `~/model_local_contract_v5_anfull_5m`

Xiao train/serve parity fix (inference decode aligned to extractor):

- Updated `orchestrator/location_predictor_FIXED.py` Xiao decoding to match extractor thresholds.
- Benchmark point Xiao value changed from `2` to `0` under aligned decode.
- Same `v4_gatefix_5m` model, same coordinate:
  - before decode alignment: radiata rank `#5`
  - after decode alignment: radiata rank `#16`

Interpretation:

- Previous top-5 result was partly driven by categorical contract drift (OOV plantation class behavior).
- Aligned train/serve semantics still keep radiata in top-20, which is a stronger trustworthy signal.

## 14) Suggested Prompt for Claude/Gemini

"You are auditing SINR v3 introduced-species failure. Use `docs/SINR March 6 External Audit Packet.md` as source of truth and inspect referenced code/logs. Diagnose why benchmark radiata coordinate remains ~rank 64-71 despite strong cultivation and land-state signals. Focus on gate/introduced coupling, planted auxiliary behavior, boost path, and congener confusion. Provide a prioritized patch plan with expected rank improvements and no-risk steps for strict GEE/BQ pipelines."
