/**
 * Geospatial controller for querying species data using PostGIS and geohash tiles
 * Provides spatial queries on Marina's compressed occurrence data
 */

module.exports = (pool) => {

// Find species near a specific location
async function findSpeciesNearby(req, res) {
  try {
    const { lat, lng, radius = 5 } = req.query;
    
    if (!lat || !lng) {
      return res.status(400).json({ 
        error: 'Missing required parameters: lat and lng' 
      });
    }
    
    const radiusMeters = radius * 1000; // Convert km to meters
    
    // Query geohash tiles within radius and extract unique species
    const query = `
      WITH nearby_tiles AS (
        SELECT species_data
        FROM geohash_species_tiles
        WHERE ST_DWithin(
          center_point,
          ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
          $3
        )
      )
      SELECT DISTINCT jsonb_object_keys(species_data) as taxon_id
      FROM nearby_tiles
      ORDER BY taxon_id;
    `;
    
    const result = await pool.query(query, [
      parseFloat(lng), 
      parseFloat(lat), 
      radiusMeters
    ]);
    
    // Get species details for found taxon IDs
    const taxonIds = result.rows.map(row => row.taxon_id);
    
    if (taxonIds.length > 0) {
      const speciesQuery = `
        SELECT taxon_id, scientific_name, common_name
        FROM species
        WHERE taxon_id = ANY($1)
        ORDER BY scientific_name;
      `;
      
      const speciesResult = await pool.query(speciesQuery, [taxonIds]);
      
      res.json({
        location: { lat: parseFloat(lat), lng: parseFloat(lng) },
        radius_km: radius,
        species_count: speciesResult.rows.length,
        species: speciesResult.rows
      });
    } else {
      res.json({
        location: { lat: parseFloat(lat), lng: parseFloat(lng) },
        radius_km: radius,
        species_count: 0,
        species: []
      });
    }
    
  } catch (error) {
    console.error('Error in findSpeciesNearby:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get species distribution as geohash tiles
async function getSpeciesDistribution(req, res) {
  try {
    const { taxon_id } = req.params;
    
    const query = `
      SELECT 
        geohash_l7,
        (species_data->>$1)::int as occurrence_count,
        ST_AsGeoJSON(geometry)::json as geometry,
        datetime,
        data_source
      FROM geohash_species_tiles
      WHERE species_data ? $1
      ORDER BY occurrence_count DESC;
    `;
    
    const result = await pool.query(query, [taxon_id]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ 
        error: 'No distribution data found for this species' 
      });
    }
    
    // Calculate distribution statistics
    const totalOccurrences = result.rows.reduce(
      (sum, row) => sum + row.occurrence_count, 
      0
    );
    
    res.json({
      taxon_id,
      tile_count: result.rows.length,
      total_occurrences: totalOccurrences,
      distribution: result.rows.map(row => ({
        type: 'Feature',
        properties: {
          geohash: row.geohash_l7,
          occurrences: row.occurrence_count,
          datetime: row.datetime,
          data_source: row.data_source
        },
        geometry: row.geometry
      }))
    });
    
  } catch (error) {
    console.error('Error in getSpeciesDistribution:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get occurrence heatmap for a bounding box
async function getOccurrenceHeatmap(req, res) {
  try {
    const { minLat, minLng, maxLat, maxLng } = req.query;

    if (!minLat || !minLng || !maxLat || !maxLng) {
      return res.status(400).json({
        error: 'Missing required parameters: minLat, minLng, maxLat, maxLng'
      });
    }

    const query = `
      SELECT
        geohash_l7,
        total_occurrences,
        species_count,
        ST_AsGeoJSON(geometry)::json as geometry,
        ST_Area(geometry::geography) / 1000000 as area_km2,
        datetime
      FROM geohash_species_tiles
      WHERE ST_Intersects(
        geometry,
        ST_MakeEnvelope($1, $2, $3, $4, 4326)
      )
      ORDER BY total_occurrences DESC
      LIMIT 10000;
    `;

    const result = await pool.query(query, [
      parseFloat(minLng),
      parseFloat(minLat),
      parseFloat(maxLng),
      parseFloat(maxLat)
    ]);

    // Calculate density and find min/max for normalization
    const tilesWithDensity = result.rows.map(row => {
      const area = parseFloat(row.area_km2) || 1; // Avoid division by zero
      const density = row.total_occurrences / area; // occurrences per km²
      return {
        ...row,
        density,
        density_per_km2: Math.round(density * 100) / 100
      };
    });

    // Find min/max density for color scale using a loop (to avoid stack overflow with large arrays)
    let minDensity = Infinity;
    let maxDensity = -Infinity;
    for (const tile of tilesWithDensity) {
      if (tile.density < minDensity) minDensity = tile.density;
      if (tile.density > maxDensity) maxDensity = tile.density;
    }

    res.json({
      bbox: {
        min: [parseFloat(minLng), parseFloat(minLat)],
        max: [parseFloat(maxLng), parseFloat(maxLat)]
      },
      tile_count: result.rows.length,
      density_range: {
        min: Math.round(minDensity * 100) / 100,
        max: Math.round(maxDensity * 100) / 100
      },
      features: tilesWithDensity.map(row => ({
        type: 'Feature',
        properties: {
          geohash: row.geohash_l7,
          total_occurrences: row.total_occurrences,
          species_count: row.species_count,
          area_km2: Math.round(parseFloat(row.area_km2) * 100) / 100,
          density: row.density_per_km2,
          datetime: row.datetime,
          // Normalized density for color mapping (0-1 scale)
          density_normalized: (row.density - minDensity) / (maxDensity - minDensity || 1)
        },
        geometry: row.geometry
      }))
    });

  } catch (error) {
    console.error('Error in getOccurrenceHeatmap:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get species in a specific geohash tile
async function getSpeciesInTile(req, res) {
  try {
    const { geohash } = req.params;
    
    // Validate geohash length
    if (geohash.length !== 7) {
      return res.status(400).json({ 
        error: 'Invalid geohash. Must be exactly 7 characters (level 7)' 
      });
    }
    
    const query = `
      SELECT 
        species_data,
        total_occurrences,
        species_count,
        datetime,
        data_source,
        ST_AsGeoJSON(geometry)::json as geometry
      FROM geohash_species_tiles
      WHERE geohash_l7 = $1;
    `;
    
    const result = await pool.query(query, [geohash]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ 
        error: 'No data found for this geohash tile' 
      });
    }
    
    const tile = result.rows[0];
    const taxonIds = Object.keys(tile.species_data);
    
    // Get species details
    const speciesQuery = `
      SELECT taxon_id, scientific_name, common_name
      FROM species
      WHERE taxon_id = ANY($1)
      ORDER BY scientific_name;
    `;
    
    const speciesResult = await pool.query(speciesQuery, [taxonIds]);
    
    // Map occurrence counts to species
    const speciesWithCounts = speciesResult.rows.map(species => ({
      ...species,
      occurrence_count: tile.species_data[species.taxon_id]
    }));
    
    res.json({
      geohash: geohash,
      tile_info: {
        total_occurrences: tile.total_occurrences,
        species_count: tile.species_count,
        datetime: tile.datetime,
        data_source: tile.data_source,
        geometry: tile.geometry
      },
      species: speciesWithCounts
    });
    
  } catch (error) {
    console.error('Error in getSpeciesInTile:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get tiles with temporal filtering (STAC-compliant)
async function getTilesByTimeRange(req, res) {
  try {
    const { start, end, bbox } = req.query;
    
    if (!start || !end) {
      return res.status(400).json({ 
        error: 'Missing required parameters: start and end dates' 
      });
    }
    
    let query = `
      SELECT 
        geohash_l7 as id,
        'Feature' as type,
        ST_AsGeoJSON(geometry)::json as geometry,
        json_build_object(
          'datetime', datetime,
          'species_count', species_count,
          'total_occurrences', total_occurrences,
          'data_source', data_source
        ) as properties
      FROM geohash_species_tiles
      WHERE datetime >= $1 AND datetime <= $2
    `;
    
    const params = [start, end];
    
    // Add spatial filter if bbox provided
    if (bbox) {
      const [minLng, minLat, maxLng, maxLat] = bbox.split(',').map(parseFloat);
      query += ` AND ST_Intersects(geometry, ST_MakeEnvelope($3, $4, $5, $6, 4326))`;
      params.push(minLng, minLat, maxLng, maxLat);
    }
    
    query += ` ORDER BY datetime DESC;`;
    
    const result = await pool.query(query, params);
    
    res.json({
      type: 'FeatureCollection',
      features: result.rows,
      numberReturned: result.rows.length,
      timeRange: { start, end }
    });
    
  } catch (error) {
    console.error('Error in getTilesByTimeRange:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get geospatial statistics
async function getGeospatialStats(req, res) {
  try {
    const query = `
      SELECT 
        COUNT(*) as total_tiles,
        COUNT(DISTINCT jsonb_object_keys(species_data)) as unique_species,
        SUM(total_occurrences) as total_occurrences,
        MIN(datetime) as earliest_observation,
        MAX(datetime) as latest_observation,
        array_agg(DISTINCT data_source) as data_sources
      FROM geohash_species_tiles;
    `;
    
    const result = await pool.query(query);
    const stats = result.rows[0];
    
    // Get coverage area
    const coverageQuery = `
      SELECT 
        ST_Area(ST_Union(geometry)::geography) / 1000000 as coverage_area_km2,
        ST_AsGeoJSON(ST_Envelope(ST_Union(geometry)))::json as bounding_box
      FROM geohash_species_tiles;
    `;
    
    const coverageResult = await pool.query(coverageQuery);
    const coverage = coverageResult.rows[0];
    
    res.json({
      tiles: {
        total: parseInt(stats.total_tiles),
        tile_size_m: 150  // Level 7 geohash
      },
      species: {
        unique_count: parseInt(stats.unique_species)
      },
      occurrences: {
        total: parseInt(stats.total_occurrences)
      },
      temporal: {
        earliest: stats.earliest_observation,
        latest: stats.latest_observation
      },
      spatial: {
        coverage_km2: Math.round(coverage.coverage_area_km2),
        bounding_box: coverage.bounding_box
      },
      data_sources: stats.data_sources
    });
    
  } catch (error) {
    console.error('Error in getGeospatialStats:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Analyze species within a polygon area
async function analyzePlot(req, res) {
  try {
    const { geometry } = req.body;
    
    if (!geometry || geometry.type !== 'Polygon') {
      return res.status(400).json({ 
        error: 'Invalid geometry. Must be a GeoJSON Polygon' 
      });
    }
    
    // Convert GeoJSON polygon to PostGIS format
    const geoJsonString = JSON.stringify(geometry);
    
    const query = `
      WITH user_polygon AS (
        SELECT ST_GeomFromGeoJSON($1) as geom
      ),
      intersected_countries AS (
        SELECT
          c.admin,
          CASE
            WHEN c.admin = 'United States of America' THEN 'United States'
            WHEN c.admin = 'United Kingdom' THEN 'United Kingdom'
            ELSE c.admin
          END as species_search_name,
          ST_Area(ST_Intersection(c.geom, up.geom)) / ST_Area(up.geom) as area_fraction
        FROM countries c, user_polygon up
        WHERE ST_Intersects(c.geom, up.geom)
      ),
      primary_country AS (
        SELECT admin, species_search_name
        FROM intersected_countries
        ORDER BY area_fraction DESC
        LIMIT 1
      ),
      intersecting_tiles AS (
        SELECT
          species_data,
          geohash_l7
        FROM geohash_species_tiles gst, user_polygon up
        WHERE ST_Intersects(gst.geometry, up.geom)
      ),
      species_aggregated AS (
        SELECT
          key as taxon_id,
          SUM(value::int) as total_occurrences,
          COUNT(DISTINCT geohash_l7) as tile_count
        FROM intersecting_tiles,
        LATERAL jsonb_each_text(species_data)
        GROUP BY key
      )
      SELECT
        sa.taxon_id,
        sa.total_occurrences,
        sa.tile_count,
        COALESCE(s.species_scientific_name, s.accepted_scientific_name) as scientific_name,
        s.common_name,
        s.family,
        s.genus,

        -- Country detection (primary country for display)
        pc.admin as country_name,
        pc.species_search_name,

        -- Native status analysis (check ALL intersected countries)
        CASE
          WHEN EXISTS (
            SELECT 1 FROM intersected_countries ic
            WHERE s.countries_native LIKE '%' || ic.species_search_name || '%'
          ) THEN 'native'
          WHEN EXISTS (
            SELECT 1 FROM intersected_countries ic
            WHERE s.countries_introduced LIKE '%' || ic.species_search_name || '%'
          ) THEN 'introduced'
          ELSE 'unknown'
        END as native_status,

        -- Calculate native percentage across all intersected countries
        COALESCE((
          SELECT
            ROUND(
              SUM(
                CASE
                  WHEN s.countries_native LIKE '%' || ic.species_search_name || '%' THEN ic.area_fraction * 100
                  ELSE 0
                END
              )
            )
          FROM intersected_countries ic
        ), 0) as native_percentage,

        -- Intact forest analysis
        CASE
          WHEN s.present_intact_forest LIKE '%YES%' THEN 'present'
          WHEN s.present_intact_forest = 'NO' THEN 'absent'
          ELSE 'unknown'
        END as intact_forest_status,

        -- Commercial status
        CASE WHEN s.comercialspecies_lower = 'YES' THEN true ELSE false END as is_commercial

      FROM species_aggregated sa
      LEFT JOIN species s ON s.taxon_id = sa.taxon_id
      LEFT JOIN primary_country pc ON true
      ORDER BY sa.total_occurrences DESC;
    `;
    
    const result = await pool.query(query, [geoJsonString]);

    const totalOccurrences = result.rows.reduce(
      (sum, row) => sum + parseInt(row.total_occurrences),
      0
    );

    // Calculate cross-analysis statistics
    let crossAnalysis = null;
    if (result.rows.length > 0) {
      const firstRow = result.rows[0];
      const countryDetected = firstRow.country_name != null;

      // Get all intersected countries for display
      const countriesQuery = `
        WITH user_polygon AS (
          SELECT ST_GeomFromGeoJSON($1) as geom
        ),
        intersected_countries AS (
          SELECT
            c.admin,
            ST_Area(ST_Intersection(c.geom, up.geom)) / ST_Area(up.geom) as area_fraction
          FROM countries c, user_polygon up
          WHERE ST_Intersects(c.geom, up.geom)
          ORDER BY area_fraction DESC
        )
        SELECT admin, ROUND(area_fraction * 100) as percentage
        FROM intersected_countries
        WHERE area_fraction > 0.01;  -- Only show countries with >1% overlap
      `;

      const countriesResult = await pool.query(countriesQuery, [geoJsonString]);
      const countryList = countriesResult.rows.map(r =>
        `${r.admin} (${r.percentage}%)`
      ).join(', ');

      // Count native status categories
      const nativeSpecies = result.rows.filter(row => row.native_status === 'native').length;
      const introducedSpecies = result.rows.filter(row => row.native_status === 'introduced').length;
      const unknownNativeStatus = result.rows.filter(row => row.native_status === 'unknown').length;

      // Count intact forest status categories
      const intactForestSpecies = result.rows.filter(row => row.intact_forest_status === 'present').length;
      const nonIntactForestSpecies = result.rows.filter(row => row.intact_forest_status === 'absent').length;
      const unknownForestStatus = result.rows.filter(row => row.intact_forest_status === 'unknown').length;

      // Count commercial species
      const commercialSpecies = result.rows.filter(row => row.is_commercial === true).length;
      const nonCommercialSpecies = result.rows.filter(row => row.is_commercial === false).length;

      crossAnalysis = {
        country: countryList || null,
        countryDetected: countryDetected,
        nativeSpecies,
        introducedSpecies,
        unknownNativeStatus,
        intactForestSpecies,
        nonIntactForestSpecies,
        unknownForestStatus,
        commercialSpecies,
        nonCommercialSpecies
      };
    }

    res.json({
      totalSpecies: result.rows.length,
      totalOccurrences: totalOccurrences,
      crossAnalysis: crossAnalysis,
      species: result.rows.map(row => ({
        taxon_id: row.taxon_id,
        scientific_name: row.scientific_name || `Unknown (${row.taxon_id})`,
        common_name: row.common_name || null,
        family: row.family || null,
        genus: row.genus || null,
        occurrences: parseInt(row.total_occurrences),
        tile_count: parseInt(row.tile_count),
        nativeStatus: row.native_status || 'unknown',
        nativePercentage: parseInt(row.native_percentage) || 0,
        intactForestStatus: row.intact_forest_status || 'unknown',
        isCommercial: row.is_commercial || false
      }))
    });
    
  } catch (error) {
    console.error('Error in analyzePlot:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get species within a specific ecoregion
async function getSpeciesByEcoregion(req, res) {
  try {
    const { ecoregion_id } = req.params;
    const { limit = 100, offset = 0 } = req.query;
    
    if (!ecoregion_id) {
      return res.status(400).json({ 
        error: 'Missing required parameter: ecoregion_id' 
      });
    }
    
    const query = `
      WITH ecoregion_species AS (
        SELECT 
          jsonb_object_keys(species_data) as taxon_id,
          SUM((species_data->>jsonb_object_keys(species_data))::int) as total_occurrences,
          COUNT(DISTINCT geohash_l7) as tile_count
        FROM geohash_species_tiles
        WHERE eco_id = $1
        GROUP BY jsonb_object_keys(species_data)
      )
      SELECT 
        es.taxon_id,
        es.total_occurrences,
        es.tile_count,
        s.species_scientific_name as scientific_name,
        s.common_name,
        s.family,
        s.genus
      FROM ecoregion_species es
      LEFT JOIN species s ON s.taxon_id = es.taxon_id
      ORDER BY es.total_occurrences DESC
      LIMIT $2 OFFSET $3;
    `;
    
    const result = await pool.query(query, [ecoregion_id, limit, offset]);
    
    // Get ecoregion info
    const ecoregionQuery = `
      SELECT eco_id, eco_name, biome_name, realm, 
             ST_Area(geom::geography) / 1000000 as area_km2
      FROM ecoregions WHERE eco_id = $1;
    `;
    const ecoregionResult = await pool.query(ecoregionQuery, [ecoregion_id]);
    
    if (ecoregionResult.rows.length === 0) {
      return res.status(404).json({ error: 'Ecoregion not found' });
    }
    
    const ecoregion = ecoregionResult.rows[0];
    
    res.json({
      ecoregion: {
        eco_id: ecoregion.eco_id,
        eco_name: ecoregion.eco_name,
        biome_name: ecoregion.biome_name,
        realm: ecoregion.realm,
        area_km2: Math.round(parseFloat(ecoregion.area_km2))
      },
      species_count: result.rows.length,
      species: result.rows.map(row => ({
        taxon_id: row.taxon_id,
        scientific_name: row.scientific_name || `Unknown (${row.taxon_id})`,
        common_name: row.common_name || null,
        family: row.family || null,
        genus: row.genus || null,
        occurrences: parseInt(row.total_occurrences),
        tile_count: parseInt(row.tile_count)
      }))
    });
    
  } catch (error) {
    console.error('Error in getSpeciesByEcoregion:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get ecoregion information for specific coordinates
async function getEcoregionAtPoint(req, res) {
  try {
    const { lat, lng } = req.query;
    
    if (!lat || !lng) {
      return res.status(400).json({ 
        error: 'Missing required parameters: lat and lng' 
      });
    }
    
    const query = `
      SELECT 
        eco_id,
        eco_name,
        biome_name,
        realm,
        ST_Area(geom::geography) / 1000000 as area_km2
      FROM ecoregions
      WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
      LIMIT 1;
    `;
    
    const result = await pool.query(query, [parseFloat(lng), parseFloat(lat)]);
    
    if (result.rows.length === 0) {
      return res.json({
        location: { lat: parseFloat(lat), lng: parseFloat(lng) },
        ecoregion: null,
        message: 'No ecoregion found at this location (may be ocean or unmapped area)'
      });
    }
    
    const ecoregion = result.rows[0];
    
    res.json({
      location: { lat: parseFloat(lat), lng: parseFloat(lng) },
      ecoregion: {
        eco_id: ecoregion.eco_id,
        eco_name: ecoregion.eco_name,
        biome_name: ecoregion.biome_name,
        realm: ecoregion.realm,
        area_km2: Math.round(parseFloat(ecoregion.area_km2))
      }
    });
    
  } catch (error) {
    console.error('Error in getEcoregionAtPoint:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get overlapping ecoregions for a polygon
async function getEcoregionsIntersecting(req, res) {
  try {
    const { geometry } = req.body;
    
    if (!geometry || geometry.type !== 'Polygon') {
      return res.status(400).json({ 
        error: 'Invalid geometry. Must be a GeoJSON Polygon' 
      });
    }
    
    const geoJsonString = JSON.stringify(geometry);
    
    const query = `
      SELECT 
        e.eco_id,
        e.eco_name,
        e.biome_name,
        e.realm,
        ST_Area(e.geom::geography) / 1000000 as total_area_km2,
        ST_Area(ST_Intersection(e.geom, ST_GeomFromGeoJSON($1))::geography) / 1000000 as intersection_area_km2,
        ST_AsGeoJSON(ST_Intersection(e.geom, ST_GeomFromGeoJSON($1)))::json as intersection_geom
      FROM ecoregions e
      WHERE ST_Intersects(e.geom, ST_GeomFromGeoJSON($1))
      ORDER BY intersection_area_km2 DESC;
    `;
    
    const result = await pool.query(query, [geoJsonString]);
    
    res.json({
      ecoregions_count: result.rows.length,
      ecoregions: result.rows.map(row => ({
        eco_id: row.eco_id,
        eco_name: row.eco_name,
        biome_name: row.biome_name,
        realm: row.realm,
        total_area_km2: Math.round(parseFloat(row.total_area_km2)),
        intersection_area_km2: Math.round(parseFloat(row.intersection_area_km2)),
        coverage_percent: Math.round(parseFloat(row.intersection_area_km2) / parseFloat(row.total_area_km2) * 100),
        geometry: row.intersection_geom
      }))
    });
    
  } catch (error) {
    console.error('Error in getEcoregionsIntersecting:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get ecoregion diversity statistics
async function getEcoregionStats(req, res) {
  try {
    const query = `
      SELECT 
        e.eco_id,
        e.eco_name,
        e.biome_name,
        e.realm,
        ST_Area(e.geom::geography) / 1000000 as area_km2,
        COUNT(DISTINCT t.geohash_l7) as tile_count,
        COUNT(DISTINCT jsonb_object_keys(t.species_data)) as unique_species,
        SUM(t.total_occurrences) as total_occurrences,
        COUNT(DISTINCT jsonb_object_keys(t.species_data))::float / (ST_Area(e.geom::geography) / 1000000000) as species_per_1000km2
      FROM ecoregions e
      LEFT JOIN geohash_species_tiles t ON t.eco_id = e.eco_id
      GROUP BY e.eco_id, e.eco_name, e.biome_name, e.realm, e.geom
      HAVING COUNT(DISTINCT jsonb_object_keys(t.species_data)) > 0
      ORDER BY unique_species DESC
      LIMIT 50;
    `;
    
    const result = await pool.query(query);
    
    res.json({
      top_ecoregions: result.rows.map(row => ({
        eco_id: row.eco_id,
        eco_name: row.eco_name,
        biome_name: row.biome_name,
        realm: row.realm,
        area_km2: Math.round(parseFloat(row.area_km2)),
        tile_count: parseInt(row.tile_count),
        unique_species: parseInt(row.unique_species),
        total_occurrences: parseInt(row.total_occurrences),
        species_density: parseFloat(row.species_per_1000km2).toFixed(2)
      }))
    });
    
  } catch (error) {
    console.error('Error in getEcoregionStats:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Export ecoregion boundary in various formats
async function exportEcoregion(req, res) {
  try {
    const { ecoregion_id } = req.params;
    const { format = 'kml' } = req.query;
    
    if (!ecoregion_id) {
      return res.status(400).json({ 
        error: 'Missing required parameter: ecoregion_id' 
      });
    }

    // First get basic ecoregion info
    const infoQuery = `
      SELECT eco_id, eco_name, biome_name, realm,
             ST_Area(geom::geography) / 1000000 as area_km2
      FROM ecoregions 
      WHERE eco_id = $1;
    `;
    
    const infoResult = await pool.query(infoQuery, [ecoregion_id]);
    
    if (infoResult.rows.length === 0) {
      return res.status(404).json({ error: 'Ecoregion not found' });
    }
    
    const ecoregion = infoResult.rows[0];
    
    // Generate different formats based on request
    if (format.toLowerCase() === 'kml') {
      const kmlQuery = `
        SELECT ST_AsKML(geom) as kml_geometry 
        FROM ecoregions 
        WHERE eco_id = $1;
      `;
      
      const kmlResult = await pool.query(kmlQuery, [ecoregion_id]);
      const kmlGeometry = kmlResult.rows[0].kml_geometry;
      
      // Create full KML document with metadata
      const kmlDocument = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${ecoregion.eco_name}</name>
    <description>
      WWF Terrestrial Ecoregion
      
      Ecoregion: ${ecoregion.eco_name}
      Biome: ${ecoregion.biome_name}
      Realm: ${ecoregion.realm}
      Area: ${Math.round(parseFloat(ecoregion.area_km2)).toLocaleString()} km²
      
      Source: Treekipedia (https://treekipedia.silvi.earth)
      Data: WWF Terrestrial Ecoregions 2017
    </description>
    <Style id="ecoregionStyle">
      <LineStyle>
        <color>ff00ff00</color>
        <width>2</width>
      </LineStyle>
      <PolyStyle>
        <color>7f00ff00</color>
        <fill>1</fill>
        <outline>1</outline>
      </PolyStyle>
    </Style>
    <Placemark>
      <name>${ecoregion.eco_name}</name>
      <description>
        Biome: ${ecoregion.biome_name}
        Realm: ${ecoregion.realm}
        Area: ${Math.round(parseFloat(ecoregion.area_km2)).toLocaleString()} km²
      </description>
      <styleUrl>#ecoregionStyle</styleUrl>
      ${kmlGeometry}
    </Placemark>
  </Document>
</kml>`;

      res.set({
        'Content-Type': 'application/vnd.google-earth.kml+xml',
        'Content-Disposition': `attachment; filename="${ecoregion.eco_name.replace(/[^a-zA-Z0-9]/g, '_')}.kml"`
      });
      
      res.send(kmlDocument);
      
    } else if (format.toLowerCase() === 'geojson') {
      const geoJsonQuery = `
        SELECT 
          json_build_object(
            'type', 'Feature',
            'properties', json_build_object(
              'eco_id', eco_id,
              'eco_name', eco_name,
              'biome_name', biome_name,
              'realm', realm,
              'area_km2', ROUND(ST_Area(geom::geography) / 1000000)
            ),
            'geometry', ST_AsGeoJSON(geom)::json
          ) as geojson
        FROM ecoregions 
        WHERE eco_id = $1;
      `;
      
      const geoJsonResult = await pool.query(geoJsonQuery, [ecoregion_id]);
      
      res.set({
        'Content-Type': 'application/geo+json',
        'Content-Disposition': `attachment; filename="${ecoregion.eco_name.replace(/[^a-zA-Z0-9]/g, '_')}.geojson"`
      });
      
      res.json(geoJsonResult.rows[0].geojson);
      
    } else if (format.toLowerCase() === 'wkt') {
      const wktQuery = `
        SELECT ST_AsText(geom) as wkt_geometry 
        FROM ecoregions 
        WHERE eco_id = $1;
      `;
      
      const wktResult = await pool.query(wktQuery, [ecoregion_id]);
      
      res.set({
        'Content-Type': 'text/plain',
        'Content-Disposition': `attachment; filename="${ecoregion.eco_name.replace(/[^a-zA-Z0-9]/g, '_')}.wkt"`
      });
      
      res.send(`# ${ecoregion.eco_name}\n# Biome: ${ecoregion.biome_name}\n# Realm: ${ecoregion.realm}\n# Area: ${Math.round(parseFloat(ecoregion.area_km2)).toLocaleString()} km²\n\n${wktResult.rows[0].wkt_geometry}`);
      
    } else {
      return res.status(400).json({ 
        error: 'Unsupported format. Supported formats: kml, geojson, wkt' 
      });
    }
    
  } catch (error) {
    console.error('Error in exportEcoregion:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Get ecoregion boundaries for map display
async function getEcoregionBoundaries(req, res) {
  try {
    const { bbox, simplify = 0.01 } = req.query;

    let query;
    let params = [];

    if (bbox) {
      // Parse bbox: minLng,minLat,maxLng,maxLat
      const [minLng, minLat, maxLng, maxLat] = bbox.split(',').map(Number);

      query = `
        SELECT
          eco_id,
          eco_name,
          biome_name,
          realm,
          color,
          color_bio,
          ST_AsGeoJSON(ST_Simplify(geom, $5))::json as geometry
        FROM ecoregions
        WHERE ST_Intersects(
          geom,
          ST_MakeEnvelope($1, $2, $3, $4, 4326)
        )
      `;
      params = [minLng, minLat, maxLng, maxLat, simplify];
    } else {
      // Return all ecoregions (simplified for performance)
      query = `
        SELECT
          eco_id,
          eco_name,
          biome_name,
          realm,
          color,
          color_bio,
          ST_AsGeoJSON(ST_Simplify(geom, $1))::json as geometry
        FROM ecoregions
      `;
      params = [simplify];
    }

    const result = await pool.query(query, params);

    // Return as GeoJSON FeatureCollection
    res.json({
      type: 'FeatureCollection',
      features: result.rows.map(row => ({
        type: 'Feature',
        properties: {
          eco_id: row.eco_id,
          eco_name: row.eco_name,
          biome_name: row.biome_name,
          realm: row.realm,
          color: row.color,
          color_bio: row.color_bio
        },
        geometry: row.geometry
      }))
    });

  } catch (error) {
    console.error('Error in getEcoregionBoundaries:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// In-memory cache for intact forest data
class IntactForestCache {
  constructor() {
    this.cache = new Map();
    this.maxSize = 100;
    this.ttl = 5 * 60 * 1000; // 5 minutes
    this.hits = 0;
    this.misses = 0;
    this.slowQueries = [];

    // Cleanup old entries every minute
    setInterval(() => this.cleanup(), 60000);
  }

  getCacheKey(minLat, maxLat, minLng, maxLng, zoom) {
    // Dynamic precision based on zoom level
    const precision = zoom > 10 ? 3 : zoom > 5 ? 2 : 1;
    return `${parseFloat(minLat).toFixed(precision)},${parseFloat(maxLat).toFixed(precision)},` +
           `${parseFloat(minLng).toFixed(precision)},${parseFloat(maxLng).toFixed(precision)},${zoom}`;
  }

  get(key) {
    const entry = this.cache.get(key);
    if (!entry) {
      this.misses++;
      return null;
    }

    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      this.misses++;
      return null;
    }

    this.hits++;
    return entry.data;
  }

  set(key, data) {
    if (this.cache.size >= this.maxSize) {
      // Remove oldest entry
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  cleanup() {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.ttl) {
        this.cache.delete(key);
      }
    }
  }

  recordSlowQuery(duration, params) {
    this.slowQueries.push({
      duration,
      params,
      timestamp: Date.now()
    });

    // Keep only last 10 slow queries
    if (this.slowQueries.length > 10) {
      this.slowQueries.shift();
    }
  }

  getStats() {
    const total = this.hits + this.misses;
    return {
      size: this.cache.size,
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? (this.hits / total * 100).toFixed(2) + '%' : 'N/A',
      slowQueries: this.slowQueries
    };
  }
}

// Initialize cache
const intactForestCache = new IntactForestCache();

// Rate limiting (simple IP-based)
const rateLimiter = new Map();
const RATE_LIMIT = 100; // requests per minute (increased for map interactions)
const RATE_WINDOW = 60000; // 1 minute

function checkRateLimit(ip) {
  const now = Date.now();
  const record = rateLimiter.get(ip);

  if (!record) {
    rateLimiter.set(ip, { count: 1, resetTime: now + RATE_WINDOW });
    return true;
  }

  if (now > record.resetTime) {
    rateLimiter.set(ip, { count: 1, resetTime: now + RATE_WINDOW });
    return true;
  }

  if (record.count >= RATE_LIMIT) {
    return false;
  }

  record.count++;
  return true;
}

// Helper function to determine which table to use based on zoom level
function getTableForZoom(zoom) {
  if (zoom <= 3) return 'intact_forest_z0_z3';
  if (zoom <= 6) return 'intact_forest_z4_z6';
  if (zoom <= 9) return 'intact_forest_z7_z9';
  return 'intact_forest_landscapes_2021';
}

// Get intact forest boundaries for map display
async function getIntactForestBoundaries(req, res) {
  const startTime = Date.now();
  const clientIp = req.ip || req.connection.remoteAddress;

  try {
    // Rate limiting
    if (!checkRateLimit(clientIp)) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        message: 'Maximum 30 requests per minute allowed'
      });
    }

    const { bbox, zoom = 3 } = req.query;

    if (!bbox) {
      return res.status(400).json({
        error: 'Missing required parameter: bbox',
        format: 'bbox=minLng,minLat,maxLng,maxLat'
      });
    }

    // Parse bbox
    const [minLng, minLat, maxLng, maxLat] = bbox.split(',').map(Number);

    if ([minLng, minLat, maxLng, maxLat].some(isNaN)) {
      return res.status(400).json({
        error: 'Invalid bbox format',
        format: 'bbox=minLng,minLat,maxLng,maxLat (all numeric)'
      });
    }

    const zoomLevel = parseInt(zoom);

    // Check cache
    const cacheKey = intactForestCache.getCacheKey(minLat, maxLat, minLng, maxLng, zoomLevel);
    const cached = intactForestCache.get(cacheKey);

    if (cached) {
      res.set('X-Cache', 'HIT');
      return res.json(cached);
    }

    // Determine table based on zoom level
    const tableName = getTableForZoom(zoomLevel);

    // Progressive polygon limit based on zoom
    const polygonLimit = zoomLevel <= 3 ? 500 : zoomLevel <= 6 ? 300 : zoomLevel <= 9 ? 200 : 100;

    // Query with index hint for PostgreSQL
    const query = `
      WITH viewport_polygons AS (
        SELECT /*+ INDEX(${tableName} idx_${tableName}_geom) */
          ogc_fid,
          ifl_id,
          year,
          ROUND((gfw_area__ / 1000000)::numeric, 2) as area_km2,
          ST_Intersection(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326)) as clipped_geom
        FROM ${tableName}
        WHERE ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
          AND ST_IsValid(geom)
        ORDER BY gfw_area__ DESC
        LIMIT $5
      )
      SELECT
        ogc_fid,
        ifl_id,
        year,
        area_km2,
        ST_AsGeoJSON(clipped_geom)::json as geometry,
        ST_NPoints(clipped_geom) as vertex_count
      FROM viewport_polygons
      WHERE clipped_geom IS NOT NULL
        AND ST_IsValid(clipped_geom);
    `;

    const queryStartTime = Date.now();
    const result = await pool.query(query, [minLng, minLat, maxLng, maxLat, polygonLimit]);
    const queryDuration = Date.now() - queryStartTime;

    // Record slow queries (>2 seconds)
    if (queryDuration > 2000) {
      intactForestCache.recordSlowQuery(queryDuration, { bbox, zoom: zoomLevel, table: tableName });
    }

    // Build GeoJSON response
    const response = {
      type: 'FeatureCollection',
      features: result.rows.map(row => ({
        type: 'Feature',
        properties: {
          ogc_fid: row.ogc_fid,
          ifl_id: row.ifl_id,
          year: row.year,
          area_km2: parseFloat(row.area_km2),
          vertex_count: row.vertex_count
        },
        geometry: row.geometry
      })),
      metadata: {
        zoom_level: zoomLevel,
        table_used: tableName,
        bbox: { minLng, minLat, maxLng, maxLat },
        polygon_count: result.rows.length,
        polygon_limit: polygonLimit,
        query_time_ms: queryDuration
      }
    };

    // Cache the result
    intactForestCache.set(cacheKey, response);

    res.set('X-Cache', 'MISS');
    res.set('X-Query-Time', `${queryDuration}ms`);
    res.json(response);

  } catch (error) {
    console.error('Error in getIntactForestBoundaries:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
}

// Get native species for an ecoregion by name
// Uses species.ecoregions field and filters by native status
async function getNativeSpeciesByEcoregionName(req, res) {
  try {
    const { ecoregion_name } = req.params;
    const { native_only = 'true', exclude_invasive = 'true', limit = 1000 } = req.query;

    if (!ecoregion_name) {
      return res.status(400).json({
        error: 'Missing required parameter: ecoregion_name'
      });
    }

    // Get countries that intersect this ecoregion
    const countriesQuery = `
      SELECT array_agg(DISTINCT
        CASE
          WHEN name_en = 'United States of America' THEN 'United States'
          WHEN name_en = 'United Kingdom' THEN 'United Kingdom'
          ELSE name_en
        END
      ) as country_list
      FROM ecoregions e
      JOIN countries c ON ST_Intersects(e.geom, c.geom)
      WHERE e.eco_name = $1;
    `;

    const countriesResult = await pool.query(countriesQuery, [ecoregion_name]);

    if (countriesResult.rows.length === 0 || !countriesResult.rows[0].country_list) {
      return res.status(404).json({
        error: 'Ecoregion not found or no countries intersect this ecoregion'
      });
    }

    const countries = countriesResult.rows[0].country_list;

    // Build SQL pattern matching for countries
    const countryPatterns = countries.map(c => `countries_native LIKE '%${c}%'`).join(' OR ');

    const query = `
      SELECT
        taxon_id,
        taxon_full,
        species_scientific_name,
        common_name,
        family,
        genus,
        countries_native,
        countries_invasive,
        countries_introduced
      FROM species
      WHERE ecoregions LIKE $1
        AND ecoregions != 'NA'
        ${native_only === 'true' ? `AND (${countryPatterns})` : ''}
        ${exclude_invasive === 'true' ? `AND (countries_invasive = 'NA' OR countries_invasive NOT LIKE ANY($2))` : ''}
      ORDER BY species_scientific_name
      LIMIT $3;
    `;

    const invasivePatterns = countries.map(c => `%${c}%`);
    const result = await pool.query(query, [
      `%${ecoregion_name}%`,
      invasivePatterns,
      limit
    ]);

    // Get ecoregion metadata
    const ecoregionInfoQuery = `
      SELECT eco_id, eco_name, biome_name, realm,
             ST_Area(geom::geography) / 1000000 as area_km2
      FROM ecoregions
      WHERE eco_name = $1;
    `;

    const ecoregionInfo = await pool.query(ecoregionInfoQuery, [ecoregion_name]);

    res.json({
      ecoregion: ecoregionInfo.rows[0] || { eco_name: ecoregion_name },
      countries_in_ecoregion: countries,
      filters_applied: {
        native_only: native_only === 'true',
        exclude_invasive: exclude_invasive === 'true'
      },
      species_count: result.rows.length,
      species: result.rows.map(row => ({
        taxon_id: row.taxon_id,
        taxon_full: row.taxon_full,
        scientific_name: row.species_scientific_name,
        common_name: row.common_name || null,
        family: row.family || null,
        genus: row.genus || null
      }))
    });

  } catch (error) {
    console.error('Error in getNativeSpeciesByEcoregionName:', error);
    res.status(500).json({ error: 'Internal server error', details: error.message });
  }
}

return {
  findSpeciesNearby,
  getSpeciesDistribution,
  getOccurrenceHeatmap,
  getSpeciesInTile,
  getTilesByTimeRange,
  getGeospatialStats,
  analyzePlot,
  getSpeciesByEcoregion,
  getEcoregionAtPoint,
  getEcoregionsIntersecting,
  getEcoregionStats,
  exportEcoregion,
  getEcoregionBoundaries,
  getNativeSpeciesByEcoregionName,
  getIntactForestBoundaries
};

};