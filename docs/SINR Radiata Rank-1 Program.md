# SINR Radiata Rank-1 Program

Date: 2026-03-19
Audience: active SINR V4 operators
Status: active experiment program

## Goal

Chase `rank #1` for the canonical radiata benchmark without relaxing the strict-data program.

Canonical benchmark:

- `lat=-41.151583464812404`
- `lon=175.09968969862783`
- `year=2023`
- `target=GymPiPiPnCx50820-00`

Initial nearby radiata plantation suite (`year=2023`, same target):

- `lat=-41.15417025743087`, `lon=175.09915476475814`
- `lat=-41.15504998747567`, `lon=175.1065715571766`
- `lat=-41.15927635199013`, `lon=175.09953576436868`
- `lat=-41.18626808111574`, `lon=175.0509971829668`

Use the canonical point as the headline benchmark, but treat this nearby suite as
the first local anti-overfitting benchmark set for all parity and post-parity runs.

Current merged baseline:

- model: `~/model_v47_merged_anfull`
- table: `species_data.sinr_v47_merged_strict_core_train_v2`
- recipe-faithful result: about `#74 / 45,096`

## Non-Negotiable Rules

1. One primary change per experiment.
2. Use artifact-faithful benchmark flags.
3. Keep the benchmark harness fixed within each phase.
4. Log every run with exact config, exact changed knob, and exact result.
5. Do not treat GEDI as a blocker for the no-GEDI forensic line.
6. Do not assume more data is the main missing piece.

## Current Read

What is already settled:

- merged no-GEDI data is trainable and not broadly corrupt
- radiata support was restored, but rank improved only modestly
- location encoding alone is not the main problem
- introduced conditioning is still effectively inert
- older `v2/v3` benchmark stories are not replaying cleanly under the current inference path

So the next program has to separate:

- benchmark / inference parity problems,
- narrow data-integrity questions,
- training objective / supervision problems,
- and representation-vs-head problems.

The storage-retirement milestones below are subordinate to those actual
investigations. They are not generic cleanup gates.

## Versioning Scheme

Use explicit phase prefixes.

- `P*` = parity / benchmark-harness only, no training change
- `D*` = data-validation only, no model change
- `T*` = training recipe experiments, one primary knob at a time
- `R*` = retrieval / head diagnosis, inference-side analysis or reranking
- `G*` = GEDI sidecar / GEDI-inclusive work

Each entry should have:

- `version_id`
- `hypothesis`
- `single changed knob`
- `frozen base`
- `benchmark results`
- `decision`

Recommended naming examples:

- `P1` parity-faithful merged baseline replay
- `P2` old-artifact parity audit
- `D1` merged non-GEDI validation sample
- `T1` merged BCE baseline
- `T2` merged true-background-negative run
- `T3` merged plantation-aware supervision run
- `R1` merged retrieval / hidden-state diagnosis
- `G1` GEDI lookup QC

## Active Issue Map

- `treekipedia-v7x` - rank-1 program umbrella
- `treekipedia-ts1` - post-merge radiata forensic and benchmark-parity audit
- `treekipedia-ahp` - completed targeted non-GEDI merged-data validation sampling
- `treekipedia-jo1` - narrow non-GEDI branch-semantic repair implemented; unchanged-rerun pending
- `treekipedia-jt3` - merged background-negative and plantation-aware experiment
- `treekipedia-2x6` - merged retrieval / head-diagnosis probes
- `treekipedia-c5q` - GEDI semantics / reintroduction policy
- `treekipedia-1i5` - GEDI lookup extraction

Storage-retirement milestones tied to program progress:

- `treekipedia-7by` - completed zero-regret delete pass (~687 GB freed)
- `treekipedia-a12` - phase-2 storage retirement after parity and validation
- `treekipedia-7za` - phase-3 legacy SINR retirement after v2/v3 forensic closeout
- `treekipedia-rn8` - phase-4 strict-stack consolidation after merged canonization

## Storage Retirement Milestones

Current SINR/species_data storage after the zero-regret delete pass:

- about `1,567.36 GB`

The storage plan is now part of the rank-1 program, not a separate cleanup thread.

### `M0` - Completed zero-regret delete pass

Status:

- complete under `treekipedia-7by`

What was deleted:

- exact duplicates / accidental superseded outputs
- superseded new_gbif intermediate lineage tables
- repeated release snapshots
- repeated allowlist snapshots
- GEDI smoke table

Savings already realized:

- about `687 GB`

### `M1` - After `P1/P2` and `D1`

Gate:

- benchmark parity completed
- targeted non-GEDI validation completed

Meaning:

- the concrete parity and data-integrity questions that still justify keeping
  extra replay/export artifacts are closed

Eligible delete bucket:

- latest release snapshots / allowlists if parity says they are no longer needed
- BQ export artifacts / shard tables if local copies are sufficient

Rough additional savings available:

- release snapshots / allowlists: about `109 GB`
- BQ export artifacts: about `62 GB`
- combined: about `171 GB`

Tracked by:

- `treekipedia-a12`

### `M2` - After old-artifact forensic closeout

Gate:

- `v2/v3` parity work is complete
- no remaining need to reproduce against legacy raw/assembled tables in active forensics

Meaning:

- the old-line forensic story is closed enough that legacy `v1/v2/raw` tables are no
  longer buying us meaningful diagnostic leverage

Eligible delete bucket:

- `sinr_v3_unified_v1`
- `sinr_v3_unified_v2`
- legacy raw `new_gbif` / `backfill`
- legacy introduced / aux tables no longer needed for reproduction

Rough additional savings available:

- about `343 GB`

Tracked by:

- `treekipedia-7za`

### `M3` - After merged canonization

Gate:

- merged V4 lineage is the only canonical training provenance we still need
- strict intermediate assembly tables are no longer needed for replay

Meaning:

- the merged line has become the sole active truth layer, so overlapping strict
  assembly intermediates can finally be collapsed

Eligible delete bucket:

- `sinr_v3_unified_strict_train`
- `sinr_v3_strict_unified_hits_raw`
- `sinr_v3_strict_unified_train_core`

Rough additional savings available:

- about `350 GB`

Tracked by:

- `treekipedia-rn8`

### Bottom-line storage path

- current after `M0`: about `1.57 TB`
- after `M1`: about `1.40 TB`
- after `M2`: about `1.06 TB`
- after `M3`: about `0.71 TB`

These later milestones are conditional, not promises. The rule is simple:

- no deletion milestone advances until the corresponding forensic need is genuinely closed.
- the main purpose of the program remains improving radiata ranking for the V4 line,
  with storage cleanup happening only after those investigative needs are satisfied.

## Program Order

### Phase P - Benchmark and Inference Parity

This phase happens before any new training run.

#### `P1` - recipe-faithful merged baseline replay

Goal:

- lock the canonical merged baseline result
- confirm exact flags for `no_boost`, location, intro gate, land-state mode

Expected output:

- one benchmark table for `V4.1`, `V4.2`, `V4.3a`, `V4.7`
- old documented rank vs current replay rank vs exact flags used
- canonical-point result plus nearby-suite results

#### `P2` - legacy artifact parity audit

Goal:

- explain why historical `v14 #2` and `v4 #12` are not replaying cleanly now

Questions:

- old model + current sampler mismatch?
- stale benchmark docs?
- changed categorical semantics?
- changed land-state / boost / intro handling?

Success condition:

- no more ambiguous historical benchmark claims in active docs
- clear understanding of whether old `v2/v3` success was real model behavior,
  stale harness behavior, or legacy train/serve shortcuts

### Phase D - Narrow Data Validation

This is targeted sampling only, not a full estate re-audit.

#### `D1` - merged non-GEDI validation sample

Sample only the remaining suspect families:

- `modis_gpp_mean` `NULL` vs `0` drift
- pre-2015 `Dynamic World` / `ESA` proxy mismatches
- `xiao_planted_forest` branch mismatches
- `modis_lc_at_obs = -1` residue

Suggested sample sizes:

- `300-500` GPP rows
- `300` DW/ESA rows
- `200` Xiao mismatch rows
- full census of the `modis_lc_at_obs = -1` residue

Decision gate:

- if these look narrow and survivable, stop blaming merged data
- storage milestone `M1` does not unlock until this gate is actually closed

### Phase T - Training Experiments

Only start after `P1/P2` and `D1` are done.

Important update after `D1`:

- `D1` found three real non-GEDI repair targets
- the narrow repair pass (`treekipedia-jo1`) is now implemented
- the next practical step is one rerun of the current merged recipe unchanged
- that repair/rerun becomes the final data gate before the first true recipe-change run

#### `T1` - merged BCE baseline

Hypothesis:

- old strong runs were BCE-based, and current `an_full` may not be the best radiata-ranking objective

Precondition:

- complete the narrow non-GEDI repair pass from `treekipedia-jo1`
- rerun the current merged recipe unchanged once on the repaired lineage

Change:

- switch `loss_mode` from `an_full` to `bce`
- keep everything else fixed on merged no-GEDI data
- benchmark against both the canonical point and the nearby local plantation suite

#### `T2` - merged true background negatives

Hypothesis:

- the model is still land-use blind because it never learns that random land points should score low for almost all species

Change:

- add true background negatives on top of the merged no-GEDI baseline
- keep the rest of the best-performing merged recipe fixed
- benchmark against both the canonical point and the nearby local plantation suite

#### `T3` - plantation-aware supervision

Hypothesis:

- radiata ranking is still weak because plantation signal is not supervised cleanly enough

Change:

- add the cleanest available plantation-aware supervision on top of the best `T1/T2` recipe
- do not change multiple unrelated knobs in the same run
- benchmark against both the canonical point and the nearby local plantation suite

#### `T4` - old-clue revival, one at a time

Only after `T1-T3`.

Candidates to revive one by one:

- legacy-style two-pass inference aggregation
- carefully audited boost / prior logic
- other old mechanisms only after parity proves they were genuinely helpful

### Phase R - Representation vs Head Diagnosis

#### `R1` - merged retrieval / hidden-state analysis

Goal:

- determine whether radiata is already retrievable from the merged model even when the head ranks it poorly

Outputs:

- AE neighbor audit
- temporal neighbor audit
- hidden-state neighbor audit
- light reranking tests

Decision gate:

- if retrieval works but parametric rank fails, focus on the head / calibration
- if retrieval also fails, focus on supervision and representation

### Phase G - GEDI Sidecar Track

GEDI proceeds in parallel and does not block the no-GEDI program.

#### `G1` - finish GEDI-only lookup
- `species_data.sinr_v48_gedi_lookup_v1`

#### `G2` - GEDI QC
- duplicates = `0`
- sane canopy ranges
- explicit missingness
- `countf` QC

#### `G3` - conservative GEDI-inclusive experiment
- only after `G1/G2`
- canopy first
- no blind foliage `shan` reuse

## Success Ladder

- `target A`: get recipe-faithful merged rank into top `50`
- `target B`: get into top `20`
- `target C`: top `10`
- `target D`: top `3`
- `target E`: `#1`

The immediate program objective is not to promise `#1` in one jump.
It is to create a disciplined path that can explain every move from `#74` upward.

## What Not To Do

- do not launch more blind merged retrains without a single-knob hypothesis
- do not keep citing old `v14 #2` claims as if they are replay-faithful truth
- do not treat GEDI as the explanation for the no-GEDI merged failure
- do not widen the data estate again before the current merged line is understood

## Bottom Line

The rank-1 program is now:

1. parity first,
2. narrow data validation second,
3. one-change-at-a-time merged training experiments,
4. retrieval/head diagnosis,
5. GEDI in parallel.

That is the disciplined path forward.
