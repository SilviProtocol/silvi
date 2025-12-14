# CHANGELOG - Treekipedia

Complete history of features, fixes, and improvements. For current status see ACTIVE.md, upcoming work see TODO.md.

**WRITING STYLE**: Telegraphic style. Omit articles (a, an, the), conjunctions where possible. Maintain specificity: include file references, error details, technical accuracy.

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
