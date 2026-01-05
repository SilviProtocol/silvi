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
   * POST /:taxon_id/research
   * Trigger AI research for a species and update the database
   * Route params: taxon_id - The unique identifier for the species
   */
  router.post('/:taxon_id/research', async (req, res) => {
    const { taxon_id } = req.params;

    try {
      console.log(`POST /species/${taxon_id}/research - Starting AI research`);

      // Get species info
      const speciesQuery = `
        SELECT taxon_id, species_scientific_name, common_name
        FROM species
        WHERE taxon_id = $1
      `;
      const speciesResult = await pool.query(speciesQuery, [taxon_id]);

      if (speciesResult.rows.length === 0) {
        return res.status(404).json({ success: false, error: 'Species not found' });
      }

      const species = speciesResult.rows[0];
      const scientificName = species.species_scientific_name;
      const commonNames = species.common_name || '';

      // Perform AI research
      const grokResearch = require('../services/grokResearch');
      const result = await grokResearch.performResearch(scientificName, commonNames);

      if (!result.success) {
        console.error(`Research failed for ${taxon_id}:`, result.error);
        return res.status(500).json({ success: false, error: result.error });
      }

      // Update species table with research data
      const updateQuery = `
        UPDATE species SET
          popular_common_name_ai = $1,
          habitat_ai = $2,
          elevation_ranges_ai = $3,
          ecological_function_ai = $4,
          native_adapted_habitats_ai = $5,
          agroforestry_use_cases_ai = $6,
          conservation_status_ai = $7,
          general_description_ai = $8,
          compatible_soil_types_ai = $9,
          growth_form_ai = $10,
          leaf_type_ai = $11,
          deciduous_evergreen_ai = $12,
          flower_color_ai = $13,
          fruit_type_ai = $14,
          bark_characteristics_ai = $15,
          maximum_height_ai = $16,
          maximum_diameter_ai = $17,
          lifespan_ai = $18,
          maximum_tree_age_ai = $19,
          stewardship_best_practices_ai = $20,
          planting_recipes_ai = $21,
          pruning_maintenance_ai = $22,
          disease_pest_management_ai = $23,
          fire_management_ai = $24,
          cultural_significance_ai = $25
        WHERE taxon_id = $26
      `;

      const d = result.data;
      await pool.query(updateQuery, [
        d.popular_common_name_ai,
        d.habitat_ai,
        d.elevation_ranges_ai,
        d.ecological_function_ai,
        d.native_adapted_habitats_ai,
        d.agroforestry_use_cases_ai,
        d.conservation_status_ai,
        d.general_description_ai,
        d.compatible_soil_types_ai,
        d.growth_form_ai,
        d.leaf_type_ai,
        d.deciduous_evergreen_ai,
        d.flower_color_ai,
        d.fruit_type_ai,
        d.bark_characteristics_ai,
        d.maximum_height_ai,
        d.maximum_diameter_ai,
        d.lifespan_ai,
        d.maximum_tree_age_ai,
        d.stewardship_best_practices_ai,
        d.planting_recipes_ai,
        d.pruning_maintenance_ai,
        d.disease_pest_management_ai,
        d.fire_management_ai,
        d.cultural_significance_ai,
        taxon_id
      ]);

      console.log(`POST /species/${taxon_id}/research - Database updated successfully`);

      res.json({
        success: true,
        taxon_id: taxon_id,
        scientific_name: scientificName,
        fields_filled: result.fields_filled,
        fields_total: result.fields_total,
        duration_ms: result.duration_ms,
        data: result.data
      });

    } catch (error) {
      console.error(`Error in research for species "${taxon_id}":`, error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  });

  return router;
};