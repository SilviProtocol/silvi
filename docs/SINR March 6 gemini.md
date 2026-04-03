# SINR v3 Forensic Handoff (Gemini)

Date: 2026-03-07
Owner: External audit synthesis for main implementation agent
Scope: Radiata benchmark recovery with strict train/serve parity and experiment hygiene

## Executive Reality Check

- Trusted control is `v4_gatefix_5m` at roughly `#16 / 45,247` for `GymPiPiPnCx50820-00` at `(-41.151583464812404, 175.09968969862783)`.
- Attempts after control regressed (`#23`, `#152`, `#744`, `#919`, `#256`) and did **not** beat control.
- The two strongest failure signals are:
  - **Objective coupling / negative transfer** from auxiliary heads.
  - **Dead introduced conditioning path** (`is_introduced` has no effect on rank at inference).

## Verified Evidence in Code / Runs

1. **Auxiliary objective can poison shared trunk**
   - `orchestrator/train_on_vm.py:1055` onward applies planted aux loss on shared representation.
   - Planted proxy currently built from categorical mapping state (`xiao_planted_forest`) and has shown unstable semantics across experiments.
   - Multiple planted-label variants were regressive in smoke runs; these do not conclusively validate semantics due to limited shard scope.

2. **Introduced scalar appears washed out**
   - Inference toggles of `is_introduced` (`0.0`, `0.5`, `1.0`) can yield identical target rank for regressed models.
   - This strongly suggests conditioning is not effectively routing trunk features.

3. **AN-Full path underperformed control**
   - `v5` AN-Full full run regressed versus trusted BCE-based control.
   - `v6` AN-Full sign-adjust smoke remained poor.
   - Conclusion: do not prioritize further AN-Full tuning before isolating objective coupling and conditioning behavior.

4. **Train/serve parity lessons are real and high-impact**
   - Xiao decode parity correction changed apparent performance from `#5` to trusted `#16`.
   - Prior improvements were partly artifact from parity drift, so experiment discipline is non-negotiable.

## Most Likely Root Causes (Ranked)

1. **Negative transfer from auxiliary heads into the species trunk**
   - Shared trunk receives gradients from planted/land-state tasks that are not fully aligned with main species objective.
   - If aux labels are noisy, sparse, or semantically drifted, the trunk is trained away from fine-grained species discrimination.

2. **Conditioning path ineffectiveness (`is_introduced`)**
   - Scalar conditioning likely too weak relative to high-dimensional fused features.
   - Result: introduced prior has little to no effect on logits for confuser-heavy taxa.

3. **Confuser dominance from long-tail imbalance remains unresolved**
   - Flat/global weighting strategies can still favor frequent `Pinus` confusers over `P. radiata` at this benchmark.

4. **Experiment signal contamination from smoke-only conclusions**
   - `s0` smoke runs are useful for crash checks, not for ranking verdicts in a 45k-label task.

## Next Experiments (Single Variable Only, in Order)

### Experiment 1 (Highest signal, lowest risk)
- Change only: set `--aux-planted-weight 0.0 --aux-land-state-weight 0.0`.
- Keep all else equal to trusted control (`v4` settings: include `--disable-intro-in-gate --zero-phylo-input`).
- Run full local 5-shard cycle (not s0 smoke).
- Hypothesis isolated: shared-trunk negative transfer from aux objectives is suppressing species discrimination.
- Expected directional impact: **improve or hold near control** if aux poisoning is real.
- Stop condition: if rank worsens by >50 positions from control, revert and proceed to Experiment 2.

### Experiment 2
- Change only: re-enable aux weights to control values; modify introduced path behavior with existing safe flag path (`--enable-intro-residual`) while keeping gate disabled as in control.
- Keep loss mode as BCE (control-compatible).
- Run full local 5-shard cycle.
- Hypothesis isolated: introduced conditioning can recover separation when routed through a dedicated residual path.
- Expected directional impact: **small to moderate improvement** if scalar washout was the bottleneck.
- Stop condition: if `is_introduced` sweeps at inference still produce near-identical rank/probability for target, classify conditioning as ineffective and revert.

### Experiment 3
- Change only: keep control architecture; enable species-frequency contract weighting (no AN-Full).
- Keep all control flags constant.
- Run full local 5-shard cycle.
- Hypothesis isolated: long-tail frequency pressure from confusers is overwhelming target species.
- Expected directional impact: **moderate improvement** in confuser-heavy locations.
- Stop condition: if broad top-k quality degrades and benchmark does not improve beyond control, roll back.

## What Not To Do Right Now

- Do not stack multiple architectural/loss/pipeline changes in one run.
- Do not use `s0` smoke ranking as a go/no-go for model quality.
- Do not do further AN-Full redesign before resolving objective coupling and introduced-conditioning effectiveness.
- Do not make destructive BQ/GEE changes; keep strict extractor continuity and append/resume behavior.

## Reproducibility and Hygiene Rules (Mandatory)

- Every run must have:
  - unique artifact version,
  - explicit log path,
  - full command recorded,
  - mapping/feature/frequency/intro contracts pinned where applicable,
  - benchmark inference recorded at the target coordinate.
- Compare only against trusted baseline configuration and parity-aligned inference path.

## Copy/Paste Prompt for Main Agent

Use this exact prompt for the main implementation agent:

```text
You are executing SINR v3 recovery work under strict experiment hygiene.

Primary benchmark:
- lat: -41.151583464812404
- lon: 175.09968969862783
- year: 2023
- target taxon: GymPiPiPnCx50820-00

Trusted control:
- v4_gatefix_5m behavior with Xiao parity-aligned inference
- expected reference rank: ~#16 / 45,247

Hard constraints:
1) Single-variable experiments only.
2) No train/serve drift.
3) No destructive BQ/GEE operations.
4) Preserve versioned artifacts and reproducibility.
5) No broad rewrites.

Execute exactly one run now:

Experiment 1 (objective coupling isolation):
- Keep control settings fixed.
- Set only:
  --aux-planted-weight 0.0
  --aux-land-state-weight 0.0
- Keep:
  --disable-intro-in-gate
  --zero-phylo-input
  loss mode = BCE (control-compatible)
- Run full local 5-shard training (not s0 smoke).

After training:
1) Run parity-aligned point inference at benchmark for introduced sweeps (0.0/0.5/1.0).
2) Report target rank/probability and top confusers.
3) Compare only vs trusted #16 baseline.
4) Record full command, artifact version, and log path.

Decision gate:
- If improved (<#16), lock result and propose next single-variable run from the handoff doc.
- If not improved, revert to control and run Experiment 2 from handoff doc.

Output format:
- concise run summary
- benchmark table (mode, rank, prob)
- diff vs baseline
- next action recommendation (one variable only)
```

## Notes for Reviewer

- This handoff intentionally avoids code rewrite proposals.
- It prioritizes maximum information gain per run under strict parity controls.
- It is designed to stop the cycle of ambiguous regressions and recover forward momentum.
