#!/usr/bin/env python3
"""
IPFS Version Archiver for Treekipedia
=====================================
Archives species research snapshots to IPFS for immutable provenance.

Each version creates:
- JSON file with all insights at that version
- Link to previous version (creating a chain)
- Stored via Lighthouse (existing integration)

Usage:
    python ipfs_archiver.py --archive TAXON_ID      # Archive single species
    python ipfs_archiver.py --archive-all           # Archive all researched species
    python ipfs_archiver.py --history TAXON_ID      # Show version history
    python ipfs_archiver.py --verify CID            # Verify archive integrity
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
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

# Lighthouse IPFS gateway (existing Treekipedia integration)
LIGHTHOUSE_CONFIG = {
    'api_key': os.environ.get('LIGHTHOUSE_API_KEY', ''),
    'upload_url': 'https://node.lighthouse.storage/api/v0/add',
    'gateway_url': 'https://gateway.lighthouse.storage/ipfs'
}

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_species_info(taxon_id: str) -> Optional[Dict]:
    """Get species basic info."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT taxon_id, species_scientific_name, family, genus,
                       research_version, researched
                FROM species
                WHERE taxon_id = %s
            """, (taxon_id,))
            return cur.fetchone()


def get_current_insights(taxon_id: str) -> List[Dict]:
    """Get all current insights for a species."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id::text as insight_id,
                    claim_type,
                    claim_value,
                    confidence,
                    methodology,
                    sources,
                    model_version,
                    agent_type,
                    version,
                    created_at
                FROM insights
                WHERE taxon_id = %s AND is_current = TRUE
                ORDER BY claim_type, created_at
            """, (taxon_id,))
            rows = cur.fetchall()
            # Convert datetime to ISO string
            for row in rows:
                if row.get('created_at'):
                    row['created_at'] = row['created_at'].isoformat()
            return [dict(r) for r in rows]


def get_previous_archive_cid(taxon_id: str) -> Optional[str]:
    """Get the CID of the most recent archive for this species."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ipfs_cid
                FROM research_archives
                WHERE taxon_id = %s
                ORDER BY archived_at DESC
                LIMIT 1
            """, (taxon_id,))
            row = cur.fetchone()
            return row['ipfs_cid'] if row else None


def save_archive_record(
    taxon_id: str,
    version: int,
    ipfs_cid: str,
    content_hash: str,
    insight_count: int,
    previous_cid: Optional[str]
) -> int:
    """Save archive record to database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO research_archives
                    (taxon_id, version, ipfs_cid, content_hash, insight_count, previous_cid, archived_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
            """, (taxon_id, version, ipfs_cid, content_hash, insight_count, previous_cid))
            result = cur.fetchone()
            conn.commit()
            return result[0]


def get_archive_history(taxon_id: str) -> List[Dict]:
    """Get archive history for a species."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    version,
                    ipfs_cid,
                    content_hash,
                    insight_count,
                    previous_cid,
                    archived_at
                FROM research_archives
                WHERE taxon_id = %s
                ORDER BY version DESC
            """, (taxon_id,))
            rows = cur.fetchall()
            for row in rows:
                if row.get('archived_at'):
                    row['archived_at'] = row['archived_at'].isoformat()
            return [dict(r) for r in rows]


def ensure_archive_table():
    """Create research_archives table if it doesn't exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS research_archives (
                    id SERIAL PRIMARY KEY,
                    taxon_id VARCHAR(50) NOT NULL,
                    version INTEGER NOT NULL,
                    ipfs_cid VARCHAR(100) NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    insight_count INTEGER NOT NULL,
                    previous_cid VARCHAR(100),
                    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(taxon_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_archives_taxon
                ON research_archives(taxon_id);

                CREATE INDEX IF NOT EXISTS idx_archives_cid
                ON research_archives(ipfs_cid);
            """)
            conn.commit()


# ============================================================================
# IPFS FUNCTIONS
# ============================================================================

def upload_to_lighthouse(data: dict) -> Optional[str]:
    """Upload JSON data to Lighthouse IPFS."""
    if not LIGHTHOUSE_CONFIG['api_key']:
        logger.warning("LIGHTHOUSE_API_KEY not set - using mock CID")
        # Generate mock CID for testing
        content_hash = hashlib.sha256(json.dumps(data).encode()).hexdigest()
        return f"Qm_mock_{content_hash[:32]}"

    try:
        json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')

        response = requests.post(
            LIGHTHOUSE_CONFIG['upload_url'],
            headers={'Authorization': f"Bearer {LIGHTHOUSE_CONFIG['api_key']}"},
            files={'file': ('archive.json', json_bytes, 'application/json')},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            cid = result.get('Hash') or result.get('cid')
            logger.info(f"Uploaded to IPFS: {cid}")
            return cid
        else:
            logger.error(f"Lighthouse upload failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"IPFS upload error: {e}")
        return None


def fetch_from_ipfs(cid: str) -> Optional[dict]:
    """Fetch archive from IPFS."""
    if cid.startswith('Qm_mock_'):
        logger.warning("Cannot fetch mock CID")
        return None

    try:
        url = f"{LIGHTHOUSE_CONFIG['gateway_url']}/{cid}"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"IPFS fetch failed: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"IPFS fetch error: {e}")
        return None


# ============================================================================
# ARCHIVE FUNCTIONS
# ============================================================================

def create_archive_document(taxon_id: str) -> Optional[Dict]:
    """Create archive document for a species."""
    species = get_species_info(taxon_id)
    if not species:
        logger.error(f"Species not found: {taxon_id}")
        return None

    if not species.get('researched'):
        logger.warning(f"Species not researched: {taxon_id}")
        return None

    insights = get_current_insights(taxon_id)
    if not insights:
        logger.warning(f"No insights for species: {taxon_id}")
        return None

    previous_cid = get_previous_archive_cid(taxon_id)
    version = (species.get('research_version') or 0) + 1

    # Create archive document
    archive = {
        'schema_version': '1.0',
        'archive_type': 'treekipedia_research',
        'taxon_id': taxon_id,
        'species_name': species['species_scientific_name'],
        'family': species.get('family'),
        'research_version': version,
        'archived_at': datetime.utcnow().isoformat() + 'Z',
        'insight_count': len(insights),
        'previous_version_cid': previous_cid,
        'insights': insights,
        'metadata': {
            'source': 'treekipedia',
            'api_url': f"https://treekipedia-api.silvi.earth/species/{taxon_id}",
            'provenance_api': f"https://treekipedia-api.silvi.earth/species/{taxon_id}/insights"
        }
    }

    # Calculate content hash
    content_for_hash = json.dumps(archive['insights'], sort_keys=True, default=str)
    archive['content_hash'] = hashlib.sha256(content_for_hash.encode()).hexdigest()

    return archive


def archive_species(taxon_id: str, dry_run: bool = False) -> Optional[str]:
    """Archive a species to IPFS."""
    ensure_archive_table()

    archive = create_archive_document(taxon_id)
    if not archive:
        return None

    if dry_run:
        print(json.dumps(archive, indent=2, default=str))
        return "DRY_RUN"

    # Upload to IPFS
    cid = upload_to_lighthouse(archive)
    if not cid:
        return None

    # Save record to database
    save_archive_record(
        taxon_id=taxon_id,
        version=archive['research_version'],
        ipfs_cid=cid,
        content_hash=archive['content_hash'],
        insight_count=archive['insight_count'],
        previous_cid=archive['previous_version_cid']
    )

    logger.info(f"Archived {taxon_id} v{archive['research_version']} -> {cid}")
    return cid


def archive_all_researched(dry_run: bool = False) -> List[Dict]:
    """Archive all researched species."""
    ensure_archive_table()

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT s.taxon_id
                FROM species s
                INNER JOIN insights i ON s.taxon_id = i.taxon_id
                WHERE i.is_current = TRUE
            """)
            species_ids = [r['taxon_id'] for r in cur.fetchall()]

    results = []
    for taxon_id in species_ids:
        cid = archive_species(taxon_id, dry_run=dry_run)
        results.append({
            'taxon_id': taxon_id,
            'cid': cid,
            'status': 'archived' if cid else 'failed'
        })

    return results


def verify_archive(cid: str) -> Dict:
    """Verify archive integrity."""
    data = fetch_from_ipfs(cid)
    if not data:
        return {'valid': False, 'error': 'Could not fetch from IPFS'}

    # Verify structure
    required_fields = ['taxon_id', 'insights', 'content_hash', 'research_version']
    missing = [f for f in required_fields if f not in data]
    if missing:
        return {'valid': False, 'error': f'Missing fields: {missing}'}

    # Verify content hash
    content_for_hash = json.dumps(data['insights'], sort_keys=True, default=str)
    calculated_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()

    if calculated_hash != data['content_hash']:
        return {
            'valid': False,
            'error': 'Content hash mismatch',
            'expected': data['content_hash'],
            'calculated': calculated_hash
        }

    return {
        'valid': True,
        'taxon_id': data['taxon_id'],
        'species_name': data.get('species_name'),
        'version': data['research_version'],
        'insight_count': len(data['insights']),
        'archived_at': data.get('archived_at'),
        'previous_cid': data.get('previous_version_cid')
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='IPFS Version Archiver for Treekipedia')
    parser.add_argument('--archive', type=str, help='Archive single species by taxon_id')
    parser.add_argument('--archive-all', action='store_true', help='Archive all researched species')
    parser.add_argument('--history', type=str, help='Show archive history for taxon_id')
    parser.add_argument('--verify', type=str, help='Verify archive by CID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be archived without uploading')

    args = parser.parse_args()

    if args.archive:
        cid = archive_species(args.archive, dry_run=args.dry_run)
        if cid and not args.dry_run:
            print(json.dumps({
                'taxon_id': args.archive,
                'ipfs_cid': cid,
                'gateway_url': f"{LIGHTHOUSE_CONFIG['gateway_url']}/{cid}"
            }, indent=2))

    elif args.archive_all:
        results = archive_all_researched(dry_run=args.dry_run)
        print(json.dumps({
            'archived': len([r for r in results if r['status'] == 'archived']),
            'failed': len([r for r in results if r['status'] == 'failed']),
            'results': results
        }, indent=2))

    elif args.history:
        history = get_archive_history(args.history)
        if history:
            print(json.dumps({
                'taxon_id': args.history,
                'versions': len(history),
                'history': history
            }, indent=2))
        else:
            print(json.dumps({'taxon_id': args.history, 'history': []}))

    elif args.verify:
        result = verify_archive(args.verify)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
