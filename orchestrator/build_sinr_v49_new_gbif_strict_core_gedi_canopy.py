#!/usr/bin/env python3
"""Build the v49 new_gbif strict-core table with canopy-only GEDI overlay."""

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
GEDI_LOOKUP = f"{PROJECT}.{DATASET}.sinr_v48_gedi_lookup_deduped_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v49_new_gbif_strict_core_gedi_canopy_v1"

GEDI_MIN_COUNTF = 10
GEDI_MAX_CANOPY_M = 100


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
    select_parts.append(f"    {build_gpp_expr('s')}")
    select_parts.append(f"    {build_nighttime_expr('s')}")
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
WHERE {build_row_filters('s')}
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v49 new_gbif strict-core with GEDI canopy")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print(f"Building v49 new_gbif strict-core GEDI canopy -> {args.dest_table}")
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
