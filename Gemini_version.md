# Treekipedia Recommendation Engine: The Gemini Masterplan

**Document:** `Gemini_version.md`
**Author:** Gemini AI Research Coordinator
**Version:** 2.0
**Date:** 2026-01-21

## 1. Vision: The SAFE-B Score & The Prediction/Recommendation Framework

This document presents a new, unified masterplan for the Treekipedia species recommendation engine. It builds upon the project's existing strengths, incorporates the findings of a comprehensive environmental research sprint, and integrates the visionary concepts from Treekipedia's own architectural roadmaps.

The core of this masterplan is the **SAFE-B Score**, a next-generation, multi-layered scoring framework. It is designed to first **predict** scientifically valid options and then **recommend** contextually appropriate ones.

### Prediction vs. Recommendation

This framework makes a clear distinction between two fundamental questions:
1.  **Prediction (The "Can it live here?" question):** This is a purely scientific assessment of habitat suitability. It combines a species' environmental requirements with the physical characteristics of a location, now and in the future.
2.  **Recommendation (The "Should I plant it here?" question):** This is a prescriptive judgment that builds upon the scientific prediction. It layers on real-world context, including local biodiversity, project goals, and risk factors.

The SAFE-B score is a composite of five pillars, with a clear separation between prediction and recommendation:

---
**PREDICTION COMPONENTS (The Habitat Suitability Index - HSI)**
*   **S - Suitability:** Can this species grow well at this specific location *today*?
*   **A - Adaptability:** Will this species survive and thrive here *in the future*?

---
**RECOMMENDATION MODIFIERS (The Contextual Score)**
*   **F - Functionality:** What ecological *job* will this species perform?
*   **E - Externality:** What are the external *risks* and landscape context?
*   **B - Biogeography:** Is this species part of the local *biological neighborhood*?
---

The SAFE-B Score is not a replacement for the LEAF™ engine or the AlphaEarth vision; it is the unifying framework that orchestrates them into a single, coherent system.

---

## 2. The SAFE-B Score: A Deeper Dive

The SAFE-B Score is a composite score from -10 (Detrimental) to +10 (Highly Recommended), calculated from its five core components. The final score is the sum of the Prediction components (S+A) and the Recommendation modifiers (F+E+B).

---
### **PREDICTION: The Habitat Suitability Index (HSI)**
---

#### 2.1. **S** - Suitability (The Site-Species Match)
**Question:** *Can this species grow here?*
**Weight:** 35%

This is the foundational environmental matching component. It assesses the compatibility between a species' known ecological niche and the specific environmental conditions of a location. This component will have two sub-scores that can be weighted and combined:

1.  **The Explainable Suitability Score (ESS):**
    *   **Methodology:** Uses a powerful and interpretable machine learning model (e.g., **LightGBM** or **XGBoost**) trained on species occurrence data against a rich set of discrete environmental variables. This provides a highly accurate prediction with "explainability," allowing the user to see *why* a location is suitable (e.g., "Good match for soil pH and annual precipitation").
    *   **Input Variables:** The full suite of researched variables: Topography (Slope, Aspect, TWI), Soil (SOC, CEC, AWC), and Microclimate (Min Temp, Driest Month Precip, GDD).

2.  **The Vector Suitability Score (VSS):**
    *   **Methodology:** This is the implementation of the **AlphaEarth** vision. It uses a deep learning approach based on a 64-dimensional environmental embedding.
    *   **How it Works:** The 64-D vector for a target location is extracted. A vector database (`pgvector`) is then used to find the species "prototypes" with the highest **cosine similarity**, providing a powerful but less interpretable measure of environmental similarity.
    *   **Role:** The VSS is excellent at capturing complex, non-linear environmental interactions that discrete variables might miss.

**Final Suitability Score:** `(ESS_score * weight_explainable) + (VSS_score * weight_vector)`.

#### 2.2. **A** - Adaptability (The Future-Proofing Score)
**Question:** *Will this species survive and thrive in the future?*
**Weight:** 15%

This component assesses a species' resilience to future stressors, primarily climate change.

*   **Methodology:**
    1.  **Climate Change Match:** Compares the species' current climatic niche (from CHELSA) with future projected climate for the location (e.g., CMIP6 projections for 2050).
    2.  **Trait-Based Resilience:** Scores species based on key functional traits: high score for `max_rooting_depth` > 2m (drought tolerance) or thick bark (fire tolerance).

---
### **RECOMMENDATION: The Contextual Modifiers**
---

#### 2.3. **F** - Functionality (The Ecological Role Score)
**Question:** *What ecological job will this species perform?*
**Weight:** 20%

This component allows for **goal-oriented recommendations** by assessing a species' contribution to ecosystem structure, health, and food webs. It directly incorporates Treekipedia's existing data on ecological function groups and biotic interactions.

*   **Methodology:**
    1.  **Match to Ecosystem Typology:** Compares the species' known `functional_ecosystem_groups` (e.g., "Pioneer", "Canopy", "Understory", "Nitrogen-Fixer") with the needs of the target restoration site. A pioneer species would be up-weighted for a highly degraded site.
    2.  **Trophic Role Assessment (Food Web Foundation):**
        *   **Keystone Support:** Boosts species known to be foundational. A species that is `eatenBy` a large number of other organisms (from GloBI data) is a cornerstone of the food web.
        *   **Pollinator & Disperser Hub:** Boosts species that `pollinatedBy` or have a `hasDispersalVector` relationship with a diverse array of other species, enhancing overall biodiversity.
    3.  **User-Defined Goal Matching:** The user can select a "restoration goal," and the engine up-weights species with relevant traits:
        *   **Goal: "Erosion Control"** -> Boosts species with high `specific_root_length`.
        *   **Goal: "Build Soil Fertility"** -> Boosts species with the `Nitrogen-Fixing` functional group classification.

#### 2.4. **E** - Externality (The Context & Risk Score)
**Question:** *What are the external risks and contextual factors?*
**Weight:** 15% (can be a strong negative penalty)

This component acts as a critical "reality check," assessing risks and landscape context.

*   **Methodology:**
    1.  **Native Status:** This is the primary factor, using the `invasive-first-elimination` logic.
        *   **Invasive:** Applies a massive penalty.
        *   **Native:** Applies a significant score boost.
    2.  **Disturbance Context:** Penalizes species that are poorly adapted to the local disturbance regime (e.g., fire-intolerant species in a high fire-frequency zone).
    3.  **Human Context:** Penalizes commercial species to avoid greenwashing and penalizes wilderness species if planted in a high Human Footprint Index zone.

#### 2.5. **B** - Biogeography (The "Neighborhood" Score)
**Question:** *Is this species part of the local biological neighborhood?*
**Weight:** 10%

This new component directly addresses dispersal limitation and local adaptation. A species that is native to a country but only found 3,000km away is a riskier choice than a species found 10km away. This score is heavily based on the robust logic of the existing **LEAF™ Engine**.

*   **Methodology:**
    1.  **Local Abundance & Distribution:** Calculates a score based on the `occurrence_count` and `tile_count` within the target ecoregion and its adjacent ecoregions (determined via the `zone_connectivity` table). Higher density and wider distribution lead to a higher score.
    2.  **Proximity Bonus:** Calculates the distance from the target location to the nearest known occurrence of the species. This score is highest for species already present at the site and decays with distance, providing a strong bonus for local presence. This directly answers the question: "Is it already here or nearby?"

---

## 3. Unified Knowledge & Data Architecture

This masterplan fully embraces the **Insight-Based Knowledge Architecture** and the **Unified Zone Schema**.

1.  **Unified Zone Schema as the Foundation:** The proposed `treekipedia_zones` table is the perfect spatial foundation. All environmental raster data (Soil, Climate, Topography, Disturbance) will be pre-processed in GEE and their values will be aggregated and stored against these unified zones. This creates a single, consistent spatial framework for all queries.

2.  **Insight-Based Data Model:** The SAFE Score components map directly to the proposed "insight" model:
    *   A species' **Suitability** is determined by matching location insights with species preference insights (e.g., a `soil_ph` insight for a location is matched against a `ph_preference` insight for a species).
    *   A species' **Adaptability** score is derived from its `drought_tolerance_trait` insight.
    *   Its **Functionality** is derived from `nitrogen_fixation` or `pollinator_interaction` insights.
    *   Its **Externality** score is derived from `native_status` and `fire_tolerance` insights.

3.  **Hybrid Data Storage:** The SAFE engine will leverage the full hybrid architecture:
    *   **PostGIS:** The primary store for the `treekipedia_zones` and for executing fast spatial queries that underpin all components.
    *   **pgvector:** The dedicated engine for the AlphaEarth-based **Vector Suitability Score (VSS)**.
    *   **Graph Database (Apache AGE):** Used to query the `INTERACTS_WITH` relationships needed for the **Functionality** score.

## 4. Implementation Roadmap for the SAFE-B Engine

This is a phased plan to build the SAFE-B engine, delivering value at each step.

**Phase 1: SAFE-S (Suitability) - The Environmental Match Engine (3-4 Months)**
*   **Goal:** Implement the "Explainable Suitability Score (ESS)". This delivers the most-requested feature: true environmental matching.
*   **Actions:**
    1.  **Data Ingestion:** Ingest the Priority 1 & 2 variables from the research audit (Soil, Topography, Microclimate). Pre-process them in GEE and store them in the `treekipedia_zones` table.
    2.  **Model Training:** Train a LightGBM model on existing species occurrences against these new environmental variables to predict habitat suitability.
    3.  **API Development:** Create a new API endpoint `GET /api/v2/recommendations/safe` that returns a list of species ranked by their Suitability score for a given location.

**Phase 2: SAFE-E & SAFE-B (Externality & Biogeography) - Integrating Context (2-3 Months)**
*   **Goal:** Integrate the robust native status logic, disturbance context, and the new biogeographical proximity score.
*   **Actions:**
    1.  **Externality (E):** Implement the full `invasive-first-elimination` and `sub-country-clustering` algorithm for native status. Ingest the disturbance and human context layers (fire, land use, commercial flags).
    2.  **Biogeography (B):** Implement the local abundance/distribution score based on the LEAF™ engine's logic. Develop and add the "Proximity Bonus" score based on distance to the nearest known occurrence.
    3.  **API Update:** Update the SAFE score algorithm to apply the powerful boosts and penalties from these two essential contextual components.

**Phase 3: SAFE-F & SAFE-A (Functionality & Adaptability) - Goal-Oriented Recommendations (3 Months)**
*   **Goal:** Enable users to select species for specific restoration goals and future climates.
*   **Actions:**
    1.  **Trait Ingestion:** Systematically ingest quantitative functional trait data from GRooT and TRY, as well as the `functional_ecosystem_groups` Treekipedia already possesses.
    2.  **Climate Projections:** Ingest downscaled CMIP6 climate projection data for 2050.
    3.  **UI/API Update:** Add a `restoration_goal` parameter to the API and UI. Implement the scoring logic for the Functionality and Adaptability components.

**Phase 4: The Vector Engine (Ongoing)**
*   **Goal:** Implement the AlphaEarth-based "Vector Suitability Score (VSS)".
*   **Actions:** This is a parallel, long-term R&D effort, following the detailed `ALPHAEARTH_EXECUTABLE_PLAN.md`. Once mature, its score will be integrated as a second, powerful component of the main **Suitability** score, providing a deep-learning-based perspective alongside the explainable model.

By following this masterplan, Treekipedia can leverage its incredible data assets and forward-thinking architectural plans to create a species recommendation engine that is not only best-in-class but also a critical tool for global ecological restoration efforts.
