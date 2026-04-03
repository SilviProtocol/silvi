#!/usr/bin/env python3
"""Extract a GEDI-only coord-grain lookup for strict SINR repair.

This script reads the distinct-coordinate manifest built by
`build_sinr_v48_gedi_coord_manifest.py`, samples the verified per-asset GEDI
images directly from Earth Engine, and appends the results to a BigQuery table.

Key semantic rules:
- no collection-level GEDI mosaic
- no `unmask(0)` for GEDI
- preserve NULL missingness
- include count/support bands and provenance columns
"""

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

MANIFEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_gedi_coord_manifest_v1"
DEST_TABLE = f"{PROJECT}.{DATASET}.sinr_v48_gedi_lookup_v1"

RH98_ASSET = "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316"
FHD_ASSET = "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316"

RH_BANDS = ["mean", "meanbase", "median", "sd", "iqr", "p95", "shan", "countf"]
FHD_BANDS = ["mean", "meanbase", "median", "sd", "iqr", "p95", "shan", "countf"]

POLL_INTERVAL_SEC = 30
MAX_RETRIES = 2


@dataclass
class BatchItem:
    batch_idx: int
    rows: list[dict]
    retry: int = 0


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def build_gedi_image() -> ee.Image:
    anchor = ee.Image.constant(1).rename("probe_anchor").toFloat()
    rh_img = ee.Image(RH98_ASSET).select(RH_BANDS, [f"rh_{b}" for b in RH_BANDS]).toFloat()
    fhd_img = ee.Image(FHD_ASSET).select(FHD_BANDS, [f"fhd_{b}" for b in FHD_BANDS]).toFloat()
    return anchor.addBands(rh_img).addBands(fhd_img)


def build_feature_collection(rows: list[dict]) -> ee.FeatureCollection:
    features = []
    for row in rows:
        geom = ee.Geometry.Point([float(row["sample_longitude"]), float(row["sample_latitude"])])
        props = {
            "coord_key": str(row["coord_key"]),
            "lat4": float(row["lat4"]),
            "lon4": float(row["lon4"]),
            "sample_latitude": float(row["sample_latitude"]),
            "sample_longitude": float(row["sample_longitude"]),
            "new_gbif_context_rows": int(row["new_gbif_context_rows"]),
            "backfill_context_rows": int(row["backfill_context_rows"]),
            "total_context_rows": int(row["total_context_rows"]),
            "in_new_gbif": bool(row["in_new_gbif"]),
            "in_backfill": bool(row["in_backfill"]),
        }
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


def annotate_sampled(fc: ee.FeatureCollection, run_id: str) -> ee.FeatureCollection:
    extracted_at = datetime.now(timezone.utc).isoformat()

    def _map_fn(f: ee.Feature) -> ee.Feature:
        feat = ee.Feature(None, ee.Feature(f).toDictionary())
        return feat.set(
            {
                "lat4": ee.Number(feat.get("lat4")).toFloat(),
                "lon4": ee.Number(feat.get("lon4")).toFloat(),
                "sample_latitude": ee.Number(feat.get("sample_latitude")).toFloat(),
                "sample_longitude": ee.Number(feat.get("sample_longitude")).toFloat(),
                "new_gbif_context_rows": ee.Number(feat.get("new_gbif_context_rows")).toInt64(),
                "backfill_context_rows": ee.Number(feat.get("backfill_context_rows")).toInt64(),
                "total_context_rows": ee.Number(feat.get("total_context_rows")).toInt64(),
                "probe_anchor": ee.Number(feat.get("probe_anchor")).toFloat(),
                "gedi_lookup_version": "v1",
                "gedi_product": "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM",
                "gedi_resolution_m": 1000,
                "gedi_temporal_contract": "full_mission_gridded_composite_2019_2023",
                "gedi_canopy_asset_id": RH98_ASSET,
                "gedi_canopy_band_set": ",".join(RH_BANDS),
                "gedi_fhd_asset_id": FHD_ASSET,
                "gedi_fhd_band_set": ",".join(FHD_BANDS),
                "gedi_extraction_run_id": run_id,
                "gedi_extracted_at_utc": extracted_at,
            }
        )

    return fc.map(_map_fn)


def submit_batch(batch: BatchItem, dest_table: str, run_id: str) -> ee.batch.Task | None:
    try:
        fc = build_feature_collection(batch.rows)
        sampled = build_gedi_image().reduceRegions(collection=fc, reducer=ee.Reducer.first(), scale=1000)
        sampled = annotate_sampled(sampled, run_id)
        desc = f"sinr_v48_gedi_lookup_b{batch.batch_idx:06d}"
        task = ee.batch.Export.table.toBigQuery(
            collection=sampled,
            description=desc,
            table=dest_table,
            append=True,
            overwrite=False,
        )
        task.start()
        return task
    except Exception as exc:
        log(f"ERROR submitting batch {batch.batch_idx}: {exc}")
        return None


def stream_manifest_batches(client: bigquery.Client, manifest_table: str, batch_size: int, start_batch: int, max_batches: int | None):
    table = client.get_table(manifest_table)
    selected_field_names = [
        "coord_key",
        "lat4",
        "lon4",
        "sample_latitude",
        "sample_longitude",
        "new_gbif_context_rows",
        "backfill_context_rows",
        "total_context_rows",
        "in_new_gbif",
        "in_backfill",
    ]
    selected_fields = [field for field in table.schema if field.name in selected_field_names]
    rows_iter = client.list_rows(table, selected_fields=selected_fields, page_size=batch_size)

    emitted = 0
    for page_idx, page in enumerate(rows_iter.pages):
        if page_idx < start_batch:
            continue
        if max_batches is not None and emitted >= max_batches:
            break
        batch_rows = [dict(row.items()) for row in page]
        if not batch_rows:
            continue
        yield BatchItem(batch_idx=page_idx, rows=batch_rows)
        emitted += 1


def run_pool(
    client: bigquery.Client,
    manifest_table: str,
    dest_table: str,
    batch_size: int,
    pool_size: int,
    start_batch: int,
    max_batches: int | None,
    run_id: str,
    total_batches: int,
) -> None:
    batch_iter = iter(stream_manifest_batches(client, manifest_table, batch_size, start_batch, max_batches))
    retry_queue: list[BatchItem] = []
    if total_batches == 0:
        log("No GEDI manifest batches to process")
        return

    log(f"Starting GEDI lookup extraction: {total_batches:,} batches -> {dest_table}")
    active: dict[str, tuple[ee.batch.Task, BatchItem, float]] = {}
    completed = 0
    failed = 0
    more_batches = True

    while retry_queue or active or more_batches:
        while len(active) < pool_size:
            if retry_queue:
                batch = retry_queue.pop(0)
            elif more_batches:
                try:
                    batch = next(batch_iter)
                except StopIteration:
                    more_batches = False
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
            active[task.id] = (task, batch, time.time())

        if not active:
            break

        time.sleep(POLL_INTERVAL_SEC)
        for task_id in list(active.keys()):
            task, batch, start_time = active[task_id]
            try:
                status = task.status()
            except Exception as exc:
                log(f"Warning checking batch {batch.batch_idx}: {exc}")
                continue

            state = status.get("state", "UNKNOWN")
            if state in ("COMPLETED", "SUCCEEDED"):
                completed += 1
                del active[task_id]
                if completed % 20 == 0 or completed == total_batches:
                    log(
                        f"Completed {completed:,}/{total_batches:,} GEDI batches "
                        f"({100.0 * completed / total_batches:.2f}%)"
                    )
            elif state in ("FAILED", "CANCELLED", "CANCEL_REQUESTED"):
                err = status.get("error_message", "unknown")
                del active[task_id]
                if batch.retry < MAX_RETRIES:
                    retry_queue.append(BatchItem(batch_idx=batch.batch_idx, rows=batch.rows, retry=batch.retry + 1))
                else:
                    failed += 1
                    log(f"Permanent GEDI batch failure {batch.batch_idx}: {err}")

    log(f"GEDI extraction finished: completed={completed:,} failed={failed:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract GEDI-only coord lookup to BigQuery")
    parser.add_argument("--manifest-table", default=MANIFEST_TABLE)
    parser.add_argument("--dest-table", default=DEST_TABLE)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--pool-size", type=int, default=8)
    parser.add_argument("--start-batch", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id", default=f"gedi_lookup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    args = parser.parse_args()

    if args.dry_run:
        log(f"Manifest table: {args.manifest_table}")
        log(f"Dest table: {args.dest_table}")
        log(f"Batch size: {args.batch_size:,} | pool: {args.pool_size}")
        log(f"Run id: {args.run_id}")
        return

    client = bigquery.Client(project=PROJECT)
    table = client.get_table(args.manifest_table)
    est_batches = math.ceil(table.num_rows / args.batch_size) if table.num_rows else 0

    log(f"Manifest table: {args.manifest_table}")
    log(f"Manifest rows: {table.num_rows:,}")
    log(f"Batch size: {args.batch_size:,} | est batches: {est_batches:,} | pool: {args.pool_size}")
    log(f"Dest table: {args.dest_table}")
    log(f"Run id: {args.run_id}")

    ee.Initialize(project=PROJECT)
    run_pool(
        client=client,
        manifest_table=args.manifest_table,
        dest_table=args.dest_table,
        batch_size=args.batch_size,
        pool_size=args.pool_size,
        start_batch=args.start_batch,
        max_batches=args.max_batches,
        run_id=args.run_id,
        total_batches=(args.max_batches if args.max_batches is not None else est_batches - args.start_batch),
    )


if __name__ == "__main__":
    main()
