#!/usr/bin/env python3
"""
Auto-sync PostgreSQL insights to Fuseki SPARQL endpoint.

This script monitors the PostgreSQL insights table and syncs new insights
to Fuseki in real-time or on a schedule.

Can be run as:
1. A daemon that watches for changes
2. A cron job that runs periodically
3. Called after each research session

Usage:
    python fuseki_auto_sync.py --daemon           # Run as background service
    python fuseki_auto_sync.py --once             # Single sync run
    python fuseki_auto_sync.py --watch            # Watch for changes
    python fuseki_auto_sync.py --full-reload      # Clear and reload all data

Environment:
    PROD_DB_HOST, PROD_DB_PASSWORD  - PostgreSQL connection
    FUSEKI_URL, FUSEKI_PASSWORD     - Fuseki connection
"""

import os
import sys
import json
import time
import signal
import argparse
import logging
from datetime import datetime, timedelta
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DB_CONFIG = {
    'host': os.environ.get('PROD_DB_HOST', os.environ.get('DB_HOST', 'localhost')),
    'port': os.environ.get('PROD_DB_PORT', os.environ.get('DB_PORT', '5432')),
    'database': os.environ.get('PROD_DB_NAME', os.environ.get('DB_NAME', 'treekipedia')),
    'user': os.environ.get('PROD_DB_USER', os.environ.get('DB_USER', 'postgres')),
    'password': os.environ.get('PROD_DB_PASSWORD', os.environ.get('DB_PASSWORD', ''))
}

FUSEKI_CONFIG = {
    'base_url': os.environ.get('FUSEKI_URL', 'http://167.172.143.162:3030'),
    'dataset': os.environ.get('FUSEKI_DATASET', 'treekipedia'),
    'user': os.environ.get('FUSEKI_USER', 'admin'),
    'password': os.environ.get('FUSEKI_PASSWORD', '')
}

SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL_SECONDS', '300'))  # 5 minutes default

# Track last sync time
LAST_SYNC_FILE = '/tmp/fuseki_last_sync.json'

# RDF Prefixes
PREFIXES = """
@prefix treekipedia: <https://treekipedia.silvi.earth/species/> .
@prefix tkp: <https://treekipedia.silvi.earth/ontology#> .
@prefix dwc: <http://rs.tdwg.org/dwc/terms/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix schema: <https://schema.org/> .
"""

# Signal handling for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("Shutdown signal received")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_last_sync_time() -> Optional[datetime]:
    """Get timestamp of last successful sync."""
    try:
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data['last_sync'])
    except Exception:
        pass
    return None


def save_last_sync_time(timestamp: datetime):
    """Save timestamp of successful sync."""
    try:
        with open(LAST_SYNC_FILE, 'w') as f:
            json.dump({'last_sync': timestamp.isoformat()}, f)
    except Exception as e:
        logger.warning(f"Failed to save sync timestamp: {e}")


def get_insights_since(since: Optional[datetime] = None) -> List[Dict]:
    """Get insights created or updated since timestamp."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if since:
                cur.execute("""
                    SELECT * FROM insights
                    WHERE created_at > %s OR updated_at > %s
                    ORDER BY created_at
                """, (since, since))
            else:
                cur.execute("SELECT * FROM insights ORDER BY created_at")
            return cur.fetchall()


def get_all_species_with_insights() -> List[Dict]:
    """Get all species that have been researched (have insights)."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT s.taxon_id, s.species_scientific_name,
                       s.common_name, s.family, s.genus
                FROM species s
                INNER JOIN insights i ON s.taxon_id = i.taxon_id
            """)
            return cur.fetchall()


def escape_turtle(s: str) -> str:
    """Escape string for Turtle."""
    if s is None:
        return '""'
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "\\r")
    return f'"{s}"'


def insight_to_turtle(insight: Dict) -> str:
    """Convert insight to Turtle RDF."""
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

    if isinstance(claim_value, dict):
        claim_text = claim_value.get('text', json.dumps(claim_value))
    else:
        claim_text = str(claim_value) if claim_value else ""

    lines = []
    lines.append(f"{species_uri} tkp:{claim_type} {escape_turtle(claim_text)} .")
    lines.append(f"{insight_uri} a tkp:Insight ;")
    lines.append(f"    tkp:aboutSpecies {species_uri} ;")
    lines.append(f"    tkp:claimType {escape_turtle(claim_type)} ;")
    lines.append(f"    tkp:confidence \"{confidence}\"^^xsd:decimal ;")
    lines.append(f"    prov:wasGeneratedBy {escape_turtle(model)} ;")

    if created_at:
        iso = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
        lines.append(f"    dcterms:created \"{iso}\"^^xsd:dateTime ;")

    source_uris = []
    source_triples = []
    if sources:
        for i, src in enumerate(sources if isinstance(sources, list) else []):
            src_uri = f"<https://treekipedia.silvi.earth/ontology#source_{quote(insight_id)}_{i}>"
            source_uris.append(src_uri)
            source_triples.extend([
                f"{src_uri} a tkp:Source ;",
                f"    schema:url {escape_turtle(src.get('url', ''))} ;",
                f"    dcterms:title {escape_turtle(src.get('title', ''))} ;",
                f"    tkp:credibility \"{src.get('credibility', 0.0)}\"^^xsd:decimal ."
            ])

    for src_uri in source_uris:
        lines.append(f"    dcterms:source {src_uri} ;")

    if lines[-1].endswith(";"):
        lines[-1] = lines[-1][:-1] + "."

    lines.extend(source_triples)
    return "\n".join(lines)


def species_to_turtle(species: Dict) -> str:
    """Convert species basic info to Turtle RDF."""
    taxon_id = species['taxon_id']
    species_uri = f"treekipedia:{quote(taxon_id)}"

    lines = [f"{species_uri} a tkp:Species ;"]

    if species.get('species_scientific_name'):
        lines.append(f"    dwc:scientificName {escape_turtle(species['species_scientific_name'])} ;")
    if species.get('common_name'):
        lines.append(f"    dwc:vernacularName {escape_turtle(species['common_name'])} ;")
    if species.get('family'):
        lines.append(f"    dwc:family {escape_turtle(species['family'])} ;")
    if species.get('genus'):
        lines.append(f"    dwc:genus {escape_turtle(species['genus'])} ;")

    if lines[-1].endswith(";"):
        lines[-1] = lines[-1][:-1] + "."

    return "\n".join(lines)


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
    response = requests.post(
        f"{base_url}/data?default",
        data=turtle_data.encode('utf-8'),
        headers={'Content-Type': 'text/turtle'},
        auth=auth,
        timeout=120
    )

    if response.status_code in (200, 201):
        result = response.json() if response.text else {}
        logger.info(f"Uploaded {result.get('tripleCount', '?')} triples to Fuseki")
        return True
    else:
        logger.error(f"Fuseki upload failed: {response.status_code} - {response.text[:200]}")
        return False


def sync_incremental():
    """Sync only new/updated insights since last sync."""
    last_sync = get_last_sync_time()
    logger.info(f"Last sync: {last_sync or 'never'}")

    insights = get_insights_since(last_sync)
    if not insights:
        logger.info("No new insights to sync")
        return True

    logger.info(f"Syncing {len(insights)} new insights")

    turtle_lines = [PREFIXES]
    for insight in insights:
        turtle_lines.append(insight_to_turtle(insight))
        turtle_lines.append("")

    success = upload_to_fuseki("\n".join(turtle_lines))
    if success:
        save_last_sync_time(datetime.now())

    return success


def sync_full_reload():
    """Clear Fuseki and reload all data."""
    logger.info("Performing full reload...")

    # Get all data
    insights = get_insights_since(None)
    species_list = get_all_species_with_insights()

    logger.info(f"Loading {len(species_list)} species and {len(insights)} insights")

    turtle_lines = [PREFIXES]

    # Add species
    for species in species_list:
        turtle_lines.append(species_to_turtle(species))
        turtle_lines.append("")

    # Add insights
    for insight in insights:
        turtle_lines.append(insight_to_turtle(insight))
        turtle_lines.append("")

    success = upload_to_fuseki("\n".join(turtle_lines), clear_first=True)
    if success:
        save_last_sync_time(datetime.now())
        logger.info("Full reload complete")

    return success


def run_daemon():
    """Run as a daemon, syncing periodically."""
    logger.info(f"Starting Fuseki sync daemon (interval: {SYNC_INTERVAL}s)")

    while not shutdown_requested:
        try:
            sync_incremental()
        except Exception as e:
            logger.error(f"Sync error: {e}")

        # Sleep in small increments to allow graceful shutdown
        for _ in range(SYNC_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Daemon stopped")


def main():
    parser = argparse.ArgumentParser(description='Sync PostgreSQL to Fuseki')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--once', action='store_true', help='Single incremental sync')
    parser.add_argument('--full-reload', action='store_true', help='Clear and reload all')
    parser.add_argument('--status', action='store_true', help='Show sync status')

    args = parser.parse_args()

    if args.status:
        last_sync = get_last_sync_time()
        insights = get_insights_since(last_sync)
        print(json.dumps({
            'last_sync': last_sync.isoformat() if last_sync else None,
            'pending_insights': len(insights),
            'fuseki_url': FUSEKI_CONFIG['base_url'],
            'db_host': DB_CONFIG['host']
        }, indent=2))
        return

    if args.full_reload:
        sync_full_reload()
    elif args.daemon:
        run_daemon()
    elif args.once:
        sync_incremental()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
