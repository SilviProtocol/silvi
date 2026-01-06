# TODO.md - Treekipedia Implementation Plan

Active tasks and planned work. See CHANGELOG.md for completed features.

**Sev's Reference Docs**: See [sev-reference/](sev-reference/) for `latest` branch planning docs (LEAF scoring, Grok research, V10 schema).

---

## [IMMEDIATE] - Merge & Data Import

**Status**: Ready to merge `origin/latest` and import V11 data

### Merge Latest Branch
- [ ] Commit/stash local changes
- [ ] Merge `origin/latest` into `djimotreekipedia`
- [ ] Resolve conflicts (keep both features)
- [ ] Test LEAF scoring endpoint locally

### Import V11 Data
- [ ] Import V11 species knowledge (67,750 species, 133 columns)
- [ ] Import 96.5M occurrences from new parquet
- [ ] Rebuild geohash tiles
- [ ] Verify LEAF scoring works with new data

---

## [IN PROGRESS] - AlphaEarth Scale-Up

**Status**: 100-species pilot complete, planning scale to full coverage

### Phase 5: Scale to 1,000+ Species
- [ ] Analyze coverage patterns from pilot (which species/regions failed)
- [ ] Create geographic/temporal coverage model
- [ ] Pre-filter occurrences with <20% success probability
- [ ] Run batch extraction for next 1,000 species
- [ ] Monitor GEE quota usage during extraction

### Evaluation & Quality
- [ ] Create validation script with held-out occurrences
- [ ] Calculate Recall@K (K=5, 10, 20) metrics
- [ ] Generate performance report per species
- [ ] Document limitations transparently in UI

### Frontend Enhancements
- [ ] Add geographic filtering (show only species native to clicked continent)
- [ ] Implement real SSE progress (currently manual 5%→30%→60%→100%)
- [ ] Add confidence threshold filter (only show >50% predictions)
- [ ] Add "Why?" explanations showing top contributing features
- [ ] Allow user to select year (2017-2024) for temporal queries

---

## [HIGH PRIORITY] - Fix Critical Bugs

**Status**: Species search endpoint broken in production

### Species Search Bug
- [ ] Fix `/species?search=X` returning 500 error
  - File: [backend/controllers/species.js](treekipedia/backend/controllers/species.js) ~line 25
  - Change: `WHERE species ILIKE` → `WHERE species_scientific_name ILIKE`
  - Test: `curl http://localhost:5001/species?search=oak`

### Validate All Endpoints
- [ ] Test each endpoint in [API.md](treekipedia/API.md)
- [ ] Document any other schema mismatches
- [ ] Create automated endpoint test suite

---

## [HIGH PRIORITY] - Native Status Analysis Frontend

**Status**: Backend endpoints exist, frontend integration pending

### Frontend Integration
- [ ] Update frontend types.ts with native status response structure
- [ ] Enhance ResultsList component to display native status breakdown
- [ ] Add visual indicators (charts/percentages) for native vs introduced species
- [ ] Test cross-analysis with various countries and polygons

### Backend Enhancements
- [ ] Update `/api/geospatial/analyze-plot` with native status analysis
- [ ] Add country detection and native percentage calculation
- [ ] Create helper functions for country name normalization

---

## [MEDIUM PRIORITY] - Database Optimization

**Status**: Working but could be faster

### Index Optimization
- [ ] Add indexes on countries_native and countries_introduced columns
- [ ] Optimize cross-analysis query performance
- [ ] Monitor query performance with larger polygon analyses
- [ ] Add caching for frequently accessed country polygon intersections

### Cleanup
- [ ] Archive backup tables (species_v7_backup, species_v8) to separate schema
- [ ] Clean up temporary scripts from recent imports
- [ ] Remove duplicate/test data from development iterations

---

## [MEDIUM PRIORITY] - GraphFlow Production Deployment

**Status**: Admin UI complete, needs production setup

### Python Dependencies
- [ ] Install full Python dependencies on production server
- [ ] Configure systemd service for Python microservice
- [ ] Test all endpoints on production

### Security
- [ ] Enable authentication for /api/admin/* routes (wallet-based?)
- [ ] Implement activity logging
- [ ] Add error tracking and notifications

### Features
- [ ] Test species sync with real data (67k species)
- [ ] Test ontology generation with CSV files
- [ ] Improve SPARQL editor (syntax highlighting, autocomplete)

---

## [MEDIUM PRIORITY] - Knowledge Graph Integration

**Status**: Exploration phase

### Apache Jena/Fuseki Evaluation
- [ ] Assess current Blazegraph instance vs Fuseki capabilities
- [ ] Research SPARQL query patterns for species relationships
- [ ] Evaluate RDF data modeling for taxonomic hierarchies
- [ ] Test semantic query capabilities with sample data

### Graph Database Planning
- [ ] Compare PostGIS spatial + semantic graphs vs pure relational
- [ ] Identify use cases where graph queries enhance UX
- [ ] Plan species-ecosystem-location-taxonomy relationships in RDF
- [ ] Consider hybrid approach: PostGIS for spatial, graph for semantic

---

## [STRATEGIC] - Claude Code Native Research Framework

**Status**: Architecture documented (Jan 2025), ready for implementation

**Reference Documents**:
- [CLAUDE_CODE_RESEARCHER_ARCHITECTURE.md](../../CLAUDE_CODE_RESEARCHER_ARCHITECTURE.md) - **Primary plan (Claude-native)**
- [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](../../TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) - Insight-based knowledge model
- [sev-reference/SEV_GROK_PROMPTS.js](sev-reference/SEV_GROK_PROMPTS.js) - **Sev's 25-field research prompts (adopt these)**
- [sev-reference/SEV_GROK_RESEARCHER.md](sev-reference/SEV_GROK_RESEARCHER.md) - Sev's Grok architecture

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (Research Button)                                     │
│  └── Click "Research Species" → POST /api/research/queue        │
│                                                                 │
│  LOCAL PYTHON SERVICE (port 5003)                               │
│  └── Receives queue request → spawns Claude Code agent          │
│                                                                 │
│  CLAUDE CODE AGENTS (Haiku/Sonnet/Opus)                        │
│  ├── Haiku: Web search + extraction (3 parallel groups)        │
│  │   ├── Ecological (9 fields)                                 │
│  │   ├── Morphological (10 fields)                             │
│  │   └── Stewardship (6 fields)                                │
│  ├── Sonnet: Validate + synthesize results                     │
│  └── Opus: Quality control (high-value species only)           │
│                                                                 │
│  OUTPUT → SQLite queue → Sync to PostgreSQL                    │
└─────────────────────────────────────────────────────────────────┘
```

**Cost estimate**: $670-$3,000 for all 67k species

### Phase 1 - Local Research Service
- [ ] Create Python service (`research_orchestrator.py`) on port 5003
- [ ] Implement `/queue` endpoint for frontend research button
- [ ] Create SQLite research queue (`research_queue.db`)
- [ ] Build Claude Code agent spawning logic
- [ ] Adapt Sev's 25-field prompts for Claude (from `SEV_GROK_PROMPTS.js`)

### Phase 2 - Claude Agent Implementation
- [ ] Implement Haiku extraction agents (3 parallel: eco, morph, steward)
- [ ] Implement Sonnet synthesis agent
- [ ] Add web search integration (using Claude's web tools)
- [ ] Add source citation tracking
- [ ] Create JSON schema validation

### Phase 3 - Frontend Integration
- [ ] Update Research Button to call local service (port 5003)
- [ ] Add research progress UI (polling status)
- [ ] Show "Research in Progress" indicator
- [ ] Display results when complete
- [ ] Admin page: batch research controls

### Phase 4 - Scale & Quality
- [ ] Run batch research (1,000/week target)
- [ ] Monitor API quota usage and optimize
- [ ] Implement confidence scoring based on source quality
- [ ] Create quality metrics dashboard
- [ ] Sync validated results to production DB

### Infrastructure
- **Local**: Claude Code + SQLite queue + PostgreSQL dev
- **Cloud**: Digital Ocean (or GCP) for serving only
- **Goal**: Minimize cloud costs, maximize local processing

---

## [LOW PRIORITY] - Data Enrichment

**Status**: Future enhancements

### External Data Integration
- [ ] Integrate climate data for species-environment correlations
- [ ] Add elevation data for elevation range analysis
- [ ] Consider IUCN Red List integration for conservation status
- [ ] Explore trait data for functional diversity analysis

### Advanced Analysis
- [ ] Multi-country polygon analysis (species crossing borders)
- [ ] Temporal analysis capabilities (species changes over time)
- [ ] Biodiversity metrics (Shannon diversity, Simpson index)
- [ ] Species co-occurrence and community composition

### UX Improvements
- [ ] Analysis result export (CSV, JSON, GeoJSON)
- [ ] Analysis history and saved polygon management
- [ ] Comparison tools for multiple polygon analyses
- [ ] Interactive data visualizations beyond species lists

---

## [LOW PRIORITY] - Technical Debt

**Status**: Ongoing maintenance

### Code Quality
- [ ] Add comprehensive error handling for edge cases
- [ ] Write tests for new functionality
- [ ] Document API changes and new endpoints

### Monitoring
- [ ] Set up query performance monitoring
- [ ] Add logging for analysis usage patterns
- [ ] Monitor memory usage during large analyses
- [ ] Implement rate limiting if needed

---

## Backlog (Unprioritized)

- [ ] Mobile app or PWA
- [ ] Batch AI research for unresearched species
- [ ] Increase image coverage from 20% to 50%
- [ ] Pre-compute predictions for popular locations
- [ ] Show prediction confidence as heatmap overlay
- [ ] Local LLM support (Gemini, GPT-5, Grok)
- [ ] E2E tests with Playwright
- [ ] Unit tests for Python endpoints

---

## Documentation References

- **GO.md** - Onboarding procedure (this folder)
- **ACTIVE.md** - Current system status (this folder)
- **CHANGELOG.md** - Completed features (this folder)
- **[CLAUDE.md](../CLAUDE.md)** - Development guide (parent folder)
