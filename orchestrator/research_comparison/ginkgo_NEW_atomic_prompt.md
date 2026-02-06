
================================================================================
TREEKIPEDIA ATOMIC RESEARCH - Ginkgo biloba
================================================================================

Family: GINKGOACEAE
Native to: China Southeast
Taxon ID: GymGiGiGnKg50344-00

================================================================================
CRITICAL: ATOMIC INSIGHTS MODEL
================================================================================

Generate MULTIPLE SEPARATE insights for fields that have multiple distinct facts.

WRONG (old way - combining into one blob):
```json
{
  "claim_type": "cultural_significance",
  "claim_value": {"text": "Sacred in Buddhism. Also survived Hiroshima. Used in TCM."},
  "confidence": 0.85
}
```

CORRECT (new way - atomic insights):
```json
[
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Sacred in Buddhism - monks preserved species through temple plantings", "context": "Buddhism", "region": "East Asia"},
    "confidence": 0.95,
    "sources": [{"url": "...", "title": "Buddhist temple records"}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Six trees survived 1945 Hiroshima atomic bomb, now symbols of peace", "context": "Japanese post-war", "region": "Japan"},
    "confidence": 0.98,
    "sources": [{"url": "...", "title": "Hiroshima Peace Memorial"}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Traditional Chinese medicine uses leaves for memory enhancement", "context": "TCM", "region": "China"},
    "confidence": 0.88,
    "sources": [{"url": "...", "title": "TCM pharmacopoeia"}]
  }
]
```

Each insight is:
- ONE atomic, citable fact
- Independently sourced
- Independently scored for confidence
- Queryable by context/region

================================================================================
FIELD TYPES AND INSTRUCTIONS
================================================================================

**MULTI-INSIGHT FIELDS** (generate multiple insights):

For these fields, generate MULTIPLE separate insights:

1. **cultural_significance** - One insight per culture/tradition/use
   - claim_value: {{"text": "...", "context": "Buddhism|Indigenous|historical", "region": "..."}}
   - Example: 3 insights for Buddhist, Shinto, and medicinal significance

2. **associated_species** - One insight per ecological community/association
   - claim_value: {{"text": "...", "community_type": "...", "species_list": [...]}}
   - Example: 2 insights for "temperate forest understory" and "riparian zone"

3. **habitat** - One insight per distinct habitat type
   - claim_value: {{"text": "...", "biome": "...", "vegetation_type": "..."}}
   - Example: 2 insights for "lowland rainforest" and "montane cloud forest"

4. **agroforestry_use_cases** - One insight per system type
   - claim_value: {{"text": "...", "system": "silvopasture|alley cropping|windbreak", "benefits": [...]}}

5. **non_timber_products** - One insight per product category
   - claim_value: {{"text": "...", "product_type": "medicinal|food|fiber|resin", "uses": [...]}}

6. **ecological_function** - One insight per ecosystem service
   - claim_value: {{"text": "...", "function": "nitrogen fixation|wildlife habitat|soil stabilization"}}

7. **native_adapted_habitats** - One insight per region/climate zone
   - claim_value: {{"text": "...", "region": "...", "climate_zone": "..."}}

8. **disease_pest_management** - One insight per disease/pest
   - claim_value: {{"text": "...", "problem_type": "disease|pest", "name": "...", "management": "..."}}

9. **stewardship_best_practices** - One insight per practice category
   - claim_value: {{"text": "...", "category": "watering|fertilizing|protection"}}

10. **tolerances** - One insight per tolerance type
    - claim_value: {{"text": "...", "tolerance_type": "drought|salt|flood|shade", "level": "low|moderate|high"}}


**RANKED LIST FIELDS** (generate ranked items):

For these fields, generate ranked items:

1. **popular_common_name** - One insight per name, ranked by popularity
   - claim_value: {{"name": "...", "rank": 1, "languages": ["en"], "regions": ["UK"]}}
   - Rank 1 = most commonly used name
   - Include names in multiple languages

2. **synonyms** - One insight per synonym
   - claim_value: {{"name": "...", "rank": 1, "authority": "L.", "year": 1753, "type": "basionym|homotypic|heterotypic"}}
   - Rank by taxonomic importance (basionym first)

3. **identification_features** - One insight per key feature, ranked by diagnostic value
   - claim_value: {{"text": "...", "rank": 1, "feature_type": "leaf|bark|flower|fruit"}}
   - Rank 1 = most diagnostic feature


**SINGLE VALUE FIELDS** (generate one insight):

For these fields, generate ONE insight with the most authoritative value:

- **conservation_status**: {{"iucn_status": "LC|NT|VU|EN|CR", "iucn_year": 2024, "population_trend": "...", "text": "..."}}
- **growth_form**: {{"primary": "tree|shrub|palm", "habit": "erect|spreading", "text": "..."}}
- **leaf_type**: {{"type": "simple|compound|needle", "arrangement": "alternate|opposite", "text": "..."}}
- **deciduous_evergreen**: {{"type": "deciduous|evergreen|semi-deciduous", "text": "..."}}
- **flower_color**: {{"primary": "...", "secondary": "...", "text": "..."}}
- **fruit_type**: {{"type": "drupe|berry|capsule|nut", "edible": true/false, "text": "..."}}
- **bark_characteristics**: {{"texture": "smooth|fissured|scaly", "color": "...", "text": "..."}}
- **maximum_height**: {{"value": 40, "unit": "meters", "typical_range": "20-30", "text": "..."}}
- **maximum_diameter**: {{"value": 2, "unit": "meters", "text": "..."}}
- **lifespan**: {{"category": "short-lived|medium|long-lived", "typical_years": "50-100", "text": "..."}}
- **maximum_tree_age**: {{"value": 500, "unit": "years", "text": "..."}}
- **general_description**: {{"text": "2-3 sentence botanical description"}}
- **etymology**: {{"genus_meaning": "...", "species_meaning": "...", "named_for": "..."}}
- **elevation_ranges**: {{"min_m": 0, "max_m": 2000, "optimal_m": 500, "text": "..."}}
- **compatible_soil_types**: {{"preferred": [...], "tolerated": [...], "ph_range": "5.5-7.0", "text": "..."}}
- **climate_tolerance**: {{"temp_min_c": -15, "temp_max_c": 40, "rainfall_mm": "500-1500", "text": "..."}}
- **planting_recipes**: {{"spacing": "...", "soil_prep": "...", "best_season": "...", "text": "..."}}
- **pruning_maintenance**: {{"frequency": "...", "best_time": "...", "text": "..."}}
- **fire_management**: {{"tolerance": "low|moderate|high", "response": "resprouter|seeder", "text": "..."}}
- **propagation_methods**: {{"primary": "seed|cutting|grafting", "methods": [...], "text": "..."}}
- **timber_value**: {{"quality": "low|medium|high", "uses": [...], "commercial": true/false, "text": "..."}}
- **nutritional_caloric_value**: {{"edible_parts": [...], "nutritional_info": "...", "text": "..."}}


================================================================================
OUTPUT FORMAT
================================================================================

Return ONLY valid JSON:

{
  "taxon_id": "GymGiGiGnKg50344-00",
  "species_name": "Ginkgo biloba",
  "research_date": "2026-01-07",
  "model_version": "research-agent",
  "insights": [
    // MULTI-INSIGHT EXAMPLE (cultural_significance)
    {
      "claim_type": "cultural_significance",
      "claim_value": {
        "text": "Specific cultural fact here",
        "context": "Buddhism|Christianity|Indigenous|etc",
        "region": "Geographic scope"
      },
      "confidence": 0.95,
      "sources": [{"url": "...", "title": "...", "credibility": 0.9}]
    },
    // More cultural_significance insights...

    // RANKED LIST EXAMPLE (popular_common_name)
    {
      "claim_type": "popular_common_name",
      "claim_value": {
        "name": "English Oak",
        "rank": 1,
        "languages": ["en"],
        "regions": ["UK", "Ireland"]
      },
      "confidence": 0.95,
      "sources": [...]
    },
    {
      "claim_type": "popular_common_name",
      "claim_value": {
        "name": "Pedunculate Oak",
        "rank": 2,
        "languages": ["en"],
        "regions": ["scientific"]
      },
      "confidence": 0.85,
      "sources": [...]
    },

    // SINGLE VALUE EXAMPLE (conservation_status)
    {
      "claim_type": "conservation_status",
      "claim_value": {
        "iucn_status": "LC",
        "iucn_year": 2024,
        "population_trend": "stable",
        "text": "Least Concern - widespread and abundant"
      },
      "confidence": 0.98,
      "sources": [{"url": "https://iucnredlist.org/...", "title": "IUCN Red List"}]
    }
  ]
}

================================================================================
CONFIDENCE SCORING
================================================================================

Base confidence on SOURCE QUALITY, not self-assessment:
- 3+ authoritative sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source (IUCN, POWO, GBIF) → 0.75-0.85
- 1 secondary source → 0.55-0.70
- No verifiable source → 0.30-0.50 (include anyway if valuable)

================================================================================
BEGIN RESEARCH
================================================================================

Research "Ginkgo biloba" comprehensively.
For multi-insight fields, generate SEPARATE insights for each distinct fact.
For ranked fields, include rank numbers and order by popularity/importance.
For single-value fields, provide the most authoritative answer.

