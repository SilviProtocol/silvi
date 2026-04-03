#!/usr/bin/env python3
"""Build non-destructive field-family integrity scaffold for SINR occurrence rows."""

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
SOURCE = f"`{PROJECT}.{DATASET}.sinr_occurrence_salvage_status_v1`"
TARGET = f"`{PROJECT}.{DATASET}.sinr_occurrence_field_integrity_status_v1`"


SQL = f"""
CREATE OR REPLACE TABLE {TARGET} AS
SELECT
  s.*,
  CASE
    WHEN data_source = 'new_gbif' THEN 'recent_gbif_branch'
    WHEN data_source = 'backfill' THEN 'legacy_backfill_branch'
    ELSE 'unknown'
  END AS occurrence_source_class_hint,
  CASE
    WHEN data_source = 'new_gbif' THEN 'high'
    WHEN data_source = 'backfill' THEN 'medium'
    ELSE 'low'
  END AS occurrence_source_hint_confidence,
  TRUE AS ae_anchor_expected,
  TRUE AS ae_stack_expected,
  TRUE AS static_env_expected,
  CASE
    WHEN has_strict_context THEN TRUE
    WHEN in_preview_train THEN TRUE
    ELSE NULL
  END AS ae_anchor_ok,
  CASE
    WHEN has_strict_context THEN TRUE
    WHEN in_preview_train THEN FALSE
    ELSE NULL
  END AS ae_stack_ok,
  CASE
    WHEN has_strict_context OR has_legacy_context THEN TRUE
    ELSE FALSE
  END AS static_env_ok,
  CASE
    WHEN has_strict_context THEN TRUE
    WHEN in_preview_train THEN FALSE
    ELSE NULL
  END AS temporal_obs_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN NULL
    ELSE NULL
  END AS xiao_ok,
  CASE
    WHEN in_preview_train THEN 'corrected_preview_backfill'
    WHEN has_strict_context THEN 'strict_raw_partial_bug_window_unknown'
    WHEN has_legacy_context THEN 'legacy_pre_fix_or_unknown'
    ELSE 'no_xiao_context'
  END AS xiao_provenance_status,
  CASE
    WHEN in_preview_train THEN FALSE
    WHEN has_strict_context THEN NULL
    ELSE NULL
  END AS xiao_bug_window_flag,
  CASE
    WHEN has_strict_context OR in_preview_train THEN NULL
    ELSE NULL
  END AS land_state_ok,
  CASE
    WHEN has_strict_context OR in_preview_train THEN TRUE
    ELSE NULL
  END AS land_state_train_ok,
  CASE
    WHEN has_strict_context OR in_preview_train THEN FALSE
    ELSE NULL
  END AS land_state_serve_parity_ok,
  CASE
    WHEN in_preview_train THEN NULL
    WHEN has_strict_context THEN NULL
    ELSE NULL
  END AS carbon_family_ok,
  CASE
    WHEN in_preview_train THEN NULL
    WHEN has_strict_context THEN NULL
    ELSE NULL
  END AS aridity_family_ok,
  CASE
    WHEN in_preview_train THEN NULL
    WHEN has_strict_context THEN NULL
    ELSE NULL
  END AS hilda_family_ok,
  CASE
    WHEN has_strict_context THEN NULL
    WHEN in_preview_train THEN NULL
    ELSE NULL
  END AS ipcc_family_ok,
  CASE
    WHEN in_preview_train THEN NULL
    WHEN has_strict_context THEN NULL
    ELSE FALSE
  END AS aridity_family_train_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN TRUE
    ELSE FALSE
  END AS aridity_family_serve_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN TRUE
    ELSE FALSE
  END AS et0_family_serve_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN TRUE
    ELSE FALSE
  END AS ipcc_family_serve_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN NULL
    ELSE FALSE
  END AS carbon_family_train_optional,
  FALSE AS carbon_family_serve_ok,
  CASE
    WHEN in_preview_train THEN TRUE
    WHEN has_strict_context THEN NULL
    ELSE FALSE
  END AS hilda_family_train_optional,
  FALSE AS hilda_family_serve_ok,
  CASE
    WHEN in_preview_train OR has_strict_context THEN TRUE
    ELSE FALSE
  END AS offline_only_excluded_by_online_contract,
  CASE
    WHEN in_preview_train THEN 'preview_payload_mixed_temporal_semantics'
    WHEN has_strict_context THEN 'strict_context_obs_year_plus_emb_year_plus_full_ae_stack'
    WHEN has_legacy_context THEN 'legacy_context_temporal_semantics_uncertain'
    ELSE 'no_context'
  END AS temporal_semantics_class,
  CASE
    WHEN has_strict_context THEN 'verified_exact_context_match'
    WHEN has_legacy_context THEN 'legacy_context_match_only'
    ELSE 'missing_context'
  END AS identity_integrity_status,
  CASE
    WHEN has_strict_context THEN 'strict_raw_payload'
    WHEN in_preview_train THEN 'preview_inherited_legacy_payload'
    WHEN has_legacy_context THEN 'legacy_payload_only'
    ELSE 'no_payload'
  END AS payload_provenance_status,
  CASE
    WHEN has_strict_context THEN 'allow_strict_release'
    WHEN in_preview_train AND context_quality_status = 'legacy_unverified' THEN 'block_pending_audit_override'
    ELSE 'block'
  END AS release_gate_default,
  CASE
    WHEN has_strict_context THEN 'provisionally_valid'
    WHEN in_preview_train THEN 'mixed_or_unknown'
    WHEN has_legacy_context THEN 'unknown'
    ELSE 'missing'
  END AS temporal_validity_default,
  CASE
    WHEN has_strict_context THEN FALSE
    WHEN in_preview_train AND context_quality_status = 'legacy_unverified' THEN TRUE
    ELSE FALSE
  END AS requires_manual_audit_override,
  CASE
    WHEN has_strict_context THEN 'strict_raw_match'
    WHEN in_preview_train THEN 'preview_inherited_legacy_payload'
    WHEN has_legacy_context THEN 'legacy_context_only'
    ELSE 'no_context_available'
  END AS feature_integrity_basis,
  CASE
    WHEN has_strict_context THEN TRUE
    WHEN in_preview_train AND context_quality_status = 'legacy_unverified' THEN NULL
    ELSE FALSE
  END AS feature_contract_complete,
  CASE
    WHEN has_strict_context THEN TRUE
    ELSE FALSE
  END AS fully_trainable_strict_only,
  CASE
    WHEN has_strict_context THEN TRUE
    WHEN in_preview_train AND context_quality_status = 'legacy_unverified' THEN NULL
    ELSE FALSE
  END AS fully_trainable_hybrid_candidate
FROM {SOURCE} s
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    client.query(SQL).result()
    table = client.get_table(f"{PROJECT}.{DATASET}.sinr_occurrence_field_integrity_status_v1")
    print(f"Created sinr_occurrence_field_integrity_status_v1 rows={table.num_rows:,} cols={len(table.schema)}")


if __name__ == "__main__":
    main()
