#!/usr/bin/env python3
"""Build cleaned patch and merged canonical lineages for repaired strict new_gbif rows."""

from __future__ import annotations

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

CURRENT_CANONICAL_TABLE = (
    f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_v1"
)
PATCH_RAW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_missing_patch_raw_v1"
PATCH_CLEAN_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_missing_patch_clean_v1"
MERGED_CANONICAL_TABLE = (
    f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
SUMMARY_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_patch_lineage_summary_v1"


def build_patch_clean_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{PATCH_CLEAN_TABLE}` AS
    SELECT
      p.* EXCEPT(xiao_planted_forest, modis_gpp_mean),
      p.xiao_planted_forest AS xiao_planted_forest_raw,
      p.xiao_planted_forest AS xiao_planted_forest,
      FALSE AS xiao_has_clean_lookup,
      FALSE AS xiao_value_changed,
      'strict_missing_context_reextract_v1' AS xiao_repair_source,
      CAST(NULL AS ARRAY<STRING>) AS xiao_lookup_sources,
      CAST(NULL AS INT64) AS xiao_lookup_source_row_count,
      p.modis_gpp_mean AS modis_gpp_mean_raw,
      CASE
        WHEN p.observation_year < 2001 THEN CAST(NULL AS FLOAT64)
        ELSE p.modis_gpp_mean
      END AS modis_gpp_mean,
      p.observation_year >= 2001 AS modis_gpp_available,
      CASE
        WHEN p.observation_year BETWEEN 2001 AND 2023 THEN p.observation_year
        WHEN p.observation_year > 2023 THEN 2023
        ELSE NULL
      END AS dataset_sample_year_modis_gpp,
      p.observation_year > 2023 AS dataset_year_is_fallback_modis_gpp,
      p.observation_year < 2001 AS modis_gpp_unavailable_pre_2001
    FROM `{PATCH_RAW_TABLE}` p
    """
    client.query(sql).result()


def build_merged_canonical_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{MERGED_CANONICAL_TABLE}` AS
    WITH unioned AS (
      SELECT * FROM `{CURRENT_CANONICAL_TABLE}`
      UNION ALL
      SELECT * FROM `{PATCH_CLEAN_TABLE}`
    )
    SELECT *
    FROM unioned
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4)), observation_year, emb_year
      ORDER BY CASE WHEN xiao_repair_source = 'strict_missing_context_reextract_v1' THEN 0 ELSE 1 END, `system:index`
    ) = 1
    """
    client.query(sql).result()


def build_summary_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{SUMMARY_TABLE}` AS
    WITH src AS (
      SELECT DISTINCT
        CAST(lat4dp AS FLOAT64) AS lat4,
        CAST(lon4dp AS FLOAT64) AS lon4,
        observation_year,
        emb_year
      FROM `{PROJECT}.{DATASET}.gbif_new_occurrences`
      WHERE observation_year IS NOT NULL
    ),
    merged AS (
      SELECT DISTINCT
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year
      FROM `{MERGED_CANONICAL_TABLE}`
    ),
    singletons AS (
      SELECT DISTINCT lat4, lon4, observation_year, emb_year
      FROM `{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_singleton_failures_v1`
    )
    SELECT
      (SELECT COUNT(*) FROM `{PATCH_RAW_TABLE}`) AS patch_raw_rows,
      (SELECT COUNT(*) FROM `{PATCH_CLEAN_TABLE}`) AS patch_clean_rows,
      (SELECT COUNT(*) FROM `{MERGED_CANONICAL_TABLE}`) AS merged_rows,
      (
        SELECT COUNT(*)
        FROM src s
        LEFT JOIN merged m USING (lat4, lon4, observation_year, emb_year)
        WHERE m.lat4 IS NULL
      ) AS missing_contexts_vs_source,
      (
        SELECT COUNT(*)
        FROM `{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_singleton_failures_v1`
      ) AS singleton_failure_count,
      (
        SELECT COUNT(*)
        FROM src s
        LEFT JOIN merged m USING (lat4, lon4, observation_year, emb_year)
        LEFT JOIN singletons f USING (lat4, lon4, observation_year, emb_year)
        WHERE m.lat4 IS NULL
          AND f.lat4 IS NULL
      ) AS effective_remaining_missing_contexts,
      (
        SELECT COUNT(*)
        FROM (
          SELECT 1
          FROM `{MERGED_CANONICAL_TABLE}`
          GROUP BY ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year
          HAVING COUNT(*) > 1
        )
      ) AS duplicate_context_groups
    """
    client.query(sql).result()


def verify(client: bigquery.Client) -> None:
    row = next(client.query(f"SELECT * FROM `{SUMMARY_TABLE}`").result())
    if int(row.duplicate_context_groups) != 0:
        raise RuntimeError(f"Merged canonical table still has {row.duplicate_context_groups} duplicate context groups")
    if int(row.effective_remaining_missing_contexts) != 0:
        raise RuntimeError(
            f"Merged canonical accounting still leaves {row.effective_remaining_missing_contexts} unresolved contexts"
        )


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    client.get_table(PATCH_RAW_TABLE)
    build_patch_clean_table(client)
    build_merged_canonical_table(client)
    build_summary_table(client)
    verify(client)

    patch_clean = client.get_table(PATCH_CLEAN_TABLE)
    merged = client.get_table(MERGED_CANONICAL_TABLE)
    summary = client.get_table(SUMMARY_TABLE)
    print(f"Created patch clean table: {PATCH_CLEAN_TABLE} rows={patch_clean.num_rows:,}")
    print(f"Created merged table:      {MERGED_CANONICAL_TABLE} rows={merged.num_rows:,}")
    print(f"Created summary table:     {SUMMARY_TABLE} rows={summary.num_rows:,}")


if __name__ == "__main__":
    main()
