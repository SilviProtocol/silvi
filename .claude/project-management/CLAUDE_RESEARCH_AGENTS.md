# Claude Research Agent Architecture for Treekipedia

**Version**: 4.0
**Created**: January 5, 2026
**Updated**: January 6, 2026
**Status**: Implemented and Tested

---

## Executive Summary

Claude Code CLI-native research system for enriching Treekipedia's 67,743 species. Uses a **unified research agent** (consolidated from 4 agents) with auto-approved WebSearch for seamless operation. Queue-based workflow from web UI to CLI research.

**Key Files**:
- `orchestrator/unified_research_prompt.py` - **NEW** Single unified prompt for all 35 fields
- `orchestrator/research_prompts.py` - Legacy 4-agent prompts (deprecated)
- `orchestrator/research_orchestrator.py` - Queue and insights API (port 5003)
- `.claude/skills/species-research/SKILL.md` - **NEW** Claude Code skill definition
- `.claude/hooks/approve-research-websearch.py` - **NEW** Auto-approve hook for WebSearch
- `.claude/settings.json` - **NEW** Hook configuration

**Recent Changes (v4.0)**:
1. Consolidated 4 agents into 1 unified research session per species
2. Added Claude Code skill for standardized research workflow
3. Added PreToolUse hook for auto-approving research WebSearches
4. Improved context building by researching all 35 fields in one session

---

## 1. Research Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED RESEARCH WORKFLOW (v4.0)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  WEB UI                                                                  │
│    │                                                                     │
│    ▼                                                                     │
│  [Click Research Button] ─────► research_queue table                    │
│                                       │                                  │
│  CLI (with auto-approve hook)         │                                  │
│    │                                  ▼                                  │
│    ├── /research (skill) or python scripts/research_species.py --next  │
│    │                                  │                                  │
│    ▼                                  ▼                                  │
│  UNIFIED AGENT (1 per species):                                         │
│    └── ALL 35 fields in one session ─► WebSearch (auto-approved)       │
│        • Identity (4)     │            └── approve-research-websearch.py│
│        • Ecological (10)  │                                              │
│        • Morphological (10)│           Builds context as research       │
│        • Stewardship (11) │           progresses for better quality     │
│                                                                          │
│    ▼                                                                     │
│  POST /research/{taxon_id}/save ─────► insights table                   │
│                                              │                           │
│    ▼                                         ▼                           │
│  POST /queue/{id}/complete          species.*_ai columns synced         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Unified Agent (v4.0)?

**Before (4 agents):**
- Each agent ran independently
- No context sharing between agents
- 4 separate sessions per species
- Redundant searches for same data

**After (1 unified agent):**
- Single session builds cumulative context
- Information from taxonomy informs ecology searches
- Conservation status informs stewardship recommendations
- Better cross-referencing and consistency
- Fewer redundant searches

---

## 1.5 Auto-Approve Hook Configuration

The research system includes an automatic approval hook for WebSearch tool calls that match botanical research patterns. This eliminates manual approval prompts during research sessions.

### Files

| File | Purpose |
|------|---------|
| `.claude/hooks/approve-research-websearch.py` | Hook script that validates WebSearch queries |
| `.claude/settings.json` | Hook configuration |
| `.claude/skills/species-research/SKILL.md` | Skill definition for research workflow |

### How It Works

1. **PreToolUse Hook**: Before any WebSearch call, the hook script runs
2. **Pattern Matching**: Query is checked against research keywords (species, IUCN, habitat, etc.)
3. **Security**: Blocked patterns prevent non-research searches (passwords, exploits, etc.)
4. **Decision**: Research queries are auto-approved; others fall through to manual approval

### Approved Query Patterns

The hook auto-approves queries containing:
- Species/taxonomy terms: `species`, `tree`, `plant`, `genus`, `family`, `flora`
- Database names: `IUCN`, `GBIF`, `POWO`, `WCVP`, `Kew`, `FAO`, `USDA`
- Ecological terms: `habitat`, `ecosystem`, `distribution`, `conservation`
- Morphology terms: `height`, `bark`, `leaf`, `flower`, `fruit`
- Stewardship terms: `propagation`, `cultivation`, `agroforestry`, `timber`
- Common genus names: `Acacia`, `Quercus`, `Pinus`, `Eucalyptus`, etc.

### Verification

```bash
# Test that research queries are approved
echo '{"tool_name": "WebSearch", "tool_input": {"query": "Acacia acuminata IUCN"}}' | \
  python3 .claude/hooks/approve-research-websearch.py
# Should output: {"hookSpecificOutput": {"permissionDecision": "allow", ...}}

# Test that non-research queries fall through
echo '{"tool_name": "WebSearch", "tool_input": {"query": "weather today"}}' | \
  python3 .claude/hooks/approve-research-websearch.py
# Should output nothing (exit 0, no auto-approval)
```

---

## 2. Research Fields (35 Total)

### Identity Agent (4 fields)
```
popular_common_name, etymology, synonyms, identification_features
```

### Ecological Agent (10 fields)
```
general_description, habitat, elevation_ranges, ecological_function,
native_adapted_habitats, conservation_status, compatible_soil_types,
climate_tolerance, tolerances, associated_species
```

### Morphological Agent (10 fields)
```
growth_form, leaf_type, deciduous_evergreen, flower_color, fruit_type,
bark_characteristics, maximum_height, maximum_diameter, lifespan, maximum_tree_age
```

### Stewardship Agent (11 fields)
```
stewardship_best_practices, planting_recipes, pruning_maintenance,
disease_pest_management, fire_management, propagation_methods,
cultural_significance, agroforestry_use_cases, timber_value,
non_timber_products, nutritional_caloric_value
```

---

## 3. Agent Architecture

Each agent has an **exact prompt** defined in `orchestrator/research_prompts.py`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         4 SPECIALIZED AGENTS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  IDENTITY AGENT (4 fields)                                               │
│    └── Names, etymology, synonyms, visual ID features                   │
│    └── Sources: POWO, WCVP, IPNI, regional floras                       │
│                                                                          │
│  ECOLOGICAL AGENT (10 fields)                                            │
│    └── Habitat, conservation, distribution, ecology                     │
│    └── Sources: IUCN, GBIF, FAO Ecocrop, ecological studies            │
│                                                                          │
│  MORPHOLOGICAL AGENT (10 fields)                                         │
│    └── Physical traits, dimensions, appearance                          │
│    └── Sources: Flora databases, botanical descriptions                 │
│                                                                          │
│  STEWARDSHIP AGENT (11 fields)                                           │
│    └── Cultivation, uses, cultural significance                         │
│    └── Sources: FAO, ICRAF, USDA, ethnobotanical databases             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Design Principles**:
1. **Exact prompts** - Same prompt structure every time for reproducibility
2. **Structured output** - Each field has a specific JSON schema
3. **Source citations** - Every insight must cite sources with credibility scores
4. **Confidence tracking** - 0.0-1.0 confidence per insight

---

## 3. Research Prompt

```python
RESEARCH_PROMPT = """
Research the tree species "{scientific_name}" (Family: {family}, Native to: {wcvp_native}).

Return a JSON object with these fields. Use null for unavailable data. Be concise but accurate.

IDENTITY:
- popular_common_name: Most widely-used English common name
- etymology: Origin/meaning of scientific name (brief)
- identification_features: 2-3 key visual ID features

ECOLOGICAL:
- general_description: 2-3 sentence botanical description
- habitat: Natural habitat types
- elevation_ranges: "min-max" in meters
- ecological_function: Key ecological roles
- native_adapted_habitats: Native range and climate zones
- conservation_status: IUCN status if known
- compatible_soil_types: Soil preferences
- climate_tolerance: Temperature/precipitation preferences
- tolerances: Drought/flood/salt tolerance

MORPHOLOGICAL:
- growth_form: tree/shrub/palm/etc
- leaf_type: simple/compound/needle/etc
- deciduous_evergreen: deciduous/evergreen/semi-deciduous
- flower_color: Primary colors
- fruit_type: Fruit/seed type
- bark_characteristics: Texture and color
- maximum_height: Number only (meters)
- maximum_diameter: Number only (meters DBH)
- lifespan: Typical lifespan
- maximum_tree_age: Number only (years)

STEWARDSHIP:
- stewardship_best_practices: Care guidelines
- planting_recipes: Planting conditions
- pruning_maintenance: Pruning needs
- disease_pest_management: Common issues
- fire_management: Fire tolerance
- propagation_methods: Seed/cutting/grafting

USES:
- cultural_significance: Traditional importance
- agroforestry_use_cases: Agroforestry applications
- timber_value: Wood quality/uses
- non_timber_products: Fruits, resins, medicines
- nutritional_caloric_value: Edible parts (if any)

Return ONLY valid JSON. No markdown, no explanation.
"""
```

---

## 3.5 Insight-Based Output Format (FAIR-Compliant)

**Updated January 6, 2026** - Research agents now output insights with provenance.

Instead of flat field values, agents return **insights** that include:
- `claim_value`: The actual data (text or structured)
- `confidence`: 0.0-1.0 certainty score
- `sources`: Array of citations with URLs and metadata

### Insight Output Schema

```json
{
  "taxon_id": "AngMaFaFgCx14888-20",
  "species_name": "Quercus robur",
  "research_session_id": "session_2026-01-06_001",
  "model_version": "claude-3-haiku-20240307",
  "agent_type": "ecological",
  "insights": [
    {
      "claim_type": "maximum_height",
      "claim_value": {"value": 40, "unit": "meters", "note": "exceptional specimens to 45m"},
      "confidence": 0.90,
      "methodology": "extraction",
      "sources": [
        {
          "url": "https://www.conifers.org/cu/Quercus_robur.php",
          "title": "Quercus robur - The Gymnosperm Database",
          "type": "database",
          "accessed_date": "2026-01-06",
          "credibility": 0.85
        },
        {
          "url": "https://www.iucnredlist.org/species/194843/167525622",
          "title": "IUCN Red List - Quercus robur",
          "type": "database",
          "accessed_date": "2026-01-06",
          "credibility": 0.95
        }
      ]
    },
    {
      "claim_type": "habitat",
      "claim_value": {"text": "Temperate broadleaf and mixed forests, particularly on clay-rich soils in lowland areas"},
      "confidence": 0.85,
      "methodology": "extraction",
      "sources": [
        {
          "url": "https://www.worldagroforestry.org/treedb2/speciesprofile.php?Ession=0&Spession=0&Id=1559",
          "title": "World Agroforestry - Quercus robur",
          "type": "database",
          "accessed_date": "2026-01-06",
          "credibility": 0.80
        }
      ]
    },
    {
      "claim_type": "conservation_status",
      "claim_value": {"iucn_status": "LC", "full_name": "Least Concern", "year_assessed": 2017},
      "confidence": 0.95,
      "methodology": "extraction",
      "sources": [
        {
          "url": "https://www.iucnredlist.org/species/194843/167525622",
          "title": "IUCN Red List - Quercus robur",
          "type": "database",
          "doi": "10.2305/IUCN.UK.2018-1.RLTS.T194843A167525622.en",
          "accessed_date": "2026-01-06",
          "credibility": 0.98
        }
      ]
    }
  ],
  "token_usage": {
    "input_tokens": 1200,
    "output_tokens": 800,
    "cost_usd": 0.005
  }
}
```

### Source Types & Credibility Scores

| Source Type | Default Credibility | Examples |
|-------------|---------------------|----------|
| `peer_reviewed` | 0.90-0.98 | DOI-linked papers |
| `database` | 0.80-0.95 | IUCN, GBIF, WCVP, Kew |
| `institutional` | 0.75-0.85 | FAO, USDA, university extensions |
| `book` | 0.70-0.85 | Published field guides |
| `website` | 0.50-0.70 | Wikipedia, general web |
| `model_inference` | 0.40-0.60 | AI reasoning without source |

### Updated Research Prompt (with sources)

```python
INSIGHT_RESEARCH_PROMPT = """
Research the tree species "{scientific_name}" (Family: {family}, Native to: {wcvp_native}).

Return a JSON object with "insights" array. Each insight must include:
- claim_type: field name (e.g., "maximum_height", "habitat")
- claim_value: the data (use structured objects where appropriate)
- confidence: 0.0-1.0 (how certain are you?)
- sources: array of sources used (with url, title, type, credibility)

For sources, prefer authoritative databases:
- IUCN Red List (conservation)
- GBIF, POWO, WCVP (taxonomy, distribution)
- FAO, USDA (uses, cultivation)
- Published papers with DOIs

If you cannot find a reliable source, set confidence lower and note "model_inference" as methodology.

Fields to research:
{field_list}

Return ONLY valid JSON. Structure:
{{
  "insights": [
    {{
      "claim_type": "...",
      "claim_value": {{...}},
      "confidence": 0.85,
      "sources": [...]
    }}
  ]
}}
"""
```

### Backward Compatibility

Insights are stored in the `insights` table. A sync process copies current values to `species.*_ai` columns for frontend compatibility:

```sql
-- Sync insights to flat species columns
UPDATE species s
SET general_description_ai = (
    SELECT i.claim_value->>'text'
    FROM insights i
    WHERE i.taxon_id = s.taxon_id
    AND i.claim_type = 'general_description'
    AND i.is_current = TRUE
    LIMIT 1
)
WHERE EXISTS (
    SELECT 1 FROM insights WHERE taxon_id = s.taxon_id AND is_current = TRUE
);
```

---

## 4. Tracking Schema

### SQLite Database (research_tracking.db)

```sql
-- Track each research attempt
CREATE TABLE research_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  taxon_id TEXT NOT NULL,
  species_name TEXT NOT NULL,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  status TEXT DEFAULT 'in_progress',  -- in_progress, completed, failed
  fields_populated INTEGER,
  fields_total INTEGER DEFAULT 35,
  error_message TEXT,
  session_id TEXT  -- Group by CLI session
);

-- Track what was written to database
CREATE TABLE field_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  research_log_id INTEGER NOT NULL,
  field_name TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  confidence REAL,
  FOREIGN KEY (research_log_id) REFERENCES research_log(id)
);

-- Session summaries
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,  -- UUID or timestamp
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  species_attempted INTEGER DEFAULT 0,
  species_completed INTEGER DEFAULT 0,
  species_failed INTEGER DEFAULT 0,
  notes TEXT
);

-- Aggregation views
CREATE VIEW research_progress AS
SELECT
  COUNT(*) as total_attempts,
  COUNT(*) FILTER (WHERE status = 'completed') as completed,
  COUNT(*) FILTER (WHERE status = 'failed') as failed,
  AVG(fields_populated) as avg_fields_populated,
  DATE(started_at) as date
FROM research_log
GROUP BY DATE(started_at);
```

---

## 5. Database Versioning

Migration file already created: `treekipedia/database/07_research_versioning.sql`

Adds to species table:
- `research_version` (INTEGER, default 0)
- `research_date` (TIMESTAMP)
- `research_agent` (TEXT)
- `research_confidence` (REAL)
- `research_sources` (JSONB)
- `research_flags` (JSONB)
- `research_token_cost` (REAL)

Plus `research_history` table for audit trail.

---

## 6. Implementation

### Step 1: Run Database Migration

```bash
psql treekipedia < treekipedia/database/07_research_versioning.sql
```

### Step 2: Create Research Script

File: `scripts/research_species.py`

```python
#!/usr/bin/env python3
"""
Treekipedia Species Research Script
Run via Claude Code CLI to research species using subscription quota.

Usage:
  python scripts/research_species.py --taxon-id "AngQuRo1234-00"
  python scripts/research_species.py --batch 10
  python scripts/research_species.py --list-pending
"""

import argparse
import json
import sqlite3
import psycopg2
from datetime import datetime
from uuid import uuid4

# Database connections
PG_CONN = "dbname=treekipedia"
SQLITE_DB = "research_tracking.db"

def init_sqlite():
    """Initialize SQLite tracking database."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taxon_id TEXT NOT NULL,
            species_name TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'in_progress',
            fields_populated INTEGER,
            fields_total INTEGER DEFAULT 35,
            error_message TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            species_attempted INTEGER DEFAULT 0,
            species_completed INTEGER DEFAULT 0,
            species_failed INTEGER DEFAULT 0,
            notes TEXT
        );
    """)
    conn.commit()
    return conn

def get_species_to_research(limit=10):
    """Get species that haven't been researched yet."""
    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, species_scientific_name, family, wcvp_native
        FROM species
        WHERE research_version = 0 OR research_version IS NULL
        ORDER BY total_occurrences DESC NULLS LAST
        LIMIT %s
    """, (limit,))
    species = cur.fetchall()
    conn.close()
    return species

def get_species_by_id(taxon_id):
    """Get a specific species by taxon_id."""
    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, species_scientific_name, family, wcvp_native
        FROM species
        WHERE taxon_id = %s
    """, (taxon_id,))
    species = cur.fetchone()
    conn.close()
    return species

def update_species_research(taxon_id, research_data):
    """Write research results to PostgreSQL."""
    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()

    # Build UPDATE query for AI fields
    updates = []
    values = []

    field_mapping = {
        'popular_common_name': 'common_name',  # Map to existing column
        'general_description': 'general_description_ai',
        'habitat': 'habitat_ai',
        'elevation_ranges': 'elevation_ranges_ai',
        'ecological_function': 'ecological_function_ai',
        'native_adapted_habitats': 'native_adapted_habitats_ai',
        'conservation_status': 'conservation_status_ai',
        'compatible_soil_types': 'compatible_soil_types_ai',
        'growth_form': 'growth_form_ai',
        'leaf_type': 'leaf_type_ai',
        'deciduous_evergreen': 'deciduous_evergreen_ai',
        'flower_color': 'flower_color_ai',
        'fruit_type': 'fruit_type_ai',
        'bark_characteristics': 'bark_characteristics_ai',
        'maximum_height': 'maximum_height_ai',
        'maximum_diameter': 'maximum_diameter_ai',
        'lifespan': 'lifespan_ai',
        'maximum_tree_age': 'maximum_tree_age_ai',
        'stewardship_best_practices': 'stewardship_best_practices_ai',
        'planting_recipes': 'planting_recipes_ai',
        'pruning_maintenance': 'pruning_maintenance_ai',
        'disease_pest_management': 'disease_pest_management_ai',
        'fire_management': 'fire_management_ai',
        'cultural_significance': 'cultural_significance_ai',
        'agroforestry_use_cases': 'agroforestry_use_cases_ai',
    }

    for field, value in research_data.items():
        if value is not None and field in field_mapping:
            db_column = field_mapping[field]
            updates.append(f"{db_column} = %s")
            values.append(str(value) if not isinstance(value, str) else value)

    # Add versioning fields
    updates.extend([
        "research_version = COALESCE(research_version, 0) + 1",
        "research_date = %s",
        "research_agent = %s"
    ])
    values.extend([datetime.now(), 'claude-code-cli'])

    values.append(taxon_id)

    query = f"""
        UPDATE species
        SET {', '.join(updates)}
        WHERE taxon_id = %s
    """

    cur.execute(query, values)
    conn.commit()
    updated = cur.rowcount
    conn.close()

    return updated

def list_pending():
    """Show species pending research."""
    species = get_species_to_research(limit=20)
    print(f"\n{'='*60}")
    print(f"Top 20 Species Pending Research (by occurrence count)")
    print(f"{'='*60}\n")
    for s in species:
        print(f"  {s[0]}: {s[1]} ({s[2]})")
    print(f"\nTotal: {len(species)} shown")

def main():
    parser = argparse.ArgumentParser(description='Research species via Claude Code CLI')
    parser.add_argument('--taxon-id', help='Research specific species by taxon_id')
    parser.add_argument('--batch', type=int, help='Research N species from queue')
    parser.add_argument('--list-pending', action='store_true', help='List pending species')

    args = parser.parse_args()

    if args.list_pending:
        list_pending()
        return

    if args.taxon_id:
        species = get_species_by_id(args.taxon_id)
        if species:
            print(f"\nResearch target: {species[1]} ({species[0]})")
            print(f"Family: {species[2]}")
            print(f"Native to: {species[3]}")
            print("\n[Ready for Claude Code to research this species]")
        else:
            print(f"Species {args.taxon_id} not found")
        return

    if args.batch:
        species = get_species_to_research(limit=args.batch)
        print(f"\nBatch of {len(species)} species ready for research:")
        for s in species:
            print(f"  - {s[1]} ({s[0]})")
        return

    parser.print_help()

if __name__ == '__main__':
    main()
```

### Step 3: Test Single Species

```bash
# List what's pending
python scripts/research_species.py --list-pending

# Research one species (Claude Code will execute the research)
python scripts/research_species.py --taxon-id "AngQuRo1234-00"
```

---

## 7. Usage Workflow

### Manual Research (On-Demand)

1. User clicks Research button on species page
2. Frontend calls backend endpoint
3. Backend spawns CLI task or queues for next session
4. Claude Code researches species, writes to DB
5. Frontend polls for completion

### Batch Research (Quota Maximization)

```bash
# Start a research session
cd /path/to/silvi-open
claude

# In Claude Code CLI:
> Research the next 10 unresearched species. For each:
> 1. Get species from database using scripts/research_species.py --batch 10
> 2. Research each species using the research prompt
> 3. Update database with results
> 4. Log to research_tracking.db
```

### Weekly Schedule (Suggested)

| Day | Action | Expected Species |
|-----|--------|------------------|
| Mon | Morning batch | 50-100 |
| Tue | Morning batch | 50-100 |
| Wed | Morning batch | 50-100 |
| Thu | Morning batch | 50-100 |
| Fri | Morning batch + review | 50-100 |
| **Week** | | **250-500** |

Actual throughput depends on quota usage and will be learned empirically.

---

## 8. Quality Tracking

### After Each Session

```sql
-- Check today's progress
SELECT
  COUNT(*) as researched_today,
  AVG(fields_populated) as avg_fields
FROM research_log
WHERE DATE(started_at) = DATE('now');

-- Overall progress
SELECT
  COUNT(*) FILTER (WHERE research_version >= 1) as researched,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE research_version >= 1) / COUNT(*), 2) as pct
FROM species;
```

### Quality Checks

- **Field completion**: How many of 35 fields populated?
- **Null rate**: Which fields frequently return null?
- **Consistency**: Do similar species get similar results?

---

## 9. Files Created

| File | Purpose |
|------|---------|
| `07_research_versioning.sql` | Database migration for versioning |
| `scripts/research_species.py` | CLI research helper script |
| `research_tracking.db` | SQLite tracking database (created on first run) |

---

## 10. Next Steps

1. **Run migration**: `psql treekipedia < treekipedia/database/07_research_versioning.sql`
2. **Create research script**: `scripts/research_species.py`
3. **Initialize SQLite**: Run script once to create tracking DB
4. **Test on 1 species**: Manually research, verify database update
5. **Test on 5 species**: Small batch, check quality
6. **Iterate**: Adjust prompts based on results

---

## Appendix: Sample Research Output

```json
{
  "popular_common_name": "English Oak",
  "etymology": "Quercus from Latin for oak; robur meaning strength",
  "identification_features": "Deeply lobed leaves with 4-5 pairs; acorns on long stalks",

  "general_description": "Large deciduous tree reaching 20-40m with broad spreading crown. Iconic European forest species.",
  "habitat": "Temperate broadleaf forests, particularly on clay-rich soils",
  "elevation_ranges": "0-1000",
  "ecological_function": "Keystone species supporting 280+ insect species",
  "conservation_status": "Least Concern (IUCN)",

  "growth_form": "Large deciduous tree",
  "maximum_height": 40,
  "maximum_diameter": 4,
  "deciduous_evergreen": "deciduous",
  "leaf_type": "Simple, deeply lobed",

  "stewardship_best_practices": "Plant in full sun to partial shade. Tolerates periodic flooding.",
  "propagation_methods": "Seed (acorns) - plant fresh in autumn"
}
```

---

*CLI-native architecture for Claude Code Max 5x subscription*
