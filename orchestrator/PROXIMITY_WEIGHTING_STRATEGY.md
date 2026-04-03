# Proximity-Based Density Weighting for Habitat Clustering

**Date**: January 21, 2026
**Supersedes**: Pixel-based occurrence counting approach
**Key Insight**: Sampling bias is spatial, not per-pixel. A hectare with 1000 pixels (each with 1 occurrence) is just as biased as 1 pixel with 1000 occurrences.

---

## The Problem with Pixel-Based Counting

### Scenario: Research Station Bias

```
┌────────────────────────────────────────┐
│ Research Station Area (1 hectare)      │
│                                        │
│  • • • • • • • • • • • • • • • • • •  │
│  • • • • • • • • • • • • • • • • • •  │
│  • • • • • • • • • • • • • • • • • •  │
│  (1000 pixels, each with 1 occurrence) │
└────────────────────────────────────────┘

vs.

┌────────────────────────────────────────┐
│ Remote Forest (1000 hectares)          │
│                                        │
│          •               •             │
│                    •                   │
│     •                        •         │
│  (5 pixels, each with 1 occurrence)    │
└────────────────────────────────────────┘
```

**With pixel-based weighting**: Both areas have weight proportional to pixels = 1000 : 5 = 200:1
**Reality**: The research station is massively over-sampled and should have ~5:5 = 1:1 influence

---

## Solution: Kernel Density Estimation (KDE) Weighting

### Concept

For each observation point, calculate the **local density of observations** within a radius, then apply inverse-density weighting:

```
weight_i = 1 / density_i
```

Points in crowded areas (high density) get lower weights; isolated points (low density) get higher weights.

### Implementation Options

#### Option 1: Ball Tree KDE (Exact, Memory-Intensive)

```python
from sklearn.neighbors import BallTree
import numpy as np

def compute_density_weights(coords, radius_km=1.0):
    """
    Compute inverse-density weights using Ball Tree.

    coords: np.array of shape (n, 2) with [lat, lon]
    radius_km: Radius for density estimation
    """
    # Convert to radians for haversine
    coords_rad = np.radians(coords)

    # Build ball tree
    tree = BallTree(coords_rad, metric='haversine')

    # Radius in radians (Earth radius ≈ 6371 km)
    radius_rad = radius_km / 6371.0

    # Count neighbors within radius for each point
    counts = tree.query_radius(coords_rad, r=radius_rad, count_only=True)

    # Inverse density weight (with log smoothing)
    # Adding 1 to avoid division by zero
    weights = 1.0 / np.log1p(counts)

    # Normalize to [0, 1]
    weights = weights / weights.max()

    return weights, counts
```

**Pros**: Exact, handles irregular boundaries
**Cons**: O(n log n) per species, memory-intensive for large n

#### Option 2: Grid-Based Density (Fast, Approximate)

```python
import numpy as np
from collections import defaultdict

def compute_grid_density_weights(coords, cell_size_km=1.0):
    """
    Compute inverse-density weights using spatial grid cells.

    Much faster than Ball Tree for large datasets.
    """
    # Convert km to degrees (approximate)
    # 1 degree ≈ 111 km at equator
    cell_size_deg = cell_size_km / 111.0

    # Assign each point to a grid cell
    cell_x = (coords[:, 1] / cell_size_deg).astype(int)  # longitude
    cell_y = (coords[:, 0] / cell_size_deg).astype(int)  # latitude

    # Count points per cell
    cell_counts = defaultdict(int)
    for x, y in zip(cell_x, cell_y):
        cell_counts[(x, y)] += 1

    # Compute density as count in cell + adjacent cells (3x3 neighborhood)
    densities = np.zeros(len(coords))
    for i, (x, y) in enumerate(zip(cell_x, cell_y)):
        density = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                density += cell_counts.get((x + dx, y + dy), 0)
        densities[i] = density

    # Inverse density weight with log smoothing
    weights = 1.0 / np.log1p(densities)
    weights = weights / weights.max()

    return weights, densities
```

**Pros**: O(n) complexity, low memory
**Cons**: Approximation, edge effects at cell boundaries

#### Option 3: Geohash-Based Density (Hierarchical, Very Fast)

```python
import geohash2
from collections import Counter

def compute_geohash_density_weights(lats, lons, precision=5):
    """
    Use geohash at precision 5 (~5km × 5km cells) for density.

    Precision levels:
    - 4: ~40km × 20km
    - 5: ~5km × 5km
    - 6: ~1.2km × 0.6km
    - 7: ~150m × 150m
    """
    # Compute geohash for each point
    geohashes = [geohash2.encode(lat, lon, precision) for lat, lon in zip(lats, lons)]

    # Count points per geohash cell
    cell_counts = Counter(geohashes)

    # Map counts back to points
    counts = np.array([cell_counts[gh] for gh in geohashes])

    # Include neighbors (8 adjacent geohashes)
    # geohash2.neighbors() gives adjacent cells
    density = counts.copy()
    for i, gh in enumerate(geohashes):
        neighbors = geohash2.neighbors(gh)
        for neighbor in neighbors.values():
            density[i] += cell_counts.get(neighbor, 0)

    # Inverse density weight
    weights = 1.0 / np.log1p(density)
    weights = weights / weights.max()

    return weights, density
```

**Pros**: Very fast, uses existing geohash infrastructure
**Cons**: Fixed cell shapes, precision tuning needed

---

## Recommended Approach: Multi-Scale Density

Use **hierarchical geohash density** at multiple scales to capture both local and regional sampling bias:

```python
def compute_multiscale_density_weights(lats, lons):
    """
    Combine density at multiple scales for robust weighting.

    Scales:
    - Local (precision 6, ~1km): Captures research station clusters
    - Regional (precision 5, ~5km): Captures city/road bias
    - Broad (precision 4, ~40km): Captures continental sampling patterns
    """
    import geohash2
    from collections import Counter
    import numpy as np

    n = len(lats)

    # Compute geohashes at each precision
    gh_local = [geohash2.encode(lat, lon, 6) for lat, lon in zip(lats, lons)]
    gh_regional = [geohash2.encode(lat, lon, 5) for lat, lon in zip(lats, lons)]
    gh_broad = [geohash2.encode(lat, lon, 4) for lat, lon in zip(lats, lons)]

    # Count at each scale
    counts_local = Counter(gh_local)
    counts_regional = Counter(gh_regional)
    counts_broad = Counter(gh_broad)

    # Map back to points
    density_local = np.array([counts_local[gh] for gh in gh_local])
    density_regional = np.array([counts_regional[gh] for gh in gh_regional])
    density_broad = np.array([counts_broad[gh] for gh in gh_broad])

    # Combine scales with different weights
    # Local bias matters most for clustering
    combined_density = (
        0.5 * density_local +
        0.3 * density_regional +
        0.2 * density_broad
    )

    # Inverse density weight with log smoothing
    weights = 1.0 / np.log1p(combined_density)

    # Normalize to [0, 1]
    weights = weights / weights.max()

    return weights, {
        'local': density_local,
        'regional': density_regional,
        'broad': density_broad,
        'combined': combined_density
    }
```

---

## Integration with Clustering Pipeline

### Modified Clustering Function

```python
def cluster_species_proximity_weighted(
    embeddings: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    min_k: int = 3,
    max_k: int = 10
) -> List[dict]:
    """
    Cluster embeddings with proximity-based density weighting.
    """
    n_samples = len(embeddings)

    if n_samples < min_k:
        return [create_single_centroid(embeddings, lats, lons)]

    # Compute proximity-based weights
    weights, density_info = compute_multiscale_density_weights(lats, lons)

    # Find optimal k with weighted silhouette
    optimal_k = find_optimal_clusters_weighted(embeddings, weights, min_k, max_k)

    # Weighted K-means
    centroids, labels = weighted_kmeans_custom(embeddings, weights, optimal_k)

    # Compute cluster statistics
    clusters = []
    for k in range(optimal_k):
        mask = labels == k
        cluster_weights = weights[mask]

        # Weighted centroid
        centroid = np.average(embeddings[mask], axis=0, weights=cluster_weights)

        # Effective sample size (accounts for weighting)
        ess = (cluster_weights.sum() ** 2) / (cluster_weights ** 2).sum()

        clusters.append({
            'cluster_id': k,
            'centroid': centroid.tolist(),
            'n_pixels': int(mask.sum()),
            'effective_sample_size': float(ess),
            'mean_density': float(density_info['combined'][mask].mean()),
            'mean_weight': float(cluster_weights.mean()),
            # ... other metadata
        })

    return clusters
```

---

## Why This Works Better

### Example: European Oak (Quercus robur)

**Before (unweighted or pixel-count weighted)**:
```
Cluster 1: Urban parks in UK, Netherlands, Germany (80% of centroids)
Cluster 2: Agricultural areas with scattered trees
Cluster 3: (rare) Actual forest habitats
```

**After (proximity-density weighted)**:
```
Cluster 1: Lowland deciduous forests (primary habitat)
Cluster 2: Mixed oak-beech forests on slopes
Cluster 3: Urban/periurban populations (appropriately weighted down)
Cluster 4: Floodplain forests
Cluster 5: Northern range edge populations
```

---

## Recommended Parameters

| Scale | Geohash Precision | Approximate Size | Weight |
|-------|-------------------|------------------|--------|
| Local | 6 | ~1.2km × 0.6km | 0.5 |
| Regional | 5 | ~5km × 5km | 0.3 |
| Broad | 4 | ~40km × 20km | 0.2 |

### Why These Scales?

- **Local (1km)**: Captures research station / botanical garden clusters
- **Regional (5km)**: Captures city / road network bias
- **Broad (40km)**: Captures continental sampling patterns (Europe well-sampled, Africa under-sampled)

---

## Performance Considerations

For 3.4M embeddings across 18K species:

| Method | Time Complexity | Memory | Recommended |
|--------|-----------------|--------|-------------|
| Ball Tree | O(n log n) per species | High | ❌ Too slow |
| Grid-based | O(n) total | Low | ✅ Good |
| Geohash | O(n) total | Very low | ✅✅ Best |

Geohash encoding is ~100K points/second in Python, so 3.4M points = ~34 seconds.

---

## Implementation Plan

1. **Add proximity weighting to clustering pipeline**
   - Modify `cluster_habitat_centroids.py`
   - Use multi-scale geohash density

2. **Store density metadata**
   - Add `local_density`, `regional_density` columns to export
   - Useful for diagnostics and API responses

3. **Validate**
   - Compare centroids for well-studied species (Quercus robur, Pinus sylvestris)
   - Check if rare habitat types are now represented

---

## Summary

| Approach | Bias Addressed | Pros | Cons |
|----------|----------------|------|------|
| Pixel-count | Per-pixel saturation | Simple | Misses spatial clustering |
| **Proximity-density** | **Spatial clustering** | **Correct** | Slightly more compute |
| Spatial thinning | All | Data loss | Throws away information |

**Recommendation**: Use **multi-scale geohash density weighting** with log-inverse weights. This correctly handles the research station scenario where 1000 pixels in 1 hectare should have similar weight to 5 pixels in 1000 hectares.
