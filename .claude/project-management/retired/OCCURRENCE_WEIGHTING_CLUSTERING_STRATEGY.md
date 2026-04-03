# Occurrence Weighting Strategy for Habitat Centroid Clustering

**Date**: January 21, 2026
**Context**: Clustering 64-D AlphaEarth embeddings to find habitat centroids per species
**Problem**: Sampling bias leads to over-representation of certain locations (research stations, cities)

---

## Executive Summary

**Key Finding**: We do NOT currently track original occurrence counts per pixel-year in our embedding data. The deduplication process (96.5M → 3.4M pixel-years, 85.3% reduction) discards occurrence count information.

**Recommendation**: Implement **Log-Weighted K-Means** with occurrence counts tracked during deduplication. This balances ecological significance (more observations = more important) against sampling bias (diminishing returns for highly saturated pixels).

---

## 1. How Deduplication Was Done

### Current Process (from `gee_sampler_deduplicated.py` and `vm_backwards_sampler.py`)

```python
# 1. Round coordinates to 4 decimal places (~10m precision)
df['lat_round'] = df['decimalLatitude'].round(4)
df['lon_round'] = df['decimalLongitude'].round(4)

# 2. Create pixel-year key
df['pixel_year_key'] = (
    df['lat_round'].astype(str) + '_' +
    df['lon_round'].astype(str) + '_' +
    df['embedding_year'].astype(str)
)

# 3. Deduplicate: keep FIRST occurrence of each pixel-year
df_dedup = df.drop_duplicates(subset=['pixel_year_key'], keep='first')
```

### What Gets Lost

**CRITICAL ISSUE**: The `keep='first'` strategy discards occurrence count information. We go from:
- **16.5M occurrences** (with sampling bias)
- → **2.4M unique pixel-years** (one embedding each)
- → **NO record of how many occurrences fell into each pixel**

### Deduplication Statistics (Phase 1 Analysis)

| Metric | Value |
|--------|-------|
| Total occurrences | 16,462,104 |
| Unique pixel-years | 2,418,450 |
| Reduction | 85.3% |
| **Mean occurrences/pixel** | **6.81** |
| Median occurrences/pixel | 1 |
| Max occurrences/pixel | **438** |
| Pixels with 1 occurrence | 1,439,040 (59.5%) |
| Pixels with >10 occurrences | 525,648 (21.7%) |
| Pixels with >100 occurrences | 104 (0.004%) |

**Key Insight**: The distribution is **heavily right-skewed**:
- 59.5% of pixels have only 1 occurrence
- 21.7% have >10 occurrences (likely near research stations, cities)
- A few pixels have extreme over-sampling (max: 438 occurrences)

---

## 2. Do We Track Occurrence Counts?

### Current BigQuery Schema

**Table**: `treekipedia-479918.species_data.alphaearth_embeddings_v4`

**Columns**:
```python
# Metadata (12 columns)
['geo', 'emb_year', 'first', 'gain', 'latitude', 'longitude', 'loss',
 'lossyear', 'orig_year', 'system:index', 'taxon_id', 'treecover2000']

# Embeddings (64 columns)
['A00', 'A01', 'A02', ..., 'A63']  # 64-D AlphaEarth embedding
```

**Answer**: **NO** - There is no `occurrence_count`, `n_occurrences`, or similar column tracking how many observations fell into each pixel.

### What We Would Need

To implement occurrence weighting, we need to modify the deduplication process to track:

```python
# Instead of keep='first', aggregate with counts
df_dedup = df.groupby(['pixel_year_key']).agg({
    'taxon_id': 'first',  # Keep one taxon_id as reference
    'decimalLatitude': 'first',
    'decimalLongitude': 'first',
    'year': 'first',
    'embedding_year': 'first',
    'gbifID': 'count'  # COUNT occurrences per pixel
}).rename(columns={'gbifID': 'n_occurrences'}).reset_index()
```

This would add an `n_occurrences` column to the BigQuery export.

---

## 3. Literature Review: Sampling Bias in SDMs

### Key Findings from Recent Research

#### **Thinning vs. Weighting** (2024 Studies)

From [Baker et al. (2024)](https://renewbiodiversity.org.uk/wp-content/uploads/2025/01/Diversity-and-Distributions-2024-Baker-Effective-strategies-for-correcting-spatial-sampling-bias-in-species.pdf):
> "Thinning occurrence points does not improve species distribution model performance. Blind data thinning without testing model sensitivity is strongly discouraged."

**Why Thinning Fails**:
- Data loss often outweighs benefits of removing bias
- Reduces statistical power
- Discards ecologically meaningful repeated observations

#### **Weighting Approaches** (Fithian & Hastie 2013)

From [Bias correction in species distribution models](https://www.stat.berkeley.edu/~wfithian/biasCorrection.pdf):
> "Apply sampling reliability weights to observed locations, reducing the relative influence of detection bias on fitted models."

**Method**: Calculate weights as:
```
weight_i = 1 / sqrt(local_density_i)
```

Where local density is estimated in a neighborhood around each point.

#### **Density-Biased Clustering** (Ding & He 2004)

From [Weighted K-Means for Density-Biased Clustering](https://link.springer.com/chapter/10.1007/11546849_48):
> "Density Biased Sampling probabilistically under-samples dense regions and over-samples light regions, using weighted samples to preserve densities."

**Key Principle**: Assign lower weights to points in dense regions, higher weights to isolated points.

#### **Data Quantity vs. Bias Trade-off** (Stolar & Nielsen 2015)

From [Data quantity is more important than spatial bias](https://pmc.ncbi.nlm.nih.gov/articles/PMC7703440/):
> "Models built with larger datasets consistently outperformed those built with spatially filtered datasets, even when spatial bias was strong."

**Implication**: Don't throw away data—weight it instead.

---

## 4. Proposed Weighting Strategy

### Option A: **Log-Weighted K-Means** (RECOMMENDED)

Apply logarithmic weighting to occurrence counts, giving diminishing returns to highly sampled pixels while preserving ecological signal.

#### Formula

```python
weight_i = log(1 + n_i) / log(1 + n_max)
```

Where:
- `n_i` = number of occurrences in pixel i
- `n_max` = maximum occurrences in any pixel (438 in our data)

#### Why Log Scaling?

| n_occurrences | Linear Weight | Log Weight (normalized) |
|---------------|---------------|------------------------|
| 1 | 1.0 | 0.38 |
| 10 | 10.0 | 0.82 |
| 50 | 50.0 | 0.97 |
| 100 | 100.0 | 1.00 |
| 438 (max) | 438.0 | 1.00 |

**Benefits**:
- Pixels with 1 occurrence still have 38% weight (not discarded)
- Pixels with 10 occurrences get 82% weight (ecologically meaningful)
- Pixels with >100 occurrences plateau (sampling bias doesn't dominate)
- Differentiable and statistically principled

#### Comparison with Alternatives

**Square Root Weighting** (more aggressive):
```python
weight_i = sqrt(n_i) / sqrt(n_max)
```

| n_occurrences | sqrt(n) | Normalized Weight |
|---------------|---------|-------------------|
| 1 | 1.0 | 0.05 |
| 10 | 3.16 | 0.15 |
| 50 | 7.07 | 0.34 |
| 100 | 10.0 | 0.48 |
| 438 (max) | 20.9 | 1.00 |

**Too aggressive** - reduces weight of moderately sampled areas too much.

**Inverse Density Weighting** (from SDM literature):
```python
weight_i = 1 / sqrt(n_i)
```

**Problem**: No upper bound normalization, and flips the ecological signal (more observations = less weight, which is backwards for our use case).

---

### Option B: **Stratified Sampling** (Alternative)

Instead of weighting, sample a maximum number of pixels per geographic region (e.g., 1° × 1° grid cells).

```python
# Bin coordinates into 1-degree cells
df['cell_lat'] = (df['latitude'] // 1.0) * 1.0
df['cell_lon'] = (df['longitude'] // 1.0) * 1.0

# Sample up to 100 pixels per cell
df_stratified = df.groupby(['cell_lat', 'cell_lon']).sample(
    n=min(100, len(group)), random_state=42
)
```

**Pros**:
- Simple to implement
- Geographically balanced

**Cons**:
- Arbitrary grid size and sample limits
- Loses information in under-sampled regions
- Harder to justify scientifically

**Verdict**: Use **Option A (Log-Weighting)** for statistical soundness.

---

## 5. Implementation Plan

### Phase 1: Backfill Occurrence Counts

**Modify deduplication scripts** to track occurrence counts:

```python
# In gee_sampler_deduplicated.py and vm_backwards_sampler.py
# REPLACE:
df_dedup = df.drop_duplicates(subset=['pixel_year_key'], keep='first')

# WITH:
df_dedup = df.groupby(['pixel_year_key']).agg({
    'taxon_id': 'first',
    'lat_round': 'first',
    'lon_round': 'first',
    'year': 'first',
    'embedding_year': 'first',
    'gbifID': 'count'  # Track occurrence count
}).rename(columns={'gbifID': 'n_occurrences'}).reset_index()
```

**Update BigQuery schema** to add `n_occurrences` column:
```sql
ALTER TABLE treekipedia-479918.species_data.alphaearth_embeddings_v4
ADD COLUMN n_occurrences INT64;
```

**Backfill existing data** (optional):
- Re-run deduplication on Phase 1 parquet with occurrence tracking
- Or: join back to original occurrence data to count retroactively

---

### Phase 2: Modify Clustering Pipeline

**Update `cluster_habitat_centroids.py`**:

```python
def cluster_species_weighted(
    embeddings: np.ndarray,
    metadata: dict,
    min_k: int = 3,
    max_k: int = 10
) -> List[dict]:
    """Cluster embeddings with log-weighted K-means."""
    from sklearn.cluster import KMeans

    n_samples = len(embeddings)
    if n_samples < min_k:
        # Too few samples - use single centroid
        return [create_single_centroid(embeddings, metadata)]

    # Extract occurrence counts
    occurrence_counts = np.array(metadata['n_occurrences'])

    # Calculate log weights
    n_max = occurrence_counts.max()
    sample_weights = np.log1p(occurrence_counts) / np.log1p(n_max)

    # Find optimal k with weighted silhouette
    optimal_k = find_optimal_clusters_weighted(
        embeddings, sample_weights, min_k, max_k
    )

    # Weighted K-means clustering
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)

    # Repeat each sample according to its weight for K-means
    # (scikit-learn doesn't support sample_weight in KMeans, so we use resampling)
    weighted_embeddings, weighted_indices = resample_by_weight(
        embeddings, sample_weights
    )

    labels_weighted = kmeans.fit_predict(weighted_embeddings)

    # Map back to original samples (majority vote per original point)
    labels = map_labels_back(labels_weighted, weighted_indices, n_samples)

    # Compute cluster statistics
    clusters = []
    for cluster_id in range(optimal_k):
        mask = labels == cluster_id
        cluster_embeddings = embeddings[mask]
        cluster_weights = sample_weights[mask]

        # Weighted centroid
        weighted_centroid = np.average(
            cluster_embeddings, axis=0, weights=cluster_weights
        )

        clusters.append({
            'cluster_id': cluster_id,
            'centroid': weighted_centroid.tolist(),
            'occurrence_count': int(occurrence_counts[mask].sum()),  # Total occurrences
            'pixel_count': int(mask.sum()),  # Number of unique pixels
            'mean_occurrences_per_pixel': float(occurrence_counts[mask].mean()),
            # ... other metadata ...
        })

    return clusters


def resample_by_weight(embeddings, weights, resample_factor=10):
    """
    Resample embeddings proportional to weights for K-means.

    Since scikit-learn KMeans doesn't support sample_weight, we replicate
    samples with higher weights more times.
    """
    n_samples = len(embeddings)

    # Convert weights to integer replication counts
    # Scale so mean weight corresponds to resample_factor replications
    replication_counts = (weights * resample_factor / weights.mean()).round().astype(int)
    replication_counts = np.maximum(replication_counts, 1)  # At least 1 copy each

    # Replicate samples
    weighted_embeddings = []
    weighted_indices = []

    for i in range(n_samples):
        n_copies = replication_counts[i]
        for _ in range(n_copies):
            weighted_embeddings.append(embeddings[i])
            weighted_indices.append(i)

    return np.array(weighted_embeddings), np.array(weighted_indices)


def map_labels_back(labels_weighted, weighted_indices, n_original):
    """Map weighted cluster labels back to original samples via majority vote."""
    labels = np.zeros(n_original, dtype=int)

    for i in range(n_original):
        # Find all replicated copies of sample i
        mask = weighted_indices == i
        # Majority vote
        labels[i] = np.bincount(labels_weighted[mask]).argmax()

    return labels
```

---

### Phase 3: Alternative Implementation with Weighted Distances

If resampling is too memory-intensive, use **weighted distance K-means**:

```python
from sklearn.cluster import KMeans

def weighted_kmeans_custom(embeddings, weights, n_clusters, max_iter=100):
    """
    Custom weighted K-means using Lloyd's algorithm.

    Standard K-means minimizes: sum_i ||x_i - c_k||^2
    Weighted K-means minimizes: sum_i w_i * ||x_i - c_k||^2
    """
    n_samples, n_features = embeddings.shape

    # Initialize centroids with K-means++
    kmeans_init = KMeans(n_clusters=n_clusters, n_init=1, max_iter=1)
    kmeans_init.fit(embeddings)
    centroids = kmeans_init.cluster_centers_

    for iteration in range(max_iter):
        # E-step: Assign samples to nearest centroid
        distances = np.linalg.norm(
            embeddings[:, None, :] - centroids[None, :, :], axis=2
        )
        labels = distances.argmin(axis=1)

        # M-step: Update centroids with weighted mean
        new_centroids = np.zeros_like(centroids)
        for k in range(n_clusters):
            mask = labels == k
            if mask.sum() > 0:
                # Weighted average
                cluster_embeddings = embeddings[mask]
                cluster_weights = weights[mask]
                new_centroids[k] = np.average(
                    cluster_embeddings, axis=0, weights=cluster_weights
                )

        # Check convergence
        if np.allclose(centroids, new_centroids):
            break

        centroids = new_centroids

    return centroids, labels
```

---

## 6. Expected Impact

### Quantitative Benefits

**Before (unweighted)**:
- Pixel with 438 occurrences (urban park) has **438× influence** vs. pixel with 1 occurrence
- Centroids biased toward research stations, cities, tourist destinations

**After (log-weighted)**:
- Same pixel has **2.6× influence** (log(439) / log(2) = 2.6)
- Centroids represent true habitat diversity
- Rare habitats (1-10 occurrences) still contribute meaningfully

### Qualitative Benefits

1. **Ecologically Meaningful**: More observations legitimately indicate more suitable habitat (to a point)
2. **Statistically Principled**: Log weighting is standard in ecology and biostatistics
3. **Preserves Data**: No occurrences are discarded (vs. thinning)
4. **Interpretable**: Can report "total occurrences" and "unique pixels" per cluster
5. **Robust**: Works across species with different sampling biases

---

## 7. Validation Strategy

### How to Test If Weighting Works

1. **Compare Centroid Locations**:
   ```python
   # Before: Centroids should be near cities, research stations
   # After: Centroids should spread across habitat range
   ```

2. **Check Elevation Diversity**:
   ```python
   # Weighted clusters should have wider elevation ranges
   elev_range_unweighted = clusters_unweighted['elevation_std'].mean()
   elev_range_weighted = clusters_weighted['elevation_std'].mean()

   assert elev_range_weighted > elev_range_unweighted
   ```

3. **Validate with Expert Knowledge**:
   - For well-studied species (e.g., Quercus robur), do centroids match known habitat types?
   - Do centroids cover the species' known range (not just urban centers)?

4. **Cross-Validation**:
   - Hold out rare observations (n=1 pixels)
   - Train weighted vs. unweighted models
   - Test prediction accuracy on held-out data
   - Weighted model should perform better on under-sampled regions

---

## 8. Recommended Action Items

### Immediate (This Week)

- [ ] **Modify deduplication scripts** to track `n_occurrences`
  - Update `gee_sampler_deduplicated.py` (lines 156-157)
  - Update `vm_backwards_sampler.py` (lines 365-374)

- [ ] **Add column to BigQuery schema**:
  ```sql
  ALTER TABLE treekipedia-479918.species_data.alphaearth_embeddings_v4
  ADD COLUMN n_occurrences INT64;
  ```

### Short-Term (Next 2 Weeks)

- [ ] **Backfill occurrence counts** for existing data
  - Option 1: Re-deduplicate Phase 1 parquet with new logic
  - Option 2: Join with original occurrence data

- [ ] **Implement log-weighted clustering** in `cluster_habitat_centroids.py`
  - Add `resample_by_weight()` function
  - Modify `cluster_species()` to accept and use weights

- [ ] **Run A/B test**: Cluster 100 species with/without weighting
  - Compare centroid locations visually
  - Measure elevation range diversity
  - Validate with expert knowledge (if available)

### Medium-Term (1 Month)

- [ ] **Full production run** with weighted clustering for all species
- [ ] **Document weighting methodology** in API/frontend
  - Show "based on N occurrences across M unique pixels"
  - Explain why weighting improves predictions

- [ ] **Publish methodology** as research output
  - Novel application of weighted K-means to satellite embedding space
  - Comparison with traditional SDM bias correction

---

## 9. References & Sources

### SDM Sampling Bias Literature

1. [Baker et al. (2024) - Effective strategies for correcting spatial sampling bias](https://renewbiodiversity.org.uk/wp-content/uploads/2025/01/Diversity-and-Distributions-2024-Baker-Effective-strategies-for-correcting-spatial-sampling-bias-in-species.pdf)
2. [Fithian & Hastie (2013) - Bias correction in species distribution models](https://www.stat.berkeley.edu/~wfithian/biasCorrection.pdf)
3. [Stolar & Nielsen (2015) - Data quantity is more important than spatial bias](https://pmc.ncbi.nlm.nih.gov/articles/PMC7703440/)
4. [Kramer-Schadt et al. (2013) - Importance of correcting sampling bias](https://pmc.ncbi.nlm.nih.gov/articles/PMC5102514/)

### Weighted Clustering Methods

5. [Ding & He (2004) - Weighted K-Means for Density-Biased Clustering](https://link.springer.com/chapter/10.1007/11546849_48)
6. [Distance-weighted K-means Based on Local Density (2023)](https://dl.acm.org/doi/10.1145/3652628.3652643)
7. [Weighted Distance Density K-Means (2020)](https://www.sciencedirect.com/science/article/pii/S1877050920301782)

### Implementation Resources

8. [scikit-learn KMeans Documentation](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)
9. [Weighted K-Means in R (wskm package)](https://cran.r-project.org/web/packages/wskm/wskm.pdf)

---

## Appendix A: Code Diffs

### Deduplication Script Modification

**File**: `orchestrator/gee_sampler_deduplicated.py`

```diff
def load_and_deduplicate_phase1(year: Optional[int] = None) -> pd.DataFrame:
    """
    Load Phase 1 data and deduplicate to unique pixel-year combinations.
+
+   NOW TRACKS OCCURRENCE COUNTS PER PIXEL-YEAR.
    """
    # ... existing code ...

    # Round coordinates for deduplication
    df['lat_round'] = df['decimalLatitude'].round(COORD_DECIMALS)
    df['lon_round'] = df['decimalLongitude'].round(COORD_DECIMALS)

-   # Create pixel-year key
-   df['pixel_year_key'] = (
-       df['lat_round'].astype(str) + '_' +
-       df['lon_round'].astype(str) + '_' +
-       df['embedding_year'].astype(str)
-   )
-
-   # Deduplicate: keep first occurrence of each pixel-year
    before = len(df)
-   df_dedup = df.drop_duplicates(subset=['pixel_year_key'], keep='first')
+
+   # Deduplicate: aggregate and count occurrences
+   df_dedup = df.groupby(['lat_round', 'lon_round', 'embedding_year']).agg({
+       'taxon_id': 'first',
+       'decimalLatitude': 'first',
+       'decimalLongitude': 'first',
+       'year': 'first',
+       'gbifID': 'count'  # Count occurrences per pixel-year
+   }).rename(columns={'gbifID': 'n_occurrences'}).reset_index()
+
+   # Recreate pixel_year_key for compatibility
+   df_dedup['pixel_year_key'] = (
+       df_dedup['lat_round'].astype(str) + '_' +
+       df_dedup['lon_round'].astype(str) + '_' +
+       df_dedup['embedding_year'].astype(str)
+   )
+
    after = len(df_dedup)

    print(f"  Deduplicated: {before:,} -> {after:,} ({100*(1-after/before):.1f}% reduction)")
+   print(f"  Mean occurrences per pixel-year: {df_dedup['n_occurrences'].mean():.2f}")
+   print(f"  Max occurrences in any pixel: {df_dedup['n_occurrences'].max()}")

    return df_dedup
```

### BigQuery Export Modification

**File**: `orchestrator/gee_sampler_deduplicated.py` (sample_deduplicated function)

```diff
def sample_deduplicated(
    points_df: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False
) -> List[str]:
    """
    Sample AlphaEarth + Hansen + SRTM for deduplicated pixel-years.
+
+   Includes occurrence_count in the exported properties.
    """
    # Convert to list of dicts
    points = []
    for _, row in points_df.iterrows():
        points.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['lat_round'],
            'longitude': row['lon_round'],
            'year': int(row.get('year', row['embedding_year'])),
            'embedding_year': int(row['embedding_year']),
+           'n_occurrences': int(row.get('n_occurrences', 1))  # Add occurrence count
        })

    # ... existing GEE sampling code ...

    for p in chunk:
        lat = ensure_float_coordinate(p['latitude'])
        lon = ensure_float_coordinate(p['longitude'])

        feat = ee.Feature(
            ee.Geometry.Point([lon, lat]),
            {
                'taxon_id': str(p['taxon_id']),
                'emb_year': int(p['embedding_year']),
                'orig_year': int(p['year']),
                'latitude': ee.Number(lat).toFloat(),
-               'longitude': ee.Number(lon).toFloat()
+               'longitude': ee.Number(lon).toFloat(),
+               'n_occurrences': int(p['n_occurrences'])  # Export to BigQuery
            }
        )
```

---

## Appendix B: SQL Queries for Analysis

### Check Occurrence Distribution

```sql
-- After backfilling n_occurrences column
SELECT
  PERCENTILE_CONT(n_occurrences, 0.5) as median_occ,
  AVG(n_occurrences) as mean_occ,
  MAX(n_occurrences) as max_occ,
  COUNT(*) as total_pixels,
  COUNTIF(n_occurrences = 1) as single_occurrence_pixels,
  COUNTIF(n_occurrences > 10) as heavy_sampled_pixels,
  COUNTIF(n_occurrences > 100) as extreme_sampled_pixels
FROM `treekipedia-479918.species_data.alphaearth_embeddings_v4`
```

### Analyze Sampling Bias Per Species

```sql
WITH species_stats AS (
  SELECT
    taxon_id,
    COUNT(*) as n_pixels,
    SUM(n_occurrences) as total_occurrences,
    AVG(n_occurrences) as mean_occ_per_pixel,
    STDDEV(n_occurrences) as stddev_occ,
    MAX(n_occurrences) as max_occ_in_pixel
  FROM `treekipedia-479918.species_data.alphaearth_embeddings_v4`
  WHERE taxon_id IS NOT NULL
  GROUP BY taxon_id
)
SELECT
  taxon_id,
  n_pixels,
  total_occurrences,
  mean_occ_per_pixel,
  stddev_occ,
  max_occ_in_pixel,
  -- Coefficient of variation (measure of sampling bias)
  stddev_occ / mean_occ_per_pixel as cv_occ
FROM species_stats
WHERE n_pixels >= 10
ORDER BY cv_occ DESC  -- Species with highest sampling bias
LIMIT 100;
```

### Test Weighted vs. Unweighted Clustering

```sql
-- Compare centroids from weighted vs. unweighted runs
WITH weighted AS (
  SELECT taxon_id, cluster_id, representative_lat, representative_lon
  FROM species_habitat_centroids_weighted
),
unweighted AS (
  SELECT taxon_id, cluster_id, representative_lat, representative_lon
  FROM species_habitat_centroids_unweighted
)
SELECT
  w.taxon_id,
  w.cluster_id,
  -- Haversine distance between weighted and unweighted centroids
  ST_DISTANCE(
    ST_GEOGPOINT(w.representative_lon, w.representative_lat),
    ST_GEOGPOINT(u.representative_lon, u.representative_lat)
  ) / 1000 as distance_km
FROM weighted w
JOIN unweighted u ON w.taxon_id = u.taxon_id AND w.cluster_id = u.cluster_id
ORDER BY distance_km DESC;
```

---

**END OF REPORT**
