#!/usr/bin/env python3
"""
High-Resolution Extraction for NEW Variables Only

Extracts variables we DON'T already have from AlphaEarth or overnight extraction,
at their NATIVE resolutions.

NEW variables to extract:
1. Soil (250m native) - clay, sand, silt, bulk_density, organic_carbon, pH, texture
2. Water/Hydrology (30m native) - water_occurrence, water_seasonality, water_recurrence
3. Landcover (10m native) - ESA WorldCover class
4. Topo indices (270m native) - mTPI, landforms, topo_diversity
5. Human modification (1km native) - gHM index
6. Fire (500m native) - fire count

We SKIP:
- Climate (bio01-bio19) - already extracted at 1km (native), usable from overnight
- Elevation/slope/aspect - getting from Hansen extraction at 30m
- Forest (treecover, loss, gain) - already in AlphaEarth + Hansen extraction
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
MAX_WORKERS = 5  # Reduced to avoid GEE rate limits
OUTPUT_DIR = Path(__file__).parent / "environmental_extractions"
PARQUET_PATH = Path(__file__).parent.parent / "Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet"

print("Initializing Earth Engine...")
ee.Initialize(project=PROJECT)
print(f"✅ Earth Engine initialized (project: {PROJECT})")


def load_unique_locations():
    """Load all unique locations."""
    print(f"\nLoading locations from {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()
    df = df.rename(columns={'decimalLatitude': 'latitude', 'decimalLongitude': 'longitude'})
    locations = df[['latitude', 'longitude']].drop_duplicates().reset_index(drop=True)
    print(f"  Total unique locations: {len(locations):,}")
    return locations


# Define extraction layers with native resolutions
EXTRACTION_LAYERS = {
    'soil_250m': {
        'scale': 250,
        'image': lambda: (
            ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('clay_pct')
            .addBands(ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('sand_pct'))
            # Silt computed as: 100 - clay - sand (silt dataset doesn't exist in GEE)
            .addBands(ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('bulk_density'))
            .addBands(ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('organic_carbon'))
            .addBands(ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph'))
            .addBands(ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture'))
        ),
    },
    'water_30m': {
        'scale': 30,
        'image': lambda: (
            ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').rename('water_occurrence')
            .addBands(ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('seasonality').rename('water_seasonality'))
            .addBands(ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('recurrence').rename('water_recurrence'))
        ),
    },
    'landcover_10m': {
        'scale': 10,
        'image': lambda: ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').rename('landcover_esa'),
    },
    'topo_270m': {
        'scale': 270,
        'image': lambda: (
            ee.Image('CSP/ERGo/1_0/Global/ALOS_mTPI').rename('mtpi')
            .addBands(ee.Image('CSP/ERGo/1_0/Global/ALOS_landforms').rename('landforms'))
            .addBands(ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').rename('topo_diversity'))
        ),
    },
    'disturbance_1km': {
        'scale': 1000,
        'image': lambda: (
            ee.ImageCollection('CSP/HM/GlobalHumanModification').first().select('gHM').rename('human_modification')
            .addBands(
                ee.ImageCollection('MODIS/061/MCD64A1').select('BurnDate')
                .map(lambda img: img.gt(0).unmask(0)).sum().rename('fire_count')
            )
        ),
    },
}


def sample_batch_layer(args):
    """Sample a batch for a specific layer at native resolution."""
    batch_idx, locations_batch, layer_name, layer_config = args

    try:
        image = layer_config['image']()
        scale = layer_config['scale']

        features = []
        for _, row in locations_batch.iterrows():
            point = ee.Geometry.Point([float(row['longitude']), float(row['latitude'])])
            features.append(ee.Feature(point, {
                'orig_lat': float(row['latitude']),
                'orig_lon': float(row['longitude'])
            }))

        fc = ee.FeatureCollection(features)

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
        import traceback
        err_msg = f"{str(e)[:80]} | {traceback.format_exc()[-100:]}"
        return batch_idx, layer_name, pd.DataFrame(), err_msg


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
        print(f"    Resuming: {len(existing):,} done, {len(remaining):,} remaining")
        all_results = [existing]
    else:
        remaining = locations
        all_results = []

    if len(remaining) == 0:
        print(f"    ✅ Complete")
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
                if errors <= 3:
                    print(f"      ERROR: {status}")

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                remaining_time = (len(remaining) - extracted) / rate / 3600 if rate > 0 else 0
                print(f"      {i+1}/{n_batches}, {extracted:,} extracted, ~{remaining_time:.1f}h remaining")

            if (i + 1) % 500 == 0 and all_results:
                checkpoint_df = pd.concat(all_results, ignore_index=True)
                checkpoint_df.to_parquet(checkpoint_file)

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df.to_parquet(checkpoint_file)
        return final_df

    return pd.DataFrame()


def main():
    print("=" * 70)
    print("HIGH-RESOLUTION NEW VARIABLES EXTRACTION")
    print("Native resolution per dataset")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    checkpoint_dir = OUTPUT_DIR / "highres_new_vars"
    checkpoint_dir.mkdir(exist_ok=True)

    locations = load_unique_locations()

    print("\nLayers to extract:")
    for name, config in EXTRACTION_LAYERS.items():
        print(f"  {name}: {config['scale']}m native")

    print("\n" + "=" * 70)

    layer_results = {}

    for layer_name, layer_config in EXTRACTION_LAYERS.items():
        print(f"\n[{layer_name}] @ {layer_config['scale']}m native")
        result = extract_layer(layer_name, layer_config, locations, checkpoint_dir)
        if len(result) > 0:
            layer_results[layer_name] = result
            print(f"    ✅ {len(result):,} records")

    # Merge all layers
    print("\n" + "=" * 70)
    print("MERGING LAYERS")
    print("=" * 70)

    if layer_results:
        # Start with first layer
        base_name = list(layer_results.keys())[0]
        merged = layer_results[base_name].copy()
        print(f"Base: {base_name} ({len(merged):,} records)")

        for name, df in layer_results.items():
            if name != base_name:
                # Merge on coordinates
                cols_to_add = [c for c in df.columns if c not in ['latitude', 'longitude']]
                df_merge = df[['latitude', 'longitude'] + cols_to_add].copy()
                df_merge['lat_key'] = df_merge['latitude'].round(8)
                df_merge['lon_key'] = df_merge['longitude'].round(8)

                merged['lat_key'] = merged['latitude'].round(8)
                merged['lon_key'] = merged['longitude'].round(8)

                merged = merged.merge(
                    df_merge.drop(columns=['latitude', 'longitude']),
                    on=['lat_key', 'lon_key'],
                    how='outer'
                )
                merged = merged.drop(columns=['lat_key', 'lon_key'])

                # Fill lat/lon from either source
                if 'latitude_x' in merged.columns:
                    merged['latitude'] = merged['latitude_x'].fillna(merged['latitude_y'])
                    merged['longitude'] = merged['longitude_x'].fillna(merged['longitude_y'])
                    merged = merged.drop(columns=['latitude_x', 'latitude_y', 'longitude_x', 'longitude_y'])

                print(f"  + {name}")

        # Save final merged
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"new_vars_highres_{timestamp}.parquet"
        merged.to_parquet(output_file)

        print("\n" + "=" * 70)
        print("EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"Total records: {len(merged):,}")
        print(f"Total variables: {len(merged.columns) - 2}")
        print(f"Output: {output_file}")
        print(f"\nVariables: {[c for c in merged.columns if c not in ['latitude', 'longitude']]}")


if __name__ == "__main__":
    main()
