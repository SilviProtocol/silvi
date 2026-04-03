#!/usr/bin/env python3
"""Build the feature contract for the v49 canopy-only GEDI training table."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from build_sinr_v41_preview_stats import V41_ENV_CONTINUOUS_COLS
from train_on_vm import AE_EMB_COLS, AE_TEMPORAL_COLS


SOURCE_TABLE = "treekipedia-479918.species_data.sinr_v49_merged_strict_core_train_v1"
OUT_DIR = Path("orchestrator/contracts/sinr_v3")
OUT_PATH = OUT_DIR / "feature_contract_v49_gedi_canopy_train.json"

CATEGORICAL_FEATURES = [
    "jrc_forest_type",
    "xiao_planted_forest",
    "eco_id",
    "biome_num",
    "soil_texture_class",
]


def build_env_continuous_cols() -> list[str]:
    cols: list[str] = []
    for col in V41_ENV_CONTINUOUS_COLS:
        cols.append(col)
        if col == "lossyear":
            cols.extend(["gedi_canopy_height_m", "gedi_canopy_countf"])
    return cols


V49_GEDI_CANOPY_ENV_CONTINUOUS_COLS = build_env_continuous_cols()


def sha256_list(values: list[str]) -> str:
    payload = json.dumps(values, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_name": "sinr_v49_gedi_canopy_train_feature_contract",
        "version": "v49_gedi_canopy_train",
        "mode": "online",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": SOURCE_TABLE,
        "num_ae_embeddings": len(AE_EMB_COLS),
        "num_ae_temporal": len(AE_TEMPORAL_COLS),
        "num_env_continuous": len(V49_GEDI_CANOPY_ENV_CONTINUOUS_COLS),
        "env_continuous_sha256": sha256_list(V49_GEDI_CANOPY_ENV_CONTINUOUS_COLS),
        "env_continuous_cols": V49_GEDI_CANOPY_ENV_CONTINUOUS_COLS,
        "categorical_features": CATEGORICAL_FEATURES,
        "land_state_cols": [],
        "notes": [
            "Training-grain v49 canopy-only GEDI contract",
            "Adds GEDI canopy height and count support on top of stable v47 merged no-GEDI baseline",
            "Canopy source is RH98 p95 with conservative countf and range gates",
            "Foliage GEDI remains excluded from the training contract",
        ],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
