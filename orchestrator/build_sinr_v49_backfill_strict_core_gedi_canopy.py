#!/usr/bin/env python3
"""Build the v49 backfill strict-core table with canopy-only GEDI overlay."""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v47_backfill_strict_core_v1"
GEDI_LOOKUP = f"{PROJECT}.{DATASET}.sinr_v48_gedi_lookup_deduped_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v49_backfill_strict_core_gedi_canopy_v1"

GEDI_MIN_COUNTF = 10
GEDI_MAX_CANOPY_M = 100


def build_gedi_canopy_expr(gedi_alias: str = "g") -> str:
    return (
        "CASE "
        f"WHEN {gedi_alias}.rh_countf IS NULL THEN NULL "
        f"WHEN {gedi_alias}.rh_countf < {GEDI_MIN_COUNTF} THEN NULL "
        f"WHEN {gedi_alias}.rh_p95 < 0 OR {gedi_alias}.rh_p95 > {GEDI_MAX_CANOPY_M} THEN NULL "
        f"ELSE CAST({gedi_alias}.rh_p95 AS FLOAT64) END AS gedi_canopy_height_m"
    )


def build_gedi_countf_expr(gedi_alias: str = "g") -> str:
    return f"CAST(IFNULL({gedi_alias}.rh_countf, 0) AS FLOAT64) AS gedi_canopy_countf"


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    plain_cols = preview_core.build_column_list()
    select_parts = [f"    s.{col} AS {col}" for col in plain_cols]
    select_parts.append("    s.modis_gpp_mean AS modis_gpp_mean")
    select_parts.append("    s.nighttime_lights AS nighttime_lights")
    select_parts.append(f"    {build_gedi_canopy_expr('g')}")
    select_parts.append(f"    {build_gedi_countf_expr('g')}")
    select_clause = ",\n".join(select_parts)
    return f"""
{create_clause} `{dest_table}` AS
SELECT
{select_clause}
FROM `{SOURCE_TABLE}` s
LEFT JOIN `{GEDI_LOOKUP}` g
  ON ROUND(s.latitude, 4) = g.lat4
 AND ROUND(s.longitude, 4) = g.lon4
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v49 backfill strict-core with GEDI canopy")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print(f"Building v49 backfill strict-core GEDI canopy -> {args.dest_table}")
    client.query(sql).result()
    row = next(
        client.query(
            f"SELECT COUNT(*) AS n, "
            f"COUNTIF(gedi_canopy_height_m IS NOT NULL) AS canopy_rows, "
            f"COUNTIF(gedi_canopy_countf >= {GEDI_MIN_COUNTF}) AS supported_rows "
            f"FROM `{args.dest_table}`"
        ).result()
    )
    print(f"  rows: {int(row.n):,}")
    print(f"  canopy rows: {int(row.canopy_rows):,}")
    print(f"  supported rows: {int(row.supported_rows):,}")


if __name__ == "__main__":
    main()
