#!/usr/bin/env python3
"""Build a small audited review batch of hybrid candidates.

This does not approve anything. It creates a stable, human-reviewable queue.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
SOURCE = f"`{PROJECT}.{DATASET}.sinr_hybrid_override_candidate_queue_v1`"
FIELD = f"`{PROJECT}.{DATASET}.sinr_occurrence_field_integrity_status_v1`"


SQL_TEMPLATE = """
CREATE OR REPLACE TABLE `{target_table}` AS
WITH ranked AS (
  SELECT
    q.*,
    f.payload_provenance_status AS audit_payload_provenance_status,
    f.temporal_validity_default AS audit_temporal_validity_default,
    f.release_gate_default AS audit_release_gate_default,
    f.requires_manual_audit_override AS audit_requires_manual_audit_override,
    ROW_NUMBER() OVER (
      PARTITION BY q.data_source
      ORDER BY q.context_quality_status, q.occurrence_example_id
    ) AS rn_by_source,
    ROW_NUMBER() OVER (
      PARTITION BY q.data_source, q.context_quality_status
      ORDER BY q.occurrence_example_id
    ) AS rn_by_status
  FROM {source_table} q
  JOIN {field_table} f
    ON q.occurrence_example_id = f.occurrence_example_id
),
per_status AS (
  SELECT *
  FROM ranked
  WHERE (
    data_source = 'backfill' AND rn_by_status <= 70
  ) OR (
    data_source = 'new_gbif' AND rn_by_status <= 30
  )
),
trimmed AS (
  SELECT *
  FROM per_status
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY data_source
    ORDER BY context_quality_status, occurrence_example_id
  ) <= CASE WHEN data_source = 'backfill' THEN 70 ELSE 30 END
)
SELECT
  trimmed.occurrence_example_id,
  trimmed.data_source,
  trimmed.taxon_id,
  trimmed.latitude,
  trimmed.longitude,
  trimmed.lat4,
  trimmed.lon4,
  trimmed.observation_year,
  trimmed.emb_year,
  trimmed.context_quality_status,
  trimmed.feature_integrity_basis,
  trimmed.audit_payload_provenance_status AS payload_provenance_status,
  trimmed.audit_temporal_validity_default AS temporal_validity_default,
  trimmed.occurrence_source_class_hint,
  trimmed.occurrence_source_hint_confidence,
  trimmed.xiao_provenance_status,
  trimmed.xiao_bug_window_flag,
  trimmed.land_state_train_ok,
  trimmed.land_state_serve_parity_ok,
  trimmed.aridity_family_serve_ok,
  trimmed.carbon_family_serve_ok,
  trimmed.hilda_family_serve_ok,
  trimmed.audit_release_gate_default AS release_gate_default,
  trimmed.audit_requires_manual_audit_override AS requires_manual_audit_override,
  '{batch_id}' AS review_batch_id,
  CURRENT_TIMESTAMP() AS review_batch_created_at,
  'pending_manual_review' AS review_status
FROM trimmed
ORDER BY data_source, context_quality_status, occurrence_example_id
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()

    batch_id = args.batch_id or datetime.now(timezone.utc).strftime("hybrid_review_100_%Y%m%d_%H%M%S")
    target_table = f"{PROJECT}.{DATASET}.sinr_hybrid_override_review_batch__{batch_id}"

    client = bigquery.Client(project=PROJECT)
    sql = SQL_TEMPLATE.format(
        target_table=target_table,
        source_table=SOURCE,
        field_table=FIELD,
        batch_id=batch_id,
    )
    client.query(sql).result()
    table = client.get_table(target_table)
    print(f"Created review batch: {target_table} rows={table.num_rows:,} cols={len(table.schema)}")


if __name__ == "__main__":
    main()
