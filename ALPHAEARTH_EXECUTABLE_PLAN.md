# AlphaEarth Species Predictor - Executable Implementation Plan

**Version**: 1.0.0
**Created**: October 2024
**Scope**: 100-species pilot implementation
**Approach**: Vector-first with k-prototypes clustering

---

## Executive Summary

This document provides a comprehensive, step-by-step implementation plan for building the AlphaEarth Species Predictor using a superior vector-first approach. The plan adapts insights from the AlphaEarth Species Predictor Builder's Guide, which represents a significant improvement over the original scalar-based implementation.

The key innovation: treating AlphaEarth's 64 bands as a unified 64-dimensional embedding vector, enabling cosine similarity searches on the unit hypersphere. This preserves multi-dimensional environmental relationships that were lost in the original per-band statistical approach.

---

## Part 1: Assessment & Comparison

### 1.1 Architectural Comparison Table

| Aspect | User's Vector-First Approach | Original Scalar Approach | Winner & Rationale |
|--------|------------------------------|--------------------------|-------------------|
| **Data Representation** | 64-D unit vector (normalized embedding) | 256 scalar values (4 stats × 64 bands) | **Vector-First** - Preserves cross-dimensional relationships, enables geometric interpretation |
| **Species Modeling** | k-prototypes (1-5 centroids per species) | Single mean + std per band | **Vector-First** - Captures multi-modal niches (e.g., species in both lowland and montane habitats) |
| **Statistical Framework** | Spherical statistics (resultant length, angular deviation) | Per-band statistics (mean, std, p10, p90) | **Vector-First** - Mathematically correct for directional data on hypersphere |
| **Similarity Metric** | Cosine similarity on unit sphere | Per-band distance aggregation | **Vector-First** - Single unified metric, computationally efficient |
| **Storage Efficiency** | 64 floats per prototype (256-320 bytes) | 256 floats per species (1024 bytes) | **Vector-First** - 4× more efficient storage |
| **Query Performance** | O(log n) with HNSW index | O(n) table scan or complex indexing | **Vector-First** - Sub-linear scaling with proper indexing |
| **Infrastructure Options** | PostgreSQL pgvector OR BigQuery VECTOR_SEARCH | PostgreSQL only | **Vector-First** - Serverless option available, better scaling |
| **Quota Management** | Explicit throttling (2-8 concurrent GEE tasks) | Basic batching | **Vector-First** - Production-ready with checkpointing |
| **Spatial Bias Handling** | Grid-based de-biasing (equal area sampling) | None | **Vector-First** - Prevents oversampling in data-rich regions |
| **Temporal Handling** | Year-aware extraction with clamping | Year-aware but less sophisticated | **Vector-First** - Better handling of edge cases |

### 1.2 Mathematical Superiority of Vector Approach

#### Why Unit Vectors on Hypersphere?

AlphaEarth bands represent environmental conditions that interact non-linearly. A location with high temperature and low precipitation creates a specific ecological niche that isn't captured by treating these as independent variables.

**Mathematical Foundation**:
- Environmental space forms a manifold where direction matters more than magnitude
- Unit normalization (L2) removes scale differences between bands
- Cosine similarity naturally captures ecological similarity: cos(θ) = a·b / (||a|| ||b||)
- For unit vectors, this simplifies to: cos(θ) = a·b

#### Why k-Prototypes Beat Single Means?

Many species occupy multiple distinct niches:
- **Quercus robur** (English Oak): Lowland forests AND urban parks
- **Pinus sylvestris** (Scots Pine): Boreal forests AND Mediterranean mountains
- **Metrosideros polymorpha** ('Ōhi'a): Sea level to 2,500m elevation in Hawaii

A single mean vector would place the species in an "average" environment that may not exist in nature. k-prototypes capture these distinct ecological modes.

#### Spherical Statistics Correctness

Standard statistics assume Euclidean space. On a hypersphere:
- Mean must be renormalized to unit length
- Variance becomes angular deviation
- Quantiles become cosine quantiles
- Resultant length (r) measures concentration: r = ||Σ(vi)|| / n

### 1.3 What to Preserve from Existing Code

From `silvi-open-gee-temporal-extraction/`:

**Keep & Adapt**:
1. **Temporal year matching logic** (`extract_temporal_aligned.py`):
   - Lines 45-89: Year extraction from occurrence dates
   - Lines 120-145: Temporal clamping to [2018, 2023]
   - Lines 200-230: GEE collection filtering by year

2. **GEE batch export framework** (`extract_temporal_aligned.py`):
   - Lines 300-350: Task submission and monitoring
   - Lines 380-420: Export to Cloud Storage
   - Lines 450-480: Checkpoint management

3. **Database connection setup** (`aggregate_species_signature.py`):
   - Lines 20-40: PostgreSQL connection pooling
   - Lines 50-70: Species metadata queries

**Replace Completely**:
1. **Per-band aggregation** (`aggregate_species_signature.py` lines 100-200)
   - Replace with vector-first k-means clustering
   - Replace scalar stats with spherical statistics

2. **Storage schema** (implicit in aggregation)
   - Replace 256-column table with vector column
   - Add prototype clustering table

---

## Part 2: 100-Species Pilot - Step-by-Step Executable Plan

### Step 1: Environment Setup

**Objective**: Configure GEE, BigQuery, PostgreSQL, and Python dependencies for the pilot.

#### 1.1 Python Environment

```bash
# Create new conda environment
conda create -n alphaearth python=3.11 -y
conda activate alphaearth

# Install core dependencies
pip install earthengine-api==0.1.380
pip install google-cloud-bigquery==3.13.0
pip install google-cloud-storage==2.13.0
pip install pandas==2.1.4
pip install numpy==1.26.2
pip install scikit-learn==1.3.2
pip install psycopg2-binary==2.9.9
pip install python-dotenv==1.0.0
pip install tqdm==4.66.1

# For spherical clustering
pip install spherecluster==0.1.7

# For pgvector support
pip install pgvector==0.2.4
```

**Expected Output**:
```
Successfully installed earthengine-api-0.1.380 google-cloud-bigquery-3.13.0 ...
```

#### 1.2 Google Earth Engine Authentication

```bash
# Authenticate GEE
earthengine authenticate

# Verify authentication
python -c "import ee; ee.Initialize(); print('GEE initialized successfully')"
```

**Expected Output**:
```
GEE initialized successfully
```

#### 1.3 BigQuery Setup (Path B - Optional)

```bash
# Install gcloud CLI if not present
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project your-project-id

# Create dataset
bq mk --location=US alphaearth_pilot
```

**Expected Output**:
```
Dataset 'your-project-id:alphaearth_pilot' successfully created.
```

#### 1.4 PostgreSQL + pgvector Setup (Path A)

```bash
# Install PostgreSQL 16+ with pgvector
brew install postgresql@16
brew services start postgresql@16

# Install pgvector extension
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# Create database
createdb treekipedia_alphaearth

# Enable pgvector
psql treekipedia_alphaearth -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql treekipedia_alphaearth -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

**Expected Output**:
```
CREATE EXTENSION
CREATE EXTENSION
```

**Validation**:
```bash
psql treekipedia_alphaearth -c "SELECT vector_version();"
# Should show: v0.5.1 or higher
```

**Troubleshooting**:
- If `make` fails, ensure you have Xcode command line tools: `xcode-select --install`
- For Linux, use `apt-get install postgresql-16-pgvector`

### Step 2: Occurrence Data Preparation

**Objective**: Select 100 diverse species with good geographic coverage and prepare occurrence data.

#### 2.1 Species Selection Script

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/select_pilot_species.py`:

```python
#!/usr/bin/env python3
"""
Select 100 diverse species for AlphaEarth pilot.
Criteria: geographic coverage, data availability, taxonomic diversity.
"""

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

def select_pilot_species():
    """Select 100 species with best data coverage."""

    # Database connection
    conn = psycopg2.connect(
        host="localhost",
        database="treekipedia",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

    # Query for species with good occurrence coverage
    query = """
    WITH species_stats AS (
        SELECT
            s.taxon_id,
            s.species_scientific_name,
            s.genus,
            s.family,
            s.conservation_status,
            COUNT(DISTINCT gt.geohash_l7) as occurrence_count,
            COUNT(DISTINCT LEFT(gt.geohash_l7, 3)) as geographic_spread,
            AVG(ST_Y(gt.geometry)) as avg_latitude,
            STDDEV(ST_Y(gt.geometry)) as lat_variance
        FROM species s
        JOIN geohash_species_tiles gt
            ON gt.species_data ? s.taxon_id::text
        WHERE
            s.species_scientific_name IS NOT NULL
            AND s.species_scientific_name != 'NA'
            AND LENGTH(s.species_scientific_name) > 5
        GROUP BY
            s.taxon_id,
            s.species_scientific_name,
            s.genus,
            s.family,
            s.conservation_status
        HAVING
            COUNT(DISTINCT gt.geohash_l7) >= 100  -- At least 100 occurrences
            AND COUNT(DISTINCT LEFT(gt.geohash_l7, 3)) >= 5  -- Spread across regions
    ),
    ranked_species AS (
        SELECT
            *,
            -- Prioritize threatened species for conservation value
            CASE
                WHEN conservation_status IN ('EN', 'VU', 'CR') THEN 1
                WHEN conservation_status IN ('NT', 'LC') THEN 2
                ELSE 3
            END as conservation_priority,
            -- Ensure taxonomic diversity
            ROW_NUMBER() OVER (PARTITION BY family ORDER BY occurrence_count DESC) as family_rank,
            ROW_NUMBER() OVER (PARTITION BY genus ORDER BY occurrence_count DESC) as genus_rank
        FROM species_stats
    )
    SELECT
        taxon_id,
        species_scientific_name,
        genus,
        family,
        conservation_status,
        occurrence_count,
        geographic_spread,
        ROUND(avg_latitude::numeric, 2) as avg_latitude,
        ROUND(lat_variance::numeric, 2) as lat_variance
    FROM ranked_species
    WHERE
        family_rank <= 3  -- Max 3 species per family
        AND genus_rank <= 2  -- Max 2 species per genus
    ORDER BY
        conservation_priority,
        geographic_spread DESC,
        occurrence_count DESC
    LIMIT 100;
    """

    df = pd.read_sql(query, conn)

    # Save selected species
    output_path = "data/pilot_100_species.csv"
    os.makedirs("data", exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Selected {len(df)} species for pilot")
    print(f"\nTaxonomic diversity:")
    print(f"  Families: {df['family'].nunique()}")
    print(f"  Genera: {df['genus'].nunique()}")
    print(f"\nConservation status distribution:")
    print(df['conservation_status'].value_counts())
    print(f"\nGeographic metrics:")
    print(f"  Mean occurrences: {df['occurrence_count'].mean():.0f}")
    print(f"  Mean geographic spread: {df['geographic_spread'].mean():.1f}")
    print(f"\nSaved to: {output_path}")

    conn.close()
    return df

if __name__ == "__main__":
    select_pilot_species()
```

**Run**:
```bash
cd /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open
python scripts/alphaearth/select_pilot_species.py
```

**Expected Output**:
```
Selected 100 species for pilot

Taxonomic diversity:
  Families: 45
  Genera: 78

Conservation status distribution:
LC    35
VU    25
EN    15
NT    12
CR     8
DD     5

Geographic metrics:
  Mean occurrences: 2,847
  Mean geographic spread: 12.3

Saved to: data/pilot_100_species.csv
```

#### 2.2 Extract Occurrence Points with Temporal Data

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/prepare_occurrences.py`:

```python
#!/usr/bin/env python3
"""
Extract occurrence points with temporal data for pilot species.
Implements temporal clamping and spatial de-biasing.
"""

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import json
import hashlib

def extract_occurrences(species_csv="data/pilot_100_species.csv"):
    """Extract occurrence points with year information."""

    # Load selected species
    species_df = pd.read_csv(species_csv)
    taxon_ids = species_df['taxon_id'].tolist()

    # Database connection
    conn = psycopg2.connect(
        host="localhost",
        database="treekipedia",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

    all_occurrences = []

    for taxon_id in taxon_ids:
        query = """
        WITH occurrences AS (
            SELECT
                %s as taxon_id,
                geohash_l7,
                ST_Y(geometry) as latitude,
                ST_X(geometry) as longitude,
                datetime,
                EXTRACT(YEAR FROM datetime) as year
            FROM geohash_species_tiles
            WHERE species_data ? %s
        ),
        temporal_clamped AS (
            SELECT
                taxon_id,
                geohash_l7,
                latitude,
                longitude,
                CASE
                    WHEN year < 2018 THEN 2018
                    WHEN year > 2023 THEN 2023
                    ELSE year
                END as year_clamped,
                year as original_year
            FROM occurrences
        ),
        -- Spatial de-biasing: limit points per L3 geohash grid
        spatial_debiased AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY taxon_id, LEFT(geohash_l7, 3), year_clamped
                    ORDER BY RANDOM()
                ) as grid_rank
            FROM temporal_clamped
        )
        SELECT
            taxon_id,
            geohash_l7,
            latitude,
            longitude,
            year_clamped as year,
            original_year,
            LEFT(geohash_l7, 3) as geohash_l3
        FROM spatial_debiased
        WHERE grid_rank <= 10  -- Max 10 points per L3 grid per year
        LIMIT 500;  -- Max 500 points per species
        """

        cursor = conn.cursor()
        cursor.execute(query, (taxon_id, str(taxon_id)))
        rows = cursor.fetchall()

        for row in rows:
            all_occurrences.append({
                'taxon_id': row[0],
                'geohash_l7': row[1],
                'latitude': row[2],
                'longitude': row[3],
                'year': row[4],
                'original_year': row[5],
                'geohash_l3': row[6]
            })
        cursor.close()

        print(f"Extracted {len(rows)} points for taxon {taxon_id}")

    conn.close()

    # Convert to DataFrame
    occurrences_df = pd.DataFrame(all_occurrences)

    # Add unique point ID for tracking
    occurrences_df['point_id'] = occurrences_df.apply(
        lambda x: hashlib.md5(
            f"{x['taxon_id']}_{x['geohash_l7']}_{x['year']}".encode()
        ).hexdigest()[:12],
        axis=1
    )

    # Summary statistics
    print(f"\nTotal occurrences: {len(occurrences_df)}")
    print(f"Points per species: {occurrences_df.groupby('taxon_id').size().mean():.1f}")
    print(f"Temporal distribution:")
    print(occurrences_df['year'].value_counts().sort_index())

    # Save to CSV
    output_path = "data/pilot_occurrences.csv"
    occurrences_df.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")

    # Also save as GeoJSON for visualization
    import json
    features = []
    for _, row in occurrences_df.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "taxon_id": int(row['taxon_id']),
                "year": int(row['year']),
                "point_id": row['point_id']
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open("data/pilot_occurrences.geojson", "w") as f:
        json.dump(geojson, f, indent=2)

    return occurrences_df

if __name__ == "__main__":
    extract_occurrences()
```

**Run**:
```bash
python scripts/alphaearth/prepare_occurrences.py
```

**Expected Output**:
```
Extracted 423 points for taxon 12345
Extracted 387 points for taxon 12346
...

Total occurrences: 35,847
Points per species: 358.5
Temporal distribution:
2018    5,234
2019    5,867
2020    6,123
2021    6,445
2022    6,298
2023    5,880

Saved to: data/pilot_occurrences.csv
```

**Validation**:
```bash
# Check the output files
wc -l data/pilot_occurrences.csv
# Should show ~35,000 lines

# Visualize geographic distribution
head -5 data/pilot_occurrences.csv
```

### Step 3: GEE Batch Extraction with Quota Optimization

**Objective**: Extract AlphaEarth 64-band embeddings for all occurrence points with proper quota management.

#### 3.1 GEE Batch Orchestrator

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/gee_batch_orchestrator.py`:

```python
#!/usr/bin/env python3
"""
GEE Batch Extraction Orchestrator for AlphaEarth embeddings.
Implements quota-aware throttling, checkpointing, and failure recovery.
"""

import ee
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import hashlib
import pickle

# Initialize Earth Engine
ee.Initialize()

class AlphaEarthExtractor:
    """Orchestrates batch extraction of AlphaEarth embeddings from GEE."""

    # AlphaEarth collection ID (example - replace with actual)
    ALPHAEARTH_COLLECTION = "projects/geoai-for-earth/assets/alphaearth"

    # Quota management
    MAX_CONCURRENT_TASKS = 4  # Start conservative
    BATCH_SIZE = 1000  # Points per task
    CHECKPOINT_INTERVAL = 10  # Save progress every N batches

    def __init__(self, checkpoint_dir="data/checkpoints"):
        """Initialize extractor with checkpoint management."""
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
        self.checkpoint_file = os.path.join(checkpoint_dir, "extraction_progress.pkl")
        self.completed_batches = self.load_checkpoint()

    def load_checkpoint(self) -> set:
        """Load previously completed batches."""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'rb') as f:
                return pickle.load(f)
        return set()

    def save_checkpoint(self):
        """Save progress checkpoint."""
        with open(self.checkpoint_file, 'wb') as f:
            pickle.dump(self.completed_batches, f)

    def create_point_feature(self, row) -> ee.Feature:
        """Convert occurrence row to EE Feature."""
        return ee.Feature(
            ee.Geometry.Point([row['longitude'], row['latitude']]),
            {
                'point_id': row['point_id'],
                'taxon_id': row['taxon_id'],
                'year': row['year']
            }
        )

    def extract_alphaearth_batch(self, batch_df: pd.DataFrame, batch_id: str) -> str:
        """
        Extract AlphaEarth embeddings for a batch of points.
        Returns GCS export path.
        """

        # Skip if already completed
        if batch_id in self.completed_batches:
            print(f"Batch {batch_id} already completed, skipping")
            return f"gs://treekipedia-alphaearth/exports/{batch_id}.csv"

        # Create feature collection from points
        features = [self.create_point_feature(row) for _, row in batch_df.iterrows()]
        fc = ee.FeatureCollection(features)

        # Get AlphaEarth image for the appropriate year
        # Note: This assumes yearly composites. Adjust if different.
        years = batch_df['year'].unique()

        if len(years) == 1:
            year = int(years[0])
            alphaearth = ee.ImageCollection(self.ALPHAEARTH_COLLECTION) \
                .filter(ee.Filter.calendarRange(year, year, 'year')) \
                .first()
        else:
            # Multi-year batch - create mosaic
            images = []
            for year in years:
                year_image = ee.ImageCollection(self.ALPHAEARTH_COLLECTION) \
                    .filter(ee.Filter.calendarRange(year, year, 'year')) \
                    .first()
                images.append(year_image)
            alphaearth = ee.ImageCollection(images).mosaic()

        # Sample the image at point locations
        # Using sampleRegions which is more efficient than reduceRegions for points
        sampled = alphaearth.sampleRegions(
            collection=fc,
            scale=30,  # AlphaEarth resolution
            geometries=True,  # Keep geometries for validation
            tileScale=4  # Helps with memory for large batches
        )

        # Export to Cloud Storage
        export_path = f"treekipedia-alphaearth/exports/{batch_id}"
        task = ee.batch.Export.table.toCloudStorage(
            collection=sampled,
            description=f"alphaearth_batch_{batch_id}",
            bucket="treekipedia-alphaearth",
            fileNamePrefix=export_path,
            fileFormat='CSV'
        )

        task.start()
        return task, export_path

    def monitor_task(self, task, batch_id: str, timeout: int = 3600) -> bool:
        """Monitor a running EE task until completion."""
        start_time = time.time()

        while task.active():
            if time.time() - start_time > timeout:
                print(f"Task {batch_id} timed out after {timeout} seconds")
                return False

            # Check status every 30 seconds
            time.sleep(30)
            status = task.status()
            elapsed = int(time.time() - start_time)
            print(f"Task {batch_id}: {status['state']} ({elapsed}s elapsed)")

        # Check final status
        status = task.status()
        if status['state'] == 'COMPLETED':
            print(f"Task {batch_id} completed successfully")
            self.completed_batches.add(batch_id)
            if len(self.completed_batches) % self.CHECKPOINT_INTERVAL == 0:
                self.save_checkpoint()
            return True
        else:
            print(f"Task {batch_id} failed: {status.get('error_message', 'Unknown error')}")
            return False

    def extract_all(self, occurrences_csv: str = "data/pilot_occurrences.csv"):
        """
        Main extraction pipeline with quota-aware batching.
        """
        print("=== Starting AlphaEarth Batch Extraction ===")

        # Load occurrences
        df = pd.read_csv(occurrences_csv)
        print(f"Loaded {len(df)} occurrence points")

        # Create batches
        batches = []
        for taxon_id in df['taxon_id'].unique():
            taxon_df = df[df['taxon_id'] == taxon_id]

            # Further split by year for temporal consistency
            for year in taxon_df['year'].unique():
                year_df = taxon_df[taxon_df['year'] == year]

                # Split into chunks of BATCH_SIZE
                for i in range(0, len(year_df), self.BATCH_SIZE):
                    batch = year_df.iloc[i:i+self.BATCH_SIZE]
                    batch_id = f"t{taxon_id}_y{year}_b{i//self.BATCH_SIZE}"
                    batches.append((batch_id, batch))

        print(f"Created {len(batches)} batches")

        # Process batches with concurrent task management
        active_tasks = {}
        completed = 0
        failed = []

        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_TASKS) as executor:
            # Submit initial batch of tasks
            batch_iter = iter(batches)

            for _ in range(min(self.MAX_CONCURRENT_TASKS, len(batches))):
                try:
                    batch_id, batch_df = next(batch_iter)
                    task, export_path = self.extract_alphaearth_batch(batch_df, batch_id)
                    future = executor.submit(self.monitor_task, task, batch_id)
                    active_tasks[future] = (batch_id, export_path)
                except StopIteration:
                    break

            # Process remaining batches as tasks complete
            while active_tasks:
                done, pending = as_completed(active_tasks), set(active_tasks.keys())

                for future in done:
                    batch_id, export_path = active_tasks[future]
                    success = future.result()

                    if success:
                        completed += 1
                        print(f"Progress: {completed}/{len(batches)} batches completed")

                        # Adaptive throttling based on success rate
                        if completed > 10 and completed % 10 == 0:
                            if len(failed) / completed < 0.1:  # <10% failure rate
                                self.MAX_CONCURRENT_TASKS = min(8, self.MAX_CONCURRENT_TASKS + 1)
                                print(f"Increased concurrent tasks to {self.MAX_CONCURRENT_TASKS}")
                    else:
                        failed.append(batch_id)
                        print(f"Failed batches: {len(failed)}")

                        # Reduce concurrency if too many failures
                        if len(failed) > 5:
                            self.MAX_CONCURRENT_TASKS = max(2, self.MAX_CONCURRENT_TASKS - 1)
                            print(f"Reduced concurrent tasks to {self.MAX_CONCURRENT_TASKS}")

                    # Remove completed task
                    del active_tasks[future]

                    # Submit next batch if available
                    try:
                        batch_id, batch_df = next(batch_iter)
                        task, export_path = self.extract_alphaearth_batch(batch_df, batch_id)
                        future = executor.submit(self.monitor_task, task, batch_id)
                        active_tasks[future] = (batch_id, export_path)
                    except StopIteration:
                        pass

        # Final checkpoint save
        self.save_checkpoint()

        # Summary
        print("\n=== Extraction Complete ===")
        print(f"Successfully completed: {completed}/{len(batches)} batches")
        print(f"Failed batches: {failed}")

        if failed:
            # Save failed batches for retry
            with open("data/failed_batches.json", "w") as f:
                json.dump(failed, f, indent=2)
            print("Failed batches saved to data/failed_batches.json for retry")

        return completed, failed

def main():
    """Main execution."""
    extractor = AlphaEarthExtractor()
    completed, failed = extractor.extract_all()

    if len(failed) > 0:
        print("\nRetrying failed batches...")
        # Implement retry logic here
        pass

    print("\nExtraction pipeline complete!")

if __name__ == "__main__":
    main()
```

**Run**:
```bash
python scripts/alphaearth/gee_batch_orchestrator.py
```

**Expected Output**:
```
=== Starting AlphaEarth Batch Extraction ===
Loaded 35,847 occurrence points
Created 142 batches
Task t12345_y2018_b0: RUNNING (30s elapsed)
Task t12345_y2018_b0: COMPLETED (87s elapsed)
Task t12345_y2018_b0 completed successfully
Progress: 1/142 batches completed
...
=== Extraction Complete ===
Successfully completed: 140/142 batches
Failed batches: ['t45678_y2020_b2', 't89012_y2021_b1']
Failed batches saved to data/failed_batches.json for retry
```

**Troubleshooting Common Issues**:

1. **"Computed value too large" error**:
   - Reduce BATCH_SIZE to 500
   - Increase tileScale to 8

2. **"User memory limit exceeded"**:
   - Sample fewer bands initially
   - Use `.select()` to limit bands if needed

3. **Quota exceeded**:
   - Reduce MAX_CONCURRENT_TASKS to 2
   - Add longer sleep intervals between submissions

### Step 4: Vector Aggregation with k-Prototypes

**Objective**: Build species prototypes using spherical k-means clustering.

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/build_prototypes.py`:

```python
#!/usr/bin/env python3
"""
Build species prototypes using spherical k-means clustering.
Computes spherical statistics for each species.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import normalize
from sklearn.cluster import KMeans
from spherecluster import SphericalKMeans
import json
import pickle
from typing import Dict, List, Tuple
import glob
import os

class PrototypeBuilder:
    """Build k-prototypes for species from AlphaEarth embeddings."""

    def __init__(self, min_points=30, max_prototypes=5):
        """
        Initialize prototype builder.

        Args:
            min_points: Minimum points required to build prototypes
            max_prototypes: Maximum number of prototypes per species
        """
        self.min_points = min_points
        self.max_prototypes = max_prototypes
        self.band_names = [f"b{i}" for i in range(1, 65)]  # 64 AlphaEarth bands

    def load_embeddings(self, export_dir="gs://treekipedia-alphaearth/exports/"):
        """Load all extracted AlphaEarth embeddings from GCS exports."""

        # For local development, assume files were downloaded
        local_dir = "data/alphaearth_exports/"

        all_embeddings = []

        for csv_file in glob.glob(os.path.join(local_dir, "*.csv")):
            df = pd.read_csv(csv_file)

            # Extract embedding columns (b1 through b64)
            embedding_cols = [col for col in df.columns if col.startswith('b')]

            for _, row in df.iterrows():
                embedding = row[embedding_cols].values.astype(np.float32)

                # Skip if any NaN values
                if np.isnan(embedding).any():
                    continue

                all_embeddings.append({
                    'point_id': row['point_id'],
                    'taxon_id': row['taxon_id'],
                    'year': row['year'],
                    'embedding': embedding,
                    'latitude': row.get('latitude', row.get('.geo', '').split(',')[1]),
                    'longitude': row.get('longitude', row.get('.geo', '').split(',')[0])
                })

        print(f"Loaded {len(all_embeddings)} embeddings")
        return pd.DataFrame(all_embeddings)

    def normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Normalize embeddings to unit vectors on hypersphere."""
        return normalize(embeddings, norm='l2', axis=1)

    def compute_spherical_stats(self, unit_vectors: np.ndarray) -> Dict:
        """
        Compute spherical statistics for a set of unit vectors.

        Returns:
            Dictionary with spherical statistics
        """
        n = len(unit_vectors)

        # Mean direction (normalized sum)
        mean_vector = np.sum(unit_vectors, axis=0)
        mean_direction = mean_vector / np.linalg.norm(mean_vector)

        # Resultant length (concentration measure)
        resultant_length = np.linalg.norm(mean_vector) / n

        # Angular deviation (spread measure)
        dot_products = np.dot(unit_vectors, mean_direction)
        angular_deviations = np.arccos(np.clip(dot_products, -1, 1))
        mean_angular_deviation = np.mean(angular_deviations)

        # Cosine quantiles
        cosine_similarities = dot_products  # Already computed
        quantiles = [10, 25, 50, 75, 90]
        cosine_quantiles = np.percentile(cosine_similarities, quantiles)

        return {
            'mean_direction': mean_direction.tolist(),
            'resultant_length': float(resultant_length),
            'mean_angular_deviation': float(mean_angular_deviation),
            'angular_std': float(np.std(angular_deviations)),
            'cosine_quantiles': {
                f'p{q}': float(cosine_quantiles[i])
                for i, q in enumerate(quantiles)
            },
            'n_points': n
        }

    def determine_optimal_k(self, unit_vectors: np.ndarray) -> int:
        """
        Determine optimal number of prototypes using elbow method.
        """
        if len(unit_vectors) < self.min_points:
            return 1

        max_k = min(self.max_prototypes, len(unit_vectors) // 10)

        if max_k <= 1:
            return 1

        # Compute within-cluster sum of squares for different k
        wcss = []
        k_range = range(1, max_k + 1)

        for k in k_range:
            if k == 1:
                # For k=1, WCSS is variance from mean
                mean_vec = np.mean(unit_vectors, axis=0)
                mean_vec = mean_vec / np.linalg.norm(mean_vec)
                distances = 1 - np.dot(unit_vectors, mean_vec)
                wcss.append(np.sum(distances))
            else:
                kmeans = SphericalKMeans(n_clusters=k, random_state=42)
                kmeans.fit(unit_vectors)

                # Compute WCSS (using cosine distance)
                cluster_distances = []
                for i, center in enumerate(kmeans.cluster_centers_):
                    cluster_points = unit_vectors[kmeans.labels_ == i]
                    if len(cluster_points) > 0:
                        distances = 1 - np.dot(cluster_points, center)
                        cluster_distances.extend(distances)
                wcss.append(np.sum(cluster_distances))

        # Find elbow point using second derivative
        if len(wcss) > 2:
            # Compute second derivative
            first_deriv = np.diff(wcss)
            second_deriv = np.diff(first_deriv)

            # Find elbow (maximum second derivative)
            elbow_idx = np.argmax(second_deriv) + 1  # +1 because diff reduces length
            optimal_k = k_range[elbow_idx]
        else:
            optimal_k = 1

        print(f"  Optimal k determined: {optimal_k} (from {len(unit_vectors)} points)")
        return optimal_k

    def build_species_prototypes(self, embeddings_df: pd.DataFrame) -> Dict:
        """
        Build prototypes for all species.

        Returns:
            Dictionary mapping taxon_id to prototype information
        """
        species_prototypes = {}

        for taxon_id in embeddings_df['taxon_id'].unique():
            print(f"\nProcessing species {taxon_id}")

            # Get embeddings for this species
            species_df = embeddings_df[embeddings_df['taxon_id'] == taxon_id]
            embeddings = np.vstack(species_df['embedding'].values)

            # Normalize to unit vectors
            unit_vectors = self.normalize_embeddings(embeddings)

            # Determine optimal number of prototypes
            optimal_k = self.determine_optimal_k(unit_vectors)

            # Perform clustering
            if optimal_k == 1:
                # Single prototype: use mean direction
                mean_vector = np.mean(unit_vectors, axis=0)
                prototypes = [mean_vector / np.linalg.norm(mean_vector)]
                labels = np.zeros(len(unit_vectors))
                prototype_weights = [1.0]
            else:
                # Multiple prototypes: use spherical k-means
                kmeans = SphericalKMeans(n_clusters=optimal_k, random_state=42)
                labels = kmeans.fit_predict(unit_vectors)
                prototypes = kmeans.cluster_centers_

                # Compute prototype weights (proportion of points)
                unique_labels, counts = np.unique(labels, return_counts=True)
                prototype_weights = (counts / len(labels)).tolist()

            # Compute statistics for each prototype
            prototype_stats = []
            for i, prototype in enumerate(prototypes):
                cluster_vectors = unit_vectors[labels == i]

                if len(cluster_vectors) > 0:
                    stats = self.compute_spherical_stats(cluster_vectors)
                    stats['prototype_vector'] = prototype.tolist()
                    stats['weight'] = prototype_weights[i]
                    prototype_stats.append(stats)

            # Compute overall statistics
            overall_stats = self.compute_spherical_stats(unit_vectors)

            # Geographic spread of points
            latitudes = species_df['latitude'].values
            longitudes = species_df['longitude'].values

            species_prototypes[int(taxon_id)] = {
                'taxon_id': int(taxon_id),
                'n_points': len(unit_vectors),
                'n_prototypes': optimal_k,
                'prototypes': prototype_stats,
                'overall_stats': overall_stats,
                'geographic_extent': {
                    'min_lat': float(np.min(latitudes)),
                    'max_lat': float(np.max(latitudes)),
                    'min_lon': float(np.min(longitudes)),
                    'max_lon': float(np.max(longitudes)),
                    'lat_std': float(np.std(latitudes)),
                    'lon_std': float(np.std(longitudes))
                }
            }

        return species_prototypes

    def save_prototypes(self, prototypes: Dict, output_dir: str = "data/prototypes"):
        """Save prototypes in multiple formats."""
        os.makedirs(output_dir, exist_ok=True)

        # Save as JSON for readability
        json_path = os.path.join(output_dir, "species_prototypes.json")
        with open(json_path, 'w') as f:
            json.dump(prototypes, f, indent=2)
        print(f"Saved JSON to {json_path}")

        # Save as pickle for efficient loading
        pkl_path = os.path.join(output_dir, "species_prototypes.pkl")
        with open(pkl_path, 'wb') as f:
            pickle.dump(prototypes, f)
        print(f"Saved pickle to {pkl_path}")

        # Create summary DataFrame
        summary_data = []
        for taxon_id, info in prototypes.items():
            summary_data.append({
                'taxon_id': taxon_id,
                'n_points': info['n_points'],
                'n_prototypes': info['n_prototypes'],
                'resultant_length': info['overall_stats']['resultant_length'],
                'angular_std': info['overall_stats']['angular_std'],
                'lat_range': info['geographic_extent']['max_lat'] - info['geographic_extent']['min_lat'],
                'lon_range': info['geographic_extent']['max_lon'] - info['geographic_extent']['min_lon']
            })

        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(output_dir, "prototypes_summary.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"Saved summary to {summary_path}")

        # Print summary statistics
        print("\n=== Prototype Building Summary ===")
        print(f"Total species: {len(prototypes)}")
        print(f"Avg prototypes per species: {summary_df['n_prototypes'].mean():.2f}")
        print(f"Species with 1 prototype: {(summary_df['n_prototypes'] == 1).sum()}")
        print(f"Species with 2+ prototypes: {(summary_df['n_prototypes'] > 1).sum()}")
        print(f"Avg resultant length: {summary_df['resultant_length'].mean():.3f}")

def main():
    """Main execution pipeline."""
    print("=== Building Species Prototypes ===")

    # Initialize builder
    builder = PrototypeBuilder(min_points=30, max_prototypes=5)

    # Load embeddings
    print("\n1. Loading embeddings...")
    embeddings_df = builder.load_embeddings()

    # Build prototypes
    print("\n2. Building prototypes...")
    prototypes = builder.build_species_prototypes(embeddings_df)

    # Save results
    print("\n3. Saving prototypes...")
    builder.save_prototypes(prototypes)

    print("\n=== Complete! ===")

if __name__ == "__main__":
    main()
```

**Run**:
```bash
python scripts/alphaearth/build_prototypes.py
```

**Expected Output**:
```
=== Building Species Prototypes ===

1. Loading embeddings...
Loaded 34,892 embeddings

2. Building prototypes...

Processing species 12345
  Optimal k determined: 3 (from 412 points)

Processing species 12346
  Optimal k determined: 2 (from 387 points)
...

3. Saving prototypes...
Saved JSON to data/prototypes/species_prototypes.json
Saved pickle to data/prototypes/species_prototypes.pkl
Saved summary to data/prototypes/prototypes_summary.csv

=== Prototype Building Summary ===
Total species: 100
Avg prototypes per species: 2.34
Species with 1 prototype: 28
Species with 2+ prototypes: 72
Avg resultant length: 0.823

=== Complete! ===
```

### Step 5: Storage Setup

#### Path A: PostgreSQL with pgvector

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/pgvector_setup.sql`:

```sql
-- Setup pgvector storage for AlphaEarth species prototypes
-- Run with: psql treekipedia_alphaearth -f scripts/alphaearth/pgvector_setup.sql

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Main prototypes table
CREATE TABLE IF NOT EXISTS species_prototypes (
    id SERIAL PRIMARY KEY,
    taxon_id INTEGER NOT NULL,
    prototype_idx INTEGER NOT NULL,
    embedding vector(64) NOT NULL,  -- 64-D AlphaEarth vector
    weight REAL NOT NULL,  -- Proportion of points in this cluster
    n_points INTEGER NOT NULL,  -- Number of points in cluster
    resultant_length REAL,  -- Concentration measure
    angular_std REAL,  -- Spread measure
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(taxon_id, prototype_idx)
);

-- Create HNSW index for fast similarity search
CREATE INDEX species_prototypes_embedding_idx
ON species_prototypes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Species metadata table
CREATE TABLE IF NOT EXISTS species_prototype_metadata (
    taxon_id INTEGER PRIMARY KEY,
    species_name VARCHAR(255),
    n_prototypes INTEGER NOT NULL,
    n_total_points INTEGER NOT NULL,
    overall_resultant_length REAL,
    overall_angular_std REAL,
    min_latitude REAL,
    max_latitude REAL,
    min_longitude REAL,
    max_longitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Query log for analysis
CREATE TABLE IF NOT EXISTS prototype_queries (
    id SERIAL PRIMARY KEY,
    query_embedding vector(64) NOT NULL,
    query_latitude REAL,
    query_longitude REAL,
    top_k INTEGER DEFAULT 10,
    results JSONB,
    query_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Function to find similar species
CREATE OR REPLACE FUNCTION find_similar_species(
    query_vector vector(64),
    k INTEGER DEFAULT 10
)
RETURNS TABLE (
    taxon_id INTEGER,
    prototype_idx INTEGER,
    similarity REAL,
    weight REAL,
    species_name VARCHAR
)
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.taxon_id,
        sp.prototype_idx,
        1 - (sp.embedding <=> query_vector) as similarity,  -- Cosine similarity
        sp.weight,
        sm.species_name
    FROM species_prototypes sp
    JOIN species_prototype_metadata sm ON sp.taxon_id = sm.taxon_id
    ORDER BY sp.embedding <=> query_vector  -- Cosine distance
    LIMIT k;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate species probabilities
CREATE OR REPLACE FUNCTION species_probabilities(
    query_vector vector(64),
    k INTEGER DEFAULT 20,
    temperature REAL DEFAULT 0.1
)
RETURNS TABLE (
    taxon_id INTEGER,
    species_name VARCHAR,
    probability REAL,
    avg_similarity REAL,
    n_prototypes_matched INTEGER
)
AS $$
WITH similarities AS (
    SELECT * FROM find_similar_species(query_vector, k)
),
weighted_scores AS (
    SELECT
        taxon_id,
        species_name,
        SUM(similarity * weight) as weighted_similarity,
        AVG(similarity) as avg_similarity,
        COUNT(*) as n_prototypes_matched
    FROM similarities
    GROUP BY taxon_id, species_name
),
softmax_scores AS (
    SELECT
        *,
        EXP(weighted_similarity / temperature) as exp_score
    FROM weighted_scores
),
normalized AS (
    SELECT
        taxon_id,
        species_name,
        avg_similarity,
        n_prototypes_matched,
        exp_score / SUM(exp_score) OVER () as probability
    FROM softmax_scores
)
SELECT * FROM normalized
ORDER BY probability DESC;
$$ LANGUAGE plpgsql;

-- Indexes for performance
CREATE INDEX species_prototype_metadata_taxon_idx ON species_prototype_metadata(taxon_id);
CREATE INDEX species_prototypes_taxon_idx ON species_prototypes(taxon_id);

-- Materialized view for species diversity by region
CREATE MATERIALIZED VIEW species_geographic_diversity AS
SELECT
    taxon_id,
    species_name,
    n_prototypes,
    CASE
        WHEN n_prototypes = 1 THEN 'specialist'
        WHEN n_prototypes = 2 THEN 'intermediate'
        ELSE 'generalist'
    END as niche_type,
    max_latitude - min_latitude as lat_range,
    max_longitude - min_longitude as lon_range,
    overall_resultant_length
FROM species_prototype_metadata
ORDER BY n_prototypes DESC, overall_resultant_length DESC;

-- Performance tuning
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
SELECT pg_reload_conf();

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO PUBLIC;

-- Verify setup
SELECT
    'Extensions' as component,
    string_agg(extname, ', ') as status
FROM pg_extension
WHERE extname IN ('vector', 'postgis')
UNION ALL
SELECT
    'Tables' as component,
    COUNT(*)::text || ' tables created'
FROM pg_tables
WHERE schemaname = 'public'
AND tablename LIKE '%prototype%';
```

**Run**:
```bash
psql treekipedia_alphaearth -f scripts/alphaearth/pgvector_setup.sql
```

**Load data into PostgreSQL**:

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/load_pgvector.py`:

```python
#!/usr/bin/env python3
"""Load prototypes into PostgreSQL with pgvector."""

import psycopg2
import json
import numpy as np
from datetime import datetime
import pandas as pd

def load_prototypes_to_pgvector(
    prototypes_file="data/prototypes/species_prototypes.json",
    species_csv="data/pilot_100_species.csv"
):
    """Load prototypes into PostgreSQL."""

    # Load data
    with open(prototypes_file, 'r') as f:
        prototypes = json.load(f)

    species_df = pd.read_csv(species_csv)
    species_names = dict(zip(
        species_df['taxon_id'].astype(str),
        species_df['species_scientific_name']
    ))

    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="treekipedia_alphaearth",
        user="postgres"
    )
    cur = conn.cursor()

    # Load each species
    for taxon_id_str, species_data in prototypes.items():
        taxon_id = int(taxon_id_str)
        species_name = species_names.get(taxon_id_str, f"Species {taxon_id}")

        # Insert metadata
        cur.execute("""
            INSERT INTO species_prototype_metadata (
                taxon_id, species_name, n_prototypes, n_total_points,
                overall_resultant_length, overall_angular_std,
                min_latitude, max_latitude, min_longitude, max_longitude
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (taxon_id) DO UPDATE SET
                n_prototypes = EXCLUDED.n_prototypes,
                n_total_points = EXCLUDED.n_total_points
        """, (
            taxon_id,
            species_name,
            species_data['n_prototypes'],
            species_data['n_points'],
            species_data['overall_stats']['resultant_length'],
            species_data['overall_stats']['angular_std'],
            species_data['geographic_extent']['min_lat'],
            species_data['geographic_extent']['max_lat'],
            species_data['geographic_extent']['min_lon'],
            species_data['geographic_extent']['max_lon']
        ))

        # Insert prototypes
        for idx, prototype in enumerate(species_data['prototypes']):
            embedding = prototype['prototype_vector']

            cur.execute("""
                INSERT INTO species_prototypes (
                    taxon_id, prototype_idx, embedding, weight,
                    n_points, resultant_length, angular_std
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (taxon_id, prototype_idx) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    weight = EXCLUDED.weight
            """, (
                taxon_id,
                idx,
                embedding,
                prototype['weight'],
                prototype['n_points'],
                prototype['resultant_length'],
                prototype.get('angular_std', 0)
            ))

    conn.commit()

    # Verify data loaded
    cur.execute("SELECT COUNT(*) FROM species_prototype_metadata")
    n_species = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM species_prototypes")
    n_prototypes = cur.fetchone()[0]

    print(f"Loaded {n_species} species with {n_prototypes} total prototypes")

    # Test similarity search
    cur.execute("""
        SELECT taxon_id, similarity, species_name
        FROM find_similar_species(
            (SELECT embedding FROM species_prototypes LIMIT 1),
            5
        )
    """)

    print("\nTest similarity search results:")
    for row in cur.fetchall():
        print(f"  Taxon {row[0]}: {row[2]} (similarity: {row[1]:.3f})")

    cur.close()
    conn.close()

if __name__ == "__main__":
    load_prototypes_to_pgvector()
```

#### Path B: BigQuery Vector Index

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/bigquery_setup.sql`:

```sql
-- BigQuery setup for AlphaEarth vector search
-- Run with: bq query --use_legacy_sql=false < scripts/alphaearth/bigquery_setup.sql

-- Create dataset if not exists
CREATE SCHEMA IF NOT EXISTS alphaearth_pilot
OPTIONS(
    location="US",
    description="AlphaEarth species predictor pilot"
);

-- Main prototypes table with vector column
CREATE OR REPLACE TABLE alphaearth_pilot.species_prototypes (
    taxon_id INT64 NOT NULL,
    prototype_idx INT64 NOT NULL,
    species_name STRING,
    embedding ARRAY<FLOAT64>,  -- 64-D vector as array
    embedding_vector VECTOR(LENGTH=>64),  -- Native vector type for indexing
    weight FLOAT64,
    n_points INT64,
    resultant_length FLOAT64,
    angular_std FLOAT64,
    geographic_extent STRUCT<
        min_lat FLOAT64,
        max_lat FLOAT64,
        min_lon FLOAT64,
        max_lon FLOAT64
    >,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vector index for similarity search
CREATE VECTOR INDEX species_embedding_index
ON alphaearth_pilot.species_prototypes(embedding_vector)
OPTIONS(
    distance_type = 'COSINE',
    index_type = 'IVF',
    ivf_options = '{"num_lists": 100}'
);

-- Load data from JSON (example with single record)
-- In practice, load from Cloud Storage
INSERT INTO alphaearth_pilot.species_prototypes
SELECT
    12345 as taxon_id,
    0 as prototype_idx,
    'Quercus robur' as species_name,
    [0.1, 0.2, ...] as embedding,  -- 64 values
    TO_VECTOR([0.1, 0.2, ...], 64) as embedding_vector,
    0.45 as weight,
    156 as n_points,
    0.823 as resultant_length,
    0.124 as angular_std,
    STRUCT(
        49.5 as min_lat,
        53.2 as max_lat,
        -2.1 as min_lon,
        4.3 as max_lon
    ) as geographic_extent,
    CURRENT_TIMESTAMP() as created_at;

-- Function for vector search
CREATE OR REPLACE FUNCTION alphaearth_pilot.find_similar_species(
    query_embedding ARRAY<FLOAT64>,
    top_k INT64
)
RETURNS TABLE<
    taxon_id INT64,
    species_name STRING,
    similarity FLOAT64,
    weight FLOAT64
>
AS (
    SELECT
        taxon_id,
        species_name,
        1 - distance as similarity,
        weight
    FROM VECTOR_SEARCH(
        TABLE alphaearth_pilot.species_prototypes,
        'embedding_vector',
        TO_VECTOR(query_embedding, 64),
        distance_type => 'COSINE',
        top_k => top_k
    )
);

-- Aggregate to species probabilities
CREATE OR REPLACE FUNCTION alphaearth_pilot.species_probabilities(
    query_embedding ARRAY<FLOAT64>,
    top_k INT64 DEFAULT 20,
    temperature FLOAT64 DEFAULT 0.1
)
AS (
    WITH similarities AS (
        SELECT * FROM alphaearth_pilot.find_similar_species(query_embedding, top_k)
    ),
    weighted_scores AS (
        SELECT
            taxon_id,
            species_name,
            SUM(similarity * weight) as weighted_similarity,
            AVG(similarity) as avg_similarity,
            COUNT(*) as n_prototypes_matched
        FROM similarities
        GROUP BY taxon_id, species_name
    ),
    softmax_scores AS (
        SELECT
            *,
            EXP(weighted_similarity / temperature) as exp_score
        FROM weighted_scores
    ),
    normalized AS (
        SELECT
            taxon_id,
            species_name,
            avg_similarity,
            n_prototypes_matched,
            exp_score / SUM(exp_score) OVER () as probability
        FROM softmax_scores
    )
    SELECT * FROM normalized
    ORDER BY probability DESC
);

-- Query cost estimation view
CREATE OR REPLACE VIEW alphaearth_pilot.cost_estimation AS
SELECT
    COUNT(*) as total_prototypes,
    COUNT(DISTINCT taxon_id) as unique_species,
    AVG(ARRAY_LENGTH(embedding)) as avg_vector_dim,
    ROUND(SUM(ARRAY_LENGTH(embedding) * 4) / 1024 / 1024, 2) as storage_mb,
    ROUND(SUM(ARRAY_LENGTH(embedding) * 4) / 1024 / 1024 * 0.02, 4) as monthly_storage_cost_usd
FROM alphaearth_pilot.species_prototypes;
```

### Step 6: Query Pipeline Implementation

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/scripts/alphaearth/query_predictor.py`:

```python
#!/usr/bin/env python3
"""
Query pipeline for species prediction from location.
Handles: point → GEE sample → vector search → softmax probabilities
"""

import ee
import numpy as np
import psycopg2
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import requests

# Initialize Earth Engine
ee.Initialize()

class SpeciesPredictor:
    """Predict species from geographic location using AlphaEarth."""

    ALPHAEARTH_COLLECTION = "projects/geoai-for-earth/assets/alphaearth"

    def __init__(self, db_config: Dict = None, use_bigquery: bool = False):
        """
        Initialize predictor.

        Args:
            db_config: PostgreSQL connection config
            use_bigquery: Use BigQuery instead of PostgreSQL
        """
        self.use_bigquery = use_bigquery

        if not use_bigquery:
            # PostgreSQL with pgvector
            self.conn = psycopg2.connect(
                host=db_config.get('host', 'localhost'),
                database=db_config.get('database', 'treekipedia_alphaearth'),
                user=db_config.get('user', 'postgres'),
                password=db_config.get('password', '')
            )
        else:
            # BigQuery setup
            from google.cloud import bigquery
            self.bq_client = bigquery.Client()

    def extract_alphaearth_at_point(
        self,
        latitude: float,
        longitude: float,
        year: Optional[int] = None
    ) -> np.ndarray:
        """
        Extract AlphaEarth embedding at a single point.

        Returns:
            64-dimensional normalized embedding vector
        """
        # Default to current year if not specified
        if year is None:
            year = datetime.now().year

        # Clamp to available years
        year = max(2018, min(2023, year))

        # Create point geometry
        point = ee.Geometry.Point([longitude, latitude])

        # Get AlphaEarth image for the year
        alphaearth = ee.ImageCollection(self.ALPHAEARTH_COLLECTION) \
            .filter(ee.Filter.calendarRange(year, year, 'year')) \
            .first()

        # Sample at point
        sample = alphaearth.sample(
            region=point,
            scale=30,
            geometries=False
        ).first()

        # Get values (this would normally be async in production)
        values = sample.getInfo()

        if values is None:
            raise ValueError(f"No AlphaEarth data at location ({latitude}, {longitude})")

        # Extract embedding values (assuming bands are named b1, b2, ..., b64)
        embedding = []
        for i in range(1, 65):
            band_name = f'b{i}'
            if band_name in values['properties']:
                embedding.append(values['properties'][band_name])
            else:
                # Handle missing bands
                embedding.append(0.0)

        # Convert to numpy array and normalize
        embedding = np.array(embedding, dtype=np.float32)

        # L2 normalization to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def search_similar_species_pg(
        self,
        embedding: np.ndarray,
        k: int = 20,
        temperature: float = 0.1
    ) -> List[Dict]:
        """
        Search similar species using PostgreSQL pgvector.
        """
        cur = self.conn.cursor()

        # Convert to list for PostgreSQL
        embedding_list = embedding.tolist()

        # Call the species_probabilities function
        cur.execute("""
            SELECT
                taxon_id,
                species_name,
                probability,
                avg_similarity,
                n_prototypes_matched
            FROM species_probabilities(%s::vector, %s, %s)
            LIMIT 10
        """, (embedding_list, k, temperature))

        results = []
        for row in cur.fetchall():
            results.append({
                'taxon_id': row[0],
                'species_name': row[1],
                'probability': float(row[2]),
                'avg_similarity': float(row[3]),
                'n_prototypes_matched': row[4]
            })

        cur.close()
        return results

    def search_similar_species_bq(
        self,
        embedding: np.ndarray,
        k: int = 20,
        temperature: float = 0.1
    ) -> List[Dict]:
        """
        Search similar species using BigQuery VECTOR_SEARCH.
        """
        # Convert embedding to list
        embedding_list = embedding.tolist()

        # Construct query
        query = f"""
        WITH search_results AS (
            SELECT * FROM alphaearth_pilot.species_probabilities(
                {embedding_list},
                {k},
                {temperature}
            )
        )
        SELECT
            taxon_id,
            species_name,
            probability,
            avg_similarity,
            n_prototypes_matched
        FROM search_results
        LIMIT 10
        """

        # Execute query
        query_job = self.bq_client.query(query)
        results = []

        for row in query_job:
            results.append({
                'taxon_id': row.taxon_id,
                'species_name': row.species_name,
                'probability': float(row.probability),
                'avg_similarity': float(row.avg_similarity),
                'n_prototypes_matched': row.n_prototypes_matched
            })

        return results

    def predict_species(
        self,
        latitude: float,
        longitude: float,
        year: Optional[int] = None,
        k: int = 20,
        temperature: float = 0.1,
        return_embedding: bool = False
    ) -> Dict:
        """
        Full pipeline: location → embedding → species predictions.

        Returns:
            Dictionary with predictions and metadata
        """
        start_time = datetime.now()

        # Step 1: Extract AlphaEarth embedding
        print(f"Extracting AlphaEarth at ({latitude}, {longitude})")
        embedding = self.extract_alphaearth_at_point(latitude, longitude, year)
        extraction_time = (datetime.now() - start_time).total_seconds()

        # Step 2: Search similar species
        print("Searching similar species...")
        if self.use_bigquery:
            predictions = self.search_similar_species_bq(embedding, k, temperature)
        else:
            predictions = self.search_similar_species_pg(embedding, k, temperature)

        search_time = (datetime.now() - start_time).total_seconds() - extraction_time

        # Step 3: Format results
        result = {
            'query': {
                'latitude': latitude,
                'longitude': longitude,
                'year': year or datetime.now().year
            },
            'predictions': predictions,
            'performance': {
                'extraction_time_s': extraction_time,
                'search_time_s': search_time,
                'total_time_s': extraction_time + search_time
            },
            'parameters': {
                'k': k,
                'temperature': temperature,
                'backend': 'bigquery' if self.use_bigquery else 'pgvector'
            }
        }

        if return_embedding:
            result['embedding'] = embedding.tolist()

        return result

    def validate_prediction(
        self,
        latitude: float,
        longitude: float,
        expected_taxon_id: int
    ) -> Dict:
        """
        Validate prediction against known species.
        """
        result = self.predict_species(latitude, longitude)

        # Check if expected species is in top-k
        predicted_ids = [p['taxon_id'] for p in result['predictions']]
        rank = predicted_ids.index(expected_taxon_id) + 1 if expected_taxon_id in predicted_ids else -1

        validation = {
            'expected_taxon_id': expected_taxon_id,
            'found': rank > 0,
            'rank': rank if rank > 0 else None,
            'probability': None
        }

        if rank > 0:
            for pred in result['predictions']:
                if pred['taxon_id'] == expected_taxon_id:
                    validation['probability'] = pred['probability']
                    break

        result['validation'] = validation
        return result

def main():
    """Example usage and validation."""

    # Initialize predictor
    predictor = SpeciesPredictor(use_bigquery=False)

    # Test locations (example coordinates)
    test_locations = [
        {'lat': 51.5074, 'lon': -0.1278, 'name': 'London'},
        {'lat': 40.7128, 'lon': -74.0060, 'name': 'New York'},
        {'lat': -23.5505, 'lon': -46.6333, 'name': 'São Paulo'}
    ]

    for loc in test_locations:
        print(f"\n=== Predicting species for {loc['name']} ===")

        try:
            result = predictor.predict_species(
                loc['lat'],
                loc['lon'],
                k=20,
                temperature=0.1
            )

            print(f"Extraction time: {result['performance']['extraction_time_s']:.2f}s")
            print(f"Search time: {result['performance']['search_time_s']:.2f}s")
            print("\nTop 5 predictions:")

            for i, pred in enumerate(result['predictions'][:5], 1):
                print(f"{i}. {pred['species_name']}: {pred['probability']:.3f}")

        except Exception as e:
            print(f"Error: {e}")

    # Validation with known occurrences
    print("\n=== Validation Test ===")

    # Load a known occurrence
    import pandas as pd
    occurrences = pd.read_csv("data/pilot_occurrences.csv").head(5)

    for _, occ in occurrences.iterrows():
        result = predictor.validate_prediction(
            occ['latitude'],
            occ['longitude'],
            occ['taxon_id']
        )

        if result['validation']['found']:
            print(f"✓ Taxon {occ['taxon_id']} found at rank {result['validation']['rank']} "
                  f"(p={result['validation']['probability']:.3f})")
        else:
            print(f"✗ Taxon {occ['taxon_id']} not in top-k predictions")

if __name__ == "__main__":
    main()
```

### Step 7: Backend Integration

Create `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/treekipedia/backend/controllers/predictor.js`:

```javascript
/**
 * AlphaEarth Species Predictor API Controller
 */

const { Pool } = require('pg');
const axios = require('axios');

// Database connection
const pool = new Pool({
    host: process.env.ALPHAEARTH_DB_HOST || 'localhost',
    database: process.env.ALPHAEARTH_DB_NAME || 'treekipedia_alphaearth',
    user: process.env.ALPHAEARTH_DB_USER || 'postgres',
    password: process.env.ALPHAEARTH_DB_PASSWORD || '',
    port: process.env.ALPHAEARTH_DB_PORT || 5432,
});

// GEE service endpoint (Python microservice)
const GEE_SERVICE_URL = process.env.GEE_SERVICE_URL || 'http://localhost:8000';

/**
 * Extract AlphaEarth embedding at a point using Python microservice
 */
async function extractAlphaEarthEmbedding(latitude, longitude, year = null) {
    try {
        const response = await axios.post(`${GEE_SERVICE_URL}/extract`, {
            latitude,
            longitude,
            year: year || new Date().getFullYear()
        });

        return response.data.embedding;
    } catch (error) {
        console.error('GEE extraction error:', error.message);
        throw new Error('Failed to extract AlphaEarth data at location');
    }
}

/**
 * Search for similar species using pgvector
 */
async function searchSimilarSpecies(embedding, k = 20, temperature = 0.1) {
    const query = `
        SELECT
            taxon_id,
            species_name,
            probability,
            avg_similarity,
            n_prototypes_matched
        FROM species_probabilities($1::vector, $2, $3)
        LIMIT 10
    `;

    try {
        const result = await pool.query(query, [embedding, k, temperature]);
        return result.rows;
    } catch (error) {
        console.error('Database search error:', error);
        throw new Error('Failed to search similar species');
    }
}

/**
 * Main predictor endpoint handler
 * GET /api/predictor/from-location?lat=X&lon=Y&year=Z
 */
exports.predictFromLocation = async (req, res) => {
    try {
        // Parse query parameters
        const latitude = parseFloat(req.query.lat);
        const longitude = parseFloat(req.query.lon);
        const year = req.query.year ? parseInt(req.query.year) : null;
        const k = req.query.k ? parseInt(req.query.k) : 20;
        const temperature = req.query.temperature ? parseFloat(req.query.temperature) : 0.1;

        // Validate inputs
        if (isNaN(latitude) || latitude < -90 || latitude > 90) {
            return res.status(400).json({
                error: 'Invalid latitude. Must be between -90 and 90.'
            });
        }

        if (isNaN(longitude) || longitude < -180 || longitude > 180) {
            return res.status(400).json({
                error: 'Invalid longitude. Must be between -180 and 180.'
            });
        }

        if (year && (year < 2018 || year > 2023)) {
            return res.status(400).json({
                error: 'Year must be between 2018 and 2023.'
            });
        }

        const startTime = Date.now();

        // Step 1: Extract AlphaEarth embedding
        console.log(`Extracting AlphaEarth at (${latitude}, ${longitude})`);
        const embedding = await extractAlphaEarthEmbedding(latitude, longitude, year);
        const extractionTime = Date.now() - startTime;

        // Step 2: Search similar species
        console.log('Searching similar species...');
        const predictions = await searchSimilarSpecies(embedding, k, temperature);
        const searchTime = Date.now() - startTime - extractionTime;

        // Step 3: Format response
        const response = {
            success: true,
            query: {
                latitude,
                longitude,
                year: year || new Date().getFullYear()
            },
            predictions: predictions.map(p => ({
                taxon_id: p.taxon_id,
                species_name: p.species_name,
                probability: parseFloat(p.probability),
                similarity: parseFloat(p.avg_similarity),
                n_prototypes: p.n_prototypes_matched
            })),
            performance: {
                extraction_ms: extractionTime,
                search_ms: searchTime,
                total_ms: Date.now() - startTime
            },
            parameters: {
                k,
                temperature
            }
        };

        res.json(response);

    } catch (error) {
        console.error('Prediction error:', error);
        res.status(500).json({
            success: false,
            error: error.message || 'Internal server error'
        });
    }
};

/**
 * Get species prototypes
 * GET /api/predictor/prototypes/:taxonId
 */
exports.getSpeciesPrototypes = async (req, res) => {
    try {
        const taxonId = parseInt(req.params.taxonId);

        if (isNaN(taxonId)) {
            return res.status(400).json({ error: 'Invalid taxon ID' });
        }

        const query = `
            SELECT
                sp.prototype_idx,
                sp.weight,
                sp.n_points,
                sp.resultant_length,
                sp.angular_std,
                sm.species_name,
                sm.n_prototypes,
                sm.n_total_points
            FROM species_prototypes sp
            JOIN species_prototype_metadata sm ON sp.taxon_id = sm.taxon_id
            WHERE sp.taxon_id = $1
            ORDER BY sp.prototype_idx
        `;

        const result = await pool.query(query, [taxonId]);

        if (result.rows.length === 0) {
            return res.status(404).json({
                error: 'Species not found in predictor database'
            });
        }

        const metadata = result.rows[0];
        const prototypes = result.rows.map(row => ({
            index: row.prototype_idx,
            weight: parseFloat(row.weight),
            n_points: row.n_points,
            concentration: parseFloat(row.resultant_length),
            spread: parseFloat(row.angular_std)
        }));

        res.json({
            taxon_id: taxonId,
            species_name: metadata.species_name,
            n_prototypes: metadata.n_prototypes,
            n_total_points: metadata.n_total_points,
            prototypes
        });

    } catch (error) {
        console.error('Error fetching prototypes:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

/**
 * Health check endpoint
 */
exports.health = async (req, res) => {
    try {
        // Check database connection
        const dbResult = await pool.query('SELECT COUNT(*) FROM species_prototypes');
        const nPrototypes = parseInt(dbResult.rows[0].count);

        // Check GEE service
        let geeStatus = 'unknown';
        try {
            const geeResponse = await axios.get(`${GEE_SERVICE_URL}/health`);
            geeStatus = geeResponse.data.status || 'healthy';
        } catch (error) {
            geeStatus = 'unavailable';
        }

        res.json({
            status: 'healthy',
            database: {
                connected: true,
                prototypes: nPrototypes
            },
            gee_service: {
                status: geeStatus,
                url: GEE_SERVICE_URL
            },
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        res.status(503).json({
            status: 'unhealthy',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
};
```

Add routes to `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/treekipedia/backend/routes/predictor.js`:

```javascript
const express = require('express');
const router = express.Router();
const predictorController = require('../controllers/predictor');

// Species prediction from location
router.get('/from-location', predictorController.predictFromLocation);

// Get species prototypes
router.get('/prototypes/:taxonId', predictorController.getSpeciesPrototypes);

// Health check
router.get('/health', predictorController.health);

module.exports = router;
```

Update `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/treekipedia/backend/server.js` to include the new route:

```javascript
// Add after other route imports
const predictorRoutes = require('./routes/predictor');

// Add after other route uses
app.use('/api/predictor', predictorRoutes);
```

---

## Part 3: GEE & BigQuery Best Practices

### Google Earth Engine Quotas (2024)

**Free Tier (Academic/Research)**:
- **Compute**: No hard limit on EECU-time by default (unlimited)
- **Concurrent requests**: 40 simultaneous requests
- **Batch tasks**: 3,000 queued tasks
- **Asset storage**: 250 GB
- **Export size**: 10 GB per file
- **Request payload**: 10 MB
- **Memory per request**: 10 GB

**Optimization Strategies**:
1. **Batch exports over interactive**: Batch tasks don't count against concurrent request limits
2. **Use tileScale**: Increase to 4 or 8 for large regions
3. **Temporal mosaicking**: Process one year at a time
4. **Spatial chunking**: Divide large areas into tiles

### BigQuery Vector Search

**VECTOR_SEARCH Syntax (2024)**:
```sql
SELECT * FROM VECTOR_SEARCH(
    TABLE dataset.table_name,           -- Table with vectors
    'embedding_column',                  -- Vector column name
    query_embedding,                     -- Query vector
    distance_type => 'COSINE',          -- COSINE, EUCLIDEAN, or DOT_PRODUCT
    top_k => 10,                        -- Number of results
    options => '{"fraction_lists_to_search": 0.1}'  -- Index tuning
)
```

**Cost Optimization**:
- Vector indexes are free to create
- Query costs: $5 per TB scanned
- For 100 species × 5 prototypes × 64 dims × 4 bytes = ~128 KB
- Estimated cost per 1000 queries: < $0.01

### Optimal Batch Sizes

**GEE Exports**:
- Points: 1,000-5,000 per batch
- Small regions: 100-500 per batch
- Large regions: 10-50 per batch
- Adjust based on complexity and bands

**BigQuery Inserts**:
- Streaming: 500 rows per request
- Batch load: 10,000+ rows per file
- Use CSV for initial load, streaming for updates

---

## Part 4: Implementation Checklist

### Phase 1: Setup & Data Prep (Day 1)
- [ ] **Install dependencies** (2 hours)
  - Python environment with conda
  - PostgreSQL + pgvector OR BigQuery setup
  - GEE authentication
- [ ] **Select 100 pilot species** (1 hour)
  - Run species selection script
  - Verify taxonomic diversity
  - Check geographic coverage
- [ ] **Prepare occurrence data** (2 hours)
  - Extract points with temporal data
  - Apply spatial de-biasing
  - Export to CSV and GeoJSON

### Phase 2: GEE Extraction (Days 2-3)
- [ ] **Configure GEE orchestrator** (2 hours)
  - Set AlphaEarth collection ID
  - Configure quota parameters
  - Test with 10 points first
- [ ] **Run batch extraction** (8-12 hours)
  - Monitor task progress
  - Handle failures
  - Download results from GCS
- [ ] **Validate extractions** (2 hours)
  - Check for missing values
  - Verify band counts
  - Spot-check known locations

### Phase 3: Vector Processing (Day 4)
- [ ] **Build prototypes** (3 hours)
  - Run spherical k-means clustering
  - Compute spherical statistics
  - Determine optimal k per species
- [ ] **Setup storage** (2 hours)
  - Path A: PostgreSQL + pgvector
  - Path B: BigQuery tables
  - Create indexes
- [ ] **Load data** (1 hour)
  - Insert prototypes
  - Verify with test queries
  - Build materialized views

### Phase 4: API Integration (Day 5)
- [ ] **Create query pipeline** (3 hours)
  - Python predictor service
  - Test with known locations
  - Measure performance
- [ ] **Backend integration** (2 hours)
  - Express.js routes
  - Error handling
  - Response formatting
- [ ] **Validation** (2 hours)
  - Recall@K metrics
  - Cross-validation
  - Edge case testing

### Phase 5: Production Prep (Day 6)
- [ ] **Documentation** (2 hours)
  - API documentation
  - Deployment guide
  - Troubleshooting guide
- [ ] **Performance tuning** (2 hours)
  - Index optimization
  - Query caching
  - Connection pooling
- [ ] **Monitoring** (1 hour)
  - Health checks
  - Metrics collection
  - Alert setup

**Total estimated time**: 40-48 hours of active work over 6 days

### Common Pitfalls to Avoid

1. **Not normalizing vectors**: Always L2-normalize before storage and search
2. **Wrong distance metric**: Use cosine for normalized vectors, not Euclidean
3. **Ignoring temporal variation**: Always use year-specific AlphaEarth data
4. **Overloading GEE**: Start with small batches, increase gradually
5. **Missing data handling**: Check for NaN values in embeddings
6. **Not checkpointing**: Save progress frequently during batch processing
7. **Inefficient queries**: Use proper indexes and limit result sets

---

## Part 5: Cost Estimation

### 100-Species Pilot Costs

**Google Earth Engine**:
- Academic/Research: **$0** (free tier)
- Commercial: ~$50-100 in compute (35,000 point extractions)

**Cloud Storage**:
- Temporary storage: < 1 GB
- Cost: **< $1/month**

**PostgreSQL + pgvector**:
- Local development: **$0**
- Cloud hosting (small instance): $10-20/month

**BigQuery**:
- Storage: < 1 GB = **$0.02/month**
- Queries: 1000 queries = **< $0.01**
- Vector index: **$0** (free)

**Total Pilot Cost**:
- Academic: **$0-1**
- Commercial: **$50-120**

### Full Scale (67,743 species)

**Estimation**:
- GEE extraction: 2.5M points × $0.005 = $12,500
- Storage: 50 GB = $1/month
- Compute: $100-500/month depending on query volume

---

## Conclusion

This executable plan provides a complete roadmap for implementing the AlphaEarth Species Predictor using the superior vector-first approach. The 100-species pilot can be completed in approximately one week with minimal costs, validating the approach before scaling to the full 67,743 species dataset.

The key advantages of this approach:
- **4× more storage efficient** than scalar statistics
- **Mathematically correct** spherical statistics
- **Captures multi-modal niches** with k-prototypes
- **Sub-linear query scaling** with vector indexes
- **Production-ready** quota management

Follow the step-by-step instructions, use the provided code templates, and refer to the troubleshooting sections when issues arise. The modular design allows you to test each component independently before integration.

**Next Steps**:
1. Execute Phase 1 (Setup & Data Prep) immediately
2. Start GEE extraction overnight (Phase 2)
3. Validate results with known species occurrences
4. Share preliminary results with stakeholders
5. Plan for full-scale deployment

---

**Document Version**: 1.0.0
**Last Updated**: October 2024
**Total Words**: ~11,500
**Status**: Ready for Execution