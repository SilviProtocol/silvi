#!/usr/bin/env python3
"""
Habitat Centroid Clustering Pipeline
=====================================
Clusters AlphaEarth 64-D embeddings to find 3-10 habitat centroids per species.
These centroids are used for cosine similarity-based habitat prediction.

Usage:
    python cluster_habitat_centroids.py [--batch-size 1000] [--min-clusters 3] [--max-clusters 10]

Prerequisites:
    - BigQuery table: treekipedia-479918.species_data.alphaearth_embeddings_v4
    - PostgreSQL with pgvector extension
    - Google Cloud credentials configured
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import List, Tuple, Optional
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# BigQuery configuration
PROJECT_ID = "treekipedia-479918"
DATASET_ID = "species_data"
TABLE_ID = "alphaearth_embeddings_v4"
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# PostgreSQL configuration (from environment or defaults)
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DATABASE = os.environ.get("PG_DATABASE", "treekipedia")
PG_USER = os.environ.get("PG_USER", "")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")


def get_bigquery_client():
    """Initialize BigQuery client."""
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=PROJECT_ID)
    except ImportError:
        logger.error("google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
        sys.exit(1)


def get_postgres_connection():
    """Initialize PostgreSQL connection with pgvector."""
    try:
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
    except ImportError:
        logger.error("psycopg2 or pgvector not installed. Run: pip install psycopg2-binary pgvector")
        sys.exit(1)


def ensure_postgres_schema(conn):
    """Create the centroid table if it doesn't exist."""
    with conn.cursor() as cur:
        # Ensure pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Create centroids table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS species_habitat_centroids (
                id SERIAL PRIMARY KEY,
                taxon_id VARCHAR(50) NOT NULL,
                cluster_id INTEGER NOT NULL,
                centroid_vector vector(64) NOT NULL,
                occurrence_count INTEGER,
                mean_elevation FLOAT,
                elevation_std FLOAT,
                mean_treecover2000 FLOAT,
                forest_loss_fraction FLOAT,
                representative_lat FLOAT,
                representative_lon FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(taxon_id, cluster_id)
            );
        """)

        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_centroid_vector
            ON species_habitat_centroids
            USING ivfflat (centroid_vector vector_cosine_ops) WITH (lists = 100);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_centroid_taxon
            ON species_habitat_centroids(taxon_id);
        """)

        # Create elevation profiles table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS species_elevation_profiles (
                taxon_id VARCHAR(50) PRIMARY KEY,
                min_elevation FLOAT,
                max_elevation FLOAT,
                mean_elevation FLOAT,
                median_elevation FLOAT,
                p10_elevation FLOAT,
                p90_elevation FLOAT,
                elevation_std FLOAT,
                occurrence_count INTEGER,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        logger.info("PostgreSQL schema ensured")


def get_species_list(bq_client, min_occurrences: int = 10) -> List[str]:
    """Get list of species with enough occurrences for clustering."""
    query = f"""
        SELECT taxon_id, COUNT(*) as occ_count
        FROM `{FULL_TABLE_ID}`
        WHERE taxon_id IS NOT NULL
        GROUP BY taxon_id
        HAVING COUNT(*) >= {min_occurrences}
        ORDER BY occ_count DESC
    """
    result = bq_client.query(query).result()
    species_list = [(row.taxon_id, row.occ_count) for row in result]
    logger.info(f"Found {len(species_list)} species with >= {min_occurrences} occurrences")
    return species_list


def get_species_embeddings(bq_client, taxon_id: str) -> Tuple[np.ndarray, dict]:
    """Fetch all embeddings for a species from BigQuery."""
    # Build the embedding column list
    embedding_cols = ", ".join([f"alphaearth_dim_{i}" for i in range(64)])

    query = f"""
        SELECT
            {embedding_cols},
            elevation,
            treecover2000,
            lossyear,
            loss,
            latitude,
            longitude
        FROM `{FULL_TABLE_ID}`
        WHERE taxon_id = @taxon_id
          AND alphaearth_dim_0 IS NOT NULL
    """

    job_config = bq_client.QueryJobConfig(
        query_parameters=[
            bq_client.ScalarQueryParameter("taxon_id", "STRING", taxon_id)
        ]
    )

    # Need to import bigquery properly
    from google.cloud import bigquery
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("taxon_id", "STRING", taxon_id)
        ]
    )

    result = bq_client.query(query, job_config=job_config).result()

    embeddings = []
    metadata = {
        'elevations': [],
        'treecover': [],
        'lossyears': [],
        'losses': [],
        'lats': [],
        'lons': []
    }

    for row in result:
        # Extract 64-D embedding
        embedding = [getattr(row, f"alphaearth_dim_{i}") for i in range(64)]
        if all(v is not None for v in embedding):
            embeddings.append(embedding)
            metadata['elevations'].append(row.elevation)
            metadata['treecover'].append(row.treecover2000)
            metadata['lossyears'].append(row.lossyear)
            metadata['losses'].append(row.loss)
            metadata['lats'].append(row.latitude)
            metadata['lons'].append(row.longitude)

    return np.array(embeddings), metadata


def find_optimal_clusters(embeddings: np.ndarray, min_k: int = 3, max_k: int = 10) -> int:
    """Find optimal number of clusters using silhouette score."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n_samples = len(embeddings)
    if n_samples < min_k:
        return n_samples

    max_k = min(max_k, n_samples - 1)  # Can't have more clusters than samples

    best_k = min_k
    best_score = -1

    for k in range(min_k, max_k + 1):
        try:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            # Need at least 2 clusters with samples for silhouette
            unique_labels = len(set(labels))
            if unique_labels < 2:
                continue

            score = silhouette_score(embeddings, labels)
            if score > best_score:
                best_k = k
                best_score = score
        except Exception as e:
            logger.warning(f"Clustering with k={k} failed: {e}")
            continue

    return best_k


def cluster_species(
    embeddings: np.ndarray,
    metadata: dict,
    min_k: int = 3,
    max_k: int = 10
) -> List[dict]:
    """Cluster embeddings and compute centroid statistics."""
    from sklearn.cluster import KMeans

    n_samples = len(embeddings)
    if n_samples < min_k:
        # Not enough samples - use single centroid
        return [{
            'cluster_id': 0,
            'centroid': embeddings.mean(axis=0).tolist(),
            'occurrence_count': n_samples,
            'mean_elevation': np.nanmean(metadata['elevations']),
            'elevation_std': np.nanstd(metadata['elevations']),
            'mean_treecover': np.nanmean(metadata['treecover']),
            'forest_loss_fraction': np.nanmean([1 if l else 0 for l in metadata['losses']]),
            'representative_lat': metadata['lats'][0] if metadata['lats'] else None,
            'representative_lon': metadata['lons'][0] if metadata['lons'] else None,
        }]

    # Find optimal k
    optimal_k = find_optimal_clusters(embeddings, min_k, max_k)

    # Final clustering
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Compute statistics per cluster
    clusters = []
    for cluster_id in range(optimal_k):
        mask = labels == cluster_id
        cluster_embeddings = embeddings[mask]

        # Get metadata for this cluster
        cluster_elevations = [metadata['elevations'][i] for i, m in enumerate(mask) if m]
        cluster_treecover = [metadata['treecover'][i] for i, m in enumerate(mask) if m]
        cluster_losses = [metadata['losses'][i] for i, m in enumerate(mask) if m]
        cluster_lats = [metadata['lats'][i] for i, m in enumerate(mask) if m]
        cluster_lons = [metadata['lons'][i] for i, m in enumerate(mask) if m]

        # Find representative point (closest to centroid)
        centroid = kmeans.cluster_centers_[cluster_id]
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        rep_idx = np.argmin(distances)

        clusters.append({
            'cluster_id': cluster_id,
            'centroid': centroid.tolist(),
            'occurrence_count': int(mask.sum()),
            'mean_elevation': float(np.nanmean(cluster_elevations)) if cluster_elevations else None,
            'elevation_std': float(np.nanstd(cluster_elevations)) if cluster_elevations else None,
            'mean_treecover': float(np.nanmean(cluster_treecover)) if cluster_treecover else None,
            'forest_loss_fraction': float(np.nanmean([1 if l else 0 for l in cluster_losses])) if cluster_losses else None,
            'representative_lat': cluster_lats[rep_idx] if cluster_lats else None,
            'representative_lon': cluster_lons[rep_idx] if cluster_lons else None,
        })

    return clusters


def compute_elevation_profile(metadata: dict) -> dict:
    """Compute elevation statistics for a species."""
    elevations = [e for e in metadata['elevations'] if e is not None]

    if not elevations:
        return None

    elevations = np.array(elevations)
    return {
        'min_elevation': float(np.min(elevations)),
        'max_elevation': float(np.max(elevations)),
        'mean_elevation': float(np.mean(elevations)),
        'median_elevation': float(np.median(elevations)),
        'p10_elevation': float(np.percentile(elevations, 10)),
        'p90_elevation': float(np.percentile(elevations, 90)),
        'elevation_std': float(np.std(elevations)),
        'occurrence_count': len(elevations)
    }


def save_centroids(conn, taxon_id: str, clusters: List[dict]):
    """Save cluster centroids to PostgreSQL."""
    with conn.cursor() as cur:
        # Delete existing centroids for this species
        cur.execute(
            "DELETE FROM species_habitat_centroids WHERE taxon_id = %s",
            (taxon_id,)
        )

        # Insert new centroids
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
                cluster['centroid'],  # pgvector handles list -> vector conversion
                cluster['occurrence_count'],
                cluster['mean_elevation'],
                cluster['elevation_std'],
                cluster['mean_treecover'],
                cluster['forest_loss_fraction'],
                cluster['representative_lat'],
                cluster['representative_lon']
            ))

        conn.commit()


def save_elevation_profile(conn, taxon_id: str, profile: dict):
    """Save elevation profile to PostgreSQL."""
    if profile is None:
        return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO species_elevation_profiles
            (taxon_id, min_elevation, max_elevation, mean_elevation, median_elevation,
             p10_elevation, p90_elevation, elevation_std, occurrence_count, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (taxon_id) DO UPDATE SET
                min_elevation = EXCLUDED.min_elevation,
                max_elevation = EXCLUDED.max_elevation,
                mean_elevation = EXCLUDED.mean_elevation,
                median_elevation = EXCLUDED.median_elevation,
                p10_elevation = EXCLUDED.p10_elevation,
                p90_elevation = EXCLUDED.p90_elevation,
                elevation_std = EXCLUDED.elevation_std,
                occurrence_count = EXCLUDED.occurrence_count,
                updated_at = NOW()
        """, (
            taxon_id,
            profile['min_elevation'],
            profile['max_elevation'],
            profile['mean_elevation'],
            profile['median_elevation'],
            profile['p10_elevation'],
            profile['p90_elevation'],
            profile['elevation_std'],
            profile['occurrence_count']
        ))
        conn.commit()


def process_species(
    bq_client,
    pg_conn,
    taxon_id: str,
    min_k: int = 3,
    max_k: int = 10
) -> bool:
    """Process a single species: fetch, cluster, save."""
    try:
        # Fetch embeddings
        embeddings, metadata = get_species_embeddings(bq_client, taxon_id)

        if len(embeddings) == 0:
            logger.warning(f"No valid embeddings for {taxon_id}")
            return False

        # Cluster
        clusters = cluster_species(embeddings, metadata, min_k, max_k)

        # Save centroids
        save_centroids(pg_conn, taxon_id, clusters)

        # Compute and save elevation profile
        profile = compute_elevation_profile(metadata)
        save_elevation_profile(pg_conn, taxon_id, profile)

        logger.info(f"Processed {taxon_id}: {len(embeddings)} embeddings -> {len(clusters)} clusters")
        return True

    except Exception as e:
        logger.error(f"Error processing {taxon_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Cluster species habitat embeddings")
    parser.add_argument("--min-clusters", type=int, default=3, help="Minimum clusters per species")
    parser.add_argument("--max-clusters", type=int, default=10, help="Maximum clusters per species")
    parser.add_argument("--min-occurrences", type=int, default=10, help="Minimum occurrences to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Commit every N species")
    parser.add_argument("--start-from", type=str, default=None, help="Start from specific taxon_id")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to database")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Habitat Centroid Clustering Pipeline")
    logger.info("=" * 60)
    logger.info(f"Clusters per species: {args.min_clusters}-{args.max_clusters}")
    logger.info(f"Minimum occurrences: {args.min_occurrences}")

    # Initialize clients
    bq_client = get_bigquery_client()
    pg_conn = get_postgres_connection()

    # Ensure schema
    if not args.dry_run:
        ensure_postgres_schema(pg_conn)

    # Get species list
    species_list = get_species_list(bq_client, args.min_occurrences)

    # Start from specific species if requested
    if args.start_from:
        try:
            start_idx = next(i for i, (tid, _) in enumerate(species_list) if tid == args.start_from)
            species_list = species_list[start_idx:]
            logger.info(f"Starting from {args.start_from} (index {start_idx})")
        except StopIteration:
            logger.warning(f"Species {args.start_from} not found, starting from beginning")

    # Process species
    processed = 0
    failed = 0
    start_time = datetime.now()

    for i, (taxon_id, occ_count) in enumerate(species_list):
        if args.dry_run:
            logger.info(f"[DRY RUN] Would process {taxon_id} ({occ_count} occurrences)")
            continue

        success = process_species(
            bq_client, pg_conn, taxon_id,
            args.min_clusters, args.max_clusters
        )

        if success:
            processed += 1
        else:
            failed += 1

        # Progress logging
        if (i + 1) % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed * 3600
            logger.info(f"Progress: {i + 1}/{len(species_list)} ({rate:.0f}/hour)")

    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info(f"Completed: {processed} species processed, {failed} failed")
    logger.info(f"Total time: {elapsed/60:.1f} minutes")
    logger.info("=" * 60)

    pg_conn.close()


if __name__ == "__main__":
    main()
