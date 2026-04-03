#!/usr/bin/env python3
"""Build the V4.7 repaired backfill strict-core feature-grain table.

This is the fast-safe backfill lineage step before the first merged V4.7
training table. It is intentionally non-destructive:

- source:  `species_data.sinr_v3_features_backfill_strict_full`
- output:  a new versioned strict-core table
- policy:  mirror the V4.1 strict-core surface

Applied guards:
- GEDI excluded entirely
- MODIS GPP fill codes masked to NULL
- pre-2001 MODIS GPP forced to NULL
- nighttime lights pre-2012 forced to NULL
- obvious bio/soil unmask artifacts filtered out
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v47_backfill_strict_core_v1"


def build_row_filters(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return f"""
    NOT ({prefix}bio01 = 0 AND {prefix}bio02 = 0 AND {prefix}bio12 = 0)
    AND ({prefix}soil_ph IS NULL OR {prefix}soil_ph != 0)
    """.strip()


def build_gpp_expr(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2001 THEN NULL "
        f"WHEN {prefix}modis_gpp_mean >= 65530 THEN NULL "
        f"WHEN {prefix}modis_gpp_mean IS NULL THEN NULL "
        f"ELSE {prefix}modis_gpp_mean END AS modis_gpp_mean"
    )


def build_nighttime_expr(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2012 THEN NULL "
        f"ELSE {prefix}nighttime_lights END AS nighttime_lights"
    )


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    plain_cols = preview_core.build_column_list()
    select_parts = [f"    {col}" for col in plain_cols]
    select_parts.append(f"    {build_gpp_expr()}")
    select_parts.append(f"    {build_nighttime_expr()}")

    select_clause = ",\n".join(select_parts)

    return f"""
{create_clause} `{dest_table}` AS
SELECT
{select_clause}
FROM `{SOURCE_TABLE}`
WHERE {build_row_filters()}
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build repaired V4.7 backfill strict-core table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print("Building V4.7 repaired backfill strict-core table...")
    print(f"  Source:   {SOURCE_TABLE}")
    print(f"  Dest:     {args.dest_table}")
    print(f"  Columns:  {len(preview_core.build_column_list()) + 2}")
    print("  Excluded: GEDI, external/manual families")
    print("  Guards:   GPP pre-2001 -> NULL, GPP >= 65530 -> NULL, nighttime pre-2012 -> NULL")
    print("  Filters:  bio zero-contamination, soil_ph = 0")

    client.query(sql).result()

    verify_sql = f"""
    WITH source_stats AS (
      SELECT
        COUNT(*) AS source_rows,
        COUNT(DISTINCT FORMAT('%.4f|%.4f|%d|%d', ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year)) AS source_contexts
      FROM `{SOURCE_TABLE}`
    ),
    dest_stats AS (
      SELECT
        COUNT(*) AS dest_rows,
        COUNT(DISTINCT FORMAT('%.4f|%.4f|%d|%d', ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year)) AS dest_contexts
      FROM `{args.dest_table}`
    ),
    dupes AS (
      SELECT COUNT(*) AS dup_groups
      FROM (
        SELECT 1
        FROM `{args.dest_table}`
        GROUP BY ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year
        HAVING COUNT(*) > 1
      )
    )
    SELECT *
    FROM source_stats, dest_stats, dupes
    """
    row = next(client.query(verify_sql).result())

    print("\nBuilt V4.7 repaired backfill strict-core table")
    print(f"  source rows:      {int(row.source_rows):,}")
    print(f"  source contexts:  {int(row.source_contexts):,}")
    print(f"  strict-core rows: {int(row.dest_rows):,}")
    print(f"  strict contexts:  {int(row.dest_contexts):,}")
    print(f"  excluded rows:    {int(row.source_rows - row.dest_rows):,}")
    print(f"  duplicate groups: {int(row.dup_groups):,}")


if __name__ == "__main__":
    main()
