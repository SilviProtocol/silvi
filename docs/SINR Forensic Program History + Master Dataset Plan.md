# SINR Forensic Program History + Master Dataset Plan

Date: 2026-03-12
Owner: treekipedia-xi6
Status: working synthesis for data governance, prediction, and recommendation cleanup

## Why this document exists

We need one narrative that explains:

- how Treekipedia moved from centroid/k-means habitat retrieval into SINR-style neural training,
- why v2/v2.2 could perform well on plantation cases like NZ radiata pine,
- how v3 data expansion introduced integrity regressions,
- which current tables are useful vs dangerous,
- and how to create one canonical master data system without deleting legacy assets yet.

This document is intentionally blunt. The repo accumulated useful assets faster than it accumulated data governance. The main recent failure was not ambition; it was allowing extraction shortcuts, join ambiguity, and experiment sprawl to outrun lineage discipline.

---

## 1. Short Chronology

### Phase A: Pre-SINR product vision

Core product split was established early and remains correct:

- Predictor = `what CAN grow here?`
- Recommender = `what SHOULD be planted here?`

Evidence:

- `species predictor discussions.md:11`
- `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_2.md:32`

The early system was not learned causal modeling. It was weighted habitat similarity:

- AlphaEarth embeddings as habitat signatures
- clustering / centroids / cosine similarity
- environmental envelopes and geospatial filters
- SAFE-B style recommendation overlays

This architecture was product-legible and fast, but had a ceiling on cultivated or ambiguous contexts.

### Phase B: Centroids -> multi-centroid -> k-NN

The product-side predictor improved by:

- moving from single centroids to multiple centroids,
- then to individual occurrence k-NN,
- while keeping recommendation as a separate layer.

Evidence:

- `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md:42`
- `treekipedia/backend/routes/prediction.js:587`

This was the right direction. It preserved the predictor/recommender distinction and made multi-modal habitats easier to represent.

### Phase C: v2 / v2.2 neural SINR line

The repo then introduced the first serious neural prediction line in `orchestrator/train_sinr_model.py`.

What v2.2 got right:

- hard cap per species (`HARD_CAP_PER_SPECIES = 50000`)
- assumed-negative loss with background loss
- explicit planted auxiliary signal
- species introduced/planted prior (`species_intro_ratio`)
- two-pass native / introduced inference with max aggregation
- relatively disciplined feature contract compared with later v3 sprawl

Evidence:

- `orchestrator/train_sinr_model.py:5`
- `orchestrator/train_sinr_model.py:138`
- `orchestrator/train_sinr_model.py:140`
- `orchestrator/location_predictor_FIXED.py:1709`

This is why v2.2 could sometimes do unusually well on radiata plantations: it had simpler but more coherent training-serving behavior.

### Phase D: v3 scale-up

v3 expanded scope aggressively:

- more GBIF rows,
- pre-2017 backfill,
- more environmental layers,
- all AlphaEarth years,
- land-state heuristics,
- introduced logic,
- auxiliary heads,
- more experiment variants.

This increased potential, but governance lagged behind expansion.

---

## 2. What Went Wrong In v3 Data

There were two distinct failure classes.

### Failure 1: raw feature extraction temporal collapse

Old sampler:

- `orchestrator/unified_gee_sampler_v3.py:475`
- `orchestrator/unified_gee_sampler_v3.py:490`

It deduplicated on pixel only and kept one retained year context. That means many valid multi-year observation contexts were never written into the old raw feature tables.

Confirmed by docs and live BQ behavior:

- `docs/SINR March 5 Codex.md:273`
- `docs/SINR March 5 Codex.md:278`
- `docs/SINR March 5 Codex.md:285`

Live cross-checks performed during this audit:

- source `gbif_new_occurrences` has `264,234` multi-year coordinates
- source `existing_training_coords` has `187,082` multi-year coordinates
- old `sinr_v3_features_new_gbif` has `0` multi-year coordinates
- old `sinr_v3_unified_strict_train_v30_preview_clean` has `0` multi-year coordinates by `(data_source, lat4, lon4)`
- current strict `sinr_v3_features_new_gbif_strict_full` has `123,920` multi-year coordinates

Conclusion: the preview train table is cleaner than legacy unified tables, but still inherits the old extraction collapse in its feature payload.

### Failure 2: consolidation / join corruption

Legacy consolidation then made things worse.

Main offenders:

- `orchestrator/consolidate_bq_v2.py`
- `orchestrator/compute_is_introduced_bq.py`

Key failure modes:

- coordinate-only or under-specified joins,
- omission of `observation_year` in backfill taxon assignment,
- append-based chunk resume without hard anti-dup guarantees,
- dangerous auxiliary joins on non-unique keys,
- catastrophic `sinr_v3_unified_v2_final` fanout.

The deleted `sinr_v3_unified_v2_final` was the clearest symptom, not the only bug.

---

## 3. Current Truth About The Data Estate

### Cleanest active raw feature table today

- `species_data.sinr_v3_features_new_gbif_strict_full`

Observed during this audit:

- rows: `5,676,884` at audit time; still increasing while extraction runs
- columns: `647`
- multi-year coordinates preserved: `123,920`
- null key rows on `(latitude, longitude, observation_year, emb_year)`: `0`

But it is not a training table.

It does **not** include critical labeled-training context like:

- `taxon_id`
- `data_source`
- `verification_status`
- `is_introduced`
- `tdwg_region`
- `land_state_class`

It also still has small raw duplicate pressure at context grain and therefore is not yet a finished master release by itself.

Why those fields are not trivially embedded into raw extraction:

- adding `data_source` and source-context provenance is easy and desirable,
- but adding `taxon_id` directly to raw strict feature rows is not always clean because raw extraction is context-grain while many source occurrence rows can map to the same `(lat4, lon4, observation_year)` context,
- during this audit, `gbif_new_occurrences` showed `1,862,126` coordinate-year contexts with more than one taxon,
- so label-bearing fields should usually live in a later assertion layer unless we intentionally materialize example-grain feature tables.

### Current safest training table today

- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`

What it does well:

- zero canonical duplicate groups on `(data_source, taxon_id, lat4, lon4, observation_year, emb_year)`
- zero temporal nulls
- all rows `verification_status = 'HIT'`
- no key carbon sentinel placeholders like `-9999`

What it still inherits:

- old feature extraction collapse for many multi-year coordinates
- preview-era compromises before strict-full rebuild completes

### What the strict program still needs

The strict extractor must finish both branches:

- `sinr_v3_features_new_gbif_strict_full`
- `sinr_v3_features_backfill_strict_full`

Then a brand-new strict unified training release must be built from those outputs with key-safe joins and explicit lineage.

---

## 4. Prediction vs Recommendation Product Architecture

The product architecture should remain split.

### Predictor

Question:

- `what is growing here now, or at a specific time of interest?`

Should be driven by:

- observed / inferred present vegetation,
- species likelihood at a place-time context,
- habitat evidence,
- uncertainty,
- and managed vs unmanaged context.

### Recommender

Question:

- `what should be planted here?`

Should be driven by:

- predictor output,
- nativity policy,
- disturbance / trajectory,
- recommendation profile,
- risk filters,
- diversity portfolio logic,
- restoration goals.

This split was correct in the original product vision and should not be collapsed back into one rank list.

Practical note:

- `what can grow here?` is often a recommendation-layer or management-layer question, not a pure predictor question.
- In Treekipedia terms, predictor should stay close to descriptive / inferential ecology, while recommender should answer intervention questions.

---

## 5. Master Dataset Strategy

We should stop thinking of one giant training table as the whole system. We need layers.

### Layer 1: Mutable canonical masters

These are the only tables that should reflect the latest corrected truth.

Recommended logical masters:

- `sinr_occurrence_master_v1`
- `sinr_feature_context_master_v1`
- `sinr_label_assertion_master_v1`
- `sinr_species_knowledge_master_v1`

These should be canonical, documented, and repairable.

### Layer 2: Immutable release tables

These should be created fresh for every material training or serving release.

Recommended examples:

- `sinr_feature_release_new_gbif__YYYY_MM_DD`
- `sinr_feature_release_backfill__YYYY_MM_DD`
- `sinr_train_release__YYYY_MM_DD`
- `sinr_serving_release__YYYY_MM_DD`
- `species_knowledge_release__YYYY_MM_DD`

### Layer 3: Contracts and manifests

Every release must point to:

- mapping contract
- feature contract
- split contract
- schema contract
- lineage manifest
- code revision

This is how we stop future drift.

---

## 6. Proposed One Source of Truth Model

### For raw features

Canonical future raw sources:

- `sinr_v3_features_new_gbif_strict_full`
- `sinr_v3_features_backfill_strict_full`

Not canonical:

- `sinr_v3_features_new_gbif`
- `sinr_v3_features_backfill`

### For training

Current temporary source of truth:

- `sinr_v3_unified_strict_train_v30_preview_clean`

Future canonical source of truth:

- a new strict-full unified training release built only from strict feature outputs

### For species knowledge

Current repo has schema knowledge spread across Treekipedia docs and database schema files. We need one release-oriented species knowledge contract with:

- taxonomy version
- nativity / introduced status provenance
- trait / stewardship provenance
- schema version
- release id

---

## 7. Practical Near-Term Plan

### Do now

- finish strict extraction for `new_gbif`
- start / finish strict extraction for `backfill`
- formalize master dataset and release naming
- document species knowledge release schema
- keep current preview train table for local experimentation only

### Do next

- create first strict-full unified train release from strict raw outputs
- create release manifest + validation report alongside it
- redirect training defaults to strict-full release

### Do not do yet

- do not delete more legacy tables until retention matrix is reviewed
- do not treat current preview-clean table as final canonical truth
- do not train from old `unified_v1` / `unified_v2`

---

## 8. Files Created In This Governance Push

- `docs/SINR BigQuery Lineage Map.md`
- `docs/SINR Master Dataset v1 README.md`
- `orchestrator/sql/sinr_master_dataset_v1/README.md`
- `orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql`

---

## 9. Related Beads Issues

- `treekipedia-xi6` - forensic audit SINR data lineage and master dataset
- `treekipedia-cz6` - design SINR master dataset v1
- `treekipedia-csc` - rebuild strict-full unified training table from strict feature outputs
- `treekipedia-qhs` - version species knowledge schema and releases
- `treekipedia-9bw` - plan legacy SINR table retirement and archive policy

---

## 10. Hard Conclusions

- v2.2 was not magic; it was simpler and more coherent.
- v3 gained capability but let data lineage discipline slip.
- current preview training is useful, but not the final master training truth.
- current strict `new_gbif` raw extraction is the cleanest active feature asset we have for that branch.
- the final master dataset must be built from strict outputs for both branches plus explicit manifests and contracts.
