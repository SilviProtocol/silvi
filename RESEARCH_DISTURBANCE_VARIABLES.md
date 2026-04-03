# RESEARCH: Disturbance & Land Use History Variables for SDM

This document outlines key disturbance and land use history variables used in Species Distribution Modeling (SDM) and restoration planning. It covers the ecological significance of these variables, identifies major global datasets available in Google Earth Engine (GEE), and provides implementation recommendations for Treekipedia.

---

## 1. The Ecological Importance of Legacy Effects

The current distribution of species is not just a function of the present-day environment. It is also shaped by the "ghosts of the past"—the legacy effects of historical disturbances and land use. A forest growing on a field that was abandoned 50 years ago is ecologically very different from an old-growth forest, even if the current climate and soil are identical. Incorporating these historical variables is critical for accurate modeling and effective restoration planning.

---

## 2. Key Disturbance & Land Use Variables

These variables can be grouped into natural disturbances, direct human modifications, and composite indices of human pressure.

### 2.1. Natural & Semi-Natural Disturbances

| Variable | Description | Ecological Significance |
| --- | --- | --- |
| **Fire Frequency** | The number of times a given area has burned over a specific period. | A primary driver of ecosystem structure in many biomes. Some species are fire-adapted and require it for regeneration (e.g., Jack Pine), while others are fire-intolerant. |
| **Time Since Last Fire** | The number of years that have passed since the last recorded fire event. | Determines the successional stage of the ecosystem. Recently burned areas favor early-successional, colonizing species. |
| **Fire Intensity/Severity**| The magnitude of the fire's impact (e.g., energy release, biomass consumed). | High-severity, stand-replacing fires reset the ecosystem, while low-intensity ground fires may only clear out understory, creating different regeneration niches. |

### 2.2. Land Use & Anthropogenic Variables

| Variable | Description | Ecological Significance |
| --- | --- | --- |
| **Forest Loss & Gain** | The removal (deforestation) or establishment (afforestation) of tree cover. | The most direct measure of habitat conversion. "Loss" indicates a major disturbance event. |
| **Time Since Disturbance** | The number of years since a major forest loss event. | Similar to "Time Since Last Fire," this indicates the successional stage. Early-successional species thrive in recently disturbed areas. |
| **Land Use Type** | Categorical classification of land (e.g., cropland, pasture, urban, forest). | Determines the fundamental habitat type and the nature of human pressure. Historical land use has strong legacy effects on soil structure and chemistry. |
| **Road Density / Distance to Roads** | The length of roads within a given area, or the distance from a point to the nearest road. | Roads are vectors for invasive species, sources of pollution, and cause habitat fragmentation, creating "edge effects." |
| **Human Footprint Index** | A composite index that aggregates multiple human pressures (population, infrastructure, land use). | Provides a single, continuous measure of anthropogenic intensity, from pristine (0) to heavily modified (100). |

---

## 3. Global Datasets & GEE Availability

Google Earth Engine hosts a rich catalog of global, high-resolution datasets perfect for characterizing disturbance and land use.

| Variable | GEE Dataset | Resolution | Temporal Coverage | Notes |
| --- | --- | --- | --- | --- |
| **Fire** | **MODIS Burned Area**: `MODIS/061/MCD64A1` | 500 meters | 2000 - Present | Provides the day of year for each burn event. Ideal for calculating fire frequency and time since last fire. |
| **Forest Change** | **Hansen Global Forest Change**: `UMD/hansen/global_forest_change_2022_v1_10` | 30 meters | 2000 - 2022 | **The gold standard for deforestation.** Includes layers for tree cover in 2000, loss, gain, and the year of loss for each pixel. |
| **Human Footprint**| **Human Influence Index (HII)**: `projects/HII/v1/hii` | ~1 km | 1995-2004 (static) | A powerful, pre-calculated index of cumulative human pressure. While somewhat dated, it provides an excellent baseline. |
| **Modern Land Use**| **ESA WorldCover 10m** | 10 meters | 2020, 2021 | Extremely high-resolution classification of modern land cover, including cropland, built-up, forest, etc. |
| **Historical Land Use**| **HYDE (History Database of the Global Environment)** | ~10 km | 1700 - 2017 | Coarse resolution but provides the invaluable long-term historical context of land conversion to cropland and pasture. |

---

## 4. Implementation Recommendations for Treekipedia

Integrating these variables will allow the LEAF™ engine to account for the ecological history of a site, leading to more realistic and successful restoration recommendations.

**Priority 1: Implement Core Disturbance History**

1.  **Calculate Fire Frequency and Time Since Fire:**
    -   **Action:** Using the `MODIS/061/MCD64A1` dataset in GEE, create two new global layers: `fire_frequency` (count of burns since 2000) and `time_since_last_fire` (years). Store the value for each geohash tile.
    -   **Integration (LEAF™ Engine):**
        -   Profile species based on their fire tolerance. Species that occur in high-frequency fire regimes are fire-adapted.
        -   In the LEAF™ engine, use this to up-weight fire-adapted species in fire-prone landscapes and down-weight fire-intolerant species.

2.  **Calculate Time Since Forest Loss:**
    -   **Action:** Using the `lossyear` band from the Hansen Global Forest Change dataset, calculate a `time_since_disturbance` layer. This represents the age of the regenerating forest.
    -   **Integration:** This is a powerful variable for successional status.
        -   Profile species as "early," "mid," or "late" successional based on the average `time_since_disturbance` of their occurrence locations.
        -   For a restoration site, this allows the engine to recommend pioneer species for recently cleared land, and late-successional species for maturing forests.

**Priority 2: Add Land Use Context**

3.  **Incorporate Land Use Data:**
    -   **Action:** Ingest both a modern and a historical land use layer.
        -   **Modern:** Use the **ESA WorldCover 10m** data to classify each geohash tile by its current land use (e.g., `cropland`, `forest`, `grassland`).
        -   **Historical:** Use the **HYDE** dataset to create a `legacy_cropland` flag for tiles that were agricultural in the past (e.g., in 1950).
    -   **Integration:**
        -   This provides critical context. Recommending a forest restoration on land that is currently active cropland is not feasible. The `legacy_cropland` flag is a powerful indicator of past soil degradation.
        -   The LEAF™ engine can use the modern land use class as a hard filter (e.g., don't recommend trees in `urban` areas) and the historical flag as a scoring factor (e.g., prioritize hardy, soil-building species on legacy cropland).

By adding disturbance and land use history, Treekipedia can better understand the "starting point" of a restoration project, recommending the right species for the right successional stage and historical context.
