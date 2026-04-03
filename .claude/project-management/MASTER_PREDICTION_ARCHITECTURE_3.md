# Treekipedia Species Intelligence System
## Master Prediction Architecture v3.0

**Version**: 3.0
**Date**: February 11, 2026
**Status**: Architecture specification + implementation roadmap
**Supersedes**: MASTER_PREDICTION_ARCHITECTURE_2.md (v2.0, January 22, 2026)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Theoretical Foundation](#2-theoretical-foundation)
3. [Data Architecture](#3-data-architecture)
4. [Prediction Pipeline v3: k-NN + Multi-Signal Scoring](#4-prediction-pipeline-v3)
5. [The Model Progression: k-NN → GMM → Neural Head](#5-model-progression)
6. [Forest Stability Index (FSI)](#6-forest-stability-index)
7. [Disturbance-Aware Prediction](#7-disturbance-aware-prediction)
8. [Species Expansion Pipeline](#8-species-expansion-pipeline)
9. [SAFE-B Recommendation Framework v2](#9-safe-b-recommendation-framework-v2)
10. [GEE Data Stack](#10-gee-data-stack)
11. [Uncertainty Quantification](#11-uncertainty-quantification)
12. [Validation Framework](#12-validation-framework)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Competitive Analysis](#14-competitive-analysis)
15. [Appendices](#15-appendices)

---

## 1. Executive Summary

### 1.1 Mission

Treekipedia answers two questions at any point on Earth:

| System | Question | User |
|--------|----------|------|
| **Predictor** | "What tree species CAN survive at this location?" | Scientists, ecologists, land managers |
| **Recommender** | "What tree species SHOULD I plant here for my goals?" | Restoration practitioners, agroforesters, planners |

### 1.2 Architecture Evolution

| Version | Approach | Limitation |
|---------|----------|------------|
| **v1** (Oct 2025) | Single-centroid cosine similarity | One point per species, no context |
| **v2** (Jan 2026) | Multi-centroid + 5-signal scoring | Centroid averaging destroys distribution shape; common species bias |
| **v3** (Feb 2026) | **k-NN on individual occurrences + IDF weighting + Forest Stability Index + disturbance-aware scoring** | Current architecture |
| **v4** (planned) | Gaussian Mixture Models per species | Requires >100 occurrences per species for reliable covariance |
| **v5** (planned) | Neural prediction head (SINR-style) | Requires gap-filling to 60K+ species for effective training |

### 1.3 Key Architectural Decisions (v3)

1. **Match against individual occurrence embeddings, not averaged centroids.** Centroids destroy multi-modal habitat distributions. A species in both lowland rainforest and cloud forest gets a centroid matching neither. k-NN against individual occurrences preserves the full distribution shape and naturally handles multi-modal habitats.

2. **Apply inverse document frequency (IDF) weighting to correct common species bias.** A rare species with 15 well-placed occurrences should outscore a common species with 50,000 loosely-matching occurrences. IDF weight = `1/log(1 + total_occurrences)`.

3. **Compute a Forest Stability Index (FSI) at every query location.** Combines 6 signals (years since disturbance, canopy height, biomass, NDVI trend, fragmentation, primary forest classification) into a single 0-100 score that modulates native/introduced/invasive species weighting.

4. **Use disturbance context to differentiate prediction from recommendation.** For a disturbed pixel, the Predictor answers "what matches NOW" using current embeddings. The Recommender also samples nearby undisturbed reference pixels to answer "what SHOULD grow here after restoration."

5. **Build toward a neural prediction head.** The k-NN occurrence table IS the training dataset for a SINR-style neural network. Every improvement in data coverage directly improves the eventual model. k-NN ships immediately; the neural head trains on the same data later.

### 1.4 Current System State (February 11, 2026)

| Asset | Status | Detail |
|-------|--------|--------|
| **AlphaEarth v4 embeddings** | COMPLETE | 3.37M rows, 17,924 species, 277MB parquet |
| **Phase A: Rejoin gap species** | COMPLETE | +4,679 species recovered via pixel data join |
| **Phase B: Geographic re-clustering** | COMPLETE | 2,257 species re-clustered with DBSCAN → 49,640 centroids, 22,603 species |
| **Habitat centroids (pgvector)** | LIVE | 49,640 centroids, IVFFlat index (lists=320) |
| **Multi-signal predictor** | LIVE | 5-signal scoring (embedding + spatial + range + ecoregion + climate) |
| **SAFE-B recommender** | LIVE | 7 strategies, 5-component scoring |
| **Climate/Soil GEE sampling** | LIVE | WorldClim BIO (19 vars) + OpenLandMap soil (4 vars) + Koppen-Geiger |
| **k-NN occurrence table** | BUILDING | Will replace centroid-based Channel 1 |
| **Forest Stability Index** | PLANNED | 6-signal composite from GEE layers |
| **Neural prediction head** | PLANNED | SINR-style, trains on k-NN table after gap-fill |

---

## 2. Theoretical Foundation

### 2.1 Why Satellite Embeddings for Species Distribution Modeling?

Traditional Species Distribution Models (SDMs) use hand-crafted environmental variables (BioClim, soil, elevation) as predictors. These variables capture known ecological gradients but miss unmeasured factors: canopy structure, phenological timing, spectral signatures of understory composition, soil moisture proxies visible in vegetation greenness.

**Foundation model embeddings** (AlphaEarth, Clay, Prithvi) learn a compressed representation of the complete satellite signal — all spectral bands across all available dates — into a fixed-dimensional vector. This captures:

- **Structural habitat features**: canopy density, height heterogeneity, gap fraction
- **Phenological patterns**: deciduousness, flowering timing, drought response
- **Edaphic proxies**: vegetation vigor as a function of soil quality
- **Microclimate indicators**: aspect-driven productivity differences, frost hollows
- **Land use legacies**: plantation regularity vs natural forest complexity

AlphaEarth specifically provides 64-dimensional embeddings at 10m resolution from Sentinel-2 annual composites (2017-2024). Each embedding is **deterministic per pixel-year**: the same pixel in the same year always produces the same 64-D vector, regardless of which species occurs there. The embedding describes the **habitat**, not the species.

### 2.2 The Fundamental Insight: Embeddings as Habitat Fingerprints

Consider a query location at Auckland, New Zealand. The AlphaEarth embedding at that pixel encodes the satellite-observable properties of that specific 10m×10m patch: its spectral signature, seasonal phenology, and structural characteristics.

**The question becomes**: which species have historically been observed at locations with similar satellite fingerprints?

This framing has critical implications:

1. **Multi-modality is expected.** A species can occupy habitats with very different fingerprints (lowland vs montane, natural vs plantation). The matching algorithm must handle multi-modal distributions.

2. **Similarity ≠ identity.** Two species at the same pixel share the exact same embedding. Differentiation requires additional signals: native range, ecoregion, climate envelope, disturbance history.

3. **Absence of evidence ≠ evidence of absence.** A location may perfectly match a species' habitat fingerprint, but the species may not be present due to dispersal limitation, competition, or historical extirpation.

4. **Disturbance changes the fingerprint.** A recently deforested pixel has a very different embedding from the same pixel before deforestation. For restoration, we may want to match against the pre-disturbance fingerprint.

### 2.3 Literature Context

The field of deep SDM has converged on several key findings (2023-2026):

| Finding | Key Papers | Implication for Treekipedia |
|---------|-----------|---------------------------|
| Learned prediction heads outperform distance-based matching | Sat-SINR (Dollinger et al. 2024), GeoLifeCLEF 2024 (Joly et al.) | Our roadmap: k-NN → GMM → neural head |
| Data quantity matters more than model sophistication at moderate scale | SINR (Cole et al. 2023), FS-SINR (Lange et al. 2025) | Gap-filling the remaining 38K species is highest priority |
| Inverse-frequency weighting corrects observation bias | Baker et al. 2022, Moudrý et al. 2024 | Apply IDF to k-NN vote aggregation |
| Taxonomic borrowing enables few-shot prediction | LE-SINR (Hamilton et al. NeurIPS 2024) | Rare species can borrow from well-sampled congeners |
| Land disturbance is the strongest predictor of invasion risk | Lazaro-Lobo et al. 2021, Seebens et al. Nature 2024 | FSI modulates native/introduced weighting |
| Normalizing flows capture complex niche shapes | NicheFlow (Dinnage 2024) | Future: replace GMM with normalizing flows for niche modeling |

### 2.4 Why k-NN First, Not Directly to Neural?

| Criterion | k-NN | Neural Head |
|-----------|------|------------|
| Training required | None | 30-60 min on GPU |
| Ships immediately | Yes | No |
| Handles new species | Instantly (add rows) | Requires retraining or fine-tuning |
| Data efficiency | Works with 1 occurrence | Needs >20 per species for reliable signal |
| Interpretability | "These 3 occurrence points match" | Opaque probabilities |
| Same data asset | Yes — the occurrence table | Yes — trains on the same table |
| Accuracy ceiling | Lower | Higher (learns non-linear relationships) |

**k-NN is the foundation, not technical debt.** The occurrence embedding table IS the training data for everything more advanced. Every row we add improves both k-NN immediately and the eventual neural model.

---

## 3. Data Architecture

### 3.1 Primary Tables

```sql
-- EXISTING: Species habitat centroids (v2 system, retained as pre-filter)
species_habitat_centroids (
    taxon_id, cluster_id, centroid_vector vector(64),
    occurrence_count, mean_elevation, elevation_std,
    mean_treecover2000, forest_loss_fraction,
    representative_lat, representative_lon
)
-- 49,640 rows, 22,603 species, IVFFlat index (lists=320)

-- NEW: Individual occurrence embeddings (v3 system, primary matching)
species_occurrence_embeddings (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    embedding vector(64) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    emb_year SMALLINT,                    -- AlphaEarth mosaic year
    elevation SMALLINT,                   -- SRTM meters
    treecover2000 SMALLINT,              -- Hansen baseline %
    loss BOOLEAN DEFAULT FALSE,           -- Hansen forest loss
    lossyear SMALLINT,                   -- Year of loss (2001-2024)
    density_weight FLOAT DEFAULT 1.0,    -- Inverse spatial density
    data_regime SMALLINT DEFAULT 1       -- 1=direct v4, 2=rejoin, 3=regime2
);
-- Target: ~3M rows initially (v4 + Phase A), growing to ~10M after Phase C
-- HNSW index for fast approximate nearest neighbor search

CREATE INDEX idx_occ_emb_hnsw
ON species_occurrence_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);

CREATE INDEX idx_occ_taxon ON species_occurrence_embeddings (taxon_id);
CREATE INDEX idx_occ_location ON species_occurrence_embeddings (latitude, longitude);

-- NEW: Species occurrence statistics (for IDF weighting)
species_occurrence_stats (
    taxon_id VARCHAR(50) PRIMARY KEY,
    total_occurrences INTEGER,           -- Total rows in occurrence table
    total_unique_pixels INTEGER,         -- Deduplicated locations
    embedding_coverage_pct FLOAT,        -- % of occurrences with embeddings
    geographic_extent_km FLOAT,          -- Max pairwise distance
    n_geographic_regions INTEGER,        -- DBSCAN cluster count
    idf_weight FLOAT,                    -- Pre-computed 1/log(1+total_occurrences)
    data_quality_score FLOAT             -- Composite quality metric (0-1)
)

-- NEW: Forest Stability Index cache (computed at extraction time)
pixel_forest_stability (
    lat_i INTEGER,                       -- latitude * 10000, rounded
    lon_i INTEGER,                       -- longitude * 10000, rounded
    fsi_score FLOAT,                     -- Forest Stability Index 0-100
    years_since_disturbance SMALLINT,    -- From LandTrendr/CCDC
    canopy_height_m FLOAT,              -- GEDI or Meta canopy height
    biomass_mgha FLOAT,                 -- ORNL AGBD
    ndvi_trend FLOAT,                   -- 20+ year NDVI slope
    primary_forest BOOLEAN,             -- JRC GFC2020 subtypes
    jrc_tmf_status SMALLINT,            -- JRC TMF transition class
    distance_to_edge_m FLOAT,           -- Hansen fastDistanceTransform
    computed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (lat_i, lon_i)
)
```

### 3.2 Data Flow Architecture

```
                         ┌─────────────────────────────────┐
                         │     GBIF Occurrences (96.5M)     │
                         └──────────────┬──────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
              ┌─────▼─────┐     ┌──────▼──────┐    ┌──────▼──────┐
              │  V4 Direct │     │  Phase A    │    │  Phase C    │
              │  (17,924)  │     │  Rejoin     │    │  Regime 2   │
              │  2017-2024 │     │  (4,679)    │    │  (~36,500)  │
              │  3.37M rows│     │  9,144 rows │    │  ~1M rows   │
              └─────┬──────┘     └──────┬──────┘    └──────┬──────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                         ┌──────────────▼──────────────────┐
                         │  species_occurrence_embeddings   │
                         │  (individual points, HNSW index) │
                         │  ~3M rows → ~10M after Phase C   │
                         └──────────────┬──────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
     ┌────────▼────────┐    ┌──────────▼──────────┐   ┌─────────▼─────────┐
     │  k-NN Matching  │    │  GMM Fitting        │   │  Neural Head      │
     │  (immediate)    │    │  (per species,       │   │  (train on full   │
     │  HNSW top-500   │    │   requires >100 pts) │   │   dataset, SINR)  │
     │  Vote + IDF     │    │  Diagonal covariance │   │  64-D → 60K probs │
     └────────┬────────┘    └──────────┬──────────┘   └─────────┬─────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                         ┌──────────────▼──────────────────┐
                         │   Multi-Signal Scoring Engine    │
                         │   + Forest Stability Index       │
                         │   + Disturbance-Aware Weighting  │
                         │   + Climate Envelope Check       │
                         │   + Native/Introduced Modulation │
                         └─────────────────────────────────┘
```

### 3.3 Current Database State (February 11, 2026)

| Table | Rows | Species | Index | Notes |
|-------|------|---------|-------|-------|
| `species_habitat_centroids` | 49,640 | 22,603 | IVFFlat (lists=320) | Phase A (+6,461) + Phase B re-clustered (2,257 species) |
| `species` | 67,743 | — | B-tree on taxon_id | 50,797 species + 16,946 subspecies |
| `geohash_species_tiles` | 5,786,835 | 48,129 | GiST on geometry | L7 precision (~150m) |
| `ecoregions` | 847 | — | GiST on geometry | WWF polygons |
| `insights` | ~200 | 6 species | B-tree on taxon_id | Atomic research insights |
| `species_occurrence_embeddings` | — | — | — | **TO BUILD** (this architecture) |

---

## 4. Prediction Pipeline v3: k-NN + Multi-Signal Scoring

### 4.1 Query Flow (Point Prediction)

```
User clicks (lat, lon) on map
    │
    ├── [1] GEE Sampling (Python service, port 5002)
    │   Single batched ee.Image.cat().sample() call:
    │   ├── AlphaEarth 64-D embedding (multi-year fallback: 2023→2017)
    │   ├── SRTM elevation
    │   ├── Hansen GFC (treecover2000, loss, lossyear, gain)
    │   ├── WorldClim BIO (19 variables)
    │   ├── OpenLandMap soil (pH, clay%, sand%, organic C)
    │   ├── Dynamic World (current land cover class)
    │   ├── JRC GFC2020 subtypes (primary forest flag)
    │   ├── JRC TMF status (tropical sites: degradation/deforestation year)
    │   ├── GEDI canopy height (if available at 1km)
    │   ├── ORNL biomass carbon density
    │   └── CSP Human Modification Index
    │
    ├── [2] Forest Stability Index computation
    │   FSI = f(years_since_disturbance, canopy_height, biomass,
    │           ndvi_trend, primary_forest, distance_to_edge)
    │   → 0-100 score: 0 = heavily disturbed, 100 = intact old growth
    │
    ├── [3] Three-Channel Candidate Discovery
    │   ├── Channel 1 (k-NN): HNSW search → top-500 nearest occurrences
    │   │   Vote by species with IDF weighting
    │   │   → Top ~200 species candidates with embedding scores
    │   │
    │   ├── Channel 2 (Spatial): geohash tiles within 50km
    │   │   → Species with nearby occurrence records
    │   │
    │   └── Channel 3 (Strategy): WCVP native range + ecoregion match
    │       → Species expected in this biogeographic region
    │
    ├── [4] Multi-Signal Scoring (per candidate species)
    │   ├── Signal 1: Embedding match (from k-NN vote score)
    │   ├── Signal 2: Spatial proximity (occurrence density near query)
    │   ├── Signal 3: Range confirmation (WCVP native/introduced status)
    │   ├── Signal 4: Ecoregion co-occurrence
    │   ├── Signal 5: Climate envelope (elevation + precip + temp + Koppen)
    │   ├── Signal 6: Soil compatibility (pH + texture match) [NEW]
    │   └── Signal 7: Disturbance congruence (FSI-based) [NEW]
    │
    ├── [5] Disturbance-Aware Modulation
    │   ├── if FSI > 80: boost native, reduce introduced
    │   ├── if FSI 40-80: moderate modulation
    │   ├── if FSI < 40: boost pioneer/introduced for PREDICT
    │   │               sample reference pixels for RECOMMEND
    │   └── Adjust confidence based on FSI agreement with species ecology
    │
    └── [6] Return ranked species with:
        ├── Composite score (0-1)
        ├── Per-signal breakdown (7 signals)
        ├── Confidence interval
        ├── Native/introduced status
        ├── FSI context
        ├── Data quality indicators (occurrence count, centroid reliability)
        └── Strategy alignment (for recommender)
```

### 4.2 k-NN Matching Algorithm (Channel 1 v3)

```sql
-- Stage 1: HNSW approximate nearest neighbor search
-- Find 500 nearest occurrence embeddings to query location
WITH nearest AS (
    SELECT
        oe.taxon_id,
        1 - (oe.embedding <=> $1::vector) AS similarity,
        oe.density_weight,
        oe.latitude,
        oe.longitude,
        oe.elevation,
        oe.treecover2000,
        oe.loss,
        oe.data_regime
    FROM species_occurrence_embeddings oe
    ORDER BY oe.embedding <=> $1::vector
    LIMIT 500
),

-- Stage 2: Aggregate by species with IDF weighting
species_scores AS (
    SELECT
        n.taxon_id,
        COUNT(*) AS hit_count,
        MAX(n.similarity) AS best_similarity,
        AVG(n.similarity) AS mean_similarity,
        -- Weighted vote: sum of (similarity × density_weight × IDF)
        SUM(n.similarity * n.density_weight) * os.idf_weight AS weighted_score,
        AVG(n.elevation) AS avg_matched_elevation,
        AVG(n.treecover2000) AS avg_matched_treecover,
        os.total_occurrences,
        os.data_quality_score
    FROM nearest n
    JOIN species_occurrence_stats os ON os.taxon_id = n.taxon_id
    GROUP BY n.taxon_id, os.idf_weight, os.total_occurrences, os.data_quality_score
)

SELECT *
FROM species_scores
ORDER BY weighted_score DESC
LIMIT 200;
```

### 4.3 IDF Weighting: Correcting Common Species Bias

The inverse document frequency (IDF) principle from information retrieval, adapted for ecology:

```
IDF_weight(species) = 1 / log(1 + total_occurrences)
```

| Species | Occurrences | IDF Weight | Effect |
|---------|-------------|------------|--------|
| Quercus robur | 50,000 | 0.092 | 10× penalty vs rare species |
| Pinus radiata | 2,808 | 0.126 | Moderate penalty |
| Rare endemic (50 occ) | 50 | 0.255 | 2.8× boost vs Q. robur |
| Very rare (10 occ) | 10 | 0.417 | 4.5× boost vs Q. robur |

**Ecological rationale**: Common species dominate occurrence databases because they're frequently observed, not because they're more suitable at a given location. IDF corrects this by asking: "given that this species was found at a matching location, how informative is that match?"

A rare species with 3 out of 10 total occurrences matching is far more informative than a common species with 3 out of 50,000 matching.

### 4.4 Centroid Retention (Dual System)

Centroids are retained as a **fast pre-filter and fallback**:

```
┌──────────────────────────────────────────────────────────────┐
│                  DUAL-SYSTEM ARCHITECTURE                      │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  PRIMARY (v3): k-NN on individual occurrences                 │
│  ├── HNSW search: top-500 nearest points                     │
│  ├── Vote + IDF: aggregate by species                        │
│  ├── Preserves multi-modal distributions                     │
│  └── Handles rare species correctly                          │
│                                                                │
│  SECONDARY (v2, retained): Centroid pre-filter               │
│  ├── IVFFlat search: top-200 nearest centroids               │
│  ├── Used as candidate set expansion                         │
│  ├── Used when HNSW index is building/unavailable            │
│  └── Provides cluster-level metadata (elevation, treecover)  │
│                                                                │
│  MERGE: Union of both candidate sets → multi-signal scoring  │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### 4.5 Seven-Signal Scoring

| Signal | Weight Range | Source | New in v3? |
|--------|-------------|--------|-----------|
| 1. Embedding match | 15-50% | k-NN vote score | Updated (was centroid similarity) |
| 2. Spatial proximity | 22-45% | Geohash tile density within 50km | Unchanged |
| 3. Range confirmation | 10-15% | WCVP native/introduced status | Unchanged |
| 4. Ecoregion match | 8-15% | WWF ecoregion co-occurrence | Unchanged |
| 5. Climate envelope | 8-15% | Elevation + precipitation + temperature + Koppen | Unchanged |
| 6. **Soil compatibility** | 5-10% | pH match + texture match | **NEW** (was sampled but unused) |
| 7. **Disturbance congruence** | 5-15% | FSI-based native/introduced modulation | **NEW** |

**Dynamic weight selection** (context-dependent):

```python
def select_weights(embedding_score, spatial_score, fsi_score):
    if embedding_score >= 0.65:
        # Strong embedding match — trust it
        return {emb: 0.40, spatial: 0.18, range: 0.12, eco: 0.10,
                climate: 0.08, soil: 0.05, disturbance: 0.07}
    elif spatial_score >= 0.60:
        # Strong spatial presence — weight spatial heavily
        return {emb: 0.12, spatial: 0.38, range: 0.12, eco: 0.12,
                climate: 0.10, soil: 0.06, disturbance: 0.10}
    elif fsi_score < 40:
        # Disturbed site — disturbance signal matters more
        return {emb: 0.25, spatial: 0.20, range: 0.10, eco: 0.10,
                climate: 0.10, soil: 0.05, disturbance: 0.20}
    else:
        # Balanced — no dominant signal
        return {emb: 0.30, spatial: 0.22, range: 0.12, eco: 0.12,
                climate: 0.10, soil: 0.06, disturbance: 0.08}
```

---

## 5. The Model Progression: k-NN → GMM → Neural Head

### 5.1 Overview

The k-NN occurrence table is simultaneously:
- The **production serving system** (immediate, no training)
- The **training dataset** for GMMs and neural heads
- The **data quality tracker** (occurrence count, coverage metrics)

```
┌────────────────────────────────────────────────────────────┐
│                   MODEL PROGRESSION                          │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: k-NN (CURRENT)                                   │
│  ├── Accuracy: Baseline                                     │
│  ├── Training: None (store embeddings, build HNSW index)   │
│  ├── Query: HNSW search + weighted vote + IDF              │
│  ├── New species: Add rows → immediately available         │
│  └── Ships: Immediately                                    │
│                                                              │
│  PHASE 2: GMM (requires >100 occurrences/species)          │
│  ├── Accuracy: ~1.5-2× k-NN                               │
│  ├── Training: sklearn GMM fit per species (~1 hour total) │
│  ├── Query: Evaluate log-likelihood per species (fast)     │
│  ├── Storage: Add variance_vector + mixing_weight to       │
│  │            existing centroid table                       │
│  ├── Interpretability: Full niche shape per cluster        │
│  └── Ships: After Phase C gap-fill for dense species       │
│                                                              │
│  PHASE 3: Neural Prediction Head (SINR-style)              │
│  ├── Accuracy: ~2-4× k-NN                                 │
│  ├── Training: PyTorch, 30-60 min on GPU, 10 epochs       │
│  │   Architecture: 64-D → 256 → [ResBlock]×4 → 60K spp   │
│  ├── Query: One forward pass → all species probabilities   │
│  ├── Calibrated: Outputs P(species|location), not distance │
│  ├── Few-shot: Shared feature extractor helps rare species │
│  └── Ships: After gap-fill to 60K species                  │
│                                                              │
│  PHASE 4: Multimodal Neural (Sat-SINR + NicheFlow)        │
│  ├── Input: 64-D embedding + lat/lon + climate + soil + FSI│
│  ├── Accuracy: State-of-the-art (~5× k-NN)               │
│  ├── Training: Hours on GPU                                │
│  └── Ships: Research phase, 2026 H2                        │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

### 5.2 GMM Extension (Phase 2)

Extend the existing centroid table with distribution parameters:

```sql
ALTER TABLE species_habitat_centroids
ADD COLUMN variance_vector vector(64),     -- Diagonal of covariance matrix
ADD COLUMN mixing_weight FLOAT DEFAULT 1.0; -- GMM component weight (pi_k)
```

At query time, compute Mahalanobis-like log-likelihood instead of cosine similarity:

```python
def gmm_log_likelihood(query, centroids, variances, weights):
    """
    For each species, compute P(query | species) using diagonal GMM.
    More principled than cosine similarity: accounts for spread of each cluster.
    A tight cluster (low variance) gives high confidence to nearby matches.
    A broad cluster (high variance) gives moderate confidence across a wide range.
    """
    log_probs = []
    for mu, sigma_diag, pi_k in zip(centroids, variances, weights):
        diff = query - mu
        # Mahalanobis distance with diagonal covariance
        log_prob = -0.5 * np.sum(diff**2 / sigma_diag + np.log(sigma_diag))
        log_prob += np.log(pi_k)
        log_probs.append(log_prob)
    return scipy.special.logsumexp(log_probs)  # Mixture likelihood
```

**Requirement**: Reliable GMM fitting requires >64 occurrences per cluster (one per embedding dimension). With diagonal covariance, this relaxes somewhat, but species with <30 total occurrences should stay on k-NN only.

### 5.3 Neural Prediction Head (Phase 3)

Architecture following SINR (Cole et al. 2023, ICML) and Sat-SINR (Dollinger et al. 2024):

```python
class TreekipediaPredictionHead(nn.Module):
    """
    Input: 64-D AlphaEarth embedding (+ optional: lat/lon encoding, climate, soil, FSI)
    Output: Per-species presence probability for all N_species
    
    Architecture:
    - 4-layer residual fully-connected network
    - Each ResBlock: Linear → LayerNorm → ReLU → Dropout → Linear → Add
    - Final layer: Linear → Sigmoid (multi-label, not softmax)
    
    Training:
    - Loss: Assumed-Negative (AN) loss (presence-only data)
    - Pseudo-absences: Random background sampling
    - Epochs: 10 (converges fast with 3M+ samples)
    - Batch size: 2048
    - Optimizer: AdamW, lr=5e-4, weight_decay=1e-4
    
    Expected performance (based on SINR benchmarks):
    - 60K species, 10M occurrences: top-30 accuracy ~40-60%
    - Calibrated probabilities (not similarity scores)
    - All species predicted in single forward pass (~5ms on GPU)
    """
    def __init__(self, input_dim=64, hidden_dim=256, n_species=60000, n_blocks=4):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.blocks = nn.ModuleList([
            ResBlock(hidden_dim) for _ in range(n_blocks)
        ])
        self.output = nn.Linear(hidden_dim, n_species)
    
    def forward(self, x):
        x = F.relu(self.input_proj(x))
        for block in self.blocks:
            x = block(x)
        return torch.sigmoid(self.output(x))
```

**Training data**: Directly from `species_occurrence_embeddings` table:
```python
# Training sample: (embedding_64d, species_id)
# Exactly what our k-NN table stores
X = embeddings_table['embedding'].values  # (N, 64)
y = embeddings_table['taxon_id'].values   # (N,) → one-hot encode to (N, 60000)
```

**Framework**: [Malpolon](https://github.com/plantnet/malpolon) (Pl@ntNet's deep SDM framework, PyTorch Lightning + Hydra config, GeoLifeCLEF benchmarks included).

---

## 6. Forest Stability Index (FSI)

### 6.1 Purpose

The Forest Stability Index answers: "How ecologically intact and temporally stable is this location?" This single composite score (0-100) modulates every prediction by providing ecological context that satellite embeddings alone cannot capture.

A pixel can have a high AlphaEarth match to a native species' habitat fingerprint but be a 5-year-old regrowth forest, a guava-invaded degraded remnant, or a recently cleared field. The FSI distinguishes these cases.

### 6.2 Component Signals

| Component | Weight | Source | Resolution | Temporal |
|-----------|--------|--------|------------|----------|
| **Years since last disturbance** | 0.25 | LandTrendr on Landsat 1985-present OR Google CCDC 1999-2019 | 30m | 40-year lookback |
| **Primary forest classification** | 0.20 | JRC GFC2020 subtypes V1 | 10m | Static (2020) |
| **Canopy height percentile** | 0.15 | GEDI gridded 1km OR Meta/ETH 10m canopy height | 10m-1km | 2020-2024 |
| **Biomass density percentile** | 0.15 | NASA ORNL biomass carbon density | 300m | ~2010 |
| **NDVI trend stability** | 0.15 | Landsat NDVI linear trend 1985-present | 30m | 40-year trend |
| **Distance to forest edge** | 0.10 | Hansen treecover2000 fastDistanceTransform | 30m | Static (2000) |

### 6.3 Computation

```python
def compute_forest_stability_index(pixel_data):
    """
    Compute FSI (0-100) from multi-source environmental data.
    
    Higher FSI = more intact, stable, undisturbed forest.
    Lower FSI = disturbed, degraded, or recently changed land.
    """
    
    # 1. Years since disturbance (0-1)
    #    Source: LandTrendr greatest_disturbance_year or CCDC tBreak
    #    No detected disturbance in 40-year record → 1.0
    ysd = pixel_data.get('years_since_disturbance')
    if ysd is None or ysd >= 40:
        dist_score = 1.0
    else:
        dist_score = min(1.0, ysd / 40.0)
    
    # 2. Primary forest flag (0 or 1)
    #    Source: JRC GFC2020 subtypes (value=10 → primary)
    primary = 1.0 if pixel_data.get('jrc_primary_forest') else 0.0
    
    # 3. Canopy height percentile (0-1)
    #    Relative to biome maximum (tropical=50m, temperate=35m, boreal=25m)
    height = pixel_data.get('canopy_height_m', 0)
    biome_max = pixel_data.get('biome_max_canopy_height', 40)
    height_score = min(1.0, height / biome_max)
    
    # 4. Biomass percentile (0-1)
    #    Relative to biome maximum
    biomass = pixel_data.get('biomass_mgha', 0)
    biome_max_biomass = pixel_data.get('biome_max_biomass', 300)
    biomass_score = min(1.0, biomass / biome_max_biomass)
    
    # 5. NDVI trend stability (0-1)
    #    Stable or increasing → 1.0, declining → lower
    ndvi_slope = pixel_data.get('ndvi_trend', 0)
    ndvi_score = min(1.0, max(0.0, (ndvi_slope + 0.01) / 0.02))
    
    # 6. Distance to forest edge (0-1)
    #    Core interior forest (>5km from edge) → 1.0
    dist_to_edge = pixel_data.get('distance_to_edge_m', 0)
    edge_score = min(1.0, dist_to_edge / 5000.0)
    
    # Weighted composite
    fsi = (
        0.25 * dist_score +
        0.20 * primary +
        0.15 * height_score +
        0.15 * biomass_score +
        0.15 * ndvi_score +
        0.10 * edge_score
    ) * 100
    
    return round(fsi, 1)
```

### 6.4 FSI Classification

| FSI Range | Classification | Ecological Interpretation | Prediction Implication |
|-----------|---------------|--------------------------|----------------------|
| **80-100** | Intact / Old Growth | Primary or mature secondary forest, no detected disturbance, high biomass, interior habitat | Strongly boost native species; reduce introduced/cultivated weight; high confidence in habitat match |
| **60-80** | Stable Secondary | Long-established secondary forest or intact but fragmented; moderate canopy and biomass | Moderate native boost; consider both native and well-adapted introduced |
| **40-60** | Recovering / Modified | Post-disturbance regrowth, selective logging recovery, or edge-affected forest | Equal weight to native and introduced; boost mid-successional species |
| **20-40** | Recently Disturbed | Active regeneration, recent clearing, plantation establishment | For PREDICT: match current state; for RECOMMEND: sample reference pixels; boost pioneer species |
| **0-20** | Heavily Modified | Agricultural land, urban, cleared, or severely degraded | For PREDICT: current land cover; for RECOMMEND: restoration potential assessment; pioneer/N-fixer species |

### 6.5 Tropical Forest History (JRC TMF Integration)

For tropical moist forests, the JRC Tropical Moist Forests dataset provides 34 years of annual forest state (1990-2024), far more detailed than Hansen's binary loss:

```
JRC TMF Annual Changes classes:
  1 = Undisturbed Tropical Moist Forest (never degraded 1990-present)
  2 = Degraded TMF (selective logging, fire, but canopy persists)
  3 = Deforested land
  4 = Forest regrowth
  5 = Permanent/seasonal water
  6 = Other land cover
```

**For Kakamega Forest (Kenya) and similar cases**: The `DegradationYear` layer detects when forest blocks experienced degradation events — including invasive species proliferation that alters canopy spectral properties — even when canopy closure is maintained. This addresses the guava invasion problem: areas that remain "forested" in Hansen but show degradation in JRC TMF can be flagged as FSI-reduced.

### 6.6 Pre-Satellite Forest History Inference

Satellite data only extends back ~40 years (Landsat 1985). For forests that may have regrown in the last 100-200 years:

**Approach 1: "No disturbance detected = minimum age 40+"**
If LandTrendr finds zero breakpoints in 40 years of Landsat data, AND canopy height is >25m, AND biomass is in the top quartile for the biome, the forest is likely >80 years old. This is the strongest satellite-based inference.

**Approach 2: HILDA+ historical land use (1960-2019)**
HILDA+ provides global land use reconstruction at 1km resolution back to 1960, using historical maps, census data, and remote sensing. A pixel that was forested in 1960 AND shows no disturbance in 40 years of Landsat → likely >100 years old. A pixel that was agricultural in 1960 but forested now → maximum 66 years old secondary growth.

**Approach 3: GEDI Foliage Height Diversity (FHD)**
Old-growth forests have complex multi-layered canopies with high foliage height diversity. Even-aged secondary regrowth has low FHD regardless of total height. GEDI's FHD metric at 1km is the best single indicator for distinguishing true old growth from tall secondary forest.

**Approach 4: Country-specific datasets**
- **Canada**: `CANADA/NFIS/NTEMS/CA_FOREST_AGE` — direct forest age at 30m
- **Brazil**: MapBiomas `projects/mapbiomas-public/assets/brazil/lulc/v1` — annual LULC 1985-2024
- **US**: USFS LCMS `USFS/GTAC/LCMS/v2024-10` — annual change 1985-2024

---

## 7. Disturbance-Aware Prediction

### 7.1 The Core Problem

A recently deforested pixel in the Amazon has a very different AlphaEarth embedding from the same pixel before deforestation. The Predictor and Recommender need to handle this differently:

| System | Question at Disturbed Site | Approach |
|--------|---------------------------|----------|
| **Predictor** | "What can currently grow here?" | Use current embedding — matches pioneer species, grassland species, etc. |
| **Recommender** | "What should I plant to restore this?" | Also sample nearby undisturbed reference pixels → match restoration targets |

### 7.2 Dual-Embedding Approach for Disturbed Sites

```python
def get_query_embeddings(lat, lon, pixel_data):
    """
    At disturbed sites, generate TWO query embeddings:
    1. Current: what the pixel looks like NOW
    2. Reference: what nearby undisturbed forest looks like
    """
    current_embedding = sample_alphaearth(lat, lon, year=2023)
    
    if pixel_data['fsi_score'] < 40:
        # Disturbed site — also find reference ecosystem
        # Search within 5km for highest-FSI pixel
        reference_embedding = sample_reference_ecosystem(
            lat, lon, radius_km=5, min_fsi=60
        )
        return {
            'current': current_embedding,
            'reference': reference_embedding,
            'mode': 'disturbed'
        }
    else:
        return {
            'current': current_embedding,
            'reference': None,
            'mode': 'intact'
        }

def predict_species(query_embeddings, fsi_score):
    """
    Predictor: uses current embedding only.
    Recommender: blends current and reference.
    """
    if query_embeddings['mode'] == 'intact':
        return knn_search(query_embeddings['current'])
    else:
        # For PREDICT: current only
        predict_results = knn_search(query_embeddings['current'])
        
        # For RECOMMEND: blend 30% current + 70% reference
        if query_embeddings['reference'] is not None:
            ref_results = knn_search(query_embeddings['reference'])
            recommend_results = blend_results(
                current=predict_results, weight_current=0.3,
                reference=ref_results, weight_reference=0.7
            )
        
        return predict_results, recommend_results
```

### 7.3 Successional Stage Matching

For disturbed sites, match species' ecological roles to the site's recovery stage:

```python
SUCCESSIONAL_PREFERENCES = {
    'early_succession': {    # 0-5 years post-disturbance
        'boost': ['pioneer', 'nitrogen_fixer', 'fast_growing', 'light_demanding'],
        'penalize': ['climax', 'shade_tolerant', 'slow_growing'],
        'boost_factor': 1.3,
        'penalize_factor': 0.7
    },
    'mid_succession': {      # 5-20 years
        'boost': ['competitive', 'moderate_growth', 'canopy_forming'],
        'penalize': ['pioneer', 'obligate_shade'],
        'boost_factor': 1.2,
        'penalize_factor': 0.8
    },
    'late_succession': {     # 20-50 years
        'boost': ['shade_tolerant', 'long_lived', 'specialist'],
        'penalize': ['pioneer', 'light_demanding'],
        'boost_factor': 1.2,
        'penalize_factor': 0.8
    },
    'old_growth': {          # 50+ years
        'boost': ['climax', 'specialist', 'old_growth_indicator'],
        'penalize': ['invasive', 'pioneer'],
        'boost_factor': 1.1,
        'penalize_factor': 0.6
    }
}
```

### 7.4 Native/Introduced Confidence Differentiation

The confidence in a prediction should differ based on native status AND disturbance context:

| FSI | Native Status | Confidence Modifier | Rationale |
|-----|--------------|--------------------|-----------| 
| >80 | Native | +0.15 | High FSI + native = very likely natural presence |
| >80 | Introduced | -0.10 | Intact forest unlikely to have cultivated species |
| >80 | Invasive | -0.20 | Intact but invaded = lower confidence in recommendation |
| <40 | Native | +0.05 | May struggle on disturbed land without intervention |
| <40 | Introduced | +0.10 | Introduced species often thrive on disturbed land |
| <40 | Pioneer native | +0.20 | Ecological match: pioneer on disturbed site |

---

## 8. Species Expansion Pipeline

### 8.1 Three Phases (Updated)

| Phase | Status | Species | Rows | GEE Calls | Time |
|-------|--------|---------|------|-----------|------|
| **A: Rejoin** | COMPLETE | +4,679 | +9,144 | 0 | Done |
| **B: Re-cluster** | COMPLETE | 2,257 improved | Net -1,452 centroids | 0 | Done |
| **C: Regime 2** | TO BUILD | ~36,500 | ~1M estimated | ~250 GEE tasks | Days-weeks |

### 8.2 Phase C: Regime 2 Sampling (Detailed Design)

```python
"""
Regime 2: Sample 2017 AlphaEarth at pre-2017 occurrence sites that are still forested.

Assumption: If a forest pixel shows no disturbance (Hansen loss=0) between the
observation date and 2017, the 2017 embedding approximates the habitat at the
time of observation.

Steps:
1. Load 96.5M occurrence parquet, filter to gap species (42K species not in v4)
2. Deduplicate to unique pixel locations (4dp)
3. Exclude pixels already in v4 (don't re-sample)
4. For each pixel, check Hansen GFC: treecover2000 >= 25 AND loss == 0
5. Sample AlphaEarth at year=2017
6. Piggyback: SRTM elevation + Hansen GFC + WorldClim BIO + soil + JRC TMF
7. Mark as data_regime=3 in species_occurrence_embeddings
8. Cluster and add to k-NN table

Estimated scope:
- ~1.1M occurrence points for 36,500 gap species
- After dedup to unique pixels: ~200K-500K unique locations
- After Hansen filter (undisturbed): ~150K-400K pixels
- At 2000 points per GEE batch: ~75-200 tasks
"""
```

### 8.3 Phase C Enhancement: Piggyback FSI Components

Since we're making GEE calls for Phase C anyway, piggyback the Forest Stability Index components:

```python
# Bands to sample at each pixel (nearly free when added to AlphaEarth batch)
PHASE_C_BANDS = {
    # Core (already planned)
    'AlphaEarth': 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL',  # 64 bands
    'SRTM': 'USGS/SRTMGL1_003',                            # elevation
    'Hansen': 'UMD/hansen/global_forest_change_2024_v1_12', # loss/gain/year/treecover
    
    # Climate + Soil (already in predictor)
    'WorldClim': 'WORLDCLIM/V1/BIO',                       # 19 BIO vars
    'SoilpH': 'OpenLandMap/SOL/SOL_PH-H2O_USDA-A614_M/v02',
    'SoilClay': 'OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02',
    
    # NEW: FSI components (piggyback on same GEE call)
    'JRC_ForestType': 'JRC/GFC2020_subtypes/V1',           # Primary forest flag
    'JRC_TMF': 'projects/JRC/TMF/v1_2024/TransitionMap_Subtypes',  # TMF status
    'GEDI': 'LARSE/GEDI/GRIDDEDVEG_002/V1/1KM',           # Canopy height + FHD
    'Biomass': 'NASA/ORNL/biomass_carbon_density/v1',       # AGBD
    'HumanMod': 'CSP/HM/GlobalHumanModification',          # Disturbance gradient
    'DynamicWorld': 'GOOGLE/DYNAMICWORLD/V1',               # Current land cover
}
```

---

## 9. SAFE-B Recommendation Framework v2

### 9.1 Architecture Update

The v2 SAFE-B framework incorporates FSI, disturbance-aware scoring, and the k-NN matching upgrade:

```
┌─────────────────────────────────────────────────────────────┐
│                    SAFE-B v2 SCORING                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  S (Spatial)     10-30%  Occurrence density + native status  │
│  ├── k-NN hit count (normalized)                             │
│  ├── Geohash tile count within 50km                         │
│  ├── WCVP native range confirmation                         │
│  └── IDF-weighted species relevance                         │
│                                                               │
│  A (Abiotic)     15-35%  Climate + soil + topography match  │
│  ├── Elevation percentile fit (species p10-p90)             │
│  ├── Precipitation envelope (BIO12-19)                      │
│  ├── Temperature envelope (BIO1-11)                         │
│  ├── Koppen-Geiger classification match                     │
│  ├── Soil pH compatibility                          [NEW]   │
│  ├── Soil texture compatibility                     [NEW]   │
│  └── Aridity / water stress (TerraClimate VPD)     [FUTURE]│
│                                                               │
│  F (Functional)  15-50%  Trait suitability for goals         │
│  ├── Successional stage match (FSI-derived)         [NEW]   │
│  ├── Growth rate / biomass accumulation potential            │
│  ├── Nitrogen fixation capability                           │
│  ├── Drought/flood/salt/shade tolerance                     │
│  └── Strategy-specific trait alignment                      │
│                                                               │
│  E (Ecosystem)   15-30%  Ecoregion + biome + integrity      │
│  ├── Ecoregion match (eco_id exact match)           [FIX]   │
│  ├── Biome-level match (fallback)                           │
│  ├── IUCN GET ecosystem group alignment                     │
│  └── Forest Stability Index congruence              [NEW]   │
│                                                               │
│  B (Biotic)       5-25%  Interactions + invasion risk        │
│  ├── Pollinator/disperser availability (GloBI)              │
│  ├── Pathogen/herbivore risk                                │
│  ├── Invasive species risk (FSI-modulated)          [NEW]   │
│  └── Competition intensity (species density signal)         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Strategy-Specific Weight Profiles (Updated)

| Strategy | S | A | F | E | B | FSI Influence | Key Traits |
|----------|---|---|---|---|---|--------------|------------|
| **General** | 20% | 20% | 20% | 25% | 15% | Moderate | Balanced mix |
| **Rewilding** | 15% | 15% | 10% | 30% | 30% | Strong (native-only at high FSI) | Late-successional, wildlife support, native |
| **Agroforestry** | 10% | 25% | 40% | 15% | 10% | Low (introduced OK) | Multi-use, N-fixing, food/timber |
| **Riparian** | 15% | 35% | 20% | 20% | 10% | Moderate | Flood tolerance, bank stabilization |
| **Carbon** | 10% | 20% | 50% | 15% | 5% | Moderate | Tall, long-lived, high biomass |
| **Biodiversity** | 15% | 10% | 15% | 30% | 30% | Strong (native priority) | Interaction richness, structural diversity |
| **Erosion Control** | 10% | 30% | 35% | 15% | 10% | Low (pioneers welcome) | Fast-establishing, deep roots, ground cover |

---

## 10. GEE Data Stack

### 10.1 Currently In Production

| Dataset | GEE Asset ID | Resolution | Used In |
|---------|-------------|-----------|---------|
| AlphaEarth V1 Annual | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | 10m | v4 pipeline, real-time predictor |
| Hansen GFC v1.11 | `UMD/hansen/global_forest_change_2023_v1_11` | 30m | v4 pipeline, disturbance |
| SRTM Elevation | `USGS/SRTMGL1_003` | 30m | v4 pipeline, real-time predictor |
| WorldClim V1 BIO | `WORLDCLIM/V1/BIO` | ~1km | Real-time predictor (19 bioclim vars) |
| OpenLandMap Soil pH | `OpenLandMap/SOL/SOL_PH-H2O_USDA-A614_M/v02` | 250m | Real-time predictor |
| OpenLandMap Clay% | `OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02` | 250m | Real-time predictor |
| OpenLandMap Sand% | `OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02` | 250m | Real-time predictor |
| OpenLandMap Organic C | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | 250m | Real-time predictor |

### 10.2 Adding for v3 (Forest Stability + Disturbance)

| Dataset | GEE Asset ID | Resolution | Purpose | Priority |
|---------|-------------|-----------|---------|----------|
| **JRC Global Forest Types 2020** | `JRC/GFC2020_subtypes/V1` | 10m | Primary forest flag | P0 |
| **JRC TMF Transition** | `projects/JRC/TMF/v1_2024/TransitionMap_Subtypes` | 30m | TMF degradation/deforestation history | P0 |
| **JRC TMF Annual Changes** | `projects/JRC/TMF/v1_2024/AnnualChanges` | 30m | Per-year forest state 1990-2024 | P0 |
| **JRC TMF Degradation Year** | `projects/JRC/TMF/v1_2024/DegradationYear` | 30m | When degradation first detected | P0 |
| **Google CCDC** | `GOOGLE/GLOBAL_CCDC/V1` | 30m | Change detection breakpoints 1999-2019 | P0 |
| **Google Dynamic World** | `GOOGLE/DYNAMICWORLD/V1` | 10m | Current land cover class (near-real-time) | P0 |
| **GEDI Gridded Vegetation** | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | 1km | Canopy height + Foliage Height Diversity | P1 |
| **NASA ORNL Biomass** | `NASA/ORNL/biomass_carbon_density/v1` | 300m | Aboveground biomass density | P1 |
| **CSP Human Modification** | `CSP/HM/GlobalHumanModification` | 1km | Human modification index (0-1) | P1 |
| **TerraClimate** | `IDAHO_EPSCOR/TERRACLIMATE` | 4km | Drought stress (VPD, soil moisture, AET) | P1 |
| **ESA WorldCover** | `ESA/WorldCover/v200` | 10m | Baseline land cover (2021) | P2 |
| **MODIS VCF** | `MODIS/006/MOD44B` | 250m | Tree cover change trends 2000-present | P2 |
| **MODIS GPP** | `MODIS/006/MOD17A3HGF` | 500m | Site productivity potential | P2 |
| **SBTN Natural Lands** | `WRI/SBTN/naturalLands/v1_1/2020` | 10m | Natural vs non-natural classification | P2 |

### 10.3 Temporal Analysis Algorithms (Built into GEE)

| Algorithm | Usage | What It Provides |
|-----------|-------|-----------------|
| **LandTrendr** | `ee.Algorithms.TemporalSegmentation.LandTrendr()` | Temporal segmentation of Landsat 1985-present: breakpoints, magnitude, year of greatest disturbance |
| **CCDC** | `ee.Algorithms.TemporalSegmentation.Ccdc()` | Continuous change detection with harmonic fitting: break dates, spectral coefficients |

### 10.4 Available for Country-Specific Analysis

| Dataset | GEE Asset | Coverage | Use |
|---------|-----------|----------|-----|
| USFS LCMS | `USFS/GTAC/LCMS/v2024-10` | US only | 1985-2024 annual LULC + disturbance |
| MapBiomas | `projects/mapbiomas-public/assets/brazil/lulc/v1` | Brazil | 1985-2024 annual LULC |
| Canada Forest Age | `CANADA/NFIS/NTEMS/CA_FOREST_AGE` | Canada | Direct forest age (2019) |
| GLAD Primary Forest | `UMD/GLAD/PRIMARY_HUMID_TROPICAL_FORESTS/v1` | Humid tropics | Primary forest extent |
| PLANET NICFI | `projects/planet-nicfi/assets/basemaps/africa` | Tropics (Africa) | 5m monthly basemaps |

### 10.5 Requires Upload (Not Natively on GEE)

| Dataset | Source | Resolution | Value |
|---------|--------|-----------|-------|
| **HILDA+ v2.0** | [PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.974335) | 1km | Land use history 1960-2019 (only global pre-satellite land use source) |
| **Forest Landscape Integrity Index** | Grantham et al. 2020, Zenodo | 1km | Composite forest integrity (used in JRC GFC2020) |
| **Intact Forest Landscapes** | intactforests.org | Vector | IFL 2000, 2013, 2020 extents |

---

## 11. Uncertainty Quantification

### 11.1 Sources of Uncertainty

| Source | Type | Mitigation |
|--------|------|-----------|
| **Observation bias** | Systematic | IDF weighting + density correction |
| **Centroid averaging** | Information loss | k-NN on individual occurrences (v3) |
| **Embedding noise** | Random (phenology, compositing) | Multi-year fallback, temporal averaging |
| **Absence ambiguity** | Fundamental (presence-only data) | Report confidence intervals, not point estimates |
| **Climate mismatch** | Systematic (current vs future) | Flag climate velocity risk |
| **Taxonomic confusion** | Systematic | Flag species with known misidentification rates |

### 11.2 Confidence Score Computation

```python
def compute_prediction_confidence(species_result, query_context):
    """
    Confidence = product of component confidences, each ∈ [0, 1]
    """
    components = {
        # Data quality: how reliable is the species' occurrence data?
        'data_quality': min(1.0, log10(species_result.total_occurrences) / 3),
        
        # Match quality: how strong is the embedding match?
        'match_quality': species_result.best_similarity,
        
        # Signal agreement: do multiple signals agree?
        'signal_agreement': count_agreeing_signals(species_result) / 7,
        
        # FSI congruence: does the species' ecology match the site's condition?
        'fsi_congruence': compute_fsi_congruence(species_result, query_context.fsi),
        
        # Native status: is the prediction ecologically plausible?
        'native_plausibility': native_confidence_modifier(
            species_result.native_status, query_context.fsi
        )
    }
    
    confidence = geometric_mean(components.values())
    
    return {
        'overall': confidence,
        'components': components,
        'interpretation': classify_confidence(confidence)
        # 'high' (>0.7), 'moderate' (0.4-0.7), 'low' (<0.4)
    }
```

---

## 12. Validation Framework

### 12.1 Spatial Cross-Validation

Standard random train/test splits inflate SDM accuracy because nearby observations are spatially autocorrelated. We use **spatial block cross-validation** (Roberts et al. 2017):

```python
# Divide the globe into 200km × 200km spatial blocks
# Assign blocks to 5 folds (ensuring geographic separation)
# Train on 4 folds, evaluate on held-out blocks
# Report mean ± std across folds
```

### 12.2 Metrics

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| **Top-K accuracy** | % of test locations where the true species is in top K predictions | Top-10: >50%, Top-30: >70% |
| **Mean Reciprocal Rank (MRR)** | Average 1/rank of the correct species | >0.15 |
| **AUC-ROC** (per species) | Discrimination between presence/absence | >0.8 for data-rich species |
| **True Skill Statistic (TSS)** | Sensitivity + Specificity - 1 (threshold-independent) | >0.5 |
| **Calibration** | Do predicted probabilities match observed frequencies? | Brier score < 0.1 |

### 12.3 Benchmark Species

| Species | taxon_id | Regions | Why It's a Good Test |
|---------|----------|---------|---------------------|
| *Pinus radiata* | `GymPiPiPnCx50820-00` | AU, NZ, CA, SA, EU, CO, CL | Multi-continental, native + introduced |
| *Quercus robur* | TBD | Europe, introduced globally | Very common, strong climate envelope |
| *Adansonia digitata* | TBD | Sub-Saharan Africa | Tropical, distinctive habitat |
| *Araucaria araucana* | TBD | Chile, Argentina | Narrow endemic, high conservation |
| A rare endemic (TBD) | TBD | Single region | Tests rare species handling |

---

## 13. Implementation Roadmap

### 13.1 Phase 1: k-NN Foundation (Current Sprint)

| Step | Task | Effort | Output |
|------|------|--------|--------|
| 1.1 | Create `species_occurrence_embeddings` table + HNSW index | 1 day | Schema + index |
| 1.2 | Load v4 parquet + Phase A data into occurrence table | 1 day | ~3M rows indexed |
| 1.3 | Compute `species_occurrence_stats` (IDF weights) | Hours | 22,603 species stats |
| 1.4 | Update `prediction.js` Channel 1 to use k-NN + IDF | 2 days | New matching algorithm |
| 1.5 | Wire soil signal into `/predict` scoring | Hours | Signal 6 active |
| 1.6 | Test P. radiata benchmark at Auckland | Hours | Validate improvement |

### 13.2 Phase 2: Forest Stability + Disturbance (Next Sprint)

| Step | Task | Effort | Output |
|------|------|--------|--------|
| 2.1 | Add FSI datasets to GEE service (JRC, CCDC, GEDI, biomass) | 2-3 days | Expanded /sample response |
| 2.2 | Implement FSI computation in Python service | 1 day | FSI score per query |
| 2.3 | Add disturbance-aware weighting to prediction.js | 1-2 days | Signal 7 + FSI modulation |
| 2.4 | Implement dual-embedding for disturbed sites | 1-2 days | Reference pixel sampling |
| 2.5 | Add successional stage matching | 1 day | Trait × stage alignment |
| 2.6 | Frontend: Show FSI, disturbance context in results | 1-2 days | UI updates |

### 13.3 Phase 3: Species Gap-Fill (Parallel)

| Step | Task | Effort | Output |
|------|------|--------|--------|
| 3.1 | Build `regime2_sampler.py` | 2-3 days | GEE batch script |
| 3.2 | Run Phase C (GEE batch, 200K-500K pixels) | Days-weeks | ~1M new embedding rows |
| 3.3 | Load Phase C data to k-NN table | Hours | 60K+ species coverage |
| 3.4 | Re-compute species_occurrence_stats | Hours | Updated IDF weights |

### 13.4 Phase 4: GMM Extension

| Step | Task | Effort | Output |
|------|------|--------|--------|
| 4.1 | Fit diagonal GMMs for species with >100 occurrences | Hours (compute) | ~5K species with GMM params |
| 4.2 | Add GMM scoring as optional Channel 1 refinement | 1-2 days | Niche-aware probability scoring |
| 4.3 | Store variance_vector + mixing_weight in centroid table | Hours | Schema extension |

### 13.5 Phase 5: Neural Prediction Head

| Step | Task | Effort | Output |
|------|------|--------|--------|
| 5.1 | Set up Malpolon framework with Treekipedia data | 1-2 days | Training pipeline |
| 5.2 | Train SINR-style head on full occurrence table | 30-60 min (GPU) | Trained model |
| 5.3 | Evaluate against k-NN baseline (spatial CV) | 1 day | Accuracy comparison |
| 5.4 | Deploy as batch prediction service | 1-2 days | Range map generation |
| 5.5 | Optionally replace k-NN for real-time if accuracy >> | 1 day | Model serving |

---

## 14. Competitive Analysis

### 14.1 Feature Comparison (Updated February 2026)

| Feature | Treekipedia v3 | eBird | Map of Life | iNaturalist | GeoLifeCLEF |
|---------|---------------|-------|-------------|-------------|-------------|
| **Taxon focus** | **Trees (60K+)** | Birds | All taxa | All taxa | Plants + Animals |
| **Resolution** | **10m** | 1km | 1km | Point | 10m-1km |
| **Embedding model** | **AlphaEarth 64-D** | None | None | None | SatCLIP / custom |
| **Matching method** | **k-NN + IDF + multi-signal** | GAM + RF | MaxEnt ensemble | Simple overlay | Neural head |
| **Disturbance-aware** | **FSI (6-signal composite)** | No | No | No | Partial |
| **Restoration recommendations** | **SAFE-B 7 strategies** | N/A | N/A | N/A | N/A |
| **Native status** | **99.99% WCVP** | N/A | Partial | Partial | N/A |
| **Biotic interactions** | **100% GloBI** | Partial | No | iNat observations | No |
| **Forest history** | **JRC TMF + CCDC + LandTrendr** | No | No | No | No |
| **Blockchain provenance** | **EAS attestations** | No | No | No | No |

### 14.2 Novel Contributions

1. **First system combining AlphaEarth 10m embeddings with k-NN species prediction at global scale for trees.** No published system uses AlphaEarth for species distribution modeling.

2. **First Forest Stability Index-modulated prediction system.** FSI combines 6 temporal and structural signals to differentiate old growth from secondary growth from degraded forest, directly informing native/introduced species weighting.

3. **First restoration recommender with disturbance-aware dual-embedding approach.** Sampling both current and reference ecosystem embeddings enables recommending restoration targets, not just current-state matches.

4. **Integrated model progression pipeline**: k-NN → GMM → neural head, all sharing the same data asset, with each phase improving accuracy while maintaining production serving.

---

## 15. Appendices

### 15.1 Key Citations

| Paper | Year | Relevance |
|-------|------|-----------|
| Cole et al. "Spatial Implicit Neural Representations for Global-Scale SDM" | ICML 2023 | SINR architecture — our neural head target |
| Dollinger et al. "Sat-SINR: SDM through Satellite Imagery" | ISPRS 2024 | Satellite embedding + SDM fusion |
| Hamilton et al. "Combining Observational Data and Language for SDM" | NeurIPS 2024 | Taxonomic transfer for rare species |
| Lange et al. "Few-shot Species Range Estimation" | arXiv 2025 | Meta-learning for data-poor species |
| Dinnage. "NicheFlow: Foundation Model for SDM" | bioRxiv 2024 | Normalizing flows for niche modeling |
| Joly et al. "Overview of LifeCLEF 2024" | Springer 2024 | Annual SDM benchmark and SOTA methods |
| Moudrý et al. "Sampling bias in SDM" | Ecography 2024 | Bias correction (IDF justification) |
| Baker et al. "Spatial bias interaction with SDM" | 2022 | Spatial filtering approaches |
| Lazaro-Lobo et al. "Land disturbance and invasion risk" | 2021 | Disturbance → invasive species link |
| Seebens et al. "Global invasion dynamics" | Nature 2024 | Invasion risk modeling |
| Brancalion & Holl. "Tree planting guidance" | J. Applied Ecology 2020 | Restoration best practices |
| Roberts et al. "Spatial cross-validation for SDM" | Ecography 2017 | Validation methodology |

### 15.2 Document Supersession

This document supersedes:
- MASTER_PREDICTION_ARCHITECTURE_2.md (v2.0, January 22, 2026)
- All documents previously superseded by v2.0 (see v2.0 Appendix 12.4)

New topics not in v2.0:
- k-NN on individual occurrence embeddings
- IDF weighting for common species bias correction
- Forest Stability Index (6-component composite)
- Disturbance-aware dual-embedding prediction
- Successional stage matching
- Model progression roadmap (k-NN → GMM → neural head)
- JRC TMF, CCDC, GEDI, Dynamic World integration
- Soil signal activation in prediction (was sampled but unused)
- Uncertainty quantification framework
- Spatial cross-validation methodology

### 15.3 Key Files

| File | Purpose | Status |
|------|---------|--------|
| `orchestrator/location_predictor_FIXED.py` | Python GEE service (port 5002) | v3 LIVE |
| `treekipedia/backend/routes/prediction.js` | Prediction + recommendation API (~1930 lines) | v2 LIVE, v3 upgrading |
| `treekipedia/backend/services/safeb-scorer.js` | SAFE-B scoring engine (~710 lines) | v2 LIVE |
| `orchestrator/rejoin_gap_species.py` | Phase A: rejoin gap species | COMPLETE |
| `orchestrator/recluster_expanded.py` | Phase B: geographic DBSCAN re-clustering | COMPLETE |
| `orchestrator/regime2_sampler.py` | Phase C: Regime 2 GEE batch sampling | TO BUILD |
| `orchestrator/run_clustering_v4.py` | V4 clustering pipeline | COMPLETE |
| `orchestrator/bigquery_exports/alphaearth_embeddings_v4/` | V4 parquet data (277MB) | COMPLETE |

---

**Version**: 3.0
**Author**: Claude Code (Opus 4)
**Reviewed**: February 11, 2026
**Next review**: After k-NN implementation validates accuracy improvement
