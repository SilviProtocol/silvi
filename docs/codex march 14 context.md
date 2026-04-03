# Codex March 14 Context

Date: 2026-03-14
Purpose: full continuity handoff for a new model/session to continue SINR recovery work without losing state.

## High-level situation

This repo is in the middle of a major SINR v3 forensic recovery / data-governance cleanup.

The work has shifted from:

- just debugging model behavior

to:

- establishing which data is trustworthy,
- creating enforceable release gates,
- separating strict vs legacy vs hybrid data,
- auditing temporal semantics,
- and only then resuming model work on top of controlled releases.

The biggest conceptual lesson so far:

- stop pretending all rows are equally valid,
- stop pretending all feature families share the same temporal semantics,
- stop treating docs as governance when no release builder enforces them.

## Read these first in a new session

1. `.claude/project-management/GO.md`
2. `docs/SINR Claude Continuation Handoff.md`
3. `docs/SINR Claude Audit Adjudication.md`
4. `docs/SINR Data Estate Audit Handoff.md`
5. `docs/SINR Fresh Validation Findings.md`
6. `docs/SINR Temporal Sampling Contract.md`
7. `docs/SINR BigQuery Lineage Map.md`
8. `docs/SINR Forensic Program History + Master Dataset Plan.md`
9. `docs/SINR Master Dataset v1 README.md`
10. `docs/SINR Legacy Backfill Salvage Plan.md`
11. `docs/SINR Field-Family Integrity Audit Plan.md`
12. `docs/SINR Strict-Only Release Builder.md`
13. `docs/SINR Hybrid Override System.md`
14. `docs/SINR Hybrid Train-Only Release Builder.md`
15. `docs/SINR Hybrid Review Batch.md`
16. `docs/SINR Fresh Validation Sampling Plan.md`
17. `docs/SINR Deletion Readiness Matrix.md`

## Key beads issues

Run `bd show` on these:

- `treekipedia-xi6` — forensic audit SINR data lineage and master dataset
- `treekipedia-cz6` — design SINR master dataset v1
- `treekipedia-csc` — rebuild strict-full unified training table from strict feature outputs
- `treekipedia-qhs` — version species knowledge schema and releases
- `treekipedia-9bw` — retirement policy / deletion readiness
- `treekipedia-08v` — legacy context salvageability
- `treekipedia-9fq` — field-family integrity and temporal semantics
- `treekipedia-wzb` — enforce release gates in release builders
- `treekipedia-bb9` — hybrid release builder
- `treekipedia-n5j` — fresh validation extraction against salvage assumptions
- `treekipedia-8e5` — year-2000 GPP failure
- `treekipedia-zk7` — temporal sampling contract

## BigQuery reality

Dataset:

- `treekipedia-479918.species_data`

Approx current storage:

- ~`1.45 TB`

Deleted already:

- `species_data.sinr_v3_unified_v2_final`

Do not delete more tables yet.

Use:

- `docs/SINR Deletion Readiness Matrix.md`

## Important tables now in play

### Occurrence/salvage governance

- `species_data.sinr_occurrence_unified_source_v1`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_salvage_candidates_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1`
- `species_data.sinr_occurrence_salvage_summary_v1`

### Field integrity / release eligibility

- `species_data.sinr_occurrence_field_integrity_status_v1`
- `species_data.sinr_occurrence_integrity_reconciliation_v1`
- `species_data.sinr_occurrence_release_eligibility_v1`

### Hybrid governance

- `species_data.sinr_hybrid_override_registry_v1`
- `species_data.sinr_hybrid_override_candidate_queue_v1`
- `species_data.sinr_hybrid_override_duplicate_audit_v1`
- `species_data.sinr_hybrid_override_orphan_audit_v1`

### Release artifacts

- `species_data.sinr_release_registry_v1`
- `species_data.sinr_release_allowlist__strict_only_20260312_194000`
- `species_data.sinr_train_release__strict_only_20260312_194000`
- `species_data.sinr_release_allowlist__hybrid_train_only_20260312_221500`
- `species_data.sinr_train_release__hybrid_train_only_20260312_221500`

### Review / validation

- `species_data.sinr_hybrid_override_review_batch__hybrid_review_100_20260312_223500`
- `species_data.sinr_fresh_validation_batch__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_extract__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_compare__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_failures__fresh_validation_1000_20260313_001500`
- `species_data.sinr_xiao_inconsistency_audit__fresh_validation_1000_20260313_001500`

## What has been built

### New docs

- `docs/SINR BigQuery Lineage Map.md`
- `docs/SINR Forensic Program History + Master Dataset Plan.md`
- `docs/SINR Master Dataset v1 README.md`
- `docs/SINR Legacy Backfill Salvage Plan.md`
- `docs/SINR Occurrence-Grain Master Training Schema.md`
- `docs/SINR Field-Family Integrity Audit Plan.md`
- `docs/SINR Data Estate Audit Handoff.md`
- `docs/SINR Claude Audit Adjudication.md`
- `docs/SINR Strict-Only Release Builder.md`
- `docs/SINR Hybrid Override System.md`
- `docs/SINR Hybrid Train-Only Release Builder.md`
- `docs/SINR Hybrid Review Batch.md`
- `docs/SINR Fresh Validation Sampling Plan.md`
- `docs/SINR Fresh Validation Findings.md`
- `docs/SINR Deletion Readiness Matrix.md`
- `docs/SINR Temporal Sampling Contract.md`
- `docs/SINR Claude Continuation Handoff.md`

### New scripts/builders

- `orchestrator/build_sinr_occurrence_salvage_tables.py`
- `orchestrator/build_sinr_field_integrity_status.py`
- `orchestrator/build_sinr_strict_only_release.py`
- `orchestrator/build_sinr_hybrid_override_system.py`
- `orchestrator/register_sinr_hybrid_override.py`
- `orchestrator/build_sinr_hybrid_train_release.py`
- `orchestrator/build_sinr_hybrid_review_batch.py`
- `orchestrator/build_sinr_fresh_validation_batch.py`
- `orchestrator/run_sinr_fresh_validation_extraction.py`
- `orchestrator/check_sinr_fresh_validation_status.py`
- `orchestrator/build_sinr_fresh_validation_compare.py`

### Existing code patched

- `orchestrator/unified_gee_sampler_v3.py`
  - MODIS annual GPP fixed from `2000+` to `2001+`

## Most important proven findings

### 1. Release gating is partially enforced now

Before this work, release gates were advisory only.

Now there is a real enforced strict-only release builder and a hybrid override system.

### 2. Strict-only release exists

- `species_data.sinr_train_release__strict_only_20260312_194000`

This includes only rows with:

- `release_gate_default = 'allow_strict_release'`

### 3. Hybrid governance is fail-closed

Hybrid rows are blocked unless explicitly approved in:

- `species_data.sinr_hybrid_override_registry_v1`

One pilot row was approved end-to-end to prove plumbing works.

### 4. One pilot hybrid row successfully flowed into a release

Pilot override release id:

- `pilot_hybrid_override_20260312_220500`

Pilot occurrence:

- `0000014f1fc240a5790c1634179dfbc996f46a600dfd295f71bda7341dcc05b7`

### 5. Fresh validation run surfaced two real issues

Validation sample:

- `1,000` rows

Fresh extracted:

- `860`

Failed/missing:

- `140`

Real issues surfaced:

- localized Xiao inconsistency
- year-2000 MODIS GPP failure

### 6. The scary strict-control result was narrowed down

Strict controls:

- `100` sampled
- `100` got fresh extract
- `93` matched current strict overlap hash
- `7` mismatched

All 7 mismatches differ in exactly one column:

- `xiao_planted_forest`

Pattern for all 7:

- preview-clean = `2.0`
- fresh validation extract = `2.0`
- current strict raw = `0.0`

Interpretation:

- not broad strict corruption
- likely localized Xiao inconsistency in current strict raw

### 7. Year-2000 GPP failure was real and patched

Failure:

- `Image.select: Band pattern 'Gpp' was applied to an Image with no bands`

Cause:

- `MODIS/061/MOD17A3HGF` starts in `2001`
- code incorrectly treated it as `2000+`

Patch:

- `orchestrator/unified_gee_sampler_v3.py`

### 8. Temporal semantics need redesign

Do not treat `emb_year` as universal temporal anchor.

Correct interpretation:

- `emb_year` = AE anchor year actually used

Non-AE temporal families should have their own sampled-year / fallback provenance.

See:

- `docs/SINR Temporal Sampling Contract.md`

## Still unresolved / likely next tasks

### A. Quantify full-scope Xiao inconsistency

The 1,000-row sample found:

- `11` rows where preview + fresh agree and current strict raw differs on Xiao

Need to quantify full-estate prevalence in:

- `sinr_v3_features_new_gbif_strict_full`

Likely next outputs:

- `sinr_xiao_preview_vs_strict_full_audit_v1`
- `sinr_xiao_context_drift_audit_v1`
- `sinr_xiao_year_profile_v1`

### B. Rerun year-2000 slice after patch

Need explicit proof the GPP fix works.

### C. Validate auxiliary/manual feature families separately

Fresh validation so far mostly tests core strict GEE payload.

Need dedicated validation for:

- carbon extras
- HILDA
- aridity / ET0 / IPCC
- land-state
- introduced/native joins

### D. Rename optimistic bucket names

Still probably worth changing:

- `legacy_safe_candidate`
- `strict_full`

### E. Temporal provenance implementation

Need real fields/flags like:

- `ae_anchor_is_fallback`
- `ae_anchor_strategy`
- `obs_minus_emb_year`
- `dataset_sample_year_<family>`
- `dataset_year_is_fallback_<family>`

## Files that matter most in code right now

- `orchestrator/build_sinr_occurrence_salvage_tables.py`
- `orchestrator/build_sinr_field_integrity_status.py`
- `orchestrator/build_sinr_strict_only_release.py`
- `orchestrator/build_sinr_hybrid_override_system.py`
- `orchestrator/register_sinr_hybrid_override.py`
- `orchestrator/build_sinr_hybrid_train_release.py`
- `orchestrator/build_sinr_fresh_validation_batch.py`
- `orchestrator/run_sinr_fresh_validation_extraction.py`
- `orchestrator/build_sinr_fresh_validation_compare.py`
- `orchestrator/unified_gee_sampler_v3.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`

## Suggested immediate next steps for the next model

1. Read `GO.md` and `docs/SINR Claude Continuation Handoff.md`
2. Inspect `docs/SINR Fresh Validation Findings.md`
3. Quantify full-scope Xiao inconsistency in strict raw
4. Re-run the year-2000 validation slice after the GPP patch
5. Build auxiliary/manual-family validation
6. Continue temporal provenance design and implementation
7. Only then resume deeper model fixes based on more trustworthy releases

## Important warnings

- Do not delete more tables yet
- Do not bulk approve hybrid rows
- Do not assume current strict raw is fully canonical yet
- Do not conflate prediction and recommendation temporal semantics
- Do not assume fresh validation covers every feature family yet

## One-line summary

The project now has real governance scaffolding and enforced release paths, but the next model/session still needs to resolve Xiao inconsistency, validate patched year-2000 behavior, and implement family-specific temporal provenance before trusting the data estate fully.
