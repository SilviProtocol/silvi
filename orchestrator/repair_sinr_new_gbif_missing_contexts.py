#!/usr/bin/env python3
"""Adaptive repair fork for the missing strict new_gbif contexts.

This does not modify the main strict sampler or canonical tables.
It targets only the currently missing contexts and writes successful repairs
into a separate patch table. Failed batches are recursively split until the
passing subset lands or a singleton poison row is isolated.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from typing import Dict, List, Tuple

import ee
import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

import unified_gee_sampler_v3 as base


PROJECT = base.PROJECT
DATASET = base.BQ_DATASET
AE_SCALE = base.AE_SCALE

SOURCE_CONTEXTS_TABLE = f"{PROJECT}.{DATASET}.gbif_new_occurrences"
CURRENT_CANONICAL_TABLE = (
    f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_v1"
)
PATCH_RAW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_missing_patch_raw_v1"
MISSING_CONTEXTS_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_contexts_v1"
SINGLETON_FAILURE_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_singleton_failures_v1"
SUMMARY_TABLE = f"{PROJECT}.{DATASET}.sinr_new_gbif_strict_missing_patch_summary_v1"

RAW_SCHEMA_SOURCE_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full"

POLL_INTERVAL_SEC = 30
TASK_TIMEOUT_MIN = 180
MAX_RETRIES = 4


def log(message: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def should_split_immediately(error_message: str, item: dict) -> bool:
    if len(item["pts"]) <= 1:
        return False
    lowered = (error_message or "").lower()
    return "projection error" in lowered or "unable to compute intersection" in lowered


def ensure_patch_raw_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{PATCH_RAW_TABLE}` AS
    SELECT *
    FROM `{RAW_SCHEMA_SOURCE_TABLE}`
    WHERE 1 = 0
    """
    client.query(sql).result()


def ensure_singleton_failure_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{SINGLETON_FAILURE_TABLE}` (
      lat4 FLOAT64,
      lon4 FLOAT64,
      observation_year INT64,
      emb_year INT64,
      failure_path STRING,
      error_message STRING,
      logged_at TIMESTAMP
    )
    """
    client.query(sql).result()


def build_missing_contexts_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{MISSING_CONTEXTS_TABLE}` AS
    WITH src AS (
      SELECT DISTINCT
        CAST(lat4dp AS FLOAT64) AS lat4,
        CAST(lon4dp AS FLOAT64) AS lon4,
        observation_year,
        emb_year
      FROM `{SOURCE_CONTEXTS_TABLE}`
      WHERE observation_year IS NOT NULL
    ),
    current_canonical AS (
      SELECT DISTINCT
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year
      FROM `{CURRENT_CANONICAL_TABLE}`
    ),
    patch_raw AS (
      SELECT DISTINCT
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        observation_year,
        emb_year
      FROM `{PATCH_RAW_TABLE}`
    ),
    singletons AS (
      SELECT DISTINCT lat4, lon4, observation_year, emb_year
      FROM `{SINGLETON_FAILURE_TABLE}`
    )
    SELECT
      s.lat4,
      s.lon4,
      s.observation_year,
      s.emb_year
    FROM src s
    LEFT JOIN current_canonical c
      USING (lat4, lon4, observation_year, emb_year)
    LEFT JOIN patch_raw p
      USING (lat4, lon4, observation_year, emb_year)
    LEFT JOIN singletons f
      USING (lat4, lon4, observation_year, emb_year)
    WHERE c.lat4 IS NULL
      AND p.lat4 IS NULL
      AND f.lat4 IS NULL
    ORDER BY observation_year, emb_year, lat4, lon4
    """
    client.query(sql).result()


def load_missing_contexts(client: bigquery.Client) -> pd.DataFrame:
    sql = f"SELECT lat4, lon4, observation_year, emb_year FROM `{MISSING_CONTEXTS_TABLE}` ORDER BY observation_year, emb_year, lat4, lon4"
    df = client.query(sql).to_dataframe()
    log(f"Loaded missing strict new_gbif contexts: {len(df):,}")
    return df


def build_initial_batches(df: pd.DataFrame, batch_size: int) -> List[dict]:
    batches: List[dict] = []
    global_batch_idx = 0
    grouped = df.groupby(["observation_year", "emb_year"], sort=True)

    for (obs_year, emb_year), group in grouped:
        points = [{"lat": float(r.lat4), "lon": float(r.lon4)} for r in group.itertuples(index=False)]
        for i in range(0, len(points), batch_size):
            chunk = points[i:i + batch_size]
            batches.append(
                {
                    "obs_year": int(obs_year),
                    "emb_year": int(emb_year),
                    "batch_idx": global_batch_idx,
                    "path": str(global_batch_idx),
                    "pts": chunk,
                    "retry": 0,
                }
            )
            global_batch_idx += 1

    return batches


def sample_batch(obs_year: int, emb_year: int, path: str, pts: List[dict]):
    has_arctic = any(p["lat"] > base.ARCTIC_LAT_THRESHOLD for p in pts)

    features = []
    for p in pts:
        geom = ee.Geometry.Point([base.ensure_float(p["lon"]), base.ensure_float(p["lat"])] )
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

    desc = f"sinr_v3_strict_patch_y{obs_year}_ae{emb_year}_p{path}"
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=desc,
        table=PATCH_RAW_TABLE,
        append=True,
        overwrite=False,
    )

    try:
        task.start()
        return task
    except Exception as exc:
        log(f"ERROR submitting {desc}: {exc}")
        return None


def split_batch(item: dict) -> Tuple[dict, dict]:
    mid = len(item["pts"]) // 2
    left_pts = item["pts"][:mid]
    right_pts = item["pts"][mid:]
    left = {
        "obs_year": item["obs_year"],
        "emb_year": item["emb_year"],
        "batch_idx": item["batch_idx"],
        "path": f"{item['path']}L",
        "pts": left_pts,
        "retry": 0,
    }
    right = {
        "obs_year": item["obs_year"],
        "emb_year": item["emb_year"],
        "batch_idx": item["batch_idx"],
        "path": f"{item['path']}R",
        "pts": right_pts,
        "retry": 0,
    }
    return left, right


def record_singleton_failure(client: bigquery.Client, item: dict, error_message: str) -> None:
    pt = item["pts"][0]
    rows = [{
        "lat4": round(float(pt["lat"]), 4),
        "lon4": round(float(pt["lon"]), 4),
        "observation_year": int(item["obs_year"]),
        "emb_year": int(item["emb_year"]),
        "failure_path": item["path"],
        "error_message": (error_message or "")[:1024],
        "logged_at": datetime.utcnow().isoformat(),
    }]
    errors = client.insert_rows_json(SINGLETON_FAILURE_TABLE, rows)
    if errors:
        raise RuntimeError(f"Failed to log singleton failure: {errors}")


def run_pool(client: bigquery.Client, queue: List[dict], pool_size: int) -> None:
    total_root = len(queue)
    active: Dict[str, dict] = {}
    completed = 0
    split_count = 0
    singleton_failures = 0

    log(f"Starting adaptive strict repair: {total_root:,} root batches -> {PATCH_RAW_TABLE}")

    while queue or active:
        while len(active) < pool_size and queue:
            item = queue.pop(0)
            task_obj = sample_batch(item["obs_year"], item["emb_year"], item["path"], item["pts"])
            if task_obj is None:
                submit_error = "submit_failed"
                if should_split_immediately(submit_error, item):
                    left, right = split_batch(item)
                    queue.extend([left, right])
                    split_count += 1
                    log(f"Split submit-failed batch path={item['path']} size={len(item['pts'])} -> {len(left['pts'])}+{len(right['pts'])}")
                elif item["retry"] < MAX_RETRIES:
                    item["retry"] += 1
                    queue.append(item)
                else:
                    if len(item["pts"]) > 1:
                        left, right = split_batch(item)
                        queue.extend([left, right])
                        split_count += 1
                        log(f"Split submit-failed batch path={item['path']} size={len(item['pts'])} -> {len(left['pts'])}+{len(right['pts'])}")
                    else:
                        record_singleton_failure(client, item, "submit_failed")
                        singleton_failures += 1
                continue

            active[task_obj.id] = {
                **item,
                "task": task_obj,
                "start_time": time.time(),
            }

        if not active:
            break

        time.sleep(POLL_INTERVAL_SEC)
        statuses = []
        for tid in list(active.keys()):
            try:
                status = active[tid]["task"].status()
                status["id"] = tid
            except Exception as exc:
                status = {"id": tid, "state": "UNKNOWN", "error_message": str(exc)}
            statuses.append(status)

        for status in statuses:
            tid = status["id"]
            if tid not in active:
                continue
            item = active[tid]
            state = status.get("state", "UNKNOWN")
            elapsed = time.time() - item["start_time"]

            if state in ("COMPLETED", "SUCCEEDED"):
                completed += 1
                del active[tid]
                log(f"Completed repair path={item['path']} size={len(item['pts'])}")
            elif state in ("FAILED", "CANCELLED", "CANCEL_REQUESTED"):
                err = status.get("error_message", "unknown")
                del active[tid]
                if should_split_immediately(err, item):
                    left, right = split_batch(item)
                    queue.extend([left, right])
                    split_count += 1
                    log(f"Split projection-failed batch path={item['path']} size={len(item['pts'])} -> {len(left['pts'])}+{len(right['pts'])}; error={err}")
                elif item["retry"] < MAX_RETRIES:
                    item["retry"] += 1
                    queue.append(item)
                elif len(item["pts"]) > 1:
                    left, right = split_batch(item)
                    queue.extend([left, right])
                    split_count += 1
                    log(f"Split failed batch path={item['path']} size={len(item['pts'])} -> {len(left['pts'])}+{len(right['pts'])}; error={err}")
                else:
                    record_singleton_failure(client, item, err)
                    singleton_failures += 1
                    log(f"Singleton failure isolated path={item['path']} lat={item['pts'][0]['lat']:.4f} lon={item['pts'][0]['lon']:.4f}; error={err}")
            elif state in ("RUNNING", "READY", "PENDING", "QUEUED") and elapsed > TASK_TIMEOUT_MIN * 60:
                try:
                    ee.data.cancelTask(tid)
                except Exception:
                    pass
                del active[tid]
                if item["retry"] < MAX_RETRIES:
                    item["retry"] += 1
                    queue.append(item)
                elif len(item["pts"]) > 1:
                    left, right = split_batch(item)
                    queue.extend([left, right])
                    split_count += 1
                    log(f"Split timed-out batch path={item['path']} size={len(item['pts'])} -> {len(left['pts'])}+{len(right['pts'])}")
                else:
                    record_singleton_failure(client, item, "task_timeout")
                    singleton_failures += 1

        if queue or active:
            log(
                "Heartbeat repair completed_paths={completed} active={active_count} queued={queued} splits={splits} singleton_failures={singleton_failures}".format(
                    completed=completed,
                    active_count=len(active),
                    queued=len(queue),
                    splits=split_count,
                    singleton_failures=singleton_failures,
                )
            )

    log(
        f"Adaptive strict repair finished: completed_paths={completed}, splits={split_count}, singleton_failures={singleton_failures}"
    )


def build_summary_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{SUMMARY_TABLE}` AS
    WITH remaining AS (
      SELECT * FROM `{MISSING_CONTEXTS_TABLE}`
    ),
    patch_counts AS (
      SELECT COUNT(*) AS patch_row_count FROM `{PATCH_RAW_TABLE}`
    ),
    singleton_counts AS (
      SELECT COUNT(*) AS singleton_failure_count FROM `{SINGLETON_FAILURE_TABLE}`
    )
    SELECT
      (SELECT COUNT(*) FROM remaining) AS remaining_missing_contexts,
      (SELECT patch_row_count FROM patch_counts) AS patch_row_count,
      (SELECT singleton_failure_count FROM singleton_counts) AS singleton_failure_count
    """
    client.query(sql).result()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["prepare", "run", "summarize", "all"], default="all")
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--pool-size", type=int, default=1)
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)
    ensure_patch_raw_table(client)
    ensure_singleton_failure_table(client)

    if args.phase in {"prepare", "run", "all", "summarize"}:
        build_missing_contexts_table(client)

    if args.phase in {"run", "all"}:
        ee.Initialize(project=PROJECT)
        df = load_missing_contexts(client)
        batches = build_initial_batches(df, args.batch_size)
        log(f"Prepared {len(df):,} missing contexts into {len(batches):,} root repair batches")
        run_pool(client, batches, args.pool_size)
        build_missing_contexts_table(client)

    if args.phase in {"summarize", "all", "run"}:
        build_summary_table(client)
        row = next(client.query(f"SELECT * FROM `{SUMMARY_TABLE}`").result())
        log(
            f"Repair summary: remaining_missing_contexts={int(row.remaining_missing_contexts):,}, "
            f"patch_row_count={int(row.patch_row_count):,}, singleton_failure_count={int(row.singleton_failure_count):,}"
        )


if __name__ == "__main__":
    main()
