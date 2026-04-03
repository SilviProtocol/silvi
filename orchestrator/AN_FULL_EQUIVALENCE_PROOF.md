# AN-Full Loss Equivalence Proof

Date: 2026-03-16
Context: treekipedia-xz2 (V4.2 comparison)

## Claim

Our `_compute_an_full_loss` (train_on_vm.py:304-332) is mathematically equivalent
to the original SINR `an_full` (github.com/elijahcole/sinr, losses.py).

The `/ num_species` on line 326 is **correct**, not a bug.

## Original SINR Implementation

```python
# From elijahcole/sinr/losses.py
loss_pos = neg_log(1.0 - loc_pred)          # B x C matrix, all assumed-negative
loss_pos[inds, class_id] = pos_weight * neg_log(loc_pred[inds, class_id])  # overwrite target
loss = loss_pos.mean()                       # mean over ALL B*C elements
```

Per-sample loss (before averaging over batch):

```
L_i = [sum_{j != t} (-log(1 - p_j)) + pos_weight * (-log(p_t))] / C
```

where `t = target[i]`, `C = num_species`.

## Our Implementation

```python
loss_neg = -log_neg.mean(dim=1)                                    # mean over C species
correction = (t_log_neg + pos_weight * (-t_log_pos)) / num_species # correction to that mean
loss_per = loss_neg + correction
return loss_per.mean()                                             # mean over batch
```

Expanding:

```
loss_neg = sum_j(-log(1 - p_j)) / C              # includes target j

correction = (log(1 - p_t) + pos_weight * (-log(p_t))) / C

loss_per = [sum_j(-log(1 - p_j)) + log(1 - p_t) + pos_weight * (-log(p_t))] / C
         = [sum_{j != t}(-log(1 - p_j)) + (-log(1 - p_t) + log(1 - p_t)) + pos_weight * (-log(p_t))] / C
         = [sum_{j != t}(-log(1 - p_j)) + pos_weight * (-log(p_t))] / C
```

This is identical to the original SINR per-sample loss.

## Numerical Verification

```python
import torch
import torch.nn.functional as F

# Setup: 3 species, 2 samples
logits = torch.tensor([[2.0, -1.0, 0.5], [0.3, 1.5, -0.8]])
targets = torch.tensor([1, 0])
pos_weight = 2048.0

# === Original SINR style (matrix overwrite) ===
p = torch.sigmoid(logits)
neg_log = lambda x: -torch.log(x + 1e-5)
loss_matrix = neg_log(1.0 - p)
for i in range(2):
    loss_matrix[i, targets[i]] = pos_weight * neg_log(p[i, targets[i]])
loss_original = loss_matrix.mean()

# === Our implementation ===
B, C = logits.shape
log_pos = F.logsigmoid(logits)
log_neg = F.logsigmoid(-logits)
loss_neg_ours = -log_neg.mean(dim=1)
t_log_pos = log_pos.gather(1, targets.unsqueeze(1)).squeeze(1)
t_log_neg = log_neg.gather(1, targets.unsqueeze(1)).squeeze(1)
correction = (t_log_neg + pos_weight * (-t_log_pos)) / C
loss_per = loss_neg_ours + correction
loss_ours = loss_per.mean()

print(f"Original: {loss_original.item():.6f}")
print(f"Ours:     {loss_ours.item():.6f}")
print(f"Match:    {torch.allclose(loss_original, loss_ours, atol=1e-4)}")
# Note: not bitwise identical due to neg_log using +1e-5 vs logsigmoid,
# but mathematically equivalent under the same numerical scheme.
```

## Why `/ num_species` is Correct

`loss_neg` is already a **mean** over `C` species columns (divided by `C`).
The correction replaces one element of that mean: remove the target's negative
contribution and add the weighted positive contribution. Since we're modifying
a mean, the correction must also be divided by `C` to stay in the same units.

Removing `/ num_species` would make the positive term `C` times stronger than
the original SINR — i.e., 19,043x too strong — and would destabilize training.

## What IS Different From Original SINR

1. We use `F.logsigmoid` (numerically stable) vs original's `neg_log(x) = -log(x + 1e-5)`.
   These differ by ~1e-5 in extreme regions but are equivalent for practical purposes.

2. Background loss is a separate `--bg-weight` term, not folded into `an_full`.
   When `bg_weight=0` (our default), we omit the background term entirely.
   The original always includes it.

3. Background sampling: original uses random spherical coordinates;
   ours samples random training rows. Different semantics.
