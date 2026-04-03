# SINR Deletion Readiness Matrix

Date: 2026-03-12
Status: non-destructive review only
Owner issue: `treekipedia-9bw`

## Recommendation first

Do **not** delete more BigQuery tables yet.

The only clearly safe delete that was already taken was:

- `species_data.sinr_v3_unified_v2_final`

Everything else should stay until all of the following are true:

1. a validated replacement exists,
2. salvage / reverse-engineering value is exhausted,
3. lineage value is documented elsewhere,
4. release builders no longer depend on the table,
5. a final retirement decision is reviewed explicitly.

This is the conservative position.

---

## Why not delete yet

- legacy tables still help quantify what was lost vs recovered,
- some legacy rows may still be salvageable,
- strict-full backfill is not built yet,
- field-family integrity logic is still maturing,
- release governance is now improving but not yet complete,
- deleting too early makes forensic recovery and confidence-building harder.

---

## Current storage context

Current `species_data` dataset size is about:

- `1,446.21 GB` decimal
- about `1.45 TB`

So yes, storage matters, but correctness matters more right now.

---

## Readiness matrix

| Table | Size GB | Current role | Replacement exists? | Salvage / forensic value | Delete readiness | Recommendation |
|---|---:|---|---|---|---|---|
| `species_data.sinr_v3_unified_v1` | 79.81 | legacy assembled training table | no final strict replacement yet | high | low | keep |
| `species_data.sinr_v3_unified_v2` | 168.30 | legacy assembled training table with known join issues | no final strict replacement yet | very high | low | keep |
| `species_data.sinr_v3_features_new_gbif` | 51.15 | legacy raw feature table, new GBIF branch | partial (`new_gbif_strict_full`) | high | low-medium | keep |
| `species_data.sinr_v3_features_backfill` | 21.95 | legacy raw feature table, backfill branch | no strict-full replacement yet | very high | low | keep |
| `species_data.sinr_v3_is_introduced` | 10.79 | legacy auxiliary join table | not fully superseded | medium | low | keep |
| `species_data.sinr_v3_land_state_t1` | 3.68 | legacy auxiliary join table / training artifact | not fully superseded | medium | low | keep |
| `species_data.sinr_v3_unified_strict_train_v30_preview` | 122.59 | preview-era training table | partly replaced by `_clean`, but still useful | medium | low | keep for now |
| `species_data.sinr_v3_unified_strict_train_v30_preview_clean` | 122.02 | current safest usable training table | no final strict-full release yet | very high | very low | keep |
| `species_data.sinr_v3_unified_strict_train` | 121.71 | current strict train table | no final master replacement yet | very high | very low | keep |
| `species_data.sinr_v3_strict_unified_hits_raw` | 116.04 | strict intermediate / provenance table | no proven scripted replacement chain yet | very high | very low | keep |
| `species_data.sinr_v3_strict_unified_quarantine` | 52.25 | strict quarantine table | no replacement | high | very low | keep |
| `species_data.sinr_v3_features_new_gbif_strict_full` | 31.98 | active strict raw feature table | canonical for this branch | critical | none | never delete now |
| `species_data.sinr_occurrence_unified_source_v1` | 5.16 | audit / salvage base | rebuildable | medium | medium | keep until audit complete |
| `species_data.sinr_occurrence_salvage_status_v1` | 6.92 | occurrence-grain salvage audit | rebuildable | high current value | low-medium | keep |
| `species_data.sinr_occurrence_field_integrity_status_v1` | 12.86 | field-integrity scaffold | rebuildable | high current value | low-medium | keep |
| `species_data.sinr_train_release__strict_only_20260312_194000` | 47.57 | enforced strict-only release | active release artifact | high | none | keep |
| `species_data.sinr_train_release__hybrid_train_only_20260312_195000` | 47.85 | hybrid-builder proof artifact | supersedable later | medium | medium later | keep for now |

---

## Strongest future delete candidates

These are the strongest **future** candidates, but not yet safe enough to remove:

### Tier 1: likely removable later

- `species_data.sinr_v3_unified_v1`
- `species_data.sinr_v3_unified_v2`

Only after:

- strict-full unified replacement exists,
- salvage audit is complete,
- and lineage/reporting value is captured elsewhere.

### Tier 2: likely removable after strict-full backfill lands

- `species_data.sinr_v3_features_new_gbif`
- `species_data.sinr_v3_features_backfill`

Only after:

- strict raw replacements exist for both branches,
- randomized salvage audit is complete,
- and no release/salvage process still references them.

### Tier 3: maybe removable later, but low savings

- `species_data.sinr_v3_is_introduced`
- `species_data.sinr_v3_land_state_t1`

These are smaller tables and not worth risking early.

---

## Tables that should not be considered for deletion now

- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_unified_strict_train`
- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`
- `species_data.sinr_v3_strict_unified_hits_raw`
- `species_data.sinr_v3_strict_unified_quarantine`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_field_integrity_status_v1`
- `species_data.sinr_occurrence_release_eligibility_v1`
- `species_data.sinr_train_release__strict_only_20260312_194000`

These are either active sources of truth, active audit assets, or active release artifacts.

---

## Practical deletion policy

Use this rule:

- **Keep** if table is still needed for any of:
  - release building,
  - salvage validation,
  - lineage proof,
  - bug-window audit,
  - comparison against strict rebuild

- **Review later** if table is rebuildable and has no unique remaining forensic value

- **Delete only after review** when:
  - replacement is validated,
  - no active process reads it,
  - and retirement is logged in docs + beads

---

## Best next step

Do not delete anything else now.

Instead:

1. complete Claude audit feedback on release builders / override system,
2. finish strict/full governance work,
3. finish salvage / field-family validation,
4. revisit retirement once the future strict-full replacement is in place.
