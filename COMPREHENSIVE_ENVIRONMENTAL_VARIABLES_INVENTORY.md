# Comprehensive Environmental Variables Inventory for Treekipedia

**Date:** 2026-01-21

**Author:** Gemini AI Research Coordinator

**Version:** 1.0

---

## 1. Executive Summary

This document presents a comprehensive inventory of environmental variables to enhance Treekipedia's LEAF™ species recommendation engine. The goal is to evolve the engine from its current, successful model based on species occurrence and native status to a world-class, ecologically-grounded prediction system.

The research audited Treekipedia's existing data, identifying a strong foundation in biogeography (`ecoregions`, `biomes`) and basic climate data. However, major gaps exist in the quantitative characterization of a site's **soil, topography, and disturbance history**.

This inventory details key variables across six domains: Hydrology, Topography, Soil, Microclimate, Disturbance, and Functional Traits. For each variable, we provide its ecological significance, the best-in-class global datasets (with a focus on Google Earth Engine accessibility), and a recommended implementation priority.

The overarching recommendation is to adopt a tiered implementation strategy:
1.  **Priority 1: Foundational Site Characterization.** Ingest quantitative **Soil** data (from OpenLandMap & SoilGrids) and derive advanced **Topographic** indices (TWI, TPI) from the existing SRTM elevation data. These two categories represent the largest current gaps and offer the most significant immediate improvement to the model.
2.  **Priority 2: Dynamic & Contextual Layers.** Integrate **Microclimate** variables (like Growing Degree Days) and **Disturbance/Land Use** history (from MODIS Fire and Hansen Forest Change). This will allow the model to account for growing seasons and site history.
3.  **Priority 3: Functional & Specialized Layers.** Augment the species database with quantitative **Functional Traits** (from TRY & GRooT) and add advanced **Hydrological** modeling (from HydroSHEDS). This enables goal-oriented recommendations (e.g., for "erosion control" or "drought resilience").

By systematically closing these data gaps, Treekipedia can create a uniquely powerful and scientifically robust species recommendation tool that accounts for the complete ecological context of a site.

---

## 2. The Variable Inventory

This section provides a detailed breakdown of the recommended environmental variables, categorized by domain.

### 2.1. Topography & Terrain
**Audit:** Treekipedia currently has descriptive elevation ranges but lacks quantitative terrain analysis.
**Recommendation:** This is a **High Priority** area. These variables can be derived from the existing SRTM elevation data.

| Variable | Ecological Significance | Recommended GEE Dataset | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Slope** | Affects runoff, soil stability, and solar radiation. | Derived from `USGS/SRTMGL1_003` | **1 - High** |
| **Aspect** | A critical microclimate driver, creating warm/dry vs. cool/moist slopes. | Derived from `USGS/SRTMGL1_003` | **1 - High** |
| **Topographic Wetness Index (TWI)** | **Powerful proxy for soil moisture** based on water flow paths. | Derived from `USGS/SRTMGL1_003` | **1 - High** |
| **Topographic Position Index (TPI)** | Identifies ridges, valleys, and slopes, which have distinct microclimates. | Derived from `USGS/SRRMGL1_003` | **2 - Medium** |
| **Solar Radiation Index** | A direct measure of the energy input on a slope, refining the proxy of Aspect. | Calculated from DEM & latitude. | **3 - Low** |

### 2.2. Soil
**Audit:** This is the **largest gap** in the current system, which only has qualitative text descriptions.
**Recommendation:** This is the **Highest Priority** area for new data ingestion.

| Variable | Ecological Significance | Recommended GEE Dataset | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Soil Organic Carbon (SOC)** | A master indicator of soil health, fertility, and water retention. | **OpenLandMap** (30m, temporal) | **1 - Highest** |
| **Cation Exchange Capacity (CEC)** | A primary proxy for **soil fertility** and nutrient retention. | **SoilGrids** `mean_cec_0-30cm` | **1 - Highest** |
| **Available Water Capacity (AWC)** | The amount of water soil can hold for plants; a key drought-resilience metric. | **SoilGrids** (Calculated from texture/SOC) | **1 - Highest** |
| **Bulk Density** | Measures soil compaction, which can restrict root growth. | **OpenLandMap** / **SoilGrids** | **2 - Medium** |
| **Depth to Bedrock** | Determines the available rooting volume for trees. | **SoilGrids** `depth_to_bedrock` | **2 - Medium** |
| **pH** | Controls nutrient availability. | **OpenLandMap** / **SoilGrids** | **2 - Medium** |

### 2.3. Microclimate
**Audit:** Good foundation of species-level Bioclim variables exists. Gaps are in site-specific, derived variables.
**Recommendation:** This is a **Medium Priority** area, focused on deriving more dynamic variables.

| Variable | Ecological Significance | Recommended GEE Dataset | Implementation Priority |
| :--- | --- | :--- | :--- |
| **Core BIOVARS (e.g., BIO6, BIO14)**| Min Temp of Coldest Month (cold stress) and Precip of Driest Month (drought). | **CHELSA V2.1** `BioClim` | **1 - High (Already Partially Implemented)** |
| **Growing Degree Days (GDD)** | The energy available for growth; defines the effective growing season length. | Derived from CHELSA/TerraClimate daily temp. | **2 - Medium** |
| **Frost-Free Days** | The number of days between last and first frost; a key limit for sensitive species. | Derived from CHELSA/TerraClimate daily temp. | **2 - Medium** |
| **Aridity Index (P/PET)** | A measure of water stress, comparing precipitation (P) to potential evapotranspiration (PET). | `P` from CHELSA, `PET` from `IDAHO_EPSCOR/TERRACLIMATE` | **3 - Low** |

### 2.4. Disturbance & Land Use History
**Audit:** This is a major gap. The database currently has no explicit fields for disturbance or land use history.
**Recommendation:** This is a **Medium Priority** area that provides crucial context for restoration.

| Variable | Ecological Significance | Recommended GEE Dataset | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Time Since Forest Loss** | Indicates the successional stage (early vs. mature forest). | **Hansen Global Forest Change** `lossyear` band | **1 - High** |
| **Fire Frequency** | Determines the fire regime and favors fire-adapted or fire-intolerant species. | **MODIS Burned Area** `MODIS/061/MCD64A1` | **2 - Medium** |
| **Historical Land Use** | Legacy of agriculture degrades soil; provides context on feasibility. | **HYDE 3.2** (cropland/pasture layers) | **3 - Low** |
| **Human Footprint Index** | A composite measure of all human pressures on the landscape. | **Human Influence Index (HII)** `projects/HII/v1/hii` | **3 - Low** |

### 2.5. Hydrology & Riparian
**Audit:** This is a major gap, with no specific hydrological variables currently implemented.
**Recommendation:** This is a **Medium Priority** area, essential for modeling riparian zones and floodplains.

| Variable | Ecological Significance | Recommended GEE Dataset | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Distance to Water** | A fundamental proxy for water availability, defining riparian corridors. | **JRC Global Surface Water** `occurrence` band | **1 - High** |
| **Stream Order** | Differentiates small headwater streams from large rivers, which have different ecologies. | Derived from **HydroSHEDS** | **2 - Medium** |
| **Flood Frequency** | Identifies flood-prone areas, favoring flood-tolerant species. | **Global Flood Database (GFD)** | **3 - Low** |

### 2.6. Species Functional Traits
**Audit:** A good foundation of morphological traits exists, but it lacks quantitative data linked to restoration goals.
**Recommendation:** This is a **Low Priority** for new data ingestion but high priority for integration with the LEAF™ engine.

| Variable | Ecological Significance | Recommended Trait Database(s) | Implementation Priority |
| :--- | :--- | :--- | :--- |
| **Maximum Rooting Depth** | The key trait for **drought resilience**. | **GRooT** (primary), TRY | **1 - High** |
| **Wood Density** | Relates to drought tolerance and growth rate. | TRY, BIEN | **2 - Medium** |
| **Specific Leaf Area (SLA)** | Relates to growth rate and resource strategy (conservative vs. acquisitive). | TRY, BIEN | **2 - Medium** |
| **Nitrogen Fixation** | A critical trait for **soil building** on degraded sites. | TRY (categorical trait) | **3 - Low** |

---
## 3. Final Implementation Roadmap

1.  **Phase 1: Ingest Foundational Soil & Topography (Highest Impact)**
    -   Create GEE scripts to generate global raster layers for **Slope**, **Aspect**, and **TWI**.
    -   Ingest **SOC**, **CEC**, **AWC**, and **Depth to Bedrock** from OpenLandMap and SoilGrids.
    -   Integrate these six new variables into the LEAF™ engine's species profiling and site scoring algorithms.

2.  **Phase 2: Add Contextual Layers for Disturbance & Microclimate**
    -   Derive **Time Since Disturbance** and **Fire Frequency** layers.
    -   Derive **Growing Degree Days** and **Frost-Free Days** layers.
    -   Incorporate these as additional scoring factors in the LEAF™ engine (e.g., matching species successional stage to time since disturbance).

3.  **Phase 3: Enable Goal-Oriented Recommendations**
    -   Systematically query and ingest quantitative **Functional Trait** data from GRooT and TRY for Treekipedia's species.
    -   Modify the LEAF™ engine and UI to accept "Restoration Goals" (e.g., Drought Resilience, Erosion Control).
    -   Create scoring logic that up-weights species possessing the functional traits that support the selected goal.

By executing this roadmap, Treekipedia can build a truly world-class, data-driven recommendation system that honors the ecological complexity of restoration.
