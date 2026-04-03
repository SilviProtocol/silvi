#!/usr/bin/env python3
"""
Phase 1 GEE Processing - Year by Year with Progress Tracking
=============================================================

Processes Phase 1 data one year at a time for better progress tracking.
Each year can be run independently, allowing:
- Resume from any point if interrupted
- Track progress by year
- Monitor GEE task queue more easily

Usage:
    python run_phase1_by_year.py --year 2017          # Process single year
    python run_phase1_by_year.py --year 2017 --test   # Test with 1000 points
    python run_phase1_by_year.py --all                # Process all years
    python run_phase1_by_year.py --status             # Check task status

Author: Treekipedia Team
Created: January 2026
"""

import ee
import pandas as pd
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE = 'occ_embeddings_hansen_elev_v3'  # New table with elevation

AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'
SRTM_ASSET = 'USGS/SRTMGL1_003'  # 30m SRTM elevation

BATCH_SIZE = 2000
PHASE1_FILE = Path(__file__).parent / 'alphaearth_extractions/alphaearth_phase1_20260119_033003.parquet'
TASKS_DIR = Path(__file__).parent / 'alphaearth_extractions/tasks'

# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_gee():
    """Initialize Google Earth Engine."""
    try:
        ee.Initialize(project=PROJECT)
        print(f"GEE initialized (project: {PROJECT})")
        return True
    except Exception as e:
        print(f"GEE initialization failed: {e}")
        return False


def ensure_float_coordinate(value: float) -> float:
    """Ensure coordinate is a proper float."""
    float_val = float(value)
    if float_val == int(float_val):
        return float_val + 1e-10
    return float_val


# =============================================================================
# IMAGE GETTERS
# =============================================================================

def get_alphaearth_mosaic(year: int) -> ee.Image:
    """Get AlphaEarth mosaic for a year."""
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    return col.mosaic()


def get_hansen_image() -> ee.Image:
    """Get Hansen image with lossyear unmask fix."""
    hansen = ee.Image(HANSEN_ASSET)
    treecover = hansen.select('treecover2000')
    lossyear = hansen.select('lossyear').unmask(0)
    loss = hansen.select('loss')
    gain = hansen.select('gain')
    return treecover.addBands(lossyear).addBands(loss).addBands(gain)


def get_srtm_image() -> ee.Image:
    """Get SRTM 30m elevation."""
    return ee.Image(SRTM_ASSET).select('elevation')


# =============================================================================
# DATA LOADING
# =============================================================================

def load_year_data(year: int, test_limit: int = None) -> pd.DataFrame:
    """Load Phase 1 data for a specific year."""
    df = pd.read_parquet(PHASE1_FILE)
    df_year = df[df['year'] == year]

    if test_limit and len(df_year) > test_limit:
        df_year = df_year.sample(n=test_limit, random_state=42)

    return df_year


def df_to_points(df: pd.DataFrame, year: int) -> List[Dict]:
    """Convert DataFrame to list of point dicts."""
    points = []
    for _, row in df.iterrows():
        points.append({
            'taxon_id': str(row['taxon_id']),
            'latitude': float(row['decimalLatitude']),
            'longitude': float(row['decimalLongitude']),
            'year': int(row['year']),
            'embedding_year': year
        })
    return points


# =============================================================================
# SAMPLING
# =============================================================================

def process_year(year: int, points: List[Dict], batch_size: int = BATCH_SIZE,
                 start_chunk: int = 0, end_chunk: int = None) -> List[str]:
    """
    Process all points for a single year.

    Args:
        year: The year to process
        points: List of point dictionaries
        batch_size: Number of points per task
        start_chunk: Starting chunk index (0-based, for resuming)
        end_chunk: Ending chunk index (exclusive, None for all)

    Returns list of GEE task IDs.
    """
    if not points:
        print(f"No points for year {year}")
        return []

    total_chunks = (len(points) - 1) // batch_size + 1
    if end_chunk is None:
        end_chunk = total_chunks

    print(f"\n{'='*60}")
    print(f"PROCESSING YEAR {year}")
    print(f"{'='*60}")
    print(f"Points: {len(points):,}")
    print(f"Total chunks: {total_chunks}")
    if start_chunk > 0 or end_chunk < total_chunks:
        print(f"Processing chunks: {start_chunk} to {end_chunk-1} ({end_chunk - start_chunk} chunks)")

    # Get images
    ae_img = get_alphaearth_mosaic(year)
    hansen_img = get_hansen_image()
    srtm_img = get_srtm_image()  # Add SRTM elevation

    task_ids = []

    for chunk_idx in range(start_chunk, end_chunk):
        chunk_start = chunk_idx * batch_size
        chunk = points[chunk_start:chunk_start + batch_size]

        # Create features
        features = []
        for p in chunk:
            lat = ensure_float_coordinate(p['latitude'])
            lon = ensure_float_coordinate(p['longitude'])

            feat = ee.Feature(
                ee.Geometry.Point([lon, lat]),
                {
                    'taxon_id': p['taxon_id'],
                    'emb_year': year,
                    'orig_year': p['year'],
                    'latitude': ee.Number(lat).toFloat(),
                    'longitude': ee.Number(lon).toFloat()
                }
            )
            features.append(feat)

        fc = ee.FeatureCollection(features)

        # Sample AlphaEarth with geometry
        ae_sampled = ae_img.sampleRegions(
            collection=fc,
            scale=10,
            geometries=True,
            tileScale=4
        )

        # Add Hansen (30m)
        with_hansen = hansen_img.reduceRegions(
            collection=ae_sampled,
            reducer=ee.Reducer.first(),
            scale=30
        )

        # Add SRTM elevation (30m)
        combined = srtm_img.reduceRegions(
            collection=with_hansen,
            reducer=ee.Reducer.first(),
            scale=30
        )

        # Export
        task_desc = f'phase1_{year}_{chunk_idx:04d}'
        task = ee.batch.Export.table.toBigQuery(
            collection=combined,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}',
            append=True,
            overwrite=False
        )
        task.start()
        task_ids.append(task.id)

        if (chunk_idx + 1) % 10 == 0 or chunk_idx == 0:
            print(f"  Started {chunk_idx + 1}/{total_chunks} tasks...")

    print(f"  Started all {len(task_ids)} tasks for {year}")
    return task_ids


# =============================================================================
# TASK MANAGEMENT
# =============================================================================

def save_task_ids(year: int, task_ids: List[str], test: bool = False):
    """Save task IDs to file for monitoring."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    suffix = '_test' if test else ''
    filename = TASKS_DIR / f'phase1_{year}{suffix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    data = {
        'year': year,
        'timestamp': datetime.now().isoformat(),
        'n_tasks': len(task_ids),
        'task_ids': task_ids,
        'table': f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}'
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Task IDs saved to: {filename}")
    return filename


def check_task_status(task_id: str) -> Dict:
    """Check single task status."""
    try:
        status = ee.data.getTaskStatus(task_id)[0]
        return {
            'id': task_id,
            'state': status['state'],
            'error': status.get('error_message')
        }
    except Exception as e:
        return {'id': task_id, 'state': 'UNKNOWN', 'error': str(e)}


def monitor_tasks(task_ids: List[str], poll_interval: int = 60) -> Dict:
    """Monitor tasks until completion."""
    pending = set(task_ids)
    completed = []
    failed = []

    print(f"\nMonitoring {len(task_ids)} tasks...")
    start_time = time.time()

    while pending:
        time.sleep(poll_interval)

        for task_id in list(pending):
            status = check_task_status(task_id)

            if status['state'] == 'COMPLETED':
                completed.append(task_id)
                pending.remove(task_id)
            elif status['state'] == 'FAILED':
                failed.append((task_id, status['error']))
                pending.remove(task_id)

        elapsed = time.time() - start_time
        print(f"  Completed: {len(completed)}, Failed: {len(failed)}, Pending: {len(pending)} ({elapsed/60:.1f} min)")

    return {'completed': completed, 'failed': failed}


def check_all_tasks_status():
    """Check status of all saved task files."""
    if not TASKS_DIR.exists():
        print("No tasks directory found")
        return

    task_files = sorted(TASKS_DIR.glob('phase1_*.json'))
    if not task_files:
        print("No task files found")
        return

    initialize_gee()

    print(f"\n{'='*60}")
    print("TASK STATUS SUMMARY")
    print(f"{'='*60}")

    for task_file in task_files:
        with open(task_file) as f:
            data = json.load(f)

        year = data['year']
        task_ids = data['task_ids']

        # Sample status check (first 5 and last 5)
        sample_ids = task_ids[:5] + task_ids[-5:] if len(task_ids) > 10 else task_ids

        states = {'COMPLETED': 0, 'RUNNING': 0, 'READY': 0, 'FAILED': 0, 'UNKNOWN': 0}
        for tid in sample_ids:
            status = check_task_status(tid)
            states[status['state']] = states.get(status['state'], 0) + 1

        print(f"\n{task_file.name}")
        print(f"  Year: {year}, Total tasks: {len(task_ids)}")
        print(f"  Sample status: {dict(states)}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Phase 1 GEE Processing by Year')
    parser.add_argument('--year', type=int, help='Process specific year (2017-2024)')
    parser.add_argument('--all', action='store_true', help='Process all years')
    parser.add_argument('--test', action='store_true', help='Test mode (1000 points)')
    parser.add_argument('--status', action='store_true', help='Check task status')
    parser.add_argument('--monitor', type=str, help='Monitor tasks from file')
    parser.add_argument('--start-chunk', type=int, default=0, help='Starting chunk index (for resuming)')
    parser.add_argument('--end-chunk', type=int, help='Ending chunk index (exclusive)')

    args = parser.parse_args()

    if args.status:
        check_all_tasks_status()
        return

    if args.monitor:
        initialize_gee()
        with open(args.monitor) as f:
            data = json.load(f)
        monitor_tasks(data['task_ids'])
        return

    if not args.year and not args.all:
        # Show summary
        df = pd.read_parquet(PHASE1_FILE)
        print(f"\nPhase 1 Summary:")
        print(f"  Total: {len(df):,} points")
        print(f"\n  By year:")
        for year in sorted(df['year'].unique()):
            count = (df['year'] == year).sum()
            tasks = (count - 1) // BATCH_SIZE + 1
            print(f"    {int(year)}: {count:>10,} points ({tasks:,} tasks)")
        print(f"\n  Use --year YYYY to process a year")
        print(f"  Use --all to process all years")
        print(f"  Use --test for test mode (1000 points)")
        return

    if not initialize_gee():
        return

    years = list(range(2017, 2025)) if args.all else [args.year]
    test_limit = 1000 if args.test else None

    for year in years:
        df_year = load_year_data(year, test_limit)
        if len(df_year) == 0:
            print(f"No data for year {year}")
            continue

        points = df_to_points(df_year, year)
        task_ids = process_year(year, points, start_chunk=args.start_chunk, end_chunk=args.end_chunk)

        if task_ids:
            save_task_ids(year, task_ids, test=args.test)

    print(f"\n{'='*60}")
    print("PROCESSING STARTED")
    print(f"{'='*60}")
    print(f"Tasks are running in GEE background")
    print(f"Use --status to check progress")
    print(f"Use --monitor <file> to wait for completion")


if __name__ == '__main__':
    main()
