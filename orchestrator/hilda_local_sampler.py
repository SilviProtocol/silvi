#!/usr/bin/env python3
"""
HILDA+ Local Sampler for SINR v3
=================================
Samples HILDA+ v2.0 land use/cover classes from local GeoTIFFs
at observation_year and emb_year for all training points.

Reads from:
  - species_data.sinr_v3_features_new_gbif
  - species_data.sinr_v3_features_backfill

Writes to (CREATE/APPEND only, NEVER deletes):
  - species_data.sinr_v3_hilda_lulc

HILDA+ v2.0 classes:
  11=Urban, 22=Annual crops, 23=Tree crops, 24=Agroforestry,
  33=Pasture/rangeland, 40=Forest(unknown), 41=Forest(evergreen needle),
  42=Forest(evergreen broad), 43=Forest(deciduous needle),
  44=Forest(deciduous broad), 45=Forest(mixed), 55=Grass/shrub,
  66=Sparse/no veg, 77=Water, 99=Ocean/NoData, 0=NoData

Usage:
  python3 orchestrator/hilda_local_sampler.py
  python3 orchestrator/hilda_local_sampler.py --source new_gbif
  python3 orchestrator/hilda_local_sampler.py --source backfill
  python3 orchestrator/hilda_local_sampler.py --source all --resume
"""

import argparse
import os
import sys
import time
import numpy as np
import rasterio
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_OUTPUT_TABLE = 'sinr_v3_hilda_lulc'

HILDA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'hilda_plus', 'hildap_vGLOB-2.0_geotiff_wgs84', 'states'
)

# HILDA+ covers 1960-2020. Clamp years outside this range.
HILDA_MIN_YEAR = 1960
HILDA_MAX_YEAR = 2020

# BQ upload batch size (rows per insert)
BQ_BATCH_SIZE = 50000

# =============================================================================
# LOGGING
# =============================================================================

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

# =============================================================================
# RASTER CACHE
# =============================================================================

class HildaRasterCache:
    """Cache HILDA+ rasters in memory for fast repeated sampling.
    
    Each raster is ~648 MB (36000x18000 uint8). We keep a bounded cache
    to avoid running out of RAM. With 18 GB Mac, we can hold ~10-12 rasters.
    """
    
    def __init__(self, hilda_dir, max_cache_size=10):
        self.hilda_dir = hilda_dir
        self.max_cache_size = max_cache_size
        self.cache = {}  # year -> (data_array, transform)
        self.access_order = []  # LRU tracking
        
        # Verify directory exists
        if not os.path.isdir(hilda_dir):
            raise FileNotFoundError(f"HILDA+ directory not found: {hilda_dir}")
        
        # Check which years are available
        self.available_years = set()
        for f in os.listdir(hilda_dir):
            if f.startswith('hilda_plus_states_') and f.endswith('.tif'):
                year = int(f.split('_')[3])
                self.available_years.add(year)
        
        log(f"HILDA+ rasters found: {len(self.available_years)} years "
            f"({min(self.available_years)}-{max(self.available_years)})")
    
    def _tif_path(self, year):
        return os.path.join(
            self.hilda_dir,
            f'hilda_plus_states_{year}_GLOB-v2_wgs84.tif'
        )
    
    def _load_raster(self, year):
        """Load a raster into memory."""
        # Evict LRU if cache is full
        while len(self.cache) >= self.max_cache_size:
            evict_year = self.access_order.pop(0)
            if evict_year in self.cache:
                del self.cache[evict_year]
                log(f"  Evicted year {evict_year} from cache")
        
        path = self._tif_path(year)
        with rasterio.open(path) as src:
            data = src.read(1)  # uint8 array
            transform = src.transform
        
        self.cache[year] = (data, transform)
        self.access_order.append(year)
        return data, transform
    
    def get_raster(self, year):
        """Get raster data for a year, loading from disk if needed."""
        # Clamp to available range
        year = max(HILDA_MIN_YEAR, min(HILDA_MAX_YEAR, year))
        
        if year not in self.available_years:
            return None, None
        
        if year in self.cache:
            # Move to end of LRU
            if year in self.access_order:
                self.access_order.remove(year)
            self.access_order.append(year)
            return self.cache[year]
        
        return self._load_raster(year)
    
    def sample_points(self, lats, lons, year):
        """Sample HILDA+ values at arrays of lat/lon for a given year.
        
        Returns numpy array of uint8 class values.
        Returns -9999 for points outside HILDA range or with no data.
        """
        result = np.full(len(lats), -9999, dtype=np.int32)
        
        if year < HILDA_MIN_YEAR or year > HILDA_MAX_YEAR:
            return result
        
        data, transform = self.get_raster(year)
        if data is None:
            return result
        
        # Convert lat/lon to pixel coordinates
        # transform: (x_origin, x_scale, 0, y_origin, 0, y_scale)
        # For WGS84: x=lon, y=lat
        cols = ((lons - transform.c) / transform.a).astype(np.int32)
        rows = ((lats - transform.f) / transform.e).astype(np.int32)
        
        # Mask out-of-bounds
        valid = (rows >= 0) & (rows < data.shape[0]) & \
                (cols >= 0) & (cols < data.shape[1])
        
        result[valid] = data[rows[valid], cols[valid]].astype(np.int32)
        
        # Map HILDA NoData (0) to our sentinel
        result[result == 0] = -9999
        
        return result

# =============================================================================
# DATA LOADING
# =============================================================================

def load_points_from_bq(source):
    """Load unique (lat, lon, observation_year, emb_year) from BQ.
    
    NEVER modifies or deletes any existing tables.
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    
    tables = []
    if source in ('new_gbif', 'all'):
        tables.append('sinr_v3_features_new_gbif')
    if source in ('backfill', 'all'):
        tables.append('sinr_v3_features_backfill')
    
    all_dfs = []
    for table in tables:
        log(f"Loading points from {table}...")
        query = f"""
        SELECT DISTINCT
            ROUND(latitude, 4) as lat,
            ROUND(longitude, 4) as lon,
            CAST(observation_year AS INT64) as observation_year,
            CAST(emb_year AS INT64) as emb_year
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{table}`
        """
        df = client.query(query).to_dataframe()
        log(f"  Loaded {len(df):,} rows from {table}")
        all_dfs.append(df)
    
    import pandas as pd
    combined = pd.concat(all_dfs, ignore_index=True)
    
    # Deduplicate on (lat, lon, observation_year, emb_year)
    before = len(combined)
    combined = combined.drop_duplicates(subset=['lat', 'lon', 'observation_year', 'emb_year'])
    log(f"Combined: {before:,} -> {len(combined):,} unique pixel-year combos")
    
    return combined


def load_completed_keys():
    """Load already-completed keys from the output table for resume mode.
    
    NEVER modifies or deletes the output table.
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    
    full_table = f'{BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}'
    
    try:
        query = f"""
        SELECT DISTINCT
            CONCAT(
                CAST(latitude AS STRING), '|',
                CAST(longitude AS STRING), '|',
                CAST(observation_year AS STRING)
            ) as key
        FROM `{full_table}`
        """
        df = client.query(query).to_dataframe()
        keys = set(df['key'].values)
        log(f"Found {len(keys):,} completed keys in {BQ_OUTPUT_TABLE}")
        return keys
    except Exception as e:
        log(f"No completed keys found (table may not exist yet): {e}")
        return set()

# =============================================================================
# BQ WRITING (APPEND ONLY)
# =============================================================================

def write_batch_to_bq(rows, client, table_ref):
    """Write a batch of rows to BQ. APPEND ONLY, never overwrites.
    
    rows: list of dicts with keys matching BQ schema
    """
    import pandas as pd
    from google.cloud.bigquery import LoadJobConfig, WriteDisposition
    
    df = pd.DataFrame(rows)
    
    job_config = LoadJobConfig(
        write_disposition=WriteDisposition.WRITE_APPEND,  # APPEND ONLY
    )
    
    job = client.load_table_from_dataframe(
        df, table_ref, job_config=job_config
    )
    job.result()  # Wait for completion
    
    return len(rows)

# =============================================================================
# MAIN SAMPLING LOOP
# =============================================================================

def run_sampling(source='all', resume=False):
    """Main entry point. Samples HILDA+ for all training points."""
    from google.cloud import bigquery
    
    log("=" * 60)
    log("HILDA+ Local Sampler for SINR v3")
    log(f"Source: {source}")
    log(f"Resume mode: {resume}")
    log(f"Output table: {BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}")
    log("=" * 60)
    
    # Load points
    df = load_points_from_bq(source)
    
    if len(df) == 0:
        log("No points to process. Exiting.")
        return
    
    # Resume mode: skip already-completed keys
    if resume:
        completed = load_completed_keys()
        if completed:
            df['_key'] = (df['lat'].astype(str) + '|' + 
                         df['lon'].astype(str) + '|' + 
                         df['observation_year'].astype(str))
            before = len(df)
            df = df[~df['_key'].isin(completed)]
            df = df.drop(columns=['_key'])
            log(f"Resume: skipped {before - len(df):,} completed, {len(df):,} remaining")
    
    if len(df) == 0:
        log("All points already completed. Nothing to do.")
        return
    
    # Initialize raster cache
    cache = HildaRasterCache(HILDA_DIR, max_cache_size=8)
    
    # Group by observation_year to minimize raster loading
    year_groups = df.groupby('observation_year')
    unique_obs_years = sorted(df['observation_year'].unique())
    unique_emb_years = sorted(df['emb_year'].unique())
    log(f"Observation years: {len(unique_obs_years)} unique "
        f"({min(unique_obs_years)}-{max(unique_obs_years)})")
    log(f"Embedding years: {len(unique_emb_years)} unique "
        f"({min(unique_emb_years)}-{max(unique_emb_years)})")
    
    # Process all points
    client = bigquery.Client(project=BQ_PROJECT)
    table_ref = f'{BQ_PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE}'
    
    total_points = len(df)
    processed = 0
    written = 0
    batch_rows = []
    t_start = time.time()
    
    lats = df['lat'].values
    lons = df['lon'].values
    obs_years = df['observation_year'].values.astype(int)
    emb_years = df['emb_year'].values.astype(int)
    
    # Get all unique years we need to sample
    all_years_needed = set(obs_years) | set(emb_years)
    all_years_needed = {y for y in all_years_needed if HILDA_MIN_YEAR <= y <= HILDA_MAX_YEAR}
    log(f"Need to sample {len(all_years_needed)} unique HILDA years")
    
    # Strategy: process in chunks, sample obs_year and emb_year per chunk
    CHUNK_SIZE = 500000
    n_chunks = (total_points + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    log(f"\nProcessing {total_points:,} points in {n_chunks} chunks of {CHUNK_SIZE:,}")
    
    for chunk_idx in range(n_chunks):
        start = chunk_idx * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, total_points)
        chunk_lats = lats[start:end]
        chunk_lons = lons[start:end]
        chunk_obs = obs_years[start:end]
        chunk_emb = emb_years[start:end]
        
        # Sample HILDA at obs_year for each point
        hilda_at_obs = np.full(len(chunk_lats), -9999, dtype=np.int32)
        hilda_at_ae = np.full(len(chunk_lats), -9999, dtype=np.int32)
        
        # Group by obs_year within this chunk for efficient raster reuse
        for year in np.unique(chunk_obs):
            year = int(year)
            mask = chunk_obs == year
            if mask.sum() == 0:
                continue
            vals = cache.sample_points(chunk_lats[mask], chunk_lons[mask], year)
            hilda_at_obs[mask] = vals
        
        # Group by emb_year within this chunk
        for year in np.unique(chunk_emb):
            year = int(year)
            mask = chunk_emb == year
            if mask.sum() == 0:
                continue
            vals = cache.sample_points(chunk_lats[mask], chunk_lons[mask], year)
            hilda_at_ae[mask] = vals
        
        # Compute derived features
        # lulc_changed: did class change between obs and ae?
        has_both = (hilda_at_obs != -9999) & (hilda_at_ae != -9999)
        lulc_changed = np.where(has_both, (hilda_at_obs != hilda_at_ae).astype(int), -9999)
        
        # forest_to_nonforest: was forest at obs (40-45) but not forest at ae?
        is_forest_obs = (hilda_at_obs >= 40) & (hilda_at_obs <= 45)
        is_forest_ae = (hilda_at_ae >= 40) & (hilda_at_ae <= 45)
        forest_to_nonforest = np.where(
            has_both,
            (is_forest_obs & ~is_forest_ae).astype(int),
            -9999
        )
        
        # has_hilda: is obs_year within HILDA range?
        has_hilda = ((chunk_obs >= HILDA_MIN_YEAR) & 
                     (chunk_obs <= HILDA_MAX_YEAR)).astype(int)
        
        # Build rows for BQ
        for i in range(len(chunk_lats)):
            row = {
                'latitude': float(chunk_lats[i]),
                'longitude': float(chunk_lons[i]),
                'observation_year': int(chunk_obs[i]),
                'emb_year': int(chunk_emb[i]),
                'hilda_lulc_at_obs': int(hilda_at_obs[i]),
                'hilda_lulc_at_ae': int(hilda_at_ae[i]),
                'lulc_changed': int(lulc_changed[i]),
                'forest_to_nonforest': int(forest_to_nonforest[i]),
                'has_hilda': int(has_hilda[i]),
            }
            batch_rows.append(row)
        
        # Write batch to BQ when full
        while len(batch_rows) >= BQ_BATCH_SIZE:
            to_write = batch_rows[:BQ_BATCH_SIZE]
            batch_rows = batch_rows[BQ_BATCH_SIZE:]
            n = write_batch_to_bq(to_write, client, table_ref)
            written += n
        
        processed += (end - start)
        elapsed = time.time() - t_start
        rate = processed / elapsed if elapsed > 0 else 0
        eta_sec = (total_points - processed) / rate if rate > 0 else 0
        log(f"  Chunk {chunk_idx+1}/{n_chunks}: {processed:,}/{total_points:,} "
            f"({100*processed/total_points:.1f}%), "
            f"written={written:,}, "
            f"rate={rate:.0f} pts/s, "
            f"ETA={eta_sec/60:.1f}min")
    
    # Write remaining rows
    if batch_rows:
        n = write_batch_to_bq(batch_rows, client, table_ref)
        written += n
    
    elapsed = time.time() - t_start
    log(f"\nDONE. Processed {processed:,} points, wrote {written:,} rows "
        f"in {elapsed/60:.1f} min ({processed/elapsed:.0f} pts/s)")

# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HILDA+ Local Sampler')
    parser.add_argument('--source', choices=['new_gbif', 'backfill', 'all'],
                        default='all', help='Which BQ tables to sample for')
    parser.add_argument('--resume', action='store_true',
                        help='Skip already-completed points')
    args = parser.parse_args()
    
    run_sampling(source=args.source, resume=args.resume)
