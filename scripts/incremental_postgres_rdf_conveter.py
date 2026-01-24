#!/usr/bin/env python3
"""
Incremental PostgreSQL RDF Converter - Detects and avoids duplicates
Only pushes new data that doesn't already exist in Blazegraph
"""

import psycopg2
import requests
import logging
import time
from typing import Dict, List, Any, Tuple, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)

class IncrementalPostgreSQLRDFConverter:
    """RDF converter with duplicate detection and incremental updates"""
    
    def __init__(self, postgres_config: Dict[str, Any]):
        self.postgres_config = postgres_config
        
        # Use same URIs as working bulk sync
        self.base_uris = {
            'species': 'http://treekipedia.org/species/',
            'ontology': 'http://treekipedia.org/ontology/',
            'property': 'http://treekipedia.org/property/'
        }
        
        # Blazegraph endpoints
        self.fuseki_sparql = 'http://167.172.143.162:3030/treekipedia/sparql'
        self.fuseki_data = 'http://167.172.143.162:3030/treekipedia/data'
        
        self.connection = None
        self.table_schemas = {}
    
    def connect_to_database(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(**self.postgres_config)
            logger.info("✅ Connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            return False
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def get_existing_entities_in_blazegraph(self, table_name: str) -> Set[str]:
        """Get set of entity IDs that already exist in Blazegraph for this table"""
        try:
            logger.info(f"📊 Checking existing {table_name} entities in Blazegraph...")
            
            # Determine entity type based on table name
            if table_name == 'species':
                entity_type = f"{self.base_uris['ontology']}Species"
                base_uri = self.base_uris['species']
            else:
                entity_type = f"{self.base_uris['ontology']}{table_name.title()}"
                base_uri = f"{self.base_uris['ontology']}{table_name}/"
            
            # Query for existing entities of this type
            query = f"""
            SELECT DISTINCT ?entity WHERE {{
                ?entity a <{entity_type}> .
            }}
            """
            
            response = requests.post(
               self.fuseki_sparql ,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=60
            )
            
            existing_entities = set()
            
            if response.status_code == 200:
                result = response.json()
                for binding in result['results']['bindings']:
                    entity_uri = binding['entity']['value']
                    # Extract ID from URI
                    if entity_uri.startswith(base_uri):
                        entity_id = entity_uri[len(base_uri):]
                        existing_entities.add(str(entity_id))
            
            logger.info(f"✅ Found {len(existing_entities)} existing {table_name} entities in Blazegraph")
            return existing_entities
            
        except Exception as e:
            logger.error(f"❌ Error checking existing entities: {e}")
            return set()
    
    def detect_table_schema(self, table_name: str) -> bool:
        """Detect table schema and primary key"""
        try:
            cursor = self.connection.cursor()
            
            # Get column information
            cursor.execute("""
                SELECT column_name, data_type, ordinal_position
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns_info = cursor.fetchall()
            columns = [col[0] for col in columns_info]
            
            # Try to find primary key
            cursor.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary;
            """, (table_name,))
            
            actual_pk = cursor.fetchall()
            primary_key = actual_pk[0][0] if actual_pk else None
            
            # Store schema info
            self.table_schemas[table_name] = {
                'columns': columns,
                'primary_key': primary_key
            }
            
            cursor.close()
            logger.info(f"✅ Detected schema for {table_name}: {len(columns)} columns, PK: {primary_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error detecting schema for {table_name}: {e}")
            return False
    
    def get_table_data_incremental(self, table_name: str, existing_entities: Set[str], limit: int = 50000) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Get table data and separate new vs existing records"""
        try:
            if table_name not in self.table_schemas:
                if not self.detect_table_schema(table_name):
                    return [], []
            
            cursor = self.connection.cursor()
            schema = self.table_schemas[table_name]
            columns = schema['columns']
            primary_key = schema['primary_key']
            
            # Build query with proper ordering if we have primary key
            if primary_key:
                query = f"SELECT * FROM {table_name} ORDER BY {primary_key} LIMIT {limit}"
            else:
                query = f"SELECT * FROM {table_name} LIMIT {limit}"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convert to dictionaries and separate new vs existing
            all_records = []
            new_records = []
            existing_records = []
            
            for i, row in enumerate(rows):
                record = {}
                for j, value in enumerate(row):
                    if j < len(columns):
                        record[columns[j]] = value
                all_records.append(record)
                
                # Determine entity ID for this record
                entity_id = None
                for id_field in [primary_key, 'taxon_id', 'id', f'{table_name}_id']:
                    if id_field and id_field in record and record[id_field] is not None:
                        entity_id = str(record[id_field])
                        break
                
                # Fallback to generating an ID
                if entity_id is None:
                    entity_id = f"{table_name}_{i}_{hash(str(record)) % 1000000}"
                
                # Check if this entity already exists
                if entity_id in existing_entities:
                    existing_records.append(record)
                else:
                    new_records.append(record)
            
            cursor.close()
            
            logger.info(f"📊 {table_name} data analysis:")
            logger.info(f"   Total records: {len(all_records)}")
            logger.info(f"   New records: {len(new_records)}")
            logger.info(f"   Existing records: {len(existing_records)}")
            
            return new_records, existing_records
            
        except Exception as e:
            logger.error(f"❌ Error getting incremental data from {table_name}: {e}")
            return [], []
    
    def convert_table_to_rdf(self, table_name: str, table_data: List[Dict[str, Any]]) -> str:
        """Convert table data to RDF using same format as working bulk sync"""
        if not table_data:
            return ""
            
        rdf_triples = []
        
        # Use same URI patterns as bulk sync
        if table_name == 'species':
            base_uri = self.base_uris['species']
            entity_type = f"{self.base_uris['ontology']}Species"
        else:
            base_uri = f"{self.base_uris['ontology']}{table_name}/"
            entity_type = f"{self.base_uris['ontology']}{table_name.title()}"
        
        for i, record in enumerate(table_data):
            try:
                # Create entity URI - same logic as bulk sync
                entity_id = None
                
                # Try different ID fields
                schema = self.table_schemas.get(table_name, {})
                primary_key = schema.get('primary_key')
                
                for id_field in [primary_key, 'taxon_id', 'id', f'{table_name}_id']:
                    if id_field and id_field in record and record[id_field] is not None:
                        entity_id = record[id_field]
                        break
                
                # Fallback to generating an ID
                if entity_id is None:
                    entity_id = f"{table_name}_{i}_{hash(str(record)) % 1000000}"
                
                entity_uri = f"<{base_uri}{entity_id}>"
                
                # Add type declaration
                rdf_triples.append(f"{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{entity_type}> .")
                
                # Convert each column to RDF property
                for column, value in record.items():
                    if value is not None and value != '':
                        property_uri = f"<{self.base_uris['property']}{column}>"
                        
                        # Handle different data types with proper escaping
                        if isinstance(value, str):
                            escaped_value = (value
                                .replace('\\', '\\\\')
                                .replace('"', '\\"')
                                .replace('\n', '\\n')
                                .replace('\r', '\\r')
                                .replace('\t', '\\t'))
                            rdf_value = f'"{escaped_value}"'
                        elif isinstance(value, int):
                            rdf_value = f'"{value}"^^<http://www.w3.org/2001/XMLSchema#integer>'
                        elif isinstance(value, float):
                            rdf_value = f'"{value}"^^<http://www.w3.org/2001/XMLSchema#decimal>'
                        elif isinstance(value, bool):
                            rdf_value = f'"{str(value).lower()}"^^<http://www.w3.org/2001/XMLSchema#boolean>'
                        else:
                            escaped_value = str(value).replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                            rdf_value = f'"{escaped_value}"'
                        
                        rdf_triples.append(f"{entity_uri} {property_uri} {rdf_value} .")
                        
            except Exception as e:
                logger.warning(f"Error converting record {i} from {table_name}: {e}")
                continue
        
        rdf_content = '\n'.join(rdf_triples)
        logger.info(f"✅ Generated {len(rdf_triples)} RDF triples for {len(table_data)} new {table_name} records")
        return rdf_content
    
    def upload_rdf_to_blazegraph(self, rdf_content: str) -> Tuple[bool, str]:
        """Upload RDF to Blazegraph using same method as working bulk sync"""
        try:
            response = requests.post(
                self.fuseki_data,
                data=rdf_content.encode('utf-8'),
                headers={'Content-Type': 'application/n-triples; charset=utf-8'},
                timeout=300
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ RDF uploaded successfully: HTTP {response.status_code}")
                return True, f"Success (HTTP {response.status_code})"
            else:
                logger.error(f"❌ Upload failed: HTTP {response.status_code}")
                return False, f"HTTP {response.status_code}: {response.text[:200]}"
                
        except Exception as e:
            logger.error(f"❌ Upload error: {e}")
            return False, f"Error: {str(e)}"
    
    def generate_and_upload_rdf_incremental(self, table_name: str, limit: int = 1000, push_to_blazegraph: bool = True) -> Dict[str, Any]:
        """Generate RDF from table with duplicate detection and incremental upload"""
        try:
            logger.info(f"🔄 Incremental processing table: {table_name}")
            
            # Step 1: Check what already exists in Blazegraph
            existing_entities = set()
            if push_to_blazegraph:
                existing_entities = self.get_existing_entities_in_blazegraph(table_name)
            
            # Step 2: Get table data and separate new vs existing
            new_records, existing_records = self.get_table_data_incremental(table_name, existing_entities, limit)
            
            if not new_records and not existing_records:
                return {
                    'success': False,
                    'error': f'No data found in table {table_name}',
                    'records_total': 0,
                    'records_new': 0,
                    'records_existing': 0,
                    'rdf_triples': 0
                }
            
            result = {
                'success': True,
                'table_name': table_name,
                'records_total': len(new_records) + len(existing_records),
                'records_new': len(new_records),
                'records_existing': len(existing_records),
                'rdf_triples': 0,
                'blazegraph': {'success': False, 'message': 'Not attempted'}
            }
            
            # Step 3: Only process new records if any exist
            if new_records:
                # Convert new records to RDF
                rdf_content = self.convert_table_to_rdf(table_name, new_records)
                
                if rdf_content.strip():
                    rdf_triple_count = rdf_content.count('.')
                    result['rdf_triples'] = rdf_triple_count
                    
                    # Upload to Blazegraph if requested
                    if push_to_blazegraph:
                        upload_success, upload_message = self.upload_rdf_to_blazegraph(rdf_content)
                        result['blazegraph'] = {
                            'success': upload_success,
                            'message': upload_message
                        }
                        
                        if upload_success:
                            logger.info(f"✅ Incremental update: Added {len(new_records)} new {table_name} records ({rdf_triple_count} triples)")
                        else:
                            logger.error(f"❌ Failed to upload {len(new_records)} new {table_name} records")
                    else:
                        result['blazegraph']['message'] = 'Push to Blazegraph disabled'
                        
                else:
                    logger.warning(f"⚠️ No RDF content generated for {len(new_records)} new records")
            else:
                logger.info(f"✅ No new {table_name} records to process - all {len(existing_records)} records already exist in Blazegraph")
                result['blazegraph'] = {
                    'success': True,
                    'message': f'All {len(existing_records)} records already exist - no upload needed'
                }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in incremental processing {table_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'records_total': 0,
                'records_new': 0,
                'records_existing': 0,
                'rdf_triples': 0
            }

# Convenience function for routes_api.py
def generate_rdf_from_table_incremental(table_name: str, postgres_config: Dict[str, Any], push_to_blazegraph: bool = True, limit: int = 1000) -> Dict[str, Any]:
    """Generate RDF from PostgreSQL table with duplicate detection"""
    converter = IncrementalPostgreSQLRDFConverter(postgres_config)
    
    try:
        if not converter.connect_to_database():
            return {
                'success': False,
                'error': 'Could not connect to PostgreSQL'
            }
        
        result = converter.generate_and_upload_rdf_incremental(table_name, limit, push_to_blazegraph)
        return result
        
    finally:
        converter.close_connection()