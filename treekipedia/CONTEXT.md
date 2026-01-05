> Jeremic:
/*
TREEKIPEDIA ZONE SCHEMA
A unified schema for all environmental/geographic zones in the Treekipedia system.

This schema allows ANY environmental dataset (biomes, ecoregions, land types, 
climate zones, etc.) to be queried consistently with pre-computed connectivity.
*/

-- ============================================================================
-- MASTER ZONE TABLE
-- ============================================================================
CREATE TABLE treekipedia_zones (
  -- MASTER IDENTIFIER (Djimo's "AOI_ID")
  aoi_id STRING NOT NULL,  -- Format: "BIOME_NA_DESERT_001" or "ECO_SAHARA_042"
  
  -- ZONE CLASSIFICATION
  zone_type STRING NOT NULL,  -- "BIOME", "ECOREGION", "LAND_TYPE", "CLIMATE_ZONE"
  zone_name STRING NOT NULL,  -- Human-readable name: "Sonoran Desert"
  zone_class STRING,          -- Classification: "Deserts & Xeric Shrublands"
  
  -- CONNECTIVITY (The key to solving continuous boundary problem!)
  cluster_id INT64 NOT NULL,  -- Which connected group does this belong to?
  cluster_name STRING,         -- "North American Deserts", "Sahara Desert Complex"
  is_continuous BOOLEAN,       -- Is this part of a continuous region?
  
  -- ORIGINAL SOURCE DATA
  source_dataset STRING,       -- "WWF_Ecoregions", "ESA_CCI_LandCover", etc.
  source_id STRING,            -- Original ID from source dataset (e.g., ECO_ID)
  
  -- GEOGRAPHY
  geometry GEOGRAPHY NOT NULL, -- The actual polygon/multipolygon
  centroid GEOGRAPHY,          -- Center point of the zone
  area_km2 FLOAT64,            -- Area in square kilometers
  
  -- DATA TYPE (Vector vs Raster)
  data_type STRING,            -- "VECTOR" or "RASTER"
  resolution_meters FLOAT64,   -- For raster data, pixel size
  
  -- METADATA
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  processing_notes STRING
);

-- ============================================================================
-- ZONE CONNECTIVITY TABLE
-- ============================================================================
-- Stores which zones touch each other (pre-computed adjacency graph)
CREATE TABLE zone_connectivity (
  aoi_id_a STRING NOT NULL,    -- First zone
  aoi_id_b STRING NOT NULL,    -- Second zone (touches first zone)
  cluster_id INT64 NOT NULL,   -- Shared cluster ID
  
  -- Connectivity metrics
  shared_boundary_length_km FLOAT64,  -- How much border they share
  connectivity_type STRING,            -- "DIRECT_TOUCH", "CLOSE_PROXIMITY"
  
  PRIMARY KEY (aoi_id_a, aoi_id_b)
);

-- ============================================================================
-- CLUSTER SUMMARY TABLE
-- ============================================================================
-- Summary information about each connected cluster
CREATE TABLE zone_clusters (
  cluster_id INT64 NOT NULL PRIMARY KEY,
  cluster_name STRING NOT NULL,      -- "North American Deserts"
  zone_type STRING NOT NULL,         -- "BIOME"
  zone_class STRING,                 -- "Deserts & Xeric Shrublands"
  
  -- Cluster statistics
  num_zones INT64,                   -- How many zones in this cluster
  total_area_km2 FLOAT64,            -- Total area
  centroid GEOGRAPHY,                -- Geographic center
  bounding_box GEOGRAPHY,            -- Bounding rectangle
  
  -- Representative info
  sample_zones ARRAY<STRING>,        -- List of zone names (for display)
  
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ============================================================================
-- EXAMPLE: POPULATE WITH BIOME DATA
-- ============================================================================
/*
This would be run once to populate the schema with biome clusters:
*/

INSERT INTO treekipedia_zones
SELECT
  CONCAT('BIOME_', cluster_id, '_', ROW_NUMBER() OVER (PARTITION BY cluster_id)) as aoi_id,
  'BIOME' as zone_type,
  ECO_NAME as zone_name,
  BIOME_NAME as zone_class,
  cluster_id,
  cluster_name,
  TRUE as is_continuous,
  'WWF_Ecoregions' as source_dataset,
  ECO_ID as source_id,
  geometry,
  ST_CENTROID(geometry) as centroid,
  ST_AREA(geometry) / 1000000 as area_km2,  -- Convert m² to

> Jeremic:
km²
  'VECTOR' as data_type,
  NULL as resolution_meters,
  CURRENT_TIMESTAMP() as created_at,
  CURRENT_TIMESTAMP() as updated_at,
  'Initial import from WWF Ecoregions with cluster analysis' as processing_notes
FROM (
  -- This would be your cluster assignment query from before
  -- (The recursive CTE that assigns cluster_ids)
);

-- ============================================================================
-- EXAMPLE QUERIES USING THE SCHEMA
-- ============================================================================

-- Query 1: Find all zones in the North American desert cluster
SELECT 
  aoi_id,
  zone_name,
  area_km2
FROM treekipedia_zones
WHERE cluster_id = 1  -- North American Deserts
  AND zone_type = 'BIOME';

-- Query 2: Get species in a specific continuous region
SELECT 
  t.species,
  COUNT(*) as occurrences
FROM bigquery-public-data.gbif.occurrences o
JOIN treekipedia_zones z
  ON ST_CONTAINS(z.geometry, ST_GEOGPOINT(o.decimalLongitude, o.decimalLatitude))
WHERE z.cluster_id = 2  -- African Deserts
  AND z.zone_type = 'BIOME'
GROUP BY t.species
ORDER BY occurrences DESC;

-- Query 3: Find which cluster a clicked point belongs to
SELECT 
  cluster_id,
  cluster_name,
  zone_name
FROM treekipedia_zones
WHERE ST_CONTAINS(geometry, ST_GEOGPOINT(-110.0, 32.0))  -- User click
  AND zone_type = 'BIOME'
LIMIT 1;

/*
BENEFITS OF THIS SCHEMA:

1. PERFORMANCE: No need to calculate connectivity on every query
2. CONSISTENCY: Same structure for biomes, land types, climate zones, etc.
3. SCALABILITY: Can add new zone types without changing query logic
4. CLARITY: Clear AOI_IDs make it easy to reference zones
5. FLEXIBILITY: Works with both vector and raster data

ADDRESSING DJIMO'S CONCERNS:

Vector Data: ✅ Handled with polygon geometry
Raster Data: ✅ Can store pixel-level zones with resolution_meters field
Multiple Datasets: ✅ zone_type field distinguishes them
Master ID: ✅ aoi_id is the universal identifier
Scalability: ✅ Schema designed to accommodate any environmental dataset
*/
