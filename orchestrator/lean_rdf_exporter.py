#!/usr/bin/env python3
"""
Lean RDF Exporter for Treekipedia
=================================
Exports insights to RDF/Turtle format for Fuseki SPARQL endpoint.

LEAN means: Facts only, no provenance bloat.
- Each insight becomes ONE triple (subject-predicate-object)
- Provenance stays in PostgreSQL, linked via API

Example output:
    treekipedia:ginkgo-biloba
        tkp:cultural_significance "Sacred in Buddhism - monks preserved species" ;
        tkp:cultural_significance "Six trees survived Hiroshima atomic bomb" ;
        tkp:common_name "Ginkgo" ;
        tkp:common_name "Maidenhair Tree" ;
        dwc:scientificName "Ginkgo biloba" ;
        dwc:family "Ginkgoaceae" .

Usage:
    python lean_rdf_exporter.py --export           # Export all to stdout
    python lean_rdf_exporter.py --export --file    # Export to file
    python lean_rdf_exporter.py --upload           # Export and upload to Fuseki
    python lean_rdf_exporter.py --species TAXON_ID # Export single species
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Run: pip3 install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip3 install requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'treekipedia'),
    'user': os.environ.get('DB_USER', os.environ.get('USER', 'postgres')),
    'password': os.environ.get('DB_PASSWORD', '')
}

FUSEKI_CONFIG = {
    'base_url': os.environ.get('FUSEKI_URL', 'http://167.172.143.162:3030'),
    'dataset': os.environ.get('FUSEKI_DATASET', 'treekipedia'),
    'user': os.environ.get('FUSEKI_USER', 'admin'),
    'password': os.environ.get('FUSEKI_PASSWORD', '')
}

# ============================================================================
# RDF PREFIXES
# ============================================================================

PREFIXES = """@prefix treekipedia: <https://treekipedia.silvi.earth/species/> .
@prefix tkp: <https://treekipedia.silvi.earth/ontology#> .
@prefix dwc: <http://rs.tdwg.org/dwc/terms/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

"""

# ============================================================================
# PREDICATE MAPPING
# ============================================================================

# Map claim_types to RDF predicates
CLAIM_TYPE_TO_PREDICATE = {
    # Identity
    'popular_common_name': 'dwc:vernacularName',
    'etymology': 'tkp:etymology',
    'synonyms': 'dwc:scientificNameAuthorship',
    'identification_features': 'tkp:identificationFeatures',

    # Ecological
    'general_description': 'dcterms:description',
    'habitat': 'dwc:habitat',
    'elevation_ranges': 'tkp:elevationRange',
    'ecological_function': 'tkp:ecologicalFunction',
    'native_adapted_habitats': 'tkp:nativeHabitat',
    'conservation_status': 'dwc:establishmentMeans',  # or iucn:redListCategory
    'compatible_soil_types': 'tkp:soilPreference',
    'climate_tolerance': 'tkp:climateTolerance',
    'tolerances': 'tkp:tolerance',
    'associated_species': 'tkp:associatedSpecies',

    # Morphological
    'growth_form': 'tkp:growthForm',
    'leaf_type': 'tkp:leafType',
    'deciduous_evergreen': 'tkp:leafPhenology',
    'flower_color': 'tkp:flowerColor',
    'fruit_type': 'tkp:fruitType',
    'bark_characteristics': 'tkp:barkCharacteristics',
    'maximum_height': 'tkp:maximumHeight',
    'maximum_diameter': 'tkp:maximumDiameter',
    'lifespan': 'tkp:lifespan',
    'maximum_tree_age': 'tkp:maximumAge',

    # Stewardship
    'stewardship_best_practices': 'tkp:stewardshipPractice',
    'planting_recipes': 'tkp:plantingMethod',
    'pruning_maintenance': 'tkp:pruningGuidance',
    'disease_pest_management': 'tkp:pestManagement',
    'fire_management': 'tkp:fireManagement',
    'propagation_methods': 'tkp:propagationMethod',
    'cultural_significance': 'tkp:culturalSignificance',
    'agroforestry_use_cases': 'tkp:agroforestryUse',
    'timber_value': 'tkp:timberValue',
    'non_timber_products': 'tkp:nonTimberProduct',
    'nutritional_caloric_value': 'tkp:nutritionalValue',
}

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_species_with_insights() -> List[Dict]:
    """Get all species that have insights."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT
                    s.taxon_id,
                    s.species_scientific_name,
                    s.family,
                    s.genus
                FROM species s
                INNER JOIN insights i ON s.taxon_id = i.taxon_id
                WHERE i.is_current = TRUE
                ORDER BY s.species_scientific_name
            """)
            return cur.fetchall()


def get_insights_for_species(taxon_id: str) -> List[Dict]:
    """Get all current insights for a species."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id,
                    claim_type,
                    claim_value,
                    confidence
                FROM insights
                WHERE taxon_id = %s AND is_current = TRUE
                ORDER BY claim_type, confidence DESC
            """, (taxon_id,))
            return cur.fetchall()


def get_all_current_insights() -> List[Dict]:
    """Get all current insights with species info."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    i.id,
                    i.taxon_id,
                    i.claim_type,
                    i.claim_value,
                    i.confidence,
                    s.species_scientific_name,
                    s.family,
                    s.genus
                FROM insights i
                JOIN species s ON i.taxon_id = s.taxon_id
                WHERE i.is_current = TRUE
                ORDER BY s.species_scientific_name, i.claim_type
            """)
            return cur.fetchall()


# ============================================================================
# RDF CONVERSION
# ============================================================================

def escape_turtle_string(s: str) -> str:
    """Escape string for Turtle format."""
    if s is None:
        return '""'
    s = str(s)
    # Escape backslashes first, then quotes and newlines
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return f'"{s}"'


def extract_text_value(claim_value: dict) -> str:
    """Extract displayable text from claim_value JSONB."""
    if isinstance(claim_value, str):
        return claim_value

    # Try common fields in order of preference
    for field in ['text', 'name', 'primary', 'value', 'iucn_status', 'type', 'category']:
        if field in claim_value and claim_value[field]:
            val = claim_value[field]
            # Add unit if present
            if field == 'value' and 'unit' in claim_value:
                return f"{val} {claim_value['unit']}"
            return str(val)

    # Fallback: stringify the whole thing
    return json.dumps(claim_value)


def species_to_turtle(species: Dict, insights: List[Dict]) -> str:
    """Convert a species and its insights to Turtle format."""
    taxon_id = species['taxon_id']
    scientific_name = species['species_scientific_name']
    family = species.get('family')
    genus = species.get('genus')

    # Create URI-safe taxon ID
    species_uri = f"treekipedia:{quote(taxon_id, safe='')}"

    lines = [f"{species_uri} a tkp:Species ;"]

    # Add taxonomy
    if scientific_name:
        lines.append(f"    dwc:scientificName {escape_turtle_string(scientific_name)} ;")
    if family:
        lines.append(f"    dwc:family {escape_turtle_string(family)} ;")
    if genus:
        lines.append(f"    dwc:genus {escape_turtle_string(genus)} ;")

    # Add insights as triples
    for insight in insights:
        claim_type = insight['claim_type']
        claim_value = insight['claim_value']

        # Get predicate
        predicate = CLAIM_TYPE_TO_PREDICATE.get(claim_type, f"tkp:{claim_type}")

        # Extract text value
        text = extract_text_value(claim_value)

        if text:
            lines.append(f"    {predicate} {escape_turtle_string(text)} ;")

    # Close the statement (replace last ; with .)
    if lines[-1].endswith(";"):
        lines[-1] = lines[-1][:-1] + "."

    return "\n".join(lines)


def generate_lean_rdf(taxon_id: Optional[str] = None) -> str:
    """Generate lean RDF for all species or a single species."""
    turtle_parts = [PREFIXES]

    if taxon_id:
        # Single species
        species_list = get_species_with_insights()
        species = next((s for s in species_list if s['taxon_id'] == taxon_id), None)
        if not species:
            logger.error(f"Species not found or has no insights: {taxon_id}")
            return ""
        insights = get_insights_for_species(taxon_id)
        turtle_parts.append(species_to_turtle(species, insights))
    else:
        # All species
        species_list = get_species_with_insights()
        logger.info(f"Exporting {len(species_list)} species with insights")

        for species in species_list:
            insights = get_insights_for_species(species['taxon_id'])
            if insights:
                turtle_parts.append(species_to_turtle(species, insights))
                turtle_parts.append("")  # Blank line between species

    return "\n".join(turtle_parts)


# ============================================================================
# FUSEKI UPLOAD
# ============================================================================

def upload_to_fuseki(turtle_data: str, clear_first: bool = False) -> bool:
    """Upload Turtle data to Fuseki."""
    if not FUSEKI_CONFIG['password']:
        logger.error("FUSEKI_PASSWORD not set")
        return False

    auth = (FUSEKI_CONFIG['user'], FUSEKI_CONFIG['password'])
    base_url = f"{FUSEKI_CONFIG['base_url']}/{FUSEKI_CONFIG['dataset']}"

    # Optionally clear existing data
    if clear_first:
        logger.info("Clearing existing data from Fuseki...")
        response = requests.post(
            f"{base_url}/update",
            data="CLEAR ALL",
            headers={'Content-Type': 'application/sparql-update'},
            auth=auth,
            timeout=60
        )
        if response.status_code not in (200, 204):
            logger.error(f"Failed to clear Fuseki: {response.status_code}")
            return False

    # Upload new data
    logger.info("Uploading to Fuseki...")
    response = requests.post(
        f"{base_url}/data?default",
        data=turtle_data.encode('utf-8'),
        headers={'Content-Type': 'text/turtle'},
        auth=auth,
        timeout=120
    )

    if response.status_code in (200, 201):
        try:
            result = response.json() if response.text else {}
            logger.info(f"Uploaded {result.get('tripleCount', '?')} triples to Fuseki")
        except:
            logger.info("Upload successful")
        return True
    else:
        logger.error(f"Fuseki upload failed: {response.status_code} - {response.text[:200]}")
        return False


def get_fuseki_stats() -> Dict:
    """Get statistics from Fuseki."""
    if not FUSEKI_CONFIG['password']:
        return {'error': 'FUSEKI_PASSWORD not set'}

    auth = (FUSEKI_CONFIG['user'], FUSEKI_CONFIG['password'])
    url = f"{FUSEKI_CONFIG['base_url']}/{FUSEKI_CONFIG['dataset']}/sparql"

    # Count triples
    try:
        response = requests.get(
            url,
            params={'query': 'SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'},
            headers={'Accept': 'application/sparql-results+json'},
            auth=auth,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            triple_count = int(result['results']['bindings'][0]['count']['value'])
        else:
            triple_count = 'error'
    except Exception as e:
        triple_count = f'error: {e}'

    # Count species
    try:
        response = requests.get(
            url,
            params={'query': 'SELECT (COUNT(DISTINCT ?s) as ?count) WHERE { ?s a <https://treekipedia.silvi.earth/ontology#Species> }'},
            headers={'Accept': 'application/sparql-results+json'},
            auth=auth,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            species_count = int(result['results']['bindings'][0]['count']['value'])
        else:
            species_count = 'error'
    except Exception as e:
        species_count = f'error: {e}'

    return {
        'fuseki_url': FUSEKI_CONFIG['base_url'],
        'dataset': FUSEKI_CONFIG['dataset'],
        'triple_count': triple_count,
        'species_count': species_count
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Lean RDF Exporter for Treekipedia')
    parser.add_argument('--export', action='store_true', help='Export RDF to stdout')
    parser.add_argument('--file', type=str, help='Export to file instead of stdout')
    parser.add_argument('--upload', action='store_true', help='Upload to Fuseki')
    parser.add_argument('--clear', action='store_true', help='Clear Fuseki before upload')
    parser.add_argument('--species', type=str, help='Export single species by taxon_id')
    parser.add_argument('--stats', action='store_true', help='Show Fuseki statistics')

    args = parser.parse_args()

    if args.stats:
        stats = get_fuseki_stats()
        print(json.dumps(stats, indent=2))
        return

    if not any([args.export, args.upload]):
        parser.print_help()
        return

    # Generate RDF
    turtle_data = generate_lean_rdf(args.species)

    if not turtle_data:
        logger.error("No data to export")
        return

    # Output
    if args.export:
        if args.file:
            with open(args.file, 'w') as f:
                f.write(turtle_data)
            logger.info(f"Exported to {args.file}")
        else:
            print(turtle_data)

    # Upload
    if args.upload:
        success = upload_to_fuseki(turtle_data, clear_first=args.clear)
        if success:
            logger.info("Upload complete")
            stats = get_fuseki_stats()
            print(json.dumps(stats, indent=2))
        else:
            logger.error("Upload failed")
            sys.exit(1)


if __name__ == '__main__':
    main()
