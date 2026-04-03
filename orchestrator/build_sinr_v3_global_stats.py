#!/usr/bin/env python3
"""Build versioned global normalization stats from local parquet shards/chunks."""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import train_on_vm as tvm


def parse_args():
    p = argparse.ArgumentParser(description="Build SINR v3 global normalization stats")
    p.add_argument("--data-root", required=True, help="Root directory containing unified_*.parquet")
    p.add_argument("--version", default="v1")
    p.add_argument("--out-dir", default="orchestrator/contracts/sinr_v3")
    p.add_argument("--feature-contract", default=None)
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def iter_parquet_files(root: Path):
    return sorted(root.glob("**/unified_*.parquet"))


def update_welford(count, mean, m2, x):
    if x.size == 0:
        return count, mean, m2
    batch_count = x.shape[0]
    batch_mean = x.mean(axis=0)
    batch_m2 = ((x - batch_mean) ** 2).sum(axis=0)

    if count == 0:
        return batch_count, batch_mean, batch_m2

    delta = batch_mean - mean
    total = count + batch_count
    mean_new = mean + delta * (batch_count / total)
    m2_new = m2 + batch_m2 + (delta ** 2) * (count * batch_count / total)
    return total, mean_new, m2_new


def main():
    args = parse_args()
    root = Path(args.data_root).expanduser()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cont_path = out_dir / f"normalize_stats_v3_{args.version}.npz"
    temp_path = out_dir / f"normalize_temporal_v3_{args.version}.npz"
    manifest_path = out_dir / f"stats_contract_{args.version}.json"
    if (cont_path.exists() or temp_path.exists() or manifest_path.exists()) and not args.overwrite:
        raise FileExistsError(f"Version exists. Use --overwrite: {args.version}")

    files = iter_parquet_files(root)
    if not files:
        raise FileNotFoundError(f"No unified_*.parquet under {root}")

    if args.feature_contract:
        with open(Path(args.feature_contract).expanduser()) as f:
            fc = json.load(f)
        env_cols = [str(c) for c in fc["env_continuous_cols"]]
    else:
        env_cols = tvm.ENV_CONTINUOUS_COLS

    cont_cols = tvm.AE_EMB_COLS + env_cols
    temp_cols = tvm.AE_TEMPORAL_COLS

    cont_count = 0
    cont_mean = np.zeros(len(cont_cols), dtype=np.float64)
    cont_m2 = np.zeros(len(cont_cols), dtype=np.float64)

    temp_count = 0
    temp_mean = np.zeros(len(temp_cols), dtype=np.float64)
    temp_m2 = np.zeros(len(temp_cols), dtype=np.float64)

    total_rows = 0
    for fp in files:
        df = pd.read_parquet(fp)
        total_rows += len(df)

        for col in cont_cols:
            if col not in df.columns:
                df[col] = 0.0
        cont = df[cont_cols].to_numpy(dtype=np.float32)
        cont = np.nan_to_num(cont, nan=0.0, posinf=0.0, neginf=0.0)
        cont_count, cont_mean, cont_m2 = update_welford(cont_count, cont_mean, cont_m2, cont)

        for col in temp_cols:
            if col not in df.columns:
                df[col] = 0.0
        temp = df[temp_cols].to_numpy(dtype=np.float32)
        temp = np.nan_to_num(temp, nan=0.0, posinf=0.0, neginf=0.0)
        temp_count, temp_mean, temp_m2 = update_welford(temp_count, temp_mean, temp_m2, temp)

    cont_var = cont_m2 / max(1, cont_count)
    temp_var = temp_m2 / max(1, temp_count)
    cont_std = np.sqrt(cont_var).astype(np.float32)
    temp_std = np.sqrt(temp_var).astype(np.float32)
    cont_std[cont_std < 1e-8] = 1.0
    temp_std[temp_std < 1e-8] = 1.0

    np.savez(
        cont_path,
        mean=cont_mean.astype(np.float32),
        std=cont_std,
        columns=np.array(cont_cols),
    )
    np.savez(
        temp_path,
        mean=temp_mean.astype(np.float32),
        std=temp_std,
        columns=np.array(temp_cols),
    )

    manifest = {
        "contract_name": "sinr_v3_global_normalization",
        "version": args.version,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "data_root": str(root),
        "num_files": len(files),
        "total_rows_seen": int(total_rows),
        "feature_contract": args.feature_contract,
        "continuous_stats": cont_path.name,
        "temporal_stats": temp_path.name,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    with open(out_dir / "stats_contract_latest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {cont_path}")
    print(f"Wrote {temp_path}")
    print(f"Wrote {manifest_path}")
    print(f"files={len(files)} rows={total_rows:,}")


if __name__ == "__main__":
    main()
