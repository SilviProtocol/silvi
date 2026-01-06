# CHANGELOG - Treekipedia

Complete history of features, fixes, and improvements. For current status see ACTIVE.md, upcoming work see TODO.md.

**WRITING STYLE**: Use telegraphic style for all entries. Omit articles (a, an, the), conjunctions where possible. Maintain specificity: include file references, error details, technical accuracy.

---

## January 2026

### 2026-01-05 - Project Management System
**DOCUMENTATION** - Implemented GO_TEMPLATE.md workflow system
- Created GO.md onboarding procedure for Claude Code
- Created ACTIVE.md with real-time system status and metrics
- Created CHANGELOG.md (this file) with historical record
- Restructured TODO.md with priority-based format
- Files: GO.md, ACTIVE.md, CHANGELOG.md, TODO.md

---

## October 2025

### 2025-10-28 - AlphaEarth Frontend Integration Complete
**FEATURE** - Click-to-predict habitat prediction in Analysis map
- Created HabitatPredictionModal.tsx for species predictions
- Created MapClickHandler.tsx for Leaflet click events
- Integrated with Map.tsx at line 878
- Progress bar with manual updates (5% → 30% → 60% → 100%)
- Top 10 species predictions with confidence scores
- Clickable cards linking to species pages
- Files: treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx, MapClickHandler.tsx, Map.tsx

### 2025-10-28 - Location Prediction Backend Complete
**FEATURE** - Python GEE microservice for AlphaEarth sampling
- Created location_predictor_service.py (Port 5002)
- POST /sample endpoint samples AlphaEarth at clicked location
- POST /sample-stream endpoint with SSE progress (optional)
- GET /health endpoint for service monitoring
- Returns 64-D embedding vector in ~3-8 seconds
- Files: orchestrator/location_predictor_service.py, orchestrator/location_predictor_FIXED.py

### 2025-10-28 - Embeddings API Endpoints
**FEATURE** - Node.js backend endpoints for species prediction
- Created embeddings controller with predict, stats, similar endpoints
- POST /api/embeddings/predict - predict species from 64-D vector
- GET /api/embeddings/:taxon_id - get species habitat centroids
- GET /api/embeddings/similar/:taxon_id - find similar species
- Cosine similarity search against species_alphaearth_centroids table
- Files: treekipedia/backend/controllers/embeddings.js, routes added to server.js

### 2025-10-28 - 100 Species Pilot Extraction Complete
**DATA** - AlphaEarth embeddings extraction for pilot species
- Extracted 45,677 clean embeddings from 100 species
- GBIF occurrences: 95,934 points across 2017-2024
- Success rate: 47.6% (AlphaEarth coverage limitation)
- Fixed coordinate type errors (Quercus rotundifolia, Eucalyptus caliginosa, Eucalyptus placita)
- Mosaic discovery critical for AlphaEarth tiled structure
- BigQuery table: treekipedia-476404.alphaearth.occ_embeddings_clean
- Files: orchestrator/gee_sampler_FIXED.py, run_pilot_PRODUCTION_FIXED.py

### 2025-10-27 - K-Prototypes Clustering POC
**FEATURE** - Species habitat signature computation
- Implemented spherical k-means with k=5 prototypes per species
- Computed centroids (64-D vectors), r (concentration), q10/q50/q90 quantiles
- Created species_alphaearth_centroids PostgreSQL table (500 rows)
- Files: orchestrator/clustering_poc/build_centroids.py

### 2025-10-27 - GBIF Integration Complete
**DATA** - Replaced flawed CSV with GBIF API data
- Downloaded 6,153 occurrences from 40 species (first pilot batch)
- Temporal distribution 2017-2024 with real collection years
- Quality filters: hasCoordinates, uncertainty ≤1000m
- GBIF Download Key: 0002042-251025141854904
- Files: orchestrator/gbif_downloader.py, gbif_data/gbif_occurrences.parquet

### 2025-10-27 - GEE + GCS + BigQuery Setup Complete
**INFRASTRUCTURE** - Cloud infrastructure for AlphaEarth pipeline
- Google Cloud SDK authenticated (project: treekipedia-476404)
- Earth Engine API enabled and tested
- Created BigQuery dataset: alphaearth
- Test scripts passing
- Files: test_ee_simple.py, authenticate_ee.py

### 2025-10-20 - GraphFlow Phase 3 Complete
**FEATURE** - Next.js Admin UI integrated into Treekipedia
- Created 7 admin pages: dashboard, sync, upload, sheets, SPARQL, monitor, versions
- Created 4 shared components: StatusCard, ProgressBar, DataTable, FileDropzone
- Total ~1,790 lines TypeScript/React code
- Matches Treekipedia emerald/black design system
- Auto-refresh status monitoring
- SSE streaming infrastructure ready
- Files: treekipedia/frontend/app/admin/

### 2025-10-20 - GraphFlow Phase 2 Complete
**FEATURE** - Express backend admin proxy routes
- Created controllers/admin.js with proxy to Python microservice
- Created routes/admin.js with all admin endpoints
- Added multer for file uploads
- SSE streaming support for sync progress
- Files: treekipedia/backend/controllers/admin.js, routes/admin.js

### 2025-10-20 - GraphFlow Phase 1 Complete
**FEATURE** - Python microservice for ontology generation
- Created api_only.py Flask headless API
- Health checks, status endpoints, ontology generation
- PostgreSQL → Fuseki sync capability
- CORS restricted to localhost:5001
- Files: treekipedia/python-microservice/api_only.py, API_SPEC.yaml

### 2025-10-18 - Local Database Sync Complete
**INFRASTRUCTURE** - Full production sync to local development
- Imported full database from Digital Ocean VM (167.172.143.162)
- 67,743 species records with all metadata
- 5,786,835 geohash tiles with PostGIS geometries
- 31,796 Wikimedia images
- Database size: 1.9GB compressed, 8.5GB uncompressed
- Files: treekipedia_custom.dump

### 2025-10-18 - STATE.md Created
**DOCUMENTATION** - Comprehensive project status document
- Documented all local services and ports
- Database statistics and data quality insights
- Known issues including species search bug
- Development workflow and troubleshooting
- Files: STATE.md

---

## Earlier History (Compressed)

### September 2025
- **Native Status Analysis**: Started backend/frontend integration for native status cross-analysis
- **Ecoregion Integration**: Planned ecoregion assignment for geohash tiles
- **PostGIS Integration**: Added STAC-compliant geospatial endpoints

### Pre-September 2025
- **v8 Species Import**: Complete v8 species data with comprehensive database updates
- **Analysis Page**: Complete geospatial species plotting feature
- **Treekipedia v6**: Initial launch with core features
- **Ontology Generator**: Original Flask application for RDF/OWL ontology building
- **Smart Contracts**: ResearchSponsorshipPayment.sol and ContreebutionNFT.sol deployed

---

## Documentation References

- **GO.md** - Onboarding procedure (this folder)
- **ACTIVE.md** - Current system status (this folder)
- **TODO.md** - Development roadmap (this folder)
- **[CLAUDE.md](../CLAUDE.md)** - Development guide (parent folder)
