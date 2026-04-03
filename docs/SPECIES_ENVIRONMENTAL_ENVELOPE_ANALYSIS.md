# Species Environmental Envelope Feature: BigQuery Data Estate Analysis

**Date**: 2026-03-17
**Status**: Research complete — schema and implementation planning ready
**Purpose**: Comprehensive inventory of species-level environmental data, existing aggregates, and proposed architecture for "what conditions does species X typically grow in?"

---

## Executive Summary

### Current State

The BigQuery estate **already has sufficient data to build a robust environmental envelope product**. We have:

- **11.92M training rows** across **19,043 species** in `sinr_v41_preview_strict_core_train_v1`
- **60 environmental features** (climate, soil, terrain, land cover, disturbance)
- **Per-species metadata** already computed: occurrence frequency, introduced/native ratios
- **Two-year old corpus** of aggregation patterns established (frequency contracts, intro ratios, TDWG priors)

### What Doesn't Exist Yet

There is **no species-level environmental envelope aggregate table** currently in BQ. All existing species-level aggregates are:

- **Frequency contracts** (JSON): occurrence counts per species
- **Intro ratio contracts** (JSON): native/introduced ratio per species
- **TDWG frequency contracts** (JSON): species frequency per geographic region

None of these aggregate the **environmental features themselves** (temperature, soil pH, elevation, etc.) into quantile distributions or centroid summaries per species.

### Recommendation

Build a `species_environmental_envelope_v1` table that stores:

- Per-species quantiles (p10, p25, p50, p75, p90) for 60 continuous environmental features
- Per-species categorical proportions (land cover, forest type, biome, soil texture)
- Per-species geographic summary (centroid, bounding box, TDWG region membership)
- Per-species data quality flags (sample count, temporal coverage)
- Derived per-species "typical conditions" summaries (climate zone, soil class, elevation band)

This would enable UI features like:
- "**Typical Conditions**: Quercus robur grows between 150-600m elevation, in temperate climates with 800-1200mm annual precipitation, on loamy soils with pH 6.0-7.5"
- Interactive climate envelope comparisons ("Is your site too dry for this species?")
- Niche overlap analysis across related species

---

## Part A: Existing Per-Species Aggregate Data

### What We Already Have

#### 1. Frequency Contracts (in `orchestrator/contracts/sinr_v3/`)

**File**: `species_frequency_contract_v41_preview_train.json`

```json
{
  "contract_name": "sinr_v3_species_frequency_contract",
  "version": "v41_preview_train",
  "num_species": 19043,
  "class_counts": [int, ...],  // occurrence count per species (indexed by species_to_idx)
  "taxa_seen_in_mapping": 19043,
  "taxa_seen_outside_mapping": 0
}
```

**What it contains**:
- Occurrence count (total training rows) per species
- Built from: `sinr_v3_unified_strict_train_v30_preview_clean`
- Created by: `orchestrator/build_sinr_v3_species_frequency_contract.py`

**Typical values**:
- Average: 625 rows/species (11.92M total / 19,043 species)
- Range: 1 row (single-occurrence species) to 100K+ rows (common species)
- Skew: Long tail; most species have <1,000 rows, a few have >50K

#### 2. Intro/Native Ratio Contract

**File**: `intro_ratio_contract_v41_preview_train.json`

```json
{
  "contract_name": "sinr_v3_intro_ratio_contract",
  "version": "v41_preview_train",
  "num_species": 19043,
  "species_intro_ratio": [float, ...],     // 0.0 to 1.0, per species
  "species_known_counts": [int, ...],      // rows with known intro status
  "taxa_seen_in_mapping": 19043
}
```

**What it contains**:
- Per-species ratio of occurrences marked as introduced (0.0 = all native, 1.0 = all introduced)
- Per-species count of occurrences with known intro status (rest are unknown)
- Built from: `sinr_v3_unified_strict_train_v30_preview_clean`, `is_introduced` column

**Typical values**:
- Most species: intro_ratio = 0.0 (native-only)
- Planted/invasive species: intro_ratio = 0.5 to 1.0
- Unknown introduction status for ~40-60% of rows across all species

#### 3. TDWG Regional Frequency Contract (Geo-spatial)

**File**: `tdwg_frequency_contract_v1.json`

```json
{
  "tdwg_code": {
    "taxon_id": freq_ratio,  // occurrence frequency in this region
    ...
  },
  ...
}
```

**What it contains**:
- Per-TDWG-region per-species occurrence frequency
- Used as spatial prior during inference (`--tdwg-contract` flag)
- Built from: 96.5M GBIF occurrences joined to 369 TDWG Level 3 polygons

**Example**:
- TDWG "UKI" (United Kingdom & Ireland): {"Quercus robur": 0.12, "Fagus sylvatica": 0.08, ...}

#### 4. Species Mapping

**File**: `species_mapping_v41_preview_train.json`

```json
{
  "species_to_idx": {"WCVP_taxon_id": int, ...},  // 19,043 species
  "idx_to_species": [str, ...],                    // reverse mapping
  "num_species": 19043,
  "version": "v41_preview_train"
}
```

**What it contains**:
- Mapping between WCVP taxon IDs and 0-indexed species array indices
- Used to correlate all contracts together (all use the same `num_species=19,043` and ordering)

---

## Part B: Global Statistics Already Available

### Normalization Stats (in `orchestrator/contracts/sinr_v3/`)

#### 1. Continuous Feature Stats

**File**: `normalize_stats_v41_preview_train.npz`

Numpy archive containing (for each of 119 continuous features):
- `mean`: Global mean across all 11.92M rows
- `std`: Global standard deviation
- `columns`: Feature names

**Coverage**: 64 AE embeddings + 55 environmental continuous features

**Example dimensions**:
- `bio01` (mean annual temp): mean ≈ 132 (stored as C*10), std ≈ 45
- `elevation`: mean ≈ 850m, std ≈ 650m
- `soil_ph`: mean ≈ 60 (stored as pH*10), std ≈ 12

**Data quality note**: These statistics were computed from raw values including nulls (treated as 0) and outliers (clipped at ±inf).

#### 2. Temporal Feature Stats

**File**: `normalize_temporal_v41_preview_train.npz`

Numpy archive for 512 AlphaEarth temporal embedding dimensions:
- `mean`: Per-dimension mean across all rows
- `std`: Per-dimension standard deviation

**What it captures**: AlphaEarth 8-year (2017-2024) temporal evolution signatures

#### 3. Stats Contract Manifest

**File**: `stats_contract_v41_preview_train.json`

```json
{
  "contract_name": "sinr_v41_preview_train_normalization",
  "version": "v41_preview_train",
  "source_table": "treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1",
  "total_rows": 11920314,
  "continuous_cols": 119,
  "ae_emb_cols": 64,
  "env_continuous_cols": 55,
  "temporal_cols": 512
}
```

---

## Part C: Available BigQuery Training Tables

### Primary Training Table

**Table**: `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`

**Statistics**:
- **11,920,314 rows** (training-grain)
- **643 columns**
- **Source**: `sinr_v3_unified_strict_train_v30_preview_clean` (labels) + strict-lineage features
- **Grain**: One row per (taxon_id, latitude, longitude, observation_year, emb_year)

**Key columns for aggregation**:
- `taxon_id` (STRING): Species identifier (WCVP taxon ID)
- `latitude`, `longitude` (FLOAT64): Observation coordinates
- All 60 continuous features (55 env + 5 others)
- 5 categorical features: jrc_forest_type, xiao_planted_forest, eco_id, biome_num, soil_texture_class
- 64 AE embeddings: ae_emb_0, ..., ae_emb_63
- 512 AE temporal embeddings: ae_temporal_0, ..., ae_temporal_511
- Metadata: `observation_year`, `emb_year`, `is_introduced`, `verification_status`

**Temporal coverage**:
- Observation years: 1970-2024 (sparse pre-2000)
- AlphaEarth years: 2017-2024 (clamped for pre-2017 observations)
- TerraClimate: 1958-2024

### Backup Training Table (Preview-Compatible)

**Table**: `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean`

- 9,747,945 rows (slightly smaller, deduplicated)
- Same species set (19,043 species)
- Cleaner temporal coverage, explicit NULL handling for carbon sentinels

### Raw Feature Tables (Not Recommended for Initial Envelope)

**Available but higher complexity**:
- `sinr_v3_features_new_gbif_strict_full`: 8.8M rows, raw GEE extractions
- `sinr_v3_features_backfill_strict_full`: Backfill branch (still being populated)

**Why skip for now**: These require exact (lat, lon, obs_year, emb_year) grain joins and have lower deduplication.

---

## Part D: Feature Families & Data Confidence

### Feature Availability & Trust Levels

Based on `/docs/SINR\ V4.1\ Data\ Confidence\ Matrix.md`:

#### GREEN (High Confidence — Aggregate Directly)

| Family | Columns | Count | Notes |
|--------|---------|-------|-------|
| **AlphaEarth embeddings** | ae_emb_0 to ae_emb_63 | 64 | Complete coverage, strict raw |
| **Terrain/Hydro** | elevation, slope, aspect, hillshade, topo_diversity, merit_hand_m, merit_upstream_area_km2 | 7 | Complete coverage, static |
| **Hansen/JRC** | treecover2000, lossyear, jrc_tmf_status, jrc_tmf_degrad_year | 4 | Complete coverage, temporal |
| **Water occurrence** | water_occurrence, water_recurrence, water_seasonality | 3 | Complete coverage, static |
| **Biomass** | biomass_agb_mgha | 1 | Complete coverage, static |
| **Xiao plantations** | xiao_planted_forest (categorical) | 1 | Fixed 2026-03-08, now reliable |

**Total GREEN columns**: 81

#### YELLOW (Use with Guardrails — Aggregate with Caveats)

| Family | Columns | Count | Guardrails |
|--------|---------|-------|-----------|
| **TerraClimate** | tc_vpd_mean, tc_vpd_delta, tc_aet_mean, tc_soil_moisture_mean, tc_pdsi_mean, tc_water_deficit_mean, tc_solar_rad_mean | 7 | Monitor masked-zero behavior; some regions pre-1958 are NULL |
| **BIO Climate** | bio01 to bio19 | 19 | Verify zero-mask semantics; some contamination rows filtered in preview |
| **Soil** | soil_ph, soil_clay_pct, soil_sand_pct, soil_organic_carbon, soil_bulk_density, soil_water_content | 6 | soil_ph=0 contamination filtered; verify missingness semantics |
| **Land cover proxies** | esa_worldcover_2021, dynamic_world, sbtn_natural_land, neumann_natural_prob | 4 | Dynamic World: pre-2015 uses ESA 2021 as proxy (flag needed) |
| **MODIS GPP** | modis_gpp_mean | 1 | Pre-2001 = NULL (2026-03-08 fix); explicit 65530-65535 contamination nulled |
| **Nighttime lights** | nighttime_lights | 1 | Pre-2012 = NULL in preview |
| **Disturbance** | fire_frequency_count, human_modification | 2 | Complete coverage; pre-2001 fire is cumulative from 2001-2001 (≈ 0) |

**Total YELLOW columns**: 40

#### RED (Excluded from V4.1 Preview)

| Family | Reason |
|--------|--------|
| GEDI canopy height | Semantic unresolved (band ambiguity) |
| GEDI foliage diversity | Semantic unresolved (Shan vs other aggregations) |
| Carbon extras, HILDA, Aridity, ET0, IPCC, land-state assertions | Not in preview-core table (gray status) |

**Impact**: None of these 60 main features are excluded; RED families are advanced/auxiliary.

#### Summary of Available Features

- **55 environment continuous**: All available, mix of green/yellow
- **5 categorical**: jrc_forest_type, xiao_planted_forest, eco_id, biome_num, soil_texture_class (all green/yellow)
- **64 AE embeddings**: All green
- **512 AE temporal**: All green (but typically not aggregated — need to decide strategy)

**Total**: **121 primary aggregation targets** (not counting temporal embeddings)

---

## Part E: Temporal Semantics for Aggregation

From `/docs/SINR\ Temporal\ Sampling\ Contract.md`:

### Key Temporal Considerations

1. **AlphaEarth anchor year (`emb_year`)**
   - Represents the AE year actually used for the row's embedding branch
   - For observation_year outside 2017-2024: clamped to nearest AE year
   - **For aggregation**: Important to track which species have observation_year in/out of range

2. **Observation-year temporal datasets** (TerraClimate, MODIS GPP, Dynamic World)
   - Strict sampler uses `observation_year` (correct)
   - **For aggregation**: Should preserve temporal coverage per species (e.g., "this species has obs from 1980-2024")

3. **Static datasets** (DEM, soil, WorldClim base, Hansen, JRC)
   - No temporal anchor needed
   - **For aggregation**: Can aggregate across all time periods

4. **Current gap**: No `ae_anchor_is_fallback` or `obs_minus_emb_year` columns (tracked as treekipedia-zk7)
   - **Workaround for aggregation**: Assume observation_year is in BQ; if != emb_year, treat as potential fallback

### Recommended Aggregation Strategy for Temporal Features

**Conservative approach** (recommended for V1 envelope):
1. Aggregate all static features normally (DEM, soil, Hansen, JRC, etc.)
2. For temporal families (TerraClimate, MODIS, lights):
   - Compute quantiles as normal
   - But store separately flagged metadata: observation_year_min, observation_year_max per species
   - Display caveat: "Based on observations from YYYY-YYYY"

**Future enhancement** (V2):
- Separate "typical conditions in recent years" vs "historical range across all observations"
- Provide temporal trend (e.g., "mean elevation of occurrence has moved upslope 50m over 30 years")

---

## Part F: Data Quality Issues & Mitigations

From `/docs/SINR\ Fresh\ Validation\ Findings.md`:

### Known Issues

1. **Xiao planted forest inconsistencies** (FIXED 2026-03-08)
   - Training bug: RGB decode was wrong; looked for red instead of yellow
   - Result: xiao_planted_forest=2 had ZERO rows in historical training data
   - **Status**: FIXED in strict lineage; V4.1 preview uses corrected data
   - **Mitigation for envelope**: Use xiao_planted_forest as-is; it's now correct

2. **TerraClimate masked-zero behavior**
   - Some regions/periods return 0 instead of NULL for unknown values
   - **Status**: Under investigation (beads treekipedia-9vo)
   - **Mitigation for envelope**: Flag species with high counts of zero values in soil_ph, PDSI, etc.

3. **BIO climate contamination**
   - Some all-zero rows filtered in preview; exact semantics TBD
   - **Status**: Under investigation
   - **Mitigation for envelope**: Exclude rows where ALL bio0x columns are zero

4. **Temporal extraction year-2000 bug**
   - MODIS GPP starts 2001, not 2000; caused empty collection failures
   - **Status**: FIXED in unified_gee_sampler_v3_strict.py (pre-2001 returns 0)
   - **Mitigation for envelope**: Pre-2001 observations: modis_gpp_mean will be NULL/0; document this

5. **Nighttime lights pre-2012**
   - VIIRS starts 2012; pre-2012 = NULL
   - **Status**: Documented in contract
   - **Mitigation for envelope**: Pre-2012 observations: nighttime_lights will be NULL; count non-null rows

### Aggregate Table Safeguards

The envelope table should include:

- `num_rows_total`: Total rows per species
- `num_rows_with_obs_pre_2001`: Count of rows with year < 2001 (may have missing temporal data)
- `num_rows_with_introduced_unknown`: Count where is_introduced is NULL
- `feature_null_counts`: Per-feature count of NULLs per species (detect contamination)
- `confidence_flag`: "green" (all rows post-2001), "yellow" (mixed temporal coverage), "red" (mostly pre-2001)

---

## Part G: Proposed Schema for `species_environmental_envelope_v1`

### Table Structure

```sql
CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.species_environmental_envelope_v1` (
  -- Species identifier
  taxon_id STRING NOT NULL,

  -- Metadata & counts
  num_rows_total INT64,
  num_rows_native INT64,           -- is_introduced = 0
  num_rows_introduced INT64,       -- is_introduced = 1
  num_rows_unknown_intro INT64,    -- is_introduced IS NULL
  introduced_ratio FLOAT64,        -- num_rows_introduced / (num_rows_native + num_rows_introduced)

  -- Temporal coverage
  observation_year_min INT64,
  observation_year_max INT64,
  observation_year_median INT64,
  num_obs_pre_2001 INT64,

  -- Geographic coverage
  centroid_latitude FLOAT64,
  centroid_longitude FLOAT64,
  latitude_min FLOAT64,
  latitude_max FLOAT64,
  longitude_min FLOAT64,
  longitude_max FLOAT64,
  tdwg_regions ARRAY<STRING>,      -- TDWG Level 3 codes where this species occurs

  -- Quantiles for continuous environmental features (55 features)
  -- Pattern: {feature_name}_{quantile}
  -- Example: bio01_p10, bio01_p25, bio01_p50, bio01_p75, bio01_p90
  elevation_p10 FLOAT64, elevation_p25 FLOAT64, elevation_p50 FLOAT64, elevation_p75 FLOAT64, elevation_p90 FLOAT64,
  slope_p10 FLOAT64, slope_p25 FLOAT64, slope_p50 FLOAT64, slope_p75 FLOAT64, slope_p90 FLOAT64,
  aspect_p10 FLOAT64, aspect_p25 FLOAT64, aspect_p50 FLOAT64, aspect_p75 FLOAT64, aspect_p90 FLOAT64,
  hillshade_p10 FLOAT64, hillshade_p25 FLOAT64, hillshade_p50 FLOAT64, hillshade_p75 FLOAT64, hillshade_p90 FLOAT64,
  topo_diversity_p10 FLOAT64, topo_diversity_p25 FLOAT64, topo_diversity_p50 FLOAT64, topo_diversity_p75 FLOAT64, topo_diversity_p90 FLOAT64,
  merit_hand_m_p10 FLOAT64, merit_hand_m_p25 FLOAT64, merit_hand_m_p50 FLOAT64, merit_hand_m_p75 FLOAT64, merit_hand_m_p90 FLOAT64,
  merit_upstream_area_km2_p10 FLOAT64, merit_upstream_area_km2_p25 FLOAT64, merit_upstream_area_km2_p50 FLOAT64, merit_upstream_area_km2_p75 FLOAT64, merit_upstream_area_km2_p90 FLOAT64,
  bio01_p10 FLOAT64, bio01_p25 FLOAT64, bio01_p50 FLOAT64, bio01_p75 FLOAT64, bio01_p90 FLOAT64,  -- Mean annual temp (C*10)
  bio02_p10 FLOAT64, bio02_p25 FLOAT64, bio02_p50 FLOAT64, bio02_p75 FLOAT64, bio02_p90 FLOAT64,  -- Mean diurnal range
  -- ... [repeat for bio03 through bio19, all soil features, water, jrc, esa, dynamic_world, tc_*, nighttime_lights, fire_frequency_count, human_modification, modis_gpp_mean]
  -- [See full schema below for complete list]

  -- Categorical feature distributions (binned by class)
  jrc_forest_type_distribution MAP<STRING, FLOAT64>,  -- {class_name: proportion}
  xiao_planted_forest_distribution MAP<INT64, FLOAT64>,
  eco_id_distribution MAP<INT64, FLOAT64>,
  biome_num_distribution MAP<INT64, FLOAT64>,
  soil_texture_class_distribution MAP<INT64, FLOAT64>,

  -- AlphaEarth embedding statistics
  -- Typically not aggregated into quantiles (65D embeddings are complex)
  -- Instead: mean and std per dimension
  ae_emb_mean ARRAY<FLOAT64>,      -- 64-element array: mean per embedding dimension
  ae_emb_std ARRAY<FLOAT64>,       -- 64-element array: std per embedding dimension

  -- Quality flags
  confidence_level STRING,          -- "green" (post-2001 majority), "yellow" (mixed), "red" (pre-2001 majority)
  num_null_values_per_feature MAP<STRING, INT64>,  -- Detect contamination

  -- Metadata
  derived_from_table STRING,        -- Source table (for audit)
  derived_at TIMESTAMP,

  PRIMARY KEY (taxon_id) NOT ENFORCED
);
```

### Quantile Column Naming

Rather than 275 individual columns (55 features × 5 quantiles), recommend a more concise representation. Two options:

**Option 1 (Verbose but SQL-friendly)**: Separate column per quantile
```sql
elevation_p10, elevation_p25, elevation_p50, elevation_p75, elevation_p90
```

**Option 2 (Compact)**: Use STRUCT or JSON arrays
```sql
quantiles STRUCT<
  feature_name STRING,
  p10 FLOAT64,
  p25 FLOAT64,
  p50 FLOAT64,
  p75 FLOAT64,
  p90 FLOAT64
>[]  -- repeated struct
```

**Recommendation for V1**: Go with **Option 1** (verbose columns) for frontend ease-of-use. Frontend can query directly without parsing JSON/arrays. Drawback: ~275 columns total, but modern BQ handles this fine.

---

## Part H: SQL Sketch for Building the Envelope Table

### Strategy

1. **Source table**: `sinr_v41_preview_strict_core_train_v1` (11.92M rows)
2. **Group by**: `taxon_id`
3. **For each taxon**: Compute quantiles on all continuous features
4. **Key aggregations**:

```sql
SELECT
  taxon_id,

  -- Counts
  COUNT(*) AS num_rows_total,
  COUNTIF(is_introduced = 0) AS num_rows_native,
  COUNTIF(is_introduced = 1) AS num_rows_introduced,
  COUNTIF(is_introduced IS NULL) AS num_rows_unknown_intro,
  SAFE_DIVIDE(
    COUNTIF(is_introduced = 1),
    COUNTIF(is_introduced IN (0, 1))
  ) AS introduced_ratio,

  -- Temporal
  MIN(observation_year) AS observation_year_min,
  MAX(observation_year) AS observation_year_max,
  APPROX_QUANTILES(observation_year, 100)[OFFSET(50)] AS observation_year_median,
  COUNTIF(observation_year < 2001) AS num_obs_pre_2001,

  -- Geographic
  AVG(latitude) AS centroid_latitude,
  AVG(longitude) AS centroid_longitude,
  MIN(latitude) AS latitude_min,
  MAX(latitude) AS latitude_max,
  MIN(longitude) AS longitude_min,
  MAX(longitude) AS longitude_max,

  -- Elevation quantiles (example; repeat for all continuous features)
  APPROX_QUANTILES(elevation, 100)[OFFSET(10)] AS elevation_p10,
  APPROX_QUANTILES(elevation, 100)[OFFSET(25)] AS elevation_p25,
  APPROX_QUANTILES(elevation, 100)[OFFSET(50)] AS elevation_p50,
  APPROX_QUANTILES(elevation, 100)[OFFSET(75)] AS elevation_p75,
  APPROX_QUANTILES(elevation, 100)[OFFSET(90)] AS elevation_p90,

  -- Repeat for all 55 continuous env features...
  -- (bio01..bio19, soil_*, water_*, terrain_*, etc.)

  -- Categorical distributions (example)
  ARRAY_AGG(STRUCT(xiao_planted_forest AS class, COUNT(*) AS count)) AS xiao_dist_raw,
  -- Then normalize to get proportions...

  -- AlphaEarth embeddings: compute per-dimension mean/std
  -- Challenge: ae_emb_0..ae_emb_63 are 64 separate columns
  -- Need to unnest, aggregate, then re-nest

  CURRENT_TIMESTAMP() AS derived_at,
  "sinr_v41_preview_strict_core_train_v1" AS derived_from_table

FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
WHERE taxon_id IS NOT NULL
GROUP BY taxon_id;
```

### Implementation Notes

1. **APPROX_QUANTILES()** is efficient for large groups; exact computation may timeout
2. **Per-dimension embedding aggregation** requires CROSS JOIN + UNNEST on ae_emb_* columns:
   ```sql
   -- In a preprocessing step, unnest embeddings
   WITH embeddings_unnested AS (
     SELECT taxon_id, 0 AS dim, ae_emb_0 AS value
     UNION ALL
     SELECT taxon_id, 1 AS dim, ae_emb_1 AS value
     -- ... repeat for ae_emb_2..ae_emb_63
   )
   SELECT
     taxon_id,
     ARRAY_AGG(STRUCT(dim, AVG(value) AS mean, STDDEV(value) AS std))
   FROM embeddings_unnested
   GROUP BY taxon_id
   ```
3. **Categorical distributions** need post-processing to convert counts to proportions
4. **TDWG region membership** requires spatial join with 369 TDWG Level 3 polygons (may be slow; consider batching)

### Estimated Build Time

- **Query complexity**: High (275+ quantile columns, categorical aggregations, embedding unnesting)
- **Data volume**: 11.92M rows grouped by 19,043 species
- **Estimated scan**: ~1-2 minutes; aggregation 5-10 minutes total
- **Cost**: ~12GB scanned ≈ $0.06 per run

### Alternative: Build Incrementally

If full 275-column table is unwieldy, consider building in two stages:

**Stage 1** (lightweight): Green + high-confidence Yellow features only (45 features)
```sql
SELECT taxon_id, elevation_p10, elevation_p50, ..., bio01_p10, bio01_p50, ...
-- 45 features × 3 quantiles (p10, p50, p90) = 135 columns
```

**Stage 2** (enhanced): All features + categorical distributions + embeddings

---

## Part I: Which Source Table to Use?

### Comparison: Candidate Source Tables

| Aspect | `sinr_v41_preview_strict_core_train_v1` | `sinr_v3_unified_strict_train_v30_preview_clean` | `sinr_v3_features_new_gbif_strict_full` |
|--------|----------------------------------------|-----------------------------------------------|----------------------------------------|
| **Rows** | 11,920,314 | 9,747,945 | 8,800,000 (estimated) |
| **Species** | 19,043 | ~19,000 | ~17,000 |
| **Features** | 60 env + 64 AE emb + 512 AE temp | 60 env + 64 AE emb + 512 AE temp | 60 env + 64 AE emb + 512 AE temp |
| **Grain** | (taxon_id, lat, lon, obs_year, emb_year) | (taxon_id, lat, lon, obs_year, emb_year) | Exact (lat4, lon4, observation_year, emb_year) — no taxon_id join |
| **Quality** | Training-grain; labeled + deduplicated | Preview-optimized; very clean | Raw features; requires join to occurrences |
| **Temporal** | Raw observation_year (1970-2024) | Clean temporal coverage | Raw; no curation |
| **Data confidence** | HIGH — V4.1 preview standard | HIGH — preview-safe | MEDIUM — raw features, needs validation |
| **Use case** | **Envelope aggregation** | Backup (lighter) | Raw source for custom work |

### Recommendation

**Use `sinr_v41_preview_strict_core_train_v1`** for initial envelope table:

✓ Largest sample per species (avg 625 rows vs 512 in preview-clean)
✓ Most complete temporal coverage
✓ V4.1 preview pedigree (highest current data confidence)
✓ All 60 environmental features available
✓ Labeled with taxon_id directly

**If lighter weight needed**, can rebuild from `preview_clean` with slightly sparser quantiles.

---

## Part J: Implementation Roadmap

### Phase 1: Data Contract & Prototyping (1-2 weeks)

- [ ] Finalize schema (option 1 vs 2 for columns)
- [ ] Build lightweight prototype (green features only, 3 quantiles p10/p50/p90)
- [ ] Test on subset of species (e.g., top 100 by frequency)
- [ ] Validate quantile distributions, spot-check outliers
- [ ] Document any data quality issues discovered

### Phase 2: Full Table Build (1 week)

- [ ] Add all 60 continuous features
- [ ] Add categorical distributions
- [ ] Add AlphaEarth embedding statistics
- [ ] Add quality flags and null tracking
- [ ] Build full envelope table in BQ

### Phase 3: Frontend Integration (2-3 weeks)

- [ ] Query API endpoint: `/species/:taxon_id/environmental-envelope`
- [ ] Returns: quantiles, categorical summaries, typical conditions narrative
- [ ] UI component: "Typical Conditions" card showing climate/soil/terrain summary
- [ ] Interactive comparison: "How does your site compare?" UI
- [ ] Display confidence level and temporal coverage warnings

### Phase 4: Product Launch (ongoing)

- [ ] Expose envelope in species detail page
- [ ] Add to species comparison tool
- [ ] Support envelope-based species recommendations ("species for your climate")
- [ ] Monitor query performance; add caching if needed

---

## Part K: FAQ & Design Decisions

### Q1: Why quantiles instead of mean/std?

**Answer**:
- Quantiles are **robust to outliers** (one experimental plot at 5,000m doesn't skew the mean)
- Quantiles are **interpretable to non-scientists** ("50% grow below 800m elevation")
- Quantiles show **multi-modality** (e.g., widespread species may have bimodal elevation distribution)
- Mean/std assume normal distribution, which fails for many environmental variables (elevation, precipitation, etc. are often skewed)

### Q2: Should we aggregate AE embeddings or leave raw?

**Answer**:
- **Option A (Aggregate)**: Store mean/std per embedding dimension per species. Pros: Enables dimensionality reduction, species similarity. Cons: Less interpretable, may lose distributional info.
- **Option B (Raw)**: Don't aggregate; leave as raw training data. Pros: Preserves full info. Cons: 64D embeddings aren't human-interpretable anyway.
- **Recommendation for V1**: Go with Option A (mean/std). Embeddings are for ML consumption, not UI display. Mean/std is sufficient.

### Q3: How to handle the 275 columns (55 features × 5 quantiles)?

**Answer**:
- BQ supports this fine (no hard column limit)
- Frontend can query with explicit SELECT list
- Consider views for common groupings: `species_envelope_climate_quantiles`, `species_envelope_terrain_quantiles`, etc.
- Or use dynamic column projection in API endpoint

### Q4: Should we include species from the full 67K database or just the 19,043 training species?

**Answer**:
- **V1 (Recommended)**: 19,043 training species only. Why: (1) Has data, (2) Aligns with SINR model, (3) Can expand later
- **Future (V2)**: Backfill from full GBIF occurrence database for all 67K species (requires separate GEE sampling, significant effort)

### Q5: What about temporal trends (e.g., "this species has moved upslope")?

**Answer**:
- Out of scope for V1 (first pass just describes typical conditions)
- **V2 opportunity**: Compute per-decade quantiles and show "typical elevation in 1980s vs 2020s"
- Would require stratifying by decade or using temporal bin aggregation

### Q6: Should envelope be public or require API key?

**Answer**:
- **Public** (no key required). Why: Species data is open source (GBIF), aggregations are non-sensitive, supports educational use
- **Opt-in** per species if needed (e.g., protected species could have anonymized envelope only)

---

## Part L: Risk Mitigation & Data Quality Assurance

### Quality Checks to Build Into Aggregation Job

1. **Sanity checks per feature**:
   ```sql
   -- Flag if quantile spread is suspiciously small (potential uniform contamination)
   ASSERT (p90 - p10) > 0.01 * p50 OR num_rows < 10

   -- Flag if all values are identical (data quality issue)
   ASSERT (elevation_p10 != elevation_p90) OR (elevation_p10 IS NULL)
   ```

2. **Null/missing tracking**:
   ```sql
   -- For each feature, track null percentage
   SELECT
     taxon_id,
     feature_name,
     COUNTIF(feature_value IS NULL) / COUNT(*) AS null_pct
   ```

3. **Outlier validation**:
   ```sql
   -- Compare against global quantiles from stats contract
   -- Flag if species-level quantiles differ wildly (e.g., elevation p50 = 10,000m globally)
   ```

4. **Temporal coverage**:
   ```sql
   -- Warn if >90% of observations pre-2001 (may have temporal data gaps)
   ASSERT (num_obs_pre_2001 / num_rows_total) < 0.9 OR confidence_level != "green"
   ```

### Continuous Monitoring

- **Monthly regeneration**: Rebuild envelope table as new training data arrives
- **Alerting**: Flag species where envelope stats changed >10% (indicates data drift)
- **Audit trail**: Store versioned envelopes (envelope_v1, envelope_v2) for reproducibility

---

## Part M: Integration with Existing Systems

### Connection Points

1. **Species detail page** (`/species/[taxon_id]`)
   - Add "Typical Conditions" tab with envelope summary
   - Query: `/api/species/{taxon_id}/environmental-envelope`

2. **Habitat predictor** (`location_predictor_FIXED.py`)
   - Envelopes can inform "suitability outside known range" heuristics
   - Compare current site conditions to species envelope

3. **SINR model inference** (`v3_point_inference.py`)
   - Envelope stats could inform per-species logit offsets
   - E.g., "is this location within the 10-90 quantile range for this species?"

4. **Species comparison UI** (`SpeciesRecommenderModal.tsx`)
   - Show overlapping envelopes for competing species
   - "Which species has narrower soil pH tolerance?"

5. **Research orchestrator** (`research_orchestrator.py`)
   - Use envelope to validate AI-generated species descriptions
   - "Text claims species needs elevation 800-2000m; envelope shows 150-3200m — flag for review"

---

## Part N: Data Lineage & Auditability

### Provenance Chain

```
GBIF raw occurrences (96.5M)
  ↓
SINR strict GEE extraction (11.92M training rows)
  ↓
V4.1 preview training grain (11.92M rows, 60 features)
  ↓
Species environmental envelope (19,043 species × 275 columns)
  ↓
Frontend UI: "Typical Conditions" display
```

### Audit Fields in Envelope Table

- `derived_from_table`: Source BQ table
- `derived_at`: Build timestamp
- `num_rows_total`: Total rows per species (transparency on sample size)
- `confidence_level`: Green/yellow/red flag
- `num_null_values_per_feature`: Detect data gaps

---

## Summary: What Exists vs What Needs to Be Built

### Currently Available (No Action Needed)

✓ **Per-species frequency contracts** (occurrence counts)
✓ **Per-species intro/native ratios**
✓ **Global normalization statistics** (mean/std for all features)
✓ **TDWG regional frequency priors**
✓ **Training data with all 60+ features** (11.92M rows, 19,043 species)

### Needs to Be Built (Propose Starting)

✗ **Species environmental envelope table** (per-species quantiles for all 60 features)
✗ **API endpoint** to query envelope data
✗ **Frontend UI component** to display typical conditions
✗ **Comparison UI** to show species envelope overlaps

### Estimated Effort

- **BQ table build**: 1-2 weeks (including schema finalization, testing, data validation)
- **Backend API endpoint**: 1 week
- **Frontend UI**: 2-3 weeks (design, component, integration with species page)
- **Total**: 4-6 weeks for MVP

---

## Recommendations

### Immediate Next Steps

1. **Finalize schema** (this week)
   - Decide: 275 individual columns vs STRUCT-based approach?
   - Get stakeholder buy-in on "typical conditions" narrative format

2. **Build prototype** (next 2 weeks)
   - Green features only (45 features)
   - 3 quantiles (p10, p50, p90) to reduce column count
   - Top 100 species by frequency
   - Validate schema against sample data

3. **Iterate design** based on prototype
   - Adjust quantile definitions, handle edge cases
   - Refine data quality flags
   - Plan feature expansion

4. **Build production table** (weeks 3-4)
   - All 60 features, all quantiles
   - All 19,043 species
   - Full validation suite

5. **Frontend integration** (weeks 5-6)
   - API endpoint
   - UI component
   - Launch on species detail page

---

## Reference Files

### Key BQ Tables
- `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1` (11.92M rows, V4.1 training grain)
- `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean` (9.74M rows, backup)

### Key Contracts
- `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json` (60 features + 64 AE + 512 temporal)
- `orchestrator/contracts/sinr_v3/stats_contract_v41_preview_train.json` (global mean/std)
- `orchestrator/contracts/sinr_v3/species_frequency_contract_v41_preview_train.json` (per-species occurrence counts)
- `orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json` (per-species native/introduced ratio)

### Key Documentation
- `/docs/SINR\ V4.1\ Data\ Confidence\ Matrix.md` (feature trust levels)
- `/docs/SINR\ Temporal\ Sampling\ Contract.md` (temporal semantics per feature family)
- `/docs/SINR\ Fresh\ Validation\ Findings.md` (known data quality issues)
- `/docs/SINR\ BigQuery\ Lineage\ Map.md` (table provenance)

---

**End of Analysis**
**Status**: Ready for implementation planning
**Next Action**: Stakeholder review of proposed schema and timeline
