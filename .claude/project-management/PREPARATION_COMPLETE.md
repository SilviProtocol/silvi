# Preparation Complete: Habitat Prediction Pipeline

**Date:** 2026-01-21
**Status:** Ready for clustering once GEE tasks complete

## What We Did While Waiting

### 1. PostgreSQL Schema (COMPLETED)
**File:** [treekipedia/database/migrations/007_habitat_centroids.sql](../../treekipedia/database/migrations/007_habitat_centroids.sql)

Created and applied migration with:

| Table | Purpose | Status |
|-------|---------|--------|
| `species_habitat_centroids` | 3-10 cluster centroids per species with 64-D vectors | ✅ Created |
| `species_elevation_profiles` | Pre-aggregated elevation stats per species | ✅ Created |
| `habitat_prediction_cache` | Cache for recent predictions | ✅ Created |
| `species_habitat_summary` | View for quick habitat overview | ✅ Created |

**Functions created:**
- `find_similar_habitats(query_vector, elevation_min, elevation_max, limit)` - pgvector cosine similarity search
- `get_species_habitat_match(taxon_id, query_vector)` - Check specific species match

**pgvector installed:** v0.8.1 via Homebrew

### 2. Clustering Pipeline (READY TO RUN)
**File:** [orchestrator/cluster_habitat_centroids.py](../../orchestrator/cluster_habitat_centroids.py)

Python script that:
1. Connects to BigQuery (`treekipedia-479918.species_data.alphaearth_embeddings_v4`)
2. For each species with ≥10 occurrences:
   - Fetches 64-D AlphaEarth embeddings
   - Uses silhouette score to find optimal K (3-10 clusters)
   - K-means clustering to create habitat centroids
   - Computes cluster statistics (elevation, treecover, forest loss)
   - Saves to PostgreSQL with pgvector

**Usage:**
```bash
python orchestrator/cluster_habitat_centroids.py --min-occurrences 10 --batch-size 100
```

### 3. Prediction API Routes (READY TO INTEGRATE)
**File:** [treekipedia/backend/routes/prediction.js](../../treekipedia/backend/routes/prediction.js)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/prediction/sample` | GET | Get AlphaEarth embedding for lat/lon |
| `/api/prediction/predict` | GET | Scientific habitat suitability (S score) |
| `/api/prediction/recommend` | GET | Contextual recommendations (SAFE-B) |
| `/api/prediction/species/:taxon_id/habitat-match` | GET | Check specific species match |
| `/api/prediction/health` | GET | Service health check |

**Key parameters:**
- `lat`, `lon` - Location (required)
- `country_code` - For native status filtering
- `restoration_goal` - `erosion_control|soil_fertility|biodiversity|carbon|timber`
- `elevation_tolerance` - ± meters (default 500)
- `min_similarity` - Cosine threshold (default 0.7)

## Next Steps (When GEE Tasks Complete)

### Step 1: Run Clustering Pipeline
```bash
cd /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open

# Install Python dependencies
pip install google-cloud-bigquery psycopg2-binary pgvector scikit-learn numpy

# Run clustering
python orchestrator/cluster_habitat_centroids.py --min-occurrences 10

# Estimated time: ~2-4 hours for 15,000+ species
```

### Step 2: Integrate Prediction Routes
Add to `treekipedia/backend/server.js`:
```javascript
const predictionRoutes = require('./routes/prediction');
app.use('/api/prediction', predictionRoutes);
```

### Step 3: Rebuild IVFFlat Index
After data is loaded, rebuild the index for better performance:
```sql
DROP INDEX idx_centroid_vector;
CREATE INDEX idx_centroid_vector ON species_habitat_centroids
    USING ivfflat (centroid_vector vector_cosine_ops) WITH (lists = 300);
```

### Step 4: Test the Endpoints
```bash
# Test habitat prediction
curl "http://localhost:5001/api/prediction/predict?lat=-1.2921&lon=36.8219"

# Test species-specific match
curl "http://localhost:5001/api/prediction/species/wfo-0000723513/habitat-match?lat=-1.2921&lon=36.8219"
```

## Data Coverage Summary

| Source | Records | Species | Status |
|--------|---------|---------|--------|
| BigQuery (Phase 1) | 3.36M | 15,979 | ✅ Complete |
| BigQuery (remaining) | ~6.2K | 2,845 | ⏳ 4 GEE tasks |
| Phase 2 (pre-2017) | 72.2M | 39,933 | 📋 Not started |
| PostgreSQL species | - | 67,743 | ✅ Available |
| With occurrences | - | 48,129 | ✅ Available |

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                     User Request (lat, lon)                     │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Location Predictor (Python 5002)               │
│  • Calls GEE for AlphaEarth embedding                          │
│  • Returns 64-D vector + elevation + treecover                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Prediction API (Node 5001)                   │
│  • /predict - Pure suitability (pgvector cosine similarity)    │
│  • /recommend - SAFE-B scoring (native status, goals)          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + pgvector                        │
│  • species_habitat_centroids (64-D vectors, IVFFlat index)     │
│  • species table (taxonomy, native status, traits)             │
│  • species_elevation_profiles (pre-aggregated stats)           │
└─────────────────────────────────────────────────────────────────┘
```

## Files Created This Session

| File | Purpose |
|------|---------|
| `orchestrator/cluster_habitat_centroids.py` | Clustering pipeline |
| `treekipedia/database/migrations/007_habitat_centroids.sql` | PostgreSQL schema |
| `treekipedia/backend/routes/prediction.js` | API endpoints |
| This document | Status summary |
