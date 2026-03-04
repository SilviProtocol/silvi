const express = require('express');
const { authenticateUser } = require('../middleware/userAuth');

module.exports = (pool) => {
  const router = express.Router();

  // All routes require authentication
  router.use(authenticateUser);

  /**
   * POST /api/analyses — Save a new analysis
   */
  router.post('/', async (req, res) => {
    try {
      const userId = req.user.id;
      const {
        aoi_type, aoi_geometry, aoi_label, aoi_center,
        area_hectares, summary_data, prediction_data,
        recommendation_data, recommendation_strategy, ecoregion_ids
      } = req.body;

      if (!aoi_type || !aoi_geometry) {
        return res.status(400).json({ error: 'aoi_type and aoi_geometry are required' });
      }

      const result = await pool.query(`
        INSERT INTO user_analyses (
          user_id, aoi_type, aoi_geometry, aoi_label, aoi_center,
          area_hectares, summary_data, prediction_data,
          recommendation_data, recommendation_strategy, ecoregion_ids
        ) VALUES (
          $1, $2, ST_SetSRID(ST_GeomFromGeoJSON($3), 4326), $4,
          CASE WHEN $5::jsonb IS NOT NULL THEN ST_SetSRID(ST_GeomFromGeoJSON($5), 4326) ELSE NULL END,
          $6, $7, $8, $9, $10, $11
        ) RETURNING id, aoi_type, aoi_label, area_hectares, status, created_at, updated_at
      `, [
        userId, aoi_type, JSON.stringify(aoi_geometry), aoi_label,
        aoi_center ? JSON.stringify(aoi_center) : null,
        area_hectares, JSON.stringify(summary_data), JSON.stringify(prediction_data),
        JSON.stringify(recommendation_data), recommendation_strategy, ecoregion_ids
      ]);

      res.status(201).json(result.rows[0]);
    } catch (error) {
      console.error('Error saving analysis:', error);
      res.status(500).json({ error: 'Failed to save analysis' });
    }
  });

  /**
   * GET /api/analyses — List user's analyses
   */
  router.get('/', async (req, res) => {
    try {
      const userId = req.user.id;
      const limit = Math.min(parseInt(req.query.limit || '20'), 100);
      const offset = parseInt(req.query.offset || '0');

      const result = await pool.query(`
        SELECT id, aoi_type, aoi_label, area_hectares,
               summary_data, recommendation_strategy,
               status, created_at, updated_at
        FROM user_analyses
        WHERE user_id = $1 AND status != 'deleted'
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
      `, [userId, limit, offset]);

      res.json(result.rows);
    } catch (error) {
      console.error('Error listing analyses:', error);
      res.status(500).json({ error: 'Failed to list analyses' });
    }
  });

  /**
   * GET /api/analyses/:id — Get a single analysis
   */
  router.get('/:id', async (req, res) => {
    try {
      const userId = req.user.id;
      const { id } = req.params;

      const result = await pool.query(`
        SELECT id, aoi_type, aoi_label, area_hectares,
               summary_data, prediction_data, recommendation_data,
               recommendation_strategy, ecoregion_ids,
               status, created_at, updated_at
        FROM user_analyses
        WHERE id = $1 AND user_id = $2
      `, [id, userId]);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Analysis not found' });
      }

      res.json(result.rows[0]);
    } catch (error) {
      console.error('Error fetching analysis:', error);
      res.status(500).json({ error: 'Failed to fetch analysis' });
    }
  });

  /**
   * PATCH /api/analyses/:id — Update with prediction/recommendation results
   */
  router.patch('/:id', async (req, res) => {
    try {
      const userId = req.user.id;
      const { id } = req.params;
      const { prediction_data, recommendation_data, recommendation_strategy, status } = req.body;

      // Build dynamic SET clause
      const sets = [];
      const values = [id, userId];
      let paramIdx = 3;

      if (prediction_data !== undefined) {
        sets.push(`prediction_data = $${paramIdx++}`);
        values.push(JSON.stringify(prediction_data));
      }
      if (recommendation_data !== undefined) {
        sets.push(`recommendation_data = $${paramIdx++}`);
        values.push(JSON.stringify(recommendation_data));
      }
      if (recommendation_strategy !== undefined) {
        sets.push(`recommendation_strategy = $${paramIdx++}`);
        values.push(recommendation_strategy);
      }
      if (status !== undefined) {
        sets.push(`status = $${paramIdx++}`);
        values.push(status);
      }

      if (sets.length === 0) {
        return res.status(400).json({ error: 'No fields to update' });
      }

      sets.push('updated_at = NOW()');

      const result = await pool.query(`
        UPDATE user_analyses
        SET ${sets.join(', ')}
        WHERE id = $1 AND user_id = $2
        RETURNING id, aoi_type, aoi_label, status, updated_at
      `, values);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Analysis not found' });
      }

      res.json(result.rows[0]);
    } catch (error) {
      console.error('Error updating analysis:', error);
      res.status(500).json({ error: 'Failed to update analysis' });
    }
  });

  return router;
};
