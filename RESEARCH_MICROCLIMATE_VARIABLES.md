# RESEARCH: Microclimate Variables for Species Distribution Modeling

This document details the key microclimate variables used in Species Distribution Modeling (SDM) and fine-scale habitat assessment. It covers the primary global datasets, the ecological meaning of the variables, and provides recommendations for integration into the Treekipedia platform.

---

## 1. The Importance of Microclimate

While broad-scale climate (macroclimate) determines the general geographic range of a species, microclimate determines where it can persist at a local scale. Topography, vegetation cover, and hydrological features create fine-scale variations in temperature, moisture, and light that are not captured by coarse climate models. These variations create "microrefugia" where species can survive outside their main range, which is especially important in the context of climate change.

## 2. Key Microclimate Variables & Datasets

High-resolution, gridded climate datasets are the foundation for microclimate analysis. They are typically created by "downscaling" coarser global climate models (GCMs) using topographic and other data to predict conditions at a finer scale.

### 2.1. Leading High-Resolution Climate Datasets

| Dataset | Resolution | Key Features | GEE Asset Example |
| --- | --- | --- | --- |
| **CHELSA** (Climatologies at high resolution for the earth's land surface areas) | ~1 km (30 arc-seconds) | **The current standard for ecological modeling.** Provides monthly temperature and precipitation, plus a suite of 19 standard bioclimatic variables. Topographically downscaled for high accuracy in complex terrain. | `projects/earthengine-legacy/assets/projects/climate-engine/chelsa/v2_1/` |
| **WorldClim** | ~1 km (30 arc-seconds) | **The classic, most widely used dataset.** Provides monthly climate data and the same 19 bioclimatic variables as CHELSA. Version 2.1 is the latest. | `WORLDCLIM/V1` (Note: older version, GEE may have newer versions in community assets) |
| **TerraClimate** | ~4 km | **Includes water balance variables.** Provides monthly temperature, precipitation, and derived variables like potential evapotranspiration (PET), soil moisture, and runoff. | `IDAHO_EPSCOR/TERRACLIMATE` |

**Recommendation:** **CHELSA** should be the primary source for Treekipedia's microclimate data due to its high resolution, rigorous downscaling methodology, and specific focus on ecological applications.

### 2.2. Bioclimatic Variables ("BIO" variables)

These 19 variables are derived from monthly temperature and precipitation data to represent more biologically meaningful aspects of climate. They are a standard feature of both CHELSA and WorldClim.

| Category | Variable | Description | Ecological Significance |
| --- | --- | --- | --- |
| **Annual Trends** | **BIO1**: Annual Mean Temperature | The average temperature over the year. | A general measure of warmth and energy availability. |
| | **BIO12**: Annual Precipitation | The total precipitation over the year. | A general measure of water availability. |
| **Seasonality** | **BIO4**: Temperature Seasonality | The standard deviation of monthly temperatures. | Measures the degree of temperature variation over the year. High values indicate a strongly seasonal, continental climate. |
| | **BIO15**: Precipitation Seasonality | The coefficient of variation of monthly precipitation. | Measures the evenness of precipitation. High values indicate a "peaky" rainfall pattern (e.g., a monsoon). |
| **Limiting Factors (Temperature)** | **BIO5**: Max Temperature of Warmest Month | The highest temperature experienced in an average year. | Represents the peak heat stress a species must tolerate. |
| | **BIO6**: Min Temperature of Coldest Month | The lowest temperature experienced in an average year. | **Represents the peak cold stress.** A critical limiting factor for species' poleward or upper-elevation range limits. |
| | **BIO11**: Mean Temperature of Coldest Quarter | The average temperature of the three coldest months. | A measure of the overall severity of the cold season. |
| **Limiting Factors (Precipitation)** | **BIO13**: Precipitation of Wettest Month | The amount of precipitation in the single wettest month. | Indicates the magnitude of peak water availability. |
| | **BIO14**: Precipitation of Driest Month | The amount of precipitation in the single driest month. | **Represents drought stress.** A critical limiting factor for species survival in arid or seasonal climates. |
| | **BIO17**: Precipitation of Driest Quarter | The total precipitation in the three driest months. | A measure of the length and severity of the dry season. |

### 2.3. Other Derived Microclimate Variables

These variables are not always pre-calculated but can be derived from the same daily or monthly temperature data that powers CHELSA and WorldClim.

| Variable | Description | Ecological Significance |
| --- | --- | --- |
| **Frost-Free Days** | The number of days between the last frost of spring and the first frost of autumn. | **Defines the length of the growing season.** A primary control on the life cycle of many plants. |
| **Growing Degree Days (GDD)** | A measure of heat accumulation, calculated by summing the degrees by which the mean daily temperature exceeds a certain base temperature (e.g., 5°C). | A proxy for the energy available for plant growth and development. Crucial for predicting flowering, fruiting, and maturation times. |
| **Potential Evapotranspiration (PET)** | The amount of water that *would be* evaporated and transpired if there were sufficient water available. | When compared with precipitation, it provides a measure of water deficit or aridity. |
| **Vapor Pressure Deficit (VPD)** | A measure of the "dryness" of the air, representing the difference between how much moisture is in the air and how much it can hold. | High VPD causes plants to close their stomata to conserve water, limiting photosynthesis. A key measure of drought stress. |
| **Cold Air Drainage/Pooling**| The tendency for cold, dense air to settle in valleys and depressions. | Creates "frost pockets" where nighttime temperatures are significantly colder than surrounding slopes. This can be modeled using a combination of TPI and elevation. |

---

## 3. Implementation Recommendations for Treekipedia

Integrating microclimate variables will allow the LEAF™ engine to model species' thermal and moisture niches with high precision.

**Priority 1: Ingest Core Bioclimatic Variables**

1.  **Select CHELSA as the Primary Source:** Use the CHELSA V2.1 Bioclimatic variables dataset in Google Earth Engine.
2.  **Ingest Key "BIO" Variables:** It is not necessary to ingest all 19 variables, as many are highly correlated. Start with a core set that represents annual trends, seasonality, and key limiting factors.
    -   **Action:** From CHELSA, ingest the following layers:
        -   `BIO1` (Annual Mean Temp)
        -   `BIO12` (Annual Precip)
        -   `BIO4` (Temp Seasonality)
        -   `BIO15` (Precip Seasonality)
        -   `BIO6` (Min Temp of Coldest Month) - *Critical for cold tolerance*
        -   `BIO14` (Precip of Driest Month) - *Critical for drought tolerance*
    -   Store the mean value for each variable in each geohash tile.
    -   **Integration (LEAF™ Engine):**
        -   **Species Profiling:** For each species, calculate its climatic niche by finding the mean and standard deviation of these 6 BIO variables across its known occurrences.
        -   **Scoring:** Score species for a new plot based on how well the plot's climate matches the species' preferred niche. This is a classic and powerful SDM technique.

**Priority 2: Add Derived Growing Season & Stress Variables**

3.  **Calculate Growing Season Indicators:**
    -   **Action:** Using daily temperature data (if available from a source like TerraClimate or CHELSA daily), calculate and ingest layers for **Frost-Free Days** and **Growing Degree Days (GDD)**.
    -   **Integration:** These provide a more direct measure of the conditions for growth than the standard BIO variables. A species can be profiled based on the GDD it requires to complete its life cycle.

4.  **Calculate a Moisture Stress Index:**
    -   **Action:** Ingest the **Potential Evapotranspiration (PET)** layer from the TerraClimate dataset. Calculate an aridity index, such as `P / PET` (Precipitation divided by PET).
    -   **Integration:** This provides a powerful index of water stress. Species can be scored based on their tolerance to arid conditions, improving recommendations in drylands and areas prone to drought.

By implementing this suite of microclimate variables, Treekipedia can move beyond generic climate zones and model the specific thermal and moisture conditions that a tree will experience at a given location, dramatically improving the ecological realism of its recommendations.
