#!/usr/bin/env python3
"""
Fix invalid geohash geometries by recomputing from geohash string.

The parquet import used pre-computed WKT that was degenerate (all vertices same point).
This script recomputes geometries using PostGIS ST_GeomFromGeoHash().

Usage:
    python3 scripts/fix_geohash_geometries.py
"""

import os
import time
import psycopg2

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://tree_user:Kj9mPx7vLq2wZn4t@localhost:5432/treekipedia'
)

BATCH_SIZE = 50000  # Update in batches to show progress

def main():
    print("=== Fix Geohash Geometries ===\n")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Count invalid geometries
    print("Counting invalid geometries...")
    cur.execute("""
        SELECT COUNT(*) FROM geohash_species_tiles
        WHERE NOT ST_IsValid(geometry)
    """)
    invalid_count = cur.fetchone()[0]
    print(f"Invalid geometries to fix: {invalid_count:,}\n")

    if invalid_count == 0:
        print("No invalid geometries found. Exiting.")
        conn.close()
        return

    # Fix in batches using ctid for efficient pagination
    print(f"Fixing geometries in batches of {BATCH_SIZE:,}...")
    start_time = time.time()
    total_fixed = 0

    while True:
        cur.execute(f"""
            UPDATE geohash_species_tiles
            SET geometry = ST_GeomFromGeoHash(geohash_l7)
            WHERE ctid IN (
                SELECT ctid FROM geohash_species_tiles
                WHERE NOT ST_IsValid(geometry)
                LIMIT {BATCH_SIZE}
            )
        """)

        fixed = cur.rowcount
        conn.commit()
        total_fixed += fixed

        elapsed = time.time() - start_time
        rate = total_fixed / elapsed if elapsed > 0 else 0
        pct = (total_fixed / invalid_count) * 100

        print(f"  Fixed: {total_fixed:,}/{invalid_count:,} ({pct:.1f}%) - {rate:.0f} rows/sec")

        if fixed < BATCH_SIZE:
            break

    elapsed = time.time() - start_time
    print(f"\n=== Complete ===")
    print(f"Total fixed: {total_fixed:,}")
    print(f"Time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

    # Verify
    print("\nVerifying...")
    cur.execute("""
        SELECT COUNT(*) FROM geohash_species_tiles
        WHERE NOT ST_IsValid(geometry)
    """)
    remaining = cur.fetchone()[0]
    print(f"Remaining invalid: {remaining:,}")

    conn.close()
    print("Done!")

if __name__ == '__main__':
    main()
