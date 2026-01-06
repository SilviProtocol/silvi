# AlphaEarth Embedding Extraction - Status Report
**Date**: October 27, 2025
**Status**: Single-Species Test In Progress

---

## Current Status: TESTING PHASE ✅

### Completed ✓
1. **GEE AlphaEarth Sampling Fixed** - Discovered critical `.mosaic()` requirement
2. **BigQuery Export Working** - Successfully exported test embedding (Google HQ)
3. **GBIF Data Integration** - 100 species, 95,934 occurrences with ≤10m GPS precision
4. **Single-Point Test** - Verified end-to-end pipeline works (GEE → BigQuery)

### In Progress ⏳
- **Acacia pycnantha Test** (100 points) - Running in background
- Validating full pipeline with realistic data volume

### Next Steps
1. Verify Acacia test completes successfully
2. Query BigQuery to confirm 100 embeddings were extracted
3. Run full 100-species extraction (~95,934 points)
4. Implement k-prototypes clustering
5. Store centroids in PostgreSQL

---

## Critical Technical Discovery: The `.mosaic()` Fix

### Problem
AlphaEarth collection has ~11,074 tiles per year (globally distributed). Using `.first()` or individual tiles resulted in:
```
❌ Error: FeatureCollection is empty - No export data provided
```

### Root Cause
Individual AlphaEarth tiles don't cover all geographic locations. Sampling from a single tile returns empty results for coordinates outside that tile's coverage area.

### Solution
**Use `.mosaic()` to combine all tiles into a single global image before sampling:**

```python
def ae_image_for_year_FIXED(year: int) -> ee.Image:
    """
    Get AlphaEarth mosaic image for a given year.

    CRITICAL FIX: Use .mosaic() to combine all ~11K tiles into single global image.
    Without mosaic(), individual tiles have gaps and sampling returns empty results.
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )

    # CRITICAL: Use .mosaic() to combine all tiles
    mosaic_img = col.mosaic()

    return mosaic_img
```

### Verification
**Test Point**: Google HQ (37.422°, -122.0841°) - 2023

**Result** (from BigQuery):
```
taxon_id: TEST-FINAL
emb_year: 2023
A00: 0.160000
A01: -0.236463
A02: 0.172795
A03: -0.093564
A04: 0.059116
A05: -0.147697
... (64 dimensions total)
```

✅ **Embeddings successfully extracted and stored in BigQuery!**

---

## Architecture Overview

```
GBIF Parquet (local)
    ↓ read occurrences
Python Orchestrator (run_pilot.py)
    ↓ submit coordinates + years
Google Earth Engine (AlphaEarth V1 - ANNUAL)
    ↓ mosaic tiles, sample at 10m, export
BigQuery (occ_embeddings_raw table)
    ↓ query embeddings per species
Python (k-means clustering, k=1-5)
    ↓ compute centroids + spherical stats
PostgreSQL (final prototype storage)
```

---

## Data Specifications

### GBIF Occurrence Data
- **File**: `orchestrator/gbif_data/gbif_occurrences_top100_gps.parquet`
- **Species**: 100 (across 5 families: Fabaceae, Myrtaceae, Fagaceae, Salicaceae, Pinaceae)
- **Occurrences**: 95,934 (all with ≤10m GPS precision)
- **Temporal Coverage**: 2017-2024 (perfect alignment with AlphaEarth)
- **Schema**:
  - `taxon_id` (STRING): Treekipedia species ID
  - `species` (STRING): Scientific name with author (e.g., "Acacia pycnantha Benth.")
  - `family` (STRING): Taxonomic family
  - `latitude` (FLOAT): Decimal latitude
  - `longitude` (FLOAT): Decimal longitude
  - `year` (INTEGER): Collection year (2017-2024)
  - `gbif_id` (STRING): GBIF occurrence ID

### AlphaEarth Collection
- **GEE Collection**: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- **Bands**: A00-A63 (64-dimensional embeddings)
- **Resolution**: 10m
- **Temporal Coverage**: 2017-2024 (annual composites)
- **Tiles Per Year**: ~11,074 globally
- **Projection**: EPSG:4326 (WGS84)

### BigQuery Schema
- **Project**: `treekipedia-476404`
- **Dataset**: `alphaearth`
- **Table**: `occ_embeddings_raw`
- **Schema**:
  - `taxon_id` (STRING)
  - `emb_year` (INTEGER) - Embedding year used
  - `orig_year` (INTEGER) - Original occurrence year
  - `latitude` (FLOAT)
  - `longitude` (FLOAT)
  - `A00` through `A63` (FLOAT) - 64 embedding dimensions

---

## GEE Quota Management

### Implemented Strategy
- **Dynamic Concurrency**: 2-8 tasks based on quota availability
- **Adaptive Batch Sizing**: 500-5000 points per task
- **Quota Monitoring**: Track requests/second and compute units
- **Backoff Logic**: Reduce concurrency when quota limits approached

### Current Configuration
```python
# gee_sampler_FINAL.py
export_batch_to_bigquery(
    batch_id='acacia_test_20251027',
    points=occurrences,  # 100 points
    batch_size=2000      # Comfortable within quota
)
```

### Estimated Throughput
- **100 species pilot**: ~95,934 points
- **Estimated tasks**: ~50 tasks (at 2000 points/task)
- **Expected duration**: 3-6 hours (with 30s polling)
- **GEE quota usage**: ~96K API calls (well within 5M/month free tier)

---

## File References

### Core Scripts
1. **[gee_sampler_FINAL.py](gee_sampler_FINAL.py)** - GEE sampler with `.mosaic()` fix
   - `ae_image_for_year_FIXED()` - Critical mosaic function
   - `export_batch_to_bigquery()` - Export embeddings to BigQuery
   - `wait_for_tasks()` - Task monitoring with status updates

2. **[run_pilot.py](run_pilot.py)** - Main orchestrator for 100-species extraction
   - Reads GBIF parquet
   - Submits batches to GEE
   - Tracks progress with checkpoints

3. **[test_acacia_full.py](test_acacia_full.py)** - Single-species test (100 points)
   - Validates full pipeline before large-scale run

### Data Files
- `gbif_data/gbif_occurrences_top100_gps.parquet` - GBIF occurrence data
- `checkpoints.json` - Orchestrator progress tracking (created on first run)

### Documentation
- `GBIF_INTEGRATION_COMPLETE.md` - GBIF data collection summary
- `GBIF_TOP100_SPECIES_REPORT.md` - Detailed species breakdown

---

## Known Issues & Solutions

### Issue 1: BigQuery "table already exists" error
**Problem**: GEE fails with "table already exists" even when using `WRITE_APPEND`

**Solution**: Delete table before first run, then WRITE_APPEND works
```bash
bq rm -f treekipedia-476404:alphaearth.occ_embeddings_raw
```

**Root Cause**: GEE's WRITE_APPEND requires table to not exist on first export (unclear from docs)

### Issue 2: FeatureCollection is empty
**Problem**: All GEE sampling returned empty results

**Solution**: Use `.mosaic()` to combine ~11K tiles before sampling (see Critical Technical Discovery above)

### Issue 3: Species names include author names
**Problem**: Filtering by "Acacia pycnantha" failed because GBIF has "Acacia pycnantha Benth."

**Solution**: Use string contains for species matching
```python
df[df['species'].str.contains('Acacia pycnantha', case=False, na=False)]
```

---

## Testing Results

### Test 1: Google HQ Single Point ✅ SUCCESS
- **Location**: 37.422°, -122.0841°
- **Year**: 2023
- **Result**: 64-D embedding successfully extracted and stored in BigQuery
- **Verification**: Queried BigQuery, confirmed all bands (A00-A63) have non-null values

### Test 2: Acacia pycnantha (100 points) ⏳ IN PROGRESS
- **Species**: Acacia pycnantha Benth. (Golden wattle)
- **Taxon ID**: AngMaFaFbCx09400-00
- **Occurrences Sampled**: 100 (from 2,853 total)
- **Temporal Distribution**: 2017-2024 (8 years represented)
- **Status**: GEE task submitted, waiting for completion

---

## Next Actions

### Immediate (After Acacia Test Completes)
1. Query BigQuery to verify 100 embeddings exist:
   ```sql
   SELECT COUNT(*) FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`
   WHERE taxon_id = 'AngMaFaFbCx09400-00';
   ```

2. Verify embedding quality (check for null values, reasonable ranges):
   ```sql
   SELECT
     AVG(A00) as avg_A00, MIN(A00) as min_A00, MAX(A00) as max_A00,
     COUNT(CASE WHEN A00 IS NULL THEN 1 END) as null_count
   FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`;
   ```

### Short Term (This Week)
1. Run full 100-species extraction with `run_pilot.py`
2. Monitor GEE quota usage and adjust concurrency as needed
3. Verify all 95,934 embeddings extracted successfully

### Medium Term (Next 2 Weeks)
1. Implement k-prototypes clustering script:
   - Query BigQuery for each species
   - Run k-means (k=1-5 based on sample size)
   - Compute spherical statistics (r, q10/q50/q90)
   - Store centroids + metadata in PostgreSQL

2. Validate prototypes:
   - Visualize centroid distributions
   - Check spherical variance values
   - Ensure prototypes represent species niche

3. Integrate with Treekipedia API:
   - Add endpoint to serve AlphaEarth prototypes
   - Enable species niche similarity queries

---

## Performance Metrics (Estimated)

### Single Point Test (Google HQ)
- **Submission Time**: < 1 second
- **GEE Processing Time**: ~30 seconds
- **Total Time**: ~45 seconds (including polling)

### 100-Point Test (Acacia pycnantha)
- **Submission Time**: ~2 seconds
- **GEE Processing Time**: ~60-90 seconds (estimated)
- **Total Time**: ~2-3 minutes (including polling)

### Full 100-Species Extraction (95,934 points)
- **Tasks**: ~50 tasks at 2000 points each
- **Sequential Processing**: ~3-6 hours (with 30s polling)
- **Parallel Optimization Potential**: 2-4 hours (with dynamic concurrency)
- **BigQuery Storage**: ~20-30GB for raw embeddings

---

## Resources

**Google Cloud Project**: `treekipedia-476404`
- GEE Free Tier: 5M requests/month, 250K concurrent requests
- BigQuery Free Tier: 10GB storage, 1TB queries/month

**External Resources**:
- [AlphaEarth GEE Collection](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
- [GBIF Data Portal](https://www.gbif.org/)
- [Treekipedia Documentation](./.claude/CLAUDE.md)

---

## Status Summary

| Component | Status | Details |
|-----------|--------|---------|
| GBIF Data | ✅ Complete | 100 species, 95,934 occurrences |
| GEE Sampler | ✅ Working | `.mosaic()` fix implemented |
| BigQuery Export | ✅ Tested | Single-point test successful |
| 100-Point Test | ⏳ Running | Acacia pycnantha in progress |
| Full Extraction | ⏳ Pending | Ready to run after validation |
| K-Prototypes | ❌ Not Started | Next phase after extraction |
| PostgreSQL Integration | ❌ Not Started | Final phase |

---

**Document Created**: October 27, 2025
**Last Updated**: October 27, 2025 (05:30 UTC)
**Status**: Actively Testing
