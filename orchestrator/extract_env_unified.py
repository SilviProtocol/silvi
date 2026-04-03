#!/usr/bin/env python3
"""
Unified Environmental Variable Extraction - Multi-Resolution

Extracts ALL environmental variables in a single pass per location,
preserving original coordinates and using appropriate resolutions.

Strategy:
- Climate (WorldClim): 1km native - sample at 1km
- Terrain (SRTM): 30m native - sample at 100m (balance speed/detail)
- Soil (OpenLandMap): 250m native - sample at 250m
- Water/Forest (JRC/Hansen): 30m native - sample at 100m
- Land cover (ESA): 10m native - sample at 100m

Output: Single parquet with all 47 variables per location
"""

import ee
import time
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

PROJECT = 'treekipedia-479918'
BATCH_SIZE = 1000  # Smaller batches for more variables
MAX_WORKERS = 15   # Slightly fewer to reduce quota pressure
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    """Load unique locations preserving original precision."""
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()
    df = df.rename(columns={'decimalLatitude': 'latitude', 'decimalLongitude': 'longitude'})
    locations = df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total occurrences: {len(df):,}")
    print(f"  Unique locations: {len(locations):,}")
    return locations


def create_climate_image():
    """WorldClim BioClim - 1km native resolution."""
    worldclim = ee.Image('WORLDCLIM/V1/BIO')
    return worldclim  # 19 bands: bio01-bio19


def create_terrain_image():
    """SRTM terrain derivatives - 30m native, sample at 100m."""
    srtm = ee.Image('USGS/SRTMGL1_003')
    terrain = ee.Terrain.products(srtm)

    # Multi-scale TPI for ridge/valley detection
    mtpi = ee.Image('CSP/ERGo/1_0/Global/ALOS_mTPI').rename('mtpi')

    # Landforms classification
    landforms = ee.Image('CSP/ERGo/1_0/Global/ALOS_landforms').rename('landforms')

    # Topographic diversity
    topo_div = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').rename('topo_diversity')

    return (terrain.select(['elevation', 'slope', 'aspect'])
            .addBands(mtpi)
            .addBands(landforms)
            .addBands(topo_div))


def create_soil_image():
    """OpenLandMap soil properties - 250m native."""
    clay = ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('clay_pct')
    sand = ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('sand_pct')
    silt = ee.Image('OpenLandMap/SOL/SOL_SILT-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('silt_pct')
    bulk = ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('bulk_density')
    soc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('organic_carbon')
    ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')
    texture = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture')

    return (clay.addBands(sand).addBands(silt).addBands(bulk)
            .addBands(soc).addBands(ph).addBands(texture))


def create_water_forest_image():
    """JRC Water + Hansen Forest - 30m native, sample at 100m."""
    # JRC Global Surface Water
    jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
    water_occ = jrc.select('occurrence').rename('water_occurrence')
    water_season = jrc.select('seasonality').rename('water_seasonality')
    water_recur = jrc.select('recurrence').rename('water_recurrence')

    # Hansen Global Forest Change
    hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')
    treecover = hansen.select('treecover2000')
    loss = hansen.select('loss').rename('forest_loss')
    gain = hansen.select('gain').rename('forest_gain')
    lossyear = hansen.select('lossyear').rename('loss_year')

    return (water_occ.addBands(water_season).addBands(water_recur)
            .addBands(treecover).addBands(loss).addBands(gain).addBands(lossyear))


def create_landcover_disturbance_image():
    """ESA WorldCover + Human Modification."""
    # ESA WorldCover 2021 (10m native)
    worldcover = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').rename('landcover')

    # Global Human Modification (1km native)
    ghm = ee.ImageCollection('CSP/HM/GlobalHumanModification').first().select('gHM').rename('human_modification')

    # MODIS fire frequency
    fire = ee.ImageCollection('MODIS/061/MCD64A1').select('BurnDate')
    fire_count = fire.map(lambda img: img.gt(0).unmask(0)).sum().rename('fire_count')

    return worldcover.addBands(ghm).addBands(fire_count)


def create_vegetation_image():
    """MODIS NDVI/EVI - 250m-1km native."""
    ndvi_col = ee.ImageCollection('MODIS/061/MOD13A2').filterDate('2020-01-01', '2023-12-31')
    ndvi_mean = ndvi_col.select('NDVI').mean().multiply(0.0001).rename('ndvi_mean')
    ndvi_std = ndvi_col.select('NDVI').reduce(ee.Reducer.stdDev()).multiply(0.0001).rename('ndvi_std')
    evi_mean = ndvi_col.select('EVI').mean().multiply(0.0001).rename('evi_mean')

    return ndvi_mean.addBands(ndvi_std).addBands(evi_mean)


def sample_location_multiresolution(lat, lon):
    """Sample all variables at appropriate resolutions for a single point."""
    point = ee.Geometry.Point([lon, lat])

    results = {'latitude': lat, 'longitude': lon}

    # Climate at 1km
    climate = create_climate_image()
    climate_sample = climate.sample(point, scale=1000).first().getInfo()
    if climate_sample:
        results.update(climate_sample['properties'])

    # Terrain at 100m
    terrain = create_terrain_image()
    terrain_sample = terrain.sample(point, scale=100).first().getInfo()
    if terrain_sample:
        results.update(terrain_sample['properties'])

    # Soil at 250m
    soil = create_soil_image()
    soil_sample = soil.sample(point, scale=250).first().getInfo()
    if soil_sample:
        results.update(soil_sample['properties'])

    # Water/Forest at 100m
    water_forest = create_water_forest_image()
    wf_sample = water_forest.sample(point, scale=100).first().getInfo()
    if wf_sample:
        results.update(wf_sample['properties'])

    # Landcover/Disturbance at 100m
    landcover = create_landcover_disturbance_image()
    lc_sample = landcover.sample(point, scale=100).first().getInfo()
    if lc_sample:
        results.update(lc_sample['properties'])

    # Vegetation at 500m
    veg = create_vegetation_image()
    veg_sample = veg.sample(point, scale=500).first().getInfo()
    if veg_sample:
        results.update(veg_sample['properties'])

    return results


def sample_batch_unified(args):
    """Sample a batch using single composite at mixed resolution."""
    batch_idx, locations_batch = args

    try:
        # Create all images once
        climate = create_climate_image()
        terrain = create_terrain_image()
        soil = create_soil_image()
        water_forest = create_water_forest_image()
        landcover = create_landcover_disturbance_image()
        vegetation = create_vegetation_image()

        # Combine ALL into single image (will resample to common scale)
        # Use 250m as compromise - good for most, not too slow
        combined = (climate
            .addBands(terrain)
            .addBands(soil)
            .addBands(water_forest)
            .addBands(landcover)
            .addBands(vegetation)
        )

        # Create features with ORIGINAL coordinates stored as properties
        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point, {
                'orig_lat': float(row['latitude']),
                'orig_lon': float(row['longitude'])
            }))

        fc = ee.FeatureCollection(features)

        # Sample at 250m (compromise resolution)
        sampled = combined.sampleRegions(
            collection=fc,
            scale=250,
            geometries=False  # Don't need geometry back, we have orig coords
        )

        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, pd.DataFrame(), "no_results"

        # Parse results, using ORIGINAL coordinates
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
    print("UNIFIED ENVIRONMENTAL EXTRACTION (250m resolution)")
    print(f"Using {MAX_WORKERS} parallel workers")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    locations = load_unique_locations()

    # Check for checkpoint - use ORIGINAL coordinates for matching
    checkpoint_file = OUTPUT_DIR / "env_unified_checkpoint.parquet"
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        # Match on original coordinates (high precision)
        existing_locs = set(zip(
            existing['latitude'].round(8),
            existing['longitude'].round(8)
        ))
        locations['key'] = list(zip(
            locations['latitude'].round(8),
            locations['longitude'].round(8)
        ))
        locations = locations[~locations['key'].isin(existing_locs)].drop('key', axis=1)
        print(f"  Resuming: {len(existing):,} done, {len(locations):,} remaining")
        all_results = [existing]
    else:
        all_results = []

    if len(locations) == 0:
        print("✅ All locations already extracted!")
        return

    # Show what we're extracting
    print("\nVariables to extract (47 total):")
    print("  Climate (19): bio01-bio19 at 1km→250m")
    print("  Terrain (6): elevation, slope, aspect, mtpi, landforms, topo_diversity at 100m→250m")
    print("  Soil (7): clay, sand, silt, bulk_density, organic_carbon, ph, texture at 250m")
    print("  Water/Forest (7): water_occ/season/recur, treecover, loss, gain, lossyear at 100m→250m")
    print("  Landcover (3): landcover, human_modification, fire_count at 100m→250m")
    print("  Vegetation (3): ndvi_mean, ndvi_std, evi_mean at 500m→250m")

    n_batches = (len(locations) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = [(i, locations.iloc[i*BATCH_SIZE:(i+1)*BATCH_SIZE])
               for i in range(n_batches)]

    print(f"\nProcessing {len(locations):,} locations in {n_batches} batches...")

    start_time = time.time()
    extracted = errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_unified, b): b[0] for b in batches}

        for i, future in enumerate(as_completed(futures)):
            batch_idx, result_df, status = future.result()

            if status == "success" and len(result_df) > 0:
                all_results.append(result_df)
                extracted += len(result_df)
            elif status != "success":
                errors += 1
                if errors <= 5:
                    print(f"  Batch {batch_idx} error: {status}")

            if (i + 1) % 25 == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining = (len(locations) - extracted) / rate / 3600 if rate > 0 else 0
                print(f"  Progress: {i+1}/{n_batches}, {extracted:,} extracted, "
                      f"{errors} errors, ~{remaining:.1f}h remaining")

            if (i + 1) % 100 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)
                print(f"  💾 Checkpoint: {len(checkpoint_df):,} records")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"env_unified_{timestamp}.parquet"
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

        # Show sample of columns
        cols = [c for c in final_df.columns if c not in ['latitude', 'longitude']]
        print(f"Columns: {cols[:10]}... (+{len(cols)-10} more)")
    else:
        print("\n❌ No results")


if __name__ == "__main__":
    main()
