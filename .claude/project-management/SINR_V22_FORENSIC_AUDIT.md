# FORENSIC AUDIT: SINR v2.2 Training Script (train_sinr_model.py)
**Purpose**: Identify what v2.2 does RIGHT that v3 dropped to enable superior P. radiata performance.
**Date**: March 6, 2026
**File**: orchestrator/train_sinr_model.py (1434 lines)

---

## 1. HARD_CAP_PER_SPECIES: Value & Implementation

**Line 138**: `HARD_CAP_PER_SPECIES = 50000`

**Lines 395-401** (Application):
```python
df = df.groupby("taxon_id", group_keys=False).apply(
    lambda g: g.sample(n=min(len(g), HARD_CAP_PER_SPECIES), random_state=42)
)
```

Groups by species, samples min(count, 50k) per species with seed 42.
Prevents dominance; balances learning across species.

---

## 2. AN-Full Loss Function (Lines 846-903)

**Mathematical Formula**:
```
loss_per_sample = loss_neg + correction

loss_neg = mean_s(-log(1-sigmoid(logit_s)))
correction = (-target_log_neg + pos_weight × (-target_log_pos)) / num_species

weighted_loss = mean(loss_per_sample × sample_weight)

if bg_logits:
  loss_bg = mean_s(-log(1-sigmoid(bg_logit_s)))
  weighted_loss += bg_weight × loss_bg
```

**Key Constants**:
- **Line 134**: `POS_WEIGHT = 2048.0` (scales for ~44K assumed negatives)
- **Line 140**: `BG_WEIGHT = 1.0` (equal to observed loss)

Correction term uses SUBTRACTION for both negative and positive, with pos_weight as multiplier.

---

## 3. Background Loss (Lines 1079-1091)

Randomly samples BATCH_SIZE from training data (not true random locations).
All species assumed absent for background.

**Computation (Lines 896-899)**:
```python
bg_log_neg = F.logsigmoid(-bg_logits)
loss_bg = -bg_log_neg.mean()
weighted_loss = weighted_loss + bg_weight * loss_bg
```

BG_WEIGHT=1.0 makes background equally important as observed.

---

## 4. Planted Label (Lines 1105-1114)

```python
planted_label = ((xiao_vals == 3) | (jrc_vals == 4)).float()
has_data = (xiao_vals > 0) | (jrc_vals > 0)
if has_data.any():
    aux_loss = F.binary_cross_entropy_with_logits(...)
    loss = loss + 0.1 * aux_loss
```

Label=1 if xiao==3 OR jrc==4. Only computed where has_data=True.
10% weight on auxiliary loss.

---

## 5. Model Architecture

**Input Dims**: 64 (AE) + 56 (env cont) + 52 (emb) = 172D

**Categorical embeddings** (52D total):
- jrc_forest_type → 3D
- xiao_planted_forest → 3D
- eco_id → 32D
- biome_num → 8D
- soil_texture_class → 6D

**Layers**:
- Gated fusion: sat(64→128) + env(108→128) with α gate(4D→1D)
- input_layer: 128 → 256
- [ResidualBlock(256)]×4
- output_layer: 256 → num_species (no bias)

---

## 6. Two-Pass Inference

NOT in training. Training is single-pass.
Two-pass happens at inference time in location_predictor_FIXED.py.

---

## 7. Sample Weighting (Lines 815-818)

```python
self.sample_weight = np.clip(qw * dw, 0.01, 10.0)
```

Quality × density, clipped to [0.01, 10.0].
Applied: `weighted_loss = (loss_per_sample * sample_weight).mean()`

---

## 8. Training Hyperparameters

```python
BATCH_SIZE = 2048
NUM_EPOCHS = 12
LEARNING_RATE = 0.0005
LR_DECAY = 0.98  # ExponentialLR gamma/epoch
POS_WEIGHT = 2048.0
DROPOUT = 0.3
HIDDEN_DIM = 256
NUM_RES_BLOCKS = 4
HARD_CAP_PER_SPECIES = 50000
VAL_FRACTION = 0.05
BG_WEIGHT = 1.0
GRADIENT_CLIP_NORM = 1.0  # Line 1122
```

Optimizer: Adam(lr=0.0005) + ExponentialLR(gamma=0.98)

---

## 9. Features Used (61 ENV_FEATURE_COLS)

Topography: elevation, slope, aspect, hillshade, topo_diversity
WorldClim: bio01-bio19 (19 vars)
Soil: soil_ph, clay_pct, sand_pct, organic_carbon, texture_class, bulk_density, water_content
Forest: treecover2000, lossyear, jrc_forest_type, jrc_tmf_status, jrc_tmf_degrad_year
Land cover: esa_worldcover_2021, dynamic_world, sbtn_natural_land
Water: water_occurrence, recurrence, seasonality
Hydrology: merit_hand_m, merit_upstream_area_km2
Canopy: gedi_canopy_height_m, gedi_foliage_height_div
Productivity: modis_gpp_mean, biomass_agb_mgha
Disturbance: human_modification, nighttime_lights, fire_frequency_count
Ecoregion: eco_id, biome_num
Climate: tc_vpd_mean, tc_aet_mean, tc_soil_moisture_mean, tc_pdsi_mean, tc_water_deficit_mean, tc_solar_rad_mean
Plantation: xiao_planted_forest, neumann_natural_prob

All 120 continuous + 52 categorical used in training.

---

## 10. Gate Mechanism (Lines 96-100)

**GATE_FEATURES = ["jrc_forest_type"]** (4D gate input):
- jrc_forest_type embedding (3D)
- is_introduced (1D)

v2.2 explicitly reverted from v2.1 which included xiao/neumann.
Reason: Xiao only 24% accurate for P. radiata.

**Gate network** (Lines 560-565):
```python
nn.Sequential(
    nn.Linear(4, 16),
    nn.ReLU(inplace=True),
    nn.Linear(16, 1),
    nn.Sigmoid(),
)
```

**Fusion** (Line 659):
```python
x = alpha * sat_h + (1 - alpha) * env_h
```

α=1 trusts satellite visual, α=0 trusts environment.

---

## CRITICAL PRINCIPLES

1. Hard cap 50k/species prevents dominance
2. Gate only jrc (not noisy xiao) learns robust patterns
3. pos_weight=2048 scales for ~44k negatives
4. BG_WEIGHT=1.0 makes background equally important
5. All 120+52 features available (even if gate ignores some)
6. Planted boost post-hoc, per-species intro_ratio
7. Subspecies merge (-01/-02/-03 → -00)
8. Sample weight [0.01, 10.0] prevents outliers
9. Gradient clip norm=1.0
10. Comprehensive feature engineering (61 env cols)

---

## Key v3 Differences to Check

| Aspect | v2.2 | Check v3 |
|--------|------|----------|
| Hard cap | 50,000 | Lines 1-50 of train_sinr_v3.py |
| Gate features | 4D jrc only | Might include xiao/neumann? |
| Pos weight | 2048.0 | Different? |
| Background weighting | 1.0 | Lower? |
| Features | All 120+52 | Subset? |
| Subspecies merge | Yes | Still? |
| Gradient clip | norm=1.0 | Different? |

---

**Primary File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_sinr_model.py`

Lines 1-50: Header, 138-140: Hyperparams, 395-401: Hard cap, 443-707: Model, 846-903: Loss, 1079-1091: Background, 1105-1115: Planted label
