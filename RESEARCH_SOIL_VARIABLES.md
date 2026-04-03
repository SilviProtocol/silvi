# RESEARCH: Soil Variables for Species Distribution Modeling

This document details the key soil variables used in Species Distribution Modeling (SDM), with a focus on data sources that go beyond basic pH and texture. It covers the ecological significance of these variables, compares leading global soil datasets, and provides recommendations for integration into the Treekipedia platform.

---

## 1. Key Soil Variables for SDM (Beyond pH & Texture)

While pH and texture (sand/silt/clay content) are fundamental, a richer set of soil variables is needed to model the complex relationship between species and their edaphic environment. These variables influence nutrient availability, water retention, and root growth.

| Variable | Description | Ecological Significance & Effect |
| --- | --- | --- |
| **Soil Organic Carbon (SOC)** | The mass of organic carbon in the soil, often measured in grams per kg. | A master indicator of soil health. SOC influences soil structure, water retention, and nutrient cycling. High SOC generally supports higher biological activity and fertility. |
| **Cation Exchange Capacity (CEC)** | The soil's capacity to hold and exchange positively charged ions (cations) like Calcium (Ca), Magnesium (Mg), and Potassium (K). | **A proxy for soil fertility.** A higher CEC indicates a greater ability to retain essential plant nutrients, preventing them from being leached away. Clay and organic matter have high CEC. |
| **Bulk Density** | The weight of dry soil in a given volume (e.g., g/cm³). | **Indicates soil compaction.** High bulk density can restrict root penetration and reduce water infiltration and aeration, limiting the growth of many tree species. |
| **Available Water Capacity (AWC)** | The amount of water that a soil can store that is available for use by plants. | A critical factor for plant survival, especially in regions with seasonal rainfall. It is the difference between field capacity and permanent wilting point. |
| **Soil Depth to Bedrock** | The depth from the surface to a restrictive layer or bedrock. | **Determines rooting volume.** Deeper soils allow for more extensive root systems, providing better anchorage and access to a larger volume of water and nutrients. Shallow soils limit tree size and drought resilience. |
| **Soil Erodibility (K-factor)**| A measure of the soil's susceptibility to erosion by water. | High erodibility indicates unstable soils where seedlings may struggle to establish. Species with strong, binding root systems are often favored on such soils. |
| **Soil Drainage Class** | A qualitative measure of how quickly water moves through the soil (e.g., very poorly drained to excessively drained). | Determines the soil's oxygen content (aeration). Waterlogged soils (poorly drained) lack oxygen and support only specialized anaerobic species (e.g., many willows, bald cypress). |
| **Nutrient Content (N, P, K)** | The concentration of macronutrients Nitrogen (N), Phosphorus (P), and Potassium (K). | Directly impacts plant growth and productivity. While often correlated with SOC and CEC, direct measurements can reveal specific nutrient limitations for certain species. |

---

## 2. Global Soil Data Sources

The main challenge in using soil data for SDMs has been the lack of high-resolution, global datasets. Two leading projects, SoilGrids and OpenLandMap, have largely solved this problem.

### 2.1. Comparison: SoilGrids vs. OpenLandMap

| Feature | **SoilGrids (ISRIC)** | **OpenLandMap** | **Treekipedia Recommendation** |
| --- | --- | --- | --- |
| **Primary Sponsor** | ISRIC - World Soil Information | Various academic partners | Both are reputable. |
| **Spatial Resolution** | 250 meters | **30 meters** | **OpenLandMap**. The ~8x higher resolution is a significant advantage for fine-scale analysis. |
| **Temporal Data** | Static (snapshot in time) | **Dynamic (5-year intervals for some variables)** | **OpenLandMap**. The ability to model changes in soil properties over time is a powerful feature for climate change analysis. |
| **Key Variables** | SOC, CEC, Bulk Density, pH, Texture, Nutrients, Depth to Bedrock, AWC (via calculations) | SOC, Bulk Density, pH, Texture | SoilGrids has a slightly more comprehensive list of directly available advanced variables (CEC, N). |
| **GEE Availability** | Yes (`projects/soilgrids-isric/assets/`) | Yes (various assets, search for OpenLandMap) | Both are readily accessible in GEE. |

**Conclusion:** For a next-generation platform like Treekipedia, **OpenLandMap should be the primary data source for soil variables where available**, due to its superior spatial resolution and unique temporal capabilities. **SoilGrids should be used as a secondary source** to fill in key variables that OpenLandMap may not yet provide, such as CEC and Nitrogen.

### 2.2. Other Datasets

-   **FAO Harmonized World Soil Database (HWSD):** An older but still valuable dataset. It's a raster database at a ~1km resolution. It has been largely superseded by SoilGrids and OpenLandMap for SDM purposes but can be a useful reference.
-   **ISRIC World Soil Information:** ISRIC is the organization behind SoilGrids. Their data portal is the source for the SoilGrids product.

---

## 3. Implementation Recommendations for Treekipedia

Integrating these advanced soil variables will significantly enhance the LEAF™ engine by allowing it to match species to the edaphic conditions they require.

**Priority 1: Integrate High-Resolution Base Layers**

1.  **Select Primary Data Source:** Make a strategic decision to prioritize **OpenLandMap (30m)** for its resolution and temporal data. Use **SoilGrids (250m)** to supplement with variables not present in OpenLandMap.
2.  **Ingest Core Fertility and Water Retention Variables:**
    -   **Action:** From OpenLandMap, ingest layers for **Soil Organic Carbon (SOC)** and **Bulk Density**. From SoilGrids, ingest **Cation Exchange Capacity (CEC)** and **Available Water Capacity (AWC)**. For each variable, ingest data for a relevant root-zone depth (e.g., 0-30 cm average). Store the mean value for each geohash tile.
    -   **Integration (LEAF™ Engine):**
        -   **Species Profiling:** Profile each species' "soil niche" by calculating the mean and standard deviation of SOC, CEC, Bulk Density, and AWC across its known occurrence locations.
        -   **Scoring:** Score species for a new plot based on how well the plot's soil properties match the species' preferred niche. This adds a crucial fertility and water-holding dimension to the model.

**Priority 2: Add Rooting and Stability Variables**

3.  **Incorporate Depth and Erodibility:**
    -   **Action:** From SoilGrids, ingest the **Depth to Bedrock** layer. From other sources or calculations (e.g., based on RUSLE equation using soil, slope, and climate data), derive a **Soil Erodibility (K-factor)** layer.
    -   **Integration:**
        -   **Depth to Bedrock:** Use as a hard filter or strong negative scoring factor. A species that can grow into a large tree should be heavily penalized in areas with very shallow soil.
        -   **Erodibility:** Create a "Soil Stabilization" suitability score. Species known for erosion control (e.g., deep, fibrous roots) can be up-weighted on highly erodible soils.

By adding this suite of soil variables, Treekipedia's LEAF™ engine can begin to answer not just "what can grow here?" but "what will *thrive* here based on the soil's fertility, water-holding capacity, and depth?"
