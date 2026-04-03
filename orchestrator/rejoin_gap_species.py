#!/usr/bin/env python3
"""
Phase A: Rejoin Gap Species to Existing V4 Embeddings
======================================================

Purpose: Recover ~4,680 species that have occurrences at the same pixels
         where v4 species were already sampled. Since AlphaEarth returns
         the same 64-D embedding for a pixel regardless of species, we can
         assign existing embeddings to new species without any GEE calls.

How it works:
  1. Load v4 parquet (2.4M unique pixel-years with embeddings)
  2. Load full occurrence parquet (96.5M rows, 60K species)
  3. Identify gap species (in occurrences but NOT in v4)
  4. Match gap species' occurrence coordinates to v4 pixel locations
  5. Assign the v4 embedding at that pixel to the gap species
  6. Output: new parquet in v4 format, ready for clustering

Key insight: AlphaEarth is deterministic per pixel-year. If pixel (lat, lon)
was sampled for species A in year 2020, and species B also occurs at that
pixel, species B gets the same embedding. No GEE call needed.

Reference: .claude/project-management/GEE_PIPELINE_REFERENCE.md

Usage:
    python3 rejoin_gap_species.py                    # Full run
    python3 rejoin_gap_species.py --dry-run           # Show stats only
    python3 rejoin_gap_species.py --output-only       # Save parquet, don't cluster/load

Author: Treekipedia Team
Created: February 11, 2026
"""

import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
import argparse
import json

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
V4_PARQUET = SCRIPT_DIR / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
OCC_PARQUET = SCRIPT_DIR.parent / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"
OUTPUT_DIR = SCRIPT_DIR / "expansion_phase_a"

EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]
COORD_PRECISION = 4  # 4 decimal places = ~10m, matching v4 dedup

# =============================================================================
# PIXEL MATCHING
# =============================================================================

def coords_to_int_key(lat, lon):
    """Convert lat/lon to integer keys for exact matching.
    
    Float comparison is unreliable. Multiply by 10000 and round to int.
    This gives ~10m precision matching v4's dedup strategy.
    """
    return (
        (lat * 10000).round().astype(np.int64),
        (lon * 10000).round().astype(np.int64)
    )


def build_pixel_lookup(v4_df):
    """Build a lookup from (lat_i, lon_i) → best embedding row.
    
    For pixels sampled in multiple years, keep the most recent year
    (most relevant embedding for current habitat state).
    """
    print("  Building pixel lookup table...")
    v4_df = v4_df.copy()
    v4_df['lat_i'], v4_df['lon_i'] = coords_to_int_key(
        v4_df['latitude'], v4_df['longitude']
    )
    
    # Sort by year descending so first occurrence per pixel is most recent
    v4_df = v4_df.sort_values('emb_year', ascending=False)
    
    # Drop duplicate pixels (keep most recent year)
    pixel_lookup = v4_df.drop_duplicates(subset=['lat_i', 'lon_i'], keep='first')
    
    print(f"    Unique pixel locations: {len(pixel_lookup):,}")
    print(f"    Year range: {pixel_lookup['emb_year'].min()}-{pixel_lookup['emb_year'].max()}")
    
    return pixel_lookup


def match_gap_species_to_pixels(gap_occ, pixel_lookup):
    """Match gap species occurrences to v4 pixel locations.
    
    Returns DataFrame of gap species with matched embeddings.
    """
    print("  Matching gap species to v4 pixels...")
    
    gap_occ = gap_occ.copy()
    gap_occ['lat_i'], gap_occ['lon_i'] = coords_to_int_key(
        gap_occ['decimalLatitude'], gap_occ['decimalLongitude']
    )
    
    # Build set of v4 pixel keys for fast lookup
    pixel_keys = set(zip(pixel_lookup['lat_i'], pixel_lookup['lon_i']))
    
    # Find gap occurrences at v4 pixels
    gap_occ['pixel_key'] = list(zip(gap_occ['lat_i'], gap_occ['lon_i']))
    matched = gap_occ[gap_occ['pixel_key'].isin(pixel_keys)].copy()
    
    if len(matched) == 0:
        print("    No matches found!")
        return pd.DataFrame()
    
    print(f"    Gap occurrences at v4 pixels: {len(matched):,}")
    print(f"    Gap species with matches: {matched['taxon_id'].nunique():,}")
    
    # Merge with pixel embeddings
    # Join on (lat_i, lon_i) to get the embedding columns
    embedding_cols_plus = ['lat_i', 'lon_i', 'emb_year', 'elevation', 
                           'treecover2000', 'lossyear', 'loss', 'gain'] + EMBEDDING_COLS
    
    result = matched.merge(
        pixel_lookup[embedding_cols_plus],
        on=['lat_i', 'lon_i'],
        how='inner'
    )
    
    # Format to match v4 schema
    output = pd.DataFrame({
        'taxon_id': result['taxon_id'],
        'latitude': result['decimalLatitude'].round(COORD_PRECISION),
        'longitude': result['decimalLongitude'].round(COORD_PRECISION),
        'emb_year': result['emb_year'],
        'orig_year': result['year'].fillna(0).astype(int),
        'elevation': result['elevation_y'] if 'elevation_y' in result.columns else result.get('elevation', 0),
        'treecover2000': result['treecover2000'],
        'lossyear': result['lossyear'],
        'loss': result['loss'],
        'gain': result['gain'],
    })
    
    # Add embedding columns
    for col in EMBEDDING_COLS:
        output[col] = result[col]
    
    # Safety check: remove any rows with null taxon_id
    output = output.dropna(subset=['taxon_id'])
    
    # Deduplicate: same species at same pixel = keep one
    output = output.drop_duplicates(subset=['taxon_id', 'latitude', 'longitude'])
    
    print(f"    After dedup: {len(output):,} rows, {output['taxon_id'].nunique():,} species")
    
    return output


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Phase A: Rejoin gap species to v4 embeddings')
    parser.add_argument('--dry-run', action='store_true', help='Show stats only, no output')
    parser.add_argument('--output-only', action='store_true', help='Save parquet but skip clustering/loading')
    args = parser.parse_args()
    
    print("=" * 70)
    print("PHASE A: REJOIN GAP SPECIES TO V4 EMBEDDINGS")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"No GEE calls needed — pure data join")
    print()
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 1: Load v4 data
    # ─────────────────────────────────────────────────────────────────────
    print("STEP 1: Loading v4 parquet...")
    if not V4_PARQUET.exists():
        print(f"  ERROR: v4 parquet not found at {V4_PARQUET}")
        sys.exit(1)
    
    v4 = pq.read_table(V4_PARQUET).to_pandas()
    v4_species = set(v4['taxon_id'].unique())
    print(f"  V4: {len(v4):,} rows, {len(v4_species):,} species")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 2: Load occurrence data and identify gap species
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 2: Loading occurrence parquet...")
    if not OCC_PARQUET.exists():
        print(f"  ERROR: Occurrence parquet not found at {OCC_PARQUET}")
        sys.exit(1)
    
    occ = pq.read_table(OCC_PARQUET).to_pandas()
    
    # Filter out rows with null taxon_id (present in source GBIF data)
    null_count = occ['taxon_id'].isna().sum()
    if null_count > 0:
        print(f"  Dropping {null_count:,} occurrence rows with null taxon_id")
        occ = occ.dropna(subset=['taxon_id'])
    
    occ_species = set(occ['taxon_id'].unique())
    gap_species = occ_species - v4_species
    
    print(f"  Occurrences: {len(occ):,} rows, {len(occ_species):,} species")
    print(f"  Gap species (in occ but not in v4): {len(gap_species):,}")
    
    # Filter to gap species only
    gap_occ = occ[occ['taxon_id'].isin(gap_species)]
    print(f"  Gap species occurrences: {len(gap_occ):,}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 3: Build pixel lookup from v4
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 3: Building v4 pixel lookup...")
    pixel_lookup = build_pixel_lookup(v4)
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 4: Match gap species to v4 pixels
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 4: Matching gap species to v4 pixels...")
    rejoined = match_gap_species_to_pixels(gap_occ, pixel_lookup)
    
    if len(rejoined) == 0:
        print("\nNo gap species could be rejoined. Exiting.")
        return
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 5: Statistics
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    n_species = rejoined['taxon_id'].nunique()
    n_rows = len(rejoined)
    
    print(f"  Species recovered: {n_species:,} (out of {len(gap_species):,} gap species)")
    print(f"  Embedding rows: {n_rows:,}")
    print(f"  Avg points per species: {n_rows/n_species:.1f}")
    
    # Distribution of points per species
    pts_per_species = rejoined.groupby('taxon_id').size()
    print(f"\n  Points per species distribution:")
    print(f"    Min: {pts_per_species.min()}")
    print(f"    Median: {pts_per_species.median():.0f}")
    print(f"    Mean: {pts_per_species.mean():.1f}")
    print(f"    Max: {pts_per_species.max()}")
    
    for threshold in [1, 3, 5, 10, 20, 50]:
        count = (pts_per_species >= threshold).sum()
        print(f"    >= {threshold} points: {count:,} species")
    
    # Species with enough points for meaningful clustering (>= 3)
    clusterable = (pts_per_species >= 3).sum()
    print(f"\n  Species with >= 3 points (clusterable): {clusterable:,}")
    print(f"  Species with 1-2 points (single centroid): {n_species - clusterable:,}")
    
    # Remaining gap species still need GEE sampling
    still_gap = len(gap_species) - n_species
    print(f"\n  Remaining gap species (need GEE sampling): {still_gap:,}")
    
    if args.dry_run:
        print("\n[DRY RUN — no files written]")
        return
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 6: Save output
    # ─────────────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"rejoined_gap_species_{timestamp}.parquet"
    rejoined.to_parquet(output_path, index=False, compression='snappy')
    print(f"\n  Saved: {output_path}")
    print(f"  Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'phase': 'A',
        'description': 'Gap species recovered via pixel rejoin from v4 data',
        'v4_parquet': str(V4_PARQUET),
        'occ_parquet': str(OCC_PARQUET),
        'gap_species_total': len(gap_species),
        'species_recovered': n_species,
        'rows_output': n_rows,
        'species_still_needing_gee': still_gap,
        'coord_precision_dp': COORD_PRECISION,
        'notes': [
            'No GEE calls made — pure data join',
            'Embeddings inherited from v4 pixel matches',
            'Most recent year embedding used for multi-year pixels',
            f'Output compatible with v4 schema for clustering pipeline',
        ]
    }
    
    metadata_path = OUTPUT_DIR / f"rejoin_metadata_{timestamp}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata: {metadata_path}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 7: Cluster and load (unless --output-only)
    # ─────────────────────────────────────────────────────────────────────
    if args.output_only:
        print("\n[--output-only: Skipping clustering and DB load]")
        print(f"\nNext step: Run clustering on {output_path}")
        print(f"  python3 run_clustering_v4.py  # with path adjusted to include this file")
        return
    
    print("\nSTEP 7: Clustering rejoined species...")
    try:
        from run_clustering_v4 import cluster_species, save_clusters_batch, safe_float, safe_mean, safe_std
        import psycopg2
        
        conn = psycopg2.connect(dbname="treekipedia")
        
        species_list = rejoined.groupby('taxon_id').size().sort_values(ascending=False)
        print(f"  Clustering {len(species_list):,} species...")
        
        batch_data = []
        processed = 0
        total_centroids = 0
        
        for taxon_id, count in species_list.items():
            sp_df = rejoined[rejoined['taxon_id'] == taxon_id]
            
            # Deduplicate by location (not pixel-year)
            sp_dedup = sp_df.drop_duplicates(subset=['latitude', 'longitude'])
            
            clusters = cluster_species(sp_dedup)
            batch_data.append((taxon_id, clusters))
            total_centroids += len(clusters)
            processed += 1
            
            if processed % 100 == 0:
                save_clusters_batch(conn, batch_data)
                batch_data = []
                print(f"    Processed {processed:,}/{len(species_list):,} species, {total_centroids:,} centroids")
        
        # Save remaining batch
        if batch_data:
            save_clusters_batch(conn, batch_data)
        
        conn.close()
        
        print(f"\n  Clustering complete!")
        print(f"  Species clustered: {processed:,}")
        print(f"  Centroids created: {total_centroids:,}")
        print(f"  Loaded to: species_habitat_centroids table")
        
    except ImportError as e:
        print(f"\n  Could not import clustering module: {e}")
        print(f"  Run clustering manually on: {output_path}")
    except Exception as e:
        print(f"\n  Clustering/loading error: {e}")
        print(f"  Data saved to: {output_path}")
        print(f"  You can run clustering separately.")
    
    print("\n" + "=" * 70)
    print("PHASE A COMPLETE")
    print("=" * 70)
    print(f"  Species with embeddings: {17924 + n_species:,} (was 17,924)")
    print(f"  Next: Phase B (re-cluster for better regional coverage)")
    print(f"  Then: Phase C (GEE sampling for remaining {still_gap:,} species)")


if __name__ == '__main__':
    main()
