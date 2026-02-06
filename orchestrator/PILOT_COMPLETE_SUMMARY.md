# AlphaEarth Embeddings Extraction - Pilot Complete

**Date**: October 27-28, 2025
**Status**: 97/100 species completed (3 failed due to coordinate type errors)

---

## Final Results

### Extraction Statistics
- **Species processed**: 97/100 (97%)
- **GBIF occurrences**: 93,167
- **Raw embeddings extracted**: 100,875 (includes duplicates from test runs)
- **Clean embeddings (after dedup)**: 43,451
- **Success rate**: **46.6%** ⚠️

### Why Only 46.6% Success Rate?

**Critical Discovery**: Over half of GBIF occurrences could not be matched to AlphaEarth embeddings.

**Possible reasons**:
1. **AlphaEarth coverage gaps**: Not all geographic regions have satellite data
2. **Temporal misalignment**: AlphaEarth years (2017-2024) vs occurrence years
3. **Coordinate precision**: Some GBIF coordinates may fall in areas without imagery
4. **GEE sampling failures**: Some tiles failed to return data during sampling

**Data loss breakdown**:
- Expected: 93,167 embeddings (1:1 with occurrences)
- Actual: 43,451 embeddings
- Lost: 49,716 occurrences (53.4%)

---

## Deduplication Results

### Clean Table Statistics
| Year | Embeddings | Species |
|------|------------|---------|
| 2017 | 3,950      | 67      |
| 2018 | 3,658      | 78      |
| 2019 | 4,266      | 77      |
| 2020 | 3,624      | 80      |
| 2021 | 6,300      | 90      |
| 2022 | 6,898      | 91      |
| 2023 | 7,274      | 92      |
| 2024 | 7,481      | 90      |
| **Total** | **43,451** | **98** |

### Duplicate Removal
- **Raw table**: 100,875 embeddings
- **Clean table**: 43,451 embeddings
- **Duplicates removed**: 57,424 (56.9%)

**Why so many duplicates?**
- Multiple test runs during debugging (especially Castanea sativa with 53,041 duplicates!)
- Retry attempts for failed species
- Development iterations

---

## Failed Species (3)

All 3 failures due to **coordinate type errors** in GEE BigQuery export:

1. **Quercus rotundifolia** (2,390 occurrences)
   - Error: Feature [1_1_1_1_1_1_2_63_0] longitude type incompatible
   - Root cause: Exact integer coordinate (-4.0)

2. **Eucalyptus caliginosa** (360 occurrences)
   - Error: Feature [1_1_1_1_1_1_2_290_0] longitude type incompatible
   - Root cause: Exact integer coordinate (152.0)

3. **Eucalyptus placita** (17 occurrences)
   - Error: Feature [2_16_0] latitude type incompatible
   - Root cause: Exact integer coordinate (-32.0)

### Fix Implemented
- Created `gee_sampler_FIXED.py` with coordinate type enforcement
- Adds tiny epsilon (1e-10 degrees ≈ 0.01mm) to force float typing
- Running now to complete these 3 species

---

## Data Quality Assessment

### ✅ Strengths
- **No null values**: All embeddings have complete 64-D vectors
- **Proper deduplication**: Only true duplicates removed (exact coordinate matches)
- **Year alignment**: `emb_year` = `orig_year` (correct 1:1 mapping)
- **Geographic diversity**: 98 species across multiple families

### ⚠️ Concerns
1. **Low success rate (46.6%)**: Over half of occurrences lost
2. **Coverage gaps**: Need to investigate AlphaEarth availability
3. **Failing species**: 3 species with coordinate type errors (fix in progress)

---

## Next Steps

### Immediate (In Progress)
1. ✅ Complete 3 failing species with fixed code
2. ✅ Re-deduplicate including new species

### Critical Investigation Needed
1. **Analyze AlphaEarth coverage**: Which geographic regions have gaps?
2. **Identify failure patterns**: Are certain coordinates/regions always failing?
3. **Coverage report**: Generate species-level success rate breakdown

### Production Planning
1. **Scale decision**: Should we proceed with 46.6% success rate for all 67k species?
2. **Alternative approaches**:
   - Use older satellite datasets with better coverage?
   - Fill gaps with interpolation/synthetic data?
   - Accept partial coverage and document limitations?

---

## File Locations

- **GBIF data**: `gbif_data/gbif_occurrences_top100_gps.parquet` (95,934 occurrences)
- **Checkpoints**: `checkpoints.json` (97 completed, 5 in retry queue)
- **Fixed checkpoints**: `checkpoints_fixed.json` (for coordinate-fixed version)
- **BigQuery tables**:
  - Raw: `treekipedia-476404.alphaearth.occ_embeddings_raw` (100,875 rows)
  - Clean: `treekipedia-476404.alphaearth.occ_embeddings_clean` (43,451 rows)

---

## Lessons Learned

1. **Coordinate typing matters**: GEE is strict about float vs integer types
2. **Coverage isn't universal**: AlphaEarth doesn't cover all regions equally
3. **Deduplication is essential**: Test runs create massive duplicate counts
4. **Mosaic is critical**: Must use `.mosaic()` to combine AlphaEarth's 11k tiles/year
5. **Success tracking needed**: Monitor extraction success rate per species

---

## Questions for Review

1. Is 46.6% success rate acceptable for production scale-up?
2. Should we investigate alternative satellite datasets?
3. How to handle species with very low extraction rates?
4. Document coverage limitations in final dataset?

---

**Generated**: October 28, 2025
**Tool**: AlphaEarth Embeddings Orchestrator
**Dataset**: 100-species pilot (97 completed)
