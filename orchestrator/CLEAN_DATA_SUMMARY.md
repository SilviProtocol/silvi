# AlphaEarth Clean Embeddings Data Summary
**Generated**: October 27, 2025
**Status**: Active deduplication and production run in progress

---

## Deduplication Complete ✅

Created clean table: `treekipedia-476404:alphaearth.occ_embeddings_clean`

### Before vs After Deduplication

| Species | Raw Count | Duplicates | Clean Count | Reduction |
|---------|-----------|------------|-------------|-----------|
| Castanea sativa | 75,302 | 53,041 | **22,261** | 70.4% removed |
| Acacia pycnantha | 2,853 | 54 | **2,799** | 1.9% removed |
| Acacia cyclops | 2,066 | 6 | **2,060** | 0.3% removed |
| Eucalyptus obliqua | 1,614 | 394 | **1,220** | 24.4% removed |
| Acacia decurrens | 1,011 | 78 | **933** | 7.7% removed |
| Acacia floribunda | 1,082 | 594 | **488** | 54.9% removed |
| Quercus rotundifolia | 390 | 1 | **389** | 0.3% removed |

**Total in clean table**: ~32,000 unique embeddings (and growing as production continues)

---

## Production Run Status

**Current Progress**: 90/100 species completed (90%)
**Running Time**: ~6 hours
**Estimated Completion**: ~30-60 minutes remaining

### Key Metrics
- **Castanea sativa dominates**: 22,261 embeddings (69% of current clean data)
- **All 69,651 Castanea occurrences processed** (no 5k limit!)
- **Deduplication critical**: Removed 53,041 duplicate Castanea records from debugging

---

## Data Quality Assurance

### Deduplication Method
```sql
-- Partition by unique location + year, keep only one embedding per unique point
ROW_NUMBER() OVER (
  PARTITION BY taxon_id, CAST(latitude AS STRING), CAST(longitude AS STRING), orig_year
  ORDER BY emb_year DESC
)
```

### Clean Table Schema
- **Columns**: taxon_id, latitude, longitude, orig_year, emb_year, A00-A63 (64-D embeddings), geo (geometry)
- **No duplicates**: Each (taxon, lat, lon, year) tuple appears exactly once
- **Verified**: No null embeddings, values in valid range (-0.25 to +0.25)

---

## Next Steps After Production Completes

1. **Final deduplication** on complete raw table (after all 100 species)
2. **K-prototypes clustering** per Builder's Guide:
   - k=1 for <50 points
   - k=2 for 50-100 points
   - k=3 for 100-500 points
   - k=4 for 500-1000 points
   - k=5 for >1000 points
3. **Compute centroid statistics**:
   - Mean centroid vector (64-D)
   - Spherical variance (r, q10, q50, q90)
   - Confidence metrics
4. **Store in PostgreSQL** for Treekipedia integration

---

## Data Governance

### Tables
- **Raw table**: `occ_embeddings_raw` - Contains duplicates from debugging
- **Clean table**: `occ_embeddings_clean` - Deduplicated, production-ready
- **Future**: `species_prototypes` - K-means centroids and statistics

### Monitoring Query
```sql
-- Check clean data growth
SELECT
  COUNT(DISTINCT taxon_id) as species_count,
  COUNT(*) as total_embeddings,
  ROUND(AVG(A00), 4) as avg_a00_check
FROM `treekipedia-476404.alphaearth.occ_embeddings_clean`
```

---

**Document maintained by**: Production pipeline
**Auto-updates**: After production completes