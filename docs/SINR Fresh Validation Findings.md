# SINR Fresh Validation Findings

Date: 2026-03-13
Status: initial findings from the 1,000-row fresh validation run

## Tables

- sample batch:
  - `species_data.sinr_fresh_validation_batch__fresh_validation_1000_20260313_001500`
- fresh extraction output:
  - `species_data.sinr_fresh_validation_extract__fresh_validation_1000_20260313_001500`
- comparison table:
  - `species_data.sinr_fresh_validation_compare__fresh_validation_1000_20260313_001500`
- failures table:
  - `species_data.sinr_fresh_validation_failures__fresh_validation_1000_20260313_001500`
- Xiao-specific audit:
  - `species_data.sinr_xiao_inconsistency_audit__fresh_validation_1000_20260313_001500`

## Top-line result

The strict-control mismatch was not broad corruption.

It was mostly a **specific Xiao inconsistency**.

## Core numbers

- sampled rows: `1,000`
- fresh extracted rows landed: `860`
- missing fresh extract rows: `140`

## Fresh validation compare summary

### Strict controls

- sampled: `100`
- fresh rows: `100`
- current strict rows present: `100`
- fresh vs strict exact overlap matches: `93`
- mismatches: `7`

### What those 7 strict mismatches actually were

All 7 mismatches had exactly one differing field:

- `xiao_planted_forest`

Pattern for all 7:

- preview-clean: `2.0`
- fresh validation extract: `2.0`
- current strict raw: `0.0`

Interpretation:

- fresh extraction agrees with preview-clean
- current strict raw disagrees
- this points to a localized Xiao inconsistency in current strict raw rows, not broad strict corruption

### Xiao-specific audit summary

- `missing_comparison`: `663`
- `fresh_equals_strict`: `186`
- `preview_fresh_agree_strict_differs`: `11`

This means the validation run already found `11` rows where preview + fresh agree and current strict raw differs on Xiao.

## Temporal extraction failure surfaced

The fresh validation run also exposed a separate temporal bug:

- year-2000 batches failed with:
  - `Image.select: Band pattern 'Gpp' was applied to an Image with no bands`

This is tracked as:

- `treekipedia-8e5`

## Practical conclusion

### Good news

- the `93/100` strict-control result does **not** imply broad strict-payload corruption
- the control mismatch appears narrow and diagnosable

### Bad news

- current strict raw is not internally uniform on Xiao
- temporal extraction has a year-2000 edge-case bug

## Safest next actions

1. Audit and repair Xiao consistency in `sinr_v3_features_new_gbif_strict_full`.
2. Fix the year-2000 GPP / temporal-env failure.
3. Refine comparison methodology so control checks distinguish:
   - stable core strict fields
   - Xiao / operationally corrected fields
   - preview-inherited vs strict-backed fields
