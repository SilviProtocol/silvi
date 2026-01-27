# Claude Code Native Research Architecture

## Overview

This document outlines a **Claude Code-native** approach to AI research for Treekipedia, leveraging Claude models (Haiku, Sonnet, Opus) instead of local LLMs. The architecture prioritizes:

1. **Local-first processing** - Run research orchestration on your machine
2. **Minimal cloud costs** - Use Digital Ocean / GCP only for serving static data
3. **Claude model optimization** - Use Haiku for research, Sonnet/Opus for synthesis
4. **Queue-based research** - Maintain a persistent research queue that survives sessions

---

## Current Data State (January 2025)

| Dataset | Records | Size | Location |
|---------|---------|------|----------|
| **Species Knowledge V11** | 67,750 species | 1.4 GB | `Treekipedia_V11_Native_introduced_December_09d.csv` |
| **Occurrences** | 96.5M records | 526 MB (parquet) | `Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet` |
| **Production DB** | 67,743 species | 8.5 GB | Digital Ocean PostgreSQL |

### Schema: 133 columns including:
- Taxonomy: `taxon_id_new`, `species_scientific_name`, `family`, `genus`
- Native status: `wcvp_native`, `wcvp_introduced`, `countries_native`, `countries_invasive`
- AI fields: `general_description_ai`, `ecological_function_ai`, etc.
- Human fields: `general_description_human`, `ecological_function_human`, etc.
- Research status: `researched` (boolean/NA)

---

## Architecture: Claude Code as Research Orchestrator

### Why Claude Code Instead of Local LLMs?

| Aspect | Local LLMs (Ollama/LM Studio) | Claude Code Native |
|--------|-------------------------------|-------------------|
| **Setup complexity** | High (model downloads, GPU, RAM) | Zero (already using it) |
| **Research quality** | Variable (small models hallucinate) | High (Claude excels at synthesis) |
| **Cost** | Free compute, but time-intensive | API costs, but quota-optimized |
| **Orchestration** | Need custom queue system | Claude Code IS the orchestrator |
| **Multi-model consensus** | Complex to implement | Built-in (Haiku vs Sonnet vs Opus) |

### Model Strategy: Tiered Research

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESEARCH PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. HAIKU AGENTS (Cheap, Fast, Parallel)                       │
│     ├── Web search for species info                            │
│     ├── Extract structured data from sources                   │
│     ├── Parse GBIF/Wikipedia/iNaturalist                       │
│     └── Generate candidate insights                            │
│                                                                 │
│  2. SONNET (Balanced, Synthesis)                               │
│     ├── Validate Haiku outputs                                 │
│     ├── Cross-reference multiple sources                       │
│     ├── Resolve conflicts between extractions                  │
│     └── Structure final JSON output                            │
│                                                                 │
│  3. OPUS (Deep Analysis, Quality Control)                      │
│     ├── Complex ecological reasoning                           │
│     ├── Final quality review for high-value species            │
│     └── Schema alignment verification                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategy

| Model | Cost/1M tokens | Use Case | % of Workload |
|-------|----------------|----------|---------------|
| **Haiku** | $0.25 input, $1.25 output | Research & extraction | 70% |
| **Sonnet** | $3 input, $15 output | Synthesis & validation | 25% |
| **Opus** | $15 input, $75 output | Quality control | 5% |

**Estimated cost per species**: ~$0.01-0.05 (mostly Haiku)
**Estimated cost for 67k species**: $670 - $3,350

---

## Implementation Plan

### Phase 1: Research Queue System

Create a local SQLite database to track research progress:

```sql
-- research_queue.db

CREATE TABLE research_queue (
    taxon_id TEXT PRIMARY KEY,
    species_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, researching, completed, failed
    priority INTEGER DEFAULT 0,
    haiku_output JSONB,
    sonnet_output JSONB,
    opus_output JSONB,
    final_output JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE research_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taxon_id TEXT REFERENCES research_queue(taxon_id),
    source_type TEXT,  -- gbif, wikipedia, inaturalist, web
    source_url TEXT,
    raw_content TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE research_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taxon_id TEXT REFERENCES research_queue(taxon_id),
    aspect TEXT,  -- morphology, ecology, soil, tolerances, etc.
    model TEXT,   -- haiku, sonnet, opus
    value JSONB,
    confidence FLOAT,
    sources TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Phase 2: Claude Code Research Skill

Create a custom Claude Code skill that can be invoked to research species:

**File: `.claude/skills/research-species.md`**

```markdown
# Species Research Skill

## Trigger
/research <taxon_id> or /research-batch <count>

## Process
1. Load species from queue with status='pending'
2. For each species:
   a. Search web for authoritative sources (GBIF, Wikipedia, POWO)
   b. Extract structured data for each aspect
   c. Validate and synthesize
   d. Update queue with results
3. Commit results to staging table

## Aspects to Research
- general_description
- ecological_function
- elevation_ranges
- compatible_soil_types
- habitat
- growth_form
- leaf_type
- deciduous_evergreen
- maximum_height
- conservation_status
- native_adapted_habitats
- agroforestry_use_cases
- tolerances
- stewardship_best_practices
```

### Phase 3: Infrastructure Setup

```
┌──────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Claude Code                                                │ │
│  │  ├── Research orchestration                                │ │
│  │  ├── SQLite queue (research_queue.db)                      │ │
│  │  ├── Staging data (JSON files)                             │ │
│  │  └── Sync scripts to production                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (Local Dev Copy)                               │ │
│  │  └── Full sync from production for testing                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                            │
                            │ Sync completed research
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   DIGITAL OCEAN (or GCP)                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL 17 + PostGIS                                   │ │
│  │  ├── species table (67k rows, 133 columns)                 │ │
│  │  ├── geohash_species_tiles (5.7M rows)                     │ │
│  │  └── species_alphaearth_centroids (500 rows)               │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Express.js API                                             │ │
│  │  └── Read-only endpoints (no AI calls on server)           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Research Workflow

### Step 1: Initialize Queue

```bash
# Run once to populate queue from species that need research
python3 scripts/init_research_queue.py \
    --source "Treekipedia_V11_Native_introduced_December_09d.csv" \
    --filter "researched == 'NA' or researched == False" \
    --output "research_queue.db"
```

### Step 2: Run Research Session

In Claude Code:
```
/research-batch 10
```

This triggers:
1. Pick 10 pending species from queue
2. For each species, use Haiku to search and extract
3. Use Sonnet to validate and synthesize
4. Mark as completed in queue
5. Output structured JSON ready for database import

### Step 3: Review and Sync

```bash
# Review completed research
python3 scripts/review_research.py --queue research_queue.db

# Sync to production (only verified entries)
python3 scripts/sync_to_production.py \
    --queue research_queue.db \
    --status verified \
    --target production
```

---

## Haiku Research Agent Template

When researching a species, the Haiku agent should:

```markdown
## Research Task: {species_scientific_name}

### Step 1: Gather Sources
Search for:
1. GBIF species page: https://www.gbif.org/species/{taxon_id}
2. Wikipedia: {species_scientific_name}
3. Plants of the World Online (POWO)
4. iNaturalist observations

### Step 2: Extract by Aspect
For each aspect, extract structured JSON:

**general_description**:
- 2-3 sentence description of the species
- Include growth form, size, distinctive features

**ecological_function**:
- Role in ecosystem
- Nitrogen fixation, wildlife habitat, etc.

**elevation_ranges**:
- Format: "min-max meters" or "sea level to X meters"

**compatible_soil_types**:
- List: Clay, Loam, Sandy, etc.

**habitat**:
- Natural habitat description

**tolerances**:
- Drought, flood, shade, salt tolerance

### Step 3: Cite Sources
For each extracted fact, record:
- Source URL
- Snippet used
- Confidence (0.0-1.0)
```

---

## Sonnet Synthesis Template

```markdown
## Synthesis Task: {species_scientific_name}

### Input
- Haiku extraction results (multiple aspects)
- Raw source content

### Validation Steps
1. Check for contradictions between sources
2. Verify scientific accuracy of claims
3. Ensure values match expected formats

### Output Schema
```json
{
    "taxon_id": "string",
    "species_scientific_name": "string",
    "research_date": "ISO timestamp",
    "aspects": {
        "general_description_ai": "string",
        "ecological_function_ai": "string",
        "elevation_ranges_ai": "string",
        "compatible_soil_types_ai": ["string"],
        "habitat_ai": "string",
        "growth_form_ai": "string",
        "leaf_type_ai": "string",
        "deciduous_evergreen_ai": "string",
        "maximum_height_ai": "string",
        "conservation_status_ai": "string"
    },
    "confidence_scores": {
        "general_description": 0.85,
        "ecological_function": 0.75
    },
    "sources": [
        {"url": "string", "type": "string", "accessed": "timestamp"}
    ]
}
```

---

## Migration: Load New Data to Production

### 1. Update Species Table with V11 Data

```sql
-- Backup current data
CREATE TABLE species_backup_jan2025 AS SELECT * FROM species;

-- Load new columns from V11 CSV
-- wcvp_native, wcvp_introduced are new authoritative fields
ALTER TABLE species ADD COLUMN IF NOT EXISTS wcvp_native TEXT;
ALTER TABLE species ADD COLUMN IF NOT EXISTS wcvp_introduced TEXT;

-- Update from CSV (use COPY or psql \copy)
```

### 2. Update Occurrences (96.5M records)

The new occurrence data has 96.5M records with clean taxon_id mappings.

Options:
- **Option A**: Import to new geohash table (rebuild)
- **Option B**: Incremental update existing tiles

```python
# Example: Convert parquet to geohash tiles
import pandas as pd
import geohash2

df = pd.read_parquet('Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet')

# Generate L7 geohashes
df['geohash_l7'] = df.apply(
    lambda row: geohash2.encode(row['decimalLatitude'], row['decimalLongitude'], precision=7),
    axis=1
)

# Aggregate by geohash
tiles = df.groupby('geohash_l7').agg({
    'taxon_id': lambda x: list(set(x)),
    'decimalLatitude': 'first',
    'decimalLongitude': 'first'
}).reset_index()
```

---

## Cost Comparison

| Approach | Compute Cost | API Cost | Time | Quality |
|----------|--------------|----------|------|---------|
| **Local LLMs (Phi-3, Qwen)** | $0 | $0 | Slow | Medium |
| **Claude Haiku Only** | $0 | ~$670 | Fast | Good |
| **Claude Haiku + Sonnet** | $0 | ~$1,500 | Fast | High |
| **Full Pipeline (H+S+O)** | $0 | ~$3,000 | Fast | Excellent |

**Recommendation**: Start with Haiku-only for 90% of species, use Sonnet for validation, reserve Opus for complex/important species.

---

## Next Steps

1. [ ] Create research queue SQLite schema
2. [ ] Initialize queue with 67k species (prioritize unresearched)
3. [ ] Create `/research` Claude Code skill
4. [ ] Test with 10 species batch
5. [ ] Validate output schema matches database
6. [ ] Build sync script to production
7. [ ] Import V11 knowledge data to production DB
8. [ ] Import new occurrence data (96.5M records)

---

## Files Reference

| File | Purpose |
|------|---------|
| `research_queue.db` | Local SQLite queue (to be created) |
| `Treekipedia_V11_Native_introduced_December_09d.csv` | Latest species knowledge |
| `Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet` | Latest occurrence data |
| `.claude/skills/research-species.md` | Claude Code skill definition |
| `scripts/init_research_queue.py` | Queue initialization |
| `scripts/sync_to_production.py` | Sync research results |

---

*Document Version: 1.0*
*Created: January 5, 2026*
