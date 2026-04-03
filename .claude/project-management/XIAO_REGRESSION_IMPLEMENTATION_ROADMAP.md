# SINR v3 Xiao Regression - Implementation Roadmap

This document provides concrete implementation steps to fix the xiao regression and achieve a model that works correctly with true forest type data.

---

## Problem Statement (TL;DR)

- **v14**: Trained on buggy xiao=always 0, ranked #2 at NZ plantation
- **v15**: Trained on correct xiao distribution, ranked #92
- **Root cause**: Architecture assumes constant xiao signal; correct data breaks this assumption

**Goal**: Achieve v16 with correct xiao AND good performance (target: rank #10-20)

---

## Strategy Comparison

| Strategy | Effort | Risk | Timeline | Expected Rank |
|---|---|---|---|---|
| **Revert to Buggy** | 1 day | Low | Immediate | #2 (but wrong semantics) |
| **Simple Retrain** | 3 days | High | 1 week | #92 (fails) |
| **Decouple + Regularize** | 2 weeks | Medium | 3-4 weeks | #10-15 (goal) |
| **Curriculum Learning** | 1 week | Low | 2 weeks | #15-25 (likely) |
| **Separate Branch** | 3 weeks | Low | 4-5 weeks | #5-10 (if done well) |

**Recommendation**: Start with **Curriculum Learning** (lowest risk, 2 weeks) to validate the hypothesis. If successful, escalate to **Separate Branch** (best long-term).

---

## Phase 1: Validation & Diagnosis (Days 1-3)

### 1.1 Reproduce the Regression

```bash
# Load v14 checkpoint
python3 orchestrator/v3_point_inference.py \
  --lat -41.1508 --lon 175.0997 \
  --model-dir ~/model_local_5m \
  --top-k 20 \
  --target-taxon GymPiPiPnCx50820-00  # Pinus radiata

# Check rank (should be #2)
# Expected output rank in top-2
```

### 1.2 Instrument Inference to Log Internal States

Create `orchestrator/v3_point_inference_debug.py`:

```python
def run_one_pass_debug(model, idx_to_species, x_cont, x_cat, x_intro, x_temporal,
                       x_land, x_phylo, top_k, x_location=None, debug=False):
    """Run inference with intermediate state logging."""
    with torch.no_grad():
        # Capture embeddings
        xiao_idx = 1  # position of xiao in CATEGORICAL_FEATURES
        xiao_emb = model.embeddings['xiao_planted_forest'](x_cat[:, xiao_idx:xiao_idx+1])

        # Capture auxiliary outputs
        logits, aux_planted, aux_land_state = model(
            x_cont, x_cat, x_intro, x_temporal, x_land, x_phylo, x_location)

        if debug:
            print(f"\n=== Inference Debug ===")
            print(f"Xiao categorical index: {x_cat[0, xiao_idx].item()}")
            print(f"Xiao embedding shape: {xiao_emb.shape}, norm: {xiao_emb.norm().item():.4f}")
            print(f"Land state class: {x_land[0, 0].item()}")
            print(f"Aux planted raw: {aux_planted[0, 0].item():.4f}")
            print(f"Aux planted sigmoid: {torch.sigmoid(aux_planted[0, 0]).item():.4f}")
            print(f"Logits range: [{logits.min().item():.2f}, {logits.max().item():.2f}]")

        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

    top_idx = np.argsort(probs)[::-1][:top_k]
    top = [(rank + 1, idx_to_species[int(i)], float(probs[i]))
           for rank, i in enumerate(top_idx)]
    return probs, top

# Call with debug=True
```

### 1.3 Compare Embedding Representations

```python
# Test embedding indices
model = load_model()
xiao_embeddings = model.embeddings['xiao_planted_forest'].weight

for idx in range(4):
    emb = xiao_embeddings[idx]
    print(f"Index {idx}: {emb.detach().cpu().numpy()} (norm: {emb.norm():.4f})")

# Expected:
# - Index 0: [0, 0, 0] (padding)
# - Index 1: Consistent learned 3D vector
# - Index 2: Another 3D vector (less trained)
# - Index 3: Another 3D vector (even less trained)
```

### 1.4 Log v14 vs v15 Training Data Distributions

```python
# Quick inspection
import pandas as pd

df = pd.read_parquet("~/data/unified_0.parquet")
xiao_counts = df['xiao_planted_forest'].value_counts().sort_index()
print(f"Xiao distribution:\n{xiao_counts}")

# Calculate mapped indices distribution
value_map = {0: 1, 1: 2, 2: 3}
mapped = df['xiao_planted_forest'].map(value_map)
mapped_counts = mapped.value_counts().sort_index()
print(f"Mapped indices distribution:\n{mapped_counts}")
```

**Expected Output**:
```
Index 0: [0, 0, 0] (padding, unused)
Index 1: [a, b, c] (well-trained)
Index 2: [d, e, f] (37% training)
Index 3: [g, h, i] (15% training)
```

---

## Phase 2: Curriculum Learning Approach (Days 4-10)

This is the **lowest-risk** path to validate the hypothesis.

### 2.1 Modify Training Loop for Curriculum

**File**: `orchestrator/train_on_vm.py`

Add curriculum learning flag and schedule:

```python
# Near line 45, add:
class CurriculumConfig:
    """Curriculum learning for xiao feature."""
    enabled: bool = True
    warm_epochs: int = 5          # Epochs 0-4: xiao=0 only
    transition_epochs: int = 10   # Epochs 5-14: gradually introduce xiao
    full_epochs: int = 15         # Epochs 15+: full distribution

    def get_xiao_mask(self, epoch, total_epochs):
        """Return fraction of samples to use correct xiao at this epoch."""
        if epoch < self.warm_epochs:
            return 0.0  # Use xiao=0 only
        elif epoch < self.warm_epochs + self.transition_epochs:
            # Linear interpolation from 0% to 100%
            progress = (epoch - self.warm_epochs) / self.transition_epochs
            return progress
        else:
            return 1.0  # Full distribution

# Add to argparse:
parser.add_argument('--curriculum-enabled', action='store_true', default=True)
parser.add_argument('--curriculum-warm-epochs', type=int, default=5)
```

### 2.2 Apply Curriculum in Dataset

```python
# In SINRDataset.__init__, after line 599:
def apply_curriculum(self, xiao_fraction):
    """Replace xiao values: keep original with prob xiao_fraction,
    set to 0 otherwise."""
    if xiao_fraction >= 1.0:
        return  # No modification

    # Find xiao column index
    for i, (col, cfg) in enumerate(CATEGORICAL_FEATURES.items()):
        if col == 'xiao_planted_forest':
            xiao_col_idx = i
            break
    else:
        return

    # Randomly replace with 0 (raw value, before mapping)
    mask = np.random.random(len(self.df)) > xiao_fraction
    self.cat_data[mask, xiao_col_idx] = 1  # Mapped from raw 0
```

### 2.3 Integrate into Training Loop

```python
# In train() function, around line 1084 (training loop):
curriculum_cfg = CurriculumConfig()

for epoch in range(start_epoch, args.epochs):
    # ... line 1085-1096 ...

    # NEW: Apply curriculum
    if curriculum_cfg.enabled:
        xiao_fraction = curriculum_cfg.get_xiao_mask(epoch, args.epochs)
        dataset.apply_curriculum(xiao_fraction)
        if epoch % 5 == 0:
            log(f"Epoch {epoch}: Curriculum xiao_fraction={xiao_fraction:.2f}")

    # ... rest of training loop ...
```

### 2.4 Run Curriculum Training

```bash
cd orchestrator
python3 train_on_vm.py \
  --train \
  --epochs 30 \
  --curriculum-enabled \
  --curriculum-warm-epochs 5 \
  --curriculum-transition-epochs 10 \
  --model-dir ~/model_v16_curriculum \
  --artifact-version "v16_curriculum" \
  > training_v16_curriculum_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

### 2.5 Benchmark Results

After training completes:

```bash
# Test on NZ plantation
python3 orchestrator/v3_point_inference.py \
  --lat -41.1508 --lon 175.0997 \
  --model-dir ~/model_v16_curriculum \
  --artifact-version v16_curriculum \
  --top-k 20 \
  --target-taxon GymPiPiPnCx50820-00

# Expected: Rank #10-25 (improvement from #92)

# Test on other benchmarks to ensure no regression
python3 orchestrator/v3_point_inference.py \
  --lat -3.12 --lon -60.02 \
  --model-dir ~/model_v16_curriculum \
  --top-k 20
```

**Success Criteria**:
- NZ plantation: Rank improves from #92 to #20 or better
- No catastrophic regression on other benchmarks
- Training loss smoothly decreases

---

## Phase 3: Separate Xiao Branch (Weeks 2-3)

If curriculum learning works, escalate to a more principled fix.

### 3.1 Modify Model Architecture

**File**: `orchestrator/train_on_vm.py`, lines 400-470

```python
class SINRModelV3:
    def __init__(self, ..., use_xiao_branch=True):
        # ... existing __init__ ...

        self.use_xiao_branch = use_xiao_branch

        # EXISTING: Generic categorical embeddings
        self.embeddings = nn.ModuleDict()
        for col_name, cfg in self.categorical_config.items():
            if col_name != 'xiao_planted_forest' or not use_xiao_branch:
                self.embeddings[col_name] = nn.Embedding(
                    cfg["vocab_size"], cfg["emb_dim"], padding_idx=0)

        # NEW: Specialized xiao branch
        if use_xiao_branch:
            self.xiao_emb = nn.Embedding(4, 3, padding_idx=0)
            self.xiao_proj = nn.Sequential(
                nn.Linear(3, 16), nn.GELU(),
                nn.Linear(16, 16), nn.GELU()
            )
            self.plantation_head = nn.Linear(16, 1)  # Binary: planted or not
            self.plantation_scale = nn.Parameter(torch.tensor(1.0))

        # ... rest of model ...
```

### 3.2 Update Forward Pass

```python
def forward(self, x_continuous, x_categorical, x_is_introduced,
            x_ae_temporal, x_land_state, x_phylo, x_location=None):
    B = x_continuous.shape[0]
    cat_embs = {}
    cat_emb_list = []

    if x_categorical is not None:
        for i, col_name in enumerate(self.categorical_config.keys()):
            if col_name == 'xiao_planted_forest' and self.use_xiao_branch:
                # SPECIAL: Use raw xiao value, not embedding
                # Extract xiao from x_categorical (it's the mapped index)
                # We'll pass this to compute_land_state separately
                continue

            emb = self.embeddings[col_name](x_categorical[:, i])
            cat_embs[col_name] = emb
            cat_emb_list.append(emb)

    # NEW: Separate xiao branch
    if self.use_xiao_branch:
        xiao_idx = list(self.categorical_config.keys()).index('xiao_planted_forest')
        xiao_emb = self.xiao_emb(x_categorical[:, xiao_idx])
        xiao_h = self.xiao_proj(xiao_emb)
        plantation_score = torch.sigmoid(self.plantation_head(xiao_h))

        # Store for auxiliary loss
        self._plantation_score = plantation_score

    # Existing branches (without xiao in env_input)
    x_sat = x_continuous[:, :self.NUM_SAT_DIMS]
    sat_h = self.sat_proj(x_sat)
    temporal_h = self.temporal_module(x_ae_temporal)
    x_env = x_continuous[:, self.NUM_SAT_DIMS:]
    env_input = torch.cat([x_env] + cat_emb_list, dim=1)
    env_h = self.env_proj(env_input)
    land_h = self.land_state_proj(x_land_state)

    # ... rest of forward pass ...
```

### 3.3 Update Auxiliary Loss

```python
# In training loop, around line 1145
if 'xiao_planted_forest' in CATEGORICAL_FEATURES and args.aux_planted_weight > 0:
    if model.use_xiao_branch:
        # Use plantation_score from xiao branch
        planted_label = (x_land[:, 0] == 2).float().unsqueeze(1)
        loss = loss + args.aux_planted_weight * aux_planted_loss(
            model._plantation_score, planted_label)
    else:
        # Original behavior
        # ... (existing code)
```

### 3.4 Decouple Land State Class Computation

**File**: `orchestrator/v3_point_inference.py`, lines 188-202

Replace the hardcoded `if xiao == 2` rule:

```python
def compute_land_state(feat: dict, ae_temporal_flat, mode: str, year: int) -> np.ndarray:
    if mode == "zero":
        return np.zeros(5, dtype=np.float32)

    # NEW: Decouple land_state_class from xiao
    treecover = float(feat.get("treecover2000", 0.0) or 0.0)
    lossyear = float(feat.get("lossyear", 0.0) or 0.0)
    fire = float(feat.get("fire_frequency_count", 0.0) or 0.0)

    # Compute class based on continuous features only
    if treecover >= 20.0:
        land_state_class = 1.0  # Natural forest or unknown
    else:
        land_state_class = 0.0  # Non-forest

    # NOTE: Xiao can still be used in a separate pathway or auxiliary head
    # but doesn't hardcode land_state_class anymore

    disturbance_intensity = min(1.0, fire / 5.0 + (0.5 if lossyear > 0 else 0.0))

    # ... rest unchanged ...
```

### 3.5 Benchmark Phase 3

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.1508 --lon 175.0997 \
  --model-dir ~/model_v16_separate_branch \
  --artifact-version v16_separate_branch \
  --top-k 20

# Expected: Rank #5-15 (better than curriculum alone)
```

---

## Phase 4: Validation & Rollout (Weeks 3-4)

### 4.1 Comprehensive Benchmarking

Create `orchestrator/benchmark_xiao_fix.py`:

```python
#!/usr/bin/env python3
"""Benchmark SINR versions on plantation detection."""

import json
import subprocess
from pathlib import Path

BENCHMARKS = [
    # (lat, lon, expected_species, description)
    (-41.1508, 175.0997, "GymPiPiPnCx50820-00", "NZ Radiata Plantation"),
    (37.8044, -122.2712, "GymPiPiPnCx50825-00", "California Pine Plantation"),
    (-27.5898, 151.9507, "GymPiPiPnCx50824-00", "Australia Plantation"),
    (-3.12, -60.02, "GymPiPiPnCx50001-00", "Amazon - No Plantation"),
]

MODELS = [
    ("v14", "~/model_local_5m", None),
    ("v15_failed", "~/model_v15", None),
    ("v16_curriculum", "~/model_v16_curriculum", "v16_curriculum"),
    ("v16_separate", "~/model_v16_separate_branch", "v16_separate_branch"),
]

results = {}

for model_name, model_dir, version in MODELS:
    results[model_name] = []
    for lat, lon, taxon, desc in BENCHMARKS:
        cmd = [
            "python3", "orchestrator/v3_point_inference.py",
            "--lat", str(lat),
            "--lon", str(lon),
            "--model-dir", model_dir,
            "--target-taxon", taxon,
            "--top-k", "20"
        ]
        if version:
            cmd.extend(["--artifact-version", version])

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
            # Parse rank from output
            for line in output.split('\n'):
                if "Rank:" in line and taxon in line:
                    rank = int(line.split("Rank: #")[1].split()[0])
                    results[model_name].append((desc, rank))
                    break
        except:
            results[model_name].append((desc, None))

# Print results table
print("\n=== SINR Xiao Fix Benchmark Results ===\n")
print(f"{'Location':<40}", end="")
for model_name, _, _ in MODELS:
    print(f"{model_name:<15}", end="")
print()

for i, (lat, lon, taxon, desc) in enumerate(BENCHMARKS):
    print(f"{desc:<40}", end="")
    for model_name, _, _ in MODELS:
        if i < len(results[model_name]):
            _, rank = results[model_name][i]
            if rank:
                print(f"Rank #{rank:<13}", end="")
            else:
                print(f"{'ERROR':<15}", end="")
        else:
            print(f"{'':<15}", end="")
    print()

# Save JSON
with open("benchmark_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nDetailed results saved to benchmark_results.json")
```

### 4.2 Run Comprehensive Benchmarks

```bash
cd orchestrator
python3 benchmark_xiao_fix.py
```

### 4.3 Acceptance Criteria

✓ **Pass** if:
- NZ plantation (expected): Rank #1-15
- California plantation (expected): Rank #1-20
- Australia plantation (expected): Rank #1-15
- Amazon (expected): Top 10-20 (any Amazon native species)
- No catastrophic regression on non-plantation locations

### 4.4 Decision Tree

```
Does v16_curriculum pass benchmarks?
  ├─ YES
  │  ├─ Rank #5-15 on plantations?
  │  │  ├─ YES: Deploy v16_curriculum, plan Phase 3 for v17
  │  │  └─ NO: Implement Phase 3 now
  │  └─ Training smooth and stable?
  │     └─ YES: Safe to merge
  └─ NO: Diagnose issues
     ├─ Curriculum learning rate?
     ├─ Curriculum schedule?
     ├─ Data quality?
     └─ Architecture incompatibility (escalate to Phase 3)
```

---

## Phase 5: Deployment & Monitoring (Week 4)

### 5.1 Update Production Inference Code

```bash
# Once v16 passes benchmarks
cp orchestrator/v3_point_inference.py orchestrator/v3_point_inference_v14.py
cp orchestrator/v3_point_inference_v16.py orchestrator/v3_point_inference.py

# Update location_predictor_FIXED.py to use v16 model
```

### 5.2 Monitor Performance

Add instrumentation:

```python
# In location_predictor_FIXED.py, after inference
import logging

logger = logging.getLogger("sinr_monitor")
handler = logging.FileHandler("sinr_inference.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Log inference details
logger.info(f"Inference at ({lat}, {lon}): top_3={top_3_species}, xiao={xiao}, land_state_class={lsc}")
```

### 5.3 A/B Testing (Optional)

If deploying to production UI:

```javascript
// In frontend (next request handler)
const modelVersion = Math.random() < 0.5 ? 'v14' : 'v16';
const response = await fetch(`/predict?model=${modelVersion}&lat=...&lon=...`);

// Log which version was used
analytics.log('prediction_model', { version: modelVersion, rank: result.rank });
```

---

## Timeline & Resource Estimate

| Phase | Tasks | Duration | Person | Effort |
|---|---|---|---|---|
| **1. Validation** | Debug instrumentation | 3 days | 1 eng | 24h |
| **2. Curriculum** | Impl + training + benchmark | 7 days | 1 eng | 56h |
| **3. Separate Branch** | Architecture + training | 14 days | 1 eng | 112h |
| **4. Validation** | Benchmark + decision | 7 days | 1 eng | 56h |
| **5. Deployment** | Updates + monitoring | 5 days | 1 eng + DevOps | 40h |

**Total**: ~4-5 weeks, ~290 person-hours (1 FTE)

**Concurrent Path**: Deploy v14 (working) while building v16 in parallel. No blocking.

---

## Debugging Checklist

If things go wrong:

- [ ] Is training loss decreasing smoothly?
- [ ] Are all categorical indices being activated?
- [ ] Is validation top-10 accuracy improving?
- [ ] Are auxiliary heads producing reasonable signals?
- [ ] Is the feature distribution matching expectations?
- [ ] Have you checked for NaNs in gradients?
- [ ] Is the learning rate schedule appropriate?
- [ ] Are you using the correct normalization stats?
- [ ] Is batch size large enough for stable training?
- [ ] Have you validated feature engineering in isolation?

---

## Success Metrics

**v16 Achievement**:
- Xiao feature correctly integrated (not always 0)
- NZ plantation Pinus radiata ranks #5-15
- Other benchmarks show no regression
- Model produces reasonable landed vs. natural predictions
- Training converges smoothly
- Auxiliary losses are well-calibrated

**Nice to Haves**:
- Top-10 accuracy > 40% on validation set
- Aux_planted_head outputs correlate with ground truth plantation labels
- Feature ablation shows xiao contributes positively to performance

---

## References

- Main forensic analysis: `XIAO_REGRESSION_FORENSIC_ANALYSIS.md`
- Code locations: `XIAO_REGRESSION_CODE_REFERENCE.md`
- Training script: `orchestrator/train_on_vm.py`
- Inference script: `orchestrator/v3_point_inference.py`
- Model definition: `orchestrator/train_on_vm.py` (ResidualFCNet class)
