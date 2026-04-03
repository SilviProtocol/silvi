#!/usr/bin/env python3
"""Build a non-destructive deduped strict new_gbif lineage and audits."""

from __future__ import annotations

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_v1"
DEDUPED_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_v1"
AUDIT_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_duplicate_audit_v1"
SUMMARY_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_duplicate_audit_summary_v1"


def build_audit_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{AUDIT_TABLE}` AS
    WITH grouped AS (
      SELECT
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year,
        COUNT(*) AS duplicate_group_size,
        ARRAY_AGG(`system:index` ORDER BY `system:index`) AS system_indexes,
        ARRAY_AGG(
          STRUCT(
            `system:index` AS system_index,
            CAST(xiao_planted_forest AS INT64) AS xiao_planted_forest,
            modis_gpp_mean,
            dynamic_world
          )
          ORDER BY `system:index`
        ) AS sample_rows
      FROM `{SOURCE_TABLE}`
      GROUP BY 1, 2, 3, 4
      HAVING COUNT(*) > 1
    )
    SELECT
      lat4,
      lon4,
      observation_year,
      emb_year,
      duplicate_group_size,
      system_indexes[OFFSET(0)] AS kept_system_index,
      ARRAY(
        SELECT idx
        FROM UNNEST(system_indexes) AS idx WITH OFFSET pos
        WHERE pos > 0
      ) AS dropped_system_indexes,
      sample_rows
    FROM grouped
    ORDER BY observation_year, emb_year, lat4, lon4
    """
    client.query(sql).result()


def build_deduped_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{DEDUPED_TABLE}` AS
    WITH ranked AS (
      SELECT
        t.*,
        ROW_NUMBER() OVER (
          PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4)), observation_year, emb_year
          ORDER BY `system:index`
        ) AS dedupe_rank
      FROM `{SOURCE_TABLE}` t
    )
    SELECT * EXCEPT(dedupe_rank)
    FROM ranked
    WHERE dedupe_rank = 1
    """
    client.query(sql).result()


def build_summary_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{SUMMARY_TABLE}` AS
    WITH duplicate_groups AS (
      SELECT
        observation_year,
        emb_year,
        COUNT(*) AS duplicate_context_groups,
        SUM(duplicate_group_size - 1) AS extra_duplicate_rows
      FROM `{AUDIT_TABLE}`
      GROUP BY observation_year, emb_year
    ),
    source_counts AS (
      SELECT
        COUNT(*) AS source_row_count,
        COUNT(DISTINCT CONCAT(
          CAST(ROUND(latitude, 4) AS STRING), '|',
          CAST(ROUND(longitude, 4) AS STRING), '|',
          CAST(observation_year AS STRING), '|',
          CAST(emb_year AS STRING)
        )) AS source_distinct_contexts
      FROM `{SOURCE_TABLE}`
    ),
    deduped_counts AS (
      SELECT
        COUNT(*) AS deduped_row_count,
        COUNT(DISTINCT CONCAT(
          CAST(ROUND(latitude, 4) AS STRING), '|',
          CAST(ROUND(longitude, 4) AS STRING), '|',
          CAST(observation_year AS STRING), '|',
          CAST(emb_year AS STRING)
        )) AS deduped_distinct_contexts
      FROM `{DEDUPED_TABLE}`
    )
    SELECT
      'global' AS summary_scope,
      NULL AS observation_year,
      NULL AS emb_year,
      (SELECT COUNT(*) FROM `{AUDIT_TABLE}`) AS duplicate_context_groups,
      (SELECT SUM(duplicate_group_size - 1) FROM `{AUDIT_TABLE}`) AS extra_duplicate_rows,
      (SELECT source_row_count FROM source_counts) AS source_row_count,
      (SELECT source_distinct_contexts FROM source_counts) AS source_distinct_contexts,
      (SELECT deduped_row_count FROM deduped_counts) AS deduped_row_count,
      (SELECT deduped_distinct_contexts FROM deduped_counts) AS deduped_distinct_contexts

    UNION ALL

    SELECT
      'year_pair' AS summary_scope,
      observation_year,
      emb_year,
      duplicate_context_groups,
      extra_duplicate_rows,
      NULL,
      NULL,
      NULL,
      NULL
    FROM duplicate_groups
    ORDER BY summary_scope, extra_duplicate_rows DESC, observation_year, emb_year
    """
    client.query(sql).result()


def verify(client: bigquery.Client) -> None:
    sql = f"""
    SELECT COUNT(*) AS duplicate_context_groups
    FROM (
      SELECT 1
      FROM `{DEDUPED_TABLE}`
      GROUP BY ROUND(latitude, 4), ROUND(longitude, 4), observation_year, emb_year
      HAVING COUNT(*) > 1
    )
    """
    duplicate_context_groups = int(next(client.query(sql).result()).duplicate_context_groups)
    if duplicate_context_groups != 0:
      raise RuntimeError(f"Deduped table still has {duplicate_context_groups} duplicate context groups")


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    client.get_table(SOURCE_TABLE)
    build_audit_table(client)
    build_deduped_table(client)
    build_summary_table(client)
    verify(client)

    audit = client.get_table(AUDIT_TABLE)
    deduped = client.get_table(DEDUPED_TABLE)
    summary = client.get_table(SUMMARY_TABLE)
    print(f"Created audit table:   {AUDIT_TABLE} rows={audit.num_rows:,}")
    print(f"Created deduped table: {DEDUPED_TABLE} rows={deduped.num_rows:,}")
    print(f"Created summary table: {SUMMARY_TABLE} rows={summary.num_rows:,}")


if __name__ == "__main__":
    main()
