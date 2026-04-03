#!/usr/bin/env python3
"""
Backfill Elevation for v2 Records
==================================

Samples ONLY elevation for occurrences that already have AlphaEarth embeddings
in the v2 table, then exports to a separate table for JOIN.

This avoids re-requesting expensive AlphaEarth embeddings.

Usage:
    python backfill_elevation_v2.py --year 2017 --end-chunk 767  # Backfill completed 2017 chunks
    python backfill_elevation_v2.py --status                     # Check task status

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
BQ_TABLE_ELEVATION = 'occ_elevation_backfill'  # Elevation-only table

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

def get_srtm_image() -> ee.Image:
    """Get SRTM 30m elevation."""
    return ee.Image(SRTM_ASSET).select('elevation')


# =============================================================================
# DATA LOADING
# =============================================================================

def load_year_data(year: int) -> pd.DataFrame:
    """Load Phase 1 data for a specific year."""
    df = pd.read_parquet(PHASE1_FILE)
    df_year = df[df['year'] == year]
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
# ELEVATION-ONLY SAMPLING
# =============================================================================

def process_elevation_only(year: int, points: List[Dict],
                           start_chunk: int = 0, end_chunk: int = None,
                           batch_size: int = BATCH_SIZE) -> List[str]:
    """
    Sample ONLY elevation for points (no AlphaEarth, no Hansen).

    Args:
        year: The year being processed
        points: List of point dictionaries
        start_chunk: Starting chunk index
        end_chunk: Ending chunk index (exclusive)
        batch_size: Points per task

    Returns list of GEE task IDs.
    """
    if not points:
        print(f"No points for year {year}")
        return []

    total_chunks = (len(points) - 1) // batch_size + 1
    if end_chunk is None:
        end_chunk = total_chunks

    print(f"\n{'='*60}")
    print(f"ELEVATION BACKFILL - YEAR {year}")
    print(f"{'='*60}")
    print(f"Points: {len(points):,}")
    print(f"Processing chunks: {start_chunk} to {end_chunk-1} ({end_chunk - start_chunk} chunks)")
    print(f"Target table: {PROJECT}.{BQ_DATASET}.{BQ_TABLE_ELEVATION}")

    # Get SRTM image
    srtm_img = get_srtm_image()

    task_ids = []

    for chunk_idx in range(start_chunk, end_chunk):
        chunk_start = chunk_idx * batch_size
        chunk = points[chunk_start:chunk_start + batch_size]

        # Create features with minimal properties (just enough to JOIN later)
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

        # Sample ONLY elevation (much faster than full pipeline)
        with_elevation = srtm_img.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.first(),
            scale=30
        )

        # Export
        task_desc = f'elev_backfill_{year}_{chunk_idx:04d}'
        task = ee.batch.Export.table.toBigQuery(
            collection=with_elevation,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE_ELEVATION}',
            append=True,
            overwrite=False
        )
        task.start()
        task_ids.append(task.id)

        chunks_done = chunk_idx - start_chunk + 1
        chunks_total = end_chunk - start_chunk
        if chunks_done % 10 == 0 or chunks_done == 1:
            print(f"  Started {chunks_done}/{chunks_total} tasks (chunk {chunk_idx})...")

    print(f"  Started all {len(task_ids)} elevation backfill tasks for {year}")
    return task_ids


# =============================================================================
# TASK MANAGEMENT
# =============================================================================

def save_task_ids(year: int, task_ids: List[str], start_chunk: int, end_chunk: int):
    """Save task IDs to file for monitoring."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    filename = TASKS_DIR / f'elev_backfill_{year}_chunks{start_chunk}-{end_chunk}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    data = {
        'year': year,
        'type': 'elevation_backfill',
        'start_chunk': start_chunk,
        'end_chunk': end_chunk,
        'timestamp': datetime.now().isoformat(),
        'n_tasks': len(task_ids),
        'task_ids': task_ids,
        'table': f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE_ELEVATION}'
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


def check_all_backfill_status():
    """Check status of all elevation backfill task files."""
    if not TASKS_DIR.exists():
        print("No tasks directory found")
        return

    task_files = sorted(TASKS_DIR.glob('elev_backfill_*.json'))
    if not task_files:
        print("No elevation backfill task files found")
        return

    initialize_gee()

    print(f"\n{'='*60}")
    print("ELEVATION BACKFILL STATUS")
    print(f"{'='*60}")

    for task_file in task_files:
        with open(task_file) as f:
            data = json.load(f)

        year = data['year']
        task_ids = data['task_ids']

        # Check all tasks
        states = {}
        for tid in task_ids:
            status = check_task_status(tid)
            state = status['state']
            states[state] = states.get(state, 0) + 1

        print(f"\n{task_file.name}")
        print(f"  Year: {year}, Chunks: {data['start_chunk']}-{data['end_chunk']}")
        print(f"  Status: {dict(states)}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Backfill elevation for v2 records')
    parser.add_argument('--year', type=int, help='Year to backfill (2017 or 2018)')
    parser.add_argument('--start-chunk', type=int, default=0, help='Starting chunk index')
    parser.add_argument('--end-chunk', type=int, help='Ending chunk index (exclusive)')
    parser.add_argument('--status', action='store_true', help='Check backfill task status')

    args = parser.parse_args()

    if args.status:
        check_all_backfill_status()
        return

    if not args.year:
        print("\nElevation Backfill Tool")
        print("=" * 40)
        print("\nThis tool samples ONLY elevation for occurrences")
        print("that already have AlphaEarth embeddings in v2.")
        print("\nKnown v2 completed chunks:")
        print("  2017: chunks 0-766 (767 tasks, ~1.53M points)")
        print("  2018: none (all cancelled)")
        print("\nUsage:")
        print("  python backfill_elevation_v2.py --year 2017 --end-chunk 767")
        print("  python backfill_elevation_v2.py --status")
        return

    if not initialize_gee():
        return

    # Load data
    df_year = load_year_data(args.year)
    if len(df_year) == 0:
        print(f"No data for year {args.year}")
        return

    points = df_to_points(df_year, args.year)

    # Process elevation only
    task_ids = process_elevation_only(
        args.year,
        points,
        start_chunk=args.start_chunk,
        end_chunk=args.end_chunk
    )

    if task_ids:
        save_task_ids(args.year, task_ids, args.start_chunk, args.end_chunk or len(task_ids))

    print(f"\n{'='*60}")
    print("ELEVATION BACKFILL STARTED")
    print(f"{'='*60}")
    print(f"Tasks are running in GEE background")
    print(f"Use --status to check progress")
    print(f"\nAfter completion, JOIN in BigQuery:")
    print(f"""
SELECT
    v2.*,
    elev.elevation
FROM `{PROJECT}.{BQ_DATASET}.occ_embeddings_hansen_v2` v2
JOIN `{PROJECT}.{BQ_DATASET}.{BQ_TABLE_ELEVATION}` elev
ON v2.taxon_id = elev.taxon_id
   AND v2.latitude = elev.latitude
   AND v2.longitude = elev.longitude
   AND v2.emb_year = elev.emb_year
""")


if __name__ == '__main__':
    main()
