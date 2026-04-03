# V3 Forensic Audit: Exact Code Reference

**Purpose**: Quick lookup of exact line numbers for all 10 focus areas analyzed

---

## 1. HARD CAP PER SPECIES

### v2.2 Implementation (train_sinr_model.py)
- **Constant definition**: Line 138
  ```python
  HARD_CAP_PER_SPECIES = 50000  # Max training samples per species (prevent dominance)
  ```
- **Application in data extraction**: Lines 395-401
  ```python
  if HARD_CAP_PER_SPECIES:
      before = len(df)
      df = df.groupby("taxon_id", group_keys=False).apply(
          lambda g: g.sample(n=min(len(g), HARD_CAP_PER_SPECIES), random_state=42)
      )
      df = df.reset_index(drop=True)
      print(f"  Hard cap {HARD_CAP_PER_SPECIES}/species: {before:,} → {len(df):,}")
  ```

### v3 Status (train_on_vm.py)
- **MISSING**: No constant exists (search lines 1-300)
- **MISSING**: No hard cap logic in SINRDataset._prepare_arrays (lines 483-673)
- **Impact**: Species imbalance, common species dominate

### Required Fix
- Add constant at line ~62 (after other hyperparameters)
- Apply in SINRDataset._prepare_arrays() at line ~535

---

## 2. BACKGROUND LOSS

### v2.2 Implementation (train_sinr_model.py)
- **Background weight constant**: Line 140
  ```python
  BG_WEIGHT = 1.0  # Weight for background (random location) loss
  ```

- **Loss function with background parameter**: Lines 851-901
  ```python
  def sinr_an_full_loss(
      logits: torch.Tensor,
      species_idx: torch.Tensor,
      sample_weight: torch.Tensor,
      bg_logits: Optional[torch.Tensor] = None,  # ← Background logits optional
      pos_weight: float = POS_WEIGHT,
      bg_weight: float = BG_WEIGHT,
  ) -> torch.Tensor:
      # ... foreground loss ...
      if bg_logits is not None:  # Line 896
          bg_log_neg = F.logsigmoid(-bg_logits)  # Line 897
          loss_bg = -bg_log_neg.mean()  # Line 898
          weighted_loss = weighted_loss + bg_weight * loss_bg  # Line 899
      return weighted_loss
  ```

- **Background sampling in training loop**: Lines 1079-1093
  ```python
  # Generate random background samples (all species assumed absent)
  # ... create bg_cont_np, bg_cat_np, bg_intro_np with random values ...
  bg_output = model(bg_cont_t, bg_cat_t, bg_intro_t)  # Line 1087
  if isinstance(bg_output, tuple):
      bg_logits, _ = bg_output  # Line 1089
  else:
      bg_logits = bg_output  # Line 1091
  loss = loss_fn(logits, species_idx, sample_weight, bg_logits)  # Line 1093
  ```

### v3 Status (train_on_vm.py)
- **AN-Full loss function exists**: Lines 265-293
  - BUT takes NO bg_logits parameter
  - Has NO background handling code
- **Loss mode evaluation**: Lines 1044-1054
  ```python
  if loss_mode == 'an_full':  # Line 1044
      loss = _compute_an_full_loss(
          logits,
          targets,
          species_weights=species_weights_t,
          pos_weight=args.an_pos_weight,
      )
  else:  # Line 1051
      loss = _compute_species_weighted_bce_loss(
          criterion, logits, target_one_hot, targets, species_weights=species_weights_t
      )
  ```
- **NO background sampling in training loop** (Lines 1016-1082 completely missing bg code)

### Required Fix
- Add `BG_WEIGHT = 1.0` constant at line ~140
- Add background sampling in training loop (after line 1029)
- Modify `_compute_an_full_loss` to accept bg_logits parameter
- Add background loss to total loss calculation

---

## 3. PLANTED LABEL CONSTRUCTION

### v2.2 Implementation (train_sinr_model.py)

**Planted label definition**: Lines 1102-1107
```python
xiao_col_idx = list(CATEGORICAL_FEATURES.keys()).index("xiao_planted_forest")  # Line 1101
xiao_vals = cat[:, xiao_col_idx]  # remapped: 4=planted, 2=natural...

jrc_col_idx = list(CATEGORICAL_FEATURES.keys()).index("jrc_forest_type")  # Line 1102
jrc_vals = cat[:, jrc_col_idx]  # remapped: 4=planted, 3=primary, 2=natural

# CRITICAL: Planted is when BOTH sources agree OR either has strong signal
planted_label = ((xiao_vals == 3) | (jrc_vals == 4)).float()  # Line 1107
```

**Value maps** (lines 68-77):
```python
"xiao_planted_forest": {
    "vocab_size": 4,
    "emb_dim": 3,
    "value_map": {0: 1, 1: 2, 2: 3},  # raw 2 (planted) → mapped 3
},
```

### v3 Status (train_on_vm.py)

**Three different label modes**: Lines 1058-1068
```python
if args.planted_label_mode == 'strict_planted3':  # Line 1060
    # mapped class 3 corresponds to raw Xiao planted class 2
    planted_label = (x_cat[:, xiao_idx] == 3).float().unsqueeze(1)  # Line 1062
elif args.planted_label_mode == 'land_state2':  # Line 1063
    # land_state_class=2 as plantation proxy
    planted_label = (x_land[:, 0] == 2).float().unsqueeze(1)  # Line 1065
else:  # Line 1066
    # legacy behavior retained for reproducibility
    planted_label = (x_cat[:, xiao_idx] > 1).float().unsqueeze(1)  # Line 1068 ❌ WRONG DEFAULT
```

**Default flag**: Line 1346
```python
parser.add_argument('--planted-label-mode',
                    choices=['legacy_gt1', 'strict_planted3', 'land_state2'],
                    default='legacy_gt1',  # ❌ WRONG
```

**Value maps identical to v2.2**: Lines 102-103

### Issues Identified

1. **Default is 'legacy_gt1'** (line 1068)
   - `xiao > 1` includes both natural (2) AND planted (3)
   - Should be `xiao == 3` only

2. **Missing jrc_forest_type cross-check**
   - 'strict_planted3' mode only uses xiao, loses jrc signal
   - v2.2 uses `(xiao==3) | (jrc==4)` for high-confidence detection

3. **No jrc_forest_type handling** in planted_label_mode options

### Required Fix
- Change default at line 1346 to 'strict_planted3'
- Modify planted label construction to add jrc cross-check:
  ```python
  if args.planted_label_mode == 'strict_planted3':
      xiao_idx = list(CATEGORICAL_FEATURES.keys()).index('xiao_planted_forest')
      jrc_idx = list(CATEGORICAL_FEATURES.keys()).index('jrc_forest_type')
      planted_label = ((x_cat[:, xiao_idx] == 3) | (x_cat[:, jrc_idx] == 4)).float().unsqueeze(1)
  ```

---

## 4. AN-FULL LOSS FUNCTION

### v2.2 Implementation (train_sinr_model.py)

**Full loss definition**: Lines 851-901
```python
def sinr_an_full_loss(
    logits: torch.Tensor,  # (batch, num_species)
    species_idx: torch.Tensor,  # (batch,)
    sample_weight: torch.Tensor,  # (batch,)
    bg_logits: Optional[torch.Tensor] = None,
    pos_weight: float = POS_WEIGHT,
    bg_weight: float = BG_WEIGHT,
) -> torch.Tensor:
    batch_size, num_species = logits.shape
    valid = species_idx >= 0

    log_pos = F.logsigmoid(logits)  # log(sigmoid(logits))
    log_neg = F.logsigmoid(-logits)  # log(sigmoid(-logits))

    # Mean negative (assumed absent) over all species
    loss_neg = -log_neg.mean(dim=1)  # Line 862

    # Replace with weighted positive term
    target_log_pos = log_pos[valid, species_idx[valid]]
    target_log_neg = log_neg[valid, species_idx[valid]]
    correction = (target_log_neg + pos_weight * (-target_log_pos)) / num_species  # Line 876
    loss_per = (loss_neg[valid] + correction)

    weighted_loss = (loss_per * sample_weight[valid]).mean()

    if bg_logits is not None:  # Line 896
        bg_log_neg = F.logsigmoid(-bg_logits)
        loss_bg = -bg_log_neg.mean()
        weighted_loss = weighted_loss + bg_weight * loss_bg

    return weighted_loss
```

**Loss invocation in training**: Line 1093
```python
loss = loss_fn(logits, species_idx, sample_weight, bg_logits)
```

### v3 Status (train_on_vm.py)

**AN-Full loss reimplemented**: Lines 265-293
```python
def _compute_an_full_loss(logits, targets, species_weights=None, pos_weight=POS_WEIGHT):
    """Assumed-negative full loss (SINR-style), with optional per-species sample weighting."""
    batch_size, num_species = logits.shape
    valid = targets >= 0
    if not valid.any():
        return logits.sum() * 0.0

    v_logits = logits[valid]
    v_targets = targets[valid]

    log_pos = F.logsigmoid(v_logits)
    log_neg = F.logsigmoid(-v_logits)

    # Mean assumed-negative over all species
    loss_neg = -log_neg.mean(dim=1)  # Line 282

    # Replace target's negative term with weighted positive term
    t_log_pos = log_pos.gather(1, v_targets.unsqueeze(1)).squeeze(1)
    t_log_neg = log_neg.gather(1, v_targets.unsqueeze(1)).squeeze(1)
    correction = (t_log_neg + pos_weight * (-t_log_pos)) / num_species  # Line 287 ✅ IDENTICAL
    loss_per = loss_neg + correction

    if species_weights is not None:
        loss_per = loss_per * species_weights[v_targets]

    return loss_per.mean()
```

**BUT: Loss function selection in training loop**: Lines 1044-1054
```python
if loss_mode == 'an_full':  # Line 1044
    loss = _compute_an_full_loss(
        logits,
        targets,
        species_weights=species_weights_t,
        pos_weight=args.an_pos_weight,
    )
else:  # Line 1051
    loss = _compute_species_weighted_bce_loss(
        criterion, logits, target_one_hot, targets, species_weights=species_weights_t
    )
```

**Default loss mode**: Line 1338
```python
parser.add_argument('--loss-mode', choices=['bce', 'an_full'], default='bce',
                    help='Primary species loss function')
```

### Analysis
- ✅ Formula is IDENTICAL to v2.2 (line 287)
- ❌ But default loss_mode is 'bce' (line 1338)
- ❌ Most trained v3 models used BCEWithLogitsLoss instead
- ❌ No background loss handling (missing bg_logits parameter and usage)

### Required Fix
- Change line 1338: `default='bce'` → `default='an_full'`
- Modify _compute_an_full_loss to accept bg_logits parameter
- Add background loss logic back to function

---

## 5. FREQUENCY WEIGHTING

### v2.2 Implementation (train_sinr_model.py)

**Weight computation**: Lines 217-222
```python
class_counts = np.clip(class_counts, 1.0, None)
median_count = float(np.median(class_counts))
gamma = float(payload.get("weight_gamma", 0.5))
weights = np.power(median_count / class_counts, gamma).astype(np.float32)
weights = np.clip(weights, 0.25, 16.0)  # Line 221 ← Clipping range
return payload, class_counts, weights
```

### v3 Status (train_on_vm.py)

**Identical weight computation**: Lines 217-222
```python
weights = np.clip(weights, 0.25, 16.0)  # Line 221 ✅ SAME
```

**But conditional loading**: Lines 843-856
```python
if args.species_frequency_contract:  # Line 843
    freq_contract_path = Path(args.species_frequency_contract).expanduser()
    if not freq_contract_path.exists():
        log(f"ERROR: species frequency contract not found: {freq_contract_path}")
        return
    species_frequency_meta, class_counts, species_weights_np = _load_species_frequency_contract(
        freq_contract_path, mapping_meta['mapping_sha256'], num_species
    )
    species_weights_t = torch.from_numpy(species_weights_np).to(device)
else:
    # NO WEIGHTING APPLIED ❌
```

### Analysis
- ✅ Weight computation identical
- ❌ Only applied if `--species-frequency-contract` flag provided
- ❌ v2.2 always applies (extracted from data)
- ⚠️ Combined with missing hard cap, this is critical

### Required Fix
- Make `--species-frequency-contract` required, or
- Extract from BigQuery during data prep

---

## 6-10. OTHER FOCUS AREAS (Quick Reference)

### 6. AUXILIARY LOSS COUPLING
- **v3 Lines**: 420, 470-473 (identical to v2.2)
- **Status**: ✅ Correct (gradients flow through aux heads)

### 7. FEATURE CONTRACT ENFORCEMENT
- **v3 Lines**: 176-185, 542-558
- **Status**: ✅ Correct (flexible, with strict mode optional)

### 8. BOOST PATH
- **v3 Lines**: 470-473 (boost applied inside forward)
- **Status**: ✅ Correct (affects training AND inference)

### 9. MODEL ARCHITECTURE
- **v3 Lines**: 298-476 (build_model function)
- **Dimensions**:
  - Satellite: 64D → Linear(64→192)
  - Temporal: 512D → MultiheadAttention → 128D
  - Environment: 100D → Linear(100→192)
  - Land State: 5D → Linear(5→32)
  - Trunk: 352D input → Linear(352→384) → 6 ResBlocks(384D)
  - Phylo: 32D → gated residual
- **Status**: ✅ Architecture sound, but batch size 8× larger may mask issues

### 10. COMMAND-LINE ARGUMENTS
- **Default flags**: Lines 1338, 1346
  - `--loss-mode` default: 'bce' ❌ Should be 'an_full'
  - `--planted-label-mode` default: 'legacy_gt1' ❌ Should be 'strict_planted3'
- **Missing flags**: No `--hard-cap-per-species`, no `--bg-weight`

---

## Summary Table: Line Number Reference

| Finding | v2.2 Lines | v3 Lines | Status |
|---------|-----------|----------|--------|
| Hard cap constant | 138 | MISSING | ❌ |
| Hard cap application | 395-401 | MISSING | ❌ |
| Background weight | 140 | MISSING | ❌ |
| Background loss func | 851-901 | 265-293 | ⚠️ Missing bg param |
| Background sampling | 1079-1093 | MISSING | ❌ |
| Planted label logic | 1102-1107 | 1057-1068 | ⚠️ Wrong default |
| AN-Full loss formula | Line 876 | Line 287 | ✅ Identical |
| Loss mode default | an_full | bce | ❌ WRONG |
| Frequency weighting | Lines 217-222 | Lines 217-222 | ✅ Identical |
| Weighting application | Always | Optional | ⚠️ |
| Auxiliary boost | Line 681-683 | Line 470-473 | ✅ |
| Model arch | 462-687 | 298-476 | ✅ Better |
| Args: loss-mode | - | Line 1338 | ❌ |
| Args: planted-mode | - | Line 1346 | ❌ |

