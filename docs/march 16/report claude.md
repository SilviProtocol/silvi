# SINR V4 Plantation-Conifer Benchmark Failure: Deep Diagnosis

**Date:** 2026-03-16
**Scope:** Independent investigation into why Pinus radiata remains poorly ranked at a canonical NZ plantation benchmark despite V4.1/V4.2 improvements
**Benchmark:** lat=-41.1516, lon=175.0997, year=2023, target=GymPiPiPnCx50820-00

---

## 1. Executive Diagnosis

The model is not learning "plantation-ness." It is learning "what species live in this climate zone at this coordinate" — which is the correct behavior for a species distribution model operating on the features and data it has been given. The failure is not a bug. It is a consequence of three compounding structural problems, listed in order of causal importance:

1. **The model has no mechanism to distinguish plantation from native forest.** The AE temporal embeddings encode land-cover appearance and change trajectories, but the training objective never asks "is this a plantation?" in a way that connects to species prediction. The planted auxiliary head is broken (xiao=2 has zero true-planted rows in training data due to the RGB decode bug). The introduced conditioning path is inert. The model treats a radiata plantation pixel and a native podocarp forest pixel as the same prediction problem: "which of 19,043 species is most likely at this climate/location?"

2. **Location encoding creates a powerful geographic prior that radiata cannot overcome.** The 40D sinusoidal location encoding tells the model exactly where it is. At (-41.15, 175.10), the model has seen overwhelmingly native NZ species. With only 7 radiata rows within 25km (vs hundreds of native broadleaf rows), the location prior dominates. The model correctly learns: "at this coordinate, native NZ species are observed." Radiata's plantation signal, even if present in AE embeddings, is outweighed by the geographic prior.

3. **The data scope collapse from V3 to V4.1 removed 93% of radiata's training support.** V3 had 9,616 radiata rows (8,705 from backfill). V4.1 has 706 (new_gbif only). This is not just "less data" — it is a qualitative change. V3's backfill included many NZ plantation records that provided local geographic support for radiata in plantation-dominated regions. Without those rows, radiata has almost no local support at the benchmark, while native species retain strong local presence.

**The core misunderstanding:** The pipeline treats species distribution modeling and plantation recognition as the same problem. They are not. SINR was designed to answer "what species could exist at this climate/location?" — a range-prediction problem. The plantation benchmark asks a fundamentally different question: "what was planted here?" — a land-use attribution problem. The current architecture cannot answer the second question because nothing in the training signal connects land-use type to species identity.

---

## 2. What the Benchmark Failure is REALLY Saying

### 2.1 The model is seeing "native NZ temperate forest"

The top-100 species above radiata in both V4.1 and V4.2 are **91% native NZ angiosperms** — Coprosma, Nothofagus, Metrosideros, Olearia, Pseudopanax, Weinmannia, etc. Only 9 of the top 104 are gymnosperms, and 8 of those are NZ-native podocarps (Podocarpus, Prumnopitys, Dacrydium, Phyllocladus). Only 1 is a plantation conifer (Pseudotsuga menziesii at rank #96). **Zero Pinus congeners appear above radiata.**

This is not a species-discrimination failure. The model is not confusing radiata with other pines. It is not even reaching the "which conifer?" question. The model sees the benchmark location and predicts: "this is where NZ native forest species live." The entire top of the ranking is populated by the native broadleaf/podocarp flora of the southern North Island.

### 2.2 What this implies about the feature space

The model's internal representation of the benchmark point is dominated by:
- **Location encoding:** (-41.15, 175.10) maps to southern Wairarapa — a region where the overwhelming majority of training observations are native NZ species
- **Environmental features:** bio01-bio19, elevation, soil — consistent with temperate oceanic NZ forest, which is where both native forest AND plantations exist
- **AE primary embedding:** 64D satellite appearance — encodes what the pixel looks like, which for a mature plantation may actually overlap with native forest signatures at 10m resolution
- **AE temporal stack:** 512D across 2017-2024 — should encode plantation temporal dynamics (planting/harvest cycles, homogeneous growth), but is overwhelmed by the location prior

### 2.3 The introduced pathway is not dead — it is uninformative

The fact that rank is unchanged across introduced=0.0/0.5/1.0 does NOT necessarily mean the pathway is architecturally dead. It could also mean:

- `--disable-intro-in-gate` is set at inference, so the gate does not use the introduced value
- `--no-boost` is set in V4.2, so there is no logit boost from intro_ratio
- The intro_residual path (if active) may have learned a near-zero scale because the introduced signal in training data is noisy/unreliable

The current setup intentionally disables the introduced pathway because the proxy labels were known to be broken. This is correct defensively, but it means the model has no mechanism to distinguish native from planted occurrences at inference time.

### 2.4 V4.2 improved radiata but did not fix the structural problem

The rank improvement from #105 to #79 shows that an_full + hard-cap is a better training recipe than plain BCE. Hard-cap reduced the dominance ratio from 378:1 to 1.4:1. The assumed-negative loss treats unobserved species as "probably absent" rather than "definitely absent," which is more honest for rare species.

But the improvement is modest (26 positions out of 19,043) because it addresses the training-objective problem without addressing the structural problem: the model still has no plantation-aware features, no plantation-discriminative loss, and insufficient radiata support near the benchmark.

---

## 3. Top-100 Above-Radiata Analysis

### 3.1 V4.2 an_full + hard-cap (rank #79)

From the V4.2 Comparison Analysis, the top 104 species ranked above radiata break down as:

| Category | Count | % |
|---|---:|---:|
| NZ native angiosperm (broadleaf) | ~80 | 77% |
| NZ native gymnosperm (podocarp/Phyllocladaceae) | 8 | 8% |
| Introduced angiosperm (weeds/naturalized) | ~15 | 14% |
| Plantation/introduced conifer | 1 | 1% |

**Notable patterns:**
- **Zero Pinus species** above radiata — no congener confusion
- **Dominant genera:** Coprosma, Nothofagus, Metrosideros, Olearia, Pseudopanax, Weinmannia — the canonical native flora of southern North Island NZ
- **The single plantation conifer** (Pseudotsuga menziesii, Douglas fir) at rank #96 is itself a plantation species commonly grown in NZ — yet it barely outranks radiata
- **Introduced species above radiata** are mostly invasive weeds and naturalized plants, not plantation timber

### 3.2 What changed from BCE to an_full

The V4.2 comparison documents note that during early an_full training (partial convergence), the ranking temporarily shifted toward "plantation/invasive/conifer-feeling taxa." But after full training (24 epochs), the model converged back to a broadleaf-heavy regime. This is consistent with the interpretation that:
- Early in training, an_full's more aggressive assumed-negative loss disrupts the dominant-species equilibrium
- But as training converges, the geographic prior reasserts itself because the location encoding provides such strong evidence for native NZ species
- The objective is not wrong — it just cannot overcome the data imbalance at the geographic level

### 3.3 Ecological interpretation

The model's ranking is ecologically reasonable if you ask "what species have been observed near this coordinate?" rather than "what was planted here?" The southern Wairarapa has extensive native forest reserves, and the GBIF observation record for NZ is heavily biased toward native species (naturalist observations, herbarium records, ecological surveys). Plantation forestry observations are underrepresented in GBIF because foresters do not typically upload radiata records to citizen-science platforms.

---

## 4. Representation / AE-Temporal Interpretation

### 4.1 What the AE embeddings should encode

AlphaEarth 64D embeddings encode 10m-resolution satellite imagery appearance. For a mature radiata plantation, this should capture:
- **Spectral homogeneity** — monoculture stands have uniform canopy reflectance
- **Canopy structure** — conifer canopy texture differs from broadleaf
- **Stand geometry** — plantation rows may be visible at 10m resolution

The AE temporal stack (8 years, 2017-2024) should additionally capture:
- **Growth trajectories** — plantation age classes show characteristic NDVI/reflectance curves
- **Harvest events** — clearcut disturbance followed by replanting
- **Phenological stability** — evergreen conifers show less seasonal variation than deciduous broadleaves

### 4.2 Why AE signal is not translating to radiata ranking

The AE embeddings likely DO contain plantation-relevant signal. The user's observation that "AE kNN surfaces plantation signal better than the classifier" is important evidence. If nearest-neighbor search over AE embeddings can find plantation-like matches, then the representation contains the information. The classifier is failing to use it. Here is why:

**Mechanism 1: The classifier objective does not reward plantation discrimination.** The species-level BCE/an_full loss asks: "predict which of 19,043 species is present." It does not ask: "is this a plantation?" The planted auxiliary head was supposed to provide this signal, but it is broken (zero true-planted rows due to xiao decode bug). Without a functioning plantation-awareness loss term, the AE plantation signal is noise from the classifier's perspective — it does not help predict any specific species better.

**Mechanism 2: The gated fusion architecture may suppress AE signal in favor of location.** The gated fusion produces `alpha * sat_h + (1-alpha) * env_h`. If the model learns that environmental features (which include climate, soil, and elevation) are more predictive of species identity than satellite appearance, it will down-weight the satellite branch. In NZ, where climate+location strongly predict native species, the model has a strong incentive to ignore satellite texture and rely on geographic/climatic priors. The AE branch may receive low gate weight precisely because the location encoding already provides strong species predictions.

**Mechanism 3: The trunk aggregation dilutes AE specificity.** After gated fusion, the 192D fused representation is concatenated with temporal (128D), land-state (32D), and location (64D), then passed through 6 residual blocks. The 384D trunk must represent all 19,043 species simultaneously. Subtle plantation-specific signals from the AE branch are averaged out during trunk processing because they are useful for only a tiny fraction of species.

**Mechanism 4: The shared representation learns "forestness" not "plantation-ness."** The SINR design assumes that a shared trunk learns a rich spatial/environmental representation that generalizes across species. For most species, this means learning biome-level and climate-zone-level features. Plantation-specific texture is a niche signal that benefits maybe 20-30 plantation timber species out of 19,043. The shared trunk has no incentive to preserve this signal because it helps so few species.

### 4.3 Why kNN over AE embeddings works better

Nearest-neighbor search in AE embedding space operates fundamentally differently from the trained classifier:

1. **kNN preserves local similarity structure.** If the benchmark point's AE embedding is close to training rows from radiata plantations, kNN will find them regardless of how many native broadleaf species dominate the dataset. The classifier head must balance 19,043 species simultaneously and chooses the most probable one overall.

2. **kNN has no location prior.** It matches on appearance alone. The classifier combines appearance with location encoding, and location dominates at this benchmark.

3. **kNN is not parametric.** It does not have a weight matrix that over-represents common classes. The classifier's final Linear(384, 19043) layer gives each species a 384D weight vector, and common species' vectors are trained with 100x-378x more gradient updates than radiata's vector.

4. **This is evidence that the representation is sound but the prediction head is the bottleneck.** The AE embeddings are doing their job; the issue is how the classifier converts representation to species prediction.

---

## 5. SINR Method Gap Analysis

### 5.1 Detailed comparison table

| Component | Original SINR | Our V4.2 | Impact on Radiata | Confidence |
|---|---|---|---|---|
| **Input encoding** | 4D sin/cos or 24D sin_cos+env | 40D sinusoidal + 64D AE + 512D temporal + 55D env + categoricals = ~680D | **Harmful.** Our richer input creates a stronger geographic/climatic prior that native species exploit more effectively than radiata. Original SINR's simpler input gives no single species family an overwhelming location advantage. | High |
| **Architecture** | Simple ResidualFCNet: 256-wide, 4 residual blocks, no branching | 5-branch gated fusion, temporal attention, aux heads, 384-wide trunk, 6 residual blocks | **Neutral to harmful.** More expressive, but complexity makes it harder to identify what the model is actually learning. Gate may suppress satellite branch. Aux heads are broken. | Medium |
| **Loss function** | `an_full` with pos_weight=2048, plus explicit background location loss | `an_full` with pos_weight=2048, NO background location loss | **Harmful.** Missing background negatives is the largest single SINR alignment gap. See section 5.2. | High |
| **Background negatives** | Spherical-uniform random locations with real environmental features; all species pushed to 0 at random points | Re-uses training data as pseudo-background (when bg_weight>0), currently disabled | **Harmful.** Without true background negatives, the model has no mechanism to learn "this location is NOT suitable for species X." The model only learns FROM where species are observed, never from where they are NOT observed. | Very High |
| **Hard cap** | 1000 per class (demo default) | 1000 per class | **Matched.** | High |
| **Species weighting** | None (all samples equal after cap) | Inverse-frequency weighting with gamma=0.5, clipped [0.25, 16.0] | **Slightly helpful.** Upweights rare species like radiata. But the maximum 16x boost is small relative to the location-prior advantage of dominant species. | Medium |
| **Output bias** | Explicitly False (no bias in final layer) | Explicitly False (bias=False in Linear) | **Matched.** | High |
| **Number of species** | 47,375 | 19,043 | **Favorable.** Fewer species means less assumed-negative pressure per sample. | Low |
| **Training data size** | 35.5M observations | 11.9M rows (or ~6.5M after hard cap) | **Somewhat unfavorable.** Less data overall, but manageable. | Low |
| **Temporal features** | None | 512D AE temporal with attention | **Should help but doesn't.** Temporal signal exists but is not connected to species prediction effectively. | Medium |
| **Introduced/planted features** | None (SINR does not model native vs introduced) | Broken (xiao decode bug, zero planted rows, inert conditioning) | **Harmful.** The presence of broken features is worse than their absence. The gate, residual, and boost mechanisms all reference introduced/planted signals that contain no useful information, potentially adding noise. | High |
| **Phylogenetic features** | None | Zeroed at inference (used only during training as regularization) | **Neutral.** Zeroed at inference so cannot help or hurt at benchmark time. | High |
| **Training epochs** | 10 full passes over entire dataset | 24 shard-epochs (2 cycles x 12 shards, each shard ~1/12 of data) | **Probably matched.** 24 shard-epochs with 12 shards = ~2 full dataset passes. Original SINR does 10 full passes. Our model may be undertrained relative to original SINR. | Medium |

### 5.2 The missing background negative loss — the largest gap

Original SINR's `an_full` loss has TWO components:

```
L = L_pos_and_assumed_neg(data_location) + L_background(random_location)
```

Where `L_background = -mean(log(1 - sigmoid(logits_at_random_point)))` pushes ALL species toward 0 at random geographic locations.

Our V4.2 implementation has only:

```
L = L_pos_and_assumed_neg(data_location)
```

The background component is entirely missing (bg_weight=0.0).

**Why this matters for radiata:**

Without background negatives, the model learns species ranges ONLY from where species are observed. It never learns "species X should NOT be predicted here." This creates an asymmetry:
- Common NZ native species have thousands of observations across NZ, giving the model strong positive evidence for their presence throughout the country
- Radiata has only 706 observations, heavily concentrated in plantation regions
- At a location where both native species and radiata could plausibly exist, the model defaults to the species with more local positive evidence — native species win

With background negatives, the model would also learn:
- At random ocean locations: ALL species should be 0 (geographic range learning)
- At random desert locations: NZ forest species should be 0
- At random tropical locations: NZ temperate species should be 0
- This forces the model to learn BOUNDED ranges, not just unbounded presence signals

The background loss acts as a regularizer that prevents the model from predicting species everywhere their climate niche is satisfied. It forces spatial specificity. Without it, common species "leak" their predictions into locations where they have climate tolerance but no actual presence — which is exactly what's happening at the benchmark.

### 5.3 How our architecture has drifted from SINR's spirit

Original SINR solves a clean problem: **given a location, predict which species are present.** The input is minimal (4D or 24D), the architecture is simple (256-wide residual MLP), and the loss is principled (assumed-negative with background).

Our pipeline solves a different problem: **given a location, satellite imagery, temporal trajectory, climate, soil, land cover, and forest type, predict which species are present.** The input is massive (~680D), the architecture is complex (5-branch gated fusion with attention), and the loss is one piece of a multi-task objective (species + planted + land-state).

The drift matters because:
1. **More features create more ways for common species to dominate.** Each additional feature family provides new dimensions along which native NZ species have stronger training signal than radiata.
2. **The gated fusion adds an implicit attention mechanism** that the model can use to selectively ignore branches — including the satellite branch that contains plantation signal.
3. **The auxiliary heads create competing objectives** that do not serve the benchmark. The planted head has zero useful signal. The land-state head encodes heuristic rules rather than learned plantation attributes.
4. **The temporal attention module adds 128D to the trunk input** but the temporal signal it captures (plantation growth trajectories) is not rewarded by the species-level loss unless it helps discriminate among species that share the same location.

---

## 6. What Mechanism is Most Likely Failing

Ranked by estimated causal contribution to the benchmark failure:

### Rank 1: Location-prior dominance (estimated 40% of failure)

The 40D sinusoidal location encoding gives the model a precise geographic coordinate. At (-41.15, 175.10), the training data is overwhelmingly native NZ species. The model learns a strong geographic prior: "at this coordinate, predict NZ native broadleaf/podocarp species." This prior is correct for the majority of training observations at this location and is strongly rewarded by the loss.

Radiata cannot overcome this prior because:
- Only 7 radiata rows exist within 25km of the benchmark
- Hundreds of native species rows exist in the same radius
- The location encoding is high-frequency enough (up to 2^9 * pi) to resolve ~100km scale, so the model can learn very local species distributions
- The shared trunk's 384D representation is dominated by the location-prior signal because it helps predict the most species correctly

**Key test:** V3 experiment v14 (which added location encoding) achieved rank #2 for radiata — but V3 had 9,616 radiata rows including 39 within 25km. With sufficient local support, radiata can overcome the location prior. Without it (V4.1: 7 rows within 25km), it cannot.

### Rank 2: Missing background negative loss (estimated 25% of failure)

Without background negatives, the model never learns to suppress species predictions at locations outside their true range. Common NZ species "leak" high predictions across all NZ coordinates because the model has only seen positive evidence for them. Radiata's prediction is not actively suppressed — it just cannot compete with hundreds of species that each have stronger positive evidence.

Background negatives would help by:
- Teaching the model to output 0 for NZ native species at non-NZ locations, making their NZ predictions more calibrated
- Teaching the model to output 0 for ALL species at random locations, providing a baseline against which local positive evidence is measured
- Forcing the model to learn bounded geographic ranges rather than climate-envelope predictions

### Rank 3: Data scope collapse (estimated 25% of failure)

The V3-to-V4.1 transition removed 93% of radiata's training support. This is not just a quantity issue — it is a geographic coverage issue. The backfill rows likely included observations from plantation-dominated landscapes where radiata was the dominant species. Without those rows, the model has no examples of "locations where radiata dominates and native species are subordinate."

The remaining 706 new_gbif rows are likely:
- Scattered across radiata's global range (not concentrated in NZ)
- Mixed with other species at the same locations
- Insufficient to establish a strong local prior in any NZ region

### Rank 4: Broken plantation-awareness features (estimated 10% of failure)

The planted auxiliary head, the introduced conditioning path, and the xiao_planted_forest categorical all intended to provide plantation-specific signal. All are non-functional:
- Planted aux head: trained on legacy_gt1 proxy which labels natural forest as planted (xiao RGB decode bug)
- Introduced conditioning: disabled at inference (--disable-intro-in-gate, --no-boost)
- Xiao categorical: has zero true-planted (value=2) rows in training data

These features occupy model capacity without contributing useful signal. Their presence is worse than absence because they may confuse the gate's routing decisions during training.

### Summary

The model is solving the right problem (species distribution modeling) but being evaluated on a different problem (plantation species attribution). The location prior, the missing background loss, and the data scope collapse combine to make radiata uncompetitive at a coordinate where the training record is dominated by native species. No single fix will resolve this — it requires addressing at least the background-loss and data-scope problems simultaneously.

---

## 7. Minimum-Change Experiment Roadmap

### Experiment 1: True Background Negative Loss (HIGHEST PRIORITY)

**Hypothesis:** Adding true background negatives will improve spatial specificity and reduce the "leak" of common species into locations outside their actual observed range. This should lower the scores of NZ native species at plantation locations and improve radiata's relative rank.

**Implementation:**
- Generate random lat/lon points using spherical uniform sampling (matching original SINR)
- For each random point, sample environmental features from GEE (or use pre-computed global environmental raster)
- At each random point, push ALL species logits toward 0
- Weight the background loss at 1.0 (matching original SINR default)
- Use `--bg-weight 1.0` flag (already exists in codebase but currently generates pseudo-backgrounds from training data, not true random locations)

**Exact change needed:** Modify the background sampling in `train_on_vm.py` lines 1226-1240 to sample truly random geographic points with real environmental features, rather than re-using training data indices. This requires either:
- Pre-computing a global environmental feature raster and sampling from it at random coordinates
- Or computing features on-the-fly from stored GEE rasters

**Non-destructive:** Yes — new training run with new model directory
**Expected outcome if hypothesis is true:** Native NZ species scores drop at the benchmark (they should have bounded ranges, not global high predictions). Radiata rank improves to <#50 even without data augmentation.
**When:** Before backfill merge. This tests a training-recipe hypothesis independent of data scope.

### Experiment 2: Location Encoding Ablation

**Hypothesis:** Location encoding is providing such a strong geographic prior that it overwhelms the AE/environmental signal. Removing it may allow the model to rely more on satellite appearance and environmental features, which better distinguish plantations from native forest.

**Implementation:**
- Train with `--use-location-encoding` disabled
- Keep all other V4.2 settings (an_full, hard-cap 1000, no-boost)

**Non-destructive:** Yes — new model directory
**Expected outcome if hypothesis is true:** Radiata rank improves because the model cannot use coordinate as a shortcut for "predict native NZ species." Environmental/AE features become the primary discriminators.
**Expected outcome if hypothesis is false:** Overall validation accuracy drops significantly (the model loses geographic specificity), and radiata may not improve because climate alone does not distinguish plantations from native forest.
**When:** Before backfill merge. Quick experiment, single run.

### Experiment 3: Reduced Location Encoding Resolution

**Hypothesis:** The location encoding's highest frequencies (2^7, 2^8, 2^9) create overly precise geographic priors that memorize local species distributions. Reducing to 4-5 frequencies (2^0..2^4) would provide continental/regional context without enabling location memorization.

**Implementation:**
- Modify `encode_location_sinusoidal` to use `num_frequencies=5` instead of 10
- This reduces location encoding from 40D to 20D
- Keep all other V4.2 settings

**Non-destructive:** Yes — new model directory
**Expected outcome if hypothesis is true:** Model retains broad geographic awareness (hemisphere, continent, biome) but cannot memorize "at this exact coordinate, predict these species." AE/environmental features become more important for local discrimination.
**When:** Before backfill merge, after Experiment 2 results clarify location encoding's role.

### Experiment 4: kNN-Assisted Reranking

**Hypothesis:** A post-hoc reranking step using AE embedding similarity can inject plantation-specific signal that the classifier misses, without retraining.

**Implementation:**
- At inference time, compute AE cosine similarity between the query point and all training rows
- Find the k nearest neighbors in AE space
- Compute a species distribution from the kNN result (frequency of each species among k neighbors)
- Blend the kNN distribution with the classifier's probability distribution using a configurable mixing weight: `final_score = (1-lambda) * classifier_prob + lambda * knn_freq`
- Evaluate at lambda = 0.0, 0.1, 0.2, 0.3, 0.5

**Non-destructive:** Yes — post-hoc inference script, no model retraining
**Expected outcome if hypothesis is true:** At moderate lambda (0.1-0.3), radiata rank improves significantly because kNN finds plantation-like training examples that share AE similarity with the benchmark.
**When:** Immediately — no training required. Can run on existing V4.2 model.

### Experiment 5: TDWG Region Prior

**Hypothesis:** Adding a TDWG Level-3 region prior at inference time can provide biogeographic context that the model currently lacks. For NZ, this would boost known NZ species (both native and introduced) and suppress species from other continents.

**Implementation:**
- Already partially implemented in v3_point_inference.py (lines 125-140)
- Extend to include both native and introduced species known from NZ TDWG regions
- Compute boost as `weight * log(1 + alpha * freq_ratio)` for species with TDWG occurrence records in NZ
- Radiata has TDWG records for NZ and would receive a boost

**Non-destructive:** Yes — inference-time parameter, no retraining
**Expected outcome if hypothesis is true:** Radiata rank improves because it receives a biogeographic boost from its known NZ occurrence. However, NZ native species also receive a boost, so the net effect depends on whether radiata's boost is proportionally larger.
**When:** Immediately — inference parameter. Can test in combination with Experiment 4.

### Experiment 6: Backfill Data Merge (After Recipe Experiments)

**Hypothesis:** Restoring the ~8,700 backfill radiata rows (plus backfill rows for other species) will provide sufficient local support to overcome the geographic prior, especially when combined with improved training recipe (an_full + background negatives + reduced location encoding).

**Implementation:**
- Join backfill feature table with V4.1 preview training table
- Apply strict data quality filters (same as V4.1 pipeline)
- Retrain with best training recipe from Experiments 1-3

**Non-destructive:** Yes — new training table, new model directory
**Expected outcome if hypothesis is true:** Radiata rank returns to competitive range (#1-10), matching V3 v14 performance.
**When:** AFTER Experiments 1-3 establish the best training recipe. Merging backfill first would mask whether recipe changes are necessary.

### Experiment priority and sequencing

```
Phase 1 (immediate, no retraining):
  Exp 4: kNN reranking         <- tests representation hypothesis
  Exp 5: TDWG prior            <- tests biogeographic prior hypothesis

Phase 2 (before backfill):
  Exp 1: True background negatives  <- tests SINR alignment hypothesis
  Exp 2: Location encoding ablation <- tests location-prior hypothesis
  Exp 3: Reduced location freqs     <- refines location-prior finding

Phase 3 (after recipe established):
  Exp 6: Backfill merge         <- tests data scope hypothesis
```

---

## 8. What Should Wait Until Backfill / V4.3

### Must wait for backfill

1. **Final radiata benchmark target setting.** Until the model has sufficient radiata support (>5,000 rows), any rank target below ~#30 is unrealistic. Set intermediate targets for recipe experiments (#50-#80) and final targets for post-backfill (#1-#10).

2. **Multi-species plantation benchmark suite.** Evaluating on a single species/location is high-variance. A proper benchmark needs:
   - Eucalyptus globulus in Tasmania
   - Pinus sylvestris in Scandinavia
   - Tectona grandis in SE Asia
   - Acacia mangium in SE Asia
   - Plus native forest control points for each region

3. **Introduced/planted feature repair.** The xiao RGB decode bug must be fixed at the data level. This requires re-extracting xiao features or applying a correction overlay. Only worth doing when the backfill data provides sufficient planted-location examples to train a meaningful planted auxiliary head.

### Should wait for V4.3+

4. **Architecture changes to the fusion gate.** Modifying the gated fusion to give satellite branch more weight at plantation locations requires a reliable planted/natural label — which requires the xiao fix.

5. **LE-SINR text embeddings (6th branch).** Species text descriptions could provide a "plantation timber" signal, but this is a major feature addition that should not confound the current diagnosis.

6. **Imbalance-Aware Loss (Zbinden 2024).** Promising loss upgrade but should be evaluated after the background-negative gap is closed and backfill is merged.

7. **Carbon regression auxiliary head.** Could provide a plantation-correlated training signal (plantations have distinct carbon dynamics), but requires canonical carbon features which are currently in the gray/excluded confidence class.

### Should NOT be done

- **Increasing epochs without recipe changes.** Both V4.1 and V4.2 show signs of convergence by epoch 24. V4.2 validation metrics are still improving but at a decelerating rate. More epochs would overfit common species without helping radiata.

- **Widening the feature estate.** The model already has ~680D of input features. Adding more features without fixing the objective/prior problem will not help and may make it worse.

- **Rewriting the architecture.** The 5-branch gated fusion is more expressive than original SINR. The problem is not architecture capacity — it is what the model is asked to learn.

---

## 9. Final Recommendation

### The diagnosis in one sentence

The model correctly learns "what species are observed near this coordinate and climate" but is being evaluated on "what species was planted here" — and nothing in the training pipeline teaches it the difference.

### The three things that would most change the result

1. **Add true background negative sampling** (Experiment 1). This is the single most impactful SINR-alignment fix. It forces the model to learn bounded species ranges rather than unbounded climate-envelope predictions. It is the largest gap between our trainer and original SINR. Estimated impact: 15-30 rank positions.

2. **Reduce or ablate location encoding** (Experiments 2-3). The location encoding creates an overpowering geographic prior that radiata cannot overcome with only 7 local training rows. Removing it or reducing its resolution forces the model to rely on environmental/satellite features that better distinguish land-use types. Estimated impact: 10-20 rank positions, with possible validation accuracy tradeoff.

3. **Merge backfill data** (Experiment 6). Restoring radiata's local support is necessary for competitive ranking. But this should happen AFTER recipe experiments establish whether the training objective can convert data into accurate predictions. Estimated impact: 30-50 rank positions when combined with recipe fixes.

### What the user should believe

- The AE embeddings almost certainly contain plantation-relevant signal. The kNN evidence supports this.
- The classifier is not using this signal because the training objective rewards predicting common local species, not distinguishing land-use types.
- The location encoding is the strongest single predictor in the model, and it encodes "where native NZ species live" far more than "where radiata plantations exist."
- Original SINR would likely also fail at this benchmark with the current data scope, but its background negative loss would at least prevent the extreme location-prior dominance we see.
- The solution is not more data OR a better loss — it is both, applied in the right order: fix the recipe first, then add data.

### What the user should NOT believe

- "More epochs will fix it." No — the model is converging to the wrong solution because the objective rewards the wrong behavior.
- "More data will fix it." Partially — backfill will help, but without recipe fixes, the model will still learn geographic priors that favor common local species over plantation species.
- "The introduced pathway will fix it." No — even a perfectly functioning introduced pathway only tells the model that a species CAN be introduced, not that it IS planted at a specific location. The pathway's inertness is a symptom, not a cause.
- "AE is not capturing plantation signal." Almost certainly wrong — kNN evidence suggests it is. The problem is downstream of the representation.

---

## Appendix A: SINR an_full Loss — Exact Implementation Comparison

### Original SINR (from `losses.py:93-125`)

```python
# At data location: all species assumed negative, then correct for true positive
loss_pos = neg_log(1.0 - loc_pred)                    # [B, S] — all assumed absent
loss_pos[i, class_id] = pos_weight * neg_log(loc_pred[i, class_id])  # correct for true species

# At random background location: all species assumed absent
loss_bg = neg_log(1.0 - loc_pred_rand)                # [B, S]

loss = loss_pos.mean() + loss_bg.mean()
```

Where `loc_pred_rand` uses features from a truly random geographic location sampled from a spherical uniform distribution.

### Our V4.2 (from `train_on_vm.py:304-332`)

```python
# At data location: compute assumed-negative correction
log_pos = log(sigmoid(logit))
log_neg = log(sigmoid(-logit))
loss_neg = -mean(log_neg, dim=species)                 # mean "all absent" loss
correction = (log_neg[t] + pos_weight * (-log_pos[t])) / num_species
loss = loss_neg + correction

# NO background location loss
```

### Key difference

The background loss `loss_bg = neg_log(1.0 - loc_pred_rand).mean()` is completely absent from our implementation. This term pushes all 19,043 species toward 0 at random geographic points. Without it, the model has no incentive to learn bounded ranges — it can predict high probabilities for common species across all locations within their climate envelope.

---

## Appendix B: Data Support Summary

| Metric | V3 (preview-clean) | V4.1 (preview-train) | Ratio |
|---|---:|---:|---|
| Total radiata rows | 9,616 | 706 | 13.6x loss |
| Radiata rows from backfill | 8,705 | 0 | 100% loss |
| Radiata rows from new_gbif | 911 | 706 | 1.3x loss |
| NZ radiata rows | 1,107 | 272 | 4.1x loss |
| Radiata within 25km of benchmark | 39 | 7 | 5.6x loss |
| Radiata rank at benchmark | #2 (v14) / #12 (v4) | #79 (V4.2) / #105 (V4.1) | -- |

---

## Appendix C: Architecture Dimension Flow

```
Input Features:
  AE primary:     64D  ──→ sat_proj (64→192) ──→ ┐
  Environment:    55D  ──→ env_proj (55→192) ──→ ├─ gate(alpha) ──→ fused (192D)
  Categoricals:   ~15D (embedded) ──────────────→ ┘
  
  AE temporal:   512D  ──→ TemporalAttention ──→ temporal_h (128D)
  Land state:      5D  ──→ land_proj (5→32)  ──→ land_h (32D)
  Location enc:   40D  ──→ loc_proj (40→64)  ──→ loc_h (64D)
  
Trunk input:
  [fused(192) + temporal(128) + land(32) + location(64)] = 416D
  ──→ Linear(416→384) ──→ 6x ResidualBlock(384) ──→ trunk_out (384D)
  
Output heads:
  Species:    Linear(384→19,043, bias=False) ──→ logits
  Planted:    Linear(384→1)                  ──→ planted_score
  Land-state: Linear(384→6)                  ──→ land_state_pred
```

---

## Appendix D: Key V3 Experiment Comparison

The V3 experiment history provides crucial evidence about what factors matter:

| Change | V3 Experiment | Radiata Rank | What It Tells Us |
|---|---|---:|---|
| Baseline (BCE, no location enc) | v4 | #12 | Without location encoding, radiata competes reasonably with 9,616 rows |
| + location encoding | v14 | #2 | Location encoding + sufficient local data = excellent radiata ranking |
| - aux heads | v11 | #106 | Aux heads matter — they provide regularization that helps rare species |
| + bg-weight 1.0 | v12 | #12 | Background loss is a good regularizer (val top10 50.3%) but does not help radiata rank when pseudo-backgrounds are used |
| + temporal magnitude | v17 | #83 | Temporal magnitude features HURT — they may encode noise that confuses the model |
| + strict_planted3 label | v16a | #919 | Broken planted label is catastrophically harmful |
| + 3 training cycles | v13 | #49 | More training hurts radiata — the model over-learns the geographic prior |

**Critical insight from v14 vs v4:** Location encoding HELPS radiata (from #12 to #2) when there is sufficient local support (39 rows within 25km). It HURTS when local support is thin (V4.1: 7 rows within 25km, rank #105). Location encoding is a multiplier — it amplifies whatever signal is locally dominant. If native species dominate locally, location encoding amplifies their dominance.

**Critical insight from v13:** More training cycles HURT radiata (#12 to #49). This means the model is progressively over-learning the geographic prior and squeezing out radiata's weak local signal. This is exactly consistent with the "location prior dominance" diagnosis.

---

## Appendix E: Validation Metric Comparison (Final Epoch)

| Metric | V4.1 BCE (ep24) | V4.2 AN_FULL (ep24) | V3 v14 best | V3 v4 baseline |
|---|---|---|---|---|
| Val Top-1 | 12.63% | 10.07% | — | ~42% (est) |
| Val Top-5 | 38.77% | 32.55% | — | — |
| Val Top-10 | 57.32% | 48.30% | 46.3% | ~42% |
| Radiata rank | #105 | #79 | #2 | #12 |
| Radiata prob | 0.608 | 0.917 | 0.940 | 0.950 |

**Note:** V4.2 AN_FULL has LOWER validation accuracy than V4.1 BCE but HIGHER radiata probability (0.917 vs 0.608) and BETTER radiata rank (#79 vs #105). This is because AN_FULL with hard-cap redistributes learning capacity from dominant species to rare species. The aggregate metrics (top-1/5/10) drop because dominant species lose accuracy, but rare species like radiata gain.

This is further evidence that the training objective matters: AN_FULL is better for rare species even though it appears worse on aggregate metrics. The aggregate metrics are dominated by common species performance.

---

## Appendix F: Effective Training Passes

| Setup | Shard epochs | Shards | Effective full passes | Original SINR |
|---|---|---|---|---|
| V4.1 | 24 | 12 | 2.0 | 10 |
| V4.2 | 24 | 12 | 2.0 | 10 |

Our model sees the full dataset only ~2 times vs SINR's 10 full passes. This is a potential contributing factor, though the convergence curves suggest diminishing returns after epoch 18-20. More passes may help, but the effect is likely small (5-10 rank positions) compared to the structural issues identified above.
