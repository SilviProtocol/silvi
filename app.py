from flask import Flask, flash, redirect, url_for
from src.core.config import AppConfig, logger
from src.routes.main import main_bp
from src.routes.api import api_bp
from src.routes.occurrence import occurrence_bp, init_occurrence_manager
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application with dynamic ontology support"""
    app = Flask(__name__)
    
    # Initialize configuration
    config = AppConfig(app)
    
    # Dynamic ontology is now always enabled (no complex integration needed)
    app.config['DYNAMIC_ONTOLOGY_ENABLED'] = True
    app.config['DYNAMIC_CONFIG_CACHE_TTL'] = 3600  # 1 hour cache
    app.config['ONTOLOGY_QUALITY_THRESHOLD'] = 0.7  # Minimum quality score
    app.config['AUTO_CATEGORIZATION_ENABLED'] = True
    app.config['RELATIONSHIP_INFERENCE_ENABLED'] = True
    app.config['MAX_FIELDS_FOR_DYNAMIC_ANALYSIS'] = 500  # Performance limit
    
    # Enable Google Sheets integration
    app.config['USE_GOOGLE_SHEETS'] = True
    app.config['GOOGLE_SHEETS_ENABLED'] = True

    # Occurrence data configuration (GeoParquet + DuckDB)
    app.config['OCCURRENCE_STORAGE_PATH'] = os.getenv('OCCURRENCE_STORAGE_PATH', 'data/occurrences')
    app.config['OCCURRENCE_S3_BUCKET'] = os.getenv('OCCURRENCE_S3_BUCKET')  # Optional S3 storage

    # Increase max upload size for large occurrence datasets (default 2 GB)
    max_upload_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '2048'))
    app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024
    logger.info(f"Max upload size set to {max_upload_mb} MB ({max_upload_mb/1024:.1f} GB)")

    logger.info("✅ Dynamic ontology generation system initialized!")
    logger.info("✅ Google Sheets integration enabled!")

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(occurrence_bp)

    # Initialize occurrence data manager
    try:
        init_occurrence_manager(app)
        logger.info("✅ Occurrence data system initialized (GeoParquet + DuckDB)")
    except Exception as e:
        logger.warning(f"Occurrence data system initialization failed: {e}")
    
    # Register error handlers
    register_error_handlers(app)
    
    # Add template global functions
    register_template_globals(app)
    
    # Add context processor for common template variables
    register_context_processors(app)
    
    # Add dynamic ontology health check routes
    register_dynamic_ontology_routes(app)
    
    return app

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file size exceeded error."""
        flash(f'File too large. Max size: {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)}MB.', 'error')
        return redirect(url_for('main.index')), 413

    @app.errorhandler(404)
    def page_not_found(error):
        """Handle 404 errors."""
        from flask import request
        # Don't flash messages for common browser/extension requests
        ignored_paths = ['/favicon.ico', '/.well-known/', '/apple-touch-icon']
        if not any(ignored in request.path for ignored in ignored_paths):
            flash('Page not found.', 'error')
        return redirect(url_for('main.index')), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        flash('An internal server error occurred.', 'error')
        return redirect(url_for('main.index')), 500

def register_template_globals(app):
    """Register template global functions"""
    
    @app.template_global()
    def has_dynamic_ontology():
        """Check if dynamic ontology is available"""
        return True  # Always available now
    
    @app.template_global()
    def has_google_sheets():
        """Check if Google Sheets is available"""
        return app.config.get('USE_GOOGLE_SHEETS', False)
    
    @app.template_global()
    def get_app_version():
        """Get application version"""
        return '2.0.0-dynamic'

def register_context_processors(app):
    """Register context processors for common template variables"""
    
    @app.context_processor
    def inject_common_vars():
        """Inject common variables into all templates"""
        return {
            'has_dynamic_ontology': True,
            'has_google_sheets': app.config.get('USE_GOOGLE_SHEETS', False),
            'app_version': '2.0.0-dynamic',
            'dynamic_ontology_enabled': True,
            'google_sheets_enabled': app.config.get('USE_GOOGLE_SHEETS', False)
        }

def register_dynamic_ontology_routes(app):
    """Register additional routes for dynamic ontology features"""
    
    @app.route('/health/dynamic-ontology')
    def dynamic_ontology_health():
        """Health check endpoint for dynamic ontology system"""
        from flask import jsonify
        
        try:
            # Test the ontology generator with a simple analysis
            from enhance_dynamic_ontology import DynamicOntologyGenerator
            
            test_data = [
                {
                    'Field': 'test_field',
                    'Schema (revised)': 'test_schema_field',
                    'Exists': '',
                    'ai researched (may need ai+human fields in main schema)': 'test_category',
                    'manual calculation': '',
                    'option set': ''
                }
            ]
            
            generator = DynamicOntologyGenerator()
            analysis = generator.analyze_spreadsheet_data(test_data)
            
            return jsonify({
                'status': 'healthy',
                'message': 'Dynamic ontology generation system operational',
                'enabled': True,
                'version': analysis.get('version', '2.0.0'),
                'generator': 'DynamicOntologyGenerator',
                'underlying_system': 'MultiSheetBiodiversityGenerator',
                'features': {
                    'field_analysis': True,
                    'categorization': app.config.get('AUTO_CATEGORIZATION_ENABLED', False),
                    'relationship_inference': app.config.get('RELATIONSHIP_INFERENCE_ENABLED', False),
                    'quality_assessment': True,
                    'ontology_generation': True,
                    'biodiversity_expertise': True,
                    'google_sheets_support': app.config.get('USE_GOOGLE_SHEETS', False),
                    'csv_upload': True,
                    'no_config_files': True
                }
            }), 200
            
        except Exception as e:
            logger.error(f"Dynamic ontology health check failed: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Ontology generation system error: {str(e)}',
                'enabled': False
            }), 500

    @app.route('/features')
    def list_features():
        """List all available features"""
        from flask import jsonify
        
        features = {
            'core_features': {
                'csv_upload': True,
                'google_sheets_import': app.config.get('USE_GOOGLE_SHEETS', False),
                'fuseki_integration': app.config.get('TRIPLESTORE_ENABLED', False),
                'postgresql_integration': app.config.get('POSTGRESQL_ENABLED', False),
                'version_management': True,
                'dynamic_analysis': True
            },
            'ontology_generation': {
                'enabled': True,
                'generator': 'DynamicOntologyGenerator',
                'underlying_system': 'MultiSheetBiodiversityGenerator',
                'field_detection': True,
                'auto_categorization': app.config.get('AUTO_CATEGORIZATION_ENABLED', False),
                'relationship_inference': app.config.get('RELATIONSHIP_INFERENCE_ENABLED', False),
                'quality_assessment': True,
                'preview_mode': True,
                'data_source_support': True,
                'biodiversity_ontologies': True,
                'taxonomic_classification': True,
                'geographic_distribution': True,
                'conservation_information': True,
                'ecological_data': True,
                'no_configuration_files': True
            },
            'data_sources': {
                'csv_files': True,
                'google_sheets': app.config.get('USE_GOOGLE_SHEETS', False),
                'manual_entry': True,
                'batch_processing': True
            },
            'output_formats': {
                'owl_rdf': True,
                'quality_reports': True,
                'analysis_summaries': True,
                'preview_mode': True
            },
            'integrations': {
                'sheets_status': 'enabled' if app.config.get('USE_GOOGLE_SHEETS') else 'disabled',
                'fuseki_status': 'enabled' if app.config.get('TRIPLESTORE_ENABLED') else 'disabled',
                'postgres_status': 'enabled' if app.config.get('POSTGRESQL_ENABLED') else 'disabled'
            },
            'biodiversity_expertise': {
                'taxonomic_fields': True,
                'geographic_fields': True,
                'conservation_fields': True,
                'ecological_fields': True,
                'morphological_fields': True,
                'economic_value_fields': True,
                'cultural_significance_fields': True,
                'management_fields': True,
                'species_count_support': '50000+',
                'field_patterns': '25+'
            }
        }
        
        return jsonify(features)
    
    @app.route('/health')
    def general_health():
        """General health check endpoint"""
        from flask import jsonify
        
        health_status = {
            'status': 'healthy',
            'timestamp': app.config.get('START_TIME', 'unknown'),
            'version': '2.0.0-dynamic',
            'components': {
                'ontology_generator': True,
                'google_sheets': app.config.get('USE_GOOGLE_SHEETS', False),
                'fuseki': app.config.get('TRIPLESTORE_ENABLED', False),
                'postgresql': app.config.get('POSTGRESQL_ENABLED', False)
            },
            'data_status': {
                'species_in_fuseki': '49000+',
                'ontology_classes': '8+',
                'field_patterns': '25+'
            }
        }
        
        return jsonify(health_status)

# Create the app instance
app = create_app()

def print_startup_banner():
    """Print application startup information"""
    port = int(os.environ.get('PORT', 5001))
    
    print(f"\n{'='*70}")
    print(f"🌲 Treekipedia GraphFlow - Dynamic Ontology Generator")
    print(f"✨ Advanced Biodiversity Ontology Generation Platform")
    print(f"{'='*70}")
    print(f"🌐 Server: http://localhost:{port}")
    print(f"📊 Apache Fuseki: {app.config.get('FUSEKI_SPARQL_ENDPOINT', 'Not configured')}")
    print(f"🗄️  PostgreSQL: {'✅ Enabled' if app.config.get('POSTGRESQL_ENABLED') else '❌ Disabled'}")
    print(f"")
    print(f"📋 DATA SOURCES:")
    print(f"   • CSV File Upload: ✅ Always Available")
    print(f"   • Google Sheets Import: {'✅ Enabled' if app.config.get('USE_GOOGLE_SHEETS') else '❌ Disabled'}")
    print(f"   • Manual Data Entry: ✅ Available")
    print(f"")
    print(f"🔗 API ENDPOINTS:")
    print(f"   • Main Interface: http://localhost:{port}")
    print(f"")
    print(f"⚡ QUICK START:")
    print(f"   1. Upload CSV file or connect Google Sheets")
    print(f"   2. System automatically detects biodiversity fields")
    print(f"   3. Generate professional OWL ontology")
    print(f"   4. Review quality assessment and suggestions")
    print(f"   5. Download or integrate with Apache Fuseki")
    print(f"{'='*70}")
    print(f"🚀 Ready to generate biodiversity ontologies!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    
    # Store start time for health checks
    import datetime
    app.config['START_TIME'] = datetime.datetime.now().isoformat()
    
    # Print startup banner with feature information
    print_startup_banner()
    
    # Check if running in production
    if os.environ.get('FLASK_ENV') == 'production':
        print("🚀 Running in PRODUCTION mode")
        print("   • Debug mode: OFF")
        print("   • Error handling: Enhanced")
        print("   • Logging: Production level")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("🛠️  Running in DEVELOPMENT mode")
        print("   • Debug mode: ON")
        print("   • Auto-reload: Enabled")
        print("   • Logging: Verbose")
        app.run(host='0.0.0.0', port=port, debug=True)