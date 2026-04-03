# SINR Occurrence-Grain Master Training Schema

Date: 2026-03-12
Status: design only
Owner issue: `treekipedia-cz6`

## Purpose

Define the master training-table shape where each row is an occurrence/example and the environmental context is attached onto that occurrence.

This is the recommended shape for future training releases.

---

## One row = one occurrence/example

The row grain should be:

- one occurrence record
- one canonical taxon id
- one place-time context
- one attached feature context
- one salvage / quality status

This avoids confusing raw context tables with labeled training tables.

---

## Proposed key columns

### Occurrence identity

- `occurrence_example_id`
- `source_record_id`
- `data_source`
- `source_system`

### Taxonomy

- `taxon_id`
- `species_scientific_name`
- `taxonomy_version`

### Raw occurrence context

- `latitude`
- `longitude`
- `lat4`
- `lon4`
- `observation_year`
- `emb_year`
- `coordinate_uncertainty_m`
- `establishment_means`

### Joined feature provenance

- `feature_context_id`
- `feature_source_type`  -- `strict_context_present`, `legacy`, `hybrid`
- `feature_release_id`
- `feature_match_status`

### Label / metadata assertions

- `verification_status`
- `verification_source`
- `is_introduced`
- `tdwg_region`
- `land_state_class`
- `disturbance_intensity`
- `forest_stability`
- `successional_stage`

### Salvage / quality fields

- `context_quality_status`
- `bug_window_flag`
- `has_strict_context`
- `has_legacy_context`
- `requires_reextract`
- `quarantine_reason`

### Feature payload

- AlphaEarth embedding columns
- environmental continuous features
- categorical environmental features
- optional derived features

---

## Why this shape is better

- training uses example rows, not abstract context rows
- many occurrences can still share the same context internally
- provenance stays explicit
- salvageability becomes measurable per row
- future recommendation layers can fork from the same occurrence-linked evidence base

---

## Required statuses

Every row should be assigned one of:

- `strict_context_present`
- `legacy_unverified`
- `legacy_partial_candidate`
- `ambiguous_context`
- `needs_reextract`
- `quarantine`

These statuses should be material columns, not hidden pipeline logic.

---

## Release policy

### Gold training release

- only `strict_context_present`

### Hybrid training release

- `strict_context_present` + audited `legacy_unverified`

Current implementation support:

- `species_data.sinr_occurrence_salvage_candidates_v1` is the first non-destructive candidate pool for that future hybrid release.
- It is an audit table, not yet a promoted training table.

### Analysis release

- all statuses retained for diagnostics and cleanup work

---

## Non-goals

- raw strict feature tables should not directly become the training table
- legacy unified tables should not be re-promoted as canonical truth
- train-time labels should not be hidden inside raw extraction outputs without explicit example grain

---

## Bottom line

The master training dataset should be occurrence-row based, with context attached, provenance explicit, and salvageability visible.
