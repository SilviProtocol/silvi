#!/usr/bin/env python3
"""SINR v3 strict re-extraction sampler.

Key guarantees vs unified_gee_sampler_v3.py:
1) No pixel-only collapse: sample at (lat4, lon4, observation_year, emb_year)
2) No representative-year shortcut: temporal features use exact batch obs/emb year
3) Resume key includes year context, not just coordinate

Outputs (non-destructive new tables by default):
- sinr_v3_features_new_gbif_strict_full
- sinr_v3_features_backfill_strict_full
"""

import argparse
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import ee
import numpy as np
import pandas as pd
from google.cloud import bigquery

import unified_gee_sampler_v3 as base


PROJECT = base.PROJECT
BQ_DATASET = base.BQ_DATASET
AE_SCALE = base.AE_SCALE

DEFAULT_BATCH_SIZE = 2000
DEFAULT_POOL_SIZE = 25
POLL_INTERVAL_SEC = 30
MAX_RETRIES = 5
TASK_TIMEOUT_MIN = 180

OUT_NEW = "sinr_v3_features_new_gbif_strict_full"
OUT_BACKFILL = "sinr_v3_features_backfill_strict_full"
UNSAMPLEABLE_TABLE = "sinr_v3_strict_unsampleable_contexts"
UNSAMPLEABLE_LOG = "orchestrator/strict_unsampleable_contexts.jsonl"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_new_gbif_contexts(resume_from_bq: bool, out_table: str) -> pd.DataFrame:
    client = bigquery.Client(project=PROJECT)
    if resume_from_bq:
        q = f"""
        SELECT DISTINCT
          CAST(g.lat4dp AS FLOAT64) AS lat4dp,
          CAST(g.lon4dp AS FLOAT64) AS lon4dp,
          g.observation_year,
          g.emb_year
        FROM `{PROJECT}.{BQ_DATASET}.gbif_new_occurrences` g
        LEFT JOIN `{PROJECT}.{BQ_DATASET}.{out_table}` o
          ON ROUND(o.latitude, 4) = g.lat4dp
         AND ROUND(o.longitude, 4) = g.lon4dp
         AND o.observation_year = g.observation_year
         AND o.emb_year = g.emb_year
        LEFT JOIN `{PROJECT}.{BQ_DATASET}.{UNSAMPLEABLE_TABLE}` u
          ON u.data_source = 'new_gbif'
         AND u.lat4 = g.lat4dp
         AND u.lon4 = g.lon4dp
         AND u.observation_year = g.observation_year
         AND u.emb_year = g.emb_year
        WHERE g.observation_year IS NOT NULL
          AND o.latitude IS NULL
          AND u.lat4 IS NULL
        """
    else:
        q = f"""
        SELECT DISTINCT
          CAST(lat4dp AS FLOAT64) AS lat4dp,
          CAST(lon4dp AS FLOAT64) AS lon4dp,
          observation_year,
          emb_year
        FROM `{PROJECT}.{BQ_DATASET}.gbif_new_occurrences`
        WHERE observation_year IS NOT NULL
        """
    df = client.query(q).to_dataframe()
    log(f"Loaded new GBIF strict contexts: {len(df):,}")
    return df


def load_backfill_contexts(resume_from_bq: bool, out_table: str) -> pd.DataFrame:
    client = bigquery.Client(project=PROJECT)
    if resume_from_bq:
        q = f"""
        SELECT DISTINCT
          CAST(ROUND(e.latitude, 4) AS FLOAT64) AS lat4dp,
          CAST(ROUND(e.longitude, 4) AS FLOAT64) AS lon4dp,
          e.occurrence_year AS observation_year,
          e.emb_year
        FROM `{PROJECT}.{BQ_DATASET}.existing_training_coords` e
        LEFT JOIN `{PROJECT}.{BQ_DATASET}.{out_table}` o
          ON ROUND(o.latitude, 4) = ROUND(e.latitude, 4)
         AND ROUND(o.longitude, 4) = ROUND(e.longitude, 4)
         AND o.observation_year = e.occurrence_year
         AND o.emb_year = e.emb_year
        LEFT JOIN `{PROJECT}.{BQ_DATASET}.{UNSAMPLEABLE_TABLE}` u
          ON u.data_source = 'backfill'
         AND u.lat4 = ROUND(e.latitude, 4)
         AND u.lon4 = ROUND(e.longitude, 4)
         AND u.observation_year = e.occurrence_year
         AND u.emb_year = e.emb_year
        WHERE e.occurrence_year IS NOT NULL
          AND o.latitude IS NULL
          AND u.lat4 IS NULL
        """
    else:
        q = f"""
        SELECT DISTINCT
          CAST(ROUND(latitude, 4) AS FLOAT64) AS lat4dp,
          CAST(ROUND(longitude, 4) AS FLOAT64) AS lon4dp,
          occurrence_year AS observation_year,
          emb_year
        FROM `{PROJECT}.{BQ_DATASET}.existing_training_coords`
        WHERE occurrence_year IS NOT NULL
        """
    df = client.query(q).to_dataframe()
    log(f"Loaded backfill strict contexts: {len(df):,}")
    return df


def load_completed_context_keys(table_name: str) -> Set[str]:
    client = bigquery.Client(project=PROJECT)
    try:
        q = f"""
        SELECT DISTINCT
          CONCAT(
            FORMAT('%.4f', ROUND(latitude, 4)), '|',
            FORMAT('%.4f', ROUND(longitude, 4)), '|',
            CAST(observation_year AS STRING), '|',
            CAST(emb_year AS STRING)
          ) AS k
        FROM `{PROJECT}.{BQ_DATASET}.{table_name}`
        """
        df = client.query(q).to_dataframe()
        keys = set(df["k"].tolist())
        log(f"Found completed contexts in {table_name}: {len(keys):,}")
        return keys
    except Exception as e:
        log(f"No completed contexts in {table_name} yet: {e}")
        return set()


def load_unsampleable_context_keys() -> Set[str]:
    client = bigquery.Client(project=PROJECT)
    try:
        q = f"""
        SELECT DISTINCT
          CONCAT(
            FORMAT('%.4f', CAST(lat4 AS FLOAT64)), '|',
            FORMAT('%.4f', CAST(lon4 AS FLOAT64)), '|',
            CAST(observation_year AS STRING), '|',
            CAST(emb_year AS STRING)
          ) AS k
        FROM `{PROJECT}.{BQ_DATASET}.{UNSAMPLEABLE_TABLE}`
        """
        df = client.query(q).to_dataframe()
        keys = set(df["k"].tolist())
        log(f"Found unsampleable contexts to skip: {len(keys):,}")
        return keys
    except Exception as e:
        log(f"No unsampleable context table yet: {e}")
        return set()


def ensure_unsampleable_table() -> None:
    client = bigquery.Client(project=PROJECT)
    q = f"""
    CREATE TABLE IF NOT EXISTS `{PROJECT}.{BQ_DATASET}.{UNSAMPLEABLE_TABLE}` (
      data_source STRING,
      lat4 FLOAT64,
      lon4 FLOAT64,
      observation_year INT64,
      emb_year INT64,
      batch_idx INT64,
      n_points INT64,
      error_message STRING,
      logged_at TIMESTAMP
    )
    """
    client.query(q).result()
    log(f"Ensured unsampleable context table exists: {UNSAMPLEABLE_TABLE}")


def record_unsampleable(mode: str, info: dict, error_msg: str) -> None:
    row = {
        "data_source": mode,
        "lat4": round(float(info["pts"][0]["lat"]), 4) if info.get("pts") else None,
        "lon4": round(float(info["pts"][0]["lon"]), 4) if info.get("pts") else None,
        "observation_year": int(info["obs_year"]),
        "emb_year": int(info["emb_year"]),
        "batch_idx": int(info["batch_idx"]),
        "n_points": int(len(info.get("pts", []))),
        "error_message": (error_msg or "")[0:1024],
        "logged_at": datetime.utcnow().isoformat(),
    }

    # Local append-only log (always)
    try:
        with open(UNSAMPLEABLE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        log(f"Warning: failed writing unsampleable local log: {e}")

    # Best-effort BQ log
    try:
        client = bigquery.Client(project=PROJECT)
        table_id = f"{PROJECT}.{BQ_DATASET}.{UNSAMPLEABLE_TABLE}"
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            log(f"Warning: failed inserting unsampleable row: {errors}")
    except Exception as e:
        log(f"Warning: failed writing unsampleable row to BQ: {e}")


def to_key(lat: float, lon: float, obs_year: int, emb_year: int) -> str:
    return f"{lat:.4f}|{lon:.4f}|{int(obs_year)}|{int(emb_year)}"


def build_batches(df: pd.DataFrame, batch_size: int) -> List[Tuple[int, int, int, List[dict]]]:
    batches: List[Tuple[int, int, int, List[dict]]] = []
    grouped = df.groupby(["observation_year", "emb_year"], sort=True)
    global_batch_idx = 0

    for (obs_year, emb_year), g in grouped:
        points = [{"lat": float(r.lat4dp), "lon": float(r.lon4dp)} for r in g.itertuples(index=False)]
        random.shuffle(points)
        for i in range(0, len(points), batch_size):
            chunk = points[i:i + batch_size]
            batches.append((int(obs_year), int(emb_year), global_batch_idx, chunk))
            global_batch_idx += 1

    random.shuffle(batches)
    return batches


def sample_batch(obs_year: int, emb_year: int, batch_idx: int, batch: List[dict], bq_table: str, mode: str):
    has_arctic = any(p["lat"] > base.ARCTIC_LAT_THRESHOLD for p in batch)

    features = []
    for p in batch:
        geom = ee.Geometry.Point([base.ensure_float(p["lon"]), base.ensure_float(p["lat"])])
        props = {
            "latitude": base.ensure_float(p["lat"]),
            "longitude": base.ensure_float(p["lon"]),
            "observation_year": int(obs_year),
            "emb_year": int(emb_year),
        }
        features.append(ee.Feature(geom, props))
    fc = ee.FeatureCollection(features)

    dem = base.get_dem_image(has_arctic=has_arctic)
    static_env = base.get_static_env_image()
    temporal_env = base.get_temporal_env_for_year(int(obs_year))
    temporal_stack = base.get_temporal_stack_features(int(obs_year), int(emb_year))
    ae_all = base.get_ae_all_years_image()
    primary_ae = base.get_primary_ae_image(int(emb_year))

    combined = dem.addBands(static_env).addBands(temporal_env).addBands(temporal_stack).addBands(ae_all).addBands(primary_ae).toFloat()

    sampled = combined.sampleRegions(collection=fc, scale=AE_SCALE, geometries=False, tileScale=4)

    desc = f"sinr_v3_strict_{mode}_y{obs_year}_ae{emb_year}_b{batch_idx:06d}"
    full_table = f"{PROJECT}.{BQ_DATASET}.{bq_table}"
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=desc,
        table=full_table,
        append=True,
        overwrite=False,
    )

    try:
        task.start()
        return task
    except Exception as e:
        log(f"ERROR submitting {desc}: {e}")
        return None


def run_pool(batches: List[Tuple[int, int, int, List[dict]]], bq_table: str, mode: str, pool_size: int) -> Tuple[int, int]:
    total = len(batches)
    queue: List[Tuple[int, int, int, List[dict], int]] = [(o, e, b, pts, 0) for (o, e, b, pts) in batches]
    active: Dict[str, dict] = {}
    completed = 0
    failed = 0

    log(f"Starting strict sampling for {mode}: {total:,} batches -> {PROJECT}.{BQ_DATASET}.{bq_table}")

    while queue or active:
        while len(active) < pool_size and queue:
            obs_year, emb_year, batch_idx, pts, retry = queue.pop(0)
            task_obj = sample_batch(obs_year, emb_year, batch_idx, pts, bq_table, mode)
            if task_obj:
                tid = task_obj.id
                active[tid] = {
                    "task": task_obj,
                    "obs_year": obs_year,
                    "emb_year": emb_year,
                    "batch_idx": batch_idx,
                    "start_time": time.time(),
                    "pts": pts,
                    "retry": retry,
                }
            else:
                if retry < MAX_RETRIES:
                    queue.append((obs_year, emb_year, batch_idx, pts, retry + 1))
                else:
                    failed += 1

        if not active:
            break

        time.sleep(POLL_INTERVAL_SEC)
        statuses = []
        for tid in list(active.keys()):
            info = active[tid]
            try:
                st = info["task"].status()
                st["id"] = tid
                statuses.append(st)
            except Exception as e:
                log(f"Warning: failed checking status for {tid}: {e}")
                statuses.append({"id": tid, "state": "UNKNOWN", "error_message": str(e)})

        for st in statuses:
            tid = st["id"]
            if tid not in active:
                continue
            info = active[tid]
            state = st.get("state", "UNKNOWN")
            elapsed = time.time() - info["start_time"]

            if state in ("COMPLETED", "SUCCEEDED"):
                completed += 1
                del active[tid]
                if completed % 50 == 0 or completed == total:
                    log(f"Completed {completed:,}/{total:,} batches ({100.0 * completed / total:.2f}%)")
            elif state in ("FAILED", "CANCELLED", "CANCEL_REQUESTED"):
                err = st.get("error_message", "unknown")
                del active[tid]
                if info["retry"] < MAX_RETRIES:
                    queue.append((info["obs_year"], info["emb_year"], info["batch_idx"], info["pts"], info["retry"] + 1))
                else:
                    failed += 1
                    log(f"Permanent failure batch {info['batch_idx']}: {err}")
                    record_unsampleable(mode, info, err)
            elif state in ("RUNNING", "READY", "PENDING", "QUEUED") and elapsed > TASK_TIMEOUT_MIN * 60:
                try:
                    ee.data.cancelTask(tid)
                except Exception:
                    pass
                del active[tid]
                if info["retry"] < MAX_RETRIES:
                    queue.append((info["obs_year"], info["emb_year"], info["batch_idx"], info["pts"], info["retry"] + 1))
                else:
                    failed += 1
                    record_unsampleable(mode, info, "task_timeout")

        # heartbeat log every poll cycle when work remains
        if queue or active:
            log(f"Heartbeat mode={mode} completed={completed:,}/{total:,} active={len(active)} queued={len(queue):,} failed={failed:,}")

    log(f"Strict sampling finished for {mode}: completed={completed:,}, failed={failed:,}, total={total:,}")
    return completed, failed


def run_mode(mode: str, out_table: str, batch_size: int, pool_size: int, resume_from_bq: bool, limit: Optional[int]) -> None:
    if mode == "new_gbif":
        df = load_new_gbif_contexts(resume_from_bq=resume_from_bq, out_table=out_table)
    else:
        df = load_backfill_contexts(resume_from_bq=resume_from_bq, out_table=out_table)

    if resume_from_bq:
        log(f"Resume mode for {mode}: contexts pre-filtered in BigQuery anti-join against {out_table} and {UNSAMPLEABLE_TABLE}")

    if limit is not None:
        df = df.head(limit)
        log(f"Applied limit for {mode}: {len(df):,}")

    batches = build_batches(df, batch_size)
    log(f"Prepared {len(df):,} contexts into {len(batches):,} batches for {mode}")
    run_pool(batches, out_table, mode, pool_size)


def main() -> None:
    parser = argparse.ArgumentParser(description="SINR v3 strict full re-extraction sampler")
    parser.add_argument("--new-gbif", action="store_true", help="Run strict extraction for new GBIF")
    parser.add_argument("--backfill", action="store_true", help="Run strict extraction for backfill")
    parser.add_argument("--all", action="store_true", help="Run both")
    parser.add_argument("--pool-size", type=int, default=DEFAULT_POOL_SIZE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--resume-from-bq", action="store_true", help="Skip contexts already in output tables")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.all:
        args.new_gbif = True
        args.backfill = True
    if not args.new_gbif and not args.backfill:
        parser.error("Must set --new-gbif, --backfill, or --all")

    log("Initializing Earth Engine...")
    ee.Initialize(project=PROJECT)
    log("Earth Engine initialized.")
    ensure_unsampleable_table()

    if args.new_gbif:
        run_mode("new_gbif", OUT_NEW, args.batch_size, args.pool_size, args.resume_from_bq, args.limit)
    if args.backfill:
        run_mode("backfill", OUT_BACKFILL, args.batch_size, args.pool_size, args.resume_from_bq, args.limit)


if __name__ == "__main__":
    main()
