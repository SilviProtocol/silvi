#!/usr/bin/env python3
"""Compute normalization stats for the V4.1 preview training-grain table."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
from google.cloud import bigquery

from build_sinr_v41_preview_stats import (
    AE_EMB_COLS,
    AE_TEMPORAL_COLS,
    V41_ENV_CONTINUOUS_COLS,
    compute_stats_from_bq,
)


PROJECT = "treekipedia-479918"
DATASET = "species_data"
PREVIEW_TRAIN_TABLE = f"{PROJECT}.{DATASET}.sinr_v41_preview_strict_core_train_v1"
CONT_COLS = AE_EMB_COLS + V41_ENV_CONTINUOUS_COLS


def main() -> None:
    out_dir = Path("orchestrator/contracts/sinr_v3")
    out_dir.mkdir(parents=True, exist_ok=True)

    cont_path = out_dir / "normalize_stats_v41_preview_train.npz"
    temp_path = out_dir / "normalize_temporal_v41_preview_train.npz"
    manifest_path = out_dir / "stats_contract_v41_preview_train.json"

    client = bigquery.Client(project=PROJECT)
    print(f"Computing V4.1 preview training stats from {PREVIEW_TRAIN_TABLE}...")
    cont_mean, cont_std, n_rows = compute_stats_from_bq(client, PREVIEW_TRAIN_TABLE, CONT_COLS)
    temp_mean, temp_std, _ = compute_stats_from_bq(client, PREVIEW_TRAIN_TABLE, AE_TEMPORAL_COLS)

    np.savez(cont_path, mean=cont_mean, std=cont_std, columns=np.array(CONT_COLS))
    np.savez(temp_path, mean=temp_mean, std=temp_std, columns=np.array(AE_TEMPORAL_COLS))

    manifest = {
        "contract_name": "sinr_v41_preview_train_normalization",
        "version": "v41_preview_train",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": PREVIEW_TRAIN_TABLE,
        "total_rows": int(n_rows),
        "continuous_cols": len(CONT_COLS),
        "ae_emb_cols": len(AE_EMB_COLS),
        "env_continuous_cols": len(V41_ENV_CONTINUOUS_COLS),
        "temporal_cols": len(AE_TEMPORAL_COLS),
        "continuous_stats": cont_path.name,
        "temporal_stats": temp_path.name,
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    print(f"Wrote {cont_path}")
    print(f"Wrote {temp_path}")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
