# Missing GEE Datasets for Feature Parity

**Date**: March 6, 2026
**Status**: Implementation blockers identified

## Overview

The v3 inference pipeline is missing 3 features that are declared in training and feature contracts but not sampled at inference time. All three need to be added to `location_predictor_FIXED.py:sample_sinr_env_features()`.

---

## Missing Continuous Features (2)

### 1. Aridity Index

**Expected**: Declared in train_on_vm.py line 95, feature_contract_v2_online56.json line 67

**Purpose**: Climate aridity metric (0=humid to 1=arid)

**Potential GEE Sources**:
- CGIAR Aridity Index (30-arc-second): `CGIAR/ARIDSOIL/raster/aridity`
- TerraClimate-derived (already sampled for other vars): Could compute from VPD/precipitation
- WorldClim Aridity Index (alternative): If available in EE catalog

**Sampling Recommendations**:
```python
# Option 1: CGIAR Aridity (30m, global)
bands.append(
    ee.Image('CGIAR/ARIDSOIL/raster/aridity')
    .select('aridity').rename('aridity_index').unmask(0).toFloat()
)

# Option 2: Compute from TerraClimate VPD (already sampled)
# aridity ≈ VPD / mean_annual_precip (needs normalization)
```

**Normalization**: Check training data for mean/std values for standardization

---

### 2. ET0 (Reference Evapotranspiration)

**Expected**: Declared in train_on_vm.py line 95, feature_contract_v2_online56.json line 68

**Purpose**: Reference evapotranspiration in mm/year (water availability indicator)

**Potential GEE Sources**:
- TERRACLIMATE ET (already using TerraClimate): Extract 'pet' (potential evapotranspiration)
- FAO Penman-Monteith: If precomputed dataset exists in EE
- Computed from TerraClimate components: Temperature, wind, radiation

**Sampling Recommendations**:
```python
# Use TerraClimate PET (already have TC data access)
# In the TerraClimate sampler (around line 591-600):
tc = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
      .filterDate(f'{tc_start}-01-01', f'{tc_end}-01-01')
      .select(['vpd', 'aet', 'soil', 'pdsi', 'def', 'srad', 'pet'])  # ← ADD 'pet'
      .mean())

bands.append(tc.select('pet').rename('et0_mm_yr').unmask(0).toFloat())
```

**Scale**: TerraClimate PET is in mm/month, may need annual sum or mean

**Normalization**: Check training data for expected range

---

## Missing Categorical Features (1)

### 3. IPCC Forest Classification

**Expected**: Declared in train_on_vm.py line 107, feature_contract_v2_online56.json line 76

**Config**: vocab_size=10, emb_dim=4, no value_map

**Purpose**: IPCC forest type classification (primary/secondary/planted distinction)

**Potential GEE Sources**:
- JRC GFC2020 forest subtypes (already used for `jrc_forest_type`): Could extract more detail
- ESA WorldCover forest subcategories (already sampled)
- Copernicus Forest Type Map (if available in EE)
- Combined logic from multiple sources (Xiao + JRC + ESA)

**Sampling Recommendations**:

Option 1: Direct source (if exists):
```python
# If dedicated IPCC dataset exists in EE
bands.append(
    ee.Image('dataset/ipcc_forest_classification')
    .select('class').rename('ipcc_forest_class').unmask(0).toFloat()
)
```

Option 2: Derived from existing data:
```python
# Synthesize from xiao (plantation detection) + JRC + ESA worldcover
# ipcc_class mapping:
# 0 = no forest
# 1 = primary forest
# 2 = secondary forest (natural)
# 3 = planted (from xiao=2)
# etc. (up to 10 classes)

# Logic:
# if xiao_planted == 2: ipcc_class = 3 (or category for planted)
# elif jrc_forest_type == 10: ipcc_class = 1 (primary)
# elif jrc_forest_type == 1: ipcc_class = 2 (natural regen)
# elif esa_worldcover has forest: ipcc_class = 2 (secondary default)
# else: ipcc_class = 0 (no forest)
```

**Complexity**: Requires reverse-engineering the IPCC class definition from training data distribution

---

## Integration Steps

### 1. Location Predictor Update (HIGH PRIORITY)

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/location_predictor_FIXED.py`

**Function**: `sample_sinr_env_features()` (lines 425-647)

**Insertion Points**:
- Add aridity_index and et0_mm_yr to the bands list in `sample_sinr_env_features()`
- Should be added around lines 540-545 (after biomass/before human modification)

**Testing**: After modification, test with:
```bash
curl -X POST http://localhost:5002/sample \
  -H "Content-Type: application/json" \
  -d '{"lat": -14.2644, "lon": -52.7344, "year": 2023}'
```

Verify that returned `sinr_env` includes:
- `aridity_index`
- `et0_mm_yr`
- (if adding ipcc): `ipcc_forest_class`

### 2. v3 Point Inference Testing (MEDIUM PRIORITY)

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/v3_point_inference.py`

**Test with Strict Contract**:
```bash
python3 v3_point_inference.py \
  --lat -14.2644 --lon -52.7344 --year 2023 \
  --strict-feature-contract
```

Should NOT raise ValueError after fixes are applied.

### 3. Verify Training Data Alignment (MEDIUM PRIORITY)

Check BigQuery training table (`sinr_v3_unified_v2_final`) for:
- aridity_index values (range, distribution, null count)
- et0_mm_yr values (range, distribution, null count)
- ipcc_forest_class distribution (if using it)

This ensures inference sampling will be normalized correctly.

---

## Current Workaround

The inference pipeline currently works WITHOUT these 3 features because:

1. **map_sample_to_features()** (lines 1512-1569) fills missing features with 0.0
2. **align_normalization()** (lines 266-284) can pad missing features with mean/std=1.0
3. Model handles zero-initialized features without crashing

However:

- Inference results are suboptimal (using fallback zeros instead of real data)
- `--strict-feature-contract` flag will fail (intentional validation)
- Training/serve distribution mismatch (model trained on real aridity/ET0, infers on zeros)

---

## Implementation Timeline

**Week 1**:
1. Identify exact GEE asset paths for aridity_index and ET0
2. Add sampling logic to location_predictor_FIXED.py
3. Test /sample endpoint returns new features

**Week 2**:
1. For ipcc_forest_class: Decide between direct source or derived logic
2. Implement ipcc_forest_class sampling
3. Verify all 3 features in v3_point_inference.py strict mode

**Week 3**:
1. Update feature contract SHA256 (if feature set changed)
2. Validate normalization stats alignment
3. Run comparative inference tests with/without new features

---

## Questions for Data Team

1. **Aridity Index**: Is CGIAR/ARIDSOIL the official source for this project? Any internal preprocessing?

2. **ET0**: Should we use TerraClimate PET or compute from components? Is annual sum or mean expected?

3. **IPCC Forest Class**: Is this a real dataset in GEE, or synthesized from other sources in training? If synthesized, what's the mapping logic?

4. **Training Data**: Can you provide the aridity_index and et0_mm_yr distributions from the training table? (mean, std, min, max)
