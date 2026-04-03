# SINR Data Estate Audit Handoff

Date: 2026-03-12
Purpose: handoff packet for an external or parallel auditor to review the full SINR data estate, salvage system, field-integrity scaffold, and master dataset governance.

## Audit goal

Do not audit only model quality.

Audit whether the current SINR data estate has a trustworthy path from:

- source occurrence rows
- to raw feature extraction
- to occurrence-grain salvage classification
- to field-family integrity gating
- to future canonical master / release tables.

This audit should be skeptical and fail-closed.

## Required source-of-truth order

1. Live BigQuery tables and row/key behavior
2. Executable scripts / SQL blueprints
3. Governance and lineage docs

If prose disagrees with tables/scripts, trust tables/scripts.

## BigQuery tables to review

- `species_data.gbif_new_occurrences`
- `species_data.existing_training_coords`
- `species_data.occurrences`
- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_features_backfill_strict_full`
- `species_data.sinr_v3_strict_unsampleable_contexts`
- `species_data.sinr_v3_unified_strict_train`
- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`
- `species_data.sinr_v3_strict_unified_quarantine`
- `species_data.sinr_v3_features_new_gbif`
- `species_data.sinr_v3_features_backfill`
- `species_data.sinr_v3_unified_v1`
- `species_data.sinr_v3_unified_v2`
- `species_data.sinr_occurrence_unified_source_v1`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_salvage_candidates_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1`
- `species_data.sinr_occurrence_salvage_summary_v1`
- `species_data.sinr_occurrence_field_integrity_status_v1`
- `species_data.sinr_occurrence_integrity_reconciliation_v1`

Retired lineage evidence only:

- `species_data.sinr_v3_unified_v2_final` (deleted; use docs/history only)

## Scripts / SQL to review

- `orchestrator/unified_gee_sampler_v3.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/consolidate_bq_v2.py`
- `orchestrator/compute_is_introduced_bq.py`
- `orchestrator/build_sinr_occurrence_salvage_tables.py`
- `orchestrator/build_sinr_field_integrity_status.py`
- `orchestrator/check_v30_preview_readiness.py`
- `orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql`
- `orchestrator/sql/sinr_master_dataset_v1/occurrence_grain_salvage_blueprint.sql`
- `orchestrator/sql/sinr_master_dataset_v1/field_family_integrity_blueprint.sql`

## Docs to review

- `docs/SINR BigQuery Lineage Map.md`
- `docs/SINR Forensic Program History + Master Dataset Plan.md`
- `docs/SINR Legacy Backfill Salvage Plan.md`
- `docs/SINR Field-Family Integrity Audit Plan.md`
- `docs/SINR Master Dataset v1 README.md`
- `docs/SINR Occurrence-Grain Master Training Schema.md`
- `.claude/project-management/GO.md`

## Current key findings to challenge

- `sinr_v3_unified_v2_final` was unsafe and is now deleted.
- `sinr_v3_unified_strict_train_v30_preview_clean` is the safest current training table, but still inherits legacy payloads.
- `sinr_v3_features_new_gbif_strict_full` is the cleanest active strict raw feature table for the `new_gbif` branch.
- Current salvage system is occurrence-grain and non-destructive.
- Current field-integrity table is intentionally conservative and fail-closed for hybrid rows.

## Current table snapshots to validate

Occurrence-grain salvage:

- `strict_context_present`: `8,579,371`
- `legacy_unverified`: `13,428,663`
- `needs_reextract`: `2,004,216` (current field-integrity blocked no-context view)

Field-integrity basis:

- `strict_raw_match`: `8,579,371`
- `preview_inherited_legacy_payload`: `13,863,012`
- `legacy_context_only`: `36,424`
- `no_context_available`: `2,004,216`

Release gates:

- `allow_strict_release`: only `strict_context_present`
- `block_pending_audit_override`: legacy-unverified preview-inherited rows
- all other buckets: blocked

These numbers are moving where strict extraction is still in progress.

## Critical skepticism points

1. Is `legacy_unverified` still too optimistic as a name or logic bucket?
2. Does `strict_context_present` really mean release-grade, or only raw context identity-grade?
3. Are hybrid rows truly fail-closed in every downstream interpretation?
4. Is the field-integrity scaffold still too coarse to trust for release gating?
5. Are there any hidden paths where preview-inherited rows could be mistaken for clean strict data?

## Required audit questions

1. Which tables are:
   - safe raw sources,
   - safe current training sources,
   - salvage-only audit assets,
   - unsafe legacy artifacts?
2. Is the occurrence-grain salvage system materially useful and correctly scoped?
3. Is the field-integrity scaffold still placeholder-only, or already decision-grade for any release policy?
4. What exact bug windows and family-specific rules are still missing?
5. What must exist before a canonical `sinr_*_master_v1` governance system is trustworthy?
6. What should be rebuilt, promoted, quarantined, preserved, or retired next?

## Required output

1. Estate classification matrix: table -> role -> trust level -> keep/rebuild/retire
2. Top integrity risks, ranked
3. Gaps in salvage logic
4. Gaps in field-family integrity logic
5. Gaps in master dataset governance / manifests / release contracts
6. Concrete next build order with exact tables/scripts to change or create

## Copy/paste prompt for Claude

```text
You are conducting a fail-closed forensic audit of the full SINR data estate.

Your job is NOT to judge model quality first. Your job is to determine whether the current data estate can support a trustworthy canonical master dataset and release system for prediction/recommendation.

Use this trust order:
1. Live BigQuery tables and row/key behavior
2. Executable scripts and SQL
3. Docs / prose

Review these BigQuery tables:
- species_data.gbif_new_occurrences
- species_data.existing_training_coords
- species_data.occurrences
- species_data.sinr_v3_features_new_gbif_strict_full
- species_data.sinr_v3_features_backfill_strict_full
- species_data.sinr_v3_strict_unsampleable_contexts
- species_data.sinr_v3_unified_strict_train
- species_data.sinr_v3_unified_strict_train_v30_preview_clean
- species_data.sinr_v3_strict_unified_quarantine
- species_data.sinr_v3_features_new_gbif
- species_data.sinr_v3_features_backfill
- species_data.sinr_v3_unified_v1
- species_data.sinr_v3_unified_v2
- species_data.sinr_occurrence_unified_source_v1
- species_data.sinr_occurrence_salvage_status_v1
- species_data.sinr_occurrence_salvage_candidates_v1
- species_data.sinr_occurrence_salvage_audit_sample_v1
- species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1
- species_data.sinr_occurrence_salvage_summary_v1
- species_data.sinr_occurrence_field_integrity_status_v1
- species_data.sinr_occurrence_integrity_reconciliation_v1

Review these scripts / SQL:
- orchestrator/unified_gee_sampler_v3.py
- orchestrator/unified_gee_sampler_v3_strict.py
- orchestrator/consolidate_bq_v2.py
- orchestrator/compute_is_introduced_bq.py
- orchestrator/build_sinr_occurrence_salvage_tables.py
- orchestrator/build_sinr_field_integrity_status.py
- orchestrator/check_v30_preview_readiness.py
- orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql
- orchestrator/sql/sinr_master_dataset_v1/occurrence_grain_salvage_blueprint.sql
- orchestrator/sql/sinr_master_dataset_v1/field_family_integrity_blueprint.sql

Review these docs:
- docs/SINR BigQuery Lineage Map.md
- docs/SINR Forensic Program History + Master Dataset Plan.md
- docs/SINR Legacy Backfill Salvage Plan.md
- docs/SINR Field-Family Integrity Audit Plan.md
- docs/SINR Master Dataset v1 README.md
- docs/SINR Occurrence-Grain Master Training Schema.md
- docs/SINR Strict-Only Release Builder.md
- docs/SINR Hybrid Override System.md
- .claude/project-management/GO.md

Current working assumptions to challenge:
- strict_context_present rows are the only rows allowed into a strict release by default
- legacy-safe preview-inherited rows are blocked pending explicit audit override
- preview rows still inherit legacy feature payloads
- field-integrity status is currently a conservative scaffold, not final truth

Questions to answer:
1. Which current tables are safe raw sources, safe current training sources, salvage-only audit assets, and unsafe legacy artifacts?
2. Is the occurrence-grain salvage system correctly scoped and materially useful?
3. Is the field-integrity scaffold only a placeholder, or already decision-grade for release gating?
4. What exact bug windows and family-specific rules are still missing?
5. What is still missing before a canonical sinr_*_master_v1 governance system is trustworthy?
6. What exact release policy should govern strict_only, hybrid, and diagnostics-only outputs?
7. What should be retired, preserved, rebuilt, or promoted next?

Required output:
1. Estate classification matrix: table -> role -> trust level -> keep/rebuild/retire
2. Top integrity risks, ranked
3. Gaps in salvage logic
4. Gaps in field-family integrity logic
5. Gaps in governance / manifests / release contracts
6. Concrete next build order with exact tables/scripts to change or create

Be brutally skeptical. Prefer false negatives over false approval.
```

---

## Expanded Claude Audit Prompt

```text
You are auditing the SINR data estate after a major forensic cleanup and salvage-governance push.

Your job is to audit EVERYTHING that was just added or changed, verify whether the logic is actually conservative, identify hidden optimism or compounded assumptions, and recommend the safest next build order.

Do not focus only on model quality. Focus on data truth, lineage truth, release gating, and whether current audit tables could accidentally let bad rows pass as good.

Operating principles:
1. Fail closed.
2. Prefer false negatives over false approvals.
3. Trust live BigQuery + executable scripts over docs.
4. Treat docs as hypotheses unless confirmed in code/tables.
5. Look specifically for places where a field/table name sounds safer than it really is.

Audit scope

BigQuery tables to inspect:
- species_data.gbif_new_occurrences
- species_data.existing_training_coords
- species_data.occurrences
- species_data.sinr_v3_features_new_gbif_strict_full
- species_data.sinr_v3_features_backfill_strict_full
- species_data.sinr_v3_strict_unsampleable_contexts
- species_data.sinr_v3_unified_strict_train
- species_data.sinr_v3_unified_strict_train_v30_preview_clean
- species_data.sinr_v3_strict_unified_quarantine
- species_data.sinr_v3_features_new_gbif
- species_data.sinr_v3_features_backfill
- species_data.sinr_v3_unified_v1
- species_data.sinr_v3_unified_v2
- species_data.sinr_occurrence_unified_source_v1
- species_data.sinr_occurrence_salvage_status_v1
- species_data.sinr_occurrence_salvage_candidates_v1
- species_data.sinr_occurrence_salvage_audit_sample_v1
- species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1
- species_data.sinr_occurrence_salvage_summary_v1
- species_data.sinr_occurrence_field_integrity_status_v1
- species_data.sinr_occurrence_integrity_reconciliation_v1

Scripts / SQL to inspect:
- orchestrator/unified_gee_sampler_v3.py
- orchestrator/unified_gee_sampler_v3_strict.py
- orchestrator/consolidate_bq_v2.py
- orchestrator/compute_is_introduced_bq.py
- orchestrator/build_sinr_occurrence_salvage_tables.py
- orchestrator/build_sinr_field_integrity_status.py
- orchestrator/check_v30_preview_readiness.py
- orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql
- orchestrator/sql/sinr_master_dataset_v1/occurrence_grain_salvage_blueprint.sql
- orchestrator/sql/sinr_master_dataset_v1/field_family_integrity_blueprint.sql

Docs to inspect:
- docs/SINR Claude Audit Adjudication.md
- docs/SINR BigQuery Lineage Map.md
- docs/SINR Forensic Program History + Master Dataset Plan.md
- docs/SINR Legacy Backfill Salvage Plan.md
- docs/SINR Field-Family Integrity Audit Plan.md
- docs/SINR Master Dataset v1 README.md
- docs/SINR Occurrence-Grain Master Training Schema.md
- docs/SINR Data Estate Audit Handoff.md
- .claude/project-management/GO.md

What was recently built and must be audited skeptically:

1. Occurrence-grain salvage tables:
- species_data.sinr_occurrence_unified_source_v1
- species_data.sinr_occurrence_salvage_status_v1
- species_data.sinr_occurrence_salvage_candidates_v1
- species_data.sinr_occurrence_salvage_audit_sample_v1
- species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1
- species_data.sinr_occurrence_salvage_summary_v1

2. Field-integrity scaffold:
- species_data.sinr_occurrence_field_integrity_status_v1
- species_data.sinr_occurrence_integrity_reconciliation_v1

3. Hard-gated logic added recently:
- release_gate_default
- requires_manual_audit_override
- identity_integrity_status
- payload_provenance_status
- temporal_validity_default
- xiao_provenance_status
- xiao_bug_window_flag
- land_state_train_ok
- land_state_serve_parity_ok
- offline_only_excluded_by_online_contract
- occurrence_source_class_hint

Current assumptions you must challenge:
- strict_context_present rows are the only rows allowed into a strict release by default
- preview-inherited legacy-safe rows are blocked pending explicit audit override
- preview rows still inherit legacy payloads and should not silently count as clean strict rows
- field-integrity status is still a conservative scaffold, not final truth
- source-class hints are lineage hints, not quality guarantees

Questions to answer:
1. Which tables are truly safe raw sources, safe current training sources, salvage-only audit assets, and unsafe legacy artifacts?
2. Is the occurrence-grain salvage system correctly scoped, or is it still hiding optimism / collapsed assumptions?
3. Is the field-integrity scaffold correctly fail-closed, or are there still paths where preview-inherited / legacy rows can be mistaken as approved?
4. Which flags are too optimistic, too vague, or semantically overloaded?
5. Which rows/buckets should remain blocked no matter what until more provenance exists?
6. What exact next steps should happen before any hybrid training release is built?
7. What should be changed in naming, schema, or release policy to reduce human misinterpretation?

Required output format:
1. What was done correctly
2. What is still dangerous or misleading
3. Specific logic errors or hidden optimism
4. Recommended next 5 steps in order
5. Checklist for validating the estate before promoting any release
6. Which docs/tables should be updated next

Be brutally skeptical. Assume future humans will misunderstand any ambiguous label.
```

---

## Audit Checklist

- Verify `sinr_occurrence_unified_source_v1` row counts reconcile to `gbif_new_occurrences` + `existing_training_coords` expectations.
- Verify `sinr_occurrence_salvage_status_v1` does not silently classify ambiguous rows as usable.
- Verify `sinr_occurrence_salvage_candidates_v1` is never treated as release-ready by default.
- Verify `sinr_occurrence_salvage_audit_sample_legacy90_v1` is actually 90% backfill / legacy focused.
- Verify `sinr_occurrence_field_integrity_status_v1` uses fail-closed defaults for hybrid rows.
- Verify `release_gate_default='block_pending_audit_override'` rows cannot be mistaken for approved rows in downstream queries.
- Verify `strict_context_present` means exact strict context match, not full final release quality.
- Verify Xiao bug-window logic is conservative enough for preview and strict raw rows.
- Verify land-state flags do not overstate serve parity.
- Verify aridity / ET0 / IPCC flags do not overstate historical parity.
- Verify carbon / HILDA flags do not imply online serving support where none exists.
- Verify occurrence source hints are not being mistaken for data quality labels.
- Verify `no_context_available` rows stay visible in summary outputs and are not buried.
- Verify reconciliation matrix exposes all blocked vs override-required vs strict-approved combinations.
- Verify docs and scripts use the same meanings for `observation_year`, `emb_year`, `strict_context_present`, `legacy_unverified`, and `preview_inherited_legacy_payload`.

---

## Recommended next steps after Claude audit

1. Rename or tighten any bucket labels Claude flags as implicitly optimistic.
2. Add explicit bug-window columns for Xiao and any other known issue windows.
3. Encode family-specific availability / parity rules into the field-integrity table instead of relying on broad placeholders.
4. Add occurrence-source normalization into the future occurrence master rather than keeping it as a hint only.
5. Define the exact policy for:
   - `strict_only` release
   - `hybrid` release
   - diagnostics-only release
6. Only after that, consider building a first hybrid training release candidate.
