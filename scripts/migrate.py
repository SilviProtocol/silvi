#!/usr/bin/env python3
"""
Simple script to migrate existing data from Blazegraph to Fuseki
Run this after setting up Fuseki on your VM
"""

import requests
import json
from datetime import datetime

class SimpleMigration:
    def __init__(self):
        self.blazegraph_url = "http://167.172.143.162:9999/blazegraph/namespace/kb/sparql"
        self.fuseki_sparql = "http://167.172.143.162:3030/treekipedia/sparql"
        self.fuseki_data = "http://167.172.143.162:3030/treekipedia/data"
    
    def test_connections(self):
        """Test both Blazegraph and Fuseki connections"""
        print("🔍 Testing connections...")
        
        # Test Blazegraph
        try:
            bg_response = requests.get(self.blazegraph_url, timeout=5)
            bg_working = bg_response.status_code == 200
            print(f"{'✅' if bg_working else '❌'} Blazegraph: {'Working' if bg_working else 'Not accessible'}")
        except:
            bg_working = False
            print("❌ Blazegraph: Not accessible")
        
        # Test Fuseki
        try:
            fuseki_ping = requests.get("http://167.172.143.162:3030/$/ping", timeout=5)
            fuseki_working = fuseki_ping.status_code == 200
            print(f"{'✅' if fuseki_working else '❌'} Fuseki: {'Working' if fuseki_working else 'Not accessible'}")
        except:
            fuseki_working = False
            print("❌ Fuseki: Not accessible")
        
        return bg_working, fuseki_working
    
    def get_blazegraph_data(self):
        """Export all data from Blazegraph"""
        try:
            print("📤 Exporting data from Blazegraph...")
            
            # SPARQL query to get all triples
            query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
            
            response = requests.post(
                self.blazegraph_url,
                data={'query': query},
                headers={'Accept': 'application/rdf+xml'},
                timeout=120
            )
            
            if response.status_code == 200:
                rdf_data = response.content
                print(f"✅ Exported {len(rdf_data)} bytes of RDF data")
                return rdf_data
            else:
                print(f"❌ Export failed: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Export error: {e}")
            return None
    
    def import_to_fuseki(self, rdf_data):
        """Import data to Fuseki"""
        try:
            print("📥 Importing data to Fuseki...")
            
            # Create a graph for the migrated data
            graph_uri = f"http://treekipedia.org/migrated_data_{datetime.now().strftime('%Y%m%d')}"
            
            # Import using HTTP PUT
            response = requests.put(
                self.fuseki_data,
                data=rdf_data,
                headers={'Content-Type': 'application/rdf+xml'},
                params={'graph': graph_uri},
                timeout=120
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"✅ Import successful: HTTP {response.status_code}")
                return True, graph_uri
            else:
                print(f"❌ Import failed: HTTP {response.status_code}")
                return False, None
                
        except Exception as e:
            print(f"❌ Import error: {e}")
            return False, None
    
    def verify_migration(self):
        """Verify data was migrated successfully"""
        try:
            print("🔍 Verifying migration...")
            
            # Count triples in Blazegraph
            bg_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            bg_response = requests.post(
                self.blazegraph_url,
                data={'query': bg_query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=30
            )
            
            bg_count = 0
            if bg_response.status_code == 200:
                bg_result = bg_response.json()
                bg_count = int(bg_result['results']['bindings'][0]['count']['value'])
            
            # Count triples in Fuseki
            fuseki_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            fuseki_response = requests.post(
                self.fuseki_sparql,
                data={'query': fuseki_query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=30
            )
            
            fuseki_count = 0
            if fuseki_response.status_code == 200:
                fuseki_result = fuseki_response.json()
                fuseki_count = int(fuseki_result['results']['bindings'][0]['count']['value'])
            
            print(f"📊 Migration Results:")
            print(f"   Blazegraph: {bg_count:,} triples")
            print(f"   Fuseki:     {fuseki_count:,} triples")
            
            success_rate = (fuseki_count / bg_count * 100) if bg_count > 0 else 100
            print(f"   Success:    {success_rate:.1f}%")
            
            return fuseki_count > 0
            
        except Exception as e:
            print(f"❌ Verification error: {e}")
            return False
    
    def run_migration(self):
        """Run the complete migration"""
        print("🚀 Starting Simple Blazegraph to Fuseki Migration")
        print("=" * 55)
        
        # Test connections
        bg_working, fuseki_working = self.test_connections()
        
        if not bg_working:
            print("❌ Cannot proceed: Blazegraph not accessible")
            return False
        
        if not fuseki_working:
            print("❌ Cannot proceed: Fuseki not accessible")
            print("   Please run the Fuseki setup script first")
            return False
        
        # Export data
        rdf_data = self.get_blazegraph_data()
        if not rdf_data:
            print("❌ Cannot proceed: No data exported")
            return False
        
        # Import data
        import_success, graph_uri = self.import_to_fuseki(rdf_data)
        if not import_success:
            print("❌ Migration failed during import")
            return False
        
        # Verify migration
        verification_success = self.verify_migration()
        
        if verification_success:
            print(f"\n🎉 MIGRATION SUCCESSFUL!")
            print("=" * 25)
            print(f"✅ Data migrated to Fuseki")
            print(f"🔗 Graph URI: {graph_uri}")
            print(f"🌐 Fuseki UI: http://167.172.143.162:3030")
            print(f"📊 SPARQL: http://167.172.143.162:3030/treekipedia/sparql")
            print(f"\n🔄 Next: Update your config.py with the new endpoint!")
            return True
        else:
            print("⚠️  Migration completed but verification failed")
            return False

def main():
    """Main execution"""
    migration = SimpleMigration()
    success = migration.run_migration()
    
    if success:
        print(f"\n📝 To complete the migration:")
        print(f"   1. Update your config.py BLAZEGRAPH_ENDPOINT to:")
        print(f"      http://167.172.143.162:3030/treekipedia/sparql")
        print(f"   2. Restart your Flask application")
        print(f"   3. Test your existing routes - they should work unchanged!")
    
    return success

if __name__ == "__main__":
    main()