# 🚀 AlphaEarth Species Predictor - Quick Start Guide

**FOR DJIMO**: Your step-by-step guide to get started TODAY with the 100-species pilot.

---

## 📊 What You Have vs What You Need

### ✅ What You Already Have:
1. Treekipedia PostgreSQL database (67,743 species)
2. Occurrence data in Parquet format
3. Existing GEE extraction code (`silvi-open-gee-temporal-extraction/`)
4. Your excellent Builder's Guide (vector-first approach)
5. Comprehensive executable plan (ALPHAEARTH_EXECUTABLE_PLAN.md)

### 🎯 What You Need to Do:
1. Set up Google Earth Engine account
2. Set up Google Cloud + BigQuery (for serverless option)
3. Select 100 diverse species
4. Adapt existing code to vector-first approach
5. Run pilot extraction

---

## 🗓️ Day 1: Setup & Authentication (2-3 hours)

### Task 1.1: Google Earth Engine Setup (30 min)

**If you don't have GEE account yet:**
```bash
# 1. Sign up at https://earthengine.google.com/signup/
# 2. Wait for approval email (usually within hours)
# 3. Install GEE Python API
pip install earthengine-api

# 4. Authenticate (opens browser)
earthengine authenticate

# 5. Test authentication
python3 -c "import ee; ee.Initialize(); print('✅ GEE working!')"
```

**If you already have GEE:**
```bash
# Just test it works
cd "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/silvi-open-gee-temporal-extraction"
python3 -c "import ee; ee.Initialize(project='treekipedia'); print('✅ GEE ready')"
```

**Validation**: Should print "✅ GEE working!" or "✅ GEE ready"

---

### Task 1.2: Google Cloud Project Setup (45 min)

**Create GCP project (if not exists):**
```bash
# 1. Go to https://console.cloud.google.com/
# 2. Create new project named "treekipedia" (or use existing)
# 3. Enable billing (free tier: $300 credit for new accounts)
# 4. Enable APIs:
#    - BigQuery API
#    - Cloud Storage API
#    - Earth Engine API
```

**Set up gcloud CLI:**
```bash
# Install gcloud (if not installed)
brew install --cask google-cloud-sdk

# Initialize
gcloud init
# Choose: treekipedia project
# Choose: your Google account
# Choose: us-central1 region (for BigQuery)

# Authenticate
gcloud auth application-default login

# Verify
gcloud config list
# Should show: project = treekipedia
```

**Validation**:
```bash
gcloud projects describe treekipedia
# Should show: projectId: treekipedia, lifecycleState: ACTIVE
```

---

### Task 1.3: BigQuery Setup (30 min)

**Create dataset for AlphaEarth data:**
```bash
# Create dataset
bq mk --dataset --location=us-central1 treekipedia:alphaearth

# Verify
bq ls treekipedia
# Should show: alphaearth dataset
```

**Test BigQuery access:**
```bash
# Simple query
bq query --use_legacy_sql=false 'SELECT 1 as test'
# Should return: test = 1
```

---

### Task 1.4: Python Environment Setup (30 min)

```bash
cd "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open"

# Create new virtual environment for pilot
python3 -m venv .venv-pilot
source .venv-pilot/bin/activate

# Install dependencies
pip install --upgrade pip
pip install \
  earthengine-api \
  google-cloud-storage \
  google-cloud-bigquery \
  pandas \
  polars \
  scikit-learn \
  numpy \
  psycopg2-binary \
  tqdm \
  matplotlib \
  seaborn

# Verify key imports
python3 -c "
import ee
import google.cloud.bigquery as bq
import google.cloud.storage as gcs
import pandas as pd
import polars as pl
import sklearn
import numpy as np
print('✅ All imports successful!')
"
```

**Validation**: Should print "✅ All imports successful!"

---

## 🗓️ Day 2: Species Selection & Data Prep (2-4 hours)

### Task 2.1: Select 100 Diverse Species (1 hour)

**Goal**: Get 100 species that represent diverse:
- Geographic ranges (global coverage)
- Families (taxonomic diversity)
- Occurrence counts (mix of common and rare)
- Ecoregions (tropical, temperate, boreal, etc.)

**Run this SQL in PostgreSQL:**
```bash
psql treekipedia
```

```sql
-- Create selection table
CREATE TEMP TABLE pilot_species AS
WITH species_stats AS (
  SELECT
    s.taxon_id,
    s.species_scientific_name,
    s.family,
    COUNT(DISTINCT o.id) as occ_count,
    COUNT(DISTINCT o.latitude::text || ',' || o.longitude::text) as unique_locations,
    MIN(o.year) as min_year,
    MAX(o.year) as max_year
  FROM species s
  INNER JOIN occurrence_data o ON s.taxon_id = o.taxon_id
  WHERE o.latitude IS NOT NULL
    AND o.longitude IS NOT NULL
    AND o.year IS NOT NULL
  GROUP BY s.taxon_id, s.species_scientific_name, s.family
  HAVING COUNT(*) >= 50  -- At least 50 occurrences
),
stratified AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY
      CASE
        WHEN occ_count < 200 THEN 'rare'
        WHEN occ_count < 1000 THEN 'common'
        ELSE 'abundant'
      END
      ORDER BY RANDOM()
    ) as rn_freq,
    ROW_NUMBER() OVER (PARTITION BY family ORDER BY RANDOM()) as rn_family
  FROM species_stats
)
SELECT
  taxon_id,
  species_scientific_name,
  family,
  occ_count,
  unique_locations,
  min_year,
  max_year
FROM stratified
WHERE
  rn_freq <= 35  -- ~33 per frequency bucket
  OR rn_family = 1  -- Plus 1 per family for diversity
ORDER BY family, occ_count DESC
LIMIT 100;

-- Save to file
\copy (SELECT * FROM pilot_species) TO '/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/pilot_species_100.csv' CSV HEADER;

-- Summary stats
SELECT
  COUNT(*) as total_species,
  COUNT(DISTINCT family) as families,
  SUM(occ_count) as total_occurrences,
  AVG(occ_count)::int as avg_occ_per_species,
  MIN(min_year) as earliest_year,
  MAX(max_year) as latest_year
FROM pilot_species;
```

**Expected Output**:
```
total_species | families | total_occurrences | avg_occ_per_species | earliest_year | latest_year
     100      |   ~50    |     ~50,000       |        ~500         |     ~1950     |    ~2024
```

**Validation**:
```bash
# Check file was created
ls -lh /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/pilot_species_100.csv
# Should show ~5-10 KB file

# Preview
head -5 /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/pilot_species_100.csv
```

---

### Task 2.2: Extract Occurrence Data for Pilot Species (30 min)

```sql
-- Create staging table for pilot occurrences
CREATE TABLE IF NOT EXISTS pilot_occurrences AS
SELECT
  o.id,
  o.taxon_id,
  o.latitude,
  o.longitude,
  o.year,
  CASE
    WHEN o.year <= 2017 THEN 2017
    WHEN o.year >= 2024 THEN 2024
    ELSE o.year
  END as embedding_year
FROM occurrence_data o
WHERE o.taxon_id IN (SELECT taxon_id FROM pilot_species)
  AND o.latitude IS NOT NULL
  AND o.longitude IS NOT NULL
  AND o.year IS NOT NULL
  AND o.latitude BETWEEN -90 AND 90
  AND o.longitude BETWEEN -180 AND 180;

-- Create index for faster access
CREATE INDEX IF NOT EXISTS idx_pilot_occ_taxon ON pilot_occurrences(taxon_id);
CREATE INDEX IF NOT EXISTS idx_pilot_occ_year ON pilot_occurrences(embedding_year);

-- Summary
SELECT
  COUNT(*) as total_occurrences,
  COUNT(DISTINCT taxon_id) as species_count,
  COUNT(DISTINCT embedding_year) as unique_years,
  MIN(embedding_year) as min_emb_year,
  MAX(embedding_year) as max_emb_year
FROM pilot_occurrences;
```

**Expected Output**:
```
total_occurrences | species_count | unique_years | min_emb_year | max_emb_year
    ~50,000       |      100      |      8       |     2017     |     2024
```

---

## 🗓️ Day 3: GEE Batch Extraction (4-6 hours)

### Task 3.1: Create Batch Orchestrator Script (1 hour)

**Create file**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/gee_pilot_extraction.py`

```python
#!/usr/bin/env python3
"""
GEE AlphaEarth Extraction - 100 Species Pilot
Vector-first approach: extract 64-D embeddings at occurrence points
"""

import ee
import psycopg2
import pandas as pd
import time
import json
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm

# Configuration
GCS_BUCKET = 'treekipedia-embeddings'  # Change to your bucket
DB_CONFIG = {
    'host': 'localhost',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': 'postgres'  # Change to your password
}

# GEE Quotas
MAX_CONCURRENT_TASKS = 5  # Keep conservative for free tier
POINTS_PER_TASK = 5000    # Max points per export task

# Initialize GEE
ee.Initialize(project='treekipedia')

def get_alphaearth_image(year: int) -> ee.Image:
    """Get AlphaEarth image for specific year"""
    ae_collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
    filtered = ae_collection.filterDate(f'{year}-01-01', f'{year}-12-31')
    return ee.Image(filtered.first())

def load_pilot_occurrences() -> pd.DataFrame:
    """Load occurrence data from PostgreSQL"""
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
    SELECT
        id,
        taxon_id,
        latitude,
        longitude,
        year,
        embedding_year
    FROM pilot_occurrences
    ORDER BY taxon_id, embedding_year
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def create_point_features(points_df: pd.DataFrame) -> ee.FeatureCollection:
    """Convert DataFrame rows to GEE Features"""
    features = []
    for _, row in points_df.iterrows():
        point = ee.Geometry.Point([row['longitude'], row['latitude']])
        feature = ee.Feature(point, {
            'occ_id': int(row['id']),
            'taxon_id': int(row['taxon_id']),
            'year': int(row['year']),
            'emb_year': int(row['embedding_year'])
        })
        features.append(feature)
    return ee.FeatureCollection(features)

def export_batch_to_gcs(batch_id: int, points_df: pd.DataFrame) -> ee.batch.Task:
    """
    Export embeddings for a batch of points to Google Cloud Storage

    Returns: GEE Task object
    """
    # Group by embedding year
    years = sorted(points_df['embedding_year'].unique())

    all_sampled = []

    for year in years:
        year_df = points_df[points_df['embedding_year'] == year]

        # Get AlphaEarth image for this year
        ae_img = get_alphaearth_image(year)

        # Create features
        fc = create_point_features(year_df)

        # Sample embeddings at points
        sampled = ae_img.sampleRegions(
            collection=fc,
            scale=10,  # Native 10m resolution
            geometries=False,
            tileScale=4  # Increase for larger batches
        )

        all_sampled.append(sampled)

    # Merge all years
    merged = ee.FeatureCollection(all_sampled).flatten()

    # Export to GCS
    task = ee.batch.Export.table.toCloudStorage(
        collection=merged,
        description=f'pilot_batch_{batch_id:04d}',
        bucket=GCS_BUCKET,
        fileNamePrefix=f'pilot/batch_{batch_id:04d}',
        fileFormat='CSV'
    )

    task.start()
    return task

def monitor_tasks(tasks: List[ee.batch.Task], check_interval: int = 60):
    """Monitor GEE tasks until completion"""
    print(f"\nMonitoring {len(tasks)} tasks...")

    while tasks:
        time.sleep(check_interval)

        remaining = []
        for task in tasks:
            status = task.status()
            state = status['state']

            if state == 'COMPLETED':
                print(f"✅ {status['description']} completed")
            elif state == 'FAILED':
                print(f"❌ {status['description']} failed: {status.get('error_message', 'Unknown error')}")
            else:
                remaining.append(task)

        tasks = remaining
        if tasks:
            print(f"  {len(tasks)} tasks still running...")

    print("✅ All tasks completed!")

def run_pilot_extraction():
    """Main extraction workflow"""
    print("="*70)
    print("GEE ALPHAEARTH EXTRACTION - 100 SPECIES PILOT")
    print("="*70)

    # Load data
    print("\n📂 Loading occurrence data...")
    df = load_pilot_occurrences()
    print(f"  Total occurrences: {len(df):,}")
    print(f"  Species: {df['taxon_id'].nunique()}")
    print(f"  Years: {df['embedding_year'].min()} - {df['embedding_year'].max()}")

    # Create batches
    print(f"\n📦 Creating batches ({POINTS_PER_TASK} points per batch)...")
    batches = [df.iloc[i:i+POINTS_PER_TASK] for i in range(0, len(df), POINTS_PER_TASK)]
    print(f"  Total batches: {len(batches)}")

    # Export batches with throttling
    print(f"\n🚀 Starting exports (max {MAX_CONCURRENT_TASKS} concurrent)...")
    all_tasks = []
    active_tasks = []

    for batch_id, batch_df in enumerate(tqdm(batches, desc="Submitting batches")):
        # Wait if at max concurrent tasks
        while len(active_tasks) >= MAX_CONCURRENT_TASKS:
            time.sleep(30)
            active_tasks = [t for t in active_tasks if t.status()['state'] not in ['COMPLETED', 'FAILED']]

        # Submit new task
        task = export_batch_to_gcs(batch_id, batch_df)
        active_tasks.append(task)
        all_tasks.append(task)

        time.sleep(2)  # Brief pause between submissions

    # Monitor remaining tasks
    monitor_tasks(all_tasks)

    print("\n" + "="*70)
    print("EXTRACTION COMPLETE!")
    print("="*70)
    print(f"📁 Data exported to: gs://{GCS_BUCKET}/pilot/")
    print(f"📊 Next step: Download CSVs and build prototypes")

if __name__ == "__main__":
    run_pilot_extraction()
```

**Make executable**:
```bash
chmod +x /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/scripts/gee_pilot_extraction.py
```

---

### Task 3.2: Create GCS Bucket (15 min)

```bash
# Create bucket (must be globally unique name)
gsutil mb -p treekipedia -l us-central1 gs://treekipedia-embeddings

# Verify
gsutil ls gs://treekipedia-embeddings
# Should show empty bucket
```

---

### Task 3.3: Run Pilot Extraction (3-4 hours)

```bash
cd "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open"
source .venv-pilot/bin/activate

# Run extraction
python3 scripts/gee_pilot_extraction.py
```

**Expected Output**:
```
======================================================================
GEE ALPHAEARTH EXTRACTION - 100 SPECIES PILOT
======================================================================

📂 Loading occurrence data...
  Total occurrences: 50,000
  Species: 100
  Years: 2017 - 2024

📦 Creating batches (5000 points per batch)...
  Total batches: 10

🚀 Starting exports (max 5 concurrent)...
Submitting batches: 100%|████████████████████| 10/10 [00:30<00:00]

Monitoring 10 tasks...
✅ pilot_batch_0000 completed
✅ pilot_batch_0001 completed
...
✅ All tasks completed!

======================================================================
EXTRACTION COMPLETE!
======================================================================
📁 Data exported to: gs://treekipedia-embeddings/pilot/
📊 Next step: Download CSVs and build prototypes
```

**Validation**:
```bash
# List exported files
gsutil ls gs://treekipedia-embeddings/pilot/

# Should show CSV files like:
# gs://treekipedia-embeddings/pilot/batch_0000.csv
# gs://treekipedia-embeddings/pilot/batch_0001.csv
# ...
```

**Troubleshooting**:
- If tasks fail with "User memory limit exceeded": Reduce POINTS_PER_TASK to 2000
- If tasks timeout: Check GEE task console at https://code.earthengine.google.com/tasks
- If quota exceeded: Wait 24 hours or reduce MAX_CONCURRENT_TASKS to 2

---

## 🗓️ Day 4: Build Prototypes (3-4 hours)

### Task 4.1: Download GCS Files (30 min)

```bash
# Create local directory
mkdir -p /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/data/pilot_raw

# Download all CSVs
gsutil -m cp -r gs://treekipedia-embeddings/pilot/* \
  /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/data/pilot_raw/

# Verify
ls -lh /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/data/pilot_raw/
# Should show ~10 CSV files, total ~200-500 MB
```

---

### Task 4.2: Build k-Prototypes (2 hours)

**Create file**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/build_prototypes.py`

```python
#!/usr/bin/env python3
"""
Build k-means prototypes from AlphaEarth embeddings
Vector-first approach with spherical statistics
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from pathlib import Path
import psycopg2
from tqdm import tqdm
import json

# Configuration
DATA_DIR = Path("/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/data/pilot_raw")
DB_CONFIG = {
    'host': 'localhost',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': 'postgres'
}

# AlphaEarth band names (A00-A63 or A01-A64 depending on export)
BANDS = [f'A{i:02d}' for i in range(64)]  # Will auto-detect actual column names

def unit_normalize(X: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit length"""
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # Avoid division by zero
    return X / norms

def resultant_length(X: np.ndarray) -> float:
    """Calculate resultant length (concentration measure)"""
    return np.linalg.norm(X.sum(axis=0)) / len(X)

def cosine_quantiles(X: np.ndarray, mu: np.ndarray) -> Dict[str, float]:
    """Calculate cosine quantiles relative to mean direction"""
    cosines = X @ mu  # Dot product for unit vectors
    return {
        'q10': float(np.quantile(cosines, 0.10)),
        'q50': float(np.quantile(cosines, 0.50)),
        'q90': float(np.quantile(cosines, 0.90))
    }

def determine_k(n_samples: int) -> int:
    """Heuristic for number of prototypes based on sample size"""
    if n_samples < 100:
        return 1
    elif n_samples < 500:
        return 2
    elif n_samples < 2000:
        return 3
    else:
        return 5

def load_all_embeddings() -> pd.DataFrame:
    """Load and combine all CSV files"""
    print("📂 Loading raw embedding CSVs...")

    csv_files = list(DATA_DIR.glob("*.csv"))
    print(f"  Found {len(csv_files)} files")

    dfs = []
    for csv_file in tqdm(csv_files, desc="Reading CSVs"):
        df = pd.read_csv(csv_file)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    print(f"  Total rows: {len(combined):,}")

    return combined

def detect_band_columns(df: pd.DataFrame) -> List[str]:
    """Auto-detect AlphaEarth band column names"""
    # Try A00-A63 format
    candidates_00 = [f'A{i:02d}' for i in range(64)]
    if all(col in df.columns for col in candidates_00):
        return candidates_00

    # Try A01-A64 format
    candidates_01 = [f'A{i:02d}' for i in range(1, 65)]
    if all(col in df.columns for col in candidates_01):
        return candidates_01

    raise ValueError("Could not detect AlphaEarth band columns")

def build_species_prototypes(df: pd.DataFrame) -> pd.DataFrame:
    """Build k-means prototypes for all species"""
    print("\n🔬 Building prototypes per species...")

    # Detect band columns
    band_cols = detect_band_columns(df)
    print(f"  Using bands: {band_cols[0]} - {band_cols[-1]}")

    # Group by species
    species_groups = df.groupby('taxon_id')
    print(f"  Total species: {len(species_groups)}")

    prototypes = []

    for taxon_id, group in tqdm(species_groups, desc="Processing species"):
        # Extract 64-D vectors
        X = group[band_cols].values

        # Remove NaN rows
        valid_mask = ~np.isnan(X).any(axis=1)
        X = X[valid_mask]

        if len(X) == 0:
            print(f"  ⚠️  Species {taxon_id}: No valid embeddings, skipping")
            continue

        # Unit normalize
        X = unit_normalize(X)

        # Determine k
        k = determine_k(len(X))

        if k == 1:
            # Single prototype (mean direction)
            mu = unit_normalize(X.mean(axis=0, keepdims=True))[0]
            r = resultant_length(X)
            q = cosine_quantiles(X, mu)

            prototypes.append({
                'taxon_id': int(taxon_id),
                'proto_id': 0,
                'vec': mu.tolist(),
                'count': len(X),
                'r': float(r),
                'q10_s': q['q10'],
                'q50_s': q['q50'],
                'q90_s': q['q90']
            })
        else:
            # k-means clustering
            kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = kmeans.fit_predict(X)

            # Unit normalize centroids
            centers = unit_normalize(kmeans.cluster_centers_)

            for j in range(k):
                X_j = X[labels == j]

                if len(X_j) == 0:
                    continue

                mu_j = centers[j]
                r_j = resultant_length(X_j)
                q_j = cosine_quantiles(X_j, mu_j)

                prototypes.append({
                    'taxon_id': int(taxon_id),
                    'proto_id': int(j),
                    'vec': mu_j.tolist(),
                    'count': len(X_j),
                    'r': float(r_j),
                    'q10_s': q_j['q10'],
                    'q50_s': q_j['q50'],
                    'q90_s': q_j['q90']
                })

    df_prototypes = pd.DataFrame(prototypes)
    print(f"\n  ✅ Created {len(df_prototypes)} prototypes for {df_prototypes['taxon_id'].nunique()} species")
    print(f"  Average k: {len(df_prototypes) / df_prototypes['taxon_id'].nunique():.2f}")

    return df_prototypes

def save_prototypes(df_prototypes: pd.DataFrame):
    """Save prototypes to PostgreSQL"""
    print("\n💾 Saving to PostgreSQL...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Create table with pgvector
    cur.execute("""
    CREATE EXTENSION IF NOT EXISTS vector;

    DROP TABLE IF EXISTS species_prototypes CASCADE;

    CREATE TABLE species_prototypes (
        taxon_id BIGINT NOT NULL,
        proto_id INT NOT NULL,
        vec VECTOR(64) NOT NULL,
        count INT,
        r DOUBLE PRECISION,
        q10_s DOUBLE PRECISION,
        q50_s DOUBLE PRECISION,
        q90_s DOUBLE PRECISION,
        PRIMARY KEY (taxon_id, proto_id)
    );
    """)

    # Insert prototypes
    for _, row in tqdm(df_prototypes.iterrows(), total=len(df_prototypes), desc="Inserting"):
        cur.execute("""
        INSERT INTO species_prototypes (taxon_id, proto_id, vec, count, r, q10_s, q50_s, q90_s)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['taxon_id'],
            row['proto_id'],
            row['vec'],  # pgvector handles list → vector conversion
            row['count'],
            row['r'],
            row['q10_s'],
            row['q50_s'],
            row['q90_s']
        ))

    conn.commit()

    # Create index
    print("  Creating vector index...")
    cur.execute("""
    CREATE INDEX idx_prototypes_vec ON species_prototypes
    USING ivfflat (vec vector_cosine_ops)
    WITH (lists = 50);
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("  ✅ Saved to species_prototypes table")

def main():
    print("="*70)
    print("BUILD K-MEANS PROTOTYPES - VECTOR-FIRST APPROACH")
    print("="*70)

    # Load embeddings
    df = load_all_embeddings()

    # Build prototypes
    df_prototypes = build_species_prototypes(df)

    # Save to database
    save_prototypes(df_prototypes)

    # Summary
    print("\n" + "="*70)
    print("PROTOTYPES COMPLETE!")
    print("="*70)
    print(f"📊 Total prototypes: {len(df_prototypes)}")
    print(f"🌳 Species covered: {df_prototypes['taxon_id'].nunique()}")
    print(f"📈 Average r (concentration): {df_prototypes['r'].mean():.3f}")
    print(f"\n✅ Ready for prediction queries!")

if __name__ == "__main__":
    main()
```

**Make executable and run**:
```bash
chmod +x /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open/scripts/build_prototypes.py

source .venv-pilot/bin/activate
python3 scripts/build_prototypes.py
```

**Expected Output**:
```
======================================================================
BUILD K-MEANS PROTOTYPES - VECTOR-FIRST APPROACH
======================================================================
📂 Loading raw embedding CSVs...
  Found 10 files
Reading CSVs: 100%|██████████████████| 10/10
  Total rows: 50,000

🔬 Building prototypes per species...
  Using bands: A00 - A63
  Total species: 100
Processing species: 100%|████████████| 100/100

  ✅ Created 250 prototypes for 100 species
  Average k: 2.50

💾 Saving to PostgreSQL...
  Creating vector index...
  ✅ Saved to species_prototypes table

======================================================================
PROTOTYPES COMPLETE!
======================================================================
📊 Total prototypes: 250
🌳 Species covered: 100
📈 Average r (concentration): 0.875

✅ Ready for prediction queries!
```

---

## 🗓️ Day 5: Test Predictions (2-3 hours)

### Task 5.1: Test Single-Point Query (30 min)

```python
# File: scripts/test_prediction.py

import ee
import psycopg2
import numpy as np

ee.Initialize(project='treekipedia')

DB_CONFIG = {
    'host': 'localhost',
    'database': 'treekipedia',
    'user': 'postgres',
    'password': 'postgres'
}

def query_point(lat: float, lon: float, year: int = 2024):
    """Query species predictions for a point"""

    # 1. Get AlphaEarth embedding from GEE
    ae_img = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
        .filterDate(f'{year}-01-01', f'{year}-12-31') \
        .first()

    point = ee.Geometry.Point([lon, lat])
    vals = ae_img.reduceRegion(ee.Reducer.first(), point, 10).getInfo()

    # Extract 64-D vector
    vec = np.array([vals[f'A{i:02d}'] for i in range(64)])

    # Unit normalize
    vec = vec / np.linalg.norm(vec)

    # 2. Query PostgreSQL with pgvector
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
    SELECT
        p.taxon_id,
        s.species_scientific_name,
        s.family,
        p.proto_id,
        p.count,
        1 - (p.vec <#> %s) as cosine_sim,
        p.r,
        p.q10_s
    FROM species_prototypes p
    JOIN species s ON p.taxon_id = s.taxon_id
    ORDER BY p.vec <#> %s ASC
    LIMIT 20
    """, (vec.tolist(), vec.tolist()))

    results = cur.fetchall()
    cur.close()
    conn.close()

    # 3. Display results
    print(f"\n🌍 Location: {lat:.4f}, {lon:.4f} (Year: {year})")
    print(f"📊 Top 20 predicted species:\n")
    print(f"{'Rank':<6} {'Species':<35} {'Family':<20} {'Score':<8} {'Proto':<6}")
    print("-" * 80)

    for i, row in enumerate(results, 1):
        taxon_id, name, family, proto_id, count, cosine, r, q10 = row
        print(f"{i:<6} {name:<35} {family:<20} {cosine:.4f} {proto_id:<6}")

    return results

# Test locations
print("="*80)
print("SPECIES PREDICTOR - POINT QUERY TEST")
print("="*80)

# Amazon rainforest
query_point(-3.1190, -60.0217, 2024)

# Temperate deciduous forest (England)
query_point(51.5074, -0.1278, 2024)
```

**Run test**:
```bash
python3 scripts/test_prediction.py
```

---

## 📋 Next Steps Checklist

Once you've completed Days 1-5, you'll have:
- ✅ Working GEE extraction pipeline
- ✅ 100 species with k-prototypes in PostgreSQL
- ✅ Ability to query predictions for any point

**Then proceed to**:
- [ ] Day 6: Create Express backend endpoint
- [ ] Day 7: Add frontend map integration
- [ ] Week 2: Validate with Recall@K metrics
- [ ] Week 3: Scale to 1,000 species
- [ ] Week 4: Production deployment

---

## 🆘 Troubleshooting

### GEE Authentication Issues
```bash
# Re-authenticate
earthengine authenticate --force

# Verify
python3 -c "import ee; ee.Initialize(); print('OK')"
```

### PostgreSQL pgvector Not Found
```bash
# Install pgvector extension
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install  # May need sudo

# Enable in database
psql treekipedia -c "CREATE EXTENSION vector;"
```

### GCS Permission Denied
```bash
# Ensure you're authenticated
gcloud auth application-default login

# Check project
gcloud config get-value project
# Should be: treekipedia
```

---

## 📞 Get Help

If you get stuck:
1. Check the full executable plan: `ALPHAEARTH_EXECUTABLE_PLAN.md`
2. Review your Builder's Guide: `treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md`
3. Check GEE task console: https://code.earthengine.google.com/tasks

---

**YOU'RE READY! START WITH DAY 1 SETUP** 🚀
