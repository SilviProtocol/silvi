# SINR Hybrid Review Batch

Date: 2026-03-12
Status: created for manual audit, no automatic approvals

## Purpose

This is a small human-review batch for hybrid override decisions.

It is intended to let us inspect a manageable slice of blocked hybrid candidates before any broader approval policy is considered.

Builder script:

- `orchestrator/build_sinr_hybrid_review_batch.py`

## Current batch

- table:
  - `species_data.sinr_hybrid_override_review_batch__hybrid_review_100_20260312_223500`
- total rows:
  - `100`

## Selection policy

- `70` rows from `backfill`
- `30` rows from `new_gbif`
- all rows are currently:
  - `context_quality_status = 'legacy_safe_candidate'`
  - `release_gate_default = 'block_pending_audit_override'`

This is intentional.

The goal is not diversity across all blocked buckets yet.
The goal is to review the main blocked-but-candidate pool that would matter most for a future training-only hybrid policy.

## Current composition

- `backfill legacy_safe_candidate`: `70`
- `new_gbif legacy_safe_candidate`: `30`

## Relationship to pilot override

One separate pilot override was already tested successfully end-to-end:

- override release id:
  - `pilot_hybrid_override_20260312_220500`
- resulting hybrid release:
  - `species_data.sinr_train_release__hybrid_train_only_20260312_221500`

That pilot proved the plumbing.

This 100-row batch is for broader review, not automatic promotion.

## Recommended use

For each reviewed row, decide one of:

- approve for `hybrid_train_only`
- reject / keep blocked
- defer pending more provenance

Approvals should only be entered via:

- `orchestrator/register_sinr_hybrid_override.py`

## Important caution

This batch does not prove the rows are safe.

It only provides a practical review queue.
