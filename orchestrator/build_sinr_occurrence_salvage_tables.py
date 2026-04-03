#!/usr/bin/env python3
"""Build non-destructive SINR occurrence-grain salvage tables in BigQuery.

Creates derived audit tables only. Does not mutate legacy or strict source tables.
"""

from __future__ import annotations

from google.cloud import bigquery
from google.api_core.exceptions import NotFound


PROJECT = "treekipedia-479918"
DATASET = "species_data"

UNIFIED_SOURCE = "sinr_occurrence_unified_source_v1"
SALVAGE_STATUS = "sinr_occurrence_salvage_status_v1"
SALVAGE_CANDIDATES = "sinr_occurrence_salvage_candidates_v1"
SALVAGE_AUDIT_SAMPLE = "sinr_occurrence_salvage_audit_sample_v1"
SALVAGE_AUDIT_SAMPLE_LEGACY = "sinr_occurrence_salvage_audit_sample_legacy90_v1"
SALVAGE_SUMMARY = "sinr_occurrence_salvage_summary_v1"


def table_exists(client: bigquery.Client, table_name: str) -> bool:
    try:
        client.get_table(f"{PROJECT}.{DATASET}.{table_name}")
        return True
    except NotFound:
        return False


def qname(table_name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table_name}`"


def run_query(client: bigquery.Client, sql: str, label: str) -> None:
    print(f"\n=== {label} ===")
    client.query(sql).result()
    print("done")


def main() -> None:
    client = bigquery.Client(project=PROJECT)

    strict_new_exists = table_exists(client, "sinr_v3_features_new_gbif_strict_full")
    strict_backfill_exists = table_exists(client, "sinr_v3_features_backfill_strict_full")

    if not strict_new_exists:
        raise RuntimeError("Missing required table: sinr_v3_features_new_gbif_strict_full")

    strict_parts = []
    if strict_new_exists:
        strict_parts.append(
            f"""
            SELECT
              'new_gbif' AS data_source,
              ROUND(latitude, 4) AS lat4,
              ROUND(longitude, 4) AS lon4,
              observation_year,
              emb_year,
              COUNT(*) AS strict_exact_match_count
            FROM {qname('sinr_v3_features_new_gbif_strict_full')}
            GROUP BY 1,2,3,4,5
            """
        )
    if strict_backfill_exists:
        strict_parts.append(
            f"""
            SELECT
              'backfill' AS data_source,
              ROUND(latitude, 4) AS lat4,
              ROUND(longitude, 4) AS lon4,
              observation_year,
              emb_year,
              COUNT(*) AS strict_exact_match_count
            FROM {qname('sinr_v3_features_backfill_strict_full')}
            GROUP BY 1,2,3,4,5
            """
        )
    strict_contexts_sql = "\nUNION ALL\n".join(strict_parts)

    unified_source_sql = f"""
    CREATE OR REPLACE TABLE {qname(UNIFIED_SOURCE)} AS
    WITH new_gbif AS (
      SELECT DISTINCT
        TO_HEX(SHA256(CONCAT(
          'new_gbif|',
          COALESCE(taxon_id, ''), '|',
          COALESCE(CAST(decimallatitude AS STRING), ''), '|',
          COALESCE(CAST(decimallongitude AS STRING), ''), '|',
          COALESCE(CAST(observation_year AS STRING), ''), '|',
          COALESCE(CAST(emb_year AS STRING), ''), '|',
          COALESCE(CAST(gbif_species_key AS STRING), ''), '|',
          COALESCE(basis_of_record, ''), '|',
          COALESCE(establishmentmeans, '')
        ))) AS occurrence_example_id,
        'new_gbif' AS data_source,
        'species_data.gbif_new_occurrences' AS source_table,
        taxon_id,
        species_name,
        CAST(gbif_species_key AS STRING) AS source_native_id,
        decimallatitude AS latitude,
        decimallongitude AS longitude,
        lat4dp AS lat4,
        lon4dp AS lon4,
        observation_year,
        emb_year,
        coord_uncertainty_m AS coordinate_uncertainty_m,
        establishmentmeans AS establishment_means,
        basis_of_record,
        FALSE AS source_year_missing
      FROM {qname('gbif_new_occurrences')}
      WHERE observation_year IS NOT NULL
    ),
    backfill AS (
      SELECT DISTINCT
        TO_HEX(SHA256(CONCAT(
          'backfill|',
          COALESCE(taxon_id, ''), '|',
          COALESCE(CAST(latitude AS STRING), ''), '|',
          COALESCE(CAST(longitude AS STRING), ''), '|',
          COALESCE(CAST(occurrence_year AS STRING), ''), '|',
          COALESCE(CAST(emb_year AS STRING), '')
        ))) AS occurrence_example_id,
        'backfill' AS data_source,
        'species_data.existing_training_coords' AS source_table,
        taxon_id,
        CAST(NULL AS STRING) AS species_name,
        CAST(NULL AS STRING) AS source_native_id,
        latitude,
        longitude,
        lat4dp AS lat4,
        lon4dp AS lon4,
        occurrence_year AS observation_year,
        emb_year,
        CAST(NULL AS FLOAT64) AS coordinate_uncertainty_m,
        CAST(NULL AS STRING) AS establishment_means,
        CAST(NULL AS STRING) AS basis_of_record,
        FALSE AS source_year_missing
      FROM {qname('existing_training_coords')}
      WHERE occurrence_year IS NOT NULL
    )
    SELECT * FROM new_gbif
    UNION ALL
    SELECT * FROM backfill
    """
    run_query(client, unified_source_sql, UNIFIED_SOURCE)

    salvage_status_sql = f"""
    CREATE OR REPLACE TABLE {qname(SALVAGE_STATUS)} AS
    WITH source_coord_stats AS (
      SELECT
        data_source,
        lat4,
        lon4,
        COUNT(DISTINCT observation_year) AS source_coord_year_count
      FROM {qname(UNIFIED_SOURCE)}
      GROUP BY 1,2,3
    ),
    source_context_stats AS (
      SELECT
        data_source,
        lat4,
        lon4,
        observation_year,
        emb_year,
        COUNT(DISTINCT taxon_id) AS source_taxa_at_context,
        COUNT(*) AS source_rows_at_context
      FROM {qname(UNIFIED_SOURCE)}
      GROUP BY 1,2,3,4,5
    ),
    legacy_contexts AS (
      SELECT
        'new_gbif' AS data_source,
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year,
        COUNT(*) AS legacy_exact_match_count
      FROM {qname('sinr_v3_features_new_gbif')}
      GROUP BY 1,2,3,4,5
      UNION ALL
      SELECT
        'backfill' AS data_source,
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year,
        COUNT(*) AS legacy_exact_match_count
      FROM {qname('sinr_v3_features_backfill')}
      GROUP BY 1,2,3,4,5
    ),
    strict_contexts AS (
      {strict_contexts_sql}
    ),
    preview_matches AS (
      SELECT
        data_source,
        taxon_id,
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year,
        COUNT(*) AS preview_exact_match_count
      FROM {qname('sinr_v3_unified_strict_train_v30_preview_clean')}
      GROUP BY 1,2,3,4,5,6
    )
    SELECT
      u.*,
      COALESCE(sc.source_coord_year_count, 0) AS source_coord_year_count,
      COALESCE(sctx.source_taxa_at_context, 0) AS source_taxa_at_context,
      COALESCE(sctx.source_rows_at_context, 0) AS source_rows_at_context,
      COALESCE(l.legacy_exact_match_count, 0) AS legacy_exact_match_count,
      COALESCE(st.strict_exact_match_count, 0) AS strict_exact_match_count,
      COALESCE(pm.preview_exact_match_count, 0) AS preview_exact_match_count,
      COALESCE(l.legacy_exact_match_count, 0) > 0 AS has_legacy_context,
      COALESCE(st.strict_exact_match_count, 0) > 0 AS has_strict_context,
      COALESCE(pm.preview_exact_match_count, 0) > 0 AS in_preview_train,
      sc.source_coord_year_count = 1 AS source_is_single_year_coordinate,
      {str(strict_backfill_exists).upper()} AS strict_backfill_table_present,
      CASE
        WHEN COALESCE(st.strict_exact_match_count, 0) > 0 THEN 'strict_context_present'
        WHEN COALESCE(l.legacy_exact_match_count, 0) = 0 THEN 'needs_reextract'
        WHEN COALESCE(l.legacy_exact_match_count, 0) > 1 THEN 'ambiguous_legacy_duplicate'
        WHEN COALESCE(sc.source_coord_year_count, 0) > 1 THEN 'ambiguous_multi_year'
        ELSE 'legacy_unverified'
      END AS context_quality_status
    FROM {qname(UNIFIED_SOURCE)} u
    LEFT JOIN source_coord_stats sc
      ON u.data_source = sc.data_source
     AND u.lat4 = sc.lat4
     AND u.lon4 = sc.lon4
    LEFT JOIN source_context_stats sctx
      ON u.data_source = sctx.data_source
     AND u.lat4 = sctx.lat4
     AND u.lon4 = sctx.lon4
     AND u.observation_year = sctx.observation_year
     AND u.emb_year = sctx.emb_year
    LEFT JOIN legacy_contexts l
      ON u.data_source = l.data_source
     AND u.lat4 = l.lat4
     AND u.lon4 = l.lon4
     AND u.observation_year = l.observation_year
     AND u.emb_year = l.emb_year
    LEFT JOIN strict_contexts st
      ON u.data_source = st.data_source
     AND u.lat4 = st.lat4
     AND u.lon4 = st.lon4
     AND u.observation_year = st.observation_year
     AND u.emb_year = st.emb_year
    LEFT JOIN preview_matches pm
      ON u.data_source = pm.data_source
     AND u.taxon_id = pm.taxon_id
     AND u.lat4 = pm.lat4
     AND u.lon4 = pm.lon4
     AND u.observation_year = pm.observation_year
     AND u.emb_year = pm.emb_year
    """
    run_query(client, salvage_status_sql, SALVAGE_STATUS)

    salvage_candidates_sql = f"""
    CREATE OR REPLACE TABLE {qname(SALVAGE_CANDIDATES)} AS
    SELECT *
    FROM {qname(SALVAGE_STATUS)}
    WHERE context_quality_status IN ('strict_context_present', 'legacy_unverified')
    """
    run_query(client, salvage_candidates_sql, SALVAGE_CANDIDATES)

    salvage_audit_sample_sql = f"""
    CREATE OR REPLACE TABLE {qname(SALVAGE_AUDIT_SAMPLE)} AS
    SELECT *
    FROM {qname(SALVAGE_STATUS)}
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY data_source, context_quality_status
      ORDER BY RAND()
    ) <= 1000
    """
    run_query(client, salvage_audit_sample_sql, SALVAGE_AUDIT_SAMPLE)

    salvage_audit_sample_legacy_sql = f"""
    CREATE OR REPLACE TABLE {qname(SALVAGE_AUDIT_SAMPLE_LEGACY)} AS
    WITH prioritized AS (
      SELECT *
      FROM {qname(SALVAGE_STATUS)}
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY data_source, context_quality_status
        ORDER BY RAND()
      ) <= CASE
        WHEN data_source = 'backfill' AND context_quality_status = 'legacy_unverified' THEN 2250
        WHEN data_source = 'backfill' AND context_quality_status = 'needs_reextract' THEN 2250
        WHEN data_source = 'backfill' AND context_quality_status = 'ambiguous_multi_year' THEN 2250
        WHEN data_source = 'backfill' AND context_quality_status = 'ambiguous_legacy_duplicate' THEN 2250
        WHEN data_source = 'new_gbif' AND context_quality_status = 'strict_context_present' THEN 200
        WHEN data_source = 'new_gbif' AND context_quality_status = 'legacy_unverified' THEN 200
        WHEN data_source = 'new_gbif' AND context_quality_status = 'needs_reextract' THEN 200
        WHEN data_source = 'new_gbif' AND context_quality_status = 'ambiguous_multi_year' THEN 200
        WHEN data_source = 'new_gbif' AND context_quality_status = 'ambiguous_legacy_duplicate' THEN 200
        ELSE 0
      END
    )
    SELECT * FROM prioritized
    """
    run_query(client, salvage_audit_sample_legacy_sql, SALVAGE_AUDIT_SAMPLE_LEGACY)

    salvage_summary_sql = f"""
    CREATE OR REPLACE TABLE {qname(SALVAGE_SUMMARY)} AS
    SELECT
      data_source,
      context_quality_status,
      COUNT(*) AS row_count,
      COUNTIF(in_preview_train) AS rows_in_preview_train,
      COUNTIF(has_strict_context) AS rows_with_strict_context,
      COUNTIF(has_legacy_context) AS rows_with_legacy_context,
      COUNTIF(source_is_single_year_coordinate) AS rows_single_year_coordinate,
      COUNT(DISTINCT FORMAT('%s|%.4f|%.4f|%d|%d', data_source, lat4, lon4, observation_year, emb_year)) AS distinct_contexts
    FROM {qname(SALVAGE_STATUS)}
    GROUP BY 1,2
    ORDER BY 1,2
    """
    run_query(client, salvage_summary_sql, SALVAGE_SUMMARY)

    print("\nCreated tables:")
    for t in [UNIFIED_SOURCE, SALVAGE_STATUS, SALVAGE_CANDIDATES, SALVAGE_AUDIT_SAMPLE, SALVAGE_AUDIT_SAMPLE_LEGACY, SALVAGE_SUMMARY]:
        full = f"{PROJECT}.{DATASET}.{t}"
        table = client.get_table(full)
        print(f"- {full}: rows={table.num_rows:,}, cols={len(table.schema)}")


if __name__ == "__main__":
    main()
