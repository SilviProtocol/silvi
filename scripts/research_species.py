#!/usr/bin/env python3
"""
Treekipedia Species Research Script
Run via Claude Code CLI to research species using subscription quota.

Usage:
  python scripts/research_species.py --queue          # Show queue from web UI
  python scripts/research_species.py --next           # Get next species from queue
  python scripts/research_species.py --taxon-id "AngQuRo1234-00"
  python scripts/research_species.py --batch 10
  python scripts/research_species.py --list-pending
  python scripts/research_species.py --stats
"""

import argparse
import json
import sqlite3
import os
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import psycopg2
except ImportError:
    print("Note: psycopg2 not installed. Install with: pip install psycopg2-binary")
    psycopg2 = None

# Configuration
ORCHESTRATOR_URL = os.environ.get('ORCHESTRATOR_URL', 'http://localhost:5003')

# Database connections
PG_CONN = "dbname=treekipedia"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(SCRIPT_DIR, "..", "research_tracking.db")


def init_sqlite():
    """Initialize SQLite tracking database."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taxon_id TEXT NOT NULL,
            species_name TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'in_progress',
            fields_populated INTEGER,
            fields_total INTEGER DEFAULT 35,
            error_message TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            species_attempted INTEGER DEFAULT 0,
            species_completed INTEGER DEFAULT 0,
            species_failed INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS field_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_log_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            confidence REAL,
            FOREIGN KEY (research_log_id) REFERENCES research_log(id)
        );
    """)
    conn.commit()
    return conn


def get_pg_connection():
    """Get PostgreSQL connection."""
    if psycopg2 is None:
        raise ImportError("psycopg2 is required. Install with: pip install psycopg2-binary")
    return psycopg2.connect(PG_CONN)


def get_species_to_research(limit=10):
    """Get species that haven't been researched yet."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, species_scientific_name, family, wcvp_native
        FROM species
        WHERE (research_version = 0 OR research_version IS NULL)
          AND species_scientific_name IS NOT NULL
          AND species_scientific_name != ''
        ORDER BY total_occurrences DESC NULLS LAST
        LIMIT %s
    """, (limit,))
    species = cur.fetchall()
    conn.close()
    return species


def get_species_by_id(taxon_id):
    """Get a specific species by taxon_id."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, species_scientific_name, family, wcvp_native
        FROM species
        WHERE taxon_id = %s
    """, (taxon_id,))
    species = cur.fetchone()
    conn.close()
    return species


def get_research_stats():
    """Get research progress statistics."""
    conn = get_pg_connection()
    cur = conn.cursor()

    # Overall progress
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE research_version >= 1) as researched,
            COUNT(*) FILTER (WHERE research_version = 0 OR research_version IS NULL) as pending
        FROM species
    """)
    overall = cur.fetchone()

    # Recent research
    cur.execute("""
        SELECT
            COUNT(*) as count,
            DATE(research_date) as date
        FROM species
        WHERE research_version >= 1
          AND research_date IS NOT NULL
        GROUP BY DATE(research_date)
        ORDER BY DATE(research_date) DESC
        LIMIT 7
    """)
    recent = cur.fetchall()

    conn.close()
    return overall, recent


def update_species_research(taxon_id, research_data):
    """Write research results to PostgreSQL."""
    conn = get_pg_connection()
    cur = conn.cursor()

    # Build UPDATE query for AI fields
    updates = []
    values = []

    field_mapping = {
        'popular_common_name': 'common_name',
        'general_description': 'general_description_ai',
        'habitat': 'habitat_ai',
        'elevation_ranges': 'elevation_ranges_ai',
        'ecological_function': 'ecological_function_ai',
        'native_adapted_habitats': 'native_adapted_habitats_ai',
        'conservation_status': 'conservation_status_ai',
        'compatible_soil_types': 'compatible_soil_types_ai',
        'growth_form': 'growth_form_ai',
        'leaf_type': 'leaf_type_ai',
        'deciduous_evergreen': 'deciduous_evergreen_ai',
        'flower_color': 'flower_color_ai',
        'fruit_type': 'fruit_type_ai',
        'bark_characteristics': 'bark_characteristics_ai',
        'maximum_height': 'maximum_height_ai',
        'maximum_diameter': 'maximum_diameter_ai',
        'lifespan': 'lifespan_ai',
        'maximum_tree_age': 'maximum_tree_age_ai',
        'stewardship_best_practices': 'stewardship_best_practices_ai',
        'planting_recipes': 'planting_recipes_ai',
        'pruning_maintenance': 'pruning_maintenance_ai',
        'disease_pest_management': 'disease_pest_management_ai',
        'fire_management': 'fire_management_ai',
        'cultural_significance': 'cultural_significance_ai',
        'agroforestry_use_cases': 'agroforestry_use_cases_ai',
    }

    fields_populated = 0
    for field, value in research_data.items():
        if value is not None and field in field_mapping:
            db_column = field_mapping[field]
            updates.append(f"{db_column} = %s")
            values.append(str(value) if not isinstance(value, str) else value)
            fields_populated += 1

    # Add versioning fields
    updates.extend([
        "research_version = COALESCE(research_version, 0) + 1",
        "research_date = %s",
        "research_agent = %s"
    ])
    values.extend([datetime.now(), 'claude-code-cli'])

    values.append(taxon_id)

    query = f"""
        UPDATE species
        SET {', '.join(updates)}
        WHERE taxon_id = %s
    """

    cur.execute(query, values)
    conn.commit()
    updated = cur.rowcount
    conn.close()

    return updated, fields_populated


def log_research(taxon_id, species_name, status, fields_populated=None, error=None, session_id=None):
    """Log research attempt to SQLite."""
    conn = init_sqlite()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO research_log (taxon_id, species_name, status, fields_populated, error_message, session_id, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        taxon_id,
        species_name,
        status,
        fields_populated,
        error,
        session_id,
        datetime.now() if status in ('completed', 'failed') else None
    ))

    conn.commit()
    log_id = cur.lastrowid
    conn.close()
    return log_id


def list_pending(limit=20):
    """Show species pending research."""
    species = get_species_to_research(limit=limit)
    print(f"\n{'='*70}")
    print(f"Top {limit} Species Pending Research (by occurrence count)")
    print(f"{'='*70}\n")

    for s in species:
        native = s[3][:50] + "..." if s[3] and len(s[3]) > 50 else (s[3] or "Unknown")
        print(f"  {s[0]}")
        print(f"    {s[1]} ({s[2] or 'Unknown family'})")
        print(f"    Native: {native}")
        print()

    print(f"Total pending: Use --stats for full count")


def show_stats():
    """Show research statistics."""
    overall, recent = get_research_stats()

    print(f"\n{'='*50}")
    print(f"RESEARCH PROGRESS")
    print(f"{'='*50}\n")

    print(f"  Total species:     {overall[0]:,}")
    print(f"  Researched:        {overall[1]:,} ({100*overall[1]/overall[0]:.2f}%)")
    print(f"  Pending:           {overall[2]:,}")

    if recent:
        print(f"\n  Recent activity:")
        for count, date in recent:
            print(f"    {date}: {count} species")


def show_species(taxon_id):
    """Show details for a specific species."""
    species = get_species_by_id(taxon_id)
    if species:
        print(f"\n{'='*50}")
        print(f"RESEARCH TARGET")
        print(f"{'='*50}\n")
        print(f"  Taxon ID:  {species[0]}")
        print(f"  Name:      {species[1]}")
        print(f"  Family:    {species[2] or 'Unknown'}")
        print(f"  Native:    {species[3] or 'Unknown'}")
        print()
        print(f"To research this species, use the research prompt from")
        print(f"CLAUDE_RESEARCH_AGENTS.md with the above details.")
    else:
        print(f"Species {taxon_id} not found")


def show_batch(count):
    """Show batch of species ready for research."""
    species = get_species_to_research(limit=count)
    print(f"\n{'='*50}")
    print(f"BATCH: {len(species)} SPECIES FOR RESEARCH")
    print(f"{'='*50}\n")

    for i, s in enumerate(species, 1):
        print(f"{i}. {s[1]}")
        print(f"   ID: {s[0]}")
        print(f"   Family: {s[2] or 'Unknown'}")
        print(f"   Native: {(s[3] or 'Unknown')[:60]}")
        print()


# ============================================================================
# QUEUE FUNCTIONS (for processing user-requested research from web UI)
# ============================================================================

def show_queue():
    """Show species in the research queue (requested via web UI)."""
    if not HAS_REQUESTS:
        print("Error: 'requests' library required. Install with: pip install requests")
        return

    try:
        response = requests.get(f'{ORCHESTRATOR_URL}/queue?status=pending&limit=20')
        data = response.json()

        print(f"\n{'='*80}")
        print(f"RESEARCH QUEUE (User-Requested from Web UI)")
        print(f"{'='*80}\n")

        status_counts = data.get('status_counts', {})
        print(f"Status: pending={status_counts.get('pending', 0)}, "
              f"processing={status_counts.get('processing', 0)}, "
              f"completed={status_counts.get('completed', 0)}, "
              f"failed={status_counts.get('failed', 0)}\n")

        queue_items = data.get('queue_items', [])
        if not queue_items:
            print("No pending items in queue.")
            print("\nUsers can add species by clicking 'Research' on the web UI.")
            return

        print(f"{'ID':<6} {'Taxon ID':<24} {'Species Name':<35} {'Family':<15} {'Queued':<20}")
        print("-" * 100)
        for item in queue_items:
            queued_at = item.get('queued_at', '')
            if queued_at:
                queued_at = str(queued_at)[:16]
            print(f"{item['id']:<6} {item['taxon_id']:<24} {item['species_name'][:33]:<35} "
                  f"{(item.get('family') or 'N/A')[:13]:<15} {queued_at:<20}")

        print(f"\nTo process next item: python scripts/research_species.py --next")

    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to orchestrator at {ORCHESTRATOR_URL}")
        print("Start it with: cd orchestrator && python research_orchestrator.py")
    except Exception as e:
        print(f"Error: {e}")


def get_next_from_queue():
    """Get and display the next species to research from the queue."""
    if not HAS_REQUESTS:
        print("Error: 'requests' library required. Install with: pip install requests")
        return None

    try:
        response = requests.get(f'{ORCHESTRATOR_URL}/queue/next')
        data = response.json()

        if not data.get('success'):
            print("\nNo pending items in queue.")
            print("Users can add species by clicking 'Research' on the web UI.")
            return None

        print(f"\n{'='*80}")
        print(f"NEXT RESEARCH TARGET (Queue ID: {data.get('queue_id')})")
        print(f"{'='*80}\n")

        print(f"  Species:    {data.get('species_name')}")
        print(f"  Taxon ID:   {data.get('taxon_id')}")
        print(f"  Family:     {data.get('family') or 'Unknown'}")
        print(f"  Native to:  {(data.get('wcvp_native') or 'Unknown')[:60]}")

        print(f"\n{'='*80}")
        print(f"FIELDS TO RESEARCH ({data.get('total_fields', 35)} total)")
        print(f"{'='*80}\n")

        agents = data.get('agents', {})
        for agent_type, fields in agents.items():
            print(f"  {agent_type.upper()} ({len(fields)} fields):")
            for field in fields:
                print(f"    - {field}")
            print()

        print(f"{'='*80}")
        print(f"HOW TO RESEARCH THIS SPECIES")
        print(f"{'='*80}")
        print(f"""
1. Mark as processing:
   curl -X POST {ORCHESTRATOR_URL}/queue/{data.get('queue_id')}/start

2. Research using web searches (IUCN, GBIF, POWO, FAO, etc.)

3. Save insights:
   curl -X POST {ORCHESTRATOR_URL}/research/{data.get('taxon_id')}/save \\
     -H "Content-Type: application/json" \\
     -d '{{"session_id": "cli_session", "insights": [...]}}'

4. Mark as completed:
   curl -X POST {ORCHESTRATOR_URL}/queue/{data.get('queue_id')}/complete
""")

        return data

    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to orchestrator at {ORCHESTRATOR_URL}")
        print("Start it with: cd orchestrator && python research_orchestrator.py")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Treekipedia Species Research Helper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Queue-based research (from web UI clicks):
  python scripts/research_species.py --queue         # Show research queue
  python scripts/research_species.py --next          # Get next species from queue

  # Manual research:
  python scripts/research_species.py --list-pending  # List unresearched species
  python scripts/research_species.py --stats         # Show research statistics
  python scripts/research_species.py --taxon-id "AngMaFaFgCx14888-00"
  python scripts/research_species.py --batch 5
        """
    )

    # Queue-based arguments
    parser.add_argument('--queue', action='store_true', help='Show research queue (user-requested)')
    parser.add_argument('--next', action='store_true', help='Get next species from queue to research')

    # Manual research arguments
    parser.add_argument('--taxon-id', help='Show details for specific species')
    parser.add_argument('--batch', type=int, help='Show N species ready for research')
    parser.add_argument('--list-pending', action='store_true', help='List pending species')
    parser.add_argument('--stats', action='store_true', help='Show research statistics')
    parser.add_argument('--limit', type=int, default=20, help='Limit for list-pending (default: 20)')

    args = parser.parse_args()

    # Initialize SQLite on first run
    init_sqlite()

    # Queue-based commands (require orchestrator)
    if args.queue:
        show_queue()
        return

    if args.next:
        get_next_from_queue()
        return

    # Manual research commands
    if args.stats:
        show_stats()
        return

    if args.list_pending:
        list_pending(limit=args.limit)
        return

    if args.taxon_id:
        show_species(args.taxon_id)
        return

    if args.batch:
        show_batch(args.batch)
        return

    parser.print_help()


if __name__ == '__main__':
    main()
