# =============================================================================
# Updated config.py - Apache Jena Fuseki Configuration
# =============================================================================

import os
import logging
from src.core.sheets_integration import SheetsIntegration
import psycopg2
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AppConfig:
    """Application configuration and initialization with Fuseki support"""
    
    def __init__(self, app):
        self.app = app
        self.setup_config()
        self.setup_directories()
        self.setup_integrations()
    
    def setup_config(self):
        """Setup Flask configuration with Fuseki endpoints"""
        self.app.secret_key = os.environ.get('SECRET_KEY', "biodiversity_ontology_builder")
        
        # Set up storage directories
        if os.environ.get('RENDER') == 'true':
            self.app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
            self.app.config['METADATA_DIR'] = '/tmp/metadata'
        else:
            self.app.config['UPLOAD_FOLDER'] = 'Uploads'
            self.app.config['METADATA_DIR'] = 'Metadata'

        self.app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
        self.app.config['SESSION_EXPIRY'] = 3600  # 1 hour in seconds

        # Google Sheets configuration
        self.app.config['USE_GOOGLE_SHEETS'] = True
        self.app.config['GOOGLE_SHEETS_CREDS_FILE'] = 'config/service_account.json'
        self.app.config['SPREADSHEET_ID'] = os.environ.get('SPREADSHEET_ID', '')

        # Apache Jena Fuseki configuration (triple store)
        fuseki_base = os.environ.get('FUSEKI_ENDPOINT', 'http://167.172.143.162:3030')
        dataset_name = os.environ.get('FUSEKI_DATASET', 'treekipedia')

        self.app.config['TRIPLESTORE_TYPE'] = 'fuseki'
        self.app.config['TRIPLESTORE_ENABLED'] = True
        self.app.config['FUSEKI_BASE_URL'] = fuseki_base
        self.app.config['FUSEKI_DATASET'] = dataset_name

        # Fuseki authentication (load from environment variables only - no defaults for security)
        self.app.config['FUSEKI_USERNAME'] = os.environ.get('FUSEKI_USERNAME')
        self.app.config['FUSEKI_PASSWORD'] = os.environ.get('FUSEKI_PASSWORD')

        # Fuseki-specific endpoints
        self.app.config['FUSEKI_SPARQL_ENDPOINT'] = f"{fuseki_base}/{dataset_name}/sparql"
        self.app.config['FUSEKI_UPDATE_ENDPOINT'] = f"{fuseki_base}/{dataset_name}/update"
        self.app.config['FUSEKI_DATA_ENDPOINT'] = f"{fuseki_base}/{dataset_name}/data"
        self.app.config['FUSEKI_UPLOAD_ENDPOINT'] = f"{fuseki_base}/{dataset_name}/upload"

        # PostgreSQL configuration
        self.app.config['POSTGRESQL_ENABLED'] = True
        self.app.config['POSTGRESQL_CONFIG'] = {
            'db_connection': {
                'host': os.environ.get('POSTGRES_HOST', '167.172.143.162'),
                'database': os.environ.get('POSTGRES_DB', 'treekipedia'),
                'user': os.environ.get('POSTGRES_USER', 'postgres'),
                'password': os.environ.get('POSTGRES_PASSWORD', '9353jeremic'),
                'port': int(os.environ.get('POSTGRES_PORT', 5432))
            }
        }
    
    def setup_directories(self):
        """Ensure upload and metadata directories exist"""
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(self.app.config['METADATA_DIR'], exist_ok=True)
    
    def setup_integrations(self):
        """Initialize external integrations with improved error handling"""
        # Initialize Google Sheets integration
        logger.info("=== Starting Google Sheets Integration Setup ===")
        
        try:
            service_account_path = 'config/service_account.json'
            
            # Check if file exists
            if not os.path.exists(service_account_path):
                logger.warning("config/service_account.json not found. Google Sheets integration disabled.")
                self.app.sheets_integration = None
                return
            
            logger.info(f"Found service account file: {service_account_path}")
            
            # Try to create SheetsIntegration instance
            try:
                logger.info("Creating SheetsIntegration instance...")
                self.sheets_integration = SheetsIntegration(service_account_file=service_account_path)
                logger.info("SheetsIntegration instance created")
            except Exception as import_error:
                logger.error(f"Error creating SheetsIntegration instance: {str(import_error)}")
                self.app.sheets_integration = None
                return
            
            # Check if initialization was successful
            logger.info("Checking if SheetsIntegration is initialized...")
            if self.sheets_integration and hasattr(self.sheets_integration, 'is_initialized') and self.sheets_integration.is_initialized():
                logger.info("✅ Google Sheets integration initialized successfully!")
                if hasattr(self.sheets_integration, 'credentials') and hasattr(self.sheets_integration.credentials, 'service_account_email'):
                    logger.info(f"Service account email: {self.sheets_integration.credentials.service_account_email}")
                self.app.sheets_integration = self.sheets_integration
            else:
                logger.error("❌ Google Sheets integration failed to initialize")
                logger.error("SheetsIntegration.is_initialized() returned False")
                
                # Debug information
                if self.sheets_integration:
                    logger.info(f"SheetsIntegration object exists: {type(self.sheets_integration)}")
                    logger.info(f"Has is_initialized method: {hasattr(self.sheets_integration, 'is_initialized')}")
                    if hasattr(self.sheets_integration, 'initialized'):
                        logger.info(f"Initialized attribute: {self.sheets_integration.initialized}")
                
                self.app.sheets_integration = None
                
        except Exception as e:
            logger.error(f"❌ Error initializing Google Sheets integration: {str(e)}")
            logger.error("Full error details:", exc_info=True)
            self.app.sheets_integration = None
        
        logger.info("=== Google Sheets Integration Setup Complete ===")

# Global utility functions for connections
def test_postgres_connection():
    """Test PostgreSQL connection"""
    from flask import current_app
    try:
        config = current_app.config['POSTGRESQL_CONFIG']['db_connection']
        conn = psycopg2.connect(
            host=config['host'],
            database=config['database'],
            user=config['user'],
            password=config['password'],
            port=config['port'],
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {str(e)}")
        return False

def test_postgres_connection_simple():
    """Simple PostgreSQL connection test"""
    try:
        conn = psycopg2.connect(
            host='167.172.143.162',
            database='treekipedia', 
            user='postgres',
            password='9353jeremic',
            port=5432,
            connect_timeout=3
        )
        conn.close()
        return True
    except Exception:
        return False

def test_fuseki_connection():
    """Test Apache Jena Fuseki connection"""
    from flask import current_app
    try:
        fuseki_base = current_app.config.get('FUSEKI_BASE_URL', 'http://167.172.143.162:3030')
        fuseki_username = current_app.config.get('FUSEKI_USERNAME')
        fuseki_password = current_app.config.get('FUSEKI_PASSWORD')
        auth = (fuseki_username, fuseki_password) if fuseki_username and fuseki_password else None

        # Test server ping endpoint (anonymous access allowed)
        ping_response = requests.get(f"{fuseki_base}/$/ping", timeout=5)
        if ping_response.status_code != 200:
            return False

        # Test dataset endpoint (requires authentication)
        sparql_endpoint = current_app.config.get('FUSEKI_SPARQL_ENDPOINT')
        if sparql_endpoint:
            test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
            query_response = requests.post(
                sparql_endpoint,
                data={'query': test_query},
                headers={'Accept': 'application/sparql-results+json'},
                auth=auth,
                timeout=5
            )
            return query_response.status_code in [200, 404]  # 404 is OK if no data

        return True
    except Exception:
        return False

def test_fuseki_connection_simple():
    """Simple Fuseki connection test"""
    try:
        # Ping endpoint allows anonymous access
        response = requests.get("http://167.172.143.162:3030/$/ping", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

# Triplestore status functions
def check_triplestore_status():
    """Check if triplestore (Apache Fuseki) is accessible."""
    return test_fuseki_connection_simple()

def check_fuseki_status():
    """Check if Apache Fuseki is accessible."""
    return test_fuseki_connection_simple()