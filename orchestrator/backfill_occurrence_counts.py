#!/usr/bin/env python3
"""
Backfill Occurrence Counts for AlphaEarth Embeddings
=====================================================
Joins the deduplicated embeddings with original occurrence data to
count how many GBIF occurrences fell into each pixel-year.

This enables weighted K-means clustering to correct for sampling bias.

Usage:
    python backfill_occurrence_counts.py [--output OUTPUT_DIR]

Input:
    - Original occurrence parquet with year info
    - Exported BigQuery embeddings (local parquet)

Output:
    - Updated parquet files with n_occurrences column
    - Summary statistics
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
OCCURRENCE_FILE = BASE_DIR / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"
EMBEDDINGS_DIR = BASE_DIR / "orchestrator" / "bigquery_exports" / "alphaearth_embeddings_v4"
OUTPUT_DIR = BASE_DIR / "orchestrator" / "bigquery_exports" / "alphaearth_embeddings_v4_weighted"

# Deduplication precision (must match original deduplication)
COORD_DECIMALS = 4


def load_occurrence_counts(year_range: tuple = (2017, 2024)) -> pd.DataFrame:
    """
    Load original occurrence data and count occurrences per pixel-year-species.

    Returns DataFrame with columns: taxon_id, lat_round, lon_round, year, n_occurrences
    """
    logger.info(f"Loading occurrence data from {OCCURRENCE_FILE}...")

    # Load only needed columns
    df = pd.read_parquet(
        OCCURRENCE_FILE,
        columns=['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year']
    )
    logger.info(f"  Total occurrences: {len(df):,}")

    # Filter to year range
    min_year, max_year = year_range
    df = df[(df['year'] >= min_year) & (df['year'] <= max_year)].copy()
    logger.info(f"  After year filter ({min_year}-{max_year}): {len(df):,}")

    # Round coordinates (same as original deduplication)
    df['lat_round'] = df['decimalLatitude'].round(COORD_DECIMALS)
    df['lon_round'] = df['decimalLongitude'].round(COORD_DECIMALS)

    # Count occurrences per pixel-year-species
    logger.info("  Counting occurrences per pixel-year-species...")
    counts = df.groupby(
        ['taxon_id', 'lat_round', 'lon_round', 'year'],
        observed=True
    ).size().reset_index(name='n_occurrences')

    logger.info(f"  Unique pixel-year-species combinations: {len(counts):,}")
    logger.info(f"  Occurrence count stats:")
    logger.info(f"    Mean: {counts['n_occurrences'].mean():.2f}")
    logger.info(f"    Median: {counts['n_occurrences'].median():.0f}")
    logger.info(f"    Max: {counts['n_occurrences'].max()}")
    logger.info(f"    >1 occurrence: {(counts['n_occurrences'] > 1).sum():,} ({100*(counts['n_occurrences'] > 1).mean():.1f}%)")

    return counts


def process_embedding_batch(
    batch_file: Path,
    occurrence_counts: pd.DataFrame,
    output_dir: Path
) -> dict:
    """
    Process one batch of embeddings, adding occurrence counts.

    Returns statistics dict.
    """
    logger.info(f"Processing {batch_file.name}...")

    # Load embeddings batch
    df_emb = pd.read_parquet(batch_file)
    n_original = len(df_emb)

    # Round coordinates to match occurrence data
    # Note: BigQuery export uses 'latitude', 'longitude' columns
    df_emb['lat_round'] = df_emb['latitude'].round(COORD_DECIMALS)
    df_emb['lon_round'] = df_emb['longitude'].round(COORD_DECIMALS)

    # Use orig_year for joining (the actual observation year)
    # If orig_year is not available, fall back to emb_year
    year_col = 'orig_year' if 'orig_year' in df_emb.columns else 'emb_year'

    # Join with occurrence counts
    df_merged = df_emb.merge(
        occurrence_counts,
        left_on=['taxon_id', 'lat_round', 'lon_round', year_col],
        right_on=['taxon_id', 'lat_round', 'lon_round', 'year'],
        how='left'
    )

    # Fill missing counts with 1 (at minimum, the point exists)
    df_merged['n_occurrences'] = df_merged['n_occurrences'].fillna(1).astype(int)

    # Drop temporary columns
    df_merged = df_merged.drop(columns=['lat_round', 'lon_round', 'year'], errors='ignore')

    # Calculate log weights
    n_max = occurrence_counts['n_occurrences'].max()
    df_merged['log_weight'] = np.log1p(df_merged['n_occurrences']) / np.log1p(n_max)

    # Save to output
    output_file = output_dir / batch_file.name
    df_merged.to_parquet(output_file, index=False, compression='snappy')

    # Statistics
    matched = (df_merged['n_occurrences'] > 0).sum()
    stats = {
        'file': batch_file.name,
        'n_rows': n_original,
        'n_matched': matched,
        'match_rate': matched / n_original,
        'mean_occurrences': df_merged['n_occurrences'].mean(),
        'max_occurrences': df_merged['n_occurrences'].max(),
        'mean_weight': df_merged['log_weight'].mean(),
        'output_size_mb': output_file.stat().st_size / (1024 * 1024)
    }

    logger.info(f"  Matched: {matched:,}/{n_original:,} ({100*stats['match_rate']:.1f}%)")
    logger.info(f"  Mean occurrences: {stats['mean_occurrences']:.2f}")
    logger.info(f"  Saved: {output_file.name} ({stats['output_size_mb']:.1f} MB)")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill occurrence counts for embeddings")
    parser.add_argument("--embeddings-dir", type=str, default=str(EMBEDDINGS_DIR),
                        help="Directory with embedding parquet files")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR),
                        help="Output directory for weighted embeddings")
    parser.add_argument("--year-min", type=int, default=2017)
    parser.add_argument("--year-max", type=int, default=2024)
    args = parser.parse_args()

    embeddings_dir = Path(args.embeddings_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Backfill Occurrence Counts for Weighted Clustering")
    logger.info("=" * 60)
    logger.info(f"Embeddings: {embeddings_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Year range: {args.year_min}-{args.year_max}")

    # Load occurrence counts
    occurrence_counts = load_occurrence_counts((args.year_min, args.year_max))

    # Find embedding files
    batch_files = sorted(embeddings_dir.glob("batch_*.parquet"))
    if not batch_files:
        logger.error("No batch files found!")
        return

    logger.info(f"\nFound {len(batch_files)} batch files to process")

    # Process each batch
    all_stats = []
    start_time = datetime.now()

    for batch_file in batch_files:
        stats = process_embedding_batch(batch_file, occurrence_counts, output_dir)
        all_stats.append(stats)

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    total_rows = sum(s['n_rows'] for s in all_stats)
    total_matched = sum(s['n_matched'] for s in all_stats)
    total_size = sum(s['output_size_mb'] for s in all_stats)

    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total rows processed: {total_rows:,}")
    logger.info(f"Total matched with counts: {total_matched:,} ({100*total_matched/total_rows:.1f}%)")
    logger.info(f"Total output size: {total_size:.1f} MB")
    logger.info(f"Time elapsed: {elapsed/60:.1f} minutes")

    # Save summary
    summary_df = pd.DataFrame(all_stats)
    summary_file = output_dir / "backfill_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
