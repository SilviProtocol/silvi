#!/usr/bin/env python3
"""
AlphaEarth GCS COG Sampler
==========================

Sample AlphaEarth embeddings directly from Cloud Optimized GeoTIFFs on GCS.
This bypasses Earth Engine entirely, reducing cost by 10-50x.

Cost: ~$0.12/GB egress (requester pays)
Speed: ~1000 points/second with batching

Requirements:
    pip install rasterio pyproj pandas numpy geopandas shapely

Usage:
    python sample_alphaearth_cog.py --test           # Test with 10 points
    python sample_alphaearth_cog.py --year 2017 --limit 1000  # Sample 1000 points
    python sample_alphaearth_cog.py --all            # Process all years

Author: Treekipedia Team
Created: January 2026
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import time
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

GCS_BUCKET = "gs://alphaearth_foundations"
GCS_BASE_PATH = "satellite_embedding/v1/annual"
PROJECT_ID = "treekipedia-479918"  # For requester-pays

YEARS_AVAILABLE = list(range(2017, 2025))  # 2017-2024
NUM_BANDS = 64

# Local paths
SCRIPT_DIR = Path(__file__).parent
INDEX_FILE = SCRIPT_DIR / "aef_index.parquet"
OUTPUT_DIR = SCRIPT_DIR / "gcs_embeddings"

# GCS Authentication
GOOGLE_APPLICATION_CREDENTIALS = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS


# =============================================================================
# DEPENDENCIES CHECK
# =============================================================================

def check_dependencies():
    """Check and import required dependencies."""
    missing = []

    global rasterio, Transformer, gpd, box

    try:
        import rasterio as _rasterio
        from rasterio.windows import Window
        rasterio = _rasterio
    except ImportError:
        missing.append('rasterio')

    try:
        from pyproj import Transformer as _Transformer
        Transformer = _Transformer
    except ImportError:
        missing.append('pyproj')

    try:
        import geopandas as _gpd
        gpd = _gpd
    except ImportError:
        missing.append('geopandas')

    try:
        from shapely.geometry import box as _box, Point
        box = _box
    except ImportError:
        missing.append('shapely')

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False

    return True


# =============================================================================
# INDEX LOADING
# =============================================================================

def load_cog_index(year: int = None) -> pd.DataFrame:
    """
    Load the COG index file.

    Args:
        year: Optional year filter

    Returns:
        DataFrame with COG file info and bounding boxes
    """
    if not INDEX_FILE.exists():
        raise FileNotFoundError(
            f"Index file not found: {INDEX_FILE}\n"
            f"Download with: gsutil -u {PROJECT_ID} cp "
            f"{GCS_BUCKET}/{GCS_BASE_PATH}/aef_index.parquet {INDEX_FILE}"
        )

    df = pd.read_parquet(INDEX_FILE)

    if year is not None:
        df = df[df['year'] == year]

    return df


def find_cog_for_point(lat: float, lon: float, year: int, index_df: pd.DataFrame) -> Optional[str]:
    """
    Find which COG file contains a given lat/lon point for a year.

    Args:
        lat: Latitude
        lon: Longitude
        year: Year (2017-2024)
        index_df: COG index DataFrame

    Returns:
        GCS path to COG file, or None if not found
    """
    # Filter by year first
    year_df = index_df[index_df['year'] == year]

    # Filter by bounding box
    matches = year_df[
        (year_df['wgs84_west'] <= lon) &
        (year_df['wgs84_east'] >= lon) &
        (year_df['wgs84_south'] <= lat) &
        (year_df['wgs84_north'] >= lat)
    ]

    if len(matches) == 0:
        return None

    # Return first match (there might be overlaps at UTM zone boundaries)
    return matches.iloc[0]['path']


# =============================================================================
# EMBEDDING SAMPLING
# =============================================================================

def dequantize_embedding(raw_values: np.ndarray) -> np.ndarray:
    """
    Convert int8 COG values to float embeddings.

    Formula: embedding = sign(raw) * (raw / 127.5)^2

    Args:
        raw_values: Array of int8 values from COG

    Returns:
        Array of float embeddings in range [-1, 1]
    """
    raw = raw_values.astype(np.float64)
    embedding = np.sign(raw) * ((raw / 127.5) ** 2)
    return embedding


def sample_single_point(
    cog_path: str,
    lat: float,
    lon: float,
    src=None
) -> Optional[np.ndarray]:
    """
    Sample embedding for a single point from a COG file.

    Args:
        cog_path: GCS path to COG file
        lat: Latitude
        lon: Longitude
        src: Optional pre-opened rasterio dataset

    Returns:
        64-element numpy array of embedding values, or None if failed/masked
    """
    from rasterio.windows import Window

    close_src = False
    try:
        if src is None:
            # Configure GDAL for GCS access with requester-pays
            env = rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif,.tiff',
                GDAL_HTTP_UNSAFESSL='YES',
                GS_USER_PROJECT=PROJECT_ID
            )
            env.__enter__()
            src = rasterio.open(cog_path)
            close_src = True

        # Transform lat/lon to the COG's CRS
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(lon, lat)

        # Get pixel coordinates
        row, col = src.index(x, y)

        # Check bounds
        if not (0 <= row < src.height and 0 <= col < src.width):
            return None

        # Read single pixel (all 64 bands) via HTTP range request
        window = Window(col, row, 1, 1)
        data = src.read(window=window)  # Shape: (64, 1, 1)
        raw = data.flatten()

        # Check for masked pixel (-128)
        if raw[0] == -128:
            return None

        # Dequantize
        embedding = dequantize_embedding(raw)
        return embedding

    except Exception as e:
        print(f"Error sampling ({lat}, {lon}) from {cog_path}: {e}")
        return None
    finally:
        if close_src and src is not None:
            src.close()


def sample_batch_from_cog(
    cog_path: str,
    points: List[Dict],
    year: int
) -> List[Dict]:
    """
    Sample multiple points from a single COG file efficiently.

    Opens the file once and reads all points - much faster than opening per-point.

    Args:
        cog_path: GCS path to COG file
        points: List of dicts with 'lat', 'lon', 'taxon_id' keys
        year: Year for this COG

    Returns:
        List of result dicts with embeddings
    """
    from rasterio.windows import Window

    results = []

    # Configure GDAL for GCS with requester-pays
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif,.tiff',
        GS_USER_PROJECT=PROJECT_ID
    ):
        try:
            with rasterio.open(cog_path) as src:
                # Create transformer once
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

                for pt in points:
                    lat, lon = pt['lat'], pt['lon']

                    try:
                        # Transform coordinates
                        x, y = transformer.transform(lon, lat)
                        row, col = src.index(x, y)

                        # Check bounds
                        if not (0 <= row < src.height and 0 <= col < src.width):
                            continue

                        # Read pixel
                        window = Window(col, row, 1, 1)
                        data = src.read(window=window)
                        raw = data.flatten()

                        # Skip masked pixels
                        if raw[0] == -128:
                            continue

                        # Dequantize
                        embedding = dequantize_embedding(raw)

                        # Build result
                        result = {
                            'taxon_id': pt.get('taxon_id', ''),
                            'latitude': lat,
                            'longitude': lon,
                            'emb_year': year,
                            'orig_year': pt.get('year', year),
                        }
                        for i, val in enumerate(embedding):
                            result[f'A{i:02d}'] = val

                        results.append(result)

                    except Exception as e:
                        # Skip individual point errors silently
                        pass

        except Exception as e:
            print(f"Error opening {cog_path}: {e}")

    return results


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def group_points_by_cog(
    points_df: pd.DataFrame,
    year: int,
    index_df: pd.DataFrame
) -> Dict[str, List[Dict]]:
    """
    Group points by which COG file they belong to.

    This is the key optimization - process all points in a COG together.

    Args:
        points_df: DataFrame with 'decimalLatitude', 'decimalLongitude', 'taxon_id'
        year: Year to process
        index_df: COG index DataFrame

    Returns:
        Dict mapping COG path -> list of point dicts
    """
    # Filter index to year
    year_index = index_df[index_df['year'] == year].copy()

    grouped = defaultdict(list)
    unmatched = 0

    for _, row in points_df.iterrows():
        lat = row['decimalLatitude']
        lon = row['decimalLongitude']

        # Find matching COG
        matches = year_index[
            (year_index['wgs84_west'] <= lon) &
            (year_index['wgs84_east'] >= lon) &
            (year_index['wgs84_south'] <= lat) &
            (year_index['wgs84_north'] >= lat)
        ]

        if len(matches) > 0:
            cog_path = matches.iloc[0]['path']
            grouped[cog_path].append({
                'lat': lat,
                'lon': lon,
                'taxon_id': row.get('taxon_id', ''),
                'year': row.get('year', year)
            })
        else:
            unmatched += 1

    if unmatched > 0:
        print(f"  Warning: {unmatched} points didn't match any COG")

    return dict(grouped)


def process_year(
    year: int,
    limit: int = None,
    output_file: str = None,
    workers: int = 4
) -> pd.DataFrame:
    """
    Process all occurrences for a year.

    Args:
        year: Year to process (2017-2024)
        limit: Optional limit on number of points
        output_file: Optional output parquet file
        workers: Number of parallel workers

    Returns:
        DataFrame with embeddings
    """
    print(f"\n{'='*60}")
    print(f"PROCESSING YEAR {year}")
    print(f"{'='*60}")

    # Load index
    print("Loading COG index...")
    index_df = load_cog_index()
    year_cogs = len(index_df[index_df['year'] == year])
    print(f"  COG files for {year}: {year_cogs:,}")

    # Load occurrences from BigQuery (or local file)
    print("Loading occurrences...")
    occ_file = SCRIPT_DIR / f"occurrences_{year}.parquet"

    if occ_file.exists():
        points_df = pd.read_parquet(occ_file)
    else:
        # Query BigQuery
        try:
            import pandas_gbq
            query = f"""
            SELECT taxon_id, decimalLatitude, decimalLongitude, year
            FROM `{PROJECT_ID}.species_data.occurrences`
            WHERE year = {year}
            """
            if limit:
                query += f" LIMIT {limit}"

            points_df = pandas_gbq.read_gbq(query, project_id=PROJECT_ID)
            # Cache locally
            points_df.to_parquet(occ_file, index=False)
        except Exception as e:
            print(f"Error loading from BigQuery: {e}")
            print("Using local parquet files instead...")

            # Fall back to local full file
            local_file = Path("/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet")
            if local_file.exists():
                full_df = pd.read_parquet(local_file)
                points_df = full_df[full_df['year'] == year]
            else:
                raise FileNotFoundError("No occurrence data found")

    if limit:
        points_df = points_df.head(limit)

    print(f"  Points to process: {len(points_df):,}")

    # Group by COG
    print("Grouping points by COG file...")
    grouped = group_points_by_cog(points_df, year, index_df)
    print(f"  COG files to read: {len(grouped)}")

    # Process each COG
    all_results = []
    total_cogs = len(grouped)

    start_time = time.time()

    for i, (cog_path, points) in enumerate(grouped.items()):
        if i % 100 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  Processing COG {i+1}/{total_cogs} ({rate:.1f} COGs/sec)...")

        results = sample_batch_from_cog(cog_path, points, year)
        all_results.extend(results)

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"  Points sampled: {len(all_results):,}")
    print(f"  Rate: {len(all_results)/elapsed:.0f} points/sec")

    # Create DataFrame
    if all_results:
        result_df = pd.DataFrame(all_results)

        if output_file:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / output_file
            result_df.to_parquet(output_path, index=False)
            print(f"  Saved to: {output_path}")

        return result_df

    return pd.DataFrame()


# =============================================================================
# TEST MODE
# =============================================================================

def run_test():
    """Test sampling with a few known points."""
    print("\n" + "="*60)
    print("GCS COG SAMPLING TEST")
    print("="*60)

    # Load index
    print("\n1. Loading COG index...")
    index_df = load_cog_index()
    print(f"   Total COG files: {len(index_df):,}")
    print(f"   Years: {sorted(index_df['year'].unique())}")

    # Test points (various locations)
    test_points = [
        {"lat": 37.7749, "lon": -122.4194, "name": "San Francisco"},
        {"lat": 51.5074, "lon": -0.1278, "name": "London"},
        {"lat": -33.8688, "lon": 151.2093, "name": "Sydney"},
        {"lat": -22.9068, "lon": -43.1729, "name": "Rio de Janeiro"},
        {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo"},
    ]

    year = 2020

    print(f"\n2. Finding COGs for test points (year={year})...")
    for pt in test_points:
        cog_path = find_cog_for_point(pt['lat'], pt['lon'], year, index_df)
        if cog_path:
            print(f"   {pt['name']}: {cog_path.split('/')[-1]}")
        else:
            print(f"   {pt['name']}: NO COG FOUND")

    print(f"\n3. Sampling embeddings...")
    for pt in test_points:
        cog_path = find_cog_for_point(pt['lat'], pt['lon'], year, index_df)
        if cog_path:
            print(f"\n   {pt['name']} ({pt['lat']}, {pt['lon']}):")
            embedding = sample_single_point(cog_path, pt['lat'], pt['lon'])
            if embedding is not None:
                print(f"   ✓ Got 64-dim embedding")
                print(f"   First 5 values: {embedding[:5].round(4)}")
                print(f"   Norm: {np.linalg.norm(embedding):.4f}")
            else:
                print(f"   ✗ Masked or error")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Sample AlphaEarth from GCS COGs')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    parser.add_argument('--year', type=int, help='Year to process (2017-2024)')
    parser.add_argument('--all', action='store_true', help='Process all years')
    parser.add_argument('--limit', type=int, help='Limit number of points')
    parser.add_argument('--workers', type=int, default=4, help='Parallel workers')
    parser.add_argument('--output', type=str, help='Output file name')

    args = parser.parse_args()

    if not check_dependencies():
        return

    if args.test:
        run_test()
        return

    if args.year:
        output = args.output or f"embeddings_{args.year}.parquet"
        process_year(args.year, limit=args.limit, output_file=output, workers=args.workers)
    elif args.all:
        for year in YEARS_AVAILABLE:
            output = f"embeddings_{year}.parquet"
            process_year(year, limit=args.limit, output_file=output, workers=args.workers)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
