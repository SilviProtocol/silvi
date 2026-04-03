-- SINR master dataset v1 blueprint
-- Status: design only, not yet executed
-- Purpose: create new canonical and release-oriented tables without mutating legacy assets.

-- ---------------------------------------------------------------------------
-- 1) Release registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_release_registry_v1` (
  release_id STRING,
  release_type STRING,
  bq_table STRING,
  status STRING,
  created_at TIMESTAMP,
  source_tables ARRAY<STRING>,
  schema_contract_version STRING,
  feature_contract_version STRING,
  split_contract_version STRING,
  mapping_contract_version STRING,
  notes STRING
);

-- ---------------------------------------------------------------------------
-- 2) Canonical occurrence master
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_master_v1` AS
SELECT
  o.gbifID AS source_record_id,
  'gbif_occurrences' AS source_system,
  o.taxon_id,
  o.decimalLatitude AS latitude,
  o.decimalLongitude AS longitude,
  ROUND(o.decimalLatitude, 4) AS lat4,
  ROUND(o.decimalLongitude, 4) AS lon4,
  o.observation_year,
  CURRENT_TIMESTAMP() AS ingested_at
FROM `treekipedia-479918.species_data.occurrences` o
WHERE o.taxon_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3) Canonical strict feature context master
-- ---------------------------------------------------------------------------
-- This should be populated only from strict feature outputs.
-- New GBIF and backfill branches are unioned at exact context grain.

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_feature_context_master_v1` AS
WITH new_gbif AS (
  SELECT
    'new_gbif' AS data_source,
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    emb_year,
    * EXCEPT(latitude, longitude, observation_year, emb_year)
  FROM `treekipedia-479918.species_data.sinr_v3_features_new_gbif_strict_full`
),
backfill AS (
  SELECT
    'backfill' AS data_source,
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    emb_year,
    * EXCEPT(latitude, longitude, observation_year, emb_year)
  FROM `treekipedia-479918.species_data.sinr_v3_features_backfill_strict_full`
)
SELECT * FROM new_gbif
UNION ALL
SELECT * FROM backfill;

-- ---------------------------------------------------------------------------
-- 4) Label assertion master
-- ---------------------------------------------------------------------------
-- Placeholder shape. This should be rebuilt from strict HIT logic and
-- key-safe auxiliary joins, not copied from legacy unified tables.

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_label_assertion_master_v1` (
  data_source STRING,
  taxon_id STRING,
  lat4 FLOAT64,
  lon4 FLOAT64,
  observation_year INT64,
  emb_year INT64,
  verification_status STRING,
  verification_source STRING,
  is_introduced FLOAT64,
  tdwg_region STRING,
  land_state_class INT64,
  disturbance_intensity FLOAT64,
  forest_stability FLOAT64,
  successional_stage INT64,
  created_at TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 5) First immutable train release (shape only)
-- ---------------------------------------------------------------------------
-- Replace the source CTEs with approved strict joins before execution.

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_train_release__TEMPLATE` AS
SELECT
  l.data_source,
  l.taxon_id,
  l.lat4,
  l.lon4,
  l.observation_year,
  l.emb_year,
  l.verification_status,
  l.verification_source,
  l.is_introduced,
  l.tdwg_region,
  l.land_state_class,
  f.* EXCEPT(data_source, lat4, lon4, observation_year, emb_year)
FROM `treekipedia-479918.species_data.sinr_label_assertion_master_v1` l
JOIN `treekipedia-479918.species_data.sinr_feature_context_master_v1` f
  ON l.data_source = f.data_source
 AND l.lat4 = f.lat4
 AND l.lon4 = f.lon4
 AND l.observation_year = f.observation_year
 AND l.emb_year = f.emb_year;

-- ---------------------------------------------------------------------------
-- 6) Species knowledge master (shape only)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.species_knowledge_master_v1` (
  taxon_id STRING,
  species_scientific_name STRING,
  family STRING,
  genus STRING,
  wcvp_native STRING,
  wcvp_introduced STRING,
  verification_status STRING,
  schema_version STRING,
  release_id STRING,
  created_at TIMESTAMP
);

-- End blueprint.

-- Note:
-- A first enforced implementation now exists outside this blueprint:
--   orchestrator/build_sinr_strict_only_release.py
-- It creates strict-only preview-backed release tables using
--   release_gate_default = 'allow_strict_release'
-- and explicitly nulls preview-only feature families without strict raw provenance.
