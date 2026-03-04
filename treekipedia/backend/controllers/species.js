const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { authenticateUser } = require('../middleware/userAuth');

module.exports = (pool) => {
  const router = express.Router();
  const creditService = require('../services/creditService')(pool);

  // ============================================================================
  // INSIGHT MANAGEMENT FUNCTIONS
  // ============================================================================

  /**
   * Mapping from research field names to insight claim_types
   * The _ai suffix is stripped for the claim_type
   */
  const FIELD_TO_CLAIM_TYPE = {
    popular_common_name_ai: 'popular_common_name',
    habitat_ai: 'habitat',
    elevation_ranges_ai: 'elevation_ranges',
    ecological_function_ai: 'ecological_function',
    native_adapted_habitats_ai: 'native_adapted_habitats',
    agroforestry_use_cases_ai: 'agroforestry_use_cases',
    conservation_status_ai: 'conservation_status',
    general_description_ai: 'general_description',
    compatible_soil_types_ai: 'compatible_soil_types',
    growth_form_ai: 'growth_form',
    leaf_type_ai: 'leaf_type',
    deciduous_evergreen_ai: 'deciduous_evergreen',
    flower_color_ai: 'flower_color',
    fruit_type_ai: 'fruit_type',
    bark_characteristics_ai: 'bark_characteristics',
    maximum_height_ai: 'maximum_height',
    maximum_diameter_ai: 'maximum_diameter',
    lifespan_ai: 'lifespan',
    maximum_tree_age_ai: 'maximum_tree_age',
    stewardship_best_practices_ai: 'stewardship_best_practices',
    planting_recipes_ai: 'planting_recipes',
    pruning_maintenance_ai: 'pruning_maintenance',
    disease_pest_management_ai: 'disease_pest_management',
    fire_management_ai: 'fire_management',
    cultural_significance_ai: 'cultural_significance',
    // v2 additions (10 new fields)
    etymology_ai: 'etymology',
    synonyms_ai: 'synonyms',
    identification_features_ai: 'identification_features',
    climate_tolerance_ai: 'climate_tolerance',
    tolerances_ai: 'tolerances',
    associated_species_ai: 'associated_species',
    propagation_methods_ai: 'propagation_methods',
    timber_value_ai: 'timber_value',
    non_timber_products_ai: 'non_timber_products',
    nutritional_caloric_value_ai: 'nutritional_caloric_value'
  };

  // Numeric fields that should store value+unit instead of text
  const NUMERIC_CLAIM_TYPES = ['maximum_height', 'maximum_diameter', 'maximum_tree_age'];

  /**
   * Create insights from research data
   * @param {string} taxonId - The species taxon_id
   * @param {object} researchData - The data object from grokResearch
   * @param {number} confidence - Overall confidence score
   * @param {array} sources - Array of source objects
   * @param {string} model - The AI model used
   * @param {number} version - Research version number
   * @returns {Promise<{created: number, skipped: number}>}
   */
  async function createInsightsFromResearch(taxonId, researchData, confidence, sources, model, version) {
    let created = 0;
    let skipped = 0;
    const researchSessionId = uuidv4();

    for (const [fieldName, claimType] of Object.entries(FIELD_TO_CLAIM_TYPE)) {
      const value = researchData[fieldName];

      // Skip null/undefined/empty values
      if (value === null || value === undefined || value === '' || value === 'Data not available') {
        skipped++;
        continue;
      }

      // Build claim_value based on field type
      let claimValue;
      if (NUMERIC_CLAIM_TYPES.includes(claimType)) {
        // Numeric fields: store as {value, unit}
        const unit = claimType === 'maximum_tree_age' ? 'years' : 'meters';
        claimValue = { value: value, unit: unit };
      } else {
        // Text fields: store as {text}
        claimValue = { text: String(value) };
      }

      try {
        // Insert insight (content_hash trigger will handle deduplication)
        await pool.query(`
          INSERT INTO insights (
            taxon_id, claim_type, claim_value, confidence, sources,
            is_current, research_session_id
          ) VALUES ($1, $2, $3, $4, $5, TRUE, $6)
          ON CONFLICT (content_hash) WHERE is_current = TRUE
          DO UPDATE SET
            confidence = GREATEST(insights.confidence, EXCLUDED.confidence),
            sources = EXCLUDED.sources,
            updated_at = NOW()
        `, [
          taxonId,
          claimType,
          JSON.stringify(claimValue),
          confidence,
          JSON.stringify(sources),
          researchSessionId
        ]);
        created++;
      } catch (err) {
        console.warn(`Failed to create insight for ${taxonId}/${claimType}:`, err.message);
        skipped++;
      }
    }

    console.log(`[Insights] Created ${created} insights, skipped ${skipped} for ${taxonId}`);
    return { created, skipped, sessionId: researchSessionId };
  }

  /**
   * Create atomic insights from v2 research data (multi-value arrays)
   * @param {string} taxonId
   * @param {object} fields - Keyed by claim_type (no _ai suffix), values are strings/numbers/arrays
   * @param {array} globalSources - Sources from the Grok calls
   * @param {string} model - AI model used
   * @param {number} version - Research version number
   * @returns {Promise<{created: number, skipped: number, sessionId: string}>}
   */
  async function createAtomicInsights(taxonId, fields, globalSources, model, version) {
    let created = 0;
    let skipped = 0;
    const researchSessionId = uuidv4();

    // Mark old insights as not current before inserting new ones
    await pool.query(
      `UPDATE insights SET is_current = FALSE WHERE taxon_id = $1 AND is_current = TRUE`,
      [taxonId]
    );

    for (const [fieldName, value] of Object.entries(fields)) {
      // Skip null/undefined/empty
      if (value === null || value === undefined || value === '' || value === 'Data not available') {
        skipped++;
        continue;
      }

      // Determine entries to insert
      const entries = [];

      if (Array.isArray(value)) {
        // Multi-value field: one insight per array element
        for (const item of value) {
          if (!item || (typeof item === 'object' && !item.text)) {
            skipped++;
            continue;
          }
          const text = typeof item === 'string' ? item : item.text;
          if (!text || text === 'Data not available') {
            skipped++;
            continue;
          }
          // Per-insight confidence: 0.80 if source_hint present, 0.70 otherwise
          const confidence = (item.source_hint) ? 0.80 : 0.70;
          const claimValue = {
            text,
            context: item.context || null,
            region: item.region || null,
            source_hint: item.source_hint || null
          };
          entries.push({ claimValue, confidence });
        }
        if (entries.length === 0) {
          skipped++;
          continue;
        }
      } else if (NUMERIC_CLAIM_TYPES.includes(fieldName)) {
        // Numeric field
        const numVal = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(numVal) || numVal === null) {
          skipped++;
          continue;
        }
        const unit = fieldName === 'maximum_tree_age' ? 'years' : 'meters';
        entries.push({ claimValue: { value: numVal, unit }, confidence: 0.75 });
      } else {
        // Single string field
        const text = String(value);
        if (text === 'Data not available') {
          skipped++;
          continue;
        }
        entries.push({ claimValue: { text }, confidence: 0.75 });
      }

      // Insert each entry
      for (const entry of entries) {
        try {
          await pool.query(`
            INSERT INTO insights (
              taxon_id, claim_type, claim_value, confidence, sources,
              is_current, research_session_id
            ) VALUES ($1, $2, $3, $4, $5, TRUE, $6)
            ON CONFLICT (content_hash) WHERE is_current = TRUE
            DO UPDATE SET
              confidence = GREATEST(insights.confidence, EXCLUDED.confidence),
              sources = EXCLUDED.sources,
              is_current = TRUE,
              updated_at = NOW()
          `, [
            taxonId,
            fieldName,
            JSON.stringify(entry.claimValue),
            entry.confidence,
            JSON.stringify(globalSources),
            researchSessionId
          ]);
          created++;
        } catch (err) {
          console.warn(`Failed to create atomic insight for ${taxonId}/${fieldName}:`, err.message);
          skipped++;
        }
      }
    }

    console.log(`[AtomicInsights] Created ${created} insights, skipped ${skipped} for ${taxonId}`);
    return { created, skipped, sessionId: researchSessionId };
  }

  /**
   * Sync insights to species._ai columns
   * Aggregates all current insights for a species and updates the _ai columns
   * @param {string} taxonId - The species taxon_id
   * @returns {Promise<{synced: number}>}
   */
  async function syncInsightsToSpecies(taxonId) {
    // Get all current insights for this species
    const insightsResult = await pool.query(`
      SELECT claim_type, claim_value, confidence
      FROM insights
      WHERE taxon_id = $1 AND is_current = TRUE
      ORDER BY claim_type, confidence DESC
    `, [taxonId]);

    if (insightsResult.rows.length === 0) {
      return { synced: 0 };
    }

    // Group insights by claim_type
    const insightsByType = {};
    for (const row of insightsResult.rows) {
      if (!insightsByType[row.claim_type]) {
        insightsByType[row.claim_type] = [];
      }
      insightsByType[row.claim_type].push(row);
    }

    // Build update values - aggregate insights into prose for each _ai column
    const updates = {};
    for (const [claimType, insights] of Object.entries(insightsByType)) {
      const fieldName = claimType + '_ai';

      if (NUMERIC_CLAIM_TYPES.includes(claimType)) {
        // For numeric fields, use the highest-confidence value
        const topInsight = insights[0];
        const val = topInsight.claim_value;
        updates[fieldName] = typeof val === 'object' ? val.value : val;
      } else {
        // For text fields, join multiple insights with paragraph breaks
        const texts = insights.map(i => {
          const val = i.claim_value;
          return typeof val === 'object' ? (val.text || JSON.stringify(val)) : String(val);
        });
        // Remove duplicates and join
        const uniqueTexts = [...new Set(texts)];
        updates[fieldName] = uniqueTexts.join('\n\n');
      }
    }

    // Build dynamic UPDATE query
    const setClauses = [];
    const values = [];
    let paramIndex = 1;

    for (const [field, value] of Object.entries(updates)) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(value);
      paramIndex++;
    }

    if (setClauses.length === 0) {
      return { synced: 0 };
    }

    // Add taxon_id as last parameter
    values.push(taxonId);

    const updateQuery = `
      UPDATE species SET
        ${setClauses.join(',\n        ')},
        updated_at = NOW()
      WHERE taxon_id = $${paramIndex}
    `;

    await pool.query(updateQuery, values);

    console.log(`[Sync] Updated ${setClauses.length} _ai columns for ${taxonId}`);
    return { synced: setClauses.length };
  }

  /**
   * GET /:taxon_id/insights
   * Get all current insights for a species
   */
  router.get('/:taxon_id/insights', async (req, res) => {
    try {
      const { taxon_id } = req.params;
      const { full } = req.query;

      const query = full === 'true'
        ? `SELECT * FROM insights WHERE taxon_id = $1 AND is_current = TRUE ORDER BY claim_type, confidence DESC`
        : `SELECT id, claim_type, claim_value, confidence, created_at FROM insights WHERE taxon_id = $1 AND is_current = TRUE ORDER BY claim_type, confidence DESC`;

      const result = await pool.query(query, [taxon_id]);

      // Group by claim_type for easier frontend consumption
      const grouped = {};
      for (const row of result.rows) {
        if (!grouped[row.claim_type]) {
          grouped[row.claim_type] = [];
        }
        grouped[row.claim_type].push(row);
      }

      // Get research metadata from species table
      const metaResult = await pool.query(`
        SELECT research_version, research_date, research_agent,
               research_confidence, research_sources
        FROM species WHERE taxon_id = $1
      `, [taxon_id]);

      const speciesMeta = metaResult.rows[0] || {};
      const hasInsights = result.rows.length > 0;

      // Compute avg confidence from actual insights
      const avgConfidence = hasInsights
        ? result.rows.reduce((sum, r) => sum + (r.confidence || 0), 0) / result.rows.length
        : 0;

      // Count unique sources across all insights
      let sourceCount = 0;
      if (hasInsights && full === 'true') {
        const sourceSet = new Set();
        for (const row of result.rows) {
          const sources = typeof row.sources === 'string' ? JSON.parse(row.sources) : (row.sources || []);
          if (Array.isArray(sources)) {
            sources.forEach(s => sourceSet.add(typeof s === 'object' ? (s.url || s.title || JSON.stringify(s)) : s));
          }
        }
        sourceCount = sourceSet.size;
      }

      res.json({
        taxon_id,
        has_insights: hasInsights,
        insight_count: result.rows.length,
        claim_types: Object.keys(grouped).length,
        metadata: hasInsights ? {
          version: speciesMeta.research_version || 1,
          research_date: speciesMeta.research_date || null,
          model: speciesMeta.research_agent || 'unknown',
          insight_count: result.rows.length,
          field_count: Object.keys(grouped).length,
          avg_confidence: avgConfidence,
          source_count: sourceCount,
        } : null,
        insights: result.rows,
        insights_grouped: grouped
      });
    } catch (error) {
      console.error(`Error fetching insights for ${req.params.taxon_id}:`, error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

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
        OR species ILIKE $1
        OR species_scientific_name ILIKE $1
        OR accepted_scientific_name ILIKE $1
        ORDER BY common_name
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

      // Get derived habitat biomes from occurrence data
      const biomesQuery = `
        SELECT
            t.biome_name,
            SUM((t.species_data->>$1)::int) as occurrences,
            COUNT(DISTINCT t.geohash_l7) as tile_count
        FROM geohash_species_tiles t
        WHERE t.species_data ? $1
          AND t.biome_name IS NOT NULL
        GROUP BY t.biome_name
        HAVING SUM((t.species_data->>$1)::int) >= 10
        ORDER BY occurrences DESC
        LIMIT 5
      `;
      const biomesResult = await pool.query(biomesQuery, [taxon_id]);
      species.derived_biomes = biomesResult.rows.map(r => ({
        biome: r.biome_name,
        occurrences: parseInt(r.occurrences),
        tiles: parseInt(r.tile_count)
      }));

      console.log(`GET /species/${taxon_id} - researched flag: ${species.researched}, hasAiFields: ${hasAnyAiFields}, images: ${species.image_count}, biomes: ${species.derived_biomes.length}`);

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
   * POST /:taxon_id/research
   * Trigger AI research for a species using insights architecture
   * Flow: Grok API → Create Insights → Sync to _ai columns
   * Includes research versioning, confidence scoring, and source tracking
   * Route params: taxon_id - The unique identifier for the species
   */
  router.post('/:taxon_id/research', authenticateUser, async (req, res) => {
    const { taxon_id } = req.params;

    try {
      // Validate species exists before charging credits
      const speciesQuery = `
        SELECT taxon_id, species_scientific_name, common_name,
               COALESCE(research_version, 0) as research_version
        FROM species
        WHERE taxon_id = $1
      `;
      const speciesResult = await pool.query(speciesQuery, [taxon_id]);

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ success: false, error: 'Species not found' });
      }

      // Deduct 25 credits for species research
      const deduction = await creditService.deductCredits(
        req.user.id,
        25,
        'species_research',
        taxon_id,
        { taxon_id },
        `species_research_${req.user.id}_${taxon_id}_${Date.now()}`
      );

      if (!deduction.success) {
        return res.status(402).json({
          error: 'Insufficient credits',
          required: deduction.required,
          balance: deduction.balance,
          cost_credits: 25
        });
      }

      console.log(`POST /species/${taxon_id}/research - Starting AI research (insights flow)`);

      const species = speciesResult.rows[0];
      const scientificName = species.species_scientific_name;
      const commonNames = species.common_name || '';
      const currentVersion = species.research_version;
      const newVersion = currentVersion + 1;

      // Step 1: Perform atomic AI research via Grok (two parallel calls)
      const grokResearch = require('../services/grokResearch');
      const result = await grokResearch.performAtomicResearch(scientificName, commonNames);

      if (!result.success) {
        console.error(`Research failed for ${taxon_id}:`, result.error);
        return res.status(500).json({ success: false, error: result.error });
      }

      // Step 2: Create atomic insights from research results
      const insightResult = await createAtomicInsights(
        taxon_id,
        result.fields,
        result.sources || [],
        result.model || 'grok-4-1-fast-reasoning',
        newVersion
      );

      // Step 3: Sync insights to species._ai columns
      const syncResult = await syncInsightsToSpecies(taxon_id);

      // Step 4: Update versioning metadata on species table
      // Calculate avg confidence from created insights
      const avgConfResult = await pool.query(
        `SELECT AVG(confidence) as avg_conf FROM insights WHERE taxon_id = $1 AND is_current = TRUE`,
        [taxon_id]
      );
      const avgConfidence = avgConfResult.rows[0]?.avg_conf
        ? Math.round(parseFloat(avgConfResult.rows[0].avg_conf) * 100) / 100
        : null;

      await pool.query(`
        UPDATE species SET
          research_version = $1,
          research_date = NOW(),
          research_agent = $2,
          research_confidence = $3,
          research_sources = $4,
          researched = TRUE,
          updated_at = NOW()
        WHERE taxon_id = $5
      `, [
        newVersion,
        result.model || 'grok-4-1-fast-reasoning',
        avgConfidence,
        JSON.stringify(result.sources || []),
        taxon_id
      ]);

      // Step 5: Track token usage if available
      if (result.usage) {
        try {
          await pool.query(`
            INSERT INTO research_token_usage
              (taxon_id, agent_name, model, input_tokens, output_tokens, cost_usd)
            VALUES ($1, $2, $3, $4, $5, $6)
          `, [
            taxon_id,
            'grok-research-atomic',
            result.model || 'grok-4-1-fast-reasoning',
            result.usage.input_tokens || 0,
            result.usage.output_tokens || 0,
            0
          ]);
        } catch (tokenError) {
          console.warn(`Failed to track token usage for ${taxon_id}:`, tokenError.message);
        }
      }

      console.log(`POST /species/${taxon_id}/research - Complete (v${newVersion}, ${insightResult.created} insights, ${result.calls_succeeded}/2 calls, confidence: ${avgConfidence})`);

      res.json({
        success: true,
        taxon_id: taxon_id,
        scientific_name: scientificName,
        research_version: newVersion,
        insights_created: insightResult.created,
        insights_skipped: insightResult.skipped,
        fields_synced: syncResult.synced,
        confidence: avgConfidence,
        calls_succeeded: result.calls_succeeded,
        partial: result.partial,
        fields_filled: result.fields_filled,
        fields_total: result.fields_total,
        sources: result.sources,
        model: result.model,
        duration_ms: result.duration_ms,
        session_id: insightResult.sessionId,
        credits_charged: 25,
        balance_after: deduction.balance_after
      });

    } catch (error) {
      console.error(`Error in research for species "${taxon_id}":`, error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  });

  return router;
};