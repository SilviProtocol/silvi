#!/usr/bin/env python3
"""
FAST BioClim + Terrain Extraction from GEE

Extracts environmental variables for ALL unique occurrence locations
(9.4M unique locations from 96.5M total occurrences).

Variables: 19 BioClim + terrain + soil + water = 25 bands
"""

import ee
import time
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# Configuration
PROJECT = 'treekipedia-479918'
GCS_BUCKET = 'treekipedia-gee-exports'  # We'll use local sampling with batches instead
BATCH_SIZE = 2000  # Larger batches for efficiency
MAX_WORKERS = 20  # More parallel requests
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
# Use FULL occurrence file (96.5M occurrences, 9.4M unique locations)
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    """Load unique locations from FULL occurrence parquet (96.5M → 9.4M unique)."""
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()

    # Rename columns to standard format
    df = df.rename(columns={
        'decimalLatitude': 'latitude',
        'decimalLongitude': 'longitude'
    })

    # Get unique locations
    locations = df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total occurrences: {len(df):,}")
    print(f"  Unique locations: {len(locations):,}")

    return locations


def create_env_image():
    """Create composite image with all environmental variables."""

    # WorldClim BioClim (19 variables) - KEY TEMPERATURE DATA
    worldclim = ee.Image('WORLDCLIM/V1/BIO')

    # Terrain from SRTM
    srtm = ee.Image('USGS/SRTMGL1_003')
    terrain = ee.Terrain.products(srtm)

    # Topographic Diversity
    topo_diversity = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity')

    # Soil Texture
    soil = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')

    # Water occurrence
    water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')

    # Combine
    combined = (worldclim
        .addBands(terrain.select(['slope', 'aspect', 'hillshade']))
        .addBands(topo_diversity.rename('topo_diversity'))
        .addBands(soil.select('b0').rename('soil_texture_0cm'))
        .addBands(water.rename('water_occurrence'))
    )

    return combined


def sample_batch_fast(args):
    """Sample a batch of locations - designed for parallel execution."""
    batch_idx, locations_batch, env_image = args

    try:
        # Create FeatureCollection
        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point))

        fc = ee.FeatureCollection(features)

        # Sample
        sampled = env_image.sampleRegions(
            collection=fc,
            scale=1000,
            geometries=True
        )

        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, pd.DataFrame(), "no_results"

        # Parse
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
    print("FAST BIOCLIM + TERRAIN EXTRACTION")
    print(f"Using {MAX_WORKERS} parallel workers")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load locations
    locations = load_unique_locations()

    # Check for checkpoint
    checkpoint_file = OUTPUT_DIR / "bioclim_terrain_checkpoint.parquet"
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

    # Create env image
    print("\nCreating environmental composite...")
    env_image = create_env_image()
    bands = env_image.bandNames().getInfo()
    print(f"  Extracting {len(bands)} bands: bio01-bio19, slope, aspect, soil, water...")

    # Prepare batches
    n_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = []
    for i in range(n_batches):
        start = i * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(locations))
        batches.append((i, locations.iloc[start:end], env_image))

    print(f"\nProcessing {len(locations):,} locations in {n_batches} batches...")
    print(f"With {MAX_WORKERS} workers: ~{n_batches * 5 / MAX_WORKERS / 60:.1f} hours estimated")

    start_time = time.time()
    extracted = 0
    errors = 0

    # Process with ThreadPool
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_fast, batch): batch[0] for batch in batches}

        for i, future in enumerate(as_completed(futures)):
            batch_idx, result_df, status = future.result()

            if status == "success" and len(result_df) > 0:
                all_results.append(result_df)
                extracted += len(result_df)
            elif status != "success":
                errors += 1

            # Progress every 50 batches
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining = (len(locations) - extracted) / rate / 3600 if rate > 0 else 0

                print(f"  Progress: {i+1}/{n_batches} batches, "
                      f"{extracted:,} extracted, {errors} errors, "
                      f"~{remaining:.1f}h remaining")

            # Checkpoint every 200 batches
            if (i + 1) % 200 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint: {len(checkpoint_df):,} records")

    # Final save
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        output_file = OUTPUT_DIR / f"bioclim_terrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
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
        print(f"Columns: {list(final_df.columns)}")
    else:
        print("\n❌ No results")


if __name__ == "__main__":
    main()
