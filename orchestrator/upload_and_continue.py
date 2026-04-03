#!/usr/bin/env python3
"""
Upload Local Exports to BigQuery + Continue with Deduplicated GEE
==================================================================

This script:
1. Uploads the 1.25M rows from local v3 parquet files to BigQuery
2. Continues GEE processing with deduplication for remaining pixels

Usage:
    # Step 1: Upload existing data
    python3 upload_and_continue.py --upload

    # Step 2: Process remaining with deduplication (dry run first)
    python3 upload_and_continue.py --continue --dry-run

    # Step 3: Actually process
    python3 upload_and_continue.py --continue --year 2019

Author: Treekipedia Team
Created: January 2026
"""

import ee
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
import time
from typing import List, Dict, Set

# =============================================================================
# CONFIGURATION
# =============================================================================

# Use the billing-enabled project
PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_TABLE = 'alphaearth_embeddings_v4'  # New table with Hansen + SRTM

# GEE data sources
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'
SRTM_ASSET = 'USGS/SRTMGL1_003'

# Processing settings
BATCH_SIZE = 2000
COORD_DECIMALS = 4  # ~10m precision

# Paths
SCRIPT_DIR = Path(__file__).parent
EXPORTS_DIR = SCRIPT_DIR / 'bigquery_exports'
EXTRACTIONS_DIR = SCRIPT_DIR / 'alphaearth_extractions'


# =============================================================================
# STEP 1: UPLOAD LOCAL DATA TO BIGQUERY
# =============================================================================

def upload_local_to_bigquery():
    """Upload local v3 parquet files to BigQuery - fresh table."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    table_id = f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}'

    # Find v3 files
    v3_files = sorted(EXPORTS_DIR.glob('occ_embeddings_hansen_elev_v3_*.parquet'))

    if not v3_files:
        print("No v3 files found to upload!")
        return

    print(f"Found {len(v3_files)} v3 files to upload")
    print(f"Target: {table_id}")

    # Delete existing table if it exists
    try:
        client.delete_table(table_id)
        print("Deleted existing table")
    except Exception:
        pass

    # Upload each file
    total_uploaded = 0
    for i, f in enumerate(v3_files):
        print(f"\nUploading {f.name}...")
        df = pd.read_parquet(f)

        # Clean up columns
        if 'geo' in df.columns:
            df = df.drop(columns=['geo'])
        if 'system:index' in df.columns:
            df = df.drop(columns=['system:index'])
        if 'first' in df.columns:
            df = df.rename(columns={'first': 'elevation'})

        print(f"  Rows: {len(df):,}")

        # First file creates table, rest append
        if i == 0:
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                autodetect=True
            )
        else:
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )

        job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
        job.result()

        total_uploaded += len(df)
        print(f"  Uploaded! Total so far: {total_uploaded:,}")

    # Verify
    table = client.get_table(table_id)
    print(f"\nDone! Table now has {table.num_rows:,} rows")

    return total_uploaded


# =============================================================================
# STEP 2: GET ALREADY PROCESSED PIXELS FROM BIGQUERY
# =============================================================================

def get_processed_pixel_years() -> Set[str]:
    """Query BigQuery to get already-processed pixel-years."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    table_id = f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}'

    print(f"Querying processed pixels from {table_id}...")

    # Query unique lat/lon/year combinations
    query = f"""
    SELECT DISTINCT
        ROUND(latitude, {COORD_DECIMALS}) as lat_round,
        ROUND(longitude, {COORD_DECIMALS}) as lon_round,
        emb_year
    FROM `{table_id}`
    """

    try:
        df = client.query(query).to_dataframe()
        print(f"  Found {len(df):,} unique pixel-years already processed")

        # Create key set
        keys = set()
        for _, row in df.iterrows():
            key = f"{row['lat_round']}_{row['lon_round']}_{row['emb_year']}"
            keys.add(key)

        return keys
    except Exception as e:
        print(f"  Error querying BigQuery: {e}")
        print("  Falling back to local files...")
        return get_processed_from_local()


def get_processed_from_local() -> Set[str]:
    """Fallback: get processed pixels from local files."""
    keys = set()

    v3_files = list(EXPORTS_DIR.glob('occ_embeddings_hansen_elev_v3_*.parquet'))
    for f in v3_files:
        df = pd.read_parquet(f)
        df['lat_round'] = df['latitude'].round(COORD_DECIMALS)
        df['lon_round'] = df['longitude'].round(COORD_DECIMALS)

        for _, row in df.iterrows():
            key = f"{row['lat_round']}_{row['lon_round']}_{row['emb_year']}"
            keys.add(key)

    print(f"  Loaded {len(keys):,} processed pixel-years from local files")
    return keys


# =============================================================================
# STEP 3: LOAD AND DEDUPLICATE PHASE 1
# =============================================================================

def load_remaining_pixels(year: int = None) -> pd.DataFrame:
    """Load Phase 1 data, deduplicate, and exclude already-processed."""

    # Get processed pixels
    processed_keys = get_processed_pixel_years()

    # Load Phase 1
    phase1_files = list(EXTRACTIONS_DIR.glob('alphaearth_phase1_*.parquet'))
    if not phase1_files:
        raise FileNotFoundError("No Phase 1 file found!")

    phase1_path = sorted(phase1_files)[-1]
    print(f"\nLoading Phase 1: {phase1_path.name}")

    df = pd.read_parquet(phase1_path)
    print(f"  Total rows: {len(df):,}")

    if year:
        df = df[df['embedding_year'] == year]
        print(f"  Filtered to year {year}: {len(df):,}")

    # Round coordinates and create key
    df['lat_round'] = df['decimalLatitude'].round(COORD_DECIMALS)
    df['lon_round'] = df['decimalLongitude'].round(COORD_DECIMALS)
    df['pixel_year_key'] = (
        df['lat_round'].astype(str) + '_' +
        df['lon_round'].astype(str) + '_' +
        df['embedding_year'].astype(str)
    )

    # Deduplicate
    before = len(df)
    df_dedup = df.drop_duplicates(subset=['pixel_year_key'], keep='first')
    print(f"  Deduplicated: {before:,} -> {len(df_dedup):,}")

    # Exclude already processed
    remaining = df_dedup[~df_dedup['pixel_year_key'].isin(processed_keys)]
    print(f"  After excluding processed: {len(remaining):,}")

    return remaining


# =============================================================================
# STEP 4: GEE SAMPLING WITH DEDUPLICATION
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


def sample_with_gee(
    points_df: pd.DataFrame,
    dry_run: bool = False
) -> List[str]:
    """Sample AlphaEarth + Hansen + SRTM using GEE."""

    if len(points_df) == 0:
        print("No points to process!")
        return []

    # Convert to list of dicts
    points = []
    for _, row in points_df.iterrows():
        points.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['lat_round'],
            'longitude': row['lon_round'],
            'year': int(row.get('year', row['embedding_year'])),
            'embedding_year': int(row['embedding_year'])
        })

    n_tasks = (len(points) - 1) // BATCH_SIZE + 1
    cost_estimate = len(points) * 0.00024

    print(f"\n{'='*60}")
    print(f"GEE SAMPLING - DEDUPLICATED")
    print(f"{'='*60}")
    print(f"  Unique pixel-years: {len(points):,}")
    print(f"  Tasks: {n_tasks}")
    print(f"  Estimated cost: ${cost_estimate:.0f}")
    print(f"  Target: {PROJECT}.{BQ_DATASET}.{BQ_TABLE}")

    if dry_run:
        print("\n  [DRY RUN - no tasks submitted]")
        return []

    # Get static images
    hansen_img = ee.Image(HANSEN_ASSET)
    hansen_bands = hansen_img.select('treecover2000').addBands(
        hansen_img.select('lossyear').unmask(0)
    ).addBands(hansen_img.select('loss')).addBands(hansen_img.select('gain'))

    srtm_img = ee.Image(SRTM_ASSET).select('elevation')

    task_ids = []

    for chunk_idx, chunk_start in enumerate(range(0, len(points), BATCH_SIZE)):
        chunk = points[chunk_start:chunk_start + BATCH_SIZE]

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

        # Group by year
        years = sorted({p['embedding_year'] for p in chunk})
        sampled_all = ee.FeatureCollection([])

        for year in years:
            # AlphaEarth mosaic for this year
            ae_img = ee.ImageCollection(AE_COLLECTION).filterDate(
                f'{year}-01-01', f'{year}-12-31'
            ).mosaic()

            fc_year = fc.filter(ee.Filter.eq('emb_year', year))

            # Sample AlphaEarth (keep geometry for BigQuery geo column)
            ae_sampled = ae_img.sampleRegions(
                collection=fc_year,
                scale=10,
                geometries=True,
                tileScale=4
            )

            # Add Hansen
            with_hansen = hansen_bands.reduceRegions(
                collection=ae_sampled,
                reducer=ee.Reducer.first(),
                scale=30
            )

            # Add SRTM
            with_all = srtm_img.reduceRegions(
                collection=with_hansen,
                reducer=ee.Reducer.first(),
                scale=30
            )

            # Just merge with_all directly - GEE export will handle properties
            sampled_all = sampled_all.merge(with_all)

        # Export
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
            print(f"  Task {chunk_idx + 1}/{n_tasks}: {len(chunk)} pts, years {years}")

    print(f"\n  Submitted {len(task_ids)} tasks")
    return task_ids


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Upload and Continue GEE Processing')
    parser.add_argument('--upload', action='store_true', help='Upload local v3 files to BigQuery')
    parser.add_argument('--continue', dest='continue_processing', action='store_true',
                        help='Continue GEE processing with deduplication')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--year', type=int, help='Process specific year')
    parser.add_argument('--limit', type=int, help='Limit points for testing')

    args = parser.parse_args()

    print("=" * 70)
    print("UPLOAD AND CONTINUE - DEDUPLICATED GEE PIPELINE")
    print("=" * 70)
    print(f"Project: {PROJECT}")
    print(f"Dataset: {BQ_DATASET}")
    print(f"Table: {BQ_TABLE}")

    if args.upload:
        print("\n" + "=" * 70)
        print("STEP 1: UPLOADING LOCAL DATA TO BIGQUERY")
        print("=" * 70)
        upload_local_to_bigquery()

    if args.continue_processing:
        print("\n" + "=" * 70)
        print("STEP 2: CONTINUE GEE PROCESSING WITH DEDUPLICATION")
        print("=" * 70)

        if not initialize_gee():
            return

        # Load remaining pixels
        remaining_df = load_remaining_pixels(year=args.year)

        if len(remaining_df) == 0:
            print("\nAll pixels already processed!")
            return

        # Show by year
        print("\nRemaining by year:")
        for year in sorted(remaining_df['embedding_year'].unique()):
            count = len(remaining_df[remaining_df['embedding_year'] == year])
            print(f"  {year}: {count:,}")

        if args.limit:
            remaining_df = remaining_df.head(args.limit)
            print(f"\nLimited to {args.limit} pixels for testing")

        # Process
        task_ids = sample_with_gee(remaining_df, dry_run=args.dry_run)

        if task_ids:
            print(f"\nMonitor tasks at: https://code.earthengine.google.com/tasks")

    if not args.upload and not args.continue_processing:
        parser.print_help()
        print("\n\nExample usage:")
        print("  1. Upload existing data:   python3 upload_and_continue.py --upload")
        print("  2. Check what's remaining: python3 upload_and_continue.py --continue --dry-run")
        print("  3. Process year 2019:      python3 upload_and_continue.py --continue --year 2019")
        print("  4. Process all remaining:  python3 upload_and_continue.py --continue")


if __name__ == '__main__':
    main()
