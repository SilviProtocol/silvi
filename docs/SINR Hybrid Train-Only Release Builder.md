# SINR Hybrid Train-Only Release Builder

Date: 2026-03-12
Status: implemented, fail-closed

## Purpose

This builder exists so a future hybrid training release can only include rows that are explicitly approved through the hybrid override system.

Builder script:

- `orchestrator/build_sinr_hybrid_train_release.py`

## What it builds

For each run it creates:

- `species_data.sinr_release_allowlist__<release_id>`
- `species_data.sinr_train_release__<release_id>`
- a registry row in `species_data.sinr_release_registry_v1`

## Enforced logic

The builder includes only rows where:

- `effective_release_gate IN ('allow_strict_release', 'allow_hybrid_release')`

Because the override registry is currently empty, there are **no** `allow_hybrid_release` rows yet.

So today this builder behaves the same as strict-only, by design.

## Current release id

- `hybrid_train_only_20260312_221500`

Audit verification:

- allowlist rows: `8,579,372`
- release rows: `8,172,289`
- `allow_hybrid_release` rows in release: `1`

Pilot proof:

- one manually approved `hybrid_train_only` override now flows end-to-end into the release
- pilot override release id:
  - `pilot_hybrid_override_20260312_220500`
- approved occurrence example id:
  - `0000014f1fc240a5790c1634179dfbc996f46a600dfd295f71bda7341dcc05b7`

Important implementation note:

- the hybrid builder initially inherited the strict-only assumption that all rows must join to strict raw features
- that would have prevented approved legacy/hybrid rows from ever entering the release
- this was corrected so:
  - `allow_strict_release` rows prefer strict raw features
  - `allow_hybrid_release` rows fall back to preview payload for common columns
  - preview-only non-strict feature families still remain nulled conservatively

## Why this still matters now

Even with zero approved hybrid rows today, this builder proves the governance path is ready:

- strict rows can flow through automatically
- hybrid rows can flow through only after explicit override approval

## Required future step before hybrid rows appear

At least one row must be inserted into:

- `species_data.sinr_hybrid_override_registry_v1`

with:

- `override_decision = 'approve'`
- `override_scope = 'hybrid_train_only'`
- `status = 'active'`

Then rebuild:

- `species_data.sinr_occurrence_release_eligibility_v1`

and rerun the builder.

## Related scripts

- `orchestrator/build_sinr_hybrid_override_system.py`
- `orchestrator/register_sinr_hybrid_override.py`
- `orchestrator/build_sinr_strict_only_release.py`

## Safety properties

- no hybrid approvals by default
- duplicate override audit table exists
- orphaned override audit table exists
- explicit registry required for any hybrid inclusion
