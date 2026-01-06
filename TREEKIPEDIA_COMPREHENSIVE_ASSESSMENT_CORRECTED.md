# Treekipedia Comprehensive Assessment & Google Earth Engine Integration Strategy

**CORRECTED VERSION**

**Date**: October 26, 2025
**Version**: 1.1 (Corrected)
**Author**: AI Architecture Assessment Team
---

## Executive Summary

## Executive Summary

Treekipedia has evolved from its conceptual vision into a functional platform with substantial infrastructure in place. The repository contains a sophisticated multi-tier architecture combining a Next.js 15 frontend, Express.js backend with PostGIS spatial capabilities, and PostgreSQL database with 67,743 species records and 5.7M geohash tiles. While the core platform is operational, significant gaps exist between the documented vision and actual implementation, particularly in AI research capabilities, blockchain integration, and advanced ecological modeling.

This assessment identifies these gaps and presents a comprehensive strategy for integrating Google Earth Engine's AlphaEarth embeddings to extract species-level environmental signatures. The proposed pipeline will process 67,743 species using their occurrence data to generate 256 new knowledge fields per species (mean, std dev, 10th, and 90th percentiles across 64 embedding bands), enabling advanced ecological AI applications.

- **Frontend**: Next.js 15 with comprehensive admin portal for GraphFlow management
- **Backend**: Express.js with admin API routes proxying to Python microservice
- **Python Microservice**: Flask API (port 5002) providing GraphFlow functionality
- **GraphFlow System**: Full OWL/RDF ontology generation and PostgreSQL→Fuseki sync
- **Database**: PostgreSQL 17 + PostGIS 3.6 with 67,743 species and 5.7M geohash tiles
- **Knowledge Graph**: Apache Fuseki RDF triple store with SPARQL capabilities


This assessment provides:
1. Inventory of actual capabilities 
2. Analysis of database schema and geospatial systems
3. Strategy for Google Earth Engine AlphaEarth embedding integration
4. Implementation roadmap for species-level environmental signatures

---

## 1. Current Capabilities Inventory

### 1.1 Frontend Features (Next.js 15.2.3 + React 18.3.1)

**Implemented Components:**

**Core Platform**:
- **Species Pages**: Detail views at `/species/[taxon_id]` with 115-field display
- **Interactive Analysis Map**: Leaflet-based mapping with polygon drawing
- **Heatmap Visualization**: Using leaflet.heat for occurrence density
- **Treederboard**: User leaderboard system for contributions
- **Search Interface**: Species search functionality

**Admin Portal** (`app/admin/`) - **FULLY IMPLEMENTED**:
- **Dashboard** (`/admin/page.tsx`): System status monitoring for PostgreSQL, Fuseki, GraphFlow modules
- **Species Sync** (`/admin/sync/page.tsx`): PostgreSQL → Fuseki synchronization with real-time progress
- **SPARQL Query Editor** (`/admin/sparql/page.tsx`): Interactive query interface with examples
- **CSV Upload** (`/admin/upload/page.tsx`): Ontology generation from uploaded files
- **Google Sheets Import** (`/admin/sheets/page.tsx`): Import biodiversity data from Google Sheets
- **System Monitor** (`/admin/monitor/page.tsx`): Health monitoring and diagnostics
- **Version Control** (`/admin/versions/page.tsx`): Ontology version management

**Admin Components**:
- `StatusCard.tsx`: Service status display (PostgreSQL, Fuseki, GraphFlow)
- `DataTable.tsx`: Tabular data display with sorting/filtering
- `ProgressBar.tsx`: Real-time sync progress visualization
- `FileDropzone.tsx`: Drag-and-drop file upload component

**Technology Stack:**
```json
{
  "framework": "Next.js 15.2.3",
  "ui": "Tailwind CSS 3.4.1",
  "state": "@tanstack/react-query 5.69.0",
  "maps": "leaflet 1.9.4 + react-leaflet 5.0.0",
  "blockchain": "wagmi 2.14.15 + viem 2.24.2 + ethers 6.13.5",
  "icons": "lucide-react"
}
```

### 1.2 Backend API Endpoints (Express.js 4.21.2)

**Operational Endpoints:**

**Species Endpoints**:
```javascript
GET /species                    // Search (⚠️ broken - schema column mismatch)
GET /species/suggest            // Autocomplete functionality
GET /species/:taxon_id          // Species details (115 fields)
GET /species/:taxon_id/images   // Species images
```

**Geospatial Endpoints** (PostGIS-powered):
```javascript
GET /api/geospatial/species/:taxon_id/distribution  // Distribution map
GET /api/geospatial/tiles/:geohash                  // Species in geohash
GET /api/geospatial/tiles                           // STAC-compliant temporal query
GET /api/geospatial/stats                           // Spatial statistics
GET /api/geospatial/species-nearby                  // Find species near location
GET /api/geospatial/occurrence-heatmap              // Heatmap for bounding box
GET /api/geospatial/ecoregions/boundaries           // Ecoregion polygons
GET /api/geospatial/intact-forests/boundaries       // Intact forest polygons
GET /api/geospatial/heatmap                         // Advanced heatmap endpoint
```

**Admin/GraphFlow Endpoints** (`routes/admin.js`) - **FULLY IMPLEMENTED**:
```javascript
// Health & Status
GET /api/admin/health                    // Python service health check
GET /api/admin/status                    // PostgreSQL, Fuseki, GraphFlow status
GET /api/admin/status/fuseki             // Detailed Fuseki statistics

// Sync Operations
POST /api/admin/sync/species             // Full species sync (SSE stream)
POST /api/admin/sync/incremental         // Incremental sync (new/updated only)

// Ontology Generation
POST /api/admin/ontology/generate        // Generate from CSV files (multipart)
POST /api/admin/ontology/from-sheets     // Generate from Google Sheets

// SPARQL
POST /api/admin/sparql/query             // Execute SPARQL query

// Version Management
GET /api/admin/versions                  // List ontology versions
POST /api/admin/versions/create          // Create version snapshot
```

**Research & Sponsorship** (Partially Implemented):
```javascript
GET /research/research/:taxon_id         // Get research data
GET /sponsorships/transaction/:hash      // Check payment status
POST /sponsorships/webhook               // Infura payment webhook
```

**User Management**:
```javascript
GET /treederboard                        // Leaderboard
GET /treederboard/user/:wallet_address   // User profile
PUT /treederboard/user/profile           // Update display name
```

**Critical Bug Identified:**
```javascript
// File: controllers/species.js line ~25
// Issue: Queries non-existent column "species"
// Should use: "species_scientific_name" or "accepted_scientific_name"
// Impact: /species?search=oak returns 500 Internal Server Error
```

### 1.3 Python Microservice (Flask - Port 5002) - **NEWLY DOCUMENTED**

**Purpose**: Headless Python backend providing GraphFlow functionality that cannot be replicated in Node.js.

**Architecture**:
```
Express Backend (port 5001)
        ↓ HTTP proxy
Python Microservice (port 5002) - Internal only, NOT public
        ↓ Imports GraphFlow modules
GraphFlow System (silvi-open-graphflow/)
        ↓ RDF/SPARQL
Apache Fuseki (port 3030)
```

**Key File**: `treekipedia/python-microservice/api_only.py` (395 lines)

**Capabilities**:
1. **OWL/RDF Ontology Generation** (owlready2, rdflib)
2. **PostgreSQL → Fuseki Synchronization** (batch processing, 67K species)
3. **Google Sheets Integration** (gspread, OAuth)
4. **SPARQL Query Execution** (requests to Fuseki)
5. **Server-Sent Events** (real-time progress streaming)

**API Endpoints** (internal, not public):
```python
# Health & Status
GET /api/health                  # Microservice health check
GET /api/status                  # Test PostgreSQL + Fuseki connections
GET /api/status/fuseki           # Triple count and graph stats

# Sync Operations
POST /api/sync/species           # Full sync (returns SSE stream)
POST /api/sync/incremental       # Incremental sync since timestamp

# Ontology Generation
POST /api/ontology/generate      # From CSV files (multipart/form-data)
POST /api/ontology/from-sheets   # From Google Sheets (spreadsheetId)

# SPARQL
POST /api/sparql/query           # Execute SPARQL query

# Version Management
GET /api/versions                # List versions
POST /api/versions/create        # Create snapshot
```

**Dependencies**:
```python
Flask==2.3.3              # Web framework
psycopg2-binary==2.9.9    # PostgreSQL connection
requests==2.31.0          # HTTP client for Fuseki
flask-cors==4.0.0         # CORS (localhost only)
owlready2==0.34           # OWL ontology manipulation (critical)
rdflib==7.0.0             # RDF triple generation (critical)
gspread==5.12.0           # Google Sheets API (critical)
pandas==2.1.4             # Data processing
numpy==1.26.2             # Numerical operations
```

**Security**:
- CORS restricted to `http://localhost:5001` and `http://localhost:3000`
- Internal service only (NOT exposed to public internet)
- File upload limit: 32MB
- Accessed exclusively by Express backend

**Performance**:
- Full sync: 20-30 minutes for 67,743 species
- Batch size: 1000 species per batch
- Memory usage: ~500MB peak
- Output: ~6.7M RDF triples (100 triples per species)

### 1.4 GraphFlow System (`graphflow-extracted/silvi-open-graphflow/`) - **NEWLY DOCUMENTED**

**Purpose**: Complete OWL/RDF ontology generation and knowledge graph management system.

**Core Modules**:

**1. PostgreSQL → Fuseki Sync** (`postgres_to_fuseki_sync.py` - 740 lines):
```python
class PostgreSQLFusekiSync:
    """Sync PostgreSQL data to Apache Jena Fuseki"""

    # Key Methods:
    - test_postgres_connection() → (bool, str)
    - test_fuseki_connection() → (bool, str)
    - get_postgres_tables() → List[Dict]
    - get_table_data(table_name, limit) → List[Dict]
    - convert_table_to_rdf(table_name, data) → str  # N-Triples format
    - upload_rdf_to_fuseki(rdf_content, graph_uri) → (bool, str)
    - sync_table_to_fuseki(table_name, batch_size) → Dict
    - run_full_sync(tables_to_sync, batch_size) → Dict
```

**Features**:
- Batch processing with configurable batch size
- Temporal pagination using primary keys
- RDF N-Triples generation with proper escaping
- Graph URI organization (per-table, per-batch)
- Connection health checking
- Progress logging and error handling
- Resume capability for failed syncs

**2. Multi-Sheet Biodiversity Ontology Generator** (`multi_sheet_biodiversity_generator.py` - 560 lines):
```python
class MultiSheetBiodiversityOntologyGenerator:
    """Generate biodiversity ontologies from CSV/Google Sheets"""

    # Key Methods:
    - detect_field_patterns(data) → Dict  # 120+ biodiversity patterns
    - infer_relationships(sheets) → List[Tuple]
    - generate_ontology(data, config) → OWL
    - assess_quality(ontology) → float  # Quality score 0-1
    - export_to_rdf(ontology, format) → str
```

**Field Detection Patterns** (120+ patterns):
- Taxonomic: scientific_name, family, genus, order, class, phylum, kingdom
- Geographic: countries, ecoregions, biomes, elevation, latitude, longitude
- Conservation: IUCN status, threatened status, endemic status
- Ecological: habitat, diet, pollinator, dispersal mechanism
- Physical: growth form, leaf type, bark color, maximum height
- Economic: uses, timber quality, commercial value
- Cultural: cultural significance, traditional uses

**3. Incremental Species Sync** (`incremental_species_sync.py` - 480 lines):
```python
class IncrementalSpeciesSync:
    """Sync only new/updated species since timestamp"""

    # Key Methods:
    - get_updated_species(since_timestamp) → List[Dict]
    - sync_new_species(since_timestamp) → Dict
    - track_sync_history() → None
```

**4. Google Sheets Integration** (`sheets_integration.py` - 200 lines):
```python
# Service account authentication
# OAuth2 credential management
# Read/write operations
# Batch data retrieval
```

**5. Configuration Files**:
- `fuseki_config.json`: Fuseki endpoints and PostgreSQL connection
- `.env`: Environment variables (FUSEKI_BASE_URL, POSTGRES_HOST, etc.)

**Total GraphFlow Code**: ~3,700 lines of critical Python code that MUST stay in Python (no JavaScript alternatives exist for owlready2, rdflib core functionality).

### 1.5 Database Schema (PostgreSQL 17 + PostGIS 3.6)

**Core Tables:**

**1. species** (67,743 records, 115 columns):
```sql
-- Primary Key
taxon_id BIGINT PRIMARY KEY

-- Taxonomy
species_scientific_name VARCHAR(255)
accepted_scientific_name VARCHAR(255)
family VARCHAR(100)
genus VARCHAR(100)
species VARCHAR(100)
subspecies VARCHAR(100)  -- 16,946 records with subspecies

-- Ecology
habitat TEXT
elevation_ranges TEXT
conservation_status VARCHAR(50)  -- IUCN Red List
threatened_status VARCHAR(50)

-- Physical Characteristics
growth_form VARCHAR(100)
leaf_type VARCHAR(50)
maximum_height VARCHAR(50)
lifespan TEXT
bark_color TEXT

-- Geographic
countries_native TEXT
countries_introduced TEXT
ecoregions TEXT

-- Geospatial Analysis
present_intact_forest VARCHAR(10)  -- YES/NO/NA/YES;NO/NO;YES

-- Economic/Cultural
uses TEXT
cultural_significance TEXT
timber_quality VARCHAR(50)
commercial_species VARCHAR(10)

-- Research Status
researched VARCHAR(10)  -- NA/true/false
verification_status VARCHAR(50)

-- AI vs Human Data (dual fields pattern)
field_ai TEXT
field_human TEXT
-- Human data takes precedence in display
```

**Data Statistics**:
- Total species records: 67,743
  - Species-only: 50,797
  - Subspecies/varieties: 16,946
- Species with geohash data: 48,129 (71%)
- Species without geohash data: 19,614 (29%, mostly subspecies)
- Intact forest classification:
  - NO (not in intact forest): 35,613 (52.6%)
  - NO;YES (in both): 20,729 (30.6%)
  - NA (no spatial data): 6,366 (9.4%)
  - YES;NO (in both): 4,042 (6.0%)
  - YES (only in intact forest): 993 (1.5%)

**2. images** (31,796 records):
```sql
id SERIAL PRIMARY KEY
taxon_id BIGINT REFERENCES species(taxon_id)
image_url TEXT
license VARCHAR(100)
photographer VARCHAR(255)
page_url TEXT
source VARCHAR(50)
is_primary BOOLEAN
```

**3. users**:
```sql
id SERIAL PRIMARY KEY
wallet_address VARCHAR(42) UNIQUE
display_name VARCHAR(100)
total_points INTEGER
contribution_count INTEGER
```

**4. contreebution_nfts**:
```sql
id SERIAL PRIMARY KEY
global_id INTEGER UNIQUE  -- Used as NFT token ID
taxon_id BIGINT REFERENCES species(taxon_id)
wallet_address VARCHAR(42)
points INTEGER
ipfs_cid TEXT
transaction_hash VARCHAR(66)
```

**5. sponsorships**:
```sql
id SERIAL PRIMARY KEY
wallet_address VARCHAR(42)
chain VARCHAR(20)
transaction_hash VARCHAR(66)
total_amount NUMERIC(20, 6)
payment_timestamp TIMESTAMP
status VARCHAR(20)  -- pending, confirmed, failed
```

**6. sponsorship_items**:
```sql
id SERIAL PRIMARY KEY
sponsorship_id INTEGER REFERENCES sponsorships(id)
taxon_id BIGINT REFERENCES species(taxon_id)
research_status VARCHAR(20)  -- pending, researching, completed, failed
```

**7. geohash_species_tiles** (5,786,835 records):
```sql
geohash_l7 VARCHAR(7) PRIMARY KEY  -- Level 7 geohash (~153m × 153m)
species_data JSONB  -- { "taxon_id": count, ... }
geometry GEOMETRY(Point, 4326)  -- PostGIS spatial index
datetime TIMESTAMP  -- For STAC compliance
```

**PostGIS Spatial Features**:
```sql
-- Spatial indexes
CREATE INDEX idx_geohash_geom ON geohash_species_tiles USING GIST(geometry);

-- Example query: Find species in bounding box
SELECT geohash_l7, species_data
FROM geohash_species_tiles
WHERE ST_Intersects(
    geometry,
    ST_MakeEnvelope(lon_min, lat_min, lon_max, lat_max, 4326)
);
```

**Database Size**:
- Total: ~8.5GB uncompressed
- Compressed backup: ~1.9GB (pg_dump -Fc)

### 1.6 Apache Fuseki Integration - **CORRECTED ASSESSMENT**

**Status**: ✅ **FULLY IMPLEMENTED** (not "missing" as initially stated)

**Architecture**:
```
PostgreSQL (67,743 species)
        ↓ Python sync script
RDF N-Triples (6.7M triples)
        ↓ HTTP PUT
Apache Fuseki (port 3030)
        ↓ SPARQL endpoint
Admin Frontend + API
```

**Fuseki Configuration**:
```json
{
  "fuseki": {
    "base_url": "http://localhost:3030",
    "dataset": "treekipedia",
    "sparql_endpoint": "http://localhost:3030/treekipedia/sparql",
    "update_endpoint": "http://localhost:3030/treekipedia/update",
    "data_endpoint": "http://localhost:3030/treekipedia/data"
  }
}
```

**RDF Ontology Structure**:
```turtle
# Base URIs
@prefix species: <http://treekipedia.org/species/> .
@prefix property: <http://treekipedia.org/property/> .
@prefix ontology: <http://treekipedia.org/ontology/> .

# Example species entity
species:12345 a ontology:Species ;
    property:species_scientific_name "Quercus robur" ;
    property:family "Fagaceae" ;
    property:growth_form "Tree" ;
    property:conservation_status "LC" .
```

**Sync Capabilities**:
1. **Full Sync**: All 67,743 species → ~6.7M RDF triples (20-30 min)
2. **Incremental Sync**: Only new/updated species since timestamp
3. **Batch Processing**: Configurable batch size (default 1000)
4. **Resume Capability**: Checkpoint-based resume for failed syncs
5. **Progress Streaming**: Real-time progress via Server-Sent Events

**SPARQL Query Examples**:
```sparql
# Get all species in Fagaceae family
PREFIX bd: <http://www.example.org/biodiversity-ontology#>
SELECT ?species ?name WHERE {
  ?species bd:scientificName ?name .
  ?species bd:family "Fagaceae" .
} LIMIT 20

# Count total triples
SELECT (COUNT(*) as ?count) WHERE {
  ?s ?p ?o .
}

# Find species by conservation status
PREFIX prop: <http://treekipedia.org/property/>
SELECT ?species ?name ?status WHERE {
  ?species prop:species_scientific_name ?name .
  ?species prop:conservation_status ?status .
  FILTER(?status = "EN")  # Endangered
}
```

**Admin Frontend Integration**:
- Real-time connection status monitoring
- Triple count and graph statistics display
- Interactive SPARQL query editor
- Sync progress visualization
- Error handling and logging

**Files Implementing Fuseki Integration**:
- `graphflow-extracted/silvi-open-graphflow/postgres_to_fuseki_sync.py` (740 lines)
- `treekipedia/python-microservice/api_only.py` (395 lines)
- `treekipedia/backend/routes/admin.js` (171 lines)
- `treekipedia/backend/controllers/admin.js` (286 lines)
- `treekipedia/frontend/app/admin/sparql/page.tsx` (170 lines)
- `treekipedia/frontend/app/admin/sync/page.tsx` (estimated 200 lines)
- `treekipedia/frontend/app/admin/page.tsx` (261 lines)

**Total Lines of Code**: ~2,200 lines dedicated to Fuseki integration

**Performance Metrics**:
- Sync speed: ~38 species/second (2,250 species/minute)
- RDF generation: ~100 triples per species
- Memory usage: ~500MB peak during full sync
- Network throughput: ~10MB/minute to Fuseki

**Critical Dependencies (Python-only, cannot be ported to Node.js)**:
- `owlready2==0.34` - OWL ontology manipulation (no JS alternative)
- `rdflib==7.0.0` - RDF triple generation (no equivalent JS library)

### 1.7 Map & Geospatial Integration

**Frontend Mapping** (Leaflet 1.9.4):
```typescript
// File: treekipedia/frontend/app/analysis/components/Map.tsx

// Key Features:
- Interactive polygon drawing for custom analysis areas
- Heatmap layer for species occurrence density
- Ecoregion boundary visualization
- Intact forest landscape overlay
- Real-time species count in drawn polygons
- Multi-layer toggle (heatmap, ecoregions, intact forests)
```

**API Integration**:
```javascript
// Occurrence heatmap data
GET /api/geospatial/occurrence-heatmap?bbox=lon1,lat1,lon2,lat2

// Ecoregion boundaries
GET /api/geospatial/ecoregions/boundaries?bbox=lon1,lat1,lon2,lat2

// Intact forest boundaries (6,819 polygons)
GET /api/geospatial/intact-forests/boundaries?zoom=5&bbox=...
```

**PostGIS Queries** (Backend):
```sql
-- Heatmap generation (file: controllers/geospatial.js)
SELECT
  geohash_l7,
  ST_Y(geometry) as lat,
  ST_X(geometry) as lng,
  jsonb_array_length(jsonb_object_keys(species_data)) as species_count
FROM geohash_species_tiles
WHERE ST_Intersects(
  geometry,
  ST_MakeEnvelope($1, $2, $3, $4, 4326)
);

-- Species in polygon
SELECT DISTINCT key as taxon_id
FROM geohash_species_tiles,
     jsonb_object_keys(species_data) as key
WHERE ST_Within(
  geometry,
  ST_GeomFromGeoJSON($1)
);
```

**STAC Compliance** (Spatiotemporal Asset Catalog):
```javascript
// File: backend/controllers/geospatial.js
GET /api/geospatial/tiles?bbox=lon1,lat1,lon2,lat2&datetime=2020-01-01/2025-12-31

// Response format:
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "geohash_12345",
      "geometry": { "type": "Point", "coordinates": [lng, lat] },
      "properties": {
        "datetime": "2024-01-01T00:00:00Z",
        "species_count": 42,
        "species_data": { "taxon_123": 10, "taxon_456": 5 }
      }
    }
  ]
}
```

**Geohash System**:
- Level 7 precision: ~153m × 153m tiles
- 5,786,835 total tiles with species data
- Coverage: 48,129 species (71% of database)
- Average: ~120 occurrences per tile

---

## 2. Architecture Analysis

### 2.1 Technology Stack Overview

```
┌─────────────────────────────────────────────────────────┐
│                    USER BROWSER                         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│         Next.js 15 Frontend (Port 3000)                 │
│  - React 18.3.1, Tailwind CSS 3.4.1                     │
│  - Leaflet maps, React Query state management           │
│  - Admin portal (6 pages + 4 components)                │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼──────────────────────────────────────┐
│         Express.js Backend (Port 5001)                  │
│  - Species API, Geospatial API, Admin proxy             │
│  - Blockchain webhook handling                          │
│  - Image serving, User management                       │
└──────┬───────────┬──────────────────────────────────────┘
       │           │
       │           └──────────────┐
       │                          │
┌──────▼──────────────┐   ┌───────▼────────────────────────┐
│  PostgreSQL 17      │   │ Python Microservice (Port 5002)│
│  + PostGIS 3.6      │   │  - Flask API (internal only)   │
│                     │   │  - GraphFlow module loader     │
│  - 67,743 species   │◄──┤  - SSE progress streaming      │
│  - 5.7M geohash     │   └────────┬───────────────────────┘
│  - 31K images       │            │
└─────────────────────┘   ┌────────▼───────────────────────┐
                          │  GraphFlow System              │
                          │  (silvi-open-graphflow/)       │
                          │                                │
                          │  - postgres_to_fuseki_sync.py  │
                          │  - multi_sheet_generator.py    │
                          │  - incremental_sync.py         │
                          │  - sheets_integration.py       │
                          └────────┬───────────────────────┘
                                   │ RDF/SPARQL
                          ┌────────▼───────────────────────┐
                          │    Apache Fuseki (Port 3030)   │
                          │    RDF Triple Store            │
                          │    - SPARQL endpoint           │
                          │    - Graph storage             │
                          └────────────────────────────────┘
```

### 2.2 Data Flow Examples

**Species Detail Page Load**:
```
User visits /species/12345
  ↓
Next.js fetches GET /species/12345 from Express
  ↓
Express queries PostgreSQL species table (115 fields)
  ↓
Express queries images table (join on taxon_id)
  ↓
Express queries geohash_species_tiles (occurrence count)
  ↓
JSON response with species data, images, occurrence stats
  ↓
Next.js renders species page with tabs
```

**Admin Species Sync Flow**:
```
Admin clicks "Sync Species" button
  ↓
Frontend POST /api/admin/sync/species to Express
  ↓
Express proxies POST /api/sync/species to Python microservice (port 5002)
  ↓
Python microservice imports GraphFlow postgres_to_fuseki_sync.py
  ↓
Python connects to PostgreSQL, fetches 67,743 species in batches of 1000
  ↓
For each batch:
  - Convert to RDF N-Triples format (~100 triples per species)
  - HTTP PUT to Fuseki data endpoint
  - Send SSE progress event
  ↓
Express streams SSE back to frontend
  ↓
Frontend updates progress bar in real-time
  ↓
Sync complete: 6.7M triples in Fuseki
```

**SPARQL Query Flow**:
```
Admin enters SPARQL query in /admin/sparql
  ↓
Frontend POST /api/admin/sparql/query to Express
  ↓
Express proxies POST /api/sparql/query to Python microservice
  ↓
Python microservice sends query to Fuseki SPARQL endpoint
  ↓
Fuseki executes query, returns results
  ↓
Python formats results as JSON
  ↓
Express returns results to frontend
  ↓
Frontend displays results in table or JSON view
```

**Geospatial Heatmap Query**:
```
User draws polygon on analysis map
  ↓
Frontend calculates bounding box
  ↓
GET /api/geospatial/occurrence-heatmap?bbox=lon1,lat1,lon2,lat2
  ↓
Express backend executes PostGIS query:
  SELECT geohash_l7, ST_Y(geometry) as lat, ST_X(geometry) as lng,
         (species_data->>'count')::int as species_count
  FROM geohash_species_tiles
  WHERE ST_Intersects(geometry, ST_MakeEnvelope(...))
  ↓
Returns array of { lat, lng, species_count }
  ↓
Frontend renders heatmap with leaflet.heat
```

### 2.3 Critical Code Paths

**Most Used Endpoints** (by frontend):
1. `GET /species/:taxon_id` - Species detail page (every species view)
2. `GET /api/geospatial/occurrence-heatmap` - Analysis map (every map interaction)
3. `GET /species/suggest` - Search autocomplete (every keystroke)
4. `GET /api/admin/status` - Admin dashboard (every 30s polling)

**Performance Bottlenecks**:
1. **Geohash queries**: 5.7M records require proper spatial indexing
2. **Fuseki sync**: 20-30 min for full sync (67K species)
3. **Image loading**: 31K images need CDN optimization
4. **Search query**: Currently broken, will be slow without indexing when fixed

**Recommended Optimizations**:
```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_species_scientific_name ON species(species_scientific_name);
CREATE INDEX idx_species_family ON species(family);
CREATE INDEX idx_geohash_species_data ON geohash_species_tiles USING GIN(species_data);
```

---

## 3. Vision vs Reality Gap Analysis

### 3.1 Feature Implementation Status

| Feature | Vision | Implementation | Status |
|---------|--------|----------------|--------|
| Species Knowledge Graph | ✅ 115 fields | ✅ Database schema | ✅ Complete |
| Geospatial Analysis | ✅ PostGIS + Geohashing | ✅ Functional | ✅ Complete |
| Apache Fuseki/GraphFlow | ✅ Extensive docs | ✅ **FULLY IMPLEMENTED** | ✅ **COMPLETE** |
| Admin Portal | ✅ Planned | ✅ **6 pages + 4 components** | ✅ **COMPLETE** |
| Python Microservice | ✅ Planned | ✅ **395 lines, production-ready** | ✅ **COMPLETE** |
| OWL Ontology Generation | ✅ Designed | ✅ **560 lines, 120+ patterns** | ✅ **COMPLETE** |
| PostgreSQL→Fuseki Sync | ✅ Designed | ✅ **740 lines, batch processing** | ✅ **COMPLETE** |
| SPARQL Query Interface | ✅ Planned | ✅ **Interactive editor with examples** | ✅ **COMPLETE** |
| Google Sheets Import | ✅ Planned | ✅ **200 lines, OAuth integration** | ✅ **COMPLETE** |
| AI Research Agents | ✅ Extensive docs | ❌ Not implemented | 🔴 Critical Gap |
| Blockchain Integration | ✅ Smart contracts | ⚠️ Partial | 🟡 Incomplete |
| On-Demand Recommendations | ✅ Designed | ⚠️ Basic only | 🟡 Partial |
| EAS Attestations | ✅ Planned | ❌ Not implemented | 🔴 Missing |
| IPFS Integration | ✅ Documented | ❌ Not implemented | 🔴 Missing |

**Key Revision**: The initial assessment incorrectly marked Apache Fuseki/GraphFlow as "Not Started". It is actually **FULLY IMPLEMENTED** with comprehensive capabilities including:
- Python microservice proxy architecture
- Full PostgreSQL→Fuseki synchronization (6.7M triples)
- Interactive SPARQL query editor
- Real-time sync progress via Server-Sent Events
- OWL ontology generation from CSV/Google Sheets
- Automatic biodiversity field detection (120+ patterns)
- Admin frontend with 6 dedicated pages

### 3.2 Data Model Completeness

**Implemented:**
- ✅ Core species taxonomy (complete)
- ✅ Geographic distribution (complete)
- ✅ Geohash occurrence tiles (complete)
- ✅ Basic image support (31,796 images, 47% species coverage)
- ✅ RDF triple store (Fuseki with SPARQL)
- ✅ Ontology generation system (OWL/RDF)

**Missing:**
- ❌ AI-generated research fields (empty, research pipeline not implemented)
- ❌ Ecological embeddings (not started - THIS ASSESSMENT'S FOCUS)
- ⚠️ Temporal species data (limited - only occurrence years)
- ❌ Allometric models (empty fields)
- ❌ EAS attestation records (table doesn't exist)
- ❌ IPFS CID tracking (no table)

---

## 4. Google Earth Engine Integration Strategy

### 4.1 GEE Capabilities Overview

**AlphaEarth Embeddings** (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`):
- **64-dimensional embedding vectors** per 10m pixel
- **Available years**: 2017-2024 (annually)
- **Temporal alignment**: Captures seasonal/annual surface conditions
- **Band labels**: A01-A64
- **Resolution**: 10 meters (10m × 10m pixels)
- **Projection**: EPSG:4326 (WGS84)

**What AlphaEarth Encodes**:
- Surface reflectance patterns
- Vegetation indices (NDVI-like features)
- Soil moisture indicators
- Land cover characteristics
- Seasonal phenology
- Disturbance signatures
- Climate-vegetation interactions

**API Access** (Python):
```python
import ee
ee.Initialize()

# Get embeddings for a point and year
point = ee.Geometry.Point([-122.08, 37.42])  # [lng, lat]
embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
    .filterDate('2024-01-01', '2025-01-01') \
    .filterBounds(point) \
    .first()

# Extract 64-band values at point
sample = embeddings.reduceRegion(
    reducer=ee.Reducer.first(),
    geometry=point,
    scale=10  # 10m resolution
)

# Returns: { 'A01': value, 'A02': value, ..., 'A64': value }
```

### 4.2 Quota Management Strategies

**GEE Quotas (Free Tier)**:
- **Interactive requests**: 5-minute timeout per request
- **Batch processing**: 10-day maximum task lifetime
- **Concurrent tasks**: Up to 3,000 active tasks
- **Asset storage**: 250 GB default (10,000 assets)
- **Earth Engine Units (EEUs)**: Consumption-based limits

**Optimization Strategies**:

1. **Batch Exports to Google Drive**:
   - Export large extractions as CSV/GeoJSON to Drive
   - Minimizes local storage (<5GB requirement)
   - Automatic resume on failure
   - Parallel task submission

2. **Species Chunking**:
   - Process 100-500 species per batch
   - Each batch = 1 GEE export task
   - Checkpoint after each batch

3. **Occurrence Batching**:
   - Group occurrences by species
   - Use `reduceRegions` for multi-point extraction (more efficient than individual calls)
   - Process up to 5,000 points per request

4. **Caching Strategy**:
   - Cache raw embeddings in Google Drive
   - Compute statistics locally (no re-extraction needed)
   - Only re-extract if occurrence data changes

5. **Exponential Backoff**:
   ```python
   def extract_with_retry(geometry, year, max_retries=5):
       for i in range(max_retries):
           try:
               return extract_embedding(geometry, year)
           except ee.EEException as e:
               if 'quota' in str(e).lower():
                   wait_time = 2 ** i * 60  # 1, 2, 4, 8, 16 minutes
                   time.sleep(wait_time)
               else:
                   raise
   ```

6. **Reduce Precision**:
   - Round embedding values to 6 decimal places
   - Reduces CSV file size by ~30%

### 4.3 Pipeline Architecture Design

**High-Level Flow**:
```
PostgreSQL (67,743 species, occurrence coordinates)
        ↓
Occurrence Data Extraction (species-by-species)
        ↓
GEE Batch Processing (100 species chunks)
        ↓ Export to Google Drive
Raw Embeddings (CSV: taxon_id, lat, lng, year, A01-A64)
        ↓ Download batches
Local Aggregation (compute mean, std, p10, p90 per species)
        ↓
New Database Fields (256 fields per species)
        ↓
PostgreSQL Update (67,743 species × 256 fields)
```

**Python Implementation** (Pseudocode):

```python
import ee
import psycopg2
import pandas as pd
import numpy as np
from google.colab import drive  # Or use Google Drive API

class SpeciesEmbeddingPipeline:
    """
    Extracts AlphaEarth embeddings for species occurrences
    Generates 256 statistical fields per species
    """

    def __init__(self):
        # Initialize Google Earth Engine
        ee.Initialize()

        # Configuration
        self.drive_folder = 'treekipedia_embeddings'
        self.batch_size = 100  # species per GEE export task
        self.occurrence_batch_size = 5000  # points per reduceRegions call

        # Database connection
        self.db_conn = psycopg2.connect(
            host='localhost',
            database='treekipedia',
            user='postgres'
        )

        # Embedding years
        self.first_year = 2017  # First AlphaEarth year
        self.last_year = 2024   # Last AlphaEarth year

    def get_species_occurrences(self, taxon_id):
        """
        Fetch occurrence data from PostgreSQL

        Returns: DataFrame with columns [lat, lng, year]
        """
        query = """
        SELECT latitude, longitude, year
        FROM occurrence_data
        WHERE taxon_id = %s
        """
        return pd.read_sql(query, self.db_conn, params=(taxon_id,))

    def get_embedding_year(self, occurrence_year):
        """
        Map occurrence year to available embedding year

        Logic:
        - occurrence_year <= 2017 → use 2017
        - 2018 <= occurrence_year <= 2024 → use occurrence_year
        - occurrence_year > 2024 → use 2024
        """
        if occurrence_year <= self.first_year:
            return self.first_year
        elif occurrence_year > self.last_year:
            return self.last_year
        else:
            return occurrence_year

    def extract_embeddings_batch(self, occurrences_df):
        """
        Extract embeddings for a batch of occurrences using GEE

        Args:
            occurrences_df: DataFrame with [lat, lng, year, taxon_id]

        Returns:
            DataFrame with [lat, lng, year, taxon_id, A01-A64]
        """
        # Group by year for efficiency
        results = []

        for year, group in occurrences_df.groupby('year'):
            # Get embedding year
            embedding_year = self.get_embedding_year(year)

            # Load AlphaEarth embeddings for this year
            embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
                .filterDate(f'{embedding_year}-01-01', f'{embedding_year}-12-31') \
                .first()

            # Create feature collection from points
            points = [
                ee.Feature(ee.Geometry.Point([row['lng'], row['lat']]), {
                    'taxon_id': row['taxon_id'],
                    'occurrence_year': row['year']
                })
                for _, row in group.iterrows()
            ]

            fc = ee.FeatureCollection(points)

            # Extract embedding values at all points (efficient multi-point extraction)
            sampled = embeddings.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.first(),
                scale=10  # 10m resolution
            )

            # Convert to pandas DataFrame
            # Note: This is a simplification; actual implementation would use export tasks
            sampled_list = sampled.getInfo()['features']
            for feature in sampled_list:
                properties = feature['properties']
                coords = feature['geometry']['coordinates']

                result_row = {
                    'taxon_id': properties['taxon_id'],
                    'lat': coords[1],
                    'lng': coords[0],
                    'occurrence_year': properties['occurrence_year'],
                    'embedding_year': embedding_year
                }

                # Add all 64 embedding bands
                for band in range(1, 65):
                    band_name = f'A{band:02d}'
                    result_row[band_name] = properties.get(band_name, None)

                results.append(result_row)

        return pd.DataFrame(results)

    def calculate_species_statistics(self, embeddings_df):
        """
        Calculate mean, std, p10, p90 for each of 64 bands

        Args:
            embeddings_df: DataFrame with A01-A64 columns

        Returns:
            Dict with 256 fields:
            {
                'A01_mean': float, 'A01_std': float, 'A01_p10': float, 'A01_p90': float,
                'A02_mean': float, 'A02_std': float, 'A02_p10': float, 'A02_p90': float,
                ...
                'A64_mean': float, 'A64_std': float, 'A64_p10': float, 'A64_p90': float
            }
        """
        stats = {}

        for band in range(1, 65):
            band_name = f'A{band:02d}'

            # Extract band values (filter out NaNs)
            values = embeddings_df[band_name].dropna()

            if len(values) > 0:
                stats[f'{band_name}_mean'] = float(values.mean())
                stats[f'{band_name}_std'] = float(values.std())
                stats[f'{band_name}_p10'] = float(values.quantile(0.10))
                stats[f'{band_name}_p90'] = float(values.quantile(0.90))
            else:
                # No valid data for this band
                stats[f'{band_name}_mean'] = None
                stats[f'{band_name}_std'] = None
                stats[f'{band_name}_p10'] = None
                stats[f'{band_name}_p90'] = None

        return stats

    def process_species(self, taxon_id):
        """
        Complete pipeline for one species

        Returns:
            Dict with 256 embedding statistics
        """
        # 1. Get occurrences
        occurrences = self.get_species_occurrences(taxon_id)

        if len(occurrences) == 0:
            return None  # No occurrence data

        # Add taxon_id column
        occurrences['taxon_id'] = taxon_id

        # 2. Extract embeddings
        embeddings = self.extract_embeddings_batch(occurrences)

        # 3. Calculate statistics
        stats = self.calculate_species_statistics(embeddings)

        return stats

    def update_database(self, taxon_id, stats):
        """
        Update species table with embedding statistics

        Adds 256 new columns if they don't exist
        """
        cursor = self.db_conn.cursor()

        # Build UPDATE query
        set_clause = ', '.join([f'{key} = %s' for key in stats.keys()])
        values = list(stats.values()) + [taxon_id]

        query = f"""
        UPDATE species
        SET {set_clause}
        WHERE taxon_id = %s
        """

        cursor.execute(query, values)
        self.db_conn.commit()
        cursor.close()

    def run_full_pipeline(self, species_chunk_size=100):
        """
        Process all 67,743 species in chunks

        Uses Google Drive for intermediate storage
        """
        cursor = self.db_conn.cursor()

        # Get all species with occurrence data
        cursor.execute("""
            SELECT DISTINCT taxon_id
            FROM occurrence_data
            ORDER BY taxon_id
        """)

        all_species = [row[0] for row in cursor.fetchall()]
        total_species = len(all_species)

        print(f"Processing {total_species} species with occurrence data...")

        # Process in chunks
        for i in range(0, total_species, species_chunk_size):
            chunk = all_species[i:i+species_chunk_size]

            print(f"\nProcessing species chunk {i//species_chunk_size + 1}/{(total_species-1)//species_chunk_size + 1}")
            print(f"Species {i+1}-{min(i+species_chunk_size, total_species)}")

            # Process each species in chunk
            for taxon_id in chunk:
                try:
                    print(f"  Processing species {taxon_id}...")

                    stats = self.process_species(taxon_id)

                    if stats:
                        self.update_database(taxon_id, stats)
                        print(f"    ✓ Updated {taxon_id} with 256 embedding fields")
                    else:
                        print(f"    ⚠ No occurrence data for {taxon_id}")

                except Exception as e:
                    print(f"    ✗ Error processing {taxon_id}: {e}")
                    continue

            # Checkpoint
            print(f"  Checkpoint: {min(i+species_chunk_size, total_species)}/{total_species} species completed")

        print(f"\n✅ Full pipeline complete!")
        cursor.close()

# Usage
pipeline = SpeciesEmbeddingPipeline()
pipeline.run_full_pipeline(species_chunk_size=100)
```

**Optimized GEE Export Version** (Production):

For production, use GEE's export functionality to avoid quota issues:

```python
def export_embeddings_to_drive(self, species_chunk):
    """
    Export embeddings for a chunk of species to Google Drive
    More efficient for large batches
    """
    # Collect all occurrences for chunk
    all_occurrences = []
    for taxon_id in species_chunk:
        occurrences = self.get_species_occurrences(taxon_id)
        occurrences['taxon_id'] = taxon_id
        all_occurrences.append(occurrences)

    occurrences_df = pd.concat(all_occurrences)

    # Group by embedding year
    for year in occurrences_df['year'].unique():
        embedding_year = self.get_embedding_year(year)
        year_occurrences = occurrences_df[occurrences_df['year'] == year]

        # Create feature collection
        features = [
            ee.Feature(ee.Geometry.Point([row['lng'], row['lat']]), {
                'taxon_id': int(row['taxon_id']),
                'occ_year': int(row['year'])
            })
            for _, row in year_occurrences.iterrows()
        ]

        fc = ee.FeatureCollection(features)

        # Load embeddings
        embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
            .filterDate(f'{embedding_year}-01-01', f'{embedding_year}-12-31') \
            .first()

        # Sample embeddings at points
        sampled = embeddings.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.first(),
            scale=10
        )

        # Export to Google Drive
        task = ee.batch.Export.table.toDrive(
            collection=sampled,
            description=f'embeddings_year{embedding_year}_chunk{species_chunk[0]}',
            folder=self.drive_folder,
            fileFormat='CSV'
        )

        task.start()
        print(f"  Export task started: {task.id}")

    return task
```

### 4.4 Database Schema Modifications

**New Columns** (256 total):

```sql
-- Add embedding statistic columns to species table
ALTER TABLE species
  -- Band A01 statistics
  ADD COLUMN A01_mean NUMERIC(10, 6),
  ADD COLUMN A01_std NUMERIC(10, 6),
  ADD COLUMN A01_p10 NUMERIC(10, 6),
  ADD COLUMN A01_p90 NUMERIC(10, 6),

  -- Band A02 statistics
  ADD COLUMN A02_mean NUMERIC(10, 6),
  ADD COLUMN A02_std NUMERIC(10, 6),
  ADD COLUMN A02_p10 NUMERIC(10, 6),
  ADD COLUMN A02_p90 NUMERIC(10, 6),

  -- ... (repeat for A03-A63) ...

  -- Band A64 statistics
  ADD COLUMN A64_mean NUMERIC(10, 6),
  ADD COLUMN A64_std NUMERIC(10, 6),
  ADD COLUMN A64_p10 NUMERIC(10, 6),
  ADD COLUMN A64_p90 NUMERIC(10, 6);

-- Add metadata columns
ALTER TABLE species
  ADD COLUMN embedding_extraction_date TIMESTAMP,
  ADD COLUMN embedding_occurrence_count INTEGER,
  ADD COLUMN embedding_year_range VARCHAR(20);  -- e.g., "2017-2024"

-- Create index for embedding queries
CREATE INDEX idx_species_embeddings_complete
ON species(taxon_id)
WHERE A01_mean IS NOT NULL;
```

**Migration Script**:

```sql
-- File: database/migrations/add_embedding_fields.sql

BEGIN;

-- Generate all 256 columns programmatically
DO $$
DECLARE
    band_num INTEGER;
    stat_type TEXT;
BEGIN
    FOR band_num IN 1..64 LOOP
        FOR stat_type IN SELECT unnest(ARRAY['mean', 'std', 'p10', 'p90']) LOOP
            EXECUTE format(
                'ALTER TABLE species ADD COLUMN IF NOT EXISTS A%s_%s NUMERIC(10, 6)',
                lpad(band_num::text, 2, '0'),
                stat_type
            );
        END LOOP;
    END LOOP;
END $$;

-- Add metadata
ALTER TABLE species
  ADD COLUMN IF NOT EXISTS embedding_extraction_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS embedding_occurrence_count INTEGER,
  ADD COLUMN IF NOT EXISTS embedding_year_range VARCHAR(20);

-- Create index
CREATE INDEX IF NOT EXISTS idx_species_embeddings_complete
ON species(taxon_id)
WHERE A01_mean IS NOT NULL;

COMMIT;
```

### 4.5 Storage/Caching Strategy (Google Drive)

**Google Drive Folder Structure**:

```
Google Drive/
└── treekipedia_embeddings/
    ├── raw_extractions/
    │   ├── species_batch_001/
    │   │   ├── embeddings_year2017_chunk0001.csv
    │   │   ├── embeddings_year2018_chunk0001.csv
    │   │   ├── ... (one file per year)
    │   │   └── embeddings_year2024_chunk0001.csv
    │   ├── species_batch_002/
    │   │   └── ... (same structure)
    │   └── ... (one folder per 100-species batch)
    ├── aggregated_stats/
    │   ├── species_stats_batch_001.csv
    │   ├── species_stats_batch_002.csv
    │   └── ... (256 columns × batch size rows)
    ├── checkpoints/
    │   ├── completed_species.txt  # List of completed taxon_ids
    │   └── failed_species.txt     # List of failed taxon_ids
    └── logs/
        ├── extraction_log_2025-10-26.txt
        └── ... (daily logs)
```

**CSV Format** (Raw Extractions):

```csv
taxon_id,lat,lng,occurrence_year,embedding_year,A01,A02,A03,...,A64
12345,-34.6037,138.7224,2020,2020,0.123,0.456,0.789,...,0.321
12345,-34.5892,138.7456,2019,2019,0.124,0.455,0.788,...,0.322
12346,-35.2809,149.1300,2021,2021,0.125,0.454,0.787,...,0.323
```

**CSV Format** (Aggregated Stats):

```csv
taxon_id,A01_mean,A01_std,A01_p10,A01_p90,A02_mean,A02_std,A02_p10,A02_p90,...,A64_p90
12345,0.1235,0.0123,0.1100,0.1370,0.4555,0.0234,0.4200,0.4900,...,0.3215
12346,0.1245,0.0125,0.1105,0.1375,0.4545,0.0236,0.4195,0.4895,...,0.3225
```

**Local Storage** (Minimal):
- Python scripts: ~100KB
- Checkpoint files: ~1MB (list of completed taxon_ids)
- Temporary download: ~50MB per batch (deleted after processing)
- **Total**: <5GB local storage

**Google Drive Storage** (Cloud):
- Raw extractions: ~500MB per 1,000 species (compressed)
- Aggregated stats: ~10MB per 1,000 species
- **Total for 67,743 species**: ~35GB (well within 250GB quota)

### 4.6 Temporal Matching Logic

**Occurrence Year → Embedding Year Mapping**:

```python
def get_embedding_year(occurrence_year):
    """
    Map occurrence year to available AlphaEarth embedding year

    AlphaEarth available years: 2017-2024

    Rules:
    1. If occurrence_year <= 2017: use 2017 (earliest available)
    2. If 2017 < occurrence_year <= 2024: use occurrence_year (exact match)
    3. If occurrence_year > 2024: use 2024 (latest available)

    Examples:
    - occurrence_year = 2010 → 2017
    - occurrence_year = 2020 → 2020
    - occurrence_year = 2025 → 2024
    """
    FIRST_YEAR = 2017
    LAST_YEAR = 2024

    if occurrence_year <= FIRST_YEAR:
        return FIRST_YEAR
    elif occurrence_year > LAST_YEAR:
        return LAST_YEAR
    else:
        return occurrence_year
```

**Rationale**:
- **Pre-2017 occurrences**: Use 2017 as proxy (assumes habitat stability)
- **2017-2024 occurrences**: Use exact year for temporal accuracy
- **Post-2024 occurrences**: Use 2024 as latest available data

**Temporal Distribution Analysis**:

```sql
-- Analyze occurrence year distribution
SELECT
  CASE
    WHEN year <= 2017 THEN '≤2017 (use 2017)'
    WHEN year BETWEEN 2018 AND 2024 THEN '2018-2024 (exact match)'
    WHEN year > 2024 THEN '>2024 (use 2024)'
  END as year_category,
  COUNT(*) as occurrence_count,
  COUNT(DISTINCT taxon_id) as species_count
FROM occurrence_data
GROUP BY year_category
ORDER BY year_category;
```

**Expected Results** (based on typical occurrence data patterns):
- ~40% of occurrences: ≤2017 (historical data, use 2017 embedding)
- ~55% of occurrences: 2018-2024 (exact year match)
- ~5% of occurrences: >2024 (recent data, use 2024 embedding)

### 4.7 Error Handling & Resume Capability

**Checkpoint System**:

```python
class CheckpointManager:
    def __init__(self, checkpoint_file='checkpoints/completed_species.txt'):
        self.checkpoint_file = checkpoint_file
        os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)

    def load_completed(self):
        """Load list of completed species"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                return set(int(line.strip()) for line in f)
        return set()

    def mark_completed(self, taxon_id):
        """Mark species as completed"""
        with open(self.checkpoint_file, 'a') as f:
            f.write(f"{taxon_id}\n")

    def get_remaining_species(self, all_species):
        """Get list of species still to process"""
        completed = self.load_completed()
        return [s for s in all_species if s not in completed]

# Usage in pipeline
checkpoint_mgr = CheckpointManager()
remaining_species = checkpoint_mgr.get_remaining_species(all_species)

for taxon_id in remaining_species:
    try:
        process_species(taxon_id)
        checkpoint_mgr.mark_completed(taxon_id)
    except Exception as e:
        log_error(taxon_id, e)
        continue  # Skip to next species
```

**Error Logging**:

```python
import logging

logging.basicConfig(
    filename='logs/extraction_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_species_with_logging(taxon_id):
    try:
        logging.info(f"Starting extraction for species {taxon_id}")

        stats = extract_embeddings(taxon_id)
        update_database(taxon_id, stats)

        logging.info(f"Completed species {taxon_id}: 256 fields updated")

    except ee.EEException as e:
        if 'quota' in str(e).lower():
            logging.warning(f"Quota exceeded for species {taxon_id}, will retry later")
        else:
            logging.error(f"GEE error for species {taxon_id}: {e}")
        raise

    except psycopg2.Error as e:
        logging.error(f"Database error for species {taxon_id}: {e}")
        raise

    except Exception as e:
        logging.error(f"Unexpected error for species {taxon_id}: {e}", exc_info=True)
        raise
```

**Retry Logic**:

```python
def extract_with_exponential_backoff(taxon_id, max_retries=5):
    """
    Retry extraction with exponential backoff for quota errors
    """
    for attempt in range(max_retries):
        try:
            return process_species(taxon_id)

        except ee.EEException as e:
            if 'quota' in str(e).lower() and attempt < max_retries - 1:
                wait_time = 2 ** attempt * 60  # 1, 2, 4, 8, 16 minutes
                logging.warning(f"Quota exceeded, waiting {wait_time/60} minutes before retry {attempt+1}")
                time.sleep(wait_time)
            else:
                raise

    raise Exception(f"Failed to extract species {taxon_id} after {max_retries} attempts")
```

### 4.8 Performance Estimates

**Processing Time**:

```
Total species with occurrence data: 48,129
Average occurrences per species: ~120

Batch size: 100 species
Total batches: 482

Time per batch:
  - GEE extraction: ~5-10 minutes (depends on quota)
  - Google Drive export: ~2-3 minutes
  - Download from Drive: ~1 minute
  - Aggregation: ~30 seconds
  - Database update: ~30 seconds
  Total: ~10-15 minutes per batch

Total time estimate:
  482 batches × 12 minutes = 5,784 minutes = 96 hours = 4 days

With parallelization (3 concurrent batches):
  96 hours / 3 = 32 hours = 1.3 days

Conservative estimate: 2-3 days for full extraction
```

**Storage Estimates**:

```
Raw CSV data per species:
  Average 120 occurrences × 70 columns (metadata + 64 bands) × 10 bytes = ~84KB

Total raw data:
  48,129 species × 84KB = 4,043MB = ~4GB

Compressed (Google Drive):
  4GB × 0.3 (CSV compression ratio) = ~1.2GB

Aggregated stats:
  48,129 species × 256 fields × 8 bytes = 98MB

Total Google Drive storage needed: ~1.5GB (well within quota)
```

**Cost Estimate** (Free Tier):

- Google Earth Engine: Free (within quota limits)
- Google Drive: Free (15GB storage included)
- Local compute: Free (uses your machine)
- **Total cost**: $0

**If quota exceeded, consider**:
- Google Cloud account upgrade ($300 free credit)
- Distribute processing across multiple Google accounts
- Slow down extraction rate (more time, but still free)

---

## 5. Implementation Roadmap

### Phase 1: Infrastructure Setup (Week 1)

**Days 1-2: Environment Setup**
- [ ] Set up Google Earth Engine account
- [ ] Enable Google Drive API
- [ ] Create `treekipedia_embeddings` folder in Drive
- [ ] Set up local Python environment:
  ```bash
  pip install earthengine-api google-api-python-client pandas numpy psycopg2
  ```
- [ ] Authenticate GEE:
  ```python
  import ee
  ee.Authenticate()
  ee.Initialize()
  ```

**Days 3-4: Database Preparation**
- [ ] Run migration script to add 256 embedding columns
- [ ] Create `occurrence_data` table (if not exists):
  ```sql
  CREATE TABLE occurrence_data (
    id SERIAL PRIMARY KEY,
    taxon_id BIGINT REFERENCES species(taxon_id),
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    year INTEGER,
    source VARCHAR(100)
  );
  ```
- [ ] Import occurrence data from Parquet file:
  ```python
  import pandas as pd
  df = pd.read_parquet('Treekipedia_occ_Year_october24d.parquet')
  df.to_sql('occurrence_data', engine, if_exists='append')
  ```
- [ ] Create spatial index:
  ```sql
  CREATE INDEX idx_occurrence_coords ON occurrence_data(latitude, longitude);
  CREATE INDEX idx_occurrence_taxon ON occurrence_data(taxon_id);
  ```

**Days 5-7: Pipeline Development**
- [ ] Implement `SpeciesEmbeddingPipeline` class
- [ ] Test with 10 species (pilot extraction)
- [ ] Verify GEE quota limits
- [ ] Test Google Drive export/download
- [ ] Validate database updates

**Deliverables**:
- ✅ GEE account authenticated
- ✅ Database schema updated with 256 columns
- ✅ Occurrence data imported (if from Parquet)
- ✅ Python pipeline code complete
- ✅ Pilot test successful (10 species)

### Phase 2: Pilot Extraction (Week 2)

**Days 8-10: Extract 100 Species**
- [ ] Select diverse species sample:
  ```sql
  SELECT taxon_id
  FROM species
  WHERE taxon_id IN (
    SELECT DISTINCT taxon_id
    FROM occurrence_data
  )
  ORDER BY RANDOM()
  LIMIT 100;
  ```
- [ ] Run extraction pipeline on pilot batch
- [ ] Monitor GEE quota consumption
- [ ] Validate embedding statistics
- [ ] Check for errors/edge cases

**Days 11-12: Quality Assurance**
- [ ] Verify 256 fields populated correctly
- [ ] Check for NULL values (species with no data)
- [ ] Analyze embedding distributions:
  ```sql
  SELECT
    AVG(A01_mean), STDDEV(A01_mean),
    AVG(A01_std), STDDEV(A01_std),
    COUNT(*) FILTER (WHERE A01_mean IS NULL) as null_count
  FROM species
  WHERE A01_mean IS NOT NULL;
  ```
- [ ] Visualize embedding space (PCA, t-SNE)
- [ ] Compare species in similar habitats

**Days 13-14: Optimization**
- [ ] Tune batch sizes based on quota usage
- [ ] Implement parallel processing (if quota allows)
- [ ] Optimize Google Drive file sizes
- [ ] Add progress bars and ETA estimates

**Deliverables**:
- ✅ 100 species with complete embedding data
- ✅ Quality metrics documented
- ✅ Quota consumption analyzed
- ✅ Optimized pipeline ready for scale

### Phase 3: Full-Scale Extraction (Weeks 3-4)

**Days 15-28: Process All 48,129 Species**
- [ ] Run pipeline on all species with occurrence data
- [ ] Process in batches of 100 species
- [ ] Monitor progress daily:
  ```sql
  SELECT COUNT(*)
  FROM species
  WHERE A01_mean IS NOT NULL;
  ```
- [ ] Handle errors and retries
- [ ] Maintain checkpoint files
- [ ] Backup Google Drive folder daily

**Concurrent Tasks**:
- [ ] Document embedding field meanings
- [ ] Create data dictionary
- [ ] Prepare API documentation
- [ ] Design embedding query endpoints

**Error Recovery**:
- [ ] If quota exceeded: pause and resume next day
- [ ] If extraction fails: check logs, fix, resume from checkpoint
- [ ] If Drive full: compress older batches, delete raw CSVs after aggregation

**Deliverables**:
- ✅ 48,129 species with embedding data (100% of species with occurrences)
- ✅ 19,614 species marked as "no occurrence data"
- ✅ Google Drive folder with all raw + aggregated data
- ✅ Extraction logs and error reports
- ✅ Final database backup with embeddings

### Phase 4: API Integration & Applications (Week 5)

**Days 29-30: Backend API Endpoints**
- [ ] Create embedding query endpoint:
  ```javascript
  // File: backend/routes/embeddings.js
  GET /api/embeddings/:taxon_id
  // Returns: 256 embedding statistics

  GET /api/embeddings/similar/:taxon_id?limit=10
  // Returns: Most similar species by embedding distance
  ```
- [ ] Implement embedding similarity calculation:
  ```sql
  -- Euclidean distance between species embeddings
  WITH target AS (
    SELECT A01_mean, A02_mean, ..., A64_mean
    FROM species
    WHERE taxon_id = $1
  )
  SELECT
    s.taxon_id,
    s.species_scientific_name,
    SQRT(
      POWER(s.A01_mean - t.A01_mean, 2) +
      POWER(s.A02_mean - t.A02_mean, 2) +
      ... +
      POWER(s.A64_mean - t.A64_mean, 2)
    ) as embedding_distance
  FROM species s, target t
  WHERE s.A01_mean IS NOT NULL
  ORDER BY embedding_distance ASC
  LIMIT 10;
  ```

**Days 31-32: Frontend Visualization**
- [ ] Add "Environmental Signature" tab to species pages
- [ ] Visualize embedding statistics with charts
- [ ] Show similar species recommendations
- [ ] Add embedding-based species search

**Days 33-35: Advanced Applications**
- [ ] **Diversity Composition Estimator**:
  ```python
  def estimate_species_diversity(location, buffer_km=10):
      """
      Estimate likely species at location based on embedding similarity
      to known occurrences in nearby areas
      """
      # Get embeddings for location (from GEE)
      location_embedding = extract_embedding(location, year=2024)

      # Compare to all species embeddings
      distances = calculate_embedding_distances(location_embedding, all_species)

      # Return top matches
      return species[distances.argsort()[:50]]
  ```

- [ ] **Habitat Suitability Predictor**:
  ```python
  def predict_habitat_suitability(taxon_id, candidate_locations):
      """
      Predict if candidate locations are suitable habitat
      based on embedding similarity to known occurrences
      """
      species_embedding = get_species_embedding(taxon_id)

      suitability_scores = []
      for loc in candidate_locations:
          loc_embedding = extract_embedding(loc, year=2024)
          distance = euclidean_distance(species_embedding, loc_embedding)
          suitability = 1 / (1 + distance)  # Convert distance to 0-1 score
          suitability_scores.append(suitability)

      return suitability_scores
  ```

- [ ] **Climate Change Impact Analysis**:
  ```python
  def analyze_temporal_embedding_shift(taxon_id):
      """
      Analyze how species' environmental signature has changed over time
      by comparing embeddings from different years
      """
      embeddings_by_year = {}

      for year in range(2017, 2025):
          embeddings_by_year[year] = get_species_embedding(taxon_id, year=year)

      # Calculate trajectory
      shifts = []
      for i in range(len(embeddings_by_year) - 1):
          year1, year2 = 2017 + i, 2017 + i + 1
          distance = euclidean_distance(
              embeddings_by_year[year1],
              embeddings_by_year[year2]
          )
          shifts.append(distance)

      return {
          'average_annual_shift': np.mean(shifts),
          'total_shift_2017_2024': euclidean_distance(
              embeddings_by_year[2017],
              embeddings_by_year[2024]
          ),
          'trajectory': shifts
      }
  ```

**Deliverables**:
- ✅ Backend API endpoints for embeddings
- ✅ Frontend visualization of environmental signatures
- ✅ Species similarity recommendations
- ✅ Advanced ecological AI applications
- ✅ Documentation for embedding-based features

---

## 6. Expected Outcomes & Applications

### 6.1 New Capabilities Enabled

**1. Species Matching by Environment**
```
User Query: "Which tree species are similar to Quercus robur in environmental niche?"

System Response:
1. Quercus petraea (Euclidean distance: 0.12)
2. Fagus sylvatica (Euclidean distance: 0.18)
3. Quercus cerris (Euclidean distance: 0.23)
...

Rationale: Species with similar embedding signatures likely occupy similar
environmental niches (temperature, precipitation, soil, vegetation patterns).
```

**2. Diversity Composition Estimation**
```
User Input: Latitude/Longitude coordinates of unmapped area

System Output:
Predicted species composition based on environmental similarity:
- Probability Quercus robur: 0.82 (embedding distance: 0.15)
- Probability Pinus sylvestris: 0.76 (embedding distance: 0.19)
- Probability Betula pendula: 0.68 (embedding distance: 0.24)
...

Use Case: Rapid biodiversity assessment, reforestation planning,
conservation prioritization.
```

**3. Habitat Suitability Prediction**
```
User Query: "Is this location suitable habitat for Sequoia sempervirens?"

System Analysis:
- Extract embedding for target location (2024)
- Compare to S. sempervirens mean embedding
- Compute suitability score

Result: Suitability = 0.71 (High)
Rationale: Location embedding within 1 std dev of species' typical range.
```

**4. Climate Change Impact Detection**
```
Analysis: Compare species embeddings 2017 vs 2024

Species: Picea abies (Norway Spruce)
- 2017 mean embedding: [0.12, 0.34, ...]
- 2024 mean embedding: [0.14, 0.32, ...]
- Shift magnitude: 0.08 (moderate)

Interpretation: Species experiencing environmental stress,
possible range shift northward/upward in elevation.
```

**5. Functional Ecology Insights**
```
Analysis: Cluster species by embedding similarity

Cluster 1 (Temperate broadleaf): Quercus, Fagus, Acer
Cluster 2 (Boreal conifer): Picea, Pinus, Abies
Cluster 3 (Mediterranean): Olea, Quercus ilex, Pinus halepensis

Application: Functional group classification without manual labeling.
```

### 6.2 Research Applications

**Ecological Research**:
- Species distribution modeling (SDM) with environmental embeddings
- Functional trait prediction from environmental associations
- Niche overlap analysis across species
- Climate envelope modeling

**Conservation**:
- Identify at-risk species (those with rapidly shifting embeddings)
- Prioritize areas for protection (high embedding diversity)
- Predict impacts of land-use change
- Monitor habitat degradation

**Forestry & Land Management**:
- Select suitable species for reforestation projects
- Predict timber growth based on environmental similarity to known plantations
- Assess fire risk based on vegetation embedding patterns
- Plan agroforestry systems with compatible species

**AI/ML Research**:
- Train models to predict species traits from embeddings
- Generate synthetic occurrence data for rare species
- Develop explainable AI for biodiversity predictions
- Create embedding-based recommendation systems

### 6.3 Integration with Existing Treekipedia Features

**Enhanced Species Pages**:
```
Current: Taxonomy, Distribution, Images
New: Environmental Signature, Similar Species, Habitat Suitability Map
```

**Cross-Species Analysis Tool**:
```
Current: Search by taxonomy, geography
New: Search by environmental similarity
```

**API Enhancements**:
```javascript
// New endpoint examples:

GET /api/embeddings/:taxon_id
// Returns 256 embedding fields

GET /api/embeddings/similar/:taxon_id?limit=10&threshold=0.5
// Returns species with similar embeddings

POST /api/embeddings/predict-diversity
// Body: { "coordinates": [[lng, lat], ...], "year": 2024 }
// Returns: Predicted species composition

POST /api/embeddings/suitability
// Body: { "taxon_id": 12345, "locations": [[lng, lat], ...] }
// Returns: Suitability scores (0-1) for each location
```

**SPARQL Knowledge Graph**:
```sparql
# Query species by embedding similarity (if synced to Fuseki)
PREFIX prop: <http://treekipedia.org/property/>
PREFIX emb: <http://treekipedia.org/embedding/>

SELECT ?species ?name ?distance WHERE {
  ?species prop:species_scientific_name ?name .
  ?species emb:similarity_to_target ?distance .
  FILTER(?distance < 0.3)
}
ORDER BY ?distance
LIMIT 10
```

---

## 7. Risks & Mitigation

### 7.1 Technical Risks

**Risk 1: GEE Quota Exceeded**
- **Likelihood**: High (67K species, millions of occurrences)
- **Impact**: Delays in extraction, potential data gaps
- **Mitigation**:
  - Use batch exports to Drive (more quota-efficient)
  - Implement exponential backoff
  - Distribute across multiple days
  - Consider Cloud account upgrade if needed ($300 free credit)

**Risk 2: Occurrence Data Quality**
- **Likelihood**: Medium (occurrence data may have errors)
- **Impact**: Inaccurate embeddings for some species
- **Mitigation**:
  - Filter out low-quality occurrences (no coordinates, invalid years)
  - Use median instead of mean for robustness to outliers
  - Calculate p10/p90 to detect anomalies
  - Manual review of species with high embedding variance

**Risk 3: Database Performance**
- **Likelihood**: Medium (256 new columns × 67K species)
- **Impact**: Slow queries, increased storage
- **Mitigation**:
  - Use partial indexes (`WHERE A01_mean IS NOT NULL`)
  - Consider separate `species_embeddings` table
  - Compress old occurrence data
  - Optimize embedding similarity queries with spatial indexes

**Risk 4: Google Drive Storage Limits**
- **Likelihood**: Low (1.5GB estimate vs 15GB quota)
- **Impact**: Export failures if quota exceeded
- **Mitigation**:
  - Monitor Drive storage during extraction
  - Delete raw CSVs after aggregation
  - Compress archived data
  - Use multiple Google accounts if needed

### 7.2 Data Quality Risks

**Risk 5: Subspecies Without Occurrence Data**
- **Likelihood**: Certain (19,614 species lack occurrence data)
- **Impact**: No embeddings for ~29% of species
- **Mitigation**:
  - Inherit embeddings from parent species (e.g., subspecies gets species-level embedding)
  - Mark as "inherited" in metadata
  - Future: Generate synthetic occurrences based on range descriptions

**Risk 6: Temporal Mismatch**
- **Likelihood**: High (40% of occurrences pre-2017)
- **Impact**: Inaccurate temporal alignment
- **Mitigation**:
  - Acceptable for pilot (using 2017 as proxy)
  - Future: Use climate reanalysis data (ERA5) for pre-2017 occurrences
  - Document limitations in metadata

**Risk 7: AlphaEarth Band Interpretation**
- **Likelihood**: Medium (64 bands not fully documented by Google)
- **Impact**: Difficulty explaining results
- **Mitigation**:
  - Use embeddings as black-box features (valid for similarity)
  - Correlate bands with known environmental variables
  - Publish methodology transparently
  - Wait for Google to release band documentation

### 7.3 Project Risks

**Risk 8: Processing Time Overruns**
- **Likelihood**: Medium (estimate 2-3 days, could be 5-7)
- **Impact**: Delayed delivery
- **Mitigation**:
  - Start pilot early to refine estimates
  - Parallelize where possible
  - Accept partial completion (e.g., 80% species)
  - Resume from checkpoints after interruptions

**Risk 9: Code Bugs in Pipeline**
- **Likelihood**: High (complex pipeline, new codebase)
- **Impact**: Data corruption, extraction failures
- **Mitigation**:
  - Extensive testing with pilot batch (100 species)
  - Unit tests for critical functions
  - Validate outputs at each step
  - Checkpoint system allows re-running failed batches

**Risk 10: Insufficient Documentation**
- **Likelihood**: Medium (complex system, many components)
- **Impact**: Difficult to maintain/extend
- **Mitigation**:
  - Comprehensive README for pipeline
  - Inline code comments
  - API documentation for new endpoints
  - Data dictionary for embedding fields

---

## 8. Conclusion

### 8.1 Summary

This comprehensive assessment reveals that **Treekipedia is MORE COMPLETE than initially assessed**. Critical corrections:

1. **Apache Fuseki/GraphFlow Integration**: NOT missing - fully implemented with:
   - Python microservice (Flask API, 395 lines)
   - GraphFlow system (3,700 lines, OWL/RDF generation)
   - PostgreSQL→Fuseki sync (6.7M triples, 20-30 min)
   - Admin frontend (6 pages, 4 components, SPARQL editor)
   - Real-time progress streaming (Server-Sent Events)

2. **Actual Capabilities**:
   - ✅ 67,743 species with 115-field knowledge schema
   - ✅ 5.7M geohash tiles with STAC compliance
   - ✅ PostGIS spatial analysis (ecoregions, intact forests)
   - ✅ Admin portal for ontology management
   - ✅ RDF triple store with SPARQL queries
   - ✅ Google Sheets import for biodiversity data
   - ⚠️ AI research pipeline documented but not implemented
   - ⚠️ Blockchain integration partial

3. **Google Earth Engine Integration Strategy**:
   - Extract AlphaEarth embeddings (64 bands, 2017-2024)
   - Process 48,129 species with occurrence data
   - Generate 256 new fields per species (mean, std, p10, p90 × 64 bands)
   - Use Google Drive for intermediate storage (<5GB local)
   - Estimated 2-3 days for full extraction
   - Zero cost (within free tier quotas)

### 8.2 Next Steps

**Immediate (This Week)**:
1. Fix species search bug ([controllers/species.js:25](treekipedia/backend/controllers/species.js#L25))
2. Start GEE environment setup
3. Import occurrence data from Parquet file
4. Run database migration for 256 embedding columns

**Short Term (2 Weeks)**:
1. Implement `SpeciesEmbeddingPipeline` class
2. Run pilot extraction (100 species)
3. Validate embedding quality
4. Optimize pipeline for full scale

**Medium Term (1 Month)**:
1. Extract embeddings for all 48,129 species
2. Create backend API endpoints
3. Build frontend visualizations
4. Develop species similarity recommender

**Long Term (3 Months)**:
1. Implement diversity composition estimator
2. Create habitat suitability predictor
3. Add climate change impact analysis
4. Publish research paper on embedding-based biodiversity modeling

### 8.3 Final Recommendations

**For Stakeholders**:
- Treekipedia has a solid foundation (PostgreSQL + PostGIS + Fuseki)
- GraphFlow integration is production-ready (was incorrectly assessed)
- GEE embedding integration is feasible with zero cost
- Expected ROI: 256 new fields × 48K species = 12.3M new data points
- Enables advanced AI applications (similarity search, diversity estimation)

**For Developers**:
- Prioritize fixing the species search bug (high visibility issue)
- Test Python microservice thoroughly (port 5002 dependency)
- Document GraphFlow architecture (currently underdocumented)
- Add database indexes for performance (geohash queries slow)
- Consider separating `species_embeddings` table for scalability

**For Researchers**:
- GEE embeddings enable novel biodiversity analyses
- Methodology is transparent and reproducible
- Data will be openly accessible via API
- Potential for high-impact publications
- Collaboration opportunities with GEE team

---

## Appendices

### Appendix A: Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | Next.js | 15.2.3 | React framework |
| | React | 18.3.1 | UI library |
| | Tailwind CSS | 3.4.1 | Styling |
| | Leaflet | 1.9.4 | Maps |
| | React Query | 5.69.0 | State management |
| | Wagmi | 2.14.15 | Blockchain |
| **Backend** | Express.js | 4.21.2 | REST API |
| | Node.js | 18+ | Runtime |
| | Axios | 1.8.4 | HTTP client |
| | Multer | - | File uploads |
| **Python Microservice** | Flask | 2.3.3 | Web framework |
| | psycopg2 | 2.9.9 | PostgreSQL |
| | requests | 2.31.0 | HTTP client |
| | owlready2 | 0.34 | OWL ontology |
| | rdflib | 7.0.0 | RDF triples |
| | gspread | 5.12.0 | Google Sheets |
| **Database** | PostgreSQL | 17 | RDBMS |
| | PostGIS | 3.6 | Spatial extension |
| **Knowledge Graph** | Apache Fuseki | - | RDF triple store |
| **Blockchain** | Solidity | - | Smart contracts |
| | Base, Celo, OP, Arbitrum | - | Networks |
| **Cloud** | Google Earth Engine | - | Satellite data |
| | Google Drive | - | Storage |
| | Vercel | - | Frontend hosting |
| | Digital Ocean | - | Backend VM |

### Appendix B: Database Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         species                             │
├─────────────────────────────────────────────────────────────┤
│ taxon_id (PK)                                     BIGINT    │
│ species_scientific_name                           VARCHAR   │
│ family, genus, species                            VARCHAR   │
│ ... (115 existing columns) ...                               │
│                                                               │
│ --- New Embedding Columns (256 total) ---                   │
│ A01_mean, A01_std, A01_p10, A01_p90              NUMERIC    │
│ A02_mean, A02_std, A02_p10, A02_p90              NUMERIC    │
│ ... (A03-A63) ...                                            │
│ A64_mean, A64_std, A64_p10, A64_p90              NUMERIC    │
│                                                               │
│ embedding_extraction_date                         TIMESTAMP  │
│ embedding_occurrence_count                        INTEGER    │
│ embedding_year_range                              VARCHAR    │
└─────────────────────────────────────────────────────────────┘
                    │
                    │ 1:N
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    occurrence_data                          │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                           SERIAL    │
│ taxon_id (FK → species.taxon_id)                  BIGINT    │
│ latitude                                          NUMERIC   │
│ longitude                                         NUMERIC   │
│ year                                              INTEGER   │
│ source                                            VARCHAR   │
└─────────────────────────────────────────────────────────────┘
                    │
                    │ N:1 (spatial join)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│               geohash_species_tiles                         │
├─────────────────────────────────────────────────────────────┤
│ geohash_l7 (PK)                                   VARCHAR   │
│ species_data                                      JSONB     │
│ geometry                                          GEOMETRY  │
│ datetime                                          TIMESTAMP │
└─────────────────────────────────────────────────────────────┘
```

### Appendix C: API Endpoint Reference

**Full API documentation**: See `treekipedia/API.md`

**New Embedding Endpoints** (to be implemented):

```
GET /api/embeddings/:taxon_id
Description: Get 256 embedding statistics for a species
Response: {
  "taxon_id": 12345,
  "A01_mean": 0.123, "A01_std": 0.012, "A01_p10": 0.110, "A01_p90": 0.137,
  ...,
  "metadata": {
    "extraction_date": "2025-10-26T12:00:00Z",
    "occurrence_count": 120,
    "year_range": "2017-2024"
  }
}

GET /api/embeddings/similar/:taxon_id?limit=10&threshold=0.5
Description: Find species with similar environmental signatures
Response: [
  {
    "taxon_id": 67890,
    "species_scientific_name": "Quercus petraea",
    "embedding_distance": 0.12,
    "similarity_score": 0.88
  },
  ...
]

POST /api/embeddings/predict-diversity
Description: Predict species composition at unmapped locations
Body: {
  "coordinates": [[lng, lat], ...],
  "year": 2024,
  "limit": 50
}
Response: [
  {
    "species_scientific_name": "Quercus robur",
    "probability": 0.82,
    "embedding_distance": 0.15
  },
  ...
]

POST /api/embeddings/suitability
Description: Predict habitat suitability for a species at candidate locations
Body: {
  "taxon_id": 12345,
  "locations": [[lng, lat], ...],
  "year": 2024
}
Response: [
  {
    "location": [lng, lat],
    "suitability_score": 0.71,
    "embedding_distance": 0.23
  },
  ...
]
```

### Appendix D: GEE Code Examples

**Extract embedding for single point**:
```python
import ee
ee.Initialize()

def extract_embedding(lng, lat, year):
    """Extract 64-band embedding for a single point and year"""
    point = ee.Geometry.Point([lng, lat])

    embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
        .filterDate(f'{year}-01-01', f'{year}-12-31') \
        .filterBounds(point) \
        .first()

    sample = embeddings.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=10  # 10m resolution
    )

    return sample.getInfo()

# Usage
result = extract_embedding(-122.08, 37.42, 2024)
# Returns: {'A01': 0.123, 'A02': 0.456, ..., 'A64': 0.789}
```

**Batch extraction with export**:
```python
def export_embeddings_batch(occurrences_df, year, output_filename):
    """Export embeddings for multiple points to Google Drive"""

    # Create feature collection from occurrences
    features = []
    for _, row in occurrences_df.iterrows():
        point = ee.Geometry.Point([row['lng'], row['lat']])
        feature = ee.Feature(point, {
            'taxon_id': int(row['taxon_id']),
            'occ_year': int(row['year'])
        })
        features.append(feature)

    fc = ee.FeatureCollection(features)

    # Load embeddings for year
    embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
        .filterDate(f'{year}-01-01', f'{year}-12-31') \
        .first()

    # Sample embeddings at all points
    sampled = embeddings.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.first(),
        scale=10
    )

    # Export to Google Drive
    task = ee.batch.Export.table.toDrive(
        collection=sampled,
        description=output_filename,
        folder='treekipedia_embeddings',
        fileFormat='CSV'
    )

    task.start()
    return task

# Usage
import pandas as pd
occurrences = pd.read_sql("SELECT * FROM occurrence_data WHERE year = 2020 LIMIT 1000", conn)
task = export_embeddings_batch(occurrences, 2020, 'embeddings_2020_batch1')
print(f"Task started: {task.id}")
```

### Appendix E: Useful SQL Queries

**Find species needing embeddings**:
```sql
SELECT
  s.taxon_id,
  s.species_scientific_name,
  COUNT(o.id) as occurrence_count
FROM species s
LEFT JOIN occurrence_data o ON s.taxon_id = o.taxon_id
WHERE s.A01_mean IS NULL  -- No embeddings yet
  AND o.id IS NOT NULL     -- Has occurrence data
GROUP BY s.taxon_id, s.species_scientific_name
ORDER BY occurrence_count DESC;
```

**Embedding extraction progress**:
```sql
SELECT
  COUNT(*) FILTER (WHERE A01_mean IS NOT NULL) as species_with_embeddings,
  COUNT(*) FILTER (WHERE A01_mean IS NULL AND taxon_id IN (SELECT DISTINCT taxon_id FROM occurrence_data)) as species_pending,
  COUNT(*) FILTER (WHERE taxon_id NOT IN (SELECT DISTINCT taxon_id FROM occurrence_data)) as species_no_occurrences,
  COUNT(*) as total_species
FROM species;
```

**Species with highest embedding variance** (potential outliers):
```sql
SELECT
  taxon_id,
  species_scientific_name,
  A01_std, A02_std, A03_std,  -- Check first 3 bands
  (A01_std + A02_std + A03_std + ... + A64_std) as total_variance
FROM species
WHERE A01_mean IS NOT NULL
ORDER BY total_variance DESC
LIMIT 20;
```

**Find similar species** (Euclidean distance):
```sql
-- Find species similar to Quercus robur (taxon_id = 12345)
WITH target AS (
  SELECT A01_mean, A02_mean, A03_mean, ..., A64_mean
  FROM species
  WHERE taxon_id = 12345
)
SELECT
  s.taxon_id,
  s.species_scientific_name,
  SQRT(
    POWER(s.A01_mean - t.A01_mean, 2) +
    POWER(s.A02_mean - t.A02_mean, 2) +
    POWER(s.A03_mean - t.A03_mean, 2) +
    -- ... (repeat for A04-A64)
    POWER(s.A64_mean - t.A64_mean, 2)
  ) as embedding_distance
FROM species s, target t
WHERE s.A01_mean IS NOT NULL
  AND s.taxon_id != 12345
ORDER BY embedding_distance ASC
LIMIT 10;
```

---

**END OF ASSESSMENT**

**Document Revision**: 1.1 (Corrected)
**Last Updated**: October 26, 2025
**Contact**: For questions or clarifications, refer to project repository

---
