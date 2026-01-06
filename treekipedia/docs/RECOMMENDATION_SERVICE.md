# Treekipedia Species Recommendation Service

## Executive Summary

The Treekipedia Species Recommendation Service combines geospatial occurrence data, deep species knowledge, semantic relationships, and data-driven ecological analysis to provide intelligent, zone-specific tree species recommendations. This document outlines the implementation plan for building this service on top of Treekipedia's existing infrastructure.

### Core Value Proposition
An intelligent recommendation engine that answers: **"What trees should I plant here?"** with scientifically-grounded, ecologically-appropriate, and practically-viable species suggestions tailored to specific ecoregions and use cases.

### Primary Use Case: Bioregional Reforestation Campaigns
**Mission-critical application**: Generate approved species lists for 12 bioregional reforestation campaigns backed by $100,000 in funding. This system must prevent extractive monoculture greenwashing and prioritize ecologically-sound, biodiverse restoration.

## Current Infrastructure (October 2025)

### ✅ What We Have Today

#### 1. Geospatial Infrastructure
- **PostGIS 3.2** enabled PostgreSQL database
- **5.3M geohash tiles** with species occurrence data (Level 7, ~150m resolution)
- **89.3M occurrence records** compressed into tiles
- **847 WWF ecoregions** with spatial boundaries integrated
- **242 country polygons** for native status analysis
- **Spatial query capabilities** via PostGIS functions

#### 2. Species Knowledge Base
- **67,743 total species** (50,797 species + 16,946 subspecies)
- **61,142 species (90%)** have ecoregion data
- **17,405 species (26%)** have native country data
- **48,081 species (71%)** have functional ecosystem group data
- **100% coverage** on vegetation type
- **993 species** flagged as present in intact forests
- **1,524 species** identified as commercial species

#### 3. Knowledge Graph (Apache Jena Fuseki)
- **Apache Jena Fuseki** RDF triple store running on port 3030
- **Populated ontology** with option sets for ecological attributes
- **SPARQL query capabilities** for semantic relationships
- **Species relationship modeling** for companion planting and ecological guilds

#### 4. Data Quality Reality Check

**Well-Populated Fields:**
- `biomes`: 90% coverage
- `vegetationtype`: 100% coverage
- `functional_ecosystem_groups`: 71% coverage
- `countries_native`: 26% coverage
- `ph_prefered`: 24% coverage
- `soil_texture_prefered`: 34% coverage
- `present_intact_forest`: 993 species flagged
- `comercialspecies_lower`: 1,524 species flagged

**Not Yet Populated (all 0%):**
- Conservation status AI
- Elevation ranges AI
- Habitat AI
- Successional stage
- Growth form AI
- Forest layers
- Ecological function AI
- Associated species

**Key Insight**: Many fields show 100% populated in database but values are literal string "NA" - actual usable data is significantly less.

## Implementation Phases

### Phase 0: Bioregional Campaign Lists (IMPLEMENTED)
**Timeline: October 2025**
**Status: Foundation complete, scoring system in development**
**Priority: CRITICAL - $100K funding decisions**

#### Target Ecoregions (12 Total)
1. Appalachian-Blue Ridge forests (USA) - 980 native species
2. Central African mangroves (7 countries) - 1,458 species
3. Cross-Niger transition forests (Nigeria) - 188 species
4. Cross-Sanaga-Bioko coastal forests (3 countries) - 2,186 species
5. Guinean forest-savanna (12 countries) - 2,295 species
6. Niger Delta swamp forests (Nigeria) - 67 species
7. Nigerian lowland forests (2 countries) - 1,192 species
8. Dry Chaco (4 countries) - 1,614 species
9. Southern Andean Yungas (Argentina, Bolivia) - 958 species
10. Eastern Cordillera Real montane forests (3 countries) - 4,761 species
11. Serra do Mar coastal forests (Brazil) - 3,451 native species
12. Tyrrhenian-Adriatic sclerophyllous forests (4 countries) - 1,462 species

#### 0.1 Working API Endpoint

**Endpoint**: `GET /api/geospatial/ecoregions/native-species/:ecoregion_name`

**Parameters:**
- `native_only` (default: true) - Filter to native species only
- `exclude_invasive` (default: true) - Exclude invasive species
- `limit` (default: 1000) - Maximum species to return

**Implementation:**
```javascript
// Example API call
GET /api/geospatial/ecoregions/native-species/Serra%20do%20Mar%20coastal%20forests

// Response structure
{
  "ecoregion": {
    "eco_id": "500",
    "eco_name": "Serra do Mar coastal forests",
    "biome_name": "Tropical & Subtropical Moist Broadleaf Forests",
    "realm": "Neotropic",
    "area_km2": 104609
  },
  "countries_in_ecoregion": ["Brazil"],
  "filters_applied": {
    "native_only": true,
    "exclude_invasive": true
  },
  "species_count": 3451,
  "species": [
    {
      "taxon_id": "...",
      "taxon_full": "...",
      "scientific_name": "...",
      "common_name": "...",
      "family": "...",
      "genus": "..."
    }
  ]
}
```

**How It Works:**
1. PostGIS spatial join: Find countries intersecting ecoregion
2. Country name normalization: Handle "United States of America" → "United States"
3. Species.ecoregions LIKE match: Find species listing that ecoregion
4. Native status check: `countries_native` must include at least one country from ecoregion
5. Invasive exclusion: Filter out species where `countries_invasive` includes ecoregion countries

#### 0.2 Occurrence-Based Scoring System (IN DEVELOPMENT)

**The Problem**:
Native-by-country is too broad. The USA is huge - a species native to Florida shouldn't necessarily be recommended for the Appalachians.

**The Solution**:
Use actual GBIF occurrence data from geohash tiles to measure which species are **abundant and established** in each specific ecoregion.

**Scoring Factors:**

1. **OCCURRENCE COUNT** (weight: 0.30)
   - Sum of GBIF occurrences from all geohash tiles intersecting the ecoregion
   - Raw abundance metric
   - Example: Acer rubrum in Appalachian-Blue Ridge = 1,518 occurrences

2. **TILE DISTRIBUTION** (weight: 0.25)
   - Number of distinct geohash tiles where species occurs
   - Spatial distribution metric
   - Example: Acer rubrum present in 241 distinct tiles
   - Benefit: Distinguishes widespread vs. localized species

3. **OCCURRENCE DENSITY** (derived metric)
   - `occurrence_count / tile_count`
   - Example: 1,518 / 241 = 6.3 occurrences per tile
   - Distinguishes "common & abundant" from "rare & scattered"

4. **BIOME MATCHING** (weight: 0.20)
   - Does species.biomes include ecoregion.biome_name?
   - Ecological appropriateness beyond geography
   - Bonus points if biome matches

5. **INTACT FOREST PRESENCE** (weight: 0.15)
   - Bonus for `present_intact_forest = 'YES'`
   - Prioritizes species from undisturbed ecosystems
   - Limited data: only 993 species flagged

6. **COMMERCIAL PENALTY** (weight: -0.20)
   - Penalize or exclude `comercialspecies_lower = 'YES'`
   - Anti-monoculture stance
   - Prevents timber plantation greenwashing
   - 1,524 species flagged as commercial

7. **FAMILY DIVERSITY QUOTA** (weight: 0.10)
   - After scoring, cap species per family (e.g., max 15-20 per family)
   - Prevents taxonomic monoculture
   - Example: Appalachian has 362 Rosaceae species - too dominant
   - Ensures biodiversity across taxonomic groups

**Three-Tier Output:**

- **BEST (Top 10-15 species)**: High occurrence count + wide distribution + biome match + not commercial + intact forest presence
- **GOOD (Next 30-40 species)**: Medium occurrence + biome match OR intact forest + limited commercial
- **ACCEPTABLE (Remaining)**: Native + occurs in ecoregion, fills ecosystem diversity gaps

**Query Structure:**
```sql
WITH ecoregion_tiles AS (
  -- Get all geohash tiles intersecting ecoregion boundary
  SELECT gst.species_data, gst.geohash_l7
  FROM geohash_species_tiles gst
  JOIN ecoregions e ON ST_Intersects(gst.geometry, e.geom)
  WHERE e.eco_name = 'Appalachian-Blue Ridge forests'
),
species_occurrences AS (
  -- Aggregate occurrence counts per species
  SELECT
    key as taxon_id,
    SUM(value::int) as occurrence_count,
    COUNT(DISTINCT geohash_l7) as tile_count,
    SUM(value::int)::float / COUNT(DISTINCT geohash_l7) as occurrence_density
  FROM ecoregion_tiles,
  LATERAL jsonb_each_text(species_data)
  GROUP BY key
)
SELECT
  so.*,
  s.species_scientific_name,
  s.biomes,
  s.present_intact_forest,
  s.comercialspecies_lower,
  s.family,
  -- Calculate composite score
  (so.occurrence_count * 0.30) +
  (so.tile_count * 0.25) +
  (CASE WHEN s.biomes LIKE '%' || e.biome_name || '%' THEN 20 ELSE 0 END) +
  (CASE WHEN s.present_intact_forest = 'YES' THEN 15 ELSE 0 END) +
  (CASE WHEN s.comercialspecies_lower = 'YES' THEN -20 ELSE 0 END) as composite_score
FROM species_occurrences so
JOIN species s ON s.taxon_id = so.taxon_id
JOIN ecoregions e ON e.eco_name = 'Appalachian-Blue Ridge forests'
ORDER BY composite_score DESC;
```

#### 0.3 CSV Export Format

**Columns:**
- `taxon_id` - Unique identifier
- `taxon_full` - Full name including subspecies
- `scientific_name` - Species name
- `common_name` - Common names
- `family` - Taxonomic family
- `genus` - Taxonomic genus
- `tier` - BEST / GOOD / ACCEPTABLE
- `composite_score` - Calculated suitability score
- `occurrence_count` - Number of GBIF occurrences in ecoregion
- `tile_count` - Number of geohash tiles with occurrences
- `occurrence_density` - Occurrences per tile

### Phase 1: Enhanced Filtering (NEXT STEPS)
**Timeline: Weeks**
**Status: Design complete, implementation pending**

#### 1.1 Functional Group Diversity
- Ensure species lists include diverse functional roles
- Nitrogen fixers, canopy species, understory, pioneer species
- Prevent ecological monoculture
- Data available for 48,081 species (71%)

#### 1.2 Family Diversity Enforcement
- Implement hard caps on species per family
- Example: Max 15-20 Rosaceae in any list
- Ensures taxonomic diversity
- Automatic in scoring system

#### 1.3 Biome Validation
- Strict filtering: species.biomes MUST include ecoregion.biome_name
- Removes ecologically inappropriate species
- 90% data coverage

### Phase 2: Apache Jena Fuseki Integration
**Timeline: 2-3 months**
**Status: Infrastructure ready, API integration needed**

#### 2.1 RESTful API Wrapper for SPARQL
- Query Fuseki at http://localhost:3030
- Pre-built query templates for common relationships
- Ontology management for ecological attributes

#### 2.2 Companion Species Networks
```sparql
PREFIX tree: <http://treekipedia.org/ontology/>
PREFIX eco: <http://purl.org/eco/ontology/>

SELECT ?companion ?companionName ?function
WHERE {
  ?target tree:taxonId "AngMaAcac12345-00" .
  ?target eco:hasEcologicalAssociation ?association .
  ?association eco:hasCompanion ?companion .
  ?companion tree:commonName ?companionName .
  ?companion eco:hasFunction ?function .
  FILTER(?function = eco:NitrogenFixation)
}
```

#### 2.3 Ecological Guild Recommendations
- Query for species sharing functional roles
- Successional stage compatibility
- Polyculture design support

### Phase 3: Environmental Layer Integration
**Timeline: 3-6 months**
**Status: Future development**

#### 3.1 Additional Geospatial Datasets
- **Soil data layers**: pH, texture, moisture (USDA SSURGO, FAO)
- **Climate zones**: Köppen-Geiger classification
- **Elevation models**: SRTM/ASTER DEM
- **Future climate projections**: CMIP6 scenarios for 2050, 2100

#### 3.2 Raster/Vector Integration
```sql
WITH location_environment AS (
  SELECT
    ST_Value(soil_ph_raster, point) as soil_ph,
    ST_Value(precipitation_raster, point) as annual_precip,
    ecoregion_id
  FROM environmental_layers
  WHERE ST_Intersects(ecoregion_polygons, ST_SetSRID(ST_MakePoint($1, $2), 4326))
)
SELECT s.*, le.soil_ph, le.annual_precip
FROM species s, location_environment le
WHERE s.ph_prefered::float BETWEEN le.soil_ph - 0.5 AND le.soil_ph + 0.5;
```

### Phase 4: AI Research Integration
**Timeline: 6-12 months**
**Status: Conceptual**

#### 4.1 AI-Driven Gap Filling
- For species with limited data, use AI research to fill knowledge gaps
- Ecological function inference
- Companion species discovery
- Risk assessment

#### 4.2 AI Synthesis for Complex Queries
```javascript
const synthesizeRecommendations = async (candidateSpecies, locationData, userRequirements) => {
  const prompt = `
    You are an expert ecological advisor synthesizing tree planting recommendations.

    CANDIDATE SPECIES (top 50 by occurrence-based score):
    ${candidateSpecies.map(species => `
      ${species.scientific_name}:
      - Occurrences in ecoregion: ${species.occurrence_count}
      - Spatial distribution: ${species.tile_count} tiles
      - Biome match: ${species.biome_match}
      - Intact forest presence: ${species.intact_forest}
    `).join('\n')}

    Generate final ranked list with:
    1. Ecological rationale for each recommendation
    2. Companion species suggestions
    3. Implementation timeline
    4. Risk factors
  `;

  return await callClaude(prompt);
};
```

## API Design

### Implemented Endpoints

#### GET /api/geospatial/ecoregions/native-species/:ecoregion_name
Returns native species for a specific WWF ecoregion.

**Query Parameters:**
- `native_only` (boolean, default: true)
- `exclude_invasive` (boolean, default: true)
- `limit` (integer, default: 1000)

**Response:**
```json
{
  "ecoregion": {
    "eco_id": "331",
    "eco_name": "Appalachian-Blue Ridge forests",
    "biome_name": "Temperate Broadleaf & Mixed Forests",
    "realm": "Nearctic",
    "area_km2": 163311
  },
  "countries_in_ecoregion": ["United States"],
  "filters_applied": {
    "native_only": true,
    "exclude_invasive": true
  },
  "species_count": 980,
  "species": [...]
}
```

### Planned Endpoints

#### POST /api/recommendations/ecoregion-scored
Returns scored and tiered species list for ecoregion with occurrence data.

**Request:**
```json
{
  "ecoregion_name": "Serra do Mar coastal forests",
  "filters": {
    "exclude_commercial": true,
    "biome_match_required": true,
    "intact_forest_priority": true,
    "max_species_per_family": 20
  },
  "output": {
    "tiers": true,
    "include_occurrence_data": true,
    "include_functional_groups": true
  }
}
```

**Response:**
```json
{
  "ecoregion": {...},
  "scoring_methodology": {
    "occurrence_weight": 0.30,
    "distribution_weight": 0.25,
    "biome_match_weight": 0.20,
    "intact_forest_weight": 0.15,
    "commercial_penalty": -0.20,
    "family_diversity_quota": 20
  },
  "recommendations": {
    "best": [
      {
        "taxon_id": "...",
        "scientific_name": "...",
        "composite_score": 87.5,
        "occurrence_count": 1234,
        "tile_count": 156,
        "occurrence_density": 7.9,
        "biome_match": true,
        "intact_forest": true,
        "commercial": false,
        "family": "Fabaceae"
      }
    ],
    "good": [...],
    "acceptable": [...]
  },
  "statistics": {
    "total_native_species": 3451,
    "scored_species": 3451,
    "best_tier_count": 12,
    "good_tier_count": 38,
    "acceptable_tier_count": 3401,
    "families_represented": 145
  }
}
```

## Success Metrics

### Technical Performance
- Query response time < 3 seconds for native species lists
- Occurrence scoring computation < 10 seconds for any ecoregion
- 95%+ uptime for all endpoints
- CSV export generation < 5 seconds

### Scientific Integrity
- **Anti-monoculture**: No family exceeds 15% of any recommendation list
- **Ecological appropriateness**: 100% biome matching for BEST tier
- **Native status accuracy**: 100% verified against spatial country intersections
- **Commercial filtering**: 0 purely commercial species in BEST tier

### Mission Impact (Bioregional Campaigns)
- **$100K funding allocation**: Species lists scientifically defensible
- **12 ecoregion campaigns**: Complete approved species lists delivered
- **Biodiversity assurance**: Each list represents >50 taxonomic families
- **Greenwashing prevention**: Commercial species flagged and penalized

## Implementation Timeline

### Completed (October 2025)
- ✅ Native species by ecoregion API endpoint
- ✅ Country-ecoregion spatial intersection
- ✅ Invasive species filtering
- ✅ Data quality analysis
- ✅ Occurrence-based scoring algorithm design

### In Progress (Days)
- 🔄 Implement occurrence counting from geohash tiles
- 🔄 Add biome matching filter
- 🔄 Apply family diversity quotas
- 🔄 Generate three-tier classifications
- 🔄 CSV export with scoring metadata

### Next Steps (Weeks)
- ⏳ Test all 12 target ecoregions
- ⏳ Functional group diversity analysis
- ⏳ Intact forest prioritization
- ⏳ API documentation and examples

### Future Development (Months)
- ⏳ Apache Jena Fuseki API integration
- ⏳ Companion species queries
- ⏳ Environmental layer integration
- ⏳ AI synthesis for complex recommendations

## Conclusion

The Treekipedia Species Recommendation Service is being built with a **data-first, scientifically-defensible approach** that prioritizes actual ecological occurrence patterns over theoretical compatibility. By leveraging 89.3 million GBIF occurrence records compressed into geohash tiles, we can identify which species are truly **abundant and established** in each ecoregion, not just theoretically present.

The immediate focus on **bioregional reforestation campaigns** ensures that the first implementation delivers high-stakes, real-world value: preventing monoculture greenwashing and directing $100,000 in funding toward ecologically sound, biodiverse restoration projects.

This phased approach allows immediate delivery of foundational capabilities while building toward a comprehensive ecosystem planning platform that integrates semantic relationships, environmental layers, and AI synthesis for increasingly sophisticated recommendations.
