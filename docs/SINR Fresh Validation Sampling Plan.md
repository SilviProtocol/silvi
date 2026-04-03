# SINR Fresh Validation Sampling Plan

Date: 2026-03-12
Status: implemented sampling batch, fresh extraction comparison not yet run

## Why this exists

Human review does not scale across millions of rows.

So the right next validation step is:

- make our best data-quality assumptions,
- then test those assumptions against **fresh strict re-extractions** on a stratified sample,
- with the majority of the sample focused on the lowest-certainty / highest-risk rows.

## Current batches created

- table:
  - `species_data.sinr_fresh_validation_batch__fresh_validation_20260312_224500`
- total rows:
  - `120`

Superseding larger randomized batch:

- table:
  - `species_data.sinr_fresh_validation_batch__fresh_validation_1000_20260313_001500`
- total rows:
  - `1,000`

## Sampling design

This batch is intentionally weighted toward risk.

### High-risk candidate rows (`700` total)

- `500` `high_risk_backfill_candidate`
- `200` `high_risk_new_gbif_candidate`

These are rows currently blocked pending audit override.

### Explicitly blocked risk rows (`200` total)

- `150` `blocked_backfill_risk`
- `50` `blocked_new_gbif_risk`

These are rows we already distrust more strongly.

### Strict controls (`100` total)

- `100` `strict_control`

These act as a baseline / sanity check.

## Why this weighting

Most of the validation budget should go where uncertainty is highest.

The main 1,000-row batch therefore puts:

- `900 / 1,000` rows (`90%`) into risky or blocked strata
- only `100 / 1,000` rows (`10%`) into control strata

Randomization note:

- sampling is randomized **within each stratum** using `ORDER BY RAND()` before row-number trimming
- this avoids the earlier deterministic ordering by `occurrence_example_id`

## What should happen next

For each sampled row, perform a fresh strict extraction and compare:

- coordinate / year context match
- AE anchor fields
- temporal stack parity
- Xiao-related fields
- key train/serve family fields
- whether the row's current classification looks justified

Current implementation status:

- isolated fresh extraction runner:
  - `orchestrator/run_sinr_fresh_validation_extraction.py`
- comparison-table builder:
  - `orchestrator/build_sinr_fresh_validation_compare.py`
- extraction status checker:
  - `orchestrator/check_sinr_fresh_validation_status.py`

Important clarification:

- this uses the **same strict extraction logic** as the main strict sampler on purpose,
- but writes to a **separate validation output table** so we can test assumptions without polluting active strict-full tables,
- so yes, it is similar to the main extraction run, but isolated and targeted to the validation sample.

## Intended outcome

This batch should tell us whether:

- `legacy_safe_candidate` is too optimistic,
- blocked rows are truly bad,
- strict controls behave as expected,
- and which assumptions in the current salvage / integrity system are right or wrong.

## Important note

This is a validation **batch**, not a release.

No approvals are implied by inclusion in this table.

---

## Current execution status

Fresh extraction output table:

- `species_data.sinr_fresh_validation_extract__fresh_validation_1000_20260313_001500`

Comparison table:

- `species_data.sinr_fresh_validation_compare__fresh_validation_1000_20260313_001500`

Failure table:

- `species_data.sinr_fresh_validation_failures__fresh_validation_1000_20260313_001500`

Current outcome:

- sampled rows: `1,000`
- fresh extracted rows landed: `860`
- rows without fresh extract: `140`
- logged unsampleable failures: `2`

Observed extraction failure signature:

- `Image.select: Band pattern 'Gpp' was applied to an Image with no bands`

This indicates the validation run surfaced a real temporal extraction edge case rather than just queue noise.
