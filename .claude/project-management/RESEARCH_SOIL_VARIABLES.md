# Research: Soil Variables for Species Distribution Modeling and Restoration

**Date**: January 21, 2026
**Purpose**: Evaluate soil variables beyond pH/texture for Treekipedia's AlphaEarth integration
**Status**: Research Complete

---

## Executive Summary

This research evaluates advanced soil variables that can enhance Treekipedia's species distribution modeling and restoration planning capabilities. While the current system uses basic soil texture (sand, silt, clay) and pH from AlphaEarth, numerous additional soil properties are available through global databases accessible via Google Earth Engine (GEE). This document identifies the most valuable variables for tree species modeling and provides implementation guidance.

**Key Findings**:
- **SoilGrids250m v2.0** provides 14 soil properties globally at 250m resolution, available in GEE
- **HiHydroSoil v2.0** offers critical hydraulic properties (water holding capacity, saturated conductivity) at 250m resolution in GEE
- Soil chemical properties (CEC, nutrients) show stronger correlations with tree species distribution than topographic variables (54.5% vs 45.4% in recent studies)
- Implementation requires minimal changes to existing AlphaEarth sampling pipeline

---

## 1. Soil Physical Properties

### 1.1 Drainage Class and Permeability

**Definition**: Drainage class describes the frequency and duration of wet periods under natural conditions. Permeability measures the rate at which water percolates through soil.

**Ecological Significance**:
- Highly permeable soils reduce runoff and erosion, favoring deep-rooted species
- Poorly drained soils limit root oxygen availability, favoring hydrophytic species
- Water rapidly enters highly permeable soils, reducing runoff and soil erosion

**Relationship to Species Distribution**:
- Tree species exhibit strong preferences for drainage classes (e.g., willows for poorly drained, pines for well-drained)
- Drainage influences nutrient availability, root architecture, and competitive outcomes
- Critical for wetland vs. upland species separation

**Data Availability**:
- **Indirect derivation**: Can be inferred from texture, bulk density, and saturated hydraulic conductivity
- **HWSD v2.0**: Includes drainage classes in categorical format (global coverage, ~1km resolution)
- **Not directly in SoilGrids**: But can be modeled from hydraulic conductivity and water content

### 1.2 Soil Erodibility (K-factor)

**Definition**: The K-factor expresses the susceptibility of soil to erosion by water, measured in USLE/RUSLE (Universal Soil Loss Equation).

**Calculation**: K-factor is related to:
- Organic matter content
- Soil texture (sand, silt, clay percentages)
- Soil structure and permeability
- Saturated hydraulic conductivity (recent advanced methods)

**Ecological Significance**:
- Erosion-prone soils limit tree establishment and root stability
- High K-factor areas require erosion-resistant species for restoration
- Relates to slope stability and landslide risk

**Recent Advances**:
- Advanced global K-factor assessment now incorporates saturated hydraulic conductivity data with soil texture and organic carbon
- Machine learning models successfully predict K-factor using topographic attributes, thematic maps, and remotely sensed data
- Global K distribution shows regularity with soil properties using ISRIC 2.0 data and four algorithms (USLE-K, RUSLE2-K, EPIC-K, Dg-K)

**Data Availability**:
- **Not pre-calculated in major databases**, but derivable from SoilGrids variables:
  - Organic matter (soil organic carbon)
  - Texture (sand, silt, clay)
  - Permeability (from saturated hydraulic conductivity)
- **Implementation**: Can be calculated post-sampling using established nomographs or machine learning models

### 1.3 Depth to Bedrock

**Definition**: Vertical distance from soil surface to consolidated bedrock or lithic contact.

**Ecological Significance**:
- Limits maximum rooting depth and tree height potential
- Affects water storage capacity and drought resistance
- Shallow bedrock restricts species to those with shallow root systems

**Species Implications**:
- Deep-rooted species (e.g., oaks, hickories) require >100cm soil depth
- Shallow soils (<50cm) favor species with fibrous roots or rock-penetrating capabilities
- Critical for predicting mature tree height and drought tolerance

**Data Availability**:
- **SoilGrids**: Does not include depth to bedrock
- **HWSD v2.0**: Includes soil depth parameters
- **Regional datasets**: POLARIS (US) includes depth to bedrock at 30m resolution
- **Limitation**: Difficult to model globally; regional variation is high

### 1.4 Bulk Density

**Definition**: Mass of dry soil per unit volume, typically g/cm³.

**Ecological Significance**:
- Inversely related to porosity and root penetrability
- High bulk density (>1.6 g/cm³) restricts root growth
- Affects water infiltration and nutrient availability

**Data Availability**:
- **SoilGrids250m v2.0**: `bdod_mean` (bulk density) for 6 depth intervals globally
- **GEE Access**: `ISRIC/SoilGrids250m_v2_0` dataset

---

## 2. Soil Chemical Properties

### 2.1 Cation Exchange Capacity (CEC)

**Definition**: The soil's ability to hold and exchange cations (Ca²⁺, Mg²⁺, K⁺, NH₄⁺), measured in cmol(+)/kg.

**Ecological Significance**:
- **Critical for nutrient retention**: High CEC soils resist nutrient leaching
- **pH buffering**: Higher CEC stabilizes soil pH against rapid changes
- **Species-specific preferences**: Some species thrive in high-CEC soils (nutrient-demanding), others in low-CEC soils (nutrient-poor specialists)

**Tree Species Effects**:
- Different tree species significantly affect soil CEC
- CEC is smallest in hornbeam and oak soils, intermediate in beech soils, and largest in spruce and pine soils
- Total carbon content is the major contributor to total CEC even in loamy soils
- Tree species contribute to soil organic matter dynamics through effects on acidification and cation availability

**Research Evidence**:
- Soil chemical properties (including CEC) defined 54.5% of species-habitat associations, compared to 45.4% for topographically-defined habitat
- CEC helps soils hold nutrients and buffer pH, making it vital for maintaining basic function of terrestrial ecosystems
- Understanding CEC is critical for ecological restoration and predicting environmental requirements of tree species

**Data Availability**:
- **SoilGrids250m v2.0**: `cec_mean` (cation exchange capacity in cmol(+)/kg) for 6 depth layers
- **GEE Access**: Available in `ISRIC/SoilGrids250m_v2_0`
- **Global Coverage**: 250m resolution worldwide

### 2.2 Soil Nutrients (N, P, K)

**Nitrogen (N)**:
- **Function**: Primary macronutrient for protein synthesis and chlorophyll production
- **Forms**: Total N, available N (NO₃⁻, NH₄⁺)
- **Species Response**: Fast-growing species require high N; slow-growing species tolerate low N
- **Data Availability**:
  - **SoilGrids250m v2.0**: `nitrogen_mean` (total nitrogen in g/kg)
  - **Limitation**: Total N only; available N not mapped globally

**Phosphorus (P)**:
- **Function**: Energy transfer (ATP), root development
- **Forms**: Total P, available P (plant-accessible)
- **Species Response**: Leguminous trees less dependent; ericaceous species adapted to low P
- **Data Availability**:
  - **Not in SoilGrids or HWSD**
  - Regional datasets may include P (e.g., national soil surveys)
  - **Gap**: Major limitation for global modeling

**Potassium (K)**:
- **Function**: Water regulation, disease resistance, enzyme activation
- **Forms**: Exchangeable K, available K
- **Species Response**: Influences drought tolerance and disease susceptibility
- **Data Availability**:
  - **Not in global datasets**
  - Can be partially inferred from parent material geology
  - **Gap**: Major limitation

**Practical Implication**: Of the NPK trio, only nitrogen is available globally. Phosphorus and potassium remain significant data gaps for comprehensive species modeling.

### 2.3 Soil Organic Carbon (SOC)

**Definition**: Amount of carbon stored in soil organic matter, measured in g/kg or stock (tonnes/ha).

**Ecological Significance**:
- **Nutrient source**: Releases nutrients through decomposition
- **Water retention**: Organic matter increases water holding capacity
- **Soil structure**: Improves aggregation and reduces erosion
- **CEC contribution**: Major contributor to cation exchange capacity

**Forms Available**:
- **Concentration**: g/kg soil (density-independent)
- **Density**: Organic carbon per unit volume (accounts for bulk density)
- **Stock**: Total carbon in a depth layer (tonnes C/ha)

**Data Availability**:
- **SoilGrids250m v2.0**:
  - `soc_mean` - Soil organic carbon content (g/kg)
  - `ocd_mean` - Organic carbon density (kg/m³)
  - `ocs_mean` - Organic carbon stock (tonnes/ha)
- **All available for 6 depth layers** (0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm)
- **GEE Access**: `ISRIC/SoilGrids250m_v2_0`

---

## 3. Soil Hydraulic Properties

### 3.1 Saturated Hydraulic Conductivity (Ksat)

**Definition**: The rate at which water moves through fully saturated soil, measured in cm/day or mm/hr.

**Ecological Significance**:
- **Drainage characterization**: High Ksat = well-drained; Low Ksat = poorly drained
- **Flood tolerance**: Species in high Ksat soils less exposed to waterlogging
- **Drought response**: Affects infiltration and groundwater recharge
- **Root oxygen availability**: Low Ksat can create anaerobic conditions

**Modeling Applications**:
- **Hydrophytic species prediction**: Low Ksat areas favor wetland-adapted trees
- **Restoration planning**: Match species to site drainage capacity
- **Erosion modeling**: Integrated into advanced K-factor calculations

**Research Context**:
- Ksat is a key parameter in hydrological and climate models
- SoilKsatDB database contains 13,258 measurements from 1,908 sites globally
- High-quality datasets from Europe (572 undisturbed samples) provide validation

**Data Availability**:
- **HiHydroSoil v2.0**:
  - Variable: `ksat` (saturated hydraulic conductivity)
  - Resolution: 250m global coverage
  - **GEE Access**: Available via GEE Community Catalog
- **POLARIS** (US only):
  - Variable: `ksat_mean`
  - Resolution: 30m
  - **GEE Access**: Community Catalog
- **SoilGrids**: Not directly included, but texture data can estimate Ksat via pedotransfer functions

### 3.2 Water Holding Capacity (WHC)

**Definition**: The amount of water soil can retain against gravitational drainage, typically measured between field capacity and permanent wilting point.

**Related Concepts**:
- **Field Capacity (θ_fld)**: Water content after excess has drained (~33 kPa suction)
- **Permanent Wilting Point (θ_wlt)**: Water content when plants cannot extract water (~1500 kPa suction)
- **Available Water Capacity (AWC)**: Difference between field capacity and wilting point (plant-available water)
- **Saturated Water Content (θ_s)**: Maximum water at full saturation

**Ecological Significance**:
- **Drought resistance**: High AWC buffers trees against dry periods
- **Species sorting**: Drought-adapted species thrive in low AWC; mesic species require high AWC
- **Productivity**: Water availability limits growth in many ecosystems
- **Climate change resilience**: Critical for predicting species responses to altered precipitation

**Data Availability**:

**HiHydroSoil v2.0** (Global, 250m resolution, GEE):
- `sat-field` - Saturated water content (θ_s)
- `wcavail` - Available water capacity (AWC)
- `crit-wilt` - Critical wilting point
- **Access**: GEE Community Catalog

**SoilGrids250m v2.0** (Global, 250m resolution, GEE):
- Volumetric water content at different suctions:
  - 10 kPa (wet conditions)
  - 33 kPa (field capacity approximation)
  - 1500 kPa (permanent wilting point)
- Available for 6 depth layers
- **Calculation**: AWC = (θ at 33kPa) - (θ at 1500kPa)
- **Access**: `ISRIC/SoilGrids250m_v2_0`

**Implementation Note**: Either dataset provides sufficient information. HiHydroSoil offers derived AWC directly, while SoilGrids requires simple subtraction but offers more depth resolution.

### 3.3 Derived Hydraulic Properties

**Unsaturated Hydraulic Conductivity**:
- How water moves through partially saturated soil
- Can be predicted from saturated Ksat and water retention curves
- More complex but relevant for modeling drought stress

**Water Retention Curves**:
- Relationship between soil water content and matric potential
- Describes how tightly water is held at different moisture levels
- Advanced modeling uses parameters like van Genuchten alpha/n

**Data Availability**:
- Research datasets available (e.g., ESSD soil water retention database with 572 samples)
- Not currently mapped globally at high resolution
- Future opportunity for advanced modeling

---

## 4. Global Soil Databases Comparison

### 4.1 SoilGrids250m v2.0

**Provider**: ISRIC (International Soil Reference and Information Centre)
**Resolution**: 250m globally
**Coverage**: Complete global land coverage
**Depth Layers**: 6 standard GlobalSoilMap depths (0-5, 5-15, 15-30, 30-60, 60-100, 100-200 cm)

**Variables Available** (14 properties):
1. **Texture**: Sand, silt, clay content (%)
2. **pH**: pH in water (phh2o_mean)
3. **Bulk Density**: bdod_mean (g/cm³)
4. **Coarse Fragments**: cfvo_mean (% volume)
5. **Cation Exchange Capacity**: cec_mean (cmol(+)/kg)
6. **Nitrogen**: nitrogen_mean (total N, g/kg)
7. **Soil Organic Carbon**:
   - soc_mean (concentration, g/kg)
   - ocd_mean (density, kg/m³)
   - ocs_mean (stock, tonnes/ha)
8. **Water Content** at three suctions:
   - wv0010_mean (10 kPa)
   - wv0033_mean (33 kPa - field capacity)
   - wv1500_mean (1500 kPa - wilting point)

**Methodology**:
- Digital soil mapping using Quantile Random Forest
- Trained on 230,000+ soil profiles from WoSIS database
- Uncertainty quantified for each pixel

**GEE Access**:
- Dataset ID: `ISRIC/SoilGrids250m_v2_0`
- Also available via GEE Community Catalog
- Each variable is a multi-band image (6 bands = 6 depths)

**Strengths**:
- Comprehensive variable coverage
- High resolution (250m)
- Uncertainty estimates included
- Well-documented and actively maintained

**Limitations**:
- Does not include: depth to bedrock, P, K, drainage class
- Predictions may be less accurate in data-sparse regions
- Total nitrogen only (not available N)

### 4.2 HWSD v2.0 (Harmonized World Soil Database)

**Provider**: FAO/IIASA
**Resolution**: ~1 km (30 arc-seconds)
**Coverage**: Global land coverage
**Structure**: 15,000+ soil mapping units

**Variables Available**:
- Basic properties: texture, pH, organic carbon, bulk density
- Soil depth and drainage class
- Reference soil groups (FAO classification)
- Gravel content
- CEC (limited coverage)

**Methodology**:
- Compilation of regional and national soil maps
- Conventional soil mapping unit approach (not pixel-based predictions)
- Each grid cell assigned to a mapping unit with dominant soil properties

**GEE Access**:
- Available via GEE Community Catalog
- Dataset: `HWSD v2.0`

**Strengths**:
- Includes drainage class (categorical)
- Soil depth information
- Legacy dataset with broad adoption
- FAO soil classification

**Limitations**:
- Coarser resolution (1 km vs 250m)
- Categorical mapping units (less detail than SoilGrids pixel predictions)
- Fewer variables than SoilGrids
- No uncertainty estimates

**Use Case for Treekipedia**: Secondary dataset for drainage class and soil depth where SoilGrids lacks these.

### 4.3 HiHydroSoil v2.0

**Provider**: FutureWater
**Resolution**: 250m globally
**Coverage**: Global land coverage
**Focus**: Soil hydraulic properties

**Variables Available**:
1. **ksat** - Saturated hydraulic conductivity (cm/day)
2. **sat-field** - Saturated water content (cm³/cm³)
3. **wcavail** - Available water capacity (cm³/cm³)
4. **crit-wilt** - Critical wilting point (cm³/cm³)

**Methodology**:
- Derived from SoilGrids250m texture and organic carbon data
- Uses pedotransfer functions to estimate hydraulic properties
- Validated against measured hydraulic property databases

**GEE Access**:
- Available via GEE Community Catalog
- Dataset ID in catalog: `HiHydroSoil v2.0 layers`

**Strengths**:
- Purpose-built for hydraulic properties
- Pre-calculated AWC (no need to derive)
- Same resolution as SoilGrids (250m)
- Critical for hydrological modeling

**Limitations**:
- Fewer variables (focused on hydraulics)
- Derived product (inherits SoilGrids uncertainty)
- Relatively new (less validation than SoilGrids)

**Use Case for Treekipedia**: Primary source for water holding capacity and saturated hydraulic conductivity.

### 4.4 POLARIS

**Provider**: USDA/University of Wisconsin
**Resolution**: 30m (US only)
**Coverage**: Contiguous United States (CONUS)
**Depth Layers**: 6 layers matching SoilGrids

**Variables Available** (13 properties):
- Texture: sand, silt, clay
- pH
- Bulk density
- Organic matter
- **Saturated hydraulic conductivity** (ksat_mean)
- **Depth to bedrock**
- Water content at 33 kPa and 1500 kPa

**Methodology**:
- Probabilistic remapping of SSURGO (detailed US soil survey)
- Provides mean and quantiles (5th, 50th, 95th percentiles)
- Machine learning disaggregation of SSURGO polygons

**GEE Access**:
- Available via GEE Community Catalog
- Very high resolution (30m vs 250m)

**Strengths**:
- Highest resolution (30m)
- Includes depth to bedrock and Ksat
- Probabilistic estimates (uncertainty quantification)
- Based on detailed field surveys (SSURGO)

**Limitations**:
- **US only** (not global)
- Not applicable for global Treekipedia deployment

**Use Case for Treekipedia**: Potential for future US-specific enhanced predictions, but not for global deployment.

### 4.5 OpenLandMap

**Provider**: OpenGeoHub Foundation
**Resolution**: 250m - 1km (variable by product)
**Coverage**: Global
**Methodology**: Machine learning on point observations and covariates

**Variables Available**:
- Comprehensive suite overlapping with SoilGrids
- Additional layers for soil type, land cover, climate
- Comparison studies show similar accuracy to SoilGrids

**GEE Access**:
- Some layers available in GEE Community Catalog
- Documentation: https://openlandmap.org

**Strengths**:
- Open-source and actively developed
- Comparable to SoilGrids in many variables
- Integrated with broader environmental datasets

**Limitations**:
- Variable documentation quality
- Less standardized than SoilGrids
- Fragmented access (not all layers in single GEE collection)

**Use Case for Treekipedia**: Alternative/supplementary to SoilGrids, but SoilGrids preferred for standardization.

### 4.6 Database Selection Recommendation

**For Treekipedia Implementation**:

**Primary Dataset**: **SoilGrids250m v2.0**
- Rationale: Best balance of variable coverage, resolution, global extent, and GEE integration
- Variables: Texture, pH, CEC, N, SOC, bulk density, water content

**Secondary Dataset**: **HiHydroSoil v2.0**
- Rationale: Provides critical hydraulic properties (Ksat, AWC) not in SoilGrids
- Variables: Saturated conductivity, available water capacity, wilting point

**Tertiary Dataset (optional)**: **HWSD v2.0**
- Rationale: Drainage class and soil depth (gaps in SoilGrids)
- Use: Supplement for specific analyses requiring these variables

**Not Recommended for Global Use**: POLARIS (US-only), OpenLandMap (less standardized)

---

## 5. GEE Availability and Implementation for Treekipedia

### 5.1 Current AlphaEarth Sampling Architecture

**Existing Implementation** (`orchestrator/location_predictor_FIXED.py`):
```python
# Current AlphaEarth variables sampled:
- Clay (0-5cm): clay_0_5cm_merged
- Sand (0-5cm): sand_0_5cm_merged
- Silt (0-5cm): silt_0_5cm_merged
- pH (0-5cm): ph_0_5cm_merged
- Organic Carbon Density (0-5cm): ocd_0_5cm_merged
```

**Sampling Endpoint**: `/sample` (POST request with lat/lon)
**Response Format**: JSON with variable:value pairs
**Integration Point**: Called by frontend when user clicks map for habitat prediction

### 5.2 Recommended Variable Additions

**Priority 1 - High Impact, Readily Available**:

From **SoilGrids250m v2.0** (already partially used via AlphaEarth):
1. **Cation Exchange Capacity** (`cec_mean`, 0-5cm layer)
   - Impact: 54.5% of species associations defined by chemical properties
   - Implementation: Add to AlphaEarth extraction or sample directly from SoilGrids GEE
2. **Nitrogen** (`nitrogen_mean`, 0-5cm layer)
   - Impact: Primary limiting nutrient in many ecosystems
   - Implementation: Same as CEC
3. **Bulk Density** (`bdod_mean`, 0-5cm layer)
   - Impact: Affects root penetration and water infiltration
   - Implementation: Same as CEC

From **HiHydroSoil v2.0**:
4. **Available Water Capacity** (`wcavail`)
   - Impact: Critical for drought tolerance prediction
   - Implementation: Sample from HiHydroSoil GEE collection
5. **Saturated Hydraulic Conductivity** (`ksat`)
   - Impact: Indicates drainage class, waterlogging risk
   - Implementation: Same as AWC

**Priority 2 - Moderate Impact, More Complex**:

6. **Soil Depth** (from HWSD v2.0)
   - Impact: Limits rooting depth and tree height
   - Implementation: Sample from HWSD GEE collection (coarser 1km resolution)
7. **Coarse Fragments** (`cfvo_mean` from SoilGrids)
   - Impact: Affects water holding capacity and excavation difficulty
   - Implementation: Add to SoilGrids sampling

8. **Derived K-factor** (Erodibility)
   - Impact: Restoration planning for erosion-prone sites
   - Implementation: Calculate from existing + new variables post-sampling

**Priority 3 - Lower Priority or Data Gaps**:

9. **Deeper Soil Layers** (15-30cm, 30-60cm)
   - Impact: Relevant for deep-rooted species
   - Implementation: Sample additional depth bands from SoilGrids
10. **Phosphorus and Potassium**
    - Impact: High, but **not available globally**
    - Implementation: Future opportunity if data becomes available

### 5.3 Implementation Strategy

**Option A: Extend AlphaEarth Sampling (Recommended)**

Modify the existing AlphaEarth GEE extraction to include additional variables:

```python
# Pseudocode for extended sampling
def sample_enhanced_soil(lat, lon):
    # Existing AlphaEarth variables
    alphaearth_vars = ['clay_0_5cm', 'sand_0_5cm', 'silt_0_5cm', 'ph_0_5cm', 'ocd_0_5cm']

    # Additional SoilGrids variables
    soilgrids_vars = {
        'cec_0-5cm_mean': 'projects/soilgrids-isric/cec_0-5cm_mean',
        'nitrogen_0-5cm_mean': 'projects/soilgrids-isric/nitrogen_0-5cm_mean',
        'bdod_0-5cm_mean': 'projects/soilgrids-isric/bdod_0-5cm_mean',
        'cfvo_0-5cm_mean': 'projects/soilgrids-isric/cfvo_0-5cm_mean'
    }

    # HiHydroSoil variables
    hihydro_vars = {
        'awc': 'projects/hihydrosoil/wcavail',
        'ksat': 'projects/hihydrosoil/ksat'
    }

    # Sample all at point
    results = {}
    results.update(sample_alphaearth(lat, lon, alphaearth_vars))
    results.update(sample_soilgrids(lat, lon, soilgrids_vars))
    results.update(sample_hihydrosoil(lat, lon, hihydro_vars))

    return results
```

**Advantages**:
- Minimal frontend changes
- Centralized sampling logic
- Consistent with existing architecture

**Disadvantages**:
- Increases sampling latency (more GEE calls)
- AlphaEarth COG availability unclear for new variables

**Option B: Direct GEE Sampling (Alternative)**

Sample SoilGrids and HiHydroSoil directly from GEE, bypassing AlphaEarth for new variables:

```python
import ee

def sample_soilgrids_gee(lat, lon, depth='0-5cm'):
    point = ee.Geometry.Point([lon, lat])

    # SoilGrids ImageCollection
    soilgrids = ee.Image('projects/soilgrids-isric/soilgrids250m_v2_0')

    # Select bands for depth layer
    cec = soilgrids.select(f'cec_{depth}_mean')
    nitrogen = soilgrids.select(f'nitrogen_{depth}_mean')
    bdod = soilgrids.select(f'bdod_{depth}_mean')

    # Sample at point
    sample = cec.addBands([nitrogen, bdod]).sample(point, 250)

    return sample.first().getInfo()['properties']
```

**Advantages**:
- Direct access to latest SoilGrids data
- No dependency on AlphaEarth COG availability
- Easier to add new variables

**Disadvantages**:
- Requires Earth Engine initialization (service account or user auth)
- Different data source pathway than existing texture variables

**Recommendation**: **Option A** (extend AlphaEarth) if AlphaEarth COGs include the additional SoilGrids variables. Otherwise, **Option B** (direct GEE) for new variables while keeping existing AlphaEarth sampling for texture/pH.

### 5.4 Database Schema Updates

**Add Columns to `species_alphaearth_centroids` Table** (or create new table):

```sql
-- Option 1: Extend existing table
ALTER TABLE species_alphaearth_centroids ADD COLUMN IF NOT EXISTS
    cec_0_5cm NUMERIC,           -- cmol(+)/kg
    nitrogen_0_5cm NUMERIC,       -- g/kg
    bulk_density_0_5cm NUMERIC,   -- g/cm³
    coarse_fragments_0_5cm NUMERIC, -- % volume
    awc NUMERIC,                  -- cm³/cm³
    ksat NUMERIC,                 -- cm/day
    erodibility_k NUMERIC;        -- USLE K-factor (derived)

-- Option 2: Create new enhanced soil table
CREATE TABLE IF NOT EXISTS species_soil_properties (
    taxon_id TEXT PRIMARY KEY REFERENCES species(taxon_id),
    centroid_lat NUMERIC,
    centroid_lon NUMERIC,

    -- Texture (existing from AlphaEarth)
    clay_0_5cm NUMERIC,
    sand_0_5cm NUMERIC,
    silt_0_5cm NUMERIC,

    -- Chemical properties
    ph_0_5cm NUMERIC,
    cec_0_5cm NUMERIC,
    nitrogen_0_5cm NUMERIC,
    organic_carbon_density_0_5cm NUMERIC,

    -- Physical properties
    bulk_density_0_5cm NUMERIC,
    coarse_fragments_0_5cm NUMERIC,

    -- Hydraulic properties
    awc NUMERIC,
    ksat NUMERIC,
    water_content_33kpa NUMERIC,  -- Field capacity
    water_content_1500kpa NUMERIC, -- Wilting point

    -- Derived properties
    erodibility_k NUMERIC,

    -- Metadata
    sampled_at TIMESTAMP DEFAULT NOW(),
    data_source TEXT
);
```

### 5.5 API Endpoint Updates

**Extend `/sample` Endpoint** (location_predictor_FIXED.py):

```python
@app.route('/sample', methods=['POST'])
def sample_location():
    data = request.json
    lat = data.get('lat')
    lon = data.get('lon')

    # Sample enhanced soil properties
    soil_data = sample_enhanced_soil(lat, lon)

    # Calculate derived properties
    soil_data['erodibility_k'] = calculate_k_factor(
        sand=soil_data['sand_0_5cm'],
        silt=soil_data['silt_0_5cm'],
        clay=soil_data['clay_0_5cm'],
        organic_carbon=soil_data['ocd_0_5cm'],
        ksat=soil_data.get('ksat')
    )

    soil_data['awc'] = (
        soil_data.get('water_content_33kpa', 0) -
        soil_data.get('water_content_1500kpa', 0)
    )

    # Existing species prediction logic
    predicted_species = predict_species(lat, lon, soil_data)

    return jsonify({
        'soil': soil_data,
        'predicted_species': predicted_species
    })
```

**New Endpoint for Bulk Species Soil Enrichment**:

```python
@app.route('/enrich-species-soil', methods=['POST'])
def enrich_species_soil():
    """
    Batch process to sample soil properties for all species centroids
    and populate species_soil_properties table.
    """
    species_centroids = get_species_centroids()  # From DB

    results = []
    for species in species_centroids:
        try:
            soil_data = sample_enhanced_soil(
                species['centroid_lat'],
                species['centroid_lon']
            )

            # Insert into database
            insert_species_soil_properties(species['taxon_id'], soil_data)
            results.append({'taxon_id': species['taxon_id'], 'status': 'success'})

        except Exception as e:
            results.append({'taxon_id': species['taxon_id'], 'status': 'error', 'message': str(e)})

    return jsonify(results)
```

### 5.6 Frontend Integration

**Update Species Detail Page** (`frontend/app/species/[taxon_id]/page.tsx`):

Display additional soil properties in the **Ecological Tab**:

```tsx
// Add to EcologicalTab.tsx
<DataField
  label="Soil Preferences"
  value={species.soil_preferences || 'Not available'}
  source={species.soil_preferences_source}
/>

<DataField
  label="Cation Exchange Capacity"
  value={species.cec_0_5cm ? `${species.cec_0_5cm} cmol(+)/kg` : 'Not available'}
  tooltip="Soil's ability to hold and exchange nutrients"
/>

<DataField
  label="Available Water Capacity"
  value={species.awc ? `${species.awc} cm³/cm³` : 'Not available'}
  tooltip="Water available to plants between field capacity and wilting point"
/>

<DataField
  label="Soil Nitrogen"
  value={species.nitrogen_0_5cm ? `${species.nitrogen_0_5cm} g/kg` : 'Not available'}
  tooltip="Total nitrogen content in topsoil"
/>
```

**Update Habitat Prediction Map** (map click feature):

```tsx
// When user clicks map, display enhanced soil data
const handleMapClick = async (lat: number, lon: number) => {
  const response = await fetch('/sample', {
    method: 'POST',
    body: JSON.stringify({ lat, lon })
  });

  const data = await response.json();

  // Display soil properties in popup
  return (
    <Popup>
      <h3>Soil Properties</h3>
      <p>Texture: {data.soil.sand_0_5cm}% sand, {data.soil.clay_0_5cm}% clay</p>
      <p>pH: {data.soil.ph_0_5cm}</p>
      <p>CEC: {data.soil.cec_0_5cm} cmol(+)/kg</p>
      <p>AWC: {data.soil.awc} cm³/cm³</p>
      <p>Drainage: {data.soil.ksat > 10 ? 'Well-drained' : 'Poorly-drained'}</p>

      <h3>Predicted Species</h3>
      <ul>
        {data.predicted_species.map(sp => <li>{sp.name}</li>)}
      </ul>
    </Popup>
  );
};
```

### 5.7 Implementation Timeline

**Phase 1: Backend Soil Data Collection (Week 1-2)**
- [ ] Implement GEE sampling functions for SoilGrids and HiHydroSoil
- [ ] Create database schema for enhanced soil properties
- [ ] Develop bulk enrichment script for existing 500 species centroids
- [ ] Test sampling accuracy against known values

**Phase 2: API Integration (Week 2-3)**
- [ ] Extend `/sample` endpoint with new variables
- [ ] Add K-factor and AWC calculation functions
- [ ] Create batch enrichment endpoint (`/enrich-species-soil`)
- [ ] Update API documentation

**Phase 3: Frontend Display (Week 3-4)**
- [ ] Update Ecological Tab to show new soil properties
- [ ] Enhance map click popup with enriched data
- [ ] Add tooltips explaining soil variables
- [ ] Test user experience

**Phase 4: Validation and Optimization (Week 4-5)**
- [ ] Validate soil data against field measurements (if available)
- [ ] Optimize GEE sampling for latency
- [ ] Cache commonly sampled locations
- [ ] Monitor database performance

---

## 6. Ecological Interpretation Guide

### 6.1 Using Soil Variables for Species Prediction

**Decision Tree for Tree Species Suitability**:

```
1. Water Availability Assessment
   - AWC > 0.15 cm³/cm³ → Mesic species viable
   - AWC < 0.10 cm³/cm³ → Xerophytic species only

2. Drainage Class (from Ksat)
   - Ksat > 100 cm/day → Well-drained (pines, oaks)
   - Ksat 10-100 cm/day → Moderately drained (maples, beeches)
   - Ksat < 10 cm/day → Poorly drained (willows, alders, bald cypress)

3. Nutrient Status (from CEC + N)
   - CEC > 15 cmol(+)/kg, N > 2 g/kg → Nutrient-rich (fast-growing species)
   - CEC < 10 cmol(+)/kg, N < 1 g/kg → Nutrient-poor (slow-growing, adapted species)

4. Rooting Constraints
   - Bulk density > 1.6 g/cm³ → Shallow-rooted species only
   - Coarse fragments > 50% → Species tolerant of rocky soils
   - Depth to bedrock < 50 cm → Restricted species palette

5. Erosion Risk (K-factor)
   - K > 0.4 → High erosion risk (prioritize erosion-control species)
   - K < 0.2 → Low erosion risk (broader species options)
```

### 6.2 Restoration Planning Applications

**Site Assessment Workflow**:

1. **Sample soil properties** at restoration site using `/sample` endpoint
2. **Classify site conditions**:
   - Drainage: Well-drained / Moderately drained / Poorly drained
   - Fertility: High / Medium / Low (based on CEC + N)
   - Water stress risk: High / Medium / Low (based on AWC)
   - Erosion risk: High / Medium / Low (based on K-factor)
3. **Filter species database** for matching tolerances
4. **Rank species** by suitability score incorporating all soil variables
5. **Generate species recommendation list** with confidence scores

**Example Species Matching Logic**:

```python
def calculate_soil_suitability(species_tolerances, site_soil):
    """
    Score species suitability (0-100) based on soil match.
    """
    score = 100

    # Drainage match
    if site_soil['ksat'] > 100 and species_tolerances['drainage'] == 'poor':
        score -= 40  # Major mismatch
    elif site_soil['ksat'] < 10 and species_tolerances['drainage'] == 'well':
        score -= 40

    # Fertility match
    if site_soil['cec'] < 10 and species_tolerances['fertility'] == 'high':
        score -= 30

    # Water availability match
    if site_soil['awc'] < 0.10 and species_tolerances['drought_tolerance'] == 'low':
        score -= 35

    # Soil depth match (if available)
    if site_soil.get('depth_to_bedrock', 200) < 50 and species_tolerances['rooting_depth'] == 'deep':
        score -= 25

    return max(score, 0)
```

### 6.3 Cross-Species Analysis Applications

**Potential Analyses Enabled by Enhanced Soil Data**:

1. **Niche Overlap Analysis**:
   - Compare soil preferences of competing species
   - Identify species pairs with distinct niches for mixed plantings

2. **Climate Change Vulnerability**:
   - Species with low AWC tolerance + declining precipitation = high vulnerability
   - Prioritize species with wide soil tolerance ranges

3. **Functional Trait Mapping**:
   - Correlate leaf traits, wood density with soil CEC, N, AWC
   - Understand trait-environment relationships

4. **Biogeographic Pattern Explanation**:
   - Why is species X absent from region Y despite climate match?
   - Soil constraints (e.g., low pH, high bulk density) may explain

---

## 7. Research Gaps and Future Opportunities

### 7.1 Critical Data Gaps

**Phosphorus and Potassium**:
- **Impact**: Major macronutrients, but not mapped globally
- **Workaround**: Use parent material geology as proxy (limited accuracy)
- **Future**: National datasets (e.g., US SSURGO) could fill regional gaps

**Soil Depth to Bedrock**:
- **Impact**: Limits rooting depth and tree height
- **Current**: Only in HWSD (coarse 1km) and POLARIS (US only)
- **Future**: High-resolution global depth maps (active research area)

**Drainage Class**:
- **Impact**: Categorical drainage classes widely used in forestry
- **Current**: Must be derived from Ksat (continuous) or use coarse HWSD
- **Future**: Machine learning to classify drainage from multiple variables

**Micronutrients** (Fe, Mn, Zn, B, Cu, Mo):
- **Impact**: Deficiencies limit species on certain soils
- **Current**: Not mapped globally
- **Future**: Low priority due to data scarcity

### 7.2 Advanced Modeling Opportunities

**Pedotransfer Functions**:
- Derive additional properties (e.g., unsaturated conductivity, aggregate stability) from basic variables
- Reduces need for direct measurement

**Soil-Climate Interactions**:
- Combine soil AWC with precipitation → actual water stress
- Soil thermal properties + temperature → frost depth

**Mycorrhizal Associations**:
- Some soil properties (pH, P availability) correlate with mycorrhizal type
- Could infer ectomycorrhizal vs. arbuscular associations

**Soil Erosion Modeling**:
- Use K-factor + slope + precipitation → erosion rate
- Prioritize erosion-control species for high-risk sites

### 7.3 Validation and Uncertainty

**Current Limitations**:
- SoilGrids predictions have higher uncertainty in data-sparse regions (e.g., tropics, remote areas)
- Validation against field data is limited for most global datasets

**Recommendations**:
1. **Display uncertainty**: Show confidence intervals for soil predictions (available in SoilGrids)
2. **Field validation**: Partner with forestry organizations to validate predictions at field sites
3. **User feedback**: Allow users to report discrepancies (crowdsourced validation)

---

## 8. Conclusion and Recommendations

### 8.1 Summary

Advanced soil variables significantly enhance species distribution modeling and restoration planning beyond basic texture and pH. The most impactful additions for Treekipedia are:

1. **Cation Exchange Capacity (CEC)**: Nutrient retention and fertility indicator
2. **Available Water Capacity (AWC)**: Drought tolerance prediction
3. **Saturated Hydraulic Conductivity (Ksat)**: Drainage class and waterlogging risk
4. **Nitrogen**: Nutrient availability and growth potential
5. **Bulk Density**: Rooting difficulty and soil compaction

These variables are globally available at 250m resolution through SoilGrids250m v2.0 and HiHydroSoil v2.0, both accessible via Google Earth Engine.

### 8.2 Immediate Action Items

**High Priority** (Implement in next development cycle):
1. Sample CEC, N, bulk density from SoilGrids for all 500 species centroids
2. Sample AWC and Ksat from HiHydroSoil for all 500 species centroids
3. Add soil properties to species database schema
4. Display CEC, AWC, Ksat in Species Detail page (Ecological Tab)
5. Update map click `/sample` endpoint to include new variables

**Medium Priority** (Next quarter):
1. Calculate derived K-factor (erodibility) for all species
2. Implement species-soil suitability scoring function
3. Add soil-based filtering to species search/recommendation
4. Develop restoration planning tool using soil constraints

**Low Priority** (Future iterations):
1. Add deeper soil layers (15-30cm, 30-60cm) for deep-rooted species
2. Integrate HWSD drainage class and soil depth (where SoilGrids lacks)
3. Explore POLARIS for US-specific high-resolution enhancements
4. Develop uncertainty visualization for soil predictions

### 8.3 Expected Impact

**For Users**:
- More accurate habitat suitability predictions
- Better-informed restoration site assessments
- Understanding of why species succeed/fail on different soils

**For Treekipedia Platform**:
- Differentiation from other species databases (unique soil integration)
- Enables advanced analyses (niche modeling, climate vulnerability)
- Foundation for predictive restoration planning tools

**For Ecological Restoration**:
- Reduced planting failures due to soil mismatches
- Data-driven species selection for challenging sites (eroded, compacted, nutrient-poor)
- Quantifiable soil-species relationships for adaptive management

---

## Sources

### Soil Physical Properties and Erodibility
- [Advanced global soil erodibility assessment - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0048969723068766)
- [RUSLE K-factor assessment tool - MSU](http://www.iwr.msu.edu/rusle/kfactor.htm)
- [Optimal mapping of soil erodibility factor - Earth Systems and Environment](https://link.springer.com/article/10.1007/s41748-024-00553-3)
- [Global soil erodibility factor mapping - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0341816224001413)

### SoilGrids and Global Soil Databases
- [SoilGrids - Global gridded soil information - ISRIC](https://isric.org/explore/soilgrids)
- [SoilGrids Documentation - ISRIC](https://docs.isric.org/globaldata/soilgrids/)
- [Datasets tagged soil in Earth Engine - Google for Developers](https://developers.google.com/earth-engine/datasets/tags/soil)
- [SoilGrids with Google Earth Engine - Romero Stories](https://www.romerostories.com/post/soilgrids-with-google-earth-engine)
- [SoilGrids250m 2.0 Volumetric Water Content - GEE Data Catalog](https://developers.google.com/earth-engine/datasets/catalog/ISRIC_SoilGrids250m_v2_0)
- [Soil Grids 250m v2.0 - GEE Community Catalog](https://gee-community-catalog.org/projects/isric/)

### Soil Chemical Properties and CEC
- [Tree species affect CEC - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0048969715000169)
- [Soil-available nutrients following restoration - MDPI Forests](https://www.mdpi.com/1999-4907/14/2/259)
- [Soil enzyme activity and nutrients in post-fire habitat models - MDPI](https://www.mdpi.com/2571-6255/3/4/54)
- [Effects of tree species on reforested post-mining soils - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0016706117300241)

### Soil Hydraulic Properties
- [Soil hydrologic properties - Minnesota Stormwater Manual](https://stormwater.pca.state.mn.us/soil_hydrologic_properties_and_processes)
- [SoilKsatDB: global database of saturated hydraulic conductivity - ESSD](https://essd.copernicus.org/articles/13/1593/2021/)
- [Soil water retention and hydraulic conductivity measurements - ESSD](https://essd.copernicus.org/articles/15/4417/2023/)
- [HiHydroSoil v2.0 on Google Earth Engine - FutureWater](https://www.futurewater.eu/2021/06/hihydrosoil-v2-0-now-available-on-google-earth-engine/)
- [HiHydroSoil v2.0 layers - GEE Community Catalog](https://gee-community-catalog.org/projects/hihydro_soil/)
- [HiHydroSoil v2.0: Global Maps - FutureWater](https://www.futurewater.eu/projects/hihydrosoil/)

### Global Soil Database Comparisons
- [World Soil Geographic Databases - ISRIC](https://docs.isric.org/soil-geographic-databases/sections/soil-geographic-databases-world.html)
- [Open compendium of global soil samples - OpenLandMap](https://soildb.openlandmap.org/index.html)
- [Polaris 30m Probabilistic Soil Properties - GEE Community Catalog](https://gee-community-catalog.org/projects/polaris/)
- [Harmonized World Soil Database v2.0 - GEE Community Catalog](https://gee-community-catalog.org/projects/hwsd/)
- [Harmonized World Soil Database - IIASA](https://iiasa.ac.at/models-tools-data/hwsd)
- [Compendium of Global Gridded Environmental Data - OpenLandMap](https://openlandmap.github.io/book/012-compendium.html)

---

**Document Version**: 1.0
**Next Review**: March 2026 (post-implementation evaluation)
**Maintained By**: Treekipedia Development Team
