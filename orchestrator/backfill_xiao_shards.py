#!/usr/bin/env python3
"""
backfill_xiao_shards.py — Backfill corrected Xiao planted forest classification
into local 5M training shards AND full 22M BQ table.

CONTEXT (2026-03-08):
The original GEE sampler had WRONG RGB decoding for the Xiao et al. 2024 dataset:
  - WRONG: looked for red (R>200, G<50) for planted → matched NOTHING
  - CORRECT: planted = yellow (127,127,0), natural = green (0,127,0)

This caused xiao_planted_forest=2 (planted) to have ZERO rows in all training data.

Strategy (v2 — threaded getInfo, no EE export tasks):
  Phase A — Extract unique coords from shards, save as local pickle
  Phase B — Sample Xiao via threaded getInfo() calls, save results locally
  Phase C — Apply results to local parquet files
  Phase A-FULL — Extract unique coords from 22M BQ preview table
  Phase D — Update BQ preview + shard tables with results

Usage:
  python3 orchestrator/backfill_xiao_shards.py --phase all           # shard-only (a+b+c)
  python3 orchestrator/backfill_xiao_shards.py --phase full          # everything
  python3 orchestrator/backfill_xiao_shards.py --phase a-full        # upload full coords
  python3 orchestrator/backfill_xiao_shards.py --phase b             # sample (resumable)
  python3 orchestrator/backfill_xiao_shards.py --phase c --shard-dir # apply to parquet
  python3 orchestrator/backfill_xiao_shards.py --phase d             # update BQ tables
"""

import argparse
import json
import math
import os
import pickle
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional

import ee
import numpy as np
import pandas as pd
from google.cloud import bigquery

PROJECT = "treekipedia-479918"
BQ_DATASET = "species_data"
XIAO_ASSET = "projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS"

# BQ tables
COORDS_TABLE = "xiao_backfill_coords"
OUTPUT_TABLE = "xiao_backfill_results"
PREVIEW_TABLE = "sinr_v3_unified_strict_train_v30_preview_clean"

# Sampling config — threaded getInfo() approach
GETINFO_BATCH_SIZE = 5000   # points per getInfo() call
NUM_THREADS = 8             # concurrent threads (EE allows ~10-12 before throttling)
MAX_RETRIES = 3

# Local cache files
CACHE_DIR = Path("orchestrator/.xiao_backfill_cache")
COORDS_CACHE = CACHE_DIR / "coords.pkl"
RESULTS_CACHE = CACHE_DIR / "results.pkl"

LOG_FILE = "orchestrator/backfill_xiao_shards.log"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def build_xiao_image() -> ee.Image:
    """Build corrected Xiao classification image.

    RGB encoding (Xiao et al. 2024):
      Green (0,127,0) = natural forest → 1
      Yellow (127,127,0) = planted forest → 2
      White/other = non-forest → 0
    """
    xiao_raw = ee.ImageCollection(XIAO_ASSET).mosaic()
    b1 = xiao_raw.select('b1')
    b2 = xiao_raw.select('b2')
    b3 = xiao_raw.select('b3')

    is_natural = b1.eq(0).And(b2.eq(127)).And(b3.eq(0))
    is_planted = b1.eq(127).And(b2.eq(127)).And(b3.eq(0))

    return (ee.Image(0)
            .where(is_natural, 1)
            .where(is_planted, 2)
            .rename('xiao_planted_forest')
            .toInt())


def sample_batch_getinfo(batch_points: List[dict], xiao_img: ee.Image) -> List[dict]:
    """Sample a batch of points using synchronous getInfo(). Thread-safe."""
    features = [
        ee.Feature(
            ee.Geometry.Point([p["lon"], p["lat"]]),
            {"latitude": p["lat"], "longitude": p["lon"]}
        )
        for p in batch_points
    ]
    fc = ee.FeatureCollection(features)
    sampled = xiao_img.sampleRegions(collection=fc, scale=30, geometries=False)
    result = sampled.getInfo()

    out = []
    for f in result.get("features", []):
        props = f.get("properties", {})
        out.append({
            "lat": props.get("latitude"),
            "lon": props.get("longitude"),
            "xiao": props.get("xiao_planted_forest"),
        })
    return out


# ═══════════════════════════════════════════════════════════════════════
# PHASE A: Extract unique coords from shards → local cache
# ═══════════════════════════════════════════════════════════════════════

def phase_a(shard_dir: Path):
    log("=" * 60)
    log("PHASE A: Extract unique coordinates from shards")
    log("=" * 60)

    coord_dfs = []
    file_count = 0
    for shard in sorted(shard_dir.iterdir()):
        if not shard.is_dir():
            continue
        for pf in sorted(shard.glob("*.parquet")):
            df = pd.read_parquet(pf, columns=["latitude", "longitude"])
            coord_dfs.append(df)
            file_count += 1

    all_df = pd.concat(coord_dfs, ignore_index=True)
    all_df["lat4"] = all_df["latitude"].round(4)
    all_df["lon4"] = all_df["longitude"].round(4)
    unique = all_df[["lat4", "lon4"]].drop_duplicates().reset_index(drop=True)
    log(f"  {file_count} files, {len(all_df):,} rows, {len(unique):,} unique coords")

    del all_df, coord_dfs

    # Filter out NaN/inf
    before = len(unique)
    unique = unique.dropna()
    unique = unique[np.isfinite(unique["lat4"]) & np.isfinite(unique["lon4"])]
    unique = unique[(unique["lat4"].abs() <= 90) & (unique["lon4"].abs() <= 180)]
    if len(unique) < before:
        log(f"  Filtered {before - len(unique)} invalid coords → {len(unique):,} valid")

    # Save to local cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    points = [{"lat": float(r.lat4), "lon": float(r.lon4)} for r in unique.itertuples()]
    with open(COORDS_CACHE, "wb") as f:
        pickle.dump(points, f)
    log(f"  Saved {len(points):,} coords to {COORDS_CACHE}")
    log("PHASE A COMPLETE")
    return points


# ═══════════════════════════════════════════════════════════════════════
# PHASE A-FULL: Extract unique coords from 22M BQ preview table
# ═══════════════════════════════════════════════════════════════════════

def phase_a_full():
    log("=" * 60)
    log("PHASE A-FULL: Extract unique coords from 22M BQ preview table")
    log("=" * 60)

    client = bigquery.Client(project=PROJECT)
    preview_table = f"{PROJECT}.{BQ_DATASET}.{PREVIEW_TABLE}"

    q = f"""
        SELECT DISTINCT
            ROUND(latitude, 4) as lat4,
            ROUND(longitude, 4) as lon4
        FROM `{preview_table}`
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND ABS(latitude) <= 90
          AND ABS(longitude) <= 180
    """
    log("  Querying BQ for unique coords...")
    df = client.query(q).to_dataframe()
    log(f"  Got {len(df):,} unique coords from BQ")

    points = [{"lat": float(r.lat4), "lon": float(r.lon4)} for r in df.itertuples()]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(COORDS_CACHE, "wb") as f:
        pickle.dump(points, f)
    log(f"  Saved {len(points):,} coords to {COORDS_CACHE}")
    log("PHASE A-FULL COMPLETE")
    return points


# ═══════════════════════════════════════════════════════════════════════
# PHASE B: Sample Xiao via threaded getInfo() — resumable
# ═══════════════════════════════════════════════════════════════════════

def phase_b():
    log("=" * 60)
    log("PHASE B: Sample Xiao via threaded getInfo()")
    log("=" * 60)

    # Load coords
    if not COORDS_CACHE.exists():
        log("  ERROR: No coords cache. Run Phase A first.")
        return
    with open(COORDS_CACHE, "rb") as f:
        all_points = pickle.load(f)
    log(f"  Loaded {len(all_points):,} coords from cache")

    # Load existing results for resume
    results_map: Dict[str, int] = {}
    if RESULTS_CACHE.exists():
        with open(RESULTS_CACHE, "rb") as f:
            results_map = pickle.load(f)
        log(f"  Resuming: {len(results_map):,} already sampled")

    # Filter to remaining
    remaining = [p for p in all_points
                 if f"{p['lat']:.4f},{p['lon']:.4f}" not in results_map]
    log(f"  Remaining to sample: {len(remaining):,}")

    if not remaining:
        log("  Nothing to do — all coords sampled")
        _print_distribution(results_map)
        return

    # Initialize EE
    ee.Initialize(project=PROJECT)
    xiao_img = build_xiao_image()

    # Build batches
    random.shuffle(remaining)
    batches = []
    for i in range(0, len(remaining), GETINFO_BATCH_SIZE):
        batches.append(remaining[i:i + GETINFO_BATCH_SIZE])

    total_batches = len(batches)
    log(f"  {total_batches} batches of {GETINFO_BATCH_SIZE}, {NUM_THREADS} threads")

    completed = 0
    failed = 0
    start_time = time.time()
    save_interval = 50  # save cache every N batches

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        # Submit batches in chunks to avoid overwhelming memory
        batch_idx = 0
        while batch_idx < total_batches:
            # Submit a chunk of batches
            chunk_size = min(NUM_THREADS * 4, total_batches - batch_idx)
            futures = {}
            for i in range(chunk_size):
                bi = batch_idx + i
                future = executor.submit(
                    _sample_with_retry, batches[bi], xiao_img, MAX_RETRIES
                )
                futures[future] = bi

            for future in as_completed(futures):
                bi = futures[future]
                try:
                    batch_results = future.result()
                    if batch_results is not None:
                        for r in batch_results:
                            key = f"{r['lat']:.4f},{r['lon']:.4f}"
                            results_map[key] = r["xiao"]
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    log(f"  Batch {bi} exception: {e}")

                # Progress
                done_total = completed + failed
                if done_total % 10 == 0 or done_total == total_batches:
                    elapsed = time.time() - start_time
                    rate = completed * GETINFO_BATCH_SIZE / elapsed if elapsed > 0 else 0
                    remaining_pts = len(all_points) - len(results_map)
                    eta_min = remaining_pts / rate / 60 if rate > 0 else float("inf")
                    log(f"  {done_total}/{total_batches} batches "
                        f"({len(results_map):,} sampled, {failed} failed, "
                        f"{rate:.0f} pts/sec, ETA {eta_min:.1f}m)")

            batch_idx += chunk_size

            # Periodic save
            if (completed % save_interval < chunk_size) or batch_idx >= total_batches:
                with open(RESULTS_CACHE, "wb") as f:
                    pickle.dump(results_map, f)

    # Final save
    with open(RESULTS_CACHE, "wb") as f:
        pickle.dump(results_map, f)

    elapsed = time.time() - start_time
    log(f"\n  Sampling complete: {completed} succeeded, {failed} failed in {elapsed/60:.1f}m")
    log(f"  Total results: {len(results_map):,}")

    _print_distribution(results_map)

    # Also upload results to BQ for Phase D
    _upload_results_to_bq(results_map)

    log("PHASE B COMPLETE")


def _sample_with_retry(batch_points, xiao_img, max_retries):
    """Sample a batch with retries on failure."""
    for attempt in range(max_retries):
        try:
            return sample_batch_getinfo(batch_points, xiao_img)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 5 + random.random() * 5
                time.sleep(wait)
            else:
                return None


def _print_distribution(results_map: Dict[str, int]):
    """Print distribution of sampled values."""
    counts = {0: 0, 1: 0, 2: 0}
    for v in results_map.values():
        if v is not None and v in counts:
            counts[v] += 1
    total = sum(counts.values())
    labels = {0: "non-forest", 1: "natural", 2: "planted"}
    for k in sorted(counts.keys()):
        pct = counts[k] / total * 100 if total > 0 else 0
        log(f"    {k} ({labels[k]}): {counts[k]:,} ({pct:.1f}%)")


def _upload_results_to_bq(results_map: Dict[str, int]):
    """Upload results to BQ for use by Phase D."""
    log("  Uploading results to BQ...")
    rows = []
    for key, val in results_map.items():
        lat_s, lon_s = key.split(",")
        rows.append({
            "latitude": float(lat_s),
            "longitude": float(lon_s),
            "xiao_planted_forest": int(val) if val is not None else None,
        })
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["xiao_planted_forest"])
    df["xiao_planted_forest"] = df["xiao_planted_forest"].astype(int)

    client = bigquery.Client(project=PROJECT)
    table_id = f"{PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("latitude", "FLOAT64"),
            bigquery.SchemaField("longitude", "FLOAT64"),
            bigquery.SchemaField("xiao_planted_forest", "INT64"),
        ],
    )
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    log(f"  Uploaded {len(df):,} results to {OUTPUT_TABLE}")


# ═══════════════════════════════════════════════════════════════════════
# PHASE C: Apply results to local parquet files
# ═══════════════════════════════════════════════════════════════════════

def phase_c(shard_dir: Path):
    log("=" * 60)
    log("PHASE C: Apply results to local parquet files")
    log("=" * 60)

    # Load results
    if not RESULTS_CACHE.exists():
        log("  ERROR: No results cache. Run Phase B first.")
        return
    with open(RESULTS_CACHE, "rb") as f:
        results_map = pickle.load(f)
    log(f"  Loaded {len(results_map):,} results from cache")

    # Distribution
    _print_distribution(results_map)

    # Collect shard files
    shard_files = []
    for shard in sorted(shard_dir.iterdir()):
        if not shard.is_dir():
            continue
        for pf in sorted(shard.glob("*.parquet")):
            shard_files.append(pf)
    log(f"  Found {len(shard_files)} parquet files")

    total_changed = 0
    total_rows = 0
    total_planted = 0

    for fi, pf in enumerate(shard_files):
        df = pd.read_parquet(pf)
        total_rows += len(df)

        keys = (df["latitude"].round(4).apply(lambda x: f"{x:.4f}") + "," +
                df["longitude"].round(4).apply(lambda x: f"{x:.4f}"))
        new_xiao = keys.map(results_map)

        old_xiao = df["xiao_planted_forest"]
        changed = ((old_xiao.isna() & new_xiao.notna()) |
                    (old_xiao.notna() & new_xiao.notna() & (old_xiao != new_xiao)))
        total_changed += changed.sum()

        mask = new_xiao.notna()
        df.loc[mask, "xiao_planted_forest"] = new_xiao[mask].astype(float)
        total_planted += (df["xiao_planted_forest"] == 2.0).sum()

        df.to_parquet(pf, index=False)

        if (fi + 1) % 100 == 0 or fi == 0 or fi == len(shard_files) - 1:
            log(f"    {fi+1}/{len(shard_files)} files "
                f"({total_changed:,} changed, {total_planted:,} planted so far)")

    log(f"\n  Done: {total_changed:,} values changed across {total_rows:,} rows")
    log(f"  Total planted (xiao=2) rows: {total_planted:,}")

    # Verify
    log("\n  Verification — first shard file:")
    df_v = pd.read_parquet(shard_files[0], columns=["xiao_planted_forest"])
    dist_v = df_v["xiao_planted_forest"].value_counts(dropna=False).sort_index()
    for k, v in dist_v.items():
        log(f"    {k}: {v:,}")

    log("\n" + "=" * 60)
    log("PHASE C COMPLETE — LOCAL PARQUET UPDATED")
    log("=" * 60)


# ═══════════════════════════════════════════════════════════════════════
# PHASE D: Update BQ preview table with corrected xiao values
# ═══════════════════════════════════════════════════════════════════════

def phase_d():
    log("=" * 60)
    log("PHASE D: Update BQ preview + shard tables with corrected xiao")
    log("=" * 60)

    client = bigquery.Client(project=PROJECT)
    output_table = f"{PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}"
    preview_table = f"{PROJECT}.{BQ_DATASET}.{PREVIEW_TABLE}"

    # Check results available
    count_q = f"SELECT COUNT(*) as n FROM `{output_table}`"
    n_results = list(client.query(count_q).result())[0].n
    log(f"  Results available: {n_results:,} rows")

    if n_results == 0:
        log("  ERROR: No results in BQ. Run Phase B first.")
        return

    # Distribution in results
    log("  Distribution in backfill results:")
    dist_q = f"SELECT xiao_planted_forest, COUNT(*) as n FROM `{output_table}` GROUP BY 1 ORDER BY 1"
    for row in client.query(dist_q).result():
        labels = {0: "non-forest", 1: "natural", 2: "planted"}
        log(f"    {row.xiao_planted_forest} ({labels.get(row.xiao_planted_forest, '?')}): {row.n:,}")

    # Current state of preview table
    log("  Current xiao distribution in preview table:")
    preview_dist_q = f"""
        SELECT CAST(xiao_planted_forest AS INT64) as xiao, COUNT(*) as n
        FROM `{preview_table}`
        GROUP BY 1 ORDER BY 1
    """
    for row in client.query(preview_dist_q).result():
        log(f"    {row.xiao}: {row.n:,}")

    # Update preview table directly from results
    log(f"  Updating {PREVIEW_TABLE}...")
    update_q = f"""
        UPDATE `{preview_table}` t
        SET t.xiao_planted_forest = r.xiao_planted_forest
        FROM `{output_table}` r
        WHERE ROUND(t.latitude, 4) = ROUND(r.latitude, 4)
          AND ROUND(t.longitude, 4) = ROUND(r.longitude, 4)
    """
    client.query(update_q).result()
    log("  Preview table updated")

    # Update shard tables
    for shard_idx in range(5):
        shard_table = f"{PROJECT}.{BQ_DATASET}.sinr_v3_unified_strict_train_v30_medium_5m_s{shard_idx}"
        try:
            shard_q = f"""
                UPDATE `{shard_table}` t
                SET t.xiao_planted_forest = r.xiao_planted_forest
                FROM `{output_table}` r
                WHERE ROUND(t.latitude, 4) = ROUND(r.latitude, 4)
                  AND ROUND(t.longitude, 4) = ROUND(r.longitude, 4)
            """
            client.query(shard_q).result()
            log(f"  Updated shard table s{shard_idx}")
        except Exception as e:
            log(f"  Warning: shard s{shard_idx} failed: {e}")

    # Verify
    log("\n  Post-update distribution in preview table:")
    for row in client.query(preview_dist_q).result():
        log(f"    {row.xiao}: {row.n:,}")

    log("\n" + "=" * 60)
    log("PHASE D COMPLETE — BQ TABLES UPDATED")
    log("=" * 60)


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Backfill corrected Xiao classification into training data")
    parser.add_argument("--phase", type=str, required=True,
                        choices=["a", "a-full", "b", "c", "d", "all", "full"],
                        help=("a=extract shard coords, a-full=extract 22M BQ coords, "
                              "b=sample via getInfo (resumable), c=apply to parquet, "
                              "d=update BQ tables, all=a+b+c, full=a-full+b+c+d"))
    parser.add_argument("--shard-dir", type=str, default="~/data_5m_shards",
                        help="Path to local training shards directory")
    args = parser.parse_args()

    shard_dir = Path(args.shard_dir).expanduser()

    if args.phase == "a":
        phase_a(shard_dir)
    elif args.phase == "a-full":
        phase_a_full()
    elif args.phase == "b":
        phase_b()
    elif args.phase == "c":
        phase_c(shard_dir)
    elif args.phase == "d":
        phase_d()
    elif args.phase == "all":
        phase_a(shard_dir)
        phase_b()
        phase_c(shard_dir)
    elif args.phase == "full":
        phase_a_full()
        phase_b()
        phase_c(shard_dir)
        phase_d()


if __name__ == "__main__":
    main()
