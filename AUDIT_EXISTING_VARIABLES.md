# AUDIT: Treekipedia Existing Environmental Variables

This document audits the environmental and species variables currently implemented in the Treekipedia database, based on a review of the database schema and migration scripts. It identifies existing data assets and analyzes them in the context of the comprehensive variable list generated from the research tasks.

---

## Part 1: Variables We Already Have

This section details the variables that are present in the `species` table or other parts of the Treekipedia system.

### Climate Variables (Good Foundation)
The v10 data migration added a solid set of climate variables. These appear to be species-level summaries rather than per-geohash-tile data, likely representing the typical climate where the species is found. These correspond to several of the standard "Bioclim" variables.

-   `climate_type_koppengeiger` (Köppen-Geiger classification)
-   `annual_temperature_range_c`
-   `annual_precipitation_mm` (Corresponds to BIO12)
-   `wettest_month_precipitation_mm` (Corresponds to BIO13)
-   `driest_month_precipitation_mm` (Corresponds to BIO14)
-   `precipitation_seasonality_cv` (Corresponds to BIO15)
-   `wettest_quarter_precipitation_mm` (Corresponds to BIO16)
-   `driest_quarter_precipitation_mm` (Corresponds to BIO17)

### Soil Variables (Significant Gaps)
The existing soil data is qualitative and limited, representing a major area for improvement.

-   `compatible_soil_types_ai` / `_human`: These are high-level, descriptive text fields (e.g., "loamy, well-drained"). They lack the quantitative detail needed for robust SDM (e.g., specific values for pH, SOC, CEC).

### Topographic Variables (Basic Implementation)
The system has a basic understanding of elevation but lacks the more advanced terrain analysis variables.

-   `elevation_ranges_ai` / `_human`: A descriptive text field stating the typical elevation range for a species.
-   **SRTM Elevation Data:** The use of SRTM is mentioned in documentation (`TODO.md`), which is the foundational DEM for all other topographic variables.

### Species Traits (Good Foundation)
The database has a good number of morphological and life-history traits that serve as a foundation for a functional trait database.

-   **Morphology:** `growth_form`, `leaf_type`, `deciduous_evergreen`, `flower_color`, `fruit_type`, `bark_characteristics`, `maximum_height`, `maximum_diameter`.
-   **Life History:** `lifespan`, `maximum_tree_age`, `successional_stage`.
-   **Other:** `tolerances` (text field), `timber_value`, `non_timber_products`.

### Geographic/Biogeographic Variables (Strong)
This is a well-developed area of the database.

-   `ecoregions`
-   `biomes`
-   **Native Status:** The system has been updated to use the authoritative **WCVP (World Checklist of Vascular Plants)** dataset, replacing older, less reliable country-level fields. The `wcvp_native` and `wcvp_introduced` fields mentioned in the `CHANGELOG.md` are the current standard.

---

## Part 2: Variables We're Currently Collecting (External Datasets)

This lists data sources that are used to enrich the Treekipedia system, even if the variables are not stored directly in the main `species` table.

-   **SRTM Elevation:** Used as the base Digital Elevation Model. This is mentioned in the `TODO.md` and implied by the `elevation_ranges` field.
-   **Hansen Global Forest Change:** The `TODO.md` indicates plans to use this for updated occurrence data, but it can also be used for disturbance analysis (`lossyear`).
-   **AlphaEarth:** The user prompt mentioned this as an enrichment source, likely for the `geohash_species_tiles` table, providing embeddings for machine learning applications.

---

## Part 3: Variables We Can Derive

Based on the existing data, several powerful variables can be derived with an acceptable amount of effort.

-   **Slope, Aspect, TPI, TWI:** All of these can be derived directly from the **SRTM elevation data** that is already in use. This is a high-value, medium-effort task.
-   **Climate Analogues:** With the existing climate data, it's possible to build models that find locations with analogous climates.
-   **Cold Air Drainage:** Can be modeled using a combination of TPI and elevation.

---

## Part 4: Gap Analysis & Priority Ranking

This section compares the existing variables with the comprehensive list from the research tasks and ranks the gaps by priority.

| Variable Category | Gaps | Priority | Recommendation |
| --- | --- | --- | --- |
| **Soil** | **Massive Gap.** Lack of quantitative data on fertility, water capacity, and structure. | **1 (Highest)** | Ingest quantitative data from **OpenLandMap** (for resolution) and **SoilGrids** (for variable breadth). Target SOC, CEC, Bulk Density, AWC, and Depth to Bedrock. |
| **Topography** | **Major Gap.** The system only has descriptive elevation ranges. It lacks slope, aspect, and key indices like TWI and TPI. | **2 (High)** | Derive Slope, Aspect, TPI, and TWI from the existing SRTM DEM. These are computationally intensive but critically important for microclimate and soil moisture. |
| **Microclimate** | **Medium Gap.** The species-level BIO variables are good, but the system lacks key *derived* microclimate variables. | **3 (Medium)** | Derive **Frost-Free Days** and **Growing Degree Days (GDD)**. Ingest **PET** from TerraClimate to calculate an aridity index. |
| **Disturbance / Land Use** | **Major Gap.** The database has no explicit fields for fire history, land use history, or human pressure. | **4 (Medium)** | Ingest **MODIS Fire** data (for fire frequency), **Hansen** data (for time since disturbance), and the **Human Influence Index**. This provides crucial context for restoration success. |
| **Hydrology** | **Major Gap.** No variables for distance to water, flood risk, or stream order. | **5 (Medium)** | Derive **Distance to Water** from the JRC Global Surface Water dataset. Use **HydroSHEDS** to derive stream order. This is essential for modeling riparian species. |
| **Functional Traits** | **Minor Gap.** A good foundation exists, but it's missing key, quantifiable traits for restoration goals (e.g., `max_rooting_depth`, `specific_leaf_area`). | **6 (Low)** | Augment the existing trait data by systematically querying and ingesting data from **TRY**, **BIEN**, and especially **GRooT** for root traits. |

**Overall Conclusion:** Treekipedia has a strong foundation in biogeography and basic climate. The most significant and impactful next step would be to build out a comprehensive, quantitative understanding of the **soil** and **topography** of a site. These two categories have the largest gaps and offer the greatest potential for improving the accuracy and ecological relevance of the LEAF™ species recommendation engine.
