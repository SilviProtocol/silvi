# SAFE-B Engine: Data & Infrastructure Strategy

**Document:** `SAFEB_DATA_AND_INFRA_STRATEGY.md`
**Author:** Gemini AI Research Coordinator
**Version:** 1.0
**Date:** 2026-01-21

## 1. Introduction

This document provides a complete data sourcing and infrastructure plan for building and deploying the **SAFE-B Recommendation Engine** as outlined in `Gemini_version.md`.

The strategy is guided by two core principles:
1.  **Data Completeness:** Systematically leverage Treekipedia's existing assets and fill critical gaps with best-in-class global datasets.
2.  **Financial Affordability:** Design a hybrid cloud/local architecture that minimizes cost at every stage of the data lifecycle—from processing to model training to serving predictions.

---

## 2. Data Audit and Acquisition Plan

This section maps the data requirements for each component of the SAFE-B score to Treekipedia's existing assets and provides a clear acquisition plan for any gaps.

### 2.1. Existing Data Assets for SAFE-B

Your project already possesses a rich foundation of data that can immediately power key components of the recommendation engine.

| SAFE-B Component | Existing Treekipedia Assets |
| :--- | :--- |
| **Suitability (S)** | <ul><li>**Species Occurrences:** 89M records in 5.3M geohash tiles (from GBIF).</li><li>**Base Elevation:** SRTM Digital Elevation Model (DEM) is already in use.</li></ul> |
| **Adaptability (A)** | <ul><li>**Basic Traits:** The species schema contains qualitative fields like `tolerances` and `growth_form`.</li></ul> |
| **Functionality (F)** | <ul><li>**Ecosystem Groups:** The `functional_ecosystem_groups` field is populated for 71% of species.</li><li>**Biotic Interactions:** `Globi_` prefixed fields provide a starting point for food web analysis.</li></ul> |
| **Externality (E)** | <ul><li>**Native Status:** Authoritative `wcvp_native` and `wcvp_introduced` data is integrated.</li><li>**Ecoregions:** 847 WWF Ecoregion polygons are integrated.</li><li>**Commercial Status:** `comercialspecies_lower` flag exists.</li></ul> |
| **Biogeography (B)** | <ul><li>**Core Occurrence Data:** The geohashed GBIF data is the foundation for calculating local abundance, distribution, and proximity.</li></ul> |

### 2.2. Missing Data & Acquisition Strategy

The following table identifies critical data gaps and the most direct and cost-effective way to acquire them, leveraging the findings from our research sprint.

| SAFE-B Component | Missing Data | Acquisition Method & Source (Cost-Effective) |
| :--- | :--- | :--- |
| **Suitability (S)** | **Quantitative Environmental Grids:** <ul><li>Soil properties (SOC, CEC, pH, AWC, etc.)</li><li>Derived Topography (Slope, Aspect, TWI)</li><li>Microclimate (Bioclim variables, GDD)</li></ul> | **Google Earth Engine (GEE).** These are all available as pre-built, analysis-ready assets. <ul><li>**Soil:** OpenLandMap / SoilGrids</li><li>**Topography:** Derive from SRTM DEM in GEE</li><li>**Climate:** CHELSA / WorldClim / TerraClimate</li></ul> |
| **Adaptability (A)** | **Quantitative Functional Traits:** <ul><li>Max Rooting Depth</li><li>Wood Density</li><li>Specific Leaf Area (SLA)</li></ul> | **API/Scripted Query of Trait Databases.** <ul><li>**GRooT:** For all root traits.</li><li>**TRY:** For leaf and stem traits.</li></ul> This is a local data harvesting and integration task. |
| **Externality (E)** | **Disturbance & Land Use History:** <ul><li>Fire History (Frequency, Time Since)</li><li>Deforestation History (Time Since)</li><li>Human Pressure Index</li><li>Historical Land Use</li></ul> | **Google Earth Engine (GEE).** <ul><li>**Fire:** MODIS Burned Area (`MCD64A1`)</li><li>**Deforestation:** Hansen Global Forest Change</li><li>**Pressure:** Human Influence Index (HII)</li><li>**Land Use:** ESA WorldCover / HYDE</li></ul> |
| **Biogeography (B)** | **Zone Connectivity Graph:** A pre-computed table of which ecoregions are adjacent to each other. | **Local PostGIS Analysis.** Implement the `unified-zone-schema.md` plan by running a one-time spatial join script on the existing ecoregion geometries in your PostGIS database. |

---

## 3. Financially Affordable Infrastructure Plan

This plan outlines a hybrid-cloud architecture designed to maximize computational power while minimizing cost by assigning each task to the most appropriate environment.

### Stage 1: Data ETL (Extract, Transform, Load)
**Environment:** **Google Earth Engine (GEE)**
**Principle:** *Do large-scale raster processing where the data lives.* GEE's parallel processing capabilities are free for non-commercial use and eliminate the need to download and process terabytes of data.

**Workflow:**
1.  Develop GEE scripts to take each required global dataset (e.g., SoilGrids pH, CHELSA temperature, Hansen forest loss).
2.  For each dataset, run a `reduceResolution` or `reduceRegions` job to calculate the average value for each of Treekipedia's geohash tiles.
3.  **Export the resulting `(geohash, value)` tables directly to a Google Cloud Storage (GCS) bucket.** This is efficient and extremely cheap.

*   **Estimated Cost:** **Near-zero.** GEE computation is free. GCS storage for the resulting feature tables will be a few dollars per month.

### Stage 2: Model Training
**Environment:** **Local Machine (for development) & Google Vertex AI (for production)**
**Principle:** *Rent, don't own, heavy compute.* Develop locally on small data samples for free, then pay only for the few hours needed for the final training run on the full dataset.

**Workflow:**
1.  **Local Development:** A data scientist downloads a small subset of the feature data from GCS (e.g., for a single ecoregion). They use this to write and debug the model training script (e.g., for the LightGBM `Explainable Suitability Score`) on their laptop.
2.  **Cloud Training:** When the script is ready, use **Vertex AI Training**.
    *   Submit a custom training job.
    *   The job automatically spins up a powerful machine, reads the *full* dataset from GCS, trains the final model, and saves the resulting model artifact back to GCS.
    *   The machine then spins down automatically. You only pay for the time it was running.

*   **Estimated Cost:** **Minimal.** A single training run on Vertex AI might cost **$5 - $20**, depending on machine type and duration. This is vastly cheaper than purchasing and maintaining a dedicated local machine with equivalent power.

### Stage 3: Serving Predictions
**Environment:** **Self-Hosted Cloud VM (e.g., DigitalOcean, Hetzner, or a Google Cloud VM)**
**Principle:** *Use open-source and self-hosted solutions for serving to avoid expensive managed service fees.*

**Workflow:**
1.  **Database:** Continue using your existing cloud VM with PostgreSQL. **Install the `pgvector` extension** (it's free). This turns your existing database into a powerful vector database, avoiding the need for a costly separate service like Pinecone.
2.  **Feature Store:** Load the processed environmental features from GCS into a table in your PostgreSQL database, indexed by geohash.
3.  **Model Deployment:** The trained model artifact (e.g., `model.lgb`) is downloaded from GCS to the API server on the same VM.
4.  **Prediction Flow:**
    *   A request hits the Node.js API with a lat/lon.
    *   The API queries PostGIS to get the geohash and its pre-computed features (soil, climate, etc.).
    *   The model, loaded in memory, makes a prediction using these features.
    *   The API performs the final SAFE-B score calculation and returns the JSON response.

*   **Estimated Cost:** **Minimal incremental cost.** The primary cost is the existing cloud VM. `pgvector` is a free and open-source extension.

### Stage 4: Knowledge Gap Filling (AI-Powered Insights)
**Environment:** **Local Machine or cheap, preemptible Cloud VM**
**Principle:** *Use LLMs as an offline, batch-processing tool, not a real-time dependency.*

**Workflow:**
1.  **Task Queue:** Use a simple table in your existing PostgreSQL database to manage a queue of research tasks (e.g., "Find soil preferences for *Quercus alba*").
2.  **Batch Processing:** A simple Python script runs periodically (e.g., as a cron job). It pulls tasks from the queue, formats them into prompts, and sends them to a cost-effective LLM API (e.g., **Google's Gemini API**).
3.  **Store Insights:** The structured JSON output from the LLM is saved as "insights" in your database, following the `TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md`.

*   **Estimated Cost:** **Near-zero.** This workflow can be run on an existing machine. The Google Gemini API has a generous free tier and is very low-cost for text-based tasks, likely falling within free usage limits for this kind of focused, non-real-time work.

By following this hybrid strategy, Treekipedia can build a world-class, AI-powered recommendation engine on a startup-friendly budget.
