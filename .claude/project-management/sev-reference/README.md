# Sev's Reference Documentation

**Source**: `origin/latest` branch (fetched January 5, 2026)
**Purpose**: Preserve Sev's planning docs for reference while we maintain our own structure

---

## Files in This Directory

| File | Original Location | Description |
|------|-------------------|-------------|
| [SEV_GO.md](SEV_GO.md) | `treekipedia/GO.md` | Sev's onboarding procedure |
| [SEV_TODO.md](SEV_TODO.md) | `treekipedia/TODO.md` | Sev's task roadmap |
| [SEV_ACTIVE.md](SEV_ACTIVE.md) | `treekipedia/ACTIVE.md` | Sev's system status |
| [SEV_LEAF.md](SEV_LEAF.md) | `treekipedia/docs/todo/LEAF.md` | LEAF scoring algorithm spec |
| [SEV_GROK_RESEARCHER.md](SEV_GROK_RESEARCHER.md) | `grok_local_ai_researcher_plan.md` | Grok-based research architecture |
| [SEV_GROK_PROMPTS.js](SEV_GROK_PROMPTS.js) | `treekipedia/scripts/research/test-grok-agentic.js` | Research prompts (25 fields) |

---

## Key Features from Sev's Work

### 1. LEAF™ Scoring (Production Ready)
**Endpoint**: `GET/POST /api/geospatial/leaf/score`

Answers: "What trees should I plant here?"

```
Pool = WCVP natives UNION occurrence species MINUS introduced
Score = percentile rank based on (occurrence × tile_count × native_boost)
```

### 2. Research Prompts (25 Fields)

Sev's 3-group strategy:
- **Ecological** (9 fields): habitat, elevation, conservation status, etc.
- **Morphological** (10 fields): growth form, leaf type, height, etc.
- **Stewardship** (6 fields): planting, pruning, disease management, etc.

### 3. V10 Schema (130 fields)
- Climate data (Köppen-Geiger, temperature, precipitation)
- WCVP native/introduced status (97.5% coverage)
- GloBI ecological interactions
- SBTN land cover

---

## How We're Using Sev's Work

1. **Merge LEAF scoring** - Critical for bioregional campaigns
2. **Adopt research prompts** - Same 25-field schema for Claude agents
3. **Use V10 frontend components** - Climate, GloBI display
4. **Build on geohash import script** - For our 96.5M occurrences

---

## Differences in Approach

| Aspect | Sev | Us |
|--------|-----|-----|
| **Research Model** | Grok 4.1 + web_search | Claude Haiku/Sonnet/Opus |
| **Orchestration** | Backend API calls | Claude Code native + local Python |
| **Data Version** | V10 (Nov 2025) | V11 (Dec 2025) |
| **Occurrences** | 89M | 96.5M (newer) |

---

## Reference When Needed

These docs are preserved for:
- Understanding Sev's implementation decisions
- Referencing LEAF algorithm details
- Adapting Grok prompts for Claude
- Maintaining compatibility with `latest` branch

**Note**: Our active planning docs are in the parent directory (`../*.md`).
