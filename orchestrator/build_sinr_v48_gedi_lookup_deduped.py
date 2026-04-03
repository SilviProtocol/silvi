#!/usr/bin/env python3
"""Build a deduped GEDI coord lookup table for strict SINR repair."""

from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_gedi_lookup_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_gedi_lookup_deduped_v1"


def build_sql(source_table: str, dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    return f"""
{create_clause} `{dest_table}` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY coord_key
      ORDER BY gedi_extracted_at_utc DESC, gedi_extraction_run_id DESC
    ) AS dedupe_rank
  FROM `{source_table}`
)
SELECT * EXCEPT(dedupe_rank)
FROM ranked
WHERE dedupe_rank = 1
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deduped GEDI lookup table")
    parser.add_argument("--source-table", default=SOURCE_TABLE)
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.source_table, args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print("Building deduped GEDI lookup table...")
    print(f"  source: {args.source_table}")
    print(f"  dest:   {args.dest_table}")
    client.query(sql).result()

    verify_sql = f"""
    SELECT
      COUNT(*) AS rows_total,
      COUNT(DISTINCT coord_key) AS distinct_coord_key,
      COUNT(*) - COUNT(DISTINCT coord_key) AS duplicate_rows,
      COUNT(DISTINCT gedi_extraction_run_id) AS distinct_run_ids
    FROM `{args.dest_table}`
    """
    row = next(client.query(verify_sql).result())
    print("\nBuilt deduped GEDI lookup table")
    print(f"  rows total:          {int(row.rows_total):,}")
    print(f"  distinct coord_key:  {int(row.distinct_coord_key):,}")
    print(f"  duplicate rows:      {int(row.duplicate_rows):,}")
    print(f"  distinct run ids:    {int(row.distinct_run_ids):,}")


if __name__ == "__main__":
    main()
