#!/usr/bin/env python3
"""Build the backfill zero-GPP repair manifest.

This is a non-destructive, targeted repair manifest for backfill contexts where
post-2000 MODIS GPP was stored as 0 in the raw strict table. D1 validation
showed these zeros are mostly fake missingness and should be resampled from GEE
before the next merged training run.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_backfill_gpp_zero_manifest_v1"


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    return f"""
{create_clause} `{dest_table}` AS
WITH grouped AS (
  SELECT
    ROUND(latitude, 4) AS lat4,
    ROUND(longitude, 4) AS lon4,
    observation_year,
    ANY_VALUE(latitude) AS sample_latitude,
    ANY_VALUE(longitude) AS sample_longitude,
    COUNT(*) AS context_rows
  FROM `{SOURCE_TABLE}`
  WHERE observation_year >= 2001
    AND modis_gpp_mean = 0
  GROUP BY lat4, lon4, observation_year
)
SELECT
  FORMAT('%.4f|%.4f|%d', lat4, lon4, observation_year) AS repair_key,
  lat4,
  lon4,
  observation_year,
  sample_latitude,
  sample_longitude,
  context_rows
FROM grouped
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build backfill zero-GPP repair manifest")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print(f"Building GPP zero repair manifest -> {args.dest_table}")
    client.query(sql).result()
    row = next(
        client.query(
            f"SELECT COUNT(*) AS manifest_rows, SUM(context_rows) AS source_rows FROM `{args.dest_table}`"
        ).result()
    )
    print(f"  repair contexts: {int(row.manifest_rows):,}")
    print(f"  source rows:      {int(row.source_rows):,}")


if __name__ == "__main__":
    main()
