# TODO.md - Treekipedia Implementation Plan

Active tasks and planned work. See CHANGELOG.md for completed features.

**Planning docs**: Detailed plans for each section are in `docs/todo/`. When complete, move to `docs/completed/`.

---

## [IN PROGRESS] - LEAF™ Scoring Engine

**Status**: Planning complete, MVP implementation starting
**Planning Doc**: [docs/todo/LEAF.md](docs/todo/LEAF.md)
**Reference**: [docs/RECOMMENDATION_SERVICE.md](docs/RECOMMENDATION_SERVICE.md)

**LEAF™** = **Location-based Ecological Aptness Forecast**

### MVP: Occurrence-Based Percentile Scoring
**Goal**: Point → Ecoregion → Percentile-ranked species recommendations

- [ ] Add index on `eco_id` column in geohash_species_tiles table
- [ ] Implement occurrence aggregation query (by eco_id)
- [ ] Apply 0.05% minimum threshold (self-calibrating filter)
- [ ] Calculate affinity score: `occurrence_count × tile_count`
- [ ] Convert to percentile LEAF score (0-100)
- [ ] Create endpoint: `GET /api/leaf/score?lat=X&lng=Y`
- [ ] Tier classification (BEST: 90-100, GOOD: 70-89, ACCEPTABLE: 50-69)
- [ ] Test on 12 target bioregional campaign ecoregions
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

### v1.4: WCVP Native Status Filtering (DATA READY)
- [x] Import WCVP native/introduced data (66,220 species - 97.5% coverage)
- [ ] Update native species API to use `wcvp_native` instead of `countries_native`
- [ ] Filter LEAF results to species native to ecoregion's countries
- [ ] Include native_status in API response

---

## [IN PROGRESS] - Frontend v10 Field Implementation

**Status**: Backend v10 migration complete, frontend display pending
**Planning Doc**: [docs/todo/frontend-v10-implementation.md](docs/todo/frontend-v10-implementation.md)

### Species Detail Page Updates
- [ ] Implement ClimateProfile component display (Köppen-Geiger, temperature, precipitation)
- [ ] Implement EcologicalInteractions component (GloBI data visualization)
- [ ] Add SBTN land cover display to species pages
- [ ] Update TypeScript types in `lib/types.ts` for new v10 fields
- [ ] Test all new field displays across species with varying data coverage

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

### Database Optimization
- [ ] Add indexes on `wcvp_native` and `wcvp_introduced` columns (replaces countries_native)
- [ ] Optimize cross-analysis query performance
- [ ] Complete remaining 3% of ecoregion tile assignments (171k tiles)
- [ ] Monitor query performance with larger polygon analyses

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

## [FUTURE] - Advanced Features

### AI Research Enhancement
- [ ] Analyze Claude 3.5 Haiku vs Grok 3 Mini testing results
- [ ] Decide on production integration strategy
- [ ] Implement improved 3-group research strategy (Ecological, Morphological, Stewardship)

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

### Open Data & Governance
- [ ] Automated monthly exports to IPFS
- [ ] Database schema documentation to EAS
- [ ] RDF/Turtle exports for semantic web
- [ ] Version control for dataset changes

---

## Priority Order

1. **LEAF™ Scoring Engine** - Critical for $100K bioregional campaigns
2. **Frontend v10 Implementation** - Display new climate/ecological data
3. **Documentation Updates** - API docs critical for users
4. **Database Optimization** - Performance improvements
5. **Advanced Features** - Long-term enhancements

---

## Planning Documents

| Section | Planning Doc | Status |
|---------|--------------|--------|
| LEAF™ Scoring | [docs/todo/LEAF.md](docs/todo/LEAF.md) | Active |
| Frontend v10 | [docs/todo/frontend-v10-implementation.md](docs/todo/frontend-v10-implementation.md) | Active |

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
