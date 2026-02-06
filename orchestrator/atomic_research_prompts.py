#!/usr/bin/env python3
"""
Atomic Research Prompts for Treekipedia
=======================================
Generates MULTIPLE atomic insights per claim_type.

Key difference from previous prompts:
- OLD: 1 insight per field, combined into blobs
- NEW: N insights per field, each an atomic citable claim

Example for cultural_significance:
- OLD: Single insight with combined text about Buddhism, Hiroshima, TCM
- NEW: 3 separate insights, each independently sourced and scored

Field Types:
1. ATOMIC_MULTI: Generate multiple insights (cultural_significance, habitat, etc.)
2. RANKED_LIST: Generate ranked items (common_names, synonyms)
3. SINGLE_VALUE: Generate one insight (conservation_status, growth_form)
"""

from datetime import date
from typing import List, Dict

# ============================================================================
# FIELD CLASSIFICATION
# ============================================================================

ATOMIC_MULTI_FIELDS = [
    'cultural_significance',      # Per culture/tradition
    'associated_species',         # Per ecological community
    'agroforestry_use_cases',     # Per system type
    'non_timber_products',        # Per product category
    'ecological_function',        # Per ecosystem service
    'habitat',                    # Per distinct habitat type
    'native_adapted_habitats',    # Per region/biome
    'disease_pest_management',    # Per disease/pest
    'stewardship_best_practices', # Per practice category
    'tolerances',                 # Per tolerance type (drought, salt, etc.)
]

RANKED_LIST_FIELDS = [
    'popular_common_name',        # Ranked by usage frequency
    'synonyms',                   # With authority/year
    'identification_features',    # Ranked by diagnostic value
]

SINGLE_VALUE_FIELDS = [
    'conservation_status',        # IUCN status
    'growth_form',                # Primary form
    'leaf_type',                  # Primary type
    'deciduous_evergreen',        # Category
    'flower_color',               # Primary color
    'fruit_type',                 # Primary type
    'bark_characteristics',       # Description
    'maximum_height',             # Measurement
    'maximum_diameter',           # Measurement
    'lifespan',                   # Category
    'maximum_tree_age',           # Measurement
    'general_description',        # Synthesis
    'etymology',                  # Fixed meaning
    'elevation_ranges',           # Range
    'compatible_soil_types',      # Preferences
    'climate_tolerance',          # Requirements
    'planting_recipes',           # Instructions
    'pruning_maintenance',        # Guidelines
    'fire_management',            # Ecology
    'propagation_methods',        # Methods
    'timber_value',               # Properties
    'nutritional_caloric_value',  # Info
]

ALL_FIELDS = ATOMIC_MULTI_FIELDS + RANKED_LIST_FIELDS + SINGLE_VALUE_FIELDS

# ============================================================================
# ATOMIC INSIGHT PROMPT
# ============================================================================

ATOMIC_RESEARCH_PROMPT = """
================================================================================
TREEKIPEDIA ATOMIC RESEARCH - {scientific_name}
================================================================================

Family: {family}
Native to: {native_range}
Taxon ID: {taxon_id}

================================================================================
CRITICAL: ATOMIC INSIGHTS MODEL
================================================================================

Generate MULTIPLE SEPARATE insights for fields that have multiple distinct facts.

WRONG (old way - combining into one blob):
```json
{{
  "claim_type": "cultural_significance",
  "claim_value": {{"text": "Sacred in Buddhism. Also survived Hiroshima. Used in TCM."}},
  "confidence": 0.85
}}
```

CORRECT (new way - atomic insights):
```json
[
  {{
    "claim_type": "cultural_significance",
    "claim_value": {{"text": "Sacred in Buddhism - monks preserved species through temple plantings", "context": "Buddhism", "region": "East Asia"}},
    "confidence": 0.95,
    "sources": [{{"url": "...", "title": "Buddhist temple records"}}]
  }},
  {{
    "claim_type": "cultural_significance",
    "claim_value": {{"text": "Six trees survived 1945 Hiroshima atomic bomb, now symbols of peace", "context": "Japanese post-war", "region": "Japan"}},
    "confidence": 0.98,
    "sources": [{{"url": "...", "title": "Hiroshima Peace Memorial"}}]
  }},
  {{
    "claim_type": "cultural_significance",
    "claim_value": {{"text": "Traditional Chinese medicine uses leaves for memory enhancement", "context": "TCM", "region": "China"}},
    "confidence": 0.88,
    "sources": [{{"url": "...", "title": "TCM pharmacopoeia"}}]
  }}
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
{multi_insight_instructions}

**RANKED LIST FIELDS** (generate ranked items):
{ranked_list_instructions}

**SINGLE VALUE FIELDS** (generate one insight):
{single_value_instructions}

================================================================================
OUTPUT FORMAT
================================================================================

Return ONLY valid JSON:

{{
  "taxon_id": "{taxon_id}",
  "species_name": "{scientific_name}",
  "research_date": "{today}",
  "model_version": "research-agent",
  "insights": [
    // MULTI-INSIGHT EXAMPLE (cultural_significance)
    {{
      "claim_type": "cultural_significance",
      "claim_value": {{
        "text": "Specific cultural fact here",
        "context": "Buddhism|Christianity|Indigenous|etc",
        "region": "Geographic scope"
      }},
      "confidence": 0.95,
      "sources": [{{"url": "...", "title": "...", "credibility": 0.9}}]
    }},
    // More cultural_significance insights...

    // RANKED LIST EXAMPLE (popular_common_name)
    {{
      "claim_type": "popular_common_name",
      "claim_value": {{
        "name": "English Oak",
        "rank": 1,
        "languages": ["en"],
        "regions": ["UK", "Ireland"]
      }},
      "confidence": 0.95,
      "sources": [...]
    }},
    {{
      "claim_type": "popular_common_name",
      "claim_value": {{
        "name": "Pedunculate Oak",
        "rank": 2,
        "languages": ["en"],
        "regions": ["scientific"]
      }},
      "confidence": 0.85,
      "sources": [...]
    }},

    // SINGLE VALUE EXAMPLE (conservation_status)
    {{
      "claim_type": "conservation_status",
      "claim_value": {{
        "iucn_status": "LC",
        "iucn_year": 2024,
        "population_trend": "stable",
        "text": "Least Concern - widespread and abundant"
      }},
      "confidence": 0.98,
      "sources": [{{"url": "https://iucnredlist.org/...", "title": "IUCN Red List"}}]
    }}
  ]
}}

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

Research "{scientific_name}" comprehensively.
For multi-insight fields, generate SEPARATE insights for each distinct fact.
For ranked fields, include rank numbers and order by popularity/importance.
For single-value fields, provide the most authoritative answer.
"""

# ============================================================================
# FIELD-SPECIFIC INSTRUCTIONS
# ============================================================================

MULTI_INSIGHT_INSTRUCTIONS = """
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
"""

RANKED_LIST_INSTRUCTIONS = """
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
"""

SINGLE_VALUE_INSTRUCTIONS = """
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
"""

# ============================================================================
# PROMPT FORMATTING
# ============================================================================

def format_atomic_prompt(
    taxon_id: str,
    scientific_name: str,
    family: str = None,
    native_range: str = None
) -> str:
    """Format the atomic research prompt for a species."""
    return ATOMIC_RESEARCH_PROMPT.format(
        taxon_id=taxon_id,
        scientific_name=scientific_name,
        family=family or 'Unknown',
        native_range=native_range or 'Unknown',
        today=date.today().isoformat(),
        multi_insight_instructions=MULTI_INSIGHT_INSTRUCTIONS,
        ranked_list_instructions=RANKED_LIST_INSTRUCTIONS,
        single_value_instructions=SINGLE_VALUE_INSTRUCTIONS
    )


def get_field_type(claim_type: str) -> str:
    """Get the field type for a claim_type."""
    if claim_type in ATOMIC_MULTI_FIELDS:
        return 'multi'
    elif claim_type in RANKED_LIST_FIELDS:
        return 'ranked'
    else:
        return 'single'


def get_all_fields() -> List[str]:
    """Return all research fields."""
    return ALL_FIELDS


def get_fields_by_type() -> Dict[str, List[str]]:
    """Return fields organized by type."""
    return {
        'multi': ATOMIC_MULTI_FIELDS,
        'ranked': RANKED_LIST_FIELDS,
        'single': SINGLE_VALUE_FIELDS
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python atomic_research_prompts.py <taxon_id> <scientific_name> [family] [native_range]")
        print("\nOptions:")
        print("  --fields    List all fields by type")
        print("\nExample:")
        print("  python atomic_research_prompts.py 'GymGiGiGnKg50344-00' 'Ginkgo biloba' 'Ginkgoaceae' 'China'")
        sys.exit(1)

    if '--fields' in sys.argv:
        print("\nFields by type:")
        for field_type, fields in get_fields_by_type().items():
            print(f"\n{field_type.upper()} ({len(fields)} fields):")
            for f in fields:
                print(f"  - {f}")
        sys.exit(0)

    taxon_id = sys.argv[1]
    scientific_name = sys.argv[2]
    family = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else None
    native_range = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else None

    print(format_atomic_prompt(taxon_id, scientific_name, family, native_range))
