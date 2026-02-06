/**
 * Ecoregion Guide Controller
 * Endpoints for retrieving and synthesizing ecoregion reforestation guides.
 */

const express = require('express');
const { synthesizeGuide, getLocalLanguages } = require('../services/guideSynthesis');

module.exports = (pool) => {
  const router = express.Router();

  /**
   * GET /api/guides/ecoregion/:eco_id
   * Returns ecoregion metadata + synthesized content (if exists) + LEAF-ranked species
   */
  router.get('/ecoregion/:eco_id', async (req, res) => {
    try {
      const { eco_id } = req.params;

      // Get ecoregion metadata
      const ecoResult = await pool.query(`
        SELECT eco_id, eco_name, biome_name, realm,
               ST_Area(geom::geography) / 1000000 as area_km2
        FROM ecoregions WHERE eco_id = $1
      `, [eco_id]);

      if (ecoResult.rows.length === 0) {
        return res.status(404).json({ error: 'Ecoregion not found' });
      }

      const ecoregion = ecoResult.rows[0];

      // Get synthesized content if exists
      const guideResult = await pool.query(`
        SELECT overview_intro, planting_strategy, climate_context, conservation_notes,
               generated_at, model_used, synthesis_version, species_count, source_data
        FROM ecoregion_guides WHERE eco_id = $1
      `, [eco_id]);

      const synthesized_content = guideResult.rows.length > 0 ? guideResult.rows[0] : null;

      // Get LEAF-ranked species for this ecoregion
      // Use occurrence data + native status for scoring
      const { getWcvpRegionsForCountry } = require('../utils/wcvpRegions');

      // Get countries for WCVP lookup
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
      `, [eco_id]);

      const countries = countriesResult.rows.map(r => r.country_name).filter(Boolean);

      // Build WCVP patterns
      const wcvpPatterns = [];
      for (const country of countries) {
        const regions = getWcvpRegionsForCountry(country);
        wcvpPatterns.push(...regions.map(r => r.toLowerCase()));
      }

      // Get occurrence data
      const occurrenceResult = await pool.query(`
        WITH tile_species AS (
          SELECT
            (jsonb_each_text(species_data)).key AS taxon_id,
            (jsonb_each_text(species_data)).value::int AS occurrences
          FROM geohash_species_tiles
          WHERE eco_id = $1
        )
        SELECT
          taxon_id,
          SUM(occurrences) AS occurrence_count,
          COUNT(*) AS tile_count
        FROM tile_species
        GROUP BY taxon_id
      `, [eco_id]);

      // Build species map with affinities
      const speciesMap = new Map();
      for (const row of occurrenceResult.rows) {
        speciesMap.set(row.taxon_id, {
          taxon_id: row.taxon_id,
          affinity: parseInt(row.occurrence_count) * parseInt(row.tile_count),
          occurrence_count: parseInt(row.occurrence_count),
          tile_count: parseInt(row.tile_count),
          is_native: false,
          is_introduced: false
        });
      }

      // Check native/introduced status
      if (wcvpPatterns.length > 0) {
        const nativePatterns = wcvpPatterns.map(p => `%${p}%`);

        const nativeResult = await pool.query(`
          SELECT taxon_id FROM species
          WHERE wcvp_native IS NOT NULL AND wcvp_native ILIKE ANY($1)
        `, [nativePatterns]);
        const nativeSet = new Set(nativeResult.rows.map(r => r.taxon_id));

        const introducedResult = await pool.query(`
          SELECT taxon_id FROM species
          WHERE wcvp_introduced IS NOT NULL AND wcvp_introduced ILIKE ANY($1)
        `, [nativePatterns]);
        const introducedSet = new Set(introducedResult.rows.map(r => r.taxon_id));

        // Add WCVP-only native species
        for (const taxon_id of nativeSet) {
          if (!speciesMap.has(taxon_id)) {
            speciesMap.set(taxon_id, {
              taxon_id,
              affinity: 100,
              occurrence_count: 0,
              tile_count: 0,
              is_native: true,
              is_introduced: false
            });
          } else {
            speciesMap.get(taxon_id).is_native = true;
          }
        }

        for (const taxon_id of introducedSet) {
          if (speciesMap.has(taxon_id)) {
            speciesMap.get(taxon_id).is_introduced = true;
          }
        }
      }

      // Filter out introduced, apply native boost, calculate LEAF scores
      const filtered = [];
      for (const [, sp] of speciesMap) {
        if (sp.is_introduced) continue;
        const nativeMultiplier = sp.is_native ? 2.0 : 1.0;
        sp.weighted_affinity = sp.affinity * nativeMultiplier;
        filtered.push(sp);
      }

      filtered.sort((a, b) => a.weighted_affinity - b.weighted_affinity);
      const total = filtered.length;
      for (let i = 0; i < total; i++) {
        filtered[i].leaf_score = total > 1 ? Math.round((i / (total - 1)) * 1000) / 10 : 100;
        filtered[i].tier = filtered[i].leaf_score >= 90 ? 'BEST' :
                           filtered[i].leaf_score >= 70 ? 'GOOD' :
                           filtered[i].leaf_score >= 50 ? 'ACCEPTABLE' : 'LOW';
      }

      filtered.sort((a, b) => b.leaf_score - a.leaf_score);

      // Get species details for top 10 (enriched) and all qualifying
      const allTaxonIds = filtered.slice(0, 2500).map(s => s.taxon_id);
      const top10Ids = filtered.slice(0, 10).map(s => s.taxon_id);

      let detailsMap = new Map();
      if (allTaxonIds.length > 0) {
        const detailsResult = await pool.query(`
          SELECT taxon_id, species_scientific_name, common_name, family, genus
          FROM species WHERE taxon_id = ANY($1)
        `, [allTaxonIds]);
        detailsMap = new Map(detailsResult.rows.map(r => [r.taxon_id, r]));
      }

      // Enriched top 10 with _ai fields
      let enrichedMap = new Map();
      if (top10Ids.length > 0) {
        const enrichedResult = await pool.query(`
          SELECT taxon_id, species_scientific_name, common_name, family, genus,
                 popular_common_name_ai, general_description_ai, habitat_ai,
                 ecological_function_ai, maximum_height_ai, conservation_status_ai
          FROM species WHERE taxon_id = ANY($1)
        `, [top10Ids]);
        enrichedMap = new Map(enrichedResult.rows.map(r => [r.taxon_id, r]));
      }

      // Build species response grouped by tier
      const speciesByTier = { BEST: [], GOOD: [], ACCEPTABLE: [], LOW: [] };
      const top10Species = [];

      for (const sp of filtered.slice(0, 2500)) {
        const details = detailsMap.get(sp.taxon_id) || {};
        const enriched = enrichedMap.get(sp.taxon_id);

        const entry = {
          taxon_id: sp.taxon_id,
          scientific_name: details.species_scientific_name || null,
          common_name: details.common_name || null,
          family: details.family || null,
          genus: details.genus || null,
          leaf_score: sp.leaf_score,
          tier: sp.tier,
          is_native: sp.is_native,
          occurrence_count: sp.occurrence_count,
          tile_count: sp.tile_count
        };

        if (enriched && top10Species.length < 10) {
          entry.popular_common_name_ai = enriched.popular_common_name_ai || null;
          entry.general_description_ai = enriched.general_description_ai || null;
          entry.habitat_ai = enriched.habitat_ai || null;
          entry.ecological_function_ai = enriched.ecological_function_ai || null;
          entry.maximum_height_ai = enriched.maximum_height_ai || null;
          entry.conservation_status_ai = enriched.conservation_status_ai || null;
          top10Species.push(entry);
        }

        if (speciesByTier[sp.tier]) {
          speciesByTier[sp.tier].push(entry);
        }
      }

      res.json({
        ecoregion: {
          eco_id: parseInt(ecoregion.eco_id),
          eco_name: ecoregion.eco_name,
          biome_name: ecoregion.biome_name,
          realm: ecoregion.realm,
          area_km2: Math.round(parseFloat(ecoregion.area_km2))
        },
        synthesized_content,
        statistics: {
          total_species: total,
          by_tier: {
            BEST: speciesByTier.BEST.length,
            GOOD: speciesByTier.GOOD.length,
            ACCEPTABLE: speciesByTier.ACCEPTABLE.length,
            LOW: speciesByTier.LOW.length
          }
        },
        top_species: top10Species,
        species_by_tier: speciesByTier,
        countries
      });

    } catch (error) {
      console.error('Error in getEcoregionGuide:', error);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  /**
   * POST /api/guides/ecoregion/:eco_id/synthesize
   * Triggers LLM synthesis for the ecoregion guide
   */
  router.post('/ecoregion/:eco_id/synthesize', async (req, res) => {
    try {
      const { eco_id } = req.params;
      const { force } = req.query;

      // Check for existing synthesis
      if (force !== 'true') {
        const existing = await pool.query(
          'SELECT generated_at FROM ecoregion_guides WHERE eco_id = $1', [eco_id]
        );
        if (existing.rows.length > 0) {
          return res.json({
            success: false,
            message: 'Guide already synthesized. Use ?force=true to regenerate.',
            generated_at: existing.rows[0].generated_at
          });
        }
      }

      // Get ecoregion metadata
      const ecoResult = await pool.query(`
        SELECT eco_id, eco_name, biome_name, realm,
               ST_Area(geom::geography) / 1000000 as area_km2
        FROM ecoregions WHERE eco_id = $1
      `, [eco_id]);

      if (ecoResult.rows.length === 0) {
        return res.status(404).json({ error: 'Ecoregion not found' });
      }

      const ecoregion = ecoResult.rows[0];

      // Get countries for region-specific naming
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
      `, [eco_id]);

      const countries = countriesResult.rows.map(r => r.country_name).filter(Boolean);

      // Get top 20 species with _ai fields for the synthesis prompt
      // Simplified: use occurrence-based ranking
      const speciesResult = await pool.query(`
        WITH tile_species AS (
          SELECT
            (jsonb_each_text(species_data)).key AS taxon_id,
            (jsonb_each_text(species_data)).value::int AS occurrences
          FROM geohash_species_tiles
          WHERE eco_id = $1
        ),
        ranked AS (
          SELECT taxon_id, SUM(occurrences) as total_occ, COUNT(*) as tile_count
          FROM tile_species GROUP BY taxon_id
          ORDER BY SUM(occurrences) * COUNT(*) DESC
          LIMIT 20
        )
        SELECT r.taxon_id, r.total_occ, r.tile_count,
               s.species_scientific_name as scientific_name, s.common_name,
               s.popular_common_name_ai, s.general_description_ai, s.habitat_ai,
               s.ecological_function_ai, s.maximum_height_ai, s.conservation_status_ai
        FROM ranked r
        LEFT JOIN species s ON s.taxon_id = r.taxon_id
      `, [eco_id]);

      const topSpecies = speciesResult.rows.map(r => ({
        ...r,
        tier: 'BEST',
        is_native: true
      }));

      // Call synthesis service with countries for region-specific naming
      const content = await synthesizeGuide(ecoregion, topSpecies, countries);

      // Upsert into ecoregion_guides
      await pool.query(`
        INSERT INTO ecoregion_guides (eco_id, overview_intro, planting_strategy, climate_context, conservation_notes,
                                      generated_at, model_used, synthesis_version, species_count, source_data)
        VALUES ($1, $2, $3, $4, $5, NOW(), $6, 1, $7, $8)
        ON CONFLICT (eco_id) DO UPDATE SET
          overview_intro = EXCLUDED.overview_intro,
          planting_strategy = EXCLUDED.planting_strategy,
          climate_context = EXCLUDED.climate_context,
          conservation_notes = EXCLUDED.conservation_notes,
          generated_at = NOW(),
          model_used = EXCLUDED.model_used,
          synthesis_version = ecoregion_guides.synthesis_version + 1,
          species_count = EXCLUDED.species_count,
          source_data = EXCLUDED.source_data
      `, [
        eco_id,
        content.overview_intro,
        content.planting_strategy,
        content.climate_context,
        content.conservation_notes,
        'grok-4-1-fast-reasoning',
        topSpecies.length,
        JSON.stringify({
          species_used: topSpecies.map(s => s.taxon_id),
          countries: countries,
          local_languages: getLocalLanguages(countries)
        })
      ]);

      res.json({
        success: true,
        eco_id: parseInt(eco_id),
        sections_generated: Object.keys(content).filter(k => content[k]).length,
        species_used: topSpecies.length,
        model: 'grok-4-1-fast-reasoning'
      });

    } catch (error) {
      console.error('Error in synthesizeGuide:', error);
      res.status(500).json({ error: 'Internal server error', details: error.message });
    }
  });

  return router;
};
