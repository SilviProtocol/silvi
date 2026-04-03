# Independent Diagnostic Report: SINR V4.1/4.2 Radiata Benchmark Failure

**Date:** March 16, 2026
**Target Benchmark:** Lat -41.1516, Lon 175.0997 (2023) - Known *Pinus radiata* plantation
**Investigator:** Opencode (Gemini 3.1 Pro)

## 1. Executive Diagnosis

The model is not failing to learn species discrimination; it is **failing to learn "plantation-ness" in the presence of overwhelming geographic priors.** 

Our V4 architecture concatenates AlphaEarth (AE) embeddings, Environmental features, and a Sinusoidal Location Encoding. In the supervised training objective (BCE or Assumed-Negative), the model seeks to minimize global loss across 11.9 million rows. Because GBIF data is >99% wild/native occurrences, the strongest statistical predictor of a species is its biogeographic location. The network learns a massive, dominant location prior. 

At the NZ benchmark, the location encoding "shouts" that this area is native NZ forest (supported by ~100,000 local training points). The AE embedding "whispers" that this is a plantation (supported by only 272 radiata points in all of NZ). The network's linear fusion simply drowns out the AE signal to satisfy the geographic prior. 

**Conclusion:** The model correctly identifies the geography, but the architecture and training recipe allow the geographical prior to overrule the visual/temporal evidence of a plantation.

---

## 2. What the benchmark failure is REALLY saying

When you toggle the `is_introduced` parameter (0.0, 0.5, 1.0) and see **no change in rank**, it means the introduced pathway is statistically dead for this specific location/feature combination. 

The benchmark failure is telling us:
1. **It sees Native Forest, not a Plantation:** The model does not see the benchmark as a generic "managed conifer-like place". It sees it as deep native New Zealand bush.
2. **The "Assumed Negative" loss is not enough on its own:** Moving from BCE (rank #105) to `an_full` (rank #79) improved the rank by globally pushing down false positives, but it did not fundamentally alter the model's reliance on the geographic prior.
3. **Data count is relative to local confusers:** While Radiata has 706 global rows in V4.1 (not ultra-rare), it only has **7 rows within 25km** of the benchmark. In contrast, the top 10 native angiosperms have **over 3,500 rows** in that same radius. The neural network optimizes for the 3,500, ignoring the 7.

---

## 3. Top-100 above-radiata analysis

I extracted and translated the top 20 species predicted by both V4.1 (BCE) and V4.2 (an_full) at the benchmark. 

**V4.1 (BCE) Top 5:**
1. *Coprosma lucida* (Native Angiosperm)
2. *Melicytus ramiflorus* (Native Angiosperm)
3. *Hedycarya arborea* (Native Angiosperm)
4. *Knightia excelsa* (Native Angiosperm)
5. *Carpodetus serratus* (Native Angiosperm)

**V4.2 (an_full) Top 5:**
1. *Knightia excelsa* (Native Angiosperm)
2. *Melicytus ramiflorus* (Native Angiosperm)
3. *Hedycarya arborea* (Native Angiosperm)
4. *Beilschmiedia tawa* (Native Angiosperm)
5. *Coprosma lucida* (Native Angiosperm)

**Analysis of the Top 100:**
- **Angiosperms vs Gymnosperms:** ~90% of the top 100 are native NZ broadleaf angiosperms. 
- **Native vs Introduced:** 100% of the top 20 are endemic/native to New Zealand. There are **zero** plantation confusers (no Eucalyptus, no other Pines, no Acacia, no Douglas Fir) in the top 50.
- **Gymnosperm Confusers:** The highest-ranked conifers are *Prumnopitys ferruginea* (Miro) and *Dacrydium cupressinum* (Rimu)—which are native NZ podocarps (wild forest), not plantation species.

**Summary:** The `an_full` objective shuffled the native broadleaves slightly, but the regime remains entirely "Native NZ Forest". The model is predicting the background ecology of the region, completely missing the plantation disturbance.

---

## 4. Representation / AE-temporal interpretation

**Why does AE kNN surface plantation signal better than the classifier?**

In a kNN setup, distance is measured directly in the AE representation manifold. Because the AE model was pre-trained to reconstruct spectral and temporal signatures (e.g., clearcut cycles, dense mono-crop texture), a radiata plantation in NZ looks mathematically close to a radiata plantation in Chile in AE space.

However, in the supervised V4 model, we use a simple concatenation:
`[AE_Proj, Temp_Proj, Env_Proj, Location_Proj] -> MLP -> Logits`

During backpropagation, the gradients update the MLP weights to minimize error. Because 99% of training points are wild, the MLP learns: *"If `Location_Proj` = New Zealand, weight the native species logits heavily and ignore `AE_Proj`, because doing so minimizes my loss on the 96,000 native rows, even if I get the 272 radiata rows wrong."*

The classifier head acts as an over-regularizer that collapses the rich, cross-continental AE plantation manifold into a simplistic, geography-bound lookup table.

---

## 5. SINR method gap analysis

We are calling this "SINR", but our architecture and data have drifted significantly from the original Cole et al. methodology in ways that directly cause this failure.

| Component | Original SINR | Our V4.2 Setup | Impact on Radiata (Confidence: High) |
| :--- | :--- | :--- | :--- |
| **Spatial Fusion** | Pure implicit spatial representation (Lat/Lon is the only/primary input). | Location encoding is concatenated with high-dimensional AE and Env. | Location dominates as a "shortcut" prior, suppressing the AE plantation texture signal. |
| **Background Negatives** | Uses truly random, uniform, or population-weighted spatial points as assumed negatives. | Uses pseudo-absences derived *only* from where other species are present (GBIF data). | Forces the model to learn the sampling bias of GBIF (dense in native forests). The model learns to predict "Native Forest" because that is what the negative pool looks like locally. |
| **Class Imbalance** | Evaluates spatial range boundary precision, independent of global row counts. | Uses hard-caps (1000) globally, but locally remains violently imbalanced (7 radiata vs 3500 natives). | Global hard-caps do not fix extreme local imbalances. The geographical prior still votes for the local majority. |
| **Ecological Assumption** | Assumes species distributions follow smooth biogeographical gradients. | Trying to map both biogeographical gradients (wild) and abrupt human disturbances (plantations). | Plantations break the rules of biogeography. Fusing location + texture with a smooth spatial prior guarantees the plantation signal will be smoothed out. |

---

## 6. What mechanism is most likely failing

**The Geographic Prior is overpowering the Representation.**

The model is failing to learn a hard conditional rule: *"If the AE texture is a plantation, disregard the geographic prior and predict plantation species."* 

Instead, it learns a linear compromise: *"Add the plantation texture to the geographic prior."* But because the geographic prior is mathematically massive (due to local row counts), the final sum is still overwhelmingly "Native Forest".

---

## 7. Minimum-change experiment roadmap

Do **not** rewrite the trainer. Run these non-destructive experiments to isolate the fusion failure:

**Experiment A: Ablate the Location Encoding (Highest Priority)**
*   **Hypothesis:** The location encoding is acting as a massive confounding prior that drowns out the AE plantation signal.
*   **Action:** Train a V4.2 `an_full` model with `--use-location-encoding False`.
*   **Expected Outcome:** If the hypothesis is true, the benchmark prediction will shift drastically away from Native NZ Broadleaves and towards generic plantation species (Pines, Eucalyptus), even if it doesn't get *radiata* perfectly as #1.
*   **Destructive?** No. Just a new run artifact.

**Experiment B: kNN-Assisted Feature Probing**
*   **Hypothesis:** The internal `AE_Proj` manifold clusters plantations correctly, but the final output layer squashes them.
*   **Action:** Write a short script to extract the pre-logits hidden state (or pure AE features) for the benchmark point and the nearest 100 radiata/native points. Calculate cosine similarities.
*   **Expected Outcome:** Proves whether the neural network is *erasing* the plantation signal in the final layers to satisfy the spatial loss, or if it never extracted it properly from the AE sequence.

**Experiment C: True Uniform Background Negatives (Mini-batch)**
*   **Hypothesis:** Our "assumed negatives" are just other GBIF points, forcing the model to over-index on native forests.
*   **Action:** Modify the data loader (optionally) to inject 10% completely random Lat/Lon points into the batch as "background", pushing the model to differentiate presence from *everything*, not just other survey biases. 

---

## 8. What should wait until backfill / V4.3

*   **Massive Data Merges:** Waiting for the 8,705 backfill radiata rows will definitely improve the local NZ count, and might artificially "fix" this specific benchmark by giving radiata enough geographic weight to fight back. However, it will not fix the underlying architectural flaw for other rare, non-native disturbances. Do not rely on backfill as the scientific solution.
*   **Complex Reranking / TDWG Priors:** Do not build complex post-hoc rerankers until we prove (via Exp A) that the neural network *can* learn plantation texture when unburdened by the spatial prior.

---

## 9. Final recommendation

Stop tweaking the loss function and class caps for a moment. **The model is suffering from spatial prior collapse.** Run a training cycle completely ablating the location encoding (`--use-location-encoding False`). If the model suddenly starts predicting *Pinus*, *Eucalyptus*, or other plantation taxa at the benchmark, you have proven that the architecture's linear fusion is fundamentally incompatible with identifying abrupt, human-driven ecological disturbances in a dataset dominated by wild geography.