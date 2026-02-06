# CHANGELOG - Treekipedia

Complete history of features, fixes, and improvements. For current status see ACTIVE.md, upcoming work see TODO.md.

**WRITING STYLE**: Telegraphic style. Omit articles (a, an, the), conjunctions where possible. Maintain specificity: include file references, error details, technical accuracy.

---

## 2026-02-04 - Guide Synthesis & Unified Scoring Architecture

**Planning Doc**: [docs/todo/leaf-alpha-unified-scoring.md](docs/todo/leaf-alpha-unified-scoring.md)

**Species Research** — Researched missing top LEAF species for Tyrrhenian-Adriatic guide
- Pistacia lentiscus (68 insights, v1) — LEAF rank #1
- Quercus ilex (73 insights, v2) — LEAF rank #3
- Juniperus phoenicea (63 insights, v1) — LEAF rank #5
- Juniperus oxycedrus (69 insights, v1) — LEAF rank #6
- Fixed Myrtus communis sync (67 insights existed but weren't synced to species._ai columns)
- 5 species × ~67 insights = 341 total insights created

**Guide Synthesis** — Regenerated Tyrrhenian-Adriatic guide v4 with updated species data
- Overview now references: Holm Oak (Leccio/Chêne vert), Mastic Tree (Lentisco), Common Myrtle (Mirto), Strawberry Tree (Corbezzolo)
- Planting strategy with stratification percentages and spacing recommendations
- Climate context with Mediterranean-specific guidance
- Conservation notes referencing Natura 2000, EU LIFE projects

**LEAF + AlphaEarth Unified Scoring** — Expanded planning doc (~290 → ~550 lines)
- Added two query modes: Ecoregion (current) vs Site-specific (new)
- Added AOI support: Point, Small Plot (≤10ha), Medium Plot (≤100ha), Large Area (≤1000ha)
- Added 6 restoration strategies: rewilding, agroforestry, riparian, carbon, biodiversity, general
- Added strategy weight profiles (LEAF/Alpha/Functional/Biotic percentages)
- Added functional trait scoring with boost/penalize lists per strategy
- Added site environmental data: elevation, slope, aspect, tree cover
- Added polygon processing flow with multi-point sampling
- Added hard filters: native status, elevation compatibility, invasive flag
- Linked to MASTER_PREDICTION_ARCHITECTURE_2.md (copied to docs/)

**Documentation** — Copied MASTER_PREDICTION_ARCHITECTURE_2.md (45KB, 1,096 lines) to docs/
- Full SAFE-B framework reference
- Environmental variables inventory (climate, soil, topographic, hydrological, disturbance)
- Clustering & bias correction algorithms
- API design specifications

Files: `docs/todo/leaf-alpha-unified-scoring.md`, `docs/MASTER_PREDICTION_ARCHITECTURE_2.md`, `backend/services/guideSynthesis.js`

---

## 2026-01-28 - Ecoregion Reforestation Guides

**Planning Doc**: [docs/todo/ecoregion-reforestation-guides.md](docs/todo/ecoregion-reforestation-guides.md)

**Backend API** (`backend/controllers/guides.js`, `backend/routes/guides.js`)
- `GET /api/guides/ecoregion/:eco_id` — Returns ecoregion metadata, synthesized content, LEAF-ranked species grouped by tier, top 10 enriched with _ai fields
- `POST /api/guides/ecoregion/:eco_id/synthesize` — Triggers Grok 4.1 Fast synthesis, stores in `ecoregion_guides` table; supports `?force=true` regeneration
- `GET /api/geospatial/ecoregions/search?q=` — ILIKE search on eco_name for autocomplete (added to geospatial.js)

**Database** (`database/09_ecoregion_guides_table.sql`)
- New `ecoregion_guides` table: eco_id (PK), overview_intro, planting_strategy, climate_context, conservation_notes, generated_at, model_used, synthesis_version, species_count, source_data (JSONB)

**Guide Synthesis Service** (`backend/services/guideSynthesis.js`)
- Grok 4.1 Fast generates 4 structured sections from ecoregion metadata + top 20 species _ai summaries
- Returns JSON with overview_intro, planting_strategy, climate_context, conservation_notes

**Frontend Pages** (`frontend/app/guide/`)
- `/guide` — Ecoregion search with 300ms debounced autocomplete, info cards (LEAF Scoring, AI Research, 847 Ecoregions)
- `/guide/[eco_id]` — Accordion-style guide: Overview, Top Species (2-col cards), All Species by Tier (compact rows), Planting Strategy, Climate, Conservation, Methodology
- Components: Accordion (useState + ChevronDown/Up), TierBadge, SpeciesCard, CompactSpeciesRow
- Links species cards to `/species/[taxon_id]`

**API Types** (`frontend/lib/api.ts`)
- Added: `EcoregionSearchResult`, `EcoregionGuideSpecies`, `EcoregionGuideSynthesized`, `EcoregionGuideResponse`
- Functions: `searchEcoregions()`, `getEcoregionGuide()`

**Verification**
- Ecoregion 806 (Tyrrhenian-Adriatic): 1,208 species scored, 122 BEST, 241 GOOD
- Ecoregion 331 (Appalachian-Blue Ridge): 2,835 species scored
- Backend live at `https://treekipedia-api.silvi.earth/api/guides/...`

---

## 2026-01-27 - Atomic Grok Research (v2)

**Grok research upgraded from 25 flat fields to 35 fields with multi-value array support**
- Two parallel Grok API calls via `Promise.allSettled`: Call 1 (Identity + Ecological, 14 fields), Call 2 (Morphological + Stewardship, 21 fields)
- 12 array fields return `[{text, context, region?, source_hint?}]` — one insight row per array element
- 23 single-value fields (string/number) — one insight row each
- Expected output: 50-80+ atomic insights per well-documented species (was exactly 25)
- Per-insight confidence: 0.80 with source_hint, 0.70 without, 0.75 for string/numeric fields
- Old insights marked `is_current = FALSE` before inserting new batch (clean supersession)
- Partial success handling: if one call fails, results from other still saved; response includes `calls_succeeded` and `partial` flag
- 10 new fields covered: etymology, synonyms, identification_features, climate_tolerance, tolerances, associated_species, propagation_methods, timber_value, non_timber_products, nutritional_caloric_value
- Added `propagation_methods_ai` column to species table (was missing)
- Token usage tracked per species in `research_token_usage` with agent `grok-research-atomic`
- Legacy `performResearch()` (v1) preserved for backward compatibility
- Files: `backend/services/grokResearch.js`, `backend/controllers/species.js`

---

## 2026-01-27 - djimotreekipedia Merge + Frontend Alignment

**Full merge of djimotreekipedia branch into latest**
- Frontend: adopted djimo's species page (DataField, tabs, page, hooks, ResearchMetadataPanel)
- Backend: kept our species.js (Grok agentic research, insights flow, confidence scoring)
- New from djimo: research.js controller (queue), admin.js, embeddings.js, prediction routes (1,214 lines), orchestrator service, python-microservice, v11 schema migrations, insights schema migrations
- Backup: `latest-pre-merge` branch preserved
- Added missing `multer` dependency for admin routes
- Added 9 missing species columns: `etymology_ai`, `synonyms_ai`, `identification_features_ai`, `climate_tolerance_ai`, `tolerances_ai`, `associated_species_ai`, `timber_value_ai`, `non_timber_products_ai`, `nutritional_caloric_value_ai`

**Insights endpoint fixed** - `GET /species/:taxon_id/insights`
- Now returns `has_insights` boolean (was missing → Synthetic Knowledge panel never rendered)
- Now returns `metadata` object: version, research_date, model, insight_count, field_count, avg_confidence, source_count
- Returns `insights` as flat array (was grouped object → caused `.forEach is not a function` crash)
- Retains `insights_grouped` for optional grouped access

**Frontend data flow simplified** - `useSpeciesData.ts`
- Reduced from 3 parallel queries to 2: species + insights (removed redundant `/research/:taxon_id` query)
- `researchData` aliased to species query data for backwards compatibility with TabContainer
- `getFieldValue()` priority chain unchanged: human → ai → legacy
- Removed debug console.logs

**Dead code removed**
- Deleted `InsightField.tsx`, `InsightItem.tsx` (unused, different interface than API)
- Deleted `useResearchProcess.ts` (legacy polling hook, never imported by page.tsx)

**Infrastructure setup for AlphaEarth pipeline**
- Installed pgvector 0.8.0 extension in PostgreSQL (`CREATE EXTENSION vector`)
- Installed Python earthengine-api, scikit-learn, numpy, pandas, pyarrow
- GEE authenticated with dev@silvi.earth, project `treekipedia` (86K AlphaEarth images accessible)
- v4 parquet data pending (was on djimo's local machine)

**Planning docs added**
- `docs/todo/dual-research-integration.md` - NOWPayments crypto payment + dual research buttons
- Updated TODO.md with dual research checklist and planning doc table

Files: `backend/controllers/species.js`, `backend/controllers/research.js`, `frontend/app/species/[taxon_id]/hooks/useSpeciesData.ts`, `frontend/lib/api.ts`

---

## 2026-01-23 - Insights Flow Integration

**Research Flow Refactored** - Research now writes to insights table, then syncs to _ai columns
- Flow: Grok API → Create Insights → Sync to species._ai columns
- `createInsightsFromResearch()` - Creates atomic insights from each research field
- `syncInsightsToSpecies()` - Aggregates insights back to _ai columns for backward compatibility
- Each insight stores: `claim_type`, `claim_value` (JSON), `confidence`, `sources`, `research_session_id`
- Content-hash deduplication via trigger prevents duplicate insights
- Tested: 23 insights created for Manilkara bidentata, synced to species table

**New Endpoint** - `GET /species/:taxon_id/insights`
- Returns all current insights for species grouped by claim_type
- Optional `?full=true` for complete insight data with sources/confidence_breakdown
- Response: `{taxon_id, insight_count, claim_types, insights: {habitat: [...], ...}}`

**Field Mapping** - 25 research fields mapped to claim_types
- Text fields stored as `{text: "..."}` in claim_value
- Numeric fields (maximum_height, maximum_diameter, maximum_tree_age) stored as `{value: N, unit: "meters|years"}`
- ON CONFLICT updates confidence if new is higher, preserves existing insights

Files: `backend/controllers/species.js`

---

## 2026-01-20 - Insights Architecture & Research Versioning

**Database Migration** - Added insights architecture for research quality tracking
- Applied `database/06_insights_architecture.sql` migration
- New species columns: `research_version`, `research_date`, `research_agent`, `research_confidence`, `research_sources`, `research_flags`, `research_token_cost`
- New helper columns: `sci_lower`, `taxon_lower`, `taxon_full_clean` for search optimization
- New tables: `insights` (atomic knowledge), `research_history` (audit trail), `research_token_usage` (cost tracking), `research_queue` (processing status)
- New views: `research_progress`, `research_token_summary`, `insights_needing_review`, `confidence_statistics`
- Aggregation functions: `aggregate_text_insights()`, `aggregate_ranked_insights()`, `aggregate_top_insight()`
- Note: FK constraint on insights.taxon_id omitted due to 27 duplicate taxon_ids in species table (logged in TODO.md)

**Research Process** - Updated Grok service with confidence scoring
- `backend/services/grokResearch.js` now extracts confidence and sources from Grok responses
- Confidence calculation: field_coverage (40%) + critical_fields (30%) + specificity (20%) + sources (10%)
- Critical fields: `general_description_ai`, `habitat_ai`, `ecological_function_ai`, `conservation_status_ai`, `native_adapted_habitats_ai`
- Source extraction from web_search tool_use blocks in Grok API response
- Returns `confidence`, `confidence_breakdown`, `sources`, `model` in response

**Species Controller** - Updated research endpoint for versioning
- `POST /species/:taxon_id/research` now stores versioning metadata
- Increments `research_version`, sets `research_date`, `research_agent`, `research_confidence`, `research_sources`
- Tracks token usage in `research_token_usage` table
- API response includes confidence scoring and source data
- Files: `backend/controllers/species.js`

**Frontend Types** - Added research metadata fields to TypeScript
- Added `research_version`, `research_date`, `research_agent`, `research_confidence`, `research_sources`, `research_flags`, `research_token_cost`, `popular_common_name_ai` to `TreeSpecies` interface
- Files: `frontend/lib/types.ts`

**Data Quality Discovery** - Found 27 duplicate taxon_ids affecting 54 species
- Same taxon_id assigned to different species within same genus
- Example: `AngMaApPtTs00060-00` = both *Pittosporum ellipticum* and *Pittosporum bicolor*
- Documented in TODO.md for future fix
- Blocks UNIQUE constraint on taxon_id column

---

## 2026-01-13 - Geohash Occurrence Data Refresh & Habitat Biomes

**Database** - Full refresh of geohash occurrence data from BigQuery parquet export
- Imported 6,458,119 tiles (was 5,786,835) - +11.6% increase
- Total occurrences: 96,512,768 (was 94,422,564) - +2.2% increase
- 12 parquet files processed, ~2GB total
- Zero import errors
- Files: `scripts/import_geohash_parquet.py`

**Geometry Fix** - Recomputed geometries from geohash strings
- Source WKT polygons were degenerate (5.4M tiles affected)
- Used `ST_GeomFromGeoHash()` to recompute valid polygons
- All 6.46M geometries now valid
- Files: `scripts/fix_geohash_geometries.py`

**Ecoregion Assignment** - Assigned ecoregions to 664,854 new tiles
- Preserved 5.6M existing assignments via cache table
- Phase 1: Center point containment (fast)
- Phase 2: Intersection matching for boundary tiles
- Final coverage: 97.2% (6,278,540 tiles with ecoregion)
- Files: `scripts/assign_ecoregions_new_tiles.py`

**Habitat Biomes Feature** - Replaced unreliable `sbtn_landcover` with derived biomes
- SBTN land cover data was corrupted (tropical species showing "Permanent snow/ice")
- New `derived_biomes` field computed from occurrence data per species
- API returns top 5 biomes with ≥10 occurrences, ordered by occurrence count
- Frontend "Quick Facts" now shows "Habitat Biomes" instead of "Land Cover Types"
- Hover tooltip shows occurrence/tile counts for each biome
- Files: `backend/controllers/species.js`, `frontend/app/species/[taxon_id]/components/SpeciesInfobox.tsx`, `frontend/lib/types.ts`

**Verification** - LEAF scoring tested on Appalachian-Blue Ridge
- Top species: Red Maple, Tuliptree, White Oak, Black Gum, Black Cherry
- Species analysis spatial queries work correctly
- Updated ACTIVE.md with new metrics

---

## 2025-12-17 - Data Cleanup & LEAF Enhancements

**Database** - Cleaned `taxon_full` field, removing redundant " NA" suffix from 50,970 species-level records
- `taxon_full` now contains clean names: "Pinus roxburghii" instead of "Pinus roxburghii NA"
- Subspecies records unchanged: "Aralia elata glabrescens"
- `taxon_id` + `taxon_full` established as primary anchor fields
- `taxon_id` suffix encodes type: `-00` = parent species, `-01`+ = subspecies
- Generated `species_names.csv` export (67,927 records)

**LEAF API** - Added `eco_name` parameter support
- Endpoint now accepts `eco_name` (exact match) in addition to `eco_id`
- Example: `?eco_name=Appalachian-Blue%20Ridge%20forests`
- Files: `backend/controllers/geospatial.js`

**Documentation** - Created LEAF Integration Guide for Silvi Protocol
- Comprehensive guide for external integration
- API reference, algorithm explanation, target ecoregions list
- File: `docs/LEAF_INTEGRATION_GUIDE.md`

---

## 2025-12-15 - LEAF™ Endpoint Implementation

**LEAF™ Score API** - Full implementation of Location-based Ecological Aptness Forecast
- New endpoint: `GET/POST /api/geospatial/leaf/score`
- Three input methods: eco_id, lat/lng point, or GeoJSON polygon
- Multi-ecoregion support: Polygons spanning multiple ecoregions aggregate weighted by area
- Algorithm: Pool = (WCVP natives) UNION (occurrence species) MINUS (introduced)
- Scoring: `weighted_affinity = (occurrence_count × tile_count) × native_multiplier`
- Native boost: ×2.0, Unknown: ×1.0, Introduced: EXCLUDED
- Returns: species ranked by LEAF score with tier (BEST/GOOD/ACCEPTABLE/LOW)
- Tested on Appalachian-Blue Ridge: 3,292 species pool, 468 introduced excluded
- Files: `backend/controllers/geospatial.js`, `backend/routes/geospatial.js`

**Species Pages** - Updated to use WCVP native/introduced data
- SpeciesInfobox "Native to" section now uses `wcvp_native` (97.5% coverage)
- Geographic tab fields updated: "Native Regions", "Introduced Regions"
- Added `wcvp_native`, `wcvp_introduced` to TypeScript types
- Files: `frontend/app/species/[taxon_id]/components/SpeciesInfobox.tsx`, `frontend/app/species/[taxon_id]/hooks/useFieldDefinitions.ts`, `frontend/lib/types.ts`

---

## 2025-12-12 - WCVP Native Status Integration

**Database** - Imported authoritative WCVP (World Checklist of Vascular Plants) native/introduced data
- Added `wcvp_native` column: 66,220 species (97.5% coverage) - 3x improvement over previous 26%
- Added `wcvp_introduced` column: 5,738 species with introduced region data
- Source: Kew Gardens WCVP, significantly more reliable than GBIF-derived `countries_native`
- Import script: `scripts/import_wcvp_native_status.js`, matched on `taxon_full`

**API** - Updated native species endpoint to use WCVP data
- `/api/geospatial/ecoregions/native-species/:ecoregion_name` now uses `wcvp_native` instead of `countries_native`
- Created `backend/utils/wcvpRegions.js` with country-to-WCVP-region mappings
- US states, Canadian provinces, Brazilian/Mexican/Chinese regions properly mapped
- Response includes `wcvp_native`, `wcvp_introduced` fields and WCVP data source indicator
- Files: `backend/controllers/geospatial.js`, `backend/utils/wcvpRegions.js`

**LEAF Roadmap** - Updated v1.4 milestone now achievable with WCVP data
- Files: `docs/todo/LEAF.md`, `TODO.md`

**GIS Analysis Tool** - Updated to use WCVP native status
- `analyzePlot` endpoint now uses `wcvp_native` and `wcvp_introduced` instead of `countries_native`
- Native status detection uses WCVP region mappings (US states, Canadian provinces, etc.)
- Cross-analysis summary now shows "WCVP (World Checklist of Vascular Plants)" data source
- Frontend types updated with `dataSource` field
- Files: `backend/controllers/geospatial.js`, `frontend/lib/types.ts`, `frontend/app/analysis/components/CrossAnalysisSummary.tsx`

---

## 2025-11-20 - Frontend Design System Overhaul

**UI/UX** - Complete species page redesign with unified color system
- Implemented two-column desktop layout with sticky 400px image sidebar
- Unified nature-themed palette: emerald (primary), green (secondary), amber (accent), blue (precipitation), red (threats only)
- Enhanced contrast: card backgrounds `bg-black/40`, borders `border-white/15`
- Standardized rounding: `rounded-xl` for cards, `rounded-full` for badges
- Search page simplified to minimal centered design
- Admin auth simplified to client-side password check (removed backend session complexity)
- Performance: Search page 168kB → 108kB (60kB reduction)
- Files: `/frontend/app/species/[taxon_id]/`, `/frontend/app/search/page.tsx`, `/frontend/app/admin/page.tsx`

---

## 2025-11-18 - Treekipedia v10 Data Migration

**Database** - Major schema update with 17 new fields (113 → 130 total)
- Added 8 climate fields: Köppen-Geiger, temperature, precipitation metrics
- Added 8 GloBI ecological interaction fields: pollinators, herbivores, parasites, pathogens
- Added SBTN land cover classification field
- Import strategy: matched on `taxon_full` to preserve existing taxon_ids
- 67,701 species updated (99.9%), 42 new species added
- Climate data: 60-88% populated, SBTN: 85%, GloBI herbivores: 24%
- Streaming CSV import for 1.3GB file, batch processing 1,000 records/transaction
- Created index on `taxon_full` for fast lookups
- Data integrity verified: all 21 NFTs, 17,276 image links, geohash references intact
- Files: `database/04_v10_schema_migration.sql`, `database/05_v10_climate_fields.sql`, `scripts/import_v10_species.js`
- Documentation: Created `SPECIES_FIELDS_FRONTEND_GUIDE.md` (130-field guide)

---

## 2025-10-24 - Enhanced Biome Filtering for Native Species API

**API** - Ecological filtering prevents inappropriate recommendations
- Added biome-based filtering to `/api/geospatial/ecoregions/native-species/:ecoregion_name`
- Dual-criteria: species must match BOTH country AND biome type
- Fixed SQL injection vulnerability: replaced string interpolation with parameterized queries
- Added `biome_match` field to `filters_applied` in response
- Updated `PUBLIC_API_GUIDE.md` with biome filtering documentation
- Files: `backend/controllers/geospatial.js`, `PUBLIC_API_GUIDE.md`

---

## 2025-10-22 - SSL & NGINX Configuration

**Infrastructure** - Ontology service SSL setup
- Migrated to `https://treekipedia-graph-flow.silvi.earth`
- Let's Encrypt certificate configured
- HTTP/2 enabled, HSTS with 1-year max-age
- Services exposed: main ontology (8000), Fuseki SPARQL (3030), health check
- 300-second timeouts for large ontology queries
- Files: `/etc/nginx/sites-available/treekipedia-graph-flow`

---

## 2025-10-22 - Public API Access with Authentication

**API** - External access for native species recommendations
- Implemented API key middleware (`backend/middleware/apiAuth.js`)
- Route-specific public CORS allowing all origins
- Rate limiting: 60 requests/minute per API key
- Protected endpoint: `GET /api/geospatial/ecoregions/native-species/:ecoregion_name`
- Response headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- Created `PUBLIC_API_GUIDE.md` with examples in cURL, JavaScript, Python, Node.js
- Files: `backend/middleware/apiAuth.js`, `backend/routes/geospatial.js`

---

## 2025-10-02 - Image Re-linking After v9 Migration

**Database** - Fixed broken image links post-migration
- v9 import changed taxon_id structure, breaking 31,796 image links
- URL-based species name extraction from Wikimedia Commons filenames
- Added `species_scientific_name` column to images table
- Extraction: 20,145 images (63.4%) valid names from URLs
- Re-linking: 17,276 images (54.3%) successfully re-linked
- Files: `scripts/relink_images_from_urls.js`

---

## 2025-10-01 - Subspecies & Taxonomy Management

**Feature** - Complete subspecies system implementation
- Fixed duplicate subspecies in search (Pinus ponderosa: 7 → 1 result)
- PostgreSQL `DISTINCT ON (species_scientific_name)` with subspecies prioritization
- New endpoint: `GET /species/:taxon_id/subspecies`
- Created `SubspeciesSection.tsx` with clickable subspecies cards
- Database: 50,797 species-level + 16,946 subspecies/variety records
- Fixed search form to handle 47,788 species with NULL common names
- Files: `backend/controllers/species.js`, `frontend/app/species/[taxon_id]/components/SubspeciesSection.tsx`

---

## 2025-09-16 - Species Analysis Infrastructure

**Geospatial** - Major spatial query infrastructure completion
- v9 species data: 67,743 species imported with corrected taxon_id mappings
- Geohash geometry population: 5.8M tiles using ST_GeomFromGeoHash()
- Countries integration: 242 Natural Earth country polygons imported
- Cross-analysis unlocked: native status analysis, country detection
- Smart name mapping for country variations
- Files: `backend/controllers/geospatial.js`, `database/03_ecoregions_integration.sql`

---

## 2025-08-15 - Ecoregions Integration

**Geospatial** - WWF ecoregions full integration
- Imported 847 WWF Terrestrial Ecoregions from shapefile
- Metadata: ecoregion names, biomes, realms, areas
- MultiPolygon geometries with GIST spatial indexes
- Added eco_id, eco_name, biome_name, realm columns to geohash tiles
- Created 7 new ecoregion API endpoints
- Batch tile assignment: 5.6M/5.8M tiles (97% complete)
- Files: `scripts/import_ecoregions.js`, `database/03_ecoregions_integration.sql`, `scripts/assign_ecoregions_batch.js`

---

## 2025-07-28 - Analysis Page Frontend

**Feature** - Full geospatial analysis UI
- React-Leaflet integration with polygon drawing and KML upload
- Species analysis within user-drawn polygons
- Treekipedia design system applied
- Collapsible instructions, transparent backgrounds
- Files: `frontend/app/analysis/page.tsx`, `frontend/app/analysis/components/Map.tsx`

---

## 2025-07-21 - Geospatial Data Import

**Database** - Marina's compressed geohash data imported
- 4.7M geohash tiles containing 89M occurrence records
- PostGIS 3.2 installation enabled
- Streaming CSV import for 480MB file
- Zero errors, ready for spatial queries
- Files: `scripts/import_geohash_csv.js`

---

## 2025-07-08 - PostGIS Geospatial Integration

**Infrastructure** - Complete spatial database setup
- STAC-compliant geohash_species_tiles table (Level 7, ~150m resolution)
- 6 new spatial API endpoints (nearby species, distribution maps, heatmaps)
- Spatial query functions: ST_DWithin, ST_Intersects, ST_GeomFromGeoJSON
- Import pipeline for compressed geohash data
- Files: `database/02_create_geohash_tiles_table.sql`, `backend/controllers/geospatial.js`

---

## 2025-06-16 - Data Attribution & Images System

**Feature** - Complete image management implementation
- Created Images table with 31,796 images
- Node.js import script with species name matching
- Primary image designation system
- API endpoints for image data serving
- Custom React image carousel with navigation, thumbnails, attribution
- Complete reference list in site footer (12+ data sources)
- Fixed PM2 deployment issue causing API crashes
- Files: `database/create_images_table.sql`, `scripts/import_images.js`, `frontend/app/species/[taxon_id]/components/ImageCarousel.tsx`

---

## Earlier History (Pre-2025-06)

### Initial Launch Features
- Tree species search with 50,000+ species
- AI research agent with OpenAI/Perplexity integration
- Species knowledge pages with taxonomic data
- Contreebution NFT minting (Base, Celo, Optimism, Arbitrum)
- EAS attestation and IPFS storage integration
- Treederboard leaderboard
- Blazegraph knowledge graph setup
- Wallet integration via Wagmi v2

---

## Documentation References

- **GO.md** - Onboarding procedure
- **ACTIVE.md** - Current system status
- **TODO.md** - Development roadmap
- **README.md** - Architecture overview
