/**
 * Admin Routes - GraphFlow Integration
 *
 * Routes for admin portal functionality
 * All routes proxy to Python microservice
 */

const express = require('express');
const router = express.Router();
const multer = require('multer');
const adminController = require('../controllers/admin');

// File upload configuration
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 32 * 1024 * 1024, // 32MB max file size
    files: 10 // Max 10 files at once
  },
  fileFilter: (req, file, cb) => {
    // Accept CSV files only
    if (file.mimetype === 'text/csv' || file.originalname.endsWith('.csv')) {
      cb(null, true);
    } else {
      cb(new Error('Only CSV files are allowed'));
    }
  }
});

// ============================================================================
// Health & Status Routes
// ============================================================================

/**
 * GET /api/admin/health
 * Health check for Python microservice
 */
router.get('/health', adminController.healthCheck);

/**
 * GET /api/admin/status
 * Get status of all services (PostgreSQL, Fuseki, GraphFlow)
 */
router.get('/status', adminController.getStatus);

/**
 * GET /api/admin/status/fuseki
 * Get detailed Fuseki statistics
 */
router.get('/status/fuseki', adminController.getFusekiStatus);

// ============================================================================
// Sync Routes
// ============================================================================

/**
 * POST /api/admin/sync/species
 * Sync species from PostgreSQL to Fuseki
 * Returns Server-Sent Events stream with progress
 *
 * Body:
 * {
 *   "batchSize": 1000,  // optional
 *   "table": "species"   // optional
 * }
 */
router.post('/sync/species', adminController.syncSpecies);

/**
 * POST /api/admin/sync/incremental
 * Incremental sync - only new/updated species
 *
 * Body:
 * {
 *   "since": "2025-01-01T00:00:00Z"  // ISO timestamp
 * }
 */
router.post('/sync/incremental', adminController.syncIncremental);

// ============================================================================
// Ontology Generation Routes
// ============================================================================

/**
 * POST /api/admin/ontology/generate
 * Generate OWL ontology from uploaded CSV files
 * Multipart/form-data with files
 */
router.post('/ontology/generate', upload.array('files', 10), adminController.generateOntology);

/**
 * POST /api/admin/ontology/from-sheets
 * Generate ontology from Google Sheets
 *
 * Body:
 * {
 *   "spreadsheetId": "abc123...",
 *   "sheets": ["Sheet1", "Sheet2"]  // optional
 * }
 */
router.post('/ontology/from-sheets', adminController.generateFromSheets);

// ============================================================================
// SPARQL Routes
// ============================================================================

/**
 * POST /api/admin/sparql/query
 * Execute SPARQL query against Fuseki
 *
 * Body:
 * {
 *   "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
 * }
 */
router.post('/sparql/query', adminController.executeSparqlQuery);

// ============================================================================
// Version Management Routes
// ============================================================================

/**
 * GET /api/admin/versions
 * List all ontology versions
 */
router.get('/versions', adminController.listVersions);

/**
 * POST /api/admin/versions/create
 * Create new ontology version snapshot
 *
 * Body:
 * {
 *   "description": "Version description"
 * }
 */
router.post('/versions/create', adminController.createVersion);

// ============================================================================
// Error Handling
// ============================================================================

// Handle multer errors
router.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({
        error: 'File too large',
        message: 'Maximum file size is 32MB'
      });
    }
    if (error.code === 'LIMIT_FILE_COUNT') {
      return res.status(400).json({
        error: 'Too many files',
        message: 'Maximum 10 files allowed'
      });
    }
  }

  if (error.message === 'Only CSV files are allowed') {
    return res.status(400).json({
      error: 'Invalid file type',
      message: error.message
    });
  }

  next(error);
});

module.exports = router;
