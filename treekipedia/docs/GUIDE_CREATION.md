# Ecoregion Guide Creation Process

**Last Updated**: January 28, 2026

This document describes how ecoregion reforestation guides are generated, how to trigger synthesis, and planned improvements.

---

## Overview

Each ecoregion guide has two data layers:

| Layer | Source | Generated |
|-------|--------|-----------|
| **Species Rankings** | LEAF algorithm (GBIF + WCVP) | On-the-fly per request |
| **Prose Sections** | Grok 4.1 Fast synthesis | Manual trigger, stored in DB |

---

## Layer 1: LEAF Species Ranking

Calculated automatically when `/api/guides/ecoregion/:eco_id` is called.

### Algorithm

```
1. Query geohash_species_tiles WHERE eco_id = :eco_id
2. Aggregate: affinity = occurrence_count × tile_count
3. Check WCVP native/introduced status for ecoregion's countries
4. Apply multipliers:
   - Native species: ×2.0 boost
   - Unknown origin: ×1.0 neutral
   - Introduced species: EXCLUDED
5. Percentile normalize → LEAF score (0-100)
6. Assign tiers: BEST (≥90), GOOD (≥70), ACCEPTABLE (≥50), LOW (<50)
```

### Data Sources

- **Occurrences**: `geohash_species_tiles` (6.46M tiles, 96.5M occurrences)
- **Native Status**: `species.wcvp_native`, `species.wcvp_introduced`
- **Country Mapping**: `backend/utils/wcvpRegions.js`

### No Action Required

This layer is always current - no manual steps needed.

---

## Layer 2: AI Synthesis

Generates prose sections stored in `ecoregion_guides` table.

### Sections Generated

1. **overview_intro** — 2-3 paragraphs on ecoregion ecology, biodiversity, reforestation potential
2. **planting_strategy** — Species mix ratios, canopy layering, successional stages, spacing
3. **climate_context** — Temperature, precipitation, seasonal patterns affecting establishment
4. **conservation_notes** — Threatened species, habitat connectivity, conservation alignment

### Trigger Synthesis

**Single ecoregion:**
```bash
curl -X POST "https://treekipedia-api.silvi.earth/api/guides/ecoregion/806/synthesize"
```

**Regenerate existing:**
```bash
curl -X POST "https://treekipedia-api.silvi.earth/api/guides/ecoregion/806/synthesize?force=true"
```

**Batch synthesis (example script):**
```bash
#!/bin/bash
# synthesize_guides.sh

ECOREGIONS=(806 331 329 330 748 749)  # Add target eco_ids

for eco_id in "${ECOREGIONS[@]}"; do
  echo "Synthesizing guide for ecoregion $eco_id..."
  curl -s -X POST "https://treekipedia-api.silvi.earth/api/guides/ecoregion/$eco_id/synthesize"
  echo ""
  sleep 10  # Rate limit buffer
done
```

### What Happens During Synthesis

1. Fetch ecoregion metadata (name, biome, realm, area)
2. Get top 20 species by occurrence with `_ai` fields:
   - `general_description_ai`
   - `habitat_ai`
   - `ecological_function_ai`
   - `maximum_height_ai`
   - `conservation_status_ai`
3. Build prompt with ecoregion context + species summaries
4. Call Grok 4.1 Fast (`grok-4-1-fast-reasoning`) with web search enabled
5. Parse JSON response into 4 sections
6. Upsert into `ecoregion_guides` table

### Database Schema

```sql
CREATE TABLE ecoregion_guides (
  eco_id NUMERIC PRIMARY KEY,
  overview_intro TEXT,
  planting_strategy TEXT,
  climate_context TEXT,
  conservation_notes TEXT,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  model_used VARCHAR(100),
  synthesis_version INTEGER DEFAULT 1,
  species_count INTEGER,
  source_data JSONB
);
```

### Files Involved

| File | Purpose |
|------|---------|
| `backend/services/guideSynthesis.js` | Grok API call, prompt construction |
| `backend/controllers/guides.js` | API endpoints, species data assembly |
| `backend/routes/guides.js` | Route mounting |
| `database/09_ecoregion_guides_table.sql` | Table schema |

---

## Viewing Guides

### Frontend Routes

- `/guide` — Search ecoregions by name
- `/guide/[eco_id]` — View guide with accordion sections

### API Endpoints

```bash
# Search ecoregions
GET /api/geospatial/ecoregions/search?q=tyrr

# Get full guide data
GET /api/guides/ecoregion/806

# Trigger synthesis
POST /api/guides/ecoregion/806/synthesize
POST /api/guides/ecoregion/806/synthesize?force=true
```

---

## Current Status

| Ecoregion | eco_id | Synthesized | Species Count |
|-----------|--------|-------------|---------------|
| Tyrrhenian-Adriatic | 806 | No | 1,208 |
| Appalachian-Blue Ridge | 331 | No | 2,835 |
| Appalachian mixed mesophytic | 329 | No | TBD |
| Appalachian Piedmont | 330 | No | TBD |

---

## Implemented Features

### 1. Popular Common Names ✅

**Status**: Implemented in species research (Grok Atomic v2)

The `popular_common_name_ai` field is populated during species research with the single most recognizable English common name. This is used in guide synthesis instead of the messy semicolon-separated `common_name` field.

**Example**:
```
common_name: "; Common Myrtle; Arrayán, Mirto; Myrte..."
popular_common_name_ai: "Common Myrtle"
```

### 2. Region-Specific Common Names ✅

**Status**: Implemented in guide synthesis

The synthesis service automatically detects the ecoregion's countries and local languages, then instructs Grok to use both English and local names where appropriate.

**How it works**:
1. `guides.js` queries countries that intersect with the ecoregion
2. `guideSynthesis.js` maps countries → languages via `COUNTRY_LANGUAGES` lookup (~100 countries)
3. Prompt includes naming instruction: "Use English Name (Local Name)" format
4. Grok picks appropriate regional names from the `common_name` field

**Example prompt addition for Tyrrhenian (Italy)**:
```
NAMING CONVENTION:
This ecoregion spans: Italy
Local languages: Italian
Format: "English Name (Local Name)" - e.g., "Common Myrtle (Mirto)"
```

**Files**:
- `backend/services/guideSynthesis.js` - `COUNTRY_LANGUAGES` map, `getLocalLanguages()`
- `backend/controllers/guides.js` - fetches countries, passes to synthesis

---

## Planned Improvements

### 3. Species Research Gating

**Problem**: Top species may not have `_ai` fields populated (show "NA").

**Solution**:
- Before synthesis, check if top 20 species have research data
- If <50% researched, prompt user to research species first
- Or auto-trigger research for top species before synthesis

### 4. Synthesis Quality Scoring

**Problem**: No way to assess guide quality.

**Solution**:
- Track which species were referenced in synthesis
- Score based on: species coverage, section completeness, specificity
- Store quality metrics in `source_data` JSONB

### 5. Frontend Synthesis Button

**Problem**: Synthesis requires API call, no UI.

**Solution**:
- Add "Generate AI Synthesis" button on guide page (when no synthesis exists)
- Gate behind authentication or payment
- Show progress indicator during generation

### 6. Incremental Updates

**Problem**: Full regeneration required for any update.

**Solution**:
- Track species list hash at synthesis time
- Detect when top species have changed significantly
- Offer "Update synthesis" when stale

---

## Quality Checklist

Before publishing a synthesized guide:

- [ ] Top 10 species have research data (not "NA")
- [ ] Synthesis references specific species by name
- [ ] Planting strategy is biome-appropriate
- [ ] Conservation notes mention any threatened species
- [ ] No generic/placeholder content
- [ ] Common names are recognizable

---

## Related Documentation

- [docs/todo/ecoregion-reforestation-guides.md](todo/ecoregion-reforestation-guides.md) — Planning doc
- [docs/LEAF_INTEGRATION_GUIDE.md](LEAF_INTEGRATION_GUIDE.md) — LEAF algorithm details
- [SPECIES_FIELDS_FRONTEND_GUIDE.md](../SPECIES_FIELDS_FRONTEND_GUIDE.md) — Species field reference
