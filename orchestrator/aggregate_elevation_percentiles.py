#!/usr/bin/env python3
"""
Aggregate Elevation Percentiles from AlphaEarth v4 Data

This script calculates per-species elevation statistics from the v4 parquet file,
handling the deduplication issue where the same pixel may appear multiple times
(once per year sampled).

Output: species_elevation_profiles table with percentiles for each taxon_id

Usage:
    python3 -u aggregate_elevation_percentiles.py [--output-csv] [--load-db]
"""

import sys
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
import argparse
from pathlib import Path
from collections import Counter

# Force unbuffered output
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# Constants
PARQUET_PATH = Path(__file__).parent / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
OUTPUT_CSV = Path(__file__).parent / "species_elevation_profiles.csv"
DB_NAME = "treekipedia"


def fast_grid_density(lats: np.ndarray, lons: np.ndarray, cell_size_deg: float = 0.01) -> np.ndarray:
    """
    Fast vectorized grid-based density calculation.

    Much faster than geohash - uses integer grid cells.
    cell_size_deg=0.01 ≈ 1.1km at equator
    """
    n = len(lats)
    if n < 10:
        return np.ones(n)

    # Create grid cell indices
    cell_x = (lons / cell_size_deg).astype(np.int32)
    cell_y = (lats / cell_size_deg).astype(np.int32)

    # Create unique cell keys
    cell_keys = cell_x * 1000000 + cell_y  # Unique key per cell

    # Count occurrences per cell using pandas for speed
    key_series = pd.Series(cell_keys)
    counts = key_series.map(key_series.value_counts()).values

    # Log-inverse weight
    weights = 1.0 / np.log1p(counts)

    # Normalize
    if weights.max() > 0:
        weights = weights / weights.max()

    return weights


def weighted_percentile(values: np.ndarray, weights: np.ndarray, percentile: float) -> float:
    """Calculate weighted percentile."""
    if len(values) == 0:
        return np.nan

    sorted_indices = np.argsort(values)
    sorted_values = values[sorted_indices]
    sorted_weights = weights[sorted_indices]

    cumsum = np.cumsum(sorted_weights)
    cumsum /= cumsum[-1]  # Normalize

    idx = np.searchsorted(cumsum, percentile / 100.0)
    idx = min(idx, len(sorted_values) - 1)

    return float(sorted_values[idx])


def calculate_species_profiles_fast(df: pd.DataFrame, use_weights: bool = True) -> pd.DataFrame:
    """
    Calculate elevation profiles per species using vectorized operations.
    """
    print("Deduplicating by unique locations...")
    df_unique = df.drop_duplicates(subset=['taxon_id', 'latitude', 'longitude'])
    print(f"  {len(df):,} rows → {len(df_unique):,} unique locations")

    # Remove null elevations
    df_valid = df_unique[df_unique['elevation'].notna()].copy()
    print(f"  {len(df_valid):,} locations with valid elevation")

    # Group by species for fast aggregation
    print("\nCalculating profiles...")

    results = []
    grouped = df_valid.groupby('taxon_id')
    total = len(grouped)

    for i, (taxon_id, group) in enumerate(grouped):
        if (i + 1) % 2000 == 0 or i == 0:
            print(f"  Progress: {i+1:,}/{total:,} ({100*(i+1)/total:.1f}%)")

        elevations = group['elevation'].values.astype(float)
        n = len(elevations)

        if n == 0:
            continue

        # Apply weights for species with enough data
        if use_weights and n >= 10:
            lats = group['latitude'].values
            lons = group['longitude'].values
            weights = fast_grid_density(lats, lons)
        else:
            weights = np.ones(n)

        if n == 1:
            profile = {
                'taxon_id': taxon_id,
                'n_locations': n,
                'elevation_min': float(elevations[0]),
                'elevation_p10': float(elevations[0]),
                'elevation_p25': float(elevations[0]),
                'elevation_median': float(elevations[0]),
                'elevation_p75': float(elevations[0]),
                'elevation_p90': float(elevations[0]),
                'elevation_max': float(elevations[0]),
                'elevation_mean': float(elevations[0]),
                'elevation_std': 0.0,
                'effective_sample_size': 1.0,
            }
        else:
            # Effective sample size (Kish's formula)
            ess = (weights.sum() ** 2) / (weights ** 2).sum()
            weighted_mean = np.average(elevations, weights=weights)

            profile = {
                'taxon_id': taxon_id,
                'n_locations': n,
                'elevation_min': float(np.min(elevations)),
                'elevation_p10': weighted_percentile(elevations, weights, 10),
                'elevation_p25': weighted_percentile(elevations, weights, 25),
                'elevation_median': weighted_percentile(elevations, weights, 50),
                'elevation_p75': weighted_percentile(elevations, weights, 75),
                'elevation_p90': weighted_percentile(elevations, weights, 90),
                'elevation_max': float(np.max(elevations)),
                'elevation_mean': float(weighted_mean),
                'elevation_std': float(np.sqrt(np.average((elevations - weighted_mean)**2, weights=weights))),
                'effective_sample_size': float(ess),
            }

        results.append(profile)

    print(f"  Completed {len(results):,} species")
    return pd.DataFrame(results)


def load_to_database(profiles_df: pd.DataFrame):
    """Load elevation profiles to PostgreSQL."""
    print("\nLoading to PostgreSQL...")

    conn = psycopg2.connect(dbname=DB_NAME)
    cur = conn.cursor()

    # Create table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS species_elevation_profiles (
            taxon_id VARCHAR(50) PRIMARY KEY,
            n_locations INTEGER,
            elevation_min FLOAT,
            elevation_p10 FLOAT,
            elevation_p25 FLOAT,
            elevation_median FLOAT,
            elevation_p75 FLOAT,
            elevation_p90 FLOAT,
            elevation_max FLOAT,
            elevation_mean FLOAT,
            elevation_std FLOAT,
            effective_sample_size FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_elev_median ON species_elevation_profiles(elevation_median);
        CREATE INDEX IF NOT EXISTS idx_elev_range ON species_elevation_profiles(elevation_min, elevation_max);
    """)

    # Truncate and reload
    cur.execute("TRUNCATE species_elevation_profiles;")

    # Prepare data
    columns = ['taxon_id', 'n_locations', 'elevation_min', 'elevation_p10',
               'elevation_p25', 'elevation_median', 'elevation_p75', 'elevation_p90',
               'elevation_max', 'elevation_mean', 'elevation_std', 'effective_sample_size']

    data = [tuple(row[col] for col in columns) for _, row in profiles_df.iterrows()]

    # Bulk insert
    execute_values(cur, f"""
        INSERT INTO species_elevation_profiles ({', '.join(columns)})
        VALUES %s
        ON CONFLICT (taxon_id) DO UPDATE SET
            n_locations = EXCLUDED.n_locations,
            elevation_min = EXCLUDED.elevation_min,
            elevation_p10 = EXCLUDED.elevation_p10,
            elevation_p25 = EXCLUDED.elevation_p25,
            elevation_median = EXCLUDED.elevation_median,
            elevation_p75 = EXCLUDED.elevation_p75,
            elevation_p90 = EXCLUDED.elevation_p90,
            elevation_max = EXCLUDED.elevation_max,
            elevation_mean = EXCLUDED.elevation_mean,
            elevation_std = EXCLUDED.elevation_std,
            effective_sample_size = EXCLUDED.effective_sample_size,
            created_at = NOW()
    """, data, page_size=1000)

    conn.commit()
    print(f"  Loaded {len(data):,} species elevation profiles")

    # Verify
    cur.execute("SELECT COUNT(*) FROM species_elevation_profiles;")
    count = cur.fetchone()[0]
    print(f"  Verified: {count:,} rows in species_elevation_profiles")

    cur.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Aggregate elevation percentiles from v4 data")
    parser.add_argument('--output-csv', action='store_true', help='Save to CSV file')
    parser.add_argument('--load-db', action='store_true', help='Load to PostgreSQL database')
    parser.add_argument('--no-weights', action='store_true', help='Disable proximity weighting')
    args = parser.parse_args()

    print("=" * 60)
    print("Elevation Percentile Aggregation from AlphaEarth v4")
    print("=" * 60)

    # Load parquet
    print(f"\nLoading {PARQUET_PATH}...")
    df = pq.read_table(PARQUET_PATH).to_pandas()
    print(f"  Loaded {len(df):,} rows, {df['taxon_id'].nunique():,} species")

    # Calculate profiles
    profiles_df = calculate_species_profiles_fast(df, use_weights=not args.no_weights)
    print(f"\nGenerated profiles for {len(profiles_df):,} species")

    # Output
    if args.output_csv or not args.load_db:
        print(f"\nSaving to {OUTPUT_CSV}...")
        profiles_df.to_csv(OUTPUT_CSV, index=False)
        print(f"  Saved {len(profiles_df):,} profiles")

    if args.load_db:
        load_to_database(profiles_df)

    # Summary stats
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)
    print(profiles_df[['n_locations', 'elevation_median', 'elevation_std', 'effective_sample_size']].describe())

    print("\nDone!")


if __name__ == "__main__":
    main()
