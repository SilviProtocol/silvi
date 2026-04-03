# SINR P1-P2-D1-T1 Runbook

Date: 2026-03-19
Audience: operators executing the first post-merge radiata forensic cycle
Status: active runbook

## Purpose

This runbook gives the exact first execution cycle for the post-merge rank-1
program:

- `P1` benchmark the current merged baseline and nearby local suite
- `P2` audit historical artifact parity vs current replay behavior
- `D1` validate the remaining narrow non-GEDI data questions
- `T1` run the first merged BCE baseline after parity/data gates are satisfied

This runbook assumes the active canonical state in:

- `docs/SINR Current Program State.md`
- `docs/SINR Radiata Rank-1 Program.md`

## Benchmark Suite

Target taxon:

- `GymPiPiPnCx50820-00`

Canonical point:

- `-41.151583464812404, 175.09968969862783, 2023`

Nearby local suite:

- `-41.15417025743087, 175.09915476475814, 2023`
- `-41.15504998747567, 175.1065715571766, 2023`
- `-41.15927635199013, 175.09953576436868, 2023`
- `-41.18626808111574, 175.0509971829668, 2023`

## Output Convention

For every benchmarked model, record at minimum:

- model id
- command used
- canonical rank / prob
- nearby suite ranks / probs
- median local-suite rank
- worst local-suite rank
- notes on top species above radiata

Recommended report destination:

- append or create a dated report under `docs/`
- update the corresponding bead notes

## P1 - Benchmark The Current Merged Baseline

### `P1A` Merged V4.7/V4.9 baseline replay

Use the current accepted recipe-faithful merged inference flags:

- `--land-state-mode zero`
- `--use-location-encoding`
- `--disable-intro-in-gate`
- `--no-boost`

Command template:

```bash
python3 orchestrator/v3_point_inference.py \
  --lat <LAT> --lon <LON> --year 2023 \
  --model-dir "/Users/djimoserodio/model_v47_merged_anfull" \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json \
  --mapping-contract orchestrator/contracts/sinr_v3/species_mapping_v47_merged.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v47_merged.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v47_merged.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all \
  --top-k 20 \
  --land-state-mode zero \
  --disable-intro-in-gate \
  --use-location-encoding \
  --no-boost
```

Run it once for the canonical point and once for each nearby point.

### `P1B` Historical V4.x comparison replays

Use the same suite on these artifacts:

- `~/model_v41_preview`
- `~/model_v42_anfull_hardcap_full`
- `~/model_v43a_nolocation`

Working replay conventions for now:

- `V4.1`: `--land-state-mode zero --use-location-encoding`
- `V4.2`: `--land-state-mode zero --use-location-encoding --disable-intro-in-gate --no-boost`
- `V4.3a`: `--land-state-mode zero --disable-intro-in-gate --no-boost`

Use these contracts:

- feature contract: `orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json`
- `V4.1` mapping/intro: `species_mapping_v41_preview_train.json`, `intro_ratio_contract_v41_preview_train.json`
- `V4.2/V4.3a`: use the model-dir artifacts by default, and if needed validate against the saved local files in those model dirs

Important:

- these historical flags are still part of the parity audit, not final truth
- if a replay looks surprising, treat that as evidence for `P2`, not as a final benchmark conclusion

## P2 - Historical Artifact Parity Audit

Goal:

- explain why old documented ranks and current replays disagree

Core questions:

1. Are the historical docs replaying with the exact same flags?
2. Has `location_predictor_FIXED.py` drifted enough to change old-model behavior?
3. Which categorical / feature semantics changed after the old runs?
4. Which historical wins depended on old harness assumptions rather than durable model quality?

Required checks:

### `P2A` Artifact reconstruction

For each old artifact (`v4_gatefix_5m`, `v14_location_5m` at minimum):

- inspect `model_config_v3.json`
- inspect `artifact_manifest*.json`
- inspect `training_log.json`
- search historical docs for the exact claimed command / flags

### `P2B` Current replay table

Build a table with columns:

- artifact
- historically documented rank
- current replay rank
- current replay flags
- likely mismatch source

### `P2C` Sampler drift checklist

Check whether these changed relative to the historical period:

- Xiao decode
- GPP handling
- land-state inference path
- feature presence / missingness
- introduced / boost behavior
- any categorical remap that affects live sampling

Success condition:

- no more ambiguous historical benchmark claims remain in the active docs

## D1 - Narrow Non-GEDI Data Validation

This is not a full data-estate re-audit.

Validate only the still-suspect non-GEDI families:

1. `modis_gpp_mean` `NULL` vs `0` branch drift
2. pre-2015 `Dynamic World` / `ESA` proxy mismatches
3. `xiao_planted_forest` branch mismatches
4. `modis_lc_at_obs = -1` residue

Recommended sample sizes:

- `300-500` GPP mismatch rows
- `300` DW/ESA rows
- `200` Xiao mismatch rows
- full census of the `modis_lc_at_obs = -1` residue

Recommended outputs:

- % validated as expected / policy-correct
- % surprising
- whether the issue is narrow enough to stop blaming merged data broadly

Decision gate:

- if these remain narrow, close the broad “merged data is bad” theory

### `D1` Actual 2026-03-19 outcome

`D1` is now complete, and the result is:

- the merged no-GEDI estate is not broadly broken,
- but three real repair targets were confirmed:
  1. backfill post-2000 `modis_gpp_mean = 0` is mostly fake missingness,
  2. backfill `xiao_planted_forest` has real semantic drift,
  3. new_gbif pre-2015 `dynamic_world` has a stale proxy/remap subset.

See:

- `docs/SINR D1 Validation Findings 2026-03-19.md`

### New gate after D1

Before `T1`, run a narrow non-GEDI repair pass and rerun the current merged recipe
unchanged once. That isolates the data-repair effect before changing the loss.

## T1 - First Merged BCE Baseline

Run only after `P1/P2`, `D1`, and the narrow non-GEDI repair/rerun are documented.

Hypothesis:

- old strong runs were BCE-based, and current `an_full` may not be the best radiata-ranking objective on the merged path

Single changed knob:

- `loss_mode: an_full -> bce`

Keep fixed:

- merged no-GEDI data
- location encoding on
- `no_boost`
- `disable_intro_in_gate`
- same shard cadence
- same contracts / normalization / mapping

Training command template:

```bash
nohup caffeinate -s python3 orchestrator/run_local_5m_shard_training.py \
  --local-data-root ~/data_v47_merged_train_shards \
  --table-prefix dummy \
  --model-dir ~/model_v47_merged_bce \
  --num-shards 20 --start-shard 0 --end-shard 19 \
  --skip-export \
  --mapping-contract orchestrator/contracts/sinr_v3/species_mapping_v47_merged.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v47_merged.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v47_merged.npz \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v47_merged.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v47_merged.json \
  --loss-mode bce \
  --disable-boost-in-training --no-boost \
  --use-location-encoding \
  --zero-phylo-input \
  --disable-intro-in-gate \
  --batch-size 1536 \
  --epochs-per-shard 1 \
  --cycles 2 \
  > orchestrator/v47_bce_training_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

Benchmark it against:

- canonical point
- nearby local suite

Decision rule:

- if BCE improves both canonical and local-suite behavior, it becomes the new base for `T2`
- if BCE helps only the canonical point and hurts the suite, treat it as overfitting noise

## What Not To Do In This First Cycle

- do not add GEDI yet
- do not combine BCE + background negatives + plantation supervision all at once
- do not reopen broad “maybe the merged table is bad” arguments before `D1`
- do not trust old `#2`/`#12` claims until `P2` is closed

## Bottom Line

The first post-merge cycle is:

1. benchmark honestly
2. resolve historical parity contradictions
3. validate only the remaining narrow data suspects
4. change one training knob (`BCE`) and test it on the canonical point plus the nearby plantation suite

That gives the cleanest possible starting point for the next steps.
