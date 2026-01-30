const express = require('express');
const { v4: uuidv4 } = require('uuid');

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

/**
 * Sync current insights back to species._ai columns
 */
async function syncInsightsToSpeciesColumns(pool, taxonId) {
  const NUMERIC_CLAIMS = ['maximum_height', 'maximum_diameter', 'maximum_tree_age'];

  const insightsResult = await pool.query(
    `SELECT claim_type, claim_value, confidence
     FROM insights WHERE taxon_id = $1 AND is_current = TRUE
     ORDER BY claim_type, confidence DESC`,
    [taxonId]
  );

  if (insightsResult.rows.length === 0) return { synced: 0 };

  // Group by claim_type
  const byType = {};
  for (const row of insightsResult.rows) {
    if (!byType[row.claim_type]) byType[row.claim_type] = [];
    byType[row.claim_type].push(row);
  }

  const setClauses = [];
  const values = [];
  let idx = 1;

  for (const [claimType, insights] of Object.entries(byType)) {
    const colName = claimType + '_ai';

    let val;
    if (NUMERIC_CLAIMS.includes(claimType)) {
      const top = insights[0].claim_value;
      val = typeof top === 'object' ? top.value : top;
    } else {
      const texts = insights.map(i => {
        const v = i.claim_value;
        return typeof v === 'object' ? (v.text || JSON.stringify(v)) : String(v);
      });
      val = [...new Set(texts)].join('\n\n');
    }

    setClauses.push(`${colName} = $${idx}`);
    values.push(val);
    idx++;
  }

  if (setClauses.length === 0) return { synced: 0 };

  values.push(taxonId);
  try {
    await pool.query(
      `UPDATE species SET ${setClauses.join(', ')} WHERE taxon_id = $${idx}`,
      values
    );
  } catch (err) {
    // Some _ai columns may not exist yet for newer fields — log and continue
    console.warn(`[syncInsights] Partial sync for ${taxonId}:`, err.message);
  }

  return { synced: setClauses.length };
}

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

  /**
   * POST /research/queue/bulk-add
   * Add multiple species to the research queue at once.
   * Expects: { taxon_ids: ["id1", "id2", ...], priority?: number }
   * Skips species already in queue with pending/processing status.
   */
  router.post('/queue/bulk-add', async (req, res) => {
    try {
      const { taxon_ids, priority } = req.body;
      const prio = priority || 50;

      if (!taxon_ids || !Array.isArray(taxon_ids) || taxon_ids.length === 0) {
        return res.status(400).json({ error: 'taxon_ids array is required' });
      }

      // Look up species names
      const speciesResult = await pool.query(
        `SELECT taxon_id, species_scientific_name FROM species WHERE taxon_id = ANY($1)`,
        [taxon_ids]
      );
      const nameMap = {};
      for (const row of speciesResult.rows) {
        nameMap[row.taxon_id] = row.species_scientific_name;
      }

      // Check which are already queued as pending/processing
      const existingResult = await pool.query(
        `SELECT taxon_id FROM research_queue WHERE taxon_id = ANY($1) AND status IN ('pending', 'processing')`,
        [taxon_ids]
      );
      const alreadyQueued = new Set(existingResult.rows.map(r => r.taxon_id));

      let added = 0;
      let skipped = 0;
      const notFound = [];

      for (const taxonId of taxon_ids) {
        if (!nameMap[taxonId]) {
          notFound.push(taxonId);
          continue;
        }
        if (alreadyQueued.has(taxonId)) {
          skipped++;
          continue;
        }
        // Upsert: insert or reset if previously completed/failed
        await pool.query(`
          INSERT INTO research_queue (taxon_id, species_name, status, priority, queued_at)
          VALUES ($1, $2, 'pending', $3, NOW())
          ON CONFLICT (taxon_id) DO UPDATE SET
            status = 'pending', priority = $3, queued_at = NOW(),
            started_at = NULL, completed_at = NULL, error_message = NULL
        `, [taxonId, nameMap[taxonId], prio]);
        added++;
      }

      res.json({
        success: true,
        added,
        skipped,
        not_found: notFound,
        total_in_queue: added + skipped
      });
    } catch (error) {
      console.error('Error bulk-adding to queue:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // ─── CLI Orchestrator Endpoints ───────────────────────────────────
  // These replace the never-built port 5003 orchestrator service.
  // Used by the Claude Code species-research skill.

  /**
   * GET /research/queue/next
   * Pop the next pending species from the research queue
   */
  router.get('/queue/next', async (req, res) => {
    try {
      const result = await pool.query(`
        SELECT id, taxon_id, species_name, priority, queued_at
        FROM research_queue
        WHERE status = 'pending'
        ORDER BY priority DESC, queued_at ASC
        LIMIT 1
      `);

      if (result.rows.length === 0) {
        return res.json({ queue_empty: true, message: 'No pending species in queue' });
      }

      const item = result.rows[0];
      res.json({
        queue_id: item.id,
        taxon_id: item.taxon_id,
        species_name: item.species_name,
        priority: item.priority,
        queued_at: item.queued_at
      });
    } catch (error) {
      console.error('Error getting next queue item:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * POST /research/queue/:id/start
   * Mark a queue item as processing
   */
  router.post('/queue/:id/start', async (req, res) => {
    try {
      const { id } = req.params;
      await pool.query(
        `UPDATE research_queue SET status = 'processing', started_at = NOW() WHERE id = $1`,
        [id]
      );
      res.json({ success: true, status: 'processing' });
    } catch (error) {
      console.error('Error starting queue item:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * POST /research/queue/:id/complete
   * Mark a queue item as completed
   */
  router.post('/queue/:id/complete', async (req, res) => {
    try {
      const { id } = req.params;
      await pool.query(
        `UPDATE research_queue SET status = 'completed', completed_at = NOW() WHERE id = $1`,
        [id]
      );
      res.json({ success: true, status: 'completed' });
    } catch (error) {
      console.error('Error completing queue item:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * GET /research/:taxon_id/context
   * Get research context for a species — tells the CLI skill whether
   * this is first research or re-research, and which fields to focus on.
   */
  router.get('/:taxon_id/context', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      // Get species basic info
      const speciesResult = await pool.query(
        `SELECT taxon_id, species_scientific_name, common_name, research_version
         FROM species WHERE taxon_id = $1`,
        [taxon_id]
      );

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }

      const species = speciesResult.rows[0];
      const version = species.research_version || 0;

      // Get existing insights
      const insightsResult = await pool.query(
        `SELECT claim_type, confidence, claim_value
         FROM insights WHERE taxon_id = $1 AND is_current = TRUE`,
        [taxon_id]
      );

      const existingInsights = insightsResult.rows;
      const isFirst = existingInsights.length === 0;

      const ALL_FIELDS = [
        'popular_common_name', 'etymology', 'synonyms', 'identification_features',
        'general_description', 'habitat', 'elevation_ranges', 'ecological_function',
        'native_adapted_habitats', 'conservation_status', 'compatible_soil_types',
        'climate_tolerance', 'tolerances', 'associated_species',
        'growth_form', 'leaf_type', 'deciduous_evergreen', 'flower_color',
        'fruit_type', 'bark_characteristics', 'maximum_height', 'maximum_diameter',
        'lifespan', 'maximum_tree_age',
        'stewardship_best_practices', 'planting_recipes', 'pruning_maintenance',
        'disease_pest_management', 'fire_management', 'propagation_methods',
        'cultural_significance', 'agroforestry_use_cases', 'timber_value',
        'non_timber_products', 'nutritional_caloric_value'
      ];

      if (isFirst) {
        return res.json({
          taxon_id,
          species_name: species.species_scientific_name || species.common_name,
          is_first_research: true,
          existing_version: version,
          existing_insight_count: 0,
          recommended_focus: 'full',
          priority_fields: ALL_FIELDS,
          skip_fields: []
        });
      }

      // Analyze existing insights for gaps/weaknesses
      const coveredFields = [...new Set(existingInsights.map(i => i.claim_type))];
      const missingFields = ALL_FIELDS.filter(f => !coveredFields.includes(f));

      const highConfidence = existingInsights
        .filter(i => i.confidence >= 0.8)
        .map(i => i.claim_type);
      const lowConfidence = existingInsights
        .filter(i => i.confidence < 0.6)
        .map(i => i.claim_type);

      const priorityFields = [...new Set([...missingFields, ...lowConfidence])];
      const skipFields = highConfidence.filter(f => !lowConfidence.includes(f));

      res.json({
        taxon_id,
        species_name: species.species_scientific_name || species.common_name,
        is_first_research: false,
        existing_version: version,
        existing_insight_count: existingInsights.length,
        recommended_focus: missingFields.length > 10 ? 'gaps' : 'refresh',
        high_confidence_fields: [...new Set(highConfidence)],
        low_confidence_fields: [...new Set(lowConfidence)],
        missing_fields: missingFields,
        priority_fields: priorityFields,
        skip_fields: skipFields
      });
    } catch (error) {
      console.error('Error getting research context:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * POST /research/:taxon_id/save
   * Save atomic insights from CLI research.
   * Expects: { session_id, model_version, insights: [...] }
   * Each insight: { claim_type, claim_value, methodology, sources }
   */
  router.post('/:taxon_id/save', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const { session_id, model_version, insights } = req.body;

      if (!insights || !Array.isArray(insights) || insights.length === 0) {
        return res.status(400).json({ error: 'insights array is required' });
      }

      // Always use a valid UUID for research_session_id
      const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      const researchSessionId = (session_id && UUID_REGEX.test(session_id))
        ? session_id : uuidv4();

      // Mark old insights as superseded
      await pool.query(
        `UPDATE insights SET is_current = FALSE, updated_at = NOW()
         WHERE taxon_id = $1 AND is_current = TRUE`,
        [taxon_id]
      );

      let saved = 0;
      let failed = 0;

      for (const insight of insights) {
        try {
          // Calculate confidence from sources if not provided
          let confidence = insight.confidence;
          if (!confidence && insight.sources && insight.sources.length > 0) {
            const avgCredibility = insight.sources.reduce(
              (sum, s) => sum + (s.credibility || 0.7), 0
            ) / insight.sources.length;
            // Factor in number of sources
            const sourceBonus = Math.min(insight.sources.length * 0.03, 0.1);
            confidence = Math.min(avgCredibility + sourceBonus, 0.98);
          }
          confidence = confidence || 0.7;

          await pool.query(`
            INSERT INTO insights (
              taxon_id, claim_type, claim_value, confidence, sources,
              is_current, research_session_id
            ) VALUES ($1, $2, $3, $4, $5, TRUE, $6)
          `, [
            taxon_id,
            insight.claim_type,
            JSON.stringify(insight.claim_value),
            confidence,
            JSON.stringify(insight.sources || []),
            researchSessionId
          ]);
          saved++;
        } catch (err) {
          console.warn(`Failed to save insight ${insight.claim_type}:`, err.message);
          failed++;
        }
      }

      // Update species research metadata
      const avgConfResult = await pool.query(
        `SELECT AVG(confidence) as avg_conf FROM insights
         WHERE taxon_id = $1 AND is_current = TRUE`,
        [taxon_id]
      );
      const avgConfidence = parseFloat(avgConfResult.rows[0].avg_conf) || 0;

      await pool.query(`
        UPDATE species SET
          research_version = COALESCE(research_version, 0) + 1,
          research_date = NOW(),
          research_agent = $2,
          research_confidence = $3
        WHERE taxon_id = $1
      `, [taxon_id, model_version || 'claude-cli', avgConfidence]);

      // Sync insights to species _ai columns
      await syncInsightsToSpeciesColumns(pool, taxon_id);

      const newVersion = await pool.query(
        `SELECT research_version FROM species WHERE taxon_id = $1`,
        [taxon_id]
      );

      res.json({
        success: true,
        taxon_id,
        insights_saved: saved,
        insights_failed: failed,
        average_confidence: Math.round(avgConfidence * 1000) / 1000,
        version: newVersion.rows[0]?.research_version || 1,
        superseded_count: 0 // already marked above
      });
    } catch (error) {
      console.error('Error saving research insights:', error);
      res.status(500).json({ error: error.message });
    }
  });

  /**
   * GET /research/insights/:taxon_id/gaps
   * Find fields missing or low-confidence for a species
   */
  router.get('/insights/:taxon_id/gaps', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      const ALL_FIELDS = [
        'popular_common_name', 'etymology', 'synonyms', 'identification_features',
        'general_description', 'habitat', 'elevation_ranges', 'ecological_function',
        'native_adapted_habitats', 'conservation_status', 'compatible_soil_types',
        'climate_tolerance', 'tolerances', 'associated_species',
        'growth_form', 'leaf_type', 'deciduous_evergreen', 'flower_color',
        'fruit_type', 'bark_characteristics', 'maximum_height', 'maximum_diameter',
        'lifespan', 'maximum_tree_age',
        'stewardship_best_practices', 'planting_recipes', 'pruning_maintenance',
        'disease_pest_management', 'fire_management', 'propagation_methods',
        'cultural_significance', 'agroforestry_use_cases', 'timber_value',
        'non_timber_products', 'nutritional_caloric_value'
      ];

      const result = await pool.query(
        `SELECT claim_type, COUNT(*) as count, AVG(confidence) as avg_confidence
         FROM insights WHERE taxon_id = $1 AND is_current = TRUE
         GROUP BY claim_type`,
        [taxon_id]
      );

      const covered = {};
      for (const row of result.rows) {
        covered[row.claim_type] = {
          count: parseInt(row.count),
          avg_confidence: parseFloat(row.avg_confidence)
        };
      }

      const missing = ALL_FIELDS.filter(f => !covered[f]);
      const lowConfidence = Object.entries(covered)
        .filter(([_, v]) => v.avg_confidence < 0.6)
        .map(([k]) => k);

      res.json({
        taxon_id,
        total_insights: result.rows.reduce((s, r) => s + parseInt(r.count), 0),
        covered_fields: Object.keys(covered).length,
        total_fields: ALL_FIELDS.length,
        missing_fields: missing,
        low_confidence_fields: lowConfidence,
        field_coverage: covered
      });
    } catch (error) {
      console.error('Error getting insight gaps:', error);
      res.status(500).json({ error: error.message });
    }
  });

  return {
    router
  };
};
