# SINR Current Program State

Date: 2026-03-19
Audience: anyone resuming SINR V4 work after the first merged backfill-inclusive run
Status: active restart document

## Purpose

This is the single active restart document for the current SINR V4 program.

Use it to answer:

- what the program has already proven,
- what is now falsified,
- what the current trusted training data is,
- what the first merged run actually showed,
- and what the next work should be.

This document supersedes the older handoff docs as the operational entry point.
Older handoffs and reports are still useful as reference, but they should no
longer be treated as the live source of truth.

## Read Order

For active SINR work, read these in order:

1. `docs/SINR Current Program State.md`
2. `.claude/project-management/GO.md`
3. `docs/SINR V4.1 Data Confidence Matrix.md`
4. `docs/SINR GEDI Probe Findings 2026-03-18.md`
5. `docs/SINR Radiata Rank-1 Program.md`
6. `docs/SINR P1-P2-D1-T1 Runbook.md`

Use older handoffs only when you need historical detail or exact prior claims.

## Current Program Snapshot

- `V3` = frozen benchmark family / historical comparison family
- `V4.1` = governed `new_gbif`-only preview baseline (retired, keep for provenance)
- `V4.2 / V4.3` = pre-backfill diagnosis phase (completed, now historical)
- `V4.7` = fast-safe merged strict-core path (`new_gbif completed_v1` + repaired backfill strict-core, no GEDI)
- `V4.8` = merged artifacts / contracts / shards rebuild (completed)
- `V4.9` = first backfill-inclusive no-GEDI merged training run (completed)

Canonical current training lineage:

- `species_data.sinr_v47_backfill_strict_core_v1`
- `species_data.sinr_v47_merged_strict_core_train_v2`

Canonical current merged model:

- `~/model_v47_merged_anfull`

Current SINR/species_data storage footprint after the zero-regret delete pass:

- about `1,567.36 GB`

GEDI status:

- still excluded from the canonical merged training path
- repair work is happening separately via a GEDI-only coord-grain lookup

## Benchmark Facts

Canonical benchmark:

- `lat=-41.151583464812404`
- `lon=175.09968969862783`
- `year=2023`
- `target=GymPiPiPnCx50820-00` (`Pinus radiata`)

Initial nearby radiata plantation suite (`year=2023`, same target):

- `lat=-41.15417025743087`, `lon=175.09915476475814`
- `lat=-41.15504998747567`, `lon=175.1065715571766`
- `lat=-41.15927635199013`, `lon=175.09953576436868`
- `lat=-41.18626808111574`, `lon=175.0509971829668`

Treat the canonical point as the headline benchmark and this nearby suite as the
first local anti-overfitting benchmark set for post-merge V4 work.

Historical documented results:

| Run | Config | Result |
|---|---|---|
| `V4.1` | BCE | `#105 / 19,043`, `p=0.608283` |
| `V4.2` | `an_full + hard-cap/effective-cap + no-boost + location` | historical documented `#79 / 19,043` |
| `V4.3a` | same as `V4.2` but no location | historical documented `#78 / 19,043` |
| `V4.7/V4.9` merged | frozen merged no-GEDI recipe | recipe-faithful `#74 / 45,096`, historical boosted convention `#56 / 45,096` |

Important caveat:

- older benchmark reruns did not always honor saved artifact flags like `no_boost`
- so historical rank deltas are directionally useful, but a clean post-merge parity audit is still required

## What Is Proven

### 1. The merged no-GEDI data path is real and trainable

- `v47_merged_strict_core_train_v2` was built successfully
- merged artifacts were rebuilt
- the first merged no-GEDI run trained successfully to completion

### 2. Data scope restoration helped only modestly

- radiata support was restored from `706` rows in `V4.1` to about `9,090` matched rows in merged `V4.7`
- local support near the benchmark is also back (`37` rows within `25km`)
- but the radiata rank only improved modestly

### 3. "More radiata rows" is not the main explanation anymore

- this was the strongest working hypothesis before the merge
- the merged run did improve the rank, but not enough to explain the failure away
- data scope mattered, but it is not the decisive missing piece

### 4. The merged non-GEDI table does not look broadly corrupt

- no unexplained join holes
- no duplicate training keys
- restored radiata support is real
- remaining suspicious non-GEDI mismatches are narrow and targeted, not broad-estate failures

### 5. Location encoding is not the dominant bottleneck

- the no-location ablation was effectively neutral in the pre-backfill phase

### 6. GEDI is not blocking the current no-GEDI program

- GEDI was correctly kept out of `V4.7/V4.9`
- GEDI repair is a separate sidecar track, not a blocker for the current radiata forensic path

## What Is Falsified

### 1. "GEE nondeterminism" as the main explanation

- earlier claims of large random benchmark swings were not established

### 2. "Location prior is the main villain"

- removing location did not materially rescue radiata

### 3. "Radiata is mainly losing because it is underrepresented"

- underrepresentation was real
- after restoring most of that support, the problem still remains

### 4. "Backfill must not be merged before a full canonical re-extract"

- the fast-safe merged path was explicitly chosen and completed
- it is the current live no-GEDI training lineage

### 5. "This is just a Pinus-vs-Pinus confusion problem"

- current evidence points more toward native NZ forest taxa outranking radiata than simple within-genus confusion

## What Is Still Open

### 1. Benchmark parity / inference parity

- we still need a clean replay of benchmark results using artifact-faithful flags
- we also still need to align live inference semantics with the current strict V4 program

### 2. Plantation-specific supervision

- current evidence suggests the model still lacks a strong planted/plantation-aware ranking signal

### 3. True background negatives

- still one of the strongest remaining hypotheses
- not yet tested on the merged path

### 4. Representation vs head/ranking bottleneck

- we still need merged-model retrieval / neighbor / rerank probes to tell whether the representation already contains the needed signal

### 5. Narrow non-GEDI integrity checks are now partly resolved

`D1` is now complete:

- `modis_lc_at_obs = -1` residue is benign
- but three real branch-semantic issues were confirmed:
  - backfill post-2000 `modis_gpp_mean = 0` is mostly fake missingness
  - backfill `xiao_planted_forest` has real semantic drift
  - new_gbif pre-2015 `Dynamic World` proxy values are stale on a subset of contexts

So the broad "merged data is bad" theory remains unsupported, but a narrow non-GEDI
repair pass is now justified before the next training experiment.

That repair pass is now implemented:

- repaired branch tables:
  - `species_data.sinr_v48_new_gbif_strict_core_repaired_v1`
  - `species_data.sinr_v48_backfill_strict_core_repaired_v1`
- repaired merged table:
  - `species_data.sinr_v48_merged_strict_core_train_v1`

The next gate is now an unchanged-rerun on the repaired merged line before any
true recipe change.

## Current Best Read Of The Failure

The current failure is best understood as a post-merge forensic problem, not a simple data-gap problem.

Plain-English interpretation:

- we gave the model much more relevant radiata/backfill data,
- the rank improved only modestly,
- so the main problem is probably no longer "we just need more data",
- and is more likely some combination of benchmark/inference mismatch, weak plantation supervision, no true background negatives, and a ranking stack that still prefers nearby native forest taxa.

Most likely remaining bottlenecks:

1. weak plantation-specific supervision
2. no true background negatives
3. stale inference / benchmark parity mismatch
4. a head / fusion / ranking stack that still prefers nearby native NZ forest taxa

Least likely explanations now:

1. broad corruption of the merged no-GEDI training table
2. raw global radiata underrepresentation as the primary issue
3. location prior alone

## Active Workstreams

Primary current issues:

- `treekipedia-ts1` - post-merge radiata forensic and benchmark-parity audit
- `treekipedia-ahp` - completed targeted non-GEDI merged-data validation sampling
- `treekipedia-jo1` - narrow non-GEDI repair implemented; unchanged-rerun still pending
- `treekipedia-jt3` - merged background-negative and plantation-aware experiment
- `treekipedia-2x6` - merged retrieval / head-diagnosis probes
- `treekipedia-v7x` - umbrella rank-1 program / milestone ladder

Parallel but separate:

- `treekipedia-c5q` - verify and reintroduce GEDI for strict V4 lineage
- `treekipedia-1i5` - GEDI-only coord manifest and lookup extraction
- `treekipedia-d4q` - align live inference with repaired GEDI/Xiao semantics after repair contract freezes

Storage retirement milestones aligned to program progress:

- `treekipedia-7by` - completed zero-regret delete pass
- `treekipedia-a12` - phase-2 retirement after parity and narrow validation
- `treekipedia-7za` - phase-3 retirement after legacy forensic closeout
- `treekipedia-rn8` - phase-4 strict-stack consolidation after merged canonization

Fallback only:

- `treekipedia-rag` - full frozen canonical strict-context re-extract

## Recommended Execution Order

1. Finish `treekipedia-ts1`
   - clean benchmark parity audit
   - exact above-radiata forensic analysis
   - use the canonical point plus the nearby local radiata plantation suite
2. Run `treekipedia-jo1`
   - repair the three confirmed non-GEDI branch-semantic issues (done)
   - rerun the current merged recipe unchanged to isolate the data-repair effect (next)
3. Run `treekipedia-jt3`
   - first merged one-change-at-a-time training experiment after parity/data repair gates
   - start with BCE and then move to true background negatives / plantation-aware supervision in sequence
4. Run `treekipedia-2x6`
   - retrieval and head-diagnosis probes on the merged model

Keep GEDI work running in parallel, but do not let GEDI delay the no-GEDI forensic path.

## Canonical Active Supporting Docs

- `docs/SINR V4.1 Data Confidence Matrix.md`
- `docs/SINR GEDI Probe Findings 2026-03-18.md`
- `docs/SINR D1 Validation Findings 2026-03-19.md`
- `docs/SINR jo1 Repair Status 2026-03-19.md`

## Historical Docs To Treat As Reference Only

These are still useful, but they are no longer the live operational narrative:

- `docs/SINR Claude V4.2 Comparison Handoff.md`
- `docs/SINR Claude Continuation Handoff.md`
- `docs/SINR V4.2 Comparison Analysis.md`
- `docs/march 16/V4.3a Run Report.md`
- `docs/march 16/V4.3c Neighbor Probe Report.md`
- `.claude/compacted-sessions/sinr-v3-recovery-handoff-release-gates.md`
- `.claude/compacted-sessions/session_3014_full_context.md`

## Bottom Line

The program is no longer in the phase of asking whether we should merge backfill or whether radiata is simply underrepresented.

That phase is over.

The current state is:

- merged no-GEDI lineage exists,
- merged no-GEDI run exists,
- radiata improved only modestly,
- merged data does not look broadly broken,
- and the next job is a focused forensic phase on plantation supervision, background negatives, inference parity, and head/representation diagnosis.
