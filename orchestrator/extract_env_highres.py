#!/usr/bin/env python3
"""
High-Resolution Environmental Variable Extraction

Uses NATIVE resolution for each dataset:
- Climate (WorldClim): 1km (native)
- Terrain (SRTM): 30m (native)
- Soil (OpenLandMap): 250m (native)
- Water/Forest (JRC/Hansen): 30m (native)
- Land cover (ESA): 10m (native)
- Vegetation (MODIS): 250m (native)
- Human modification: 1km (native)

Extracts in separate passes at native resolutions, then merges.
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
BATCH_SIZE = 500   # Smaller batches for high-res
MAX_WORKERS = 10   # Fewer workers to avoid quota issues
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


# Define extraction layers with their native resolutions
EXTRACTION_LAYERS = {
    'climate_1km': {
        'scale': 1000,
        'image': lambda: ee.Image('WORLDCLIM/V1/BIO'),
        'bands': ['bio01', 'bio02', 'bio03', 'bio04', 'bio05', 'bio06', 'bio07',
                  'bio08', 'bio09', 'bio10', 'bio11', 'bio12', 'bio13', 'bio14',
                  'bio15', 'bio16', 'bio17', 'bio18', 'bio19']
    },
    'terrain_30m': {
        'scale': 30,
        'image': lambda: ee.Terrain.products(ee.Image('USGS/SRTMGL1_003')).select(['elevation', 'slope', 'aspect']),
        'bands': ['elevation', 'slope', 'aspect']
    },
    'topo_indices_270m': {
        'scale': 270,
        'image': lambda: (ee.Image('CSP/ERGo/1_0/Global/ALOS_mTPI').rename('mtpi')
                         .addBands(ee.Image('CSP/ERGo/1_0/Global/ALOS_landforms').rename('landforms'))
                         .addBands(ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').rename('topo_diversity'))),
        'bands': ['mtpi', 'landforms', 'topo_diversity']
    },
    'soil_250m': {
        'scale': 250,
        'image': lambda: (ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('clay_pct')
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('sand_pct'))
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_SILT-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('silt_pct'))
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('bulk_density'))
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('organic_carbon'))
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph'))
                         .addBands(ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture'))),
        'bands': ['clay_pct', 'sand_pct', 'silt_pct', 'bulk_density', 'organic_carbon', 'soil_ph', 'soil_texture']
    },
    'water_30m': {
        'scale': 30,
        'image': lambda: (ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').rename('water_occurrence')
                         .addBands(ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('seasonality').rename('water_seasonality'))
                         .addBands(ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('recurrence').rename('water_recurrence'))),
        'bands': ['water_occurrence', 'water_seasonality', 'water_recurrence']
    },
    'forest_30m': {
        'scale': 30,
        'image': lambda: (ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000')
                         .addBands(ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('loss').rename('forest_loss'))
                         .addBands(ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('gain').rename('forest_gain'))
                         .addBands(ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('lossyear').rename('loss_year'))),
        'bands': ['treecover2000', 'forest_loss', 'forest_gain', 'loss_year']
    },
    'landcover_10m': {
        'scale': 10,
        'image': lambda: ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').rename('landcover_esa'),
        'bands': ['landcover_esa']
    },
    'vegetation_250m': {
        'scale': 250,
        'image': lambda: (ee.ImageCollection('MODIS/061/MOD13A2').filterDate('2020-01-01', '2023-12-31')
                         .select('NDVI').mean().multiply(0.0001).rename('ndvi_mean')
                         .addBands(ee.ImageCollection('MODIS/061/MOD13A2').filterDate('2020-01-01', '2023-12-31')
                                  .select('NDVI').reduce(ee.Reducer.stdDev()).multiply(0.0001).rename('ndvi_std'))
                         .addBands(ee.ImageCollection('MODIS/061/MOD13A2').filterDate('2020-01-01', '2023-12-31')
                                  .select('EVI').mean().multiply(0.0001).rename('evi_mean'))),
        'bands': ['ndvi_mean', 'ndvi_std', 'evi_mean']
    },
    'disturbance_1km': {
        'scale': 1000,
        'image': lambda: (ee.ImageCollection('CSP/HM/GlobalHumanModification').first().select('gHM').rename('human_modification')
                         .addBands(ee.ImageCollection('MODIS/061/MCD64A1').select('BurnDate')
                                  .map(lambda img: img.gt(0).unmask(0)).sum().rename('fire_count'))),
        'bands': ['human_modification', 'fire_count']
    }
}


def sample_batch_layer(args):
    """Sample a batch for a specific layer at native resolution."""
    batch_idx, locations_batch, layer_name, layer_config = args

    try:
        image = layer_config['image']()
        scale = layer_config['scale']

        # Create features with original coordinates
        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point, {
                'orig_lat': float(row['latitude']),
                'orig_lon': float(row['longitude'])
            }))

        fc = ee.FeatureCollection(features)

        # Sample at NATIVE resolution
        sampled = image.sampleRegions(
            collection=fc,
            scale=scale,
            geometries=False
        )

        results = sampled.getInfo()

        if not results or 'features' not in results:
            return batch_idx, layer_name, pd.DataFrame(), "no_results"

        records = []
        for feature in results['features']:
            props = feature['properties']
            record = {
                'latitude': props.pop('orig_lat'),
                'longitude': props.pop('orig_lon'),
                **props
            }
            records.append(record)

        return batch_idx, layer_name, pd.DataFrame(records), "success"

    except Exception as e:
        return batch_idx, layer_name, pd.DataFrame(), str(e)[:100]


def extract_layer(layer_name, layer_config, locations, checkpoint_dir):
    """Extract a single layer for all locations."""
    checkpoint_file = checkpoint_dir / f"{layer_name}_checkpoint.parquet"

    # Check for existing progress
    if checkpoint_file.exists():
        existing = pd.read_parquet(checkpoint_file)
        existing_locs = set(zip(existing['latitude'].round(8), existing['longitude'].round(8)))
        locations_copy = locations.copy()
        locations_copy['key'] = list(zip(locations_copy['latitude'].round(8), locations_copy['longitude'].round(8)))
        remaining = locations_copy[~locations_copy['key'].isin(existing_locs)].drop('key', axis=1)
        print(f"  Resuming {layer_name}: {len(existing):,} done, {len(remaining):,} remaining")
        all_results = [existing]
    else:
        remaining = locations
        all_results = []

    if len(remaining) == 0:
        print(f"  ✅ {layer_name} complete")
        return pd.read_parquet(checkpoint_file)

    n_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    batches = [(i, remaining.iloc[i*BATCH_SIZE:(i+1)*BATCH_SIZE], layer_name, layer_config)
               for i in range(n_batches)]

    start_time = time.time()
    extracted = errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(sample_batch_layer, b): b[0] for b in batches}

        for i, future in enumerate(as_completed(futures)):
            batch_idx, lname, result_df, status = future.result()

            if status == "success" and len(result_df) > 0:
                all_results.append(result_df)
                extracted += len(result_df)
            elif status != "success":
                errors += 1

            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining_time = (len(remaining) - extracted) / rate / 3600 if rate > 0 else 0
                print(f"    {layer_name}: {i+1}/{n_batches}, {extracted:,} extracted, ~{remaining_time:.1f}h remaining")

            if (i + 1) % 200 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df.to_parquet(checkpoint_file)
        return final_df

    return pd.DataFrame()


def main():
    print("=" * 70)
    print("HIGH-RESOLUTION ENVIRONMENTAL EXTRACTION")
    print("Native resolution per dataset")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    checkpoint_dir = OUTPUT_DIR / "highres_checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    locations = load_unique_locations()

    print("\nExtraction layers:")
    for name, config in EXTRACTION_LAYERS.items():
        print(f"  {name}: {config['scale']}m - {config['bands']}")

    print("\n" + "=" * 70)
    print("EXTRACTING EACH LAYER AT NATIVE RESOLUTION")
    print("=" * 70)

    layer_results = {}

    for layer_name, layer_config in EXTRACTION_LAYERS.items():
        print(f"\n[{layer_name}] Scale: {layer_config['scale']}m")
        result = extract_layer(layer_name, layer_config, locations, checkpoint_dir)
        if len(result) > 0:
            layer_results[layer_name] = result
            print(f"  ✅ {layer_name}: {len(result):,} records")

    # Merge all layers by coordinates
    print("\n" + "=" * 70)
    print("MERGING LAYERS")
    print("=" * 70)

    if layer_results:
        # Start with largest result as base
        base_name = max(layer_results.keys(), key=lambda k: len(layer_results[k]))
        merged = layer_results[base_name].copy()
        print(f"Base: {base_name} ({len(merged):,} records)")

        for name, df in layer_results.items():
            if name != base_name:
                # Merge on coordinates (high precision)
                df_to_merge = df.drop(columns=['latitude', 'longitude'], errors='ignore')
                df_to_merge['lat_key'] = layer_results[name]['latitude'].round(8)
                df_to_merge['lon_key'] = layer_results[name]['longitude'].round(8)

                merged['lat_key'] = merged['latitude'].round(8)
                merged['lon_key'] = merged['longitude'].round(8)

                merged = merged.merge(df_to_merge, on=['lat_key', 'lon_key'], how='left')
                merged = merged.drop(columns=['lat_key', 'lon_key'])
                print(f"  + {name}: {len(df):,} records merged")

        # Save final
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"env_highres_{timestamp}.parquet"
        merged.to_parquet(output_file)

        print("\n" + "=" * 70)
        print("EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"Total records: {len(merged):,}")
        print(f"Total variables: {len(merged.columns) - 2}")
        print(f"Output: {output_file}")

        # Show coverage stats
        print("\nVariable coverage:")
        for col in merged.columns:
            if col not in ['latitude', 'longitude']:
                non_null = merged[col].notna().sum()
                print(f"  {col}: {non_null:,} ({100*non_null/len(merged):.1f}%)")


if __name__ == "__main__":
    main()
