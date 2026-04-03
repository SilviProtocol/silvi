#!/usr/bin/env python3
"""
Habitat Centroid Clustering with Proximity-Based Weighting
===========================================================
Clusters AlphaEarth 64-D embeddings using proximity-based density weighting
to correct for sampling bias (research stations, cities, roads).

Key Features:
1. Multi-scale geohash density: Captures bias at 1km, 5km, and 40km scales
2. Log-inverse weighting: Points in dense areas get lower influence
3. Weighted K-means: Centroids represent true habitat diversity, not sampling intensity
4. Local Parquet input: Reads from exported BigQuery data (free compute)

Usage:
    python cluster_habitat_centroids_weighted.py [--input-dir PATH] [--min-clusters 3] [--max-clusters 10]

Prerequisites:
    - Exported embeddings in orchestrator/bigquery_exports/alphaearth_embeddings_v4/
    - PostgreSQL with pgvector extension
    - pip install pygeohash scikit-learn numpy pandas psycopg2-binary pgvector
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DEFAULT_INPUT_DIR = BASE_DIR / "orchestrator" / "bigquery_exports" / "alphaearth_embeddings_v4"

# PostgreSQL configuration
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DATABASE = os.environ.get("PG_DATABASE", "treekipedia")
PG_USER = os.environ.get("PG_USER", "")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")

# Embedding columns
EMBEDDING_COLS = [f"A{i:02d}" for i in range(64)]


# =============================================================================
# Proximity-Based Density Weighting
# =============================================================================

def compute_multiscale_density_weights(
    lats: np.ndarray,
    lons: np.ndarray,
    local_precision: int = 6,    # ~1.2km × 0.6km
    regional_precision: int = 5,  # ~5km × 5km
    broad_precision: int = 4      # ~40km × 20km
) -> Tuple[np.ndarray, Dict]:
    """
    Compute proximity-based density weights using multi-scale geohash.

    Points in densely sampled areas (research stations, cities) get lower weights.
    Isolated points get higher weights.

    Returns:
        weights: np.ndarray of shape (n,) with values in [0, 1]
        density_info: Dict with density at each scale
    """
    try:
        import pygeohash as pgh
    except ImportError:
        logger.warning("pygeohash not installed, falling back to grid-based density")
        return compute_grid_density_weights(lats, lons)

    n = len(lats)

    # Encode geohashes at each precision level
    gh_local = [pgh.encode(lat, lon, local_precision) for lat, lon in zip(lats, lons)]
    gh_regional = [pgh.encode(lat, lon, regional_precision) for lat, lon in zip(lats, lons)]
    gh_broad = [pgh.encode(lat, lon, broad_precision) for lat, lon in zip(lats, lons)]

    # Count points per cell at each scale
    counts_local = Counter(gh_local)
    counts_regional = Counter(gh_regional)
    counts_broad = Counter(gh_broad)

    # Map counts back to each point
    density_local = np.array([counts_local[gh] for gh in gh_local], dtype=float)
    density_regional = np.array([counts_regional[gh] for gh in gh_regional], dtype=float)
    density_broad = np.array([counts_broad[gh] for gh in gh_broad], dtype=float)

    # Combine scales with different weights
    # Local bias matters most for clustering (research stations, botanical gardens)
    combined_density = (
        0.5 * density_local +
        0.3 * density_regional +
        0.2 * density_broad
    )

    # Log-inverse weighting: high density = low weight
    # Adding 1 to avoid log(0), then inverting
    weights = 1.0 / np.log1p(combined_density)

    # Normalize to [0, 1]
    weights = weights / weights.max()

    return weights, {
        'local': density_local,
        'regional': density_regional,
        'broad': density_broad,
        'combined': combined_density
    }


def compute_grid_density_weights(
    lats: np.ndarray,
    lons: np.ndarray,
    cell_size_km: float = 5.0
) -> Tuple[np.ndarray, Dict]:
    """
    Fallback: Grid-based density estimation.
    """
    # Approximate: 1 degree ≈ 111 km
    cell_size_deg = cell_size_km / 111.0

    # Assign to grid cells
    cell_x = (lons / cell_size_deg).astype(int)
    cell_y = (lats / cell_size_deg).astype(int)

    # Count per cell
    cell_counts = Counter(zip(cell_x, cell_y))

    # Density includes 3x3 neighborhood
    densities = np.zeros(len(lats))
    for i, (x, y) in enumerate(zip(cell_x, cell_y)):
        density = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                density += cell_counts.get((x + dx, y + dy), 0)
        densities[i] = density

    # Log-inverse weight
    weights = 1.0 / np.log1p(densities)
    weights = weights / weights.max()

    return weights, {'combined': densities}


# =============================================================================
# Weighted K-Means Clustering
# =============================================================================

def weighted_kmeans(
    embeddings: np.ndarray,
    weights: np.ndarray,
    n_clusters: int,
    max_iter: int = 100,
    tol: float = 1e-4,
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    K-means clustering with sample weights.

    Standard K-means minimizes: sum_i ||x_i - c_k||^2
    Weighted K-means minimizes: sum_i w_i * ||x_i - c_k||^2

    Args:
        embeddings: (n, d) array of feature vectors
        weights: (n,) array of sample weights
        n_clusters: Number of clusters
        max_iter: Maximum iterations
        tol: Convergence tolerance
        random_state: Random seed

    Returns:
        centroids: (k, d) array of cluster centers
        labels: (n,) array of cluster assignments
    """
    from sklearn.cluster import KMeans

    n_samples, n_features = embeddings.shape
    rng = np.random.RandomState(random_state)

    # Initialize with K-means++ (unweighted)
    kmeans_init = KMeans(n_clusters=n_clusters, n_init=1, max_iter=1, random_state=random_state)
    kmeans_init.fit(embeddings)
    centroids = kmeans_init.cluster_centers_.copy()

    for iteration in range(max_iter):
        # E-step: Assign to nearest centroid
        distances = np.linalg.norm(
            embeddings[:, None, :] - centroids[None, :, :], axis=2
        )
        labels = distances.argmin(axis=1)

        # M-step: Update centroids with weighted mean
        new_centroids = np.zeros_like(centroids)
        for k in range(n_clusters):
            mask = labels == k
            if mask.sum() > 0:
                cluster_embeddings = embeddings[mask]
                cluster_weights = weights[mask]
                # Weighted average
                new_centroids[k] = np.average(
                    cluster_embeddings, axis=0, weights=cluster_weights
                )
            else:
                # Empty cluster: reinitialize randomly
                new_centroids[k] = embeddings[rng.randint(n_samples)]

        # Check convergence
        centroid_shift = np.linalg.norm(new_centroids - centroids)
        if centroid_shift < tol:
            logger.debug(f"Converged at iteration {iteration}")
            break

        centroids = new_centroids

    return centroids, labels


def find_optimal_k_weighted(
    embeddings: np.ndarray,
    weights: np.ndarray,
    min_k: int = 3,
    max_k: int = 10
) -> int:
    """
    Find optimal number of clusters using weighted silhouette score.
    """
    from sklearn.metrics import silhouette_score

    n_samples = len(embeddings)
    if n_samples < min_k:
        return n_samples

    max_k = min(max_k, n_samples - 1)

    best_k = min_k
    best_score = -1

    for k in range(min_k, max_k + 1):
        try:
            centroids, labels = weighted_kmeans(embeddings, weights, k)

            # Check we have enough unique labels
            n_unique = len(set(labels))
            if n_unique < 2:
                continue

            # Silhouette score (unweighted, but on weighted clustering)
            score = silhouette_score(embeddings, labels)

            if score > best_score:
                best_k = k
                best_score = score

        except Exception as e:
            logger.debug(f"k={k} failed: {e}")
            continue

    return best_k


# =============================================================================
# Species Processing
# =============================================================================

def load_species_data(input_dir: Path, taxon_id: str) -> Optional[pd.DataFrame]:
    """
    Load all data for a species from Parquet batches.
    """
    dfs = []

    for batch_file in sorted(input_dir.glob("batch_*.parquet")):
        df = pd.read_parquet(batch_file)
        species_df = df[df['taxon_id'] == taxon_id]
        if len(species_df) > 0:
            dfs.append(species_df)

    if not dfs:
        return None

    return pd.concat(dfs, ignore_index=True)


def cluster_species(
    df: pd.DataFrame,
    min_k: int = 3,
    max_k: int = 10
) -> List[Dict]:
    """
    Cluster a species' embeddings with proximity-based weighting.

    Args:
        df: DataFrame with embedding columns and lat/lon
        min_k: Minimum clusters
        max_k: Maximum clusters

    Returns:
        List of cluster dicts with centroids and metadata
    """
    # Extract embeddings
    embeddings = df[EMBEDDING_COLS].values
    lats = df['latitude'].values
    lons = df['longitude'].values

    n_samples = len(embeddings)

    # Handle small sample sizes
    if n_samples < 3:
        return [{
            'cluster_id': 0,
            'centroid': embeddings.mean(axis=0).tolist(),
            'n_pixels': n_samples,
            'effective_sample_size': float(n_samples),
            'mean_weight': 1.0,
            'mean_density': 1.0,
            'mean_elevation': float(df['elevation'].mean()) if 'elevation' in df else None,
            'elevation_std': float(df['elevation'].std()) if 'elevation' in df else None,
            'mean_treecover': float(df['treecover2000'].mean()) if 'treecover2000' in df else None,
            'representative_lat': float(lats[0]),
            'representative_lon': float(lons[0])
        }]

    # Compute proximity-based weights
    weights, density_info = compute_multiscale_density_weights(lats, lons)

    # Find optimal number of clusters
    optimal_k = find_optimal_k_weighted(embeddings, weights, min_k, min(max_k, n_samples - 1))

    # Run weighted K-means
    centroids, labels = weighted_kmeans(embeddings, weights, optimal_k)

    # Compute cluster statistics
    clusters = []
    for k in range(optimal_k):
        mask = labels == k
        if mask.sum() == 0:
            continue

        cluster_embeddings = embeddings[mask]
        cluster_weights = weights[mask]
        cluster_lats = lats[mask]
        cluster_lons = lons[mask]
        cluster_density = density_info['combined'][mask]

        # Weighted centroid (already computed by K-means, but recalculate for precision)
        weighted_centroid = np.average(cluster_embeddings, axis=0, weights=cluster_weights)

        # Effective sample size (Kish's formula)
        ess = (cluster_weights.sum() ** 2) / (cluster_weights ** 2).sum()

        # Find representative point (highest weight in cluster)
        best_idx = np.argmax(cluster_weights)

        # Elevation stats
        if 'elevation' in df.columns:
            cluster_elev = df.loc[mask, 'elevation'].dropna()
            mean_elev = float(cluster_elev.mean()) if len(cluster_elev) > 0 else None
            std_elev = float(cluster_elev.std()) if len(cluster_elev) > 1 else None
        else:
            mean_elev, std_elev = None, None

        # Treecover stats
        if 'treecover2000' in df.columns:
            mean_treecover = float(df.loc[mask, 'treecover2000'].mean())
        else:
            mean_treecover = None

        # Forest loss fraction
        if 'loss' in df.columns:
            forest_loss_frac = float(df.loc[mask, 'loss'].mean())
        else:
            forest_loss_frac = None

        clusters.append({
            'cluster_id': k,
            'centroid': weighted_centroid.tolist(),
            'n_pixels': int(mask.sum()),
            'effective_sample_size': float(ess),
            'mean_weight': float(cluster_weights.mean()),
            'mean_density': float(cluster_density.mean()),
            'mean_elevation': mean_elev,
            'elevation_std': std_elev,
            'mean_treecover': mean_treecover,
            'forest_loss_fraction': forest_loss_frac,
            'representative_lat': float(cluster_lats[best_idx]),
            'representative_lon': float(cluster_lons[best_idx])
        })

    return clusters


# =============================================================================
# Database Operations
# =============================================================================

def get_postgres_connection():
    """Initialize PostgreSQL connection with pgvector."""
    import psycopg2
    from pgvector.psycopg2 import register_vector

    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
        user=PG_USER or None,
        password=PG_PASSWORD or None
    )
    register_vector(conn)
    return conn


def save_clusters_to_db(conn, taxon_id: str, clusters: List[Dict]):
    """Save cluster centroids to PostgreSQL."""
    with conn.cursor() as cur:
        # Delete existing
        cur.execute("DELETE FROM species_habitat_centroids WHERE taxon_id = %s", (taxon_id,))

        # Insert new
        for cluster in clusters:
            cur.execute("""
                INSERT INTO species_habitat_centroids
                (taxon_id, cluster_id, centroid_vector, occurrence_count,
                 mean_elevation, elevation_std, mean_treecover2000,
                 forest_loss_fraction, representative_lat, representative_lon)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                taxon_id,
                cluster['cluster_id'],
                cluster['centroid'],
                cluster['n_pixels'],  # Using n_pixels as occurrence_count
                cluster['mean_elevation'],
                cluster['elevation_std'],
                cluster['mean_treecover'],
                cluster['forest_loss_fraction'],
                cluster['representative_lat'],
                cluster['representative_lon']
            ))

        conn.commit()


# =============================================================================
# Main Pipeline
# =============================================================================

def get_species_list_from_parquet(input_dir: Path, min_occurrences: int = 10) -> List[Tuple[str, int]]:
    """
    Get list of species with occurrence counts from Parquet files.
    """
    logger.info("Scanning Parquet files for species list...")

    species_counts = Counter()

    for batch_file in sorted(input_dir.glob("batch_*.parquet")):
        df = pd.read_parquet(batch_file, columns=['taxon_id'])
        species_counts.update(df['taxon_id'].value_counts().to_dict())

    # Filter by minimum occurrences
    species_list = [
        (taxon_id, count)
        for taxon_id, count in species_counts.items()
        if count >= min_occurrences and taxon_id is not None
    ]

    # Sort by count descending
    species_list.sort(key=lambda x: -x[1])

    logger.info(f"Found {len(species_list)} species with >= {min_occurrences} occurrences")

    return species_list


def main():
    parser = argparse.ArgumentParser(description="Cluster species habitats with proximity weighting")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR),
                        help="Directory with embedding Parquet files")
    parser.add_argument("--min-clusters", type=int, default=3)
    parser.add_argument("--max-clusters", type=int, default=10)
    parser.add_argument("--min-occurrences", type=int, default=10)
    parser.add_argument("--start-from", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of species to process")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    logger.info("=" * 60)
    logger.info("Habitat Clustering with Proximity-Based Weighting")
    logger.info("=" * 60)
    logger.info(f"Input: {input_dir}")
    logger.info(f"Clusters: {args.min_clusters}-{args.max_clusters}")
    logger.info(f"Min occurrences: {args.min_occurrences}")

    # Check input exists
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    batch_files = list(input_dir.glob("batch_*.parquet"))
    if not batch_files:
        logger.error("No batch files found!")
        sys.exit(1)

    logger.info(f"Found {len(batch_files)} batch files")

    # Get species list
    species_list = get_species_list_from_parquet(input_dir, args.min_occurrences)

    if args.start_from:
        try:
            start_idx = next(i for i, (tid, _) in enumerate(species_list) if tid == args.start_from)
            species_list = species_list[start_idx:]
            logger.info(f"Starting from {args.start_from}")
        except StopIteration:
            logger.warning(f"Species {args.start_from} not found")

    if args.limit:
        species_list = species_list[:args.limit]
        logger.info(f"Limited to {args.limit} species")

    # Initialize database
    if not args.dry_run:
        conn = get_postgres_connection()
    else:
        conn = None

    # Process species
    processed = 0
    failed = 0
    start_time = datetime.now()

    for i, (taxon_id, occ_count) in enumerate(species_list):
        try:
            # Load species data
            df = load_species_data(input_dir, taxon_id)
            if df is None or len(df) < 3:
                logger.warning(f"Skipping {taxon_id}: insufficient data")
                continue

            # Cluster
            clusters = cluster_species(df, args.min_clusters, args.max_clusters)

            # Save
            if not args.dry_run:
                save_clusters_to_db(conn, taxon_id, clusters)

            processed += 1

            # Log progress
            if (i + 1) % 100 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (i + 1) / elapsed * 3600
                logger.info(f"Progress: {i + 1}/{len(species_list)} ({rate:.0f}/hour)")
                logger.info(f"  Last: {taxon_id} -> {len(clusters)} clusters from {len(df)} pixels")

        except Exception as e:
            logger.error(f"Error processing {taxon_id}: {e}")
            failed += 1
            continue

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE: {processed} species, {failed} failed")
    logger.info(f"Time: {elapsed/60:.1f} minutes")
    logger.info("=" * 60)

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
