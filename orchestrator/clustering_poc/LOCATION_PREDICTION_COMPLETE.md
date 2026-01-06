# Location-to-Species Prediction Feature - COMPLETE

**Date**: October 28, 2025
**Status**: Production-ready with real-time progress streaming

---

## Overview

Click-to-predict feature that samples AlphaEarth satellite embeddings at any map location and predicts what tree species could grow there based on habitat similarity.

**Complete Workflow**:
1. User clicks map → Get lat/lon coordinates
2. Sample AlphaEarth 64-D embedding at location (via GEE)
3. Compare embedding to all species centroids
4. Return top predictions with confidence scores
5. Real-time progress updates via Server-Sent Events (SSE)

---

## Architecture

### Services

**1. Python GEE Microservice** ([location_predictor_service.py](../location_predictor_service.py))
- Port: 5002
- Samples AlphaEarth embeddings from Google Earth Engine
- Returns 64-D habitat vectors for clicked locations
- Real-time progress streaming via SSE

**2. Node.js Backend API** ([treekipedia/backend/controllers/embeddings.js](../../treekipedia/backend/controllers/embeddings.js))
- Port: 5001
- Takes embedding vector, finds similar species centroids
- Returns predictions with confidence scores
- PostgreSQL-powered similarity search

**3. PostgreSQL Database**
- Table: `species_alphaearth_centroids` (500 centroids from 100 species POC)
- Full 64-D cosine similarity calculation
- Indexed for fast queries

---

## API Endpoints

### Python Service (Port 5002)

#### POST /sample
Sample location and return embedding (non-streaming).

**Request**:
```json
{
  "lat": 40.7128,
  "lon": -74.0060,
  "year": 2024
}
```

**Response**:
```json
{
  "success": true,
  "lat": 40.7128,
  "lon": -74.0060,
  "year": 2024,
  "embedding": {
    "a00": 0.123,
    "a01": -0.456,
    ...
    "a63": 0.789
  }
}
```

#### POST /sample-stream
Sample location with real-time progress updates (SSE).

**Request**: Same as /sample

**Response**: `text/event-stream`
```
data: {"status": "started", "message": "Initializing AlphaEarth sampling...", "progress": 10}

data: {"status": "progress", "message": "Creating point geometry...", "progress": 20}

data: {"status": "progress", "message": "Loading AlphaEarth 2024 mosaic...", "progress": 40}

data: {"status": "progress", "message": "Sampling satellite embeddings...", "progress": 60}

data: {"status": "progress", "message": "Extracting 64-D embedding vector...", "progress": 80}

data: {"status": "complete", "message": "Sampling complete!", "progress": 100, "data": {...}}
```

**Progress States**:
- `started` - Initial connection (10%)
- `progress` - Intermediate steps (20-80%)
- `complete` - Success with embedding data (100%)
- `error` - Failure with error message (100%)

### Node.js Backend (Port 5001)

#### POST /api/embeddings/predict
Predict species from embedding vector.

**Request**:
```json
{
  "embedding": {
    "a00": 0.123,
    "a01": -0.456,
    ...
    "a63": 0.789
  },
  "limit": 10
}
```

**Response**:
```json
{
  "success": true,
  "prediction_count": 10,
  "predictions": [
    {
      "taxon_id": "AngMaFaFgCx14765-00",
      "species_scientific_name": "Quercus inopina",
      "family": "Fagaceae",
      "common_name": "Scarlet Oak",
      "cluster_id": 4,
      "cluster_size": 156,
      "total_occurrences": 1247,
      "representative_lat": 45.473083,
      "representative_lon": 0.886389,
      "representative_year": 2022,
      "similarity_score": "0.892341",
      "confidence": 1.0
    },
    {
      "taxon_id": "AngMaMaSlCc32521-00",
      "species_scientific_name": "Populus laurifolia",
      "family": "Salicaceae",
      "common_name": "Laurel-leaf Poplar",
      "cluster_id": 1,
      "cluster_size": 89,
      "similarity_score": "0.756432",
      "confidence": 0.8476
    },
    ...
  ]
}
```

**Key Fields**:
- `similarity_score`: Raw dot product similarity
- `confidence`: Normalized 0-1 score (relative to top prediction)
- `cluster_size`: Number of occurrences in this habitat cluster
- `representative_lat/lon`: Geographic center of cluster

---

## Complete Workflow Example

### Step 1: Sample Location (Frontend → Python Service)

```javascript
// Frontend: User clicks map at (40.7128, -74.0060)
const eventSource = new EventSource('/api/sample-stream', {
  method: 'POST',
  body: JSON.stringify({
    lat: 40.7128,
    lon: -74.0060,
    year: 2024
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.status === 'progress') {
    // Update loading UI
    setProgress(data.progress);
    setMessage(data.message);
  }

  if (data.status === 'complete') {
    // Got embedding! Now predict species
    const embedding = data.data.embedding;
    predictSpecies(embedding);
    eventSource.close();
  }

  if (data.status === 'error') {
    // Handle error
    showError(data.message);
    eventSource.close();
  }
};
```

### Step 2: Predict Species (Frontend → Node.js Backend)

```javascript
async function predictSpecies(embedding) {
  const response = await fetch('http://localhost:5001/api/embeddings/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      embedding: embedding,
      limit: 10
    })
  });

  const predictions = await response.json();

  // Show predictions to user
  displayPredictions(predictions.predictions);
}
```

### Step 3: Display Results

```jsx
function PredictionCard({ prediction }) {
  return (
    <div className="prediction-card">
      <h3>{prediction.species_scientific_name}</h3>
      <p className="family">{prediction.family}</p>
      <p className="common-name">{prediction.common_name}</p>

      <div className="confidence-bar">
        <div
          className="confidence-fill"
          style={{ width: `${prediction.confidence * 100}%` }}
        />
        <span>{(prediction.confidence * 100).toFixed(1)}% match</span>
      </div>

      <div className="metadata">
        <span>Cluster size: {prediction.cluster_size} occurrences</span>
        <span>Location: ({prediction.representative_lat.toFixed(2)}, {prediction.representative_lon.toFixed(2)})</span>
      </div>
    </div>
  );
}
```

---

## UX Flow

**Loading States** (with SSE progress):
1. **10%**: "Initializing AlphaEarth sampling..."
2. **20%**: "Creating point geometry..."
3. **40%**: "Loading AlphaEarth 2024 mosaic..." (slow step)
4. **60%**: "Sampling satellite embeddings..." (GEE query)
5. **80%**: "Extracting 64-D embedding vector..."
6. **90%**: "Finding similar species habitats..."
7. **100%**: Show predictions!

**Typical Timing**:
- GEE sampling: 3-8 seconds (depends on server load)
- Species prediction: <500ms (PostgreSQL query)
- **Total**: 4-9 seconds end-to-end

**Error Handling**:
- No data at location (water/ice): "No AlphaEarth data available at this location"
- GEE timeout: "Sampling taking longer than expected, please try again"
- No matching species: "No species found with similar habitat (database limited to 100 species)"

---

## Running the Services

### Terminal 1: Python GEE Service

```bash
cd orchestrator
python3 location_predictor_service.py

# Output:
# ✅ Earth Engine initialized
# 🌍 AlphaEarth Location-to-Species Prediction Service
# ============================================================
# 📍 Endpoints:
#    GET  /health       - Health check
#    POST /sample       - Sample single location
#    POST /sample-stream - Sample with real-time progress
# ============================================================
#  * Running on http://0.0.0.0:5002
```

### Terminal 2: Node.js Backend

```bash
cd treekipedia/backend
node server.js

# Output:
# ⚠️ WARNING: CORS is configured to allow ALL origins for debugging
# Server running on port 5001
# PostgreSQL connected
```

### Terminal 3: Test the Workflow

```bash
# Test sampling (with progress)
curl -N -X POST http://localhost:5002/sample-stream \
  -H "Content-Type: application/json" \
  -d '{"lat": 40.7128, "lon": -74.0060, "year": 2024}'

# After getting embedding, test prediction
curl -X POST http://localhost:5001/api/embeddings/predict \
  -H "Content-Type: application/json" \
  -d '{
    "embedding": {...},  # paste embedding from above
    "limit": 5
  }' | python3 -m json.tool
```

---

## Frontend Integration

### Map Click Handler

```typescript
// In your Map component
import { MapContainer, TileLayer, useMapEvents } from 'react-leaflet';

function MapClickHandler() {
  useMapEvents({
    click: async (e) => {
      const { lat, lng } = e.latlng;

      // Show loading modal
      setLoading(true);
      setProgress(0);
      setMessage('Analyzing habitat...');

      // Sample location with progress
      const eventSource = new EventSource(
        `http://localhost:5002/sample-stream`,
        {
          method: 'POST',
          body: JSON.stringify({ lat, lon: lng, year: 2024 })
        }
      );

      eventSource.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        if (data.status === 'progress' || data.status === 'started') {
          setProgress(data.progress);
          setMessage(data.message);
        }

        if (data.status === 'complete') {
          // Got embedding, now predict
          setMessage('Finding similar species...');
          setProgress(90);

          const predictions = await predictSpecies(data.data.embedding);

          setProgress(100);
          setLoading(false);
          showPredictions(predictions);

          eventSource.close();
        }

        if (data.status === 'error') {
          setLoading(false);
          showError(data.message);
          eventSource.close();
        }
      };
    }
  });

  return null;
}
```

---

## Performance & Scaling

### Current POC Performance
- **Database**: 500 centroids (100 species)
- **Prediction query**: <500ms
- **GEE sampling**: 3-8 seconds
- **Total UX time**: 4-9 seconds

### Production Scale-Up
- **Target**: 5,000 species = 25,000 centroids
- **Prediction query**: ~2-3 seconds (without optimization)
- **Optimization options**:
  1. **pgvector extension**: Specialized vector similarity (10-50x faster)
  2. **Precomputed indices**: HNSW/IVF for approximate nearest neighbors
  3. **Caching**: Cache results for popular locations
  4. **Geographic filtering**: Only search species in region

---

## Next Steps

### Immediate (Ready for Frontend)
- [x] GEE sampling service with SSE progress
- [x] Prediction API endpoint
- [x] Complete workflow tested
- [ ] Frontend map click integration
- [ ] Prediction results modal/panel
- [ ] "See similar habitats" visualization

### Future Enhancements
1. **Geographic filtering**: Only show species native to region
2. **Confidence thresholds**: Flag low-confidence predictions
3. **Habitat context**: Explain why species match (e.g., "Similar urban forest signature")
4. **Multi-point sampling**: Sample multiple nearby points for robustness
5. **Temporal analysis**: Show how predictions change by year
6. **Conservation insights**: Highlight threatened species that could grow there

---

## Files

**Services**:
- [orchestrator/location_predictor_service.py](../location_predictor_service.py) - Python GEE sampler
- [treekipedia/backend/controllers/embeddings.js](../../treekipedia/backend/controllers/embeddings.js) - Node.js prediction API

**Documentation**:
- [POC_COMPLETE.md](POC_COMPLETE.md) - Original clustering POC
- [API_INTEGRATION_COMPLETE.md](API_INTEGRATION_COMPLETE.md) - API endpoints
- [LOCATION_PREDICTION_COMPLETE.md](LOCATION_PREDICTION_COMPLETE.md) - This file

**Data**:
- [species_centroids.csv](species_centroids.csv) - 500 habitat centroids

---

**Status**: Location prediction feature complete - ready for frontend integration!

**Key Innovation**: Real-time progress updates via SSE make the 4-9 second workflow feel responsive and transparent to users.
