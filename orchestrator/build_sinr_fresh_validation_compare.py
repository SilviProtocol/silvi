#!/usr/bin/env python3
"""Build comparison tables for fresh validation extraction results."""

from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
PREVIEW = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"
STRICT_RAW = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full"
LEGACY_NEW = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif"
LEGACY_BACKFILL = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill"
ELIGIBILITY = f"{PROJECT}.{DATASET}.sinr_occurrence_release_eligibility_v1"

KEY_EXCLUDE = {"latitude", "longitude", "observation_year", "emb_year", "geo", "system:index"}


def quoted(cols: list[str], alias: str) -> str:
    return ", ".join(f"{alias}.`{c}`" for c in cols)


def make_hash(alias: str, cols: list[str]) -> str:
    if not cols:
        return "NULL"
    return f"TO_HEX(SHA256(TO_JSON_STRING(STRUCT({quoted(cols, alias)}))))"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--batch-table", required=True)
    p.add_argument("--fresh-table", required=True)
    p.add_argument("--compare-table", required=True)
    args = p.parse_args()

    client = bigquery.Client(project=PROJECT)
    fresh_schema = client.get_table(args.fresh_table).schema
    preview_schema = client.get_table(PREVIEW).schema
    strict_schema = client.get_table(STRICT_RAW).schema

    fresh_cols = [f.name for f in fresh_schema if f.name not in KEY_EXCLUDE]
    preview_cols = [f.name for f in preview_schema if f.name not in KEY_EXCLUDE]
    strict_cols = [f.name for f in strict_schema if f.name not in KEY_EXCLUDE]

    fresh_preview_common = sorted(set(fresh_cols) & set(preview_cols))
    fresh_strict_common = sorted(set(fresh_cols) & set(strict_cols))

    sql = f"""
    CREATE OR REPLACE TABLE `{args.compare_table}` AS
    WITH batch AS (
      SELECT * FROM `{args.batch_table}`
    ),
    fresh_one AS (
      SELECT *
      FROM `{args.fresh_table}`
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4)), observation_year, emb_year
        ORDER BY `system:index`
      ) = 1
    ),
    strict_one AS (
      SELECT *
      FROM `{STRICT_RAW}`
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4)), observation_year, emb_year
        ORDER BY `system:index`
      ) = 1
    ),
    legacy_new_one AS (
      SELECT ROUND(latitude,4) AS lat4, ROUND(longitude,4) AS lon4, observation_year, emb_year, COUNT(*) legacy_new_count
      FROM `{LEGACY_NEW}` GROUP BY 1,2,3,4
    ),
    legacy_backfill_one AS (
      SELECT ROUND(latitude,4) AS lat4, ROUND(longitude,4) AS lon4, observation_year, emb_year, COUNT(*) legacy_backfill_count
      FROM `{LEGACY_BACKFILL}` GROUP BY 1,2,3,4
    )
    SELECT
      b.*, 
      e.effective_release_gate AS eligibility_effective_release_gate,
      e.identity_integrity_status AS eligibility_identity_integrity_status,
      e.payload_provenance_status AS eligibility_payload_provenance_status,
      e.temporal_validity_default AS eligibility_temporal_validity_default,
      CASE WHEN f.latitude IS NOT NULL THEN TRUE ELSE FALSE END AS has_fresh_extract,
      CASE WHEN s.latitude IS NOT NULL THEN TRUE ELSE FALSE END AS has_current_strict_raw,
      CASE WHEN p.data_source IS NOT NULL THEN TRUE ELSE FALSE END AS has_preview_row,
      COALESCE(ln.legacy_new_count, 0) AS legacy_new_count,
      COALESCE(lb.legacy_backfill_count, 0) AS legacy_backfill_count,
      {make_hash('f', fresh_preview_common)} AS fresh_preview_overlap_hash_fresh,
      {make_hash('p', fresh_preview_common)} AS fresh_preview_overlap_hash_preview,
      {make_hash('f', fresh_strict_common)} AS fresh_strict_overlap_hash_fresh,
      {make_hash('s', fresh_strict_common)} AS fresh_strict_overlap_hash_strict,
      CASE
        WHEN f.latitude IS NULL OR p.data_source IS NULL THEN NULL
        WHEN {make_hash('f', fresh_preview_common)} = {make_hash('p', fresh_preview_common)} THEN TRUE
        ELSE FALSE
      END AS fresh_vs_preview_overlap_match,
      CASE
        WHEN f.latitude IS NULL OR s.latitude IS NULL THEN NULL
        WHEN {make_hash('f', fresh_strict_common)} = {make_hash('s', fresh_strict_common)} THEN TRUE
        ELSE FALSE
      END AS fresh_vs_strict_overlap_match
    FROM batch b
    LEFT JOIN `{ELIGIBILITY}` e
      ON b.occurrence_example_id = e.occurrence_example_id
    LEFT JOIN fresh_one f
      ON b.lat4 = ROUND(f.latitude,4)
     AND b.lon4 = ROUND(f.longitude,4)
     AND b.observation_year = f.observation_year
     AND b.emb_year = f.emb_year
    LEFT JOIN strict_one s
      ON b.lat4 = ROUND(s.latitude,4)
     AND b.lon4 = ROUND(s.longitude,4)
     AND b.observation_year = s.observation_year
     AND b.emb_year = s.emb_year
    LEFT JOIN `{PREVIEW}` p
      ON b.data_source = p.data_source
     AND b.taxon_id = p.taxon_id
     AND b.lat4 = ROUND(p.latitude,4)
     AND b.lon4 = ROUND(p.longitude,4)
     AND b.observation_year = p.observation_year
     AND b.emb_year = p.emb_year
    LEFT JOIN legacy_new_one ln
      ON b.lat4 = ln.lat4 AND b.lon4 = ln.lon4 AND b.observation_year = ln.observation_year AND b.emb_year = ln.emb_year
    LEFT JOIN legacy_backfill_one lb
      ON b.lat4 = lb.lat4 AND b.lon4 = lb.lon4 AND b.observation_year = lb.observation_year AND b.emb_year = lb.emb_year
    """

    client.query(sql).result()
    table = client.get_table(args.compare_table)
    print(f"Created compare table: {args.compare_table} rows={table.num_rows:,} cols={len(table.schema)}")


if __name__ == "__main__":
    main()
