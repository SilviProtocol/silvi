#!/usr/bin/env python3
"""
plantation_dataset_sampler.py — Sample Xiao (2024) and Neumann (2025) plantation 
detection datasets at all pixel_environmental_bands locations.

Two new features for SINR v2.1:
  1. xiao_planted_forest (smallint): From Xiao et al. 2024 Global Natural & Planted Forests (30m)
     Values: 0=non-forest, 1=natural forest, 2=planted forest
     GEE: projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS
     
  2. neumann_natural_prob (smallint): From Neumann/DeepMind 2025 Natural Forests of the World (10m)
     Values: 0-255 probability of natural forest (0=not natural/planted, 255=definitely natural)
     GEE: projects/nature-trace/assets/forest_typology/natural_forest_2020_v1_0_collection

These fix the JRC GFC2020 misclassification problem discovered at Wairarapa NZ — JRC labels
known P. radiata plantations as "naturally regenerating" (type=1). The Xiao dataset correctly
identifies Wairarapa as PLANTED, and Neumann gives it 0% natural probability.

Architecture:
  1. Extract unique (lat4dp, lon4dp) from pixel_environmental_bands where data is missing
  2. Sample Xiao + Neumann via GEE API in batches of 500 points, multithreaded
  3. Write results directly to PostgreSQL via temp table + bulk UPDATE
  4. Temporal triangulation: NULL out values for pixels where Hansen forest loss
     occurred between occurrence_year and 2021 (~196K rows), and for pre-1985
     occurrences (~239K rows) that have no Landsat baseline

Usage:
  python3 plantation_dataset_sampler.py --sample --threads 8
  python3 plantation_dataset_sampler.py --triangulate   # just the NULL-out step
  python3 plantation_dataset_sampler.py --all --threads 8
"""

import argparse
import ee
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-479918'

# GEE sampling: 500 points per API call is the sweet spot
# (GEE starts throttling above ~5000 concurrent getInfo calls)
BATCH_SIZE = 500
COORD_DECIMALS = 4

DB_NAME = "treekipedia"
DB_USER = os.environ.get("DB_USER", os.environ.get("USER", "djimoserodio"))
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

SCRIPT_DIR = Path(__file__).parent
CHECKPOINT_FILE = SCRIPT_DIR / "plantation_sampling_checkpoint.json"

# GEE asset paths
XIAO_ASSET = 'projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS'
NEUMANN_ASSET = 'projects/nature-trace/assets/forest_typology/natural_forest_2020_v1_0_collection'


# =============================================================================
# GEE IMAGE BUILDER
# =============================================================================

def build_plantation_stack() -> 'ee.Image':
    """Build a 2-band image stack: xiao_planted_forest + neumann_natural_prob.
    
    Xiao bands (RGB encoding):
      - Green (0,127,0) = natural forest -> remap to 1
      - Yellow (127,127,0) = planted forest -> remap to 2
      - White (127,127,127) = non-forest -> remap to 0
      - No data -> 0
    
    Neumann: B0 = probability of natural forest (0-255)
    """
    xiao_mosaic = ee.ImageCollection(XIAO_ASSET).mosaic()
    b1 = xiao_mosaic.select('b1')
    b2 = xiao_mosaic.select('b2')
    b3 = xiao_mosaic.select('b3')
    
    is_natural = b1.eq(0).And(b2.eq(127)).And(b3.eq(0))
    is_planted = b1.eq(127).And(b2.eq(127)).And(b3.eq(0))
    
    xiao_class = ee.Image(0).where(is_natural, 1).where(is_planted, 2) \
        .rename('xiao_planted_forest').toInt()
    
    neumann_mosaic = ee.ImageCollection(NEUMANN_ASSET).mosaic()
    neumann_prob = neumann_mosaic.select('B0').rename('neumann_natural_prob') \
        .unmask(0).toInt()
    
    return xiao_class.addBands(neumann_prob)


# =============================================================================
# GEE SAMPLING
# =============================================================================

def sample_batch(
    batch_lats: np.ndarray,
    batch_lons: np.ndarray,
    plantation_stack: 'ee.Image',
) -> List[Tuple[float, float, Optional[int], Optional[int]]]:
    """Sample plantation stack at a batch of points via GEE API.
    
    Returns list of (lat, lon, xiao_planted_forest, neumann_natural_prob).
    """
    features = []
    for lat, lon in zip(batch_lats, batch_lons):
        features.append(ee.Feature(
            ee.Geometry.Point([float(lon), float(lat)]),
            {'lat': float(lat), 'lon': float(lon)}
        ))
    
    fc = ee.FeatureCollection(features)
    sampled = plantation_stack.sampleRegions(
        collection=fc,
        scale=30,
        geometries=False,
    )
    
    result = sampled.getInfo()
    
    rows = []
    if result and 'features' in result:
        for feat in result['features']:
            props = feat['properties']
            rows.append((
                props['lat'],
                props['lon'],
                props.get('xiao_planted_forest'),
                props.get('neumann_natural_prob'),
            ))
    
    return rows


# =============================================================================
# MAIN SAMPLING PIPELINE
# =============================================================================

def get_unique_pixels() -> pd.DataFrame:
    """Get unique (lat4dp, lon4dp) from pixel_environmental_bands where plantation data is missing."""
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
    
    print("Querying unique pixel locations needing plantation data...")
    query = """
    SELECT DISTINCT 
        ROUND(latitude::numeric, 4)::float8 as lat,
        ROUND(longitude::numeric, 4)::float8 as lon
    FROM pixel_environmental_bands
    WHERE xiao_planted_forest IS NULL
    ORDER BY lat, lon
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"  Found {len(df):,} unique pixel locations needing plantation data")
    return df


def run_sampling(num_threads: int = 8):
    """Sample plantation data at all pixel locations using multithreaded GEE API calls."""
    import json
    
    print("=" * 70)
    print("STEP 1: SAMPLE PLANTATION DATA VIA GEE API")
    print("=" * 70)
    
    ee.Initialize(project=PROJECT)
    plantation_stack = build_plantation_stack()
    print("Built plantation stack (xiao_planted_forest + neumann_natural_prob)")
    
    pixels_df = get_unique_pixels()
    if len(pixels_df) == 0:
        print("All pixels already have plantation data. Nothing to sample.")
        return
    
    # Check for checkpoint (resume from where we left off)
    start_batch = 0
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            checkpoint = json.load(f)
        start_batch = checkpoint.get('next_batch', 0)
        print(f"Resuming from checkpoint: batch {start_batch}")
    
    n_batches = (len(pixels_df) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Total: {len(pixels_df):,} pixels, {n_batches:,} batches of {BATCH_SIZE}")
    print(f"Threads: {num_threads}")
    print()
    
    # Collect results in memory, flush to DB periodically
    all_results = []
    FLUSH_INTERVAL = 50000  # Flush to DB every 50K results
    
    completed_batches = start_batch
    failed_batches = 0
    total_sampled = 0
    t_start = time.time()
    
    lock = threading.Lock()
    
    def process_batch(batch_idx):
        """Process a single batch."""
        nonlocal failed_batches
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(pixels_df))
        batch = pixels_df.iloc[start:end]
        
        try:
            rows = sample_batch(
                batch['lat'].values,
                batch['lon'].values,
                plantation_stack,
            )
            return rows
        except Exception as e:
            with lock:
                failed_batches += 1
            # Retry once after a pause
            time.sleep(5)
            try:
                rows = sample_batch(
                    batch['lat'].values,
                    batch['lon'].values,
                    plantation_stack,
                )
                return rows
            except Exception as e2:
                print(f"  FAILED batch {batch_idx}: {e2}")
                return []
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit batches in chunks to control memory
        SUBMIT_CHUNK = num_threads * 10  # Submit 10x threads at a time
        
        for chunk_start in range(start_batch, n_batches, SUBMIT_CHUNK):
            chunk_end = min(chunk_start + SUBMIT_CHUNK, n_batches)
            
            futures = {}
            for batch_idx in range(chunk_start, chunk_end):
                future = executor.submit(process_batch, batch_idx)
                futures[future] = batch_idx
            
            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    rows = future.result()
                    with lock:
                        all_results.extend(rows)
                        completed_batches += 1
                        total_sampled += len(rows)
                except Exception as e:
                    print(f"  ERROR batch {batch_idx}: {e}")
                    with lock:
                        failed_batches += 1
            
            # Progress report
            elapsed = time.time() - t_start
            rate = total_sampled / elapsed if elapsed > 0 else 0
            eta_min = (len(pixels_df) - total_sampled) / rate / 60 if rate > 0 else 0
            print(f"  Batches: {completed_batches}/{n_batches} | "
                  f"Sampled: {total_sampled:,}/{len(pixels_df):,} | "
                  f"Failed: {failed_batches} | "
                  f"Rate: {rate:.0f} pts/s | "
                  f"ETA: {eta_min:.0f} min")
            
            # Save checkpoint
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump({'next_batch': completed_batches, 'total_sampled': total_sampled}, f)
            
            # Flush to DB periodically
            if len(all_results) >= FLUSH_INTERVAL:
                flush_to_db(all_results)
                all_results = []
    
    # Final flush
    if all_results:
        flush_to_db(all_results)
    
    elapsed = time.time() - t_start
    print(f"\nSampling complete in {elapsed/60:.1f} min")
    print(f"  Total sampled: {total_sampled:,}")
    print(f"  Failed batches: {failed_batches}")
    
    # Clean up checkpoint
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


def flush_to_db(results: List[Tuple[float, float, Optional[int], Optional[int]]]):
    """Write accumulated results to PostgreSQL via temp table + bulk UPDATE."""
    if not results:
        return
    
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
    cur = conn.cursor()
    
    t0 = time.time()
    
    # Create temp table
    cur.execute("""
    CREATE TEMP TABLE IF NOT EXISTS plantation_updates (
        lat float8,
        lon float8,
        xiao_planted_forest smallint,
        neumann_natural_prob smallint
    ) ON COMMIT DROP
    """)
    
    # Bulk insert
    values = [
        (lat, lon,
         int(xiao) if xiao is not None else None,
         int(neum) if neum is not None else None)
        for lat, lon, xiao, neum in results
    ]
    
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO plantation_updates (lat, lon, xiao_planted_forest, neumann_natural_prob) VALUES %s",
        values,
        page_size=10000,
    )
    
    # Create index for join performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pu_latlon ON plantation_updates (lat, lon)")
    
    # Bulk update
    cur.execute("""
    UPDATE pixel_environmental_bands peb
    SET 
        xiao_planted_forest = pu.xiao_planted_forest,
        neumann_natural_prob = pu.neumann_natural_prob
    FROM plantation_updates pu
    WHERE ROUND(peb.latitude::numeric, 4) = pu.lat
      AND ROUND(peb.longitude::numeric, 4) = pu.lon
    """)
    updated = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    elapsed = time.time() - t0
    print(f"    Flushed {len(results):,} results to DB -> {updated:,} rows updated ({elapsed:.1f}s)")


# =============================================================================
# TEMPORAL TRIANGULATION
# =============================================================================

def run_triangulation():
    """NULL out plantation values for pixels where landscape changed."""
    
    print("=" * 70)
    print("STEP 2: TEMPORAL TRIANGULATION")
    print("=" * 70)
    
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
    cur = conn.cursor()
    
    # Count before
    cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(xiao_planted_forest) as has_xiao,
        COUNT(neumann_natural_prob) as has_neumann
    FROM pixel_environmental_bands
    """)
    before = cur.fetchone()
    print(f"Before triangulation: {before[1]:,} with Xiao, {before[2]:,} with Neumann (of {before[0]:,} total)")
    
    # NULL out pixels where Hansen loss occurred between obs year and 2021
    print("\nNulling pixels where Hansen loss occurred between observation and 2021...")
    t0 = time.time()
    cur.execute("""
    UPDATE pixel_environmental_bands
    SET xiao_planted_forest = NULL,
        neumann_natural_prob = NULL
    WHERE loss = true
      AND occurrence_year IS NOT NULL
      AND lossyear IS NOT NULL
      AND (lossyear + 2000) > occurrence_year
      AND (lossyear + 2000) <= 2021
      AND (xiao_planted_forest IS NOT NULL OR neumann_natural_prob IS NOT NULL)
    """)
    nulled_disturbed = cur.rowcount
    conn.commit()
    print(f"  Nulled {nulled_disturbed:,} disturbed rows ({time.time()-t0:.1f}s)")
    
    # NULL out pre-1985 pixels (no Landsat baseline for Xiao)
    print("Nulling pre-1985 pixels (no Landsat baseline)...")
    t0 = time.time()
    cur.execute("""
    UPDATE pixel_environmental_bands
    SET xiao_planted_forest = NULL,
        neumann_natural_prob = NULL
    WHERE occurrence_year IS NOT NULL
      AND occurrence_year < 1985
      AND (xiao_planted_forest IS NOT NULL OR neumann_natural_prob IS NOT NULL)
    """)
    nulled_pre85 = cur.rowcount
    conn.commit()
    print(f"  Nulled {nulled_pre85:,} pre-1985 rows ({time.time()-t0:.1f}s)")
    
    # Verification
    cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(xiao_planted_forest) as has_xiao,
        COUNT(neumann_natural_prob) as has_neumann,
        COUNT(CASE WHEN xiao_planted_forest = 2 THEN 1 END) as xiao_planted,
        COUNT(CASE WHEN xiao_planted_forest = 1 THEN 1 END) as xiao_natural,
        COUNT(CASE WHEN xiao_planted_forest = 0 THEN 1 END) as xiao_nonforest,
        ROUND(AVG(CASE WHEN neumann_natural_prob IS NOT NULL THEN neumann_natural_prob END), 1) as avg_neumann
    FROM pixel_environmental_bands
    """)
    after = cur.fetchone()
    print(f"\nAfter triangulation:")
    print(f"  Total rows: {after[0]:,}")
    print(f"  Has Xiao: {after[1]:,} ({after[1]/after[0]*100:.1f}%)")
    print(f"  Has Neumann: {after[2]:,} ({after[2]/after[0]*100:.1f}%)")
    print(f"  Xiao planted: {after[3]:,}")
    print(f"  Xiao natural: {after[4]:,}")
    print(f"  Xiao non-forest: {after[5]:,}")
    print(f"  Avg Neumann prob: {after[6]}")
    print(f"  Nulled (disturbed): {nulled_disturbed:,}")
    print(f"  Nulled (pre-1985): {nulled_pre85:,}")
    
    cur.close()
    conn.close()
    print("\nDone!")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Sample Xiao & Neumann plantation datasets at all pixel locations"
    )
    parser.add_argument('--sample', action='store_true',
                       help='Sample plantation data via GEE API (multithreaded)')
    parser.add_argument('--triangulate', action='store_true',
                       help='Run temporal triangulation (NULL out changed pixels)')
    parser.add_argument('--all', action='store_true',
                       help='Run both sample and triangulate')
    parser.add_argument('--threads', type=int, default=8,
                       help='Number of concurrent GEE API threads (default: 8)')
    
    args = parser.parse_args()
    
    if not any([args.sample, args.triangulate, args.all]):
        parser.print_help()
        sys.exit(1)
    
    if args.all or args.sample:
        run_sampling(num_threads=args.threads)
    
    if args.all or args.triangulate:
        run_triangulation()


if __name__ == '__main__':
    main()
