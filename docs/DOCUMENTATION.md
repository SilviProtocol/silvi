# 🌲 Treekipedia GraphFlow

## Complete Platform Documentation

**Version:** 2.0.0-dynamic
**Last Updated:** October 8, 2025

---

## 📖 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Pipeline](#data-pipeline)
5. [Installation & Setup](#installation--setup)
6. [User Guide](#user-guide)
7. [API Reference](#api-reference)
8. [Development Guide](#development-guide)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

---

## Overview

### What is Treekipedia GraphFlow?

Treekipedia GraphFlow is a **comprehensive biodiversity data management platform** that transforms structured data from multiple sources into semantically rich OWL ontologies and stores them in a graph database (Apache Jena Fuseki).

### Key Capabilities

🔄 **Multi-Source Data Integration**
- Google Sheets (collaborative editing)
- PostgreSQL databases (enterprise scale)
- CSV files (quick imports)

🧠 **Intelligent Ontology Generation**
- Automatic field detection (120+ biodiversity patterns)
- Smart categorization into 8 ontology classes
- Transposed format support
- Option set enumeration handling

🗄️ **Triple Store Management**
- Apache Jena Fuseki integration
- Direct SPARQL endpoint access
- Incremental updates
- Version management

📊 **Data Quality & Monitoring**
- Real-time system health checks
- Completeness scoring
- Change detection
- Automated validation

### Use Cases

- **Biodiversity Research**: Manage taxonomic, ecological, and conservation data
- **Tree Species Cataloging**: Process 50,000+ tree species with structured metadata
- **Environmental Monitoring**: Track geographic distribution and conservation status
- **Data Integration**: Unify data from spreadsheets, databases, and APIs
- **Knowledge Graphs**: Build semantic relationships for biodiversity informatics

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Web    │  │  Import  │  │ Monitor  │  │ Version  │       │
│  │Dashboard │  │  Sheets  │  │PostgreSQL│  │  Mgmt    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK APPLICATION                            │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Main Routes (routes_main.py)             │      │
│  │  • File uploads  • Sheet imports  • Ontology gen     │      │
│  └──────────────────────────────────────────────────────┘      │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              API Routes (routes_api.py)               │      │
│  │  • System status  • Version mgmt  • Health checks    │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PROCESSING LAYER                            │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │ Multi-Sheet Bio      │  │ Sheets Integration   │           │
│  │ Generator            │  │ (Google API)         │           │
│  │                      │  │                      │           │
│  │ • Field analysis     │  │ • OAuth2 auth        │           │
│  │ • Categorization     │  │ • Change detection   │           │
│  │ • OWL generation     │  │ • Version tracking   │           │
│  └──────────────────────┘  └──────────────────────┘           │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │ PostgreSQL RDF       │  │ Incremental Updater  │           │
│  │ Converter            │  │                      │           │
│  │                      │  │ • Change detection   │           │
│  │ • Table scanning     │  │ • Partial updates    │           │
│  │ • RDF generation     │  │ • Sync management    │           │
│  └──────────────────────┘  └──────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Apache     │  │  PostgreSQL  │  │    Local     │         │
│  │   Fuseki     │  │   Database   │  │  File Store  │         │
│  │              │  │              │  │              │         │
│  │ • SPARQL     │  │ • Species    │  │ • CSV files  │         │
│  │ • Update     │  │ • Taxonomy   │  │ • OWL files  │         │
│  │ • Query      │  │ • Metadata   │  │ • Metadata   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend**
- **Python 3.8+**: Core application
- **Flask**: Web framework
- **Owlready2**: OWL ontology manipulation
- **gspread**: Google Sheets API client
- **psycopg2**: PostgreSQL adapter
- **requests**: HTTP client for Fuseki

**Frontend**
- **Bootstrap 5**: UI framework
- **Font Awesome 6**: Icons
- **Vanilla JavaScript**: Interactivity
- **Custom CSS**: Treekipedia unified theme

**Data Storage**
- **Apache Jena Fuseki**: Triple store (SPARQL endpoint)
- **PostgreSQL**: Relational data storage
- **File System**: Temporary file storage, metadata

**External Services**
- **Google Sheets API**: Collaborative data editing
- **Google Cloud Platform**: Service account authentication

---

## Core Components

### 1. Multi-Sheet Biodiversity Generator

**File**: `multi_sheet_biodiversity_generator.py`

The heart of the ontology generation system.

#### Features

- **Automatic Format Detection**
  ```python
  # Detects three formats automatically:
  # 1. Direct Schema: Column names are field definitions
  # 2. Transposed: Field names in rows (120 rows × 1 column)
  # 3. MVP Format: Traditional metadata sheet
  ```

- **Field Analysis**
  - 120+ biodiversity field patterns
  - Smart categorization
  - Data type inference
  - Constraint extraction

- **Ontology Classes**
  ```python
  ONTOLOGY_CLASSES = {
      'TaxonomicRank': ['species', 'genus', 'family', 'order', 'class'],
      'GeographicDistribution': ['countries', 'ecoregions', 'biomes'],
      'EcologicalInformation': ['habitat', 'elevation', 'soil_types'],
      'ConservationInformation': ['iucn_status', 'threats'],
      'MorphologicalCharacteristics': ['height', 'diameter', 'leaf_type'],
      'EconomicValue': ['timber_value', 'agroforestry'],
      'CulturalSignificance': ['traditional_uses'],
      'ManagementInformation': ['stewardship', 'planting']
  }
  ```

#### Key Methods

```python
# Analyze multi-sheet directory
def analyze_multi_sheet_directory(directory_path: str) -> Dict[str, Any]

# Handle direct schema format (your use case!)
def analyze_direct_schema(schema_file: str, option_set_file: str) -> Dict[str, Any]

# Generate OWL ontology
def create_enhanced_ontology(analysis: Dict, ontology_name: str) -> Ontology

# Complete pipeline
def generate_enhanced_ontology_from_directory(directory: str, name: str) -> str
```

### 2. Google Sheets Integration

**File**: `sheets_integration.py`

#### Capabilities

- **OAuth2 Authentication**: Service account-based
- **Sheet Operations**:
  - Open by ID or name
  - Read worksheet data
  - Get metadata (actual row/column counts)
  - Version management
- **Change Detection**: Compare current vs. last processed version
- **Multi-sheet Support**: Process multiple worksheets

#### Usage Example

```python
from sheets_integration import SheetsIntegration

# Initialize
sheets = SheetsIntegration('service_account.json')

# Open spreadsheet
spreadsheet = sheets.open_spreadsheet(spreadsheet_name='TreeSheet')

# Get metadata
metadata = sheets.get_spreadsheet_metadata(spreadsheet)
# Returns: {title, id, worksheets: [{title, row_count, col_count}], version_info}

# Read data
data = sheets.get_worksheet_data(spreadsheet, worksheet_name='species')
# Returns: List[Dict] - rows as dictionaries
```

### 3. PostgreSQL RDF Converter

**File**: `postgres_rdf_converter.py`

Converts PostgreSQL tables to RDF triples.

#### Features

- **Table Scanning**: Automatic table discovery
- **Schema Mapping**: Column → RDF property mapping
- **Type Detection**: Infer XSD data types
- **Incremental Updates**: Only process changed rows
- **Batch Processing**: Handle large datasets efficiently

#### Configuration

```python
POSTGRESQL_CONFIG = {
    'host': '167.172.143.162',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': '***',
    'port': 5432
}
```

### 4. Flask Routes

#### Main Routes (`routes_main.py`)

- **`/`** - Dashboard home
- **`/upload`** - CSV file upload
- **`/import-from-sheets`** - Google Sheets import
- **`/preview-multi-sheet-ontology`** - Preview before generation
- **`/success/<session_id>`** - Generation success page

#### API Routes (`routes_api.py`)

- **`/api/system-status`** - Check all integrations
- **`/system-health`** - Detailed health metrics
- **`/spreadsheet-metadata`** - Get sheet info
- **`/postgres-monitor`** - PostgreSQL monitoring dashboard
- **`/version-management`** - Track data versions
- **`/run-full-automation`** - Trigger complete pipeline

### 5. Automation Scripts

**Directory**: `scripts/`

- **`treekipedia_pipeline.py`**: Complete automation workflow
- **`automation_script.py`**: Scheduled task runner
- **`blazegraph_data_cleaner.py`**: Cleanup utilities

---

## Data Pipeline

### Pipeline Workflow

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: DATA ACQUISITION                                     │
├──────────────────────────────────────────────────────────────┤
│  ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│  │  Google   │    │PostgreSQL │    │CSV Upload │           │
│  │  Sheets   │───▶│  Query    │◀───│           │           │
│  └───────────┘    └───────────┘    └───────────┘           │
│         │               │                 │                  │
│         └───────────────┴─────────────────┘                  │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 2: FORMAT DETECTION                                     │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐             │
│  │ Analyze sheet structure:                    │             │
│  │  • Check column names                       │             │
│  │  • Detect transposed format (1 col, N rows)│             │
│  │  • Identify MVP vs Direct schema            │             │
│  └────────────────────────────────────────────┘             │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 3: FIELD ANALYSIS                                       │
├──────────────────────────────────────────────────────────────┤
│  For each field:                                             │
│  ┌────────────────────────────────────────────┐             │
│  │ 1. Pattern matching (120+ patterns)        │             │
│  │ 2. Category determination                   │             │
│  │ 3. Data type inference                      │             │
│  │ 4. Option set linkage                       │             │
│  │ 5. Constraint extraction                    │             │
│  └────────────────────────────────────────────┘             │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 4: ONTOLOGY CONSTRUCTION                                │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐             │
│  │ Create OWL components:                      │             │
│  │  • Classes (8 ontology classes)            │             │
│  │  • Data properties (fields)                 │             │
│  │  • Object properties (relationships)        │             │
│  │  • Individuals (option set values)          │             │
│  │  • Constraints & restrictions               │             │
│  └────────────────────────────────────────────┘             │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 5: QUALITY ASSESSMENT                                   │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐             │
│  │ Calculate metrics:                          │             │
│  │  • Completeness score                       │             │
│  │  • Taxonomic completeness (≥3 fields)      │             │
│  │  • Geographic completeness (≥1 field)      │             │
│  │  • Ecological completeness (≥1 field)      │             │
│  │  • Enumeration coverage                     │             │
│  └────────────────────────────────────────────┘             │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 6: EXPORT & STORAGE                                     │
├──────────────────────────────────────────────────────────────┤
│  ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│  │OWL/RDF    │    │  Upload   │    │  Version  │           │
│  │File       │───▶│ to Fuseki │───▶│  Tracking │           │
│  │Generation │    │  SPARQL   │    │           │           │
│  └───────────┘    └───────────┘    └───────────┘           │
└──────────────────────────────────────────────────────────────┘
```

### Data Format Support

#### Format 1: Direct Schema (Recommended)

**Your current format!**

**Species Sheet** (field names as columns OR transposed as rows)
```csv
species_scientific_name,subspecies,family,genus,common_name,biomes,...
```

Or transposed:
```csv
Species
species_scientific_name
subspecies
family
genus
common_name
biomes
...
```

**Optionset Sheet** (enumerations)
```csv
Biomes,Conservation Status,Climate Type,...
Tropical Rainforest,LC (Least Concern),Af - Tropical rainforest,...
Temperate Forest,NT (Near Threatened),Am - Tropical monsoon,...
...
```

#### Format 2: MVP + Option Set

**MVP Sheet** (field metadata)
```csv
Field,Schema (revised),option set,ai researched,manual calculation,Exists
Scientific Name,species_scientific_name,,,TRUE,TRUE
Biomes,biomes,Biome values,Ecological,TRUE,TRUE
```

**Option Set Sheet** (enumeration values)
```csv
Field Name,Option Value,Description
Biomes,Tropical Rainforest,Tropical rainforest biome
Biomes,Temperate Forest,Temperate forest biome
```

---

## Installation & Setup

### Prerequisites

✅ Python 3.8 or higher
✅ pip package manager
✅ PostgreSQL 12+ (optional)
✅ Apache Jena Fuseki 4.0+ (optional)
✅ Google Cloud account with Sheets API (optional)

### Step 1: Clone & Setup Environment

```bash
# Clone repository
git clone <your-repo-url>
cd biodiversity-ontology-automation

# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configuration

Create `config.py` or set environment variables:

```python
# Google Sheets
USE_GOOGLE_SHEETS = True
GOOGLE_SHEETS_CREDS_FILE = 'service_account.json'

# Apache Fuseki
FUSEKI_BASE_URL = 'http://167.172.143.162:3030'
FUSEKI_DATASET = 'treekipedia'
TRIPLESTORE_ENABLED = True

# PostgreSQL
POSTGRESQL_ENABLED = True
POSTGRESQL_CONFIG = {
    'host': '167.172.143.162',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': 'your_password',
    'port': 5432
}

# File Storage
UPLOAD_FOLDER = 'Uploads'
METADATA_DIR = 'Metadata'
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
```

### Step 3: Google Sheets Setup

1. **Create Google Cloud Project**
   - Go to https://console.cloud.google.com
   - Create new project

2. **Enable APIs**
   - Enable Google Sheets API
   - Enable Google Drive API

3. **Create Service Account**
   - IAM & Admin → Service Accounts
   - Create service account
   - Generate JSON key

4. **Save Credentials**
   - Save JSON as `service_account.json` in project root

5. **Share Sheets**
   - Share your Google Sheet with service account email
   - Grant "Editor" permissions

### Step 4: Apache Fuseki Setup

```bash
# Download Fuseki
wget https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-4.10.0.tar.gz

# Extract
tar -xzf apache-jena-fuseki-4.10.0.tar.gz
cd apache-jena-fuseki-4.10.0

# Start server
./fuseki-server --port=3030

# Create dataset
curl -X POST http://localhost:3030/$/datasets \
     -d "dbName=treekipedia" \
     -d "dbType=mem"
```

### Step 5: PostgreSQL Setup (Optional)

```bash
# Install PostgreSQL
# Mac: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Create database
createdb treekipedia

# Create tables (use your schema)
psql treekipedia < schema.sql
```

### Step 6: Run Application

```bash
# Development mode
python app.py

# Production mode (with gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app
```

Access at: **http://localhost:5001**

---

## User Guide

### Dashboard Overview

![Dashboard](https://via.placeholder.com/800x400?text=Treekipedia+Dashboard)

**Main Sections:**
1. **System Status** - Real-time health checks
2. **Data Sources** - Google Sheets, PostgreSQL, CSV
3. **Quick Actions** - Run automation, health check, view logs
4. **Recent Activity** - Latest operations

### Importing from Google Sheets

**Step-by-Step:**

1. **Navigate** to "Import from Google Sheets"

2. **Enter Spreadsheet Info**
   - **Option A**: Spreadsheet ID (from URL)
     ```
     https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
     ```
   - **Option B**: Exact spreadsheet name

3. **View Auto-Detected Metadata**
   - Sheet names
   - Row/column counts (actual data)
   - Version information

4. **Configure Generation**
   - Ontology name (optional, defaults to sheet name)
   - Force generation (override change detection)

5. **Generate Ontology**
   - Click "Import & Generate Ontology"
   - View real-time progress
   - See quality metrics

6. **Download or Upload**
   - Download OWL file
   - Auto-upload to Fuseki (if enabled)
   - View in SPARQL endpoint

### Your Data Format (TreeSheet Example)

**Your sheets:**
- `species` (120 fields as rows in 1 column) → **Auto-detected as transposed format**
- `optionset` (815 rows × 24 columns) → **Option sets**
- `metadata` (8 rows × 2 columns) → **Version tracking**

**What happens:**
1. System detects transposed format: "120 field names in single column"
2. Extracts all 120 field names
3. Matches with 23 option sets from optionset sheet
4. Generates comprehensive ontology with all fields
5. Categorizes into 8 ontology classes
6. Creates ~100KB+ OWL file (not 1.75KB!)

### PostgreSQL Monitoring

**Features:**
- Real-time table statistics
- Automatic RDF conversion
- Change detection
- Incremental sync to Fuseki

**Access:** Click "PostgreSQL Monitor" from dashboard

### Version Management

Track changes to your spreadsheets:
- View version history
- Compare versions
- Roll back if needed
- Changelog tracking

---

## API Reference

### System Status

**Endpoint:** `GET /api/system-status`

**Response:**
```json
{
  "blazegraph": {
    "status": "online",
    "enabled": true,
    "endpoint": "http://167.172.143.162:3030/treekipedia/sparql"
  },
  "google_sheets": {
    "status": "connected",
    "enabled": true,
    "initialized": true
  },
  "postgresql": {
    "status": "connected",
    "enabled": true,
    "details": {
      "host": "167.172.143.162",
      "database": "treekipedia"
    }
  }
}
```

### Import from Google Sheets

**Endpoint:** `POST /import-from-sheets`

**Form Data:**
- `spreadsheet_id` (optional): Google Sheets ID
- `spreadsheet_name` (optional): Sheet name
- `ontology_name` (optional): Output filename
- `force_generation` (optional): Boolean

**Response:** Redirects to success page with generated ontology

### Spreadsheet Metadata

**Endpoint:** `GET /spreadsheet-metadata`

**Query Parameters:**
- `spreadsheet_id` or `spreadsheet_name`

**Response:**
```json
{
  "success": true,
  "metadata": {
    "title": "TreeSheet",
    "id": "...",
    "worksheets": [
      {
        "title": "optionset",
        "row_count": 815,
        "col_count": 24
      },
      {
        "title": "species",
        "row_count": 121,
        "col_count": 1
      }
    ],
    "version_info": {
      "version": "1.0.24",
      "last_modified_by": "sev"
    }
  }
}
```

### Preview Ontology

**Endpoint:** `POST /preview-multi-sheet-ontology`

**Form Data:**
- `spreadsheet_id` or `spreadsheet_name`

**Response:**
```json
{
  "success": true,
  "preview": {
    "ontology_summary": {
      "total_properties": 120,
      "total_classes": 8,
      "total_relationships": 15
    },
    "field_categories": {
      "TaxonomicRank": ["species_scientific_name", "family", "genus", ...],
      "GeographicDistribution": ["countries", "ecoregions", ...],
      "EcologicalInformation": ["biomes", "habitat", ...]
    },
    "data_quality": {
      "completeness_score": 0.92,
      "taxonomic_completeness": true,
      "geographic_completeness": true
    }
  }
}
```

### Upload CSV

**Endpoint:** `POST /upload`

**Form Data:**
- `files`: CSV file(s) (multipart/form-data)
- `ontology_name`: Output filename

**Response:** Redirects to success page

---

## Development Guide

### Project Structure

```
biodiversity-ontology-automation/
├── app.py                           # Flask app entry point
├── wsgi.py                          # WSGI configuration
├── config.py                        # App configuration
├── requirements.txt                 # Python dependencies
│
├── routes_main.py                   # Main web routes
├── routes_api.py                    # API endpoints
├── utils.py                         # Helper functions
│
├── multi_sheet_biodiversity_generator.py  # Core ontology engine
├── sheets_integration.py            # Google Sheets client
├── postgres_rdf_converter.py        # PostgreSQL → RDF
├── incremental_ontology_updater.py  # Incremental updates
│
├── templates/                       # HTML templates
│   ├── index.html                   # Dashboard
│   ├── import_sheets.html           # Sheets import
│   ├── postgres_monitor.html        # DB monitor
│   ├── success.html                 # Success page
│   ├── version_management.html      # Versions
│   └── documentation.html           # This file (web)
│
├── static/css/
│   └── treekipedia-unified.css      # Unified styles
│
├── scripts/                         # Automation
│   ├── treekipedia_pipeline.py      # Full pipeline
│   └── automation_script.py         # Scheduled tasks
│
├── Uploads/                         # Temporary files
├── Metadata/                        # Version tracking
│
└── docs/
    ├── README.md                    # Quick start
    ├── DOCUMENTATION.md             # This file
    └── CHANGELOG.md                 # Version history
```

### Adding New Field Patterns

Edit `multi_sheet_biodiversity_generator.py`:

```python
# Add to field_patterns dict
self.field_patterns = {
    # ... existing patterns ...
    'YOUR_PATTERN': re.compile(r'your_regex', re.IGNORECASE),
}

# Add to _determine_ontology_class()
if pattern_name in ['YOUR_PATTERN']:
    return 'YourOntologyClass'
```

### Adding New Ontology Classes

```python
# Add to __init__
self.ontology_classes = {
    # ... existing classes ...
    'YourClassName': {
        'properties': ['prop1', 'prop2'],
        'description': 'Your description'
    }
}
```

### Custom Data Source Integration

Create new file `your_source_integration.py`:

```python
class YourSourceIntegration:
    def __init__(self, config):
        self.config = config

    def fetch_data(self):
        """Fetch data from your source"""
        # Return List[Dict] format
        pass

    def get_metadata(self):
        """Get source metadata"""
        pass
```

Add route in `routes_main.py`:

```python
@main_bp.route('/import-from-yoursource', methods=['GET', 'POST'])
def import_from_your_source():
    # Your integration logic
    pass
```

---

## Troubleshooting

### Issue: "Detected transposed format" but ontology still small

**Cause:** Field names might be empty or have whitespace

**Solution:**
```python
# Check logs for:
logger.info(f"Extracted {len(field_names)} field names from transposed format")

# Verify field names aren't empty
field_names = [f for f in field_names if f]  # Already implemented
```

### Issue: "Page not found" alert

**Status:** ✅ **FIXED**

Browser requests for `favicon.ico` and `.well-known/*` are now ignored.

### Issue: Row counts show 1000

**Status:** ✅ **FIXED**

Now counts actual non-empty rows, not allocated sheet size.

### Issue: Google Sheets connection fails

**Checklist:**
- [ ] `service_account.json` exists
- [ ] Sheet shared with service account email
- [ ] Google Sheets API enabled
- [ ] Service account has Editor permissions
- [ ] Sheet ID/name is correct

### Issue: Fuseki upload fails

**Checklist:**
- [ ] Fuseki server running
- [ ] Dataset exists
- [ ] Endpoint URL correct
- [ ] OWL file valid
- [ ] No firewall blocking port 3030

### Debugging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check logs:
```bash
tail -f app.log
```

---

## FAQ

**Q: What data formats are supported?**
A: CSV files, Google Sheets, and PostgreSQL databases. Sheets can be in direct schema, transposed, or MVP format.

**Q: How many fields can I process?**
A: Tested with 120+ fields. Performance limit is ~500 fields for dynamic analysis.

**Q: Can I use this without Google Sheets?**
A: Yes! CSV upload works standalone.

**Q: Does it support species with actual data rows?**
A: Currently it processes **schema definitions** (field names), not data rows. For 50,000 species, use PostgreSQL import.

**Q: How do I update existing ontologies?**
A: Use incremental update mode or force regeneration from sheets.

**Q: Can I customize ontology classes?**
A: Yes! Edit `multi_sheet_biodiversity_generator.py` and add your classes.

**Q: What's the difference between Blazegraph and Fuseki?**
A: Fuseki is the current triple store. "Blazegraph" references remain for backward compatibility.

**Q: How do I query the generated ontology?**
A: Use SPARQL endpoint at `http://167.172.143.162:3030/treekipedia/sparql`

---

## Support & Contributing

### Get Help

- 📖 Read this documentation
- 🐛 Check troubleshooting section
- 📝 Review logs in `app.log`
- 💬 Open GitHub issue

### Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

### License

[Your License Here]

---

**Built with ❤️ for biodiversity conservation and research**

*Treekipedia GraphFlow - Transforming data into knowledge graphs*
