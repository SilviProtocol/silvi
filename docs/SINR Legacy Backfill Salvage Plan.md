# SINR Legacy Backfill Salvage Plan

Date: 2026-03-12
Status: design only, no data mutation
Owner issue: `treekipedia-xi6`

## Why this exists

The current strict-full rebuild path is clean, but expensive.

The old legacy extraction estate is not uniformly worthless. Some occurrence rows may still be salvageable, especially where:

- the source occurrence context is single-year,
- the extracted feature context matches that year exactly,
- no known decode/contract bug affected the row,
- and the joined training row is complete.

This document defines a conservative salvage strategy so we can recover useful legacy value without pretending all legacy data is safe.

---

## Core principle

Do not reason at raw-feature-table level only.

Reason at **occurrence/example grain**:

- one occurrence row
- one intended `(lat4, lon4, observation_year, emb_year)` context
- one best-available feature attachment
- one quality/salvage status

That lets us salvage good rows, quarantine ambiguous ones, and re-extract only what is necessary.

---

## What should be sampled to verify health?

Yes: a randomized extraction audit is a good idea.

Recommended audit buckets:

1. `legacy_single_year_candidate`
   - occurrence rows at coordinates with only one year in source
   - expected to be the healthiest legacy subset

2. `legacy_multi_year_collapsed`
   - occurrence rows where source had >1 year but legacy feature estate only retained one
   - expected to be risky

3. `legacy_partial_feature`
   - rows with missing columns / sentinel contamination / known contract drift exposure

4. `known_bug_window`
   - rows likely affected by known decode issues like Xiao

For each bucket, sample random occurrence rows and compare:

- source occurrence year
- legacy attached feature year
- strict re-extracted feature year
- key feature deltas
- categorical parity (`xiao`, `jrc`, etc.)

This gives an empirical salvage rate instead of ideology.

---

## Can we always guarantee the correct collapsed year?

No.

That is the key limit.

For some occurrence rows we can prove the legacy feature row corresponds to the correct intended year.
For others we cannot.

Three cases:

### Case A: provably correct

- source occurrence has one valid year context
- legacy feature row exists for that exact year/context
- no competing year ambiguity

These are salvage candidates.

### Case B: provably wrong

- source occurrence has multiple years at the same coordinate
- legacy feature estate retained only one year
- target occurrence year differs from retained year

These must be re-extracted or excluded.

### Case C: ambiguous

- multiple possible source contexts
- incomplete provenance on the legacy row
- or feature row lacks enough audit information to prove correctness

These should be quarantined unless strict context is available.

So the correct rule is not:

- `drop all coordinates that ever had multi-year collapse`

It is:

- `only trust occurrence rows whose attached context can be proven correct or empirically validated`

---

## Recommended salvage status taxonomy

Every occurrence row should get one of these statuses.

### `strict_context_present`

- strict context exists at exact `(lat4, lon4, observation_year, emb_year)`
- preferred gold standard

### `legacy_unverified`

- no strict context yet
- legacy context appears temporally unambiguous
- no known decode/contract bug exposure
- passes completeness checks

### `legacy_partial_candidate`

- legacy context exists
- but some features are missing, sentinel-cleaned, or contract-incomplete

### `ambiguous_context`

- multiple possible year mappings
- or legacy provenance insufficient to prove match

### `needs_reextract`

- exact context missing or provably wrong

### `quarantine`

- context/label conflict or known bug contamination too severe for safe use

---

## Proposed validation rules

### Rule 1: temporal correctness

Check whether the occurrence's intended year can be matched to feature year exactly.

### Rule 2: feature completeness

Check for:

- critical nulls
- sentinel placeholders
- missing contract columns
- impossible categorical values

### Rule 3: bug-window exclusion

Flag rows created during known problematic decode / extraction windows.

### Rule 4: downstream contamination

Do not salvage from exploded or join-corrupted unified tables.
Salvage from occurrence/context lineage, not from bad final assemblies.

---

## Recommended audit workflow

1. Start from occurrence rows.
2. Build intended strict context key per row.
3. Attempt exact strict match.
4. If not found, attempt legacy match.
5. Assign salvage status.
6. Run randomized re-extraction audit on a sample from each status bucket.
7. Only then promote a hybrid training release.

---

## Conservative release policy

### Release A: `strict_only`

- includes only `strict_context_present`
- lowest risk

### Release B: `strict_plus_legacy_safe`

- includes `strict_context_present` + `legacy_unverified`
- only after sample audit validates acceptable error rate

### Release C: diagnostics only

- includes all statuses for analysis, not production training

---

## Bottom line

- You are right that not all backfill should be blindly discarded.
- You are also right that randomized audit extraction can empirically test whether single-year legacy contexts are healthy.
- The key is that salvage decisions must happen at occurrence/example grain, not just table grain.

---

## Implemented non-destructive audit tables

Created on 2026-03-12 via:

- `orchestrator/build_sinr_occurrence_salvage_tables.py`

Tables:

- `species_data.sinr_occurrence_unified_source_v1`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_salvage_candidates_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1`
- `species_data.sinr_occurrence_salvage_summary_v1`

Important caveat:

- `strict_context_present` counts are still moving because `sinr_v3_features_new_gbif_strict_full` is still mid-extraction.
- `backfill` currently has no strict-full table yet, so backfill rows cannot currently land in `strict_context_present`.

Audit-time snapshot:

- `new_gbif strict_context_present`: `8,558,736`
- `new_gbif legacy_unverified`: `4,108,207`
- `new_gbif ambiguous_multi_year`: `184,801`
- `new_gbif ambiguous_legacy_duplicate`: `18,815`
- `new_gbif needs_reextract`: `217,018`
- `backfill legacy_unverified`: `9,373,754`
- `backfill ambiguous_multi_year`: `190,759`
- `backfill ambiguous_legacy_duplicate`: `42,806`
- `backfill needs_reextract`: `1,788,127`

Audit sampling tables:

- `sinr_occurrence_salvage_audit_sample_v1`
  - balanced baseline audit sample
  - `9,000` rows total
- `sinr_occurrence_salvage_audit_sample_legacy90_v1`
  - legacy-focused audit sample
  - `10,000` rows total
  - `9,000` backfill rows + `1,000` new_gbif rows
