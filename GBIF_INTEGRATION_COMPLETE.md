# GBIF Integration - COMPLETE ✅
**Date**: October 27, 2025
**Status**: Ready for AlphaEarth Embedding Extraction

---

## Summary

Successfully replaced flawed CSV occurrence data (96% from 2024) with real GBIF occurrence data featuring GPS-level precision and proper temporal distribution.

### What We Achieved
- ✅ **100 species** selected from 5 families (Fabaceae, Myrtaceae, Fagaceae, Salicaceae, Pinaceae)
- ✅ **95,934 occurrences** with ≤10m GPS coordinate uncertainty
- ✅ **Perfect temporal alignment** with AlphaEarth (2017-2024)
- ✅ **Real collection years** (not data dump artifacts)
- ✅ **All matched to Treekipedia taxon_ids** from PostgreSQL database

---

## Dataset Specifications

### Final Dataset File
**Location**: `orchestrator/gbif_data/gbif_occurrences_top100_gps.parquet`

**Schema**:
- `taxon_id` (STRING): Treekipedia species ID
- `species` (STRING): Scientific name
- `family` (STRING): Taxonomic family
- `latitude` (FLOAT): Decimal latitude
- `longitude` (FLOAT): Decimal longitude
- `year` (INTEGER): Collection year (2017-2024)
- `gbif_id` (STRING): GBIF occurrence ID

**Size**: ~3MB (Parquet compressed)

### Data Quality Metrics

**GPS Precision**: 100% at ≤10m coordinate uncertainty
- Matches AlphaEarth's 10m pixel resolution
- Ensures pixel-level accuracy for embedding extraction

**Temporal Distribution**:
| Year | Occurrences | % |
|------|-------------|---|
| 2017 | 8,994 | 9.4% |
| 2018 | 8,606 | 9.0% |
| 2019 | 10,205 | 10.6% |
| 2020 | 7,789 | 8.1% |
| 2021 | 14,206 | 14.8% |
| 2022 | 15,653 | 16.3% |
| 2023 | 14,737 | 15.4% |
| 2024 | 15,744 | 16.4% |

**Temporal Evenness**: 0.983/1.0 (nearly perfect distribution)

---

## Problem Solved

### Original CSV Issues
```
File: Treekipedia_occ_Year_october24d.csv
❌ 96% occurrences from 2024 (data dump artifact)
❌ Real collection years unknown
❌ No coordinate uncertainty metadata
❌ Unsuitable for temporal modeling
```

### New GBIF Data
```
File: gbif_occurrences_top100_gps.parquet
✅ 16.4% from 2024 (natural distribution)
✅ Real GPS collection timestamps
✅ All ≤10m coordinate uncertainty
✅ Perfect for temporal AlphaEarth alignment
```

---

## Species Breakdown

### By Family
| Family | Species | Occurrences | % |
|--------|---------|-------------|---|
| Fabaceae | 51 | 12,758 | 13.3% |
| Myrtaceae | 36 | 10,515 | 11.0% |
| Fagaceae | 7 | 72,978 | 76.1% |
| Salicaceae | 4 | 964 | 1.0% |
| Pinaceae | 2 | 634 | 0.7% |

### Top 10 Species
1. *Castanea sativa* - 69,651 occurrences (European chestnut)
2. *Acacia pycnantha* - 2,853 occurrences (Golden wattle)
3. *Quercus rotundifolia* - 2,390 occurrences (Holm oak)
4. *Acacia cyclops* - 2,066 occurrences (Coastal wattle)
5. *Eucalyptus obliqua* - 1,614 occurrences (Messmate)
6. *Acacia floribunda* - 1,082 occurrences (White sallow wattle)
7. *Acacia decurrens* - 1,011 occurrences (Early black wattle)
8. *Angophora inopina* - 957 occurrences (Charmhaven apple)
9. *Eucalyptus propinqua* - 882 occurrences (Small-fruited grey gum)
10. *Syzygium australe* - 844 occurrences (Brush cherry)

**Full list**: See [GBIF_TOP100_SPECIES_REPORT.md](orchestrator/GBIF_TOP100_SPECIES_REPORT.md)

---

## Data Collection Process

### GBIF Downloads (Oct 27, 2025)
- **11 separate GBIF downloads** combined
- **303,494 raw occurrences** downloaded
- **502 species** across 5 families
- **99.0% pass rate** for ≤10m GPS filter (300,425 occurrences)
- **282 species matched** to Treekipedia taxon_ids
- **Top 100 selected** by occurrence count

### GBIF Query Filters Applied
```json
{
  "HAS_COORDINATE": true,
  "HAS_GEOSPATIAL_ISSUE": false,
  "YEAR": "2017-2024",
  "COORDINATE_UNCERTAINTY_IN_METERS": "≤10"
}
```

### Source Files
All GBIF downloads preserved in `orchestrator/gbif_data/`:
- 11 ZIP files (0002042 through 0002148)
- Combined size: ~27MB compressed
- Can be reprocessed or validated at any time

---

## Next Steps: AlphaEarth Embedding Extraction

### Architecture
```
GBIF Parquet (local)
    ↓
Python Orchestrator (coordinates + years)
    ↓
Google Earth Engine (AlphaEarth sampling at 10m)
    ↓
BigQuery (raw 64-D embeddings - intermediate storage)
    ↓
Python (k-means clustering, 1-5 prototypes)
    ↓
PostgreSQL (centroids + metadata - final storage)
```

### Phase 1: Single Species Test
- [x] GBIF data ready
- [ ] Modify `run_pilot.py` to read from GBIF parquet
- [ ] Test GEE sampling with 1 species (e.g., *Acacia pycnantha* - 2,853 occurrences)
- [ ] Verify BigQuery receives embeddings
- [ ] Estimate processing time

### Phase 2: Full 100-Species Extraction
- [ ] Run all 100 species (~95,934 occurrence points)
- [ ] Monitor GEE quota (estimate: ~96K API calls, well within 5M/month free tier)
- [ ] Expected completion: 6-12 hours
- [ ] BigQuery storage: ~20-30GB for raw embeddings

### Phase 3: K-Prototypes Aggregation
- [ ] Query BigQuery for each species
- [ ] Run k-means clustering (k=1-5 based on sample size)
- [ ] Compute spherical statistics (r, q10/q50/q90)
- [ ] Store centroids + metadata in local PostgreSQL

---

## Files Modified/Created

### New Files
1. `orchestrator/gbif_downloader.py` - GBIF API integration script
2. `orchestrator/gbif_data/gbif_occurrences_top100_gps.parquet` - Final dataset
3. `orchestrator/gbif_data/gbif_matches.json` - Species to GBIF taxon key mappings
4. `orchestrator/GBIF_TOP100_SPECIES_REPORT.md` - Comprehensive species report
5. `GBIF_INTEGRATION_COMPLETE.md` - This summary document

### To Be Modified
1. `orchestrator/run_pilot.py` - Change from geohash tiles to GBIF parquet
2. `orchestrator/alphaearth_extractor.py` - Ensure BigQuery schema matches

---

## Key Technical Details

### Why GPS-Level Precision (≤10m) Matters
- AlphaEarth has **10m pixel resolution**
- Using >10m coordinate uncertainty creates pixel misalignment
- GPS devices typically have 3-10m accuracy (ideal match)
- Smartphone GPS: 4.9m median accuracy (within our filter)

### Why Temporal Data Quality Matters
- Each occurrence gets embedding from **its actual collection year**
- Enables temporal niche modeling (2017-2024 trends)
- Avoids false temporal patterns from data dump artifacts
- Natural growth pattern (+65.9% from early to late years) expected and valid

### AlphaEarth Collection Details
- **Name**: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- **Bands**: A01-A64 (64-dimensional embeddings)
- **Resolution**: 10m
- **Temporal coverage**: 2017-2024 (annual composites)
- **Projection**: EPSG:4326 (WGS84)

---

## Validation Checklist ✅

- [x] 100 species selected
- [x] All occurrences have ≤10m GPS precision
- [x] All occurrences within 2017-2024 temporal window
- [x] All species matched to Treekipedia taxon_ids
- [x] Temporal distribution is healthy (not data dump)
- [x] Dataset saved in efficient format (Parquet)
- [x] Documentation complete
- [ ] AlphaEarth extraction tested
- [ ] BigQuery pipeline validated
- [ ] K-prototypes computed

---

## Credits

**Data Source**: GBIF.org (Global Biodiversity Information Facility)
**GBIF User**: djimo (djimo@silvi.earth)
**Downloads**: 11 separate occurrence downloads (Oct 27, 2025)
**Citation**: Available via GBIF download DOIs (preserved in ZIP files)

**Tools Used**:
- `pygbif` (Python GBIF API client)
- PostgreSQL 17 + PostGIS 3.6 (species database)
- Pandas + PyArrow (data processing)
- Google Earth Engine (AlphaEarth access)
- BigQuery (embedding storage)

---

## Status: READY FOR EMBEDDINGS ✅

The GBIF integration is **complete and validated**. The dataset is production-ready for AlphaEarth embedding extraction.

**Next action**: Modify `orchestrator/run_pilot.py` to read from GBIF parquet and test with 1 species.

---

**Document Created**: October 27, 2025
**Last Updated**: October 27, 2025
**Version**: 1.0 (Final)
