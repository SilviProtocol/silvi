# Treekipedia & Ontology-Generator Documentation
**Last Updated**: October 18, 2025
**Version**: Production + Local Development Environment

> **IMPORTANT**: For current deployment status, known issues, and immediate priorities, see [STATE.md](/STATE.md)

This repository contains two interconnected systems: **Treekipedia** (web platform for tree species knowledge) and **Ontology-Generator** (semantic knowledge graph builder).

---

## Current Environment Status

| Service | Status | Location | Details |
|---------|--------|----------|---------|
| **Local Backend** | ✅ Running | http://localhost:5001 | PostgreSQL 17 + PostGIS 3.6 |
| **Local Frontend** | ✅ Running | http://localhost:3000 | Next.js 15 dev server |
| **Local Database** | ✅ Synced | treekipedia (local) | 67,743 species, 5.7M geohash tiles |
| **Production API** | ✅ Live | https://treekipedia-api.silvi.earth | Digital Ocean VM |
| **Production Frontend** | ✅ Live | https://treekipedia.silvi.earth | Vercel deployment |

**Critical Known Issues**:
- ⚠️ Species search endpoint broken (`/species?search=X` returns 500 error - schema column mismatch in [controllers/species.js](treekipedia/backend/controllers/species.js))

---

## Project Overview

### Treekipedia
An open-source, AI-powered knowledge repository for tree species data combining:
- **Frontend**: Next.js 15.2.3 React application with Tailwind CSS 3.4.1
- **Backend**: Node.js/Express 4.21.2 REST API with PostgreSQL 17
- **Blockchain**: Smart contracts (Solidity) for payments (USDC) and NFT minting
- **Database**: PostgreSQL 17 with PostGIS 3.6 for geospatial analysis
- **Integration**: IPFS (Lighthouse) for storage, EAS for attestations
- **Deployment**: Base, Celo, Optimism, Arbitrum (production + testnets)

**Key Statistics**:
- 67,743 species records (50,797 species + 16,946 subspecies)
- 31,796 Wikimedia images with attribution
- 5,786,835 geohash occurrence tiles (L7 precision)
- 847 ecoregion polygons
- 6,819 intact forest landscape polygons

### Ontology-Generator
Python/Flask application for building RDF/OWL semantic ontologies:
- Imports data from Google Sheets
- Generates ontologies using OWLready2
- Publishes to Blazegraph SPARQL endpoint
- Automated update scheduling with version control

---

## Directory Structure

```
/treekipedia/
├── frontend/          # Next.js 15 + React 18 + Tailwind CSS
├── backend/           # Express.js REST API
├── contracts/         # Solidity smart contracts
├── database/          # PostgreSQL schema + migrations
├── scripts/           # Utility scripts
├── API.md             # Complete API documentation
└── README.md

/ontology-generator/
├── app.py             # Flask web application
├── generate_ontology.py        # Ontology generation engine
├── sheets_integration.py       # Google Sheets integration
├── automation_script.py        # Automated updates
├── ontology_config.json        # Ontology structure config
├── automation_config.json      # Automation settings
├── templates/         # HTML web interface
└── requirements.txt   # Python dependencies
```

---

## Frontend (`/treekipedia/frontend/`)

**Tech Stack**: Next.js 15.2.3, React 18.3.1, TypeScript, Tailwind CSS 3.4.1

### Key Technologies
- **Blockchain**: Wagmi 2.14.15, Viem 2.24.2, Ethers.js 6.13.5
- **State Management**: React Query (TanStack) 5.69.0
- **Maps**: Leaflet 1.9.4, React-Leaflet 5.0.0
- **UI**: Lucide React, Sonner (toasts), Next Themes
- **HTTP**: Axios 1.8.4

### Key Pages & Components

**Pages**:
- `app/page.tsx` - Home page
- `app/species/page.tsx` - Species list
- `app/species/[taxon_id]/page.tsx` - **Species detail page (core)**
  - 5 main tabs: Overview, Geographic, Ecological, Physical, Stewardship
  - Shows "researched" vs "unresearched" status
  - Displays AI vs human data with color-coding
  - Image carousel for species photos
  - Research funding card for unresearched species
- `app/treederboard/page.tsx` - Leaderboard and user profiles
- `app/analysis/page.tsx` - Cross-species analysis
- `app/admin/page.tsx` - Admin dashboard

**Key Components**:
- `SpeciesHeader.tsx` - Header with navigation
- `ResearchCard.tsx` - Sidebar with research status and funding
- `TabContainer.tsx` - Tab navigation system
- `DataField.tsx` - Reusable field display (handles AI/human data distinction)
- `tabs/*.tsx` - Individual tab content components
- `Map.tsx` - Leaflet distribution map

### Styling Conventions
- Dark mode with emerald green accents
- Card design: `bg-black/30 backdrop-blur-md border border-white/20`
- Headings: `text-emerald-300`
- Consistent rounded corners: `rounded-xl`
- See `STYLE_GUIDE.md` for complete design system

### Important Hooks
- `useSpeciesData()` - Fetch species details with React Query
- `useSpeciesImages()` - Load species photos
- `useResearchProcess()` - Handle research polling
- `useFieldDefinitions()` - Get field metadata

---

## Backend (`/treekipedia/backend/`)

**Tech Stack**: Express.js 4.21.2, Node.js, PostgreSQL 14+

### Main Routes

**Species**:
- `GET /species` - Search species by name
- `GET /species/suggest` - Autocomplete suggestions
- `GET /species/:taxon_id` - Get species details (115 fields)
- `GET /species/:taxon_id/images` - Get all images for species

**Research**:
- `GET /research/research/:taxon_id` - Get research data
- Research initiates via payment contract webhook

**User & Leaderboard**:
- `GET /treederboard` - Leaderboard
- `GET /treederboard/user/:wallet_address` - User profile & NFTs
- `PUT /treederboard/user/profile` - Update user display name

**Sponsorship**:
- `GET /sponsorships/transaction/:transaction_hash` - Check sponsorship status
- `POST /sponsorships/webhook` - Infura payment webhook (receives USDC payments)

**Geospatial**:
- `GET /api/geospatial/species/:taxon_id/distribution` - Distribution map
- `GET /api/geospatial/tiles/:geohash` - Species in geohash tile
- `GET /api/geospatial/tiles` - STAC-compliant temporal query
- `GET /api/geospatial/stats` - Geospatial statistics

### Research Process Workflow
1. User sponsors species (pays 3 USDC via payment contract)
2. Backend receives payment webhook
3. Backend calls OpenAI/Perplexity API to generate research
4. Results saved to `*_ai` fields in database
5. Results attested to EAS (on-chain)
6. NFT minted and given to sponsor
7. User points awarded on Treederboard

### Key Controllers
- `controllers/species.js` - Search and detail queries
- `controllers/research.js` - AI research integration
- `controllers/treederboard.js` - User management
- `controllers/sponsorship.js` - Payment handling
- `controllers/geospatial.js` - PostGIS queries

---

## Database (`/treekipedia/database/`)

**Database**: PostgreSQL 17.6 with PostGIS 3.6.0 extension

### 7 Core Tables

**1. species** (115 columns)
- Primary table with all tree species data
- **67,743 total records** (50,797 species + 16,946 subspecies/varieties)
- Dual fields: `field_ai` and `field_human` (human takes precedence)
- Key fields:
  - Taxonomy: taxon_id, species_scientific_name, family, genus, order, etc.
  - Ecology: habitat, elevation_ranges, conservation_status, threatened_status
  - Physical: growth_form, leaf_type, maximum_height, lifespan, bark_color
  - Geographic: countries_native, countries_introduced, ecoregions
  - Economic: uses, cultural_significance, timber_quality, commercial_species
  - Spatial: present_intact_forest (YES/NO/NA/YES;NO/NO;YES)
- Tracking: `researched` (NA/boolean), `verification_status`

**Important Data Notes**:
- 48,129 species have geohash occurrence data (geographic coordinates)
- 19,614 species lack occurrence data (mostly subspecies)
- Intact forest classification: 52.6% NO, 30.6% NO;YES, 9.4% NA, 6.0% YES;NO, 1.5% YES

**2. images** (30,000+ Wikimedia Commons images)
- Columns: id, taxon_id, image_url, license, photographer, page_url, source, is_primary
- One primary image per species
- Proper attribution and licensing info

**3. users**
- Columns: id, wallet_address, display_name, total_points, contribution_count

**4. contreebution_nfts**
- Records of all NFTs minted
- Columns: id, global_id, taxon_id, wallet_address, points, ipfs_cid, transaction_hash

**5. sponsorships**
- Payment transactions for research
- Status values: pending, confirmed, failed
- Columns: id, wallet_address, chain, transaction_hash, total_amount, payment_timestamp

**6. sponsorship_items**
- Individual species funded through sponsorships
- Research status: pending, researching, completed, failed

**7. geohash_species_tiles** (PostGIS)
- STAC-compliant species occurrence data
- Level 7 geohash tiles (~150m × 150m)
- Columns: geohash_l7, species_data (JSONB), geometry, datetime
- Enables distribution maps and heatmaps

### Key Database Features
- PostGIS for spatial queries
- Foreign key relationships with CASCADE
- Auto-update triggers for user points and sponsorship status
- STAC compliance for temporal data access

---

## Smart Contracts (`/treekipedia/contracts/`)

**Networks**: Base, Celo, Optimism, Arbitrum

### ResearchSponsorshipPayment.sol
- Handles USDC payments for research (3 USDC per species, 0.01 USDC for testing)
- Chain-specific USDC token addresses
- Events: SponsorshipReceived, MassSponsorshipReceived, FundsWithdrawn
- Emits webhook to backend on payment

### ContreebutionNFT.sol (ERC-721)
- Mints NFTs for research contributions
- Uses `global_id` from database as token ID
- Name: "Research Contreebution", Symbol: "treekipediaRSRCH"
- Validates to prevent duplicate token IDs
- Metadata stored on IPFS

---

## Ontology-Generator (`/ontology-generator/`)

**Tech Stack**: Python (Flask 2.3.3), OWLready2 0.34, Blazegraph SPARQL

### Key Files

**app.py**
- Flask web application entry point
- Handles file uploads and ontology generation
- Google Sheets integration
- Blazegraph import functionality
- Config: 32MB file size limit, 1-hour session expiry

**generate_ontology.py**
- Core ontology generation engine
- Loads CSV files using ontology configuration
- Creates RDF/OWL classes and properties
- Populates instances from data
- Exports to RDF/OWL format

**sheets_integration.py**
- Google Sheets API authentication and data reading
- Exports ontology data to sheets
- Service account credentials management

**automation_script.py**
- Monitors Google Sheets for changes
- Triggers regeneration on updates
- Automatically imports to Blazegraph
- Implements configurable scheduling (default 1 hour)
- Email notifications on completion

**config_automation.py**
- Automates detection of new spreadsheets
- Detects relationships between sheets
- Manages configuration backups

### Configuration Files

**ontology_config.json**
```json
{
  "base_classes": ["Species", "Ecosystem", ...],
  "annotation_properties": ["hasDescription", "hasDataSource"],
  "spreadsheet_files": [
    {
      "name": "species_data.csv",
      "type": "class",
      "class_type": "Species"
    }
  ]
}
```

**automation_config.json**
- `check_interval`: 3600 seconds (1 hour)
- `spreadsheet_ids`: List of Google Sheets to monitor
- `blazegraph_endpoint`: SPARQL endpoint URL
- `auto_update_version`: Enable version incrementing

### Workflow

**Manual Generation**:
1. User uploads CSV files via web interface
2. App processes CSVs with ontology configuration
3. Generates RDF/OWL ontology
4. Optionally imports to Blazegraph

**Automated Updates**:
1. Monitors configured Google Sheets for changes
2. On change: regenerates ontology, updates Blazegraph, increments version
3. Sends notification email
4. Repeats at configured interval

---

## Data Flow & Architecture

### Research Process
```
User Fund (3 USDC) → Payment Contract → Backend Webhook → AI Research
→ Save to database (*_ai fields) → EAS Attestation → IPFS Pin
→ NFT Mint → Points Awarded → Display on Treederboard
```

### Species Data Display
```
Database (species table) → API (/species/:taxon_id)
→ Frontend useSpeciesData() hook → Species Page
→ Human data shown preferentially (green accent)
→ AI data shown if no human data (blue accent)
```

### Geospatial Queries
```
PostGIS geohash_species_tiles table
→ Backend /api/geospatial/* endpoints
→ Frontend Map component (Leaflet)
→ Display distribution + heatmap overlay
```

---

## Important Conventions

### Naming
- **Database**: snake_case tables/columns, `field_ai`/`field_human` for dual data
- **Frontend**: PascalCase components, camelCase hooks (useXxx pattern)
- **API**: RESTful resource-oriented design, camelCase query params

### Status Values
- **Sponsorship**: pending, confirmed, failed
- **Research**: pending, researching, completed, failed
- **Data Source**: AI data (`*_ai`), Human data (`*_human`), Legacy data (`field`)

### Color Coding
- **AI Data**: Blue/emerald-300
- **Human Data**: Green/emerald-400
- **Unresearched**: Gray (pending status)

---

## File References

### Critical Files for Development

**Frontend**:
- `frontend/STYLE_GUIDE.md` - Complete UI/UX design system
- `frontend/app/layout.tsx` - App structure and providers
- `frontend/app/species/[taxon_id]/page.tsx` - Species page implementation
- `frontend/app/providers.tsx` - Context setup (React Query, themes)

**Backend**:
- `backend/server.js` - Express setup and route definitions
- `backend/controllers/species.js` - Species queries
- `backend/controllers/research.js` - AI research integration
- `backend/models/species.js` - Database queries

**Database**:
- `database/README.md` - Comprehensive schema documentation
- `database/current-schema.sql` - Current schema definition
- `database/01_enable_postgis.sql` - PostGIS setup

**API**:
- `treekipedia/API.md` - Complete API endpoint documentation

**Ontology**:
- `ontology-generator/ontology_config.json` - Ontology structure

---

## Development Patterns

1. **Data Precedence**: Human data > AI data > Legacy data in display
2. **Dual Sourcing**: All researchable fields have `_ai` and `_human` variants
3. **Component Composition**: Reusable components with single responsibility
4. **React Query Caching**: Frontend manages server state efficiently
5. **Polling Pattern**: Frontend polls research status with exponential backoff
6. **STAC Compliance**: Geospatial data follows Spatiotemporal Asset Catalog
7. **Event-Driven Backend**: Webhook-based payment processing

---

## Security & Best Practices

- Environment variables for sensitive data (.env files)
- Wallet address validation before blockchain transactions
- CORS configuration for frontend-backend communication
- IPFS CID validation for data integrity
- Rate limiting on API endpoints
- Service account credentials for Google API access
- EAS attestations for on-chain verification

---

## Quick Commands

### Frontend Development
```bash
cd treekipedia/frontend
npm install
npm run dev  # http://localhost:3000
```

### Backend Development
```bash
cd treekipedia/backend
npm install
node server.js  # http://localhost:5001 (changed from 5000 due to macOS ControlCenter)
```

### Local Database Access
```bash
# Connect to local PostgreSQL
psql treekipedia

# Useful queries
SELECT COUNT(*) FROM species;  # Should return 67,743
SELECT COUNT(*) FROM geohash_species_tiles;  # Should return 5,786,835
SELECT PostGIS_Version();  # Should show 3.6.0
```

### Ontology-Generator
```bash
cd ontology-generator
pip install -r requirements.txt
python app.py  # http://localhost:5000
```

---

## Additional Resources

- **Current state & issues**: [STATE.md](../STATE.md) - Comprehensive status document
- **Local deployment guide**: [LOCAL_DEPLOYMENT_GUIDE.md](../LOCAL_DEPLOYMENT_GUIDE.md) - Setup instructions
- **API documentation**: [treekipedia/API.md](../treekipedia/API.md) - Complete endpoint reference
- **Extended project docs**: [treekipedia/TREEKIPEDIA_EXTENSIVE.md](../treekipedia/TREEKIPEDIA_EXTENSIVE.md)
- **Frontend style guide**: [treekipedia/frontend/STYLE_GUIDE.md](../treekipedia/frontend/STYLE_GUIDE.md)
- **Database schema**: [treekipedia/database/README.md](../treekipedia/database/README.md)
- **Development roadmap**: [treekipedia/TODO.md](../treekipedia/TODO.md)
- **Research planning**: [research.md](../research.md) - Local LLM integration plans

---

## Recent Discoveries & Important Notes (Oct 2025)

### Database Investigation Findings

**Species Count Clarification**:
- Total records: 67,743 (NOT 67k species + 16k subspecies)
- Breakdown: 50,797 species-only + 16,946 subspecies/varieties = 67,743
- Unique species names: 50,922

**Geohash Coverage Analysis**:
- 48,129 species have occurrence data in geohash tiles
- 19,614 species lack occurrence data:
  - 16,862 are subspecies (86% of missing records)
  - 2,752 are species-level records without geographic data
- **Why subspecies are missing**: Occurrence data typically uses species-level taxon_ids, not subspecies-level

**Intact Forest Classification Breakdown**:
```
NO (not in intact forest):     35,613 species (52.6%)
NO;YES (in both):               20,729 species (30.6%)
NA (no data):                    6,366 species (9.4%)
YES;NO (in both):                4,042 species (6.0%)
YES (only in intact forest):       993 species (1.5%)
```
- **Why "NA" exists**: Species without geographic occurrence data cannot be spatially analyzed against intact forest polygons
- This is valid data representation, not a bug

### Critical Bugs to Fix

**1. Species Search Endpoint Broken** (HIGH PRIORITY)
- **File**: [treekipedia/backend/controllers/species.js](../treekipedia/backend/controllers/species.js) ~line 25
- **Issue**: Queries non-existent column "species"
- **Actual columns**: `species_scientific_name`, `accepted_scientific_name`
- **Impact**: `/species?search=oak` returns 500 Internal Server Error
- **Fix**: Update WHERE clause to use correct column names

### Local Development Environment Notes

**Port Configuration**:
- Backend runs on port **5001** (not 5000)
- Reason: macOS ControlCenter uses port 5000 by default
- Frontend configured to connect to http://localhost:5001

**Database Sync Status**:
- ✅ Full production sync completed (Oct 18, 2025)
- Source: Digital Ocean VM (167.172.143.162)
- Method: pg_dump -Fc → pg_restore
- Size: 1.9GB compressed, 8.5GB uncompressed

**API Keys Not Required for Local Dev**:
- OpenAI, Perplexity: Only needed for AI research workflow
- Infura, Lighthouse: Only needed for blockchain/IPFS features
- Local development works without these for most features

### Development Priorities

**Immediate (This Week)**:
1. Fix species search endpoint
2. Test all API endpoints
3. Archive backup database tables

**Short Term (2 Weeks)**:
1. Add database indexes on frequently queried fields
2. Complete native status cross-analysis frontend
3. Optimize geohash tile queries

**Medium Term (1 Month)**:
1. Evaluate Apache Jena/Fuseki integration (see [research.md](../research.md))
2. Implement batch AI research for unresearched species
3. Increase image coverage from 20% to 50%+

---

## Quick Reference

**Local Services**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5001
- Database: localhost:5432 (treekipedia)

**Production Services**:
- Frontend: https://treekipedia.silvi.earth
- API: https://treekipedia-api.silvi.earth

**Common Commands**:
```bash
# Check PostgreSQL status
brew services list | grep postgresql

# Check backend process
lsof -i :5001

# Database query
psql treekipedia -c "SELECT COUNT(*) FROM species;"

# View git status
git status

# View recent commits
git log --oneline -10
```

---

**Document maintained by**: Development Team
**For current status**: See [STATE.md](../STATE.md)
**For setup instructions**: See [LOCAL_DEPLOYMENT_GUIDE.md](../LOCAL_DEPLOYMENT_GUIDE.md)
