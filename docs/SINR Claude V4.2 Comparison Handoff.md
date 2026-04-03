# SINR Claude V4.2 Comparison Handoff

Superseded note (2026-03-19): this handoff is now historical reference only.
Backfill has already been merged via the fast-safe no-GEDI path, and the first merged run is complete.
For active work, read `docs/SINR Current Program State.md` and `docs/SINR Claude Opinion Handoff - Post-Merge Radiata Forensics.md` first.

Date: 2026-03-16
Audience: Claude or any successor agent continuing SINR after the failed `V4.1` radiata benchmark
Status: superseded historical handoff

## Mission

`V4.1` is no longer the active forward path.

Treat `V4.1` as a completed-but-retired preview baseline.

The current active path is `V4.2 comparison and SINR alignment`:

- explain why the corrected `V4.1` preview still fails the canonical radiata benchmark,
- compare the current trainer against the actual SINR method from the paper/repo,
- design and, if justified, implement minimum-change non-destructive experiments on the current `V4.1` data,
- and only after that decide whether / how backfill should join the `V4` program.

Do **not** quietly widen the data estate or join backfill into the training program without an explicit decision.

## Read First

1. `.claude/project-management/GO.md`
2. `docs/SINR V4.1 Data Confidence Matrix.md`
3. `docs/SINR Claude V4.1 Preview Handoff.md` (now historical baseline context)
4. `docs/SINR v3 Master Recovery Plan.md`
5. `docs/SINR BigQuery Lineage Map.md`
6. `docs/SINR Temporal Sampling Contract.md`
7. `docs/SINR Fresh Validation Findings.md`
8. The actual SINR method sources:
   - `https://sites.google.com/view/sinr-geo`
   - `https://github.com/elijahcole/sinr`

Then inspect these local files:

- `orchestrator/train_on_vm.py`
- `orchestrator/run_local_5m_shard_training.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/unified_gee_sampler_v3.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/build_sinr_v41_preview_train_table.py`
- `orchestrator/build_sinr_v41_preview_train_stats.py`
- `orchestrator/build_sinr_v41_preview_train_feature_contract.py`
- `orchestrator/export_v41_preview_shards.py`

## Current Proven State

### 1. Canonical repaired `new_gbif` strict lineage exists

Source table:

- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`

Key facts:

- `8,838,488` rows
- `8,838,488` distinct contexts
- `0` duplicate context groups
- `0` effective unresolved contexts
- `3` explicit singleton unsampleables logged separately

### 2. `V4.1` preview assets exist and are internally correct

Feature-grain preview table:

- `species_data.sinr_v41_preview_strict_core_v1`

Training-grain preview table:

- `species_data.sinr_v41_preview_strict_core_train_v1`

Training-grain facts:

- `11,920,314` rows
- `19,043` unique species
- `0` null `taxon_id`
- labels/meta from `sinr_v3_unified_strict_train_v30_preview_clean`
- features from repaired strict lineage `...completed_v1`

Training artifacts:

- `orchestrator/contracts/sinr_v3/species_mapping_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/species_frequency_contract_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/normalize_stats_v41_preview_train.npz`
- `orchestrator/contracts/sinr_v3/normalize_temporal_v41_preview_train.npz`
- `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`

### 3. Corrected `V4.1` training run finished

Run log:

- `orchestrator/v41_preview_training_r2_20260316_004743.log`

Configuration facts verified from the run:

- uses training-grain shards from `~/data_v41_preview_train_shards`
- uses `19,043`-species V4.1 mapping, not the old `35,561` mapping
- uses species-frequency weighting and intro-ratio contract
- uses location encoding
- uses `2` cycles × `12` shards = `24` shard-epochs total
- finishes at `checkpoint_epoch_24.pt`

### 4. Canonical radiata benchmark result is still bad

Benchmark coordinate:

- `lat = -41.151583464812404`
- `lon = 175.09968969862783`
- `year = 2023`
- target taxon = `GymPiPiPnCx50820-00`

Finished corrected `V4.1` result:

- `rank #105 / 19,043`
- `prob = 0.6083`

Important verified behavior:

- running inference with `introduced = 0.0`, `0.5`, and `1.0` leaves the rank unchanged at `#105`
- so the current model is effectively not getting useful radiata separation from the introduced-conditioning path

### 5. Why this is alarming

The top predictions above radiata at the benchmark are mostly `AngMa...` taxa, i.e. broadleaf/angiosperm/native-looking species, not just nearby conifer confusers.

That suggests the model is **not** simply failing among Pinus congeners; it is also failing to identify the location as plantation-like enough to make radiata competitive.

### 6. Why `V4.1` is a weak radiata training slice

Verified radiata support by table:

| Table | Total rows | NZ rows | Rows within 25km of benchmark |
|---|---:|---:|---:|
| `v2_unified_v1` | `4,146` | `1,128` | `42` |
| `v2_unified_v2` | `13,918` | `1,171` | `40` |
| `v3_preview_clean` | `9,616` | `1,107` | `39` |
| `v3_strict_train` | `9,616` | `1,107` | `39` |
| `v41_preview_train` | `706` | `272` | `7` |

Verified source split inside old V3 preview-clean:

- `backfill` radiata rows = `8,705`
- `new_gbif` radiata rows = `911`

So over `90%` of historical radiata support lived in `backfill`, not `new_gbif`.

This means the current `new_gbif`-only preview is inherently a much thinner radiata slice.

### 7. Confuser ratios are much worse in `V4.1`

Example confuser ratios against radiata:

In `v3_preview_clean`:

- `GymPiPiPnCx50832-00 / radiata = 31.2x`
- `GymPiPiCpRs50414-00 / radiata = 20.0x`

In `v41_preview_train`:

- `GymPiPiPnCx50832-00 / radiata = 56.8x`
- `GymPiPiCpRs50414-00 / radiata = 89.1x`

So radiata is not only smaller in absolute support; it is also much more drowned by major conifer confusers.

## The Key Hypothesis To Test

The current failure is probably **not** just “cleaned data got worse.”

More likely it is a combination of:

1. `V4.1` is a very thin radiata slice because it is `new_gbif`-only
2. the strongest radiata support historically lived in backfill
3. the current trainer is not effectively exploiting introduced/planted conditioning
4. the current trainer may be less aligned with the original SINR method than we assumed
5. the AE representation likely contains useful plantation signal, but the supervised objective is not converting that signal into the right ranking

## What The Actual SINR Method Adds

The original SINR method / repo is not just “big multiclass BCE classifier.”

Key relevant ingredients from the linked SINR codebase:

- shared spatial implicit neural representation over location/features
- positive-only occurrence supervision
- assumed-negative losses:
  - `an_full`
  - `an_slds`
  - `an_ssdl`
- random background negative locations
- hard-capping dominant classes (`hard_cap_num_per_class`)
- range-learning objective rather than only plain multiclass BCE behavior

Our current `V4.1` trainer is more customized and uses BCE in the current run.

This gap matters, especially for a benchmark like radiata where the issue is not mere rarity but confuser discrimination + plantation semantics.

## Current Beads Anchor

Active comparison issue:

- `treekipedia-xz2` — `V4.2 radiata comparison and SINR alignment`

Keep these in view too:

- `treekipedia-bj7` — backfill strict extraction in flight
- `treekipedia-9vo` — non-AE semantic audit
- `treekipedia-2t9` — future multi-source temporal intelligence

`V4.1` issue `treekipedia-bfc` is now a completed preview baseline, not the main forward path.

### Pre-backfill phase order

Treat the next steps as explicit phases before any backfill join decision:

- `V4.3` — `treekipedia-xrj`
  - location-prior and representation diagnosis
  - top-100 above-radiata audit
  - no-location / reduced-location ablations
  - AE / hidden-state / kNN manifold probe
- `V4.4` — `treekipedia-37w`
  - true background negatives and spatial-specificity experiments
- `V4.5` — `treekipedia-e0p`
  - retrieval / regional-calibration probes (AE kNN rerank, TDWG / regional priors) if needed
- `V4.6` — `treekipedia-03y`
  - pre-backfill recipe lock and expanded plantation benchmark suite

Do **not** merge backfill into the `V4` program before `V4.6` produces a deliberate go/no-go recommendation.

## Your Job

Do **not** defend the current `V4.1` result.

Your job is to explain it rigorously and propose minimum-change next experiments.

### Task 1 — Top-100 species above radiata analysis

Using the finished `V4.1` model and the canonical benchmark coordinate, identify the top `100` species ranked above radiata and classify them.

For each, determine where possible:

- angiosperm vs gymnosperm
- likely native vs introduced signal class
- plantation-affinity or disturbance-affinity if inferable
- major genus/confuser clusters

Then summarize:

- how many are broadleaf / angiosperm vs conifer/gymnosperm
- how many are likely NZ-native / temperate-native style taxa
- how many are direct Pinus/Pseudotsuga/Cupressus-type confusers

Goal: confirm whether the model is mostly failing at plantation recognition or mostly failing at congener discrimination.

### Task 2 — SINR gap analysis vs current trainer

Compare the actual SINR method (paper/site/repo) against our current `train_on_vm.py` / `run_local_5m_shard_training.py` pipeline.

Specifically answer:

- what pieces of original SINR we are effectively using already
- what pieces we are not using
- which missing pieces are most relevant to the radiata failure

Focus especially on:

- assumed-negative objectives (`an_full` etc.)
- hard class caps
- background negative sampling
- whether our current BCE setup is likely washing out plantation/range structure

### Task 3 — Minimum-change experiment plan

Design a **non-destructive** experiment plan using the current `V4.1` training-grain table and artifacts.

Do not mutate or replace the canonical repaired lineage.

Prefer new artifacts / new model dirs / new contracts if needed.

I want a ranked plan with the smallest high-confidence experiments first.

At minimum, evaluate:

1. `an_full` loss on the current `V4.1` data
2. hard cap per species (e.g. `1000` or another justified cap)
3. whether to re-enable introduced-path behavior in a way that is actually comparable
4. whether current `legacy_gt1` planted label mode is hurting the benchmark

For each experiment, say:

- exact code/file changes needed (if any)
- whether existing flags already support it
- exact command to run
- why it is non-destructive
- what benchmark improvement would count as success

### Task 4 — Decide what not to do yet

Be explicit about what should wait:

- do not merge backfill into `V4` yet unless you can justify it
- do not widen feature families just to chase the benchmark
- do not rewrite the entire architecture if a smaller objective/imbalance fix is more principled

### Task 5 — Recommendation

At the end, answer bluntly:

1. Is `#105` mainly a data-scope problem, a loss/objective problem, or both?
2. Is the strongest next move `an_full`, hard-cap, introduced-path fix, or something else?
3. Should radiata remain the leading stress test for `V4.2`, or should it be paired with additional plantation/introduction cases?

## Constraints

- Prefer analysis and new artifacts over destructive mutation
- Do not overwrite canonical tables
- Do not assume more epochs alone solve this
- Do not silently change the benchmark coordinate/year/target taxon
- Treat AE+kNN outperforming the classifier as a real signal that the objective/training setup may be wrong

## Canonical benchmark references

- coordinate: `(-41.151583464812404, 175.09968969862783)`
- year: `2023`
- target taxon: `GymPiPiPnCx50820-00`

## Useful local files / logs

- `orchestrator/v41_preview_training_r2_20260316_004743.log`
- `orchestrator/train_on_vm.py`
- `orchestrator/run_local_5m_shard_training.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/contracts/sinr_v3/species_mapping_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/species_frequency_contract_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`

## Copy-paste Claude prompt

```text
You are taking over SINR at the start of V4.2 comparison/alignment.

V4.1 preview is no longer the active forward path. Treat it as a completed baseline that still fails the canonical radiata benchmark.

Your job:
1. analyze the top 100 species above radiata at the canonical benchmark,
2. compare our current trainer against the real SINR method from the paper/repo,
3. propose a minimum-change non-destructive experiment plan on the current V4.1 data,
4. tell us what to try next before deciding whether to merge backfill into the V4 program.

Read first:
1. .claude/project-management/GO.md
2. docs/SINR Claude V4.2 Comparison Handoff.md
3. docs/SINR V4.1 Data Confidence Matrix.md
4. docs/SINR Claude V4.1 Preview Handoff.md
5. docs/SINR v3 Master Recovery Plan.md
6. docs/SINR BigQuery Lineage Map.md
7. https://sites.google.com/view/sinr-geo
8. https://github.com/elijahcole/sinr

Anchor facts:
- canonical benchmark coordinate = (-41.151583464812404, 175.09968969862783)
- year = 2023
- target taxon = GymPiPiPnCx50820-00
- corrected finished V4.1 result = rank #105 / 19,043, p=0.6083
- introduced=0.0/0.5/1.0 leaves the rank unchanged
- V4.1 radiata support = 706 rows, 272 NZ rows, 7 rows within 25km
- old V3 radiata support = 9,616 rows, 1,107 NZ rows, 39 rows within 25km
- in old V3 preview-clean, radiata was 8,705 backfill rows and only 911 new_gbif rows

What I want back:
1. top-100 outranking-radiata analysis with taxonomy/confuser summary
2. SINR gap analysis vs current trainer/loss/config
3. minimum-change experiment plan centered on an_full + hard-cap + current V4.1 data
4. exact commands and code changes (if any)
5. a blunt recommendation for the next experiment

Constraints:
- be skeptical
- non-destructive only
- do not overwrite canonical tables
- do not silently merge backfill
- do not hand-wave away AE+kNN outperforming the classifier
```
