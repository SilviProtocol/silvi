#!/usr/bin/env python3
"""Extract Xiao repair lookup for backfill coords missing the clean lookup."""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import ee
from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

MANIFEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_backfill_xiao_missing_manifest_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_backfill_xiao_lookup_v1"
XIAO_ASSET = "projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS"

POLL_INTERVAL_SEC = 20
MAX_RETRIES = 2


@dataclass
class BatchItem:
    batch_idx: int
    rows: list[dict]
    retry: int = 0


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def build_xiao_image() -> ee.Image:
    xiao = ee.ImageCollection(XIAO_ASSET).mosaic()
    b1 = xiao.select("b1")
    b2 = xiao.select("b2")
    b3 = xiao.select("b3")
    return ee.Image.constant(1).rename("anchor").addBands(
        ee.Image(0)
        .where(b1.eq(0).And(b2.eq(127)).And(b3.eq(0)), 1)
        .where(b1.eq(127).And(b2.eq(127)).And(b3.eq(0)), 2)
        .rename("xiao_planted_forest")
        .toFloat()
    )


def build_feature_collection(rows: list[dict]) -> ee.FeatureCollection:
    feats = []
    for row in rows:
        geom = ee.Geometry.Point([float(row["sample_longitude"]), float(row["sample_latitude"])])
        feats.append(
            ee.Feature(
                geom,
                {
                    "coord_key": str(row["coord_key"]),
                    "lat4": float(row["lat4"]),
                    "lon4": float(row["lon4"]),
                    "sample_latitude": float(row["sample_latitude"]),
                    "sample_longitude": float(row["sample_longitude"]),
                    "context_rows": int(row["context_rows"]),
                },
            )
        )
    return ee.FeatureCollection(feats)


def annotate(fc: ee.FeatureCollection, run_id: str) -> ee.FeatureCollection:
    extracted_at = datetime.now(timezone.utc).isoformat()

    def _map_fn(f: ee.Feature) -> ee.Feature:
        feat = ee.Feature(None, ee.Feature(f).toDictionary())
        return feat.set(
            {
                "lat4": ee.Number(feat.get("lat4")).toFloat(),
                "lon4": ee.Number(feat.get("lon4")).toFloat(),
                "sample_latitude": ee.Number(feat.get("sample_latitude")).toFloat(),
                "sample_longitude": ee.Number(feat.get("sample_longitude")).toFloat(),
                "context_rows": ee.Number(feat.get("context_rows")).toInt64(),
                "anchor": ee.Number(feat.get("anchor")).toFloat(),
                "xiao_lookup_version": "v1",
                "xiao_asset": XIAO_ASSET,
                "xiao_extraction_run_id": run_id,
                "xiao_extracted_at_utc": extracted_at,
            }
        )

    return fc.map(_map_fn)


def submit_batch(batch: BatchItem, dest_table: str, run_id: str) -> ee.batch.Task | None:
    try:
        fc = build_feature_collection(batch.rows)
        sampled = build_xiao_image().reduceRegions(collection=fc, reducer=ee.Reducer.first(), scale=30)
        sampled = annotate(sampled, run_id)
        task = ee.batch.Export.table.toBigQuery(
            collection=sampled,
            description=f"sinr_v48_backfill_xiao_b{batch.batch_idx:06d}",
            table=dest_table,
            append=True,
            overwrite=False,
        )
        task.start()
        return task
    except Exception as exc:
        log(f"ERROR submitting Xiao batch {batch.batch_idx}: {exc}")
        return None


def stream_batches(client: bigquery.Client, manifest_table: str, batch_size: int, start_batch: int, max_batches: int | None):
    q = f"SELECT coord_key, lat4, lon4, sample_latitude, sample_longitude, context_rows FROM `{manifest_table}` ORDER BY lat4, lon4"
    df = client.query(q).to_dataframe()
    rows = [dict(row._asdict()) for row in df.itertuples(index=False)]
    emitted = 0
    batch_idx = 0
    for i in range(0, len(rows), batch_size):
        if batch_idx >= start_batch:
            if max_batches is not None and emitted >= max_batches:
                break
            yield BatchItem(batch_idx=batch_idx, rows=rows[i : i + batch_size])
            emitted += 1
        batch_idx += 1


def run_pool(client: bigquery.Client, manifest_table: str, dest_table: str, batch_size: int, pool_size: int, start_batch: int, max_batches: int | None, run_id: str, total_batches: int) -> None:
    batch_iter = iter(stream_batches(client, manifest_table, batch_size, start_batch, max_batches))
    retry_queue: list[BatchItem] = []
    if total_batches == 0:
        log("No Xiao repair batches to process")
        return
    active: dict[str, tuple[ee.batch.Task, BatchItem]] = {}
    completed = 0
    failed = 0
    more = True
    log(f"Starting Xiao repair extraction: {total_batches:,} batches -> {dest_table}")
    while retry_queue or active or more:
        while len(active) < pool_size:
            if retry_queue:
                batch = retry_queue.pop(0)
            elif more:
                try:
                    batch = next(batch_iter)
                except StopIteration:
                    more = False
                    break
            else:
                break
            task = submit_batch(batch, dest_table, run_id)
            if task is None:
                if batch.retry < MAX_RETRIES:
                    retry_queue.append(BatchItem(batch_idx=batch.batch_idx, rows=batch.rows, retry=batch.retry + 1))
                else:
                    failed += 1
                continue
            active[task.id] = (task, batch)
        if not active:
            break
        time.sleep(POLL_INTERVAL_SEC)
        for task_id in list(active.keys()):
            task, batch = active[task_id]
            st = task.status()
            state = st.get("state", "UNKNOWN")
            if state in ("COMPLETED", "SUCCEEDED"):
                completed += 1
                del active[task_id]
                if completed % 10 == 0 or completed == total_batches:
                    log(f"Completed {completed:,}/{total_batches:,} Xiao batches ({100.0 * completed / total_batches:.2f}%)")
            elif state in ("FAILED", "CANCELLED", "CANCEL_REQUESTED"):
                del active[task_id]
                if batch.retry < MAX_RETRIES:
                    retry_queue.append(BatchItem(batch_idx=batch.batch_idx, rows=batch.rows, retry=batch.retry + 1))
                else:
                    failed += 1
                    log(f"Permanent Xiao batch failure {batch.batch_idx}: {st.get('error_message', 'unknown')}")
    log(f"Xiao repair extraction finished: completed={completed:,} failed={failed:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract backfill Xiao repair lookup for missing clean coords")
    parser.add_argument("--manifest-table", default=MANIFEST_TABLE)
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--pool-size", type=int, default=4)
    parser.add_argument("--start-batch", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id", default=f"backfill_xiao_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)
    table = client.get_table(args.manifest_table)
    est_batches = math.ceil(table.num_rows / args.batch_size) if table.num_rows else 0
    log(f"Manifest table: {args.manifest_table}")
    log(f"Manifest rows: {table.num_rows:,}")
    log(f"Batch size: {args.batch_size:,} | est batches: {est_batches:,} | pool: {args.pool_size}")
    log(f"Dest table: {args.dest_table}")
    if args.dry_run:
        return
    ee.Initialize(project=PROJECT)
    run_pool(client, args.manifest_table, args.dest_table, args.batch_size, args.pool_size, args.start_batch, args.max_batches, args.run_id, (args.max_batches if args.max_batches is not None else max(est_batches - args.start_batch, 0)))


if __name__ == "__main__":
    main()
