# Species Knowledge Schema: Architectural Review & Improvements

**Date**: January 19, 2026 (Updated)
**Status**: Analysis Complete - Existing Data Validated
**Purpose**: Enable environmental matching, similarity calculations, and continuous boundary analysis for Species Aptness Score

---

## CRITICAL UPDATE: Environmental Analysis IS DONE

**Previous Assessment (INCORRECT)**: Assumed environmental data was missing or unusable.

**Actual State**: The intersection of occurrence data against environmental datasets has **already been completed** with excellent coverage:

| Field | Species with Data | Coverage |
|-------|-------------------|----------|
| `annual_precipitation_mm` | 60,005 | **88.6%** |
| `annual_temperature_range_c` | 60,005 | **88.6%** |
| `climate_type_koppengeiger` | 59,943 | **88.5%** |
| `sbtn_landcover` | 57,807 | **85.3%** |
| `ph_dominant` | 55,461 | **81.9%** |
| `functional_ecosystem_groups` | 48,081 | **71.0%** |
| `soil_texture_dominant` | 44,858 | **66.2%** |
| `present_intact_forest` | 4,300 | **6.3%** (most have "NA") |

### Data Format Analysis

**Numeric Ranges (Percentiles)**: The `min;max` format appears to be **interquartile ranges (IQR)**, NOT raw min/max:

```sql
-- Acer rubrum (2.3M occurrences):
annual_precipitation_mm = "467;510"      -- Range: 43mm (~9% width)
annual_temperature_range_c = "27.8;28.6" -- Range: 0.8°C (~3% width)

-- Quercus alba (2M occurrences):
annual_precipitation_mm = "457;502"      -- Range: 45mm (~9% width)

-- Ulmus americana (1.9M occurrences):
annual_precipitation_mm = "433;454"      -- Range: 21mm (~5% width)
```

If these were raw min/max, we'd expect ranges of 50-200%+ width. The narrow widths (5-11%) confirm these are **statistical percentiles** (likely p25-p75 or similar).

**Categorical Fields**:
- `climate_type_koppengeiger`: Semicolon-separated codes (e.g., "Cfa; Cwa; Aw; Dfa")
- `functional_ecosystem_groups`: Semicolon-separated EFG names (not codes)
- `ph_dominant`: Categories like "moderately acidic", "neutral", "strongly acidic"
- `soil_texture_dominant`: Categories like "Clay Loam", "Sandy Clay Loam"
- `present_intact_forest`: "YES", "NO", "YES;NO", "NO;YES", "NA"

---

## 1. What Already Works (No Changes Needed)

### 1.1 Climate Data ✅
The existing `annual_precipitation_mm` and `annual_temperature_range_c` fields:
- Store percentile ranges in `min;max` format
- Cover 88.6% of species (60,005 species)
- Can be parsed with SQL SPLIT_PART for comparison

**Sample Query**:
```sql
-- Find species suitable for location with 900mm annual precipitation
SELECT taxon_id, species_scientific_name, annual_precipitation_mm
FROM species
WHERE annual_precipitation_mm LIKE '%;%'
  AND CAST(SPLIT_PART(annual_precipitation_mm, ';', 1) AS NUMERIC) <= 900
  AND CAST(SPLIT_PART(annual_precipitation_mm, ';', 2) AS NUMERIC) >= 900;
```

### 1.2 Köppen-Geiger Climate Classification ✅
- 59,943 species (88.5%) have `climate_type_koppengeiger` data
- Format: Semicolon-separated codes with descriptions
- Can check if target climate code exists in list

### 1.3 Soil Data ✅
- `ph_dominant`: 81.9% coverage with categorical values
- `soil_texture_dominant`: 66.2% coverage
- `oc_dominant`: Organic carbon data available

### 1.4 Ecosystem Data ✅
- `functional_ecosystem_groups`: 71% coverage with EFG names
- `sbtn_landcover`: 85.3% coverage with SBTN land cover types

---

## 2. What Still Needs Work

### 2.1 Elevation Data Gap 🔴

**Issue**: No numeric elevation data exists in the schema.

Current fields:
- `elevation_ranges_ai`: TEXT prose from AI research (e.g., "Native populations occur from 300m to 1250m...")
- `elevation_ranges_human`: TEXT prose from human input

**Required**: Numeric elevation percentiles from SRTM/DEM intersection

**Solution**: Add fields or new table with elevation ranges from intersection:
```sql
-- Option A: Add to species table
ALTER TABLE species
  ADD COLUMN elevation_min_m INTEGER,
  ADD COLUMN elevation_p25_m INTEGER,
  ADD COLUMN elevation_median_m INTEGER,
  ADD COLUMN elevation_p75_m INTEGER,
  ADD COLUMN elevation_max_m INTEGER;

-- Option B: Separate profile table (see Section 3.1)
```

### 2.2 IFL Data Gap 🟡

**Issue**: `present_intact_forest` has only 6.3% coverage (4,300 species)
- 63,443 species have "NA" (no occurrence data intersected with IFL)

**Root Cause**: IFL intersection may not have been run, or species without occurrences can't be analyzed.

**Note**: This is expected for subspecies (16,862) that lack occurrence data.

### 2.3 EFG Code vs Name 🟡

**Issue**: `functional_ecosystem_groups` stores full names, not codes:
```
"Tropical-subtropical lowland rainforests; Temperate broadleaf deciduous forests"
```

**Preferred**: Store EFG codes for easier matching:
```
"T1.1; T2.2; FM1.3"
```

**Solution**: Either:
- Create a lookup table for name-to-code mapping
- Add a new field with codes
- Parse at query time (slower)

### 2.4 No Percentile Documentation 🟡

**Issue**: The min;max values appear to be percentiles, but there's no documentation confirming:
- Are they p25-p75 (IQR)?
- Are they p10-p90?
- Or raw min/max from occurrence samples?

**Action**: Check with data team to confirm percentile methodology.

---

## 3. Recommended Schema Additions

### 3.1 Elevation Profile Table (NEEDED)

```sql
CREATE TABLE species_elevation_profiles (
    taxon_id VARCHAR(50) PRIMARY KEY REFERENCES species(taxon_id),

    -- Elevation statistics (meters)
    elevation_min INTEGER,
    elevation_p10 INTEGER,
    elevation_p25 INTEGER,
    elevation_median INTEGER,
    elevation_p75 INTEGER,
    elevation_p90 INTEGER,
    elevation_max INTEGER,
    elevation_stddev FLOAT,

    -- Sample info
    occurrence_count INTEGER,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- Index for range queries
CREATE INDEX idx_elev_range ON species_elevation_profiles(elevation_p25, elevation_p75);
```

### 3.2 EFG Code Mapping (RECOMMENDED)

```sql
CREATE TABLE efg_lookup (
    efg_code VARCHAR(10) PRIMARY KEY,  -- "T1.1", "T2.2", etc.
    efg_name TEXT NOT NULL,
    realm CHAR(1),                      -- T, M, F, S
    biome VARCHAR(5),                   -- T1, T2, M1, etc.
    description TEXT
);

-- Add code field to species table
ALTER TABLE species
ADD COLUMN efg_codes TEXT;  -- Semicolon-separated codes: "T1.1;T2.2;FM1.3"
```

### 3.3 Environmental Profile View (USEFUL)

```sql
CREATE OR REPLACE VIEW species_environmental_summary AS
SELECT
    s.taxon_id,
    s.species_scientific_name,

    -- Parse precipitation range
    CASE
        WHEN s.annual_precipitation_mm LIKE '%;%'
        THEN CAST(SPLIT_PART(s.annual_precipitation_mm, ';', 1) AS NUMERIC)
    END as precip_min_mm,
    CASE
        WHEN s.annual_precipitation_mm LIKE '%;%'
        THEN CAST(SPLIT_PART(s.annual_precipitation_mm, ';', 2) AS NUMERIC)
    END as precip_max_mm,

    -- Parse temperature range
    CASE
        WHEN s.annual_temperature_range_c LIKE '%;%'
        THEN CAST(SPLIT_PART(s.annual_temperature_range_c, ';', 1) AS NUMERIC)
    END as temp_min_c,
    CASE
        WHEN s.annual_temperature_range_c LIKE '%;%'
        THEN CAST(SPLIT_PART(s.annual_temperature_range_c, ';', 2) AS NUMERIC)
    END as temp_max_c,

    -- Soil
    s.ph_dominant,
    s.soil_texture_dominant,

    -- Climate
    s.climate_type_koppengeiger,

    -- Ecosystems
    s.functional_ecosystem_groups,
    s.sbtn_landcover,
    s.present_intact_forest,

    -- Elevation (from profile table when available)
    e.elevation_p25,
    e.elevation_median,
    e.elevation_p75

FROM species s
LEFT JOIN species_elevation_profiles e ON s.taxon_id = e.taxon_id
WHERE s.annual_precipitation_mm IS NOT NULL
  AND s.annual_precipitation_mm != 'NA';
```

---

## 4. Continuous Boundary Algorithms

### 4.1 PostGIS Functions (Ready to Use)

The database already has PostGIS with IFL and ecoregion polygons. Functions from previous section remain valid:

```sql
-- Check if two points share IFL
CREATE OR REPLACE FUNCTION same_ifl(lat1 FLOAT, lon1 FLOAT, lat2 FLOAT, lon2 FLOAT)
RETURNS BOOLEAN AS $$
  SELECT COALESCE(
    (SELECT ifl_id FROM intact_forest_landscapes_2021
     WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon1, lat1), 4326)) LIMIT 1)
    =
    (SELECT ifl_id FROM intact_forest_landscapes_2021
     WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon2, lat2), 4326)) LIMIT 1),
    FALSE
  );
$$ LANGUAGE SQL STABLE;

-- Check if two points share ecoregion
CREATE OR REPLACE FUNCTION same_ecoregion(lat1 FLOAT, lon1 FLOAT, lat2 FLOAT, lon2 FLOAT)
RETURNS BOOLEAN AS $$
  SELECT COALESCE(
    (SELECT eco_id FROM ecoregions
     WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon1, lat1), 4326)) LIMIT 1)
    =
    (SELECT eco_id FROM ecoregions
     WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon2, lat2), 4326)) LIMIT 1),
    FALSE
  );
$$ LANGUAGE SQL STABLE;
```

### 4.2 Local Raster Sampling (Ready to Use)

EFG rasters are available in `Sources_Data/` for local sampling without GEE.

---

## 5. Implementation Priority

### Immediate (1-2 days)
1. ✅ Create `species_environmental_summary` view for easy querying
2. 🔲 Confirm percentile methodology with data team
3. 🔲 Create `species_elevation_profiles` table schema

### Short-term (1 week)
4. 🔲 Run elevation intersection using local SRTM data
5. 🔲 Create EFG code mapping table
6. 🔲 Add PostGIS boundary functions

### Medium-term (2-3 weeks)
7. 🔲 Investigate IFL coverage gap (why only 6.3%?)
8. 🔲 Build `aptness_score.py` module using existing data
9. 🔲 Performance optimization for range queries

---

## 6. Summary: What Works vs What's Missing

| Capability | Status | Data Coverage | Action |
|------------|--------|---------------|--------|
| **Precipitation ranges** | ✅ WORKS | 88.6% | Parse semicolon format |
| **Temperature ranges** | ✅ WORKS | 88.6% | Parse semicolon format |
| **Köppen-Geiger climate** | ✅ WORKS | 88.5% | String matching |
| **Soil pH** | ✅ WORKS | 81.9% | Category matching |
| **Soil texture** | ✅ WORKS | 66.2% | Category matching |
| **EFG (ecosystem)** | ⚠️ PARTIAL | 71.0% | Need code mapping |
| **SBTN landcover** | ✅ WORKS | 85.3% | String matching |
| **Elevation ranges** | ❌ MISSING | 0% | Need SRTM intersection |
| **IFL presence** | ⚠️ PARTIAL | 6.3% | Investigate gap |
| **IFL boundary check** | ✅ READY | PostGIS | Create function |
| **Ecoregion check** | ✅ READY | PostGIS | Create function |

---

## 7. Key Insight

**The environmental analysis has already been done well.** The schema stores percentile-based climate and soil data for ~60K species (88%+ coverage). The main gaps are:

1. **Elevation**: Not intersected yet - needs SRTM/DEM processing
2. **IFL**: Low coverage (6.3%) - may need re-analysis
3. **EFG codes**: Stored as names, not codes - need mapping table

The Aptness Score can be built using existing data for most factors. Elevation will require additional processing.

---

**Document Author**: Claude Code
**Last Updated**: January 19, 2026
**Review Status**: User feedback incorporated - data exists!
