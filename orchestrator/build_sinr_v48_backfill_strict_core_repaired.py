#!/usr/bin/env python3
"""Build the repaired backfill strict-core table for the post-D1 merged rerun."""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"
XIAO_CLEAN_LOOKUP = f"{PROJECT}.{DATASET}.sinr_xiao_clean_lookup_v1"
XIAO_EXTRA_LOOKUP = f"{PROJECT}.{DATASET}.sinr_v48_backfill_xiao_lookup_v1"
GPP_LOOKUP = f"{PROJECT}.{DATASET}.sinr_v48_backfill_gpp_lookup_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_backfill_strict_core_repaired_v1"


def build_row_filters(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return f"""
    NOT ({prefix}bio01 = 0 AND {prefix}bio02 = 0 AND {prefix}bio12 = 0)
    AND ({prefix}soil_ph IS NULL OR {prefix}soil_ph != 0)
    """.strip()


def build_gpp_expr(alias: str = "s") -> str:
    prefix = f"{alias}."
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2001 THEN NULL "
        f"WHEN {prefix}modis_gpp_mean >= 65530 THEN NULL "
        f"WHEN {prefix}modis_gpp_mean = 0 THEN g.modis_gpp_mean_resampled "
        f"WHEN {prefix}modis_gpp_mean IS NULL THEN NULL "
        f"ELSE {prefix}modis_gpp_mean END AS modis_gpp_mean"
    )


def build_nighttime_expr(alias: str = "s") -> str:
    prefix = f"{alias}."
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2012 THEN NULL "
        f"ELSE {prefix}nighttime_lights END AS nighttime_lights"
    )


def build_dynamic_world_expr(alias: str = "s") -> str:
    prefix = f"{alias}."
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2015 THEN CASE CAST({prefix}esa_worldcover_2021 AS INT64) "
        "WHEN 10 THEN 1 WHEN 20 THEN 5 WHEN 30 THEN 2 WHEN 40 THEN 4 WHEN 50 THEN 6 "
        "WHEN 60 THEN 7 WHEN 70 THEN 8 WHEN 80 THEN 0 WHEN 90 THEN 3 WHEN 95 THEN 1 WHEN 100 THEN 7 "
        f"ELSE {prefix}dynamic_world END "
        f"ELSE {prefix}dynamic_world END AS dynamic_world"
    )


def build_xiao_expr() -> str:
    return "COALESCE(xc.xiao_planted_forest, xm.xiao_planted_forest, s.xiao_planted_forest) AS xiao_planted_forest"


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    plain_cols = [
        c for c in preview_core.build_column_list() if c not in {"dynamic_world", "xiao_planted_forest"}
    ]
    select_parts = [f"    s.{col} AS {col}" for col in plain_cols]
    select_parts.append(f"    {build_dynamic_world_expr()}")
    select_parts.append(f"    {build_xiao_expr()}")
    select_parts.append(f"    {build_gpp_expr()}")
    select_parts.append(f"    {build_nighttime_expr()}")
    select_clause = ",\n".join(select_parts)
    return f"""
{create_clause} `{dest_table}` AS
SELECT
{select_clause}
FROM `{SOURCE_TABLE}` s
LEFT JOIN `{XIAO_CLEAN_LOOKUP}` xc
  ON ROUND(s.latitude, 4) = ROUND(xc.latitude, 4)
 AND ROUND(s.longitude, 4) = ROUND(xc.longitude, 4)
LEFT JOIN `{XIAO_EXTRA_LOOKUP}` xm
  ON ROUND(s.latitude, 4) = xm.lat4
 AND ROUND(s.longitude, 4) = xm.lon4
LEFT JOIN `{GPP_LOOKUP}` g
  ON ROUND(s.latitude, 4) = g.lat4
 AND ROUND(s.longitude, 4) = g.lon4
 AND s.observation_year = g.observation_year
WHERE {build_row_filters('s')}
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build repaired backfill strict-core table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return
    client = bigquery.Client(project=PROJECT)
    print(f"Building repaired backfill strict-core -> {args.dest_table}")
    client.query(sql).result()
    q = f"SELECT COUNT(*) AS n, COUNTIF(observation_year >= 2001 AND modis_gpp_mean = 0) AS zero_gpp_post2000 FROM `{args.dest_table}`"
    row = next(client.query(q).result())
    print(f"  rows: {int(row.n):,}")
    print(f"  post-2000 zero GPP rows remaining: {int(row.zero_gpp_post2000):,}")


if __name__ == "__main__":
    main()
