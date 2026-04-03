# RESEARCH: Topographic & Terrain Variables for Species Distribution Modeling

This document details the key topographic and terrain variables used in Species Distribution Modeling (SDM) and ecological site assessment. It covers the derivation of these variables from Digital Elevation Models (DEMs), their ecological significance, data availability in Google Earth Engine (GEE), and recommendations for integration into the Treekipedia platform.

---

## 1. Primary & Secondary Terrain Variables

Topography exerts a powerful indirect influence on species distribution by controlling microclimate, hydrology, and soil properties. Nearly all topographic variables are derived from a Digital Elevation Model (DEM). They can be classified as primary (directly calculated from the DEM) or secondary (more complex indices).

### 1.1. Primary Topographic Variables

These are the foundational attributes of the landscape.

| Variable | Description | Ecological Meaning & Effect | Derivation |
| --- | --- | --- | --- |
| **Elevation** | The height of a point above sea level. | A master variable that influences temperature (adiabatic lapse rate), precipitation, and atmospheric pressure. Often creates distinct life zones (e.g., montane, subalpine, alpine). | Direct value from DEM. |
| **Slope** | The steepness or gradient of the terrain, measured in degrees or percent. | Affects solar radiation exposure, soil stability, soil moisture (runoff vs. infiltration), and erosion rates. Steep slopes have thinner soils and are prone to disturbance. | First derivative of elevation. |
| **Aspect** | The downslope direction of the terrain, measured in degrees (0-360°). | A critical microclimate driver. In the Northern Hemisphere, south-facing slopes are warmer and drier (more sun) while north-facing slopes are cooler and moister (less sun), creating vastly different habitats. | First derivative of elevation. |

### 1.2. Secondary Topographic Variables (Terrain Indices)

These indices combine primary variables to quantify more complex landscape characteristics that are often more ecologically meaningful.

| Variable | Description | Ecological Meaning & Effect | Derivation |
| --- | --- | --- | --- |
| **Topographic Position Index (TPI)** | The difference between a cell's elevation and the mean elevation of its neighborhood. | **Identifies landforms.** Positive values = ridges/hilltops (exposed, drier). Negative values = valleys/depressions (sheltered, moister, prone to cold air drainage). Values near zero = mid-slopes or flat areas. Highly scale-dependent. | `TPI = Elevation - FocalMean(Elevation)` |
| **Topographic Wetness Index (TWI)** | Also Compound Topographic Index (CTI). Quantifies topographic control on soil moisture. | **Proxy for soil moisture.** High TWI predicts higher soil moisture (valley bottoms, flats). Low TWI predicts lower soil moisture (ridges). A powerful predictor for vegetation patterns, especially in temperate forests. | `TWI = ln(Upslope Contributing Area / tan(Slope))` |
| **Terrain Ruggedness Index (TRI)** | The mean difference between a central pixel and its 8 neighbors. | **Measures topographic heterogeneity.** High TRI indicates rugged, complex terrain, which can offer a diversity of micro-refugia from climate change and disturbance. Low TRI indicates smoother, more uniform terrain. | `TRI = Mean(Abs(CenterPixel - NeighborPixel))` |
| **Solar Radiation / Heat Load Index** | An estimate of the potential solar energy received at a location, based on latitude, aspect, and slope. | **Proxy for energy input and temperature.** A more direct measure of the energy-driven microclimate differences captured indirectly by aspect. Influences temperature, evapotranspiration, and growing season length. | Complex calculation involving sun-earth geometry, slope, and aspect. Many formulations exist. |
| **Curvature** (Profile & Plan) | The second derivative of the DEM. Profile curvature is parallel to slope; Plan curvature is perpendicular. | **Characterizes erosion/deposition.** Profile curvature affects flow acceleration. Plan curvature affects flow convergence/divergence. Helps identify areas of soil accumulation or erosion. | Second derivative of elevation. |
| **Landform Classification** | A categorical variable that classifies the landscape into types like "ridge", "valley", "upper slope", "lower slope" etc. | A user-friendly synthesis of TPI and slope, providing an intuitive way to categorize habitat types. | Derived from TPI and slope thresholds. For example, "Valley" = low TPI, "Ridge" = high TPI. |

---

## 2. Data Sources & GEE Availability

All topographic variables are derived from a DEM. The quality of the input DEM is therefore critical.

| DEM Dataset | GEE Availability | Resolution | Coverage | Notes |
| --- | --- | --- | --- | --- |
| **SRTM GL1 (Shuttle Radar Topography Mission)** | `USGS/SRTMGL1_003` | 30 meters | Near-Global | **The industry standard for global SDMs.** Treekipedia already uses this. It is sufficient for deriving all listed topographic variables. |
| **USGS 3DEP** | `USGS/3DEP/10m`, `USGS/3DEP/1m` | 10m, 1m | USA Only | Higher resolution data available for the US, which can be beneficial for fine-scale local analysis. |
| **Copernicus DEM** | `COPERNICUS/DEM/GLO30` | 30 meters | Global | A newer global DEM product that can be a good alternative or supplement to SRTM. |

**Derivation in GEE:** Google Earth Engine provides built-in functions to calculate primary derivatives like slope and aspect (`ee.Terrain.products`). Secondary indices like TWI and TPI require custom functions but are well-documented in the GEE community and literature. These calculations are computationally intensive and results should be pre-calculated and stored as new asset layers.

---

## 3. Implementation Recommendations for Treekipedia

Treekipedia's use of a geohash-based grid system is well-suited to integrating topographic variables. Since SRTM is already in use, the foundational data is ready.

**Priority 1: Implement Core Landform & Microclimate Variables**

1.  **Calculate and Store Slope, Aspect, and TPI:** These three variables provide the core "shape" and microclimate context of the landscape.
    -   **Action:** Create a server-side GEE script to compute `slope`, `aspect`, and `TPI` (at a medium neighborhood, e.g., 300m) for the entire globe from the SRTM DEM. Store the mean value of each variable for every geohash tile in the Treekipedia database.
    -   **Integration (LEAF™ Engine):**
        -   **Species Profiling:** For each species, calculate the mean and standard deviation of `slope`, `aspect`, and `TPI` across all its known occurrence points. This creates a "topographic niche" profile.
        -   **Scoring:** When a user analyzes a new plot, the LEAF™ engine can score species based on how well the plot's topographic variables match the species' preferred niche. For example, a species that prefers cool, moist north-facing slopes would be down-weighted for a plot on a hot, dry south-facing slope.

2.  **Derive a Categorical Landform Layer:**
    -   **Action:** Using the pre-calculated TPI and slope, create a simplified landform classification layer (e.g., 6 classes: Ridge, Upper Slope, Mid-Slope, Lower Slope, Valley, Flat).
    -   **Integration (UI/UX):** This provides a very user-friendly filter and descriptive variable. Users could see that a species "Often found in Valleys" or filter recommendations for "Ridges only".

**Priority 2: Add Advanced Hydrological & Energy Proxies**

3.  **Calculate and Store TWI:** As detailed in the Hydrological Variables report, TWI is a powerful proxy for soil moisture.
    -   **Action:** Compute and store a global TWI layer, averaging the value for each geohash tile.
    -   **Integration:** This adds a soil moisture dimension to the LEAF™ model, crucial for distinguishing species' water requirements.

4.  **Calculate and Store a Solar Radiation Index:** This provides a more direct measure of energy input than aspect alone.
    -   **Action:** Use a standard formulation in GEE to calculate a heat load or solar radiation index. Store the mean value per geohash tile.
    -   **Integration:** This allows for more accurate modeling of the thermal niche of species, improving recommendations in topographically complex terrain.

By implementing these variables, Treekipedia can add a detailed understanding of terrain and microclimate to its species recommendation engine, enabling it to distinguish between a hot, dry, steep southern slope and a cool, moist, gentle northern slope within the same climate zone.
