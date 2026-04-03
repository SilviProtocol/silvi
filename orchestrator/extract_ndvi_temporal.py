#!/usr/bin/env python3
"""
Temporal NDVI Extraction - Matched to Occurrence Year

For AlphaEarth v4 records that have occurrence years (2017-2024),
extract NDVI/EVI for the specific year of observation.

This provides year-matched vegetation indices rather than
multi-year averages, which is more ecologically meaningful.

Variables extracted at 250m (MODIS native):
- ndvi_year: Mean NDVI for occurrence year
- ndvi_year_std: Std dev NDVI for occurrence year
- evi_year: Mean EVI for occurrence year
- ndvi_max_year: Max NDVI for occurrence year (peak greenness)
"""

import ee
import time
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

PROJECT = 'treekipedia-479918'
BATCH_SIZE = 500
MAX_WORKERS = 12
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
ALPHAEARTH_PATH = Path(__file__).parent / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_locations_with_years():
    """Load AlphaEarth locations with their occurrence years."""
    print(f"\nLoading AlphaEarth v4 with years...")
    df = pq.read_table(ALPHAEARTH_PATH).to_pandas()

    # Keep only what we need
    locations = df[['latitude', 'longitude', 'orig_year']].copy()
    locations = locations.rename(columns={'orig_year': 'year'})

    # Remove duplicates (same location + year)
    locations = locations.drop_duplicates().reset_index(drop=True)

    print(f"  Total location-year combinations: {len(locations):,}")
    print(f"  Year range: {locations['year'].min()} - {locations['year'].max()}")

    return locations


def get_ndvi_for_year(year):
    """Get MODIS NDVI/EVI composite for a specific year."""
    start_date = f'{int(year)}-01-01'
    end_date = f'{int(year)}-12-31'

    ndvi_col = ee.ImageCollection('MODIS/061/MOD13A2').filterDate(start_date, end_date)

    # Compute statistics for the year
    ndvi_mean = ndvi_col.select('NDVI').mean().multiply(0.0001).rename('ndvi_year')
    ndvi_std = ndvi_col.select('NDVI').reduce(ee.Reducer.stdDev()).multiply(0.0001).rename('ndvi_year_std')
    ndvi_max = ndvi_col.select('NDVI').max().multiply(0.0001).rename('ndvi_max_year')
    evi_mean = ndvi_col.select('EVI').mean().multiply(0.0001).rename('evi_year')

    return ndvi_mean.addBands(ndvi_std).addBands(ndvi_max).addBands(evi_mean)


def sample_batch_by_year(args):
    """Sample a batch for a specific year at 250m native resolution."""
    batch_idx, locations_batch, year = args

    try:
        # Get NDVI image for this year
        ndvi_image = get_ndvi_for_year(year)

        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point, {
                'orig_lat': float(row['latitude']),
                'orig_lon': float(row['longitude']),
                'year': int(row['year'])
            }))

        fc = ee.FeatureCollection(features)

        # Sample at 250m NATIVE resolution (MODIS)
        sampled = ndvi_image.sampleRegions(
            collection=fc,
            scale=250,
            geometries=False
        )

        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, pd.DataFrame(), "no_results"

        records = []
        for feature in results['features']:
            props = feature['properties']
            record = {
                'latitude': props.pop('orig_lat'),
                'longitude': props.pop('orig_lon'),
                'year': props.pop('year'),
                **props
            }
            records.append(record)

        return batch_idx, pd.DataFrame(records), "success"

    except Exception as e:
        return batch_idx, pd.DataFrame(), str(e)[:100]


def main():
    print("=" * 70)
    print("TEMPORAL NDVI EXTRACTION (250m native)")
    print("Matched to occurrence year")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    locations = load_locations_with_years()

    # Check for checkpoint
    checkpoint_file = OUTPUT_DIR / "ndvi_temporal_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_keys = set(zip(
            existing['latitude'].round(8),
            existing['longitude'].round(8),
            existing['year']
        ))
        locations['key'] = list(zip(
            locations['latitude'].round(8),
            locations['longitude'].round(8),
            locations['year']
        ))
        locations = locations[~locations['key'].isin(existing_keys)].drop('key', axis=1)
        print(f"  Resuming: {len(existing):,} done, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    # Group by year for efficient processing
    year_groups = locations.groupby('year')
    print(f"\nProcessing {len(locations):,} location-year combinations...")
    print(f"Years to process: {sorted(locations['year'].unique())}")

    # Create batches grouped by year
    batches = []
    batch_idx = 0
    for year, group in year_groups:
        n_year_batches = (len(group) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(n_year_batches):
            batch_data = group.iloc[i*BATCH_SIZE:(i+1)*BATCH_SIZE]
            batches.append((batch_idx, batch_data, year))
            batch_idx += 1

    print(f"Total batches: {len(batches)}")

    start_time = time.time()
    extracted = errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_by_year, b): b[0] for b in batches}

        for i, future in enumerate(as_completed(futures)):
            batch_idx, result_df, status = future.result()

            if status == "success" and len(result_df) > 0:
                all_results.append(result_df)
                extracted += len(result_df)
            elif status != "success":
                errors += 1

            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining = (len(locations) - extracted) / rate / 3600 if rate > 0 else 0
                print(f"  Progress: {i+1}/{len(batches)}, {extracted:,} extracted, "
                      f"{errors} errors, ~{remaining:.1f}h remaining")

            if (i + 1) % 200 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint: {len(checkpoint_df):,} records")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"ndvi_temporal_{timestamp}.parquet"
        final_df.to_parquet(output_file)
        final_df.to_parquet(checkpoint_file)

        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"Location-years extracted: {len(final_df):,}")
        print(f"Variables: {len(final_df.columns) - 3}")  # minus lat, lon, year
        print(f"Time: {elapsed/3600:.2f} hours")
        print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
