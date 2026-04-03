#!/usr/bin/env python3
"""
compute_is_introduced_bq.py — Compute is_introduced for sinr_v3_unified_v2 using BQ spatial join.

Logic (matches v2.2 train_sinr_model.py):
  1. Spatial join each (latitude, longitude) with TDWG L3 polygons → get region name
  2. Lookup taxon_id in wcvp_native_ranges → get semicolon-separated native regions
  3. If region in native_regions → is_introduced = 0 (native)
     If region NOT in native_regions → is_introduced = 1 (introduced)
     If no native range data or no TDWG match → is_introduced = -1 (unknown, → 0.5 at training)

Creates: sinr_v3_is_introduced (taxon_id, latitude, longitude, is_introduced, tdwg_region)
Then joins back to unified_v2 to create sinr_v3_unified_v2_final.

SAFETY: Only creates new tables. Never modifies existing data.

Usage:
  python3 compute_is_introduced_bq.py --dry-run
  python3 compute_is_introduced_bq.py --execute
  python3 compute_is_introduced_bq.py --stats
"""

import argparse
from datetime import datetime

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
UNIFIED_TABLE = 'sinr_v3_unified_v2'
OUTPUT_TABLE = 'sinr_v3_is_introduced'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def build_is_introduced_query():
    """Build the is_introduced computation query.

    Strategy:
    1. Get distinct (taxon_id, lat4, lon4) from unified table
    2. Spatial join with TDWG L3 to get region
    3. Join with WCVP native ranges
    4. Compute is_introduced based on whether TDWG region is in native range
    """

    query = f"""
    CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}` AS

    WITH coords AS (
        -- Get distinct coordinates per species (avoid recomputing for dupes)
        SELECT DISTINCT
            taxon_id,
            ROUND(latitude, 4) as lat4,
            ROUND(longitude, 4) as lon4
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{UNIFIED_TABLE}`
    ),

    tdwg_joined AS (
        -- Spatial join each coordinate with TDWG L3 region
        SELECT
            c.taxon_id,
            c.lat4,
            c.lon4,
            t.LEVEL3_NAM as tdwg_region
        FROM coords c
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.tdwg_level3` t
            ON ST_CONTAINS(t.geometry, ST_GEOGPOINT(c.lon4, c.lat4))
    ),

    with_native AS (
        -- Join with WCVP native ranges
        -- Handle subspecies: try exact match, then base species (-00 to -05)
        -- v2.2 tries -00 through -05 as fallbacks
        SELECT
            tj.taxon_id,
            tj.lat4,
            tj.lon4,
            tj.tdwg_region,
            COALESCE(
                w_exact.wcvp_native,
                w_00.wcvp_native,
                w_01.wcvp_native,
                w_02.wcvp_native,
                w_03.wcvp_native
            ) as wcvp_native
        FROM tdwg_joined tj
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.wcvp_native_ranges` w_exact
            ON tj.taxon_id = w_exact.taxon_id
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.wcvp_native_ranges` w_00
            ON REGEXP_REPLACE(tj.taxon_id, r'-\\d+$', '-00') = w_00.taxon_id
            AND w_exact.taxon_id IS NULL
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.wcvp_native_ranges` w_01
            ON REGEXP_REPLACE(tj.taxon_id, r'-\\d+$', '-01') = w_01.taxon_id
            AND w_exact.taxon_id IS NULL AND w_00.taxon_id IS NULL
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.wcvp_native_ranges` w_02
            ON REGEXP_REPLACE(tj.taxon_id, r'-\\d+$', '-02') = w_02.taxon_id
            AND w_exact.taxon_id IS NULL AND w_00.taxon_id IS NULL AND w_01.taxon_id IS NULL
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.wcvp_native_ranges` w_03
            ON REGEXP_REPLACE(tj.taxon_id, r'-\\d+$', '-03') = w_03.taxon_id
            AND w_exact.taxon_id IS NULL AND w_00.taxon_id IS NULL AND w_01.taxon_id IS NULL AND w_02.taxon_id IS NULL
    )

    SELECT
        taxon_id,
        lat4,
        lon4,
        tdwg_region,
        wcvp_native,
        CASE
            -- No TDWG region or no native range data → unknown
            WHEN tdwg_region IS NULL OR wcvp_native IS NULL THEN -1
            -- TDWG region is in native ranges → native
            WHEN CONCAT(';', wcvp_native, ';') LIKE CONCAT('%;', tdwg_region, ';%') THEN 0
            -- TDWG region NOT in native ranges → introduced
            ELSE 1
        END as is_introduced
    FROM with_native
    """

    return query


def show_stats():
    """Show is_introduced distribution."""
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)

    q = f"""
    SELECT
        is_introduced,
        COUNT(*) as cnt,
        COUNT(DISTINCT taxon_id) as species
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`
    GROUP BY is_introduced
    ORDER BY is_introduced
    """
    log("=== is_introduced Distribution ===")
    for row in client.query(q).result():
        label = {0: 'native', 1: 'introduced', -1: 'unknown'}[row.is_introduced]
        log(f"  {label} ({row.is_introduced}): {row.cnt:,} coord-species pairs, {row.species:,} species")

    # Total
    q2 = f"""
    SELECT COUNT(*) as total, COUNT(DISTINCT taxon_id) as species
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`
    """
    for row in client.query(q2).result():
        log(f"\n  Total: {row.total:,} pairs, {row.species:,} species")


def build_final_table_query():
    """Create sinr_v3_unified_v2_final by joining unified_v2 with is_introduced.

    This is the table that gets exported for training.
    """
    final_table = 'sinr_v3_unified_v2_final'
    return f"""
    CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{final_table}` AS
    SELECT
        u.*,
        COALESCE(i.is_introduced, -1) as is_introduced,
        i.tdwg_region
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{UNIFIED_TABLE}` u
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}` i
        ON u.taxon_id = i.taxon_id
        AND ROUND(u.latitude, 4) = i.lat4
        AND ROUND(u.longitude, 4) = i.lon4
    """, final_table


def main():
    parser = argparse.ArgumentParser(description='Compute is_introduced via TDWG+WCVP spatial join')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--finalize', action='store_true', help='Create final table with is_introduced joined')
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    query = build_is_introduced_query()

    if args.dry_run:
        log("=== DRY RUN ===")
        print(query)
        return

    if args.execute:
        from google.cloud import bigquery
        client = bigquery.Client(project=BQ_PROJECT)

        # Check if exists
        try:
            existing = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}')
            log(f"Table {OUTPUT_TABLE} already exists ({existing.num_rows:,} rows)")
            log("Delete it first if you want to recompute.")
            return
        except Exception:
            pass

        log("Computing is_introduced...")
        log("  Step 1: Distinct (taxon_id, lat, lon) from unified table")
        log("  Step 2: Spatial join with 369 TDWG L3 polygons")
        log("  Step 3: WCVP native range lookup")
        log("  Step 4: Compute is_introduced flag")

        job = client.query(query)
        log(f"  Job started: {job.job_id}")
        job.result()  # Wait

        t = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}')
        log(f"\nDone! {OUTPUT_TABLE}: {t.num_rows:,} rows")

        # Show stats
        show_stats()
        return

    if args.finalize:
        from google.cloud import bigquery
        client = bigquery.Client(project=BQ_PROJECT)

        query, final_table = build_final_table_query()

        try:
            existing = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{final_table}')
            log(f"Table {final_table} already exists ({existing.num_rows:,} rows)")
            log("Delete it first if you want to rebuild.")
            return
        except Exception:
            pass

        log(f"Creating {final_table} (unified_v2 + is_introduced)...")
        job = client.query(query)
        log(f"  Job started: {job.job_id}")
        job.result()

        t = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{final_table}')
        log(f"Done! {final_table}: {t.num_rows:,} rows, {len(t.schema)} cols, {t.num_bytes / (1024**3):.2f} GB")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
