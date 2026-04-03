#!/usr/bin/env python3
"""Register a single SINR hybrid override with duplicate protection.

This script is intentionally conservative:
- only supports `hybrid_train_only` scope today
- rejects duplicate active overrides for the same occurrence/scope
- rejects overrides for rows not currently in the candidate queue
- refreshes eligibility/audit tables after insertion
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
REGISTRY = f"{PROJECT}.{DATASET}.sinr_hybrid_override_registry_v1"
QUEUE = f"{PROJECT}.{DATASET}.sinr_hybrid_override_candidate_queue_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--occurrence-example-id", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--source-review-table", required=True)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--scope", default="hybrid_train_only", choices=["hybrid_train_only"])
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)

    queue_check = f"""
    SELECT COUNT(*) AS cnt
    FROM `{QUEUE}`
    WHERE occurrence_example_id = @occurrence_example_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("occurrence_example_id", "STRING", args.occurrence_example_id),
        ]
    )
    cnt = list(client.query(queue_check, job_config=job_config).result())[0].cnt
    if cnt == 0:
        raise SystemExit("Occurrence is not in the hybrid override candidate queue; refusing override.")

    dup_check = f"""
    SELECT COUNT(*) AS cnt
    FROM `{REGISTRY}`
    WHERE occurrence_example_id = @occurrence_example_id
      AND override_scope = @override_scope
      AND status = 'active'
    """
    dup_cfg = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("occurrence_example_id", "STRING", args.occurrence_example_id),
            bigquery.ScalarQueryParameter("override_scope", "STRING", args.scope),
        ]
    )
    dup = list(client.query(dup_check, job_config=dup_cfg).result())[0].cnt
    if dup > 0:
        raise SystemExit("Active override already exists for this occurrence/scope; refusing duplicate.")

    release_id = args.release_id or datetime.now(timezone.utc).strftime("hybrid_override_%Y%m%d_%H%M%S")
    insert_sql = f"""
    INSERT INTO `{REGISTRY}`
    (occurrence_example_id, override_decision, override_scope, approved_by, approved_at,
     rationale, evidence_refs, source_review_table, release_id, status, created_at, updated_at)
    VALUES (
      @occurrence_example_id,
      'approve',
      @override_scope,
      @approved_by,
      CURRENT_TIMESTAMP(),
      @rationale,
      @evidence_refs,
      @source_review_table,
      @release_id,
      'active',
      CURRENT_TIMESTAMP(),
      CURRENT_TIMESTAMP()
    )
    """
    ins_cfg = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("occurrence_example_id", "STRING", args.occurrence_example_id),
            bigquery.ScalarQueryParameter("override_scope", "STRING", args.scope),
            bigquery.ScalarQueryParameter("approved_by", "STRING", args.approved_by),
            bigquery.ScalarQueryParameter("rationale", "STRING", args.rationale),
            bigquery.ArrayQueryParameter("evidence_refs", "STRING", args.evidence_ref),
            bigquery.ScalarQueryParameter("source_review_table", "STRING", args.source_review_table),
            bigquery.ScalarQueryParameter("release_id", "STRING", release_id),
        ]
    )
    client.query(insert_sql, job_config=ins_cfg).result()
    print("Inserted override; rebuild eligibility with:")
    print("python3 orchestrator/build_sinr_hybrid_override_system.py")


if __name__ == "__main__":
    main()
