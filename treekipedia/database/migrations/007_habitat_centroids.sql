-- Migration: 007_habitat_centroids.sql
-- Description: Create tables for AlphaEarth habitat centroids and elevation profiles
-- Date: 2026-01-21
-- Depends on: pgvector extension

-- Ensure pgvector extension is available
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Table: species_habitat_centroids
-- Purpose: Store 3-10 habitat cluster centroids per species for similarity search
-- ============================================================================

CREATE TABLE IF NOT EXISTS species_habitat_centroids (
    id SERIAL PRIMARY KEY,

    -- Species identification
    taxon_id VARCHAR(50) NOT NULL,
    cluster_id INTEGER NOT NULL,

    -- 64-dimensional AlphaEarth embedding centroid
    centroid_vector vector(64) NOT NULL,

    -- Cluster statistics
    occurrence_count INTEGER,           -- Number of pixels in this cluster
    mean_elevation FLOAT,               -- Mean elevation (meters)
    elevation_std FLOAT,                -- Elevation standard deviation
    mean_treecover2000 FLOAT,           -- Mean tree cover % in 2000
    forest_loss_fraction FLOAT,         -- Fraction of pixels with forest loss

    -- Representative location (point closest to centroid)
    representative_lat FLOAT,
    representative_lon FLOAT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(taxon_id, cluster_id)
);

-- Index for fast cosine similarity search using IVFFlat
-- lists = 100 is good for ~100k-1M vectors; adjust if needed
CREATE INDEX IF NOT EXISTS idx_centroid_vector
ON species_habitat_centroids
USING ivfflat (centroid_vector vector_cosine_ops) WITH (lists = 100);

-- Index for species lookup
CREATE INDEX IF NOT EXISTS idx_centroid_taxon
ON species_habitat_centroids(taxon_id);

-- Index for elevation filtering
CREATE INDEX IF NOT EXISTS idx_centroid_elevation
ON species_habitat_centroids(mean_elevation);

COMMENT ON TABLE species_habitat_centroids IS
'Habitat cluster centroids derived from AlphaEarth 64-D satellite embeddings.
Each species has 3-10 clusters representing distinct habitat types.
Used for cosine similarity-based habitat prediction.';

COMMENT ON COLUMN species_habitat_centroids.centroid_vector IS
'64-dimensional AlphaEarth embedding centroid for this habitat cluster';

COMMENT ON COLUMN species_habitat_centroids.forest_loss_fraction IS
'Fraction of occurrences in this cluster that experienced forest loss (Hansen data)';


-- ============================================================================
-- Table: species_elevation_profiles
-- Purpose: Pre-aggregated elevation statistics per species
-- ============================================================================

CREATE TABLE IF NOT EXISTS species_elevation_profiles (
    taxon_id VARCHAR(50) PRIMARY KEY,

    -- Elevation range
    min_elevation FLOAT,
    max_elevation FLOAT,
    mean_elevation FLOAT,
    median_elevation FLOAT,

    -- Percentiles for filtering
    p10_elevation FLOAT,    -- 10th percentile (lower bound of typical range)
    p90_elevation FLOAT,    -- 90th percentile (upper bound of typical range)

    -- Variance
    elevation_std FLOAT,

    -- Sample size
    occurrence_count INTEGER,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE species_elevation_profiles IS
'Pre-aggregated elevation statistics per species from AlphaEarth/SRTM data.
Used for efficient elevation-based filtering in habitat prediction.';


-- ============================================================================
-- Table: habitat_prediction_cache
-- Purpose: Cache recent habitat predictions for performance
-- ============================================================================

CREATE TABLE IF NOT EXISTS habitat_prediction_cache (
    id SERIAL PRIMARY KEY,

    -- Query parameters (for cache key)
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    query_vector vector(64),            -- The AlphaEarth embedding for this location

    -- Results (JSONB for flexibility)
    top_species JSONB,                  -- Array of {taxon_id, similarity, score}
    prediction_metadata JSONB,          -- elevation, ecoregion, etc.

    -- Cache management
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days'
);

-- Spatial index for finding cached predictions nearby
CREATE INDEX IF NOT EXISTS idx_prediction_cache_location
ON habitat_prediction_cache(latitude, longitude);

-- TTL cleanup (run periodically)
-- DELETE FROM habitat_prediction_cache WHERE expires_at < NOW();

COMMENT ON TABLE habitat_prediction_cache IS
'Cache for habitat predictions to avoid repeated BigQuery/GEE calls.
Entries expire after 7 days by default.';


-- ============================================================================
-- View: species_habitat_summary
-- Purpose: Quick overview of habitat data per species
-- ============================================================================

CREATE OR REPLACE VIEW species_habitat_summary AS
SELECT
    c.taxon_id,
    s.accepted_scientific_name,
    COUNT(c.id) as cluster_count,
    SUM(c.occurrence_count) as total_occurrences,
    AVG(c.mean_elevation) as avg_elevation,
    MIN(c.mean_elevation) as min_cluster_elevation,
    MAX(c.mean_elevation) as max_cluster_elevation,
    AVG(c.mean_treecover2000) as avg_treecover,
    AVG(c.forest_loss_fraction) as avg_loss_fraction
FROM species_habitat_centroids c
LEFT JOIN species s ON c.taxon_id = s.taxon_id
GROUP BY c.taxon_id, s.accepted_scientific_name;

COMMENT ON VIEW species_habitat_summary IS
'Aggregated view of habitat centroids per species for quick analysis';


-- ============================================================================
-- Function: find_similar_habitats
-- Purpose: Find species with similar habitats using cosine similarity
-- ============================================================================

CREATE OR REPLACE FUNCTION find_similar_habitats(
    query_vector vector(64),
    elevation_min FLOAT DEFAULT NULL,
    elevation_max FLOAT DEFAULT NULL,
    limit_count INTEGER DEFAULT 50
)
RETURNS TABLE (
    taxon_id VARCHAR(50),
    cluster_id INTEGER,
    similarity FLOAT,
    mean_elevation FLOAT,
    occurrence_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.taxon_id,
        c.cluster_id,
        1 - (c.centroid_vector <=> query_vector) as similarity,
        c.mean_elevation,
        c.occurrence_count
    FROM species_habitat_centroids c
    WHERE
        (elevation_min IS NULL OR c.mean_elevation >= elevation_min)
        AND (elevation_max IS NULL OR c.mean_elevation <= elevation_max)
    ORDER BY c.centroid_vector <=> query_vector
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_similar_habitats IS
'Find species with habitat centroids most similar to a query embedding.
Uses cosine similarity via pgvector. Optional elevation filtering.';


-- ============================================================================
-- Function: get_species_habitat_match
-- Purpose: Get best habitat match score for a specific species at a location
-- ============================================================================

CREATE OR REPLACE FUNCTION get_species_habitat_match(
    p_taxon_id VARCHAR(50),
    query_vector vector(64)
)
RETURNS TABLE (
    best_cluster_id INTEGER,
    similarity FLOAT,
    cluster_elevation FLOAT,
    cluster_treecover FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.cluster_id,
        1 - (c.centroid_vector <=> query_vector) as similarity,
        c.mean_elevation,
        c.mean_treecover2000
    FROM species_habitat_centroids c
    WHERE c.taxon_id = p_taxon_id
    ORDER BY c.centroid_vector <=> query_vector
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_species_habitat_match IS
'Get the best matching habitat cluster for a species at a given location.
Returns the cluster with highest cosine similarity to the query embedding.';


-- ============================================================================
-- Grants (adjust role names as needed)
-- ============================================================================

-- GRANT SELECT ON species_habitat_centroids TO treekipedia_readonly;
-- GRANT SELECT ON species_elevation_profiles TO treekipedia_readonly;
-- GRANT SELECT ON species_habitat_summary TO treekipedia_readonly;
-- GRANT ALL ON habitat_prediction_cache TO treekipedia_api;
