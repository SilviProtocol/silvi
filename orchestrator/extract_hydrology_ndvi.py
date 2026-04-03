#!/usr/bin/env python3
"""
Hydrology + NDVI Extraction from GEE

Variables:
1. JRC Water - seasonality, recurrence, occurrence
2. MODIS NDVI - mean annual vegetation greenness
3. Soil Moisture (if available)

Critical for identifying riparian species and vegetation patterns.
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
BATCH_SIZE = 2000
MAX_WORKERS = 20
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()
    df = df.rename(columns={'decimalLatitude': 'latitude', 'decimalLongitude': 'longitude'})
    locations = df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total occurrences: {len(df):,}")
    print(f"  Unique locations: {len(locations):,}")
    return locations


def create_hydro_ndvi_image():
    """Create composite with hydrology and NDVI."""

    # JRC Global Surface Water (all bands)
    jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
    water_occurrence = jrc.select('occurrence')  # % time water present
    water_seasonality = jrc.select('seasonality')  # months with water
    water_recurrence = jrc.select('recurrence')  # inter-annual recurrence
    water_transition = jrc.select('transition')  # change class

    # MODIS NDVI - compute mean over recent years (2020-2023)
    ndvi_col = ee.ImageCollection('MODIS/061/MOD13A2').filterDate('2020-01-01', '2023-12-31')
    ndvi_mean = ndvi_col.select('NDVI').mean().multiply(0.0001).rename('ndvi_mean')  # Scale factor
    ndvi_std = ndvi_col.select('NDVI').reduce(ee.Reducer.stdDev()).multiply(0.0001).rename('ndvi_std')

    # EVI for comparison
    evi_mean = ndvi_col.select('EVI').mean().multiply(0.0001).rename('evi_mean')

    combined = (water_occurrence.rename('water_occurrence')
        .addBands(water_seasonality.rename('water_seasonality'))
        .addBands(water_recurrence.rename('water_recurrence'))
        .addBands(water_transition.rename('water_transition'))
        .addBands(ndvi_mean)
        .addBands(ndvi_std)
        .addBands(evi_mean)
    )

    return combined


def sample_batch_fast(args):
    batch_idx, locations_batch, env_image = args
    try:
        features = [ee.Feature(ee.Geometry.Point([float(row['longitude']), float(row['latitude'])]))
                    for _, row in locations_batch.iterrows()]
        fc = ee.FeatureCollection(features)

        sampled = env_image.sampleRegions(collection=fc, scale=1000, geometries=True)
        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, pd.DataFrame(), "no_results"

        records = [{'longitude': f['geometry']['coordinates'][0],
                    'latitude': f['geometry']['coordinates'][1],
                    **f['properties']} for f in results['features']]
        return batch_idx, pd.DataFrame(records), "success"
    except Exception as e:
        return batch_idx, pd.DataFrame(), str(e)[:50]


def main():
    print("=" * 70)
    print("HYDROLOGY + NDVI EXTRACTION")
    print(f"Using {MAX_WORKERS} parallel workers")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)
    locations = load_unique_locations()

    checkpoint_file = OUTPUT_DIR / "hydrology_ndvi_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_locs = set(zip(existing['latitude'].round(6), existing['longitude'].round(6)))
        locations['key'] = list(zip(locations['latitude'].round(6), locations['longitude'].round(6)))
        locations = locations[~locations['key'].isin(existing_locs)].drop('key', axis=1)
        print(f"  Resuming: {len(existing):,} done, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    print("\nCreating hydrology + NDVI composite...")
    env_image = create_hydro_ndvi_image()
    bands = env_image.bandNames().getInfo()
    print(f"  Extracting {len(bands)} bands: {bands}")

    n_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = [(i, locations.iloc[i*BATCH_SIZE:min((i+1)*BATCH_SIZE, len(locations))], env_image)
               for i in range(n_batches)]

    print(f"\nProcessing {len(locations):,} locations in {n_batches} batches...")

    start_time = time.time()
    extracted = errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_fast, b): b[0] for b in batches}
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
                print(f"  Progress: {i+1}/{n_batches}, {extracted:,} extracted, {errors} errors, ~{remaining:.1f}h remaining")

            if (i + 1) % 200 == 0 and all_results:
                pd.concat(all_results, ignore_index=True).to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint saved")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        output_file = OUTPUT_DIR / f"hydrology_ndvi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        final_df.to_parquet(output_file)
        final_df.to_parquet(checkpoint_file)
        print(f"\n✅ COMPLETE: {len(final_df):,} locations, {len(final_df.columns)-2} variables")
        print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
