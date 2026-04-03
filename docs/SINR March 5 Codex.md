# SINR March 5 Codex Audit

Date: 2026-03-05
Auditor: Codex (verification-first, no code/data edits during audit)
Scope: SINR v3 pipeline reality check across docs, code, and BigQuery production tables in `treekipedia-479918.species_data`.

---

## 1) Why this document exists

This document is a forensic-grade audit of SINR v3 status and integrity after conflicting narrative updates in March docs.

Primary goals:

1. Verify what is true in BigQuery right now.
2. Separate implemented reality from speculative or hallucinated claims.
3. Identify data integrity risks (temporal drift, join amplification, duplicates, table explosions).
4. Provide actionable fixes with proof anchors.

No claims in this file are based only on prose docs. Every critical claim is tied to code inspection and/or live BQ query output.

---

## 2) Source hierarchy and trust model

Trust order used in this audit:

1. **Live BigQuery table metadata and SQL query results** (highest trust).
2. **Executable code paths** in `orchestrator/*.py` (high trust for logic/intention).
3. **Operational docs** (`GO.md`, TODO/CHANGELOG) (medium trust).
4. **Narrative docs** (`docs/SINR March 4 - Claude`, `docs/SINR March 5 - Claude`, `docs/SINR March 5 Gemini.md`) (lowest trust unless corroborated).

---

## 3) Evolution timeline (v2.2 -> v3)

### v2.2 baseline

- Legacy production model and training artifacts are present.
- `sinr_v3_unified_v1` exists with:
  - `14,609,514` rows
  - `24,832` species

Interpretation: v1 had the known species-collapse issue relative to v2.2 historical expectations.

### v3 consolidation v2 intent

`orchestrator/consolidate_bq_v2.py` clearly states intent to fix species collapse by switching backfill taxon source:

- From `alphaearth_embeddings_v4`-based taxon mapping (limited species coverage)
- To `occurrences`-based taxon mapping (wider species coverage)

This was implemented, but with critical side effects (detailed below).

---

## 4) Live BigQuery reality (verified)

### Core v3 tables exist

Confirmed in `treekipedia-479918:species_data`:

- `sinr_v3_features_new_gbif`
- `sinr_v3_features_backfill`
- `sinr_v3_carbon_temporal`
- `sinr_v3_hilda_lulc`
- `sinr_v3_aridity_index`
- `sinr_v3_is_introduced`
- `sinr_v3_land_state_t1`
- `sinr_v3_unified_v1`
- `sinr_v3_unified_v2`
- `sinr_v3_unified_v2_final`

### Current row counts (direct query)

- `sinr_v3_features_new_gbif`: `9,868,255`
- `sinr_v3_features_backfill`: `5,256,693`
- `sinr_v3_carbon_temporal`: `12,926,305`
- `sinr_v3_hilda_lulc`: `13,999,971`
- `sinr_v3_is_introduced`: `30,262,138`
- `sinr_v3_land_state_t1`: `32,323,081`
- `sinr_v3_unified_v1`: `14,609,514`
- `sinr_v3_unified_v2`: `32,323,081`
- `sinr_v3_unified_v2_final`: `1,762,406,754`

### Unified v2 temporal and species stats

`sinr_v3_unified_v2`:

- Rows: `32,323,081`
- Distinct species (`taxon_id`): `45,979`
- `observation_year`: min `1574`, max `2025`, nulls `0`
- `emb_year`: min `2017`, max `2024`, nulls `0`

Source split:

- `backfill`: `19,588,574` rows, `43,973` species
- `new_gbif`: `12,734,507` rows, `19,189` species

Species overlap:

- Overlap species: `17,183`
- Backfill-only: `26,790`
- New-GBIF-only: `2,006`

Interpretation: species recovery objective succeeded numerically, but row quality and join cardinality remain problematic.

---

## 5) Technical logic verified in code

### 5.1 Consolidation v2 join design

File: `orchestrator/consolidate_bq_v2.py`

Backfill taxon assignment:

- Uses `occurrences` with `SELECT DISTINCT ROUND(lat), ROUND(lon), taxon_id`
- Joins backfill only on rounded coordinates
- **Explicitly does not join on year** (`observation_year`) by design comment

Evidence lines:

- `orchestrator/consolidate_bq_v2.py:201`
- `orchestrator/consolidate_bq_v2.py:202`
- `orchestrator/consolidate_bq_v2.py:229`

### 5.2 Chunked execution behavior

The script supports resume by appending to existing table:

- If output table exists, it does `INSERT INTO` for chunks instead of rebuild.

Evidence:

- `orchestrator/consolidate_bq_v2.py:321`
- `orchestrator/consolidate_bq_v2.py:381`

Risk: reruns can create duplicate rows if no anti-dup guard is enforced.

### 5.3 Temporal sampling caveat

File: `orchestrator/unified_gee_sampler_v3.py`

- Uses representative temporal strategy by batch (median-year style behavior), not strict row-by-row year-perfect retrieval for all temporal products.

Implication: acceptable as an engineering approximation only if documented and tested; otherwise can be misread as strict temporal alignment.

### 5.4 GEDI handling risk

File: `orchestrator/unified_gee_sampler_v3.py`

- Uses `.mosaic()` over GEDI collection path (`LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` pattern).

File: `orchestrator/carbon_gee_sampler.py`

- Contains explicit-asset style handling that appears safer for GEDI.

Interpretation: mixed GEDI logic paths exist; one path is flagged high risk for unintended spatial compositing behavior.

---

## 6) Hallucination / drift matrix

### Claims that are supported

From `docs/SINR March 5 - Claude`:

- `sinr_v3_unified_v2` around `32.3M` rows and `45,979` species: **supported**.
- `sinr_v3_is_introduced` around `30.26M`: **supported**.
- `sinr_v3_land_state_t1` around `32.3M`: **supported**.
- Species-collapse in v1 and recovery in v2: **supported**.

### Claims that are partially true but operationally unsafe

- "Year not lost, only dropped from taxon assignment join": technically true for stored columns, but **semantically dangerous** because taxon identity can be borrowed across years at a location.
- "Data ready for training": only true if one accepts major cardinality issues and leakage risk.

### Claims contradicted by hard reality

- Any expectation that `sinr_v3_unified_v2_final` should be near ~32M rows: **contradicted**.
  - Actual `sinr_v3_unified_v2_final`: `1,762,406,754` rows.

### Gemini doc status

`docs/SINR March 5 Gemini.md` made strong corruption claims.

- Some warnings were directionally correct (temporal join risk, row blow-up risk).
- Several numeric specifics were stale/inexact.
- Net: useful risk radar, not authoritative truth source.

---

## 7) Proofs of data integrity risks

### 7.1 Unified v2 duplicates are substantial

On exact key `(taxon_id, lat, lon, observation_year, emb_year)`:

- Duplicate groups: `702,550`
- Extra duplicate rows: `1,828,673`

After including source in key `(data_source, taxon_id, lat, lon, observation_year, emb_year)`:

- Duplicate groups: `682,005`
- Extra rows: `1,805,104`

Interpretation: duplicates are not just cross-source collisions; many are intra-source.

### 7.2 Backfill coordinate multiplexing is severe

For backfill coordinates joined against `occurrences` taxon space:

- Backfill coords: `5,232,752`
- Coords with >1 taxon: `1,487,341`
- Mean taxa per coord: `3.45`
- Max taxa at a coord: `2,177`

Interpretation: coordinate-only taxon join creates high ambiguity and temporal/species cross-assignment risk.

### 7.3 Join amplification across phases

Recomputed from consolidation logic:

- Base rows after taxon joins: `30,660,377`
- After carbon left join: `31,061,060`
- After hilda left join: `31,061,060`
- After aridity left join: `31,162,784`

Actual `sinr_v3_unified_v2`: `32,323,081`

Gap vs recomputed full join: `+1,160,297` rows.

Interpretation: likely replay/append accumulation from chunked execution, plus duplicate sensitivity in source tables.

### 7.4 Auxiliary table key quality

`sinr_v3_is_introduced` key quality (`taxon_id, lat4, lon4`):

- Rows: `30,262,138`
- Duplicate key rows: `15` (very low)

`sinr_v3_land_state_t1` key quality (`data_source, lat4, lon4, observation_year, emb_year`):

- Rows: `32,323,081`
- Distinct keys: `13,703,022`
- Duplicate rows over key: `18,620,059`

Multiplicity buckets in land_state keyspace:

- `1`: `10,853,291` keys
- `2-5`: `2,124,050`
- `6-20`: `513,233`
- `21-100`: `206,859`
- `101+`: `5,589`

Interpretation: land_state table is not key-unique for geo-time-source and is dangerous for direct joins.

### 7.5 Final table explosion (already happened)

`sinr_v3_unified_v2_final` exists and is massively inflated:

- Rows: `1,762,406,754`
- Species: `45,979`
- Distinct base keys (`data_source,taxon_id,lat,lon,observation_year,emb_year`): `30,517,977`

Interpretation: this table is not safe as a direct training source without strict dedup/keying.

### 7.6 Confirmed temporal compression in v3 sampler

This is now verified as a hard fact in both code and data:

- `unified_gee_sampler_v3.py` deduplicates by pixel only (`lat4dp, lon4dp`) and keeps latest year.
- This is not per-pixel-per-year sampling.

BigQuery proof (new GBIF branch):

- Source multi-year pixels: `264,114`
- Multi-year source pixels that became single-year in `sinr_v3_features_new_gbif`: `264,114`
- Collapse rate: `100%`

BigQuery proof (backfill branch):

- Source multi-year pixels: `187,082`
- Multi-year source pixels that became single-year in `sinr_v3_features_backfill`: `187,082`
- Collapse rate: `100%`

Implication: many historical pixel-year contexts were intentionally dropped at sampling stage.

### 7.7 Backfill strict species-year recoverability (binary hit/miss)

Strict match key used: `(lat4, lon4, taxon_id, observation_year)` against `occurrences`.

- Backfill unified rows: `19,588,574`
- Exact strict hits: `10,351,028` (`52.842%`)
- Strict misses: `9,237,546` (`47.158%`)

Interpretation: this 47.158% is a label-confidence issue in current assembled backfill-unified rows.

### 7.8 Backfill missing pixel-year feature contexts

Compare `existing_training_coords` vs `sinr_v3_features_backfill` at `(lat4, lon4, observation_year, emb_year)`:

- Existing backfill pixel-year rows (non-null year): `11,439,575`
- Present in backfill features: `9,928,315`
- Missing from backfill features: `1,511,260` (`13.211%`)

For multi-year pixels only:

- Existing multi-year pixel-year rows: `1,705,918`
- Missing from features: `1,511,260` (`88.589%`)

Distinct cardinality check:

- `existing_training_coords` distinct pixels: `5,232,751`
- `existing_training_coords` distinct pixel-year: `5,871,847`
- `sinr_v3_features_backfill` distinct pixels: `5,232,752`
- `sinr_v3_features_backfill` distinct pixel-year: `5,232,752`

Interpretation: backfill features are effectively one-row-per-pixel, not one-row-per-pixel-year.

### 7.9 Micro-resample confirmation in live GEE

Surgical spot checks on multi-year pixels show temporal signal changes across years at same pixel (examples observed):

- Dynamic World class changed between early and late years (e.g. `0 -> 1`, `0 -> 6`, `0 -> 2`).
- MODIS LC also changed in sampled examples (e.g. `8 -> 9`).

Interpretation: dropped pixel-year contexts are not redundant; they can carry materially different temporal signals.

---

## 8) Temporal integrity analysis

### Facts

- `observation_year` is populated for all unified rows.
- `emb_year` is populated and limited to `2017-2024`.
- Many rows have `observation_year < 2017` while `emb_year = 2017` (by design fallback behavior).

Distribution highlights:

- `observation_year < 2017`: `13,080,853` rows
- `observation_year > 2024` (mostly 2025): `165,802` rows

### Risk statement

Temporal values are present, but **temporal semantics are weakened** for backfill taxon assignment because species identity may come from any year observed at that coordinate.

This is temporal leakage risk, not literal null-year loss.

Additional confirmed loss mode:

- Sampling pipeline compressed multi-year pixels to a single retained year (latest), so many valid historical pixel-year contexts were never represented in feature tables.

---

## 9) What is complete vs not complete

### Actually complete

- Large-scale v3 feature extraction pipelines produced major tables.
- Consolidation v2 ran and restored species breadth.
- `is_introduced` computed at large scale.
- Land state table generated.

### Not complete in production-quality sense

- Cardinality-safe final training table is not complete.
- Temporal-consistent backfill taxon attribution is not solved.
- Dedup guarantees are not enforced.
- Rebuild idempotency is not guaranteed.

---

## 10) Root causes

1. **Coordinate-only backfill taxon join** (`occurrences` year ignored).
2. **Chunk resume via raw append** with no anti-dup guard.
3. **Auxiliary left-join tables are not key-unique** at join grain.
4. **Narrative status updates outpaced integrity validation**.

---

## 11) Severity map

### Critical

- `sinr_v3_unified_v2_final` row explosion (`1.76B`) from non-unique join path.
- Land state key multiplicity if joined at geo-time-source without pre-aggregation.

### High

- Backfill temporal leakage from coordinate-only taxon assignment.
- Large duplicate burden in unified v2.

### Medium

- GEDI mosaic-path uncertainty.
- Temporal approximation behavior not strongly constrained/documented in trainer assumptions.

---

## 12) Immediate fixes (prioritized)

### Fix 1: Freeze unsafe training inputs

Do not train from `sinr_v3_unified_v2_final` in current form.

Use a quarantined, deduped rebuild as new canonical training table.

### Fix 2: Rebuild land_state join safely

Before joining land_state, enforce one row per `(data_source, lat4, lon4, observation_year, emb_year)` using deterministic aggregation.

Example pattern:

```sql
WITH land_state_1to1 AS (
  SELECT
    data_source,
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    emb_year,
    ANY_VALUE(land_state_class) AS land_state_class,
    AVG(disturbance_intensity) AS disturbance_intensity,
    AVG(forest_stability) AS forest_stability,
    ANY_VALUE(successional_stage) AS successional_stage,
    AVG(ae_temporal_change_l2) AS ae_temporal_change_l2,
    AVG(natural_score) AS natural_score,
    AVG(plantation_score) AS plantation_score,
    ANY_VALUE(is_forest) AS is_forest,
    AVG(years_since_loss) AS years_since_loss
  FROM `treekipedia-479918.species_data.sinr_v3_land_state_t1`
  GROUP BY data_source, lat4, lon4, observation_year, emb_year
)
```

Then join only to `land_state_1to1`.

### Fix 3: Rebuild unified v2 idempotently

Rebuild from source with either:

- full replace (`CREATE OR REPLACE TABLE`) per full query, or
- chunk writes into staging + final distinct key collapse.

Do not append into existing target without dedup key enforcement.

### Fix 4: Harden backfill taxon attribution

Options (ordered safest to pragmatic):

1. Strict year match on rounded coord + year where feasible.
2. Year window match (for known noisy years), with nearest-year selection.
3. Probabilistic attribution with confidence score and downstream weighting.

At minimum, add provenance columns:

- `taxon_assignment_mode` (`strict_year`, `nearest_year`, `coord_only`)
- `taxon_assignment_year_delta`
- `taxon_assignment_confidence`

For strict rebuild mode, use binary policy only:

- `HIT` = exact `(lat4, lon4, taxon_id, observation_year)` exists in trusted occurrence source.
- `MISS` = no exact key hit; quarantine (do not silently relabel).

### Fix 5: Add mandatory integrity gates

Block promotion if any of these fail:

- Row amplification ratio above threshold after each join stage.
- Duplicate ratio above threshold on canonical key.
- Aux join tables not unique on join key.
- Unexpected year-range shifts.

Add two pre-training gates specific to the newly confirmed issue:

- Gate A: pixel-year completeness threshold vs source (`existing_training_coords` and `gbif_new_occurrences`).
- Gate B: strict species-year hit-rate threshold for any row used in training.

### Fix 6: Rebuild sampler at pixel-year grain

`unified_gee_sampler_v3.py` must deduplicate at least by:

- `(lat4dp, lon4dp, observation_year, emb_year)`

not by pixel only.

This is required to preserve temporal contexts before consolidation.

---

## 13) Recommended canonical keys

### Unified training grain

- `(data_source, taxon_id, lat4, lon4, observation_year, emb_year)`

### Land state grain

- `(data_source, lat4, lon4, observation_year, emb_year)`

### is_introduced grain

- `(taxon_id, lat4, lon4)`

Every join should preserve row cardinality against expected grain deltas, logged at each stage.

---

## 14) Explicit answers to the original concern set

### Pipeline corruption?

**Yes, materially at join/cardinality level.**
Not raw table absence corruption, but semantic and multiplicative corruption.

### Consolidation errors?

**Yes.**
Species recovery succeeded, but with temporal leakage risk and duplicate amplification.

### Temporal context loss?

**Partially.**
Year columns exist, but taxon-year relationship is weakened in backfill.

### Hallucinated status claims?

**Mixed.**
Topline counts are mostly true; readiness and safety implications were overstated.

---

## 15) Final verdict

SINR v3 is **feature-complete in volume**, but **not yet integrity-safe for final training consumption** without remediation.

In short:

- Data acquisition progress: strong.
- Species coverage recovery: successful.
- Join integrity and reproducibility: currently unsafe.
- Immediate priority: strict rebuild with pixel-year sampling, exact species-year verification, and cardinality controls.

Training should not proceed until strict rebuild outputs pass integrity gates.

---

## 16) Pre-training plan of action (strict rebuild)

Objective: produce a training table with deterministic provenance and binary verification (`HIT`/`MISS`) only.

Step 1: Re-sample feature tables at pixel-year grain

- Rebuild `sinr_v3_features_backfill` from `existing_training_coords` at `(lat4, lon4, observation_year, emb_year)`.
- Rebuild `sinr_v3_features_new_gbif` at same grain from `gbif_new_occurrences`.

Step 2: Strict species-year relink

- Join labels with exact key `(lat4, lon4, taxon_id, observation_year)`.
- Keep only `HIT` for strict-training table.
- Route `MISS` into quarantine table for explicit analysis.

Step 3: Cardinality-safe joins for auxiliaries

- Pre-aggregate auxiliary tables to join grain before joining (especially land-state).
- Enforce one row per canonical key.

Step 4: Build two artifacts

- `sinr_v3_unified_strict_train` (HIT-only, deduped)
- `sinr_v3_unified_strict_quarantine` (MISS and any key conflicts)

Step 5: Final go/no-go gates before training

- No duplicate canonical keys in strict-train table.
- No join amplification beyond expected tolerance.
- Pixel-year completeness reported and accepted.
- Strict hit-rate and coverage accepted.

### Execution update (completed in BigQuery)

Strict rebuild has now been executed into new, non-destructive tables (original v3 tables preserved):

- `sinr_v3_strict_backfill_hit_keys`
- `sinr_v3_strict_new_gbif_hit_keys`
- `sinr_v3_strict_unified_hits_raw`
- `sinr_v3_strict_unified_train_core`
- `sinr_v3_unified_strict_train`
- `sinr_v3_strict_unified_quarantine`
- `sinr_v3_strict_land_state_1to1`
- `sinr_v3_strict_is_introduced_dedup`
- `sinr_v3_strict_backfill_missing_feature_contexts`
- `sinr_v3_strict_new_gbif_missing_feature_contexts`

Strict rebuild outcomes:

- `sinr_v3_unified_strict_train`: `22,033,317` rows, `45,247` species
- Duplicate canonical keys in strict train: `0`
- Enrichment coverage in strict train:
  - `is_introduced` nulls: `0`
  - land-state nulls: `0`
- `sinr_v3_strict_unified_quarantine`: `9,640,797` rows, `18,167` species

Strict hit/miss rates by source:

- `new_gbif`: `12,464,405` / `12,734,507` strict hits in final strict train (`97.879%`), misses `0` after strict join (difference is duplicate-collapse between unified_v2 and canonical strict key)
- `backfill`: `9,568,912` / `19,588,574` strict hits in final strict train (`48.850%`), misses `9,640,797` (`49.216%`) with remainder explained by duplicate-collapse

Accounting note:

- `sinr_v3_unified_v2` total rows: `32,323,081`
- `strict_train + strict_quarantine`: `31,674,114`
- dedup-collapse gap: `648,967` rows (duplicate casualties, not missing keyspace)
- quarantine-only species (not present in strict train): `732`

Missing feature contexts (distinct pixel-year contexts requiring re-extraction for full temporal completeness):

- Backfill missing contexts: `752,692`
- New GBIF missing contexts: `336,632`

Interpretation:

- A strict, non-exploding, deduplicated training table now exists.
- Backfill remains the limiting factor for strict species-year coverage.
- Full temporal completeness still requires targeted GEE re-extraction of missing contexts.

---

## 17) Appendix: Key verified numbers snapshot

- `sinr_v3_unified_v1`: `14,609,514` rows, `24,832` species
- `sinr_v3_unified_v2`: `32,323,081` rows, `45,979` species
- `sinr_v3_unified_v2` duplicate extras on canonical key: `1,828,673`
- `sinr_v3_is_introduced`: `30,262,138` rows, duplicate key rows `15`
- `sinr_v3_land_state_t1`: `32,323,081` rows, duplicate key rows `18,620,059`
- `sinr_v3_unified_v2_final`: `1,762,406,754` rows, `45,979` species
- Backfill strict species-year exact-hit rate: `52.842%`
- Backfill strict species-year misses: `47.158%`
- Backfill missing pixel-year feature contexts: `1,511,260` (`13.211%`)
- Multi-year pixel collapse to single feature year: `100%` (both new-GBIF and backfill)

These numbers are from live BQ queries run during this audit session.
