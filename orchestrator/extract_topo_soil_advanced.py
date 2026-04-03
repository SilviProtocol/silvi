#!/usr/bin/env python3
"""
Advanced Topography + Soil Extraction from GEE

Variables:
1. TPI - Topographic Position Index (ridges vs valleys)
2. Multi-scale TPI (ALOS)
3. Soil clay/sand/silt percentages (OpenLandMap)
4. Soil depth / bulk density
5. Landforms classification

These are the remaining critical gaps from MASTER_PREDICTION_ARCHITECTURE_2.md
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


def create_topo_soil_image():
    """Create composite with advanced topo/soil variables."""

    # 1. Multi-scale TPI (ALOS) - Topographic Position Index
    # Positive = ridges/hilltops, Negative = valleys/depressions
    mtpi = ee.Image('CSP/ERGo/1_0/Global/ALOS_mTPI').rename('mtpi')

    # 2. Landforms (derived from TPI)
    landforms = ee.Image('CSP/ERGo/1_0/Global/ALOS_landforms').rename('landforms')

    # 3. Topographic Diversity (local variance in elevation)
    topo_diversity = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').rename('topo_diversity')

    # 4. OpenLandMap Soil Properties (250m)
    # Clay content at 0cm depth
    clay = ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('clay_0cm')

    # Sand content at 0cm depth
    sand = ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('sand_0cm')

    # Bulk density at 0cm
    bulk_density = ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('bulk_density_0cm')

    # Soil organic carbon at 0cm
    soc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('organic_carbon_0cm')

    # Water content at field capacity (0cm)
    water_capacity = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01').select('b0').rename('water_capacity_0cm')

    # Combine all
    combined = (mtpi
        .addBands(landforms)
        .addBands(topo_diversity)
        .addBands(clay)
        .addBands(sand)
        .addBands(bulk_density)
        .addBands(soc)
        .addBands(water_capacity)
    )

    return combined


def sample_batch_fast(args):
    batch_idx, locations_batch, env_image = args
    try:
        features = [ee.Feature(ee.Geometry.Point([float(row['longitude']), float(row['latitude'])]))
                    for _, row in locations_batch.iterrows()]
        fc = ee.FeatureCollection(features)

        sampled = env_image.sampleRegions(collection=fc, scale=250, geometries=True)
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
    print("ADVANCED TOPOGRAPHY + SOIL EXTRACTION")
    print(f"Using {MAX_WORKERS} parallel workers")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)
    locations = load_unique_locations()

    checkpoint_file = OUTPUT_DIR / "topo_soil_advanced_checkpoint.parquet"
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

    print("\nCreating advanced topo+soil composite...")
    env_image = create_topo_soil_image()
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
        output_file = OUTPUT_DIR / f"topo_soil_advanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        final_df.to_parquet(output_file)
        final_df.to_parquet(checkpoint_file)
        print(f"\n✅ COMPLETE: {len(final_df):,} locations, {len(final_df.columns)-2} variables")
        print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
