/**
 * Prediction API Routes
 * =====================
 * Endpoints for habitat prediction and species recommendation.
 *
 * Architecture:
 * 1. /predict - Pure scientific habitat suitability (the "can it grow here?" question)
 * 2. /recommend - Contextual recommendations (the "should I plant it here?" question)
 *
 * Flow:
 * 1. Client sends lat/lon
 * 2. Backend calls Python microservice to get AlphaEarth embedding
 * 3. Backend queries pgvector for similar habitat centroids
 * 4. Backend applies additional filters (elevation, native status, etc.)
 * 5. Returns ranked species list
 */

const express = require('express');
const router = express.Router();
const { Pool } = require('pg');
const axios = require('axios');

// Configuration
const LOCATION_PREDICTOR_URL = process.env.LOCATION_PREDICTOR_URL || 'http://localhost:5002';
const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://tree_user:Kj9mPx7vLq2wZn4t@localhost:5432/treekipedia',
});

/**
 * GET /api/prediction/sample
 *
 * Get AlphaEarth embedding for a location.
 * This is a proxy to the Python location predictor service.
 */
router.get('/sample', async (req, res) => {
    try {
        const { lat, lon } = req.query;

        if (!lat || !lon) {
            return res.status(400).json({
                error: 'Missing required parameters: lat, lon'
            });
        }

        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);

        if (isNaN(latitude) || isNaN(longitude)) {
            return res.status(400).json({
                error: 'Invalid coordinates: lat and lon must be numbers'
            });
        }

        // Call Python microservice
        const response = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
            params: { lat: latitude, lon: longitude },
            timeout: 30000 // 30 second timeout for GEE calls
        });

        res.json(response.data);

    } catch (error) {
        console.error('Sample endpoint error:', error.message);

        if (error.code === 'ECONNREFUSED') {
            return res.status(503).json({
                error: 'Location predictor service unavailable',
                detail: 'The Python microservice at port 5002 is not running'
            });
        }

        res.status(500).json({
            error: 'Failed to sample location',
            detail: error.message
        });
    }
});

/**
 * GET /api/prediction/predict
 *
 * Predict suitable species for a location based on habitat similarity.
 * This is the pure scientific prediction (Suitability score).
 *
 * Query Parameters:
 * - lat: Latitude (required)
 * - lon: Longitude (required)
 * - elevation_tolerance: ± meters for elevation filtering (default: 500)
 * - limit: Max species to return (default: 50, max: 200)
 * - min_similarity: Minimum cosine similarity threshold (default: 0.7)
 */
router.get('/predict', async (req, res) => {
    try {
        const {
            lat,
            lon,
            elevation_tolerance = 500,
            limit = 50,
            min_similarity = 0.7
        } = req.query;

        if (!lat || !lon) {
            return res.status(400).json({
                error: 'Missing required parameters: lat, lon'
            });
        }

        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);
        const elevTolerance = parseInt(elevation_tolerance);
        const resultLimit = Math.min(parseInt(limit), 200);
        const minSim = parseFloat(min_similarity);

        // Step 1: Get embedding from location predictor
        let embedding, locationData;
        try {
            const sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                params: { lat: latitude, lon: longitude },
                timeout: 30000
            });
            embedding = sampleResponse.data.alphaearth_embedding;
            locationData = sampleResponse.data;
        } catch (error) {
            // If location predictor fails, return error with explanation
            return res.status(503).json({
                error: 'Cannot get habitat embedding for location',
                detail: 'Location predictor service unavailable or location not covered',
                location: { lat: latitude, lon: longitude }
            });
        }

        if (!embedding || !Array.isArray(embedding) || embedding.length !== 64) {
            return res.status(400).json({
                error: 'Invalid embedding from location predictor',
                detail: 'Expected 64-dimensional AlphaEarth embedding'
            });
        }

        // Step 2: Query pgvector for similar habitat centroids
        const elevation = locationData.elevation || null;
        const elevMin = elevation ? elevation - elevTolerance : null;
        const elevMax = elevation ? elevation + elevTolerance : null;

        // Convert embedding array to pgvector format
        const vectorString = `[${embedding.join(',')}]`;

        const query = `
            WITH ranked_centroids AS (
                SELECT
                    c.taxon_id,
                    c.cluster_id,
                    1 - (c.centroid_vector <=> $1::vector) as similarity,
                    c.mean_elevation,
                    c.occurrence_count,
                    c.mean_treecover2000,
                    c.forest_loss_fraction,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.taxon_id
                        ORDER BY c.centroid_vector <=> $1::vector
                    ) as rank_in_species
                FROM species_habitat_centroids c
                WHERE
                    ($2::float IS NULL OR c.mean_elevation >= $2)
                    AND ($3::float IS NULL OR c.mean_elevation <= $3)
            )
            SELECT
                r.taxon_id,
                r.similarity,
                r.mean_elevation as cluster_elevation,
                r.occurrence_count,
                r.mean_treecover2000,
                r.forest_loss_fraction,
                s.accepted_scientific_name,
                s.common_name,
                s.family,
                s.genus,
                COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                COALESCE(s.maximum_height_human, s.maximum_height_ai) as maximum_height,
                s.wcvp_native as native_regions,
                COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status
            FROM ranked_centroids r
            LEFT JOIN species s ON r.taxon_id = s.taxon_id
            WHERE r.rank_in_species = 1  -- Best cluster per species
              AND r.similarity >= $4
            ORDER BY r.similarity DESC
            LIMIT $5
        `;

        const result = await pool.query(query, [
            vectorString,
            elevMin,
            elevMax,
            minSim,
            resultLimit
        ]);

        // Step 3: Format response
        const predictions = result.rows.map((row, index) => ({
            rank: index + 1,
            taxon_id: row.taxon_id,
            scientific_name: row.accepted_scientific_name,
            common_name: row.common_name,
            family: row.family,
            genus: row.genus,

            // Suitability score (0-100)
            suitability_score: Math.round(row.similarity * 100),
            habitat_similarity: parseFloat(row.similarity.toFixed(4)),

            // Habitat match details
            habitat_match: {
                cluster_elevation: row.cluster_elevation,
                cluster_treecover: row.mean_treecover2000,
                cluster_occurrences: row.occurrence_count,
                forest_loss_risk: row.forest_loss_fraction
            },

            // Species attributes for filtering
            attributes: {
                growth_form: row.growth_form,
                maximum_height: row.maximum_height,
                conservation_status: row.conservation_status,
                threatened_status: null
            }
        }));

        res.json({
            success: true,
            location: {
                latitude,
                longitude,
                elevation: locationData.elevation,
                treecover2000: locationData.treecover2000,
                forest_loss: locationData.loss
            },
            query_params: {
                elevation_tolerance: elevTolerance,
                min_similarity: minSim,
                limit: resultLimit
            },
            results: {
                count: predictions.length,
                predictions
            }
        });

    } catch (error) {
        console.error('Predict endpoint error:', error);
        res.status(500).json({
            error: 'Prediction failed',
            detail: error.message
        });
    }
});

/**
 * GET /api/prediction/recommend
 *
 * Get contextual species recommendations for a location.
 * Builds on /predict but adds SAFE-B scoring components:
 * - Native status filtering/boosting
 * - Restoration goal matching
 * - Biogeographic proximity
 *
 * Query Parameters:
 * - lat, lon: Location (required)
 * - country_code: ISO country code for native filtering (optional)
 * - restoration_goal: erosion_control|soil_fertility|biodiversity|carbon|timber (optional)
 * - include_introduced: Include non-native species (default: false)
 * - limit: Max species to return (default: 20, max: 100)
 */
router.get('/recommend', async (req, res) => {
    try {
        const {
            lat,
            lon,
            country_code,
            restoration_goal,
            include_introduced = 'false',
            limit = 20
        } = req.query;

        if (!lat || !lon) {
            return res.status(400).json({
                error: 'Missing required parameters: lat, lon'
            });
        }

        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);
        const includeIntroduced = include_introduced === 'true';
        const resultLimit = Math.min(parseInt(limit), 100);

        // Step 1: Get habitat predictions (reuse predict logic)
        let embedding, locationData;
        try {
            const sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                params: { lat: latitude, lon: longitude },
                timeout: 30000
            });
            embedding = sampleResponse.data.alphaearth_embedding;
            locationData = sampleResponse.data;
        } catch (error) {
            return res.status(503).json({
                error: 'Cannot get habitat embedding for location',
                detail: 'Location predictor service unavailable'
            });
        }

        if (!embedding || embedding.length !== 64) {
            return res.status(400).json({
                error: 'Invalid embedding from location predictor'
            });
        }

        const vectorString = `[${embedding.join(',')}]`;
        const elevation = locationData.elevation;
        const elevMin = elevation ? elevation - 500 : null;
        const elevMax = elevation ? elevation + 500 : null;

        // Step 2: Query with SAFE-B scoring
        // This query applies native status filtering and goal-based scoring
        const query = `
            WITH habitat_matches AS (
                SELECT
                    c.taxon_id,
                    1 - (c.centroid_vector <=> $1::vector) as similarity,
                    c.mean_elevation,
                    c.occurrence_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.taxon_id
                        ORDER BY c.centroid_vector <=> $1::vector
                    ) as rank_in_species
                FROM species_habitat_centroids c
                WHERE
                    ($2::float IS NULL OR c.mean_elevation >= $2)
                    AND ($3::float IS NULL OR c.mean_elevation <= $3)
            ),
            scored_species AS (
                SELECT
                    h.taxon_id,
                    h.similarity,
                    h.mean_elevation as cluster_elevation,
                    h.occurrence_count,
                    s.accepted_scientific_name,
                    s.common_name,
                    s.family,
                    COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                    s.wcvp_native,
                    s.wcvp_introduced,
                    s.functional_ecosystem_groups,
                    s.uses,
                    COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status,
                    -- Native status scoring
                    CASE
                        WHEN $4::text IS NOT NULL AND s.wcvp_native ILIKE '%' || $4 || '%' THEN 0.2
                        WHEN $4::text IS NOT NULL AND s.wcvp_introduced ILIKE '%' || $4 || '%' THEN -0.1
                        ELSE 0
                    END as native_boost,
                    -- Restoration goal scoring
                    CASE
                        WHEN $5 = 'soil_fertility' THEN 0.0
                        WHEN $5 = 'biodiversity' AND s.functional_ecosystem_groups IS NOT NULL THEN 0.1
                        WHEN $5 = 'carbon' AND COALESCE(s.growth_form_human, s.growth_form_ai) ILIKE '%tree%' THEN 0.1
                        WHEN $5 = 'timber' AND s.uses ILIKE '%timber%' THEN 0.1
                        ELSE 0
                    END as goal_boost
                FROM habitat_matches h
                LEFT JOIN species s ON h.taxon_id = s.taxon_id
                WHERE h.rank_in_species = 1
                  AND h.similarity >= 0.6
                  AND (
                      $6::boolean = true  -- include_introduced
                      OR $4::text IS NULL  -- no country filter
                      OR s.wcvp_native ILIKE '%' || $4 || '%'
                      OR s.wcvp_introduced IS NULL
                  )
            )
            SELECT
                taxon_id,
                accepted_scientific_name,
                common_name,
                family,
                growth_form,
                wcvp_native,
                wcvp_introduced,
                functional_ecosystem_groups,
                conservation_status,
                similarity,
                cluster_elevation,
                occurrence_count,
                native_boost,
                goal_boost,
                -- Final SAFE-B score (simplified)
                (similarity * 0.5 + native_boost + goal_boost + 0.3) as safe_b_score
            FROM scored_species
            ORDER BY (similarity * 0.5 + native_boost + goal_boost + 0.3) DESC
            LIMIT $7
        `;

        const result = await pool.query(query, [
            vectorString,
            elevMin,
            elevMax,
            country_code || null,
            restoration_goal || null,
            includeIntroduced,
            resultLimit
        ]);

        // Step 3: Format recommendations
        const recommendations = result.rows.map((row, index) => ({
            rank: index + 1,
            taxon_id: row.taxon_id,
            scientific_name: row.accepted_scientific_name,
            common_name: row.common_name,
            family: row.family,

            // SAFE-B Score components
            scores: {
                safe_b_total: Math.round(row.safe_b_score * 100),
                suitability: Math.round(row.similarity * 100),
                native_bonus: Math.round(row.native_boost * 100),
                goal_bonus: Math.round(row.goal_boost * 100)
            },

            // Recommendation context
            context: {
                is_native: row.wcvp_native?.toLowerCase().includes(country_code?.toLowerCase() || ''),
                is_introduced: row.wcvp_introduced?.toLowerCase().includes(country_code?.toLowerCase() || ''),
                native_regions: row.wcvp_native,
                functional_groups: row.functional_ecosystem_groups,
                nitrogen_fixing: null
            },

            // Species attributes
            attributes: {
                growth_form: row.growth_form,
                conservation_status: row.conservation_status,
                cluster_elevation: row.cluster_elevation,
                occurrence_count: row.occurrence_count
            }
        }));

        res.json({
            success: true,
            location: {
                latitude,
                longitude,
                elevation: locationData.elevation,
                country_code: country_code || 'not specified'
            },
            query_params: {
                restoration_goal: restoration_goal || 'none',
                include_introduced: includeIntroduced,
                limit: resultLimit
            },
            results: {
                count: recommendations.length,
                recommendations
            }
        });

    } catch (error) {
        console.error('Recommend endpoint error:', error);
        res.status(500).json({
            error: 'Recommendation failed',
            detail: error.message
        });
    }
});

/**
 * GET /api/prediction/species/:taxon_id/habitat-match
 *
 * Check how well a specific species matches a location's habitat.
 * Useful for "Can I plant this specific species here?" questions.
 */
router.get('/species/:taxon_id/habitat-match', async (req, res) => {
    try {
        const { taxon_id } = req.params;
        const { lat, lon } = req.query;

        if (!lat || !lon) {
            return res.status(400).json({
                error: 'Missing required parameters: lat, lon'
            });
        }

        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);

        // Get location embedding
        let embedding, locationData;
        try {
            const sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                params: { lat: latitude, lon: longitude },
                timeout: 30000
            });
            embedding = sampleResponse.data.alphaearth_embedding;
            locationData = sampleResponse.data;
        } catch (error) {
            return res.status(503).json({
                error: 'Cannot get habitat embedding for location'
            });
        }

        if (!embedding || embedding.length !== 64) {
            return res.status(400).json({
                error: 'Invalid embedding from location predictor'
            });
        }

        const vectorString = `[${embedding.join(',')}]`;

        // Query habitat match for this specific species
        const query = `
            SELECT
                c.taxon_id,
                c.cluster_id,
                1 - (c.centroid_vector <=> $1::vector) as similarity,
                c.mean_elevation,
                c.occurrence_count,
                c.mean_treecover2000,
                c.forest_loss_fraction,
                c.representative_lat,
                c.representative_lon,
                s.accepted_scientific_name,
                s.common_name,
                s.wcvp_native,
                s.wcvp_introduced
            FROM species_habitat_centroids c
            LEFT JOIN species s ON c.taxon_id = s.taxon_id
            WHERE c.taxon_id = $2
            ORDER BY c.centroid_vector <=> $1::vector
        `;

        const result = await pool.query(query, [vectorString, taxon_id]);

        if (result.rows.length === 0) {
            return res.status(404).json({
                error: 'Species not found or no habitat data available',
                taxon_id
            });
        }

        const bestMatch = result.rows[0];
        const allClusters = result.rows;

        // Determine match quality
        const similarity = parseFloat(bestMatch.similarity);
        let match_quality;
        if (similarity >= 0.9) match_quality = 'excellent';
        else if (similarity >= 0.8) match_quality = 'good';
        else if (similarity >= 0.7) match_quality = 'moderate';
        else if (similarity >= 0.6) match_quality = 'marginal';
        else match_quality = 'poor';

        res.json({
            success: true,
            taxon_id,
            scientific_name: bestMatch.accepted_scientific_name,
            common_name: bestMatch.common_name,

            location: {
                latitude,
                longitude,
                elevation: locationData.elevation
            },

            habitat_match: {
                quality: match_quality,
                similarity: parseFloat(similarity.toFixed(4)),
                suitability_score: Math.round(similarity * 100),
                best_cluster: {
                    id: bestMatch.cluster_id,
                    elevation: bestMatch.mean_elevation,
                    treecover: bestMatch.mean_treecover2000,
                    occurrences: bestMatch.occurrence_count,
                    representative_location: {
                        lat: bestMatch.representative_lat,
                        lon: bestMatch.representative_lon
                    }
                },
                all_clusters: allClusters.map(c => ({
                    cluster_id: c.cluster_id,
                    similarity: parseFloat(parseFloat(c.similarity).toFixed(4)),
                    elevation: c.mean_elevation,
                    occurrences: c.occurrence_count
                }))
            },

            native_status: {
                native_regions: bestMatch.wcvp_native,
                introduced_regions: bestMatch.wcvp_introduced
            }
        });

    } catch (error) {
        console.error('Habitat match endpoint error:', error);
        res.status(500).json({
            error: 'Habitat match query failed',
            detail: error.message
        });
    }
});

/**
 * POST /api/prediction/from-embedding
 *
 * Predict species from a raw embedding vector (backwards compatible with frontend).
 * Accepts embedding as either:
 *   - Array: [0.1, 0.2, ..., 0.9] (64 elements)
 *   - Object: {a00: 0.1, a01: 0.2, ..., a63: 0.9}
 *
 * This replaces the old /api/embeddings/predict endpoint with the new
 * 17,924 species database and pgvector IVFFlat index.
 */
router.post('/from-embedding', async (req, res) => {
    try {
        const { embedding, limit = 10 } = req.body;

        if (!embedding) {
            return res.status(400).json({ error: 'Missing required field: embedding' });
        }

        // Convert embedding to array format if it's an object
        let embeddingArray;
        if (Array.isArray(embedding)) {
            embeddingArray = embedding;
        } else if (typeof embedding === 'object') {
            // Convert {a00: 0.1, a01: 0.2, ...} to [0.1, 0.2, ...]
            embeddingArray = [];
            for (let i = 0; i < 64; i++) {
                const key = `a${i.toString().padStart(2, '0')}`;
                if (!(key in embedding)) {
                    return res.status(400).json({
                        error: 'Incomplete embedding vector',
                        missing_key: key
                    });
                }
                embeddingArray.push(parseFloat(embedding[key]));
            }
        } else {
            return res.status(400).json({
                error: 'Invalid embedding format. Expected array or object.'
            });
        }

        if (embeddingArray.length !== 64) {
            return res.status(400).json({
                error: `Invalid embedding length: ${embeddingArray.length}. Expected 64.`
            });
        }

        console.log(`POST /api/prediction/from-embedding (limit=${limit})`);

        // Convert to pgvector format
        const vectorString = `[${embeddingArray.join(',')}]`;
        const resultLimit = Math.min(parseInt(limit), 100);

        // Query using pgvector cosine similarity with IVFFlat index
        const query = `
            WITH ranked_centroids AS (
                SELECT
                    c.taxon_id,
                    c.cluster_id,
                    1 - (c.centroid_vector <=> $1::vector) as similarity,
                    c.mean_elevation,
                    c.occurrence_count,
                    c.mean_treecover2000,
                    c.forest_loss_fraction,
                    c.representative_lat,
                    c.representative_lon,
                    c.is_single_cluster,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.taxon_id
                        ORDER BY c.centroid_vector <=> $1::vector
                    ) as rank_in_species
                FROM species_habitat_centroids c
            )
            SELECT
                r.taxon_id,
                r.cluster_id,
                r.similarity,
                r.mean_elevation as cluster_elevation,
                r.occurrence_count as cluster_size,
                r.mean_treecover2000,
                r.forest_loss_fraction,
                r.representative_lat,
                r.representative_lon,
                r.is_single_cluster,
                s.taxon_full,
                s.common_name,
                s.family,
                (SELECT SUM(occurrence_count) FROM species_habitat_centroids WHERE taxon_id = r.taxon_id) as total_occurrences,
                (SELECT COUNT(*) FROM species_habitat_centroids WHERE taxon_id = r.taxon_id) as habitat_count
            FROM ranked_centroids r
            LEFT JOIN species s ON r.taxon_id = s.taxon_id
            WHERE r.rank_in_species = 1
              AND r.similarity >= 0.5
            ORDER BY r.similarity DESC
            LIMIT $2
        `;

        const result = await pool.query(query, [vectorString, resultLimit * 2]);

        if (result.rowCount === 0) {
            return res.status(404).json({
                error: 'No species predictions available',
                details: 'No matching habitats found'
            });
        }

        // Normalize confidence scores
        const maxSimilarity = parseFloat(result.rows[0].similarity);

        // Format predictions to match frontend expectations
        const predictions = result.rows.slice(0, resultLimit).map(row => ({
            taxon_id: row.taxon_id,
            taxon_full: row.taxon_full,
            common_name: row.common_name,
            family: row.family,
            cluster_id: row.cluster_id,
            cluster_size: parseInt(row.cluster_size),
            total_occurrences: parseInt(row.total_occurrences),
            representative_lat: parseFloat(row.representative_lat),
            representative_lon: parseFloat(row.representative_lon),
            similarity_score: row.similarity.toFixed(6),
            confidence: maxSimilarity > 0 ? parseFloat(row.similarity) / maxSimilarity : 0,
            habitat_count: parseInt(row.habitat_count),
            is_single_cluster: row.is_single_cluster,
            // Additional metadata
            cluster_elevation: row.cluster_elevation,
            mean_treecover2000: row.mean_treecover2000,
            forest_loss_fraction: row.forest_loss_fraction
        }));

        console.log(`Found ${predictions.length} species predictions (from ${result.rowCount} candidates)`);
        console.log(`Top prediction: ${predictions[0].taxon_full} (confidence: ${predictions[0].confidence.toFixed(4)})`);

        res.json({
            success: true,
            prediction_count: predictions.length,
            predictions
        });

    } catch (error) {
        console.error('From-embedding prediction error:', error);
        res.status(500).json({
            error: 'Prediction failed',
            detail: error.message
        });
    }
});

/**
 * POST /api/prediction/polygon
 *
 * Predict species suitable for an entire polygon/AOI.
 * Samples multiple points within the polygon, gets embeddings, and aggregates predictions.
 *
 * Body:
 * - geometry: GeoJSON Polygon { type: 'Polygon', coordinates: [...] }
 * - sample_count: Number of points to sample within polygon (default: 9, max: 25)
 * - limit: Max species to return (default: 20, max: 50)
 * - strategy: 'random' | 'grid' (default: 'grid')
 *
 * Response includes:
 * - Species ranked by average suitability across all sample points
 * - Species coverage (% of sample points where species is suitable)
 * - Variability in suitability across the AOI
 */
router.post('/polygon', async (req, res) => {
    try {
        const {
            geometry,
            sample_count = 9,
            strategy = 'grid',
            min_similarity = 0.7  // 70% threshold - filters out marginal matches
        } = req.body;

        if (!geometry || geometry.type !== 'Polygon') {
            return res.status(400).json({
                error: 'Invalid geometry',
                detail: 'Expected GeoJSON Polygon with type and coordinates'
            });
        }

        const sampleCount = Math.min(Math.max(parseInt(sample_count), 1), 25);
        // No hard limit - return all species above threshold (limit only used for initial query per point)

        // Calculate bounding box from polygon
        const coords = geometry.coordinates[0]; // Outer ring
        const lngs = coords.map(c => c[0]);
        const lats = coords.map(c => c[1]);
        const minLng = Math.min(...lngs);
        const maxLng = Math.max(...lngs);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);

        // Get ecoregions intersecting the polygon for native status determination
        const geoJsonString = JSON.stringify(geometry);
        let ecoregions = [];
        let countries = [];
        let wcvpPatterns = [];

        try {
            const ecoResult = await pool.query(`
                WITH input_geom AS (
                    SELECT ST_SetSRID(ST_GeomFromGeoJSON($1), 4326) as geom
                ),
                intersections AS (
                    SELECT
                        e.eco_id, e.eco_name, e.biome_name, e.realm,
                        ST_Area(ST_Intersection(e.geom, i.geom)::geography) as intersection_area
                    FROM ecoregions e, input_geom i
                    WHERE ST_Intersects(e.geom, i.geom)
                ),
                total_area AS (
                    SELECT SUM(intersection_area) as total FROM intersections
                )
                SELECT
                    i.*,
                    CASE WHEN t.total > 0 THEN i.intersection_area / t.total ELSE 1.0 END as weight
                FROM intersections i, total_area t
                ORDER BY weight DESC
                LIMIT 10
            `, [geoJsonString]);
            ecoregions = ecoResult.rows;

            if (ecoregions.length > 0) {
                // Get countries for these ecoregions
                const ecoIds = ecoregions.map(e => e.eco_id);
                const countriesResult = await pool.query(`
                    SELECT DISTINCT
                        CASE
                            WHEN c.name_en = 'United States of America' THEN 'United States'
                            WHEN c.name_en = 'United Kingdom' THEN 'United Kingdom'
                            ELSE c.name_en
                        END as country_name
                    FROM ecoregions e
                    JOIN countries c ON ST_Intersects(e.geom, c.geom)
                    WHERE e.eco_id = ANY($1)
                `, [ecoIds]);
                countries = countriesResult.rows.map(r => r.country_name).filter(Boolean);

                // Build WCVP search patterns
                const { getWcvpRegionsForCountry } = require('../utils/wcvpRegions');
                for (const country of countries) {
                    const regions = getWcvpRegionsForCountry(country);
                    wcvpPatterns.push(...regions.map(r => r.toLowerCase()));
                }
            }
        } catch (ecoError) {
            console.log('Ecoregion lookup failed (non-fatal):', ecoError.message);
        }

        // Point-in-polygon test helper
        const pointInPolygon = (lng, lat) => {
            let inside = false;
            for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
                const xi = coords[i][0], yi = coords[i][1];
                const xj = coords[j][0], yj = coords[j][1];
                if (((yi > lat) !== (yj > lat)) && (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi)) {
                    inside = !inside;
                }
            }
            return inside;
        };

        // Generate sample points within polygon
        const samplePoints = [];
        if (strategy === 'grid') {
            // Grid sampling: create regular grid and filter to polygon
            const gridSize = Math.ceil(Math.sqrt(sampleCount * 2)); // Oversample to account for filtering
            const latStep = (maxLat - minLat) / (gridSize + 1);
            const lngStep = (maxLng - minLng) / (gridSize + 1);

            for (let i = 1; i <= gridSize && samplePoints.length < sampleCount; i++) {
                for (let j = 1; j <= gridSize && samplePoints.length < sampleCount; j++) {
                    const lat = minLat + latStep * i;
                    const lng = minLng + lngStep * j;
                    if (pointInPolygon(lng, lat)) {
                        samplePoints.push({ lat, lng });
                    }
                }
            }
        } else {
            // Random sampling within polygon bounds
            let attempts = 0;
            while (samplePoints.length < sampleCount && attempts < sampleCount * 10) {
                const lat = minLat + Math.random() * (maxLat - minLat);
                const lng = minLng + Math.random() * (maxLng - minLng);
                if (pointInPolygon(lng, lat)) {
                    samplePoints.push({ lat, lng });
                }
                attempts++;
            }
        }

        if (samplePoints.length === 0) {
            return res.status(400).json({
                error: 'No valid sample points',
                detail: 'Could not generate sample points within polygon'
            });
        }

        console.log(`Polygon prediction: ${samplePoints.length} sample points`);

        // Get embeddings for all sample points (in parallel, but rate-limited)
        const embeddingResults = [];
        const batchSize = 3; // Process 3 at a time to avoid overwhelming GEE

        for (let i = 0; i < samplePoints.length; i += batchSize) {
            const batch = samplePoints.slice(i, i + batchSize);
            const batchPromises = batch.map(async (point) => {
                try {
                    const response = await axios.post(`${LOCATION_PREDICTOR_URL}/sample`, {
                        lat: point.lat,
                        lon: point.lng,
                        year: 2024
                    }, { timeout: 60000 });

                    if (response.data.success && response.data.embedding) {
                        return {
                            point,
                            embedding: response.data.embedding,
                            elevation: response.data.elevation,
                            success: true
                        };
                    }
                    return { point, success: false };
                } catch (error) {
                    console.log(`Sample point ${point.lat.toFixed(4)}, ${point.lng.toFixed(4)} failed: ${error.message}`);
                    return { point, success: false };
                }
            });

            const batchResults = await Promise.all(batchPromises);
            embeddingResults.push(...batchResults);
        }

        const successfulSamples = embeddingResults.filter(r => r.success);
        console.log(`${successfulSamples.length}/${samplePoints.length} sample points succeeded`);

        if (successfulSamples.length === 0) {
            return res.status(503).json({
                error: 'No embeddings obtained',
                detail: 'Could not get habitat data for any sample points. The area may be over water or outside satellite coverage.'
            });
        }

        // Query species predictions for each embedding and aggregate
        const speciesScores = new Map(); // taxon_id -> { scores: [], details: {} }

        for (const sample of successfulSamples) {
            // Convert embedding dict {a00: val, a01: val, ...} to array in correct order
            let embeddingArray;
            if (Array.isArray(sample.embedding)) {
                embeddingArray = sample.embedding;
            } else if (typeof sample.embedding === 'object') {
                // Sort keys (a00, a01, ..., a63) and extract values
                const keys = Object.keys(sample.embedding).sort();
                embeddingArray = keys.map(k => sample.embedding[k]);
            } else {
                console.log('Unknown embedding format:', typeof sample.embedding);
                continue;
            }
            const vectorString = `[${embeddingArray.join(',')}]`;

            const query = `
                WITH ranked_centroids AS (
                    SELECT
                        c.taxon_id,
                        c.cluster_id,
                        1 - (c.centroid_vector <=> $1::vector) as similarity,
                        c.mean_elevation,
                        c.occurrence_count,
                        c.representative_lat,
                        c.representative_lon,
                        ROW_NUMBER() OVER (
                            PARTITION BY c.taxon_id
                            ORDER BY c.centroid_vector <=> $1::vector
                        ) as rank_in_species
                    FROM species_habitat_centroids c
                )
                SELECT
                    r.taxon_id,
                    r.similarity,
                    r.mean_elevation,
                    r.occurrence_count,
                    s.accepted_scientific_name,
                    s.common_name,
                    s.family,
                    COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                    s.wcvp_native,
                    s.wcvp_introduced,
                    s.countries_invasive
                FROM ranked_centroids r
                LEFT JOIN species s ON r.taxon_id = s.taxon_id
                WHERE r.rank_in_species = 1
                  AND r.similarity >= $2
                ORDER BY r.similarity DESC
            `;

            try {
                const result = await pool.query(query, [vectorString, parseFloat(min_similarity)]);

                for (const row of result.rows) {
                    if (!speciesScores.has(row.taxon_id)) {
                        speciesScores.set(row.taxon_id, {
                            scores: [],
                            details: {
                                taxon_id: row.taxon_id,
                                scientific_name: row.accepted_scientific_name,
                                common_name: row.common_name,
                                family: row.family,
                                growth_form: row.growth_form,
                                wcvp_native: row.wcvp_native,
                                wcvp_introduced: row.wcvp_introduced,
                                countries_invasive: row.countries_invasive
                            }
                        });
                    }
                    speciesScores.get(row.taxon_id).scores.push(parseFloat(row.similarity));
                }
            } catch (error) {
                console.error(`Query error for sample point: ${error.message}`);
            }
        }

        // Calculate aggregated scores
        const aggregatedPredictions = [];
        const totalSamples = successfulSamples.length;

        // Helper function to check if species matches any WCVP pattern
        const matchesWcvpPatterns = (wcvpField) => {
            if (!wcvpField || wcvpPatterns.length === 0) return false;
            const fieldLower = wcvpField.toLowerCase();
            return wcvpPatterns.some(pattern => fieldLower.includes(pattern));
        };

        // Helper function to check if invasive in any of the countries
        const isInvasiveInCountries = (invasiveField) => {
            if (!invasiveField || countries.length === 0) return false;
            const invasiveLower = invasiveField.toLowerCase();
            return countries.some(country => invasiveLower.includes(country.toLowerCase()));
        };

        for (const [, data] of speciesScores) {
            const scores = data.scores;
            const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
            const coverage = scores.length / totalSamples;
            const minScore = Math.min(...scores);
            const maxScore = Math.max(...scores);
            const variability = maxScore - minScore;

            // Combined ranking: weight average score (60%) + coverage (40%)
            const combinedScore = avgScore * 0.6 + coverage * 0.4;

            // Determine native status for this location
            const isNative = matchesWcvpPatterns(data.details.wcvp_native);
            const isIntroduced = matchesWcvpPatterns(data.details.wcvp_introduced);
            const isInvasive = isInvasiveInCountries(data.details.countries_invasive);

            // Determine overall native_status
            let native_status = 'unknown';
            if (isInvasive) {
                native_status = 'invasive';
            } else if (isNative && !isIntroduced) {
                native_status = 'native';
            } else if (isIntroduced && !isNative) {
                native_status = 'introduced';
            } else if (isNative && isIntroduced) {
                native_status = 'native_and_introduced';  // Species is both native and introduced in different parts
            }

            aggregatedPredictions.push({
                taxon_id: data.details.taxon_id,
                scientific_name: data.details.scientific_name,
                common_name: data.details.common_name,
                family: data.details.family,
                growth_form: data.details.growth_form,
                native_status,
                is_native: isNative,
                is_introduced: isIntroduced,
                is_invasive: isInvasive,
                avg_suitability: Math.round(avgScore * 100),
                coverage_percent: Math.round(coverage * 100),
                coverage_points: scores.length,
                total_points: totalSamples,
                score_range: {
                    min: Math.round(minScore * 100),
                    max: Math.round(maxScore * 100),
                    variability: Math.round(variability * 100)
                },
                combined_score: parseFloat(combinedScore.toFixed(4))
            });
        }

        // Sort by combined score - return ALL species above threshold
        aggregatedPredictions.sort((a, b) => b.combined_score - a.combined_score);

        // Calculate polygon area (approximate, using average lat)
        const centerLat = (minLat + maxLat) / 2;
        const latFactor = 111.32; // km per degree latitude
        const lngFactor = 111.32 * Math.cos(centerLat * Math.PI / 180); // km per degree longitude
        const approxWidthKm = (maxLng - minLng) * lngFactor;
        const approxHeightKm = (maxLat - minLat) * latFactor;
        const approxAreaKm2 = approxWidthKm * approxHeightKm * 0.7; // Rough approximation

        // Calculate native status summary
        const nativeStatusSummary = {
            native: aggregatedPredictions.filter(p => p.native_status === 'native').length,
            introduced: aggregatedPredictions.filter(p => p.native_status === 'introduced').length,
            invasive: aggregatedPredictions.filter(p => p.native_status === 'invasive').length,
            native_and_introduced: aggregatedPredictions.filter(p => p.native_status === 'native_and_introduced').length,
            unknown: aggregatedPredictions.filter(p => p.native_status === 'unknown').length
        };

        res.json({
            success: true,
            polygon_summary: {
                bounds: { minLat, maxLat, minLng, maxLng },
                approx_area_km2: Math.round(approxAreaKm2 * 100) / 100,
                sample_strategy: strategy,
                sample_points_requested: sampleCount,
                sample_points_succeeded: successfulSamples.length
            },
            location_context: {
                ecoregions: ecoregions.map(e => ({
                    eco_id: e.eco_id,
                    eco_name: e.eco_name,
                    biome_name: e.biome_name,
                    realm: e.realm,
                    weight: Math.round(parseFloat(e.weight) * 1000) / 1000
                })),
                countries: countries
            },
            sample_points: successfulSamples.map(s => ({
                lat: s.point.lat,
                lng: s.point.lng,
                elevation: s.elevation
            })),
            results: {
                species_count: aggregatedPredictions.length,
                native_status_summary: nativeStatusSummary,
                predictions: aggregatedPredictions
            }
        });

    } catch (error) {
        console.error('Polygon prediction error:', error);
        res.status(500).json({
            error: 'Polygon prediction failed',
            detail: error.message
        });
    }
});

/**
 * GET /api/prediction/health
 *
 * Health check for the prediction service.
 */
router.get('/health', async (req, res) => {
    const health = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        services: {}
    };

    // Check PostgreSQL
    try {
        const pgResult = await pool.query('SELECT COUNT(*) FROM species_habitat_centroids');
        health.services.postgresql = {
            status: 'healthy',
            centroid_count: parseInt(pgResult.rows[0].count)
        };
    } catch (error) {
        health.services.postgresql = {
            status: 'unhealthy',
            error: error.message
        };
        health.status = 'degraded';
    }

    // Check location predictor
    try {
        const predictorResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/health`, {
            timeout: 5000
        });
        health.services.location_predictor = {
            status: 'healthy',
            url: LOCATION_PREDICTOR_URL
        };
    } catch (error) {
        health.services.location_predictor = {
            status: 'unhealthy',
            error: 'Service unreachable',
            url: LOCATION_PREDICTOR_URL
        };
        health.status = 'degraded';
    }

    res.status(health.status === 'healthy' ? 200 : 503).json(health);
});

module.exports = router;
