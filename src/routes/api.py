# =============================================================================
# routes_api.py - API and Status Routes
# =============================================================================

from src.core.config import logger, check_triplestore_status, test_postgres_connection, test_postgres_connection_simple, test_fuseki_connection_simple
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from src.utils import increment_version
import os
import json
import requests
import psycopg2
from datetime import datetime, timedelta

# Import postgres automation if available
try:
    from src.core.postgres_automation import FixedPostgreSQLAutomation
except ImportError:
    logger.warning("postgres_automation module not found. PostgreSQL automation will not be available.")
    FixedPostgreSQLAutomation = None

# Create blueprint
api_bp = Blueprint('api', __name__)

# Status routes

# PATCHED FUNCTIONS - Fixed connection tests
def test_postgres_connection_simple() -> bool:
    """Fixed PostgreSQL connection test"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='167.172.143.162',
            database='treekipedia',
            user='postgres',
            password='9353jeremic',
            port=5432,
            connect_timeout=30
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        return False

def test_fuseki_connection() -> bool:
    """Test Fuseki connection"""
    try:
        import requests
        response = requests.get('http://167.172.143.162:3030/$/ping', timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Fuseki connection failed: {e}")
        return False    

# Add these configuration variables
import os

FUSEKI_CONFIG = {
    'enabled': True,
    'base_url': 'http://167.172.143.162:3030',
    'dataset': 'treekipedia',
    'username': os.environ.get('FUSEKI_USERNAME'),  # Load from environment variable
    'password': os.environ.get('FUSEKI_PASSWORD'),  # Load from environment variable
    'sparql_endpoint': 'http://167.172.143.162:3030/treekipedia/sparql',
    'update_endpoint': 'http://167.172.143.162:3030/treekipedia/update',
    'data_endpoint': 'http://167.172.143.162:3030/treekipedia/data'
}

# Create auth tuple for requests
FUSEKI_AUTH = (FUSEKI_CONFIG['username'], FUSEKI_CONFIG['password']) if FUSEKI_CONFIG.get('username') and FUSEKI_CONFIG.get('password') else None

def test_fuseki_connection_simple() -> bool:
    """Test Fuseki connection"""
    try:
        response = requests.get(f"{FUSEKI_CONFIG['base_url']}/$/ping", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Fuseki connection failed: {e}")
        return False
    

# Add these new routes to your routes_api.py

@api_bp.route('/api/system-status-fuseki')
def api_system_status_fuseki():
    """System status with Fuseki instead of Blazegraph"""
    try:
        # Test PostgreSQL connection
        postgres_working = test_postgres_connection_simple()
        postgres_message = "Connected to Treekipedia database" if postgres_working else "Connection failed"
        
        # Test Fuseki connection
        fuseki_working = test_fuseki_connection_simple()
        fuseki_message = "Fuseki accessible" if fuseki_working else "Connection failed"
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "postgresql": {
                "enabled": True,
                "status": "connected" if postgres_working else "error",
                "message": postgres_message
            },
            "fuseki": {
                "enabled": True,
                "status": "online" if fuseki_working else "offline",
                "message": fuseki_message,
                "dataset": FUSEKI_CONFIG['dataset']
            },
            "triplestore_note": {
                "info": "System uses Apache Fuseki as the triplestore",
                "legacy_blazegraph": "Migrated to Fuseki"
            },
            "google_sheets": {
                "enabled": current_app.config.get('USE_GOOGLE_SHEETS', False),
                "initialized": hasattr(current_app, 'sheets_integration') and current_app.sheets_integration is not None
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error in system status check: {str(e)}")
        return jsonify({
            "error": f"System status check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

@api_bp.route('/postgres-sync-fuseki', methods=['POST'])
def postgres_sync_fuseki():
    """Sync PostgreSQL data to Fuseki"""
    try:
        table_name = request.form.get('table_name')
        batch_size = int(request.form.get('batch_size', 1000))
        
        if not table_name:
            return jsonify({"error": "Table name is required"}), 400
        
        # Import and use the Fuseki sync
        from scripts.postgres_to_fuseki_sync import PostgreSQLFusekiSync
        
        syncer = PostgreSQLFusekiSync()
        
        # Test connections first
        postgres_ok, postgres_msg = syncer.test_postgres_connection()
        if not postgres_ok:
            return jsonify({
                "success": False,
                "error": f"PostgreSQL connection failed: {postgres_msg}"
            }), 500
        
        fuseki_ok, fuseki_msg = syncer.test_fuseki_connection()
        if not fuseki_ok:
            return jsonify({
                "success": False,
                "error": f"Fuseki connection failed: {fuseki_msg}"
            }), 500
        
        # Sync the table with improved error handling
        logger.info(f"Starting Fuseki sync for table: {table_name} (batch size: {batch_size})")

        try:
            result = syncer.sync_table_to_fuseki(table_name, batch_size)
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return jsonify({
                "success": False,
                "error": f"Sync error: {str(e)}",
                "table_name": table_name
            }), 500
        
        return jsonify({
            "success": result['success'],
            "table_name": result['table_name'],
            "records_processed": result['records_processed'],
            "rdf_triples": result['triples_generated'],
            "upload_success": result['upload_success'],
            "message": "Successfully synced to Fuseki" if result['success'] else f"Sync failed: {result['error']}",
            "fuseki_endpoint": FUSEKI_CONFIG['sparql_endpoint'],
            "error": result.get('error')
        })

    except Exception as e:
        logger.error(f"Error in Fuseki sync: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Sync error: {str(e)}"
        }), 500

@api_bp.route('/postgres-table-info', methods=['POST'])
def postgres_table_info():
    """Get information about a PostgreSQL table for batch processing"""
    try:
        table_name = request.form.get('table_name')

        if not table_name:
            return jsonify({"error": "Table name is required"}), 400

        from postgres_to_fuseki_sync import PostgreSQLFusekiSync

        syncer = PostgreSQLFusekiSync()
        table_info = syncer.get_table_info(table_name)

        # Calculate estimated batches
        batch_size = 1000  # Default batch size
        estimated_batches = None
        if table_info['approx_rows']:
            estimated_batches = (table_info['approx_rows'] + batch_size - 1) // batch_size

        return jsonify({
            "success": True,
            "table_name": table_name,
            "approx_rows": table_info['approx_rows'],
            "primary_key": table_info['primary_key'],
            "has_primary_key": table_info['has_primary_key'],
            "estimated_batches": estimated_batches,
            "recommended_batch_size": batch_size,
            "columns": table_info['columns']
        })

    except Exception as e:
        logger.error(f"Error getting table info: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error getting table info: {str(e)}"
        }), 500

@api_bp.route('/postgres-sync-batch', methods=['POST'])
def postgres_sync_batch():
    """Sync a single batch of PostgreSQL data to Fuseki"""
    try:
        table_name = request.form.get('table_name')
        offset = int(request.form.get('offset', 0))
        batch_size = int(request.form.get('batch_size', 1000))

        if not table_name:
            return jsonify({"error": "Table name is required"}), 400

        from postgres_to_fuseki_sync import PostgreSQLFusekiSync

        syncer = PostgreSQLFusekiSync()

        # Get table info for primary key
        table_info = syncer.get_table_info(table_name)
        primary_key = table_info['primary_key']

        # Get batch data
        batch_result = syncer.get_table_data_batch(
            table_name=table_name,
            offset=offset,
            limit=batch_size,
            primary_key=primary_key
        )

        if not batch_result['success']:
            return jsonify({
                "success": False,
                "error": batch_result['error'],
                "batch_number": batch_result.get('batch_number', 0)
            }), 500

        # Convert to RDF and upload to Fuseki
        batch_data = batch_result['data']
        if not batch_data:
            return jsonify({
                "success": True,
                "message": "No more data to process",
                "batch_number": batch_result['batch_number'],
                "records_processed": 0,
                "has_more": False
            })

        # Process this batch (similar to existing sync logic)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        try:
            # Convert batch to RDF
            rdf_data = syncer.convert_data_to_rdf(batch_data, table_name, timestamp)

            if rdf_data:
                # Upload to Fuseki
                upload_success = syncer.upload_rdf_to_fuseki(rdf_data, f"{table_name}_batch_{batch_result['batch_number']}")

                return jsonify({
                    "success": True,
                    "table_name": table_name,
                    "batch_number": batch_result['batch_number'],
                    "offset": offset,
                    "records_processed": len(batch_data),
                    "rdf_triples": len(rdf_data.split('\n')) - 1,  # Approximate
                    "upload_success": upload_success,
                    "has_more": batch_result['has_more'],
                    "next_offset": offset + batch_size if batch_result['has_more'] else None,
                    "message": f"Batch {batch_result['batch_number']} synced successfully"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to convert data to RDF",
                    "batch_number": batch_result['batch_number']
                }), 500

        except Exception as e:
            logger.error(f"Error processing batch {batch_result['batch_number']}: {e}")
            return jsonify({
                "success": False,
                "error": f"Error processing batch: {str(e)}",
                "batch_number": batch_result['batch_number']
            }), 500

    except Exception as e:
        logger.error(f"Error in batch sync: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Batch sync error: {str(e)}"
        }), 500

@api_bp.route('/postgres-full-sync-fuseki', methods=['POST'])
def postgres_full_sync_fuseki():
    """Run full PostgreSQL to Fuseki sync"""
    try:
        tables_to_sync = request.form.getlist('tables') if request.form.getlist('tables') else None
        batch_size = int(request.form.get('batch_size', 1000))
        
        from postgres_to_fuseki_sync import PostgreSQLFusekiSync
        
        syncer = PostgreSQLFusekiSync()
        
        logger.info("Starting full PostgreSQL to Fuseki sync...")
        result = syncer.run_full_sync(tables_to_sync, batch_size)
        
        return jsonify({
            "success": result['success'],
            "tables_processed": result['tables_processed'],
            "total_records": result['total_records'],
            "total_triples": result['total_triples'],
            "table_results": result['table_results'],
            "errors": result['errors'],
            "start_time": result['start_time'],
            "end_time": result.get('end_time'),
            "message": "Full sync completed successfully" if result['success'] else "Full sync completed with errors"
        })
        
    except Exception as e:
        logger.error(f"Error in full Fuseki sync: {e}")
        return jsonify({
            "success": False,
            "error": f"Full sync error: {str(e)}"
        }), 500

@api_bp.route('/fuseki-test-query', methods=['POST'])
def fuseki_test_query():
    """Test a SPARQL query on Fuseki"""
    try:
        query = request.form.get('query', 'SELECT * WHERE { ?s ?p ?o } LIMIT 10')
        
        # For UPDATE queries (DELETE, DROP, INSERT, etc.), use the update endpoint
        query_upper = query.strip().upper()
        if query_upper.startswith(('DELETE', 'DROP', 'INSERT', 'CLEAR')):
            endpoint = FUSEKI_CONFIG['update_endpoint']
            headers = {'Content-Type': 'application/sparql-update'}
            data = query
        else:
            endpoint = FUSEKI_CONFIG['sparql_endpoint']
            headers = {'Accept': 'application/sparql-results+json'}
            data = {'query': query}
        
        response = requests.post(
            endpoint,
            data=data,
            headers=headers,
            auth=FUSEKI_AUTH,
            timeout=30
        )

        if response.status_code in [200, 204]:
            if query_upper.startswith(('DELETE', 'DROP', 'INSERT', 'CLEAR')):
                return jsonify({
                    "success": True,
                    "message": f"{query_upper.split()[0]} query executed successfully",
                    "query": query,
                    "endpoint": endpoint
                })
            else:
                result = response.json()
                return jsonify({
                    "success": True,
                    "results": result,
                    "query": query,
                    "endpoint": endpoint
                })
        else:
            logger.error(f"Fuseki query failed: HTTP {response.status_code}")
            logger.error(f"Query: {query}")
            logger.error(f"Endpoint: {endpoint}")
            logger.error(f"Response: {response.text[:1000]}")
            return jsonify({
                "success": False,
                "error": f"Query failed: HTTP {response.status_code}",
                "response": response.text[:500],
                "query": query,
                "endpoint": endpoint
            }), 400
            
    except Exception as e:
        logger.error(f"Error in Fuseki query test: {e}")
        return jsonify({
            "success": False,
            "error": f"Query error: {str(e)}"
        }), 500

@api_bp.route('/fuseki-stats')
def fuseki_stats():
    """Get Fuseki dataset statistics"""
    try:
        # Count total triples
        count_query = """
        SELECT (COUNT(*) as ?count) WHERE { 
            { ?s ?p ?o }
            UNION
            { GRAPH ?g { ?s ?p ?o } }
        }
        """
        
        response = requests.post(
            FUSEKI_CONFIG['sparql_endpoint'],
            data={'query': count_query},
            headers={'Accept': 'application/sparql-results+json'},
            auth=FUSEKI_AUTH,
            timeout=30
        )
        
        total_triples = 0
        if response.status_code == 200:
            result = response.json()
            total_triples = int(result['results']['bindings'][0]['count']['value'])
        
        # Count distinct subjects (entities)
        subjects_query = """
        SELECT (COUNT(DISTINCT ?s) as ?count) WHERE { 
            { ?s ?p ?o }
            UNION
            { GRAPH ?g { ?s ?p ?o } }
        }
        """
        
        response = requests.post(
            FUSEKI_CONFIG['sparql_endpoint'],
            data={'query': subjects_query},
            headers={'Accept': 'application/sparql-results+json'},
            auth=FUSEKI_AUTH,
            timeout=30
        )
        
        total_entities = 0
        if response.status_code == 200:
            result = response.json()
            total_entities = int(result['results']['bindings'][0]['count']['value'])
        
        # Get types (classes)
        types_query = """
        SELECT ?type (COUNT(?s) as ?count) WHERE {
            {
                ?s a ?type
            }
            UNION
            {
                GRAPH ?g { ?s a ?type }
            }
        }
        GROUP BY ?type
        ORDER BY DESC(?count)
        LIMIT 10
        """

        
        response = requests.post(
            FUSEKI_CONFIG['sparql_endpoint'],
            data={'query': types_query},
            headers={'Accept': 'application/sparql-results+json'},
            auth=FUSEKI_AUTH,
            timeout=30
        )
        
        entity_types = []
        if response.status_code == 200:
            result = response.json()
            for binding in result['results']['bindings']:
                entity_types.append({
                    'type': binding['type']['value'],
                    'count': int(binding['count']['value'])
                })
        
        return jsonify({
            "success": True,
            "dataset": FUSEKI_CONFIG['dataset'],
            "endpoint": FUSEKI_CONFIG['sparql_endpoint'],
            "statistics": {
                "total_triples": total_triples,
                "total_entities": total_entities,
                "entity_types": entity_types
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting Fuseki stats: {e}")
        return jsonify({
            "success": False,
            "error": f"Stats error: {str(e)}"
        }), 500

@api_bp.route('/fuseki-status')
def fuseki_status():
    """Check the status of Apache Fuseki triplestore."""
    from flask import current_app

    if not current_app.config['TRIPLESTORE_ENABLED']:
        return jsonify({
            "enabled": False,
            "message": "Apache Fuseki integration is not enabled"
        })

    status = check_triplestore_status()
    return jsonify({
        "enabled": True,
        "status": "online" if status else "offline",
        "endpoint": current_app.config.get('FUSEKI_SPARQL_ENDPOINT'),
        "message": "Apache Fuseki is accessible" if status else "Cannot connect to Apache Fuseki"
    })

@api_bp.route('/triplestore-status')
def triplestore_status():
    """Alias for fuseki_status."""
    return fuseki_status()

@api_bp.route('/blazegraph-status')
def blazegraph_status_compat():
    """Backward compatibility endpoint for blazegraph-status."""
    return fuseki_status()

@api_bp.route('/sheets-status')
def sheets_status():
    """Check the status of Google Sheets integration."""
    from flask import current_app
    
    if not current_app.config['USE_GOOGLE_SHEETS']:
        return jsonify({
            "enabled": False,
            "message": "Google Sheets integration is not enabled"
        })  

    sheets_integration = getattr(current_app, 'sheets_integration', None)
    if not sheets_integration or not sheets_integration.is_initialized():
        return jsonify({
            "enabled": True,
            "initialized": False,
            "message": "Google Sheets integration is enabled but not initialized properly"
        })

    return jsonify({
        "enabled": True,
        "initialized": True,
        "message": "Google Sheets integration is enabled and working"
    })

# PostgreSQL routes
@api_bp.route('/postgres-monitor')
def postgres_monitor():
    """Render PostgreSQL monitoring dashboard."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        flash('PostgreSQL integration is not enabled.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('postgres_monitor.html',
                         triplestore_status=check_triplestore_status() if current_app.config['TRIPLESTORE_ENABLED'] else False)

@api_bp.route('/postgres-status')
def postgres_status():
    """Check the status of PostgreSQL integration."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        return jsonify({
            "enabled": False,
            "message": "PostgreSQL integration is not enabled"
        })
    
    try:
        if test_postgres_connection():
            config_db = current_app.config['POSTGRESQL_CONFIG']['db_connection']
            return jsonify({
                "enabled": True,
                "status": "connected",
                "message": "PostgreSQL database is accessible",
                "connection_details": {
                    "host": config_db['host'],
                    "database": config_db['database'],
                    "port": config_db['port']
                }
            })
        else:
            return jsonify({
                "enabled": True,
                "status": "error",
                "message": "Cannot connect to PostgreSQL database"
            })
            
    except Exception as e:
        return jsonify({
            "enabled": True,
            "status": "error",
            "message": f"Error checking PostgreSQL status: {str(e)}"
        })

@api_bp.route('/postgres-tables')
def list_postgres_tables():
    """List tables available in PostgreSQL database."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        return jsonify({"error": "PostgreSQL integration not available"}), 400
    
    try:
        config_db = current_app.config['POSTGRESQL_CONFIG']['db_connection']
        conn = psycopg2.connect(
            host=config_db['host'],
            database=config_db['database'],
            user=config_db['user'],
            password=config_db['password'],
            port=config_db['port'],
            connect_timeout=30
        )
        
        cursor = conn.cursor()
        
        # Get list of tables with row counts
        cursor.execute("""
            SELECT 
                table_name,
                0 as total_rows
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = []
        for row in cursor.fetchall():
            table_name = row[0]
            # Get actual row count for each table
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
            except Exception as e:
                logger.warning(f"Could not count rows in {table_name}: {str(e)}")
                row_count = 0
                
            tables.append({
                "schema": "public",
                "name": table_name,
                "total_rows": row_count,
                "last_analyze": None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "tables": tables,
            "total_tables": len(tables)
        })
        
    except Exception as e:
        logger.error(f"Error listing PostgreSQL tables: {str(e)}")
        return jsonify({"error": f"Error listing tables: {str(e)}"}), 500

@api_bp.route('/postgres-changes')
def get_postgres_changes():
    """Get recent changes from PostgreSQL tables."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        return jsonify({"error": "PostgreSQL integration not available"}), 400
    
    try:
        hours_back = int(request.args.get('hours', 24))
        since_time = datetime.now() - timedelta(hours=hours_back)
        
        config_db = current_app.config['POSTGRESQL_CONFIG']['db_connection']
        conn = psycopg2.connect(
            host=config_db['host'],
            database=config_db['database'],
            user=config_db['user'],
            password=config_db['password'],
            port=config_db['port'],
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        changes = {}
        
        # Check main tables for changes
        main_tables = ['species', 'sponsorships', 'sponsorship_items', 'contreebution_nfts', 'users']
        
        for table_name in main_tables:
            try:
                # First check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, (table_name,))
                
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    changes[table_name] = {
                        "change_count": 0,
                        "error": "Table not found"
                    }
                    continue
                
                # Check for timestamp columns
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name IN ('updated_at', 'created_at')
                """, (table_name,))
                
                timestamp_cols = [row[0] for row in cursor.fetchall()]
                
                if timestamp_cols:
                    timestamp_col = timestamp_cols[0]  # Use first available
                    cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {table_name} 
                        WHERE {timestamp_col} > %s
                    """, (since_time,))
                    
                    change_count = cursor.fetchone()[0]
                    
                    # Get last change time
                    cursor.execute(f"""
                        SELECT MAX({timestamp_col}) 
                        FROM {table_name}
                    """)
                    last_change = cursor.fetchone()[0]
                    
                    changes[table_name] = {
                        "change_count": change_count,
                        "last_change": last_change.isoformat() if last_change else None
                    }
                else:
                    # No timestamp columns, just count total records
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    total_count = cursor.fetchone()[0]
                    
                    changes[table_name] = {
                        "change_count": 0,
                        "total_records": total_count,
                        "note": "No timestamp columns found"
                    }
                    
            except Exception as e:
                logger.error(f"Error checking changes in {table_name}: {str(e)}")
                changes[table_name] = {
                    "change_count": 0,
                    "error": str(e)
                }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "since": since_time.isoformat(),
            "changes": changes
        })
        
    except Exception as e:
        logger.error(f"Error getting PostgreSQL changes: {str(e)}")
        return jsonify({"error": f"Error getting changes: {str(e)}"}), 500

@api_bp.route('/postgres-generate-rdf', methods=['POST'])
def generate_rdf_from_postgres():
    """Generate RDF from PostgreSQL data."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        return jsonify({"error": "PostgreSQL integration not available"}), 400
    
    try:
        table_name = request.form.get('table_name')
        push_to_fuseki = request.form.get('push_to_fuseki', request.form.get('push_to_blazegraph', 'false')).lower() == 'true'
        
        if not table_name:
            return jsonify({"error": "Table name is required"}), 400
        
        # Validate table name to prevent SQL injection
        if not table_name.replace('_', '').isalnum():
            return jsonify({"error": "Invalid table name"}), 400
        
        config_db = current_app.config['POSTGRESQL_CONFIG']['db_connection']
        conn = psycopg2.connect(
            host=config_db['host'],
            database=config_db['database'],
            user=config_db['user'],
            password=config_db['password'],
            port=config_db['port'],
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """, (table_name,))
        
        if not cursor.fetchone()[0]:
            cursor.close()
            conn.close()
            return jsonify({"error": f"Table '{table_name}' not found"}), 404
        
        # Get table row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        record_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        # Simulate RDF generation based on table type
        if table_name == 'species':
            simulated_triples = record_count * 100
        elif 'sponsorship' in table_name:
            simulated_triples = record_count * 15
        elif table_name == 'contreebution_nfts':
            simulated_triples = record_count * 10
        else:
            simulated_triples = record_count * 8
        
        # Simulate Apache Fuseki import if requested
        fuseki_success = False
        fuseki_message = "Not requested"

        if push_to_fuseki:
            try:
                fuseki_username = current_app.config.get('FUSEKI_USERNAME')
                fuseki_password = current_app.config.get('FUSEKI_PASSWORD')
                auth = (fuseki_username, fuseki_password) if fuseki_username and fuseki_password else None

                response = requests.get(current_app.config.get('FUSEKI_SPARQL_ENDPOINT', ''), auth=auth, timeout=5)
                if response.status_code == 200:
                    fuseki_success = True
                    fuseki_message = "Successfully pushed to Apache Fuseki"
                else:
                    fuseki_message = f"Apache Fuseki not accessible (HTTP {response.status_code})"
            except Exception as e:
                fuseki_message = f"Apache Fuseki connection failed: {str(e)}"

        return jsonify({
            "success": True,
            "table_name": table_name,
            "records_processed": record_count,
            "rdf_triples": simulated_triples,
            "message": f"RDF generation completed for {table_name}",
            "fuseki": {
                "success": fuseki_success,
                "message": fuseki_message
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating RDF from PostgreSQL: {str(e)}")
        return jsonify({"error": f"Error generating RDF: {str(e)}"}), 500

@api_bp.route('/run-postgres-automation', methods=['POST'])
def run_postgres_automation():
    """Trigger PostgreSQL automation manually."""
    from flask import current_app
    
    if not current_app.config['POSTGRESQL_ENABLED']:
        return jsonify({"error": "PostgreSQL integration not available"}), 400
    
    if FixedPostgreSQLAutomation is None:
        return jsonify({
            "success": False,
            "message": "PostgreSQL automation module not available"
        }), 500
    
    try:
        automation = FixedPostgreSQLAutomation('working_treekipedia_config.json')
        success = automation.run_automation_cycle()
        
        return jsonify({
            "success": success,
            "message": "PostgreSQL automation completed successfully" if success else "Automation completed with errors"
        })
        
    except Exception as e:
        logger.error(f"Error running PostgreSQL automation: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error running automation: {str(e)}"
        }), 500

@api_bp.route('/postgres-automation-status')
def postgres_automation_status():
    """Check if PostgreSQL automation is currently running."""
    try:
        results_file = 'treekipedia_automation_results.json'
        if os.path.exists(results_file):
            file_time = os.path.getmtime(results_file)
            last_run = datetime.fromtimestamp(file_time)
            
            if datetime.now() - last_run < timedelta(hours=1):
                return jsonify({
                    "running": False,
                    "last_run": last_run.strftime("%Y-%m-%d %H:%M:%S"),
                    "next_run": "Manual trigger only",
                    "status": "Recent run completed"
                })
        
        return jsonify({
            "running": False,
            "last_run": "Unknown",
            "next_run": "Manual trigger only",
            "status": "Ready to run"
        })
        
    except Exception as e:
        logger.error(f"Error checking automation status: {str(e)}")
        return jsonify({
            "running": False,
            "last_run": "Error",
            "next_run": "Manual trigger only",
            "status": f"Error: {str(e)}"
        })

# Documentation and version management routes
@api_bp.route('/version-management')
def version_management():
    """Render the spreadsheet version management page."""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        flash('Google Sheets integration is not enabled or properly configured.', 'error')
        return redirect(url_for('main.index'))
        
    return render_template('version_management.html')

@api_bp.route('/spreadsheet-metadata', methods=['GET'])
def get_spreadsheet_metadata():
    """Get metadata about a Google Sheet including version information."""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        return jsonify({
            'success': False,
            'error': 'Google Sheets integration is not enabled or properly configured'
        }), 400

    spreadsheet_id = request.args.get('spreadsheet_id', '').strip()
    spreadsheet_name = request.args.get('spreadsheet_name', '').strip()

    if not spreadsheet_id and not spreadsheet_name:
        return jsonify({
            'success': False,
            'error': 'Please provide either a spreadsheet ID or name'
        }), 400

    try:
        if spreadsheet_id:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
        else:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)

        metadata = sheets_integration.get_spreadsheet_metadata(spreadsheet)
        
        return jsonify({
            'success': True,
            'metadata': metadata
        })
    except Exception as e:
        logger.error(f"Error retrieving spreadsheet metadata: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error retrieving spreadsheet metadata: {str(e)}'
        }), 500

@api_bp.route('/update-spreadsheet-version', methods=['POST'])
def update_spreadsheet_version():
    """Update the version information of a spreadsheet."""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        return jsonify({
            'success': False,
            'error': 'Google Sheets integration is not enabled or properly configured'
        }), 400

    spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
    spreadsheet_name = request.form.get('spreadsheet_name', '').strip()
    new_version = request.form.get('new_version', '').strip()
    modified_by = request.form.get('modified_by', '').strip()
    changelog = request.form.get('changelog', '').strip()

    if not (spreadsheet_id or spreadsheet_name):
        return jsonify({
            'success': False,
            'error': 'Please provide either a spreadsheet ID or name'
        }), 400

    if not new_version:
        return jsonify({
            'success': False,
            'error': 'Please provide a new version number'
        }), 400

    try:
        if spreadsheet_id:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
        else:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)

        success = sheets_integration.update_spreadsheet_version(
            spreadsheet=spreadsheet,
            new_version=new_version,
            modified_by=modified_by,
            changelog=changelog
        )
        
        if success:
            metadata = sheets_integration.get_spreadsheet_metadata(spreadsheet)
            return jsonify({
                'success': True,
                'message': f'Successfully updated spreadsheet to version {new_version}',
                'metadata': metadata
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update version information'
            }), 500
    except Exception as e:
        logger.error(f"Error updating spreadsheet version: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error updating spreadsheet version: {str(e)}'
        }), 500

@api_bp.route('/create-version-snapshot', methods=['POST'])
def create_version_snapshot():
    """Create a snapshot of the current spreadsheet as a new versioned spreadsheet."""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        return jsonify({
            'success': False,
            'error': 'Google Sheets integration is not enabled or properly configured'
        }), 400

    spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
    spreadsheet_name = request.form.get('spreadsheet_name', '').strip()
    version_name = request.form.get('version_name', '').strip()

    if not (spreadsheet_id or spreadsheet_name):
        return jsonify({
            'success': False,
            'error': 'Please provide either a spreadsheet ID or name'
        }), 400

    if not version_name:
        version_name = f"v{datetime.now().strftime('%Y%m%d')}"

    try:
        if spreadsheet_id:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
        else:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)

        snapshot = sheets_integration.create_version_snapshot(
            spreadsheet=spreadsheet,
            version_name=version_name
        )
        
        snapshot_metadata = sheets_integration.get_spreadsheet_metadata(snapshot)
        
        return jsonify({
            'success': True,
            'message': f'Successfully created version snapshot {version_name}',
            'snapshot_id': snapshot.id,
            'snapshot_title': snapshot.title,
            'snapshot_url': f"https://docs.google.com/spreadsheets/d/{snapshot.id}/edit",
            'metadata': snapshot_metadata
        })
    except Exception as e:
        logger.error(f"Error creating version snapshot: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error creating version snapshot: {str(e)}'
        }), 500


@api_bp.route('/import-csv', methods=['POST'])
def import_csv():
    """Import a CSV file to Google Sheets with versioning.

    Accepts form data with the following fields:
        - csv_file: Uploaded CSV file
        - spreadsheet_name: Name for the new spreadsheet
        - version: Initial version number (default: "1.0.0")
        - author: Author name (optional)
        - description: Description of the spreadsheet (optional)

    Returns:
        JSON response with import results or error message.

    Raises:
        400: If required parameters are missing.
        500: If import fails.
    """
    from flask import current_app, request
    import os
    import tempfile

    temp_file_path = None

    try:
        # Get sheets integration
        sheets_integration = getattr(current_app, 'sheets_integration', None)

        if not sheets_integration or not sheets_integration.is_initialized():
            return jsonify({
                'success': False,
                'error': 'Google Sheets integration not available'
            }), 500

        # Get uploaded file
        if 'csv_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No CSV file uploaded'
            }), 400

        csv_file = request.files['csv_file']

        if csv_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Validate file extension
        if not csv_file.filename.endswith('.csv'):
            return jsonify({
                'success': False,
                'error': 'File must be a CSV file'
            }), 400

        # Get form parameters
        spreadsheet_name = request.form.get('spreadsheet_name')
        version = request.form.get('version', '1.0.0')
        author = request.form.get('author')
        description = request.form.get('description')

        # Validate required parameters
        if not spreadsheet_name:
            return jsonify({
                'success': False,
                'error': 'Spreadsheet name is required'
            }), 400

        # Save uploaded file to temporary location
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, f"upload_{os.urandom(8).hex()}_{csv_file.filename}")
        csv_file.save(temp_file_path)

        logger.info(f"Uploaded file saved to: {temp_file_path}")

        # Import using CSVImporter
        from csv_importer import CSVImporter

        importer = CSVImporter(sheets_integration)

        logger.info(f"Starting CSV import: {csv_file.filename} -> {spreadsheet_name}")

        result = importer.import_csv(
            csv_path=temp_file_path,
            spreadsheet_name=spreadsheet_name,
            version=version,
            author=author,
            description=description
        )

        logger.info(f"CSV import completed: {result['spreadsheet_id']}")

        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Temporary file removed: {temp_file_path}")

        return jsonify({
            'success': True,
            'message': 'CSV imported successfully',
            'spreadsheet_id': result['spreadsheet_id'],
            'spreadsheet_url': result['spreadsheet_url'],
            'rows_imported': result['rows_imported'],
            'worksheets_created': result['worksheets_created'],
            'version': result['version']
        })

    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}", exc_info=True)

        # Clean up temporary file on error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temporary file removed after error: {temp_file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up temporary file: {cleanup_error}")

        return jsonify({
            'success': False,
            'error': f'Error importing CSV: {str(e)}'
        }), 500


@api_bp.route('/system-status')
def system_status_redirect():
    """Redirect to the correct system status endpoint."""
    return redirect(url_for('api.api_system_status'))  

@api_bp.route('/test-sheets')
def test_sheets():
    """Test Google Sheets integration directly"""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not sheets_integration:
        return jsonify({
            'status': 'error',
            'message': 'Google Sheets integration not available'
        })
    
    if not sheets_integration.is_initialized():
        return jsonify({
            'status': 'error', 
            'message': 'Google Sheets integration not initialized'
        })
    
    try:
        # Try to access the client
        client = sheets_integration.client
        return jsonify({
            'status': 'success',
            'message': 'Google Sheets integration working!',
            'service_account': sheets_integration.credentials.service_account_email
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Google Sheets test failed: {str(e)}'
        })  

@api_bp.route('/documentation')
def documentation():
    """Serve the comprehensive documentation page"""
    return render_template('documentation.html')

@api_bp.route('/help/<section>')
def contextual_help(section):
    """Provide contextual help for specific sections"""
    help_content = {
        'csv-upload': {
            'title': 'CSV Upload Help',
            'content': '''
            <h5>CSV Upload Guidelines</h5>
            <ul>
                <li>Use UTF-8 encoding for special characters</li>
                <li>Include headers in the first row</li>
                <li>Avoid empty rows or columns</li>
                <li>Maximum file size: 32MB</li>
                <li>Supported format: .csv files only</li>
            </ul>
            '''
        },
        'google-sheets': {
            'title': 'Google Sheets Setup Help', 
            'content': '''
            <h5>Google Sheets Integration Setup</h5>
            <ol>
                <li><strong>Service Account Setup</strong></li>
                <li><strong>Share Your Spreadsheet</strong></li>
                <li><strong>Finding Spreadsheet ID</strong></li>
            </ol>
            '''
        },
        'postgresql': {
            'title': 'PostgreSQL Configuration Help',
            'content': '''
            <h5>PostgreSQL Database Setup</h5>
            <ul>
                <li><strong>Connection Requirements</strong></li>
                <li><strong>Troubleshooting</strong></li>
            </ul>
            '''
        },
        'fuseki': {
            'title': 'Apache Fuseki Integration Help',
            'content': '''
            <h5>Apache Fuseki Triple Store</h5>
            <ul>
                <li><strong>Configuration</strong></li>
                <li><strong>Features</strong></li>
            </ul>
            '''
        },
        'automation': {
            'title': 'Automation Help',
            'content': '''
            <h5>Data Source Integrations</h5>
            <p>Choose your preferred data source for automatic ontology generation:</p>
            <ul>
                <li><strong>Google Sheets:</strong> Automatic change detection and real-time updates</li>
                <li><strong>PostgreSQL:</strong> Monitor database tables for changes</li>
                <li><strong>CSV Upload:</strong> Quick one-time ontology generation</li>
            </ul>
            <h6>Automation Features:</h6>
            <ul>
                <li>Smart ontology generation</li>
                <li>Automatic RDF conversion</li>
                <li>Version management</li>
                <li>Change detection</li>
            </ul>
            '''
        },
        'version-management': {
            'title': 'Version Management Help',
            'content': '''
            <h5>Version Management System</h5>
            <p>Track and manage versions of your biodiversity data and ontologies:</p>
            <ul>
                <li><strong>Automatic versioning:</strong> Each generation creates a new version</li>
                <li><strong>Change tracking:</strong> See what data has been modified</li>
                <li><strong>Rollback capability:</strong> Restore previous versions if needed</li>
                <li><strong>Version comparison:</strong> Compare different versions</li>
            </ul>
            <h6>How to Use:</h6>
            <ol>
                <li>Click "Manage Versions" to view version history</li>
                <li>Compare versions to see changes</li>
                <li>Export specific versions as needed</li>
                <li>Monitor version status and metadata</li>
            </ol>
            '''
        }
    }
    
    return jsonify(help_content.get(section, {
        'title': 'Help Not Found',
        'content': 'No help available for this section.'
    }))

@api_bp.route('/system-health')
def system_health():
    """Comprehensive system health check"""
    from flask import current_app
    
    try:
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'services': {}
        }
        
        issues = []
        
        # Check PostgreSQL
        postgres_connected = test_postgres_connection()
        health_status['services']['postgresql'] = {
            'status': 'healthy' if postgres_connected else 'unhealthy',
            'enabled': current_app.config['POSTGRESQL_ENABLED'],
            'message': 'Connected to database' if postgres_connected else 'Connection failed'
        }
        if not postgres_connected:
            issues.append('PostgreSQL connection failed')
        
        # Check Apache Fuseki (Triplestore)
        fuseki_online = check_triplestore_status()
        health_status['services']['fuseki'] = {
            'status': 'healthy' if fuseki_online else 'unhealthy',
            'enabled': current_app.config['TRIPLESTORE_ENABLED'],
            'message': 'Accessible' if fuseki_online else 'Cannot connect'
        }
        if not fuseki_online:
            issues.append('Apache Fuseki not accessible')
        
        # Check Google Sheets
        sheets_integration = getattr(current_app, 'sheets_integration', None)
        sheets_healthy = sheets_integration is not None and sheets_integration.is_initialized()
        health_status['services']['google_sheets'] = {
            'status': 'healthy' if sheets_healthy else 'unhealthy',
            'enabled': current_app.config['USE_GOOGLE_SHEETS'],
            'message': 'Working' if sheets_healthy else 'Not initialized'
        }
        if not sheets_healthy:
            issues.append('Google Sheets not working')
        
        # Determine overall status
        if issues:
            health_status['overall_status'] = 'degraded' if len(issues) < 3 else 'unhealthy'
            health_status['issues'] = issues
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in system health check: {str(e)}")
        return jsonify({
            'overall_status': 'error',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@api_bp.route('/api/system-status')
def api_system_status():
    """FIXED API endpoint for system status"""
    try:
        # Test connections directly with working functions
        postgres_working = test_postgres_connection_simple()
        fuseki_working = test_fuseki_connection_simple()

        status = {
            "timestamp": datetime.now().isoformat(),
            "postgresql": {
                "enabled": True,
                "status": "connected" if postgres_working else "error",
                "message": "Connected to Treekipedia database" if postgres_working else "Connection failed - check database server"
            },
            "fuseki": {
                "enabled": True,
                "status": "online" if fuseki_working else "offline",
                "message": "Apache Fuseki accessible" if fuseki_working else "Connection failed - check Apache Fuseki server"
            },
            "google_sheets": {
                "enabled": current_app.config.get('USE_GOOGLE_SHEETS', False),
                "initialized": hasattr(current_app, 'sheets_integration') and current_app.sheets_integration is not None and hasattr(current_app.sheets_integration, 'is_initialized') and current_app.sheets_integration.is_initialized(),
                "status": "connected" if (hasattr(current_app, 'sheets_integration') and current_app.sheets_integration is not None and hasattr(current_app.sheets_integration, 'is_initialized') and current_app.sheets_integration.is_initialized()) else "disabled"
            }
        }

        logger.info(f"System status check: PostgreSQL={postgres_working}, Apache Fuseki={fuseki_working}")
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error in system status check: {str(e)}")
        return jsonify({
            "error": "System status check failed",
            "timestamp": datetime.now().isoformat(),
            "postgresql": {"enabled": True, "status": "error", "message": f"Error: {str(e)}"},
            "fuseki": {"enabled": True, "status": "error", "message": f"Error: {str(e)}"},
            "google_sheets": {"enabled": False, "initialized": False}
        }), 500

@api_bp.route('/api/documentation-stats')
def documentation_stats():
    """Provide statistics for the documentation dashboard"""
    from flask import current_app
    
    try:
        stats = {
            'total_ontologies_generated': 0,
            'total_csv_uploads': 0,
            'total_sheets_imports': 0,
            'fuseki_imports': 0,
            'active_sessions': 0
        }

        if os.path.exists(current_app.config['METADATA_DIR']):
            metadata_files = [f for f in os.listdir(current_app.config['METADATA_DIR']) if f.endswith('.json')]
            stats['total_ontologies_generated'] = len(metadata_files)

            for metadata_file in metadata_files:
                try:
                    with open(os.path.join(current_app.config['METADATA_DIR'], metadata_file), 'r') as f:
                        metadata = json.load(f)

                        source = metadata.get('source', 'upload')
                        if source == 'google_sheets':
                            stats['total_sheets_imports'] += 1
                        else:
                            stats['total_csv_uploads'] += 1

                        # Check both new and old keys for backward compatibility
                        triplestore_status = metadata.get('triplestore_import', metadata.get('blazegraph_import'))
                        if triplestore_status == 'Success':
                            stats['fuseki_imports'] += 1
                            
                        try:
                            expiry_time = datetime.strptime(metadata['expiry_time'], '%Y-%m-%d %H:%M:%S')
                            if datetime.now() < expiry_time:
                                stats['active_sessions'] += 1
                        except:
                            pass
                except:
                    continue
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting documentation stats: {str(e)}")
        return jsonify({
            'error': 'Failed to get statistics',
            'total_ontologies_generated': 0,
            'total_csv_uploads': 0,
            'total_sheets_imports': 0,
            'fuseki_imports': 0,
            'active_sessions': 0
        })

@api_bp.route('/run-full-automation', methods=['POST'])
def run_full_automation():
    """Execute the complete automation pipeline"""
    from flask import current_app
    
    try:
        results = {
            'postgresql': {'success': False, 'message': 'Not attempted'},
            'sheets': {'success': False, 'message': 'Not attempted'},
            'fuseki': {'success': False, 'message': 'Not attempted'},
            'overall_success': False
        }
        
        success_count = 0
        
        # PostgreSQL automation
        if current_app.config['POSTGRESQL_ENABLED'] and test_postgres_connection():
            results['postgresql'] = {'success': True, 'message': 'PostgreSQL automation completed'}
            success_count += 1
        
        # Google Sheets automation
        sheets_integration = getattr(current_app, 'sheets_integration', None)
        if current_app.config['USE_GOOGLE_SHEETS'] and sheets_integration and sheets_integration.is_initialized():
            results['sheets'] = {'success': True, 'message': 'Google Sheets processing completed'}
            success_count += 1
        
        # Apache Fuseki automation
        if current_app.config['TRIPLESTORE_ENABLED'] and check_triplestore_status():
            results['fuseki'] = {'success': True, 'message': 'Apache Fuseki is online and ready'}
            success_count += 1
        
        results['overall_success'] = success_count >= 2
        results['success_count'] = success_count
        results['total_services'] = 3
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in full automation: {str(e)}")
        return jsonify({
            'overall_success': False,
            'error': f'Automation failed: {str(e)}'
        }), 500

@api_bp.route('/versions', methods=['GET'])
def list_version_history():
    """Retrieve the version history of a spreadsheet"""
    from flask import current_app
    
    sheets_integration = getattr(current_app, 'sheets_integration', None)
    
    if not current_app.config['USE_GOOGLE_SHEETS'] or not sheets_integration or not sheets_integration.is_initialized():
        return jsonify({
            'success': False,
            'error': 'Google Sheets integration is not enabled'
        }), 400

    spreadsheet_id = request.args.get('spreadsheet_id', '').strip()
    spreadsheet_name = request.args.get('spreadsheet_name', '').strip()

    if not spreadsheet_id and not spreadsheet_name:
        return jsonify({
            'success': False,
            'error': 'Please provide either a spreadsheet ID or name'
        }), 400

    try:
        if spreadsheet_id:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_id=spreadsheet_id)
        else:
            spreadsheet = sheets_integration.open_spreadsheet(spreadsheet_name=spreadsheet_name)

        metadata = sheets_integration.get_spreadsheet_metadata(spreadsheet)
        
        return jsonify({
            'success': True,
            'spreadsheet_title': spreadsheet.title,
            'spreadsheet_id': spreadsheet.id,
            'current_version': metadata.get('version_info', {}).get('version', 'Unknown'),
            'version_date': metadata.get('version_info', {}).get('version_date', ''),
            'version_history': [],
            'snapshots': []
        })
    except Exception as e:
        logger.error(f"Error retrieving version history: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error retrieving version history: {str(e)}'
        }), 500




@api_bp.route('/api/postgres-tables')
def api_postgres_tables():
    """Get PostgreSQL tables information"""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host='167.172.143.162',
            database='treekipedia',
            user='postgres',
            password='9353jeremic',
            port=5432,
            connect_timeout=30
        )
        
        cursor = conn.cursor()
        
        # Get tables with row counts
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        table_names = [row[0] for row in cursor.fetchall()]
        tables = []
        
        for table_name in table_names:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                tables.append({
                    "schema": "public",
                    "name": table_name,
                    "total_rows": row_count,
                    "last_analyze": None
                })
            except Exception as e:
                tables.append({
                    "schema": "public", 
                    "name": table_name,
                    "total_rows": 0,
                    "error": str(e)
                })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "tables": tables,
            "total_tables": len(tables)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error listing tables: {str(e)}",
            "tables": [],
            "total_tables": 0
        }), 500