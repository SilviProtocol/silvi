# SINR Claude Continuation Handoff

Superseded note (2026-03-19): this is now continuity/reference material only.
For active SINR work, start with `docs/SINR Current Program State.md`.

Date: 2026-03-13
Audience: Claude or any successor agent continuing SINR data/model recovery work
Status: superseded historical continuity handoff

Note: for the current program focus, read `docs/SINR Claude V4.1 Preview Handoff.md` first. This file is now primarily historical continuity / provenance.

## Mission

Pick up the SINR recovery program exactly where it stands now.

You are not starting from scratch.

Your job is to continue:

- data-estate cleanup and governance,
- strict vs legacy salvage validation,
- field-family integrity work,
- temporal-contract cleanup,
- release-builder hardening,
- and then resume model-facing work only on top of trustworthy releases.

Fail closed. Prefer false negatives over false approvals.

---

## Start Here

Read these in this order:

1. `.claude/project-management/GO.md`
2. `docs/SINR Claude Audit Adjudication.md`
3. `docs/SINR Data Estate Audit Handoff.md`
4. `docs/SINR Fresh Validation Findings.md`
5. `docs/SINR Temporal Sampling Contract.md`
6. `docs/SINR BigQuery Lineage Map.md`
7. `docs/SINR Forensic Program History + Master Dataset Plan.md`
8. `docs/SINR Master Dataset v1 README.md`
9. `docs/SINR Legacy Backfill Salvage Plan.md`
10. `docs/SINR Field-Family Integrity Audit Plan.md`
11. `docs/SINR Strict-Only Release Builder.md`
12. `docs/SINR Hybrid Override System.md`
13. `docs/SINR Hybrid Train-Only Release Builder.md`
14. `docs/SINR Fresh Validation Sampling Plan.md`
15. `docs/SINR Deletion Readiness Matrix.md`

Then inspect these scripts:

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
- `orchestrator/unified_gee_sampler_v3.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`

---

## Beads Issues To Continue

Use `bd show <id>` on these first:

- `treekipedia-xi6` — forensic audit SINR data lineage and master dataset
- `treekipedia-cz6` — design SINR master dataset v1
- `treekipedia-csc` — rebuild strict-full unified training table from strict feature outputs
- `treekipedia-qhs` — version species knowledge schema and releases
- `treekipedia-9bw` — legacy table retirement and archive policy
- `treekipedia-08v` — audit legacy context salvageability
- `treekipedia-9fq` — field-family integrity and temporal semantics
- `treekipedia-wzb` — enforce SINR release gates in release builders
- `treekipedia-bb9` — hybrid release builder
- `treekipedia-n5j` — fresh validation extraction against salvage assumptions
- `treekipedia-8e5` — year-2000 GPP failure
- `treekipedia-zk7` — temporal sampling contract

Likely next issue creation candidates:

- full-scope Xiao inconsistency quantification / remediation
- family-specific temporal provenance columns
- strict raw Xiao repair/backfill plan
- fresh-validation rerun for year-2000 slice after patch
- auxiliary/manual-family validation layer (carbon/HILDA/aridity/IPCC)

---

## Current BigQuery Situation

Dataset:

- `treekipedia-479918.species_data`

Approx current total storage:

- ~`1.45 TB`

Confirmed deleted already:

- `species_data.sinr_v3_unified_v2_final`

Do not delete more tables yet without explicit review.

Use:

- `docs/SINR Deletion Readiness Matrix.md`

---

## Current Core Audit / Governance Tables

These were created non-destructively and are now part of the active governance layer:

### Occurrence / salvage layer

- `species_data.sinr_occurrence_unified_source_v1`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_salvage_candidates_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1`
- `species_data.sinr_occurrence_salvage_summary_v1`

### Field-integrity / release-gate layer

- `species_data.sinr_occurrence_field_integrity_status_v1`
- `species_data.sinr_occurrence_integrity_reconciliation_v1`
- `species_data.sinr_occurrence_release_eligibility_v1`

### Hybrid governance layer

- `species_data.sinr_hybrid_override_registry_v1`
- `species_data.sinr_hybrid_override_candidate_queue_v1`
- `species_data.sinr_hybrid_override_duplicate_audit_v1`
- `species_data.sinr_hybrid_override_orphan_audit_v1`

### Current release artifacts

- `species_data.sinr_release_registry_v1`
- `species_data.sinr_release_allowlist__strict_only_20260312_194000`
- `species_data.sinr_train_release__strict_only_20260312_194000`
- `species_data.sinr_release_allowlist__hybrid_train_only_20260312_221500`
- `species_data.sinr_train_release__hybrid_train_only_20260312_221500`

### Hybrid review / validation batches

- `species_data.sinr_hybrid_override_review_batch__hybrid_review_100_20260312_223500`
- `species_data.sinr_fresh_validation_batch__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_extract__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_compare__fresh_validation_1000_20260313_001500`
- `species_data.sinr_fresh_validation_failures__fresh_validation_1000_20260313_001500`
- `species_data.sinr_xiao_inconsistency_audit__fresh_validation_1000_20260313_001500`

---

## Current Proven Facts

### 1. Release gating is now partially enforced

This was a major gap and is no longer purely advisory.

Implemented:

- strict-only release builder
- hybrid override system
- hybrid train-only release builder

Current gates:

- `allow_strict_release`
- `allow_hybrid_release`
- `block_pending_audit_override`
- `block`

### 2. One pilot hybrid row was approved end-to-end

Pilot override:

- release id: `pilot_hybrid_override_20260312_220500`

Pilot row:

- `occurrence_example_id = 0000014f1fc240a5790c1634179dfbc996f46a600dfd295f71bda7341dcc05b7`

This proved:

- registry -> eligibility -> release path works

### 3. Current hybrid release is mostly strict-only plus one approved hybrid row

Current hybrid train-only release:

- `species_data.sinr_train_release__hybrid_train_only_20260312_221500`

It contains:

- `8,172,288` `allow_strict_release` rows
- `1` `allow_hybrid_release` row

### 4. Fresh validation run completed partially and surfaced real issues

Validation batch:

- `1,000` sampled rows

Fresh extracted rows landed:

- `860`

Missing / failed:

- `140`

This is not just queue noise.

It surfaced real bugs.

### 5. The scary `93/100` strict-control result was narrowed down

This does **not** indicate broad strict corruption.

All `7` strict-control mismatches differed in exactly one field:

- `xiao_planted_forest`

Pattern for all 7:

- preview-clean = `2.0`
- fresh validation extract = `2.0`
- current strict raw = `0.0`

Meaning:

- preview + fresh agree
- current strict raw disagrees

Interpretation:

- likely localized Xiao inconsistency in current strict raw

### 6. The year-2000 temporal extraction failure was confirmed

Failure:

- `Image.select: Band pattern 'Gpp' was applied to an Image with no bands`

Root cause:

- `MODIS/061/MOD17A3HGF` starts in `2001`, not `2000`
- code previously treated it as `2000+`

Patch already applied:

- `orchestrator/unified_gee_sampler_v3.py`
- MODIS GPP now treated as `2001+`
- pre-2001 currently returns `0` to avoid future leakage

### 7. Temporal semantics are still overloaded

Key insight:

- `emb_year` should not be a universal temporal anchor
- it should be only the AE anchor year used
- non-AE families need their own sampled-year / fallback provenance

Documented in:

- `docs/SINR Temporal Sampling Contract.md`

---

## What Is Still Weak / Incomplete

### A. Xiao in current strict raw is not yet fully quantified

We have sample evidence, not full-estate quantification.

Likely next step:

- quantify full-scope Xiao inconsistency in `sinr_v3_features_new_gbif_strict_full`
- decide whether to repair / backfill / mark non-canonical

### B. Fresh validation currently tests core strict GEE payload, not all manual/auxiliary families

It does **not** fully validate:

- carbon extras
- HILDA
- aridity / ET0 / IPCC
- introduced/native joins
- land-state joins

You need a second validation layer for those.

### C. Validation runner still shares unsampleable table helper

No contamination was observed yet, but it should eventually get its own validation-specific unsampleable table/log.

### D. Naming optimism is still not fully cleaned up

Especially:

- `legacy_unverified`
- `strict_context_present`

These were called out by Claude and should still be revisited.

### E. Strict pipeline maturity is still partly manual / ad hoc

Docs have improved, but full strict intermediate build automation is still not complete in-repo.

---

## Exact Files Modified / Added In This Phase

### Core docs

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

### New scripts / builders

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

### SQL blueprints

- `orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql`
- `orchestrator/sql/sinr_master_dataset_v1/occurrence_grain_salvage_blueprint.sql`
- `orchestrator/sql/sinr_master_dataset_v1/field_family_integrity_blueprint.sql`

### Existing code patched

- `orchestrator/unified_gee_sampler_v3.py`
  - year-2000 MODIS GPP fix (`2001+`)

---

## Recommended Next Steps For Claude

### Priority 0 — audit/repair Xiao in current strict raw

Do this next.

Goal:

- quantify full-scope Xiao inconsistency beyond the 1,000-row sample
- determine whether mismatch clusters by year / batch / geography / run window
- decide whether to:
  - repair values in a new derived table,
  - backfill / rebuild affected rows,
  - or mark current strict raw Xiao as non-canonical

Likely outputs:

- `sinr_xiao_preview_vs_strict_full_audit_v1`
- `sinr_xiao_context_drift_audit_v1`
- `sinr_xiao_year_profile_v1`
- issue + doc update

### Priority 1 — rerun year-2000 validation slice after patch

Use the patched strict sampler to test whether the GPP issue is resolved.

Do not assume it is fixed until revalidated.

### Priority 1 — build auxiliary/manual-family validation layer

Fresh validation so far is mainly core strict GEE payload.

Need separate validation for:

- carbon family
- HILDA
- aridity / ET0 / IPCC
- land-state
- introduced/native joins

### Priority 1 — rename misleading bucket labels

Still important:

- `legacy_unverified` -> safer blocked language
- `strict_context_present` -> clearer exact-context language

### Priority 2 — temporal provenance implementation

Implement first-class fields / flags for:

- `ae_anchor_is_fallback`
- `ae_anchor_strategy`
- `obs_minus_emb_year`
- per-family sampled-year provenance for non-AE temporal families

### Priority 2 — strict pipeline maturity honesty — DONE

See `docs/SINR Pipeline Maturity Matrix.md` for full assessment.

---

## Important Warnings

1. Do **not** delete more tables yet.
   - Use `docs/SINR Deletion Readiness Matrix.md`

2. Do **not** treat current strict raw as fully canonical yet.
   - Xiao inconsistency is unresolved.

3. Do **not** assume fresh validation compares all feature families.
   - it currently covers core strict GEE payload best

4. Do **not** silently approve hybrid rows in bulk.
   - use explicit override registry only

5. Do **not** conflate prediction and recommendation temporal semantics.
   - read `docs/SINR Temporal Sampling Contract.md`

---

## Claude Build Prompt

Use this prompt if you want Claude to continue directly:

```text
You are taking over the SINR recovery/build program mid-flight.

Read first:
1. .claude/project-management/GO.md
2. docs/SINR Claude Continuation Handoff.md
3. docs/SINR Claude Audit Adjudication.md
4. docs/SINR Fresh Validation Findings.md
5. docs/SINR Temporal Sampling Contract.md

Then inspect these scripts:
- orchestrator/build_sinr_occurrence_salvage_tables.py
- orchestrator/build_sinr_field_integrity_status.py
- orchestrator/build_sinr_strict_only_release.py
- orchestrator/build_sinr_hybrid_override_system.py
- orchestrator/register_sinr_hybrid_override.py
- orchestrator/build_sinr_hybrid_train_release.py
- orchestrator/build_sinr_fresh_validation_batch.py
- orchestrator/run_sinr_fresh_validation_extraction.py
- orchestrator/build_sinr_fresh_validation_compare.py
- orchestrator/unified_gee_sampler_v3.py

Current state you must treat as factual:
- release gating is partially enforced
- strict-only release exists
- hybrid override system exists and one pilot hybrid row flows end-to-end
- 1,000-row fresh validation run completed partially: 860 rows landed
- strict-control mismatch is localized to xiao_planted_forest, not broad strict corruption
- year-2000 MODIS GPP bug was identified and patched in unified_gee_sampler_v3.py
- emb_year should be treated narrowly as AE anchor year, not universal temporal anchor

Primary next tasks:
1. quantify full-scope Xiao inconsistency in current strict raw tables
2. rerun year-2000 validation slice after patch and confirm resolution
3. build validation layer for auxiliary/manual feature families (carbon, HILDA, aridity/ET0/IPCC, land-state, introduced)
4. continue temporal provenance design and implementation
5. rename misleading salvage buckets and keep governance fail-closed

Constraints:
- do not delete more tables yet
- do not bulk approve hybrid rows
- prefer new derived/audit tables over mutating legacy assets
- keep using beads for tracking
- update GO.md only as source-of-truth pointer, not as a dumping ground

Deliverables expected from you:
- exact Xiao inconsistency quantification tables
- rerun proof for year-2000 bug fix
- next generation temporal provenance design or patches
- updated docs/beads tracking
- blunt assessment of what is still unsafe to train on
```

---

## Final Note

The biggest conceptual shift in this whole phase was:

- stop pretending all rows are equally valid,
- stop pretending all feature families share the same temporal semantics,
- and stop treating docs as governance if no release path enforces them.

Continue in that spirit.
