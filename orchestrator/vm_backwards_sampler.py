#!/usr/bin/env python3
"""
VM Backwards COG Sampler - Meet in the Middle
==============================================

Runs on GCP VM to sample AlphaEarth embeddings directly from COGs,
working backwards from 2024 while GEE tasks work forward.

Key differences from gcp_vm_sampler_v3:
- Writes to alphaearth_embeddings_v4 table
- Queries BigQuery to find what's NOT yet processed
- Works backwards (2024 -> 2017) to meet GEE in the middle
- Skips Hansen/SRTM (those will be backfilled or aren't critical)

Usage (on VM):
    python3 vm_backwards_sampler.py --year 2024 --workers 32
    python3 vm_backwards_sampler.py --backwards --workers 32

Author: Treekipedia Team
Created: January 2026
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import time
import warnings

warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ID = "treekipedia-479918"
BIGQUERY_DATASET = "species_data"
BIGQUERY_TABLE = "alphaearth_embeddings_v4"  # Same as GEE exports

YEARS_AVAILABLE = list(range(2017, 2025))
NUM_BANDS = 64
COORD_DECIMALS = 4  # Match GEE deduplication precision

# Optimization parameters
MAX_BBOX_SIZE = 2000
UPLOAD_BATCH_SIZE = 50000

# Paths
SCRIPT_DIR = Path(__file__).parent
INDEX_FILE = SCRIPT_DIR / "aef_index.parquet"

POSSIBLE_OCC_PATHS = [
    SCRIPT_DIR / "occurrences.parquet",
    Path("/home/data/occurrences.parquet"),
    Path.home() / "data" / "occurrences.parquet",
]

# =============================================================================
# IMPORTS
# =============================================================================

try:
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio pyproj")
    sys.exit(1)

try:
    from rtree import index as rtree_index
    HAS_RTREE = True
except ImportError:
    HAS_RTREE = False
    print("Warning: rtree not installed, using slower matching")

try:
    import pandas_gbq
    from google.cloud import bigquery
    HAS_BIGQUERY = True
except ImportError:
    HAS_BIGQUERY = False
    print("Warning: BigQuery not available")


# =============================================================================
# SPATIAL INDEX
# =============================================================================

class COGSpatialIndex:
    """R-tree spatial index for fast point-to-COG lookup."""

    def __init__(self, index_df: pd.DataFrame):
        self.index_df = index_df.reset_index(drop=True)
        self.paths = self.index_df['path'].values
        self.rtree = None

        if HAS_RTREE:
            self._build_rtree()
        else:
            self.west = self.index_df['wgs84_west'].values
            self.east = self.index_df['wgs84_east'].values
            self.south = self.index_df['wgs84_south'].values
            self.north = self.index_df['wgs84_north'].values

    def _build_rtree(self):
        p = rtree_index.Property()
        p.dimension = 2
        self.rtree = rtree_index.Index(properties=p)

        for idx, (_, row) in enumerate(self.index_df.iterrows()):
            bbox = (row['wgs84_west'], row['wgs84_south'],
                    row['wgs84_east'], row['wgs84_north'])
            self.rtree.insert(idx, bbox)

    def find_cog(self, lon: float, lat: float) -> Optional[str]:
        if self.rtree:
            candidates = list(self.rtree.intersection((lon, lat, lon, lat)))
            if candidates:
                return self.paths[candidates[0]]
            return None
        else:
            mask = ((self.west <= lon) & (self.east >= lon) &
                    (self.south <= lat) & (self.north >= lat))
            if mask.any():
                return self.paths[mask][0]
            return None


# =============================================================================
# BIGQUERY FUNCTIONS
# =============================================================================

def get_already_processed(year: int) -> set:
    """Get set of already processed pixel-years from BigQuery."""
    if not HAS_BIGQUERY:
        return set()

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT DISTINCT
        CONCAT(
            CAST(ROUND(latitude, {COORD_DECIMALS}) AS STRING), '_',
            CAST(ROUND(longitude, {COORD_DECIMALS}) AS STRING)
        ) as pixel_key
    FROM `{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
    WHERE emb_year = {year}
    """

    print(f"  Querying BigQuery for already-processed pixels (year {year})...")
    result = client.query(query).result()

    processed = {row.pixel_key for row in result}
    print(f"  Found {len(processed):,} already processed")
    return processed


def upload_to_bigquery(df: pd.DataFrame) -> bool:
    """Upload DataFrame to BigQuery v4 table."""
    if not HAS_BIGQUERY or df.empty:
        return False

    table_id = f"{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

    try:
        pandas_gbq.to_gbq(df, table_id, project_id=PROJECT_ID,
                         if_exists='append', progress_bar=False)
        print(f"  Uploaded {len(df):,} rows to BigQuery")
        return True
    except Exception as e:
        print(f"  BigQuery upload failed: {e}")
        return False


# =============================================================================
# COG SAMPLING
# =============================================================================

def dequantize_embedding(raw_values: np.ndarray) -> np.ndarray:
    """Convert int8 COG values to float embeddings."""
    raw = raw_values.astype(np.float64)
    normalized = raw / 127.5
    return np.sign(raw) * (normalized ** 2)


def sample_cog_batch(cog_path: str, points: List[Dict], year: int) -> List[Dict]:
    """Sample multiple points from a COG with bbox optimization."""
    results = []

    if cog_path.startswith('gs://'):
        full_path = '/vsigs/' + cog_path[5:]
    else:
        full_path = f"/vsigs/{cog_path}"

    try:
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
            GS_USER_PROJECT=PROJECT_ID,
            GDAL_HTTP_TIMEOUT=120,
            GDAL_HTTP_MAX_RETRY=3,
            VSI_CACHE=True,
        ):
            with rasterio.open(full_path) as src:
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

                # Convert to pixel coordinates
                pixel_coords = []
                for pt in points:
                    try:
                        x, y = transformer.transform(pt['lon'], pt['lat'])
                        row, col = src.index(x, y)
                        if 0 <= row < src.height and 0 <= col < src.width:
                            pixel_coords.append((row, col, pt))
                    except Exception:
                        continue

                if not pixel_coords:
                    return results

                # Bounding box read
                rows = [p[0] for p in pixel_coords]
                cols = [p[1] for p in pixel_coords]
                min_row, max_row = min(rows), max(rows)
                min_col, max_col = min(cols), max(cols)
                height = int(max_row - min_row + 1)
                width = int(max_col - min_col + 1)

                if height <= MAX_BBOX_SIZE and width <= MAX_BBOX_SIZE:
                    try:
                        window = Window(int(min_col), int(min_row), width, height)
                        batch_data = src.read(window=window)

                        for row, col, pt in pixel_coords:
                            local_row = row - min_row
                            local_col = col - min_col
                            raw = batch_data[:, local_row, local_col]

                            if raw[0] == -128:  # Masked
                                continue

                            embedding = dequantize_embedding(raw)

                            result = {
                                'taxon_id': pt.get('taxon_id', ''),
                                'latitude': pt['lat'],
                                'longitude': pt['lon'],
                                'emb_year': year,
                                'orig_year': pt.get('year', year),
                            }
                            for i, val in enumerate(embedding):
                                result[f'A{i:02d}'] = float(val)

                            results.append(result)

                        return results
                    except Exception:
                        pass  # Fall through to individual

                # Individual reads
                for row, col, pt in pixel_coords:
                    try:
                        window = Window(int(col), int(row), 1, 1)
                        data = src.read(window=window)
                        raw = data.flatten()

                        if raw[0] == -128:
                            continue

                        embedding = dequantize_embedding(raw)

                        result = {
                            'taxon_id': pt.get('taxon_id', ''),
                            'latitude': pt['lat'],
                            'longitude': pt['lon'],
                            'emb_year': year,
                            'orig_year': pt.get('year', year),
                        }
                        for i, val in enumerate(embedding):
                            result[f'A{i:02d}'] = float(val)

                        results.append(result)
                    except Exception:
                        continue

    except Exception as e:
        if not hasattr(sample_cog_batch, '_logged_error'):
            sample_cog_batch._logged_error = True
            print(f"  COG error: {e}")

    return results


def process_cog_worker(args):
    """Worker function for parallel processing."""
    cog_path, points, year = args
    return sample_cog_batch(cog_path, points, year)


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def find_occurrences_file() -> Path:
    for path in POSSIBLE_OCC_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError("Occurrences file not found")


def load_cog_index() -> pd.DataFrame:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"Index file not found: {INDEX_FILE}")
    return pd.read_parquet(INDEX_FILE)


def process_year(year: int, workers: int = 32, limit: int = None) -> int:
    """Process a year, skipping already-processed pixels."""

    print(f"\n{'='*60}")
    print(f"PROCESSING YEAR {year} (VM Backwards Sampler)")
    print(f"{'='*60}")

    # Get already processed
    already_processed = get_already_processed(year)

    # Load COG index
    print("Loading COG index...")
    full_index = load_cog_index()
    year_index = full_index[full_index['year'] == year][
        ['path', 'wgs84_west', 'wgs84_east', 'wgs84_south', 'wgs84_north']
    ].copy()
    print(f"  COG files for {year}: {len(year_index):,}")

    # Build spatial index
    print("Building spatial index...")
    spatial_index = COGSpatialIndex(year_index)

    # Load occurrences
    print("Loading occurrences...")
    occ_file = find_occurrences_file()

    columns_needed = ['decimalLatitude', 'decimalLongitude', 'taxon_id', 'year']
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(occ_file, columns=columns_needed,
                             filters=[('year', '=', year)])
        year_df = table.to_pandas()
        del table
    except Exception:
        full_df = pd.read_parquet(occ_file, columns=columns_needed)
        year_df = full_df[full_df['year'] == year].copy()
        del full_df

    print(f"  Raw occurrences for {year}: {len(year_df):,}")

    # Deduplicate to 4 decimal places (match GEE)
    year_df['lat_round'] = year_df['decimalLatitude'].round(COORD_DECIMALS)
    year_df['lon_round'] = year_df['decimalLongitude'].round(COORD_DECIMALS)
    year_df['pixel_key'] = (year_df['lat_round'].astype(str) + '_' +
                           year_df['lon_round'].astype(str))

    # Remove already processed
    year_df = year_df[~year_df['pixel_key'].isin(already_processed)]

    # Dedupe keeping first
    year_df = year_df.drop_duplicates(subset=['pixel_key'], keep='first')

    print(f"  Unique unprocessed pixels: {len(year_df):,}")

    if len(year_df) == 0:
        print("  Nothing to process!")
        return 0

    if limit:
        year_df = year_df.head(limit)
        print(f"  Limited to: {len(year_df):,}")

    # Group by COG (vectorized for speed)
    print("Grouping points by COG...")
    grouped = defaultdict(list)
    unmatched = 0

    # Extract numpy arrays for fast iteration
    lats = year_df['lat_round'].values
    lons = year_df['lon_round'].values
    taxon_ids = year_df['taxon_id'].values
    years_arr = year_df['year'].values

    for i in range(len(lats)):
        cog_path = spatial_index.find_cog(lons[i], lats[i])
        if cog_path:
            grouped[cog_path].append({
                'lat': float(lats[i]),
                'lon': float(lons[i]),
                'taxon_id': str(taxon_ids[i]) if pd.notna(taxon_ids[i]) else '',
                'year': int(years_arr[i])
            })
        else:
            unmatched += 1

        # Progress every 10K points
        if i > 0 and i % 10000 == 0:
            print(f"    Grouped {i:,}/{len(lats):,} points...")

    if unmatched > 0:
        print(f"  Warning: {unmatched} points outside COG coverage")

    total_cogs = len(grouped)
    total_points = sum(len(pts) for pts in grouped.values())
    print(f"  COG files to read: {total_cogs:,}")
    print(f"  Points to sample: {total_points:,}")

    # Sort by point count (dense COGs first)
    sorted_cogs = sorted(grouped.items(), key=lambda x: -len(x[1]))

    # Process
    print(f"\nProcessing with {workers} workers...")

    all_results = []
    total_uploaded = 0
    processed = 0
    start_time = time.time()

    work_items = [(path, pts, year) for path, pts in sorted_cogs]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_cog_worker, item): item[0]
                  for item in work_items}

        for future in as_completed(futures):
            processed += 1

            try:
                results = future.result()
                all_results.extend(results)
            except Exception:
                pass

            # Progress
            if processed % 100 == 0:
                elapsed = time.time() - start_time
                pts_done = len(all_results) + total_uploaded
                rate = pts_done / elapsed if elapsed > 0 else 0
                cog_rate = processed / elapsed if elapsed > 0 else 0
                eta = (total_cogs - processed) / cog_rate if cog_rate > 0 else 0
                print(f"  {processed}/{total_cogs} COGs ({100*processed/total_cogs:.1f}%), "
                      f"{pts_done:,} pts, {rate:.1f} pts/sec, ETA: {eta/60:.1f}min")

            # Batch upload
            if len(all_results) >= UPLOAD_BATCH_SIZE:
                df = pd.DataFrame(all_results)
                if upload_to_bigquery(df):
                    total_uploaded += len(all_results)
                all_results = []

    # Final upload
    if all_results:
        df = pd.DataFrame(all_results)
        if upload_to_bigquery(df):
            total_uploaded += len(all_results)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"COMPLETED YEAR {year}")
    print(f"{'='*60}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Embeddings: {total_uploaded:,}")
    print(f"  Rate: {total_uploaded/elapsed:.1f} pts/sec")

    return total_uploaded


def main():
    parser = argparse.ArgumentParser(description='VM Backwards COG Sampler')
    parser.add_argument('--year', type=int, help='Process specific year')
    parser.add_argument('--backwards', action='store_true', help='Process all years backwards (2024->2017)')
    parser.add_argument('--workers', type=int, default=32, help='Workers')
    parser.add_argument('--limit', type=int, help='Limit points per year')
    parser.add_argument('--test', action='store_true', help='Test mode (1000 pts)')

    args = parser.parse_args()

    if args.test:
        args.limit = 1000
        if not args.year:
            args.year = 2024

    if args.year:
        years = [args.year]
    elif args.backwards:
        years = list(reversed(YEARS_AVAILABLE))  # 2024, 2023, ..., 2017
    else:
        parser.print_help()
        return

    print("="*60)
    print("VM BACKWARDS COG SAMPLER")
    print("="*60)
    print(f"Years: {years}")
    print(f"Workers: {args.workers}")
    print(f"R-tree: {'Yes' if HAS_RTREE else 'No'}")
    print(f"BigQuery: {'Yes' if HAS_BIGQUERY else 'No'}")

    total = 0
    start = time.time()

    for year in years:
        try:
            total += process_year(year, args.workers, args.limit)
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - start
    print(f"\nTOTAL: {total:,} embeddings in {elapsed/60:.1f} min ({total/elapsed:.1f} pts/sec)")


if __name__ == '__main__':
    main()
