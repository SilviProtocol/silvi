#!/usr/bin/env python3
"""Build the V4.1 preview training-grain table.

This is the training-ready companion to `sinr_v41_preview_strict_core_v1`.

- Labels / row grain come from `sinr_v3_unified_strict_train_v30_preview_clean`
- Features come from the repaired strict lineage
  `sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`

The result is one row per `(taxon_id, lat4, lon4, observation_year, emb_year)`.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery

import build_sinr_v41_preview_strict_core as preview_core


PROJECT = "treekipedia-479918"
DATASET = "species_data"

LABEL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
STRICT_SOURCE_TABLE = (
    f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v41_preview_strict_core_train_v1"

ROW_FILTERS = """
    NOT (s.bio01 = 0 AND s.bio02 = 0 AND s.bio12 = 0)
    AND (s.soil_ph IS NULL OR s.soil_ph != 0)
"""


def build_select_clause() -> str:
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
    select_parts.append(
        "    CASE "
        "WHEN s.modis_gpp_mean >= 65530 THEN NULL "
        "WHEN s.modis_gpp_mean IS NULL THEN NULL "
        "ELSE s.modis_gpp_mean END AS modis_gpp_mean"
    )
    select_parts.append(
        "    CASE WHEN p.observation_year < 2012 THEN NULL ELSE s.nighttime_lights END AS nighttime_lights"
    )
    return ",\n".join(select_parts)


def build_sql(dest_table: str) -> str:
    select_clause = build_select_clause()
    return f"""
CREATE OR REPLACE TABLE `{dest_table}` AS
SELECT
{select_clause}
FROM `{LABEL_TABLE}` p
JOIN `{STRICT_SOURCE_TABLE}` s
  ON ROUND(p.latitude, 4) = ROUND(s.latitude, 4)
 AND ROUND(p.longitude, 4) = ROUND(s.longitude, 4)
 AND p.observation_year = s.observation_year
 AND p.emb_year = s.emb_year
WHERE p.data_source = 'new_gbif'
  AND {ROW_FILTERS.strip()}
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V4.1 preview training-grain table")
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sql = build_sql(args.dest_table)
    if args.dry_run:
        print(sql)
        return

    client = bigquery.Client(project=PROJECT)
    print("Building V4.1 preview training-grain table...")
    print(f"  Labels:   {LABEL_TABLE}")
    print(f"  Features: {STRICT_SOURCE_TABLE}")
    print(f"  Dest:     {args.dest_table}")
    client.query(sql).result()

    verify_sql = f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT taxon_id) AS unique_species,
      COUNTIF(taxon_id IS NULL) AS null_taxon_ids
    FROM `{args.dest_table}`
    """
    row = next(client.query(verify_sql).result())
    print("\nBuilt V4.1 preview training-grain table")
    print(f"  rows:          {int(row.total_rows):,}")
    print(f"  unique species:{int(row.unique_species):,}")
    print(f"  null taxon_id: {int(row.null_taxon_ids):,}")


if __name__ == "__main__":
    main()
