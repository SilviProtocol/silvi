# LEAF™ - Location-based Ecological Aptness Forecast

**Status**: Planning Complete → Implementation
**Priority**: HIGH - Critical for $100K bioregional campaigns
**Related TODO Section**: `[IN PROGRESS] - LEAF Scoring Engine`

---

## Overview

The **Treekipedia LEAF™** (Location-based Ecological Aptness Forecast) is a scoring system that answers: **"What trees should I plant here?"**

LEAF provides scientifically-grounded, occurrence-based species recommendations for any location on Earth, with built-in safeguards against monoculture greenwashing.

**Key Innovation**: Uses 89.3M GBIF occurrences compressed into 5.3M geohash tiles to measure which species are truly **abundant and established** in each ecological zone, not just theoretically present.

**Design Philosophy**: Start simple with existing data, iterate and improve. The occurrence data IS the signal - species that appear frequently across many tiles are *de facto* well-suited to that ecological context.

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
Aggregate Occurrences (all tiles in ecoregion)
    ↓
Apply Minimum Threshold (0.05% of total occurrences)
    ↓
Calculate Affinity (occurrence_count × tile_count)
    ↓
Convert to Percentile (0-100 LEAF score)
    ↓
Tier Results (BEST / GOOD / ACCEPTABLE)
```

### The Affinity Formula

```
affinity = occurrence_count × tile_count
```

This single metric captures both:
- **Abundance**: How many times has this species been observed?
- **Distribution**: How widespread is it across the ecoregion?

Species that are both **common AND widespread** score highest. This is a robust proxy for "well-established in this ecological context."

### The 0.05% Threshold

Species must account for at least **0.05% of total occurrences** in the ecoregion to be considered.

**Why this is elegant**:
- **Self-calibrating**: Richer ecoregions have higher absolute thresholds
- **Filters noise**: Eliminates species with sparse, potentially erroneous records
- **Relative consistency**: Same 0.05% bar everywhere

**Examples**:
- Ecoregion with 1,000,000 occurrences → minimum 500 occurrences to qualify
- Ecoregion with 50,000 occurrences → minimum 25 occurrences to qualify

---

## MVP Implementation

### Core SQL Query

```sql
WITH ecoregion_occurrences AS (
  -- Aggregate all species occurrences for this ecoregion
  SELECT
    (jsonb_each_text(species_data)).key AS taxon_id,
    SUM((jsonb_each_text(species_data)).value::int) AS occurrence_count,
    COUNT(DISTINCT geohash_l7) AS tile_count
  FROM geohash_species_tiles
  WHERE eco_id = $1
  GROUP BY taxon_id
),
totals AS (
  SELECT SUM(occurrence_count) AS total_occurrences
  FROM ecoregion_occurrences
),
filtered AS (
  -- Apply 0.05% minimum threshold
  SELECT
    eo.taxon_id,
    eo.occurrence_count,
    eo.tile_count,
    eo.occurrence_count::float / t.total_occurrences AS occurrence_share
  FROM ecoregion_occurrences eo, totals t
  WHERE eo.occurrence_count::float / t.total_occurrences >= 0.0005
),
scored AS (
  -- Calculate affinity and percentile rank
  SELECT
    f.*,
    f.occurrence_count * f.tile_count AS affinity,
    PERCENT_RANK() OVER (ORDER BY f.occurrence_count * f.tile_count) * 100 AS leaf_score
  FROM filtered f
)
SELECT
  s.*,
  sp.species_scientific_name,
  sp.common_name,
  sp.family,
  sp.biomes
FROM scored s
JOIN species sp ON sp.taxon_id = s.taxon_id
ORDER BY leaf_score DESC;
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

### MVP (Current Sprint)
**Goal**: Working LEAF scores using existing data

- [x] Design: Point → Ecoregion → Percentile scoring
- [ ] Implement occurrence aggregation query
- [ ] Apply 0.05% threshold filtering
- [ ] Calculate affinity and percentile scores
- [ ] Create API endpoint: `GET /api/leaf/score`
- [ ] Test on 12 target bioregional ecoregions
- [ ] CSV export for campaign distribution

**Data Used**: Existing geohash tiles, eco_id assignments, species table

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

### v1.4 - WCVP Native Status Filtering ✅ DATA READY
**Goal**: Filter to verified native species using authoritative WCVP data

- [x] Import WCVP native/introduced data (66,220 species - 97.5% coverage)
- [ ] Update native species API to use `wcvp_native` instead of `countries_native`
- [ ] Filter LEAF results to species native to ecoregion's countries
- [ ] Flag `wcvp_introduced` species with warning
- [ ] Include native_status in API response

**Data Used**: species.wcvp_native (97.5% coverage), species.wcvp_introduced (8.4% coverage)
**Source**: WCVP (World Checklist of Vascular Plants) - Kew Gardens

### v1.5 - Invasive Species Exclusion
**Goal**: Exclude known invasive species from recommendations

- [ ] Integrate invasive species data (when available from Marina)
- [ ] Hard exclude invasives from all tiers
- [ ] Include invasive_status flag in API response

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
