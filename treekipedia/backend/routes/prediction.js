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
    database: 'treekipedia',
    // Uses default localhost:5432 and current user
});

/**
 * Normalize embedding from Python service to a 64-element array.
 * The Python service returns embedding as an object dict {a00: val, a01: val, ...}
 * but pgvector queries need a flat array [val, val, ...].
 *
 * Handles three formats:
 * 1. Array: [0.1, 0.2, ...] — pass through
 * 2. Object dict: {a00: 0.1, a01: 0.2, ...} — sort keys and extract values
 * 3. Legacy 'alphaearth_embedding' key — array format from older services
 */
function normalizeEmbedding(sampleData) {
    // Try the legacy key first (older Python service versions)
    let raw = sampleData.alphaearth_embedding || sampleData.embedding;

    if (!raw) return null;

    // If already an array, validate and return
    if (Array.isArray(raw)) {
        return raw.length === 64 ? raw : null;
    }

    // If object dict {a00: val, a01: val, ...}, convert to sorted array
    if (typeof raw === 'object') {
        const arr = [];
        for (let i = 0; i < 64; i++) {
            const key = `a${i.toString().padStart(2, '0')}`;
            if (!(key in raw) || raw[key] === null || raw[key] === undefined) {
                return null; // Incomplete embedding
            }
            arr.push(parseFloat(raw[key]));
        }
        return arr;
    }

    return null;
}

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
 * Multi-signal species prediction for a location.
 *
 * Uses 3 independent discovery channels to build a candidate pool,
 * then scores each candidate with a weighted multi-signal formula:
 *
 *   Signal 1: Embedding similarity (AlphaEarth pgvector cosine)
 *   Signal 2: Spatial proximity (geohash_species_tiles within 50km)
 *   Signal 3: Range confirmation (WCVP native/introduced for this country)
 *   Signal 4: Ecoregion co-occurrence (species recorded in this ecoregion)
 *   Signal 5: Climate envelope match (elevation, precipitation, temperature)
 *
 * This replaces the pure-embedding approach which failed for introduced species
 * whose training centroids don't resemble the planted habitat.
 *
 * Query Parameters:
 * - lat: Latitude (required)
 * - lon: Longitude (required)
 * - limit: Max species to return (default: 50, max: 200)
 */
router.get('/predict', async (req, res) => {
    try {
        const {
            lat,
            lon,
            limit = 100
        } = req.query;

        if (!lat || !lon) {
            return res.status(400).json({
                error: 'Missing required parameters: lat, lon'
            });
        }

        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);
        const resultLimit = Math.min(parseInt(limit), 200);

        console.log(`\n=== MULTI-SIGNAL PREDICT: ${latitude}, ${longitude} ===`);

        // Step 1: Get embedding from location predictor
        let embedding, locationData;
        try {
            let sampleResponse;
            try {
                sampleResponse = await axios.post(`${LOCATION_PREDICTOR_URL}/sample`, {
                    lat: latitude,
                    lon: longitude,
                    year: 2023
                }, { timeout: 60000 });
            } catch (postErr) {
                sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                    params: { lat: latitude, lon: longitude },
                    timeout: 30000
                });
            }
            locationData = sampleResponse.data;
            embedding = normalizeEmbedding(sampleResponse.data);
        } catch (error) {
            return res.status(503).json({
                error: 'Cannot get habitat embedding for location',
                detail: 'Location predictor service unavailable or location not covered',
                location: { lat: latitude, lon: longitude }
            });
        }

        const isDemoMode = locationData?.demo_mode || false;
        const elevation = locationData?.elevation || null;
        
        // Extract climate data from Python service (WorldClim BIO)
        const locationClimate = locationData?.climate || null;
        const locationTemperature = locationClimate?.annual_mean_temp_c ?? null;
        const locationPrecipitation = locationClimate?.annual_precipitation_mm ?? null;
        const locationKoppenCode = locationClimate?.koppen_code ?? null;
        const locationKoppenDesc = locationClimate?.koppen_description ?? null;
        
        // Extract soil data from Python service (OpenLandMap)
        const locationSoil = locationData?.soil || null;
        const locationSoilPh = locationSoil?.soil_ph ?? null;
        const locationSoilPhCategory = locationSoil?.soil_ph_category ?? null;
        const locationSoilTexture = locationSoil?.soil_texture ?? null;

        if (locationClimate) {
            console.log(`  Climate: temp=${locationTemperature}°C, precip=${locationPrecipitation}mm, koppen=${locationKoppenCode}`);
        }
        if (locationSoil) {
            console.log(`  Soil: pH=${locationSoilPh} (${locationSoilPhCategory}), texture=${locationSoilTexture}`);
        }

        // =====================================================================
        // Managed Forest Probability (MFP)
        // Computed from embedding homogeneity + canopy height uniformity + CCDC.
        // When MFP > 0.50, scoring shifts from "habitat suitability" mode toward
        // "species identification" mode: k-NN concentration matters more, centroid
        // fallback is penalized, introduced species with spatial evidence get a boost.
        // =====================================================================
        const embHomogeneity = locationData?.embedding_homogeneity ?? null;
        const canopyHeightMean = locationData?.canopy_height?.canopy_height_mean_m ?? null;
        const canopyHeightStddev = locationData?.canopy_height?.canopy_height_stddev_100m ?? null;
        const ccdcBreaks = locationData?.ccdc?.ccdc_num_breaks ?? null;

        let managedForestProb = 0;
        if (embHomogeneity != null && canopyHeightMean != null && canopyHeightStddev != null) {
            const heightCv = canopyHeightMean > 0 ? canopyHeightStddev / canopyHeightMean : 1.0;

            // Component 1: Spatial embedding homogeneity (0.80→0, 0.95→1)
            const homogSignal = Math.max(0, Math.min(1, (embHomogeneity - 0.80) / 0.15));

            // Component 2: Canopy height uniformity (CV 0.30→0, CV 0→1)
            // Natural forest CV typically 0.20-0.50, plantation 0.05-0.12
            const canopySignal = Math.max(0, Math.min(1, 1.0 - heightCv / 0.30));

            // Component 3: Tall canopy (>15m) strengthens managed signal
            const heightSignal = canopyHeightMean > 15 ? 1.0 : canopyHeightMean / 15.0;

            // Component 4: CCDC stability modifier
            // 0 breaks = ambiguous (undisturbed native OR stable plantation) → reduce confidence
            // 1+ breaks = management activity → full confidence
            const stabilityFactor = (ccdcBreaks == null || ccdcBreaks === 0) ? 0.8 : 1.0;

            managedForestProb = Math.min(1.0,
                (0.40 * homogSignal + 0.35 * canopySignal + 0.25 * heightSignal) * stabilityFactor
            );
        }
        const isManagedForest = managedForestProb > 0.50;
        if (managedForestProb > 0) {
            console.log(`  MFP: ${managedForestProb.toFixed(3)} (managed=${isManagedForest})`);
            if (canopyHeightMean != null && canopyHeightStddev != null) {
                console.log(`    homog=${embHomogeneity}, height_cv=${(canopyHeightStddev / canopyHeightMean).toFixed(3)}, height=${canopyHeightMean}m, ccdc_breaks=${ccdcBreaks}`);
            }
        }

        if (!embedding || embedding.length !== 64) {
            return res.status(400).json({
                error: 'Invalid embedding from location predictor',
                detail: `Expected 64-dimensional AlphaEarth embedding, got: ${embedding ? embedding.length : 'null'}`,
                demo_mode: isDemoMode
            });
        }

        // Step 1b: Fire SINR v3 inference in parallel (doesn't block candidate discovery)
        let sinrPredictions = new Map(); // taxon_id → { prob_native, prob_introduced, prob_best, rank }
        let sinrAvailable = false;
        let sinrModelVersion = null;
        const sinrPromise = (async () => {
            try {
                const sinrResponse = await axios.post(`${LOCATION_PREDICTOR_URL}/sinr-infer`, {
                    lat: latitude,
                    lon: longitude,
                    year: 2023,
                    sample_data: locationData,
                    top_k: 500,
                    two_pass: true
                }, { timeout: 120000 });
                if (sinrResponse.data?.success && sinrResponse.data?.predictions) {
                    for (const pred of sinrResponse.data.predictions) {
                        sinrPredictions.set(pred.taxon_id, pred);
                    }
                    sinrAvailable = true;
                    sinrModelVersion = sinrResponse.data.model_version || 'unknown';
                    console.log(`  SINR ${sinrModelVersion}: ${sinrResponse.data.predictions.length} species predicted in ${sinrResponse.data.timing?.inference_ms || '?'}ms`);
                }
            } catch (err) {
                console.log(`  SINR inference unavailable: ${err.message}`);
            }
        })();

        // Step 2: Get location context (ecoregion + country)
        let ecoregion = null;
        let countries = [];
        let wcvpPatterns = [];

        try {
            const ecoResult = await pool.query(`
                SELECT eco_name, biome_name, realm, eco_id
                FROM ecoregions
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
                ORDER BY ST_Area(geom) ASC
                LIMIT 1
            `, [longitude, latitude]);

            if (ecoResult.rows.length > 0) {
                ecoregion = ecoResult.rows[0];

                const countriesResult = await pool.query(`
                    SELECT DISTINCT
                        CASE
                            WHEN c.name_en = 'United States of America' THEN 'United States'
                            WHEN c.name_en = 'United Kingdom' THEN 'United Kingdom'
                            ELSE c.name_en
                        END as country_name
                    FROM countries c
                    WHERE ST_Intersects(c.geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
                `, [longitude, latitude]);
                countries = countriesResult.rows.map(r => r.country_name).filter(Boolean);

                try {
                    const { getWcvpRegionsForCountry } = require('../utils/wcvpRegions');
                    for (const country of countries) {
                        const regions = getWcvpRegionsForCountry(country);
                        wcvpPatterns.push(...regions.map(r => r.toLowerCase()));
                    }
                } catch (e) { /* non-fatal */ }
            }
        } catch (ecoError) {
            console.log('Ecoregion lookup failed (non-fatal):', ecoError.message);
        }

        // =====================================================================
        // Step 3: MULTI-SOURCE CANDIDATE DISCOVERY
        // Three independent channels, merged into a single candidate pool.
        // =====================================================================

        const candidateMap = new Map(); // taxon_id -> candidate data

        const addCandidate = (taxon_id, source, data) => {
            if (!candidateMap.has(taxon_id)) {
                candidateMap.set(taxon_id, {
                    taxon_id,
                    sources: new Set(),
                    embedding_similarity: 0,
                    spatial_proximity_score: 0,
                    spatial_tile_count: 0,
                    spatial_min_distance: Infinity,
                    wcvp_native: false,
                    wcvp_introduced: false,
                    ecoregion_match: false,
                    ...data
                });
            }
            const c = candidateMap.get(taxon_id);
            c.sources.add(source);
            // Merge data (later sources don't overwrite earlier non-null/zero/false/Infinity values)
            for (const [key, value] of Object.entries(data)) {
                if (value != null && (c[key] == null || c[key] === 0 || c[key] === false || c[key] === Infinity)) {
                    c[key] = value;
                }
            }
        };

        // --- Channel 1a: k-NN occurrence matching (primary) ---
        // Uses HNSW index on species_occurrence_embeddings (11.4M individual points).
        // Returns top-500 nearest occurrences as RAW per-subtaxon rows (no IDF in SQL).
        //
        // Three key improvements over naive k-NN:
        //   1. Subtaxa merging: Accumulates votes at species-root level (e.g., all
        //      GymPiPiPnCx50820-* variants combine), reports best subtaxon as detail.
        //   2. Context-dependent IDF: IDF is applied in JS, modulated by embedding
        //      homogeneity — high homogeneity (monoculture signal) softens IDF so
        //      common plantation species aren't crushed.
        //   3. Multi-scale blending: top-50 fine-scale votes (local specificity) are
        //      blended with full top-500 broad votes (regional coverage).
        const vectorString = `[${embedding.join(',')}]`;
        let knnSpeciesSet = new Set(); // Track species roots found by k-NN
        let idfFactor = 1.0; // Hoisted: will be set inside Channel 1a based on embedding homogeneity
        try {
            await pool.query('SET hnsw.ef_search = 200');
            // Return per-subtaxon aggregates WITHOUT IDF (raw_vote = SUM(sim * density * quality))
            // Also return the row's rank within the 500 nearest for multi-scale splitting
            const knnResult = await pool.query(`
                WITH nearest AS (
                    SELECT
                        oe.taxon_id,
                        1 - (oe.embedding <=> $1::vector) AS similarity,
                        oe.density_weight,
                        oe.quality_weight,
                        oe.source_type,
                        oe.elevation,
                        oe.latitude,
                        oe.longitude,
                        ROW_NUMBER() OVER (ORDER BY oe.embedding <=> $1::vector) AS neighbor_rank
                    FROM species_occurrence_embeddings oe
                    ORDER BY oe.embedding <=> $1::vector
                    LIMIT 500
                )
                SELECT
                    n.taxon_id,
                    COUNT(*) AS hit_count,
                    MAX(n.similarity) AS best_similarity,
                    AVG(n.similarity) AS mean_similarity,
                    SUM(n.similarity * n.density_weight * n.quality_weight) AS raw_vote,
                    SUM(CASE WHEN n.neighbor_rank <= 50 THEN n.similarity * n.density_weight * n.quality_weight ELSE 0 END) AS raw_vote_fine,
                    COUNT(CASE WHEN n.neighbor_rank <= 50 THEN 1 END) AS hit_count_fine,
                    AVG(n.elevation) AS avg_matched_elevation,
                    ARRAY_AGG(DISTINCT n.source_type) AS source_types,
                    os.total_occurrences,
                    os.total_unique_pixels,
                    os.data_quality_score,
                    os.idf_weight,
                    -- Species metadata
                    s.accepted_scientific_name, s.common_name, s.family, s.genus,
                    COALESCE(s.growth_form_human, s.growth_form_ai) AS growth_form,
                    COALESCE(s.maximum_height_human, s.maximum_height_ai) AS maximum_height,
                    s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                    COALESCE(s.conservation_status_human, s.conservation_status_ai) AS conservation_status,
                    s.ecoregions AS species_ecoregions,
                    s.annual_precipitation_mm, s.annual_temperature_range_c,
                    s.climate_type_koppengeiger,
                    -- Soil preferences from species table
                    s.ph_dominant,
                    s.ph_tolerated,
                    s.soil_texture_dominant,
                    s.soil_texture_tolerated
                FROM nearest n
                JOIN species_occurrence_stats os ON os.taxon_id = n.taxon_id
                LEFT JOIN species s ON n.taxon_id = s.taxon_id
                GROUP BY n.taxon_id, os.idf_weight, os.total_occurrences,
                         os.total_unique_pixels, os.data_quality_score,
                         s.accepted_scientific_name, s.common_name, s.family, s.genus,
                         s.growth_form_human, s.growth_form_ai,
                         s.maximum_height_human, s.maximum_height_ai,
                         s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                         s.conservation_status_human, s.conservation_status_ai,
                         s.ecoregions, s.annual_precipitation_mm,
                         s.annual_temperature_range_c, s.climate_type_koppengeiger,
                         s.ph_dominant, s.ph_tolerated,
                         s.soil_texture_dominant, s.soil_texture_tolerated
                ORDER BY raw_vote DESC
                LIMIT 300
            `, [vectorString]);

            // --- Subtaxa merging ---
            // Group subtaxon rows by species root (taxon_id minus trailing "-XX").
            // Accumulate: hit_count, raw_vote, raw_vote_fine, hit_count_fine.
            // Take max: best_similarity, mean_similarity (of best subtaxon).
            // Pick metadata from the subtaxon with highest raw_vote.
            const speciesRootMap = new Map(); // species_root -> merged data

            for (const row of knnResult.rows) {
                const taxonId = row.taxon_id;
                const speciesRoot = taxonId.replace(/-[0-9]{2}$/, '');
                const rawVote = parseFloat(row.raw_vote);
                const rawVoteFine = parseFloat(row.raw_vote_fine);
                const hitCount = parseInt(row.hit_count);
                const hitCountFine = parseInt(row.hit_count_fine);
                const bestSim = parseFloat(row.best_similarity);
                const meanSim = parseFloat(row.mean_similarity);
                const idfWeight = parseFloat(row.idf_weight);
                const totalOcc = parseInt(row.total_occurrences);

                if (!speciesRootMap.has(speciesRoot)) {
                    speciesRootMap.set(speciesRoot, {
                        species_root: speciesRoot,
                        best_subtaxon: taxonId,
                        best_subtaxon_vote: rawVote,
                        subtaxon_ids: [taxonId],
                        // Accumulated vote data
                        raw_vote: rawVote,
                        raw_vote_fine: rawVoteFine,
                        hit_count: hitCount,
                        hit_count_fine: hitCountFine,
                        best_similarity: bestSim,
                        mean_similarity: meanSim,
                        // Species-level IDF: use the subtaxon with most occurrences (most representative)
                        // We accumulate total_occurrences across subtaxa for combined IDF
                        total_occurrences_combined: totalOcc,
                        subtaxon_idf_weights: [{ taxonId, idf: idfWeight, occ: totalOcc }],
                        // Metadata from best subtaxon (will be overwritten if a better one appears)
                        metadata_row: row
                    });
                } else {
                    const merged = speciesRootMap.get(speciesRoot);
                    merged.subtaxon_ids.push(taxonId);
                    merged.raw_vote += rawVote;
                    merged.raw_vote_fine += rawVoteFine;
                    merged.hit_count += hitCount;
                    merged.hit_count_fine += hitCountFine;
                    merged.best_similarity = Math.max(merged.best_similarity, bestSim);
                    merged.mean_similarity = Math.max(merged.mean_similarity, meanSim);
                    merged.total_occurrences_combined += totalOcc;
                    merged.subtaxon_idf_weights.push({ taxonId, idf: idfWeight, occ: totalOcc });

                    // Track best subtaxon (highest raw_vote)
                    if (rawVote > merged.best_subtaxon_vote) {
                        merged.best_subtaxon = taxonId;
                        merged.best_subtaxon_vote = rawVote;
                        merged.metadata_row = row;
                    }
                }
            }

            // --- Context-dependent IDF + Multi-scale blending ---
            // Embedding homogeneity comes from the Python service (when available).
            // homogeneity > 0.90 suggests monoculture → soften IDF (don't crush common species).
            // homogeneity < 0.85 suggests mixed forest → keep IDF strong (reward rarity).
            const embHomogeneity = locationData?.embedding_homogeneity ?? null;
            // IDF softening factor: 1.0 = full IDF, 0.0 = no IDF
            // Ramp: homogeneity 0.85 → idfFactor=1.0, 0.95 → idfFactor=0.3
            if (embHomogeneity != null && embHomogeneity > 0.85) {
                idfFactor = Math.max(0.3, 1.0 - (embHomogeneity - 0.85) * 7.0);
                // 0.85 → 1.0, 0.90 → 0.65, 0.95 → 0.30
            }

            for (const [speciesRoot, merged] of speciesRootMap) {
                const row = merged.metadata_row;

                // Compute species-level IDF from combined occurrences across all subtaxa
                const combinedOcc = merged.total_occurrences_combined;
                const speciesIdf = 1.0 / Math.log(1 + combinedOcc);

                // Context-dependent IDF: blend between full IDF and sqrt-dampened IDF
                // Full IDF: 1/log(1+n) — strongly penalizes common species
                // Dampened IDF: 1/log(1+sqrt(n)) — gentler, lets common species through
                const dampenedIdf = 1.0 / Math.log(1 + Math.sqrt(combinedOcc));
                const effectiveIdf = idfFactor * speciesIdf + (1.0 - idfFactor) * dampenedIdf;

                // Multi-scale blending: 40% fine-scale (k=50) + 60% broad (k=500)
                // Fine-scale captures precise local habitat match
                // Broad captures regional species pool presence
                const fineVote = merged.raw_vote_fine * effectiveIdf;
                const broadVote = merged.raw_vote * effectiveIdf;
                const blendedScore = 0.4 * fineVote + 0.6 * broadVote;

                // Use the best subtaxon's taxon_id as the canonical ID for downstream
                const canonicalTaxonId = merged.best_subtaxon;
                knnSpeciesSet.add(canonicalTaxonId);
                // Also add all subtaxon IDs so centroid fallback can detect overlap
                for (const stId of merged.subtaxon_ids) {
                    knnSpeciesSet.add(stId);
                }

                addCandidate(canonicalTaxonId, 'embedding', {
                    embedding_similarity: merged.best_similarity,
                    knn_weighted_score: blendedScore,
                    knn_raw_vote: merged.raw_vote,
                    knn_raw_vote_fine: merged.raw_vote_fine,
                    knn_effective_idf: effectiveIdf,
                    knn_hit_count: merged.hit_count,
                    knn_hit_count_fine: merged.hit_count_fine,
                    knn_mean_similarity: merged.mean_similarity,
                    knn_idf_weight: speciesIdf,
                    knn_source_types: row.source_types,
                    knn_total_occurrences: combinedOcc,
                    knn_subtaxa_count: merged.subtaxon_ids.length,
                    knn_subtaxa_ids: merged.subtaxon_ids,
                    knn_best_subtaxon: merged.best_subtaxon,
                    knn_species_root: speciesRoot,
                    cluster_elevation: row.avg_matched_elevation,
                    occurrence_count: combinedOcc,
                    scientific_name: row.accepted_scientific_name,
                    common_name: row.common_name,
                    family: row.family,
                    genus: row.genus,
                    growth_form: row.growth_form,
                    maximum_height: row.maximum_height,
                    wcvp_native_raw: row.wcvp_native,
                    wcvp_introduced_raw: row.wcvp_introduced,
                    countries_invasive_raw: row.countries_invasive,
                    conservation_status: row.conservation_status,
                    species_ecoregions: row.species_ecoregions,
                    annual_precipitation_mm: row.annual_precipitation_mm,
                    annual_temperature_range_c: row.annual_temperature_range_c,
                    climate_type_koppengeiger: row.climate_type_koppengeiger,
                    ph_dominant: row.ph_dominant,
                    ph_tolerated: row.ph_tolerated,
                    soil_texture_dominant: row.soil_texture_dominant,
                    soil_texture_tolerated: row.soil_texture_tolerated
                });
            }
            const multiSubtaxa = [...speciesRootMap.values()].filter(m => m.subtaxon_ids.length > 1);
            console.log(`  Channel 1a (k-NN): ${knnResult.rows.length} subtaxon rows → ${speciesRootMap.size} species (${multiSubtaxa.length} merged from multiple subtaxa)`);
            if (embHomogeneity != null) {
                console.log(`  IDF modulation: homogeneity=${embHomogeneity.toFixed(3)}, idfFactor=${idfFactor.toFixed(2)}`);
            }
        } catch (err) {
            console.error('  Channel 1a (k-NN) error:', err.message);
        }

        // --- Channel 1b: Centroid fallback (for species not in k-NN table) ---
        // The k-NN table has 22,603 species. The centroid table also has 22,603.
        // This catches species that may not appear in k-NN top-500 but have a
        // good centroid match, providing broader coverage.
        try {
            const centroidResult = await pool.query(`
                WITH ranked AS (
                    SELECT
                        c.taxon_id,
                        1 - (c.centroid_vector <=> $1::vector) as similarity,
                        c.cluster_id,
                        c.mean_elevation,
                        c.occurrence_count,
                        c.mean_treecover2000,
                        c.representative_lat,
                        c.representative_lon,
                        ROW_NUMBER() OVER (
                            PARTITION BY c.taxon_id
                            ORDER BY c.centroid_vector <=> $1::vector
                        ) as rank_in_species
                    FROM species_habitat_centroids c
                    WHERE 1 - (c.centroid_vector <=> $1::vector) >= 0.40
                )
                SELECT
                    r.taxon_id, r.similarity, r.cluster_id,
                    r.mean_elevation as cluster_elevation,
                    r.occurrence_count, r.mean_treecover2000,
                    r.representative_lat, r.representative_lon,
                    s.accepted_scientific_name, s.common_name, s.family, s.genus,
                    COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                    COALESCE(s.maximum_height_human, s.maximum_height_ai) as maximum_height,
                    s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                    COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status,
                    s.ecoregions as species_ecoregions,
                    s.annual_precipitation_mm, s.annual_temperature_range_c,
                    s.climate_type_koppengeiger,
                    s.ph_dominant,
                    s.ph_tolerated,
                    s.soil_texture_dominant,
                    s.soil_texture_tolerated
                FROM ranked r
                LEFT JOIN species s ON r.taxon_id = s.taxon_id
                WHERE r.rank_in_species = 1
                ORDER BY r.similarity DESC
                LIMIT 300
            `, [vectorString]);

            let centroidOnlyCount = 0;
            for (const row of centroidResult.rows) {
                // Only add if not already found by k-NN (avoid double-counting)
                const isNew = !knnSpeciesSet.has(row.taxon_id);
                if (isNew) centroidOnlyCount++;

                addCandidate(row.taxon_id, isNew ? 'centroid_fallback' : 'embedding', {
                    embedding_similarity: Math.max(
                        candidateMap.get(row.taxon_id)?.embedding_similarity || 0,
                        parseFloat(row.similarity)
                    ),
                    cluster_id: row.cluster_id,
                    cluster_elevation: row.cluster_elevation,
                    occurrence_count: row.occurrence_count,
                    cluster_treecover: row.mean_treecover2000,
                    representative_lat: row.representative_lat,
                    representative_lon: row.representative_lon,
                    scientific_name: row.accepted_scientific_name,
                    common_name: row.common_name,
                    family: row.family,
                    genus: row.genus,
                    growth_form: row.growth_form,
                    maximum_height: row.maximum_height,
                    wcvp_native_raw: row.wcvp_native,
                    wcvp_introduced_raw: row.wcvp_introduced,
                    countries_invasive_raw: row.countries_invasive,
                    conservation_status: row.conservation_status,
                    species_ecoregions: row.species_ecoregions,
                    annual_precipitation_mm: row.annual_precipitation_mm,
                    annual_temperature_range_c: row.annual_temperature_range_c,
                    climate_type_koppengeiger: row.climate_type_koppengeiger,
                    ph_dominant: row.ph_dominant,
                    ph_tolerated: row.ph_tolerated,
                    soil_texture_dominant: row.soil_texture_dominant,
                    soil_texture_tolerated: row.soil_texture_tolerated
                });
            }
            console.log(`  Channel 1b (centroid): ${centroidResult.rows.length} candidates (${centroidOnlyCount} new beyond k-NN)`);
        } catch (err) {
            console.error('  Channel 1b (centroid) error:', err.message);
        }

        // --- Channel 2: Spatial proximity (geohash_species_tiles) ---
        try {
            const spatialResult = await pool.query(`
                WITH nearby_tiles AS (
                    SELECT
                        species_data,
                        ST_Distance(
                            geometry::geography,
                            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                        ) as dist_m
                    FROM geohash_species_tiles
                    WHERE ST_DWithin(
                        geometry::geography,
                        ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                        50000
                    )
                )
                SELECT
                    key as taxon_id,
                    COUNT(*) as tile_count,
                    MIN(dist_m) as min_distance,
                    SUM(CASE
                        WHEN jsonb_typeof(value) = 'number' THEN value::text::float
                        WHEN jsonb_typeof(value) = 'object' THEN COALESCE((value->>'count')::float, 1)
                        ELSE 1
                    END) as total_occurrences
                FROM nearby_tiles,
                     jsonb_each(species_data) as kv(key, value)
                GROUP BY key
                ORDER BY tile_count DESC, min_distance ASC
                LIMIT 1000
            `, [longitude, latitude]);

            // Normalize spatial scores using log scale (more fair to mid-range species)
            // A species with 10+ tiles nearby is significant; 100+ is very strong
            for (const row of spatialResult.rows) {
                const tileCount = parseInt(row.tile_count);
                const minDist = parseFloat(row.min_distance);
                // Log-scale density with base 100 (better discrimination for plantation/introduced species)
                // 1 tile=0, 5 tiles≈0.245, 10 tiles≈0.35, 30 tiles≈0.518, 50 tiles≈0.594, 100 tiles≈0.70 (cap)
                const densityScore = Math.min(0.7, (Math.log10(Math.max(tileCount, 1)) / Math.log10(100)) * 0.7);
                // Distance bonus: closer = more significant
                const distBonus = minDist < 2000 ? 0.3 : (minDist < 10000 ? 0.25 : (minDist < 25000 ? 0.15 : (minDist < 40000 ? 0.08 : 0.03)));
                const spatialScore = Math.min(1.0, densityScore + distBonus);

                addCandidate(row.taxon_id, 'spatial', {
                    spatial_proximity_score: spatialScore,
                    spatial_tile_count: tileCount,
                    spatial_min_distance: minDist,
                    spatial_total_occurrences: parseFloat(row.total_occurrences) || 0
                });
            }
            console.log(`  Channel 2 (spatial): ${spatialResult.rows.length} species within 50km`);
        } catch (err) {
            console.error('  Channel 2 (spatial) error:', err.message);
        }

        // --- Channel 3: WCVP range + ecoregion match ---
        // For species found by spatial channel that lack species table data, fetch it
        const missingDataIds = [];
        for (const [taxonId, c] of candidateMap) {
            if (!c.scientific_name) missingDataIds.push(taxonId);
        }
        if (missingDataIds.length > 0) {
            try {
                const speciesResult = await pool.query(`
                    SELECT
                        taxon_id,
                        accepted_scientific_name, common_name, family, genus,
                        COALESCE(growth_form_human, growth_form_ai) as growth_form,
                        COALESCE(maximum_height_human, maximum_height_ai) as maximum_height,
                        wcvp_native, wcvp_introduced, countries_invasive,
                        COALESCE(conservation_status_human, conservation_status_ai) as conservation_status,
                        ecoregions as species_ecoregions,
                        annual_precipitation_mm, annual_temperature_range_c,
                        climate_type_koppengeiger,
                        ph_dominant, ph_tolerated,
                        soil_texture_dominant, soil_texture_tolerated
                    FROM species
                    WHERE taxon_id = ANY($1)
                `, [missingDataIds]);

                for (const row of speciesResult.rows) {
                    const c = candidateMap.get(row.taxon_id);
                    if (c) {
                        c.scientific_name = c.scientific_name || row.accepted_scientific_name;
                        c.common_name = c.common_name || row.common_name;
                        c.family = c.family || row.family;
                        c.genus = c.genus || row.genus;
                        c.growth_form = c.growth_form || row.growth_form;
                        c.maximum_height = c.maximum_height || row.maximum_height;
                        c.wcvp_native_raw = c.wcvp_native_raw || row.wcvp_native;
                        c.wcvp_introduced_raw = c.wcvp_introduced_raw || row.wcvp_introduced;
                        c.countries_invasive_raw = c.countries_invasive_raw || row.countries_invasive;
                        c.conservation_status = c.conservation_status || row.conservation_status;
                        c.species_ecoregions = c.species_ecoregions || row.species_ecoregions;
                        c.annual_precipitation_mm = c.annual_precipitation_mm || row.annual_precipitation_mm;
                        c.annual_temperature_range_c = c.annual_temperature_range_c || row.annual_temperature_range_c;
                        c.climate_type_koppengeiger = c.climate_type_koppengeiger || row.climate_type_koppengeiger;
                        c.ph_dominant = c.ph_dominant || row.ph_dominant;
                        c.ph_tolerated = c.ph_tolerated || row.ph_tolerated;
                        c.soil_texture_dominant = c.soil_texture_dominant || row.soil_texture_dominant;
                        c.soil_texture_tolerated = c.soil_texture_tolerated || row.soil_texture_tolerated;
                    }
                }
                console.log(`  Fetched species data for ${speciesResult.rows.length} spatial-only candidates`);
            } catch (err) {
                console.error('  Species data fetch error:', err.message);
            }
        }

        // Also fetch embedding similarity for spatial-only candidates that weren't in channel 1
        const spatialOnlyIds = [];
        for (const [taxonId, c] of candidateMap) {
            if (c.sources.has('spatial') && !c.sources.has('embedding')) {
                spatialOnlyIds.push(taxonId);
            }
        }
        if (spatialOnlyIds.length > 0) {
            try {
                const embLookup = await pool.query(`
                    SELECT DISTINCT ON (c.taxon_id)
                        c.taxon_id,
                        1 - (c.centroid_vector <=> $1::vector) as similarity,
                        c.cluster_id,
                        c.mean_elevation as cluster_elevation,
                        c.occurrence_count,
                        c.representative_lat,
                        c.representative_lon
                    FROM species_habitat_centroids c
                    WHERE c.taxon_id = ANY($2)
                    ORDER BY c.taxon_id, c.centroid_vector <=> $1::vector
                `, [vectorString, spatialOnlyIds]);

                for (const row of embLookup.rows) {
                    const c = candidateMap.get(row.taxon_id);
                    if (c) {
                        c.embedding_similarity = parseFloat(row.similarity);
                        c.cluster_id = row.cluster_id;
                        c.cluster_elevation = row.cluster_elevation;
                        c.occurrence_count = c.occurrence_count || row.occurrence_count;
                        c.representative_lat = c.representative_lat || row.representative_lat;
                        c.representative_lon = c.representative_lon || row.representative_lon;
                    }
                }
                console.log(`  Fetched embedding similarity for ${embLookup.rows.length} spatial-only candidates`);
            } catch (err) {
                console.error('  Embedding lookup error:', err.message);
            }
        }

        // =====================================================================
        // Step 3b: Await SINR v3 inference (fired in parallel with candidate discovery)
        // =====================================================================
        await sinrPromise;
        if (sinrAvailable) {
            // Add any SINR-predicted species that weren't found by other channels
            // (SINR may predict species that k-NN/spatial missed)
            let sinrOnlyAdded = 0;
            for (const [taxonId, pred] of sinrPredictions) {
                if (!candidateMap.has(taxonId) && (pred.prob_best || 0) > 0.001) {
                    // Need to look up species metadata from DB for SINR-only candidates
                    addCandidate(taxonId, 'sinr', {
                        scientific_name: pred.scientific_name || null,
                        common_name: pred.common_name || null,
                        sinr_prob: pred.prob_best || 0,
                        sinr_rank: pred.rank || 999
                    });
                    sinrOnlyAdded++;
                }
            }
            if (sinrOnlyAdded > 0) {
                console.log(`  SINR added ${sinrOnlyAdded} candidates not found by other channels`);
            }

            // Fetch metadata for SINR-only candidates that need it
            const sinrOnlyIds = [...candidateMap.entries()]
                .filter(([_, c]) => c.sources.size === 1 && c.sources.has('sinr') && !c.scientific_name)
                .map(([id, _]) => id);
            if (sinrOnlyIds.length > 0) {
                try {
                    const metaResult = await pool.query(`
                        SELECT taxon_id, species_scientific_name, common_name, family, genus,
                               growth_form_ai as growth_form, maximum_height_ai as maximum_height,
                               COALESCE(conservation_status_human, conservation_status_ai) as conservation_status, countries_native_wcvp, countries_introduced_wcvp,
                               countries_invasive, ecoregions,
                               annual_precipitation_mm_ai as annual_precipitation_mm,
                               annual_temperature_range_c_ai as annual_temperature_range_c,
                               climate_type_koppengeiger_ai as climate_type_koppengeiger,
                               ph_dominant, ph_tolerated,
                               soil_texture_dominant, soil_texture_tolerated
                        FROM species WHERE taxon_id = ANY($1)
                    `, [sinrOnlyIds]);
                    for (const row of metaResult.rows) {
                        const c = candidateMap.get(row.taxon_id);
                        if (c) {
                            c.scientific_name = c.scientific_name || row.species_scientific_name;
                            c.common_name = c.common_name || row.common_name;
                            c.family = c.family || row.family;
                            c.genus = c.genus || row.genus;
                            c.growth_form = row.growth_form;
                            c.maximum_height = row.maximum_height;
                            c.conservation_status = row.conservation_status;
                            c.wcvp_native_raw = row.countries_native_wcvp;
                            c.wcvp_introduced_raw = row.countries_introduced_wcvp;
                            c.countries_invasive_raw = row.countries_invasive;
                            c.species_ecoregions = row.ecoregions;
                            c.annual_precipitation_mm = row.annual_precipitation_mm;
                            c.annual_temperature_range_c = row.annual_temperature_range_c;
                            c.climate_type_koppengeiger = row.climate_type_koppengeiger;
                            c.ph_dominant = row.ph_dominant;
                            c.ph_tolerated = row.ph_tolerated;
                            c.soil_texture_dominant = row.soil_texture_dominant;
                            c.soil_texture_tolerated = row.soil_texture_tolerated;
                        }
                    }
                } catch (err) {
                    console.error('  SINR metadata lookup error:', err.message);
                }
            }
        }

        // =====================================================================
        // Step 4: MULTI-SIGNAL SCORING
        // =====================================================================

        const matchesWcvp = (wcvpField) => {
            if (!wcvpField || wcvpPatterns.length === 0) return false;
            return wcvpPatterns.some(p => wcvpField.toLowerCase().includes(p));
        };

        const predictions = [];

        for (const [taxonId, c] of candidateMap) {
            // Determine native/introduced status
            const isNative = matchesWcvp(c.wcvp_native_raw);
            const isIntroduced = matchesWcvp(c.wcvp_introduced_raw);
            const isInvasive = countries.length > 0 && c.countries_invasive_raw
                ? countries.some(co => (c.countries_invasive_raw || '').toLowerCase().includes(co.toLowerCase()))
                : false;

            let native_status = 'unknown';
            if (isInvasive) native_status = 'invasive';
            else if (isNative && !isIntroduced) native_status = 'native';
            else if (isIntroduced && !isNative) native_status = 'introduced';
            else if (isNative && isIntroduced) native_status = 'native_and_introduced';

            // Ecoregion match — supports partial credit for spatially-confirmed species
            let ecoregionMatch = 0; // 0 to 1 scale (was boolean)
            if (ecoregion && c.species_ecoregions) {
                const match = c.species_ecoregions.toLowerCase().includes(
                    ecoregion.eco_name.toLowerCase().substring(0, 15)
                );
                ecoregionMatch = match ? 1.0 : 0;
            }
            // Spatially-confirmed species get partial ecoregion credit even if not listed
            // (common for introduced/plantation species whose ecoregion DB entry only lists native range)
            if (ecoregionMatch === 0 && (c.spatial_tile_count || 0) >= 10) {
                ecoregionMatch = 0.5;
            } else if (ecoregionMatch === 0 && (c.spatial_tile_count || 0) >= 3) {
                ecoregionMatch = 0.25;
            }

            // Climate envelope match (elevation + temperature + precipitation)
            let climateScore = 0.5; // Default: unknown
            let climateSignals = 0;
            let climateSum = 0;

            // Sub-signal 1: Elevation match
            if (elevation != null && c.cluster_elevation != null) {
                const elevDiff = Math.abs(elevation - parseFloat(c.cluster_elevation));
                climateSum += Math.max(0, 1.0 - elevDiff / 1500);
                climateSignals++;
            }

            // Sub-signal 2: Precipitation match (species range vs location annual precip)
            if (locationPrecipitation != null && c.annual_precipitation_mm && c.annual_precipitation_mm !== 'NA') {
                try {
                    const parts = c.annual_precipitation_mm.split(';').map(s => parseFloat(s.trim()));
                    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
                        const [pMin, pMax] = parts;
                        const rangeWidth = Math.max(pMax - pMin, 100); // Minimum range width 100mm
                        if (locationPrecipitation >= pMin && locationPrecipitation <= pMax) {
                            climateSum += 1.0; // Perfect match
                        } else {
                            const dist = locationPrecipitation < pMin 
                                ? pMin - locationPrecipitation 
                                : locationPrecipitation - pMax;
                            climateSum += Math.max(0, 1.0 - dist / rangeWidth);
                        }
                        climateSignals++;
                    }
                } catch (e) {}
            }

            // Sub-signal 3: Temperature match (species range vs location annual mean temp)
            if (locationTemperature != null && c.annual_temperature_range_c && c.annual_temperature_range_c !== 'NA') {
                try {
                    const parts = c.annual_temperature_range_c.split(';').map(s => parseFloat(s.trim()));
                    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
                        const [tMin, tMax] = parts;
                        const rangeWidth = Math.max(tMax - tMin, 5); // Minimum range width 5°C
                        if (locationTemperature >= tMin && locationTemperature <= tMax) {
                            climateSum += 1.0; // Perfect match
                        } else {
                            const dist = locationTemperature < tMin 
                                ? tMin - locationTemperature 
                                : locationTemperature - tMax;
                            climateSum += Math.max(0, 1.0 - dist / rangeWidth);
                        }
                        climateSignals++;
                    }
                } catch (e) {}
            }

            // Sub-signal 4: Koppen-Geiger climate zone match
            if (locationKoppenCode && c.climate_type_koppengeiger && c.climate_type_koppengeiger !== 'NA') {
                // Species has semicolon-separated Koppen zones like "Af - Tropical rainforest; Am - Tropical monsoon"
                const speciesKoppens = c.climate_type_koppengeiger.split(';').map(s => {
                    const code = s.trim().split(' ')[0]; // Extract just the code: "Af", "Am", etc.
                    return code;
                }).filter(Boolean);
                
                if (speciesKoppens.length > 0) {
                    // Exact code match
                    if (speciesKoppens.includes(locationKoppenCode)) {
                        climateSum += 1.0;
                        climateSignals++;
                    } else {
                        // Partial match: same major group (first letter matches)
                        const locationGroup = locationKoppenCode[0]; // A, B, C, D, E
                        const hasGroupMatch = speciesKoppens.some(k => k[0] === locationGroup);
                        if (hasGroupMatch) {
                            climateSum += 0.6; // Same major climate group
                            climateSignals++;
                        } else {
                            // Adjacent groups (C/D are adjacent temperate-continental)
                            const adjacent = { 'C': 'D', 'D': 'C', 'A': 'C', 'B': 'C' };
                            const hasAdjacentMatch = speciesKoppens.some(k => 
                                k[0] === adjacent[locationGroup] || adjacent[k[0]] === locationGroup
                            );
                            if (hasAdjacentMatch) {
                                climateSum += 0.3;
                            } // else 0 — totally different climate
                            climateSignals++;
                        }
                    }
                }
            }

            if (climateSignals > 0) {
                climateScore = climateSum / climateSignals;
            }

            // Pre-compute key values needed for scoring
            const embSim = c.embedding_similarity || 0;
            const spatialProx = c.spatial_proximity_score || 0;
            const numSources = c.sources.size;
            const hasKnn = c.knn_weighted_score != null;

            // WCVP range score — but if species has strong spatial presence,
            // it's confirmed-present even without WCVP record (common for plantation species)
            let rangeScore = 0;
            if (isNative) rangeScore = 1.0;
            else if (isIntroduced && spatialProx >= 0.5) rangeScore = 0.95; // Introduced AND confirmed present
            else if (isIntroduced) rangeScore = 0.8;
            else if (spatialProx >= 0.85) rangeScore = 0.90; // Very strong spatial = de-facto present (WCVP data gap)
            else if (spatialProx >= 0.6) rangeScore = 0.75; // Strong spatial = likely present, range data gap
            else if (spatialProx >= 0.3) rangeScore = 0.40; // Moderate spatial = possibly present
            else rangeScore = 0; // Unknown range, no spatial confirmation

            // In managed forest, strong k-NN + spatial evidence confirms presence
            // regardless of native/introduced status (native monocultures exist too —
            // e.g. Pinus palustris savannas, Nothofagus beech forests).
            // This closes WCVP data gaps without favoring introduced over native.
            if (isManagedForest && hasKnn && (c.knn_hit_count || 0) >= 3 && spatialProx >= 0.3) {
                rangeScore = Math.max(rangeScore, 0.90);
            }

            // Ecoregion score (now 0-1 continuous, was binary)
            const ecoregionScore = ecoregionMatch;

            // ========== SOIL COMPATIBILITY SCORE (Signal 6) ==========
            // Compares location soil (pH, texture) against species preferences from V11.
            // Species soil data: pH categories (strongly acidic, slightly acidic, neutral, etc.)
            // Location soil data: numeric pH from OpenLandMap
            let soilScore = 0.5; // Default: unknown (no penalty, no boost)
            
            if (locationSoilPh != null) {
                let soilSignals = 0;
                let soilSum = 0;
                
                // Sub-signal 1: pH match
                const speciesPhDominant = c.ph_dominant;
                const speciesPhTolerated = c.ph_tolerated;
                const speciesPhCategories = [];
                if (speciesPhDominant) speciesPhCategories.push(...speciesPhDominant.toLowerCase().split(';').map(s => s.trim()));
                if (speciesPhTolerated) speciesPhCategories.push(...speciesPhTolerated.toLowerCase().split(';').map(s => s.trim()));
                
                if (speciesPhCategories.length > 0) {
                    // Map location pH to category
                    let locPhCategory;
                    if (locationSoilPh < 4.5) locPhCategory = 'very strongly acidic';
                    else if (locationSoilPh < 5.5) locPhCategory = 'strongly acidic';
                    else if (locationSoilPh < 6.0) locPhCategory = 'slightly acidic';
                    else if (locationSoilPh < 6.5) locPhCategory = 'moderately acidic';
                    else if (locationSoilPh < 7.5) locPhCategory = 'neutral';
                    else if (locationSoilPh < 8.5) locPhCategory = 'slightly alkaline';
                    else locPhCategory = 'strongly alkaline';
                    
                    // Check if species tolerates this pH
                    const phMatch = speciesPhCategories.some(cat => {
                        if (cat === locPhCategory) return true;
                        // Adjacent categories get partial match
                        const phOrder = ['very strongly acidic', 'strongly acidic', 'slightly acidic', 
                                       'moderately acidic', 'neutral', 'slightly alkaline', 'strongly alkaline'];
                        const locIdx = phOrder.indexOf(locPhCategory);
                        const catIdx = phOrder.indexOf(cat);
                        if (locIdx >= 0 && catIdx >= 0 && Math.abs(locIdx - catIdx) <= 1) return true;
                        return false;
                    });
                    
                    const isDominant = speciesPhDominant && 
                        speciesPhDominant.toLowerCase().split(';').map(s => s.trim()).includes(locPhCategory);
                    
                    if (isDominant) soilSum += 1.0;
                    else if (phMatch) soilSum += 0.7;
                    else soilSum += 0.2; // Species found in very different pH
                    soilSignals++;
                }
                
                // Sub-signal 2: Soil texture match
                if (locationSoilTexture && (c.soil_texture_dominant || c.soil_texture_tolerated)) {
                    const speciesTextures = [];
                    if (c.soil_texture_dominant) speciesTextures.push(...c.soil_texture_dominant.toLowerCase().split(';').map(s => s.trim()));
                    if (c.soil_texture_tolerated) speciesTextures.push(...c.soil_texture_tolerated.toLowerCase().split(';').map(s => s.trim()));
                    
                    const locTexture = locationSoilTexture.toLowerCase();
                    
                    if (speciesTextures.some(t => locTexture.includes(t) || t.includes(locTexture))) {
                        soilSum += 1.0;
                    } else {
                        // Broad texture group matching (sandy/loamy/clay)
                        const isSandy = t => t.includes('sand');
                        const isLoamy = t => t.includes('loam');
                        const isClay = t => t.includes('clay');
                        
                        const locGroup = isSandy(locTexture) ? 'sandy' : isLoamy(locTexture) ? 'loamy' : isClay(locTexture) ? 'clay' : 'other';
                        const speciesGroups = new Set(speciesTextures.map(t => 
                            isSandy(t) ? 'sandy' : isLoamy(t) ? 'loamy' : isClay(t) ? 'clay' : 'other'
                        ));
                        
                        if (speciesGroups.has(locGroup)) soilSum += 0.7;
                        else soilSum += 0.3;
                    }
                    soilSignals++;
                }
                
                if (soilSignals > 0) {
                    soilScore = soilSum / soilSignals;
                }
            }

            // ========== SINR NEURAL SCORE (Signal 7) ==========
            // SINR v3 deep neural prediction — trained on 5M+ occurrences with
            // satellite, temporal, environmental, and location encoding branches.
            // When available, this is the strongest single signal.
            let sinrScore = 0;
            const sinrPred = sinrAvailable ? sinrPredictions.get(taxonId) : null;
            if (sinrPred) {
                // SINR rank is the primary signal — rank 1-500 from 45K species.
                // Use inverse-log rank to create a smooth curve:
                //   rank 1 → 1.0, rank 2 → 0.95, rank 5 → 0.87, rank 10 → 0.79,
                //   rank 20 → 0.70, rank 50 → 0.57, rank 100 → 0.46, rank 200 → 0.34,
                //   rank 500 → 0.16
                const sinrRank = sinrPred.rank || 999;
                sinrScore = Math.max(0, 1.0 - Math.log(sinrRank) / Math.log(500));
            }

            // ========== COMPOSITE SCORE ==========
            // Dynamic weighting: 7 signals when SINR available, 6 when not.
            // SINR gets significant weight as it's the most comprehensive signal
            // (trained on satellite + env + location jointly).

            let w_emb, w_spatial, w_range, w_eco, w_climate, w_soil, w_sinr;

            if (sinrAvailable) {
                // ===== SINR-ENHANCED SCORING =====
                // SINR becomes the dominant signal, other signals provide confirmation/correction
                if (isManagedForest) {
                    if (embSim >= 0.65) {
                        w_sinr = 0.35; w_emb = 0.25; w_spatial = 0.18; w_range = 0.05; w_eco = 0.03; w_climate = 0.05; w_soil = 0.09;
                    } else if (spatialProx > 0 && embSim >= 0.15) {
                        w_sinr = 0.35; w_emb = 0.12; w_spatial = 0.28; w_range = 0.06; w_eco = 0.03; w_climate = 0.06; w_soil = 0.10;
                    } else {
                        w_sinr = 0.40; w_emb = 0.25; w_spatial = 0.10; w_range = 0.05; w_eco = 0.03; w_climate = 0.07; w_soil = 0.10;
                    }
                } else {
                    if (embSim >= 0.65) {
                        w_sinr = 0.35; w_emb = 0.22; w_spatial = 0.12; w_range = 0.08; w_eco = 0.07; w_climate = 0.07; w_soil = 0.09;
                    } else if (spatialProx > 0 && embSim >= 0.15) {
                        w_sinr = 0.35; w_emb = 0.08; w_spatial = 0.25; w_range = 0.08; w_eco = 0.08; w_climate = 0.08; w_soil = 0.08;
                    } else if (spatialProx > 0) {
                        w_sinr = 0.35; w_emb = 0.05; w_spatial = 0.28; w_range = 0.08; w_eco = 0.08; w_climate = 0.08; w_soil = 0.08;
                    } else {
                        w_sinr = 0.40; w_emb = 0.22; w_spatial = 0.05; w_range = 0.08; w_eco = 0.08; w_climate = 0.08; w_soil = 0.09;
                    }
                }
            } else if (isManagedForest) {
                // ===== MANAGED FOREST MODE (no SINR) =====
                w_sinr = 0;
                if (embSim >= 0.65) {
                    w_emb = 0.45; w_spatial = 0.25; w_range = 0.08; w_eco = 0.05; w_climate = 0.07; w_soil = 0.10;
                } else if (spatialProx > 0 && embSim >= 0.15) {
                    w_emb = 0.20; w_spatial = 0.45; w_range = 0.10; w_eco = 0.05; w_climate = 0.08; w_soil = 0.12;
                } else {
                    w_emb = 0.50; w_spatial = 0.15; w_range = 0.08; w_eco = 0.05; w_climate = 0.10; w_soil = 0.12;
                }
            } else {
                // ===== STANDARD MODE (no SINR) =====
                w_sinr = 0;
                if (embSim >= 0.65) {
                    w_emb = 0.38; w_spatial = 0.18; w_range = 0.12; w_eco = 0.10; w_climate = 0.10; w_soil = 0.12;
                } else if (spatialProx > 0 && embSim >= 0.15) {
                    w_emb = 0.12; w_spatial = 0.38; w_range = 0.12; w_eco = 0.12; w_climate = 0.12; w_soil = 0.14;
                } else if (spatialProx > 0) {
                    w_emb = 0.08; w_spatial = 0.40; w_range = 0.12; w_eco = 0.15; w_climate = 0.13; w_soil = 0.12;
                } else {
                    w_emb = 0.45; w_spatial = 0.08; w_range = 0.12; w_eco = 0.12; w_climate = 0.10; w_soil = 0.13;
                }
            }

            // ========== EMBEDDING SCORE (Signal 1) ==========
            // The embScore computation changes based on managed forest context.
            //
            // Standard mode: max(knnNorm, centroidNorm) — k-NN boosts but never penalizes.
            // Managed forest mode: k-NN CONCENTRATION matters more than centroid match.
            //   Centroid-only species are dampened (they match the general biome, not
            //   the specific species dominating here). k-NN hit count fraction rewards
            //   whatever species genuinely dominates the embedding neighborhood —
            //   REGARDLESS of native/introduced status. A native Pinus palustris in a
            //   longleaf savanna should rank just as well as an introduced P. radiata
            //   in a NZ plantation. The mechanism is the same: trust the embedding
            //   neighborhood over the biome-level centroid.
            let embScore;
            if (hasKnn) {
                const knnScore = c.knn_weighted_score || 0;
                const knnNorm = Math.min(1.0, Math.max(0, Math.log1p(knnScore * 5) / Math.log1p(10)));
                const centroidNorm = Math.max(0, Math.min(1.0, (embSim - 0.2) / 0.6));

                if (isManagedForest) {
                    // Managed forest: k-NN concentration is the primary signal.
                    // Species with more hits in the k-NN neighborhood are likely what's
                    // actually growing here. Log-scale because significance is non-linear:
                    // 3 hits is much more than 0, but 20 vs 10 matters less.
                    const hits = c.knn_hit_count || 0;
                    const fineHits = c.knn_hit_count_fine || 0;
                    // log-scale: 1 hit→0.25, 3→0.43, 5→0.52, 10→0.65, 20→0.78, 50→0.92
                    const hitSignal = Math.min(1.0, Math.log1p(hits) / Math.log1p(50));
                    const fineSignal = Math.min(1.0, Math.log1p(fineHits) / Math.log1p(10));
                    embScore = Math.min(1.0,
                        0.40 * knnNorm +
                        0.15 * centroidNorm +
                        0.25 * hitSignal +
                        0.20 * fineSignal
                    );
                } else {
                    // Standard: max of the two signals + small confirmation bonus
                    const baseEmb = Math.max(knnNorm, centroidNorm);
                    const confirmBonus = Math.min(knnNorm, centroidNorm) * 0.1;
                    embScore = Math.min(1.0, baseEmb + confirmBonus);
                }
            } else {
                // Centroid-only species (no k-NN hits)
                const centroidNorm = Math.max(0, Math.min(1.0, (embSim - 0.2) / 0.6));
                if (isManagedForest) {
                    // In managed forest: centroid-only species are penalized HEAVILY.
                    // They match the general biome but have NO k-NN evidence of being
                    // the specific species planted here. The penalty scales with MFP.
                    embScore = centroidNorm * (1.0 - managedForestProb * 0.65);
                    // MFP=0.65 → multiplier=0.577, MFP=0.80 → multiplier=0.48
                } else {
                    embScore = centroidNorm;
                }
            }

            const compositeScore =
                w_sinr * sinrScore +
                w_emb * embScore +
                w_spatial * spatialProx +
                w_range * rangeScore +
                w_eco * ecoregionScore +
                w_climate * climateScore +
                w_soil * soilScore;

            // Multi-source bonus: species confirmed by multiple channels are more credible
            const multiSourceBonus = numSources >= 3 ? 0.12 : (numSources === 2 ? 0.06 : 0);

            const finalScore = Math.min(1.0, compositeScore + multiSourceBonus);

            // Minimum score threshold: at least 0.15 to appear
            if (finalScore < 0.15) continue;

            predictions.push({
                taxon_id: taxonId,
                scientific_name: c.scientific_name,
                common_name: c.common_name,
                family: c.family,
                genus: c.genus,

                // Multi-signal score
                suitability_score: Math.round(finalScore * 100),
                habitat_similarity: parseFloat(finalScore.toFixed(4)),

                // Signal breakdown (7 signals when SINR available)
                signals: {
                    sinr: Math.round(sinrScore * 100),
                    embedding: Math.round(embScore * 100),
                    spatial: Math.round(spatialProx * 100),
                    range: Math.round(rangeScore * 100),
                    ecoregion: Math.round(ecoregionScore * 100),
                    climate: Math.round(climateScore * 100),
                    soil: Math.round(soilScore * 100)
                },
                signal_weights: { sinr: w_sinr, embedding: w_emb, spatial: w_spatial, range: w_range, ecoregion: w_eco, climate: w_climate, soil: w_soil },
                sinr_data: sinrPred ? {
                    rank: sinrPred.rank,
                    prob_best: sinrPred.prob_best,
                    prob_native: sinrPred.prob_native,
                    prob_introduced: sinrPred.prob_introduced,
                    best_mode: sinrPred.best_mode || null,
                } : null,

                // k-NN metadata (when available)
                knn_data: hasKnn ? {
                    hit_count: c.knn_hit_count,
                    hit_count_fine: c.knn_hit_count_fine || 0,
                    weighted_score: parseFloat((c.knn_weighted_score || 0).toFixed(4)),
                    raw_vote: parseFloat((c.knn_raw_vote || 0).toFixed(4)),
                    raw_vote_fine: parseFloat((c.knn_raw_vote_fine || 0).toFixed(4)),
                    effective_idf: parseFloat((c.knn_effective_idf || 0).toFixed(4)),
                    idf_weight: parseFloat((c.knn_idf_weight || 0).toFixed(4)),
                    total_occurrences: c.knn_total_occurrences,
                    source_types: c.knn_source_types,
                    subtaxa_count: c.knn_subtaxa_count || 1,
                    subtaxa_ids: c.knn_subtaxa_ids || null,
                    best_subtaxon: c.knn_best_subtaxon || null,
                    species_root: c.knn_species_root || null
                } : null,
                discovery_sources: [...c.sources],
                source_count: numSources,

                // Raw values
                raw_embedding_similarity: parseFloat((c.embedding_similarity || 0).toFixed(4)),
                spatial_tiles_nearby: c.spatial_tile_count || 0,
                spatial_min_distance_m: c.spatial_min_distance === Infinity ? null : Math.round(c.spatial_min_distance),

                // Habitat match
                habitat_match: {
                    cluster_id: c.cluster_id,
                    cluster_elevation: c.cluster_elevation,
                    cluster_treecover: c.cluster_treecover,
                    cluster_occurrences: c.occurrence_count,
                    representative_location: c.representative_lat ? {
                        lat: c.representative_lat,
                        lon: c.representative_lon
                    } : null
                },

                // Native/introduced status
                native_status,
                is_native: isNative,
                is_introduced: isIntroduced,
                is_invasive: isInvasive,
                ecoregion_match: ecoregionMatch,

                // Attributes
                attributes: {
                    growth_form: c.growth_form,
                    maximum_height: c.maximum_height,
                    conservation_status: c.conservation_status
                }
            });
        }

        // Sort by composite score and limit
        predictions.sort((a, b) => b.suitability_score - a.suitability_score);
        const limited = predictions.slice(0, resultLimit);
        limited.forEach((p, i) => { p.rank = i + 1; });

        // Summary stats
        const nativeStatusSummary = {
            native: limited.filter(p => p.native_status === 'native').length,
            introduced: limited.filter(p => p.native_status === 'introduced').length,
            native_and_introduced: limited.filter(p => p.native_status === 'native_and_introduced').length,
            unknown: limited.filter(p => p.native_status === 'unknown').length,
            invasive: limited.filter(p => p.native_status === 'invasive').length
        };

        const sourceSummary = {
            embedding_only: limited.filter(p => p.source_count === 1 && p.discovery_sources.includes('embedding')).length,
            spatial_only: limited.filter(p => p.source_count === 1 && p.discovery_sources.includes('spatial')).length,
            multi_source: limited.filter(p => p.source_count >= 2).length,
            total_candidates_evaluated: candidateMap.size
        };

        console.log(`  Final: ${limited.length} predictions from ${candidateMap.size} candidates`);
        console.log(`  Sources: ${sourceSummary.embedding_only} emb-only, ${sourceSummary.spatial_only} spatial-only, ${sourceSummary.multi_source} multi-source`);

        res.json({
            success: true,
            location: {
                latitude,
                longitude,
                elevation,
                treecover2000: locationData?.treecover2000,
                forest_loss: locationData?.loss,
                data_source: locationData?.data_source || 'unknown',
                demo_mode: isDemoMode
            },
            location_context: {
                ecoregion: ecoregion ? {
                    eco_id: ecoregion.eco_id,
                    eco_name: ecoregion.eco_name,
                    biome_name: ecoregion.biome_name,
                    realm: ecoregion.realm
                } : null,
                countries,
                climate: locationClimate ? {
                    annual_mean_temp_c: locationTemperature,
                    annual_precipitation_mm: locationPrecipitation
                } : null,
                soil: locationSoil ? {
                    ph: locationSoilPh,
                    ph_category: locationSoilPhCategory,
                    texture: locationSoilTexture
                } : null,
                embedding_homogeneity: locationData?.embedding_homogeneity ?? null
            },
            query_params: {
                limit: resultLimit,
                scoring: sinrAvailable ? 'multi-signal-v3-sinr' : 'multi-signal-v3-mfp',
                sinr: {
                    available: sinrAvailable,
                    model_version: sinrModelVersion,
                    candidates_added: sinrAvailable ? [...candidateMap.values()].filter(c => c.sources.has('sinr') && c.sources.size === 1).length : 0
                },
                managed_forest: {
                    probability: parseFloat(managedForestProb.toFixed(3)),
                    is_managed: isManagedForest,
                    embedding_homogeneity: embHomogeneity,
                    canopy_height_mean: canopyHeightMean,
                    canopy_height_stddev: canopyHeightStddev,
                    ccdc_breaks: ccdcBreaks,
                    description: isManagedForest
                        ? 'Uniform canopy detected — scoring favors k-NN concentration over centroid match'
                        : 'Natural/mixed canopy — standard multi-signal scoring'
                },
                idf_context: {
                    idf_factor: idfFactor ?? 1.0,
                    description: 'idf_factor=1.0 means full IDF, lower values soften IDF for uniform canopy sites'
                }
            },
            results: {
                count: limited.length,
                native_status_summary: nativeStatusSummary,
                source_summary: sourceSummary,
                predictions: limited
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
 * Multi-source species recommendations using SAFE-B framework.
 *
 * Uses the same multi-source candidate discovery as /predict (embedding +
 * spatial + WCVP range), THEN applies SAFE-B scoring with strategy-specific
 * weights. Different strategies produce different results because:
 *
 *   1. Candidate pool is augmented with strategy-specific sources:
 *      - rewilding/biodiversity: adds WCVP-native species even without embedding match
 *      - agroforestry: adds species with agroforestry_use_cases in the region
 *      - riparian: prioritizes flood/waterlog-tolerant species
 *   2. SAFE-B components are weighted differently per strategy
 *   3. Hard filters differ (invasive always excluded, introduced excluded for rewilding)
 *
 * Query Parameters:
 * - lat, lon: Location (required)
 * - strategy: rewilding|agroforestry|riparian|carbon|biodiversity|erosion_control|general
 * - include_introduced: Include non-native species (default: false)
 * - limit: Max species to return (default: 30, max: 100)
 */
router.get('/recommend', async (req, res) => {
    try {
        const {
            lat,
            lon,
            strategy = 'general',
            include_introduced = 'false',
            limit = 30
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

        console.log(`\n=== MULTI-SOURCE RECOMMEND: ${latitude}, ${longitude} strategy=${strategy} ===`);

        // Validate strategy
        const { SafeBScorer, STRATEGY_WEIGHTS } = require('../services/safeb-scorer');
        if (!STRATEGY_WEIGHTS[strategy]) {
            return res.status(400).json({
                error: 'Invalid strategy',
                valid_strategies: Object.keys(STRATEGY_WEIGHTS),
                detail: Object.entries(STRATEGY_WEIGHTS).map(([k, v]) => `${k}: ${v.description}`)
            });
        }

        // Step 1: Get habitat embedding
        let embedding, locationData;
        try {
            let sampleResponse;
            try {
                sampleResponse = await axios.post(`${LOCATION_PREDICTOR_URL}/sample`, {
                    lat: latitude,
                    lon: longitude,
                    year: 2023
                }, { timeout: 60000 });
            } catch (postErr) {
                sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                    params: { lat: latitude, lon: longitude },
                    timeout: 30000
                });
            }
            locationData = sampleResponse.data;
            embedding = normalizeEmbedding(sampleResponse.data);
        } catch (error) {
            return res.status(503).json({
                error: 'Cannot get habitat embedding for location',
                detail: 'Location predictor service unavailable'
            });
        }

        if (!embedding || embedding.length !== 64) {
            return res.status(400).json({
                error: 'Invalid embedding from location predictor',
                detail: `Expected 64-D embedding, got: ${embedding ? embedding.length : 'null'}`
            });
        }

        // Step 1b: Call SINR inference (v3 primary with location encoding, v2.2 fallback)
        let sinrPredictions = new Map(); // taxon_id → { prob_native, prob_introduced, prob_best }
        let sinrAvailable = false;
        const sinrPromise = (async () => {
            try {
                const sinrResponse = await axios.post(`${LOCATION_PREDICTOR_URL}/sinr-infer`, {
                    lat: latitude,
                    lon: longitude,
                    year: 2023,
                    sample_data: locationData,
                    top_k: 200,
                    two_pass: true
                }, { timeout: 120000 });
                if (sinrResponse.data?.success && sinrResponse.data?.predictions) {
                    for (const pred of sinrResponse.data.predictions) {
                        sinrPredictions.set(pred.taxon_id, pred);
                    }
                    sinrAvailable = true;
                    const modelVer = sinrResponse.data.model_version || 'unknown';
                    console.log(`  SINR ${modelVer}: ${sinrResponse.data.predictions.length} species predicted in ${sinrResponse.data.timing?.inference_ms}ms`);
                }
            } catch (err) {
                console.log(`  SINR inference unavailable: ${err.message}`);
            }
        })();

        // Step 2: Get location context
        let ecoregion = null;
        let countries = [];
        let wcvpPatterns = [];

        try {
            const ecoResult = await pool.query(`
                SELECT eco_name, biome_name, realm, eco_id
                FROM ecoregions
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
                ORDER BY ST_Area(geom) ASC
                LIMIT 1
            `, [longitude, latitude]);

            if (ecoResult.rows.length > 0) {
                ecoregion = ecoResult.rows[0];

                const countriesResult = await pool.query(`
                    SELECT DISTINCT
                        CASE
                            WHEN c.name_en = 'United States of America' THEN 'United States'
                            WHEN c.name_en = 'United Kingdom' THEN 'United Kingdom'
                            ELSE c.name_en
                        END as country_name
                    FROM countries c
                    WHERE ST_Intersects(c.geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
                `, [longitude, latitude]);
                countries = countriesResult.rows.map(r => r.country_name).filter(Boolean);

                try {
                    const { getWcvpRegionsForCountry } = require('../utils/wcvpRegions');
                    for (const country of countries) {
                        const regions = getWcvpRegionsForCountry(country);
                        wcvpPatterns.push(...regions.map(r => r.toLowerCase()));
                    }
                } catch (e) { /* non-fatal */ }
            }
        } catch (ecoError) {
            console.log('Ecoregion lookup failed (non-fatal):', ecoError.message);
        }

        const vectorString = `[${embedding.join(',')}]`;
        const elevation = locationData?.elevation || null;

        // Extract climate data from Python service (WorldClim BIO)
        const recLocationClimate = locationData?.climate || null;
        const recLocationTemperature = recLocationClimate?.annual_mean_temp_c ?? null;
        const recLocationPrecipitation = recLocationClimate?.annual_precipitation_mm ?? null;

        // Extract soil data from Python service (OpenLandMap)
        const recLocationSoil = locationData?.soil || null;
        const recLocationSoilPh = recLocationSoil?.soil_ph ?? null;
        const recLocationSoilPhCategory = recLocationSoil?.soil_ph_category ?? null;
        const recLocationSoilTexture = recLocationSoil?.soil_texture ?? null;

        // =====================================================================
        // Step 3: MULTI-SOURCE CANDIDATE DISCOVERY (broader for recommend)
        // =====================================================================

        // Channel 1a: k-NN occurrence matching (primary)
        // Same approach as /predict — finds species by nearest individual occurrence embeddings
        let embeddingCandidates = [];
        const recKnnSpeciesSet = new Set();
        try {
            await pool.query('SET hnsw.ef_search = 200');
            const knnResult = await pool.query(`
                WITH nearest AS (
                    SELECT
                        oe.taxon_id,
                        1 - (oe.embedding <=> $1::vector) AS similarity,
                        oe.density_weight,
                        oe.quality_weight,
                        oe.elevation
                    FROM species_occurrence_embeddings oe
                    ORDER BY oe.embedding <=> $1::vector
                    LIMIT 500
                )
                SELECT
                    n.taxon_id,
                    COUNT(*) AS hit_count,
                    MAX(n.similarity) AS best_similarity,
                    SUM(n.similarity * n.density_weight * n.quality_weight) * os.idf_weight AS weighted_score,
                    AVG(n.elevation) AS mean_elevation,
                    os.total_occurrences AS occurrence_count,
                    os.idf_weight,
                    -- Full species metadata for SAFE-B
                    s.accepted_scientific_name, s.common_name, s.family, s.genus,
                    COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                    s.growth_form_ai, s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                    s.ecoregions, s.biomes, s.bioregions, s.successional_stage,
                    s.tolerances, s.tolerances_ai, s.forest_layers,
                    s.maximum_height_ai, s.lifespan_ai,
                    s.annual_precipitation_mm, s.annual_temperature_range_c,
                    s.ph_prefered, s.soil_texture_prefered,
                    s.climate_type_koppengeiger,
                    s.agroforestry_use_cases_ai, s.timber_value, s.timber_value_ai,
                    s.non_timber_products, s.non_timber_products_ai,
                    s.functional_ecosystem_groups,
                    COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status,
                    s.globi_pollinatedby, s.globi_eatenby, s.globi_flowersvisitedby,
                    s.globi_hasdispersalvector, s.globi_hasparasite, s.globi_haspathogen,
                    s.globi_preyeduponby, s.globi_hasparasitoid
                FROM nearest n
                JOIN species_occurrence_stats os ON os.taxon_id = n.taxon_id
                LEFT JOIN species s ON n.taxon_id = s.taxon_id
                GROUP BY n.taxon_id, os.idf_weight, os.total_occurrences,
                         s.accepted_scientific_name, s.common_name, s.family, s.genus,
                         s.growth_form_human, s.growth_form_ai,
                         s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                         s.ecoregions, s.biomes, s.bioregions, s.successional_stage,
                         s.tolerances, s.tolerances_ai, s.forest_layers,
                         s.maximum_height_ai, s.lifespan_ai,
                         s.annual_precipitation_mm, s.annual_temperature_range_c,
                         s.ph_prefered, s.soil_texture_prefered,
                         s.climate_type_koppengeiger,
                         s.agroforestry_use_cases_ai, s.timber_value, s.timber_value_ai,
                         s.non_timber_products, s.non_timber_products_ai,
                         s.functional_ecosystem_groups,
                         s.conservation_status_human, s.conservation_status_ai,
                         s.globi_pollinatedby, s.globi_eatenby, s.globi_flowersvisitedby,
                         s.globi_hasdispersalvector, s.globi_hasparasite, s.globi_haspathogen,
                         s.globi_preyeduponby, s.globi_hasparasitoid
                ORDER BY weighted_score DESC
                LIMIT 200
            `, [vectorString]);

            for (const row of knnResult.rows) {
                recKnnSpeciesSet.add(row.taxon_id);
                // Compute blended similarity for SAFE-B (k-NN weighted + centroid-equivalent)
                const knnNorm = Math.min(1.0, Math.max(0, Math.log1p(parseFloat(row.weighted_score) * 5) / Math.log1p(10)));
                const centroidNorm = Math.max(0, Math.min(1.0, (parseFloat(row.best_similarity) - 0.2) / 0.6));
                row.similarity = 0.6 * knnNorm + 0.4 * centroidNorm;
                row.knn_hit_count = parseInt(row.hit_count);
                row.knn_weighted_score = parseFloat(row.weighted_score);
                embeddingCandidates.push(row);
            }
            console.log(`  Channel 1a (k-NN): ${knnResult.rows.length} species from 500 nearest occurrences`);
        } catch (err) {
            console.error('  Channel 1a (k-NN) error:', err.message);
        }

        // Channel 1b: Centroid fallback — catches species not in k-NN top-500
        try {
            const centroidResult = await pool.query(`
                WITH ranked AS (
                    SELECT
                        c.taxon_id,
                        1 - (c.centroid_vector <=> $1::vector) as similarity,
                        c.mean_elevation,
                        c.occurrence_count,
                        c.is_single_cluster,
                        ROW_NUMBER() OVER (
                            PARTITION BY c.taxon_id
                            ORDER BY c.centroid_vector <=> $1::vector
                        ) as rank_in_species
                    FROM species_habitat_centroids c
                    WHERE 1 - (c.centroid_vector <=> $1::vector) >= 0.40
                )
                SELECT
                    r.taxon_id, r.similarity, r.mean_elevation, r.occurrence_count, r.is_single_cluster,
                    s.accepted_scientific_name, s.common_name, s.family, s.genus,
                    COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                    s.growth_form_ai, s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                    s.ecoregions, s.biomes, s.bioregions, s.successional_stage,
                    s.tolerances, s.tolerances_ai, s.forest_layers,
                    s.maximum_height_ai, s.lifespan_ai,
                    s.annual_precipitation_mm, s.annual_temperature_range_c,
                    s.ph_prefered, s.soil_texture_prefered,
                    s.climate_type_koppengeiger,
                    s.agroforestry_use_cases_ai, s.timber_value, s.timber_value_ai,
                    s.non_timber_products, s.non_timber_products_ai,
                    s.functional_ecosystem_groups,
                    COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status,
                    s.globi_pollinatedby, s.globi_eatenby, s.globi_flowersvisitedby,
                    s.globi_hasdispersalvector, s.globi_hasparasite, s.globi_haspathogen,
                    s.globi_preyeduponby, s.globi_hasparasitoid
                FROM ranked r
                LEFT JOIN species s ON r.taxon_id = s.taxon_id
                WHERE r.rank_in_species = 1
                ORDER BY r.similarity DESC
                LIMIT 200
            `, [vectorString]);

            let centroidOnlyCount = 0;
            for (const row of centroidResult.rows) {
                if (!recKnnSpeciesSet.has(row.taxon_id)) {
                    centroidOnlyCount++;
                    embeddingCandidates.push(row);
                }
                // For k-NN species already added, we skip — their blended similarity is better
            }
            console.log(`  Channel 1b (centroid): ${centroidResult.rows.length} candidates (${centroidOnlyCount} new beyond k-NN)`);
        } catch (err) {
            console.error('  Channel 1b (centroid) error:', err.message);
        }

        // Channel 2: Spatial proximity — species actually observed nearby
        const spatialTaxonIds = new Set();
        try {
            const spatialResult = await pool.query(`
                WITH nearby_tiles AS (
                    SELECT species_data
                    FROM geohash_species_tiles
                    WHERE ST_DWithin(
                        geometry::geography,
                        ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                        50000
                    )
                )
                SELECT DISTINCT key as taxon_id
                FROM nearby_tiles,
                     jsonb_each(species_data) as kv(key, value)
            `, [longitude, latitude]);

            for (const row of spatialResult.rows) {
                spatialTaxonIds.add(row.taxon_id);
            }
            console.log(`  Channel 2 (spatial): ${spatialTaxonIds.size} species within 50km`);
        } catch (err) {
            console.error('  Channel 2 error:', err.message);
        }

        // Channel 3: Strategy-specific candidates
        // For rewilding/biodiversity: add WCVP-native species in this region
        // For agroforestry: add species with agroforestry uses in the ecoregion
        const strategyTaxonIds = new Set();
        try {
            if ((strategy === 'rewilding' || strategy === 'biodiversity') && wcvpPatterns.length > 0) {
                // Find native species for this region that have centroid data
                const nativeQ = await pool.query(`
                    SELECT DISTINCT s.taxon_id
                    FROM species s
                    INNER JOIN species_habitat_centroids c ON s.taxon_id = c.taxon_id
                    WHERE ${wcvpPatterns.map((_, i) => `s.wcvp_native ILIKE $${i + 1}`).join(' OR ')}
                    LIMIT 300
                `, wcvpPatterns.map(p => `%${p}%`));
                for (const row of nativeQ.rows) strategyTaxonIds.add(row.taxon_id);
                console.log(`  Channel 3 (${strategy} native): ${nativeQ.rows.length} WCVP-native species`);
            } else if (strategy === 'agroforestry' && ecoregion) {
                const agroQ = await pool.query(`
                    SELECT DISTINCT s.taxon_id
                    FROM species s
                    INNER JOIN species_habitat_centroids c ON s.taxon_id = c.taxon_id
                    WHERE s.agroforestry_use_cases_ai IS NOT NULL
                      AND s.agroforestry_use_cases_ai != 'NA'
                      AND LENGTH(s.agroforestry_use_cases_ai) > 5
                      AND (s.ecoregions ILIKE $1 OR s.biomes ILIKE $2)
                    LIMIT 200
                `, [`%${ecoregion.eco_name.substring(0, 15)}%`, `%${(ecoregion.biome_name || '').substring(0, 15)}%`]);
                for (const row of agroQ.rows) strategyTaxonIds.add(row.taxon_id);
                console.log(`  Channel 3 (agroforestry): ${agroQ.rows.length} agroforestry species`);
            } else if (strategy === 'riparian') {
                const riparianQ = await pool.query(`
                    SELECT DISTINCT s.taxon_id
                    FROM species s
                    INNER JOIN species_habitat_centroids c ON s.taxon_id = c.taxon_id
                    WHERE (s.tolerances_ai ILIKE '%flood%' OR s.tolerances_ai ILIKE '%waterlog%'
                           OR s.tolerances_ai ILIKE '%riparian%' OR s.tolerances ILIKE '%flood%')
                      AND (s.ecoregions ILIKE $1 OR s.bioregions ILIKE $2)
                    LIMIT 200
                `, [`%${(ecoregion?.eco_name || '').substring(0, 15)}%`, `%${(ecoregion?.realm || '').substring(0, 10)}%`]);
                for (const row of riparianQ.rows) strategyTaxonIds.add(row.taxon_id);
                console.log(`  Channel 3 (riparian): ${riparianQ.rows.length} flood-tolerant species`);
            } else if (strategy === 'carbon') {
                const carbonQ = await pool.query(`
                    SELECT DISTINCT s.taxon_id
                    FROM species s
                    INNER JOIN species_habitat_centroids c ON s.taxon_id = c.taxon_id
                    WHERE (s.growth_form_ai ILIKE '%tree%' OR s.growth_form_human ILIKE '%tree%')
                      AND s.maximum_height_ai IS NOT NULL AND s.maximum_height_ai != 'NA'
                      AND (s.ecoregions ILIKE $1 OR s.biomes ILIKE $2)
                    LIMIT 200
                `, [`%${(ecoregion?.eco_name || '').substring(0, 15)}%`, `%${(ecoregion?.biome_name || '').substring(0, 15)}%`]);
                for (const row of carbonQ.rows) strategyTaxonIds.add(row.taxon_id);
                console.log(`  Channel 3 (carbon): ${carbonQ.rows.length} tall tree species`);
            } else if (strategy === 'erosion_control') {
                const erosionQ = await pool.query(`
                    SELECT DISTINCT s.taxon_id
                    FROM species s
                    INNER JOIN species_habitat_centroids c ON s.taxon_id = c.taxon_id
                    WHERE (s.successional_stage ILIKE '%pioneer%' OR s.successional_stage ILIKE '%early%'
                           OR s.tolerances_ai ILIKE '%drought%' OR s.tolerances ILIKE '%drought%')
                      AND (s.ecoregions ILIKE $1 OR s.bioregions ILIKE $2)
                    LIMIT 200
                `, [`%${(ecoregion?.eco_name || '').substring(0, 15)}%`, `%${(ecoregion?.realm || '').substring(0, 10)}%`]);
                for (const row of erosionQ.rows) strategyTaxonIds.add(row.taxon_id);
                console.log(`  Channel 3 (erosion_control): ${erosionQ.rows.length} pioneer/drought species`);
            }
        } catch (err) {
            console.error('  Channel 3 error:', err.message);
        }

        // Wait for SINR inference to complete before merging
        await sinrPromise;

        // Channel 4: SINR v2.2 neural predictions
        const sinrTaxonIds = new Set();
        if (sinrAvailable) {
            for (const [taxonId] of sinrPredictions) {
                sinrTaxonIds.add(taxonId);
            }
            console.log(`  Channel 4 (SINR v2.2): ${sinrTaxonIds.size} species predicted`);
        }

        // Merge all candidates: start with embedding candidates, add spatial + strategy + SINR
        const candidateMap = new Map();
        for (const row of embeddingCandidates) {
            candidateMap.set(row.taxon_id, { ...row, sources: ['embedding'] });
        }

        // Add spatial and strategy candidates that aren't already in the pool
        const additionalIds = new Set();
        for (const id of spatialTaxonIds) {
            if (candidateMap.has(id)) {
                candidateMap.get(id).sources.push('spatial');
            } else {
                additionalIds.add(id);
            }
        }
        for (const id of strategyTaxonIds) {
            if (candidateMap.has(id)) {
                candidateMap.get(id).sources.push('strategy');
            } else {
                additionalIds.add(id);
            }
        }
        for (const id of sinrTaxonIds) {
            if (candidateMap.has(id)) {
                candidateMap.get(id).sources.push('sinr');
            } else {
                additionalIds.add(id);
            }
        }

        // Fetch full species data + embedding similarity for additional candidates
        if (additionalIds.size > 0) {
            try {
                const additionalResult = await pool.query(`
                    SELECT
                        s.taxon_id,
                        s.accepted_scientific_name, s.common_name, s.family, s.genus,
                        COALESCE(s.growth_form_human, s.growth_form_ai) as growth_form,
                        s.growth_form_ai, s.wcvp_native, s.wcvp_introduced, s.countries_invasive,
                        s.ecoregions, s.biomes, s.bioregions, s.successional_stage,
                        s.tolerances, s.tolerances_ai, s.forest_layers,
                        s.maximum_height_ai, s.lifespan_ai,
                        s.annual_precipitation_mm, s.annual_temperature_range_c,
                        s.ph_prefered, s.soil_texture_prefered,
                        s.climate_type_koppengeiger,
                        s.agroforestry_use_cases_ai, s.timber_value, s.timber_value_ai,
                        s.non_timber_products, s.non_timber_products_ai,
                        s.functional_ecosystem_groups,
                        COALESCE(s.conservation_status_human, s.conservation_status_ai) as conservation_status,
                        s.globi_pollinatedby, s.globi_eatenby, s.globi_flowersvisitedby,
                        s.globi_hasdispersalvector, s.globi_hasparasite, s.globi_haspathogen,
                        s.globi_preyeduponby, s.globi_hasparasitoid,
                        (SELECT 1 - (c.centroid_vector <=> $2::vector)
                         FROM species_habitat_centroids c WHERE c.taxon_id = s.taxon_id
                         ORDER BY c.centroid_vector <=> $2::vector LIMIT 1) as similarity,
                        (SELECT c.mean_elevation FROM species_habitat_centroids c
                         WHERE c.taxon_id = s.taxon_id ORDER BY c.centroid_vector <=> $2::vector LIMIT 1) as mean_elevation,
                        (SELECT c.occurrence_count FROM species_habitat_centroids c
                         WHERE c.taxon_id = s.taxon_id ORDER BY c.centroid_vector <=> $2::vector LIMIT 1) as occurrence_count
                    FROM species s
                    WHERE s.taxon_id = ANY($1)
                `, [[...additionalIds], vectorString]);

                for (const row of additionalResult.rows) {
                    const sources = [];
                    if (spatialTaxonIds.has(row.taxon_id)) sources.push('spatial');
                    if (strategyTaxonIds.has(row.taxon_id)) sources.push('strategy');
                    if (sinrTaxonIds.has(row.taxon_id)) sources.push('sinr');
                    candidateMap.set(row.taxon_id, { ...row, sources });
                }
                console.log(`  Additional candidates fetched: ${additionalResult.rows.length}`);
            } catch (err) {
                console.error('  Additional candidates error:', err.message);
            }
        }

        const allCandidates = [...candidateMap.values()];
        console.log(`  Total candidate pool: ${allCandidates.length} (emb:${embeddingCandidates.length}, spatial:${spatialTaxonIds.size}, strategy:${strategyTaxonIds.size}, sinr:${sinrTaxonIds.size})`);

        if (allCandidates.length === 0) {
            return res.json({
                success: true,
                location: { latitude, longitude, elevation },
                strategy: { name: strategy },
                results: { count: 0, recommendations: [], excluded: [] },
                message: 'No candidate species found for this location'
            });
        }

        // Step 4: Score with SAFE-B
        const scorer = new SafeBScorer(pool);
        const recLocationKoppenCode = recLocationClimate?.koppen_code ?? null;
        const locationContext = {
            lat: latitude,
            lon: longitude,
            elevation,
            ecoregion,
            countries,
            wcvpPatterns,
            precipitation: recLocationPrecipitation,
            temperature: recLocationTemperature,
            soil_ph: recLocationSoilPhCategory,
            soil_texture: recLocationSoilTexture,
            koppen_code: recLocationKoppenCode
        };

        const { recommendations, excluded } = await scorer.scoreSpecies(
            allCandidates,
            locationContext,
            strategy,
            { includeIntroduced }
        );

        // Enrich all recommendations with SINR data and re-rank
        for (const rec of recommendations) {
            const c = candidateMap.get(rec.taxon_id);
            rec.discovery_sources = c?.sources || [];

            // SINR probability (two-pass: pick native/introduced based on native status)
            const sinrPred = sinrPredictions.get(rec.taxon_id);
            if (sinrPred) {
                if (rec.is_native) {
                    rec.sinr_probability = sinrPred.prob_native;
                } else if (rec.is_introduced) {
                    rec.sinr_probability = sinrPred.prob_introduced;
                } else {
                    rec.sinr_probability = sinrPred.prob_best;
                }
                rec.sinr_detail = {
                    prob_native: sinrPred.prob_native,
                    prob_introduced: sinrPred.prob_introduced,
                    prob_best: sinrPred.prob_best,
                    rank: sinrPred.rank,
                };
            } else {
                rec.sinr_probability = null;
                rec.sinr_detail = null;
            }

            // Blend SINR into final score when available:
            // SINR acts as a habitat reality check — species the neural model
            // predicts have strong presence at this location get a significant boost.
            // Species NOT in SINR top-200 get a penalty (they're less likely to thrive).
            if (sinrAvailable) {
                const sinrProb = rec.sinr_probability;
                if (sinrProb != null && sinrProb > 0) {
                    // Blend: 60% SAFE-B + 40% SINR (scaled to 0-100)
                    const sinrScaled = Math.min(100, sinrProb * 150); // 0.66 → ~100
                    rec.combined_score = Math.round(0.6 * rec.safeb_score + 0.4 * sinrScaled);
                } else {
                    // Species not in SINR top-200: slight penalty (unlikely at this location)
                    rec.combined_score = Math.round(rec.safeb_score * 0.7);
                }
            } else {
                rec.combined_score = rec.safeb_score;
            }

            // 6-axis radar chart scores (0-100 each)
            const sinrRadar = rec.sinr_probability != null
                ? Math.round(Math.min(1.0, rec.sinr_probability * 1.5) * 100)
                : null;
            rec.radar = {
                sinr_habitat: sinrRadar,
                spatial: rec.safeb_components.spatial,
                abiotic: rec.safeb_components.abiotic,
                functional: rec.safeb_components.functional,
                ecosystem: rec.safeb_components.ecosystem,
                biotic: rec.safeb_components.biotic,
            };
        }

        // Re-sort by combined score (SAFE-B + SINR blend)
        recommendations.sort((a, b) => b.combined_score - a.combined_score);
        recommendations.forEach((s, i) => { s.rank = i + 1; });

        const limitedRecommendations = recommendations.slice(0, resultLimit);

        res.json({
            success: true,
            location: {
                latitude,
                longitude,
                elevation,
                data_source: locationData?.data_source || 'unknown',
                demo_mode: locationData?.demo_mode || false
            },
            location_context: {
                ecoregion: ecoregion ? {
                    eco_id: ecoregion.eco_id,
                    eco_name: ecoregion.eco_name,
                    biome_name: ecoregion.biome_name,
                    realm: ecoregion.realm
                } : null,
                countries,
                climate: recLocationClimate ? {
                    annual_mean_temp_c: recLocationTemperature,
                    annual_precipitation_mm: recLocationPrecipitation
                } : null,
                soil: recLocationSoil ? {
                    ph: recLocationSoilPh,
                    ph_category: recLocationSoilPhCategory,
                    texture: recLocationSoilTexture
                } : null
            },
            strategy: {
                name: strategy,
                description: STRATEGY_WEIGHTS[strategy].description,
                weights: STRATEGY_WEIGHTS[strategy]
            },
            query_params: {
                include_introduced: includeIntroduced,
                limit: resultLimit
            },
            results: {
                count: limitedRecommendations.length,
                total_candidates: allCandidates.length,
                excluded_count: excluded.length,
                candidate_sources: {
                    embedding: embeddingCandidates.length,
                    spatial: spatialTaxonIds.size,
                    strategy_specific: strategyTaxonIds.size,
                    sinr_v2: sinrTaxonIds.size
                },
                sinr_available: sinrAvailable,
                recommendations: limitedRecommendations,
                excluded_sample: excluded.slice(0, 5)
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
            let sampleResponse;
            try {
                sampleResponse = await axios.post(`${LOCATION_PREDICTOR_URL}/sample`, {
                    lat: latitude,
                    lon: longitude,
                    year: 2023
                }, { timeout: 60000 });
            } catch (postErr) {
                sampleResponse = await axios.get(`${LOCATION_PREDICTOR_URL}/sample`, {
                    params: { lat: latitude, lon: longitude },
                    timeout: 30000
                });
            }
            locationData = sampleResponse.data;
            embedding = normalizeEmbedding(sampleResponse.data);
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
                s.accepted_scientific_name as species_scientific_name,
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
            species_scientific_name: row.species_scientific_name,
            family: row.family,
            common_name: row.common_name,
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
        console.log(`Top prediction: ${predictions[0].species_scientific_name} (confidence: ${predictions[0].confidence.toFixed(4)})`);

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

/**
 * GET /api/prediction/strategies
 *
 * List available restoration strategies and their SAFE-B weight profiles.
 * Used by the frontend to populate the strategy dropdown.
 */
router.get('/strategies', (req, res) => {
    const { STRATEGY_WEIGHTS } = require('../services/safeb-scorer');

    const strategies = Object.entries(STRATEGY_WEIGHTS).map(([key, value]) => ({
        key,
        name: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' '),
        description: value.description,
        weights: {
            spatial: value.spatial,
            abiotic: value.abiotic,
            functional: value.functional,
            ecosystem: value.ecosystem,
            biotic: value.biotic
        }
    }));

    res.json({
        success: true,
        strategies
    });
});

module.exports = router;
