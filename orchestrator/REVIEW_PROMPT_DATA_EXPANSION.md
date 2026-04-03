# Treekipedia SINR v3 — Data Expansion & Temporal Stack Design Review

## Request

We're seeking expert critique on our plan to **triple the training data** for our species prediction model and add a **temporal indicator stack** that teaches the model to assess land use reliability across time. We want feedback on:

1. The temporal stack feature design — are we capturing the right signals? Missing anything?
2. The approach of letting the model learn temporal reliability vs. hardcoded filtering rules
3. BigQuery/GEE pipeline architecture for 14.2M new points
4. Any landmines we haven't seen
5. Suggestions for what else to try

---

## System Overview

**Treekipedia** predicts which tree species are present at any location on Earth. Given a lat/lon, we sample a 64-D AlphaEarth satellite embedding + ~60 environmental features from Google Earth Engine, feed them through a neural network, and output a probability for each of 35,561 tree species.

The architecture is based on Cole et al.'s **SINR** (Spatial Implicit Neural Representation) with our modifications: gated satellite/environment fusion, entity embeddings for categorical features, and a planted logit boost for plantation detection.

**The model is already trained and working (v2.2).** This review is about the next step: massively expanding the training data and adding temporal context features for v3.

---

## Current State: v2.2 (Baseline)

### Training Data

| Metric | Value |
|--------|-------|
| Training rows | 7,899,973 |
| Validation rows | 415,831 |
| Species | 35,561 (subspecies merged from 43,566) |
| Features | 130 columns (64 AlphaEarth + 56 continuous env + 5 categorical + is_introduced + weights) |
| Data composition | 90.3% USDA FIA forest inventory, 9.7% GBIF |
| Geographic bias | Heavy Europe/North America. Tropics underrepresented. |
| Species distribution | Extreme long-tail. Median 6 occurrences. 60% have <10 samples. 20% singletons. |
| Dedup key | (taxon_id, lat4dp, lon4dp, emb_year) — multi-year obs at same pixel are DIFFERENT rows |

### v2.2 Training Results (12 epochs, best = epoch 8)

| Epoch | train_loss | val_loss | top-10 | top-50 |
|-------|-----------|----------|--------|--------|
| 1 | 0.021898 | 0.007018 | 48.90% | 85.41% |
| 4 | 0.008712 | 0.005403 | 57.79% | 89.29% |
| **8** | **0.007624** | **0.005286** | **59.34%** | **90.08%** |
| 12 | 0.007163 | 0.005514 | 59.91% | 90.34% |

Best model = epoch 8 by val_loss. Mild overfitting after that (train_loss keeps dropping, val_loss rises). 9,713,042 parameters.

### v2.2 Architecture (model_version=4)

```
Input: 64-D AlphaEarth + 56 continuous env + 5 categorical embeddings + is_introduced

                    ┌──────────────────────┐
                    │  Entity Embeddings    │
                    │  JRC forest (5→3D)    │
                    │  Xiao planted (4→3D)  │
                    │  Ecoregion (850→32D)  │
                    │  Biome (16→8D)        │
                    │  Soil texture (14→6D) │
                    └────────┬─────────────┘
                             │
    Satellite (64-D)    Context (56 continuous + 52D embeddings = 108D)
         │                    │
         │              ┌─────┴──────┐
    Linear(64→128)      │ Gate MLP   │ ← jrc_emb(3D) + is_introduced(1D) = 4D input
    ReLU                │ 4→16→1     │
         │              │ → sigmoid  │→ α (0=trust env, 1=trust satellite)
         │              └─────┬──────┘
         │                    │
         │              Linear(108→128)
         │              ReLU
         │                    │
    ┌────┴────────────────────┴───┐
    │  Gated Fusion:              │
    │  α × sat_proj + (1-α) × env_proj  │ → 128D
    └─────────────┬───────────────┘
                  │
    Linear(128→256), ReLU
                  │
    ┌─────────────┴───────────────┐
    │  4 × ResidualBlock(256)     │
    │  Each: Linear→ReLU→Drop(0.3)→Linear→ReLU + skip  │
    └─────────┬───────────────────┘
              │
    ┌─────────┼───────────────────┐
    │         │                   │
    │  Species Head           Aux Head
    │  Linear(256→35,561)     Linear(256→1)
    │  (no bias)              → sigmoid → planted_score
    │         │                   │
    │         │  Planted Logit Boost:
    │         │  logits += planted_score × species_intro_ratio × boost_scale
    │         │
    │  → sigmoid → species probabilities
    └─────────────────────────────┘
```

**Key components:**

- **Gated fusion**: A learned gate dynamically decides how much to trust the satellite embedding vs. environmental context. When JRC says "planted forest" and the species is outside its native range (`is_introduced=1`), the gate opens to trust satellite. At a P. radiata plantation in New Zealand, gate alpha reached 0.845 (85% satellite trust).

- **Planted logit boost**: The aux head predicts whether a location is a plantation. This score is multiplied by a per-species `species_intro_ratio` buffer (fraction of training observations where `is_introduced=1`) and a learned `boost_scale` parameter (initialized 2.0). Only boosts introduced species at plantation-like sites. Native species are unaffected (ratio ≈ 0).

- **Assumed-negative BCE loss** (`sinr_an_full_loss`): For each training row, only one species is "present." All other 35,560 are assumed absent. Positive weight = 2048.0. Background samples (random locations, all species absent) with weight 1.0.

- **Aux loss**: Binary cross-entropy on the planted_score head, supervised by weak labels from Xiao (planted=1?) or JRC (planted=1?). Weight = 0.1 of total loss.

**Hyperparameters**: batch=2048, lr=0.0005, Adam, ExponentialLR(γ=0.98), dropout=0.3, gradient clip=1.0.

### Current Feature Set (130 columns)

| Category | Features | Source | Resolution |
|----------|----------|--------|-----------|
| Satellite embedding | emb_00 through emb_63 (64D) | AlphaEarth (Google) | 10m |
| Climate | bio01-bio19 (19) | WorldClim V1 | ~1km |
| Soil | pH, clay%, sand%, organic_carbon, texture_class, bulk_density, water_content (7) | OpenLandMap | 250m |
| Forest cover | treecover2000, lossyear (2) | Hansen GFC v1.12 | 30m |
| Forest type | jrc_forest_type, jrc_tmf_status, jrc_tmf_degrad_year (3) | JRC GFC2020, TMF | 10-30m |
| Land cover | esa_worldcover_2021, dynamic_world, sbtn_natural_land (3) | ESA, Google, WRI | 10m |
| Water | occurrence, recurrence, seasonality (3) | JRC Global Surface Water | 30m |
| Hydrology | merit_hand_m, merit_upstream_area_km2 (2) | MERIT Hydro | 90m |
| Canopy | gedi_canopy_height_m, gedi_foliage_height_div (2) | GEDI L2B gridded | 1km |
| Productivity | modis_gpp_mean (1) | MODIS MOD17A3 | 500m |
| Biomass | biomass_agb_mgha (1) | NASA CMS | 300m |
| Human impact | human_modification, nighttime_lights, fire_frequency_count (3) | CSP gHM, VIIRS, MODIS | 500m-1km |
| Biogeography | eco_id, biome_num (2) | RESOLVE Ecoregions | vector |
| Topography | elevation, slope, aspect, hillshade, topo_diversity (5) | SRTM/Copernicus, CSP | 30-270m |
| Climate (temporal) | tc_vpd_mean, tc_aet_mean, tc_soil_moisture_mean, tc_pdsi_mean, tc_water_deficit_mean, tc_solar_rad_mean (6) | TerraClimate | ~4km |
| Plantation | xiao_planted_forest, neumann_natural_prob (2) | Xiao 2024, Neumann/DeepMind 2025 | 10-30m |
| Status | is_introduced (1) | WCVP + TDWG spatial join | — |
| Weights | quality_weight, density_weight (2) | computed | — |

**Temporal handling**: Some features are year-matched to the observation (TerraClimate ±2yr window, MODIS GPP, Dynamic World, fire, nightlights). Others are static snapshots (WorldClim, soil, Hansen treecover2000, biomass). AlphaEarth is sampled for the observation year when 2017-2024, or 2017 for older observations.

---

## The Problem: We're Only Using 13% of Available GBIF

We discovered that our training data has a massive GBIF gap:

| Source | Records in Training | Notes |
|--------|-------------------|-------|
| USDA FIA (US forest inventory) | ~87.1M raw → sampled | 90.3% of our training pixels |
| GBIF | ~9.4M raw → sampled | 9.7% of our training pixels |

Meanwhile, `bigquery-public-data.gbif.occurrences` has **3.52 billion rows**. Filtering for our species list + HUMAN_OBSERVATION + valid coordinates + ≤100m uncertainty:

| Observation Era | GBIF Records Available | Net New Unique (species, lat4dp, lon4dp) |
|----------------|----------------------|----------------------------------------|
| 2017-2024 (AlphaEarth direct match) | 12.1M | **7.3M** |
| 2000-2016 (Hansen can validate) | 8.2M | part of 6.9M below |
| 1985-1999 (temporal stack validates) | 3.5M | part of 6.9M below |
| Pre-1985 | 1.2M | part of 6.9M below |
| Null year | 4.5M | part of 6.9M below |
| **Pre-2017 + null total** | **~17.4M** | **6.9M** |
| **Grand total net new** | | **14.2M** |

For species where we have overlapping data with GBIF, we only have about **12.7%** of what GBIF has. We're leaving 87% of the data on the table.

**This would ~3x our training data from ~8.3M to ~22-27M rows.**

---

## The Temporal Problem

The challenge with pre-2017 observations: AlphaEarth satellite embeddings only exist from 2017-2024. If a tree was observed in 1990, we sample AlphaEarth at 2017 for that pixel. But has the land changed between 1990 and 2017? Options:

### Approach A: Hardcoded Filtering (REJECTED)

Skip observations where Hansen shows forest loss between observation year and 2017. Skip pre-1985 observations entirely. Skip null-year observations.

**Problems:**
- Some trees live hundreds or thousands of years. A 1970 observation of Sequoia sempervirens is probably still valid in 2020.
- This throws away 6.9M data points (49% of the expansion).
- Native timber species (Pinus taeda in SE US, Picea abies in Scandinavia) are BOTH native AND planted. "Planted + native species ≠ suspicious." A simplistic rule would discard valid observations.
- Hansen only starts at 2000, so pre-2000 has no disturbance check at all.

### Approach B: Temporal Indicator Stack (CHOSEN)

Don't filter. Instead, sample temporal land cover / disturbance data at **both** the observation time **and** the AlphaEarth time, compute transition signals, and let the model learn which temporal gaps matter.

**The model becomes a land assessment AI nested inside the species predictor.** It learns:
- "Large gap + stable forest = probably valid"
- "Large gap + forest → cropland = probably invalid"
- "Null year + unknown transitions = weight down"
- "Zero gap = full confidence"

---

## Temporal Stack Feature Design (REVIEW THIS)

### New features to add to every training row

| # | Feature | Source | Resolution | Temporal Range | Description |
|---|---------|--------|-----------|---------------|-------------|
| 1 | `years_gap` | computed | — | — | `emb_year - observation_year`. 0 for direct match. NULL for null-year observations. |
| 2 | `hilda_lulc_at_obs` | HILDA+ | 1km | 1960-2019 | Land use class when the tree was observed. Categories: Urban, Cropland, Pasture, Forest, Grass/shrubland, Water. NULL if obs pre-1960 or null year. |
| 3 | `hilda_lulc_at_ae` | HILDA+ | 1km | 1960-2019 | Land use class when AlphaEarth was sampled. Always populated (AE is 2017-2024, HILDA covers to 2019; for 2020-2024 use 2019). |
| 4 | `hilda_transition_count` | HILDA+ | 1km | obs→AE | Number of LULC class changes in the gap period. 0 = stable. NULL if obs pre-1960 or null year. |
| 5 | `esa_cci_lc_at_obs` | ESA CCI LC | 300m | 1992-2020 | LCCS land cover class at observation year. 37 classes including 6 forest types. NULL if obs pre-1992 or null year. |
| 6 | `esa_cci_lc_at_ae` | ESA CCI LC | 300m | 1992-2020 | LCCS class at AlphaEarth year. For AE 2021-2024, use 2020. |
| 7 | `modis_lc_at_obs` | MODIS MCD12Q1 | 500m | 2001-2024 | IGBP land cover class at observation year. NULL if obs pre-2001 or null year. |
| 8 | `modis_lc_at_ae` | MODIS MCD12Q1 | 500m | 2001-2024 | IGBP class at AlphaEarth year. |
| 9 | `hansen_gain` | Hansen GFC | 30m | 2000-2012 | Forest gain flag (0/1). Captures reforestation. |
| 10 | `wri_driver_of_loss` | WRI/DeepMind | 1km | 2001-2024 | Dominant driver of forest loss: commodity agriculture, managed forestry, wildfire, urbanization, shifting agriculture. NULL where no loss detected. |
| 11 | `basis_of_record` | GBIF BQ | — | — | Categorical: HUMAN_OBSERVATION, PRESERVED_SPECIMEN, MACHINE_OBSERVATION, etc. Quality signal — museum specimens have different error profiles than citizen science. |
| 12 | `coord_uncertainty_m` | GBIF BQ | — | — | GPS precision in meters (0-100, capped by our filter). Lower = more precise. NULL for records without this metadata. |

**Total new features: 12.** Total feature set grows from 130 to ~142 columns.

### How features interact — worked examples

**Example 1: Valid old observation (confident)**
- Species: Sequoia sempervirens observed in 1975 at a California redwood grove
- `years_gap = 42` (2017 - 1975)
- `hilda_lulc_at_obs = Forest` (1975)
- `hilda_lulc_at_ae = Forest` (2017)
- `hilda_transition_count = 0`
- `hansen_lossyear = 0` (no loss 2000-2024)
- `modis_lc_at_obs = NULL` (pre-2001)
- `modis_lc_at_ae = Evergreen Needleleaf` (2017)
- AlphaEarth embedding: shows tall conifers

The model learns: big gap but land is stable forest, no transitions, no Hansen loss → observation likely still valid. The redwood is probably still there.

**Example 2: Invalid old observation (land converted)**
- Species: Pinus sylvestris observed in 1985 at a location in suburban London
- `years_gap = 32` (2017 - 1985)
- `hilda_lulc_at_obs = Forest` (1985)
- `hilda_lulc_at_ae = Urban` (2017)
- `hilda_transition_count = 1` (Forest→Urban)
- `hansen_lossyear = 2003`
- `esa_cci_lc_at_obs = Broad-leaved deciduous forest` (1992, closest to 1985)
- `esa_cci_lc_at_ae = Urban` (2017)
- AlphaEarth embedding: shows buildings/pavement

The model learns: big gap + forest→urban transition + Hansen confirms loss → this observation is unreliable for predicting what's there NOW.

**Example 3: Null-year observation (maximum uncertainty)**
- Species: Quercus robur, observed at unknown date in England
- `years_gap = NULL`
- `hilda_lulc_at_obs = NULL`
- `hilda_lulc_at_ae = Forest` (2017)
- `hilda_transition_count = NULL`
- `modis_lc_at_obs = NULL`
- `modis_lc_at_ae = Mixed forest` (2017)
- `basis_of_record = PRESERVED_SPECIMEN` (herbarium)

The model learns: null year means maximum temporal uncertainty. But: current land use IS forest, and Q. robur is extremely common in English forests. The model can still extract signal, just with less confidence.

**Example 4: Plantation ambiguity (the hard case)**
- Species: Pinus taeda observed in 1995 in SE United States
- `years_gap = 22`
- `hilda_lulc_at_obs = Forest` (1995)
- `hilda_lulc_at_ae = Forest` (2017)
- `hilda_transition_count = 0`
- `hansen_lossyear = 0`
- `xiao_planted_forest = planted` (Xiao dataset says plantation)
- `neumann_natural_prob = 0.12` (Neumann says likely planted)
- `is_introduced = 0` (Pinus taeda IS native to SE US)
- `jrc_forest_type = naturally_regenerating` (JRC misclassifies many US plantations)

The model learns: P. taeda is BOTH the native species AND the primary plantation species in SE US. `is_introduced=0` correctly indicates it's in its native range. The temporal stack shows stable forest (no conversion). Xiao/Neumann correctly identify this as a plantation, but that's fine — a P. taeda plantation in SE US is ecologically reasonable. The model should predict P. taeda with high confidence here, regardless of planted vs. natural status.

This is exactly why we don't use simplistic "planted + native = suspicious" rules. Native timber species in their home range are the most common plantation trees precisely BECAUSE they evolved there.

### How NULLs propagate

Different temporal datasets have different coverage windows:

| Dataset | Start Year | End Year | What's NULL |
|---------|-----------|---------|-------------|
| HILDA+ | 1960 | 2019 | obs pre-1960 or null year |
| ESA CCI | 1992 | 2020 | obs pre-1992 or null year |
| MODIS LC | 2001 | 2024 | obs pre-2001 or null year |
| Hansen GFC | 2000 | 2024 | Static feature — always populated |
| WRI Drivers | 2001 | 2024 | NULL where no forest loss |
| GEDI | 2019-2023 | — | NULL above ~51.6°N (ISS orbit) |

The model sees a **gradient of temporal certainty**: a 2023 observation has all features populated, a 1975 observation has HILDA but no ESA CCI/MODIS, a 1955 observation has nothing. The pattern of NULLs itself is informative — it tells the model how far back in time this observation comes from.

**Handling in the model**: NaN/NULL → 0 before z-score normalization (same as current approach for GEDI nulls, which are 10.3% of training data). The model already handles sparse features effectively.

### Categorical embedding design for new features

| Feature | Vocab Size | Emb Dim | Rationale |
|---------|-----------|---------|-----------|
| `hilda_lulc_at_obs` | 8 | 4 | 6 LULC classes + NULL + unknown |
| `hilda_lulc_at_ae` | 8 | 4 | Same classes |
| `esa_cci_lc_at_obs` | 40 | 8 | 37 LCCS classes + NULL + padding |
| `esa_cci_lc_at_ae` | 40 | 8 | Same |
| `modis_lc_at_obs` | 20 | 6 | 17 IGBP classes + NULL + padding |
| `modis_lc_at_ae` | 20 | 6 | Same |
| `wri_driver_of_loss` | 8 | 4 | 5 driver classes + no_loss + NULL + padding |
| `basis_of_record` | 10 | 4 | ~7 GBIF record types + NULL + padding |

**New embedding dims**: 4+4+8+8+6+6+4+4 = **44D** additional

**Continuous new features**: `years_gap` (1), `hansen_gain` (1), `coord_uncertainty_m` (1), `hilda_transition_count` (1) = **4** additional continuous

**Total v3 input expansion**: +44D embeddings + 4 continuous = +48 dimensions. Total entity embedding dim goes from 52D to 96D. Total continuous features from 120 to 124. This adds parameters mainly in the env projection layer (from 108→128 to 152→128 or similar — may need to increase fusion_dim).

---

## Pipeline Architecture

### Phase 1: GBIF BigQuery Extraction

```sql
SELECT
  g.speciesKey, g.species, s.taxon_id,
  g.decimalLatitude, g.decimalLongitude,
  ROUND(g.decimalLatitude, 4) as lat4dp,
  ROUND(g.decimalLongitude, 4) as lon4dp,
  g.year as observation_year,
  g.basisOfRecord, g.coordinateUncertaintyInMeters,
  g.establishmentMeans, g.institutionCode
FROM `bigquery-public-data.gbif.occurrences` g
JOIN `treekipedia-479918.species_data.species_list` s
  ON g.speciesKey = s.gbif_species_key
WHERE g.basisOfRecord = 'HUMAN_OBSERVATION'
  AND g.hasCoordinate = true
  AND g.hasGeospatialIssues = false
  AND (g.coordinateUncertaintyInMeters IS NULL
       OR g.coordinateUncertaintyInMeters <= 100)
```

Then deduplicate against existing training data on `(taxon_id, lat4dp, lon4dp, emb_year)`.

### Phase 2: Upload to GEE

- **HILDA+** (PANGAEA, ~5GB GeoTIFFs) → `projects/treekipedia-479918/assets/hilda_plus_lulc`
- **ESA CCI Land Cover** (~20GB) → `projects/treekipedia-479918/assets/esa_cci_landcover`

### Phase 3: Unified GEE Sampling

One script samples everything — new GBIF records AND backfills temporal stack on existing 8.3M training rows.

```
Input: BQ table with (taxon_id, lat, lon, observation_year, emb_year)
                          |
            ┌─────────────┼──────────────┐
            │             │              │
    AlphaEarth 64D    Existing Env     Temporal Stack
    (at emb_year)     (130 features)   (12 new features)
            │             │              │
            └─────────────┼──────────────┘
                          │
              Output: BQ table with ~142 columns
```

- Batch size: 5,000 points per GEE export task (proven at 3.5M points in prior phase)
- Parallelism: 10-20 concurrent GEE tasks
- Output: Direct to BigQuery via `ee.batch.Export.table.toBigQuery()`
- Estimated: ~14.2M new + ~8.3M backfill = ~22.5M points. At 5K/batch = ~4,500 batches. ~10-15 hours.

### Phase 4: BigQuery Consolidation

```
treekipedia-479918.species_data.sinr_training_v3
  = existing v2.2 data (with temporal stack backfilled)
  + new GBIF data (with all features)
  = ~22-27M rows
```

Export to local parquet. Spatial block split for train/val.

### Phase 5: Train v3

Same architecture as v2.2, expanded input layer for new features. Same hyperparameters initially.

---

## Datasets Available in GEE (Already Integrated)

Everything below is already sampled in our training pipeline or inference server:

| Dataset | GEE Asset | Resolution | What We Use |
|---------|-----------|-----------|-------------|
| AlphaEarth | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | 10m | 64D embedding (A00-A63), 2017-2024 |
| Hansen GFC v1.12 | `UMD/hansen/global_forest_change_2024_v1_12` | 30m | treecover2000, lossyear |
| JRC GFC2020 | `JRC/GFC2020_subtypes/V1` | 10m | forest_type (0/1/10/20) |
| JRC TMF | `projects/JRC/TMF/v1_2024/...` | 30m | tmf_status, tmf_degrad_year |
| ESA WorldCover | `ESA/WorldCover/v200` | 10m | Land cover 2021 |
| Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | 10m | Year-matched land cover (2015+) |
| SBTN Natural Land | `WRI/SBTN/naturalLands/v1_1/2020` | 10m | natural/non-natural |
| MODIS GPP | `MODIS/061/MOD17A3HGF` | 500m | Year-matched gross primary productivity |
| WorldClim V1 BIO | `WORLDCLIM/V1/BIO` | ~1km | 19 bioclimatic variables |
| OpenLandMap Soil | Multiple assets | 250m | pH, clay%, sand%, organic C, texture, bulk density, water |
| SRTM / Copernicus DEM | `USGS/SRTMGL1_003` / `COPERNICUS/DEM/GLO30` | 30m | elevation, slope, aspect, hillshade |
| JRC Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | 30m | occurrence, recurrence, seasonality |
| MERIT Hydro | `MERIT/Hydro/v1_0_1` | 90m | HAND, upstream area |
| GEDI gridded | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | 1km | canopy height, foliage diversity |
| NASA CMS Biomass | `NASA/ORNL/biomass_carbon_density/v1` | 300m | AGB |
| CSP Human Modification | `CSP/HM/GlobalHumanModification` | 1km | gHM index |
| VIIRS Nightlights | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG` | 500m | Year-matched avg_rad |
| MODIS Burned Area | `MODIS/061/MCD64A1` | 500m | Cumulative fire count |
| RESOLVE Ecoregions | `RESOLVE/ECOREGIONS/2017` | vector | eco_id, biome_num |
| CSP Topo Diversity | `CSP/ERGo/1_0/Global/SRTM_topoDiversity` | 270m | topographic diversity |
| TerraClimate | `IDAHO_EPSCOR/TERRACLIMATE` | ~4km | VPD, AET, soil moisture, PDSI, water deficit, solar rad (±2yr window) |
| Xiao Planted Forest | `projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS` | 30m | natural/planted classification |
| Neumann/DeepMind | `projects/nature-trace/assets/forest_typology/natural_forest_2020_v1_0_collection` | 10m | natural forest probability |

### Datasets to Add (Need Upload to GEE)

| Dataset | Resolution | Temporal | Source | Size |
|---------|-----------|----------|--------|------|
| **HILDA+** | 1km | 1960-2019 (annual) | PANGAEA doi:10.1594/PANGAEA.921846 | ~5GB |
| **ESA CCI Land Cover** | 300m | 1992-2020 (annual) | ESA Climate Change Initiative | ~20GB |

### Datasets Already in GEE (New Usage for Temporal Stack)

| Dataset | Current Use | New Temporal Use |
|---------|------------|-----------------|
| MODIS MCD12Q1 | Not in training | `modis_lc_at_obs` and `modis_lc_at_ae` (2001-2024) |
| Hansen GFC | treecover2000, lossyear | Add `hansen_gain` (2000-2012) |
| WRI/DeepMind Drivers | Not in training | `wri_driver_of_loss` (2001-2024) |

---

## Known Issues and Concerns

### 1. Resolution Mismatch in Temporal Stack

HILDA+ is 1km — coarse compared to AlphaEarth at 10m. A 1km pixel could contain both forest and cropland. At 1km, transition signals may be too coarse to capture localized land use changes.

**Our take**: 1km HILDA+ is still useful because it captures landscape-scale transitions (urban sprawl, deforestation fronts) that affect large areas. Fine-grained changes within 1km are captured by Hansen (30m) and ESA CCI (300m). The multi-resolution stack gives the model signals at different spatial scales.

**Question for reviewers**: Is 1km too coarse to be useful? Should we weight HILDA+ differently from finer-resolution temporal features?

### 2. NULL Encoding

We plan to encode NULLs as 0 after z-score normalization (same treatment as current GEDI nulls). This means "no data" maps to the mean of the feature distribution.

**Concern**: 0 after z-score means "average value," not "missing." The model can't distinguish "HILDA says forest" from "no HILDA data" if forest happens to map to the normalized mean.

**Alternative**: Add explicit `has_hilda`, `has_esa_cci`, `has_modis_lc` binary indicator features so the model knows which temporal signals are available. This adds 3-4 more features but provides a clean missing-data signal.

**Question for reviewers**: Is the NULL-as-0 approach acceptable, or should we add explicit missingness indicators?

### 3. Extreme Class Imbalance After Expansion

The 14.2M new GBIF records will be heavily biased toward well-observed species in Europe and North America (citizen science bias). Our existing `HARD_CAP_PER_SPECIES = 50,000` per-species cap helps, but:
- After expansion, common species may hit the cap and be randomly subsampled
- Rare species (60% have <10 samples) get no new data at all
- The geographic bias may worsen

**Question for reviewers**: Should we adjust the hard cap? Use a log-scale cap? Apply geographic stratification?

### 4. Spatial Autocorrelation in Validation

Current train/val split is random 95/5. Points 100m apart may end up in different splits, inflating accuracy.

**Plan**: Implement spatial block cross-validation using 2° grid cells for v3. Assign entire grid cells to train or val to eliminate spatial leakage.

**Question for reviewers**: Is 2° too coarse? Too fine? Should we use a different spatial blocking strategy?

### 5. Interaction Between Temporal Stack and Gate

The gate currently uses `jrc_forest_type(3D) + is_introduced(1D)` to decide satellite vs. environment weighting. Should any temporal features be added to the gate input? For example, if `hilda_transition_count > 0`, should the gate trust the satellite less (because the land may have changed since the observation)?

**Question for reviewers**: Should temporal features influence the gate, or only the main prediction pathway?

### 6. years_gap Distribution

The distribution of `years_gap` will be heavily skewed:
- 2017-2024 data: gap = 0-7 (majority of new records)
- 2000-2016: gap = 1-17
- 1985-1999: gap = 18-32
- Pre-1985: gap = 32-57+
- Null year: gap = NULL

**Question for reviewers**: Should `years_gap` be log-transformed? Binned? Left as continuous?

### 7. Feature Engineering vs. Raw Features

We're providing raw temporal indicators (land cover class at time A, land cover class at time B) and one derived feature (transition count). Should we add more derived features?

Candidates:
- `lulc_changed` (binary: did HILDA class change between obs and AE?)
- `forest_to_nonforest` (binary: was it forest at obs but not at AE?)
- `years_since_disturbance` (Hansen lossyear → continuous)
- `temporal_confidence` (composite score: 1.0 for gap=0, decreasing with gap and transitions)

**Question for reviewers**: More derived features, or let the model learn the interactions?

---

## Model Version History

| Version | Architecture | Species | Data | Key Result |
|---------|-------------|---------|------|------------|
| v1 | Simple ResidualFCNet, no gate | 43,566 | 8.6M | top-10: 53.3%, P.radiata #22 |
| v2 | 4D gate + entity embeddings | 43,566 | 8.6M | P.radiata **#5**, alpha=0.845 |
| v2.1 | 8D gate + aux head (REGRESSED) | 43,566 | 8.6M | P.radiata #21 (noisy gate inputs) |
| v2.2 | 4D gate + planted logit boost + subspecies merge | 35,561 | 8.3M | top-10: 59.3%, top-50: 90.1% |
| **v3** (planned) | v2.2 + temporal stack | 35,561+ | ~22-27M | Target: top-10 >65%, better temporal robustness |

---

## Specific Questions for Reviewers

1. **Temporal stack completeness**: Are there temporal / disturbance datasets we're missing? We've looked at HILDA+ (1960-2019), ESA CCI (1992-2020), MODIS LC (2001-2024), Hansen GFC (2000-2024), JRC TMF (1982-2022), WRI/DeepMind drivers (2001-2024). What else exists at global scale?

2. **NULL encoding strategy**: 0-after-z-score vs. explicit missingness indicators vs. something else? With ~12 new features, many will be NULL for pre-1992 or pre-2001 observations. What's the best practice for neural networks with structured missing data?

3. **Temporal feature design**: Are paired features (LULC-at-obs + LULC-at-AE) the right abstraction? Or should we compute explicit transition features (forest→cropland = class 1, forest→urban = class 2, stable = class 0, etc.)?

4. **Gate expansion**: Should temporal reliability signals enter the gate mechanism (influencing how much the model trusts satellite vs. environment), or only the main prediction pathway?

5. **Spatial block CV**: Best strategy for splitting? 2° grid cells? Hexagonal grids? Systematic vs. random assignment of blocks?

6. **Hard cap and sampling strategy**: With 3x data and extreme class imbalance (median 6 occurrences, max >400K), what's the optimal capping / weighting strategy?

7. **Architecture scaling**: With ~50 more input dimensions and 3x more data, should we scale the hidden dim (256→512)? Add more residual blocks? Or keep architecture fixed and let data do the work?

8. **Multi-year AlphaEarth**: For 2017-2024 observations, we sample AE at the observation year. Should we also consider sampling AE at multiple years and providing temporal embedding deltas as features?

9. **Anything we haven't thought of**: What are we missing? What would you do differently?

---

## Loss Function Details (for reference)

Our assumed-negative full BCE loss, following the SINR paper:

```python
# For each batch of 2048 training rows:
# - Each row is one (location, species) observation
# - Target species is "present" (positive), all other 35,560 are "assumed absent"

log_pos = log(sigmoid(logits))           # log probability of presence
log_neg = log(1 - sigmoid(logits))       # log probability of absence

# Base: assume all species absent everywhere
loss_neg = -mean(log_neg, dim=species)   # per-sample negative loss

# Correction: for the target species, remove negative contribution, add weighted positive
correction = (-log_neg[target] + POS_WEIGHT * (-log_pos[target])) / num_species

loss = loss_neg + correction

# Weight by sample quality (quality_weight × density_weight, clipped [0.01, 10.0])
weighted_loss = mean(loss × sample_weight)

# Background regularization: random locations, all species assumed absent
bg_loss = -mean(log(1 - sigmoid(bg_logits)))
total_loss = weighted_loss + BG_WEIGHT * bg_loss

# Auxiliary plantation detection loss (weight = 0.1)
aux_loss = BCE(planted_score, weak_planted_label)
total_loss += 0.1 * aux_loss
```

`POS_WEIGHT = 2048.0`, `BG_WEIGHT = 1.0`.

---

## Summary

We have a working species prediction model (v2.2, 35,561 species, top-10 accuracy 59.3%). We want to triple the training data by extracting ~14.2M new GBIF records from BigQuery. The key innovation is a **temporal indicator stack** that provides land use context at both observation time and satellite sampling time, letting the model learn which old observations are still valid — rather than discarding them with hardcoded rules.

We're asking for feedback on the temporal stack design, NULL handling, pipeline architecture, and anything we might be missing before we commit to the ~3-day extraction/sampling campaign.
