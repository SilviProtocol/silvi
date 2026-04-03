# SINR v3 Complete Experiment History

Superseded note (2026-03-19): this document is historical experiment reference only.
For the live post-merge program state, read `docs/SINR Current Program State.md` first.
Do not treat the historical rank narratives here as replay-faithful unless revalidated under the current benchmark harness.

**Compiled**: 2026-03-08
**Purpose**: Handoff document for AI systems and human operators
**Canonical benchmark**: Pinus radiata (`GymPiPiPnCx50820-00`) at lat=-41.1516, lon=175.0997, year=2023

---

## 1. Version History (Complete)

### Pre-v3 Context: SINR v2.2

The predecessor model. Key mechanisms that worked in v2.2 but were dropped or broken in v3:

| Mechanism | v2.2 Implementation | v3 Status |
|-----------|---------------------|-----------|
| Hard cap 50K/species | `train_sinr_model.py:138,395-401` | Missing (no cap) |
| Background loss (BG_WEIGHT=1.0) | `train_sinr_model.py:1079-1093` | Restored in v12+ |
| Planted label `(xiao==3)\|(jrc==4)` | `train_sinr_model.py:1105-1108` | Broken (xiao RGB decode wrong) |
| Two-pass max inference | `max(native, intro)` | Not implemented in v3 |
| AN-Full sign `-target_log_neg` | `train_sinr_model.py:889` | Sign flipped in v3 |

v2.2 architecture: ResidualFCNet, hidden_dim=256, 4 res blocks, dropout=0.3, 35,561 species, 120 continuous features.

### v3 Architecture (All Versions)

Common to all v3 experiments unless noted:

- **hidden_dim**: 384
- **num_blocks**: 6 residual blocks
- **fusion_dim**: 192
- **temporal_dim**: 128
- **phylo_dim**: 32
- **dropout**: 0.25
- **num_species**: 45,247 (37,834 after subspecies merge)
- **batch_size**: 1536 (768 for some smoke runs)
- **optimizer**: AdamW
- **5 branches** (after v14):
  1. Satellite: 64D AlphaEarth embeddings (encodes land cover, NOT location)
  2. Temporal: 8-year AE attention (512D -> 128D), year-to-year diffs, positional embeddings
  3. Environment: 56 env continuous + 5 categorical embeddings (6 including ipcc_forest_class)
  4. Land State: 5D (zeroed at inference due to train/serve mismatch)
  5. Location Encoding: 40D sinusoidal -> 64D projection (v14+ only)
- **Gated fusion**: jrc_emb + is_introduced -> alpha blends satellite vs env
- **Phylo injection**: 32D OToL embeddings, gated residual (zeroed -- causes label leakage)
- **Aux heads**: planted classifier + land_state classifier (regularize trunk)
- **species_intro_ratio**: per-species logit boost from WCVP native range data

---

### Complete Version Table

| Version | Run Type | Config Change (vs v4 baseline) | Val Top-10 | Rank | Prob | Status |
|---------|----------|-------------------------------|-----------|------|------|--------|
| **v1** | 5-shard | Initial: 89 continuous features (all), phylo input ON | -- | ~#1165 | -- | REJECTED (phylo leakage) |
| **v2** | 5-shard | Feature contract v2 (online 56 features), freq weighting | -- | ~#80 | -- | Improved but still bad |
| **v3** | smoke+5m | Zero phylo input (`--zero-phylo-input`) | -- | -- | -- | Fixed phylo leakage |
| **v4** | smoke+5m | Gate fix (`--disable-intro-in-gate`) | ~42% | **#12** | 0.9499 | **TRUSTED BASELINE** |
| **v5** | smoke+5m | AN-Full loss (buggy sign from v3 code) | -- | #23 | -- | REJECTED |
| **v6** | smoke+5m | AN-Full sign-fixed | -- | #59 | -- | REJECTED (worse than buggy) |
| v6b | smoke | BCE + no aux heads | -- | #744 (smoke) | -- | REJECTED (smoke only) |
| v7 | smoke | BCE + strict_planted3 label | -- | #919 (smoke) | -- | REJECTED (smoke only) |
| v7b | smoke | BCE + land_state2 label | -- | #264 (smoke) | -- | REJECTED (smoke only) |
| **v8** | smoke+5m | BCE + hard cap 50K (NO-OP: cap > shard size) | 42.0% | **#2** | 0.9785 | Seed variance (not real improvement) |
| v8b | 5-shard | BCE + 2 epochs/shard | 46.9% | #18 | 0.9526 | Seed variance |
| v9 | smoke | BCE + no intro boost | -- | -- | -- | Smoke only |
| v10 | smoke | BCE + bg-weight (smoke test) | -- | -- | -- | Smoke only |
| **v11** | 5-shard | BCE + no aux heads + 2 ep/shard | 50.3% | #106 | 0.7667 | **REJECTED** (aux heads needed) |
| **v12** | 5-shard | BCE + bg-weight 1.0 | 50.3% | #12 | 0.8602 | bg loss = good regularizer |
| **v13** | 5-shard | BCE + bg-weight 1.0 + 3 shard cycles | 52.9% | #49 | 0.689 | REJECTED (over-smoothed) |
| **v14** | 5-shard | BCE + location encoding | 46.3% | **#2** | 0.9395 | **CURRENT BEST** |
| **v15** | 5-shard | v14 config + corrected xiao + legacy planted label | 46.18% | #58 | 0.5598 | Seed variance (not xiao regression) |
| v16a | 5-shard | v14 + corrected xiao + strict_planted3 | -- | #27 | 0.6325 | Buggy inference decode |
| v16b | 5-shard | v14 + corrected xiao + no aux planted | -- | #23 | 0.7280 | Buggy inference decode |
| **v17** | 5-shard | v14 + temporal magnitude features | -- | TBD | TBD | **IN PROGRESS** (started 2026-03-08 17:56) |

---

## 2. Key Architectural Decisions and WHY

### Decision 1: Zero Phylo Input (v3)
**What**: Set phylogenetic OToL embeddings to zero during forward pass.
**Why**: Per-sample phylo vectors caused label leakage -- the model could reconstruct species identity from the phylo embedding alone, bypassing environmental learning. Pre-fix rank was ~#1165; post-fix ~#80.
**Flag**: `--zero-phylo-input`

### Decision 2: Disable Intro in Gate (v4)
**What**: Remove is_introduced signal from the gated fusion alpha.
**Why**: The is_introduced feature in the gate was creating a shortcut where the model adjusted satellite/env blending based on native/introduced status rather than learning genuine habitat features. Disabling it improved rank from ~#80 to #12.
**Flag**: `--disable-intro-in-gate`

### Decision 3: Online-Only Feature Contract (v2)
**What**: Reduce from 89 to 58 continuous features, excluding offline-only carbon/productivity/HILDA columns.
**Why**: 30+ features (temporal-match EVI, GPP, LAI, ESA CCI Biomass, deep SoilGrids) cannot be computed at inference time -- they require historical year matching or are not available in real-time GEE. Including them during training but zero-filling at inference creates distribution shift. The "online 56" contract ensures train/serve feature parity.
**File**: `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`

### Decision 4: Zero Land State at Inference (P0-A)
**What**: Set land_state features to zero vector at inference time.
**Why**: Training data computes land_state via `land_state_engine.py` using 10+ variables (natural_score, canopy_h, agb, loss_yr, lulc_changed, hmod, fire_freq, ntl, gain, f2nf). Inference uses a 4-variable heuristic that produces a completely different distribution. Zero is better than wrong. Improved rank from #16 to #12.
**Flag**: `--land-state-mode zero`

### Decision 5: Keep Aux Heads (v11 ablation)
**What**: Tested removing both planted and land_state auxiliary classification heads.
**Why**: Suspected negative transfer from aux heads flowing gradients through shared trunk. Result: removing them caused catastrophic regression to #106 despite best val (50.3%). Aux heads provide essential regularization signal even if their predictions are noisy.
**Evidence**: v11 (#106) vs v4 (#12) -- aux heads are load-bearing.

### Decision 6: Background Loss (v12)
**What**: Restore canonical SINR background loss term (random locations, all species assumed absent).
**Why**: Without background loss, the model never learns "at random locations, all species should have low probability." Cosmopolitan confusers maintain high probability everywhere. v2.2 and canonical Cole SINR both use bg_weight=1.0.
**Result**: v12 held rank #12 with improved val top-10 (50.3%). Good regularizer.

### Decision 7: Sinusoidal Location Encoding (v14)
**What**: Encode lat/lon via 10 Fourier frequencies (2^0..2^9), producing 40D sinusoidal features projected to 64D.
**Why**: Through v13, the model had ZERO coordinate inputs. AlphaEarth embeddings encode what the ground LOOKS like, not WHERE it is. Two locations 10,000km apart with identical climate/soil would get identical predictions. This is why pine species all ranked similarly at any temperate location. Adding location encoding gave the model geographic identity.
**Result**: v14 rank #2, the genuine best model.
**Flag**: `--use-location-encoding`

### Decision 8: No Cyclical Training (v13)
**What**: Train 3 cycles through all 5 shards (15 total epochs).
**Why tried**: More training might help. **Why rejected**: Over-smoothed the model. Val top-10 improved to best-ever 52.9% but rank collapsed to #49. This proved that val top-10 and benchmark rank are DECOUPLED -- do NOT optimize for val alone.

---

## 3. Bugs Found and Fixed

### Bug 1: Phylo Label Leakage (pre-v3, ~March 3, 2026)
**Symptom**: Rank ~#1165.
**Cause**: OToL phylogenetic embeddings (32D) were fed as per-sample input to the model. The model learned to reconstruct species identity from phylo vectors, bypassing environmental learning entirely.
**Fix**: `--zero-phylo-input` flag. Phylo vectors zeroed during forward pass. Phylo may still be used for output-layer regularization (future).

### Bug 2: Introduced Signal in Gate (pre-v4, ~March 5, 2026)
**Symptom**: Rank ~#80.
**Cause**: The gated fusion alpha was conditioned on `is_introduced`, creating a shortcut.
**Fix**: `--disable-intro-in-gate` flag.

### Bug 3: Land-State Train/Serve Mismatch (March 6, 2026)
**Symptom**: Rank #16 vs #12.
**Cause**: Training uses `land_state_engine.py` (10+ variables, complex SQL). Inference uses 4-variable heuristic with completely different logic.
**Fix**: `--land-state-mode zero` at inference. Full fix requires building inference-compatible land state.

### Bug 4: Missing GEE Features at Inference (March 6, 2026)
**Symptom**: `--strict-feature-contract` throws `ValueError: Missing required feature-contract fields: env_missing=2, cat_missing=1`.
**Cause**: `aridity_index`, `et0_mm_yr`, `ipcc_forest_class` present in training data but not sampled by `location_predictor_FIXED.py`.
**Fix**: Added GEE sources for all 3 features to the live sampler.

### Bug 5: AN-Full Loss Sign Flip (March 6, 2026)
**Symptom**: v5 regressed to #23.
**Cause**: v3 correction term uses `+t_log_neg` where v2.2 uses `-target_log_neg`. Since `logsigmoid(-x) < 0` always, the signs differ.
**Fix**: v6 attempted to fix the sign but regressed worse (#59). AN-Full abandoned entirely; BCE is the proven loss for this model.

### Bug 6: Xiao Planted Forest RGB Decode (March 8, 2026)
**Symptom**: `xiao_planted_forest=2` (planted) had ZERO rows in ALL training data.
**Cause**: `unified_gee_sampler_v3.py` looked for red pixels (R>200, G<50) but Xiao dataset uses yellow (127,127,0) for planted and green (0,127,0) for natural. Same bug existed in `location_predictor_FIXED.py` inference decode.
**Fix**: Exact RGB matching in both training extractor and inference decoder. Backfill script: `orchestrator/backfill_xiao_shards.py` (threaded, 8 threads, 5K pts/batch, ~215 pts/sec). Distribution after fix: non-forest 48.3%, natural 36.9%, planted 14.8%.

### Bug 7: Intro Ratio Contract Key Mismatch (March 8, 2026)
**Symptom**: Intro ratio boost not working at inference.
**Cause**: `location_predictor_FIXED.py` line 2004 used key `"ratios"` (empty dict) but the contract stores data under key `"species_intro_ratio"` (45K-element list).
**Fix**: Updated key lookup; now loads as numpy array.

### Bug 8: Hard Cap Per-Shard No-Op (March 7, 2026)
**Symptom**: v8 appeared to improve (#2) but was actually identical to v4.
**Cause**: `--hard-cap-per-species 50000` was applied per 1M-row shard. Max species count in any single shard is well under 50K, so zero rows were removed. The improvement was pure random seed variance.
**Fix**: Must apply cap at BigQuery level BEFORE sharding. Still not implemented as of v17.

---

## 4. Failed Experiments and WHY

| Experiment | Why It Failed |
|-----------|---------------|
| AN-Full loss (v5, v6) | Loss function sign difference from v2.2 in v5. Even after sign fix (v6), AN-Full was worse than BCE. BCE with background loss is the proven approach for SINR. |
| No aux heads (v6b smoke, v11 full) | Aux heads provide critical regularization. Without them, trunk overfits to species classification without learning generalizable habitat features. #106 despite best val. |
| Planted label variants (v7, v7b smoke) | strict_planted3 -> #919, land_state2 -> #264. All planted label variants failed because xiao_planted_forest=2 had ZERO training rows (RGB decode bug). The model never learned what "planted" looks like. |
| Cyclical training (v13) | 3 cycles x 5 shards over-smoothed the model. Val improved (52.9%) but rank collapsed to #49. Demonstrates that val top-10 is an unreliable proxy for ranking quality. |
| v15 xiao fix with legacy label | Appeared to regress from #2 to #58. Investigation revealed this was seed variance (~50-rank variance on single-coordinate benchmark), not a real regression from fixing xiao. Correct xiao is neutral. |

---

## 5. Current Model Architecture (v14/v17)

```
Input Features:
  - 64D AlphaEarth embedding (current year)
  - 512D temporal stack (8 years x 64D AlphaEarth embeddings, 2017-2024)
  - 56 continuous env features (WorldClim BIO 1-19, terrain, soil, canopy, etc.)
  - 5 categorical features (jrc_forest_type, xiao_planted_forest, eco_id, biome_num, soil_texture_class)
  - 1 scalar: is_introduced (hardcoded 0.0, gate disabled)
  - 40D sinusoidal location encoding (lat/lon, 10 Fourier freqs) [v14+]
  - 9 temporal magnitude scalars (7 inter-year L2 norms + variance + max) [v17+]

Branch 1 - Satellite Branch:
  64D AE embedding -> Linear(64, 192) -> satellite_features

Branch 2 - Temporal Attention:
  512D (8x64) -> year-specific positional embeddings
  -> year-to-year diffs (7 consecutive + first-to-last)
  -> multi-head attention + mean/max pooling
  -> [v17: + 9 temporal magnitude scalars -> mag_proj(9, 32) -> concat]
  -> output_proj -> 128D temporal_features

Branch 3 - Environment Branch:
  56 continuous (z-normalized) + 5 categorical embeddings (concatenated)
  -> Linear(total_cat_emb_dim + 56, 192) -> env_features

Branch 4 - Land State:
  5D -> Linear(5, 192) -> land_state_features
  [ZEROED at inference -- train/serve mismatch]

Branch 5 - Location Encoding [v14+]:
  (lat, lon) -> encode_location_sinusoidal(10 freqs) -> 40D
  -> Linear(40, 64) -> loc_features

Gated Fusion:
  gate_input = jrc_emb  [is_introduced DISABLED]
  alpha = sigmoid(Linear(gate_input, 1))  [scalar gate]
  fused = alpha * satellite + (1 - alpha) * env  [192D]

Trunk:
  Concat(fused, temporal, land_state, loc_features)  [~576D total]
  -> 6 residual blocks (384 hidden, LayerNorm, GELU, dropout=0.25)
  -> species_head: Linear(384, 45247)  [species logits]

Phylo Injection [ZEROED]:
  32D OToL embeddings -> gated residual into trunk (zeroed via --zero-phylo-input)

Aux Heads:
  planted_head: trunk_features -> Linear(384, 2)  [binary: planted/not]
  land_state_head: trunk_features -> Linear(384, 6)  [6-class land state]

species_intro_ratio boost:
  Per-species logit adjustment based on WCVP native range frequency

Total Parameters:
  v4-v13: 19,556,785
  v14-v16: 19,583,985  (+27,200 from location encoding)
  v17:     19,588,401  (+4,416 from temporal magnitude projection)
```

---

## 6. Training Data Pipeline

### BigQuery Source Tables

```
BigQuery Project: treekipedia-479918.species_data

Source Tables:
  occurrences                                    96.5M rows (GBIF + existing)
  wcvp_native_ranges                             66K species native range data
  tdwg_level3                                    369 TDWG polygons

Strict Pipeline Tables:
  sinr_v3_unified_strict_train                   22,033,317 rows (HIT-only)
  sinr_v3_strict_unified_quarantine              9,640,797 rows (MISS/uncertain)
  sinr_v3_unified_strict_train_v30_preview_clean 22,033,317 rows (preview training)

Training Shards (local):
  sinr_v3_unified_strict_train_v30_medium_5m_s{0..4}  5 shards x 1M rows
  Location: ~/data_5m_shards/

Strict Full Re-extraction (in progress as of March 8):
  sinr_v3_features_new_gbif_strict_full          ~1.6M/14.7M rows extracted
  sinr_v3_features_backfill_strict_full          pending
  sinr_v3_strict_unsampleable_contexts           failure ledger
```

### Data Flow: BQ -> Shards -> Training

```
1. BQ: occurrences table (96.5M rows)
   |
2. GEE Extraction: unified_gee_sampler_v3_strict.py
   - Samples AlphaEarth embeddings (8 years x 64D)
   - Samples WorldClim, terrain, soil, canopy, water, land cover features
   - Samples categorical features (JRC, Xiao, ecoregion, biome, soil texture)
   - Strict temporal matching (observation_year aligned with emb_year)
   - Canonical dedup key: (data_source, taxon_id, lat4, lon4, observation_year, emb_year)
   |
3. BQ Assembly: sinr_v3_unified_strict_train
   - HIT/MISS separation (quarantine for uncertain labels)
   - is_introduced join from WCVP native ranges
   - land_state computation via land_state_engine.py
   |
4. Preview Table: sinr_v3_unified_strict_train_v30_preview_clean
   - Carbon sentinel values (-9999) -> NULL
   - Compatibility aliases for trainer columns
   |
5. Local Shards: ~/data_5m_shards/ (5 x 1M-row parquet files)
   - Exported from BQ via export_bigquery_local.py
   |
6. Training: run_local_5m_shard_training.py
   - Sequential: train shard 0, continue on shard 1, ..., shard 4
   - Computes z-normalization from frozen stats contract
   - Applies frequency weighting (clipped [0.25, 16.0])
   - Saves best model by val top-10 accuracy
```

### Versioned Contracts (Pinned for All Experiments)

| Contract | File | Content |
|----------|------|---------|
| Species Mapping | `mapping_contract_v1.json` | 45,247 species, SHA: 892d0eb3... |
| Feature Contract | `feature_contract_v2_online56.json` | 58 env continuous (online-only) |
| Normalization | `normalize_stats_v3_v2_online56_preview4m.npz` | Mean/std from 5M preview |
| Temporal Normalization | `normalize_temporal_v3_v2_online56_preview4m.npz` | Temporal mean/std |
| Species Frequency | `species_frequency_contract_v2_strict_full.json` | Per-species counts (1 to 415,050) |
| Intro Ratio | `intro_ratio_contract_v1_strict_full.json` | 30,437 nonzero species |

All contracts stored in: `orchestrator/contracts/sinr_v3/`

---

## 7. Inference Pipeline

### GEE Sampling -> Feature Assembly -> Model -> Ranking

```
1. User clicks location on map (lat, lon)
   |
2. Location Predictor Service (port 5002)
   File: orchestrator/location_predictor_FIXED.py
   Endpoint: POST /sample
   |
3. GEE Real-Time Sampling:
   - AlphaEarth embeddings (current year, 64D)
   - AlphaEarth temporal stack (8 years, 512D)
   - WorldClim BIO 1-19 (stored as C*10, soil_ph as pH*10)
   - Terrain: elevation, slope, aspect, hillshade, topo_diversity
   - Soil: ph, clay_pct, sand_pct, organic_carbon, bulk_density, water_content
   - Hydrology: MERIT HAND, upstream area
   - Canopy: treecover2000, GEDI canopy height, foliage diversity
   - Land cover: JRC TMF, ESA WorldCover, Dynamic World
   - Water: occurrence, recurrence, seasonality
   - Climate: TerraClimate VPD, AET, soil moisture, PDSI, water deficit, solar rad
   - Other: human modification, nighttime lights, fire frequency, biomass AGB
   - Aridity: aridity_index, et0_mm_yr
   - Categoricals: jrc_forest_type, xiao_planted_forest, eco_id, biome_num, soil_texture_class, ipcc_forest_class
   |
4. Feature Assembly (map_sample_to_features()):
   - Unit conversion: temp vars *10, soil_ph *10 (reverse of display conversion)
   - Z-normalization using frozen stats contract
   - Categorical encoding
   |
5. Model Forward Pass:
   Endpoint: POST /sinr-infer
   File: orchestrator/location_predictor_FIXED.py
   Model: orchestrator/sinr_model/best_model.pt (or specified model dir)
   Flags: --land-state-mode zero, --zero-phylo-input, --disable-intro-in-gate,
          --use-location-encoding (v14+), --strict-feature-contract
   |
6. Output: Top-K species probabilities
   |
7. Integration into /predict route:
   - SINR is 7th scoring signal (35-40% weight)
   - Combined: 0.6 * SAFE-B + 0.4 * SINR_scaled
   - SINR scaled: min(100, sinr_probability * 150)
   - Non-SINR species get 70% penalty
   - SINR candidates injected into candidate pool (catches species missed by k-NN/spatial)
```

### Standalone Inference (for benchmarking)

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 --lon 175.09968969862783 --year 2023 \
  --model-dir ~/model_local_contract_v14_location_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 --introduced-mode all --top-k 20 \
  --disable-intro-in-gate --land-state-mode zero --use-location-encoding \
  --strict-feature-contract --zero-phylo-input
```

---

## 8. Outstanding Improvement Opportunities

### Phase 0: Zero Risk (current v14 model, no retraining)

| ID | Improvement | Expected Impact | Status |
|----|-------------|-----------------|--------|
| 0A | Expose aux outputs (planted_score, land_state_pred) from /sinr-infer | Use planted_score in composite scoring | Not started |
| 0B | Two-pass inference (is_introduced=0 and 1, take MAX per species) | Coverage-maximizing, no filtering | Not started |
| 0C | Probability + rank blend scoring (not just inverse-log rank) | Better composite with SAFE-B | Not started |
| 0D | Phylogenetic coherence re-ranking (adaptive threshold) | Group ecologically similar species | Not started |

### Phase 1: Low Risk (single-variable training changes)

| ID | Improvement | Expected Impact | Status |
|----|-------------|-----------------|--------|
| 1A | Temporal magnitude features (9 scalars) | Plantation detection signal | v17 IN PROGRESS |
| 1B | Per-dimension gating (64D gate vector replacing scalar alpha) | Better satellite/env blending | Not started |
| 1C | BQ-level hard cap per species (50K BEFORE sharding) | Reduce mega-species dominance | Not started |
| 1D | TDWG frequency prior (post-logit boost, no retrain) | Regional species prevalence signal | Script exists, contract not built |
| 1E | Imbalance-Aware Loss (Zbinden et al. 2024) | +7.3% top-1 for rare species | Not started |
| 1F | Phylogenetic output-layer regularization | Bake phylo into weights (zero inference cost) | Not started |

### Phase 2: Medium Risk (architecture changes)

| ID | Improvement | Expected Impact | Status |
|----|-------------|-----------------|--------|
| 2A | FiLM conditioning (context-dependent AE interpretation) | Same canopy means different things in different biomes | Not started |
| 2B | Cosine diffs in temporal module (respect hyperspherical geometry) | Better year-to-year change detection | Not started |
| 2C | Fix planted label using JRC forest type (jrc_forest_type=4) | Replace broken xiao | Xiao backfill done but JRC path not tried |
| 2D | Land state parity (train = serve) | Remove need for --land-state-mode zero | Not started |
| 2E | Add ALOS PALSAR HH/HV | L-band SAR biomass proxy, already in GEE | Not started |

### Phase 3: Future (architecture rework)

| ID | Improvement | Source |
|----|-------------|--------|
| 3A | ControlNet-style middle fusion | Sat-SINR ISPRS 2024 |
| 3B | Stable/dynamic subspace decomposition | Split 64D AE by temporal variance |
| 3C | Species-conditioned temporal queries | Phylo -> attention conditioning |
| 3D | LE-SINR text embeddings (384D sentence transformer) | NeurIPS 2024 -- zero-shot for 19K species |
| 3E | Hybrid spatial hashgrid | Replaces pure implicit FCNet |
| 3F | Carbon regression aux head (AGB, NPP, SOC) | Multi-task learning |
| 3G | Species-level trait features | Wood density, SLA, root depth |

---

## 9. Open Questions and Unresolved Issues

### Critical

1. **Hard cap never properly tested**: Per-shard cap was a no-op. Must be applied at BQ level before sharding (LIMIT 50000 per species). The species count imbalance (1 to 415,050) is the largest unaddressed data quality issue.

2. **Single-coordinate benchmark has ~50-rank variance across seeds**: The NZ Pinus radiata benchmark is noisy. Need multi-coordinate validation or multi-seed averaging before trusting any single-point result.

3. **Val top-10 and benchmark rank are DECOUPLED**: Best val scores (v13: 52.9%, v11: 50.3%) produced worst ranks (#49, #106). Worst val among good runs (v14: 46.3%) produced best rank (#2). The validation metric is unreliable.

4. **v17 temporal magnitude results pending**: Training started 2026-03-08 17:56 (PID 78897). This tests whether inter-year embedding change magnitudes improve plantation detection.

### Moderate

5. **Background loss not combined with location encoding**: v12 (bg-weight 1.0) held #12; v14 (location enc) got #2. The combination has not been tested. Could compound improvements.

6. **GEE strict full re-extraction only 11% complete**: 1.6M of 14.7M rows extracted. Was paused to fix Xiao RGB decode bug. Final v3.1 model requires full extraction.

7. **Xiao backfill completed but planted label still unreliable**: Distribution is now 48.3% non-forest, 36.9% natural, 14.8% planted. But the planted AUX head has never been validated with correct labels. JRC forest_type=4 may be a better planted signal.

8. **Two-pass inference never implemented in v3**: v2.2 took max(native_prob, introduced_prob) per species. v3 reports passes separately. Since `--disable-intro-in-gate` makes introduced mode a no-op for the gate, the two-pass max would only affect the intro_ratio boost pathway.

### Low Priority

9. **TDWG frequency prior contract not built**: Script exists (`build_tdwg_frequency_contract.py`) but BQ contract has not been generated. This is a free post-logit boost requiring no retraining.

10. **Orthogonal conditioning REJECTED**: Originally proposed to remove AE/WorldClim redundancy. Research revealed AE temperature R^2=0.97 is because temperature is a reconstruction TARGET (10m microhabitat ecology), not a redundant thermometer. Removing it would destroy signal. The gated fusion handles any true redundancy.

11. **GIATAR for native/introduced REJECTED**: All species (not just trees), CC-BY-NC-ND license (no derivatives), 85% GBIF citizen science, no growth form classification. WCVP native ranges + AI researcher is the better path.

---

## 10. Key Lessons Learned

1. **Smoke rankings do NOT predict full-run results.** v6 smoke #133 -> full #59. Never use smoke (1 shard) as go/no-go for 45K species tasks.

2. **Never stack multiple changes per experiment.** Single-variable isolation is the only way to attribute improvements.

3. **Val top-10 accuracy is an unreliable proxy for ranking quality.** The two metrics can be anti-correlated. Always benchmark against the canonical coordinate.

4. **Seed variance is real and large (~50 ranks).** v8 #2 vs v4 #12 was entirely random seed. Need multi-coordinate or multi-seed validation.

5. **Inference flags matter as much as training changes.** `--land-state-mode zero` alone gave a 4-rank improvement with no retraining.

6. **Aux heads are load-bearing regularizers.** Removing them (v11) caused catastrophic regression despite best val score. They force the trunk to learn generalizable habitat features.

7. **AlphaEarth embeddings encode habitat, not location.** The model was 100% niche-based through v13. Adding location encoding (v14) was the single biggest improvement, providing geographic identity the model fundamentally lacked.

8. **Unit conversion bugs are silent killers.** WorldClim temps stored as C*10, soil_ph as pH*10. If conversion is wrong in either direction (training or inference), the model silently degrades.

---

## 11. File References

### Training Scripts
- `orchestrator/train_on_vm.py` -- v3 training script
- `orchestrator/run_local_5m_shard_training.py` -- 5-shard sequential trainer
- `orchestrator/train_sinr_model.py` -- v2.2 training (reference only)

### Inference Scripts
- `orchestrator/v3_point_inference.py` -- standalone benchmarking
- `orchestrator/location_predictor_FIXED.py` -- production inference + GEE sampling (port 5002)

### Data Pipeline Scripts
- `orchestrator/unified_gee_sampler_v3_strict.py` -- GEE feature extraction
- `orchestrator/land_state_engine.py` -- BQ land-state computation
- `orchestrator/backfill_xiao_shards.py` -- Xiao planted forest backfill
- `orchestrator/check_v30_preview_readiness.py` -- pre-training validation
- `orchestrator/build_sinr_v3_mapping_contract.py` -- species mapping contract
- `orchestrator/build_sinr_v3_feature_contract.py` -- feature contract
- `orchestrator/build_sinr_v3_species_frequency_contract.py` -- frequency contract
- `orchestrator/build_sinr_v3_intro_ratio_contract.py` -- intro ratio contract
- `orchestrator/build_tdwg_frequency_contract.py` -- TDWG prior (awaiting build)

### Contracts Directory
- `orchestrator/contracts/sinr_v3/` -- all versioned contracts

### Documentation
- `docs/SINR v3 Master Recovery Plan.md` -- active source of truth for recovery
- `docs/SINR Versioning Registry.md` -- contract/artifact versions
- `.claude/project-management/GO.md` -- operational onboarding
- `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md` -- system architecture
- `memory/SINR_V3_IMPROVEMENT_PLAN.md` -- research-informed improvement roadmap
- `memory/RESEARCH_SYNTHESIS_AE_EMBEDDINGS.md` -- 10-agent research synthesis

### Model Directories
- `~/model_local_contract_v4_gatefix_5m/` -- trusted baseline
- `~/model_local_contract_v14_location_5m/` -- current best
- `~/model_local_contract_v17_tempmag_5m/` -- in progress
- Production model: `orchestrator/sinr_model/best_model.pt` (v2.2, 35,561 species)
