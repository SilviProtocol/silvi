# SINR V4.1 Data Confidence Matrix

Date: 2026-03-15
Audience: agents and humans working on SINR `V4.1 preview` and beyond
Status: active reference document for the retired `V4.1` preview baseline

## Purpose

This document is the blunt trust boundary for `V4.1 preview`.

Use it to answer:

- which feature families are trusted enough to include now,
- which families are usable only with guardrails,
- which families must stay out of the preview,
- and what exact work moves a family from `exclude` to `preview-safe` to `full strict`.

If work widens the preview scope, update this matrix and the relevant beads issue in the same session.

## Program Framing

- `V3` = frozen benchmark family
- `V4.0` = lineage / semantic cleanup
- `V4.1 preview` = `new_gbif` strict-core only
- `V4.2+` = full strict estate after backfill and family canonicalization

## Current Anchors

Canonical repaired `new_gbif` strict source:

- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`

Current preview-core table:

- `species_data.sinr_v41_preview_strict_core_v1`

Current preview training table:

- `species_data.sinr_v41_preview_strict_core_train_v1`

Current preview-core table facts:

- `8,392,893` rows
- `643` columns
- `445,595` rows excluded relative to `completed_v1`
- `gedi_canopy_height_m` excluded
- `gedi_foliage_height_div` excluded
- explicit GPP high codes (`>=65530`) nulled out of preview
- `nighttime_lights` pre-2012 nulled in preview
- obvious `BIO` / soil contamination rows filtered out

Current training-grain facts:

- `11,920,314` rows
- includes `taxon_id`
- labels/meta come from `sinr_v3_unified_strict_train_v30_preview_clean`
- features come from repaired strict lineage `...completed_v1`

Current training artifacts:

- `orchestrator/contracts/sinr_v3/normalize_stats_v41_preview_train.npz`
- `orchestrator/contracts/sinr_v3/normalize_temporal_v41_preview_train.npz`
- `orchestrator/contracts/sinr_v3/stats_contract_v41_preview_train.json`
- `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`

## Confidence Classes

- `green` — include in `V4.1 preview` by default
- `yellow` — include in `V4.1 preview` only with explicit guardrails / provenance / filters
- `red` — exclude from `V4.1 preview`
- `gray` — not canonical strict raw; separate rebuild or policy decision required before full strict use

## Family Matrix

| Family | Current source / path | V4.1 status | Confidence | Current rule | Next step | Beads |
|---|---|---|---|---|---|---|
| AE embeddings | strict raw `completed_v1` | include | green | use directly | freeze preview contract | `treekipedia-bfc` |
| Terrain / hydro | strict raw `completed_v1` | include | green | use directly | none beyond contract freeze | `treekipedia-bfc` |
| Hansen / JRC water / JRC forest | strict raw `completed_v1` | include | green | use directly | none beyond contract freeze | `treekipedia-bfc` |
| Biomass AGB / SOC / topo / human modification / eco ids | strict raw `completed_v1` | include | green | use directly | none beyond contract freeze | `treekipedia-bfc` |
| Xiao | repaired in strict lineage | include | green | use `completed_v1`; do not reintroduce old raw Xiao | keep release builders sourced from repaired lineage | `treekipedia-cl3` |
| TerraClimate family | strict raw `completed_v1` | include with guards | yellow | keep in preview; monitor masked-zero behavior | verify family-level zero/missing semantics | `treekipedia-9vo` |
| BIO climate family | strict raw `completed_v1` | include with guards | yellow | preview filters obvious all-zero contamination rows | verify zero-mask semantics per family | `treekipedia-9vo` |
| Soil family | strict raw `completed_v1` | include with guards | yellow | preview filters `soil_ph=0` contamination rows | verify per-band missingness semantics | `treekipedia-9vo` |
| Dynamic World / ESA proxy | strict raw `completed_v1` | include with guards | yellow | use corrected ESA remap; treat pre-2015 as proxy | add explicit proxy provenance flag | `treekipedia-9vo` |
| MODIS GPP | strict raw `completed_v1` | include with guards | yellow | keep pre-2001 NULL semantics; null explicit `65530-65535` contamination; do not blanket-null `30000-49999` | finish source-doc + distribution validation and bake final lineage rule | `treekipedia-9vo` |
| Nighttime lights | strict raw `completed_v1` | include with guards | yellow | null pre-2012 in preview | decide whether to add explicit availability flag | `treekipedia-9vo` |
| GEDI canopy height | strict raw contaminated by historical mosaic misuse | exclude | red | excluded from preview and V4.7 merged strict-core | 2026-03-18 probe confirmed current raw values in both branches are mostly old-mosaic contamination; repair via GEDI-only coord-grain re-extract (`rh-98-a0 / p95` + `countf`) before any reintroduction | `treekipedia-c5q`, `treekipedia-1i5` |
| GEDI foliage diversity | strict raw semantically wrong for current model-facing field | exclude | red | excluded from preview and V4.7 merged strict-core | current `shan` is a heterogeneity statistic, not raw FHD; if foliage returns, re-extract `mean`/`median` from the FHD asset instead of reusing `shan` | `treekipedia-c5q`, `treekipedia-1i5` |
| Carbon extras / productivity extras | external/manual / preview-backed | exclude | gray | keep out of preview | canonicalize or fail closed for full strict | `treekipedia-8b2` |
| HILDA | external/manual / preview-backed | exclude | gray | keep out of preview | canonicalize or fail closed for full strict | `treekipedia-8b2` |
| Aridity / ET0 / IPCC | external/manual / preview-backed | exclude | gray | keep out of preview unless rebuilt with provenance | canonicalize or fail closed for full strict | `treekipedia-8b2` |
| Land-state assertions | external/manual / preview-backed | exclude | gray | keep out of preview | canonicalize or fail closed for full strict | `treekipedia-8b2` |
| Introduced/native joins | external/manual / preview-backed | exclude from feature surface | gray | use only where explicitly needed for labels/meta, not as trusted strict features | canonicalize or provenance-tag before full strict use | `treekipedia-8b2` |

## What The Preview Actually Means

`V4.1 preview` is not “the whole pipeline is done.”

It means:

- we have a cleaned, repaired, accounted-for `new_gbif` strict lineage,
- we are using only the portion of that lineage we currently trust,
- and we are explicitly excluding unresolved families instead of pretending they are solved.

This is a feature, not a compromise.

## Temporal Scope In Plain English

`V4.1 preview` is **not** a fully temporalized multi-source model.

Current design:

- the actual temporal branch is AE-only:
  - `2017-2024` AlphaEarth sequence,
  - `512D` temporal tensor,
  - intended to capture multi-year trend signatures / land-cover evolution.
- non-AE time-related families currently enter as scalar or year-matched snapshot features, not as their own temporal sequences.

That means `V4.1 preview` can learn a strong AE-based trend signature, but it is **not yet** modeling richer temporal history such as:

- disturbance chronology,
- agriculture / crop-cycle rhythm,
- long-run land-use history,
- repeated fire regime trajectories,
- or soil-degradation trajectories.

This is intentional for `V4.1`.

Future expansion is tracked in:

- `treekipedia-2t9` — design `V4.2+` multi-source temporal intelligence stack.

## Iterative Path

### V4.1a — Preview data contract

Goal:

- freeze confidence boundaries,
- freeze preview-core table,
- recompute normalization stats,
- freeze feature contract.

Owned by:

- `treekipedia-bfc`

Exit criteria:

- confidence matrix updated,
- stats regenerated from `sinr_v41_preview_strict_core_train_v1`,
- feature contract versioned,
- trainer-ready grain confirmed (`taxon_id` present).

### V4.1b — Preview training + benchmark

Goal:

- train preview model on preview-core table,
- benchmark against frozen `V3`,
- compare only within the reduced-scope contract.

Owned by:

- `treekipedia-bfc`

Exit criteria:

- training log path,
- stats / contract references,
- benchmark results against `V3` documented.

### V4.1c — Optional release formalization

Goal:

- if downstream systems need a versioned release artifact, rebuild strict / hybrid release outputs from the repaired lineage.

Owned by:

- `treekipedia-cl3`

Exit criteria:

- release registry entries rebuilt from `completed_v1` or later preview-core lineage,
- stale-source release artifacts superseded.

### V4.2 — Full strict estate

Goal:

- finish backfill strict extraction,
- merge `new_gbif` + backfill into the full strict unified table,
- keep unresolved families fail-closed unless canonicalized.

Owned by:

- `treekipedia-bj7`
- `treekipedia-csc`

Exit criteria:

- backfill extraction complete,
- full strict unified table built and validated.

### V4.3 — Family expansion

Goal:

- reintroduce excluded families only after they are genuinely canonical.

Owned by:

- `treekipedia-9vo`
- `treekipedia-8b2`
- `treekipedia-2t9`

Exit criteria:

- family-specific validation complete,
- provenance / masking semantics settled,
- confidence matrix updated from `red/gray` to `yellow/green` where justified.

## Operating Rules

1. Do not widen `V4.1 preview` without updating this matrix.
2. Do not move a family from `red/gray` to `yellow/green` without a beads-linked reason.
3. Do not treat “present in strict raw” as the same as “trusted for preview”.
4. Do not block `V4.1 preview` on backfill completion.
5. Do not claim the full SINR pipeline is complete until `V4.2+` is done.

## Current Next Actions

1. Export local training shards from `species_data.sinr_v41_preview_strict_core_train_v1`
2. Train the `V4.1 preview` model
3. Benchmark `V4.1 preview` against frozen `V3`
4. Rebuild formal release artifacts if downstream consumers need them
5. Keep backfill extraction running toward `V4.2`
