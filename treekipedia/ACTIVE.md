# ACTIVE - Treekipedia System Status

**Last Updated**: January 20, 2026
**System Health**: Operational

---

## Live Metrics

### Database
| Metric | Value | Coverage |
|--------|-------|----------|
| **Total Species** | 67,927 | 50,797 species + 16,946 subspecies |
| **Primary Keys** | `taxon_id` + `taxon_full` | `-00` suffix = species, `-01`+ = subspecies |
| **Fields per Species** | 130+ | v10 schema + research versioning (7 new metadata fields Jan 2026) |
| **Images** | 31,796 | 13,609 species (22.1% coverage) |
| **Researched Species** | 19 | With AI-generated data |
| **Research Architecture** | Insights-based | Confidence scoring, source tracking, versioning |

### Geospatial Data
| Metric | Value |
|--------|-------|
| **Geohash Tiles** | 6.46M (Level 7, ~150m resolution) |
| **Species Occurrences** | 96.5M |
| **WWF Ecoregions** | 847 (822 with occurrence data) |
| **Ecoregion Assignment** | 97.2% complete (6.28M/6.46M tiles) |
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

### Research
- `POST /species/:taxon_id/research` - Trigger Grok-powered AI research with confidence scoring
- `GET /research/:taxon_id` - Retrieve research data

**Research Process** (Updated Jan 2026):
- Uses Grok 4.1 Fast with agentic web search
- Returns 25 AI fields with confidence scores (0-1.0)
- Tracks research version, date, sources, and token usage
- Stores metadata in `research_version`, `research_confidence`, `research_sources` columns

Full API documentation: See **API.md**

---

## Current Capabilities

### Working Features
1. **Species Search & Browse** - 67,927 species searchable
2. **Subspecies Management** - Automatic subspecies discovery on detail pages
3. **Species Images** - Sticky sidebar carousel with 31,796 images
4. **Species Detail Pages** - Two-column layout with 130+ fields (v10 data)
5. **AI Research Process** - Grok 4.1 with confidence scoring and source tracking
6. **Research Versioning** - Version history, confidence scores, source citations
7. **Geospatial Analysis** - Interactive map with polygon drawing and KML upload
8. **LEAF Scoring** - Location-based species recommendations with native status integration
9. **WCVP Native Status** - 97.5% species coverage for native/introduced filtering
10. **Ecoregion Queries** - 7 endpoints for ecological context
11. **Public API Access** - API key authentication for external integrations
12. **Admin Dashboard** - Password-protected server stats
13. **Habitat Biomes** - Derived from occurrence data, replaces unreliable SBTN land cover

### Known Issues
- `performResearch is not a function` errors in logs (non-critical)
- Database parameter validation ("null" strings vs NULL values)
- `/scripts/research/` contains 48 test files (4.1MB) - can be archived
- ~180K tiles without ecoregion assignment (ocean, Antarctica, remote areas)

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
- `XAI_API_KEY` - Grok AI research (primary)
- `OPENAI_API_KEY` - AI research (legacy)
- `PERPLEXITY_API_KEY` - AI research (legacy)
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
