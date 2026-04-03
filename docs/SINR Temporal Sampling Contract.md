# SINR Temporal Sampling Contract

Date: 2026-03-13
Updated: 2026-03-13
Status: formalized — current code behavior documented, gaps identified
Issue: treekipedia-zk7

## Core principle

`emb_year` should not be the universal temporal anchor for all feature families.

It should mean only:

- the AlphaEarth anchor year actually used for the row's primary AE embedding branch

Other feature families should use their own best temporal strategy.

## Product semantics

### Prediction

Question:

- what is or was growing at a place-time context?

Recommended temporal rule:

- use only information available at or before the target time for dynamic families
- do not silently borrow future annual products just because they are the nearest year

### Recommendation

Question:

- what should be planted or prioritized at a place under a chosen planning horizon?

Recommended temporal rule:

- recommendation may intentionally use a modern or scenario target year
- but that should be explicit and should not be confused with historical occurrence prediction

## Recommended temporal policy by family

### 1. AlphaEarth primary embedding

- key field: `emb_year`
- strategy:
  - exact if `2017 <= observation_year <= 2024`
  - otherwise fallback/clamp to nearest available AE year
- keep explicit flags:
  - `ae_anchor_is_fallback`
  - `ae_anchor_strategy`
  - `obs_minus_emb_year`

### 2. AlphaEarth full temporal stack

- strategy:
  - always sample all available AE years
- these features are not tied to a single `emb_year`

### 3. Observation-year temporal datasets

- examples:
  - MODIS GPP/NPP
  - Dynamic World / year-based land cover
  - VIIRS night lights
  - fire / disturbance accumulations
- strategy:
  - for prediction, use the exact observation year when supported
  - if unsupported, avoid future leakage by using a family-specific fallback policy
  - fallback policy must be explicit per family, not inherited from `emb_year`
- keep explicit fields:
  - `dataset_sample_year_<family>`
  - `dataset_year_is_fallback_<family>`

Recommended fallback hierarchy for prediction:

1. exact year
2. nearest prior supported year
3. explicit static/climatology proxy
4. missing/zero with provenance flag

For some families a future-year fallback may be acceptable in recommendation mode, but that should never be silently mixed into historical prediction labels.

### 4. Static / quasi-static datasets

- examples:
  - DEM
  - many soil layers
  - long-term climatology
- strategy:
  - no year anchoring needed

### 5. Derived / joined families

- examples:
  - land-state
  - introduced/native assertions
  - HILDA joins
  - carbon auxiliary families
- strategy:
  - treat temporal provenance explicitly per family
  - do not pretend they share one universal anchor year

## Current Code Reality vs Contract

This section maps what `unified_gee_sampler_v3.py` actually does for each temporal family against what the contract recommends.

### AlphaEarth primary embedding

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | `emb_year` from BQ occurrence table | AE anchor year | None — `emb_year` IS the AE anchor year |
| Fallback | Clamped to nearest AE year (2017-2024) upstream in BQ | Explicit fallback flags | **YES** — no `ae_anchor_is_fallback` column exists yet |
| Provenance | No flag distinguishing exact vs fallback | `ae_anchor_strategy`, `obs_minus_emb_year` | **YES** — not emitted by extractor |

### AlphaEarth full temporal stack

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Sampling | All 8 years (2017-2024) sampled for every row | All available years | None |
| Year anchoring | Not tied to `emb_year` | Correct | None |

### TerraClimate (tc_vpd_mean, tc_aet_mean, etc.)

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | **Strict**: `observation_year` via `get_temporal_env_for_year(obs_year)` (line 262). **Legacy**: fixed representative year per batch. | `observation_year` | **None in strict** — correct |
| Windowing | +/-2 year window around target year | Exact observation year | **MINOR** — 5yr window is defensible for climate |
| Coverage | 1958-2024 | Any year | None |
| Fallback | Clamped to 1958-2024, no flag emitted | Explicit flag | **YES** — no provenance column |

### Dynamic World

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | **Strict**: `observation_year` (correct). **Legacy**: fixed representative year. | `observation_year` | **None in strict** |
| Coverage | 2015+ (exact year mode) | Observation year when available | None |
| Pre-2015 fallback | ESA WorldCover 2021 remapped to DW classes | Nearest prior year | **YES** — uses future static proxy, no fallback flag |

### MODIS GPP

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | **Strict**: `observation_year` (correct) | `observation_year` | **None** |
| Coverage | 2001-2023 | 2001+ | None |
| Pre-2001 fallback | Returns 0 (patched 2026-03-08) | Zero with provenance flag | **PARTIAL** — returns 0 but no flag |

### MODIS Fire Frequency

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | Cumulative from 2001 to `observation_year` (strict sampler) | Correct | **None in strict** |
| Pre-2001 | Returns 0 | Zero with flag | **PARTIAL** — no flag |

### VIIRS Nighttime Lights

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year source | **Strict**: `observation_year` (correct) | `observation_year` | **None** |
| Coverage | 2012+ | 2012+ | None |
| Pre-2012 | Returns 0 | Zero with flag | **PARTIAL** — no flag |

### MODIS Land Cover (temporal stack)

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Obs year | Uses `observation_year` correctly in `get_temporal_stack_features()` | Correct | None |
| AE year | Uses `ae_year` correctly | Correct | None |

### TerraClimate VPD Delta (temporal stack)

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Delta | `tc_vpd(ae_year) - tc_vpd(obs_year)` | Correct | None |

### Static families (DEM, soil, WorldClim, Hansen, JRC, etc.)

| Aspect | Current Code | Contract | Gap? |
|--------|-------------|----------|------|
| Year anchoring | None (all in `get_static_env_image()`) | No anchoring needed | None |

### Summary of Gaps

The strict sampler (`unified_gee_sampler_v3_strict.py`) is **correctly using `observation_year`** for all temporal env features (line 262). The main remaining gaps are provenance/auditability columns:

| Gap | Severity | Fix Complexity |
|-----|----------|---------------|
| No `ae_anchor_is_fallback` / `ae_anchor_strategy` columns | **Medium** — cannot audit which rows used fallback AE years | Medium — add to extractor output |
| No `obs_minus_emb_year` column | **Low** — computable post-hoc from existing columns | Low — add derived column |
| No per-family fallback flags (zero vs unavailable) | **Low** — implicit in zero values but not auditable | Medium — add provenance columns |
| Dynamic World pre-2015 uses future ESA data without flag | **Low** — affects pre-2015 rows only | Low — add flag column |
| Legacy sampler used fixed representative year per batch | **N/A** — legacy sampler is superseded; strict is correct | None needed |

### Recommended Fix Priority

1. **Add `ae_anchor_is_fallback` boolean** to extractor output (TRUE when `observation_year` outside 2017-2024 AE range, so `emb_year` was clamped).
2. **Add `obs_minus_emb_year` integer** to extractor output (simple `observation_year - emb_year`).
3. **Add `dynamic_world_is_fallback` boolean** for pre-2015 rows using ESA WorldCover proxy.
4. Per-family fallback flags for GPP/fire/VIIRS can wait for the next extraction cycle — the zero values are correct, just not flagged.

## Why this matters

The current estate mixes at least three temporal concepts:

- `observation_year`
- `emb_year`
- fixed all-year stacks

That is manageable only if we stop overloading `emb_year` as if it explains everything.

## Recommendation

- keep `emb_year`
- do **not** set it to NULL just because it differs from `observation_year`
- redefine it narrowly as the AE anchor year used
- add family-specific sampled-year / fallback flags for non-AE temporal features

## Immediate follow-up

Before more model work, the pipeline should expose:

- `ae_anchor_is_fallback`
- `ae_anchor_strategy`
- `obs_minus_emb_year`
- per-family sampled-year fields for key temporal datasets

## Current concrete bug lesson

The year-2000 GPP failure exposed why this contract matters:

- `MODIS/061/MOD17A3HGF` starts in `2001`, not `2000`
- treating it as `2000+` caused empty-collection failures
- the strict sampler has now been patched to treat pre-2001 GPP as unavailable and return a zero proxy rather than silently borrowing 2001 values

That is not the final ideal policy for every family, but it is safer than hidden future leakage.

This will make the master dataset more truthful and should help both training and auditability.
