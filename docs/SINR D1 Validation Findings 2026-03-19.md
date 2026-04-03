# SINR D1 Validation Findings 2026-03-19

Date: 2026-03-19
Audience: active SINR V4 operators
Status: active D1 validation report

## Purpose

This report records `D1` from the post-merge radiata rank-1 program:

- targeted validation of the remaining narrow non-GEDI data questions
- enough to decide whether the merged no-GEDI estate is broadly bad, narrowly fixable, or already clean enough for the next training experiment

## Scope

Validated families:

1. `modis_gpp_mean` `NULL` vs `0` branch drift
2. pre-2015 `Dynamic World` / `ESA` proxy mismatches
3. `xiao_planted_forest` branch mismatches
4. `modis_lc_at_obs = -1` residue

Tables used:

- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`
- `species_data.sinr_v3_features_backfill_strict_full`
- `species_data.sinr_v47_backfill_strict_core_v1`
- `species_data.sinr_v47_merged_strict_core_train_v2`

Validation method:

- BigQuery overlap and affected-row counts
- targeted current GEE re-sampling on mismatch rows
- current GEE used as the adjudication source for these field families

## Headline Verdict

The merged no-GEDI estate is **not broadly broken**.

But `D1` found **three real branch-semantic issues** that are important enough to fix before the next training experiment:

1. backfill post-2000 `modis_gpp_mean = 0` is mostly fake missingness
2. backfill `xiao_planted_forest` contains real semantic drift
3. new_gbif pre-2015 `dynamic_world` has a stale proxy/remap problem on a subset of contexts

The tiny `modis_lc_at_obs = -1` residue is benign and does not need repair.

## Shared Context

Overlapping branch contexts at rounded training grain:

- `556,530` overlapping `(lat4, lon4, observation_year, emb_year)` contexts

Local overlap around the canonical radiata benchmark (`25km` radius):

- `209` overlapping contexts

## 1. MODIS GPP Drift

### BigQuery findings

Overlap mismatch count after the current strict-core policy:

- `20,012` overlap contexts (`3.6%` of overlaps)

Mismatch type:

- **all** `20,012` are `new_gbif -> NULL` vs `backfill -> 0`
- there were **no** cases where backfill matched a nonzero current value and new_gbif was clearly wrong

Affected canonical merged rows:

- known-bad overlap contexts contribute:
  - `52,032` `new_gbif` merged rows
  - `22,876` `backfill` merged rows
- total backfill rows in the canonical merged train with post-2000 `modis_gpp_mean = 0`:
  - `244,503`

### GEE validation

Targeted sample of `100` overlap mismatch rows:

- current GEE returned `NULL` for `88`
- current GEE returned a real positive value for `12`
- current GEE returned `0` for `0`

Separate random sample of `100` backfill post-2000 zero-GPP rows overall:

- current GEE returned `NULL` for `93`
- current GEE returned a real positive value for `7`
- current GEE returned `0` for `0`

Local radiata vicinity (`25km`) mismatch contexts:

- `20`
- current GEE returned:
  - `15` `NULL`
  - `5` real positive values
  - `0` zeros

### Conclusion

Backfill post-2000 `modis_gpp_mean = 0` is mostly **fake missingness**, not a real ecological zero.

This is a real issue in the current canonical merged path because the fast-safe backfill strict-core builder does not currently convert these zeros to `NULL`.

### Decision

- **Repair required before the next training experiment**

## 2. Dynamic World / ESA Proxy Drift

### BigQuery findings

Overlap mismatch counts:

- pre-2015 mismatches: `32,492` (`5.8%` of overlaps)
- 2015+ mismatches: `20`

Dominant mismatch directions:

- `4 -> 2`: `25,540`
- `1 -> 4`: `5,205`
- `4 -> 5`: `1,354`

Affected canonical merged rows on known-bad overlap contexts:

- `103,121` `new_gbif` merged rows
- `69,883` `backfill` merged rows on the same contexts

Local radiata vicinity (`25km`) pre-2015 DW mismatches:

- `0`

### GEE validation

Targeted sample of `100` pre-2015 mismatch rows:

- current GEE matched `backfill` in `92`
- current GEE matched `new_gbif` in `0`
- current GEE matched neither in `8`

### Conclusion

This is a real branch semantic drift, and the evidence strongly suggests the **new_gbif pre-2015 proxy/remap is stale on a subset of contexts**, while backfill usually matches the current expected proxy behavior.

This matters for overall training cleanliness, but it does **not** look like the immediate cause of the 2023 radiata plantation failure because there are no such mismatches near the benchmark suite.

### Decision

- **Repair recommended before broader forward training, but not the top local radiata blocker**

## 3. Xiao Drift

### BigQuery findings

Overlap mismatch count:

- `13,504` (`2.4%` of overlaps)

Dominant mismatch directions:

- `1 -> 0`: `3,786`
- `0 -> 1`: `3,742`
- `2 -> 0`: `1,961`
- `0 -> 2`: `1,781`
- `2 -> 1`: `1,130`
- `1 -> 2`: `1,104`

Affected canonical merged rows on known-bad overlap contexts:

- `35,091` `new_gbif` merged rows on those contexts
- `22,609` `backfill` merged rows on those contexts

Local radiata vicinity (`25km`) Xiao mismatches:

- `8`

### GEE validation

Targeted sample of `100` Xiao mismatch rows:

- current GEE matched `new_gbif` in `100 / 100`
- current GEE matched `backfill` in `0 / 100`

Local radiata vicinity mismatch sample:

- current GEE matched `new_gbif` in `8 / 8`

### Conclusion

Backfill Xiao has real semantic drift relative to the current correct decode.

This is important because Xiao is one of the few explicit plantation-related signals in the current system, and the mismatches reach into the benchmark vicinity.

### Decision

- **Repair required before the next training experiment**

## 4. `modis_lc_at_obs = -1` Residue

### BigQuery findings

Post-2000 residue:

- `76` rows in `new_gbif`
- `15` rows in `backfill`
- `91` rows total

Local radiata vicinity:

- `0`

### GEE validation

Full census of all `91` rows:

- current GEE still returns `-1` for all `91`

### Conclusion

This residue is benign and expected. It does not need repair.

### Decision

- **No action needed**

## What D1 Proves

### Proven false

- the merged no-GEDI estate is **not** broadly corrupt
- the remaining non-GEDI questions are **not** just cosmetic bookkeeping

### Proven true

- there are at least two real branch-semantic issues still inside the current canonical merged path:
  - backfill GPP zero-as-missingness
  - backfill Xiao drift
- and one meaningful but less benchmark-local issue:
  - new_gbif pre-2015 Dynamic World proxy drift

## Recommended Next Step

Before `T1` BCE, do a narrow repair pass and rebuild the merged table with:

1. backfill post-2000 `modis_gpp_mean = 0` repaired to explicit missingness where appropriate
2. backfill Xiao repaired via the current correct decode
3. new_gbif pre-2015 Dynamic World repaired / reprojected to the current proxy contract

Then rerun the current merged recipe **unchanged** on that repaired no-GEDI lineage.

That isolates the data repair effect before changing the loss.

## Bottom Line

`D1` does **not** send us back to “the merged data is bad.”

But it does say the current no-GEDI merged line is **not yet the cleanest version we can make it**.

There are three concrete, repairable, non-GEDI semantic issues left, and at least two of them reach into the plantation/radiata problem directly enough that they should be fixed before the next training experiment.
