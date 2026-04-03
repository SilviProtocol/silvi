# SINR v3 Xiao Regression - Visual Explanation

## The Core Problem in One Diagram

```
v14 Training (BUGGY)              v15 Training (CORRECT)
─────────────────────────────────────────────────────────

Xiao Raw:     0   0   0   0       Xiao Raw: 0   1   2   0
              [100% all 0s]                  [48% 37% 15%]

Mapped Index: 1   1   1   1       Mapped:   1   2   3   1
              [all use index 1]             [mixed indices]

Embedding:    E₁  E₁  E₁  E₁      Embedding: E₁  E₂  E₃  E₁
              [constant!]                   [variable!]

env_proj      linear layer        env_proj: linear layer
Input:        [89D + 3D] = 145D   Input:    [89D + 3D] = 145D
Output:       [192D]              Output:   [192D]
              well-optimized             struggling with E₂, E₃

Land State:   class ∈ {0,1}       Land State: class ∈ {0,1,2}
              [only 2 classes]            [3 classes, new class 2]

Aux Head:     trained on          Aux Head:  must learn
              all zeros                    non-zero targets

Boost:        1.0 * intro_ratio    Boost:    1.8 * intro_ratio
              constant            variable, unpredictable


RESULT: Works (#2)                RESULT: Broken (#92)
```

---

## The Cascade Effect

```
                        GEE Decode Bug
                      xiao_class=0 always
                              ↓
                    ┌─────────────────────┐
                    │ Embedding Layer     │
                    │ index always = 1    │ ← E₁ gets 100% training
                    │ (3D learned vector) │   E₂, E₃ unused
                    └─────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
  ┌──────────────┐                         ┌──────────────────┐
  │ env_proj     │                         │ compute_land_    │
  │ (145→192)    │ ← Optimized for         │ state()          │
  │ Linear layer │   constant input       │ if xiao==2:      │
  │              │   (index 1)             │   class=2        │
  └──────────────┘                         │ (never happens)  │
        ↓                                   └──────────────────┘
        ↓                                           ↓
  ┌──────────────┐                         ┌──────────────────┐
  │ Fused        │                         │ aux_land_state_  │
  │ representation                         │ head             │
  │ (192D)       │                         │ (trained on      │
  │ Works well   │                         │  classes 0,1)    │
  └──────────────┘                         └──────────────────┘
        ↓                                           ↓
        ├─────────────────────┬─────────────────────┤
        ↓                     ↓                     ↓
   ┌─────────┐         ┌──────────┐         ┌──────────────┐
   │ Logits  │         │aux_      │         │Land state (5D)
   │(from    │         │planted   │         │flows to trunk │
   │trunk)   │         │head      │         └──────────────┘
   └─────────┘         │(trained  │
        ↓              │on        │
        ├─ boost ←─ zero labels) │
        ↓              └──────────┘
   ┌─────────────┐           ↓
   │ Final       │      boost ≈ 0.5
   │ Logits      │      (very small)
   │ (adjusted)  │
   └─────────────┘
        ↓
   Predictions ✓
   Rank #2 ✓
```

**Problem**: Everything is tightly coupled. Change xiao → everything shifts.

```
When we FIX xiao to {0,1,2}:

        CORRECT Xiao Values {0,1,2}
                      ↓
        ┌──────────────┴───────────────┐
        ↓                              ↓
    Index 1 (48%)               Indices 2,3 (52%)
    Well-trained           Only 37% and 15% training data
    E₁ learned signal      E₂, E₃ randomly initialized
                           Poorly trained → noisy embeddings
        ↓                              ↓
        └──────────┬───────────────────┘
                   ↓
        ┌──────────────────────────┐
        │ env_proj sees mixed      │
        │ embedding distribution   │ ← Linear layer was optimized
        │ E₁(48%) + E₂(37%) +      │   for constant E₁, now sees
        │ E₃(15%)                  │   high-variance input
        └──────────────────────────┘   → Covariate shift!
                   ↓
        ┌──────────────────────────┐
        │ Output noisy             │
        │ (E₂, E₃ have poor        │
        │ representations)         │
        └──────────────────────────┘
                   ↓
            ┌──────┴────────┐
            ↓               ↓
    ┌──────────────┐  ┌───────────────────┐
    │land_state    │  │ planted aux head  │
    │class now     │  │ now sees 51%      │
    │includes 2    │  │ positive labels   │
    │(new!)        │  │ (was 0%)          │
    │              │  │                   │
    │Aux head      │  │ Output flips from │
    │trained on    │  │ ~0.5 to ~0.8      │
    │{0,1}         │  │                   │
    │must learn    │  │ Boost changes     │
    │class 2       │  │ unpredictably     │
    │              │  │                   │
    │Conflicts     │  │ Conflicts with    │
    │with v14      │  │ v14 training      │
    │training      │  │                   │
    └──────────────┘  └───────────────────┘
            ↓                   ↓
            └────────┬──────────┘
                     ↓
        ┌────────────────────────────┐
        │ Main trunk receives         │
        │ conflicting signals         │
        │ - noisy env_h              │
        │ - wrong land_state class   │
        │ - unstable boost           │
        │                            │
        │ Model is broken            │
        │ Rank #92 ❌               │
        └────────────────────────────┘
```

---

## Why Each Component Breaks

### 1. Embedding Index Problem

```
v14 Training:                    v15 Inference:
┌────────────────────┐          ┌────────────────────┐
│ Embedding Matrix   │          │ Embedding Matrix   │
│ (vocab_size=4,     │          │ (vocab_size=4,     │
│  emb_dim=3)        │          │  emb_dim=3)        │
├────────────────────┤          ├────────────────────┤
│ idx 0: [0,0,0]     │          │ idx 0: [0,0,0]     │
│ idx 1: [a,b,c] ✓✓✓│ ← 100%   │ idx 1: [a,b,c] ✓✓✓ │ ← 48%
│        all samples  │          │        training    │
│ idx 2: [d,e,f]     │ ← 0%     │ idx 2: [d,e,f]     │ ← 37%
│        never used   │          │        training    │
│ idx 3: [g,h,i]     │ ← 0%     │ idx 3: [g,h,i]     │ ← 15%
│        never used   │          │        training    │
└────────────────────┘          └────────────────────┘

v14 Inference:                   What Goes Wrong:
Sample → raw 0                   Sample → raw 0/1/2
      ↓                               ↓
   mapped 1                       mapped 1/2/3
      ↓                               ↓
   lookup [a,b,c]                 lookup [a,b,c] OR [d,e,f] OR [g,h,i]
   ✓ well-trained                 ✓ 48% chance of good
                                  ✗ 52% chance of poor
                                     training signal
```

**Math**: With 5M training samples and 384D hidden dimension:
- Index 1: 2.4M samples, signal/noise ratio optimal
- Index 2: 1.8M samples (75% of index 1), signal spreads thinner
- Index 3: 0.7M samples (29% of index 1), barely trained above noise

### 2. Land State Class Problem

```
v14 Training Data           v15 Training Data
─────────────────          ─────────────────

land_state_class           land_state_class
distribution:              distribution:

class 0: 45%                class 0: 45%
class 1: 55%                class 1: 40%
class 2:  0% ← NEVER        class 2: 15% ← NEW!
class 3:  0%                class 3:  0%
class 4:  0%                class 4:  0%
class 5:  0%                class 5:  0%


aux_land_state_head        aux_land_state_head
(Linear: 384→6)            (Linear: 384→6)

Trained on:                Trained on:
{0, 1}  ← 2 classes        {0, 1, 2} ← 3 classes

During inference:          During inference:
- class 0: good           - class 0: good
- class 1: good           - class 1: good
- class 2: RANDOM         - class 2: learned but
  (never trained)           confuses with 0,1
- class 3+: random        - class 3+: random

Result: Loss increases     Result: Worse loss
but stable              worse generalization
```

### 3. Planted Auxiliary Loss Problem

```
v14 Training                    v15 Training
──────────────                  ──────────────

Planted Label:                  Planted Label:
x_cat[:, xiao_idx] > 1          x_cat[:, xiao_idx] > 1

When xiao_idx mapped to:        When xiao_idx mapped to:
1 → False (never true)          1 → False (48% samples)
                                2 → True (37% samples)
                                3 → True (15% samples)

Label distribution:             Label distribution:
0: 100% of samples             0: 48% of samples
1:   0% of samples             1: 52% of samples

BCELoss on head output:         BCELoss on head output:

aux_planted_head learns:        aux_planted_head learns:
"output 0 always"               "output 1 when index >1
                                 output 0 when index =1"

During inference (v14):         During inference (v15):
real plantation (xiao=2)        real plantation (xiao=2)
→ index=3                        → index=3
→ head outputs ~0               → head outputs ~0.8-0.9
→ planted_score=0.5             → planted_score=0.8-0.9
→ boost ≈ 1.0                   → boost ≈ 1.6

Result: Weak boost              Result: Strong boost
but consistent                   but unpredictable
```

### 4. Linear Layer Covariate Shift

```
v14: env_proj input distribution
────────────────────────────────
x_env (89D continuous): Normal(0, 1) after normalization
xiao_emb (3D embedding): [a, b, c] CONSTANT for all samples

Combined input (145D):
[normal + constant] repeated 5M times

env_proj = Linear(145, 192)
learns optimal W, b for this distribution

v15: env_proj input distribution
────────────────────────────────
x_env (89D continuous): Normal(0, 1) after normalization
xiao_emb (3D embedding): mixture of [a,b,c], [d,e,f], [g,h,i]

Combined input (145D):
[normal + variable] repeated 5M times

Same W, b are now suboptimal for mixture
Especially for [d,e,f] and [g,h,i] which weren't in training
→ covariate shift
→ worse reconstruction
→ loss increases
```

---

## The Fix: Decouple the Mechanisms

```
CURRENT (BROKEN):              FIXED (PROPOSED):
─────────────────────          ────────────────────

xiao_raw                       xiao_raw
   ↓                              ↓
xiao_embedding                 xiao_embedding
   ↓                              ↓
[concatenate with              [separate path]
 89 continuous +                   ↓
 other embeddings]             xiao_proj
   ↓                              ↓
env_proj (145→192)             plantation_head
   ├→ env_h                        ↓
   └→ gate fusion              plantation_score
       ↓                           ↓
       ├→ compute_land_state    [NOT FUSED with env_h]
       │    (xiao triggers 2)       ↓
       │    ↓                    [used only for aux loss
       │ [class 2 sometimes]        and logit boost]
       │ ↓
       │ land_state_branch
       │    ├→ aux_land_state_head
       │    └→ land_h
       │
       └→ main_trunk
            ├→ logits
            ├→ aux_planted_head
            └→ boost
                ↓
            logits + boost
```

Benefits:
1. **xiao embedding**: Still learns from all samples, but doesn't contaminate env_h
2. **land_state_class**: No longer depends on xiao, stays {0, 1}
3. **aux_land_state**: Trained only on {0, 1}, no class 2 confusion
4. **env_proj**: Input distribution stable (no xiao variance)
5. **aux_planted**: Can be its own head, independent from aux_land_state

---

## Expected Performance Trajectory

```
Version         Xiao Data    Strategy         Rank    Timeline
───────────────────────────────────────────────────────────────

v14 (current)   Buggy (0)    As-is            #2      Live
v15 (failed)    Correct      Direct retrain   #92     ✗ Broken

PHASE 2: Quick Fix
v16 curriculum  Correct      Curriculum       #10-20  1 week

PHASE 3: Clean Fix
v17 separate    Correct      Decouple arch    #5-10   3 weeks
```

---

## Debugging Visualization

If v16 curriculum training fails, here's how to diagnose:

```
Training Loss Not Decreasing?
    ├─ Check: Curriculum schedule
    │  (is xiao_fraction changing?)
    └─ Diagnostic: log curriculum_epoch, xiao_fraction
       Expected: fraction increases 0→1 smoothly

Validation Accuracy Plateaus?
    ├─ Check: Embedding indices distribution
    │  (are all 3 indices being used?)
    └─ Diagnostic: print x_cat[:, xiao_idx].unique()
       Expected: values should include 1, 2, 3

Auxiliary Loss Spikes?
    ├─ Check: Planted label distribution
    │  (is it matching xiao distribution?)
    └─ Diagnostic: print (x_cat[:, xiao_idx] > 1).float().mean()
       Expected: ~0.52 (36.9% + 14.8%)

Logits Blowing Up?
    ├─ Check: Boost magnitude
    │  (is boost term stable?)
    └─ Diagnostic: print boost.mean(), boost.std()
       Expected: mean ~1.0-1.5, std ~0.3-0.5

Inference Produces Wrong Ranks?
    ├─ Check: Feature distribution at inference
    │  (does computed xiao match training data?)
    └─ Diagnostic: compare inference xiao vs.
       training xiao histogram
       Expected: distribution should match
```

---

## Key Takeaway

**The problem is NOT data corruption. The problem is architectural assumptions.**

The model was implicitly trained on:
- Constant xiao signal
- 2-class land_state
- Zero planted labels
- Fixed boost contribution

When xiao was corrected, all four assumptions broke simultaneously. Fixing just the data exposes the architectural fragility.

**The solution** is to decouple these mechanisms so that fixing xiao doesn't cascade through the entire model.

**Timeline**: 4-5 weeks to optimal design, 1-2 weeks to acceptable interim fix.
