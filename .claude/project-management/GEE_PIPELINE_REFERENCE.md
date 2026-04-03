# GEE & AlphaEarth Pipeline Reference
## How We Use Google Earth Engine, AlphaEarth, and BigQuery

**Version**: 1.2
**Date**: February 15, 2026
**Status**: Definitive reference — READ THIS before touching any GEE/embedding code
**Changes in 1.2**: Added Section 6b (temporal vs static dataset audit), updated Phase C status
**See also**: [MASTER_PREDICTION_ARCHITECTURE_3.md](MASTER_PREDICTION_ARCHITECTURE_3.md) for the full v3.0 system design

---

## 1. Infrastructure

### GCP Projects
| Project | ID | Used For |
|---------|-----|----------|
| **Primary (current)** | `treekipedia-479918` | All recent scripts, BigQuery, GEE |
| **Legacy (pilot)** | `treekipedia-476404` | Original 100-species pilot, some older scripts |

### Authentication
- **Method**: Google Cloud Application Default Credentials (ADC)
- **Setup**: `gcloud auth application-default login`
- **No credential files in repo** — uses local gcloud config
- **Earth Engine**: Initialized with `ee.Initialize(project='treekipedia-479918')`

### BigQuery
- **Dataset**: `treekipedia-479918.species_data`
- **Key table**: `alphaearth_embeddings_v4` (source for v4 parquet export)
- **Usage**: BigQuery was used as intermediate storage during GEE batch export. The v4 parquet on disk is the definitive local copy. BigQuery can be reused for future batch exports.

---

## 2. AlphaEarth: What It Is

**AlphaEarth** (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`) is a Google Earth Engine ImageCollection providing **64-dimensional habitat embeddings** derived from satellite imagery.

### Key Properties
| Property | Value |
|----------|-------|
| Resolution | 10m per pixel |
| Temporal coverage | 2017-2024 (annual mosaics) |
| Bands | A00-A63 (64 float bands) |
| Spatial coverage | Global terrestrial land (99.9% coverage) |
| What it represents | Learned habitat signature from satellite imagery |
| Deterministic | YES — same pixel + same year = same 64-D vector, regardless of species |

### Critical Insight: Pixel-Level, Not Species-Level
AlphaEarth embeddings describe the **habitat at a location**, not a species. If Pinus radiata and Eucalyptus globulus both occur at pixel (-37.8, 144.9) in 2020, they get the **identical** 64-D vector. This is why:
- Deduplication to unique pixel-years is correct and efficient
- Species-specific centroids come from **clustering** per-species occurrence embeddings
- The embedding captures habitat structure (canopy density, spectral properties, phenology), not species identity

### Year-to-Year Variation
Embeddings at the same undisturbed pixel vary slightly across years due to:
- Phenological differences (wet vs. dry year)
- Sensor calibration changes
- Cloud masking and compositing artifacts
- Actual ecological change (growth, minor disturbance)

For the **habitat stability assumption** (Regime 2), 2017 is the preferred year for pre-2017 occurrences because it's closest in time to historical observations.

---

## 3. The V4 Pipeline: How We Got 17,924 Species

### Pipeline Flow
```
GBIF Occurrences (96.5M rows, 60,207 species)
  │
  ├── Filter 1: year >= 2017 AND year <= 2024
  │   (Keep only AlphaEarth-era observations)
  │
  ├── Filter 2: coordinateUncertaintyInMeters < 10m OR NULL
  │   (90.7% of records have NULL uncertainty — these pass)
  │   (Only 2.3M have explicit <10m; the rest are NULL = unknown precision)
  │
  │   Result: 16.5M rows, 20,857 species
  │
  ├── Dedup 1: Per species+pixel+year (4 decimal places ≈ 10m)
  │   (Multiple GBIF records at same pixel for same species = keep one)
  │   Result: ~17.3M unique species-pixel-years
  │
  ├── Dedup 2: Cross-species pixel+year dedup
  │   (AlphaEarth returns same embedding regardless of species)
  │   (Only need to sample each unique pixel-year ONCE)
  │   Result: 2,418,450 unique pixel-years to send to GEE
  │
  ├── GEE Batch Sampling
  │   (Sample AlphaEarth + Hansen + SRTM at each pixel-year)
  │   (Batches of 2000 points, exported to BigQuery)
  │   Coverage: 99.9% — only 1,809 pixels returned no data
  │   Result: 2,416,641 pixel-years with embeddings
  │
  ├── Rejoin: Map pixel embeddings back to species
  │   (Each pixel-year gets assigned to ALL species observed there)
  │   Result: 3,371,724 rows (1.39 species per pixel on average)
  │   Species: 17,924
  │
  ├── Export to BigQuery → Download as Parquet
  │   File: orchestrator/bigquery_exports/alphaearth_embeddings_v4/
  │         alphaearth_embeddings_v4_COMPLETE.parquet (277MB)
  │
  └── Clustering: K-means per species
      (Weighted by occurrence density, deduped to unique locations)
      Result: 44,625 centroids for 17,924 species
      Loaded to: species_habitat_centroids table (pgvector)
```

### V4 Parquet Schema (74 columns)
| Column | Type | Description |
|--------|------|-------------|
| taxon_id | string | Species identifier (e.g., 'GymPiPiPnCx50820-00') |
| latitude | double | Rounded to 4dp (~10m precision) |
| longitude | double | Rounded to 4dp |
| emb_year | int64 | Year of AlphaEarth mosaic sampled (2017-2024) |
| orig_year | int64 | Original GBIF observation year |
| elevation | int64 | SRTM elevation in meters |
| treecover2000 | int64 | Hansen baseline tree cover (%) |
| lossyear | int64 | Year of forest loss (0 = no loss, 1-23 = 2001-2023) |
| loss | int64 | Binary: was forest lost? (0/1) |
| gain | int64 | Binary: did forest regrow 2000-2012? (0/1) |
| A00-A63 | double | 64-dimensional AlphaEarth embedding |

### Why Only 17,924 Species (Not 60,207)?
The 42,283 missing species have occurrences but **no post-2017 observations with acceptable coordinates**:

| Category | Species | Occurrences |
|----------|---------|-------------|
| Only pre-2017 occurrences | 36,511 | ~1.1M |
| Post-2017 but not in v4 extraction (rejoin gap) | ~2,934 | ~18K |
| At pixels already in v4 (pixel-level rejoin possible) | ~4,680 | ~41K |
| Need new GEE sampling | ~37,600 | ~1.1M |

---

## 4. The Coverage Reality

### V4 Coverage Is Near-Complete For Its Target Population
```
Target: 2017-2024, <10m uncertainty or NULL
Eligible pixel-years: 2,418,450
Successfully sampled:  2,416,641 (99.93%)
Failed (no AE data):       1,809 (0.07%) — Antarctica, tiny islands
```

The earlier misleading "4.8% median coverage" statistic was comparing v4 points against ALL 96.5M occurrences (including pre-2017 and bad coordinates). For the actual target population, coverage is essentially 100%.

### AlphaEarth Global Coverage
AlphaEarth covers 99.9% of terrestrial land. Gaps exist only at:
- Antarctica (no satellite coverage in annual composites)
- Very small islands (sub-pixel)
- Persistent cloud regions (rare — annual mosaic handles most)

---

## 5. The Three Expansion Strategies

### Strategy A: Rejoin (FREE — No GEE Calls)
**~4,680 species recoverable immediately**

Some gap species have occurrences at the exact same pixels (4dp) where v4 species were sampled. The embeddings exist in the v4 parquet — we just need to assign them to the additional species.

```python
# Pseudocode:
# 1. Load v4 pixel-year embeddings (unique lat/lon/year → embedding)
# 2. Load gap species occurrences
# 3. Round gap coords to 4dp, match to v4 pixels
# 4. Assign v4 embedding to gap species at matching pixels
```

### Strategy B: Re-clustering (FREE — No GEE Calls)
**Fixes species like P. radiata that have data but bad centroids**

P. radiata has 685 NZ points in v4 (cosine sim 0.84 to AU cluster) but k-means with k=3 merged NZ into Australia. Increasing k or using density-aware clustering creates a NZ-specific centroid.

Cross-region similarity for P. radiata:
```
AU ↔ NZ: 0.839 (similar — plantation pine in both)
AU ↔ CA: 0.186 (very different — Mediterranean vs temperate)
AU ↔ SA: 0.258 (different — tropical vs temperate)
NZ ↔ CA: 0.234 (different)
NZ ↔ SA: 0.165 (very different)
```

The AU↔NZ similarity (0.84) is high but NOT high enough to be identical habitats. With more clusters (k=5-7), NZ separates from AU.

### Strategy C: Regime 2 Sampling (GEE Calls Required)
**~36,500 species need new AlphaEarth data**

For species with only pre-2017 occurrences at currently undisturbed sites:
1. Check Hansen GFC: `loss == 0` at occurrence location → site is still forested
2. Sample AlphaEarth at **2017** (closest year to historical observations)
3. The habitat stability assumption: if forest is undisturbed, 2017 embedding approximates what was there when the species was observed

**Why 2017, not 2023/2024:**
- Closest in time to pre-2017 observations (less temporal drift)
- Best AlphaEarth coverage (809K rows in v4 vs 153K for 2024)
- More conservative assumption (less ecological change since observation)

---

## 6. GEE Datasets We Sample

### Currently In Use (V4 + Real-time Predictor)

| Dataset | GEE Asset ID | Resolution | Type | Used In |
|---------|-------------|-----------|------|---------|
| AlphaEarth V1 Annual | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | 10m | Annual 2017-2024 | v4 pipeline, real-time predictor |
| Hansen GFC v1.11 | `UMD/hansen/global_forest_change_2023_v1_11` | 30m | Static | v4 pipeline, disturbance classification |
| SRTM Elevation | `USGS/SRTMGL1_003` | 30m | Static | v4 pipeline, real-time predictor |
| WorldClim V1 BIO | `WORLDCLIM/V1/BIO` | ~1km | Static | Real-time predictor (v3, 19 bioclim vars) |
| OpenLandMap Soil pH | `OpenLandMap/SOL/SOL_PH-H2O_USDA-A614_M/v02` | 250m | Static | Real-time predictor (v3) |
| OpenLandMap Clay% | `OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02` | 250m | Static | Real-time predictor (v3) |
| OpenLandMap Sand% | `OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02` | 250m | Static | Real-time predictor (v3) |
| OpenLandMap Organic C | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | 250m | Static | Real-time predictor (v3) |

### Previously Extracted (Environmental Context for V4 Points)

| Dataset | Rows | File |
|---------|------|------|
| BioClim + terrain (19 BIO + slope/aspect/hillshade + soil texture + topo diversity + water) | 1.7M | `environmental_extractions/bioclim_terrain_checkpoint.parquet` |
| NDVI temporal (NDVI mean/max/std + EVI per year) | 2.3M | `environmental_extractions/ndvi_temporal_checkpoint.parquet` |
| Terrain (slope, aspect, hillshade) | 1.7M | `environmental_extractions/terrain_alphaearth_checkpoint.parquet` |
| Hansen + elevation (for missing v4 points) | 408K | `environmental_extractions/hansen_elevation_missing_checkpoint.parquet` |

### Forest Stability Index (FSI) Datasets — NEW for v3.0

These datasets are being integrated for the Forest Stability Index, which scores each location 0-100 for ecological integrity and modulates native/introduced species weighting.

| Dataset | GEE Asset ID | Resolution | FSI Component |
|---------|-------------|-----------|---------------|
| **JRC Global Forest Types 2020** | `JRC/GFC2020_subtypes/V1` | 10m | Primary forest flag (value=10 → primary) |
| **JRC TMF Transition Subtypes** | `projects/JRC/TMF/v1_2024/TransitionMap_Subtypes` | 30m | Tropical moist forest status |
| **JRC TMF Annual Changes** | `projects/JRC/TMF/v1_2024/AnnualChanges` | 30m | Per-year state 1990-2024 |
| **JRC TMF Degradation Year** | `projects/JRC/TMF/v1_2024/DegradationYear` | 30m | First degradation detected (invasive detection) |
| **JRC TMF Deforestation Year** | `projects/JRC/TMF/v1_2024/DeforestationYear` | 30m | Deforestation year |
| **Google CCDC** | `GOOGLE/GLOBAL_CCDC/V1` | 30m | Change detection breakpoints 1999-2019 |
| **GEDI Gridded Vegetation** | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | 1km | Canopy height (RH98) + Foliage Height Diversity |
| **NASA ORNL Biomass** | `NASA/ORNL/biomass_carbon_density/v1` | 300m | Aboveground biomass density (Mg/ha) |
| **CSP Human Modification** | `CSP/HM/GlobalHumanModification` | 1km | Human modification index (0-1) |
| **LandTrendr** (algorithm) | `ee.Algorithms.TemporalSegmentation.LandTrendr()` | 30m | Temporal segmentation of Landsat 1985-present |
| **CCDC** (algorithm) | `ee.Algorithms.TemporalSegmentation.Ccdc()` | 30m | Continuous change detection |

### Additional Datasets for v3.0

| Dataset | GEE Asset ID | Resolution | Purpose |
|---------|-------------|-----------|---------|
| **Google Dynamic World** | `GOOGLE/DYNAMICWORLD/V1` | 10m | Near-real-time land cover classification |
| **TerraClimate** | `IDAHO_EPSCOR/TERRACLIMATE` | 4km | Drought stress (VPD, soil moisture, AET) |
| **ESA WorldCover 2021** | `ESA/WorldCover/v200` | 10m | Baseline land cover |
| **MODIS VCF** | `MODIS/006/MOD44B` | 250m | Tree cover change trends |
| **MODIS GPP** | `MODIS/006/MOD17A3HGF` | 500m | Site productivity potential |
| **SBTN Natural Lands** | `WRI/SBTN/naturalLands/v1_1/2020` | 10m | Natural/non-natural classification |
| **GLAD Primary Forest** | `UMD/GLAD/PRIMARY_HUMID_TROPICAL_FORESTS/v1` | 30m | Primary humid tropical forest extent |

### Country-Specific Datasets

| Dataset | GEE Asset | Coverage | Use |
|---------|-----------|----------|-----|
| USFS LCMS | `USFS/GTAC/LCMS/v2024-10` | US only | 1985-2024 annual LULC + disturbance |
| MapBiomas | `projects/mapbiomas-public/assets/brazil/lulc/v1` | Brazil | 1985-2024 annual LULC (40 years!) |
| Canada Forest Age | `CANADA/NFIS/NTEMS/CA_FOREST_AGE` | Canada | Direct forest age at 30m |
| PLANET NICFI | `projects/planet-nicfi/assets/basemaps/africa` | Tropics (Africa) | 5m monthly basemaps |

### Requires Upload (Not Natively on GEE)

| Dataset | Source | Value |
|---------|--------|-------|
| **HILDA+ v2.0** | PANGAEA | Global land use 1960-2019 at 1km (only pre-satellite land use source) |
| **Forest Landscape Integrity Index** | Grantham 2020, Zenodo | Composite forest integrity |

### Previously Listed (Retained)

| Dataset | GEE Asset ID | Resolution | Value |
|---------|-------------|-----------|-------|
| JRC Global Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | 30m | Water proximity (riparian) |
| MODIS Burned Area | `MODIS/061/MCD64A1` | 500m | Fire frequency |
| Topo Diversity | `CSP/ERGo/1_0/Global/SRTM_topoDiversity` | 270m | Landscape heterogeneity |
| SRTM Terrain derivatives | `ee.Terrain.products(SRTM)` | 30m | Slope, aspect, hillshade |
| Soil Texture Class | `OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02` | 250m | USDA texture class |
| Copernicus DEM | `COPERNICUS/DEM/GLO30` | 30m | Better than SRTM in some regions |

**Key insight for batch extraction**: Static datasets (soil, climate, terrain) add negligible cost when piggy-backed onto AlphaEarth sampling. The GEE compute bottleneck is the AlphaEarth `sampleRegions()` call — adding more static bands via `reduceRegions()` is nearly free.

---

## 6b. Temporal vs Static Dataset Audit (Added Feb 15, 2026)

**CRITICAL**: When sampling environmental variables for species occurrences, temporal datasets MUST be year-matched to the occurrence year. Static datasets can be sampled once regardless of year. This distinction was not properly implemented in the Phase C sampler (regime2_sampler.py) and must be corrected.

### Datasets Requiring Year-Matching

| Dataset | GEE Asset | Temporal Range | Sampling Strategy |
|---------|-----------|---------------|-------------------|
| **TerraClimate** | `IDAHO_EPSCOR/TERRACLIMATE` | 1958-present (monthly) | Mean of occurrence_year +/-2yr window. For very old records, use 5yr window. |
| **MODIS GPP** | `MODIS/061/MOD17A3HGF` | 2000-present (annual) | Year-matched. Pre-2000 occurrences: use year 2000 (earliest available). |
| **Dynamic World** | `GOOGLE/DYNAMICWORLD/V1` | 2015-present (10m) | Mode for occurrence_year. Pre-2015: use ESA WorldCover 2021 as static proxy. |
| **MODIS Burned Area** | `MODIS/061/MCD64A1` | 2000-present (monthly) | Cumulative burn count from 2001 to occurrence_year (not through 2023). |
| **VIIRS Nightlights** | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG` | 2012-present (monthly) | Annual mean for occurrence_year. Pre-2012: use DMSP-OLS if available, or omit. |
| **Hansen lossyear** | `UMD/hansen/global_forest_change_2023_v1_11` | Static cumulative | Filter: only count `lossyear <= (occurrence_year - 2000)`. A 2005 observation should not show a 2015 forest loss. |

### Datasets That Are Correctly Static (No Year-Matching Needed)

| Dataset | GEE Asset | Rationale |
|---------|-----------|-----------|
| WorldClim BIO 1-19 | `WORLDCLIM/V1/BIO` | 30-year climate normals (1970-2000), static by definition |
| OpenLandMap soil (7 bands) | `OpenLandMap/SOL/*` | Soil properties change on geological timescales |
| SRTM elevation + terrain | `USGS/SRTMGL1_003` + `ee.Terrain` | Topography is static |
| MERIT Hydro | `MERIT/Hydro/v1_0_1` | Hydrological flow accumulation, static |
| GEDI canopy height | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | Composite from 2019-2023, quasi-static |
| ORNL Biomass | `NASA/ORNL/biomass_carbon_density/v1` | Single ~2010 snapshot |
| JRC Global Forest Types | `JRC/GFC2020_subtypes/V1` | 2020 snapshot |
| ESA WorldCover | `ESA/WorldCover/v200` | 2021 snapshot |
| SBTN Natural Lands | `WRI/SBTN/naturalLands/v1_1/2020` | 2020 snapshot |
| CSP Human Modification | `CSP/HM/GlobalHumanModification` | ~2016 snapshot |
| RESOLVE Ecoregions | `RESOLVE/ECOREGIONS/2017` | Static boundaries |
| CSP Topographic Diversity | `CSP/ERGo/1_0/Global/SRTM_topoDiversity` | Static |
| JRC Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | Cumulative summary |
| JRC TMF status/degradation | `projects/JRC/TMF/v1_2024/*` | Cumulative status maps |
| Hansen treecover2000 | `UMD/hansen/...` (treecover2000 band) | Year 2000 baseline, static |

### Implementation Architecture for Year-Matched Sampling

```
1. Group pixels by occurrence_year into year cohorts
2. For each year cohort:
   a. Build STATIC image stack (same for all cohorts — soil, terrain, WorldClim, etc.)
   b. Build TEMPORAL image stack (year-specific — TerraClimate, MODIS, etc.)
   c. Combine: static.addBands(temporal_for_this_year).addBands(alphaearth_2017)
   d. Sample all pixels in this cohort against the combined image
3. Export to BQ with occurrence_year as metadata column
```

This means pixels at the SAME location but with occurrences in DIFFERENT years will have different temporal env values (correct behavior — climate conditions in 2005 differ from 2015).

For Phase C (pre-2017 occurrences): year range is ~1960-2016. TerraClimate covers back to 1958. MODIS covers 2000+. Pre-MODIS occurrences get MODIS 2000 as earliest proxy.

For V4 backfill (2017-2024 occurrences): year range is 2017-2024. All temporal datasets have full coverage.

### Carbon Merge Policy (v3 temporal carbon)

- Carbon sampling outputs are inherently sparse at some locations (coverage/footprint gaps and occasional `sampleRegions` empty returns).
- **Training-table rule:** when assembling `sinr_v3_unified`, always **LEFT JOIN** source feature tables to `sinr_v3_carbon_temporal` on `(round(lat,4), round(lon,4), observation_year)`.
- Never INNER JOIN carbon features, or valid species occurrences will be dropped.
- Preserve missing carbon values as null/sentinel and include explicit missingness indicators so the model can learn from incomplete carbon coverage.
- Operationally, if `--all --resume-from-bq` repeatedly revisits unresolved `new_gbif` tails, run `--existing --resume-from-bq` directly to clear existing backlog first.

---

## 7. Key Scripts

### Extraction Pipeline
| Script | Purpose | Status |
|--------|---------|--------|
| `orchestrator/extract_alphaearth_occurrences_v2.py` | 2-phase occurrence extraction from parquet (Phase 1: 2017+, Phase 2: pre-2017) | Complete, template for new work |
| `orchestrator/gee_sampler_deduplicated.py` | Cost-optimized GEE batch sampler (dedup to 10m, batch 2000pts, AlphaEarth + Hansen + SRTM) | Complete, template for new work |
| `orchestrator/extract_bioclim_terrain.py` | WorldClim BIO + terrain + soil + water extraction at v4 points | Complete |
| `orchestrator/extract_disturbance_landuse.py` | Hansen + ESA WorldCover + Human Modification + fire | Complete |

### Clustering & Loading
| Script | Purpose | Status |
|--------|---------|--------|
| `orchestrator/run_clustering_v4.py` | K-means clustering per species → centroids | Complete |
| `orchestrator/cluster_habitat_centroids_weighted.py` | Weighted clustering with density correction | Complete |
| `orchestrator/aggregate_elevation_percentiles.py` | Elevation percentile aggregation per species | Complete |

### Real-time Prediction Service
| Script | Purpose | Status |
|--------|---------|--------|
| `orchestrator/location_predictor_FIXED.py` | Python Flask service (port 5002) — samples AlphaEarth + SRTM + Hansen + WorldClim + Soil at clicked location | v3, active |

### Expansion Pipeline
| Script | Purpose | Status |
|--------|---------|--------|
| `orchestrator/rejoin_gap_species.py` | Phase A: Recovered 4,679 species from existing v4 pixel data | ✅ COMPLETE |
| `orchestrator/recluster_expanded.py` | Phase B: Geographic DBSCAN re-clustering (2,257 species, P. radiata 3→9 clusters) | ✅ COMPLETE |
| `orchestrator/regime2_sampler.py` | Phase C: 125-band GEE batch at 4.2M pre-2017 pixels + rejoin | ✅ GEE export done, 🔴 needs temporal year-matching fix + Regime 3 |

---

## 8. Data Files

### On Disk (Root Directory)
| File | Rows | Size | Content |
|------|------|------|---------|
| `Treekipedia_occ_YEAR_*.parquet` | 96.5M | ~2GB | Full occurrences: lat, lon, year, taxon_id, elevation, uncertainty, establishmentMeans |
| `Treekipedia_LatLong_ONLY_*.parquet` | 96.5M | 526MB | Simplified: lat, lon, taxon_id only |
| `Treekipedia_V11_*.csv` | 67,750 | 1.4GB | Species knowledge (133 columns) |

### On Disk (Orchestrator)
| File | Rows | Size | Content |
|------|------|------|---------|
| `orchestrator/bigquery_exports/alphaearth_embeddings_v4_COMPLETE.parquet` | 3.37M | 277MB | V4: 17,924 species, 64-D embeddings + elevation + forest |
| `orchestrator/environmental_extractions/bioclim_terrain_checkpoint.parquet` | 1.7M | — | 19 BIO vars + terrain + soil + water |
| `orchestrator/environmental_extractions/ndvi_temporal_checkpoint.parquet` | 2.3M | — | NDVI/EVI annual stats |

### In PostgreSQL
| Table | Rows | Content |
|-------|------|---------|
| `species_habitat_centroids` | 49,640 | pgvector 64-D centroids, IVFFlat index (lists=320), **22,603 species** (Phase A+B) |
| `species` | 67,743 | All species data (133+ columns, 88.6% climate envelope coverage) |
| `geohash_species_tiles` | 5,786,835 | L7 geohash occurrence tiles, 48,129 species |
| `ecoregions` | 847 | WWF ecoregion polygons with PostGIS geometry |

---

## 9. The Occurrence Parquet Schema

The full occurrence file (`Treekipedia_occ_YEAR_*.parquet`) has 12 columns:

| Column | Type | Notes |
|--------|------|-------|
| species_scientific_name | string | Binomial name |
| decimalLatitude | double | GBIF coordinate |
| decimalLongitude | double | GBIF coordinate |
| taxon_full | string | Full taxonomic name |
| subspecies | string | Subspecies if applicable |
| year | int32 | Observation year (NULL for 8.1% of records) |
| coordinateUncertaintyInMeters | double | NULL for 90.7% of records |
| occurrenceID | string | GBIF occurrence ID |
| gbifID | double | GBIF numeric ID |
| elevation | double | GBIF-reported elevation |
| establishmentMeans | string | Native/introduced/managed etc. |
| taxon_id | string | Our internal taxon ID |

### Important Statistics
- 96,527,874 total rows
- 60,207 unique species
- 91.9% have year data; 8.1% NULL
- 90.7% have NULL coordinate uncertainty (passes <10m filter)
- 9.3% have explicit uncertainty values

---

## 10. P. radiata Case Study (Debugging Reference)

**taxon_id**: `GymPiPiPnCx50820-00`

### The Problem
User clicks on a P. radiata plantation in NZ. Species ranks #67 with "unknown" native status.

### Data Available
| Source | NZ Data |
|--------|---------|
| V4 parquet | 685 NZ embedding points (out of 2,825 total) |
| Full occurrences | 2,374 NZ occurrences (1,961 post-2017) |
| Centroids in DB | 3 centroids: AU (-37.7, 145.7), CO (4.9, -73.9), CA (38.3, -123.0) — NONE in NZ |
| WCVP | NZ NOT listed in wcvp_introduced (data gap) |

### Root Causes
1. **Clustering merged NZ into AU**: AU↔NZ cosine similarity = 0.84, high enough for k=3 to merge them
2. **WCVP data gap**: NZ not listed as introduced → native_status = "unknown" → weaker range score
3. **Degenerate climate range**: annual_temperature_range_c = '12.099;12.099' (min = max)

### Fix
- Re-cluster with higher k (5-7) → NZ separates as its own centroid
- No new GEE calls needed — the 685 NZ embedding points are already in v4

### Cross-Region Embedding Similarity
```
AU ↔ NZ: 0.839  (plantation pine in both — similar but distinct)
AU ↔ CA: 0.186  (Mediterranean vs temperate — very different)
AU ↔ SA: 0.258  (tropical vs temperate)
NZ ↔ CA: 0.234
NZ ↔ SA: 0.165
CA ↔ SA: 0.139
```

---

## 11. Common Pitfalls for Future Sessions

### DO NOT assume v4 coverage is low
The "3.37M rows out of 96.5M occurrences" looks like 3.5% coverage. In reality, v4 covers 99.9% of its target population (2017+, good coordinates). The 93M "missing" rows are pre-2017 or have poor coordinates.

### DO NOT re-sample pixels that are already in v4
AlphaEarth is deterministic per pixel-year. If a pixel-year is in v4, its embedding is known. New species at that pixel just need a data join, not a GEE call.

### DO use 2017 for Regime 2 (pre-2017 occurrences)
Not 2023, not "current year". 2017 is closest to historical observations and has best coverage.

### DO check Hansen before sampling disturbed sites
`loss == 1` means the forest was cleared. Current AlphaEarth there shows the disturbance, not the original habitat.

### DO use integer keys for pixel matching
Float comparison fails silently. Multiply lat/lon by 10000, round to int, then compare:
```python
v4['lat_i'] = (v4['latitude'] * 10000).round().astype(int)
v4['lon_i'] = (v4['longitude'] * 10000).round().astype(int)
```

### DO batch GEE calls (2000 points per task)
GEE has per-request limits. The `gee_sampler_deduplicated.py` pattern of 2000-point batches with `sampleRegions()` → `reduceRegions()` chaining is proven.

### DO piggyback static layers on AlphaEarth sampling
Adding WorldClim, soil, terrain bands to a batch task is nearly free — the bottleneck is the AlphaEarth image access, not the number of bands.
