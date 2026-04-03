#!/usr/bin/env python3
"""Build the backfill Xiao repair manifest for coords missing the clean lookup."""

from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

BACKFILL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"
CLEAN_LOOKUP = f"{PROJECT}.{DATASET}.sinr_xiao_clean_lookup_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_backfill_xiao_missing_manifest_v1"


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    return f"""
{create_clause} `{dest_table}` AS
WITH backfill_coords AS (
  SELECT
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    ANY_VALUE(latitude) AS sample_latitude,
    ANY_VALUE(longitude) AS sample_longitude,
    COUNT(*) AS context_rows
  FROM `{BACKFILL_TABLE}`
  GROUP BY lat4, lon4
)
SELECT
  FORMAT('%.4f|%.4f', b.lat4, b.lon4) AS coord_key,
  b.lat4,
  b.lon4,
  b.sample_latitude,
  b.sample_longitude,
  b.context_rows
FROM backfill_coords b
LEFT JOIN (
  SELECT DISTINCT ROUND(latitude, 4) AS lat4, ROUND(longitude, 4) AS lon4
  FROM `{CLEAN_LOOKUP}`
) c USING (lat4, lon4)
WHERE c.lat4 IS NULL
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build backfill Xiao missing lookup manifest")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print(f"Building backfill Xiao missing manifest -> {args.dest_table}")
    client.query(sql).result()
    row = next(
        client.query(
            f"SELECT COUNT(*) AS manifest_rows, SUM(context_rows) AS source_rows FROM `{args.dest_table}`"
        ).result()
    )
    print(f"  repair coords: {int(row.manifest_rows):,}")
    print(f"  source rows:   {int(row.source_rows):,}")


if __name__ == "__main__":
    main()
