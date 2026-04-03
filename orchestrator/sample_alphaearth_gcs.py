#!/usr/bin/env python3
"""
Sample AlphaEarth Embeddings from GCS COGs
==========================================

This script reads AlphaEarth embeddings directly from Cloud Optimized GeoTIFFs
on Google Cloud Storage, WITHOUT using Earth Engine.

Cost: ~$0.12/GB egress (vs ~$0.40/EECU-hour for Earth Engine)
Speed: Range requests fetch only the pixels needed

Requirements:
    pip install rasterio pyproj pandas numpy gcsfs

Usage:
    python sample_alphaearth_gcs.py --test          # Test with 10 points
    python sample_alphaearth_gcs.py --year 2017     # Process a year
    python sample_alphaearth_gcs.py --input file.parquet --output embeddings.parquet

Author: Treekipedia Team
Created: January 2026
"""

import os
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# These will be imported after checking installation
rasterio = None
Transformer = None


def check_dependencies():
    """Check and import required dependencies."""
    global rasterio, Transformer

    missing = []

    try:
        import rasterio as _rasterio
        rasterio = _rasterio
    except ImportError:
        missing.append('rasterio')

    try:
        from pyproj import Transformer as _Transformer
        Transformer = _Transformer
    except ImportError:
        missing.append('pyproj')

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)} gcsfs")
        return False

    return True


# =============================================================================
# GCS COG CONFIGURATION
# =============================================================================

GCS_BUCKET = "gs://alphaearth_foundations"
YEARS_AVAILABLE = list(range(2017, 2025))  # 2017-2024

# COG file structure: 8192x8192 pixels, 64 bands, int8 values
COG_PIXEL_SIZE = 8192
NUM_BANDS = 64


def get_utm_zone(lon: float, lat: float) -> Tuple[int, str]:
    """
    Get UTM zone number and hemisphere from lat/lon.

    Args:
        lon: Longitude (-180 to 180)
        lat: Latitude (-90 to 90)

    Returns:
        (zone_number, hemisphere) e.g., (17, 'N')
    """
    zone = int((lon + 180) / 6) + 1
    hemisphere = 'N' if lat >= 0 else 'S'
    return zone, hemisphere


def dequantize_embedding(raw_values: np.ndarray) -> np.ndarray:
    """
    Convert int8 COG values to float embeddings.

    The COG stores embeddings as signed 8-bit integers.
    De-quantization formula:
        normalized = raw / 127.5
        embedding = sign(raw) * normalized^2

    Args:
        raw_values: Array of int8 values from COG

    Returns:
        Array of float embeddings in range [-1, 1]
    """
    raw = raw_values.astype(np.float64)
    normalized = raw / 127.5
    embedding = np.sign(raw) * (normalized ** 2)
    return embedding


def get_cog_path(year: int, utm_zone: int, hemisphere: str, tile_x: int, tile_y: int) -> str:
    """
    Build GCS path to a specific COG file.

    Note: Actual file naming may vary - need to check the index file.
    This is a placeholder that may need adjustment based on actual bucket structure.
    """
    zone_dir = f"{utm_zone:02d}{hemisphere}"
    # Tile naming convention TBD - need to check manifest
    return f"{GCS_BUCKET}/{year}/{zone_dir}/"


def sample_single_point(
    lat: float,
    lon: float,
    year: int,
    cog_cache: Dict = None
) -> Optional[np.ndarray]:
    """
    Sample embedding for a single point from GCS COG.

    Args:
        lat: Latitude
        lon: Longitude
        year: Year (2017-2024)
        cog_cache: Optional dict to cache open COG file handles

    Returns:
        64-element numpy array of embedding values, or None if failed
    """
    if rasterio is None:
        raise RuntimeError("rasterio not installed")

    try:
        # 1. Determine UTM zone
        utm_zone, hemisphere = get_utm_zone(lon, lat)

        # 2. Build COG URL (simplified - actual implementation needs index lookup)
        # For now, this is a placeholder showing the concept
        cog_url = f"{GCS_BUCKET}/{year}/{utm_zone:02d}{hemisphere}/"

        # 3. Open COG and read pixel
        # Note: rasterio can open URLs directly using GDAL's /vsigs/ or /vsicurl/
        # For GCS with requester-pays, you need authentication

        # Placeholder for actual implementation:
        # with rasterio.open(cog_url) as src:
        #     # Transform lat/lon to pixel coordinates
        #     transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        #     x, y = transformer.transform(lon, lat)
        #     row, col = src.index(x, y)
        #
        #     # Read 64 bands at this pixel
        #     window = rasterio.windows.Window(col, row, 1, 1)
        #     data = src.read(window=window)  # Shape: (64, 1, 1)
        #     raw = data.flatten()
        #
        #     # Dequantize
        #     embedding = dequantize_embedding(raw)

        # For testing, return mock data
        return None

    except Exception as e:
        print(f"Error sampling ({lat}, {lon}): {e}")
        return None


def sample_batch_from_cog(
    points: pd.DataFrame,
    cog_path: str,
    year: int
) -> pd.DataFrame:
    """
    Sample multiple points from a single COG file efficiently.

    This is the key optimization - open the file once, read all pixels.

    Args:
        points: DataFrame with 'latitude', 'longitude' columns
        cog_path: Path to COG file
        year: Year for this COG

    Returns:
        DataFrame with original columns + embedding columns (A00-A63)
    """
    if rasterio is None:
        raise RuntimeError("rasterio not installed")

    results = []

    with rasterio.open(cog_path) as src:
        # Create coordinate transformer
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

        for idx, row in points.iterrows():
            try:
                # Transform to pixel coordinates
                x, y = transformer.transform(row['longitude'], row['latitude'])
                px_row, px_col = src.index(x, y)

                # Check bounds
                if 0 <= px_row < src.height and 0 <= px_col < src.width:
                    # Read single pixel (all 64 bands)
                    window = rasterio.windows.Window(px_col, px_row, 1, 1)
                    data = src.read(window=window)
                    raw = data.flatten()

                    # Check for masked pixel (-128)
                    if raw[0] == -128:
                        embedding = np.full(64, np.nan)
                    else:
                        embedding = dequantize_embedding(raw)
                else:
                    embedding = np.full(64, np.nan)

                # Build result row
                result = {
                    'taxon_id': row.get('taxon_id', ''),
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'emb_year': year,
                    'orig_year': row.get('year', year),
                }
                for i, val in enumerate(embedding):
                    result[f'A{i:02d}'] = val

                results.append(result)

            except Exception as e:
                print(f"Error at ({row['latitude']}, {row['longitude']}): {e}")

    return pd.DataFrame(results)


def group_points_by_cog(
    points: pd.DataFrame,
    year: int
) -> Dict[str, pd.DataFrame]:
    """
    Group points by which COG file they belong to.

    This enables efficient batch reading - open each COG once.

    Args:
        points: DataFrame with latitude, longitude columns
        year: Year to process

    Returns:
        Dict mapping COG path -> DataFrame of points in that COG
    """
    points = points.copy()

    # Add UTM zone info
    points['utm_zone'] = points.apply(
        lambda r: get_utm_zone(r['longitude'], r['latitude'])[0],
        axis=1
    )
    points['hemisphere'] = points.apply(
        lambda r: get_utm_zone(r['longitude'], r['latitude'])[1],
        axis=1
    )

    # Group by zone/hemisphere (actual implementation would use tile index)
    grouped = {}
    for (zone, hem), group in points.groupby(['utm_zone', 'hemisphere']):
        # Placeholder path - actual implementation needs index lookup
        cog_key = f"{year}/{zone:02d}{hem}"
        grouped[cog_key] = group

    return grouped


def process_year_gcs(
    input_file: str,
    year: int,
    output_file: str,
    max_workers: int = 4
) -> int:
    """
    Process all points for a year using GCS COGs.

    Args:
        input_file: Parquet file with points to process
        year: Year to sample (2017-2024)
        output_file: Output parquet file
        max_workers: Number of parallel workers

    Returns:
        Number of points processed
    """
    print(f"\n{'='*60}")
    print(f"PROCESSING YEAR {year} FROM GCS COGS")
    print(f"{'='*60}")

    # Load input
    df = pd.read_parquet(input_file)
    df_year = df[df['year'] == year] if 'year' in df.columns else df

    print(f"Input points: {len(df_year):,}")

    # Group by COG file
    grouped = group_points_by_cog(df_year, year)
    print(f"COG files to read: {len(grouped)}")

    # Process each COG
    all_results = []
    for cog_key, points in grouped.items():
        print(f"  Processing {cog_key}: {len(points)} points...")
        # Actual implementation would call sample_batch_from_cog here
        # results = sample_batch_from_cog(points, cog_path, year)
        # all_results.append(results)

    # Combine and save
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df.to_parquet(output_file, index=False)
        print(f"\nSaved {len(final_df):,} embeddings to {output_file}")
        return len(final_df)

    return 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Sample AlphaEarth from GCS COGs')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--year', type=int, help='Year to process (2017-2024)')
    parser.add_argument('--input', type=str, help='Input parquet file')
    parser.add_argument('--output', type=str, help='Output parquet file')
    parser.add_argument('--workers', type=int, default=4, help='Parallel workers')

    args = parser.parse_args()

    if not check_dependencies():
        return

    if args.test:
        print("\n" + "="*60)
        print("GCS COG SAMPLING TEST")
        print("="*60)

        # Test with a few sample coordinates
        test_points = [
            (32.206283, -81.165253, 2017),  # USA
            (-34.769728, 172.975071, 2017),  # New Zealand
            (48.587380, -1.184676, 2020),    # France
        ]

        for lat, lon, year in test_points:
            zone, hem = get_utm_zone(lon, lat)
            print(f"\n({lat:.4f}, {lon:.4f}) year={year}")
            print(f"  UTM Zone: {zone}{hem}")
            print(f"  COG path: {GCS_BUCKET}/{year}/{zone:02d}{hem}/")

        print("\n" + "="*60)
        print("HOW TO USE THIS APPROACH")
        print("="*60)
        print("""
1. Install dependencies:
   pip install rasterio pyproj gcsfs pandas numpy

2. Set up GCS authentication:
   gcloud auth application-default login

3. Download the index file to find actual COG paths:
   gsutil cp gs://alphaearth_foundations/index.parquet .

4. Key insight: COGs support HTTP range requests
   - You DON'T download entire files
   - rasterio fetches only the bytes for your pixels
   - Cost is egress only (~$0.12/GB vs $0.40/EECU-hour)

5. Optimal strategy:
   - Group points by COG file (UTM zone + tile)
   - Open each COG once, read all points
   - This minimizes network round-trips
""")
        return

    if args.year and args.input and args.output:
        process_year_gcs(args.input, args.year, args.output, args.workers)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
