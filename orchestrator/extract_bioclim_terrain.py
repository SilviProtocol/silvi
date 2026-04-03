#!/usr/bin/env python3
"""
BioClim + Terrain Extraction from GEE

Extracts environmental variables at all unique species occurrence locations.
Can run for several hours for ~3M points.

Variables extracted:
1. WorldClim BioClim (19 variables) - Temperature & Precipitation
   - bio01: Annual Mean Temperature (°C × 10)
   - bio05: Max Temp of Warmest Month (heat stress limit)
   - bio06: Min Temp of Coldest Month (cold tolerance limit)
   - bio12: Annual Precipitation
   - ... etc
2. Terrain derivatives (slope, aspect, hillshade) from SRTM
3. Soil texture classes (USDA classification)
4. Water occurrence (JRC Global Surface Water)
5. Topographic diversity index

Output: Parquet file with environmental data per location
"""

import ee
import time
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
import numpy as np
import sys

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# Configuration
PROJECT = 'treekipedia-479918'
BATCH_SIZE = 5000  # Points per GEE request (balance between speed and quota)
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"

# Initialize Earth Engine
print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    """Load unique locations from v4 parquet."""
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()

    # Get unique locations
    locations = df[['latitude', 'longitude']].drop_duplicates()
    print(f"  Total rows: {len(df):,}")
    print(f"  Unique locations: {len(locations):,}")

    return locations


def create_env_image():
    """Create composite image with all environmental variables."""

    # 1. WorldClim BioClim (19 variables)
    # bio01: Annual Mean Temperature (°C × 10)
    # bio05: Max Temp of Warmest Month
    # bio06: Min Temp of Coldest Month
    # bio12: Annual Precipitation (mm)
    # ... etc
    worldclim = ee.Image('WORLDCLIM/V1/BIO')

    # 2. Terrain from SRTM
    srtm = ee.Image('USGS/SRTMGL1_003')
    terrain = ee.Terrain.products(srtm)  # slope, aspect, hillshade

    # 3. Topographic Diversity Index
    topo_diversity = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity')

    # 4. Soil Texture (USDA classification)
    soil = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')

    # 5. Global Surface Water - occurrence
    water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')

    # 6. Aridity Index
    aridity = ee.Image('CSP/ERGo/1_0/Global/ALOS_mTPI')  # Multi-scale TPI

    # Combine all bands
    combined = (worldclim
        .addBands(terrain.select(['slope', 'aspect', 'hillshade']))
        .addBands(topo_diversity.rename('topo_diversity'))
        .addBands(soil.select('b0').rename('soil_texture_0cm'))
        .addBands(soil.select('b10').rename('soil_texture_10cm'))
        .addBands(soil.select('b30').rename('soil_texture_30cm'))
        .addBands(water.rename('water_occurrence'))
        .addBands(aridity.rename('mtpi'))
    )

    return combined


def sample_batch(env_image, locations_batch, batch_num, total_batches):
    """Sample environmental variables for a batch of locations."""

    # Create FeatureCollection from locations
    features = []
    for idx, row in locations_batch.iterrows():
        point = ee.Geometry.Point([row['longitude'], row['latitude']])
        features.append(ee.Feature(point, {'idx': int(idx)}))

    fc = ee.FeatureCollection(features)

    # Sample the image at all points
    sampled = env_image.sampleRegions(
        collection=fc,
        scale=1000,  # 1km resolution for climate data
        geometries=True
    )

    # Get results
    results = sampled.getInfo()

    if not results or 'features' not in results:
        print(f"  ⚠️ Batch {batch_num}/{total_batches}: No results")
        return pd.DataFrame()

    # Parse results
    records = []
    for feature in results['features']:
        props = feature['properties']
        coords = feature['geometry']['coordinates']

        record = {
            'longitude': coords[0],
            'latitude': coords[1],
            **{k: v for k, v in props.items() if k != 'idx'}
        }
        records.append(record)

    return pd.DataFrame(records)


def main():
    print("=" * 70)
    print("BIOCLIM + TERRAIN EXTRACTION FROM GEE")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load locations
    locations = load_unique_locations()

    # Check for existing progress
    checkpoint_file = OUTPUT_DIR / "env_extraction_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_locs = set(zip(existing['latitude'], existing['longitude']))
        locations = locations[~locations.apply(
            lambda r: (r['latitude'], r['longitude']) in existing_locs, axis=1
        )]
        print(f"  Resuming: {len(existing):,} already extracted, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    # Create environment image
    print("\nCreating environmental composite image...")
    env_image = create_env_image()
    band_names = env_image.bandNames().getInfo()
    print(f"  Bands to extract: {len(band_names)}")
    print(f"  Including: bio01-bio19 (climate), slope, aspect, soil, water...")

    # Process in batches
    total_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nProcessing {len(locations):,} locations in {total_batches} batches...")
    print(f"Estimated time: {total_batches * 15 / 60:.1f} hours (at ~15s per batch)")

    start_time = time.time()
    extracted = 0
    errors = 0

    for batch_num in range(total_batches):
        batch_start = batch_num * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, len(locations))
        batch = locations.iloc[batch_start:batch_end]

        try:
            batch_start_time = time.time()
            results_df = sample_batch(env_image, batch, batch_num + 1, total_batches)
            batch_time = time.time() - batch_start_time

            if len(results_df) > 0:
                all_results.append(results_df)
                extracted += len(results_df)

            # Progress report every 10 batches
            if (batch_num + 1) % 10 == 0 or batch_num == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining = (len(locations) - extracted) / rate if rate > 0 else 0

                print(f"  Batch {batch_num + 1}/{total_batches}: "
                      f"{extracted:,} extracted, {batch_time:.1f}s, "
                      f"~{remaining/3600:.1f}h remaining")

            # Save checkpoint every 50 batches
            if (batch_num + 1) % 50 == 0:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint saved: {len(checkpoint_df):,} records")

            # Small delay to avoid quota issues
            time.sleep(0.5)

        except Exception as e:
            errors += 1
            print(f"  ❌ Batch {batch_num + 1} error: {str(e)[:80]}")
            if errors > 10:
                print("  Too many errors, saving progress and stopping...")
                break
            time.sleep(5)  # Longer delay after error

    # Final save
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        output_file = OUTPUT_DIR / f"env_variables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        final_df.to_parquet(output_file)

        # Also save as checkpoint
        final_df.to_parquet(checkpoint_file)

        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"Total locations extracted: {len(final_df):,}")
        print(f"Variables per location: {len(final_df.columns) - 2}")  # minus lat/lon
        print(f"Total time: {elapsed/3600:.2f} hours")
        print(f"Output: {output_file}")
        print(f"Columns: {list(final_df.columns)}")
    else:
        print("\n❌ No results extracted")


if __name__ == "__main__":
    main()
