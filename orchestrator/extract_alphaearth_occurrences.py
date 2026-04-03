#!/usr/bin/env python3
"""
AlphaEarth Occurrence Data Extraction Script
============================================

Purpose: Extract high-quality occurrence data for AlphaEarth embedding generation.

Filters Applied:
1. Coordinate Uncertainty: < 10 meters (highest accuracy)
2. Year Range: 2017-2024 (AlphaEarth satellite coverage period)

This script creates a reproducible extraction with full provenance metadata
for future reference and audit trails.

Usage:
    python extract_alphaearth_occurrences.py

Output:
    - alphaearth_input_YYYYMMDD_HHMMSS.parquet (filtered occurrences)
    - alphaearth_input_YYYYMMDD_HHMMSS_metadata.json (extraction metadata)

Author: Treekipedia Team
Created: January 2026
"""

import pandas as pd
import numpy as np
import json
import hashlib
from datetime import datetime
from pathlib import Path
import sys

# =============================================================================
# CONFIGURATION
# =============================================================================

# Source file - December 2025 GBIF occurrence data with quality metrics
SOURCE_FILE = "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"

# Filter criteria
MAX_COORDINATE_UNCERTAINTY_METERS = 10  # Only sub-10m accuracy
MIN_YEAR = 2017  # AlphaEarth starts in 2017
MAX_YEAR = 2024  # AlphaEarth latest available

# Output directory
OUTPUT_DIR = Path("/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/alphaearth_extractions")

# =============================================================================
# MAIN EXTRACTION LOGIC
# =============================================================================

def compute_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of source file for provenance tracking."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_alphaearth_occurrences():
    """
    Main extraction function.

    Applies filters and creates output with full metadata.
    """
    print("=" * 80)
    print("AlphaEarth Occurrence Data Extraction")
    print("=" * 80)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ==========================================================================
    # Step 1: Load Source Data
    # ==========================================================================
    print(f"\n📂 Loading source file...")
    print(f"   Path: {SOURCE_FILE}")

    if not Path(SOURCE_FILE).exists():
        print(f"❌ ERROR: Source file not found!")
        sys.exit(1)

    # Compute source file hash for provenance
    print("   Computing file hash for provenance...")
    source_hash = compute_file_hash(SOURCE_FILE)
    print(f"   SHA256: {source_hash[:16]}...")

    # Load parquet
    df = pd.read_parquet(SOURCE_FILE)
    source_records = len(df)
    source_species = df['taxon_id'].nunique()

    print(f"\n✅ Source data loaded:")
    print(f"   Total records: {source_records:,}")
    print(f"   Unique species (taxon_id): {source_species:,}")
    print(f"   Columns: {list(df.columns)}")

    # ==========================================================================
    # Step 2: Analyze Data Quality Before Filtering
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PRE-FILTER DATA ANALYSIS")
    print("=" * 80)

    # Year distribution
    print("\n📊 Year Distribution:")
    year_counts = df['year'].value_counts().sort_index()
    records_with_year = df['year'].notna().sum()
    print(f"   Records with year data: {records_with_year:,} ({100*records_with_year/len(df):.1f}%)")
    print(f"   Year range: {df['year'].min():.0f} - {df['year'].max():.0f}")

    # Show 2017-2024 distribution
    print("\n   AlphaEarth period (2017-2024):")
    for year in range(2017, 2025):
        count = (df['year'] == year).sum()
        pct = 100 * count / len(df)
        print(f"     {year}: {count:>10,} records ({pct:>5.2f}%)")

    # Coordinate uncertainty distribution
    print("\n📊 Coordinate Uncertainty Distribution:")
    uncertainty_col = 'coordinateUncertaintyInMeters'
    records_with_uncertainty = df[uncertainty_col].notna().sum()
    print(f"   Records with uncertainty data: {records_with_uncertainty:,} ({100*records_with_uncertainty/len(df):.1f}%)")

    if records_with_uncertainty > 0:
        print(f"   Min uncertainty: {df[uncertainty_col].min():.2f}m")
        print(f"   Max uncertainty: {df[uncertainty_col].max():.2f}m")
        print(f"   Median uncertainty: {df[uncertainty_col].median():.2f}m")

        # Show distribution by threshold
        print("\n   Uncertainty thresholds:")
        for threshold in [1, 5, 10, 50, 100, 500, 1000]:
            count = (df[uncertainty_col] <= threshold).sum()
            pct = 100 * count / len(df)
            marker = " ← TARGET" if threshold == MAX_COORDINATE_UNCERTAINTY_METERS else ""
            print(f"     ≤{threshold:>4}m: {count:>10,} records ({pct:>5.2f}%){marker}")

    # ==========================================================================
    # Step 3: Apply Filters
    # ==========================================================================
    print("\n" + "=" * 80)
    print("APPLYING FILTERS")
    print("=" * 80)

    print(f"\n🔍 Filter criteria:")
    print(f"   1. coordinateUncertaintyInMeters < {MAX_COORDINATE_UNCERTAINTY_METERS}m")
    print(f"   2. year >= {MIN_YEAR} AND year <= {MAX_YEAR}")

    # Filter 1: Coordinate uncertainty
    mask_uncertainty = df[uncertainty_col] < MAX_COORDINATE_UNCERTAINTY_METERS
    after_uncertainty = mask_uncertainty.sum()
    print(f"\n   After uncertainty filter: {after_uncertainty:,} records")

    # Filter 2: Year range
    mask_year = (df['year'] >= MIN_YEAR) & (df['year'] <= MAX_YEAR)
    after_year = mask_year.sum()
    print(f"   After year filter alone: {after_year:,} records")

    # Combined filter
    mask_combined = mask_uncertainty & mask_year
    df_filtered = df[mask_combined].copy()

    filtered_records = len(df_filtered)
    filtered_species = df_filtered['taxon_id'].nunique()

    print(f"\n✅ FINAL FILTERED DATASET:")
    print(f"   Records: {filtered_records:,} ({100*filtered_records/source_records:.2f}% of source)")
    print(f"   Species: {filtered_species:,} ({100*filtered_species/source_species:.2f}% of source)")

    # ==========================================================================
    # Step 4: Analyze Filtered Data
    # ==========================================================================
    print("\n" + "=" * 80)
    print("FILTERED DATA ANALYSIS")
    print("=" * 80)

    # Year distribution in filtered data
    print("\n📊 Year distribution (filtered):")
    for year in range(MIN_YEAR, MAX_YEAR + 1):
        count = (df_filtered['year'] == year).sum()
        pct = 100 * count / len(df_filtered) if len(df_filtered) > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"   {year}: {count:>10,} ({pct:>5.2f}%) {bar}")

    # Species occurrence distribution
    print("\n📊 Species occurrence distribution (filtered):")
    species_counts = df_filtered['taxon_id'].value_counts()
    print(f"   Min occurrences per species: {species_counts.min()}")
    print(f"   Max occurrences per species: {species_counts.max()}")
    print(f"   Mean occurrences per species: {species_counts.mean():.1f}")
    print(f"   Median occurrences per species: {species_counts.median():.1f}")

    # Distribution by occurrence count
    print("\n   Species by occurrence count:")
    for threshold in [1, 5, 10, 50, 100, 500, 1000]:
        count = (species_counts >= threshold).sum()
        pct = 100 * count / len(species_counts)
        print(f"     ≥{threshold:>4} occurrences: {count:>6,} species ({pct:>5.1f}%)")

    # Top 10 species
    print("\n🏆 Top 10 species by occurrence count:")
    for taxon_id, count in species_counts.head(10).items():
        # Try to get scientific name if available
        name = df_filtered[df_filtered['taxon_id'] == taxon_id]['species_scientific_name'].iloc[0]
        print(f"   {taxon_id}: {count:,} occurrences ({name})")

    # Coordinate uncertainty stats
    print("\n📊 Coordinate uncertainty (filtered):")
    print(f"   Min: {df_filtered[uncertainty_col].min():.2f}m")
    print(f"   Max: {df_filtered[uncertainty_col].max():.2f}m")
    print(f"   Mean: {df_filtered[uncertainty_col].mean():.2f}m")
    print(f"   Median: {df_filtered[uncertainty_col].median():.2f}m")

    # Geographic coverage
    print("\n🌍 Geographic coverage (filtered):")
    print(f"   Latitude range: {df_filtered['decimalLatitude'].min():.4f} to {df_filtered['decimalLatitude'].max():.4f}")
    print(f"   Longitude range: {df_filtered['decimalLongitude'].min():.4f} to {df_filtered['decimalLongitude'].max():.4f}")

    # ==========================================================================
    # Step 5: Prepare Output Columns
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PREPARING OUTPUT")
    print("=" * 80)

    # Select and rename columns for GEE processing
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

    # Check which columns exist
    available_columns = [col for col in output_columns if col in df_filtered.columns]
    missing_columns = [col for col in output_columns if col not in df_filtered.columns]

    if missing_columns:
        print(f"⚠️  Missing columns (will be excluded): {missing_columns}")

    df_output = df_filtered[available_columns].copy()

    # Add embedding_year column (same as year for AlphaEarth)
    df_output['embedding_year'] = df_output['year'].astype(int)

    print(f"\n📋 Output columns: {list(df_output.columns)}")

    # ==========================================================================
    # Step 6: Save Output Files
    # ==========================================================================
    output_parquet = OUTPUT_DIR / f"alphaearth_input_{timestamp}.parquet"
    output_metadata = OUTPUT_DIR / f"alphaearth_input_{timestamp}_metadata.json"

    # Save parquet
    print(f"\n💾 Saving output files...")
    df_output.to_parquet(output_parquet, index=False, compression='snappy')
    print(f"   ✅ Parquet: {output_parquet}")
    print(f"      Size: {output_parquet.stat().st_size / (1024*1024):.2f} MB")

    # Compute output hash
    output_hash = compute_file_hash(str(output_parquet))

    # Create comprehensive metadata
    metadata = {
        "extraction_info": {
            "timestamp": timestamp,
            "timestamp_iso": datetime.now().isoformat(),
            "script_name": "extract_alphaearth_occurrences.py",
            "script_version": "1.0.0",
            "purpose": "Extract high-quality occurrence data for AlphaEarth embedding generation"
        },
        "source_data": {
            "file_path": SOURCE_FILE,
            "file_name": Path(SOURCE_FILE).name,
            "sha256_hash": source_hash,
            "total_records": source_records,
            "total_species": source_species,
            "columns": list(df.columns)
        },
        "filter_criteria": {
            "coordinate_uncertainty_max_meters": MAX_COORDINATE_UNCERTAINTY_METERS,
            "year_min": MIN_YEAR,
            "year_max": MAX_YEAR,
            "description": f"coordinateUncertaintyInMeters < {MAX_COORDINATE_UNCERTAINTY_METERS} AND year >= {MIN_YEAR} AND year <= {MAX_YEAR}"
        },
        "output_data": {
            "file_path": str(output_parquet),
            "file_name": output_parquet.name,
            "sha256_hash": output_hash,
            "total_records": filtered_records,
            "total_species": filtered_species,
            "columns": list(df_output.columns),
            "retention_rate_records": round(filtered_records / source_records * 100, 4),
            "retention_rate_species": round(filtered_species / source_species * 100, 4)
        },
        "statistics": {
            "year_distribution": {str(year): int((df_filtered['year'] == year).sum()) for year in range(MIN_YEAR, MAX_YEAR + 1)},
            "coordinate_uncertainty": {
                "min": float(df_filtered[uncertainty_col].min()),
                "max": float(df_filtered[uncertainty_col].max()),
                "mean": float(df_filtered[uncertainty_col].mean()),
                "median": float(df_filtered[uncertainty_col].median())
            },
            "species_occurrence_counts": {
                "min": int(species_counts.min()),
                "max": int(species_counts.max()),
                "mean": float(species_counts.mean()),
                "median": float(species_counts.median())
            },
            "geographic_bounds": {
                "lat_min": float(df_filtered['decimalLatitude'].min()),
                "lat_max": float(df_filtered['decimalLatitude'].max()),
                "lon_min": float(df_filtered['decimalLongitude'].min()),
                "lon_max": float(df_filtered['decimalLongitude'].max())
            },
            "species_by_min_occurrences": {
                f"gte_{t}": int((species_counts >= t).sum()) for t in [1, 5, 10, 50, 100, 500, 1000]
            }
        },
        "top_species": [
            {
                "taxon_id": taxon_id,
                "occurrence_count": int(count),
                "scientific_name": str(df_filtered[df_filtered['taxon_id'] == taxon_id]['species_scientific_name'].iloc[0])
            }
            for taxon_id, count in species_counts.head(20).items()
        ],
        "notes": [
            "This extraction is designed for AlphaEarth embedding generation",
            "Coordinate uncertainty < 10m ensures sub-pixel accuracy for 10m resolution imagery",
            "Year range 2017-2024 matches AlphaEarth satellite coverage",
            "embedding_year column added for GEE processing compatibility"
        ]
    }

    # Save metadata
    with open(output_metadata, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   ✅ Metadata: {output_metadata}")

    # ==========================================================================
    # Step 7: Summary
    # ==========================================================================
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)

    print(f"""
📊 SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Source:     {source_records:>12,} records │ {source_species:>8,} species
Filtered:   {filtered_records:>12,} records │ {filtered_species:>8,} species
Retention:  {100*filtered_records/source_records:>11.2f}% records │ {100*filtered_species/source_species:>7.2f}% species
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 OUTPUT FILES:
   1. {output_parquet.name}
      → Ready for GEE AlphaEarth sampling

   2. {output_metadata.name}
      → Full provenance and statistics

🚀 NEXT STEPS:
   1. Review metadata JSON to verify extraction parameters
   2. Use gee_sampler_FIXED.py to extract AlphaEarth embeddings
   3. Run cluster_embeddings.py to generate species centroids
   4. Load centroids to PostgreSQL for API access
""")

    return {
        "output_parquet": str(output_parquet),
        "output_metadata": str(output_metadata),
        "filtered_records": filtered_records,
        "filtered_species": filtered_species
    }


if __name__ == "__main__":
    result = extract_alphaearth_occurrences()
    print(f"\n✅ Extraction complete. Files saved to: {OUTPUT_DIR}")
