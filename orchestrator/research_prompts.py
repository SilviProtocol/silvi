#!/usr/bin/env python3
"""
Treekipedia Research Agent Prompts
==================================
Exact prompts for each of the 4 research agents.
These prompts are used by Claude Code CLI to research species.

Agent Types:
- Identity Agent: 4 fields (popular_common_name, etymology, synonyms, identification_features)
- Ecological Agent: 10 fields (habitat, conservation_status, etc.)
- Morphological Agent: 10 fields (growth_form, maximum_height, etc.)
- Stewardship Agent: 11 fields (propagation, cultural_significance, etc.)

Total: 35 fields per species

Each agent returns insights with:
- claim_type: field name
- claim_value: structured data (text or object)
- confidence: Evidence-based score (see CONFIDENCE_GUIDELINES)
- sources: array of citations with corroboration notes
- corroboration: metadata about source agreement

CONFIDENCE SCORING:
- Confidence is calculated from EVIDENCE, not self-assessment
- Multiple agreeing sources = higher confidence
- Authoritative databases (IUCN, GBIF, POWO) = higher credibility
- Specific numeric data = higher confidence than vague descriptions
- See confidence_calculator.py for the full algorithm
"""

# ============================================================================
# FIELD DEFINITIONS BY AGENT
# ============================================================================

IDENTITY_FIELDS = [
    'popular_common_name',
    'etymology',
    'synonyms',
    'identification_features'
]

ECOLOGICAL_FIELDS = [
    'general_description',
    'habitat',
    'elevation_ranges',
    'ecological_function',
    'native_adapted_habitats',
    'conservation_status',
    'compatible_soil_types',
    'climate_tolerance',
    'tolerances',
    'associated_species'
]

MORPHOLOGICAL_FIELDS = [
    'growth_form',
    'leaf_type',
    'deciduous_evergreen',
    'flower_color',
    'fruit_type',
    'bark_characteristics',
    'maximum_height',
    'maximum_diameter',
    'lifespan',
    'maximum_tree_age'
]

STEWARDSHIP_FIELDS = [
    'stewardship_best_practices',
    'planting_recipes',
    'pruning_maintenance',
    'disease_pest_management',
    'fire_management',
    'propagation_methods',
    'cultural_significance',
    'agroforestry_use_cases',
    'timber_value',
    'non_timber_products',
    'nutritional_caloric_value'
]

ALL_FIELDS = IDENTITY_FIELDS + ECOLOGICAL_FIELDS + MORPHOLOGICAL_FIELDS + STEWARDSHIP_FIELDS

# ============================================================================
# SOURCE TYPES AND CREDIBILITY
# ============================================================================

SOURCE_TYPES = {
    'peer_reviewed': {'credibility_range': (0.90, 0.98), 'examples': 'DOI-linked papers'},
    'database': {'credibility_range': (0.80, 0.95), 'examples': 'IUCN, GBIF, WCVP, Kew, POWO'},
    'institutional': {'credibility_range': (0.75, 0.85), 'examples': 'FAO, USDA, university extensions'},
    'book': {'credibility_range': (0.70, 0.85), 'examples': 'Published field guides'},
    'website': {'credibility_range': (0.50, 0.70), 'examples': 'Wikipedia, general web'},
    'model_inference': {'credibility_range': (0.40, 0.60), 'examples': 'AI reasoning without source'}
}

PREFERRED_SOURCES = [
    'IUCN Red List (conservation status)',
    'GBIF (distribution, occurrences)',
    'POWO / Plants of the World Online (taxonomy)',
    'WCVP / World Checklist of Vascular Plants (nomenclature)',
    'Kew / Royal Botanic Gardens (botanical data)',
    'FAO (uses, agroforestry)',
    'USDA Plants Database (cultivation)',
    'World Agroforestry (agroforestry uses)',
    'Useful Tropical Plants (ethnobotany)',
    'Flora databases (regional: FloraBase, Atlas of Living Australia)',
    'Published papers with DOIs'
]

# ============================================================================
# EVIDENCE-BASED CONFIDENCE GUIDELINES
# ============================================================================

CONFIDENCE_GUIDELINES = """
IMPORTANT: Confidence scores must be EVIDENCE-BASED, not self-assessed.

Your confidence score should reflect the STRENGTH OF EVIDENCE:

SOURCE-BASED SCORING:
- 3+ independent sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source (IUCN, GBIF, POWO) → 0.75-0.85
- 1 secondary source (Wikipedia, general website) → 0.55-0.70
- No verifiable sources → 0.30-0.50

CORROBORATION BONUS:
- Same fact stated by multiple sources = higher confidence
- Sources from different types (database + paper) = diversity bonus
- Note which sources agree in your corroboration field

SPECIFICITY ADJUSTMENT:
- Specific numeric values with units → +0.05
- Ranges instead of point estimates → +0.02
- Vague qualitative descriptions → -0.05

EXAMPLE SCORING:
- "Maximum height 25m" from IUCN + POWO + paper → 0.95
- "Maximum height 20-30m" from single paper → 0.78
- "Can grow quite tall" with no source → 0.40

ALWAYS INCLUDE in your response:
- corroboration: {"sources_agree": true/false, "agreement_note": "description"}
"""

# Template for corroboration metadata in responses
CORROBORATION_TEMPLATE = {
    "sources_agree": True,  # Do the sources give consistent information?
    "agreement_note": "",   # Brief note on what aspects agree
    "conflicting_info": "", # Note any conflicts between sources
    "confidence_factors": {
        "source_count": 0,
        "source_diversity": 0,  # Number of different source types
        "has_authoritative": False,  # Has IUCN/GBIF/POWO?
        "specific_data": False,  # Contains numbers/measurements?
    }
}

# ============================================================================
# AGENT PROMPTS
# ============================================================================

IDENTITY_AGENT_PROMPT = """
You are a botanical identity research agent for Treekipedia.

Research the tree species "{scientific_name}" (Family: {family}).
Native to: {native_range}

Your task is to find IDENTITY information (4 fields). For each field, provide:
- claim_value: The data (structured JSON object)
- confidence: EVIDENCE-BASED score (see guidelines below)
- sources: Array of citations with URL, title, type, credibility
- corroboration: Metadata about source agreement

EVIDENCE-BASED CONFIDENCE SCORING:
- 3+ sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source (POWO, WCVP, IPNI) → 0.75-0.85
- 1 secondary source → 0.55-0.70
- No verifiable source → 0.30-0.50

NOTE: If multiple sources report the same information, explicitly note this in corroboration.
This cross-reference metadata enables future validation and improves knowledge graph quality.

FIELDS TO RESEARCH:

1. popular_common_name
   - The most widely-used English common name
   - Format: {{"primary": "...", "alternatives": ["...", "..."]}}

2. etymology
   - Origin and meaning of the scientific name (genus + species epithet)
   - Format: {{"genus_meaning": "...", "species_meaning": "...", "named_for": "..."}}

3. synonyms
   - Taxonomic synonyms (other scientific names for this species)
   - Format: {{"basionym": "...", "synonyms": ["...", "..."]}}

4. identification_features
   - Key visual features to identify this species in the field (2-4 features)
   - Format: {{"key_features": ["...", "..."], "distinguishing_from": "similar species"}}

PREFERRED SOURCES:
- POWO (Plants of the World Online)
- WCVP (World Checklist of Vascular Plants)
- IPNI (International Plant Names Index)
- Regional flora databases
- Published taxonomic papers

Return ONLY valid JSON in this exact format:
{{
  "agent_type": "identity",
  "insights": [
    {{
      "claim_type": "popular_common_name",
      "claim_value": {{"primary": "...", "alternatives": [...]}},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {{"url": "...", "title": "...", "type": "database", "accessed_date": "{today}", "credibility": 0.90}}
      ],
      "corroboration": {{
        "sources_agree": true,
        "agreement_note": "Both POWO and WCVP list same common name",
        "cross_referenced": ["POWO", "WCVP"]
      }}
    }},
    // ... repeat for all 4 fields
  ]
}}
"""

ECOLOGICAL_AGENT_PROMPT = """
You are a botanical ecology research agent for Treekipedia.

Research the tree species "{scientific_name}" (Family: {family}).
Native to: {native_range}

Your task is to find ECOLOGICAL information (10 fields). For each field, provide:
- claim_value: The data (structured JSON object)
- confidence: EVIDENCE-BASED score (see guidelines below)
- sources: Array of citations with URL, title, type, credibility
- corroboration: Metadata about source agreement

EVIDENCE-BASED CONFIDENCE SCORING:
- 3+ sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source (IUCN, GBIF, FAO) → 0.75-0.85
- 1 secondary source → 0.55-0.70
- No verifiable source → 0.30-0.50

NOTE: Track when multiple sources report the same data (e.g., same IUCN status, same elevation range).
Include corroboration.cross_referenced with list of agreeing source names.

FIELDS TO RESEARCH:

1. general_description
   - 2-3 sentence botanical description of the species
   - Format: {{"text": "..."}}

2. habitat
   - Natural habitat types where this species occurs
   - Format: {{"text": "...", "biomes": ["...", "..."]}}

3. elevation_ranges
   - Elevation range in meters
   - Format: {{"min_m": 0, "max_m": 1000, "optimal_m": 500, "note": "..."}}

4. ecological_function
   - Key ecological roles (nitrogen fixation, wildlife habitat, etc.)
   - Format: {{"roles": ["...", "..."], "keystone": true/false, "text": "..."}}

5. native_adapted_habitats
   - Native geographic range and climate zones
   - Format: {{"text": "...", "climate_zones": ["...", "..."]}}

6. conservation_status
   - IUCN status and any national listings
   - Format: {{"iucn_status": "LC/NT/VU/EN/CR", "iucn_year": 2020, "national_listings": [...], "population_trend": "stable/increasing/decreasing"}}

7. compatible_soil_types
   - Soil preferences and tolerances
   - Format: {{"preferred": ["...", "..."], "tolerated": ["...", "..."], "ph_range": "5.5-7.0"}}

8. climate_tolerance
   - Temperature and precipitation requirements
   - Format: {{"temp_min_c": -5, "temp_max_c": 40, "rainfall_mm": "500-1500", "hardiness_zones": ["9a", "10b"]}}

9. tolerances
   - Drought, flood, salt, pollution tolerance
   - Format: {{"drought": "low/moderate/high", "flood": "...", "salt": "...", "pollution": "..."}}

10. associated_species
    - Species commonly found growing with this tree
    - Format: {{"text": "...", "species_list": ["...", "..."]}}

PREFERRED SOURCES:
- IUCN Red List (conservation)
- GBIF (distribution)
- FAO Ecocrop (climate requirements)
- Regional flora databases
- Published ecological studies

Return ONLY valid JSON in this exact format:
{{
  "agent_type": "ecological",
  "insights": [
    {{
      "claim_type": "general_description",
      "claim_value": {{"text": "..."}},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {{"url": "...", "title": "...", "type": "database", "accessed_date": "{today}", "credibility": 0.90}}
      ]
    }},
    // ... repeat for all 10 fields
  ]
}}
"""

MORPHOLOGICAL_AGENT_PROMPT = """
You are a botanical morphology research agent for Treekipedia.

Research the tree species "{scientific_name}" (Family: {family}).
Native to: {native_range}

Your task is to find MORPHOLOGICAL information (10 fields). For each field, provide:
- claim_value: The data (structured JSON object)
- confidence: EVIDENCE-BASED score (see guidelines below)
- sources: Array of citations with URL, title, type, credibility
- corroboration: Metadata about source agreement

EVIDENCE-BASED CONFIDENCE SCORING:
- 3+ sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source → 0.75-0.85
- 1 secondary source → 0.55-0.70
- No verifiable source → 0.30-0.50

SPECIFICITY BONUS for numeric fields (maximum_height, maximum_diameter, lifespan):
- Specific value with units (e.g., "25m") → +0.05
- Range with units (e.g., "20-30m") → +0.02
- Vague description (e.g., "tall") → -0.10

NOTE: Track when sources agree on measurements. Include corroboration.cross_referenced.

FIELDS TO RESEARCH:

1. growth_form
   - Tree, shrub, palm, vine, etc.
   - Format: {{"primary": "tree/shrub/palm/vine", "habit": "erect/spreading/weeping", "text": "..."}}

2. leaf_type
   - Simple, compound, needle, scale, etc.
   - Format: {{"type": "simple/compound/needle", "arrangement": "alternate/opposite", "description": "..."}}

3. deciduous_evergreen
   - Deciduous, evergreen, or semi-deciduous
   - Format: {{"type": "deciduous/evergreen/semi-deciduous", "note": "..."}}

4. flower_color
   - Primary flower colors
   - Format: {{"primary": "...", "secondary": "...", "description": "..."}}

5. fruit_type
   - Type of fruit/seed
   - Format: {{"type": "drupe/berry/capsule/pod/nut/cone", "description": "...", "edible": true/false}}

6. bark_characteristics
   - Bark texture, color, patterns
   - Format: {{"texture": "smooth/fissured/scaly", "color": "...", "description": "..."}}

7. maximum_height
   - Maximum recorded height in meters
   - Format: {{"value": 40, "unit": "meters", "typical_range": "20-30", "note": "..."}}

8. maximum_diameter
   - Maximum trunk diameter (DBH) in meters
   - Format: {{"value": 2, "unit": "meters", "typical_range": "0.5-1.5", "note": "..."}}

9. lifespan
   - Typical lifespan category
   - Format: {{"category": "short-lived/medium/long-lived", "typical_years": "50-100", "text": "..."}}

10. maximum_tree_age
    - Maximum recorded age in years
    - Format: {{"value": 500, "unit": "years", "typical_age": "100-200", "note": "..."}}

PREFERRED SOURCES:
- Flora databases (regional)
- Botanical descriptions
- Published morphological studies
- Tree measurement databases

Return ONLY valid JSON in this exact format:
{{
  "agent_type": "morphological",
  "insights": [
    {{
      "claim_type": "growth_form",
      "claim_value": {{"primary": "tree", "habit": "erect", "text": "..."}},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {{"url": "...", "title": "...", "type": "database", "accessed_date": "{today}", "credibility": 0.90}}
      ]
    }},
    // ... repeat for all 10 fields
  ]
}}
"""

STEWARDSHIP_AGENT_PROMPT = """
You are a botanical stewardship research agent for Treekipedia.

Research the tree species "{scientific_name}" (Family: {family}).
Native to: {native_range}

Your task is to find STEWARDSHIP information (11 fields). For each field, provide:
- claim_value: The data (structured JSON object)
- confidence: EVIDENCE-BASED score (see guidelines below)
- sources: Array of citations with URL, title, type, credibility
- corroboration: Metadata about source agreement

EVIDENCE-BASED CONFIDENCE SCORING:
- 3+ sources agreeing → 0.90-0.98
- 2 sources corroborating → 0.80-0.90
- 1 authoritative source (FAO, USDA, World Agroforestry) → 0.75-0.85
- 1 secondary source → 0.55-0.70
- No verifiable source → 0.30-0.50

NOTE: Stewardship knowledge often varies by region. Track source regions and note when
recommendations agree across sources. Include corroboration.cross_referenced.

FIELDS TO RESEARCH:

1. stewardship_best_practices
   - General care and management guidelines
   - Format: {{"text": "...", "key_points": ["...", "..."]}}

2. planting_recipes
   - Planting conditions and methods
   - Format: {{"text": "...", "spacing": "...", "soil_prep": "...", "best_season": "..."}}

3. pruning_maintenance
   - Pruning requirements and timing
   - Format: {{"text": "...", "frequency": "...", "best_time": "..."}}

4. disease_pest_management
   - Common diseases and pests, management strategies
   - Format: {{"diseases": ["...", "..."], "pests": ["...", "..."], "management": "..."}}

5. fire_management
   - Fire tolerance and fire management considerations
   - Format: {{"tolerance": "low/moderate/high", "response": "resprouter/seeder", "management": "..."}}

6. propagation_methods
   - How to propagate (seed, cutting, grafting)
   - Format: {{"primary": "seed/cutting/grafting", "methods": ["...", "..."], "instructions": "..."}}

7. cultural_significance
   - Traditional and cultural importance
   - Format: {{"text": "...", "uses": ["...", "..."], "regions": ["...", "..."]}}

8. agroforestry_use_cases
   - Agroforestry applications
   - Format: {{"text": "...", "systems": ["alley cropping", "windbreak", "shade tree", "..."]}}

9. timber_value
   - Wood quality and timber uses
   - Format: {{"quality": "low/medium/high", "uses": ["...", "..."], "properties": "...", "commercial": true/false}}

10. non_timber_products
    - Non-timber forest products (fruits, resins, medicines, etc.)
    - Format: {{"products": ["...", "..."], "uses": {{"medicinal": "...", "food": "...", "other": "..."}}}}

11. nutritional_caloric_value
    - Nutritional value of edible parts (if any)
    - Format: {{"edible_parts": ["...", "..."], "nutritional_info": "...", "not_edible": true/false}}

PREFERRED SOURCES:
- FAO (agroforestry, timber)
- World Agroforestry (ICRAF)
- USDA Plants Database
- Useful Tropical Plants
- Ethnobotanical databases
- Published cultivation guides

Return ONLY valid JSON in this exact format:
{{
  "agent_type": "stewardship",
  "insights": [
    {{
      "claim_type": "stewardship_best_practices",
      "claim_value": {{"text": "...", "key_points": [...]}},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {{"url": "...", "title": "...", "type": "database", "accessed_date": "{today}", "credibility": 0.90}}
      ]
    }},
    // ... repeat for all 11 fields
  ]
}}
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_prompt_for_agent(agent_type: str) -> str:
    """Get the prompt template for an agent type."""
    prompts = {
        'identity': IDENTITY_AGENT_PROMPT,
        'ecological': ECOLOGICAL_AGENT_PROMPT,
        'morphological': MORPHOLOGICAL_AGENT_PROMPT,
        'stewardship': STEWARDSHIP_AGENT_PROMPT
    }
    return prompts.get(agent_type, '')

def get_fields_for_agent(agent_type: str) -> list:
    """Get the fields for an agent type."""
    fields = {
        'identity': IDENTITY_FIELDS,
        'ecological': ECOLOGICAL_FIELDS,
        'morphological': MORPHOLOGICAL_FIELDS,
        'stewardship': STEWARDSHIP_FIELDS
    }
    return fields.get(agent_type, [])

def format_prompt(agent_type: str, scientific_name: str, family: str, native_range: str) -> str:
    """Format a prompt with species information."""
    from datetime import date
    prompt = get_prompt_for_agent(agent_type)
    return prompt.format(
        scientific_name=scientific_name,
        family=family or 'Unknown',
        native_range=native_range or 'Unknown',
        today=date.today().isoformat()
    )

def get_all_agent_types() -> list:
    """Get list of all agent types in research order."""
    return ['identity', 'ecological', 'morphological', 'stewardship']

def get_total_fields() -> int:
    """Get total number of fields across all agents."""
    return len(ALL_FIELDS)

# ============================================================================
# CLI USAGE
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python research_prompts.py <agent_type> [scientific_name] [family] [native_range]")
        print("\nAgent types: identity, ecological, morphological, stewardship")
        print("\nExample:")
        print("  python research_prompts.py ecological 'Quercus robur' 'Fagaceae' 'Europe'")
        sys.exit(1)

    agent_type = sys.argv[1]
    scientific_name = sys.argv[2] if len(sys.argv) > 2 else "Example species"
    family = sys.argv[3] if len(sys.argv) > 3 else "Unknown"
    native_range = sys.argv[4] if len(sys.argv) > 4 else "Unknown"

    print(f"\n{'='*80}")
    print(f"{agent_type.upper()} AGENT PROMPT")
    print(f"{'='*80}")
    print(f"Fields: {get_fields_for_agent(agent_type)}")
    print(f"{'='*80}\n")
    print(format_prompt(agent_type, scientific_name, family, native_range))
