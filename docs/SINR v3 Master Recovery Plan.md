# SINR v3 Master Recovery Plan

Superseded note (2026-03-19): this document is now historical reference only.
For the active post-merge program, read `docs/SINR Current Program State.md` first.
Do not treat the issue queue or next steps in this file as the live operational plan.

Date: 2026-03-07
Owner: Claude Opus 4.6 (synthesis of Claude, Gemini, Codex audits + independent verification)
Status: superseded active source of truth for the historical `v3` recovery line

## Executive Summary

Three independent audits (Claude, Gemini, Codex) + independent verification have converged on a clear diagnosis. SINR v3 underperforms v2.2 due to 5 specific mechanisms that were dropped or broken during the v2.2→v3 transition. The fix path is well-defined: restore v2.2 mechanisms one at a time, verify each against the trusted baseline.

**Trusted baseline**: v4_gatefix_5m = radiata rank **#16 / 45,247** at benchmark coordinate
**Immediate free improvement**: `--land-state-mode zero` at inference → **#12** (no retraining)

---

## 1. Benchmark Protocol

**Canonical coordinate**: `lat=-41.151583464812404, lon=175.09968969862783`
**Target taxon**: `GymPiPiPnCx50820-00` (Pinus radiata)
**Year**: 2023

**Trusted control command**:
```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 --lon 175.09968969862783 --year 2023 \
  --model-dir ~/model_local_contract_v4_gatefix_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 --introduced-mode all --top-k 20 \
  --disable-intro-in-gate
```

**Report format for every experiment**:

| Mode | Rank | Probability | vs Control |
|------|------|------------|------------|
| native (0.0) | | | |
| unknown (0.5) | | | |
| introduced (1.0) | | | |

---

## 2. Verified Root Causes (All Three Audits + Code Verification)

### RC1: No Hard Cap Per Species [ALL AUDITS AGREE - Claude primary]

**v2.2**: `HARD_CAP_PER_SPECIES = 50000` at `train_sinr_model.py:138`
Applied via `df.groupby("taxon_id").apply(lambda g: g.sample(n=min(len(g), 50000)))` at lines 395-401.

**v3**: No equivalent exists. Zero matches for `hard_cap`, `HARD_CAP` in `train_on_vm.py`.

**Impact**: Species counts range from 1 to 415,050. Without cap, dominant Pinus confusers get 30-60x more gradient updates than radiata (9,616 samples). The frequency weighting at line 221 clips to [0.25, 16.0] — a 64x range for a 415,050x imbalance (99.98% information loss).

**Confidence**: VERY HIGH. Direct code comparison, mathematically clear impact.

### RC2: Background Loss Missing [Claude + Canonical SINR]

**v2.2**: Background loss at `train_sinr_model.py:1079-1093`:
```python
bg_indices = np.random.randint(0, len(train_dataset), BATCH_SIZE)
bg_output = model(bg_cont_t, bg_cat_t, bg_intro_t)
loss = loss_fn(logits, species_idx, sample_weight, bg_logits)
```
Background term in loss at lines 896-899: `loss_bg = -bg_log_neg.mean()`, weighted by `BG_WEIGHT = 1.0`.

**Canonical Cole SINR** (`github.com/elijahcole/sinr/losses.py`): Background is 50% of the loss:
```python
loss = loss_pos.mean() + loss_bg.mean()  # equal weight
```

**v3**: Zero matches for `bg_logits`, `background`, `bg_weight`, `rand_samples`, `bg_indices` in `train_on_vm.py`. Background loss is completely absent.

**Impact**: Without background term, the model never learns "at random locations, all species should have low probability." It only learns to push down non-target species at observed locations. This lets cosmopolitan confusers maintain high probability everywhere.

**Confidence**: VERY HIGH. Canonical SINR source code confirms background is half the objective.

### RC3: Land-State Train/Serve Mismatch [Codex discovery, verified]

**Training data**: Land-state computed by `land_state_engine.py` using a complex SQL CASE statement with `natural_score`, `canopy_h`, `agb`, `loss_yr`, `lulc_changed`, `hmod`, `fire_freq`, `ntl`, `gain`, `f2nf` — 10+ input variables.

**Inference heuristic** (v3_point_inference.py:136-176): Uses only `xiao_planted_forest`, `treecover2000`, `lossyear`, `fire_frequency_count` — 4 input variables with completely different logic.

**Codex evidence**: Same v4 checkpoint:
- `--land-state-mode heuristic` → rank #16
- `--land-state-mode zero` → rank **#12**

**Impact**: The heuristic inference path introduces distribution shift that HURTS ranking by 4 positions. Setting to zero removes the shift.

**Confidence**: HIGH. Code paths verified. Codex tested and observed the rank difference.

### RC4: Feature Parity Gap — 3 Missing Inference Features [All audits agree]

**Training contract** (`feature_contract_v2_online56.json`): 58 continuous features including `aridity_index`, `et0_mm_yr`.
**Categorical features**: 6 including `ipcc_forest_class`.

**Inference sampler** (`location_predictor_FIXED.py`): Zero matches for `aridity_index`, `et0_mm_yr`, `ipcc_forest_class`. These are silently zero-filled at inference.

**Strict contract check**: `v3_point_inference.py` with `--strict-feature-contract` throws:
`ValueError: Missing required feature-contract fields: env_missing=2, cat_missing=1`

**Impact**: 3 features populated during training but zero at inference = distribution shift. The model learned to use these features but sees zeros at test time.

**Confidence**: VERY HIGH. Code verified, error message confirmed by Codex.

### RC5: AN-Full Correction Term Sign Differs from v2.2 [All audits agree]

**v2.2** (`train_sinr_model.py:889`):
```python
correction = (-target_log_neg + pos_weight * (-target_log_pos)) / num_species
```

**v3** (`train_on_vm.py:287`):
```python
correction = (t_log_neg + pos_weight * (-t_log_pos)) / num_species
```

The first term has opposite signs: v2.2 uses `-target_log_neg` (positive value), v3 uses `+t_log_neg` (negative value). Since `logsigmoid(-x) < 0` always, `-logsigmoid(-x) > 0`.

**Impact**: Changes the loss landscape. v5 (AN-Full) regressed from #16 to #23, likely partly due to this difference. Not the primary cause of v3's issues (v4 uses BCE), but relevant for AN-Full experiments.

**Confidence**: HIGH. Code comparison definitive.

### RC6: Auxiliary Head Negative Transfer [Gemini primary, all agree]

**v3** (`train_on_vm.py:1058-1075`): Planted and land-state aux losses flow through shared trunk with no gradient isolation.

**Planted label** at line 1059-1060: `(x_cat[:, xiao_idx] > 1)` = "is forest" (natural + planted), not "is plantation". v2.2 correctly used `(xiao==3) | (jrc==4)`.

**But**: Codex tested planted label fixes in smoke and they regressed (#919, #256). And v6b (aux disabled) was also poor (#744 smoke).

**Gemini Experiment 1**: Disable both aux weights (`--aux-planted-weight 0.0 --aux-land-state-weight 0.0`) for full 5-shard run. This isolates negative transfer cleanly.

**Impact**: Uncertain. Smoke results are unreliable for 45K species. Full 5-shard aux ablation is needed.

**Confidence**: MEDIUM. Hypothesis is strong but empirical smoke evidence is mixed.

### RC7: Two-Pass Max Inference Missing [Claude]

**v2.2**: `probs_best = np.maximum(probs_native, probs_intro)` — element-wise max across passes.

**v3**: Three separate passes reported independently. No max aggregation.

**Impact**: Each species gets its BEST probability across native/introduced contexts in v2.2. v3 reports separate rankings per mode.

**Confidence**: HIGH. But since v4 uses `--disable-intro-in-gate`, introduced mode has no effect on logits currently — so this is lower priority until introduced conditioning is fixed.

---

## 3. Prioritized Implementation Plan

### Phase 0: FREE IMPROVEMENTS (No Retraining)

#### P0-A: Use land-state-mode=zero at inference [IMMEDIATE]

**What**: Change default or always pass `--land-state-mode zero` when benchmarking.
**Expected**: #16 → #12 (4-rank improvement, already validated by Codex)
**Risk**: None. No code change needed. Just a flag at inference time.
**Verification**: Run benchmark with `--land-state-mode zero`.

#### P0-B: Wire missing GEE features [1-2 hours work]

**What**: Add `aridity_index`, `et0_mm_yr`, `ipcc_forest_class` to `location_predictor_FIXED.py` GEE sampler.
**Files**: `orchestrator/location_predictor_FIXED.py` — add GEE image sources and sampling
**Expected**: Small improvement (reduces train/serve drift for 3 features)
**Risk**: Low. Additive code change.
**Verification**: `--strict-feature-contract` should pass without error.

**GEE sources**:
- `aridity_index`: CGIAR Global Aridity Index (`CGIAR/ARIDITY`) or derived from PET/precip
- `et0_mm_yr`: MODIS MOD16A2 or derived from TerraClimate
- `ipcc_forest_class`: Derived from existing forest type categoricals

### Phase 1: SINGLE-VARIABLE RETRAINING EXPERIMENTS

Each experiment below changes ONE thing from v4 control settings. All use:
- `--disable-intro-in-gate --zero-phylo-input`
- BCE loss mode (v4 control)
- All current contracts pinned
- Full 5-shard training (not smoke)
- Inference with `--land-state-mode zero`

#### P1-A: Hard Cap 50K Per Species [HIGHEST PRIORITY]

**What**: Add `--hard-cap-per-species 50000` to `train_on_vm.py`.
**Where**: After DataFrame loaded, before array construction.
```python
if args.hard_cap_per_species:
    before = len(self.df)
    self.df = self.df.groupby("taxon_id", group_keys=False).apply(
        lambda g: g.sample(n=min(len(g), args.hard_cap_per_species), random_state=42)
    )
    self.df = self.df.reset_index(drop=True)
    log(f"Hard cap {args.hard_cap_per_species}/species: {before:,} → {len(self.df):,}")
```
**Files**: `orchestrator/train_on_vm.py` (add arg + apply in dataset), `orchestrator/run_local_5m_shard_training.py` (pass through)
**Expected**: #12 → #5-8 (major improvement, v2.2's primary balancing mechanism)
**Risk**: Low. Proven in v2.2.
**Version**: v8_hardcap_5m
**Rollback**: Remove `--hard-cap-per-species` flag.

**Training command**:
```bash
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
```

**Decision gate**: If rank improves vs #12 control → lock and proceed to P1-B. If worsens → try 25000 cap.

#### P1-B: Disable Auxiliary Heads [IF P1-A SUCCEEDS]

**What**: `--aux-planted-weight 0.0 --aux-land-state-weight 0.0`
**Where**: No code change needed — flags already exist.
**Expected**: Moderate improvement if negative transfer is real.
**Risk**: None. Existing flags.
**Version**: v9_noaux_5m (includes hard cap if P1-A worked)
**Rollback**: Remove the zero-weight flags.

**Decision gate**: If rank improves → keep aux disabled. If worsens → re-enable aux, negative transfer is not the issue.

#### P1-C: Restore Background Loss [IF P1-A or P1-B SUCCEED]

**What**: Add background sampling and loss term to training loop.
**Where**: `orchestrator/train_on_vm.py` — after forward pass, before loss backward.
```python
# Generate background batch (random indices, all species assumed absent)
bg_indices = np.random.randint(0, len(dataset), len(batch_indices))
bg_batch = dataset[bg_indices]
# ... forward pass on bg_batch ...
bg_log_neg = F.logsigmoid(-bg_logits)
loss_bg = -bg_log_neg.mean()
total_loss = total_loss + args.bg_weight * loss_bg
```
**Expected**: Significant improvement. Teaches global absence prior.
**Risk**: Medium. Doubles compute per batch (~2x slower). Need `--bg-weight` flag (default 1.0).
**Version**: v10_bg_5m
**Rollback**: `--bg-weight 0.0`

### Phase 2: REFINEMENTS (After Phase 1 validated)

#### P2-A: Widen Frequency Weight Clipping
Change `np.clip(weights, 0.25, 16.0)` to `np.clip(weights, 0.05, 100.0)`.

#### P2-B: Two-Pass Max Inference
Add `--two-pass-max` to v3_point_inference.py: `probs = np.maximum(probs_native, probs_intro)`.

#### P2-C: AN-Full Sign Revert
Change line 287 from `(t_log_neg + ...)` to `(-t_log_neg + ...)` to match v2.2.

#### P2-D: Fix Planted Label Semantics
Change line 1059-1060 to match v2.2: `((xiao_vals == 3) | (jrc_vals == 4))` with `has_data` filter. Only after aux coupling is understood.

### Phase 3: ARCHITECTURE (Future, after Phase 1+2 validated)

#### P3-A: Additive Satellite Injection (Sat-SINR style)
Replace gated convex combination with zero-initialized additive injection at each residual block.

#### P3-B: Stop-Gradient Auxiliary Heads
Detach trunk features before passing to aux heads. Heads train independently, trunk only sees species loss.

#### P3-C: Per-Species Inverse-Frequency Weighting (Zbinden 2024)
Apply per-species `w_s = n / n_p(s)` to positive term in loss. +7.3% top-1 in published results.

#### P3-D: ASL Negative Focusing (Ridnik ICCV 2021)
Apply focal negative with `gamma=4, margin=0.05` to down-weight trivially absent species.

---

## 4. What NOT To Do

1. **Do not stack multiple changes** in one experiment.
2. **Do not use smoke (s0) rankings** as go/no-go decisions for 45K species tasks.
3. **Do not pursue AN-Full tuning** before resolving hard cap + background + aux coupling.
4. **Do not modify strict BQ tables** or stop the GEE extraction process.
5. **Do not change planted label** without first understanding aux coupling via P1-B.
6. **Do not rewrite the model architecture** until Phase 1 mechanisms are validated.
7. **Do not trust inference results without `--land-state-mode zero`** until land-state parity is resolved.

---

## 5. Safety Constraints

- **No destructive BQ operations**. Read-only queries only.
- **No stopping strict GEE extractor** without explicit approval.
- **All experiments get unique model dirs**: `~/model_local_contract_v{N}_{name}_5m`
- **All experiments get unique logs**: `orchestrator/local_contract_v{N}_{name}_5m_YYYYMMDD_HHMM.log`
- **v4 baseline preserved** as control throughout.
- **All code changes are additive** (new flags with safe defaults).

---

## 6. Experiment Tracking Table

| Version | Change | Model Dir | Rank (zero-ls) | Prob | vs Control | Status |
|---------|--------|-----------|-----------------|------|------------|--------|
| v4 (control) | BCE + gate-fix | ~/model_local_contract_v4_gatefix_5m | #12 | 0.9499 | — | BASELINE |
| v5 | AN-Full (buggy sign) | ~/model_local_contract_v5_anfull_5m | #23 | — | Regressed | REJECTED |
| v6 | AN-Full sign-fixed | ~/model_local_contract_v6_anfullfix_5m | #59 | — | Regressed | REJECTED |
| v8 full | BCE + 50K cap (no-op) | ~/model_local_contract_v8_hardcap_5m_full | **#2** | 0.9785 | Improved (seed) | BEST |
| v8b | BCE + 2 epochs/shard | ~/model_local_contract_v8b_2epoch_5m | #18 | 0.9526 | Seed variance | DONE (val top10=46.9%) |
| v11 | +no aux (2 ep/shard) | ~/model_local_contract_v11_noaux_5m | TBD | TBD | TBD | RUNNING |
| v12 | +background loss | ~/model_local_contract_v12_bg_5m | TBD | TBD | TBD | PENDING |

**Key findings (2026-03-08)**:
- Hard cap 50K per-shard removes 0 rows (max species count per 1M shard is well under 50K). Must apply at BQ level before sharding.
- v8 full (#2) vs v4 (#12) is entirely random seed variance — configs are functionally identical.
- Single-coordinate benchmark has ~10-rank variance across seeds. Need multi-coordinate or multi-seed validation.
- Smoke rankings (1 shard) do NOT predict full run results (v6 smoke #133 → full #59).

---

## 7. Versioned Contracts (Pinned)

All experiments use these exact contracts:

| Contract | File | Key |
|----------|------|-----|
| Mapping | `orchestrator/contracts/sinr_v3/mapping_contract_v1.json` | 45,247 species |
| Feature | `orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json` | 58 env continuous |
| Frequency | `orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json` | Per-species counts |
| Intro ratio | `orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json` | 30,437 nonzero |
| Stats | `orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz` | 5M preview |
| Temporal stats | `orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz` | 5M preview |

---

## 8. v2.2 vs v3 Definitive Comparison

| Mechanism | v2.2 (works) | v3 (broken) | Fix |
|-----------|-------------|-------------|-----|
| Hard cap/species | 50,000 | None | P1-A |
| Background loss | Yes (BG_WEIGHT=1.0) | None | P1-C |
| Planted label | `(xiao==3)\|(jrc==4)` | `(mapped>1)` = "is forest" | P2-D |
| Feature parity | All 120 sampled | 3 missing at inference | P0-B |
| Land-state parity | Trained=inferred | Different computation paths | P0-A (zero) |
| Two-pass inference | `max(native, intro)` | Separate passes | P2-B |
| AN-Full sign | `-target_log_neg` | `+t_log_neg` | P2-C |
| Freq weight clip | Not applicable (BCE) | [0.25, 16.0] | P2-A |
| Aux heads | Planted only, simple | Planted + land-state, coupled | P1-B |
| Hidden dim | 256 | 384 | — |
| Res blocks | 4 | 6 | — |
| Dropout | 0.3 | 0.25 | — |

---

## 9. Literature-Validated Future Improvements

From web research (verified sources):

| Technique | Source | Expected Impact | When |
|-----------|--------|-----------------|------|
| Per-species inverse-frequency weighting | Zbinden et al. 2024 (arXiv:2403.07472) | +7.3% top-1 | Phase 3 |
| ASL negative focusing (gamma=4) | Ridnik et al. ICCV 2021 | Focus on confusers | Phase 3 |
| Additive satellite injection (ControlNet) | Sat-SINR ISPRS 2024 | Better fusion | Phase 3 |
| Stop-gradient aux heads | ForkMerge NeurIPS 2023 | Prevent neg transfer | Phase 3 |
| Background as 50% of loss | Cole SINR canonical code | Core SINR mechanism | Phase 1 |

---

## 10. File References

| File | Role | Lines of Interest |
|------|------|-------------------|
| `orchestrator/train_on_vm.py` | v3 training | 138(no cap), 221(clip), 265-293(AN-Full), 469-473(boost), 1058-1075(aux) |
| `orchestrator/train_sinr_model.py` | v2.2 training (reference) | 138(cap), 395-401(cap apply), 846-903(AN-Full+bg), 1079-1093(bg sampling), 1105-1108(planted) |
| `orchestrator/v3_point_inference.py` | v3 inference | 46-49(land-state-mode), 136-176(compute_land_state), 253(land-state call) |
| `orchestrator/location_predictor_FIXED.py` | GEE sampler + v2.2 inference | Missing aridity_index, et0_mm_yr, ipcc_forest_class |
| `orchestrator/land_state_engine.py` | BQ land-state computation | 180-197(complex SQL vs simple heuristic at inference) |
| `orchestrator/run_local_5m_shard_training.py` | 5-shard sequential trainer | Needs --hard-cap-per-species passthrough |
| `orchestrator/contracts/sinr_v3/` | All versioned contracts | Pinned for all experiments |
| `docs/SINR March 6 claude.md` | Claude forensic audit | 5 root causes + literature |
| `docs/SINR March 6 gemini.md` | Gemini forensic audit | 3 experiments + hygiene rules |
| `docs/SINR March 7 Deep Root Cause + Action Plan.md` | Codex deep-dive | Land-state finding + feature parity |
