# Treekipedia SINR Species Prediction Model: Comprehensive Technical Specification

## Document Purpose

This document provides a complete technical specification of the Treekipedia species prediction system, including the data pipeline, model architecture, training process, and integration plan. It is written to enable a thorough external review and solicit feedback on potential improvements.

---

## 1. Project Goal

**Predict which tree species are present at any location on Earth, given satellite imagery and environmental features.**

The system takes a geographic coordinate (lat/lon), retrieves a 64-dimensional satellite embedding and 59 environmental variables for that location, and returns a probability-ranked list of the most likely tree species from a catalog of 43,566 species.

### 1.1 Why This Matters

Treekipedia is a global tree species knowledge platform. When a user drops a pin on the map, we need to tell them what trees likely grow there. This powers two use cases:
- **Predictor**: "What species exist at this location?" (ecological survey, land assessment)
- **Recommender**: "What species should I plant here?" (reforestation, agroforestry)

### 1.2 The Problem With the Current System

The current prediction system uses **k-nearest-neighbor (k-NN) voting** on satellite embeddings. It finds the 500 most similar satellite tiles in the database, looks at which species were observed at those tiles, and votes. This has fundamental limitations:

- **No cross-biome learning**: A P. radiata plantation in New Zealand looks similar to other NZ plantations, but the k-NN search may not surface P. radiata records from Chile or California because those pixels look different (different soil, different surrounding landscape). The model can't learn that "planted conifer rows + mild Southern Hemisphere climate = P. radiata regardless of continent."
- **Hit ceiling**: Our benchmark test case (P. radiata at a known plantation in Wairarapa, NZ: -41.15235814226619, 175.0998652276375) ranks P. radiata at **#17**. We've tried IDF weighting, subtaxa merging, managed forest probability scoring, and multi-scale blending. The best we achieved was #16. The k-NN architecture cannot do better.
- **No environmental context**: k-NN only uses the 64-D satellite embedding. It ignores elevation, climate, soil, land cover, and all other environmental variables. Two locations can look identical from satellite but have completely different species due to altitude, rainfall, or soil chemistry.

### 1.3 The Solution: SINR Neural Network

We are training a **SINR-style ResidualFCNet** (Cole et al., ICML 2023) that takes satellite embedding + environmental features as input and outputs species probabilities. This architecture was proven at scale on 47,000 species in the original SINR paper.

Key advantages over k-NN:
- Sees ALL training data globally (not just 500 nearest neighbors)
- Uses environmental context (elevation, climate, soil) alongside satellite imagery
- Learns cross-biome species signatures
- Inference in <1ms (vs. HNSW search overhead for k-NN)
- 47 MB model file (vs. querying an 11M-row database)

---

## 2. Data Pipeline: From GBIF to Training Data

### 2.1 Raw Occurrence Data

**Source**: GBIF (Global Biodiversity Information Facility) — the world's largest open biodiversity database.

We hold **96,527,874 raw occurrence records** in BigQuery (`treekipedia-479918.species_data.occurrences`), representing observations of tree species with geographic coordinates. These come from herbarium specimens, citizen science (iNaturalist), ecological surveys, and forest inventories.

Each record has:
- `taxon_id`: Our internal species identifier (e.g., `GymPiPiPnCx50820-00` for *Pinus radiata*)
- `latitude`, `longitude`: Where the tree was observed
- `coordinate_uncertainty_m`: GPS accuracy (ranges from 1m to 100km+)
- `occurrence_year`: When the observation was made (1700-2024)
- `establishment_means`: Native, introduced, managed, etc.

**Species catalog**: 67,743 species in our `species` table. 60,207 have GBIF occurrences.

### 2.2 Satellite Embeddings: AlphaEarth

**Source**: Google AlphaEarth (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`) on Google Earth Engine.

AlphaEarth is a foundation model trained on Sentinel-2 satellite imagery. It produces a **64-dimensional embedding vector** for every 10m x 10m tile on Earth, capturing:
- Land cover type and structure
- Vegetation phenology (seasonal patterns)
- Canopy height and density
- Soil color and moisture (to the extent visible from space)
- Urban/agricultural/natural land use patterns
- Spectral signatures across visible, near-infrared, and shortwave bands

**Resolution**: 10m native, stored as `vector(64)` in PostgreSQL with pgvector.

**Temporal coverage**: Annual composites from 2017-2024. Each embedding is tagged with `emb_year` (the year the satellite composite was produced). A tree observed in 2005 might be matched to a 2017 embedding (the closest available year).

**Key property**: Two locations that look similar from satellite will have similar embedding vectors (high cosine similarity). This is the foundation of both the k-NN system and the SINR model.

### 2.3 The Data Funnel

```
96.5M raw GBIF occurrences (60,207 species)
    |
    | Coordinate deduplication at 4 decimal places (~11m, matches AlphaEarth 10m tiles)
    | Dedup key: (taxon_id, lat4dp, lon4dp, emb_year)
    v
29.4M unique (species, pixel) pairs
    |
    | GEE sampling: fetch AlphaEarth embedding at each pixel
    | Two phases: V4 Direct (2.4M pixels) + Phase C Regime 2 (4.7M pixels)
    v
7.1M unique pixels sampled
    |
    | AlphaEarth coverage filter (not all pixels have embeddings)
    v
6.4M pixels with AlphaEarth coverage
    |
    | Species rejoin: one row per (species, pixel) pair
    v
11,396,890 rows in species_occurrence_embeddings (43,992 species)
    |
    | Environmental data JOIN (pixel_environmental_bands)
    | 97.1% coverage after V4 + Arctic backfills
    v
11,071,342 rows with both embeddings AND environmental data (43,566 species)
    |
    | Hard cap: max 50,000 training samples per species
    v
8,585,022 training rows
    |
    | 95/5 train/val split
    v
8,155,811 train + 429,211 validation
```

### 2.4 Why 4 Decimal Places?

Coordinates are rounded to 4 decimal places for deduplication. At the equator, 0.0001 degrees ~ 11.1 meters, which approximately matches AlphaEarth's 10m tile size. This means:
- Two GBIF observations within ~11m of each other map to the same satellite tile
- Multi-year observations at the same pixel are treated as DIFFERENT occurrences (because the satellite embedding changes year to year — the dedup key includes `emb_year`)
- The 6-decimal-place original coordinates are preserved in the database but rounded for pixel-level operations

### 2.5 Data Quality Weights

Each training sample has two quality weights:

- **`quality_weight`** (0.0-1.0): Based on coordinate uncertainty. Records with GPS accuracy <100m get weight 1.0; records with 10km uncertainty get ~0.1. This downweights herbarium specimens from the 1800s with vague locality descriptions.
- **`density_weight`** (0.0-1.0): Inverse of local observation density. Prevents overrepresentation of heavily-sampled areas (e.g., European forests near research stations). A lone observation in remote Papua New Guinea gets higher weight than one of 10,000 observations in the Black Forest.

The training loss multiplies by `quality_weight * density_weight` (clipped to [0.01, 10.0]).

---

## 3. Environmental Features

### 3.1 Overview

Each pixel has **59 environmental variables** extracted from Google Earth Engine, covering:

| Category | Variables | Source | Resolution | Count |
|----------|-----------|--------|-----------|-------|
| **Terrain** | elevation, slope, aspect, hillshade | SRTM 30m / Copernicus DEM GLO-30 (>60N) | 30m | 4 |
| **Climate** | bio01-bio19 (temperature, precipitation, seasonality) | WorldClim V1 | 1km | 19 |
| **Soil** | pH, clay%, sand%, organic carbon, texture class, bulk density, water content | OpenLandMap | 250m | 7 |
| **Forest** | treecover2000, lossyear | Hansen GFC 2023 | 30m | 2 |
| **Land Cover** | JRC forest type, JRC TMF status, TMF degradation year, ESA WorldCover, Dynamic World, SBTN natural land | Various | 10m-30m | 6 |
| **Water** | surface water occurrence, recurrence, seasonality, MERIT HAND, upstream area | JRC GSW, MERIT Hydro | 30m-90m | 5 |
| **Canopy/Biomass** | GEDI canopy height, foliage height diversity, MODIS GPP, biomass AGB | GEDI, MODIS, NASA ORNL | 300m-1km | 4 |
| **Human** | human modification, nighttime lights, fire frequency | CSP HM, VIIRS, MODIS MCD64A1 | 1km | 3 |
| **Ecoregion** | eco_id, biome_num, topo_diversity | RESOLVE Ecoregions 2017, CSP/ERGo | 250m-1km | 3 |
| **TerraClimate** | VPD, AET, soil moisture, PDSI, water deficit, solar radiation | TerraClimate | 4km | 6 |

**Total**: 59 environmental features + 64 embedding dimensions = **123 input features** to the model.

### 3.2 Temporal Matching

Environmental variables are **year-matched** to the occurrence observation, not sampled at a fixed modern date. This is critical because:
- A tree observed in 2005 should get 2005 climate data, not 2023
- Forest loss that happened in 2020 shouldn't affect a 2010 observation
- TerraClimate uses a +/-2 year window around the occurrence year for smoothing

Static datasets (soil, terrain, ecoregions) are the same for all years. Temporal datasets (TerraClimate, MODIS GPP, Dynamic World, fire, nightlights, Hansen loss) are year-specific.

### 3.3 The Arctic Gap (Fixed)

**Problem**: SRTM (the DEM used for terrain extraction and as a grid-alignment anchor for GEE sampling) has no coverage above 60N. This caused 65,471 embeddings across 232 subarctic/boreal species to have zero environmental data. Affected species include Pinus sylvestris (6,459 records), Picea abies (5,023), Juniperus communis (22,639).

**Fix**: We modified the extraction pipeline (`temporal_env_sampler.py`) to use **Copernicus DEM GLO-30** (same 30m resolution, covers to 84N) for pixels above 59N. For the 4 datasets with no arctic coverage (SRTM, GEDI, JRC TMF, SRTM topo diversity), values are set to 0 and the model handles them as missing features (NaN -> 0 after z-score normalization).

**Result**: Arctic extraction completed in 11 minutes (40 batches, 100% success rate), recovering 56,589 new environmental data rows. Final coverage: **97.1%** of embeddings have environmental data.

### 3.4 Disturbed Forest Handling

The system distinguishes between natural and disturbed forests through multiple features:
- **Hansen treecover2000 + lossyear**: Shows forest cover in 2000 and when/if loss occurred
- **loss_at_obs / lossyear_at_obs**: Computed fields showing whether forest loss had already occurred at the time of the species observation
- **JRC TMF status**: Tropical Moist Forest classification (undisturbed, degraded, deforested, regrowth)
- **JRC TMF degradation year**: When degradation was first detected
- **ESA WorldCover / Dynamic World**: Current land cover class
- **SBTN natural land**: Binary flag for natural vs. modified land
- **Human modification index**: Continuous 0-1 score

The model learns from all of these simultaneously, allowing it to differentiate between species that thrive in primary forest vs. secondary growth vs. plantations vs. degraded land.

---

## 4. Model Architecture

### 4.1 Why SINR?

We conducted exhaustive research comparing architectures:

- **LightGBM**: Mathematically impossible at 43K classes. Gradient boosting requires gradient matrices of size (n_samples x n_classes). At 10M rows x 43K classes, this would need ~1.6 TB RAM.
- **Per-species binary classifiers**: 43K separate models. Impractical to train, deploy, and maintain.
- **Embedding-space models** (predict embedding, find nearest species): Loses the multi-label nature of the problem (multiple species can occur at one location).
- **SINR ResidualFCNet** (Cole et al., ICML 2023): Proven at 47,375 species. Multi-label via independent sigmoids. Fits in memory. Fast inference. This is what we chose.

### 4.2 Architecture Details

```
Input: 123 features (64 embedding + 59 environmental)
    |
    v
Linear(123 -> 256) + ReLU
    |
    v
ResidualBlock_1(256):  Linear(256->256) -> ReLU -> Dropout(0.3) -> Linear(256->256) -> ReLU -> + skip
    |
    v
ResidualBlock_2(256):  (same structure)
    |
    v
ResidualBlock_3(256):  (same structure)
    |
    v
ResidualBlock_4(256):  (same structure)
    |
    v
Linear(256 -> 43,566, no bias)  -->  Raw logits (one per species)
    |
    v
Sigmoid (applied in loss function, not in forward pass)
    -->  Independent probability [0, 1] per species
```

**Total parameters**: 11,710,976 (~11.7M)
**Model size on disk**: ~47 MB (float32)
**Inference time**: <1ms per query

### 4.3 Key Design Decisions

**No bias in output layer**: Following SINR, the output projection has no bias term. This prevents the model from learning species-specific base rates that could dominate over location-based features.

**Independent sigmoids, not softmax**: Each species gets an independent sigmoid probability. This is a multi-label formulation — multiple species CAN have high probability at the same location (because multiple species DO co-occur). Softmax would force probabilities to sum to 1, which is wrong for this problem.

**Residual connections (skip connections)**: Each ResidualBlock adds its output to its input (`x + f(x)`). This helps gradient flow in deeper networks and allows the model to learn identity mappings for features that are already useful.

**Dropout 0.3**: Applied within each residual block to prevent overfitting. At inference time, dropout is disabled.

### 4.4 Feature Normalization

All 123 features are **z-score normalized**: `(x - mean) / std`, computed on the training set and applied identically to validation and inference. Features with zero variance get `std = 1.0` to prevent division by zero.

NaN and infinity values are replaced with 0 before normalization. After normalization, a NaN feature becomes `(0 - mean) / std`, which is a slight bias toward the mean — acceptable for the small fraction of missing data.

The normalization statistics (mean and std per feature) are saved alongside the model for use during inference.

---

## 5. Loss Function: Assumed-Negative BCE

### 5.1 The Core Problem

We have **presence-only data**. GBIF tells us "species X was observed at location Y." It does NOT tell us "species X was NOT observed at location Z." The absence of a record doesn't mean the species is absent — it might simply mean no one surveyed there.

### 5.2 The SINR Solution

The **Assumed-Negative Full Loss** (`an_full`) treats the problem as follows:

For each training sample (a location where species S was observed):
1. **Positive signal**: Species S is present. Loss = `-pos_weight * log(sigmoid(logit_S))`
2. **Assumed-negative signal**: All other ~43,565 species are assumed absent. Loss = `-log(1 - sigmoid(logit_i))` for each species i != S
3. **Background signal**: At random locations (shuffled from training set), ALL species are assumed absent.

The positive loss is weighted by `pos_weight = 2048` to compensate for the extreme class imbalance: 1 positive species vs. ~43,565 assumed negatives per sample.

### 5.3 Mathematical Formulation

```
For a batch of observations with logits L (shape: batch x num_species):

log_pos = log(sigmoid(L))           # = -softplus(-L)
log_neg = log(1 - sigmoid(L))       # = -softplus(L) = log_sigmoid(-L)

# Base: assume all species absent
loss_neg = -mean(log_neg, dim=species)    # per-sample negative loss

# Correction for the target species: remove negative, add weighted positive
correction = (-target_log_neg + pos_weight * (-target_log_pos)) / num_species

loss_per_sample = loss_neg + correction

# Apply quality/density weights
weighted_loss = mean(loss_per_sample * sample_weight)

# Background: random locations, all species absent
bg_loss = -mean(log_neg(bg_logits))
total_loss = weighted_loss + bg_weight * bg_loss
```

### 5.4 Why Not Standard BCE?

Standard BCE requires explicit positive AND negative labels. We'd need to decide which species are "confirmed absent" at each location, which we don't know. The assumed-negative approach elegantly handles this by treating all unobserved species as "probably absent" while acknowledging this is an approximation through the pos_weight parameter.

---

## 6. Training Process

### 6.1 Training Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Batch size | 2,048 | Fits in MPS GPU memory; large enough for stable gradients |
| Epochs | 12 | Empirically chosen; model plateaus around epoch 6-8 |
| Learning rate | 0.0005 | Adam optimizer default range |
| LR decay | 0.98/epoch | ExponentialLR; gradual cooldown |
| pos_weight | 2,048 | ~= batch_size; compensates for 1 positive vs 43K negatives |
| Dropout | 0.3 | Standard for SINR; moderate regularization |
| Hidden dim | 256 | SINR default; 512 would double model size for marginal gain |
| Residual blocks | 4 | SINR default; enough depth for non-linear feature interactions |
| Hard cap/species | 50,000 | Prevents common species from dominating training |
| Gradient clipping | max_norm=1.0 | Prevents exploding gradients |
| Background weight | 1.0 | Equal weight to observed and background loss |

### 6.2 Training Data Stats

- **Training set**: 8,155,811 rows
- **Validation set**: 429,211 rows (5% random split)
- **Species**: 43,566 (with subtaxa)
- **Features**: 123 (64 embedding + 59 environmental)
- **NaN values replaced**: 2,604,956 in train, 137,188 in validation
- **Train parquet size**: 1.36 GB
- **Validation parquet size**: 0.07 GB

### 6.3 Training Results (Complete)

Training on Apple Silicon MPS (M-series GPU), ~27-36 min/epoch, 12 epochs total (~6 hours):

| Epoch | Train Loss | Val Loss | Top-10 Accuracy | Top-50 Accuracy | Best Model? |
|-------|-----------|----------|----------------|----------------|-------------|
| 1 | 0.01616 | 0.00641 | 45.6% | 82.4% | Yes |
| 2 | 0.00977 | 0.00577 | 49.7% | 84.3% | Yes |
| 3 | 0.00886 | 0.00551 | 51.0% | 85.3% | Yes |
| 4 | 0.00836 | 0.00543 | 51.7% | 85.8% | Yes |
| 5 | 0.00804 | 0.00542 | 52.1% | 86.0% | Yes |
| 6 | 0.00782 | 0.00539 | 52.4% | 86.2% | Yes (best by loss) |
| 7 | 0.00765 | 0.00544 | 52.7% | 86.3% | No |
| 8 | 0.00750 | 0.00547 | 52.8% | 86.4% | No |
| 9 | 0.00738 | 0.00550 | 52.9% | 86.5% | No |
| 10 | 0.00729 | 0.00556 | 53.1% | 86.5% | No |
| 11 | 0.00720 | 0.00561 | 53.2% | 86.6% | No |
| 12 | 0.00713 | 0.00563 | 53.3% | 86.6% | No |

**Final results**: Best val_loss = 0.00539 at epoch 6. Best ranking accuracy at epoch 12: top-10 = 53.3%, top-50 = 86.6%. The saved best model is epoch 6 (by val_loss).

**Interpretation**: Val loss plateaued at epoch 6 and rose thereafter (mild overfitting). However, ranking accuracy (top-10, top-50) continued improving through epoch 12, reaching 53.3% and 86.6% respectively. This divergence is expected — the model gets better at ranking species correctly while becoming slightly miscalibrated in absolute probability values. The best checkpoint by val_loss (epoch 6) may actually produce better-calibrated probabilities, while the final epoch has slightly better ranking.

**Key metric**: Top-10 accuracy of 53.3% means the correct species appears in the model's top 10 predictions more than half the time, across 43,566 possible species. Top-50 accuracy of 86.6% means the correct species is almost always in the top 50.

---

## 7. The P. radiata Case Study

### 7.1 Test Location

**Coordinates**: -41.15235814226619, 175.0998652276375
**Location**: Wairarapa region, North Island, New Zealand
**Ground truth**: Known *Pinus radiata* commercial plantation

### 7.2 k-NN System History

| Version | P. radiata Rank | Score | System Description |
|---------|----------------|-------|-------------------|
| Original (session 7) | #16 | 88 | IDF weighting in SQL |
| v3 subtaxa + IDF | #26 | 99 | max() inflation bug from subtaxa |
| v3 + MFP v2 (current) | #17 | 80 | Managed forest probability + log-scale concentration |
| SINR model (target) | TBD | TBD | Trained neural network |

### 7.3 Why k-NN Fails Here

The Wairarapa plantation's AlphaEarth embedding captures "planted conifer rows, dense canopy, Southern Hemisphere mid-latitude." The k-NN search finds the 500 most similar embeddings globally. Many of these are:
- Other NZ plantations (often *Pseudotsuga menziesii*, *Cupressus macrocarpa*, or *Eucalyptus* spp. which also exist in NZ planted forests)
- Native NZ forest (which dominates the NZ embeddings by sheer volume)
- Southern Hemisphere planted forests (Australia, Chile) which may contain different species

P. radiata occurrences are spread across California (native), NZ, Chile, Australia, Spain, and South Africa (planted). The k-NN approach can't aggregate this cross-continental evidence because it only looks at the nearest 500 tiles by embedding similarity.

### 7.4 Why SINR Should Do Better

The SINR model has seen ALL P. radiata training data globally during training. It has learned that the combination of:
- Satellite embedding pattern (planted conifer visual signature)
- Environmental features (mild temperate climate, moderate rainfall, moderate elevation)
- Geographic context (Southern Hemisphere, specific biome and ecoregion)

...is strongly associated with P. radiata. It doesn't need to find similar pixels — it has internalized the species' environmental signature.

### 7.5 Evaluation Plan

After training completes, we will:
1. Extract the 123 features at the test coordinates (AlphaEarth embedding + GEE environmental data)
2. Run inference through the trained model
3. Report P. radiata's rank and probability
4. Compare to the k-NN rank of #17

---

## 8. Database Architecture

### 8.1 PostgreSQL Tables

#### `species_occurrence_embeddings` (11,396,890 rows)

The core table. Each row represents one (species, pixel, year) tuple.

| Column | Type | Description |
|--------|------|-------------|
| id | integer PK | Auto-increment |
| taxon_id | varchar(50) | Species identifier (e.g., `GymPiPiPnCx50820-00`) |
| embedding | vector(64) | AlphaEarth 64-D satellite embedding |
| latitude | double precision | WGS84 latitude |
| longitude | double precision | WGS84 longitude |
| emb_year | smallint | Year of satellite composite (2017-2024) |
| elevation | smallint | SRTM elevation (meters) |
| treecover2000 | smallint | Hansen tree cover % in 2000 |
| loss | boolean | Hansen forest loss detected |
| lossyear | smallint | Year of forest loss (1-23 = 2001-2023) |
| density_weight | double precision | Inverse observation density weight |
| quality_weight | double precision | Coordinate accuracy weight |
| data_regime | smallint | Sampling pipeline version (1=V4, 2=Phase C) |
| coordinate_uncertainty_m | double precision | GPS accuracy from GBIF |
| establishment_means | varchar(50) | Native, introduced, managed, etc. |
| occurrence_year | smallint | Year of original GBIF observation |

**Indexes**:
- HNSW on `embedding` (vector_cosine_ops, m=16, ef_construction=200) — for k-NN similarity search
- B-tree on `taxon_id` — for species-level queries

#### `pixel_environmental_bands` (9,173,240 rows)

Environmental features per pixel. Joined to embeddings via `(round(lat, 4), round(lon, 4), year)`.

59 environmental columns + location columns. Full schema in Section 3.1.

**Index**: B-tree on `(latitude, longitude, occurrence_year)` for JOIN performance.

#### `species_occurrence_stats` (43,992 rows)

Per-species statistics for IDF weighting in the k-NN system.

#### `species_habitat_centroids` (49,640 rows, 22,603 species)

K-means cluster centroids in embedding space. Used as fallback when k-NN returns too few results. IVFFlat index for approximate nearest neighbor search.

### 8.2 BigQuery Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `occurrences` | 96,527,874 | Raw GBIF data |
| `alphaearth_embeddings_v4` | 3,371,724 | V4 direct pixel embeddings |
| `phase_c_embeddings_env_v1` | 3,957,403 | Phase C with env data |
| `v4_env_backfill_v1` | 1,592,380 | V4 env backfill round 1 |
| `v4_env_backfill_v2` | 693,815 | V4 env backfill round 2 |
| `arctic_env_backfill_v1` | 113,603 | Arctic >59N env data |

### 8.3 Data Coverage Summary

| Metric | Count |
|--------|-------|
| Species in catalog | 67,743 |
| Species with GBIF occurrences | 60,207 |
| Species with embeddings | 43,992 |
| Species with embeddings + env data | 43,566 |
| Species with >= 10 training samples | 17,448 |
| Species with >= 100 training samples | 3,719 |
| Total embeddings | 11,396,890 |
| Embeddings with env data (97.1%) | 11,071,342 |
| Training rows (after hard cap) | 8,585,022 |

---

## 9. Current Prediction System (k-NN) — Detailed

### 9.1 Query Flow

When a user queries location (lat, lon):

1. **Fetch embedding**: Call Python microservice (port 5002) which queries AlphaEarth on GEE with multi-year fallback [2023, 2022, ..., 2017]. Also fetches SRTM elevation, Hansen forest data, WorldClim bioclim, soil properties.

2. **Managed Forest Probability (MFP)**: Computed from 4 signals:
   - Spatial embedding homogeneity (3x3 grid around point): weight 0.40
   - Canopy height uniformity (coefficient of variation): weight 0.35
   - Tall canopy signal (>15m): weight 0.25
   - CCDC stability modifier (Google CCDC change detection)
   - Threshold: MFP > 0.50 activates managed forest mode with different scoring weights

3. **Channel 1a — k-NN Occurrence Matching**: HNSW search for top 500 nearest neighbors in `species_occurrence_embeddings`. Aggregate per species:
   - `raw_vote = SUM(similarity * density_weight * quality_weight)`
   - Multi-scale: fine (top 50 neighbors) and broad (all 500)
   - Subtaxa merging: group subtaxa back to parent species
   - Context-dependent IDF: `speciesIdf = 1 / log(1 + total_occurrences)`, dampened when embedding homogeneity is high (managed forest)
   - Blended score: `0.4 * fineVote + 0.6 * broadVote`

4. **Channel 1b — Centroid Fallback**: IVFFlat search on `species_habitat_centroids`. Adds species not found by k-NN with cosine similarity >= 0.40.

5. **Channel 2 — Spatial Proximity**: Query `geohash_species_tiles` within 50km. Score based on observation density and distance.

6. **Channel 3 — WCVP/Ecoregion Enrichment**: Metadata lookup for range information, native status.

7. **Multi-Signal Scoring**: 6 signals combined with dynamic weights:
   - Embedding similarity (0.08-0.45 weight depending on confidence)
   - Spatial proximity (0.08-0.40)
   - Range/native status (0.10-0.15)
   - Ecoregion match (0.10-0.15)
   - Climate envelope (0.10-0.15)
   - Soil match (0.10-0.15)

   Weights shift based on data availability and signal confidence. Managed forest mode uses different weight profiles.

### 9.2 Limitations

1. **Only 500 neighbors**: Can miss species that are common globally but rare in the local embedding neighborhood
2. **No environmental learning**: The 6-signal scoring is hand-tuned heuristics, not learned
3. **No cross-biome generalization**: P. radiata in California vs. P. radiata in New Zealand have different embedding neighborhoods
4. **IDF ceiling**: IDF weighting helps rare species but can't fix fundamental neighborhood composition issues
5. **Maintenance burden**: 1,300+ lines of hand-tuned scoring logic with many magic numbers and threshold constants

---

## 10. SINR Integration Plan

### 10.1 Inference Endpoint

The trained model will run as a new endpoint on the existing Python microservice (`location_predictor_FIXED.py`, port 5002):

```
POST /sinr/predict
Body: { "lat": -41.15, "lon": 175.10 }
Response: {
  "predictions": [
    { "taxon_id": "GymPiPiPnCx50820-00", "probability": 0.83, "rank": 1 },
    { "taxon_id": "GymCuCuCpCx23456-00", "probability": 0.45, "rank": 2 },
    ...
  ],
  "model_version": "v1",
  "inference_time_ms": 0.8
}
```

### 10.2 Inference Pipeline

1. Fetch AlphaEarth embedding at (lat, lon) from GEE — already done by existing `/sample` endpoint
2. Fetch environmental features from GEE — already done by existing endpoint
3. Construct 123-feature vector: [64 embedding dims] + [59 env vars]
4. Z-score normalize using saved mean/std
5. Forward pass through model: 123 -> 256 -> ResBlock x4 -> 43,566 logits
6. Apply sigmoid to get probabilities
7. Sort descending, return top-K

### 10.3 Resource Requirements

| Metric | Value |
|--------|-------|
| Model file | 47 MB |
| RAM at runtime | ~100 MB (model + Python) |
| CPU | Any single core |
| GPU | Not needed for inference |
| Time per prediction | <1 ms |
| Load time (startup) | ~2 seconds |

### 10.4 Deployment Options

- **Option A**: Add to existing Python microservice (simplest, just load model at startup)
- **Option B**: Separate lightweight container (isolates model from GEE service)
- **Option C**: Serverless function (AWS Lambda, Cloud Functions) — model loads from cold start in ~5s

---

## 11. Known Limitations and Open Questions

### 11.1 Current Limitations

1. **Presence-only data**: We never truly know where a species is absent. The assumed-negative loss is an approximation.

2. **Temporal mismatch**: AlphaEarth embeddings are from 2017-2024 but GBIF observations span 1700-2024. A tree observed in 1950 gets a 2017 satellite embedding — the landscape may have changed dramatically.

3. **Species with few records**: 26,118 species (of 43,566) have fewer than 10 training samples. The model cannot learn meaningful patterns for these. They rely on whatever signal exists in their few samples.

4. **Planted vs. native confusion**: A *Pinus radiata* in its native California range and a *Pinus radiata* in a New Zealand plantation may have very different environmental signatures. The model treats all occurrences equally (though `establishment_means` could be used to differentiate in future versions).

5. **No spatial autocorrelation**: The model treats each sample independently. It doesn't learn that "if species X is at this location, it's more likely to be at the location 100m away too." This is by design (SINR operates on individual locations), but limits predictions for range boundaries.

6. **Categorical features as continuous**: Features like `eco_id`, `biome_num`, `soil_texture_class`, and `esa_worldcover_2021` are categorical but fed as continuous values after z-score normalization. The model may learn spurious ordinal relationships (e.g., treating eco_id 300 as "between" eco_id 200 and 400). Entity embeddings for categorical features could help.

7. **No uncertainty quantification**: The sigmoid outputs are not calibrated probabilities. A "0.8 probability" doesn't mean the species is present 80% of the time. Future work could add temperature scaling or Platt calibration.

### 11.2 Potential Improvements (For Review)

1. **Spatial encoding**: SINR originally includes latitude/longitude as input features (encoded via sinusoidal functions). We currently don't include geographic coordinates — the model must infer location purely from environmental features. Adding spatial encoding could help.

2. **Class frequency weighting**: Adjusting `pos_weight` per species based on observation frequency (rare species get higher weight) rather than using a single global `pos_weight = 2048`.

3. **Feature engineering**: Derived features like "distance to coast," "growing degree days," or biome-species interaction terms could add signal.

4. **Ensemble**: Combining SINR predictions with k-NN scores (the two systems use different signals and may be complementary).

5. **Curriculum learning**: Training on well-represented species first, then introducing rare species.

6. **Multi-year embeddings**: Using multiple years of AlphaEarth data per pixel (2017-2024) to capture phenological variation and temporal stability.

7. **Negative sampling strategy**: Instead of random background locations, sampling "hard negatives" from similar-but-different locations (same biome, different species) could sharpen discrimination.

8. **Model distillation**: Training a smaller model on the SINR's predictions for faster inference on constrained devices.

---

## 12. Species Knowledge Base: Full Schema (152 Columns)

The `species` table in PostgreSQL contains 67,743 records (50,797 species + 16,946 subspecies/varieties) with 152 columns of curated and AI-generated knowledge. This is not used in the SINR model's input features, but represents the rich species metadata that the prediction system surfaces to users. Understanding this schema is important for evaluating what additional data could improve predictions.

### 12.1 Taxonomy & Identification

| Column | Type | Description |
|--------|------|-------------|
| `taxon_id` | text PK | Internal identifier (e.g., `GymPiPiPnCx50820-00` for *Pinus radiata*). Encodes clade/order/family/genus hierarchy. |
| `species_scientific_name` | varchar(500) | Binomial name (e.g., "Pinus radiata") |
| `accepted_scientific_name` | text | Currently accepted name per taxonomic authorities |
| `taxon_full` | text | Full name including authority (e.g., "Pinus radiata D.Don") |
| `taxon_full_clean` | text | Cleaned version of above |
| `family` | varchar(500) | Taxonomic family (e.g., "Pinaceae") |
| `genus` | varchar(500) | Genus (e.g., "Pinus") |
| `class` | varchar(500) | Taxonomic class |
| `taxonomic_order` | varchar(500) | Taxonomic order |
| `specific_epithet` | varchar(500) | Species epithet (e.g., "radiata") |
| `subspecies` | text | Subspecies/variety designation |
| `taxon_id_new` | text | Updated taxon_id (if taxonomy changed) |
| `synonyms` | text | Known synonyms |
| `synonyms_ai` | text | AI-generated synonym list |
| `sci_lower` | text | Lowercase scientific name (for search) |
| `taxon_lower` | text | Lowercase full taxon (for search) |
| `common_name` | text | Common name(s) |
| `popular_common_name_ai` | text | AI-generated popular common name |
| `common_countries` | text | Countries where common name is used |
| `identification_features_ai` | text | AI-generated field identification guide |
| `etymology_ai` | text | AI-generated name origin |

### 12.2 Ecology & Habitat

| Column | Type | Description |
|--------|------|-------------|
| `habitat_ai` / `habitat_human` | text | Natural habitat description |
| `native_adapted_habitats_ai` / `_human` | text | Habitats the species is adapted to |
| `general_description_ai` / `_human` | text | Overall species description |
| `ecological_function_ai` / `_human` | text | Role in ecosystem (nitrogen fixer, canopy, etc.) |
| `associated_species` / `_ai` | text | Species commonly found growing nearby |
| `forest_type` | text | Forest classification (tropical dry, temperate rain, boreal, etc.) |
| `wetland_type` | text | Wetland association (if any) |
| `urban_setting` | text | Urban tree suitability |
| `successional_stage` | varchar(500) | Pioneer, early secondary, late secondary, climax |
| `forest_layers` | text | Canopy position (emergent, canopy, subcanopy, understory) |
| `tolerances` / `tolerances_ai` | text | Shade/drought/frost/salt tolerance |
| `climate_tolerance_ai` | text | AI-generated climate tolerance description |
| `ecoregions` | text | WWF ecoregion presence |
| `biomes` | text | Biome presence |
| `bioregions` | text | Bioregion presence |
| `functional_ecosystem_groups` | text | IUCN GET ecosystem classification |
| `vegetationtype` | text | Vegetation type classification |
| `present_intact_forest` | text | YES/NO/NA/YES;NO — presence in intact forest landscapes |
| `sbtn_landcover` | text | SBTN land cover classification |

### 12.3 Geographic Distribution

| Column | Type | Description |
|--------|------|-------------|
| `countries_native` | text | Native range countries |
| `countries_introduced` | text | Countries where introduced |
| `countries_invasive` | text | Countries where invasive |
| `wcvp_native` | text | WCVP (World Checklist of Vascular Plants) native regions — botanical country codes |
| `wcvp_introduced` | text | WCVP introduced regions |
| `total_occurrences` | text | Total GBIF occurrence count |

### 12.4 Climate & Soil Preferences

| Column | Type | Description |
|--------|------|-------------|
| `climate_type_koppengeiger` | text | Koppen-Geiger climate classifications where species occurs |
| `annual_temperature_range_c` | text | Temperature range tolerance |
| `annual_precipitation_mm` | text | Annual precipitation range |
| `wettest_month_precipitation_mm` | text | Wettest month precipitation |
| `driest_month_precipitation_mm` | text | Driest month precipitation |
| `precipitation_seasonality_cv` | text | Precipitation seasonality (coefficient of variation) |
| `wettest_quarter_precipitation_mm` | text | Wettest quarter precipitation |
| `driest_quarter_precipitation_mm` | text | Driest quarter precipitation |
| `elevation_ranges_ai` / `_human` | text | Elevation range (e.g., "0-2500m") |
| `compatible_soil_types_ai` / `_human` | text | Soil type preferences |
| `soil_texture_all` | text | All soil textures where found |
| `soil_texture_dominant` | text | Most common soil texture |
| `soil_texture_prefered` | text | Preferred soil texture |
| `soil_texture_tolerated` | text | Tolerated soil textures |
| `ph_all` / `ph_dominant` / `ph_prefered` / `ph_tolerated` | text | Soil pH ranges |
| `oc_all` / `oc_dominant` / `oc_prefered` / `oc_tolerated` | text | Soil organic carbon ranges |

### 12.5 Physical Characteristics

| Column | Type | Description |
|--------|------|-------------|
| `growth_form_ai` / `_human` | varchar(500) | Tree, shrub, liana, palm, etc. |
| `leaf_type_ai` / `_human` | varchar(500) | Needle, broad-leaf, compound, etc. |
| `deciduous_evergreen_ai` / `_human` | varchar(500) | Deciduous, evergreen, semi-deciduous |
| `flower_color_ai` / `_human` | varchar(500) | Flower color |
| `fruit_type_ai` / `_human` | varchar(500) | Fruit type (drupe, berry, cone, samara, etc.) |
| `bark_characteristics_ai` / `_human` | text | Bark description |
| `maximum_height_ai` / `_human` | text | Max height in meters |
| `maximum_diameter_ai` / `_human` | text | Max DBH in cm |
| `lifespan_ai` / `_human` | varchar(500) | Short-lived, moderate, long-lived |
| `maximum_tree_age_ai` / `_human` | text | Maximum recorded age |
| `allometric_models` | text | Biomass allometric equations |
| `allometric_curve` | text | Growth curve parameters |

### 12.6 Conservation & Threats

| Column | Type | Description |
|--------|------|-------------|
| `conservation_status_ai` / `_human` | varchar(500) | IUCN Red List status (LC, NT, VU, EN, CR, EW, EX) |
| `national_conservation_status` | text | Country-level protection status |
| `climate_change_vulnerability` | varchar(500) | Climate change vulnerability rating |
| `threats` | text | Known threats (deforestation, disease, invasive species, etc.) |
| `verification_status` | varchar(500) | Data verification level |

### 12.7 Ecological Interactions (GloBI)

Data sourced from the Global Biotic Interactions (GloBI) database:

| Column | Type | Description |
|--------|------|-------------|
| `globi_pollinatedby` | text | Known pollinators |
| `globi_eatenby` | text | Herbivores/browsers |
| `globi_flowersvisitedby` | text | Flower visitors (not confirmed pollinators) |
| `globi_hasparasite` | text | Known parasites |
| `globi_haspathogen` | text | Known pathogens |
| `globi_hasdispersalvector` | text | Seed dispersal agents |
| `globi_preyeduponby` | text | Predators |
| `globi_hasparasitoid` | text | Parasitoids |

### 12.8 Economic & Cultural Value

| Column | Type | Description |
|--------|------|-------------|
| `comercialspecies` / `_upper` / `_lower` | text | Commercial species flag and classification |
| `timber_value` / `_ai` | text | Timber value description |
| `non_timber_products` / `_ai` | text | NTFPs (resins, fruits, medicines, etc.) |
| `cultural_significance_ai` / `_human` | text | Cultural/religious significance |
| `nutritional_caloric_value` / `_ai` | text | Nutritional value of edible parts |
| `agroforestry_use_cases_ai` / `_human` | text | Agroforestry applications |
| `cultivars` | text | Known cultivated varieties |

### 12.9 Stewardship & Management

| Column | Type | Description |
|--------|------|-------------|
| `stewardship_best_practices_ai` / `_human` | text | Management guidelines |
| `planting_recipes_ai` / `_human` | text | Planting and establishment guidance |
| `pruning_maintenance_ai` / `_human` | text | Pruning guidelines |
| `disease_pest_management_ai` / `_human` | text | IPM guidance |
| `fire_management_ai` / `_human` | text | Fire management recommendations |
| `propagation_methods_ai` | text | Seed/cutting propagation methods |
| `cultivation_details` | text | Cultivation requirements |

### 12.10 Research & Data Provenance

| Column | Type | Description |
|--------|------|-------------|
| `researched` | text | Whether AI research has been completed (NA/TRUE/FALSE) |
| `research_version` | integer | Research version number |
| `research_date` | timestamp | When research was last run |
| `research_agent` | text | Which AI model performed research |
| `research_confidence` | real | AI confidence score |
| `research_sources` | jsonb | Structured source references |
| `research_flags` | jsonb | Data quality flags from research |
| `research_token_cost` | real | Token cost of AI research |
| `reference_list` | text | Reference citations |
| `data_sources` | text | Data source attribution |
| `ipfs_cid` | varchar(500) | IPFS content hash for on-chain attestation |
| `last_updated_date` | text | Last update timestamp |
| `default_image` | varchar(500) | Primary Wikimedia image URL |
| `associated_media` | text | Additional media references |

---

## 13. Species Occurrence Distribution Analysis

Understanding the distribution of training data per species is critical because the SINR model's ability to learn meaningful patterns is directly proportional to the number of training samples available for each species.

### 13.1 Distribution Statistics

**Total species with embeddings**: 43,992

| Metric | Value |
|--------|-------|
| Mean occurrences/species | 259.1 |
| Median occurrences/species | 6 |
| Min | 1 |
| Max | 447,893 (Acer rubrum) |

The extreme skew (mean 259 vs. median 6) reveals a severe long-tail problem.

### 13.2 Occurrence Count Brackets

| Bracket | Species Count | % of Total | Cumulative % |
|---------|--------------|-----------|--------------|
| >= 100,000 | 17 | 0.04% | 0.04% |
| 50,000 - 99,999 | 29 | 0.07% | 0.10% |
| 10,000 - 49,999 | 153 | 0.35% | 0.45% |
| 1,000 - 9,999 | 503 | 1.14% | 1.60% |
| 100 - 999 | 3,104 | 7.06% | 8.65% |
| 10 - 99 | 13,938 | 31.68% | 40.34% |
| 2 - 9 | 17,432 | 39.62% | 79.96% |
| 1 (singletons) | 8,816 | 20.04% | 100.00% |

**Key observation**: 60% of species (26,248) have fewer than 10 training samples. 20% are singletons. The model cannot learn meaningful environmental signatures for these species. They effectively receive a "generic species" prediction based on the few data points available.

### 13.3 Top 20 Most-Observed Species

| Rank | Species | Family | Occurrences |
|------|---------|--------|-------------|
| 1 | Acer rubrum | Sapindaceae | 447,893 |
| 2 | Pinus sylvestris | Pinaceae | 270,193 |
| 3 | Pinus pinaster | Pinaceae | 239,258 |
| 4 | Pinus halepensis | Pinaceae | 232,754 |
| 5 | Pinus pinea | Pinaceae | 188,753 |
| 6 | Quercus rotundifolia | Fagaceae | 179,145 |
| 7 | Acer negundo | Sapindaceae | 166,153 |
| 8 | Picea abies | Pinaceae | 157,955 |
| 9 | Quercus robur | Fagaceae | 141,066 |
| 10 | Acer platanoides | Sapindaceae | 136,515 |
| 11 | Juniperus communis | Cupressaceae | 130,681 |
| 12 | Prunus serotina | Rosaceae | 124,622 |
| 13 | Fraxinus excelsior | Oleaceae | 122,971 |
| 14 | Fagus sylvatica | Fagaceae | 113,675 |
| 15 | Pseudotsuga menziesii | Pinaceae | 108,827 |
| 16 | Acer saccharum | Sapindaceae | 106,778 |
| 17 | Quercus alba | Fagaceae | 101,110 |
| 18 | Quercus suber | Fagaceae | 92,947 |
| 19 | Corylus avellana | Betulaceae | 90,357 |
| 20 | Pinus nigra | Pinaceae | 89,475 |

**Bias patterns**: Heavy overrepresentation of European and North American species (where citizen science programs like iNaturalist and national forest inventories are most active). Tropical species are severely underrepresented in GBIF despite constituting the majority of global tree diversity.

### 13.4 GBIF Data Characteristics

Each raw occurrence record from GBIF includes:
- **Observation type**: Herbarium specimens (historical, precise locality), citizen science (modern, GPS-tagged), ecological surveys (systematic, high quality), forest inventories (government, plot-based)
- **Temporal range**: 1700-2024, though the vast majority are post-2000 (citizen science boom)
- **Coordinate uncertainty**: Ranges from <1m (modern GPS) to >100km (historical records with only county-level locality). Our `quality_weight` downweights uncertain records.
- **Establishment means**: Native, introduced, managed, invasive. Most records lack this field, so the model cannot reliably distinguish native vs. planted occurrences.

### 13.5 Geographic Bias in GBIF Data

GBIF occurrence density is profoundly uneven globally:

- **Over-sampled**: Western Europe (esp. Spain, France, Germany, UK, Scandinavia), eastern North America, Australia, parts of southern South America
- **Under-sampled**: Central Africa, mainland Southeast Asia, central South America, central Asia, much of Indonesia/Papua New Guinea
- **Consequence**: The model will perform well in Europe/North America and poorly in data-sparse tropical regions where species diversity is highest. Our `density_weight` partially compensates but cannot fix fundamental absence of data.

---

## 14. GEE Dataset Catalog: Complete Reference

Every Google Earth Engine dataset used in the environmental feature pipeline. This section enables evaluation of what additional datasets could improve the model.

### 14.1 Terrain (4 features)

| Feature | GEE Asset ID | Band | Resolution | Notes |
|---------|-------------|------|-----------|-------|
| `elevation` | `USGS/SRTMGL1_003` | `elevation` | 30m | Derived via `ee.Terrain.products()`. No coverage >60N. |
| `slope` | (derived from above) | — | 30m | Degrees. |
| `aspect` | (derived from above) | — | 30m | 0-360 degrees. |
| `hillshade` | (derived from above) | — | 30m | 0-255. |

**Arctic substitute**: `COPERNICUS/DEM/GLO30` (band `DEM`, 30m, covers to 84N) used for pixels >59N.

### 14.2 Bioclimatic Variables (19 features)

| Feature | GEE Asset ID | Band | Resolution | Description |
|---------|-------------|------|-----------|-------------|
| `bio01` | `WORLDCLIM/V1/BIO` | `bio01` | ~1km | Annual mean temperature (C x 10) |
| `bio02` | | `bio02` | | Mean diurnal range |
| `bio03` | | `bio03` | | Isothermality (bio02/bio07 x 100) |
| `bio04` | | `bio04` | | Temperature seasonality (stdev x 100) |
| `bio05` | | `bio05` | | Max temperature warmest month |
| `bio06` | | `bio06` | | Min temperature coldest month |
| `bio07` | | `bio07` | | Temperature annual range (bio05-bio06) |
| `bio08` | | `bio08` | | Mean temperature wettest quarter |
| `bio09` | | `bio09` | | Mean temperature driest quarter |
| `bio10` | | `bio10` | | Mean temperature warmest quarter |
| `bio11` | | `bio11` | | Mean temperature coldest quarter |
| `bio12` | | `bio12` | | Annual precipitation (mm) |
| `bio13` | | `bio13` | | Precipitation wettest month |
| `bio14` | | `bio14` | | Precipitation driest month |
| `bio15` | | `bio15` | | Precipitation seasonality (CV) |
| `bio16` | | `bio16` | | Precipitation wettest quarter |
| `bio17` | | `bio17` | | Precipitation driest quarter |
| `bio18` | | `bio18` | | Precipitation warmest quarter |
| `bio19` | | `bio19` | | Precipitation coldest quarter |

### 14.3 Soil Properties (7 features)

All from OpenLandMap at 250m resolution, surface layer (0cm depth, band `b0`):

| Feature | GEE Asset ID | Units |
|---------|-------------|-------|
| `soil_ph` | `OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02` | pH x 10 |
| `soil_clay_pct` | `OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02` | % mass |
| `soil_sand_pct` | `OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02` | % mass |
| `soil_organic_carbon` | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | g/kg |
| `soil_texture_class` | `OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02` | USDA class (1-12) |
| `soil_bulk_density` | `OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02` | kg/m3 |
| `soil_water_content` | `OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01` | % vol at -33kPa |

### 14.4 Forest Cover & Change (5 features)

| Feature | GEE Asset ID | Band | Resolution | Temporal? |
|---------|-------------|------|-----------|-----------|
| `treecover2000` | `UMD/hansen/global_forest_change_2023_v1_11` | `treecover2000` | 30m | Static (year 2000 baseline) |
| `lossyear` | (same) | `lossyear` | 30m | Static (cumulative) |
| `jrc_forest_type` | `JRC/GFC2020_subtypes/V1` | `Map` | 10m | Static (2020) |
| `jrc_tmf_status` | `projects/JRC/TMF/v1_2024/TransitionMap_Subtypes` | `TransitionMap_Subtypes` | 30m | Static (tropics only) |
| `jrc_tmf_degrad_year` | `projects/JRC/TMF/v1_2024/DegradationYear` | `constant` | 30m | Static (tropics only) |

### 14.5 Land Cover (3 features)

| Feature | GEE Asset ID | Band | Resolution | Temporal? |
|---------|-------------|------|-----------|-----------|
| `esa_worldcover_2021` | `ESA/WorldCover/v200` | `Map` | 10m | Static (2021) |
| `dynamic_world` | `GOOGLE/DYNAMICWORLD/V1` | `label` | 10m | Yes: mode() for occurrence year. Pre-2015: ESA proxy with class remapping. |
| `sbtn_natural_land` | `WRI/SBTN/naturalLands/v1_1/2020` | `natural` | 10m | Static (2020) |

### 14.6 Hydrology (5 features)

| Feature | GEE Asset ID | Band | Resolution |
|---------|-------------|------|-----------|
| `water_occurrence` | `JRC/GSW1_4/GlobalSurfaceWater` | `occurrence` | 30m |
| `water_recurrence` | (same) | `recurrence` | 30m |
| `water_seasonality` | (same) | `seasonality` | 30m |
| `merit_hand_m` | `MERIT/Hydro/v1_0_1` | `hnd` | 90m |
| `merit_upstream_area_km2` | (same) | `upa` | 90m |

### 14.7 Vegetation Structure & Biomass (4 features)

| Feature | GEE Asset ID | Band | Resolution | Temporal? |
|---------|-------------|------|-----------|-----------|
| `gedi_canopy_height_m` | `LARSE/GEDI/GRIDDEDVEG_002/V1/1KM` | `p95` | 1km | Static. No coverage >51.6N (ISS orbit). |
| `gedi_foliage_height_div` | (same) | `shan` | 1km | Static. Shannon diversity of height bins. |
| `modis_gpp_mean` | `MODIS/061/MOD17A3HGF` | `Gpp` | 500m | Yes: +/-1yr window around occurrence year. 2000-2023. |
| `biomass_agb_mgha` | `NASA/ORNL/biomass_carbon_density/v1` | `agb` | 300m | Static. |

### 14.8 Human Impact (3 features)

| Feature | GEE Asset ID | Band | Resolution | Temporal? |
|---------|-------------|------|-----------|-----------|
| `human_modification` | `CSP/HM/GlobalHumanModification` | `gHM` | 1km | Static (2016 baseline). |
| `nighttime_lights` | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG` | `avg_rad` | 500m | Yes: annual mean for occurrence year. Pre-2012: 0. |
| `fire_frequency_count` | `MODIS/061/MCD64A1` | `BurnDate` | 500m | Yes: cumulative burn count 2001 to occurrence year. Pre-2001: 0. |

### 14.9 Biogeography (3 features)

| Feature | GEE Asset ID | Band/Property | Resolution |
|---------|-------------|---------------|-----------|
| `eco_id` | `RESOLVE/ECOREGIONS/2017` (FeatureCollection) | `ECO_ID` | Vector (rasterized) |
| `biome_num` | (same) | `BIOME_NUM` | Vector (rasterized) |
| `topo_diversity` | `CSP/ERGo/1_0/Global/SRTM_topoDiversity` | `constant` | 270m |

**Note**: `eco_id` and `biome_num` are categorical identifiers currently fed as continuous values. See Section 11.1 item 6 for limitations.

### 14.10 Temporal Climate (6 features)

| Feature | GEE Asset ID | Band | Resolution | Temporal Logic |
|---------|-------------|------|-----------|----------------|
| `tc_vpd_mean` | `IDAHO_EPSCOR/TERRACLIMATE` | `vpd` | ~4km | +/-2yr window around occurrence year, mean. Range: 1958-2024. |
| `tc_aet_mean` | (same) | `aet` | ~4km | (same) |
| `tc_soil_moisture_mean` | (same) | `soil` | ~4km | (same) |
| `tc_pdsi_mean` | (same) | `pdsi` | ~4km | (same) |
| `tc_water_deficit_mean` | (same) | `def` | ~4km | (same) |
| `tc_solar_rad_mean` | (same) | `srad` | ~4km | (same) |

### 14.11 Datasets NOT Used (Potential Additions)

These GEE datasets exist but are not currently in the pipeline. A reviewer might evaluate whether any would add signal:

| Dataset | GEE Asset ID | What It Provides | Resolution | Why Not Used |
|---------|-------------|-----------------|-----------|-------------|
| WorldClim V2 | `WORLDCLIM/V2/BIO` | Updated bioclim (2.1) | ~1km | V1 already in pipeline; marginal improvement |
| CHELSA | Not on GEE | Higher-accuracy bioclim for mountains | ~1km | Requires external download |
| SoilGrids 2.0 | `projects/soilgrids-isric/*` | Higher-res soil properties | 250m | OpenLandMap already covers soil; SoilGrids has more depth layers |
| Global Aridity Index | `projects/sat-io/open-datasets/global_ai_et0` | Aridity/PET | ~1km | Partially captured by TerraClimate VPD+deficit |
| Global Wind Atlas | Not on GEE | Wind exposure | ~250m | Relevant for exposed ridgelines; requires external |
| Sentinel-1 SAR | `COPERNICUS/S1_GRD` | Canopy structure via radar | 10m | Partially captured by AlphaEarth embedding |
| PALSAR Forest/Non-Forest | `JAXA/ALOS/PALSAR/YEARLY/FNF4` | L-band SAR forest map | 25m | Already have Hansen + JRC forest |
| MODIS EVI/NDVI | `MODIS/061/MOD13A1` | Vegetation greenness | 500m | Partially captured by GPP and AlphaEarth |
| Global Lithology | Not on GEE natively | Bedrock geology | 1:1M | Could add signal for soil-parent-material interaction |
| Köppen-Geiger climate map | Not on GEE natively | Climate zones | ~1km | Already have WorldClim bio vars which encode this |
| Distance to coast | Derived | Continentality proxy | — | Could be derived from DEM/water layers |
| Photoperiod/daylength | Derived from lat | Light regime | — | Could be derived from latitude |

---

## 15. Data Gaps and Improvement Opportunities

### 15.1 Geographic Coverage Gaps

**Problem**: GBIF data is heavily biased toward Europe, North America, and Australia. For context:

- The 20 most-observed species are entirely European or North American (see Section 13.3)
- 8,816 species (20%) have exactly 1 training sample — effectively unlearnable
- Tropical tree diversity represents >50% of global species but likely <20% of our training data

**Impact**: The model will systematically underperform in:
- Sub-Saharan Africa (esp. Congo Basin, West Africa)
- Southeast Asia (Indonesia, Myanmar, Laos, Cambodia)
- Amazonia and Cerrado
- Central Asia and the Himalayas

**Potential mitigations**:
- Supplement with regional herbarium digitization projects
- Use species range maps (IUCN, BGCI) as weak labels for locations within known ranges
- Pseudo-labeling from high-confidence predictions in data-sparse regions
- Transfer learning from well-sampled sister taxa to rare species

### 15.2 Temporal Coverage Gaps

- AlphaEarth embeddings only cover 2017-2024
- GBIF observations span 1700-2024
- ~30% of occurrences predate 2000, getting modern satellite embeddings for historical observations
- Dynamic World only available from 2015; pre-2015 uses ESA WorldCover as static proxy
- VIIRS nightlights only from 2012; pre-2012 get constant 0
- MODIS fire only from 2001; pre-2001 get constant 0

**Impact**: Historical observations in areas with significant land-use change (deforestation, urbanization) receive environmental features that don't match what the tree actually experienced.

### 15.3 Feature Resolution Mismatch

The 59 environmental features span 4 orders of magnitude in resolution:

| Resolution | Features | Count |
|-----------|----------|-------|
| 10m | JRC forest type, ESA WorldCover, Dynamic World, SBTN | 4 |
| 30m | Terrain (4), Hansen (2), JRC TMF (2), JRC Water (3) | 11 |
| 90m | MERIT Hydro (2) | 2 |
| 250m | OpenLandMap soil (7), topo_diversity | 8 |
| 300m | Biomass AGB | 1 |
| 500m | MODIS GPP, VIIRS lights, MODIS fire | 3 |
| 1km | WorldClim (19), GEDI (2), human modification | 22 |
| 4km | TerraClimate (6) | 6 |
| Vector | Ecoregions (2) | 2 |

The coarsest features (TerraClimate at 4km, WorldClim at 1km) cover the same 4km patch for many 10m pixels. This is inherent to the available global datasets and cannot be "fixed" — but a reviewer might identify finer-resolution alternatives.

### 15.4 Missing Feature Categories

Categories not represented in the current 59 features that could carry biological signal:

1. **Photoperiod/daylength**: Derivable from latitude. Key driver of phenology for temperate species.
2. **Distance to coast**: Continentality strongly influences species distribution (maritime vs. continental climate).
3. **Bedrock geology/lithology**: Parent material drives soil chemistry beyond what OpenLandMap surface properties capture.
4. **Frost frequency/growing degree days**: WorldClim bio06 captures minimum temperature but not frost event frequency.
5. **Wind exposure**: Important for exposed ridgeline and coastal species.
6. **Nitrogen deposition**: Affects nutrient cycling and competitive dynamics.
7. **Functional trait priors**: Using species traits (leaf type, growth form, deciduousness) as auxiliary model inputs, not just labels. This could enable few-shot generalization for rare species.

### 15.5 The 2.9% Missing Environmental Data

3.2% of embeddings (325,548 rows) still lack environmental data. These fall into:
- Pixels over open ocean (misplaced GBIF coordinates)
- Small islands with no DEM/soil coverage
- Edge pixels at dataset boundaries

This is acceptable coverage at 97.1% but represents a non-random data loss (island and coastal species may be disproportionately affected).

---

## 16. AlphaEarth Satellite Embeddings: Details

### 16.1 What AlphaEarth Is

AlphaEarth (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`) is Google's satellite foundation model, available on Google Earth Engine. It processes Sentinel-2 multispectral imagery (10 bands: B2-B8A, B11-B12) into a 64-dimensional embedding per 10m pixel.

The embedding captures high-level scene semantics:
- Land cover type (forest, crop, water, urban, bare)
- Vegetation structure (height, density, canopy closure)
- Phenology (growth cycles, seasonal variation)
- Surface composition (soil color, moisture, geology)
- Spatial texture (homogeneous plantation vs. mixed natural forest)

### 16.2 How Embeddings Are Stored

- **PostgreSQL table**: `species_occurrence_embeddings`
- **Column**: `embedding vector(64)` using pgvector extension
- **Index**: HNSW (Hierarchical Navigable Small World) with `vector_cosine_ops`, `m=16`, `ef_construction=200`
- **Total embeddings**: 11,396,890

### 16.3 How Embeddings Are Sampled

AlphaEarth embeddings are NOT sampled through the GEE environmental pipeline. They were collected in two phases:

1. **V4 Direct** (2.4M pixels): Queried directly from AlphaEarth ImageCollection on GEE, using GBIF coordinates rounded to 4 decimal places. Annual composite for the year closest to the GBIF observation.
2. **Phase C Regime 2** (4.7M pixels): Additional pixels for species with >50 occurrences but <50 embedded occurrences. Backfill campaign to improve coverage.

The environmental features (59 variables) are sampled in a separate pipeline (`temporal_env_sampler.py`) and stored in `pixel_environmental_bands`. The two tables are joined at training time via `(round(lat, 4), round(lon, 4), year)`.

### 16.4 Multi-Year Fallback

At inference time, the `/sample` endpoint tries multiple AlphaEarth years: [2023, 2022, 2021, 2020, 2019, 2018, 2017]. It returns the first year with valid data. This handles the ~3% of locations where the most recent year has cloud/shadow masking artifacts.

---

## 17. File Reference

### 17.1 Core Files

| File | Purpose |
|------|---------|
| `orchestrator/train_sinr_model.py` | SINR training pipeline (extract, train, evaluate) |
| `orchestrator/temporal_env_sampler.py` | GEE environmental data extraction with year-matching |
| `orchestrator/backfill_env_from_bigquery.py` | BQ-to-PG env data loader |
| `orchestrator/location_predictor_FIXED.py` | Python microservice (GEE sampling, will host SINR inference) |
| `treekipedia/backend/routes/prediction.js` | Node.js k-NN prediction system (2,073 lines) |

### 17.2 Model Artifacts (produced by training)

| File | Purpose |
|------|---------|
| `orchestrator/sinr_model/best_model.pt` | Best model checkpoint (~47 MB) |
| `orchestrator/sinr_model/latest_checkpoint.pt` | Latest epoch checkpoint |
| `orchestrator/sinr_model/normalize_stats.npz` | Feature normalization (mean/std per feature) |
| `orchestrator/sinr_model/training_history.json` | Per-epoch metrics |
| `orchestrator/sinr_training_data/train.parquet` | Training data (1.36 GB) |
| `orchestrator/sinr_training_data/val.parquet` | Validation data (0.07 GB) |
| `orchestrator/sinr_training_data/species_mapping.json` | taxon_id <-> index mapping |

---

## 18. Questions for the Reviewer

1. Is the assumed-negative BCE loss the right choice here, or would a different formulation (e.g., positive-unlabeled learning, focal loss) be better suited to presence-only biodiversity data?

2. The model uses eco_id and biome_num as continuous features. Should these be one-hot encoded or embedded as learned entity embeddings? What about other categorical features (soil_texture_class, esa_worldcover_2021)?

3. SINR originally uses sinusoidal spatial encoding of latitude/longitude. We omit this because the environmental features implicitly encode location. Would adding explicit spatial encoding help or hurt?

4. The training shows val_loss plateauing at epoch 6 while top-10 accuracy continues improving. Should we optimize for a ranking metric (e.g., MRR, NDCG) instead of BCE loss?

5. With 26,118 species having fewer than 10 samples, what strategies would best handle this extreme long-tail distribution? Data augmentation? Few-shot learning? Species trait-based priors?

6. We use a single global pos_weight=2048. Would per-species adaptive weighting improve performance, particularly for rare species?

7. The background sampling currently draws random locations from the training set. Would geographically-structured negative sampling (e.g., same biome, nearby pixels) produce better discrimination?

8. Are there additional environmental datasets or feature engineering approaches that would significantly improve species prediction accuracy?

9. For the managed forest / plantation use case, should we train a separate model or add "planted vs. native" as an output head?

10. What validation methodology would be most appropriate for assessing this model's real-world utility? Spatial block cross-validation? Expert ground-truthing? Comparison to IUCN range maps?
