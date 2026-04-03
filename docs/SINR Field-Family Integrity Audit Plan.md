# SINR Field-Family Integrity Audit Plan

Date: 2026-03-12
Owner issue: `treekipedia-9fq`
Status: design / forensic mapping

## Why this exists

The current salvage system is strong at row-grain context matching, but it is not yet a complete model of feature integrity.

That is because SINR feature payloads are not one homogeneous block. They include:

- features tied to `observation_year`,
- features tied to `emb_year`,
- full fixed-year temporal stacks,
- and static / quasi-static layers.

Some feature families also have bug windows or pipeline-specific provenance problems.

So the master salvage system needs a second layer:

- row-grain context status
- plus field-family integrity status

---

## Key semantic distinction

### `observation_year`

- the year of the occurrence / observation record

### `emb_year`

- the AlphaEarth anchor year used for the row's primary embedding-year-dependent features
- constrained to available AlphaEarth years (`2017..2024` in current estate)

Important nuance:

- now that SINR samples the full AlphaEarth temporal stack, `emb_year` is not the only AE signal in the row
- but it still matters because several feature families remain tied specifically to the selected AE year

---

## Current understanding of feature families

### A. Observation-year-tied

These should be interpreted relative to `observation_year`.

Examples:

- year-specific temporal env features from `get_temporal_env_for_year(obs_year)`
- Dynamic World / MODIS / fire / nighttime-lights at observation year
- obs-side delta variables
- carbon/HILDA fields with `_at_obs`

### B. Embedding-year-tied

These should be interpreted relative to `emb_year`.

Examples:

- primary `emb_*` feature block
- AE-year side categorical / delta features
- carbon/HILDA fields with `_at_ae`
- older single-year AE joins from v2 / v2.2 lineage

### C. Fixed-year temporal stack

These are not tied to one selected `emb_year`; they are the full stack.

Examples:

- `ae_2017_* ... ae_2024_*`

These are row-attached snapshots across calendar years.

### D. Static / quasi-static

These should not vary by row year in normal use.

Examples:

- terrain
- many soil layers
- aridity / long-term summaries (depending on derivation)
- static carbon summary products

---

## Why `emb_year` still matters even with all AE years sampled

Yes, the system now samples the full AE stack.

But `emb_year` still matters because:

- the row still has a designated AE anchor year,
- the primary embedding branch depends on that year,
- some temporal and auxiliary features are sampled or interpreted relative to that anchor,
- and the canonical strict context key still includes it.

So `emb_year` is not obsolete; it is now one coordinate in a richer temporal representation.

---

## Occurrence source visibility

### What we have

- `species_data.gbif_new_occurrences`
  - explicit recent GBIF branch
- `species_data.existing_training_coords`
  - legacy/backfill branch
- `species_data.occurrences`
  - broad master occurrence estate

### What we do not have cleanly yet

- a first-class normalized `occurrence_source_class` like:
  - `gbif_recent`
  - `gbif_legacy`
  - `other_legacy`
  - `mixed_unknown`

### Practical current state

- `occurrences` contains `gbifID` and `occurrenceID`, but not a clean source-class column
- live audit shows only about `9.4M / 96.5M` rows have GBIF identifiers populated in `occurrences`
- so the current estate is not yet sufficient to perfectly separate all legacy rows into `GBIF` vs `Other`

That source normalization should become part of the master occurrence dataset design.

---

## Overlap interpretation warning

Do not confuse:

- schema overlap,
- row overlap,
- context overlap,
- and source overlap.

Examples:

- two tables can have different schemas but still describe the same real occurrence context
- two tables can share coordinates but not the same taxon/year/example rows
- two rows can share context but still represent different occurrences or taxa

The salvage model should therefore reason at three levels:

1. occurrence identity
2. context identity
3. field-family integrity

---

## Feature-family bug windows / known risks

### Xiao

- known RGB decode bug historically affected interpretation of planted vs natural classes
- requires bug-window flagging and/or corrected backfill provenance

### Land-state

- training-side BQ computation vs inference-side heuristic mismatch
- row may be usable for training while land-state family is still not safe for serving parity

### Aridity / ET0 / IPCC forest class

- known periods where training contract included them but live inference sampler did not
- these need explicit feature-family parity flags

### Carbon / productivity / HILDA families

- not all are always online / temporal / available the same way
- some are better treated as optional field families rather than core always-on training requirements

---

## Recommended next extension to salvage system

Add a field-family integrity table keyed by occurrence example:

- `ae_anchor_ok`
- `ae_stack_ok`
- `temporal_obs_ok`
- `static_env_ok`
- `xiao_ok`
- `land_state_ok`
- `carbon_family_ok`
- `aridity_family_ok`
- `hilda_family_ok`
- `fully_trainable`

This should join onto `sinr_occurrence_salvage_status_v1`.

---

## Implemented scaffold table

Created on 2026-03-12:

- `species_data.sinr_occurrence_field_integrity_status_v1`

Builder:

- `orchestrator/build_sinr_field_integrity_status.py`

Current purpose:

- provide a first non-destructive scaffold for field-family integrity attached to `sinr_occurrence_salvage_status_v1`
- distinguish:
  - `strict_raw_match`
  - `preview_inherited_legacy_payload`
  - `legacy_context_only`
  - `no_context_available`
- expose two coarse rollups:
  - `fully_trainable_strict_only`
  - `fully_trainable_hybrid_candidate`
- expose hard-gated axes so unknown rows fail closed by default:
  - `identity_integrity_status`
  - `payload_provenance_status`
  - `release_gate_default`
  - `temporal_validity_default`
  - `requires_manual_audit_override`

Audit-time snapshot:

- `strict_raw_match`: `8,579,371`
- `preview_inherited_legacy_payload`: `13,863,012`
- `legacy_context_only`: `36,424`
- `no_context_available`: `2,004,216`

Current hybrid-candidate mix:

- `strict_context_present`: `8,579,371`
- `legacy_unverified`: `13,428,663`

Current release-gate snapshot:

- `allow_strict_release` + `strict_context_present`: `8,579,371`
- `block_pending_audit_override` + `legacy_unverified`: `13,428,663`
- blocked ambiguous / reextract / other rows: remainder

Important caveat:

- this is a coarse first-pass integrity scaffold, not the final feature-family truth layer
- bug windows and family-specific availability rules still need to be encoded explicitly
- hybrid rows are now fail-closed by default; they are not approved unless a later audit explicitly promotes them

---

## Bottom line

- the current salvage plan is necessary but not sufficient
- it gives row-grain context truth, not full field-grain integrity truth
- `emb_year` still matters even after all-year AE stack sampling
- source normalization (`GBIF` vs `Other`) still needs to be formalized in the occurrence master
- next step is a field-family integrity layer attached to occurrence-grain salvage rows
