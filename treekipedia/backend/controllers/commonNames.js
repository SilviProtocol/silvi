/**
 * Common Names Controller
 *
 * Endpoints:
 *   GET  /api/common-names/light-list    — Bulk species list with structured common names for sync
 *   POST /api/common-names/:taxon_id     — Submit a new common name (user contribution)
 *   GET  /api/common-names/:taxon_id     — Get all common names for a species
 */

const express = require('express');

module.exports = function(pool) {
  const router = express.Router();

  /**
   * GET /light-list
   *
   * Paginated bulk download of species with pre-aggregated common names.
   * Designed for Silvi app sync — returns only fields needed for search/display.
   *
   * Query params:
   *   - page (default 1)
   *   - per_page (default 10000, max 10000)
   *   - since (ISO timestamp — only species updated after this date)
   *   - family (filter by family)
   */
  router.get('/light-list', async (req, res) => {
    try {
      const page = Math.max(1, parseInt(req.query.page) || 1);
      const perPage = Math.min(10000, Math.max(1, parseInt(req.query.per_page) || 10000));
      const since = req.query.since || null;
      const family = req.query.family || null;
      const offset = (page - 1) * perPage;

      // Build WHERE clauses
      const conditions = [];
      const params = [];
      let paramIdx = 1;

      if (since) {
        conditions.push(`(s.updated_at > $${paramIdx} OR cn_agg.latest_update > $${paramIdx})`);
        params.push(since);
        paramIdx++;
      }

      if (family) {
        conditions.push(`s.family = $${paramIdx}`);
        params.push(family);
        paramIdx++;
      }

      const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

      // Count total
      const countResult = await pool.query(`
        SELECT COUNT(*) as total
        FROM species s
        LEFT JOIN LATERAL (
          SELECT MAX(updated_at) as latest_update
          FROM species_common_names WHERE taxon_id = s.taxon_id
        ) cn_agg ON true
        ${whereClause}
      `, params);
      const total = parseInt(countResult.rows[0].total);

      // Fetch species with aggregated common names
      const dataParams = [...params, perPage, offset];
      const result = await pool.query(`
        SELECT
          s.taxon_id,
          s.species_scientific_name AS scientific_name,
          s.display_common_name,
          s.family,
          s.genus,
          COALESCE(
            (
              SELECT json_agg(json_build_object(
                'name', cn.name,
                'lang', cn.language_code,
                'regions', cn.region_codes,
                'primary', cn.is_primary
              ) ORDER BY cn.is_primary DESC, cn.created_at ASC)
              FROM species_common_names cn
              WHERE cn.taxon_id = s.taxon_id AND cn.staging = false
            ),
            '[]'::json
          ) AS common_names
        FROM species s
        LEFT JOIN LATERAL (
          SELECT MAX(updated_at) as latest_update
          FROM species_common_names WHERE taxon_id = s.taxon_id
        ) cn_agg ON true
        ${whereClause}
        ORDER BY s.taxon_id
        LIMIT $${paramIdx} OFFSET $${paramIdx + 1}
      `, dataParams);

      res.json({
        total,
        page,
        per_page: perPage,
        pages: Math.ceil(total / perPage),
        updated_since: since,
        version: new Date().toISOString(),
        data: result.rows
      });

    } catch (error) {
      console.error('Error fetching light list:', error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id
   *
   * Get all common names for a species, ordered by primary status and language.
   */
  router.get('/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const includeStaging = req.query.include_staging === 'true';

      const stagingFilter = includeStaging ? '' : 'AND staging = false';

      const result = await pool.query(`
        SELECT id, name, language_code, region_codes, source, is_primary, staging, created_at
        FROM species_common_names
        WHERE taxon_id = $1 ${stagingFilter}
        ORDER BY is_primary DESC, language_code NULLS LAST, created_at ASC
      `, [taxon_id]);

      // Also get the display name
      const speciesResult = await pool.query(`
        SELECT display_common_name, popular_common_name_ai
        FROM species WHERE taxon_id = $1
      `, [taxon_id]);

      const species = speciesResult.rows[0] || {};

      res.json({
        taxon_id,
        display_common_name: species.display_common_name || null,
        popular_common_name_ai: species.popular_common_name_ai || null,
        common_names: result.rows,
        count: result.rowCount
      });

    } catch (error) {
      console.error(`Error fetching common names for ${req.params.taxon_id}:`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * POST /:taxon_id
   *
   * Submit a new common name for a species (user contribution).
   * Goes into staging by default.
   *
   * Body:
   *   - name (required): The common name
   *   - language_code (optional): ISO 639-1 code
   *   - region_codes (optional): Array of ISO 3166-1 alpha-2 codes
   *   - submitted_by (optional): User identifier
   */
  router.post('/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const { name, language_code, region_codes, submitted_by } = req.body;

      if (!name || name.trim().length < 2) {
        return res.status(400).json({ error: 'Name is required and must be at least 2 characters' });
      }

      // Verify species exists
      const speciesCheck = await pool.query(
        'SELECT taxon_id FROM species WHERE taxon_id = $1',
        [taxon_id]
      );
      if (speciesCheck.rowCount === 0) {
        return res.status(404).json({ error: `Species ${taxon_id} not found` });
      }

      // Validate region_codes format if provided
      if (region_codes && !Array.isArray(region_codes)) {
        return res.status(400).json({ error: 'region_codes must be an array of ISO 3166-1 alpha-2 codes' });
      }

      const result = await pool.query(`
        INSERT INTO species_common_names (taxon_id, name, language_code, region_codes, source, submitted_by, staging)
        VALUES ($1, $2, $3, $4, 'user', $5, true)
        ON CONFLICT (taxon_id, name, language_code) DO UPDATE SET
          region_codes = COALESCE(
            NULLIF(array_cat(species_common_names.region_codes, $4), '{}'),
            species_common_names.region_codes
          ),
          updated_at = NOW()
        RETURNING id, taxon_id, name, language_code, region_codes, staging, created_at
      `, [
        taxon_id,
        name.trim(),
        language_code || null,
        region_codes || null,
        submitted_by || null
      ]);

      res.status(201).json(result.rows[0]);

    } catch (error) {
      console.error(`Error adding common name for ${req.params.taxon_id}:`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  return router;
};
