# SINR jo1 Repair Status 2026-03-19

Date: 2026-03-19
Audience: active SINR V4 operators
Status: repair implementation complete; unchanged-rerun still pending

## Purpose

Record what the narrow non-GEDI repair pass (`treekipedia-jo1`) actually changed after `D1`.

## What Was Repaired

### 1. Backfill post-2000 GPP zero-as-missingness

Problem from `D1`:

- many backfill post-2000 `modis_gpp_mean = 0` values were fake missingness

Repair path implemented:

- manifest table:
  - `species_data.sinr_v48_backfill_gpp_zero_manifest_v1`
- repair lookup table:
  - `species_data.sinr_v48_backfill_gpp_lookup_v1`

Final lookup status:

- `236,120 / 236,120` repair contexts complete

### 2. Backfill Xiao semantic drift

Problem from `D1`:

- backfill `xiao_planted_forest` disagreed with the current correct decode

Repair path implemented:

- missing-coord manifest:
  - `species_data.sinr_v48_backfill_xiao_missing_manifest_v1`
- repair lookup table:
  - `species_data.sinr_v48_backfill_xiao_lookup_v1`
- combined clean source for backfill overlay:
  - `species_data.sinr_xiao_clean_lookup_v1`
  - plus the new missing-coord lookup above

Final lookup status:

- `117,408 / 117,408` missing repair coords complete

### 3. new_gbif pre-2015 Dynamic World proxy drift

Problem from `D1`:

- `new_gbif` had a stale pre-2015 proxy/remap subset

Repair path implemented:

- deterministic recomputation of pre-2015 `dynamic_world` from `esa_worldcover_2021`
- no new extraction needed

## New Repaired Tables

### Repaired branch strict-core tables

- `species_data.sinr_v48_new_gbif_strict_core_repaired_v1`
- `species_data.sinr_v48_backfill_strict_core_repaired_v1`

### Repaired merged training-grain table

- `species_data.sinr_v48_merged_strict_core_train_v1`

## Sanity Checks

### Table size / shape

- repaired merged table rows: `21,387,371`
- repaired merged table species: `45,096`

This means the repair stayed non-destructive at the training-grain level.

### Backfill post-2000 zero GPP

- `species_data.sinr_v48_backfill_strict_core_repaired_v1`
  - post-2000 zero GPP rows remaining: `0`

### Row-level change magnitude vs `v47`

Using the full training key:

- `gpp_changed_rows`: `244,503`
- `dw_changed_rows`: `7,042,829`
- `xiao_changed_rows`: `6,568,744`

Interpretation:

- GPP fix is narrow and targeted
- DW/Xiao repairs touch a large part of the merged training surface because they change branch-aligned categorical values across many training-grain rows, even when the number of distinct repaired overlap contexts is much smaller

## What This Means

The non-GEDI repair pass is now actually implemented.

We are no longer in the state of:

- "we know the problems but have not fixed them"

We are now in the state of:

- repaired `v48` merged no-GEDI table exists,
- it is non-destructive,
- and the next gate is to rerun the current merged recipe unchanged to measure the effect of the data repair before changing the loss or adding negatives.

Important correction:

- the first `v48` unchanged rerun that regressed badly is **not** a valid comparison result.
- root cause: `build_sinr_v48_merged_strict_core_train.py` originally used a positional `UNION ALL` across repaired branch tables with different column order.
- that scrambled backfill features from the `xiao_planted_forest` / `dynamic_world` boundary onward.
- the merge builder has now been fixed to use an explicit common projection order for both branches.
- therefore the first `v48` rerun should be treated as invalid and superseded.

## Next Step

The next required step is:

- rebuild the normalization stats / local data path from `species_data.sinr_v48_merged_strict_core_train_v1`
- rerun the current merged recipe unchanged on the corrected merged table

Only after that should the program move to the first true recipe change (`BCE`).
