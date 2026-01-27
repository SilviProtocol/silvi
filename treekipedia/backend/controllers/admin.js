/**
 * Admin Controller - Proxy to Python Microservice
 *
 * Routes admin requests from Express to Python microservice
 * Handles authentication, file uploads, and Server-Sent Events
 */

const axios = require('axios');
const FormData = require('form-data');

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5002';

/**
 * Health check - verify Python service is running
 */
exports.healthCheck = async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/api/health`, {
      timeout: 5000
    });

    res.json({
      ...response.data,
      proxy: 'express',
      proxyTime: new Date().toISOString()
    });
  } catch (error) {
    console.error('Python service health check failed:', error.message);
    res.status(503).json({
      error: 'Python microservice unavailable',
      message: error.message,
      proxy: 'express'
    });
  }
};

/**
 * Get service status (PostgreSQL, Fuseki, GraphFlow modules)
 */
exports.getStatus = async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/api/status`, {
      timeout: 10000
    });

    res.json(response.data);
  } catch (error) {
    console.error('Status check failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to get service status',
      message: error.message
    });
  }
};

/**
 * Get Fuseki statistics
 */
exports.getFusekiStatus = async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/api/status/fuseki`, {
      timeout: 10000
    });

    res.json(response.data);
  } catch (error) {
    console.error('Fuseki status check failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to get Fuseki status',
      message: error.message
    });
  }
};

/**
 * Sync species to Fuseki - Stream Server-Sent Events
 */
exports.syncSpecies = async (req, res) => {
  try {
    const { batchSize = 1000, table = 'species' } = req.body;

    // Set headers for Server-Sent Events
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    // Stream from Python service
    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/sync/species`,
      { batchSize, table },
      {
        responseType: 'stream',
        timeout: 3600000 // 1 hour timeout for large syncs
      }
    );

    // Pipe SSE stream to client
    response.data.pipe(res);

    // Handle stream end
    response.data.on('end', () => {
      res.end();
    });

    // Handle errors
    response.data.on('error', (error) => {
      console.error('Sync stream error:', error);
      res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
      res.end();
    });

  } catch (error) {
    console.error('Sync species failed:', error.message);

    // If headers not sent yet, send JSON error
    if (!res.headersSent) {
      res.status(error.response?.status || 500).json({
        error: 'Failed to sync species',
        message: error.message
      });
    } else {
      // If streaming already started, send SSE error
      res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
      res.end();
    }
  }
};

/**
 * Incremental sync - only new/updated species
 */
exports.syncIncremental = async (req, res) => {
  try {
    const { since } = req.body;

    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/sync/incremental`,
      { since },
      { timeout: 300000 } // 5 minute timeout
    );

    res.json(response.data);
  } catch (error) {
    console.error('Incremental sync failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to perform incremental sync',
      message: error.message
    });
  }
};

/**
 * Generate ontology from uploaded CSV files
 */
exports.generateOntology = async (req, res) => {
  try {
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ error: 'No files uploaded' });
    }

    // Create FormData and append files
    const formData = new FormData();
    req.files.forEach(file => {
      formData.append('files', file.buffer, {
        filename: file.originalname,
        contentType: file.mimetype
      });
    });

    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/ontology/generate`,
      formData,
      {
        headers: formData.getHeaders(),
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 300000 // 5 minute timeout
      }
    );

    res.json(response.data);
  } catch (error) {
    console.error('Ontology generation failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to generate ontology',
      message: error.message
    });
  }
};

/**
 * Generate ontology from Google Sheets
 */
exports.generateFromSheets = async (req, res) => {
  try {
    const { spreadsheetId, sheets } = req.body;

    if (!spreadsheetId) {
      return res.status(400).json({ error: 'spreadsheetId required' });
    }

    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/ontology/from-sheets`,
      { spreadsheetId, sheets },
      { timeout: 300000 } // 5 minute timeout
    );

    res.json(response.data);
  } catch (error) {
    console.error('Google Sheets ontology generation failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to generate ontology from Google Sheets',
      message: error.message
    });
  }
};

/**
 * Execute SPARQL query
 */
exports.executeSparqlQuery = async (req, res) => {
  try {
    const { query } = req.body;

    if (!query) {
      return res.status(400).json({ error: 'query required' });
    }

    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/sparql/query`,
      { query },
      { timeout: 60000 } // 1 minute timeout
    );

    res.json(response.data);
  } catch (error) {
    console.error('SPARQL query failed:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to execute SPARQL query',
      message: error.message
    });
  }
};

/**
 * List all ontology versions
 */
exports.listVersions = async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/api/versions`, {
      timeout: 10000
    });

    res.json(response.data);
  } catch (error) {
    console.error('Failed to list versions:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to list versions',
      message: error.message
    });
  }
};

/**
 * Create new ontology version snapshot
 */
exports.createVersion = async (req, res) => {
  try {
    const { description } = req.body;

    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/api/versions/create`,
      { description },
      { timeout: 60000 }
    );

    res.json(response.data);
  } catch (error) {
    console.error('Failed to create version:', error.message);
    res.status(error.response?.status || 500).json({
      error: 'Failed to create version',
      message: error.message
    });
  }
};
