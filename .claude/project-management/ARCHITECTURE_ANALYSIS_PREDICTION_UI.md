# Treekipedia Prediction & Analysis Architecture Analysis
**Date**: March 17, 2026
**Purpose**: Deep technical analysis for "environmental envelope" and "site context" UI design
**Scope**: Frontend components, backend API flows, microservice integration, data structures

---

## Executive Summary

The prediction system follows a **three-tier architecture**:

1. **Frontend Layer** (`treekipedia/frontend`): React components for user interaction, modal displays, filtering
2. **Backend API** (`treekipedia/backend`): Node.js/Express that orchestrates multi-source candidate discovery and scoring
3. **Microservice** (`orchestrator/location_predictor_FIXED.py`): Flask service that samples environmental data from Google Earth Engine and computes AI embeddings

**Two major interaction modes** exist:
- **Species Predictor** (scientific habitat suitability: "can it grow here?") — `/api/prediction/predict`
- **Species Recommender** (strategy-based recommendations: "should I plant it here?") — `/api/prediction/recommend`

**Environmental data exposure** is **partially implemented**: The backend receives rich environmental context (climate, soil, elevation, forest type) but only returns a subset to the frontend. Significant **opportunities exist to surface more context** (canopy metrics, managed forest probability, embedding homogeneity).

---

## Component Tree: Frontend Prediction/Analysis Features

### Page-Level Components
```
/treekipedia/frontend/app/
├── analysis/page.tsx ⭐ MAIN ENTRY
│   ├── Header (icon + title + description)
│   ├── Map component (dynamic import)
│   ├── Floating panels (overlay pattern)
│   └── Floating panels container (position: absolute)
│
└── v3/page.tsx
    └── (Newer UI variant — check if in use)
```

### Analysis Page Structure
```
AnalysisPage (analysis/page.tsx)
├── State Management (7 React useState hooks)
│   ├── analysisResults: PlotAnalysisResponse | null
│   ├── isLoading: boolean
│   ├── isHeatmapLoading: boolean
│   ├── error: string | null
│   ├── showResultsPanel: boolean
│   ├── showKMLPanel: boolean
│   ├── isResultsMinimized: boolean
│   └── isKMLMinimized: boolean
│
├── Map Component (MapContainer from react-leaflet)
│   ├── TileLayer (base map)
│   ├── DrawControl (polygon + rectangle drawing)
│   ├── EcoregionLayer (conditional rendering)
│   ├── MangaroaNativeForestsLayer (NZ-specific)
│   ├── MapClickHandler ⭐ KEY COMPONENT
│   │   ├── LocationPredictionModal
│   │   ├── SpeciesRecommenderModal
│   │   └── ModeSelector (portal)
│   └── (Additional layers)
│
└── Results Panels (floating, z-1000+)
    ├── Species Analysis Panel
    │   └── ResultsList component
    └── KML Upload Panel
        └── FileUpload component
```

### Click-to-Prediction Flow Diagram
```
User clicks map (enabled when not drawing)
    ↓
MapClickHandler.useMapEvents({ click: ... })
    ↓
Detect drawing mode (leaflet-draw event listeners)
    ↓
Yes: Ignore click
No: Show ModeSelector portal (2 buttons)
    ├── "Species Predictor" → HabitatPredictionModal
    │   └── Call /api/prediction/predict?lat=X&lon=Y
    │
    └── "Species Recommender" → SpeciesRecommenderModal
        └── Call /api/prediction/recommend?lat=X&lon=Y&strategy=...

Modal renders results → User can expand species, filter by native status, click through to species pages
```

### Modal Component Details

#### HabitatPredictionModal.tsx (Species Predictor)
**Location**: `/treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx`
**Lines**: 1–810 (massive component, highly feature-rich)

**State**:
```typescript
status: 'sampling' | 'predicting' | 'complete' | 'error'
progress: number (0-100)
message: string
predictions: SpeciesPrediction[]
locationContext: LocationContext | null
nativeStatusSummary: NativeStatusSummary | null
errorMessage: string
isDemoMode: boolean (true when using simulated embedding)
expandedSpecies: Set<string> (tracks which species show signal breakdown)
displayCount: number (pagination: default 30)
activeFilters: Set<NativeStatusFilter> ('native'|'introduced'|'invasive'|'unknown')
```

**API Call** (lines 256–329):
```typescript
const response = await fetch(
  `${API_URL}/api/prediction/predict?lat=${lat}&lon=${lon}&limit=100`
);
const data: PredictionResponse = await response.json();
```

**Data Structure Received** (from backend `/predict` response):
```typescript
interface PredictionResponse {
  success: boolean;
  location: {
    latitude: number;
    longitude: number;
    elevation: number | null;
    treecover2000?: number;
    forest_loss?: boolean;
    data_source: string;
    demo_mode: boolean;
  };
  location_context: {
    ecoregion: {
      eco_id: number;
      eco_name: string;
      biome_name: string;
      realm: string;
    } | null;
    countries: string[];
    climate: {
      annual_mean_temp_c: number | null;
      annual_precipitation_mm: number | null;
    } | null;
    soil: {
      ph: number | null;
      ph_category: string | null;
      texture: string | null;
    } | null;
    embedding_homogeneity: number | null;  // ⭐ NEW FIELD
  };
  results: {
    count: number;
    native_status_summary: {
      native: number;
      introduced: number;
      invasive: number;
      native_and_introduced: number;
      unknown: number;
    };
    source_summary: {
      embedding_only: number;
      spatial_only: number;
      multi_source: number;
      total_candidates_evaluated: number;
    };
    predictions: SpeciesPrediction[];
  };
}

interface SpeciesPrediction {
  rank: number;
  taxon_id: string;
  scientific_name: string;
  family: string;
  common_name: string | null;
  suitability_score: number;
  habitat_similarity: number;

  // Multi-signal breakdown (5 channels)
  signals?: {
    embedding: number;        // Satellite habitat similarity %
    spatial: number;          // Observed nearby %
    range: number;            // WCVP native range %
    ecoregion: number;        // Ecoregion match %
    climate: number;          // Climate envelope %
  };

  signal_weights?: {
    embedding: number;
    spatial: number;
    range: number;
    ecoregion: number;
    climate: number;
  };

  // Source tracking
  discovery_sources: string[]; // ['embedding', 'spatial', 'range', 'ecoregion']
  source_count?: number;

  // Native status
  native_status: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native: boolean;
  is_introduced: boolean;
  is_invasive: boolean;

  // Habitat match details
  habitat_match?: {
    cluster_id: number;
    cluster_elevation: number;
    cluster_treecover: number;
    cluster_occurrences: number;
    representative_location: { lat: number; lon: number } | null;
  };

  // Spatial analysis
  spatial_tiles_nearby?: number;
  spatial_min_distance_m?: number | null;

  // Species attributes
  attributes?: {
    growth_form: string | null;
    maximum_height: string | null;
    conservation_status: string | null;
  };

  // Other
  confidence?: number;
  ecoregion_match?: boolean;
}
```

**Rendering Logic**:
- Shows `location_context` with ecoregion + countries + climate/soil (lines 441–555)
- Native status filter buttons (native/introduced/invasive/unknown)
- Multi-signal score bars (visual 5-part bar, lines 625–651)
- Signal breakdown expansion (lines 678–733)
- Species list with pagination (lines 741–756)

**Key UI Patterns**:
- Dark theme: `bg-gradient-to-br from-emerald-950 to-black`
- Modal: Portal rendered to `document.body`
- Responsive cards: `bg-black/30 backdrop-blur-sm border border-emerald-500/20`
- Inline badges for native status (green/blue/red/yellow)
- Loading progress bar (10→20→30→80→100)

---

#### SpeciesRecommenderModal.tsx (Species Recommender)
**Location**: `/treekipedia/frontend/app/analysis/components/SpeciesRecommenderModal.tsx`
**Lines**: 1–300+ (similar structure to HabitatPredictionModal)

**Key Differences**:
- Takes `strategy` query param (e.g., `rewilding`, `agroforestry`, `riparian`, `carbon`, etc.)
- Returns `SafeBComponents` scores instead of pure habitat suitability
- Includes `sinr_probability` and `sinr_detail` (SINR v3 habitat predictions)
- Radar chart visualization of SAFE-B components
- `combined_score` (blended SAFE-B + SINR when available)

**API Call**:
```typescript
const response = await fetch(
  `${API_URL}/api/prediction/recommend?lat=${lat}&lon=${lon}&strategy=${strategy}&limit=30`
);
```

---

### MapClickHandler.tsx
**Location**: `/treekipedia/frontend/app/analysis/components/MapClickHandler.tsx`
**Lines**: 1–246

**Purpose**: Orchestrates map click detection + mode selection modal

**Key Features**:
- **Drawing detection** (lines 50–87): Listens to leaflet-draw events to suppress clicks during drawing
- **Click handler** (lines 89–118): Detects clicks outside draw controls
- **Mode selector portal** (lines 122–184): Creates floating modal with 2 options
- **Icon for clicked location** (lines 9–33): Custom circular marker with emerald gradient

**State Flow**:
```
clickedLocation: { lat, lon } | null
showPredictionModal: boolean
showRecommenderModal: boolean
showModeSelector: boolean
isDrawing: boolean
```

**Portal Rendering**: Uses React portal to render outside Leaflet DOM to avoid z-index/click event issues

---

### Map.tsx
**Location**: `/treekipedia/frontend/app/analysis/components/Map.tsx`
**Lines**: 1–400+

**Key Components**:
1. **DrawControl**: Leaflet-draw integration for polygon/rectangle drawing
   - Triggers `analyzePlot` API call when polygon created/edited/deleted
   - Clears previous results on new shape

2. **EcoregionLayer**: Dynamic GeoJSON overlay
   - Loads ecoregions via `/api/geospatial/ecoregions/boundaries?bbox=...`
   - Updates on map pan/zoom
   - Shows ecoregion names + biome in popups

3. **MangaroaNativeForestsLayer**: NZ-specific layer
   - Loads native forest polygons
   - Renders with opacity control

4. **MapClickHandler**: Included as nested component (no props needed for basic functionality)

---

## Backend API Architecture

### File Location
**Route Handler**: `/treekipedia/backend/routes/prediction.js` (~3000 lines)
**Service**: `/treekipedia/backend/services/safeb-scorer.js`
**Server**: `/treekipedia/backend/server.js` (registers `/api/prediction/*` routes)

### Route Registration (server.js)
```javascript
const predictionRoutes = require('./routes/prediction');
app.use('/api/prediction', predictionRoutes);
```

### Endpoints Overview

#### 1. GET /api/prediction/sample
**Purpose**: Proxy to Python microservice `/sample` endpoint
**Use Case**: Get raw embedding + environmental data for a location

**Request**:
```
GET /api/prediction/sample?lat=-14.2644&lon=-52.7344
```

**Response**:
```json
{
  "success": true,
  "lat": -14.2644,
  "lon": -52.7344,
  "year": 2023,
  "embedding": {"a00": 0.1, "a01": 0.2, ..., "a63": 0.15},  // 64-D AlphaEarth
  "elevation": 450,
  "treecover2000": 85,
  "forest_loss": false,
  "climate": {
    "annual_mean_temp_c": 24.5,
    "annual_precipitation_mm": 2100,
    "koppen_code": "Am",
    "koppen_description": "Monsoon"
  },
  "soil": {
    "soil_ph": 5.8,
    "soil_ph_category": "strongly acidic",
    "soil_texture": "clay loam"
  },
  "embedding_homogeneity": 0.92,
  "ccdc": {"ccdc_num_breaks": 1, ...},
  "canopy_height": {"canopy_height_mean_m": 28.5, "canopy_height_stddev_100m": 4.2},
  "sinr_env": {...35 bands...},
  "data_source": "alphaearth_real",
  "demo_mode": false,
  "processing_time": 12.34
}
```

---

#### 2. GET /api/prediction/predict ⭐ MAIN PREDICTION ENDPOINT
**Purpose**: Multi-signal species habitat suitability prediction
**Question Answered**: "What species CAN grow here?"

**Request**:
```
GET /api/prediction/predict?lat=-14.2644&lon=-52.7344&limit=100
```

**Backend Flow** (lines 139–1445):
```
1. Get embedding from Python service (/sample POST or GET)
   ├─ Normalize embedding (64-D array)
   └─ Extract: elevation, climate, soil, treecover, MFP

2. Fire SINR v3 inference in parallel (→ `/sinr-infer`)
   └─ Get taxon_id → {prob_native, prob_introduced, prob_best, rank}

3. Get location context
   ├─ Query ecoregions (PostGIS)
   ├─ Query countries (PostGIS)
   └─ Get WCVP region codes for country

4. MULTI-SOURCE CANDIDATE DISCOVERY (3 independent channels)

   Channel 1: Embedding similarity (pgvector)
   ├─ Query top 500 species centroids by cosine similarity
   ├─ Calculate: embedding_similarity score
   └─ Add to candidateMap with source='embedding'

   Channel 2: Spatial proximity (geohash tiles)
   ├─ Query geohash_species_tiles within 50km
   ├─ Calculate: spatial_proximity_score, tile_count, min_distance
   └─ Add to candidateMap with source='spatial'

   Channel 3: WCVP native range
   ├─ Query species table by wcvp_region
   ├─ Mark: wcvp_native, wcvp_introduced flags
   └─ Add to candidateMap with source='range'

5. Additional signals (per candidate)

   Signal 4: Ecoregion match
   ├─ Query: species recorded in this ecoregion?
   └─ Mark: ecoregion_match boolean

   Signal 5: Climate envelope
   ├─ Compare species elevation/temp/precip ranges vs location
   └─ Calculate: climate_envelope_match score

6. COMPOSITE SCORING (per candidate)
   ├─ Base weights: embedding=0.3, spatial=0.3, range=0.15, ecoregion=0.15, climate=0.1
   ├─ Adjust if managed forest (MFP > 0.50): boost spatial, reduce embedding
   ├─ Apply introduced penalty if SINR unavailable
   └─ suitability_score = weighted_sum(signals)

7. Sort by suitability_score, limit to N results
8. Build response with location_context + results
```

**Key Architectural Patterns**:
- **Parallel SINR inference**: Doesn't block candidate discovery (line 263)
- **Managed Forest Probability (MFP)**: Adjusts scoring based on canopy uniformity (lines 209–249)
- **Signal weights**: Dynamic based on forest type (lines 1415–1437)
- **IDF factor**: Inverse document frequency weighting for rare candidates (line 1435)

**Response Structure** (lines 1385–1445):
```json
{
  "success": true,
  "location": {
    "latitude": -14.2644,
    "longitude": -52.7344,
    "elevation": 450,
    "treecover2000": 85,
    "forest_loss": false,
    "data_source": "alphaearth_real",
    "demo_mode": false
  },
  "location_context": {
    "ecoregion": {
      "eco_id": 123,
      "eco_name": "Atlantic tropical and subtropical moist broadleaf forests",
      "biome_name": "Tropical & Subtropical Moist Broadleaf Forests",
      "realm": "Neotropical"
    },
    "countries": ["Brazil"],
    "climate": {
      "annual_mean_temp_c": 24.5,
      "annual_precipitation_mm": 2100
    },
    "soil": {
      "ph": 5.8,
      "ph_category": "strongly acidic",
      "texture": "clay loam"
    },
    "embedding_homogeneity": 0.92
  },
  "query_params": {
    "limit": 100,
    "scoring": "multi-signal-v3-sinr",
    "sinr": {
      "available": true,
      "model_version": "v3.0",
      "candidates_added": 150
    },
    "managed_forest": {
      "probability": 0.68,
      "is_managed": true,
      "embedding_homogeneity": 0.92,
      "canopy_height_mean": 28.5,
      "canopy_height_stddev": 4.2,
      "ccdc_breaks": 1,
      "description": "Uniform canopy detected — scoring favors k-NN concentration over centroid match"
    },
    "idf_context": {
      "idf_factor": 1.0,
      "description": "..."
    }
  },
  "results": {
    "count": 100,
    "native_status_summary": {
      "native": 65,
      "introduced": 20,
      "invasive": 3,
      "native_and_introduced": 12,
      "unknown": 0
    },
    "source_summary": {
      "embedding_only": 30,
      "spatial_only": 25,
      "multi_source": 45,
      "total_candidates_evaluated": 8453
    },
    "predictions": [
      {
        "rank": 1,
        "taxon_id": "12345",
        "scientific_name": "Xylopia emarginata",
        "family": "Annonaceae",
        "common_name": "Embira",
        "suitability_score": 92.5,
        "habitat_similarity": 0.87,

        "signals": {
          "embedding": 92,
          "spatial": 88,
          "range": 95,
          "ecoregion": 100,
          "climate": 85
        },
        "signal_weights": {
          "embedding": 0.30,
          "spatial": 0.30,
          "range": 0.15,
          "ecoregion": 0.15,
          "climate": 0.10
        },

        "discovery_sources": ["embedding", "spatial", "range"],
        "source_count": 3,

        "native_status": "native",
        "is_native": true,
        "is_introduced": false,
        "is_invasive": false,

        "habitat_match": {
          "cluster_id": 456,
          "cluster_elevation": 450,
          "cluster_treecover": 82,
          "cluster_occurrences": 1250,
          "representative_location": {"lat": -14.3, "lon": -52.8}
        },

        "spatial_tiles_nearby": 48,
        "spatial_min_distance_m": 2500,

        "attributes": {
          "growth_form": "tree",
          "maximum_height": "20",
          "conservation_status": "Not Evaluated"
        },

        "ecoregion_match": true,
        "confidence": 0.95
      }
      // ... 99 more species
    ]
  }
}
```

---

#### 3. GET /api/prediction/recommend
**Purpose**: Strategy-based species recommendations with SAFE-B scoring
**Question Answered**: "What SHOULD I plant here?"
**Strategies**: rewilding, agroforestry, riparian, carbon, biodiversity, erosion_control, general

**Request**:
```
GET /api/prediction/recommend?lat=-14.2644&lon=-52.7344&strategy=rewilding&limit=30
```

**Key Differences from `/predict`**:
- Uses SAFE-B scorer service (5 weighted dimensions)
- Applies strategy-specific candidate filters
- Returns SINR probability blended with SAFE-B score
- Excludes invasive species by default
- Can include non-native species with `include_introduced=true`

**Response includes SAFE-B components**:
```json
"safeb_components": {
  "spatial": 0.85,        // Observed in nearby regions
  "abiotic": 0.78,        // Climate + soil envelope match
  "functional": 0.72,     // Functional traits for strategy
  "ecosystem": 0.88,      // Ecoregion + biome suitability
  "biotic": 0.65          // Compatible with local biota
}
```

---

## Python Microservice: location_predictor_FIXED.py

**File**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/location_predictor_FIXED.py`
**Language**: Python 3 + Flask
**Port**: 5002 (default)
**Dependencies**: `ee` (Google Earth Engine), `flask`, `flask_cors`, `numpy`

### Architecture
```
Flask app (CORS enabled)
├── /sample (POST/GET)         ← Main sampling endpoint
├── /health (GET)              ← Status check
├── /sinr-infer (POST)         ← SINR v3 inference
├── /predict (POST)            ← Compatibility endpoint
└── /test-* (diagnostic)       ← Debug endpoints

Helper functions (call Google Earth Engine):
├── sample_alphaearth_multiyear()    → 64-D embedding
├── sample_srtm_elevation()          → Elevation (m)
├── sample_hansen_forest()           → Treecover2000, loss
├── sample_worldclim_bio()           → 19 BIO variables
├── sample_openlandmap_soil()        → pH, clay, sand, OC
├── sample_embedding_homogeneity()   → 3×3 grid similarity
├── sample_ccdc()                    → Change detection
├── sample_canopy_height_variance()  → Canopy metrics
├── sample_sinr_env_features()       → 35 environmental bands
├── sample_xiao_planted_forest()     → Xiao forest type (0/1/2)
└── sample_neumann_natural_prob()    → Natural vs planted probability
```

### /sample Endpoint (Lines 1087–1272)

**Request**:
```json
POST /sample
{
  "lat": -14.2644,
  "lon": -52.7344,
  "year": 2023
}
```

**Processing**:
1. Sample AlphaEarth embedding (multi-year fallback: 2023→2022→...→2017)
2. Sample elevation (SRTM 30m)
3. Sample Hansen forest change (treecover2000, loss)
4. Sample 19 WorldClim BIO variables (temperature, precipitation)
5. Sample OpenLandMap soil (pH, clay%, sand%, organic carbon)
6. Compute embedding homogeneity (3×3 grid of embeddings, cosine similarity)
7. Sample CCDC change detection (number of breakpoints since 1999)
8. Sample ETH canopy height (mean + stddev within 100m)
9. Sample SINR environmental features (35 bands: elevation, slope, aspect, VVI, tasseled cap, etc.)

**Response Structure** (lines 1172–1268):
```json
{
  "success": true,
  "lat": -14.2644,
  "lon": -52.7344,
  "year": 2023,

  // Elevation
  "elevation": 450,

  // Hansen Forest Change
  "treecover2000": 85,
  "lossyear": 0,
  "loss": false,
  "gain": false,

  // Climate (WorldClim BIO)
  "climate": {
    "annual_mean_temp_c": 24.5,           // BIO01 / 10
    "max_temp_warmest_month_c": 27.3,     // BIO05 / 10
    "min_temp_coldest_month_c": 21.7,     // BIO06 / 10
    "annual_precipitation_mm": 2100,      // BIO12
    "precip_wettest_month_mm": 285,       // BIO13
    "precip_driest_month_mm": 95,         // BIO14
    "precip_seasonality_cv": 89,          // BIO15
    "mean_diurnal_range_c": 8.4,          // BIO02 / 10
    "isothermality": 29,                  // BIO03
    "temp_seasonality": 480,              // BIO04 / 100
    "temp_annual_range_c": 5.6,           // BIO07 / 10
    "mean_temp_wettest_quarter_c": 25.1,  // BIO08 / 10
    "mean_temp_driest_quarter_c": 23.9,   // BIO09 / 10
    "mean_temp_warmest_quarter_c": 26.2,  // BIO10 / 10
    "mean_temp_coldest_quarter_c": 22.8,  // BIO11 / 10
    "precip_wettest_quarter_mm": 825,     // BIO16
    "precip_driest_quarter_mm": 280,      // BIO17
    "precip_warmest_quarter_mm": 750,     // BIO18
    "precip_coldest_quarter_mm": 550,     // BIO19
    "koppen_code": "Am",
    "koppen_description": "Tropical Monsoon"
  },

  // Soil (OpenLandMap)
  "soil": {
    "soil_ph": 5.8,                       // pH × 10 / 10
    "soil_ph_category": "strongly acidic",
    "soil_texture": "clay loam",
    "soil_clay_percent": 35.2,
    "soil_sand_percent": 28.5,
    "soil_organic_carbon_g_per_kg": 58.4
  },

  // Embedding homogeneity (monoculture signal)
  "embedding_homogeneity": 0.92,
  "homogeneity_detail": {
    "embedding_homogeneity": 0.92,
    "grid_size": 3,
    "num_grids": 9,
    "embedding_std": 0.45,
    "message": "High spatial homogeneity — likely planted/managed forest"
  },

  // CCDC change detection
  "ccdc": {
    "ccdc_num_breaks": 1,
    "ccdc_first_year": 2012,
    "ccdc_description": "1 change detected (likely plantation establishment)"
  },

  // Canopy height
  "canopy_height": {
    "canopy_height_mean_m": 28.5,
    "canopy_height_stddev_100m": 4.2,
    "canopy_height_cv": 0.147,
    "message": "Tall, uniform canopy — high probability of managed forest"
  },

  // SINR environmental features (35 bands)
  "sinr_env": {
    "elevation_m": 450,
    "slope_degrees": 8.5,
    "aspect_degrees": 135,
    "vvi": 0.62,
    "roughness": 0.18,
    "tri": 85,
    // ... 29 more bands (terrain, water, climate, soil, ecoregion, etc.)
  },

  "embedding": {
    "a00": 0.123, "a01": 0.234, ..., "a63": 0.456  // 64-D AlphaEarth
  },

  "data_source": "alphaearth_real",
  "demo_mode": false,
  "processing_time": 12.34
}
```

### Key Transformations
- **Temperature variables**: Stored as °C × 10 in WorldClim, divided by 10 for display
- **Soil pH**: Stored as pH × 10 in OpenLandMap, divided by 10 for display
- **Embedding**: Normalized to unit hypersphere (L2 norm = 1)
- **Homogeneity**: Computed as mean cosine similarity of 9 embeddings (3×3 grid)

---

## Data Flow Diagrams

### Click-to-Prediction Flow (Complete)
```
User clicks map at (lat, lon)
    ↓
MapClickHandler detects click (not in draw mode)
    ↓
Shows ModeSelector portal with 2 options
    ├─ "Species Predictor"
    │  ↓
    │  HabitatPredictionModal renders with loading state
    │  ↓
    │  Calls: GET /api/prediction/predict?lat=X&lon=Y&limit=100
    │      ↓ (Backend)
    │      Backend calls: POST /sample (to 5002)
    │          ↓ (Python)
    │          GEE samples: AlphaEarth (embedding), SRTM, Hansen, WorldClim, etc.
    │          Returns: 64-D embedding + climate + soil + elevation + homogeneity
    │      ↓
    │      Backend normalizes embedding
    │      ↓
    │      Backend fires SINR inference in parallel
    │      ↓
    │      Backend runs 3-channel candidate discovery
    │         ├─ pgvector cosine similarity (embedding)
    │         ├─ geohash spatial proximity (50km)
    │         └─ WCVP native range lookup
    │      ↓
    │      Backend scores all candidates (weighted multi-signal)
    │      ↓
    │      Backend returns top 100 with signals breakdown
    │  ↓
    │  Frontend displays:
    │    ├─ Location context (ecoregion + countries + climate + soil)
    │    ├─ Native status filter buttons
    │    ├─ Species list with signal bars
    │    └─ Expandable signal breakdown per species
    │  ↓
    │  User can:
    │    ├─ Click species name → navigate to species page
    │    ├─ Expand to see signal breakdown
    │    ├─ Filter by native/introduced/invasive
    │    └─ Scroll to see more results
    │
    └─ "Species Recommender"
       ↓
       SpeciesRecommenderModal renders
       ↓
       (Same flow as predictor, but with strategy-specific SAFE-B scoring)
```

### Backend Multi-Signal Scoring Flow
```
Location: (lat, lon)
    ↓
Get embedding from /sample
    ├─ if success: use embedding
    └─ if fail: return 503 error
    ↓
Fire SINR v3 inference (async)
    └─ Get: {taxon_id → prob_native, prob_introduced, prob_best}
    ↓
Query ecoregion + country
    ↓
CHANNEL 1: Embedding similarity (pgvector)
    ├─ Query pgvector: SELECT TOP 500 by cosine similarity
    ├─ For each: embedding_similarity = cosine_dist
    └─ Add to candidateMap with source='embedding'
    ↓
CHANNEL 2: Spatial proximity (geohash tiles)
    ├─ Query geohash_species_tiles: within 50km polygon
    ├─ For each species: spatial_score = tile_density + distance_penalty
    └─ Add/update candidateMap with source='spatial'
    ↓
CHANNEL 3: WCVP range
    ├─ Query species table by wcvp_region
    ├─ Mark: native_in_country, introduced_in_country
    └─ Add/update candidateMap with source='range'
    ↓
SIGNAL 4: Ecoregion match (per candidate)
    ├─ Query: species.ecoregions ILIKE '%{ecoregion}%'
    └─ Mark: ecoregion_match = true/false
    ↓
SIGNAL 5: Climate envelope (per candidate)
    ├─ Compare elevation/temp/precip ranges vs location climate
    └─ Calculate: envelope_match_score
    ↓
COMPOSITE SCORE (per candidate)
    ├─ base_weights = {embedding: 0.3, spatial: 0.3, range: 0.15, ecoregion: 0.15, climate: 0.1}
    ├─ if managed_forest_prob > 0.50:
    │    ├─ embedding_weight *= 0.7 (less reliance on habitat similarity)
    │    └─ spatial_weight *= 1.3 (boost observed occurrences)
    ├─ suitability_score = weighted_sum
    └─ if no SINR: penalize by 30% (non-SINR species get combined_score = score * 0.7)
    ↓
Sort by suitability_score DESC
    ↓
Return top N with:
    ├─ rank
    ├─ signals breakdown (5 channels)
    ├─ discovery_sources
    ├─ native_status
    ├─ confidence
    └─ attributes (growth form, height, conservation status)
```

---

## Current Data Flow: Frontend ← Backend ← Microservice

### Returned Data Structure (What Frontend Receives)

The **HabitatPredictionModal** receives via `/api/prediction/predict`:

```
location: {
  latitude, longitude, elevation,
  treecover2000, forest_loss,
  data_source, demo_mode
}

location_context: {
  ecoregion: {eco_id, eco_name, biome_name, realm},
  countries: [],
  climate: {annual_mean_temp_c, annual_precipitation_mm},
  soil: {ph, ph_category, texture},
  embedding_homogeneity: 0.0-1.0   ← ⭐ ALREADY AVAILABLE (but not displayed)
}

results: {
  native_status_summary: {native, introduced, invasive, native_and_introduced, unknown},
  source_summary: {embedding_only, spatial_only, multi_source, total_candidates},
  predictions: [
    {
      rank, taxon_id, scientific_name, family, common_name,
      suitability_score, habitat_similarity,
      signals: {embedding, spatial, range, ecoregion, climate},
      signal_weights: {...},
      discovery_sources,
      native_status, is_native, is_introduced, is_invasive,
      habitat_match: {cluster_id, cluster_elevation, cluster_treecover, representative_location},
      spatial_tiles_nearby, spatial_min_distance_m,
      attributes: {growth_form, maximum_height, conservation_status},
      ecoregion_match, confidence
    }
  ]
}
```

---

## Data NOT Currently Exposed to Frontend

**In `/api/prediction/predict` response but not displayed**:

```javascript
location_context.embedding_homogeneity  ← Monoculture signal (0-1)

query_params.managed_forest: {
  probability: 0-1,              ← What % this is a managed forest
  is_managed: boolean,           ← Threshold decision
  embedding_homogeneity: 0-1,    ← Spatial uniformity
  canopy_height_mean: meters,    ← Tall canopies = managed
  canopy_height_stddev: meters,  ← Uniform heights = managed
  ccdc_breaks: integer,          ← Change detection count
  description: string
}

query_params.sinr: {
  available: boolean,
  model_version: string,
  candidates_added: integer
}

query_params.idf_context: {
  idf_factor: 0-2,               ← Rarity weighting
  description: string
}
```

**In Python `/sample` response but not passed through backend**:
```
ccdc: {                          ← Change detection history
  ccdc_num_breaks,
  ccdc_first_year
}

canopy_height: {                 ← Structural uniformity
  canopy_height_mean_m,
  canopy_height_stddev_100m,
  canopy_height_cv
}

sinr_env: {                      ← 35 environmental bands
  elevation_m, slope_degrees, aspect, vvi, roughness, tri,
  tasseled_cap_*, forest_coverage, canopy_height_models, etc.
}

homogeneity_detail: {            ← Grid analysis details
  embedding_std, num_grids, message
}
```

---

## Styling Patterns (Tailwind/Dark Theme)

### Color Scheme
- **Primary/Accent**: Emerald (`emerald-300`, `emerald-400`, `emerald-500`)
- **Background**: Black/black with opacity (`bg-black/30`, `bg-emerald-950`)
- **Borders**: Subtle white/emerald (`border-white/20`, `border-emerald-500/20`)
- **Text**: White/white with opacity (`text-white`, `text-white/70`)
- **Signal Colors**:
  - Embedding (Satellite): Blue (`bg-blue-500`)
  - Spatial (Observed): Amber (`bg-amber-500`)
  - Range (WCVP): Green (`bg-green-500`)
  - Ecoregion: Purple (`bg-purple-500`)
  - Climate: Teal (`bg-teal-500`)

### Component Patterns
```tsx
// Card
<div className="bg-black/30 backdrop-blur-sm border border-emerald-500/20 rounded-xl">

// Button
<button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors">

// Badge/Tag
<span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-green-500/20 text-green-300 text-xs">

// Modal
<div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">

// Progress bar
<div className="h-2 bg-emerald-950 rounded-full overflow-hidden">
  <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-300"></div>
</div>

// Header
<div className="flex-shrink-0 bg-gradient-to-r from-emerald-900/90 to-emerald-800/90 backdrop-blur-md px-6 py-4 border-b border-emerald-500/20">
```

---

## Component Inventory for Environmental Envelope UI

### Existing Reusable Components
1. **HabitatPredictionModal.tsx** (810 lines)
   - Multi-signal score bars (lines 625–651)
   - Signal breakdown expansion (lines 678–733)
   - Native status filter UI (lines 476–553)
   - Card layout pattern

2. **SpeciesRecommenderModal.tsx**
   - Radar chart rendering (if implemented)
   - SAFE-B component breakdown
   - Strategy selector

3. **Map.tsx**
   - Leaflet integration
   - Custom markers
   - Popups

### Styling Utilities
- Tailwind grid: `grid grid-cols-1 gap-3` (responsive stacking)
- Flex alignment: `flex items-center justify-between`
- Spacing scale: `px-4 py-2` (consistent padding)
- Border/shadow: `border-emerald-500/20 shadow-2xl`

---

## Gaps & Opportunities for Environmental Envelope Layer

### Missing Context (Available but Not Displayed)

1. **Managed Forest Probability**
   - Currently computed but buried in `query_params.managed_forest`
   - **Opportunity**: Display as badge/indicator in location context
   - Example: "Managed Forest 68%" with icon

2. **Canopy Metrics**
   - Mean height + uniformity (coefficient of variation)
   - **Opportunity**: Add to location context card with icon
   - Signals: "28.5m mean height • CV 0.15 (uniform)"

3. **Change Detection (CCDC)**
   - Number of breaks since 1999 + first year
   - **Opportunity**: Indicates disturbance history
   - Example: "1 disturbance detected (2012)" with timeline

4. **Embedding Homogeneity**
   - Returned in `location_context` but never rendered
   - **Opportunity**: Visual indicator (0-1 scale)
   - Example: "Spatial uniformity: ████░ 92%"

5. **SINR Model Metadata**
   - Model version, candidates added, timing
   - **Opportunity**: Collapsible "methodology" section
   - Example: "Habitat predictions from v3.0 neural model (15ms inference)"

6. **SINR Environmental Features (35 bands)**
   - All available in Python service but not exposed
   - **Opportunity**: "Raw environmental data" expandable section
   - Bands: elevation, slope, aspect, VVI, roughness, tasseled cap, etc.

7. **IDF Context**
   - Rarity weighting factor (0-2 scale)
   - **Opportunity**: Explains why some species are boosted
   - Example: "IDF factor: 1.2 (species rarity boost applied)"

### Architectural Changes Needed

1. **Backend changes** (minimal):
   - Already computing all data; just need to expose in response
   - Add `managed_forest`, `canopy_height`, `ccdc_details`, `sinr_metadata` to frontend response

2. **Frontend changes** (moderate):
   - Create new "EnvironmentalEnvelope" component
   - Add "SiteContext" card/panel
   - Add expandable sections for raw SINR data

---

## API Response Shape Summary

### Current `/api/prediction/predict` Response Keys
```
✅ location              (basic: lat, lon, elevation, treecover2000, data_source, demo_mode)
✅ location_context      (ecoregion, countries, climate, soil)
  ✅ embedding_homogeneity (present but not displayed)
✅ results
  ✅ native_status_summary
  ✅ source_summary
  ✅ predictions[]
    ✅ rank, taxon_id, scientific_name, family, suitability_score
    ✅ signals, signal_weights, discovery_sources
    ✅ native_status, habitat_match, spatial_tiles_nearby
    ✅ attributes

❌ query_params.managed_forest  (computed but not exposed to frontend)
❌ query_params.sinr           (metadata about SINR inference)
❌ query_params.idf_context    (rarity weighting explanation)
```

### Python `/sample` Response Keys Not Passed Through
```
❌ ccdc                  (change detection history)
❌ canopy_height        (structural metrics)
❌ sinr_env            (35 environmental bands)
❌ homogeneity_detail  (embedding grid analysis)
```

---

## Recommendation for Environmental Envelope Design

### Phased Approach

**Phase 1 (Expose what's already computed)**:
- Expose `query_params.managed_forest` in backend response
- Expose `query_params.sinr` metadata
- Display in modal header/context section
- 2-3 hour backend work + 4-5 hours frontend

**Phase 2 (Add canopy metrics & change detection)**:
- Pass `canopy_height` from Python → backend → frontend
- Pass `ccdc_details` from Python → backend → frontend
- Create "Forest Structure" card in modal
- 3-4 hours total

**Phase 3 (SINR environmental features)**:
- Expose selected `sinr_env` bands (top 10-15 most interpretable)
- Create "Raw Environmental Data" expandable section
- Add tooltips for each variable
- 5-6 hours total

**Phase 4 (Interactive envelope visualization)**:
- Create species-specific envelope overlay on maps
- Add "view suitable climate range" feature
- Add comparative analysis: "location vs species preference"
- 8-10 hours total (requires frontend + backend changes)

---

## File Reference

### Frontend Files
- **Analysis Page**: `/treekipedia/frontend/app/analysis/page.tsx`
- **Prediction Modal**: `/treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx`
- **Recommender Modal**: `/treekipedia/frontend/app/analysis/components/SpeciesRecommenderModal.tsx`
- **Map Click Handler**: `/treekipedia/frontend/app/analysis/components/MapClickHandler.tsx`
- **Map Component**: `/treekipedia/frontend/app/analysis/components/Map.tsx`
- **Types**: `/treekipedia/frontend/lib/types.ts`
- **API Calls**: `/treekipedia/frontend/lib/api.ts`

### Backend Files
- **Prediction Routes**: `/treekipedia/backend/routes/prediction.js`
- **SAFE-B Scorer**: `/treekipedia/backend/services/safeb-scorer.js`
- **Server Entry**: `/treekipedia/backend/server.js`

### Python Microservice
- **Location Predictor**: `/orchestrator/location_predictor_FIXED.py`

---

## Summary: Current vs. Potential Data Exposure

| Metric | Currently Exposed | Status | Opportunity |
|--------|------------------|--------|-------------|
| Ecoregion + countries | ✅ Yes | Displayed in modal | — |
| Climate (temp, precip) | ✅ Yes | Displayed in modal | Expand to show all 19 BIO vars |
| Soil (pH, texture) | ✅ Yes | Displayed in modal | Expand to clay%, sand%, OC |
| Elevation | ✅ Yes | In location object | Could emphasize in envelope |
| Managed forest probability | ⚠️ Computed but not exposed | Hidden in `query_params` | Display as badge + context |
| Canopy height metrics | ⚠️ Computed but not exposed | Hidden in Python service | Display in new "Structure" card |
| Change detection (CCDC) | ⚠️ Computed but not exposed | Hidden in Python service | Display disturbance timeline |
| Embedding homogeneity | ⚠️ Returned but not displayed | In `location_context` | Display as uniformity meter |
| SINR metadata | ⚠️ Computed but not exposed | Hidden in `query_params` | Display model version + timing |
| 35 SINR env features | ❌ Not passed through | Lost at Python→Backend | Expose top 10-15 in expandable |
| Multi-signal weights | ✅ Yes | Returned per species | Already shown in signal breakdown |

---

**This analysis provides the foundation for designing a comprehensive "environmental envelope" UI layer that surfaces the rich environmental context already computed by the prediction system.**
