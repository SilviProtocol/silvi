#!/usr/bin/env python3
"""
Assign ecoregions to new geohash tiles that don't have ecoregion data.

Uses ST_Contains for center point matching (fast), then ST_Intersects
for boundary tiles that weren't matched.

Usage:
    python3 scripts/assign_ecoregions_new_tiles.py
"""

import os
import time
import psycopg2

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://tree_user:Kj9mPx7vLq2wZn4t@localhost:5432/treekipedia'
)

BATCH_SIZE = 10000


def main():
    print("=== Assign Ecoregions to New Tiles ===\n")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Count tiles needing assignment
    cur.execute("""
        SELECT COUNT(*) FROM geohash_species_tiles
        WHERE eco_id IS NULL AND geometry IS NOT NULL
    """)
    total_tiles = cur.fetchone()[0]
    print(f"Tiles needing ecoregion: {total_tiles:,}")

    if total_tiles == 0:
        print("All tiles already have ecoregion assignments!")
        conn.close()
        return

    # Phase 1: Center point containment (fast)
    print(f"\n=== Phase 1: Center Point Matching ===")
    print(f"Processing in batches of {BATCH_SIZE:,}...")

    start_time = time.time()
    total_assigned = 0
    batch_num = 0

    while True:
        batch_num += 1
        batch_start = time.time()

        # Use ctid for efficient batch selection
        cur.execute(f"""
            WITH batch_tiles AS (
                SELECT ctid, geohash_l7, center_point
                FROM geohash_species_tiles
                WHERE eco_id IS NULL
                LIMIT {BATCH_SIZE}
            )
            UPDATE geohash_species_tiles g
            SET
                eco_id = e.eco_id,
                eco_name = e.eco_name,
                biome_name = e.biome_name,
                realm = e.realm
            FROM ecoregions e, batch_tiles bt
            WHERE g.ctid = bt.ctid
              AND ST_Contains(e.geom, bt.center_point::geometry)
        """)

        assigned = cur.rowcount
        conn.commit()
        total_assigned += assigned

        batch_elapsed = time.time() - batch_start
        total_elapsed = time.time() - start_time

        # Check remaining
        cur.execute("SELECT COUNT(*) FROM geohash_species_tiles WHERE eco_id IS NULL")
        remaining = cur.fetchone()[0]

        pct = ((total_tiles - remaining) / total_tiles) * 100
        rate = total_assigned / total_elapsed if total_elapsed > 0 else 0

        print(f"  Batch {batch_num}: +{assigned:,} assigned, {remaining:,} remaining ({pct:.1f}%) - {rate:.0f}/sec")

        if assigned == 0 or remaining == 0:
            break

    print(f"\nPhase 1 complete: {total_assigned:,} tiles assigned in {time.time() - start_time:.1f}s")

    # Phase 2: Intersection for boundary/ocean tiles
    cur.execute("SELECT COUNT(*) FROM geohash_species_tiles WHERE eco_id IS NULL")
    remaining = cur.fetchone()[0]

    if remaining > 0:
        print(f"\n=== Phase 2: Intersection Matching ({remaining:,} remaining) ===")
        print("This handles tiles on ecoregion boundaries...")

        phase2_start = time.time()

        # For remaining tiles, use intersection and pick largest overlap
        cur.execute("""
            UPDATE geohash_species_tiles g
            SET
                eco_id = e.eco_id,
                eco_name = e.eco_name,
                biome_name = e.biome_name,
                realm = e.realm
            FROM ecoregions e
            WHERE g.eco_id IS NULL
              AND ST_Intersects(e.geom, g.geometry)
              AND e.eco_id = (
                  SELECT e2.eco_id
                  FROM ecoregions e2
                  WHERE ST_Intersects(e2.geom, g.geometry)
                  ORDER BY ST_Area(ST_Intersection(e2.geom, g.geometry)) DESC
                  LIMIT 1
              )
        """)

        phase2_assigned = cur.rowcount
        conn.commit()
        total_assigned += phase2_assigned

        print(f"Phase 2 complete: {phase2_assigned:,} tiles assigned in {time.time() - phase2_start:.1f}s")

    # Final statistics
    print(f"\n=== Final Statistics ===")
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(eco_id) as with_eco,
            COUNT(CASE WHEN eco_id IS NULL THEN 1 END) as without_eco,
            COUNT(DISTINCT eco_id) as unique_ecoregions
        FROM geohash_species_tiles
    """)
    r = cur.fetchone()
    print(f"Total tiles: {r[0]:,}")
    print(f"With ecoregion: {r[1]:,} ({r[1]/r[0]*100:.1f}%)")
    print(f"Without ecoregion: {r[2]:,} (likely ocean/remote)")
    print(f"Unique ecoregions used: {r[3]:,}")

    total_time = time.time() - start_time
    print(f"\nTotal time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"Total assigned: {total_assigned:,}")

    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
