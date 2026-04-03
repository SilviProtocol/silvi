#!/usr/bin/env python3
"""Build the AE + xiao-only feature contract for merged v47 training data."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from train_on_vm import AE_EMB_COLS, AE_TEMPORAL_COLS


SOURCE_TABLE = "treekipedia-479918.species_data.sinr_v47_merged_strict_core_train_v2"
OUT_DIR = Path("orchestrator/contracts/sinr_v3")
OUT_PATH = OUT_DIR / "feature_contract_v51_ae_xiao_train.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_name": "sinr_v51_ae_xiao_train_feature_contract",
        "version": "v51_ae_xiao_train",
        "mode": "online",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": SOURCE_TABLE,
        "num_ae_embeddings": len(AE_EMB_COLS),
        "num_ae_temporal": len(AE_TEMPORAL_COLS),
        "num_env_continuous": 0,
        "env_continuous_sha256": None,
        "env_continuous_cols": [],
        "categorical_features": ["xiao_planted_forest"],
        "land_state_cols": [],
        "notes": [
            "AE plus xiao-only add-back experiment",
            "Uses AE current-year embeddings, AE temporal embeddings, and only the xiao_planted_forest categorical input",
            "Drops all other non-AE environmental and land-state inputs",
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
