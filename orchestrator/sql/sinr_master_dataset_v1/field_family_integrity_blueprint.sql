-- SINR field-family integrity blueprint
-- Status: design only, not executed

-- Purpose:
-- Attach feature-family integrity flags to occurrence-grain salvage rows.

CREATE TABLE IF NOT EXISTS `treekipedia-479918.species_data.sinr_occurrence_field_integrity_status_v1` AS
SELECT
  s.*,
  TRUE AS ae_stack_expected,
  TRUE AS ae_anchor_expected,
  TRUE AS static_env_expected,
  NULL AS temporal_obs_ok,
  NULL AS ae_anchor_ok,
  NULL AS ae_stack_ok,
  NULL AS static_env_ok,
  NULL AS xiao_ok,
  NULL AS land_state_ok,
  NULL AS carbon_family_ok,
  NULL AS aridity_family_ok,
  NULL AS hilda_family_ok,
  NULL AS feature_contract_complete,
  NULL AS fully_trainable
FROM `treekipedia-479918.species_data.sinr_occurrence_salvage_status_v1` s;

-- This is only a placeholder table shape.
-- Actual logic should populate these flags using:
--   - extraction provenance windows
--   - feature family availability
--   - bug-window registries
--   - strict vs legacy source lineage
