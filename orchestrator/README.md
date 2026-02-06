# Orchestrator - Location Predictor Services

This directory contains Python services for AlphaEarth habitat prediction.

## 🚀 Main Service (Port 5002)

### `location_predictor_FIXED.py` ⭐ **USE THIS ONE**

**Purpose**: Real-time AlphaEarth embedding sampling for clicked map locations

**Features**:
- Samples 64-D embeddings from Google's AlphaEarth dataset
- Tries multiple years (2024, 2023, 2022, etc.) for data availability
- Falls back to realistic simulated data when AlphaEarth unavailable
- Provides `/sample` endpoint required by frontend habitat prediction feature

**Endpoints**:
- `POST /sample` - Sample location and return embedding
- `GET /health` - Health check
- `GET /test-amazon` - Test Amazon rainforest locations

**Usage**:
```bash
python3 location_predictor_FIXED.py
# Runs on http://localhost:5002
```

**When to use**: Always use this for local development with habitat prediction

---

## 📁 Other Service Versions

### `location_predictor_service.py`
- Original version (Oct 28, 9:47 AM)
- Uses `.reduceRegion()` sampling method
- Less reliable than FIXED version

### `location_predictor_multiyear.py`
- Multi-year fallback logic
- Intermediate version before FIXED

### `location_predictor_hybrid.py`
- Experimental hybrid approach
- Not recommended for production use

### `location_predictor_DEMO.py`
- Demo/testing version
- Always returns simulated data

### `location_predictor_service_nodebug.py`
- Version without debug logging
- Production-oriented but less useful for development

---

## ⚠️ Important Notes

1. **Port Conflict**: Only ONE service can run on port 5002 at a time
   - This service conflicts with `treekipedia/python-microservice/api_only.py`
   - GraphFlow/ontology service also uses port 5002
   - Choose based on what you need:
     - Habitat prediction → Use `location_predictor_FIXED.py`
     - Ontology generation → Use `python-microservice/api_only.py`

2. **GEE Authentication**:
   - Requires Google Earth Engine authentication
   - Project: `treekipedia-476404`
   - Run `python3 ../test_ee_simple.py` to verify auth

3. **AlphaEarth Coverage**:
   - Global coverage but gaps exist
   - Water bodies return no data
   - Urban areas may have incomplete data
   - Service automatically falls back to simulated data

4. **Fallback Behavior**:
   - Real AlphaEarth data is ALWAYS preferred
   - Simulated data is only used when necessary
   - Frontend displays `demo_mode: true` when using simulated data

---

## 🔧 Dependencies

```bash
pip install flask flask-cors earthengine-api numpy
```

See `requirements.txt` for complete list.

---

## 📊 Related Files

- **Frontend**: `treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx`
- **Backend**: `treekipedia/backend/controllers/embeddings.js` (prediction endpoint)
- **Database**: `species_alphaearth_centroids` table (100 species, 500 centroids)
- **Extraction scripts**: `../silvi-open-gee-temporal-extraction/`

---

## 🐛 Troubleshooting

**Service won't start**:
```bash
# Check if port is in use
lsof -ti:5002

# Kill existing process
lsof -ti:5002 | xargs kill

# Restart
python3 location_predictor_FIXED.py
```

**GEE authentication errors**:
```bash
# Test GEE connection
cd ..
python3 test_ee_simple.py

# Re-authenticate if needed
earthengine authenticate
```

**No data returned**:
- Normal for water/urban areas
- Service will use simulated data
- Check logs: `/tmp/location-predictor.log`

---

**Last Updated**: November 5, 2025
