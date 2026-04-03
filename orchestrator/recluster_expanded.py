#!/usr/bin/env python3
"""
Phase B: Re-cluster V4 Species with Adaptive K
================================================

Purpose: Fix species like P. radiata where k=3 merged geographically distinct
         regions (e.g., NZ merged into AU because cosine similarity was 0.84).
         
         The original clustering used min_k=3, max_k=10 with silhouette score.
         This script re-clusters species that likely need more clusters by:
         1. Detecting species with geographically dispersed occurrences
         2. Increasing max_k for those species
         3. Replacing their centroids in the database

How it works:
  1. Load v4 parquet + Phase A rejoined data
  2. For each species, compute geographic dispersion
  3. If occurrences span > 2000km, increase max_k proportionally
  4. Re-run weighted k-means with higher max_k
  5. Replace centroids in species_habitat_centroids table

Key insight: P. radiata has AU↔NZ cosine similarity of 0.84 — similar enough
for k=3 to merge them, but distinct enough that they should be separate clusters.
Higher k allows the algorithm to find this natural boundary.

Reference: .claude/project-management/GEE_PIPELINE_REFERENCE.md

Usage:
    python3 recluster_expanded.py                    # Re-cluster all species needing it
    python3 recluster_expanded.py --species GymPiPiPnCx50820-00  # Just P. radiata
    python3 recluster_expanded.py --dry-run           # Show which species would be re-clustered
    python3 recluster_expanded.py --min-dispersion 1000  # Lower threshold (default 2000km)

Author: Treekipedia Team
Created: February 11, 2026
"""

import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import psycopg2
from psycopg2.extras import execute_values
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from datetime import datetime
from pathlib import Path
import argparse
import json
from math import radians, cos, sin, asin, sqrt

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
V4_PARQUET = SCRIPT_DIR / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
PHASE_A_DIR = SCRIPT_DIR / "expansion_phase_a"
OUTPUT_DIR = SCRIPT_DIR / "expansion_phase_b"

EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]
DB_NAME = "treekipedia"

# Clustering parameters
DEFAULT_MIN_DISPERSION_KM = 2000  # Species spanning > this distance get more clusters
MAX_K_CAP = 15  # Maximum clusters per species


# =============================================================================
# GEOGRAPHIC UTILITIES
# =============================================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate haversine distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 2 * 6371 * asin(sqrt(a))


def compute_geographic_dispersion(lats, lons):
    """Compute the maximum pairwise distance among occurrence points.
    
    For efficiency, samples up to 200 points if there are more.
    Returns max distance in km.
    """
    n = len(lats)
    if n < 2:
        return 0.0
    
    # Subsample for large datasets
    if n > 200:
        idx = np.random.choice(n, 200, replace=False)
        lats = lats[idx]
        lons = lons[idx]
        n = 200
    
    max_dist = 0.0
    # Use corner-based heuristic: check extremes first
    extremes = []
    for arr, axis in [(lats, 0), (lons, 1)]:
        extremes.extend([np.argmin(arr), np.argmax(arr)])
    extremes = list(set(extremes))
    
    # Check distances from extreme points to all others
    for i in extremes:
        for j in range(n):
            if i != j:
                d = haversine_km(lats[i], lons[i], lats[j], lons[j])
                max_dist = max(max_dist, d)
    
    return max_dist


def adaptive_max_k(dispersion_km, n_points, base_max_k=10):
    """Determine max_k based on geographic dispersion.
    
    Logic:
    - < 2000km: keep default max_k (3-10)
    - 2000-5000km: max_k = 7-10
    - 5000-10000km: max_k = 8-12
    - > 10000km: max_k = 10-15
    
    Also capped by n_points (need at least 3 points per cluster).
    """
    if dispersion_km < 2000:
        max_k = base_max_k
    elif dispersion_km < 5000:
        max_k = max(base_max_k, 10)
    elif dispersion_km < 10000:
        max_k = max(base_max_k, 12)
    else:
        max_k = MAX_K_CAP
    
    # Cap by available data (need at least 3 points per cluster)
    max_k = min(max_k, n_points // 3)
    max_k = max(max_k, 3)  # At least 3 clusters
    
    return min(max_k, MAX_K_CAP)


# =============================================================================
# CLUSTERING (imported logic from run_clustering_v4.py)
# =============================================================================

def fast_grid_density(lats, lons, cell_size_deg=0.01):
    """Fast vectorized grid-based density calculation (~1km cells)."""
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


def weighted_kmeans(embeddings, weights, n_clusters, max_iter=50, random_state=42):
    """Weighted K-means clustering."""
    n_samples, n_features = embeddings.shape
    rng = np.random.RandomState(random_state)
    
    kmeans_init = KMeans(n_clusters=n_clusters, n_init=1, max_iter=1, random_state=random_state)
    kmeans_init.fit(embeddings)
    centroids = kmeans_init.cluster_centers_.copy()
    
    for iteration in range(max_iter):
        distances = np.linalg.norm(embeddings[:, None, :] - centroids[None, :, :], axis=2)
        labels = distances.argmin(axis=1)
        
        new_centroids = np.zeros_like(centroids)
        for k in range(n_clusters):
            mask = labels == k
            if mask.sum() > 0:
                new_centroids[k] = np.average(embeddings[mask], axis=0, weights=weights[mask])
            else:
                new_centroids[k] = embeddings[rng.randint(n_samples)]
        
        if np.linalg.norm(new_centroids - centroids) < 1e-4:
            break
        centroids = new_centroids
    
    return centroids, labels


def find_optimal_k(embeddings, weights, min_k=3, max_k=10):
    """Find optimal k using silhouette score."""
    n = len(embeddings)
    if n < min_k:
        return min(n, 3)
    
    max_k = min(max_k, n - 1)
    
    MAX_SAMPLE = 5000
    if n > MAX_SAMPLE:
        probs = weights / weights.sum()
        sample_idx = np.random.choice(n, size=MAX_SAMPLE, replace=False, p=probs)
        sample_emb = embeddings[sample_idx]
        sample_weights = weights[sample_idx]
    else:
        sample_emb = embeddings
        sample_weights = weights
    
    best_k, best_score = min_k, -1
    
    for k in range(min_k, max_k + 1):
        try:
            _, labels = weighted_kmeans(sample_emb, sample_weights, k)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(sample_emb, labels)
            if score > best_score:
                best_k, best_score = k, score
        except:
            continue
    
    return best_k


def safe_float(val):
    if val is None or pd.isna(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def safe_mean(series):
    valid = series.dropna()
    return safe_float(valid.mean()) if len(valid) > 0 else None


def safe_std(series):
    valid = series.dropna()
    return safe_float(valid.std()) if len(valid) >= 2 else None


def cluster_species_adaptive(df, min_k=3, max_k=10, max_points=20000, geo_eps_deg=5.0):
    """Cluster using geographic DBSCAN first, then embedding centroid per region.
    
    The key insight: silhouette score in embedding space can merge geographically
    distant regions if their embeddings are similar (e.g., P. radiata AU↔NZ = 0.84).
    But for prediction, we need regional centroids — a NZ query should match a NZ 
    centroid, not an AU one even if they're 84% similar.
    
    Approach:
    1. DBSCAN on (lat, lon) to find geographic regions (eps=5° ≈ 550km)
    2. For each geographic region, compute density-weighted embedding centroid
    3. Each region = one centroid (geographic regions ARE the clusters)
    4. Small noise points (DBSCAN label=-1) get assigned to nearest cluster
    """
    from sklearn.cluster import DBSCAN
    
    n_original = len(df)
    
    if n_original > max_points:
        weights_full = fast_grid_density(df['latitude'].values, df['longitude'].values)
        probs = weights_full / weights_full.sum()
        sample_idx = np.random.choice(n_original, size=max_points, replace=False, p=probs)
        df = df.iloc[sample_idx].reset_index(drop=True)
    
    embeddings = df[EMBEDDING_COLS].values
    lats = df['latitude'].values
    lons = df['longitude'].values
    n = len(embeddings)
    
    if n < 3:
        return [{
            'cluster_id': 0,
            'centroid': embeddings.mean(axis=0).tolist(),
            'occurrence_count': n,
            'is_single_cluster': True,
            'mean_elevation': safe_mean(df['elevation']) if 'elevation' in df.columns else None,
            'elevation_std': safe_std(df['elevation']) if 'elevation' in df.columns else None,
            'mean_treecover2000': safe_mean(df['treecover2000']) if 'treecover2000' in df.columns else None,
            'forest_loss_fraction': safe_mean(df['loss']) if 'loss' in df.columns else None,
            'representative_lat': float(lats[0]),
            'representative_lon': float(lons[0])
        }]
    
    # Step 1: Geographic DBSCAN
    coords = np.column_stack([lats, lons])
    db = DBSCAN(eps=geo_eps_deg, min_samples=5).fit(coords)
    geo_labels = db.labels_
    
    n_geo_clusters = len(set(geo_labels)) - (1 if -1 in geo_labels else 0)
    
    # If DBSCAN finds only 1 cluster (all points in one region), fall back to
    # embedding-space clustering
    if n_geo_clusters <= 1:
        dispersion = compute_geographic_dispersion(lats, lons)
        adapted_max_k = adaptive_max_k(dispersion, n, max_k)
        weights = fast_grid_density(lats, lons)
        optimal_k = find_optimal_k(embeddings, weights, min_k, adapted_max_k)
        _, labels = weighted_kmeans(embeddings, weights, optimal_k)
        
        clusters = []
        for k in range(optimal_k):
            mask = labels == k
            if mask.sum() == 0:
                continue
            cluster_weights = weights[mask]
            best_idx = np.argmax(cluster_weights)
            cluster_elev = df.loc[mask, 'elevation'].dropna() if 'elevation' in df.columns else pd.Series()
            clusters.append({
                'cluster_id': k,
                'centroid': np.average(embeddings[mask], axis=0, weights=cluster_weights).tolist(),
                'occurrence_count': int(mask.sum()),
                'is_single_cluster': False,
                'mean_elevation': safe_mean(cluster_elev),
                'elevation_std': safe_std(cluster_elev),
                'mean_treecover2000': safe_mean(df.loc[mask, 'treecover2000']) if 'treecover2000' in df.columns else None,
                'forest_loss_fraction': safe_mean(df.loc[mask, 'loss']) if 'loss' in df.columns else None,
                'representative_lat': float(lats[mask][best_idx]),
                'representative_lon': float(lons[mask][best_idx]),
            })
        return clusters
    
    # Step 2: Assign noise points to nearest geographic cluster
    if -1 in geo_labels:
        noise_mask = geo_labels == -1
        cluster_centers = {}
        for label in set(geo_labels):
            if label >= 0:
                mask = geo_labels == label
                cluster_centers[label] = (lats[mask].mean(), lons[mask].mean())
        
        for i in np.where(noise_mask)[0]:
            min_dist = float('inf')
            best_label = 0
            for label, (clat, clon) in cluster_centers.items():
                d = haversine_km(lats[i], lons[i], clat, clon)
                if d < min_dist:
                    min_dist = d
                    best_label = label
            geo_labels[i] = best_label
    
    # Step 3: One embedding centroid per geographic region
    weights = fast_grid_density(lats, lons)
    clusters = []
    cluster_id = 0
    
    for label in sorted(set(geo_labels)):
        mask = geo_labels == label
        if mask.sum() == 0:
            continue
        
        cluster_weights = weights[mask]
        cluster_emb = embeddings[mask]
        best_idx = np.argmax(cluster_weights)
        cluster_elev = df.loc[mask, 'elevation'].dropna() if 'elevation' in df.columns else pd.Series()
        
        clusters.append({
            'cluster_id': cluster_id,
            'centroid': np.average(cluster_emb, axis=0, weights=cluster_weights).tolist(),
            'occurrence_count': int(mask.sum()),
            'is_single_cluster': False,
            'mean_elevation': safe_mean(cluster_elev),
            'elevation_std': safe_std(cluster_elev),
            'mean_treecover2000': safe_mean(df.loc[mask, 'treecover2000']) if 'treecover2000' in df.columns else None,
            'forest_loss_fraction': safe_mean(df.loc[mask, 'loss']) if 'loss' in df.columns else None,
            'representative_lat': float(lats[mask][best_idx]),
            'representative_lon': float(lons[mask][best_idx]),
        })
        cluster_id += 1
    
    return clusters


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Phase B: Re-cluster with adaptive K')
    parser.add_argument('--dry-run', action='store_true', help='Show which species need re-clustering')
    parser.add_argument('--species', type=str, help='Re-cluster a specific species')
    parser.add_argument('--min-dispersion', type=float, default=DEFAULT_MIN_DISPERSION_KM,
                        help=f'Min geographic dispersion to trigger re-clustering (km, default {DEFAULT_MIN_DISPERSION_KM})')
    parser.add_argument('--min-occurrences', type=int, default=10,
                        help='Minimum occurrences to consider for re-clustering (default 10)')
    parser.add_argument('--batch-size', type=int, default=100, help='DB commit batch size')
    args = parser.parse_args()
    
    print("=" * 70)
    print("PHASE B: RE-CLUSTER WITH ADAPTIVE K")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Min dispersion threshold: {args.min_dispersion:.0f} km")
    print()
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 1: Load all embedding data (v4 + Phase A)
    # ─────────────────────────────────────────────────────────────────────
    print("STEP 1: Loading embedding data...")
    
    v4 = pq.read_table(V4_PARQUET).to_pandas()
    print(f"  V4: {len(v4):,} rows, {v4['taxon_id'].nunique():,} species")
    
    # Also load Phase A rejoined data
    phase_a_files = list(PHASE_A_DIR.glob("rejoined_gap_species_*.parquet")) if PHASE_A_DIR.exists() else []
    if phase_a_files:
        phase_a = pd.concat([pd.read_parquet(f) for f in phase_a_files])
        print(f"  Phase A: {len(phase_a):,} rows, {phase_a['taxon_id'].nunique():,} species")
        all_data = pd.concat([v4, phase_a], ignore_index=True)
    else:
        print("  Phase A: No data found")
        all_data = v4
    
    # Deduplicate by species + location
    all_data = all_data.drop_duplicates(subset=['taxon_id', 'latitude', 'longitude'])
    print(f"  Combined (deduped): {len(all_data):,} rows, {all_data['taxon_id'].nunique():,} species")
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 2: Identify species needing re-clustering
    # ─────────────────────────────────────────────────────────────────────
    print("\nSTEP 2: Computing geographic dispersion...")
    
    species_counts = all_data.groupby('taxon_id').size()
    eligible_species = species_counts[species_counts >= args.min_occurrences].index
    
    if args.species:
        eligible_species = [args.species] if args.species in eligible_species else []
        if not eligible_species:
            print(f"  Species {args.species} not found or has < {args.min_occurrences} occurrences")
            return
    
    print(f"  Eligible species (>= {args.min_occurrences} occurrences): {len(eligible_species):,}")
    
    # Compute dispersion for each
    needs_recluster = []
    for i, taxon_id in enumerate(eligible_species):
        sp_df = all_data[all_data['taxon_id'] == taxon_id]
        dispersion = compute_geographic_dispersion(
            sp_df['latitude'].values, sp_df['longitude'].values
        )
        n_points = len(sp_df)
        new_max_k = adaptive_max_k(dispersion, n_points)
        
        if dispersion >= args.min_dispersion:
            needs_recluster.append({
                'taxon_id': taxon_id,
                'n_points': n_points,
                'dispersion_km': dispersion,
                'new_max_k': new_max_k,
            })
        
        if (i + 1) % 1000 == 0:
            print(f"    Scanned {i+1:,}/{len(eligible_species):,} species, {len(needs_recluster):,} need re-clustering")
    
    print(f"\n  Species needing re-clustering: {len(needs_recluster):,}")
    
    if not needs_recluster:
        print("  No species need re-clustering.")
        return
    
    # Sort by dispersion (most dispersed first)
    needs_recluster.sort(key=lambda x: -x['dispersion_km'])
    
    # Show top candidates
    print(f"\n  Top 20 most dispersed species:")
    for info in needs_recluster[:20]:
        print(f"    {info['taxon_id']}: {info['dispersion_km']:.0f}km, {info['n_points']} pts, max_k={info['new_max_k']}")
    
    if args.dry_run:
        print(f"\n[DRY RUN — no changes made]")
        print(f"  Would re-cluster {len(needs_recluster):,} species")
        return
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 3: Re-cluster and update database
    # ─────────────────────────────────────────────────────────────────────
    print(f"\nSTEP 3: Re-clustering {len(needs_recluster):,} species...")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = psycopg2.connect(dbname=DB_NAME)
    cur = conn.cursor()
    
    processed = 0
    total_new_centroids = 0
    total_old_centroids = 0
    batch_data = []
    
    for info in needs_recluster:
        taxon_id = info['taxon_id']
        
        # Get current centroid count
        cur.execute("SELECT COUNT(*) FROM species_habitat_centroids WHERE taxon_id = %s", (taxon_id,))
        old_count = cur.fetchone()[0]
        total_old_centroids += old_count
        
        # Get species data
        sp_df = all_data[all_data['taxon_id'] == taxon_id].copy()
        sp_df = sp_df.drop_duplicates(subset=['latitude', 'longitude'])
        
        # Re-cluster with adaptive max_k
        clusters = cluster_species_adaptive(sp_df, min_k=3, max_k=info['new_max_k'])
        
        # Delete old centroids
        cur.execute("DELETE FROM species_habitat_centroids WHERE taxon_id = %s", (taxon_id,))
        
        # Prepare new centroids
        for c in clusters:
            batch_data.append((
                taxon_id,
                c['cluster_id'],
                c['centroid'],
                c['occurrence_count'],
                c.get('is_single_cluster', False),
                c.get('mean_elevation'),
                c.get('elevation_std'),
                c.get('mean_treecover2000'),
                c.get('forest_loss_fraction'),
                c['representative_lat'],
                c['representative_lon']
            ))
        
        total_new_centroids += len(clusters)
        processed += 1
        
        if processed % args.batch_size == 0:
            # Bulk insert batch
            if batch_data:
                execute_values(cur, """
                    INSERT INTO species_habitat_centroids
                    (taxon_id, cluster_id, centroid_vector, occurrence_count, is_single_cluster,
                     mean_elevation, elevation_std, mean_treecover2000,
                     forest_loss_fraction, representative_lat, representative_lon)
                    VALUES %s
                """, batch_data, template="(%s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s)")
                batch_data = []
            conn.commit()
            print(f"    Processed {processed:,}/{len(needs_recluster):,}: "
                  f"{total_old_centroids} old → {total_new_centroids} new centroids")
    
    # Final batch
    if batch_data:
        execute_values(cur, """
            INSERT INTO species_habitat_centroids
            (taxon_id, cluster_id, centroid_vector, occurrence_count, is_single_cluster,
             mean_elevation, elevation_std, mean_treecover2000,
             forest_loss_fraction, representative_lat, representative_lon)
            VALUES %s
        """, batch_data, template="(%s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s)")
    conn.commit()
    
    cur.close()
    conn.close()
    
    # ─────────────────────────────────────────────────────────────────────
    # Step 4: Summary
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("PHASE B COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Species re-clustered: {processed:,}")
    print(f"  Old centroids removed: {total_old_centroids:,}")
    print(f"  New centroids created: {total_new_centroids:,}")
    print(f"  Net change: {total_new_centroids - total_old_centroids:+,} centroids")
    
    # Save metadata
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metadata = {
        'timestamp': timestamp,
        'phase': 'B',
        'description': 'Re-clustered species with adaptive max_k based on geographic dispersion',
        'min_dispersion_km': args.min_dispersion,
        'min_occurrences': args.min_occurrences,
        'species_reclustered': processed,
        'old_centroids': total_old_centroids,
        'new_centroids': total_new_centroids,
        'species_details': needs_recluster[:50],  # Top 50 for reference
    }
    
    metadata_path = OUTPUT_DIR / f"recluster_metadata_{timestamp}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  Metadata: {metadata_path}")
    
    print(f"\n  Next: Rebuild IVFFlat index, then run Phase C (Regime 2 GEE sampling)")


if __name__ == '__main__':
    main()
