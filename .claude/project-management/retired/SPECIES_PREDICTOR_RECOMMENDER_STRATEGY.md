# Species Predictor & Recommender: Master Strategy

**Date**: January 19, 2026 (Updated)
**Status**: Phase 1 GEE Processing IN PROGRESS (39% complete)
**Author**: Claude Code + Djimo

---

## Executive Summary

This document outlines a comprehensive strategy for building two distinct but related systems:

### Species Predictor
**Question**: "What trees ARE here, or WERE here before deforestation?"

This is a **reconstruction tool** - given a location, predict what species naturally occur(red) there based on environmental similarity to known occurrences. The predictor works backward in time as far as data allows.

### Species Recommender
**Question**: "What trees SHOULD I plant here for restoration?"

This builds ON TOP of the predictor but adds ecological intelligence:
- May recommend **pioneer species first** (for shade/soil prep)
- May recommend **soil-building species** for degraded farmland
- May recommend **invasive removal** before planting
- Considers restoration **strategy** (rewilding vs agroforestry vs carbon)
- These nuances will be added iteratively; **the predictor is the foundation**

### The Core Challenge

Handle any location, going back as far as data allows with confidence scores:

| Era | Data Source | Confidence |
|-----|-------------|------------|
| 2017-2024 | AlphaEarth embeddings (64-D, 10m) | HIGH |
| 2000-2017 | Landsat 7/8 + cross-calibration to AlphaEarth | MEDIUM-HIGH |
| 1985-2000 | Landsat 5 TM + cross-calibration | MEDIUM |
| 1972-1985 | Landsat 1-5 MSS + cross-calibration | MEDIUM-LOW |
| Pre-1972 | Pollen records, PNV maps, climate analogues | LOW |

---

## Part 1: Current System Analysis

### What We Have Built

| Component | Status | Details |
|-----------|--------|---------|
| **AlphaEarth GEE Sampling** | ✅ Working | Point-based, 64-D embeddings, 2017-2024 |
| **Species Centroids** | ✅ 500 species | K-means clustered, 5 habitats per species |
| **Cosine Similarity** | ✅ Working | Full 64-D in PostgreSQL |
| **Frontend Modal** | ✅ Working | Click-to-predict, top 10 results |
| **BigQuery Pipeline** | 🔄 IN PROGRESS | 2.1M+ embeddings being processed |
| **Polygon/AOI Support** | ❌ Not implemented | Currently point-only |
| **Historical Analysis** | ❌ Not implemented | No temporal dimension |
| **Recommender Weights** | ❌ Not implemented | No native/LEAF integration |

### Current Architecture (POC - 500 species)

```
User Click (lat, lon)
       ↓
GEE Service (port 5002)
  → Sample AlphaEarth at point
  → Return 64-D embedding
       ↓
Backend API (port 5001)
  → Cosine similarity vs 500 centroids
  → Weighted confidence calculation
       ↓
Frontend Modal
  → Display top 10 predictions
```

### Scale-Up Architecture (IN PROGRESS - 6,775 species)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BIGQUERY EMBEDDING PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: GEE Batch Processing (39% complete)                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │ Parquet     │ →  │ GEE Tasks   │ →  │ BigQuery    │                     │
│  │ 16.5M pts   │    │ 2000 pts/ea │    │ Tables      │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│                                              │                               │
│  Tables:                                     │                               │
│  - occ_embeddings_hansen_v2 (1.5M, no elev) │                               │
│  - occ_embeddings_hansen_elev_v3 (building) │                               │
│  - occ_elevation_backfill (1.5M, elev only) │                               │
│                                              ▼                               │
│  PHASE 2: Aggregation                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ BigQuery SQL: GROUP BY taxon_id → species_embedding_centroids      │   │
│  │ - Mean embedding per species                                        │   │
│  │ - OR k-means clustering (5 habitats/species)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                              │                               │
│                                              ▼                               │
│  PHASE 3: PostgreSQL Load                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ species_alphaearth_centroids table (replace 500 → 6,775 species)   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Limitations (Being Addressed)

1. **Point-only**: No polygon/AOI support (future phase)
2. **Present-only**: No historical analysis (2017-2024 only)
3. **No land cover awareness**: Doesn't know if area is forested
4. **No recommender logic**: Predictor ≠ Recommender → Building "Species Aptness Score"
5. ~~**100 species**~~: Scaling to 6,775 species via BigQuery pipeline

---

## Part 2: Foundation Model Landscape

### Available Geospatial Foundation Models

| Model | Provider | Resolution | Temporal | Bands | Embeddings | Best For |
|-------|----------|------------|----------|-------|------------|----------|
| **[AlphaEarth](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)** | Google/DeepMind | 10m | 2017-2024 | 64-D | Annual | Current conditions |
| **[Clay v1.5](https://clay-foundation.github.io/model/)** | Dev Seed | 10m | 2018-present | 768-D | On-demand | Flexible, open |
| **[Prithvi-EO-2.0](https://research.ibm.com/blog/prithvi2-geospatial)** | NASA/IBM | 30m | Multi-temporal | 600M params | On-demand | Change detection |
| **[SatCLIP](https://arxiv.org/abs/2311.17179)** | Microsoft | Variable | 2021-2023 | Location | Pretrained | Location-only tasks |

### Temporal Coverage Comparison (CORRECTED)

```
                    1972  1985  2000  2017  2024
                     │     │     │     │     │
Landsat MSS ─────────┴─────┤                      (60m, 4 bands, GREEN/RED/NIR)
Landsat TM        ────────┴─────────────────────  (30m, 7 bands)
Landsat ETM+                    ├───────────────  (30m, 8 bands, SLC-off 2003+)
Landsat OLI                           ├─────────  (30m, 11 bands, 2013+)
Sentinel-2                            ├─────────  (10m, 13 bands, 2015+)
AlphaEarth                            ├─────────  (10m, 64-D, 2017+)
HLS (Harmonized)                      ├─────────  (30m, unified, 2013+)
Prithvi (trained on HLS)              ├─────────  (30m, multi-temporal)
Clay                                  ├─────────  (10m, 768-D, 2018+)
```

**IMPORTANT CORRECTION**: Prithvi is trained on HLS which starts in 2013, NOT able to go back to 1985 directly. For pre-2013 data, we need different approaches.

---

## Part 2a: Answering Key Technical Questions

### Q1: Is Prithvi Free/Open Source?

**YES** - [Prithvi-EO-2.0](https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-600M) is released under **Apache-2.0 license**:
- Free for commercial use
- Available on Hugging Face: `ibm-nasa-geospatial/Prithvi-EO-2.0-300M` and `Prithvi-EO-2.0-600M`
- Includes fine-tuned versions with temporal/location awareness (`-TL` variants)
- Code available at [github.com/NASA-IMPACT/Prithvi-EO-2.0](https://github.com/NASA-IMPACT/Prithvi-EO-2.0)

### Q2: Early Landsat Data (1972-1984) - Availability and APIs

**YES, fully available and FREE** via multiple sources:

| Source | Coverage | API | Notes |
|--------|----------|-----|-------|
| [Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/landsat-mss) | 1972-2012 | GEE Python/JS API | `LANDSAT/LM01_C02_T2` through `LM05` |
| [USGS EarthExplorer](https://earthexplorer.usgs.gov/) | 1972-present | REST API | Bulk download, free registration |
| [Google Cloud Storage](https://cloud.google.com/storage/docs/public-datasets/landsat/) | 1972-present | Cloud API | Public bucket, no registration |
| [AWS Open Data](https://registry.opendata.aws/usgs-landsat/) | 1982-present | S3 API | Landsat Collection 2 |

**GEE MSS Collections**:
- `LANDSAT/LM01_C02_T2` - Landsat 1 MSS (July 1972 - January 1978)
- `LANDSAT/LM02_C02_T2` - Landsat 2 MSS (January 1975 - February 1982)
- `LANDSAT/LM03_C02_T2` - Landsat 3 MSS (March 1978 - March 1983)
- `LANDSAT/LM04_C02_T2` - Landsat 4 MSS (August 1982 - December 1993)
- `LANDSAT/LM05_C02_T2` - Landsat 5 MSS (January 1984 - May 2012)

### Q3: How to Detect Forest Transition Year Algorithmically

The [Hansen Global Forest Change dataset](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12) provides exactly this:

```javascript
// GEE Code to get forest loss year
var hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12');
var lossYear = hansen.select('lossyear');  // 0 = no loss, 1-24 = year (2001-2024)
var treecover2000 = hansen.select('treecover2000');  // % canopy cover in 2000

// For a point
var point = ee.Geometry.Point([lon, lat]);
var yearLost = lossYear.reduceRegion({
  reducer: ee.Reducer.first(),
  geometry: point,
  scale: 30
});
// Returns: {lossyear: 15} meaning forest lost in 2015
```

**For pre-2000 deforestation**, we need to:
1. Check if `treecover2000 > 0` → Was forested in 2000
2. If `treecover2000 = 0` → Need to go back further using Landsat archive

**Multi-Tier Detection Algorithm**:
```python
def detect_forest_history(lat, lon):
    """
    Detect when forest existed at this location.
    Returns: (was_forested, forest_year_range, confidence)
    """
    # Tier 1: Hansen dataset (2000-2024)
    hansen = get_hansen_data(lat, lon)
    if hansen['treecover2000'] > 25:  # Was forested in 2000
        if hansen['lossyear'] > 0:
            return (True, (2000, 2000 + hansen['lossyear']), 'HIGH')
        else:
            return (True, (2000, 2024), 'HIGH')  # Still forested

    # Tier 2: Landsat TM/ETM+ archive (1985-2000)
    for year in range(2000, 1984, -1):
        ndvi = get_landsat_ndvi(lat, lon, year)
        if ndvi > 0.4:  # Forest threshold
            return (True, (year, year), 'MEDIUM')

    # Tier 3: Landsat MSS archive (1972-1985)
    for year in range(1985, 1971, -1):
        ndvi = get_mss_ndvi(lat, lon, year)  # Limited spectral bands
        if ndvi > 0.35:  # Lower threshold for MSS
            return (True, (year, year), 'MEDIUM-LOW')

    # Tier 4: No satellite evidence of forest
    # Check PNV/biome data
    pnv = get_potential_natural_vegetation(lat, lon)
    if pnv in ['tropical_forest', 'temperate_forest', 'boreal_forest']:
        return (True, ('pre-1972', 'unknown'), 'LOW')

    return (False, None, 'HIGH')  # Likely never forested
```

### Q4: Cross-Sensor Calibration Techniques

**Your intuition about multi-tier calibration is exactly right.** Here's the established science:

#### MSS → TM Calibration (Already Done by USGS)
As of April 2011, USGS applied [updated absolute radiometric calibration](https://www.usgs.gov/landsat-missions/landsat-1-5-multispectral-scanner-mss-calibration-notices) tying all Landsat sensors to a consistent radiometric scale. This reduces cross-sensor differences from ~16% to ~5%.

#### The Multi-Tier Calibration Approach You Suggested

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMBEDDING TRANSFER CHAIN                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MSS (1972-1985)  →  TM (1985-2012)  →  OLI/HLS (2013+)  →  AlphaEarth     │
│     4 bands            7 bands           11 bands            64-D           │
│     60m                30m               30m                 10m            │
│         ↓                  ↓                 ↓                              │
│    Calibrated         Calibrated       Harmonized         TARGET           │
│    to TM              to OLI           (HLS ready)                         │
│                                                                              │
│  Method: Find PROXY TILES that have data in BOTH eras                       │
│  - Intact forest that existed in 1975 AND exists in 2024                   │
│  - Same ecoregion, similar elevation                                        │
│  - Build transfer function from overlapping observations                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Per-Request Calibration Strategy (Your Idea)

**YES, this is the right approach.** For each AOI request:

```python
def calibrate_historical_to_alphaearth(aoi, historical_year):
    """
    Build a transfer function from historical data to AlphaEarth embedding space
    using nearby proxy tiles that have data in BOTH eras.
    """
    # Step 1: Find proxy tiles within 50-100km
    proxy_candidates = find_tiles_with_continuous_forest(
        near=aoi,
        radius_km=100,
        same_ecoregion=True,
        same_biome=True,
        elevation_tolerance_m=500
    )

    # Step 2: Get historical spectral signature for each proxy
    proxy_historical = []
    proxy_current_ae = []

    for proxy in proxy_candidates:
        # Get historical Landsat data (MSS or TM)
        hist_bands = get_landsat(proxy, historical_year)

        # Get current AlphaEarth embedding
        current_ae = get_alphaearth(proxy, 2024)

        if hist_bands and current_ae:
            proxy_historical.append(hist_bands)
            proxy_current_ae.append(current_ae)

    # Step 3: Build transfer model
    # Option A: Simple linear regression per AE dimension
    # Option B: Neural network (if enough proxies)
    # Option C: Weighted average of proxy AE embeddings

    if len(proxy_historical) >= 10:
        # Enough data for regression
        transfer_model = train_spectral_to_ae_model(
            X=proxy_historical,  # Shape: (n_proxies, n_bands)
            y=proxy_current_ae   # Shape: (n_proxies, 64)
        )
        return transfer_model

    else:
        # Fallback: weighted average of proxy AE embeddings
        # Weight by spectral similarity to target AOI
        aoi_historical = get_landsat(aoi, historical_year)
        weights = [spectral_similarity(aoi_historical, ph) for ph in proxy_historical]
        weighted_ae = np.average(proxy_current_ae, weights=weights, axis=0)
        return weighted_ae
```

#### Key Insight: MSS Has Limited Bands

Landsat MSS only has 4 bands (Green, Red, 2× NIR) at 60m resolution:
- Cannot directly compute all indices that TM/OLI can
- BUT: NDVI-equivalent can be computed (NIR - Red) / (NIR + Red)
- Key research shows [NDVI transformation models](https://www.sciencedirect.com/science/article/abs/pii/S0034425709000169) can reduce MSS-TM differences by ~10%

### Q5: Why Everything Must Map to AlphaEarth Embeddings

**You're absolutely right** - since our species centroids are in AlphaEarth embedding space (64-D), ALL historical data must ultimately be translated to that space for cosine similarity to work.

**Two Approaches**:

#### Approach A: Direct Transfer (Historical → AlphaEarth)
```
Historical Landsat → [Transfer Model] → Pseudo-AlphaEarth Embedding → Cosine Similarity
```
- Requires training transfer model per era/sensor
- Higher accuracy if good proxy tiles exist
- Per-request calibration using local proxies

#### Approach B: Environmental Proxy (Indirect)
```
Historical Landsat → Forest Type Classification → Find Similar Current Forests → Sample AlphaEarth There
```
- More robust when direct transfer is poor
- Uses ecological knowledge as bridge
- Example: "This was Atlantic Forest in 1980" → Find current Atlantic Forest with AlphaEarth → Use those embeddings

---

## Part 3: The Three Scenarios

### Scenario 1: Currently Forested Areas (Easiest)

**Condition**: AlphaEarth embedding shows forest signature

**Method**:
```
1. Sample AlphaEarth at AOI (polygon mean or grid)
2. Detect land cover class from embedding
3. If forest → direct cosine similarity to species centroids
4. Apply recommender weights:
   - Native status (×2.0 boost)
   - LEAF score (0-100)
   - Ecosystem continuity
   - Soil/climate compatibility
```

**Data Sources**:
- AlphaEarth (2017-2024)
- Species occurrence centroids
- WCVP native/introduced data
- Geohash occurrence tiles

**Confidence**: HIGH (direct embedding match)

---

### Scenario 2: Recently Deforested (1985-2017)

**Condition**: Current embedding shows non-forest, but Landsat archive shows historical forest

**Method**:
```
1. Sample AlphaEarth at AOI → non-forest signature
2. Query historical Landsat/HLS archive (1985-2017)
3. Find forest transition year (when forest disappeared)
4. Extract embedding from forest period using:
   a. Prithvi-EO-2.0 on HLS data
   b. OR find nearby still-forested "proxy" tiles
   c. OR use cross-sensor transfer learning
5. Map historical embedding to AlphaEarth space
6. Proceed with cosine similarity + recommender weights
```

**Data Sources**:
- Landsat 5/7/8 archive (1985-present)
- Harmonized Landsat-Sentinel (HLS)
- Prithvi-EO-2.0 embeddings
- Global Forest Watch (forest change year)

**Cross-Reference Strategy**:
```
FOR tiles in AOI:
  historical_rgb = get_landsat(tile, forest_year)

  # Find nearby tiles with both historical AND current data
  proxy_tiles = find_tiles_with_current_forest(
    within_km=50,
    same_ecoregion=True,
    similar_elevation=True
  )

  # Build transfer function
  FOR proxy in proxy_tiles:
    proxy_historical_rgb = get_landsat(proxy, forest_year)
    proxy_current_ae = get_alphaearth(proxy, 2024)

    # Learn RGB → AlphaEarth mapping
    transfer_model.fit(proxy_historical_rgb, proxy_current_ae)

  # Apply to target
  predicted_ae = transfer_model.predict(historical_rgb)
```

**Confidence**: MEDIUM (depends on proxy quality and transfer accuracy)

---

### Scenario 3: Pre-Satellite Deforestation (Before 1972/1985)

**Condition**: No satellite record of forest, but ecological evidence suggests historical forest

**Method**:
```
1. Determine if area EVER had forest:
   a. Potential Natural Vegetation (PNV) maps
   b. Paleoecological records (pollen cores)
   c. Historical documents/maps
   d. Soil characteristics (forest soils persist)
   e. Biome classification + climate envelope

2. If PNV indicates forest potential:
   a. Find analogous CURRENTLY FORESTED reference sites
   b. Match by: climate, soil, elevation, biome, ecoregion
   c. Sample AlphaEarth at reference sites
   d. Use weighted average of reference embeddings

3. Apply recommender weights with EXTRA caution:
   - Lower confidence scores
   - Emphasize pioneer/early successional species
   - Consider rewilding vs. assisted regeneration
```

**Data Sources**:
- [NOAA Historical Land-Cover Change Dataset](https://catalog.data.gov/dataset/historical-land-cover-change-and-land-use-conversions-global-dataset2) (1765-present reconstruction)
- WWF Ecoregions + Biome classification
- FAO Soil Maps
- Climate analogues (present-day locations with matching climate)

**Confidence**: LOW (ecological inference, not direct observation)

---

## Part 4: Species Aptness Score (Filter-First Model)

**Key Insight**: Computing cosine similarity against 6,775+ species is expensive. Most species are irrelevant for any given location. Use filters to reduce candidates BEFORE embedding comparison.

### The Filter-First Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SPECIES APTNESS SCORE PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT: (lat, lon) click on map                                             │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FILTER 1: NATIVE STATUS (WCVP)                              DYNAMIC │   │
│  │ "Which species are native to this country/region?"                   │   │
│  │ → Madagascar: ~3,000 native species                                 │   │
│  │ → Germany: ~400 native tree species                                 │   │
│  │ → Brazil: ~8,000+ native species                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FILTER 2: OCCURRENCE DATA (geohash presence)                DYNAMIC │   │
│  │ "Which native species have occurrence records in this region?"      │   │
│  │ → Species with at least 1 geohash tile within ~100km               │   │
│  │ → High-biodiversity areas: 500-2,000 species                       │   │
│  │ → Low-biodiversity areas: 20-100 species                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FILTER 3: EMBEDDING AVAILABILITY                            DYNAMIC │   │
│  │ "Do we have AlphaEarth embeddings for this species?"                │   │
│  │ → Only species in species_alphaearth_centroids                      │   │
│  │ → Returns ALL matching species (no arbitrary cutoff)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ SCORE: COSINE SIMILARITY (AlphaEarth)                       ALL     │   │
│  │ "How similar is clicked location to species' known habitats?"       │   │
│  │ → Compute similarity for ALL filtered candidates                   │   │
│  │ → Return ALL with aptness scores, sorted by score                  │   │
│  │ → Frontend can paginate/filter (e.g., show top 20, threshold >0.5) │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         ↓                                                                    │
│  OUTPUT: [{taxon_id, score, native_status, leaf_percentile, similarity}]   │
│          Count varies by location: 20 to 2,000+ species                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Filter-First?

The number of candidates varies dramatically by location:

| Location Type | Example | Native Species | After Filters |
|---------------|---------|----------------|---------------|
| Tropical hotspot | Atlantic Forest, Brazil | ~8,000 | 500-2,000 |
| Island endemic | Madagascar highlands | ~3,000 | 200-800 |
| Temperate forest | Germany | ~400 | 50-150 |
| Arid region | Sahel | ~200 | 20-80 |

**Benefits of dynamic filtering**:
- Returns ecologically meaningful results (all relevant species, not arbitrary top-N)
- Tropical biodiversity hotspots return more species (as expected)
- Depauperate regions return fewer (accurate)
- Frontend handles display limits via pagination/thresholds

### Aptness Score Formula

```python
def get_candidate_species(click_location):
    """
    Apply filters to get ecologically relevant candidates.
    Returns VARIABLE number based on actual biodiversity at location.
    """
    # Filter 1: Native to this country/region
    natives = get_native_species(click_location.country)  # Could be 200 to 8,000+

    # Filter 2: Has occurrence data in this area
    with_occurrences = [s for s in natives
                        if has_nearby_occurrences(s, click_location, radius_km=100)]

    # Filter 3: Has AlphaEarth embedding
    with_embeddings = [s for s in with_occurrences
                       if s.taxon_id in species_alphaearth_centroids]

    return with_embeddings  # Dynamic count: 20 to 2,000+ depending on location


def calculate_aptness_score(species, click_embedding, click_location):
    """
    Aptness = weighted combination of ecological relevance factors.
    Higher = more appropriate for restoration at this location.
    """
    # Get pre-computed values
    native_status = get_wcvp_native_status(species, click_location.country)
    occurrence_density = get_occurrence_density(species, click_location.geohash)
    cosine_sim = cosine_similarity(click_embedding, species.centroid)

    # Weights (tunable)
    W_NATIVE = 0.25   # Native status importance
    W_OCCUR = 0.25    # Occurrence density importance
    W_EMBED = 0.50    # Environmental similarity importance (primary signal)

    # Native status: 1.0 if native, 0.5 if unknown, 0.0 if introduced
    native_score = {
        'native': 1.0,
        'unknown': 0.5,
        'introduced': 0.0  # Should already be filtered out
    }.get(native_status, 0.5)

    # Occurrence density: log-scaled to handle wide variation
    occur_score = min(1.0, log10(occurrence_density + 1) / 3.0)

    # Cosine similarity: already 0-1
    embed_score = cosine_sim

    # Combined aptness score
    aptness = (W_NATIVE * native_score +
               W_OCCUR * occur_score +
               W_EMBED * embed_score)

    return {
        'taxon_id': species.taxon_id,
        'aptness_score': aptness,
        'breakdown': {
            'native_status': native_status,
            'native_score': native_score,
            'occurrence_density': occurrence_density,
            'embedding_similarity': embed_score
        }
    }


def get_aptness_results(click_location, click_embedding):
    """
    Main entry point: returns ALL relevant species with scores.
    Frontend handles display limits.
    """
    candidates = get_candidate_species(click_location)

    results = [calculate_aptness_score(s, click_embedding, click_location)
               for s in candidates]

    # Sort by aptness score, return ALL
    return sorted(results, key=lambda x: x['aptness_score'], reverse=True)
```

### Implementation Plan

1. **Create `aptness_score.py`** in orchestrator/
2. **Add `/aptness` endpoint** to location_predictor service
   - Returns all candidates with scores
   - Optional `?min_score=0.5` query param for filtering
   - Optional `?limit=20` for pagination
3. **Update frontend modal** to use aptness scores
   - Show total count: "Found 347 suitable species"
   - Default display: top 20
   - "Show more" button for full list
4. **Add breakdown display** showing why species ranked high

---

## Part 4b: Species Predictor vs Recommender (Original)

### Predictor: "What CAN survive here?"

Pure habitat matching based on environmental similarity:
```python
def predict_species(embedding, limit=10):
    """Find species whose known habitats match this embedding."""
    similarities = cosine_similarity(embedding, all_centroids)
    return top_k(similarities, k=limit)
```

### Recommender: "What SHOULD I plant here?"

Predictor + ecological/strategic weights:
```python
def recommend_species(embedding, polygon, strategy='rewilding', limit=10):
    """Recommend species considering multiple factors."""

    # Base: habitat match
    predictions = predict_species(embedding, limit=100)

    # Apply recommender weights
    for species in predictions:
        score = species.similarity_score

        # 1. Native status (from WCVP)
        if is_native(species, polygon.country):
            score *= 2.0  # Strong boost
        elif is_introduced_invasive(species, polygon.country):
            score = 0  # Exclude entirely

        # 2. LEAF score (occurrence density + native status)
        leaf = get_leaf_score(species, polygon.geohash)
        score *= (1 + leaf / 100)  # 0-2x boost

        # 3. Ecosystem continuity
        # Prefer species found in adjacent intact forest
        if found_in_nearby_forest(species, polygon, radius_km=50):
            score *= 1.5

        # 4. Strategy-specific weights
        if strategy == 'rewilding':
            score *= rewilding_weight(species)  # Favor ecological function
        elif strategy == 'agroforestry':
            score *= agroforestry_weight(species)  # Favor productive species
        elif strategy == 'carbon':
            score *= carbon_weight(species)  # Favor fast-growing

        # 5. Soil/climate compatibility
        soil_match = soil_compatibility(species, polygon)
        climate_match = climate_compatibility(species, polygon)
        score *= (soil_match * climate_match)

        species.recommendation_score = score

    return sorted(predictions, key=lambda s: s.recommendation_score)[:limit]
```

### Weight Factors Summary

| Factor | Weight Range | Data Source | Notes |
|--------|--------------|-------------|-------|
| Habitat similarity | 0.0-1.0 | AlphaEarth cosine | Base score |
| Native status | 0-2.0× | WCVP | Introduced = 0, Native = 2× |
| LEAF score | 1.0-2.0× | Occurrence data | Percentile 0-100 |
| Ecosystem proximity | 1.0-1.5× | Nearby forest analysis | Within 50km |
| Strategy alignment | 0.5-2.0× | Species traits | Rewilding/agroforestry/carbon |
| Soil compatibility | 0.0-1.0 | V11 soil fields | pH, texture match |
| Climate compatibility | 0.0-1.0 | V11 climate fields | Köppen-Geiger match |

---

## Part 5: Technical Architecture

### Proposed System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SPECIES RECOMMENDER SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    USER INTERFACE (Frontend)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Draw Polygon│  │Upload KML/  │  │  Strategy   │  │  Results    │  │   │
│  │  │   on Map    │  │  GeoJSON    │  │  Selector   │  │  Display    │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │   │
│  └─────────┼────────────────┼────────────────┼────────────────┼─────────┘   │
│            └────────────────┴────────────────┴────────────────┘              │
│                                      │                                       │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATION LAYER (New Service)                  │   │
│  │                                                                        │   │
│  │  1. Receive polygon + strategy                                        │   │
│  │  2. Determine AOI characteristics:                                    │   │
│  │     - Current land cover (forest/non-forest)                         │   │
│  │     - Historical forest status                                        │   │
│  │     - Ecoregion, biome, climate zone                                 │   │
│  │  3. Route to appropriate scenario handler                            │   │
│  │  4. Aggregate results + apply recommender weights                    │   │
│  │  5. Return ranked species list                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                          │           │           │                          │
│            ┌─────────────┴───┐   ┌───┴───────────┴───┐                      │
│            ▼                 ▼   ▼                   ▼                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐                │
│  │   SCENARIO 1    │ │   SCENARIO 2    │ │   SCENARIO 3    │                │
│  │   Currently     │ │   Recently      │ │   Pre-Satellite │                │
│  │   Forested      │ │   Deforested    │ │   Historical    │                │
│  │                 │ │   (1985-2017)   │ │   (pre-1972)    │                │
│  │  AlphaEarth     │ │  Landsat/HLS +  │ │  PNV + Climate  │                │
│  │  Direct Match   │ │  Transfer Model │ │  Analogues      │                │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘                │
│           │                   │                   │                         │
│           └───────────────────┴───────────────────┘                         │
│                               │                                             │
│                               ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA SERVICES LAYER                                │   │
│  │                                                                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  AlphaEarth │  │  Prithvi/   │  │  PostgreSQL │  │    WCVP     │  │   │
│  │  │    (GEE)    │  │    Clay     │  │  + PostGIS  │  │   + LEAF    │  │   │
│  │  │  2017-2024  │  │  1985-2024  │  │  Centroids  │  │   Weights   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New API Endpoints

```
POST /api/recommend
{
  "polygon": { GeoJSON },
  "strategy": "rewilding" | "agroforestry" | "carbon" | "riparian",
  "limit": 20,
  "include_introduced": false,
  "min_confidence": 0.5
}

Response:
{
  "scenario": "currently_forested" | "recently_deforested" | "historical",
  "confidence_level": "high" | "medium" | "low",
  "aoi_analysis": {
    "area_km2": 12.5,
    "current_cover": "grassland",
    "historical_forest_year": 1992,
    "ecoregion": "Atlantic Forest",
    "biome": "Tropical Moist Broadleaf"
  },
  "recommendations": [
    {
      "taxon_id": "...",
      "species_scientific_name": "Araucaria angustifolia",
      "common_name": "Paraná Pine",
      "recommendation_score": 0.89,
      "breakdown": {
        "habitat_similarity": 0.78,
        "native_boost": 2.0,
        "leaf_score": 85,
        "ecosystem_proximity": 1.3,
        "strategy_alignment": 1.2
      },
      "confidence": 0.85,
      "rationale": "Native to Atlantic Forest, high occurrence density, found in nearby intact forest"
    }
  ]
}
```

---

## Part 6: Implementation Roadmap

### Phase 1: Polygon Support + Current Forest (4 weeks)

**Goal**: Enable AOI-based predictions for currently forested areas

**Tasks**:
1. Add polygon sampling to GEE service
   - `POST /sample-polygon` endpoint
   - Mean embedding aggregation
   - Area limits (< 100 km²)
2. Add land cover detection
   - Classify embedding as forest/non-forest
   - Use AlphaEarth embedding patterns
3. Add polygon drawing to frontend
   - Leaflet.draw integration
   - KML/GeoJSON upload
4. Scale species centroids
   - Process next 1,000 species
   - Optimize similarity search (pgvector?)

**Deliverable**: Working polygon predictor for forested areas

---

### Phase 2: Recommender Weights (3 weeks)

**Goal**: Add ecological intelligence to predictions

**Tasks**:
1. Implement LEAF scoring integration
   - Query LEAF endpoint for each prediction
   - Apply native status weights
2. Add strategy selector
   - UI for rewilding/agroforestry/carbon
   - Strategy-specific weight functions
3. Add ecosystem proximity analysis
   - Find nearby intact forest
   - Boost species found in proximity
4. Add soil/climate compatibility
   - Use V11 species data
   - Match against AOI characteristics

**Deliverable**: Full recommender with weighted results

---

### Phase 3: Historical Analysis - Recent (6 weeks)

**Goal**: Handle recently deforested areas (1985-2017)

**Tasks**:
1. Integrate Global Forest Watch
   - Detect forest loss year per tile
   - Classify AOI as "recently deforested"
2. Set up Prithvi-EO-2.0 or Clay
   - Deploy model for historical embedding extraction
   - Process HLS archive for target areas
3. Build transfer learning pipeline
   - Find proxy tiles (current forest with historical data)
   - Train RGB → AlphaEarth mapping
4. Implement scenario routing
   - Auto-detect scenario based on land cover analysis
   - Route to appropriate handler

**Deliverable**: Historical analysis for post-1985 deforestation

---

### Phase 4: Ecological Reconstruction (4 weeks)

**Goal**: Handle pre-satellite historical areas

**Tasks**:
1. Integrate PNV/biome data
   - WWF Ecoregions layer
   - Potential Natural Vegetation maps
2. Build climate analogue finder
   - Find currently forested areas with matching climate
   - Use as reference embeddings
3. Add confidence degradation
   - Lower scores for inferred data
   - Clear UI indication of uncertainty
4. Historical land cover integration
   - NOAA reconstruction data
   - Soil-based forest indicators

**Deliverable**: Full three-scenario system

---

### Phase 5: Scale & Optimize (Ongoing)

**Tasks**:
1. Scale to 10,000+ species
2. Pre-compute embeddings for common AOIs
3. Add caching layer (Redis/geohash tiles)
4. Implement async job queue for large polygons
5. Build validation framework
6. Documentation and methodology paper

---

## Part 7: Data Requirements

### Immediate Needs (Phase 1-2)

| Data | Status | Action |
|------|--------|--------|
| AlphaEarth embeddings | ✅ 100 species | Scale to 1,000+ |
| WCVP native/introduced | ✅ 99.99% coverage | Integrate into recommender |
| LEAF scoring | ✅ Endpoint exists | Connect to recommender |
| Species traits (V11) | ✅ 133 columns | Use for strategy weights |
| Soil data | ✅ V11 fields | Match to AOI |

### Future Needs (Phase 3-4)

| Data | Status | Action |
|------|--------|--------|
| Global Forest Watch | ❌ Not integrated | Add forest loss year layer |
| HLS Archive access | ❌ Need setup | Register with NASA Earthdata |
| Prithvi-EO-2.0 | ❌ Not deployed | Deploy model or use API |
| WWF Ecoregions | ⚠️ Partial | Full integration needed |
| PNV maps | ❌ Not available | Source from literature |
| NOAA historical | ❌ Not integrated | Download and integrate |

---

## Part 8: Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GEE rate limits | Medium | High | Implement caching, batch processing |
| Prithvi deployment complexity | High | Medium | Consider Clay as alternative |
| Transfer learning accuracy | Medium | Medium | Validate on known sites |
| Large polygon timeouts | High | Medium | Implement async jobs, area limits |
| Cross-sensor domain gap | Medium | High | Use HLS harmonized data |

### Data Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Species centroid coverage | Medium | High | Prioritize high-value species |
| Historical data gaps | High | Medium | Multiple fallback scenarios |
| PNV map availability | Medium | Low | Use biome/climate as proxy |

### Scientific Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Overfitting to training data | Medium | High | Validation framework |
| Ecological oversimplification | Medium | Medium | Expert review, clear caveats |
| Climate change invalidation | Low | Medium | Include future climate projections |

---

## Part 9: Success Metrics

### Phase 1-2 Success Criteria

- [ ] Polygon predictions work for areas < 100 km²
- [ ] Response time < 60 seconds for forested areas
- [ ] Recommender weights improve expert-rated relevance by >20%
- [ ] 1,000+ species with embeddings

### Phase 3-4 Success Criteria

- [ ] Historical analysis works for post-1985 deforested areas
- [ ] Pre-satellite inference produces reasonable results
- [ ] Clear confidence indicators in UI
- [ ] Validation against known restoration sites

### Long-term Success Criteria

- [ ] 10,000+ species coverage
- [ ] Validated in at least 3 biomes
- [ ] Published methodology paper
- [ ] Used by external organizations

---

## References

### Foundation Models
- [Google AlphaEarth Documentation](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
- [AlphaEarth Foundations Blog](https://deepmind.google/blog/alphaearth-foundations-helps-map-our-planet-in-unprecedented-detail/)
- [Clay Foundation Model](https://clay-foundation.github.io/model/)
- [Prithvi-EO-2.0 (NASA/IBM)](https://research.ibm.com/blog/prithvi2-geospatial)
- [SatCLIP (Microsoft)](https://arxiv.org/abs/2311.17179)

### Cross-Sensor Adaptation
- [Harmonized Landsat-Sentinel Data](https://www.researchgate.net/publication/328488378_The_Harmonized_Landsat_and_Sentinel-2_surface_reflectance_data_set)
- [Domain Adaptation for Satellite Imagery](https://arxiv.org/abs/2006.05923)

### Historical Data
- [Landsat Archive (NASA)](https://landsat.gsfc.nasa.gov/data/)
- [Global Forest Watch](https://www.globalforestwatch.org/)
- [NOAA Historical Land-Cover Dataset](https://catalog.data.gov/dataset/historical-land-cover-change-and-land-use-conversions-global-dataset2)

### Species Distribution Modeling
- [Machine Learning for Ecological Niche Modeling](https://link.springer.com/chapter/10.1007/978-3-319-96978-7_6)
- [OpenForest ML Catalog](https://www.cambridge.org/core/journals/environmental-data-science/article/openforest-a-data-catalog-for-machine-learning-in-forest-monitoring/F62FBEADFF8E3A10C6EDA789D7D180C6)

---

*This document represents the strategic vision for the Species Predictor/Recommender system. Implementation details will be refined as development progresses.*
