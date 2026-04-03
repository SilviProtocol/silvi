#!/usr/bin/env python3
"""
GEE Deduplicated Sampler - Cost-Optimized Phase 1 Completion
=============================================================

This sampler:
1. Deduplicates pixels to ~10m precision (4 decimal places)
2. Excludes already-processed pixel-years from BigQuery exports
3. Samples BOTH AlphaEarth AND Hansen data in one pass
4. Includes SRTM elevation data

Cost Reduction:
- Original: 16.5M occurrences = $4,000+ at naive pricing
- Deduplicated: 2.1M unique pixel-years = ~$2,000
- Already processed: 310K = $300 spent
- Remaining: 2.1M - 0.3M = 1.8M pixel-years = ~$1,800

Usage:
    # Dry run to see what would be processed
    python3 gee_sampler_deduplicated.py --dry-run

    # Test with small batch
    python3 gee_sampler_deduplicated.py --test 1000

    # Process a specific year
    python3 gee_sampler_deduplicated.py --year 2019

    # Process all remaining data
    python3 gee_sampler_deduplicated.py --all

Author: Treekipedia Team
Created: January 2026
"""

import ee
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Set, Tuple
import time
import json
from pathlib import Path
from datetime import datetime
import argparse

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE = 'occ_embeddings_hansen_elev_v4'  # New table for deduplicated run

# Data sources
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'
SRTM_ASSET = 'USGS/SRTMGL1_003'

# Processing settings
DEFAULT_BATCH_SIZE = 2000  # Points per GEE task
DEFAULT_SCALE = 10  # 10m resolution (AlphaEarth native)
HANSEN_SCALE = 30  # Hansen is 30m resolution
COORD_DECIMALS = 4  # ~10m precision for deduplication

# Paths
SCRIPT_DIR = Path(__file__).parent
EXPORTS_DIR = SCRIPT_DIR / 'bigquery_exports'
EXTRACTIONS_DIR = SCRIPT_DIR / 'alphaearth_extractions'


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
        print("Run 'earthengine authenticate' if needed")
        return False


# =============================================================================
# DATA LOADING & DEDUPLICATION
# =============================================================================

def load_processed_pixel_years() -> Set[str]:
    """
    Load already-processed pixel-year combinations from BigQuery exports.

    Returns set of "lat_lon_year" keys that we don't need to process again.
    """
    processed_keys = set()

    # Load v3 exports (most complete)
    v3_files = list(EXPORTS_DIR.glob('occ_embeddings_hansen_elev_v3_*.parquet'))

    if not v3_files:
        print("  No existing processed data found")
        return processed_keys

    for f in v3_files:
        df = pd.read_parquet(f)
        df['lat_round'] = df['latitude'].round(COORD_DECIMALS)
        df['lon_round'] = df['longitude'].round(COORD_DECIMALS)

        for _, row in df.iterrows():
            key = f"{row['lat_round']}_{row['lon_round']}_{row['emb_year']}"
            processed_keys.add(key)

    print(f"  Loaded {len(processed_keys):,} already-processed pixel-years")
    return processed_keys


def load_and_deduplicate_phase1(year: Optional[int] = None) -> pd.DataFrame:
    """
    Load Phase 1 data and deduplicate to unique pixel-year combinations.

    Args:
        year: If specified, only load this year

    Returns:
        DataFrame with unique pixel-years (deduplicated)
    """
    # Find Phase 1 file
    phase1_files = list(EXTRACTIONS_DIR.glob('alphaearth_phase1_*.parquet'))
    if not phase1_files:
        raise FileNotFoundError("No Phase 1 parquet file found!")

    phase1_path = sorted(phase1_files)[-1]
    print(f"  Loading: {phase1_path.name}")

    df = pd.read_parquet(phase1_path)

    if year:
        df = df[df['embedding_year'] == year]
        print(f"  Filtered to year {year}: {len(df):,} rows")

    # Round coordinates for deduplication
    df['lat_round'] = df['decimalLatitude'].round(COORD_DECIMALS)
    df['lon_round'] = df['decimalLongitude'].round(COORD_DECIMALS)

    # Create pixel-year key
    df['pixel_year_key'] = (
        df['lat_round'].astype(str) + '_' +
        df['lon_round'].astype(str) + '_' +
        df['embedding_year'].astype(str)
    )

    # Deduplicate: keep first occurrence of each pixel-year
    # We keep taxon_id for reference but the embedding is the same for all species at that pixel
    before = len(df)
    df_dedup = df.drop_duplicates(subset=['pixel_year_key'], keep='first')
    after = len(df_dedup)

    print(f"  Deduplicated: {before:,} -> {after:,} ({100*(1-after/before):.1f}% reduction)")

    return df_dedup


def get_remaining_pixels(
    phase1_df: pd.DataFrame,
    processed_keys: Set[str]
) -> pd.DataFrame:
    """
    Filter to only pixels that haven't been processed yet.
    """
    remaining = phase1_df[~phase1_df['pixel_year_key'].isin(processed_keys)]
    print(f"  Remaining after excluding processed: {len(remaining):,}")
    return remaining


# =============================================================================
# COORDINATE UTILITIES
# =============================================================================

def ensure_float_coordinate(value: float) -> float:
    """
    Ensure coordinate is a proper float, not interpretable as integer.
    """
    float_val = float(value)
    if float_val == int(float_val):
        return float_val + 1e-10
    return float_val


# =============================================================================
# IMAGE GETTERS
# =============================================================================

def get_alphaearth_mosaic(year: int) -> ee.Image:
    """Get AlphaEarth mosaic image for a given year."""
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    return col.mosaic()


def get_hansen_image() -> ee.Image:
    """Get Hansen Global Forest Change image with selected bands."""
    hansen = ee.Image(HANSEN_ASSET)
    treecover = hansen.select('treecover2000')
    lossyear = hansen.select('lossyear').unmask(0)
    loss = hansen.select('loss')
    gain = hansen.select('gain')
    return treecover.addBands(lossyear).addBands(loss).addBands(gain)


def get_srtm_image() -> ee.Image:
    """Get SRTM elevation data."""
    return ee.Image(SRTM_ASSET).select('elevation')


# =============================================================================
# COMBINED SAMPLER
# =============================================================================

def sample_deduplicated(
    points_df: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False
) -> List[str]:
    """
    Sample AlphaEarth + Hansen + SRTM for deduplicated pixel-years.

    Args:
        points_df: DataFrame with deduplicated pixel-years
        batch_size: Points per export task
        dry_run: If True, just show what would be done

    Returns:
        List of GEE task IDs
    """
    if len(points_df) == 0:
        print("No points to process!")
        return []

    # Convert to list of dicts
    points = []
    for _, row in points_df.iterrows():
        points.append({
            'taxon_id': row['taxon_id'],  # Keep for reference
            'latitude': row['lat_round'],
            'longitude': row['lon_round'],
            'year': int(row.get('year', row['embedding_year'])),
            'embedding_year': int(row['embedding_year'])
        })

    n_tasks = (len(points) - 1) // batch_size + 1

    print(f"\n{'='*60}")
    print(f"SAMPLING {len(points):,} UNIQUE PIXEL-YEARS")
    print(f"{'='*60}")
    print(f"  Tasks: {n_tasks}")
    print(f"  Batch size: {batch_size}")
    print(f"  Target table: {PROJECT}.{BQ_DATASET}.{BQ_TABLE}")

    if dry_run:
        print("\n  [DRY RUN - no tasks submitted]")
        return []

    # Get static images
    hansen_img = get_hansen_image()
    srtm_img = get_srtm_image()

    task_ids = []
    total_chunks = n_tasks

    for chunk_idx, chunk_start in enumerate(range(0, len(points), batch_size)):
        chunk = points[chunk_start:chunk_start + batch_size]

        # Create features
        features = []
        for p in chunk:
            lat = ensure_float_coordinate(p['latitude'])
            lon = ensure_float_coordinate(p['longitude'])

            feat = ee.Feature(
                ee.Geometry.Point([lon, lat]),
                {
                    'taxon_id': str(p['taxon_id']),
                    'emb_year': int(p['embedding_year']),
                    'orig_year': int(p['year']),
                    'latitude': ee.Number(lat).toFloat(),
                    'longitude': ee.Number(lon).toFloat()
                }
            )
            features.append(feat)

        fc = ee.FeatureCollection(features)

        # Group by embedding year
        years = sorted({p['embedding_year'] for p in chunk})

        # Sample each year
        sampled_all = ee.FeatureCollection([])

        for year in years:
            ae_img = get_alphaearth_mosaic(year)
            fc_year = fc.filter(ee.Filter.eq('emb_year', year))

            # Step 1: Sample AlphaEarth at 10m WITH geometry
            ae_sampled = ae_img.sampleRegions(
                collection=fc_year,
                scale=DEFAULT_SCALE,
                geometries=True,
                tileScale=4
            )

            # Step 2: Add Hansen data at 30m
            with_hansen = hansen_img.reduceRegions(
                collection=ae_sampled,
                reducer=ee.Reducer.first(),
                scale=HANSEN_SCALE
            )

            # Step 3: Add SRTM elevation
            with_all = srtm_img.reduceRegions(
                collection=with_hansen,
                reducer=ee.Reducer.first(),
                scale=30
            )

            sampled_all = sampled_all.merge(with_all)

        # Export to BigQuery
        task_desc = f'dedup_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{chunk_idx:04d}'

        task = ee.batch.Export.table.toBigQuery(
            collection=sampled_all,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}',
            append=True,
            overwrite=False
        )
        task.start()
        task_ids.append(task.id)

        if (chunk_idx + 1) % 10 == 0 or chunk_idx == 0:
            print(f"  Chunk {chunk_idx + 1}/{total_chunks}: {len(chunk)} pts, years {years}")

    print(f"\n  Submitted {len(task_ids)} tasks")
    return task_ids


# =============================================================================
# TASK MONITORING
# =============================================================================

def check_task_status(task_id: str) -> Dict:
    """Check GEE task status."""
    try:
        status = ee.data.getTaskStatus(task_id)[0]
        return {
            'id': task_id,
            'state': status['state'],
            'error_message': status.get('error_message')
        }
    except Exception as e:
        return {
            'id': task_id,
            'state': 'UNKNOWN',
            'error_message': str(e)
        }


def wait_for_tasks(task_ids: List[str], poll_interval: int = 60) -> Dict:
    """Wait for GEE tasks to complete."""
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
                elapsed = time.time() - start_time
                print(f"  Completed: {len(completed)}/{len(task_ids)} ({elapsed/60:.1f}min)")

            elif status['state'] == 'FAILED':
                error = status['error_message'] or 'Unknown error'
                failed.append((task_id, error))
                pending.remove(task_id)
                print(f"  FAILED: {error[:100]}")

        if pending and len(pending) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  Pending: {len(pending)} ({elapsed/60:.1f}min elapsed)")

    total_time = time.time() - start_time
    return {
        'completed': completed,
        'failed': failed,
        'total_time_seconds': total_time
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='GEE Deduplicated Sampler')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without submitting')
    parser.add_argument('--test', type=int, help='Test with N samples')
    parser.add_argument('--year', type=int, help='Process specific year (2017-2024)')
    parser.add_argument('--all', action='store_true', help='Process all remaining data')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='Batch size')
    parser.add_argument('--no-wait', action='store_true', help='Submit tasks but dont wait')

    args = parser.parse_args()

    print("=" * 70)
    print("GEE DEDUPLICATED SAMPLER - COST-OPTIMIZED PHASE 1")
    print("=" * 70)

    # Initialize GEE
    if not initialize_gee():
        return

    # Load already-processed data
    print("\n1. LOADING PROCESSED DATA:")
    processed_keys = load_processed_pixel_years()

    # Load and deduplicate Phase 1
    print("\n2. LOADING PHASE 1 DATA:")
    phase1_df = load_and_deduplicate_phase1(year=args.year)

    # Get remaining pixels
    print("\n3. CALCULATING REMAINING WORK:")
    remaining_df = get_remaining_pixels(phase1_df, processed_keys)

    if len(remaining_df) == 0:
        print("\nAll data already processed!")
        return

    # Show summary by year
    print("\n  By year:")
    for year in sorted(remaining_df['embedding_year'].unique()):
        year_count = len(remaining_df[remaining_df['embedding_year'] == year])
        print(f"    {year}: {year_count:,} unique pixel-years")

    # Cost estimate
    cost_per_pixel = 0.00097
    estimated_cost = len(remaining_df) * cost_per_pixel
    print(f"\n  Estimated cost: ${estimated_cost:,.0f}")

    # Test mode: sample subset
    if args.test:
        print(f"\n  [TEST MODE: Using {args.test} samples]")
        remaining_df = remaining_df.sample(n=min(args.test, len(remaining_df)), random_state=42)

    # Process
    print("\n4. PROCESSING:")
    task_ids = sample_deduplicated(
        remaining_df,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    if not task_ids:
        return

    # Save task IDs
    task_file = EXTRACTIONS_DIR / f'dedup_tasks_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(task_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'n_pixels': len(remaining_df),
            'n_tasks': len(task_ids),
            'task_ids': task_ids,
            'year_filter': args.year,
            'estimated_cost': estimated_cost
        }, f, indent=2)
    print(f"\n  Task IDs saved to: {task_file}")

    # Wait for completion
    if not args.no_wait:
        print("\n5. MONITORING:")
        results = wait_for_tasks(task_ids, poll_interval=60)

        print(f"\n{'='*70}")
        print("COMPLETED")
        print(f"{'='*70}")
        print(f"  Successful: {len(results['completed'])}")
        print(f"  Failed: {len(results['failed'])}")
        print(f"  Time: {results['total_time_seconds']/60:.1f} minutes")

        if results['completed']:
            print(f"\n  Data in: {PROJECT}.{BQ_DATASET}.{BQ_TABLE}")
    else:
        print("\n  [--no-wait: Tasks running in background]")
        print(f"  Monitor at: https://code.earthengine.google.com/tasks")


if __name__ == '__main__':
    main()
