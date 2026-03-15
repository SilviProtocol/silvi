# SINR Claude V4.1 Preview Handoff

Date: 2026-03-15
Audience: Claude or any successor agent continuing SINR data / release / preview-model work
Status: active handoff, supersedes the old instinct to keep iterating `v3.x` directly

## Mission

Do not keep nudging `V3` forward as if it were still the main product line.

Treat the program as:

- `V3` = frozen benchmark / comparison family
- `V4.0` = data-governance, lineage repair, semantic cleanup
- `V4.1 preview` = controlled `new_gbif` strict-core experiment while backfill finishes
- `V4.2+` = full strict estate after backfill and family canonicalization

Your job is to keep the work fail-closed and relentlessly scoped to that path.

## CRITICAL: Version Numbering Disambiguation

There are **two independent version numbering systems** in this project. Do not confuse them.

### Program versions (V3, V4.0, V4.1, V4.2+)

These describe the **data governance and release program**:

- `V3` = frozen benchmark family. No further iteration.
- `V4.0` = data-governance, lineage repair, semantic cleanup.
- `V4.1 preview` = strict-core new_gbif-only experiment (current target).
- `V4.2+` = full strict estate after backfill completion.

### V3 experiment versions (v1 through v18)

These are **internal training experiment numbers** from the V3 model development cycle. They all used V3 training data and V3 normalization stats. Key examples:

| Experiment | Dir on disk | What it was | Rank | Status |
|------------|-------------|-------------|------|--------|
| v4 | `model_local_contract_v4_gatefix_5m` | BCE + gate fix, 5M rows | #16 | **V3 frozen benchmark** |
| v14 | `model_local_contract_v14_location_5m` | + location encoding | #2 | **Best V3 model** |
| v5-v13, v15-v18 | various `model_local_contract_v*` | rejected experiments | various | Obsolete |

**These experiment numbers (v1-v18) are NOT V4.x program versions.** They are all V3-family artifacts. The first actual V4.1 model does not exist yet — it will be trained from the V4.1 preview table with V4.1 stats and the V4.1 feature contract.

### Local disk artifacts

All `~/model_local_contract_v*` directories and `~/data_5m_shards` are **V3 experiment artifacts**. Only two are worth keeping as V3 benchmarks:

- `~/model_local_contract_v4_gatefix_5m` — V3 frozen benchmark (rank #16)
- `~/model_local_contract_v14_location_5m` — best V3 model (rank #2)

Everything else is reproducible from BQ tables + scripts in the repo (except trained weights, which are seed-dependent and from rejected experiments).

### Reproducibility from BQ

- Training shards: re-exportable from `sinr_v3_unified_strict_train_v30_medium_5m_s{0..4}` via `export_bigquery_local.py`
- Normalization stats: deterministically recomputable from data via `build_sinr_v3_global_stats.py` or `build_sinr_v41_preview_stats.py`
- Contracts (JSON): committed to `orchestrator/contracts/sinr_v3/` in git
- Xiao backfill cache: fully written to BQ; local cache was only for resumability
- The only non-reproducible artifacts are **trained model weights** (random seed dependent)

## Read First

1. `.claude/project-management/GO.md`
2. `docs/SINR V4.1 Data Confidence Matrix.md`
3. `docs/SINR v3 Master Recovery Plan.md`
4. `docs/SINR BigQuery Lineage Map.md`
5. `docs/SINR Strict-Only Release Builder.md`
6. `docs/SINR Temporal Sampling Contract.md`
7. `docs/SINR Fresh Validation Findings.md`
8. `docs/SINR Claude Audit Adjudication.md`
9. `docs/SINR Claude Continuation Handoff.md` (historical continuity only)

Then inspect these scripts:

- `orchestrator/unified_gee_sampler_v3.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/repair_sinr_strict_xiao.py`
- `orchestrator/repair_sinr_strict_modis_gpp_semantics.py`
- `orchestrator/repair_sinr_strict_new_gbif_duplicates.py`
- `orchestrator/repair_sinr_new_gbif_missing_contexts.py`
- `orchestrator/build_sinr_new_gbif_missing_patch_lineage.py`
- `orchestrator/build_sinr_strict_only_release.py`
- `orchestrator/build_sinr_hybrid_train_release.py`
- `orchestrator/train_on_vm.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/temporal_env_sampler.py`

## Current Proven State

### 1. Canonical repaired `new_gbif` strict lineage exists

Source table to treat as canonical for `new_gbif` strict raw:

- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`

Confirmed properties:

- `8,838,488` rows
- `8,838,488` distinct `(lat4, lon4, observation_year, emb_year)` contexts
- `0` duplicate context groups
- `0` effective unresolved contexts
- `3` explicit singleton unsampleables logged separately:
  - `(90.0, 0.0, 2013, 2017)`
  - `(90.0, 0.0, 2016, 2017)`
  - `(90.0, 117.0, 2017, 2017)`

Supporting lineage / audit tables:

- `species_data.sinr_v3_features_new_gbif_strict_missing_patch_raw_v1`
- `species_data.sinr_v3_features_new_gbif_strict_missing_patch_clean_v1`
- `species_data.sinr_new_gbif_strict_missing_singleton_failures_v1`
- `species_data.sinr_new_gbif_strict_missing_patch_lineage_summary_v1`
- `species_data.sinr_new_gbif_strict_duplicate_audit_v1`
- `species_data.sinr_new_gbif_strict_duplicate_audit_summary_v1`

### 2. Backfill strict extraction is still in flight

Target table:

- `species_data.sinr_v3_features_backfill_strict_full`

Current operational rule:

- let backfill continue,
- do not block `V4.1 preview` on backfill completion,
- reserve full strict-estate rebuild for `V4.2+`.

### 3. Release builders now point at the repaired `new_gbif` lineage

Files:

- `orchestrator/build_sinr_strict_only_release.py`
- `orchestrator/build_sinr_hybrid_train_release.py`

But this alone does not mean all feature families are now trustworthy.

### 4. `V4.1` preview-core table already exists

Built artifact:

- `species_data.sinr_v41_preview_strict_core_v1`

Current facts:

- `8,392,893` rows
- `643` columns
- `445,595` rows excluded relative to `completed_v1`
- `GEDI` excluded
- explicit GPP high codes nulled out of preview
- `nighttime_lights` pre-2012 nulled
- obvious `BIO` / soil contamination rows filtered

### 5. Temporal scope is intentionally narrow in `V4.1`

For `V4.1 preview`, the actual temporal branch is AE-only:

- `2017-2024` AlphaEarth sequence (`512D`)

Non-AE time-related families currently enter only as year-matched or summary scalar features.

This is deliberate.

Reason:

- AE temporal sequence is the cleanest currently trusted temporal signal,
- non-AE temporal families still need stronger sampled-year provenance and family-specific validation,
- `V4.1` should stay simple and fail closed rather than pretending we already have a fully temporalized multi-source model.

Future tracked expansion:

- `treekipedia-2t9` — design `V4.2+` multi-source temporal intelligence stack (disturbance, agriculture/crop cycles, land-use history, fire regime, soil-degradation-relevant signals).

### 6. Current semantic confidence is mixed

High confidence:

- row accounting / lineage integrity
- Xiao repair lineage
- duplicate removal
- pre-2001 GPP NULL semantics

Still under verification:

- explicit MODIS GPP high-code contamination handling (`65530-65535` confirmed bad)
- exact GEDI canopy/FHD semantics
- masked-zero contamination from `.unmask(0)`
- canonical handling of external/manual families

## What To Treat As Safe vs Unsafe Right Now

Use `docs/SINR V4.1 Data Confidence Matrix.md` as the family-by-family inclusion boundary.

### Safe enough for `V4.1 preview strict-core`

Keep / prioritize:

- AE embeddings
- terrain / hydro
- Hansen / JRC water / JRC forest families already in strict raw
- biomass
- human modification
- Xiao
- most TerraClimate families
- most BIO / soil families with contamination filters
- Dynamic World only with corrected ESA proxy remap logic
- MODIS GPP only after explicit high-code masking / guardrails

### Exclude or quarantine for now

- `gedi_canopy_height_m` until GEDI semantics are conclusively verified
- `gedi_foliage_height_div` until the correct band semantics are confirmed
- external/manual / preview-backed families unless rebuilt or explicitly provenance-tagged:
  - carbon extras
  - HILDA
  - aridity / ET0 / IPCC
  - land-state
  - introduced/native joins (unless refreshed and provenance-tagged)

## Current Best Understanding Of The Disputed Issues

### MODIS GPP

Confirmed:

- pre-2001 no-coverage handling is repaired in lineage
- explicit `65530-65535` values are bad and must not be treated as real GPP

Important nuance:

- do **not** blindly wipe the entire `30000-49999` range;
- those rows are continuous with tree-covered tropical contexts and may contain valid high-productivity observations.

### GEDI

Confirmed:

- collection-level `.mosaic()` was too loose and needed replacement with specific image assets

Not yet fully settled:

- whether `gedi_canopy_height_m` and `gedi_foliage_height_div` are now using the exact right band semantics in every path
- whether any training-time guard should be a temporary clip or a deeper lineage repair

### Dynamic World / ESA proxy

Confirmed:

- older remap logic had errors
- sampler and inference should use the same corrected remap

Still needed:

- explicit proxy provenance flag for pre-2015 rows (`dw_is_esa_proxy` or equivalent)

## Active Beads Pipeline

Use `bd show` on these before doing new design work:

- `treekipedia-bj7` — backfill strict extraction with corrected Xiao (in progress)
- `treekipedia-cl3` — repoint release builders to completed `new_gbif` lineage + rebuild releases
- `treekipedia-9vo` — audit and repair non-AE strict raw semantics
- `treekipedia-8b2` — canonicalize or explicitly exclude external/manual families
- `treekipedia-bfc` — build the `V4.1` strict-core preview dataset and preview-model run
- `treekipedia-2t9` — design the future multi-source temporal intelligence stack
- `treekipedia-csc` — build the full strict unified training table after backfill completion

`treekipedia-bfc` scope:

- source from `...completed_v1`
- use preview only for labels/meta/splits where necessary
- exclude unresolved GEDI and external/manual families
- apply explicit GPP high-code guard
- apply BIO / soil contamination filters
- recompute normalization stats
- train a clearly labeled `V4.1 preview` model

## Non-Negotiable Operating Rules

1. Do **not** drift back into generic `v3.x` model tinkering while the data contract is still changing.
2. Do **not** treat current releases as final truth just because the builders are repointed.
3. Do **not** promote unresolved families into `V4.1 preview` just to imitate old `V3` feature breadth.
4. Do **not** mutate old tables when a new lineage table is good enough.
5. Do **not** equate “row exists” with “value is semantically trustworthy.”

## Recommended Next Steps For Claude

### Priority 0

1. Verify the current release-builder output against `completed_v1` and rebuild versioned strict / hybrid releases if not already done.
2. Finish the non-AE semantic audit with emphasis on:
    - MODIS GPP explicit high-code masking,
    - GEDI canopy/FHD band semantics,
    - `.unmask(0)` contamination families,
    - Dynamic World proxy provenance.

### Priority 1

3. Freeze an explicit feature contract for `species_data.sinr_v41_preview_strict_core_v1`.
4. Recompute normalization stats from the preview-core table.
5. Train the `V4.1 preview` model and compare it against the frozen `V3` benchmark family.
6. Update the confidence matrix if any family changes trust class during the work.

### Priority 2

7. Let backfill finish.
8. Build the full strict unified training table (`V4.2+`) after `sinr_v3_features_backfill_strict_full` is complete.
9. Canonicalize or explicitly version-gate the external/manual families before claiming a full strict estate.
10. Design the richer multi-source temporal stack only after `V4.1` is frozen enough to benchmark cleanly.

## Claude Execution Prompt

```text
You are continuing the SINR program in its current phase.

Do not optimize V3 incrementally as if that were still the main path.
Treat:
- V3 = frozen benchmark
- V4.0 = lineage / semantic cleanup
- V4.1 preview = strict-core new_gbif-only experiment
- V4.2+ = full strict estate after backfill

Read first:
1. .claude/project-management/GO.md
2. docs/SINR Claude V4.1 Preview Handoff.md
3. docs/SINR V4.1 Data Confidence Matrix.md
4. docs/SINR v3 Master Recovery Plan.md
5. docs/SINR BigQuery Lineage Map.md
6. docs/SINR Strict-Only Release Builder.md
7. docs/SINR Temporal Sampling Contract.md

Then inspect:
- orchestrator/unified_gee_sampler_v3.py
- orchestrator/unified_gee_sampler_v3_strict.py
- orchestrator/repair_sinr_strict_xiao.py
- orchestrator/repair_sinr_strict_modis_gpp_semantics.py
- orchestrator/repair_sinr_strict_new_gbif_duplicates.py
- orchestrator/repair_sinr_new_gbif_missing_contexts.py
- orchestrator/build_sinr_new_gbif_missing_patch_lineage.py
- orchestrator/build_sinr_strict_only_release.py
- orchestrator/build_sinr_hybrid_train_release.py
- orchestrator/train_on_vm.py
- orchestrator/location_predictor_FIXED.py
- orchestrator/temporal_env_sampler.py

Use these live tables as anchors:
- species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1
- species_data.sinr_v3_features_backfill_strict_full

Current mission:
1. verify / finish release-builder rebuilds from completed_v1
2. settle non-AE semantic trust boundaries (GPP, GEDI, masked-zero families, DW proxy)
3. treat docs/SINR V4.1 Data Confidence Matrix.md as the preview inclusion boundary
4. freeze the V4.1 preview contract/stats and run the preview model while backfill continues

Constraints:
- fail closed
- prefer lineage over mutation
- do not pretend unresolved families are canonical
- keep using beads for task tracking
- keep V3 only as benchmark context

Deliverables:
- a blunt trust matrix for preview-core families
- a V4.1 preview table / contract
- rebuilt strict release artifacts if needed
- exact list of remaining blockers before V4.2 full
```
