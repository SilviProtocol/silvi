# SINR Master Dataset v1 README

Status: design document, not yet executed in BigQuery
Owner issue: `treekipedia-cz6`

## Goal

Define the first disciplined master-data layout for SINR prediction and recommendation so we can:

- stop training from ambiguous legacy tables,
- preserve raw extraction lineage,
- fork immutable releases for training and serving,
- version species knowledge and nativity logic,
- and retire legacy assets safely later.

## Design Principles

- No destructive mutation of legacy tables.
- Canonical mutable masters for curation.
- Immutable release tables for training and serving.
- Explicit lineage manifests and contracts.
- Separate predictor data products from recommender data products.

## Recommended BigQuery Layout

### Canonical masters

- `species_data.sinr_occurrence_master_v1`
- `species_data.sinr_feature_context_master_v1`
- `species_data.sinr_label_assertion_master_v1`
- `species_data.species_knowledge_master_v1`

### Immutable releases

- `species_data.sinr_feature_release_new_gbif__YYYY_MM_DD`
- `species_data.sinr_feature_release_backfill__YYYY_MM_DD`
- `species_data.sinr_train_release__YYYY_MM_DD`
- `species_data.sinr_serving_release__YYYY_MM_DD`
- `species_data.species_knowledge_release__YYYY_MM_DD`

### Registry / manifests

- `species_data.sinr_release_registry_v1`
- `species_data.sinr_schema_contract_registry_v1`
- `species_data.sinr_feature_contract_registry_v1`
- `species_data.sinr_split_contract_registry_v1`

## Minimum Keys

### Occurrence grain

- `source_record_id`
- `data_source`
- `taxon_id`
- `latitude`
- `longitude`
- `observation_year`

### Feature context grain

- `lat4`
- `lon4`
- `observation_year`
- `emb_year`
- `feature_context_id`

### Training example grain

- `data_source`
- `taxon_id`
- `lat4`
- `lon4`
- `observation_year`
- `emb_year`
- `release_id`

## What Goes In Each Master

### `sinr_occurrence_master_v1`

Holds occurrence facts and canonical taxon mapping.

Suggested fields:

- source ids and provenance
- original coordinates and rounded coordinates
- observation date / year
- canonical taxon id
- taxonomic version
- establishment means / managed context if known

### `sinr_feature_context_master_v1`

Holds one row per strict feature context.

Suggested fields:

- `(lat4, lon4, observation_year, emb_year)`
- raw GEE / AlphaEarth / environmental features
- extraction provenance
- quality flags
- unsampleable / retry metadata

Important design choice:

- raw feature context tables should include enough provenance to rejoin safely later,
- but they should stay at context grain, not duplicated out to species-example grain.
- So fields like `data_source`, `source_record_id`, `lat4`, `lon4`, `observation_year`, and `emb_year` should be carried in or joinable from raw outputs.
- Fields like `taxon_id`, `is_introduced`, or `land_state_class` generally belong in label / assertion layers unless the raw table is explicitly promoted to example grain.

Why this matters:

- one strict feature context can correspond to more than one species occurrence,
- and duplicating taxon-linked labels directly into raw feature extraction tables would blur the boundary between context extraction and labeled training assembly.

### `sinr_label_assertion_master_v1`

Holds derived labels and metadata used by prediction and recommendation.

Suggested fields:

- `taxon_id`
- `feature_context_id`
- `verification_status`
- `verification_source`
- `is_introduced`
- `tdwg_region`
- `land_state_class`
- other auxiliary labels with provenance

### `species_knowledge_master_v1`

Holds versioned species knowledge used across products.

Suggested fields:

- `taxon_id`
- taxonomy fields
- native / introduced evidence and provenance
- stewardship / traits / use fields
- schema version
- source release ids

## What The New Master Dataset Must Fix

- no pixel-only temporal collapse
- no ambiguous coordinate-only taxon assignment
- no hidden sentinel placeholders like `-9999`
- no silent train/serve feature mismatch
- no release without a manifest

## Validation Gates

Every release should fail publication if any of these fail:

- canonical uniqueness
- key null checks
- year integrity checks
- feature range checks
- duplicate context checks
- split leakage checks
- contract completeness

## Relationship To Current Tables

### Current temporary training source

- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`

### Current strict raw sources

- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_features_backfill_strict_full` (to be completed / created)

### Legacy sources to preserve but not promote

- `species_data.sinr_v3_features_new_gbif`
- `species_data.sinr_v3_features_backfill`
- `species_data.sinr_v3_unified_v1`
- `species_data.sinr_v3_unified_v2`

## Prediction vs Recommendation Forks

### Predictor release

Used for:

- `what can grow here?`
- species ranking
- suitability / uncertainty

Should be as ecological and evidence-based as possible.

### Recommender release

Used for:

- `what should be planted here?`
- profile- and policy-aware ranking
- restoration vs agroforestry vs plantation pathways

Should fork from predictor-safe releases plus policy / risk / goal layers.

## Recommended Next Build Step

When approved, create the registry tables and first immutable release tables using the SQL blueprint in:

- `orchestrator/sql/sinr_master_dataset_v1/master_dataset_blueprint.sql`

Current implemented step beyond the blueprint:

- `orchestrator/build_sinr_strict_only_release.py`
- documented in `docs/SINR Strict-Only Release Builder.md`

Fail-closed hybrid governance scaffolding now also exists:

- `orchestrator/build_sinr_hybrid_override_system.py`
- documented in `docs/SINR Hybrid Override System.md`

Hybrid train-only release builder now also exists:

- `orchestrator/build_sinr_hybrid_train_release.py`
- documented in `docs/SINR Hybrid Train-Only Release Builder.md`

This is an enforced `strict_only` release path, not yet a full canonical strict release system.
