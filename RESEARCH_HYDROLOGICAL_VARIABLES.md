# RESEARCH: Hydrological & Riparian Variables for Species Distribution Modeling

This document outlines the key hydrological and riparian variables used in Species Distribution Modeling (SDM) and ecological restoration. It covers variables found in scientific literature, their data sources (with a focus on Google Earth Engine), their ecological significance, and recommendations for integration into the Treekipedia platform.

---

## 1. Key Hydrological & Riparian Variables

Hydrological variables are critical for all species and are foundational to defining riparian ecosystems. They can be categorized into several groups.

### 1.1. Direct Water & Flow Characteristics

These variables describe the presence, movement, and characteristics of surface water.

| Variable | Description | Ecological Effect |
| --- | --- | --- |
| **Distance to Water** | Horizontal distance to the nearest river, stream, or water body. | A fundamental proxy for water availability. Species intolerant of dry conditions cluster near water. A key variable in almost all riparian SDMs. |
| **Flow Rate / Velocity**| Speed of water movement. | Affects substrate composition, nutrient transport, and physical disturbance. High velocity favors species adapted to disturbance. |
| **Flow Accumulation** | Modeled amount of upstream water flowing into a specific cell. | Proxy for stream size and power. Larger flow accumulation indicates larger rivers with different ecological dynamics than headwater streams. |
| **Stream Order** | A numerical classification of stream size (e.g., Strahler stream order). | Headwater streams (low order) have different temperature, light, and nutrient regimes than larger rivers (high order). |
| **Flood Frequency & Duration**| How often and for how long an area is inundated. | A primary driver of riparian vegetation. Species are adapted to specific flood regimes (e.g., "flood-tolerant" vs. "flood-intolerant"). |
| **Surface Water Presence**| Binary or probabilistic measure of surface water existence in a given pixel over time. | Identifies permanent vs. intermittent or ephemeral streams and water bodies, which support different ecological communities. |

### 1.2. Topographically-Derived Hydrological Proxies

These variables are derived from Digital Elevation Models (DEMs) and serve as proxies for soil moisture and water flow patterns.

| Variable | Description | Ecological Effect |
| --- | --- | --- |
| **Topographic Wetness Index (TWI)** | Also known as Compound Topographic Index (CTI). Quantifies topographic control on hydrological processes. `TWI = ln(a / tan(b))` where 'a' is the upslope contributing area and 'b' is the local slope. | High TWI values indicate areas likely to be wetter (flats, valley bottoms). Low TWI values indicate drier ridgetops. Strongly correlates with soil moisture and vegetation patterns. |
| **Topographic Position Index (TPI)**| The difference between a cell's elevation and the average elevation of the neighborhood around it. | Identifies landscape features like ridges (positive TPI), valleys (negative TPI), and slopes (near-zero TPI), which have distinct moisture and microclimate regimes. |
| **Terrain Ruggedness Index (TRI)** | Measures the elevation change between a grid cell and its neighbors. | High TRI indicates rugged terrain, which can create diverse microhabitats but also limit species movement. |

### 1.3. Soil & Groundwater Indicators

| Variable | Description | Ecological Effect |
| --- | --- | --- |
| **Soil Moisture** | Amount of water held in the soil. | A direct measure of water availability to plant roots. A critical limiting factor for plant growth and survival. |
| **Soil Drainage Class** | A qualitative measure of the frequency and duration of wet periods (e.g., very poorly drained to excessively drained). | Determines the soil's aeration and chemical properties, strongly influencing which species can thrive. |
| **Depth to Groundwater** | The distance from the soil surface to the water table. | Indicates the accessibility of groundwater for deep-rooted plants, especially in arid or seasonally dry climates. |

---

## 2. Data Sources & GEE Availability

A significant advantage for Treekipedia is the availability of global-scale datasets within Google Earth Engine (GEE).

| Variable | GEE Dataset / Method | Resolution | Notes |
| --- | --- | --- | --- |
| **DEM & Derivatives (TWI, TPI, Slope)** | **SRTM GL1** (Global), **USGS 3DEP** (US) | 30m (SRTM), 10m/3m (3DEP) | Treekipedia already uses SRTM. TWI and TPI are computationally intensive but can be derived directly from the DEM in GEE. |
| **Distance to Water** | **Global Surface Water (JRC)**, **NHDPlus (US)** | 30m | The JRC dataset provides global maps of water occurrence, which can be used to calculate distance. NHDPlus is a high-resolution US-specific dataset. |
| **Flow Accumulation / Stream Networks** | **HydroSHEDS** | 30m / 90m | This is the key dataset for hydrological modeling. It provides pre-calculated flow direction and accumulation layers, from which stream networks can be derived. |
| **Flood Frequency** | **Global Flood Database (GFD)** | 30m | Provides flood extent and frequency maps derived from Landsat data from 2000-2018. |
| **Soil Moisture** | **SMAP**, **ERA5-Land** | ~10km | Coarse resolution, but provides a direct, time-series measure of soil moisture, useful for regional trends. Downscaling may be required for local SDMs. |
| **Soil Drainage** | **SoilGrids** | 250m | Provides soil properties, including drainage-related characteristics, that can be used to infer drainage class. |

---

## 3. How Organizations Model Riparian Ecosystems

### 3.1. US Forest Service (USFS)

-   **Model**: Riparian Buffer Delineation Model (RBDM), an ArcGIS-based tool.
-   **Goal**: To create a consistent, national inventory of riparian areas.
-   **Methodology**: Uses geospatial data to define variable-width riparian buffers.
-   **Key Datasets**:
    -   **NHDPlus**: The core hydrologic framework.
    -   **USGS DEMs**: For topographic analysis.
    -   **gSSURGO**: For soil information.
    -   **National Wetland Inventory**: To identify existing wetlands.

### 3.2. The Nature Conservancy (TNC)

-   **Tool**: Riparian Restoration Prioritization to Promote Climate Change Resilience (RPCCR).
-   **Goal**: To identify and prioritize riparian areas for restoration to enhance climate resilience.
-   **Methodology**: A web-based decision support tool that scores areas based on need and potential benefit.
-   **Key Variables**:
    -   **Lack of Tree Cover/Shade**: Identifies areas where planting trees would reduce water temperature.
    -   **Vulnerability to Air Temperature Warming**: Prioritizes areas most at risk.
    -   **Presence of Cold-Water Species**: Focuses on habitats for sensitive species like trout.
    -   **Land Cover, Dams, and other disturbances**.

---

## 4. Implementation Recommendations for Treekipedia

The LEAF™ scoring engine currently uses species occurrences and native status. Integrating hydrological variables can dramatically improve its ecological relevance and accuracy.

**Phase 1: Foundational Topographic Hydrology (High-Value, Low-Complexity)**

1.  **Derive TWI from existing DEM:** Since Treekipedia already uses SRTM elevation data, the Topographic Wetness Index (TWI) can be calculated. This is a powerful proxy for soil moisture.
    -   **Action:** Create a new GEE task or server-side process to compute and store a global TWI layer.
    -   **Integration:** Add `twi` as a new variable for each geohash tile. In the LEAF™ model, species could have a "preferred TWI range" calculated from the TWI values of their known occurrence locations. Recommendations for a new plot would be scored based on how well the plot's TWI matches the species' preferred range.

2.  **Calculate Distance to Water:** Use the JRC Global Surface Water dataset in GEE to calculate the distance to the nearest permanent or seasonal water body for every geohash tile.
    -   **Action:** Generate a global "distance to water" layer.
    -   **Integration:** Add `distance_to_water` to the geohash tile data. Similar to TWI, this can be used to create a species preference profile and score new locations.

**Phase 2: Advanced Hydrological Modeling**

3.  **Incorporate HydroSHEDS Data:** This is a more advanced step that would enable true network-based analysis.
    -   **Action:** Use HydroSHEDS to delineate watersheds and stream networks.
    -   **Integration:**
        -   **Stream Order:** Assign a stream order to relevant geohash tiles. This allows differentiating between headwater and large-river species.
        -   **Flow Accumulation:** Use as a proxy for river size and power.
        -   **Watershed-based Analysis:** Allow users to get recommendations for an entire watershed, not just a polygon.

**Phase 3: Dynamic & Disturbance Variables**

4.  **Integrate Flood Data:** Use the Global Flood Database to identify areas prone to flooding.
    -   **Action:** Create a "flood frequency" or "flood risk" variable for geohash tiles.
    -   **Integration:** This allows for a "flood tolerance" filter or score modifier in the LEAF™ engine, recommending flood-tolerant species in high-risk areas.

---

## 5. Gap Analysis

-   **High-Resolution Soil Moisture:** Global, high-resolution soil moisture data is still a major gap in ecological modeling. While coarse satellite products (SMAP) exist, they are not suitable for fine-scale SDMs. TWI is the best available proxy.
-   **Groundwater Data:** Global datasets for depth to groundwater are generally very coarse or unavailable. This is a significant unknown in many ecosystems, especially arid ones where it's a critical water source.
-   **Riparian-Specific Species Traits:** While not a data layer, there is a need to systematically classify species as "riparian obligate," "riparian facultative," or "upland." This would require a literature review and expert input but would be a powerful flag in the species database.

By integrating these hydrological variables, Treekipedia can evolve the LEAF™ engine from a location-based system to a more sophisticated, ecologically-grounded recommendation tool that accounts for the fundamental role of water in shaping plant communities.
