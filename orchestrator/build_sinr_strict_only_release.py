#!/usr/bin/env python3
"""Build an enforced strict-only SINR training release.

This is intentionally conservative:
- only rows with release_gate_default='allow_strict_release' are included
- strict raw feature payload is preferred over preview payload
- preview-only feature families without strict raw provenance are nulled
- label/assertion metadata from preview is preserved where needed

This creates new release tables only. It does not mutate source tables.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

PREVIEW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
STRICT_RAW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
FIELD_TABLE = f"{PROJECT}.{DATASET}.sinr_occurrence_field_integrity_status_v1"
REGISTRY_TABLE = f"{PROJECT}.{DATASET}.sinr_release_registry_v1"
XIAO_CORRECTION_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_correction_overlay_v1"

UNSAFE_PREVIEW_FEATURE_ONLY_COLS = {
    "carbon_canopy_height_m",
    "spawn_agb",
    "spawn_agb_unc",
    "spawn_bgb",
    "spawn_bgb_unc",
    "gedi_l4b_agbd",
    "gedi_l4b_agbd_se",
    "gedi_rh98",
    "gedi_fhd",
    "soc_0cm",
    "soc_30cm",
    "soc_100cm",
    "soc_200cm",
    "ipcc_forest_class",
    "npp_at_obs",
    "gpp_at_obs",
    "lai_at_obs",
    "fpar_at_obs",
    "evi_at_obs",
    "cci_agb_at_obs",
    "cci_agb_sd_at_obs",
    "npp_at_ae",
    "gpp_at_ae",
    "lai_at_ae",
    "fpar_at_ae",
    "evi_at_ae",
    "cci_agb_at_ae",
    "cci_agb_sd_at_ae",
    "npp_mean_longterm",
    "npp_trend",
    "hilda_lulc_at_obs",
    "hilda_lulc_at_ae",
    "lulc_changed",
    "forest_to_nonforest",
    "has_hilda",
    "aridity_index",
    "aridity_index_raw",
    "et0_mm_yr",
    "et0_mm_yr_raw",
}


def quote(name: str) -> str:
    return f"`{name}`"


def bq_type(field_type: str) -> str:
    mapping = {
        "FLOAT": "FLOAT64",
        "INTEGER": "INT64",
        "BOOLEAN": "BOOL",
    }
    return mapping.get(field_type, field_type)


def build_release_sql(client: bigquery.Client, allowlist_table: str, release_table: str, release_id: str) -> str:
    preview_schema = client.get_table(PREVIEW_TABLE).schema
    strict_schema = client.get_table(STRICT_RAW_TABLE).schema

    preview_cols = [f.name for f in preview_schema]
    strict_cols = [f.name for f in strict_schema]
    strict_col_set = set(strict_cols)

    select_parts: list[str] = []

    for field in preview_schema:
        col = field.name
        if col in strict_col_set:
            if col == "xiao_planted_forest":
                select_parts.append(
                    f"COALESCE(x.corrected_xiao, s.{quote(col)}) AS {quote(col)}"
                )
            elif col == "modis_gpp_mean":
                select_parts.append(
                    "CASE WHEN p.observation_year < 2001 THEN CAST(NULL AS FLOAT64) "
                    f"ELSE s.{quote(col)} END AS {quote(col)}"
                )
            elif col == "geo":
                select_parts.append(f"s.{quote(col)} AS {quote(col)}")
            else:
                select_parts.append(f"s.{quote(col)} AS {quote(col)}")
        elif col in UNSAFE_PREVIEW_FEATURE_ONLY_COLS:
            select_parts.append(f"CAST(NULL AS {bq_type(field.field_type)}) AS {quote(col)}")
        else:
            select_parts.append(f"p.{quote(col)} AS {quote(col)}")

    select_parts.extend(
        [
            f"'{release_id}' AS release_id",
            "CURRENT_TIMESTAMP() AS release_created_at",
            "'strict_only_preview_backed' AS release_type",
            "f.release_gate_default AS release_gate_default",
            "f.identity_integrity_status AS identity_integrity_status",
            "f.payload_provenance_status AS payload_provenance_status",
            "f.temporal_validity_default AS temporal_validity_default",
            "f.feature_integrity_basis AS feature_integrity_basis",
        ]
    )

    select_sql = ",\n  ".join(select_parts)

    return f"""
    CREATE OR REPLACE TABLE `{release_table}` AS
    WITH strict_one AS (
      SELECT *
      FROM `{STRICT_RAW_TABLE}`
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4)), observation_year, emb_year
        ORDER BY `system:index`
      ) = 1
    ),
    xiao_one AS (
      SELECT
        lat4,
        lon4,
        emb_year,
        ANY_VALUE(corrected_xiao) AS corrected_xiao
      FROM `{XIAO_CORRECTION_TABLE}`
      GROUP BY 1,2,3
    )
    SELECT
      {select_sql}
    FROM `{PREVIEW_TABLE}` p
    JOIN `{allowlist_table}` f
      ON p.data_source = f.data_source
     AND p.taxon_id = f.taxon_id
     AND ROUND(p.latitude, 4) = f.lat4
     AND ROUND(p.longitude, 4) = f.lon4
     AND p.observation_year = f.observation_year
     AND p.emb_year = f.emb_year
    JOIN strict_one s
      ON ROUND(p.latitude, 4) = ROUND(s.latitude, 4)
     AND ROUND(p.longitude, 4) = ROUND(s.longitude, 4)
     AND p.observation_year = s.observation_year
     AND p.emb_year = s.emb_year
    LEFT JOIN xiao_one x
      ON ROUND(p.latitude, 4) = x.lat4
     AND ROUND(p.longitude, 4) = x.lon4
     AND p.emb_year = x.emb_year
    WHERE f.release_gate_default = 'allow_strict_release'
      AND p.data_source = 'new_gbif'
    """


def ensure_registry(client: bigquery.Client) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{REGISTRY_TABLE}` (
      release_id STRING,
      release_type STRING,
      bq_table STRING,
      status STRING,
      created_at TIMESTAMP,
      source_tables ARRAY<STRING>,
      schema_contract_version STRING,
      feature_contract_version STRING,
      split_contract_version STRING,
      mapping_contract_version STRING,
      notes STRING
    )
    """
    client.query(sql).result()


def insert_registry(client: bigquery.Client, release_id: str, release_table: str, allowlist_table: str) -> None:
    sql = f"""
    INSERT INTO `{REGISTRY_TABLE}`
    (release_id, release_type, bq_table, status, created_at, source_tables,
     schema_contract_version, feature_contract_version, split_contract_version,
     mapping_contract_version, notes)
    VALUES (
      '{release_id}',
      'strict_only_preview_backed',
      '{release_table}',
      'active',
      CURRENT_TIMESTAMP(),
      ['{PREVIEW_TABLE}', '{STRICT_RAW_TABLE}', '{FIELD_TABLE}', '{XIAO_CORRECTION_TABLE}', '{allowlist_table}'],
      'sinr_occurrence_field_integrity_status_v1',
      'strict_raw_plus_preview_labels_plus_xiao_overlay_plus_gpp_null_v3',
      'strict_only_allow_strict_release',
      'pending',
      'Enforced strict-only release: preview-backed labels/meta plus strict raw features with Xiao correction overlay applied; pre-2001 MODIS GPP is emitted as NULL instead of proxy zero; preview-only non-strict feature families nulled.'
    )
    """
    client.query(sql).result()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", default=None)
    args = parser.parse_args()

    release_id = args.release_id or datetime.now(timezone.utc).strftime("strict_only_%Y%m%d_%H%M%S")
    allowlist_table = f"{PROJECT}.{DATASET}.sinr_release_allowlist__{release_id}"
    release_table = f"{PROJECT}.{DATASET}.sinr_train_release__{release_id}"

    client = bigquery.Client(project=PROJECT)

    ensure_registry(client)
    client.get_table(XIAO_CORRECTION_TABLE)

    allowlist_sql = f"""
    CREATE OR REPLACE TABLE `{allowlist_table}` AS
    SELECT *
    FROM `{FIELD_TABLE}`
    WHERE release_gate_default = 'allow_strict_release'
    """
    client.query(allowlist_sql).result()

    release_sql = build_release_sql(client, allowlist_table, release_table, release_id)
    client.query(release_sql).result()
    insert_registry(client, release_id, release_table, allowlist_table)

    allowlist = client.get_table(allowlist_table)
    release = client.get_table(release_table)
    print(f"Created allowlist: {allowlist_table} rows={allowlist.num_rows:,}")
    print(f"Created release:   {release_table} rows={release.num_rows:,} cols={len(release.schema)}")


if __name__ == "__main__":
    main()
