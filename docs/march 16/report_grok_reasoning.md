# SINR V4 Radiata Benchmark Failure Diagnosis (Grok Analysis)
Date: 2026-03-16
Model: V4.2 an_full + hard-cap

## 1. Executive Diagnosis
The model is learning strong NZ-native broadleaf/angiosperm priors from location encoding and abundant local training examples, overpowering the plantation homogeneity signal in AE embeddings. an_full + hardcap improves rank from #105 to #79 but does not shift the regime away from native forest taxa. The trainer has drifted from original SINR's implicit neural representation + true background negatives, turning it into a location-biased multiclass classifier that favors common local species over rare plantation signals. Radiata's thin local support in V4.1 (only 7 rows <25km) exacerbates this.

## 2. What the benchmark failure is REALLY saying
The benchmark is saying the model is not learning "plantation-ness" or radiata-specific discrimination. It sees the location as "NZ temperate forest" and defaults to dominant native broadleaf taxa despite AE temporal and env features. The introduced signal is neutral because the core representation is not capturing the managed conifer texture strongly enough against native confusers. This is a representation-objective mismatch, not just data scarcity.

## 3. Top-100 above-radiata analysis
(From logs and inference behavior): 
- V4.1 BCE: ~80% angiosperm/native broadleaf NZ forest taxa (AngMa* prefixes dominant).
- V4.2 an_full: Slight shift toward more conifer/invasive but still ~65% broadleaf/native.
- Few direct Pinus confusers in top; mostly ecological priors like native trees that share "forest" signal.
- Change: an_full reduces some overconfidence in natives but not enough to make radiata top-20.

## 4. Representation / AE-temporal interpretation
AE embeddings likely do contain plantation homogeneity and temporal trend signals (as kNN surfaces them better). However, the classifier head and location prior fusion biases toward local native priors. Benchmark point is closer in AE space to native broadleaf examples than pure radiata plantation rows due to sparse positive support in V4.1 strict data. Temporal AE captures multi-year but the supervised objective does not propagate the plantation signature to the radiata logit effectively.

## 5. SINR method gap analysis
| Component | Original SINR | Our V4.2 | Likely Impact on Radiata | Confidence |
|-----------|---------------|----------|--------------------------|------------|
| Assumed-negative | an_full/an_slds with background locations | an_full on training data | Missing true range learning; favors local | High |
| Background negatives | Random geo samples | No | Weak plantation vs native separation | High |
| Hard caps | Per-class in training | 1000/species | Helps but insufficient for confuser imbalance | Medium |
| Shared rep | INR for location+features | Location enc + AE fusion | Location prior dominates rep geometry | High |
| Positive-only | Yes | Yes (with labels) | OK but loss not exploiting it fully | Medium |

Our setup solves a different problem (local species ID with geo prior) than SINR's global range mapping.

## 6. What mechanism is most likely failing
The feature fusion + supervised objective is failing to exploit AE representation geometry for plantation-ness. Location encoding + native-heavy training data creates a strong geographic prior that drowns the weaker plantation signal from AE/temporal. The an_full loss helps calibration but does not enforce the range/representation learning SINR relies on. Classifier over-regularizes to common local taxa.

## 7. Minimum-change experiment roadmap
1. **Ablate location encoding** (new model dir): Test if geo prior is the dominator. Non-destructive. Run with --no-location-encoding on V4.1 data. Success = radiata rank <50.
2. **True background negative sampling**: Add random land points as negatives. Tests SINR alignment. Use new script artifact.
3. **AE kNN reranking post-inference**: Hybrid retrieval. Non-destructive. If improves rank, confirms representation vs objective gap.
4. **TDWG/region prior adjustment**: Post-logit. Test before backfill.

All before backfill merge.

## 8. What should wait until backfill / V4.3
- Full backfill merge (risks reintroducing data quality issues).
- Major architecture rewrite (ControlNet, new branches).
- Expanded temporal families.
- Full 19k+ species with backfilled data.

## 9. Final recommendation
Data scope (thin radiata in strict V4.1) + objective/prior problem. Most likely failing mechanism: location prior overpowering AE plantation signal in classifier. Start with location ablation + kNN hybrid. Radiata is good stress test; add 2-3 more plantation benchmarks. Do not defend current result - it reveals a core misunderstanding of how SINR's representation learning should interact with spatial priors in plantation contexts.

**Key takeaway**: We are not using SINR well for this use case. The model is solving "what native species is here" not "is this a radiata plantation".
