#!/usr/bin/env python3
"""
AlphaEarth Occurrence Data Extraction Script - V2 (Two-Phase)
==============================================================

Purpose: Extract occurrence data for AlphaEarth embedding generation in two phases.

PHASE 1: High-Confidence (2017-2024)
- Year: 2017-2024 (matches AlphaEarth temporal coverage)
- Uncertainty: < 10m OR NULL
- Confidence: HIGH
- No forest validation needed (temporal match)

PHASE 2: Historical with Forest Validation (pre-2017)
- Year: < 2017 (all historical data)
- Uncertainty: < 10m OR NULL
- Confidence: MEDIUM (requires forest validation at GEE sampling time)
- Forest check: Only include if current AlphaEarth pixel shows forest
- Rationale: If forest exists today at that coordinate, habitat likely similar

Usage:
    python extract_alphaearth_occurrences_v2.py --phase 1  # Run Phase 1 first
    python extract_alphaearth_occurrences_v2.py --phase 2  # Run Phase 2 after

Output:
    Phase 1: alphaearth_phase1_YYYYMMDD_HHMMSS.parquet
    Phase 2: alphaearth_phase2_YYYYMMDD_HHMMSS.parquet

Author: Treekipedia Team
Created: January 2026
"""

import pandas as pd
import numpy as np
import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
import sys

# =============================================================================
# CONFIGURATION
# =============================================================================

SOURCE_FILE = "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"

# Phase 1: High-confidence (temporal match)
PHASE1_MIN_YEAR = 2017
PHASE1_MAX_YEAR = 2024

# Phase 2: Historical (requires forest validation)
PHASE2_MAX_YEAR = 2016  # Everything before 2017

# Shared filter
MAX_COORDINATE_UNCERTAINTY_METERS = 10  # Only sub-10m OR NULL

# Output directory
OUTPUT_DIR = Path("/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/alphaearth_extractions")


# =============================================================================
# UTILITIES
# =============================================================================

def compute_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of source file for provenance tracking."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def apply_uncertainty_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply coordinate uncertainty filter: < 10m OR NULL."""
    mask = (df['coordinateUncertaintyInMeters'] < MAX_COORDINATE_UNCERTAINTY_METERS) | \
           (df['coordinateUncertaintyInMeters'].isna())
    return df[mask].copy()


def prepare_output_columns(df: pd.DataFrame, phase: int) -> pd.DataFrame:
    """Select and prepare output columns."""
    output_columns = [
        'taxon_id',
        'species_scientific_name',
        'decimalLatitude',
        'decimalLongitude',
        'year',
        'coordinateUncertaintyInMeters',
        'elevation',
        'establishmentMeans',
        'occurrenceID',
        'gbifID'
    ]

    available_columns = [col for col in output_columns if col in df.columns]
    df_output = df[available_columns].copy()

    # Add metadata columns
    df_output['phase'] = phase
    df_output['confidence'] = 'HIGH' if phase == 1 else 'MEDIUM'

    # For Phase 1: embedding_year = occurrence year
    # For Phase 2: embedding_year = 2017 (earliest AlphaEarth, will be validated)
    if phase == 1:
        df_output['embedding_year'] = df_output['year'].astype(int)
    else:
        # Map to nearest AlphaEarth year (2017 for all pre-2017)
        df_output['embedding_year'] = 2017
        # Flag that forest validation is required
        df_output['requires_forest_validation'] = True

    return df_output


# =============================================================================
# PHASE 1: HIGH-CONFIDENCE (2017-2024)
# =============================================================================

def extract_phase1(df: pd.DataFrame, timestamp: str) -> dict:
    """
    Extract Phase 1: High-confidence occurrences (2017-2024).

    These have temporal match with AlphaEarth - no forest validation needed.
    """
    print("\n" + "=" * 70)
    print("PHASE 1: HIGH-CONFIDENCE EXTRACTION (2017-2024)")
    print("=" * 70)

    # Year filter
    mask_year = (df['year'] >= PHASE1_MIN_YEAR) & (df['year'] <= PHASE1_MAX_YEAR)
    df_year = df[mask_year]
    print(f"\n📅 Year filter ({PHASE1_MIN_YEAR}-{PHASE1_MAX_YEAR}): {len(df_year):,} records")

    # Uncertainty filter
    df_filtered = apply_uncertainty_filter(df_year)
    print(f"📍 Uncertainty filter (<{MAX_COORDINATE_UNCERTAINTY_METERS}m OR NULL): {len(df_filtered):,} records")

    # Statistics
    filtered_species = df_filtered['taxon_id'].nunique()
    print(f"\n✅ PHASE 1 RESULT:")
    print(f"   Records: {len(df_filtered):,}")
    print(f"   Species: {filtered_species:,}")

    # Year distribution
    print(f"\n📊 Year distribution:")
    for year in range(PHASE1_MIN_YEAR, PHASE1_MAX_YEAR + 1):
        count = (df_filtered['year'] == year).sum()
        pct = 100 * count / len(df_filtered) if len(df_filtered) > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"   {year}: {count:>10,} ({pct:>5.2f}%) {bar}")

    # Prepare output
    df_output = prepare_output_columns(df_filtered, phase=1)

    # Save
    output_path = OUTPUT_DIR / f"alphaearth_phase1_{timestamp}.parquet"
    df_output.to_parquet(output_path, index=False, compression='snappy')
    print(f"\n💾 Saved: {output_path}")
    print(f"   Size: {output_path.stat().st_size / (1024*1024):.2f} MB")

    return {
        'phase': 1,
        'output_path': str(output_path),
        'records': len(df_filtered),
        'species': filtered_species,
        'year_range': f"{PHASE1_MIN_YEAR}-{PHASE1_MAX_YEAR}",
        'confidence': 'HIGH',
        'requires_forest_validation': False
    }


# =============================================================================
# PHASE 2: HISTORICAL WITH FOREST VALIDATION (pre-2017)
# =============================================================================

def extract_phase2(df: pd.DataFrame, timestamp: str) -> dict:
    """
    Extract Phase 2: Historical occurrences (pre-2017).

    These require forest validation at GEE sampling time:
    - Sample AlphaEarth embedding
    - Sample Hansen treecover2000 and lossyear
    - Only keep if treecover2000 > 25 AND lossyear = 0 (still forested)
    """
    print("\n" + "=" * 70)
    print("PHASE 2: HISTORICAL EXTRACTION (pre-2017, requires forest validation)")
    print("=" * 70)

    # Year filter (everything before 2017)
    mask_year = (df['year'] < PHASE1_MIN_YEAR) & (df['year'].notna())
    df_year = df[mask_year]
    print(f"\n📅 Year filter (<{PHASE1_MIN_YEAR}): {len(df_year):,} records")

    # Also include records with NULL year (will be validated by forest check)
    mask_null_year = df['year'].isna()
    df_null = df[mask_null_year]
    print(f"📅 Records with NULL year: {len(df_null):,} records")

    # Combine
    df_historical = pd.concat([df_year, df_null])
    print(f"📅 Total historical candidates: {len(df_historical):,} records")

    # Uncertainty filter
    df_filtered = apply_uncertainty_filter(df_historical)
    print(f"📍 Uncertainty filter (<{MAX_COORDINATE_UNCERTAINTY_METERS}m OR NULL): {len(df_filtered):,} records")

    # Statistics
    filtered_species = df_filtered['taxon_id'].nunique()

    # How many are NEW species not in Phase 1?
    phase1_mask = (df['year'] >= PHASE1_MIN_YEAR) & (df['year'] <= PHASE1_MAX_YEAR)
    phase1_species = set(df[phase1_mask]['taxon_id'].unique())
    phase2_species = set(df_filtered['taxon_id'].unique())
    new_species = phase2_species - phase1_species

    print(f"\n✅ PHASE 2 RESULT:")
    print(f"   Records: {len(df_filtered):,}")
    print(f"   Species: {filtered_species:,}")
    print(f"   NEW species (not in Phase 1): {len(new_species):,}")

    # Decade distribution
    print(f"\n📊 Decade distribution:")
    df_with_year = df_filtered[df_filtered['year'].notna()].copy()
    df_with_year['decade'] = (df_with_year['year'] // 10 * 10).astype(int)
    decade_counts = df_with_year.groupby('decade').size().sort_index()
    for decade, count in decade_counts.items():
        if decade >= 1900:  # Only show recent decades
            pct = 100 * count / len(df_filtered)
            print(f"   {int(decade)}s: {count:>10,} ({pct:>5.2f}%)")

    null_count = df_filtered['year'].isna().sum()
    if null_count > 0:
        pct = 100 * null_count / len(df_filtered)
        print(f"   NULL:  {null_count:>10,} ({pct:>5.2f}%)")

    # Prepare output
    df_output = prepare_output_columns(df_filtered, phase=2)

    # Save
    output_path = OUTPUT_DIR / f"alphaearth_phase2_{timestamp}.parquet"
    df_output.to_parquet(output_path, index=False, compression='snappy')
    print(f"\n💾 Saved: {output_path}")
    print(f"   Size: {output_path.stat().st_size / (1024*1024):.2f} MB")

    print(f"\n⚠️  IMPORTANT: Phase 2 data requires forest validation at GEE sampling!")
    print(f"   The GEE sampler must check Hansen treecover2000 > 25 AND lossyear = 0")
    print(f"   Records where forest no longer exists should be excluded")

    return {
        'phase': 2,
        'output_path': str(output_path),
        'records': len(df_filtered),
        'species': filtered_species,
        'new_species_count': len(new_species),
        'year_range': f"pre-{PHASE1_MIN_YEAR}",
        'confidence': 'MEDIUM',
        'requires_forest_validation': True
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Extract AlphaEarth occurrences (two-phase)')
    parser.add_argument('--phase', type=int, choices=[1, 2], required=True,
                        help='Phase to extract: 1 (2017-2024) or 2 (pre-2017)')
    parser.add_argument('--both', action='store_true',
                        help='Run both phases sequentially')
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("AlphaEarth Occurrence Extraction - V2 (Two-Phase)")
    print("=" * 70)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load source data
    print(f"\n📂 Loading source file...")
    print(f"   Path: {SOURCE_FILE}")

    if not Path(SOURCE_FILE).exists():
        print(f"❌ ERROR: Source file not found!")
        sys.exit(1)

    df = pd.read_parquet(SOURCE_FILE)
    print(f"✅ Loaded {len(df):,} records, {df['taxon_id'].nunique():,} species")

    # Compute source hash
    source_hash = compute_file_hash(SOURCE_FILE)

    results = []

    if args.phase == 1 or args.both:
        result1 = extract_phase1(df, timestamp)
        results.append(result1)

    if args.phase == 2 or args.both:
        result2 = extract_phase2(df, timestamp)
        results.append(result2)

    # Save metadata
    metadata = {
        'extraction_timestamp': timestamp,
        'source_file': SOURCE_FILE,
        'source_hash': source_hash,
        'source_records': len(df),
        'source_species': df['taxon_id'].nunique(),
        'uncertainty_filter': f'< {MAX_COORDINATE_UNCERTAINTY_METERS}m OR NULL',
        'phases': results
    }

    metadata_path = OUTPUT_DIR / f"extraction_metadata_{timestamp}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"\n📋 Metadata saved: {metadata_path}")

    # Summary
    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    total_records = sum(r['records'] for r in results)
    total_species = sum(r['species'] for r in results)  # Note: may have overlap

    for r in results:
        print(f"\nPhase {r['phase']} ({r['year_range']}):")
        print(f"  Records: {r['records']:,}")
        print(f"  Species: {r['species']:,}")
        print(f"  Confidence: {r['confidence']}")
        print(f"  Forest validation: {'Required' if r['requires_forest_validation'] else 'Not needed'}")

    print(f"\n🎯 NEXT STEPS:")
    print(f"   1. Run GEE sampler on Phase 1 data (no validation needed)")
    print(f"   2. Run GEE sampler on Phase 2 data WITH Hansen forest check")
    print(f"   3. Combine results in BigQuery")
    print(f"   4. Run clustering on combined embeddings")


if __name__ == "__main__":
    main()
