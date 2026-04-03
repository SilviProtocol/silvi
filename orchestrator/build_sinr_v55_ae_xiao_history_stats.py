#!/usr/bin/env python3
"""Compute normalization stats for the AE + xiao + forest-history experiment."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
from google.cloud import bigquery

from build_sinr_v55_ae_xiao_history_feature_contract import ENV_CONTINUOUS_COLS
from train_on_vm import AE_EMB_COLS, AE_TEMPORAL_COLS


PROJECT = "treekipedia-479918"
DATASET = "species_data"
SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v47_merged_strict_core_train_v2"


def compute_stats_from_bq(client: bigquery.Client, table: str, columns: list[str], batch_size: int = 50):
    means = np.zeros(len(columns), dtype=np.float64)
    stds = np.zeros(len(columns), dtype=np.float64)
    row_count = 0

    for batch_start in range(0, len(columns), batch_size):
        batch_cols = columns[batch_start:batch_start + batch_size]
        select_parts = []
        for col in batch_cols:
            select_parts.append(f"AVG(IFNULL(CAST({col} AS FLOAT64), 0.0)) AS mean_{col}")
            select_parts.append(f"STDDEV_POP(IFNULL(CAST({col} AS FLOAT64), 0.0)) AS std_{col}")
        if batch_start == 0:
            select_parts.append("COUNT(*) AS n")

        sql = f"SELECT\n  {', '.join(select_parts)}\nFROM `{table}`"
        row = next(client.query(sql).result())
        if batch_start == 0:
            row_count = int(row.n)
        for i, col in enumerate(batch_cols):
            idx = batch_start + i
            means[idx] = getattr(row, f"mean_{col}") or 0.0
            stds[idx] = getattr(row, f"std_{col}") or 1.0

    stds[stds < 1e-8] = 1.0
    return means.astype(np.float32), stds.astype(np.float32), row_count


def main() -> None:
    out_dir = Path("orchestrator/contracts/sinr_v3")
    out_dir.mkdir(parents=True, exist_ok=True)

    cont_cols = AE_EMB_COLS + ENV_CONTINUOUS_COLS
    cont_path = out_dir / "normalize_stats_v55_ae_xiao_history.npz"
    temp_path = out_dir / "normalize_temporal_v55_ae_xiao_history.npz"
    manifest_path = out_dir / "stats_contract_v55_ae_xiao_history.json"

    client = bigquery.Client(project=PROJECT)
    cont_mean, cont_std, n_rows = compute_stats_from_bq(client, SOURCE_TABLE, cont_cols)
    temp_mean, temp_std, _ = compute_stats_from_bq(client, SOURCE_TABLE, AE_TEMPORAL_COLS)

    np.savez(cont_path, mean=cont_mean, std=cont_std, columns=np.array(cont_cols))
    np.savez(temp_path, mean=temp_mean, std=temp_std, columns=np.array(AE_TEMPORAL_COLS))

    manifest = {
        "contract_name": "sinr_v55_ae_xiao_history_normalization",
        "version": "v55_ae_xiao_history",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": SOURCE_TABLE,
        "total_rows": int(n_rows),
        "continuous_cols": len(cont_cols),
        "ae_emb_cols": len(AE_EMB_COLS),
        "env_continuous_cols": len(ENV_CONTINUOUS_COLS),
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
