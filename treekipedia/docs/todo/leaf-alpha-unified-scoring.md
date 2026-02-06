# LEAF + AlphaEarth Unified Scoring

**Status**: Planning
**Added**: January 28, 2026
**Updated**: February 4, 2026
**Priority**: High
**Reference**: [MASTER_PREDICTION_ARCHITECTURE_2.md](../MASTER_PREDICTION_ARCHITECTURE_2.md)

---

## Overview

Combine LEAF (occurrence-based ecoregion scoring) with AlphaEarth (satellite embedding habitat prediction) into a unified species recommendation system supporting both ecoregion-level and site-specific queries with strategy-aware scoring.

**Key Insight**: LEAF provides ecological appropriateness (native status, observed occurrences), while AlphaEarth provides site-specific habitat matching. AlphaEarth alone recommends inappropriate species (e.g., Australian Eucalyptus for Sicily) — LEAF must act as the ecological filter.

---

## Current State

### LEAF Score (`/api/geospatial/leaf/score`)
- **Data**: 60,207 species with occurrence data + WCVP native status
- **Granularity**: Ecoregion (847 regions) or point → ecoregion lookup
- **Formula**: `affinity = occurrence_count × tile_count × native_multiplier`
- **Native handling**: 2x boost for native, exclude introduced, add WCVP-native species even without occurrences
- **Strengths**: Ecologically grounded, authoritative native status, comprehensive species coverage
- **Weaknesses**: Ecoregion-level granularity, doesn't account for microhabitat variation

### AlphaEarth Prediction (`/api/prediction/predict`)
- **Data**: 17,924 species with habitat centroids (subset of LEAF)
- **Granularity**: Exact lat/lon point
- **Formula**: Cosine similarity between location embedding and species habitat centroids
- **Infrastructure**: Python microservice (GEE) → 64-dim embedding → pgvector query
- **Strengths**: Site-specific, accounts for actual habitat signature
- **Weaknesses**: Recommends non-native species purely on habitat match, limited species coverage

### Data Overlap
| Dataset | Species Count |
|---------|---------------|
| LEAF only | 42,284 |
| AlphaEarth only | 1 |
| **Both** | 17,923 |
| **Total** | 60,208 |

---

## Two Query Modes: Ecoregion vs Site

### Mode 1: Ecoregion Query (Current)
```
GET /api/prediction/unified?eco_id=806
GET /api/prediction/unified?lat=37.5&lon=15.0  (resolves to ecoregion)
```
- Returns species ranked for the entire ecoregion
- LEAF-dominant scoring (ecoregion-wide occurrences)
- AlphaEarth uses ecoregion centroid embedding
- Best for: Regional planning, ecoregion guides, broad recommendations

### Mode 2: Site-Specific Query (NEW)
```
GET /api/prediction/unified?lat=37.5&lon=15.0&mode=site
POST /api/prediction/unified/polygon  (GeoJSON body)
```
- Returns species ranked for the specific location/plot
- AlphaEarth-dominant scoring (precise habitat match)
- Includes site environmental data (elevation, slope, aspect, etc.)
- Best for: Specific planting sites, project plots, microhabitat matching

---

## Area of Interest (AOI) Support

### AOI Types

| Type | Input | Max Size | Processing |
|------|-------|----------|------------|
| **Point** | `lat, lon` | N/A | Single embedding lookup |
| **Small Plot** | GeoJSON polygon | ≤10 ha | Centroid embedding + boundary check |
| **Medium Plot** | GeoJSON polygon | ≤100 ha | Multi-point sampling (9 points) |
| **Large Area** | GeoJSON polygon | ≤1000 ha | Grid sampling (25 points) + aggregate |
| **Ecoregion** | `eco_id` | Unlimited | Ecoregion centroid + LEAF data |

### Site Environmental Data (for Site Mode)

When `mode=site`, fetch additional environmental context:

```javascript
site_context: {
  // From AlphaEarth embedding extraction
  elevation_m: 450,
  slope_degrees: 12.5,
  aspect: "NW",
  tree_cover_2000: 65,
  forest_loss_year: null,

  // Derived
  topographic_position: "mid-slope",  // ridge, valley, flat, mid-slope
  distance_to_water_m: 1200,

  // From ecoregion lookup
  ecoregion: {
    eco_id: 806,
    eco_name: "Tyrrhenian-Adriatic sclerophyllous and mixed forests",
    biome: "Mediterranean Forests, Woodlands & Scrub"
  },

  // Climate (from species percentiles or external)
  climate_zone: "Csa",  // Köppen-Geiger
  annual_precip_mm: 650,
  mean_temp_c: 16.5
}
```

### Polygon Processing

For polygon inputs (plots/AOIs):

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: GeoJSON Polygon                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 0: Validate & Measure                                  │
│  - Calculate area (reject if > 1000 ha)                     │
│  - Determine sampling strategy based on size                │
│  - Extract centroid for primary query                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Sample Points                                       │
│  - ≤10 ha: centroid only                                    │
│  - ≤100 ha: centroid + 8 boundary points (3×3 grid)        │
│  - ≤1000 ha: 25-point grid (5×5)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Get Embeddings for All Sample Points               │
│  - Batch request to Python microservice                     │
│  - Get elevation, slope, aspect for each point             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Aggregate Environmental Variation                   │
│  - elevation_range: {min, max, mean, std}                   │
│  - slope_range: {min, max, mean}                            │
│  - habitat_heterogeneity: std(embeddings)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Run Unified Scoring with Aggregated Context        │
│  - Use mean embedding for AlphaEarth similarity             │
│  - Apply elevation filtering per species                    │
│  - Boost species tolerant of observed variation             │
└─────────────────────────────────────────────────────────────┘
```

---

## Restoration Strategy Profiles

Based on SAFE-B framework from [MASTER_PREDICTION_ARCHITECTURE_2.md](../MASTER_PREDICTION_ARCHITECTURE_2.md).

### Strategy Selection
```
GET /api/prediction/unified?lat=37.5&lon=15.0&strategy=rewilding
```

### Available Strategies

| Strategy | Description | Primary Goals |
|----------|-------------|---------------|
| `rewilding` | Ecological restoration | Native species, ecological function, wildlife support |
| `agroforestry` | Productive landscapes | Multi-use species, fast growth, marketability |
| `riparian` | Waterway restoration | Flood tolerance, bank stabilization, water quality |
| `carbon` | Carbon sequestration | Biomass accumulation, longevity, fast growth |
| `biodiversity` | Habitat creation | Fauna support, keystone species, structural diversity |
| `general` | Balanced default | No specific emphasis (default) |

### Strategy Weight Profiles

Weights applied to scoring components:

| Strategy | LEAF (S+E) | AlphaEarth (A) | Functional (F) | Biotic (B) |
|----------|------------|----------------|----------------|------------|
| `general` | 50% | 40% | 5% | 5% |
| `rewilding` | 45% | 20% | 10% | 25% |
| `agroforestry` | 25% | 25% | 45% | 5% |
| `riparian` | 30% | 40% | 25% | 5% |
| `carbon` | 25% | 25% | 45% | 5% |
| `biodiversity` | 35% | 20% | 15% | 30% |

**Component Definitions:**
- **LEAF (S+E)**: Spatial occurrences + Ecosystem/ecoregion match + native status
- **AlphaEarth (A)**: Abiotic habitat similarity from satellite embeddings
- **Functional (F)**: Trait match to strategy goals (from `*_ai` fields)
- **Biotic (B)**: Ecological interactions (pollinator support, wildlife value)

### Functional Trait Scoring by Strategy

For each strategy, boost species with matching traits:

```javascript
const STRATEGY_TRAIT_BOOSTS = {
  rewilding: {
    boost: ['native', 'keystone', 'wildlife_food_source', 'shade_tolerant'],
    penalize: ['fast_growing_pioneer']  // Avoid monoculture dominants
  },
  agroforestry: {
    boost: ['fast_growing', 'nitrogen_fixing', 'edible_fruit', 'timber_value', 'multi_use'],
    penalize: ['toxic_to_livestock']
  },
  riparian: {
    boost: ['flood_tolerant', 'bank_stabilization', 'deep_rooted', 'waterlogging_tolerant'],
    penalize: ['drought_specialist']
  },
  carbon: {
    boost: ['fast_growing', 'high_biomass', 'long_lived', 'dense_wood'],
    penalize: ['short_lived', 'small_statured']
  },
  biodiversity: {
    boost: ['wildlife_food_source', 'nesting_habitat', 'pollinator_support', 'keystone'],
    penalize: []
  }
};
```

### Trait Data Sources

| Trait Category | Source Field | Coverage |
|----------------|--------------|----------|
| Growth rate | `growth_rate_ai` | 100% (AI) |
| Max height | `maximum_height_ai` | 100% (AI) |
| Ecological function | `ecological_function_ai` | 100% (AI) |
| Tolerances | `tolerances_ai` | 100% (AI) |
| Timber value | `timber_value_ai` | 100% (AI) |
| Wildlife support | `globi_*` fields | Partial |

---

## Unified Scoring Formula

### Base Formula (General Strategy)

```javascript
// For species with LEAF + AlphaEarth data
unified_score = (
  LEAF_percentile * 0.50 +           // Occurrence-based regional fit
  AlphaEarth_similarity * 0.40 +     // Habitat signature match (0-1 → 0-100)
  functional_score * 0.05 +          // Trait match (if strategy specified)
  biotic_score * 0.05                // Ecological interactions
)

// For species with LEAF only
unified_score = (
  LEAF_percentile * 0.85 +
  functional_score * 0.10 +
  biotic_score * 0.05
)
```

### Strategy-Adjusted Formula

```javascript
function calculateUnifiedScore(species, context, strategy = 'general') {
  const weights = STRATEGY_WEIGHTS[strategy];

  // Base scores (0-100 scale)
  const leaf_score = species.leaf_percentile || 0;
  const alpha_score = (species.alpha_similarity || 0) * 100;
  const func_score = calculateFunctionalScore(species, strategy);
  const biotic_score = calculateBioticScore(species);

  // Apply strategy weights
  let unified = (
    leaf_score * weights.leaf +
    alpha_score * weights.alpha +
    func_score * weights.functional +
    biotic_score * weights.biotic
  );

  // Apply hard filters
  if (context.mode === 'site' && species.elevation_range) {
    if (!elevationCompatible(species, context.elevation_m)) {
      return null;  // Filter out
    }
  }

  return unified;
}
```

### Hard Filters (Applied Before Scoring)

| Filter | Rule | Applied When |
|--------|------|--------------|
| **Native Status** | Exclude if `is_introduced = true` | Always |
| **Elevation** | Exclude if site elevation outside species p10-p90 | Site mode |
| **Invasive Flag** | Exclude if USDA invasive flagged | Always |
| **Strategy Incompatible** | Exclude if critical trait mismatch | Strategy-specific |

---

## API Endpoints

### Primary Endpoint
```
GET /api/prediction/unified
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lat` | float | Yes* | Latitude (-90 to 90) |
| `lon` | float | Yes* | Longitude (-180 to 180) |
| `eco_id` | int | Yes* | Ecoregion ID (alternative to lat/lon) |
| `mode` | string | No | `ecoregion` (default) or `site` |
| `strategy` | string | No | Restoration strategy (default: `general`) |
| `limit` | int | No | Max species to return (default: 100) |
| `min_score` | float | No | Minimum unified score (default: 50) |

*Either `lat`+`lon` or `eco_id` required

### Polygon Endpoint
```
POST /api/prediction/unified/polygon
```

**Request Body:**
```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lon1, lat1], [lon2, lat2], ...]]
  },
  "strategy": "rewilding",
  "limit": 50
}
```

### Response Format

```json
{
  "success": true,
  "query": {
    "mode": "site",
    "strategy": "rewilding",
    "location": {
      "latitude": 37.5,
      "longitude": 15.0,
      "type": "point"
    }
  },
  "site_context": {
    "elevation_m": 450,
    "slope_degrees": 12.5,
    "aspect": "NW",
    "tree_cover_2000": 65,
    "ecoregion": {
      "eco_id": 806,
      "eco_name": "Tyrrhenian-Adriatic sclerophyllous and mixed forests"
    },
    "countries": ["Italy"]
  },
  "methodology": {
    "version": "2.0",
    "name": "LEAF + AlphaEarth Unified",
    "strategy": "rewilding",
    "weights": {
      "leaf": 0.45,
      "alpha": 0.20,
      "functional": 0.10,
      "biotic": 0.25
    },
    "filters_applied": ["native_only", "elevation_compatible"]
  },
  "statistics": {
    "total_candidates": 1208,
    "after_filters": 892,
    "with_alpha": 412,
    "leaf_only": 480
  },
  "species": [
    {
      "rank": 1,
      "taxon_id": "AngMaSaNcRd46762-00",
      "scientific_name": "Pistacia lentiscus",
      "common_name": "Mastic Tree",
      "unified_score": 94.2,
      "tier": "BEST",
      "confidence": "high",
      "scores": {
        "leaf_percentile": 100,
        "alpha_similarity": 0.82,
        "functional_score": 85,
        "biotic_score": 78
      },
      "strategy_match": {
        "aligned_traits": ["native", "wildlife_food_source", "drought_tolerant"],
        "explanation": "Native keystone species with high wildlife value"
      },
      "is_native": true
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Core Unified Endpoint (Backend)
- [ ] Create `/api/prediction/unified` endpoint in `prediction.js`
- [ ] Implement parallel LEAF + AlphaEarth queries
- [ ] Basic merge logic with configurable weights
- [ ] Add `mode` parameter (ecoregion vs site)
- [ ] Handle AlphaEarth service unavailability (fall back to LEAF-only)

### Phase 2: Strategy Support
- [ ] Implement strategy weight profiles
- [ ] Add functional trait scoring from `*_ai` fields
- [ ] Add biotic scoring from `globi_*` fields
- [ ] Create `calculateFunctionalScore()` and `calculateBioticScore()` functions

### Phase 3: Site-Specific Enhancements
- [ ] Add elevation extraction from AlphaEarth response
- [ ] Implement elevation compatibility filtering
- [ ] Add slope/aspect to site context
- [ ] Create species elevation profiles table (if not exists)

### Phase 4: Polygon/AOI Support
- [ ] Create `/api/prediction/unified/polygon` POST endpoint
- [ ] Implement area validation (max 1000 ha)
- [ ] Multi-point sampling for larger polygons
- [ ] Aggregate embeddings and environmental variation

### Phase 5: Testing & Calibration
- [ ] Test on 10+ diverse locations
- [ ] Compare strategy rankings (rewilding vs agroforestry should differ)
- [ ] Validate no invasive species in top recommendations
- [ ] Tune weights based on expert feedback

### Phase 6: Frontend Integration
- [ ] Add strategy selector to map UI
- [ ] Create polygon drawing tool for AOI
- [ ] Show site context panel
- [ ] Display strategy-specific explanations

### Phase 7: Documentation
- [ ] Update API.md with all endpoints
- [ ] Create user guide for strategy selection
- [ ] Document weight rationale

---

## Edge Cases

### 1. AlphaEarth Service Unavailable
- Fall back to LEAF-only scoring with adjusted weights
- Log warning, don't fail request
- Mark all species as `confidence: "medium"`
- Disable site-specific elevation filtering

### 2. Location Outside Ecoregion Coverage
- Use nearest ecoregion (with distance warning)
- AlphaEarth may still work (satellite coverage is broader)
- Flag response with `ecoregion_extrapolated: true`

### 3. Ocean/Urban Locations
- AlphaEarth returns simulated/invalid embedding
- LEAF returns empty (no ecoregion)
- Return error: "Location not suitable for tree recommendations"

### 4. Polygon Too Large
- Return error if > 1000 ha
- Suggest using ecoregion mode instead
- Or provide degraded service with sparse sampling

### 5. No Species Pass Filters
- Return empty list with explanation
- Suggest relaxing elevation or strategy constraints
- Provide LEAF-only fallback option

### 6. Species Missing Trait Data
- Use neutral score (50) for missing functional traits
- Don't penalize for missing data
- Flag `trait_data_incomplete: true`

---

## Success Metrics

1. **No invasive species in top 20** for any test location
2. **Strategy differentiation**: Rewilding and agroforestry top-10 should differ by 30%+
3. **Elevation filtering works**: No alpine species recommended for coastal sites
4. **Response time < 3 seconds** for point queries, < 10 seconds for polygons
5. **Expert validation**: 80%+ agreement on "appropriate" recommendations

---

## Related Documentation

- [MASTER_PREDICTION_ARCHITECTURE_2.md](../MASTER_PREDICTION_ARCHITECTURE_2.md) — Full SAFE-B framework
- [LEAF_INTEGRATION_GUIDE.md](../LEAF_INTEGRATION_GUIDE.md) — LEAF API reference
- [RECOMMENDATION_SERVICE.md](../RECOMMENDATION_SERVICE.md) — Original recommendation spec
- [prediction.js](../../backend/routes/prediction.js) — AlphaEarth endpoints
- [geospatial.js](../../backend/controllers/geospatial.js) — LEAF endpoint

---

## Test Locations

| Location | Lat | Lon | Ecoregion | Strategy Test |
|----------|-----|-----|-----------|---------------|
| Sicily | 37.5 | 15.0 | 806 Tyrrhenian | Mediterranean rewilding |
| Appalachia | 35.6 | -82.5 | 331 Blue Ridge | Temperate biodiversity |
| Amazon | -3.5 | -62.2 | TBD | Tropical agroforestry |
| Kenya | -1.3 | 36.8 | TBD | African carbon project |
| Australia | -33.8 | 151.2 | TBD | Test AlphaEarth-only handling |
| Netherlands | 52.3 | 4.9 | TBD | Riparian restoration |

---

## Appendix: Weight Tuning Guidelines

### When to Increase LEAF Weight
- Location has sparse AlphaEarth coverage
- Native status is critical (rewilding projects)
- Ecoregion has well-documented species list

### When to Increase AlphaEarth Weight
- Site-specific query with precise location
- Microhabitat variation matters (slope, aspect)
- Ecoregion is large/heterogeneous

### When to Increase Functional Weight
- Strategy has specific trait requirements (agroforestry, carbon)
- Species selection for specific use case
- Client has expressed functional priorities

### When to Increase Biotic Weight
- Biodiversity focus
- Existing fauna to support
- Pollinator/disperser availability uncertain
