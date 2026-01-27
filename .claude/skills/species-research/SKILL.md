---
name: species-research
description: Process tree species research queue, run autonomous species research, conduct deep botanical research. Use when user says "process the queue", "research species", "run species research", "research trees", or mentions the research queue. Generates ATOMIC insights (50-80+ per species) across 35 fields.
allowed-tools: WebSearch, WebFetch, Read, Grep, Glob, Bash
---

# Treekipedia Species Research Skill

## ⚠️ CRITICAL: ATOMIC INSIGHT MODEL ⚠️

**READ THIS FIRST. DO NOT SKIP.**

You MUST generate **MULTIPLE SEPARATE insights** for fields that contain multiple distinct facts. This is the #1 requirement.

### The Rule

For **MULTI-INSIGHT FIELDS**, create ONE insight per distinct fact:

| Field | Split By | Example for Ginkgo biloba |
|-------|----------|---------------------------|
| `cultural_significance` | Each culture/tradition | Buddhism (1), Shinto (1), TCM (1), Hiroshima (1) = 4 insights |
| `tolerances` | Each tolerance type | drought (1), pollution (1), salt (1), cold (1) = 4 insights |
| `habitat` | Each habitat type | montane forest (1), riparian (1), temple grounds (1) = 3 insights |
| `ecological_function` | Each ecosystem service | wildlife food (1), shade (1), pollinator support (1) = 3 insights |
| `non_timber_products` | Each product category | medicine (1), food (1), dye (1) = 3 insights |
| `agroforestry_use_cases` | Each use case | alley cropping (1), windbreak (1), urban forestry (1) = 3 insights |
| `disease_pest_management` | Each disease/pest | leaf spot (1), aphids (1), root rot (1) = 3 insights |
| `stewardship_best_practices` | Each practice | watering (1), mulching (1), pruning (1) = 3 insights |
| `associated_species` | Each community type | temperate forest (1), urban (1) = 2 insights |
| `native_adapted_habitats` | Each region | SE China (1), Japan (1), Korea (1) = 3 insights |

### WRONG vs CORRECT

**❌ WRONG (combining everything into one blob):**
```json
{
  "claim_type": "cultural_significance",
  "claim_value": "Sacred in Buddhism, Confucianism, Taoism, and Shintoism. Buddhist monks preserved it. Hiroshima survivor trees are symbols of peace. Used in TCM for 5000 years.",
  "confidence": 0.85
}
```
This is ONE insight containing 5+ facts = **WRONG**

**✅ CORRECT (atomic - one fact per insight):**
```json
[
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Sacred in Buddhism - monks preserved species through temple plantings for over 1000 years", "context": "Buddhism", "region": "East Asia"},
    "confidence": 0.95,
    "sources": [{"url": "https://...", "title": "Buddhist temple records", "type": "historical", "credibility": 0.88}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Six trees survived 1945 Hiroshima atomic bomb within 2km of blast center, now symbols of peace", "context": "Hiroshima hibaku jumoku", "region": "Japan"},
    "confidence": 0.98,
    "sources": [{"url": "https://...", "title": "Hiroshima Peace Memorial", "type": "database", "credibility": 0.95}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Leaves used in Traditional Chinese Medicine for memory and circulation for 2000+ years", "context": "TCM", "region": "China"},
    "confidence": 0.88,
    "sources": [{"url": "https://...", "title": "TCM pharmacopoeia", "type": "database", "credibility": 0.85}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Sacred tree in Shintoism, planted at temples throughout Japan", "context": "Shintoism", "region": "Japan"},
    "confidence": 0.85,
    "sources": [{"url": "https://...", "title": "Japanese temple guide", "type": "cultural", "credibility": 0.82}]
  }
]
```
This is 4 insights for 4 distinct cultural facts = **CORRECT**

### Expected Output

A well-researched species should have **50-80+ total insights** across 35 fields:
- Single-value fields: ~20 insights (1 each)
- Multi-insight fields: ~30-60 insights (2-6 each)

If you only have ~35 insights (one per field), **you are doing it wrong**.

---

## Adaptive Research Workflow

The orchestrator provides **context-aware research**. Before researching, check if existing insights exist.

### STEP 1: Get Next Species from Queue
```bash
curl -s http://localhost:5003/queue/next
```
Response: `{"queue_id": 123, "taxon_id": "GymGiGiGnKg50344-00", "species_name": "Ginkgo biloba", ...}`

### STEP 2: Mark as Processing
```bash
curl -s -X POST http://localhost:5003/queue/{queue_id}/start
```

### STEP 3: Get Research Context (IMPORTANT!)
```bash
curl -s http://localhost:5003/research/{taxon_id}/context
```

Response tells you HOW to research:
```json
{
  "taxon_id": "GymGiGiGnKg50344-00",
  "species_name": "Ginkgo biloba",
  "is_first_research": true,
  "existing_version": 0,
  "existing_insight_count": 0,
  "recommended_focus": "full",
  "priority_fields": ["all 35 fields"],
  "skip_fields": []
}
```

OR for re-research:
```json
{
  "is_first_research": false,
  "existing_version": 1,
  "existing_insight_count": 65,
  "recommended_focus": "gaps",
  "high_confidence_fields": ["conservation_status", "maximum_height", ...],
  "low_confidence_fields": ["cultural_significance", "tolerances"],
  "missing_fields": ["fire_management", "propagation_methods"],
  "controversial_fields": [],
  "priority_fields": ["cultural_significance", "tolerances", "fire_management"],
  "skip_fields": ["conservation_status", "maximum_height"]
}
```

### Research Modes

| Mode | When | What to Do |
|------|------|------------|
| `full` | First research | Research ALL 35 fields, generate 50-80+ insights |
| `gaps` | Re-research | Focus on `priority_fields`, skip `skip_fields` |
| `deep_dive` | Controversies | Deep research on `controversial_fields` with multiple sources |
| `refresh` | Old data | Light refresh of time-sensitive fields (conservation_status) |

### STEP 4: Conduct Research

Based on `recommended_focus`:

**For "full" mode**: Research all 35 fields comprehensively.

**For "gaps" mode**:
- SKIP fields in `skip_fields` (already high confidence)
- PRIORITIZE fields in `priority_fields` (low confidence or missing)
- Generate new insights that will SUPERSEDE old ones

### STEP 5: Save Insights

```bash
curl -s -X POST http://localhost:5003/research/{taxon_id}/save \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "claude_cli_2026_01_16",
    "model_version": "claude-opus-4-5-20251101",
    "insights": [...]
  }'
```

The orchestrator will:
1. Calculate evidence-based confidence scores (NOT your self-assessment)
2. Mark old insights as `is_current = FALSE` (superseded)
3. Save new insights with `is_current = TRUE`
4. Update species table `avg_confidence` field

Response:
```json
{
  "success": true,
  "taxon_id": "GymGiGiGnKg50344-00",
  "insights_saved": 72,
  "average_confidence": 0.847,
  "version": 1,
  "superseded_count": 0
}
```

### STEP 6: Mark Complete
```bash
curl -s -X POST http://localhost:5003/queue/{queue_id}/complete
```

### STEP 7: Loop until queue empty

---

## The 35 Research Fields

### Identity (4 fields)
- `popular_common_name` - Most widely-used name + regional variants
- `etymology` - Meaning of scientific name (Latin/Greek roots)
- `synonyms` - All taxonomic synonyms from POWO/WCVP
- `identification_features` - Key visual ID features

### Ecological (10 fields)
- `general_description` - 2-4 sentence botanical description
- `habitat` - **MULTI-INSIGHT**: One per habitat type
- `elevation_ranges` - Actual recorded elevations (meters)
- `ecological_function` - **MULTI-INSIGHT**: One per ecosystem service
- `native_adapted_habitats` - **MULTI-INSIGHT**: One per region
- `conservation_status` - IUCN + national listings
- `compatible_soil_types` - Specific soil preferences
- `climate_tolerance` - Temperature extremes + rainfall requirements
- `tolerances` - **MULTI-INSIGHT**: One per tolerance type
- `associated_species` - **MULTI-INSIGHT**: One per community type

### Morphological (10 fields)
- `growth_form` - Tree/shrub/multi-stemmed + variations
- `leaf_type` - Complete leaf description
- `deciduous_evergreen` - Note climate variation
- `flower_color` - With flowering season
- `fruit_type` - Complete fruit/seed info
- `bark_characteristics` - How bark changes with age
- `maximum_height` - Maximum + typical range (meters)
- `maximum_diameter` - DBH measurements (cm)
- `lifespan` - Typical vs maximum (years)
- `maximum_tree_age` - Oldest recorded specimen

### Stewardship (11 fields)
- `stewardship_best_practices` - **MULTI-INSIGHT**: One per practice
- `planting_recipes` - Detailed planting instructions
- `pruning_maintenance` - When and how to prune
- `disease_pest_management` - **MULTI-INSIGHT**: One per disease/pest
- `fire_management` - Fire ecology and management
- `propagation_methods` - All viable methods
- `cultural_significance` - **MULTI-INSIGHT**: One per culture/tradition
- `agroforestry_use_cases` - **MULTI-INSIGHT**: One per use case
- `timber_value` - Wood properties and commercial value
- `non_timber_products` - **MULTI-INSIGHT**: One per product category
- `nutritional_caloric_value` - Edible parts and nutrition

---

## Insight JSON Structure

```json
{
  "claim_type": "field_name",
  "claim_value": {
    "text": "The specific fact being claimed",
    "context": "Category within the field (for multi-insight fields)",
    "region": "Geographic scope if applicable"
  },
  "methodology": "extraction",
  "sources": [
    {
      "url": "https://source-url.com/...",
      "title": "Source Title",
      "type": "database|journal|government|cultural|grey_literature",
      "credibility": 0.90
    }
  ]
}
```

**Note**: Do NOT include `confidence` in your insights. The orchestrator calculates evidence-based confidence from your sources automatically.

---

## Search Strategy

### Core Searches (every species)
```
"{species}" POWO OR WCVP taxonomy accepted name
"{species}" IUCN conservation status assessment
"{species}" GBIF distribution native range
"{species}" ecology habitat ecosystem biome
"{species}" morphology height diameter bark leaf flower fruit
"{species}" traditional use ethnobotany medicinal cultural
"{species}" cultivation propagation planting agroforestry
"{species}" timber wood properties uses
```

### Grey Literature
```
"{species}" filetype:pdf site:.edu OR site:.gov
"{species}" dissertation OR thesis
"{species}" site:fao.org OR site:worldagroforestry.org
```

---

## Source Credibility Tiers

| Tier | Score | Sources |
|------|-------|---------|
| 1 | 0.90-0.98 | IUCN, POWO, WCVP, GBIF, peer-reviewed journals |
| 2 | 0.80-0.90 | FAO, USDA, World Agroforestry, Kew |
| 3 | 0.75-0.85 | Regional floras, national databases |
| 4 | 0.70-0.85 | Dissertations, grey literature |
| 5 | 0.70-0.85 | Ethnobotanical surveys, TEK |
| 6 | 0.50-0.70 | iNaturalist, Wikipedia (cross-reference) |

---

## Key Endpoints (port 5003)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/queue/next` | GET | Get next pending species |
| `/queue/{id}/start` | POST | Mark as processing |
| `/queue/{id}/complete` | POST | Mark as completed |
| `/research/{taxon_id}/context` | GET | **NEW**: Get research context (first vs re-research) |
| `/research/{taxon_id}/save` | POST | Save insights (auto-calculates confidence) |
| `/insights/{taxon_id}/gaps` | GET | **NEW**: Get gaps in existing insights |

---

## Remember

1. **ATOMIC INSIGHTS** - Split multi-value fields into separate insights
2. **50-80+ insights expected** per well-documented species
3. **If you only have ~35 insights, you're doing it wrong**
4. **CHECK CONTEXT FIRST** - Call `/research/{taxon_id}/context` before researching
5. **ADAPT your research** based on `recommended_focus`
6. **Don't include confidence** - orchestrator calculates it from sources
7. Search HARDER for poorly documented species
