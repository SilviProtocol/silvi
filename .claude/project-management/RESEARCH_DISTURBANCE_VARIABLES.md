# Disturbance and Land Use History Variables for Species Distribution Modeling

**Last Updated**: January 21, 2026
**Research Focus**: Fire history, land use legacy, human footprint, fragmentation, successional dynamics
**Target Application**: Treekipedia AlphaEarth integration and restoration planning

---

## Executive Summary

Disturbance and land use history are critical predictors in species distribution modeling (SDM) that capture temporal dynamics and legacy effects often missed by static environmental variables. This research identifies seven key variable categories with established GEE implementations for integration into Treekipedia's AlphaEarth sampling framework.

**Priority Recommendations**:
1. **Hansen Global Forest Change** (loss/gain, 2000-2024, 30m resolution) - immediate implementation
2. **Human Footprint Index** (time series 2000-2018/2020, 100-1000m) - high priority
3. **LANDFIRE MFRI** (US-only, historical fire return intervals) - regional priority
4. **HILDA+ v2.0** (land use change 1960-2020, 1km) - global context
5. **Time-since-disturbance** (derived from Hansen loss year) - critical for succession modeling

---

## 1. Fire History Variables

### 1.1 LANDFIRE Products (USA Only)

**Mean Fire Return Interval (MFRI)**
- **Definition**: Average period between fires under presumed historical fire regime
- **GEE Asset**: `LANDFIRE/Fire/MFRI/v1_2_0`
- **Resolution**: 30m
- **Temporal Coverage**: Historical baseline (pre-European settlement)
- **Application**: Species adapted to fire-prone ecosystems (pines, oaks, chaparral species)

**Related LANDFIRE Fire Regime Products**:
- Fire Regime Groups (FRG): `LANDFIRE/Fire/FRG/v1_2_0` - categorizes fire frequency/severity
- Percent Low-severity Fire (PLS): `LANDFIRE/Fire/PLS/v1_2_0`
- Percent Mixed-severity Fire (PMS): `LANDFIRE/Fire/PMS/v1_2_0`
- Fire Return Interval (FRI): Now standalone product (as of 2024)

**Limitations**:
- USA coverage only (excludes global species ranges)
- Represents historical conditions, not current fire regimes
- Based on Vegetation Dynamics Development Tool (VDDT) modeling

**Implementation Priority**: Medium (high for US-native species modeling)

### 1.2 Global Fire Products

**MODIS Burned Area (MCD64A1)**
- **GEE Asset**: `MODIS/061/MCD64A1`
- **Resolution**: 500m
- **Temporal**: Monthly, 2000-present
- **Variables**: Burn date, burn quality assessment, first day of burning

**FIRMS Active Fires (VIIRS/MODIS)**
- **GEE Asset**: `FIRMS` collection
- **Resolution**: 375m (VIIRS), 1km (MODIS)
- **Temporal**: Near real-time
- **Application**: Recent fire history, fire frequency mapping

**Derived Variables for SDM**:
```javascript
// Calculate fire frequency (2000-2024)
var fireFrequency = burnedAreaCollection
  .select('BurnDate')
  .map(function(img) {
    return img.gt(0); // Binary: burned = 1
  })
  .sum(); // Total fires per pixel

// Years since last fire
var lastBurnYear = burnedAreaCollection
  .select('BurnDate')
  .qualityMosaic('BurnDate')
  .subtract(ee.Date(Date.now()).get('year'));
```

**Implementation Priority**: High (global coverage, readily available)

---

## 2. Land Use History

### 2.1 HILDA+ Global Land Use Change

**Dataset Overview**:
- **Name**: HIstoric Land Dynamics Assessment+ v2.0
- **Temporal**: 1960-2020 (annual time steps)
- **Resolution**: 1km (~0.01°)
- **Access**: PANGAEA repository (DOI: 10.1594/PANGAEA.974335)
- **GEE Status**: Not directly in GEE catalog (requires manual upload)

**Land Use Categories** (12 classes):
- Urban, cropland, pasture, rangeland
- Primary/secondary forest (managed/unmanaged)
- Water, other land

**Key Innovation**: Distinguishes pasture (livestock grazing) from natural grassland - critical for grassland species modeling.

**Agricultural Legacy Variables**:
```python
# Derived metrics for SDM
1. Years since cropland abandonment
2. Years under continuous agriculture
3. Land use transitions (e.g., forest→cropland→pasture)
4. Cumulative disturbance intensity (transition count)
```

**Biodiversity Applications**:
- Primary dataset for habitat environment definition in global biodiversity models
- Captures diverging trends: afforestation in Global North, deforestation in South
- 32% of global land affected by land use change (1960-2019) - 4x previous estimates

**Implementation Strategy**:
1. Download regional subsets from PANGAEA
2. Upload to GEE as ImageCollection
3. Calculate time-since-transition variables
4. Sample at species occurrence centroids

**Implementation Priority**: High (global coverage, biodiversity-validated)

### 2.2 Hansen Global Forest Change

**Dataset Overview**:
- **GEE Asset**: `UMD/hansen/global_forest_change_2024_v1_12`
- **Temporal**: 2000-2024 (annual loss updates)
- **Resolution**: 30m
- **Data Source**: Landsat time series

**Key Bands**:
- `treecover2000`: Forest canopy cover percentage in year 2000
- `loss`: Binary forest loss (2000-2024)
- `gain`: Binary forest gain (2000-2012)
- `lossyear`: Year of forest loss (1-24 = 2001-2024)
- `datamask`: Data/no-data distinction

**Critical Variables for SDM**:

**1. Forest Loss (Deforestation Pressure)**
```javascript
var dataset = ee.Image('UMD/hansen/global_forest_change_2024_v1_12');
var forestLoss = dataset.select('loss');
var lossYear = dataset.select('lossyear');

// Visualize loss
Map.addLayer(forestLoss.updateMask(forestLoss),
  {palette: ['FF0000']}, 'Forest Loss 2000-2024');
```

**2. Time Since Disturbance**
```javascript
// Calculate years since forest loss
var currentYear = 2024;
var yearsSinceLoss = lossYear.where(lossYear.gt(0),
  currentYear - (2000 + lossYear));

// Categorize successional stage
var successionalStage = yearsSinceLoss
  .where(yearsSinceLoss.lt(5), 1)    // Early succession
  .where(yearsSinceLoss.gte(5).and(yearsSinceLoss.lt(15)), 2)  // Mid
  .where(yearsSinceLoss.gte(15), 3); // Late/mature
```

**3. Forest Fragmentation Metrics**
```javascript
// Calculate forest patch size (requires neighborhood analysis)
var forestMask = dataset.select('treecover2000').gt(30); // >30% canopy
var patchSize = forestMask.reduceNeighborhood({
  reducer: ee.Reducer.sum(),
  kernel: ee.Kernel.circle(500, 'meters') // 500m radius
});
```

**Logging/Harvest History Effects**:
- Hansen "loss" captures all forest canopy removal (logging, fire, disease, harvest)
- Repeated loss in same location = intensive management/selective logging
- Old-growth species negatively correlated with loss frequency
- Pioneer species positively correlated with recent loss (succession)

**Implementation Priority**: **CRITICAL** - Already in GEE, 30m resolution, annual updates

---

## 3. Human Footprint and Fragmentation Indices

### 3.1 Global Human Footprint Datasets

**Wildlife Conservation Society (WCS) Human Footprint**
- **Temporal**: 1993, 2009, time series 2000-2018/2020
- **Resolution**: 100m (recent operational approach), 1km (historical)
- **GEE Access**: Available via open-source code and Google Cloud Storage as COGs
- **Components**: Built environments, population density, electric infrastructure, crop/pasture lands, roads, railways, navigable waterways

**Human Influence Index (HII) in GEE**:
- **Access**: Public bucket on Google Cloud Storage
- **Format**: Cloud-Optimized GeoTIFFs
- **Variables**: Composite pressure index (0-64 scale)

**Brazil High-Resolution HFP (HIBR-10)**
- **Resolution**: 10m (10,000x higher than previous datasets)
- **Coverage**: Brazil only (2020)
- **Innovation**: Detects small-range fragmented habitats missed at coarse resolution
- **Application**: Critical for species in fragmented Atlantic Forest, Amazon edge habitats

**Implementation Example**:
```javascript
// Load HFP from external source (requires asset upload)
var hfp2020 = ee.Image('users/your_assets/HFP_2020');

// Calculate change in human pressure (2000-2020)
var hfp2000 = ee.Image('users/your_assets/HFP_2000');
var hfpChange = hfp2020.subtract(hfp2000);

// Identify areas of increasing vs. decreasing pressure
var increasingPressure = hfpChange.gt(0);
```

**Implementation Priority**: High (global coverage, direct biodiversity relevance)

### 3.2 Fragmentation Metrics for Species Modeling

**Three Core Metrics from Literature**:

**1. Distance to Core Habitat**
- **Definition**: Average Euclidean distance from patch edge into suitable habitat core
- **Application**: Interior forest specialists (canopy birds, salamanders)
- **GEE Implementation**: Distance transform on habitat suitability maps

**2. Patch Isolation**
- **Definition**: Average Euclidean distance between suitable habitat patches through matrix
- **Application**: Dispersal-limited species, connectivity modeling
- **Calculation**: Nearest-neighbor distance in fragmented landscapes

**3. Matrix Condition**
- **Definition**: Extent of high human pressure overlapping unsuitable habitat
- **Innovation**: Recognizes that matrix quality affects species persistence
- **Metric**: Human Footprint Index overlaid on low-suitability areas

**Implementation Strategy**:
```javascript
// 1. Distance to core habitat
var habitatMask = suitabilityMap.gt(0.5);
var distanceToEdge = habitatMask.distance(ee.Kernel.euclidean(5000));
var coreHabitat = distanceToEdge.gt(500); // >500m from edge

// 2. Patch isolation (requires connected components)
var patches = habitatMask.connectedPixelCount(1000, true);
var largePatchMask = patches.gt(100); // >100 connected pixels

// 3. Matrix condition
var matrix = suitabilityMap.lt(0.3); // Unsuitable habitat
var matrixPressure = matrix.multiply(humanFootprint);
var meanMatrixPressure = matrixPressure.reduceRegion({
  reducer: ee.Reducer.mean(),
  geometry: speciesRange,
  scale: 1000
});
```

**Ecological Intactness Index (EII)**:
- Combines habitat quality, fragmentation, and connectivity
- Derived from Human Industrial Footprint (HIF)
- Application: Filtering occurrence data to intact vs. degraded habitats

**Implementation Priority**: Medium-High (computationally intensive, high ecological value)

---

## 4. Time Since Disturbance and Successional Stage

### 4.1 Remote Sensing Approaches

**Spectral Recovery Indicators**:

**1. Normalized Burn Ratio (NBR)**
- **Formula**: (NIR - SWIR) / (NIR + SWIR)
- **Application**: Post-fire recovery tracking
- **Recovery Definition**: Time to reach 80% of pre-disturbance NBR value
- **Mean Recovery Time**: 1.6-4.2 years (varies by bioclimate zone)

**2. Tasseled Cap Greenness (TCG)**
- **Application**: Vegetation structural recovery
- **Combined with NBR**: Multi-indicator approach improves accuracy

**3. NDVI Trajectory Clustering**
- **Application**: Identifying successional pathways in heterogeneous forests
- **Method**: Time series clustering (k-means, hierarchical) on annual NDVI
- **Output**: Successional stage classes (early, mid, late)

**4. Fractional Vegetation Cover (FVC)**
- **Advantage**: More sensitive for early succession stages than NBR
- **Application**: Herbaceous layer recovery, shrub establishment

**GEE Implementation - Landsat Time Series Recovery**:
```javascript
// Calculate post-disturbance recovery trajectory
var preDist = landsatCollection.filterDate('1998-01-01', '2000-01-01')
  .median().select('NBR');

var postDistSeries = landsatCollection.filterDate('2000-01-01', '2024-01-01')
  .map(function(img) {
    var nbr = img.select('NBR');
    var recovery = nbr.divide(preDist).multiply(100); // % of pre-dist
    return img.addBands(recovery.rename('recovery_pct'));
  });

// Find year when recovery reaches 80% threshold
var recoveryYear = postDistSeries
  .map(function(img) {
    var recovered = img.select('recovery_pct').gte(80);
    return img.updateMask(recovered).select('system:time_start');
  })
  .min(); // First year reaching threshold

// Calculate recovery duration
var recoveryDuration = recoveryYear.subtract(disturbanceYear);
```

**Recovery Duration Variables**:
- **Fast recovery** (<5 years): Pioneer species dominance, herbaceous-dominated
- **Medium recovery** (5-20 years): Secondary forest development, shrub-to-tree transition
- **Slow recovery** (>20 years): Old-growth species recruitment, structural complexity

**Implementation Priority**: High (temporal dynamics critical for succession-dependent species)

### 4.2 Successional Stage Classification

**Data-Driven Approaches**:

**Method 1: Age-Based Classification (Hansen Loss Year)**
```python
# Derive successional stage from time since loss
0-5 years:    Early succession (pioneers, herbaceous)
5-15 years:   Mid succession (young forest, shrub-dominated)
15-30 years:  Late succession (maturing forest)
>30 years:    Old-growth characteristics (if undisturbed)
No loss:      Continuous forest (may be old-growth or plantation)
```

**Method 2: Spectral Trajectory Analysis**
- Cluster pixels by NDVI/NBR/EVI time series shape
- Validate clusters against field data on successional stage
- Assign ecological labels to spectral clusters

**Method 3: Disturbance Agent Differentiation**
- **Finding**: Anthropogenic disturbances (logging) show slower recovery than natural (fire, wind)
- **Application**: Distinguish logged areas (slow recovery) from fire-regenerated (fast recovery)
- **Implementation**: Combine Hansen loss with FIRMS fire data

**Critical for SDM**:
- Old-growth species: Require >50 years since disturbance
- Early successional species: Optimal in 0-10 year post-disturbance
- Mid-successional species: Peak in 10-30 year windows

---

## 5. Edge Effects and Patch Metrics

### 5.1 Edge Distance Variables

**Ecological Rationale**:
- Forest edges experience altered microclimate (temperature, humidity, light)
- Edge effects extend 50-500m into forest interior (species-dependent)
- Many forest species avoid edges; edge specialists favor them

**GEE Implementation**:
```javascript
// Calculate distance to forest edge
var forestMask = treecover.gt(30);
var nonForest = forestMask.not();

// Distance transform
var distToEdge = nonForest.fastDistanceTransform()
  .sqrt()
  .multiply(ee.Image.pixelArea().sqrt()); // Convert to meters

// Categorize edge influence zones
var edgeZones = distToEdge
  .where(distToEdge.lt(50), 1)    // Edge (0-50m)
  .where(distToEdge.gte(50).and(distToEdge.lt(200)), 2)  // Transition
  .where(distToEdge.gte(200), 3); // Interior (>200m)
```

**Species-Specific Edge Thresholds**:
- **Edge avoiders**: Minimum 100-500m from edge (interior specialists)
- **Edge neutral**: 0-100m tolerance
- **Edge specialists**: Maximum within 50m of edge

### 5.2 Patch Size and Shape Metrics

**Core Metrics**:

**1. Patch Area**
```javascript
// Connected component analysis
var patches = forestMask.connectedPixelCount(10000, true);
var patchArea = patches.multiply(ee.Image.pixelArea()).divide(10000); // Hectares
```

**2. Perimeter-to-Area Ratio (Shape Complexity)**
```javascript
// Identify edge pixels
var edgePixels = forestMask.reduceNeighborhood({
  reducer: ee.Reducer.min(),
  kernel: ee.Kernel.square(1)
}).eq(0).and(forestMask);

var perimeter = edgePixels.multiply(ee.Image.pixelArea().sqrt().multiply(4));
var shapeIndex = perimeter.divide(patchArea.sqrt());
```

**3. Core Area (Interior Habitat)**
```javascript
// Area >100m from edge
var coreArea = distToEdge.gt(100).multiply(ee.Image.pixelArea());
var coreAreaFraction = coreArea.divide(patchArea);
```

**Ecological Thresholds**:
- **Minimum viable patch**: 100-1000 ha (species-dependent)
- **Core area requirement**: 30-70% of patch area for interior species
- **Shape complexity**: High edge/area ratio = increased edge effects

**Fragmentation Impact on Species**:
- Reduced patch size → local extinction risk for area-sensitive species
- Increased isolation → dispersal limitation, genetic isolation
- Edge dominance → unsuitable for interior specialists

---

## 6. Logging/Harvest History Effects on Species

### 6.1 Selective Logging Detection

**Challenges**:
- Selective logging often below Hansen 30m resolution detection threshold
- Canopy gaps may close rapidly in tropical forests
- Requires high-resolution or SAR data for detection

**Proxy Variables from Available Data**:

**1. Forest Degradation Indices**
```javascript
// Detect partial canopy loss (degradation vs. deforestation)
var canopyLoss = treecover2000.subtract(currentTreecover);
var degradation = canopyLoss.gt(10).and(canopyLoss.lt(50)); // 10-50% loss
var deforestation = canopyLoss.gte(50); // >50% loss
```

**2. Repeated Disturbance (Selective Logging Cycles)**
```javascript
// Analyze Hansen loss time series for multiple events
var lossCount = hansenCollection
  .map(function(img) { return img.select('loss'); })
  .sum(); // Pixels with 2+ loss events = repeated logging
```

**3. Road Proximity (Logging Infrastructure)**
- Distance to roads (OpenStreetMap in GEE)
- Logging roads visible in high-res imagery
- Proximity <1km to roads = higher logging probability

**Species Responses to Logging**:

**Negative Associations**:
- Old-growth specialists (large snags, coarse woody debris)
- Slow-dispersing species (fragmentation-sensitive)
- Interior forest species (increased edge effects)

**Positive Associations**:
- Pioneer species (light-demanding, gap specialists)
- Disturbed-habitat species (invasives, generalists)
- Edge-preferring species

**Implementation in SDM**:
```python
# Feature engineering for logging history
logging_proxy = {
    'dist_to_road': distance_to_nearest_road,
    'canopy_loss_partial': degradation_mask,
    'repeated_disturbance': loss_count > 1,
    'years_since_logging': years_since_loss,
    'surrounding_forest_loss': focal_mean(loss, radius=5km)
}
```

### 6.2 Plantation vs. Natural Forest

**Critical Distinction**:
- Hansen "gain" includes both natural regeneration AND plantations
- Plantations often monocultures with low biodiversity value
- Natural regeneration = high conservation value

**Differentiation Approaches**:
1. **Spatial pattern**: Plantations show regular grid patterns
2. **NDVI uniformity**: Plantations have low spectral variance
3. **Species composition**: Remote sensing cannot distinguish (requires field data)

**SDM Implications**:
- Exclude plantation "gain" areas for natural forest species
- Include for plantation-adapted species (edge generalists)

---

## 7. GEE Data Sources and Implementation Summary

### 7.1 Priority GEE Assets for Treekipedia

| Dataset | GEE Asset ID | Resolution | Temporal | Priority | Notes |
|---------|-------------|------------|----------|----------|-------|
| **Hansen Forest Change** | `UMD/hansen/global_forest_change_2024_v1_12` | 30m | 2000-2024 | **CRITICAL** | Loss, gain, year |
| **MODIS Burned Area** | `MODIS/061/MCD64A1` | 500m | 2000-present | High | Fire frequency |
| **LANDFIRE MFRI** | `LANDFIRE/Fire/MFRI/v1_2_0` | 30m | Historical | Medium | USA only |
| **LANDFIRE FRG** | `LANDFIRE/Fire/FRG/v1_2_0` | 30m | Historical | Medium | Fire regime groups |
| **VIIRS Active Fires** | `FIRMS` collection | 375m | 2012-present | Medium | Recent fires |
| **Landsat 8/9 Collection 2** | `LANDSAT/LC08/C02/T1_L2` | 30m | 2013-present | High | Recovery trajectories |
| **Sentinel-2** | `COPERNICUS/S2_SR_HARMONIZED` | 10m | 2015-present | High | Fine-scale disturbance |

### 7.2 External Datasets (Require Upload to GEE)

| Dataset | Source | Resolution | Implementation | Priority |
|---------|--------|------------|----------------|----------|
| **HILDA+ v2.0** | [PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.974335) | 1km | Download + upload as ImageCollection | High |
| **Human Footprint (WCS)** | [WCS HFP Portal](https://wcshumanfootprint.org/) | 100m-1km | GCS bucket → GEE | High |
| **HIBR-10 (Brazil)** | [Nature Scientific Data](https://www.nature.com/articles/s41597-025-06034-0) | 10m | Regional upload | Low |

### 7.3 Derived Variable Workflow

**Step 1: Sample Base Layers at Occurrence Centroids**
```javascript
var occurrencePoints = ee.FeatureCollection('users/treekipedia/species_centroids');

var sampledData = hansenImage.sampleRegions({
  collection: occurrencePoints,
  properties: ['taxon_id'],
  scale: 30,
  geometries: false
});
```

**Step 2: Calculate Derived Metrics**
```javascript
// Time since disturbance
var yearsSinceLoss = ee.Image(2024).subtract(lossYear.add(2000));

// Fire frequency (2000-2024)
var fireFreq = modisBA.select('BurnDate').map(function(img) {
  return img.gt(0);
}).sum();

// Distance to edge
var distEdge = forestMask.not().fastDistanceTransform().sqrt()
  .multiply(ee.Image.pixelArea().sqrt());
```

**Step 3: Export for AlphaEarth Integration**
```javascript
Export.table.toDrive({
  collection: sampledData,
  description: 'disturbance_variables_export',
  fileFormat: 'CSV'
});
```

### 7.4 Integration with Existing AlphaEarth Workflow

**Current AlphaEarth Variables** (from `species_alphaearth_centroids`):
- Topography: elevation, slope, aspect
- Climate: temperature, precipitation
- Soil: clay, sand, silt, organic carbon density

**New Disturbance Variables to Add**:
```python
disturbance_variables = [
    # Hansen-derived
    'forest_loss_2000_2024',      # Binary: any loss
    'loss_year',                  # Year of loss (1-24)
    'years_since_loss',           # Time since disturbance
    'forest_gain_2000_2012',      # Binary: gain detected
    'treecover_2000',             # Baseline canopy %

    # Fire-derived
    'fire_frequency_2000_2024',   # Count of fires
    'years_since_fire',           # Time since last burn

    # Fragmentation
    'distance_to_forest_edge',    # Meters to edge
    'patch_area',                 # Hectares of connected forest
    'core_area_fraction',         # % of patch >100m from edge

    # Human pressure
    'human_footprint_2020',       # HFP index value
    'hfp_change_2000_2020',       # Change in pressure

    # Land use (HILDA+)
    'land_use_2020',              # Categorical (1-12)
    'years_since_land_use_change',# Time since transition
    'cumulative_transitions',     # Count of changes 1960-2020
]
```

**Database Schema Extension**:
```sql
-- Add to species_alphaearth_centroids table
ALTER TABLE species_alphaearth_centroids
ADD COLUMN forest_loss_2000_2024 BOOLEAN,
ADD COLUMN loss_year SMALLINT,
ADD COLUMN years_since_loss SMALLINT,
ADD COLUMN fire_frequency_2000_2024 SMALLINT,
ADD COLUMN distance_to_forest_edge REAL,
ADD COLUMN human_footprint_2020 REAL,
ADD COLUMN land_use_2020 SMALLINT;
```

---

## 8. Implementation Roadmap for Treekipedia

### Phase 1: Critical Variables (Week 1-2)

**Immediate Implementation**:
1. **Hansen Forest Loss/Gain** - Already in GEE, direct sampling
2. **Time Since Disturbance** - Derived from Hansen `lossyear`
3. **Distance to Forest Edge** - Fast distance transform on Hansen treecover

**Code Template**:
```javascript
// treekipedia/orchestrator/gee_disturbance_sampler.js
var hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12');
var occurrences = ee.FeatureCollection('users/treekipedia/occurrence_centroids');

// Sample Hansen variables
var sample = hansen.select([
  'treecover2000',
  'loss',
  'lossyear',
  'gain'
]).sampleRegions({
  collection: occurrences,
  scale: 30,
  properties: ['taxon_id', 'geohash_l7']
});

// Calculate derived variables in post-processing
// years_since_loss = 2024 - (2000 + lossyear)
```

### Phase 2: Fire and Human Footprint (Week 3-4)

**Datasets**:
1. **MODIS Burned Area** - Fire frequency calculation
2. **Human Footprint Index** - Upload from WCS portal

**Processing**:
```javascript
// Fire frequency 2000-2024
var modisBA = ee.ImageCollection('MODIS/061/MCD64A1');
var fireCount = modisBA.select('BurnDate')
  .map(function(img) { return img.gt(0); })
  .sum();

// Sample at occurrence points
var fireSample = fireCount.sampleRegions({
  collection: occurrences,
  scale: 500
});
```

### Phase 3: Land Use History (Week 5-6)

**HILDA+ Integration**:
1. Download regional subsets from PANGAEA
2. Upload to GEE as multi-band image (1960-2020)
3. Calculate transition metrics
4. Sample at occurrence centroids

**Derived Metrics**:
- Years under continuous cropland/pasture
- Time since last land use change
- Number of transitions (stability metric)

### Phase 4: Advanced Fragmentation (Month 2)

**Compute-Intensive Metrics**:
1. Patch size (connected components)
2. Core area calculation
3. Isolation metrics (nearest-neighbor distances)

**Strategy**: Pre-compute global layers at 1km resolution, store as GEE assets

---

## 9. Species-Specific Applications

### Use Case 1: Old-Growth Specialists

**Example Species**: *Pseudotsuga menziesii* (Douglas-fir, old-growth ecotype)

**Critical Variables**:
- `years_since_loss` > 50 (minimum age requirement)
- `forest_loss_2000_2024` = FALSE (continuous forest)
- `distance_to_forest_edge` > 200m (interior preference)
- `human_footprint_2020` < 10 (low disturbance)

**Prediction**: Probability peaks in undisturbed, large forest patches

### Use Case 2: Fire-Adapted Species

**Example Species**: *Pinus ponderosa* (Ponderosa pine)

**Critical Variables**:
- `fire_frequency_2000_2024` = 1-3 (moderate fire regime)
- `years_since_fire` = 5-15 (post-fire regeneration window)
- `LANDFIRE_MFRI` = 10-30 years (historical fire return interval)

**Prediction**: Probability peaks in recently burned areas with historical fire regime

### Use Case 3: Edge Specialists

**Example Species**: *Rubus spectabilis* (Salmonberry, edge/disturbance specialist)

**Critical Variables**:
- `distance_to_forest_edge` < 50m (edge preference)
- `years_since_loss` = 1-10 (early succession)
- `forest_gain_2000_2012` = TRUE (regenerating areas)

**Prediction**: Probability peaks at forest edges and recent clearings

### Use Case 4: Agricultural Avoiders

**Example Species**: Endemic tropical species

**Critical Variables**:
- `land_use_2020` ≠ cropland/pasture (avoid agriculture)
- `years_since_land_use_change` > 20 (stable forest)
- `hfp_change_2000_2020` < 0 (decreasing human pressure)

**Prediction**: Probability highest in long-term stable forests

---

## 10. Data Quality and Limitations

### Known Issues and Workarounds

**Hansen Forest Change**:
- **Issue**: 30m resolution misses selective logging, small gaps
- **Workaround**: Use Sentinel-2 (10m) for fine-scale disturbance in critical areas
- **Issue**: "Gain" includes plantations (low biodiversity value)
- **Workaround**: Cross-reference with spatial pattern analysis (grid detection)

**LANDFIRE**:
- **Issue**: USA only, historical baseline (not current conditions)
- **Workaround**: Use MODIS fire products for global current fire regime
- **Issue**: Modeled data (VDDT), not direct observation
- **Workaround**: Validate with field fire history records where available

**Human Footprint**:
- **Issue**: Coarse resolution (1km) for fragmentation-sensitive species
- **Workaround**: Use high-resolution versions (HIBR-10 for Brazil, 100m WCS operational)
- **Issue**: Temporal lag (2020 most recent global coverage)
- **Workaround**: Assume pressure continues or extrapolate from trends

**HILDA+**:
- **Issue**: 1km resolution may miss small-scale land use dynamics
- **Workaround**: Combine with Hansen 30m for forest-specific changes
- **Issue**: Not directly in GEE (requires manual upload)
- **Workaround**: Create GEE asset pipeline for regional subsets

### Validation Strategies

**1. Cross-Validation with Occurrence Data**:
```python
# Split known occurrences by disturbance gradient
intact_occurrences = df[df['human_footprint_2020'] < 10]
disturbed_occurrences = df[df['human_footprint_2020'] > 30]

# Test model performance on each subset
# Expect different variable importance
```

**2. Expert Review**:
- Consult species ecology literature for disturbance tolerance
- Validate predicted relationships (e.g., old-growth species avoid recent loss)

**3. Temporal Validation**:
- Train model on pre-2010 data, test on post-2010 occurrences
- Check if disturbance variables improve temporal transferability

---

## 11. Future Enhancements

### Emerging Datasets (2026-2027)

**1. GEDI Canopy Structure**
- **Variable**: Canopy height, vertical structure
- **Application**: Distinguish old-growth (tall, complex) from young forest
- **Status**: GEE assets available (L2A/L2B products)

**2. Sentinel-1 SAR for Logging**
- **Variable**: Backscatter change (logging detection)
- **Application**: Selective logging in tropics (below optical detection)
- **Status**: GEE available, requires preprocessing

**3. Dynamic World Land Cover**
- **Resolution**: 10m (Sentinel-2 based)
- **Temporal**: Near real-time (2015-present)
- **Application**: Fine-scale land use change, urban expansion

**4. Global Forest Watch Integrated Alerts**
- **Variables**: Tree cover loss alerts, fire alerts, commodity-driven deforestation
- **Application**: Near real-time disturbance detection
- **Status**: API access, integration with GEE possible

### Research Directions

**1. Disturbance Synergies**:
- Interaction effects: fire + logging, drought + deforestation
- Cumulative impact modeling

**2. Legacy Effects**:
- Multi-decadal land use history (beyond 1960 with HILDA+)
- Soil legacy of past agriculture (nutrient depletion persistence)

**3. Recovery Trajectories**:
- Species-specific recovery curves (not just 80% threshold)
- Asymptotic vs. overshoot recovery patterns

**4. Functional Traits**:
- Link disturbance variables to species traits (shade tolerance, seed dispersal mode)
- Trait-based filtering of occurrence data quality

---

## Conclusion

Disturbance and land use history variables represent a critical but often overlooked component of species distribution modeling. By integrating temporal dynamics—fire regimes, deforestation, land use transitions, and recovery trajectories—into Treekipedia's AlphaEarth framework, we can capture the legacy effects and ongoing processes that shape species distributions beyond static environmental conditions.

**Priority Implementation**:
1. **Hansen Global Forest Change** (loss, gain, time-since-disturbance) - immediate
2. **Human Footprint Index** (pressure gradient, change over time) - high priority
3. **Fire frequency/history** (MODIS burned area, LANDFIRE for US) - high priority
4. **HILDA+ land use change** (agricultural legacy, transitions) - medium priority

**Expected Outcomes**:
- Improved model accuracy for disturbance-sensitive and disturbance-adapted species
- Enhanced restoration planning (identify degraded vs. intact habitat)
- Better prediction of species responses to ongoing land use change
- Temporal transferability of models (predict future distributions under change scenarios)

**Next Steps**:
1. Implement Phase 1 (Hansen variables) in `orchestrator/gee_disturbance_sampler.js`
2. Extend `species_alphaearth_centroids` database schema for new variables
3. Validate variable importance with known disturbance-specialist species
4. Integrate into production AlphaEarth sampling workflow

---

## Sources

### Fire History
- [LANDFIRE MFRI v1.2.0 | Earth Engine Data Catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDFIRE_Fire_MFRI_v1_2_0)
- [Fire Return Interval | LandFire](https://www.landfire.gov/fire-regime/fri)
- [Historical Fire Regime | LandFire](https://www.landfire.gov/fire-regime)
- [LANDFIRE FRG v1.2.0 | Earth Engine Data Catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDFIRE_Fire_FRG_v1_2_0)

### Hansen Global Forest Change
- [Introduction to Hansen et al. Global Forest Change Data | Google Earth Engine](https://developers.google.com/earth-engine/tutorials/tutorial_forest_02)
- [Hansen Global Forest Change v1.12 (2000-2024) | Earth Engine Data Catalog](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12)
- [Global Forest Change Download](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/download.html)
- [Quantifying Forest Change | Google Earth Engine Tutorial](https://developers.google.com/earth-engine/tutorials/tutorial_forest_03)

### Human Footprint and Fragmentation
- [A global record of annual terrestrial Human Footprint dataset from 2000 to 2018 | Scientific Data](https://www.nature.com/articles/s41597-022-01284-8)
- [Matrix condition mediates the effects of habitat fragmentation on species extinction risk | Nature Communications](https://www.nature.com/articles/s41467-022-28270-3)
- [WCS - 20 years of the Human Footprint](https://wcshumanfootprint.org/)
- [An operational approach to near real time global high resolution mapping of the terrestrial Human Footprint | Frontiers in Remote Sensing](https://www.frontiersin.org/journals/remote-sensing/articles/10.3389/frsen.2023.1130896/full)
- [A 10-meter resolution human footprint dataset to support biodiversity and conservation studies in Brazil | Scientific Data](https://www.nature.com/articles/s41597-025-06034-0)

### Time Since Disturbance and Recovery
- [Forest recovery trends derived from Landsat time series for North American boreal forests | Taylor & Francis Online](https://www.tandfonline.com/doi/full/10.1080/2150704X.2015.1126375)
- [Analysis of trends and changes in the successional trajectories of tropical forest using the Landsat NDVI time series | ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2352938521001580)
- [Characterizing forest disturbance and recovery with thermal trajectories derived from Landsat time series data | ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0034425722003807)
- [A multi‐source remote sensing approach to identify and predict delayed succession in human‐dominated tropical landscapes | Journal of Applied Ecology](https://besjournals.onlinelibrary.wiley.com/doi/full/10.1111/1365-2664.70107)

### HILDA+ Land Use History
- [HILDA+ Global Land Use Change | CEOS](https://ceos.org/gst/HILDAplus.html)
- [Land Use Change & Climate Research Group](https://landchange.imk-ifu.kit.edu/hilda)
- [Winkler, K et al. (2025): HILDA+ version 2.0: Global Land Use Change between 1960 and 2020 | PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.974335)
- [Global land use changes are four times greater than previously estimated | Nature Communications](https://www.nature.com/articles/s41467-021-22702-2)

---

**Document Version**: 1.0
**Author**: Research Agent
**Date**: January 21, 2026
**Word Count**: ~4,950 words
