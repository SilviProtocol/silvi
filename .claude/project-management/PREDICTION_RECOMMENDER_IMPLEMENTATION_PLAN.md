# Species Prediction & Recommendation Implementation Plan
## From Current Predictor to World-Class Recommender

**Version**: 1.2
**Date**: February 10, 2026
**Status**: Phase 1 + Phase 2 COMPLETE + SCORING TUNED, Phase 3 pending
**Author**: Claude Code session analysis

### Implementation Progress (February 10, 2026)

| Phase | Status | Files Changed |
|-------|--------|---------------|
| **Phase 1: Prediction Fixes** | COMPLETE | prediction.js, location_predictor_FIXED.py |
| **Phase 2: SAFE-B Recommender** | COMPLETE | safeb-scorer.js (new), prediction.js, SpeciesRecommenderModal.tsx (new), MapClickHandler.tsx |
| **Phase 2.5: Scoring Tuning** | COMPLETE | prediction.js, safeb-scorer.js, HabitatPredictionModal.tsx |
| **Phase 3: Pixel-Specific** | PENDING | — |

**Key changes — Session 1 (Multi-Signal Architecture):**
1. Fixed embedding key mismatch (dict→array normalization) in all prediction routes
2. Added multi-centroid matching (all clusters above threshold, not just best)
3. Added introduced-range boosting (+0.05 for species known to be introduced at location)
4. Added SRTM elevation + Hansen forest data to Python service
5. Added multi-year AlphaEarth fallback (2023→2017)
6. Created `safeb-scorer.js` — full SAFE-B scoring engine with 5 components
7. Created 7 strategy presets with distinct weight profiles
8. Refactored `/recommend` endpoint to use SAFE-B engine
9. Added `/strategies` endpoint for frontend discovery
10. Created `SpeciesRecommenderModal.tsx` with strategy selector UI
11. Modified `MapClickHandler.tsx` with Predict/Recommend mode selector

**Key changes — Session 2 (Scoring Tuning):**
12. Changed spatial density log base from 1000 to 100 (better discrimination for plantation species)
13. Added partial ecoregion credit (0.5) for spatially-confirmed species (10+ tiles)
14. Added "de-facto present" range tier (0.90) for species with spatial >= 0.85
15. Boosted introduced+spatially-confirmed range score (0.80 → 0.95)
16. Increased spatial weight in balanced bucket (0.35 → 0.40)
17. Increased multi-source bonus (2src: +0.04→+0.06, 3src: +0.08→+0.12)
18. Increased default result limit from 50 to 100
19. Updated SAFE-B scorer with spatial tile count tracking + partial ecoregion credit
20. Added "Show More" pagination to HabitatPredictionModal (initially 30, expandable to 100)
21. **Benchmark: P. radiata rank #103/64% → rank #42/81% at Auckland NZ**

---

## Table of Contents

1. [Current State Diagnosis](#1-current-state-diagnosis)
2. [Phase 1: Fix Prediction Accuracy](#2-phase-1-fix-prediction-accuracy)
3. [Phase 2: Build SAFE-B Recommender](#3-phase-2-build-safe-b-recommender)
4. [Phase 3: Pixel-Specific Recommendations](#4-phase-3-pixel-specific-recommendations)
5. [Data Inventory](#5-data-inventory)
6. [File Reference](#6-file-reference)

---

## 1. Current State Diagnosis

### 1.1 What Works

| Component | Status | Details |
|-----------|--------|---------|
| AlphaEarth GEE sampling | Working | `location_predictor_FIXED.py` on port 5002 |
| pgvector habitat centroids | Working | 44,625 centroids, 17,924 species, IVFFlat index |
| Point prediction (cosine similarity) | Working | Click map → embedding → top-N species |
| Polygon/AOI prediction | Working | Grid sampling within polygon, aggregated scores |
| Native/introduced badges | Working | WCVP + ecoregion → country → pattern matching |
| Frontend modals | Working | `HabitatPredictionModal.tsx`, `PolygonPredictionModal.tsx` |

### 1.2 Critical Bugs Found

#### Bug 1: Embedding Key Mismatch (BREAKS /predict and /recommend)

**Problem**: The `/api/prediction/predict` and `/recommend` routes expect:
```javascript
embedding = sampleResponse.data.alphaearth_embedding; // expects ARRAY
```

But `location_predictor_FIXED.py` returns:
```python
return {
    'embedding': {a00: 0.1, a01: 0.2, ...},  # returns OBJECT DICT
    # No 'alphaearth_embedding' key at all
}
```

**Impact**: `/predict` and `/recommend` always get `undefined` embedding, return 400 error.
**The working flow** uses `POST /api/prediction/from-embedding` and `POST /api/embeddings/predict` which handle both formats.

**Fix**: Convert dict to array in prediction.js OR rename key in Python service.

#### Bug 2: Elevation Never Available

**Problem**: `location_predictor_FIXED.py` returns no elevation data. It only samples AlphaEarth bands (A00-A63), not SRTM.

**Impact**: Elevation filtering in `/predict` always has `elevMin = null, elevMax = null`, making it a no-op.

**Fix**: Add SRTM sampling to the Python service.

### 1.3 Architectural Limitation: Introduced Species Gap

**The Pinus radiata Problem** (reproduces for ALL introduced/plantation species):

Pinus radiata's 3 habitat centroids are in:
- California (38.31, -123.04) — 582 occurrences (native range)
- SE Australia (-37.74, 145.68) — 1,381 occurrences (introduced)
- Colombia (4.90, -73.88) — 845 occurrences (introduced)

**None are in New Zealand**, despite P. radiata being NZ's dominant plantation species (~89% of planted forests).

**Root causes**:
1. AlphaEarth embeddings were extracted at GBIF occurrence points only
2. GBIF has 1,259 P. radiata tiles in NZ, but the AlphaEarth extraction pipeline may not have sampled these
3. K-means clustering (K=3) absorbed any NZ points into the SE Australia cluster
4. Cosine similarity between NZ forest embedding and Australian centroid may fall below 0.7 threshold

**This affects ALL species planted far outside their native/primary-occurrence range.**

### 1.4 The Recommender Gap

The `/api/prediction/recommend` endpoint exists but scoring is:
```
safe_b_score = similarity * 0.5 + native_boost(±0.2) + goal_boost(0.15) + 0.3
```

This is NOT the SAFE-B framework. It's a simplified placeholder. The full framework requires 5 independent scoring components weighted by restoration strategy, none of which are implemented.

**Data that EXISTS but is NOT used in any prediction/recommendation query:**
- Climate variables (8 WorldClim vars, 88.6% coverage)
- Soil variables (pH, texture, organic carbon, 66-82% coverage)
- Ecoregion/biome associations (100% coverage)
- GloBI biotic interactions (100% coverage)
- Functional traits (growth_form, nitrogen_fixing, uses, tolerances, successional_stage)
- Geohash occurrence density (5.7M tiles, 48,129 species)

---

## 2. Phase 1: Fix Prediction Accuracy

**Goal**: Make existing predictor work correctly and handle introduced species
**Effort**: ~2-3 days
**Impact**: Fixes broken endpoints, improves accuracy for 30%+ of use cases

### Fix 1.1: Embedding Key Mismatch

**Files**: `treekipedia/backend/routes/prediction.js`
**Change**: In `/predict` and `/recommend` routes, handle the Python service's actual response format.

The Python service returns:
```json
{"success": true, "embedding": {"a00": 0.1, "a01": 0.2, ...}}
```

Need to:
1. Read from `sampleResponse.data.embedding` (not `alphaearth_embedding`)
2. Convert dict `{a00: val, ...}` to sorted array `[val, val, ...]`
3. Same pattern used in `/from-embedding` and `/polygon` (already working)

### Fix 1.2: Multi-Centroid Matching

**Files**: `treekipedia/backend/routes/prediction.js`
**Change**: Replace `rank_in_species = 1` (only best cluster) with returning ALL clusters above threshold, then aggregating per species.

Currently: A species only matches if its BEST cluster is above 0.7 similarity.
Better: A species matches if ANY of its clusters is above threshold, and the score is the best match.

This alone could fix the Pinus radiata problem — its SE Australia cluster might score 0.65-0.72 for NZ locations (just below current 0.7 threshold), while the aggregate of multiple partial matches could push it above.

### Fix 1.3: Add SRTM Elevation to Python Service

**Files**: `orchestrator/location_predictor_FIXED.py`
**Change**: Add SRTM elevation sampling alongside AlphaEarth.

```python
# After AlphaEarth sampling, add:
srtm = ee.Image('USGS/SRTMGL1_003')
elevation = srtm.sample(region=point, scale=30).first().getInfo()
result['elevation'] = elevation['properties']['elevation']
```

This enables the elevation filtering that's already coded in prediction.js but never works.

### Fix 1.4: Introduced-Range Boosting

**Files**: `treekipedia/backend/routes/prediction.js`
**Change**: After pgvector similarity query, boost species known to be introduced in the query location's country.

Logic:
1. Get country from ecoregion lookup (already done in `/polygon`)
2. For each predicted species, check `wcvp_introduced` against country
3. If species is introduced there, apply +0.05-0.10 similarity boost
4. This captures the "the species IS here even if centroids don't represent it" signal

### Fix 1.5: Multi-Year AlphaEarth Fallback

**Files**: `orchestrator/location_predictor_FIXED.py`
**Change**: Try years 2023 → 2022 → 2021 → 2020 → 2019 → 2018 → 2017 before falling back to simulated.

AlphaEarth coverage varies by year. A location might have no 2023 data but good 2020 data.

### Fix 1.6: Lower Threshold for Sparse-Centroid Species

**Files**: `treekipedia/backend/routes/prediction.js`
**Change**: For species with `is_single_cluster = true` or `occurrence_count < 50`, use a lower similarity threshold (0.6 instead of 0.7).

Species with few observations have imprecise centroids — demanding 0.7 similarity excludes them unfairly.

---

## 3. Phase 2: Build SAFE-B Recommender

**Goal**: Implement the full 5-component SAFE-B scoring engine with strategy presets
**Effort**: ~1-2 weeks
**Impact**: Transforms the tool from "species predictor" to "species recommender"

### Architecture: SAFE-B Scoring Engine

```
For each candidate species at location (lat, lon):

SAFE-B Score = w_S * S + w_A * A + w_F * F + w_E * E + w_B * B

Where:
  S = Spatial score (0-1): Occurrence density + range proximity
  A = Abiotic score (0-1): Climate + soil + elevation match
  F = Functional score (0-1): Trait suitability for restoration goal
  E = Ecosystem score (0-1): Ecoregion + biome + GET match
  B = Biotic score (0-1): Interaction network viability

Weights (w_S through w_B) vary by restoration strategy.
```

### Component S: Spatial Score

**Data**: `geohash_species_tiles` (5.7M tiles, 48,129 species)
**Method**:
1. Get L7 geohash for query location
2. Search expanding rings of geohashes for species presence
3. Score = inverse_distance_weighted_count / max_possible

```sql
-- Find species with occurrences near the query point
WITH nearby_tiles AS (
    SELECT geohash_l7, species_data,
           ST_Distance(geometry, ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography) as dist_m
    FROM geohash_species_tiles
    WHERE ST_DWithin(geometry, ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography, 50000)
    -- 50km radius
)
SELECT taxon_id, 
       SUM(count::float / GREATEST(dist_m, 150)) as proximity_score
FROM nearby_tiles, 
     jsonb_each(species_data) as sp(taxon_id, data)
GROUP BY taxon_id
```

### Component A: Abiotic Score

**Data**: Species table climate + soil columns + SRTM elevation
**Method**:
1. Get location climate from WorldClim/TerraClimate (via GEE or pre-computed)
2. Compare against species percentile ranges
3. Score each variable, average with confidence weighting

For each variable (e.g., annual_precipitation_mm with format "min;max"):
```
match = 1.0 if value within [min, max]
match = 1.0 - (distance_to_range / range_width) if outside (clamped to 0)
```

Variables to use (already in species table):
- `annual_precipitation_mm` (88.6% coverage)
- `annual_temperature_range_c` (88.6%)
- `climate_type_koppengeiger` (88.5%)
- `driest_month_precipitation_mm` (100%)
- `wettest_month_precipitation_mm` (100%)
- `ph_prefered` / `ph_tolerated` (100%)
- `soil_texture_prefered` / `soil_texture_tolerated` (100%)
- Elevation from SRTM vs `elevation_ranges` (when numeric)

### Component F: Functional Score

**Data**: Species table trait columns
**Method**: Strategy-dependent trait matching

| Strategy | Key Traits | Scoring Logic |
|----------|-----------|---------------|
| Rewilding | `successional_stage`, `deciduous_evergreen`, native status | Late-successional + native + structural diversity |
| Agroforestry | `nitrogen_fixing`, `uses` (food/timber), `growth_form` | N-fixing + multi-use + fast growth |
| Riparian | `tolerances` (flood), root depth, bank stabilization | Flood tolerance + riparian association |
| Carbon | `growth_form` (tree), `maximum_height`, `lifespan` | Tall + long-lived + fast biomass |
| Biodiversity | GloBI interaction count, `forest_layers`, keystone potential | High interaction richness + structural diversity |

For each trait, compute a 0-1 match score based on the strategy's priorities, then average.

### Component E: Ecosystem Score

**Data**: `ecoregions` table (847 polygons), species `ecoregions` column, `biomes`, `functional_ecosystem_groups`
**Method**:
1. Get ecoregion(s) at query location via PostGIS ST_Intersects
2. For each species, check if its `ecoregions` field contains matching ecoregion names
3. If exact match: 1.0. If same biome: 0.7. If same realm: 0.4. Otherwise: 0.1.

```sql
-- Get ecoregion at location
SELECT eco_name, biome_name, realm 
FROM ecoregions 
WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint($lon, $lat), 4326));
```

### Component B: Biotic Score

**Data**: Species `globi_*` columns (pollinatedby, eatenby, flowersvisitedby, etc.)
**Method**:
1. Count total interaction partners (richness)
2. Check if key mutualists (pollinators, dispersers) are likely present at location
3. Higher richness = more ecologically integrated = higher score

Simple version:
```
interaction_richness = count_non_null_globi_fields(species)
B = interaction_richness / max_richness_across_candidates
```

Advanced version (later): Cross-reference interaction partners with other predicted species at the location to assess ecological viability.

### Strategy Weight Presets

| Strategy | S (Spatial) | A (Abiotic) | F (Functional) | E (Ecosystem) | B (Biotic) |
|----------|-------------|-------------|----------------|----------------|------------|
| Rewilding | 0.20 | 0.15 | 0.10 | 0.30 | 0.25 |
| Agroforestry | 0.10 | 0.25 | 0.40 | 0.15 | 0.10 |
| Riparian | 0.15 | 0.35 | 0.20 | 0.20 | 0.10 |
| Carbon | 0.10 | 0.20 | 0.50 | 0.15 | 0.05 |
| Biodiversity | 0.15 | 0.15 | 0.20 | 0.25 | 0.25 |
| General (default) | 0.20 | 0.25 | 0.20 | 0.20 | 0.15 |

### Hard Filters (Applied Before Scoring)

1. **Native filter**: For rewilding/biodiversity strategies, EXCLUDE species where `wcvp_introduced` contains the location's country AND `wcvp_native` does NOT
2. **Invasive filter**: ALWAYS exclude species in `countries_invasive` for the location (currently all NA — needs GRIIS import)
3. **AlphaEarth similarity floor**: Species must have ≥0.5 cosine similarity to even be considered (captures habitat plausibility)

### Implementation Plan

1. Create `treekipedia/backend/services/safeb-scorer.js` — the SAFE-B engine
2. Refactor `/api/prediction/recommend` to use the engine
3. Add location environment sampling (climate, soil at point) to Python service or as GEE proxy
4. Build frontend `RecommenderPanel.tsx` with strategy dropdown
5. Integrate into Analysis page map

---

## 4. Phase 3: Pixel-Specific Recommendations

**Goal**: Per-pixel species assignment within polygons, heterogeneous site analysis
**Effort**: ~3-4 weeks
**Impact**: World-class differentiation — no other tool does this

### 3.1 Micro-Habitat Classification

Within a polygon, instead of averaging all sample embeddings:
1. Sample at high density (e.g., every 100m in grid)
2. Cluster the sample embeddings using K-means (K=2-5)
3. Each cluster represents a distinct micro-habitat
4. Run SAFE-B recommendations independently per micro-habitat
5. Return: "Zone A (ridge, well-drained) → Species X, Y, Z; Zone B (valley, moist) → Species P, Q, R"

### 3.2 Multi-Site Analysis

Allow users to:
1. Drop multiple pins or draw multiple polygons
2. Get per-site recommendations
3. See connectivity analysis between sites (corridor potential)
4. Identify species that work across ALL sites vs site-specific species

### 3.3 Temporal/Disturbance Awareness

Use Hansen loss/gain data already in AlphaEarth v4:
1. `lossyear`: Year of forest loss (2001-2023)
2. `treecover2000`: Baseline canopy cover
3. `gain`: Whether forest has regrown

Map to successional stages:
- Recent loss (< 5 years): bare soil → pioneer species
- Medium (5-15 years): early succession → competitive colonizers
- Long recovery (15+ years): mid succession → shade-tolerant species
- Intact (no loss, high treecover): old growth → enrichment planting

### 3.4 Planting Plan Generation

Given polygon + strategy + micro-habitat zones:
1. Assign species to pixels based on SAFE-B scores per zone
2. Ensure species diversity within each zone (avoid monoculture)
3. Apply successional staging (plant pioneers first, climax later)
4. Generate downloadable GeoJSON with species assignments per zone
5. Include spacing recommendations based on growth_form and maximum_height

---

## 5. Data Inventory

### Available and Unused

| Data | Table/Column | Coverage | Currently Used In |
|------|-------------|----------|-------------------|
| Precipitation (annual, seasonal) | species.annual_precipitation_mm etc. | 88-100% | Nothing |
| Temperature range | species.annual_temperature_range_c | 88.6% | Nothing |
| Koppen climate | species.climate_type_koppengeiger | 88.5% | Nothing |
| Soil pH preference | species.ph_prefered, ph_tolerated | 100% | Nothing |
| Soil texture | species.soil_texture_prefered | 100% | Nothing |
| Organic carbon | species.oc_prefered | 100% | Nothing |
| Ecoregion associations | species.ecoregions | 100% | Nothing (in prediction) |
| Biome associations | species.biomes | 100% | Nothing |
| GloBI interactions (8 fields) | species.globi_* | 100% | Nothing |
| Growth form | species.growth_form | 100% | Minimal (goal_boost) |
| Nitrogen fixing | species.nitrogen_fixing | ? | Minimal (goal_boost) |
| Uses | species.uses | 100% | Minimal (goal_boost) |
| Successional stage | species.successional_stage | 100% | Nothing |
| Tolerances | species.tolerances | 100% | Nothing |
| Forest layers | species.forest_layers | 100% | Nothing |
| Conservation status | species.conservation_status | ? | Display only |
| Geohash tiles | geohash_species_tiles | 48,129 spp | Nothing (in prediction) |
| Ecoregion polygons | ecoregions | 847 | Native status only |
| Hansen forest change | In AlphaEarth v4 | 17,924 spp | Nothing |

### Missing (Would Improve System)

| Data | Impact | Effort to Acquire |
|------|--------|-------------------|
| Temperature BIO1, BIO5, BIO6 | HIGH — no temp data at all | 1-2 days (CHELSA via GEE) |
| GRIIS invasive species data | HIGH — countries_invasive all NA | 1 day (import from CSV) |
| Numeric elevation percentiles | MEDIUM — currently text prose | 2-3 days (SRTM aggregation) |
| Topographic derivatives (slope, TWI) | MEDIUM — riparian/drainage | 1 week (GEE pipeline) |
| Distance to water | MEDIUM — riparian species | 1 week (JRC water) |

---

## 6. File Reference

### Active Code Files

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| `orchestrator/location_predictor_FIXED.py` | GEE sampling (SRTM+Hansen+multi-year) | ~280 | UPGRADED |
| `treekipedia/backend/routes/prediction.js` | All prediction/recommendation endpoints | ~1500 | UPGRADED |
| `treekipedia/backend/services/safeb-scorer.js` | SAFE-B scoring engine (5 components) | ~500 | NEW |
| `treekipedia/backend/controllers/embeddings.js` | Legacy embedding endpoints (frontend uses) | 480 | Unchanged |
| `treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx` | Point prediction UI | 597 | Unchanged |
| `treekipedia/frontend/app/analysis/components/PolygonPredictionModal.tsx` | Polygon prediction UI | 509 | Unchanged |
| `treekipedia/frontend/app/analysis/components/SpeciesRecommenderModal.tsx` | SAFE-B recommender UI | ~400 | NEW |
| `treekipedia/frontend/app/analysis/components/MapClickHandler.tsx` | Map click → mode selector → predict/recommend | ~220 | UPGRADED |
| `treekipedia/backend/utils/wcvpRegions.js` | WCVP country → region mapping | ? | Unchanged |

### Architecture Documents

| File | Purpose |
|------|---------|
| `MASTER_PREDICTION_ARCHITECTURE.md` | v3.0 — System design, SAFE-B framework |
| `MASTER_PREDICTION_ARCHITECTURE_2.md` | v2.0 — Complete synthesis with env variables |
| `THIS FILE` | Implementation plan with specific code changes |
| `DYNAMIC_WEIGHTING_FRAMEWORK.md` | Context-adaptive weight research |
| `HABITAT_CLUSTERING_STRATEGY_RESEARCH.md` | 3-tier clustering approach |

### Database Tables

| Table | Records | Purpose |
|-------|---------|---------|
| `species_habitat_centroids` | 44,625 | pgvector 64-D centroids (ACTIVE) |
| `species_alphaearth_centroids` | 500 | Legacy POC centroids |
| `species` | 67,743 | All species data (115+ columns) |
| `geohash_species_tiles` | 5,786,835 | STAC occurrence tiles |
| `ecoregions` | 847 | WWF ecoregion polygons |
| `species_elevation_profiles` | ? | Elevation percentiles (may be empty) |

---

## Implementation Order

### Week 1: Prediction Fixes (Phase 1)
1. Fix embedding key mismatch → immediately unblocks /predict and /recommend
2. Add multi-centroid matching → better recall for introduced species
3. Add SRTM elevation to Python service → enables elevation filtering
4. Add introduced-range boosting → Pinus radiata shows up in NZ
5. Add multi-year fallback → better coverage globally
6. Test end-to-end with known locations

### Week 2-3: SAFE-B Engine (Phase 2)
1. Create safeb-scorer.js service module
2. Implement S (Spatial) scoring with geohash proximity
3. Implement A (Abiotic) scoring with climate/soil matching
4. Implement F (Functional) scoring with strategy traits
5. Implement E (Ecosystem) scoring with ecoregion matching
6. Implement B (Biotic) scoring with GloBI data
7. Wire up strategy presets and weight tables
8. Refactor /recommend endpoint to use full SAFE-B
9. Build frontend strategy selector and recommendation panel

### Week 4+: Pixel-Specific (Phase 3)
1. High-density polygon sampling
2. Micro-habitat clustering within polygons
3. Per-zone SAFE-B recommendations
4. Temporal disturbance integration
5. Multi-site analysis
6. Planting plan export

---

**This document should be read alongside MASTER_PREDICTION_ARCHITECTURE.md (system design) and MASTER_PREDICTION_ARCHITECTURE_2.md (data inventory).**
