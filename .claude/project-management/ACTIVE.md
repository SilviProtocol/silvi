# ACTIVE - Treekipedia System Status

**Last Updated**: February 10, 2026
**System Health**: Operational — Multi-signal prediction system live

---

## Live Metrics

### Database Statistics
| Metric | Count | Notes |
|--------|-------|-------|
| **Total Species** | 67,743 | 50,797 species + 16,946 subspecies |
| **Geohash Tiles** | 5,786,835 | L7 precision (~150m) |
| **Images** | 31,796 | Wikimedia Commons with attribution |
| **Ecoregions** | 847 | PostGIS polygons |
| **Intact Forest Landscapes** | 6,819 | 2021 dataset |
| **Users** | 11 | Wallet-based auth |
| **NFTs Minted** | 21 | Research contributions |
| **Sponsorships** | 34 | USDC payments |

### Prediction System (Multi-Signal)
| Metric | Value |
|--------|-------|
| **Species with Centroids** | 17,924 (from v4 AlphaEarth) |
| **Habitat Centroids** | 44,625 (pgvector IVFFlat index) |
| **Prediction Signals** | 5 (embedding, spatial, range, ecoregion, climate) |
| **Recommender Strategies** | 7 (general, rewilding, agroforestry, riparian, carbon, biodiversity, erosion) |
| **Benchmark: P. radiata @ Auckland NZ** | Rank #42, 81% suitability |
| **Default Result Limit** | 100 species per prediction |
| **Latency** | ~5-15s (includes GEE sampling) |

---

## System Resources

### Services Status

| Service | Expected Port | Purpose | Status |
|---------|---------------|---------|--------|
| **PostgreSQL 17** | 5432 | Primary database | Check with `brew services list` |
| **Backend API** | 5001 | Express.js REST API | `lsof -ti:5001` |
| **Location Predictor** | 5002 | AlphaEarth GEE sampling | `lsof -ti:5002` |
| **Frontend** | 3001 | Next.js dev server | `lsof -ti:3001` |

### Production Endpoints
| Service | URL | Status |
|---------|-----|--------|
| **Frontend** | https://treekipedia.silvi.earth | Live (Vercel) |
| **API** | https://treekipedia-api.silvi.earth | Live (Digital Ocean) |

### Local Development
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:5001 |
| Location Predictor | http://localhost:5002 |
| Database | localhost:5432 (treekipedia) |

---

## API Endpoints

### Species
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| GET | `/species/suggest?q=oak` | Working | Autocomplete |
| GET | `/species?search=oak` | **BROKEN** | Column mismatch bug |
| GET | `/species/:taxon_id` | Working | Full species detail |
| GET | `/species/:taxon_id/images` | Working | Photo gallery |

### Geospatial
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/geospatial/species/:taxon_id/distribution` | Working |
| GET | `/api/geospatial/tiles/:geohash` | Working |
| GET | `/api/geospatial/tiles` | Working |
| GET | `/api/geospatial/stats` | Working |

### Prediction & Recommendation (Multi-Signal)
| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| GET | `/api/prediction/predict?lat=&lon=` | **Working** | 5-signal scoring, 100 species |
| GET | `/api/prediction/recommend?lat=&lon=&strategy=` | **Working** | SAFE-B, 7 strategies |
| GET | `/api/prediction/strategies` | Working | Lists available strategies |
| GET | `/api/prediction/sample?lat=&lon=` | Working | Raw AlphaEarth embedding |

### Embeddings (Legacy)
| Method | Endpoint | Status |
|--------|----------|--------|
| POST | `/api/embeddings/predict` | Working (legacy, use /prediction/predict instead) |
| GET | `/api/embeddings/stats` | Working |
| GET | `/api/embeddings/:taxon_id` | Working |
| GET | `/api/embeddings/similar/:taxon_id` | Working |

### Admin (GraphFlow)
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/admin/health` | Working |
| GET | `/api/admin/status` | Working |
| POST | `/api/admin/sync/species` | Needs deps |
| POST | `/api/admin/sparql/query` | Needs Fuseki |

---

## Current Capabilities

### Working Features
- Species search autocomplete (`/species/suggest`)
- Species detail pages with 115 fields
- Image gallery with Wikimedia attribution
- Distribution maps with heatmap overlay
- Geohash tile queries (STAC-compliant)
- Intact forest layer on maps
- **Multi-signal species predictor** (click map → 5-signal scoring → 100 species)
- **SAFE-B species recommender** (7 strategies: rewilding, agroforestry, carbon, etc.)
- **Signal breakdown UI** (per-species embedding/spatial/range/ecoregion/climate bars)
- **Show More pagination** (initially 30, expandable to 100)
- Admin dashboard UI
- Treederboard and user profiles
- Research sponsorship workflow (USDC payments)
- NFT minting for contributors

### Known Issues
1. **Climate scoring incomplete**: Only elevation used; precipitation/temperature not sampled at query location
   - Need to add WorldClim/CHELSA sampling to Python GEE service

3. **WCVP data gaps**: Some major introduced species (e.g., P. radiata in NZ) not listed
   - Mitigated by spatial-confirmed range scoring (de-facto present tier)

4. **GraphFlow Dependencies**: Full ontology features need Python deps installed
   - Run: `pip install -r treekipedia/python-microservice/requirements.txt`

---

## Quick Commands

### Start All Services
```bash
./start-local.sh
```

### Stop All Services
```bash
./stop-local.sh
```

### Manual Start
```bash
# Backend (port 5001)
cd treekipedia/backend && node server.js

# Location Predictor (port 5002)
cd orchestrator && python3 location_predictor_FIXED.py

# Frontend (port 3001)
cd treekipedia/frontend && npm run dev
```

### Database Access
```bash
psql treekipedia
SELECT COUNT(*) FROM species;            -- 67,743
SELECT COUNT(*) FROM geohash_species_tiles;  -- 5,786,835
SELECT PostGIS_Version();                 -- 3.6.0
```

### Test Endpoints
```bash
curl http://localhost:5001/species/suggest?q=oak
curl http://localhost:5002/health
curl http://localhost:5001/api/admin/health
```

---

## Configuration Reference

### Environment Files
| File | Purpose |
|------|---------|
| `treekipedia/backend/.env` | Backend config (DB, ports) |
| `treekipedia/frontend/.env.local` | Frontend config (API URL) |
| `orchestrator/.env` | GEE credentials |

### Key Environment Variables
```env
# Backend
DATABASE_URL=postgresql://localhost:5432/treekipedia
PORT=5001
NODE_ENV=development

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:5001

# Location Predictor
GOOGLE_CLOUD_PROJECT=treekipedia-476404
```

### Database Schema
- **species**: 115 columns with `_ai` and `_human` variants
- **images**: Wikimedia photos with attribution
- **users**: Wallet-based user profiles
- **contreebution_nfts**: NFT minting records
- **sponsorships**: Payment tracking
- **geohash_species_tiles**: PostGIS spatial data
- **species_habitat_centroids**: 64-D habitat embeddings (44,625 rows, 17,924 species, pgvector IVFFlat)
- **species_alphaearth_centroids**: Legacy POC centroids (500 rows)

---

## Documentation References

| Document | Purpose | Location |
|----------|---------|----------|
| [GO.md](GO.md) | Onboarding procedure | This folder |
| [TODO.md](TODO.md) | Development roadmap | This folder |
| [CHANGELOG.md](CHANGELOG.md) | Version history | This folder |
| [CLAUDE.md](../CLAUDE.md) | Development guide | Parent folder |
| [README.md](../../treekipedia/README.md) | Architecture overview | treekipedia/ |
| [API.md](../../treekipedia/API.md) | API documentation | treekipedia/ |

### Strategic Architecture Documents

| Document | Purpose |
|----------|---------|
| [CLAUDE_CODE_RESEARCHER_ARCHITECTURE.md](../../CLAUDE_CODE_RESEARCHER_ARCHITECTURE.md) | **Primary: Claude-native research framework** |
| [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](../../TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) | Insight-based knowledge model (master vision) |
| [Species knowledge schema.md](../../Species%20knowledge%20schema.md) | Knowledge ontology definition |

**Alternative Plans** (local LLM - on hold):
| [TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md](../../TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md) | Multi-model local LLM framework |
| [gpt5-local-ai-researcher-plan.md](../../gpt5-local-ai-researcher-plan.md) | Local LLM provider abstraction |
| [gemini-local-ai-researcher-plan.md](../../gemini-local-ai-researcher-plan.md) | LM Studio setup & Python pipeline |

### Latest Data Files (January 2025)

| File | Records | Size | Content |
|------|---------|------|---------|
| `Treekipedia_V11_Native_introduced_December_09d.csv` | 67,750 | 1.4 GB | Species knowledge (133 cols) |
| `Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet` | 96.5M | 526 MB | Occurrence coordinates |

---

## Recent Architecture Changes

### AlphaEarth Integration (Oct 2025)
- Added Python location predictor service on port 5002
- Created `species_alphaearth_centroids` table in PostgreSQL
- Integrated click-to-predict feature in Analysis map
- BigQuery storage for raw embeddings

### GraphFlow Integration (Oct 2025)
- Added admin UI at `/admin`
- Python microservice for ontology generation
- Express proxy routes for admin API
- 7 admin pages (dashboard, sync, upload, sheets, SPARQL, monitor, versions)

### Analysis Map Enhancements (Recent)
- Interactive heatmap with multi-layer support
- Intact forest layer with progressive loading
- Fixed production API URL fallbacks
