#!/usr/bin/env python3
"""Build the distinct-coordinate GEDI manifest for strict SINR repair.

This is the first non-destructive step for the GEDI-only repair path.
It unions distinct rounded coordinates across:

- new_gbif repaired strict lineage completed_v1
- backfill strict raw lineage

The output is coordinate-grain and intentionally static so a future GEDI-only
extract can sample once per coord and then join back to both branches.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

NEW_GBIF_TABLE = (
    f"{PROJECT}.{DATASET}."
    "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
BACKFILL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_gedi_coord_manifest_v1"


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    return f"""
{create_clause} `{dest_table}` AS
WITH branch_counts AS (
  SELECT
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    COUNT(*) AS new_gbif_context_rows,
    0 AS backfill_context_rows
  FROM `{NEW_GBIF_TABLE}`
  GROUP BY lat4, lon4

  UNION ALL

  SELECT
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    0 AS new_gbif_context_rows,
    COUNT(*) AS backfill_context_rows
  FROM `{BACKFILL_TABLE}`
  GROUP BY lat4, lon4
)
SELECT
  FORMAT('%.4f|%.4f', lat4, lon4) AS coord_key,
  lat4,
  lon4,
  lat4 AS sample_latitude,
  lon4 AS sample_longitude,
  SUM(new_gbif_context_rows) AS new_gbif_context_rows,
  SUM(backfill_context_rows) AS backfill_context_rows,
  SUM(new_gbif_context_rows) + SUM(backfill_context_rows) AS total_context_rows,
  SUM(CASE WHEN new_gbif_context_rows > 0 THEN 1 ELSE 0 END) > 0 AS in_new_gbif,
  SUM(CASE WHEN backfill_context_rows > 0 THEN 1 ELSE 0 END) > 0 AS in_backfill
FROM branch_counts
GROUP BY lat4, lon4
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GEDI coord manifest for strict repair")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print("Building V4.8 GEDI coord manifest...")
    print(f"  new_gbif:  {NEW_GBIF_TABLE}")
    print(f"  backfill:  {BACKFILL_TABLE}")
    print(f"  dest:      {args.dest_table}")
    client.query(sql).result()

    verify_sql = f"""
    WITH stats AS (
      SELECT
        COUNT(*) AS coord_rows,
        COUNT(DISTINCT coord_key) AS distinct_coord_keys,
        COUNTIF(in_new_gbif) AS coords_in_new_gbif,
        COUNTIF(in_backfill) AS coords_in_backfill,
        COUNTIF(in_new_gbif AND in_backfill) AS coords_in_both,
        SUM(new_gbif_context_rows) AS sum_new_gbif_context_rows,
        SUM(backfill_context_rows) AS sum_backfill_context_rows,
        SUM(total_context_rows) AS sum_total_context_rows
      FROM `{args.dest_table}`
    )
    SELECT * FROM stats
    """
    row = next(client.query(verify_sql).result())
    print("\nBuilt GEDI coord manifest")
    print(f"  coord rows:              {int(row.coord_rows):,}")
    print(f"  distinct coord keys:     {int(row.distinct_coord_keys):,}")
    print(f"  coords in new_gbif:      {int(row.coords_in_new_gbif):,}")
    print(f"  coords in backfill:      {int(row.coords_in_backfill):,}")
    print(f"  coords in both:          {int(row.coords_in_both):,}")
    print(f"  summed new_gbif rows:    {int(row.sum_new_gbif_context_rows):,}")
    print(f"  summed backfill rows:    {int(row.sum_backfill_context_rows):,}")
    print(f"  summed total rows:       {int(row.sum_total_context_rows):,}")


if __name__ == "__main__":
    main()
