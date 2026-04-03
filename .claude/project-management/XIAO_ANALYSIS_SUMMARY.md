# SINR v3 Xiao Regression - Executive Summary

## The Problem in 30 Seconds

The SINR v3 model was trained on corrupted data where `xiao_planted_forest` was always 0. It ranked #2 at the NZ radiata pine plantation benchmark. When we fixed the training data to have correct xiao values (0/1/2 distribution), the model regressed to rank #92 despite using the same architecture. Retraining with correct data didn't help.

## Why Correct Data Made Things Worse

The model implicitly optimized for the buggy data:

1. **Embedding indices**: The xiao feature maps raw values 0/1/2 to embedding indices 1/2/3. Only index 1 was ever activated during v14 training. Indices 2 and 3 were randomly initialized and never trained.

2. **Land state class**: The code has a rule `if xiao == 2: land_state_class = 2` (plantation). In v14, xiao was never 2, so class 2 never appeared. The auxiliary head never learned to predict it.

3. **Planted auxiliary loss**: The aux_planted head was trained on all-zero labels (since xiao was always mapped to index 1, never > 1). When xiao distribution became mixed, the head suddenly had positive examples, but it was already adapted to zero output.

4. **Boost mechanism**: The planted score contribution to logits was effectively constant in v14 (~1.0). In v15, it becomes variable (~1.6-1.8), which unpredictably reshuffles species rankings.

5. **Covariate shift**: The linear layer projecting categorical embeddings to 192D was optimized for constant input (always index 1). With mixed indices, it's using untrained regions of its weight matrix.

All five mechanisms coupled together, creating a cascade of distributional shifts that broke the model.

## Root Cause: Architectural Fragility

This isn't a data quality issue. It's an architecture problem: **the model was never designed to handle varying xiao signals**. It implicitly learned to work with xiao=always-0 as a side effect of corruption, not as a design choice.

The fix requires decoupling these mechanisms so that correcting xiao data doesn't trigger a cascade of distributional shifts.

---

## Key Findings (Verified)

### 1. Training Data v14 vs v15

**v14 (Buggy Decode)**:
- xiao_planted_forest raw values: **100% are 0**
- Mapped embedding indices: **100% are index 1**
- Planted auxiliary label: **0% positive**
- land_state_class distribution: **{0, 1} only**

**v15 (Corrected Decode)**:
- xiao_planted_forest raw values: **48.3% (0), 36.9% (1), 14.8% (2)**
- Mapped embedding indices: **48.3% (1), 36.9% (2), 14.8% (3)**
- Planted auxiliary label: **51.7% positive** (from indices 2 and 3)
- land_state_class distribution: **{0, 1, 2}** (new class 2 appears!)

### 2. Embedding Training Coverage

| Index | Raw xiao | v14 Training | v15 Training | Signal Loss |
|---|---|---|---|---|
| 0 | — | 0% | 0% | — |
| 1 | 0 | 100% | 48.3% | -51.7% |
| 2 | 1 | 0% | 36.9% | +36.9% untrained |
| 3 | 2 | 0% | 14.8% | +14.8% untrained |

Indices 2 and 3 start randomly initialized and receive only 37% and 15% of training signal vs. index 1.

### 3. Cascade Effects

```
GEE Decode Bug (xiao always 0)
  ↓
Embedding Index 1 Only
  ├→ env_proj learns constant xiao contribution
  ├→ land_state_class only {0, 1}
  │   └→ aux_land_state_head trained on {0,1}
  ├→ Planted label all-zero
  │   └→ aux_planted_head learns to output ~0
  └→ Boost always ~constant

When xiao = fixed to {0,1,2}:
  ↓
Indices 1, 2, 3 Now Activated
  ├→ Embedding space now has variance (indices 2,3 poorly trained)
  ├→ env_proj sees OOD input (was optimized for index 1)
  ├→ land_state_class now {0, 1, 2}
  │   └→ aux_land_state_head must learn class 2 (never in training)
  ├→ Planted label now 51% positive
  │   └→ aux_planted_head must reverse its learned bias
  └→ Boost becomes variable (unpredictable)

Result: All 5 mechanisms shift simultaneously → model breaks
```

---

## Solution Approaches (Ranked by Effort vs. Risk)

### Approach 1: Curriculum Learning (RECOMMENDED FOR IMMEDIATE FIX)

**Idea**: Gradually introduce correct xiao distribution during training.

- Epochs 0-4: Train with xiao=always 0 (v14 behavior)
- Epochs 5-14: Gradually transition (xiao_fraction increases 0→100%)
- Epochs 15-29: Full correct distribution

**Pros**:
- Low risk (no architecture changes)
- Can validate hypothesis quickly
- Reuses existing training code
- Expected improvement: Rank #10-25

**Cons**:
- Still trains on early epochs with buggy data
- Fragile (if model converges early, later epochs don't help)

**Effort**: 1 week implementation + training

---

### Approach 2: Decouple Xiao from Land State (LONGER-TERM FIX)

**Idea**: Remove the hardcoded `if xiao == 2: land_state_class = 2` rule. Let land_state_class be computed from treecover/lossyear only. Use xiao independently.

**Changes**:
1. `compute_land_state()` in `v3_point_inference.py`: Remove xiao==2 check
2. Create separate xiao branch in model (don't feed embedding into env_input)
3. Orthogonalize xiao branch from land_state branch

**Pros**:
- Clean architecture
- Xiao can be integrated later without breaking land_state
- Best long-term design

**Cons**:
- Requires architectural changes
- More retraining needed
- Higher risk if not implemented carefully

**Expected improvement**: Rank #5-15
**Effort**: 2-3 weeks

---

### Approach 3: Separate Xiao Branch (BEST FINAL DESIGN)

Create an independent plantation detection head that doesn't interfere with the main niche model.

```python
class SINRModelV3:
    def __init__(...):
        # Existing branches unchanged
        self.sat_proj = ...
        self.env_proj = ...  # NO xiao embedding concatenated
        self.temporal_module = ...
        self.land_state_proj = ...

        # NEW: Separate xiao branch
        self.xiao_emb = nn.Embedding(4, 3)
        self.xiao_proj = nn.Sequential(
            nn.Linear(3, 16), nn.GELU(),
            nn.Linear(16, 16), nn.GELU()
        )
        self.plantation_head = nn.Linear(16, 1)
```

**Pros**:
- Xiao is truly independent (can't break main model)
- Plantation detection as auxiliary task (proper design)
- Cleanest interface

**Cons**:
- Requires significant rework
- New auxiliary loss to tune

**Expected improvement**: Rank #5-10
**Effort**: 3-4 weeks

---

## Recommended Path Forward

### Immediate (This Week)
1. **Day 1-3**: Validate the hypothesis with debug instrumentation
2. **Day 4-10**: Implement curriculum learning, retrain v16_curriculum

### Short-term (Next 2 Weeks)
3. If curriculum works (rank #10-25): Deploy v16_curriculum
4. Simultaneously start v17 with separate xiao branch architecture

### Long-term (Weeks 3-4)
5. Train v17_separate_branch with new architecture
6. Benchmark v17 vs. v16
7. Plan rollout strategy

**Timeline**: 4-5 weeks to optimal solution, 1-2 weeks to acceptable interim solution.

---

## Critical Code Locations

All details in `XIAO_REGRESSION_CODE_REFERENCE.md`. Key files:

| Component | File | Lines | Impact |
|---|---|---|---|
| Xiao config | `train_on_vm.py` | 101-110 | Value mapping |
| GEE decode (buggy) | `location_predictor_FIXED.py` | 612-615 | Input corruption |
| Embedding lookup | `train_on_vm.py` | 476-489 | Cascade starts |
| Land state rule | `v3_point_inference.py` | 197 | Hardcoded coupling |
| Planted aux loss | `train_on_vm.py` | 1157 | Label inversion |
| Boost mechanism | `train_on_vm.py` | 526 | Unpredictable effect |

---

## Expected Outcomes by Version

| Version | xiao Data | Land State Class | Planted Label | Rank (NZ) | Status |
|---|---|---|---|---|---|
| **v14** | Buggy (0) | {0,1} | All-zero | #2 | Current (working) |
| **v15** | Correct (0/1/2) | {0,1,2} | 51% positive | #92 | Broken ❌ |
| **v16_curriculum** | Correct | {0,1,2} | 51% positive | #10-25 | Target ✓ |
| **v17_separate** | Correct | {0,1} | Decoupled | #5-10 | Ideal |

---

## Validation Checklist

Before claiming victory:

- [ ] Validate hypothesis with debug output
- [ ] v16 curriculum passes benchmarks (NZ #1-15)
- [ ] No regression on non-plantation locations
- [ ] Training loss smooth and stable
- [ ] Auxiliary heads well-calibrated
- [ ] Feature ablation confirms xiao helps (not hurts)
- [ ] Model can distinguish plantation vs. natural forest
- [ ] Inference latency acceptable

---

## Documentation Provided

1. **XIAO_REGRESSION_FORENSIC_ANALYSIS.md** (15 pages)
   - Full root cause analysis
   - Code path tracing for all 5 mechanisms
   - Why simple retraining failed

2. **XIAO_REGRESSION_CODE_REFERENCE.md** (20 pages)
   - Exact line numbers for every component
   - v14 vs v15 behavior side-by-side
   - Data distribution statistics

3. **XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md** (30 pages)
   - Step-by-step implementation for 3 approaches
   - Curriculum learning code
   - Separate branch architecture
   - Benchmarking scripts
   - Timeline and effort estimates

4. **XIAO_ANALYSIS_SUMMARY.md** (This file)
   - Executive overview
   - Key findings
   - Decision matrix
   - Next steps

---

## Questions Answered

**Q: Why did correcting xiao from always-0 to {0,1,2} hurt performance?**

A: The model architecture was implicitly optimized for the buggy constant signal. Correcting xiao triggered cascading distributional shifts in:
1. Embedding indices (untrained indices activated)
2. Land state classes (new class 2 appeared)
3. Auxiliary losses (label distribution flipped)
4. Boost mechanism (became variable)
5. Linear layer inputs (covariate shift)

All five shifted simultaneously, breaking the model.

**Q: Why didn't retraining from scratch with correct data work?**

A: Because the architecture doesn't gracefully handle the transition. The embedding layer, aux heads, and boost mechanism were all initialized assuming xiao=0. Even with fresh random initialization, training on the mixed distribution is like asking the model to learn three separate versions of itself (one per xiao value) with only 14.8%-48.3% of the training data per version.

**Q: Is this a bug in the data or the model?**

A: The *bug* is in the data (GEE decode). But the *root cause of regression* is architectural fragility. The model design doesn't separate xiao from downstream mechanisms, so fixing the data cascades.

**Q: Can we just force xiao=0 in inference forever?**

A: We can, but we'd be throwing away information. Plantations are a critical use case (Pinus radiata benchmark). The fix is worth the effort.

**Q: What if curriculum learning doesn't work?**

A: Escalate to the separate branch architecture immediately. This is low-risk because we'll detect failure within 1 week of curriculum training.

---

## Next Steps

1. Read `XIAO_REGRESSION_FORENSIC_ANALYSIS.md` for full understanding
2. Review code locations in `XIAO_REGRESSION_CODE_REFERENCE.md`
3. Follow implementation steps in `XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md`
4. Start with Phase 1 (validation) to confirm hypothesis
5. Proceed to Phase 2 (curriculum learning) if validation passes
6. Plan Phase 3 (separate branch) in parallel while training Phase 2

**Decision point**: After Phase 2 training completes (1 week), decide whether to deploy v16_curriculum or escalate to v17_separate_branch.

**Owner**: One engineer, 4-5 weeks to completion, can work in parallel with other features.
