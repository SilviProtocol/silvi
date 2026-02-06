"""
Treekipedia Python Microservice - API Only
Headless Python backend for GraphFlow functionality
No HTML templates - all responses are JSON or Server-Sent Events

This service provides:
- OWL/RDF ontology generation (owlready2, rdflib)
- PostgreSQL → Fuseki synchronization
- Google Sheets integration (gspread)
- Multi-sheet biodiversity ontology generation
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
import traceback

# Add GraphFlow modules to path
GRAPHFLOW_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'graphflow-extracted', 'silvi-open-graphflow')
sys.path.insert(0, GRAPHFLOW_PATH)

# Import GraphFlow modules
try:
    from postgres_to_fuseki_sync import PostgreSQLFusekiSync
    from multi_sheet_biodiversity_generator import MultiSheetBiodiversityOntologyGenerator
    from incremental_species_sync import IncrementalSpeciesSync
    GRAPHFLOW_AVAILABLE = True
except ImportError as e:
    GRAPHFLOW_AVAILABLE = False
    logging.warning(f"GraphFlow modules not available: {e}")

# Configuration
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

# CORS - only allow Express backend and Next.js frontend
CORS(app, origins=[
    'http://localhost:5001',  # Express backend
    'http://localhost:3000',  # Next.js dev (for development)
    'http://localhost:3001',  # Next.js dev (alternate port)
])

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============================================================================
# Health Check & Status Endpoints
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'treekipedia-python-microservice',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'graphflow_available': GRAPHFLOW_AVAILABLE
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get status of all connected services"""
    status = {
        'postgres': {'status': 'unknown', 'message': ''},
        'fuseki': {'status': 'unknown', 'message': ''},
        'graphflow_modules': {'status': 'available' if GRAPHFLOW_AVAILABLE else 'unavailable'}
    }

    if GRAPHFLOW_AVAILABLE:
        try:
            sync = PostgreSQLFusekiSync()

            # Test PostgreSQL
            pg_ok, pg_msg = sync.test_postgres_connection()
            status['postgres'] = {
                'status': 'connected' if pg_ok else 'disconnected',
                'message': pg_msg
            }

            # Test Fuseki
            fuseki_ok, fuseki_msg = sync.test_fuseki_connection()
            status['fuseki'] = {
                'status': 'connected' if fuseki_ok else 'disconnected',
                'message': fuseki_msg
            }

        except Exception as e:
            logger.error(f"Error checking status: {e}")
            status['error'] = str(e)

    return jsonify(status)

@app.route('/api/status/fuseki', methods=['GET'])
def get_fuseki_status():
    """Get detailed Fuseki statistics"""
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    try:
        sync = PostgreSQLFusekiSync()
        fuseki_ok, fuseki_msg = sync.test_fuseki_connection()

        if not fuseki_ok:
            return jsonify({
                'status': 'disconnected',
                'message': fuseki_msg
            }), 503

        # Get triple count
        stats = sync.get_fuseki_stats()

        return jsonify({
            'status': 'connected',
            'endpoint': os.getenv('FUSEKI_SPARQL_ENDPOINT'),
            'dataset': os.getenv('FUSEKI_DATASET'),
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error getting Fuseki status: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# PostgreSQL → Fuseki Sync Endpoints
# ============================================================================

@app.route('/api/sync/species', methods=['POST'])
def sync_species():
    """
    Sync species table from PostgreSQL to Fuseki
    Streams progress back as Server-Sent Events

    Request body:
    {
        "batchSize": 1000,  // optional, default 1000
        "table": "species"   // optional, default "species"
    }
    """
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    data = request.get_json() or {}
    batch_size = data.get('batchSize', 1000)
    table_name = data.get('table', 'species')

    def generate():
        """Generator function for Server-Sent Events"""
        try:
            sync = PostgreSQLFusekiSync()

            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting sync...'})}\n\n"

            # Test connections
            pg_ok, pg_msg = sync.test_postgres_connection()
            if not pg_ok:
                yield f"data: {json.dumps({'type': 'error', 'message': f'PostgreSQL connection failed: {pg_msg}'})}\n\n"
                return

            fuseki_ok, fuseki_msg = sync.test_fuseki_connection()
            if not fuseki_ok:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Fuseki connection failed: {fuseki_msg}'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'status', 'message': 'Connections verified'})}\n\n"

            # Sync table
            # Note: We'll need to modify sync.sync_table_to_fuseki to accept a progress callback
            # For now, send periodic updates
            yield f"data: {json.dumps({'type': 'progress', 'message': f'Syncing {table_name} with batch size {batch_size}...'})}\n\n"

            sync.sync_table_to_fuseki(table_name, batch_size=batch_size)

            yield f"data: {json.dumps({'type': 'complete', 'message': 'Sync completed successfully'})}\n\n"

        except Exception as e:
            logger.error(f"Sync error: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/sync/incremental', methods=['POST'])
def sync_incremental():
    """
    Incremental sync - only sync new/updated species

    Request body:
    {
        "since": "2025-01-01T00:00:00Z"  // optional, ISO timestamp
    }
    """
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    data = request.get_json() or {}
    since = data.get('since')

    try:
        sync = IncrementalSpeciesSync()
        result = sync.sync_new_species(since_timestamp=since)

        return jsonify({
            'success': True,
            'synced': result.get('synced_count', 0),
            'message': 'Incremental sync completed'
        })

    except Exception as e:
        logger.error(f"Incremental sync error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Ontology Generation Endpoints
# ============================================================================

@app.route('/api/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    Generate OWL ontology from uploaded CSV files

    Request: multipart/form-data with files
    Response: JSON with ontology download URL or error
    """
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')

    try:
        # Save uploaded files
        file_paths = []
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                file_paths.append(filepath)

        # Generate ontology
        generator = MultiSheetBiodiversityOntologyGenerator()
        result = generator.process_files(file_paths)

        return jsonify({
            'success': True,
            'ontology_path': result.get('ontology_path'),
            'field_detection': result.get('detected_fields'),
            'quality_score': result.get('quality_score')
        })

    except Exception as e:
        logger.error(f"Ontology generation error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ontology/from-sheets', methods=['POST'])
def generate_from_sheets():
    """
    Generate ontology from Google Sheets

    Request body:
    {
        "spreadsheetId": "abc123...",
        "sheets": ["Sheet1", "Sheet2"]  // optional
    }
    """
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    data = request.get_json()
    if not data or 'spreadsheetId' not in data:
        return jsonify({'error': 'spreadsheetId required'}), 400

    spreadsheet_id = data['spreadsheetId']
    sheet_names = data.get('sheets')

    try:
        generator = MultiSheetBiodiversityOntologyGenerator()
        result = generator.process_google_sheet(spreadsheet_id, sheet_names)

        return jsonify({
            'success': True,
            'ontology_path': result.get('ontology_path'),
            'sheets_processed': result.get('sheets_processed'),
            'field_detection': result.get('detected_fields')
        })

    except Exception as e:
        logger.error(f"Google Sheets ontology error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SPARQL Query Endpoints
# ============================================================================

@app.route('/api/sparql/query', methods=['POST'])
def sparql_query():
    """
    Execute SPARQL query against Fuseki

    Request body:
    {
        "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
    }
    """
    if not GRAPHFLOW_AVAILABLE:
        return jsonify({'error': 'GraphFlow modules not available'}), 503

    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'query required'}), 400

    query = data['query']

    try:
        sync = PostgreSQLFusekiSync()
        results = sync.execute_sparql_query(query)

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"SPARQL query error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Version Management Endpoints
# ============================================================================

@app.route('/api/versions', methods=['GET'])
def list_versions():
    """List all ontology versions"""
    # TODO: Implement version tracking
    return jsonify({
        'versions': [],
        'message': 'Version management coming soon'
    })

@app.route('/api/versions/create', methods=['POST'])
def create_version():
    """Create new ontology version snapshot"""
    # TODO: Implement version creation
    return jsonify({
        'success': True,
        'message': 'Version creation coming soon'
    })

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5002))
    debug = os.getenv('FLASK_ENV') == 'development'

    logger.info(f"Starting Treekipedia Python Microservice on port {port}")
    logger.info(f"GraphFlow modules available: {GRAPHFLOW_AVAILABLE}")
    logger.info(f"CORS enabled for: http://localhost:5001, http://localhost:3000")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
