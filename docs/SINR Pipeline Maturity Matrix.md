# SINR Pipeline Maturity Matrix

Date: 2026-03-13
Status: honest assessment of what is scripted, manual, and planned
Issue: treekipedia-l14

## Maturity Levels

- **Scripted**: Executable script exists, produces correct output, supports resume/rerun
- **Manual**: Requires human invocation with correct args; no orchestration
- **Ad-hoc**: One-shot forensic/audit script; not part of regular pipeline
- **Planned**: Documented intent but no implementation yet

## Pipeline Stages

### 1. GEE Feature Extraction

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Strict new_gbif extraction | **Scripted** | `unified_gee_sampler_v3_strict.py` | Resumable via `--resume-from-bq`. Long-running (~40h for 1,239 batches). Must be manually started. |
| Strict backfill extraction | **Scripted** | `unified_gee_sampler_v3_strict.py` | Same script, `--backfill` mode. Not yet started. |
| Legacy extraction | **Superseded** | `unified_gee_sampler_v3.py` | Code retained; no longer used for new runs. |
| Unsampleable context tracking | **Scripted** | (built into strict sampler) | Logs to `sinr_v3_strict_unsampleable_contexts` in BQ. |

**Gap**: No orchestrator or scheduler — human must start extraction and monitor.

### 2. Occurrence-Grain Salvage & Audit

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Unified source view | **Manual** | `build_sinr_occurrence_salvage_tables.py` | Non-destructive. Builds 6 audit tables. Safe to rerun. |
| Field-family integrity | **Manual** | `build_sinr_field_integrity_status.py` | Builds integrity scaffold + release gates. Replaces self each run. |
| Xiao RGB audit | **Ad-hoc** | `build_sinr_xiao_full_audit.py` | Forensic one-shot. Created 4 audit tables. |
| Xiao correction overlay | **Ad-hoc** | (built into xiao audit script) | `sinr_xiao_correction_overlay_v1` — LEFT JOIN for training. |

**Gap**: These are run manually in sequence. No dependency chain enforced.

### 3. Release Building

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Strict-only release | **Scripted** | `build_sinr_strict_only_release.py` | Enforces `allow_strict_release` gate. Produces versioned release table. |
| Hybrid override infra | **Manual** | `build_sinr_hybrid_override_system.py` | Builds candidate queue + eligibility table. Fail-closed by default. |
| Hybrid single-row approval | **Manual** | `register_sinr_hybrid_override.py` | Per-row with safety checks. Requires human audit first. |
| Hybrid release | **Scripted** | `build_sinr_hybrid_train_release.py` | Only includes rows with explicit overrides. Currently dormant. |
| Release registry | **Scripted** | (built into release builders) | `sinr_release_registry_v1` tracks all releases. |

**Gap**: No CI/CD or approval UI. Override registration is manual SQL-level.

### 4. Fresh Validation

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Stratified batch builder | **Manual** | `build_sinr_fresh_validation_batch.py` | Samples from eligibility table. |
| Validation extraction | **Scripted** | `run_sinr_fresh_validation_extraction.py` | Isolated GEE re-extraction. Resumable. |
| Status checker | **Manual** | `check_sinr_fresh_validation_status.py` | Polls GEE tasks + BQ metadata. |
| Feature comparison | **Manual** | `build_sinr_fresh_validation_compare.py` | Diffs fresh vs preview vs strict vs legacy. |

**Gap**: Covers core strict GEE payload only. No validation for carbon, HILDA, aridity/ET0/IPCC, land-state, or introduced/native joins.

### 5. Contracts & Normalization

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Feature contract | **Manual** | `build_sinr_v3_feature_contract.py` | Versioned JSON. Run before each model release. |
| Mapping contract | **Manual** | `build_sinr_v3_mapping_contract.py` | Species → model index. |
| Intro ratio contract | **Manual** | `build_sinr_v3_intro_ratio_contract.py` | Per-species introduced ratio for logit boost. |
| Species frequency contract | **Manual** | `build_sinr_v3_species_frequency_contract.py` | Occurrence counts for class weighting. |
| Global normalization stats | **Manual** | `build_sinr_v3_global_stats.py` | Feature mean/std as NPZ. |

**Gap**: Contracts are versioned but not tied to release table versions. Manual pairing required.

### 6. Training

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| Full model training | **Manual** | `train_on_vm.py` | 1535 LOC. H100 GPU. Manual flag selection per experiment. |
| 5M shard training | **Manual** | `run_local_5m_shard_training.py` | Wrapper for faster prototyping. |

**Gap**: No training automation. Experiment tracking is ad-hoc (model dir naming + beads). No hyperparameter sweep infrastructure.

### 7. Inference

| Component | Maturity | Script | Notes |
|-----------|----------|--------|-------|
| CLI point inference | **Scripted** | `v3_point_inference.py` | Research/validation tool. |
| Production Flask service | **Scripted** | `location_predictor_FIXED.py` | Port 5002. `/sinr-infer` + `/sample`. Must be manually started. |

**Gap**: No health monitoring, auto-restart, or model hot-swap.

## What Does NOT Exist Yet

| Capability | Status | Priority |
|------------|--------|----------|
| End-to-end pipeline orchestrator | **Planned** | P3 |
| Hybrid approval UI | **Planned** | P3 |
| Automated training trigger on release | **Planned** | P3 |
| Contract-to-release version binding | **Planned** | P2 |
| Auxiliary family validation (carbon, HILDA, aridity, land-state) | **Planned** | P1 |
| Backfill strict extraction run | **Planned** | P1 (after new_gbif completes) |
| Xiao full re-extraction (clean column) | **Planned** | P2 (treekipedia-wtt) |
| Model serving with auto-restart | **Planned** | P3 |

## Honest Summary

The pipeline is **scripted at the component level** but **manual at the orchestration level**. Each stage has a working script. No stage has automated triggering from the previous stage. Human judgment is required at:

1. Extraction start/restart
2. Release gate decisions (strict is automated; hybrid requires per-row approval)
3. Training invocation and flag selection
4. Contract versioning
5. Validation review and sign-off

This is appropriate for the current research/recovery phase. Automation should follow only after the data estate is fully trustworthy.
