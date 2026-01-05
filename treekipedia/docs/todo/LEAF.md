# LEAF™ - Location-based Ecological Aptness Forecast

**Status**: ✅ MVP IMPLEMENTED (December 2025)
**Priority**: HIGH - Critical for $100K bioregional campaigns
**Endpoint**: `GET/POST /api/geospatial/leaf/score`
**Report**: [LEAF_Appalachian_Blue_Ridge_Report.md](../reports/LEAF_Appalachian_Blue_Ridge_Report.md)

---

## Overview

The **Treekipedia LEAF™** (Location-based Ecological Aptness Forecast) is a scoring system that answers: **"What trees should I plant here?"**

LEAF provides scientifically-grounded, occurrence-based species recommendations for any location on Earth, with built-in safeguards against monoculture greenwashing.

**Key Innovation**: Combines 89.3M GBIF occurrences with WCVP native/introduced status to measure which species are truly **native, abundant, and established** in each ecological zone.

**Design Philosophy**: Union pool approach - include all WCVP native species PLUS all species with occurrences, then exclude introduced species and rank by weighted affinity.

---

## The LEAF Score

Each species receives a **LEAF score** (0-100) for a given location, representing its **percentile rank** among all qualifying species for that ecoregion.

- A score of **85** means "this species ranks higher than 85% of species in this ecoregion"
- Scores are **relative within each ecoregion**, enabling fair comparison of "what's best HERE"
- A **minimum threshold** (0.05% of occurrences) filters out species with weak signals

### Why Percentile Scoring?

| Approach | Pros | Cons |
|----------|------|------|
| **Relative (percentile)** | Clean 0-100 distribution, easy tiers, answers "what's best here" | Can't compare across ecoregions |
| **Absolute (fixed formula)** | Comparable everywhere, shows signal strength | Wildly different scales per ecoregion |

**Decision**: Use percentile scoring with a minimum threshold. The threshold ensures only species with meaningful presence are considered; the percentile ranks them fairly.

---

## MVP Architecture

### Core Concept

```
Point (lat, lng)
    ↓
Resolve to Ecoregion (via eco_id lookup)
    ↓
Build Species Pool:
  - WCVP natives for ecoregion's countries/states
  - UNION species with occurrences in ecoregion
  - EXCLUDE species marked as introduced (wcvp_introduced)
    ↓
Calculate Affinity:
  - With occurrences: occurrence_count × tile_count × native_multiplier
  - WCVP-only natives: baseline (100) × native_multiplier
    ↓
Convert to Percentile (0-100 LEAF score)
    ↓
Tier Results (BEST / GOOD / ACCEPTABLE)
```

### The Species Pool (Union Approach)

The pool combines two authoritative data sources:

1. **WCVP Native Species**: All species marked native to the ecoregion's countries/states
2. **Occurrence Data**: All species observed within ecoregion boundaries

**Why union?** Data gaps shouldn't exclude valid species. A native species with no GBIF occurrences is still appropriate for planting - it just has lower confidence than one with both native status AND occurrence evidence.

### Native Status Detection (Three-Tier)

Using WCVP (World Checklist of Vascular Plants) data:

| Status | Detection | Treatment |
|--------|-----------|-----------|
| **Native** | In `wcvp_native` for region | ×2.0 boost |
| **Unknown** | Not in native OR introduced | ×1.0 neutral |
| **Introduced** | In `wcvp_introduced` for region | **EXCLUDED** |

**Tested Result (Appalachian-Blue Ridge):**
- 170 introduced species excluded (Tree of Heaven, Mimosa, Princess Tree, etc.)
- 1,131 native species kept
- 148 unknown species kept (ranked by occurrence only)

### The Affinity Formula

```
weighted_affinity = base_affinity × native_multiplier

Where:
  base_affinity = occurrence_count × tile_count  (if has occurrences)
                  OR 100                          (WCVP-only natives)

  native_multiplier = 2.0  (native)
                      1.0  (unknown)
```

This captures:
- **Abundance**: How many times has this species been observed?
- **Distribution**: How widespread is it across the ecoregion?
- **Native Boost**: Verified native species get 2× advantage

Species that are **native + common + widespread** score highest.

---

## MVP Implementation

### Core SQL Query

```sql
-- Step 1: Expand tile species data
WITH tile_species AS (
  SELECT
    geohash_l7,
    (jsonb_each_text(species_data)).key AS taxon_id,
    (jsonb_each_text(species_data)).value::int AS occurrences
  FROM geohash_species_tiles
  WHERE eco_id = $1
),

-- Step 2: Aggregate occurrences by species
ecoregion_occurrences AS (
  SELECT
    taxon_id,
    SUM(occurrences) AS occurrence_count,
    COUNT(DISTINCT geohash_l7) AS tile_count
  FROM tile_species
  GROUP BY taxon_id
),

-- Step 3: Get WCVP native species for ecoregion's states/countries
wcvp_natives AS (
  SELECT taxon_id FROM species
  WHERE wcvp_native IS NOT NULL
    AND (wcvp_native ILIKE ANY($2))  -- Array of state/country patterns
),

-- Step 4: Get WCVP introduced species (to exclude)
wcvp_introduced AS (
  SELECT taxon_id FROM species
  WHERE wcvp_introduced IS NOT NULL
    AND (wcvp_introduced ILIKE ANY($2))
),

-- Step 5: Build union pool, excluding introduced
species_pool AS (
  SELECT DISTINCT
    COALESCE(eo.taxon_id, wn.taxon_id) AS taxon_id,
    COALESCE(eo.occurrence_count, 0) AS occurrence_count,
    COALESCE(eo.tile_count, 0) AS tile_count,
    CASE WHEN wn.taxon_id IS NOT NULL THEN true ELSE false END AS is_native
  FROM ecoregion_occurrences eo
  FULL OUTER JOIN wcvp_natives wn ON eo.taxon_id = wn.taxon_id
  LEFT JOIN wcvp_introduced wi ON COALESCE(eo.taxon_id, wn.taxon_id) = wi.taxon_id
  WHERE wi.taxon_id IS NULL  -- Exclude introduced
),

-- Step 6: Calculate weighted affinity
scored AS (
  SELECT
    sp.*,
    CASE
      WHEN sp.occurrence_count > 0 THEN sp.occurrence_count * sp.tile_count
      ELSE 100  -- Baseline for WCVP-only natives
    END AS base_affinity,
    CASE
      WHEN sp.occurrence_count > 0 THEN
        (sp.occurrence_count * sp.tile_count) * (CASE WHEN sp.is_native THEN 2.0 ELSE 1.0 END)
      ELSE 200  -- Baseline × 2.0 for WCVP-only natives
    END AS weighted_affinity
  FROM species_pool sp
),

-- Step 7: Calculate percentile LEAF score
ranked AS (
  SELECT
    s.*,
    PERCENT_RANK() OVER (ORDER BY weighted_affinity) * 100 AS leaf_score
  FROM scored s
)

SELECT
  r.taxon_id,
  r.occurrence_count,
  r.tile_count,
  r.is_native,
  ROUND(r.leaf_score::numeric, 1) AS leaf_score,
  CASE
    WHEN r.leaf_score >= 90 THEN 'BEST'
    WHEN r.leaf_score >= 70 THEN 'GOOD'
    WHEN r.leaf_score >= 50 THEN 'ACCEPTABLE'
    ELSE 'LOW'
  END AS tier,
  sp.species_scientific_name,
  sp.common_name,
  sp.family
FROM ranked r
JOIN species sp ON sp.taxon_id = r.taxon_id
WHERE r.leaf_score >= 50  -- Only return ACCEPTABLE and above
ORDER BY r.leaf_score DESC;
```

### Point-to-Ecoregion Resolution

For any point input, resolve to ecoregion:

```sql
-- Option 1: Via geohash tile lookup (fast)
SELECT eco_id, eco_name, biome_name, realm
FROM geohash_species_tiles gst
JOIN ecoregions e ON e.eco_id = gst.eco_id
WHERE gst.geohash_l7 = encode_geohash($lat, $lng, 7)
LIMIT 1;

-- Option 2: Direct spatial query (accurate)
SELECT eco_id, eco_name, biome_name, realm
FROM ecoregions
WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($lng, $lat), 4326));
```

### Tier Classification

| Tier | Percentile Range | Description |
|------|------------------|-------------|
| **BEST** | 90-100 | Top 10% - Highly recommended |
| **GOOD** | 70-89 | Next 20% - Appropriate choice |
| **ACCEPTABLE** | 50-69 | Middle tier - Viable option |
| **Below threshold** | <50 or filtered | Not recommended for this location |

---

## Incremental Roadmap

### MVP (Current Sprint) ✅ TESTED
**Goal**: Working LEAF scores with native status integration

- [x] Design: Point → Ecoregion → Union Pool → Percentile scoring
- [x] Design: WCVP native/introduced integration
- [x] Test query on Appalachian-Blue Ridge (1,279 species, 170 introduced excluded)
- [ ] Add index on `eco_id` column for performance
- [ ] Implement full query with WCVP region mapping
- [ ] Create API endpoint: `GET /api/leaf/score`
- [ ] Test on all 12 target bioregional ecoregions
- [ ] CSV export for campaign distribution

**Data Used**:
- Geohash tiles with eco_id (97% coverage)
- WCVP native status (97.5% coverage)
- WCVP introduced status (8.4% coverage) - for exclusion
- WCVP region mappings (US states, Canadian provinces, etc.)

### v1.1 - Biome Matching
**Goal**: Add ecological appropriateness filter

- [ ] Add biome match modifier: `× 1.2` if species.biomes includes ecoregion.biome_name
- [ ] Add biome mismatch penalty: `× 0.8` if no biome match
- [ ] Include biome_match flag in API response

**Data Used**: species.biomes (90% coverage), ecoregions.biome_name

### v1.2 - Commercial Penalty
**Goal**: Discourage monoculture species

- [ ] Add commercial penalty: `× 0.7` if comercialspecies_lower = 'YES'
- [ ] Include is_commercial flag in API response

**Data Used**: species.comercialspecies_lower (~2.2% flagged)

### v1.3 - Family Diversity Quotas
**Goal**: Ensure taxonomic diversity in recommendations

- [ ] Post-filter: Cap at 15-20 species per family in BEST tier
- [ ] Redistribute slots to next-highest-scoring species from underrepresented families
- [ ] Report family distribution in API response

**Data Used**: species.family (100% coverage)

### v1.4 - Invasive Species Layer (Future)
**Goal**: Add explicit invasive species data when available

- [ ] Integrate invasive species data (when available from Marina)
- [ ] Add invasive_status flag alongside introduced exclusion
- [ ] Consider regional invasive lists (state/country-specific)

**Data Required**: Invasive species dataset (in progress)

### v2.0 - Combined Confidence Scoring
**Goal**: Combine occurrence data + native status for confidence scoring

- [ ] Weight species by both occurrence abundance AND native status match
- [ ] Native + high occurrence = highest confidence
- [ ] Native + low occurrence = medium confidence (rare but appropriate)
- [ ] Non-native + high occurrence = flag as potentially naturalized/invasive

### v3.0 - Environmental Matching
**Goal**: Add soil, climate, elevation compatibility

- [ ] Integrate WorldClim bioclimatic variables
- [ ] Integrate SoilGrids 250m
- [ ] Species-environment preference matching

**Data Required**: Environmental layer integration

---

## API Design

### MVP Endpoint

```yaml
GET /api/leaf/score

Query Parameters:
  lat: float (required) - Latitude
  lng: float (required) - Longitude
  # OR
  eco_id: int - Direct ecoregion ID (alternative to lat/lng)

  # Optional filters
  limit: int (default: 100) - Max species to return
  min_score: float (default: 50) - Minimum LEAF score
  tier: string - Filter to specific tier (BEST, GOOD, ACCEPTABLE)

Response:
  location:
    lat: 35.5951
    lng: -82.5515

  ecoregion:
    eco_id: 331
    eco_name: "Appalachian-Blue Ridge forests"
    biome_name: "Temperate Broadleaf & Mixed Forests"
    realm: "Nearctic"

  methodology:
    version: "1.0-mvp"
    threshold: 0.0005
    scoring: "percentile"
    formula: "occurrence_count × tile_count"

  statistics:
    total_species_in_ecoregion: 2847
    species_above_threshold: 980
    total_occurrences: 1247832

  species:
    - taxon_id: "AngMaFaFaLg47652-01"
      scientific_name: "Quercus rubra"
      common_name: "Red Oak"
      family: "Fagaceae"
      leaf_score: 97.2
      tier: "BEST"
      occurrence_count: 12307
      tile_count: 1845
      affinity: 22706415
      occurrence_share: 0.0099

    - taxon_id: "..."
      ...
```

### Batch Endpoint (Future)

```yaml
POST /api/leaf/score/batch

Request Body:
  locations:
    - lat: 35.5951, lng: -82.5515
    - lat: -23.5505, lng: -46.6333

Response:
  results:
    - location: {...}
      ecoregion: {...}
      top_species: [...]
    - ...
```

---

## Data Infrastructure

### What We Have (MVP-Ready)

| Asset | Count | Coverage | Notes |
|-------|-------|----------|-------|
| Geohash tiles | 5.3M | 97% have eco_id | Pre-indexed for fast queries |
| Species occurrences | 89.3M | In JSONB per tile | Aggregatable |
| WWF Ecoregions | 847 | Global | Boundaries + metadata |
| Species biomes | ~61K | 90% | For v1.1 biome matching |
| Commercial flags | ~1.5K | 2.2% flagged | For v1.2 penalty |
| Family taxonomy | 67.9K | 100% | For v1.3 diversity quotas |
| **WCVP native status** | 66,220 | **97.5%** | For v1.4 native filtering (NEW) |
| **WCVP introduced status** | 5,738 | 8.4% | For introduced flagging (NEW) |

### Key Index Requirement

```sql
-- CRITICAL: Add index on eco_id for LEAF queries
CREATE INDEX IF NOT EXISTS idx_geohash_tiles_eco_id
ON geohash_species_tiles(eco_id);
```

---

## Target Ecoregions (12 Bioregional Campaigns)

| Ecoregion | Countries | Status |
|-----------|-----------|--------|
| Appalachian-Blue Ridge forests | USA | Ready |
| Central African mangroves | 7 countries | Ready |
| Cross-Niger transition forests | Nigeria | Ready |
| Cross-Sanaga-Bioko coastal forests | 3 countries | Ready |
| Guinean forest-savanna | 12 countries | Ready |
| Niger Delta swamp forests | Nigeria | Ready |
| Nigerian lowland forests | 2 countries | Ready |
| Dry Chaco | 4 countries | Ready |
| Southern Andean Yungas | ARG, BOL | Ready |
| Eastern Cordillera Real montane forests | 3 countries | Ready |
| Serra do Mar coastal forests | Brazil | Ready |
| Tyrrhenian-Adriatic sclerophyllous forests | 4 countries | Ready |

**Funding**: $100,000 allocation depends on scientifically defensible species lists

---

## Success Metrics

### MVP
- [ ] LEAF scores generated for all 12 target ecoregions
- [ ] API response time < 3 seconds per ecoregion
- [ ] CSV exports ready for campaign distribution
- [ ] Scores validated against known ecological patterns

### v1.x
- [ ] Biome matching improves ecological appropriateness
- [ ] No commercial-only species in BEST tier
- [ ] No family exceeds 15% of BEST tier recommendations
- [ ] Domain expert validation of top recommendations

---

## Related Documentation

- **[docs/RECOMMENDATION_SERVICE.md](../RECOMMENDATION_SERVICE.md)** - Detailed implementation specs
- **[docs/SPECIES_NATIVE_STATUS_ROADMAP.md](../SPECIES_NATIVE_STATUS_ROADMAP.md)** - Long-term SLAS vision
- **[TODO.md](../../TODO.md)** - Current task breakdown
- **[API.md](../../API.md)** - API endpoint documentation

---

**Document Version**: 2.0
**Last Updated**: December 2025
**Status**: Planning Complete → Implementation

**Trademark**: LEAF™ (Location-based Ecological Aptness Forecast) is a Treekipedia feature.
