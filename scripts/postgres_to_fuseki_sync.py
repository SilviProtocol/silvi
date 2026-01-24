#!/usr/bin/env python3
"""
PostgreSQL to Apache Jena Fuseki Sync
Complete sync from PostgreSQL to Fuseki with proper error handling
"""

import psycopg2
import requests
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PostgreSQLFusekiSync:
    """Sync PostgreSQL data to Apache Jena Fuseki"""
    
    def __init__(self, config_file: str = "fuseki_config.json"):
        """Initialize with configuration"""
        self.config = self.load_config(config_file)
        
        # PostgreSQL configuration
        self.postgres_config = self.config['postgresql']['db_connection']
        
        # Fuseki configuration
        fuseki_config = self.config['fuseki']
        self.fuseki_base = fuseki_config['base_url']
        self.dataset_name = fuseki_config['dataset']
        self.fuseki_sparql = fuseki_config['sparql_endpoint']
        self.fuseki_update = fuseki_config['update_endpoint']
        self.fuseki_data = fuseki_config['data_endpoint']

        # Authentication credentials (prefer environment variables for security)
        self.fuseki_username = fuseki_config.get('username') or os.environ.get('FUSEKI_USERNAME')
        self.fuseki_password = fuseki_config.get('password') or os.environ.get('FUSEKI_PASSWORD')
        self.fuseki_auth = (self.fuseki_username, self.fuseki_password) if self.fuseki_username and self.fuseki_password else None
        
        # URI patterns
        self.base_uris = {
            'species': 'http://treekipedia.org/species/',
            'users': 'http://treekipedia.org/users/',
            'sponsorships': 'http://treekipedia.org/sponsorships/',
            'sponsorship_items': 'http://treekipedia.org/sponsorship_items/',
            'contreebution_nfts': 'http://treekipedia.org/nfts/',
            'ontology': 'http://treekipedia.org/ontology/',
            'property': 'http://treekipedia.org/property/'
        }
        
        logger.info(f"🔧 Fuseki Sync initialized")
        logger.info(f"   SPARQL Endpoint: {self.fuseki_sparql}")
        logger.info(f"   Update Endpoint: {self.fuseki_update}")
        logger.info(f"   Data Endpoint: {self.fuseki_data}")
    
    def load_config(self, config_file: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            # Return default config for Treekipedia
            return {
                "fuseki": {
                    "base_url": "http://167.172.143.162:3030",
                    "dataset": "treekipedia",
                    "sparql_endpoint": "http://167.172.143.162:3030/treekipedia/sparql",
                    "update_endpoint": "http://167.172.143.162:3030/treekipedia/update",
                    "data_endpoint": "http://167.172.143.162:3030/treekipedia/data"
                },
                "postgresql": {
                    "db_connection": {
                        "host": "167.172.143.162",
                        "database": "treekipedia",
                        "user": "postgres",
                        "password": "9353jeremic",
                        "port": 5432
                    }
                }
            }
    
    def test_fuseki_connection(self) -> Tuple[bool, str]:
        """Test Fuseki connection"""
        try:
            logger.info("🔍 Testing Fuseki connection...")

            # Test server ping (anonymous access allowed)
            ping_response = requests.get(f"{self.fuseki_base}/$/ping", timeout=10)
            if ping_response.status_code != 200:
                return False, f"Fuseki server not accessible (HTTP {ping_response.status_code})"

            # Test dataset query (requires authentication)
            test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
            query_response = requests.post(
                self.fuseki_sparql,
                data={'query': test_query},
                headers={'Accept': 'application/sparql-results+json'},
                auth=self.fuseki_auth,
                timeout=10
            )

            if query_response.status_code == 200:
                return True, "Fuseki connection successful"
            elif query_response.status_code == 401:
                return False, "Authentication failed - check username/password"
            else:
                return False, f"Dataset query failed (HTTP {query_response.status_code})"

        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def test_postgres_connection(self) -> Tuple[bool, str]:
        """Test PostgreSQL connection"""
        try:
            logger.info("🔍 Testing PostgreSQL connection...")
            conn = psycopg2.connect(**self.postgres_config)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True, "PostgreSQL connection successful"
        except Exception as e:
            return False, f"PostgreSQL error: {str(e)}"
    
    def get_postgres_tables(self) -> List[Dict[str, Any]]:
        """Get PostgreSQL table information"""
        try:
            conn = psycopg2.connect(**self.postgres_config)
            cursor = conn.cursor()
            
            # Get tables with row counts
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            
            tables = []
            for (table_name,) in cursor.fetchall():
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    # Get column info
                    cursor.execute("""
                        SELECT column_name, data_type
                        FROM information_schema.columns 
                        WHERE table_name = %s AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """, (table_name,))
                    
                    columns = cursor.fetchall()
                    
                    tables.append({
                        'name': table_name,
                        'row_count': row_count,
                        'columns': [col[0] for col in columns],
                        'column_types': dict(columns)
                    })
                    
                except Exception as e:
                    logger.warning(f"Error getting info for table {table_name}: {e}")
            
            cursor.close()
            conn.close()
            
            logger.info(f"✅ Found {len(tables)} PostgreSQL tables")
            return tables
            
        except Exception as e:
            logger.error(f"Error getting PostgreSQL tables: {e}")
            return []
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get basic table information without loading data"""
        try:
            conn_params = self.postgres_config.copy()
            conn_params.update({
                'connect_timeout': 30,
                'options': '-c statement_timeout=30000'  # 30 seconds for info queries
            })
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()

            # Try to get approximate row count from statistics (much faster than COUNT(*))
            cursor.execute("""
                SELECT schemaname, tablename, n_tup_ins - n_tup_del as approx_count
                FROM pg_stat_user_tables
                WHERE tablename = %s
            """, (table_name,))

            stat_result = cursor.fetchone()
            approx_rows = stat_result[2] if stat_result and stat_result[2] > 0 else None

            # Get primary key for efficient pagination
            cursor.execute("""
                SELECT column_name
                FROM information_schema.key_column_usage
                WHERE table_name = %s AND constraint_name LIKE '%_pkey'
                ORDER BY ordinal_position
            """, (table_name,))

            pk_columns = [row[0] for row in cursor.fetchall()]
            primary_key = pk_columns[0] if pk_columns else None

            # Get column names
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))

            columns = [row[0] for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            return {
                'table_name': table_name,
                'approx_rows': approx_rows,
                'primary_key': primary_key,
                'columns': columns,
                'has_primary_key': primary_key is not None
            }

        except Exception as e:
            logger.error(f"Error getting table info for {table_name}: {e}")
            return {
                'table_name': table_name,
                'approx_rows': None,
                'primary_key': None,
                'columns': [],
                'has_primary_key': False
            }

    def get_table_data_batch(self, table_name: str, offset: int = 0, limit: int = 1000, primary_key: str = None) -> Dict[str, Any]:
        """Get a batch of table data with offset pagination"""
        try:
            conn_params = self.postgres_config.copy()
            conn_params.update({
                'connect_timeout': 30,
                'options': '-c statement_timeout=120000'  # 2 minutes per batch
            })
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()

            # Get column names if not provided
            if not hasattr(self, '_table_columns') or table_name not in self._table_columns:
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position
                """, (table_name,))

                columns = [row[0] for row in cursor.fetchall()]
                if not hasattr(self, '_table_columns'):
                    self._table_columns = {}
                self._table_columns[table_name] = columns
            else:
                columns = self._table_columns[table_name]

            # Build efficient query with primary key ordering for consistency
            if primary_key:
                query = f"SELECT * FROM {table_name} ORDER BY {primary_key} OFFSET {offset} LIMIT {limit}"
            else:
                # Fallback: use OFFSET without ORDER BY (less reliable but faster)
                query = f"SELECT * FROM {table_name} OFFSET {offset} LIMIT {limit}"

            logger.info(f"📊 Batch query: {query}")
            start_time = time.time()

            cursor.execute(query)
            rows = cursor.fetchall()
            query_time = time.time() - start_time

            # Convert to dictionaries
            data = []
            for row in rows:
                record = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        record[columns[i]] = value
                data.append(record)

            cursor.close()
            conn.close()

            logger.info(f"⏱️ Batch {offset//limit + 1} completed in {query_time:.2f}s: {len(data)} records")

            return {
                'success': True,
                'data': data,
                'offset': offset,
                'limit': limit,
                'batch_number': offset // limit + 1,
                'records_in_batch': len(data),
                'has_more': len(data) == limit
            }

        except Exception as e:
            logger.error(f"Error getting batch data from {table_name} (offset {offset}): {e}")
            return {
                'success': False,
                'error': str(e),
                'data': [],
                'offset': offset,
                'limit': limit,
                'records_in_batch': 0,
                'has_more': False
            }

    def get_table_data(self, table_name: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get data from a PostgreSQL table with progress logging"""
        try:
            # Connect with timeout settings
            conn_params = self.postgres_config.copy()
            conn_params.update({
                'connect_timeout': 30,
                'options': '-c statement_timeout=120000'  # 2 minutes per statement
            })
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()

            # For very large tables, skip the COUNT(*) check as it can timeout
            # Instead, apply a default reasonable limit for unspecified limits
            if not limit:
                # Use very small limits for known large tables
                if table_name.lower() in ['species', 'observations', 'specimens']:
                    limit = 1000  # Very conservative for massive tables
                else:
                    limit = 10000  # Normal default for other tables
                logger.info(f"📊 No limit specified for {table_name}, using default limit of {limit:,} rows")

            # Get column names
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))

            columns = [row[0] for row in cursor.fetchall()]

            # For massive tables, use TABLESAMPLE for fast random sampling
            # This avoids the need for expensive ORDER BY operations
            if table_name.lower() in ['species', 'observations', 'specimens']:
                # Use TABLESAMPLE SYSTEM for ultra-fast sampling of large tables
                sample_percent = min(1.0, (limit / 100000) * 100) if limit else 0.01  # 0.01% default
                query = f"SELECT * FROM {table_name} TABLESAMPLE SYSTEM ({sample_percent}) LIMIT {limit or 10000}"
                logger.info(f"📊 Using TABLESAMPLE for large table. Sample rate: {sample_percent:.3f}%")
            else:
                # For smaller tables, use regular query without ORDER BY for speed
                query = f"SELECT * FROM {table_name}"
                if limit:
                    query += f" LIMIT {limit}"

            logger.info(f"📊 Executing query: {query}")
            start_time = time.time()
            
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                query_time = time.time() - start_time
                logger.info(f"⏱️ Query executed in {query_time:.2f} seconds, fetched {len(rows):,} rows")
            except Exception as e:
                if "TABLESAMPLE" in str(e) and table_name.lower() in ['species', 'observations', 'specimens']:
                    # Fallback: use simple LIMIT without ORDER BY for problematic tables
                    logger.warning(f"TABLESAMPLE failed, falling back to simple LIMIT: {e}")
                    fallback_query = f"SELECT * FROM {table_name} LIMIT {limit or 1000}"
                    logger.info(f"📊 Fallback query: {fallback_query}")
                    cursor.execute(fallback_query)
                    rows = cursor.fetchall()
                    query_time = time.time() - start_time
                    logger.info(f"⏱️ Fallback query executed in {query_time:.2f} seconds, fetched {len(rows):,} rows")
                else:
                    raise

            # Convert to dictionaries with progress logging
            data = []
            conversion_start = time.time()
            for i, row in enumerate(rows):
                record = {}
                for j, value in enumerate(row):
                    if j < len(columns):
                        record[columns[j]] = value
                data.append(record)

                # Log progress for large datasets
                if len(rows) > 10000 and (i + 1) % 10000 == 0:
                    logger.info(f"📈 Converted {i + 1:,}/{len(rows):,} rows to dictionaries...")

            conversion_time = time.time() - conversion_start
            logger.info(f"⏱️ Data conversion completed in {conversion_time:.2f} seconds")

            cursor.close()
            conn.close()

            total_time = time.time() - start_time
            logger.info(f"✅ Retrieved {len(data):,} records from {table_name} in {total_time:.2f} seconds")
            return data
            
        except Exception as e:
            logger.error(f"Error getting data from {table_name}: {e}")
            return []
    
    def convert_table_to_rdf(self, table_name: str, data: List[Dict[str, Any]]) -> str:
        """Convert PostgreSQL data to RDF N-Triples format"""
        logger.info(f"🔄 Converting {table_name} to RDF...")
        
        rdf_triples = []
        
        # Determine base URI and entity type
        base_uri = self.base_uris.get(table_name, f'http://treekipedia.org/{table_name}/')
        entity_type = f"<{self.base_uris['ontology']}{table_name.title()}>"
        
        for i, record in enumerate(data):
            try:
                # Create entity URI - try different ID fields
                entity_id = None
                for id_field in ['id', 'taxon_id', f'{table_name}_id']:
                    if id_field in record and record[id_field] is not None:
                        entity_id = record[id_field]
                        break
                
                if entity_id is None:
                    entity_id = f"generated_{i}"
                
                entity_uri = f"<{base_uri}{entity_id}>"
                
                # Add type declaration
                rdf_triples.append(f"{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> {entity_type} .")
                
                # Convert each column to RDF property
                for column, value in record.items():
                    if value is not None and value != '':
                        property_uri = f"<{self.base_uris['property']}{column}>"
                        
                        # Handle different data types with proper escaping
                        if isinstance(value, str):
                            # Escape special characters
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
                            # Convert other types to string
                            escaped_value = str(value).replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                            rdf_value = f'"{escaped_value}"'
                        
                        rdf_triples.append(f"{entity_uri} {property_uri} {rdf_value} .")
                        
            except Exception as e:
                logger.warning(f"Error converting record {i} from {table_name}: {e}")
                continue
        
        rdf_content = '\n'.join(rdf_triples)
        logger.info(f"✅ Generated {len(rdf_triples)} RDF triples for {table_name}")
        return rdf_content
    
    def upload_rdf_to_fuseki(self, rdf_content: str, graph_uri: str = None) -> Tuple[bool, str]:
        """Upload RDF content to Fuseki"""
        try:
            if graph_uri:
                logger.info(f"🔄 Uploading to Fuseki graph: {graph_uri}")
            else:
                logger.info("🔄 Uploading to Fuseki default graph...")
            
            # Prepare headers
            headers = {'Content-Type': 'application/n-triples; charset=utf-8'}
            
            # Prepare parameters
            params = {}
            if graph_uri:
                params['graph'] = graph_uri
            else:
                params['default'] = ''
            
            # Upload using HTTP PUT to data endpoint
            response = requests.put(
                self.fuseki_data,
                data=rdf_content.encode('utf-8'),
                headers=headers,
                params=params,
                auth=self.fuseki_auth,
                timeout=300
            )
            
            if response.status_code in [200, 201, 204]:
                return True, f"Upload successful (HTTP {response.status_code})"
            else:
                return False, f"Upload failed (HTTP {response.status_code}): {response.text[:200]}"
                
        except Exception as e:
            return False, f"Upload error: {str(e)}"
    
    def verify_fuseki_data(self, graph_uri: str = None) -> Tuple[bool, int]:
        """Verify data in Fuseki by counting triples"""
        try:
            if graph_uri:
                query = f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
            else:
                query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            
            response = requests.post(
                self.fuseki_sparql,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                auth=self.fuseki_auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                count = int(result['results']['bindings'][0]['count']['value'])
                return True, count
            else:
                return False, 0
                
        except Exception as e:
            logger.error(f"Error verifying data: {e}")
            return False, 0
    
    def sync_table_to_fuseki(self, table_name: str, batch_size: int = 1000) -> Dict[str, Any]:
        """Sync a single table to Fuseki"""
        logger.info(f"🔄 Syncing {table_name} to Fuseki...")
        
        result = {
            'table_name': table_name,
            'success': False,
            'records_processed': 0,
            'triples_generated': 0,
            'upload_success': False,
            'error': None
        }
        
        try:
            # Get table data
            data = self.get_table_data(table_name)
            
            if not data:
                result['error'] = f"No data found in table {table_name}"
                return result
            
            result['records_processed'] = len(data)
            
            # Process in batches for large tables
            batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]
            total_triples = 0
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for batch_num, batch_data in enumerate(batches):
                try:
                    # Convert batch to RDF
                    rdf_content = self.convert_table_to_rdf(table_name, batch_data)
                    
                    if not rdf_content.strip():
                        logger.warning(f"No RDF content generated for batch {batch_num + 1}")
                        continue
                    
                    # Create graph URI for this batch
                    graph_uri = f"http://treekipedia.org/{table_name}/{timestamp}_batch_{batch_num + 1}"
                    
                    # Upload to Fuseki
                    upload_success, upload_message = self.upload_rdf_to_fuseki(rdf_content, graph_uri)
                    
                    if upload_success:
                        batch_triple_count = rdf_content.count('.')
                        total_triples += batch_triple_count
                        logger.info(f"✅ Batch {batch_num + 1}/{len(batches)}: {batch_triple_count:,} triples")
                    else:
                        logger.error(f"❌ Batch {batch_num + 1} failed: {upload_message}")
                        result['error'] = f"Upload failed: {upload_message}"
                        return result
                        
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num + 1}: {e}")
                    result['error'] = f"Batch processing error: {str(e)}"
                    return result
            
            result['success'] = True
            result['upload_success'] = True
            result['triples_generated'] = total_triples
            
            logger.info(f"✅ {table_name} sync complete: {total_triples:,} triples")
            return result
            
        except Exception as e:
            logger.error(f"Error syncing {table_name}: {e}")
            result['error'] = str(e)
            return result
    
    def run_full_sync(self, tables_to_sync: List[str] = None, batch_size: int = 1000) -> Dict[str, Any]:
        """Run complete sync from PostgreSQL to Fuseki"""
        logger.info("🚀 POSTGRESQL TO FUSEKI SYNC STARTED")
        logger.info("=" * 60)
        
        sync_results = {
            'start_time': datetime.now().isoformat(),
            'success': False,
            'tables_processed': 0,
            'total_records': 0,
            'total_triples': 0,
            'table_results': [],
            'errors': []
        }
        
        try:
            # Test connections
            logger.info("Step 1: Testing connections...")
            
            postgres_ok, postgres_msg = self.test_postgres_connection()
            if not postgres_ok:
                sync_results['errors'].append(f"PostgreSQL: {postgres_msg}")
                return sync_results
            
            fuseki_ok, fuseki_msg = self.test_fuseki_connection()
            if not fuseki_ok:
                sync_results['errors'].append(f"Fuseki: {fuseki_msg}")
                return sync_results
            
            logger.info("✅ Both PostgreSQL and Fuseki connections successful")
            
            # Get tables to sync
            all_tables = self.get_postgres_tables()
            if not all_tables:
                sync_results['errors'].append("No PostgreSQL tables found")
                return sync_results
            
            # Filter tables if specified
            if tables_to_sync:
                all_tables = [t for t in all_tables if t['name'] in tables_to_sync]
            
            logger.info(f"📊 Tables to sync: {len(all_tables)}")
            for table in all_tables:
                logger.info(f"   • {table['name']}: {table['row_count']:,} rows")
            
            # Sync each table
            successful_syncs = 0
            
            for table in all_tables:
                table_name = table['name']
                
                logger.info(f"\n🔄 Processing {table_name}...")
                
                table_result = self.sync_table_to_fuseki(table_name, batch_size)
                sync_results['table_results'].append(table_result)
                
                if table_result['success']:
                    successful_syncs += 1
                    sync_results['total_records'] += table_result['records_processed']
                    sync_results['total_triples'] += table_result['triples_generated']
                    logger.info(f"✅ {table_name} completed successfully")
                else:
                    sync_results['errors'].append(f"{table_name}: {table_result['error']}")
                    logger.error(f"❌ {table_name} failed: {table_result['error']}")
            
            # Final summary
            sync_results['tables_processed'] = len(all_tables)
            sync_results['success'] = successful_syncs == len(all_tables)
            sync_results['end_time'] = datetime.now().isoformat()
            
            logger.info(f"\n📊 SYNC SUMMARY")
            logger.info(f"   Tables: {successful_syncs}/{len(all_tables)} successful")
            logger.info(f"   Records: {sync_results['total_records']:,}")
            logger.info(f"   Triples: {sync_results['total_triples']:,}")
            
            if sync_results['success']:
                print(f"\n🎉 FULL SYNC COMPLETED SUCCESSFULLY!")
                print(f"✅ All {len(all_tables)} tables synced to Fuseki")
                print(f"📊 Total: {sync_results['total_records']:,} records → {sync_results['total_triples']:,} triples")
                print(f"🔗 Query your data at: {self.fuseki_sparql}")
            else:
                print(f"\n⚠️ PARTIAL SYNC: {successful_syncs}/{len(all_tables)} tables completed")
                print(f"❌ Errors: {len(sync_results['errors'])}")
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Fatal sync error: {e}")
            sync_results['errors'].append(f"Fatal error: {str(e)}")
            sync_results['end_time'] = datetime.now().isoformat()
            return sync_results


def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync PostgreSQL to Apache Jena Fuseki')
    parser.add_argument('--config', default='fuseki_config.json', help='Configuration file')
    parser.add_argument('--tables', nargs='+', help='Specific tables to sync')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size')
    parser.add_argument('--test', action='store_true', help='Test connections only')
    
    args = parser.parse_args()
    
    try:
        syncer = PostgreSQLFusekiSync(args.config)
        
        if args.test:
            # Test mode
            print("\n🔍 TESTING CONNECTIONS")
            print("=" * 25)
            
            postgres_ok, postgres_msg = syncer.test_postgres_connection()
            print(f"PostgreSQL: {'✅' if postgres_ok else '❌'} {postgres_msg}")
            
            fuseki_ok, fuseki_msg = syncer.test_fuseki_connection()
            print(f"Fuseki: {'✅' if fuseki_ok else '❌'} {fuseki_msg}")
            
            if postgres_ok and fuseki_ok:
                tables = syncer.get_postgres_tables()
                print(f"\nFound {len(tables)} tables:")
                total_records = 0
                for table in tables:
                    print(f"  • {table['name']}: {table['row_count']:,} rows")
                    total_records += table['row_count']
                print(f"\nTotal records: {total_records:,}")
                print("\nReady for sync! Run without --test to start.")
            else:
                print("\n❌ Fix connection issues before syncing.")
        else:
            # Run sync
            result = syncer.run_full_sync(args.tables, args.batch_size)
            exit(0 if result['success'] else 1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)


if __name__ == '__main__':
    main()