#!/usr/bin/env python3
"""Build the repaired new_gbif strict-core table for the post-D1 merged rerun.

This keeps the current completed_v1 lineage but normalizes the pre-2015
Dynamic World proxy deterministically from ESA WorldCover so the branch follows
the current documented proxy contract.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = (
    f"{PROJECT}.{DATASET}."
    "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_new_gbif_strict_core_repaired_v1"


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


def build_dynamic_world_expr(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return (
        "CASE "
        f"WHEN {prefix}observation_year < 2015 THEN CASE CAST({prefix}esa_worldcover_2021 AS INT64) "
        "WHEN 10 THEN 1 WHEN 20 THEN 5 WHEN 30 THEN 2 WHEN 40 THEN 4 WHEN 50 THEN 6 "
        "WHEN 60 THEN 7 WHEN 70 THEN 8 WHEN 80 THEN 0 WHEN 90 THEN 3 WHEN 95 THEN 1 WHEN 100 THEN 7 "
        f"ELSE {prefix}dynamic_world END "
        f"ELSE {prefix}dynamic_world END AS dynamic_world"
    )


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    plain_cols = [
        c for c in preview_core.build_column_list() if c not in {"dynamic_world"}
    ]
    select_parts = [f"    {col}" for col in plain_cols]
    select_parts.append(f"    {build_dynamic_world_expr()}")
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
    parser = argparse.ArgumentParser(description="Build repaired new_gbif strict-core table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return
    client = bigquery.Client(project=PROJECT)
    print(f"Building repaired new_gbif strict-core -> {args.dest_table}")
    client.query(sql).result()
    row = next(client.query(f"SELECT COUNT(*) AS n FROM `{args.dest_table}`").result())
    print(f"  rows: {int(row.n):,}")


if __name__ == "__main__":
    main()
