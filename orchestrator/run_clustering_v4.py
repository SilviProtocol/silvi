#!/usr/bin/env python3
"""
Run Weighted Clustering on v4 AlphaEarth Data

Processes the complete v4 parquet file with:
1. Deduplication by unique locations (not pixel-years)
2. Fast grid-based density weighting
3. Weighted K-means clustering
4. Save to species_habitat_centroids table

Usage:
    python3 -u run_clustering_v4.py [--limit N] [--min-occurrences 10]
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
from collections import Counter
import argparse

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# Constants
PARQUET_PATH = Path(__file__).parent / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]
DB_NAME = "treekipedia"


def safe_float(val):
    """Safely convert a value to float, handling pandas NA/NaN."""
    if val is None or pd.isna(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def safe_mean(series):
    """Get mean of a series, returning None if empty or all NA."""
    valid = series.dropna()
    if len(valid) == 0:
        return None
    return safe_float(valid.mean())


def safe_std(series):
    """Get std of a series, returning None if < 2 values."""
    valid = series.dropna()
    if len(valid) < 2:
        return None
    return safe_float(valid.std())


def fast_grid_density(lats: np.ndarray, lons: np.ndarray, cell_size_deg: float = 0.01) -> np.ndarray:
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


def weighted_kmeans(embeddings: np.ndarray, weights: np.ndarray, n_clusters: int,
                    max_iter: int = 50, random_state: int = 42):
    """Weighted K-means clustering."""
    n_samples, n_features = embeddings.shape
    rng = np.random.RandomState(random_state)

    # Initialize with K-means++
    kmeans_init = KMeans(n_clusters=n_clusters, n_init=1, max_iter=1, random_state=random_state)
    kmeans_init.fit(embeddings)
    centroids = kmeans_init.cluster_centers_.copy()

    for iteration in range(max_iter):
        # Assign to nearest centroid
        distances = np.linalg.norm(embeddings[:, None, :] - centroids[None, :, :], axis=2)
        labels = distances.argmin(axis=1)

        # Update centroids with weighted mean
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


def find_optimal_k(embeddings: np.ndarray, weights: np.ndarray, min_k: int = 3, max_k: int = 10) -> int:
    """Find optimal number of clusters using silhouette score (with subsampling for large N)."""
    n = len(embeddings)
    if n < min_k:
        return n

    max_k = min(max_k, n - 1)

    # Subsample for large datasets to speed up silhouette calculation
    MAX_SAMPLE = 5000
    if n > MAX_SAMPLE:
        # Sample with weights as probability
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


def cluster_species(df: pd.DataFrame, min_k: int = 3, max_k: int = 10, max_points: int = 20000) -> list:
    """Cluster a species' embeddings with proximity-based weighting.

    For species with >max_points occurrences, subsample for clustering
    but report actual occurrence counts.
    """
    n_original = len(df)

    # Subsample very large species for clustering (keeps weighting)
    if n_original > max_points:
        weights_full = fast_grid_density(df['latitude'].values, df['longitude'].values)
        probs = weights_full / weights_full.sum()
        sample_idx = np.random.choice(n_original, size=max_points, replace=False, p=probs)
        df = df.iloc[sample_idx].reset_index(drop=True)

    embeddings = df[EMBEDDING_COLS].values
    lats = df['latitude'].values
    lons = df['longitude'].values
    n = len(embeddings)

    # For species with few occurrences, store single centroid (no clustering possible)
    # This still allows prediction via embedding similarity
    if n < 3:
        return [{
            'cluster_id': 0,
            'centroid': embeddings.mean(axis=0).tolist(),
            'occurrence_count': n,
            'is_single_cluster': True,  # Flag that clustering wasn't possible
            'mean_elevation': safe_mean(df['elevation']) if 'elevation' in df.columns else None,
            'elevation_std': safe_std(df['elevation']) if 'elevation' in df.columns else None,
            'mean_treecover2000': safe_mean(df['treecover2000']) if 'treecover2000' in df.columns else None,
            'forest_loss_fraction': safe_mean(df['loss']) if 'loss' in df.columns else None,
            'representative_lat': float(lats[0]),
            'representative_lon': float(lons[0])
        }]

    weights = fast_grid_density(lats, lons)
    optimal_k = find_optimal_k(embeddings, weights, min_k, min(max_k, n - 1))
    centroids, labels = weighted_kmeans(embeddings, weights, optimal_k)

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
            'is_single_cluster': False,  # Proper clustering was performed
            'mean_elevation': safe_mean(cluster_elev),
            'elevation_std': safe_std(cluster_elev),
            'mean_treecover2000': safe_mean(df.loc[mask, 'treecover2000']) if 'treecover2000' in df.columns else None,
            'forest_loss_fraction': safe_mean(df.loc[mask, 'loss']) if 'loss' in df.columns else None,
            'representative_lat': float(lats[mask][best_idx]),
            'representative_lon': float(lons[mask][best_idx])
        })

    return clusters


def save_clusters_batch(conn, batch_data: list):
    """Bulk insert clusters to database."""
    cur = conn.cursor()

    # Prepare data for bulk insert
    values = []
    for taxon_id, clusters in batch_data:
        for c in clusters:
            values.append((
                taxon_id,
                c['cluster_id'],
                c['centroid'],
                c['occurrence_count'],
                c.get('is_single_cluster', False),
                c['mean_elevation'],
                c['elevation_std'],
                c['mean_treecover2000'],
                c['forest_loss_fraction'],
                c['representative_lat'],
                c['representative_lon']
            ))

    if values:
        execute_values(cur, """
            INSERT INTO species_habitat_centroids
            (taxon_id, cluster_id, centroid_vector, occurrence_count, is_single_cluster,
             mean_elevation, elevation_std, mean_treecover2000,
             forest_loss_fraction, representative_lat, representative_lon)
            VALUES %s
        """, values, template="(%s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s)")

    conn.commit()
    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Run weighted clustering on v4 data")
    parser.add_argument('--limit', type=int, default=None, help='Limit species to process')
    parser.add_argument('--min-occurrences', type=int, default=1, help='Minimum occurrences per species (default: 1 = ALL species)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for DB commits')
    args = parser.parse_args()

    print("=" * 60)
    print("Weighted Clustering on v4 AlphaEarth Data")
    print("=" * 60)

    # Load data
    print(f"\nLoading {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()
    print(f"  Loaded {len(df):,} rows")

    # Deduplicate by unique locations
    print("\nDeduplicating by unique locations...")
    df = df.drop_duplicates(subset=['taxon_id', 'latitude', 'longitude'])
    print(f"  {len(df):,} unique locations")

    # Get species list
    species_counts = df.groupby('taxon_id').size()
    species_list = species_counts[species_counts >= args.min_occurrences].sort_values(ascending=False)
    print(f"  {len(species_list):,} species with >= {args.min_occurrences} occurrences")

    if args.limit:
        species_list = species_list.head(args.limit)
        print(f"  Limited to {len(species_list)} species")

    # Connect to database
    print("\nConnecting to PostgreSQL...")
    conn = psycopg2.connect(dbname=DB_NAME)
    cur = conn.cursor()

    # Ensure table exists (create if not exists, don't drop to preserve progress)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS species_habitat_centroids (
            taxon_id VARCHAR(50),
            cluster_id INTEGER,
            centroid_vector vector(64),
            occurrence_count INTEGER,
            is_single_cluster BOOLEAN DEFAULT FALSE,
            mean_elevation FLOAT,
            elevation_std FLOAT,
            mean_treecover2000 FLOAT,
            forest_loss_fraction FLOAT,
            representative_lat FLOAT,
            representative_lon FLOAT,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (taxon_id, cluster_id)
        );
    """)
    conn.commit()

    # Get already processed species to skip them
    cur.execute("SELECT DISTINCT taxon_id FROM species_habitat_centroids")
    already_processed = set(row[0] for row in cur.fetchall())
    print(f"  {len(already_processed):,} species already processed, will be skipped")

    # Filter out already processed species
    species_list = species_list[~species_list.index.isin(already_processed)]
    print(f"  {len(species_list):,} species remaining to process")
    cur.close()

    # Process species
    print(f"\nProcessing {len(species_list):,} species...")
    start_time = datetime.now()
    processed = 0
    total_clusters = 0
    batch_data = []

    for i, taxon_id in enumerate(species_list.index):
        try:
            species_df = df[df['taxon_id'] == taxon_id].reset_index(drop=True)
            clusters = cluster_species(species_df)
            batch_data.append((taxon_id, clusters))
            total_clusters += len(clusters)
            processed += 1

            # Commit batch
            if len(batch_data) >= args.batch_size:
                save_clusters_batch(conn, batch_data)
                batch_data = []

            # Progress
            if (i + 1) % 500 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (i + 1) / elapsed * 3600
                print(f"  Progress: {i+1:,}/{len(species_list):,} ({100*(i+1)/len(species_list):.1f}%) - {rate:.0f}/hour")

        except Exception as e:
            print(f"  Error processing {taxon_id}: {e}")
            continue

    # Save remaining batch
    if batch_data:
        save_clusters_batch(conn, batch_data)

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n" + "=" * 60)
    print(f"COMPLETE: {processed:,} species, {total_clusters:,} clusters")
    print(f"Time: {elapsed/60:.1f} minutes ({processed/elapsed*60:.1f} species/min)")
    print("=" * 60)

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT taxon_id), COUNT(*) FROM species_habitat_centroids")
    n_species, n_clusters = cur.fetchone()
    print(f"\nDatabase: {n_species:,} species, {n_clusters:,} clusters")
    cur.close()

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
