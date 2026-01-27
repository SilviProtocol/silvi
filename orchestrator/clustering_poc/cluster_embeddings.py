#!/usr/bin/env python3
"""
K-Prototypes Clustering for AlphaEarth Embeddings
Based on the AlphaEarth Builder's Guide methodology

This script:
1. Loads 45,677 clean embeddings from CSV
2. Performs k-prototypes clustering per species
3. Extracts representative centroids
4. Saves results for PostgreSQL storage
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import json
from pathlib import Path
from collections import defaultdict
import sys

print("="*70)
print("AlphaEarth Embeddings - K-Prototypes Clustering POC")
print("="*70)

# Load embeddings
print("\n📊 Loading embeddings...")
df = pd.read_csv('embeddings_clean.csv')
print(f"✅ Loaded {len(df):,} embeddings")
print(f"   Species: {df['taxon_id'].nunique()}")
print(f"   Columns: {len(df.columns)}")

# Extract embedding columns (A00-A63)
embedding_cols = [f'A{i:02d}' for i in range(64)]
print(f"\n🔢 Embedding dimensions: {len(embedding_cols)}")

# Verify all embedding columns exist
missing = [col for col in embedding_cols if col not in df.columns]
if missing:
    print(f"⚠️  Missing columns: {missing}")
    sys.exit(1)

print("\n" + "="*70)
print("CLUSTERING STRATEGY")
print("="*70)
print("""
Per AlphaEarth Builder's Guide:
1. Cluster embeddings by species
2. Find optimal K for each species (or use fixed K)
3. Extract centroid for each cluster
4. Store centroids as species representation

For POC, we'll use:
- Fixed K=5 clusters per species (can be optimized later)
- Species with <5 occurrences: use all points as centroids
""")

# Parameters
K_CLUSTERS = 5
MIN_OCCURRENCES_FOR_CLUSTERING = 5

print(f"\n⚙️  Parameters:")
print(f"   K clusters per species: {K_CLUSTERS}")
print(f"   Min occurrences for clustering: {MIN_OCCURRENCES_FOR_CLUSTERING}")

# Group by species
print("\n📦 Grouping by species...")
species_groups = df.groupby('taxon_id')
print(f"✅ Found {len(species_groups)} unique species")

# Analyze species distribution
occurrence_counts = df['taxon_id'].value_counts()
print(f"\n📊 Species occurrence distribution:")
print(f"   Min: {occurrence_counts.min()}")
print(f"   Max: {occurrence_counts.max()}")
print(f"   Mean: {occurrence_counts.mean():.1f}")
print(f"   Median: {occurrence_counts.median():.1f}")

# Count how many species have enough data for clustering
clust_species = (occurrence_counts >= MIN_OCCURRENCES_FOR_CLUSTERING).sum()
noCluster_species = (occurrence_counts < MIN_OCCURRENCES_FOR_CLUSTERING).sum()
print(f"\n   Will cluster: {clust_species} species")
print(f"   Too few occurrences: {noCluster_species} species")

print("\n" + "="*70)
print("CLUSTERING PROCESS")
print("="*70)

# Storage for results
centroids_data = []
clustering_stats = defaultdict(dict)

# Standardize embeddings (important for K-Means)
print("\n🔧 Standardizing embeddings...")
scaler = StandardScaler()
embeddings_all = df[embedding_cols].values
embeddings_standardized = scaler.fit_transform(embeddings_all)
df_standardized = df.copy()
df_standardized[embedding_cols] = embeddings_standardized
print("✅ Standardization complete")

print("\n🔄 Processing species...")
processed = 0
failed = 0

for taxon_id, group in df_standardized.groupby('taxon_id'):
    processed += 1
    n_occurrences = len(group)

    if processed % 10 == 0:
        print(f"   Progress: {processed}/{len(species_groups)} species", end='\r')

    # Get standardized embeddings for this species
    species_embeddings = group[embedding_cols].values

    # Strategy depends on number of occurrences
    if n_occurrences < MIN_OCCURRENCES_FOR_CLUSTERING:
        # Too few points - use all as centroids
        centroids = species_embeddings
        labels = list(range(n_occurrences))
        n_clusters_actual = n_occurrences
        method = 'all_points'
    else:
        # Enough points - perform K-Means clustering
        try:
            k = min(K_CLUSTERS, n_occurrences)  # Can't have more clusters than points
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(species_embeddings)
            centroids = kmeans.cluster_centers_
            n_clusters_actual = k
            method = 'kmeans'
        except Exception as e:
            print(f"\n⚠️  Failed to cluster {taxon_id}: {e}")
            failed += 1
            # Fallback: use all points
            centroids = species_embeddings
            labels = list(range(n_occurrences))
            n_clusters_actual = n_occurrences
            method = 'fallback'

    # Store centroids and metadata
    for cluster_id, centroid in enumerate(centroids):
        # Get original (unstandardized) centroid by inverse transform
        centroid_original = scaler.inverse_transform(centroid.reshape(1, -1))[0]

        # Count how many occurrences in this cluster
        cluster_size = (np.array(labels) == cluster_id).sum()

        # Get representative lat/lon from cluster members
        cluster_members = group[np.array(labels) == cluster_id]
        rep_lat = cluster_members['latitude'].mean()
        rep_lon = cluster_members['longitude'].mean()
        rep_year = int(cluster_members['orig_year'].mode()[0])  # Most common year

        centroids_data.append({
            'taxon_id': taxon_id,
            'cluster_id': cluster_id,
            'cluster_size': int(cluster_size),
            'total_occurrences': n_occurrences,
            'clustering_method': method,
            'representative_lat': float(rep_lat),
            'representative_lon': float(rep_lon),
            'representative_year': rep_year,
            **{f'centroid_a{i:02d}': float(centroid_original[i]) for i in range(64)}
        })

    clustering_stats[taxon_id] = {
        'n_occurrences': n_occurrences,
        'n_clusters': n_clusters_actual,
        'method': method
    }

print(f"\n✅ Clustering complete!")
print(f"   Processed: {processed} species")
print(f"   Failed: {failed} species")
print(f"   Total centroids: {len(centroids_data)}")

print("\n" + "="*70)
print("RESULTS SUMMARY")
print("="*70)

# Convert to DataFrame
centroids_df = pd.DataFrame(centroids_data)
print(f"\n📊 Centroids DataFrame:")
print(f"   Total rows: {len(centroids_df):,}")
print(f"   Unique species: {centroids_df['taxon_id'].nunique()}")
print(f"   Columns: {len(centroids_df.columns)}")

# Method breakdown
method_counts = centroids_df.groupby('clustering_method').size()
print(f"\n🔍 Clustering methods used:")
for method, count in method_counts.items():
    pct = (count / len(centroids_df) * 100)
    print(f"   {method}: {count:,} centroids ({pct:.1f}%)")

# Cluster size stats
print(f"\n📈 Cluster statistics:")
print(f"   Avg cluster size: {centroids_df['cluster_size'].mean():.1f}")
print(f"   Max cluster size: {centroids_df['cluster_size'].max()}")
print(f"   Min cluster size: {centroids_df['cluster_size'].min()}")

# Species with most clusters
top_species = centroids_df.groupby('taxon_id').size().nlargest(5)
print(f"\n🏆 Species with most clusters:")
for taxon_id, n_clusters in top_species.items():
    n_occ = centroids_df[centroids_df['taxon_id']==taxon_id]['total_occurrences'].iloc[0]
    print(f"   {taxon_id}: {n_clusters} clusters ({n_occ} occurrences)")

# Save results
print("\n💾 Saving results...")

# Save centroids to CSV
centroids_df.to_csv('species_centroids.csv', index=False)
print(f"✅ Saved centroids to: species_centroids.csv")

# Save clustering stats to JSON
with open('clustering_stats.json', 'w') as f:
    json.dump(clustering_stats, f, indent=2)
print(f"✅ Saved stats to: clustering_stats.json")

# Create summary report
summary = {
    'total_embeddings': len(df),
    'total_species': len(species_groups),
    'total_centroids': len(centroids_df),
    'centroids_per_species_avg': len(centroids_df) / len(species_groups),
    'clustering_methods': method_counts.to_dict(),
    'parameters': {
        'k_clusters': K_CLUSTERS,
        'min_occurrences': MIN_OCCURRENCES_FOR_CLUSTERING
    }
}

with open('clustering_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print(f"✅ Saved summary to: clustering_summary.json")

print("\n" + "="*70)
print("✅ CLUSTERING POC COMPLETE!")
print("="*70)
print(f"""
Next Steps:
1. Store centroids in PostgreSQL treekipedia database
2. Create API endpoint to query species centroids
3. Build UI visualization for embedding space
4. Implement similarity search across species

Files created:
- species_centroids.csv ({len(centroids_df):,} rows)
- clustering_stats.json (per-species metadata)
- clustering_summary.json (overall statistics)
""")
