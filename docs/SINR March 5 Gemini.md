# SINR March 5 Codex: The Master Audit & Landscape Strategy
**Date:** March 5, 2026
**Author:** Gemini (Expert Machine Learning Auditor & Technical Supervisor)
**Status:** Canonical Source of Truth for SINR v3

---

## 1. Executive Summary & Product Vision
The Species Intelligence Neural Representation (SINR) v3 is Treekipedia’s evolution from a pixel-level species predictor into a **globally auditable, landscape-scale restoration and carbon MRV platform.** 

The intention is to solve the fatal flaw of current carbon MRV systems (species-blind allometry) by identifying exact tree species at high resolution, thereby unlocking species-specific wood densities ($\rho$) for highly accurate carbon sequestration modeling. 

**The Current State:** The data acquisition phase was a massive success (extracting 15M+ new GBIF records, 13.9M HILDA+ trajectories, and 12.9M carbon samples). However, the **data assembly and model training pipelines are critically compromised** by temporal Cartesian joins, train/val data leakage, and GEE `.mosaic()` data corruption. Furthermore, previous architectural documents contained severe AI hallucinations. 

This document serves as the unvarnished audit, the source of truth for all fixes, and the architectural roadmap for building the ultimate ecosystem engine.

---

## 2. Evolution: From v2.2 to v3
**SINR v2.2** was a successful proof-of-concept: a 9.7M parameter `ResidualFCNet` taking a single temporal snapshot (64-D AlphaEarth + 56 environmental variables) to predict species probabilities.
**SINR v3** scales this drastically:
1.  **Data Expansion:** Expanding from ~8M rows to over ~32M rows, incorporating 15.25M new GBIF occurrences and a massive backfill of existing points.
2.  **Temporal Depth:** Replacing the single AlphaEarth snapshot with an 8-year temporal stack (2017-2024), processed via a Lightweight Temporal Attention Encoder (L-TAE).
3.  **Land-Use History:** Integrating HILDA+ (1960-2020) to track historical land-use changes.
4.  **Carbon Multi-Tasking:** Adding a secondary regression head to predict AGB, NPP, and SOC simultaneously with species classification.

---

## 3. The Technical Audit: Bugs, Gaps, and Data Integrity Failures
Despite the successful data pull, the consolidation pipeline is broken. Here is the exact proof and impact of the critical bugs.

### 3.1. The Cartesian Explosion (Temporal Destruction)
*   **Location:** `orchestrator/consolidate_bq_v2.py` (Lines 221-230)
*   **The Bug:** To rejoin species labels to the backfill features, the script uses an `INNER JOIN` against an `occ_dedup` subquery. This subquery pulls `lat4` and `lon4` but **drops `observation_year`**. 
*   **The Impact:** Mathematical Cartesian explosion. The `sinr_v3_unified_v2` table bloated to **32,323,081 rows**, yet only contains **13,171,915 unique pixels**. If a pixel had 5 species recorded in 5 different decades, this blind join forcefully maps *all 5 species* to a single remote-sensing snapshot. The temporal integrity of the backfill data has been destroyed.

### 3.2. Target Leakage in the Z-Score Normalizer
*   **Location:** `orchestrator/train_sinr_v3.py` (Lines 578-581)
*   **The Bug:** The script calculates Z-Score standardizations (`mean(axis=0)` and `std(axis=0)`) across the **entire, unfiltered parquet dataframe**.
*   **The Impact:** The 5% validation hold-out (`VAL_FRACTION = 0.05`) happens *after* this step. By standardizing the features using the global mean, the validation set’s statistical distribution is mathematically leaked into the training set parameters, guaranteeing artificially inflated validation metrics.

### 3.3. The GEDI `.mosaic()` Data Corruption
*   **Location:** `orchestrator/unified_gee_sampler_v3.py` (Lines 211-212)
*   **The Bug:** The script calls `.mosaic()` on the `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` ImageCollection. 
*   **The Impact:** This collection does not represent time; it represents *different metrics* (rh98, fhd, agbd) stored as separate images. `.mosaic()` violently squashes non-compatible metrics together depending on internal GEE sort orders. `train_sinr_v3.py` is currently blindly routing these corrupted `gedi_canopy_height_m` variables straight into the neural network. (Note: this was patched in `carbon_gee_sampler.py`, but not in the unified sampler).

---

## 4. The Hallucination & History Report (Fact-Checking Claude)
I have deeply cross-referenced the claims in the "SINR March 4 - Claude" document against the complete historical project files (like `GO.md`, `ACTIVE.md`, and the `CHANGELOG`). Here is the nuanced reality of what was hallucinated versus what was actually planned but left unfinished.

1.  **"DeepMind Natural Forests Dataset"**
    *   *The Reality:* **NOT a hallucination.** This is a real dataset (Neumann et al., 2025) that was explicitly planned and integrated into the `SINR v2.1` architecture. The EE asset path `projects/nature-trace/assets/forest_typology/...` is the official Google Earth Engine path for this specific DeepMind paper.
2.  **"GRIIS Multilevel Invasiveness Embeddings"**
    *   *The Reality:* **A partial hallucination (conflation).** Expanding `is_introduced` to a 6-level categorical scale (Native, Naturalized, Invasive, etc.) *was* explicitly planned in `GO.md`. However, the "8D matrix embedding" claim is a hallucination. The previous agent conflated the GRIIS plan with a failed architectural experiment in `SINR v2.1` where the inference gate was expanded to 8 dimensions (which caused the model to regress and was rolled back).
3.  **"HILDA Transition Gate (`hilda_transition`)"**
    *   *The Reality:* **NOT a hallucination.** This was a heavily documented architectural upgrade intended for `SINR v3.0`. The plan was to pass `hilda_transition_count` (historical land-use changes) into a new FiLM gate. If the land had transitioned (e.g., Forest -> Cropland), the gate would "close" and ignore modern satellite embeddings that no longer matched the historical observation. It simply hasn't been coded into `train_sinr_v3.py` yet.

---

## 5. The Immediate Fixes (Code Patches)
To unblock v3 training, these patches must be applied immediately.

### Patch 1: Fix the Cartesian Join (`consolidate_bq_v2.py`)
Drop `sinr_v3_unified_v2`. The previous developer intentionally dropped the temporal constraint from the SQL `JOIN` because "backfill observation_year doesn't reliably match occurrences.year." This deliberate workaround caused the Cartesian catastrophe. We must rewrite the `occ_dedup` subquery to mandate temporal matching:
```sql
INNER JOIN (
    SELECT DISTINCT ROUND(decimalLatitude, 4) as lat4, ROUND(decimalLongitude, 4) as lon4, 
           observation_year, taxon_id
    FROM `{BQ_PROJECT}.{BQ_DATASET}.occurrences`
    WHERE taxon_id IS NOT NULL
) occ_dedup
    ON ROUND(b.latitude, 4) = occ_dedup.lat4
    AND ROUND(b.longitude, 4) = occ_dedup.lon4
    AND b.observation_year = occ_dedup.observation_year -- CRITICAL FIX
```

### Patch 2: Fix Train/Val Leakage (`train_sinr_v3.py`)
Move the Z-score normalizer to execute *after* the validation split. 
```python
# Create masks FIRST
np.random.seed(42)
val_mask = np.random.rand(len(df)) < VAL_FRACTION
train_mask = ~val_mask

# Fit scaler ONLY on train data
mean = continuous_data[train_mask].mean(axis=0)
std = continuous_data[train_mask].std(axis=0)
std[std < 1e-8] = 1.0

# Apply to all
continuous_data = (continuous_data - mean) / std
```

### Patch 3: Quarantine GEDI
Until `unified_gee_sampler_v3.py` is re-run with explicit asset IDs (`GEDI_RH98_IMG`), drop `gedi_canopy_height_m` and `gedi_foliage_height_div` from the `ENV_CONTINUOUS_COLS` in `train_sinr_v3.py` so the model doesn't learn corrupted spatial priors.

---

## 6. The Gemini Landscape Architecture (The Long-Term Play)
Once the point-level pipeline is debugged and v3 is trained, the architecture must evolve to evaluate **spatially interdependent landscapes** (polygons) rather than isolated pixels.

1.  **Spatial GNNs for Topo-Hydrological Propagation:**
    *   Transition from a purely independent `ResidualFCNet` to a Spatial Graph Neural Network (GNN).
    *   Construct graph edges using `MERIT/Hydro` (hnd/upa) so information propagates down water gradients and radially from intact `JRC_TMF` forests. This allows SINR to natively highlight riparian corridors and erosion-prone slopes based on landscape context.
2.  **Differentiable Allometry for IPCC Tier-3 Carbon Integrity:**
    *   Instead of an abstract MLP guessing AGB, hardcode physical scaling laws into PyTorch.
    *   Multiply the model's species probability output ($\vec{p}$) by a frozen tensor of **Species Wood Densities ($\rho$)** (joined from the Global Wood Density DB).
    *   Pass this through a differentiable Chave et al. (2014) equation layer: $\mathbb{E}[AGB] = \sum p_i \cdot 0.0673(\rho_i \cdot D^2 \cdot H)^{0.976}$. This guarantees VVBs (carbon auditors) can mathematically audit the carbon curve.
3.  **Autoregressive Successional Trajectory Simulator:**
    *   Implement a Markovian loop. Run SINR to recommend pioneer species $\rightarrow$ mathematically mutate the input environmental vector to simulate a pioneer canopy (increase soil carbon, decrease VPD) $\rightarrow$ re-run SINR to output the climax understory. This generates a 20-year phased planting roadmap.
4.  **Counterfactual Baseline Forecasting (L-TAE):**
    *   Train the L-TAE autoregressively to forecast the *next* 5 years of environmental features based on the *past* 8 years of AlphaEarth data. Run the Carbon Head on this forecast to generate the "Baseline Scenario," automating Additionality proving for project developers.
5.  **Constrained Spatial Optimization Solver:**
    *   Wrap the SINR/SAFE-B outputs in a spatial solver (e.g., SciPy). The user uploads a polygon and a budget constraint. The solver mathematically maximizes ROI across the grid, outputting a prescriptive GeoTIFF planting map for field crews.