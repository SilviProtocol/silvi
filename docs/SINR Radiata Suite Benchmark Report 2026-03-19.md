# SINR Radiata Suite Benchmark Report 2026-03-19

Date: 2026-03-19
Audience: active SINR V4 operators
Status: active benchmark report

## Purpose

Record the first local radiata plantation benchmark suite replay across the current
merged V4 line and selected historical comparison artifacts.

This report is part of `P1/P2` in `docs/SINR P1-P2-D1-T1 Runbook.md`.

## Benchmark Suite

Target taxon:

- `GymPiPiPnCx50820-00`

Points (`year=2023`):

- canonical: `(-41.151583464812404, 175.09968969862783)`
- nearby_1: `(-41.15417025743087, 175.09915476475814)`
- nearby_2: `(-41.15504998747567, 175.1065715571766)`
- nearby_3: `(-41.15927635199013, 175.09953576436868)`
- nearby_4: `(-41.18626808111574, 175.0509971829668)`

## Replay Convention Used Here

All replays used `orchestrator/v3_point_inference.py` with:

- live current sampling path (`location_predictor_FIXED.py`)
- `--land-state-mode zero`
- exact contracts/artifacts listed below

Important:

- these are current replay results under the current harness,
- not guaranteed historical ground truth for every old doc claim,
- and therefore they are evidence for the parity audit, not the final historical record.

## Artifact / Flag Matrix

| Model | Artifact | Key replay flags |
|---|---|---|
| `v41_preview` | `~/model_v41_preview` | `--use-location-encoding --disable-intro-in-gate` |
| `v42_anfull` | `~/model_v42_anfull_hardcap_full` | `--use-location-encoding --disable-intro-in-gate --no-boost` |
| `v43a_nolocation` | `~/model_v43a_nolocation` | `--disable-intro-in-gate --no-boost` |
| `v47_merged` | `~/model_v47_merged_anfull` | `--use-location-encoding --disable-intro-in-gate --no-boost` |
| `v4_gatefix_legacy` | `~/model_local_contract_v4_gatefix_5m` | `--disable-intro-in-gate` |
| `v14_location_legacy` | `~/model_local_contract_v14_location_5m` | `--disable-intro-in-gate --use-location-encoding` |

## Results

### Rank Table

| Model | Canonical | Nearby 1 | Nearby 2 | Nearby 3 | Nearby 4 | Median | Worst |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v41_preview` | 105 | 115 | 111 | 114 | 125 | 114 | 125 |
| `v42_anfull` | 105 | 120 | 95 | 110 | 117 | 110 | 120 |
| `v43a_nolocation` | 100 | 106 | 95 | 99 | 99 | 99 | 106 |
| `v47_merged` | 74 | 83 | 90 | 75 | 84 | 83 | 90 |
| `v4_gatefix_legacy` | 4 | 163 | 172 | 5 | 3 | 5 | 172 |
| `v14_location_legacy` | 54 | 146 | 153 | 43 | 42 | 54 | 153 |

### Probability Table

| Model | Canonical | Nearby 1 | Nearby 2 | Nearby 3 | Nearby 4 |
|---|---:|---:|---:|---:|---:|
| `v41_preview` | 0.6083 | 0.4753 | 0.4816 | 0.5355 | 0.5643 |
| `v42_anfull` | 0.6270 | 0.4934 | 0.6271 | 0.5918 | 0.5585 |
| `v43a_nolocation` | 0.6352 | 0.4711 | 0.3777 | 0.6096 | 0.6396 |
| `v47_merged` | 0.9000 | 0.8564 | 0.8216 | 0.8937 | 0.8628 |
| `v4_gatefix_legacy` | 0.9808 | 0.3693 | 0.3174 | 0.9816 | 0.9866 |
| `v14_location_legacy` | 0.5180 | 0.1312 | 0.1164 | 0.5475 | 0.5530 |

## Main Findings

### 1. The merged V4.7 model is the best currently stable local-suite model

Among the current V4 line, `v47_merged` is clearly best on the suite:

- best canonical rank among current V4 artifacts
- best median local-suite rank among current V4 artifacts
- best worst-case local-suite rank among current V4 artifacts

This does not make it good enough, but it does make it the best current stable base.

### 2. The historical `V4.2` / `V4.3a` rank story is not replaying cleanly

Historical docs said roughly:

- `V4.2` -> `#79`
- `V4.3a` -> `#78`

Current replay under the present harness gives:

- `V4.2` canonical `#105`
- `V4.3a` canonical `#100`

This is direct evidence that benchmark parity is still unresolved.

### 3. Legacy `v4_gatefix` is extremely strong at some nearby points and terrible at others

`v4_gatefix_legacy`:

- canonical `#4`
- nearby_3 `#5`
- nearby_4 `#3`
- but nearby_1 `#163` and nearby_2 `#172`

This is a major clue.

Interpretation:

- either the old artifact is highly brittle / overfit / unstable across very local perturbations,
- or the current harness/sampler is exposing strong local sensitivity that the older single-point story hid.

### 4. Legacy `v14_location` is not reproducing as the best model under current replay

Historical docs treated `v14` as the genuine best legacy model (`#2`).
Current replay gives:

- canonical `#54`
- nearby_3 `#43`
- nearby_4 `#42`
- but nearby_1 `#146`, nearby_2 `#153`

This is another major parity warning.

### 5. The local suite is already useful

The nearby-suite results show that a single-point benchmark was hiding important behavior.

- current merged `v47` is not great, but it is relatively consistent
- older legacy artifacts sometimes look brilliant on a subset of local points and collapse on others

This supports keeping the nearby suite as part of all forward experiments.

## Implications

1. `P2` benchmark/inference parity is mandatory before treating old rank claims as operational truth.
2. The merged `v47` model should remain the base for `T1` because it is the strongest current stable no-GEDI model on the suite.
3. The old-artifact forensic question is no longer just “why was `v14` good?”
   - it is now “why do legacy artifacts show extreme local instability under current replay?”

## Recommended Next Steps

1. Finish the old-artifact parity audit (`P2`)
2. Finish narrow non-GEDI validation (`D1`)
3. Run `T1` merged BCE baseline against the same suite

## Bottom Line

The first local radiata suite changes the story.

- `v47_merged` is the best current stable base, but still not good enough
- historical `v14 #2` should not be trusted blindly
- legacy `v4_gatefix` has shockingly strong local best cases but terrible nearby failures
- so the next move has to be parity + diagnosis, not nostalgia or more blind retraining
