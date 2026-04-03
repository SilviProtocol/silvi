# SINR Strict-Only Release Builder

Date: 2026-03-12
Status: implemented, non-destructive, conservative

## Purpose

This documents the first enforced SINR release builder that actually uses release gates instead of treating them as advisory labels.

Builder script:

- `orchestrator/build_sinr_strict_only_release.py`

## What it builds

For each run it creates:

- `species_data.sinr_release_allowlist__<release_id>`
- `species_data.sinr_train_release__<release_id>`
- a registry row in `species_data.sinr_release_registry_v1`

## Current enforced logic

The builder only includes rows where:

- `release_gate_default = 'allow_strict_release'`

This means hybrid rows are blocked by default.

## Current implementation details

- source training labels / metadata come from:
  - `species_data.sinr_v3_unified_strict_train_v30_preview_clean`
- release-gate truth comes from:
  - `species_data.sinr_occurrence_field_integrity_status_v1`
- strict raw feature payload comes from:
  - `species_data.sinr_v3_features_new_gbif_strict_full`

Important limitation:

- current strict-only release is **preview-backed for labels/meta**, but **strict-backed for common feature columns**
- preview-only feature families without strict raw provenance are explicitly nulled
- because `sinr_v3_features_backfill_strict_full` does not exist yet, this release currently covers only `new_gbif`

## Current release ids

- `strict_only_20260312_194000` — current corrected release

Superseded due to strict raw duplicate fanout before dedup fix:

- `strict_only_20260312_193619`

## Audit-time verification

For `strict_only_20260312_194000`:

- allowlist rows: `8,579,371`
- release rows: `8,172,288`
- non-allow-gated rows in release: `0`
- non-`new_gbif` rows in release: `0`

The row-count difference between allowlist and release exists because not every allowlisted occurrence row is currently represented in the preview training table.

## What this is and is not

### This is

- the first enforced strict-only release path
- a safer alternative to training directly from preview-clean
- a concrete proof that release gates can be operationalized

### This is not

- a final full strict release
- a hybrid release
- a replacement for the future strict-full unified builder
- a solution for backfill strict coverage

## Next required follow-up

1. Rename optimistic salvage bucket names.
2. Add explicit bug-window and family-specific rules into field integrity.
3. Build a separate explicit override mechanism for audited hybrid rows.
4. Build a full strict release path once `sinr_v3_features_backfill_strict_full` exists.
