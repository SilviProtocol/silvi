#!/usr/bin/env python3
"""Build the AE + xiao + dynamic_world feature contract for merged v47 training data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from train_on_vm import AE_EMB_COLS, AE_TEMPORAL_COLS


SOURCE_TABLE = "treekipedia-479918.species_data.sinr_v47_merged_strict_core_train_v2"
OUT_DIR = Path("orchestrator/contracts/sinr_v3")
OUT_PATH = OUT_DIR / "feature_contract_v53_ae_xiao_dynamic_world_train.json"

ENV_CONTINUOUS_COLS = ["dynamic_world"]
CATEGORICAL_FEATURES = ["xiao_planted_forest"]


def sha256_list(values: list[str]) -> str:
    payload = json.dumps(values, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_name": "sinr_v53_ae_xiao_dynamic_world_train_feature_contract",
        "version": "v53_ae_xiao_dynamic_world_train",
        "mode": "online",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": SOURCE_TABLE,
        "num_ae_embeddings": len(AE_EMB_COLS),
        "num_ae_temporal": len(AE_TEMPORAL_COLS),
        "num_env_continuous": len(ENV_CONTINUOUS_COLS),
        "env_continuous_sha256": sha256_list(ENV_CONTINUOUS_COLS),
        "env_continuous_cols": ENV_CONTINUOUS_COLS,
        "categorical_features": CATEGORICAL_FEATURES,
        "land_state_cols": [],
        "notes": [
            "AE plus xiao plus dynamic_world add-back experiment",
            "Uses AE current-year embeddings, AE temporal embeddings, xiao_planted_forest, and dynamic_world",
            "Drops all other non-AE environmental and land-state inputs",
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
