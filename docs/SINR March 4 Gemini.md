# SINR March 4 Gemini: The Ultimate Ecological Intelligence Engine
**Date:** March 4, 2026
**Objective:** Evolve SINR from a pixel-level species predictor into a globally auditable, landscape-scale restoration and carbon MRV platform.

## 1. The Core Paradigm
We are moving from evaluating **isolated pixels (IID)** to evaluating **interdependent landscapes**. However, we must adhere to the *Codex* constraint: **Point-system first, area-system on top.** We will *not* pretrain a massive new foundation model from scratch. Instead, we will use frozen foundation embeddings (AlphaEarth) and route them through highly specialized, physics-aware neural heads.

The system will strictly separate its intelligence into three operational questions:
1. **What is growing there now?** (Current State & Degradation)
2. **What can grow there?** (Biophysical Suitability)
3. **What should we grow there?** (Strategy-Constrained Spatial Optimization)

---

## 2. The "Best System" Target Architecture
This is the end-state architecture that merges deep learning with biological constraints to achieve IPCC Tier-3 MRV compliance.

*   **Layer A: Data Fabric (Frozen Foundations)**
    *   AlphaEarth (64-D, 8-year temporal stack).
    *   Minimal but critical additions: MERIT HAND (Riparian), SRTM/GLO-30 (Erosion/Slope), JRC Forest Type, OpenLandMap Soils.
*   **Layer B: The Land State Engine**
    *   A classification head explicitly determining *Disturbance Status*, *Successional Stage*, and *Restoration Readiness* before any species are recommended. This prevents recommending climax species on freshly bulldozed dirt.
*   **Layer C: Spatio-Temporal Inference (The Spatial GNN + L-TAE)**
    *   Instead of evaluating pixels blindly, the engine evaluates grid-chunks (e.g., 100x100 pixels) using a Spatial Graph Neural Network (GNN). Edges are defined by topography (water flows downhill) and proximity to intact seed sources. 
    *   The L-TAE (Lightweight Temporal Attention Encoder) reads the 8-year history to project the baseline (what happens if we do nothing).
*   **Layer D: Differentiable Allometry (Carbon Head)**
    *   Instead of a black-box MLP predicting AGB, the model outputs species probabilities ($\vec{p}$) and multiplies them by a frozen tensor of **Species Wood Densities ($\rho$)**. It pushes this through a differentiable Chave et al. (2014) equation. This guarantees Carbon VVBs (Verra auditors) can mathematically audit the carbon curve.
*   **Layer E: Successional Simulator & Spatial Solver (Area Planner)**
    *   An autoregressive loop that simulates time. (e.g., Run model $\rightarrow$ recommend pioneer species $\rightarrow$ mathematically simulate pioneer canopy altering the soil/shade $\rightarrow$ re-run model to output climax understory).
    *   Outputs a prescriptive GeoTIFF: "Plant Species A on these 1,200 riparian pixels; Plant Species B on these 800 ridge pixels to maximize ROI."

---

## 3. Short-Term Execution (Quick Wins & Data Acquisitions)
*Timeframe: Next 1–4 Weeks*

These are the immediate data grabs and engineering shifts that catapult functionality without requiring a 2-month GPU training cycle.

### A. Quick Data Acquisitions (High ROI, Low Overhead)
1.  **Global Wood Density DB + GLOWCAD:** Download and JOIN this to the Treekipedia species taxonomy. *Why:* Unlocks immediate deterministic carbon modeling based on current SINR v2.2 outputs, bypassing the need for the neural carbon head temporarily.
2.  **ESA WorldCover + JRC Water + MERIT HAND:** Extract these via GEE. *Why:* Immediately enables the identification of roads/impervious surfaces (preventing tree recommendations on asphalt) and identifies riparian zones.
3.  **ESA CCI Biomass v6.0 (2007-2022):** Download from CEDA. *Why:* This is the "ground truth" target for the future Carbon Head. 

### B. Engineering Quick Wins
1.  **Fix the GEDI Bug:** Immediately patch `unified_gee_sampler_v3.py` so it queries explicit GEDI metric images rather than mosaicking the collection (which mixes height and density metrics).
2.  **Deploy Land State Engine v1 (Heuristic):** Before training a neural Land State head, implement a deterministic ruleset in Python (using Hansen loss + Dynamic World + JRC TMF) to flag pixels as *Intact, Degraded, or Deforested*. Use this to gate SAFE-B recommendations.
3.  **The 5-Part API Contract:** Update the backend so every point queried returns 5 distinct JSON objects: `[Current State, Suitability, Strategy Recommendations, Projections, Confidence/Risk]`. 

---

## 4. Long-Term Strategy (TB-Scale & Pipeline Evolution)
*Timeframe: Next 2–6 Months*

To move from point-based JSONs to landscape-scale GeoTIFF prescriptions, the data pipeline and model architecture must evolve.

### A. TB-Scale Data Acquisition & Pipeline Transformation
1.  **Move from GEE Point-Sampling to Zarr/Xarray Chunks:** 
    *   *The Problem:* GEE `sampleRegions` is bottlenecking at 2,000 points/task and fails frequently. It cannot train a Spatial GNN because it samples scattered, disconnected points.
    *   *The Solution:* Transition the pipeline to download contiguous bounding boxes (e.g., 10x10km tiles) as multi-band NetCDFs/Zarr arrays. Store these in cloud buckets. This provides the spatial context required for graph networks and topographic algorithms.
2.  **Integrate Radar/LiDAR Heavyweights (2026/2027 prep):** 
    *   Build ingestion pipelines for NISAR (L-band SAR) and prepare for ESA BIOMASS (P-band SAR). P-band is the only wavelength that penetrates dense tropical canopies to measure true woody biomass.

### B. Model Training Pipeline & Architecture
1.  **Unified Multi-Task Training on A100s:**
    *   Assemble the LEFT JOINed unified training table in BigQuery, preserving missing carbon/GEDI values with `-9999` sentinels.
    *   Train the shared `ResidualFCNet` trunk with specialized heads: Species (BCE Loss), Land State (Cross Entropy), and Carbon (Uncertainty-weighted Huber Loss).
2.  **Implement Differentiable Allometry in PyTorch:**
    *   Code the custom PyTorch loss function where the Carbon Head doesn't just guess AGB, but computes it as $f(\text{predicted species}, \text{wood density}, \text{canopy height})$.
3.  **Counterfactual Baseline Forecasting (L-TAE):**
    *   Train the L-TAE to predict the *next* 5 years of environmental features based on the *past* 8 years. Run the Carbon Head on this forecast to generate the "Baseline Scenario" (what happens if the landowner does nothing). This automates carbon credit Additionality proving.
4.  **Area Planner (The Capstone):**
    *   Build a spatial optimization script (using SciPy or integer linear programming). The user uploads a polygon and a budget. The script tiles the polygon, runs SINR on every pixel, and mathematically solves for the exact spatial distribution of species that maximizes Carbon + Biodiversity while minimizing Erosion.
    *   *Output:* A downloadable, prescriptive GeoTIFF for drone seeding or field crews.