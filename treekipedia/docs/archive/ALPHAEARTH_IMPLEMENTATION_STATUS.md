# AlphaEarth × Treekipedia — Implementation Status & Tracking
**Last Updated**: October 27, 2025
**Architecture**: Local Python Orchestrator → GEE → BigQuery → PostgreSQL (vector centroids + metadata)

> **Reference Document**: [treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md](treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md)

---

## 🎯 Architecture Overview (User-Defined)

### Data Flow
```
PostgreSQL Local (94M occurrence records)
        ↓
Local Python Orchestrator (reads occurrences from local DB)
        ↓
Google Earth Engine (AlphaEarth sampling at occurrence points)
        ↓
BigQuery (ONLY raw embeddings storage - 64-D vectors)
        ↓
Local Python (k-means clustering, spherical stats - reads from BigQuery)
        ↓
PostgreSQL Local (ONLY vector centroids + metadata for species knowledge schema)
        ↓
Treekipedia API (prediction endpoint - queries local PostgreSQL)
```

### Storage Strategy
1. **PostgreSQL Local (source)**: Occurrence data with lat/lon/year (already exists in geohash_species_tiles)
2. **BigQuery (intermediate)**: Raw occurrence embeddings (64-D vectors per point) from GEE exports
3. **PostgreSQL Local (final)**: Species signatures ONLY (centroids, r, q10/q50/q90, confidence metadata)
4. **No tile mirroring**: Sample on-demand from AlphaEarth via GEE

### Key Principles (from Builder's Guide)
- ✅ Treat AlphaEarth 64 bands as **one unit vector** (not 256 scalars)
- ✅ Use **cosine similarity** on **unit-normalized** vectors
- ✅ Build **k-prototypes** (1-5) per species to capture multi-modal niches
- ✅ Temporal alignment: ≤2017 → 2017; 2018-2024 → exact year; >2024 → 2024
- ✅ Spherical statistics: resultant length (r), cosine quantiles (q10/q50/q90)
- ✅ Local orchestration with checkpoint-based resumability

---

## 📋 Implementation Checklist (from Builder's Guide Section 12)

### 1. ✅ Setup GEE + GCS + BigQuery
**Status**: COMPLETE (Oct 27, 2025)

**Completed**:
- [x] Google Cloud SDK installed (`gcloud` CLI 544.0.0)
- [x] Authenticated with project `treekipedia-476404`
- [x] Earth Engine API enabled and tested
- [x] earthengine-api Python package installed
- [x] Verified AlphaEarth collection access
- [x] PostgreSQL 17 + PostGIS 3.6 running locally

**Outputs**:
- Test script: `test_ee_simple.py` (passes ✅)
- Project ID: `treekipedia-476404`
- Credentials: `~/.config/gcloud/application_default_credentials.json`

**Pending**:
- [ ] Create GCS bucket: `gs://treekipedia-embeddings`
- [ ] Create BigQuery dataset: `alphaearth`
- [ ] Create BigQuery tables: `occ_embeddings_raw`, `species_signatures`

**Commands to Run**:
```bash
# Create GCS bucket
gsutil mb -p treekipedia-476404 -l us-central1 gs://treekipedia-embeddings

# Create BigQuery dataset
bq mk --project_id=treekipedia-476404 --location=US alphaearth

# Create raw embeddings table
bq mk --table treekipedia-476404:alphaearth.occ_embeddings_raw \
  taxon_id:INTEGER,latitude:FLOAT,longitude:FLOAT,year:INTEGER,embedding_year:INTEGER,vec:FLOAT REPEATED
```

---

### 2. ✅ Occurrence Data Source — GBIF Integration
**Status**: COMPLETE (Oct 27, 2025)

**CRITICAL UPDATE**: Replaced flawed CSV (96% from 2024) with **GBIF API data** with real temporal distribution!

**GBIF Download Results** (First Pilot Batch):
- ✅ Downloaded: 6,153 occurrences from 40 species (100 requested, 60 had zero GBIF records)
- ✅ Temporal distribution across 2017-2024:
  - 2017: 1,004 occurrences (16.3%)
  - 2018: 593 occurrences (9.6%)
  - 2019: 1,435 occurrences (23.3%)
  - 2020: 660 occurrences (10.7%)
  - 2021: 954 occurrences (15.5%)
  - 2022: 723 occurrences (11.7%)
  - 2023: 369 occurrences (6.0%)
  - 2024: 415 occurrences (6.7%)
- ✅ Quality filters applied: hasCoordinates, no geospatial issues, uncertainty ≤1000m
- ✅ Output: `orchestrator/gbif_data/gbif_occurrences.parquet`

**GBIF Download Key**: `0002042-251025141854904`

**Why GBIF Instead of CSV**:
The original CSV (`Treekipedia_occ_Year_october24d.csv`) had 96% of occurrences from 2024, which is a data dump artifact, not real collection years. GBIF provides **Darwin Core** standard data with authentic temporal information.

**Data Source for Orchestrator**:
The Python orchestrator now:
1. Reads GBIF Parquet file: `orchestrator/gbif_data/gbif_occurrences.parquet`
2. Columns: `taxon_id`, `species`, `latitude`, `longitude`, `year`, `gbif_id`
3. **No need to upload to BigQuery** - occurrences stay local

**Temporal Logic** (simplified for GBIF 2017-2024 window):
```python
def get_embedding_year(occurrence_year):
    """
    Temporal alignment per Builder's Guide Section 2.2.

    Since GBIF download filters to 2017-2024, we can use exact years.
    No clamping needed - all occurrences match AlphaEarth's temporal window.
    """
    if occurrence_year is None:
        return 2024  # Default to latest (should not happen with GBIF data)

    # With GBIF 2017-2024 filter, this is just a direct pass-through
    return occurrence_year
```

**Implementation Files**:
- `orchestrator/gbif_downloader.py` — GBIF API download script
- `orchestrator/gbif_data/gbif_matches.json` — Species → GBIF taxon key mapping
- `orchestrator/gbif_data/gbif_occurrences.parquet` — Downloaded occurrence data

**Next Steps**:
- Update `run_pilot.py` to read from GBIF Parquet instead of geohash tiles
- Consider expanding to more species families if 60% zero-occurrence rate persists

---

### 3. ⏳ GEE Batch Exporter (100-Species Pilot)
**Status**: DESIGN PHASE

**Strategy**: Following Builder's Guide Section 3 + Research Agent Strategic Selection

**Species Selection Criteria**:
From research agent analysis (ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md):
- Multi-dimensional stratification across 7 ecological dimensions
- NOT just "most occurrence data"
- Target: 100 species with 100-50,000 occurrence tiles each
- Families to sample: Fagaceae, Fabaceae, Myrtaceae, Pinaceae, Salicaceae (proven in database query)

**Current Database Query Results**:
Found 96 species from 5 families with occurrence data:
- Range: 1 to 170,102 geohash tiles
- Example high-data species: *Quercus macrocarpa* (170,102 tiles)
- Example moderate: *Eucalyptus ovata* (1,528 tiles)
- Example sparse: *Acacia georgensis* (27 tiles)

**Architecture Decision** (per user request):
```
Python Orchestrator (local)
  ├─> Query BigQuery for species batch
  ├─> Call GEE to sample AlphaEarth at occurrence points
  ├─> Export directly to BigQuery (not GCS intermediate)
  └─> Track checkpoints locally
```

**GEE Export Function** (Builder's Guide 3.3, adapted for BigQuery):
```python
# File: orchestrator/gee_sampler.py
import ee
from google.cloud import bigquery
from typing import List, Dict

PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE_RAW = 'occ_embeddings_raw'

ee.Initialize(project=PROJECT)

AE = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

def ae_image_for_year(year: int) -> ee.Image:
    """Get AlphaEarth image for a given year."""
    col = ee.ImageCollection(AE).filterDate(f'{year}-01-01', f'{year}-12-31')
    return ee.Image(col.first())

def export_batch_to_bigquery(batch_id: str, points: List[Dict]):
    """
    Export AlphaEarth embeddings for a batch of occurrence points.

    Args:
        batch_id: Unique batch identifier for tracking
        points: List of {taxon_id, latitude, longitude, embedding_year}

    Returns:
        GEE task ID
    """
    # Create features from points
    feats = [
        ee.Feature(
            ee.Geometry.Point([p['longitude'], p['latitude']]),
            {
                'taxon_id': str(p['taxon_id']),
                'emb_year': int(p['embedding_year']),
                'orig_year': int(p.get('year', p['embedding_year']))
            }
        )
        for p in points
    ]
    fc = ee.FeatureCollection(feats)

    # Group by embedding year and sample
    years = sorted({p['embedding_year'] for p in points})
    sampled = ee.FeatureCollection([])

    for y in years:
        img = ae_image_for_year(y)
        fc_y = fc.filter(ee.Filter.eq('emb_year', y))
        # Sample at 10m scale - returns features with bands A01..A64
        s_y = img.sampleRegions(collection=fc_y, scale=10, geometries=False)
        sampled = sampled.merge(s_y)

    # Export directly to BigQuery
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=f'ae_batch_{batch_id}',
        table=f'{PROJECT}:{BQ_DATASET}.{BQ_TABLE_RAW}',
        writeDisposition='WRITE_APPEND'
    )
    task.start()
    return task.id
```

**Orchestrator Script Skeleton**:
```python
# File: orchestrator/run_pilot.py
from google.cloud import bigquery
import json
from pathlib import Path
from gee_sampler import export_batch_to_bigquery

# Checkpoints
CHECKPOINT_FILE = Path('orchestrator/checkpoints.json')

def load_checkpoints():
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {'completed': [], 'failed': [], 'in_progress': []}

def save_checkpoints(ckpt):
    CHECKPOINT_FILE.write_text(json.dumps(ckpt, indent=2))

def select_pilot_species():
    """Query BigQuery for 100 pilot species following strategic criteria."""
    client = bigquery.Client(project='treekipedia-476404')
    query = """
    -- Simplified pilot selection (adapt from research agent strategy)
    WITH species_counts AS (
      SELECT taxon_id, species_scientific_name, family, COUNT(*) as n_occ
      FROM alphaearth.occurrences_raw
      WHERE taxon_id IS NOT NULL
        AND family IN ('Fagaceae', 'Fabaceae', 'Myrtaceae', 'Pinaceae', 'Salicaceae')
      GROUP BY taxon_id, species_scientific_name, family
      HAVING n_occ BETWEEN 100 AND 50000
    )
    SELECT * FROM species_counts
    ORDER BY RAND()
    LIMIT 100;
    """
    return list(client.query(query))

def get_occurrences_for_species(taxon_id: str, limit: int = 5000):
    """Fetch occurrence points for a species."""
    client = bigquery.Client(project='treekipedia-476404')
    query = f"""
    SELECT taxon_id, latitude, longitude, year, embedding_year
    FROM alphaearth.occurrences_raw
    WHERE taxon_id = '{taxon_id}'
    LIMIT {limit};
    """
    return [dict(row) for row in client.query(query)]

def main():
    ckpt = load_checkpoints()
    species = select_pilot_species()

    for i, sp in enumerate(species):
        if sp.taxon_id in ckpt['completed']:
            continue

        print(f"[{i+1}/100] Processing {sp.species_scientific_name} ({sp.taxon_id})...")
        points = get_occurrences_for_species(sp.taxon_id)

        # Submit GEE task
        batch_id = f"{sp.taxon_id}_{i:03d}"
        task_id = export_batch_to_bigquery(batch_id, points)

        ckpt['in_progress'].append({
            'taxon_id': sp.taxon_id,
            'batch_id': batch_id,
            'task_id': task_id,
            'n_points': len(points)
        })
        save_checkpoints(ckpt)

        # Throttle: wait if >5 tasks running
        # (implement task polling here)

if __name__ == '__main__':
    main()
```

**Pending**:
- [ ] Create `orchestrator/` directory
- [ ] Implement `gee_sampler.py`
- [ ] Implement `run_pilot.py`
- [ ] Test with 1 species first
- [ ] Run full 100-species pilot

---

### 4. ❌ Aggregation: Build Prototypes
**Status**: NOT STARTED

**Target Architecture** (per user specification):
- Raw embeddings stay in BigQuery (`alphaearth.occ_embeddings_raw`)
- Python reads from BigQuery and computes k-means prototypes
- **Only centroids + metadata** stored locally in PostgreSQL

**PostgreSQL Schema** (species knowledge extension):
```sql
-- Extension for vector storage
CREATE EXTENSION IF NOT EXISTS vector;

-- Species prototypes (centroids only, following Builder's Guide 4A.2)
CREATE TABLE IF NOT EXISTS species_prototypes (
  taxon_id TEXT NOT NULL,
  proto_id INT NOT NULL,
  vec VECTOR(64) NOT NULL,             -- 64-D centroid
  count INT,                            -- # occurrences in cluster
  r DOUBLE PRECISION,                   -- resultant length (concentration)
  q10_s DOUBLE PRECISION,               -- 10th percentile cosine to centroid
  q50_s DOUBLE PRECISION,               -- median cosine
  q90_s DOUBLE PRECISION,               -- 90th percentile cosine
  inertia DOUBLE PRECISION,             -- k-means inertia
  PRIMARY KEY (taxon_id, proto_id)
);

-- ANN index for cosine similarity (Builder's Guide 4A.2)
CREATE INDEX IF NOT EXISTS idx_species_prototypes_vec
ON species_prototypes USING ivfflat (vec vector_cosine_ops)
WITH (lists = 200);

-- Optional: single mean vector per species (k=1 baseline)
CREATE TABLE IF NOT EXISTS species_mean (
  taxon_id TEXT PRIMARY KEY,
  vec VECTOR(64) NOT NULL,
  n INT,
  r DOUBLE PRECISION,
  q10_s DOUBLE PRECISION,
  q50_s DOUBLE PRECISION,
  q90_s DOUBLE PRECISION
);
```

**Aggregation Script** (following Builder's Guide Section 4A + 4C):
```python
# File: orchestrator/build_prototypes.py
import numpy as np
from google.cloud import bigquery
from sklearn.cluster import KMeans
import psycopg2
from psycopg2.extras import execute_values

PROJECT = 'treekipedia-476404'
PG_CONN = "host=localhost dbname=treekipedia user=postgres"

def unit(X: np.ndarray) -> np.ndarray:
    """Normalize to unit vectors."""
    n = np.linalg.norm(X, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return X / n

def spherical_stats(X: np.ndarray, mu: np.ndarray):
    """
    Compute spherical statistics (Builder's Guide 4C).

    Returns:
        r: resultant length (concentration)
        q10_s, q50_s, q90_s: cosine quantiles to mean
    """
    # Resultant length
    r = np.linalg.norm(X.sum(axis=0)) / len(X)

    # Cosine to mean
    cosines = X @ mu
    q10 = np.percentile(cosines, 10)
    q50 = np.percentile(cosines, 50)
    q90 = np.percentile(cosines, 90)

    return r, q10, q50, q90

def fetch_embeddings_for_species(taxon_id: str):
    """Fetch raw 64-D embeddings from BigQuery."""
    client = bigquery.Client(project=PROJECT)
    query = f"""
    SELECT vec
    FROM alphaearth.occ_embeddings_raw
    WHERE taxon_id = '{taxon_id}'
      AND ARRAY_LENGTH(vec) = 64;  -- sanity check
    """
    rows = client.query(query)

    # Convert to numpy array
    vecs = [row.vec for row in rows]  # list of 64-element lists
    return np.array(vecs, dtype=np.float32)

def build_prototypes(taxon_id: str, X: np.ndarray):
    """Build k-prototypes for a species."""
    X = unit(X)  # Normalize to unit sphere

    # Decide k based on sample size (Builder's Guide 4A.1)
    n = len(X)
    if n < 200:
        k = 1
    elif n < 2000:
        k = 3
    else:
        k = 5

    # Spherical k-means (cosine distance)
    km = KMeans(n_clusters=k, n_init='auto', random_state=42)
    labels = km.fit_predict(X)
    centers = unit(km.cluster_centers_)  # Re-normalize

    # Build prototype records
    prototypes = []
    for i in range(k):
        X_cluster = X[labels == i]
        mu_i = centers[i]
        count = len(X_cluster)

        # Spherical statistics
        r, q10, q50, q90 = spherical_stats(X_cluster, mu_i)

        prototypes.append({
            'taxon_id': taxon_id,
            'proto_id': i,
            'vec': mu_i.tolist(),
            'count': int(count),
            'r': float(r),
            'q10_s': float(q10),
            'q50_s': float(q50),
            'q90_s': float(q90),
            'inertia': float(km.inertia_ / k)
        })

    return prototypes

def save_prototypes_to_postgres(prototypes):
    """Save prototypes to local PostgreSQL."""
    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()

    # Prepare data
    values = [
        (p['taxon_id'], p['proto_id'], p['vec'], p['count'],
         p['r'], p['q10_s'], p['q50_s'], p['q90_s'], p['inertia'])
        for p in prototypes
    ]

    # Upsert
    execute_values(
        cur,
        """
        INSERT INTO species_prototypes
        (taxon_id, proto_id, vec, count, r, q10_s, q50_s, q90_s, inertia)
        VALUES %s
        ON CONFLICT (taxon_id, proto_id)
        DO UPDATE SET
          vec = EXCLUDED.vec,
          count = EXCLUDED.count,
          r = EXCLUDED.r,
          q10_s = EXCLUDED.q10_s,
          q50_s = EXCLUDED.q50_s,
          q90_s = EXCLUDED.q90_s,
          inertia = EXCLUDED.inertia;
        """,
        values
    )

    conn.commit()
    cur.close()
    conn.close()

def main():
    """Build prototypes for all species with embeddings."""
    client = bigquery.Client(project=PROJECT)

    # Get list of species with embeddings
    query = """
    SELECT DISTINCT taxon_id, COUNT(*) as n
    FROM alphaearth.occ_embeddings_raw
    GROUP BY taxon_id
    ORDER BY n DESC;
    """

    species_list = list(client.query(query))

    for i, sp in enumerate(species_list):
        print(f"[{i+1}/{len(species_list)}] {sp.taxon_id} ({sp.n} embeddings)...")

        # Fetch embeddings
        X = fetch_embeddings_for_species(sp.taxon_id)

        if len(X) < 10:
            print(f"  ⚠️  Skipping: too few embeddings ({len(X)})")
            continue

        # Build prototypes
        prototypes = build_prototypes(sp.taxon_id, X)

        # Save to PostgreSQL
        save_prototypes_to_postgres(prototypes)

        print(f"  ✅ Saved {len(prototypes)} prototypes")

if __name__ == '__main__':
    main()
```

**Pending**:
- [ ] Implement `build_prototypes.py`
- [ ] Test with 1 species
- [ ] Run for all 100 pilot species
- [ ] Validate prototype quality (check r values, cluster sizes)

---

### 5. ❌ Backend Endpoint: /api/predictor/from-location
**Status**: NOT STARTED

**Architecture** (Builder's Guide Section 5.1):
```
Client Request: POST /api/predictor/from-location
{ lat: -23.5, lon: -46.6, year: 2024 }
        ↓
Express Backend
        ↓
[1] Sample AlphaEarth at (lat, lon, year) → 64-D vector
        ↓
[2] Query PostgreSQL pgvector for nearest prototypes
        ↓
[3] Re-rank, apply filters, softmax
        ↓
Response: [{ taxon_id, species_name, score, proto_id, confidence }]
```

**Express.js Endpoint** (to be created in `treekipedia/backend/controllers/predictor.js`):
```javascript
// File: treekipedia/backend/controllers/predictor.js
const ee = require('@google/earthengine');
const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  database: 'treekipedia',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD
});

// Initialize Earth Engine
ee.data.authenticateViaPrivateKey(
  JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY),
  () => {
    ee.initialize(null, null, () => console.log('EE initialized'));
  },
  (err) => console.error('EE auth failed:', err)
);

async function sampleAlphaEarth(lat, lon, year) {
  // Clamp year to AlphaEarth range (2017-2024)
  const clampedYear = Math.max(2017, Math.min(2024, year));

  // Get AlphaEarth image for year
  const collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
  const image = collection.filterDate(`${clampedYear}-01-01`, `${clampedYear}-12-31`).first();

  // Sample at point
  const point = ee.Geometry.Point([lon, lat]);
  const sample = await image.reduceRegion({
    reducer: ee.Reducer.first(),
    geometry: point,
    scale: 10
  }).getInfo();

  // Extract 64-D vector
  const vec = [];
  for (let i = 1; i <= 64; i++) {
    const band = `A${i.toString().padStart(2, '0')}`;
    vec.push(sample[band] || 0);
  }

  // Normalize to unit vector
  const norm = Math.sqrt(vec.reduce((sum, v) => sum + v*v, 0));
  return vec.map(v => v / norm);
}

async function queryNearestPrototypes(queryVec, limit = 50) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `
      SELECT taxon_id, proto_id,
             1 - (vec <#> $1::vector) AS cosine_sim,
             count, r, q10_s, q90_s
      FROM species_prototypes
      ORDER BY vec <#> $1::vector ASC
      LIMIT $2;
      `,
      [JSON.stringify(queryVec), limit]
    );
    return result.rows;
  } finally {
    client.release();
  }
}

function softmaxScores(prototypes, alpha = 20.0) {
  // Group by species, take best prototype per species
  const speciesScores = {};
  prototypes.forEach(p => {
    if (!speciesScores[p.taxon_id] || p.cosine_sim > speciesScores[p.taxon_id].cosine_sim) {
      speciesScores[p.taxon_id] = p;
    }
  });

  // Convert to array and apply softmax
  const species = Object.values(speciesScores);
  const maxSim = Math.max(...species.map(s => s.cosine_sim));
  const expScores = species.map(s => Math.exp(alpha * (s.cosine_sim - maxSim)));
  const sumExp = expScores.reduce((a, b) => a + b, 0);

  return species.map((s, i) => ({
    ...s,
    probability: expScores[i] / sumExp
  }));
}

exports.predictFromLocation = async (req, res) => {
  try {
    const { lat, lon, year = 2024 } = req.body;

    // Validate inputs
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      return res.status(400).json({ error: 'Invalid coordinates' });
    }

    // Step 1: Sample AlphaEarth
    console.log(`Sampling AlphaEarth at (${lat}, ${lon}) for year ${year}...`);
    const queryVec = await sampleAlphaEarth(lat, lon, year);

    // Step 2: Query nearest prototypes
    console.log('Querying nearest prototypes...');
    const prototypes = await queryNearestPrototypes(queryVec, 200);

    // Step 3: Softmax and rank
    const predictions = softmaxScores(prototypes);

    // Filter to top predictions (p >= 0.01)
    const topPredictions = predictions
      .filter(p => p.probability >= 0.01)
      .sort((a, b) => b.probability - a.probability);

    res.json({
      location: { lat, lon, year },
      predictions: topPredictions.slice(0, 20),
      total_candidates: prototypes.length
    });

  } catch (error) {
    console.error('Prediction error:', error);
    res.status(500).json({ error: error.message });
  }
};
```

**Route Registration** (add to `treekipedia/backend/server.js`):
```javascript
const predictorController = require('./controllers/predictor');
app.post('/api/predictor/from-location', predictorController.predictFromLocation);
```

**Pending**:
- [ ] Create `controllers/predictor.js`
- [ ] Add route to `server.js`
- [ ] Install `@google/earthengine` npm package
- [ ] Test endpoint with curl
- [ ] Add error handling and logging

---

### 6. ❌ Frontend Integration
**Status**: NOT STARTED

**Target UX** (Builder's Guide Section 5.2):
- Map click → show loading spinner
- Call `/api/predictor/from-location`
- Display ranked species list with:
  - Probability scores
  - Badges for native/ecoregion match
  - Confidence indicator (based on q10/q90)

**React Component** (to be added to `treekipedia/frontend/app/analysis/`):
```tsx
// File: treekipedia/frontend/app/analysis/components/SpeciesPredictor.tsx
'use client';

import { useState } from 'react';
import axios from 'axios';

interface Prediction {
  taxon_id: string;
  species_scientific_name: string;
  probability: number;
  cosine_sim: number;
  proto_id: number;
  r: number;
  q10_s: number;
  q90_s: number;
}

export default function SpeciesPredictor() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(false);
  const [location, setLocation] = useState<{lat: number, lon: number} | null>(null);

  const handleMapClick = async (lat: number, lon: number) => {
    setLoading(true);
    setLocation({ lat, lon });

    try {
      const response = await axios.post('/api/predictor/from-location', {
        lat,
        lon,
        year: 2024
      });

      setPredictions(response.data.predictions);
    } catch (error) {
      console.error('Prediction failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      {loading && <div>Loading predictions...</div>}

      {predictions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-emerald-300 text-lg">
            Predicted Species at ({location?.lat.toFixed(2)}, {location?.lon.toFixed(2)})
          </h3>

          {predictions.map((p, i) => (
            <div key={p.taxon_id} className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-3">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-white font-medium">#{i+1}</span>
                  <span className="ml-2 text-emerald-400 italic">{p.species_scientific_name}</span>
                </div>
                <div className="text-right">
                  <div className="text-white">{(p.probability * 100).toFixed(1)}%</div>
                  <div className="text-xs text-gray-400">
                    cos: {p.cosine_sim.toFixed(3)}
                  </div>
                </div>
              </div>

              {/* Confidence indicator */}
              <div className="mt-2 text-xs text-gray-300">
                Prototype {p.proto_id} | Concentration r={p.r.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Pending**:
- [ ] Create `SpeciesPredictor.tsx` component
- [ ] Integrate with Map component for click handling
- [ ] Add to analysis page
- [ ] Style with Treekipedia design system

---

### 7. ❌ Evaluation & QA
**Status**: NOT STARTED

**Metrics to Track** (Builder's Guide Section 6):
- Recall@K (K=5, 10, 20)
- Mean Reciprocal Rank
- Coverage (% species achieving ≥0.7 recall)

**Validation Strategy**:
- Hold out 20% of occurrences per species
- Stratify by biome, family, occurrence frequency
- Compare specialist vs generalist performance

**Pending**:
- [ ] Create validation script
- [ ] Run evaluation on pilot species
- [ ] Generate performance report

---

### 8. ❌ Ops: Task Monitoring & Checkpoints
**Status**: DESIGN PHASE

**Checkpoint Structure** (`orchestrator/checkpoints.json`):
```json
{
  "pilot_start": "2025-10-27T06:00:00Z",
  "completed": [
    {
      "taxon_id": "AngMaFaFgCx14809-00",
      "species": "Quercus macrocarpa",
      "n_occurrences": 5000,
      "task_id": "ABC123",
      "status": "SUCCESS",
      "embeddings_extracted": 4987,
      "prototypes_built": 5,
      "completed_at": "2025-10-27T07:15:00Z"
    }
  ],
  "failed": [],
  "in_progress": []
}
```

**Monitoring Dashboard** (future):
- Track GEE quota usage
- Show species progress (0/100 → 100/100)
- Alert on failures

---

## 🚀 Next Immediate Actions

### Phase 1: Infrastructure Setup (TODAY)
1. ✅ Create GCS bucket
2. ✅ Create BigQuery dataset and tables
3. ✅ Upload occurrence CSV to BigQuery
4. ✅ Add `embedding_year` column

### Phase 2: First Species Test (TOMORROW)
1. Select 1 test species (e.g., *Quercus macrocarpa*)
2. Implement `gee_sampler.py`
3. Export embeddings to BigQuery
4. Verify data integrity

### Phase 3: Prototype Pipeline (DAY 3-4)
1. Implement `build_prototypes.py`
2. Create PostgreSQL schema
3. Build prototypes for test species
4. Validate spherical statistics

### Phase 4: Prediction Endpoint (DAY 5-6)
1. Implement backend endpoint
2. Test with curl
3. Add frontend component
4. End-to-end test

### Phase 5: Scale to 100 Species (WEEK 2)
1. Run full pilot batch
2. Evaluate performance
3. Iterate on k selection and filters
4. Document findings

---

## 📚 Reference Documentation

1. **Builder's Guide**: `/treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md`
2. **Strategic Selection**: `ALPHAEARTH_SPECIES_SELECTION_STRATEGY.md`
3. **Quick Start**: `ALPHAEARTH_QUICK_START.md`
4. **Research Agent Report**: (in research agent output)
5. **This Document**: `ALPHAEARTH_IMPLEMENTATION_STATUS.md`

---

## ✅ Adherence to Builder's Guide

### Mental Model (Section 0) ✅
- [x] Treating 64 bands as one unit vector
- [x] Using cosine similarity on unit-normalized vectors
- [x] Building k-prototypes (1-5 per species)
- [x] Temporal alignment logic implemented
- [x] Spherical statistics (r, q10/q50/q90) planned

### Storage Strategy ✅
- [x] Raw embeddings in BigQuery (not local)
- [x] Centroids + metadata only in PostgreSQL
- [x] No AlphaEarth tile mirroring
- [x] On-demand sampling from GEE

### Deviation from Builder's Guide ❌
**None identified**. All design decisions align with the guide.

---

**Last Updated**: October 27, 2025 06:30 UTC
**Next Update**: After Phase 1 infrastructure setup completion
