const express = require('express');

/**
 * Research Controller
 *
 * NEW ARCHITECTURE (Jan 2026):
 * - Research is performed by Claude Code CLI sessions (not Perplexity/OpenAI)
 * - This controller provides endpoints to:
 *   1. GET research data from species._ai columns
 *   2. Add species to research_queue for CLI processing
 *   3. Check queue status
 *
 * The actual research is done via:
 * - orchestrator/research_orchestrator.py (port 5003)
 * - scripts/research_species.py --next
 * - Claude Code CLI with auto-approved WebSearch
 */

module.exports = (pool) => {
  const router = express.Router();

  /**
   * GET /research/:taxon_id
   * Get research data for a specific species
   */
  router.get('/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      // Query species table for AI fields
      const query = `
        SELECT
          taxon_id,
          species_scientific_name,
          researched,
          conservation_status_ai,
          general_description_ai,
          habitat_ai,
          elevation_ranges_ai,
          compatible_soil_types_ai,
          ecological_function_ai,
          native_adapted_habitats_ai,
          agroforestry_use_cases_ai,
          growth_form_ai,
          leaf_type_ai,
          deciduous_evergreen_ai,
          flower_color_ai,
          fruit_type_ai,
          bark_characteristics_ai,
          maximum_height_ai,
          maximum_diameter_ai,
          lifespan_ai,
          maximum_tree_age_ai,
          stewardship_best_practices_ai,
          planting_recipes_ai,
          pruning_maintenance_ai,
          disease_pest_management_ai,
          fire_management_ai,
          cultural_significance_ai,
          popular_common_name_ai,
          etymology_ai,
          synonyms_ai,
          identification_features_ai,
          climate_tolerance_ai,
          tolerances_ai,
          associated_species_ai,
          timber_value_ai,
          non_timber_products_ai,
          nutritional_caloric_value_ai
        FROM species
        WHERE taxon_id = $1
      `;

      const result = await pool.query(query, [taxon_id]);

      if (result.rows.length === 0) {
        return res.status(404).json({
          error: 'Species not found',
          taxon_id
        });
      }

      const speciesData = result.rows[0];

      // Check for research status in the queue
      const queueQuery = `
        SELECT status, error_message, completed_at
        FROM research_queue
        WHERE taxon_id = $1
      `;

      const queueResult = await pool.query(queueQuery, [taxon_id]);

      // If in queue, include the status
      if (queueResult.rows.length > 0) {
        speciesData.research_queue_status = queueResult.rows[0].status;
        speciesData.research_completed_at = queueResult.rows[0].completed_at;

        // If still being researched, return that info
        if (['pending', 'processing'].includes(queueResult.rows[0].status)) {
          return res.json({
            ...speciesData,
            researching: true,
            message: `Research is ${queueResult.rows[0].status}. Check back soon!`,
          });
        }
      }

      // Check if species has been researched by looking at critical AI fields
      const criticalFields = [
        'general_description_ai',
        'ecological_function_ai',
        'habitat_ai'
      ];

      let hasResearch = criticalFields.some(field =>
        speciesData[field] && speciesData[field].trim() !== ''
      );

      if (!hasResearch) {
        return res.status(404).json({
          error: 'Research not found',
          message: 'This species has not been researched yet',
          taxon_id
        });
      }

      res.json(speciesData);
    } catch (error) {
      console.error('Error getting research data:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * POST /research/fund-research
   * Add species to research queue (legacy endpoint for frontend compatibility)
   *
   * NEW: This now adds to research_queue for Claude Code CLI processing
   * instead of calling Perplexity/OpenAI directly.
   */
  router.post('/fund-research', async (req, res) => {
    try {
      const { taxon_id, wallet_address, chain, transaction_hash, scientific_name } = req.body;

      console.log(`[fund-research] Request for taxon_id=${taxon_id}, wallet=${wallet_address}`);

      if (!taxon_id) {
        return res.status(400).json({
          error: 'Missing required field: taxon_id'
        });
      }

      // Get species info
      const speciesResult = await pool.query(
        `SELECT taxon_id, species_scientific_name, researched FROM species WHERE taxon_id = $1`,
        [taxon_id]
      );

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }

      const species = speciesResult.rows[0];
      const speciesName = scientific_name || species.species_scientific_name;

      // Check if already in queue
      const queueCheck = await pool.query(
        `SELECT id, status FROM research_queue WHERE taxon_id = $1`,
        [taxon_id]
      );

      if (queueCheck.rows.length > 0) {
        const status = queueCheck.rows[0].status;
        if (status === 'pending' || status === 'processing') {
          return res.json({
            success: true,
            taxon_id,
            species_name: speciesName,
            message: `Already in queue with status: ${status}`,
            queue_status: status,
            queued: true
          });
        }
        // Re-queue if completed/failed
        await pool.query(
          `UPDATE research_queue SET status = 'pending', queued_at = NOW(),
           started_at = NULL, completed_at = NULL, error_message = NULL
           WHERE taxon_id = $1`,
          [taxon_id]
        );
      } else {
        // Add to queue
        await pool.query(
          `INSERT INTO research_queue (taxon_id, species_name, status, priority, queued_at)
           VALUES ($1, $2, 'pending', 50, NOW())`,
          [taxon_id, speciesName]
        );
      }

      console.log(`[fund-research] Added ${speciesName} (${taxon_id}) to research queue`);

      res.json({
        success: true,
        taxon_id,
        species_name: speciesName,
        message: 'Added to research queue for Claude Code CLI processing',
        queue_status: 'pending',
        queued: true,
        note: 'Research will be processed by CLI. Run: python scripts/research_species.py --next'
      });

    } catch (error) {
      console.error('Error in fund-research:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * GET /research/queue/status
   * Get status of the research queue
   */
  router.get('/queue/status', async (req, res) => {
    try {
      // Get queue statistics from research_queue table
      const stats = await pool.query(`
        SELECT
          status,
          COUNT(*) as count
        FROM research_queue
        GROUP BY status
      `);

      // Get pending/processing items
      const inProgress = await pool.query(`
        SELECT
          taxon_id,
          species_name,
          status,
          queued_at,
          started_at
        FROM research_queue
        WHERE status IN ('pending', 'processing')
        ORDER BY priority DESC, queued_at ASC
        LIMIT 20
      `);

      // Get recent completed
      const recentCompleted = await pool.query(`
        SELECT
          taxon_id,
          species_name,
          status,
          completed_at
        FROM research_queue
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 5
      `);

      res.json({
        stats: stats.rows,
        in_progress: inProgress.rows,
        recent_completed: recentCompleted.rows,
        note: 'Research performed by Claude Code CLI via orchestrator (port 5003)'
      });
    } catch (error) {
      console.error('Error getting queue status:', error);
      res.status(500).json({ error: error.message });
    }
  });

  return {
    router
  };
};
