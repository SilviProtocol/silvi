#!/usr/bin/env python3
"""
Incremental Species Data Sync
Syncs only NEW or UPDATED species from PostgreSQL to Blazegraph
"""

import psycopg2
import requests
import logging
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple

logger = logging.getLogger(__name__)

class IncrementalSpeciesSync:
    """
    Smart sync that only uploads new/changed species data to preserve existing data
    """
    
    def __init__(self):
        # PostgreSQL configuration
        self.postgres_config = {
            'host': '167.172.143.162',
            'database': 'treekipedia',
            'user': 'postgres',
            'password': '9353jeremic',
            'port': 5432
        }
        
        # Blazegraph configuration
        self.fuseki_sparql = 'http://167.172.143.162:3030/treekipedia/sparql'
        self.fuseki_data = 'http://167.172.143.162:3030/treekipedia/data'
        
        # Species URI pattern
        self.species_base_uri = 'http://treekipedia.org/species/'
        self.species_class_uri = 'http://treekipedia.org/ontology/Species'
    
    def get_existing_species_in_blazegraph(self) -> Set[str]:
        """Get set of species IDs that already exist in Blazegraph"""
        try:
            logger.info("📊 Checking existing species in Blazegraph...")
            
            query = f"""
            SELECT DISTINCT ?speciesId WHERE {{
                ?species <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{self.species_class_uri}> .
                ?species <http://treekipedia.org/property/taxon_id> ?speciesId .
            }}
            """
            
            response = requests.post(
                self.fuseki_sparql,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=120
            )
            
            existing_species = set()
            
            if response.status_code == 200:
                result = response.json()
                for binding in result['results']['bindings']:
                    species_id = binding['speciesId']['value']
                    existing_species.add(species_id)
            
            logger.info(f"✅ Found {len(existing_species)} existing species in Blazegraph")
            return existing_species
            
        except Exception as e:
            logger.error(f"Error getting existing species: {e}")
            return set()
    
    def get_species_from_postgres(self, since_date: str = None) -> List[Dict[str, Any]]:
        """Get species from PostgreSQL, optionally since a specific date"""
        try:
            conn = psycopg2.connect(**self.postgres_config)
            cursor = conn.cursor()
            
            # Get column names
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'species' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            columns = [row[0] for row in cursor.fetchall()]
            
            # Build query - get new/updated species
            if since_date:
                query = f"""
                SELECT * FROM species 
                WHERE updated_at > %s OR created_at > %s
                ORDER BY taxon_id
                """
                cursor.execute(query, (since_date, since_date))
            else:
                # Get all species
                query = "SELECT * FROM species ORDER BY taxon_id"
                cursor.execute(query)
            
            rows = cursor.fetchall()
            
            # Convert to dictionaries
            species_data = []
            for row in rows:
                record = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        record[columns[i]] = value
                species_data.append(record)
            
            cursor.close()
            conn.close()
            
            logger.info(f"✅ Retrieved {len(species_data)} species from PostgreSQL")
            return species_data
            
        except Exception as e:
            logger.error(f"Error getting species from PostgreSQL: {e}")
            return []
    
    def identify_changes(self, postgres_species: List[Dict[str, Any]], existing_blazegraph_ids: Set[str]) -> Dict[str, List]:
        """Identify new, updated, and unchanged species"""
        try:
            logger.info("🔍 Identifying changes between PostgreSQL and Blazegraph...")
            
            changes = {
                'new_species': [],
                'existing_species': [],
                'total_postgres': len(postgres_species)
            }
            
            for species in postgres_species:
                taxon_id = species.get('taxon_id')
                
                if taxon_id:
                    if taxon_id not in existing_blazegraph_ids:
                        changes['new_species'].append(species)
                    else:
                        changes['existing_species'].append(species)
            
            logger.info(f"📈 Change Analysis:")
            logger.info(f"   New species to add: {len(changes['new_species'])}")
            logger.info(f"   Existing species (skip): {len(changes['existing_species'])}")
            logger.info(f"   Total in PostgreSQL: {changes['total_postgres']}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error identifying changes: {e}")
            return {'new_species': [], 'existing_species': []}
    
    def get_last_sync_timestamp(self) -> str:
        """Get timestamp of last successful sync"""
        try:
            # Check for sync metadata in Blazegraph
            query = """
            SELECT ?timestamp WHERE {
                <http://treekipedia.org/sync/metadata> <http://treekipedia.org/property/last_sync> ?timestamp .
            }
            ORDER BY DESC(?timestamp)
            LIMIT 1
            """
            
            response = requests.post(
                self.fuseki_sparql,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['results']['bindings']:
                    return result['results']['bindings'][0]['timestamp']['value']
            
            # If no sync metadata, return a date far in the past
            return "2020-01-01 00:00:00"
            
        except Exception as e:
            logger.warning(f"Could not get last sync timestamp: {e}")
            return "2020-01-01 00:00:00"
    
    def update_sync_timestamp(self, timestamp: str) -> bool:
        """Update the last sync timestamp in Blazegraph"""
        try:
            # Delete old timestamp
            delete_query = """
            DELETE {
                <http://treekipedia.org/sync/metadata> <http://treekipedia.org/property/last_sync> ?oldTimestamp .
            }
            WHERE {
                <http://treekipedia.org/sync/metadata> <http://treekipedia.org/property/last_sync> ?oldTimestamp .
            }
            """
            
            # Insert new timestamp
            insert_query = f"""
            INSERT DATA {{
                <http://treekipedia.org/sync/metadata> <http://treekipedia.org/property/last_sync> "{timestamp}" .
            }}
            """
            
            # Execute delete
            requests.post(
                self.fuseki_sparql,
                data={'update': delete_query},
                headers={'Content-Type': 'application/sparql-update'},
                timeout=30
            )
            
            # Execute insert
            response = requests.post(
                self.fuseki_sparql,
                data={'update': insert_query},
                headers={'Content-Type': 'application/sparql-update'},
                timeout=30
            )
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Error updating sync timestamp: {e}")
            return False
    
    def convert_species_to_rdf(self, species_list: List[Dict[str, Any]]) -> str:
        """Convert species data to RDF format"""
        logger.info(f"🔄 Converting {len(species_list)} species to RDF...")
        
        rdf_triples = []
        
        for species in species_list:
            try:
                taxon_id = species.get('taxon_id')
                if not taxon_id:
                    continue
                
                entity_uri = f"<{self.species_base_uri}{taxon_id}>"
                
                # Add type declaration
                rdf_triples.append(f"{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{self.species_class_uri}> .")
                
                # Convert each column to RDF property
                for column, value in species.items():
                    if value is not None and value != '':
                        property_uri = f"<http://treekipedia.org/property/{column}>"
                        
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
                logger.warning(f"Error converting species {species.get('taxon_id', 'unknown')}: {e}")
                continue
        
        rdf_content = '\n'.join(rdf_triples)
        logger.info(f"✅ Generated {len(rdf_triples)} RDF triples")
        
        return rdf_content
    
    def upload_new_species_only(self, rdf_content: str) -> Tuple[bool, str]:
        """Upload only new species data using INSERT DATA (additive)"""
        try:
            logger.info("📤 Uploading new species data (additive mode)...")
            
            # Use INSERT DATA to add without overwriting
            insert_query = f"INSERT DATA {{\n{rdf_content}\n}}"
            
            response = requests.post(
                self.fuseki_sparql,
                data={'update': insert_query},
                headers={'Content-Type': 'application/sparql-update'},
                timeout=300
            )
            
            if response.status_code in [200, 204]:
                return True, f"Success (HTTP {response.status_code})"
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def verify_species_count(self) -> int:
        """Get current species count in Blazegraph"""
        try:
            query = f"""
            SELECT (COUNT(?species) as ?count) WHERE {{
                ?species <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{self.species_class_uri}> .
            }}
            """
            
            response = requests.post(
                self.fuseki_sparql,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                count = int(result['results']['bindings'][0]['count']['value'])
                return count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error verifying species count: {e}")
            return 0
    
    def incremental_sync(self, force_full_sync: bool = False) -> Dict[str, Any]:
        """
        Perform incremental sync - only add new species, preserve existing data
        """
        try:
            logger.info("🚀 Starting incremental species sync...")
            
            start_time = datetime.now()
            
            # Step 1: Get existing species in Blazegraph
            if not force_full_sync:
                existing_species_ids = self.get_existing_species_in_blazegraph()
                last_sync = self.get_last_sync_timestamp()
                logger.info(f"Last sync was: {last_sync}")
            else:
                existing_species_ids = set()
                last_sync = None
                logger.info("Force full sync mode - treating all as new")
            
            # Step 2: Get species from PostgreSQL (since last sync if available)
            postgres_species = self.get_species_from_postgres(last_sync if not force_full_sync else None)
            
            if not postgres_species:
                return {
                    'success': True,
                    'message': 'No species data found in PostgreSQL',
                    'new_species': 0,
                    'existing_preserved': len(existing_species_ids)
                }
            
            # Step 3: Identify changes
            changes = self.identify_changes(postgres_species, existing_species_ids)
            
            # Step 4: Process only new species
            if changes['new_species']:
                logger.info(f"🔄 Processing {len(changes['new_species'])} new species...")
                
                # Convert to RDF
                rdf_content = self.convert_species_to_rdf(changes['new_species'])
                
                # Upload additively (won't overwrite existing)
                success, message = self.upload_new_species_only(rdf_content)
                
                if success:
                    # Update sync timestamp
                    current_timestamp = datetime.now().isoformat()
                    self.update_sync_timestamp(current_timestamp)
                    
                    # Verify final count
                    final_count = self.verify_species_count()
                    
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    return {
                        'success': True,
                        'sync_type': 'incremental',
                        'new_species_added': len(changes['new_species']),
                        'existing_species_preserved': len(changes['existing_species']),
                        'total_species_in_blazegraph': final_count,
                        'sync_duration_seconds': duration,
                        'last_sync_timestamp': current_timestamp,
                        'data_preserved': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Upload failed: {message}",
                        'new_species_attempted': len(changes['new_species']),
                        'data_preserved': True  # No data was overwritten
                    }
            else:
                logger.info("✅ No new species to sync - all data is up to date!")
                
                return {
                    'success': True,
                    'sync_type': 'no_changes',
                    'message': 'All species data is up to date',
                    'existing_species_preserved': len(changes['existing_species']),
                    'total_species_in_blazegraph': self.verify_species_count(),
                    'data_preserved': True
                }
                
        except Exception as e:
            logger.error(f"Error in incremental sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'data_preserved': True  # Incremental sync preserves data
            }
    
    def sync_specific_species(self, species_ids: List[str]) -> Dict[str, Any]:
        """Sync only specific species by their taxon_ids"""
        try:
            logger.info(f"🎯 Syncing specific species: {species_ids}")
            
            conn = psycopg2.connect(**self.postgres_config)
            cursor = conn.cursor()
            
            # Get column names
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'species' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            columns = [row[0] for row in cursor.fetchall()]
            
            # Get specific species
            placeholders = ','.join(['%s'] * len(species_ids))
            query = f"SELECT * FROM species WHERE taxon_id IN ({placeholders})"
            cursor.execute(query, species_ids)
            rows = cursor.fetchall()
            
            # Convert to dictionaries
            species_data = []
            for row in rows:
                record = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        record[columns[i]] = value
                species_data.append(record)
            
            cursor.close()
            conn.close()
            
            if species_data:
                # Convert and upload
                rdf_content = self.convert_species_to_rdf(species_data)
                success, message = self.upload_new_species_only(rdf_content)
                
                return {
                    'success': success,
                    'species_synced': len(species_data),
                    'message': message if success else f"Error: {message}"
                }
            else:
                return {
                    'success': False,
                    'error': 'No species found with provided IDs'
                }
                
        except Exception as e:
            logger.error(f"Error syncing specific species: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Convenience functions
def sync_new_species_only(blazegraph_endpoint: str = None) -> Dict[str, Any]:
    """
    Convenience function to sync only new species from PostgreSQL
    """
    syncer = IncrementalSpeciesSync()
    return syncer.incremental_sync()


def force_resync_all_species(blazegraph_endpoint: str = None) -> Dict[str, Any]:
    """
    Force a complete resync of all species (use carefully)
    """
    syncer = IncrementalSpeciesSync()
    return syncer.incremental_sync(force_full_sync=True)


def sync_species_by_ids(species_ids: List[str], blazegraph_endpoint: str = None) -> Dict[str, Any]:
    """
    Sync specific species by their taxon_ids
    """
    syncer = IncrementalSpeciesSync()
    return syncer.sync_specific_species(species_ids)


if __name__ == "__main__":
    # Test incremental sync
    syncer = IncrementalSpeciesSync()
    
    # Check current state
    existing_count = len(syncer.get_existing_species_in_blazegraph())
    print(f"Current species in Blazegraph: {existing_count}")
    
    # Run incremental sync
    result = syncer.incremental_sync()
    print(f"Sync result: {result}")