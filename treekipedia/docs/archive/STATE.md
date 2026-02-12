# Treekipedia Project State Document
**Last Updated**: October 18, 2025
**Environment**: Local Development (macOS)
**Status**: Fully Operational with Known Issues

---

## Quick Status Overview

| Component | Status | Details |
|-----------|--------|---------|
| Local Backend | ✅ Running | Port 5001, PostgreSQL 17 + PostGIS |
| Local Frontend | ✅ Running | Port 3000, Next.js 15 dev server |
| Database | ✅ Synced | 67,743 species, 5.7M geohash tiles |
| Production Sync | ✅ Complete | Full database dump from Digital Ocean |
| Known Issues | ⚠️ 1 Critical | Species search endpoint broken |

---

## Local Development Environment

### Running Services

All services are currently running and healthy:

```bash
# Backend API
http://localhost:5001
Status: Active (PID 59218)
Uptime: ~3 hours

# Frontend Dev Server
http://localhost:3000
Status: Active (PID 48957)
Uptime: ~3.5 hours

# PostgreSQL Database
Port: 5432
Version: PostgreSQL 17.6 (Homebrew)
Extensions: PostGIS 3.6.0
Database: treekipedia
```

### Environment Configuration

**Frontend** ([.env.local](treekipedia/frontend/.env.local)):
```env
NEXT_PUBLIC_API_URL=http://localhost:5001
```

**Backend** ([.env](treekipedia/.env)):
```env
DATABASE_URL=postgresql://localhost:5432/treekipedia
PORT=5001
NODE_ENV=development
DEBUG_CORS=true
```

**Note**: Optional API keys (OpenAI, Perplexity, Infura, Lighthouse) are not configured for local development. These are only needed for:
- AI-powered species research
- Blockchain NFT minting
- IPFS data storage

---

## Database Statistics

### Core Data Metrics

| Metric | Count | Notes |
|--------|-------|-------|
| **Total Species Records** | 67,743 | Includes species + subspecies |
| Species-only Records | 50,797 | 75% of total |
| Subspecies/Variety Records | 16,946 | 25% of total |
| **Images** | 31,796 | Wikimedia Commons w/ attribution |
| **Geohash Tiles** | 5,786,835 | L7 precision (~150m × 150m) |
| **Ecoregions** | 847 | PostGIS MultiPolygon geometries |
| **Intact Forest Landscapes** | 6,819 | 2021 dataset, 1.2GB |
| **Users** | 11 | Wallet-based authentication |
| **NFTs Minted** | 21 | Research contributions |
| **Sponsorships** | 34 | USDC payment tracking |

### Data Quality Insights

**Species Coverage Analysis** (from recent investigation):
- **48,129 species** have geohash occurrence data (geographic coordinates)
- **19,614 species** lack occurrence data:
  - 16,862 are subspecies records (subspecies often lack individual occurrence data)
  - 2,752 are species-level records without geographic data

**Intact Forest Classification**:
```
NO (not in intact forest):     35,613 species (52.6%)
NO;YES (in both):               20,729 species (30.6%)
NA (no data):                    6,366 species (9.4%)
YES;NO (in both):                4,042 species (6.0%)
YES (only in intact forest):       993 species (1.5%)
```

The "NA" values represent species without geographic occurrence data, which cannot be spatially analyzed against intact forest polygons.

### Database Schema

7 core tables + PostGIS extensions:
1. **species** - 115 columns with dual `_ai` and `_human` fields
2. **images** - Photo library with licensing
3. **users** - User profiles and points
4. **contreebution_nfts** - NFT records
5. **sponsorships** - Payment transactions
6. **sponsorship_items** - Individual species funded
7. **geohash_species_tiles** - PostGIS spatial occurrence data

Additional tables:
- `ecoregions` (847 polygons)
- `intact_forest_landscapes_2021` (6,819 polygons)
- Multiple backup tables (`species_backup_*`, `species_v7_backup`, `species_v8`)

---

## Critical Issues

### 1. Species Search Endpoint Broken (CRITICAL)

**Issue**: `/species?search=oak` returns 500 Internal Server Error

**Root Cause**: Controller queries non-existent column named "species"
- File: [backend/controllers/species.js](treekipedia/backend/controllers/species.js) ~line 25
- Query attempts: `WHERE species ILIKE '%${search}%'`
- Actual columns: `species_scientific_name`, `accepted_scientific_name`

**Impact**: Search functionality completely broken

**Fix Required**:
```javascript
// Change from:
WHERE species ILIKE '%${search}%'

// To:
WHERE species_scientific_name ILIKE '%${search}%'
   OR accepted_scientific_name ILIKE '%${search}%'
```

**Priority**: Fix immediately before any production deployment

---

## Working Endpoints

### Verified Working

| Endpoint | Method | Status | Example |
|----------|--------|--------|---------|
| `/api` | GET | ✅ | API info and version |
| `/species/suggest` | GET | ✅ | `?query=oak` returns suggestions |
| `/treederboard` | GET | ✅ | Returns 11 user records |
| `/api/geospatial/*` | GET/POST | ✅ | Spatial queries functional |

### Untested (Likely Working)

- `/species/:taxon_id` - Species detail page
- `/treederboard/user/:wallet` - User profile
- `/research/:taxon_id` - Research data
- `/sponsorships/transaction/:hash` - Sponsorship status

---

## Technology Stack

### Frontend
- **Framework**: Next.js 15.2.3 + React 18.3.1
- **Language**: TypeScript
- **Styling**: Tailwind CSS 3.4.1
- **State**: React Query 5.71.1
- **Maps**: Leaflet 1.9.4
- **Web3**: Wagmi 2.14.15, Ethers.js 6.13.5

### Backend
- **Framework**: Express.js 4.21.2
- **Language**: JavaScript (Node.js 18+)
- **Database**: PostgreSQL 17 + PostGIS 3.6
- **HTTP Client**: Axios 1.8.4

### Database
- **Primary**: PostgreSQL 17.6 (Homebrew)
- **Spatial**: PostGIS 3.6.0
- **Size**: ~8.5GB (full dataset)

---

## Recent Discoveries

### Data Analysis Findings (Oct 18, 2025)

1. **Species Count Mystery Solved**:
   - Total: 67,743 records (not 67k + 16k)
   - Breakdown: 50,797 species + 16,946 subspecies = 67,743
   - Unique species names: 50,922

2. **Geohash Coverage Explained**:
   - 48,129 species have occurrence data in geohash tiles
   - 19,614 species lack occurrence data (86% are subspecies)
   - Global polygon analysis correctly returns 48,130 species

3. **Intact Forest "Unknown" Classification**:
   - 6,366 species marked as "NA" (9.4%)
   - These lack geographic data for spatial analysis
   - Not a bug - valid representation of data gaps

---

## Git Repository Status

**Current Branch**: master (up-to-date with origin/master)

**Recent Commits**:
- `29795d0` - Merge pull request #13 from SilviProtocol/latest
- `501c958` - Merge master into latest, resolved conflicts
- `23a2416` - Add large GeoJSON files to gitignore
- `8961e98` - Added native species by ecoregion endpoint

**Untracked Files**:
```
.claude/                              # Claude AI context
LOCAL_DEPLOYMENT_GUIDE.md             # Local setup guide (new)
research.md                           # AI research planning (475 lines)
scripts/                              # Utility scripts
treekipedia/backend/.env.example      # Backend config template
treekipedia_custom.dump               # Database dump (1.9GB)
```

**Modified Files**:
- `treekipedia/frontend/yarn.lock` - Dependency changes

---

## Production vs Local

### Production Endpoints
- **Frontend**: https://treekipedia.silvi.earth (Vercel)
- **API**: https://treekipedia-api.silvi.earth (Digital Ocean VM, PM2)
- **Backend Port**: 3000
- **Blockchain**: Base, Celo, Optimism, Arbitrum

### Local Endpoints
- **Frontend**: http://localhost:3000
- **API**: http://localhost:5001
- **Database**: localhost:5432
- **Blockchain**: Not configured (not needed for local dev)

### Database Sync Status
- ✅ **Full sync completed** from production (Digital Ocean)
- Dump size: 1.9GB compressed (8.5GB uncompressed)
- Method: `pg_dump -Fc` → `pg_restore`
- All 7 core tables + geospatial data imported successfully

---

## Development Workflow

### Starting Local Environment

```bash
# Terminal 1: Start PostgreSQL (if not auto-started)
brew services start postgresql@17

# Terminal 2: Start Backend
cd treekipedia/backend
node server.js
# Server running on http://localhost:5001

# Terminal 3: Start Frontend
cd treekipedia/frontend
npm run dev
# Frontend running on http://localhost:3000
```

### Checking Service Status

```bash
# Check running backend processes
lsof -i :5001

# Check PostgreSQL
psql treekipedia -c "SELECT COUNT(*) FROM species;"

# Check frontend
curl http://localhost:3000
```

### Database Access

```bash
# Connect to local database
psql treekipedia

# Useful queries
SELECT COUNT(*) FROM species;
SELECT COUNT(*) FROM geohash_species_tiles;
SELECT * FROM users;

# Check PostGIS
SELECT PostGIS_Version();
```

---

## Key File Locations

### Configuration
- [treekipedia/.env](treekipedia/.env) - Backend environment
- [treekipedia/frontend/.env.local](treekipedia/frontend/.env.local) - Frontend config
- [treekipedia/backend/.env.example](treekipedia/backend/.env.example) - Config template

### Database
- [treekipedia/database/current-schema.sql](treekipedia/database/current-schema.sql) - Schema definition
- [treekipedia/database/README.md](treekipedia/database/README.md) - Database docs

### Backend
- [treekipedia/backend/server.js](treekipedia/backend/server.js) - Express entry point
- [treekipedia/backend/controllers/species.js](treekipedia/backend/controllers/species.js) - Species API
- [treekipedia/backend/controllers/geospatial.js](treekipedia/backend/controllers/geospatial.js) - Spatial queries

### Frontend
- [treekipedia/frontend/app/page.tsx](treekipedia/frontend/app/page.tsx) - Root page
- [treekipedia/frontend/app/search/page.tsx](treekipedia/frontend/app/search/page.tsx) - Search UI
- [treekipedia/frontend/app/species/[taxon_id]/page.tsx](treekipedia/frontend/app/species/[taxon_id]/page.tsx) - Species detail

### Documentation
- [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md) - Setup instructions
- [treekipedia/API.md](treekipedia/API.md) - API documentation
- [treekipedia/TODO.md](treekipedia/TODO.md) - Development roadmap
- [treekipedia/CURRENT_STATE.md](treekipedia/CURRENT_STATE.md) - Project status
- [.claude/CLAUDE.md](.claude/CLAUDE.md) - AI assistant context

---

## Next Steps & Priorities

### Immediate (This Week)

1. **Fix Species Search** (30 min)
   - File: [backend/controllers/species.js](treekipedia/backend/controllers/species.js)
   - Change column from "species" to "species_scientific_name"
   - Test with `/species?search=oak`

2. **Validate All Endpoints** (1 hour)
   - Test each endpoint in [API.md](treekipedia/API.md)
   - Document any other schema mismatches
   - Create endpoint test suite

3. **Archive Backup Tables** (30 min)
   - Move `species_v7_backup`, `species_v8` to separate schema
   - Reduces confusion and database clutter

### Short Term (Next 2 Weeks)

1. **Database Optimization**
   - Add indexes on frequently queried fields
   - Monitor slow queries with logging
   - Optimize geohash tile queries

2. **Frontend Integration**
   - Complete native status cross-analysis
   - Add ecoregion filtering to analysis tool
   - Improve map performance with clustering

3. **Data Quality**
   - Validate AI vs human data distinction
   - Increase image coverage from 20% to 50%
   - Fill in missing geohash data for species

### Medium Term (Next Month)

1. **Apache Jena Integration** (per [research.md](research.md))
   - Evaluate Fuseki for semantic queries
   - Build ontology layer on top of PostgreSQL
   - Enable SPARQL endpoint for researchers

2. **AI Research Pipeline**
   - Batch process unresearched species
   - Implement local LLM support (Gemini, GPT-5, Grok)
   - Reduce OpenAI API costs

3. **User Engagement**
   - Gamification features
   - Contribution incentives
   - Mobile app or PWA

---

## Known Limitations

### Current Constraints

1. **API Keys Not Configured Locally**
   - OpenAI, Perplexity, Infura, Lighthouse
   - Impact: Cannot test research workflow or NFT minting locally
   - Workaround: Use production API for these features

2. **Blockchain Features Disabled**
   - No local testnet configured
   - Impact: Cannot test USDC payments or NFT minting
   - Workaround: Test on Base Sepolia testnet

3. **Geohash Data Gaps**
   - 29% of species lack occurrence data
   - Impact: Cannot analyze these species geographically
   - Solution: Import additional GBIF occurrence records

4. **Low Research Completion**
   - Only 0.03% of species have AI research (19 total)
   - Impact: Most species show empty research tabs
   - Solution: Batch process high-priority species

### Performance Considerations

1. **Large Geohash Table** (5.7M records)
   - Queries can be slow without proper indexing
   - Frontend map rendering may lag
   - Consider spatial index optimization

2. **Image Loading**
   - 31,796 external Wikimedia images
   - May have slow load times or broken links
   - Consider CDN or local caching

---

## Troubleshooting

### Common Issues

**Backend won't start on port 5000**:
```bash
# macOS ControlCenter uses port 5000
# Solution: Use port 5001 instead (already configured)
```

**Frontend can't connect to API**:
```bash
# Check .env.local points to correct backend
cat treekipedia/frontend/.env.local
# Should show: NEXT_PUBLIC_API_URL=http://localhost:5001

# Verify backend is running
curl http://localhost:5001/api
```

**PostgreSQL connection failed**:
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql

# Start if needed
brew services start postgresql@17

# Verify database exists
psql -l | grep treekipedia
```

**Geohash queries timeout**:
```bash
# Increase statement timeout
psql treekipedia -c "SET statement_timeout = '120s';"

# Or add to postgresql.conf
echo "statement_timeout = 120000" >> $(brew --prefix)/var/postgresql@17/postgresql.conf
```

### Getting Help

1. Check [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md) for setup issues
2. Review [treekipedia/API.md](treekipedia/API.md) for endpoint documentation
3. Check git history for recent changes: `git log --oneline -20`
4. Search [treekipedia/TODO.md](treekipedia/TODO.md) for planned fixes

---

## Summary

**Current State**: Treekipedia is fully deployed locally with production data. All core services are running and operational. One critical bug exists in the species search endpoint that must be fixed before production deployment. The database contains comprehensive species data (67,743 records) with strong geospatial coverage (5.7M occurrence tiles). Development focus should be on fixing the search bug, optimizing queries, and enriching species content through AI research.

**Health Score**: 7.2/10
- ✅ Strong: Database, geospatial features, architecture
- ⚠️ Medium: User engagement, image coverage, research completion
- ❌ Critical: Species search endpoint bug

**Next Action**: Fix species search endpoint in [backend/controllers/species.js](treekipedia/backend/controllers/species.js)

---

**Document Version**: 1.0
**Maintainer**: Development Team
**Last Sync**: October 18, 2025 (Production → Local)
