# Treekipedia × AlphaEarth — Planetary Species Predictor (Builder’s Guide)

> **Purpose**
> A pragmatic, copy‑pasteable blueprint to build a species predictor that leverages Google’s AlphaEarth 64‑D embeddings. Two paths are covered end‑to‑end:
> 1) **Local‑first (free/near‑free)** with Postgres + pgvector (or FAISS)
> 2) **BigQuery‑centric (serverless)** with native vector search
> Plus a roadmap to upgrade into a **multi‑label neural net** when (and only when) the baseline is topped.

---

## 0) Mental model (keep this in your head while vibecoding)

- AlphaEarth gives you a **64‑D vector per 10 m pixel per year** (2017…latest). Treat the 64 bands as **one embedding**. Use **cosine similarity** on **unit‑normalized** vectors.
- For each occurrence record (lat/lon + year), sample the **matching embedding year** (≤2017 → 2017; 2018–latest → exact; >latest → latest).
- Build **per‑species prototypes** in 64‑D (not 256 scalars). Prototypes can be:
  - **k = 1** (the mean unit vector), good starter
  - **k = 2–5** (k‑means/HDBSCAN centroids) to capture **multi‑modal niches**
- At query time: get the pixel’s 64‑D vector → **nearest prototype(s)** across all species (cosine). Turn distances into probabilities with a softmax over −distance.
- Add light **filters/boosts** (native range, ecoregion, elevation) to get from “math plausible” → “ecologically sound.”

---

## 1) Setup — tools & environment

### 1.1 Accounts & SDKs
- Google Earth Engine (GEE) account + Python API
- (Option B) Google Cloud project with BigQuery + GCS
- (Option A) Local Postgres 15+ with PostGIS and **pgvector**
- Python 3.11+, Node 18+ (Treekipedia backend/frontend), `gcloud` CLI

### 1.2 Local `.env` sketch (adjust to your paths)
```bash
# GCP / GEE
GOOGLE_PROJECT=treekipedia
GCS_BUCKET=gs://treekipedia-embeddings
GEE_SERVICE_ACCOUNT=gee-runner@treekipedia.iam.gserviceaccount.com
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

# Postgres (Option A)
PGHOST=localhost
PGPORT=5432
PGDATABASE=treekipedia
PGUSER=postgres
PGPASSWORD=postgres

# BigQuery (Option B)
BQ_DATASET=alphaearth
BQ_TABLE_RAW=occ_embeddings_raw
BQ_TABLE_SIG=species_signatures
```

### 1.3 Install system deps (macOS)
```bash
brew install postgresql@15 libpq duckdb
# pgvector extension
psql -d treekipedia -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

### 1.4 Python env
```bash
uv venv && source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install earthengine-api google-cloud-storage google-cloud-bigquery pandas polars duckdb scikit-learn numpy pyproj psycopg2-binary tqdm
```

> Tip: If you’re fully local/min‑cloud, you can skip BigQuery libs.

---

## 2) Data prep — occurrences → batches

### 2.1 Occurrence table (CSV/Parquet → Postgres)
Columns we need: `taxon_id`, `latitude`, `longitude`, `year`.

```sql
-- Minimal occurrence staging table
CREATE TABLE IF NOT EXISTS occ (
  taxon_id BIGINT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  year INT
);
-- Load your CSV/Parquet however you like (COPY, pandas, etc.)
```

### 2.2 Embed year mapping (temporal clamp)
```sql
ALTER TABLE occ ADD COLUMN IF NOT EXISTS embedding_year INT;
UPDATE occ
SET embedding_year = CASE
  WHEN year <= 2017 THEN 2017
  WHEN year >= 2024 THEN 2024
  ELSE year
END;
```

### 2.3 (Optional but high impact) Spatial de‑biasing before sampling
- If a species is hyper‑clustered, cap to **N points per ~1 km cell** per species×year to reduce GEE hits.
- You can do this later too; not required to start.

### 2.4 Create batches
```sql
-- Example: 50–200 species per batch based on frequency
CREATE TEMP TABLE species_counts AS
SELECT taxon_id, COUNT(*) AS n
FROM occ GROUP BY taxon_id;

-- Pull batches in your Python orchestrator; persist a checkpoints file.
```

---

## 3) GEE sampling — extract 64‑D vectors at points

> We’ll keep GEE’s job **narrow**: sample vectors at occurrence points (per year), export in manageable shards.

### 3.1 Authorize & init GEE
```python
import ee
import json, time, math

ee.Initialize()  # uses ADC; or ee.ServiceAccountCredentials if you prefer
```

### 3.2 Helper: get AlphaEarth image for a given year
```python
AE = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

def ae_image_for_year(year: int) -> ee.Image:
    col = ee.ImageCollection(AE).filterDate(f'{year}-01-01', f'{year}-12-31')
    return ee.Image(col.first())
```

### 3.3 Sample a batch (pseudo‑code; you’ll stream points from Postgres)
```python
from typing import List, Dict

def export_batch_to_gcs(batch_id: str, points: List[Dict]):
    # points: [{lon, lat, taxon_id, embedding_year}, ...]
    feats = [ee.Feature(ee.Geometry.Point([p['longitude'], p['latitude']]),
                        {'taxon_id': int(p['taxon_id']), 'emb_year': int(p['embedding_year'])})
             for p in points]
    fc = ee.FeatureCollection(feats)

    years = sorted({p['embedding_year'] for p in points})
    sampled = ee.FeatureCollection([])
    for y in years:
        img = ae_image_for_year(y)
        fc_y = fc.filter(ee.Filter.eq('emb_year', y))
        # Designed for points; returns each feature with bands A01..A64
        s_y = img.sampleRegions(collection=fc_y, scale=10, geometries=False)
        sampled = sampled.merge(s_y)

    task = ee.batch.Export.table.toCloudStorage(
        collection=sampled,
        description=f'ae_batch_{batch_id}',
        bucket='treekipedia-embeddings',
        fileNamePrefix=f'raw/batch_{batch_id}',
        fileFormat='CSV')
    task.start()
    return task.id
```

### 3.4 Task throttle + backoff
- Keep ≤ **2–8 concurrent** GEE tasks depending on your account.
- Poll tasks; on error, requeue the shard.

---

## 4) Aggregation & signatures — **two options**

You’ll produce **species signatures** from raw samples. Here’s the fork:

### Option A — Local‑first (free/near‑free)

**Storage shape**
- `species_prototypes` table holding **k prototypes** per species: each is a **vector(64)**, plus counts/radius.
- (Optional) also keep a single **mean vector(64)** per species for quick baseline.

**4A.1 Read shard CSVs and build per‑species vectors**
```python
import polars as pl
import numpy as np
from sklearn.cluster import KMeans

BANDS = [f'A{i:02d}' for i in range(1,65)]

def unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n==0] = 1.0
    return x / n

# Read multiple CSV shards lazily
lf = pl.scan_csv('data/raw/*.csv')
# Keep only what we need
lf = lf.select(['taxon_id'] + BANDS)

df = lf.collect()  # If too big, do per species in groups()

prototypes = []  # rows: {taxon_id, proto_id, vec64[], count, inertia}
for taxon_id, g in df.group_by('taxon_id'):
    X = g[BANDS].to_numpy()
    X = unit(X)
    # Decide k based on size (cheap heuristic)
    k = 1 if len(X) < 200 else 3 if len(X) < 2000 else 5
    km = KMeans(n_clusters=k, n_init='auto', random_state=42).fit(X)
    centers = unit(km.cluster_centers_)
    counts = np.bincount(km.labels_, minlength=k)
    for i in range(k):
        prototypes.append({
            'taxon_id': int(taxon_id),
            'proto_id': int(i),
            'vec': centers[i].tolist(),
            'count': int(counts[i]),
            'inertia': float(km.inertia_/k)
        })
```

**4A.2 Postgres schema with pgvector**
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS species_prototypes (
  taxon_id BIGINT NOT NULL,
  proto_id INT NOT NULL,
  vec VECTOR(64) NOT NULL,
  count INT,
  inertia DOUBLE PRECISION,
  PRIMARY KEY (taxon_id, proto_id)
);

-- Insert from Python using psycopg2; also store a 64‑D mean per species if you like:
CREATE TABLE IF NOT EXISTS species_mean (
  taxon_id BIGINT PRIMARY KEY,
  vec VECTOR(64) NOT NULL,
  n INT
);

-- ANN index (cosine)
CREATE INDEX IF NOT EXISTS idx_species_prototypes_vec
ON species_prototypes USING ivfflat (vec vector_cosine_ops)
WITH (lists = 200);
```

**4A.3 Query: point → embedding → nearest species**

- Step 1 (server): given lat/lon/year, call GEE **`reduceRegion`** or **`sample`** to get the **64‑D vector**.
- Step 2: normalize to unit length.
- Step 3: query pgvector for top‑K nearest **prototypes**, then collapse to species (min distance per species), convert to probabilities.

```sql
-- Given a query vector $q (64‑D unit vector)
SELECT taxon_id, MIN(1 - (vec <#> $q)) AS best_cosine
FROM species_prototypes
GROUP BY taxon_id
ORDER BY best_cosine DESC
LIMIT 50;
```

> `<#>` is cosine distance in pgvector. Use a prepared statement; pass `$q` as a 64‑length float array.

**4A.4 Diversity mix (composition)**
- Take top ~200 species by cosine.
- Convert to probabilities with `softmax(-alpha * distance)` (alpha ~ 10–30); threshold at p≥0.3.
- Post‑filter with ecoregion/native range; group by guild (nitrogen fixers, pioneers, canopy, etc.).

**4A.5 Optional confidence**
- For each prototype, keep a radius (e.g., avg cosine distance of points to centroid). Penalize species where query lies **outside** typical radius.

---

### Option B — BigQuery‑centric (serverless)

**Storage shape**
- `occ_embeddings_raw`: rows of (taxon_id, embedding_year, lat, lon, **vec[64] ARRAY**)
- `species_signatures`: one row per species with **mean_vec[64]** (and optionally multi‑prototypes in a child table)

**4B.1 Export directly from GEE → BigQuery**
```python
# Replace toCloudStorage with toBigQuery for each sampled FeatureCollection
bq_task = ee.batch.Export.table.toBigQuery(
  collection=sampled,
  description=f'ae_bq_batch_{batch_id}',
  table=f'{PROJECT}:{BQ_DATASET}.{BQ_TABLE_RAW}',
  writeDisposition='WRITE_APPEND')
bq_task.start()
```

**4B.2 BigQuery aggregation (arrays)**
```sql
-- Create species means (unit‑normalized first)
CREATE OR REPLACE TABLE alphaearth.species_signatures AS
WITH unit AS (
  SELECT taxon_id,
         ARRAY(SELECT x/NULLIF(SQRT(SUM(POW(x,2)) OVER(PARTITION BY taxon_id)),0) FROM UNNEST(vec) AS x) AS uvec
  FROM alphaearth.occ_embeddings_raw)
SELECT taxon_id,
       ARRAY_AGG(u ORDER BY OFFSET) AS mean_vec
FROM (
  SELECT taxon_id, OFFSET, AVG(x) AS u
  FROM unit, UNNEST(uvec) WITH OFFSET
  GROUP BY taxon_id, OFFSET)
GROUP BY taxon_id;
```

**4B.3 Vector index & search**  
(Exact syntax evolves; conceptually: create a **vector index** on `mean_vec` and use a **VECTOR_SEARCH** function.)
```sql
-- Create index (cosine)
CREATE VECTOR INDEX idx_species_mean
ON alphaearth.species_signatures(mean_vec)
OPTIONS(distance_type = 'COSINE');

-- Query: top‑K nearest species to a query 64‑D unit vector
SELECT * FROM VECTOR_SEARCH(
  TABLE alphaearth.species_signatures,
  'mean_vec',
  TO_VECTOR([0.01, -0.02, ... 64 values ...]),
  top_k => 50
);
```

**4B.4 Multi‑prototype in BQ**
- Build per‑species k‑means in Python and write a child table `species_prototypes(taxon_id, proto_id, vec[64], count, radius)`.
- Index it the same way; query nearest **prototypes**, then fold by species.

**4B.5 Serving**
- Keep a slim Cloud Run service that:
  1) calls GEE to sample the 64‑D vector for (lat, lon, year)
  2) calls BigQuery vector search; applies ecological filters; returns JSON.
- Or keep Step 2 in the Treekipedia backend if you already talk to BQ there.

---

## 4C — Vector-aware dispersion & confidence (ditch per-band stats)

**Why:** AlphaEarth’s 64 bands are one embedding vector. Per-band std/p10/p90 ignores cross-dimensional structure. Use cosine/angle-based spread on the hypersphere.

### Definitions (per species or per prototype)
Let samples be unit vectors x_i in R^64 with norm 1.

- Mean direction (primary matching vector):  mu = normalize(sum_i x_i)
- Resultant length (concentration/tightness):  r = ||sum_i x_i|| / N  in [0,1].  High r = tight niche; low r = generalist or multi-modal.
- Angular deviation (single-number spread):  sigma_angle ~= sqrt(2 * (1 - r))  (radians; small-angle approximation).
- Cosine quantiles vs mean: for each sample, s_i = dot(x_i, mu) in [-1,1].  Store q10(s), q50(s), q90(s). Optionally convert to angular radii: theta_p = arccos(q_p).

**What to store:**
- Species means: { mean_vec(64), r, q10_s, q90_s, count }.
- Multi-prototypes (spherical k-means): for each cluster j, store { mu_j(64), r_j, q10_sj, q90_sj, count_j }.

**How to use at inference:**
- Rank by cosine to nearest prototype (or species mean).
- Confidence: if cosine(query, mu_j) < q10_sj, down-weight or flag. Prefer predictions inside the 90% angular radius.
- Explainability: report distance to mu_j, cluster count, and whether inside the typical band.

### BigQuery: compute r and cosine quantiles (arrays)
Assume tables: occ_embeddings_raw(taxon_id, vec ARRAY<FLOAT64>) and species_signatures(taxon_id, mean_vec ARRAY<FLOAT64>) exist.

```sql
-- 1) Sum unit vectors per species and compute r
CREATE OR REPLACE TABLE alphaearth.species_resultant AS
WITH unit AS (
  SELECT taxon_id,
         vec AS uvec
  FROM alphaearth.occ_embeddings_raw
), sum_vec AS (
  SELECT taxon_id,
         (SELECT ARRAY_AGG(SUM(val) ORDER BY off)
          FROM unit u, UNNEST(u.uvec) AS val WITH OFFSET off
          WHERE u.taxon_id = unit.taxon_id) AS sum_arr,
         COUNT(*) AS n
  FROM unit
  GROUP BY taxon_id
)
SELECT taxon_id,
       n,
       (SELECT SQRT(SUM(POW(x,2))) FROM UNNEST(sum_arr) AS x) / n AS r
FROM sum_vec;
```

```sql
-- 2) Cosine to mean and its quantiles
CREATE OR REPLACE TABLE alphaearth.species_cosine_stats AS
WITH joined AS (
  SELECT o.taxon_id,
         (SELECT SUM(u * m)
          FROM UNNEST(o.vec) AS u WITH OFFSET off
          JOIN UNNEST(s.mean_vec) AS m WITH OFFSET off USING(off)) AS cos_to_mean
  FROM alphaearth.occ_embeddings_raw o
  JOIN alphaearth.species_signatures s USING (taxon_id)
)
SELECT taxon_id,
       APPROX_QUANTILES(cos_to_mean, 100)[OFFSET(10)] AS q10_s,
       APPROX_QUANTILES(cos_to_mean, 100)[OFFSET(50)] AS q50_s,
       APPROX_QUANTILES(cos_to_mean, 100)[OFFSET(90)] AS q90_s,
       COUNT(*) AS n
FROM joined
GROUP BY taxon_id;
```

```sql
-- 3) Merge into signatures
CREATE OR REPLACE TABLE alphaearth.species_signatures AS
SELECT s.taxon_id, s.mean_vec, r.n, r.r, c.q10_s, c.q50_s, c.q90_s
FROM alphaearth.species_signatures s
JOIN alphaearth.species_resultant r USING (taxon_id)
JOIN alphaearth.species_cosine_stats c USING (taxon_id);
```

> For prototypes, repeat the same logic per cluster id.

### Python: spherical k-means (cosine) quickstart
```python
import numpy as np
from sklearn.cluster import KMeans

def unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True); n[n==0]=1
    return X / n

X = unit(X)                 # rows = samples
k = 3                       # choose based on sample count
km = KMeans(n_clusters=k, n_init='auto', random_state=42)
labels = km.fit_predict(X)
centers = unit(km.cluster_centers_)  # prototypes mu_j

# resultant length per cluster
r = []
for j in range(k):
    Xj = X[labels==j]
    r.append(np.linalg.norm(Xj.sum(axis=0))/len(Xj))

# cosine quantiles per cluster
q10, q90 = [], []
for j in range(k):
    Xj = X[labels==j]
    s = (Xj @ centers[j])           # cosines

### 5.1 Backend endpoints (Express)
```ts
// POST /api/predictor/from-location { lat, lon, year }
// returns: [{ taxon_id, name, score, rank, proto_id }]

// Pseudocode flow
// 1) GEE sample → 64‑D vector (unit)
// 2) Vector search (pgvector or BQ)
// 3) Re‑rank with filters; softmax
```

### 5.2 Frontend (Next.js)
- Map click → call `/api/predictor/from-location` → render ranked species list with badges for native/ecoregion/guild.
- Optional: “composition mode” to suggest **top N** for a planting plan.

---

## 6) Evaluation & QA

- **Hold‑out** 20% of occurrences per species for validation.
- Metrics: **Recall@K** (K=5/10/20), Mean Reciprocal Rank, and **coverage** (how many species achieve ≥X recall).
- Stratify by species frequency bucket (rare/common) and by biome/ecoregion.
- Spot‑check failure modes; plot query vector vs closest prototype distances.

---

## 7) Ops: orchestration & quotas

- Keep a simple Python orchestrator that:
  - pulls a batch of species×year points,
  - starts ≤ N concurrent GEE exports,
  - polls statuses, retries failures,
  - writes a **checkpoints** file (`completed_species.txt`, `failed_species.txt`).
- Log **species id, #points, task id, status, elapsed**.
- If you outgrow the free tier, consider GEE paid or reduce batch size / spatially thin more.

---

## 8) Optional enrichments that punch above their weight

- **Geographic prior:** down‑weight species beyond X km of known range or outside native ecoregions.
- **Confidence score:** distance vs prototype radius; number of agreeing prototypes; count of training points.
- **AOI mean:** for polygons, average unit vectors over sample points before search.
- **Explainability:** return nearest training occurrences (ids + distance) for top species.

---

## 9) Roadmap to a neural net (only when baseline is topped)

> A compact multi‑label MLP can outperform the nearest‑prototype baseline. But don’t jump until you’ve measured the gap.

### 9.1 Training dataset
- Features: 64‑D unit vectors for occurrences (optionally concat simple covariates: elevation, precip, temp).
- Labels: multi‑hot over species. For per‑species presence with single label per row, assemble **one‑vs‑rest** views or use candidate sampling.
- **Class imbalance:** weighted BCE or focal loss; sample negatives carefully (spatially aware).

### 9.2 Model sketch (PyTorch)
```python
import torch, torch.nn as nn

class MLP(nn.Module):
    def __init__(self, n_labels:int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(64, 512), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(512, 1024), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(1024, 512), nn.ReLU(),
            nn.Linear(512, n_labels), nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)
```

- Loss: **BCEWithLogitsLoss** (use Sigmoid at inference); add **class weights**.
- Train on a single T4/A10 GPU is feasible if you limit labels (e.g., top 10–20k species by frequency) or use **candidate generation** via vector search first, then score only that subset.

### 9.3 Serving
- Export to **ONNX** or TorchScript; serve on **Cloud Run** or a tiny VM.
- Inference flow: (lat,lon,year) → GEE vector → model → top‑K species → post‑filters.

### 9.4 When to escalate to “full Path B”
- Baseline Recall@20 plateaus < target; NN yields ≥ +15% absolute recall uplift in your validation.
- You’re ready to manage label spaces (50k), candidate sampling, and retraining ops.

---

## 10) Cost & storage reality check

- **Do not mirror AlphaEarth tiles.** Sample what you need.
- Persistent footprint:
  - Option A: `species_prototypes` (k≤5) → tens of **MB**.
  - Option B: BQ tables: a few **GB** at most for raw samples; signatures tiny.
- Everything else is ephemeral (raw shard CSVs can be deleted post‑aggregation).

---

## 11) Appendix — handy snippets

### 11.1 GEE single‑point sample (server call)
```python
img = ae_image_for_year(2024)
pt = ee.Geometry.Point([lon, lat])
vals = img.reduceRegion(ee.Reducer.first(), pt, 10).getInfo()
vec = [vals[f'A{i:02d}'] for i in range(1,65)]
# normalize vec → pass to search
```

### 11.2 Softmax over negative distances
```python
import numpy as np

def softmax_scores(distances, alpha=20.0):
    # distances: smaller is better (cosine distance)
    z = -alpha * np.array(distances)
    z -= z.max()
    e = np.exp(z)
    return (e / e.sum()).tolist()
```

### 11.3 Postgres prepared search (psycopg2)
```python
cur.execute("""
SELECT taxon_id, MIN(vec <#> $1) AS d
FROM species_prototypes
GROUP BY taxon_id
ORDER BY d ASC
LIMIT 50;
""", (query_vec.tolist(),))
```

### 11.4 Minimal FAISS fallback (if not using pgvector)
```python
import faiss, numpy as np
X = np.vstack([row['vec'] for row in prototypes])  # unit vectors
index = faiss.IndexFlatIP(64)  # inner product == cosine on unit vec
index.add(X)
D, I = index.search(query_vec.reshape(1,-1), 200)
```

### 11.5 BigQuery client call (vector search)
```python
from google.cloud import bigquery
client = bigquery.Client()
q = """
SELECT taxon_id, distance
FROM VECTOR_SEARCH(
  TABLE alphaearth.species_signatures,
  'mean_vec',
  TO_VECTOR(@qvec),
  top_k => 50)
"""
job = client.query(q, job_config=bigquery.QueryJobConfig(
    query_parameters=[bigquery.ArrayQueryParameter('qvec', 'FLOAT64', query_vec.tolist())]
))
rows = list(job)
```

---

## 12) Build order (checklist)

1. ✅ Set up GEE + GCS + (optional) BigQuery; create bucket & dataset.
2. ✅ Load occurrences; add `embedding_year`.
3. ✅ Write the GEE **batch exporter**; run a **100‑species pilot**.
4. ✅ Aggregate:
   - Option A: build **prototypes** → Postgres `species_prototypes` (+ mean table).
   - Option B: **BQ arrays** → signatures table; (optional) prototypes child table.
5. ✅ Backend endpoint `/api/predictor/from-location` (GEE sample → vector search → filters → JSON).
6. ✅ UI hook: map click → predictions list.
7. ✅ Evaluate Recall@K; iterate on k, filters, alpha.
8. ➕ If needed: train the compact MLP; compare; deploy.

---

### You’re ready. Start with the 100‑species pilot, get a working prediction loop in the app, then scale. Keep it fun. 🌱

