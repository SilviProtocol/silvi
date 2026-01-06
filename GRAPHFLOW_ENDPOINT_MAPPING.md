# GraphFlow Endpoint Mapping Reference

Complete mapping of all 58 GraphFlow endpoints to new architecture.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🔵 | Frontend page (HTML → Next.js) |
| 🟢 | API endpoint → Express proxy → Python |
| 🟡 | API endpoint → Express only (no Python) |
| 🔴 | Critical Python dependency (owlready2/rdflib) |
| ⚪ | Static/simple endpoint |

---

## Complete Endpoint Inventory (58 total)

### Main Routes (13 endpoints)

| # | Old Route | Method | Type | New Route | Handler |
|---|-----------|--------|------|-----------|---------|
| 1 | `/` | GET | 🔵 | `/admin` | Next.js page |
| 2 | `/upload` | POST | 🔴🟢 | `/api/admin/ontology/upload` → Python `/api/v1/ontology/generate` | Express + Python |
| 3 | `/import-from-sheets` | GET | 🔵 | `/admin/ontology/sheets` | Next.js page |
| 4 | `/import-from-sheets` | POST | 🔴🟢 | `/api/admin/sheets/import` → Python `/api/v1/sheets/import` | Express + Python |
| 5 | `/download/<session>/<file>` | GET | 🟡 | `/api/admin/ontology/download/:session/:file` | Express file serving |
| 6 | `/status/<session>` | GET | 🟡 | `/api/admin/ontology/sessions/:session` | Express metadata |
| 7 | `/ontology-details/<session>` | GET | 🟡 | `/api/admin/ontology/sessions/:session/details` | Express metadata |
| 8 | `/system-capabilities` | GET | ⚪ | `/api/admin/system/capabilities` | Express static JSON |
| 9 | `/compare-ontologies` | GET | 🔵 | `/admin/ontology/compare` | Next.js page |
| 10 | `/cleanup` | POST | 🟡 | `/api/admin/system/cleanup` | Express background job |
| 11 | `/validate-spreadsheet` | POST | 🟡 | `/api/admin/sheets/validate` | Express validation |
| 12 | `/help/multi-sheet` | GET | ⚪ | `/api/admin/help/multi-sheet` | Express static JSON |
| 13 | `/preview-multi-sheet-ontology` | POST | 🔴🟢 | `/api/admin/ontology/preview` → Python `/api/v1/analyze/fields` | Express + Python |
| 14 | `/analyze-multi-sheet-csv` | POST | 🔴🟢 | `/api/admin/ontology/analyze` → Python `/api/v1/analyze/fields` | Express + Python |

### PostgreSQL Routes (14 endpoints)

| # | Old Route | Method | Type | New Route | Handler |
|---|-----------|--------|------|-----------|---------|
| 15 | `/postgres-monitor` | GET | 🔵 | `/admin/postgres-sync` | Next.js page |
| 16 | `/postgres-status` | GET | 🟡 | `/api/admin/postgres/status` | Express + psycopg2 |
| 17 | `/postgres-tables` | GET | 🟡 | `/api/admin/postgres/tables` | Express + psycopg2 |
| 18 | `/api/postgres-tables` | GET | 🟡 | `/api/admin/postgres/tables` | Express + psycopg2 |
| 19 | `/postgres-table-info` | POST | 🟡 | `/api/admin/postgres/tables/:name/info` | Express + psycopg2 |
| 20 | `/postgres-changes` | GET | 🟡 | `/api/admin/postgres/changes` | Express + psycopg2 |
| 21 | `/postgres-sync-fuseki` | POST | 🔴🟢 | `/api/admin/postgres/sync/:table` → Python `/api/v1/postgres/convert-table` | Express + Python |
| 22 | `/postgres-sync-batch` | POST | 🔴🟢 | `/api/admin/postgres/sync-batch` → Python `/api/v1/postgres/convert-table` | Express + Python |
| 23 | `/postgres-full-sync-fuseki` | POST | 🔴🟢 | `/api/admin/postgres/sync-all` → Python `/api/v1/postgres/convert-table` | Express + Python |
| 24 | `/postgres-generate-rdf` | POST | 🔴🟢 | `/api/admin/postgres/generate-rdf` → Python `/api/v1/postgres/convert-table` | Express + Python |
| 25 | `/run-postgres-automation` | POST | 🔴🟢 | `/api/admin/postgres/automation/run` → Python workflow | Express + Python |
| 26 | `/postgres-automation-status` | GET | 🟡 | `/api/admin/postgres/automation/status` | Express metadata |

### Fuseki/Triplestore Routes (8 endpoints)

| # | Old Route | Method | Type | New Route | Handler |
|---|-----------|--------|------|-----------|---------|
| 27 | `/fuseki-status` | GET | 🟡 | `/api/admin/fuseki/status` | Express + axios |
| 28 | `/fuseki-test-query` | POST | 🟡 | `/api/admin/fuseki/query` | Express + axios |
| 29 | `/fuseki-stats` | GET | 🟡 | `/api/admin/fuseki/stats` | Express + axios |
| 30 | `/blazegraph-status` | GET | 🟡 | `/api/admin/fuseki/status` | Express + axios (legacy) |
| 31 | `/api/system-status-fuseki` | GET | 🟡 | `/api/admin/system/status` | Express health check |
| 32 | `/api/system-status` | GET | 🟡 | `/api/admin/system/status` | Express health check |

### Google Sheets Routes (9 endpoints)

| # | Old Route | Method | Type | New Route | Handler |
|---|-----------|--------|------|-----------|---------|
| 33 | `/sheets-status` | GET | 🔴🟢 | `/api/admin/sheets/status` → Python `/api/v1/health` | Express + Python |
| 34 | `/test-sheets` | GET | 🔴🟢 | `/api/admin/sheets/test` → Python `/api/v1/sheets/test` | Express + Python |
| 35 | `/spreadsheet-metadata` | GET | 🔴🟢 | `/api/admin/sheets/metadata` → Python `/api/v1/sheets/metadata` | Express + Python |
| 36 | `/update-spreadsheet-version` | POST | 🔴🟢 | `/api/admin/sheets/version` → Python `/api/v1/sheets/version` | Express + Python |
| 37 | `/create-version-snapshot` | POST | 🔴🟢 | `/api/admin/sheets/snapshot` → Python `/api/v1/sheets/snapshot` | Express + Python |
| 38 | `/versions` | GET | 🔴🟢 | `/api/admin/sheets/versions` → Python `/api/v1/sheets/versions` | Express + Python |
| 39 | `/version-management` | GET | 🔵 | `/admin/version-control` | Next.js page |

### Documentation & Health (14 endpoints)

| # | Old Route | Method | Type | New Route | Handler |
|---|-----------|--------|------|-----------|---------|
| 40 | `/documentation` | GET | 🔵 | `/admin/docs` | Next.js page |
| 41 | `/help/<section>` | GET | ⚪ | `/api/admin/help/:section` | Express static JSON |
| 42 | `/api/documentation-stats` | GET | 🟡 | `/api/admin/stats` | Express metadata |
| 43 | `/system-health` | GET | 🟡 | `/api/admin/health` | Express health check |
| 44 | `/health` | GET | 🟡 | `/api/admin/health` | Express health check |
| 45 | `/health/dynamic-ontology` | GET | 🔴🟢 | `/api/admin/health/ontology` → Python `/api/v1/health` | Express + Python |
| 46 | `/features` | GET | ⚪ | `/api/admin/features` | Express static JSON |
| 47 | `/run-full-automation` | POST | 🔴🟢 | `/api/admin/automation/run` → Python workflow | Express + Python |

---

## Python Microservice API (New Endpoints)

### Core Python Endpoints (REQUIRED)

| Endpoint | Method | Purpose | Dependencies |
|----------|--------|---------|--------------|
| `/api/v1/ontology/generate` | POST | Generate OWL ontology | owlready2 |
| `/api/v1/ontology/analyze` | POST | Analyze field patterns | owlready2 |
| `/api/v1/postgres/convert-table` | POST | Convert table to RDF | rdflib, psycopg2 |
| `/api/v1/sheets/import` | POST | Import Google Sheet | gspread |
| `/api/v1/sheets/metadata` | GET | Get sheet metadata | gspread |
| `/api/v1/sheets/version` | POST | Update version | gspread |
| `/api/v1/sheets/snapshot` | POST | Create snapshot | gspread |
| `/api/v1/sheets/versions` | GET | List versions | gspread |
| `/api/v1/sheets/test` | GET | Test connection | gspread |
| `/api/v1/health` | GET | Service health | None |

---

## Express Proxy Routes (New Middleware)

### Frontend-Facing Endpoints

| Route Pattern | Purpose | Proxies to Python? |
|---------------|---------|-------------------|
| `/api/admin/ontology/*` | Ontology management | Some |
| `/api/admin/postgres/*` | PostgreSQL sync | Some (RDF conversion) |
| `/api/admin/fuseki/*` | Fuseki queries | No |
| `/api/admin/sheets/*` | Google Sheets | Yes (all) |
| `/api/admin/health/*` | Health checks | Some |
| `/api/admin/help/*` | Help/docs | No |
| `/api/admin/system/*` | System operations | Some |

---

## Streaming Endpoints (SSE)

| Old Route | New Route | Purpose |
|-----------|-----------|---------|
| N/A (polling) | `/api/admin/ontology/stream/:session` | Real-time generation progress |
| N/A (polling) | `/api/admin/postgres/sync-stream/:table` | Real-time sync progress |
| N/A (polling) | `/api/admin/automation/stream` | Real-time automation progress |

---

## Frontend Pages (Next.js)

### New Admin Pages

| Route | Old Template | Components |
|-------|--------------|------------|
| `/admin` | `index.html` | AdminDashboard, StatusCards, SystemHealth |
| `/admin/ontology/upload` | `index.html` (form section) | OntologyUploadForm, FileDropzone |
| `/admin/ontology/sheets` | `import_sheets.html` | SheetsImportForm, SpreadsheetSelector |
| `/admin/ontology/sessions` | N/A (new) | SessionsList, SessionCard |
| `/admin/ontology/sessions/:id` | `success.html` | SessionDetails, AnalysisSummary, DownloadCard |
| `/admin/postgres-sync` | `postgres_monitor.html` | TablesGrid, SyncControls, BatchProgress, FusekiStats |
| `/admin/fuseki` | N/A (new) | SparqlEditor, ResultsTable, QueryTemplates |
| `/admin/version-control` | `version_management.html` | VersionHistory, SnapshotCreator, ChangelogViewer |
| `/admin/docs` | `documentation.html` | DocumentationViewer (static content) |

---

## Data Flow Examples

### Example 1: Upload CSV and Generate Ontology

```
1. User uploads file in Next.js form
   └─> POST /api/admin/ontology/upload (Express)
       └─> Multer saves file to disk
       └─> Returns session_id and file_path

2. Frontend triggers generation
   └─> POST /api/admin/ontology/generate (Express)
       └─> POST http://localhost:5002/api/v1/ontology/generate (Python)
           └─> MultiSheetBiodiversityGenerator.analyze_multi_sheet_directory()
           └─> owlready2 creates OWL ontology
           └─> Returns analysis + file path

3. Frontend polls progress
   └─> GET /api/admin/ontology/stream/:session (Express SSE)
       └─> Streams progress events from background job

4. User downloads result
   └─> GET /api/admin/ontology/download/:session/:file (Express)
       └─> Send file from disk
```

### Example 2: Sync PostgreSQL Table to Fuseki

```
1. User clicks "Sync species table"
   └─> POST /api/admin/postgres/sync/species (Express)
       └─> Gets table info from PostgreSQL (Express)
       └─> Starts background batch processing

2. For each batch:
   └─> POST http://localhost:5002/api/v1/postgres/convert-table (Python)
       └─> PostgreSQLFusekiSync.get_table_data_batch()
       └─> PostgreSQLFusekiSync.convert_table_to_rdf() (rdflib)
       └─> Returns RDF N-Triples

   └─> Express uploads RDF to Fuseki
       └─> PUT http://167.172.143.162:3030/treekipedia/data

3. Frontend monitors progress
   └─> GET /api/admin/postgres/sync-stream/species (Express SSE)
       └─> Streams batch progress events

4. Completion
   └─> Final event emitted
   └─> Frontend shows success + triple count
```

### Example 3: Import Google Sheets

```
1. User enters spreadsheet ID
   └─> POST /api/admin/sheets/import (Express)
       └─> POST http://localhost:5002/api/v1/sheets/import (Python)
           └─> SheetsIntegration.open_spreadsheet() (gspread)
           └─> Reads all worksheets
           └─> Returns CSV data

2. Frontend previews data
   └─> Shows field analysis
   └─> User confirms import

3. Generate ontology from sheets data
   └─> POST http://localhost:5002/api/v1/ontology/generate (Python)
       └─> Same flow as CSV upload

4. Update spreadsheet version
   └─> POST /api/admin/sheets/version (Express)
       └─> POST http://localhost:5002/api/v1/sheets/version (Python)
           └─> SheetsIntegration.update_spreadsheet_version()
```

---

## Migration Checklist

### Per Endpoint Checklist

For each of the 58 endpoints:

- [ ] **Document current behavior**
  - Input parameters
  - Response format
  - Error cases
  - Dependencies

- [ ] **Design new route**
  - Express path
  - Python endpoint (if needed)
  - Request transformation
  - Response transformation

- [ ] **Implement Express handler**
  - Route definition
  - Middleware (auth, validation)
  - Proxy logic (if Python needed)
  - Error handling

- [ ] **Implement Python endpoint** (if needed)
  - API route
  - Request parsing
  - Business logic
  - Response formatting

- [ ] **Update frontend**
  - API client function
  - Component integration
  - Loading states
  - Error handling

- [ ] **Write tests**
  - Unit tests (Python)
  - Integration tests (Express)
  - E2E tests (Playwright)

- [ ] **Deploy**
  - Update route config
  - Test in staging
  - Monitor errors
  - Verify metrics

---

## Priority Order

### Phase 1: Core Ontology Generation (Endpoints 1-14)
**Critical path - blocks everything else**

1. Upload CSV (`/upload`)
2. Generate ontology (Python service)
3. Download result (`/download/*`)
4. Session status (`/status/*`)

### Phase 2: PostgreSQL Sync (Endpoints 15-26)
**High value - main use case**

1. List tables (`/postgres-tables`)
2. Sync single table (`/postgres-sync-fuseki`)
3. Stream progress (SSE)
4. Batch processing

### Phase 3: Google Sheets (Endpoints 33-39)
**Medium priority - alternative input**

1. Import sheets (`/import-from-sheets`)
2. Metadata (`/spreadsheet-metadata`)
3. Version control (`/versions`)

### Phase 4: Admin UI (Pages)
**User-facing polish**

1. Dashboard
2. Upload form
3. Sync interface
4. Version management

### Phase 5: Nice-to-Have (Endpoints 40-47)
**Can wait until end**

1. Documentation pages
2. Help endpoints
3. System stats

---

## Testing Matrix

| Category | Old Endpoints | New Endpoints | Test Type |
|----------|---------------|---------------|-----------|
| Ontology | 1-14 | 14 Express + 4 Python | Unit + E2E |
| PostgreSQL | 15-26 | 12 Express + 4 Python | Integration + E2E |
| Fuseki | 27-32 | 6 Express | Integration |
| Sheets | 33-39 | 7 Express + 7 Python | Integration + E2E |
| Admin | 40-47 | 8 Express | Unit |
| **Total** | **58** | **47 Express + 15 Python** | **All types** |

---

## Performance Comparison

### Before (Flask Monolith)

| Operation | Current Time |
|-----------|--------------|
| Generate ontology (100 fields) | ~3 seconds |
| PostgreSQL sync (1000 records) | ~25 seconds |
| Google Sheets import | ~8 seconds |
| Page load | ~500ms |

### After (Microservice Architecture)

| Operation | Target Time | Notes |
|-----------|-------------|-------|
| Generate ontology (100 fields) | < 5 seconds | Python service overhead |
| PostgreSQL sync (1000 records) | < 30 seconds | Streaming progress |
| Google Sheets import | < 10 seconds | Proxy overhead |
| Page load | < 300ms | Next.js SSR |

**Acceptable degradation:** +20% response time is OK for better architecture

---

**Last Updated:** October 19, 2025
**Related Docs:**
- [GRAPHFLOW_INTEGRATION_PLAN.md](./GRAPHFLOW_INTEGRATION_PLAN.md) - Full implementation plan
- [GRAPHFLOW_QUICK_REFERENCE.md](./GRAPHFLOW_QUICK_REFERENCE.md) - Quick reference guide
