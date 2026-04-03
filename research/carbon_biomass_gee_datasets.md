# Carbon/Biomass GEE Datasets for SINR v3
## Comprehensive Research Report

**Date**: 2026-02-25
**Purpose**: Integration into SINR v3 multi-task species distribution + carbon prediction model
**Context**: 23.6M point observations (lat/lon), observations span 2000-2024

---

## TABLE OF CONTENTS

1. [Biomass/Carbon Stocks](#1-biomasscarbon-stocks)
   - 1.1 NASA/ORNL Spawn AGB and BGB Carbon Density
   - 1.2 GEDI L4B Gridded Aboveground Biomass Density
   - 1.3 GEDI L4A Raster Aboveground Biomass Density (Monthly)
   - 1.4 LARSE/GEDI Gridded Vegetation Structure Metrics (1KM)
2. [Productivity/Flux](#2-productivityflux)
   - 2.1 MODIS MOD17A3HGF Annual NPP/GPP
   - 2.2 MODIS MOD17A2HGF 8-Day GPP
3. [Vegetation Structure](#3-vegetation-structure)
   - 3.1 MODIS MOD15A2H LAI/FPAR
   - 3.2 ETH Global Canopy Height 2020
   - 3.3 Meta/WRI 1m Canopy Height
   - 3.4 GLAD Forest Height
4. [Soil Carbon](#4-soil-carbon)
   - 4.1 OpenLandMap Soil Organic Carbon
   - 4.2 SoilGrids
5. [Land Cover / Forest Classification](#5-land-cover--forest-classification)
   - 5.1 NASA/ORNL IPCC Global Forest Classification 2020
   - 5.2 Hansen Global Forest Change v1.12
   - 5.3 MODIS Vegetation Indices (EVI/NDVI)
   - 5.4 Dynamic World Tree Probability
6. [Temporal Alignment Strategy](#6-temporal-alignment-strategy)
7. [Recommended Feature Set](#7-recommended-feature-set)

---

## 1. BIOMASS/CARBON STOCKS

### 1.1 NASA/ORNL Spawn AGB and BGB Carbon Density

| Property | Value |
|---|---|
| **GEE Asset ID** | `NASA/ORNL/biomass_carbon_density/v1` |
| **GEE Type** | `ee.ImageCollection` (use `.first()` or `.mosaic()` -- single image in collection) |
| **Spatial Resolution** | 300 meters |
| **Temporal Coverage** | 2010 only (single epoch) |
| **Temporal Resolution** | N/A -- single-epoch snapshot |
| **Spatial Extent** | Global (61.1S to 84N) |

**Bands:**

| Band Name | Units | Min | Max | Description |
|---|---|---|---|---|
| `agb` | Mg C/ha (megagrams carbon per hectare) | 0 | ~129 | Aboveground living biomass carbon stock density of combined woody and herbaceous cover |
| `agb_uncertainty` | Mg C/ha | 0 | ~85 | Cumulative standard error of AGB estimate |
| `bgb` | Mg C/ha | 0 | ~57 | Belowground living biomass carbon stock density (roots) |
| `bgb_uncertainty` | Mg C/ha | 0 | ~37 | Cumulative standard error of BGB estimate |

**Data Type**: Continuous (float)

**What it Measures**: Carbon stock density (mass of carbon per unit area) for both aboveground (stems, bark, branches, twigs) and belowground (roots) living biomass. Does NOT include dead wood, leaf litter, or soil organic matter.

**Known Limitations**:
- Single epoch (~2010), cannot be temporally aligned to specific observation years
- Integrates multiple input maps from different time periods (1982-2010 depending on land cover type)
- Saturates in very high biomass forests (e.g., old-growth tropical forests may be underestimated)
- Uncertainty can be large in areas with sparse input data (e.g., boreal regions, some tropical areas)
- 300m resolution means sub-pixel heterogeneity is averaged out

**Scale Factor**: None needed -- values are already in Mg C/ha (but note our existing code applies no scaling)

**GEE Usage**:
```python
spawn = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic()
agb = spawn.select('agb')
bgb = spawn.select('bgb')
```

**Temporal Alignment**: CANNOT be aligned per observation year. Use as a static baseline (~2010).

**Citation**: Spawn, S.A., Sullivan, C.C., Lark, T.J. et al. Harmonized global maps of above and belowground biomass carbon density in the year 2010. Sci Data 7, 112 (2020). doi:10.1038/s41597-020-0444-4

**DOI**: https://doi.org/10.3334/ORNLDAAC/1763

---

### 1.2 GEDI L4B Gridded Aboveground Biomass Density (Version 2)

| Property | Value |
|---|---|
| **GEE Asset ID** | `LARSE/GEDI/GEDI04_B_002` |
| **GEE Type** | `ee.Image` (single image) |
| **Spatial Resolution** | 1000 meters (1 km) |
| **Temporal Coverage** | 2019-04-18 to 2021-08-04 (mission weeks 19-138) |
| **Temporal Resolution** | N/A -- single composite |
| **Spatial Extent** | 52S to 52N latitude (ISS orbit constraint) |

**Bands:**

| Band Name | Units | Description |
|---|---|---|
| `MU` | Mg/ha (megagrams per hectare, dry biomass) | Mean aboveground biomass density (AGBD), including forest and non-forest |
| `V1` | (variance units) | Variance component 1: uncertainty from field-to-GEDI model in L4A |
| `V2` | (variance units) | Variance component 2: uncertainty from sampling or wall-to-wall model |
| `SE` | Mg/ha | Standard error of mean AGBD estimate |
| `PE` | % | Standard error as fraction of estimated mean AGBD (capped at 100%) |
| `NC` | count | Number of unique GEDI ground tracks in the cell |
| `NS` | count | Number of high-quality waveforms in the cell |
| `QF` | flag | Quality flag: 0=outside GEDI domain, 1=land, 2=meets L1 requirement (SE<20% or SE<20 Mg/ha) |
| `PS` | categorical | Prediction stratum (plant functional type + continent) |
| `MI` | categorical | Mode of inference: 0=none, 1=hybrid model-based, 2=generalized hierarchical |

**Data Type**: Continuous (MU, SE, PE); Categorical (QF, PS, MI)

**What it Measures**: Mean aboveground dry biomass density per 1km grid cell, statistically inferred from GEDI L4A footprint-level predictions. NOTE: This is DRY BIOMASS (Mg/ha), NOT carbon. To convert to carbon, multiply by ~0.47 (standard carbon fraction of dry biomass).

**Known Limitations**:
- Coverage limited to 52S-52N (no boreal forests above 52N -- misses much of Canada, Scandinavia, Siberia)
- 1km resolution is coarse for species-level predictions
- Single temporal composite (2019-2021), not year-specific
- Quality varies with shot density; areas with few GEDI orbits have higher uncertainty
- Non-forest areas included in mean (dilutes forest biomass signal)
- Based on Version 2 algorithm; V2.1 exists for L4A but L4B not yet updated

**GEE Usage**:
```python
l4b = ee.Image('LARSE/GEDI/GEDI04_B_002')
agbd = l4b.select('MU')
agbd_se = l4b.select('SE')
quality = l4b.select('QF')
# Filter to high quality: QF >= 2
agbd_hq = agbd.updateMask(quality.gte(2))
```

**Temporal Alignment**: CANNOT be aligned per observation year. Single 2019-2021 composite.

**Citation**: Dubayah, R.O., J. Armston, S.P. Healey, Z. Yang, P.L. Patterson, S. Saarela, G. Stahl, L. Duncanson, and J.R. Kellner. 2022. GEDI L4B Gridded Aboveground Biomass Density, Version 2. ORNL DAAC. doi:10.3334/ORNLDAAC/2056

---

### 1.3 GEDI L4A Raster Aboveground Biomass Density (Monthly)

| Property | Value |
|---|---|
| **GEE Asset ID** | `LARSE/GEDI/GEDI04_A_002_MONTHLY` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 25 meters (footprint level) |
| **Temporal Coverage** | 2019-03-25 to 2025-03-01 (ongoing) |
| **Temporal Resolution** | Monthly composites |
| **Spatial Extent** | 51.6S to 51.6N latitude |

**Key Bands:**

| Band Name | Units | Description |
|---|---|---|
| `agbd` | Mg/ha | Predicted aboveground biomass density (dry matter) |
| `agbd_se` | Mg/ha | Prediction standard error |
| `agbd_pi_lower` | Mg/ha | Lower prediction interval |
| `agbd_pi_upper` | Mg/ha | Upper prediction interval |
| `l4_quality_flag` | flag | Simplifies selection of most useful predictions |
| `degrade_flag` | flag | Degraded pointing/positioning |
| `sensitivity` | proportion | Maximum canopy cover penetrable given waveform SNR |

**Data Type**: Continuous (sparse -- only where GEDI footprints exist)

**What it Measures**: Footprint-level aboveground biomass density predictions from individual GEDI laser shots, rasterized into monthly composites. Extremely sparse coverage.

**Known Limitations**:
- EXTREMELY SPARSE: GEDI footprints are 25m diameter, spaced ~600m across-track and ~60m along-track. Monthly coverage is very patchy.
- NOT wall-to-wall: most pixels will be NoData
- For training a model, this is problematic -- most training points will have no GEDI L4A data
- Better to use L4B (gridded) or LARSE/GEDI/GRIDDEDVEG for wall-to-wall coverage
- Quality filtering needed: `l4_quality_flag == 1` AND `degrade_flag == 0`

**RECOMMENDATION**: Use L4B (1km gridded) or LARSE/GEDI GRIDDEDVEG instead. L4A monthly is too sparse for 23.6M point sampling.

**GEE Usage**:
```python
l4a = ee.ImageCollection('LARSE/GEDI/GEDI04_A_002_MONTHLY')
l4a_filtered = l4a.filter(ee.Filter.eq('l4_quality_flag', 1))
agbd = l4a_filtered.select('agbd').mosaic()
```

**Citation**: Dubayah, R.O., et al. GEDI L4A Footprint Level Aboveground Biomass Density, Version 2.1. ORNL DAAC.

---

### 1.4 LARSE/GEDI Gridded Vegetation Structure Metrics (1KM)

| Property | Value |
|---|---|
| **GEE Asset ID** | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` |
| **GEE Type** | `ee.ImageCollection` (multiple images, one per metric) |
| **Spatial Resolution** | 1000 meters (1 km) |
| **Temporal Coverage** | 2019-04-17 to 2023-03-16 |
| **Temporal Resolution** | Multi-year aggregate (annual subsets also available) |
| **Spatial Extent** | 52S to 52N latitude |

**This is an ImageCollection where each Image represents a different GEDI metric. Image names follow the pattern:**
`gediv002_{metric}_{filter}_{startdate}_{enddate}`

**Key metrics available (each as a separate image in the collection):**
- `rh-98-a0` -- Relative height 98th percentile (canopy height proxy)
- `rh-50-a0` -- Relative height 50th percentile (median canopy height)
- `fhd-pai-1m-a0` -- Foliage Height Diversity (1m PAI profile)
- `pavd-max-h` -- Height of maximum Plant Area Volume Density
- `pai-z-a0-{5m strata}` -- Plant Area Index at various height strata
- `cc-a0` -- Canopy cover
- `agbd` -- Aboveground biomass density (from L4A)

**Bands per image (8 statistics):**

| Band Name | Description |
|---|---|
| `mean` | Mean of GEDI shot metric values in pixel |
| `meanbse` | Bootstrapped standard error of mean (requires >=10 shots) |
| `median` | Median (50th percentile) of metric values |
| `sd` | Standard deviation of metric values |
| `iqr` | Interquartile range (75th - 25th percentile) |
| `p95` | 95th percentile value |
| `shan` | Shannon's diversity index of metric values |
| `countf` | Count of GEDI shots in pixel (first-per-30m-subcell) |

**Data Type**: Continuous

**What it Measures**: Comprehensive vegetation structure metrics derived from GEDI lidar waveforms, aggregated to 1km grid. Includes canopy height (RH98), canopy cover, foliage height diversity, plant area index, and biomass density.

**Known Limitations**:
- 1km resolution is coarse
- Coverage limited to 52S-52N
- Shot density varies; low-latitude regions may have sparse coverage at 1km
- Recommend filtering by `countf >= 10` for reliable statistics
- `mean()` across the entire collection would average DIFFERENT metrics (RH98 with FHD etc.) -- must select specific images by name

**CRITICAL NOTE ON USAGE**: This collection has one Image per metric, NOT one Image per time step. To get canopy height:
```python
# Get specific metric by filtering the collection
rh98 = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
canopy_height = rh98.select('p95')  # 95th percentile of RH98

# For quick access (our existing code uses):
gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
# WARNING: mosaic() across different metrics is semantically wrong
# The mosaic gives the LAST image's bands, which may not be what you want
# Better to select specific named images
```

**Our existing code uses**:
```python
gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
gedi_stack = gedi.select(['p95', 'shan'], ['gedi_canopy_height_m', 'gedi_foliage_height_div'])
```
This works because `mosaic()` gives the last image in the collection, and `p95` and `shan` are consistent band names across all metric images. However, the semantics depend on which image ends up last. For correctness, select specific images by ID.

**Temporal Alignment**: Single multi-year composite (2019-2023). Cannot be aligned per observation year.

**Citation**: Burns, P., Hakkenberg, C.R. & Goetz, S.J. Multi-resolution gridded maps of vegetation structure from GEDI. Sci Data 11, 881 (2024). doi:10.1038/s41597-024-03668-4

---

## 2. PRODUCTIVITY/FLUX

### 2.1 MODIS MOD17A3HGF Annual Net Primary Production (and GPP)

| Property | Value |
|---|---|
| **GEE Asset ID** | `MODIS/061/MOD17A3HGF` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 500 meters |
| **Temporal Coverage** | 2001-01-01 to 2025-01-01 |
| **Temporal Resolution** | Annual (1 image per year) |
| **Spatial Extent** | Global |

**Bands:**

| Band Name | Units (raw) | Scale Factor | Units (scaled) | Min | Max | Description |
|---|---|---|---|---|---|---|
| `Npp` | kg*C/m^2 (raw int) | 0.0001 | kg C/m^2/yr | -3.0 | 3.27 | Net Primary Productivity (annual) |
| `Gpp` | kg*C/m^2 (raw int) | 0.0001 | kg C/m^2/yr | 0 | 6.55 | Gross Primary Productivity (annual) |
| `Npp_QC` | % | 1 | % | 0 | 100 | Quality control percentage |

**Data Type**: Continuous (integer stored, requires scale factor 0.0001)

**What it Measures**:
- **NPP** (Net Primary Production): The net amount of carbon fixed by vegetation through photosynthesis minus plant respiration (autotrophic respiration). Measures net carbon uptake.
- **GPP** (Gross Primary Production): Total carbon fixed by photosynthesis before respiration losses. GPP = NPP + autotrophic respiration.
- Both are measures of ecosystem productivity/carbon flux.

**Known Limitations**:
- Model-derived (not directly observed) -- uses light-use efficiency model with MODIS fAPAR and meteorological data
- Sensitive to cloud contamination (gap-filled version helps)
- 500m resolution misses fine-scale productivity gradients
- NPP can be negative in stressed/disturbed ecosystems
- Systematic biases in some biomes (e.g., may underestimate tropical forest GPP)
- Note: The `Gpp` band in this annual product is the annual total, NOT the same as the 8-day GPP product

**Temporal Alignment**: YES -- can be aligned per observation year (2001-2024). Each year is a separate image.

```python
# Sample NPP for observation year 2015
npp_2015 = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
            .filterDate('2015-01-01', '2016-01-01')
            .first()
            .select('Npp')
            .multiply(0.0001))  # Scale to kg C/m^2/yr
```

**Citation**: Running, S., Mu, Q., Zhao, M. (2021). MODIS/Terra Net Primary Production Gap-Filled Yearly L4 Global 500m SIN Grid V061. NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD17A3HGF.061

---

### 2.2 MODIS MOD17A2HGF 8-Day Gross Primary Production

| Property | Value |
|---|---|
| **GEE Asset ID** | `MODIS/061/MOD17A2HGF` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 500 meters |
| **Temporal Coverage** | 2021-01-01 to 2025-12-27 |
| **Temporal Resolution** | 8-day composites |
| **Spatial Extent** | Global |

**IMPORTANT NOTE**: The V6.1 (061) 8-day GPP product in GEE starts from 2021, NOT from 2000. The earlier V6 (006) collection `MODIS/006/MOD17A2H` covered 2000-2021 but has been deprecated. For pre-2021 8-day GPP, you would need the annual product (MOD17A3HGF) which has the `Gpp` band going back to 2001.

**Bands:**

| Band Name | Units (raw) | Scale Factor | Units (scaled) | Description |
|---|---|---|---|---|
| `Gpp` | kg*C/m^2 (raw int) | 0.0001 | kg C/m^2 per 8 days | Gross Primary Production (cumulative 8-day) |
| `PsnNet` | kg*C/m^2 (raw int) | 0.0001 | kg C/m^2 per 8 days | Net Photosynthesis = GPP - Maintenance Respiration |
| `Psn_QC` | bitmask | N/A | N/A | Quality control bitmask |

**Data Type**: Continuous (integer stored, requires scale factor 0.0001)

**What it Measures**: 8-day cumulative Gross Primary Productivity and Net Photosynthesis (GPP minus maintenance respiration). Higher temporal resolution than annual product.

**Known Limitations**:
- V6.1 only available from 2021 in GEE (major gap for pre-2021 observations)
- Cloud/quality issues more apparent at 8-day resolution
- For annual mean GPP across the full observation period, prefer MOD17A3HGF which has `Gpp` band from 2001

**Temporal Alignment**: Partially -- only for observations 2021-2024. For pre-2021, use the annual MOD17A3HGF product.

**RECOMMENDATION**: For the SINR v3 model spanning 2000-2024, use `MODIS/061/MOD17A3HGF` (annual) for both GPP and NPP, as it covers the full range. The 8-day product adds value only for computing intra-annual variability (e.g., GPP seasonality) for observations from 2021+.

**Citation**: Running, S., Mu, Q., Zhao, M. (2021). MODIS/Terra Gross Primary Productivity 8-Day L4 Global 500m SIN Grid V061. doi:10.5067/MODIS/MOD17A2HGF.061

---

## 3. VEGETATION STRUCTURE

### 3.1 MODIS MOD15A2H LAI/FPAR

| Property | Value |
|---|---|
| **GEE Asset ID** | `MODIS/061/MOD15A2H` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 500 meters |
| **Temporal Coverage** | 2000-02-18 to present (ongoing) |
| **Temporal Resolution** | 8-day composites |
| **Spatial Extent** | Global |

**Bands:**

| Band Name | Units (raw) | Scale Factor | Units (scaled) | Description |
|---|---|---|---|---|
| `Lai_500m` | raw int | 0.1 | m^2/m^2 (area fraction) | Leaf Area Index: one-sided green leaf area per unit ground area |
| `Fpar_500m` | raw int | 0.01 | fraction (0-1) | Fraction of Photosynthetically Active Radiation absorbed by vegetation |
| `FparLai_QC` | bitmask | N/A | N/A | Quality control for LAI and FPAR |
| `FparExtra_QC` | bitmask | N/A | N/A | Extra quality detail |
| `LaiStdDev_500m` | raw int | 0.1 | m^2/m^2 | Standard deviation of LAI |
| `FparStdDev_500m` | raw int | 0.01 | fraction | Standard deviation of FPAR |

**Data Type**: Continuous

**What it Measures**:
- **LAI** (Leaf Area Index): Total one-sided area of leaf tissue per unit ground surface area. Dimensionless (m^2 leaf / m^2 ground). Key structural parameter for productivity models.
- **FPAR** (Fraction of Photosynthetically Active Radiation): Fraction of incoming PAR (400-700nm) absorbed by the green vegetation canopy. Key input for GPP models.

**Known Limitations**:
- Saturates at high LAI values (>6-7), limiting discrimination in dense tropical forests
- Cloud contamination causes noise, especially in cloudy tropics
- 500m resolution averages heterogeneous canopies
- Best-pixel composite over 8 days may still have residual atmospheric effects
- Wintertime values in deciduous forests may be unreliable

**Temporal Alignment**: YES -- excellent temporal coverage from Feb 2000 to present. Can compute annual means matching observation year.

```python
# Annual mean LAI for observation year 2015
lai_2015 = (ee.ImageCollection('MODIS/061/MOD15A2H')
            .filterDate('2015-01-01', '2016-01-01')
            .select('Lai_500m')
            .mean()
            .multiply(0.1))  # Scale to m^2/m^2
```

**Citation**: Myneni, R., Knyazikhin, Y., Park, T. (2021). MODIS/Terra Leaf Area Index/FPAR 8-Day L4 Global 500m SIN Grid V061. doi:10.5067/MODIS/MOD15A2H.061

---

### 3.2 ETH Global Canopy Height 2020 (10m)

| Property | Value |
|---|---|
| **GEE Asset ID** | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` |
| **GEE Type** | `ee.Image` (community asset) |
| **Spatial Resolution** | 10 meters |
| **Temporal Coverage** | 2020 only |
| **Temporal Resolution** | N/A -- single snapshot |
| **Spatial Extent** | Global |

**Bands:**

| Band Name | Units | Description |
|---|---|---|
| `b1` (default) | meters | Canopy height |

**Also available**: Standard deviation image at `users/nlang/ETH_GlobalCanopyHeightSD_2020_10m_v1`

**Data Type**: Continuous (float)

**What it Measures**: Top-of-canopy height in meters, derived from Sentinel-2 imagery using a deep learning model trained on GEDI L2A height data.

**Known Limitations**:
- Community asset -- may require access permissions; less stable than official GEE catalog assets
- Single year (2020), cannot temporally align
- Model-derived from optical imagery (not direct lidar measurement)
- Lower accuracy in areas with few GEDI training samples
- May overestimate height in some shrubland/savanna regions
- 10m resolution is excellent but may be oversampled when combined with 500m MODIS data

**Temporal Alignment**: CANNOT be aligned. Single 2020 snapshot.

**GEE Usage**:
```python
canopy = ee.Image('users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1')
canopy_sd = ee.Image('users/nlang/ETH_GlobalCanopyHeightSD_2020_10m_v1')
```

**Citation**: Lang, N., Jetz, W., Schindler, K. & Wegner, J.D. A high-resolution canopy height model of the Earth. Nature Ecology & Evolution 7, 1778-1789 (2023). doi:10.1038/s41559-023-02206-6

---

### 3.3 Meta/WRI 1m Canopy Height

| Property | Value |
|---|---|
| **GEE Asset ID** | NOT in official GEE catalog |
| **Alternative Access** | Available via `projects/meta-forest-monitoring-okw37/assets/CanopyHeight` (community upload) |
| **Spatial Resolution** | 1 meter |
| **Temporal Coverage** | 2024 (latest version) |

**Status**: The Meta/WRI Global Canopy Height map is NOT in the official Google Earth Engine data catalog. It has been uploaded by community users to various GEE project assets. The most common community paths referenced are:
- `projects/meta-forest-monitoring-okw37/assets/CanopyHeight`
- Various user uploads

**What it Measures**: Canopy height at 1m resolution derived from high-resolution satellite imagery using Meta's AI model.

**Known Limitations**:
- NOT officially in GEE -- reliability of community uploads may vary
- 1m resolution creates massive computational costs when sampling 23.6M points
- Would need to be mosaicked from tile collection
- At sampling scale of 10-250m (our typical), the 1m resolution adds overhead without clear benefit

**RECOMMENDATION**: Not recommended for this project. The ETH 10m product or GEDI GRIDDEDVEG products are more appropriate for our sampling scale and are officially cataloged.

**Citation**: Tolan, J., et al. Very high resolution canopy height maps from RGB imagery using self-supervised vision transformer and convolutional decoder trained on aerial lidar. Remote Sensing of Environment 300, 113888 (2024).

---

### 3.4 GLAD Forest Height

| Property | Value |
|---|---|
| **GEE Asset ID** | NOT in official GEE catalog as a standalone product |
| **Notes** | GLAD forest height for year 2000 was used as an input to Hansen GFC but is not separately published in GEE. The GLAD 2020 forest height is available via direct download but not in GEE. |

**RECOMMENDATION**: Use ETH Canopy Height 2020 (10m) or GEDI GRIDDEDVEG RH98 for canopy height. GLAD forest height is not easily accessible in GEE.

---

## 4. SOIL CARBON

### 4.1 OpenLandMap Soil Organic Carbon

| Property | Value |
|---|---|
| **GEE Asset ID** | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` |
| **GEE Type** | `ee.Image` (single image with 6 depth bands) |
| **Spatial Resolution** | 250 meters |
| **Temporal Coverage** | 1950-2018 (training data range; represents a static best estimate) |
| **Temporal Resolution** | N/A -- single static prediction |
| **Spatial Extent** | Global (excluding Antarctica) |

**Bands:**

| Band Name | Units (raw) | Scale Factor | Units (scaled) | Description |
|---|---|---|---|---|
| `b0` | raw int | 5 (divide by 5) | g/kg | Soil organic carbon content at 0 cm depth |
| `b10` | raw int | 5 | g/kg | Soil organic carbon content at 10 cm depth |
| `b30` | raw int | 5 | g/kg | Soil organic carbon content at 30 cm depth |
| `b60` | raw int | 5 | g/kg | Soil organic carbon content at 60 cm depth |
| `b100` | raw int | 5 | g/kg | Soil organic carbon content at 100 cm depth |
| `b200` | raw int | 5 | g/kg | Soil organic carbon content at 200 cm depth |

**Data Type**: Continuous (integer stored, divide by 5 to get g/kg)

**What it Measures**: Soil organic carbon (SOC) content (mass of organic carbon per mass of soil) at 6 standard ISRIC depths. SOC is the carbon component of soil organic matter -- a key carbon pool.

**Known Limitations**:
- Static product -- soil carbon changes slowly but this doesn't capture temporal trends
- Machine learning prediction from point observations; accuracy varies by region
- Sparse training data in some regions (e.g., tropical forests, remote areas)
- 250m resolution is appropriate for landscape-scale patterns
- Does NOT measure total soil carbon stock (mass per area) -- that requires multiplying by bulk density and depth
- Estimated min/max values (0-120 raw = 0-24 g/kg scaled) may not capture organic soils (histosols can have >200 g/kg)

**Temporal Alignment**: CANNOT be aligned. Static product.

**GEE Usage**:
```python
soc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02')
soc_0cm = soc.select('b0').divide(5.0)   # g/kg at surface
soc_30cm = soc.select('b30').divide(5.0)  # g/kg at 30cm
```

**Citation**: Hengl, T. & Wheeler, I. (2018). Soil organic carbon content in x 5 g/kg at 6 standard depths (0, 10, 30, 60, 100 and 200 cm) at 250 m resolution (v02). Zenodo. doi:10.5281/zenodo.1475457

---

### 4.2 SoilGrids in GEE

| Property | Value |
|---|---|
| **GEE Asset ID** | NOT in official GEE catalog |
| **Notes** | ISRIC SoilGrids 250m is not available as an official GEE dataset. Some community users have uploaded tiles. |

**Status**: SoilGrids v2.0 (ISRIC) provides SOC, bulk density, clay, sand, silt, CEC, pH, nitrogen, and more at 250m resolution and 6 standard depths. However, it is NOT in the official GEE data catalog.

**Alternatives in GEE**:
- `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` -- SOC (already using)
- `OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02` -- Bulk density
- `OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02` -- Clay fraction
- `OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02` -- Sand fraction
- `OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02` -- pH
- `OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02` -- Texture class
- `OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01` -- Water content

These OpenLandMap products are derived from the same underlying soil point observations as SoilGrids and use similar modeling approaches. They are effectively the GEE-available equivalent.

**RECOMMENDATION**: We already use OpenLandMap soil products in our unified sampler. No additional SoilGrids integration needed.

---

## 5. LAND COVER / FOREST CLASSIFICATION

### 5.1 NASA/ORNL IPCC Global Forest Classification 2020

| Property | Value |
|---|---|
| **GEE Asset ID** | `NASA/ORNL/global_forest_classification_2020/V1` |
| **GEE Type** | `ee.ImageCollection` (single image in collection, use `.first()`) |
| **Spatial Resolution** | 30 meters |
| **Temporal Coverage** | 2020 only |
| **Temporal Resolution** | N/A -- single snapshot |
| **Spatial Extent** | Global |

**Bands:**

| Band Name | Type | Description |
|---|---|---|
| `classification` | Categorical | Forest type classification |

**Class Values:**

| Value | Color | Description |
|---|---|---|
| 1 | Green | Primary Forest |
| 2 | Red | Young Secondary Forest (<=20 years old) |
| 3 | Blue | Old Secondary Forest (>20 years old) |

**Data Type**: Categorical (3 classes)

**What it Measures**: Forest status/condition classification supporting IPCC Tier 1 biomass estimates. Distinguishes primary (intact) forests from young and old secondary forests.

**Known Limitations**:
- Not validated (no independent global validation dataset exists)
- Conservative estimate of forest area (3.26 billion ha vs. FAO's 4.06 billion ha)
- Boolean combination approach means edge cases may be misclassified
- Does not distinguish forest types (broadleaf vs. needleleaf, etc.)
- Single year (2020)
- NoData in non-forest areas

**Temporal Alignment**: CANNOT be aligned. Single 2020 classification.

**GEE Usage**:
```python
forest_class = ee.ImageCollection('NASA/ORNL/global_forest_classification_2020/V1').first()
classification = forest_class.select('classification')
```

**Citation**: Hunka, N., Duncanson, L., Armston, J. et al. IPCC Tier 1 forest biomass estimates from Earth Observation. Sci Data 11, 1127 (2024). doi:10.1038/s41597-024-03930-9

---

### 5.2 Hansen Global Forest Change v1.12 (2000-2024)

| Property | Value |
|---|---|
| **GEE Asset ID** | `UMD/hansen/global_forest_change_2024_v1_12` |
| **GEE Type** | `ee.Image` (single image) |
| **Spatial Resolution** | 30.92 meters (~1 arc-second) |
| **Temporal Coverage** | 2000-2024 |
| **Spatial Extent** | Global (80N to 60S) |

**Carbon-Relevant Bands:**

| Band Name | Units | Type | Description |
|---|---|---|---|
| `treecover2000` | % (0-100) | Continuous | Tree canopy cover in 2000 for vegetation >5m tall |
| `loss` | binary (0/1) | Binary | Forest loss during 2001-2024 (any year) |
| `lossyear` | year code (0-24) | Categorical | Year of loss event: 0=no loss, 1=2001, ..., 24=2024 |
| `gain` | binary (0/1) | Binary | Forest gain 2000-2012 ONLY (not updated since) |
| `datamask` | categorical | Categorical | 0=no data, 1=land, 2=water |

**Also available but less carbon-relevant:**
- `first_b30`, `first_b40`, `first_b50`, `first_b70` -- Landsat reference imagery (first year)
- `last_b30`, `last_b40`, `last_b50`, `last_b70` -- Landsat reference imagery (last year)

**Data Type**: Mixed (continuous for treecover2000, binary/categorical for loss/gain/lossyear)

**What it Measures**: Forest extent and change detection from Landsat time series. Tree cover is canopy closure percentage. Loss is stand-replacement disturbance. Gain is forest recovery.

**Carbon Relevance**:
- `treecover2000` + `lossyear` can be used to estimate tree cover at any year: if `lossyear > 0` and `lossyear <= (obs_year - 2000)`, the pixel was deforested by the observation year
- `treecover2000` is a strong predictor of biomass potential
- Loss events indicate carbon emissions; gain indicates carbon sequestration

**Known Limitations**:
- `gain` band only covers 2000-2012 (severely outdated)
- `loss` is binary -- doesn't capture partial degradation or thinning
- Does not distinguish natural disturbance from anthropogenic deforestation
- Tree cover is canopy closure, not biomass -- a 100% canopy cover shrubland is very different from a 100% canopy cover old-growth forest
- No information about post-loss recovery (except the very dated `gain` band)
- Version updates periodically (currently v1.12 for 2024)

**Temporal Alignment**: PARTIALLY. `treecover2000` is baseline, and `lossyear` can be used to derive approximate tree cover at observation year. But no dynamic tree cover layer exists per year.

```python
hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
tc2000 = hansen.select('treecover2000')
lossyear = hansen.select('lossyear')
# Estimate tree cover at observation year (e.g., 2015):
# If loss occurred in or before 2015, tree cover = 0
obs_year_code = 15  # 2015 = 15
lost_before_obs = lossyear.gt(0).And(lossyear.lte(obs_year_code))
tc_at_obs = tc2000.where(lost_before_obs, 0)
```

**Citation**: Hansen, M.C., et al. High-Resolution Global Maps of 21st-Century Forest Cover Change. Science 342: 850-853 (2013). doi:10.1126/science.1244693

---

### 5.3 MODIS Vegetation Indices (EVI/NDVI) -- MOD13A1

| Property | Value |
|---|---|
| **GEE Asset ID** | `MODIS/061/MOD13A1` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 500 meters |
| **Temporal Coverage** | 2000-02-18 to present |
| **Temporal Resolution** | 16-day composites |
| **Spatial Extent** | Global |

**Key Bands:**

| Band Name | Units (raw) | Scale Factor | Units (scaled) | Range (scaled) | Description |
|---|---|---|---|---|---|
| `EVI` | raw int | 0.0001 | dimensionless | -0.2 to 1.0 | Enhanced Vegetation Index |
| `NDVI` | raw int | 0.0001 | dimensionless | -0.2 to 1.0 | Normalized Difference Vegetation Index |
| `DetailedQA` | bitmask | N/A | N/A | N/A | Detailed quality assessment |
| `SummaryQA` | bitmask | N/A | N/A | 0-3 | 0=good, 1=marginal, 2=snow, 3=cloud |

**Data Type**: Continuous

**What it Measures**:
- **EVI**: Enhanced vegetation greenness index that corrects for atmospheric and soil background effects. Better sensitivity in high biomass areas than NDVI.
- **NDVI**: Classic vegetation index. Correlates with vegetation greenness/vigor. Widely used as productivity/biomass proxy.

**Carbon Relevance**: EVI and NDVI are proxies for vegetation productivity and canopy greenness. Strong correlation with GPP and biomass, especially EVI which doesn't saturate as quickly as NDVI in dense canopies. EVI mean and variability (std dev) provide information about:
- Vegetation density (higher EVI = more vegetation = more carbon)
- Seasonality (high std dev = deciduous/seasonal; low std dev = evergreen)
- Ecosystem type discrimination

**Known Limitations**:
- Indirect carbon proxy (not a direct biomass measurement)
- NDVI saturates in dense canopies (EVI is somewhat better)
- Cloud contamination affects quality, especially in tropics
- 500m resolution averages heterogeneous landscapes
- Snow/ice can create artifacts in winter

**Temporal Alignment**: YES -- excellent coverage from Feb 2000 to present at 16-day resolution. Can compute annual mean/std matching observation year.

```python
# Annual EVI mean and std for observation year 2015
evi_2015 = (ee.ImageCollection('MODIS/061/MOD13A1')
            .filterDate('2015-01-01', '2016-01-01')
            .select('EVI'))
evi_mean = evi_2015.mean().multiply(0.0001)
evi_std = evi_2015.reduce(ee.Reducer.stdDev()).multiply(0.0001)
```

**Citation**: Didan, K. (2021). MODIS/Terra Vegetation Indices 16-Day L3 Global 500m SIN Grid V061. doi:10.5067/MODIS/MOD13A1.061

---

### 5.4 Dynamic World Tree Probability

| Property | Value |
|---|---|
| **GEE Asset ID** | `GOOGLE/DYNAMICWORLD/V1` |
| **GEE Type** | `ee.ImageCollection` |
| **Spatial Resolution** | 10 meters |
| **Temporal Coverage** | 2015-06-27 to present |
| **Temporal Resolution** | Per Sentinel-2 scene (2-5 day revisit) |
| **Spatial Extent** | Global |

**Key Carbon-Relevant Bands:**

| Band Name | Units | Range | Description |
|---|---|---|---|
| `trees` | probability | 0-1 | Estimated probability of complete tree coverage |
| `grass` | probability | 0-1 | Estimated probability of complete grass coverage |
| `shrub_and_scrub` | probability | 0-1 | Estimated probability of shrub/scrub |
| `crops` | probability | 0-1 | Estimated probability of cropland |
| `label` | categorical | 0-8 | Most likely class (1=trees) |

**Data Type**: Continuous (probabilities), Categorical (label)

**What it Measures**: Near-real-time land use/land cover probabilities at 10m resolution. The `trees` band gives a continuous probability of tree cover, which is a strong indicator of forest presence and, by proxy, biomass.

**Carbon Relevance**: The `trees` probability band provides a high-resolution, near-real-time indicator of tree cover. Unlike Hansen's binary loss/static treecover, Dynamic World gives probability values that can indicate partial tree cover and are available per Sentinel-2 acquisition.

**Known Limitations**:
- Only available from mid-2015 (Sentinel-2 launch) -- no coverage for observations before 2015
- Predictions are per-scene (not composited) -- need to aggregate for annual means
- Training data may have biases in underrepresented regions
- 10m resolution creates computation costs at 23.6M points
- Probability values can be noisy for individual scenes; compositing is essential

**Temporal Alignment**: YES for 2015+ observations. Can compute annual mode/mean matching observation year. NOT available for pre-2015 observations.

```python
# Annual tree probability for 2020
dw_2020 = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
           .filterDate('2020-01-01', '2021-01-01')
           .select('trees'))
tree_prob_mean = dw_2020.mean()
```

**Citation**: Brown, C.F., Brumby, S.P., Guzder-Williams, B. et al. Dynamic World, Near real-time global 10 m land use land cover mapping. Sci Data 9, 251 (2022). doi:10.1038/s41597-022-01307-4

---

## 6. TEMPORAL ALIGNMENT STRATEGY

For each dataset, here is the temporal alignment capability relative to our observation window (2000-2024):

### Temporally-Alignable Datasets (use observation-year-specific values):

| Dataset | Temporal Range | Resolution | Strategy |
|---|---|---|---|
| MODIS NPP/GPP (MOD17A3HGF) | 2001-2024 | Annual | Filter to observation year |
| MODIS LAI/FPAR (MOD15A2H) | 2000-present | 8-day | Annual mean for observation year |
| MODIS EVI/NDVI (MOD13A1) | 2000-present | 16-day | Annual mean+std for observation year |
| Dynamic World | 2015-present | Per scene | Annual mean for observation year (2015+ only) |
| Hansen lossyear | 2001-2024 | Annual | Derive tree cover at observation year |

### Static/Single-Epoch Datasets (same value regardless of observation year):

| Dataset | Epoch | Notes |
|---|---|---|
| Spawn AGB/BGB | ~2010 | Best available global biomass benchmark |
| GEDI L4B AGBD | 2019-2021 | Lidar-based biomass reference |
| LARSE/GEDI GRIDDEDVEG | 2019-2023 | Vegetation structure from lidar |
| ETH Canopy Height | 2020 | High-resolution canopy height |
| OpenLandMap SOC | Static | Soil carbon (changes very slowly) |
| IPCC Forest Classification | 2020 | Forest type |
| Hansen treecover2000 | 2000 | Baseline tree cover |

### Recommended Temporal Strategy:

1. **For carbon STOCK prediction targets** (AGB, BGB, SOC): Use static datasets as training targets. These represent the "ground truth" carbon at a reference year. The model learns to predict these from the temporally-varying features.

2. **For productivity FLUX features** (NPP, GPP, EVI, LAI): Match to observation year when possible. This captures the ecosystem state at the time the species was observed.

3. **For structure features** (canopy height, GEDI): Use as static features. These change slowly enough that 2020 values are reasonable proxies for the 2000-2024 period for most forests (except recently deforested/planted areas).

4. **For forest change features** (Hansen loss, Dynamic World): Derive per-observation-year to capture deforestation and land use change.

---

## 7. RECOMMENDED FEATURE SET

### Tier 1: Essential Carbon Features (add to every training point)

| # | Feature Name | Source Dataset | GEE Asset | Band(s) | Scale Factor | Static/Temporal |
|---|---|---|---|---|---|---|
| 1 | `carbon_agb` | Spawn AGB | `NASA/ORNL/biomass_carbon_density/v1` | `agb` | none | Static (~2010) |
| 2 | `carbon_agb_unc` | Spawn AGB unc. | same | `agb_uncertainty` | none | Static |
| 3 | `carbon_bgb` | Spawn BGB | same | `bgb` | none | Static |
| 4 | `carbon_bgb_unc` | Spawn BGB unc. | same | `bgb_uncertainty` | none | Static |
| 5 | `gedi_l4b_agbd` | GEDI L4B | `LARSE/GEDI/GEDI04_B_002` | `MU` | none | Static (2019-2021) |
| 6 | `gedi_l4b_agbd_se` | GEDI L4B SE | same | `SE` | none | Static |
| 7 | `npp_at_obs` | MODIS NPP | `MODIS/061/MOD17A3HGF` | `Npp` | x0.0001 | **Temporal** (per obs year) |
| 8 | `gpp_at_obs` | MODIS GPP | `MODIS/061/MOD17A3HGF` | `Gpp` | x0.0001 | **Temporal** (per obs year) |
| 9 | `soc_0cm` | OpenLandMap SOC | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | `b0` | /5 | Static |
| 10 | `soc_30cm` | OpenLandMap SOC | same | `b30` | /5 | Static |
| 11 | `soc_100cm` | OpenLandMap SOC | same | `b100` | /5 | Static |
| 12 | `soc_200cm` | OpenLandMap SOC | same | `b200` | /5 | Static |

### Tier 2: Important Structure Features

| # | Feature Name | Source Dataset | GEE Asset | Band(s) | Scale Factor | Static/Temporal |
|---|---|---|---|---|---|---|
| 13 | `canopy_height_m` | ETH Canopy Height | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` | `b1` | none | Static (2020) |
| 14 | `gedi_rh98_p95` | GEDI GRIDDEDVEG RH98 | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | `p95` | none | Static (2019-2023) |
| 15 | `gedi_fhd_mean` | GEDI GRIDDEDVEG FHD | same | `shan` | none | Static |
| 16 | `lai_at_obs` | MODIS LAI | `MODIS/061/MOD15A2H` | `Lai_500m` | x0.1 | **Temporal** |
| 17 | `fpar_at_obs` | MODIS FPAR | same | `Fpar_500m` | x0.01 | **Temporal** |
| 18 | `evi_mean_at_obs` | MODIS EVI | `MODIS/061/MOD13A1` | `EVI` | x0.0001 | **Temporal** |
| 19 | `evi_std_at_obs` | MODIS EVI std | same | `EVI` (reduce) | x0.0001 | **Temporal** |
| 20 | `ipcc_forest_class` | IPCC Forest Class | `NASA/ORNL/global_forest_classification_2020/V1` | `classification` | none | Static (2020) |

### Tier 3: Temporal Change Features (already partially in unified sampler)

| # | Feature Name | Source Dataset | GEE Asset | Band(s) | Notes |
|---|---|---|---|---|---|
| 21 | `hansen_treecover2000` | Hansen GFC | `UMD/hansen/global_forest_change_2024_v1_12` | `treecover2000` | Already in unified sampler |
| 22 | `hansen_lossyear` | Hansen GFC | same | `lossyear` | Already in unified sampler |
| 23 | `hansen_gain` | Hansen GFC | same | `gain` | Already in unified sampler |
| 24 | `npp_mean_longterm` | MODIS NPP mean | `MODIS/061/MOD17A3HGF` | `Npp` (mean over all years) | Multi-year mean |
| 25 | `npp_trend` | MODIS NPP trend | `MODIS/061/MOD17A3HGF` | `Npp` (linear fit slope) | Trend over time |
| 26 | `dw_tree_prob` | Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | `trees` (annual mean) | 2015+ only |

### Summary Statistics

| Category | # New Features | # Already in Unified Sampler |
|---|---|---|
| Biomass/Carbon Stocks | 6 (Spawn 4 + GEDI L4B 2) | 1 (Spawn AGB only) |
| Productivity/Flux | 6 (NPP at obs, GPP at obs, NPP mean, NPP trend, + temporal LAI/FPAR) | 1 (GPP mean in temporal env) |
| Vegetation Structure | 4 (canopy height, GEDI RH98, GEDI FHD, IPCC class) | 2 (GEDI p95, GEDI shan) |
| Soil Carbon | 4 (SOC at 4 depths) | 1 (SOC 0cm only) |
| Vegetation Indices | 2 (EVI mean+std at obs year) | 0 |
| **Total new features to add** | **~15-18** | **~5 already sampled** |

---

## APPENDIX A: Dataset Comparison Table

| Dataset | Resolution | Coverage | Epoch | Temporal? | Units | Primary Use |
|---|---|---|---|---|---|---|
| Spawn AGB/BGB | 300m | Global | 2010 | No | Mg C/ha | Carbon stocks |
| GEDI L4B | 1km | 52S-52N | 2019-2021 | No | Mg/ha (dry) | Biomass density |
| GEDI L4A Monthly | 25m | 51.6S-51.6N | 2019-present | Monthly | Mg/ha (dry) | Footprint biomass (sparse) |
| GEDI GRIDDEDVEG | 1km | 52S-52N | 2019-2023 | No | meters, various | Vegetation structure |
| MODIS NPP (annual) | 500m | Global | 2001-2024 | Annual | kg C/m^2/yr | Carbon flux |
| MODIS GPP (annual) | 500m | Global | 2001-2024 | Annual | kg C/m^2/yr | Carbon flux |
| MODIS GPP (8-day) | 500m | Global | 2021-present | 8-day | kg C/m^2/8d | Carbon flux |
| MODIS LAI/FPAR | 500m | Global | 2000-present | 8-day | m^2/m^2, fraction | Canopy structure |
| MODIS EVI/NDVI | 500m | Global | 2000-present | 16-day | dimensionless | Productivity proxy |
| ETH Canopy Height | 10m | Global | 2020 | No | meters | Canopy height |
| OpenLandMap SOC | 250m | Global (ex. Ant.) | Static | No | g/kg | Soil carbon |
| IPCC Forest Class | 30m | Global | 2020 | No | categorical | Forest type |
| Hansen GFC | 30m | Global | 2000-2024 | Loss year | %, binary | Forest change |
| Dynamic World | 10m | Global | 2015-present | Per scene | probability | Land cover |

## APPENDIX B: Key Conversion Factors

- **Mg C/ha to t C/ha**: 1:1 (megagram = metric tonne)
- **Mg/ha dry biomass to Mg C/ha**: multiply by 0.47 (IPCC default carbon fraction)
- **kg C/m^2 to Mg C/ha**: multiply by 10
- **g/kg SOC to % SOC**: divide by 10
- **MODIS Npp/Gpp raw to kg C/m^2/yr**: multiply by 0.0001
- **MODIS LAI raw to m^2/m^2**: multiply by 0.1
- **MODIS FPAR raw to fraction**: multiply by 0.01
- **MODIS EVI/NDVI raw to index**: multiply by 0.0001
- **OpenLandMap SOC raw to g/kg**: divide by 5

## APPENDIX C: Existing Code Asset ID Cross-Reference

These asset IDs are already used in our codebase (`carbon_gee_sampler.py` and `unified_gee_sampler_v3.py`):

| Variable | Asset ID | File |
|---|---|---|
| `SPAWN_BIOMASS` | `NASA/ORNL/biomass_carbon_density/v1` | carbon_gee_sampler.py:64 |
| `GEDI_GRIDDED` | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | carbon_gee_sampler.py:65 |
| `MODIS_NPP` | `MODIS/061/MOD17A3HGF` | carbon_gee_sampler.py:66 |
| `MODIS_GPP` | `MODIS/061/MOD17A2HGF` | carbon_gee_sampler.py:67 |
| `MODIS_LAI_FPAR` | `MODIS/061/MOD15A2H` | carbon_gee_sampler.py:68 |
| `SOIL_ORGANIC_CARBON` | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | carbon_gee_sampler.py:69 |
| `ETH_CANOPY_HEIGHT` | `users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1` | carbon_gee_sampler.py:70 |
| `IPCC_FOREST_CLASS` | `NASA/ORNL/global_forest_classification_2020/V1` | carbon_gee_sampler.py:71 |
| `HANSEN_GFC` | `UMD/hansen/global_forest_change_2024_v1_12` | carbon_gee_sampler.py:72 |
| `MODIS_EVI` | `MODIS/061/MOD13A1` | carbon_gee_sampler.py:73 |
| GEDI L4B | `LARSE/GEDI/GEDI04_B_002` | (not yet in code) |
| Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | unified_gee_sampler_v3.py:287 |

## APPENDIX D: Bugs/Issues in Existing Carbon Sampler

Reviewing `carbon_gee_sampler.py`, the following issues were identified:

1. **GEDI GRIDDEDVEG mosaic issue** (line 121-127): The code does `gedi.mean()` then renames with prefix -- but this averages ACROSS different metrics (RH98, FHD, AGBD etc. all have bands named `mean`, `median`, etc.). This is semantically incorrect. Should select specific metric images by ID.

2. **MODIS GPP only samples 2021+** (line 151): Due to V6.1 starting from 2021, the 8-day GPP mean only covers 2021-2025. For pre-2021 observations, this misses most of the data. Should use the annual product (MOD17A3HGF `Gpp` band) instead.

3. **No temporal alignment** (line 97-202): The entire carbon image is static -- no per-observation-year matching for NPP, GPP, EVI, LAI. All temporal datasets are averaged over fixed recent periods.

4. **SOC at all 6 depths** (line 162-168): Currently samples all 6 depths. Consider if this is redundant -- SOC at 0cm and 200cm may be sufficient with the intermediate depths being highly correlated.

5. **ETH Canopy Height access** (line 172-176): Uses community asset that may require permission. Has a try/except that silently skips if unavailable.

6. **GEDI L4B not included**: The L4B gridded biomass product is not in the carbon sampler, despite being the best wall-to-wall lidar-derived biomass product in GEE.
