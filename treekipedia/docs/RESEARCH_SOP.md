# Research SOP — Species Research Queue Processing

**Purpose**: Standard operating procedure for Claude Code sessions processing the Treekipedia species research queue. Hand this file to a new session to continue batch research.

---

## Quick Start

```bash
API="https://treekipedia-api.silvi.earth"

# Check queue status
curl -s $API/research/queue/status | jq .

# Get next pending species
curl -s $API/research/queue/next | jq .

# See what's been done
curl -s "$API/research/queue/status" | jq '.completed, .pending'
```

---

## Research Workflow

### Option A: Use the `/species-research` Skill (Recommended)

The Claude Code skill `/species-research` handles the full research pipeline autonomously — web research, insight generation, and saving via API. Invoke it and it will pull from the queue.

```
/species-research
```

The skill will:
1. Fetch next species from queue
2. Lock it (`POST /research/queue/{id}/start`)
3. Conduct deep research across 35 fields
4. Generate 50-80+ atomic insights with sources
5. Save via `POST /research/{taxon_id}/save`
6. Mark complete (`POST /research/queue/{id}/complete`)
7. Move to next species

### Option B: Direct Grok API Research

For instant research using the backend's Grok Atomic v2 endpoint:

```bash
# Research a specific species (fires 2 parallel Grok calls, creates insights automatically)
curl -s -X POST $API/species/{taxon_id}/research | jq .

# Then mark the queue entry complete
curl -s -X POST $API/research/queue/{id}/complete
```

This uses Grok 4.1 Fast with agentic web search. Returns 50-80+ insights per species. No manual insight formatting needed — the backend handles insight creation and sync to `_ai` columns.

### Option C: Manual Queue Workflow

Step-by-step for full control:

```bash
API="https://treekipedia-api.silvi.earth"

# 1. Get next pending species
curl -s $API/research/queue/next
# Returns: {"queue_id": N, "taxon_id": "...", "species_name": "...", ...}

# 2. Lock it (prevents other sessions from picking it up)
curl -s -X POST $API/research/queue/{queue_id}/start

# 3. Check research context (first research? gaps? priority fields?)
curl -s $API/research/{taxon_id}/context

# 4. Conduct research and save atomic insights
curl -s -X POST $API/research/{taxon_id}/save \
  -H "Content-Type: application/json" \
  -d '{"model_version": "claude-opus-4-5-20251101", "insights": [...]}'

# 5. Mark complete
curl -s -X POST $API/research/queue/{queue_id}/complete
```

---

## Current Queue: Ecoregion 806 Pilot (Sicily)

**Ecoregion**: Tyrrhenian-Adriatic sclerophyllous and mixed forests
**Progress**: 2/25 researched

| Queue ID | taxon_id | Species | Status |
|----------|----------|---------|--------|
| 1 | AngMaMyMyRt39690-00 | Myrtus communis | **completed** (67 insights) |
| — | AngMaFaFgCx14759-00 | Quercus ilex | **completed** (73 insights, researched directly) |
| 2 | AngMaErRcCa06930-00 | Arbutus unedo | pending |
| 3 | AngMaLaLcXx20795-00 | Olea europaea | pending |
| 4 | AngMaFaFbCx10351-00 | Ceratonia siliqua | pending |
| 5 | AngMaRoRhMn44052-00 | Rhamnus alaternus | pending |
| 6 | GymPiPiPnCx50774-00 | Pinus halepensis | pending |
| 7 | AngMaDiVbRn04478-00 | Viburnum tinus | pending |
| 8 | AngMaRoRsCx44614-00 | Pyrus spinosa | pending |
| 9 | AngMaErRcCa06994-00 | Erica arborea | pending |
| 10 | AngNAPaRcCx49866-00 | Chamaerops humilis | pending |
| 11 | GymPiPiPnCx50811-00 | Pinus pinaster | pending |
| 12 | AngMaCaTmRc03532-00 | Tamarix africana | pending |
| 13 | AngMaMaPhRb29612-00 | Euphorbia dendroides | pending |
| 14 | AngMaLaLcXx20828-00 | Phillyrea latifolia | pending |
| 15 | AngMaFaFgCx14925-00 | Quercus suber | pending |
| 16 | AngMaLaLmCx21234-00 | Vitex agnus-castus | pending |
| 17 | AngMaLaLrCx22770-00 | Laurus nobilis | pending |
| 18 | AngMaFaFgCx14877-00 | Quercus pubescens | pending |
| 19 | AngMaRoCnNb42825-00 | Celtis australis | pending |
| 20 | GymPiPiTxCx50907-00 | Taxus baccata | pending |
| 21 | AngMaRoRsCx44529-00 | Prunus spinosa | pending |
| 22 | AngMaFaFbCx10360-00 | Cercis siliquastrum | pending |
| 23 | GymPiPiPnCx50813-00 | Pinus pinea | pending |
| 24 | AngMaLaLcXx20652-00 | Fraxinus ornus | pending |

---

## Insight JSON Structure

Each insight is an atomic fact. Array fields (habitat, ecological_function, tolerances, etc.) should produce multiple insights — one per distinct claim.

```json
{
  "claim_type": "habitat",
  "claim_value": {
    "text": "Dominant species in Mediterranean maquis shrubland",
    "context": "maquis/woodland",
    "region": "Mediterranean basin",
    "source_hint": "EUFORGEN species profile"
  },
  "confidence": 0.85,
  "methodology": "extraction",
  "sources": [
    {
      "url": "https://www.euforgen.org/species/quercus-ilex",
      "title": "EUFORGEN - Quercus ilex",
      "type": "database",
      "credibility": 0.90
    }
  ]
}
```

### 35 Research Fields

**Identity (4)**: popular_common_name, etymology, synonyms, identification_features

> **Note on `popular_common_name`**: The `common_name` database field contains semicolon-separated names in multiple languages (e.g., `"; Common Myrtle; Arrayán, Mirto; ミルツス..."`). The `popular_common_name_ai` field provides a single, clean English name (e.g., `"Common Myrtle"`) for use in guides, search results, and UI display.
**Ecological (10)**: general_description, habitat, elevation_ranges, ecological_function, native_adapted_habitats, conservation_status, compatible_soil_types, climate_tolerance, tolerances, associated_species
**Morphological (10)**: growth_form, leaf_type, deciduous_evergreen, flower_color, fruit_type, bark_characteristics, maximum_height, maximum_diameter, lifespan, maximum_tree_age
**Stewardship (11)**: stewardship_best_practices, planting_recipes, pruning_maintenance, disease_pest_management, fire_management, propagation_methods, cultural_significance, agroforestry_use_cases, timber_value, non_timber_products, nutritional_caloric_value

### Array Fields (produce multiple insights each)

These 12 fields return arrays of `{text, context, region?, source_hint?}`:
`habitat`, `ecological_function`, `native_adapted_habitats`, `tolerances`, `associated_species`, `stewardship_best_practices`, `disease_pest_management`, `cultural_significance`, `agroforestry_use_cases`, `non_timber_products`

Target: 50-80+ total insights per species across all fields.

---

## Verification

After researching a species, verify:

```bash
# Check insights were saved
curl -s "$API/species/{taxon_id}/insights?full=true" | jq '.metadata'
# Should show: insight_count (50+), avg_confidence (0.7+), source_count

# Check _ai columns were synced
curl -s "$API/species/{taxon_id}" | jq '.general_description_ai, .habitat_ai, .ecological_function_ai'
# Should show non-null AI-generated text

# Check gaps
curl -s "$API/research/insights/{taxon_id}/gaps" | jq .
# Should show few/no missing fields
```

---

## Multi-Session Coordination

The queue has built-in locking. Multiple sessions can process simultaneously:
- `POST /research/queue/{id}/start` locks a species as "processing"
- `/research/queue/next` skips locked and completed entries
- If a session crashes, locked entries can be re-fetched (no automatic timeout currently)

---

## After All 25 Are Complete

Once all pilot species are researched:
1. Update the tracker in `docs/todo/ecoregion-reforestation-guides.md`
2. Update `ACTIVE.md` with new researched species count
3. Notify the team — Phase 2 (backend guide endpoint) and Phase 3 (frontend pages) can proceed

---

## Reference

- **Research queue API**: [PUBLIC_API_GUIDE.md](../PUBLIC_API_GUIDE.md#research-queue-api--batch-species-research)
- **Planning doc**: [docs/todo/ecoregion-reforestation-guides.md](todo/ecoregion-reforestation-guides.md)
- **Grok research service**: `backend/services/grokResearch.js`
- **Species controller**: `backend/controllers/species.js`
- **Research controller**: `backend/controllers/research.js`
