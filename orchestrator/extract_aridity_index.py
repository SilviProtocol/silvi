#!/usr/bin/env python3
"""
extract_aridity_index.py — Sample Global Aridity Index + ET0 at SINR v3 training points.

Samples from the Global Aridity Index v3 dataset (Trabucco & Zomer, 2022):
  - Annual Aridity Index (P/PET ratio, dimensionless × 10000)
  - Annual Reference Evapotranspiration ET0 (mm/year × 10)

OPTIMIZED: Deduplicates to 2dp (~1.1km) since native resolution is 1km.
  - 13.6M raw points → ~3.3M unique 1km grid cells
  - BQ-side dedup (fast) instead of Python-side (slow)
  - Larger batches (10K) since only 2 bands to sample

Output BQ table: species_data.sinr_v3_aridity_index

Usage:
  python3 extract_aridity_index.py --all --pool-size 25
  python3 extract_aridity_index.py --all --pool-size 25 --resume-from-bq
"""

import argparse
import ee
import time
from typing import Set

# =============================================================================
# CONFIGURATION
# =============================================================================

GEE_PROJECT = 'treekipedia-479918'
BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_OUTPUT_TABLE = 'sinr_v3_aridity_index'

BATCH_SIZE = 10000      # Larger OK — only 2 bands, static dataset
SAMPLE_SCALE = 1000     # ~1km native resolution
DEDUP_DECIMALS = 2      # Round to 2dp (~1.1km) — matches native resolution
POLL_INTERVAL_SEC = 10
MAX_RETRIES = 3

# GEE Assets — Global Aridity Index v3 (Trabucco & Zomer 2022)
AI_ASSET = 'projects/sat-io/open-datasets/global_ai/global_ai_yearly'
ET0_ASSET = 'projects/sat-io/open-datasets/global_et0/global_et0_yearly'

# =============================================================================
# LOGGING
# =============================================================================

def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# GEE IMAGE
# =============================================================================

def build_aridity_image() -> ee.Image:
    """Build the aridity index + ET0 image from separate GEE assets."""
    ai_img = ee.Image(AI_ASSET)
    ai_raw = ai_img.select('b1').rename('aridity_index_raw')
    ai_real = ai_raw.divide(10000).rename('aridity_index')

    et0_img = ee.Image(ET0_ASSET)
    et0_raw = et0_img.select('b1').rename('et0_mm_yr_raw')
    et0_real = et0_raw.divide(10).rename('et0_mm_yr')

    combined = (ai_raw
        .addBands(et0_raw)
        .addBands(ai_real)
        .addBands(et0_real)
    ).unmask(-9999).toFloat()

    return combined


# =============================================================================
# BIGQUERY — FAST SERVER-SIDE DEDUP
# =============================================================================

def load_population_fast(mode: str):
    """Load unique ~1km grid cells from BQ using server-side dedup.

    At 2 decimal places (~1.1km), 13.6M points → ~3.3M unique cells.
    This is the right resolution since the aridity dataset is 1km native.
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)

    unions = []
    if mode in ('new_gbif', 'all'):
        unions.append(f"SELECT latitude, longitude FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_new_gbif`")
    if mode in ('backfill', 'all'):
        unions.append(f"SELECT latitude, longitude FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_backfill`")

    union_sql = " UNION ALL ".join(unions)
    dp = DEDUP_DECIMALS

    query = f"""
    SELECT DISTINCT
        ROUND(latitude, {dp}) as lat,
        ROUND(longitude, {dp}) as lon
    FROM ({union_sql})
    """

    log(f"Running BQ dedup query (ROUND to {dp}dp ≈ {10**(5-dp)/100:.1f}km)...")
    df = client.query(query).to_dataframe()

    # Convert to list of plain Python float tuples — numpy types cause GEE serialization issues
    points = [(float(lat), float(lon)) for lat, lon in zip(df['lat'].values, df['lon'].values)]
    log(f"Got {len(points):,} unique ~1km grid cells from BQ")
    return points


def load_completed_keys() -> Set[str]:
    """Load already-completed pixel keys from BQ for resume."""
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    dp = DEDUP_DECIMALS

    try:
        query = f"""
        SELECT DISTINCT
            CONCAT(
                CAST(ROUND(latitude, {dp}) AS STRING), '|',
                CAST(ROUND(longitude, {dp}) AS STRING)
            ) as key
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}`
        """
        df = client.query(query).to_dataframe()
        keys = set(df['key'].values)
        log(f"Found {len(keys):,} completed pixels in {BQ_OUTPUT_TABLE}")
        return keys
    except Exception as e:
        log(f"No completed pixels found (table may not exist): {e}")
        return set()


# =============================================================================
# GEE TASK MANAGEMENT
# =============================================================================

def make_feature_collection(batch):
    """Convert batch of (lat, lon) tuples to ee.FeatureCollection.

    Uses list comprehension instead of append loop for speed.
    """
    features = [
        ee.Feature(
            ee.Geometry.Point([float(lon), float(lat)]),
            {'latitude': ee.Number(float(lat)).toFloat(),
             'longitude': ee.Number(float(lon)).toFloat()}
        )
        for lat, lon in batch
    ]
    return ee.FeatureCollection(features)


def submit_batch(batch, batch_id, image):
    """Submit a GEE sampling task to BigQuery."""
    fc = make_feature_collection(batch)
    sampled = image.sampleRegions(
        collection=fc,
        scale=SAMPLE_SCALE,
        geometries=False
    )

    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=f'aridity_batch_{batch_id}',
        table=f'{BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}',
        append=True
    )
    task.start()
    return task


def run_pool(batches, image, pool_size):
    """Run GEE tasks with a rolling pool. First batch runs alone to verify schema."""
    total_batches = len(batches)
    completed = 0
    failed = 0
    next_idx = 0
    active_tasks = {}

    log(f"Starting {total_batches} batches with pool_size={pool_size}")

    # Fill the pool
    while completed + failed < total_batches:
        while len(active_tasks) < pool_size and next_idx < total_batches:
            batch_id = next_idx
            try:
                task = submit_batch(batches[batch_id], batch_id, image)
                active_tasks[task.id] = (task, batch_id, 0)
                next_idx += 1
                if next_idx % 10 == 0:
                    log(f"  Submitted {next_idx}/{total_batches} batches...")
            except Exception as e:
                log(f"  ERROR submitting batch {batch_id}: {e}")
                next_idx += 1
                failed += 1

        if not active_tasks:
            break

        time.sleep(POLL_INTERVAL_SEC)
        done_ids = []

        for task_id, (task, batch_id, retries) in active_tasks.items():
            try:
                status = task.status()
                state = status.get('state', 'UNKNOWN')

                if state == 'COMPLETED':
                    done_ids.append(task_id)
                    completed += 1
                    total_done = completed + failed
                    pct = 100 * total_done / total_batches
                    log(f"  Batch {batch_id} done ({completed}/{total_batches}, {pct:.1f}%)")

                elif state == 'FAILED':
                    error = status.get('error_message', 'unknown error')
                    done_ids.append(task_id)
                    if retries < MAX_RETRIES:
                        log(f"  Batch {batch_id} failed (retry {retries+1}/{MAX_RETRIES}): {error[:120]}")
                        try:
                            new_task = submit_batch(batches[batch_id], batch_id, image)
                            active_tasks[new_task.id] = (new_task, batch_id, retries + 1)
                        except Exception as e:
                            log(f"  ERROR resubmitting batch {batch_id}: {e}")
                            failed += 1
                    else:
                        log(f"  Batch {batch_id} permanently failed: {error[:120]}")
                        failed += 1

                elif state in ('CANCEL_REQUESTED', 'CANCELLED'):
                    done_ids.append(task_id)
                    failed += 1
                    log(f"  Batch {batch_id} cancelled")

            except Exception as e:
                log(f"  Error checking task {task_id}: {e}")

        for tid in done_ids:
            active_tasks.pop(tid, None)

    log(f"\n{'='*60}")
    log(f"COMPLETE: {completed} succeeded, {failed} failed out of {total_batches}")
    log(f"{'='*60}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Sample Global Aridity Index at SINR v3 training points')
    parser.add_argument('--new-gbif', action='store_true', help='Sample at new GBIF locations')
    parser.add_argument('--backfill', action='store_true', help='Sample at backfill locations')
    parser.add_argument('--all', action='store_true', help='Sample at all locations')
    parser.add_argument('--pool-size', type=int, default=25, help='Max concurrent GEE tasks')
    parser.add_argument('--resume-from-bq', action='store_true', help='Skip already-completed pixels')
    args = parser.parse_args()

    if args.all:
        mode = 'all'
    elif args.new_gbif:
        mode = 'new_gbif'
    elif args.backfill:
        mode = 'backfill'
    else:
        parser.error("Must specify --new-gbif, --backfill, or --all")
        return

    # Initialize GEE
    log("Initializing Google Earth Engine...")
    ee.Initialize(project=GEE_PROJECT)
    log("GEE initialized")

    # Build the aridity image
    log("Building aridity index image...")
    image = build_aridity_image()
    log("Image built: aridity_index_raw, et0_mm_yr_raw, aridity_index, et0_mm_yr")

    # Load population — fast BQ-side dedup
    points = load_population_fast(mode)

    # Resume logic
    if args.resume_from_bq:
        completed_keys = load_completed_keys()
        before = len(points)
        dp = DEDUP_DECIMALS
        points = [p for p in points if f"{round(p[0], dp)}|{round(p[1], dp)}" not in completed_keys]
        log(f"Resume: {before:,} total → {len(points):,} remaining ({before - len(points):,} already done)")

    if not points:
        log("No points to sample — all done!")
        return

    # Create batches — no shuffle needed for static data
    batches = [points[i:i + BATCH_SIZE] for i in range(0, len(points), BATCH_SIZE)]
    log(f"Created {len(batches)} batches of up to {BATCH_SIZE} points each")

    # Run
    run_pool(batches, image, args.pool_size)

    log("Done! Results in BQ table: " + f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}")


if __name__ == '__main__':
    main()
