# ACTIVE - Treekipedia System Status

**Last Updated**: April 18, 2026
**System Health**: Operational

**Recent**: Email OTP + Google SSO live, `treekipedia_users` anchor table live, `/profile` page shipped, DJANGO_SECRET_KEY truncation bug fixed (was silently breaking all authed endpoints since 2026-02-27). See CHANGELOG.md for details.

---

## Live Metrics

### Database
| Metric | Value | Coverage |
|--------|-------|----------|
| **Total Species** | 67,927 | 50,797 species + 16,946 subspecies |
| **Primary Keys** | `taxon_id` + `taxon_full` | `-00` suffix = species, `-01`+ = subspecies |
| **Fields per Species** | 140+ | v10 schema + v11 research fields (10 new _ai columns Jan 2026, incl. propagation_methods_ai) |
| **Images** | 31,796 | 13,609 species (22.1% coverage) |
| **Researched Species** | 20 | With AI-generated data + atomic insights (1 via CLI skill, 19 via Grok) |
| **Research Queue** | 24 pending | Ecoregion 806 pilot batch (Sicily/Southern Italy) |
| **Research Architecture** | Atomic insights v2 | Two parallel Grok calls, 35 fields, 50-80+ insights/species, per-claim confidence |
| **pgvector** | 0.8.0 | Enabled for AlphaEarth embedding similarity search |

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
- `POST /api/geospatial/analyze-plot` - Polygon-based species analysis **(free, optionalAuth)**
- `GET/POST /api/geospatial/leaf/score` - **LEAF™ species recommendations** **(auth + credits required)**
- `GET /api/geospatial/ecoregions/search?q=` - **Ecoregion autocomplete search** (NEW)
- `GET /api/geospatial/ecoregions/:ecoregion_id/species` - Species in ecoregion
- `GET /api/geospatial/ecoregions/at-point` - Ecoregion at coordinates
- `POST /api/geospatial/ecoregions/intersect` - Ecoregion intersection
- `GET /api/geospatial/ecoregions/native-species/:ecoregion_name` - Native species (API key required)

### Ecoregion Guides (NEW)
- `GET /api/guides/ecoregion/:eco_id` - **Reforestation guide** with LEAF-ranked species + synthesized content
- `POST /api/guides/ecoregion/:eco_id/synthesize` - Trigger Grok synthesis (supports `?force=true`)

### Credits & Payments (NEW)
- `GET /api/credits/balance` - User credit balance + lifetime stats (auth required)
- `GET /api/credits/transactions` - Paginated transaction history (auth required)
- `GET /api/credits/packs` - Available credit packs + prices
- `POST /api/credits/estimate-analysis` - Area → credit cost preview
- `POST /api/payments/create-invoice` - Create NOWPayments crypto invoice (auth required)
- `POST /api/payments/webhooks/nowpayments` - NOWPayments IPN webhook (HMAC verified)

### Research & Insights
- `POST /species/:taxon_id/research` - Trigger Grok instant AI research (creates insights → syncs to _ai columns)
- `GET /species/:taxon_id/insights` - Atomic insights with metadata, confidence, sources
- `POST /research/fund-research` - Add species to research queue (free, async)
- `GET /research/queue/status` - Queue monitoring
- `GET /research/queue/next` - Get next pending species from queue
- `POST /research/queue/{id}/start` - Lock species for processing
- `POST /research/queue/{id}/complete` - Mark research complete
- `POST /research/queue/bulk-add` - Batch-add species to queue
- `GET /research/{taxon_id}/context` - Research context (first vs re-research, priority fields, gaps)
- `POST /research/{taxon_id}/save` - Save atomic insights from CLI research
- `GET /research/insights/{taxon_id}/gaps` - Find missing/low-confidence fields

**Research Process** (Updated Jan 2026):
- **Instant path**: Grok 4.1 Fast atomic v2 — two parallel calls, 35 fields, 50-80+ insights → sync to _ai columns
- **Queue path**: CLI skill pulls from research_queue → web research → 50-80+ atomic insights → save via API
- Queue supports multi-session coordination (local VM + remote Claude Code sessions)
- All endpoints accessible at `https://treekipedia-api.silvi.earth/research/...`
- Returns 35 AI fields with confidence scores (0-1.0)
- Tracks research version, date, sources, and token usage
- Insights endpoint returns `has_insights`, `metadata` (version, confidence, model, sources), and flat insights array

### Prediction (NEW from djimo merge)
- `GET/POST /api/prediction/*` - Species suitability prediction using AlphaEarth embeddings
- Pending: v4 parquet data + clustering pipeline

### Admin
- `GET /api/admin/*` - Admin endpoints (new from djimo merge)
- `GET /api/embeddings/*` - Embedding management (new from djimo merge)

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
10. **Ecoregion Queries** - 8 endpoints for ecological context
11. **Ecoregion Guides** - `/guide` search + `/guide/[eco_id]` reforestation guides with LEAF scoring
12. **Public API Access** - API key authentication for external integrations
13. **Admin Dashboard** - Password-protected server stats
14. **Habitat Biomes** - Derived from occurrence data, replaces unreliable SBTN land cover
15. **Credit System** - Credit gating: LEAF Score (10-685 by area, or flat 10), Guide (200), Research (25). Site Analysis = free. 50 free signup bonus.
16. **NOWPayments** - Crypto checkout for credit packs (Starter $10, Pro $40, Enterprise $120)

### Known Issues
- Database parameter validation ("null" strings vs NULL values)
- `/scripts/research/` contains 48 test files (4.1MB) - can be archived
- ~180K tiles without ecoregion assignment (ocean, Antarctica, remote areas)
- AlphaEarth v4 parquet not on server (was on djimo's local machine, pending transfer)
- `orchestrator/` contains debug scripts and logs that should be pruned
- Research queue write endpoints (save, start, complete, bulk-add) have no API key auth yet

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
- `NOWPAYMENTS_API_KEY` - NOWPayments crypto checkout
- `NOWPAYMENTS_IPN_SECRET` - NOWPayments webhook HMAC verification
- `NOWPAYMENTS_SANDBOX` - Sandbox mode (`true`/`false`)
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
