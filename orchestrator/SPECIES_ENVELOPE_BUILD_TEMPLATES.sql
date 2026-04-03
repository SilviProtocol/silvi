-- SPECIES ENVIRONMENTAL ENVELOPE: BigQuery BUILD TEMPLATES
-- Date: 2026-03-17
-- Purpose: SQL templates for building species_environmental_envelope_v1 table
-- Source: sinr_v41_preview_strict_core_train_v1 (11.92M rows)

-- ===========================================================================
-- TEMPLATE 1: Lightweight Prototype (Green Features Only, 3 Quantiles)
-- ===========================================================================
-- Build time: ~3-5 minutes
-- Columns: ~135 (45 features × 3 quantiles: p10, p50, p90)
-- Rationale: Quick validation of aggregation logic before full build

CREATE TABLE `treekipedia-479918.species_data.species_environmental_envelope_v1_prototype` AS
WITH base_stats AS (
  SELECT
    taxon_id,
    -- Metadata
    COUNT(*) AS num_rows_total,
    COUNTIF(is_introduced = 0) AS num_rows_native,
    COUNTIF(is_introduced = 1) AS num_rows_introduced,
    COUNTIF(is_introduced IS NULL) AS num_rows_unknown_intro,
    SAFE_DIVIDE(
      COUNTIF(is_introduced = 1),
      COUNTIF(is_introduced IN (0, 1))
    ) AS introduced_ratio,

    -- Temporal
    MIN(observation_year) AS observation_year_min,
    MAX(observation_year) AS observation_year_max,
    APPROX_QUANTILES(observation_year, 100)[OFFSET(50)] AS observation_year_median,
    COUNTIF(observation_year < 2001) AS num_obs_pre_2001,

    -- Geographic
    AVG(latitude) AS centroid_latitude,
    AVG(longitude) AS centroid_longitude,
    MIN(latitude) AS latitude_min,
    MAX(latitude) AS latitude_max,
    MIN(longitude) AS longitude_min,
    MAX(longitude) AS longitude_max,

    -- TERRAIN (GREEN) - 7 features × 3 quantiles = 21 cols
    APPROX_QUANTILES(elevation, 100)[OFFSET(10)] AS elevation_p10,
    APPROX_QUANTILES(elevation, 100)[OFFSET(50)] AS elevation_p50,
    APPROX_QUANTILES(elevation, 100)[OFFSET(90)] AS elevation_p90,
    APPROX_QUANTILES(slope, 100)[OFFSET(10)] AS slope_p10,
    APPROX_QUANTILES(slope, 100)[OFFSET(50)] AS slope_p50,
    APPROX_QUANTILES(slope, 100)[OFFSET(90)] AS slope_p90,
    APPROX_QUANTILES(aspect, 100)[OFFSET(10)] AS aspect_p10,
    APPROX_QUANTILES(aspect, 100)[OFFSET(50)] AS aspect_p50,
    APPROX_QUANTILES(aspect, 100)[OFFSET(90)] AS aspect_p90,
    APPROX_QUANTILES(hillshade, 100)[OFFSET(10)] AS hillshade_p10,
    APPROX_QUANTILES(hillshade, 100)[OFFSET(50)] AS hillshade_p50,
    APPROX_QUANTILES(hillshade, 100)[OFFSET(90)] AS hillshade_p90,
    APPROX_QUANTILES(topo_diversity, 100)[OFFSET(10)] AS topo_diversity_p10,
    APPROX_QUANTILES(topo_diversity, 100)[OFFSET(50)] AS topo_diversity_p50,
    APPROX_QUANTILES(topo_diversity, 100)[OFFSET(90)] AS topo_diversity_p90,
    APPROX_QUANTILES(merit_hand_m, 100)[OFFSET(10)] AS merit_hand_m_p10,
    APPROX_QUANTILES(merit_hand_m, 100)[OFFSET(50)] AS merit_hand_m_p50,
    APPROX_QUANTILES(merit_hand_m, 100)[OFFSET(90)] AS merit_hand_m_p90,
    APPROX_QUANTILES(merit_upstream_area_km2, 100)[OFFSET(10)] AS merit_upstream_area_km2_p10,
    APPROX_QUANTILES(merit_upstream_area_km2, 100)[OFFSET(50)] AS merit_upstream_area_km2_p50,
    APPROX_QUANTILES(merit_upstream_area_km2, 100)[OFFSET(90)] AS merit_upstream_area_km2_p90,

    -- CLIMATE (BIO) (YELLOW) - 19 features × 3 quantiles = 57 cols
    APPROX_QUANTILES(bio01, 100)[OFFSET(10)] AS bio01_p10,
    APPROX_QUANTILES(bio01, 100)[OFFSET(50)] AS bio01_p50,
    APPROX_QUANTILES(bio01, 100)[OFFSET(90)] AS bio01_p90,
    APPROX_QUANTILES(bio02, 100)[OFFSET(10)] AS bio02_p10,
    APPROX_QUANTILES(bio02, 100)[OFFSET(50)] AS bio02_p50,
    APPROX_QUANTILES(bio02, 100)[OFFSET(90)] AS bio02_p90,
    APPROX_QUANTILES(bio03, 100)[OFFSET(10)] AS bio03_p10,
    APPROX_QUANTILES(bio03, 100)[OFFSET(50)] AS bio03_p50,
    APPROX_QUANTILES(bio03, 100)[OFFSET(90)] AS bio03_p90,
    APPROX_QUANTILES(bio04, 100)[OFFSET(10)] AS bio04_p10,
    APPROX_QUANTILES(bio04, 100)[OFFSET(50)] AS bio04_p50,
    APPROX_QUANTILES(bio04, 100)[OFFSET(90)] AS bio04_p90,
    APPROX_QUANTILES(bio05, 100)[OFFSET(10)] AS bio05_p10,
    APPROX_QUANTILES(bio05, 100)[OFFSET(50)] AS bio05_p50,
    APPROX_QUANTILES(bio05, 100)[OFFSET(90)] AS bio05_p90,
    APPROX_QUANTILES(bio06, 100)[OFFSET(10)] AS bio06_p10,
    APPROX_QUANTILES(bio06, 100)[OFFSET(50)] AS bio06_p50,
    APPROX_QUANTILES(bio06, 100)[OFFSET(90)] AS bio06_p90,
    APPROX_QUANTILES(bio07, 100)[OFFSET(10)] AS bio07_p10,
    APPROX_QUANTILES(bio07, 100)[OFFSET(50)] AS bio07_p50,
    APPROX_QUANTILES(bio07, 100)[OFFSET(90)] AS bio07_p90,
    APPROX_QUANTILES(bio08, 100)[OFFSET(10)] AS bio08_p10,
    APPROX_QUANTILES(bio08, 100)[OFFSET(50)] AS bio08_p50,
    APPROX_QUANTILES(bio08, 100)[OFFSET(90)] AS bio08_p90,
    APPROX_QUANTILES(bio09, 100)[OFFSET(10)] AS bio09_p10,
    APPROX_QUANTILES(bio09, 100)[OFFSET(50)] AS bio09_p50,
    APPROX_QUANTILES(bio09, 100)[OFFSET(90)] AS bio09_p90,
    APPROX_QUANTILES(bio10, 100)[OFFSET(10)] AS bio10_p10,
    APPROX_QUANTILES(bio10, 100)[OFFSET(50)] AS bio10_p50,
    APPROX_QUANTILES(bio10, 100)[OFFSET(90)] AS bio10_p90,
    APPROX_QUANTILES(bio11, 100)[OFFSET(10)] AS bio11_p10,
    APPROX_QUANTILES(bio11, 100)[OFFSET(50)] AS bio11_p50,
    APPROX_QUANTILES(bio11, 100)[OFFSET(90)] AS bio11_p90,
    APPROX_QUANTILES(bio12, 100)[OFFSET(10)] AS bio12_p10,
    APPROX_QUANTILES(bio12, 100)[OFFSET(50)] AS bio12_p50,
    APPROX_QUANTILES(bio12, 100)[OFFSET(90)] AS bio12_p90,
    APPROX_QUANTILES(bio13, 100)[OFFSET(10)] AS bio13_p10,
    APPROX_QUANTILES(bio13, 100)[OFFSET(50)] AS bio13_p50,
    APPROX_QUANTILES(bio13, 100)[OFFSET(90)] AS bio13_p90,
    APPROX_QUANTILES(bio14, 100)[OFFSET(10)] AS bio14_p10,
    APPROX_QUANTILES(bio14, 100)[OFFSET(50)] AS bio14_p50,
    APPROX_QUANTILES(bio14, 100)[OFFSET(90)] AS bio14_p90,
    APPROX_QUANTILES(bio15, 100)[OFFSET(10)] AS bio15_p10,
    APPROX_QUANTILES(bio15, 100)[OFFSET(50)] AS bio15_p50,
    APPROX_QUANTILES(bio15, 100)[OFFSET(90)] AS bio15_p90,
    APPROX_QUANTILES(bio16, 100)[OFFSET(10)] AS bio16_p10,
    APPROX_QUANTILES(bio16, 100)[OFFSET(50)] AS bio16_p50,
    APPROX_QUANTILES(bio16, 100)[OFFSET(90)] AS bio16_p90,
    APPROX_QUANTILES(bio17, 100)[OFFSET(10)] AS bio17_p10,
    APPROX_QUANTILES(bio17, 100)[OFFSET(50)] AS bio17_p50,
    APPROX_QUANTILES(bio17, 100)[OFFSET(90)] AS bio17_p90,
    APPROX_QUANTILES(bio18, 100)[OFFSET(10)] AS bio18_p10,
    APPROX_QUANTILES(bio18, 100)[OFFSET(50)] AS bio18_p50,
    APPROX_QUANTILES(bio18, 100)[OFFSET(90)] AS bio18_p90,
    APPROX_QUANTILES(bio19, 100)[OFFSET(10)] AS bio19_p10,
    APPROX_QUANTILES(bio19, 100)[OFFSET(50)] AS bio19_p50,
    APPROX_QUANTILES(bio19, 100)[OFFSET(90)] AS bio19_p90,

    CURRENT_TIMESTAMP() AS derived_at

  FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
  WHERE taxon_id IS NOT NULL
  GROUP BY taxon_id
)
SELECT
  * EXCEPT(num_obs_pre_2001),
  CASE
    WHEN num_obs_pre_2001::float64 / num_rows_total < 0.1 THEN "green"
    WHEN num_obs_pre_2001::float64 / num_rows_total < 0.5 THEN "yellow"
    ELSE "red"
  END AS confidence_level
FROM base_stats
ORDER BY num_rows_total DESC;


-- ===========================================================================
-- TEMPLATE 2: Full Production Table (All 55 Env Features, 5 Quantiles Each)
-- ===========================================================================
-- Build time: ~10-15 minutes
-- Columns: ~275 (55 features × 5 quantiles + metadata)
-- To use: Copy the base_stats CTE from above and add columns for:
-- - soil_ph, soil_clay_pct, soil_sand_pct, soil_organic_carbon, soil_bulk_density, soil_water_content
-- - water_occurrence, water_recurrence, water_seasonality
-- - jrc_tmf_status, jrc_tmf_degrad_year
-- - treecover2000, lossyear
-- - biomass_agb_mgha
-- - esa_worldcover_2021, dynamic_world, sbtn_natural_land, neumann_natural_prob
-- - tc_vpd_mean, tc_vpd_delta, tc_aet_mean, tc_soil_moisture_mean, tc_pdsi_mean, tc_water_deficit_mean, tc_solar_rad_mean
-- - modis_gpp_mean, nighttime_lights, fire_frequency_count, human_modification
--
-- Pattern (repeat for each feature):
--   APPROX_QUANTILES(feature_name, 100)[OFFSET(10)] AS feature_name_p10,
--   APPROX_QUANTILES(feature_name, 100)[OFFSET(25)] AS feature_name_p25,
--   APPROX_QUANTILES(feature_name, 100)[OFFSET(50)] AS feature_name_p50,
--   APPROX_QUANTILES(feature_name, 100)[OFFSET(75)] AS feature_name_p75,
--   APPROX_QUANTILES(feature_name, 100)[OFFSET(90)] AS feature_name_p90,

-- ===========================================================================
-- TEMPLATE 3: Validate Aggregation Results (Sanity Checks)
-- ===========================================================================

SELECT
  taxon_id,
  num_rows_total,
  confidence_level,
  observation_year_min,
  observation_year_max,
  centroid_latitude,
  centroid_longitude,
  -- Sanity check: p10 should be <= p50 <= p90 for each feature
  CASE
    WHEN elevation_p10 > elevation_p50 OR elevation_p50 > elevation_p90 THEN "ERROR"
    WHEN elevation_p90 - elevation_p10 < 1 THEN "WARNING: narrow range"
    ELSE "OK"
  END AS elevation_check,
  CASE
    WHEN bio01_p10 > bio01_p50 OR bio01_p50 > bio01_p90 THEN "ERROR"
    WHEN bio01_p90 - bio01_p10 < 10 THEN "WARNING: narrow range"
    ELSE "OK"
  END AS bio01_check
FROM `treekipedia-479918.species_data.species_environmental_envelope_v1_prototype`
WHERE num_rows_total < 10  -- species with very few observations
ORDER BY num_rows_total ASC;


-- ===========================================================================
-- TEMPLATE 4: Categorical Feature Aggregation (Xiao Planted Forest Example)
-- ===========================================================================

CREATE TEMP TABLE categorical_agg AS
SELECT
  taxon_id,
  xiao_planted_forest,
  COUNT(*) AS count
FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
WHERE taxon_id IS NOT NULL AND xiao_planted_forest IS NOT NULL
GROUP BY taxon_id, xiao_planted_forest;

SELECT
  taxon_id,
  ARRAY_AGG(STRUCT(
    xiao_planted_forest AS class,
    ROUND(100.0 * count / SUM(count) OVER (PARTITION BY taxon_id), 1) AS pct
  ) ORDER BY count DESC) AS xiao_distribution
FROM categorical_agg
GROUP BY taxon_id;


-- ===========================================================================
-- TEMPLATE 5: AlphaEarth Embedding Statistics (Mean/Std Per Dimension)
-- ===========================================================================
-- Challenge: ae_emb_0 through ae_emb_63 are separate columns
-- Solution: Unnest into (dim, value) pairs, aggregate, re-nest

CREATE TEMP TABLE ae_embeddings_unnested AS
SELECT
  taxon_id,
  -- Manually unnest all 64 dimensions
  -- OR use UNION ALL pattern:
  0 AS dim, ae_emb_0 AS value FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
  UNION ALL
  SELECT taxon_id, 1, ae_emb_1 FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
  -- ... repeat for ae_emb_2 through ae_emb_63
  -- (NOTE: This is verbose; consider Python script for generation)
WHERE taxon_id IS NOT NULL;

SELECT
  taxon_id,
  ARRAY_AGG(STRUCT(
    dim,
    ROUND(AVG(value), 6) AS mean,
    ROUND(STDDEV(value), 6) AS std
  ) ORDER BY dim) AS ae_embedding_stats
FROM ae_embeddings_unnested
GROUP BY taxon_id;


-- ===========================================================================
-- TEMPLATE 6: Data Quality Check - Null Tracking
-- ===========================================================================

SELECT
  taxon_id,
  num_rows_total,
  COUNTIF(elevation IS NULL) AS null_elevation,
  COUNTIF(bio01 IS NULL) AS null_bio01,
  COUNTIF(soil_ph IS NULL) AS null_soil_ph,
  COUNTIF(modis_gpp_mean IS NULL) AS null_modis_gpp_mean,
  COUNTIF(nighttime_lights IS NULL) AS null_nighttime_lights,
  -- Compute null percentage for key features
  ROUND(100.0 * COUNTIF(elevation IS NULL) / num_rows_total, 1) AS null_pct_elevation,
  ROUND(100.0 * COUNTIF(bio01 IS NULL) / num_rows_total, 1) AS null_pct_bio01
FROM (
  SELECT
    taxon_id,
    COUNT(*) AS num_rows_total,
    * EXCEPT(taxon_id)
  FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
  GROUP BY taxon_id
)
WHERE null_pct_elevation > 5 OR null_pct_bio01 > 5  -- flag species with >5% nulls
ORDER BY null_pct_elevation DESC;


-- ===========================================================================
-- TEMPLATE 7: TDWG Region Membership (Spatial Join)
-- ===========================================================================
-- WARNING: This spatial join is slow (~10+ minutes on full 11.92M rows)
-- Consider running separately and joining results

SELECT
  train.taxon_id,
  ARRAY_AGG(DISTINCT tdwg.LEVEL3_COD IGNORE NULLS) AS tdwg_regions
FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1` train
LEFT JOIN `treekipedia-479918.species_data.tdwg_level3` tdwg
  ON ST_CONTAINS(tdwg.geometry, ST_GEOGPOINT(train.longitude, train.latitude))
WHERE train.taxon_id IS NOT NULL
GROUP BY train.taxon_id;

-- Alternative (faster): Use pre-computed TDWG frequency contract instead
-- (See build_tdwg_frequency_contract.py for how to build)
-- Then extract region list from: SELECT array_agg(tdwg_code) FROM tdwg_freq_contract


-- ===========================================================================
-- TEMPLATE 8: Versioning & Lineage
-- ===========================================================================

CREATE TABLE `treekipedia-479918.species_data.species_envelope_metadata` (
  version STRING,
  build_timestamp TIMESTAMP,
  source_table STRING,
  num_species INT64,
  total_rows_processed INT64,
  query_bytes_scanned INT64,
  query_bytes_billed INT64,
  build_duration_minutes INT64,
  notes STRING
);

INSERT INTO `treekipedia-479918.species_data.species_envelope_metadata`
VALUES (
  "v1_prototype",
  CURRENT_TIMESTAMP(),
  "sinr_v41_preview_strict_core_train_v1",
  19043,
  11920314,
  NULL,  -- Fill after query completes
  NULL,
  NULL,
  "Initial prototype with green features + 3 quantiles"
);
