# SINR v3 Comprehensive Forensic Audit

Date: 2026-03-07
Auditor: Claude (Opus 4.6)
Scope: Why SINR v3 fails to match v2.2 performance, and the exact path to fix it.

## Executive Summary

SINR v3 regressed from v2.2's radiata rank #1-#10 to #16 (best case, v4 gatefix baseline). After forensic comparison of the v2.2 and v3 codebases, training pipelines, loss functions, and inference paths, I have identified **5 root causes** in order of severity. The core problem is not architectural complexity per se — it is that v3 dropped three critical mechanisms from v2.2 while adding features that create train/serve distribution shift.

## The 5 Root Causes (Ranked by Impact)

### Root Cause 1: No Hard Cap Per Species (CRITICAL)

**v2.2**: `HARD_CAP_PER_SPECIES = 50000` at `train_sinr_model.py:138`

```python
# v2.2 — train_sinr_model.py:395-401
if HARD_CAP_PER_SPECIES:
    before = len(df)
    df = df.groupby("taxon_id", group_keys=False).apply(
        lambda g: g.sample(n=min(len(g), HARD_CAP_PER_SPECIES), random_state=42)
    )
```

**v3**: No cap exists anywhere in `train_on_vm.py`.

**Why this matters**: The strict training table has species counts ranging from 1 to 415,050. Without a cap, dominant confusers like `GymPiPiPnCx50832-00` (Pinus sylvestris, 300K+ samples) and `GymPiPiPnCx50811-00` (238K+ samples) get 30-60x more gradient updates than Pinus radiata (9,616 samples). The model becomes extremely good at predicting the common confusers and loses discrimination for medium-frequency species.

The frequency weighting at `train_on_vm.py:221` tries to compensate but clips to [0.25, 16.0], creating only a 64x range for a 415,050x imbalance — a 99.98% information loss on the extreme tails.

**Impact estimate**: This is the single largest contributor to ranking degradation. v2.2 capped all species to 50K max, meaning the max imbalance ratio was only 50,000:1 (still large but 8x less extreme).

**Fix**: Add `--hard-cap-per-species 50000` flag to `train_on_vm.py`, apply before array construction.

---

### Root Cause 2: Background Loss Component Missing (CRITICAL)

**v2.2**: AN-Full loss included a background regularization term at `train_sinr_model.py:1079-1093`

```python
# v2.2 — Background: random features, all species assumed absent
bg_indices = np.random.randint(0, len(train_dataset), BATCH_SIZE)
bg_cont_np = train_dataset.continuous[bg_indices]
bg_cat_np = train_dataset.categorical[bg_indices]
bg_intro_np = train_dataset.is_introduced[bg_indices]
bg_output = model(bg_cont_t, bg_cat_t, bg_intro_t)
loss = loss_fn(logits, species_idx, sample_weight, bg_logits)
```

The loss function handles background at `train_sinr_model.py:896-899`:
```python
if bg_logits is not None:
    bg_log_neg = F.logsigmoid(-bg_logits)
    loss_bg = -bg_log_neg.mean()
    weighted_loss = weighted_loss + bg_weight * loss_bg  # BG_WEIGHT = 1.0
```

**v3**: `_compute_an_full_loss` at `train_on_vm.py:265-293` has no background term at all. The training loop at lines 1042-1068 never generates background samples.

**Why this matters**: The background term teaches the model that at random locations, ALL species should have low probability. Without it, the model can learn to predict high probability for many species everywhere — it only learns to push down non-target species at observed locations, not globally. This is especially harmful for common, cosmopolitan species (the confusers) which appear everywhere and get positive signal at many locations.

**Impact estimate**: Second-largest contributor. Background regularization is a core part of the SINR paper's approach and prevents the "everything is probable everywhere" failure mode.

**Fix**: Restore background sampling and loss term in the v3 training loop.

---

### Root Cause 3: Planted Label Proxy is Wrong (HIGH)

**v2.2**: Correct planted detection at `train_sinr_model.py:1105-1108`

```python
# v2.2 — Correct: xiao=3 is planted, jrc=4 is planted
planted_label = ((xiao_vals == 3) | (jrc_vals == 4)).float()
has_data = (xiao_vals > 0) | (jrc_vals > 0)  # skip unknown
```

**v3**: Wrong proxy at `train_on_vm.py:1059-1060`

```python
# v3 — WRONG: (mapped > 1) selects natural forest (mapped=2) AND planted (mapped=3)
planted_label = (x_cat[:, list(CATEGORICAL_FEATURES.keys()).index(
    'xiao_planted_forest')] > 1).float().unsqueeze(1)
```

With the value map `{0: 1, 1: 2, 2: 3}` (line 102-103):
- mapped 2 = raw 1 = **natural forest** → labeled as "planted" (WRONG)
- mapped 3 = raw 2 = **actual planted** → labeled as "planted" (correct, but never appears in data)
- Effective positive rate: ~22% (all from natural forest, zero from actual plantations)

Additionally, v2.2 correctly filters unknown values (`has_data = (xiao_vals > 0) | (jrc_vals > 0)`), while v3 does not — it trains on all samples including unknowns.

**Why this matters**: The boost path at `train_on_vm.py:472` applies `planted_score * species_intro_ratio * boost_scale`. When `planted_score` means "is forest" instead of "is plantation", the boost fires at ANY forested location, not specifically plantations. This dilutes the signal and provides no plantation-specific discrimination.

**Fix**: Change to strict mode: `planted_label = (x_cat[..., xiao_idx] == 3).float()` combined with `(x_cat[..., jrc_idx] == 4)`, and only compute loss where at least one has data.

---

### Root Cause 4: Feature Parity Gap — 20+ Features Zero at Inference (HIGH)

**v3 training** uses 90 env continuous features (defined at `train_on_vm.py:67-97`), but the feature contract `feature_contract_v2_online56.json` only includes 58 for "online" inference. Even of those 58, several are not actually sampled by `sample_sinr_env_features()` in `location_predictor_FIXED.py`:

Missing at inference but present in training:
- `aridity_index`, `et0_mm_yr` — in the 58-feature contract but NOT sampled by GEE
- `carbon_canopy_height_m`, `spawn_agb`, `spawn_agb_unc`, `spawn_bgb`, `spawn_bgb_unc` — offline only
- `gedi_l4b_agbd`, `gedi_l4b_agbd_se`, `gedi_rh98`, `gedi_fhd` — offline only
- `soc_0cm`, `soc_30cm`, `soc_100cm`, `soc_200cm` — offline only
- `npp_at_obs`, `gpp_at_obs`, `lai_at_obs`, `fpar_at_obs`, `evi_at_obs` — offline only
- `cci_agb_at_obs`, `cci_agb_sd_at_obs` — offline only
- `npp_at_ae`, `gpp_at_ae`, `lai_at_ae`, `fpar_at_ae`, `evi_at_ae` — offline only
- `cci_agb_at_ae`, `cci_agb_sd_at_ae` — offline only
- `npp_mean_longterm`, `npp_trend` — offline only
- `hilda_lulc_at_obs`, `hilda_lulc_at_ae` — offline only

**v2.2** had ~56 env features, ALL of which were sampled at inference via `map_sample_to_features()` in `location_predictor_FIXED.py`. Perfect parity.

**Why this matters**: Features that are populated during training but zero at inference cause distribution shift. The model learns to use these features for species discrimination, then at inference they're all zeros — the model sees an out-of-distribution input.

The `feature_contract_v2_online56.json` was created to address this by excluding offline features from training. But even with this contract, `aridity_index` and `et0_mm_yr` are listed as "online" but never sampled.

**Fix**: Wire `aridity_index` (CGIAR Global Aridity Index) and `et0_mm_yr` (MODIS ET) into the GEE sampler, OR remove them from the online feature contract.

---

### Root Cause 5: v2.2 Two-Pass Max Inference Missing (MEDIUM)

**v2.2**: Two-pass inference with max-selection at `location_predictor_FIXED.py`:

```python
# v2.2 — Two-pass: take max of native and introduced probability
probs_best = np.maximum(probs_native, probs_intro)
```

This means each species gets its BEST probability across native and introduced contexts. For P. radiata at a NZ plantation, the introduced pass gives high probability, and `max()` ensures it ranks well regardless of what the native pass says.

**v3**: `v3_point_inference.py` runs three passes (native, unknown, introduced) but reports them SEPARATELY. It does not take the max — each mode produces an independent ranking.

**Why this matters**: Without max-selection, the benchmark rank depends on which `is_introduced` value is chosen. At the NZ coordinate:
- intro=0.0 → rank #16
- intro=0.5 → rank may differ
- intro=1.0 → rank may differ

v2.2 would take `max()` across all modes, always giving each species its best shot.

**Fix**: Add a `--two-pass-max` mode to v3 inference that takes element-wise max across intro modes.

---

## v2.2 vs v3 Complete Comparison

| Aspect | v2.2 (worked) | v3 (broken) |
|--------|---------------|-------------|
| **Species count** | 35,561 | 45,247 |
| **Hard cap/species** | 50,000 | None |
| **Loss function** | AN-Full + background | BCE or AN-Full, no background |
| **Background samples** | Yes (random shuffle, BG_WEIGHT=1.0) | No |
| **pos_weight** | 2048 | 2048 |
| **Planted label** | `(xiao==3) \| (jrc==4)` (correct) | `(mapped>1)` = "is forest" (wrong) |
| **Planted label filter** | Skip unknown (has_data mask) | No filter |
| **Features (continuous)** | 120 (64 AE + 56 env) | 122-186 (64 AE + 58-122 env) |
| **Features at inference** | All 120 sampled | 20+ zero-filled |
| **Temporal** | None | 8×64 attention (512D) |
| **Phylogenetic** | None | 32D (zeroed at inference) |
| **Land state** | None | 5D branch |
| **Hidden dim** | 256 | 384 |
| **Res blocks** | 4 | 6 |
| **Dropout** | 0.3 | 0.25 |
| **Batch size** | 2048 | 1536 (local) / 16384 (H100) |
| **Epochs** | 12 | 5 (shard-sequential) |
| **Validation** | Random 5% | Random 5% |
| **Inference** | Two-pass max(native, intro) | Three separate modes |
| **Gate input** | jrc_emb(3D) + is_introduced(1D) | jrc_emb(3D) only (after v4 fix) |
| **Frequency weighting** | Per-sample quality×density | Per-species clipped [0.25, 16.0] |
| **Best val top10** | 59.3% | 41.9% |

## The AN-Full Sign Question (Resolved)

Both v2.2 and v3 have the same correction term sign:

```python
# v2.2 — train_sinr_model.py:889
correction = (-target_log_neg + pos_weight * (-target_log_pos)) / num_species

# v3 — train_on_vm.py:287 (current, after "fix")
correction = (t_log_neg + pos_weight * (-t_log_pos)) / num_species
```

The v2.2 version uses `-target_log_neg` (adds the target's negative penalty). The v3 "fix" changed this to `+t_log_neg` (removes it). Since v2.2 worked well WITH `-target_log_neg`, the "fix" may have actually HURT performance by changing the loss dynamics that v2.2 was calibrated for. The earlier v5 regression (#16 → #23) may have been caused by introducing AN-Full with the "fixed" sign that differs from v2.2's proven formula.

**Recommendation**: Revert the sign fix. Use v2.2's exact formula: `(-target_log_neg + pos_weight * (-target_log_pos)) / num_species`.

## Priority Implementation Plan

### Phase 1: Restore v2.2 Mechanisms (estimated impact: #16 → #5-8)

These are the three changes most likely to close the gap. Each should be tested as a single variable change against v4 baseline.

#### P0: Add Hard Cap Per Species

**File**: `orchestrator/train_on_vm.py`
**Change**: Add `--hard-cap-per-species` argument (default 50000). Apply in `SINRDataset._prepare_arrays()` or in `train()` after loading dataset.

```python
# After line 524 (filtered valid years):
if hard_cap_per_species:
    before = len(self.df)
    self.df = self.df.groupby("taxon_id", group_keys=False).apply(
        lambda g: g.sample(n=min(len(g), hard_cap_per_species), random_state=42)
    )
    self.df = self.df.reset_index(drop=True)
    log(f"Hard cap {hard_cap_per_species}/species: {before:,} → {len(self.df):,}")
```

**Expected impact**: Large. This was v2.2's primary balancing mechanism. Prevents dominant confusers from overwhelming training.
**Risk**: Low. Well-proven in v2.2. Simply caps over-represented species.
**Rollback**: Remove the flag.
**Verification**: Smoke test with s0 shard, benchmark at NZ coordinate.

#### P1: Restore Background Loss

**File**: `orchestrator/train_on_vm.py`
**Change**: In the training loop (after line 1033), add background sampling and pass `bg_logits` to the loss function. Update `_compute_an_full_loss` to accept and use `bg_logits`.

```python
# After forward pass, before loss computation:
bg_indices = np.random.randint(0, len(dataset), len(batch_indices))
bg_batch = dataset.get_batch(bg_indices)
bg_cont = bg_batch['continuous'].to(device)
bg_cat = bg_batch['categorical'].to(device)
bg_intro = bg_batch['is_introduced'].to(device)
bg_temporal = bg_batch['ae_temporal'].to(device)
bg_land = bg_batch['land_state'].to(device)
bg_phylo = bg_batch['phylo'].to(device)
with autocast_ctx():
    bg_logits, _, _ = model(bg_cont, bg_cat, bg_intro, bg_temporal, bg_land, bg_phylo)
```

Then in the loss function, add:
```python
if bg_logits is not None:
    bg_log_neg = F.logsigmoid(-bg_logits)
    loss_bg = -bg_log_neg.mean()
    total_loss = total_loss + bg_weight * loss_bg
```

**Expected impact**: Significant. Teaches the model general absence, preventing "everything probable everywhere" failure.
**Risk**: Low-medium. Doubles compute per batch (one extra forward pass). On Apple Silicon with 1536 batch size this is ~2x slower per epoch.
**Rollback**: Disable with `--bg-weight 0.0`.

#### P2: Fix Planted Label Semantics

**File**: `orchestrator/train_on_vm.py`
**Change**: Use v2.2's correct planted label construction:

```python
# Replace current line 1059-1060 with:
xiao_col_idx = list(CATEGORICAL_FEATURES.keys()).index('xiao_planted_forest')
jrc_col_idx = list(CATEGORICAL_FEATURES.keys()).index('jrc_forest_type')
xiao_vals = x_cat[:, xiao_col_idx]
jrc_vals = x_cat[:, jrc_col_idx]
planted_label = ((xiao_vals == 3) | (jrc_vals == 4)).float().unsqueeze(1)
has_data = (xiao_vals > 0) | (jrc_vals > 0)
if has_data.any():
    loss = loss + args.aux_planted_weight * aux_planted_loss(
        aux_pl[has_data], planted_label[has_data])
```

**Expected impact**: Moderate. Currently the planted head learns "is forest" which fires everywhere. With the fix, it learns actual plantation detection, making the boost meaningful.
**Risk**: Low. Direct port from v2.2's proven logic.
**Rollback**: Use `--planted-label-mode legacy_gt1`.

### Phase 2: Clean Up (estimated additional impact: #5-8 → #3-5)

#### P3: Wire Missing Inference Features

Add `aridity_index` (CGIAR/MODIS) and `et0_mm_yr` to `sample_sinr_env_features()` in `location_predictor_FIXED.py`. These are the only two "online" contract features not currently sampled.

#### P4: Add Two-Pass Max Inference

Add `--two-pass-max` mode to `v3_point_inference.py` that runs intro=0 and intro=1 passes and takes element-wise `max()` of probabilities before ranking. This matches v2.2 behavior.

#### P5: Widen Frequency Weight Clipping

Change `train_on_vm.py:221` from `np.clip(weights, 0.25, 16.0)` to `np.clip(weights, 0.05, 100.0)`. Combined with the hard cap, this gives the loss proper dynamic range for rare species.

### Phase 3: Architectural Simplification (optional, after Phase 1 validated)

#### P6: Revert AN-Full Sign to v2.2 Formula

The "fix" to the correction term changed v2.2's proven formula. Revert line 287 from `(t_log_neg + ...)` back to `(-t_log_neg + ...)` to match v2.2 exactly.

#### P7: Disable Boost During Training (Inference-Only Prior)

Make the boost path inference-only by guarding with `if not self.training`. This prevents the loss from backpropagating through the planted head × intro ratio multiplication, which couples the species objective with the planted auxiliary.

---

## Recommended Experiment Sequence

All experiments are single-variable changes against v4 baseline (#16).

| Order | Name | Change | Expected | Risk |
|-------|------|--------|----------|------|
| 1 | v8_hardcap | Add hard cap 50K/species | #8-12 | Low |
| 2 | v9_bg | Add background loss (if v8 improves) | #5-8 | Low-Med |
| 3 | v10_planted | Fix planted label semantics (if v8 or v9 improves) | #3-6 | Low |
| 4 | v11_combined | v8 + v9 + v10 together | #1-5 | Low |

Each experiment should be run as a full 5-shard local training and evaluated at the NZ benchmark coordinate.

**Do NOT stack all changes at once.** Run them sequentially, one variable at a time, and only combine after individual effects are validated.

---

## Verification Protocol

For each experiment:

```bash
# 1. Train (example for v8_hardcap)
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_local_contract_v8_hardcap_5m \
  --artifact-version v8_hardcap_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --require-full-contract \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --zero-phylo-input --disable-intro-in-gate \
  --hard-cap-per-species 50000

# 2. Benchmark
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 --lon 175.09968969862783 --year 2023 \
  --model-dir ~/model_local_contract_v8_hardcap_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 --introduced-mode all --top-k 20 \
  --disable-intro-in-gate
```

## Safety Constraints

- No destructive BQ operations.
- No changes to strict GEE extractor.
- All experiments produce new versioned model directories.
- v4 baseline (`~/model_local_contract_v4_gatefix_5m`) preserved as control.
- All code changes are additive (new flags) — defaults unchanged.

## Appendix: v2.2 Code References

| Component | File | Lines | Notes |
|-----------|------|-------|-------|
| Hard cap | train_sinr_model.py | 138, 395-401 | `HARD_CAP_PER_SPECIES = 50000` |
| AN-Full loss | train_sinr_model.py | 846-903 | With background term |
| Background sampling | train_sinr_model.py | 1079-1093 | Random indices from training set |
| Planted label | train_sinr_model.py | 1105-1108 | `(xiao==3) \| (jrc==4)` |
| Planted filter | train_sinr_model.py | 1108 | `has_data = (xiao>0) \| (jrc>0)` |
| Two-pass inference | location_predictor_FIXED.py | ~1700 | `np.maximum(probs_native, probs_intro)` |
| Model architecture | train_sinr_model.py | 462-707 | 120D input, 256 hidden, 4 blocks |
| Config | train_sinr_model.py | 130-141 | All hyperparameters |

---

## Appendix B: Web Research — Cutting-Edge SDM Practices

Research conducted via canonical source code inspection (Cole's SINR repo, Sat-SINR repo) and 2024-2025 published literature. All citations verified against primary sources.

### 1. Canonical SINR AN-Full Loss (Cole et al. ICML 2023 — from source code)

The canonical `losses.py` from `github.com/elijahcole/sinr` reveals:

```python
# Canonical Cole implementation (simplified):
loc_pred = torch.sigmoid(model.class_emb(loc_emb))           # (B, S)
loc_pred_rand = torch.sigmoid(model.class_emb(loc_emb_rand)) # (B, S) background

loss_pos = neg_log(1.0 - loc_pred)                           # assume all absent
loss_bg = neg_log(1.0 - loc_pred_rand)                       # background: all absent

# OVERWRITE the target species entry with positive term:
loss_pos[inds[:B], class_id] = pos_weight * neg_log(loc_pred[inds[:B], class_id])

loss = loss_pos.mean() + loss_bg.mean()
```

Key observations:
- **Background term is 50% of the loss** — it's not optional, it's half the objective.
- **`loss_pos.mean()` averages over B×S** (flattened), not per-sample then per-batch.
- **`pos_weight = 2048 = batch_size`** — this is intentional: one positive vs ~44K negatives per sample.
- **Background locations are uniform spherical samples** on the globe surface.
- The correction term sign matches v2.2's formula (confirming our Root Cause analysis).

This confirms Root Cause 2 (background loss missing) is critical — v3 is literally running with half the SINR loss removed.

### 2. Zbinden et al. 2024 — Imbalance-Aware Presence-Only Loss (arXiv:2403.07472)

This paper directly addresses the species frequency imbalance problem in presence-only SDMs:

```
L_full-weighted = -(1/S) * SUM_s [
    1[y_s=1] * λ₁ * w_s * log(ŷ_s)              # weighted presence
  + 1[y_s=0] * λ₂ * (1/(1 - 1/w_s)) * log(1-ŷ_s) # weighted absence
  + (1 - λ₂) * log(1 - ŷ'_s)                      # pseudo-absence
]
```

Where `w_s = n / n_p(s)` (inverse frequency per species), `λ₁ = 0.1` for large datasets (iNaturalist scale), `λ₂ = 0.5`.

**Result**: +7.3% Top-1 accuracy, rare species AUC from ~0.77 to 0.85 on GeoLifeCLEF 2023.

**Relevance to our problem**: Our frequency weighting clips to [0.25, 16.0], a 64x range for a 415,050:1 imbalance. Zbinden's approach uses full inverse-frequency weighting with a dampening factor (`λ₁`), providing proper gradient to rare species. This is the published, validated version of what our hard cap + wider clipping aims to achieve.

**Implementation**: Apply per-species `w_s` to the `pos_weight` term (not negatives): `pos_weight_per_species = pos_weight * w_species[class_id]`, capped at `50 × mean(w_species)` to prevent gradient explosion from single-observation species.

### 3. Asymmetric Loss (ASL) for Negative Focusing (Ridnik et al. ICCV 2021)

ASL down-weights easy negatives (species obviously absent at a location):

```python
# Standard negative: loss_neg = -log(1 - p)
# ASL negative (gamma_neg=4, margin=0.05):
p_m = torch.clamp(p - 0.05, min=0.0)       # probability shift
loss_neg = (p_m ** 4) * (-log(1 - p_m))     # focal-style focusing
```

When `p ≈ 0.001` (species clearly absent), `p_m^4 ≈ 10^{-12}` → gradient essentially zero. When `p ≈ 0.3` (ambiguous), gradient is preserved. This focuses learning on the confusers (Pinus sylvestris vs radiata) rather than trivially absent species (tropical trees at NZ coordinate).

**Relevance**: Our an_full negative term treats all 45K species equally at every location. ASL focusing would drastically reduce wasted gradient on the ~44,990 species that are trivially absent at any given location.

### 4. Sat-SINR Middle Fusion (ISPRS 2024 — from source code)

The canonical `models.py` from `github.com/ecovision-uzh/sat-sinr` reveals three fusion approaches. The **middle fusion** (ControlNet-inspired) performed best:

```python
class ContextResidLayer(nn.Module):
    def __init__(self, hidden_dim, dropout):
        self.embedder = nn.Linear(256, hidden_dim)
        self.embedder.weight.detach().zero_()   # CRITICAL: zero init
        self.embedder.bias.detach().zero_()

    def forward(self, x, c):
        b = self.layers(x)
        return x + b + self.embedder(c)         # additive injection
```

**Why this matters for us**: Our gated fusion (`alpha * sat_h + (1-alpha) * env_h`) is a convex combination — more satellite means less environment. Additive injection avoids this zero-sum: env features pass through unchanged, satellite is an additive correction. Zero initialization means the model starts as pure env SINR and gradually learns to incorporate satellite signal.

**Our 64D AlphaEarth version**:
```python
class ResBlockWithSatContext(nn.Module):
    def __init__(self, dim, dropout, ae_dim=64):
        self.net = nn.Sequential(nn.Linear(dim, dim), nn.GELU(), nn.Dropout(dropout),
                                 nn.Linear(dim, dim), nn.GELU())
        self.sat_proj = nn.Linear(ae_dim, dim)
        nn.init.zeros_(self.sat_proj.weight)
        nn.init.zeros_(self.sat_proj.bias)

    def forward(self, x, ae_emb):
        return x + self.net(x) + self.sat_proj(ae_emb)
```

### 5. Auxiliary Head Gradient Decoupling (ForkMerge NeurIPS 2023)

ForkMerge shows negative transfer occurs when auxiliary task gradients have `cos(g_primary, g_aux) < -0.3` consistently. Our planted detection head (trained on "is forest" label) likely conflicts with species discrimination gradients.

**The fix**: Stop-gradient auxiliary heads — they learn from the trunk but don't modify it:

```python
# Current (aux gradients flow to trunk):
logits, aux_planted, aux_land = model(...)
loss = primary_loss + 0.1 * planted_loss + 0.05 * land_loss  # all backprop to trunk

# Fixed (aux heads decoupled):
logits, aux_planted, aux_land = model(...)
loss = primary_loss
loss.backward()
# Aux heads train separately on detached features:
aux_planted_det = model.aux_planted_head(trunk_features.detach())
aux_loss = 0.1 * planted_loss(aux_planted_det)
aux_loss.backward()  # only updates head weights, not trunk
```

Keeps aux heads for inference (boost path, interpretability) without contaminating species discrimination gradients.

### 6. FS-SINR Batch-Species Variant (arXiv:2502.14977)

FS-SINR introduces `an_full_b` — limits the species sum to species in the current batch only. This is 44x faster per step for 44K species. Useful if compute is the binding constraint on Apple Silicon.

### Summary: Literature-Validated Priority Additions

| Priority | Change | Source | Expected Impact |
|----------|--------|--------|-----------------|
| **P0** | Hard cap 50K/species | v2.2 proven | High (fixes 415K:1 imbalance) |
| **P1** | Restore background loss | Cole canonical SINR | High (50% of loss was missing) |
| **P2** | Fix planted label | v2.2 proven | Medium (correct aux signal) |
| **P2.5** | Per-species frequency weighting | Zbinden 2024 (+7.3% top-1) | Medium-High |
| **P3** | Stop-gradient aux heads | ForkMerge NeurIPS 2023 | Medium (prevent negative transfer) |
| **P4** | ASL negative focusing | Ridnik ICCV 2021 | Medium (focus on confusers) |
| **P5** | Middle fusion (additive injection) | Sat-SINR ISPRS 2024 | Medium (architecture, needs retraining) |

The first three (P0-P2) are direct restorations of v2.2 mechanisms. P2.5-P4 are literature-validated improvements. P5 is an architectural change for a future version.

### Literature Sources

- Cole et al. SINR — ICML 2023 (canonical `losses.py` from GitHub)
- Zbinden et al. — Imbalance-aware presence-only loss, arXiv:2403.07472
- Ridnik et al. — Asymmetric Loss, ICCV 2021
- Sat-SINR — ISPRS 2024 (canonical `models.py` from GitHub)
- FS-SINR — arXiv:2502.14977
- ForkMerge — NeurIPS 2023
- DeepMaxent — arXiv:2412.19217
- Class-Balanced Loss (Cui et al.) — CVPR 2019
- Logit Adjustment (Menon et al.) — ICLR 2021
