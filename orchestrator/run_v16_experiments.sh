#!/bin/bash
# v16a + v16b sequential training experiments
# v16a: strict_planted3 label mode (fix planted label)
# v16b: aux_planted_weight=0 (disable planted aux entirely)
set -e
cd "$(dirname "$0")/.."

echo "[$(date)] === v16a: strict_planted3 ==="
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_local_contract_v16a_strictplanted_5m \
  --artifact-version v16a_strictplanted_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --require-full-contract \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --bg-weight 1.0 \
  --planted-label-mode strict_planted3 \
  --skip-export

echo "[$(date)] === v16b: no aux planted ==="
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_local_contract_v16b_noauxplanted_5m \
  --artifact-version v16b_noauxplanted_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --require-full-contract \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --bg-weight 1.0 \
  --aux-planted-weight 0.0 \
  --skip-export

echo "[$(date)] === Both experiments complete ==="
