# SINR Hybrid Override System

Date: 2026-03-12
Status: implemented, fail-closed, no approvals by default

## Purpose

This documents the explicit override system for future hybrid SINR releases.

It exists so hybrid rows are not silently promoted by naming, hope, or ad hoc query filters.

Builder script:

- `orchestrator/build_sinr_hybrid_override_system.py`

## What it creates

- `species_data.sinr_hybrid_override_registry_v1`
- `species_data.sinr_hybrid_override_candidate_queue_v1`
- `species_data.sinr_hybrid_override_duplicate_audit_v1`
- `species_data.sinr_hybrid_override_orphan_audit_v1`
- `species_data.sinr_occurrence_release_eligibility_v1`

Guarded registration helper:

- `orchestrator/register_sinr_hybrid_override.py`

## Core design

### 1. Override registry

`sinr_hybrid_override_registry_v1` is the only table that can explicitly approve a hybrid row for release.

It starts empty.

No rows are approved by default.

### 2. Candidate queue

`sinr_hybrid_override_candidate_queue_v1` contains rows currently blocked with:

- `release_gate_default = 'block_pending_audit_override'`

Current count:

- `13,428,663`

These are review candidates, not release-approved rows.

### 3. Effective eligibility table

`sinr_occurrence_release_eligibility_v1` combines:

- field-integrity status
- release gates
- any explicit override decisions

It computes:

- `allow_strict_release`
- `allow_hybrid_release`
- `block_pending_audit_override`
- `block`

## Current fail-closed behavior

Because the override registry is empty:

- `allow_strict_release`: `8,579,371`
- `allow_hybrid_release`: `0`
- `block_pending_audit_override`: `13,428,663`
- `block`: `2,474,989`

This is intentional.

Audit tables currently show:

- duplicate overrides: `0`
- orphaned overrides: `0`

Pilot state now includes:

- one active approved override in `sinr_hybrid_override_registry_v1`
- this yields exactly `1` `allow_hybrid_release` row in `sinr_occurrence_release_eligibility_v1`

## What must happen before any hybrid release exists

1. Manual or programmatic audit of candidate rows.
2. Explicit insertion of approved rows into `sinr_hybrid_override_registry_v1`.
3. Rebuild of `sinr_occurrence_release_eligibility_v1`.
4. A dedicated hybrid release builder that only uses:
   - `effective_release_gate = 'allow_hybrid_release'`

That builder now exists:

- `orchestrator/build_sinr_hybrid_train_release.py`
- documented in `docs/SINR Hybrid Train-Only Release Builder.md`

## What this prevents

- accidental promotion of `legacy_safe_candidate` rows
- docs/naming being treated as approval
- analysts treating candidate pools as release-ready tables

## Important caution

This system only solves approval governance.

It does not itself prove:

- Xiao correctness
- land-state parity
- feature-family completeness
- source normalization truth

Those still require explicit audit rules before any override is granted.
