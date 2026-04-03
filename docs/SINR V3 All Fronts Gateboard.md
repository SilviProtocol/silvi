# SINR v3 All Fronts Gateboard

Date: 2026-03-06
Scope: strict preview readiness + strict full re-extraction in progress.

## Current Go/No-Go Board

| Front | Status | Evidence | Notes |
|---|---|---|---|
| Temporal integrity (preview strict table) | PASS (with caveat) | `sinr_v3_unified_strict_train`: 0 null `observation_year`/`emb_year`, no sentinel years | Caveat: preview table still inherits pre-strict extraction feature values; full strict run is required for absolute temporal certainty |
| Carbon completeness/sentinel quality | FAIL (for final) / CONDITIONAL (for preview) | Carbon context coverage: 87.397%; sentinel prevalence high in some bands (e.g. `cci_agb_at_obs=-9999`) | Safe for preview experimentation with masking; not final-quality until strict full carbon-temporal reconciliation |
| Label integrity | PASS (preview strict) | 100% rows are `verification_status=HIT`; source split: `existing_training_coords` + `gbif_new_occurrences` | Quarantine remains separate (`sinr_v3_strict_unified_quarantine`) |
| Join/cardinality integrity | PASS | Canonical key rows == distinct keys in strict preview (`22,033,317`) | No duplicate canonical rows in strict preview table |
| Trainer contract readiness | PASS (after compatibility table) | `sinr_v3_unified_strict_train_v30_preview_clean` has all expected `train_on_vm.py` columns | Compatibility table adds unprefixed land-state aliases and sentinel-cleaning for key carbon fields |

## Key Snapshot Metrics

- Strict preview rows: `22,033,317`
- Strict quarantine rows: `9,640,797`
- Strict preview species: `45,247`
- Strict preview contexts with carbon: `87.397%`
- Strict preview contexts with HILDA: `96.075%`
- `is_introduced` nulls in strict preview: `0`
- Land-state nulls in strict preview: `0`

## Strict Full Re-Extraction Status

- Runner: `orchestrator/unified_gee_sampler_v3_strict.py`
- Output tables:
  - `sinr_v3_features_new_gbif_strict_full`
  - `sinr_v3_features_backfill_strict_full`
- Resume support: enabled (`--resume-from-bq`)
- Unsampleable tracking: enabled (`sinr_v3_strict_unsampleable_contexts`)

Current extraction snapshot:

- Target contexts total: `14,710,338`
- As-of 2026-03-06 03:18 UTC, extracted rows in `sinr_v3_features_new_gbif_strict_full`: ~`130,699`
- Remaining contexts: ~`14.59M` (before backfill strict-full stage)
- Throughput is currently unstable; earlier burst estimates were optimistic.
- ETA is currently **rolling/uncertain**; use live telemetry snapshots rather than fixed-day estimates.

## Training Decision

- Proceed now with **v3.0 strict preview** on `sinr_v3_unified_strict_train_v30_preview_clean`.
- Do **not** call this final production model.
- After strict full extraction + strict rebuild, run **v3.1 strict full** as final candidate.
