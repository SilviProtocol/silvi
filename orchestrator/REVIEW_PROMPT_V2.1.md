# SINR v2.1 Architecture Review — Request for Expert Critique

## Context

We're building a species prediction model for Treekipedia — given a location on Earth (lat/lon), predict which tree species are present. The model takes AlphaEarth satellite embeddings (64-D) + environmental features and outputs a probability for each of 43,566 species. The architecture is based on Cole et al.'s SINR (Spatial Implicit Neural Representation) paper.

**We need your help identifying what's wrong with our architecture.** Our v2.1 model has better overall metrics than v1 but performs *worse* on a critical plantation-detection benchmark. Something is fundamentally broken in how plantation signals influence species prediction.

---

## The Benchmark

A known Pinus radiata plantation at Wairarapa, New Zealand (-41.1514, 175.0999). The site is clearly visible as dark conifer monoculture in satellite imagery.

| Model | P. radiata Rank (out of 43,566) | Notes |
|-------|--------------------------------|-------|
| k-NN baseline | #17 | Cosine similarity on embeddings |
| SINR v1 (epoch 6 best) | #22 | No plantation features, no gate |
| SINR v2 (epoch 1) | **#5** | Entity embeddings + gate + is_introduced, **no xiao/neumann** |
| SINR v2.1 (epoch 1) | #19 | Added xiao/neumann, expanded gate |
| SINR v2.1 (epoch 2) | #21 | Better overall metrics but P. radiata *worse* |

**The paradox: v2.1 has strictly more information than v2 (added two plantation-specific datasets), yet performs worse on the exact task those datasets were designed to help.**

---

## What Changed Between v2 and v2.1

### v2 Architecture (P. radiata #5)
- **Gate input**: 4D = jrc_emb(3D) + is_introduced(1D)
- **Gate alpha at Wairarapa**: 0.845 (85% satellite trust)
- **Categorical features**: 4 (jrc_forest_type, eco_id, biome_num, soil_texture_class)
- **Continuous features**: 119 (64 emb + 55 env)
- No auxiliary head
- Total entity embedding dim: 49D (3+32+8+6)

### v2.1 Architecture (P. radiata #21)
- **Gate input**: 8D = jrc_emb(3D) + xiao_emb(3D) + neumann_norm(1D) + is_introduced(1D)
- **Gate alpha at Wairarapa**: 0.667 (67% satellite trust — DROPPED from 0.845)
- **Categorical features**: 5 (added xiao_planted_forest)
- **Continuous features**: 120 (64 emb + 56 env, added neumann_natural_prob)
- Auxiliary planted-score head (0.1 weight)
- Total entity embedding dim: 52D (3+3+32+8+6)

### The critical observation: Adding plantation data REDUCED gate alpha (satellite trust) from 0.845 to 0.667

---

## Detailed Architecture

### Input Tensor Structure
```
x_continuous: (batch, 120)
  - dims 0-63: AlphaEarth satellite embedding (64D)
  - dims 64-119: environmental continuous features (56D)
    Last dim (119) = neumann_natural_prob (z-score normalized)

x_categorical: (batch, 5) long tensor
  - col 0: jrc_forest_type  → Embedding(vocab=5, dim=3), value_map {0→1, 1→2, 10→3, 20→4}, 0=unknown
  - col 1: xiao_planted_forest → Embedding(vocab=4, dim=3), value_map {0→1, 1→2, 2→3}, 0=unknown
  - col 2: eco_id → Embedding(vocab=850, dim=32), identity mapping
  - col 3: biome_num → Embedding(vocab=16, dim=8), identity mapping
  - col 4: soil_texture_class → Embedding(vocab=14, dim=6), identity mapping

x_is_introduced: (batch, 1) float
  - 0=native, 1=introduced, 0.5=unknown (mapped from -1)
```

### Forward Pass
```python
# 1. Compute entity embeddings for all 5 categoricals
cat_embs = {col: embed(x_categorical[:, i]) for i, col in enumerate(cats)}

# 2. Satellite branch: 64D embedding → Linear(128) → ReLU
sat_h = sat_proj(x_continuous[:, :64])  # (batch, 128)

# 3. Env branch: 56D continuous + ALL 52D entity embeddings → Linear(128) → ReLU
env_input = concat([x_continuous[:, 64:], *all_cat_embs])  # (batch, 108)
env_h = env_proj(env_input)  # (batch, 128)

# 4. Gate: plantation signals → alpha ∈ [0,1]
gate_input = concat([
    cat_embs['jrc_forest_type'],    # 3D
    cat_embs['xiao_planted_forest'], # 3D
    x_continuous[:, -1:],            # neumann_natural_prob (1D, z-score normalized)
    x_is_introduced,                 # 1D
])  # total: 8D
alpha = gate_MLP(gate_input)  # Sequential(Linear(8,16), ReLU, Linear(16,1), Sigmoid)

# 5. Fuse: alpha * satellite + (1-alpha) * env
x = alpha * sat_h + (1 - alpha) * env_h  # (batch, 128)

# 6. Residual blocks
x = input_layer(x)  # Linear(128, 256) → ReLU
x = res_blocks(x)   # 4 × ResidualBlock(256, dropout=0.3)

# 7. Species output
logits = output_layer(x)  # Linear(256, 43566, bias=False)

# 8. Auxiliary planted head
aux_logits = aux_head(x)  # Linear(256, 1)
```

### Loss Function
```
SINR Assumed-Negative Full Loss (an_full):
  - For each training row: 1 positive species, 43,565 assumed negatives
  - Positive: -pos_weight * log(sigmoid(logit[target]))  where pos_weight=2048
  - Negative: -mean(log(1 - sigmoid(logit[all_others])))
  - Sample weights: quality_weight * density_weight
  
Background loss (random locations): -mean(log(1-sigmoid(all_logits)))
  weight: 1.0

Auxiliary loss: BCE(aux_logits, planted_label) * 0.1
  planted_label = 1 if xiao==planted(3) OR jrc==planted(4)
  Only computed where at least one categorical is non-unknown
```

### Hyperparameters
```
batch_size: 2048
epochs: 12
lr: 0.0005, ExponentialLR decay 0.98/epoch
hidden_dim: 256
fusion_dim: 128
num_res_blocks: 4
dropout: 0.3
pos_weight: 2048
hard_cap_per_species: 50,000
grad_clip: 1.0
```

---

## Training Data Statistics

### Global
- **8,155,811 training rows**, 429,211 validation rows
- **43,566 species** (includes subspecies as separate classes)
- 85.0% native, 12.8% introduced, 2.2% unknown

### Plantation Coverage (Global)
- xiao=planted: 1,119,306 rows (13.7%)
- jrc=planted: 959,681 rows (11.8%)
- is_introduced=1: 1,117,666 rows (13.7%)
- introduced AND xiao=planted: 121,115 rows (1.5%), 4,708 species

### P. radiata Specifically (main taxon GymPiPiPnCx50820-00)
- **7,917 training rows** (after hard cap 50K not hit)
- 4 subspecies variants: -00 (7,917 rows), -01 (23), -02 (18), -03 (10) — each trained as a SEPARATE output class
- is_introduced=1: 91.1% (7,215 rows)
- xiao=planted(2): only **24.3%** (1,920 rows)
- xiao=natural(1): **39.4%** (3,117 rows) — many P. radiata in areas Xiao calls "natural"!
- xiao=non-forest(0): 29.6%
- jrc=planted(20): only 25.7% (2,031 rows)
- jrc=natural(1): **41.0%** (3,246 rows) — same JRC misclassification issue
- neumann < 30 (likely planted): 3,401 / 7,378 (46.1%)

**KEY INSIGHT: Only ~25% of P. radiata training data is labeled as "planted" by either Xiao or JRC. The majority of P. radiata observations are in areas classified as "natural" or "non-forest" by these datasets.** This means the model CANNOT learn "planted → P. radiata" because the signal is weak and contradictory in the training data.

### NZ Ecoregion (eco_id=171) Training Data
- 6,099 rows, 310 species
- P. radiata: only 197 rows in this ecoregion (3.2%)
- Top species: Dacrycarpus dacrydioides (455), Dacrydium cupressinum (442), Rhopalostylis sapida (412) — all native NZ species
- Native species vastly outnumber P. radiata in the NZ training data

---

## What the Model Sees at Wairarapa Inference

```
AlphaEarth embedding: 64D (real satellite data from 2023, clearly shows monoculture)
elevation: 357m
eco_id: 171 (Canterbury-Otago)
biome_num: 4 (Temperate Broadleaf & Mixed Forests)
xiao_planted_forest: 2 (PLANTED) ← correct
neumann_natural_prob: 0 (NOT natural) ← correct
jrc_forest_type: 20 (PLANTED) ← correct at this exact point
is_introduced: 1.0 (set manually for P. radiata)
soil_texture_class: 4 (clay loam)
bio01 (mean temp): 12.5°C
bio12 (annual precip): 1729mm
... (all 120 continuous + 5 categorical features populated)
```

**All plantation signals are correct at this point.** The model has every possible signal that this is a planted, introduced conifer. Yet P. radiata ranks #21.

---

## The Top 10 Predictions at Wairarapa (v2.1 epoch 2)

| Rank | Species | p | Native/Introduced |
|------|---------|---|-------------------|
| 1 | Prumnopitys ferruginea | 0.993 | Native NZ podocarp |
| 2 | Leptospermum scoparium | 0.960 | Native NZ |
| 3 | Lomatia fraseri | 0.942 | Native Australasia |
| 4 | Pittosporum undulatum | 0.938 | Introduced to NZ |
| 5 | Banksia marginata | 0.936 | Native Australia |
| 6 | Acacia melanoxylon | 0.935 | Introduced to NZ |
| 7 | Dacrycarpus dacrydioides | 0.927 | Native NZ |
| 8 | Coprosma autumnalis | 0.926 | Native NZ |
| 9 | Podocarpus totara | 0.924 | Native NZ |
| 10 | Ilex aquifolium | 0.924 | Introduced to NZ |
| ... | | | |
| 21 | **Pinus radiata** | 0.842 | **Introduced** |

The model is predicting "NZ temperate forest species" — ecologically reasonable for the region, but wrong for this specific plantation site.

---

## Gate Analysis

### Gate Weights (epoch 2)
```
gate.0.weight: shape=(16, 8), mean=-0.0224, std=0.2933
gate.0.bias: shape=(16), mean=0.0326, std=0.1968
gate.2.weight: shape=(1, 16), mean=-0.0428, std=0.2370
gate.2.bias: shape=(1), mean=-0.1429
```

The gate bias is -0.1429 → sigmoid(-0.1429) = 0.464. The gate is biased slightly toward env (α < 0.5 at initialization). The weights have barely moved from random initialization after 2 epochs, suggesting the gate is NOT receiving strong gradient signal.

### Why v2's gate worked better
v2's gate had 4D input: jrc_emb(3D) + is_introduced(1D). The is_introduced signal is clean (91% of P. radiata = 1). With only 4D, the gate could learn a simple rule: "if introduced → trust satellite." 

v2.1's gate has 8D input with noisy signals: xiao and JRC both incorrectly label 40%+ of P. radiata as "natural." The gate is receiving contradictory information and learning a muddled compromise.

---

## Specific Questions for Reviewers

1. **Is the gate architecture fundamentally flawed?** The gate controls satellite vs. env blending but doesn't directly influence WHICH species get boosted. Even with α=1.0, the satellite embedding alone ranks P. radiata at ~#23. The gate can't do what we need.

2. **Should the auxiliary head feed back into species prediction?** Currently the aux head detects plantations perfectly (score=1.0) but this information is completely disconnected from the species logits. It's a diagnostic output that doesn't influence prediction.

3. **Is the subspecies problem significant?** P. radiata probability is split across 4 output classes (7,917 + 23 + 18 + 10 rows). The main variant has p=0.842 but the model is distributing capacity across 4 separate sigmoid outputs. Should we merge subspecies into parent species during training?

4. **Is the assumed-negative loss with 43,566 classes the core problem?** With pos_weight=2048, each positive gets 2048× the weight of each negative, but there are 43,565 negatives. The effective positive-to-negative ratio is 2048:43565 ≈ 1:21. Is this too diluted for rare-in-region species like P. radiata?

5. **Should plantation detection be a SEPARATE MODEL rather than a gate within the species model?** For example: (1) classify planted/natural/non-forest, (2) run species prediction conditioned on that classification.

6. **Is there a data quality problem?** Only 24% of P. radiata training rows are labeled "planted" by Xiao, and only 26% by JRC. The majority are labeled "natural" — meaning the model learns that P. radiata appears in "natural" forests. This contradicts the gate's intended behavior.

7. **Would hard negative mining help?** The model needs to distinguish P. radiata from native NZ podocarps (Dacrycarpus, Podocarpus, Prumnopitys) that occupy the same ecoregion. Training on hard negatives from the same ecoregion could sharpen discrimination.

8. **Is the fusion_dim=128 bottleneck too aggressive?** Both satellite (64D) and env (56D continuous + 52D embeddings = 108D) branches are projected to 128D before the gate blends them. The env branch loses more information proportionally.

9. **Should we consider a different architecture entirely?** Options:
   - Multi-head attention over feature groups instead of a scalar gate
   - Mixture of experts (one expert per land-use type)
   - Two-stage: coarse land-use classification → conditioned species prediction
   - Feature-interaction layer (FiLM/bilinear) instead of additive fusion

10. **Any other architectural or training issues you see?**

---

## V2.1 Training Metrics (for reference)

| Epoch | train_loss | val_loss | top-10 | top-50 |
|-------|-----------|----------|--------|--------|
| 1 | 0.01902 | 0.00622 | 48.3% | 84.5% |
| 2 | 0.00925 | 0.00517 | 52.7% | 87.0% |
| (v1 best, ep6) | — | 0.00539 | 52.4% | 86.2% |

v2.1 surpasses v1's best overall metrics by epoch 2, but fails on plantation-specific prediction.

---

## Model Parameters
- Total: 11,762,385 (all trainable)
- Size: 47 MB (float32)
- Device: Apple Silicon MPS

## Training Data Dimensions
- 120 continuous (64 satellite embedding + 56 environmental)
- 5 categorical → 52D entity embeddings
- 1 binary flag (is_introduced)
- Total effective input: 172D (after embedding)

---

## Summary of the Core Problem

The model is excellent at regional ecology (correct NZ species in top 30) but cannot distinguish **planted introduced species from native species in the same region**. The plantation detection signals (xiao, neumann, jrc) are:
1. **Noisy in training data** — only 24-26% of P. radiata rows labeled as planted
2. **Disconnected from species output** — aux head knows it's a plantation but species head doesn't use this
3. **Diluted in the gate** — expanding gate from 4D to 8D with noisy inputs made it worse
4. **Overwhelmed by regional ecology signal** — eco_id=171 has 310 species dominated by natives, and the env branch + entity embeddings strongly predict "NZ native forest"

We need a fundamentally different way to connect "this is a plantation" → "boost introduced plantation species" in the species prediction.
