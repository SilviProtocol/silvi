#!/usr/bin/env python3
"""
Treekipedia Unified Deep Research Prompt
========================================
Comprehensive research prompt for all 35 fields per species.

PHILOSOPHY:
- Cast a WIDE net - don't confine searches to obvious sources
- Look for nuance, edge cases, contradictions
- Prioritize less-documented species with more thorough research
- Search BEYOND English - translate if necessary
- Find grey literature, dissertations, technical reports
- Respect and integrate Traditional Ecological Knowledge (TEK)
- Prioritize biodiversity darkspot regions

Total: 35 fields per species, researched in a single comprehensive session.
"""

from datetime import date

# ============================================================================
# ALL 35 RESEARCH FIELDS
# ============================================================================

ALL_FIELDS = [
    # Identity (4 fields)
    'popular_common_name',
    'etymology',
    'synonyms',
    'identification_features',
    # Ecological (10 fields)
    'general_description',
    'habitat',
    'elevation_ranges',
    'ecological_function',
    'native_adapted_habitats',
    'conservation_status',
    'compatible_soil_types',
    'climate_tolerance',
    'tolerances',
    'associated_species',
    # Morphological (10 fields)
    'growth_form',
    'leaf_type',
    'deciduous_evergreen',
    'flower_color',
    'fruit_type',
    'bark_characteristics',
    'maximum_height',
    'maximum_diameter',
    'lifespan',
    'maximum_tree_age',
    # Stewardship (11 fields)
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

# ============================================================================
# SOURCE HIERARCHY - Expanded for Deep Research
# ============================================================================

PREFERRED_SOURCES = """
TIER 1 - Global Authoritative Databases (0.90-0.98 credibility):
- IUCN Red List (iucnredlist.org) - conservation status, population trends
- POWO / Plants of the World Online (powo.science.kew.org) - taxonomy, distribution, descriptions
- WCVP / World Checklist of Vascular Plants - nomenclature, synonymy
- GBIF (gbif.org) - occurrence records, distribution data
- World Flora Online (worldfloraonline.org) - taxonomic backbone

TIER 2 - Institutional & Government (0.80-0.90):
- FAO (fao.org) - agroforestry, economic uses, cultivation
- USDA Plants Database (plants.usda.gov) - North American species
- World Agroforestry / ICRAF (worldagroforestry.org) - agroforestry systems
- Kew Science / Royal Botanic Gardens - botanical monographs
- BGCI PlantSearch (plantsearch.bgci.org) - living collections, ex situ conservation

TIER 3 - Regional Flora Databases (0.75-0.85):
- Flora of China (efloras.org) - 31,000 species, Chinese flora
- TROPICOS (tropicos.org) - Neotropical flora, Missouri Botanical Garden
- African Plants Database - 202,559+ names from tropical/southern Africa
- Euro+Med PlantBase (europlusmed.org) - European and Mediterranean flora
- FloraBase (Western Australia), Atlas of Living Australia
- Flora Malesiana, Flora of Thailand, Flora of Vietnam

TIER 4 - Grey Literature & Specialized Sources (0.70-0.85):
- ProQuest Dissertations & Theses - PhD/MSc research (often 12-18 months ahead of journals)
- Google Scholar - academic papers, citations, preprints
- Biodiversity Heritage Library (biodiversitylibrary.org) - historical botanical literature
- JSTOR Global Plants - type specimens, botanical illustrations
- Useful Tropical Plants (tropical.theferns.info) - ethnobotany, traditional uses
- Fire Effects Information System (FEIS) - fire ecology data
- OpenGrey (opengrey.eu) - European technical reports

TIER 5 - Ethnobotanical & Traditional Knowledge (0.70-0.85):
- Chinese Useful Plant Database - 51,949 records, 10,808 species
- Native American Ethnobotany Database (naeb.brit.org)
- Published ethnobotanical surveys and field studies
- Regional language sources (Spanish, Portuguese, French, German, Chinese, etc.)
- Traditional Ecological Knowledge literature (with ethical considerations)

TIER 6 - Community & Citizen Science (0.50-0.70):
- iNaturalist - observations with photos, community IDs
- Wikipedia (cross-reference with authoritative sources)
- Regional naturalist forums and field guides
"""

# ============================================================================
# DEEP RESEARCH STRATEGIES
# ============================================================================

RESEARCH_STRATEGIES = """
SEARCH STRATEGY - Cast a WIDE Net:

1. SCIENTIFIC NAMES ARE UNIVERSAL
   - Latin binomial nomenclature is THE universal language of botany
   - ALL countries/languages use scientific names in scientific literature
   - Chinese papers cite "Quercus robur", Japanese papers cite "Quercus robur"
   - ALWAYS search by scientific name first - this is language-agnostic
   - Results will come from databases worldwide regardless of interface language

2. BE LANGUAGE-AGNOSTIC
   - Don't restrict searches to English-only results
   - If you find a relevant source in Spanish, Portuguese, French, German,
     Chinese, Japanese, etc. - USE IT and translate the findings
   - Many regional databases have valuable data not in English sources
   - The scientific name "{species}" will find results in ANY language

3. START BROAD, GO DEEP
   - Don't stop at the first result - look for nuance, contradictions, edge cases
   - Check MULTIPLE sources for the same data point
   - If sources disagree, note the range and explain why

4. PRIORITIZE LESS-DOCUMENTED SPECIES
   - Species with few results need MORE thorough searching, not less
   - Try synonyms (check POWO/WCVP for all accepted synonyms)
   - Check regional databases that might have local data
   - Search grey literature (dissertations, technical reports)

5. GREY LITERATURE MINING
   - Search: "{species}" filetype:pdf site:.edu OR site:.gov
   - Search: "{species}" dissertation OR thesis
   - Check FAO, CIFOR, ICRAF technical reports
   - Look for Environmental Impact Assessments mentioning the species
   - Find government forestry/agriculture reports

6. ETHNOBOTANICAL & TRADITIONAL KNOWLEDGE
   - Search: "{species}" traditional use OR indigenous OR ethnobotany
   - Document cultural significance and traditional names
   - Note regional variations in use and significance
   - Respect TEK - it's valid scientific data

7. BIODIVERSITY DARKSPOT PRIORITY
   If species is from these regions, search extra thoroughly:
   - Tropical Asia: Myanmar, Philippines, Vietnam, Indonesia, Papua New Guinea
   - South America: Colombia, Peru, Ecuador
   - Africa: Madagascar, West Africa, East African highlands
   - These regions have the most undocumented species diversity

8. LOOK FOR CONTRADICTIONS & NUANCE
   - Maximum height varies by habitat - note the range
   - Conservation status may differ between countries
   - Traditional uses vary by culture - document regional differences
   - Don't oversimplify complex ecological relationships

9. SUBSPECIES & VARIETIES
   - If researching a subspecies, check if data exists at species level
   - Note when data applies to species broadly vs. this specific taxon
   - Search for the subspecies epithet separately
"""

# ============================================================================
# UNIFIED DEEP RESEARCH PROMPT
# ============================================================================

UNIFIED_RESEARCH_PROMPT = """
================================================================================
TREEKIPEDIA DEEP RESEARCH - {scientific_name}
================================================================================

Family: {family}
Native to: {native_range}
Taxon ID: {taxon_id}

================================================================================
RESEARCH PHILOSOPHY
================================================================================

1. CAST A WIDE NET - Don't confine yourself to obvious sources
2. LOOK FOR NUANCE - Edge cases, contradictions, regional variations
3. PRIORITIZE DEPTH - Less-documented species need MORE research, not less
4. SEARCH BEYOND ENGLISH - Translate findings from Spanish, Portuguese, French, German, Chinese
5. FIND GREY LITERATURE - Dissertations, technical reports, government documents
6. RESPECT TEK - Traditional Ecological Knowledge is valid scientific data
7. NOTE CONTRADICTIONS - When sources disagree, document the range

================================================================================
SEARCH STRATEGY
================================================================================

{research_strategies}

================================================================================
SOURCE PRIORITY
================================================================================

{preferred_sources}

================================================================================
FIELDS TO RESEARCH (35 total)
================================================================================

For EACH field, search thoroughly and provide:
- claim_value: Structured data (see format below)
- confidence: 0.0-1.0 based on source quality and agreement
- sources: ALL sources consulted (even if they didn't have data)
- methodology: "extraction" (from source) or "inference" (reasoned from related data)
- notes: Any nuance, contradictions, or regional variations

IDENTITY (4 fields):
1. popular_common_name
   - Search in MULTIPLE languages for the most widely-used name
   - Include regional names: "Known as X in Brazil, Y in Spanish-speaking countries"
   - Format: {{"primary": "...", "alternatives": ["...", "..."], "regional_names": {{"es": "...", "pt": "...", "fr": "..."}}}}

2. etymology
   - Meaning of genus + species epithet
   - Who named it and when (if notable)
   - Format: {{"genus_meaning": "...", "species_meaning": "...", "named_for": "...", "author": "..."}}

3. synonyms
   - Check POWO, WCVP, TROPICOS for all synonyms
   - Include basionym and homotypic/heterotypic synonyms
   - Format: {{"basionym": "...", "synonyms": ["...", "..."], "misapplied_names": ["..."]}}

4. identification_features
   - Key features to distinguish from similar species
   - Note what it's commonly confused with
   - Format: {{"key_features": ["...", "..."], "distinguishing_from": "...", "common_confusion": "..."}}

ECOLOGICAL (10 fields):
5. general_description
   - 2-4 sentence botanical description
   - Include notable characteristics
   - Format: {{"text": "..."}}

6. habitat
   - Natural habitat types - be specific
   - Note variation across range if applicable
   - Format: {{"text": "...", "biomes": ["...", "..."], "vegetation_types": ["..."], "microhabitats": "..."}}

7. elevation_ranges
   - Search for actual recorded elevations, not just ranges
   - Note if varies by region
   - Format: {{"min_m": 0, "max_m": 1000, "optimal_m": 500, "regional_variation": "...", "note": "..."}}

8. ecological_function
   - ALL ecological roles - nitrogen fixation, wildlife habitat, soil stabilization, etc.
   - Keystone species status if applicable
   - Format: {{"roles": ["...", "..."], "keystone": true/false, "associated_fauna": ["..."], "ecosystem_services": ["..."], "text": "..."}}

9. native_adapted_habitats
   - Native geographic range with climate zones
   - Note if naturalized elsewhere
   - Format: {{"text": "...", "climate_zones": ["...", "..."], "koppen_climate": ["..."], "naturalized_regions": ["..."]}}

10. conservation_status
    - IUCN global status + national/regional listings
    - Population trends and threats
    - Format: {{"iucn_status": "LC/NT/VU/EN/CR/DD", "iucn_year": 2024, "iucn_criteria": "...", "population_trend": "...", "threats": ["..."], "national_listings": [{{"country": "...", "status": "..."}}]}}

11. compatible_soil_types
    - Be specific: clay, loam, sand, etc.
    - pH preferences and tolerances
    - Format: {{"preferred": ["...", "..."], "tolerated": ["...", "..."], "ph_range": "5.5-7.0", "drainage": "...", "soil_notes": "..."}}

12. climate_tolerance
    - Temperature extremes (not just averages)
    - Precipitation requirements
    - Frost tolerance, heat tolerance
    - Format: {{"temp_min_c": -5, "temp_max_c": 40, "frost_tolerance": "...", "rainfall_mm": "500-1500", "rainfall_seasonality": "...", "hardiness_zones": ["9a", "10b"]}}

13. tolerances
    - Drought, flood, salt, pollution, shade, wind
    - Be specific about degree (low/moderate/high)
    - Format: {{"drought": "low/moderate/high", "flood": "...", "salt_spray": "...", "soil_salt": "...", "pollution": "...", "shade": "...", "wind": "..."}}

14. associated_species
    - Species commonly found growing together
    - Ecological community context
    - Format: {{"text": "...", "species_list": ["...", "..."], "community_type": "...", "succession_stage": "..."}}

MORPHOLOGICAL (10 fields):
15. growth_form
    - Primary form + variations
    - Format: {{"primary": "tree/shrub/palm/vine", "habit": "erect/spreading/weeping/multi-stemmed", "crown_shape": "...", "text": "..."}}

16. leaf_type
    - Complete leaf description
    - Format: {{"type": "simple/compound/bipinnate/needle/scale", "arrangement": "alternate/opposite/whorled", "shape": "...", "margin": "...", "size_cm": "...", "description": "..."}}

17. deciduous_evergreen
    - Note if varies by climate
    - Format: {{"type": "deciduous/evergreen/semi-deciduous", "leaf_drop_trigger": "...", "note": "..."}}

18. flower_color
    - Include flowering season and pollination
    - Format: {{"primary": "...", "secondary": "...", "flowering_season": "...", "flower_type": "...", "pollination": "...", "fragrance": "...", "description": "..."}}

19. fruit_type
    - Complete fruit/seed description
    - Format: {{"type": "drupe/berry/capsule/pod/nut/samara/cone", "size_cm": "...", "color": "...", "edible": true/false, "dispersal": "...", "fruiting_season": "...", "description": "..."}}

20. bark_characteristics
    - How bark changes with age
    - Format: {{"texture": "smooth/fissured/scaly/papery/flaky", "color": "...", "young_bark": "...", "mature_bark": "...", "exudate": "...", "description": "..."}}

21. maximum_height
    - Record maximum + typical range
    - Note exceptional specimens if known
    - Format: {{"value": 40, "unit": "meters", "typical_range": "20-30", "exceptional": "...", "growth_rate": "...", "note": "..."}}

22. maximum_diameter
    - DBH (diameter at breast height)
    - Format: {{"value": 2, "unit": "meters", "typical_range": "0.5-1.5", "note": "..."}}

23. lifespan
    - Typical vs maximum
    - Format: {{"category": "short-lived/medium/long-lived/very-long-lived", "typical_years": "50-100", "note": "..."}}

24. maximum_tree_age
    - Maximum recorded age with source if possible
    - Format: {{"value": 500, "unit": "years", "typical_age": "100-200", "oldest_known": "...", "note": "..."}}

STEWARDSHIP (11 fields):
25. stewardship_best_practices
    - Comprehensive care guidelines
    - Format: {{"text": "...", "key_points": ["...", "..."], "common_mistakes": ["..."]}}

26. planting_recipes
    - Detailed planting instructions
    - Format: {{"text": "...", "spacing": "...", "soil_prep": "...", "best_season": "...", "companion_plants": ["..."], "site_selection": "..."}}

27. pruning_maintenance
    - When and how to prune
    - Format: {{"text": "...", "frequency": "...", "best_time": "...", "pruning_tolerance": "...", "formative_pruning": "..."}}

28. disease_pest_management
    - Common problems and solutions
    - Format: {{"diseases": ["...", "..."], "pests": ["...", "..."], "management": "...", "resistant_to": ["..."], "susceptible_to": ["..."]}}

29. fire_management
    - Fire ecology - tolerance, response, management
    - Format: {{"tolerance": "low/moderate/high", "response": "resprouter/seeder/killed", "bark_thickness": "...", "management": "...", "fire_regime_adapted": "..."}}

30. propagation_methods
    - All viable methods with success rates
    - Format: {{"primary": "seed/cutting/grafting/layering", "methods": ["...", "..."], "seed_treatment": "...", "germination_rate": "...", "cutting_success": "...", "instructions": "..."}}

31. cultural_significance
    - Traditional and modern cultural importance
    - Search in NATIVE LANGUAGE sources
    - Format: {{"text": "...", "uses": ["...", "..."], "regions": ["...", "..."], "ceremonies": "...", "mythology": "...", "historical": "..."}}

32. agroforestry_use_cases
    - Specific agroforestry applications
    - Format: {{"text": "...", "systems": ["alley cropping", "windbreak", "shade tree", "silvopasture", "living fence"], "compatible_crops": ["..."], "benefits": ["..."]}}

33. timber_value
    - Wood properties and commercial value
    - Format: {{"quality": "low/medium/high", "uses": ["...", "..."], "properties": {{"hardness": "...", "density": "...", "durability": "..."}}, "commercial": true/false, "trade_name": "..."}}

34. non_timber_products
    - All non-timber products and uses
    - Format: {{"products": ["...", "..."], "uses": {{"medicinal": "...", "food": "...", "fiber": "...", "dye": "...", "resin": "...", "other": "..."}}, "commercial_value": "..."}}

35. nutritional_caloric_value
    - Edible parts and nutritional info
    - Format: {{"edible_parts": ["...", "..."], "nutritional_info": "...", "preparation": "...", "toxicity_notes": "...", "not_edible": true/false}}

================================================================================
OUTPUT FORMAT
================================================================================

Return ONLY valid JSON:

{{
  "taxon_id": "{taxon_id}",
  "species_name": "{scientific_name}",
  "research_date": "{today}",
  "model_version": "claude-opus-4-5-20251101",
  "languages_searched": ["en", "es", "pt", ...],
  "sources_consulted": ["POWO", "IUCN", "GBIF", ...],
  "research_depth": "standard/deep/comprehensive",
  "insights": [
    {{
      "claim_type": "field_name",
      "claim_value": {{...structured data...}},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {{
          "url": "https://...",
          "title": "...",
          "type": "database/peer_reviewed/grey_literature/ethnobotanical/institutional/website",
          "language": "en",
          "accessed_date": "{today}",
          "credibility": 0.90
        }}
      ],
      "notes": "Any nuance, contradictions, or regional variations"
    }},
    // ... repeat for all 35 fields
  ],
  "research_notes": "Overall observations, data gaps, contradictions found"
}}

================================================================================
CONFIDENCE SCORING
================================================================================

0.95-1.00: Multiple authoritative sources agree, peer-reviewed data
0.85-0.94: Single authoritative source (IUCN, POWO) or multiple institutional sources
0.75-0.84: Grey literature, regional databases, translated sources
0.65-0.74: Single non-authoritative source, ethnobotanical (documented)
0.50-0.64: Inference from related species, limited sources
0.40-0.49: Model inference, extrapolation, speculation (must note)
<0.40: Do not include - insufficient evidence

================================================================================
BEGIN DEEP RESEARCH
================================================================================

Research "{scientific_name}" comprehensively. Start with authoritative databases,
then expand to regional sources, grey literature, and non-English sources.
Document everything - even sources that had no data.

If this species is poorly documented, search HARDER, not less.
The goal is to find what others have missed.
"""


def format_unified_prompt(
    taxon_id: str,
    scientific_name: str,
    family: str = None,
    native_range: str = None
) -> str:
    """Format the unified prompt with species information."""
    return UNIFIED_RESEARCH_PROMPT.format(
        taxon_id=taxon_id,
        scientific_name=scientific_name,
        family=family or 'Unknown',
        native_range=native_range or 'Unknown',
        today=date.today().isoformat(),
        research_strategies=RESEARCH_STRATEGIES.format(species=scientific_name),
        preferred_sources=PREFERRED_SOURCES
    )


def get_all_fields() -> list:
    """Return all 35 research fields."""
    return ALL_FIELDS


def get_preferred_sources() -> str:
    """Return preferred sources documentation."""
    return PREFERRED_SOURCES


def get_research_strategies() -> str:
    """Return research strategy documentation."""
    return RESEARCH_STRATEGIES


# ============================================================================
# SEARCH QUERY TEMPLATES
# ============================================================================

def get_search_queries(scientific_name: str) -> dict:
    """
    Generate search queries for a species.

    Scientific names are UNIVERSAL - they work in ALL languages.
    Chinese, Japanese, Spanish, French databases all index by Latin binomials.

    Returns dict of search categories to queries.
    """
    return {
        'taxonomy': f'"{scientific_name}" POWO OR WCVP OR IPNI taxonomy',
        'conservation': f'"{scientific_name}" IUCN conservation status',
        'distribution': f'"{scientific_name}" GBIF distribution native range',
        'ecology': f'"{scientific_name}" ecology habitat ecosystem',
        'morphology': f'"{scientific_name}" morphology height bark leaf flower',
        'uses': f'"{scientific_name}" traditional use ethnobotany medicinal timber',
        'cultivation': f'"{scientific_name}" cultivation propagation planting agroforestry',
        'grey_literature': f'"{scientific_name}" filetype:pdf site:.edu OR site:.gov',
        'dissertations': f'"{scientific_name}" dissertation OR thesis',
    }


# ============================================================================
# CLI USAGE
# ============================================================================

if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python unified_research_prompt.py <taxon_id> <scientific_name> [family] [native_range]")
        print("\nOptions:")
        print("  --prompt       Show the full research prompt")
        print("  --languages    Show language-specific search queries")
        print("  --fields       List all 35 research fields")
        print("\nExample:")
        print("  python unified_research_prompt.py 'AngMaFaAcAc08801-00' 'Acacia acuminata' 'Fabaceae' 'Australia'")
        print("  python unified_research_prompt.py 'X' 'Quercus robur' --languages")
        sys.exit(1)

    taxon_id = sys.argv[1]
    scientific_name = sys.argv[2]
    family = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else None
    native_range = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else None

    # Check for options
    if '--languages' in sys.argv:
        searches = get_language_searches(scientific_name, native_range)
        print(f"\nLanguage-specific searches for {scientific_name}:")
        print(json.dumps(searches, indent=2, ensure_ascii=False))
    elif '--fields' in sys.argv:
        print(f"\nAll 35 research fields:")
        for i, field in enumerate(ALL_FIELDS, 1):
            print(f"  {i:2}. {field}")
    else:
        print(format_unified_prompt(taxon_id, scientific_name, family, native_range))
