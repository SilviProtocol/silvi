-- SINR occurrence-grain salvage blueprint
-- Status: design only, not executed
-- Purpose: define the occurrence-first audit and salvage flow.

-- ---------------------------------------------------------------------------
-- 1) Occurrence-first audit base
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_audit_base_v1` AS
SELECT
  o.occurrenceID AS source_record_id,
  'occurrences' AS source_system,
  o.taxon_id,
  o.decimalLatitude AS latitude,
  o.decimalLongitude AS longitude,
  ROUND(o.decimalLatitude, 4) AS lat4,
  ROUND(o.decimalLongitude, 4) AS lon4,
  o.observation_year,
  o.emb_year,
  NULL AS coordinate_uncertainty_m,
  NULL AS establishment_means
FROM `treekipedia-479918.species_data.occurrences` o
WHERE o.taxon_id IS NOT NULL
  AND o.observation_year IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2) Exact strict context match
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_strict_match_v1` AS
SELECT
  a.*,
  CASE WHEN f.lat4 IS NOT NULL THEN TRUE ELSE FALSE END AS has_strict_context
FROM `treekipedia-479918.species_data.sinr_occurrence_audit_base_v1` a
LEFT JOIN (
  SELECT
    'new_gbif' AS data_source,
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    emb_year
  FROM `treekipedia-479918.species_data.sinr_v3_features_new_gbif_strict_full`
  UNION ALL
  SELECT
    'backfill' AS data_source,
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    emb_year
  FROM `treekipedia-479918.species_data.sinr_v3_features_backfill_strict_full`
) f
  ON a.lat4 = f.lat4
 AND a.lon4 = f.lon4
 AND a.observation_year = f.observation_year
 AND a.emb_year = f.emb_year;

-- ---------------------------------------------------------------------------
-- 3) Legacy match summary
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_legacy_match_v1` AS
WITH legacy_contexts AS (
  SELECT ROUND(latitude, 4) AS lat4, ROUND(longitude, 4) AS lon4, observation_year, emb_year
  FROM `treekipedia-479918.species_data.sinr_v3_features_new_gbif`
  UNION ALL
  SELECT ROUND(latitude, 4) AS lat4, ROUND(longitude, 4) AS lon4, observation_year, emb_year
  FROM `treekipedia-479918.species_data.sinr_v3_features_backfill`
)
SELECT
  a.*,
  CASE WHEN l.lat4 IS NOT NULL THEN TRUE ELSE FALSE END AS has_legacy_context
FROM `treekipedia-479918.species_data.sinr_occurrence_audit_base_v1` a
LEFT JOIN legacy_contexts l
  ON a.lat4 = l.lat4
 AND a.lon4 = l.lon4
 AND a.observation_year = l.observation_year
 AND a.emb_year = l.emb_year;

-- ---------------------------------------------------------------------------
-- 4) Suggested salvage classification skeleton
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_salvage_status_v1` AS
SELECT
  a.*,
  s.has_strict_context,
  l.has_legacy_context,
  CASE
    WHEN s.has_strict_context THEN 'strict_context_present'
    WHEN NOT s.has_strict_context AND l.has_legacy_context THEN 'legacy_unverified'
    ELSE 'needs_reextract'
  END AS context_quality_status
FROM `treekipedia-479918.species_data.sinr_occurrence_audit_base_v1` a
LEFT JOIN `treekipedia-479918.species_data.sinr_occurrence_strict_match_v1` s
  USING (source_record_id, source_system, taxon_id, latitude, longitude, lat4, lon4, observation_year, emb_year, coordinate_uncertainty_m, establishment_means)
LEFT JOIN `treekipedia-479918.species_data.sinr_occurrence_legacy_match_v1` l
  USING (source_record_id, source_system, taxon_id, latitude, longitude, lat4, lon4, observation_year, emb_year, coordinate_uncertainty_m, establishment_means);

-- ---------------------------------------------------------------------------
-- 5) Randomized audit sample skeleton
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_salvage_audit_sample_v1` AS
SELECT *
FROM `treekipedia-479918.species_data.sinr_occurrence_salvage_status_v1`
QUALIFY ROW_NUMBER() OVER (PARTITION BY context_quality_status ORDER BY RAND()) <= 1000;

-- End blueprint.
