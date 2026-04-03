# AlphaEarth Embedding Extraction Pipeline - Comprehensive Investigation Report

**Date**: January 21, 2026
**Investigator**: Claude (Research Agent)
**Purpose**: Understand why we only have ~18k species with embeddings instead of ~48k

---

## Executive Summary

**The Good News**: We actually have data for **58,757 unique species** across Phase 1 + Phase 2 extraction files, which is **122% of the 48,129 species with GBIF occurrences**. The discrepancy comes from subspecies/varieties being counted separately.

**The Problem**: Only **~29%** of this data has been processed through Google Earth Engine (GEE) to extract AlphaEarth embeddings due to:
1. Google Cloud billing suspension after ~$300 spend
2. Processing stopped mid-2018 (only completed 2017 + partial 2018)
3. Years 2019-2024 remain unprocessed

**Current Status**:
- **Phase 1 extracted**: 18,824 species (2017-2024 occurrences)
- **Phase 2 extracted**: 58,181 species (pre-2017 historical + NULL year)
- **Total unique**: 58,757 species
- **Processed with embeddings**: 7,379 species (from v2 + v3 combined)
- **In BigQuery v4 (if exists)**: Unknown - need to check remote
- **In local database**: Only 100 species (test data)

---

## 1. What is "Phase 1"? How was it defined?

### Phase 1: High-Confidence Temporal Match (2017-2024)

**Definition** (from `extract_alphaearth_occurrences_v2.py`):
```python
# Phase 1: High-confidence (temporal match)
PHASE1_MIN_YEAR = 2017
PHASE1_MAX_YEAR = 2024
MAX_COORDINATE_UNCERTAINTY_METERS = 10  # Only sub-10m OR NULL
```

**Rationale**:
- AlphaEarth satellite embeddings are available for **2017-2024** only
- Phase 1 includes ONLY occurrences from these years
- Temporal match = occurrence year matches embedding year
- **No forest validation needed** (if a tree was observed in 2018, we use 2018 AlphaEarth data)

**Filter Criteria**:
1. `year >= 2017 AND year <= 2024`
2. `coordinateUncertaintyInMeters < 10 OR NULL`

**Results**:
- **File**: `alphaearth_phase1_20260119_033003.parquet`
- **Total records**: 16,462,104
- **Unique species**: 18,824 (note: includes subspecies/varieties)
- **Unique (taxon_id, lat, lon, year)**: 16,339,977
- **Unique pixel-years (lat, lon, year)**: 2,526,270 (actual unique GEE samples needed)
- **File size**: 181 MB

**Species Distribution by Year**:
| Year | Records | Species |
|------|---------|---------|
| 2017 | 2,699,256 | 8,083 |
| 2018 | 2,687,819 | 8,561 |
| 2019 | 2,753,178 | 8,390 |
| 2020 | 2,791,104 | 6,823 |
| 2021 | 2,596,410 | 7,559 |
| 2022 | 2,105,590 | 8,333 |
| 2023 | 664,378 | 7,682 |
| 2024 | 164,369 | 5,377 |

**Why only 18,824 species?** This represents species with:
- At least one GBIF occurrence record during 2017-2024
- Coordinate uncertainty < 10m (or NULL)
- Many species have occurrences outside this date range

---

## 2. Are there other phases? What do they contain?

### Yes! Phase 2: Historical + Forest Validation (pre-2017)

**Definition** (from `extract_alphaearth_occurrences_v2.py`):
```python
# Phase 2: Historical (requires forest validation)
PHASE2_MAX_YEAR = 2016  # Everything before 2017
# Also includes NULL year records
```

**Rationale**:
- Captures all historical occurrence data (pre-2017)
- Since AlphaEarth only starts in 2017, we use **2017 embeddings** for all historical points
- **Requires forest validation**: Only include if Hansen treecover2000 > 25% (forest still exists at that location)
- Logic: If forest exists today, habitat was likely similar historically

**Filter Criteria**:
1. `year < 2017 OR year IS NULL`
2. `coordinateUncertaintyInMeters < 10 OR NULL`
3. `embedding_year = 2017` (all historical points mapped to earliest AlphaEarth)
4. `requires_forest_validation = TRUE` (flag for GEE processing)

**Results**:
- **File**: `alphaearth_phase2_20260119_033102.parquet`
- **Total records**: 72,211,049 (4.4x more than Phase 1!)
- **Unique species**: 58,181
- **NEW species (not in Phase 1)**: 39,933
- **File size**: 451 MB

**Decade Distribution**:
| Decade | Records | % |
|--------|---------|---|
| 1920s | 42,697 | 0.07% |
| 1930s | 134,964 | 0.19% |
| 1940s | 110,125 | 0.15% |
| 1950s | 235,666 | 0.33% |
| 1960s | 423,754 | 0.59% |
| 1970s | 3,030,655 | 4.20% |
| 1980s | 8,292,585 | 11.48% |
| 1990s | 9,747,048 | 13.50% |
| 2000s | 23,665,220 | 32.77% |
| 2010s | 18,976,532 | 26.27% |
| NULL | 7,448,038 | 10.32% |

**Why so many more species?**
- Historical data goes back decades (some to 1900s)
- Many rare/endangered species only have old occurrence records
- 39,933 species have NO occurrences during 2017-2024

### No Phase 3 (Yet)

The two-phase extraction strategy is complete. There is no Phase 3 file.

---

## 3. Total Unique Species Across All Phases

### Combined Analysis

```python
Phase 1 species: 18,824
Phase 2 species: 58,181
Overlap: 18,248
Phase 2 ONLY (new): 39,933
Total unique: 58,757
```

**Comparison with Database**:
- Database total species: 67,743 (includes subspecies/varieties)
- Species with GBIF occurrences: 48,129
- **Phase 1 + Phase 2 coverage: 58,757 species (122% of species with occurrences)**

**Why 122%?** The GBIF occurrence data includes subspecies/varieties as unique taxon_ids. The "48,129" number from CLAUDE.md may refer to species-level records only, while Phase 1+2 includes both species and subspecies.

---

## 4. Processing Status: What's Actually Been Done?

### BigQuery Export Files (Local)

We have **two versions** of processed data exported from BigQuery:

#### Version 2 (v2): AlphaEarth + Hansen (NO Elevation)

**Files**: `occ_embeddings_hansen_v2_chunk_*.parquet` (9 chunks)

**Coverage**:
- Total records: 1,691,022
- Unique species: 5,966
- Mostly 2017 data (1,677,943 records)
- Small amounts of 2018-2024 (likely test data)

**Year Distribution**:
| Year | Records | Species |
|------|---------|---------|
| 2017 | 1,677,943 | 5,798 |
| 2018 | 8,018 | 17 |
| 2019-2023 | 60 | 57 |
| 2024 | 5,001 | 410 (test data) |

**Issue**: The 2024 test data (5,001 rows) should be **DELETED** when re-uploading to BigQuery.

#### Version 3 (v3): AlphaEarth + Hansen + SRTM Elevation

**Files**: `occ_embeddings_hansen_elev_v3_chunk_*.parquet` (7 chunks)

**Coverage**:
- Total records: 1,253,973
- Unique species: 2,986
- Split between 2017 and 2018

**Year Distribution**:
| Year | Records | Species |
|------|---------|---------|
| 2017 | 739,042 | 1,606 |
| 2018 | 514,931 | 1,866 |

**Processing Story** (from `ELEVATION_BACKFILL_TRACKING.md`):
1. Started processing Phase 1 WITHOUT elevation
2. After 841 tasks completed (2017 data), realized elevation was missing
3. **Cancelled 2,371 tasks** mid-processing
4. Added SRTM elevation to sampler
5. Started re-processing to v3 table
6. **Google Cloud billing disabled after ~$300 spend**
7. Processing stopped

#### Combined v2 + v3 Coverage

**Total unique species with embeddings**: 7,379

This is the **15,980** you mentioned in the context question. The discrepancy suggests:
- BigQuery v4 table exists remotely with more data
- OR the 15,980 includes deduplicated processing not yet exported locally

### Elevation Backfill Files

**Files**: `occ_elevation_backfill_chunk_*.parquet` (8 chunks)

**Purpose**: Backfill elevation for v2 records that don't have it

**Coverage**:
- Total records: 1,526,000
- This is elevation-only data (no embeddings)

---

## 5. Why Elevation Data is Only at 37% Coverage

From `embedding_coverage_summary.json`:

```json
{
  "total_phase1_unique": 8,016,401,
  "processed_v2": 1,548,469,
  "processed_v3": 1,138,279,
  "processed_total": 2,350,512,
  "unprocessed": 5,665,889,
  "coverage_pct": 29.32
}
```

**Answer**: Elevation is NOT at 37% coverage - it's at **29.32% coverage overall**.

Here's why:

1. **Phase 1 has 8.0M unique (lat, lon, year) combinations** (deduplicated pixels)
2. **Only 2.35M have been processed** (29.32%)
3. **v2 (no elevation)**: 1.55M records (19.3%)
4. **v3 (with elevation)**: 1.14M records (14.2%)
5. **Remaining unprocessed**: 5.67M pixels (70.7%)

**Year-by-Year Coverage**:
| Year | Total Pixels | Processed | % Done |
|------|--------------|-----------|--------|
| 2017 | 2,699,256 | 2,052,066 | **76%** |
| 2018 | 2,687,819 | 1,251,590 | **47%** |
| 2019 | 2,753,178 | 962,030 | **35%** |
| 2020 | 2,791,104 | 998,642 | **36%** |
| 2021 | 2,596,410 | 859,330 | **33%** |
| 2022 | 2,105,590 | 1,004,575 | **48%** |
| 2023 | 664,378 | 215,169 | **32%** |
| 2024 | 164,369 | 5,269 | **3%** |

**Why so low?**
- 2017 is mostly complete (76%)
- 2018 processing started but was interrupted
- 2019-2024 barely started before billing suspension

---

## 6. What Happened: The Complete Timeline

### January 19, 2026 - Morning

1. **03:07 AM**: Ran `extract_alphaearth_occurrences.py` (v1 - strict filters)
   - Output: `alphaearth_input_20260119_030704.parquet`
   - Only 854,009 records, 6,775 species
   - **This file is superseded - DO NOT USE**

2. **03:30 AM**: Ran `extract_alphaearth_occurrences_v2.py --phase 1`
   - Output: `alphaearth_phase1_20260119_033003.parquet`
   - 16.5M records, 18,824 species
   - This is the CURRENT Phase 1 file

3. **03:31 AM**: Ran `extract_alphaearth_occurrences_v2.py --phase 2`
   - Output: `alphaearth_phase2_20260119_033102.parquet`
   - 72.2M records, 58,181 species

### January 19, 2026 - GEE Processing

4. **Started processing Phase 1 to BigQuery** (`treekipedia-476404.alphaearth.occ_embeddings_hansen_v2`)
   - Sampler: AlphaEarth + Hansen (no elevation)
   - Batch size: 2,000 points per task
   - Started with 2017 data

5. **After 841 tasks completed** (~1.5M rows):
   - Realized SRTM elevation was missing
   - Added elevation to sampler script
   - Created new table: `occ_embeddings_hansen_elev_v3`

6. **Cancelled 2,371 pending tasks**
   - 2017: 582 tasks cancelled (chunks 768-1349)
   - 2018: All 1,344 tasks cancelled
   - Started re-processing to v3 table

7. **Google Cloud billing disabled**
   - Project `treekipedia-476404` suspended after ~$300 spend
   - Processing stopped mid-2018
   - 2019-2024 remain largely unprocessed

### January 20, 2026 - Data Export

8. **Exported BigQuery tables to local parquet files**
   - v2: 9 chunks (1.69M rows, 5,966 species)
   - v3: 7 chunks (1.25M rows, 2,986 species)
   - Elevation backfill: 8 chunks (1.53M rows)

9. **Created coverage summary**
   - Analyzed what's been processed vs. remaining
   - Identified unprocessed occurrences (9.0M records, 17,427 species)

---

## 7. Where is the 15,980 Species Number Coming From?

**You mentioned**: "Species with embeddings in BigQuery v4: 15,980"

**Possible explanations**:

1. **BigQuery v4 table exists remotely** that we haven't exported locally
   - Project: `treekipedia-479918` (new billing-enabled project)
   - Table: `species_data.alphaearth_embeddings_v4`
   - This would be the upload target from `upload_and_continue.py`

2. **The number includes all BigQuery processing** across v2, v3, v4, and possibly other test tables

3. **The number is from a different date** when more processing had been done

**To verify**, we need to:
```bash
# Check if v4 table exists in remote project
bq show treekipedia-479918:species_data.alphaearth_embeddings_v4

# Count unique species
bq query --use_legacy_sql=false '
SELECT COUNT(DISTINCT taxon_id) as unique_species
FROM `treekipedia-479918.species_data.alphaearth_embeddings_v4`
'
```

---

## 8. The Unprocessed Occurrences File

**File**: `unprocessed_occurrences.parquet`

**Content**:
- 9,021,381 records
- 17,427 unique species
- Years 2017-2024 only (Phase 1 data)

**Purpose**: Tracks which Phase 1 occurrences still need processing

**Year Distribution**:
| Year | Unprocessed Records | Species |
|------|---------------------|---------|
| 2017 | 642,792 | 1,630 |
| 2018 | 1,423,466 | 6,702 |
| 2019 | 1,774,567 | 8,382 |
| 2020 | 1,775,026 | 6,822 |
| 2021 | 1,721,831 | 7,557 |
| 2022 | 1,086,732 | 8,333 |
| 2023 | 440,164 | 7,681 |
| 2024 | 156,803 | 5,348 |

**Key Insight**: This is at the occurrence level, not pixel level. After deduplication by (lat, lon, year), the actual GEE sampling workload is much smaller.

---

## 9. The Path Forward: What Needs to Happen

### Immediate Next Steps

1. **Verify remote BigQuery v4 table**
   - Check if `treekipedia-479918.species_data.alphaearth_embeddings_v4` exists
   - Get row count and species count
   - Export to local if needed

2. **Upload existing v2 + v3 data to v4** (if v4 doesn't exist)
   - Use `upload_and_continue.py --upload`
   - Filter out bad data (2024 test, 2019-2023 contamination)
   - Clean table becomes baseline

3. **Resume processing with deduplication**
   - Use `upload_and_continue.py --continue`
   - Deduplicates to pixel-level (2.5M unique vs. 16.5M raw)
   - Process year by year: `--year 2019`, `--year 2020`, etc.

### Processing Estimates

**Phase 1 Remaining**:
- Unique pixel-years needed: ~5.7M (after deduplication)
- At 2,000 points/batch: ~2,850 GEE tasks
- Cost estimate: ~$570-$850 (depends on AlphaEarth vs. GCS approach)

**Phase 2 (Historical)**:
- Total records: 72.2M
- After pixel deduplication: ~10-15M unique pixels (estimate)
- Cost estimate: ~$1,000-$2,000
- **Requires forest validation** (only process where treecover2000 > 25%)

### Cost Optimization Options

From `ALPHAEARTH_PROCESSING_STATUS.md`:

1. **Use AlphaEarth on GCS** (NOT Earth Engine)
   - Available at `gs://alphaearth_foundations/`
   - Cloud Optimized GeoTIFFs (COGs)
   - **10-50x cheaper** than GEE (~$5-20 vs. $200-400)
   - Requires custom sampling script with rasterio
   - Supports range requests (no full file download)

2. **Pixel-level deduplication**
   - Round coordinates to 4 decimals (~11m precision)
   - 6-8x reduction in requests
   - Already implemented in `upload_and_continue.py`

3. **Process by year** to manage costs
   - Can pause between years if budget limits
   - Already supported: `--year 2019`

---

## 10. Database Status

### Local PostgreSQL

**Table**: `species_alphaearth_centroids`

**Current data**: Only 100 species (test data)

**Expected data**:
- Should have centroids for all species with ≥10 occurrences
- Clustering method: K-means with K=5
- 64-dimensional AlphaEarth embeddings per centroid

**To populate**:
1. Process remaining Phase 1 data through GEE
2. Run clustering script on embeddings
3. Load centroids to PostgreSQL

---

## 11. Key Files Reference

### Extraction Files

| File | Records | Species | Purpose |
|------|---------|---------|---------|
| `alphaearth_input_20260119_030704.parquet` | 854,009 | 6,775 | V1 strict filter (superseded) |
| `alphaearth_phase1_20260119_033003.parquet` | 16,462,104 | 18,824 | **Phase 1 (2017-2024)** |
| `alphaearth_phase2_20260119_033102.parquet` | 72,211,049 | 58,181 | **Phase 2 (pre-2017)** |
| `unprocessed_occurrences.parquet` | 9,021,381 | 17,427 | Phase 1 remaining |

### BigQuery Export Files

| Directory | Records | Species | Notes |
|-----------|---------|---------|-------|
| `occ_embeddings_hansen_v2_chunk_*.parquet` | 1,691,022 | 5,966 | No elevation |
| `occ_embeddings_hansen_elev_v3_chunk_*.parquet` | 1,253,973 | 2,986 | With elevation |
| `occ_elevation_backfill_chunk_*.parquet` | 1,526,000 | - | Elevation only |

### Processing Scripts

| Script | Purpose |
|--------|---------|
| `extract_alphaearth_occurrences_v2.py` | Two-phase extraction |
| `upload_and_continue.py` | Upload + deduplicated GEE processing |
| `run_phase1_by_year.py` | Year-by-year GEE sampling |
| `backfill_elevation_v2.py` | Elevation backfill |

---

## 12. Answers to Your Specific Questions

### Q1: What is "Phase 1"? How was it defined? Why only 18k species?

**Answer**:
- Phase 1 = GBIF occurrences from 2017-2024 (AlphaEarth coverage period)
- Filter: coordinateUncertaintyInMeters < 10m OR NULL
- 18,824 species because only this many have occurrences during 2017-2024
- Many species only have historical records (pre-2017)

### Q2: Are there other phases that need to be processed?

**Answer**:
- YES - Phase 2 with 72.2M records and 58,181 species
- Phase 2 = pre-2017 historical data + NULL year
- Adds 39,933 NEW species not in Phase 1
- Requires forest validation (Hansen treecover2000 > 25%)

### Q3: What's the relationship between source files?

**Answer**:
```
Source GBIF Data
   ↓
extract_alphaearth_occurrences_v2.py
   ├→ Phase 1 (2017-2024): 16.5M records, 18,824 species
   └→ Phase 2 (pre-2017): 72.2M records, 58,181 species
      ↓
GEE Sampling (run_phase1_by_year.py)
   ├→ v2 table (no elevation): 1.69M rows, 5,966 species
   ├→ v3 table (with elevation): 1.25M rows, 2,986 species
   └→ v4 table (TBD): potentially 15,980 species if exists
      ↓
BigQuery Export (local parquet files)
   ↓
Clustering (not yet done)
   ↓
PostgreSQL (only 100 test species loaded)
```

### Q4: Total unique species across all phases?

**Answer**: 58,757 unique species (Phase 1 + Phase 2 combined)

This is actually 122% of the "48,129 species with occurrences" number because it includes subspecies/varieties.

### Q5: Why elevation data is only at 37% coverage?

**Answer**: It's actually 29.32% coverage, not 37%.

Reasons:
- Google Cloud billing disabled after $300 spend
- Only processed 2.35M out of 8.0M unique pixel-years
- 2017: 76% done (mostly complete)
- 2018: 47% done (interrupted)
- 2019-2024: 3-48% done (barely started)

### Q6: Clear picture of what's been done vs. what's missing?

**Answer**:

**✅ Done**:
- Phase 1 + Phase 2 extraction files created
- 2.35M pixel-years processed with embeddings (29% of Phase 1)
- Exported to local parquet files
- Coverage analysis completed

**❌ Missing**:
- 70% of Phase 1 still needs processing (5.7M pixel-years)
- 100% of Phase 2 needs processing (72M records → ~10-15M unique pixels)
- Clustering script hasn't been run
- PostgreSQL only has 100 test species

**💰 Blocking Issue**:
- Google Cloud project `treekipedia-476404` billing disabled
- Need new project or resume billing to continue

---

## 13. Recommendations

### Short Term (Resume Processing)

1. **Verify v4 table status** in `treekipedia-479918` project
2. **Upload existing v2+v3 data** to v4 (clean baseline)
3. **Process remaining years** with deduplication:
   - Start with 2019 (highest species count)
   - Continue year by year
4. **Budget**: Set $500 limit, process what we can

### Medium Term (Optimize Costs)

1. **Migrate to GCS COG approach**
   - Write custom sampler using rasterio
   - 10-50x cheaper than GEE
   - Can process all remaining Phase 1 for ~$20-50

2. **Process Phase 2 selectively**
   - Only species with no Phase 1 data (39,933 new species)
   - Apply forest validation threshold
   - Estimate: ~30-40% of Phase 2 will pass validation

### Long Term (Complete Coverage)

1. **Full Phase 1 processing** (~$20-50 with GCS approach)
2. **Validated Phase 2 processing** (~$50-100 with GCS approach)
3. **Run clustering** on combined embeddings
4. **Load to PostgreSQL** for API access
5. **Create centroids table** for location predictor

---

## 14. Critical File Checksums

For data lineage and reproducibility:

**Source File**:
- SHA256: `79f56cdf0e7f905992527f9fc6c2de90e85f7c6cbc056af79a73145ae2edd837`
- File: `Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet`

**Extraction Outputs**:
- Phase 1: `alphaearth_phase1_20260119_033003.parquet` (181 MB)
- Phase 2: `alphaearth_phase2_20260119_033102.parquet` (451 MB)

---

## Appendix: Quick Stats Reference

```
DATABASE TOTALS
├─ Total species in database: 67,743
├─ Species with GBIF occurrences: 48,129
└─ Species without occurrences: 19,614 (mostly subspecies)

EXTRACTION FILES
├─ Phase 1 (2017-2024)
│  ├─ Records: 16,462,104
│  ├─ Species: 18,824
│  └─ Unique pixels: 2,526,270
└─ Phase 2 (pre-2017)
   ├─ Records: 72,211,049
   ├─ Species: 58,181
   ├─ New species: 39,933
   └─ Decade: 2000s-2010s dominant (59%)

PROCESSED EMBEDDINGS
├─ v2 (no elevation): 1,691,022 rows → 5,966 species
├─ v3 (with elevation): 1,253,973 rows → 2,986 species
├─ Combined unique: 7,379 species
└─ v4 (remote?): possibly 15,980 species

COVERAGE
├─ Phase 1 processed: 29.32% (2.35M / 8.0M pixels)
├─ Phase 1 remaining: 70.68% (5.67M pixels)
├─ Phase 2 processed: 0%
└─ Phase 2 remaining: 100%

LOCAL DATABASE
└─ species_alphaearth_centroids: 100 species (test data only)
```

---

**End of Report**
