# =============================================================================
# Apache Jena Fuseki Integration utils.py
# =============================================================================

import requests
import os
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def increment_version(current_version: str) -> str:
    """
    Increment a semantic version number.
    
    Args:
        current_version: Current version string (e.g., "1.2.3")
        
    Returns:
        Incremented version string (e.g., "1.2.4")
    """
    try:
        # Handle common version formats
        if not current_version:
            return "1.0.1"
        
        # Remove 'v' prefix if present
        version = current_version.lower().replace('v', '').strip()
        
        # Split version into parts
        parts = version.split('.')
        
        # Ensure we have at least 3 parts (major.minor.patch)
        while len(parts) < 3:
            parts.append('0')
        
        # Convert to integers and increment patch version
        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            
            # Increment patch version
            patch += 1
            
            return f"{major}.{minor}.{patch}"
            
        except ValueError:
            # If conversion fails, create a new version
            return "1.0.1"
            
    except Exception as e:
        logger.error(f"Error incrementing version '{current_version}': {str(e)}")
        return "1.0.1"

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be safe for filesystem use.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        return "untitled"
    
    # Remove or replace problematic characters
    # Characters not allowed in filenames on various systems
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    
    # Replace illegal characters with underscores
    clean_name = re.sub(illegal_chars, '_', filename)
    
    # Replace multiple spaces/underscores with single underscore
    clean_name = re.sub(r'[\s_]+', '_', clean_name)
    
    # Remove leading/trailing spaces and underscores
    clean_name = clean_name.strip(' _')
    
    # Ensure it's not empty
    if not clean_name:
        clean_name = "untitled"
    
    # Limit length (filesystem limits)
    if len(clean_name) > 200:
        clean_name = clean_name[:200]
    
    # Remove trailing periods (Windows issue)
    clean_name = clean_name.rstrip('.')
    
    return clean_name

def allowed_file(filename: str) -> bool:
    """
    Check if uploaded file has an allowed extension.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    # Define allowed extensions
    ALLOWED_EXTENSIONS = {'.csv', '.txt'}
    
    # Get file extension
    _, ext = os.path.splitext(filename.lower())
    
    return ext in ALLOWED_EXTENSIONS

# Backward compatibility functions
def test_blazegraph_connection():
    """Backward compatibility wrapper for Fuseki connection test."""
    return test_fuseki_connection()

def check_blazegraph_status():
    """Check if triplestore (Fuseki) is accessible - backward compatibility."""
    success, _ = test_fuseki_connection()
    return success

def import_to_blazegraph_enhanced(ontology_file_path, ontology_name, version):
    """Enhanced import wrapper for backward compatibility."""
    return import_to_fuseki(ontology_file_path, ontology_name, version)

# Enhanced Fuseki operations
class FusekiManager:
    """Manager class for advanced Fuseki operations"""

    def __init__(self, fuseki_base_url: str, dataset_name: str, username: str = None, password: str = None):
        self.fuseki_base = fuseki_base_url.rstrip('/')
        self.dataset = dataset_name
        self.sparql_endpoint = f"{self.fuseki_base}/{dataset_name}/sparql"
        self.update_endpoint = f"{self.fuseki_base}/{dataset_name}/update"
        self.data_endpoint = f"{self.fuseki_base}/{dataset_name}/data"
        self.auth = (username, password) if username and password else None
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Fuseki"""
        try:
            response = requests.get(f"{self.fuseki_base}/$/ping", timeout=10)
            if response.status_code == 200:
                return True, "Connection successful"
            else:
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    def count_triples(self, graph_uri: str = None) -> int:
        """Count triples in dataset or specific graph"""
        try:
            if graph_uri:
                query = f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
            else:
                query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            
            response = requests.post(
                self.sparql_endpoint,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return int(result['results']['bindings'][0]['count']['value'])
            
            return 0
        except Exception:
            return 0
    
    def list_graphs(self) -> list:
        """List all named graphs in the dataset"""
        try:
            query = "SELECT DISTINCT ?graph WHERE { GRAPH ?graph { ?s ?p ?o } }"
            
            response = requests.post(
                self.sparql_endpoint,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return [binding['graph']['value'] for binding in result['results']['bindings']]
            
            return []
        except Exception:
            return []
    
    def clear_graph(self, graph_uri: str) -> bool:
        """Clear a specific graph"""
        try:
            clear_query = f"DROP SILENT GRAPH <{graph_uri}>"
            response = requests.post(
                self.update_endpoint,
                data=clear_query,
                headers={'Content-Type': 'application/sparql-update'},
                auth=self.auth,
                timeout=30
            )
            return response.status_code in [200, 204]
        except Exception:
            return False
    
    def upload_rdf_data(self, rdf_content: str, graph_uri: str, content_type: str = 'application/rdf+xml') -> Tuple[bool, str]:
        """Upload RDF data to a specific graph"""
        try:
            headers = {'Content-Type': content_type}
            params = {'graph': graph_uri}
            
            response = requests.put(
                self.data_endpoint,
                data=rdf_content.encode('utf-8') if isinstance(rdf_content, str) else rdf_content,
                headers=headers,
                params=params,
                auth=self.auth,
                timeout=120
            )
            
            if response.status_code in [200, 201, 204]:
                return True, f"Upload successful (HTTP {response.status_code})"
            else:
                return False, f"Upload failed (HTTP {response.status_code}): {response.text[:200]}"
                
        except Exception as e:
            return False, f"Upload error: {str(e)}"

# Convenience function to get Fuseki manager
def get_fuseki_manager():
    """Get configured Fuseki manager instance"""
    from flask import current_app
    
    fuseki_base = current_app.config.get('FUSEKI_BASE_URL')
    dataset = current_app.config.get('FUSEKI_DATASET', 'treekipedia')
    
    if not fuseki_base:
        raise ValueError("Fuseki base URL not configured")
    
    return FusekiManager(fuseki_base, dataset)

def save_metadata(session_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Save metadata for a session.
    
    Args:
        session_id: Unique session identifier
        metadata: Dictionary containing session metadata
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        from flask import current_app
        
        # Ensure metadata directory exists
        metadata_dir = current_app.config.get('METADATA_DIR', 'metadata')
        os.makedirs(metadata_dir, exist_ok=True)
        
        # Save metadata to JSON file
        metadata_file = os.path.join(metadata_dir, f"{session_id}.json")
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved metadata for session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving metadata for session {session_id}: {str(e)}")
        return False

def load_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load metadata for a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Dictionary containing session metadata, or None if not found
    """
    try:
        from flask import current_app
        
        metadata_dir = current_app.config.get('METADATA_DIR', 'metadata')
        metadata_file = os.path.join(metadata_dir, f"{session_id}.json")
        
        if not os.path.exists(metadata_file):
            return None
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error loading metadata for session {session_id}: {str(e)}")
        return None

def check_spreadsheet_changes(spreadsheet) -> Tuple[bool, str]:
    """
    Check if there have been changes to a Google Spreadsheet since last processing.
    
    Args:
        spreadsheet: Google Sheets spreadsheet object
        
    Returns:
        Tuple of (has_changes: bool, change_info: str)
    """
    try:
        # This is a simplified implementation
        # In practice, you might want to compare timestamps, checksums, etc.
        
        # For now, always return True to allow processing
        # You can enhance this based on your specific needs
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        change_info = f"Checked at {current_time}"
        
        return True, change_info
        
    except Exception as e:
        logger.error(f"Error checking spreadsheet changes: {str(e)}")
        return True, f"Error checking changes: {str(e)}"

def import_to_blazegraph(ontology_file_path: str, ontology_name: str, version: str) -> Tuple[bool, str, str]:
    """
    Import an ontology file to Blazegraph triplestore.
    
    Args:
        ontology_file_path: Path to the ontology file
        ontology_name: Name of the ontology
        version: Version string
        
    Returns:
        Tuple of (success: bool, message: str, graph_uri: str)
    """
    try:
        from flask import current_app
        import requests
        
        if not current_app.config.get('BLAZEGRAPH_ENABLED'):
            return False, "Blazegraph not enabled", ""
        
        blazegraph_endpoint = current_app.config.get('BLAZEGRAPH_ENDPOINT')
        if not blazegraph_endpoint:
            return False, "Blazegraph endpoint not configured", ""
        
        # Check if file exists
        if not os.path.exists(ontology_file_path):
            return False, f"Ontology file not found: {ontology_file_path}", ""
        
        # Create graph URI
        graph_uri = f"http://example.org/ontology/{ontology_name}/version{version}"
        
        # Test Blazegraph connection
        try:
            response = requests.get(blazegraph_endpoint, timeout=10)
            if response.status_code != 200:
                return False, f"Blazegraph not accessible (HTTP {response.status_code})", ""
        except Exception as e:
            return False, f"Cannot connect to Blazegraph: {str(e)}", ""
        
        # Clear existing graph
        try:
            clear_url = f"{blazegraph_endpoint}/sparql"
            clear_query = f"DROP SILENT GRAPH <{graph_uri}>"
            
            clear_response = requests.post(
                clear_url,
                data={'update': clear_query},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if clear_response.status_code in [200, 204]:
                logger.info(f"Cleared existing graph: {graph_uri}")
            
        except Exception as e:
            logger.warning(f"Could not clear existing graph: {str(e)}")
        
        # Import the ontology
        try:
            with open(ontology_file_path, 'rb') as f:
                ontology_content = f.read()
            
            if not ontology_content:
                return False, "Ontology file is empty", ""
            
            # Try REST API import
            import_url = f"{blazegraph_endpoint}/namespace/kb/sparql"
            
            headers = {
                'Content-Type': 'application/rdf+xml'
            }
            
            params = {
                'context-uri': graph_uri
            }
            
            import_response = requests.post(
                import_url,
                data=ontology_content,
                headers=headers,
                params=params,
                timeout=120
            )
            
            if import_response.status_code in [200, 201, 204]:
                return True, f"Successfully imported to Blazegraph (HTTP {import_response.status_code})", graph_uri
            else:
                return False, f"Import failed (HTTP {import_response.status_code}): {import_response.text[:200]}", ""
                
        except Exception as e:
            return False, f"Error during import: {str(e)}", ""
            
    except Exception as e:
        logger.error(f"Unexpected error in Blazegraph import: {str(e)}")
        return False, f"Unexpected error: {str(e)}", ""

def log_to_google_sheets(metadata: Dict[str, Any]) -> bool:
    """
    Log ontology generation metadata to Google Sheets.
    
    Args:
        metadata: Dictionary containing metadata to log
        
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        from flask import current_app
        
        # Check if Google Sheets logging is enabled
        if not current_app.config.get('USE_GOOGLE_SHEETS'):
            return False
        
        # Get sheets integration
        sheets_integration = getattr(current_app, 'sheets_integration', None)
        if not sheets_integration or not sheets_integration.is_initialized():
            return False
        
        # This is a placeholder implementation
        # You would implement the actual Google Sheets logging here
        logger.info(f"Would log to Google Sheets: {metadata.get('session_id')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error logging to Google Sheets: {str(e)}")
        return False

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def validate_session_id(session_id: str) -> bool:
    """
    Validate that a session ID is safe and well-formed.
    
    Args:
        session_id: Session ID string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not session_id:
        return False
    
    # Check for directory traversal attempts
    if '..' in session_id or '/' in session_id or '\\' in session_id:
        return False
    
    # Check length
    if len(session_id) > 100:
        return False
    
    # Check for valid UUID-like format (optional)
    uuid_pattern = r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'
    if re.match(uuid_pattern, session_id):
        return True
    
    # Allow alphanumeric with hyphens and underscores
    if re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        return True
    
    return False

def get_file_extension(filename: str) -> str:
    """
    Get the file extension from a filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        File extension (including the dot)
    """
    if not filename:
        return ""
    
    _, ext = os.path.splitext(filename.lower())
    return ext

def ensure_directory_exists(directory_path: str) -> bool:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        True if directory exists or was created successfully
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {str(e)}")
        return False

# =============================================================================
# Configuration Helper Functions
# =============================================================================

def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get a configuration value from Flask app config.
    
    Args:
        key: Configuration key
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    try:
        from flask import current_app
        return current_app.config.get(key, default)
    except Exception:
        return default

def is_development_mode() -> bool:
    """
    Check if the application is running in development mode.
    
    Returns:
        True if in development mode, False otherwise
    """
    try:
        import os
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        return flask_env in ['development', 'dev']
    except Exception:
        return False

# Fuseki-specific import function (replaces Blazegraph version)
def import_to_fuseki(ontology_file_path: str, ontology_name: str, version: str) -> Tuple[bool, str, str]:
    """Import an ontology file to Apache Jena Fuseki triplestore."""
    try:
        from flask import current_app
        
        if not current_app.config.get('TRIPLESTORE_ENABLED'):
            return False, "Triplestore not enabled", ""
        
        # Get Fuseki endpoints
        fuseki_base = current_app.config.get('FUSEKI_BASE_URL')
        dataset = current_app.config.get('FUSEKI_DATASET', 'treekipedia')
        data_endpoint = current_app.config.get('FUSEKI_DATA_ENDPOINT')
        update_endpoint = current_app.config.get('FUSEKI_UPDATE_ENDPOINT')

        # Get authentication credentials
        fuseki_username = current_app.config.get('FUSEKI_USERNAME')
        fuseki_password = current_app.config.get('FUSEKI_PASSWORD')
        auth = (fuseki_username, fuseki_password) if fuseki_username and fuseki_password else None

        if not fuseki_base or not data_endpoint:
            return False, "Fuseki endpoints not configured", ""
        
        # Check if file exists
        if not os.path.exists(ontology_file_path):
            return False, f"Ontology file not found: {ontology_file_path}", ""
        
        # Create graph URI
        graph_uri = f"http://treekipedia.org/ontology/{ontology_name}/version{version}"
        
        # Test Fuseki connection
        try:
            ping_response = requests.get(f"{fuseki_base}/$/ping", timeout=10)
            if ping_response.status_code != 200:
                return False, f"Fuseki not accessible (HTTP {ping_response.status_code})", ""
        except Exception as e:
            return False, f"Cannot connect to Fuseki: {str(e)}", ""
        
        # Clear existing graph (optional)
        try:
            clear_query = f"DROP SILENT GRAPH <{graph_uri}>"
            clear_response = requests.post(
                update_endpoint,
                data=clear_query,
                headers={'Content-Type': 'application/sparql-update'},
                auth=auth,
                timeout=30
            )
            
            if clear_response.status_code in [200, 204]:
                logger.info(f"Cleared existing graph: {graph_uri}")
        except Exception as e:
            logger.warning(f"Could not clear existing graph: {str(e)}")
        
        # Import the ontology using HTTP PUT to data endpoint (Fuseki style)
        try:
            with open(ontology_file_path, 'rb') as f:
                ontology_content = f.read()
            
            if not ontology_content:
                return False, "Ontology file is empty", ""
            
            # Use HTTP PUT to data endpoint with graph parameter
            headers = {'Content-Type': 'application/rdf+xml'}
            params = {'graph': graph_uri}
            
            import_response = requests.put(
                data_endpoint,
                data=ontology_content,
                headers=headers,
                params=params,
                auth=auth,
                timeout=120
            )
            
            if import_response.status_code in [200, 201, 204]:
                return True, f"Successfully imported to Fuseki (HTTP {import_response.status_code})", graph_uri
            else:
                return False, f"Import failed (HTTP {import_response.status_code}): {import_response.text[:200]}", ""
                
        except Exception as e:
            return False, f"Error during import: {str(e)}", ""
            
    except Exception as e:
        logger.error(f"Unexpected error in Fuseki import: {str(e)}")
        return False, f"Unexpected error: {str(e)}", ""

def test_fuseki_connection():
    """Test Fuseki connection and return detailed status."""
    from flask import current_app
    
    if not current_app.config.get('TRIPLESTORE_ENABLED'):
        return False, "Triplestore not enabled in configuration"
    
    fuseki_base = current_app.config.get('FUSEKI_BASE_URL')
    fuseki_sparql = current_app.config.get('FUSEKI_SPARQL_ENDPOINT')

    # Get authentication credentials
    fuseki_username = current_app.config.get('FUSEKI_USERNAME')
    fuseki_password = current_app.config.get('FUSEKI_PASSWORD')
    auth = (fuseki_username, fuseki_password) if fuseki_username and fuseki_password else None

    if not fuseki_base:
        return False, "Fuseki base URL not configured"

    try:
        # Test ping endpoint (anonymous access allowed)
        ping_response = requests.get(f"{fuseki_base}/$/ping", timeout=10)

        if ping_response.status_code == 200:
            # Test SPARQL query (requires authentication)
            if fuseki_sparql:
                test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
                query_response = requests.post(
                    fuseki_sparql,
                    data={'query': test_query},
                    headers={'Accept': 'application/sparql-results+json'},
                    auth=auth,
                    timeout=10
                )
                
                if query_response.status_code in [200, 404]:  # 404 OK if no data
                    return True, f"Fuseki accessible at {fuseki_base}"
                else:
                    return False, f"SPARQL query failed: HTTP {query_response.status_code}"
            else:
                return True, f"Fuseki ping successful at {fuseki_base}"
        else:
            return False, f"Fuseki ping failed: HTTP {ping_response.status_code}"
            
    except requests.exceptions.ConnectTimeout:
        return False, f"Connection timeout to {fuseki_base}"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {fuseki_base} - check if Fuseki is running"
    except Exception as e:
        return False, f"Error connecting to Fuseki: {str(e)}"


# Backward compatibility wrapper
def import_to_blazegraph(ontology_file_path: str, ontology_name: str, version: str) -> Tuple[bool, str, str]:
    """Import to Apache Fuseki (kept for backward compatibility)."""
    return import_to_fuseki(ontology_file_path, ontology_name, version)

# =============================================================================
# Quick Apache Fuseki Diagnostics Script
# =============================================================================

def diagnose_blazegraph_issue():
    """
    Diagnostic function to identify Apache Fuseki issues.
    """
    print("🔍 BLAZEGRAPH DIAGNOSTIC REPORT")
    print("=" * 50)
    
    from flask import current_app
    
    # Check configuration
    blazegraph_enabled = current_app.config.get('BLAZEGRAPH_ENABLED', False)
    blazegraph_endpoint = current_app.config.get('BLAZEGRAPH_ENDPOINT', 'Not configured')
    
    print(f"Configuration:")
    print(f"  • Enabled: {blazegraph_enabled}")
    print(f"  • Endpoint: {blazegraph_endpoint}")
    
    if not blazegraph_enabled:
        print("\n❌ Apache Fuseki is disabled in configuration")
        return
    
    # Test connection
    print(f"\nTesting connection to {blazegraph_endpoint}...")
    success, message = test_blazegraph_connection()
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        print("\n🔧 Possible solutions:")
        print("  1. Check if Apache Fuseki is running")
        print("  2. Verify the endpoint URL in config")
        print("  3. Check network connectivity")
        print("  4. Try accessing the endpoint in a browser")
    
    return success

if __name__ == "__main__":
    # Run diagnostics
    diagnose_blazegraph_issue()