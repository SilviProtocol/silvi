# Master Prediction Architecture
## Treekipedia Species Intelligence System

**Version**: 3.0 (Comprehensive)
**Date**: January 21, 2026
**Status**: Implementation-Ready

> **This document is the single source of truth** for the Species Predictor/Recommender system.
> See [Research Document Index](#11-research-document-index) for supporting documents.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Architecture](#2-core-architecture)
3. [Data Foundation](#3-data-foundation)
4. [Environmental Variables](#4-environmental-variables)
5. [Species Knowledge Schema](#5-species-knowledge-schema)
6. [Predictor System](#6-predictor-system)
7. [Recommender System (SAFE-B)](#7-recommender-system-safe-b)
8. [Dynamic Weighting Framework](#8-dynamic-weighting-framework)
9. [Implementation Status](#9-implementation-status)
10. [Gaps & Priorities](#10-gaps--priorities)
11. [Research Document Index](#11-research-document-index)

---

## 1. Executive Summary

### What We're Building

**Two distinct but connected systems**:

| System | Question | Use Case | Invasive Species |
|--------|----------|----------|------------------|
| **Predictor** | "What trees ARE/WERE here?" | Scientific analysis | Included |
| **Recommender** | "What SHOULD I plant?" | Restoration planning | **Excluded** |

### Technology Stack

| Component | Technology | Status |
|-----------|------------|--------|
| Satellite Embeddings | AlphaEarth 64-D (10m resolution) | 3.37M records, 17,924 species |
| Vector Database | PostgreSQL + pgvector 0.8.1 | Schema ready |
| Occurrence Data | 5.7M L7 geohash tiles | Integrated |
| Climate Data | 8 WorldClim variables | 88.6% coverage |
| Soil Data | SoilGrids pH, texture, OC | 66-82% coverage |
| Native Status | WCVP | 99.99% coverage |
| Biotic Interactions | GloBI | 100% coverage |

### Competitive Advantages

1. **10m prediction resolution** - AlphaEarth embeddings are 3-100× finer than competitors
2. **99.99% native status** - 30% more coverage than best competitor
3. **100% GloBI biotic interactions** - Unique integration at scale
4. **L7 geohash tile storage** - 5.7M tiles for efficient spatial queries
5. **Blockchain provenance** - EAS attestations for research versioning

---

## 2. Core Architecture

### System Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Request (lat, lon)                          │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Location Predictor (Python :5002)                     │
│                                                                         │
│  1. Query AlphaEarth via GEE → 64-D embedding                          │
│  2. Query Hansen → treecover2000, lossyear, gain                       │
│  3. Query SRTM → elevation                                              │
│  4. Query SoilGrids → pH, texture, organic carbon                      │
│  5. Return: {embedding, elevation, treecover, soil, loss_year}         │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                      │
              ▼                                      ▼
┌─────────────────────────────┐    ┌─────────────────────────────────────┐
│      PREDICTOR API          │    │        RECOMMENDER API               │
│  /api/prediction/predict    │    │   /api/prediction/recommend          │
│                             │    │                                       │
│  Pure Suitability Score:    │    │  SAFE-B Framework:                   │
│  • Cosine similarity        │    │  • S - Spatial (occurrence density) │
│  • Elevation percentile     │    │  • A - Abiotic (climate, soil, topo)│
│  • Climate envelope         │    │  • F - Functional (traits match)    │
│  • Soil tolerance           │    │  • E - Ecosystem (ecoregion, biome) │
│  • Includes ALL species     │    │  • B - Biotic (interactions)        │
│    (even invasives)         │    │                                       │
│                             │    │  + Native filter (excludes invasive)│
│  Output: Scientific habitat │    │  + Strategy alignment               │
│  suitability for ANY tree   │    │                                       │
└─────────────────────────────┘    └─────────────────────────────────────┘
```

### Key Insight: Predictor vs Recommender

A location may be highly suitable for an invasive species (Predictor score = 0.95), but the Recommender **NEVER** suggests planting invasives.

| Aspect | Predictor | Recommender |
|--------|-----------|-------------|
| Purpose | "Can this species survive here?" | "Should I plant this species here?" |
| Invasive Species | **Included** (may be highly suitable) | **Excluded** (never recommended) |
| Native Status | Informational only | Hard filter |
| Restoration Goals | Not considered | Core factor |
| Successional Stage | Not considered | Matches site conditions |

---

## 3. Data Foundation

### 3.1 AlphaEarth Embeddings

**Current Status**: 3.37M records, 17,924 species in BigQuery

| Field | Description | Coverage |
|-------|-------------|----------|
| `taxon_id` | WFO taxon identifier | 100% |
| `latitude`, `longitude` | Occurrence location | 100% |
| `emb_year` | Embedding year (2017-2024) | 100% |
| `orig_year` | GBIF observation year | 100% |
| `elevation` | SRTM 90m elevation (meters) | 99% |
| `treecover2000` | Hansen tree cover % | 100% |
| `lossyear`, `loss`, `gain` | Forest change | 100% |
| `A00-A63` | 64-D AlphaEarth embedding | 100% |

**GEE Asset**: `ee.ImageCollection("projects/ee-caseyodonnell/assets/AlphaEarth")`

**Alternative (10-50× cheaper)**: GCS COGs at `gs://alphaearth_foundations/`

### 3.2 Occurrence Data

**Source**: GBIF via geohash L7 tiles (~150m resolution)

| Table | Records | Coverage |
|-------|---------|----------|
| `geohash_species_tiles` | 5,786,835 | 48,129 species (71%) |

**STAC-Compliant Format**:
```json
{
  "geohash_l7": "9q8yyk",
  "species_data": {
    "wfo-0000509326": {"count": 15, "years": [2019, 2020, 2021]},
    "wfo-0000723513": {"count": 8, "years": [2018, 2019]}
  },
  "datetime": "2021-12-31T00:00:00Z"
}
```

### 3.3 Proximity-Based Density Weighting

**Critical Insight**: Sampling bias is SPATIAL, not per-pixel.

A research station with 1000 observations in 1 hectare should NOT have 1000× the influence of 5 observations spread across 1000 hectares.

**Solution**: Multi-scale geohash density weighting

```python
def compute_multiscale_density_weights(lats, lons):
    """
    Three scales capture different bias patterns:
    - Local (precision 6, ~1.2km): Research station clusters
    - Regional (precision 5, ~5km): City/road bias
    - Broad (precision 4, ~40km): Continental sampling patterns
    """
    # Encode at 3 scales
    local_gh = encode_geohash(lats, lons, precision=6)
    regional_gh = encode_geohash(lats, lons, precision=5)
    broad_gh = encode_geohash(lats, lons, precision=4)

    # Count points per cell
    density_local = count_per_cell(local_gh)
    density_regional = count_per_cell(regional_gh)
    density_broad = count_per_cell(broad_gh)

    # Weighted combination (local matters most for bias correction)
    combined = 0.5 * density_local + 0.3 * density_regional + 0.2 * density_broad

    # Log-inverse weighting: high density = low weight
    weights = 1.0 / np.log1p(combined)

    return weights / weights.max()  # Normalize to [0, 1]
```

**Implementation**: [cluster_habitat_centroids_weighted.py](../../orchestrator/cluster_habitat_centroids_weighted.py)

---

## 4. Environmental Variables

### 4.1 Climate Variables (88.6% Coverage)

**Implemented in Species Table**:

| Field | Format | Coverage | Source |
|-------|--------|----------|--------|
| `annual_precipitation_mm` | `min;max` percentile | 88.6% | WorldClim |
| `annual_temperature_range_c` | `min;max` percentile | 88.6% | WorldClim |
| `climate_type_koppengeiger` | Semicolon codes | 88.5% | Köppen-Geiger |
| `wettest_month_precipitation_mm` | Percentile range | 100% | WorldClim |
| `driest_month_precipitation_mm` | Percentile range | 100% | WorldClim |
| `precipitation_seasonality_cv` | Coefficient of variation | 100% | WorldClim |
| `wettest_quarter_precipitation_mm` | Percentile range | 100% | WorldClim |
| `driest_quarter_precipitation_mm` | Percentile range | 100% | WorldClim |

**Available but Not Yet Integrated**:
- All 19 WorldClim BioClim variables (currently only 8 used)
- Growing season length (derivable)
- Frost-free days (derivable)
- Aridity index (precipitation / potential_evapotranspiration)

**Data Sources**:
- WorldClim v2.1 (1km resolution, 1970-2000 baseline)
- TerraClimate (4km monthly, GEE: `IDAHO_EPSCOR/TERRACLIMATE`)
- CHELSA v2.1 (1km, high mountain areas)

### 4.2 Soil Variables (66-82% Coverage)

**Physical Properties (Implemented)**:

| Field | Format | Coverage | Categories |
|-------|--------|----------|------------|
| `ph_dominant` | Category | 81.9% | moderately acidic, neutral, strongly acidic, slightly acidic, slightly alkaline |
| `ph_all`, `ph_prefered`, `ph_tolerated` | Categories | 100% | Same as above |
| `soil_texture_dominant` | Category | 66.2% | Clay Loam, Sandy Clay Loam, Loam, Sandy Loam |
| `soil_texture_all`, `soil_texture_prefered`, `soil_texture_tolerated` | Categories | 100% | Same as above |
| `oc_dominant` | Percentile range | 100% | Organic carbon g/kg |
| `oc_all`, `oc_prefered`, `oc_tolerated` | Percentile ranges | 100% | Same as above |

**Available via SoilGrids (Not Yet Collected)**:

| Variable | GEE Band | Description |
|----------|----------|-------------|
| `cec_mean` | SoilGrids250m | Cation Exchange Capacity |
| `nitrogen_mean` | SoilGrids250m | Total Nitrogen |
| `bdod_mean` | SoilGrids250m | Bulk Density (6 depths) |
| `sand_mean`, `silt_mean`, `clay_mean` | SoilGrids250m | Texture fractions % |

**Available via HiHydroSoil (Not Yet Collected)**:

| Variable | Description |
|----------|-------------|
| Saturated hydraulic conductivity | Water infiltration rate |
| Field capacity water content | Available water |
| Wilting point water content | Minimum plant-available water |
| Available water capacity | Field capacity - wilting point |

**Data Sources**:
- SoilGrids250m v2.0 (250m, GEE: `ISRIC/SoilGrids250m_v2_0`)
- HiHydroSoil v2.0 (250m, GEE: `projects/sat-io/open-datasets/HiHydroSoilv2_0`)

### 4.3 Topographic Variables

**CRITICAL GAP - Elevation (0% Numeric Data)**:

| Current State | Target State |
|---------------|--------------|
| `elevation_ranges_ai` - TEXT prose | Numeric percentiles (p10, p25, median, p75, p90) |
| `elevation_ranges_human` - TEXT prose | Same as above |

**1.5M SRTM backfill records exist** in BigQuery but not yet aggregated per species.

**Derived Variables (Not Yet Implemented)**:

| Variable | Formula | Use |
|----------|---------|-----|
| **Slope** | `gradient(elevation)` | Drainage, erosion, soil moisture |
| **Aspect** | `arctan2(dy, dx)` | Solar exposure, microclimate |
| **Topographic Wetness Index (TWI)** | `ln(flow_acc / tan(slope))` | Soil moisture proxy |
| **Topographic Position Index (TPI)** | `elevation - mean(neighbors)` | Ridges vs valleys |
| **Roughness** | `max(neighbors) - min(neighbors)` | Terrain complexity |

**Data Sources**:
- SRTM 30m DEM (GEE: `USGS/SRTMGL1_003`)
- MERIT DEM 90m (GEE: `MERIT/DEM/v1_0_3`)
- ALOS World 3D 30m (GEE: `JAXA/ALOS/AW3D30/V3_2`)

### 4.4 Hydrological Variables (Not Yet Implemented)

| Variable | Source | GEE Asset |
|----------|--------|-----------|
| Flow Accumulation | HydroSHEDS 15 arc-sec | `WWF/HydroSHEDS/15ACC` |
| Distance to Water | JRC Global Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` |
| Soil Moisture (monthly) | TerraClimate | `IDAHO_EPSCOR/TERRACLIMATE` |
| Actual Evapotranspiration | TerraClimate | Same |
| Climatic Water Deficit | TerraClimate | Same |
| Palmer Drought Severity Index | TerraClimate | Same |
| Permanent Water Extent | JRC (30m, 1984-2021) | `JRC/GSW1_4/GlobalSurfaceWater` |

### 4.5 Biogeographic Variables (85-100% Coverage)

**Implemented**:

| Field | Coverage | Format |
|-------|----------|--------|
| `ecoregions` | 100% | WWF/One Earth names (semicolon-separated) |
| `biomes` | 100% | WWF Biome names |
| `bioregions` | 100% | Biogeographic realms |
| `sbtn_landcover` | 85.3% | SBTN land cover types |
| `vegetationtype` | 99.8% | Vegetation classification |
| `functional_ecosystem_groups` | 91.9% | IUCN GET **names** (NOT codes) |
| `present_intact_forest` | 100% | YES/NO/YES;NO/NO;YES/NA |

**Intact Forest Breakdown** (61,377 non-NA species):

| Value | Count | Percentage |
|-------|-------|------------|
| NO (not in intact forest) | 35,613 | 52.6% |
| NO;YES (both) | 20,729 | 30.6% |
| NA (no occurrence data) | 6,366 | 9.4% |
| YES;NO (both) | 4,042 | 6.0% |
| YES (only intact) | 993 | 1.5% |

**PostGIS Spatial Layers**:

| Table | Records | Source |
|-------|---------|--------|
| `ecoregions` | 847 polygons | WWF/One Earth 2017 |
| `intact_forest_landscapes_2021` | 6,819 polygons | IFL 2021 |
| `countries` | ~250 polygons | Natural Earth |

**Gap**: IUCN GET **codes** (e.g., "T1.1") not mapped - currently have full names only.

### 4.6 Disturbance & Land Use Variables

**Implemented (via Hansen Global Forest Change)**:

| Field | Description | Collection Status |
|-------|-------------|-------------------|
| `tree_cover_2000` | Canopy cover % in year 2000 | 17.9% of occurrences |
| `loss_year` | Year of forest loss 2001-2023 | Same |
| `forest_loss` | Binary loss flag | Same |
| `forest_gain` | Forest gain 2000-2020 | Same |

**GEE Asset**: `UMD/hansen/global_forest_change_2022_v1_10` (30m resolution)

**Not Yet Implemented**:
- Fire frequency (MODIS: `MODIS/006/MCD64A1`)
- Human Footprint Index (separate download)
- Road density (OpenStreetMap)

---

## 5. Species Knowledge Schema

### 5.1 Native Status (99.99% Coverage)

| Field | Coverage | Format | Source |
|-------|----------|--------|--------|
| `wcvp_native` | 99.99% | ISO country codes (semicolon-separated) | WCVP |
| `wcvp_introduced` | 100% | ISO country codes | WCVP |
| `countries_invasive` | 100% | Country names | Various |
| `common_countries` | 100% | Aggregated from occurrences | GBIF |

**Source**: World Checklist of Vascular Plants (WCVP) by Royal Botanic Gardens, Kew

### 5.2 Functional Trait Fields (100% AI Coverage)

**Growth Form & Structure**:

| Field | Format | Coverage |
|-------|--------|----------|
| `growth_form_ai/human` | tree, shrub, palm, cycad | 100% |
| `maximum_height_ai/human` | TEXT (meters) | 100% |
| `maximum_diameter_ai/human` | TEXT (cm) | 100% |
| `lifespan_ai/human` | TEXT | 100% |
| `maximum_tree_age_ai/human` | TEXT (years) | 100% |

**Foliage Characteristics**:

| Field | Format | Coverage |
|-------|--------|----------|
| `leaf_type_ai/human` | simple, compound, needle, scale | 100% |
| `deciduous_evergreen_ai/human` | deciduous, evergreen, semi-deciduous | 100% |
| `flower_color_ai/human` | TEXT | 100% |
| `fruit_type_ai/human` | TEXT | 100% |
| `bark_characteristics_ai/human` | TEXT | 100% |

**Ecological Strategy**:

| Field | Format | Coverage |
|-------|--------|----------|
| `successional_stage` | Pioneer, Early, Mid, Late, Climax | 100% |
| `forest_layers` | Canopy, Subcanopy, Understory, Ground | 100% |
| `tolerances` / `tolerances_ai` | TEXT (shade, drought, flood, salt, frost, fire, compaction) | 100% |
| `climate_tolerance_ai` | TEXT | 100% |

**Competitive Advantage**: TRY Plant Trait Database has 15-30% coverage for most traits (mostly herbaceous). Treekipedia's 100% AI-generated coverage for trees is unprecedented.

### 5.3 Biotic Interaction Fields (100% via GloBI)

| Field | Description |
|-------|-------------|
| `globi_pollinatedby` | Pollinators (semicolon-separated taxa) |
| `globi_eatenby` | Herbivores |
| `globi_flowersvisitedby` | Flower visitors |
| `globi_hasparasite` | Parasites |
| `globi_haspathogen` | Pathogens |
| `globi_hasdispersalvector` | Seed dispersers |
| `globi_preyeduponby` | Predators |
| `globi_hasparasitoid` | Parasitoids |

**Source**: Global Biotic Interactions (GloBI) database (1.5M interactions globally)

### 5.4 Occurrence-Derived Percentile Fields (NOT YET IMPLEMENTED)

**Identified as critical for prediction accuracy**:

| Field | Target Format | Data Source |
|-------|---------------|-------------|
| `elevation_percentile` | p10, p25, median, p75, p90 | SRTM at occurrence points |
| `temperature_percentile` | Same | WorldClim at occurrence points |
| `precipitation_percentile` | Same | WorldClim at occurrence points |
| `soil_ph_percentile` | Same | SoilGrids at occurrence points |

---

## 6. Predictor System

### 6.1 Habitat Centroids

For each species, we cluster AlphaEarth embeddings into 3-10 habitat prototypes using weighted K-means:

**Schema** (`species_habitat_centroids`):

| Field | Type | Description |
|-------|------|-------------|
| `taxon_id` | VARCHAR(50) | Species identifier |
| `cluster_id` | INTEGER | 0-9 cluster index |
| `centroid_vector` | vector(64) | pgvector 64-D mean embedding |
| `occurrence_count` | INTEGER | Raw count of source pixels |
| `effective_sample_size` | FLOAT | Bias-corrected sample size |
| `mean_elevation` | FLOAT | Cluster elevation mean |
| `elevation_std` | FLOAT | Cluster elevation std dev |
| `mean_treecover2000` | FLOAT | Average tree cover |
| `forest_loss_fraction` | FLOAT | Fraction with forest loss |
| `representative_lat` | FLOAT | Medoid latitude |
| `representative_lon` | FLOAT | Medoid longitude |

**Index**: IVFFlat for cosine similarity
```sql
CREATE INDEX idx_centroid_vector
ON species_habitat_centroids
USING ivfflat (centroid_vector vector_cosine_ops) WITH (lists = 100);
```

### 6.2 Clustering Pipeline

**Three-Tier Hybrid Approach**:

| Tier | Weight | Method | Purpose |
|------|--------|--------|---------|
| **Tier 1** | 70% | Occurrence-based clustering | Capture realized niche |
| **Tier 2** | 20% | Landscape validation | Detect sampling bias |
| **Tier 3** | 10% | Contrastive learning | Refine embeddings |

**Tier 1 Implementation** (Primary):
```python
def cluster_species_habitats(species_id, min_k=3, max_k=10):
    # Get occurrence embeddings
    embeddings = get_alphaearth_embeddings(species_id)
    lats, lons = get_occurrence_coords(species_id)

    # Compute proximity-based weights
    weights = compute_multiscale_density_weights(lats, lons)

    # Find optimal K via silhouette score
    best_k = find_optimal_k(embeddings, weights, min_k, max_k)

    # Weighted K-means
    kmeans = KMeans(n_clusters=best_k)
    kmeans.fit(embeddings, sample_weight=weights)

    return kmeans.cluster_centers_  # Shape: (k, 64)
```

### 6.3 Prediction Algorithm

```python
def predict_habitat_suitability(lat, lon, taxon_id=None):
    """
    Pure scientific suitability prediction.
    Returns: List of species with suitability scores
    """
    # 1. Sample query location
    query_embedding = sample_alphaearth(lat, lon)
    query_elevation = sample_srtm(lat, lon)
    query_climate = sample_worldclim(lat, lon)
    query_soil = sample_soilgrids(lat, lon)

    # 2. Find similar centroids via pgvector
    sql = """
        SELECT
            s.taxon_id,
            s.species_scientific_name,
            1 - (shc.centroid_vector <=> $1::vector) as similarity,
            shc.mean_elevation,
            shc.effective_sample_size,
            s.wcvp_introduced
        FROM species_habitat_centroids shc
        JOIN species s ON s.taxon_id = shc.taxon_id
        WHERE 1 - (shc.centroid_vector <=> $1::vector) > 0.7
        ORDER BY similarity DESC
        LIMIT 100
    """

    # 3. Apply environmental filters
    candidates = filter_by_elevation(results, query_elevation, tolerance=500)
    candidates = filter_by_climate_envelope(candidates, query_climate)
    candidates = filter_by_soil_tolerance(candidates, query_soil)

    # 4. Return ALL suitable species (including invasives)
    return candidates
```

### 6.4 API Endpoint

**Endpoint**: `GET /api/prediction/predict`

**Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `lat` | float | Latitude (required) |
| `lon` | float | Longitude (required) |
| `elevation_tolerance` | int | ± meters (default 500) |
| `min_similarity` | float | Cosine threshold (default 0.7) |
| `limit` | int | Max results (default 50) |

**Response**:
```json
{
  "location": {"lat": -1.2921, "lon": 36.8219},
  "query_elevation": 1670,
  "ecoregion": "East African montane forests",
  "predictions": [
    {
      "taxon_id": "wfo-0000509326",
      "scientific_name": "Eucalyptus globulus",
      "similarity": 0.92,
      "elevation_match": true,
      "climate_match": 0.88,
      "soil_match": 0.75,
      "introduced_status": "INTRODUCED",
      "confidence": "high"
    },
    {
      "taxon_id": "wfo-0000723513",
      "scientific_name": "Juniperus procera",
      "similarity": 0.88,
      "elevation_match": true,
      "climate_match": 0.92,
      "soil_match": 0.85,
      "introduced_status": "NATIVE",
      "confidence": "high"
    }
  ]
}
```

---

## 7. Recommender System (SAFE-B)

### 7.1 SAFE-B Framework

The Recommender adds 5 scoring components on top of the Predictor:

| Component | Weight | Description | Data Source |
|-----------|--------|-------------|-------------|
| **S** - Spatial | 20-30% | Occurrence density, range size | GBIF geohash tiles |
| **A** - Abiotic | 20-35% | Climate, soil, topography match | WorldClim, SoilGrids, SRTM |
| **F** - Functional | 15-40% | Trait suitability for goals | Species traits |
| **E** - Ecosystem | 15-25% | Ecoregion, biome, GET match | WWF, IUCN GET |
| **B** - Biotic | 5-25% | Pollinator, disperser availability | GloBI |

**+ Hard Filters**:
- Native status (excludes invasives)
- Elevation tolerance
- Climate envelope

### 7.2 Strategy-Specific Weighting

Weights vary by restoration goal:

| Strategy | S | A | F | E | B |
|----------|---|---|---|---|---|
| **Rewilding** | 20% | 15% | 10% | 30% | 25% |
| **Agroforestry** | 10% | 25% | 40% | 15% | 10% |
| **Riparian** | 15% | 35% | 20% | 20% | 10% |
| **Carbon Sequestration** | 10% | 20% | 50% | 15% | 5% |
| **Biodiversity** | 15% | 15% | 20% | 25% | 25% |

### 7.3 Functional Trait Matching by Strategy

| Strategy | Prioritized Traits |
|----------|-------------------|
| `rewilding` | Native status, ecological function, dispersal ability |
| `agroforestry` | Fast growth, multi-use, marketability |
| `riparian` | Flood tolerance, bank stabilization, root depth |
| `carbon` | Biomass accumulation, longevity, wood density |
| `biodiversity` | Fauna support, keystone role, structural diversity |

### 7.4 API Endpoint

**Endpoint**: `GET /api/prediction/recommend`

**Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `lat` | float | Latitude (required) |
| `lon` | float | Longitude (required) |
| `country_code` | string | ISO code for native filtering |
| `restoration_goal` | enum | rewilding, agroforestry, riparian, carbon, biodiversity |
| `successional_stage` | enum | bare_soil, early, mid, late, old_growth |
| `limit` | int | Max results (default 50) |

**Response**:
```json
{
  "location": {"lat": -1.2921, "lon": 36.8219, "country": "Kenya"},
  "restoration_goal": "biodiversity",
  "recommendations": [
    {
      "taxon_id": "wfo-0000723513",
      "scientific_name": "Juniperus procera",
      "safeb_score": 91.2,
      "components": {
        "spatial": 85,
        "abiotic": 90,
        "functional": 88,
        "ecosystem": 95,
        "biotic": 82
      },
      "native_status": "native",
      "reasoning": "Native keystone species, high fauna support, excellent climate match"
    }
  ],
  "excluded": [
    {
      "taxon_id": "wfo-0000509326",
      "scientific_name": "Eucalyptus globulus",
      "reason": "Introduced species (INVASIVE filter applied)"
    }
  ]
}
```

---

## 8. Dynamic Weighting Framework

### 8.1 Context-Adaptive Weights

Weights are **functions of context**, not static constants:

| Context | What Changes |
|---------|--------------|
| **Spatial Scale** | Microhabitat vs landscape vs regional |
| **Successional Stage** | Pioneer boosted for bare soil, climax for old growth |
| **Restoration Strategy** | Rewilding vs agroforestry vs carbon |
| **Data Confidence** | Reduce embedding weight for historical reconstruction |

### 8.2 Scale-Dependent Variable Importance

| Variable | Microhabitat (<1km) | Landscape (1-10km) | Regional (>10km) |
|----------|---------------------|-------------------|------------------|
| Soil match | 25% | 15% | 5% |
| Embedding similarity | 20% | 25% | 10% |
| Climate match | 10% | 15% | 35% |
| Native status | 8% | 15% | 25% |
| Occurrence density | 15% | 20% | 15% |
| Ecoregion match | 5% | 10% | 25% |

### 8.3 Successional Stage Matching

| Stage | Boost | Penalize |
|-------|-------|----------|
| Bare soil | Pioneer, N-fixers, fast growth | Climax, shade-tolerant |
| Early (<10yr) | Fast colonizers, competitive | Slow-growing climax |
| Mid (10-50yr) | Competitive strategists | Pioneers (outcompeted) |
| Late (50-200yr) | Shade-tolerant, climax, specialists | Pioneers, generalists |
| Old growth | Gap specialists, structural diversity | Early successional |

### 8.4 Data Quality Tiers

| Tier | Embedding Weight | Occurrence Weight | Climate Weight |
|------|-----------------|------------------|----------------|
| **High** (AlphaEarth 2017-2024) | 1.0× | 1.0× | 1.0× |
| **Medium** (Landsat reconstruction) | 0.6× | 1.3× | 1.2× |
| **Low** (Pre-satellite inference) | 0.3× | 1.2× | 1.5× |

**Rationale**: When embedding data is uncertain, rely more on stable factors (climate, ecoregion, occurrences).

**Full Framework**: [DYNAMIC_WEIGHTING_FRAMEWORK.md](./DYNAMIC_WEIGHTING_FRAMEWORK.md)

---

## 9. Implementation Status

### 9.1 Completed

| Component | Status | Details |
|-----------|--------|---------|
| AlphaEarth Phase 1 GEE sampling | ✅ Complete | 3.37M embeddings, 17,924 species |
| PostgreSQL schema with pgvector | ✅ Complete | Migration 007 applied |
| Proximity weighting strategy | ✅ Designed | Multi-scale geohash density |
| Weighted clustering script | ✅ Written | `cluster_habitat_centroids_weighted.py` |
| API routes (draft) | ✅ Written | `routes/prediction.js` |
| Dynamic weighting framework | ✅ Researched | Full Python implementation |
| Location predictor service | ✅ Running | Port 5002 |
| LEAF score API | ✅ Production | `/api/geospatial/leaf/score` |
| Climate variables | ✅ Integrated | 8 WorldClim variables, 88.6% coverage |
| Soil variables | ✅ Integrated | pH, texture, OC (66-82% coverage) |
| Native status | ✅ Integrated | WCVP 99.99% coverage |
| Biotic interactions | ✅ Integrated | GloBI 100% coverage |

### 9.2 In Progress

| Component | Status | Details |
|-----------|--------|---------|
| BigQuery → Local Parquet export | 🔄 12% | 4/34 batches (~160MB) |
| GEE remaining tasks | 🔄 4 tasks | 2,845 species Phase 1 completion |

### 9.3 Pending

| Component | Depends On | Priority |
|-----------|-----------|----------|
| Run weighted clustering | Parquet export | HIGH |
| Load centroids to PostgreSQL | Clustering | HIGH |
| Integrate prediction routes | Centroids loaded | HIGH |
| Numeric elevation percentiles | SRTM aggregation | HIGH |
| IUCN GET code mapping | Lookup table | MEDIUM |
| Frontend map click UI | API routes | MEDIUM |
| Validation framework | All above | MEDIUM |
| Derived topographic variables | SRTM integration | LOW |
| Hydrological variables | New GEE pipeline | LOW |

---

## 10. Gaps & Priorities

### 10.1 Critical Gaps (P0)

| Gap | Current | Target | Effort | Impact |
|-----|---------|--------|--------|--------|
| **Numeric Elevation** | TEXT prose | Percentile ranges | 2-3 days | HIGH |
| **AlphaEarth Scale-Up** | 17,924 species (26%) | 48,000+ species | 4-8 weeks | HIGHEST |
| **EFG Code Mapping** | Names only | IUCN GET codes | 1-2 days | MEDIUM |

### 10.2 High-Value Gaps (P1)

| Gap | Current | Target | Effort | Impact |
|-----|---------|--------|--------|--------|
| **Derived Topographic** | None | Slope, aspect, TWI, TPI | 1 week | MEDIUM |
| **Hydrological Variables** | None | TWI, distance to water | 1 week | MEDIUM |
| **19 BioClim Variables** | 8 | All 19 WorldClim | 1 week | LOW |
| **Soil Hydraulic Properties** | None | Field capacity, wilting point | 1-2 weeks | MEDIUM |

### 10.3 Competitive Comparison

| Variable Category | Treekipedia | Map of Life | NatureServe | eBird | TRY |
|------------------|-------------|-------------|-------------|-------|-----|
| Climate (numeric) | 88.6% | ~60% | ~70% | ~80% | ~30% |
| Soil (numeric) | 66-82% | ~5% | ~20% | N/A | ~25% |
| Elevation (numeric) | 0% → 88%* | ~75% | ~80% | ~90% | ~15% |
| Native Status | 99.99% | ~60% | ~70% | N/A | ~80% |
| Functional Traits | 100% AI | ~30% | ~40% | ~60% | ~15-30% |
| **Prediction Resolution** | **10m AlphaEarth** | 1km | 30m Landsat | 2.5km | N/A |
| Occurrence Storage | L7 geohash (~150m tiles) | 1km grid | 10km grid | 2.5km grid | N/A |

*After SRTM intersection

---

## 11. Research Document Index

### Current (Active)

| Document | Purpose | Location |
|----------|---------|----------|
| **MASTER_PREDICTION_ARCHITECTURE.md** | This file - single source of truth | Here |
| **DYNAMIC_WEIGHTING_FRAMEWORK.md** | Context-adaptive weights (1,337 lines) | Same folder |
| **PROXIMITY_WEIGHTING_STRATEGY.md** | Sampling bias correction | `orchestrator/` |
| **HABITAT_CLUSTERING_STRATEGY_RESEARCH.md** | 3-tier hybrid approach (875 lines) | Same folder |
| **AUDIT_EXISTING_VARIABLES.md** | Complete variable inventory | Same folder |

### Research Documents (Reference)

| Document | Purpose |
|----------|---------|
| `RESEARCH_TOPOGRAPHIC_VARIABLES.md` | Topography/terrain SDM variables |
| `RESEARCH_SOIL_VARIABLES.md` | Soil variables research |
| `RESEARCH_MICROCLIMATE_VARIABLES.md` | Microclimate factors |
| `RESEARCH_HYDROLOGICAL_VARIABLES.md` | Water/riparian variables |
| `RESEARCH_DISTURBANCE_VARIABLES.md` | Land use/disturbance |
| `RESEARCH_FUNCTIONAL_TRAITS.md` | Trait databases (TRY, BIEN) |
| `RESEARCH_RESTORATION_TOOLS.md` | Competitor analysis |
| `SDM_INSTITUTIONAL_RESEARCH.md` | Industry standards |
| `SDM_RESEARCH_EXECUTIVE_SUMMARY.md` | Key findings summary |
| `WEIGHTING_RESEARCH_SUMMARY.md` | Weighting methodology summary |

### Superseded (in `retired/` folder)

| Document | Superseded By |
|----------|---------------|
| `SPECIES_PREDICTOR_RECOMMENDER_STRATEGY.md` | This document |
| `ULTIMATE_PREDICTION_ARCHITECTURE.md` | This document |
| `TREEKIPEDIA_SPECIES_INTELLIGENCE_ARCHITECTURE.md` | This document |
| `OCCURRENCE_WEIGHTING_CLUSTERING_STRATEGY.md` | `PROXIMITY_WEIGHTING_STRATEGY.md` |

---

## Quick Reference

### Database Tables

| Table | Purpose | Records |
|-------|---------|---------|
| `species` | Main species knowledge | 67,743 |
| `species_habitat_centroids` | 64-D centroids per species | Pending |
| `species_elevation_profiles` | Elevation percentiles | Pending |
| `geohash_species_tiles` | STAC-compliant occurrences | 5.7M |
| `ecoregions` | WWF polygons | 847 |
| `intact_forest_landscapes_2021` | IFL polygons | 6,819 |

### Key Functions

```sql
-- Find similar habitats
SELECT * FROM find_similar_habitats(
  query_vector := '[0.1, 0.2, ...]'::vector,
  elevation_min := 1000,
  elevation_max := 2000,
  limit_count := 50
);

-- Check species match at location
SELECT * FROM get_species_habitat_match(
  p_taxon_id := 'wfo-0000723513',
  query_vector := '[0.1, 0.2, ...]'::vector
);
```

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/prediction/sample` | Get embedding for lat/lon |
| `GET /api/prediction/predict` | Scientific suitability (all species) |
| `GET /api/prediction/recommend` | Restoration recommendations (SAFE-B) |
| `GET /api/prediction/species/:taxon_id/habitat-match` | Specific species check |
| `GET /api/geospatial/leaf/score` | LEAF score for ecoregion |

### GEE Assets

| Dataset | GEE Asset |
|---------|-----------|
| AlphaEarth | `projects/ee-caseyodonnell/assets/AlphaEarth` |
| Hansen GFC | `UMD/hansen/global_forest_change_2022_v1_10` |
| SRTM | `USGS/SRTMGL1_003` |
| SoilGrids | `ISRIC/SoilGrids250m_v2_0` |
| TerraClimate | `IDAHO_EPSCOR/TERRACLIMATE` |
| JRC Water | `JRC/GSW1_4/GlobalSurfaceWater` |
| HydroSHEDS | `WWF/HydroSHEDS/15ACC` |

---

**Document Maintainer**: Claude Code
**Last Updated**: January 21, 2026
**Version**: 3.0 (Comprehensive)
