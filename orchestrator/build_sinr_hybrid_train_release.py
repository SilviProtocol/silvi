#!/usr/bin/env python3
"""Build an enforced hybrid-train-only SINR release.

Includes:
- strict rows with effective_release_gate='allow_strict_release'
- explicitly approved hybrid rows with effective_release_gate='allow_hybrid_release'

No rows are included unless they pass the effective eligibility table.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

PREVIEW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
STRICT_RAW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
ELIGIBILITY_TABLE = f"{PROJECT}.{DATASET}.sinr_occurrence_release_eligibility_v1"
REGISTRY_TABLE = f"{PROJECT}.{DATASET}.sinr_release_registry_v1"
XIAO_CORRECTION_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_correction_overlay_v1"

UNSAFE_PREVIEW_FEATURE_ONLY_COLS = {
    "carbon_canopy_height_m", "spawn_agb", "spawn_agb_unc", "spawn_bgb", "spawn_bgb_unc",
    "gedi_l4b_agbd", "gedi_l4b_agbd_se", "gedi_rh98", "gedi_fhd", "soc_0cm", "soc_30cm",
    "soc_100cm", "soc_200cm", "ipcc_forest_class", "npp_at_obs", "gpp_at_obs", "lai_at_obs",
    "fpar_at_obs", "evi_at_obs", "cci_agb_at_obs", "cci_agb_sd_at_obs", "npp_at_ae", "gpp_at_ae",
    "lai_at_ae", "fpar_at_ae", "evi_at_ae", "cci_agb_at_ae", "cci_agb_sd_at_ae", "npp_mean_longterm",
    "npp_trend", "hilda_lulc_at_obs", "hilda_lulc_at_ae", "lulc_changed", "forest_to_nonforest",
    "has_hilda", "aridity_index", "aridity_index_raw", "et0_mm_yr", "et0_mm_yr_raw",
}


def quote(name: str) -> str:
    return f"`{name}`"


def bq_type(field_type: str) -> str:
    return {"FLOAT": "FLOAT64", "INTEGER": "INT64", "BOOLEAN": "BOOL"}.get(field_type, field_type)


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


def build_release_sql(client: bigquery.Client, allow_table: str, release_table: str, release_id: str) -> str:
    preview_schema = client.get_table(PREVIEW_TABLE).schema
    strict_col_set = set(f.name for f in client.get_table(STRICT_RAW_TABLE).schema)

    select_parts = []
    for field in preview_schema:
        col = field.name
        if col in strict_col_set:
            if col == "xiao_planted_forest":
                select_parts.append(
                    "CASE "
                    "WHEN e.effective_release_gate = 'allow_strict_release' THEN COALESCE(x.corrected_xiao, s.{col}) "
                    "ELSE p.{col} END AS {alias}".format(col=quote(col), alias=quote(col))
                )
            elif col == "modis_gpp_mean":
                select_parts.append(
                    "CASE "
                    "WHEN p.observation_year < 2001 THEN CAST(NULL AS FLOAT64) "
                    "WHEN e.effective_release_gate = 'allow_strict_release' THEN s.{col} "
                    "ELSE p.{col} END AS {alias}".format(col=quote(col), alias=quote(col))
                )
            else:
                select_parts.append(
                    "CASE "
                    "WHEN e.effective_release_gate = 'allow_strict_release' THEN s.{col} "
                    "ELSE p.{col} END AS {alias}".format(col=quote(col), alias=quote(col))
                )
        elif col in UNSAFE_PREVIEW_FEATURE_ONLY_COLS:
            select_parts.append(f"CAST(NULL AS {bq_type(field.field_type)}) AS {quote(col)}")
        else:
            select_parts.append(f"p.{quote(col)} AS {quote(col)}")

    select_parts.extend([
        f"'{release_id}' AS release_id",
        "CURRENT_TIMESTAMP() AS release_created_at",
        "'hybrid_train_only_preview_backed' AS release_type",
        "e.effective_release_gate AS effective_release_gate",
        "e.effective_override_scope AS effective_override_scope",
        "e.release_gate_default AS release_gate_default",
        "e.identity_integrity_status AS identity_integrity_status",
        "e.payload_provenance_status AS payload_provenance_status",
        "e.temporal_validity_default AS temporal_validity_default",
        "e.feature_integrity_basis AS feature_integrity_basis",
        "e.override_decision AS override_decision",
        "e.override_release_id AS override_release_id",
    ])
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
    JOIN `{allow_table}` e
      ON p.data_source = e.data_source
     AND p.taxon_id = e.taxon_id
     AND ROUND(p.latitude, 4) = e.lat4
     AND ROUND(p.longitude, 4) = e.lon4
     AND p.observation_year = e.observation_year
     AND p.emb_year = e.emb_year
    LEFT JOIN strict_one s
      ON ROUND(p.latitude, 4) = ROUND(s.latitude, 4)
     AND ROUND(p.longitude, 4) = ROUND(s.longitude, 4)
     AND p.observation_year = s.observation_year
     AND p.emb_year = s.emb_year
    LEFT JOIN xiao_one x
      ON ROUND(p.latitude, 4) = x.lat4
     AND ROUND(p.longitude, 4) = x.lon4
     AND p.emb_year = x.emb_year
    WHERE e.effective_release_gate IN ('allow_strict_release', 'allow_hybrid_release')
      AND p.data_source = 'new_gbif'
    """


def insert_registry(client: bigquery.Client, release_id: str, release_table: str, allow_table: str) -> None:
    sql = f"""
    INSERT INTO `{REGISTRY_TABLE}`
    (release_id, release_type, bq_table, status, created_at, source_tables,
     schema_contract_version, feature_contract_version, split_contract_version,
     mapping_contract_version, notes)
    VALUES (
      '{release_id}',
      'hybrid_train_only_preview_backed',
      '{release_table}',
      'active',
      CURRENT_TIMESTAMP(),
      ['{PREVIEW_TABLE}', '{STRICT_RAW_TABLE}', '{ELIGIBILITY_TABLE}', '{XIAO_CORRECTION_TABLE}', '{allow_table}'],
      'sinr_occurrence_release_eligibility_v1',
      'strict_raw_plus_preview_labels_plus_xiao_overlay_plus_gpp_null_v3',
      'hybrid_train_only_effective_release_gate',
      'pending',
      'Hybrid train-only release: includes strict rows and explicitly approved hybrid rows only, with Xiao correction overlay applied to strict rows and pre-2001 MODIS GPP emitted as NULL instead of proxy zero.'
    )
    """
    client.query(sql).result()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", default=None)
    args = parser.parse_args()

    release_id = args.release_id or datetime.now(timezone.utc).strftime("hybrid_train_only_%Y%m%d_%H%M%S")
    allow_table = f"{PROJECT}.{DATASET}.sinr_release_allowlist__{release_id}"
    release_table = f"{PROJECT}.{DATASET}.sinr_train_release__{release_id}"

    client = bigquery.Client(project=PROJECT)
    ensure_registry(client)
    client.get_table(XIAO_CORRECTION_TABLE)

    allow_sql = f"""
    CREATE OR REPLACE TABLE `{allow_table}` AS
    SELECT *
    FROM `{ELIGIBILITY_TABLE}`
    WHERE effective_release_gate IN ('allow_strict_release', 'allow_hybrid_release')
    """
    client.query(allow_sql).result()
    client.query(build_release_sql(client, allow_table, release_table, release_id)).result()
    insert_registry(client, release_id, release_table, allow_table)

    allow_tbl = client.get_table(allow_table)
    release_tbl = client.get_table(release_table)
    print(f"Created allowlist: {allow_table} rows={allow_tbl.num_rows:,}")
    print(f"Created release:   {release_table} rows={release_tbl.num_rows:,} cols={len(release_tbl.schema)}")


if __name__ == "__main__":
    main()
