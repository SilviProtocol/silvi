# Branch Comparison: `latest` vs `djimotreekipedia`

**Date**: January 5, 2026
**Purpose**: Understand what Sev has done in `latest` branch and how it relates to our work

---

## Summary

Sev's `latest` branch has significant new features that **complement** our work. There's no major conflict - the work focuses on different areas that can be merged together.

| Area | `latest` (Sev) | `djimotreekipedia` (Us) |
|------|----------------|------------------------|
| **LEAF Scoring** | ✅ MVP implemented | Not started |
| **Grok Agentic Research** | ✅ Testing done | Different approach (Claude-native) |
| **V10/V11 Data** | ✅ V10 imported | Have V11 CSV ready |
| **Geohash Import Script** | ✅ New compressed format | Have new 96.5M parquet |
| **Frontend Updates** | ✅ Climate/GloBI display | Not updated |
| **AlphaEarth** | Not present | ✅ 100-species pilot |
| **GraphFlow Admin** | Not mentioned | ✅ Full admin UI |
| **Project Management** | Different structure | Different structure |

---

## Key New Features in `latest`

### 1. LEAF™ Scoring Engine (HIGH VALUE)

**What it does**: Location-based species recommendations - "What trees should I plant here?"

**Status**: MVP implemented, tested on Appalachian-Blue Ridge ecoregion

**Endpoint**: `GET/POST /api/geospatial/leaf/score`

**Algorithm**:
```
Pool = WCVP natives for region UNION occurrence species
     MINUS species in wcvp_introduced

Affinity = (occurrence_count × tile_count) × native_multiplier
  - Native: ×2.0 boost
  - Unknown: ×1.0 neutral
  - Introduced: EXCLUDED

LEAF Score = percentile rank (0-100)
```

**Why it matters**: Critical for $100K bioregional campaigns

**Our relevance**: Complements our AlphaEarth habitat prediction - LEAF answers "what to plant" while AlphaEarth answers "where species can survive"

### 2. Grok Agentic Research Testing

**What they tested**:
- xAI Grok 4.1 Fast (reasoning vs non-reasoning)
- Single comprehensive call vs 3-group parallel strategy
- 25 research fields extraction

**Test species**: Ginkgo biloba, Quercus robur, Delonix regia (flame tree)

**Results location**: `treekipedia/scripts/research/results/*.json`

**Our approach difference**:
- They're testing Grok with web_search tool
- We proposed Claude Code native with Haiku/Sonnet/Opus tiering
- Both approaches are valid - could be combined

### 3. V10 Schema Updates

**New fields added (130 total)**:
- Climate data (Köppen-Geiger, temperature ranges, precipitation)
- SBTN land cover
- WCVP native/introduced status (97.5% coverage!)
- GloBI ecological interactions

**Import scripts created**:
- `import_v10_species.js`
- `import_wcvp_native_status.js`
- `import_geohash_parquet.py` (new compressed format)

### 4. Geohash Import Script

New script for compressed geohash occurrence data:
- Transforms array format `[{"taxon_id": "ABC", "count": 5}]` to object `{"ABC": 5}`
- Handles WKT geometry
- Preserves ecoregion assignments via cache

**Our relevance**: We have new 96.5M occurrence parquet - can use their script

### 5. Frontend Updates

- Climate profile component
- GloBI ecological interactions display
- SBTN land cover on species pages
- Updated navbar/footer

---

## What We Have That They Don't

### 1. AlphaEarth Habitat Prediction
- 100-species pilot complete
- GEE/BigQuery integration
- Click-to-predict on map
- 64-dimensional embeddings

### 2. GraphFlow Admin UI
- 7 admin pages (dashboard, sync, upload, sheets, SPARQL, monitor, versions)
- Python microservice for ontology generation
- Express proxy routes

### 3. V11 Knowledge Data
- `Treekipedia_V11_Native_introduced_December_09d.csv` (67,750 species, 133 columns)
- Includes `wcvp_native`, `wcvp_introduced` already

### 4. 96.5M Occurrence Parquet
- Latest occurrence data
- Clean taxon_id mappings

### 5. Claude Code Research Architecture
- Detailed plan for Haiku/Sonnet/Opus tiering
- Cost-optimized approach
- Different from their Grok approach

---

## Documentation Structure Comparison

### `latest` structure (Sev)
```
treekipedia/
├── GO.md          # Onboarding
├── ACTIVE.md      # System status
├── TODO.md        # Tasks
├── CHANGELOG.md   # History
├── README.md      # Architecture
├── API.md         # API docs
├── docs/
│   ├── todo/      # Planning docs (LEAF.md, etc.)
│   ├── completed/ # Finished plans
│   └── archive/   # Old docs
```

### Our structure
```
.claude/
├── CLAUDE.md                    # Development guide
└── project-management/
    ├── GO.md                    # Onboarding
    ├── ACTIVE.md                # System status
    ├── TODO.md                  # Tasks
    └── CHANGELOG.md             # History
```

**Difference**: Sev keeps docs in `treekipedia/` root, we use `.claude/project-management/`

---

## Merge Strategy Recommendation

### Phase 1: Pull Their Code
```bash
git fetch origin latest
git checkout djimotreekipedia
git merge origin/latest --no-commit
```

### Phase 2: Resolve Conflicts
Expected conflicts:
- `.env` files (take ours, add any new vars from theirs)
- `TODO.md` locations (decide on one structure)
- Frontend components (merge both changes)

### Phase 3: Keep Both Features
- ✅ Keep LEAF scoring (theirs)
- ✅ Keep AlphaEarth prediction (ours)
- ✅ Keep GraphFlow admin UI (ours)
- ✅ Use their geohash import script with our new parquet
- ✅ Merge documentation structures

### Phase 4: Consolidate Research Approach
Options:
1. **Use both**: Grok for some species, Claude for others
2. **Choose one**: Standardize on Claude Code native
3. **A/B test**: Compare results from both approaches

---

## Immediate Actions

### High Priority
1. [ ] Merge `origin/latest` into `djimotreekipedia`
2. [ ] Import V11 data (has newer WCVP native/introduced)
3. [ ] Run their geohash import with our 96.5M parquet
4. [ ] Test LEAF scoring endpoint locally

### Medium Priority
1. [ ] Consolidate documentation structure
2. [ ] Compare Grok vs Claude research outputs
3. [ ] Update frontend with their climate/GloBI components

### Lower Priority
1. [ ] Decide on unified research approach
2. [ ] Plan combined roadmap

---

## Key Files from `latest` to Review

| File | Purpose |
|------|---------|
| `treekipedia/scripts/import_geohash_parquet.py` | New occurrence import |
| `treekipedia/scripts/research/test-grok-agentic.js` | Grok research testing |
| `treekipedia/docs/todo/LEAF.md` | LEAF scoring specification |
| `treekipedia/backend/controllers/geospatial.js` | LEAF endpoint |
| `grok_local_ai_researcher_plan.md` | Their AI research plan |

---

## Conclusion

The two branches are **complementary**, not conflicting. Sev focused on:
- LEAF scoring for species recommendations
- Grok-based agentic research
- V10 frontend updates

We focused on:
- AlphaEarth habitat prediction
- GraphFlow admin UI
- Claude Code research architecture
- New data preparation (V11, 96.5M occurrences)

**Recommended action**: Merge `latest` to get LEAF scoring and their improvements, then continue with our Claude Code research approach using the combined codebase.
