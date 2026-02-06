# Treekipedia Species Intelligence System
## Master Prediction Architecture v2.0 - Complete Synthesis

**Version**: 2.0 (Complete Document - All Sources Consolidated)
**Date**: January 22, 2026
**Purpose**: Single source of truth for Species Predictor/Recommender system
**Supersedes**: All previous architecture documents in `/retired/` folder

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Data Status](#2-current-data-status)
3. [System Architecture](#3-system-architecture)
4. [Environmental Variables - Complete Inventory](#4-environmental-variables---complete-inventory)
5. [External Datasets Required](#5-external-datasets-required)
6. [SAFE-B Scoring Framework](#6-safe-b-scoring-framework)
7. [Dynamic Weighting Framework](#7-dynamic-weighting-framework)
8. [Clustering & Bias Correction](#8-clustering--bias-correction)
9. [API Design](#9-api-design)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Competitive Position](#11-competitive-position)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### 1.1 What We're Building

Two interconnected prediction systems:

| System | Question Answered | Use Case |
|--------|------------------|----------|
| **Species Predictor** | "What CAN grow here?" | Scientific analysis, range mapping, historical reconstruction |
| **Species Recommender** | "What SHOULD I plant here?" | Restoration planning, native species selection, goal-oriented recommendations |

### 1.2 Current Data Status (Verified January 22, 2026)

| Asset | Status | Details |
|-------|--------|---------|
| **AlphaEarth v4 (COMPLETE)** | ✅ Downloaded | `alphaearth_embeddings_v4_COMPLETE.parquet` (277MB) |
| v4 Contents | ✅ Verified | Phase 1 embeddings + elevation + forest state |
| Species in Database | 67,743 | 50,797 species + 16,946 subspecies |
| Species with Occurrences | 48,129 | 71% have geohash occurrence data |
| Geohash Tiles | 5,786,835 | L7 precision (~150m) |
| PostgreSQL Schema | ✅ Ready | pgvector 0.8.1, migration 007 applied |

### 1.3 Key Competitive Advantages

| Feature | Treekipedia | Best Competitor | Advantage |
|---------|-------------|-----------------|-----------|
| Resolution | 10m (AlphaEarth) | 30m-1km | 3-100× finer |
| Native Status | 99.99% WCVP | ~60-70% | 30%+ more |
| Biotic Interactions | 100% GloBI | None | Unique |
| Soil Data | 66-82% | ~25% | 2-3× more |
| Blockchain Provenance | ✅ EAS | None | Unique |

---

## 2. Current Data Status

### 2.1 AlphaEarth v4 - COMPLETE

**File Location**: `orchestrator/bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet`

**Contents** (Phase 1 - 2017-2024 occurrences):
- 64-dimensional satellite embeddings (AlphaEarth Foundation Model)
- Elevation data (SRTM 30m)
- Forest state variables (Hansen Global Forest Change)

**Next Steps**:
1. Run weighted clustering pipeline
2. Load centroids to PostgreSQL `species_habitat_centroids`
3. Integrate with prediction API

### 2.2 Existing Database Coverage

| Variable Category | Coverage | Fields | Source |
|-------------------|----------|--------|--------|
| **Climate** | 88.6% | 8 variables (precip, temp, seasonality) | WorldClim |
| **Soil** | 66-82% | 12 variables (pH, texture, OC) | SoilGrids250m |
| **Native Status** | 99.99% | wcvp_native, wcvp_introduced | WCVP (Kew) |
| **Ecoregions** | 100% | ecoregions, biomes, bioregions | WWF/One Earth |
| **Functional Traits** | 100% AI | 35+ traits | GPT-4o research |
| **Biotic Interactions** | 100% | 8 interaction types | GloBI |
| **Elevation** | 0% numeric | Text prose only | 🔴 CRITICAL GAP |
| **Topographic Derivatives** | 0% | slope, aspect, TWI, TPI | 🟡 Not derived |

### 2.3 What's Missing (Gaps)

| Gap | Priority | Status | Effort |
|-----|----------|--------|--------|
| Numeric elevation percentiles | 🔴 CRITICAL | v4 has raw elevation, needs aggregation | 2-3 days |
| Topographic derivatives (slope, aspect, TWI) | 🟡 HIGH | Can derive from elevation | 1 week |
| Additional climate variables (19 BioClim) | 🟡 HIGH | Only 8 of 19 integrated | 1 week |
| Hydrological variables (distance to water, TWI) | 🟡 HIGH | Not integrated | 1 week |
| Disturbance history (Hansen loss year) | 🟡 HIGH | In v4, needs clustering integration | 1 week |
| Fire frequency | 🟢 MEDIUM | MODIS available in GEE | 2-3 days |
| Human Footprint Index | 🟢 MEDIUM | WCS dataset, needs GEE upload | 1-2 days |

---

## 3. System Architecture

### 3.1 The Two-System Split

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      USER REQUEST: (latitude, longitude)                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
┌───────────────────────────┐    ┌────────────────────────────────────────┐
│        PREDICTOR          │    │            RECOMMENDER                  │
│  "What CAN grow here?"    │    │      "What SHOULD I plant?"            │
├───────────────────────────┤    ├────────────────────────────────────────┤
│ • Pure habitat suitability│    │ • SAFE-B scoring framework             │
│ • Includes ALL species    │    │ • Excludes invasive species            │
│ • Even invasives shown    │    │ • Matches restoration goals            │
│ • Scientific analysis     │    │ • Practical recommendations            │
│                           │    │                                        │
│ Outputs:                  │    │ Outputs:                               │
│ - Cosine similarity score │    │ - SAFE-B weighted score                │
│ - Habitat match %         │    │ - Explanation of why                   │
│ - "Invasive" flag         │    │ - Goal alignment %                     │
└───────────────────────────┘    └────────────────────────────────────────┘
```

### 3.2 The 5-Layer Intelligence Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TREEKIPEDIA INTELLIGENCE STACK                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LAYER 1: SPECIES PREDICTOR (AlphaEarth)                                │
│  "Where can this species survive?"                                       │
│  └── 64-D embeddings × cosine similarity → habitat match                │
│      STATUS: v4 COMPLETE, clustering pending                            │
│                                                                          │
│  LAYER 2: SPECIES RECOMMENDER (SAFE-B Score)                            │
│  "What trees should I plant here?"                                       │
│  └── Spatial + Abiotic + Functional + Ecosystem + Biotic               │
│      STATUS: Framework designed, not yet implemented                     │
│                                                                          │
│  LAYER 3: STRATEGY FILTER                                                │
│  "What's the best approach for my goals?"                               │
│  └── Rewilding | Agroforestry | Riparian | Carbon | Biodiversity        │
│      STATUS: Conceptual, not yet implemented                            │
│                                                                          │
│  LAYER 4: BIODIVERSITY INTELLIGENCE                                      │
│  "What ecological interactions exist?"                                   │
│  └── GloBI data → trophic networks → species interaction richness       │
│      STATUS: Data imported (V11), frontend not built                    │
│                                                                          │
│  LAYER 5: AI RESEARCH ENRICHMENT                                        │
│  "Fill knowledge gaps automatically"                                     │
│  └── Claude agents → 35-field extraction → quality synthesis            │
│      STATUS: Agentic research architecture complete                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Technology Foundation

| Component | Technology | Status |
|-----------|------------|--------|
| Satellite Embeddings | AlphaEarth 64-D (10m resolution) | v4 COMPLETE |
| Vector Database | PostgreSQL + pgvector 0.8.1 | Schema ready |
| Occurrence Data | 5.7M L7 geohash tiles | Integrated |
| Spatial Analysis | PostGIS 3.6.0 | Integrated |
| Prediction Service | Python (location_predictor_FIXED.py) | Running on port 5002 |
| API Backend | Node.js/Express (server.js) | Running on port 5001 |

---

## 4. Environmental Variables - Complete Inventory

This section consolidates ALL environmental variables from research documents.

### 4.1 Climate / Microclimate Variables

**Primary Source**: CHELSA V2.1 (1km) - Recommended for ecological modeling
**Secondary Source**: WorldClim V2.1 (1km) - Currently integrated

#### 4.1.1 Currently Integrated (8 variables, 88.6% coverage)

| Variable | Field Name | Format | Source |
|----------|-----------|--------|--------|
| Annual Precipitation | `annual_precipitation_mm` | min;max percentile | WorldClim |
| Annual Temperature Range | `annual_temperature_range_c` | min;max percentile | WorldClim |
| Köppen-Geiger Climate | `climate_type_koppengeiger` | Categorical codes | Köppen-Geiger |
| Wettest Month Precip | `wettest_month_precipitation_mm` | min;max percentile | WorldClim |
| Driest Month Precip | `driest_month_precipitation_mm` | min;max percentile | WorldClim |
| Precipitation Seasonality | `precipitation_seasonality_cv` | min;max percentile | WorldClim |
| Wettest Quarter Precip | `wettest_quarter_precipitation_mm` | min;max percentile | WorldClim |
| Driest Quarter Precip | `driest_quarter_precipitation_mm` | min;max percentile | WorldClim |

#### 4.1.2 Standard BioClim Variables (19 total - 11 TO ADD)

| BIO Variable | Name | Ecological Significance | Status |
|--------------|------|-------------------------|--------|
| **BIO1** | Annual Mean Temperature | General thermal conditions | TO ADD |
| **BIO2** | Mean Diurnal Range | Daily temperature fluctuation | TO ADD |
| **BIO3** | Isothermality | Temperature constancy | TO ADD |
| **BIO4** | Temperature Seasonality | Variability (std dev) | TO ADD |
| **BIO5** | Max Temp of Warmest Month | Heat stress limit | TO ADD |
| **BIO6** | Min Temp of Coldest Month | **Cold tolerance limit (CRITICAL)** | TO ADD |
| **BIO7** | Temperature Annual Range | Overall thermal range | TO ADD |
| **BIO8** | Mean Temp of Wettest Quarter | Growing season conditions | TO ADD |
| **BIO9** | Mean Temp of Driest Quarter | Dry season conditions | TO ADD |
| **BIO10** | Mean Temp of Warmest Quarter | Warm season conditions | TO ADD |
| **BIO11** | Mean Temp of Coldest Quarter | Cold season severity | TO ADD |
| BIO12 | Annual Precipitation | ✅ HAVE (`annual_precipitation_mm`) | HAVE |
| BIO13 | Precip of Wettest Month | ✅ HAVE | HAVE |
| BIO14 | Precip of Driest Month | **Drought stress limit (CRITICAL)** | HAVE |
| BIO15 | Precipitation Seasonality | ✅ HAVE | HAVE |
| BIO16 | Precip of Wettest Quarter | ✅ HAVE | HAVE |
| BIO17 | Precip of Driest Quarter | ✅ HAVE | HAVE |
| BIO18 | Precip of Warmest Quarter | Summer water availability | TO ADD |
| BIO19 | Precip of Coldest Quarter | Winter water availability | TO ADD |

#### 4.1.3 Derived Climate Variables (TO ADD)

| Variable | Formula/Source | Ecological Significance |
|----------|---------------|------------------------|
| **Frost-Free Days** | Count(daily min temp > 0°C) | Growing season length |
| **Growing Degree Days (GDD)** | Sum(daily mean temp - base temp) | Energy for growth |
| **Potential Evapotranspiration (PET)** | TerraClimate | Water demand |
| **Aridity Index** | Precipitation / PET | Drought stress |
| **Vapor Pressure Deficit (VPD)** | CHELSA | Atmospheric drought |
| **Cold Air Drainage Risk** | TPI × elevation derivative | Frost pocket identification |

**GEE Asset**: `projects/earthengine-legacy/assets/projects/climate-engine/chelsa/v2_1/`

---

### 4.2 Soil Variables

**Primary Source**: OpenLandMap (30m) - Recommended for resolution
**Secondary Source**: SoilGrids250m (250m) - Currently integrated

#### 4.2.1 Currently Integrated (12 variables, 66-82% coverage)

| Variable | Field Name | Format | Coverage |
|----------|-----------|--------|----------|
| Soil pH (Dominant) | `ph_dominant` | Categorical | 81.9% |
| Soil pH (All) | `ph_all` | Semicolon list | 100% |
| Soil pH (Preferred) | `ph_prefered` | Categorical | 100% |
| Soil pH (Tolerated) | `ph_tolerated` | Categorical | 100% |
| Soil Texture (Dominant) | `soil_texture_dominant` | Categorical | 66.2% |
| Soil Texture (All) | `soil_texture_all` | Semicolon list | 100% |
| Soil Texture (Preferred) | `soil_texture_prefered` | Categorical | 100% |
| Soil Texture (Tolerated) | `soil_texture_tolerated` | Categorical | 100% |
| Organic Carbon (Dominant) | `oc_dominant` | min;max percentile | 100% |
| Organic Carbon (All) | `oc_all` | Semicolon list | 100% |
| Organic Carbon (Preferred) | `oc_prefered` | min;max percentile | 100% |
| Organic Carbon (Tolerated) | `oc_tolerated` | min;max percentile | 100% |

#### 4.2.2 Advanced Soil Variables (TO ADD)

| Variable | Description | Ecological Significance | Source |
|----------|-------------|------------------------|--------|
| **Cation Exchange Capacity (CEC)** | Nutrient holding capacity | Soil fertility proxy | SoilGrids |
| **Bulk Density** | Compaction measure (g/cm³) | Root penetration limit | OpenLandMap |
| **Available Water Capacity (AWC)** | Plant-available water | Drought resilience | SoilGrids |
| **Depth to Bedrock** | Rooting volume limit | Max root depth constraint | SoilGrids |
| **Soil Erodibility (K-factor)** | Erosion susceptibility | Soil stability | Derived |
| **Soil Drainage Class** | Water movement rate | Aeration, waterlogging | SoilGrids |
| **Nitrogen Content (N)** | Primary nutrient | Growth rate | SoilGrids |
| **Clay Content (%)** | Fine particle fraction | Water retention | OpenLandMap |
| **Sand Content (%)** | Coarse particle fraction | Drainage | OpenLandMap |
| **Silt Content (%)** | Medium particle fraction | Structure | OpenLandMap |

**GEE Assets**:
- SoilGrids: `projects/soilgrids-isric/assets/`
- OpenLandMap: Search GEE catalog for "OpenLandMap"

---

### 4.3 Topographic Variables

**Primary Source**: SRTM GL1 (30m) - Already in v4 data
**Secondary Source**: Copernicus DEM (30m) - Global alternative

#### 4.3.1 Currently Available (in v4 data)

| Variable | Description | Status |
|----------|-------------|--------|
| **Elevation** | Meters above sea level | ✅ In v4, needs percentile aggregation |

#### 4.3.2 Topographic Derivatives (TO DERIVE)

| Variable | Formula | Ecological Significance |
|----------|---------|------------------------|
| **Slope** | First derivative of elevation | Drainage, soil stability, erosion |
| **Aspect** | Direction of slope face (0-360°) | Solar exposure, microclimate |
| **Topographic Position Index (TPI)** | Elevation - FocalMean(Elevation) | Ridges (+) vs valleys (-) |
| **Topographic Wetness Index (TWI)** | ln(Upslope Area / tan(Slope)) | Soil moisture proxy |
| **Terrain Ruggedness Index (TRI)** | Mean(|Center - Neighbors|) | Habitat heterogeneity |
| **Solar Radiation Index** | f(latitude, slope, aspect) | Energy/temperature proxy |
| **Curvature (Profile/Plan)** | Second derivative | Flow acceleration, convergence |
| **Landform Classification** | Derived from TPI + slope | Ridge, valley, slope, flat |

**GEE Asset**: `USGS/SRTMGL1_003`

#### 4.3.3 Implementation for Species Profiling

```python
# Target elevation percentiles per species
species_elevation_profiles = {
    'elevation_min': Integer,
    'elevation_p10': Integer,
    'elevation_p25': Integer,
    'elevation_median': Integer,
    'elevation_p75': Integer,
    'elevation_p90': Integer,
    'elevation_max': Integer,
    'elevation_stddev': Float,
    'slope_mean': Float,
    'aspect_dominant': String,  # N/S/E/W
    'twi_mean': Float,
    'tpi_mean': Float
}
```

---

### 4.4 Hydrological Variables

**Primary Sources**: JRC Global Surface Water, HydroSHEDS

#### 4.4.1 Variables to Integrate

| Variable | Description | Ecological Significance | GEE Asset |
|----------|-------------|------------------------|-----------|
| **Distance to Water** | Meters to nearest water body | Water accessibility | JRC Global Surface Water |
| **Flow Accumulation** | Upstream contributing area | Stream size proxy | HydroSHEDS |
| **Stream Order** | Strahler stream order | River size/type | HydroSHEDS |
| **Flood Frequency** | Historic flood events | Flood tolerance requirement | Global Flood Database |
| **Surface Water Presence** | Permanent vs seasonal | Water reliability | JRC |
| **Topographic Wetness Index** | See Topographic section | Soil moisture | Derived from DEM |

**GEE Assets**:
- JRC: `JRC/GSW1_4/GlobalSurfaceWater`
- HydroSHEDS: Available in GEE
- Global Flood Database: `GLOBAL_FLOOD_DB`

#### 4.4.2 Implementation Priority

| Variable | Priority | Effort | Impact |
|----------|----------|--------|--------|
| TWI | HIGH | Derive from DEM | Soil moisture |
| Distance to Water | HIGH | Calculate from JRC | Riparian species |
| Flow Accumulation | MEDIUM | From HydroSHEDS | Stream size |
| Flood Frequency | MEDIUM | From GFD | Flood tolerance |

---

### 4.5 Disturbance Variables

**Primary Source**: Hansen Global Forest Change (30m, 2000-2024)
**Secondary Sources**: MODIS Burned Area, Human Footprint Index, HILDA+

#### 4.5.1 Currently Available (in v4 data)

| Variable | Description | Status |
|----------|-------------|--------|
| **Tree Cover 2000** | Baseline canopy % | ✅ In v4 |
| **Forest Loss** | Binary loss flag | ✅ In v4 |
| **Loss Year** | Year of loss (1-24 = 2001-2024) | ✅ In v4 |
| **Forest Gain** | Binary gain 2000-2012 | ✅ In v4 |

#### 4.5.2 Derived Variables (TO CALCULATE)

| Variable | Formula | Ecological Significance |
|----------|---------|------------------------|
| **Years Since Loss** | 2024 - (2000 + lossyear) | Successional stage |
| **Fire Frequency** | Count(MODIS burned 2000-2024) | Fire adaptation |
| **Years Since Fire** | 2024 - last burn year | Recovery stage |
| **Distance to Forest Edge** | fastDistanceTransform(forest mask) | Edge vs interior |
| **Patch Size** | connectedPixelCount | Area-sensitive species |
| **Core Area Fraction** | Area >100m from edge / patch area | Interior habitat quality |

#### 4.5.3 External Disturbance Datasets (TO INTEGRATE)

| Dataset | Resolution | Temporal | Priority | GEE Asset |
|---------|------------|----------|----------|-----------|
| **Hansen Forest Change** | 30m | 2000-2024 | ✅ HAVE | `UMD/hansen/global_forest_change_2024_v1_12` |
| **MODIS Burned Area** | 500m | 2000-present | HIGH | `MODIS/061/MCD64A1` |
| **Human Footprint Index** | 100m-1km | 2000-2020 | HIGH | External (WCS) |
| **HILDA+ Land Use** | 1km | 1960-2020 | MEDIUM | External (PANGAEA) |
| **LANDFIRE MFRI** | 30m | Historical | MEDIUM (US only) | `LANDFIRE/Fire/MFRI/v1_2_0` |
| **Dynamic World** | 10m | 2015-present | MEDIUM | `GOOGLE/DYNAMICWORLD/V1` |

#### 4.5.4 Successional Stage Classification

```python
# Time since disturbance → Successional stage
def classify_successional_stage(years_since_loss):
    if years_since_loss is None:
        return "continuous_forest"  # No detected loss
    elif years_since_loss < 5:
        return "early_succession"   # Pioneers, herbaceous
    elif years_since_loss < 15:
        return "mid_succession"     # Young forest, shrubs
    elif years_since_loss < 30:
        return "late_succession"    # Maturing forest
    else:
        return "old_secondary"      # Old secondary growth
```

---

### 4.6 Functional Traits

**Primary Sources**: TRY Database, BIEN, GRooT (roots)
**Current Status**: 100% AI-generated coverage (35+ traits), validation ongoing

#### 4.6.1 Currently Integrated (AI-generated)

| Trait Category | Fields | Coverage |
|----------------|--------|----------|
| Growth Form | growth_form_ai | 100% |
| Leaf Type | leaf_type_ai | 100% |
| Deciduousness | deciduous_evergreen_ai | 100% |
| Maximum Height | maximum_height_ai | 100% |
| Maximum Diameter | maximum_diameter_ai | 100% |
| Lifespan | lifespan_ai | 100% |
| Successional Stage | successional_stage | 100% |
| Tolerances | tolerances_ai (shade, drought, flood, salt, frost, fire) | 100% |
| Forest Layers | forest_layers | 100% |
| Climate Tolerance | climate_tolerance_ai | 100% |

#### 4.6.2 Key Traits for Restoration (TO VALIDATE/ENRICH)

| Trait | Description | Use Case | Source |
|-------|-------------|----------|--------|
| **Maximum Rooting Depth** | Deepest root penetration | Drought tolerance | GRooT |
| **Specific Leaf Area (SLA)** | Leaf area / dry mass | Resource acquisition strategy | TRY, BIEN |
| **Wood Density** | Dry mass / volume | Drought resistance, longevity | TRY, BIEN |
| **Nitrogen Fixation** | Symbiotic N-fixing ability | Soil enrichment | TRY |
| **Specific Root Length (SRL)** | Root length / dry mass | Soil binding, erosion control | GRooT |
| **Seed Mass** | Average seed weight | Dispersal strategy | TRY |
| **Leaf Nitrogen Content** | N concentration in leaves | Decomposition rate | TRY |

#### 4.6.3 Trait Database Access

| Database | Species | Traits | Access Method |
|----------|---------|--------|---------------|
| **TRY** | 280,000+ | 2,600+ | Register + Data Explorer or `tryr` R package |
| **BIEN** | Western Hemisphere | 53 traits | `BIEN` R package |
| **GRooT** | Global | 38 root traits | GitHub CSV + R scripts |

---

### 4.7 Biotic Interactions

**Source**: GloBI (Global Biotic Interactions)
**Status**: 100% field coverage (may be empty for under-documented species)

#### 4.7.1 Currently Integrated (8 interaction types)

| Interaction Type | Field Name | Example Taxa |
|------------------|-----------|--------------|
| Pollinated By | `globi_pollinatedby` | Apis mellifera, Bombus spp. |
| Eaten By | `globi_eatenby` | Cervus canadensis, Sciurus spp. |
| Flowers Visited By | `globi_flowersvisitedby` | Lepidoptera, Diptera |
| Has Parasite | `globi_hasparasite` | Mistletoe, fungi |
| Has Pathogen | `globi_haspathogen` | Phytophthora, rusts |
| Has Dispersal Vector | `globi_hasdispersalvector` | Birds, mammals |
| Preyed Upon By | `globi_preyeduponby` | Herbivores |
| Has Parasitoid | `globi_hasparasitoid` | Wasps, flies |

#### 4.7.2 Derived Metrics

| Metric | Formula | Use Case |
|--------|---------|----------|
| Pollinator Richness | Count(unique pollinators) | Pollination dependency |
| Herbivore Pressure | Count(unique herbivores) | Browsing risk |
| Disperser Richness | Count(unique dispersers) | Colonization potential |
| Pathogen Load | Count(unique pathogens) | Disease risk |

---

### 4.8 Biogeographic Variables

**Status**: 85-100% coverage

#### 4.8.1 Currently Integrated

| Variable | Field Name | Coverage | Source |
|----------|-----------|----------|--------|
| Ecoregions | `ecoregions` | 100% | WWF/One Earth |
| Biomes | `biomes` | 100% | WWF |
| Bioregions | `bioregions` | 100% | Biogeographic realms |
| SBTN Land Cover | `sbtn_landcover` | 85.3% | SBTN classification |
| Vegetation Type | `vegetationtype` | 99.8% | Vegetation classification |
| Functional Ecosystem Groups | `functional_ecosystem_groups` | 91.9% | IUCN GET (names only) |
| Intact Forest Presence | `present_intact_forest` | 100% | IFL 2021 |

#### 4.8.2 Missing: IUCN GET Codes

**Issue**: Have ecosystem names ("Tropical dry forests") but not codes ("T1.1")
**Impact**: Can't do structured ecosystem matching
**Fix**: Create mapping table from names to codes

---

## 5. External Datasets Required

### 5.1 Datasets to Download/Upload to GEE

| Dataset | URL/Source | Resolution | Use Case | Priority |
|---------|------------|------------|----------|----------|
| **Human Footprint Index** | [WCS Portal](https://wcshumanfootprint.org/) | 100m-1km | Disturbance pressure | HIGH |
| **HILDA+ v2.0** | [PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.974335) | 1km | Land use history 1960-2020 | MEDIUM |
| **TRY Traits** | [TRY-db.org](https://www.try-db.org/) | Species-level | Trait validation | HIGH |
| **BIEN Traits** | `BIEN` R package | Species-level | American species traits | MEDIUM |
| **GRooT Root Traits** | [GitHub](https://github.com/MathieuTWOTWO/GRooT) | Species-level | Root depth, erosion control | HIGH |

### 5.2 GEE Assets Already Available

| Dataset | GEE Asset ID | Resolution | Use Case |
|---------|-------------|------------|----------|
| Hansen Forest Change | `UMD/hansen/global_forest_change_2024_v1_12` | 30m | Loss/gain/year |
| SRTM Elevation | `USGS/SRTMGL1_003` | 30m | Topography |
| CHELSA Climate | `projects/earthengine-legacy/assets/projects/climate-engine/chelsa/v2_1/` | 1km | BioClim variables |
| JRC Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | 30m | Distance to water |
| MODIS Burned Area | `MODIS/061/MCD64A1` | 500m | Fire frequency |
| SoilGrids | `projects/soilgrids-isric/assets/` | 250m | Soil properties |
| LANDFIRE MFRI | `LANDFIRE/Fire/MFRI/v1_2_0` | 30m | Fire return interval (US) |
| Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | 10m | Land cover 2015+ |

### 5.3 Data Acquisition Priorities

| Priority | Dataset | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 P0 | Aggregate elevation percentiles from v4 | 2-3 days | Enables elevation filtering |
| 🔴 P0 | Derive slope/aspect/TWI from elevation | 1 week | Microclimate modeling |
| 🟡 P1 | Integrate CHELSA BioClim (all 19) | 1 week | Full climate envelope |
| 🟡 P1 | Calculate distance to water (JRC) | 2-3 days | Riparian species |
| 🟡 P1 | Download TRY/BIEN traits | 1 week | Trait validation |
| 🟢 P2 | Upload Human Footprint Index | 1-2 days | Disturbance pressure |
| 🟢 P2 | Upload HILDA+ land use | 3-4 days | Agricultural legacy |

---

## 6. SAFE-B Scoring Framework

### 6.1 Component Definitions

| Component | Weight Range | Description | Data Sources |
|-----------|--------------|-------------|--------------|
| **S**patial | 10-30% | Occurrence density, range overlap, native status | Geohash tiles, WCVP |
| **A**biotic | 15-35% | Climate, soil, topography, hydrology match | WorldClim, SoilGrids, SRTM |
| **F**unctional | 15-50% | Trait suitability for restoration goals | AI traits, TRY, BIEN |
| **E**cosystem | 15-30% | Ecoregion, biome, GET match | WWF, IUCN GET |
| **B**iotic | 5-25% | Pollinator/disperser availability, pathogen risk | GloBI |

### 6.2 Strategy-Specific Weight Profiles

| Strategy | S | A | F | E | B | Key Traits Boosted |
|----------|---|---|---|---|---|-------------------|
| **Rewilding** | 20% | 15% | 10% | 30% | 25% | Native status, ecological function |
| **Agroforestry** | 10% | 25% | 40% | 15% | 10% | Fast growth, multi-use, marketability |
| **Riparian** | 15% | 35% | 20% | 20% | 10% | Flood tolerance, bank stabilization |
| **Carbon** | 10% | 20% | 50% | 15% | 5% | Biomass accumulation, longevity |
| **Biodiversity** | 15% | 15% | 20% | 25% | 25% | Fauna support, keystone role |

### 6.3 Hard Filters (Pass/Fail Before Scoring)

| Filter | Rule | Rationale |
|--------|------|-----------|
| **Native Status** | Include only if native to target region | Recommender excludes invasives |
| **Elevation** | Species p10 ≤ target ≤ species p90 | Physical survival limit |
| **Climate Envelope** | Target within species precip/temp range | Survival threshold |
| **Threatened Status** | Warn if IUCN CR/EN (don't exclude) | Conservation consideration |

### 6.4 Scoring Algorithm

```python
def calculate_safeb_score(species, location, strategy):
    """
    Calculate SAFE-B recommendation score for a species at a location.
    """
    # Get strategy-specific weights
    weights = STRATEGY_WEIGHTS[strategy]

    # Apply hard filters first
    if not passes_hard_filters(species, location):
        return None

    # Calculate component scores (0-1 each)
    S = calculate_spatial_score(species, location)      # Occurrence + native
    A = calculate_abiotic_score(species, location)      # Climate + soil + topo
    F = calculate_functional_score(species, strategy)   # Trait match to goals
    E = calculate_ecosystem_score(species, location)    # Ecoregion + biome
    B = calculate_biotic_score(species, location)       # Interactions viability

    # Weighted sum
    score = (
        weights['S'] * S +
        weights['A'] * A +
        weights['F'] * F +
        weights['E'] * E +
        weights['B'] * B
    )

    return {
        'total_score': score,
        'components': {'S': S, 'A': A, 'F': F, 'E': E, 'B': B},
        'strategy': strategy,
        'explanation': generate_explanation(species, components)
    }
```

---

## 7. Dynamic Weighting Framework

### 7.1 Core Principle

**Weights are FUNCTIONS of context, not static constants.**

### 7.2 Five Layers of Context Adaptation

#### Layer 1: Spatial Scale

| Scale | Radius | Dominant Factors | Weight Emphasis |
|-------|--------|------------------|-----------------|
| Microhabitat | <1km | Soil, topography, wetness | Landtype 25%, Soil 20% |
| Landscape | 1-10km | Land use, forest continuity | Embedding 22%, Occurrence 18% |
| Regional | 10-100km | Climate, ecoregion, elevation | Climate 28%, Ecoregion 22% |
| Continental | >100km | Biome, biogeography | Ecoregion 35%, Climate 30% |

#### Layer 2: Environmental vs. Biotic Filtering

| Scale | Environmental | Biotic | Implication |
|-------|--------------|--------|-------------|
| Large | Dominant | Weak | Boost climate, reduce occurrence |
| Small | Weaker | Stronger | Boost occurrence, reduce climate |

#### Layer 3: Successional Stage

| Stage | Boost | Penalize |
|-------|-------|----------|
| Bare soil | Pioneer, N-fixers, fast growth | Climax, shade-tolerant |
| Early (<10yr) | Fast colonizers | Slow-growing climax |
| Mid (10-50yr) | Competitive strategists | Pioneers |
| Late (>50yr) | Shade-tolerant, specialists | Pioneers, generalists |

#### Layer 4: Restoration Strategy

(See SAFE-B Strategy Weights in Section 6.2)

#### Layer 5: Data Quality Tiers

| Tier | Embedding Weight | Occurrence Weight | Climate Weight |
|------|-----------------|------------------|----------------|
| High (2017-2024 AlphaEarth) | 1.0× | 1.0× | 1.0× |
| Medium (reconstruction) | 0.6× | 1.3× | 1.2× |
| Low (pre-satellite) | 0.3× | 1.2× | 1.5× |

### 7.3 Implementation Architecture

```python
class ContextAdaptiveWeighting:
    def get_weights(self, location, restoration_strategy):
        # Layer 1: Spatial scale → base weights
        scale = detect_scale(location.aoi_radius_km)
        weights = spatial_baseline_weights(scale)

        # Layer 2: Environmental vs biotic filtering
        weights = apply_ecological_filtering(weights, scale)

        # Layer 3: Successional stage adjustments
        stage = detect_successional_stage(location)
        weights = apply_temporal_context(weights, stage)

        # Layer 4: Restoration strategy boosting
        weights = apply_strategy_weights(weights, restoration_strategy)

        # Layer 5: Data quality confidence
        confidence = assess_data_quality(location)
        weights = apply_confidence_weighting(weights, confidence)

        return normalize(weights)  # Sum to 1.0
```

---

## 8. Clustering & Bias Correction

### 8.1 Why Clustering?

Species occupy multiple distinct habitat types. A single centroid would average across:
- Different elevations (montane vs lowland populations)
- Different climates (Mediterranean vs temperate occurrences)
- Different land uses (urban parks vs natural forests)

**Solution**: 3-10 habitat clusters per species, each representing a distinct habitat niche.

### 8.2 Proximity-Based Density Weighting

**Key Insight**: Sampling bias is SPATIAL, not per-pixel.

**Problem**: Research station with 1000 observations in 1 hectare should NOT have 1000× influence of 5 observations across 1000 hectares.

**Solution**: Multi-scale geohash density weighting

```python
def compute_multiscale_density_weights(lats, lons):
    """
    Three scales capture different bias patterns:
    - Local (precision 6, ~1.2km): Research station clusters
    - Regional (precision 5, ~5km): City/road bias
    - Broad (precision 4, ~40km): Continental sampling patterns
    """
    gh_local = [geohash.encode(lat, lon, 6) for lat, lon in zip(lats, lons)]
    gh_regional = [geohash.encode(lat, lon, 5) for lat, lon in zip(lats, lons)]
    gh_broad = [geohash.encode(lat, lon, 4) for lat, lon in zip(lats, lons)]

    counts_local = Counter(gh_local)
    counts_regional = Counter(gh_regional)
    counts_broad = Counter(gh_broad)

    # Weight combination: 0.5 local + 0.3 regional + 0.2 broad
    combined_density = (
        0.5 * np.array([counts_local[gh] for gh in gh_local]) +
        0.3 * np.array([counts_regional[gh] for gh in gh_regional]) +
        0.2 * np.array([counts_broad[gh] for gh in gh_broad])
    )

    # Log-inverse: high density = low weight
    weights = 1.0 / np.log1p(combined_density)
    return weights / weights.max()
```

### 8.3 Clustering Pipeline

**File**: `orchestrator/cluster_habitat_centroids_weighted.py`

**Input**: `alphaearth_embeddings_v4_COMPLETE.parquet`

**Process**:
1. Load embeddings with proximity-based weights
2. For each species with >10 occurrences:
   - Determine optimal K (3-10 clusters) via silhouette score
   - Run weighted K-means on 64-D embeddings
   - Compute weighted centroid per cluster
   - Calculate effective sample size (ESS)
3. Output cluster metadata:
   - `centroid_vector` (64-D)
   - `occurrence_count`
   - `effective_sample_size`
   - `mean_elevation`, `elevation_std`
   - `mean_treecover2000`, `forest_loss_fraction`
   - `representative_lat/lon`

### 8.4 Database Schema

```sql
CREATE TABLE species_habitat_centroids (
    taxon_id VARCHAR(50) REFERENCES species(taxon_id),
    cluster_id INTEGER,  -- 0-9 per species
    centroid_vector vector(64),  -- pgvector 64-D
    occurrence_count INTEGER,
    effective_sample_size FLOAT,  -- Bias-corrected
    mean_elevation FLOAT,
    elevation_std FLOAT,
    mean_treecover2000 FLOAT,
    forest_loss_fraction FLOAT,
    representative_lat FLOAT,
    representative_lon FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (taxon_id, cluster_id)
);

-- IVFFlat index for cosine similarity
CREATE INDEX idx_centroid_vector
ON species_habitat_centroids
USING ivfflat (centroid_vector vector_cosine_ops)
WITH (lists = 100);
```

---

## 9. API Design

### 9.1 Prediction Endpoints

#### GET /api/predict/species

**Purpose**: Get species suitable for a location (Predictor)

```json
// Request
GET /api/predict/species?lat=-23.55&lon=-46.63&limit=20

// Response
{
  "location": {
    "lat": -23.55,
    "lon": -46.63,
    "country": "BRA",
    "ecoregion": "Atlantic Forest"
  },
  "predictions": [
    {
      "taxon_id": "6290",
      "species_name": "Cedrela fissilis",
      "cosine_similarity": 0.94,
      "habitat_match_pct": 87,
      "native_status": "native",
      "invasive_flag": false,
      "confidence": "high"
    }
  ],
  "query_embedding": [0.12, -0.34, ...],  // 64-D
  "model_version": "v4_alpha"
}
```

#### GET /api/recommend/species

**Purpose**: Get species recommendations for restoration (Recommender)

```json
// Request
GET /api/recommend/species?lat=-23.55&lon=-46.63&strategy=rewilding&limit=10

// Response
{
  "location": {...},
  "strategy": "rewilding",
  "recommendations": [
    {
      "taxon_id": "6290",
      "species_name": "Cedrela fissilis",
      "safeb_score": 0.89,
      "components": {
        "spatial": 0.92,
        "abiotic": 0.88,
        "functional": 0.85,
        "ecosystem": 0.95,
        "biotic": 0.82
      },
      "explanation": "Native to Atlantic Forest, excellent habitat match...",
      "traits_aligned": ["native", "shade_tolerant", "wildlife_support"]
    }
  ],
  "filters_applied": ["native_only", "elevation_compatible"]
}
```

### 9.2 Analysis Endpoints

#### GET /api/species/:taxon_id/distribution

**Purpose**: Get predicted distribution for a species

```json
// Response
{
  "taxon_id": "6290",
  "species_name": "Cedrela fissilis",
  "habitat_clusters": [
    {
      "cluster_id": 0,
      "representative_location": {"lat": -23.5, "lon": -46.6},
      "occurrence_count": 1234,
      "elevation_range": {"min": 200, "median": 600, "max": 1200},
      "climate_summary": "Tropical/subtropical humid"
    }
  ],
  "predicted_range_km2": 450000,
  "ecoregions": ["Atlantic Forest", "Cerrado"],
  "native_countries": ["BRA", "ARG", "PRY"]
}
```

### 9.3 Batch Endpoints

#### POST /api/predict/batch

**Purpose**: Predict for multiple locations (e.g., project polygon)

```json
// Request
{
  "locations": [
    {"lat": -23.55, "lon": -46.63},
    {"lat": -23.56, "lon": -46.64}
  ],
  "strategy": "agroforestry",
  "limit_per_location": 10
}

// Response
{
  "results": [
    {"location": {...}, "recommendations": [...]},
    {"location": {...}, "recommendations": [...]}
  ],
  "species_richness": 45,
  "common_species": ["species_id_1", "species_id_2", ...]
}
```

---

## 10. Implementation Roadmap

### 10.1 Phase 1: Core Prediction (4-6 weeks)

| Week | Task | Output | Owner |
|------|------|--------|-------|
| **1-2** | Run clustering on v4 data | `species_habitat_centroids` populated | Backend |
| **1-2** | Aggregate elevation percentiles | `species_elevation_profiles` populated | Backend |
| **3-4** | Integrate prediction routes | `/api/predict/*` endpoints live | Backend |
| **3-4** | Build frontend map click UI | Click → predictions sidebar | Frontend |
| **5-6** | Validation on test species | Accuracy metrics documented | QA |

**Success Criteria**:
- ✅ 15,000+ species with centroids loaded
- ✅ <500ms prediction latency
- ✅ >70% top-10 accuracy on validation set

### 10.2 Phase 2: SAFE-B Recommender (3-4 weeks)

| Week | Task | Output | Owner |
|------|------|--------|-------|
| **1** | Implement SAFE-B component calculators | 5 scoring functions | Backend |
| **2** | Add strategy selector to API | `/api/recommend/*` endpoints | Backend |
| **3** | Build strategy UI | Goal selection + recommendations | Frontend |
| **4** | Validate recommendations | Expert review of 50 sites | QA |

### 10.3 Phase 3: Scientific Rigor (4-6 weeks)

| Week | Task | Output |
|------|------|--------|
| **1-2** | Uncertainty quantification | Confidence intervals on all predictions |
| **3-4** | Ensemble methods | RF + cosine similarity + MaxEnt voting |
| **5-6** | Validation framework | TSS, AUC, spatial cross-validation |

### 10.4 Phase 4: Additional Variables (4-6 weeks)

| Week | Task | Output |
|------|------|--------|
| **1** | Integrate CHELSA BioClim (all 19) | Full climate envelope |
| **2** | Calculate TWI, distance to water | Hydrological variables |
| **3** | Upload Human Footprint Index | Disturbance pressure |
| **4** | Download/integrate TRY traits | Validated functional traits |
| **5-6** | Fire frequency, HILDA+ land use | Disturbance history |

---

## 11. Competitive Position

### 11.1 Feature Comparison Matrix

| Feature | Treekipedia | eBird | Map of Life | NatureServe | NASA/ESA |
|---------|-------------|-------|-------------|-------------|----------|
| **Resolution** | **10m** ✅ | 1km | 1km | 30m | 30-500m |
| **Tree Species** | **48,129** ✅ | 0 (birds) | 46,000 (mixed) | Limited | N/A |
| **Native Status** | **99.99%** ✅ | N/A | Partial | Full (US/CA) | N/A |
| **Uncertainty** | ❌ Pending | ✅ Full | Partial | Partial | ✅ Gold |
| **Ensemble Methods** | ❌ Pending | ✅ GAMs+ML | ✅ Multiple | ✅ GIS+AI | ✅ Multiple |
| **Validation** | ❌ Pending | ✅ Temporal | ✅ Test sets | ✅ Expert | ✅ Gold |
| **Explainable AI** | ❌ Pending | Partial | ❌ | ✅ Expert | Partial |
| **Blockchain** | ✅ **EAS** | ❌ | ❌ | ❌ | ❌ |

### 11.2 Unique Advantages

1. **10m resolution** - 3-100× finer than any competitor
2. **Tree species specialization** - 48,129 species, not generalist
3. **Blockchain verification** - EAS attestations for data provenance
4. **Native status integration** - 99.99% WCVP coverage
5. **Biotic interactions** - 100% GloBI (unique at this scale)
6. **STAC compliance** - Already implemented

### 11.3 Critical Gaps to Close

| Gap | Priority | Effort | Competitive Impact |
|-----|----------|--------|-------------------|
| Uncertainty quantification | 🔴 CRITICAL | 4-6 weeks | Required for scientific credibility |
| Ensemble methods | 🔴 CRITICAL | 2-3 weeks | Standard since 2020 |
| Validation framework | 🔴 CRITICAL | 2-3 weeks | Required for publication |
| Explainable AI (SHAP) | 🟡 HIGH | 2 weeks | Increasingly expected |
| Polygon/AOI support | 🟡 HIGH | 3-4 weeks | Standard for landscape analysis |

---

## 12. Appendices

### 12.1 GEE Code Templates

#### Sample AlphaEarth at Point

```javascript
var alphaearth = ee.Image('projects/deepmind/alphaearth_v1/global');
var point = ee.Geometry.Point([-46.63, -23.55]);
var sample = alphaearth.sample({
  region: point,
  scale: 10,
  numPixels: 1
}).first();
var embedding = sample.getArray('embedding');
```

#### Derive Topographic Variables

```javascript
var dem = ee.Image('USGS/SRTMGL1_003');
var terrain = ee.Terrain.products(dem);
var slope = terrain.select('slope');
var aspect = terrain.select('aspect');

// TPI
var kernel = ee.Kernel.circle(300, 'meters');
var focal_mean = dem.focalMean({kernel: kernel});
var tpi = dem.subtract(focal_mean);

// TWI (simplified)
var flow = ee.Terrain.slope(dem);
var twi = dem.expression(
  'log(area / tan(slope))',
  {area: 900, slope: flow}  // Simplified
);
```

### 12.2 Database Schema Reference

```sql
-- Core prediction tables
species_habitat_centroids     -- 64-D centroids per species cluster
species_elevation_profiles    -- Elevation percentiles per species

-- Environmental variables (existing)
species                       -- Main species table with 115+ columns
geohash_species_tiles         -- 5.7M occurrence tiles
ecoregions                    -- 847 polygons
intact_forest_landscapes_2021 -- 6,819 IFL polygons

-- Prediction results (proposed)
prediction_logs               -- API call logging
validation_results            -- Hold-out test results
```

### 12.3 Key File Locations

| File | Purpose |
|------|---------|
| `orchestrator/bigquery_exports/alphaearth_embeddings_v4/` | v4 parquet data |
| `orchestrator/cluster_habitat_centroids_weighted.py` | Clustering pipeline |
| `orchestrator/location_predictor_FIXED.py` | Prediction service (port 5002) |
| `treekipedia/backend/routes/prediction.js` | API routes (draft) |
| `treekipedia/database/migrations/007_habitat_centroids.sql` | DB schema |

### 12.4 Document Supersession

This document supersedes and consolidates:
- MASTER_PREDICTION_ARCHITECTURE.md (v1)
- SPECIES_PREDICTOR_RECOMMENDER_STRATEGY.md
- TREEKIPEDIA_SPECIES_INTELLIGENCE_ARCHITECTURE.md
- ULTIMATE_PREDICTION_ARCHITECTURE.md
- OCCURRENCE_WEIGHTING_CLUSTERING_STRATEGY.md
- DYNAMIC_WEIGHTING_FRAMEWORK.md
- PROXIMITY_WEIGHTING_STRATEGY.md
- All RESEARCH_*.md documents (incorporated into Section 4)

Previous docs moved to `.claude/project-management/retired/`

---

## Document Metadata

**Version**: 2.0
**Created**: January 22, 2026
**Author**: Claude Code (Opus 4.5)
**Status**: Complete - Ready for Implementation
**Review**: Pending team review

**Key Changes from v1**:
1. Confirmed v4 data is COMPLETE (277MB parquet)
2. Consolidated ALL environmental variables from 7 research docs
3. Added complete GEE asset inventory
4. Added external datasets acquisition list
5. Clarified clustering with proximity-based density weighting
6. Added full API design specifications
7. Created phased implementation roadmap with success criteria
