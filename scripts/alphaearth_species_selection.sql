-- AlphaEarth Pilot: Species Selection SQL Implementation
-- Version: 1.0
-- Date: 2025-10-27
-- Purpose: Select 100 strategically-chosen tree species for testing AlphaEarth embeddings

-- ==============================================================================
-- STEP 1: CREATE CANDIDATE SPECIES TABLE
-- ==============================================================================

-- This creates a temporary table with all species that meet basic criteria:
-- - Species-level records only (no subspecies)
-- - Have ecoregion and biome data
-- - Have taxonomic information

DROP TABLE IF EXISTS candidate_species CASCADE;

CREATE TABLE candidate_species AS
SELECT
    s.taxon_id,
    s.species_scientific_name,
    s.family,
    s.genus,
    s.present_intact_forest,
    s.ecoregions,
    s.biomes,
    s.countries_native,

    -- Calculate niche breadth (number of ecoregions)
    CASE
        WHEN s.ecoregions = 'NA' OR s.ecoregions IS NULL THEN 0
        ELSE array_length(string_to_array(s.ecoregions, ','), 1)
    END as num_ecoregions,

    -- Calculate geographic breadth (number of countries)
    CASE
        WHEN s.countries_native = 'NA' OR s.countries_native IS NULL THEN 0
        ELSE array_length(string_to_array(s.countries_native, ','), 1)
    END as num_countries,

    -- Extract dominant biome for stratification
    CASE
        WHEN s.biomes LIKE '%Tropical & Subtropical Moist Broadleaf%' THEN 'Tropical Moist'
        WHEN s.biomes LIKE '%Temperate Broadleaf%' THEN 'Temperate Broadleaf'
        WHEN s.biomes LIKE '%Boreal%' THEN 'Boreal'
        WHEN s.biomes LIKE '%Tropical & Subtropical Dry%' THEN 'Tropical Dry'
        WHEN s.biomes LIKE '%Mediterranean%' THEN 'Mediterranean'
        WHEN s.biomes LIKE '%Montane Grasslands%' THEN 'Montane'
        WHEN s.biomes LIKE '%Mangroves%' THEN 'Mangroves'
        WHEN s.biomes LIKE '%Deserts%' THEN 'Desert'
        WHEN s.biomes LIKE '%Temperate Conifer%' THEN 'Temperate Conifer'
        ELSE 'Other'
    END as dominant_biome,

    -- Placeholder for occurrence count (will be filled in next step)
    0::integer as tile_count

FROM species s
WHERE s.subspecies = 'NA'
    AND s.family IS NOT NULL
    AND s.ecoregions IS NOT NULL
    AND s.ecoregions != 'NA';

-- Add index for faster lookups
CREATE INDEX idx_candidate_taxon ON candidate_species(taxon_id);

SELECT COUNT(*) as candidate_pool_size FROM candidate_species;

-- ==============================================================================
-- STEP 2: ADD OCCURRENCE COUNTS (SLOW - WILL TAKE 10-30 MINUTES)
-- ==============================================================================

-- Note: This query can take a long time due to JSONB key checks across millions of tiles
-- Consider running overnight or in background

-- Option A: Direct update (slow but accurate)
/*
UPDATE candidate_species cs
SET tile_count = (
    SELECT COUNT(*)
    FROM geohash_species_tiles g
    WHERE g.species_data ? cs.taxon_id
);
*/

-- Option B: Faster approach using materialized view (recommended)
-- First create a summary of occurrence counts

DROP TABLE IF EXISTS species_occurrence_counts;

CREATE TABLE species_occurrence_counts AS
SELECT
    taxon_key as taxon_id,
    COUNT(*) as tile_count
FROM geohash_species_tiles g,
     LATERAL jsonb_object_keys(g.species_data) as taxon_key
GROUP BY taxon_key;

CREATE INDEX idx_occ_taxon ON species_occurrence_counts(taxon_id);

-- Now update candidate_species using the pre-computed counts
UPDATE candidate_species cs
SET tile_count = COALESCE(soc.tile_count, 0)
FROM species_occurrence_counts soc
WHERE cs.taxon_id = soc.taxon_id;

-- ==============================================================================
-- STEP 3: FILTER TO TARGET OCCURRENCE RANGE
-- ==============================================================================

-- Keep only species with 100-50,000 occurrence tiles
-- This avoids sparse data (< 100) and computational limits (> 50,000)

DELETE FROM candidate_species
WHERE tile_count < 100 OR tile_count > 50000;

SELECT
    COUNT(*) as species_in_range,
    MIN(tile_count) as min_tiles,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY tile_count)::integer as p25_tiles,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY tile_count)::integer as median_tiles,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY tile_count)::integer as p75_tiles,
    MAX(tile_count) as max_tiles
FROM candidate_species;

-- ==============================================================================
-- STEP 4: ADD DERIVED CATEGORICAL VARIABLES
-- ==============================================================================

ALTER TABLE candidate_species ADD COLUMN IF NOT EXISTS niche_breadth TEXT;
ALTER TABLE candidate_species ADD COLUMN IF NOT EXISTS forest_category TEXT;
ALTER TABLE candidate_species ADD COLUMN IF NOT EXISTS occurrence_category TEXT;

UPDATE candidate_species
SET niche_breadth = CASE
    WHEN num_ecoregions <= 2 THEN 'specialist'
    WHEN num_ecoregions BETWEEN 3 AND 6 THEN 'moderate'
    WHEN num_ecoregions BETWEEN 7 AND 15 THEN 'generalist'
    ELSE 'widespread'
END;

UPDATE candidate_species
SET forest_category = CASE
    WHEN present_intact_forest = 'YES' THEN 'intact_only'
    WHEN present_intact_forest = 'NO' THEN 'disturbed_only'
    WHEN present_intact_forest IN ('NO;YES', 'YES;NO') THEN 'both'
    ELSE 'unknown'
END;

UPDATE candidate_species
SET occurrence_category = CASE
    WHEN tile_count BETWEEN 100 AND 500 THEN 'sparse'
    WHEN tile_count BETWEEN 501 AND 5000 THEN 'moderate'
    WHEN tile_count BETWEEN 5001 AND 50000 THEN 'rich'
END;

-- Summary statistics by category
SELECT
    dominant_biome,
    niche_breadth,
    COUNT(*) as species_count,
    AVG(tile_count)::integer as avg_tiles
FROM candidate_species
GROUP BY dominant_biome, niche_breadth
ORDER BY dominant_biome, niche_breadth;

-- ==============================================================================
-- STEP 5: STRATIFIED SELECTION - BIOME REPRESENTATION (30 species)
-- ==============================================================================

DROP TABLE IF EXISTS selected_biome;

CREATE TABLE selected_biome AS
-- Tropical Moist (15 species)
(SELECT *, 'biome' as selection_dimension, 'Tropical Moist' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Tropical Moist'
 ORDER BY RANDOM()
 LIMIT 15)

UNION ALL

-- Temperate Broadleaf (8 species)
(SELECT *, 'biome' as selection_dimension, 'Temperate Broadleaf' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Temperate Broadleaf'
 ORDER BY RANDOM()
 LIMIT 8)

UNION ALL

-- Boreal (3 species)
(SELECT *, 'biome' as selection_dimension, 'Boreal' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Boreal'
 ORDER BY RANDOM()
 LIMIT 3)

UNION ALL

-- Tropical Dry (4 species)
(SELECT *, 'biome' as selection_dimension, 'Tropical Dry' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Tropical Dry'
 ORDER BY RANDOM()
 LIMIT 4)

UNION ALL

-- Mediterranean (3 species)
(SELECT *, 'biome' as selection_dimension, 'Mediterranean' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Mediterranean'
 ORDER BY RANDOM()
 LIMIT 3)

UNION ALL

-- Montane (4 species)
(SELECT *, 'biome' as selection_dimension, 'Montane' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Montane'
 ORDER BY RANDOM()
 LIMIT 4)

UNION ALL

-- Mangroves (3 species)
(SELECT *, 'biome' as selection_dimension, 'Mangroves' as stratum
 FROM candidate_species
 WHERE dominant_biome = 'Mangroves'
 ORDER BY RANDOM()
 LIMIT 3);

SELECT COUNT(*) as biome_selected FROM selected_biome;

-- ==============================================================================
-- STEP 6: STRATIFIED SELECTION - NICHE BREADTH (25 species)
-- ==============================================================================

DROP TABLE IF EXISTS selected_niche;

CREATE TABLE selected_niche AS
-- Specialists (10 species)
(SELECT *, 'niche' as selection_dimension, 'specialist' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'specialist'
 ORDER BY RANDOM()
 LIMIT 10)

UNION ALL

-- Moderate generalists (10 species)
(SELECT *, 'niche' as selection_dimension, 'moderate' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'moderate'
 ORDER BY RANDOM()
 LIMIT 10)

UNION ALL

-- Generalists (5 species)
(SELECT *, 'niche' as selection_dimension, 'generalist' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'generalist'
 ORDER BY RANDOM()
 LIMIT 5);

SELECT COUNT(*) as niche_selected FROM selected_niche;

-- ==============================================================================
-- STEP 7: STRATIFIED SELECTION - INTACT FOREST CATEGORY (15 species)
-- ==============================================================================

DROP TABLE IF EXISTS selected_forest;

CREATE TABLE selected_forest AS
-- Intact forest only (5 species)
(SELECT *, 'forest' as selection_dimension, 'intact_only' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION
     SELECT taxon_id FROM selected_niche
 )
 AND forest_category = 'intact_only'
 ORDER BY RANDOM()
 LIMIT 5)

UNION ALL

-- Disturbed areas only (5 species)
(SELECT *, 'forest' as selection_dimension, 'disturbed_only' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION
     SELECT taxon_id FROM selected_niche
 )
 AND forest_category = 'disturbed_only'
 ORDER BY RANDOM()
 LIMIT 5)

UNION ALL

-- Both environments (5 species)
(SELECT *, 'forest' as selection_dimension, 'both' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION
     SELECT taxon_id FROM selected_niche
 )
 AND forest_category = 'both'
 ORDER BY RANDOM()
 LIMIT 5);

SELECT COUNT(*) as forest_selected FROM selected_forest;

-- ==============================================================================
-- STEP 8: STRATIFIED SELECTION - PHYLOGENETIC DIVERSITY (20 species)
-- ==============================================================================

DROP TABLE IF EXISTS selected_phylo;

CREATE TABLE selected_phylo AS
-- Quercus (oaks) - 4 species with highest occurrence counts
(SELECT *, 'phylo' as selection_dimension, 'Quercus' as stratum
 FROM candidate_species
 WHERE genus = 'Quercus'
 ORDER BY tile_count DESC
 LIMIT 4)

UNION ALL

-- Pinus (pines) - 4 species
(SELECT *, 'phylo' as selection_dimension, 'Pinus' as stratum
 FROM candidate_species
 WHERE genus = 'Pinus'
 ORDER BY tile_count DESC
 LIMIT 4)

UNION ALL

-- Eucalyptus - 3 species
(SELECT *, 'phylo' as selection_dimension, 'Eucalyptus' as stratum
 FROM candidate_species
 WHERE genus = 'Eucalyptus'
 ORDER BY tile_count DESC
 LIMIT 3)

UNION ALL

-- Ficus - 3 species
(SELECT *, 'phylo' as selection_dimension, 'Ficus' as stratum
 FROM candidate_species
 WHERE genus = 'Ficus'
 ORDER BY tile_count DESC
 LIMIT 3)

UNION ALL

-- Acacia - 3 species
(SELECT *, 'phylo' as selection_dimension, 'Acacia' as stratum
 FROM candidate_species
 WHERE genus = 'Acacia'
 ORDER BY tile_count DESC
 LIMIT 3)

UNION ALL

-- Other key genera (1 species each)
(SELECT *, 'phylo' as selection_dimension, 'Salix' as stratum
 FROM candidate_species
 WHERE genus = 'Salix'
 ORDER BY tile_count DESC
 LIMIT 1)

UNION ALL

(SELECT *, 'phylo' as selection_dimension, 'Nothofagus' as stratum
 FROM candidate_species
 WHERE genus = 'Nothofagus'
 ORDER BY tile_count DESC
 LIMIT 1)

UNION ALL

(SELECT *, 'phylo' as selection_dimension, 'Dipterocarpus' as stratum
 FROM candidate_species
 WHERE genus = 'Dipterocarpus'
 ORDER BY tile_count DESC
 LIMIT 1);

SELECT COUNT(*) as phylo_selected FROM selected_phylo;

-- ==============================================================================
-- STEP 9: STRATIFIED SELECTION - OCCURRENCE DATA QUALITY (10 species)
-- ==============================================================================

DROP TABLE IF EXISTS selected_occurrence;

CREATE TABLE selected_occurrence AS
-- Sparse data (100-500 tiles) - 2 species
(SELECT *, 'occurrence' as selection_dimension, 'sparse' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION SELECT taxon_id FROM selected_niche
     UNION SELECT taxon_id FROM selected_forest
     UNION SELECT taxon_id FROM selected_phylo
 )
 AND occurrence_category = 'sparse'
 ORDER BY RANDOM()
 LIMIT 2)

UNION ALL

-- Moderate data (500-5000 tiles) - 4 species
(SELECT *, 'occurrence' as selection_dimension, 'moderate' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION SELECT taxon_id FROM selected_niche
     UNION SELECT taxon_id FROM selected_forest
     UNION SELECT taxon_id FROM selected_phylo
 )
 AND occurrence_category = 'moderate'
 ORDER BY RANDOM()
 LIMIT 4)

UNION ALL

-- Rich data (5000-50000 tiles) - 4 species
(SELECT *, 'occurrence' as selection_dimension, 'rich' as stratum
 FROM candidate_species
 WHERE taxon_id NOT IN (
     SELECT taxon_id FROM selected_biome
     UNION SELECT taxon_id FROM selected_niche
     UNION SELECT taxon_id FROM selected_forest
     UNION SELECT taxon_id FROM selected_phylo
 )
 AND occurrence_category = 'rich'
 ORDER BY RANDOM()
 LIMIT 4);

SELECT COUNT(*) as occurrence_selected FROM selected_occurrence;

-- ==============================================================================
-- STEP 10: COMBINE ALL SELECTIONS INTO FINAL TABLE
-- ==============================================================================

DROP TABLE IF EXISTS alphaearth_pilot_species;

CREATE TABLE alphaearth_pilot_species AS
SELECT DISTINCT ON (taxon_id)
    taxon_id,
    species_scientific_name,
    family,
    genus,
    dominant_biome,
    niche_breadth,
    forest_category,
    occurrence_category,
    tile_count,
    num_ecoregions,
    num_countries,
    present_intact_forest,
    ecoregions,
    biomes,
    countries_native,
    selection_dimension,
    stratum
FROM (
    SELECT * FROM selected_biome
    UNION ALL
    SELECT * FROM selected_niche
    UNION ALL
    SELECT * FROM selected_forest
    UNION ALL
    SELECT * FROM selected_phylo
    UNION ALL
    SELECT * FROM selected_occurrence
) combined;

-- Summary of final selection
SELECT
    selection_dimension,
    COUNT(*) as species_count
FROM alphaearth_pilot_species
GROUP BY selection_dimension
ORDER BY species_count DESC;

SELECT
    dominant_biome,
    COUNT(*) as species_count
FROM alphaearth_pilot_species
GROUP BY dominant_biome
ORDER BY species_count DESC;

SELECT COUNT(*) as total_selected FROM alphaearth_pilot_species;

-- ==============================================================================
-- STEP 11: EXPORT FINAL SPECIES LIST
-- ==============================================================================

-- Export to CSV for Python processing
\copy (SELECT taxon_id, species_scientific_name, family, genus, dominant_biome, niche_breadth, forest_category, occurrence_category, tile_count, num_ecoregions, selection_dimension, stratum FROM alphaearth_pilot_species ORDER BY family, genus, species_scientific_name) TO '/tmp/alphaearth_pilot_species.csv' WITH CSV HEADER;

-- ==============================================================================
-- STEP 12: EXTRACT OCCURRENCE DATA FOR SELECTED SPECIES
-- ==============================================================================

DROP TABLE IF EXISTS alphaearth_occurrences;

CREATE TABLE alphaearth_occurrences AS
SELECT
    aps.taxon_id,
    aps.species_scientific_name,
    aps.family,
    g.geohash_l7,
    ST_Y(g.center_point::geometry) as latitude,
    ST_X(g.center_point::geometry) as longitude,
    (g.species_data ->> aps.taxon_id)::integer as occurrence_count,
    g.datetime as observation_date
FROM alphaearth_pilot_species aps
JOIN geohash_species_tiles g ON g.species_data ? aps.taxon_id;

-- Add index for faster queries
CREATE INDEX idx_alphaearth_occ_taxon ON alphaearth_occurrences(taxon_id);
CREATE INDEX idx_alphaearth_occ_geohash ON alphaearth_occurrences(geohash_l7);

-- Summary statistics
SELECT
    COUNT(*) as total_occurrences,
    COUNT(DISTINCT taxon_id) as species_with_data,
    COUNT(DISTINCT geohash_l7) as unique_tiles
FROM alphaearth_occurrences;

SELECT
    taxon_id,
    species_scientific_name,
    COUNT(*) as occurrence_tiles
FROM alphaearth_occurrences
GROUP BY taxon_id, species_scientific_name
ORDER BY occurrence_tiles DESC
LIMIT 20;

-- Export occurrence data
\copy (SELECT taxon_id, species_scientific_name, family, geohash_l7, latitude, longitude, occurrence_count FROM alphaearth_occurrences ORDER BY taxon_id, geohash_l7) TO '/tmp/alphaearth_occurrences.csv' WITH CSV HEADER;

-- ==============================================================================
-- STEP 13: CREATE TEST POINTS TABLE
-- ==============================================================================

DROP TABLE IF EXISTS alphaearth_test_points;

CREATE TABLE alphaearth_test_points (
    point_id SERIAL PRIMARY KEY,
    point_name TEXT NOT NULL,
    category TEXT NOT NULL, -- 'gradient_extreme', 'ecotone', 'known_location'
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    description TEXT,
    environmental_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert 30 strategic test points across environmental gradients
INSERT INTO alphaearth_test_points (point_name, category, latitude, longitude, description, environmental_notes) VALUES
    -- GRADIENT EXTREMES (10 points)
    ('Yukon_Boreal', 'gradient_extreme', 64.0, -135.0, 'Coldest: Boreal Canada treeline', 'Mean annual temp -5C, short growing season, permafrost'),
    ('Sahel_Dry', 'gradient_extreme', 13.0, 2.0, 'Hottest/driest: Sahel dry season', 'Mean annual temp 28C, <500mm precip, extreme seasonality'),
    ('Western_Ghats', 'gradient_extreme', 11.5, 76.0, 'Wettest: Western Ghats monsoon', '>7000mm annual rainfall, tropical montane'),
    ('Atacama_Fringe', 'gradient_extreme', -23.0, -68.0, 'Driest: Atacama desert fringe', '<50mm annual rainfall, high elevation desert'),
    ('Andes_Treeline', 'gradient_extreme', -13.0, -72.0, 'Highest: Andean treeline', '3800m elevation, Polylepis forests, frost-adapted'),
    ('Mangrove_Estuary', 'gradient_extreme', 10.0, -84.0, 'Sea level: Mangrove estuaries Costa Rica', 'Saltwater tolerance, tidal flooding, hurricane exposure'),
    ('Mediterranean_Peak', 'gradient_extreme', 37.5, 3.0, 'Most seasonal: Mediterranean Algeria', 'Hot dry summer, cool wet winter, fire-adapted'),
    ('Congo_Equatorial', 'gradient_extreme', 0.5, 25.0, 'Least seasonal: Equatorial Congo', 'Aseasonal rainfall, constant high temp, high diversity'),
    ('Amazon_Terra_Firme', 'gradient_extreme', -3.0, -60.0, 'High soil diversity: Amazon upland', 'Nutrient-poor oxisols, high tree diversity'),
    ('Borneo_Logged', 'gradient_extreme', 1.5, 117.0, 'Extreme disturbance: Recently logged Borneo', 'Selective logging, edge effects, invasive species'),

    -- ECOTONES / TRANSITION ZONES (10 points)
    ('Cerrado_Amazon', 'ecotone', -10.0, -52.0, 'Cerrado-Amazon transition Brazil', 'Savanna-forest mosaic, fire regime, climate boundary'),
    ('Cameroon_Ecotone', 'ecotone', 5.0, 11.0, 'Forest-savanna mosaic Central Africa', 'Guinea-Congolia boundary, precipitation gradient'),
    ('Canada_Transition', 'ecotone', 54.0, -105.0, 'Temperate-boreal transition Saskatchewan', 'Mixed deciduous-conifer, climate warming signal'),
    ('Morocco_Transition', 'ecotone', 33.0, -5.0, 'Mediterranean-desert transition Morocco', 'Argan forest, arid adaptation'),
    ('Andes_Montane', 'ecotone', -8.0, -77.0, 'Montane-lowland transition Peru', 'Yungas cloud forest, elevation gradient'),
    ('Madagascar_Highlands', 'ecotone', -19.0, 47.0, 'Madagascar dry-moist transition', 'High endemism, degraded forest, restoration potential'),
    ('Australia_Mulga', 'ecotone', -27.0, 145.0, 'Temperate-arid transition Australia', 'Mulga-mallee boundary, drought stress'),
    ('Indonesia_Wallace', 'ecotone', -2.0, 120.0, 'Wallace Line Sulawesi', 'Biogeographic boundary, island biogeography'),
    ('China_Subtropical', 'ecotone', 28.0, 105.0, 'Subtropical-warm temperate China', 'Mixed evergreen-deciduous, high diversity'),
    ('Mexico_Pine_Oak', 'ecotone', 19.0, -99.0, 'Pine-oak forest Mexico', 'Temperate-tropical transition, high elevation'),

    -- KNOWN PRESENCE/ABSENCE LOCATIONS (10 points)
    -- These will be filled in during analysis based on selected species ranges
    ('Quercus_Core', 'known_location', 40.0, -82.0, 'Oak range center eastern US', 'High probability presence for Quercus species'),
    ('Quercus_Edge', 'known_location', 48.0, -95.0, 'Oak range edge Minnesota', 'Marginal habitat for Quercus macrocarpa'),
    ('Pinus_Core', 'known_location', 56.0, 25.0, 'Pine range center Baltic', 'High probability for Pinus sylvestris'),
    ('Eucalyptus_Core', 'known_location', -33.0, 150.0, 'Eucalyptus range Australia', 'High diversity, multiple species overlap'),
    ('Tropical_Moist_Core', 'known_location', -3.0, -55.0, 'Central Amazon basin', 'Peak tropical moist forest diversity'),
    ('Tropical_Moist_Absent', 'known_location', 15.0, -88.0, 'Central America gap', 'Environmental suitable but some species absent'),
    ('Temperate_Asia', 'known_location', 35.0, 136.0, 'Japan temperate forests', 'Island isolation, endemic species'),
    ('African_Montane', 'known_location', -3.0, 37.0, 'Mt Kilimanjaro', 'Afromontane flora, elevation gradient'),
    ('New_Guinea_Highlands', 'known_location', -5.5, 145.0, 'New Guinea montane', 'High endemism, isolated mountain flora'),
    ('Patagonia', 'known_location', -41.0, -71.0, 'Patagonian forests', 'Southern beech (Nothofagus) dominance');

-- Export test points
\copy (SELECT point_id, point_name, category, latitude, longitude, description, environmental_notes FROM alphaearth_test_points ORDER BY category, point_id) TO '/tmp/alphaearth_test_points.csv' WITH CSV HEADER;

SELECT
    category,
    COUNT(*) as point_count
FROM alphaearth_test_points
GROUP BY category;

-- ==============================================================================
-- STEP 14: VALIDATION QUERIES - CHECK SELECTION QUALITY
-- ==============================================================================

-- Check taxonomic diversity
SELECT
    family,
    COUNT(*) as species_count
FROM alphaearth_pilot_species
GROUP BY family
ORDER BY species_count DESC;

-- Check occurrence distribution
SELECT
    occurrence_category,
    COUNT(*) as species_count,
    MIN(tile_count) as min_tiles,
    ROUND(AVG(tile_count)) as avg_tiles,
    MAX(tile_count) as max_tiles
FROM alphaearth_pilot_species
GROUP BY occurrence_category
ORDER BY occurrence_category;

-- Check niche breadth distribution
SELECT
    niche_breadth,
    COUNT(*) as species_count,
    ROUND(AVG(num_ecoregions), 1) as avg_ecoregions
FROM alphaearth_pilot_species
GROUP BY niche_breadth
ORDER BY niche_breadth;

-- Check forest category distribution
SELECT
    forest_category,
    COUNT(*) as species_count
FROM alphaearth_pilot_species
GROUP BY forest_category
ORDER BY species_count DESC;

-- Check phylogenetic representation
SELECT
    genus,
    COUNT(*) as species_count,
    array_agg(species_scientific_name ORDER BY species_scientific_name) as species_list
FROM alphaearth_pilot_species
WHERE selection_dimension = 'phylo'
GROUP BY genus
ORDER BY species_count DESC;

-- Summary report
SELECT
    'Total Species' as metric,
    COUNT(*)::text as value
FROM alphaearth_pilot_species
UNION ALL
SELECT
    'Total Families' as metric,
    COUNT(DISTINCT family)::text as value
FROM alphaearth_pilot_species
UNION ALL
SELECT
    'Total Genera' as metric,
    COUNT(DISTINCT genus)::text as value
FROM alphaearth_pilot_species
UNION ALL
SELECT
    'Total Occurrences' as metric,
    COUNT(*)::text as value
FROM alphaearth_occurrences
UNION ALL
SELECT
    'Unique Tiles' as metric,
    COUNT(DISTINCT geohash_l7)::text as value
FROM alphaearth_occurrences
UNION ALL
SELECT
    'Test Points' as metric,
    COUNT(*)::text as value
FROM alphaearth_test_points;

-- ==============================================================================
-- NOTES FOR EXECUTION
-- ==============================================================================

/*
EXECUTION ORDER:

1. Run Steps 1-4 first (create candidate pool and filter)
   - This will take 30-60 minutes due to occurrence count calculations
   - Consider running Step 2 overnight if database is large

2. Run Steps 5-10 (stratified selection)
   - These are fast (< 1 minute each)
   - Random selection means results vary each run - set seed for reproducibility

3. Run Steps 11-12 (export species and occurrences)
   - Exports CSV files to /tmp/ directory
   - Change path if needed for your system

4. Run Step 13 (create test points)
   - Manually curated strategic locations
   - Modify coordinates as needed for your study area

5. Run Step 14 (validation)
   - Check that selection meets design criteria
   - If not satisfied, re-run Steps 5-10 with different random seeds

REPRODUCIBILITY:
- To get identical results across runs, add: SELECT setseed(0.42);
- Place this before Step 5 (first random selection)
- Change seed value (0.0-1.0) for different selections

PERFORMANCE TIPS:
- Step 2 is the bottleneck - consider parallelization
- If using PostgreSQL 14+, enable parallel queries: SET max_parallel_workers_per_gather = 4;
- Add more indexes if queries are slow: CREATE INDEX idx_geohash_species ON geohash_species_tiles USING gin(species_data);

*/
