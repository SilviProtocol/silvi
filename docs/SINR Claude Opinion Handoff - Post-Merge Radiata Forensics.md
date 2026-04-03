# SINR Claude Opinion Handoff - Post-Merge Radiata Forensics

Date: 2026-03-19
Audience: Claude or any successor agent asked to give an independent opinion on the current radiata failure
Status: active second-opinion handoff

## Read This First

Read these before forming an opinion:

1. `docs/SINR Current Program State.md`
2. `.claude/project-management/GO.md`
3. `docs/SINR V4.1 Data Confidence Matrix.md`
4. `docs/SINR GEDI Probe Findings 2026-03-18.md`

Use older SINR handoffs only as historical reference.

## The Core Situation

The first backfill-inclusive no-GEDI merged `V4` run is complete.

Canonical current merged training lineage:

- `species_data.sinr_v47_backfill_strict_core_v1`
- `species_data.sinr_v47_merged_strict_core_train_v2`

Canonical current merged model:

- `~/model_v47_merged_anfull`

Canonical benchmark:

- `lat=-41.151583464812404`
- `lon=175.09968969862783`
- `year=2023`
- `target=GymPiPiPnCx50820-00` (`Pinus radiata`)

Merged run result:

- recipe-faithful replay: `rank #74 / 45,096`, `prob≈0.900`
- older boosted convention: `rank #56 / 45,096`

This is disappointing because radiata support was largely restored:

- `V4.1` radiata rows: `706`
- merged `V4.7` radiata rows: about `9,090`
- merged local support within `25km`: `37`

So the strong version of the “missing data is the main problem” hypothesis is now falsified.

## What We Need Your Opinion On

The live question is no longer “should we merge backfill?”

The live question is:

**Why does radiata still rank badly after the merge, and what should we test next?**

We want a hard-nosed opinion on the most likely root causes and the smallest falsifying experiments.

## What Seems Proven Now

### 1. The merged no-GEDI table is not broadly broken

Current evidence says:

- no unexplained join holes
- no duplicate training keys
- radiata restoration is real
- remaining non-GEDI branch mismatches are narrow and targeted, not broad-estate corruption

Current narrow suspects:

- `modis_gpp_mean` `NULL` vs `0` branch drift
- pre-2015 `Dynamic World` / `ESA` proxy mismatches
- smaller `xiao_planted_forest` branch mismatches
- tiny `modis_lc_at_obs = -1` residue

### 2. Data scope restoration helped only modestly

- the merged run improved the radiata benchmark only a little
- that is enough to reject “more radiata rows alone will rescue the benchmark”

### 3. Location encoding is not the sole villain

- pre-backfill no-location ablation was effectively neutral

### 4. GEDI is a separate problem, not the current blocker

- current canonical merged run excludes GEDI
- GEDI probe showed current raw GEDI in both branches is contaminated by historical collection-mosaic misuse
- GEDI repair is happening in parallel as a coord-grain sidecar lookup

## The Most Important New Clue

Historical claims about the best legacy `v3` models are not currently reproducing cleanly under the present inference path.

Recent reruns using the current `v3_point_inference.py` path and canonical flags produced:

- `~/model_local_contract_v14_location_5m` (historically documented as `#2`) -> current replay around `#54-55`
- `~/model_local_contract_v4_gatefix_5m` (historically documented as `#12` with zero land-state) -> current replay around `#4`

This means we now have a major parity problem:

- either the historical benchmark story is not reproducible,
- or the live inference/sampling path has drifted enough that we are no longer benchmarking old artifacts in a fair apples-to-apples way.

This is one of the strongest current clues in the entire repo.

## What Older Runs Appeared To Have That Helped

From the historical docs, configs, and artifact review:

### Likely real clues

1. **Aux heads matter**
   - `v11` without aux heads collapsed to `#106`
   - suggests aux heads are load-bearing regularizers, not optional decoration

2. **Location encoding can help when the rest of the contract is coherent**
   - historical `v14` was the best documented run
   - current post-merge evidence still suggests location acts as a multiplier rather than a universal harm

3. **True/background negative supervision is still under-tested in the merged line**
   - `v2.2` had background loss
   - `v12` held rank well with `bg_weight=1.0`
   - merged `V4` still has not run a proper merged background-negative experiment

4. **Train/serve coherence mattered in older lines**
   - zeroing land state at inference helped old `v3`
   - several old wins may have depended on tighter train/serve consistency than we currently have

### Things that might have looked helpful for the wrong reasons

1. **Legacy mixed-trust data / stale inference shortcuts**
   - old `v2/v3` lines used older contracts and looser trust boundaries

2. **Single-benchmark variance / seed stories**
   - some strong historical claims (e.g. `v8 #2`) were later judged seed variance or no-op changes

3. **Historical benchmark claims that are not replaying now**
   - the `v14 #2` and `v4 #12` story is not currently stable under present inference replay

## Concrete Questions For Claude

Please give an opinion on these, in order:

1. **How much of the current failure do you think is still data vs head/ranking vs inference-parity?**
2. **How seriously should we take the new legacy-rerun contradiction (`v14 #54`, `v4 #4`)?**
3. **What are the top 3 smallest next experiments you would run now that the merge did not fix radiata?**
4. **Do you think true background negatives are now the highest-value next experiment?**
5. **Do you think retrieval/head diagnosis should come before or after the background-negative experiment?**
6. **What old `v2/v3` clues are worth reviving, and which should be treated as legacy artifacts we should not trust?**
7. **Would you treat this as mainly a plantation-supervision problem, a representation problem, a ranking-head problem, or an inference mismatch problem?**

## Recommended Reference Files

Current state:

- `docs/SINR Current Program State.md`
- `.claude/project-management/GO.md`

GEDI / confidence:

- `docs/SINR GEDI Probe Findings 2026-03-18.md`
- `docs/SINR V4.1 Data Confidence Matrix.md`

Historical clues:

- `docs/SINR_V3_EXPERIMENT_HISTORY.md`
- `docs/SINR v3 Master Recovery Plan.md`
- `docs/SINR Forensic Program History + Master Dataset Plan.md`
- `docs/SINR V4.2 Comparison Analysis.md`
- `docs/march 16/report claude.md`

Artifact/config anchors:

- `~/model_local_contract_v14_location_5m/model_config_v3.json`
- `~/model_local_contract_v4_gatefix_5m/model_config_v3.json`
- `~/model_v47_merged_anfull/model_config_v3.json`

## Bottom Line

The project no longer needs another opinion saying “you probably need more radiata data.”

That has already been tested.

What we need now is a sharp opinion on why the merged run still fails and what the smallest falsifying next experiments should be.
