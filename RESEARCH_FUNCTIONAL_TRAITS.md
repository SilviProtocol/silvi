# RESEARCH: Functional Trait Databases for Restoration

This document provides an overview of major plant functional trait databases, with a focus on traits relevant to ecological restoration, such as drought tolerance, erosion control, and flood tolerance. It covers database access, key traits, and recommendations for integration into the Treekipedia platform.

---

## 1. The Role of Functional Traits in Restoration

Functional traits are features of an organism that influence its growth, survival, and reproduction (its "function" in an ecosystem). In the context of species selection for restoration, using a functional trait-based approach moves beyond simple species-site matching. It allows for the selection of a diverse portfolio of species that can perform specific ecological roles and build resilient ecosystems.

For example, instead of just choosing "native species," one can choose a combination of:
-   Drought-tolerant species with deep roots for resilience.
-   Fast-growing species with high leaf-litter production to build soil organic matter.
-   Nitrogen-fixing species to improve soil fertility.
-   Species with fibrous surface roots for erosion control.

---

## 2. Major Plant Trait Databases

Several large, collaborative efforts have aggregated plant trait data from thousands of studies into unified databases.

### 2.1. Key Global Databases

| Database | Description | Trait Coverage | Access Method | Treekipedia Relevance |
| --- | --- | --- | --- | --- |
| **TRY Plant Trait Database** | The largest and most comprehensive global plant trait database. A collaboration of thousands of scientists. | **Massive.** Version 6 contains over 2,600 unique traits, covering everything from leaf chemistry to wood density to regeneration traits. | Data is open access. Users must register and can download data via a "Data Explorer" on the website or use the `tryr` R package. | **Highest.** The most comprehensive single source for a wide variety of traits. The sheer number of traits can be overwhelming. |
| **BIEN (Botanical Information and Ecology Network)** | A database focused on integrating plant distribution and trait data for the Western Hemisphere. | Good coverage for key "plant economic spectrum" traits. The full Open Traits Network lists 53 traits from BIEN. | Data can be queried via the `BIEN` R package. Primary data access is limited to the working group, but derived products are public. | **High.** Strong for the Americas. The R package provides a direct and scriptable way to query data, which is ideal for systematic integration. |
| **GRooT (Global Root Trait Database)** | A specialized database focused exclusively on root traits. | **The definitive source for root data.** Contains 38 root traits, including maximum rooting depth, root nitrogen content, and specific root length. | Data is available via GitHub, including CSV files and an R script for analysis. | **Critical.** Root traits are fundamental to drought tolerance and erosion control, yet are under-represented in other databases. This is a must-have dataset. |

### 2.2. Access Strategy

A federated approach is recommended:
1.  Use **TRY** as the foundational source for a broad range of leaf, stem, and reproductive traits.
2.  Supplement with **BIEN** for its excellent, clean data, especially for American species.
3.  Use **GRooT** as the primary source for all root-related traits.

---

## 3. Key Functional Traits for Restoration

The following traits, available in the databases above, are particularly relevant for a restoration-focused species selection tool like Treekipedia.

### 3.1. Traits for Drought Tolerance & Water Management

| Trait | Description | Ecological Significance | Potential Database(s) |
| --- | --- | --- | --- |
| **Maximum Rooting Depth** | The deepest soil layer reached by the plant's roots. | The single most important trait for accessing deep soil water and surviving drought. | **GRooT**, TRY |
| **Specific Leaf Area (SLA)** | The ratio of leaf area to dry mass. | Low SLA (thick, dense leaves) is associated with slower growth and greater tolerance to drought and stress. | TRY, BIEN |
| **Wood Density** | The dry mass per unit volume of stem wood. | High wood density is linked to slower growth, longer lifespan, and greater resistance to drought-induced embolism. | TRY, BIEN |

### 3.2. Traits for Erosion Control & Soil Stabilization

| Trait | Description | Ecological Significance | Potential Database(s) |
| --- | --- | --- | --- |
| **Root System Architecture** | Qualitative description (e.g., taproot, fibrous, rhizomatous). | Fibrous and rhizomatous (spreading) root systems are most effective at binding surface soil to prevent erosion. | GRooT, TRY (less common) |
| **Specific Root Length (SRL)** | The ratio of root length to dry mass. | High SRL (many fine roots for a given mass) indicates a strategy for efficient soil exploration and can contribute to binding soil aggregates. | **GRooT** |
| **Growth Form** | Categorical (e.g., tree, shrub, grass). | Low-growing, spreading shrubs and grasses are often most effective for surface erosion control. | BIEN, TRY |

### 3.3. Traits for Soil Health & Nutrient Cycling

| Trait | Description | Ecological Significance | Potential Database(s) |
| --- | --- | --- | --- |
| **Nitrogen Fixation** | The ability to form a symbiosis with nitrogen-fixing bacteria (e.g., in root nodules). | Enriches the soil with nitrogen, a key limiting nutrient. Crucial for kick-starting ecological succession on degraded sites. | TRY (as a categorical trait) |
| **Leaf Nitrogen Content** | The concentration of nitrogen in leaf tissue. | High leaf nitrogen is associated with faster decomposition and nutrient cycling, enriching the topsoil. | TRY, BIEN |

---

## 4. Implementation Recommendations for Treekipedia

Functional traits should not be used as simple filters. Instead, they should be integrated into the LEAF™ engine as a "suitability" or "ecosystem service" scoring modifier.

**Phase 1: Ingest Core "Economic Spectrum" and Root Traits**

1.  **Harvest Trait Data:**
    -   **Action:** Develop a set of scripts (likely in R) to query the BIEN, TRY, and GRooT databases for a target list of species and traits. The primary goal is to populate the Treekipedia species table with values for:
        -   `max_rooting_depth` (from GRooT)
        -   `specific_leaf_area` (from TRY/BIEN)
        -   `wood_density` (from TRY/BIEN)
        -   `nitrogen_fixation_type` (from TRY)
    -   Store the mean trait value for each species. It's also important to store the number of observations to have a measure of confidence.

**Phase 2: Integrate Traits into LEAF™ Scoring**

2.  **Create Trait-Based Suitability Scores:**
    -   **Action:** Modify the LEAF™ engine to accept "restoration goals" as input parameters.
    -   **Integration Examples:**
        -   **If `goal=drought_resilience`:** The engine would give a score bonus to species with `max_rooting_depth` > X meters or `wood_density` > Y g/cm³.
        -   **If `goal=erosion_control`:** The engine would give a bonus to species with known fibrous/rhizomatous root systems or high `specific_root_length`.
        -   **If `goal=soil_building`:** The engine would prioritize species where `nitrogen_fixation_type = symbiotic`.

**Phase 3: UI/UX for Trait-Based Discovery**

3.  **Expose Traits on Species Pages:**
    -   **Action:** Create a new "Functional Traits" section on the species detail pages to display the ingested trait data, helping users understand *why* a species is being recommended.
    -   **Action:** Add filters to the main search/discovery interface allowing users to search for species with specific traits (e.g., "Show me all nitrogen-fixing trees native to this ecoregion").

By integrating functional trait data, Treekipedia can provide recommendations that are not only adapted to the site's environment but are also tailored to achieve specific ecological restoration outcomes.
