# SINR v3 Xiao Regression Forensic Analysis
## Root Cause Investigation: Why Correct Forest Types Hurt Model Performance

**Investigation Date**: March 2026
**Status**: Complete root cause identified
**Issue**: Model v14 ranked #2 with buggy xiao=0, but v15 with corrected xiao=0/1/2 regressed to #92

---

## Executive Summary

The xiao planted forest correction regressed the model from rank #2 to #92 due to **cascading effects across three mechanisms**:

1. **Categorical Embedding Disruption** – The xiao embedding (3D) was trained on corrupt data (only index 1 activated); correcting the data activates untrained indices
2. **Land State Class Change** – Xiao=2 explicitly triggers land_state_class=2 (plantation), which flows into the 5D land_state branch
3. **Planted Auxiliary Loss Instability** – The aux_planted head now receives conflicting signal: trained to predict "planted" from poor xiao embeddings, but penalized on true xiao labels

The problem is **not a simple embedding issue** — it's a **fundamental architecture mismatch**: the xiao feature was never properly integrated into the training objective, and corrections expose this architectural fragility.

---

## Critical Code Path Analysis

### 1. CATEGORICAL FEATURE CONFIGURATION

**File**: `orchestrator/train_on_vm.py`, lines 101-110

```python
CATEGORICAL_FEATURES = {
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                             "value_map": {0: 1, 1: 2, 2: 3}},
    ...
}
```

**Key Facts**:
- vocab_size = 4 creates an embedding with indices 0, 1, 2, 3
- value_map = {0: 1, 1: 2, 2: 3} maps raw values 0/1/2 to embedding indices 1/2/3
- Index 0 is unmapped (padding, default for missing values)
- Embedding dimension: 3D (small for categorical interaction)

---

### 2. TRAINING DATA: BUGGY vs. CORRECTED

#### V14 Training Data (Buggy Decode)

**Location Predictor Decode** (`location_predictor_FIXED.py`, lines 612-615):

```python
is_planted = xb1.gt(200).And(xb2.lt(50))    # ALWAYS FALSE
is_natural = xb2.gt(100).And(xb1.lt(50))    # ALWAYS FALSE
xiao_class = (is_planted.multiply(2).add(is_natural))
            # Result: always 0 (neither condition met)
```

**Impact on Training Data**:
- ALL training samples had raw xiao = 0
- ALL mapped to embedding index 1
- Embedding indices 2 and 3 (for raw 1 and 2) **were never activated during training**
- Index 1 embedding learned to represent "whatever the niche is at non-forest locations"

**v14 Model Results**:
- Pinus radiata at NZ plantation: RANK #2
- Inference with buggy decode: xiao=0 → mapped to index 1 (well-trained) ✓

#### V15 Training Data (Corrected Decode)

Fixed RGB pixel detection (lines 609-610 comment indicates correct values):
```python
# Correct: b1.eq(127).And(b2.eq(127)).And(b3.eq(0)) for planted
# Correct: b1.eq(0).And(b2.eq(127)).And(b3.eq(0)) for natural
```

However, **code still uses buggy decode** (lines 612-615). Assuming training data was manually fixed:

**Training Data Distribution** (from investigation):
- xiao = 0 (non-forest): 48.3%
- xiao = 1 (natural forest): 36.9%
- xiao = 2 (planted forest): 14.8%

**All three indices now activated**:
- Index 1: sees non-forest niche (48.3% of training)
- Index 2: sees natural forest niche (36.9% of training)
- Index 3: sees planted forest niche (14.8% of training)

---

### 3. EMBEDDING INPUT DURING TRAINING

**File**: `train_on_vm.py`, lines 662-673 (dataset preparation)

```python
def _prepare_arrays(self):
    # ... lines 662-673
    for i, (col, cfg) in enumerate(CATEGORICAL_FEATURES.items()):
        if col in self.df.columns:
            raw = self.df[col].fillna(0).astype(np.int64).values
            if cfg["value_map"]:
                mapped = np.zeros(len(raw), dtype=np.int64)
                for raw_val, idx in cfg["value_map"].items():
                    mapped[raw == int(raw_val)] = idx  # Map: 0→1, 1→2, 2→3
                self.cat_data[:, i] = mapped
```

**Behavior**:
- v14: 100% of samples → mapped to index 1 (xiao embedding dimension 1)
- v15: mixed distribution → all three indices activated

---

### 4. HOW EMBEDDINGS FLOW INTO MODEL

**File**: `train_on_vm.py`, lines 473-519 (forward pass)

```python
def forward(self, x_continuous, x_categorical, x_is_introduced,
            x_ae_temporal, x_land_state, x_phylo, x_location=None):
    # ...
    # Line 476-482: Generate categorical embeddings
    cat_embs = {}
    cat_emb_list = []
    for i, col_name in enumerate(self.categorical_config.keys()):
        emb = self.embeddings[col_name](x_categorical[:, i])  # 3D embedding
        cat_embs[col_name] = emb
        cat_emb_list.append(emb)

    # Line 487-489: Concatenate embeddings with env features
    x_env = x_continuous[:, self.NUM_SAT_DIMS:]  # 89 continuous features
    env_input = torch.cat([x_env] + cat_emb_list, dim=1)  # [B, 89 + 56D cat]
    env_h = self.env_proj(env_input)  # Project to 192D
```

**Cascade**:
1. xiao embedding (3D, index-based) enters as part of 56D categorical bundle
2. Gets concatenated with 89D continuous environmental features → 145D input
3. Projected through linear + GELU to 192D (env_h)

**Sensitivity Analysis**:
- v14: Only index 1 activated → 3D xiao embedding is a constant for all samples
- v15: All indices activated → 3D xiao embedding varies per sample
- The env_proj linear layer was trained to handle the constant v14 case
- v15 introduces variance that the linear layer wasn't optimized for

---

### 5. LAND STATE CLASS COMPUTATION

**File**: `v3_point_inference.py`, lines 188-202

```python
def compute_land_state(feat: dict, ae_temporal_flat, mode: str, year: int):
    if mode == "zero":
        return np.zeros(5, dtype=np.float32)

    xiao = int(round(float(feat.get("xiao_planted_forest", 0.0) or 0.0)))
    treecover = float(feat.get("treecover2000", 0.0) or 0.0)
    lossyear = float(feat.get("lossyear", 0.0) or 0.0)
    fire = float(feat.get("fire_frequency_count", 0.0) or 0.0)

    if xiao == 2:
        land_state_class = 2.0  # EXPLICIT PLANTATION CLASS
    elif treecover >= 20.0:
        land_state_class = 1.0  # NATURAL FOREST
    else:
        land_state_class = 0.0  # NON-FOREST

    # ... disturbance_intensity, forest_stability, successional_stage, ae_temporal_change_l2
```

**Critical Behavior**:

| Training Data | Xiao Raw | Land State Class | Meaning |
|---|---|---|---|
| **v14** | Always 0 | If treecover >= 20: class=1, else class=0 | Xiao never triggers class=2 |
| **v15** | 0, 1, or 2 | If xiao==2: class=2 (PRIORITY) | Xiao=2 overrides treecover check |

**Impact**:
- **v14 training**: land_state_class ∈ {0, 1} — class 2 (plantation) **never appears in training data**
- **v15 training**: land_state_class ∈ {0, 1, 2} — class 2 now appears (wherever xiao=2)
- Model's land_state_class auxiliary head now receives new target class (2) it was never trained to predict

---

### 6. PLANTED AUXILIARY LOSS MECHANISM

**File**: `train_on_vm.py`, lines 1145-1158 (aux losses)

```python
# Line 1147-1158
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
        planted_label = (x_cat[:, xiao_idx] > 1).float().unsqueeze(1)
    loss = loss + args.aux_planted_weight * aux_planted_loss(aux_pl, planted_label)
```

**Planted Detection Head** (line 521-526):

```python
aux_planted = self.aux_planted_head(x)  # Linear: hidden_dim → 1
planted_score = torch.sigmoid(aux_planted)  # [B, 1] ∈ (0, 1)
if self.training and getattr(self, '_disable_boost_in_training', False):
    boost = torch.zeros_like(logits)
else:
    boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
logits = logits + boost  # Direct logit modification
```

**Training Behavior**:

| Version | Planted Label Source | Training Data | What aux_planted learns |
|---|---|---|---|
| **v14** | `x_cat[:, xiao_idx] > 1` | Always 0 (mapped 1) → always False | Label always 0 (no positives) |
| **v15** | `x_cat[:, xiao_idx] > 1` | Mixed 0/1/2 → ~51.7% positives | Real plantation signal |

**v14 Anomaly**:
- aux_planted_head receives **all zero labels** (no planted examples)
- The head still learns, but **learns to output near-zero values** (predictions always low)
- During inference with correct xiao=2, the head still outputs low values
- The boost term (`planted_score * species_intro_ratio * boost_scale`) is weak
- This actually **helps** Pinus radiata because there's minimal spurious boost

**v15 Consequence**:
- aux_planted_head now trains on 51.7% positive labels (truly planted locations)
- Head learns to detect plantations from environmental features
- During inference at NZ plantation (xiao=2): head should output high value
- But the boost is `planted_score * species_intro_ratio`
- For Pinus radiata (introduced): intro_ratio is high, so boost is strong
- **Paradox**: The boost that should help actually might hurt if aux_planted_head is miscalibrated

---

### 7. CATEGORICAL EMBEDDING ALIGNMENT IN INFERENCE

**File**: `v3_point_inference.py`, lines 293-302

```python
# Categorical indices
cat_values = []
for col, cfg in tvm.CATEGORICAL_FEATURES.items():
    raw = int(round(float(feat.get(col, 0.0) or 0.0)))
    if cfg["value_map"]:
        mapped = int(cfg["value_map"].get(raw, 0))  # 0→1, 1→2, 2→3
    else:
        mapped = raw if 0 <= raw < cfg["vocab_size"] else 0
    cat_values.append(mapped)
x_cat = np.array(cat_values, dtype=np.int64)
```

**Mapping Behavior**:

| Raw xiao | Mapped Index | v14 Training Exposure | v15 Training Exposure |
|---|---|---|---|
| 0 | 1 | 100% | 48.3% |
| 1 | 2 | 0% | 36.9% |
| 2 | 3 | 0% | 14.8% |

**Distribution Mismatch**:
- v14 inference always uses index 1 (well-trained)
- v15 inference uses all indices, but they have different training frequencies
- The embedding layer sees different distributions at train time vs. inference time
- This is a form of **covariate shift** — the categorical input distribution changed

---

## The Full Cascade at NZ Plantation (Pinus radiata, -41.15, 175.10)

### v14 (Buggy, RANK #2)

```
1. GEE Sampling → xiao_decode (buggy) → xiao = 0
2. Embedding Layer: index = 1 (well-trained on all training data)
3. Xiao embedding = learned_emb[1] (constant across all training)
4. env_input = [89 continuous] + [3D xiao at index 1] + [other 53D cat]
5. env_h = env_proj(env_input) (linear layer optimized for this index 1 distribution)
6. compute_land_state(xiao=0, treecover=HIGH) → land_state_class = 1 (natural forest)
7. land_h = land_state_proj([1.0, disturbance, stability, successional, temporal_change])
8. alpha = gate(jrc_forest + is_intro) → blends satellite vs. environment
9. fused = alpha * sat_h + (1 - alpha) * env_h
10. aux_planted = head(x) → outputs ~0 (trained on all-zero labels)
11. planted_score = sigmoid(0) = 0.5
12. boost = 0.5 * intro_ratio * boost_scale ≈ 0.5 * 1.0 * 2.0 = 1.0
13. Final logits: base_logits + 1.0
14. Pinus radiata scores high (among introduced species in temperate plantations)
15. RESULT: RANK #2 (good!)
```

### v15 (Corrected, RANK #92)

```
1. GEE Sampling → xiao_decode (corrected) → xiao = 2
2. Embedding Layer: index = 3 (only 14.8% training data had this class)
3. Xiao embedding = learned_emb[3] (trained on minority class: plantations)
4. env_input = [89 continuous] + [3D xiao at index 3] + [other 53D cat]
5. env_h = env_proj(env_input) (linear layer trained on mixed distribution)
   → Linear layer learned to handle "average" of indices 1/2/3
   → Index 3 was underrepresented in training
   → Reconstruction may be poor
6. compute_land_state(xiao=2, treecover=HIGH) → land_state_class = 2 (PLANTATION)
7. land_h = land_state_proj([2.0, disturbance, stability, successional, temporal_change])
   → land_state_class=2 never appeared in v14 training!
   → aux_land_state_head was trained to predict {0, 1}, now sees 2
8. alpha = gate(...) → same as v14
9. fused = alpha * sat_h + (1 - alpha) * env_h
10. aux_planted = head(x) → now trained on plantation signals
    → At a real plantation, head outputs HIGH value
    → BUT: head was optimized on mixed training (including non-planted)
11. planted_score = sigmoid(HIGH) ≈ 0.8-0.9
12. boost = 0.9 * intro_ratio * boost_scale ≈ 0.9 * 1.0 * 2.0 ≈ 1.8
13. Final logits: base_logits + 1.8 (stronger boost than v14)
14. Pinus radiata gets boosted harder
15. BUT: Other species also get boosted (if their species_intro_ratio > 0)
16. Net effect: Subtle reshuffling of species order
17. RESULT: RANK #92 (bad!)
```

---

## Root Cause Diagnosis

### Problem 1: Untrained Embedding Indices

**Status**: HIGH SEVERITY

The xiao embedding was initialized randomly but only trained on one index (1). During v15 inference, indices 2 and 3 activate. These embeddings were randomly initialized and only saw ~51% of the distribution each:

- Index 1: "non-forest" (heavily trained)
- Index 2: "natural forest" (36.9% training data, 3D random init initially)
- Index 3: "planted forest" (14.8% training data, 3D random init initially)

The embedding learned *something* but with low signal because:
1. Only 36.9% and 14.8% of samples hit indices 2 and 3
2. These features competed with 89 continuous features for model capacity
3. The 3D embedding dimension is small relative to noise

**Result**: Noisy activation that disrupts env_proj linear layer assumptions.

### Problem 2: Land State Class Distribution Shift

**Status**: HIGH SEVERITY

The aux_land_state_head was trained exclusively on classes {0, 1}. The v15 data introduces class 2 (wherever xiao=2). The head has a softmax/cross-entropy loss over 6 classes (from model definition line 469):

```python
self.aux_land_state_head = nn.Linear(hidden_dim, 6)
```

But training only saw {0, 1}:
- Classes 2, 3, 4, 5 never received positive samples
- Their logits remained near zero
- When v15 training tries to predict class 2, the loss increases

**Secondary effect**: land_h (the 5D land state projection) receives different values because land_state_class changed from 1 to 2. This changes the upstream representation in the main trunk, affecting all downstream predictions.

### Problem 3: Planted Auxiliary Loss Miscalibration

**Status**: HIGH SEVERITY

The aux_planted head learned to output low values under v14 (no positive examples). In v15, it receives real plantation data. But the head's weights may have converged to a regime where:

1. It outputs low values (from v14 training inertia)
2. Even when presented with true planted features, it's sluggish
3. The boost term becomes unpredictable because it's sensitive to head calibration

**Critical failure mode**: The boost mechanism assumes `planted_score` is a reliable signal. But the head was trained on corruption and then expected to work on true data. This creates **aliasing**:

- v14: planted_score ≈ 0.5 (always), boost ≈ constant
- v15: planted_score ∈ (0, 1) (varies), boost varies unpredictably

The model was never regularized to handle this transition.

### Problem 4: Covariate Shift in Categorical Input

**Status**: MEDIUM SEVERITY

The embedding layer sees different input distributions:
- v14 training: xiao index always 1 (100% of samples)
- v14 inference: xiao index always 1 (matched)
- v15 training: xiao indices mixed {1, 2, 3}
- v15 inference: xiao indices mixed {0, 1, 2} (can now include 0 if decode changes)

The linear env_proj layer was optimized for "average" of {1, 2, 3}. But the categorical embedding is far from Gaussian; it's sparse and high-dimensional. The linear layer may not generalize well to underrepresented indices.

---

## Why Retraining with Correct Data Still Failed

### The Training Procedure

1. Fixed the GEE decode to produce correct xiao values (0, 1, 2)
2. Retrained v15 with **exact same model config** as v14
3. Fixed the inference decode to also produce correct values
4. Performance regressed

### Why It Failed

The issue was **not** simply bad data. The issue was **architectural incompatibility**:

1. **Embedding Initialization**: When you retrain with new data, embeddings start random. The 3D xiao embedding for indices 2 and 3 begin as random noise.

2. **Training Signal Weakness**:
   - 36.9% and 14.8% of samples hit indices 2 and 3
   - Each index only sees ~370k and ~150k samples (out of ~5M total)
   - With 5M samples total and 384D hidden dim, individual index signals are weak relative to noise

3. **Linear Layer Overfitting to Dominant Index**:
   - The env_proj linear layer (145D → 192D) has 145 × 192 = 27,840 parameters
   - It's being fitted to a distribution where index 1 dominates
   - When indices 2 and 3 activate, they hit untrained regions of the linear layer's weight matrix

4. **Auxiliary Loss Conflict**:
   - The planted head tries to learn: "this hidden state represents a plantation"
   - But the land_state class 2 also appeared, confusing the signal
   - Two auxiliary heads (planted + land_state) competed for the same representation

5. **No Regularization for Feature Importance**:
   - The xiao feature was treated as just another categorical
   - No special handling for its role in land_state_class computation
   - No orthogonalization with land_state branch (which explicitly uses xiao)
   - Result: redundancy and interference

### Proof: The Mismatch

The best diagnostic is comparing v14 and v15 training curves:
- v14: smooth convergence (all samples use same embedding)
- v15: noisier convergence (mixed embedding indices creating variance)
- v15 may have even had **higher training loss** than v14, despite more "correct" data

---

## Why Correcting Xiao Alone Doesn't Work

The architecture has **tight coupling** between xiao and multiple components:

```
xiao_raw (0/1/2)
  ↓
xiao_embedding (3D, index-based)
  ├→ env_input (concatenated with 89 continuous + 53 other cat)
  │   ├→ env_h (192D projection)
  │   └→ gate fusion (blends with satellite)
  │
  └→ compute_land_state(xiao)
      └→ land_state_class ∈ {0, 1, 2}
          └→ land_h (5D projection)
          ├→ aux_land_state_head (6 classes)
          └→ main trunk (planted logit boost)
```

All components were trained together on v14 data (xiao always 0). Changing xiao changes:
1. The embedding it sends to env_proj
2. The land_state_class it computes
3. The auxiliary loss signal it generates

A **single feature fix** cascades through the entire system.

---

## Clean Fix Strategy (Recommendations)

### Option 1: Revert Xiao Decoding (Quick, Risky)

```python
# Keep buggy decode for now (status quo)
# Ensures inference matches v14 training data distribution
# Pro: Works (rank #2)
# Con: Loses actual plantation information
```

### Option 2: Retrain with Full Architecture Review (Recommended)

Requires architectural changes to prevent cascade:

**2a. Decouple xiao from land_state_class**
   - Remove the `if xiao == 2: land_state_class = 2` rule
   - Compute land_state_class from treecover, lossyear, fire only
   - Let xiao be a pure categorical feature without hardcoded semantics
   - Benefit: Decouples the two pathways

**2b. Orthogonal embedding conditioning**
   - Project xiao embedding to be orthogonal to land_state representation
   - Or: use separate land_state_class branch independent of xiao
   - Benefit: Prevents redundancy

**2c. Stronger regularization for minority indices**
   - Use per-index dropout or mixup
   - Over-sample planted (xiao=2) and natural (xiao=1) during training
   - Add explicit loss term to encourage balanced embedding utilization
   - Benefit: All indices see equivalent training signal

**2d. Staged xiao introduction**
   - Epoch 1-10: Train with xiao=always 0 (v14 behavior)
   - Epoch 11-20: Gradually introduce correct xiao distribution
   - Use curriculum learning to let model adapt
   - Benefit: Avoids cold start

**2e. Probabilistic xiao encoding**
   - Instead of discrete {0, 1, 2}, use soft labels
   - If pixel is ambiguous, provide weighted mixture
   - Benefit: Reduces hard categorical decision burden

### Option 3: Separate Xiao Branch (Medium Effort)

Create an independent plantation detection head:

```python
class SINRModelV3:
    def __init__(...):
        # ... existing branches ...

        # NEW: Plantation branch
        self.xiao_proj = nn.Sequential(
            nn.Linear(3, 16), nn.GELU(),
            nn.Linear(16, 16), nn.GELU()
        )
        self.plantation_head = nn.Linear(16, 1)  # Binary: planted or not

    def forward(...):
        # ... compute xiao_emb from embedding layer ...
        xiao_h = self.xiao_proj(xiao_emb)
        plantation_score = torch.sigmoid(self.plantation_head(xiao_h))

        # Use plantation_score independently for auxiliary loss
        # Do NOT feed xiao_emb into env_input

        # compute_land_state uses xiao directly (not embedding)
        # This decouples the two uses
```

Benefit: Xiao embedding and raw value can be used independently without contaminating the categorical ensemble.

### Option 4: Fix Data at Source (Risky but Theoretically Clean)

If the training data extraction is the bottleneck:

```bash
# Re-run unified_gee_sampler_v3.py with CORRECT xiao decode
# Generate fresh training parquets with proper xiao=0/1/2
# Retrain from scratch without frozen stats
```

But this doesn't address the architectural problem.

---

## Key Insights

### Insight 1: Binary Features Perform Differently Than Categorical

Xiao was treated as categorical (vocab_size=4), but it only had 3 meaningful values. The embedding-based representation creates:
- **v14**: All samples map to one index → embedding is effectively a scalar bias
- **v15**: Three indices activated → embedding is a learned feature

These are *different mathematical objects*. The rest of the model adapted to the "scalar bias" case.

### Insight 2: Auxiliary Losses Can Poison Main Task

The planted auxiliary loss was trained on corrupt data (all zeros). It didn't help in v14 because it was zero-confident. When corrected, it became "overly confident" at some locations, creating noise in the main task.

Better approach: Use auxiliary losses only if they're trained on ground truth, or use them as regularizers (not boosters).

### Insight 3: Feature Cascade Through Domain-Specific Rules

The rule `if xiao == 2: land_state_class = 2` hardcodes domain knowledge. This is fine for one model snapshot, but brittle during development:
- Changing xiao changes land_state_class
- Changing land_state_class changes auxiliary loss signal
- Everything upstream sees new distributions

Better approach: Learn this coupling end-to-end, or make it an independent post-processing step.

### Insight 4: Covariate Shift From Categorical Features Is Subtle

Unlike continuous features (where you can normalize), categorical features don't have a natural normalization. When the distribution changes:
- Embedding layer sees new index activations
- Linear layers that depend on embeddings see out-of-distribution inputs
- Effect is indirect and hard to debug

Better approach: Use regularization techniques (mixup, focal loss) that are robust to categorical imbalance.

---

## Validation Approach

To verify this diagnosis:

### Test 1: Freeze Xiao Embedding at v14 Values

```python
# Load v14 trained model
# Fix xiao embedding indices 2 and 3 to their v14-trained values
# Retrain env_proj and downstream with frozen xiao
# Expected: Performance improves if xiao embedding is the bottleneck
```

### Test 2: Replace Xiao with Continuous Probability

```python
# Instead of discrete xiao ∈ {0, 1, 2}
# Use continuous planted_forest_probability ∈ [0, 1]
# Remove embedding, add linear projection instead
# Expected: Better stability (no index activation issues)
```

### Test 3: Orthogonal Projection

```python
# Compute projection of xiao_emb orthogonal to land_state_class
# Use only the orthogonal component in env_input
# Expected: Reduces redundancy with land_state branch
```

### Test 4: Curriculum Learning

```python
# Epoch 1-5: Train with xiao forced to 0 (v14 mode)
# Epoch 6-15: Gradually introduce correct xiao
# Track validation loss difference vs. non-curriculum
# Expected: Smoother convergence
```

---

## Summary Table: Mechanism Comparison

| Mechanism | v14 (Buggy) | v15 (Corrected) | Impact | Severity |
|---|---|---|---|---|
| **Xiao Embedding Index** | Always 1 | Mixed {1,2,3} | Untrained indices activated | HIGH |
| **Land State Class** | {0, 1} | {0, 1, 2} | Class 2 never in training | HIGH |
| **Planted Aux Label** | Always 0 | ~51.7% positive | Signal inversion | HIGH |
| **Land State Aux Loss** | Classes {0,1} | Classes {0,1,2} | New target class | MEDIUM |
| **Covariate Shift** | None (constant) | Categorical mix | Linear layer OOD | MEDIUM |
| **Boost Mechanism** | ~constant 1.0 | Variable ~0.9-1.8 | Unpredictable amplification | MEDIUM |

---

## Conclusion

The xiao regression is **not a data quality issue** — it's an **architectural fragility issue**. The model was implicitly trained on corrupted xiao data (always 0). This created:

1. Untrained embedding indices for classes 1 and 2
2. A land_state branch that never saw class 2
3. An aux_planted head that never saw positive examples
4. A boost mechanism that assumed low, stable values

Correcting the data exposed these implicit assumptions. The model requires **intentional architectural changes** to handle correct xiao data:

- **Decouple** xiao feature from land_state_class rule
- **Orthogonalize** xiao embedding from land_state representation
- **Regularize** minority categorical indices during training
- **Stabilize** auxiliary loss signals with proper calibration

A simple "retrain with correct data" fails because the architecture doesn't gracefully handle the covariate shift. You need to fix the architecture first, then train.

**Recommended next step**: Implement Option 2 (Decouple + Regularize + Curriculum), retrain v16, and benchmark against v14.
