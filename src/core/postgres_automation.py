#!/usr/bin/env python3
"""
Fixed PostgreSQL Automation Script for Treekipedia
Works correctly with real Treekipedia data structure
"""

import json
import logging
import os
import sys
import argparse
from datetime import datetime
from postgres_rdf_converter import PostgreSQLRDFConverter, RDFValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixedPostgreSQLAutomation:
    """Fixed automation class for PostgreSQL monitoring"""
    
    def __init__(self, config_path: str):
        """Initialize automation with configuration file"""
        self.config_path = config_path
        self.config = self.load_config()
        
        # Initialize converter if PostgreSQL is enabled
        if self.config.get('postgresql', {}).get('enabled', False):
            self.converter = PostgreSQLRDFConverter(self.config['postgresql'])
        else:
            self.converter = None
            logger.warning("PostgreSQL integration is disabled in configuration")
    
    def load_config(self) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Return working config for Treekipedia
            return {
                'postgresql': {
                    'enabled': True,
                    'db_connection': {
                        'host': '167.172.143.162',
                        'database': 'treekipedia',
                        'user': 'postgres',
                        'password': '9353jeremic',
                        'port': 5432
                    }
                },
                'blazegraph': {
                    'enabled': True,
                    'endpoint': 'http://167.172.143.162:9999/blazegraph/namespace/kb/sparql'
                }
            }
    
    def check_for_changes(self) -> dict:
        """Check which tables have changed and get actual data"""
        if not self.converter:
            return {'tables': [], 'total_records': 0}
        
        if not self.converter.connect_to_database():
            logger.error("Could not connect to database")
            return {'tables': [], 'total_records': 0}
        
        try:
            # Real Treekipedia tables (based on your actual data)
            tables_to_check = ['species', 'users', 'sponsorships', 'sponsorship_items', 'contreebution_nfts']
            
            table_results = []
            total_records = 0
            
            for table_name in tables_to_check:
                try:
                    # Get actual data using the working method
                    data = self.converter.get_table_changes(table_name)
                    record_count = len(data) if data else 0
                    
                    # Get total count for this table
                    cursor = self.converter.connection.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    total_count = cursor.fetchone()[0]
                    cursor.close()
                    
                    table_info = {
                        'name': table_name,
                        'sample_records': record_count,
                        'total_records': total_count,
                        'sample_data': data[:2] if data else []  # First 2 records
                    }
                    
                    table_results.append(table_info)
                    total_records += total_count
                    
                    logger.info(f"Table {table_name}: {total_count:,} total records, {record_count} sampled")
                    
                except Exception as e:
                    logger.warning(f"Could not check table {table_name}: {str(e)}")
                    table_results.append({
                        'name': table_name,
                        'sample_records': 0,
                        'total_records': 0,
                        'error': str(e)
                    })
            
            return {
                'tables': table_results,
                'total_records': total_records,
                'database_accessible': True
            }
            
        finally:
            self.converter.close_connection()
    
    def generate_rdf_summary(self, table_data: dict) -> dict:
        """Generate RDF summary from real data"""
        logger.info("Generating RDF summary from real Treekipedia data...")
        
        total_records = table_data['total_records']
        
        # Calculate realistic RDF triples for Treekipedia
        # Species table has 99 columns, so ~100 triples per species
        # Other tables have fewer columns
        estimated_triples = 0
        
        for table_info in table_data['tables']:
            table_name = table_info['name']
            count = table_info['total_records']
            
            if table_name == 'species':
                # Species has rich data - ~100 triples per record
                triples = count * 100
            elif table_name in ['sponsorships', 'sponsorship_items']:
                # Sponsorship data - ~15 triples per record
                triples = count * 15
            elif table_name == 'contreebution_nfts':
                # NFT data - ~10 triples per record
                triples = count * 10
            else:
                # Users and other tables - ~8 triples per record
                triples = count * 8
            
            estimated_triples += triples
            logger.info(f"  {table_name}: {count:,} records → {triples:,} triples")
        
        rdf_summary = {
            'total_records_processed': total_records,
            'estimated_triples': estimated_triples,
            'tables_processed': len([t for t in table_data['tables'] if t['total_records'] > 0]),
            'timestamp': datetime.now().isoformat(),
            'mode': 'real_data'
        }
        
        logger.info(f"Total estimated RDF triples: {estimated_triples:,}")
        return rdf_summary
    
    def test_blazegraph_connection(self) -> dict:
        """Test Blazegraph connectivity"""
        if not self.config.get('blazegraph', {}).get('enabled', False):
            return {'accessible': False, 'reason': 'Blazegraph disabled in config'}
        
        try:
            import requests
            
            endpoint = self.config['blazegraph']['endpoint']
            
            # Test SPARQL query
            test_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            
            response = requests.post(
                endpoint,
                headers={
                    'Content-Type': 'application/sparql-query',
                    'Accept': 'application/sparql-results+json'
                },
                data=test_query,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                current_triples = result['results']['bindings'][0]['count']['value']
                
                return {
                    'accessible': True,
                    'current_triples': int(current_triples),
                    'endpoint': endpoint
                }
            else:
                return {
                    'accessible': False,
                    'reason': f'HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {
                'accessible': False,
                'reason': str(e)
            }
    
    def run_automation_cycle(self) -> bool:
        """Run one automation cycle with real data"""
        try:
            logger.info("🌳 Starting Treekipedia automation cycle")
            
            # Check for data
            table_data = self.check_for_changes()
            
            if not table_data['tables']:
                logger.warning("No tables could be accessed")
                return False
            
            accessible_tables = [t for t in table_data['tables'] if t['total_records'] > 0]
            
            if not accessible_tables:
                logger.warning("No tables with data found")
                return False
            
            logger.info(f"Found {len(accessible_tables)} tables with data")
            
            # Show summary of real data
            print(f"\n🌳 REAL TREEKIPEDIA DATA SUMMARY")
            print("=" * 40)
            for table_info in accessible_tables:
                print(f"  {table_info['name']}: {table_info['total_records']:,} records")
            print(f"  TOTAL: {table_data['total_records']:,} records")
            
            # Generate RDF summary
            rdf_summary = self.generate_rdf_summary(table_data)
            
            print(f"\n🔗 RDF CONVERSION ESTIMATE")
            print("=" * 30)
            print(f"  Records: {rdf_summary['total_records_processed']:,}")
            print(f"  Triples: {rdf_summary['estimated_triples']:,}")
            print(f"  Size: ~{rdf_summary['estimated_triples'] * 150 / 1024 / 1024:.1f} MB")
            
            # Test Blazegraph
            blazegraph_info = self.test_blazegraph_connection()
            print(f"\n🔥 BLAZEGRAPH STATUS")
            print("=" * 20)
            if blazegraph_info['accessible']:
                print(f"  Status: ✅ Accessible")
                print(f"  Current triples: {blazegraph_info['current_triples']:,}")
                print(f"  Endpoint: {blazegraph_info['endpoint']}")
            else:
                print(f"  Status: ❌ {blazegraph_info['reason']}")
            
            # Log results
            self.log_automation_results(table_data, rdf_summary, blazegraph_info)
            
            logger.info("Automation cycle completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error in automation cycle: {str(e)}", exc_info=True)
            return False
    
    def log_automation_results(self, table_data: dict, rdf_summary: dict, blazegraph_info: dict):
        """Log automation results"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'database_status': 'connected' if table_data['database_accessible'] else 'failed',
            'tables_summary': {
                'total_tables': len(table_data['tables']),
                'accessible_tables': len([t for t in table_data['tables'] if t['total_records'] > 0]),
                'total_records': table_data['total_records']
            },
            'rdf_summary': rdf_summary,
            'blazegraph_info': blazegraph_info
        }
        
        # Save to log file
        log_file = 'treekipedia_automation_results.json'
        try:
            with open(log_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {log_file}")
        except Exception as e:
            logger.error(f"Could not save results: {str(e)}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Fixed PostgreSQL Automation for Treekipedia')
    parser.add_argument('--config', default='working_treekipedia_config.json', 
                       help='Path to configuration file')
    parser.add_argument('--once', action='store_true', 
                       help='Run once instead of continuously')
    
    args = parser.parse_args()
    
    try:
        automation = FixedPostgreSQLAutomation(args.config)
        
        if args.once:
            success = automation.run_automation_cycle()
            sys.exit(0 if success else 1)
        else:
            logger.info("Continuous mode not implemented yet. Use --once flag.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()