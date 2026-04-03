#!/usr/bin/env python3
"""
Load Individual Occurrence Embeddings for k-NN Prediction
==========================================================

Populates species_occurrence_embeddings table with individual occurrence 
embeddings from v4 parquet + Phase A rejoined data, enriched with GBIF 
provenance metadata (coordinate uncertainty, establishment means, observation 
year) joined from the full 96M-row occurrence parquet.

Each occurrence gets a composite quality_weight (0-1) combining:
  - Coordinate uncertainty penalty (high uncertainty = lower weight)
  - Temporal match quality (how close emb_year is to occurrence_year)
  - Spatial density downweighting (oversampled areas get lower weight)
  - Source type classification (pixel-accurate vs triangulated vs interpolated)

These weights are stored per-row so they can be tuned at query time without
reloading data. The k-NN prediction query uses:
  vote_weight = similarity * density_weight * quality_weight * idf_weight

The HNSW index enables sub-10ms nearest neighbor search across ~3M vectors.
IDF weights (1/log(1+count)) are pre-computed per species to correct common 
species bias during query-time vote aggregation.

Reference: MASTER_PREDICTION_ARCHITECTURE_3.md Section 4

Usage:
    python3 load_knn_embeddings.py                # Full load
    python3 load_knn_embeddings.py --dry-run      # Show stats only
    python3 load_knn_embeddings.py --skip-index    # Load data, skip HNSW build
    python3 load_knn_embeddings.py --sample 100000 # Load subset for testing
    python3 load_knn_embeddings.py --skip-provenance  # Skip 96M join (faster, no quality metadata)

Author: Treekipedia Team
Created: February 11, 2026
Updated: February 11, 2026 — Added provenance join + quality_weight
"""

import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from pathlib import Path
from math import radians, cos, sin, asin, sqrt, log
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
PHASE_A_DIR = SCRIPT_DIR / "expansion_phase_a"
PHASE_C_PARQUET = SCRIPT_DIR / "expansion_phase_c/phase_c_knn_ready.parquet"
FULL_OCC_PARQUET = PROJECT_ROOT / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"
EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]
DB_NAME = "treekipedia"
BATCH_SIZE = 50000  # Rows per INSERT batch

# Join tolerance: lat/lon rounded to this many decimal places for matching
# 3dp = ~111m at equator. Balances join rate vs false matches.
JOIN_PRECISION_DP = 3


# =============================================================================
# QUALITY WEIGHT COMPUTATION
# =============================================================================

def compute_quality_weight(coord_uncertainty_m, emb_year, occurrence_year, 
                           establishment_means, source_type):
    """
    Compute composite quality weight (0-1) for a single occurrence.
    
    Components (multiplicative):
    1. Coordinate uncertainty: penalize records with high spatial uncertainty
    2. Temporal match: penalize when satellite year differs from observation year
    3. Source type: pixel-accurate > triangulated > interpolated
    
    All components are 0-1, multiplied together. Defaults to moderate quality
    when metadata is missing (NULL = 0.7 for uncertainty, 1.0 for temporal).
    
    These weights are STORED per-row. At query time, you can override or
    re-weight them without reloading:
      effective_weight = quality_weight^alpha  (alpha=0 ignores quality, alpha=2 amplifies it)
    """
    w = 1.0
    
    # --- Component 1: Coordinate Uncertainty ---
    # GPS-grade (<30m) = 1.0, moderate (<1km) = 0.85, coarse (<10km) = 0.5, 
    # very coarse (>10km) = 0.2, unknown = 0.7
    if coord_uncertainty_m is None or np.isnan(coord_uncertainty_m):
        w *= 0.7  # Unknown — assume moderate
    elif coord_uncertainty_m <= 30:
        w *= 1.0   # GPS-grade
    elif coord_uncertainty_m <= 100:
        w *= 0.95  # Good (survey-grade)
    elif coord_uncertainty_m <= 1000:
        w *= 0.85  # Moderate (many GBIF records)
    elif coord_uncertainty_m <= 10000:
        w *= 0.5   # Coarse (county-level)
    elif coord_uncertainty_m <= 100000:
        w *= 0.2   # Very coarse (state-level)
    else:
        w *= 0.05  # Essentially useless (>100km)
    
    # --- Component 2: Temporal Match ---
    # How well does the satellite composite year match the observation year?
    # Perfect match = 1.0, 5 years off = 0.85, 20 years off = 0.5
    if (emb_year is not None and occurrence_year is not None and 
        not np.isnan(emb_year) and not np.isnan(occurrence_year) and
        emb_year > 0 and occurrence_year > 0):
        year_gap = abs(int(emb_year) - int(occurrence_year))
        if year_gap == 0:
            w *= 1.0
        elif year_gap <= 2:
            w *= 0.95  # Very close
        elif year_gap <= 5:
            w *= 0.85  # Acceptable
        elif year_gap <= 10:
            w *= 0.7   # Getting stale
        elif year_gap <= 20:
            w *= 0.5   # Old observation, newer satellite or vice versa
        else:
            w *= 0.3   # >20 year gap — land cover likely changed
    # If either year is missing, no penalty (we can't assess)
    
    # --- Component 3: Source Type ---
    if source_type == 'pixel_accurate':
        w *= 1.0     # Gold standard: satellite year == observation year, no disturbance
    elif source_type == 'pixel_disturbed':
        w *= 0.8     # Accurate year match, but site is disturbed (still informative)
    elif source_type == 'undisturbed_pre2017':
        w *= 0.75    # Temporal mismatch but land likely unchanged
    elif source_type == 'triangulated':
        w *= 0.6     # Borrowed embedding from nearby pixel
    elif source_type == 'disturbed_pre2017':
        w *= 0.15    # WRONG: embedding shows post-disturbance, tree was in pre-disturbance habitat
    # Unknown source_type gets no penalty
    
    return round(max(0.01, min(1.0, w)), 4)


def classify_source_type(emb_year, occurrence_year, data_regime, loss, lossyear):
    """
    Classify how the embedding was generated relative to the observation:
    
    - 'pixel_accurate':     emb_year == occurrence_year, no disturbance.
                            The satellite fingerprint matches what the tree actually experienced.
                            
    - 'pixel_disturbed':    emb_year == occurrence_year, BUT Hansen loss detected at this pixel.
                            The tree was observed at a site that has been/is being disturbed.
                            Embedding is accurate but represents a degraded environment.
                            
    - 'undisturbed_pre2017': Observation was pre-2017, satellite composite is 2017+,
                            but NO Hansen loss detected. The land likely hasn't changed much.
                            Embedding is a reasonable proxy.
                            
    - 'disturbed_pre2017':  Observation was pre-2017, satellite composite is 2017+,
                            AND Hansen loss detected between observation and satellite year.
                            Embedding is WRONG — shows current degraded state, not original forest.
                            These should be heavily downweighted or excluded.
                            
    - 'triangulated':       Phase A GEE-sampled data, or other temporal mismatch.
                            Embedding borrowed from a nearby pixel at a different time.
    """
    # Safe value checks
    def _safe_int(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    
    _emb = _safe_int(emb_year)
    _occ = _safe_int(occurrence_year)
    _loss = _safe_int(loss)
    _lossyr = _safe_int(lossyear)
    
    has_loss = _loss is not None and _loss > 0
    # Hansen lossyear is encoded as years since 2000 (1=2001, 23=2023)
    loss_actual_year = 2000 + _lossyr if _lossyr and _lossyr > 0 else None
    
    # Phase C data: emb_year=2017 (fixed AE vintage), embeddings may have been
    # swapped with C3 undisturbed reference for disturbed pixels.
    # For disturbed pixels, the embedding now represents a nearby undisturbed
    # reference pixel — NOT the degraded site. This is intentional: the Recommender
    # wants "what SHOULD grow here" not "what the degraded site looks like now."
    if data_regime == 3:
        if _occ and _emb and abs(_emb - _occ) <= 1:
            if has_loss:
                return 'pixel_disturbed'     # Year-matched but disturbed; embedding is C3 reference
            return 'pixel_accurate'          # Year-matched, no disturbance
        if _occ and _emb and _occ < _emb - 1:
            if has_loss:
                # Embedding is C3 undisturbed reference — treat as "reference_proxy"
                # NOT disturbed_pre2017 (which gets 0.15 weight for bad embeddings)
                # The embedding is good, just the site history is disturbed
                return 'pixel_disturbed'     # Moderate weight — embedding is reference quality
            return 'undisturbed_pre2017'     # Pre-2017 obs, no loss, land likely unchanged
        # Default for Phase C
        if has_loss:
            return 'pixel_disturbed'
        return 'pixel_accurate'
    
    # Phase A data = borrowed embedding from a v4 pixel at a nearby location
    if data_regime == 2:
        # Even Phase A can be categorized by disturbance
        if has_loss and _occ and loss_actual_year:
            if _occ < loss_actual_year:
                return 'disturbed_pre2017'  # Observed before disturbance, embedding is post-disturbance
        if _occ and _emb and _occ < _emb - 1:
            if has_loss:
                return 'disturbed_pre2017'
            return 'undisturbed_pre2017'
        return 'triangulated'
    
    # V4 data: emb_year always == orig_year (confirmed: 100% match)
    if _emb and _occ:
        year_gap = abs(_emb - _occ)
        
        if year_gap <= 1:
            # Pixel-accurate: satellite year matches observation year
            if has_loss:
                return 'pixel_disturbed'   # Accurate, but site is disturbed
            return 'pixel_accurate'        # Gold standard
        
        # Temporal mismatch (shouldn't happen in v4, but defensive)
        if has_loss and loss_actual_year and _occ < loss_actual_year:
            return 'disturbed_pre2017'
        if has_loss:
            return 'disturbed_pre2017'     # Loss detected, observation predates satellite
        return 'undisturbed_pre2017'       # No loss, temporal mismatch
    
    # Default: v4 with no occurrence_year joined (5% unmatched from GBIF join)
    # These are v4 rows so emb_year == orig_year by construction
    if has_loss:
        return 'pixel_disturbed'
    return 'pixel_accurate'


# =============================================================================
# DENSITY WEIGHTING
# =============================================================================

def compute_density_weights(lats, lons, cell_size_deg=0.01):
    """
    Compute inverse-density weights at ~1km grid cells.
    High-density areas (research stations, cities) get lower weight.
    """
    n = len(lats)
    if n < 10:
        return np.ones(n)
    
    cell_x = (lons / cell_size_deg).astype(np.int32)
    cell_y = (lats / cell_size_deg).astype(np.int32)
    cell_keys = cell_x * 1000000 + cell_y
    
    key_series = pd.Series(cell_keys)
    counts = key_series.map(key_series.value_counts()).values.astype(float)
    
    weights = 1.0 / np.log1p(counts)
    if weights.max() > 0:
        weights = weights / weights.max()
    
    return weights


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 2 * 6371 * asin(sqrt(a))


def compute_geographic_extent(lats, lons, sample_size=200):
    """Estimate max pairwise distance (km) from a sample of points."""
    n = len(lats)
    if n < 2:
        return 0.0
    if n > sample_size:
        idx = np.random.choice(n, sample_size, replace=False)
        lats, lons = lats[idx], lons[idx]
        n = sample_size
    
    max_dist = 0.0
    # Check extremes
    for arr in [lats, lons]:
        extremes = [np.argmin(arr), np.argmax(arr)]
        for i in extremes:
            for j in range(n):
                if i != j:
                    d = haversine_km(lats[i], lons[i], lats[j], lons[j])
                    max_dist = max(max_dist, d)
    return max_dist


# =============================================================================
# PROVENANCE JOIN
# =============================================================================

def join_provenance(all_data, full_occ_path, join_dp=JOIN_PRECISION_DP):
    """
    Join GBIF provenance metadata from the full 96M occurrence parquet
    into the embedding DataFrame.
    
    Memory-optimized: reads GBIF file in chunks, filters against
    V4+Phase A join keys to avoid loading 13 GB into memory.
    
    Join strategy: taxon_id + rounded(lat, join_dp) + rounded(lon, join_dp)
    This matches occurrences that are within ~111m at the equator (3dp).
    
    For multiple matches at the same rounded location (e.g. multiple observations
    of same species at same spot in different years), we take the one with:
    1. Lowest coordinate uncertainty (best precision)
    2. Most recent year (tie-breaker)
    
    Returns the enriched DataFrame with provenance columns added.
    """
    import gc
    
    print(f"\n  Provenance join (memory-optimized chunked read)...")
    print(f"    File: {full_occ_path.name}")
    
    # Build join key set from all_data for fast filtering
    all_data['_join_lat'] = all_data['latitude'].round(join_dp)
    all_data['_join_lon'] = all_data['longitude'].round(join_dp)
    join_keys = set(
        all_data['taxon_id'].astype(str) + '_' +
        all_data['_join_lat'].astype(str) + '_' +
        all_data['_join_lon'].astype(str)
    )
    print(f"    Join key set: {len(join_keys):,} unique (taxon_id, lat3dp, lon3dp)")
    
    # Read GBIF in chunks, keep only rows matching join keys
    occ_cols = ['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year',
                'coordinateUncertaintyInMeters', 'establishmentMeans', 'gbifID']
    
    pf = pq.ParquetFile(str(full_occ_path))
    matched_chunks = []
    total_scanned = 0
    total_matched = 0
    CHUNK_SIZE = 2_000_000
    
    for batch in pf.iter_batches(batch_size=CHUNK_SIZE, columns=occ_cols):
        chunk = batch.to_pandas()
        total_scanned += len(chunk)
        
        # Round and build join keys for this chunk
        chunk['_join_lat'] = chunk['decimalLatitude'].round(join_dp)
        chunk['_join_lon'] = chunk['decimalLongitude'].round(join_dp)
        chunk['_jk'] = (
            chunk['taxon_id'].astype(str) + '_' +
            chunk['_join_lat'].astype(str) + '_' +
            chunk['_join_lon'].astype(str)
        )
        
        # Filter: only keep rows whose join key exists in our embedding data
        mask = chunk['_jk'].isin(join_keys)
        matched = chunk[mask].drop(columns=['_jk'])
        total_matched += len(matched)
        
        if len(matched) > 0:
            matched_chunks.append(matched)
        
        del chunk, mask, matched
        if total_scanned % 10_000_000 < CHUNK_SIZE:
            print(f"    Scanned {total_scanned:,}, matched {total_matched:,}")
    
    del join_keys
    gc.collect()
    
    if not matched_chunks:
        print(f"    WARNING: No GBIF matches found!")
        all_data['occurrence_year'] = None
        all_data['coordinate_uncertainty_m'] = None
        all_data['establishment_means'] = None
        all_data['gbif_id'] = None
        all_data = all_data.drop(columns=['_join_lat', '_join_lon'])
        return all_data
    
    occ = pd.concat(matched_chunks, ignore_index=True)
    del matched_chunks
    gc.collect()
    
    occ_mem_mb = occ.memory_usage(deep=True).sum() / 1024**2
    print(f"    Matched GBIF rows: {len(occ):,} ({occ_mem_mb:.0f} MB)")
    
    # Rename columns for consistency
    occ = occ.rename(columns={
        'decimalLatitude': 'latitude',
        'decimalLongitude': 'longitude',
        'year': 'occurrence_year',
        'coordinateUncertaintyInMeters': 'coordinate_uncertainty_m',
        'establishmentMeans': 'establishment_means',
        'gbifID': 'gbif_id',
    })
    
    # Deduplicate occurrences: for same species at same rounded location,
    # keep the one with lowest coordinate uncertainty (best quality).
    occ['_sort_unc'] = occ['coordinate_uncertainty_m'].fillna(999999)
    occ['_sort_year'] = occ['occurrence_year'].fillna(0)
    occ = occ.sort_values(['taxon_id', '_join_lat', '_join_lon', '_sort_unc', '_sort_year'],
                           ascending=[True, True, True, True, False])
    occ = occ.drop_duplicates(subset=['taxon_id', '_join_lat', '_join_lon'], keep='first')
    occ = occ.drop(columns=['_sort_unc', '_sort_year', 'latitude', 'longitude'])
    
    print(f"    Deduplicated to {len(occ):,} unique (taxon_id, location) combos")
    
    # Merge
    before_merge = len(all_data)
    merged = all_data.merge(
        occ[['taxon_id', '_join_lat', '_join_lon', 'occurrence_year', 
             'coordinate_uncertainty_m', 'establishment_means', 'gbif_id']],
        on=['taxon_id', '_join_lat', '_join_lon'],
        how='left'
    )
    del occ
    gc.collect()
    
    # Check join rate
    matched_count = merged['occurrence_year'].notna().sum()
    match_pct = matched_count / len(merged) * 100
    print(f"    Join result: {matched_count:,}/{len(merged):,} rows matched ({match_pct:.1f}%)")
    
    # Provenance stats
    has_uncertainty = merged['coordinate_uncertainty_m'].notna().sum()
    has_establishment = (merged['establishment_means'].notna() & (merged['establishment_means'] != '')).sum()
    has_year = merged['occurrence_year'].notna().sum()
    print(f"    Has coordinate_uncertainty: {has_uncertainty:,} ({has_uncertainty/len(merged)*100:.1f}%)")
    print(f"    Has establishment_means: {has_establishment:,} ({has_establishment/len(merged)*100:.1f}%)")
    print(f"    Has occurrence_year: {has_year:,} ({has_year/len(merged)*100:.1f}%)")
    
    if has_establishment > 0:
        est_counts = merged['establishment_means'].value_counts(dropna=False).head(10)
        print(f"    Establishment means distribution:")
        for val, count in est_counts.items():
            print(f"      {val!r}: {count:,}")
    
    # Clean up join keys
    merged = merged.drop(columns=['_join_lat', '_join_lon'])
    
    # Verify no row duplication from merge
    if len(merged) != before_merge:
        print(f"    WARNING: Merge changed row count from {before_merge:,} to {len(merged):,}!")
        print(f"    De-duplicating (keeping first)...")
        merged = merged.drop_duplicates(subset=['taxon_id', 'latitude', 'longitude', 'emb_year'], keep='first')
        print(f"    After dedup: {len(merged):,} rows")
    
    return merged


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Load occurrence embeddings for k-NN prediction')
    parser.add_argument('--dry-run', action='store_true', help='Show stats only, no DB writes')
    parser.add_argument('--skip-index', action='store_true', help='Skip HNSW index build')
    parser.add_argument('--skip-provenance', action='store_true', help='Skip 96M provenance join (faster load, no quality metadata)')
    parser.add_argument('--sample', type=int, default=None, help='Load only N rows (for testing)')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help=f'INSERT batch size (default {BATCH_SIZE})')
    parser.add_argument('--phase-c-chunk-size', type=int, default=1_000_000,
                        help='Process Phase C in chunks of N rows to limit memory (default 1M)')
    args = parser.parse_args()
    
    start_time = time.time()
    
    print("=" * 70)
    print("LOAD k-NN OCCURRENCE EMBEDDINGS (v2 — with provenance)")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Provenance join: {'ENABLED' if not args.skip_provenance else 'DISABLED'}")
    print()
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 1: Load V4 + Phase A embedding data (fits in 18GB RAM)
    # Phase C is loaded in chunks later to avoid OOM
    # ─────────────────────────────────────────────────────────────────────
    print("STEP 1: Loading V4 + Phase A embedding data...")
    
    v4 = pq.read_table(V4_PARQUET).to_pandas()
    print(f"  V4: {len(v4):,} rows, {v4['taxon_id'].nunique():,} species")
    
    # Tag data regime
    v4['data_regime'] = 1
    
    # Load Phase A rejoined data
    phase_a_files = list(PHASE_A_DIR.glob("rejoined_gap_species_*.parquet")) if PHASE_A_DIR.exists() else []
    if phase_a_files:
        phase_a = pd.concat([pd.read_parquet(f) for f in phase_a_files])
        phase_a['data_regime'] = 2
        print(f"  Phase A: {len(phase_a):,} rows, {phase_a['taxon_id'].nunique():,} species")
        all_data = pd.concat([v4, phase_a], ignore_index=True)
    else:
        print("  Phase A: No data found")
        all_data = v4
    
    del v4  # Free memory
    if phase_a_files:
        del phase_a
    
    # Drop rows with null taxon_id
    null_taxon = all_data['taxon_id'].isna().sum()
    if null_taxon > 0:
        print(f"  Dropping {null_taxon:,} rows with null taxon_id")
        all_data = all_data.dropna(subset=['taxon_id'])
    
    # Build dedup key set from V4+Phase A for later Phase C dedup
    # Key includes emb_year: multi-year observations at same pixel are DIFFERENT
    # occurrences with different embeddings — keep them all. Only true dupes
    # (same species, same pixel, same year) are removed.
    print("  Building dedup key set from V4+Phase A...")
    all_data['_dedup_key'] = (
        all_data['taxon_id'].astype(str) + '_' +
        (all_data['latitude'] * 10000).round().astype(int).astype(str) + '_' +
        (all_data['longitude'] * 10000).round().astype(int).astype(str) + '_' +
        all_data['emb_year'].fillna(0).astype(int).astype(str)
    )
    before_dedup = len(all_data)
    all_data = all_data.drop_duplicates(subset=['_dedup_key'], keep='first')
    existing_keys = set(all_data['_dedup_key'])
    all_data = all_data.drop(columns=['_dedup_key'])
    print(f"  V4+Phase A (deduped): {len(all_data):,} rows ({before_dedup - len(all_data):,} true dupes removed)")
    print(f"  Species: {all_data['taxon_id'].nunique():,}")
    
    if args.sample:
        all_data = all_data.sample(n=min(args.sample, len(all_data)), random_state=42)
        print(f"  Sampled: {len(all_data):,} rows")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 1b: Join provenance metadata from full 96M occurrence file
    # ─────────────────────────────────────────────────────────────────────
    if not args.skip_provenance and FULL_OCC_PARQUET.exists():
        print("\nSTEP 1b: Joining GBIF provenance metadata...")
        all_data = join_provenance(all_data, FULL_OCC_PARQUET)
    elif args.skip_provenance:
        print("\nSTEP 1b: Skipping provenance join (--skip-provenance)")
        all_data['occurrence_year'] = None
        all_data['coordinate_uncertainty_m'] = None
        all_data['establishment_means'] = None
        all_data['gbif_id'] = None
    else:
        print(f"\nSTEP 1b: Full occurrence parquet not found at {FULL_OCC_PARQUET}")
        print("  Proceeding without provenance metadata")
        all_data['occurrence_year'] = None
        all_data['coordinate_uncertainty_m'] = None
        all_data['establishment_means'] = None
        all_data['gbif_id'] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 1c: Classify source types and compute quality weights
    # ─────────────────────────────────────────────────────────────────────
    # Resolve the authoritative observation year:
    # - orig_year (from embedding parquet) is the year AlphaEarth used for this record
    # - occurrence_year (from GBIF join) may be a DIFFERENT observation at the same location
    # - Use orig_year when available (>0), fall back to GBIF occurrence_year
    print("\nSTEP 1c: Resolving observation years (vectorized)...")
    
    # Vectorized resolve_obs_year: prefer orig_year, fall back to occurrence_year
    orig = pd.to_numeric(all_data.get('orig_year'), errors='coerce')
    occ = pd.to_numeric(all_data.get('occurrence_year'), errors='coerce')
    all_data['resolved_obs_year'] = orig.where(orig > 0, other=occ.where(occ > 0))
    
    resolved_from_orig = all_data['resolved_obs_year'].notna().sum()
    print(f"  Resolved observation year for {resolved_from_orig:,}/{len(all_data):,} rows")
    
    print("\nSTEP 1d: Computing source types and quality weights (vectorized)...")
    
    # --- Vectorized classify_source_type ---
    _emb = pd.to_numeric(all_data['emb_year'], errors='coerce').fillna(0).astype(int)
    _occ = all_data['resolved_obs_year'].fillna(0).astype(int)
    _loss = pd.to_numeric(all_data.get('loss', 0), errors='coerce').fillna(0).astype(int)
    _lossyr = pd.to_numeric(all_data.get('lossyear', 0), errors='coerce').fillna(0).astype(int)
    _regime = pd.to_numeric(all_data.get('data_regime', 1), errors='coerce').fillna(1).astype(int)
    
    has_loss = _loss > 0
    year_gap = (_emb - _occ).abs()
    pre_emb = (_occ > 0) & (_emb > 0) & (_occ < _emb - 1)
    year_matched = (_occ > 0) & (_emb > 0) & (year_gap <= 1)
    
    # Default: pixel_accurate
    source_type = pd.Series('pixel_accurate', index=all_data.index)
    
    # V4/default (regime 1): year-matched
    source_type = source_type.where(~(year_matched & has_loss), 'pixel_disturbed')
    source_type = source_type.where(~(pre_emb & ~has_loss & (_regime == 1)), 'undisturbed_pre2017')
    source_type = source_type.where(~(pre_emb & has_loss & (_regime == 1)), 'disturbed_pre2017')
    source_type = source_type.where(~((_occ == 0) & has_loss & (_regime == 1)), 'pixel_disturbed')
    
    # Phase C (regime 3): disturbed pixels have swapped embeddings — never disturbed_pre2017
    r3 = _regime == 3
    source_type = source_type.where(~(r3 & year_matched & ~has_loss), 'pixel_accurate')
    source_type = source_type.where(~(r3 & year_matched & has_loss), 'pixel_disturbed')
    source_type = source_type.where(~(r3 & pre_emb & ~has_loss), 'undisturbed_pre2017')
    source_type = source_type.where(~(r3 & pre_emb & has_loss), 'pixel_disturbed')
    source_type = source_type.where(~(r3 & (_occ == 0) & has_loss), 'pixel_disturbed')
    source_type = source_type.where(~(r3 & (_occ == 0) & ~has_loss), 'pixel_accurate')
    
    # Phase A (regime 2): triangulated by default
    r2 = _regime == 2
    source_type = source_type.where(~r2, 'triangulated')
    source_type = source_type.where(~(r2 & pre_emb & has_loss), 'disturbed_pre2017')
    source_type = source_type.where(~(r2 & pre_emb & ~has_loss), 'undisturbed_pre2017')
    
    all_data['source_type'] = source_type
    
    source_counts = all_data['source_type'].value_counts()
    print(f"  Source type distribution:")
    for st, count in source_counts.items():
        print(f"    {st}: {count:,} ({count/len(all_data)*100:.1f}%)")
    
    # --- Vectorized compute_quality_weight ---
    w = pd.Series(1.0, index=all_data.index)
    
    # Component 1: Coordinate Uncertainty
    cu = pd.to_numeric(all_data.get('coordinate_uncertainty_m'), errors='coerce')
    w = w * np.where(cu.isna(), 0.7,
            np.where(cu <= 30, 1.0,
            np.where(cu <= 100, 0.95,
            np.where(cu <= 1000, 0.85,
            np.where(cu <= 10000, 0.5,
            np.where(cu <= 100000, 0.2, 0.05))))))
    
    # Component 2: Temporal Match
    has_years = (_emb > 0) & (_occ > 0)
    yg = year_gap.astype(float)
    temporal_w = np.where(~has_years, 1.0,
                 np.where(yg == 0, 1.0,
                 np.where(yg <= 2, 0.95,
                 np.where(yg <= 5, 0.85,
                 np.where(yg <= 10, 0.7,
                 np.where(yg <= 20, 0.5, 0.3))))))
    w = w * temporal_w
    
    # Component 3: Source Type
    st_map = {
        'pixel_accurate': 1.0,
        'pixel_disturbed': 0.8,
        'undisturbed_pre2017': 0.75,
        'triangulated': 0.6,
        'disturbed_pre2017': 0.15,
    }
    st_w = all_data['source_type'].map(st_map).fillna(1.0)
    w = w * st_w
    
    all_data['quality_weight'] = w.clip(0.01, 1.0).round(4)
    
    print(f"  Quality weight stats:")
    print(f"    Mean: {all_data['quality_weight'].mean():.3f}")
    print(f"    Median: {all_data['quality_weight'].median():.3f}")
    print(f"    Min: {all_data['quality_weight'].min():.3f}")
    print(f"    Max: {all_data['quality_weight'].max():.3f}")
    print(f"    Std: {all_data['quality_weight'].std():.3f}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 2: Compute density weights per species
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 2: Computing density weights...")
    
    all_data['density_weight'] = 1.0
    species_groups = all_data.groupby('taxon_id')
    n_species = len(species_groups)
    
    processed = 0
    for taxon_id, group in species_groups:
        if len(group) >= 10:
            weights = compute_density_weights(
                group['latitude'].values,
                group['longitude'].values
            )
            all_data.loc[group.index, 'density_weight'] = weights
        processed += 1
        if processed % 5000 == 0:
            print(f"    {processed:,}/{n_species:,} species weighted")
    
    print(f"  Done. Mean density weight: {all_data['density_weight'].mean():.3f}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 3: Accumulate species stats from V4+Phase A
    # (Phase C stats are merged in Step 4b; final stats computed in Step 5)
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 3: Accumulating species stats from V4+Phase A...")
    
    # Lightweight per-species accumulators (survive Phase C processing)
    # For geographic extent: store bbox + sampled points (max 200 per species)
    EXTENT_SAMPLE_SIZE = 200
    species_stats_accum = {}  # taxon_id -> {count, unique_pixels, provenance_sum, provenance_count, lat_min, lat_max, lon_min, lon_max, sample_lats, sample_lons}
    
    processed = 0
    for taxon_id, group in species_groups:
        n = len(group)
        lats = group['latitude'].values
        lons = group['longitude'].values
        unique_pixels = group[['latitude', 'longitude']].drop_duplicates().shape[0]
        provenance_count = group['coordinate_uncertainty_m'].notna().sum()
        
        # Store bbox + sampled points for extent calculation
        sample_idx = np.random.choice(n, min(n, EXTENT_SAMPLE_SIZE), replace=False) if n > EXTENT_SAMPLE_SIZE else np.arange(n)
        
        species_stats_accum[taxon_id] = {
            'count': n,
            'unique_pixels': unique_pixels,
            'provenance_sum': int(provenance_count),
            'provenance_total': n,
            'lat_min': float(lats.min()),
            'lat_max': float(lats.max()),
            'lon_min': float(lons.min()),
            'lon_max': float(lons.max()),
            'sample_lats': lats[sample_idx].tolist(),
            'sample_lons': lons[sample_idx].tolist(),
        }
        
        processed += 1
        if processed % 5000 == 0:
            print(f"    {processed:,}/{n_species:,} species accumulated")
    
    print(f"  V4+Phase A species accumulated: {len(species_stats_accum):,}")
    
    if args.dry_run:
        print(f"\n[DRY RUN — no database changes]")
        print(f"  Would load {len(all_data):,} V4+Phase A occurrence embeddings")
        has_phase_c = PHASE_C_PARQUET.exists()
        if has_phase_c:
            pc_meta = pq.read_metadata(str(PHASE_C_PARQUET))
            print(f"  Would also load ~{pc_meta.num_rows:,} Phase C rows (pre-dedup)")
        print(f"  Species stats accumulated (V4+PhA): {len(species_stats_accum):,}")
        elapsed = time.time() - start_time
        print(f"  Elapsed: {elapsed:.1f}s")
        
        # Show sample quality weights
        print(f"\n  Sample quality weight distribution by source_type:")
        for st in all_data['source_type'].unique():
            subset = all_data[all_data['source_type'] == st]['quality_weight']
            print(f"    {st}: mean={subset.mean():.3f}, median={subset.median():.3f}, n={len(subset):,}")
        
        print(f"\n  Sample establishment_means breakdown:")
        est = all_data['establishment_means'].value_counts(dropna=False).head(10)
        for val, count in est.items():
            print(f"    {val!r}: {count:,}")
        return
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 4: Load to database (V4+Phase A, then Phase C in chunks)
    # ─────────────────────────────────────────────────────────────────────
    total_rows = len(all_data)
    has_phase_c = PHASE_C_PARQUET.exists()
    if has_phase_c:
        pc_meta = pq.read_metadata(str(PHASE_C_PARQUET))
        total_rows += pc_meta.num_rows  # Approximate (pre-dedup)
    
    print(f"\nSTEP 4: Loading to species_occurrence_embeddings (~{total_rows:,} rows)...")
    
    conn = psycopg2.connect(dbname=DB_NAME)
    cur = conn.cursor()
    
    # Clear existing data
    cur.execute("TRUNCATE species_occurrence_embeddings RESTART IDENTITY;")
    cur.execute("TRUNCATE species_occurrence_stats;")
    conn.commit()
    print("  Cleared existing data")
    
    from io import StringIO
    from math import isnan as _isnan
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import multiprocessing as mp
    
    N_WORKERS = min(4, mp.cpu_count() - 1)  # 4 parallel PostgreSQL connections
    
    COPY_COLS = ('taxon_id', 'embedding', 'latitude', 'longitude', 'emb_year',
                 'elevation', 'treecover2000', 'loss', 'lossyear', 'density_weight',
                 'data_regime', 'coordinate_uncertainty_m', 'establishment_means',
                 'occurrence_year', 'gbif_id', 'source_type', 'quality_weight')
    COPY_SQL = f"COPY species_occurrence_embeddings ({','.join(COPY_COLS)}) FROM STDIN"
    
    def _safe_col(df, col, default=0):
        """Get column as float64 numpy array, converting pandas NA -> np.nan."""
        if col in df.columns:
            arr = pd.to_numeric(df[col], errors='coerce').astype(float).values
            if not (isinstance(default, float) and _isnan(default)):
                arr = np.where(np.isnan(arr), default, arr)
            return arr
        d = np.nan if isinstance(default, float) and _isnan(default) else float(default)
        return np.full(len(df), d)
    
    def df_to_tsv_string(df):
        """Convert DataFrame to a tab-delimited string for COPY FROM.
        
        Returns the string directly (not StringIO) so it can be passed
        across process boundaries via multiprocessing.
        """
        n = len(df)
        emb_arrays = df[EMBEDDING_COLS].values
        taxon_ids = df['taxon_id'].astype(str).values
        lats = df['latitude'].values.astype(float).tolist()
        lons = df['longitude'].values.astype(float).tolist()
        
        emb_years = _safe_col(df, 'emb_year', 0).tolist()
        resolved = _safe_col(df, 'resolved_obs_year', 0)
        occ_yr = _safe_col(df, 'occurrence_year', 0)
        obs_years = np.where(resolved > 0, resolved, np.where(occ_yr > 0, occ_yr, 0)).tolist()
        
        elev = _safe_col(df, 'elevation', np.nan).tolist()
        tc = _safe_col(df, 'treecover2000', np.nan).tolist()
        loss_arr = _safe_col(df, 'loss', 0).tolist()
        lossyr = _safe_col(df, 'lossyear', 0).tolist()
        dw = _safe_col(df, 'density_weight', 1.0).tolist()
        regime = _safe_col(df, 'data_regime', 1).tolist()
        cu = _safe_col(df, 'coordinate_uncertainty_m', np.nan).tolist()
        qw = _safe_col(df, 'quality_weight', 1.0).tolist()
        gbif_arr = _safe_col(df, 'gbif_id', np.nan).tolist()
        
        est = df['establishment_means'].values if 'establishment_means' in df.columns else [None] * n
        st = df['source_type'].values if 'source_type' in df.columns else ['pixel'] * n
        
        N = '\\N'
        lines = []
        for i in range(n):
            emb_str = '[' + ','.join(f'{v:.8g}' for v in emb_arrays[i]) + ']'
            ey = str(int(emb_years[i])) if emb_years[i] > 0 else N
            oy = str(int(obs_years[i])) if obs_years[i] > 0 else N
            el = str(int(elev[i])) if not _isnan(elev[i]) else N
            tc_v = str(int(tc[i])) if not _isnan(tc[i]) else N
            lo = 'true' if loss_arr[i] > 0 else 'false'
            ly = str(int(lossyr[i])) if lossyr[i] > 0 else N
            cu_v = str(cu[i]) if not _isnan(cu[i]) else N
            gb = str(int(gbif_arr[i])) if not _isnan(gbif_arr[i]) else N
            est_v = N
            if est[i] is not None:
                try:
                    if pd.notna(est[i]):
                        s = str(est[i]).strip()
                        if s and s != 'nan':
                            est_v = s
                except (TypeError, ValueError):
                    pass
            lines.append(f'{taxon_ids[i]}\t{emb_str}\t{lats[i]}\t{lons[i]}\t{ey}\t{el}\t{tc_v}\t{lo}\t{ly}\t{dw[i]}\t{int(regime[i])}\t{cu_v}\t{est_v}\t{oy}\t{gb}\t{st[i]}\t{qw[i]}')
        
        return '\n'.join(lines) + '\n'
    
    def _copy_worker(tsv_data):
        """Worker function: opens its own DB connection and COPYs data."""
        wconn = psycopg2.connect(dbname=DB_NAME)
        wcur = wconn.cursor()
        buf = StringIO(tsv_data)
        wcur.copy_expert(COPY_SQL, buf)
        wconn.commit()
        n = tsv_data.count('\n')
        wcur.close()
        wconn.close()
        return n
    
    def insert_df_parallel(df, label):
        """Insert DataFrame using parallel COPY across N_WORKERS connections."""
        n = len(df)
        chunk_size = max(50000, n // N_WORKERS)  # At least 50K per worker
        chunks = [df.iloc[i:i+chunk_size] for i in range(0, n, chunk_size)]
        
        print(f"    {label}: {n:,} rows across {len(chunks)} chunks, {N_WORKERS} workers")
        
        # Generate TSV strings (parallel-safe: no DB connection needed)
        # This uses multiple Python processes for the CPU-intensive string building
        insert_start = time.time()
        
        # Use ThreadPoolExecutor for buffer generation (GIL-bound but I/O-free)
        # Then ProcessPoolExecutor for the actual COPY (true parallelism)
        tsv_strings = []
        gen_start = time.time()
        for i, chunk in enumerate(chunks):
            tsv_strings.append(df_to_tsv_string(chunk))
            if (i + 1) % 4 == 0 or i == len(chunks) - 1:
                elapsed_g = time.time() - gen_start
                rows_done = sum(s.count('\n') for s in tsv_strings)
                print(f"      Buffer gen: {rows_done:,}/{n:,} rows [{rows_done/max(1,elapsed_g):.0f} rows/s]")
        
        # COPY in parallel using separate DB connections
        copy_start = time.time()
        loaded = 0
        with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
            futures = {executor.submit(_copy_worker, tsv): i for i, tsv in enumerate(tsv_strings)}
            for future in as_completed(futures):
                rows = future.result()
                loaded += rows
                elapsed_c = time.time() - copy_start
                rate = loaded / max(1, elapsed_c)
                print(f"      COPY: {loaded:,}/{n:,} done [{rate:.0f} rows/s]")
        
        del tsv_strings  # Free string memory
        total_elapsed = time.time() - insert_start
        print(f"    {label} done: {loaded:,} rows in {total_elapsed:.1f}s [{loaded/max(1,total_elapsed):.0f} rows/s]")
        return loaded
    
    # --- Insert V4 + Phase A ---
    loaded = 0
    print(f"  Inserting V4+Phase A ({len(all_data):,} rows) with {N_WORKERS} parallel workers...")
    loaded = insert_df_parallel(all_data, "V4+PhaseA")
    print(f"  V4+Phase A done: {loaded:,} rows")
    
    # Free V4+Phase A memory
    del all_data
    import gc; gc.collect()
    
    # --- Insert Phase C in chunks ---
    if has_phase_c:
        print(f"\n  Loading Phase C in {args.phase_c_chunk_size:,}-row chunks...")
        pc_full = pd.read_parquet(PHASE_C_PARQUET)
        pc_full['data_regime'] = 3
        
        # Drop null taxon_ids
        pc_full = pc_full.dropna(subset=['taxon_id'])
        
        # Dedup against V4+Phase A using existing_keys set (includes emb_year)
        pc_full['_dedup_key'] = (
            pc_full['taxon_id'].astype(str) + '_' +
            (pc_full['latitude'] * 10000).round().astype(int).astype(str) + '_' +
            (pc_full['longitude'] * 10000).round().astype(int).astype(str) + '_' +
            pc_full['emb_year'].fillna(0).astype(int).astype(str)
        )
        before = len(pc_full)
        pc_full = pc_full[~pc_full['_dedup_key'].isin(existing_keys)]
        pc_full = pc_full.drop_duplicates(subset=['_dedup_key'], keep='first')
        pc_full = pc_full.drop(columns=['_dedup_key'])
        print(f"  Phase C deduped: {before:,} -> {len(pc_full):,} ({before - len(pc_full):,} overlaps removed)")
        
        # Compute source types and quality weights for Phase C
        print("  Computing Phase C source types + quality weights...")
        _emb = pd.to_numeric(pc_full['emb_year'], errors='coerce').fillna(0).astype(int)
        _orig = pd.to_numeric(pc_full.get('orig_year', 0), errors='coerce').fillna(0).astype(int)
        pc_full['resolved_obs_year'] = _orig.where(_orig > 0)
        _occ = _orig.fillna(0).astype(int)
        _loss = pd.to_numeric(pc_full.get('loss', 0), errors='coerce').fillna(0).astype(int)
        has_loss = _loss > 0
        year_gap = (_emb - _occ).abs()
        year_matched = (_occ > 0) & (_emb > 0) & (year_gap <= 1)
        pre_emb = (_occ > 0) & (_emb > 0) & (_occ < _emb - 1)
        
        # Phase C: disturbed pixels have C3 reference embeddings -> pixel_disturbed, not disturbed_pre2017
        source_type = pd.Series('pixel_accurate', index=pc_full.index)
        source_type = source_type.where(~(year_matched & has_loss), 'pixel_disturbed')
        source_type = source_type.where(~(pre_emb & ~has_loss), 'undisturbed_pre2017')
        source_type = source_type.where(~(pre_emb & has_loss), 'pixel_disturbed')
        source_type = source_type.where(~((_occ == 0) & has_loss), 'pixel_disturbed')
        pc_full['source_type'] = source_type
        
        # Quality weight (no coord_uncertainty since --skip-provenance)
        w = pd.Series(0.7, index=pc_full.index)  # Default: unknown coord uncertainty
        has_years = (_emb > 0) & (_occ > 0)
        temporal_w = np.where(~has_years, 1.0,
                     np.where(year_gap == 0, 1.0,
                     np.where(year_gap <= 2, 0.95,
                     np.where(year_gap <= 5, 0.85,
                     np.where(year_gap <= 10, 0.7,
                     np.where(year_gap <= 20, 0.5, 0.3))))))
        w = w * temporal_w
        st_map = {'pixel_accurate': 1.0, 'pixel_disturbed': 0.8, 'undisturbed_pre2017': 0.75,
                   'triangulated': 0.6, 'disturbed_pre2017': 0.15}
        w = w * pc_full['source_type'].map(st_map).fillna(1.0)
        pc_full['quality_weight'] = w.clip(0.01, 1.0).round(4)
        
        # Density weights for Phase C species
        print("  Computing Phase C density weights...")
        pc_full['density_weight'] = 1.0
        pc_groups = pc_full.groupby('taxon_id')
        n_pc_species = len(pc_groups)
        sp_done = 0
        for taxon_id, group in pc_groups:
            if len(group) >= 10:
                weights = compute_density_weights(group['latitude'].values, group['longitude'].values)
                pc_full.loc[group.index, 'density_weight'] = weights
            sp_done += 1
            if sp_done % 5000 == 0:
                print(f"    {sp_done:,}/{n_pc_species:,} Phase C species weighted")
        
        # Ensure provenance columns exist
        for col in ['coordinate_uncertainty_m', 'establishment_means', 'gbif_id', 'occurrence_year']:
            if col not in pc_full.columns:
                pc_full[col] = None
        
        # Accumulate Phase C stats into species_stats_accum
        print("  Accumulating Phase C species stats...")
        # Reuse pc_groups from density weight computation above
        sp_accum = 0
        for taxon_id, group in pc_groups:
            n = len(group)
            lats = group['latitude'].values
            lons = group['longitude'].values
            unique_pixels = group[['latitude', 'longitude']].drop_duplicates().shape[0]
            provenance_count = group['coordinate_uncertainty_m'].notna().sum()
            
            if taxon_id in species_stats_accum:
                # Merge with existing V4+Phase A stats
                existing = species_stats_accum[taxon_id]
                existing['count'] += n
                existing['unique_pixels'] += unique_pixels  # Approximate (could have overlap, but deduped above)
                existing['provenance_sum'] += int(provenance_count)
                existing['provenance_total'] += n
                existing['lat_min'] = min(existing['lat_min'], float(lats.min()))
                existing['lat_max'] = max(existing['lat_max'], float(lats.max()))
                existing['lon_min'] = min(existing['lon_min'], float(lons.min()))
                existing['lon_max'] = max(existing['lon_max'], float(lons.max()))
                # Merge sampled points (keep up to EXTENT_SAMPLE_SIZE total)
                combined_lats = existing['sample_lats'] + lats[:50].tolist()
                combined_lons = existing['sample_lons'] + lons[:50].tolist()
                if len(combined_lats) > EXTENT_SAMPLE_SIZE:
                    idx = np.random.choice(len(combined_lats), EXTENT_SAMPLE_SIZE, replace=False)
                    combined_lats = [combined_lats[i] for i in idx]
                    combined_lons = [combined_lons[i] for i in idx]
                existing['sample_lats'] = combined_lats
                existing['sample_lons'] = combined_lons
            else:
                # New species from Phase C only
                sample_idx = np.random.choice(n, min(n, EXTENT_SAMPLE_SIZE), replace=False) if n > EXTENT_SAMPLE_SIZE else np.arange(n)
                species_stats_accum[taxon_id] = {
                    'count': n,
                    'unique_pixels': unique_pixels,
                    'provenance_sum': int(provenance_count),
                    'provenance_total': n,
                    'lat_min': float(lats.min()),
                    'lat_max': float(lats.max()),
                    'lon_min': float(lons.min()),
                    'lon_max': float(lons.max()),
                    'sample_lats': lats[sample_idx].tolist(),
                    'sample_lons': lons[sample_idx].tolist(),
                }
            sp_accum += 1
            if sp_accum % 5000 == 0:
                print(f"    {sp_accum:,}/{n_pc_species:,} Phase C species stats accumulated")
        
        print(f"  Total species after Phase C merge: {len(species_stats_accum):,}")
        
        # Insert Phase C with parallel COPY
        print(f"  Inserting Phase C: {len(pc_full):,} rows with {N_WORKERS} parallel workers...")
        pc_loaded = insert_df_parallel(pc_full, "PhaseC")
        loaded += pc_loaded
        print(f"  Phase C done: {pc_loaded:,} rows")
        del pc_full
        gc.collect()
    
    # Free dedup keys
    del existing_keys
    
    print(f"  Total loaded: {loaded:,} occurrence embeddings")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 5: Compute final species stats from accumulated data + load
    # ─────────────────────────────────────────────────────────────────────
    print(f"\nSTEP 5: Computing final species stats from {len(species_stats_accum):,} species...")
    
    stats_batch = []
    sp_processed = 0
    for taxon_id, acc in species_stats_accum.items():
        n = acc['count']
        
        # Geographic extent from sampled points
        sample_lats = np.array(acc['sample_lats'])
        sample_lons = np.array(acc['sample_lons'])
        extent_km = compute_geographic_extent(sample_lats, sample_lons) if len(sample_lats) >= 2 else 0.0
        
        # IDF weight
        idf = 1.0 / log(1 + n)
        
        # Data quality score
        quality = min(1.0, log(1 + n) / log(1 + 1000))
        if extent_km > 1000:
            quality = min(1.0, quality * 1.1)
        
        # Provenance boost
        provenance_rate = acc['provenance_sum'] / acc['provenance_total'] if acc['provenance_total'] > 0 else 0
        quality = min(1.0, quality * (0.9 + 0.1 * provenance_rate))
        
        stats_batch.append((
            taxon_id,
            int(n),
            int(acc['unique_pixels']),
            100.0,  # embedding_coverage_pct — all rows have embeddings
            round(extent_km, 1),
            0,  # n_geographic_regions — computed separately if needed
            round(idf, 6),
            round(quality, 4),
        ))
        
        sp_processed += 1
        if sp_processed % 5000 == 0:
            print(f"    {sp_processed:,}/{len(species_stats_accum):,} species stats computed")
    
    print(f"  Inserting {len(stats_batch):,} species stats...")
    # Insert in batches to avoid oversized queries
    STATS_BATCH_SIZE = 5000
    for i in range(0, len(stats_batch), STATS_BATCH_SIZE):
        batch = stats_batch[i:i+STATS_BATCH_SIZE]
        execute_values(cur, """
            INSERT INTO species_occurrence_stats
            (taxon_id, total_occurrences, total_unique_pixels, embedding_coverage_pct,
             geographic_extent_km, n_geographic_regions, idf_weight, data_quality_score)
            VALUES %s
        """, batch)
        conn.commit()
    print(f"  Loaded {len(stats_batch):,} species stats")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 6: Build HNSW index
    # ─────────────────────────────────────────────────────────────────────
    if not args.skip_index:
        print(f"\nSTEP 6: Building HNSW index...")
        print("  This may take several minutes for ~3M vectors...")
        
        idx_start = time.time()
        
        # Drop old index if exists
        cur.execute("DROP INDEX IF EXISTS idx_occ_emb_hnsw;")
        conn.commit()
        
        # Build HNSW index
        # m=16: connections per layer (higher = better recall, more memory)
        # ef_construction=200: build-time search depth (higher = better quality, slower build)
        cur.execute("""
            CREATE INDEX idx_occ_emb_hnsw
            ON species_occurrence_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200);
        """)
        conn.commit()
        
        idx_elapsed = time.time() - idx_start
        print(f"  HNSW index built in {idx_elapsed:.1f}s")
    else:
        print("\nSTEP 6: Skipping HNSW index build (--skip-index)")
    
    cur.close()
    conn.close()
    
    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print("k-NN OCCURRENCE EMBEDDINGS LOADED (v2 — with provenance)")
    print(f"{'=' * 70}")
    print(f"  Occurrence embeddings: {loaded:,}")
    print(f"  Species: {len(species_stats_accum):,}")
    print(f"  Species stats: {len(stats_batch):,}")
    print(f"  HNSW index: {'Built' if not args.skip_index else 'Skipped'}")
    print(f"  Provenance join: {'Yes' if not args.skip_provenance else 'No'}")
    print(f"  Total time: {elapsed:.1f}s")
    print()
    print("  Provenance columns stored per occurrence:")
    print("    - coordinate_uncertainty_m  (GBIF spatial precision)")
    print("    - establishment_means       (native/introduced/invasive)")
    print("    - occurrence_year            (actual observation year)")
    print("    - gbif_id                    (back-reference for audit)")
    print("    - source_type                (pixel/triangulated/interpolated)")
    print("    - quality_weight             (composite 0-1, all factors)")
    print()
    print("  Weight knobs available at query time:")
    print("    vote = similarity * density_weight^a * quality_weight^b * idf_weight")
    print("    a=0: ignore spatial density  |  a=1: full density correction")
    print("    b=0: ignore quality metadata |  b=1: full quality weighting")
    print()
    print("  Next steps:")
    print("  1. Update prediction.js Channel 1 to use k-NN query")
    print("  2. Test P. radiata benchmark at Auckland NZ")
    print("  3. Wire soil + disturbance signals into scoring")


if __name__ == '__main__':
    main()
