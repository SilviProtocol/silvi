# SINR March 8 Gemini Audit Report
**Date**: March 8, 2026
**Subject**: Extreme Detail-Oriented Audit of SINR v3 Experiment History, Architecture, and Pipeline
**Objective**: Identify critical flaws preventing model improvement, diagnose evaluation blindness, and recommend cutting-edge architectural and algorithmic corrections.

---

## 1. Executive Summary

Despite numerous experiments and architectural tweaks, the SINR v3 model has plateaued because the core training mechanics and evaluation methodologies are fundamentally misaligned. 

The audit reveals three catastrophic flaws:
1. **Severe Evaluation Blindness**: The model is being benchmarked on a single spatial coordinate.
2. **False Handling of Class Imbalance**: The 50K row cap failed silently, and the `species_weights` implementation mathematically fails to solve the 415,050-to-1 class imbalance.
3. **Flawed Contrastive Background**: The canonical "background loss" is sampling from *known tree presences* instead of true random global coordinates.

This document breaks down exactly what went wrong in the codebase, equations, and data pipeline, and provides the path forward based on state-of-the-art Spatial Implicit Neural Representations (SINRs).

---

## 2. Core Diagnoses: Why the Model Isn't Improving

### A. The 50K Hard Cap Was a Silent No-Op
**The Intent:** Cap dominant species at 50,000 rows to prevent them from overwhelming the gradient (v2.2 behavior).
**The Reality:** The cap was implemented in `train_on_vm.py` *after* the data was partitioned into 1M-row shards. 
*   Because the dataset is randomly shuffled across 5 shards, no single species has >50k rows *in a single 1M-row shard*. 
*   **Result:** Zero rows were dropped. The data maintains a catastrophic imbalance ratio of **415,050 to 1**.

### B. The Sample Weighting Mechanism is Mathematically Flawed
**The Intent:** Apply frequency weighting `[0.25, 16.0]` to compensate for class imbalance.
**The Reality:** In `_compute_species_weighted_bce_loss`, the weight `w` scales the *entire sample loss* (both the single positive target and the 45,246 negative targets):
```python
per_sample = per_elem.mean(dim=1)  # Average BCE over all 45k classes
per_sample = per_sample * w        # Scaled by target species weight
```
*   **Mathematical Proof of Failure:** A rare species (weight 16.0) observed 1 time produces `16.0` units of gradient energy. A common species (weight 0.25) observed 415,000 times produces `103,750` units of gradient energy. The common species still dominates the gradients by a factor of ~6500x. 
*   Furthermore, weighting the *sample* means a rare species occurrence heavily pushes down the logits of *all other species*, distorting the assumed-negative space.

### C. Evaluation Blindness: The Single-Coordinate Benchmark
**The Reality:** We are evaluating a 45,000-class, globally operating implicit neural network based on its rank for a single *Pinus radiata* point in New Zealand (`GymPiPiPnCx50820-00`).
*   **The Problem:** Single-point inference is hyper-sensitive to initialization (seed variance), causing rank fluctuations of ~50 positions. 
*   **The Decoupling:** The reason "Val top-10 and benchmark rank are DECOUPLED" is because the validation set shares the exact same 415k-to-1 class imbalance as the training set. A model optimizing for Val Top-10 will simply predict the top 10 most common global species everywhere. 
*   **Conclusion:** We cannot trust ANY of the version rankings (v4, v8, v14) as true indicators of model generalization.

### D. The Tautological Background Loss
**The Reality:** In `train_on_vm.py`, the background loss selects random rows from the current training batch:
```python
bg_idx = np.random.randint(0, len(train_indices), len(batch_indices))
bg_batch = dataset.get_batch(bg_idx)
```
*   **The Problem:** True SINR models (Cole et al., 2023) sample uniform random spatial coordinates (e.g., oceans, deserts, cities) to teach the model where species *do not* exist. Our implementation samples locations where *other trees are already known to exist*, acting as a restricted negative sampler rather than a true spatial regularizer.

### E. Input/Output Covariate Shift at Inference
1. **Land State:** Trained with 10+ variables, but the input is zeroed out at inference. This violently shifts the internal activation distribution of the trunk.
2. **Phylo Input:** Zeroed out during the forward pass to prevent label leakage, meaning those parameters are dead weight.

---

## 3. Cutting-Edge Solutions (The "Top-Notch" Path Forward)

To resolve these issues without guessing, we must align our approach with the latest SDM/SINR research (e.g., ICLR 2024, NeurIPS 2024).

### Phase 1: Fix the Math and Evaluation (Immediate Action)

1. **Implement True Imbalance-Aware Loss (Zbinden et al., 2024):**
   Instead of sample weighting, implement class-specific weighting for the *negative* terms. Rare species should not be heavily penalized when they are the assumed-negative background for a common species. 
   *   *Action:* Modify the BCE loss so that the negative loss component for class $c$ is weighted by $w_{neg,c} \propto 1 / \text{freq}(c)$.

2. **Establish a Multi-Coordinate Benchmark:**
   Stop using the single NZ pine tree. 
   *   *Action:* Create a benchmark set of 1,000 diverse coordinates (stratified by species frequency and biome). Track Mean Reciprocal Rank (MRR) and Top-K recall. This is the *only* way to know if an architecture change worked.

3. **Global BigQuery Hard Cap:**
   *   *Action:* Execute a `QUALIFY ROW_NUMBER() OVER(PARTITION BY taxon_id ORDER BY RAND()) <= 50000` on the BigQuery table *before* exporting shards.

### Phase 2: Architectural Corrections

1. **Move Land State to an Auxiliary Target (Only):**
   If land state cannot be faithfully computed at inference, it *must not be an input*. 
   *   *Action:* Remove Branch 4 (Land State) from the forward pass. Keep the `aux_land_state_head` to predict it from the trunk. This provides the regularization benefit without the inference covariate shift.

2. **Move Phylogenetic Data to the Output Layer:**
   Instead of passing Phylo as an input (which causes leakage), use it to regularize the final output weights.
   *   *Action:* Implement a Phylogenetic Graph Laplacian Penalty. Force the output weights $W_i$ and $W_j$ of the final `Linear(384, 45247)` layer to be similar if species $i$ and $j$ are close in the OToL tree.

3. **Upgrade Location Encoding:**
   Sinusoidal lat/lon encoding (v14) creates artifacts at the poles and antimeridian because it doesn't respect spherical geometry.
   *   *Action:* Replace 40D independent sine waves with 3D Cartesian coordinates $(x,y,z)$ mapped to a **Spatial Hashgrid** (like Instant-NGP) or **Spherical Harmonics**.

4. **True Background Sampling:**
   *   *Action:* Pre-compute a "Global Background" shard consisting of 1 million uniformly random global coordinates (with their associated AlphaEarth and Env embeddings). During training, pull a fraction of the batch from this true background set and apply the `logsigmoid(-logits)` loss.

### Phase 3: SOTA Paradigm Shifts (ISPRS & NeurIPS 2024)

1. **ControlNet-Style Middle Fusion (Sat-SINR, 2024):**
   Currently, we use a simple scalar gate (`jrc_forest_type`) to blend Satellite and Environment. 
   *   *Action:* Inject the AlphaEarth embeddings into the middle of the MLP trunk using zero-initialized linear layers. This prevents the high-dimensional satellite data from destabilizing the spatial/environmental niche representations early in training.

2. **Language-Environment SINR (LE-SINR, 2024):**
   *   *Action:* Instead of predicting 45,247 independent logits, map the trunk output into a 384D shared latent space. Compute the dot product between this spatial latent vector and pre-computed 384D SentenceTransformer embeddings of the species' Wikipedia habitat descriptions. This enables zero-shot prediction for rare species that have text data but almost no spatial coordinates.

---

## 4. Conclusion

The model is not improving because it is mathematically tethered to the most frequent species, evaluated blindly on a single data point, and suffering from severe train/serve mismatch. 

**Next Steps**: Do not train v18 until the BigQuery hard cap is applied, the single-point benchmark is replaced with a 1,000-point MRR suite, and the Land State input branch is deleted in favor of an auxiliary-only target.