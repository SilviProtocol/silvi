"""Export the V4.1 preview training-grain table to local parquet shards.

Default source:
  species_data.sinr_v41_preview_strict_core_train_v1

Default output:
  ~/data_v41_preview_train_shards/s{0..N}/unified_v41_preview_train_*.parquet

Sharding remains by (latitude, longitude) so all species rows for the same
location land in the same shard for train/val split hygiene.
"""

import argparse
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

PROJECT = "treekipedia-479918"
DATASET = "species_data"
DEFAULT_TABLE = f"{PROJECT}.{DATASET}.sinr_v41_preview_strict_core_train_v1"

# Target ~1M rows per shard (8.4M rows → 8-9 shards)
DEFAULT_ROWS_PER_SHARD = 1_000_000


def main():
    parser = argparse.ArgumentParser(description="Export V4.1 preview training shards locally")
    parser.add_argument("--table", default=DEFAULT_TABLE,
                        help="BigQuery table to export")
    parser.add_argument("--out-dir", default="~/data_v41_preview_train_shards",
                        help="Output directory for shards")
    parser.add_argument("--num-shards", type=int, default=None,
                        help="Number of shards (default: auto from row count)")
    parser.add_argument("--rows-per-shard", type=int, default=DEFAULT_ROWS_PER_SHARD,
                        help="Target rows per shard (used if --num-shards not set)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser()
    client = bigquery.Client(project=PROJECT)
    table = args.table

    # Get row count
    count_sql = f"SELECT COUNT(*) AS n FROM `{table}`"
    total_rows = list(client.query(count_sql).result())[0].n
    print(f"Source: {table}")
    print(f"Total rows: {total_rows:,}")

    num_shards = args.num_shards or max(1, math.ceil(total_rows / args.rows_per_shard))
    print(f"Shards: {num_shards} (~{total_rows // num_shards:,} rows each)")

    if args.dry_run:
        print("DRY RUN — not downloading.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # Download with shard assignment via FARM_FINGERPRINT hash
    # This is deterministic and ensures same location → same shard
    for shard_idx in range(num_shards):
        shard_dir = out_dir / f"s{shard_idx}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_path = shard_dir / f"unified_v41_preview_train_s{shard_idx}.parquet"

        if shard_path.exists():
            existing = pd.read_parquet(shard_path)
            print(f"  Shard {shard_idx}: already exists ({len(existing):,} rows), skipping")
            continue

        sql = f"""
        SELECT *
        FROM `{table}`
        WHERE MOD(ABS(FARM_FINGERPRINT(
            CONCAT(CAST(latitude AS STRING), '|', CAST(longitude AS STRING))
        )), {num_shards}) = {shard_idx}
        """

        print(f"  Downloading shard {shard_idx}/{num_shards}...", end=" ", flush=True)
        df = client.query(sql).to_dataframe()
        print(f"{len(df):,} rows", end=" ", flush=True)

        # Convert to float32 for space efficiency (matching training pipeline)
        float_cols = df.select_dtypes(include=["float64"]).columns
        df[float_cols] = df[float_cols].astype(np.float32)

        df.to_parquet(shard_path, index=False)
        size_mb = shard_path.stat().st_size / 1e6
        print(f"→ {shard_path} ({size_mb:.0f} MB)")

    # Verify
    total_exported = 0
    for shard_idx in range(num_shards):
        shard_path = out_dir / f"s{shard_idx}" / f"unified_v41_preview_train_s{shard_idx}.parquet"
        if shard_path.exists():
            n = len(pd.read_parquet(shard_path, columns=["latitude"]))
            total_exported += n
    print(f"\nTotal exported: {total_exported:,} / {total_rows:,}")
    if total_exported == total_rows:
        print("Export complete and verified.")
    else:
        print(f"WARNING: mismatch — {total_rows - total_exported:,} rows missing")


if __name__ == "__main__":
    main()
