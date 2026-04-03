# Treekipedia Species Intelligence: The v3 Model
## From Static Knowledge to Neural Habitat Prediction

**February 2026**

---

## The Journey at a Glance

```
  2025                          2026
  Sept     Oct      Jan         Feb                    Mar+
   |        |        |           |                       |
   v        v        v           v                       v

 [v0.1]   [v1]     [v2]       [v3 k-NN]              [v3 SINR]
  Text   Single    Multi     Individual              Neural Net
  Only  Centroid  Centroid   Occurrence              35,561 spp
         100 spp   500 spp   22,603 spp             9.7M params
                  + SAFE-B   + IDF + MFP            + Gated Fusion
                              11.4M points           top-10: 59.3%

  "What     "Which    "Score     "Match against       "Learn the
   do we     habitat    species    every individual     mapping from
   know?"    looks      across     observation          habitat to
             similar?"  5 axes"    ever recorded"       species"
```

---

## Phase 0: The Knowledge Graph (Sept 2025)

Before any prediction existed, Treekipedia was a **species encyclopedia** — 67,743 records across 115 columns of structured knowledge.

### The Dual-Source Schema

Every researchable field exists in two versions:

```
                    ┌─────────────────────────────────────┐
                    │         SPECIES TABLE                │
                    │         67,743 records               │
                    │         115 columns                  │
                    ├─────────────────────────────────────┤
                    │                                     │
                    │  ┌────────────┐  ┌────────────┐    │
                    │  │ habitat_ai │  │habitat_human│    │
                    │  │  (GPT-4)   │  │ (expert)    │    │
                    │  │  blue UI   │  │  green UI   │    │  ← Display precedence:
                    │  └────────────┘  └────────────┘    │    human > AI > legacy
                    │                                     │
                    │  ×56 field pairs like this          │
                    │                                     │
                    │  + taxonomy (7 cols)                │
                    │  + geography (5 cols)               │
                    │  + conservation (16 pairs)          │
                    │  + physical traits (20 pairs)       │
                    │  + economic/cultural (8 cols)       │
                    │  + soil compatibility (12 cols)     │
                    └─────────────────────────────────────┘
```

### Occurrence Data: Geohash Tiles

Species locations were stored as **geohash tiles** — compressed spatial footprints at ~150m resolution.

```
    GEOHASH LEVEL 7 TILES
    ~~~~~~~~~~~~~~~~~~~~~~
    Each tile ≈ 150m × 150m

    ┌───┬───┬───┬───┐
    │ . │ . │ 3 │ 1 │       species_data (JSONB):
    ├───┼───┼───┼───┤       {
    │ . │ 7 │ 2 │ . │         "GymPiPiPnCx50820-00": 7,
    ├───┼───┼───┼───┤         "AngMaMaQrRb02440-00": 3,
    │ 1 │ 4 │ . │ . │         "AngFaFaMrPl00150-00": 1
    ├───┼───┼───┼───┤       }
    │ . │ . │ . │ . │
    └───┴───┴───┴───┘

    5,786,835 tiles total
    48,129 species covered (71%)
    19,614 species missing (mostly subspecies)
```

**What this gave us:** "Species X has been observed near location Y."
**What this couldn't tell us:** "Is location Y actually suitable habitat for species X?"

---

## Phase 1: Single Centroid (Oct 2025)

### The AlphaEarth Breakthrough

Google's AlphaEarth foundation model encodes any 10m pixel on Earth into a **64-dimensional habitat fingerprint** — capturing canopy structure, phenology, spectral signature, and more, all from satellite imagery.

```
    SATELLITE IMAGERY                    ALPHAEARTH EMBEDDING
    ┌─────────────────┐
    │  ████████████   │
    │  ██  Pixel  ██  │     ──────►     [0.23, -0.87, 0.45, 1.12, ...]
    │  ██  10×10m ██  │                        64 dimensions
    │  ████████████   │
    └─────────────────┘

    Sentinel-2 annual composite         Deterministic per pixel-year:
    All spectral bands                  Same pixel + same year =
    2017-2024 coverage                  IDENTICAL vector regardless
                                        of what species lives there
```

**The key insight:** The embedding describes the **habitat**, not the species. If Pinus radiata and a native podocarp both grow at the same pixel, they get the **exact same** 64-D vector.

### v1 Architecture: One Point Per Species

```
    For each of ~100 species:

    1. Collect all known occurrence locations
    2. Sample AlphaEarth embedding at each location
    3. Average all embeddings into ONE centroid

         Occurrence 1: [0.23, -0.87, ...]  ─┐
         Occurrence 2: [0.31, -0.79, ...]  ─┤
         Occurrence 3: [0.19, -0.91, ...]  ─┼──► MEAN ──► Centroid: [0.24, -0.86, ...]
         Occurrence 4: [0.25, -0.83, ...]  ─┤
         Occurrence 5: [0.22, -0.89, ...]  ─┘

    At query time:

    User clicks (lat, lon)
         │
         ▼
    Sample AlphaEarth at (lat, lon) ──► query_embedding
         │
         ▼
    Cosine similarity vs ALL 100 centroids
         │
         ▼
    Rank by similarity ──► "Top 10 species for this location"
```

### Why It Failed

```
    THE CENTROID AVERAGING PROBLEM
    ──────────────────────────────

    Pinus radiata lives in TWO very different habitats:

    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │     ★ NZ Plantations          ★ AU Dry Sclerophyll  │
    │     (cool, wet, planted)       (warm, dry, natural)  │
    │                                                      │
    │              ⊕ Centroid (NEITHER habitat)            │
    │                                                      │
    │     Cosine similarity                                │
    │     NZ ↔ AU: 0.84                                   │
    │     NZ ↔ Centroid: 0.91                             │
    │     Query ↔ Centroid: 0.72  ← Mediocre match       │
    │                                                      │
    └──────────────────────────────────────────────────────┘

    The average of two distinct habitats matches NEITHER well.

    Worse: No native/introduced filtering meant Quercus robur
    scored just as high in Brazil as in its native Europe.
```

| Metric | Value |
|--------|-------|
| Species covered | ~100 |
| Matching method | Cosine similarity to single mean centroid |
| Context signals | None (pure embedding match) |
| Fatal flaw | Centroid destroys multi-modal distributions |

---

## Phase 2: SAFE-B Multi-Signal Scoring (Jan 2026)

### What Changed

Two major leaps: **multi-centroid clustering** (k-means, 5 centroids per species) and the **SAFE-B scoring framework** — a 5-axis ecological evaluation system.

### The SAFE-B Framework

Instead of relying on embedding similarity alone, every candidate species is now scored across **5 independent ecological dimensions**:

```
                          S P A T I A L
                              │
                             100
                              │
                              │
                 BIOTIC ──────┼────── ABIOTIC
                100           │           100
                              │
                              │
              ECOSYSTEM ──────┼────── FUNCTIONAL
                100                       100

    S = Spatial:    "Is the species found nearby?"         ← geohash tiles
    A = Abiotic:    "Do climate & soil match?"             ← WorldClim, OpenLandMap
    F = Functional: "Does it serve the planting goal?"     ← species traits
    E = Ecosystem:  "Is this the right ecoregion/biome?"   ← WWF ecoregions
    B = Biotic:     "What ecological interactions exist?"   ← GloBI network
```

### Strategy-Based Weighting

Different restoration goals shift the weight balance:

```
    REWILDING           CARBON              AGROFORESTRY        EROSION CONTROL
    ─────────           ──────              ────────────        ───────────────

    S ████░░░░ 20%      S ██░░░░░░ 10%      S ██░░░░░░ 10%      S ███░░░░░ 15%
    A ███░░░░░ 15%      A ████░░░░ 20%      A █████░░░ 25%      A ██████░░ 30%
    F ██░░░░░░ 10%      F ████████ 50%      F ████████ 40%      F ██████░░ 30%
    E ██████░░ 30%      E ███░░░░░ 15%      E ███░░░░░ 15%      E ███░░░░░ 15%
    B █████░░░ 25%      B █░░░░░░░  5%      B ██░░░░░░ 10%      B ██░░░░░░ 10%

    "Restore the        "Maximize            "Productive         "Hold the
     original            sequestration"       & compatible"        soil"
     ecosystem"
```

### Three Discovery Channels

```
    User clicks (lat, lon)
         │
         ├──────────────────────────────────────────────┐
         │                                              │
         ▼                                              │
    ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐
    │  CHANNEL 1  │   │  CHANNEL 2   │   │   CHANNEL 3     │
    │  Embedding  │   │  Spatial     │   │   Biogeographic  │
    │  Match      │   │  Proximity   │   │   Range          │
    ├─────────────┤   ├──────────────┤   ├─────────────────┤
    │             │   │              │   │                 │
    │ Cosine sim  │   │ Geohash tile │   │ WCVP native    │
    │ vs 5 kmeans │   │ density in   │   │ range check    │
    │ centroids   │   │ 50km radius  │   │ + ecoregion    │
    │ per species │   │              │   │ co-occurrence   │
    │             │   │              │   │                 │
    └──────┬──────┘   └──────┬───────┘   └───────┬─────────┘
           │                 │                   │
           └─────────────────┼───────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  SAFE-B SCORER  │
                    │  5-component    │
                    │  weighted sum   │
                    │  per strategy   │
                    └────────┬────────┘
                             │
                             ▼
                    Ranked species list
                    with per-axis breakdown
```

| Metric | Value |
|--------|-------|
| Species covered | 500 → 22,603 (after Phase A+B expansion) |
| Centroids | 49,640 (multi-centroid per species via k-means) |
| Scoring dimensions | 5 (SAFE-B) |
| Strategies | 7 presets (general, rewilding, carbon, agroforestry, ...) |
| New data | WorldClim (19 vars), OpenLandMap soil (4 vars), ecoregions |

---

## Phase 3a: k-NN on Individual Occurrences (Feb 2026)

### The Fundamental Shift

Instead of averaging occurrences into centroids, **keep every single observation** and match against all of them.

```
    v2: CENTROID MATCHING                   v3: k-NN OCCURRENCE MATCHING
    ═══════════════════                     ═══════════════════════════

    5 centroids per species                 EVERY occurrence point retained

    ·  ·  ·                                 ·  ·  ·  ·  ·  ·  ·  ·  ·
    ·  ⊕  ·     ← k-means centroid         ·  ·  ·  ·  ·  ·  ·  ·  ·
    ·  ·  ·                                 ·  ·  ·  ·  ·  ·  ·  ·  ·
                                            ·  ·  ·  ·  ·  ·  ·  ·  ·
           ·  ·                             ·  ·  ·  ·  ·  ·  ·  ·
           ⊕  ·     ← averaged             ·  ·  ·  ·  ·  ·  ·  ·
           ·                                ·  ·  ·  ·  ·  ·  ·

    Information lost:                       Information preserved:
    - Distribution shape                    - Full multi-modal shape
    - Outlier habitats                      - Outlier habitats
    - Relative density                      - Spatial density patterns
                                            - Per-point metadata (elevation,
                                              tree cover, loss year)
```

### Scale of the Data

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │   SPECIES OCCURRENCE EMBEDDINGS TABLE                            │
    │                                                                  │
    │   ████████████████████████████████████████  11,396,890 rows      │
    │                                                                  │
    │   43,992 species   │   64-D embedding per row                   │
    │                    │   + lat, lon, elevation                     │
    │                    │   + treecover, loss, lossyear               │
    │                    │   + density_weight, data_regime             │
    │                                                                  │
    │   Index: HNSW (m=16, ef=200)                                    │
    │   Query time: ~60ms for top-500 nearest neighbors               │
    │   Storage: 1.2 GB                                               │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

### IDF Weighting: Correcting Observation Bias

Common species dominate occurrence databases simply because they're **frequently observed**, not because they're more suitable. IDF (Inverse Document Frequency) corrects this:

```
    IDF_weight = 1 / log(1 + total_occurrences)

    ┌──────────────────┬──────────────┬────────────┬──────────────────┐
    │ Species          │ Occurrences  │ IDF Weight │ Effect           │
    ├──────────────────┼──────────────┼────────────┼──────────────────┤
    │ Quercus robur    │ 50,000       │ 0.092      │ ████░░░░░░ -10x  │
    │ Pinus radiata    │  2,808       │ 0.126      │ █████░░░░░ -4x   │
    │ Rare endemic     │     50       │ 0.255      │ ████████░░ +2.8x │
    │ Very rare        │     10       │ 0.417      │ ██████████ +4.5x │
    └──────────────────┴──────────────┴────────────┴──────────────────┘

    A rare species with 3/10 matching occurrences is FAR more
    informative than a common species with 3/50,000 matching.
```

### How Data Coverage Grew: Three Expansion Phases

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │  GBIF: 96.5 MILLION raw occurrence records, 60,207 species       │
    │                                                                  │
    │  ┌────────────────────────────────────────────────────────────┐  │
    │  │  V4 DIRECT EXTRACTION (2017-2024 observations)            │  │
    │  │  17,924 species  │  3.37M rows  │  99.9% pixel coverage   │  │
    │  │  Filter: year ≥ 2017, coords < 10m uncertainty            │  │
    │  │  Method: Dedupe pixels → sample AlphaEarth → rejoin spp   │  │
    │  └────────────────────────────────────────────────────────────┘  │
    │       │                                                          │
    │       ▼                                                          │
    │  ┌──────────────────┐  ┌──────────────────┐                     │
    │  │ PHASE A: REJOIN  │  │ PHASE B: RECLUSTER│                    │
    │  │ +4,679 species   │  │ Fix 2,257 species │                    │
    │  │ FREE (no GEE)    │  │ FREE (no GEE)     │                    │
    │  │ Shared-pixel join│  │ DBSCAN geographic │                    │
    │  └────────┬─────────┘  └────────┬──────────┘                    │
    │           │                     │                                │
    │           ▼                     ▼                                │
    │  ┌────────────────────────────────────────────────────────────┐  │
    │  │  22,603 species with habitat centroids (pgvector)         │  │
    │  │  49,640 centroids total                                   │  │
    │  └────────────────────────────────────────────────────────────┘  │
    │       │                                                          │
    │       ▼                                                          │
    │  ┌────────────────────────────────────────────────────────────┐  │
    │  │  PHASE C: REGIME 2 SAMPLING (pre-2017 occurrences)        │  │
    │  │  +37,308 species targeted  │  3.96M rows in BigQuery      │  │
    │  │  Assumption: undisturbed pixels ≈ same habitat as when    │  │
    │  │  the species was observed (sample 2017 AlphaEarth)        │  │
    │  └────────────────────────────────────────────────────────────┘  │
    │       │                                                          │
    │       ▼                                                          │
    │  ┌────────────────────────────────────────────────────────────┐  │
    │  │  TARGET: ~59,280 species with embeddings + env features   │  │
    │  │  10-15M rows in k-NN table                                │  │
    │  └────────────────────────────────────────────────────────────┘  │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

### The Long-Tail Problem

Species occurrence data follows an extreme power law:

```
    Occurrences
    per species
         │
    100K ┤ ██
         │ ██
     10K ┤ ██ ██
         │ ██ ██ ██
      1K ┤ ██ ██ ██ ██ ██
         │ ██ ██ ██ ██ ██ ██ ██
     100 ┤ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
         │ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
      10 ┤ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
         │ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
       1 ┤ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
         └──────────────────────────────────────────────────────────────────────
              ◄── common ──────────── species rank ──────────── rare ──►

    Median: 6 occurrences
    60% have < 10 samples
    20% are singletons (1 observation)
    90.3% of data is USDA FIA (US forest inventory)
    Geographic bias: heavy Europe/North America, tropics underrepresented
```

---

## Phase 3b: The SINR Neural Model (Feb 2026)

### Why Go Beyond k-NN?

```
    ┌────────────────────────────┬────────────────────────────────────┐
    │        k-NN                │        Neural Head (SINR)          │
    ├────────────────────────────┼────────────────────────────────────┤
    │ No training needed         │ 30 min/epoch on Apple Silicon      │
    │ Ships immediately          │ Requires training first            │
    │ Works with 1 occurrence    │ Needs >20 per species              │
    │ "These 3 points match"     │ Opaque probabilities               │
    │ Lower accuracy ceiling     │ HIGHER accuracy ceiling            │
    │ One species at a time      │ ALL species in one forward pass    │
    │ Can't learn non-linear     │ Learns complex habitat boundaries  │
    │ relationships              │                                    │
    └────────────────────────────┴────────────────────────────────────┘

    Key realization: The k-NN table IS the training dataset.
    Every row we add improves BOTH systems simultaneously.
```

### The Native vs. Planted Problem

This is the central challenge that drove the SINR architecture:

```
    THE PLANTATION PARADOX
    ══════════════════════

    WAIRARAPA, NEW ZEALAND (-41.15, 175.10)
    ────────────────────────────────────────

    Environmental features say:              Satellite embedding says:
    "Cool temperate rainforest"              "Monoculture conifer plantation"
    → Native podocarps & beeches            → Pinus radiata

    ┌──────────────────────┐     ┌──────────────────────┐
    │  ENVIRONMENT BRANCH  │     │  SATELLITE BRANCH    │
    │                      │     │                      │
    │  Temp: 11°C          │     │  AlphaEarth 64-D:    │
    │  Precip: 1200mm      │     │  Uniform canopy      │
    │  Soil pH: 5.2        │     │  Row patterns         │
    │  Elevation: 120m     │     │  Even-aged stand      │
    │                      │     │                      │
    │  → Dacrycarpus       │     │  → Pinus radiata     │
    │  → Podocarpus        │     │  → Eucalyptus        │
    │  → Nothofagus        │     │  → Plantation spp    │
    └──────────┬───────────┘     └──────────┬───────────┘
               │                            │
               │     WHICH TO TRUST?        │
               └────────────┬───────────────┘
                            │
                            ▼
                    The GATE decides
```

### SINR v2.2 Architecture: Gated Fusion

The breakthrough: a **learned gate** that dynamically decides whether to trust the satellite signal or the environmental features — informed by forest type and native/introduced status.

```
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │   INPUT LAYER (130 features total)                                  │
    │                                                                     │
    │   ┌──────────────┐  ┌──────────────────────────────────────────┐   │
    │   │  AlphaEarth   │  │  Environmental Context                  │   │
    │   │  64-D         │  │                                         │   │
    │   │  satellite    │  │  56 continuous:                         │   │
    │   │  embedding    │  │    19 WorldClim BIO (temp, precip)      │   │
    │   │              │  │     4 soil (pH, clay%, sand%, organic C) │   │
    │   │              │  │     1 elevation                          │   │
    │   │              │  │     ... + terrain, hydrology, NDVI       │   │
    │   │              │  │                                         │   │
    │   │              │  │  5 categorical (entity embeddings):      │   │
    │   │              │  │    JRC forest type   → 3-D embedding    │   │
    │   │              │  │    Xiao plantation   → 3-D embedding    │   │
    │   │              │  │    Ecoregion (850)   → 32-D embedding   │   │
    │   │              │  │    Biome (16)        → 8-D embedding    │   │
    │   │              │  │    Soil texture (14) → 6-D embedding    │   │
    │   │              │  │                                         │   │
    │   │              │  │  1 binary:                              │   │
    │   │              │  │    is_introduced (0 or 1)               │   │
    │   └──────┬───────┘  └──────────────────────┬──────────────────┘   │
    │          │                                  │                      │
    │          │          ┌───────────────────┐   │                      │
    │          │          │    GATE MLP       │   │                      │
    │          │          │                   │   │                      │
    │          │          │  Input: 4-D       │   │                      │
    │          │          │  jrc_emb (3-D)    │   │                      │
    │          │          │  + is_intro (1-D) │   │                      │
    │          │          │        │          │   │                      │
    │          │          │     sigmoid       │   │                      │
    │          │          │        │          │   │                      │
    │          │          │    alpha (α)      │   │                      │
    │          │          │    0 = trust env  │   │                      │
    │          │          │    1 = trust sat  │   │                      │
    │          │          └────────┬──────────┘   │                      │
    │          │                   │              │                      │
    │   ┌──────▼──────────────────▼──────────────▼──────────────────┐   │
    │   │                                                           │   │
    │   │   GATED FUSION:  output = α × satellite + (1-α) × env    │   │
    │   │                                                           │   │
    │   └───────────────────────────┬───────────────────────────────┘   │
    │                               │                                   │
    │   ┌───────────────────────────▼───────────────────────────────┐   │
    │   │                                                           │   │
    │   │   RESIDUAL NETWORK                                        │   │
    │   │                                                           │   │
    │   │   Linear(256) → ReLU                                      │   │
    │   │       │                                                   │   │
    │   │   [ResBlock(256)] × 4                                     │   │
    │   │   Each block:                                             │   │
    │   │     ├── Linear(256) → LayerNorm → ReLU → Dropout         │   │
    │   │     ├── Linear(256)                                       │   │
    │   │     └── + skip connection                                 │   │
    │   │                                                           │   │
    │   └──────────┬────────────────────────────────┬───────────────┘   │
    │              │                                │                   │
    │   ┌──────────▼──────────┐      ┌──────────────▼───────────────┐  │
    │   │   SPECIES HEAD      │      │   AUXILIARY HEAD             │  │
    │   │   Linear(35,561)    │      │   Linear(1) → sigmoid       │  │
    │   │                     │      │   → planted_score            │  │
    │   │   One neuron per    │      │                              │  │
    │   │   species           │◄─────│   PLANTED LOGIT BOOST:      │  │
    │   │                     │      │   logits += planted_score    │  │
    │   │                     │      │     × species_intro_ratio    │  │
    │   │                     │      │     × boost_scale (learned)  │  │
    │   └──────────┬──────────┘      └──────────────────────────────┘  │
    │              │                                                    │
    │              ▼                                                    │
    │   sigmoid → species probabilities (35,561 independent outputs)   │
    │                                                                     │
    │   9,713,042 total parameters                                       │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
```

### How the Gate Works in Practice

```
    SCENARIO 1: Native forest (Wairarapa bush remnant)
    ──────────────────────────────────────────────────
    JRC forest type = "naturally regenerating" (type 1)
    is_introduced = 0

    Gate alpha = 0.353  ← TRUSTS ENVIRONMENT (65%)

    Result: Native podocarps rank HIGH
            P. radiata rank #178 (suppressed)


    SCENARIO 2: Plantation (Wairarapa pine rows)
    ─────────────────────────────────────────────
    JRC forest type = "planted" (type 20)
    is_introduced = 1

    Gate alpha = 0.664  ← TRUSTS SATELLITE (66%)

    Result: P. radiata rank #3 (boosted)
            Native species suppressed


    SCENARIO 3: Misclassified plantation
    ─────────────────────────────────────
    JRC says "naturally regenerating" (WRONG — it's actually a plantation)
    is_introduced = 1

    Gate alpha = 0.845  ← HEAVILY TRUSTS SATELLITE (85%)

    The is_introduced flag OVERRIDES the bad JRC label!
    P. radiata rank #5 despite wrong forest type classification.
```

### Two-Pass Inference: Solving the Unknown Species Problem

At training time, we know which species is at each location (so we know `is_introduced`). At inference time, we don't — we're predicting. Solution: **run the model twice**.

```
    Query: (lat, lon) in New Zealand

    PASS A: is_introduced = 0          PASS B: is_introduced = 1
    "What NATIVE species fit?"         "What INTRODUCED species fit?"
             │                                   │
             ▼                                   ▼
    probs_native[35,561]               probs_introduced[35,561]
             │                                   │
             └───────────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │  WCVP RANGE LOOKUP     │
                    │                        │
                    │  Query → TDWG Level 3  │
                    │  region (spatial join)  │
                    │                        │
                    │  Per species:          │
                    │  Native here?  → use A │
                    │  Introduced?   → use B │
                    │  Unknown?     → use A  │
                    │  (conservative)        │
                    └────────────┬───────────┘
                                │
                                ▼
                    Final ranked predictions
                    with per-species probabilities
```

### Combined Scoring: SINR + SAFE-B

The neural model doesn't replace SAFE-B — it **augments** it:

```
    ┌────────────────────────────────────────────────────────────────┐
    │                                                                │
    │   COMBINED SCORE = 0.6 × SAFE-B + 0.4 × SINR_scaled          │
    │                                                                │
    │   Where:                                                       │
    │     SINR_scaled = min(100, sinr_probability × 150)            │
    │                                                                │
    │   Non-SINR species (not in 35,561 training set):              │
    │     combined_score = SAFE-B × 0.7  (30% penalty)              │
    │                                                                │
    │   This prevents bad recommendations like:                      │
    │     Quercus robur in Amazon (functional score=100              │
    │     but SINR probability ≈ 0 → combined score tanks)          │
    │                                                                │
    └────────────────────────────────────────────────────────────────┘
```

### The 6-Axis Radar Chart (Frontend Display)

Each recommendation shows a radar chart breaking down WHY it scored well:

```
                    SINR Habitat
                         │
                        /|\
                       / | \
                      /  |  \
                     /   |   \
          Traits ───/────┼────\─── Climate/Soil
                   / \   |   / \
                  /   \  |  /   \
                 /     \ | /     \
                /       \|/       \
          Biotic ────────┼──────── Ecosystem
                         |
                       Spatial

    Each axis 0-100, computed per-species:

    SINR Habitat:  Neural model probability
    Climate/Soil:  Temperature + precipitation + pH match
    Ecosystem:     Ecoregion + biome alignment
    Spatial:       Nearby occurrence density
    Biotic:        Pollinator/disperser network richness
    Traits:        Strategy-specific functional fit
```

---

## The Version Timeline: P. radiata Benchmark

A single benchmark tells the whole story. **Pinus radiata at Wairarapa, NZ** (-41.151, 175.100) — a plantation site where the model must correctly identify an introduced plantation species despite environmental features screaming "native podocarp forest":

```
    P. radiata Rank (lower = better)

    #1  ┤
        │
    #5  ┤                ★ v2          ★ v2.2 (expected)
        │               (gate α=0.85)    (logit boost
        │                                 + subspecies merge)
   #10  ┤
        │
   #15  ┤
        │              ┌──────────── k-NN production (#17)
   #17  ┤ ─ ─ ─ ─ ─ ─ ┤
        │              └─────────────────────────────────────
   #20  ┤
        │                       ★ v2.1 (#21) ← REGRESSION
   #22  ┤ ★ v1 (#22)             noisy plantation labels
        │   no gate               8D gate diluted signal
   #23  ┤ ★ v1 emb-only (#23)    aux head disconnected
        │
        └──────┬────────┬────────┬────────┬─────────┬──────
              v1      v2      v2.1     v2.2       v3
           Oct '25  Feb '26  Feb '26  Feb '26   planned
```

### Training Metrics: v2.2 (12 Epochs)

```
    Validation Loss                          Top-10 Accuracy

    0.0070 ┤ ●                               60% ┤                     ●──●──●──●
           │    ●                                │               ●──●──
    0.0060 ┤       ●                          55% ┤         ●──●
           │          ●                           │      ●──
    0.0055 ┤             ●──●──●  ← best     50% ┤   ●
           │                       (ep 8)         │ ●
    0.0050 ┤                    ●──●──●       45% ┤
           │                    overfitting       │
    0.0045 ┤                                  40% ┤
           └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──     └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──
              1  2  3  4  5  6  7  8  9 10 11 12     1  2  3  4  5  6  7  8  9 10 11 12
                         epoch                                     epoch

    Best model: Epoch 8
    val_loss: 0.005286
    top-10: 59.34%
    top-50: 90.08%
    Parameters: 9,713,042
    Training: ~30 min/epoch on Apple Silicon MPS
```

---

## What's Next: v3 Data Expansion

The current model was trained on 7.9M rows from 35,561 species. The v3 campaign will **triple** the dataset:

```
    CURRENT (v2.2 training data)              PLANNED (v3 training data)
    ────────────────────────────              ──────────────────────────

    ┌──────────────────────────┐              ┌──────────────────────────┐
    │   7.9M training rows     │              │  ~22-27M training rows   │
    │                          │              │                          │
    │   35,561 species         │              │  ~50,000+ species        │
    │                          │              │                          │
    │   130 features           │              │  ~650 features           │
    │                          │              │                          │
    │   Sources:               │              │   + 15.2M new GBIF       │
    │   90.3% USDA FIA         │              │   + Temporal backfill    │
    │    9.7% GBIF             │              │   + Carbon/biomass bands │
    │                          │              │   + HILDA+ land use      │
    │                          │              │   + ESA CCI land cover   │
    └──────────────────────────┘              └──────────────────────────┘

    New data sources being sampled via GEE:

    ┌─────────────────────────────────────────────────────────────────┐
    │  Carbon & Biomass (30 new bands)                                │
    │    GEDI L4B biomass  │  CCI Biomass 2010-2020                  │
    │    ESA CCI AGB       │  IPCC Forest Classification             │
    │    MODIS NPP/GPP     │  OCO-2 SIF (fluorescence)              │
    ├─────────────────────────────────────────────────────────────────┤
    │  Land Use History                                               │
    │    HILDA+ v2.0: 61 annual states 1960-2020 (sampled locally)  │
    │    ESA CCI LC: annual 1992-2020 (uploaded to GEE)             │
    ├─────────────────────────────────────────────────────────────────┤
    │  Temporal Environmental Features                                │
    │    TerraClimate: year-matched drought/moisture                 │
    │    Dynamic World: year-matched land cover                      │
    │    MODIS Burned Area: cumulative fire history                   │
    │    VIIRS Nightlights: urbanization pressure                    │
    └─────────────────────────────────────────────────────────────────┘
```

---

## The Full System: How It All Connects

```
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                          USER INTERFACE                                 │
    │                                                                         │
    │   User clicks a point on the map   OR   draws a polygon AOI            │
    │   Selects strategy: Rewilding / Carbon / Agroforestry / ...            │
    │                                                                         │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │   LOCATION PREDICTOR SERVICE (Python, port 5002)                       │
    │                                                                         │
    │   /sample endpoint:                                                     │
    │   ├── AlphaEarth 64-D embedding (multi-year fallback 2023→2017)        │
    │   ├── SRTM elevation                                                    │
    │   ├── Hansen forest change (treecover, loss, gain)                     │
    │   ├── WorldClim BIO (19 bioclimatic variables)                         │
    │   ├── OpenLandMap soil (pH, clay, sand, organic carbon)                │
    │   ├── JRC forest type + Xiao plantation + Neumann natural prob         │
    │   ├── Dynamic World land cover                                          │
    │   └── Embedding homogeneity + canopy height uniformity (MFP signal)    │
    │                                                                         │
    │   /sinr-infer endpoint:                                                │
    │   ├── Map sampled features → 130 model inputs                          │
    │   ├── Normalize (mean/std from training data)                          │
    │   ├── Two-pass inference (is_introduced=0, then =1)                    │
    │   ├── Per-species WCVP lookup → pick correct pass                      │
    │   └── Return top-K species with calibrated probabilities               │
    │                                                                         │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │   BACKEND API (Node.js, port 5001)                                     │
    │                                                                         │
    │   /recommend endpoint:                                                  │
    │   ├── k-NN channel:     HNSW top-500 → IDF-weighted species vote       │
    │   ├── Spatial channel:  Geohash tiles within 50km                      │
    │   ├── Range channel:    WCVP native/introduced + ecoregion match       │
    │   ├── SAFE-B scoring:   5-component weighted sum per strategy          │
    │   ├── SINR integration: Neural probability × 0.4 + SAFE-B × 0.6      │
    │   ├── Radar chart:      6-axis breakdown per species                   │
    │   └── Filters:          Exclude invasive, strategy-specific rules      │
    │                                                                         │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │   FRONTEND (Next.js, port 3001)                                        │
    │                                                                         │
    │   ┌──────────────────────────────────────────────────────────────────┐  │
    │   │  Species Recommender Modal                                       │  │
    │   │                                                                  │  │
    │   │  #1 Dacrycarpus dacrydioides  ████████████████████░  Score: 87   │  │
    │   │     Native  |  Combined: 0.6×SAFEB + 0.4×SINR                   │  │
    │   │     [Radar Chart]  [Details]  [Species Page →]                   │  │
    │   │                                                                  │  │
    │   │  #2 Podocarpus totara         ██████████████████░░  Score: 82   │  │
    │   │     Native  |  Strong climate + spatial match                    │  │
    │   │                                                                  │  │
    │   │  #3 Prumnopitys taxifolia     █████████████████░░░  Score: 78   │  │
    │   │     Native  |  Ecoregion + ecosystem alignment                  │  │
    │   │                                                                  │  │
    │   └──────────────────────────────────────────────────────────────────┘  │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix: Key Numbers

| Metric | v0.1 (Sept '25) | v1 (Oct '25) | v2 (Jan '26) | v3 k-NN (Feb '26) | v3 SINR (Feb '26) |
|--------|-----------------|-------------|-------------|-------------------|-------------------|
| Species in DB | 67,743 | 67,743 | 67,743 | 67,743 | 67,743 |
| Species with embeddings | 0 | ~100 | 500 | 43,992 | 35,561 (model) |
| Occurrence rows | 5.7M tiles | ~5,000 | ~25,000 | 11,396,890 | 7,899,973 (train) |
| Embedding dimensions | - | 64 | 64 | 64 | 64 + 66 env |
| Matching method | Text search | Cosine sim | Cosine + SAFE-B | HNSW k-NN + IDF | Neural net |
| Scoring signals | 0 | 1 | 5 (SAFE-B) | 7 + MFP | SINR + SAFE-B |
| Model parameters | - | - | - | - | 9,713,042 |
| Query latency | ~50ms | ~100ms | ~500ms | ~800ms | ~200ms (inference) |
| Training data | - | - | - | - | 7.9M rows, 130 features |

---

*Built with AlphaEarth, GBIF, WorldClim, OpenLandMap, JRC, WCVP, GloBI, and a lot of iteration.*
