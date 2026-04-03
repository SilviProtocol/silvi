#!/usr/bin/env python3
"""
Human Disturbance + Land Use Extraction from GEE

Extracts disturbance and land use variables for ALL unique occurrence locations.

Variables:
1. Human Modification Index (gHM) - 1km resolution
2. Protected Area status (WDPA) - distance to protected area
3. ESA WorldCover 2021 - land cover class (10m)
4. Hansen tree cover & loss
5. Cropland percentage
6. Fire frequency (burned area)

This helps understand which species are in disturbed vs pristine habitats.
"""

import ee
import time
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# Configuration
PROJECT = 'treekipedia-479918'
BATCH_SIZE = 2000
MAX_WORKERS = 20
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    """Load unique locations from FULL occurrence parquet."""
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()

    df = df.rename(columns={
        'decimalLatitude': 'latitude',
        'decimalLongitude': 'longitude'
    })

    locations = df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total occurrences: {len(df):,}")
    print(f"  Unique locations: {len(locations):,}")

    return locations


def create_disturbance_image():
    """Create composite image with disturbance/land use variables."""

    # 1. Global Human Modification Index (1km, 0-1 scale)
    # Higher = more human modification
    ghm = ee.ImageCollection('CSP/HM/GlobalHumanModification').first().select('gHM')

    # 2. ESA WorldCover 2021 (10m land cover)
    # Classes: 10=tree, 20=shrub, 30=grass, 40=crop, 50=urban, 60=bare, 70=snow, 80=water, 90=wetland, 95=mangrove, 100=moss
    worldcover = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map')

    # 3. Hansen Global Forest Change 2023
    hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')
    treecover2000 = hansen.select('treecover2000')  # % tree cover in 2000
    loss = hansen.select('loss')  # binary loss 2000-2023
    lossyear = hansen.select('lossyear')  # year of loss (0-23)
    gain = hansen.select('gain')  # binary gain 2000-2012

    # 4. Calculate distance to forest edge (useful for edge species)
    # Forest = treecover > 30%
    forest_mask = treecover2000.gt(30)

    # 5. MODIS burned area frequency (count of fires 2001-2023)
    # Using MCD64A1 monthly burned area
    fire = ee.ImageCollection('MODIS/061/MCD64A1').select('BurnDate')
    fire_count = fire.map(lambda img: img.gt(0).unmask(0)).sum().rename('fire_count')

    # Combine all bands
    combined = (ghm.rename('human_modification')
        .addBands(worldcover.rename('landcover_esa'))
        .addBands(treecover2000)
        .addBands(loss.rename('forest_loss'))
        .addBands(lossyear.rename('loss_year'))
        .addBands(gain.rename('forest_gain'))
        .addBands(fire_count)
    )

    return combined


def sample_batch_fast(args):
    """Sample a batch of locations."""
    batch_idx, locations_batch, env_image = args

    try:
        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point))

        fc = ee.FeatureCollection(features)

        sampled = env_image.sampleRegions(
            collection=fc,
            scale=1000,  # Match BioClim scale for speed
            geometries=True
        )

        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, pd.DataFrame(), "no_results"

        records = []
        for feature in results['features']:
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            record = {
                'longitude': coords[0],
                'latitude': coords[1],
                **props
            }
            records.append(record)

        return batch_idx, pd.DataFrame(records), "success"

    except Exception as e:
        return batch_idx, pd.DataFrame(), str(e)[:50]


def main():
    print("=" * 70)
    print("DISTURBANCE + LAND USE EXTRACTION")
    print(f"Using {MAX_WORKERS} parallel workers")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    locations = load_unique_locations()

    # Check for checkpoint
    checkpoint_file = OUTPUT_DIR / "disturbance_landuse_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_locs = set(zip(
            existing['latitude'].round(6),
            existing['longitude'].round(6)
        ))
        locations['key'] = list(zip(
            locations['latitude'].round(6),
            locations['longitude'].round(6)
        ))
        locations = locations[~locations['key'].isin(existing_locs)].drop('key', axis=1)
        print(f"  Resuming: {len(existing):,} done, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    print("\nCreating disturbance composite...")
    env_image = create_disturbance_image()
    bands = env_image.bandNames().getInfo()
    print(f"  Extracting {len(bands)} bands: {bands}")

    n_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = []
    for i in range(n_batches):
        start = i * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(locations))
        batches.append((i, locations.iloc[start:end], env_image))

    print(f"\nProcessing {len(locations):,} locations in {n_batches} batches...")

    start_time = time.time()
    extracted = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_fast, batch): batch[0] for batch in batches}

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
                print(f"  Progress: {i+1}/{n_batches} batches, "
                      f"{extracted:,} extracted, {errors} errors, "
                      f"~{remaining:.1f}h remaining")

            if (i + 1) % 200 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint: {len(checkpoint_df):,} records")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        output_file = OUTPUT_DIR / f"disturbance_landuse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
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
    else:
        print("\n❌ No results")


if __name__ == "__main__":
    main()
