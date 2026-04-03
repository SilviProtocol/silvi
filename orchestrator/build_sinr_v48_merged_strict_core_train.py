#!/usr/bin/env python3
"""Build the repaired post-D1 merged strict-core training-grain table."""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

LABEL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
NEW_GBIF_FEATURES = f"{PROJECT}.{DATASET}.sinr_v48_new_gbif_strict_core_repaired_v1"
BACKFILL_FEATURES = f"{PROJECT}.{DATASET}.sinr_v48_backfill_strict_core_repaired_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_merged_strict_core_train_v1"


def build_feature_projection(alias: str) -> str:
    prefix = f"{alias}."
    plain_cols = preview_core.build_column_list()
    select_parts = [f"        {prefix}{col} AS {col}" for col in plain_cols]
    select_parts.append(f"        {prefix}modis_gpp_mean AS modis_gpp_mean")
    select_parts.append(f"        {prefix}nighttime_lights AS nighttime_lights")
    return ",\n".join(select_parts)


def build_output_select() -> str:
    feature_cols = [c for c in preview_core.build_column_list() if c not in preview_core.META_COLS]
    select_parts = [
        "    p.data_source",
        "    p.taxon_id",
        "    p.latitude",
        "    p.longitude",
        "    p.observation_year",
        "    p.emb_year",
    ]
    select_parts.extend(f"    s.{col} AS {col}" for col in feature_cols)
    select_parts.append("    s.modis_gpp_mean")
    select_parts.append("    s.nighttime_lights")
    return ",\n".join(select_parts)


def build_sql(dest_table: str, replace: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE"
    output_select = build_output_select()
    new_proj = build_feature_projection("n")
    backfill_proj = build_feature_projection("b")
    return f"""
{create_clause} `{dest_table}` AS
WITH unified_features AS (
  SELECT
    'new_gbif' AS data_source,
{new_proj}
  FROM `{NEW_GBIF_FEATURES}` n
  UNION ALL
  SELECT
    'backfill' AS data_source,
{backfill_proj}
  FROM `{BACKFILL_FEATURES}` b
)
SELECT
{output_select}
FROM `{LABEL_TABLE}` p
JOIN unified_features s
  ON p.data_source = s.data_source
 AND ROUND(p.latitude, 4) = ROUND(s.latitude, 4)
 AND ROUND(p.longitude, 4) = ROUND(s.longitude, 4)
 AND p.observation_year = s.observation_year
 AND p.emb_year = s.emb_year
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build repaired post-D1 merged training-grain table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return
    client = bigquery.Client(project=PROJECT)
    print(f"Building repaired merged training table -> {args.dest_table}")
    client.query(sql).result()
    row = next(client.query(f"SELECT COUNT(*) AS n, COUNT(DISTINCT taxon_id) AS species FROM `{args.dest_table}`").result())
    print(f"  rows: {int(row.n):,}")
    print(f"  species: {int(row.species):,}")


if __name__ == "__main__":
    main()
