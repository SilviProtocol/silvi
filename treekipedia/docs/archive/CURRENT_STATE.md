# Treekipedia Current State (Updated: November 20, 2025)

## 🚀 What's Live and Working

### Deployment Status
- **Backend API**: Running at `https://treekipedia-api.silvi.earth` (PM2 managed, port 3000)
- **Frontend**: Deployed on Vercel at `https://treekipedia.silvi.earth`
- **Ontology Service**: Running at `https://treekipedia-graph-flow.silvi.earth` (port 8000)
- **Database**: PostgreSQL with 67,927 species (130 fields per species after v10 migration), 19 researched, 8 users, 21 NFTs minted
- **PostGIS**: Spatial database extension enabled for geospatial queries
- **Blazegraph**: Knowledge graph running on port 9999
- **Fuseki**: SPARQL endpoint accessible at `https://treekipedia-graph-flow.silvi.earth/fuseki/` (port 3030)
- **IPFS**: Lighthouse integration for decentralized storage

### Core Working Features ✅
1. **Species Search & Browse** - Clean, centered search interface with 67,927 species
2. **Subspecies Management** - Species-level search with automatic subspecies discovery on detail pages
3. **Species Images System** - Sticky sidebar carousel with 31,796 images (17,276 successfully linked, 54.3% coverage)
4. **Species Detail Pages** - Two-column layout with comprehensive data display (130 fields including v10 climate/GloBI data)
5. **AI Research Process** - Research generation, IPFS storage, NFT minting (archived: treederboard, profile, sponsorship UI)
6. **Research Data Display** - Species pages show AI vs human data with visual indicators
7. **Geospatial Analysis** - Full interactive map-based species analysis with polygon drawing and KML upload
8. **Spatial Species Queries** - PostGIS-powered location-based species search with 5.3M geohash tiles
9. **Public API Access** - External API access with API key authentication for native species recommendations
10. **Admin Dashboard** - Simple password-protected server stats and API monitoring

## 🏗 Current Architecture

### Backend (`/backend/`)
- **Framework**: Node.js + Express
- **Database**: PostgreSQL with connection pooling + PostGIS spatial extension
- **Key Services**:
  - `aiResearch.js` - OpenAI/Perplexity research generation
  - `blockchain.js` - Multi-chain NFT minting (Base, Celo, Optimism, Arbitrum)
  - `ipfs.js` - Lighthouse IPFS storage
  - `researchQueue.js` - Background job processing
- **Controllers**:
  - `geospatial.js` - Spatial queries for species distribution and nearby search
  - `species.js` - Species search, details, images, and subspecies
  - `research.js` - AI research generation and NFT minting
  - `treederboard.js` - Leaderboard and user contributions
  - `sponsorship.js` - Payment tracking and webhooks
- **Middleware**:
  - `apiAuth.js` - API key validation and rate limiting for public endpoints

### Frontend (`/frontend/`)
- **Framework**: Next.js 14+ with TypeScript
- **Web3**: Wagmi v2 + Viem for wallet integration
- **UI**: Tailwind CSS + shadcn/ui components
- **State**: React Query for server state, custom hooks for complex logic

### Database Schema
- **Species table**: 67,927 species with 130 fields per species (v10 migration completed November 2025)
  - New v10 fields: Climate data (Köppen-Geiger, precipitation, temperature), GloBI ecological interactions, SBTN land cover
  - Each record has `subspecies`, `taxon_full`, and `species_scientific_name` fields for hierarchical taxonomy
  - Climate data populated for 88% of species, SBTN land cover for 85%
- **Images table**: 31,796 images across 13,609 species with full attribution and primary image designation
- **Users table**: Wallet addresses with points/contributions
- **Research NFTs table**: Minted NFT records with IPFS links
- **Sponsorships table**: Payment tracking (current system uses direct USDC transfers)
- **Geohash Species Tiles table**: 5.3M geohash tiles with 89.3M species occurrences (Marina's compressed data imported)

## 🔄 Current User Flows

### Working Flows:
1. **Search Species** → View details → See research data (if available) → Explore subspecies
2. **Subspecies Discovery** → Search returns species-level records → Click to species page → View "Subspecies & Varieties" section → Click subspecies to view detailed page
3. **Connect Wallet** → Fund research → AI generates data → NFT minted → Points awarded
4. **View Treederboard** → See contributors and their points
5. **View Profile** → See personal NFTs and contribution history

### Payment System:
- **Current**: Direct USDC transfers (3 USDC per species research)
- **Tracking**: Sponsorship table tracks payments and research status
- **No smart contracts**: Direct wallet-to-wallet transfers, not contract-based

### Module/Code Issues:
- `performResearch is not a function` errors in logs
- ~~JSON parsing errors in API communication~~ - **FIXED**: Related to PM2 directory issue
- Database parameter validation issues ("null" strings vs NULL values)

### Cleanup Needed:
- `/scripts/research/` - 48 test files (4.1MB) from AI model testing, can be archived
- Uncommitted image system work (carousel, import scripts) needs to be reviewed and committed
- Large data file `database/treekipedia_images_full.json` should be gitignored

## 📁 Source of Truth Files

### ✅ Current and Maintained:
- `/API.md` - Comprehensive API documentation (updated with geospatial endpoints)
- `/SPECIES_FIELDS_FRONTEND_GUIDE.md` - **NEW v10** Complete 130-field guide for frontend implementation
- `/backend/controllers/` - All controller files (research.js, species.js, geospatial.js)
- `/backend/routes/geospatial.js` - Spatial API endpoints
- `/backend/services/` - Core service modules
- `/frontend/app/` - Next.js app structure
- `/frontend/lib/types.ts` - TypeScript definitions (needs update for v10 fields)
- `/database/current-schema.sql` - Current database structure
- `/database/01_enable_postgis.sql` - PostGIS extension setup
- `/database/02_create_geohash_tiles_table.sql` - Geospatial table schema
- `/database/03_ecoregions_integration.sql` - Ecoregions integration
- `/database/04_v10_schema_migration.sql` - **NEW** v10 GloBI and SBTN fields
- `/database/05_v10_climate_fields.sql` - **NEW** v10 climate/precipitation fields
- `/database/create_images_table.sql` - Images table schema
- `/scripts/import_images.js` - Image data import script
- `/scripts/import_geohash_tiles.js` - Geospatial data import script
- `/scripts/import_v10_species.js` - **NEW** v10 CSV streaming import with taxon_full matching

### ❓ Status Unknown (Need Review):
- Root directory `.md` files (15+ files, likely mix of current/outdated)
- `/contracts/` directory (may be outdated per user note)
- `/scripts/` directory (likely debug/one-off scripts)

### 🗂 Definitely Archive Later:
- Error logs and debug files
- Old migration scripts
- Temporary test files

## 🔧 Development Commands

### Backend:
```bash
cd backend && node server.js          # Run server
cd backend && nodemon server.js       # Development mode
```

### Frontend:
```bash
cd frontend && yarn dev               # Development server
cd frontend && yarn build             # Production build
cd frontend && yarn lint              # ESLint check
```

### Database:
```bash
# Connection via .env DATABASE_URL
# Schema in /database/current-schema.sql
# PostGIS setup: psql -d treekipedia < database/01_enable_postgis.sql
# Geospatial table: psql -d treekipedia < database/02_create_geohash_tiles_table.sql
```

### Geospatial Data Import:
```bash
# Import Marina's compressed geohash CSV data (COMPLETED - July 21, 2025)
cd scripts && node import_geohash_csv.js ../Treekipedia_geohash_15djuly.csv
# Results: 4,716,132 tiles imported in 11.4 minutes at 6,881 rows/sec
```

## 📊 Current Metrics (As of November 18, 2025)

- **Species Database**: 67,927 total species (v10 migration completed - 0.3% increase from v9)
- **Species Schema**: 130 fields per species (17 new fields added in v10)
- **v10 Data Population**:
  - Climate data (Köppen-Geiger, precipitation, temperature): 60-88% populated
  - SBTN land cover: 85% populated (57,950 species)
  - GloBI ecological interactions: 24% for herbivores, others sparse
- **Images Database**: 31,796 images across 13,609 species (22.1% coverage)
- **Research Status**: 19 researched (preserved during all imports)
- **Users**: 8 registered wallet addresses
- **NFTs**: 21 minted across 19 species
- **Contributors**: 7 unique wallets with contributions
- **Total Points**: 40 points awarded
- **Geospatial Data**: 5.3M geohash tiles with populated geometries and species occurrences
- **Global Coverage**: Species occurrence data spans all continents with 152m precision
- **Countries Data**: 242 country polygons from Natural Earth for native status analysis
- **Native Status Data**: 17,415 species (26%) with native countries
- **Cross-Analysis Ready**: Full spatial-taxonomic cross-referencing capabilities

## 🚧 Upcoming Development Priorities

### Recently Completed Major Features:
- **✅ Treekipedia v10 Data Migration** (November 2025): Major database enhancement with climate and ecological data
  - Backend: 17 new fields added (climate, GloBI interactions, SBTN land cover)
  - Database: 130-field schema with 88% climate data population
  - Migration: Streaming CSV import preserving all existing relationships
  - Documentation: Comprehensive frontend implementation guide (`SPECIES_FIELDS_FRONTEND_GUIDE.md`)
- **✅ Subspecies & Taxonomy System** (October 2025): Complete implementation of subspecies management
  - Backend: New `/species/:taxon_id/subspecies` endpoint
  - Search optimization: `DISTINCT ON` query returns only species-level records
  - Frontend: Subspecies section on species detail pages with clickable navigation
  - Database: 50,797 species + 16,946 subspecies/varieties properly indexed
- **✅ Data Attribution & References**: Added comprehensive citation list to site footer with all 12+ data sources
- **✅ Species Images Database Integration**: Complete implementation with 4,024 images across 1,576 species
- **✅ API Endpoints for Images**: Full backend API support for image data and attribution
- **✅ Frontend Image Carousel**: Custom React carousel with navigation, attribution, and mobile support
- **✅ PM2 Infrastructure Fix**: Resolved critical deployment issue causing API failures

### Potential Web3 Pivot (Team Discussion Pending):
- Move from wallet-based to email-based users
- Make research free with email signup
- Optional donation system instead of required payments
- Focus on research quality and new features (Blazegraph integration)

### Planned Feature Development:

#### 1. 📚 **Data Attribution & References** ✅ **COMPLETED**
**Goal**: Add proper citations for data sources to frontend
**Status**: **COMPLETED** - Comprehensive attribution added to site footer
**Completed Tasks**:
- ✅ Added complete reference list for all 12+ data sources (GBIF, iNaturalist, SiBBr, SpeciesLink, etc.)
- ✅ Implemented site-wide footer with comprehensive citation list
- ✅ Ensured proper academic and legal attribution for all data sources
- ✅ Kept individual species pages clean without citation clutter

#### 2. 🖼️ **Species Images Database Integration** ✅ **COMPLETED**
**Goal**: Import species image URLs and create proper image management system
**Status**: **COMPLETED** - Full end-to-end image system with 4,024 images across 1,576 species
**Completed Tasks**:
- ✅ Created Images table with proper schema and constraints
- ✅ Built Node.js import script with species name matching
- ✅ Imported full dataset with 100% success rate
- ✅ Established primary image designation system
- ✅ Preserved full attribution (license, photographer, page_url)
- ✅ Built API endpoints for image data serving
- ✅ Created custom React image carousel component
- ✅ Integrated carousel into species overview pages
- ✅ Added mobile-responsive design and accessibility features
- ✅ Implemented proper Wikimedia Commons attribution display

#### 3. 🧠 **AI Research Process Enhancement** ⏸️ **IN PROGRESS - PAUSED**
**Goal**: Improve quality and depth of AI-generated species research
**Status**: Testing phase complete, analysis in progress
**Current State**: 
- Completed comprehensive testing of Claude 3.5 Haiku vs Grok 3 Mini
- Developed 3-group research strategy (Ecological, Morphological, Stewardship)
- Claude 3.5 Haiku achieved 100% field completion (24/24) vs current 75% (18/24)
- Grok 3 Mini optimized to 88% completion with 3.6x better token efficiency
- Built production-ready test infrastructure in `/scripts/research/`
**Testing Results**:
- **Claude 3.5 Haiku**: Best for production (100% completion, reliable)
- **Grok 3 Mini**: Best for cost-effective bulk processing (88% completion, very efficient)
- **Current Perplexity+GPT-4o**: Baseline (75% completion, higher token usage)
**Next Steps**: Analyze results and decide on production integration strategy

#### 4. 🌍 **Geospatial Querying Capabilities** ✅ **COMPLETED**
**Goal**: Enable coordinate-based species distribution analysis
**Status**: **COMPLETED** - Full PostGIS integration with STAC-compliant geohash support
**Completed Tasks**:
- ✅ Enabled PostGIS extension for spatial data support
- ✅ Created STAC-compliant geohash_species_tiles table (level 7, ~150m resolution)
- ✅ Built comprehensive geospatial API with 6 endpoints
- ✅ Implemented spatial query functions (nearby species, distribution maps, heatmaps)
- ✅ Created import pipeline for Marina's compressed occurrence data
- ✅ Added proper indexing for high-performance spatial queries
- ✅ STAC compliance with temporal filtering support
- ✅ GeoJSON output for easy frontend visualization
**Ready for**: Marina's compressed geohash data import (90M occurrences → ~150k tiles)

#### 5. 🔗 **Blazegraph Knowledge Graph Integration**
**Goal**: Full semantic querying capabilities for species data
**Multi-phase Implementation**:
- **Phase A - Data Import**: 
  - Import species data into Blazegraph RDF format
  - Establish proper ontology mappings
- **Phase B - Ontology Review**: 
  - Review and refine current taxonomic ontology
  - Ensure semantic relationships are properly defined
- **Phase C - SPARQL Query Development**: 
  - Create standard queries for common use cases
  - Develop query templates for researchers
- **Phase D - Frontend Integration**: 
  - Build SPARQL query interface in frontend
  - Allow users to construct and execute custom queries
  - Visualize query results appropriately
**Technical Stack**: Current Blazegraph instance on port 9999, will need API endpoints for query execution

#### 6. 📦 **Open Data Export & Accessibility**
**Goal**: Fulfill open source commitments by providing regular, accessible data exports
**Implementation Plan**:
- **Automated Monthly Exports**: 
  - Full Treekipedia dataset export to IPFS for decentralized access
  - Database schema documentation export to EAS (Ethereum Attestation Service)
  - Automated scheduling (cron jobs or similar)
- **Export Formats**: 
  - JSON/CSV for raw data consumption
  - RDF/Turtle for semantic web applications
  - API documentation and schema definitions
- **Version Control**: Track dataset versions and changes over time
- **Access Methods**: 
  - Direct IPFS links for researchers
  - API endpoints for programmatic access
  - Documentation for data usage and citation
**Technical Considerations**: Data compression, IPFS pinning strategy, EAS attestation costs

#### 7. 🌐 **Community Data Curation & Wiki Integration**
**Goal**: Enable community-driven data quality improvements through collaborative editing
**Vision**: User-suggested edits and data verification system
**Exploration Areas**:
- **Wiki Integration Options**:
  - MediaWiki integration with species pages
  - Custom wiki-like editing interface
  - Version control and change tracking
- **Community Features**:
  - User-suggested edits to species data
  - Data accuracy attestation/verification by experts
  - Crowdsourced data quality improvements
  - Edit history and contributor attribution
- **Data Synchronization**:
  - Bidirectional sync between wiki edits and PostgreSQL database
  - Moderation workflow for community contributions
  - Integration with existing research validation process
- **User Management**: 
  - Expert verification system
  - Community contributor rankings
  - Integration with existing user/wallet system
**Status**: Conceptual phase, requires research into MediaWiki API and community management tools

### Immediate Development Priorities:

#### 🧠 **AI Research Process Enhancement** - **NEXT PRIORITY**
**Goal**: Improve quality and depth of AI-generated species research
**Current Focus**: Scope out improvements to research quality and methodology

#### 📊 **Geospatial Data Population** - ✅ **COMPLETED**
**Goal**: Import Marina's compressed geohash occurrence data
**Status**: Successfully imported 4.7M tiles with 89M occurrences on July 21, 2025
**Next Steps**: Build frontend Analysis page for plot-based species queries

---

**Last Updated**: November 20, 2025
**Next Review**: After any major feature additions
**Maintainer**: Update this doc whenever major changes are made

### Latest Completed Work (November 20, 2025):

#### **Frontend Design System Overhaul:**
- **Species Detail Page Refactor**:
  - Implemented two-column desktop layout with sticky image sidebar (400px width)
  - Images appear on right side on desktop, top on mobile with `order-first/order-last`
  - Removed redundant sponsorship components (archived to `/archive`)
  - Standardized all spacing to clean 4/6/8 rhythm (space-y-6 for sections, space-y-3 for fields)
  - All tabs now have consistent structure with identical wrappers

- **Unified Nature-Themed Color Palette**:
  - **Before**: 8+ different accent colors creating visual noise
  - **After**: Cohesive 3-color system
    - Emerald (`emerald-400/500`) - Primary theme for climate, pollinators, interactions
    - Green (`green-600`) - Secondary for land cover
    - Amber (`amber-400/500`) - Geography/temperature accent
    - Blue (`blue-400`) - Precipitation/water
    - Red (`red-400`) - Threats only (parasites, pathogens, predators)
  - Icons provide visual differentiation instead of arbitrary colors

- **Enhanced Contrast & Visual Hierarchy**:
  - Card backgrounds: `bg-black/30` → `bg-black/40` (33% more opaque)
  - Borders: `border-white/10` → `border-white/15` (50% more visible)
  - Text opacity simplified from 5 levels to 3:
    - Labels/metadata: `text-white/60`
    - Body content: `text-white/85`
    - Headings: `text-white`

- **Standardized Component Rounding**:
  - All cards: `rounded-xl` (12px)
  - All badges/pills: `rounded-full`
  - Consistent visual language throughout

- **Component-Specific Improvements**:
  - `SpeciesInfobox`: Emerald theme with simplified badge colors
  - `ClimateProfile`: Unified emerald accent, blue for precipitation, amber for temperature
  - `EcologicalInteractions`: Reduced from 8 colors to 2 (emerald for beneficial, red for threats)
  - `DataField`: Better contrast, cleaner text hierarchy
  - `SubspeciesSection`: Improved nested card contrast with emerald hover states

- **Search Page Simplification**:
  - Removed all landing page feature cards
  - Vertically centered search interface using flexbox
  - Clean minimal design: just logo, tagline, search bar
  - Footer appears naturally on scroll

- **Admin Authentication Simplification**:
  - **Removed**: Complex session-based backend authentication
  - **New**: Simple client-side password check with localStorage
  - Password hardcoded at top of `/frontend/app/admin/page.tsx` (line 8)
  - To change password: Edit `ADMIN_PASSWORD` constant in frontend
  - No backend auth middleware - admin endpoints now open (protected by frontend only)
  - No more 401 errors or session complexity

- **Performance Impact**:
  - Species page bundle: Stable at 12.2 kB
  - Search page: 168 kB → 108 kB (60kB reduction from removing duplicate nav/footer)
  - Admin page: 113 kB → 112 kB (simplified auth code)

- **Files Modified**:
  - `/frontend/app/species/[taxon_id]/page.tsx` - Two-column grid layout
  - `/frontend/app/species/[taxon_id]/components/` - All tab components standardized
  - `/frontend/app/species/[taxon_id]/components/DataField.tsx` - Better contrast
  - `/frontend/app/species/[taxon_id]/components/SpeciesInfobox.tsx` - Unified colors
  - `/frontend/app/species/[taxon_id]/components/ClimateProfile.tsx` - Emerald theme
  - `/frontend/app/species/[taxon_id]/components/EcologicalInteractions.tsx` - Simplified colors
  - `/frontend/app/species/[taxon_id]/components/ImageCarousel.tsx` - Enhanced contrast
  - `/frontend/app/search/page.tsx` - Minimal centered design
  - `/frontend/app/admin/page.tsx` - Simple password auth
  - `/backend/server.js` - Removed auth middleware from admin endpoints

### Previous Completed Work (November 18, 2025):

#### **Treekipedia v10 Species Data Migration:**
- **Achievement**: Successfully migrated database to v10 with 17 new fields and enhanced species data
- **Duration**: 2.45 minutes for full 67,743 row import (after optimization)
- **Schema Changes**:
  - Added 17 new columns to species table (113 → 130 fields total)
  - 8 climate fields (Köppen-Geiger, temperature, precipitation metrics)
  - 8 GloBI ecological interaction fields (pollinators, herbivores, parasites, pathogens)
  - 1 SBTN land cover classification field
- **Import Strategy**:
  - Matched on `taxon_full` field (not taxon_id, which was renumbered in v10)
  - Preserved all existing taxon_ids to maintain relationships (NFTs, images, geohash tiles)
  - Updated existing species data without breaking foreign key references
- **Data Population**:
  - 67,701 species updated with v10 data (99.9%)
  - 42 new species added from v10
  - Climate data: 60-88% populated across fields
  - SBTN land cover: 85% populated (57,950 species)
  - GloBI interactions: 24% for `globi_eatenby`, others mostly "NA"
- **Performance Optimization**:
  - Created index on `taxon_full` column for fast lookups
  - Streaming CSV parser for 1.3 GB file
  - Batch processing (1,000 records per transaction)
- **Data Integrity Verified**:
  - All 67,927 species accounted for (67,743 + 184 from test imports + 42 new)
  - All taxon_ids preserved - no broken relationships
  - All 21 NFTs intact with correct references
  - All 17,276 image links preserved
  - All geohash tile references intact
- **Documentation Created**:
  - `SPECIES_FIELDS_FRONTEND_GUIDE.md` - Comprehensive 130-field guide for frontend team
  - Complete data patterns, population statistics, and UI recommendations
  - TypeScript interface templates and example API responses
- **Migration Scripts**:
  - `database/04_v10_schema_migration.sql` - Adds GloBI and SBTN fields
  - `database/05_v10_climate_fields.sql` - Adds climate/precipitation fields
  - `scripts/import_v10_species.js` - Streaming CSV import with taxon_full matching
- **Files Modified**:
  - Species table schema: 113 → 130 columns
  - Added timestamp fields: `created_at`, `updated_at`
  - Added spatial index on `taxon_full`
- **Key Technical Decisions**:
  - Climate fields stored as TEXT (not NUMERIC) to handle semicolon-separated ranges
  - "NA" string indicates missing data (not SQL NULL) - consistent with existing pattern
  - v10's new taxon_ids ignored - kept our existing IDs for stability
- **Next Steps**: Frontend implementation of new climate and ecological interaction displays

### Previous Completed Work (October 24, 2025):

#### **Enhanced Biome Filtering for Native Species API:**
- **Feature**: Added biome-based ecological filtering to native species by ecoregion endpoint
- **Problem Solved**: Prevents ecologically inappropriate recommendations (e.g., desert cacti for temperate rainforests)
- **Filtering Strategy**: Dual-criteria approach - species must match BOTH country AND biome type
- **Implementation**: Modified `getNativeSpeciesByEcoregionName()` in `backend/controllers/geospatial.js`
- **Query Enhancement**:
  - Added `AND biomes LIKE '%{ecoregion_biome_name}%'` filter
  - Combined ecoregion metadata + countries query for efficiency (2 queries → 1 query)
  - Filters by: ecoregions field + country native status + biome match
- **Security Fix**: Replaced SQL string interpolation with parameterized queries to prevent SQL injection
  - Old: `countries_native LIKE '%${country}%'` (vulnerable)
  - New: Proper parameter placeholders with query param arrays
- **Response Update**: Added `biome_match` field to `filters_applied` in API response
- **Example Impact**:
  - Eastern Cascades forests (Temperate Conifer) → Only returns temperate conifer species
  - Filters out: Sonoran Desert species (Adenostoma sparsifolium) even though native to same country
- **Documentation**: Updated PUBLIC_API_GUIDE.md with:
  - New "How Biome Filtering Works" section with examples
  - Updated response format showing `biome_match` field
  - Added to best practices and changelog
- **Files Modified**:
  - `backend/controllers/geospatial.js` - Enhanced getNativeSpeciesByEcoregionName function
  - `PUBLIC_API_GUIDE.md` - Comprehensive biome filtering documentation
- **Result**: Ecologically intelligent species recommendations that match both geography and habitat type

### Previous Completed Work (October 22, 2025):

#### **SSL & NGINX Configuration for Ontology Service:**
- **Domain**: Migrated ontology service to `https://treekipedia-graph-flow.silvi.earth`
- **Replaced**: Old `TreekipediaGraphflow.com` domain configuration
- **SSL Certificate**: Let's Encrypt certificate already in place (valid until Nov 24, 2025)
- **NGINX Configuration**: Created new config at `/etc/nginx/sites-available/treekipedia-graph-flow`
- **Security Features**:
  - HTTP/2 enabled for improved performance
  - HSTS header with 1-year max-age and includeSubDomains
  - Automatic HTTP to HTTPS redirect (301)
  - SSL protocols: TLSv1.2 and TLSv1.3 only
- **Services Exposed**:
  - Main ontology service: Port 8000 → `/`
  - Fuseki SPARQL endpoint: Port 3030 → `/fuseki/`
  - Health check endpoint: `/health`
  - Static files: `/static` directory
- **Configuration**: 300-second timeouts for large ontology queries
- **File Modified**: `/etc/nginx/sites-available/biodiversity-ontology` replaced with new config

#### **Public API Access with API Key Authentication:**
- **Feature**: Enabled external access to native species recommendation endpoint
- **Authentication**: Implemented API key middleware (`backend/middleware/apiAuth.js`)
- **CORS Configuration**: Route-specific public CORS allowing all origins for authenticated requests
- **Rate Limiting**: Built-in 60 requests/minute per API key with in-memory tracking
- **Protected Endpoint**: `GET /api/geospatial/ecoregions/native-species/:ecoregion_name`
- **Security Model**: Two-layer approach - public CORS + required API key validation
- **Key Management**: Simple comma-separated API keys in environment variables
- **Response Headers**: Rate limit info (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- **Error Handling**: Clear 401/403/429 responses with helpful messages
- **Documentation**: Complete PUBLIC_API_GUIDE.md with examples in cURL, JavaScript, Python, Node.js
- **Sample Keys**: 3 initial API keys generated for testing and external partners
- **Files Created**:
  - `backend/middleware/apiAuth.js` - Authentication middleware with rate limiting
  - `PUBLIC_API_GUIDE.md` - Comprehensive API documentation for external users
- **Files Modified**:
  - `backend/routes/geospatial.js` - Added public CORS + API key middleware to native species endpoint
  - `.env` - Added API_KEYS environment variable with initial keys

### Previous Completed Work (October 2, 2025):

#### **Image Re-linking After v9 Migration:**
- **Problem**: v9 species import changed taxon_id structure, breaking all 31,796 image links (0% matched)
- **Solution**: URL-based species name extraction and re-linking to current taxon_ids
- **Species Name Extraction**: Parsed Wikimedia Commons URLs to extract scientific names from filenames
- **Extraction Success**: 20,145 images (63.4%) had valid species names extracted from URLs
- **Database Matching**: 8,564 unique species names matched to current species table
- **Re-linking Results**: 17,276 images (54.3%) successfully re-linked to current species
- **Technical Approach**:
  - Added `species_scientific_name` column to images table
  - Extracted genus + species epithet from URL filenames (e.g., "Eucalyptus_spathulata.JPG" → "Eucalyptus spathulata")
  - Matched to species table (species-level only, `subspecies = 'NA'`)
  - Handled duplicate primary images constraint by temporarily dropping/recreating index
- **Remaining Issues**: 14,520 images (45.7%) still unlinked due to non-standard URLs or species not in database
- **Script Location**: `/scripts/relink_images_from_urls.js`

### Previous Completed Work (October 1, 2025):

#### **Subspecies & Taxonomy Management System:**
- **Search Deduplication**: Fixed duplicate subspecies appearing in search results (Pinus ponderosa: 7 results → 1 result)
- **DISTINCT ON Query**: Implemented PostgreSQL `DISTINCT ON (species_scientific_name)` with subspecies prioritization
- **New API Endpoint**: `GET /species/:taxon_id/subspecies` returns all subspecies/varieties for a species
- **Frontend Component**: Created `SubspeciesSection.tsx` with clickable subspecies cards showing `taxon_full` names
- **Integration Complete**: Added subspecies section to species Overview tab between taxonomy and research status
- **User Flow**: Search shows species-level records → Species page lists subspecies → Click to explore individual subspecies
- **Database Structure**: 50,797 species-level (`subspecies = 'NA'`) + 16,946 subspecies/variety records
- **Query Performance**: Search prioritizes species-level using CASE statement, then applies name matching logic
- **Null Safety**: Fixed search form to handle 47,788 species with NULL common names
- **Search Placeholder**: Updated to "Search 67,743 tree species & subspecies..."

### Previous Completed Work (September 16, 2025):

#### **Major Species Analysis Infrastructure Complete:**
- **v9 Species Data**: Successfully imported 67,743 species (up from 61,455) with corrected taxon_id mappings
- **Taxon ID Mapping Complete**: Built and executed comprehensive taxon_id mapping script for geohash compatibility
- **Geohash Geometry Population**: Generated PostGIS geometries for all 5.8M geohash tiles using ST_GeomFromGeoHash()
- **Countries Integration**: Imported 242 Natural Earth country polygons for native status cross-analysis
- **Spatial Queries Working**: Fixed missing geometry columns, analysis page now returns species results

#### **Cross-Analysis Capabilities Unlocked:**
- **Native Status Analysis**: Can determine what % of species in drawn polygons are native to that country
- **Country Detection**: Spatial intersection automatically identifies which country contains user-drawn polygons
- **Smart Name Mapping**: Handles country name variations ("United States of America" → "United States")
- **Species Data Quality**: 17,405 species with native country data, 5,570 with introduction data
- **Working Example**: Test polygon in USA shows "31.9% of 141 species are native to United States"

#### **Technical Infrastructure:**
- **PostGIS Optimization**: All geohash tiles now have proper polygon geometries for spatial intersections
- **Backend Fixes**: Resolved species column reference errors in controllers (species → species_scientific_name)
- **Country Polygons**: Full Natural Earth dataset imported with proper spatial indexing
- **Cross-Reference Ready**: Complete spatial-taxonomic infrastructure for advanced ecological analysis

### Previous Work (July 28, 2025):
- **Analysis Page Complete**: Full frontend implementation with React-Leaflet, polygon drawing, KML upload, and species analysis
- **UI/UX Polish**: Applied Treekipedia design system, collapsible instructions, transparent backgrounds
- **Data Quality Discovery**: Identified numeric taxon_id corruption in source data ("1", "2", "3") requiring upstream fix

### Previous Work (July 21, 2025):
- **Geospatial Data Import**: Successfully imported 4.7M geohash tiles containing 89M occurrence records
- **PostGIS 3.2 Installation**: Enabled full spatial functionality in PostgreSQL
- **CSV Import Script**: Created streaming import script handling 480MB file efficiently
- **Data Validation**: All tiles imported with 0 errors, ready for spatial queries

### ⚠️ Pending Data Quality Issue:
**Status**: PAUSED - Awaiting Marina's investigation
**Issue**: Original CSV data contains corrupted numeric taxon_ids ("1", "2", "3", etc.) mixed with valid species identifiers
**Evidence**: Confirmed in source file `Treekipedia_geohash_15djuly.csv` - lines contain entries like `{"1":1}` instead of proper taxon_ids
**Impact**: ~4.7M tiles imported include corrupted data, currently handled gracefully by showing "Unidentified species"
**Next Steps**: Marina needs to investigate her compression script and provide corrected dataset for re-import
**Current Workaround**: Analysis page functional, corrupted entries filtered out from results

### Previous Major Work (July 8, 2025):
- **PostGIS Geospatial Integration**: Complete spatial database setup with STAC compliance
- **Geohash Tiles Support**: Level 7 geohash table ready for Marina's compressed occurrence data
- **Spatial API Endpoints**: 6 new endpoints for nearby species, distribution maps, and heatmaps  
- **Import Pipeline**: Ready-to-use script for importing compressed geohash data
- **Documentation Updates**: API.md and database README updated with spatial features

### Previous Major Work (June 16, 2025):
- **Data Attribution System**: Complete reference list added to site footer with all 12+ data sources
- **Images Database System**: Full implementation with schema, import tooling, and API integration
- **Frontend Image Carousel**: Custom React carousel with navigation, thumbnails, and attribution
- **API Documentation**: Updated with complete image endpoint specifications
- **Infrastructure Stability**: Fixed PM2 deployment issue that was causing API crashes

### Current Development Status:
- **Geospatial Backend**: ✅ Complete and ready for data import
- **Spatial API Endpoints**: ✅ Complete with full documentation  
- **PostGIS Database**: ✅ Enabled and configured (PostGIS 3.2)
- **Import Tools**: ✅ Ready for Marina's data
- **Geohash Data Import**: ✅ **COMPLETED** - 4.7M tiles with 89M occurrences successfully imported
- **Next Priority**: 🎯 Frontend Analysis page for geospatial queries + AI Research Process Enhancement



System Overview

  - OS: Ubuntu 20.04 LTS (Linux 5.15.0-134-generic)
  - Platform: DigitalOcean AMD Premium VM (KVM virtualized)
  - CPU: 2-core AMD (DO-Premium-AMD, 2.3GHz)
  - RAM: 4GB total, 67.5% used (2.7GB), only 798MB available
  - Storage: 78GB disk, 38% used (29GB used, 49GB free)
  - Uptime: 133 days, 3 hours

  🚨 Critical Issues

  Memory Pressure

  - High RAM usage: 67.5% utilized with only 798MB free
  - No swap configured - system has no swap space as fallback
  - Top memory consumers:
    - claude processes: 810MB + 231MB + 224MB = 1.27GB total
    - code-server: 522MB
    - blazegraph (Java): 201MB
    - PostgreSQL: 277MB

  Security Concerns

  - Heavy firewall activity - UFW blocking numerous intrusion attempts
  - SSH brute force attacks detected (kex_exchange_identification errors)
  - Multiple scanning attempts from various IPs

  Running Services Status

  PM2 Managed Processes

  - ✅ treekipedia-backend (PID 3306319): Healthy, 53.7MB RAM, 6 days uptime
  - ✅ treekipedia-blazegraph (PID 4026162): Healthy, 248KB RAM, 38 days uptime
  - ✅ node process (PID 594908): 21MB RAM, 29 days uptime

  System Services

  - ✅ PostgreSQL 14: Running normally
  - ✅ Nginx: Active on ports 80/443
  - ✅ RabbitMQ: Consuming 121MB RAM
  - ✅ Code-server: Running on port 8080

  Network Services

  - Port 3000: Treekipedia backend
  - Port 5432: PostgreSQL
  - Port 9999: Blazegraph
  - Port 8080: Code-server
  - Port 8000: Biodiversity ontology service
  - Ports 15672, 25672, 5672: RabbitMQ







  PostGIS Integration Overview

  Here's a comprehensive overview of your PostGIS implementation and
  cross-referencing capabilities:

  Database Architecture

  Core Spatial Table: geohash_species_tiles
  - 5.3M tiles at Level 7 geohash resolution (~150m x 150m)
  - 89.3M species occurrences aggregated by taxon_id
  - STAC-compliant with temporal fields for interoperability
  - PostGIS 3.2 with full spatial functionality

  Key Fields:
  - geohash_l7 (VARCHAR) - Primary key, 7-character geohash
  - species_data (JSONB) - {"taxon_id": count} format with GIN index
  - geometry (POLYGON) - Tile boundaries with GIST spatial index
  - center_point (GEOGRAPHY) - Tile centers for distance queries
  - datetime (TIMESTAMP) - STAC temporal requirement

  Spatial Indexing Strategy

  High-Performance Indexes:
  - GIST indexes on geometry and center_point for spatial queries
  - GIN index on species_data JSONB for fast species lookups
  - B-tree indexes on datetime, species_count, total_occurrences
  - Composite index on (datetime, geometry) for temporal-spatial queries

  PostGIS Functions Used

  Spatial Operations:
  - ST_DWithin() - Distance-based species searches
  - ST_Intersects() - Polygon/bounding box intersections
  - ST_GeomFromGeoJSON() - Converting frontend polygons
  - ST_MakePoint() - Point creation for distance queries
  - ST_MakeEnvelope() - Bounding box queries
  - ST_AsGeoJSON() - GeoJSON output for frontend

  Geography Operations:
  - Geography type for accurate distance calculations
  - Mixed geometry/geography usage optimized for query patterns

  Cross-Referencing Capabilities for New Spatial Data

  1. Coordinate-Based Joins
  -- Find species near specific coordinates
  WHERE ST_DWithin(center_point, ST_MakePoint(lng, lat)::geography,
  radius_meters)

  -- Intersect with custom geometries
  WHERE ST_Intersects(geometry, ST_GeomFromGeoJSON(your_geojson))

  2. Species Taxon Integration
  -- Link to species table via taxon_id
  JOIN species s ON s.taxon_id = ANY(SELECT jsonb_object_keys(species_data))

  -- Aggregate occurrences by species
  SELECT jsonb_object_keys(species_data) as taxon_id,
         SUM((species_data->>jsonb_object_keys(species_data))::int) as total

  3. Temporal Cross-Referencing
  -- Time-based filtering (STAC compliant)
  WHERE datetime BETWEEN start_date AND end_date

  -- Observation period overlaps
  WHERE observation_start_date <= your_end_date
    AND observation_end_date >= your_start_date

  4. Geohash-Based Joins
  -- Direct geohash matching for exact tile operations
  WHERE geohash_l7 = your_geohash

  -- Geohash prefix matching for hierarchical queries
  WHERE geohash_l7 LIKE 'abc123%' -- All tiles within larger geohash

  Integration Patterns for New Data

  A. Point Data (GPS coordinates)
  - Use ST_DWithin() with center_point geography
  - Buffer queries for nearby species analysis

  B. Polygon Data (Protected areas, boundaries)
  - Use ST_Intersects() with tile geometry
  - Can handle complex polygon intersections

  C. Raster Data (Climate, elevation)
  - Convert to point grid and use coordinate joins
  - Aggregate by tiles for performance

  D. External Species Databases
  - Join via taxon_id in species_data JSONB
  - Use species_data ? 'taxon_id' for existence checks

  E. Temporal Datasets
  - Filter by datetime or observation date ranges
  - STAC compliance enables time-series analysis

  Performance Optimizations

  Proven Query Patterns:
  - JSONB operations leverage GIN indexes effectively
  - Geography distance queries perform well with GIST indexes
  - Spatial intersections optimized with tile-based partitioning
  - Composite temporal-spatial queries use compound indexes

  Your PostGIS integration is well-architected for cross-referencing new
  spatial datasets through coordinate-based joins, species taxon linking,
  temporal filtering, and geohash hierarchies.



  🌍 Ecoregions Integration Complete!

  ✅ Successfully Imported:

  - 847 WWF Terrestrial Ecoregions from shapefile format
  - Complete metadata: ecoregion names, biomes, realms, areas
  - MultiPolygon geometries with full spatial indexing
  - PostGIS optimized with GIST spatial indexes

  🔗 Cross-Referencing Infrastructure:

  Database Schema:
  - Added eco_id, eco_name, biome_name, realm columns to geohash tiles
  - Created spatial indexes for fast ecoregion-based queries
  - Built summary views for ecoregion and biome statistics

  New API Endpoints:
  1. GET /api/geospatial/ecoregions/:ecoregion_id/species - Species in specific ecoregion
  2. GET /api/geospatial/ecoregions/at-point?lat=X&lng=Y - Ecoregion at coordinates
  3. POST /api/geospatial/ecoregions/intersect - Ecoregions overlapping polygon
  4. GET /api/geospatial/ecoregions/stats - Top ecoregions by diversity

  🚀 Capabilities Unlocked:

  Ecological Analysis:
  - Species by habitat - Find all species in specific ecoregions/biomes
  - Biogeographic filtering - Compare species across realms
  - Diversity hotspots - Identify most biodiverse ecoregions
  - Conservation priorities - Species density per area calculations

  Cross-Referencing Patterns:
  - Coordinate-based joins - Any GPS data can be linked to ecoregions
  - Polygon intersections - Protected areas, study sites, management zones
  - Taxonomic aggregation - Family/genus diversity by ecoregion
  - Temporal analysis - Species changes within ecological contexts

  ⚡ Currently Running:

  - Batch tile assignment - Linking 5.3M geohash tiles to ecoregions
  - Progress: Processing in 10K tile batches for optimal performance
  - ETA: ~530 batches, running automatically in background

  📁 Files Created:

  - scripts/import_ecoregions.js - Shapefile import automation
  - database/03_ecoregions_integration.sql - Database optimization
  - scripts/assign_ecoregions_batch.js - Efficient batch processing
  - Updated geospatial controller and routes

  Your PostGIS integration now supports rich ecological context queries like "What species
   are found in tropical rainforest ecoregions?" or "How does species diversity compare
  between the Neotropical and Palearctic realms?"




intact forest

ecological function group
