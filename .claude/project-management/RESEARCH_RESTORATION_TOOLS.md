# Environmental Variables in Leading Restoration Tools and Platforms

**Research Date**: January 21, 2026
**Researcher**: Research Agent
**Purpose**: Identify environmental variables and methodologies used by major restoration platforms for species selection

---

## Executive Summary

This research examines five leading restoration tools and platforms to understand their approaches to species selection based on environmental variables. Key findings:

- **Common Core Variables**: Climate (temperature, precipitation), soil properties (pH, texture, carbon), elevation, and ecoregion classification appear across all platforms
- **Advanced Variables**: D4R and Restor lead with climate change projections, species traits integration, and seed zone mapping
- **Data Sources**: Heavy reliance on PRISM climate data, SSURGO soil surveys, Google Earth Engine, and FIA plot networks
- **Gaps Identified**: Limited integration of biotic interactions, hydrological dynamics, disturbance regimes, and fine-scale microclimate variation

---

## 1. Diversity for Restoration (D4R) Tool

**Developer**: Alliance of Bioversity International and CIAT
**Website**: www.diversityforrestoration.org
**Geographic Focus**: Originally tropical dry forests (Colombia), expanded to Peru-Ecuador, Burkina Faso, Cameroon, Ethiopia, Thailand, Malaysia, India

### Core Methodology

D4R is the most sophisticated tool reviewed, designed to enable **non-expert users** to combine species traits, environmental data, and climate change models for climate-resilient restoration planning. The tool provides guidance on both species selection AND seed source selection.

### Environmental Variables

**Climate Variables**:
- Current climate conditions (temperature, precipitation patterns)
- **Climate change projections** (future scenarios integrated into recommendations)
- Climate variability metrics

**Soil Variables**:
- Soil type and texture
- Soil chemical properties (pH, nutrients)
- Soil carbon content

**Geographic Variables**:
- Elevation
- Latitude and longitude (for seed zone delineation)
- Geographic distance constraints (avoiding large distances within seed zones)

### Unique Features

1. **Seed Zone Mapping**: Constructs "environmentally homogeneous seed zones" by clustering climate and soil variables along with longitude and latitude to ensure genetic appropriateness
2. **Species Traits Integration**: Incorporates functional traits and propagation requirements for hundreds of tree species
3. **Climate-Smart Selection**: Explicitly accounts for future climate conditions, not just current conditions
4. **Restoration Objectives**: Allows users to specify context-specific objectives (e.g., biodiversity conservation, specific wildlife habitat)

### Data Integration Approach

The tool uses models that consider a **wide range of climate and soil variables** simultaneously, then applies clustering algorithms to create recommendations. It also includes a propagation database with information on how to grow selected species from seed or cuttings.

### Strengths
- Climate change integration as core feature
- Seed provenance guidance (critical for restoration success)
- User-friendly for non-experts
- Context-specific restoration objectives

### Limitations
- Currently limited to tropical and select temperate regions
- Expansion to new regions requires significant data assembly
- Focused primarily on trees (limited understory/herbaceous guidance)

---

## 2. USFS Forest Inventory and Analysis (FIA)

**Agency**: US Forest Service
**Website**: www.fia.fs.fed.us
**Geographic Focus**: United States (all forest lands)

### Core Methodology

FIA is not a species selection tool per se, but rather the **foundational data infrastructure** that enables species-environment modeling across the US. The program conducts systematic plot-based sampling on permanent plots measured every 5-10 years.

### Environmental Variables Collected

**Plot-Level Measurements**:
- Forest type classification
- Site attributes:
  - Ownership class
  - Terrain characteristics (slope, aspect, position)
  - Landform
- Tree species composition and abundance
- Tree size (diameter, height)
- Tree condition and health

**Extended Measurements** (subset of plots):
- **Understory vegetation** (species composition and cover)
- **Down woody material** (coarse woody debris, fuel loads)
- **Soil properties**:
  - Soil samples sent to laboratory for chemical analysis
  - Soil horizons and texture
  - Organic matter content

**Linked Geospatial Data**:
- National Elevation Dataset (DEM derivatives)
- SSURGO soils data (mapped soil series and properties)
- PRISM climate data (temperature, precipitation)
- Texture metrics and landscape pattern indices

### Applications for Species-Environment Modeling

Researchers use FIA data to:
- Study **species distributions** across environmental gradients
- Identify **key biophysical drivers** of community composition at multiple spatial scales
- Build **species distribution models** and habitat suitability maps
- Understand **climate-related variables** associated with species occurrence

### Analytical Techniques

**Gradient Nearest Neighbor (GNN)**: Uses FIA plot data combined with auxiliary geospatial datasets (elevation, soils, texture) to assign environmental characteristics to landscape pixels, enabling wall-to-wall species distribution mapping.

### Strengths
- Extensive spatial coverage (national scale)
- Long-term temporal records (decades of remeasurement)
- Standardized methodology ensuring data consistency
- Publicly available data enabling research and tool development

### Limitations
- Plot-based sampling (not continuous spatial data)
- Limited fine-scale environmental measurements (microclimate, hydrology)
- 5-10 year remeasurement interval (lags in detecting rapid changes)
- Primarily designed for inventory, not restoration planning

---

## 3. The Nature Conservancy Restoration Tools

**Organization**: The Nature Conservancy
**Website**: www.nature.org/data-and-tools
**Geographic Focus**: Global, with region-specific tools

### Core Tools and Approaches

TNC has developed multiple tools for restoration planning, including:
- **Cost-Feasibility Mapping Tool**: Identifies lower-cost, more feasible forest restoration locations in the US
- **Resilient Lands Mapping Tool**: Identifies climate-resilient places and migration pathways for species
- Integration with third-party modeling tools (Maxent, DesktopGARP)

### Environmental Variables Used

**Climate Variables**:
- Current climate conditions
- **Future climate projections** (vulnerability assessment)
- Climate resilience indicators

**Species-Specific Variables**:
- Known occurrence records (for species distribution modeling)
- Ecological niche parameters
- **Climate resilience traits** (species suited to present or future conditions)

**Site Characteristics**:
- Local environmental conditions (soil, moisture, temperature)
- Vulnerability to climate impacts (for siting decisions)
- Cost and feasibility factors (accessibility, land ownership, restoration costs)

### Modeling Approaches

**Maxent (Maximum Entropy Modeling)**:
- Predicts species' potential distributions by combining **known occurrence records** with **digital layers of environmental variables**
- Variables include climate (temperature, precipitation), soil properties, elevation, aspect
- Outputs probability surfaces showing habitat suitability

**DesktopGARP (Genetic Algorithm for Rule-set Prediction)**:
- Creates an **ecological niche model** representing environmental conditions where species can maintain populations
- Uses environmental variables to define the "realized niche"

### Best Practices for Species Selection

1. **Native species** suited to local environmental conditions
2. **Genetic diversity**: Seeds/cuttings collected from variety of sources within local region
3. **Climate adaptation**: Selection of species more resilient to climate change
4. **Context-specific goals**: Consideration of what species will be best suited to present or future climate conditions

### Strengths
- Climate change adaptation as explicit consideration
- Integration of cost-feasibility with ecological suitability
- Use of established species distribution modeling frameworks
- Emphasis on genetic diversity and local adaptation

### Limitations
- Tools appear to be primarily mapping/planning focused rather than species recommendation engines
- Less detailed information on specific environmental variable thresholds
- Not a single integrated platform (multiple separate tools)

---

## 4. Restor Platform

**Developer**: Crowther Lab (ETH Zurich) with 200+ science collaborators
**Website**: restor.eco
**Geographic Focus**: Global terrestrial ecosystems

### Core Methodology

Restor is described as a **"Google Maps for restoration"**, built on Google Earth Engine. It provides instant ecological analysis for any terrestrial location by integrating massive geospatial datasets.

### Environmental Variables Provided

When a user outlines an area on Restor, the platform displays:

**Biodiversity Variables**:
- Number of species occurring in the region
- **Species lists** (which flora could exist in the area)
- Current tree cover
- **Potential tree cover** (ecological potential)

**Soil Variables**:
- Soil pH
- Current soil carbon
- **Potential soil carbon** (sequestration potential)

**Climate Variables**:
- Annual rainfall
- Temperature patterns (inferred from location)

**Land Cover Variables**:
- Current land cover classification
- Vegetation structure
- Forest structure metrics

### Data Processing Architecture

- **23 different insights** generated instantly from polygon analysis
- Multi-petabyte catalog of satellite imagery and geospatial datasets
- Google Earth Engine processing infrastructure
- Continuous updates as new research is published

### Species Matching Approach

The platform provides information on which **native species would thrive** in particular environmental conditions based on:
- Local biodiversity databases
- Reference ecosystem analysis (nearby sites with similar conditions)
- Ecological potential modeling

### Strengths
- Instant access to comprehensive environmental data for any location
- User-friendly interface requiring no technical expertise
- Integration of current AND potential ecosystem states
- Global coverage (not region-limited)
- Continuously updated with latest research
- Connection to global restoration network (learning from similar sites)

### Limitations
- Appears to provide species lists rather than ranked recommendations
- Limited information on specific environmental variable thresholds used
- May lack fine-scale local variation (depends on underlying dataset resolution)
- More focused on general ecological potential than site-specific species-environment matching

---

## 5. NRCS Plant Materials and Ecoregion Matching

**Agency**: Natural Resources Conservation Service (USDA)
**Website**: www.nrcs.usda.gov/plantmaterials
**Geographic Focus**: United States

### Core Methodology

NRCS uses an **ecoregional approach** to plant materials selection, based on the concept that areas with similar environmental characteristics should support similar plant communities.

### Environmental Classification Framework

**Major Land Resource Areas (MLRAs)**:
- Earliest ecoregional classification system (developed early 1970s)
- Defines areas with generally similar:
  - Landforms
  - Soils
  - Hydrologic resources
  - Plant communities
  - Animal communities

### Environmental Variables for Matching

**Climate Data**:
- Temperature (derived from **PRISM Climate Group** databases)
- Precipitation patterns
- Growing season length
- Frost-free days
- **Direct, automatic links to PRISM databases** for site-specific data

**Soil Characteristics** (via SSURGO Soil Survey data):
- Soil series and classification
- Soil texture and structure
- Soil chemical properties (pH, nutrients, salinity)
- Drainage class
- Depth to restrictive layer
- **Critical matching criterion** for plant selection

**Site Characteristics**:
- Elevation
- Slope and aspect
- Hydrologic regime (wetland vs. upland)
- Disturbance history

### Ecological Site Descriptions (ESDs)

The NRCS Ecological Site Description system differentiates sites based on:
- **Significant differences in species or species groups** in characteristic plant community
- **Relative proportion of species or species groups**
- Soil-vegetation-climate relationships
- Ecological dynamics and state-and-transition models

### Plant Selection Criteria

Species selection considers:
1. **Ecoregion match**: Site falls within species' natural range/ecoregion
2. **Climate match**: Local climate parameters within species tolerance
3. **Soil match**: Soil properties compatible with species requirements
4. **Resistance to local pests**: Species adapted to local biotic pressures
5. **Intended use**: Conservation, erosion control, wildlife habitat, forage production

### Data Integration Tools

**FHWA Ecoregional Revegetation Application (ERA)**:
- Integrates climate and soil data automatically for revegetation sites
- Links to PRISM Climate Group databases
- Links to NRCS SSURGO Soil Survey data
- Provides site-specific environmental parameters

### Strengths
- Long-established ecoregional framework (50+ years development)
- Robust integration of climate and soil data via automated linkages
- Emphasis on local adaptation and genetic appropriateness
- Practical focus on propagation and availability (Plant Materials Centers)
- Considers intended use and functional requirements

### Limitations
- US-specific (not applicable internationally)
- Ecoregions may be too coarse for fine-scale site variability
- Limited explicit climate change consideration
- Focus on herbaceous and shrub species (less comprehensive tree databases)

---

## Cross-Platform Analysis

### Common Environmental Variables

All five platforms/tools use these core variables:

1. **Climate**:
   - Temperature (annual, seasonal, extremes)
   - Precipitation (annual, seasonal patterns)
   - Derived variables (growing degree days, aridity index)

2. **Soil**:
   - Soil pH
   - Soil texture (sand, silt, clay fractions)
   - Soil carbon/organic matter

3. **Topography**:
   - Elevation
   - Slope (some platforms)
   - Aspect (some platforms)

4. **Geography**:
   - Latitude/longitude
   - Ecoregion or biogeographic classification

### Advanced Variables (Used by Some Platforms)

**Climate Change Projections**:
- **D4R**: Core feature, integrates future climate scenarios
- **TNC**: Used in Resilient Lands tool and species resilience assessment
- **Restor**: Unclear if climate projections integrated
- **FIA, NRCS**: Not explicitly included

**Species Traits**:
- **D4R**: Functional traits and propagation requirements
- **TNC**: Climate resilience traits
- **Others**: Limited explicit trait integration

**Genetic/Seed Provenance**:
- **D4R**: Seed zone mapping based on environmental clustering + geographic distance
- **NRCS**: Emphasis on local seed sources within ecoregions
- **TNC**: Genetic diversity from variety of local sources
- **FIA, Restor**: Not addressed

**Biotic Variables**:
- **FIA**: Understory vegetation, down woody material (limited plots)
- **NRCS**: Resistance to local pests
- **Others**: Generally absent

### Data Source Commonalities

**Climate Data**:
- **PRISM Climate Group** (used by NRCS, likely FIA applications)
- Google Earth Engine climate layers (Restor)
- Regional climate datasets (D4R)

**Soil Data**:
- **SSURGO** soil surveys (NRCS, FIA applications)
- Google Earth Engine soil layers (Restor)
- Regional soil datasets (D4R)

**Elevation Data**:
- National Elevation Dataset (FIA)
- Google Earth Engine SRTM/ASTER (Restor)
- Regional DEMs (D4R)

---

## Gaps in Current Approaches

Despite the sophistication of these tools, several important environmental variables are underrepresented:

### 1. Hydrological Dynamics
- **Missing**: Soil moisture regimes, water table depth, seasonal flooding patterns, drought frequency
- **Why Important**: Critical for species establishment and survival, especially in riparian and wetland restoration
- **Current Coverage**: Only coarse indicators like "wetland vs. upland" or drainage class

### 2. Microclimate Variation
- **Missing**: Fine-scale temperature and humidity variation, cold air pooling, fog frequency, heat island effects
- **Why Important**: Can determine success/failure at individual site level
- **Current Coverage**: Regional climate averages mask local variation

### 3. Disturbance Regimes
- **Missing**: Fire frequency and intensity, windthrow patterns, insect outbreak history, herbivory pressure
- **Why Important**: Species adaptations to disturbance strongly influence restoration trajectories
- **Current Coverage**: Historical disturbance rarely incorporated

### 4. Biotic Interactions
- **Missing**: Mycorrhizal associations, pollinator availability, disperser presence, competitive interactions, herbivore populations
- **Why Important**: Species success depends on mutualists and is limited by antagonists
- **Current Coverage**: Essentially absent (except NRCS "pest resistance")

### 5. Soil Microbiology
- **Missing**: Soil microbial communities, mycorrhizal diversity, soil pathogens, nitrogen-fixing bacteria
- **Why Important**: Particularly critical for nitrogen-fixing species and species with obligate mycorrhizal requirements
- **Current Coverage**: Not measured in any platform reviewed

### 6. Air Quality and Pollution
- **Missing**: Ozone tolerance, salt spray (coastal), heavy metal tolerance, urban pollution stress
- **Why Important**: Critical for urban and roadside restoration, and near agricultural areas
- **Current Coverage**: Not addressed

### 7. Temporal Variability
- **Missing**: Inter-annual climate variability, extreme event frequency, phenological timing
- **Why Important**: Species differ in tolerance to variability vs. mean conditions
- **Current Coverage**: Mostly mean annual or seasonal values

### 8. Successional Dynamics
- **Missing**: Time-since-disturbance, current vegetation structure, shade tolerance requirements, facilitation needs
- **Why Important**: Early vs. late successional species have very different establishment requirements
- **Current Coverage**: Limited (Restor shows current vs. potential states)

---

## Implications for Treekipedia Species Aptness Score

Based on this research, a comprehensive species aptness scoring system should consider:

### Tier 1: Essential Variables (Present in Most Tools)
- Climate: Temperature and precipitation patterns
- Soil: pH, texture, organic matter
- Topography: Elevation, slope, aspect
- Geography: Ecoregion, latitude/longitude

### Tier 2: Advanced Variables (Present in Leading Tools)
- Climate change projections (future suitability)
- Species functional traits (growth form, drought tolerance, shade tolerance)
- Seed zone/genetic provenance matching
- Current vs. potential ecosystem state

### Tier 3: Gap-Filling Variables (Competitive Advantage)
- Soil moisture regime (beyond drainage class)
- Mycorrhizal association requirements
- Disturbance adaptation (fire, flooding, windthrow)
- Successional stage appropriateness
- Extreme event tolerance (not just means)

### Tier 4: Cutting-Edge Variables (Future Development)
- Pollinator/disperser availability
- Soil microbiome compatibility
- Urban/pollution stress tolerance
- Phenological synchrony with climate

### Data Integration Strategy

**AlphaEarth Variables** (already integrated):
- Clay, sand, silt content → soil texture matching
- Organic carbon density → soil fertility indicator
- These align well with common variables across all platforms

**Additional Data Needed**:
- Climate data integration (PRISM, WorldClim, or climate reanalysis)
- Elevation data (SRTM or regional DEMs)
- Ecoregion classifications
- Species trait databases (TRY database, regional trait compilations)
- Climate projection data (CMIP6 scenarios)

**Unique Opportunity**:
- Integrate biotic variables from species descriptions (mycorrhizal type, pollination syndrome, dispersal mode)
- Use existing Treekipedia data on species traits to inform aptness beyond abiotic factors
- Combine occurrence data (geohash tiles) with environmental layers to empirically derive species-environment relationships

---

## Recommendations

### For Immediate Implementation
1. **Prioritize climate and soil variables** - These are universal across all tools
2. **Integrate elevation data** - Critical constraint with high impact
3. **Add ecoregion filtering** - Efficient biogeographic screening
4. **Use climate means AND extremes** - Temperature/precipitation ranges, not just averages

### For Near-Term Development
1. **Climate change layer** - Future climate suitability (following D4R model)
2. **Trait-based filtering** - Drought tolerance, shade tolerance, growth rate, maximum height
3. **Seed zone mapping** - Genetic provenance recommendations (following D4R)
4. **Successional context** - Early vs. late successional species recommendations

### For Long-Term Research
1. **Soil moisture modeling** - Integrate topography, soil texture, precipitation for moisture regime
2. **Mycorrhizal matching** - Database of mycorrhizal associations and soil conditions
3. **Disturbance adaptation scoring** - Fire tolerance, flood tolerance, wind firmness
4. **Phenological modeling** - Climate-phenology synchrony for pollinators/dispersers

### Competitive Positioning
By integrating Tier 3 and Tier 4 variables, Treekipedia can differentiate from existing tools:
- **Restor**: Provides species lists but not ranked aptness scores
- **D4R**: Limited to tropical/select regions, Treekipedia is more comprehensive taxonomically
- **FIA**: Data infrastructure, not a recommendation engine
- **TNC**: Multiple separate tools, not integrated species recommendation
- **NRCS**: US-only, less sophisticated climate integration

---

## Sources

### Diversity for Restoration (D4R)
- [D4R Tool Overview - Alliance Bioversity International](https://alliancebioversityciat.org/tools-innovations/diversity-restoration-d4r)
- [Diversity for Restoration: Guiding species and seed selection - Journal of Applied Ecology](https://besjournals.onlinelibrary.wiley.com/doi/full/10.1111/1365-2664.14079)
- [D4R: A scalable tool for climate-smart restoration - ResearchGate](https://www.researchgate.net/publication/357825167_Diversity_For_Restoration_D4R_a_scalable_tool_to_guide_tree_species_and_seed_selection_for_climate-smart_restoration_of_tropical_forest_landscapes)

### USFS Forest Inventory and Analysis
- [Forest Inventory and Analysis - US Forest Service Research](https://research.fs.usda.gov/programs/fia)
- [FIA National Program](https://www.fia.fs.fed.us/)
- [United States Forest Service Use of Forest Inventory Data - Frontiers](https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2021.763487/full)
- [FIA Geospatial Showcase](https://fia-usfs.hub.arcgis.com/)

### The Nature Conservancy
- [Data & Tools - The Nature Conservancy](https://www.nature.org/en-us/what-we-do/our-insights/data-and-tools/)
- [We Must Restore Nature This Decade](https://www.nature.org/en-us/what-we-do/our-insights/perspectives/critical-decade-ecosystem-restoration/)
- [Conservation Planning Software - GIS Toolkit](https://www.landscapepartnership.org/maps-data/gis-planning/conservation-planning/conservation-planning-software)
- [Restoration Ecology - Nature Scitable](https://www.nature.com/scitable/knowledge/library/restoration-ecology-13339059/)

### Restor Platform
- [Restor: Global hub for nature restoration](https://restor.eco/)
- [Restor: New platform connects global restoration movement](https://about.restor.eco/blog/restor-new-platform-connects-the-global-restoration-movement-for-the-first)
- [How Restor is using Google Earth Engine - Google Cloud Blog](https://cloud.google.com/blog/topics/sustainability/how-restor-is-using-google-earth-engine-data-to-tackle-ecosystem-restoration)
- [Restor helps anyone be part of ecological restoration - Google Blog](https://blog.google/outreach-initiatives/sustainability/restor-helps-anyone-be-part-ecological-restoration/)
- [Welcome to Restor - Global Landscapes Forum](https://thinklandscape.globallandscapesforum.org/55965/welcome-to-restor-where-restoration-data-comes-with-just-a-click-on-a-map/)

### NRCS Plant Materials
- [Conservation Practice Standards - NRCS](https://nrcs.usda.gov/wps/portal/nrcs/main/national/technical/cp/ncps)
- [Ecological Site Descriptions - NRCS](https://www.nrcs.usda.gov/getting-assistance/technical-assistance/ecological-sciences/ecological-site-descriptions)
- [FHWA Ecoregional Revegetation Application](https://www.nativerevegetation.org/era/)
- [Ecosystem and Vegetation System Management - FHWA](https://www.environment.fhwa.dot.gov/env_topics/ecosystems/veg_mgmt_rpt/vegmgmt_ecoregional_approach.aspx)

---

**Document Status**: Complete
**Word Count**: ~4,950 words
**Next Steps**: Review findings with development team and prioritize variable integration for Species Aptness Score algorithm
