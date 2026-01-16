const express = require('express');

module.exports = (pool) => {
  const router = express.Router();

  /**
   * GET /
   * Search for species by common_name or species (scientific name)
   * Query params: search - The search term to look for
   */
  router.get('/', async (req, res) => {
    try {
      const { search } = req.query;
      
      if (!search) {
        return res.status(400).json({ error: 'Missing required parameter: search' });
      }
      
      // Debug log
      console.log(`GET /species search query: "${search}"`);
      
      const query = `
        SELECT * FROM species
        WHERE common_name ILIKE $1
        OR species_scientific_name ILIKE $1
        OR accepted_scientific_name ILIKE $1
        OR popular_common_name_ai ILIKE $1
        ORDER BY
          CASE
            WHEN species_scientific_name ILIKE $1 THEN 1
            WHEN common_name ILIKE $1 THEN 2
            WHEN accepted_scientific_name ILIKE $1 THEN 3
            ELSE 4
          END,
          species_scientific_name
        LIMIT 50
      `;
      
      const result = await pool.query(query, [`%${search}%`]);
      console.log(`GET /species returned ${result.rowCount} results`);
      
      res.json(result.rows);
    } catch (error) {
      console.error(`Error searching species for term "${req.query.search}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /suggest
   * Get autocomplete suggestions for species names
   * Query params: 
   *   - query: The partial term to look for suggestions
   *   - field: Optional field to search in (common_name or species)
   */
  router.get('/suggest', async (req, res) => {
    try {
      const { query, field } = req.query;
      
      if (!query) {
        return res.status(400).json({ error: 'Missing required parameter: query' });
      }
      
      // Debug log the request parameters
      console.log(`GET /species/suggest query: "${query}", field: "${field || 'both'}"`);
      
      let searchQuery;
      let queryParams;
      
      // Difference between % position:
      // %query% = contains anywhere
      // query% = starts with
      
      // If field is specified, search only in that field
      if (field === 'common_name') {
        searchQuery = `
          SELECT taxon_id, common_name, species_scientific_name as species, species_scientific_name, accepted_scientific_name
          FROM species
          WHERE common_name ILIKE $1
          ORDER BY common_name
          LIMIT 10
        `;
        // For common_name, we need to search anywhere in the name as they're often formatted like "Forest Oak"
        queryParams = [`%${query}%`];
      } else if (field === 'species' || field === 'scientific_name' || field === 'species_scientific_name') {
        searchQuery = `
          SELECT taxon_id, common_name, species_scientific_name, species_scientific_name as species, accepted_scientific_name
          FROM species
          WHERE species_scientific_name ILIKE $1
          ORDER BY
            CASE
              WHEN species_scientific_name ILIKE $2 THEN 0
              ELSE 1
            END,
            species_scientific_name
          LIMIT 10
        `;
        // For scientific names, we can prioritize "starts with" but should also find partial matches
        queryParams = [`%${query}%`, `${query}%`];
      } else {
        // Search in all name fields (default behavior)
        // Use DISTINCT ON to show only one result per species (prioritizing species-level records)
        searchQuery = `
          SELECT DISTINCT ON (species_scientific_name)
            taxon_id, common_name, species_scientific_name as species,
            species_scientific_name, accepted_scientific_name, subspecies
          FROM species
          WHERE common_name ILIKE $1
            OR species_scientific_name ILIKE $1
          ORDER BY species_scientific_name,
            CASE
              WHEN subspecies = 'NA' THEN 0
              ELSE 1
            END,
            CASE
              WHEN common_name ILIKE $2 THEN 0
              WHEN species_scientific_name ILIKE $2 THEN 1
              ELSE 2
            END,
            common_name
          LIMIT 10
        `;
        // Multiple parameters: first for contains anywhere, second for starts with (for ordering)
        queryParams = [`%${query}%`, `${query}%`];
      }
      
      console.log(`Executing query with params:`, queryParams);
      const result = await pool.query(searchQuery, queryParams);
      console.log(`GET /species/suggest returned ${result.rowCount} results`);
      
      res.json(result.rows);
    } catch (error) {
      console.error(`Error getting suggestions for query "${req.query.query}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id
   * Get a specific species by its taxon_id with image data
   * Route params: taxon_id - The unique identifier for the species
   */
  router.get('/:taxon_id', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      
      // Query species data with primary image
      const speciesQuery = `
        SELECT s.*, 
               i.image_url as primary_image_url,
               i.license as primary_image_license,
               i.photographer as primary_image_photographer,
               i.page_url as primary_image_page_url,
               i.source as primary_image_source
        FROM species s
        LEFT JOIN images i ON s.taxon_id = i.taxon_id AND i.is_primary = true
        WHERE s.taxon_id = $1
      `;
      
      const result = await pool.query(speciesQuery, [taxon_id]);
      
      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }
      
      // Explicitly ensure the researched flag is a boolean
      const species = result.rows[0];
      
      // Before relying on the database flag, check if any AI fields are populated
      // This provides a more reliable way to determine if research has been done
      const hasAnyAiFields = Object.keys(species).some(key => 
        key.endsWith('_ai') && 
        species[key] !== null && 
        species[key] !== undefined && 
        species[key] !== ''
      );
      
      // If AI fields are populated, force researched to true regardless of the database value
      if (hasAnyAiFields) {
        species.researched = true;
      } else {
        // Otherwise, use the database value (defaulting to false)
        species.researched = species.researched === true;
      }
      
      // Count total images for this species
      const imageCountQuery = `SELECT COUNT(*) as image_count FROM images WHERE taxon_id = $1`;
      const imageCountResult = await pool.query(imageCountQuery, [taxon_id]);
      species.image_count = parseInt(imageCountResult.rows[0].image_count);
      
      console.log(`GET /species/${taxon_id} - researched flag: ${species.researched}, hasAiFields: ${hasAnyAiFields}, images: ${species.image_count}`);
      
      res.json(species);
    } catch (error) {
      console.error(`Error fetching species with taxon_id "${req.params.taxon_id}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id/images
   * Get all images for a specific species (for carousel display)
   * Route params: taxon_id - The unique identifier for the species
   */
  router.get('/:taxon_id/images', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      // First check if species exists
      const speciesCheck = `SELECT taxon_id FROM species WHERE taxon_id = $1`;
      const speciesResult = await pool.query(speciesCheck, [taxon_id]);

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }

      // Get all images for this species, with primary image first
      const imagesQuery = `
        SELECT id, taxon_id, image_url, license, photographer, page_url, source, is_primary, created_at
        FROM images
        WHERE taxon_id = $1
        ORDER BY is_primary DESC, id ASC
      `;

      const result = await pool.query(imagesQuery, [taxon_id]);

      console.log(`GET /species/${taxon_id}/images returned ${result.rowCount} images`);

      res.json({
        taxon_id: taxon_id,
        image_count: result.rowCount,
        images: result.rows
      });
    } catch (error) {
      console.error(`Error fetching images for species "${req.params.taxon_id}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id/subspecies
   * Get all subspecies and varieties for a specific species
   * Route params: taxon_id - The unique identifier for the species
   */
  router.get('/:taxon_id/subspecies', async (req, res) => {
    try {
      const { taxon_id } = req.params;

      // First get the species to find its scientific name
      const speciesCheck = `SELECT species_scientific_name FROM species WHERE taxon_id = $1`;
      const speciesResult = await pool.query(speciesCheck, [taxon_id]);

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ error: 'Species not found' });
      }

      const speciesScientificName = speciesResult.rows[0].species_scientific_name;

      // Get all subspecies/varieties for this species (excluding the species-level record)
      const subspeciesQuery = `
        SELECT taxon_id, taxon_full, subspecies, common_name, species_scientific_name
        FROM species
        WHERE species_scientific_name = $1
          AND subspecies != 'NA'
        ORDER BY taxon_full
      `;

      const result = await pool.query(subspeciesQuery, [speciesScientificName]);

      console.log(`GET /species/${taxon_id}/subspecies returned ${result.rowCount} subspecies for ${speciesScientificName}`);

      res.json({
        taxon_id: taxon_id,
        species_scientific_name: speciesScientificName,
        subspecies_count: result.rowCount,
        subspecies: result.rows
      });
    } catch (error) {
      console.error(`Error fetching subspecies for species "${req.params.taxon_id}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * GET /:taxon_id/insights
   * Get research metadata and insights summary for a species
   * Query params: full=true to include all insight details with sources
   * Route params: taxon_id - The unique identifier for the species
   */
  router.get('/:taxon_id/insights', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const includeFull = req.query.full === 'true';

      // Get aggregate metadata from insights table
      // Returns both total insights and unique fields for atomic model
      const metadataQuery = `
        SELECT
          COUNT(*) as insight_count,
          COUNT(DISTINCT claim_type) as field_count,
          AVG(confidence) as avg_confidence,
          MAX(version) as version,
          MAX(created_at) as research_date,
          MAX(model_version) as model,
          research_session_id
        FROM insights
        WHERE taxon_id = $1 AND is_current = TRUE
        GROUP BY research_session_id
        ORDER BY MAX(created_at) DESC
        LIMIT 1
      `;
      const metadataResult = await pool.query(metadataQuery, [taxon_id]);

      if (metadataResult.rows.length === 0) {
        return res.json({
          taxon_id,
          has_insights: false,
          metadata: null,
          insights: []
        });
      }

      const meta = metadataResult.rows[0];

      // Count unique sources across all insights
      const sourcesQuery = `
        SELECT COUNT(DISTINCT s.value->>'url') as source_count
        FROM insights i,
        LATERAL jsonb_array_elements(COALESCE(i.sources, '[]'::jsonb)) as s(value)
        WHERE i.taxon_id = $1 AND i.is_current = TRUE
      `;
      const sourcesResult = await pool.query(sourcesQuery, [taxon_id]);
      const sourceCount = parseInt(sourcesResult.rows[0]?.source_count || 0);

      // If full details requested, fetch all insights with confidence breakdown
      let insights = [];
      if (includeFull) {
        const insightsQuery = `
          SELECT
            claim_type,
            claim_value,
            confidence,
            confidence_breakdown,
            corroboration,
            sources,
            model_version,
            agent_type,
            created_at
          FROM insights
          WHERE taxon_id = $1 AND is_current = TRUE
          ORDER BY claim_type
        `;
        const insightsResult = await pool.query(insightsQuery, [taxon_id]);
        insights = insightsResult.rows.map(row => ({
          claim_type: row.claim_type,
          claim_value: row.claim_value,
          confidence: parseFloat(row.confidence) || 0,
          confidence_breakdown: row.confidence_breakdown || null,
          corroboration: row.corroboration || null,
          sources: row.sources || [],
          model: row.model_version,
          agent_type: row.agent_type,
          created_at: row.created_at
        }));
      }

      res.json({
        taxon_id,
        has_insights: true,
        metadata: {
          version: parseInt(meta.version) || 1,
          research_date: meta.research_date,
          model: meta.model || 'claude-code-cli',
          insight_count: parseInt(meta.insight_count),
          field_count: parseInt(meta.field_count),
          avg_confidence: parseFloat(meta.avg_confidence) || 0,
          source_count: sourceCount,
          session_id: meta.research_session_id
        },
        insights: insights
      });
    } catch (error) {
      console.error(`Error fetching insights metadata for species "${req.params.taxon_id}":`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * POST /:taxon_id/research
   * Trigger AI research for a species using the Research Orchestrator
   * Route params: taxon_id - The unique identifier for the species
   *
   * New architecture: Checks for insights in the insights table (from Claude Code CLI research).
   * If insights exist, syncs them to species.*_ai columns.
   */
  router.post('/:taxon_id/research', async (req, res) => {
    const { taxon_id } = req.params;
    const { force } = req.body || {}; // Allow force re-research via body param

    try {
      console.log(`POST /species/${taxon_id}/research - body:`, JSON.stringify(req.body), `force=${force}, typeof force=${typeof force}`);

      // Get species info
      const speciesQuery = `
        SELECT taxon_id, species_scientific_name, common_name, research_version
        FROM species
        WHERE taxon_id = $1
      `;
      const speciesResult = await pool.query(speciesQuery, [taxon_id]);

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ success: false, error: 'Species not found' });
      }

      const species = speciesResult.rows[0];
      const scientificName = species.species_scientific_name;

      // Check if insights already exist for this species
      const insightsQuery = `
        SELECT COUNT(*) as count, AVG(confidence) as avg_confidence, MAX(version) as current_version
        FROM insights
        WHERE taxon_id = $1 AND is_current = TRUE
      `;
      const insightsResult = await pool.query(insightsQuery, [taxon_id]);
      const insightCount = parseInt(insightsResult.rows[0].count);
      const avgConfidence = insightsResult.rows[0].avg_confidence;
      const currentVersion = insightsResult.rows[0].current_version || 0;

      // If insights exist and NOT forcing re-research, sync them and return
      if (insightCount > 0 && !force) {
        console.log(`Found ${insightCount} existing insights for ${taxon_id}, syncing to _ai columns`);

        // Sync insights to species._ai columns
        await syncInsightsToSpecies(pool, taxon_id);

        return res.json({
          success: true,
          taxon_id: taxon_id,
          scientific_name: scientificName,
          message: 'Research data synced from insights',
          insights_count: insightCount,
          avg_confidence: avgConfidence ? parseFloat(avgConfidence).toFixed(3) : null,
          research_version: species.research_version,
          current_version: currentVersion,
          can_reresearch: true // Indicate re-research is available
        });
      }

      // Determine if we're doing first research or re-research
      const isReresearch = force && insightCount > 0;
      if (isReresearch) {
        console.log(`Re-research requested for ${taxon_id} (current version: ${currentVersion})`);
      } else {
        console.log(`First research requested for ${taxon_id}. Adding to research queue.`);
      }

      // Check if already in queue
      const queueCheck = await pool.query(
        `SELECT id, status FROM research_queue WHERE taxon_id = $1`,
        [taxon_id]
      );

      if (queueCheck.rows.length > 0) {
        const queueStatus = queueCheck.rows[0].status;
        if (queueStatus === 'pending') {
          return res.json({
            success: true,
            taxon_id: taxon_id,
            scientific_name: scientificName,
            message: 'Already in research queue',
            queue_status: 'pending',
            queued: true
          });
        } else if (queueStatus === 'processing') {
          return res.json({
            success: true,
            taxon_id: taxon_id,
            scientific_name: scientificName,
            message: 'Research in progress',
            queue_status: 'processing',
            queued: true
          });
        }
        // If failed or completed, allow re-queue by deleting old entry
        await pool.query(`DELETE FROM research_queue WHERE taxon_id = $1`, [taxon_id]);
      }

      // Add to queue
      await pool.query(
        `INSERT INTO research_queue (taxon_id, species_name, status, priority)
         VALUES ($1, $2, 'pending', 50)`,
        [taxon_id, scientificName]
      );

      console.log(`Added ${taxon_id} (${scientificName}) to research queue (re-research: ${isReresearch})`);

      return res.json({
        success: true,
        taxon_id: taxon_id,
        scientific_name: scientificName,
        message: isReresearch
          ? `Queued for re-research (will create version ${currentVersion + 1})`
          : 'Added to research queue',
        queue_status: 'pending',
        queued: true,
        is_reresearch: isReresearch,
        current_version: currentVersion
      });

    } catch (error) {
      console.error(`Error in research for species "${taxon_id}":`, error);
      res.status(500).json({ success: false, error: error.message || 'Internal server error' });
    }
  });

  /**
   * Sync insights from insights table to species.*_ai columns
   * This maintains backward compatibility with the frontend
   */
  async function syncInsightsToSpecies(pool, taxon_id) {
    // Map claim_type to species column name (only columns that exist in species table)
    const claimToColumn = {
      // Existing columns in species table (24 _ai columns)
      'general_description': 'general_description_ai',
      'habitat': 'habitat_ai',
      'elevation_ranges': 'elevation_ranges_ai',
      'ecological_function': 'ecological_function_ai',
      'native_adapted_habitats': 'native_adapted_habitats_ai',
      'conservation_status': 'conservation_status_ai',
      'compatible_soil_types': 'compatible_soil_types_ai',
      'growth_form': 'growth_form_ai',
      'leaf_type': 'leaf_type_ai',
      'deciduous_evergreen': 'deciduous_evergreen_ai',
      'flower_color': 'flower_color_ai',
      'fruit_type': 'fruit_type_ai',
      'bark_characteristics': 'bark_characteristics_ai',
      'maximum_height': 'maximum_height_ai',
      'maximum_diameter': 'maximum_diameter_ai',
      'lifespan': 'lifespan_ai',
      'maximum_tree_age': 'maximum_tree_age_ai',
      'stewardship_best_practices': 'stewardship_best_practices_ai',
      'planting_recipes': 'planting_recipes_ai',
      'pruning_maintenance': 'pruning_maintenance_ai',
      'disease_pest_management': 'disease_pest_management_ai',
      'fire_management': 'fire_management_ai',
      'cultural_significance': 'cultural_significance_ai',
      'agroforestry_use_cases': 'agroforestry_use_cases_ai'
      // Note: These insight types don't have corresponding _ai columns yet:
      // - popular_common_name, etymology, synonyms, identification_features (identity)
      // - climate_tolerance, tolerances, associated_species (ecological)
      // - propagation_methods (stewardship)
      // - timber_value, non_timber_products, nutritional_caloric_value (stewardship)
    };

    // Get all current insights (use DISTINCT ON to handle duplicate claim_types)
    const insightsQuery = `
      SELECT DISTINCT ON (claim_type) claim_type, claim_value
      FROM insights
      WHERE taxon_id = $1 AND is_current = TRUE
      ORDER BY claim_type, created_at DESC
    `;
    const insightsResult = await pool.query(insightsQuery, [taxon_id]);

    // Build dynamic UPDATE query
    const updates = [];
    const values = [];
    let paramIndex = 1;

    for (const insight of insightsResult.rows) {
      const column = claimToColumn[insight.claim_type];
      if (column) {
        // Extract text from claim_value (handle both {text: "..."} and simple values)
        let value;
        if (insight.claim_value && typeof insight.claim_value === 'object') {
          value = insight.claim_value.text || insight.claim_value.primary ||
                  insight.claim_value.value || JSON.stringify(insight.claim_value);
        } else {
          value = insight.claim_value;
        }

        updates.push(`${column} = $${paramIndex}`);
        values.push(value);
        paramIndex++;
      }
    }

    if (updates.length > 0) {
      values.push(taxon_id);
      const updateQuery = `
        UPDATE species
        SET ${updates.join(', ')}, researched = TRUE
        WHERE taxon_id = $${paramIndex}
      `;

      await pool.query(updateQuery, values);
      console.log(`Synced ${updates.length} fields for ${taxon_id}`);
    }
  }

  return router;
};