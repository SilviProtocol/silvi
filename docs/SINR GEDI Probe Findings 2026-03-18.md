# SINR GEDI Probe Findings — 2026-03-18

## Scope

This note records the read-only GEDI probe run used to decide whether a full GEDI-inclusive repair path is warranted for strict `SINR V4` lineage.

Inputs checked:

- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`
- `species_data.sinr_v3_features_backfill_strict_full`

Probe artifacts:

- `orchestrator/probe_gedi_semantics.py`
- `orchestrator/gedi_probe_outputs/gedi_probe_rows_20260318_080617.csv`
- `orchestrator/gedi_probe_outputs/gedi_probe_summary_20260318_080617.json`
- `orchestrator/gedi_probe_outputs/gedi_probe_rows_20260318_080617_with_old_mosaic.csv`

## Official product semantics

Assets verified against the Earth Engine catalog and the ORNL/LP DAAC GEDI documentation:

- `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316`
- `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316`

Key semantic findings:

- `p95` on `gediv002_rh-98-a0...` is the `95th` percentile of shot-level `RH98` values within the `1km` pixel.
- `RH98` is a canopy-height proxy in meters above ground, not absolute elevation above the ellipsoid.
- Official valid range for GEDI `RH` values is approximately `[-213, 213]` meters.
- `shan` on `gediv002_fhd-pai-1m-a0...` is Shannon entropy of shot-level `FHD` values within the pixel.
- `shan` is not raw foliage height diversity; it is a heterogeneity statistic.
- Missing GEDI should stay masked / `NULL`; `unmask(0)` is not a safe semantic choice for strict training.

## Probe design

The probe sampled `120` distinct coordinates total, balanced across both `new_gbif` and `backfill` and across six buckets:

- negative current canopy values
- current canopy values `> 213`
- current canopy values in `80..213`
- current zeros below orbit limit
- current zeros above orbit limit
- normal-looking canopy values in `5..60`

For each point, the probe sampled GEDI directly from the verified per-asset images without `unmask(0)` using `reduceRegions(..., first(), scale=1000)`.

Sampled GEDI metrics:

- `RH98` asset: `mean`, `meanbase`, `median`, `sd`, `iqr`, `p95`, `shan`, `countf`
- `FHD` asset: `mean`, `meanbase`, `median`, `sd`, `iqr`, `p95`, `shan`, `countf`

The probe also replayed the historical bad pattern for comparison:

- `ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic().select('p95'/'shan').unmask(0)`

## Main result

The bad raw GEDI values in the current strict tables are overwhelmingly explained by the old collection-level mosaic misuse, not by the correct per-asset GEDI values.

Cross-check result from `gedi_probe_rows_20260318_080617_with_old_mosaic.csv`:

- current raw GEDI matches old mosaic GEDI: `101 / 120`
- current raw GEDI matches proper per-asset GEDI: `7 / 120`

This is the smoking gun.

## Branch-specific interpretation

### `new_gbif`

`new_gbif` is almost entirely contaminated by the old mosaic semantics.

Probe bucket matches:

- `gt213_lowlat`: `10/10` old mosaic matches
- `hi_80_213_lowlat`: `10/10` old mosaic matches
- `neg_lowlat`: `10/10` old mosaic matches
- `zero_highlat`: `10/10` old mosaic matches
- `zero_lowlat`: `10/10` old mosaic matches
- `normal_5_60_lowlat`: `9/10` old mosaic matches

Conclusion:

- `new_gbif` raw GEDI cannot be trusted for strict training or inference.

### `backfill`

`backfill` is mixed-vintage.

Probe bucket matches:

- bad buckets (`gt213`, `80..213`, negative): `10/10` old mosaic matches
- `normal_5_60_lowlat`: `7/10` proper GEDI matches, `0/10` old mosaic matches

Conclusion:

- `backfill` contains a mixture of old-mosaic contamination and later cleaner per-asset GEDI values.
- Even though some rows look usable, the branch is not semantically uniform enough to trust raw GEDI as-is.

## Missingness and support

Probe summary (`gedi_probe_summary_20260318_080617.json`):

- `95 / 120` probe rows returned `NULL` canopy from proper GEDI sampling
- `25 / 120` probe rows returned sane canopy values in `0..100`
- `18 / 120` had `countf >= 10`
- `14 / 120` had `countf >= 20`

Interpretation:

- Many current raw zeros are fake missingness from `unmask(0)` or old mosaic behavior.
- Proper GEDI extraction returns real missingness (`NULL`) and shot-count support.

## Concrete examples

Examples reproduced during the probe:

- NYC point with current canopy `11.928`:
  - old mosaic returns `11.928`
  - proper GEDI returns `NULL`
- Italy point with current canopy `1652.228`:
  - old mosaic returns `1652.228`
  - proper GEDI returns `24.5825` with `countf=126`
- Backfill point with current canopy `903.348`:
  - old mosaic returns `903.348`
  - proper GEDI returns `19.187` with `countf=19`

## Decisions

### Keep current `V4.7/V4.9` no-GEDI path canonical

- `species_data.sinr_v47_backfill_strict_core_v1`
- `species_data.sinr_v47_merged_strict_core_train_v2`

These remain the clean current training lineage.

### If GEDI is reintroduced, do a GEDI-only re-extract

Do not full re-extract all contexts.

Repair path should be:

- both `new_gbif` and `backfill`
- distinct coordinate grain (`lat4/lon4`)
- non-destructive sidecar lookup + overlay lineage

Union coord counts as of this probe:

- `new_gbif` distinct coords: `8,505,329`
- `backfill` distinct coords: `5,232,751`
- overlap: `883,075`
- union: `12,855,005`

### First admissible GEDI contract

Canopy:

- keep `rh-98-a0 / p95`
- include `countf`
- preserve `NULL` missingness
- do not `unmask(0)`

Foliage:

- do not reuse current `gedi_foliage_height_div = shan`
- if a foliage feature is reintroduced, use `mean` or `median` from the `FHD` asset instead
- keep `shan` only as an optional diagnostic heterogeneity metric, not as the main foliage variable

### Suggested first QC gate for future GEDI admission

- `NULL` outside coverage, no fake `0`
- `countf >= 10` minimum, prefer `>= 20`
- canopy admitted only in a conservative range (first pass fail-closed on `>100m`)
- one frozen asset/band contract across both branches
- no trainer- or inference-time clipping

## Bottom line

The current raw GEDI columns in both strict branches are not clean enough to trust.

- `new_gbif` raw GEDI is overwhelmingly old-mosaic contamination.
- `backfill` raw GEDI is mixed between old-mosaic contamination and cleaner later values.
- The current foliage column is semantically wrong even when numerically sane because `shan` is not raw foliage height diversity.

Therefore:

- keep GEDI excluded now,
- repair via a GEDI-only coordinate-grain re-extract for both branches,
- reintroduce canopy first,
- and only bring foliage back after switching away from `shan`.
