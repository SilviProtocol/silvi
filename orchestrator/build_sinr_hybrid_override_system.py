#!/usr/bin/env python3
"""Build fail-closed SINR hybrid override system.

Creates review/override tables only. Does not approve any rows by default.
"""

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
FIELD_TABLE = f"`{PROJECT}.{DATASET}.sinr_occurrence_field_integrity_status_v1`"

OVERRIDE_TABLE = f"`{PROJECT}.{DATASET}.sinr_hybrid_override_registry_v1`"
QUEUE_TABLE = f"`{PROJECT}.{DATASET}.sinr_hybrid_override_candidate_queue_v1`"
ELIGIBILITY_TABLE = f"`{PROJECT}.{DATASET}.sinr_occurrence_release_eligibility_v1`"
DUPLICATE_AUDIT_TABLE = f"`{PROJECT}.{DATASET}.sinr_hybrid_override_duplicate_audit_v1`"
ORPHAN_AUDIT_TABLE = f"`{PROJECT}.{DATASET}.sinr_hybrid_override_orphan_audit_v1`"


CREATE_OVERRIDE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {OVERRIDE_TABLE} (
  occurrence_example_id STRING,
  override_decision STRING,
  override_scope STRING,
  approved_by STRING,
  approved_at TIMESTAMP,
  rationale STRING,
  evidence_refs ARRAY<STRING>,
  source_review_table STRING,
  release_id STRING,
  status STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
"""


CREATE_DUPLICATE_AUDIT_TABLE = f"""
CREATE OR REPLACE TABLE {DUPLICATE_AUDIT_TABLE} AS
SELECT
  occurrence_example_id,
  override_scope,
  COUNT(*) AS duplicate_count,
  ARRAY_AGG(STRUCT(
    override_decision,
    approved_by,
    approved_at,
    rationale,
    release_id,
    status,
    created_at,
    updated_at
  ) ORDER BY updated_at DESC NULLS LAST, approved_at DESC NULLS LAST, created_at DESC NULLS LAST) AS duplicate_rows
FROM {OVERRIDE_TABLE}
GROUP BY 1,2
HAVING COUNT(*) > 1
"""


CREATE_ORPHAN_AUDIT_TABLE = f"""
CREATE OR REPLACE TABLE {ORPHAN_AUDIT_TABLE} AS
SELECT
  o.*
FROM {OVERRIDE_TABLE} o
LEFT JOIN {FIELD_TABLE} f
  ON o.occurrence_example_id = f.occurrence_example_id
WHERE f.occurrence_example_id IS NULL
"""


CREATE_QUEUE_TABLE = f"""
CREATE OR REPLACE TABLE {QUEUE_TABLE} AS
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
  release_gate_default,
  CURRENT_TIMESTAMP() AS queued_at
FROM {FIELD_TABLE}
WHERE release_gate_default = 'block_pending_audit_override'
"""


CREATE_ELIGIBILITY_TABLE = f"""
CREATE OR REPLACE TABLE {ELIGIBILITY_TABLE} AS
WITH latest_override AS (
  SELECT *
  FROM {OVERRIDE_TABLE}
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY occurrence_example_id, override_scope
    ORDER BY updated_at DESC NULLS LAST, approved_at DESC NULLS LAST, created_at DESC NULLS LAST
  ) = 1
)
SELECT
  f.*,
  o.override_decision,
  o.override_scope,
  o.approved_by,
  o.approved_at,
  o.rationale AS override_rationale,
  o.evidence_refs,
  o.source_review_table,
  o.release_id AS override_release_id,
  o.status AS override_status,
  o.override_scope AS effective_override_scope,
  CASE
    WHEN f.release_gate_default = 'allow_strict_release' THEN 'allow_strict_release'
    WHEN f.release_gate_default = 'block_pending_audit_override'
         AND o.override_decision = 'approve'
         AND o.override_scope = 'hybrid_train_only'
         AND o.status = 'active' THEN 'allow_hybrid_release'
    WHEN f.release_gate_default = 'block_pending_audit_override' THEN 'block_pending_audit_override'
    ELSE 'block'
  END AS effective_release_gate,
  CASE
    WHEN f.release_gate_default = 'allow_strict_release' THEN FALSE
    WHEN f.release_gate_default = 'block_pending_audit_override'
         AND o.override_decision = 'approve'
         AND o.status = 'active' THEN FALSE
    WHEN f.release_gate_default = 'block_pending_audit_override' THEN TRUE
    ELSE FALSE
  END AS requires_override_review
FROM {FIELD_TABLE} f
LEFT JOIN latest_override o
  ON f.occurrence_example_id = o.occurrence_example_id
 AND o.override_scope = 'hybrid_train_only'
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    client.query(CREATE_OVERRIDE_TABLE).result()
    client.query(CREATE_QUEUE_TABLE).result()
    client.query(CREATE_DUPLICATE_AUDIT_TABLE).result()
    client.query(CREATE_ORPHAN_AUDIT_TABLE).result()
    client.query(CREATE_ELIGIBILITY_TABLE).result()

    for name in [
        "sinr_hybrid_override_registry_v1",
        "sinr_hybrid_override_candidate_queue_v1",
        "sinr_hybrid_override_duplicate_audit_v1",
        "sinr_hybrid_override_orphan_audit_v1",
        "sinr_occurrence_release_eligibility_v1",
    ]:
        table = client.get_table(f"{PROJECT}.{DATASET}.{name}")
        print(f"Created/updated {name}: rows={table.num_rows:,} cols={len(table.schema)}")


if __name__ == "__main__":
    main()
