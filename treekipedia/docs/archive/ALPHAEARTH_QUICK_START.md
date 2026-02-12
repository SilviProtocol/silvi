# AlphaEarth Species Selection: Quick Start Guide

**Quick reference for executing the AlphaEarth pilot species selection**

---

## Overview

This guide provides step-by-step instructions for selecting 100 tree species to test AlphaEarth environmental embeddings for predicting species distributions.

## Files Created

1. **ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md** - Complete strategic plan (43 pages)
2. **scripts/alphaearth_species_selection.sql** - Executable SQL implementation
3. **ALPHAEARTH_QUICK_START.md** (this file) - Quick reference guide

---

## Execution Steps

### Step 1: Database Preparation

```bash
# Connect to PostgreSQL database
psql -h localhost treekipedia

# Set random seed for reproducibility (optional)
SELECT setseed(0.42);

# Enable parallel queries for better performance (PostgreSQL 14+)
SET max_parallel_workers_per_gather = 4;
```

### Step 2: Run SQL Selection Script

Execute the SQL file in sections (recommended) or all at once:

**Option A: Section-by-section** (recommended for first run)
```bash
# Run each major section separately
psql -h localhost treekipedia -c "\i /path/to/scripts/alphaearth_species_selection.sql"

# Monitor progress after each step
```

**Option B: All at once** (fast, but less control)
```bash
psql -h localhost treekipedia -f /path/to/scripts/alphaearth_species_selection.sql
```

**Time estimates:**
- Steps 1-4 (candidate pool): 30-60 minutes
- Steps 5-10 (stratified selection): 1-2 minutes
- Steps 11-12 (export): 5-10 minutes
- Steps 13-14 (test points): <1 minute

### Step 3: Verify Output Files

Three CSV files will be created in `/tmp/`:

1. **alphaearth_pilot_species.csv** - 100 selected species with metadata
2. **alphaearth_occurrences.csv** - Geographic occurrence data (lat/lon)
3. **alphaearth_test_points.csv** - 30 strategic test locations

```bash
# Check file sizes
ls -lh /tmp/alphaearth_*.csv

# Preview species list
head /tmp/alphaearth_pilot_species.csv

# Count occurrences
wc -l /tmp/alphaearth_occurrences.csv
```

### Step 4: Validate Selection

Run validation queries (Step 14 in SQL script):

```sql
-- Check total species selected
SELECT COUNT(*) FROM alphaearth_pilot_species;
-- Expected: 100

-- Check biome distribution
SELECT dominant_biome, COUNT(*)
FROM alphaearth_pilot_species
GROUP BY dominant_biome;
-- Expected: Tropical Moist (15), Temperate Broadleaf (8), etc.

-- Check occurrence data quality
SELECT occurrence_category, COUNT(*)
FROM alphaearth_pilot_species
GROUP BY occurrence_category;
-- Expected: sparse (2), moderate (4), rich (4)
```

---

## Key Selection Criteria

The 100 species are stratified across:

1. **Biome (30 species):** Tropical moist (15), temperate (8), boreal (3), dry (4), Mediterranean (3), montane (4), mangroves (3)
2. **Niche Breadth (25 species):** Specialists (10), moderate (10), generalists (5)
3. **Forest Type (15 species):** Intact only (5), disturbed only (5), both (5)
4. **Phylogenetic (20 species):** Quercus (4), Pinus (4), Eucalyptus (3), Ficus (3), Acacia (3), others (3)
5. **Occurrence Quality (10 species):** Sparse 100-500 (2), moderate 500-5k (4), rich 5k-50k (4)

---

## Troubleshooting

### Issue: Step 2 (occurrence counts) takes too long

**Solution:** Use the materialized view approach (Option B in SQL script)
```sql
-- Create pre-computed occurrence counts
CREATE TABLE species_occurrence_counts AS
SELECT taxon_key, COUNT(*) as tile_count
FROM geohash_species_tiles,
     LATERAL jsonb_object_keys(species_data) as taxon_key
GROUP BY taxon_key;
```

### Issue: Random selection gives different results each time

**Solution:** Set random seed before Step 5
```sql
SELECT setseed(0.42);  -- Any value between 0.0 and 1.0
```

### Issue: Not enough species in a category

**Solution:** Relax occurrence filters in Step 3
```sql
-- Change from:
DELETE FROM candidate_species WHERE tile_count < 100 OR tile_count > 50000;

-- To:
DELETE FROM candidate_species WHERE tile_count < 50 OR tile_count > 100000;
```

### Issue: CSV export fails (permission denied)

**Solution:** Change export path in Steps 11, 12, 13
```sql
-- Change from:
\copy (...) TO '/tmp/alphaearth_pilot_species.csv' WITH CSV HEADER;

-- To:
\copy (...) TO '/your/writable/path/alphaearth_pilot_species.csv' WITH CSV HEADER;
```

---

## Next Steps After Selection

### 1. Spatial Thinning (Python)

Reduce spatial autocorrelation in occurrence data:

```python
import pandas as pd
from scipy.spatial import cKDTree

# Load occurrences
occ = pd.read_csv('/tmp/alphaearth_occurrences.csv')

# Thin to 10km minimum distance
# (See ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md Section 7 for full code)
```

### 2. Extract AlphaEarth Embeddings (Google Earth Engine)

```python
import ee
ee.Initialize()

# For each occurrence point:
# 1. Query AlphaEarth image at (lat, lon)
# 2. Extract 64-dimensional embedding vector
# 3. Save to CSV

# (See ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md Section 7 for full code)
```

### 3. Build K-Prototype Models (scikit-learn)

```python
from sklearn.covariance import EllipticEnvelope

# For each species:
# 1. Fit elliptic envelope on embeddings
# 2. Define environmental niche centroid and radius
# 3. Predict presence at test points

# (See ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md Section 7 for full code)
```

### 4. Validate & Analyze

- Calculate AUC, TSS, Boyce index for each species
- Test hypotheses (niche conservatism, biome discrimination)
- Compare performance across ecological categories

---

## Expected Results

### Success Criteria

The pilot is successful if:
- ✓ >70% of species achieve AUC > 0.7
- ✓ Specialists outperform generalists
- ✓ Phylogenetic signal detected (Blomberg's K > 0)
- ✓ Biome discrimination >75% accuracy
- ✓ Test point predictions match known distributions >70%

### Performance Benchmarks (from literature)

- **Excellent model:** AUC > 0.8, TSS > 0.6
- **Good model:** AUC 0.7-0.8, TSS 0.4-0.6
- **Poor model:** AUC < 0.7, TSS < 0.4

---

## Resources

- **Full Strategy Document:** `/ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md`
- **SQL Implementation:** `/scripts/alphaearth_species_selection.sql`
- **Database Schema:** `/treekipedia/database/README.md`
- **API Documentation:** `/treekipedia/API.md`

---

## Quick Reference: SQL Table Structure

### Key Tables Created

```
candidate_species
├── taxon_id (primary key)
├── species_scientific_name
├── family, genus
├── dominant_biome
├── niche_breadth (specialist/moderate/generalist)
├── forest_category (intact_only/disturbed_only/both)
├── occurrence_category (sparse/moderate/rich)
├── tile_count (100-50,000 range)
└── num_ecoregions, num_countries

alphaearth_pilot_species (final selection)
├── All fields from candidate_species
├── selection_dimension (biome/niche/forest/phylo/occurrence)
└── stratum (specific category within dimension)

alphaearth_occurrences
├── taxon_id
├── geohash_l7
├── latitude, longitude
└── occurrence_count

alphaearth_test_points
├── point_id
├── point_name
├── category (gradient_extreme/ecotone/known_location)
└── latitude, longitude
```

---

## Command Summary

```bash
# 1. Start PostgreSQL (if not running)
brew services start postgresql@17

# 2. Execute SQL script
psql -h localhost treekipedia -f scripts/alphaearth_species_selection.sql

# 3. Verify outputs
ls -lh /tmp/alphaearth_*.csv

# 4. Load in Python
python3
>>> import pandas as pd
>>> species = pd.read_csv('/tmp/alphaearth_pilot_species.csv')
>>> print(f"Selected {len(species)} species")

# 5. Check database tables
psql -h localhost treekipedia -c "SELECT COUNT(*) FROM alphaearth_pilot_species;"
```

---

## Contact & Support

For issues or questions:
- Check full strategy document: `ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md`
- Review SQL comments in: `scripts/alphaearth_species_selection.sql`
- Database documentation: `treekipedia/database/README.md`

---

**Document Version:** 1.0 (2025-10-27)
