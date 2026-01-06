# Unified Zone Schema - Treekipedia Zones

**Status**: PLANNING
**Priority**: FUTURE
**Author**: Jeremic (schema design), Implementation TBD
**Related**: CONTEXT.md (original schema proposal)

---

## Overview

A unified schema for all environmental/geographic zones in Treekipedia. This architecture allows ANY environmental dataset (biomes, ecoregions, land types, climate zones, etc.) to be queried consistently with **pre-computed connectivity**.

**Key Innovation**: Solves the "continuous boundary problem" by pre-computing zone adjacency and clustering fragmented but logically connected regions (e.g., all North American desert zones grouped under one cluster_id).

---

## Problem Statement

Current architecture uses separate tables:
- `wwf_ecoregions` - 847 ecoregions with geometries
- `geohash_species_tiles` - 5.3M tiles with eco_id references
- Country polygons in `countries` table

**Limitations**:
1. No unified query interface across zone types
2. Connectivity between zones not pre-computed
3. Cannot easily add new zone datasets (climate zones, land cover, etc.)
4. Fragmented zones (e.g., desert patches) not grouped logically

---

## Proposed Schema

### Master Zone Table

```sql
CREATE TABLE treekipedia_zones (
  -- MASTER IDENTIFIER
  aoi_id TEXT NOT NULL PRIMARY KEY,  -- Format: "BIOME_NA_DESERT_001" or "ECO_SAHARA_042"

  -- ZONE CLASSIFICATION
  zone_type TEXT NOT NULL,           -- "BIOME", "ECOREGION", "LAND_TYPE", "CLIMATE_ZONE"
  zone_name TEXT NOT NULL,           -- Human-readable: "Sonoran Desert"
  zone_class TEXT,                   -- Classification: "Deserts & Xeric Shrublands"

  -- CONNECTIVITY (Key to solving continuous boundary problem)
  cluster_id INTEGER NOT NULL,       -- Which connected group does this belong to?
  cluster_name TEXT,                 -- "North American Deserts", "Sahara Desert Complex"
  is_continuous BOOLEAN,             -- Is this part of a continuous region?

  -- ORIGINAL SOURCE DATA
  source_dataset TEXT,               -- "WWF_Ecoregions", "ESA_CCI_LandCover", etc.
  source_id TEXT,                    -- Original ID from source (e.g., ECO_ID)

  -- GEOGRAPHY
  geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
  centroid GEOMETRY(Point, 4326),
  area_km2 FLOAT,

  -- DATA TYPE (Vector vs Raster)
  data_type TEXT,                    -- "VECTOR" or "RASTER"
  resolution_meters FLOAT,           -- For raster data, pixel size

  -- METADATA
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  processing_notes TEXT
);

-- Spatial index
CREATE INDEX idx_zones_geometry ON treekipedia_zones USING GIST(geometry);
CREATE INDEX idx_zones_cluster ON treekipedia_zones(cluster_id);
CREATE INDEX idx_zones_type ON treekipedia_zones(zone_type);
```

### Zone Connectivity Table

Pre-computed adjacency graph showing which zones touch each other:

```sql
CREATE TABLE zone_connectivity (
  aoi_id_a TEXT NOT NULL,
  aoi_id_b TEXT NOT NULL,
  cluster_id INTEGER NOT NULL,

  -- Connectivity metrics
  shared_boundary_length_km FLOAT,
  connectivity_type TEXT,            -- "DIRECT_TOUCH", "CLOSE_PROXIMITY"

  PRIMARY KEY (aoi_id_a, aoi_id_b)
);

CREATE INDEX idx_connectivity_cluster ON zone_connectivity(cluster_id);
```

### Cluster Summary Table

```sql
CREATE TABLE zone_clusters (
  cluster_id INTEGER NOT NULL PRIMARY KEY,
  cluster_name TEXT NOT NULL,
  zone_type TEXT NOT NULL,
  zone_class TEXT,

  -- Cluster statistics
  num_zones INTEGER,
  total_area_km2 FLOAT,
  centroid GEOMETRY(Point, 4326),
  bounding_box GEOMETRY(Polygon, 4326),

  -- Representative info
  sample_zones TEXT[],               -- Array of zone names for display

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Use Cases

### 1. Find All Zones in a Cluster

```sql
-- All zones in North American Deserts cluster
SELECT aoi_id, zone_name, area_km2
FROM treekipedia_zones
WHERE cluster_id = 1
  AND zone_type = 'BIOME';
```

### 2. Species in Continuous Region

```sql
-- Species across all connected African desert zones
SELECT s.scientific_name, COUNT(*) as occurrences
FROM geohash_species_tiles gst
JOIN treekipedia_zones z ON ST_Contains(z.geometry, gst.geom)
JOIN species s ON s.taxon_id = ANY(array_keys(gst.species_data::jsonb))
WHERE z.cluster_id = 2  -- African Deserts
  AND z.zone_type = 'BIOME'
GROUP BY s.scientific_name
ORDER BY occurrences DESC;
```

### 3. Point-to-Cluster Resolution

```sql
-- Find which cluster a user click belongs to
SELECT cluster_id, cluster_name, zone_name
FROM treekipedia_zones
WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(-110.0, 32.0), 4326))
  AND zone_type = 'BIOME'
LIMIT 1;
```

### 4. Cross-Dataset Queries

```sql
-- Find overlap between biome and climate zone
SELECT
  b.zone_name as biome,
  c.zone_name as climate_zone,
  ST_Area(ST_Intersection(b.geometry, c.geometry)::geography) / 1e6 as overlap_km2
FROM treekipedia_zones b
JOIN treekipedia_zones c ON ST_Intersects(b.geometry, c.geometry)
WHERE b.zone_type = 'BIOME'
  AND c.zone_type = 'CLIMATE_ZONE';
```

---

## Implementation Phases

### Phase 1: Schema Creation & WWF Migration
- [ ] Create treekipedia_zones table
- [ ] Create zone_connectivity table
- [ ] Create zone_clusters table
- [ ] Migrate existing 847 WWF ecoregions into unified schema
- [ ] Preserve existing eco_id mappings for backward compatibility

### Phase 2: Cluster Computation
- [ ] Implement cluster assignment algorithm (recursive CTE or graph algorithm)
- [ ] Compute connectivity for all WWF ecoregions
- [ ] Generate cluster summaries
- [ ] Validate clusters against known ecological regions

### Phase 3: API Integration
- [ ] Update geospatial controller to query unified schema
- [ ] Add cluster-aware LEAF scoring option
- [ ] Create new endpoints for cluster queries
- [ ] Maintain backward compatibility with eco_id queries

### Phase 4: Additional Datasets
- [ ] Import ESA CCI Land Cover as LAND_TYPE zones
- [ ] Import Köppen-Geiger climate zones as CLIMATE_ZONE zones
- [ ] Compute cross-dataset clusters
- [ ] Enable multi-layer queries

---

## Benefits

| Benefit | Description |
|---------|-------------|
| **Performance** | No need to calculate connectivity on every query |
| **Consistency** | Same query structure for biomes, land types, climate zones |
| **Scalability** | Add new zone types without changing query logic |
| **Clarity** | Universal aoi_id makes zone references unambiguous |
| **Flexibility** | Works with both vector and raster data |

---

## Migration Considerations

### Backward Compatibility
- Keep existing `wwf_ecoregions` table or create view
- Maintain `eco_id` references in `geohash_species_tiles`
- API endpoints continue accepting eco_id, resolve internally to aoi_id

### Data Mapping

| Current | Unified Schema |
|---------|----------------|
| `wwf_ecoregions.eco_id` | `treekipedia_zones.source_id` WHERE `zone_type = 'ECOREGION'` |
| `wwf_ecoregions.eco_name` | `treekipedia_zones.zone_name` |
| `wwf_ecoregions.biome_name` | `treekipedia_zones.zone_class` |
| `wwf_ecoregions.geom` | `treekipedia_zones.geometry` |

### New Identifier Format

```
aoi_id format: {TYPE}_{REGION}_{SEQUENCE}

Examples:
- ECO_APPALACHIAN_001    (Appalachian-Blue Ridge forests)
- BIOME_TEMPERATE_BF_001 (Temperate Broadleaf & Mixed Forests)
- LAND_FOREST_NA_042     (Forest land cover patch in North America)
- CLIMATE_CFA_001        (Köppen Cfa humid subtropical)
```

---

## Technical Requirements

### Database
- PostgreSQL 14+ with PostGIS 3.2+
- Sufficient storage for additional geometries (~10-50GB depending on datasets)
- Memory for cluster computation (8GB+ recommended)

### Processing
- Cluster computation may require graph database or recursive CTEs
- Consider Blazegraph for connectivity graph if PostgreSQL performance insufficient
- Batch processing for initial cluster assignment

---

## Open Questions

1. **BigQuery vs PostgreSQL**: Original schema uses BigQuery types. Do we migrate to BigQuery or adapt for PostgreSQL?
2. **Raster data handling**: How to represent pixel-level zones efficiently?
3. **Cluster granularity**: What defines "continuous" - direct touch only or proximity threshold?
4. **Update frequency**: How often to recompute clusters when data changes?

---

## Related Documentation

- **CONTEXT.md** - Original schema proposal from Jeremic
- **docs/todo/LEAF.md** - LEAF scoring (would benefit from cluster-aware queries)
- **database/03_ecoregions_integration.sql** - Current ecoregions implementation
- **TODO.md** - Master task tracking

---

**Document Version**: 1.0
**Created**: December 2025
**Status**: Planning

**When complete**: Move to `docs/completed/` and update CHANGELOG.md
