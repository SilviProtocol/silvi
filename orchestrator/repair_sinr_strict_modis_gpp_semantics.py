#!/usr/bin/env python3
"""Build a non-destructive strict new_gbif table with clean MODIS GPP semantics."""

from __future__ import annotations

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_v1"
OUTPUT_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_v1"
SUMMARY_TABLE = f"{PROJECT}.{DATASET}.sinr_modis_gpp_semantic_summary_v1"


def build_output_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{OUTPUT_TABLE}` AS
    SELECT
      t.* EXCEPT(modis_gpp_mean),
      t.modis_gpp_mean AS modis_gpp_mean_raw,
      CASE
        WHEN t.observation_year < 2001 THEN CAST(NULL AS FLOAT64)
        ELSE t.modis_gpp_mean
      END AS modis_gpp_mean,
      t.observation_year >= 2001 AS modis_gpp_available,
      CASE
        WHEN t.observation_year BETWEEN 2001 AND 2023 THEN t.observation_year
        WHEN t.observation_year > 2023 THEN 2023
        ELSE NULL
      END AS dataset_sample_year_modis_gpp,
      t.observation_year > 2023 AS dataset_year_is_fallback_modis_gpp,
      t.observation_year < 2001 AS modis_gpp_unavailable_pre_2001
    FROM `{SOURCE_TABLE}` t
    """
    client.query(sql).result()


def build_summary_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{SUMMARY_TABLE}` AS
    SELECT
      observation_year,
      COUNT(*) AS row_count,
      COUNTIF(modis_gpp_mean IS NULL) AS gpp_null_rows,
      COUNTIF(modis_gpp_available) AS gpp_available_rows,
      COUNTIF(modis_gpp_unavailable_pre_2001) AS gpp_pre_2001_rows,
      COUNTIF(dataset_year_is_fallback_modis_gpp) AS gpp_fallback_rows,
      MIN(modis_gpp_mean_raw) AS min_gpp_raw,
      MAX(modis_gpp_mean_raw) AS max_gpp_raw
    FROM `{OUTPUT_TABLE}`
    GROUP BY observation_year
    ORDER BY observation_year
    """
    client.query(sql).result()


def verify(client: bigquery.Client) -> None:
    sql = f"""
    SELECT
      COUNTIF(observation_year < 2001 AND modis_gpp_mean IS NOT NULL) AS bad_pre_2001_rows,
      COUNTIF(observation_year >= 2001 AND modis_gpp_mean IS NULL) AS bad_post_2000_rows
    FROM `{OUTPUT_TABLE}`
    """
    row = next(client.query(sql).result())
    if int(row.bad_pre_2001_rows) != 0:
        raise RuntimeError(f"Found {row.bad_pre_2001_rows} pre-2001 rows with non-null GPP")
    if int(row.bad_post_2000_rows) != 0:
        raise RuntimeError(f"Found {row.bad_post_2000_rows} 2001+ rows with null GPP")


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    client.get_table(SOURCE_TABLE)
    build_output_table(client)
    build_summary_table(client)
    verify(client)

    output = client.get_table(OUTPUT_TABLE)
    summary = client.get_table(SUMMARY_TABLE)
    print(f"Created repaired table:  {OUTPUT_TABLE} rows={output.num_rows:,} cols={len(output.schema)}")
    print(f"Created summary table:   {SUMMARY_TABLE} rows={summary.num_rows:,}")


if __name__ == "__main__":
    main()
