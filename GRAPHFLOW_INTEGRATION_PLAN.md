# GraphFlow Integration Plan: Next.js Admin Portal + Python Microservice

**Generated:** October 19, 2025
**Version:** 1.0
**Target:** Rebuild GraphFlow as Treekipedia admin portal with Python backend

---

## Executive Summary

GraphFlow is a Flask-based ontology generation and RDF management system with:
- **4,501 lines** of production Python code
- **7 HTML templates** with embedded JavaScript
- **58 API endpoints** across multiple categories
- **3 core workflows**: CSV upload, Google Sheets import, PostgreSQL sync

**Integration Goal:** Rebuild as Next.js admin portal in Treekipedia while keeping Python as headless microservice for OWL/RDF processing that MUST stay in Python (owlready2, rdflib dependencies).

---

## Table of Contents

1. [Complete Feature Inventory](#1-complete-feature-inventory)
2. [Python Dependencies Analysis](#2-python-dependencies-analysis)
3. [Headless API Specification](#3-headless-api-specification)
4. [Next.js Component Architecture](#4-nextjs-component-architecture)
5. [Express Backend Integration](#5-express-backend-integration)
6. [Risk Assessment](#6-risk-assessment)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Testing Strategy](#8-testing-strategy)

---

## 1. Complete Feature Inventory

### 1.1 Flask Routes Inventory (58 endpoints)

#### Main Routes (`routes_main.py` - 1,032 lines)

| Route | Method | Purpose | Frontend | Python Processing |
|-------|--------|---------|----------|-------------------|
| `/` | GET | Main dashboard | ✓ | Status checks |
| `/upload` | POST | CSV upload + ontology generation | ✓ | OWL generation |
| `/import-from-sheets` | GET/POST | Google Sheets import | ✓ | Sheets API + OWL |
| `/download/<session_id>/<filename>` | GET | Download generated files | ✓ | File serving |
| `/status/<session_id>` | GET | Session status check | ✓ | Metadata lookup |
| `/ontology-details/<session_id>` | GET | Detailed ontology info | ✓ | Analysis data |
| `/system-capabilities` | GET | System feature list | ✓ | Config info |
| `/compare-ontologies` | GET | Comparison page | ✓ | Static data |
| `/cleanup` | POST | Expired file cleanup | Background | File system |
| `/validate-spreadsheet` | POST | Sheet validation | ✓ | Basic checks |
| `/help/multi-sheet` | GET | Help info | ✓ | Static JSON |
| `/preview-multi-sheet-ontology` | POST | Preview generation | ✓ | Analysis only |
| `/analyze-multi-sheet-csv` | POST | CSV analysis | ✓ | Field detection |

#### API Routes (`routes_api.py` - 1,565 lines)

**PostgreSQL Sync (14 endpoints):**

| Route | Method | Purpose | Critical Python? |
|-------|--------|---------|------------------|
| `/api/postgres-tables` | GET | List tables | No (psycopg2 only) |
| `/postgres-tables` | GET | List with counts | No |
| `/postgres-table-info` | POST | Table metadata | No |
| `/postgres-changes` | GET | Recent changes | No |
| `/postgres-sync-fuseki` | POST | Single table sync | **YES** (RDF conversion) |
| `/postgres-sync-batch` | POST | Batch sync | **YES** (RDF conversion) |
| `/postgres-full-sync-fuseki` | POST | Full sync | **YES** (RDF conversion) |
| `/postgres-generate-rdf` | POST | RDF generation | **YES** (RDF conversion) |
| `/postgres-status` | GET | Connection status | No |
| `/postgres-monitor` | GET | Monitor page | Frontend only |
| `/run-postgres-automation` | POST | Automation trigger | **YES** (Full workflow) |
| `/postgres-automation-status` | GET | Automation status | No |

**Fuseki/Triplestore (6 endpoints):**

| Route | Method | Purpose | Critical Python? |
|-------|--------|---------|------------------|
| `/fuseki-status` | GET | Fuseki health | No |
| `/fuseki-test-query` | POST | SPARQL query test | No |
| `/fuseki-stats` | GET | Triple counts | No |
| `/blazegraph-status` | GET | Legacy endpoint | No |
| `/api/system-status-fuseki` | GET | Full status | No |
| `/api/system-status` | GET | System health | No |

**Google Sheets (9 endpoints):**

| Route | Method | Purpose | Critical Python? |
|-------|--------|---------|------------------|
| `/sheets-status` | GET | Sheets connection | **YES** (gspread) |
| `/test-sheets` | GET | Test integration | **YES** |
| `/spreadsheet-metadata` | GET | Sheet metadata | **YES** |
| `/update-spreadsheet-version` | POST | Version update | **YES** |
| `/create-version-snapshot` | POST | Snapshot creation | **YES** |
| `/versions` | GET | Version history | **YES** |
| `/version-management` | GET | Management page | Frontend only |

**Documentation & Health (9 endpoints):**

| Route | Method | Purpose | Critical Python? |
|-------|--------|---------|------------------|
| `/documentation` | GET | Docs page | Frontend only |
| `/help/<section>` | GET | Contextual help | No (Static JSON) |
| `/api/documentation-stats` | GET | Usage stats | No |
| `/system-health` | GET | Health check | No |
| `/health` | GET | Basic health | No |
| `/health/dynamic-ontology` | GET | Ontology health | **YES** (Test generator) |
| `/features` | GET | Feature list | No |
| `/run-full-automation` | POST | Full automation | **YES** |

### 1.2 Python Processing Functions

**Critical Python-Only Functions** (MUST stay Python):

| File | Function | Lines | Why Python-Only |
|------|----------|-------|-----------------|
| `multi_sheet_biodiversity_generator.py` | `MultiSheetBiodiversityGenerator` | ~1,165 | **owlready2** - OWL ontology creation |
| `postgres_to_fuseki_sync.py` | `PostgreSQLFusekiSync` | ~739 | **rdflib** - RDF N-Triples generation |
| `incremental_ontology_updater.py` | `update_ontology_incrementally()` | ~600 | **owlready2** + SPARQL updates |
| `sheets_integration.py` | `SheetsIntegration` | ~500 | **gspread** - Google Sheets API |
| `utils.py` | Various helpers | ~700 | Field analysis patterns |

**Total Critical Python Code:** ~3,700 lines (must remain Python)

**Portable Logic** (could be Node.js):

| Function | Purpose | Can Port? |
|----------|---------|-----------|
| Metadata management | Session/file metadata | ✓ Yes (simple JSON) |
| File serving | Download handling | ✓ Yes (Express static) |
| Validation | Basic input checks | ✓ Yes (Zod/Joi) |
| Status checks | Health endpoints | ✓ Yes (axios) |

### 1.3 Frontend Pages & Components

**7 HTML Templates:**

| Template | Purpose | Key Features | JavaScript Functions |
|----------|---------|--------------|----------------------|
| `index.html` | Main dashboard | Status cards, integration options | `refreshSystemStatus()`, `runFullAutomation()` |
| `postgres_monitor.html` | PostgreSQL sync UI | Table list, sync controls, batch progress | `syncTable()`, `syncAllTables()`, `loadTables()` |
| `import_sheets.html` | Sheets import form | Spreadsheet selector, preview | `previewOntology()`, `importFromSheets()` |
| `success.html` | Generation results | Download links, summary stats | `downloadFile()`, `viewDetails()` |
| `version_management.html` | Version control | Version list, comparison | `loadVersions()`, `createSnapshot()` |
| `documentation.html` | Help/docs | Feature docs, examples | N/A (static) |
| `documentation_new.html` | Enhanced docs | Interactive examples | N/A (static) |

**Embedded JavaScript Patterns:**

All templates use:
- Bootstrap 5.3 for UI
- Font Awesome 6.1 for icons
- Fetch API for AJAX calls
- Real-time status updates (polling)
- Progress indicators for long operations
- Modal dialogs for forms

---

## 2. Python Dependencies Analysis

### 2.1 MUST Stay Python (Cannot Port)

| Dependency | Usage | Why Critical |
|------------|-------|--------------|
| **owlready2** | OWL ontology creation | No JavaScript equivalent for OWL reasoning |
| **rdflib** | RDF graph manipulation | Python-only RDF serialization |
| **gspread** | Google Sheets API | Mature Python library, complex auth |
| **psycopg2** | PostgreSQL driver | Already have in Treekipedia, but RDF conversion needs Python |

### 2.2 Can Port to Node.js

| Python Function | Node.js Equivalent | Complexity |
|-----------------|-------------------|------------|
| Flask routing | Express.js | Low |
| Request handling | Express middleware | Low |
| File uploads | Multer | Low |
| Session management | Express-session | Low |
| CSV parsing | PapaParse | Low |
| JSON operations | Native JSON | Low |
| HTTP requests | Axios | Low |
| Template rendering | React components | Medium |

### 2.3 Hybrid Approach (Best of Both)

**Python Microservice handles:**
- OWL ontology generation (owlready2)
- RDF conversion (rdflib)
- Google Sheets integration (gspread)
- Field analysis patterns
- SPARQL query generation

**Node.js/Express handles:**
- HTTP routing
- File upload/download
- Session management
- PostgreSQL queries (non-RDF)
- Metadata storage
- Request validation

**Next.js handles:**
- All UI rendering
- Real-time status updates
- Form validation
- State management
- User interaction

---

## 3. Headless API Specification

### 3.1 Python Microservice API Design

**Base URL:** `http://localhost:5002` (separate from main Treekipedia API)

#### 3.1.1 Ontology Generation

```yaml
POST /api/v1/ontology/generate
Description: Generate OWL ontology from CSV data
Request:
  Content-Type: application/json
  Body:
    {
      "session_id": "uuid",
      "files": [
        {
          "name": "mvp_sheet.csv",
          "content": "base64_encoded_csv"
        },
        {
          "name": "option_sets.csv",
          "content": "base64_encoded_csv"
        }
      ],
      "ontology_name": "treekipedia-ontology",
      "options": {
        "generate_individuals": true,
        "include_constraints": true
      }
    }
Response:
  {
    "success": true,
    "session_id": "uuid",
    "ontology_file": "treekipedia-ontology.owl",
    "download_url": "/api/v1/download/uuid/file.owl",
    "analysis": {
      "total_fields": 115,
      "ontology_classes": ["TaxonomicRank", "GeographicDistribution", ...],
      "data_properties_count": 87,
      "object_properties_count": 28,
      "individuals_count": 1543,
      "option_sets_count": 23
    },
    "quality_assessment": {
      "completeness_score": 0.87,
      "enumeration_coverage": 0.92
    }
  }
```

#### 3.1.2 PostgreSQL to RDF Conversion

```yaml
POST /api/v1/postgres/convert-table
Description: Convert PostgreSQL table to RDF N-Triples
Request:
  {
    "table_name": "species",
    "batch_offset": 0,
    "batch_size": 1000,
    "primary_key": "taxon_id"
  }
Response:
  {
    "success": true,
    "table_name": "species",
    "records_processed": 1000,
    "rdf_content": "<rdf_ntriples_string>",
    "triples_generated": 115000,
    "has_more": true,
    "next_offset": 1000
  }
```

#### 3.1.3 Google Sheets Integration

```yaml
POST /api/v1/sheets/import
Description: Import and analyze Google Sheet
Request:
  {
    "spreadsheet_id": "1abc...",
    "worksheet_names": ["MVP", "Option Sets"]
  }
Response:
  {
    "success": true,
    "spreadsheet_title": "Treekipedia MVP",
    "worksheets_processed": 2,
    "data": {
      "mvp_fields": [...],
      "option_sets": {...}
    },
    "analysis": {...}
  }
```

#### 3.1.4 Field Analysis

```yaml
POST /api/v1/analyze/fields
Description: Analyze and categorize data fields
Request:
  {
    "fields": [
      {
        "name": "species_scientific_name",
        "sample_values": ["Quercus robur", "Pinus sylvestris"]
      },
      {
        "name": "conservation_status",
        "sample_values": ["LC", "EN", "VU"]
      }
    ]
  }
Response:
  {
    "success": true,
    "field_analysis": {
      "species_scientific_name": {
        "ontology_class": "TaxonomicRank",
        "data_type": "string",
        "property_name": "scientificName",
        "creates_individuals": false,
        "pattern_matched": "SCIENTIFIC_NAME"
      },
      "conservation_status": {
        "ontology_class": "ConservationInformation",
        "data_type": "enumeration",
        "property_name": "conservationStatus",
        "creates_individuals": true,
        "option_set_values": ["LC", "EN", "VU", "CR", "EW", "EX"]
      }
    }
  }
```

### 3.2 Streaming Endpoints (Server-Sent Events)

For long-running operations, use SSE:

```yaml
GET /api/v1/stream/sync-progress/{session_id}
Description: Stream sync progress updates
Response: (text/event-stream)
  data: {"type": "progress", "table": "species", "batch": 5, "total_batches": 67, "records": 5000}

  data: {"type": "complete", "total_records": 67743, "total_triples": 7850000}

  data: {"type": "error", "message": "Connection timeout"}
```

### 3.3 Health & Status

```yaml
GET /api/v1/health
Response:
  {
    "status": "healthy",
    "version": "1.0.0",
    "dependencies": {
      "owlready2": "0.45",
      "rdflib": "7.0.0",
      "gspread": "5.12.0"
    },
    "uptime_seconds": 3600
  }
```

---

## 4. Next.js Component Architecture

### 4.1 Component Hierarchy

```
app/
├── admin/
│   ├── layout.tsx                 # Admin layout with sidebar nav
│   ├── page.tsx                   # Admin dashboard (overview)
│   │
│   ├── ontology/
│   │   ├── page.tsx               # Ontology management main page
│   │   ├── upload/
│   │   │   └── page.tsx           # CSV upload form
│   │   ├── sheets/
│   │   │   └── page.tsx           # Google Sheets import
│   │   ├── sessions/
│   │   │   ├── page.tsx           # Active sessions list
│   │   │   └── [sessionId]/
│   │   │       └── page.tsx       # Session details
│   │   └── components/
│   │       ├── OntologyUploadForm.tsx
│   │       ├── SheetsImportForm.tsx
│   │       ├── OntologyPreview.tsx
│   │       ├── AnalysisSummary.tsx
│   │       └── DownloadCard.tsx
│   │
│   ├── postgres-sync/
│   │   ├── page.tsx               # PostgreSQL sync dashboard
│   │   ├── components/
│   │   │   ├── TablesGrid.tsx
│   │   │   ├── SyncControls.tsx
│   │   │   ├── BatchProgress.tsx
│   │   │   ├── FusekiStats.tsx
│   │   │   └── SyncHistory.tsx
│   │
│   ├── fuseki/
│   │   ├── page.tsx               # Fuseki query interface
│   │   ├── components/
│   │   │   ├── SparqlEditor.tsx
│   │   │   ├── ResultsTable.tsx
│   │   │   └── QueryTemplates.tsx
│   │
│   ├── version-control/
│   │   ├── page.tsx               # Version management
│   │   ├── components/
│   │   │   ├── VersionHistory.tsx
│   │   │   ├── SnapshotCreator.tsx
│   │   │   └── ChangelogViewer.tsx
│   │
│   └── components/              # Shared admin components
│       ├── AdminNav.tsx
│       ├── StatusCard.tsx
│       ├── SystemHealth.tsx
│       └── ProgressIndicator.tsx
```

### 4.2 Key Components Specification

#### 4.2.1 OntologyUploadForm.tsx

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadOntologyFiles } from '@/lib/api/ontology';

interface OntologyUploadFormProps {
  onSuccess?: (sessionId: string) => void;
}

export function OntologyUploadForm({ onSuccess }: OntologyUploadFormProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [ontologyName, setOntologyName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);

    try {
      const result = await uploadOntologyFiles({
        files,
        ontologyName,
        onProgress: setProgress
      });

      onSuccess?.(result.session_id);
      router.push(`/admin/ontology/sessions/${result.session_id}`);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* File dropzone */}
      {/* Ontology name input */}
      {/* Progress bar */}
      {/* Submit button */}
    </form>
  );
}
```

#### 4.2.2 PostgresSyncDashboard.tsx

```typescript
'use client';

import { useState, useEffect } from 'react';
import { usePostgresSync } from '@/hooks/usePostgresSync';
import { TablesGrid } from './TablesGrid';
import { SyncControls } from './SyncControls';
import { BatchProgress } from './BatchProgress';

export function PostgresSyncDashboard() {
  const {
    tables,
    loadTables,
    syncTable,
    syncProgress,
    fusekiStats
  } = usePostgresSync();

  useEffect(() => {
    loadTables();
    // Poll for updates every 30 seconds
    const interval = setInterval(loadTables, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <TablesGrid tables={tables} onSync={syncTable} />
        {syncProgress && <BatchProgress {...syncProgress} />}
      </div>
      <div>
        <SyncControls onSyncAll={() => syncTable('all')} />
        <FusekiStats stats={fusekiStats} />
      </div>
    </div>
  );
}
```

### 4.3 Custom Hooks

#### useOntologyGeneration.ts

```typescript
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ontologyApi } from '@/lib/api/ontology';

export function useOntologyGeneration(sessionId?: string) {
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [progress, setProgress] = useState({ step: '', percent: 0 });

  const generateOntology = useMutation({
    mutationFn: ontologyApi.generate,
    onSuccess: (data) => {
      // Start listening to progress stream
      const es = new EventSource(
        `/api/admin/ontology/stream/${data.session_id}`
      );
      es.onmessage = (event) => {
        const progress = JSON.parse(event.data);
        setProgress(progress);
      };
      setEventSource(es);
    }
  });

  const sessionDetails = useQuery({
    queryKey: ['ontology-session', sessionId],
    queryFn: () => ontologyApi.getSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: 5000 // Poll every 5 seconds
  });

  return {
    generate: generateOntology.mutate,
    generating: generateOntology.isPending,
    progress,
    session: sessionDetails.data
  };
}
```

#### usePostgresSync.ts

```typescript
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { postgresApi } from '@/lib/api/postgres';

export function usePostgresSync() {
  const queryClient = useQueryClient();
  const [syncProgress, setSyncProgress] = useState(null);

  const { data: tables } = useQuery({
    queryKey: ['postgres-tables'],
    queryFn: postgresApi.getTables,
    refetchInterval: 30000
  });

  const { data: fusekiStats } = useQuery({
    queryKey: ['fuseki-stats'],
    queryFn: postgresApi.getFusekiStats,
    refetchInterval: 60000
  });

  const syncMutation = useMutation({
    mutationFn: postgresApi.syncTable,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['postgres-tables'] });
      queryClient.invalidateQueries({ queryKey: ['fuseki-stats'] });
    }
  });

  const syncTable = useCallback(async (tableName: string) => {
    // Start EventSource for progress updates
    const es = new EventSource(
      `/api/admin/postgres/sync-stream/${tableName}`
    );

    es.onmessage = (event) => {
      setSyncProgress(JSON.parse(event.data));
    };

    es.onerror = () => {
      es.close();
      setSyncProgress(null);
    };

    await syncMutation.mutateAsync({ tableName });
  }, [syncMutation]);

  return {
    tables: tables?.tables ?? [],
    fusekiStats: fusekiStats ?? {},
    syncTable,
    syncProgress,
    loadTables: () => queryClient.invalidateQueries({ queryKey: ['postgres-tables'] })
  };
}
```

### 4.4 API Client Layer

```typescript
// lib/api/ontology.ts
import axios from 'axios';

const pythonApi = axios.create({
  baseURL: 'http://localhost:5002/api/v1',
  timeout: 300000 // 5 minutes for long operations
});

const nodeApi = axios.create({
  baseURL: '/api/admin',
  timeout: 30000
});

export const ontologyApi = {
  generate: async (data: OntologyGenerateRequest) => {
    // Step 1: Upload files to Express (file handling)
    const formData = new FormData();
    data.files.forEach(file => formData.append('files', file));
    formData.append('ontologyName', data.ontologyName);

    const uploadResponse = await nodeApi.post('/ontology/upload', formData);
    const { session_id, file_paths } = uploadResponse.data;

    // Step 2: Trigger Python microservice for generation
    const generateResponse = await pythonApi.post('/ontology/generate', {
      session_id,
      files: file_paths,
      ontology_name: data.ontologyName
    });

    return generateResponse.data;
  },

  getSession: async (sessionId: string) => {
    const response = await nodeApi.get(`/ontology/sessions/${sessionId}`);
    return response.data;
  },

  downloadOntology: (sessionId: string, filename: string) => {
    return `/api/admin/ontology/download/${sessionId}/${filename}`;
  }
};
```

---

## 5. Express Backend Integration

### 5.1 Express Route Structure

```
treekipedia/backend/
├── controllers/
│   ├── admin/
│   │   ├── ontology.js          # Ontology management
│   │   ├── postgresSync.js      # PostgreSQL sync
│   │   ├── sheets.js            # Google Sheets proxy
│   │   └── system.js            # System health/status
│   │
├── middleware/
│   ├── adminAuth.js             # Admin role verification
│   ├── pythonProxy.js           # Python service proxy
│   ├── fileUpload.js            # Multer config
│   └── streamProgress.js        # SSE handler
│   │
├── services/
│   ├── pythonClient.js          # Python API client
│   ├── sessionManager.js        # Session metadata
│   └── fileManager.js           # Upload/download
│   │
└── routes/
    └── admin.js                 # Admin route definitions
```

### 5.2 Python Proxy Middleware

```javascript
// middleware/pythonProxy.js
const axios = require('axios');
const logger = require('../utils/logger');

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5002';

/**
 * Proxy middleware for Python microservice
 * Forwards requests to Python and handles errors
 */
const pythonProxy = (config = {}) => {
  return async (req, res, next) => {
    const {
      endpoint,
      method = 'POST',
      timeout = 300000,
      transformRequest,
      transformResponse
    } = config;

    try {
      const requestData = transformRequest
        ? transformRequest(req.body, req)
        : req.body;

      const response = await axios({
        method,
        url: `${PYTHON_SERVICE_URL}${endpoint}`,
        data: requestData,
        timeout,
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': req.sessionID
        }
      });

      const responseData = transformResponse
        ? transformResponse(response.data, req)
        : response.data;

      // Attach to req for controller use
      req.pythonResponse = responseData;
      next();

    } catch (error) {
      logger.error('Python service error:', error);

      if (error.code === 'ECONNREFUSED') {
        return res.status(503).json({
          success: false,
          error: 'Python service unavailable'
        });
      }

      if (error.response) {
        return res.status(error.response.status).json({
          success: false,
          error: error.response.data.error || 'Python service error'
        });
      }

      return res.status(500).json({
        success: false,
        error: 'Internal server error'
      });
    }
  };
};

module.exports = pythonProxy;
```

### 5.3 Admin Route Definitions

```javascript
// routes/admin.js
const express = require('express');
const router = express.Router();
const multer = require('multer');
const adminAuth = require('../middleware/adminAuth');
const pythonProxy = require('../middleware/pythonProxy');
const ontologyController = require('../controllers/admin/ontology');
const postgresController = require('../controllers/admin/postgresSync');

// File upload configuration
const upload = multer({
  dest: 'uploads/temp/',
  limits: { fileSize: 32 * 1024 * 1024 } // 32MB
});

// All admin routes require authentication
router.use(adminAuth);

// ===== Ontology Generation =====

// Upload files (Express handles file storage)
router.post('/ontology/upload',
  upload.array('files', 10),
  ontologyController.uploadFiles
);

// Generate ontology (Python service)
router.post('/ontology/generate',
  pythonProxy({
    endpoint: '/api/v1/ontology/generate',
    timeout: 600000 // 10 minutes
  }),
  ontologyController.handleGenerateResponse
);

// Stream progress (SSE)
router.get('/ontology/stream/:sessionId',
  ontologyController.streamProgress
);

// Session details
router.get('/ontology/sessions/:sessionId',
  ontologyController.getSession
);

// Download generated file
router.get('/ontology/download/:sessionId/:filename',
  ontologyController.downloadFile
);

// ===== PostgreSQL Sync =====

// List tables
router.get('/postgres/tables',
  postgresController.getTables
);

// Sync single table (Python for RDF conversion)
router.post('/postgres/sync/:tableName',
  pythonProxy({
    endpoint: '/api/v1/postgres/convert-table'
  }),
  postgresController.handleSyncResponse
);

// Stream sync progress
router.get('/postgres/sync-stream/:tableName',
  postgresController.streamSyncProgress
);

// Fuseki stats
router.get('/fuseki/stats',
  postgresController.getFusekiStats
);

// ===== Google Sheets =====

// Import sheet (Python for gspread)
router.post('/sheets/import',
  pythonProxy({
    endpoint: '/api/v1/sheets/import',
    timeout: 120000
  }),
  ontologyController.handleSheetsImport
);

// ===== System Health =====

router.get('/health',
  async (req, res) => {
    const pythonHealth = await checkPythonHealth();
    const postgresHealth = await checkPostgresHealth();
    const fusekiHealth = await checkFusekiHealth();

    res.json({
      status: 'healthy',
      services: {
        python: pythonHealth,
        postgres: postgresHealth,
        fuseki: fusekiHealth
      }
    });
  }
);

module.exports = router;
```

### 5.4 SSE Stream Handler

```javascript
// controllers/admin/ontology.js
const EventEmitter = require('events');
const sessionEmitter = new EventEmitter();

exports.streamProgress = (req, res) => {
  const { sessionId } = req.params;

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  // Send initial connection event
  res.write('data: {"type":"connected"}\n\n');

  // Listen for progress events
  const progressHandler = (data) => {
    if (data.session_id === sessionId) {
      res.write(`data: ${JSON.stringify(data)}\n\n`);

      // Close stream when complete
      if (data.type === 'complete' || data.type === 'error') {
        res.end();
      }
    }
  };

  sessionEmitter.on('progress', progressHandler);

  // Cleanup on client disconnect
  req.on('close', () => {
    sessionEmitter.off('progress', progressHandler);
    res.end();
  });
};

// Called by Python webhook or polling
exports.updateProgress = (sessionId, progressData) => {
  sessionEmitter.emit('progress', {
    session_id: sessionId,
    ...progressData
  });
};
```

---

## 6. Risk Assessment

### 6.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Python service downtime | HIGH | Medium | Health checks, graceful degradation, queue system |
| OWL generation timeout | HIGH | Low | Streaming progress, chunked processing |
| File upload size limits | Medium | Low | Chunk uploads, compression |
| SSE connection drops | Medium | Medium | Reconnection logic, fallback to polling |
| PostgreSQL query timeout (67k species) | HIGH | Medium | Batch processing, pagination, LIMIT defaults |
| Concurrent generation conflicts | Medium | Low | Session locking, queue management |
| Python/Node version mismatch | Low | Low | Docker containers |

### 6.2 Breaking Changes

| Change | Affected Users | Mitigation |
|--------|----------------|------------|
| New admin portal URL | Internal only | Redirect from old URLs |
| API endpoint restructure | None (internal) | N/A |
| File storage location | None (session-based) | Migrate old sessions |
| Progress update format | Frontend only | Versioned API |

### 6.3 Rollback Plan

**Phase 1: Dual-Run Period (2 weeks)**
- Keep Flask app running on separate port
- Run Next.js admin in parallel
- Compare outputs for validation
- Easy rollback: just use old URL

**Phase 2: Gradual Migration**
- Week 1: Internal testing only
- Week 2: Beta users (if applicable)
- Week 3: Full deployment
- Keep Flask code for 1 month backup

**Emergency Rollback:**
1. Revert nginx/proxy config (5 minutes)
2. Restart Flask service (2 minutes)
3. Disable Next.js admin routes (1 minute)

**Total rollback time:** < 10 minutes

---

## 7. Implementation Roadmap

### Phase 1: Python Microservice (Week 1-2)

**Goal:** Extract Python processing into standalone service

**Tasks:**
1. Create `graphflow-service/` directory
2. Refactor Flask routes into API endpoints
3. Remove HTML template dependencies
4. Add OpenAPI/Swagger documentation
5. Create Docker container
6. Write unit tests for each endpoint
7. Deploy to localhost:5002

**Deliverables:**
- Standalone Python service
- API documentation
- Health check endpoint
- Docker image

**Testing Checklist:**
- [ ] Generate ontology from CSV
- [ ] Convert PostgreSQL table to RDF
- [ ] Import Google Sheets
- [ ] Field analysis works
- [ ] All tests pass

### Phase 2: Express Integration (Week 2-3)

**Goal:** Create proxy layer in Treekipedia backend

**Tasks:**
1. Create `/backend/controllers/admin/` directory
2. Implement Python proxy middleware
3. Add admin authentication
4. Create SSE stream handlers
5. Add file upload endpoints
6. Implement session management
7. Add error handling

**Deliverables:**
- Express admin routes
- Python client library
- Session metadata storage
- Upload/download handlers

**Testing Checklist:**
- [ ] File uploads work
- [ ] Python proxy forwards correctly
- [ ] SSE streams work
- [ ] Auth blocks unauthorized access
- [ ] Error handling works

### Phase 3: Next.js Components (Week 3-5)

**Goal:** Build admin portal UI

**Tasks:**
1. Create `/app/admin/` directory structure
2. Implement OntologyUploadForm
3. Implement PostgresSyncDashboard
4. Implement SheetsImportForm
5. Add progress indicators
6. Create status cards
7. Add real-time updates
8. Style with Tailwind (match Treekipedia)

**Deliverables:**
- 5 main admin pages
- 15+ reusable components
- Custom hooks
- API client layer

**Testing Checklist:**
- [ ] Upload form works
- [ ] Progress updates display
- [ ] Sync controls work
- [ ] Real-time status updates
- [ ] Downloads work
- [ ] Mobile responsive

### Phase 4: Integration Testing (Week 5-6)

**Goal:** End-to-end testing and refinement

**Tasks:**
1. Full workflow testing
2. Performance optimization
3. Error handling edge cases
4. UI/UX refinement
5. Documentation updates
6. Load testing

**Deliverables:**
- Test suite (Cypress/Playwright)
- Performance benchmarks
- User documentation
- Deployment guide

**Testing Checklist:**
- [ ] Upload CSV → Generate → Download works
- [ ] Sheets import works
- [ ] PostgreSQL sync works
- [ ] Concurrent users work
- [ ] Error recovery works

### Phase 5: Deployment (Week 6-7)

**Goal:** Production deployment

**Tasks:**
1. Deploy Python service (Docker)
2. Update Treekipedia backend
3. Deploy Next.js changes
4. Update nginx config
5. Monitoring setup
6. Backup procedures

**Deliverables:**
- Production deployment
- Monitoring dashboards
- Backup system
- Rollback plan

**Production Checklist:**
- [ ] Python service running
- [ ] Health checks pass
- [ ] Admin portal accessible
- [ ] Authentication works
- [ ] Logs collecting
- [ ] Backups configured

---

## 8. Testing Strategy

### 8.1 Python Service Tests

```python
# tests/test_ontology_service.py
import pytest
from graphflow_service import create_app

@pytest.fixture
def client():
    app = create_app({'TESTING': True})
    with app.test_client() as client:
        yield client

def test_generate_ontology(client):
    """Test ontology generation endpoint"""
    response = client.post('/api/v1/ontology/generate', json={
        'session_id': 'test-123',
        'files': [
            {'name': 'test.csv', 'content': base64_csv}
        ],
        'ontology_name': 'test-ontology'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert 'ontology_file' in data
    assert data['analysis']['total_fields'] > 0

def test_postgres_to_rdf(client):
    """Test PostgreSQL to RDF conversion"""
    response = client.post('/api/v1/postgres/convert-table', json={
        'table_name': 'species',
        'batch_size': 100
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'rdf_content' in data
    assert data['triples_generated'] > 0
```

### 8.2 Express Integration Tests

```javascript
// tests/integration/admin.test.js
const request = require('supertest');
const app = require('../../server');

describe('Admin Ontology API', () => {
  it('should upload files', async () => {
    const response = await request(app)
      .post('/api/admin/ontology/upload')
      .attach('files', 'tests/fixtures/test.csv')
      .field('ontologyName', 'test-ontology')
      .expect(200);

    expect(response.body.session_id).toBeDefined();
  });

  it('should proxy to Python service', async () => {
    const response = await request(app)
      .post('/api/admin/ontology/generate')
      .send({
        session_id: 'test-123',
        files: ['test.csv']
      })
      .expect(200);

    expect(response.body.success).toBe(true);
  });
});
```

### 8.3 E2E Tests (Playwright)

```typescript
// tests/e2e/admin-ontology.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Admin Ontology Generation', () => {
  test('should complete full workflow', async ({ page }) => {
    // Navigate to upload page
    await page.goto('http://localhost:3000/admin/ontology/upload');

    // Upload CSV file
    await page.setInputFiles('input[type="file"]', 'tests/fixtures/mvp.csv');
    await page.fill('input[name="ontologyName"]', 'test-ontology');
    await page.click('button[type="submit"]');

    // Wait for generation
    await expect(page.locator('.progress-indicator')).toBeVisible();

    // Wait for completion (with timeout)
    await expect(page.locator('.download-button')).toBeVisible({
      timeout: 60000
    });

    // Verify results
    const analysisCard = page.locator('.analysis-summary');
    await expect(analysisCard).toContainText('Total Fields');
    await expect(analysisCard).toContainText('Ontology Classes');
  });

  test('should sync PostgreSQL table', async ({ page }) => {
    await page.goto('http://localhost:3000/admin/postgres-sync');

    // Click sync button for species table
    await page.click('[data-table="species"] button.sync-button');

    // Monitor progress
    const progressBar = page.locator('.batch-progress');
    await expect(progressBar).toBeVisible();

    // Wait for completion
    await expect(page.locator('.sync-complete')).toBeVisible({
      timeout: 120000
    });
  });
});
```

### 8.4 Load Testing

```javascript
// tests/load/ontology-generation.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 5 },   // Ramp up to 5 users
    { duration: '3m', target: 10 },  // Stay at 10 users
    { duration: '1m', target: 0 },   // Ramp down
  ],
};

export default function () {
  // Upload CSV
  const formData = {
    files: http.file(open('tests/fixtures/test.csv'), 'test.csv'),
    ontologyName: 'load-test'
  };

  const uploadRes = http.post(
    'http://localhost:3000/api/admin/ontology/upload',
    formData
  );

  check(uploadRes, {
    'upload successful': (r) => r.status === 200,
    'session ID returned': (r) => r.json('session_id') !== undefined
  });

  sleep(1);
}
```

---

## 9. Code Examples

### 9.1 Example: OntologySessionPage.tsx

```typescript
// app/admin/ontology/sessions/[sessionId]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useOntologySession } from '@/hooks/useOntologySession';
import { AnalysisSummary } from '../../components/AnalysisSummary';
import { DownloadCard } from '../../components/DownloadCard';
import { ProgressIndicator } from '@/components/admin/ProgressIndicator';

export default function OntologySessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const { session, loading, error } = useOntologySession(sessionId);

  if (loading) {
    return <ProgressIndicator message="Loading session details..." />;
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <p>Error loading session: {error.message}</p>
      </div>
    );
  }

  const isComplete = session?.status === 'complete';
  const isGenerating = session?.status === 'generating';

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">
        Ontology Generation: {session?.ontology_name}
      </h1>

      {/* Status Banner */}
      <div className={`alert mb-6 ${
        isComplete ? 'alert-success' :
        isGenerating ? 'alert-info' :
        'alert-warning'
      }`}>
        <p>
          Status: <strong>{session?.status}</strong>
        </p>
        {session?.created_at && (
          <p className="text-sm">
            Started: {new Date(session.created_at).toLocaleString()}
          </p>
        )}
      </div>

      {/* Progress Indicator */}
      {isGenerating && session?.progress && (
        <ProgressIndicator
          step={session.progress.step}
          percent={session.progress.percent}
          message={session.progress.message}
        />
      )}

      {/* Analysis Summary */}
      {isComplete && session?.analysis && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <AnalysisSummary analysis={session.analysis} />
          <DownloadCard
            sessionId={sessionId}
            filename={session.ontology_file}
            fileSize={session.file_size}
          />
        </div>
      )}

      {/* Detailed Analysis */}
      {isComplete && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Ontology Classes</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {session.analysis.ontology_classes.map((className) => (
              <div key={className} className="border rounded p-3">
                <h3 className="font-medium text-emerald-600">{className}</h3>
                <p className="text-sm text-gray-600">
                  {session.analysis.field_distribution[className] || 0} fields
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

### 9.2 Example: PostgreSQL Batch Sync Controller

```javascript
// controllers/admin/postgresSync.js
const logger = require('../../utils/logger');
const pythonClient = require('../../services/pythonClient');
const { sessionEmitter } = require('../../services/sessionManager');

/**
 * Sync PostgreSQL table to Fuseki with batch processing
 */
exports.syncTable = async (req, res) => {
  const { tableName } = req.params;
  const { batchSize = 1000 } = req.body;

  try {
    // Get table info first
    const tableInfo = await pythonClient.getTableInfo(tableName);

    if (!tableInfo.success) {
      return res.status(400).json({
        success: false,
        error: `Table ${tableName} not found`
      });
    }

    const totalRows = tableInfo.approx_rows;
    const totalBatches = Math.ceil(totalRows / batchSize);
    const sessionId = req.sessionID;

    logger.info(`Starting sync for ${tableName}: ${totalRows} rows in ${totalBatches} batches`);

    // Emit initial progress
    sessionEmitter.emit('sync-progress', {
      session_id: sessionId,
      table: tableName,
      type: 'started',
      total_rows: totalRows,
      total_batches: totalBatches
    });

    // Process batches (async background job)
    processBatchesInBackground(tableName, totalBatches, batchSize, sessionId);

    // Return immediately with job started
    res.json({
      success: true,
      session_id: sessionId,
      table_name: tableName,
      total_rows: totalRows,
      total_batches: totalBatches,
      message: 'Sync started, monitor progress via SSE stream'
    });

  } catch (error) {
    logger.error('Sync error:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
};

/**
 * Process batches in background
 */
async function processBatchesInBackground(tableName, totalBatches, batchSize, sessionId) {
  let recordsProcessed = 0;
  let triplesGenerated = 0;

  for (let batch = 0; batch < totalBatches; batch++) {
    try {
      const offset = batch * batchSize;

      // Call Python service for RDF conversion
      const result = await pythonClient.convertTableToRdf({
        table_name: tableName,
        batch_offset: offset,
        batch_size: batchSize
      });

      if (result.success) {
        recordsProcessed += result.records_processed;
        triplesGenerated += result.triples_generated;

        // Emit progress update
        sessionEmitter.emit('sync-progress', {
          session_id: sessionId,
          table: tableName,
          type: 'progress',
          batch: batch + 1,
          total_batches: totalBatches,
          records_processed: recordsProcessed,
          triples_generated: triplesGenerated,
          percent: Math.round(((batch + 1) / totalBatches) * 100)
        });
      } else {
        throw new Error(`Batch ${batch + 1} failed: ${result.error}`);
      }

    } catch (error) {
      logger.error(`Batch ${batch + 1} error:`, error);

      // Emit error
      sessionEmitter.emit('sync-progress', {
        session_id: sessionId,
        table: tableName,
        type: 'error',
        batch: batch + 1,
        error: error.message
      });

      return; // Stop processing
    }
  }

  // Emit completion
  sessionEmitter.emit('sync-progress', {
    session_id: sessionId,
    table: tableName,
    type: 'complete',
    records_processed: recordsProcessed,
    triples_generated: triplesGenerated
  });

  logger.info(`Sync complete for ${tableName}: ${recordsProcessed} records, ${triplesGenerated} triples`);
}

/**
 * Stream sync progress via SSE
 */
exports.streamSyncProgress = (req, res) => {
  const sessionId = req.sessionID;

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  // Send heartbeat every 30 seconds
  const heartbeat = setInterval(() => {
    res.write(': heartbeat\n\n');
  }, 30000);

  // Listen for progress events
  const progressHandler = (data) => {
    if (data.session_id === sessionId) {
      res.write(`data: ${JSON.stringify(data)}\n\n`);

      // Close stream on complete/error
      if (data.type === 'complete' || data.type === 'error') {
        clearInterval(heartbeat);
        res.end();
      }
    }
  };

  sessionEmitter.on('sync-progress', progressHandler);

  // Cleanup on disconnect
  req.on('close', () => {
    clearInterval(heartbeat);
    sessionEmitter.off('sync-progress', progressHandler);
    res.end();
  });
};
```

---

## 10. Time Estimates

### Detailed Timeline

| Phase | Task | Hours | Dependencies |
|-------|------|-------|--------------|
| **Phase 1** | Python service extraction | 16 | None |
| | API endpoint refactoring | 12 | Service extraction |
| | Docker containerization | 4 | API refactor |
| | Unit tests | 8 | API refactor |
| | **Phase 1 Total** | **40 hours** | **~1 week** |
| | | | |
| **Phase 2** | Express route setup | 8 | Phase 1 complete |
| | Python proxy middleware | 6 | Routes |
| | Session management | 4 | Routes |
| | File upload handlers | 6 | Routes |
| | SSE implementation | 8 | Routes |
| | Integration tests | 8 | All backend |
| | **Phase 2 Total** | **40 hours** | **~1 week** |
| | | | |
| **Phase 3** | Admin layout & nav | 8 | Phase 2 complete |
| | Ontology upload UI | 12 | Layout |
| | PostgreSQL sync UI | 16 | Layout |
| | Sheets import UI | 10 | Layout |
| | Version control UI | 8 | Layout |
| | Shared components | 12 | All pages |
| | Custom hooks | 8 | Components |
| | API client layer | 6 | Hooks |
| | Styling & responsiveness | 10 | All UI |
| | **Phase 3 Total** | **90 hours** | **~2.5 weeks** |
| | | | |
| **Phase 4** | E2E test setup | 6 | Phase 3 complete |
| | Workflow testing | 12 | Setup |
| | Performance optimization | 8 | Testing |
| | Error handling | 6 | Testing |
| | UI/UX refinement | 8 | Testing |
| | **Phase 4 Total** | **40 hours** | **~1 week** |
| | | | |
| **Phase 5** | Deployment scripts | 6 | Phase 4 complete |
| | Docker deployment | 4 | Scripts |
| | Monitoring setup | 6 | Deployment |
| | Documentation | 8 | All |
| | **Phase 5 Total** | **24 hours** | **~3 days** |
| | | | |
| **TOTAL** | | **234 hours** | **~6 weeks** |

### Resource Allocation

**Solo Developer:** 6-7 weeks (40 hours/week)
**Two Developers:** 3-4 weeks (parallel frontend/backend work)
**Team of Three:** 2-3 weeks (frontend, backend, testing in parallel)

---

## 11. Success Criteria

### Technical Metrics

- [ ] All 58 endpoints migrated and functional
- [ ] < 5 second response time for ontology generation (100 fields)
- [ ] < 30 seconds for PostgreSQL batch (1000 records)
- [ ] 99.9% uptime for Python service
- [ ] Zero data loss during migration
- [ ] < 100ms added latency from proxy layer

### Functional Requirements

- [ ] Upload CSV and generate ontology
- [ ] Import from Google Sheets
- [ ] Sync PostgreSQL tables to Fuseki
- [ ] Real-time progress updates
- [ ] Download generated files
- [ ] View session history
- [ ] Manage versions

### User Experience

- [ ] Responsive on mobile/tablet/desktop
- [ ] Consistent with Treekipedia design system
- [ ] Clear error messages
- [ ] Accessible (WCAG 2.1 AA)
- [ ] < 3 clicks to start generation

### Operational

- [ ] Docker deployment working
- [ ] Automated backups configured
- [ ] Monitoring/alerting active
- [ ] Documentation complete
- [ ] Rollback tested and working

---

## 12. Dependencies & Prerequisites

### Development Environment

```bash
# Node.js
node >= 18.0.0
npm >= 9.0.0

# Python
python >= 3.9
pip >= 21.0

# Database
postgresql >= 14
fuseki >= 4.0

# Tools
docker >= 20.0
docker-compose >= 2.0
```

### Python Packages

```txt
# requirements.txt for Python service
flask==2.3.3
owlready2==0.45
rdflib==7.0.0
gspread==5.12.0
psycopg2-binary==2.9.9
requests==2.31.0
python-dotenv==1.0.0
```

### Node.js Packages

```json
{
  "dependencies": {
    "axios": "^1.8.4",
    "multer": "^1.4.5-lts.1",
    "express": "^4.21.2",
    "@tanstack/react-query": "^5.69.0"
  },
  "devDependencies": {
    "playwright": "^1.40.0",
    "jest": "^29.7.0"
  }
}
```

---

## 13. Monitoring & Observability

### Metrics to Track

**Python Service:**
- Request rate (req/min)
- Response time (p50, p95, p99)
- Error rate (%)
- Ontology generation time
- RDF conversion rate (records/sec)
- Memory usage
- CPU usage

**Express Proxy:**
- Proxy latency
- SSE connection count
- File upload rate
- Session count
- Error rate

**Application:**
- Active sessions
- Completed generations
- Failed generations
- Download count
- Average file size

### Logging Strategy

```javascript
// Structured logging with Winston
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'treekipedia-admin' },
  transports: [
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error'
    }),
    new winston.transports.File({
      filename: 'logs/combined.log'
    })
  ]
});

// Log all Python service calls
pythonProxy.on('request', (req) => {
  logger.info('Python service call', {
    endpoint: req.url,
    method: req.method,
    session_id: req.sessionID
  });
});

pythonProxy.on('response', (req, res, duration) => {
  logger.info('Python service response', {
    endpoint: req.url,
    status: res.status,
    duration_ms: duration,
    session_id: req.sessionID
  });
});
```

### Health Checks

```javascript
// Health check endpoint
app.get('/api/admin/health', async (req, res) => {
  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {}
  };

  // Check Python service
  try {
    const pythonHealth = await axios.get('http://localhost:5002/api/v1/health', {
      timeout: 5000
    });
    health.services.python = {
      status: 'healthy',
      version: pythonHealth.data.version,
      uptime: pythonHealth.data.uptime_seconds
    };
  } catch (error) {
    health.status = 'degraded';
    health.services.python = {
      status: 'unhealthy',
      error: error.message
    };
  }

  // Check PostgreSQL
  try {
    await pool.query('SELECT 1');
    health.services.postgres = { status: 'healthy' };
  } catch (error) {
    health.status = 'degraded';
    health.services.postgres = {
      status: 'unhealthy',
      error: error.message
    };
  }

  // Check Fuseki
  try {
    const fusekiHealth = await axios.get('http://167.172.143.162:3030/$/ping', {
      timeout: 5000
    });
    health.services.fuseki = { status: 'healthy' };
  } catch (error) {
    health.status = 'degraded';
    health.services.fuseki = {
      status: 'unhealthy',
      error: error.message
    };
  }

  const statusCode = health.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});
```

---

## 14. Conclusion

This integration plan provides a comprehensive blueprint for rebuilding GraphFlow as a modern Next.js admin portal while preserving critical Python functionality. The phased approach minimizes risk and ensures a smooth transition with minimal downtime.

**Key Advantages:**
- Modern, responsive UI with Treekipedia design consistency
- Separation of concerns (UI, API, Processing)
- Scalable microservice architecture
- Real-time progress updates
- Easy rollback capability
- Comprehensive testing strategy

**Next Steps:**
1. Review and approve this plan
2. Set up development environment
3. Create project timeline
4. Begin Phase 1 implementation

**Questions or Concerns:**
- [ ] Confirm Python service port (5002 or other?)
- [ ] Confirm admin authentication strategy
- [ ] Confirm deployment target (Docker, VM, etc.)
- [ ] Confirm monitoring tools (Grafana, Datadog, etc.)
