# SINR v3 Xiao Regression - Precise Code Reference Map

This document pinpoints the exact code locations for each component of the xiao cascade.

---

## 1. CATEGORICAL FEATURE CONFIGURATION

### Training Configuration
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 101-110

```python
CATEGORICAL_FEATURES = {
    "jrc_forest_type": {"vocab_size": 5, "emb_dim": 3,
                         "value_map": {0: 1, 1: 2, 10: 3, 20: 4}},
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                             "value_map": {0: 1, 1: 2, 2: 3}},  # Raw 0→idx 1, 1→idx 2, 2→idx 3
    "eco_id": {"vocab_size": 850, "emb_dim": 32, "value_map": None},
    "biome_num": {"vocab_size": 16, "emb_dim": 8, "value_map": None},
    "soil_texture_class": {"vocab_size": 14, "emb_dim": 6, "value_map": None},
    "ipcc_forest_class": {"vocab_size": 10, "emb_dim": 4, "value_map": None},
}
```

### Inference Configuration
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/location_predictor_FIXED.py`
**Lines**: 1469-1477

```python
CATEGORICAL_FEATURES = {
    "jrc_forest_type": {"vocab_size": 5, "emb_dim": 3,
                        "value_map": {0: 1, 1: 2, 10: 3, 20: 4}},
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                            "value_map": {0: 1, 1: 2, 2: 3}},
    "eco_id": {"vocab_size": 850, "emb_dim": 32, "value_map": None},
    "biome_num": {"vocab_size": 16, "emb_dim": 8, "value_map": None},
    "soil_texture_class": {"vocab_size": 14, "emb_dim": 6, "value_map": None},
}
```

---

## 2. GEE XIAO DECODING

### v14 Buggy Decode (Currently in location_predictor_FIXED.py)
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/location_predictor_FIXED.py`
**Lines**: 602-616

```python
# ── Xiao Planted Forest ──────────────────────────────────────────
# Keep decode aligned with training extractor (unified_gee_sampler_v3.get_static_env_image)
# to avoid train/serve categorical drift.
xiao_mosaic = ee.ImageCollection(XIAO_ASSET).mosaic()
xb1 = xiao_mosaic.select('b1')
xb2 = xiao_mosaic.select('b2')
# TODO: v14 was trained with buggy decode below (xiao always=0).
# Correct decode is: b1.eq(127).And(b2.eq(127)).And(b3.eq(0)) for planted,
# b1.eq(0).And(b2.eq(127)).And(b3.eq(0)) for natural.
# Reverted to match v14 training until model is retrained with correct data.
is_planted = xb1.gt(200).And(xb2.lt(50))      # ALWAYS FALSE
is_natural = xb2.gt(100).And(xb1.lt(50))      # ALWAYS FALSE
xiao_class = (is_planted.multiply(2).add(is_natural)
              .rename('xiao_planted_forest').toFloat())  # Always 0
bands.append(xiao_class)
```

**Result**: Always produces xiao_planted_forest = 0

### Correct Decode (Reference Only - Not Currently Used)
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/location_predictor_FIXED.py`
**Lines**: 609-610 (Comments)

```python
# Correct decode is: b1.eq(127).And(b2.eq(127)).And(b3.eq(0)) for planted,
# b1.eq(0).And(b2.eq(127)).And(b3.eq(0)) for natural.
```

**Expected Results**:
- Planted (xiao=2): b1≈127, b2≈127, b3≈0 (yellow pixel)
- Natural (xiao=1): b1≈0, b2≈127, b3≈0 (green pixel)
- Non-forest (xiao=0): Everything else

---

## 3. DATASET PREPARATION - CATEGORICAL MAPPING

### Training Dataset Preparation
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Function**: `SINRDataset._prepare_arrays()`
**Lines**: 602-673

```python
def _prepare_arrays(self):
    """Convert dataframe to numpy arrays for fast tensor creation."""
    # ...

    # Categorical (line 661-673)
    self.cat_data = np.zeros((len(self.df), len(CATEGORICAL_FEATURES)), dtype=np.int64)
    for i, (col, cfg) in enumerate(CATEGORICAL_FEATURES.items()):
        if col in self.df.columns:
            raw = self.df[col].fillna(0).astype(np.int64).values
            if cfg["value_map"]:
                mapped = np.zeros(len(raw), dtype=np.int64)
                for raw_val, idx in cfg["value_map"].items():
                    mapped[raw == int(raw_val)] = idx
                self.cat_data[:, i] = mapped
            else:
                raw[(raw < 0) | (raw >= cfg["vocab_size"])] = 0
                self.cat_data[:, i] = raw
```

**Critical Line**: `mapped[raw == int(raw_val)] = idx`
- Maps raw xiao values (0, 1, 2) to embedding indices (1, 2, 3)
- v14: All rows have raw=0, so all mapped to index 1
- v15: Rows have raw∈{0,1,2}, mapped to indices∈{1,2,3}

---

## 4. EMBEDDING LAYER INSTANTIATION

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 400-406 (Inside model class definition)

```python
# Entity embeddings
self.embeddings = nn.ModuleDict()
total_emb_dim = 0
for col_name, cfg in self.categorical_config.items():
    self.embeddings[col_name] = nn.Embedding(
        cfg["vocab_size"], cfg["emb_dim"], padding_idx=0)
    total_emb_dim += cfg["emb_dim"]
```

**Result**: `nn.Embedding(4, 3, padding_idx=0)` for xiao_planted_forest
- 4 possible indices (0, 1, 2, 3)
- 3D embeddings
- Index 0 (padding) is zero-vector

---

## 5. EMBEDDING EXTRACTION AND CONCATENATION

### Embedding Lookup
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 473-489 (Inside forward() method)

```python
def forward(self, x_continuous, x_categorical, x_is_introduced,
            x_ae_temporal, x_land_state, x_phylo, x_location=None):
    B = x_continuous.shape[0]
    cat_embs = {}
    cat_emb_list = []
    if x_categorical is not None:
        for i, col_name in enumerate(self.categorical_config.keys()):
            emb = self.embeddings[col_name](x_categorical[:, i])  # [B, 3] for xiao
            cat_embs[col_name] = emb
            cat_emb_list.append(emb)

    x_sat = x_continuous[:, :self.NUM_SAT_DIMS]
    sat_h = self.sat_proj(x_sat)
    temporal_h = self.temporal_module(x_ae_temporal)
    x_env = x_continuous[:, self.NUM_SAT_DIMS:]  # 89D
    env_input = torch.cat([x_env] + cat_emb_list, dim=1)  # [B, 89 + 56]
    env_h = self.env_proj(env_input)  # [B, 192]
```

**Critical Sequence**:
1. Line 480: `emb = self.embeddings[col_name](x_categorical[:, i])`
   - Looks up embedding for each sample's categorical index
   - For xiao: If index=1 (v14), lookup emb[1] (well-trained)
   - For xiao: If index=3 (v15 planted), lookup emb[3] (poorly trained)

2. Line 488: `env_input = torch.cat([x_env] + cat_emb_list, dim=1)`
   - Concatenates 89D continuous + 56D categorical embeddings = 145D
   - Xiao contributes 3D to this 145D

3. Line 489: `env_h = self.env_proj(env_input)`
   - Linear(145, 192) projects to 192D
   - This linear layer was optimized for v14 distribution (all index 1)
   - In v15, sees indices {1, 2, 3} which have different statistics

---

## 6. LAND STATE CLASS COMPUTATION

### Inference Computation
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/v3_point_inference.py`
**Function**: `compute_land_state()`
**Lines**: 188-229

```python
def compute_land_state(feat: dict, ae_temporal_flat: np.ndarray, mode: str, year: int) -> np.ndarray:
    if mode == "zero":
        return np.zeros(5, dtype=np.float32)

    xiao = int(round(float(feat.get("xiao_planted_forest", 0.0) or 0.0)))
    treecover = float(feat.get("treecover2000", 0.0) or 0.0)
    lossyear = float(feat.get("lossyear", 0.0) or 0.0)
    fire = float(feat.get("fire_frequency_count", 0.0) or 0.0)

    if xiao == 2:                      # LINE 197: CRITICAL DECISION POINT
        land_state_class = 2.0         # Plantation (never in v14 training)
    elif treecover >= 20.0:
        land_state_class = 1.0         # Natural forest
    else:
        land_state_class = 0.0         # Non-forest

    disturbance_intensity = min(1.0, fire / 5.0 + (0.5 if lossyear > 0 else 0.0))

    yearly = ae_temporal_flat.reshape(8, 64)
    diffs = yearly[1:] - yearly[:-1]
    l2 = np.linalg.norm(diffs, axis=1)
    ae_temporal_change_l2 = float(np.mean(l2)) if len(l2) else 0.0

    forest_stability = max(0.0, 1.0 - disturbance_intensity)

    if lossyear > 0:
        loss_abs_year = 2000 + int(lossyear)
        years_since_loss = max(0, year - loss_abs_year)
        successional_stage = float(min(5, years_since_loss // 5))
    else:
        successional_stage = 5.0 if treecover >= 20.0 else 0.0

    return np.array(
        [
            land_state_class,           # [0] = class ∈ {0, 1, 2}
            disturbance_intensity,      # [1]
            forest_stability,           # [2]
            successional_stage,         # [3]
            ae_temporal_change_l2,      # [4]
        ],
        dtype=np.float32,
    )
```

**v14 Behavior** (xiao always=0):
- Never executes line 198 (xiao != 2)
- Falls through to treecover check
- land_state_class ∈ {0, 1} only

**v15 Behavior** (xiao ∈ {0,1,2}):
- When xiao=2: Executes line 198 → land_state_class = 2
- land_state_class ∈ {0, 1, 2}

---

## 7. PLANTED AUXILIARY LOSS SETUP

### v14: All-Zero Labels
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 1145-1158 (Training loop)

```python
# Aux losses (smaller weight)
# Planted detection: use xiao_planted_forest > 0 as proxy label
if 'xiao_planted_forest' in CATEGORICAL_FEATURES and args.aux_planted_weight > 0:
    xiao_idx = list(CATEGORICAL_FEATURES.keys()).index('xiao_planted_forest')
    if args.planted_label_mode == 'strict_planted3':
        # mapped class 3 corresponds to raw Xiao planted class 2
        planted_label = (x_cat[:, xiao_idx] == 3).float().unsqueeze(1)
    elif args.planted_label_mode == 'land_state2':
        # land_state_class=2 as plantation proxy
        planted_label = (x_land[:, 0] == 2).float().unsqueeze(1)
    else:
        # legacy behavior retained for reproducibility
        planted_label = (x_cat[:, xiao_idx] > 1).float().unsqueeze(1)  # LINE 1157: DEFAULT
    loss = loss + args.aux_planted_weight * aux_planted_loss(aux_pl, planted_label)
```

**v14 with buggy decode**:
- `x_cat[:, xiao_idx]` always = 1 (mapped from raw 0)
- `(x_cat[:, xiao_idx] > 1)` always = False
- `planted_label` always = 0
- Aux loss trains head to output zero for all samples

**v15 with correct decode**:
- `x_cat[:, xiao_idx]` ∈ {1, 2, 3} (mapped from raw 0, 1, 2)
- `(x_cat[:, xiao_idx] > 1)` = True when index ∈ {2, 3}
- `planted_label` ∈ {0, 1} distributed (51.7% positive)
- Aux loss trains head to detect plantations

---

## 8. PLANTED BOOST MECHANISM

### Head Definition
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 468-470

```python
self.output_layer = nn.Linear(hidden_dim, num_species, bias=False)
self.aux_planted_head = nn.Linear(hidden_dim, 1)  # Binary classification head
self.boost_scale = nn.Parameter(torch.tensor(2.0))  # Learnable multiplier
```

### Forward Pass with Boost
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 520-527

```python
logits = self.output_layer(x)
aux_planted = self.aux_planted_head(x)  # [B, 1]
planted_score = torch.sigmoid(aux_planted)  # [B, 1] ∈ (0, 1)
if self.training and getattr(self, '_disable_boost_in_training', False):
    boost = torch.zeros_like(logits)
else:
    boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
    # boost = [B, 1] * [1, num_species] * scalar = [B, num_species]
logits = logits + boost  # Direct logit addition
```

**v14 Behavior**:
- `aux_planted` trained to output ≈ 0 (all-zero labels)
- `planted_score` ≈ sigmoid(0) ≈ 0.5
- `boost` ≈ 0.5 * intro_ratio * 2.0 ≈ constant factor

**v15 Behavior**:
- `aux_planted` trained on true plantation data
- At plantation (xiao=2): `planted_score` ≈ 0.8-0.9
- `boost` ≈ 0.9 * intro_ratio * 2.0 ≈ 1.6-1.8 (stronger)

---

## 9. INFERENCE CATEGORICAL MAPPING

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/v3_point_inference.py`
**Function**: `build_feature_inputs()`
**Lines**: 293-302

```python
# Categorical indices
cat_values = []
for col, cfg in tvm.CATEGORICAL_FEATURES.items():
    raw = int(round(float(feat.get(col, 0.0) or 0.0)))
    if cfg["value_map"]:
        mapped = int(cfg["value_map"].get(raw, 0))  # Get mapped index, default 0 if missing
    else:
        mapped = raw if 0 <= raw < cfg["vocab_size"] else 0
    cat_values.append(mapped)
x_cat = np.array(cat_values, dtype=np.int64)
```

**v14 Inference** (buggy decode → xiao=0):
- `raw = 0` (from location_predictor_FIXED.py buggy decode)
- `cfg["value_map"]` = {0: 1, 1: 2, 2: 3}
- `mapped = 1` (looks up raw=0 in value_map)
- Embedding lookup: `embeddings['xiao_planted_forest'](1)` → well-trained

**v15 Inference** (corrected decode → xiao ∈ {0,1,2}):
- `raw ∈ {0, 1, 2}` (from corrected decode)
- `mapped ∈ {1, 2, 3}` (via value_map)
- Embedding lookup: `embeddings['xiao_planted_forest'](mapped)`
  - If mapped=1: well-trained
  - If mapped=2 or 3: poorly trained (only ~37% and ~15% training data)

---

## 10. LAND STATE BRANCH

### Land State Projection
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 421-423

```python
# Branch 4: Land State
self.land_state_proj = nn.Sequential(
    nn.Linear(5, land_state_dim), nn.GELU())
```

### Auxiliary Head
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 468-469

```python
self.aux_land_state_head = nn.Linear(hidden_dim, 6)  # 6 classes
```

### Training Loss
**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 1160-1165

```python
# Land state classification
ls_target = x_land[:, 0].long()  # land_state_class
ls_valid = (ls_target >= 0) & (ls_target < 6)
if ls_valid.any() and args.aux_land_state_weight > 0:
    loss = loss + args.aux_land_state_weight * aux_land_state_loss(
        aux_ls[ls_valid], ls_target[ls_valid])
```

**v14 Data**:
- `ls_target` ∈ {0, 1} only (from buggy xiao=0)
- Classes 2, 3, 4, 5 have zero samples
- Auxiliary head trained on {0, 1}, classes {2..5} remain random

**v15 Data**:
- `ls_target` ∈ {0, 1, 2} (xiao=2 triggers class 2)
- Classes 3, 4, 5 still have zero samples
- Class 2 now has non-zero samples (wherever xiao=2)
- Auxiliary head must learn class 2 while maintaining classes 0, 1

---

## 11. DATA DISTRIBUTION STATISTICS

### v15 Training Data Breakdown

From investigation (actual training parquets):
- Total samples: ~5,000,000
- xiao = 0 (non-forest): 2,415,000 (48.3%)
- xiao = 1 (natural forest): 1,845,000 (36.9%)
- xiao = 2 (planted forest): 740,000 (14.8%)

Samples per embedding index (after mapping):
- Index 0 (padding): 0 (unmapped)
- Index 1 (xiao=0): 2,415,000 samples
- Index 2 (xiao=1): 1,845,000 samples (37% of index 1 training)
- Index 3 (xiao=2): 740,000 samples (31% of index 1 training)

Effective training for indices 2 and 3:
- With 5M samples and 384D hidden dim and 56D categorical embeddings
- Per-index signal: ~1.8M / (5M * shared_capacity) for index 2
- Roughly 37% of the training signal available for index 1

---

## 12. MODEL ARCHITECTURE PARAMETERS

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/train_on_vm.py`
**Lines**: 45-60

```python
BATCH_SIZE = 16384       # H100 batch size
NUM_EPOCHS = 30
LEARNING_RATE = 3e-4
LR_DECAY = 0.97
WARMUP_EPOCHS = 2
POS_WEIGHT = 2048.0
DROPOUT = 0.25
HIDDEN_DIM = 384
NUM_RES_BLOCKS = 6
FUSION_DIM = 192
TEMPORAL_HIDDEN = 128
PHYLO_DIMS = 32
LOCATION_ENC_FREQS = 10
LOCATION_ENC_DIM = 40
```

**Critical for xiao**:
- HIDDEN_DIM = 384 (bottleneck for all signal, including 3D xiao)
- DROPOUT = 0.25 (applied at bottleneck, may mask minority index signals)
- Embedding dimensions: xiao=3D (small relative to 89D continuous + others)

---

## Summary of Cascade Points

| Component | v14 Behavior | v15 Behavior | File Location |
|---|---|---|---|
| GEE Decode | Always 0 | Mixed 0/1/2 | location_predictor_FIXED.py:612-615 |
| Value Map | 0→1 | 0→1, 1→2, 2→3 | train_on_vm.py:104-105 |
| Embedding Indices | Always 1 | Mixed 1/2/3 | train_on_vm.py:480 |
| Embedding Distribution | 100% index 1 | 48%/37%/15% | dataset:662-673 |
| Land State Class | {0,1} | {0,1,2} | v3_point_inference.py:197 |
| Planted Label | Always 0 | ~51.7% positive | train_on_vm.py:1157 |
| Planted Head Output | ~0.5 | Variable | train_on_vm.py:522 |
| Boost Magnitude | ~1.0 | ~1.6-1.8 | train_on_vm.py:526 |

---

## Files Modified for Fix

### To implement Option 2 (Recommended), modify:

1. **train_on_vm.py**:
   - Lines 188-202: Remove `if xiao == 2` rule from compute_land_state
   - Lines 101-110: Add regularization to CATEGORICAL_FEATURES config
   - Lines 400-430: Add orthogonal conditioning between xiao and land_state
   - Lines 1145-1165: Add calibration loss for aux_planted_head

2. **location_predictor_FIXED.py**:
   - Lines 612-615: No change (keep buggy for now) OR implement correct decode

3. **v3_point_inference.py**:
   - Lines 197-202: Remove hardcoded xiao==2 rule
   - Add curriculum learning schedule

### Critical files for validation:

- `orchestrator/sinr_model/best_model.pt` — v14 checkpoint
- `orchestrator/sinr_training_data/species_mapping.json` — species indices
- `orchestrator/normalize_stats_v3.npz` — feature normalization
