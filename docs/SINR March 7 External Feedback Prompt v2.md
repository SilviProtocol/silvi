# SINR March 7 External Feedback Prompt v2

Use this prompt with Claude/Gemini/other external auditors.

```text
You are auditing SINR v3 benchmark regressions for tree-species ranking.

Please produce a skeptical, implementation-level review and ranked plan.

## Goal

Improve rank for `GymPiPiPnCx50820-00` at:
- lat: `-41.151583464812404`
- lon: `175.09968969862783`
- year: `2023`

Current trusted control baseline is v4 gate-fix + Xiao parity at `#16 / 45,247`.

## Hard constraints

1. Single-variable experiments only.
2. No train/serve drift.
3. No destructive data-pipeline actions.
4. Versioned/reproducible artifacts only.

## Confirmed evidence

1) Best trusted baseline:
- `v4_gatefix_5m` -> `#16`.

2) Regressions:
- `v5_anfull_5m` -> `#23`.
- planted label mode smokes: `strict_planted3 -> #919`, `land_state2 -> #256`.

3) Point inference strict contract still fails currently:
- missing env fields: `aridity_index`, `et0_mm_yr`
- missing categorical: `ipcc_forest_class`
- strict run throws: `env_missing=2, cat_missing=1`.

4) Land-state inference sensitivity on fixed checkpoints:
- v4: heuristic `#16` vs zero `#12`
- v5: heuristic `#23` vs zero `#19`

5) Introduced invariance is expected under current flags:
- with `--disable-intro-in-gate` and no intro residual, introduced slices can be identical.

6) AN-Full parity concern:
- v2.2 and v3 AN correction-term implementations differ in sign/definition.

## Files to inspect

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/train_sinr_model.py`
- `orchestrator/land_state_engine.py`
- `docs/SINR March 7 Deep Root Cause + Action Plan.md`
- `docs/SINR March 7 Comprehensive State + Audit Request Packet.md`

## Questions to answer

1. Rank top root causes (with file/function-level evidence).
2. Confirm whether inference parity gaps alone could explain much of the residual error.
3. Evaluate AN-Full implementation correctness versus intended v2.2 math.
4. Recommend top 3 next single-variable experiments with expected direction and risk.
5. Explicitly list what to avoid next.

## Required output format

1) Most likely causes (ranked bullets)
2) Next experiments in strict order (numbered)
3) Patch scope per experiment (file + function)
4) Verification command per experiment
5) Decision gate after next two runs (if A then B else C)

Be concrete, low-risk first, and do not propose stacked changes.
```
