#!/usr/bin/env python3
"""
Sync species data from PostgreSQL to Fuseki with targeted columns
for: taxonomic hierarchy, species traits, native range, ecological relationships,
agroforestry, and carbon-related data.
"""

import psycopg2
import requests
from datetime import datetime
import time
import sys

# Config
postgres_config = {
    'host': '167.172.143.162',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': '9353jeremic',
    'port': 5432
}
fuseki_data = 'http://167.172.143.162:3030/treekipedia/data'
fuseki_auth = ('treekipedia', 'treekipedia@silvi')

# Target columns matching user requirements
TARGET_COLUMNS = [
    # ID and basic info
    'taxon_id', 'species_scientific_name', 'accepted_scientific_name', 'common_name',

    # Taxonomic hierarchy
    'family', 'genus', 'class', 'taxonomic_order', 'subspecies',

    # Species traits
    'maximum_height_ai', 'maximum_height_human', 'maximum_diameter_ai', 'maximum_diameter_human',
    'growth_form_ai', 'growth_form_human', 'leaf_type_ai', 'leaf_type_human',
    'bark_characteristics_ai', 'bark_characteristics_human', 'tolerances',

    # Native range / Ecoregions
    'ecoregions', 'bioregions', 'biomes', 'countries_native', 'countries_introduced',
    'countries_invasive', 'habitat_ai', 'habitat_human', 'native_adapted_habitats_ai',
    'native_adapted_habitats_human', 'wcvp_native', 'wcvp_introduced',

    # Ecological relationships
    'ecological_function_ai', 'ecological_function_human', 'compatible_soil_types_ai',
    'compatible_soil_types_human', 'elevation_ranges_ai', 'elevation_ranges_human',
    'soil_texture_all', 'soil_texture_dominant', 'soil_texture_prefered', 'soil_texture_tolerated',
    'ph_all', 'ph_dominant', 'ph_prefered', 'ph_tolerated',
    'climate_type_koppengeiger', 'annual_temperature_range_c', 'annual_precipitation_mm',

    # Agroforestry
    'agroforestry_use_cases_ai', 'agroforestry_use_cases_human',
    'timber_value', 'non_timber_products', 'fruit_type_ai', 'fruit_type_human',

    # Carbon related (allometric for calculations)
    'allometric_models', 'allometric_curve',

    # Associated species (ecological relationships)
    'associated_species'
]


def escape_rdf_string(value):
    """Escape special characters for RDF N-Triples format"""
    if value is None:
        return None
    s = str(value)
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    return s


def main():
    print("=" * 60)
    print("SPECIES TO FUSEKI SYNC")
    print("=" * 60)
    print(f"Target: PostgreSQL -> Apache Jena Fuseki")
    print(f"Columns: {len(TARGET_COLUMNS)} targeted fields")
    print()

    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**postgres_config)
    cursor = conn.cursor()

    # Get total count
    cursor.execute('SELECT COUNT(*) FROM species')
    total_rows = cursor.fetchone()[0]
    print(f"Total species rows: {total_rows:,}")

    # Check which columns exist
    cursor.execute('''
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'species' AND table_schema = 'public'
    ''')
    existing_cols = set(row[0] for row in cursor.fetchall())
    valid_columns = [c for c in TARGET_COLUMNS if c in existing_cols]
    missing_columns = [c for c in TARGET_COLUMNS if c not in existing_cols]

    print(f"Valid target columns: {len(valid_columns)} of {len(TARGET_COLUMNS)}")
    if missing_columns:
        print(f"Missing columns: {', '.join(missing_columns)}")
    print()

    # Process in batches
    batch_size = 5000
    offset = 0
    total_triples = 0
    batch_num = 0
    total_records = 0
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"Starting full sync of {total_rows:,} species records...")
    print(f"Batch size: {batch_size:,}")
    print()

    sync_start = time.time()

    while offset < total_rows:
        batch_num += 1
        start_time = time.time()

        # Fetch batch
        cols_str = ', '.join(valid_columns)
        query = f'''
            SELECT {cols_str}
            FROM species
            ORDER BY taxon_id
            OFFSET {offset} LIMIT {batch_size}
        '''
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            break

        # Convert to RDF
        rdf_triples = []
        for row in rows:
            record = dict(zip(valid_columns, row))
            entity_id = record.get('taxon_id') or f'gen_{offset}'
            entity_uri = f'<http://treekipedia.org/species/{entity_id}>'

            # Type declaration
            rdf_triples.append(f'{entity_uri} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://treekipedia.org/ontology/Species> .')

            for col, value in record.items():
                if value is not None and str(value).strip():
                    prop_uri = f'<http://treekipedia.org/property/{col}>'
                    escaped = escape_rdf_string(value)
                    rdf_triples.append(f'{entity_uri} {prop_uri} "{escaped}" .')

        rdf_content = '\n'.join(rdf_triples)

        # Upload to Fuseki
        graph_uri = f'http://treekipedia.org/species/{timestamp}_batch_{batch_num}'
        try:
            response = requests.put(
                fuseki_data,
                data=rdf_content.encode('utf-8'),
                headers={'Content-Type': 'application/n-triples; charset=utf-8'},
                params={'graph': graph_uri},
                auth=fuseki_auth,
                timeout=300
            )

            batch_triples = len(rdf_triples)
            total_triples += batch_triples
            total_records += len(rows)
            elapsed = time.time() - start_time

            if response.status_code in [200, 201, 204]:
                pct = (offset + len(rows)) / total_rows * 100
                print(f"✅ Batch {batch_num}: {len(rows):,} records, {batch_triples:,} triples ({elapsed:.1f}s) - {pct:.1f}%")
                sys.stdout.flush()
            else:
                print(f"❌ Batch {batch_num} failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                break

        except Exception as e:
            print(f"❌ Batch {batch_num} error: {e}")
            break

        offset += batch_size

    cursor.close()
    conn.close()

    total_time = time.time() - sync_start

    print()
    print("=" * 60)
    print("SYNC COMPLETE!")
    print("=" * 60)
    print(f"Records synced: {total_records:,}")
    print(f"Total triples: {total_triples:,}")
    print(f"Time elapsed: {total_time:.1f} seconds")
    print(f"Fuseki endpoint: http://167.172.143.162:3030/treekipedia/sparql")


if __name__ == '__main__':
    main()
