#!/bin/bash
# v17: v14 config + corrected xiao + temporal magnitude features
# Single variable change from v15: --use-temporal-magnitude
# v15 was v14 config + corrected xiao (no temporal magnitude)
set -e
cd "$(dirname "$0")/.."

echo "[$(date)] === v17: temporal magnitude features ==="
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_local_contract_v17_tempmag_5m \
  --artifact-version v17_tempmag_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --require-full-contract \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --use-temporal-magnitude \
  --bg-weight 1.0 \
  --skip-export

echo "[$(date)] === v17 complete ==="
