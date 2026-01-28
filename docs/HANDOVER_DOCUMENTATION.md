# Treekipedia GraphFlow - Complete Handover Documentation

**Version:** 2.0.0
**Last Updated:** January 2026
**Repository:** https://github.com/SilviProtocol/silvi

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Quick Start Guide](#3-quick-start-guide)
4. [Installation & Setup](#4-installation--setup)
5. [Configuration](#5-configuration)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [Core Components](#8-core-components)
9. [Scripts & Automation](#9-scripts--automation)
10. [Frontend Templates](#10-frontend-templates)
11. [Data Flow](#11-data-flow)
12. [Maintenance & Operations](#12-maintenance--operations)
13. [Troubleshooting](#13-troubleshooting)
14. [Security Considerations](#14-security-considerations)
15. [SQL Reference](#15-sql-reference)

---

## 1. Project Overview

### What is Treekipedia GraphFlow?

Treekipedia GraphFlow is a biodiversity ontology automation platform that:

- **Transforms** raw biodiversity data (CSV, Google Sheets, PostgreSQL) into OWL ontologies
- **Stores** data as RDF triples in Apache Jena Fuseki triplestore
- **Manages** geospatial occurrence data using GeoParquet + DuckDB
- **Provides** a web interface for data import, ontology generation, and version management

### Key Features

| Feature | Description |
|---------|-------------|
| Multi-source Import | CSV files, Google Sheets, PostgreSQL database |
| Automatic Ontology Generation | Detects 25+ biodiversity field patterns |
| Incremental Sync | Only processes new/changed data |
| SPARQL Endpoint | Query data via standard SPARQL |
| Geospatial Support | GeoParquet storage with spatial queries |
| Version Management | Track changes and compare versions |

### Tech Stack

- **Backend:** Python 3.11, Flask 2.3
- **Database:** PostgreSQL 15
- **Triplestore:** Apache Jena Fuseki 4.x
- **Geospatial:** GeoParquet, DuckDB, Shapely
- **Frontend:** HTML5, CSS3, JavaScript, Leaflet.js
- **Deployment:** Docker, Gunicorn, systemd

---

## 2. Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
├─────────────┬─────────────────────┬─────────────────────────────┤
│   CSV       │   Google Sheets     │      PostgreSQL              │
│   Upload    │   (gspread API)     │      (psycopg2)              │
└──────┬──────┴──────────┬──────────┴──────────────┬───────────────┘
       │                 │                         │
       └─────────────────┼─────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK APPLICATION                             │
│                       (app.py)                                   │
├─────────────────────────────────────────────────────────────────┤
│  routes_main.py    │  routes_api.py    │  routes_occurrence.py   │
│  (Web Interface)   │  (REST API)       │  (Geospatial Data)      │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CORE PROCESSORS                               │
├─────────────────────────────────────────────────────────────────┤
│  MultiSheetBiodiversityGenerator  │  OccurrenceDataManager      │
│  (Ontology Generation)            │  (GeoParquet Processing)    │
├───────────────────────────────────┴─────────────────────────────┤
│  PostgreSQLFusekiSync  │  IncrementalOntologyUpdater            │
│  (Database Sync)       │  (Fuseki Updates)                      │
└─────────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Apache Fuseki      │    │   File Storage       │
│   (RDF Triplestore)  │    │   (GeoParquet)       │
│   Port: 3030         │    │   data/occurrences/  │
└──────────────────────┘    └──────────────────────┘
```

### Directory Structure

```
biodiversity-ontology-automation/
├── app.py                      # Flask application entry point
├── wsgi.py                     # WSGI server entry point
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Multi-container setup
│
├── src/                        # Source code modules
│   ├── core/
│   │   ├── config.py           # Application configuration
│   │   ├── multi_sheet_generator.py  # Ontology generation engine
│   │   ├── occurrence_manager.py     # GeoParquet data manager
│   │   ├── postgres_automation.py    # PostgreSQL monitoring
│   │   └── sheets_integration.py     # Google Sheets API
│   ├── routes/
│   │   ├── main.py             # Web interface routes
│   │   ├── api.py              # REST API endpoints
│   │   └── occurrence.py       # Occurrence data routes
│   └── utils.py                # Utility functions
│
├── scripts/                    # Automation scripts
│   ├── postgres_to_fuseki_sync.py    # Full database sync
│   ├── sync_species_fuseki.py        # Species-specific sync
│   ├── incremental_ontology_updater.py
│   └── ...
│
├── templates/                  # HTML templates
│   ├── index.html              # Main landing page
│   ├── success.html            # Generation results
│   ├── import_sheets.html      # Google Sheets import
│   └── ...
│
├── static/                     # Static assets (CSS, JS)
├── config/                     # Configuration files
├── data/                       # Data storage
│   └── occurrences/            # GeoParquet files
├── docs/                       # Documentation
└── deployment/                 # Deployment configs
```

---

## 3. Quick Start Guide

### For Users (Web Interface)

1. **Access the application:** Open `http://localhost:5001` in your browser

2. **Upload CSV Data:**
   - Click "Upload CSV" on the home page
   - Select your biodiversity CSV file(s)
   - Enter an ontology name
   - Click "Generate Ontology"

3. **Import from Google Sheets:**
   - Click "Import from Sheets"
   - Enter the Spreadsheet ID or name
   - Select worksheets to import
   - Generate ontology

4. **Query Data:**
   - Access Fuseki UI: `http://localhost:3030`
   - Use SPARQL queries on the `treekipedia` dataset

### For Developers (Local Setup)

```bash
# Clone repository
git clone https://github.com/SilviProtocol/silvi.git
cd silvi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run development server
python app.py

# Or run with Docker
docker-compose up -d
```

---

## 4. Installation & Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Apache Jena Fuseki 4.x
- Docker & Docker Compose (optional)

### Option 1: Docker Installation (Recommended)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f web
```

### Option 2: Manual Installation

#### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### Step 2: Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb treekipedia
sudo -u postgres psql -c "CREATE USER treekipedia WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE treekipedia TO treekipedia;"
```

#### Step 3: Install Apache Fuseki

```bash
# Download Fuseki
wget https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-4.10.0.tar.gz
tar -xzf apache-jena-fuseki-4.10.0.tar.gz
cd apache-jena-fuseki-4.10.0

# Start Fuseki
./fuseki-server --update --mem /treekipedia
```

#### Step 4: Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

#### Step 5: Run Application

```bash
# Development
python app.py

# Production
gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 120 wsgi:app
```

---

## 5. Configuration

### Environment Variables (.env)

```bash
# ===========================================
# APPLICATION SETTINGS
# ===========================================
FLASK_ENV=production          # development | production
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-change-in-production
PORT=5001
HOST=0.0.0.0
WORKERS=4

# ===========================================
# POSTGRESQL DATABASE
# ===========================================
POSTGRES_HOST=167.172.143.162
POSTGRES_PORT=5432
POSTGRES_DB=treekipedia
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# ===========================================
# APACHE FUSEKI (TRIPLESTORE)
# ===========================================
FUSEKI_HOST=167.172.143.162
FUSEKI_PORT=3030
FUSEKI_DATASET=treekipedia
FUSEKI_USERNAME=treekipedia
FUSEKI_PASSWORD=your_fuseki_password
FUSEKI_ENABLED=True

# ===========================================
# GOOGLE SHEETS INTEGRATION
# ===========================================
GOOGLE_SHEETS_ENABLED=True
GOOGLE_SERVICE_ACCOUNT_FILE=config/service_account.json

# ===========================================
# OCCURRENCE DATA
# ===========================================
OCCURRENCE_STORAGE_PATH=data/occurrences
MAX_UPLOAD_SIZE_MB=2048

# ===========================================
# LOGGING
# ===========================================
LOG_LEVEL=INFO
LOG_FILE=app.log
```

### Fuseki Configuration (fuseki_config.json)

```json
{
  "fuseki": {
    "base_url": "http://167.172.143.162:3030",
    "dataset": "treekipedia",
    "sparql_endpoint": "http://167.172.143.162:3030/treekipedia/sparql",
    "update_endpoint": "http://167.172.143.162:3030/treekipedia/update",
    "data_endpoint": "http://167.172.143.162:3030/treekipedia/data"
  },
  "postgresql": {
    "db_connection": {
      "host": "167.172.143.162",
      "database": "treekipedia",
      "port": 5432
    }
  }
}
```

---

## 6. Database Schema

### PostgreSQL Tables

#### species (Primary Table - 67,927 rows)

```sql
-- Core identification
taxon_id            TEXT PRIMARY KEY
species_scientific_name  VARCHAR(255)
accepted_scientific_name TEXT
common_name         TEXT

-- Taxonomic hierarchy
family              VARCHAR(100)
genus               VARCHAR(100)
class               VARCHAR(100)
taxonomic_order     VARCHAR(100)
subspecies          TEXT

-- Species traits
maximum_height_ai   TEXT
maximum_height_human TEXT
maximum_diameter_ai TEXT
maximum_diameter_human TEXT
growth_form_ai      VARCHAR(50)
growth_form_human   VARCHAR(50)
leaf_type_ai        VARCHAR(50)
leaf_type_human     VARCHAR(50)
bark_characteristics_ai TEXT
bark_characteristics_human TEXT
tolerances          TEXT

-- Geographic distribution
ecoregions          TEXT
bioregions          TEXT
biomes              TEXT
countries_native    TEXT
countries_introduced TEXT
countries_invasive  TEXT
habitat_ai          TEXT
habitat_human       TEXT

-- Ecological relationships
ecological_function_ai TEXT
ecological_function_human TEXT
compatible_soil_types_ai TEXT
compatible_soil_types_human TEXT
elevation_ranges_ai TEXT
elevation_ranges_human TEXT
soil_texture_all    TEXT
ph_prefered         TEXT
climate_type_koppengeiger TEXT

-- Agroforestry
agroforestry_use_cases_ai TEXT
agroforestry_use_cases_human TEXT
timber_value        TEXT
non_timber_products TEXT

-- Carbon/Allometric
allometric_models   TEXT
allometric_curve    TEXT

-- Metadata
updated_at          TIMESTAMP
created_at          TIMESTAMP
```

#### Other Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `users` | 11 | User accounts |
| `countries` | 242 | Country reference data |
| `ecoregions` | 847 | Ecoregion definitions |
| `sponsorships` | 34 | Species sponsorships |
| `sponsorship_items` | 34 | Sponsorship details |
| `contreebution_nfts` | 21 | NFT tracking |
| `geohash_species_tiles` | 6.4M | Geospatial index |

### Fuseki Triple Store

**Dataset:** `treekipedia`

**Named Graphs:**
- `http://treekipedia.org/species/` - Species data
- `http://treekipedia.org/users/` - User data
- `http://treekipedia.org/ontology/` - Ontology definitions

**Current Statistics:**
- Total Triples: ~3.7 million
- Species Entities: 67,927

---

## 7. API Reference

### System Status

#### GET /api/system-status-fuseki
Returns system health and connection status.

**Response:**
```json
{
  "status": "healthy",
  "fuseki": {
    "connected": true,
    "endpoint": "http://167.172.143.162:3030/treekipedia/sparql",
    "triple_count": 3723610
  },
  "postgresql": {
    "connected": true,
    "host": "167.172.143.162"
  }
}
```

#### GET /health
Basic health check.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-01-24T12:00:00Z"
}
```

### Data Sync

#### POST /postgres-sync-fuseki
Sync PostgreSQL table to Fuseki.

**Request:**
```json
{
  "table_name": "species",
  "batch_size": 1000
}
```

**Response:**
```json
{
  "success": true,
  "records_synced": 67927,
  "triples_created": 3723610,
  "duration_seconds": 1792.8
}
```

#### POST /postgres-table-info
Get table metadata.

**Request:**
```json
{
  "table_name": "species"
}
```

**Response:**
```json
{
  "table_name": "species",
  "row_count": 67927,
  "columns": ["taxon_id", "family", "genus", ...],
  "primary_key": "taxon_id"
}
```

### Ontology Generation

#### POST /upload
Upload CSV and generate ontology.

**Request:** `multipart/form-data`
- `files`: CSV file(s)
- `ontology_name`: Name for the ontology

**Response:**
```json
{
  "success": true,
  "session_id": "abc123",
  "ontology_file": "biodiversity_ontology.owl",
  "triple_count": 15000,
  "download_url": "/download-ontology/abc123"
}
```

#### GET /download-ontology/{session_id}
Download generated OWL file.

### Google Sheets

#### POST /import-from-sheets
Import from Google Sheets.

**Request:**
```json
{
  "spreadsheet_id": "1abc...",
  "ontology_name": "my_ontology"
}
```

#### GET /spreadsheet-metadata
Get spreadsheet information.

**Query Parameters:**
- `spreadsheet_id` or `spreadsheet_name`

### Occurrence Data

#### POST /occurrence/api/query
Spatial query for occurrences.

**Request:**
```json
{
  "version": "1.0.0",
  "bbox": [-122.5, 37.5, -122.0, 38.0],
  "species": "Quercus agrifolia",
  "limit": 1000
}
```

#### GET /occurrence/api/statistics/{version}
Get version statistics.

---

## 8. Core Components

### MultiSheetBiodiversityGenerator

**Location:** `src/core/multi_sheet_generator.py`

**Purpose:** Core ontology generation engine that transforms tabular data into OWL ontologies.

**Field Detection Patterns:**

| Category | Detected Fields |
|----------|-----------------|
| Taxonomic | taxon_id, species, family, genus, order, class, kingdom |
| Geographic | countries_native, countries_introduced, distribution, bioregions, ecoregions |
| Ecological | biomes, habitat, elevation, ecological_function |
| Conservation | conservation_status, threats, climate_vulnerability |
| Morphological | height, diameter, growth_form, leaf_type |
| Economic | timber_value, non_timber, agroforestry |
| Cultural | cultural_significance, traditional_uses |
| Management | stewardship, planting, maintenance |

**Generated Ontology Classes:**

1. `TaxonomicRank` - Species classification
2. `GeographicDistribution` - Location data
3. `EcologicalInformation` - Ecosystem relationships
4. `ConservationInformation` - Conservation status
5. `MorphologicalCharacteristics` - Physical traits
6. `EconomicValue` - Economic uses
7. `CulturalSignificance` - Cultural importance
8. `ManagementInformation` - Care instructions

### OccurrenceDataManager

**Location:** `src/core/occurrence_manager.py`

**Purpose:** Manages geospatial occurrence data using GeoParquet format.

**Key Methods:**

```python
# Convert CSV to GeoParquet
manager.convert_to_geoparquet(
    input_file="occurrences.csv",
    latitude_col="decimalLatitude",
    longitude_col="decimalLongitude"
)

# Query occurrences
results = manager.query_occurrences(
    version="1.0.0",
    bbox=[-122.5, 37.5, -122.0, 38.0],
    species="Quercus agrifolia"
)

# Compare versions
diff = manager.compare_versions("1.0.0", "2.0.0")
```

### PostgreSQLFusekiSync

**Location:** `scripts/postgres_to_fuseki_sync.py`

**Purpose:** Synchronizes PostgreSQL data to Fuseki triplestore.

**Usage:**

```bash
# Test connections
python scripts/postgres_to_fuseki_sync.py --test

# Sync specific tables
python scripts/postgres_to_fuseki_sync.py --tables species users

# Sync all tables
python scripts/postgres_to_fuseki_sync.py

# Custom batch size
python scripts/postgres_to_fuseki_sync.py --batch-size 500
```

---

## 9. Scripts & Automation

### Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `postgres_to_fuseki_sync.py` | Full database sync | `python scripts/postgres_to_fuseki_sync.py` |
| `sync_species_fuseki.py` | Species-only sync | `python scripts/sync_species_fuseki.py` |
| `incremental_ontology_updater.py` | Incremental updates | `python scripts/incremental_ontology_updater.py` |
| `incremental_species_sync.py` | Incremental species sync | `python scripts/incremental_species_sync.py` |
| `csv_importer.py` | Import CSV to Sheets | `python scripts/csv_importer.py` |
| `migrate.py` | Blazegraph to Fuseki migration | `python scripts/migrate.py` |

### Automated Sync Example

```bash
#!/bin/bash
# cron_sync.sh - Run daily at 2 AM

cd /opt/treekipedia
source venv/bin/activate

# Sync species data
python scripts/sync_species_fuseki.py >> logs/sync.log 2>&1

# Verify sync
python -c "
import requests
r = requests.post(
    'http://localhost:3030/treekipedia/sparql',
    data={'query': 'SELECT (COUNT(*) as ?c) WHERE {?s a <http://treekipedia.org/ontology/Species>}'},
    headers={'Accept': 'application/json'}
)
print(f'Species count: {r.json()[\"results\"][\"bindings\"][0][\"c\"][\"value\"]}')
"
```

Add to crontab:
```bash
0 2 * * * /opt/treekipedia/cron_sync.sh
```

---

## 10. Frontend Templates

### Template Overview

| Template | Route | Purpose |
|----------|-------|---------|
| `index.html` | `/` | Main landing page with import options |
| `success.html` | `/upload` | Display generation results |
| `import_sheets.html` | `/import-from-sheets` | Google Sheets import interface |
| `version_management.html` | `/version-management` | Version history and comparison |
| `occurrence_unified.html` | `/occurrence/` | Occurrence data dashboard |
| `occurrence_map.html` | `/occurrence/map` | Interactive map visualization |

### Customizing Templates

Templates use Jinja2 templating with these global variables:

```python
# Available in all templates
{{ fuseki_enabled }}      # Boolean
{{ sheets_enabled }}      # Boolean
{{ occurrence_enabled }}  # Boolean
{{ current_version }}     # String
```

---

## 11. Data Flow

### CSV to Fuseki Flow

```
1. User uploads CSV via /upload
        ↓
2. File saved to Uploads/{session_id}/
        ↓
3. MultiSheetBiodiversityGenerator analyzes data
   - Detects field patterns
   - Infers data types
   - Generates quality score
        ↓
4. OWL ontology generated
   - Classes created based on detected fields
   - Properties defined
   - Individuals created from enumerations
        ↓
5. Ontology saved to session folder
        ↓
6. (Optional) Import to Fuseki
   - IncrementalOntologyUpdater checks existing triples
   - Only new triples uploaded
   - Named graph created with timestamp
        ↓
7. User can download OWL or query via SPARQL
```

### PostgreSQL to Fuseki Flow

```
1. API call to /postgres-sync-fuseki
        ↓
2. PostgreSQLFusekiSync connects to database
        ↓
3. Query table data in batches (default: 1000 rows)
        ↓
4. For each batch:
   a. Convert rows to RDF triples
   b. Format as N-Triples
   c. POST to Fuseki /data endpoint
        ↓
5. Verify upload success
        ↓
6. Return summary with triple count
```

---

## 12. Maintenance & Operations

### Daily Operations

```bash
# Check system status
curl http://localhost:5001/api/system-status-fuseki

# View logs
tail -f app.log

# Check Fuseki triple count
curl -X POST http://localhost:3030/treekipedia/sparql \
  -d "query=SELECT (COUNT(*) as ?c) WHERE {?s ?p ?o}" \
  -H "Accept: application/json"
```

### Backup Procedures

#### PostgreSQL Backup
```bash
pg_dump -h localhost -U postgres treekipedia > backup_$(date +%Y%m%d).sql
```

#### Fuseki Backup
```bash
# Stop Fuseki first
docker-compose stop fuseki

# Backup data directory
tar -czf fuseki_backup_$(date +%Y%m%d).tar.gz fuseki-data/

# Restart
docker-compose start fuseki
```

### Performance Tuning

#### Fuseki JVM Memory
Edit `docker-compose.yml`:
```yaml
fuseki:
  environment:
    - JVM_ARGS=-Xmx4g  # Increase from 2g to 4g
```

#### Gunicorn Workers
Edit `start-production.sh`:
```bash
gunicorn --workers 8 --timeout 180 wsgi:app
```

#### PostgreSQL Connection Pool
Edit connection settings in scripts:
```python
conn = psycopg2.connect(
    **config,
    connect_timeout=30,
    options='-c statement_timeout=300000'
)
```

---

## 13. Troubleshooting

### Common Issues

#### Fuseki Connection Failed
```
Error: Fuseki connection failed (HTTP 401)
```
**Solution:** Check FUSEKI_USERNAME and FUSEKI_PASSWORD in .env

#### PostgreSQL Timeout
```
Error: statement_timeout exceeded
```
**Solution:** Reduce batch size or increase timeout:
```python
options='-c statement_timeout=600000'  # 10 minutes
```

#### Out of Memory
```
Error: MemoryError during RDF conversion
```
**Solution:** Process in smaller batches:
```bash
python scripts/postgres_to_fuseki_sync.py --batch-size 500
```

#### Session Expired
```
Error: Session not found
```
**Solution:** Sessions expire after 1 hour. Re-upload data or extend SESSION_EXPIRY in config.

### Log Locations

| Log | Location | Content |
|-----|----------|---------|
| Application | `app.log` | Flask application logs |
| Gunicorn Access | `logs/access.log` | HTTP requests |
| Gunicorn Error | `logs/error.log` | Application errors |
| Sync Operations | stdout | Real-time sync progress |

### Health Check Commands

```bash
# Check all services
docker-compose ps

# Test PostgreSQL
psql -h localhost -U postgres -d treekipedia -c "SELECT 1"

# Test Fuseki
curl http://localhost:3030/$/ping

# Test Application
curl http://localhost:5001/health
```

---

## 14. Security Considerations

### Credentials Management

**NEVER** hardcode credentials. Always use environment variables:

```python
# WRONG
password = "9353jeremic"

# RIGHT
password = os.environ.get('POSTGRES_PASSWORD')
```

### Required Secrets

| Secret | Storage | Purpose |
|--------|---------|---------|
| `POSTGRES_PASSWORD` | .env | Database access |
| `FUSEKI_PASSWORD` | .env | Triplestore access |
| `SECRET_KEY` | .env | Session encryption |
| `service_account.json` | config/ | Google Sheets API |

### Network Security

- PostgreSQL: Restrict to known IPs via `pg_hba.conf`
- Fuseki: Enable authentication for all endpoints
- Flask: Run behind reverse proxy (nginx) in production

### File Upload Security

- Maximum size: 2GB (configurable)
- Allowed types: CSV, XLSX, Parquet
- Files sanitized before storage

---

## 15. SQL Reference

This section documents the SQL queries used throughout the application, demonstrating SQL knowledge for database operations.

### Schema Introspection Queries

```sql
-- Get all tables in database
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Get columns for a table
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'species' AND table_schema = 'public'
ORDER BY ordinal_position;

-- Get primary key columns
SELECT column_name
FROM information_schema.key_column_usage
WHERE table_name = 'species' AND constraint_name LIKE '%_pkey'
ORDER BY ordinal_position;

-- Get approximate row count (fast)
SELECT schemaname, tablename, n_tup_ins - n_tup_del as approx_count
FROM pg_stat_user_tables
WHERE tablename = 'species';
```

### Data Retrieval Queries

```sql
-- Get species count
SELECT COUNT(*) FROM species;

-- Paginated species retrieval
SELECT * FROM species
ORDER BY taxon_id
OFFSET 0 LIMIT 5000;

-- Get species with specific columns
SELECT taxon_id, family, genus, species_scientific_name,
       ecoregions, countries_native, agroforestry_use_cases_ai
FROM species
WHERE family IS NOT NULL
ORDER BY family, genus;

-- Filter by taxonomic hierarchy
SELECT * FROM species
WHERE family = 'Fabaceae'
  AND genus LIKE 'Acacia%'
ORDER BY species_scientific_name;
```

### Aggregation Queries

```sql
-- Count species by family
SELECT family, COUNT(*) as species_count
FROM species
WHERE family IS NOT NULL
GROUP BY family
ORDER BY species_count DESC
LIMIT 20;

-- Count species by conservation status
SELECT conservation_status_ai, COUNT(*) as count
FROM species
GROUP BY conservation_status_ai
ORDER BY count DESC;

-- Get unique ecoregions
SELECT DISTINCT unnest(string_to_array(ecoregions, ',')) as ecoregion
FROM species
WHERE ecoregions IS NOT NULL;
```

### Join Queries

```sql
-- Get primary key info with system tables
SELECT a.attname
FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid
  AND a.attnum = ANY(i.indkey)
WHERE i.indrelid = 'species'::regclass
  AND i.indisprimary;

-- Get column details with constraints
SELECT c.column_name, c.data_type, c.is_nullable,
       tc.constraint_type
FROM information_schema.columns c
LEFT JOIN information_schema.key_column_usage kcu
  ON c.column_name = kcu.column_name
  AND c.table_name = kcu.table_name
LEFT JOIN information_schema.table_constraints tc
  ON kcu.constraint_name = tc.constraint_name
WHERE c.table_name = 'species';
```

### Update and Insert (for reference)

```sql
-- Update species record
UPDATE species
SET updated_at = NOW(),
    conservation_status_ai = 'Vulnerable'
WHERE taxon_id = 'ABC123';

-- Insert new species
INSERT INTO species (taxon_id, species_scientific_name, family, genus)
VALUES ('NEW001', 'Quercus example', 'Fagaceae', 'Quercus');

-- Upsert pattern
INSERT INTO species (taxon_id, species_scientific_name)
VALUES ('ABC123', 'Updated Name')
ON CONFLICT (taxon_id)
DO UPDATE SET species_scientific_name = EXCLUDED.species_scientific_name,
              updated_at = NOW();
```

### Performance Optimization

```sql
-- Use TABLESAMPLE for large tables
SELECT * FROM species
TABLESAMPLE SYSTEM (1.0)  -- 1% sample
LIMIT 1000;

-- Create indexes for common queries
CREATE INDEX idx_species_family ON species(family);
CREATE INDEX idx_species_genus ON species(genus);
CREATE INDEX idx_species_updated ON species(updated_at);

-- Analyze table for query planner
ANALYZE species;
```

---

## Contact & Support

For issues or questions:
- **Repository:** https://github.com/SilviProtocol/silvi
- **Issues:** https://github.com/SilviProtocol/silvi/issues

---

**Document Version:** 1.0
**Last Updated:** January 2026
**Author:** Treekipedia Development Team
