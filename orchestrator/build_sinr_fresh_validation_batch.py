#!/usr/bin/env python3
"""Build a randomized stratified fresh-extraction validation batch.

Goal: sample mostly low-certainty / high-risk rows for fresh re-extraction checks,
with a smaller strict-control slice.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
SOURCE = f"`{PROJECT}.{DATASET}.sinr_occurrence_release_eligibility_v1`"


SQL_TEMPLATE = """
CREATE OR REPLACE TABLE `{target_table}` AS
WITH base AS (
  SELECT
    occurrence_example_id,
    data_source,
    taxon_id,
    latitude,
    longitude,
    lat4,
    lon4,
    observation_year,
    emb_year,
    context_quality_status,
    feature_integrity_basis,
    release_gate_default,
    effective_release_gate,
    identity_integrity_status,
    payload_provenance_status,
    temporal_validity_default,
    occurrence_source_class_hint,
    occurrence_source_hint_confidence,
    xiao_provenance_status,
    xiao_bug_window_flag,
    land_state_train_ok,
    land_state_serve_parity_ok,
    aridity_family_serve_ok,
    carbon_family_serve_ok,
    hilda_family_serve_ok,
    requires_manual_audit_override,
    CASE
      WHEN data_source = 'backfill' AND release_gate_default = 'block_pending_audit_override' THEN 'high_risk_backfill_candidate'
      WHEN data_source = 'new_gbif' AND release_gate_default = 'block_pending_audit_override' THEN 'high_risk_new_gbif_candidate'
      WHEN data_source = 'backfill' AND release_gate_default = 'block' THEN 'blocked_backfill_risk'
      WHEN data_source = 'new_gbif' AND release_gate_default = 'block' THEN 'blocked_new_gbif_risk'
      WHEN effective_release_gate = 'allow_strict_release' THEN 'strict_control'
      ELSE 'other'
    END AS validation_stratum,
    ROW_NUMBER() OVER (
      PARTITION BY
        CASE
          WHEN data_source = 'backfill' AND release_gate_default = 'block_pending_audit_override' THEN 'high_risk_backfill_candidate'
          WHEN data_source = 'new_gbif' AND release_gate_default = 'block_pending_audit_override' THEN 'high_risk_new_gbif_candidate'
          WHEN data_source = 'backfill' AND release_gate_default = 'block' THEN 'blocked_backfill_risk'
          WHEN data_source = 'new_gbif' AND release_gate_default = 'block' THEN 'blocked_new_gbif_risk'
          WHEN effective_release_gate = 'allow_strict_release' THEN 'strict_control'
          ELSE 'other'
        END
      ORDER BY RAND(), occurrence_example_id
    ) AS rn
  FROM {source_table}
),
picked AS (
  SELECT * FROM base
  WHERE (
    validation_stratum = 'high_risk_backfill_candidate' AND rn <= {high_risk_backfill_n}
  ) OR (
    validation_stratum = 'high_risk_new_gbif_candidate' AND rn <= {high_risk_new_gbif_n}
  ) OR (
    validation_stratum = 'blocked_backfill_risk' AND rn <= {blocked_backfill_n}
  ) OR (
    validation_stratum = 'blocked_new_gbif_risk' AND rn <= {blocked_new_gbif_n}
  ) OR (
    validation_stratum = 'strict_control' AND rn <= {strict_control_n}
  )
)
SELECT
  *,
  '{batch_id}' AS validation_batch_id,
  CURRENT_TIMESTAMP() AS validation_batch_created_at,
  'pending_fresh_extraction' AS validation_status
FROM picked
ORDER BY validation_stratum, occurrence_example_id
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--high-risk-backfill", type=int, default=500)
    parser.add_argument("--high-risk-new-gbif", type=int, default=200)
    parser.add_argument("--blocked-backfill", type=int, default=150)
    parser.add_argument("--blocked-new-gbif", type=int, default=50)
    parser.add_argument("--strict-control", type=int, default=100)
    args = parser.parse_args()

    batch_id = args.batch_id or datetime.now(timezone.utc).strftime("fresh_validation_%Y%m%d_%H%M%S")
    target_table = f"{PROJECT}.{DATASET}.sinr_fresh_validation_batch__{batch_id}"

    client = bigquery.Client(project=PROJECT)
    sql = SQL_TEMPLATE.format(
        target_table=target_table,
        source_table=SOURCE,
        batch_id=batch_id,
        high_risk_backfill_n=args.high_risk_backfill,
        high_risk_new_gbif_n=args.high_risk_new_gbif,
        blocked_backfill_n=args.blocked_backfill,
        blocked_new_gbif_n=args.blocked_new_gbif,
        strict_control_n=args.strict_control,
    )
    client.query(sql).result()
    table = client.get_table(target_table)
    print(f"Created validation batch: {target_table} rows={table.num_rows:,} cols={len(table.schema)}")


if __name__ == "__main__":
    main()
