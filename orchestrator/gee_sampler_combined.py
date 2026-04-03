#!/usr/bin/env python3
"""
GEE Combined Sampler - AlphaEarth + Hansen in Parallel
=======================================================

Purpose: Sample BOTH AlphaEarth embeddings AND Hansen Global Forest Change
data for occurrence points. This enables:

1. Phase 1: Generate embeddings + collect Hansen data to validate forest filtering
2. Phase 2: Use validated Hansen thresholds to filter historical data

Hansen Bands Collected:
- treecover2000: Tree canopy cover (0-100%)
- lossyear: Year of forest loss (0 = no loss, 1-23 = loss year since 2000)
- gain: Forest gain 2000-2020 (binary)

Output Schema (BigQuery):
- taxon_id, latitude, longitude, emb_year, orig_year
- A00-A63 (AlphaEarth 64-D embedding)
- treecover2000, lossyear, gain (Hansen forest data)

Author: Treekipedia Team
Created: January 2026
"""

import ee
import pandas as pd
from typing import List, Dict, Optional
import time
import json
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE_COMBINED = 'occ_embeddings_hansen_v2'  # Table with AlphaEarth + Hansen (incl. lossyear fix)

# Data sources
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'

# Processing settings
DEFAULT_BATCH_SIZE = 2000  # Points per GEE task
DEFAULT_SCALE = 10  # 10m resolution (AlphaEarth native)
HANSEN_SCALE = 30  # Hansen is 30m resolution

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
# COORDINATE UTILITIES
# =============================================================================

def ensure_float_coordinate(value: float) -> float:
    """
    Ensure coordinate is a proper float, not interpretable as integer.

    Earth Engine can misinterpret exact integer values (like -4.0, 152.0) as integers,
    causing type incompatibility errors during BigQuery export.
    """
    float_val = float(value)
    if float_val == int(float_val):
        # Add tiny epsilon to force decimal representation
        return float_val + 1e-10
    return float_val


# =============================================================================
# IMAGE GETTERS
# =============================================================================

def get_alphaearth_mosaic(year: int) -> ee.Image:
    """
    Get AlphaEarth mosaic image for a given year.

    Uses .mosaic() to combine ~11K tiles into single global image.
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    return col.mosaic()


def get_hansen_image() -> ee.Image:
    """
    Get Hansen Global Forest Change image with selected bands.

    Returns image with:
    - treecover2000: Tree canopy cover percentage (0-100)
    - lossyear: Year of loss (0 = no loss, 1-23 = 2001-2023)
    - loss: Binary loss indicator (0 = no loss, 1 = loss occurred)
    - gain: Forest gain 2000-2020 (binary)

    NOTE: lossyear is masked where no loss occurred. We use .unmask(0) to
    convert these to 0, ensuring the column is always exported to BigQuery.
    """
    hansen = ee.Image(HANSEN_ASSET)

    # Select bands and unmask lossyear (it's masked where no loss occurred)
    treecover = hansen.select('treecover2000')
    lossyear = hansen.select('lossyear').unmask(0)  # Convert mask to 0
    loss = hansen.select('loss')  # Binary: 0 or 1
    gain = hansen.select('gain')

    return treecover.addBands(lossyear).addBands(loss).addBands(gain)


# =============================================================================
# COMBINED SAMPLER
# =============================================================================

def sample_combined(
    points: List[Dict],
    batch_size: int = DEFAULT_BATCH_SIZE,
    table_suffix: str = ''
) -> List[str]:
    """
    Sample BOTH AlphaEarth AND Hansen data for occurrence points.

    Pipeline:
    1. Sample AlphaEarth embeddings with geometry preservation
    2. Use reduceRegions to add Hansen data to each feature
    3. Export combined results to BigQuery

    Args:
        points: List of {taxon_id, latitude, longitude, year, embedding_year}
        batch_size: Points per export task
        table_suffix: Optional suffix for BigQuery table name

    Returns:
        List of GEE task IDs
    """
    if not points:
        print("No points to process")
        return []

    table_name = f'{BQ_TABLE_COMBINED}{table_suffix}'
    print(f"\nProcessing {len(points):,} points -> {PROJECT}.{BQ_DATASET}.{table_name}")

    # Get Hansen image (static, applies to all points)
    hansen_img = get_hansen_image()

    task_ids = []
    total_chunks = (len(points) - 1) // batch_size + 1

    for chunk_idx, chunk_start in enumerate(range(0, len(points), batch_size)):
        chunk = points[chunk_start:chunk_start + batch_size]

        # Create features with coordinate fix
        features = []
        for p in chunk:
            lat = ensure_float_coordinate(p['latitude'])
            lon = ensure_float_coordinate(p['longitude'])

            feat = ee.Feature(
                ee.Geometry.Point([lon, lat]),
                {
                    'taxon_id': str(p['taxon_id']),
                    'emb_year': int(p['embedding_year']),
                    'orig_year': int(p.get('year', p['embedding_year'])),
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
            # Get AlphaEarth mosaic for this year
            ae_img = get_alphaearth_mosaic(year)

            # Filter features for this year
            fc_year = fc.filter(ee.Filter.eq('emb_year', year))

            # Step 1: Sample AlphaEarth at 10m WITH geometry preservation
            # (needed for subsequent Hansen sampling)
            ae_sampled = ae_img.sampleRegions(
                collection=fc_year,
                scale=DEFAULT_SCALE,
                geometries=True,  # Keep geometry for Hansen reduceRegions
                tileScale=4
            )

            # Step 2: Add Hansen data using reduceRegions at 30m scale
            # This adds treecover2000, lossyear, gain to each feature
            combined_sampled = hansen_img.reduceRegions(
                collection=ae_sampled,
                reducer=ee.Reducer.first(),
                scale=HANSEN_SCALE
            )

            sampled_all = sampled_all.merge(combined_sampled)

        # Export to BigQuery (geometry will be dropped during export)
        task_desc = f'combined_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{chunk_idx:04d}'

        task = ee.batch.Export.table.toBigQuery(
            collection=sampled_all,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{table_name}',
            append=True,
            overwrite=False
        )
        task.start()
        task_ids.append(task.id)

        print(f"  Chunk {chunk_idx + 1}/{total_chunks}: {len(chunk)} pts, years {years}, task: {task_desc}")

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


def wait_for_tasks(task_ids: List[str], poll_interval: int = 30) -> Dict:
    """
    Wait for GEE tasks to complete with progress monitoring.
    """
    pending = set(task_ids)
    completed = []
    failed = []

    print(f"\nMonitoring {len(task_ids)} tasks (poll every {poll_interval}s)...")

    start_time = time.time()

    while pending:
        time.sleep(poll_interval)

        for task_id in list(pending):
            status = check_task_status(task_id)

            if status['state'] == 'COMPLETED':
                completed.append(task_id)
                pending.remove(task_id)
                elapsed = time.time() - start_time
                print(f"  Completed: {len(completed)}/{len(task_ids)} ({elapsed:.0f}s elapsed)")

            elif status['state'] == 'FAILED':
                error = status['error_message'] or 'Unknown error'
                failed.append((task_id, error))
                pending.remove(task_id)
                print(f"  FAILED: {error[:100]}")

        if pending:
            elapsed = time.time() - start_time
            print(f"  Pending: {len(pending)} tasks... ({elapsed:.0f}s elapsed)")

    total_time = time.time() - start_time
    print(f"\nCompleted in {total_time:.0f}s ({total_time/60:.1f} min)")

    return {
        'completed': completed,
        'failed': failed,
        'total_time_seconds': total_time
    }


# =============================================================================
# DATA LOADING
# =============================================================================

def load_phase1_sample(parquet_path: str, n_samples: int = 1000, random_state: int = 42) -> List[Dict]:
    """
    Load a random sample of Phase 1 data for testing.

    Args:
        parquet_path: Path to Phase 1 parquet file
        n_samples: Number of samples to select
        random_state: Random seed for reproducibility

    Returns:
        List of point dictionaries
    """
    print(f"Loading sample from: {parquet_path}")
    df = pd.read_parquet(parquet_path)

    # Sample
    if len(df) > n_samples:
        df_sample = df.sample(n=n_samples, random_state=random_state)
    else:
        df_sample = df

    print(f"  Total records: {len(df):,}")
    print(f"  Sample size: {len(df_sample):,}")
    print(f"  Species in sample: {df_sample['taxon_id'].nunique():,}")

    # Convert to list of dicts
    points = []
    for _, row in df_sample.iterrows():
        points.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['decimalLatitude'],
            'longitude': row['decimalLongitude'],
            'year': int(row['year']) if pd.notna(row['year']) else row['embedding_year'],
            'embedding_year': int(row['embedding_year'])
        })

    return points


def load_species_sample(parquet_path: str, taxon_ids: List[str], max_per_species: int = 100) -> List[Dict]:
    """
    Load occurrence points for specific species.

    Args:
        parquet_path: Path to parquet file
        taxon_ids: List of taxon IDs to load
        max_per_species: Maximum points per species

    Returns:
        List of point dictionaries
    """
    print(f"Loading species: {taxon_ids}")
    df = pd.read_parquet(parquet_path)

    # Filter to requested species
    df_species = df[df['taxon_id'].isin(taxon_ids)]

    # Sample within each species
    points = []
    for taxon_id in taxon_ids:
        df_tax = df_species[df_species['taxon_id'] == taxon_id]
        if len(df_tax) > max_per_species:
            df_tax = df_tax.sample(n=max_per_species, random_state=42)

        print(f"  {taxon_id}: {len(df_tax)} points")

        for _, row in df_tax.iterrows():
            points.append({
                'taxon_id': row['taxon_id'],
                'latitude': row['decimalLatitude'],
                'longitude': row['decimalLongitude'],
                'year': int(row['year']) if pd.notna(row['year']) else row['embedding_year'],
                'embedding_year': int(row['embedding_year'])
            })

    return points


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_test_batch(n_samples: int = 1000):
    """
    Run a test batch to validate AlphaEarth + Hansen parallel sampling.
    """
    print("=" * 80)
    print("GEE COMBINED SAMPLER TEST - AlphaEarth + Hansen")
    print("=" * 80)

    # Initialize GEE
    if not initialize_gee():
        return

    # Find Phase 1 file
    extractions_dir = Path(__file__).parent / 'alphaearth_extractions'
    phase1_files = list(extractions_dir.glob('alphaearth_phase1_*.parquet'))

    if not phase1_files:
        print("No Phase 1 parquet file found!")
        return

    # Use most recent
    phase1_path = sorted(phase1_files)[-1]
    print(f"\nUsing Phase 1 file: {phase1_path.name}")

    # Load sample
    points = load_phase1_sample(str(phase1_path), n_samples=n_samples)

    # Year distribution in sample
    year_counts = {}
    for p in points:
        y = p['embedding_year']
        year_counts[y] = year_counts.get(y, 0) + 1
    print(f"\nYear distribution: {dict(sorted(year_counts.items()))}")

    # Run sampling
    print(f"\nStarting combined sampling...")
    task_ids = sample_combined(points, batch_size=500, table_suffix='_test')

    if not task_ids:
        print("No tasks created!")
        return

    # Wait for completion
    results = wait_for_tasks(task_ids, poll_interval=15)

    # Summary
    print("\n" + "=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Completed: {len(results['completed'])}/{len(task_ids)}")
    print(f"Failed: {len(results['failed'])}/{len(task_ids)}")

    if results['failed']:
        print("\nFailed tasks:")
        for task_id, error in results['failed']:
            print(f"  - {task_id}: {error}")

    if results['completed']:
        print(f"\nData exported to: {PROJECT}.{BQ_DATASET}.{BQ_TABLE_COMBINED}_test")
        print("\nNext steps:")
        print("  1. Query BigQuery to verify data")
        print("  2. Check Hansen values (treecover2000, lossyear)")
        print("  3. Analyze forest coverage distribution")
        print("\nExample query:")
        print(f"""
SELECT
    taxon_id,
    COUNT(*) as n_points,
    AVG(treecover2000) as avg_treecover,
    SUM(CASE WHEN treecover2000 > 25 THEN 1 ELSE 0 END) as forested_points,
    SUM(CASE WHEN lossyear > 0 THEN 1 ELSE 0 END) as deforested_points
FROM `{PROJECT}.{BQ_DATASET}.{BQ_TABLE_COMBINED}_test`
GROUP BY taxon_id
ORDER BY n_points DESC
LIMIT 20;
""")

    return results


def run_full_phase1(batch_size: int = 2000):
    """
    Run full Phase 1 processing with AlphaEarth + Hansen.

    This processes all 16.5M Phase 1 points.
    """
    print("=" * 80)
    print("FULL PHASE 1 PROCESSING - AlphaEarth + Hansen")
    print("=" * 80)

    # Initialize GEE
    if not initialize_gee():
        return

    # Find Phase 1 file
    extractions_dir = Path(__file__).parent / 'alphaearth_extractions'
    phase1_files = list(extractions_dir.glob('alphaearth_phase1_*.parquet'))

    if not phase1_files:
        print("No Phase 1 parquet file found!")
        return

    phase1_path = sorted(phase1_files)[-1]
    print(f"\nLoading: {phase1_path.name}")

    # Load all data
    df = pd.read_parquet(phase1_path)
    print(f"  Records: {len(df):,}")
    print(f"  Species: {df['taxon_id'].nunique():,}")

    # Convert to points
    points = []
    for _, row in df.iterrows():
        points.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['decimalLatitude'],
            'longitude': row['decimalLongitude'],
            'year': int(row['year']) if pd.notna(row['year']) else row['embedding_year'],
            'embedding_year': int(row['embedding_year'])
        })

    # Estimate tasks
    n_tasks = (len(points) - 1) // batch_size + 1
    print(f"\nEstimated tasks: {n_tasks:,}")
    print(f"Batch size: {batch_size:,}")

    # Start sampling
    print("\nStarting full Phase 1 sampling...")
    task_ids = sample_combined(points, batch_size=batch_size)

    # Save task IDs for monitoring
    task_file = extractions_dir / f'phase1_tasks_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(task_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(phase1_path),
            'n_points': len(points),
            'n_tasks': len(task_ids),
            'batch_size': batch_size,
            'task_ids': task_ids
        }, f, indent=2)
    print(f"\nTask IDs saved to: {task_file}")

    # Monitor (can be interrupted and resumed)
    print("\nMonitoring tasks (Ctrl+C to stop monitoring)...")
    try:
        results = wait_for_tasks(task_ids, poll_interval=60)
    except KeyboardInterrupt:
        print("\nMonitoring interrupted. Tasks continue running in GEE.")
        print(f"Resume monitoring with task IDs from: {task_file}")
        return

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GEE Combined Sampler - AlphaEarth + Hansen')
    parser.add_argument('--test', type=int, default=1000,
                        help='Run test with N samples (default: 1000)')
    parser.add_argument('--full', action='store_true',
                        help='Run full Phase 1 processing')
    parser.add_argument('--batch-size', type=int, default=2000,
                        help='Batch size for processing (default: 2000)')

    args = parser.parse_args()

    if args.full:
        run_full_phase1(batch_size=args.batch_size)
    else:
        run_test_batch(n_samples=args.test)
