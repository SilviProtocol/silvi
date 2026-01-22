const express = require('express');

module.exports = (pool) => {
  const router = express.Router();

  /**
   * GET /stats
   * Get statistics about embeddings coverage
   */
  router.get('/stats', async (req, res) => {
    try {
      console.log('GET /embeddings/stats');

      const query = `
        SELECT
          COUNT(DISTINCT taxon_id) as species_with_embeddings,
          COUNT(*) as total_centroids,
          AVG(cluster_size) as avg_cluster_size,
          MAX(cluster_size) as max_cluster_size,
          MIN(cluster_size) as min_cluster_size,
          SUM(total_occurrences) as total_occurrences_analyzed,
          COUNT(DISTINCT clustering_method) as methods_used
        FROM species_alphaearth_centroids
      `;

      const result = await pool.query(query);

      res.json({
        stats: result.rows[0],
        description: 'AlphaEarth embeddings statistics for Treekipedia'
      });

    } catch (error) {
      console.error('Error fetching embeddings stats:', error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id
   * Get all AlphaEarth embedding centroids for a species
   * Returns habitat clusters with 64-D centroids
   */
  router.get('/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      if (!taxon_id) {
        return res.status(400).json({ error: 'Missing required parameter: taxon_id' });
      }

      console.log(`GET /embeddings/${taxon_id}`);

      const query = `
        SELECT
          id,
          taxon_id,
          cluster_id,
          cluster_size,
          total_occurrences,
          clustering_method,
          representative_lat,
          representative_lon,
          representative_year,
          centroid_a00, centroid_a01, centroid_a02, centroid_a03, centroid_a04,
          centroid_a05, centroid_a06, centroid_a07, centroid_a08, centroid_a09,
          centroid_a10, centroid_a11, centroid_a12, centroid_a13, centroid_a14,
          centroid_a15, centroid_a16, centroid_a17, centroid_a18, centroid_a19,
          centroid_a20, centroid_a21, centroid_a22, centroid_a23, centroid_a24,
          centroid_a25, centroid_a26, centroid_a27, centroid_a28, centroid_a29,
          centroid_a30, centroid_a31, centroid_a32, centroid_a33, centroid_a34,
          centroid_a35, centroid_a36, centroid_a37, centroid_a38, centroid_a39,
          centroid_a40, centroid_a41, centroid_a42, centroid_a43, centroid_a44,
          centroid_a45, centroid_a46, centroid_a47, centroid_a48, centroid_a49,
          centroid_a50, centroid_a51, centroid_a52, centroid_a53, centroid_a54,
          centroid_a55, centroid_a56, centroid_a57, centroid_a58, centroid_a59,
          centroid_a60, centroid_a61, centroid_a62, centroid_a63,
          created_at
        FROM species_alphaearth_centroids
        WHERE taxon_id = $1
        ORDER BY cluster_size DESC
      `;

      const result = await pool.query(query, [taxon_id]);

      if (result.rowCount === 0) {
        return res.status(404).json({
          error: 'No embeddings found for this species',
          taxon_id: taxon_id
        });
      }

      console.log(`Found ${result.rowCount} habitat centroids for ${taxon_id}`);

      res.json({
        taxon_id: taxon_id,
        habitat_count: result.rowCount,
        total_occurrences: result.rows[0].total_occurrences,
        centroids: result.rows
      });

    } catch (error) {
      console.error(`Error fetching embeddings for ${req.params.taxon_id}:`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /similar/:taxon_id
   * Find species with similar habitat embeddings
   * Query params:
   *   - limit: Maximum number of similar species to return (default: 10)
   *   - cluster_id: Specific cluster to compare (default: 0, largest cluster)
   */
  router.get('/similar/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const limit = parseInt(req.query.limit) || 10;
      const cluster_id = parseInt(req.query.cluster_id) || 0;

      if (!taxon_id) {
        return res.status(400).json({ error: 'Missing required parameter: taxon_id' });
      }

      console.log(`GET /embeddings/similar/${taxon_id} (cluster=${cluster_id}, limit=${limit})`);

      // First check if the target species has embeddings
      const checkQuery = `
        SELECT COUNT(*) as count
        FROM species_alphaearth_centroids
        WHERE taxon_id = $1
      `;
      const checkResult = await pool.query(checkQuery, [taxon_id]);

      if (checkResult.rows[0].count === 0) {
        return res.status(404).json({
          error: 'No embeddings found for this species',
          taxon_id: taxon_id
        });
      }

      // Calculate cosine similarity using all 64 dimensions
      // Similarity = dot product / (magnitude1 * magnitude2)
      // For standardized centroids, we can use dot product as approximation
      const query = `
        WITH target AS (
          SELECT
            centroid_a00, centroid_a01, centroid_a02, centroid_a03, centroid_a04,
            centroid_a05, centroid_a06, centroid_a07, centroid_a08, centroid_a09,
            centroid_a10, centroid_a11, centroid_a12, centroid_a13, centroid_a14,
            centroid_a15, centroid_a16, centroid_a17, centroid_a18, centroid_a19,
            centroid_a20, centroid_a21, centroid_a22, centroid_a23, centroid_a24,
            centroid_a25, centroid_a26, centroid_a27, centroid_a28, centroid_a29,
            centroid_a30, centroid_a31, centroid_a32, centroid_a33, centroid_a34,
            centroid_a35, centroid_a36, centroid_a37, centroid_a38, centroid_a39,
            centroid_a40, centroid_a41, centroid_a42, centroid_a43, centroid_a44,
            centroid_a45, centroid_a46, centroid_a47, centroid_a48, centroid_a49,
            centroid_a50, centroid_a51, centroid_a52, centroid_a53, centroid_a54,
            centroid_a55, centroid_a56, centroid_a57, centroid_a58, centroid_a59,
            centroid_a60, centroid_a61, centroid_a62, centroid_a63
          FROM species_alphaearth_centroids
          WHERE taxon_id = $1 AND cluster_id = $2
        )
        SELECT
          c.taxon_id,
          s.species_scientific_name,
          s.family,
          c.cluster_id,
          c.cluster_size,
          c.representative_lat,
          c.representative_lon,
          ROUND(
            CAST((
              c.centroid_a00 * t.centroid_a00 + c.centroid_a01 * t.centroid_a01 +
              c.centroid_a02 * t.centroid_a02 + c.centroid_a03 * t.centroid_a03 +
              c.centroid_a04 * t.centroid_a04 + c.centroid_a05 * t.centroid_a05 +
              c.centroid_a06 * t.centroid_a06 + c.centroid_a07 * t.centroid_a07 +
              c.centroid_a08 * t.centroid_a08 + c.centroid_a09 * t.centroid_a09 +
              c.centroid_a10 * t.centroid_a10 + c.centroid_a11 * t.centroid_a11 +
              c.centroid_a12 * t.centroid_a12 + c.centroid_a13 * t.centroid_a13 +
              c.centroid_a14 * t.centroid_a14 + c.centroid_a15 * t.centroid_a15 +
              c.centroid_a16 * t.centroid_a16 + c.centroid_a17 * t.centroid_a17 +
              c.centroid_a18 * t.centroid_a18 + c.centroid_a19 * t.centroid_a19 +
              c.centroid_a20 * t.centroid_a20 + c.centroid_a21 * t.centroid_a21 +
              c.centroid_a22 * t.centroid_a22 + c.centroid_a23 * t.centroid_a23 +
              c.centroid_a24 * t.centroid_a24 + c.centroid_a25 * t.centroid_a25 +
              c.centroid_a26 * t.centroid_a26 + c.centroid_a27 * t.centroid_a27 +
              c.centroid_a28 * t.centroid_a28 + c.centroid_a29 * t.centroid_a29 +
              c.centroid_a30 * t.centroid_a30 + c.centroid_a31 * t.centroid_a31 +
              c.centroid_a32 * t.centroid_a32 + c.centroid_a33 * t.centroid_a33 +
              c.centroid_a34 * t.centroid_a34 + c.centroid_a35 * t.centroid_a35 +
              c.centroid_a36 * t.centroid_a36 + c.centroid_a37 * t.centroid_a37 +
              c.centroid_a38 * t.centroid_a38 + c.centroid_a39 * t.centroid_a39 +
              c.centroid_a40 * t.centroid_a40 + c.centroid_a41 * t.centroid_a41 +
              c.centroid_a42 * t.centroid_a42 + c.centroid_a43 * t.centroid_a43 +
              c.centroid_a44 * t.centroid_a44 + c.centroid_a45 * t.centroid_a45 +
              c.centroid_a46 * t.centroid_a46 + c.centroid_a47 * t.centroid_a47 +
              c.centroid_a48 * t.centroid_a48 + c.centroid_a49 * t.centroid_a49 +
              c.centroid_a50 * t.centroid_a50 + c.centroid_a51 * t.centroid_a51 +
              c.centroid_a52 * t.centroid_a52 + c.centroid_a53 * t.centroid_a53 +
              c.centroid_a54 * t.centroid_a54 + c.centroid_a55 * t.centroid_a55 +
              c.centroid_a56 * t.centroid_a56 + c.centroid_a57 * t.centroid_a57 +
              c.centroid_a58 * t.centroid_a58 + c.centroid_a59 * t.centroid_a59 +
              c.centroid_a60 * t.centroid_a60 + c.centroid_a61 * t.centroid_a61 +
              c.centroid_a62 * t.centroid_a62 + c.centroid_a63 * t.centroid_a63
            ) AS NUMERIC), 6) as similarity_score
        FROM species_alphaearth_centroids c
        CROSS JOIN target t
        JOIN species s ON c.taxon_id = s.taxon_id
        WHERE c.taxon_id != $1
        ORDER BY similarity_score DESC
        LIMIT $3
      `;

      const result = await pool.query(query, [taxon_id, cluster_id, limit]);

      console.log(`Found ${result.rowCount} similar species for ${taxon_id}`);

      res.json({
        query_taxon_id: taxon_id,
        query_cluster_id: cluster_id,
        similar_species: result.rows
      });

    } catch (error) {
      console.error(`Error finding similar species for ${req.params.taxon_id}:`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * POST /predict
   * Predict species from a raw embedding vector (e.g., from clicked location)
   * Body: { embedding: { a00: 0.123, a01: -0.456, ..., a63: 0.789 }, limit: 10, lat?: number, lon?: number }
   *        OR { embedding: [0.123, -0.456, ..., 0.789], limit: 10, lat?: number, lon?: number }
   *
   * UPGRADED: Now uses species_habitat_centroids (17,924 species, 44,625 clusters)
   * with pgvector IVFFlat index for <1ms queries.
   * Includes native/introduced/invasive status when lat/lon provided.
   */
  router.post('/predict', async (req, res) => {
    try {
      const { embedding, limit = 10, lat, lon } = req.body;

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

      console.log(`POST /embeddings/predict (limit=${limit}) - Using NEW 17,924 species database`);

      // Get location context if lat/lon provided (for native status determination)
      let ecoregion = null;
      let countries = [];
      let wcvpPatterns = [];

      if (lat !== undefined && lon !== undefined) {
        try {
          // Get ecoregion at point
          const ecoResult = await pool.query(`
            SELECT eco_id, eco_name, biome_name, realm
            FROM ecoregions
            WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
            LIMIT 1
          `, [parseFloat(lon), parseFloat(lat)]);

          if (ecoResult.rows.length > 0) {
            ecoregion = ecoResult.rows[0];

            // Get countries for this ecoregion
            const countriesResult = await pool.query(`
              SELECT DISTINCT
                CASE
                  WHEN c.name_en = 'United States of America' THEN 'United States'
                  WHEN c.name_en = 'United Kingdom' THEN 'United Kingdom'
                  ELSE c.name_en
                END as country_name
              FROM ecoregions e
              JOIN countries c ON ST_Intersects(e.geom, c.geom)
              WHERE e.eco_id = $1
            `, [ecoregion.eco_id]);
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
      }

      // Convert to pgvector format
      const vectorString = `[${embeddingArray.join(',')}]`;
      const resultLimit = Math.min(parseInt(limit), 100);

      // Query using pgvector cosine similarity with IVFFlat index
      // Include WCVP fields for native status
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
            s.wcvp_native,
            s.wcvp_introduced,
            s.countries_invasive,
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

      // Helper functions for native status
      const matchesWcvpPatterns = (wcvpField) => {
        if (!wcvpField || wcvpPatterns.length === 0) return false;
        const fieldLower = wcvpField.toLowerCase();
        return wcvpPatterns.some(pattern => fieldLower.includes(pattern));
      };

      const isInvasiveInCountries = (invasiveField) => {
        if (!invasiveField || countries.length === 0) return false;
        const invasiveLower = invasiveField.toLowerCase();
        return countries.some(country => invasiveLower.includes(country.toLowerCase()));
      };

      // Track native status summary
      const nativeStatusSummary = {
        native: 0,
        introduced: 0,
        invasive: 0,
        native_and_introduced: 0,
        unknown: 0
      };

      // Format predictions to match frontend expectations (backwards compatible)
      const predictions = result.rows.slice(0, resultLimit).map(row => {
        // Determine native status
        const isNative = matchesWcvpPatterns(row.wcvp_native);
        const isIntroduced = matchesWcvpPatterns(row.wcvp_introduced);
        const isInvasive = isInvasiveInCountries(row.countries_invasive);

        let native_status = 'unknown';
        if (isInvasive) {
          native_status = 'invasive';
        } else if (isNative && !isIntroduced) {
          native_status = 'native';
        } else if (isIntroduced && !isNative) {
          native_status = 'introduced';
        } else if (isNative && isIntroduced) {
          native_status = 'native_and_introduced';
        }

        nativeStatusSummary[native_status]++;

        return {
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
          // Native status info
          native_status,
          is_native: isNative,
          is_introduced: isIntroduced,
          is_invasive: isInvasive
        };
      });

      console.log(`Found ${predictions.length} species predictions (17,924 species database)`);
      if (predictions.length > 0) {
        console.log(`Top prediction: ${predictions[0].species_scientific_name} (confidence: ${predictions[0].confidence.toFixed(4)})`);
      }

      res.json({
        success: true,
        prediction_count: predictions.length,
        location_context: ecoregion ? {
          ecoregion: {
            eco_id: ecoregion.eco_id,
            eco_name: ecoregion.eco_name,
            biome_name: ecoregion.biome_name,
            realm: ecoregion.realm
          },
          countries: countries
        } : null,
        native_status_summary: nativeStatusSummary,
        predictions
      });

    } catch (error) {
      console.error('Error predicting species from embedding:', error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  return router;
};
