#!/usr/bin/env python3
"""Build the v49 merged strict-core training table with canopy-only GEDI overlay."""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

LABEL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
NEW_GBIF_FEATURES = f"{PROJECT}.{DATASET}.sinr_v49_new_gbif_strict_core_gedi_canopy_v1"
BACKFILL_FEATURES = f"{PROJECT}.{DATASET}.sinr_v49_backfill_strict_core_gedi_canopy_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v49_merged_strict_core_train_v1"


def build_extended_feature_cols() -> list[str]:
    return preview_core.build_column_list() + [
        "modis_gpp_mean",
        "nighttime_lights",
        "gedi_canopy_height_m",
        "gedi_canopy_countf",
    ]


def build_feature_projection(alias: str) -> str:
    prefix = f"{alias}."
    return ",\n".join(
        f"        {prefix}{col} AS {col}" for col in build_extended_feature_cols()
    )


def build_output_select() -> str:
    feature_cols = [
        col for col in build_extended_feature_cols() if col not in preview_core.META_COLS
    ]
    select_parts = [
        "    p.data_source",
        "    p.taxon_id",
        "    p.latitude",
        "    p.longitude",
        "    p.observation_year",
        "    p.emb_year",
    ]
    select_parts.extend(f"    s.{col} AS {col}" for col in feature_cols)
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
    parser = argparse.ArgumentParser(description="Build v49 merged training table with GEDI canopy")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print(f"Building v49 merged training table -> {args.dest_table}")
    client.query(sql).result()
    row = next(
        client.query(
            f"SELECT COUNT(*) AS n, COUNT(DISTINCT taxon_id) AS species, "
            f"COUNTIF(gedi_canopy_height_m IS NOT NULL) AS canopy_rows "
            f"FROM `{args.dest_table}`"
        ).result()
    )
    print(f"  rows: {int(row.n):,}")
    print(f"  species: {int(row.species):,}")
    print(f"  canopy rows: {int(row.canopy_rows):,}")


if __name__ == "__main__":
    main()
