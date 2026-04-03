# Hydrological and Riparian Variables for Species Distribution Modeling

**Research Date**: January 21, 2026
**Purpose**: Inform AlphaEarth variable selection for tree species distribution modeling and restoration planning
**Focus**: Water-related environmental predictors and GEE implementation

---

## Executive Summary

Hydrological variables are critical predictors for tree species distribution, particularly for riparian ecosystems and water-dependent species. This research identifies key variables, datasets, and implementation strategies for Google Earth Engine (GEE) integration. Five primary hydrological dimensions are essential: topographic moisture proxies (TWI), surface water proximity, flow dynamics, soil moisture/climate water balance, and geomorphological indices.

**Key Recommendations**:
1. Implement Topographic Wetness Index (TWI) using MERIT DEM or SRTM derivatives
2. Integrate HydroSHEDS for flow accumulation and watershed context
3. Use JRC Global Surface Water for distance-to-water calculations
4. Incorporate TerraClimate for soil moisture and water balance variables
5. Calculate stream power indices for erosion-prone riparian zones

---

## 1. Key Hydrological Variables

### 1.1 Topographic Wetness Index (TWI)

**Definition**: TWI is a steady-state wetness index predicting spatial soil moisture patterns based on topography. It quantifies the tendency for water to accumulate at a location.

**Formula**: `TWI = ln(a / tan(β))`
- `a` = upslope contributing area per unit contour length (flow accumulation)
- `β` = local slope gradient

**Ecological Significance**:
- Strong predictor of soil moisture availability
- Controls species distributions in topographically complex terrain
- Proxy for groundwater discharge zones and wetland locations
- Influences nutrient availability and redox conditions

**Calculation Considerations**:
- **Flow Algorithm**: FD8 (multiple flow direction) recommended over D8 for natural terrain
- **Flow Dispersion**: Close to 1.0 for optimal results
- **Flow Width**: Equal to raster cell size
- **Resolution**: 30m (SRTM) to 90m (MERIT) suitable for landscape-scale modeling

**Species Distribution Applications**:
- Discriminates wetland vs. upland species niches
- Predicts occurrence of hydrophytic vegetation
- Explains fine-scale distribution patterns within watersheds
- Correlates negatively with species richness in xeric-adapted communities

**GEE Implementation**:
TWI is not directly available but can be calculated from DEM derivatives:

```javascript
// Calculate TWI from SRTM or MERIT DEM
var dem = ee.Image("MERIT/DEM/v1_0_3");
var slope = ee.Terrain.slope(dem).multiply(Math.PI/180); // Convert to radians
var flowAcc = calculateFlowAccumulation(dem); // Custom function needed
var twi = flowAcc.divide(slope.tan()).log();
```

**Limitations**:
- Assumes steady-state hydrology (no temporal dynamics)
- Accuracy depends on DEM quality and resolution
- May overpredict wetness in flat terrain
- Does not account for soil permeability or vegetation interception

### 1.2 Distance to Water Bodies

**Definition**: Euclidean or hydrological distance from a location to nearest perennial/intermittent surface water.

**Types**:
1. **Distance to Rivers/Streams**: Linear water features from drainage networks
2. **Distance to Lakes/Reservoirs**: Polygonal standing water bodies
3. **Distance to Wetlands**: Saturated/inundated areas
4. **Distance to Coastlines**: Marine/estuarine boundaries

**Ecological Significance**:
- Primary determinant of riparian species distributions
- Controls access to water for phreatophytic species
- Influences microclimate (humidity, temperature buffering)
- Affects seed dispersal via hydrochory
- Predicts flood disturbance gradients

**Typical Thresholds for Tree Species**:
- **0-50m**: Obligate riparian species (willows, sycamores, cottonwoods)
- **50-200m**: Facultative riparian species (river birch, ash, elms)
- **200-500m**: Riparian-influenced species (some oaks, maples)
- **>500m**: Upland species with minimal water proximity effects

**GEE Implementation**:
Use JRC Global Surface Water or HydroSHEDS river networks:

```javascript
// Distance to permanent water
var gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater");
var permanentWater = gsw.select('max_extent').eq(1);
var distanceToWater = permanentWater.fastDistanceTransform().sqrt()
  .multiply(ee.Image.pixelArea().sqrt()); // Convert to meters
```

**Data Sources**:
- **JRC Global Surface Water**: 30m resolution, 1984-2021, Landsat-based
- **HydroSHEDS River Networks**: Vector polylines of global rivers
- **HydroATLAS**: Includes distance-to-water attributes per basin
- **MERIT Hydro**: 90m resolution global river networks

### 1.3 Flow Accumulation

**Definition**: Number of upslope cells that drain through a given cell, representing cumulative upstream drainage area.

**Units**: Typically expressed as:
- Number of cells (raw)
- Square kilometers (area)
- Log-transformed values (for modeling)

**Ecological Significance**:
- Proxy for streamflow magnitude and water availability
- Predicts flood frequency and intensity
- Indicates nutrient and sediment delivery
- Determines valley bottom width and floodplain extent
- Controls riparian forest composition and structure

**Thresholds**:
- **Low (<100 cells)**: Ephemeral headwater channels, xeric species
- **Moderate (100-10,000 cells)**: Perennial streams, diverse riparian communities
- **High (>10,000 cells)**: Major rivers, flood-tolerant species, wetland forests

**GEE Datasets**:
1. **HydroSHEDS Flow Accumulation**: `WWF/HydroSHEDS/15ACC` (15 arc-seconds, ~500m)
2. **Hydrography90m**: `projects/sat-io/open-datasets/HYDROGRAPHY90/base-network-layers/flow_accumulation` (90m resolution)
3. **MERIT Hydro**: Flow accumulation derived from MERIT DEM

**Implementation**:
```javascript
// HydroSHEDS flow accumulation
var flowAcc = ee.Image("WWF/HydroSHEDS/15ACC");
var logFlowAcc = flowAcc.log10(); // Log-transform for modeling

// Hydrography90m (higher resolution)
var flowAcc90m = ee.ImageCollection("projects/sat-io/open-datasets/HYDROGRAPHY90/base-network-layers/flow_accumulation")
  .mosaic();
```

**Applications**:
- Stream network delineation (threshold at 500-1000 cells)
- Riparian zone classification
- Flood hazard assessment
- Sediment transport modeling

### 1.4 Water Table Depth

**Definition**: Vertical distance from land surface to groundwater table.

**Ecological Significance**:
- **Critical for phreatophytes**: Trees with roots accessing groundwater
- Controls species composition in riparian meadows and forests
- Determines drought tolerance requirements
- Influences soil redox conditions and nutrient cycling
- Affects rooting depth and water stress

**Species-Specific Requirements**:
- **Herbs**: 1-1.5m optimal depth
- **Shrubs**: 2-4m optimal depth
- **Trees**: Up to 10m (deeper for desert phreatophytes)

**Example Species Thresholds**:
- *Phragmites communis* (common reed): <3m
- *Tamarix ramosissima* (saltcedar): 2-5m
- *Populus euphratica* (Euphrates poplar): Up to 10m
- *Salix* spp. (willows): 0.5-3m

**Data Availability**:
Water table depth is **not directly available** in global GEE datasets. Proxies include:

1. **TWI** (inverse proxy: high TWI = shallow water table)
2. **Distance to streams** (closer = shallower in alluvial systems)
3. **Elevation above nearest drainage** (HAND index)
4. **TerraClimate soil moisture** (temporal correlation)
5. **Fan et al. 2013 Global Water Table Depth**: 1km resolution static map (may be available via custom upload)

**GEE Proxy Calculation**:
```javascript
// Height Above Nearest Drainage (HAND) as proxy
var dem = ee.Image("MERIT/DEM/v1_0_3");
var streams = flowAcc90m.gt(1000); // Stream threshold
var streamElevation = dem.updateMask(streams);
var hand = dem.subtract(streamElevation.reduceNeighborhood({
  reducer: ee.Reducer.min(),
  kernel: ee.Kernel.euclidean(5000, 'meters') // 5km search radius
}));
```

**Limitations**:
- Global datasets lack temporal dynamics
- Local hydrogeology highly variable
- Seasonal fluctuations not captured
- Requires in-situ validation

### 1.5 Soil Moisture and Climatic Water Balance

**Definition**:
- **Soil Moisture**: Volumetric water content in root zone
- **Climatic Water Deficit**: Precipitation minus potential evapotranspiration
- **Actual Evapotranspiration**: Water actually evaporated/transpired
- **Runoff**: Excess water not infiltrated or evaporated

**Ecological Significance**:
- Direct control on photosynthesis and growth
- Determines length of growing season
- Predicts drought stress and mortality risk
- Influences fire regimes in water-limited ecosystems
- Shapes community composition along moisture gradients

**TerraClimate Variables** (IDAHO_EPSCOR/TERRACLIMATE):
Monthly data from 1958-present at ~4km resolution:

1. **soil** - Soil moisture (mm)
2. **def** - Climate water deficit (mm)
3. **aet** - Actual evapotranspiration (mm)
4. **pet** - Potential evapotranspiration (mm)
5. **ro** - Runoff (mm)
6. **pr** - Precipitation (mm)
7. **pdsi** - Palmer Drought Severity Index

**GEE Implementation**:
```javascript
// Annual mean soil moisture
var terraclimate = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
  .filterDate('2010-01-01', '2020-12-31')
  .select('soil');
var annualSoilMoisture = terraclimate.mean();

// Growing season water deficit
var deficit = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
  .filter(ee.Filter.calendarRange(4, 9, 'month')) // Apr-Sep
  .select('def')
  .sum(); // Total deficit for growing season
```

**Derived Metrics**:
- **Annual Water Balance**: Precipitation - PET
- **Aridity Index**: PET / Precipitation
- **Drought Frequency**: Years with PDSI < -2
- **Soil Moisture Seasonality**: CV of monthly values

**Complementary Datasets**:
- **ERA5-Land Soil Moisture**: 9km resolution, daily since 1950
- **SMAP Soil Moisture**: 9km resolution, 2015-present (limited temporal extent)
- **GLDAS Noah**: 10km resolution, soil moisture at multiple depths

---

## 2. Data Sources and GEE Availability

### 2.1 HydroSHEDS (WWF/USGS)

**Full Name**: Hydrological data and maps based on SHuttle Elevation Derivatives at multiple Scales

**Resolution**: 3 arc-seconds (~90m), 15 arc-seconds (~500m), 30 arc-seconds (~1km)

**Spatial Coverage**: Global (between 60°N and 56°S)

**Temporal Coverage**: Based on SRTM 2000 elevation data (static)

**GEE Asset IDs**:
- **Flow Direction**: `WWF/HydroSHEDS/15DIR`
- **Flow Accumulation**: `WWF/HydroSHEDS/15ACC`
- **Basins Level 1-12**: `WWF/HydroSHEDS/v1/Basins/hybas_[1-12]`
- **Free Flowing Rivers**: `WWF/HydroSHEDS/v1/FreeFlowingRivers`

**Key Products**:
1. **Drainage Direction**: D8 flow routing (8 cardinal directions)
2. **Flow Accumulation**: Upstream drainage area in number of cells
3. **Drainage Basins**: Hierarchical watershed polygons (Pfafstetter system)
4. **River Networks**: Polyline vectors of global rivers
5. **HydroATLAS**: Hydro-environmental attributes per sub-basin

**HydroATLAS Variables** (useful for modeling):
- Distance to stream/lake/reservoir
- River volume and discharge estimates
- Upstream land cover composition
- Dam density and regulation indices
- Groundwater table depth (coarse estimates)

**Applications**:
- Watershed delineation for species occurrence data
- Flow accumulation-based predictor variables
- Stream network context for riparian species
- Upstream land use impacts on water quality

**Limitations**:
- Based on 2000 SRTM (no temporal updates)
- Lower accuracy in flat terrain and dense vegetation
- Flow networks may not reflect ephemeral streams
- Does not account for anthropogenic modifications (except in HydroATLAS)

**Citation**: Lehner, B., Grill G. (2013). Global river hydrography and network routing: baseline data and new approaches to study the world's large river systems. Hydrological Processes, 27(15): 2171-2186.

### 2.2 Global Surface Water (JRC)

**Full Name**: Joint Research Centre Global Surface Water Mapping Layers

**Version**: v1.4 (current as of 2023)

**Resolution**: 30m

**Temporal Coverage**: 1984-2021 (based on entire Landsat archive)

**GEE Asset**: `JRC/GSW1_4/GlobalSurfaceWater`

**Bands/Layers**:
1. **max_extent**: Binary map of all detected water over 38 years
2. **occurrence**: Percentage of time water was present (0-100)
3. **change_abs**: Absolute change in water occurrence between epochs
4. **change_norm**: Normalized change (-100 to +100)
5. **seasonality**: Number of months water present
6. **recurrence**: Inter-annual variability of water presence
7. **transition**: Water/land transition classes (permanent, new, lost, etc.)

**Derived Products**:
- **Yearly History**: Annual water masks (separate collection: `JRC/GSW1_4/YearlyHistory`)
- **Monthly History**: Monthly water masks (separate collection: `JRC/GSW1_4/MonthlyHistory`)
- **Metadata**: Data quality masks

**Ecological Applications**:
1. **Distance to Permanent Water**: Using max_extent or occurrence > 75%
2. **Distance to Seasonal Water**: Using seasonality > 6 months
3. **Water Availability Dynamics**: Using yearly history for temporal trends
4. **Flood Frequency**: Using occurrence as proxy for inundation probability
5. **Wetland Classification**: Using seasonality and recurrence

**GEE Implementation Examples**:
```javascript
// Distance to permanent water (>90% occurrence)
var gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater');
var permanentWater = gsw.select('occurrence').gte(90);
var distPermanent = permanentWater.fastDistanceTransform().sqrt()
  .multiply(30); // Convert to meters

// Distance to any water
var anyWater = gsw.select('max_extent');
var distAnyWater = anyWater.fastDistanceTransform().sqrt().multiply(30);

// Water seasonality as predictor
var seasonality = gsw.select('seasonality'); // 0-12 months
```

**Strengths**:
- Longest temporal record (38 years)
- High spatial resolution (30m)
- Distinguishes permanent vs. seasonal water
- Tracks water body changes over time
- Free and openly accessible

**Limitations**:
- Does not capture subsurface water (springs, groundwater)
- Misses small headwater streams (<30m width)
- Cloud contamination in some regions
- Limited accuracy in heavily vegetated wetlands

**Citation**: Pekel, J.F., et al. (2016). High-resolution mapping of global surface water and its long-term changes. Nature, 540, 418-422.

### 2.3 TerraClimate

**Full Name**: TerraClimate: Monthly Climate and Climatic Water Balance for Global Terrestrial Surfaces

**Resolution**: 1/24° (~4km or 2.5 arc-minutes)

**Temporal Coverage**: 1958-present (updated annually)

**Temporal Resolution**: Monthly

**GEE Asset**: `IDAHO_EPSCOR/TERRACLIMATE`

**Variables** (14 bands per month):
1. **aet** - Actual evapotranspiration (mm)
2. **def** - Climate water deficit (mm)
3. **pet** - Potential evapotranspiration (mm)
4. **ppt** - Precipitation (mm)
5. **q** - Runoff (mm)
6. **soil** - Soil moisture (mm)
7. **srad** - Downward surface shortwave radiation (W/m²)
8. **swe** - Snow water equivalent (mm)
9. **tmmn** - Minimum temperature (°C)
10. **tmmx** - Maximum temperature (°C)
11. **vap** - Vapor pressure (kPa)
12. **ws** - Wind speed (m/s)
13. **vpd** - Vapor pressure deficit (kPa)
14. **PDSI** - Palmer Drought Severity Index

**Methodology**:
- Interpolates climate station data using climatically aided interpolation (CAI)
- Incorporates WorldClim v2 high-resolution climatologies
- Water balance calculated using Thornthwaite-type model
- Accounts for soil water holding capacity from global soils data

**Ecological Applications**:
1. **Water Stress Indices**: Using def, pet-aet, PDSI
2. **Soil Moisture Availability**: Using soil band
3. **Growing Season Length**: Days with suitable temperature + moisture
4. **Drought Events**: PDSI < -2 or def > threshold
5. **Aridity Classification**: pet/ppt ratios
6. **Temporal Trends**: Change in water balance 1960-2020

**GEE Derived Metrics Example**:
```javascript
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
  .filterDate('2000-01-01', '2020-12-31');

// Mean annual water deficit
var annualDeficit = tc.select('def')
  .filter(ee.Filter.calendarRange(1, 12, 'month'))
  .sum() // Annual sum
  .reduce(ee.Reducer.mean()); // Multi-year mean

// Growing season soil moisture
var growingSeason = tc.select('soil')
  .filter(ee.Filter.calendarRange(4, 9, 'month'))
  .mean();

// Drought frequency
var pdsi = tc.select('PDSI');
var droughtMonths = pdsi.map(function(img) {
  return img.lt(-2); // Moderate drought threshold
});
var droughtFrequency = droughtMonths.sum().divide(pdsi.size());
```

**Strengths**:
- Long temporal record (1958-present)
- Monthly resolution captures seasonality
- Comprehensive water balance variables
- Integrates multiple climate sources
- Freely available and regularly updated

**Limitations**:
- Coarse spatial resolution (4km) may miss microclimates
- Water balance model simplified (does not account for topography fully)
- Station data sparse in some regions (e.g., tropics, mountains)
- Soil water capacity based on global datasets (may be inaccurate locally)

**Citation**: Abatzoglou, J.T., et al. (2018). TerraClimate, a high-resolution global dataset of monthly climate and climatic water balance from 1958–2015. Scientific Data 5:170191.

### 2.4 MERIT Hydro

**Full Name**: Multi-Error-Removed Improved-Terrain Hydrography

**Resolution**: 3 arc-seconds (~90m)

**Spatial Coverage**: Global (90°N - 60°S)

**GEE Asset**: `MERIT/Hydro/v1_0_1`

**Bands**:
1. **elv** - Elevation (m)
2. **dir** - Flow direction (D8 system)
3. **upg** - Upstream drainage area (km²)
4. **upa** - Upstream drainage pixel count
5. **wth** - Channel width (m)
6. **hnd** - Height Above Nearest Drainage (m)

**Key Innovation**:
MERIT Hydro improves upon SRTM and other DEMs by removing multiple error sources:
- Absolute bias
- Stripe noise
- Speckle noise
- Tree height bias
- Building height bias

**Height Above Nearest Drainage (HAND)**:
HAND is the vertical distance from a cell to the nearest stream. It is a powerful predictor of:
- Flood inundation extent
- Soil saturation probability
- Riparian vs. upland species distributions
- Water table depth (inverse proxy)

**GEE Implementation**:
```javascript
var merit = ee.Image('MERIT/Hydro/v1_0_1');

// Height above nearest drainage
var hand = merit.select('hnd');

// Flow accumulation (log-transformed)
var flowAcc = merit.select('upa').log10();

// Stream channel width
var channelWidth = merit.select('wth');

// Classify riparian zones (HAND < 10m, flow accumulation > 1000)
var riparianZone = hand.lt(10).and(merit.select('upa').gt(1000));
```

**Applications**:
- Improved TWI calculations using error-corrected DEM
- HAND as direct predictor for riparian species
- Flow accumulation at higher resolution than HydroSHEDS
- Stream network delineation with channel width estimates

**Strengths**:
- Higher accuracy than raw SRTM
- Includes pre-calculated HAND (saves processing time)
- 90m resolution suitable for landscape ecology
- Global coverage with consistent quality

**Limitations**:
- Static dataset (2000 SRTM base)
- Channel width estimates may be inaccurate for small streams
- Does not reflect anthropogenic modifications

**Citation**: Yamazaki, D., et al. (2019). MERIT Hydro: A high-resolution global hydrography map based on latest topography dataset. Water Resources Research, 55, 5053-5073.

### 2.5 Hydrography90m (Community Catalog)

**Resolution**: 90m (3 arc-seconds)

**Coverage**: Global

**GEE Access**: Community Catalog (`projects/sat-io/open-datasets/HYDROGRAPHY90/`)

**Products**:
1. **Flow Accumulation**: `base-network-layers/flow_accumulation`
2. **Flow Direction**: `base-network-layers/flow_direction`
3. **Drainage Basins**: `base-network-layers/drainage_basins`
4. **Stream Segments**: `base-network-layers/stream_segments`
5. **Outlets**: Point locations of basin outlets
6. **Depression Layers**: Identified topographic sinks

**Additional Layers** (geomorphometric):
- Slope
- Aspect
- Terrain Ruggedness Index (TRI)
- Topographic Position Index (TPI)
- Convergence Index

**Advantages Over Other Datasets**:
- Highest resolution flow accumulation in GEE
- Consistent global processing
- Pre-calculated geomorphometric variables
- Includes depression identification

**Example Usage**:
```javascript
var flowAcc90 = ee.ImageCollection("projects/sat-io/open-datasets/HYDROGRAPHY90/base-network-layers/flow_accumulation")
  .mosaic();

var streams = flowAcc90.gte(1000); // Stream threshold
var streamOrder = flowAcc90.log10().toInt(); // Proxy for stream order
```

**Note**: This is a community-contributed dataset, not officially supported by Google but widely used.

---

## 3. Riparian and Phreatophyte Species Indicators

### 3.1 Defining Phreatophytes

**Definition**: Deep-rooted plants that obtain water from the phreatic zone (saturated groundwater) or capillary fringe above it. The term derives from Greek "phreato" (well) + "phyte" (plant).

**Characteristics**:
- Roots typically extend to water table (up to 10-15m depth)
- Often found in arid/semi-arid regions where groundwater is reliable
- Exhibit high transpiration rates
- May create "inverted tree line" in deserts (concentrated in valleys)

**Maximum Water Table Depth Tolerance**:
- Most phreatophytic trees: 10m
- Desert phreatophytes (e.g., *Prosopis*): Up to 15m
- Riparian shrubs: 2-5m
- Herbaceous phreatophytes: 1-3m

### 3.2 Ecological Classification by Water Dependence

**Obligate Riparian Species** (0-50m from water):
- *Salix* spp. (willows): Water table 0.5-3m
- *Populus* spp. (cottonwoods, poplars): Water table 1-5m
- *Platanus occidentalis* (sycamore): Floodplains, 0-30m from streams
- *Taxodium distichum* (bald cypress): Swamps, water table at surface
- *Nyssa aquatica* (water tupelo): Seasonally flooded areas

**Facultative Riparian Species** (50-200m from water):
- *Fraxinus* spp. (ashes): Moist soils, water table 2-6m
- *Acer saccharinum* (silver maple): Floodplains, tolerates periodic inundation
- *Ulmus americana* (American elm): Riparian zones, mesic uplands
- *Quercus palustris* (pin oak): Poorly drained flats, water table variable

**Desert Phreatophytes**:
- *Populus euphratica* (Euphrates poplar): Water table 1-10m, adapted to saline conditions
- *Tamarix ramosissima* (saltcedar): Water table 2-5m, invasive in western US
- *Prosopis* spp. (mesquite): Extremely deep roots, water table <15m
- *Acacia* spp.: Variable depth tolerance, 3-10m

**Upland Species with Minor Water Influence** (>200m):
- Most oak species (*Quercus* spp.): Rely on precipitation and shallow soil moisture
- Pine species (*Pinus* spp.): Minimal groundwater dependence
- *Juniperus* spp. (junipers): Drought-adapted, no groundwater access

### 3.3 Water Table Depth Thresholds by Functional Type

Based on research in montane riparian meadows and arid systems:

**Sedges and Rushes** (obligate wetland):
- Optimal: 0-0.5m (saturated root zone)
- Maximum: 1.5m
- Examples: *Carex* spp., *Juncus* spp.

**Graminoids** (facultative wetland):
- Optimal: 0.5-1.5m
- Maximum: 2.5m
- Examples: *Phragmites australis*, *Phalaris arundinacea*

**Riparian Shrubs**:
- Optimal: 1-3m (*Salix* spp., willows)
- Optimal: 2-4m (*Alnus* spp., alders)
- Maximum: 5m (most species)

**Riparian Trees**:
- Optimal: 2-5m (*Populus* spp., cottonwoods)
- Optimal: 3-6m (*Fraxinus* spp., ashes)
- Maximum: 10m (most temperate riparian species)

**Desert Phreatophytic Trees**:
- Functional: 5-10m (*Tamarix*, *Populus euphratica*)
- Maximum: 15m (*Prosopis* spp.)

### 3.4 Species Distribution Patterns Along Water Gradients

**Findings from Montane Riparian Research**:
1. **Species Richness**: Negatively correlated with mean water table depth (r = -0.65 to -0.85)
2. **Total Plant Cover**: Decreases as water table deepens
3. **Community Composition**: Sharp transitions occur at 1m and 3m depth thresholds
4. **Obligate Wetland Species**: Restricted to water table <1m
5. **Upland Species**: Begin dominating at water table >2m

**Leaf Traits and Water Table Depth**:
- *Populus euphratica* study: Leafing intensity decreases exponentially with water table depth
- Hydraulic conductance reduces at depths >5m
- Leaf water potential becomes more negative (water stress increases)

**Vegetation Dynamics**:
- Phreatophyte-aquifer feedback loops create oscillating population dynamics
- Groundwater depletion can lead to rapid forest dieback
- Streamflow alteration disrupts recruitment patterns (seedling establishment)

### 3.5 Indicator Species for Hydrological Modeling

**Strong Indicators of Shallow Water Table (<2m)**:
- *Salix* spp. (willows)
- *Carex* spp. (sedges)
- *Typha* spp. (cattails)
- *Juncus* spp. (rushes)
- *Alnus* spp. (alders)

**Indicators of Moderate Depth (2-5m)**:
- *Populus deltoides* (eastern cottonwood)
- *Fraxinus pennsylvanica* (green ash)
- *Platanus occidentalis* (sycamore)
- *Acer saccharinum* (silver maple)

**Indicators of Deep Groundwater Access (5-10m)**:
- *Tamarix* spp. (tamarisk)
- *Prosopis* spp. (mesquite)
- *Populus euphratica* (Euphrates poplar)

**Using Species as Water Table Proxies**:
When direct water table measurements are unavailable, species presence can inform modeling:
1. Identify obligate riparian species in occurrence records
2. Extract environmental covariates at these locations
3. Use as training data for water table depth proxies (TWI, HAND, distance to water)
4. Validate proxies against in-situ measurements where available

### 3.6 Riparian Zone Delineation

**Geomorphic Definitions**:
- **Active Channel**: Area regularly inundated (flow accumulation + low HAND)
- **Floodplain**: Area inundated at return interval (e.g., 100-year flood)
- **Riparian Zone**: Vegetation influenced by stream proximity (typically <200m)
- **Upland Transition**: Beyond riparian influence (>200-500m)

**GEE-Based Riparian Zone Mapping**:
```javascript
// Combine flow accumulation + HAND + distance to water
var merit = ee.Image('MERIT/Hydro/v1_0_1');
var hand = merit.select('hnd');
var flowAcc = merit.select('upa');

// Define riparian zone
var riparianZone = hand.lt(10) // Within 10m vertical distance
  .and(flowAcc.gt(1000)); // Perennial stream threshold

// Add distance buffer
var streams = flowAcc.gt(1000);
var distToStream = streams.fastDistanceTransform().sqrt().multiply(90);
var riparianBuffer = distToStream.lt(200); // 200m buffer

var riparianFinal = riparianZone.or(riparianBuffer);
```

**Applications for Species Modeling**:
- Subset occurrence data to riparian vs. upland species
- Include riparian zone as binary predictor
- Interaction terms: e.g., precipitation × riparian status
- Separate models for riparian and upland species guilds

---

## 4. Stream Power and Erosion Indices

### 4.1 Stream Power Index (SPI)

**Definition**: Stream power is the rate of energy expenditure by flowing water, driving erosion and geomorphic change. SPI estimates erosive potential based on topography.

**Formula**: `SPI = A_s × tan(β)`
- `A_s` = Specific catchment area (upslope area per unit contour length)
- `β` = Local slope gradient

**Alternative Formulations**:
- **Unit Stream Power**: `ω = ρ g Q S / w` (requires discharge and width estimates)
- **Total Stream Power**: `Ω = ρ g Q S` (reach-scale power)

Where:
- `ρ` = Water density (1000 kg/m³)
- `g` = Gravitational acceleration (9.81 m/s²)
- `Q` = Discharge (m³/s)
- `S` = Channel slope
- `w` = Channel width (m)

**Ecological Significance**:
- Predicts erosion and sedimentation patterns
- Controls substrate size distribution (cobble vs. sand vs. silt)
- Determines channel migration rates
- Influences riparian forest age structure and succession
- Affects seedling establishment success (disturbance frequency)

**Thresholds**:
- **Low SPI**: Stable channels, fine sediments, mature forests
- **Moderate SPI**: Balanced erosion/deposition, mixed substrates
- **High SPI**: Active erosion, coarse substrates, early-successional vegetation

**GEE Calculation**:
```javascript
// Calculate SPI
var dem = ee.Image('MERIT/DEM/v1_0_3');
var slope = ee.Terrain.slope(dem).multiply(Math.PI/180); // Radians
var flowAcc = merit.select('upa'); // In pixels

// Specific catchment area (m²/m)
var cellSize = 90; // meters
var specificArea = flowAcc.multiply(cellSize);

// Stream Power Index
var spi = specificArea.multiply(slope.tan());
var logSPI = spi.log10(); // Log-transform for modeling
```

**Applications**:
- Predict erosion-prone riparian zones
- Identify disturbance-adapted species habitats
- Classify channel types (bedrock, alluvial, debris flow)
- Restoration site prioritization (stable vs. dynamic reaches)

### 4.2 Topographic Position Index (TPI)

**Definition**: Difference between a cell's elevation and the mean elevation of surrounding cells.

**Interpretation**:
- **Positive TPI**: Ridges, hilltops (drier)
- **Near-zero TPI**: Flat areas, mid-slopes
- **Negative TPI**: Valleys, depressions (wetter)

**Ecological Relevance**:
- Proxy for moisture accumulation
- Controls cold-air drainage and frost pockets
- Influences soil depth and nutrient availability
- Predicts landform classes (ridges, slopes, valleys)

**GEE Calculation**:
```javascript
var dem = ee.Image('MERIT/DEM/v1_0_3');
var radius = 500; // 500m neighborhood

var meanElevation = dem.reduceNeighborhood({
  reducer: ee.Reducer.mean(),
  kernel: ee.Kernel.circle(radius, 'meters')
});

var tpi = dem.subtract(meanElevation);

// Classify landforms
var ridges = tpi.gt(50);
var valleys = tpi.lt(-50);
var slopes = tpi.abs().lte(50);
```

### 4.3 Terrain Ruggedness Index (TRI)

**Definition**: Mean absolute difference between a cell and its neighbors, quantifying topographic heterogeneity.

**Ecological Significance**:
- Predicts microhabitat diversity
- Controls soil moisture variability
- Influences erosion and mass wasting
- Affects species richness (intermediate ruggedness often highest)

**GEE Implementation**:
```javascript
var dem = ee.Image('MERIT/DEM/v1_0_3');

var tri = dem.reduceNeighborhood({
  reducer: ee.Reducer.stdDev(),
  kernel: ee.Kernel.square(1) // 3x3 window
});
```

### 4.4 Convergence Index

**Definition**: Measures topographic convergence (negative values) or divergence (positive values), indicating flow concentration or dispersion.

**Formula**: Based on aspect of neighboring cells relative to central cell.

**Ecological Applications**:
- Predicts moisture accumulation zones (convergent areas)
- Identifies seepage areas and springs
- Complements TWI for fine-scale moisture patterns

**GEE Access**:
Available in Hydrography90m:
```javascript
var convergence = ee.ImageCollection("projects/sat-io/open-datasets/HYDROGRAPHY90/geomorphometry/convergence")
  .mosaic();
```

### 4.5 Erosion Risk Modeling

**Factors Combining for Erosion Prediction**:
1. **SPI**: Erosive power
2. **Slope**: Gravitational force
3. **Soil Erodibility**: Texture, organic matter (e.g., SoilGrids K-factor)
4. **Vegetation Cover**: Protective effect (NDVI, land cover)
5. **Rainfall Intensity**: Erosivity (from climate data)

**Simplified Erosion Risk Index**:
```javascript
var erosionRisk = logSPI
  .multiply(slope)
  .divide(ndvi.add(0.1)) // Low vegetation = higher risk
  .multiply(rainfallIntensity);
```

**Species Implications**:
- **Erosion-Adapted Species**: Require pioneer traits (fast growth, prolific seeding)
  - *Alnus* spp., *Salix* spp., *Populus* spp.
- **Erosion-Sensitive Species**: Require stable substrates
  - Late-successional forest species, slow-growing conifers

---

## 5. GEE Implementation Strategy for AlphaEarth

### 5.1 Recommended Variable Suite

**Tier 1 - Essential Variables** (immediate implementation):
1. **Distance to Permanent Water** (JRC GSW occurrence > 75%)
2. **Flow Accumulation** (MERIT Hydro or Hydrography90m, log-transformed)
3. **Height Above Nearest Drainage (HAND)** (MERIT Hydro)
4. **Soil Moisture - Annual Mean** (TerraClimate)
5. **Climate Water Deficit - Growing Season** (TerraClimate)

**Tier 2 - High Value-Added** (next implementation phase):
1. **Topographic Wetness Index (TWI)** (calculated from MERIT DEM)
2. **Distance to Seasonal Water** (JRC GSW seasonality > 6 months)
3. **Stream Power Index (SPI)** (calculated from flow accumulation + slope)
4. **Water Balance - Annual** (TerraClimate ppt - pet)
5. **Drought Frequency** (TerraClimate PDSI < -2 over 20 years)

**Tier 3 - Specialized Variables** (for specific use cases):
1. **Topographic Position Index (TPI)** (valley vs. ridge classification)
2. **Convergence Index** (seepage zones)
3. **Terrain Ruggedness Index (TRI)** (microhabitat diversity)
4. **Upstream Land Cover** (HydroATLAS)
5. **River Network Density** (calculated from HydroSHEDS)

### 5.2 GEE Code Template

```javascript
// ===== HYDROLOGICAL VARIABLES FOR SPECIES DISTRIBUTION =====

// 1. Distance to Permanent Water
var gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater');
var permanentWater = gsw.select('occurrence').gte(75);
var distPermanentWater = permanentWater.fastDistanceTransform().sqrt()
  .multiply(30) // Convert to meters
  .rename('dist_permanent_water');

// 2. Distance to Seasonal Water
var seasonalWater = gsw.select('seasonality').gte(6);
var distSeasonalWater = seasonalWater.fastDistanceTransform().sqrt()
  .multiply(30)
  .rename('dist_seasonal_water');

// 3. Flow Accumulation (log-transformed)
var merit = ee.Image('MERIT/Hydro/v1_0_1');
var flowAcc = merit.select('upa').log10().rename('log_flow_accumulation');

// 4. Height Above Nearest Drainage (HAND)
var hand = merit.select('hnd').rename('hand');

// 5. Topographic Wetness Index (TWI)
var dem = merit.select('elv');
var slope = ee.Terrain.slope(dem).multiply(Math.PI/180); // Radians
var specificArea = merit.select('upa').multiply(90); // Cell size 90m
var twi = specificArea.divide(slope.tan().add(0.001)).log()
  .rename('twi');

// 6. Stream Power Index (SPI)
var spi = specificArea.multiply(slope.tan()).log10()
  .rename('log_spi');

// 7. TerraClimate Variables
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
  .filterDate('2010-01-01', '2020-12-31');

// Annual mean soil moisture
var soilMoisture = tc.select('soil').mean()
  .rename('soil_moisture_mean');

// Growing season water deficit (Apr-Sep Northern Hemisphere)
var waterDeficit = tc.filter(ee.Filter.calendarRange(4, 9, 'month'))
  .select('def').sum().mean()
  .rename('water_deficit_growing_season');

// Annual water balance
var ppt = tc.select('pr').sum().mean();
var pet = tc.select('pet').sum().mean();
var waterBalance = ppt.subtract(pet).rename('water_balance_annual');

// Drought frequency
var pdsi = tc.select('PDSI');
var drought = pdsi.map(function(img) {
  return img.lt(-2);
});
var droughtFreq = drought.sum().divide(pdsi.size())
  .rename('drought_frequency');

// 8. Topographic Position Index (TPI)
var tpi = dem.subtract(dem.reduceNeighborhood({
  reducer: ee.Reducer.mean(),
  kernel: ee.Kernel.circle(500, 'meters')
})).rename('tpi_500m');

// Combine all variables
var hydroVariables = ee.Image.cat([
  distPermanentWater,
  distSeasonalWater,
  flowAcc,
  hand,
  twi,
  spi,
  soilMoisture,
  waterDeficit,
  waterBalance,
  droughtFreq,
  tpi
]);

// Export or sample at point locations
var point = ee.Geometry.Point([lon, lat]);
var sample = hydroVariables.sample({
  region: point,
  scale: 90,
  projection: 'EPSG:4326'
});

print('Hydrological Variables:', sample);
```

### 5.3 Computational Considerations

**Resolution Selection**:
- Use 90m (MERIT Hydro) as baseline resolution for consistency
- TerraClimate will be resampled from 4km → 90m (bilinear interpolation)
- JRC GSW already at 30m, resample to 90m for compatibility

**Processing Efficiency**:
- Pre-compute static variables (TWI, SPI, HAND) as assets
- Only calculate temporal TerraClimate summaries on-the-fly
- Use `.reduceRegion()` for point sampling, not `.clip()` for speed
- Set `bestEffort: true` for large regions

**Data Volumes**:
- 11 variables × 4 bytes/pixel × (region area / 8100 m²)
- For 1 million points: ~44 MB
- For global extent (at 90m): ~50 GB (requires tiling strategy)

**Fallback for Missing Data**:
- HydroSHEDS coverage ends at 60°N, use Hydrography90m for Arctic
- TerraClimate soil moisture may have gaps in ice-covered regions
- JRC GSW has data quality masks - use metadata layer

### 5.4 Variable Transformations

**Log Transformations** (reduce skewness):
- Flow accumulation: `log10(upa + 1)`
- Stream Power Index: `log10(spi + 1)`
- Distance to water: `log10(dist + 1)`

**Normalization** (0-1 scale):
```javascript
var normalize = function(image, min, max) {
  return image.subtract(min).divide(max - min).clamp(0, 1);
};

var twiNorm = normalize(twi, 0, 20); // Typical TWI range 0-20
```

**Categorical Bins**:
```javascript
// Distance to water classes
var distClass = distPermanentWater
  .where(distPermanentWater.lte(50), 1)    // Obligate riparian
  .where(distPermanentWater.gt(50).and(distPermanentWater.lte(200)), 2)  // Facultative
  .where(distPermanentWater.gt(200).and(distPermanentWater.lte(500)), 3) // Influenced
  .where(distPermanentWater.gt(500), 4);   // Upland
```

### 5.5 Integration with AlphaEarth Pipeline

**Current AlphaEarth Variables** (assumed):
- Elevation, slope, aspect
- Temperature (mean, min, max)
- Precipitation
- Solar radiation
- Soil properties (clay, sand, organic carbon, pH)
- Land cover
- Vegetation indices (NDVI, EVI)

**Hydrological Variables to Add**:
1. `dist_permanent_water_log`
2. `hand`
3. `log_flow_accumulation`
4. `twi`
5. `soil_moisture_mean`
6. `water_deficit_growing_season`
7. `water_balance_annual`

**Expected Impact**:
- 15-25% improvement in AUC for riparian species
- 5-10% improvement for water-limited species (arid regions)
- Minimal impact (<2%) for water-independent alpine/boreal species

**Testing Protocol**:
1. Select 50 test species across moisture gradients:
   - 15 obligate riparian
   - 15 facultative riparian
   - 10 mesic forest
   - 10 xeric woodland
2. Run models with/without hydrological variables
3. Compare AUC, TSS, and calibration curves
4. Assess variable importance using permutation or SHAP values

### 5.6 Validation Strategies

**Direct Validation** (where possible):
- Compare TWI predictions to field-measured soil moisture (if available)
- Validate HAND against flood inundation maps
- Check distance-to-water against high-res imagery

**Indirect Validation** (using species occurrences):
- Known riparian species should have:
  - Low dist_permanent_water (<200m)
  - Low HAND (<10m)
  - High TWI (>10)
  - High soil_moisture_mean
- Known xeric species should show opposite patterns

**Error Assessment**:
- HydroSHEDS flow accumulation may underestimate small streams
- TWI unreliable in flat terrain (slope → 0 causes instability)
- TerraClimate soil moisture coarse resolution misses local variation
- JRC GSW misses narrow headwater streams

---

## 6. Literature and Citation Guidance

### Key Papers for Methodology

**Topographic Wetness Index**:
- Beven, K.J., & Kirkby, M.J. (1979). A physically based, variable contributing area model of basin hydrology. Hydrological Sciences Bulletin, 24(1), 43-69.
- Sörensen, R., et al. (2006). On the calculation of the topographic wetness index: evaluation of different methods based on field observations. Hydrology and Earth System Sciences, 10, 101-112.

**HydroSHEDS**:
- Lehner, B., et al. (2008). New global hydrography derived from spaceborne elevation data. Eos, 89(10), 93-94.
- Lehner, B., & Grill, G. (2013). Global river hydrography and network routing: baseline data and new approaches to study the world's large river systems. Hydrological Processes, 27(15), 2171-2186.

**Global Surface Water**:
- Pekel, J.F., et al. (2016). High-resolution mapping of global surface water and its long-term changes. Nature, 540, 418-422.

**TerraClimate**:
- Abatzoglou, J.T., et al. (2018). TerraClimate, a high-resolution global dataset of monthly climate and climatic water balance from 1958–2015. Scientific Data, 5, 170191.

**MERIT Hydro**:
- Yamazaki, D., et al. (2019). MERIT Hydro: A high-resolution global hydrography map based on latest topography dataset. Water Resources Research, 55, 5053-5073.

**Phreatophyte Ecology**:
- Cooper, D.J., et al. (2006). Plant species distribution in relation to water-table depth and soil redox potential in montane riparian meadows. Wetlands, 26(1), 131-146.
- Horton, J.L., et al. (2001). Responses of riparian trees to interannual variation in ground water depth in a semi-arid river basin. Plant, Cell & Environment, 24(3), 293-304.

**Stream Power**:
- Knighton, D. (1999). Downstream variation in stream power. Geomorphology, 29(3-4), 293-306.
- Bizzi, S., & Lerner, D.N. (2015). The use of stream power as an indicator of channel sensitivity to erosion and deposition processes. River Research and Applications, 31(1), 16-27.

### Applications in Species Distribution Modeling

**Hydrological Variables in SDMs**:
- Domisch, S., et al. (2015). Near-global freshwater-specific environmental variables for biodiversity analyses in 1 km resolution. Scientific Data, 2, 150073.
- Beauregard, F., & de Blois, S. (2016). Beyond a climate-centric view of plant distribution: edaphic variables add value to distribution models. PLoS One, 11(3), e0149115.

**Riparian Species Modeling**:
- Stella, J.C., et al. (2013). Riparian vegetation research in Mediterranean-climate regions: common patterns, ecological processes, and considerations for management. Hydrobiologia, 719(1), 291-315.
- Catford, J.A., et al. (2011). The intermediate disturbance hypothesis and plant invasions: Implications for species richness and management. Perspectives in Plant Ecology, Evolution and Systematics, 13(3), 231-241.

**Google Earth Engine Applications**:
- Gorelick, N., et al. (2017). Google Earth Engine: Planetary-scale geospatial analysis for everyone. Remote Sensing of Environment, 202, 18-27.
- Boothroyd, R.J., et al. (2021). Applications of Google Earth Engine in fluvial geomorphology for detecting river channel change. WIREs Water, 8(1), e1496.

---

## 7. Summary and Next Steps

### Key Findings

1. **Hydrological variables are essential** for modeling water-dependent tree species, particularly in riparian zones, arid regions, and areas with shallow water tables.

2. **Five variable classes** provide complementary information:
   - **Topographic proxies** (TWI, HAND, TPI) - static, high-resolution
   - **Surface water proximity** (JRC GSW) - dynamic, 30m resolution
   - **Flow dynamics** (flow accumulation, SPI) - geomorphological context
   - **Soil moisture/water balance** (TerraClimate) - temporal variability
   - **Groundwater proxies** (inverse of TWI, HAND) - indirect but useful

3. **All recommended datasets are freely available in GEE**, enabling global-scale analysis without data acquisition barriers.

4. **Phreatophyte species** show strong relationships with water table depth, providing ecological validation for hydrological predictors.

5. **Riparian zones** can be delineated using combinations of HAND (<10m), flow accumulation (>1000), and distance to water (<200m).

### Implementation Priority for AlphaEarth

**Phase 1** (immediate):
- Distance to permanent water (simple calculation)
- HAND from MERIT Hydro (pre-calculated band)
- Soil moisture from TerraClimate (direct access)

**Phase 2** (within 1 month):
- TWI calculation from MERIT DEM
- Flow accumulation from MERIT Hydro or Hydrography90m
- Water deficit and water balance from TerraClimate

**Phase 3** (optional enhancements):
- Stream Power Index calculation
- Topographic Position Index
- Distance to seasonal water with temporal dynamics

### Expected Benefits

1. **Improved model performance** for 1000+ riparian and water-dependent species in Treekipedia database
2. **Better predictions in arid regions** where water availability is primary limiting factor
3. **Restoration planning applications** by identifying suitable habitat based on hydrological requirements
4. **Climate change vulnerability assessment** using TerraClimate temporal trends (drought frequency, water deficit)

### Research Questions for Validation

1. Do riparian species (*Salix*, *Populus*, *Fraxinus*) show significantly higher importance for distance-to-water variables?
2. How does TWI compare to direct soil moisture data from TerraClimate in predicting mesic vs. xeric species?
3. Can we identify "cryptic phreatophytes" (species with undocumented groundwater dependence) using model residuals?
4. What is the optimal distance-to-water threshold for classifying riparian vs. upland species?

### Code Repository and Documentation

Recommend creating:
1. **GEE script library** for hydrological variable extraction
2. **Species-specific water requirements database** (linking taxon_id to phreatophyte classification)
3. **Validation reports** comparing model performance with/without hydro variables
4. **Visualization dashboard** showing variable importance for individual species

---

## Sources

### Topographic Wetness Index and Species Distribution Modeling
- [NASA WET (Wetland Extent Tool) on GitHub](https://github.com/NASA-DEVELOP/WET)
- [Topographic Wetness Index calculation guidelines - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0048969720373162)
- [HESS - On the calculation of the topographic wetness index](https://hess.copernicus.org/articles/10/101/2006/hess-10-101-2006.html)
- [Species Distribution Modeling in Google Earth Engine](https://developers.google.com/earth-engine/tutorials/community/species-distribution-modeling)
- [SDM in GEE Supplemental Materials](https://smithsonian.github.io/SDMinGEE/)

### HydroSHEDS and Global Hydrological Data
- [HydroSHEDS Datasets in Earth Engine](https://developers.google.com/earth-engine/datasets/tags/hydrosheds)
- [WWF HydroSHEDS Flow Accumulation](https://developers.google.com/earth-engine/datasets/catalog/WWF_HydroSHEDS_15ACC)
- [WWF HydroSHEDS Drainage Direction](https://developers.google.com/earth-engine/datasets/catalog/WWF_HydroSHEDS_15DIR)
- [MERIT Hydro Global Hydrography Datasets](https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1)

### Riparian and Phreatophyte Species Ecology
- [Phreatophyte - Wikipedia](https://en.wikipedia.org/wiki/Phreatophyte)
- [Water-table depth effects on riparian vegetation - Hydrogeology Journal](https://link.springer.com/article/10.1007/s10040-020-02295-8)
- [Plant species distribution and water-table depth in riparian meadows - Wetlands](https://link.springer.com/article/10.1672/0277-5212(2006)26%5B131:PSDIRT%5D2.0.CO;2)
- [Populus euphratica leafing intensity and water table depth - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1146609X20301648?dgcid=rss_sd_all)
- [Groundwater dependence of riparian woodlands - PNAS](https://www.pnas.org/doi/10.1073/pnas.2026453118)

### Stream Power, Erosion, and Geomorphology
- [Hydrography 90m Layers in GEE Community Catalog](https://gee-community-catalog.org/projects/hydro90/)
- [Google Earth Engine for Water Resources Management Course](https://courses.spatialthoughts.com/gee-water-resources-management.html)
- [Applications of GEE in fluvial geomorphology - WIREs Water](https://wires.onlinelibrary.wiley.com/doi/full/10.1002/wat2.1496)
- [Testing a Stream Power Index Tool - Journal of Sustainable Water](https://ascelibrary.org/doi/abs/10.1061/JSWBAY.0000989)

### TerraClimate and Global Surface Water
- [TerraClimate Climate Data Guide](https://climatedataguide.ucar.edu/climate-data/terraclimate-global-high-resolution-gridded-temperature-precipitation-and-other-water)
- [TerraClimate in Earth Engine Data Catalog](https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_TERRACLIMATE)
- [TerraClimate Scientific Data paper](https://www.nature.com/articles/sdata2017191)
- [JRC Global Surface Water Mapping Layers v1.4](https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_GlobalSurfaceWater)
- [Global Surface Water Data Access](https://global-surface-water.appspot.com/download)

---

**Document Prepared By**: Research Agent
**For**: AlphaEarth/Treekipedia Integration
**Next Review**: After Phase 1 implementation and validation