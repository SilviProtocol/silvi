#!/usr/bin/env python3
"""
Fixed Incremental Ontology Updater - Fuseki Compatible
"""

import requests
import json
import logging
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import hashlib
import re

logger = logging.getLogger(__name__)

class IncrementalOntologyUpdater:
    """
    Smart updater that only applies changes to ontologies, preserving existing data
    FIXED for Apache Jena Fuseki compatibility
    """
    
    def __init__(self, fuseki_endpoint: str):
        # FIXED: Use proper Fuseki endpoints instead of Blazegraph
        # Normalize the endpoint - find the base URL for the dataset
        endpoint = fuseki_endpoint.rstrip('/')
        
        # Extract base URL by removing endpoint-specific paths
        if '/sparql' in endpoint:
            base_url = endpoint.replace('/sparql', '')
        elif '/update' in endpoint:
            base_url = endpoint.replace('/update', '')
        elif '/data' in endpoint:
            base_url = endpoint.replace('/data', '')
        else:
            # Assume we got the base dataset URL
            base_url = endpoint
        
        # Ensure the base_url doesn't have double dataset names
        if base_url.endswith('/treekipedia/treekipedia'):
            base_url = base_url.replace('/treekipedia/treekipedia', '/treekipedia')
        elif '/treekipedia' not in base_url:
            base_url = f"{base_url}/treekipedia"
        
        # Construct the three different Fuseki endpoints
        self.fuseki_sparql = f"{base_url}/sparql"     # For SELECT queries
        self.fuseki_update = f"{base_url}/update"     # For UPDATE queries (CRITICAL: NOT /sparql/update!)
        self.fuseki_data = f"{base_url}/data"         # For data upload
        
        logger.info(f"Fuseki Query Endpoint: {self.fuseki_sparql}")
        logger.info(f"Fuseki Update Endpoint: {self.fuseki_update}")
        
        # Debug print to verify correct endpoint construction
        print(f"🔧 CONSTRUCTOR DEBUG: Input={fuseki_endpoint}")
        print(f"🔧 CONSTRUCTOR DEBUG: Base URL={base_url}")
        print(f"🔧 CONSTRUCTOR DEBUG: Update endpoint={self.fuseki_update}")
    
    def clean_text_for_rdf(self, text: str) -> str:
        """Clean text to ensure proper RDF encoding and remove problematic characters"""
        if not isinstance(text, str):
            return str(text)
        
        # Replace problematic Unicode characters with ASCII equivalents
        replacements = {
            '\u2019': "'",      # Right single quotation mark
            '\u2018': "'",      # Left single quotation mark
            '\u201C': '"',      # Left double quotation mark
            '\u201D': '"',      # Right double quotation mark
            '\u2013': '-',      # En dash
            '\u2014': '-',      # Em dash
            '\u2011': '-',      # Non-breaking hyphen
            '\u00A0': ' ',      # Non-breaking space
            '\u2026': '...',    # Horizontal ellipsis
            '\u00B0': ' deg',   # Degree symbol
            '\u00D7': 'x',      # Multiplication sign
            '\u00F7': '/',      # Division sign
        }
        
        cleaned_text = text
        for unicode_char, replacement in replacements.items():
            cleaned_text = cleaned_text.replace(unicode_char, replacement)
        
        # Remove any remaining non-ASCII characters
        cleaned_text = ''.join(char if ord(char) < 128 else '?' for char in cleaned_text)
        
        # Escape characters that need escaping in RDF literals
        cleaned_text = (cleaned_text
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t'))
        
        return cleaned_text

    def get_current_ontology_state(self, ontology_graph: str = None) -> Dict[str, Set[str]]:
        """Get current state of ontology in Fuseki"""
        try:
            logger.info("📊 Analyzing current ontology state...")
            
            # Query for existing classes, properties, and individuals
            current_state = {
                'classes': set(),
                'data_properties': set(),
                'object_properties': set(),
                'individuals': set(),
                'triples': set()
            }
            
            # Get all classes
            classes_query = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?class WHERE {
                ?class a owl:Class
            }
            """
            
            # Get all data properties  
            data_props_query = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?prop WHERE {
                ?prop a owl:DatatypeProperty
            }
            """
            
            # Get all object properties
            obj_props_query = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?prop WHERE {
                ?prop a owl:ObjectProperty
            }
            """
            
            # Get all individuals
            individuals_query = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?individual WHERE {
                ?individual a owl:NamedIndividual
            }
            """
            
            queries = [
                ('classes', classes_query),
                ('data_properties', data_props_query), 
                ('object_properties', obj_props_query),
                ('individuals', individuals_query)
            ]
            
            for category, query in queries:
                response = requests.post(
                    self.fuseki_sparql,  # FIXED: Use fuseki_sparql
                    data={'query': query},
                    headers={'Accept': 'application/sparql-results+json'},
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    for binding in result['results']['bindings']:
                        key_name = category.rstrip('s') if category != 'classes' else 'class'
                        if category == 'data_properties':
                            key_name = 'prop'
                        elif category == 'object_properties':
                            key_name = 'prop'
                        elif category == 'individuals':
                            key_name = 'individual'
                        
                        uri = binding[key_name]['value']
                        current_state[category].add(uri)
                
                logger.info(f"   Found {len(current_state[category])} {category}")
            
            return current_state
            
        except Exception as e:
            logger.error(f"Error getting current ontology state: {e}")
            return {'classes': set(), 'data_properties': set(), 'object_properties': set(), 'individuals': set()}
    
    def analyze_ontology_changes(self, new_ontology_analysis: Dict[str, Any], current_state: Dict[str, Set[str]]) -> Dict[str, Any]:
        """Compare new ontology with current state to identify changes"""
        try:
            logger.info("🔍 Analyzing ontology changes...")
            
            changes = {
                'additions': {
                    'classes': [],
                    'data_properties': [],
                    'object_properties': [], 
                    'individuals': []
                },
                'modifications': {
                    'classes': [],
                    'properties': [],
                    'individuals': []
                },
                'unchanged': {
                    'classes': [],
                    'properties': [],
                    'individuals': []
                },
                'summary': {}
            }
            
            # Analyze new classes
            for class_name, class_info in new_ontology_analysis.get('ontology_classes', {}).items():
                class_uri = f"http://www.example.org/biodiversity-ontology#{class_name}"
                
                if class_uri not in current_state['classes']:
                    changes['additions']['classes'].append({
                        'name': class_name,
                        'uri': class_uri,
                        'info': class_info
                    })
                else:
                    changes['unchanged']['classes'].append(class_name)
            
            # Analyze new data properties
            for prop in new_ontology_analysis.get('data_properties', []):
                prop_uri = f"http://www.example.org/biodiversity-ontology#{prop['name']}"
                
                if prop_uri not in current_state['data_properties']:
                    changes['additions']['data_properties'].append(prop)
                else:
                    changes['unchanged']['properties'].append(prop['name'])
            
            # Analyze new object properties
            for prop in new_ontology_analysis.get('object_properties', []):
                prop_uri = f"http://www.example.org/biodiversity-ontology#{prop['name']}"
                
                if prop_uri not in current_state['object_properties']:
                    changes['additions']['object_properties'].append(prop)
                else:
                    changes['unchanged']['properties'].append(prop['name'])
            
            # Analyze new individuals
            for individual in new_ontology_analysis.get('individuals', []):
                individual_uri = f"http://www.example.org/biodiversity-ontology#{individual['name']}"
                
                if individual_uri not in current_state['individuals']:
                    changes['additions']['individuals'].append(individual)
                else:
                    changes['unchanged']['individuals'].append(individual['name'])
            
            # Generate summary
            changes['summary'] = {
                'total_additions': (
                    len(changes['additions']['classes']) +
                    len(changes['additions']['data_properties']) +
                    len(changes['additions']['object_properties']) +
                    len(changes['additions']['individuals'])
                ),
                'new_classes': len(changes['additions']['classes']),
                'new_data_properties': len(changes['additions']['data_properties']),
                'new_object_properties': len(changes['additions']['object_properties']),
                'new_individuals': len(changes['additions']['individuals']),
                'unchanged_items': (
                    len(changes['unchanged']['classes']) +
                    len(changes['unchanged']['properties']) +
                    len(changes['unchanged']['individuals'])
                )
            }
            
            logger.info(f"📈 Change Analysis Complete:")
            logger.info(f"   New items to add: {changes['summary']['total_additions']}")
            logger.info(f"   Unchanged items: {changes['summary']['unchanged_items']}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error analyzing changes: {e}")
            return {'additions': {}, 'modifications': {}, 'summary': {'total_additions': 0}}
    
    def apply_incremental_updates(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Apply only the changes to Fuseki, preserving existing data"""
        try:
            logger.info("⚡ Applying incremental updates...")
            
            results = {
                'success': True,
                'applied_changes': 0,
                'errors': [],
                'details': {}
            }
            
            # Apply new classes
            if changes['additions']['classes']:
                logger.info(f"Adding {len(changes['additions']['classes'])} new classes...")
                
                for class_info in changes['additions']['classes']:
                    class_triples = self._generate_class_triples(class_info)
                    success = self._insert_triples(class_triples)
                    
                    if success:
                        results['applied_changes'] += 1
                        logger.info(f"✅ Added class: {class_info['name']}")
                    else:
                        results['errors'].append(f"Failed to add class: {class_info['name']}")
            
            # Apply new data properties
            if changes['additions']['data_properties']:
                logger.info(f"Adding {len(changes['additions']['data_properties'])} new data properties...")
                
                for prop in changes['additions']['data_properties']:
                    prop_triples = self._generate_data_property_triples(prop)
                    success = self._insert_triples(prop_triples)
                    
                    if success:
                        results['applied_changes'] += 1
                        logger.info(f"✅ Added data property: {prop['name']}")
                    else:
                        results['errors'].append(f"Failed to add data property: {prop['name']}")
            
            # Apply new object properties
            if changes['additions']['object_properties']:
                logger.info(f"Adding {len(changes['additions']['object_properties'])} new object properties...")
                
                for prop in changes['additions']['object_properties']:
                    prop_triples = self._generate_object_property_triples(prop)
                    success = self._insert_triples(prop_triples)
                    
                    if success:
                        results['applied_changes'] += 1
                        logger.info(f"✅ Added object property: {prop['name']}")
                    else:
                        results['errors'].append(f"Failed to add object property: {prop['name']}")
            
            # Apply new individuals in smaller batches with proper encoding
            if changes['additions']['individuals']:
                total_individuals = len(changes['additions']['individuals'])
                logger.info(f"Adding {total_individuals} new individuals in batches...")
                
                # Process in batches of 25 to avoid timeouts and encoding issues
                batch_size = 25
                individuals_added = 0
                
                for i in range(0, total_individuals, batch_size):
                    batch = changes['additions']['individuals'][i:i + batch_size]
                    logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} individuals...")
                    
                    # Generate triples for this batch with proper text cleaning
                    batch_triples = []
                    for individual in batch:
                        individual_triples = self._generate_individual_triples(individual)
                        batch_triples.extend(individual_triples)
                    
                    if batch_triples:
                        success = self._insert_triples(batch_triples)
                        
                        if success:
                            individuals_added += len(batch)
                            results['applied_changes'] += len(batch)
                            logger.info(f"✅ Added batch of {len(batch)} individuals")
                        else:
                            results['errors'].append(f"Failed to add batch of {len(batch)} individuals")
                    
                    # Small delay between batches to prevent overload
                    import time
                    time.sleep(0.5)
                
                logger.info(f"✅ Total individuals added: {individuals_added}/{total_individuals}")
            
            results['success'] = len(results['errors']) == 0
            results['details'] = {
                'classes_added': len(changes['additions']['classes']),
                'data_properties_added': len(changes['additions']['data_properties']),
                'object_properties_added': len(changes['additions']['object_properties']),
                'individuals_added': len(changes['additions']['individuals'])
            }
            
            logger.info(f"🎯 Incremental update complete: {results['applied_changes']} changes applied")
            
            return results
            
        except Exception as e:
            logger.error(f"Error applying incremental updates: {e}")
            return {
                'success': False,
                'error': str(e),
                'applied_changes': 0
            }
        
    def _generate_class_triples(self, class_info: Dict[str, Any]) -> List[str]:
        """Generate RDF triples for a new class"""
        triples = []
        class_uri = f"<{class_info['uri']}>"
        
        # Class declaration
        triples.append(f"{class_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .")
        
        # Label
        if 'name' in class_info:
            clean_name = self.clean_text_for_rdf(class_info['name'])
            triples.append(f"{class_uri} <http://www.w3.org/2000/01/rdf-schema#label> \"{clean_name}\" .")
        
        # Description/comment
        if 'description' in class_info.get('info', {}):
            clean_description = self.clean_text_for_rdf(class_info['info']['description'])
            triples.append(f"{class_uri} <http://www.w3.org/2000/01/rdf-schema#comment> \"{clean_description}\" .")
        
        return triples
    
    def _generate_data_property_triples(self, prop: Dict[str, Any]) -> List[str]:
        """Generate RDF triples for a new data property"""
        triples = []
        prop_uri = f"<http://www.example.org/biodiversity-ontology#{prop['name']}>"
        
        # Property declaration
        triples.append(f"{prop_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#DatatypeProperty> .")
        
        # Domain
        if 'domain' in prop:
            domain_uri = f"<http://www.example.org/biodiversity-ontology#{prop['domain']}>"
            triples.append(f"{prop_uri} <http://www.w3.org/2000/01/rdf-schema#domain> {domain_uri} .")
        
        # Range
        if 'range' in prop:
            if prop['range'] == 'string':
                range_uri = "<http://www.w3.org/2001/XMLSchema#string>"
            elif prop['range'] == 'numeric':
                range_uri = "<http://www.w3.org/2001/XMLSchema#decimal>"
            else:
                range_uri = "<http://www.w3.org/2001/XMLSchema#string>"
            triples.append(f"{prop_uri} <http://www.w3.org/2000/01/rdf-schema#range> {range_uri} .")
        
        # Functional property
        if prop.get('functional', False):
            triples.append(f"{prop_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#FunctionalProperty> .")
        
        return triples
    
    def _generate_object_property_triples(self, prop: Dict[str, Any]) -> List[str]:
        """Generate RDF triples for a new object property"""
        triples = []
        prop_uri = f"<http://www.example.org/biodiversity-ontology#{prop['name']}>"
        
        # Property declaration
        triples.append(f"{prop_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#ObjectProperty> .")
        
        # Domain
        if 'domain' in prop:
            domain_uri = f"<http://www.example.org/biodiversity-ontology#{prop['domain']}>"
            triples.append(f"{prop_uri} <http://www.w3.org/2000/01/rdf-schema#domain> {domain_uri} .")
        
        # Range
        if 'range' in prop:
            range_uri = f"<http://www.example.org/biodiversity-ontology#{prop['range']}>"
            triples.append(f"{prop_uri} <http://www.w3.org/2000/01/rdf-schema#range> {range_uri} .")
        
        return triples
    
    def _generate_individual_triples(self, individual: Dict[str, Any]) -> List[str]:
        """Generate RDF triples for a new individual with proper text cleaning"""
        triples = []
        individual_uri = f"<http://www.example.org/biodiversity-ontology#{individual['name']}>"
        
        # Individual declaration
        triples.append(f"{individual_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#NamedIndividual> .")
        
        # Class membership
        if 'class' in individual:
            class_uri = f"<http://www.example.org/biodiversity-ontology#{individual['class']}>"
            triples.append(f"{individual_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> {class_uri} .")
        
        # Label with proper text cleaning
        if 'label' in individual:
            clean_label = self.clean_text_for_rdf(individual['label'])
            triples.append(f"{individual_uri} <http://www.w3.org/2000/01/rdf-schema#label> \"{clean_label}\" .")
        
        return triples
    
    def _insert_triples(self, triples: List[str]) -> bool:
        """Insert triples into Fuseki using SPARQL UPDATE - FIXED for Fuseki compatibility"""
        try:
            if not triples:
                return True
            
            # Create proper SPARQL INSERT DATA query with PREFIX declarations
            prefixes = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            """
            
            insert_query = prefixes + "\nINSERT DATA {\n" + "\n".join(triples) + "\n}"
            
            logger.debug(f"Sending SPARQL UPDATE: {insert_query[:200]}...")
            
            # FIXED: Try different content types for Fuseki compatibility
            content_types = [
                ('application/sparql-update; charset=utf-8', lambda q: q.encode('utf-8')),
                ('application/x-www-form-urlencoded', lambda q: {'update': q}),
                ('text/plain; charset=utf-8', lambda q: q.encode('utf-8'))
            ]
            
            for attempt, (content_type, data_formatter) in enumerate(content_types):
                headers = {
                    'Content-Type': content_type,
                    'Accept': 'application/sparql-results+json'
                }
                
                data = data_formatter(insert_query)
                
                try:
                    logger.info(f"Attempt {attempt + 1}: Sending to {self.fuseki_update}")
                    
                    response = requests.post(
                        self.fuseki_update,  # FIXED: Use fuseki_update endpoint
                        data=data,
                        headers=headers,
                        timeout=600 
                    )
                    
                    logger.info(f"Fuseki response: {response.status_code}")  # FIXED: Say Fuseki
                    if response.text:
                        logger.debug(f"Response text: {response.text[:200]}...")
                    
                    # FIXED: Both 200 and 204 are success responses
                    if response.status_code in [200, 204]:
                        return True
                    elif response.status_code == 415:
                        logger.warning(f"HTTP 415 with {content_type}, trying next content type...")
                        continue
                    else:
                        logger.error(f"Fuseki error: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        break
                        
                except Exception as e:
                    logger.error(f"Request error with {content_type}: {e}")
                    if attempt == len(content_types) - 1:  # Last attempt
                        raise e
                    continue
            
            # If we get here, all attempts failed
            return False
            
        except Exception as e:
            logger.error(f"Error inserting triples: {e}")
            return False
    
    def update_ontology_from_spreadsheet(self, spreadsheet_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete workflow: update ontology from spreadsheet analysis
        """
        try:
            logger.info("🔄 Starting incremental ontology update from spreadsheet...")
            
            # Step 1: Get current state
            current_state = self.get_current_ontology_state()
            
            # Step 2: Analyze changes
            changes = self.analyze_ontology_changes(spreadsheet_analysis, current_state)
            
            # Step 3: Show preview of changes
            logger.info("📋 Update Preview:")
            logger.info(f"   New classes: {changes['summary']['new_classes']}")
            logger.info(f"   New data properties: {changes['summary']['new_data_properties']}")
            logger.info(f"   New object properties: {changes['summary']['new_object_properties']}")
            logger.info(f"   New individuals: {changes['summary']['new_individuals']}")
            logger.info(f"   Total new items: {changes['summary']['total_additions']}")
            
            # Step 4: Apply changes if there are any
            if changes['summary']['total_additions'] > 0:
                results = self.apply_incremental_updates(changes)
                
                return {
                    'success': results['success'],
                    'update_type': 'incremental',
                    'changes_analyzed': changes['summary'],
                    'changes_applied': results['applied_changes'],
                    'errors': results.get('errors', []),
                    'preserved_existing_data': True,
                    'timestamp': datetime.now().isoformat(),
                    'encoding_fixed': True
                }
            else:
                logger.info("✅ No changes detected - ontology is up to date!")
                
                return {
                    'success': True,
                    'update_type': 'no_changes',
                    'message': 'Ontology is already up to date',
                    'preserved_existing_data': True,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in ontology update workflow: {e}")
            return {
                'success': False,
                'error': str(e),
                'preserved_existing_data': True,
                'timestamp': datetime.now().isoformat()
            }


# Convenience function for easy integration
def update_ontology_incrementally(spreadsheet_analysis: Dict[str, Any], fuseki_endpoint: str) -> Dict[str, Any]:
    """
    Update ontology incrementally from spreadsheet analysis
    FIXED: Use fuseki_endpoint instead of blazegraph_endpoint
    """
    updater = IncrementalOntologyUpdater(fuseki_endpoint)
    return updater.update_ontology_from_spreadsheet(spreadsheet_analysis)


if __name__ == "__main__":

    test_endpoints = [
        "http://167.172.143.162:3030/treekipedia",
        "http://167.172.143.162:3030/treekipedia/sparql",
        "http://167.172.143.162:3030/treekipedia/update"
    ]
    
    for endpoint in test_endpoints:
        print(f"\n🧪 Testing: {endpoint}")
        updater = IncrementalOntologyUpdater(endpoint)
        print(f"   Result: {updater.fuseki_update}")
    # FIXED: Test with Fuseki endpoint instead of Blazegraph
    fuseki_endpoint = "http://167.172.143.162:3030/treekipedia"
    
    updater = IncrementalOntologyUpdater(fuseki_endpoint)
    
    # Check current state
    current_state = updater.get_current_ontology_state()
    print(f"Current ontology state: {current_state}")