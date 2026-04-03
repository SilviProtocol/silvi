#!/bin/bash
# v18: Fix planted signal — remove broken boost, add is_planted as 6th land_state dim
# Changes from v15 baseline:
#   --no-boost: Remove planted_score * intro_ratio * boost_scale entirely
#   --planted-as-land-state: Add binary is_planted (xiao==2) as 6th land_state input
#   --planted-label-mode strict_planted3: Correct planted label (only raw xiao=2)
#   --planted-aux-pos-weight 5.7: Compensate for 14.8% class imbalance
# Hypothesis: clean planted input lets ALL species (native+introduced) learn plantation affinity
set -e
cd "$(dirname "$0")/.."

echo "[$(date)] === v18: fix planted signal ==="
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_local_contract_v18_plantedfix_5m \
  --artifact-version v18_plantedfix_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v3_v2_online56_preview4m.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v3_v2_online56_preview4m.npz \
  --require-full-contract \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v2_strict_full.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --no-boost \
  --planted-as-land-state \
  --planted-label-mode strict_planted3 \
  --planted-aux-pos-weight 5.7 \
  --bg-weight 1.0 \
  --skip-export

echo "[$(date)] === v18 complete ==="
echo ""
echo "Benchmark with:"
echo "python3 orchestrator/v3_point_inference.py \\"
echo "  --lat -41.151583464812404 --lon 175.09968969862783 --year 2023 \\"
echo "  --model-dir ~/model_local_contract_v18_plantedfix_5m \\"
echo "  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \\"
echo "  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \\"
echo "  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \\"
echo "  --target-taxon GymPiPiPnCx50820-00 --introduced-mode all --top-k 20 \\"
echo "  --disable-intro-in-gate --zero-phylo-input --use-location-encoding \\"
echo "  --no-boost --planted-as-land-state \\"
echo "  --land-state-mode planted_only"
