# Geohash Occurrence Data Import System

**Status**: Planning
**Priority**: HIGH - Required for updated LEAF scoring and occurrence data
**Last Updated**: December 2025

---

## Overview

System for importing compressed geohash occurrence data into Treekipedia. Supports both full refresh (complete data replacement) and incremental updates (adding new occurrences to existing tiles).

**Current State**:
- 5.79M geohash tiles
- 94.4M total occurrences
- 5.62M tiles (97%) have ecoregion assignments
- Data is ~1 year outdated

**Target State**:
- ~104M+ occurrences (10M additional)
- New compression algorithm
- Updated species occurrence distributions

---

## Data Format

### Source CSV Format (Marina's Export)

```csv
geohash_l7,species_data,total_occurrences,species_count,geometry_wkt,center_point_wkt,datetime,data_source,processing_date,observation_start_date,observation_end_date,created_at,updated_at
```

**Key Difference**: `species_data` is JSON **array** format:
```json
[{"taxon_id": "AngMaMaMlVc34977-00", "count": 10}, {"taxon_id": "AngMaMyMlSt36770-00", "count": 2}]
```

### Target Database Format

`species_data` column expects JSONB **object** format:
```json
{"AngMaMaMlVc34977-00": 10, "AngMaMyMlSt36770-00": 2}
```

**Transformation Required**: Array → Object during import

### Additional Fields Available

The new CSV includes pre-computed geometry:
- `geometry_wkt` - Polygon WKT (e.g., `POLYGON((-84.004 10.430, ...))`)
- `center_point_wkt` - Point WKT (e.g., `POINT(-84.003 10.430)`)

These can be used directly via `ST_GeomFromText()` instead of computing from geohash.

---

## Import Scenarios

### Scenario 1: Full Refresh (Current Need)

Replace all existing occurrence data with new compressed data.

**Challenge**: Preserve ecoregion assignments (5.62M tiles computed via expensive spatial joins)

**Solution**: Cache and restore ecoregion mappings

```sql
-- Step 1: Cache ecoregion assignments (before import)
CREATE TABLE geohash_ecoregion_cache AS
SELECT geohash_l7, eco_id, eco_name, biome_name, realm
FROM geohash_species_tiles
WHERE eco_id IS NOT NULL;
-- Creates ~5.6M row lookup table

-- Step 2: Truncate main table
TRUNCATE geohash_species_tiles;

-- Step 3: Import new data (via Node.js script)

-- Step 4: Restore ecoregion assignments (fast index-based UPDATE)
UPDATE geohash_species_tiles g
SET
  eco_id = c.eco_id,
  eco_name = c.eco_name,
  biome_name = c.biome_name,
  realm = c.realm
FROM geohash_ecoregion_cache c
WHERE g.geohash_l7 = c.geohash_l7;

-- Step 5: Assign ecoregions to NEW tiles only (spatial query)
-- Only tiles not in cache need expensive spatial computation
UPDATE geohash_species_tiles g
SET
  eco_id = e.eco_id,
  eco_name = e.eco_name,
  biome_name = e.biome_name,
  realm = e.realm
FROM ecoregions e
WHERE g.eco_id IS NULL
  AND ST_Intersects(g.geometry, e.geom);

-- Step 6: Drop cache table
DROP TABLE geohash_ecoregion_cache;
```

**Benefits**:
- Clean slate with new compression algorithm
- Preserves 97% of ecoregion computation work
- Only new geohash locations need spatial queries

### Scenario 2: Incremental Updates (Future Need)

Add new occurrence data to existing tiles without full replacement.

**Challenge**: Merge species counts, don't replace them

**Example**:
```
Existing tile:  {"species_A": 10, "species_B": 5}
New data:       {"species_A": 3,  "species_C": 7}
─────────────────────────────────────────────────
Desired result: {"species_A": 13, "species_B": 5, "species_C": 7}
```

**Solution**: Custom JSONB merge function

```sql
CREATE OR REPLACE FUNCTION merge_species_data(existing JSONB, incoming JSONB)
RETURNS JSONB AS $$
DECLARE
  result JSONB := COALESCE(existing, '{}'::jsonb);
  key TEXT;
  val INTEGER;
BEGIN
  FOR key, val IN SELECT * FROM jsonb_each_text(incoming)
  LOOP
    IF result ? key THEN
      -- Key exists: add counts
      result := jsonb_set(
        result,
        ARRAY[key],
        to_jsonb((result->>key)::int + val::int)
      );
    ELSE
      -- New key: insert
      result := result || jsonb_build_object(key, val::int);
    END IF;
  END LOOP;
  RETURN result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Import Query with Merge**:
```sql
INSERT INTO geohash_species_tiles (
  geohash_l7, species_data, total_occurrences, species_count,
  geometry, center_point, datetime, data_source
)
VALUES ($1, $2, $3, $4, ST_GeomFromText($5, 4326), ST_GeomFromText($6, 4326), $7, $8)
ON CONFLICT (geohash_l7) DO UPDATE SET
  species_data = merge_species_data(
    geohash_species_tiles.species_data,
    EXCLUDED.species_data
  ),
  total_occurrences = geohash_species_tiles.total_occurrences + EXCLUDED.total_occurrences,
  species_count = (
    SELECT COUNT(DISTINCT key)
    FROM jsonb_object_keys(
      merge_species_data(geohash_species_tiles.species_data, EXCLUDED.species_data)
    ) AS key
  ),
  updated_at = NOW();
```

---

## Import Script Design

### Script: `scripts/import_geohash_csv_v2.js`

**Features**:
1. Stream parsing for large CSV files (handles multi-GB)
2. Transform array species_data → object format
3. Use pre-computed WKT geometry (skip PostGIS geohash computation)
4. Batch inserts (1,000 rows per transaction)
5. Progress logging
6. Validation: verify taxon_ids exist in species table
7. Mode flag: `--full-refresh` or `--incremental`

**Usage**:
```bash
# Full refresh (default for initial import)
node scripts/import_geohash_csv_v2.js data.csv --full-refresh

# Incremental update (future imports)
node scripts/import_geohash_csv_v2.js new_data.csv --incremental

# Dry run (validate without importing)
node scripts/import_geohash_csv_v2.js data.csv --dry-run
```

### Data Transformation

```javascript
// Transform array format to object format
function transformSpeciesData(arrayData) {
  const result = {};
  for (const item of arrayData) {
    result[item.taxon_id] = item.count;
  }
  return result;
}

// Example:
// Input:  [{"taxon_id": "ABC-00", "count": 5}, {"taxon_id": "DEF-00", "count": 3}]
// Output: {"ABC-00": 5, "DEF-00": 3}
```

### Validation

```javascript
// Validate taxon_ids against species table
async function validateTaxonIds(speciesData, speciesCache) {
  const unknownTaxons = [];
  for (const taxonId of Object.keys(speciesData)) {
    if (!speciesCache.has(taxonId)) {
      unknownTaxons.push(taxonId);
    }
  }
  return unknownTaxons;
}
```

---

## Implementation Tasks

### Phase 1: Full Refresh Import (Current)

- [ ] Create ecoregion cache backup SQL
- [ ] Write `import_geohash_csv_v2.js` with array→object transformation
- [ ] Add WKT geometry support (use pre-computed instead of ST_GeomFromGeoHash)
- [ ] Add taxon_id validation against species table
- [ ] Test on sample file (`test_tile_compressed.csv`)
- [ ] Run full import on production data
- [ ] Restore ecoregion assignments from cache
- [ ] Run spatial assignment for new tiles only
- [ ] Verify LEAF scoring still works
- [ ] Update ACTIVE.md with new occurrence counts

### Phase 2: Incremental Import Infrastructure (Future)

- [ ] Create `merge_species_data()` PostgreSQL function
- [ ] Add `--incremental` mode to import script
- [ ] Test merge logic with sample data
- [ ] Document incremental import workflow
- [ ] Add species_count recalculation after merge

### Phase 3: Monitoring & Validation

- [ ] Add import statistics logging
- [ ] Create data quality report (unknown taxon_ids, tile counts, etc.)
- [ ] Add rollback capability for failed imports

---

## Database Changes

### New Index (Recommended)

```sql
-- Speed up ecoregion cache restoration
CREATE INDEX IF NOT EXISTS idx_geohash_tiles_geohash_l7
ON geohash_species_tiles(geohash_l7);
-- Note: This should already exist as PRIMARY KEY
```

### Merge Function (For Future Incremental)

```sql
-- Install when incremental imports needed
CREATE OR REPLACE FUNCTION merge_species_data(existing JSONB, incoming JSONB)
RETURNS JSONB AS $$
-- See implementation above
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Import fails mid-way | Data inconsistency | Use transactions, batch commits |
| Ecoregion cache lost | Need to re-run spatial queries | Backup cache table before truncate |
| Unknown taxon_ids | Broken LEAF queries | Validate before import, log unknowns |
| Memory exhaustion | Script crash | Stream parsing, batch processing |
| Geometry mismatch | Spatial queries fail | Use provided WKT, verify SRID 4326 |

---

## Testing Plan

### Test File

`test_tile_compressed.csv` - Single tile sample:
- 1 tile (geohash: `d1u726y`)
- 482 species
- 2,835 occurrences
- Location: Costa Rica

### Test Steps

1. Import test file with dry-run
2. Verify transformation (array → object)
3. Verify geometry parsing (WKT)
4. Import to test database
5. Query tile via API
6. Verify LEAF scoring includes new tile

---

## Related Documentation

- **[LEAF.md](LEAF.md)** - LEAF scoring depends on this data
- **[../RECOMMENDATION_SERVICE.md](../RECOMMENDATION_SERVICE.md)** - Species recommendation specs
- **[../../API.md](../../API.md)** - Geospatial API endpoints
- **[../../database/02_create_geohash_tiles_table.sql](../../database/02_create_geohash_tiles_table.sql)** - Table schema

---

## File Reference

| File | Purpose |
|------|---------|
| `scripts/import_geohash_csv.js` | Existing importer (object format) |
| `scripts/import_geohash_csv_with_mapping.js` | Existing importer with taxon_id mapping |
| `scripts/import_geohash_csv_v2.js` | **NEW** - Array format support |
| `database/02_create_geohash_tiles_table.sql` | Table schema |
| `backend/controllers/geospatial.js` | Queries this data |

---

**Document Version**: 1.0
**Created**: December 2025
**Status**: Planning → Implementation
