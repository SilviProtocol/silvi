# Pre-AlphaEarth Triangulation Pipeline
## Expanding Species Centroid Coverage from 17,924 to 48,129 Species

**Version**: 1.0
**Date**: February 10, 2026
**Status**: ARCHITECTURE DESIGN — Ready for implementation
**Priority**: HIGH — This is the single highest-impact improvement to prediction quality

---

## 1. The Problem

### The Gap
| Metric | Count |
|--------|-------|
| Species with occurrence data (geohash tiles) | 48,129 |
| Species with AlphaEarth centroids (can be predicted) | 17,924 |
| **Gap: species that exist in the landscape but can't be predicted** | **30,205** |
| Species with no occurrence data at all | 19,614 |

The 30,205 missing species have known locations from GBIF but were never sampled against AlphaEarth because:
- Their occurrences are pre-2017 (AlphaEarth V1/ANNUAL starts 2017)
- They were in locations where AlphaEarth had no coverage
- They weren't included in the original sampling batches

### Why This Matters
P. radiata at Auckland NZ demonstrates the problem: even with multi-signal scoring, a species needs at least ONE signal source to appear in predictions. Species without centroids get zero embedding signal. The spatial channel helps, but adding embedding data for 30K more species would dramatically improve predictions globally.

---

## 2. The Core Challenge: Temporal Mismatch & Disturbance

### The Naive Approach (Insufficient)
"Just sample current AlphaEarth at historical occurrence locations."

This fails because:
- A 1995 occurrence of *Shorea robusta* in Borneo might now be an oil palm plantation
- A 2005 occurrence of *Picea abies* in Central Europe might now be a bark-beetle-cleared area
- The current satellite signature at a disturbed location tells you about the *disturbance*, not the species' habitat preference

### The Three Temporal Regimes

```
REGIME 1: UNDISTURBED (2017+)                    → AlphaEarth directly
REGIME 2: UNDISTURBED (pre-2017)                  → AlphaEarth now (habitat stability assumption)
REGIME 3: DISTURBED (any era)                     → Must triangulate from other data
```

**Regime 1** is trivial — sample AlphaEarth at the occurrence location for the observation year.

**Regime 2** relies on the habitat stability assumption for trees: if a forest was present in 1995 and is still present today, the fundamental habitat characteristics (soil, climate, elevation, forest structure) are largely unchanged. This is sound for mature forest sites.

**Regime 3** is the hard problem. If the forest has been cleared, burned, or converted, the current satellite signature is useless for characterizing the *original* habitat.

---

## 3. Disturbance Detection Strategy

### Available Indicators

| Indicator | Source | Resolution | Temporal | What It Tells Us |
|-----------|--------|-----------|----------|-----------------|
| `treecover2000` | Hansen GFC | 30m | Static (year 2000 baseline) | Was there forest at baseline? |
| `lossyear` | Hansen GFC | 30m | 2001-2024 | When was forest lost? |
| `loss` | Hansen GFC | 30m | 2001-2024 | Was forest lost at all? |
| `gain` | Hansen GFC | 30m | 2000-2012 only | Did forest regrow? |
| Global Human Modification | CSP/HM | 1km | ~2016 static | Human pressure level |
| Dynamic World | Google/S2 | 10m | 2015-present | Current land cover class |
| ESA WorldCover | ESA | 10m | 2020, 2021 | Land cover class |
| MODIS Burned Area | MCD64A1 | 500m | 2000-present | Fire history |

### Decision Tree for Each Occurrence Point

```
FOR EACH OCCURRENCE (species, lat, lon, year):
│
├── Step 1: Check Hansen treecover2000
│   ├── treecover2000 >= 25%  →  Was forested at baseline
│   │   ├── loss == 0  →  UNDISTURBED → Regime 1 or 2
│   │   ├── loss == 1 AND lossyear > occurrence_year
│   │   │   →  Forest was intact when species was observed
│   │   │   →  But DISTURBED NOW → Regime 3
│   │   └── loss == 1 AND lossyear <= occurrence_year
│   │       →  Species observed AFTER disturbance (weird but possible)
│   │       →  Treat as potentially disturbed habitat
│   └── treecover2000 < 25%  →  Non-forest or sparse canopy
│       →  Could still be valid (savanna species, shrublands)
│       →  Check if current land cover matches expectations
│
├── Step 2: Route to appropriate embedding strategy
│   ├── UNDISTURBED, 2017+ → AlphaEarth direct (Regime 1)
│   ├── UNDISTURBED, pre-2017 → AlphaEarth now (Regime 2)
│   └── DISTURBED → Triangulation needed (Regime 3)
│
└── Step 3: For Regime 3, find proxy embedding
    ├── Strategy A: Nearest undisturbed neighbor
    ├── Strategy B: Historical spectral feature vector
    └── Strategy C: Foundation model on historical imagery
```

---

## 4. Embedding Strategies by Regime

### Strategy 1: AlphaEarth Direct (Regime 1 — Undisturbed, 2017+)

**Input**: Occurrences where `loss == 0` AND `occurrence_year >= 2017`
**Method**: Sample AlphaEarth V1/ANNUAL at (lat, lon, year)
**Output**: 64-D embedding vector
**Estimated volume**: ~40% of the 30,205 gap species will have some occurrences in this regime
**Infrastructure**: Adapt `extract_alphaearth_occurrences_v2.py` for batch processing
**GEE cost**: Low — same as v4 extraction

### Strategy 2: AlphaEarth Proxy (Regime 2 — Undisturbed, pre-2017)

**Input**: Occurrences where `loss == 0` AND `occurrence_year < 2017`
**Method**: Sample AlphaEarth V1/ANNUAL at (lat, lon, most_recent_available_year)
**Assumption**: Trees are long-lived; undisturbed forest at (lat, lon) in 1995 has similar structural/spectral properties in 2017
**Validation**: Compare with Regime 1 embeddings for same species where both are available
**Output**: 64-D embedding vector (with `proxy=true` flag and `proxy_year_gap` metadata)
**Estimated volume**: ~35% of the gap
**Infrastructure**: Same as Strategy 1, just with year override

### Strategy 3: Nearest Undisturbed Neighbor (Regime 3 — Disturbed)

**Input**: Occurrences where `loss == 1` (site is now disturbed)
**Method**:
1. Search within a radius (starting 1km, expanding to 5km, then 10km) for pixels where:
   - `treecover2000 >= 25%`
   - `loss == 0`
   - Same elevation band (±200m)
   - Same ecoregion (from our 847 ecoregion polygons)
2. Sample AlphaEarth at the nearest qualifying undisturbed pixel
3. Weight by proximity — closer neighbors are more representative

**Assumption**: Within the same ecoregion + elevation band, nearby undisturbed forest has similar species composition. The disturbed pixel's *potential natural vegetation* is best approximated by its nearest surviving analog.

**Output**: 64-D embedding vector (with `proxy=true`, `proxy_type=nearest_undisturbed`, `proxy_distance_m` metadata)
**Estimated volume**: ~15% of the gap
**Infrastructure**: New GEE-based search function needed (doable with `reduceNeighborhood` or iterative buffer sampling)

### Strategy 4: Historical Spectral Feature Vector (Regime 3 — Disturbed, fallback)

**Input**: Occurrences where Strategy 3 fails (no undisturbed neighbor within 10km)
**Method**: Build a **45-50 feature habitat characterization vector** from historical satellite data:

**Time-Matched Spectral (from Landsat composite of occurrence year):**
```
NDVI, EVI, SAVI, NBR, NDMI                    (5 spectral indices)
Blue, Green, Red, NIR, SWIR1, SWIR2            (6 surface reflectance bands)
```

**Phenological (from MODIS, 2000+ or nearest year):**
```
Annual mean NDVI, max NDVI, NDVI amplitude, mean EVI  (4 phenological metrics)
```

**Forest Structure (from Hansen, static):**
```
treecover2000, lossyear                         (2 values)
```

**Climate (from WorldClim BIO, static):**
```
BIO1-BIO19 (all 19 bioclimatic variables)       (19 values)
```

**Soil (from OpenLandMap, static):**
```
Organic carbon, pH, clay%, sand%, silt%, bulk density at 0-30cm  (6 values)
```

**Topographic (from SRTM, static):**
```
Elevation, slope, aspect                         (3 values)
```

**Total**: ~45 features per point

**This is NOT an AlphaEarth embedding.** It's a different feature space. Two approaches to make it compatible:

**Option A: Train a projection layer** — Use the ~1M points from v4 (which have BOTH AlphaEarth embeddings AND these features) to train a simple neural net that maps 45 features → 64-D AlphaEarth-like embedding. This is a **learned spectral-to-embedding translator**.

**Option B: Keep as a parallel feature space** — Store these as a second type of centroid (`feature_type = 'spectral_historical'`). When predicting, match against both AlphaEarth centroids and spectral centroids, with appropriate weighting.

**Option A is strongly preferred** — it keeps everything in the same 64-D space and is straightforward to implement.

### Strategy 5: Foundation Model Embeddings (Regime 3 — Future Enhancement)

**Status**: NOT recommended for initial implementation. Reserved for Phase 2.

**Why not now?**
1. No foundation model was trained on pre-2013 Landsat data — out-of-distribution inference
2. Clay v1.5 is the most promising but untested on Landsat 5/7
3. All require local/cloud GPU infrastructure (not on GEE)
4. The "learned projection" from Strategy 4 may perform just as well with far less complexity

**Future potential**: If Strategy 4's projection layer shows poor quality, we can:
1. Fine-tune Clay v1.5 on a labeled set of Landsat 5/7 → AlphaEarth embedding pairs
2. Use Prithvi-EO-2.0-TL for 2013+ HLS data (superior to raw Landsat composites)
3. Build a temporal ensemble: Clay for pre-2013, Prithvi for 2013-2016, AlphaEarth for 2017+

**Key insight**: These models produce per-patch (~240-480m footprint) embeddings, not per-pixel. For species occurrence points, this is actually fine — a 240m footprint around an observation is a reasonable habitat characterization window.

---

## 5. Implementation Architecture

### Phase 1: Inventory & Classification (1-2 days)

Classify every occurrence point in `geohash_species_tiles` for the 30,205 gap species:

```sql
-- For each gap species, extract occurrence locations from geohash tiles
-- Join with Hansen forest change data to classify disturbance status
-- Output: occurrence_classification table with:
--   taxon_id, lat, lon, geohash, occurrence_year (estimated),
--   treecover2000, lossyear, loss, gain, regime (1/2/3)
```

**Challenge**: `geohash_species_tiles` stores L7 geohash centroids, not exact lat/lon of original GBIF observations. Each tile covers ~150m × 150m. The centroid is a reasonable proxy.

**Occurrence year estimation**: The `species_data` JSONB column may contain occurrence counts but likely not individual observation years. For geohash tiles, we may need to assign a representative year range based on the data import metadata. If year data isn't available, assume pre-2017 (conservative) and rely on Hansen disturbance detection.

### Phase 2: Batch AlphaEarth Sampling (3-5 days of GEE processing)

**Infrastructure**: Adapt `extract_alphaearth_occurrences_v2.py`

```
Input:  Classified occurrence points from Phase 1
        (Regime 1 + Regime 2 points only — skip Regime 3 for now)

Process:
  1. Upload occurrence FeatureCollections to GEE as assets (batch of 100K points)
  2. For each year (2017-2024), sample AlphaEarth at Regime 1 points for that year
  3. For Regime 2 points, sample AlphaEarth at most recent available year (2023/2024)
  4. Export to Cloud Storage → download as parquet
  5. Checkpoint every 1000 species

Output: Parquet files with (taxon_id, lat, lon, emb_year, proxy_year_gap, A00-A63)

GEE Budget:
  - ~1.2M points for Regime 1+2 (estimated 75% of ~50 points × 30K species)
  - Batch tasks: ~40 (year-grouped) + ~20 (overflow chunks)
  - With 2 concurrent tasks: ~3-5 days
  - Can request quota increase to 10 concurrent tasks → ~1-2 days
```

### Phase 3: Nearest Undisturbed Neighbor (1-2 days)

**For Regime 3 points (~300K points estimated):**

```python
# For each disturbed occurrence:
#   1. Create a 10km buffer
#   2. Within buffer, find pixels where:
#      - treecover2000 >= 25 AND loss == 0
#      - elevation within ±200m of occurrence
#   3. Sample AlphaEarth at the nearest qualifying pixel
#   4. Record proxy distance

# GEE implementation:
#   - Use ee.Image.neighborhoodToBands() with kernel
#   - Or: buffer → reduceRegion → find nearest valid pixel
#   - This is more compute-intensive than direct sampling
```

**Fallback**: If no undisturbed neighbor within 10km, mark for Strategy 4.

### Phase 4: Historical Spectral Feature Extraction (5-8 days)

**For Regime 3 fallback points + as validation data for all points:**

```
Extract at ALL ~1.5M occurrence points:
  - Landsat annual composite (NDVI, EVI, SAVI, NBR, NDMI, 6 SR bands)
    → 40 annual composites, grouped by year
  - MODIS annual NDVI/EVI statistics (mean, max, amplitude)
    → 25 annual composites (2000-2024)
  - WorldClim BIO (19 variables, static)
    → 1 task
  - OpenLandMap Soil (6 properties, static)
    → 5 tasks
  - SRTM elevation + slope + aspect
    → 1 task
  - Hansen (treecover2000, lossyear)
    → 1 task (likely already have from Phase 1)

Total GEE tasks: ~82
Estimated time: 5-8 days with 2 concurrent tasks
```

### Phase 5: Train Spectral-to-AlphaEarth Projection (1-2 days)

**Training data**: The ~3.37M rows in v4 parquet (which have AlphaEarth embeddings) × the spectral features extracted in Phase 4 for the SAME points.

```python
# Architecture: Simple MLP
# Input: 45 spectral/climate/soil/topo features
# Output: 64-D AlphaEarth-like embedding
# Loss: Cosine similarity loss (not MSE — we care about direction, not magnitude)
# 
# Training: 80/20 split, validate by checking that projected embeddings
#           recover the same species clusters as true AlphaEarth embeddings
#
# This is essentially a "spectral barcode to habitat signature translator"

model = nn.Sequential(
    nn.Linear(45, 256),
    nn.ReLU(),
    nn.LayerNorm(256),
    nn.Linear(256, 128),
    nn.ReLU(),
    nn.LayerNorm(128),
    nn.Linear(128, 64),
    nn.Tanh()  # AlphaEarth embeddings are roughly in [-0.3, 0.3]
)
```

**Validation metric**: For known species in v4, compare:
- True AlphaEarth centroid vs. projected centroid
- If cosine similarity > 0.8, the projection is useful
- If < 0.5, the projection adds noise and should be de-weighted

### Phase 6: Clustering & Loading (1 day)

**Run `run_clustering_v4.py`** on the new embeddings:
- Same k-means clustering with density weighting
- Same deduplication logic
- Checkpoint-aware (skips the existing 17,924 species)
- Load new centroids to `species_habitat_centroids`
- Rebuild IVFFlat index

**Expected output**: ~30,000 additional species × ~2.5 centroids average = ~75,000 new centroid rows

---

## 6. Foundation Model Strategy (Phase 2 — Future)

### When to Pursue
- After Phase 1-6 are complete and we've assessed Strategy 4 projection quality
- If projection quality is poor (cosine sim < 0.6), Clay v1.5 becomes the path forward

### Clay v1.5 Integration Plan

**Why Clay is the best candidate:**
1. Wavelength-parameterized input — can accept Landsat 5/7 TM band wavelengths
2. No year encoding — only week/hour, so no temporal extrapolation problem
3. GSD as input — handles multi-resolution naturally
4. 1024-D embeddings (richer than AlphaEarth's 64-D)
5. Apache-2.0 license, pip-installable

**Infrastructure needed:**
- GPU instance (L4 or A10G, ~24GB VRAM)
- Download Landsat 5/7/8 scenes for occurrence locations from GEE
- Preprocess to Clay's input format (256×256 chips with metadata)
- Run batch inference
- Train a 1024-D → 64-D dimensionality reduction to align with AlphaEarth space

**Validation approach:**
- For points where we have BOTH AlphaEarth AND Clay embeddings (2017+ undisturbed)
- Compare species clustering quality: which embedding space produces tighter, more ecologically meaningful clusters?
- If Clay is superior, consider migrating the entire system to Clay embeddings

### Prithvi-EO-2.0 for 2013-2016

For the 2013-2016 gap (between Landsat 8 launch and AlphaEarth start):
- Prithvi-EO-2.0-600M-TL is the best model (trained on HLS which starts 2013)
- Location + time-aware embeddings
- Clean TerraTorch API for embedding extraction
- Could fill the 4-year gap with high confidence

---

## 7. Climate Signal Enhancement (Parallel Workstream)

### Can be done simultaneously with Phases 1-6

The spectral features extracted in Phase 4 also serve the climate scoring enhancement:

**For the real-time predictor (location_predictor_FIXED.py):**
1. Add WorldClim BIO sampling at query point (19 variables, static image)
2. Add OpenLandMap soil sampling (6 properties)
3. Pass these through to the scoring engine

**For the scoring engine (prediction.js):**
1. Currently: climate signal = elevation match only
2. Enhanced: climate signal = elevation + precipitation + temperature + soil
3. Species climate envelopes are partially in the `species` table (`annual_precipitation_mm`, `annual_temperature_range_c`, `ph_prefered`, `soil_texture_prefered`)

**Estimated effort**: 1 day for Python service, 1 day for scoring integration
**Impact**: Better accuracy for the existing 17,924 species, immediately

---

## 8. Timeline & Dependencies

```
Week 1:  Phase 1 (Inventory) + Climate Enhancement (parallel)
         ├── Classify 30,205 species × occurrences into regimes
         └── Add WorldClim + soil sampling to Python service

Week 2:  Phase 2 (AlphaEarth batch sampling)
         ├── Upload occurrence points to GEE
         ├── Start batch extraction tasks
         └── ~60 GEE tasks running

Week 3:  Phase 2 continues + Phase 3 (Nearest Neighbor)
         ├── AlphaEarth sampling completes
         ├── Start nearest-undisturbed-neighbor search
         └── Begin Phase 4 (spectral features) for static layers

Week 4:  Phase 4 (Historical spectral extraction) + Phase 5 (Projection)
         ├── Landsat annual composites extraction
         ├── MODIS phenological features
         ├── Train spectral-to-AlphaEarth projection model
         └── Validate projection quality

Week 5:  Phase 6 (Clustering & Loading)
         ├── Run clustering on all new embeddings
         ├── Load to PostgreSQL
         ├── Rebuild IVFFlat index
         └── End-to-end testing at 10 global locations

Week 6:  Validation & Tuning
         ├── Compare prediction quality before/after expansion
         ├── P. radiata should now have embedding signal too
         ├── Document results
         └── If projection quality < threshold, plan Clay Phase 2
```

---

## 9. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| GEE rate limits block batch extraction | Timeline slips 2x | Request quota increase for research; parallelize across multiple GCP projects |
| AlphaEarth has gaps in key regions (tropics, remote areas) | Lower coverage than expected | Measure actual hit rate in Phase 2; use spectral features as fallback |
| Habitat stability assumption fails (forest changed character but wasn't "lost") | Noisy embeddings for Regime 2 | Validate by comparing Regime 1 vs Regime 2 cluster quality per species |
| Spectral-to-AlphaEarth projection is poor quality | Regime 3 species get bad centroids | Use cosine similarity threshold; only load projections above 0.7; fall back to spatial-only scoring |
| Geohash tile centroids are too coarse (~150m) | Location imprecision | Use geohash centroid as-is; 150m error is within AlphaEarth mosaic pixel footprint |
| Occurrence year data unavailable for geohash tiles | Can't distinguish Regime 1/2 | Conservative approach: treat all pre-2017 as Regime 2; only flag disturbed sites |

---

## 10. Success Metrics

| Metric | Before | Target | Stretch |
|--------|--------|--------|---------|
| Species with centroids | 17,924 | 40,000+ | 48,129 (all with occurrences) |
| Prediction coverage (any signal) | ~48,129 (spatial only for 30K) | 48,129 (spatial + embedding) | — |
| P. radiata @ Auckland NZ rank | #42 | Top 30 | Top 20 |
| Embedding signal for top-50 species | ~35% have embedding | 70% have embedding | 90%+ |
| Projection quality (cosine sim) | N/A | > 0.7 | > 0.85 |

---

## 11. Files & Infrastructure

### Existing Code to Adapt
| File | Purpose | Adaptation Needed |
|------|---------|------------------|
| `orchestrator/extract_alphaearth_occurrences_v2.py` | Batch AlphaEarth sampling | Add regime classification, year override for Regime 2 |
| `orchestrator/extract_disturbance_landuse.py` | Hansen + environmental extraction | Template for Phase 4 spectral extraction |
| `orchestrator/run_clustering_v4.py` | Per-species clustering | Run as-is on new embeddings (checkpoint-aware) |
| `orchestrator/location_predictor_FIXED.py` | Real-time GEE sampling | Add WorldClim + soil sampling for climate enhancement |
| `treekipedia/backend/routes/prediction.js` | Scoring engine | Update climate signal to use precipitation/temperature/soil |

### New Code to Write
| Component | Description | Estimated Lines |
|-----------|-------------|----------------|
| `orchestrator/classify_occurrences.py` | Phase 1: Classify occurrences into regimes | ~300 |
| `orchestrator/batch_alphaearth_gap.py` | Phase 2: Batch AlphaEarth for gap species | ~400 (adapting v2 script) |
| `orchestrator/nearest_undisturbed.py` | Phase 3: Find nearest undisturbed neighbor | ~250 |
| `orchestrator/extract_spectral_features.py` | Phase 4: Historical spectral + climate + soil | ~500 |
| `orchestrator/train_spectral_projection.py` | Phase 5: Train MLP for spectral→embedding | ~200 |

### Data Products
| Output | Format | Size Estimate |
|--------|--------|--------------|
| Occurrence classification | Parquet | ~200 MB |
| New AlphaEarth embeddings (Regime 1+2) | Parquet | ~500 MB |
| Nearest-neighbor proxy embeddings (Regime 3) | Parquet | ~100 MB |
| Spectral feature vectors (all points) | Parquet | ~2 GB |
| Trained projection model | PyTorch checkpoint | ~5 MB |
| New centroids (30K species) | CSV → PostgreSQL | ~100 MB |

---

## 12. Decision Record

### Why Not Pure Foundation Models Right Now?
1. **No model handles pre-2013 Landsat reliably.** Prithvi trained on HLS (2013+). Clay trained on Landsat 8/9 (2013+). Feeding them Landsat 5 TM (1984-2012) is out-of-distribution.
2. **GPU infrastructure not available.** All models require local/cloud GPU, not GEE. Adding this infrastructure is a separate project.
3. **The projection approach may work just as well.** We have 3.37M rows of paired (spectral features, AlphaEarth embedding) training data — a supervised learning problem with massive data.

### Why Not Just Spatial-Only Scoring?
Species with only spatial signal (no embedding) max out at ~85% suitability due to the zero embedding component. Adding even approximate embeddings brings them into the 90%+ range and dramatically improves ranking among species that share the same spatial footprint.

### Why the 3-Regime Architecture?
A single strategy would either:
- Waste AlphaEarth sampling on disturbed sites (getting plantation/urban embeddings)
- Throw away valid undisturbed pre-2017 sites that could use AlphaEarth
- Require foundation model GPU for all sites (expensive, uncertain quality)

The 3-regime approach uses the highest-fidelity data available for each situation.
