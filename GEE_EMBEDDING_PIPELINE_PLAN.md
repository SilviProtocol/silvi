# Google Earth Engine AlphaEarth Embedding Integration Plan
## Treekipedia Species Predictor Product

**Date**: October 26, 2025
**Version**: 1.0
**Focus**: GEE embedding extraction pipeline + Species predictor application

---

## Executive Summary

This document outlines a complete plan to integrate Google Earth Engine's AlphaEarth embeddings into Treekipedia, creating species-level environmental signatures for all 67,743 species. The extracted embeddings will power a novel **Species Predictor** product that can:

1. **Predict species diversity** at any geographic location
2. **Match species to locations** based on environmental similarity
3. **Recommend suitable habitats** for specific species
4. **Identify similar species** by environmental niche

**Pipeline Overview**:
- Extract 64-band AlphaEarth embeddings for occurrence coordinates
- Aggregate to species-level statistics (mean, std, p10, p90 × 64 bands = 256 fields)
- Store in PostgreSQL for fast querying
- Build API endpoints for species prediction
- Create frontend visualizations

**Resource Requirements**:
- Local storage: <5GB
- Google Drive storage: ~1.5GB (within free quota)
- Processing time: 2-3 days for 48,129 species with occurrence data
- Cost: $0 (uses free tier)

---

## 1. Current Treekipedia State

### 1.1 Database Overview

**PostgreSQL 17 + PostGIS 3.6**:
- **67,743 total species** (50,797 species + 16,946 subspecies)
- **48,129 species with occurrence data** (71%)
- **19,614 species without occurrence data** (29%, mostly subspecies)

**Occurrence Data**:
- Source: Parquet file `Treekipedia_occ_Year_october24d.parquet`
- Columns: `taxon_id`, `latitude`, `longitude`, `year`, `source`
- Total occurrences: ~5.8 million (average ~120 per species)

**Geospatial Infrastructure**:
- 5,786,835 geohash tiles (Level 7, ~153m × 153m)
- PostGIS spatial indexes
- STAC-compliant temporal queries
- Ecoregion polygons (847)
- Intact forest polygons (6,819)

### 1.2 What We're Adding

**256 new fields per species**:
```
For each of 64 AlphaEarth bands (A01-A64):
  - {band}_mean: Average embedding value across all occurrences
  - {band}_std: Standard deviation (captures variability)
  - {band}_p10: 10th percentile (lower bound of typical range)
  - {band}_p90: 90th percentile (upper bound of typical range)

Total: 64 bands × 4 statistics = 256 new fields
```

**Example for Quercus robur (English Oak)**:
```json
{
  "taxon_id": 12345,
  "species_scientific_name": "Quercus robur",
  "A01_mean": 0.123,
  "A01_std": 0.015,
  "A01_p10": 0.108,
  "A01_p90": 0.138,
  "A02_mean": 0.456,
  "A02_std": 0.023,
  "A02_p10": 0.433,
  "A02_p90": 0.479,
  // ... (repeat for A03-A64)
  "A64_mean": 0.789,
  "A64_std": 0.031,
  "A64_p10": 0.758,
  "A64_p90": 0.820,
  "embedding_extraction_date": "2025-10-26T12:00:00Z",
  "embedding_occurrence_count": 1842,
  "embedding_year_range": "2017-2024"
}
```

---

## 2. Google Earth Engine AlphaEarth Embeddings

### 2.1 What Are AlphaEarth Embeddings?

**Dataset**: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`

AlphaEarth embeddings are 64-dimensional vectors derived from satellite imagery using deep learning. Each pixel (10m × 10m) has 64 numerical values that encode:
- Surface reflectance patterns
- Vegetation characteristics (NDVI-like features)
- Soil moisture indicators
- Land cover types
- Seasonal phenology
- Climate-vegetation interactions

Think of it as a "fingerprint" of the environment at that location.

**Key Specifications**:
- **Resolution**: 10 meters (10m × 10m pixels)
- **Temporal coverage**: 2017-2024 (annually updated)
- **Bands**: 64 (labeled A01-A64)
- **Projection**: EPSG:4326 (WGS84 lat/lng)
- **Global coverage**: Worldwide

**Why AlphaEarth?**
- **Pre-computed features**: No need to process raw satellite data
- **Temporal consistency**: Same features across years for trend analysis
- **Ecological relevance**: Captures environmental variables correlated with species distributions
- **Computational efficiency**: Much faster than deriving features from raw imagery

### 2.2 How It Works for Treekipedia

**Concept**: Each tree species occurs in certain environmental conditions. By extracting AlphaEarth embeddings at all known occurrence locations for a species, we can characterize its "environmental niche."

**Example**:
```
Quercus robur (English Oak):
  - 1,842 occurrence points across Europe
  - Extract AlphaEarth embedding (64 values) at each point
  - Aggregate: mean, std, p10, p90 for each of 64 bands
  - Result: 256-value "environmental signature"

This signature tells us:
  - Where Q. robur typically grows (mean)
  - How variable its habitat is (std)
  - The range of environments it tolerates (p10-p90)
```

**Use Case**:
```
New Location: [lng, lat]
  1. Extract AlphaEarth embedding at location (64 values)
  2. Compare to all species' signatures
  3. Find species with most similar embeddings
  4. Return: "This location is environmentally similar to places where
     Quercus robur, Fagus sylvatica, and Pinus sylvestris grow"
```

### 2.3 Temporal Matching Logic

AlphaEarth is available 2017-2024. For occurrences outside this range:

**Rules**:
1. **Occurrence ≤ 2017**: Use 2017 embedding (earliest available)
2. **2017 < Occurrence ≤ 2024**: Use occurrence year embedding (exact match)
3. **Occurrence > 2024**: Use 2024 embedding (latest available)

**Rationale**:
- Pre-2017 occurrences: Assume habitat hasn't changed drastically (reasonable for perennial trees)
- 2017-2024: Use exact year for temporal accuracy (captures seasonal/climate variations)
- Post-2024: Use latest available data as best proxy

**Example**:
```python
def get_embedding_year(occurrence_year):
    if occurrence_year <= 2017:
        return 2017
    elif occurrence_year > 2024:
        return 2024
    else:
        return occurrence_year

# Examples:
get_embedding_year(2010) → 2017  # Historical occurrence
get_embedding_year(2020) → 2020  # Exact match
get_embedding_year(2025) → 2024  # Recent occurrence
```

**Expected Distribution**:
- ~40% of occurrences: ≤2017 (use 2017)
- ~55% of occurrences: 2018-2024 (exact match)
- ~5% of occurrences: >2024 (use 2024)

---

## 3. Pipeline Architecture

### 3.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Database                                        │
│  - 67,743 species                                           │
│  - 5.8M occurrence records (lat, lng, year)                 │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Extract Occurrences                                │
│  - Group by species                                         │
│  - 48,129 species with occurrence data                      │
│  - Average ~120 occurrences per species                     │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────��────────────────┐
│  Step 2: GEE Batch Processing                               │
│  - Process 100 species per batch (482 batches total)        │
│  - For each occurrence: extract 64-band embedding           │
│  - Export to Google Drive as CSV                            │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Google Drive Storage                                       │
│  - Raw embeddings: taxon_id, lat, lng, year, A01-A64       │
│  - One CSV per batch (~10MB per 100 species)                │
│  - Total: ~1.5GB (within free quota)                        │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Local Aggregation                                  │
│  - Download batch CSVs                                      │
│  - Calculate mean, std, p10, p90 per species per band       │
│  - Generate 256 statistics per species                      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Database Update                                    │
│  - Add 256 new columns to species table                     │
│  - Insert aggregated statistics                             │
│  - 48,129 species × 256 fields = 12.3M new data points      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Species Predictor Product                                  │
│  - API endpoints for predictions                            │
│  - Frontend visualizations                                  │
│  - Ecological applications                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Python Implementation

**Complete Pipeline Class**:

```python
import ee
import psycopg2
import pandas as pd
import numpy as np
import os
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TreekipediaEmbeddingPipeline:
    """
    Extract Google Earth Engine AlphaEarth embeddings for Treekipedia species
    Generate 256 statistical fields per species (mean, std, p10, p90 × 64 bands)
    """

    def __init__(self, db_config, drive_folder='treekipedia_embeddings'):
        # Initialize Google Earth Engine
        ee.Initialize()
        logger.info("✓ Google Earth Engine initialized")

        # Database connection
        self.db_conn = psycopg2.connect(**db_config)
        logger.info("✓ PostgreSQL connected")

        # Configuration
        self.drive_folder = drive_folder
        self.species_batch_size = 100  # Species per GEE export task
        self.occurrence_batch_size = 5000  # Occurrences per reduceRegions call

        # AlphaEarth temporal range
        self.first_year = 2017
        self.last_year = 2024

        # Checkpoint system
        self.checkpoint_file = 'checkpoints/completed_species.txt'
        os.makedirs('checkpoints', exist_ok=True)

    def get_embedding_year(self, occurrence_year):
        """
        Map occurrence year to available AlphaEarth embedding year

        Rules:
        - occurrence_year <= 2017 → use 2017
        - 2017 < occurrence_year <= 2024 → use occurrence_year
        - occurrence_year > 2024 → use 2024
        """
        if occurrence_year <= self.first_year:
            return self.first_year
        elif occurrence_year > self.last_year:
            return self.last_year
        else:
            return occurrence_year

    def get_species_with_occurrences(self):
        """
        Get list of all species that have occurrence data
        Returns: List of taxon_ids
        """
        query = """
        SELECT DISTINCT s.taxon_id, s.species_scientific_name, COUNT(o.id) as occ_count
        FROM species s
        INNER JOIN occurrence_data o ON s.taxon_id = o.taxon_id
        GROUP BY s.taxon_id, s.species_scientific_name
        ORDER BY s.taxon_id
        """
        df = pd.read_sql(query, self.db_conn)
        logger.info(f"✓ Found {len(df)} species with occurrence data")
        return df

    def get_species_occurrences(self, taxon_id):
        """
        Fetch all occurrence points for a species

        Returns: DataFrame with columns [lat, lng, year]
        """
        query = """
        SELECT latitude as lat, longitude as lng, year
        FROM occurrence_data
        WHERE taxon_id = %s
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND year IS NOT NULL
        """
        df = pd.read_sql(query, self.db_conn, params=(taxon_id,))
        return df

    def export_embeddings_to_drive(self, species_chunk, batch_num):
        """
        Export AlphaEarth embeddings for a chunk of species to Google Drive

        Args:
            species_chunk: List of (taxon_id, species_name) tuples
            batch_num: Batch number for naming

        Returns:
            List of GEE Task objects
        """
        logger.info(f"Processing batch {batch_num}: {len(species_chunk)} species")

        # Collect all occurrences for this chunk
        all_occurrences = []
        for taxon_id, species_name in species_chunk:
            occurrences = self.get_species_occurrences(taxon_id)
            if len(occurrences) == 0:
                logger.warning(f"  Species {taxon_id} has no valid occurrences, skipping")
                continue

            occurrences['taxon_id'] = taxon_id
            all_occurrences.append(occurrences)

        if not all_occurrences:
            logger.warning(f"Batch {batch_num} has no valid occurrences, skipping")
            return []

        occurrences_df = pd.concat(all_occurrences, ignore_index=True)
        logger.info(f"  Total occurrences in batch: {len(occurrences_df)}")

        # Group by embedding year
        tasks = []
        for year in occurrences_df['year'].unique():
            embedding_year = self.get_embedding_year(int(year))
            year_occurrences = occurrences_df[occurrences_df['year'] == year]

            logger.info(f"  Exporting {len(year_occurrences)} occurrences from year {year} (using {embedding_year} embeddings)")

            # Create GEE feature collection
            features = []
            for _, row in year_occurrences.iterrows():
                point = ee.Geometry.Point([row['lng'], row['lat']])
                feature = ee.Feature(point, {
                    'taxon_id': int(row['taxon_id']),
                    'occ_year': int(row['year']),
                    'emb_year': int(embedding_year)
                })
                features.append(feature)

            fc = ee.FeatureCollection(features)

            # Load AlphaEarth embeddings for embedding_year
            embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
                .filterDate(f'{embedding_year}-01-01', f'{embedding_year}-12-31') \
                .first()

            # Sample embeddings at all points (efficient multi-point extraction)
            sampled = embeddings.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.first(),
                scale=10  # 10m resolution
            )

            # Export to Google Drive
            filename = f'batch{batch_num:03d}_year{embedding_year}'
            task = ee.batch.Export.table.toDrive(
                collection=sampled,
                description=filename,
                folder=self.drive_folder,
                fileFormat='CSV'
            )

            task.start()
            tasks.append(task)
            logger.info(f"    ✓ Export task started: {filename} (Task ID: {task.id})")

        return tasks

    def calculate_species_statistics(self, embeddings_df):
        """
        Calculate mean, std, p10, p90 for each of 64 bands

        Args:
            embeddings_df: DataFrame with columns [taxon_id, A01-A64]

        Returns:
            Dict with 256 fields per species:
            {
                taxon_id: {
                    'A01_mean': float, 'A01_std': float, 'A01_p10': float, 'A01_p90': float,
                    ...,
                    'A64_mean': float, 'A64_std': float, 'A64_p10': float, 'A64_p90': float,
                    'embedding_occurrence_count': int,
                    'embedding_year_range': str
                }
            }
        """
        results = {}

        for taxon_id, group in embeddings_df.groupby('taxon_id'):
            stats = {}

            for band in range(1, 65):
                band_name = f'A{band:02d}'

                if band_name in group.columns:
                    # Extract band values, filter out NaNs
                    values = group[band_name].dropna()

                    if len(values) > 0:
                        stats[f'{band_name}_mean'] = float(values.mean())
                        stats[f'{band_name}_std'] = float(values.std())
                        stats[f'{band_name}_p10'] = float(values.quantile(0.10))
                        stats[f'{band_name}_p90'] = float(values.quantile(0.90))
                    else:
                        # No valid data for this band
                        stats[f'{band_name}_mean'] = None
                        stats[f'{band_name}_std'] = None
                        stats[f'{band_name}_p10'] = None
                        stats[f'{band_name}_p90'] = None

            # Metadata
            stats['embedding_occurrence_count'] = len(group)
            year_range = f"{group['emb_year'].min()}-{group['emb_year'].max()}"
            stats['embedding_year_range'] = year_range
            stats['embedding_extraction_date'] = datetime.utcnow().isoformat()

            results[taxon_id] = stats

        return results

    def update_database_batch(self, species_stats):
        """
        Update species table with embedding statistics (batch update)

        Args:
            species_stats: Dict {taxon_id: {field: value, ...}}
        """
        cursor = self.db_conn.cursor()

        for taxon_id, stats in species_stats.items():
            # Build UPDATE query
            set_clause = ', '.join([f'{key} = %s' for key in stats.keys()])
            values = list(stats.values()) + [taxon_id]

            query = f"""
            UPDATE species
            SET {set_clause}
            WHERE taxon_id = %s
            """

            try:
                cursor.execute(query, values)
            except Exception as e:
                logger.error(f"Error updating species {taxon_id}: {e}")
                continue

        self.db_conn.commit()
        cursor.close()
        logger.info(f"✓ Updated {len(species_stats)} species in database")

    def load_completed_species(self):
        """Load set of already-completed species from checkpoint file"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                return set(int(line.strip()) for line in f if line.strip())
        return set()

    def mark_species_completed(self, taxon_id):
        """Mark species as completed in checkpoint file"""
        with open(self.checkpoint_file, 'a') as f:
            f.write(f"{taxon_id}\n")

    def wait_for_tasks(self, tasks, check_interval=60):
        """
        Wait for all GEE export tasks to complete

        Args:
            tasks: List of ee.Task objects
            check_interval: Seconds between status checks (default 60)
        """
        logger.info(f"Waiting for {len(tasks)} export tasks to complete...")

        while tasks:
            time.sleep(check_interval)

            remaining = []
            for task in tasks:
                status = task.status()
                state = status['state']

                if state == 'COMPLETED':
                    logger.info(f"  ✓ Task {status['description']} completed")
                elif state == 'FAILED':
                    logger.error(f"  ✗ Task {status['description']} failed: {status.get('error_message')}")
                else:
                    remaining.append(task)

            tasks = remaining

            if tasks:
                logger.info(f"  {len(tasks)} tasks still running...")

        logger.info("✓ All export tasks completed")

    def download_and_aggregate_batch(self, batch_num):
        """
        Download CSV files from Google Drive and aggregate statistics

        Note: This is a placeholder. In practice, you would:
        1. Use Google Drive API to download CSVs
        2. Or manually download from Drive folder
        3. Load CSVs into pandas DataFrames
        4. Call calculate_species_statistics()

        Args:
            batch_num: Batch number

        Returns:
            Dict of species statistics
        """
        # Placeholder: Assumes CSVs are in local folder 'downloads/batch{batch_num}/'
        batch_folder = f'downloads/batch{batch_num:03d}'

        if not os.path.exists(batch_folder):
            logger.error(f"Batch folder {batch_folder} not found. Download CSVs from Google Drive first.")
            return {}

        # Load all CSV files for this batch
        csv_files = [f for f in os.listdir(batch_folder) if f.endswith('.csv')]
        logger.info(f"Loading {len(csv_files)} CSV files from {batch_folder}")

        all_data = []
        for csv_file in csv_files:
            filepath = os.path.join(batch_folder, csv_file)
            df = pd.read_csv(filepath)
            all_data.append(df)

        # Combine all CSVs
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"  Total rows: {len(combined_df)}")

        # Calculate statistics
        species_stats = self.calculate_species_statistics(combined_df)
        logger.info(f"  Calculated statistics for {len(species_stats)} species")

        return species_stats

    def run_full_pipeline(self, start_batch=0, end_batch=None):
        """
        Run complete pipeline for all species

        Args:
            start_batch: Starting batch number (for resuming)
            end_batch: Ending batch number (None = all batches)
        """
        logger.info("=" * 60)
        logger.info("TREEKIPEDIA EMBEDDING EXTRACTION PIPELINE")
        logger.info("=" * 60)

        # Get all species with occurrences
        species_df = self.get_species_with_occurrences()
        total_species = len(species_df)

        # Filter out already-completed species
        completed = self.load_completed_species()
        species_df = species_df[~species_df['taxon_id'].isin(completed)]
        remaining_species = len(species_df)

        logger.info(f"Total species: {total_species}")
        logger.info(f"Already completed: {len(completed)}")
        logger.info(f"Remaining: {remaining_species}")

        if remaining_species == 0:
            logger.info("✓ All species already completed!")
            return

        # Split into batches
        total_batches = (remaining_species - 1) // self.species_batch_size + 1

        if end_batch is None:
            end_batch = total_batches

        logger.info(f"Processing batches {start_batch} to {end_batch} (of {total_batches} total)")

        for batch_num in range(start_batch, min(end_batch, total_batches)):
            start_idx = batch_num * self.species_batch_size
            end_idx = min(start_idx + self.species_batch_size, remaining_species)

            batch_species = species_df.iloc[start_idx:end_idx]
            species_chunk = [(row['taxon_id'], row['species_scientific_name']) for _, row in batch_species.iterrows()]

            logger.info(f"\n{'=' * 60}")
            logger.info(f"BATCH {batch_num + 1}/{total_batches}")
            logger.info(f"Species {start_idx + 1}-{end_idx} of {remaining_species}")
            logger.info(f"{'=' * 60}")

            # Step 1: Export to Google Drive
            tasks = self.export_embeddings_to_drive(species_chunk, batch_num)

            if not tasks:
                logger.warning(f"Batch {batch_num} produced no export tasks, skipping")
                continue

            # Step 2: Wait for exports to complete
            self.wait_for_tasks(tasks)

            # Step 3: Download and aggregate
            logger.info(f"\nDownload CSVs from Google Drive folder '{self.drive_folder}/batch{batch_num:03d}*'")
            logger.info(f"Then save them to 'downloads/batch{batch_num:03d}/' and press Enter to continue...")
            input()  # Manual step: download from Drive

            species_stats = self.download_and_aggregate_batch(batch_num)

            if not species_stats:
                logger.warning(f"Batch {batch_num} aggregation failed, skipping database update")
                continue

            # Step 4: Update database
            self.update_database_batch(species_stats)

            # Step 5: Mark species as completed
            for taxon_id in species_stats.keys():
                self.mark_species_completed(taxon_id)

            logger.info(f"✓ Batch {batch_num + 1} completed ({len(species_stats)} species)")

        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE!")
        logger.info("=" * 60)

# ============================================================================
# Usage Example
# ============================================================================

if __name__ == '__main__':
    # Database configuration
    db_config = {
        'host': 'localhost',
        'database': 'treekipedia',
        'user': 'postgres',
        'password': 'your_password',
        'port': 5432
    }

    # Initialize pipeline
    pipeline = TreekipediaEmbeddingPipeline(db_config)

    # Run full pipeline (or resume from batch X)
    pipeline.run_full_pipeline(start_batch=0)
```

### 3.3 Database Schema Changes

**Add 256 embedding columns** to `species` table:

```sql
-- File: database/migrations/add_embedding_fields.sql

BEGIN;

-- Generate all 256 columns programmatically
DO $$
DECLARE
    band_num INTEGER;
    stat_type TEXT;
BEGIN
    FOR band_num IN 1..64 LOOP
        FOR stat_type IN SELECT unnest(ARRAY['mean', 'std', 'p10', 'p90']) LOOP
            EXECUTE format(
                'ALTER TABLE species ADD COLUMN IF NOT EXISTS A%s_%s NUMERIC(10, 6)',
                lpad(band_num::text, 2, '0'),
                stat_type
            );
        END LOOP;
    END LOOP;
END $$;

-- Add metadata columns
ALTER TABLE species
  ADD COLUMN IF NOT EXISTS embedding_extraction_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS embedding_occurrence_count INTEGER,
  ADD COLUMN IF NOT EXISTS embedding_year_range VARCHAR(20);

-- Create partial index (only species with embeddings)
CREATE INDEX IF NOT EXISTS idx_species_embeddings_complete
ON species(taxon_id)
WHERE A01_mean IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN species.A01_mean IS 'AlphaEarth embedding band A01 mean value across all occurrences';
COMMENT ON COLUMN species.A01_std IS 'AlphaEarth embedding band A01 standard deviation';
COMMENT ON COLUMN species.A01_p10 IS 'AlphaEarth embedding band A01 10th percentile';
COMMENT ON COLUMN species.A01_p90 IS 'AlphaEarth embedding band A01 90th percentile';

COMMIT;
```

**Verify migration**:
```sql
-- Check that all columns were added
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'species'
  AND column_name LIKE 'A%';
-- Should return 256 rows

-- Check extraction progress
SELECT
  COUNT(*) FILTER (WHERE A01_mean IS NOT NULL) as species_with_embeddings,
  COUNT(*) FILTER (WHERE A01_mean IS NULL) as species_without_embeddings,
  COUNT(*) as total_species
FROM species;
```

### 3.4 Google Drive Storage Organization

**Folder Structure**:
```
Google Drive/
└── treekipedia_embeddings/
    ├── batch000_year2017.csv
    ├── batch000_year2018.csv
    ├── batch000_year2019.csv
    ├── ... (one file per year per batch)
    ├── batch000_year2024.csv
    ├── batch001_year2017.csv
    ├── batch001_year2018.csv
    ├── ...
    ├── batch481_year2024.csv
    └── README.txt (extraction metadata)
```

**CSV Format** (Exported from GEE):
```csv
.geo,taxon_id,occ_year,emb_year,A01,A02,A03,...,A64
"{""type"":""Point"",""coordinates"":[-122.08,37.42]}",12345,2020,2020,0.123,0.456,0.789,...,0.321
"{""type"":""Point"",""coordinates"":[-122.09,37.43]}",12345,2019,2019,0.124,0.455,0.788,...,0.322
"{""type"":""Point"",""coordinates"":[-122.10,37.44]}",12346,2021,2021,0.125,0.454,0.787,...,0.323
```

**Storage Estimates**:
- Each batch: ~10MB compressed CSV
- Total batches: 482 (100 species each)
- Total size: ~1.5GB (well within 15GB free quota)

---

## 4. Species Predictor Product

### 4.1 Product Vision

**Core Value Proposition**: Predict which tree species are likely to grow at any location on Earth based on environmental similarity to known occurrences.

**Target Users**:
1. **Ecologists**: Rapid biodiversity assessment, species distribution modeling
2. **Foresters**: Reforestation planning, species selection for plantations
3. **Conservationists**: Habitat suitability analysis, climate change impact prediction
4. **Researchers**: Ecological niche analysis, functional trait prediction
5. **Citizen Scientists**: Identify trees, learn about local biodiversity

**Key Features**:
1. **Species Diversity Predictor**: "What species might grow here?"
2. **Habitat Suitability Analyzer**: "Is this location suitable for Quercus robur?"
3. **Similar Species Finder**: "Which species are ecologically similar to this one?"
4. **Environmental Niche Explorer**: "Show me the environmental signature of this species"

### 4.2 Backend API Endpoints

**New Endpoints** (to be added to `treekipedia/backend/`):

```javascript
// File: routes/predictor.js

const express = require('express');
const router = express.Router();
const predictorController = require('../controllers/predictor');

// ============================================================================
// Embedding Data Endpoints
// ============================================================================

/**
 * GET /api/predictor/embeddings/:taxon_id
 * Get 256 embedding statistics for a species
 *
 * Response: {
 *   taxon_id: 12345,
 *   species_scientific_name: "Quercus robur",
 *   A01_mean: 0.123, A01_std: 0.015, A01_p10: 0.108, A01_p90: 0.138,
 *   ... (256 fields total),
 *   metadata: {
 *     extraction_date: "2025-10-26T12:00:00Z",
 *     occurrence_count: 1842,
 *     year_range: "2017-2024"
 *   }
 * }
 */
router.get('/embeddings/:taxon_id', predictorController.getSpeciesEmbeddings);

// ============================================================================
// Similarity Search Endpoints
// ============================================================================

/**
 * GET /api/predictor/similar/:taxon_id?limit=10&threshold=0.5
 * Find species with similar environmental signatures
 *
 * Query params:
 *   - limit: Number of results (default 10, max 100)
 *   - threshold: Maximum embedding distance (default 0.5)
 *
 * Response: [
 *   {
 *     taxon_id: 67890,
 *     species_scientific_name: "Quercus petraea",
 *     embedding_distance: 0.12,
 *     similarity_score: 0.88,
 *     family: "Fagaceae"
 *   },
 *   ...
 * ]
 */
router.get('/similar/:taxon_id', predictorController.findSimilarSpecies);

// ============================================================================
// Prediction Endpoints
// ============================================================================

/**
 * POST /api/predictor/predict-diversity
 * Predict species diversity at a geographic location
 *
 * Body: {
 *   coordinates: [lng, lat],
 *   year: 2024,  // optional, default current year
 *   limit: 50,   // optional, default 50
 *   threshold: 0.5  // optional, max embedding distance
 * }
 *
 * Response: {
 *   location: [lng, lat],
 *   location_embedding: { A01: 0.123, A02: 0.456, ... },
 *   predicted_species: [
 *     {
 *       taxon_id: 12345,
 *       species_scientific_name: "Quercus robur",
 *       probability: 0.82,
 *       embedding_distance: 0.15,
 *       family: "Fagaceae"
 *     },
 *     ...
 *   ]
 * }
 */
router.post('/predict-diversity', predictorController.predictDiversity);

/**
 * POST /api/predictor/habitat-suitability
 * Predict habitat suitability for a species at candidate locations
 *
 * Body: {
 *   taxon_id: 12345,
 *   locations: [[lng, lat], [lng, lat], ...],
 *   year: 2024  // optional, default current year
 * }
 *
 * Response: {
 *   taxon_id: 12345,
 *   species_scientific_name: "Quercus robur",
 *   species_embedding: { A01_mean: 0.123, A01_std: 0.015, ... },
 *   location_suitability: [
 *     {
 *       location: [lng, lat],
 *       suitability_score: 0.71,  // 0-1, higher = more suitable
 *       embedding_distance: 0.23,
 *       interpretation: "High suitability"
 *     },
 *     ...
 *   ]
 * }
 */
router.post('/habitat-suitability', predictorController.assessHabitatSuitability);

module.exports = router;
```

**Controller Implementation** (key functions):

```javascript
// File: controllers/predictor.js

const db = require('../models/database');
const axios = require('axios');

// GEE extraction service (Python microservice on port 5003)
const GEE_SERVICE_URL = process.env.GEE_SERVICE_URL || 'http://localhost:5003';

/**
 * Calculate Euclidean distance between two embeddings
 */
function calculateEmbeddingDistance(embedding1, embedding2) {
  let sumSquaredDiffs = 0;

  for (let band = 1; band <= 64; band++) {
    const bandName = `A${band.toString().padStart(2, '0')}`;
    const mean1 = embedding1[`${bandName}_mean`];
    const mean2 = embedding2[`${bandName}_mean`];

    if (mean1 !== null && mean2 !== null) {
      sumSquaredDiffs += Math.pow(mean1 - mean2, 2);
    }
  }

  return Math.sqrt(sumSquaredDiffs);
}

/**
 * Convert embedding distance to similarity score (0-1)
 */
function distanceToSimilarity(distance) {
  // Inverse exponential: similarity = e^(-distance)
  return Math.exp(-distance);
}

/**
 * GET /api/predictor/embeddings/:taxon_id
 */
exports.getSpeciesEmbeddings = async (req, res) => {
  try {
    const { taxon_id } = req.params;

    // Fetch all 256 embedding fields + metadata
    const query = `
      SELECT
        taxon_id,
        species_scientific_name,
        family,
        ${generateEmbeddingSelectClause()},
        embedding_extraction_date,
        embedding_occurrence_count,
        embedding_year_range
      FROM species
      WHERE taxon_id = $1
        AND A01_mean IS NOT NULL
    `;

    const result = await db.query(query, [taxon_id]);

    if (result.rows.length === 0) {
      return res.status(404).json({
        error: 'Species not found or no embedding data available'
      });
    }

    res.json(result.rows[0]);

  } catch (error) {
    console.error('Error fetching embeddings:', error);
    res.status(500).json({ error: 'Failed to fetch embeddings' });
  }
};

/**
 * GET /api/predictor/similar/:taxon_id
 */
exports.findSimilarSpecies = async (req, res) => {
  try {
    const { taxon_id } = req.params;
    const limit = Math.min(parseInt(req.query.limit) || 10, 100);
    const threshold = parseFloat(req.query.threshold) || 0.5;

    // Get target species embedding
    const targetQuery = `
      SELECT ${generateEmbeddingSelectClause()}
      FROM species
      WHERE taxon_id = $1 AND A01_mean IS NOT NULL
    `;
    const targetResult = await db.query(targetQuery, [taxon_id]);

    if (targetResult.rows.length === 0) {
      return res.status(404).json({ error: 'Species not found or no embedding data' });
    }

    const targetEmbedding = targetResult.rows[0];

    // Calculate distance to all other species
    // Note: For large datasets, consider pre-computing distances or using approximate nearest neighbor
    const similarityQuery = `
      WITH target AS (
        SELECT ${generateEmbeddingSelectClause()}
        FROM species
        WHERE taxon_id = $1
      )
      SELECT
        s.taxon_id,
        s.species_scientific_name,
        s.family,
        ${generateEmbeddingDistanceClause('s', 'target')} as embedding_distance
      FROM species s, target
      WHERE s.A01_mean IS NOT NULL
        AND s.taxon_id != $1
      ORDER BY embedding_distance ASC
      LIMIT $2
    `;

    const result = await db.query(similarityQuery, [taxon_id, limit]);

    // Add similarity scores
    const withScores = result.rows.map(row => ({
      ...row,
      similarity_score: distanceToSimilarity(row.embedding_distance)
    }));

    // Filter by threshold
    const filtered = withScores.filter(row => row.embedding_distance <= threshold);

    res.json(filtered);

  } catch (error) {
    console.error('Error finding similar species:', error);
    res.status(500).json({ error: 'Failed to find similar species' });
  }
};

/**
 * POST /api/predictor/predict-diversity
 */
exports.predictDiversity = async (req, res) => {
  try {
    const { coordinates, year, limit, threshold } = req.body;

    if (!coordinates || coordinates.length !== 2) {
      return res.status(400).json({ error: 'Invalid coordinates [lng, lat]' });
    }

    const [lng, lat] = coordinates;
    const extractionYear = year || new Date().getFullYear();
    const maxResults = Math.min(limit || 50, 100);
    const maxDistance = threshold || 0.5;

    // Step 1: Extract embedding at location (call GEE microservice)
    const geeResponse = await axios.post(`${GEE_SERVICE_URL}/extract`, {
      coordinates: [lng, lat],
      year: extractionYear
    });

    const locationEmbedding = geeResponse.data.embedding;

    // Step 2: Compare to all species embeddings
    const predictionQuery = `
      SELECT
        taxon_id,
        species_scientific_name,
        family,
        ${calculateDistanceToLocation(locationEmbedding)} as embedding_distance
      FROM species
      WHERE A01_mean IS NOT NULL
      ORDER BY embedding_distance ASC
      LIMIT $1
    `;

    const result = await db.query(predictionQuery, [maxResults]);

    // Step 3: Convert distances to probabilities
    const predictions = result.rows
      .filter(row => row.embedding_distance <= maxDistance)
      .map(row => ({
        ...row,
        probability: distanceToSimilarity(row.embedding_distance)
      }));

    res.json({
      location: coordinates,
      location_embedding: locationEmbedding,
      predicted_species: predictions
    });

  } catch (error) {
    console.error('Error predicting diversity:', error);
    res.status(500).json({ error: 'Failed to predict diversity' });
  }
};

/**
 * POST /api/predictor/habitat-suitability
 */
exports.assessHabitatSuitability = async (req, res) => {
  try {
    const { taxon_id, locations, year } = req.body;

    if (!taxon_id || !locations || !Array.isArray(locations)) {
      return res.status(400).json({ error: 'Invalid request: taxon_id and locations required' });
    }

    const extractionYear = year || new Date().getFullYear();

    // Step 1: Get species embedding
    const speciesQuery = `
      SELECT
        species_scientific_name,
        family,
        ${generateEmbeddingSelectClause()}
      FROM species
      WHERE taxon_id = $1 AND A01_mean IS NOT NULL
    `;

    const speciesResult = await db.query(speciesQuery, [taxon_id]);

    if (speciesResult.rows.length === 0) {
      return res.status(404).json({ error: 'Species not found or no embedding data' });
    }

    const speciesData = speciesResult.rows[0];

    // Step 2: Extract embeddings at all candidate locations
    const locationEmbeddings = await Promise.all(
      locations.map(coords =>
        axios.post(`${GEE_SERVICE_URL}/extract`, {
          coordinates: coords,
          year: extractionYear
        }).then(response => ({
          location: coords,
          embedding: response.data.embedding
        }))
      )
    );

    // Step 3: Calculate suitability scores
    const suitability = locationEmbeddings.map(({ location, embedding }) => {
      const distance = calculateEmbeddingDistance(speciesData, embedding);
      const score = distanceToSimilarity(distance);

      let interpretation;
      if (score >= 0.8) interpretation = 'Very High Suitability';
      else if (score >= 0.6) interpretation = 'High Suitability';
      else if (score >= 0.4) interpretation = 'Moderate Suitability';
      else if (score >= 0.2) interpretation = 'Low Suitability';
      else interpretation = 'Very Low Suitability';

      return {
        location,
        suitability_score: score,
        embedding_distance: distance,
        interpretation
      };
    });

    res.json({
      taxon_id,
      species_scientific_name: speciesData.species_scientific_name,
      family: speciesData.family,
      location_suitability: suitability
    });

  } catch (error) {
    console.error('Error assessing habitat suitability:', error);
    res.status(500).json({ error: 'Failed to assess habitat suitability' });
  }
};

// ============================================================================
// Helper Functions
// ============================================================================

function generateEmbeddingSelectClause() {
  // Generate: A01_mean, A01_std, A01_p10, A01_p90, A02_mean, ...
  const fields = [];
  for (let band = 1; band <= 64; band++) {
    const bandName = `A${band.toString().padStart(2, '0')}`;
    fields.push(`${bandName}_mean`, `${bandName}_std`, `${bandName}_p10`, `${bandName}_p90`);
  }
  return fields.join(', ');
}

function generateEmbeddingDistanceClause(alias1, alias2) {
  // Generate SQL for Euclidean distance calculation
  const terms = [];
  for (let band = 1; band <= 64; band++) {
    const bandName = `A${band.toString().padStart(2, '0')}`;
    terms.push(`POWER(${alias1}.${bandName}_mean - ${alias2}.${bandName}_mean, 2)`);
  }
  return `SQRT(${terms.join(' + ')})`;
}

function calculateDistanceToLocation(locationEmbedding) {
  // Generate SQL for distance to extracted location embedding
  const terms = [];
  for (let band = 1; band <= 64; band++) {
    const bandName = `A${band.toString().padStart(2, '0')}`;
    const value = locationEmbedding[bandName] || 0;
    terms.push(`POWER(${bandName}_mean - ${value}, 2)`);
  }
  return `SQRT(${terms.join(' + ')})`;
}
```

### 4.3 GEE Extraction Microservice

**New Python microservice** for real-time AlphaEarth extraction:

```python
# File: treekipedia/gee-microservice/server.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=['http://localhost:5001', 'http://localhost:3000'])

# Initialize Google Earth Engine
ee.Initialize()
logger.info("✓ Google Earth Engine initialized")

def get_embedding_year(year):
    """Map requested year to available AlphaEarth year (2017-2024)"""
    if year <= 2017:
        return 2017
    elif year > 2024:
        return 2024
    else:
        return year

@app.route('/extract', methods=['POST'])
def extract_embedding():
    """
    Extract AlphaEarth embedding at a single point

    Body: {
        "coordinates": [lng, lat],
        "year": 2024  // optional
    }

    Response: {
        "embedding": { "A01": 0.123, "A02": 0.456, ..., "A64": 0.789 },
        "year": 2024,
        "location": [lng, lat]
    }
    """
    try:
        data = request.get_json()

        if 'coordinates' not in data:
            return jsonify({'error': 'coordinates required'}), 400

        lng, lat = data['coordinates']
        year = data.get('year', 2024)
        embedding_year = get_embedding_year(year)

        # Create point geometry
        point = ee.Geometry.Point([lng, lat])

        # Load AlphaEarth embeddings for year
        embeddings = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL') \
            .filterDate(f'{embedding_year}-01-01', f'{embedding_year}-12-31') \
            .filterBounds(point) \
            .first()

        # Extract 64-band values at point
        sample = embeddings.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=10  # 10m resolution
        )

        embedding_dict = sample.getInfo()

        return jsonify({
            'embedding': embedding_dict,
            'year': embedding_year,
            'location': [lng, lat]
        })

    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'gee-extraction-microservice'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### 4.4 Frontend Visualization

**Species Detail Page - New "Environmental Signature" Tab**:

```tsx
// File: treekipedia/frontend/app/species/[taxon_id]/tabs/EnvironmentalSignatureTab.tsx

'use client';

import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Loader2 } from 'lucide-react';

interface EmbeddingData {
  taxon_id: number;
  species_scientific_name: string;
  [key: string]: any; // A01_mean, A01_std, etc.
}

interface SimilarSpecies {
  taxon_id: number;
  species_scientific_name: string;
  embedding_distance: number;
  similarity_score: number;
  family: string;
}

export default function EnvironmentalSignatureTab({ taxon_id }: { taxon_id: number }) {
  const [embeddings, setEmbeddings] = useState<EmbeddingData | null>(null);
  const [similarSpecies, setSimilarSpecies] = useState<SimilarSpecies[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [taxon_id]);

  const fetchData = async () => {
    try {
      // Fetch embeddings
      const embRes = await fetch(`/api/predictor/embeddings/${taxon_id}`);
      const embData = await embRes.json();
      setEmbeddings(embData);

      // Fetch similar species
      const simRes = await fetch(`/api/predictor/similar/${taxon_id}?limit=10`);
      const simData = await simRes.json();
      setSimilarSpecies(simData);

      setLoading(false);
    } catch (error) {
      console.error('Error fetching embedding data:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  if (!embeddings) {
    return (
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-6">
        <p className="text-yellow-400">
          Environmental signature data not available for this species.
          This usually means no occurrence data exists.
        </p>
      </div>
    );
  }

  // Prepare data for chart (first 10 bands as example)
  const chartData = Array.from({ length: 10 }, (_, i) => {
    const band = `A${(i + 1).toString().padStart(2, '0')}`;
    return {
      band,
      mean: embeddings[`${band}_mean`],
      std: embeddings[`${band}_std`],
      p10: embeddings[`${band}_p10`],
      p90: embeddings[`${band}_p90`],
    };
  });

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
        <h3 className="text-xl font-semibold text-emerald-300 mb-4">
          Environmental Signature Overview
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-400">Occurrences Analyzed</p>
            <p className="text-2xl font-bold text-white">{embeddings.embedding_occurrence_count?.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400">Year Range</p>
            <p className="text-2xl font-bold text-white">{embeddings.embedding_year_range}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400">Extraction Date</p>
            <p className="text-lg font-semibold text-white">
              {new Date(embeddings.embedding_extraction_date).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>

      {/* Embedding Visualization */}
      <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
        <h3 className="text-xl font-semibold text-emerald-300 mb-4">
          AlphaEarth Embedding Values (First 10 Bands)
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Mean values with 10th-90th percentile range (error bars represent variability across habitats)
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <XAxis dataKey="band" stroke="#6ee7b7" />
            <YAxis stroke="#6ee7b7" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                border: '1px solid rgba(110, 231, 183, 0.3)',
                borderRadius: '8px',
              }}
            />
            <Bar dataKey="mean" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Similar Species */}
      <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
        <h3 className="text-xl font-semibold text-emerald-300 mb-4">
          Ecologically Similar Species
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Species with similar environmental signatures (based on embedding distance)
        </p>
        <div className="space-y-3">
          {similarSpecies.map((species, idx) => (
            <div
              key={species.taxon_id}
              className="flex items-center justify-between bg-black/40 border border-white/10 rounded-lg p-4 hover:border-emerald-500/30 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="text-2xl font-bold text-emerald-400">
                  #{idx + 1}
                </div>
                <div>
                  <p className="font-semibold text-white italic">
                    {species.species_scientific_name}
                  </p>
                  <p className="text-sm text-gray-400">{species.family}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">Similarity</p>
                <p className="text-lg font-semibold text-emerald-400">
                  {(species.similarity_score * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-gray-500">
                  Distance: {species.embedding_distance.toFixed(3)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* What This Means */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
        <h4 className="text-lg font-semibold text-blue-400 mb-2">
          What is an Environmental Signature?
        </h4>
        <p className="text-sm text-gray-300 leading-relaxed">
          This species' environmental signature is derived from satellite imagery (Google Earth Engine AlphaEarth)
          at all {embeddings.embedding_occurrence_count.toLocaleString()} known occurrence locations.
          The 64 embedding bands capture surface reflectance, vegetation patterns, soil moisture, and other
          environmental characteristics. Species with similar signatures typically occupy similar ecological niches.
        </p>
      </div>
    </div>
  );
}
```

**Interactive Species Predictor Page**:

```tsx
// File: treekipedia/frontend/app/predictor/page.tsx

'use client';

import { useState } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import { Search, MapPin, Loader2 } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

interface PredictedSpecies {
  taxon_id: number;
  species_scientific_name: string;
  probability: number;
  embedding_distance: number;
  family: string;
}

export default function SpeciesPredictorPage() {
  const [location, setLocation] = useState<[number, number] | null>(null);
  const [predictions, setPredictions] = useState<PredictedSpecies[]>([]);
  const [loading, setLoading] = useState(false);

  const handleMapClick = async (lat: number, lng: number) => {
    setLocation([lng, lat]);
    setLoading(true);

    try {
      const response = await fetch('/api/predictor/predict-diversity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coordinates: [lng, lat],
          year: 2024,
          limit: 50,
          threshold: 0.6
        })
      });

      const data = await response.json();
      setPredictions(data.predicted_species);
    } catch (error) {
      console.error('Prediction error:', error);
    } finally {
      setLoading(false);
    }
  };

  function MapClickHandler() {
    useMapEvents({
      click: (e) => {
        handleMapClick(e.latlng.lat, e.latlng.lng);
      },
    });
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900 p-8">
      <div className="container mx-auto max-w-7xl">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-emerald-300 mb-2">
            <Search className="inline-block w-10 h-10 mr-3" />
            Species Predictor
          </h1>
          <p className="text-gray-400 text-lg">
            Click any location on the map to predict which tree species might grow there
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Map */}
          <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-4 h-[600px]">
            <MapContainer
              center={[40, -100]}
              zoom={4}
              style={{ height: '100%', borderRadius: '8px' }}
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; OpenStreetMap contributors'
              />
              <MapClickHandler />
              {location && (
                <Marker position={[location[1], location[0]]} />
              )}
            </MapContainer>
          </div>

          {/* Results */}
          <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 h-[600px] overflow-y-auto">
            {!location && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <MapPin className="w-16 h-16 text-emerald-400 mb-4" />
                <p className="text-gray-400 text-lg">
                  Click anywhere on the map to predict species diversity
                </p>
              </div>
            )}

            {loading && (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-12 h-12 animate-spin text-emerald-500" />
              </div>
            )}

            {location && !loading && predictions.length > 0 && (
              <div>
                <div className="mb-4">
                  <h3 className="text-xl font-semibold text-emerald-300">
                    Predicted Species at Location
                  </h3>
                  <p className="text-sm text-gray-400">
                    Lat: {location[1].toFixed(4)}, Lng: {location[0].toFixed(4)}
                  </p>
                </div>

                <div className="space-y-3">
                  {predictions.map((species, idx) => (
                    <div
                      key={species.taxon_id}
                      className="bg-black/40 border border-white/10 rounded-lg p-4 hover:border-emerald-500/30 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className="text-lg font-bold text-emerald-400">
                            {idx + 1}
                          </div>
                          <div>
                            <p className="font-semibold text-white italic">
                              {species.species_scientific_name}
                            </p>
                            <p className="text-xs text-gray-400">{species.family}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-emerald-400">
                            {(species.probability * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-gray-500">
                            confidence
                          </div>
                        </div>
                      </div>

                      {/* Probability bar */}
                      <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
                        <div
                          className="bg-emerald-500 h-2 rounded-full transition-all"
                          style={{ width: `${species.probability * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* How It Works */}
        <div className="mt-8 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="text-xl font-semibold text-blue-400 mb-3">
            How Does This Work?
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-300">
            <div>
              <p className="font-semibold text-white mb-1">1. Extract Environment</p>
              <p>We extract the environmental "fingerprint" at your clicked location using satellite imagery (AlphaEarth embeddings).</p>
            </div>
            <div>
              <p className="font-semibold text-white mb-1">2. Compare to Species</p>
              <p>We compare this fingerprint to the environmental signatures of all 48,000+ tree species in our database.</p>
            </div>
            <div>
              <p className="font-semibold text-white mb-1">3. Rank by Similarity</p>
              <p>Species with the most similar environmental signatures are most likely to grow in that location.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 4.5 Use Cases & Applications

**1. Reforestation Planning**:
```
User: "I want to reforest this degraded area in Brazil"
Action: Click location on map
System: Predicts 50 suitable native species
User: Filters by "native to Brazil" + "fast-growing"
Result: Gets list of 10 ideal species for reforestation project
```

**2. Rapid Biodiversity Assessment**:
```
Researcher: "I'm surveying this remote forest plot"
Action: Clicks plot center on map
System: Returns 50 most likely species
Researcher: Uses list as field guide to prioritize surveys
Result: 70% of species found were in top 20 predictions (time saved)
```

**3. Species Distribution Modeling**:
```
Ecologist: "How will climate change affect Quercus robur?"
Action: Views Q. robur environmental signature
System: Shows current embedding values
Ecologist: Compares to future climate projections
Result: Identifies suitable future habitats for conservation planning
```

**4. Habitat Suitability for Restoration**:
```
Forester: "Should I plant Sequoia sempervirens here?"
Action: Selects S. sempervirens, inputs candidate locations
System: Computes suitability scores
Result: "Location A: 91% suitable, Location B: 34% suitable"
Decision: Plant at Location A
```

**5. Ecological Research**:
```
Question: "Which species are functional equivalents?"
Method: Query similar species by embedding distance
Result: Cluster species by environmental niche
Application: Understand functional diversity, ecosystem resilience
```

---

## 5. Performance & Resource Requirements

### 5.1 Processing Time Estimates

**Full Pipeline** (48,129 species):

| Stage | Time per Batch (100 species) | Total Batches | Total Time |
|-------|------------------------------|---------------|------------|
| GEE Extraction | 5-10 min | 482 | 40-80 hours |
| Google Drive Export | 2-3 min | 482 | 16-24 hours |
| Download from Drive | 1 min | 482 | 8 hours |
| Aggregation | 30 sec | 482 | 4 hours |
| Database Update | 30 sec | 482 | 4 hours |
| **Total** | **~12 min** | **482** | **~96 hours (4 days)** |

**With Parallelization** (3 concurrent batches):
- Time: 96 hours / 3 = **32 hours (1.3 days)**

**Conservative Estimate**: **2-3 days** for full extraction

**Query Performance** (after extraction):

| Query Type | Response Time | Scalability |
|------------|---------------|-------------|
| Get species embeddings | <50ms | Constant (indexed) |
| Find similar species | 100-500ms | Linear (can optimize) |
| Predict diversity | 500-2000ms | Depends on GEE (can cache) |
| Habitat suitability | 500ms × locations | Parallelizable |

### 5.2 Storage Requirements

**Local Storage**:
- Python scripts: ~500KB
- Checkpoint files: ~2MB
- Temporary downloads: ~50MB per batch (deleted after processing)
- **Total**: <5GB

**Google Drive Storage**:
- Raw CSVs: 482 batches × ~10MB = ~4.8GB
- After compression: ~1.5GB
- Well within 15GB free quota

**Database Storage**:
- New columns: 256 fields × 8 bytes × 67,743 species = 138MB
- Minimal impact on existing 8.5GB database

### 5.3 Cost Analysis

**Google Services** (Free Tier):
- Google Earth Engine: Free (within quota limits)
- Google Drive: Free (15GB storage, >1.5GB needed)
- Compute: Free (uses local machine)

**If Quotas Exceeded**:
- Google Cloud upgrade: $300 free credit (sufficient for full pipeline)
- OR: Slow down extraction rate (still free, just takes longer)

**Total Cost**: **$0** (stays within free tier)

---

## 6. Implementation Roadmap

### Week 1: Infrastructure Setup
- [ ] Day 1-2: GEE account setup, authentication, test extractions
- [ ] Day 3-4: Database migration (add 256 columns)
- [ ] Day 5: Import occurrence data from Parquet file
- [ ] Day 6-7: Implement Python pipeline class

**Deliverable**: Pipeline code complete, database ready, GEE authenticated

### Week 2: Pilot Extraction
- [ ] Day 8-10: Extract 100 species (pilot batch)
- [ ] Day 11-12: Quality assurance, validate embeddings
- [ ] Day 13-14: Optimize pipeline based on pilot results

**Deliverable**: 100 species with complete embeddings, documented QA metrics

### Weeks 3-4: Full-Scale Extraction
- [ ] Day 15-28: Run pipeline on all 48,129 species
- [ ] Concurrent: Draft API documentation
- [ ] Concurrent: Design frontend mockups

**Deliverable**: All species with embeddings, Google Drive archive

### Week 5: API & Product Development
- [ ] Day 29-30: Backend API endpoints
- [ ] Day 31-32: Frontend visualization (Environmental Signature tab)
- [ ] Day 33-34: Species Predictor page
- [ ] Day 35: GEE extraction microservice

**Deliverable**: Functional Species Predictor product

---

## 7. Success Metrics

### Technical Metrics
- ✅ 48,129 species with complete embeddings (256 fields each)
- ✅ <50ms query time for species embeddings
- ✅ <2s response time for diversity predictions
- ✅ Zero data loss during extraction
- ✅ Pipeline resume capability tested and verified

### Product Metrics
- 🎯 Species Predictor accuracy: >70% (top 20 predictions include true species)
- 🎯 Habitat suitability correlation with known distributions: >0.8
- 🎯 Similar species recommendations validated by ecologists
- 🎯 User engagement: >100 predictions per week (initial launch)

### Research Impact
- 📝 Publish methodology paper (open access)
- 📝 Share dataset openly (API + Google Drive archive)
- 📝 Present at ecology/remote sensing conference
- 📝 Collaborate with conservation organizations

---

## 8. Conclusion

This plan provides a **complete roadmap** for integrating Google Earth Engine AlphaEarth embeddings into Treekipedia, enabling a novel **Species Predictor product**. Key highlights:

**Feasibility**:
- ✅ Zero cost (free tier)
- ✅ Minimal local storage (<5GB)
- ✅ 2-3 days processing time
- ✅ Builds on existing infrastructure (PostgreSQL + PostGIS)

**Innovation**:
- 🌟 First tree species database with satellite-derived environmental signatures
- 🌟 Novel application of AlphaEarth for biodiversity prediction
- 🌟 Open data + open methodology

**Impact**:
- 🌍 Enables rapid biodiversity assessment worldwide
- 🌍 Supports reforestation and conservation planning
- 🌍 Advances ecological research with new data dimensions

**Next Steps**:
1. Set up GEE account and authenticate
2. Run database migration (add 256 columns)
3. Start pilot extraction (100 species)
4. Validate quality and proceed to full scale
5. Build API and frontend
6. Launch Species Predictor product

---

**Document prepared by**: AI Development Team
**Date**: October 26, 2025
**Version**: 1.0
**Status**: Ready for Implementation

---
