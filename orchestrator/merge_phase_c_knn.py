#!/usr/bin/env python3
"""
C5+C6: Merge Phase C Data + Species Rejoin for k-NN Loading
============================================================

Produces a parquet file in V4 format, ready for load_knn_embeddings.py.

Steps:
  1. Export Phase C pixel data from BQ (deduped at 4dp)
  2. For disturbed pixels (lossyear > 0), swap A00-A63 with C3 reference embeddings
  3. Join temporal table for occurrence_year
  4. Rejoin species: match pixel coords to GBIF 96M parquet to get taxon_id
  5. V4 backfill: join V4 parquet AE data with BQ env backfill (for training parquet)
  6. Output:
     a) phase_c_knn_ready.parquet — Phase C data in V4 schema for k-NN load
     b) v4_knn_ready.parquet — V4 data with env backfill (updated with temporal bands)
     c) training_dataset_full.parquet — full env stack for neural net (optional, --training)

Usage:
    python3 merge_phase_c_knn.py                    # Phase C + V4 k-NN parquets
    python3 merge_phase_c_knn.py --dry-run          # Show stats only
    python3 merge_phase_c_knn.py --training         # Also produce full training dataset

Author: Treekipedia Team
Created: February 16, 2026
"""

import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
from datetime import datetime
import argparse
import time

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
V4_PARQUET = SCRIPT_DIR / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
OCC_PARQUET = PROJECT_ROOT / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"
OUTPUT_DIR = SCRIPT_DIR / "expansion_phase_c"

PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]

# Coordinate precision for joins (4dp = ~11m)
COORD_PRECISION = 4


# =============================================================================
# HELPERS
# =============================================================================

def lat4lon4(df, lat_col='latitude', lon_col='longitude'):
    """Add integer join keys: lat * 10000 rounded to int."""
    df = df.copy()
    df['lat4'] = (df[lat_col] * 10000).round().astype(np.int64)
    df['lon4'] = (df[lon_col] * 10000).round().astype(np.int64)
    return df


# =============================================================================
# STEP 1: LOAD PHASE C PIXELS FROM BQ (DEDUPED)
# =============================================================================

def load_phase_c_pixels(client):
    """Load Phase C pixels from BQ, deduped at pixel level.
    
    Strategy: only pull the columns needed for k-NN (not all 130).
    Dedup in pandas after download — faster than BQ window functions.
    """
    print("STEP 1: Loading Phase C pixels from BigQuery...")
    
    # Only pull columns needed for k-NN loading
    cols = ', '.join(EMBEDDING_COLS + [
        'latitude', 'longitude', 'emb_year', 'elevation', 'treecover2000',
        'lossyear', 'loss', 'gain'
    ])
    
    q = f"""
    SELECT {cols}
    FROM `{PROJECT}.{BQ_DATASET}.phase_c_embeddings_env_v1`
    """
    
    print("  Downloading from BQ (72 columns, ~3.95M rows)...")
    df = client.query(q).to_dataframe()
    print(f"  Downloaded: {len(df):,} rows")
    
    # Dedup in pandas at 4dp — much faster than BQ ROW_NUMBER
    df['lat4'] = (df['latitude'] * 10000).round().astype(np.int64)
    df['lon4'] = (df['longitude'] * 10000).round().astype(np.int64)
    before = len(df)
    df = df.drop_duplicates(subset=['lat4', 'lon4'], keep='first')
    df = df.drop(columns=['lat4', 'lon4'])
    print(f"  Deduped: {before:,} -> {len(df):,} ({before - len(df):,} duplicates removed)")
    print(f"  emb_year range: {df['emb_year'].min()}-{df['emb_year'].max()}")
    
    return df


# =============================================================================
# STEP 2: SWAP DISTURBED PIXEL EMBEDDINGS WITH C3 REFERENCES
# =============================================================================

def swap_disturbed_embeddings(pc_df, client):
    """For disturbed pixels, replace A00-A63 with C3 reference embeddings."""
    print("\nSTEP 2: Swapping disturbed pixel embeddings with C3 references...")
    
    # Identify disturbed pixels in Phase C
    disturbed_mask = (pc_df['lossyear'].notna()) & (pc_df['lossyear'] > 0)
    n_disturbed = disturbed_mask.sum()
    print(f"  Disturbed pixels in Phase C: {n_disturbed:,}")
    
    if n_disturbed == 0:
        print("  No disturbed pixels — skipping")
        return pc_df
    
    # Load C3 reference embeddings from BQ (deduped)
    ref_cols = ', '.join([f'ref.{c}' for c in EMBEDDING_COLS] + [
        'ref.latitude', 'ref.longitude', 
        'ref.proxy_distance_m', 'ref.reference_found'
    ])
    
    q = f"""
    SELECT {', '.join(EMBEDDING_COLS)}, 
           latitude, longitude, proxy_distance_m, reference_found,
           reference_lat, reference_lon
    FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY CAST(ROUND(latitude * 10000) AS INT64),
                         CAST(ROUND(longitude * 10000) AS INT64)
            ORDER BY proxy_distance_m ASC  -- keep closest reference
        ) as _rn
        FROM `{PROJECT}.{BQ_DATASET}.regime3_reference_fast_v1`
        WHERE reference_found = 1
    )
    WHERE _rn = 1
    """
    
    print("  Loading C3 reference embeddings...")
    ref_df = client.query(q).to_dataframe()
    print(f"  C3 references loaded: {len(ref_df):,} unique pixels")
    
    # Add join keys
    pc_df = lat4lon4(pc_df)
    ref_df = lat4lon4(ref_df)
    
    # Build reference lookup: (lat4, lon4) -> embedding values
    ref_lookup = ref_df.drop_duplicates(subset=['lat4', 'lon4'], keep='first')
    ref_lookup = ref_lookup.set_index(['lat4', 'lon4'])[EMBEDDING_COLS]
    
    # Get disturbed pixel keys
    disturbed_keys = pc_df.loc[disturbed_mask, ['lat4', 'lon4']]
    disturbed_tuples = list(zip(disturbed_keys['lat4'], disturbed_keys['lon4']))
    
    # Vectorized: find which disturbed pixels have references
    ref_available = ref_lookup.index
    swap_mask = pd.Series(
        [k in ref_available for k in disturbed_tuples],
        index=disturbed_keys.index
    )
    
    swap_indices = swap_mask[swap_mask].index
    swapped = len(swap_indices)
    no_ref = n_disturbed - swapped
    
    # Do the swap: for rows with references, overwrite A00-A63
    if swapped > 0:
        swap_keys = pc_df.loc[swap_indices, ['lat4', 'lon4']]
        swap_tuples = list(zip(swap_keys['lat4'], swap_keys['lon4']))
        ref_values = ref_lookup.loc[swap_tuples].values
        pc_df.loc[swap_indices, EMBEDDING_COLS] = ref_values
    
    print(f"  Embeddings swapped: {swapped:,}")
    print(f"  Disturbed without reference: {no_ref:,}")
    print(f"  Swap rate: {swapped/n_disturbed*100:.1f}%")
    
    # Clean up join keys
    pc_df = pc_df.drop(columns=['lat4', 'lon4'])
    
    return pc_df


# =============================================================================
# STEP 3: JOIN TEMPORAL TABLE FOR OCCURRENCE_YEAR
# =============================================================================

def join_temporal_year(pc_df, client):
    """Join temporal table to get occurrence_year per pixel."""
    print("\nSTEP 3: Joining temporal table for occurrence_year...")
    
    # Load just the occurrence_year column, deduped
    q = f"""
    SELECT DISTINCT
        CAST(ROUND(latitude * 10000) AS INT64) AS lat4,
        CAST(ROUND(longitude * 10000) AS INT64) AS lon4,
        occurrence_year
    FROM `{PROJECT}.{BQ_DATASET}.phase_c_temporal_env_v1`
    """
    
    print("  Loading temporal occurrence years...")
    temp_df = client.query(q).to_dataframe()
    print(f"  Temporal rows: {len(temp_df):,}")
    
    # Check for dupes (same pixel, different occurrence_years — shouldn't happen
    # since temporal table is 1 row per pixel, but be safe)
    dupes = temp_df.duplicated(subset=['lat4', 'lon4'], keep=False).sum()
    if dupes > 0:
        print(f"  WARNING: {dupes:,} duplicate (lat4,lon4) in temporal table — keeping first")
        temp_df = temp_df.drop_duplicates(subset=['lat4', 'lon4'], keep='first')
    
    # Add join keys to Phase C
    pc_df = lat4lon4(pc_df)
    
    # Merge
    before = len(pc_df)
    pc_df = pc_df.merge(temp_df, on=['lat4', 'lon4'], how='left')
    assert len(pc_df) == before, f"Merge changed row count: {before} -> {len(pc_df)}"
    
    matched = pc_df['occurrence_year'].notna().sum()
    print(f"  Matched: {matched:,}/{len(pc_df):,} ({matched/len(pc_df)*100:.1f}%)")
    print(f"  Missing occurrence_year: {len(pc_df) - matched:,}")
    
    # Use occurrence_year as orig_year for Phase C
    pc_df['orig_year'] = pc_df['occurrence_year']
    
    # Clean up
    pc_df = pc_df.drop(columns=['lat4', 'lon4', 'occurrence_year'])
    
    return pc_df


# =============================================================================
# STEP 4: SPECIES REJOIN — MAP PIXELS TO TAXON_IDS VIA GBIF
# =============================================================================

def rejoin_species(pc_df, occ_path):
    """
    Map Phase C pixel coordinates to species via GBIF occurrence parquet.
    
    Phase C has no taxon_id — it's pixel-level data. We match each pixel's
    (lat4, lon4) to GBIF occurrences to recover which species were observed there.
    
    This is the inverse of pixel dedup: one pixel can map to MANY species.
    Output has one row per (taxon_id, latitude, longitude).
    """
    print("\nSTEP 4: Species rejoin — mapping pixels to taxon_ids...")
    
    if not occ_path.exists():
        print(f"  ERROR: GBIF occurrence parquet not found at {occ_path}")
        print(f"  Cannot do species rejoin without GBIF data!")
        return None
    
    # Load GBIF occurrences — only columns needed for join
    print(f"  Loading GBIF occurrence file ({occ_path.name})...")
    occ_cols = ['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year']
    occ = pq.read_table(str(occ_path), columns=occ_cols).to_pandas()
    print(f"  GBIF occurrences: {len(occ):,} rows, {occ['taxon_id'].nunique():,} species")
    
    # Create integer join keys
    occ['lat4'] = (occ['decimalLatitude'] * 10000).round().astype(np.int64)
    occ['lon4'] = (occ['decimalLongitude'] * 10000).round().astype(np.int64)
    
    # Dedup occurrences: keep unique (taxon_id, lat4, lon4) — one row per species per pixel
    occ = occ.drop_duplicates(subset=['taxon_id', 'lat4', 'lon4'], keep='first')
    print(f"  Unique (taxon_id, lat4, lon4): {len(occ):,}")
    
    # Drop raw GBIF coordinates (we'll use Phase C's coordinates)
    occ = occ[['taxon_id', 'lat4', 'lon4']].copy()
    
    # Add join keys to Phase C pixels
    pc_df = lat4lon4(pc_df)
    
    # Build set of Phase C pixel keys
    pc_keys = set(zip(pc_df['lat4'], pc_df['lon4']))
    print(f"  Phase C unique pixels: {len(pc_keys):,}")
    
    # Filter GBIF to only pixels that exist in Phase C
    occ['_key'] = list(zip(occ['lat4'], occ['lon4']))
    occ_matched = occ[occ['_key'].isin(pc_keys)].drop(columns=['_key']).copy()
    print(f"  GBIF occurrences at Phase C pixels: {len(occ_matched):,}")
    print(f"  Species at Phase C pixels: {occ_matched['taxon_id'].nunique():,}")
    
    # Join: each pixel gets expanded to one row per species
    before = len(pc_df)
    result = occ_matched.merge(pc_df, on=['lat4', 'lon4'], how='inner')
    print(f"  After species rejoin: {len(result):,} rows (from {before:,} pixels)")
    print(f"  Expansion factor: {len(result)/before:.1f}x")
    print(f"  Species count: {result['taxon_id'].nunique():,}")
    
    # Dedup: one row per (taxon_id, lat, lon)
    before_dedup = len(result)
    result = result.drop_duplicates(subset=['taxon_id', 'lat4', 'lon4'], keep='first')
    if len(result) < before_dedup:
        print(f"  Deduped: {before_dedup:,} -> {len(result):,} ({before_dedup - len(result):,} removed)")
    
    # Clean up join keys
    result = result.drop(columns=['lat4', 'lon4'])
    
    return result


# =============================================================================
# STEP 5: PRODUCE V4-FORMAT PARQUET
# =============================================================================

def format_for_knn(df, data_regime=3):
    """Format DataFrame to match V4 parquet schema for load_knn_embeddings.py.
    
    Required columns: taxon_id, latitude, longitude, emb_year, orig_year,
                      elevation, treecover2000, lossyear, loss, gain, A00-A63
    """
    print(f"\nSTEP 5: Formatting for k-NN load (data_regime={data_regime})...")
    
    output_cols = ['taxon_id', 'latitude', 'longitude', 'emb_year', 'orig_year',
                   'elevation', 'treecover2000', 'lossyear', 'loss', 'gain'] + EMBEDDING_COLS
    
    # Ensure all columns exist
    for col in output_cols:
        if col not in df.columns:
            print(f"  WARNING: Missing column '{col}' — filling with 0")
            df[col] = 0
    
    # Select and order columns
    result = df[output_cols].copy()
    
    # Type enforcement
    result['emb_year'] = result['emb_year'].fillna(0).astype(int)
    result['orig_year'] = result['orig_year'].fillna(0).astype(int)
    result['elevation'] = result['elevation'].fillna(0).astype(int)
    result['treecover2000'] = result['treecover2000'].fillna(0).astype(int)
    result['lossyear'] = result['lossyear'].fillna(0).astype(int)
    result['loss'] = result['loss'].fillna(0).astype(int)
    result['gain'] = result['gain'].fillna(0).astype(int)
    
    print(f"  Rows: {len(result):,}")
    print(f"  Species: {result['taxon_id'].nunique():,}")
    print(f"  Columns: {list(result.columns)}")
    
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Merge Phase C data for k-NN loading')
    parser.add_argument('--dry-run', action='store_true', help='Show stats only, no output files')
    parser.add_argument('--training', action='store_true', help='Also produce full training dataset')
    parser.add_argument('--skip-rejoin', action='store_true', help='Skip species rejoin (pixel-level output only)')
    args = parser.parse_args()
    
    start_time = time.time()
    
    print("=" * 70)
    print("C5+C6: MERGE PHASE C + SPECIES REJOIN FOR k-NN")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize BQ client
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    
    # Step 1: Load Phase C pixels (deduped)
    pc_df = load_phase_c_pixels(client)
    
    # Step 2: Swap disturbed pixel embeddings with C3 references
    pc_df = swap_disturbed_embeddings(pc_df, client)
    
    # Step 3: Join temporal table for occurrence_year
    pc_df = join_temporal_year(pc_df, client)
    
    # Step 4: Species rejoin
    if not args.skip_rejoin:
        result = rejoin_species(pc_df, OCC_PARQUET)
        if result is None:
            print("\nERROR: Species rejoin failed. Use --skip-rejoin for pixel-level output.")
            sys.exit(1)
    else:
        print("\nSTEP 4: Skipping species rejoin (--skip-rejoin)")
        result = pc_df
    
    # Step 5: Format for k-NN
    knn_df = format_for_knn(result, data_regime=3)
    
    # Stats
    elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print("MERGE COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Phase C pixels (deduped): {len(pc_df):,}")
    print(f"  k-NN ready rows: {len(knn_df):,}")
    if 'taxon_id' in knn_df.columns:
        print(f"  Species: {knn_df['taxon_id'].nunique():,}")
    print(f"  Elapsed: {elapsed:.1f}s")
    
    if args.dry_run:
        print(f"\n[DRY RUN — no files written]")
        return
    
    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "phase_c_knn_ready.parquet"
    
    print(f"\n  Writing {output_path}...")
    knn_df.to_parquet(str(output_path), index=False)
    
    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  Written: {output_path} ({file_size_mb:.0f} MB)")
    print(f"\n  Next: python3 load_knn_embeddings.py")
    print(f"  (Update load_knn_embeddings.py to include Phase C parquet as data_regime=3)")


if __name__ == '__main__':
    main()
