# GBIF Integration Plan - Better Temporal Data

**Issue Identified**: October 27, 2025
**Problem**: Existing occurrence CSV has 96% of records from 2024 (data dump artifact, not real collection years)
**Impact**: Breaks temporal alignment strategy in builder's guide
**Solution**: Use GBIF API for occurrences with accurate temporal data

---

## 🚨 Problem: Flawed Temporal Data

### Current CSV Analysis
```
Year Distribution (Treekipedia_occ_Year_october24d.csv):
  2024: 91,267,619 (96.7%) ← CLEARLY A DUMP ARTIFACT
  2023:  1,263,869 (1.3%)
  2022:    510,250 (0.5%)
  ...older years
```

**Why This Breaks AlphaEarth**:
- AlphaEarth has annual images (2017-2024)
- Builder's guide temporal alignment requires real occurrence years
- Cannot match 96% to 2024 when most are likely from 1990-2020
- Would give species incorrect environmental embeddings

---

## ✅ Solution: GBIF API Integration

### What is GBIF?
- **Global Biodiversity Information Facility**
- 2.4+ billion occurrence records
- Real collection dates from herbarium specimens, observations, etc.
- Darwin Core standard (global interoperability)
- **Free API** with generous limits

### Advantages Over Current Data

| Feature | Current CSV | GBIF |
|---------|-------------|------|
| **Temporal accuracy** | ❌ 96% from 2024 (dump year) | ✅ Real collection years |
| **Data quality** | ⚠️ Unknown | ✅ Filters for geo issues |
| **Coordinate precision** | ⚠️ Unknown | ✅ Can filter by uncertainty |
| **Basis of record** | ⚠️ Mixed | ✅ Can select specimens only |
| **Updates** | ❌ Static | ✅ Continuous updates |
| **Attribution** | ⚠️ Unclear | ✅ DOI, citable |

### Expected Temporal Distribution (GBIF)
```
Typical GBIF download for plants:
  1990-2000:  5-10%  (older specimens digitized)
  2001-2010: 15-20%  (increased digitization)
  2011-2020: 40-50%  (iNaturalist, citizen science boom)
  2021-2025: 25-35%  (recent observations)
```

This matches AlphaEarth's 2017-2024 coverage perfectly!

---

## 🔧 Implementation

### Step 1: Species Name Matching
```python
from pygbif import species

# Match Treekipedia species to GBIF taxon keys
for sp in treekipedia_species:
    match = species.name_backbone(name=sp['scientific_name'])
    if match['matchType'] == 'EXACT':
        gbif_keys.append(match['usageKey'])
```

**Expected match rate**: ~95% (most tree species well-documented in GBIF)

### Step 2: Request Download
```python
from pygbif import occurrences as occ

# Request download for up to 100,000 species at once
download_key = occ.download([
    "taxonKey = " + " OR ".join(map(str, gbif_keys)),
    "hasCoordinate = true",
    "hasGeospatialIssue = false",
    "year >= 1990",
    "year <= 2025",
    "coordinateUncertaintyInMeters <= 1000"
])
```

**Filters Explained**:
- `hasCoordinate`: Must have lat/lon
- `hasGeospatialIssue`: Exclude known geo problems
- `year >= 1990`: Last 35 years for quality (and AlphaEarth coverage)
- `coordinateUncertaintyInMeters <= 1000`: Accuracy ≤1km

### Step 3: Wait & Download
```python
# Download completes in ~10 min to 2 hours depending on size
occ.download_get(download_key, path='./gbif_data')
# Returns ZIP with occurrence.txt (tab-separated)
```

### Step 4: Parse & Clean
```python
import pandas as pd

df = pd.read_csv('occurrence.txt', sep='\t')
# Columns: gbifID, taxonKey, scientificName, lat, lon, year, ...

# Map GBIF keys back to Treekipedia taxon_ids
df['taxon_id'] = df['taxonKey'].map(key_to_taxon_lookup)

# Save as Parquet
df.to_parquet('gbif_occurrences.parquet')
```

---

## 📊 Expected Results for 100-Species Pilot

### Volume Estimate
- **Species**: 100 (pilot)
- **Expected occurrences**: 50,000 - 500,000 (depends on species commonness)
- **Download size**: ~50-500 MB (compressed ZIP)
- **Download time**: 10-60 minutes

### Quality Improvements

**Temporal Distribution** (estimated):
```
Year Range     Count      AlphaEarth Year
-----------    -------    ---------------
1990-2016      20,000     → 2017 (earliest)
2017           8,000      → 2017
2018           10,000     → 2018
2019           12,000     → 2019
2020           15,000     → 2020
2021           18,000     → 2021
2022           20,000     → 2022
2023           25,000     → 2023
2024           30,000     → 2024
-----------    -------
TOTAL          ~158,000
```

**Geographic Spread**:
- Global coverage (not biased to one region/year)
- Better representation of species ranges
- More diverse environmental conditions

---

## 🔄 Updated Architecture

### Old (Flawed)
```
CSV with 96% from 2024
        ↓
Orchestrator (can't properly temporally align)
        ↓
GEE (samples wrong years)
        ↓
Bad embeddings
```

### New (GBIF)
```
PostgreSQL (Treekipedia species list)
        ↓
GBIF API (download with real years)
        ↓
Parquet (occurrences with accurate temporal data)
        ↓
Orchestrator (proper temporal alignment)
        ↓
GEE (samples correct AlphaEarth years)
        ↓
Accurate embeddings
```

---

## 📝 Modified Orchestrator Workflow

### Change in `run_pilot.py`

**Before** (using geohash tiles):
```python
def get_occurrences_for_species(taxon_id):
    # Query geohash_species_tiles (no year info)
    # Default year = 2024
```

**After** (using GBIF data):
```python
def get_occurrences_for_species(taxon_id):
    # Read from gbif_occurrences.parquet
    df = pd.read_parquet('orchestrator/gbif_data/gbif_occurrences.parquet')
    occs = df[df['taxon_id'] == taxon_id]

    # Apply temporal alignment
    occs['embedding_year'] = occs['year'].apply(get_embedding_year)

    return occs.to_dict('records')
```

---

## 🚀 Implementation Steps

### Phase 1: Setup (10 minutes)
1. Register GBIF account: https://www.gbif.org/user/profile
2. Install `pygbif`: `pip install pygbif`
3. Update `gbif_downloader.py` with credentials

### Phase 2: Download (1-2 hours)
```bash
cd orchestrator
python3 gbif_downloader.py
```

**Output**:
- `gbif_data/gbif_matches.json` - Species→GBIF key mapping
- `gbif_data/gbif_download.json` - Download metadata
- `gbif_data/<key>.zip` - Raw GBIF export
- `gbif_data/gbif_occurrences.parquet` - Cleaned occurrences

### Phase 3: Update Orchestrator (5 minutes)
Modify `run_pilot.py`:
- Replace `get_occurrences_for_species()` to read from Parquet
- Keep rest of workflow unchanged

### Phase 4: Run Pilot
```bash
python3 run_pilot.py
# Now uses GBIF data with accurate years!
```

---

## 📈 Benefits Summary

### Data Quality
- ✅ **Real temporal data** (not dump artifacts)
- ✅ **Geographic accuracy** (filtered to ≤1km uncertainty)
- ✅ **Quality flags** (no geospatial issues)
- ✅ **Traceable** (GBIF IDs, DOI citation)

### AlphaEarth Alignment
- ✅ **Proper temporal matching** (1990-2016→2017, exact 2017-2024)
- ✅ **Diverse years** (not 96% from one year)
- ✅ **Representative embeddings** (captures true niche over time)

### Scientific Rigor
- ✅ **Reproducible** (GBIF DOI for dataset)
- ✅ **Standard format** (Darwin Core)
- ✅ **Citable** (proper attribution)

---

## 🔗 Resources

- **GBIF Portal**: https://www.gbif.org
- **pygbif Docs**: https://pygbif.readthedocs.io
- **API Guide**: https://data-blog.gbif.org/post/gbif-api-beginners-guide/
- **Download Long Species Lists**: https://data-blog.gbif.org/post/downloading-long-species-lists-on-gbif/

---

## ✅ Decision: Use GBIF

**Recommendation**: **Strongly recommend GBIF integration**

**Effort**: Low (script already created, ~2 hours total)
**Impact**: High (fixes critical temporal data flaw)
**Risk**: Low (GBIF is production-ready, widely used)

**Next Action**: Run `gbif_downloader.py` to replace flawed CSV with accurate GBIF data.
