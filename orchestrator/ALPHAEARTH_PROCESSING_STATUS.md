# AlphaEarth Processing Status & Strategy

**Last Updated**: January 20, 2026
**Project**: treekipedia-476404 (billing disabled after ~$300 spend)

---

## Current Data Status

### BigQuery Tables Exported (Local Parquet Files)

| Table | Rows | Size | Description |
|-------|------|------|-------------|
| **v2** | 1,691,022 | 165 MB | AlphaEarth + Hansen (NO elevation) |
| **v3** | 1,253,973 | 126 MB | AlphaEarth + Hansen + SRTM elevation |
| **elev** | 1,526,000 | 42 MB | Elevation backfill only |

**Location**: `orchestrator/bigquery_exports/`

### Data Quality Issues

1. **2024 Test Data** (5,001 rows in v2): Test run before main processing. **DELETE when re-uploading.**
2. **2019-2023 Contamination** (60 rows in v2): Unknown bug. **DELETE when re-uploading.**

Filter when uploading to new BigQuery:
```sql
WHERE emb_year IN (2017, 2018)
```

### Coverage by Year

| Year | Input Occurrences | Processed | Coverage |
|------|-------------------|-----------|----------|
| 2017 | 2,699,256 | 2,416,985 | **89.5%** |
| 2018 | 2,687,819 | 522,949 | **19.5%** |
| 2019 | 2,753,178 | 0 | 0% |
| 2020 | 2,791,104 | 0 | 0% |
| 2021 | 2,596,410 | 0 | 0% |
| 2022 | 2,105,590 | 0 | 0% |
| 2023 | 664,378 | 0 | 0% |
| 2024 | 164,369 | 0 | 0% |
| **Total** | **16,462,104** | **2,939,934** | **17.9%** |

### What We Have vs What We Need

- **Phase 1 Input**: 16.5M occurrence records (8.0M unique taxon+lat+lon combinations)
- **Processed**: 2.9M rows with embeddings
- **Remaining**: ~13.5M occurrences need processing

---

## AlphaEarth Technical Details

### Resolution & Structure
- **Pixel Resolution**: 10m × 10m
- **Embedding Dimensions**: 64 floats per pixel
- **Tile Size**: 163,840m × 163,840m in UTM projection
- **Years Available**: 2017-2024 (separate embeddings per year)
- **Projection**: UTM zones (varies by location, NOT fixed lat/lon grid)

### Key Insight: Coordinates Are Input, Not Pixel Centers
GEE returns your **original input coordinates**, not the pixel center. Two points 5m apart:
- **Same embedding** if both fall in the same 10m pixel
- **Different embedding** if they straddle a pixel boundary

### Deduplication Strategy
Since pixel boundaries vary by UTM zone, exact deduplication requires:
1. Project lat/lon to UTM
2. Round to nearest 10m
3. Group by (pixel_center, year)
4. Sample once per unique pixel-year

**Simpler approach** (with small redundancy):
- Round coordinates to 4-5 decimal places (~1-10m precision)
- Accept ~5-10% redundancy at pixel boundaries
- Much simpler to implement

---

## Cost Analysis

### What We Spent
- **~$300** for ~2.9M processed rows
- **Cost per row**: ~$0.0001 (0.01 cents)

### Projected Full Cost (Naive)
- 16.5M total occurrences × $0.0001 = **~$1,650**

### With Deduplication
- 8.0M unique (taxon, lat, lon) combinations
- Further reduce by ~60-70% with pixel-level dedup
- Estimated unique pixels: **2-3M**
- Projected cost: **$200-400**

---

## Optimization Strategies

### 1. Pixel-Level Deduplication (HIGHEST IMPACT)
**Problem**: Multiple occurrences in same 10m pixel get same embedding.

**Solution**:
```python
# Round to ~10m precision (4 decimal places ≈ 11m)
df['lat_pixel'] = (df['latitude'] * 10000).round() / 10000
df['lon_pixel'] = (df['longitude'] * 10000).round() / 10000

# Get unique pixel-year combinations
unique_pixels = df.groupby(['lat_pixel', 'lon_pixel', 'year']).first()
```

**Impact**: 6-8x reduction in GEE requests

### 2. Batch Size Optimization
- Current: 2,000 points per GEE task
- GEE handles up to ~5,000-10,000 points efficiently
- Larger batches = fewer tasks = less overhead

**Recommendation**: Test with 5,000 points/task

### 3. Avoid Re-requesting Elevation/Hansen
- SRTM elevation: Static, same for all years
- Hansen forest data: Static (uses 2000 baseline + loss year)

**If we already have embeddings without elevation**:
- Don't re-request AlphaEarth
- Just backfill elevation separately (much cheaper)

### 4. Export to GCS Instead of BigQuery
- BigQuery export has per-row costs
- GCS export is just storage costs
- Can import to BigQuery later if needed

### 5. Process by Geographic Region
- AlphaEarth tiles are regional
- Processing spatially clustered points may be more efficient
- Reduces tile loading overhead

---

## Cost Breakdown (What Costs Money)

| Operation | Cost Driver | Notes |
|-----------|-------------|-------|
| **AlphaEarth sampling** | EECU compute | Main cost (~90%) |
| **Hansen sampling** | EECU compute | Cheap (30m resolution) |
| **SRTM elevation** | EECU compute | Very cheap |
| **BigQuery export** | Per-row + storage | Secondary cost |
| **GCS storage** | Per-GB | Minimal |

**Key insight**: Cost scales primarily with **number of AlphaEarth pixel samples**, not total rows or geographic coverage.

---

## Recommended Approach for Resume

### Phase 1: Prepare Deduplicated Input
```python
# Load Phase 1 input
phase1 = pd.read_parquet('alphaearth_extractions/alphaearth_phase1_*.parquet')

# Round to pixel precision
phase1['lat_pixel'] = (phase1['decimalLatitude'] * 10000).round() / 10000
phase1['lon_pixel'] = (phase1['decimalLongitude'] * 10000).round() / 10000

# Get unique pixel-year combinations (one sample per pixel per year)
deduped = phase1.groupby(['lat_pixel', 'lon_pixel', 'year']).agg({
    'taxon_id': 'first',  # Keep one taxon as reference
    'decimalLatitude': 'first',
    'decimalLongitude': 'first'
}).reset_index()

# This reduces 16.5M → ~2-3M requests
```

### Phase 2: Sample AlphaEarth for Unique Pixels
- Process deduplicated set
- Get one embedding per pixel-year

### Phase 3: Join Back to Full Dataset
```sql
-- After loading to BigQuery
SELECT
    occ.*,
    emb.* EXCEPT(lat_pixel, lon_pixel, year)
FROM occurrences occ
LEFT JOIN embeddings emb
ON ROUND(occ.latitude * 10000) / 10000 = emb.lat_pixel
   AND ROUND(occ.longitude * 10000) / 10000 = emb.lon_pixel
   AND occ.year = emb.year
```

---

## Files Reference

### Input Data
- `alphaearth_extractions/alphaearth_phase1_*.parquet` - 16.5M occurrences to process
- `alphaearth_extractions/alphaearth_phase2_*.parquet` - Additional phase 2 data

### Exported Embeddings
- `bigquery_exports/occ_embeddings_hansen_v2_chunk_*.parquet` - V2 (no elevation)
- `bigquery_exports/occ_embeddings_hansen_elev_v3_chunk_*.parquet` - V3 (with elevation)
- `bigquery_exports/occ_elevation_backfill_chunk_*.parquet` - Elevation only

### Bad Data (exclude when re-uploading)
- `bigquery_exports/BAD_DATA_2019_2023.csv` - 60 rows contamination
- `bigquery_exports/BAD_DATA_2024_test.csv` - 5,001 rows test data

### Processing Scripts
- `run_phase1_by_year.py` - Year-by-year GEE processing
- `backfill_elevation_v2.py` - Elevation-only backfill
- `export_bigquery_data.py` - BigQuery → local export

---

## Next Steps When Resuming

1. **Set up new Google Cloud project** with billing
2. **Upload clean parquet files** to new BigQuery (filter out bad data)
3. **Create deduplicated input** (~2-3M unique pixel-years vs 16.5M rows)
4. **Process remaining years** (2018-2024) with deduplication
5. **Join embeddings back** to full occurrence dataset

---

## 🚀 GAME CHANGER: AlphaEarth on GCS (Skip Earth Engine!)

**As of December 2025**, AlphaEarth embeddings are available as **Cloud Optimized GeoTIFFs (COGs) on Google Cloud Storage**, bypassing Earth Engine entirely!

### GCS Bucket Details
- **Bucket**: `gs://alphaearth_foundations`
- **License**: CC-BY 4.0
- **Pricing**: **Requester pays** (egress charges only, NO EECU costs!)
- **Years**: 2017-2024 (same as Earth Engine)

### File Structure
```
gs://alphaearth_foundations/
├── 2017/
│   ├── 01N/  (UTM zone 1, Northern hemisphere)
│   │   ├── *.tif (8192x8192 pixels, 64 bands each)
│   │   └── ...
│   ├── 01S/
│   └── ... (120 UTM zone directories)
├── 2018/
└── ...
```

### Key Technical Details
- **File size**: 8192 × 8192 pixels × 64 channels
- **Data type**: Signed 8-bit integers (-128 to 127)
- **Masked pixels**: -128
- **De-quantization formula**:
  ```python
  # Convert int8 to float embedding (-1 to 1)
  raw_value = pixel_value  # int8
  normalized = raw_value / 127.5
  embedding = sign(raw_value) * (normalized ** 2)
  ```

### Why This Changes Everything

| Approach | Cost Model | Estimated Cost for 3M pixels |
|----------|------------|------------------------------|
| **Earth Engine** | $0.40/EECU-hour (batch) | ~$200-400 |
| **GCS Direct** | ~$0.12/GB egress | **~$5-20** |

**GCS is 10-50x cheaper** because:
1. No EECU compute charges
2. COGs support range requests (read only the pixels you need)
3. No BigQuery export costs

### How It Works (NO full file download needed!)

**COGs support HTTP range requests** - rasterio/GDAL fetches only the bytes for your specific pixels:

```python
import rasterio
from rasterio.windows import Window
from pyproj import Transformer

# Open COG from GCS URL (doesn't download whole file!)
cog_url = "gs://alphaearth_foundations/2017/17N/tile_xxx.tif"

with rasterio.open(cog_url) as src:
    # Transform lat/lon to pixel coordinates
    transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    row, col = src.index(x, y)

    # Read ONLY this pixel (64 bands) via HTTP range request
    # This fetches ~256 bytes, NOT the whole file!
    window = Window(col, row, 1, 1)
    data = src.read(window=window)  # Shape: (64, 1, 1)

    # De-quantize int8 → float
    raw = data.flatten().astype(float)
    embedding = np.sign(raw) * (raw / 127.5) ** 2
```

**Key insight**: Reading 1000 pixels from a single COG might fetch only ~1MB total (vs downloading the entire ~500MB file).

### Optimal Batch Strategy

```python
# Group points by COG file, then batch read
points_by_cog = group_by_utm_zone_and_tile(all_points)

for cog_path, points in points_by_cog.items():
    with rasterio.open(cog_path) as src:  # Open once
        for point in points:
            read_pixel(src, point)  # Fast - file handle cached
```

### Index Files Available
- `manifest.json` - List of all COG files
- Geographic index in Parquet/GeoPackage/CSV formats

### Recommended New Approach

1. **Download index file** from GCS bucket
2. **Map occurrences to COG files** by UTM zone
3. **Batch-read pixels** from COGs (group by file for efficiency)
4. **No Earth Engine needed!**

---

## Questions to Resolve

1. ~~**Exact cost breakdown**: What % is AlphaEarth vs BigQuery vs other?~~ → GCS approach avoids EECU entirely
2. **GCS egress optimization**: Can we read multiple pixels per COG request?
3. **UTM zone handling**: Build robust lat/lon → UTM zone → COG file mapping
4. **Local caching**: Download frequently-used COGs to avoid repeated egress?
