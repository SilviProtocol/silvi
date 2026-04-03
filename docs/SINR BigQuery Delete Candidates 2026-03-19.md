# SINR BigQuery Delete Candidates 2026-03-19

Date: 2026-03-19
Audience: operators trying to reduce BigQuery storage safely
Status: conservative delete-candidate review; `M0` completed, later milestones gated by V4 forensics

## Purpose

Answer the narrow question:

**Which SINR BigQuery tables can be deleted with high confidence because a better or strictly superseding table already exists?**

This document is intentionally conservative.
It is not a license to delete all old SINR artifacts.

## Current Principle

Delete only when one of these is true:

1. exact duplicate / accidental superseded output exists,
2. the table is a clearly superseded intermediate lineage layer and the final version exists,
3. the table is a repeated release snapshot and a later equivalent snapshot is already kept,
4. the table is a smoke-test artifact with no canonical value.

Do **not** delete raw strict branch sources, canonical merged training tables, or historical comparison tables you still need for provenance.

## Delete Now - High Confidence

These are the tables I am comfortable calling safe delete candidates now.

| Table | GB | Why safe |
|---|---:|---|
| `species_data.sinr_v47_merged_strict_core_train_v1` | 110.57 | superseded by `..._v2`; same row count, `v2` is the canonical fixed table |
| `species_data.sinr_v3_unified_strict_train_v30_preview` | 122.59 | superseded by `..._preview_clean`; keep the clean version only |
| `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_v1` | 46.44 | superseded intermediate before GPP semantic repair |
| `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_v1` | 46.61 | superseded intermediate before dedup + completion |
| `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_v1` | 46.51 | superseded by `...deduped_completed_v1` |
| `species_data.sinr_train_release__hybrid_train_only_20260312_195000` | 47.85 | repeated release snapshot, later copy retained |
| `species_data.sinr_train_release__hybrid_train_only_20260312_220800` | 47.85 | repeated release snapshot, later copy retained |
| `species_data.sinr_train_release__hybrid_train_only_20260312_221500` | 47.85 | repeated release snapshot, later 20260314 copy retained |
| `species_data.sinr_train_release__strict_only_20260312_193619` | 47.72 | repeated release snapshot, later copy retained |
| `species_data.sinr_train_release__strict_only_20260312_194000` | 47.57 | repeated release snapshot, later copy retained |
| `species_data.sinr_train_release__strict_only_20260314_142529` | 47.61 | repeated release snapshot, keep latest strict-only snapshot instead |
| `species_data.sinr_release_allowlist__hybrid_train_only_20260312_195000` | 4.75 | repeated allowlist snapshot, later copy retained |
| `species_data.sinr_release_allowlist__hybrid_train_only_20260312_220800` | 4.75 | repeated allowlist snapshot, later copy retained |
| `species_data.sinr_release_allowlist__hybrid_train_only_20260312_221500` | 4.75 | repeated allowlist snapshot, later 20260314 copy retained |
| `species_data.sinr_release_allowlist__strict_only_20260312_193548` | 4.55 | repeated allowlist snapshot, later copy retained |
| `species_data.sinr_release_allowlist__strict_only_20260312_194000` | 4.55 | repeated allowlist snapshot, later copy retained |
| `species_data.sinr_release_allowlist__strict_only_20260314_142529` | 4.55 | repeated allowlist snapshot, keep latest strict-only snapshot instead |
| `species_data.sinr_v48_gedi_lookup_smoke_v1` | ~0 | smoke table; delete after full GEDI lookup QC |

Estimated savings from the delete-now list:

- about `687 GB`

Execution status:

- completed on `2026-03-19`
- post-delete SINR/species_data footprint: about `1,567.36 GB`

## Retirement Milestones Aligned To V4 Progress

This delete plan is now tied to the active SINR V4 program.

### `M0` - Completed

- zero-regret delete pass
- tracked in `treekipedia-7by`
- already executed

### `M1` - After parity and non-GEDI validation

Gate:

- benchmark parity (`P1/P2`) complete
- targeted non-GEDI validation (`D1`) complete

Tracked by:

- `treekipedia-a12`

Likely delete bucket:

- latest release snapshots / allowlists
- BQ export artifacts / shard tables

Approximate savings:

- about `171 GB`

### `M2` - After v2/v3 forensic closeout

Gate:

- old-artifact parity work is complete
- no remaining active need for legacy v1/v2/raw tables in the radiata forensic path

Tracked by:

- `treekipedia-7za`

Likely delete bucket:

- `sinr_v3_unified_v1`
- `sinr_v3_unified_v2`
- legacy raw branch tables
- legacy introduced / aux tables no longer needed for replay

Approximate savings:

- about `343 GB`

### `M3` - After merged canonization

Gate:

- merged V4 lineage becomes the only canonical provenance we still need
- strict intermediate assembly tables are no longer needed for replay/debugging

Tracked by:

- `treekipedia-rn8`

Likely delete bucket:

- overlapping strict-stack assembly tables

Approximate savings:

- about `350 GB`

## Keep For Now

These should stay.

### Canonical current lineage

- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`
- `species_data.sinr_v3_features_backfill_strict_full`
- `species_data.sinr_v47_backfill_strict_core_v1`
- `species_data.sinr_v47_merged_strict_core_train_v2`
- `species_data.sinr_v48_gedi_coord_manifest_v1`
- `species_data.sinr_v48_gedi_lookup_v1` (while the run is active and until QC completes)

### Current safe historical comparison tables

- `species_data.sinr_v41_preview_strict_core_v1`
- `species_data.sinr_v41_preview_strict_core_train_v1`
- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`

Reason:

- these still matter for provenance and benchmark comparison

### Legacy tables to keep until an explicit retirement pass

- `species_data.sinr_v3_features_new_gbif`
- `species_data.sinr_v3_features_backfill`
- `species_data.sinr_v3_unified_v1`
- `species_data.sinr_v3_unified_v2`
- `species_data.sinr_v3_is_introduced`
- `species_data.sinr_v3_land_state_t1`

Reason:

- the strict program has better replacements, but these legacy tables still have forensic and reproducibility value
- they are not in the “delete with high confidence right now” bucket

## Maybe Later, But Not In The Immediate Delete Set

These could be revisited later if cost pressure is severe:

- `species_data.sinr_v3_unified_strict_train`
- `species_data.sinr_v3_strict_unified_hits_raw`
- `species_data.sinr_v3_strict_unified_train_core`
- `species_data.sinr_v3_unified_strict_train_v30_medium_5m`
- `species_data.sinr_v3_unified_strict_train_v30_medium_5m_s{0..4}`
- `species_data.sinr_v3_unified_strict_train_v30_smoke_1m`
- `species_data.sinr_v3_unified_strict_train_v30_local_200k`

Reason:

- many are intermediate or export-oriented tables,
- but some still have value for quick replay / debugging,
- so I would not call them “confident delete now” without one more pass.

## Recommended Delete Procedure

1. Delete only the `Delete Now - High Confidence` set.
2. Log the deletion set in beads under `treekipedia-7by`.
3. Keep one latest snapshot per release family.
4. Do not delete canonical merged or canonical strict raw tables.
5. Do not delete the full GEDI lookup or manifest until GEDI overlay work is complete.

## Bottom Line

If you want safe storage savings now, the immediate conservative delete set is the superseded intermediates, duplicate release snapshots, duplicate allowlists, the obsolete raw preview table, and the accidental `v47` duplicate.

That should free about `687 GB` without touching the current canonical strict or merged lineages.
