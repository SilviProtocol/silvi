#!/usr/bin/env python3
"""
GCP VM AlphaEarth COG Sampler
=============================

Optimized for running on a GCP VM where GCS access is fast and free (no egress).
Saves results directly to BigQuery.

Usage on GCP VM:
    python3 gcp_vm_sampler.py --year 2017
    python3 gcp_vm_sampler.py --all --workers 16

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

warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

GCS_BUCKET = "gs://alphaearth_foundations"
GCS_BASE_PATH = "satellite_embedding/v1/annual"
PROJECT_ID = "treekipedia-479918"
BIGQUERY_DATASET = "species_data"
BIGQUERY_TABLE = "alphaearth_embeddings"

YEARS_AVAILABLE = list(range(2017, 2025))
NUM_BANDS = 64

# Paths - check multiple locations
SCRIPT_DIR = Path(__file__).parent
INDEX_FILE = SCRIPT_DIR / "aef_index.parquet"
OUTPUT_DIR = SCRIPT_DIR / "gcs_embeddings"

# Occurrences file - try multiple locations
POSSIBLE_OCC_PATHS = [
    SCRIPT_DIR / "occurrences.parquet",
    SCRIPT_DIR / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet",
    SCRIPT_DIR.parent / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet",
    Path.home() / "data" / "occurrences.parquet",
    Path("/home/data/occurrences.parquet"),
]

# =============================================================================
# IMPORTS
# =============================================================================

try:
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer
    import geopandas as gpd
    from shapely.geometry import box, Point
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio pyproj geopandas shapely pandas numpy pandas-gbq google-cloud-bigquery")
    sys.exit(1)

# BigQuery imports
try:
    import pandas_gbq
    from google.cloud import bigquery
    HAS_BIGQUERY = True
except ImportError:
    HAS_BIGQUERY = False
    print("Warning: BigQuery libraries not installed. Will save to parquet only.")
    print("Install with: pip install pandas-gbq google-cloud-bigquery")


# =============================================================================
# BIGQUERY FUNCTIONS
# =============================================================================

def create_bigquery_table_if_needed():
    """Create the BigQuery table if it doesn't exist."""
    if not HAS_BIGQUERY:
        return

    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

    # Define schema
    schema = [
        bigquery.SchemaField("taxon_id", "STRING"),
        bigquery.SchemaField("latitude", "FLOAT64"),
        bigquery.SchemaField("longitude", "FLOAT64"),
        bigquery.SchemaField("emb_year", "INT64"),
        bigquery.SchemaField("orig_year", "INT64"),
    ]
    # Add 64 embedding columns
    for i in range(64):
        schema.append(bigquery.SchemaField(f"A{i:02d}", "FLOAT64"))

    table = bigquery.Table(table_id, schema=schema)

    try:
        client.get_table(table_id)
        print(f"  BigQuery table exists: {table_id}")
    except Exception:
        table = client.create_table(table)
        print(f"  Created BigQuery table: {table_id}")


def upload_to_bigquery(df: pd.DataFrame, year: int = None):
    """Upload DataFrame to BigQuery."""
    if not HAS_BIGQUERY:
        print("  BigQuery not available, skipping upload")
        return False

    if df.empty:
        print("  No data to upload")
        return False

    table_id = f"{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

    try:
        pandas_gbq.to_gbq(
            df,
            table_id,
            project_id=PROJECT_ID,
            if_exists='append',
            progress_bar=False
        )
        year_str = f" for year {year}" if year else ""
        print(f"  Uploaded {len(df):,} rows to BigQuery{year_str}")
        return True
    except Exception as e:
        print(f"  BigQuery upload failed: {e}")
        return False


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def find_occurrences_file() -> Path:
    """Find the occurrences parquet file."""
    for path in POSSIBLE_OCC_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(f"Occurrences file not found. Tried: {POSSIBLE_OCC_PATHS}")


def load_cog_index() -> pd.DataFrame:
    """Load the COG index file."""
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"Index file not found: {INDEX_FILE}")
    return pd.read_parquet(INDEX_FILE)


def dequantize_embedding(raw_values: np.ndarray) -> np.ndarray:
    """Convert int8 COG values to float embeddings."""
    raw = raw_values.astype(np.float64)
    normalized = raw / 127.5
    embedding = np.sign(raw) * (normalized ** 2)
    return embedding


def sample_batch_from_cog(cog_path: str, points: List[Dict], year: int) -> List[Dict]:
    """
    Sample multiple points from a single COG file.
    """
    results = []
    # Convert gs:// path to /vsigs/ path for GDAL
    if cog_path.startswith('gs://'):
        full_path = '/vsigs/' + cog_path[5:]  # Remove 'gs://' and prepend '/vsigs/'
    else:
        full_path = f"/vsigs/{cog_path}"

    try:
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
            GS_USER_PROJECT=PROJECT_ID,
            GDAL_HTTP_TIMEOUT=60
        ):
            with rasterio.open(full_path) as src:
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

                for pt in points:
                    try:
                        lat, lon = pt['lat'], pt['lon']
                        x, y = transformer.transform(lon, lat)
                        row, col = src.index(x, y)

                        if 0 <= row < src.height and 0 <= col < src.width:
                            window = Window(col, row, 1, 1)
                            data = src.read(window=window)
                            raw = data.flatten()

                            if raw[0] == -128:  # Masked pixel
                                continue

                            embedding = dequantize_embedding(raw)

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
                    except Exception:
                        pass

    except Exception as e:
        pass  # Silent failure for individual COGs

    return results


def process_cog_batch(args):
    """Process a single COG - for parallel execution."""
    cog_path, points, year = args
    return sample_batch_from_cog(cog_path, points, year)


def group_points_by_cog(points_df: pd.DataFrame, year: int, index_df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """Group points by which COG they belong to."""
    year_index = index_df[index_df['year'] == year].copy()
    grouped = defaultdict(list)
    unmatched = 0

    for _, row in points_df.iterrows():
        lat = row['decimalLatitude']
        lon = row['decimalLongitude']

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
        print(f"  Warning: {unmatched} points outside COG coverage")

    return dict(grouped)


# NOTE: No deduplication needed with COG approach!
# Cost is per-COG-open, not per-point. Opening a COG once and reading
# 100 points is nearly the same cost as reading 1 point.
# So we process ALL occurrences, not deduplicated ones.


def process_year(year: int, workers: int = 8, limit: int = None,
                 upload_interval: int = 50000, save_local: bool = False) -> int:
    """
    Process all occurrences for a year with parallel COG reading.
    Uploads to BigQuery in batches.
    """
    print(f"\n{'='*60}")
    print(f"PROCESSING YEAR {year}")
    print(f"{'='*60}")

    # Ensure BigQuery table exists
    create_bigquery_table_if_needed()

    # Load index
    print("Loading COG index...")
    index_df = load_cog_index()
    year_cogs = len(index_df[index_df['year'] == year])
    print(f"  COG files for {year}: {year_cogs:,}")

    # Load occurrences
    print("Loading occurrences...")
    occ_file = find_occurrences_file()
    print(f"  From: {occ_file}")

    full_df = pd.read_parquet(occ_file)
    year_df = full_df[full_df['year'] == year].copy()
    print(f"  Occurrences for {year}: {len(year_df):,}")

    if len(year_df) == 0:
        print(f"  No data for year {year}")
        return 0

    # No deduplication - process all points (COG cost is per-open, not per-point)

    if limit:
        year_df = year_df.head(limit)
        print(f"  Limited to: {len(year_df):,}")

    # Group by COG
    print("Grouping points by COG file...")
    grouped = group_points_by_cog(year_df, year, index_df)
    total_cogs = len(grouped)
    total_points = sum(len(pts) for pts in grouped.values())
    print(f"  COG files to read: {total_cogs:,}")
    print(f"  Points to sample: {total_points:,}")
    print(f"  Avg points per COG: {total_points/total_cogs:.1f}")

    # Process with parallel workers
    print(f"\nProcessing with {workers} parallel workers...")

    all_results = []
    total_uploaded = 0
    processed_cogs = 0
    start_time = time.time()

    work_items = [(cog_path, points, year) for cog_path, points in grouped.items()]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_cog_batch, item): item[0] for item in work_items}

        for future in as_completed(futures):
            cog_path = futures[future]
            processed_cogs += 1

            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                pass

            # Progress update
            if processed_cogs % 100 == 0:
                elapsed = time.time() - start_time
                rate = processed_cogs / elapsed
                eta = (total_cogs - processed_cogs) / rate if rate > 0 else 0
                print(f"  Progress: {processed_cogs}/{total_cogs} COGs ({100*processed_cogs/total_cogs:.1f}%), "
                      f"{len(all_results) + total_uploaded:,} embeddings, {rate:.1f} COGs/sec, ETA: {eta/60:.1f}min")

            # Periodic BigQuery upload
            if len(all_results) >= upload_interval:
                batch_df = pd.DataFrame(all_results)
                if upload_to_bigquery(batch_df, year):
                    total_uploaded += len(all_results)
                    all_results = []

    # Upload remaining results
    if all_results:
        batch_df = pd.DataFrame(all_results)
        if upload_to_bigquery(batch_df, year):
            total_uploaded += len(all_results)

        # Optionally save local copy
        if save_local:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            local_file = OUTPUT_DIR / f"embeddings_{year}.parquet"
            batch_df.to_parquet(local_file, index=False)
            print(f"  Local backup: {local_file}")

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"COMPLETED YEAR {year}")
    print(f"{'='*60}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  COGs processed: {processed_cogs:,}")
    print(f"  Embeddings uploaded: {total_uploaded:,}")
    print(f"  Rate: {total_uploaded/elapsed:.0f} points/sec")

    return total_uploaded


def main():
    parser = argparse.ArgumentParser(description='GCP VM AlphaEarth COG Sampler')
    parser.add_argument('--year', type=int, help='Process specific year (2017-2024)')
    parser.add_argument('--all', action='store_true', help='Process all years')
    parser.add_argument('--workers', type=int, default=8, help='Parallel workers (default: 8)')
    parser.add_argument('--limit', type=int, help='Limit points per year (for testing)')
    parser.add_argument('--test', action='store_true', help='Test mode (1000 points)')
    parser.add_argument('--save-local', action='store_true', help='Also save parquet files locally')
    parser.add_argument('--upload-interval', type=int, default=50000, help='Rows per BigQuery upload batch')

    args = parser.parse_args()

    if args.test:
        args.limit = 1000
        args.year = 2017

    if args.year:
        years = [args.year]
    elif args.all:
        years = YEARS_AVAILABLE
    else:
        parser.print_help()
        return

    print("="*60)
    print("GCP VM ALPHAEARTH COG SAMPLER")
    print("="*60)
    print(f"Project: {PROJECT_ID}")
    print(f"BigQuery: {BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print(f"Years: {years}")
    print(f"Workers: {args.workers}")
    if args.limit:
        print(f"Limit: {args.limit} points/year")
    print()

    total_embeddings = 0
    total_start = time.time()

    for year in years:
        try:
            count = process_year(
                year,
                workers=args.workers,
                limit=args.limit,
                upload_interval=args.upload_interval,
                save_local=args.save_local
            )
            total_embeddings += count
        except Exception as e:
            print(f"Error processing year {year}: {e}")
            import traceback
            traceback.print_exc()

    total_elapsed = time.time() - total_start

    print("\n" + "="*60)
    print("ALL PROCESSING COMPLETE")
    print("="*60)
    print(f"Total time: {total_elapsed/60:.1f} minutes")
    print(f"Total embeddings: {total_embeddings:,}")
    print(f"BigQuery table: {PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")


if __name__ == '__main__':
    main()
