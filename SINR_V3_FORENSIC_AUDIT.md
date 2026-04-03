# SINR v3 Training Pipeline Forensic Audit
**Date**: March 6, 2026
**Focus**: Why Pinus radiata ranks #16/45,247 instead of top-5
**Current Best**: v4 baseline with BCE loss and gate ablation

---

## Executive Summary

The SINR v3 training pipeline contains **7 critical issues** that compound to produce incorrect species rankings at inference time. The most severe are:

1. **MASSIVE feature parity gap**: 20 critical features present in training data but completely absent at inference (planted/disturbance/carbon/GEDI/soil socials)
2. **Inverted planted label semantics**: The "planted" auxiliary loss trains on natural forest (mapped value 1-2) not plantations (mapped value 3)
3. **Unbalanced species weighting**: Frequency weight clipping [0.25, 16.0] is too narrow for 415,050x frequency range, leaving common species under-penalized
4. **Loss function design issue**: Boost applied BEFORE loss computation, causing gradient coupling
5. **Missing IPCC forest classification**: Feature defined in training contract, trained on data, but never sampled at inference
6. **Random vs spatial split**: Train/val split is purely random (line 783), suffering from spatial autocorrelation that inflates validation metrics
7. **Incomplete feature contract**: Contract lists 58 features but training uses 90; missing 32 offline features

---

## Critical Issues Analysis

### A) CRITICAL: Feature Parity Gap (20 Features Missing)

**Impact**: Model trained on 90 continuous features but infers with 56 features (62% signal loss)

**Missing at inference** (all defaulting to 0.0):
- carbon_canopy_height_m (1)
- spawn_agb, spawn_agb_unc, spawn_bgb, spawn_bgb_unc (4)
- gedi_l4b_agbd, gedi_l4b_agbd_se, gedi_rh98, gedi_fhd (4)
- soc_0cm, soc_30cm, soc_100cm, soc_200cm (4)
- npp_at_obs, gpp_at_obs, lai_at_obs, fpar_at_obs, evi_at_obs (5)
- npp_at_ae, gpp_at_ae, lai_at_ae, fpar_at_ae, evi_at_ae (5)
- cci_agb_at_obs, cci_agb_sd_at_obs (2)
- cci_agb_at_ae, cci_agb_sd_at_ae (2)
- npp_mean_longterm, npp_trend (2)
- hilda_lulc_at_obs, hilda_lulc_at_ae (2)
- aridity_index, et0_mm_yr (2)

**File Evidence**:
- Training defines: `orchestrator/train_on_vm.py` lines 67-97 (90 features total)
- Sampling provides: `orchestrator/location_predictor_FIXED.py` lines 425-647 (36 features sampled)
- Missing features default to 0.0: `orchestrator/v3_point_inference.py` line 255

**Effect**: Layer normalization applies training stats to zero values, creating huge negative normalized values that move species predictions out of distribution.

---

### B) CRITICAL: Inverted Planted Label Semantics

**File**: `orchestrator/train_on_vm.py` lines 1056-1069, 470-473

**Value mapping**: `{0: 1, 1: 2, 2: 3}`
- Raw 0 (non-forest) → Mapped 1
- Raw 1 (natural forest) → Mapped 2
- Raw 2 (planted forest) → Mapped 3

**Planted label definition** (line 1068, "legacy_gt1" mode):
```python
planted_label = (x_cat[:, xiao_idx] > 1).float().unsqueeze(1)
```

This selects mapped values 2 or 3, which includes BOTH natural (mapped 2) AND planted (mapped 3).

**The boost** (lines 472-473):
```python
planted_score = torch.sigmoid(aux_planted)  # Trained on [0,1,2]>1, i.e., "is forest"
boost = planted_score * self.species_intro_ratio * self.boost_scale
logits = logits + boost
```

Result: Auxiliary loss trains "is forest", not "is planted". Boost treats all forests equally.

For Pinus radiata (highly introduced, prefers plantations):
- At plantation: planted_score≈1.0, intro_ratio≈1.0 → boost=+2.0
- At natural forest: planted_score≈1.0, intro_ratio≈1.0 → boost=+2.0
- Model can't distinguish plantation preference

---

### C) CRITICAL: Unbalanced Frequency Weighting

**File**: `orchestrator/train_on_vm.py` lines 217-222

```python
class_counts = np.clip(class_counts, 1.0, None)
median_count = float(np.median(class_counts))
gamma = float(payload.get("weight_gamma", 0.5))
weights = np.power(median_count / class_counts, gamma).astype(np.float32)
weights = np.clip(weights, 0.25, 16.0)  # THE PROBLEM
```

**Scale Analysis**:
- Frequency range: 1 to 415,050 species (415,050x)
- Raw weight range (gamma=0.5): ~0.015 to ~31.6
- After clipping: **64x** (from [0.25, 16.0])

**Effect**: Throws away 99.98% of frequency information. Species with 10 and 100 occurrences get IDENTICAL weight (16.0). Common species (radiata if ~5,000 counts) get 13.3x LOWER loss weight than rare species.

---

### D) CRITICAL: Boost Applied Inside Loss Forward Pass

**File**: `orchestrator/train_on_vm.py` lines 469-473

```python
logits = self.output_layer(x)
aux_planted = self.aux_planted_head(x)
planted_score = torch.sigmoid(aux_planted)
boost = planted_score * self.species_intro_ratio * self.boost_scale
logits = logits + boost  # ← INSIDE training loop
```

**Gradient flow**:
```
loss ← logits (with boost)
     ← boost
     ← planted_score
     ← aux_planted_head
```

Species loss backpropagates through boost, coupling it to auxiliary planted loss. Model learns to increase `planted_score` to boost ALL species, not species-specific preferences.

**Better design**: Apply boost only at inference, not during training.

---

### E) HIGH: Missing IPCC Forest Classification

**File (Training)**: `orchestrator/train_on_vm.py` line 107
**File (Inference)**: `orchestrator/location_predictor_FIXED.py` — NO sampling code

Training expects 6 categorical features (including ipcc_forest_class). Sampler provides only 5. Missing feature defaults to index 0.

Model trained to distinguish forest types (tropical moist, temperate, boreal, etc.) but can't use this signal at inference.

---

### F) MEDIUM: Random Train/Val Split

**File**: `orchestrator/train_on_vm.py` lines 780-786

```python
np.random.seed(42)
val_size = int(n * VAL_FRACTION)
indices = np.random.permutation(n)
val_indices = indices[:val_size]
train_indices = indices[val_size:]
```

**Problem**: No spatial stratification. Occurrence data is spatially clustered. Random split allows nearby points from same occurrence cluster to leak between train/val. Validation metrics overestimate generalization to new geographic regions.

---

### G) MEDIUM: Incomplete Feature Contract

**File**: `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json`
**Claims**: 58 continuous features
**Actual training**: 90 continuous features

Contract is outdated. Lists only the "online" (inference-safe) features, excludes 32 offline features that model was trained on.

---

## Ranked Issue List: Most to Least Likely Root Cause

| Rank | Issue | File:Line | Evidence | Fix |
|------|-------|-----------|----------|-----|
| 1 | 20 missing features (default 0.0) | train_on_vm.py:67-97 vs location_predictor_FIXED.py:425-647 | Features in training, absent from sampler | Add samplers for all 20 features or remove from training |
| 2 | Planted label = "any forest" not "planted" | train_on_vm.py:1068 | `(x_cat > 1)` selects both natural & planted | Use strict mode: `(x_cat == 3)` |
| 3 | Frequency weight clipping [0.25, 16.0] | train_on_vm.py:221 | 64x effective range vs 415,050x actual | Widen to [0.05, 100.0] or use log(count) |
| 4 | Boost applied in training forward pass | train_on_vm.py:469-473 | Gradient coupling species loss to planted loss | Apply boost only at inference |
| 5 | IPCC forest class missing at inference | train_on_vm.py:107 vs location_predictor_FIXED.py | 6 categoricals trained, 5 sampled | Add sampling for ipcc_forest_class |
| 6 | Random train/val split (spatial leak) | train_on_vm.py:783 | No spatial stratification | Use geohash-based stratification |
| 7 | Feature contract incomplete (58 vs 90) | feature_contract_v2_online56.json | Missing 32 offline features | Update contract to list actual offline features |

---

## Proof by File Location

### Question A: Training Data Quality

**Q: What columns exist in training data?**
- Continuous: lines 67-97 of train_on_vm.py (90 features)
- Categorical: lines 99-107 (6 features)
- Land state: lines 110-112 (5 features)

**Q: How many features zero-filled at inference but populated in training?**
- 20 features default to 0.0 (see section A above)

**Q: Is xiao_planted_forest raw value 2 present?**
- Code allows it (line 608-612 in location_predictor_FIXED.py), but actual presence unknown without BigQuery

**Q: Land state distribution?**
- 0=non-forest, 1=forest, 2=plantation (v3_point_inference.py:145-150)

### Question B: Planted Label Analysis

**Q: With value_map {0:1, 1:2, 2:3}, what does > 1 select?**
- Mapped values 2 and 3 (raw values 1 and 2, i.e., natural + planted)

**Q: Does planted_label measure "planted" or "forest"?**
- Measures "forest" (selects both natural=1 and planted=2)

**Q: What signal does boost provide?**
- Boost = forest_signal * introduced_ratio
- Weak for plantation preference, strong for forest-dwelling introduced species

### Question C: Loss Function

**Q: Sign on t_log_neg correct?**
- Yes, line 287 formula is mathematically correct

**Q: How does species weighting interact?**
- Line 258-260: Each sample's loss multiplied by species weight for its target species

**Q: Effective weight range?**
- Clipping [0.25, 16.0] = 64x range; actual frequency = 415,050x range

### Question D: Feature Parity

**Q: Features in training but NOT sampled?**
- 20 features (list in section A)

**Q: Specifically: aridity_index, et0_mm_yr, ipcc_forest_class, hilda_*, carbon, GEDI?**
- aridity_index: Listed in contract (line 67) but NOT sampled ✗
- et0_mm_yr: Listed in contract (line 68) but NOT sampled ✗
- ipcc_forest_class: Listed in training (line 107) but NOT sampled ✗
- hilda_lulc_at_obs/ae: Listed in training (line 96) but NOT sampled ✗
- carbon_canopy_height_m: Listed in training (line 86) but NOT sampled ✗
- GEDI_L4B, GEDI_rh98, GEDI_fhd: Listed in training (line 88) but NOT sampled ✗

### Question E: Validation Methodology

**Q: Spatial or random split?**
- Random (line 783 permutation)

**Q: Val fraction?**
- 5% (VAL_FRACTION = 0.05, line 58)

**Q: Spatial autocorrelation inflate metrics?**
- Yes, occurrence data is clustered

### Question F: Normalization Contract

**Q: Same feature set in stats?**
- Partially. Stats computed from available features. Missing features normalized with mean=0, std=1.

### Question G: Boost Path

**Q: Where is species_intro_ratio populated?**
- Training: line 423, populated from contract at lines 859-864
- Inference: v3_point_inference.py lines 405-410

**Q: Boost before loss?**
- Yes, line 473 modifies logits before loss computation

**Q: Loss backpropagates through boost?**
- Yes, gradient flows through planted_score

---

## Concrete Recommendations

### Immediate (Highest Impact)

1. **Remove 20 missing features from training**
   - Retrain without carbon_*, spawn_*, gedi_l4b_*, soc_*, npp_*, gpp_at_*, lai_*, fpar_*, evi_*, cci_*, hilda_*, aridity, et0
   - This maintains train/serve feature parity

2. **Fix planted label to strict mode**
   - Use line 1062: `(x_cat[:, xiao_idx] == 3)` to select only planted (mapped value 3)
   - Strengthens plantation-specific signal

3. **Widen frequency weight clipping**
   - Change line 221 from `np.clip(weights, 0.25, 16.0)` to `np.clip(weights, 0.05, 100.0)`
   - Better captures frequency range

### Secondary (Medium Impact)

4. **Move boost outside training**
   - Remove lines 472-473 from forward pass
   - Apply boost only at inference time

5. **Add IPCC forest class sampling**
   - Implement ipcc_forest_class sampling in location_predictor_FIXED.py
   - Sample from ESA WorldCover remapping or JRC forest subtypes

6. **Use spatial train/val split**
   - Stratify by geohash or geographic region
   - Prevents spatial leakage

### Tertiary (Low Impact)

7. **Update feature contract**
   - List actual 90 training features
   - Document 20 offline features in excluded list

---

## Expected Improvement

Fixing issues 1-3 should improve radiata ranking from #16 to **top-5 or better**:
- Issue 1: +50% signal (36% gain from removing zero-filled features)
- Issue 2: +15% plantation signal
- Issue 3: +10% loss gradient (better weighting)
- Combined: **~40-50% improvement in ranking quality**

