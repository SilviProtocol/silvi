#!/usr/bin/env python3
"""
Sync local insights to production database and Fuseki SPARQL endpoint.

This script:
1. Pushes new insights from local PostgreSQL to production PostgreSQL
2. Optionally syncs insights to production Fuseki as RDF triples

Environment variables required:
- LOCAL_DB_HOST, LOCAL_DB_NAME, LOCAL_DB_USER, LOCAL_DB_PASSWORD
- PROD_DB_HOST, PROD_DB_NAME, PROD_DB_USER, PROD_DB_PASSWORD
- FUSEKI_URL, FUSEKI_DATASET, FUSEKI_USER, FUSEKI_PASSWORD (optional)

Usage:
    python sync_insights.py --to-production    # Sync to prod PostgreSQL
    python sync_insights.py --to-fuseki        # Sync to Fuseki
    python sync_insights.py --all              # Both
    python sync_insights.py --status           # Check sync status
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import quote

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, execute_values
except ImportError:
    print("Error: psycopg2 not installed. Run: pip3 install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip3 install requests")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
LOCAL_DB_CONFIG = {
    'host': os.environ.get('LOCAL_DB_HOST', 'localhost'),
    'port': os.environ.get('LOCAL_DB_PORT', '5432'),
    'database': os.environ.get('LOCAL_DB_NAME', 'treekipedia'),
    'user': os.environ.get('LOCAL_DB_USER', os.environ.get('USER', 'postgres')),
    'password': os.environ.get('LOCAL_DB_PASSWORD', '')
}

PROD_DB_CONFIG = {
    'host': os.environ.get('PROD_DB_HOST', '167.172.143.162'),
    'port': os.environ.get('PROD_DB_PORT', '5432'),
    'database': os.environ.get('PROD_DB_NAME', 'treekipedia'),
    'user': os.environ.get('PROD_DB_USER', 'postgres'),
    'password': os.environ.get('PROD_DB_PASSWORD', '')
}

FUSEKI_CONFIG = {
    'base_url': os.environ.get('FUSEKI_URL', 'http://167.172.143.162:3030'),
    'dataset': os.environ.get('FUSEKI_DATASET', 'treekipedia'),
    'user': os.environ.get('FUSEKI_USER', 'admin'),
    'password': os.environ.get('FUSEKI_PASSWORD', '')
}

# RDF namespace prefixes
PREFIXES = """
@prefix treekipedia: <https://treekipedia.silvi.earth/species/> .
@prefix tkp: <https://treekipedia.silvi.earth/ontology#> .
@prefix dwc: <http://rs.tdwg.org/dwc/terms/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix schema: <https://schema.org/> .
"""


def get_local_connection():
    """Get connection to local database."""
    return psycopg2.connect(**LOCAL_DB_CONFIG)


def get_prod_connection():
    """Get connection to production database."""
    if not PROD_DB_CONFIG['password']:
        raise ValueError("PROD_DB_PASSWORD environment variable required")
    return psycopg2.connect(**PROD_DB_CONFIG)


def get_unsynced_insights(local_conn, prod_conn) -> List[Dict]:
    """Get insights that exist locally but not in production."""
    with local_conn.cursor(cursor_factory=RealDictCursor) as local_cur:
        local_cur.execute("SELECT id FROM insights ORDER BY created_at")
        local_ids = {row['id'] for row in local_cur.fetchall()}

    with prod_conn.cursor(cursor_factory=RealDictCursor) as prod_cur:
        prod_cur.execute("SELECT id FROM insights")
        prod_ids = {row['id'] for row in prod_cur.fetchall()}

    new_ids = local_ids - prod_ids

    if not new_ids:
        return []

    with local_conn.cursor(cursor_factory=RealDictCursor) as local_cur:
        placeholders = ','.join(['%s'] * len(new_ids))
        local_cur.execute(f"""
            SELECT * FROM insights
            WHERE id IN ({placeholders})
            ORDER BY created_at
        """, list(new_ids))
        return local_cur.fetchall()


def sync_insights_to_production(insights: List[Dict], prod_conn) -> int:
    """Insert insights into production database."""
    if not insights:
        return 0

    columns = [
        'id', 'taxon_id', 'claim_type', 'claim_value', 'confidence',
        'methodology', 'sources', 'model_version', 'agent_type',
        'version', 'research_session_id', 'created_at', 'updated_at',
        'corroboration', 'confidence_breakdown'
    ]

    with prod_conn.cursor() as cur:
        values = []
        for insight in insights:
            row = []
            for col in columns:
                val = insight.get(col)
                if col in ['claim_value', 'sources', 'corroboration', 'confidence_breakdown']:
                    val = json.dumps(val) if val else None
                row.append(val)
            values.append(tuple(row))

        insert_sql = f"""
            INSERT INTO insights ({', '.join(columns)})
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """
        execute_values(cur, insert_sql, values)
        prod_conn.commit()

    return len(insights)


def sync_species_ai_fields(prod_conn, taxon_ids: List[str]) -> int:
    """Sync _ai fields from insights to species table."""
    updated = 0

    with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
        for taxon_id in taxon_ids:
            # Get latest insights for this species
            cur.execute("""
                SELECT DISTINCT ON (claim_type)
                    claim_type, claim_value
                FROM insights
                WHERE taxon_id = %s
                ORDER BY claim_type, version DESC, created_at DESC
            """, (taxon_id,))

            insights = cur.fetchall()
            if not insights:
                continue

            # Build update for species table
            updates = []
            values = []
            for insight in insights:
                claim_type = insight['claim_type']
                claim_value = insight['claim_value']

                # Extract text value
                if isinstance(claim_value, dict):
                    text_value = claim_value.get('text', str(claim_value))
                else:
                    text_value = str(claim_value)

                ai_column = f"{claim_type}_ai"
                updates.append(f"{ai_column} = %s")
                values.append(text_value)

            if updates:
                values.append(taxon_id)
                cur.execute(f"""
                    UPDATE species
                    SET {', '.join(updates)}, researched = TRUE
                    WHERE taxon_id = %s
                """, values)
                updated += 1

        prod_conn.commit()

    return updated


def escape_turtle_string(s: str) -> str:
    """Escape string for Turtle format."""
    if s is None:
        return '""'
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return f'"{s}"'


def insight_to_turtle(insight: Dict) -> str:
    """Convert insight to Turtle RDF triples."""
    taxon_id = insight['taxon_id']
    claim_type = insight['claim_type']
    claim_value = insight['claim_value']
    confidence = insight.get('confidence', 0.0)
    sources = insight.get('sources', [])
    model = insight.get('model_version', 'unknown')
    created_at = insight.get('created_at')
    insight_id = str(insight['id'])

    species_uri = f"treekipedia:{quote(taxon_id)}"
    insight_uri = f"<https://treekipedia.silvi.earth/ontology#insight_{quote(insight_id)}>"

    # Extract text from claim_value
    if isinstance(claim_value, dict):
        claim_text = claim_value.get('text', str(claim_value))
    else:
        claim_text = str(claim_value)

    lines = []

    # Main assertion
    lines.append(f"{species_uri} tkp:{claim_type} {escape_turtle_string(claim_text)} .")

    # Insight metadata
    lines.append(f"{insight_uri} a tkp:Insight ;")
    lines.append(f"    tkp:aboutSpecies {species_uri} ;")
    lines.append(f"    tkp:claimType {escape_turtle_string(claim_type)} ;")
    lines.append(f"    tkp:confidence \"{confidence}\"^^xsd:decimal ;")
    lines.append(f"    prov:wasGeneratedBy {escape_turtle_string(model)} ;")

    if created_at:
        iso_date = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
        lines.append(f"    dcterms:created \"{iso_date}\"^^xsd:dateTime ;")

    # Sources
    source_uris = []
    source_triples = []
    if sources and isinstance(sources, list):
        for i, source in enumerate(sources):
            source_uri = f"<https://treekipedia.silvi.earth/ontology#source_{quote(insight_id)}_{i}>"
            source_uris.append(source_uri)

            url = source.get('url', '')
            title = source.get('title', '')
            credibility = source.get('credibility', 0.0)

            source_triples.append(f"{source_uri} a tkp:Source ;")
            source_triples.append(f"    schema:url {escape_turtle_string(url)} ;")
            source_triples.append(f"    dcterms:title {escape_turtle_string(title)} ;")
            source_triples.append(f"    tkp:credibility \"{credibility}\"^^xsd:decimal .")

    for source_uri in source_uris:
        lines.append(f"    dcterms:source {source_uri} ;")

    # Close insight statement
    if lines[-1].endswith(";"):
        lines[-1] = lines[-1][:-1] + "."

    lines.extend(source_triples)

    return "\n".join(lines)


def sync_to_fuseki(insights: List[Dict]) -> int:
    """Upload insights to Fuseki SPARQL endpoint."""
    if not insights:
        return 0

    if not FUSEKI_CONFIG['password']:
        logger.warning("FUSEKI_PASSWORD not set, skipping Fuseki sync")
        return 0

    # Build Turtle document
    turtle_lines = [PREFIXES]
    for insight in insights:
        turtle_lines.append(insight_to_turtle(insight))
        turtle_lines.append("")  # Blank line between insights

    turtle_data = "\n".join(turtle_lines)

    # Upload to Fuseki
    url = f"{FUSEKI_CONFIG['base_url']}/{FUSEKI_CONFIG['dataset']}/data?default"
    auth = (FUSEKI_CONFIG['user'], FUSEKI_CONFIG['password'])

    response = requests.post(
        url,
        data=turtle_data.encode('utf-8'),
        headers={'Content-Type': 'text/turtle'},
        auth=auth,
        timeout=60
    )

    if response.status_code in (200, 201):
        result = response.json() if response.text else {}
        logger.info(f"Uploaded {result.get('tripleCount', len(insights))} triples to Fuseki")
        return len(insights)
    else:
        logger.error(f"Fuseki upload failed: {response.status_code} - {response.text}")
        return 0


def get_sync_status():
    """Get current sync status between local and production."""
    status = {
        'timestamp': datetime.now().isoformat(),
        'local_db': {'connected': False, 'insights_count': 0},
        'prod_db': {'connected': False, 'insights_count': 0},
        'fuseki': {'connected': False, 'triples_count': 0},
        'unsynced_insights': 0
    }

    # Check local DB
    try:
        with get_local_connection() as conn:
            status['local_db']['connected'] = True
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM insights")
                status['local_db']['insights_count'] = cur.fetchone()[0]
    except Exception as e:
        status['local_db']['error'] = str(e)

    # Check prod DB
    try:
        with get_prod_connection() as conn:
            status['prod_db']['connected'] = True
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM insights")
                status['prod_db']['insights_count'] = cur.fetchone()[0]
    except Exception as e:
        status['prod_db']['error'] = str(e)

    # Calculate unsynced
    if status['local_db']['connected'] and status['prod_db']['connected']:
        status['unsynced_insights'] = (
            status['local_db']['insights_count'] -
            status['prod_db']['insights_count']
        )

    # Check Fuseki
    if FUSEKI_CONFIG['password']:
        try:
            url = f"{FUSEKI_CONFIG['base_url']}/{FUSEKI_CONFIG['dataset']}/sparql"
            response = requests.get(
                url,
                params={'query': 'SELECT (COUNT(*) as ?c) WHERE { ?s ?p ?o }'},
                headers={'Accept': 'application/sparql-results+json'},
                auth=(FUSEKI_CONFIG['user'], FUSEKI_CONFIG['password']),
                timeout=10
            )
            if response.status_code == 200:
                status['fuseki']['connected'] = True
                result = response.json()
                status['fuseki']['triples_count'] = int(
                    result['results']['bindings'][0]['c']['value']
                )
        except Exception as e:
            status['fuseki']['error'] = str(e)

    return status


def main():
    parser = argparse.ArgumentParser(
        description='Sync Treekipedia insights to production'
    )
    parser.add_argument('--to-production', action='store_true',
                        help='Sync insights to production PostgreSQL')
    parser.add_argument('--to-fuseki', action='store_true',
                        help='Sync insights to Fuseki SPARQL endpoint')
    parser.add_argument('--all', action='store_true',
                        help='Sync to both production DB and Fuseki')
    parser.add_argument('--status', action='store_true',
                        help='Show sync status')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be synced without doing it')

    args = parser.parse_args()

    if args.status:
        status = get_sync_status()
        print(json.dumps(status, indent=2))
        return

    if not any([args.to_production, args.to_fuseki, args.all]):
        parser.print_help()
        return

    sync_to_prod = args.to_production or args.all
    sync_to_sparql = args.to_fuseki or args.all

    try:
        local_conn = get_local_connection()
        logger.info("Connected to local database")
    except Exception as e:
        logger.error(f"Failed to connect to local database: {e}")
        return

    if sync_to_prod:
        try:
            prod_conn = get_prod_connection()
            logger.info("Connected to production database")

            # Get unsynced insights
            unsynced = get_unsynced_insights(local_conn, prod_conn)
            logger.info(f"Found {len(unsynced)} unsynced insights")

            if args.dry_run:
                print(f"Would sync {len(unsynced)} insights to production")
                for insight in unsynced[:5]:
                    print(f"  - {insight['taxon_id']}: {insight['claim_type']}")
                if len(unsynced) > 5:
                    print(f"  ... and {len(unsynced) - 5} more")
            else:
                if unsynced:
                    # Sync insights
                    synced = sync_insights_to_production(unsynced, prod_conn)
                    logger.info(f"Synced {synced} insights to production")

                    # Update species._ai fields
                    taxon_ids = list(set(i['taxon_id'] for i in unsynced))
                    updated = sync_species_ai_fields(prod_conn, taxon_ids)
                    logger.info(f"Updated {updated} species records")

                    # Optionally sync to Fuseki
                    if sync_to_sparql:
                        fuseki_count = sync_to_fuseki(unsynced)
                        logger.info(f"Synced {fuseki_count} insights to Fuseki")

            prod_conn.close()

        except Exception as e:
            logger.error(f"Production sync failed: {e}")

    elif sync_to_sparql:
        # Just sync to Fuseki from local
        with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM insights ORDER BY created_at")
            insights = cur.fetchall()

        if args.dry_run:
            print(f"Would sync {len(insights)} insights to Fuseki")
        else:
            fuseki_count = sync_to_fuseki(insights)
            logger.info(f"Synced {fuseki_count} insights to Fuseki")

    local_conn.close()
    logger.info("Sync complete")


if __name__ == '__main__':
    main()
