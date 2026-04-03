#!/usr/bin/env python3
"""Build the V4.7 fast-safe merged strict-core training-grain table.

This merges:
1. new_gbif repaired strict lineage (`...completed_v1`), projected onto the
   same strict-core feature surface used in V4.1
2. repaired backfill strict-core lineage (`sinr_v47_backfill_strict_core_v1`)

The result is trainer-ready and non-destructive: labels remain sourced from the
canonical training-grain table while features come from versioned strict-core
lineage tables.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

LABEL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
NEW_GBIF_FEATURES = (
    f"{PROJECT}.{DATASET}."
    "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
BACKFILL_STRICT_CORE = f"{PROJECT}.{DATASET}.sinr_v47_backfill_strict_core_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v47_merged_strict_core_train_v2"


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


def build_feature_projection(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    plain_cols = preview_core.build_column_list()
    select_parts = [f"        {prefix}{col} AS {col}" for col in plain_cols]
    select_parts.append(f"        {build_gpp_expr(alias)}")
    select_parts.append(f"        {build_nighttime_expr(alias)}")
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
    feature_projection = build_feature_projection()
    output_select = build_output_select()

    return f"""
{create_clause} `{dest_table}` AS
WITH new_gbif_features AS (
    SELECT
{feature_projection}
    FROM `{NEW_GBIF_FEATURES}`
    WHERE {build_row_filters()}
),
unified_features AS (
    SELECT
        'new_gbif' AS data_source,
        *
    FROM new_gbif_features

    UNION ALL

    SELECT
        'backfill' AS data_source,
        *
    FROM `{BACKFILL_STRICT_CORE}`
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
    parser = argparse.ArgumentParser(description="Build V4.7 merged training-grain table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table, replace=args.replace)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print("Building V4.7 fast-safe merged training-grain table...")
    print(f"  Labels:            {LABEL_TABLE}")
    print(f"  new_gbif features: {NEW_GBIF_FEATURES}")
    print(f"  backfill features: {BACKFILL_STRICT_CORE}")
    print(f"  Dest:              {args.dest_table}")

    client.query(sql).result()

    verify_sql = f"""
    WITH label_counts AS (
      SELECT data_source, COUNT(*) AS label_rows
      FROM `{LABEL_TABLE}`
      WHERE data_source IN ('new_gbif', 'backfill')
      GROUP BY data_source
    ),
    dest_counts AS (
      SELECT data_source, COUNT(*) AS dest_rows, COUNT(DISTINCT taxon_id) AS unique_species
      FROM `{args.dest_table}`
      GROUP BY data_source
    ),
    dupes AS (
      SELECT COUNT(*) AS dup_groups
      FROM (
        SELECT 1
        FROM `{args.dest_table}`
        GROUP BY data_source, taxon_id, ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year
        HAVING COUNT(*) > 1
      )
    ),
    null_stats AS (
      SELECT COUNTIF(taxon_id IS NULL) AS null_taxon_ids
      FROM `{args.dest_table}`
    )
    SELECT
      l.data_source,
      l.label_rows,
      d.dest_rows,
      d.unique_species,
      n.null_taxon_ids,
      g.dup_groups
    FROM label_counts l
    LEFT JOIN dest_counts d USING (data_source)
    CROSS JOIN null_stats n
    CROSS JOIN dupes g
    ORDER BY l.data_source
    """
    rows = list(client.query(verify_sql).result())

    total_row = next(
        client.query(
            f"SELECT COUNT(*) AS total_rows, COUNT(DISTINCT taxon_id) AS total_species FROM `{args.dest_table}`"
        ).result()
    )

    print("\nBuilt V4.7 fast-safe merged training-grain table")
    for row in rows:
        coverage = 0.0
        if row.label_rows:
            coverage = 100.0 * int(row.dest_rows or 0) / int(row.label_rows)
        print(
            f"  [{row.data_source}] labels={int(row.label_rows):,} | "
            f"train={int(row.dest_rows or 0):,} | species={int(row.unique_species or 0):,} | "
            f"coverage={coverage:.2f}%"
        )
    print(f"  total rows:       {int(total_row.total_rows):,}")
    print(f"  total species:    {int(total_row.total_species):,}")
    print(f"  null taxon ids:   {int(rows[0].null_taxon_ids if rows else 0):,}")
    print(f"  duplicate groups: {int(rows[0].dup_groups if rows else 0):,}")


if __name__ == "__main__":
    main()
