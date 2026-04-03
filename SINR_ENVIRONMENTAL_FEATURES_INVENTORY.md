# SINR v3/v4.1 Environmental Features Inventory

**Document Purpose**: Complete catalog of all environmental features sampled at a geographic point in the SINR prediction pipeline for the "environmental envelope" product layer.

**Data as of**: March 2026 (V4.1 Preview)

**Sources Examined**:
- Live sampler: `orchestrator/location_predictor_FIXED.py` (port 5002)
- Batch extractor: `orchestrator/unified_gee_sampler_v3.py` and `unified_gee_sampler_v3_strict.py`
- Training/inference: `orchestrator/train_on_vm.py` and `orchestrator/v3_point_inference.py`
- Feature contract: `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`
- Confidence matrix: `docs/SINR V4.1 Data Confidence Matrix.md`

---

## Summary Statistics

| Category | Count | In Live Sampler | In Batch Extractor | In V4.1 Contract | Status |
|----------|-------|-----------------|-------------------|------------------|--------|
| **AlphaEarth Embeddings** | 64 (snapshot) + 512 (temporal) | ✅ 64 | ✅ 64 + 512 | ✅ 64 | Live |
| **Bioclimatic (WorldClim)** | 19 | ✅ All | ✅ All | ✅ All | Live |
| **Soils** | 7 | ✅ 4/7 | ✅ All | ✅ All | Live |
| **Topography** | 4 | ⚠️ Via SINR call | ✅ All | ✅ All | Live |
| **Water/Hydrology** | 7 | ✅ All | ✅ All | ✅ All | Live |
| **Carbon/Biomass** | 2 | ✅ All | ✅ All | ✅ All | Live |
| **Land Cover/Disturbance** | 8 | ✅ All | ✅ All | ✅ All | Live |
| **Human Influence** | 2 | ✅ All | ✅ All | ✅ All | Live |
| **Ecological Context** | 3 | ✅ All | ✅ All | ✅ All | Live |
| **Temporal Signals** | 3 | ✅ All | ✅ All | ✅ All | Live |
| **Location** | 2 | ✅ All | ✅ All | ✅ 0* | Live |
| **TOTAL SCALAR FEATURES** | **120** | **~103** | **120** | **55** | |
| **AlphaEarth Temporal Stack** | 512D | ✅ (indirect) | ✅ Full | ✅ Via contract | Live |

*Location (lat/lon) in contract as sinusoidal encoding (40D) during training but not in feature_contract list.

---

## 1. ALPHAEARTH EMBEDDINGS (Satellite + Land Cover Proxy)

### 1.1 Primary AlphaEarth Snapshot (64D)

**Source**: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` (10m resolution, 2017-2024)

| Feature Name | GEE Scale | Range | Type | Live Sampler | Batch | V4.1 | Confidence | Notes |
|---|---|---|---|---|---|---|---|---|
| a00 - a63 (64 bands) | [-0.3, +0.3] | float32 | ✅ | ✅ | ✅ | 🟢 Green | Multi-year fallback (2023→2022→...→2017). Encodes land cover phenology, NOT location. Unit hypersphere (cosine similarity valid). Real data when available; simulated fallback otherwise. |

**Key Facts**:
- What it represents: Land surface reflectance patterns, vegetation greenness, moisture across 8 spectral indices
- Not location-aware: Two points 10,000km apart with identical climate/soil get nearly identical embeddings
- Fallback behavior: Simulated via lat/lon seed if no real data available
- Homogeneity signal: Live sampler computes 3×3 grid (9 points, 100m spacing) → mean pairwise cosine similarity as monoculture/plantation indicator

### 1.2 Temporal AlphaEarth Sequence (512D)

**Source**: Stack of 8 annual AlphaEarth embeddings (2017-2024)

| Signal | Type | Dims | Live | Batch | V4.1 | Confidence | Notes |
|---|---|---|---|---|---|---|
| ae_temporal_2017-2024 | 8×64D stacked | 512D | ⚠️ Implicit | ✅ Full | ✅ | 🟢 Green | Attention module learns trends, inter-year changes, derivatives. Captures deforestation progression, plantation establishment, recovery post-fire. |

---

## 2. BIOCLIMATIC VARIABLES (WorldClim V1)

**Source**: `WORLDCLIM/V1/BIO` (1km resolution)
**Unit Conversion**: Temperature (BIO01-11) stored as °C × 10 in GEE; converted to actual °C in live sampler

| Feature | Band | Unit | Display | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|---|
| Annual Mean Temperature | bio01 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Mean Diurnal Range | bio02 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Isothermality | bio03 | ×100 | ×100 | float32 | ✅ | ✅ | ✅ | 🟢 |
| Temperature Seasonality | bio04 | unitless | unitless | float32 | ✅ | ✅ | ✅ | 🟢 |
| Max Temp Warmest Month | bio05 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Min Temp Coldest Month | bio06 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Temperature Annual Range | bio07 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Mean Temp Wettest Quarter | bio08 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Mean Temp Driest Quarter | bio09 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Mean Temp Warmest Quarter | bio10 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Mean Temp Coldest Quarter | bio11 | °C×10 | °C | float32 | ✅ | ✅ | ✅ | 🟢 |
| Annual Precipitation | bio12 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Wettest Month | bio13 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Driest Month | bio14 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Seasonality (CV) | bio15 | % | % | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Wettest Quarter | bio16 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Driest Quarter | bio17 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Warmest Quarter | bio18 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |
| Precip Coldest Quarter | bio19 | mm | mm | float32 | ✅ | ✅ | ✅ | 🟡 |

**Derived in Live Sampler**: Koppen-Geiger climate classification (returns code + description, e.g., "Cfb" = Oceanic)

---

## 3. SOIL PROPERTIES

**Source**: OpenLandMap USDA/ISRIC (~250m resolution, surface layer = 0cm depth)

| Feature | Source | Unit | Model Scale | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|---|
| Soil pH (H₂O) | SOL_PH-H2O_USDA-4C1A2A_M/v02 | pH×10 | pH×10 | float32 | ✅ | ✅ | ✅ | 🟡 |
| Clay % | SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02 | % | % | float32 | ✅ | ✅ | ✅ | 🟡 |
| Sand % | SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02 | % | % | float32 | ✅ | ✅ | ✅ | 🟡 |
| Soil Organic Carbon | SOL_ORGANIC-CARBON_USDA-6A1C_M/v02 | g/kg | g/kg | float32 | ✅ | ✅ | ✅ | 🟢 |
| **Soil Texture Class** | SOL_TEXTURE-CLASS_USDA-TT_M/v02 | categorical (1-13) | categorical | int32 | ✅ Derived | ✅ | ✅ | 🟢 |
| Soil Bulk Density | SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02 | kg/m³ | kg/m³ | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| Soil Water Content (33kPa) | SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01 | % vol | % vol | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 |

**Unit Conversions**: pH stored as pH×10; soil_ph multiplied by 10 in model.map_sample_to_features()
**Categorical**: soil_texture_class remapped to USDA codes (embedding_dim=6)

---

## 4. TOPOGRAPHY / TERRAIN

**Source**: SRTM 30m (primary) | Copernicus DEM 30m (Arctic >59°N fallback)

| Feature | Resolution | Type | Live | Batch | V4.1 | Confidence | Notes |
|---|---|---|---|---|---|---|---|
| Elevation | 30m | float32 | ✅ | ✅ | ✅ | 🟢 | SRTM <60°N; Copernicus >59°N |
| Slope | 30m (derived) | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 | Via ee.Terrain.products() |
| Aspect | 30m (derived) | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 | 0=North, 180=South |
| Hillshade | 30m (derived) | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 | Lambertian illumination sim (0-255) |
| Topographic Diversity | ~1km | float32 | ❌ | ✅ | ✅ | 🟢 | Local terrain roughness |
| MERIT HAND | 90m | float32 | ❌ | ✅ | ✅ | 🟢 | Height above nearest drainage (m) |
| MERIT Upstream Area | 90m | float32 | ❌ | ✅ | ✅ | 🟢 | Catchment accumulation (km²) |

---

## 5. WATER / HYDROLOGY

| Feature | Source | Resolution | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|
| Water Occurrence | JRC/GSW1_4/GlobalSurfaceWater | 30m | float32 | ✅ | ✅ | ✅ | 🟢 |
| Water Recurrence | JRC/GSW1_4/GlobalSurfaceWater | 30m | float32 | ✅ | ✅ | ✅ | 🟢 |
| Water Seasonality | JRC/GSW1_4/GlobalSurfaceWater | 30m | float32 | ✅ | ✅ | ✅ | 🟢 |
| Vapor Pressure Deficit (VPD) | IDAHO_EPSCOR/TERRACLIMATE (year-matched) | 4km | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |
| Actual Evapotranspiration | IDAHO_EPSCOR/TERRACLIMATE | 4km | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |
| Soil Moisture | IDAHO_EPSCOR/TERRACLIMATE | 4km | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |
| PDSI (Palmer Drought Index) | IDAHO_EPSCOR/TERRACLIMATE | 4km | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |
| Water Deficit | IDAHO_EPSCOR/TERRACLIMATE | 4km | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |

**TerraClimate**: Sampled ±2yr window; pre-1958 masked as 0 (not NULL)

---

## 6. CARBON / BIOMASS / PRODUCTIVITY

| Feature | Source | Resolution | Temporal | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|---|
| Above-Ground Biomass (AGB) | NASA/ORNL/biomass_carbon_density/v1 | 100m | static ~2020 | float32 | ✅ | ✅ | ✅ | 🟢 |
| MODIS Gross Primary Productivity | MODIS/061/MOD17A3HGF | 500m | year-matched (2001-2023) | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |

**Known Issues**: GPP fill values (≥65530) explicitly nulled in preview; pre-2001 = 0 (proxy, not NULL)

---

## 7. LAND COVER / DISTURBANCE / PLANTATION

| Feature | Source | Resolution | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|
| Hansen Treecover 2000 | UMD/hansen/global_forest_change_2023 | 30m | float32 (%) | ✅ | ✅ | ✅ | 🟢 |
| Hansen Loss Year | UMD/hansen/global_forest_change_2023 | 30m | int32 (year) | ✅ | ✅ | ✅ | 🟢 |
| Hansen Gain | UMD/hansen/global_forest_change_2023 | 30m | bool | ✅ | ✅ | ✅ | 🟢 |
| **JRC Forest Type** | JRC/GFC2020_subtypes/V1 | 10m | categorical | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| JRC TMF Status | projects/JRC/TMF/v1_2024/TransitionMap_Subtypes | 30m | categorical | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| JRC TMF Degradation Year | projects/JRC/TMF/v1_2024/DegradationYear | 30m | int32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| ESA WorldCover 2021 | ESA/WorldCover/v200 | 10m | categorical | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| Dynamic World | GOOGLE/DYNAMICWORLD/V1 (2015+) | 10m | categorical | ⚠️ Via SINR | ✅ | ✅ | 🟡 |
| SBTN Natural Lands | WRI/SBTN/naturalLands/v1_1/2020 | 300m | bool | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| **Xiao Planted Forest** | projects/sat-io/.../GLOBAL-NATURAL-PLANTED-FORESTS | 30m | categorical | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| Neumann Natural Prob | projects/nature-trace/assets/forest_typology/... | 10m | float32 (0-255) | ⚠️ Via SINR | ✅ | ✅ | 🟢 |

**Categorical Embeddings**:
- jrc_forest_type: vocab_size=5, embedding_dim=3
- xiao_planted_forest: vocab_size=4, embedding_dim=3

---

## 8. HUMAN INFLUENCE

| Feature | Source | Resolution | Temporal | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|---|
| Human Modification Index | CSP/HM/GlobalHumanModification | 1km | static ~2020 | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟢 |
| Nighttime Lights (VIIRS) | NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG | 500m | year-matched (2012+) | float32 | ⚠️ Via SINR | ✅ | ✅ | 🟡 |

**Nighttime Lights**: Pre-2012 = 0 (proxy); explicitly nulled in preview

---

## 9. FIRE / DISTURBANCE

| Feature | Source | Resolution | Type | Live | Batch | V4.1 | Confidence |
|---|---|---|---|---|---|---|---|
| Fire Frequency Count | MODIS/061/MCD64A1 | 500m | int32 (cumulative 2001-year) | ⚠️ Via SINR | ✅ | ✅ | 🟡 |

**Semantics**: Cumulative count from 2001 to observation_year; cannot distinguish natural fire from controlled burns

---

## 10. ECOLOGICAL CONTEXT (CATEGORICAL)

| Feature | Source | Resolution | Type | Vocab Size | Embedding Dim | Confidence |
|---|---|---|---|---|---|---|
| **Ecoregion ID** | RESOLVE/ECOREGIONS/2017 | ~10km | categorical | 850 | 32D | 🟢 |
| **Biome Number** | RESOLVE/ECOREGIONS/2017 | ~10km | categorical | 16 | 8D | 🟢 |

---

## EXCLUDED FEATURES (NOT IN V4.1)

| Feature | Source | Reason | Status | Next Steps |
|---|---|---|---|---|
| GEDI Canopy Height | LARSE/GEDI/.../gediv002_rh-98-a0_vf | Semantically unresolved | 🔴 Red | Verify band semantics |
| GEDI Foliage Diversity | LARSE/GEDI/.../gediv002_fhd-pai-1m-a0_vf | Unresolved FHD metric | 🔴 Red | Verify FHD semantics |
| MODIS Land Cover (temporal) | MODIS/061/MCD12Q1 | Unresolved temporal semantics | 🔴 Gray | Family-level validation |
| HILDA+ Land Use History | external/manual | No canonical strict extraction | 🔴 Gray | Canonicalize or fail-closed |
| Aridity Index | projects/sat-io/open-datasets/global_ai | External/manual | 🔴 Gray | Provenance-tag before full strict |
| ET0 Reference ET | projects/sat-io/open-datasets/global_et0 | External/manual | 🔴 Gray | |
| IPCC Forest Class | NASA/ORNL/global_forest_classification_2020 | Not in strict lineage | 🔴 Gray | |

---

## FEATURE CONTRACT (V4.1 Preview)

**File**: `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`

**55 Continuous Features**:
elevation, slope, aspect, hillshade, topo_diversity, merit_hand_m, merit_upstream_area_km2, bio01-bio19 (19), soil_ph, soil_clay_pct, soil_sand_pct, soil_organic_carbon, soil_bulk_density, soil_water_content, treecover2000, lossyear, biomass_agb_mgha, water_occurrence, water_recurrence, water_seasonality, jrc_tmf_status, jrc_tmf_degrad_year, esa_worldcover_2021, dynamic_world, sbtn_natural_land, neumann_natural_prob, tc_vpd_mean, tc_vpd_delta, tc_aet_mean, tc_soil_moisture_mean, tc_pdsi_mean, tc_water_deficit_mean, tc_solar_rad_mean, human_modification, nighttime_lights, fire_frequency_count, modis_gpp_mean

**5 Categorical Features**:
jrc_forest_type (vocab=5, emb_dim=3), xiao_planted_forest (vocab=4, emb_dim=3), eco_id (vocab=850, emb_dim=32), biome_num (vocab=16, emb_dim=8), soil_texture_class (vocab=14, emb_dim=6)

**Total Model Input**: 64D AlphaEarth + 55D continuous + ~52D categorical embeddings + 128D temporal attention + optional 40D location encoding

---

## KNOWN ISSUES

| Issue | Feature | Impact | Status |
|---|---|---|---|
| Xiao RGB decode | xiao_planted_forest | Was matching red instead of yellow (127,127,0) | FIXED March 8, 2026 |
| Intro ratio contract key | species_intro_ratio | Used empty dict key "ratios" | FIXED March 8, 2026 |
| BIO all-zero contamination | bio01-bio19 | Some grid cells return all zeros | Preview filters obvious rows |
| Soil pH=0 contamination | soil_ph | Some cells invalid (pH=0) | Preview filters soil_ph=0 |
| Pre-2001 MODIS data | modis_gpp_mean, fire_frequency_count | Masked as 0 before 2001 | Semantically unsound |
| Pre-2012 nighttime lights | nighttime_lights | Masked as 0 before 2012 | Preview nulls pre-2012 |

---

## QUICK REFERENCE: SAMPLING ENDPOINTS

### `/sample` Response Structure
```
embedding (64D AlphaEarth)
elevation, treecover2000, lossyear, loss, gain
climate: {bio01-bio19, koppen_code, koppen_description}
soil: {soil_ph, soil_clay_pct, soil_sand_pct, soil_organic_carbon_g_kg, soil_texture, soil_ph_category}
embedding_homogeneity, homogeneity_detail
ccdc: {ccdc_num_breaks, ccdc_last_break}
canopy_height: {canopy_height_mean_m, canopy_height_stddev_100m, canopy_height_model_uncertainty}
sinr_env: {~35+ features including slope, aspect, soil_bulk_density, water_*, jrc_*, xiao_*, neumann_*, eco_id, biome_num, tc_*, fire_frequency_count, modis_gpp_mean, human_modification, nighttime_lights, dynamic_world, biomass_agb_mgha}
```

---

**Generated**: March 17, 2026 | **Status**: Complete Research Only | **Files Referenced**: 5 source files, 120+ features, 8 GEE image collections
