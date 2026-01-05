#!/usr/bin/env python3
"""
Geohash Occurrence Data Import from Parquet Files

Memory-efficient import of compressed geohash occurrence data.
Designed for low-resource VMs (~2-4GB RAM).

Usage:
    python3 scripts/import_geohash_parquet.py [--dry-run] [--skip-cache] [--start-file N]

Features:
    - Streams parquet files in batches (never loads full file)
    - Transforms species_data from array to object format
    - Preserves ecoregion assignments via cache table
    - Progress logging with resume capability
    - Commits after each batch to minimize memory
"""

import os
import sys
import json
import glob
import argparse
import time
from datetime import datetime

import pyarrow.parquet as pq
import psycopg2
from psycopg2.extras import execute_values

# Configuration
BATCH_SIZE = 2000  # Rows per batch (conservative for low RAM)
LOG_INTERVAL = 10000  # Log progress every N rows
DATA_DIR = '/root/silvi-open/treekipedia/data'
PARQUET_PATTERN = 'tiles-*.parquet'

# Database connection from environment or default
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://tree_user:Kj9mPx7vLq2wZn4t@localhost:5432/treekipedia'
)


def transform_species_data(species_json_str):
    """
    Transform species_data from array format to object format.

    Input:  '[{"taxon_id": "ABC-00", "count": 5}, {"taxon_id": "DEF-00", "count": 3}]'
    Output: '{"ABC-00": 5, "DEF-00": 3}'
    """
    try:
        arr = json.loads(species_json_str)
        obj = {item['taxon_id']: item['count'] for item in arr}
        return json.dumps(obj)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  Warning: Failed to transform species_data: {e}")
        return '{}'


def create_ecoregion_cache(conn):
    """Cache ecoregion assignments before truncating main table."""
    print("\n=== Caching ecoregion assignments ===")
    cur = conn.cursor()

    # Check if cache already exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'geohash_ecoregion_cache'
        )
    """)
    cache_exists = cur.fetchone()[0]

    if cache_exists:
        cur.execute("SELECT COUNT(*) FROM geohash_ecoregion_cache")
        count = cur.fetchone()[0]
        print(f"  Cache table already exists with {count:,} rows")
        print("  Skipping cache creation (use --skip-cache to ignore)")
        cur.close()
        return count

    print("  Creating cache table...")
    start = time.time()

    cur.execute("""
        CREATE TABLE geohash_ecoregion_cache AS
        SELECT geohash_l7, eco_id, eco_name, biome_name, realm
        FROM geohash_species_tiles
        WHERE eco_id IS NOT NULL
    """)

    cur.execute("SELECT COUNT(*) FROM geohash_ecoregion_cache")
    count = cur.fetchone()[0]

    # Add index for fast lookups during restore
    cur.execute("CREATE INDEX idx_ecoregion_cache_geohash ON geohash_ecoregion_cache(geohash_l7)")

    conn.commit()
    elapsed = time.time() - start
    print(f"  Cached {count:,} ecoregion assignments in {elapsed:.1f}s")
    cur.close()
    return count


def truncate_main_table(conn):
    """Truncate the main geohash_species_tiles table."""
    print("\n=== Truncating main table ===")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM geohash_species_tiles")
    count = cur.fetchone()[0]
    print(f"  Current row count: {count:,}")

    cur.execute("TRUNCATE geohash_species_tiles")
    conn.commit()
    print("  Table truncated")
    cur.close()


def process_parquet_file(filepath, conn, dry_run=False):
    """Process a single parquet file in batches."""
    filename = os.path.basename(filepath)
    print(f"\n  Processing: {filename}")

    pf = pq.ParquetFile(filepath)
    total_rows = pf.metadata.num_rows
    print(f"  Total rows: {total_rows:,}")

    cur = conn.cursor()
    processed = 0
    inserted = 0
    errors = 0
    start_time = time.time()

    # Read in batches using iter_batches (memory efficient)
    for batch in pf.iter_batches(batch_size=BATCH_SIZE):
        batch_df = batch.to_pandas()
        rows_to_insert = []

        for _, row in batch_df.iterrows():
            try:
                # Transform species_data from array to object
                species_data_obj = transform_species_data(row['species_data'])

                rows_to_insert.append((
                    row['geohash_l7'],
                    species_data_obj,
                    int(row['total_occurrences']),
                    int(row['species_count']),
                    row['geometry_wkt'],
                    row['center_point_wkt'],
                    row['data_source'] if row['data_source'] else 'gbif',
                    datetime.now()
                ))
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"    Error processing row: {e}")

        if not dry_run and rows_to_insert:
            try:
                # Simple INSERT (table is truncated before import, no conflicts)
                execute_values(
                    cur,
                    """
                    INSERT INTO geohash_species_tiles (
                        geohash_l7, species_data, total_occurrences, species_count,
                        geometry, center_point, data_source, processing_date
                    ) VALUES %s
                    """,
                    rows_to_insert,
                    template="""(
                        %s, %s::jsonb, %s, %s,
                        ST_GeomFromText(%s, 4326),
                        ST_GeomFromText(%s, 4326)::geography,
                        %s, %s
                    )"""
                )
                conn.commit()
                inserted += len(rows_to_insert)
            except Exception as e:
                conn.rollback()
                errors += len(rows_to_insert)
                print(f"    Batch insert error: {e}")

        processed += len(batch_df)

        # Progress logging
        if processed % LOG_INTERVAL < BATCH_SIZE:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            pct = (processed / total_rows) * 100
            print(f"    Progress: {processed:,}/{total_rows:,} ({pct:.1f}%) - {rate:.0f} rows/sec")

        # Release batch memory
        del batch_df
        del rows_to_insert

    elapsed = time.time() - start_time
    print(f"  Completed: {inserted:,} inserted, {errors:,} errors in {elapsed:.1f}s")
    cur.close()

    return inserted, errors


def restore_ecoregion_cache(conn):
    """Restore ecoregion assignments from cache."""
    print("\n=== Restoring ecoregion assignments ===")
    cur = conn.cursor()

    # Check cache exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'geohash_ecoregion_cache'
        )
    """)
    if not cur.fetchone()[0]:
        print("  No cache table found - skipping restore")
        cur.close()
        return 0

    print("  Restoring from cache (this may take a few minutes)...")
    start = time.time()

    cur.execute("""
        UPDATE geohash_species_tiles g
        SET
            eco_id = c.eco_id,
            eco_name = c.eco_name,
            biome_name = c.biome_name,
            realm = c.realm
        FROM geohash_ecoregion_cache c
        WHERE g.geohash_l7 = c.geohash_l7
    """)

    updated = cur.rowcount
    conn.commit()
    elapsed = time.time() - start
    print(f"  Restored {updated:,} ecoregion assignments in {elapsed:.1f}s")
    cur.close()
    return updated


def count_tiles_needing_ecoregion(conn):
    """Count tiles that still need ecoregion assignment."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM geohash_species_tiles
        WHERE eco_id IS NULL AND geometry IS NOT NULL
    """)
    count = cur.fetchone()[0]
    cur.close()
    return count


def drop_ecoregion_cache(conn):
    """Drop the ecoregion cache table."""
    print("\n=== Cleaning up cache ===")
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS geohash_ecoregion_cache")
    conn.commit()
    print("  Cache table dropped")
    cur.close()


def main():
    parser = argparse.ArgumentParser(description='Import geohash parquet files')
    parser.add_argument('--dry-run', action='store_true', help='Parse files without inserting')
    parser.add_argument('--skip-cache', action='store_true', help='Skip ecoregion caching')
    parser.add_argument('--start-file', type=int, default=0, help='Start from file N (0-11)')
    parser.add_argument('--restore-only', action='store_true', help='Only restore ecoregions from cache')
    args = parser.parse_args()

    # Find parquet files
    pattern = os.path.join(DATA_DIR, PARQUET_PATTERN)
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No parquet files found matching: {pattern}")
        sys.exit(1)

    print(f"Found {len(files)} parquet files")

    # Connect to database
    print(f"\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    print("  Connected")

    try:
        if args.restore_only:
            restore_ecoregion_cache(conn)
            needs_assignment = count_tiles_needing_ecoregion(conn)
            print(f"\n{needs_assignment:,} tiles still need ecoregion assignment")
            return

        # Step 1: Cache ecoregion assignments
        if not args.skip_cache:
            create_ecoregion_cache(conn)

        # Step 2: Truncate main table (if not resuming)
        if args.start_file == 0:
            truncate_main_table(conn)
        else:
            print(f"\nResuming from file {args.start_file}, skipping truncate")

        # Step 3: Process each parquet file
        print(f"\n=== Processing parquet files ===")
        total_inserted = 0
        total_errors = 0
        overall_start = time.time()

        for i, filepath in enumerate(files):
            if i < args.start_file:
                print(f"\n  Skipping file {i}: {os.path.basename(filepath)}")
                continue

            print(f"\n[File {i+1}/{len(files)}]")
            inserted, errors = process_parquet_file(filepath, conn, args.dry_run)
            total_inserted += inserted
            total_errors += errors

            # Log cumulative progress
            elapsed = time.time() - overall_start
            print(f"  Cumulative: {total_inserted:,} inserted, {elapsed/60:.1f} min elapsed")

        overall_elapsed = time.time() - overall_start
        print(f"\n=== Import complete ===")
        print(f"Total inserted: {total_inserted:,}")
        print(f"Total errors: {total_errors:,}")
        print(f"Total time: {overall_elapsed/60:.1f} minutes")

        # Step 4: Restore ecoregion assignments
        if not args.dry_run:
            restore_ecoregion_cache(conn)

            # Report tiles needing new ecoregion assignment
            needs_assignment = count_tiles_needing_ecoregion(conn)
            print(f"\n{needs_assignment:,} new tiles need ecoregion assignment")
            print("Run the ecoregion assignment script separately for these.")

        # Step 5: Cleanup (optional - keep cache for safety)
        # drop_ecoregion_cache(conn)
        print("\nNote: Cache table retained for safety. Drop manually when verified:")
        print("  DROP TABLE geohash_ecoregion_cache;")

    finally:
        conn.close()
        print("\nDatabase connection closed")


if __name__ == '__main__':
    main()
