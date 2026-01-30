# TODO.md - Treekipedia Implementation Plan

Active tasks and planned work. See CHANGELOG.md for completed features.

**Planning docs**: Detailed plans for each section are in `docs/todo/`. When complete, move to `docs/completed/`.

---

## [IN PROGRESS] - LEAF™ Scoring Engine

**Status**: Algorithm tested, implementation starting
**Planning Doc**: [docs/todo/LEAF.md](docs/todo/LEAF.md)
**Reference**: [docs/RECOMMENDATION_SERVICE.md](docs/RECOMMENDATION_SERVICE.md)

**LEAF™** = **Location-based Ecological Aptness Forecast**

### MVP: Union Pool + Native Boost + Introduced Exclusion ✅ IMPLEMENTED
**Goal**: Point/Polygon/Ecoregion → Native-aware species recommendations

**Endpoint**: `GET/POST /api/geospatial/leaf/score`
- `?eco_id=331` - Direct ecoregion ID lookup
- `?eco_name=Appalachian-Blue%20Ridge%20forests` - Ecoregion name lookup
- `?lat=35.5&lng=-82.5` - Point lookup
- POST with `{ geometry: {...} }` - Polygon (multi-ecoregion weighted)

**Integration Guide**: [docs/LEAF_INTEGRATION_GUIDE.md](docs/LEAF_INTEGRATION_GUIDE.md)

**Tested on Appalachian-Blue Ridge** (updated Jan 2026 with fresh data):
- 3,332 species in pool (natives + occurrences)
- 497 introduced species excluded (Tree of Heaven, Mimosa, etc.)
- Top results: Red Maple, Tuliptree, White Oak, Black Gum, Black Cherry (iconic natives)

**Algorithm:**
```
Pool = WCVP natives for region UNION occurrence species
     MINUS species in wcvp_introduced

Affinity = (occurrence_count × tile_count) × native_multiplier
  - Native: ×2.0 boost
  - Unknown: ×1.0 neutral
  - Introduced: EXCLUDED

LEAF Score = percentile rank (0-100)
```

**Remaining Tasks:**
- [ ] Add index on `eco_id` column for query performance
- [ ] Test on all 12 target bioregional campaign ecoregions
- [ ] CSV export for campaign distribution

### v1.1: Biome Matching (after MVP)
- [ ] Add biome match modifier (×1.2 bonus / ×0.8 penalty)
- [ ] Include biome_match flag in API response

### v1.2: Commercial Penalty (after v1.1)
- [ ] Add commercial species penalty (×0.7)
- [ ] Include is_commercial flag in API response

### v1.3: Family Diversity Quotas (after v1.2)
- [ ] Post-filter: Cap 15-20 species per family in BEST tier
- [ ] Report family distribution in API response

---

## [COMPLETED] - Geohash Occurrence Data Import ✅

**Status**: COMPLETED January 2026
**Planning Doc**: [docs/todo/geohash-occurrence-import.md](docs/todo/geohash-occurrence-import.md)

Full refresh of geohash occurrence data from BigQuery parquet export.

**Results**:
- 6,458,119 tiles (was 5,786,835) - +11.6% increase
- 96,512,768 occurrences (was 94,422,564) - +2.2% increase
- 97.2% ecoregion coverage (6,278,540 tiles)
- Zero import errors

**Scripts Created**:
- `scripts/import_geohash_parquet.py` - Parquet import with array→object transformation
- `scripts/fix_geohash_geometries.py` - Geometry fix (source WKT was degenerate)
- `scripts/assign_ecoregions_new_tiles.py` - Ecoregion assignment for new tiles

### Phase 2: Incremental Import Infrastructure (Future)
- [ ] Create `merge_species_data()` PostgreSQL function
- [ ] Add `--incremental` mode to import script
- [ ] Test merge logic with sample data
- [ ] Document incremental import workflow

---

## [COMPLETE] - Research & Insights Architecture ✅

**Status**: Backend + frontend aligned after djimo merge (Jan 27, 2026)
**Added**: January 2026

### Backend ✅
- [x] Insights table and triggers created (`database/06_insights_architecture.sql`)
- [x] Research creates atomic insights, then syncs to `_ai` columns
- [x] `GET /species/:taxon_id/insights` returns `has_insights`, `metadata`, flat insights array
- [x] Confidence scoring with breakdown (field_coverage, critical_fields, specificity, sources)
- [x] Research versioning (`research_version`, `research_date`, `research_agent`, `research_confidence`)
- [x] 9 new _ai columns: etymology, synonyms, identification_features, climate_tolerance, tolerances, associated_species, timber_value, non_timber_products, nutritional_caloric_value

### Frontend ✅
- [x] `useSpeciesData.ts` simplified to 2 queries (species + insights), removed redundant /research query
- [x] Synthetic Knowledge panel (ResearchMetadataPanel) renders with confidence, version, model
- [x] DataField shows per-field confidence bars and atomic insights
- [x] Data priority: human → ai → legacy via `getFieldValue()`
- [x] Dead code removed (InsightField.tsx, InsightItem.tsx, useResearchProcess.ts)

### Remaining
- [ ] Queue research path should also call `createInsightsFromResearch()` when processing completes
- [ ] Restyle ResearchMetadataPanel (violet → existing design system, or keep as differentiation)

### Dual Research Integration (NOWPayments + Grok)
**Planning Doc**: [docs/todo/dual-research-integration.md](docs/todo/dual-research-integration.md)

Two research paths: instant ($1 crypto via NOWPayments) and free queue.

- [ ] Sign up NOWPayments with dev@silvi.earth, get API key + IPN secret
- [ ] Create `research_payments` table
- [ ] Build `backend/controllers/payments.js` (invoice creation + webhook)
- [ ] Build `backend/routes/payments.js` + register in server.js
- [ ] Webhook: verify HMAC-SHA512, trigger Grok research on payment confirmation
- [ ] Frontend: dual-button UI ("Research Instantly $1" / "Add to Queue (Free)")
- [ ] Frontend: show "Re-research" with last research date for already-researched species
- [ ] Install `@nowpaymentsio/nowpayments-api-js`
- [ ] Test with NOWPayments sandbox
- [ ] Future: admin role bypasses payment for instant research

### Future: Insights Vector/Graph
- [ ] Embed insights in vector database for semantic search
- [ ] Transform insights into graph database triples
- [ ] Build insight relationships across species

---

## [IN PROGRESS] - Frontend v10 Field Implementation

**Status**: Backend v10 migration complete, some frontend updates done
**Planning Doc**: [docs/todo/frontend-v10-implementation.md](docs/todo/frontend-v10-implementation.md)

### Species Detail Page Updates
- [ ] Implement ClimateProfile component display (Köppen-Geiger, temperature, precipitation)
- [ ] Implement EcologicalInteractions component (GloBI data visualization)
- [x] ~~Add SBTN land cover display~~ → Replaced with derived Habitat Biomes (Jan 2026)
- [x] Update TypeScript types in `lib/types.ts` for derived_biomes field
- [x] Update TypeScript types for research versioning fields (Jan 2026)
- [ ] Test all new field displays across species with varying data coverage

**Habitat Biomes Feature** (Jan 2026):
- Replaced unreliable `sbtn_landcover` with `derived_biomes` from occurrence data
- API returns top 5 biomes with ≥10 occurrences per species
- Frontend displays in SpeciesInfobox with occurrence counts on hover

### Ecoregion Frontend Integration
- [ ] Display ecoregion data in CrossAnalysisSummary
- [ ] Add ecoregion-based analysis option alongside country-based
- [ ] Create UI toggle for country vs ecoregion analysis mode
- [ ] Show ecoregion metadata (name, biome, realm) in results
- [ ] Optional: Add ecoregion boundary visualization on map

---

## [HIGH PRIORITY] - Documentation & API

**Status**: Core docs need alignment with new system

### API Documentation
- [ ] Document new `/api/geospatial/analyze-plot` cross-analysis response format in API.md
- [ ] Document all 7 ecoregion endpoints in API.md
- [ ] Add examples of cross-analysis responses to PUBLIC_API_GUIDE.md
- [ ] Complete PUBLIC_API_GUIDE.md (currently nearly empty)
- [ ] Add OpenAPI/Swagger documentation

### Code Quality
- [ ] Write tests for native status analysis functionality
- [ ] Write tests for ecoregion endpoints
- [ ] Add comprehensive error handling for cross-analysis edge cases

---

## [MEDIUM PRIORITY] - Database & Performance

**Status**: Functional, optimization opportunities exist

### Codebase Migration: taxon_full
- [ ] Migrate frontend from `species_scientific_name` to `taxon_full`
- [ ] Migrate backend API responses to use `taxon_full`
- [ ] Update LEAF endpoint to return `taxon_full` (currently uses `scientific_name`)
- [ ] Deprecate `species_scientific_name`, `taxon_id_new` (redundant fields)

### Database Optimization
- [ ] Add indexes on `wcvp_native` and `wcvp_introduced` columns (replaces countries_native)
- [ ] Optimize cross-analysis query performance
- [ ] Complete remaining 3% of ecoregion tile assignments (171k tiles)
- [ ] Monitor query performance with larger polygon analyses

### Data Quality: taxon_id Collisions
- [ ] Fix 27 duplicate taxon_ids affecting 54 species rows
  - Same taxon_id assigned to different species (e.g., `AngMaApPtTs00060-00` = both *Pittosporum ellipticum* and *Pittosporum bicolor*)
  - Collisions occur within same genus due to sequence number overlap
  - Blocks adding UNIQUE constraint on taxon_id and FK from insights table
  - Fix: Regenerate unique taxon_ids for affected rows or add disambiguating suffix

### Geospatial Data Enhancement
- [ ] Add Natural Earth Admin-1 boundaries (states/provinces shapefile)
  - Enables precise state-ecoregion intersection queries
  - Required for dynamic WCVP region matching instead of static lists
  - Source: Natural Earth 10m Admin-1 States/Provinces
- [ ] Complete WCVP region mappings for all countries with sub-national regions:
  - [ ] Argentina (Northeast, Northwest, South)
  - [ ] Australia (7 states/territories)
  - [ ] Chile (Central, North, South)
  - [ ] India (Assam, East Himalaya, West Himalaya, others)
  - [ ] New Zealand (North, South)
  - [ ] Russia (20+ regions)
  - [ ] South Africa (4 provinces)
- [ ] Verify WCVP region mappings against actual ecoregion intersections

### Backend Enhancements
- [ ] Create helper functions for country name mapping/normalization
- [ ] Add caching for frequent country polygon intersections
- [ ] Implement query result caching for repeated analysis requests
- [ ] Add request rate limiting for analysis endpoints

### Cleanup Tasks
- [ ] Archive `/scripts/research/` test files (48 files, 4.1MB)
- [ ] Remove unused test files from recent migrations
- [ ] Clean up temporary scripts

---

## [IN PROGRESS] - Ecoregion Reforestation Guides

**Status**: Phases 2-3 complete — backend API + frontend pages live. Phase 1 species research ongoing.
**Added**: January 2026
**Planning Doc**: [docs/todo/ecoregion-reforestation-guides.md](docs/todo/ecoregion-reforestation-guides.md)

Auto-generated reforestation guides per ecoregion using LEAF scoring + AI-researched species data. Frontend pages at `/guide/[eco_id]`. Also feeds into ReFi Reforestation Playbook for Regen Coordination.

**Pilot Ecoregion**: Tyrrhenian-Adriatic sclerophyllous and mixed forests (eco_id 806, Sicily)

**Live Routes**: `/guide` (search), `/guide/806` (example guide)

### Phase 1: Research Pilot Species (2/25 complete)
- [x] Add 25 pilot species to research queue (queue IDs 1-24)
- [x] Research Myrtus communis (67 insights, 0.84 confidence)
- [x] Research Quercus ilex (73 insights, 0.87 confidence)
- [ ] Research remaining 23 species (via queue workflow or direct Grok API)
- [ ] Verify insights quality and coverage across all 25

### Phase 2: Backend API ✅ COMPLETE
- [x] `GET /api/guides/ecoregion/:eco_id` — LEAF-ranked species + synthesized content
- [x] `POST /api/guides/ecoregion/:eco_id/synthesize` — Grok synthesis trigger
- [x] `GET /api/geospatial/ecoregions/search?q=` — Autocomplete search
- [x] `ecoregion_guides` table + synthesis service

### Phase 3: Frontend Guide Pages ✅ COMPLETE
- [x] `/guide` search page with autocomplete
- [x] `/guide/[eco_id]` accordion detail page
- [ ] Add "Guides" to navbar (deferred)
- [x] Species cards, tier badges, methodology section

### Phase 4: Polish & Expand
- [ ] Ecoregion map visualization
- [ ] Planting strategy groupings (canopy, understory, pioneer)
- [ ] Expand to 12 bioregional campaign ecoregions

---

## [FUTURE] - Advanced Features

### Unified Zone Schema
**Status**: Planning
**Planning Doc**: [docs/todo/unified-zone-schema.md](docs/todo/unified-zone-schema.md)

A unified schema for all environmental/geographic zones (biomes, ecoregions, land types, climate zones) with pre-computed connectivity. Solves the "continuous boundary problem" by clustering fragmented but logically connected regions.

- [ ] Create treekipedia_zones master table
- [ ] Create zone_connectivity table (pre-computed adjacency)
- [ ] Create zone_clusters table (cluster summaries)
- [ ] Migrate 847 WWF ecoregions to unified schema
- [ ] Implement cluster assignment algorithm
- [ ] Update geospatial API to use unified schema
- [ ] Add cluster-aware LEAF scoring option
- [ ] Import additional datasets (ESA CCI Land Cover, Köppen-Geiger climate zones)

### AI Research Enhancement
- [x] ~~Decide on production integration strategy~~ → Using Grok 4.1 Fast with web search (Jan 2026)
- [x] ~~Implement confidence scoring~~ → Implemented in grokResearch.js (Jan 2026)
- [x] ~~Implement improved multi-group research strategy~~ → Atomic v2: 2 parallel calls (Identity+Ecological, Morphological+Stewardship), 35 fields, 50-80+ insights (Jan 2026)
- [ ] Add Claude 3.5 Haiku as fallback/alternative research agent
- [x] ~~Implement insights table population (store atomic claims with per-field confidence)~~ → `createAtomicInsights()` with per-claim confidence (Jan 2026)
- [x] ~~Add `sync_insights_to_species()` function usage for multi-source aggregation~~ → Already in use since Jan 2026

### Blazegraph Knowledge Graph
- [ ] Assess current Blazegraph instance vs Fuseki capabilities
- [ ] Research SPARQL query patterns for species relationships
- [ ] Evaluate RDF data modeling for taxonomic hierarchies
- [ ] Plan data modeling: species-ecosystem-location-taxonomy in RDF

### Advanced Analysis Features
- [ ] Multi-country polygon analysis (species crossing borders)
- [ ] Temporal analysis capabilities (species changes over time)
- [ ] Biodiversity metrics (Shannon diversity, Simpson index)
- [ ] Species co-occurrence analysis
- [ ] Elevation-based analysis using terrain data
- [ ] Climate zone cross-referencing

### Data Enrichment
- [ ] Integrate climate data for species-environment correlations
- [ ] Add elevation data for elevation range analysis
- [ ] Consider IUCN Red List integration for conservation status
- [ ] Explore trait data integration for functional diversity

### User Experience
- [ ] Export as GeoJSON (species locations with metadata)
- [ ] Export as JSON (full analysis results)
- [ ] Analysis history and saved polygon management
- [ ] Comparison tools for multiple polygon analyses
- [ ] Interactive D3.js visualizations
- [ ] Share analysis via unique URL

---

## [BACKLOG] - Long-term Vision

### Community Features
- [ ] User accounts and saved analyses
- [ ] Public sharing of analysis results
- [ ] Community-contributed species observations
- [ ] Collaborative research notes

### Advanced Visualizations
- [ ] 3D terrain visualization with species distribution
- [ ] Time-series animation of species spread
- [ ] Interactive phylogenetic trees
- [ ] Heat maps of biodiversity hotspots

### External Integrations
- [ ] GBIF data sync
- [ ] iNaturalist observations integration
- [ ] eBird data for bird species
- [ ] Forest inventory data from national databases

### Infrastructure & Security
- [ ] Migrate from root user to dedicated non-root user (create user, move project, reconfigure code-server/PM2/permissions)

### Open Data & Governance
- [ ] Automated monthly exports to IPFS
- [ ] Database schema documentation to EAS
- [ ] RDF/Turtle exports for semantic web
- [ ] Version control for dataset changes

---

## Priority Order

1. ~~**Geohash Occurrence Import**~~ ✅ COMPLETED (Jan 2026)
2. ~~**Research Versioning Backend**~~ ✅ COMPLETED (Jan 2026) - Confidence scoring, source tracking
3. **Research Metadata Frontend** - Display confidence, version, sources on species pages
4. **LEAF Scoring Engine** - Critical for $100K bioregional campaigns (remaining: eco_id index, ecoregion testing, CSV export)
5. **Frontend v10 Implementation** - Display new climate/ecological data
6. **Documentation Updates** - API docs critical for users
7. **Database Optimization** - Performance improvements, taxon_id collision fix
8. **Advanced Features** - Long-term enhancements

---

## Planning Documents

| Section | Planning Doc | Status |
|---------|--------------|--------|
| LEAF™ Scoring | [docs/todo/LEAF.md](docs/todo/LEAF.md) | Active |
| Geohash Import | [docs/todo/geohash-occurrence-import.md](docs/todo/geohash-occurrence-import.md) | Active |
| Frontend v10 | [docs/todo/frontend-v10-implementation.md](docs/todo/frontend-v10-implementation.md) | Active |
| Dual Research | [docs/todo/dual-research-integration.md](docs/todo/dual-research-integration.md) | Planning |
| Ecoregion Guides | [docs/todo/ecoregion-reforestation-guides.md](docs/todo/ecoregion-reforestation-guides.md) | Active |
| Unified Zone Schema | [docs/todo/unified-zone-schema.md](docs/todo/unified-zone-schema.md) | Planning |

**Reference Documentation** (in `docs/`):
- **RECOMMENDATION_SERVICE.md** - Species recommendation service specification
- **SPECIES_NATIVE_STATUS_ROADMAP.md** - Native status scoring roadmap
- **LIGHTPAPER.md** - Project vision
- **SPEC_SHEET.md** - Feature specifications
- **TREEKIPEDIA_EXTENSIVE.md** - Architectural vision

---

## Documentation References

- **GO.md** - Onboarding procedure
- **ACTIVE.md** - Current system status
- **CHANGELOG.md** - Completed features
- **README.md** - Architecture overview
