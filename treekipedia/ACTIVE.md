# ACTIVE - Treekipedia System Status

**Last Updated**: December 17, 2025
**System Health**: Operational

---

## Live Metrics

### Database
| Metric | Value | Coverage |
|--------|-------|----------|
| **Total Species** | 67,927 | 50,797 species + 16,946 subspecies |
| **Primary Keys** | `taxon_id` + `taxon_full` | `-00` suffix = species, `-01`+ = subspecies |
| **Fields per Species** | 130 | v10 schema (17 new fields added Nov 2025) |
| **Images** | 31,796 | 13,609 species (22.1% coverage) |
| **Researched Species** | 19 | With AI-generated data |
| **NFTs Minted** | 21 | Across 19 species |
| **Registered Users** | 8 | Wallet addresses |

### Geospatial Data
| Metric | Value |
|--------|-------|
| **Geohash Tiles** | 5.3M (Level 7, ~150m resolution) |
| **Species Occurrences** | 89.3M |
| **WWF Ecoregions** | 847 |
| **Ecoregion Assignment** | 97% complete (5.6M/5.8M tiles) |
| **Country Polygons** | 242 (Natural Earth data) |

### v10 Data Population
| Field Category | Population |
|----------------|------------|
| **Climate Data** | 60-88% |
| **SBTN Land Cover** | 85% (57,950 species) |
| **WCVP Native Status** | 97.5% (66,220 species) |
| **WCVP Introduced Status** | 8.4% (5,738 species) |
| **GloBI Interactions** | 24% (herbivores), sparse for others |

---

## Services Status

### Production Services
| Service | URL/Port | Status |
|---------|----------|--------|
| **Frontend** | https://treekipedia.silvi.earth | Vercel |
| **Backend API** | https://treekipedia-api.silvi.earth (port 3000) | PM2 managed |
| **Ontology Service** | https://treekipedia-graph-flow.silvi.earth (port 8000) | Active |
| **Fuseki SPARQL** | port 3030 | Active |
| **Blazegraph** | port 9999 | Active |
| **PostgreSQL** | port 5432 | Active |

### Infrastructure
- **OS**: Ubuntu 20.04 LTS (DigitalOcean AMD Premium VM)
- **CPU**: 2-core AMD (2.3GHz)
- **RAM**: 4GB total (~67% used)
- **Storage**: 78GB disk (38% used)
- **PostGIS**: 3.2 enabled

---

## API Endpoints Overview

### Species
- `GET /species` - Search species by name
- `GET /species/suggest` - Autocomplete suggestions
- `GET /species/:taxon_id` - Species details with images
- `GET /species/:taxon_id/images` - Image carousel data
- `GET /species/:taxon_id/subspecies` - Subspecies discovery

### Geospatial
- `POST /api/geospatial/analyze-plot` - Polygon-based species analysis
- `GET/POST /api/geospatial/leaf/score` - **LEAF™ species recommendations** (NEW)
- `GET /api/geospatial/ecoregions/:ecoregion_id/species` - Species in ecoregion
- `GET /api/geospatial/ecoregions/at-point` - Ecoregion at coordinates
- `POST /api/geospatial/ecoregions/intersect` - Ecoregion intersection
- `GET /api/geospatial/ecoregions/native-species/:ecoregion_name` - Native species (API key required)

### Research & NFT
- `POST /research` - Trigger AI research
- `GET /research/:taxon_id` - Retrieve research data

Full API documentation: See **API.md**

---

## Current Capabilities

### Working Features
1. **Species Search & Browse** - 67,927 species searchable
2. **Subspecies Management** - Automatic subspecies discovery on detail pages
3. **Species Images** - Sticky sidebar carousel with 31,796 images
4. **Species Detail Pages** - Two-column layout with 130 fields (v10 data)
5. **AI Research Process** - Research generation, IPFS storage, NFT minting
6. **Geospatial Analysis** - Interactive map with polygon drawing and KML upload
7. **LEAF™ Scoring** - Location-based species recommendations with native status integration
8. **WCVP Native Status** - 97.5% species coverage for native/introduced filtering
9. **Ecoregion Queries** - 7 endpoints for ecological context
10. **Public API Access** - API key authentication for external integrations
11. **Admin Dashboard** - Password-protected server stats

### Known Issues
- `performResearch is not a function` errors in logs (non-critical)
- Database parameter validation ("null" strings vs NULL values)
- `/scripts/research/` contains 48 test files (4.1MB) - can be archived

---

## Quick Commands

### Backend
```bash
cd backend && node server.js          # Run server
cd backend && nodemon server.js       # Development mode
pm2 status                            # Check PM2 processes
pm2 logs treekipedia-backend          # View backend logs
```

### Frontend
```bash
cd frontend && yarn dev               # Development server
cd frontend && yarn build             # Production build
cd frontend && yarn lint              # ESLint check
```

### Database
```bash
# Connection via .env DATABASE_URL
psql -h localhost -U tree_user -d treekipedia
```

---

## Configuration Reference

### Environment Files
- **Root `.env`** - Main configuration (DATABASE_URL, API keys, wallet secrets)
- **Frontend `.env.local`** - Frontend-exposed variables (NEXT_PUBLIC_*)

### Key Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - AI research generation
- `PERPLEXITY_API_KEY` - Alternative AI research
- `LIGHTHOUSE_API_KEY` - IPFS storage
- `API_KEYS` - Comma-separated public API keys
- Chain-specific: `CELO_RPC_URL`, `BASE_RPC_URL`, `OPTIMISM_RPC_URL`, `ARBITRUM_RPC_URL`

---

## Documentation References

- **GO.md** - Onboarding procedure (start here)
- **README.md** - Architecture overview
- **TODO.md** - Development roadmap
- **CHANGELOG.md** - Version history
- **CLAUDE.md** - Development guide
- **API.md** - Full API documentation
- **SPECIES_FIELDS_FRONTEND_GUIDE.md** - v10 field reference
