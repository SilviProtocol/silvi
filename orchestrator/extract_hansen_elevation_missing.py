#!/usr/bin/env python3
"""
Extract Hansen Forest + Elevation for Missing Locations

AlphaEarth v4 has 3.4M locations with forest/elevation data.
We have 9.4M total unique locations.
This extracts Hansen forest + elevation at 30m native resolution
for the ~6M locations NOT in AlphaEarth.

Variables extracted at 30m native:
- elevation (SRTM)
- slope, aspect (terrain derivatives)
- treecover2000 (Hansen baseline)
- loss, gain, lossyear (Hansen change)
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
BATCH_SIZE = 500   # Smaller batches for 30m resolution
MAX_WORKERS = 15
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"
ALPHAEARTH_PATH = Path(__file__).parent / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_missing_locations():
    """Load locations NOT already in AlphaEarth v4."""
    print(f"\nLoading all locations from {PARQUET_PATH}...")
    all_df = pq.read_table(PARQUET_PATH).to_pandas()
    all_df = all_df.rename(columns={'decimalLatitude': 'latitude', 'decimalLongitude': 'longitude'})
    all_locs = all_df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total unique locations: {len(all_locs):,}")

    print(f"\nLoading AlphaEarth v4 locations...")
    ae_df = pq.read_table(ALPHAEARTH_PATH).to_pandas()
    ae_locs = set(zip(ae_df['latitude'].round(6), ae_df['longitude'].round(6)))
    print(f"  AlphaEarth locations: {len(ae_locs):,}")

    # Find missing
    all_locs['key'] = list(zip(all_locs['latitude'].round(6), all_locs['longitude'].round(6)))
    missing = all_locs[~all_locs['key'].isin(ae_locs)].drop('key', axis=1).reset_index(drop=True)
    print(f"  Missing locations to extract: {len(missing):,}")

    return missing


def create_hansen_elevation_image():
    """Create composite with Hansen forest + SRTM elevation at 30m."""
    # SRTM elevation and derivatives (30m native)
    srtm = ee.Image('USGS/SRTMGL1_003')
    terrain = ee.Terrain.products(srtm)

    # Hansen Global Forest Change (30m native)
    hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')

    combined = (terrain.select(['elevation', 'slope', 'aspect'])
        .addBands(hansen.select('treecover2000'))
        .addBands(hansen.select('loss').rename('forest_loss'))
        .addBands(hansen.select('gain').rename('forest_gain'))
        .addBands(hansen.select('lossyear').rename('loss_year'))
    )

    return combined


def sample_batch(args):
    """Sample a batch at 30m native resolution."""
    batch_idx, locations_batch, env_image = args

    try:
        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point, {
                'orig_lat': float(row['latitude']),
                'orig_lon': float(row['longitude'])
            }))

        fc = ee.FeatureCollection(features)

        # Sample at 30m NATIVE resolution
        sampled = env_image.sampleRegions(
            collection=fc,
            scale=30,
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
                **props
            }
            records.append(record)

        return batch_idx, pd.DataFrame(records), "success"

    except Exception as e:
        return batch_idx, pd.DataFrame(), str(e)[:100]


def main():
    print("=" * 70)
    print("HANSEN FOREST + ELEVATION EXTRACTION (30m native)")
    print("For locations NOT in AlphaEarth v4")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    locations = load_missing_locations()

    # Check for checkpoint
    checkpoint_file = OUTPUT_DIR / "hansen_elevation_missing_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_locs = set(zip(existing['latitude'].round(8), existing['longitude'].round(8)))
        locations['key'] = list(zip(locations['latitude'].round(8), locations['longitude'].round(8)))
        locations = locations[~locations['key'].isin(existing_locs)].drop('key', axis=1)
        print(f"  Resuming: {len(existing):,} done, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    print("\nCreating Hansen + Elevation composite (30m)...")
    env_image = create_hansen_elevation_image()
    bands = env_image.bandNames().getInfo()
    print(f"  Extracting {len(bands)} bands: {bands}")

    n_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = [(i, locations.iloc[i*BATCH_SIZE:(i+1)*BATCH_SIZE], env_image)
               for i in range(n_batches)]

    print(f"\nProcessing {len(locations):,} locations in {n_batches} batches at 30m...")

    start_time = time.time()
    extracted = errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch, b): b[0] for b in batches}

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
                print(f"  Progress: {i+1}/{n_batches}, {extracted:,} extracted, "
                      f"{errors} errors, ~{remaining:.1f}h remaining")

            if (i + 1) % 200 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint: {len(checkpoint_df):,} records")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"hansen_elevation_missing_{timestamp}.parquet"
        final_df.to_parquet(output_file)
        final_df.to_parquet(checkpoint_file)

        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"Locations extracted: {len(final_df):,}")
        print(f"Variables: {len(final_df.columns) - 2}")
        print(f"Time: {elapsed/3600:.2f} hours")
        print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
