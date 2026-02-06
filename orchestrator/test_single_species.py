"""
Test AlphaEarth embedding extraction with a single species.
This validates the pipeline before running the full 100-species extraction.
"""

import pandas as pd
from pathlib import Path
from run_pilot import (
    load_gbif_data,
    select_pilot_species,
    get_occurrences_for_species,
    get_embedding_year
)

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'

def main():
    print("="*70)
    print("ALPHAEARTH SINGLE SPECIES TEST")
    print("="*70)

    # Load GBIF data
    print(f"\n📊 Loading GBIF data from: {GBIF_PARQUET}")
    df = load_gbif_data()
    print(f"✅ Loaded {len(df):,} occurrences from {df['taxon_id'].nunique()} species\n")

    # Get species list
    species_list = select_pilot_species(df)

    # Select a test species (use #2 - Acacia pycnantha with 2,853 occurrences)
    # Avoiding #1 (Castanea sativa) because it has 69K occurrences
    test_species = species_list[1]

    print(f"{'='*70}")
    print(f"TEST SPECIES")
    print(f"{'='*70}")
    print(f"Taxon ID: {test_species['taxon_id']}")
    print(f"Name: {test_species['species_scientific_name']}")
    print(f"Family: {test_species['family']}")
    print(f"Occurrences: {test_species['occurrence_count']:,}")
    print(f"{'='*70}\n")

    # Get occurrences
    print("📊 Fetching occurrence points...")
    occurrences = get_occurrences_for_species(df, test_species['taxon_id'], max_points=100)
    print(f"✅ Retrieved {len(occurrences)} occurrence points (sampled to max 100 for test)\n")

    # Show sample occurrences
    print(f"{'='*70}")
    print("SAMPLE OCCURRENCES (first 5)")
    print(f"{'='*70}")
    for i, occ in enumerate(occurrences[:5], 1):
        print(f"{i}. Lat: {occ['latitude']:.6f}, Lon: {occ['longitude']:.6f}, "
              f"Year: {occ['year']}, Embedding Year: {occ['embedding_year']}")

    # Year distribution
    print(f"\n{'='*70}")
    print("TEMPORAL DISTRIBUTION")
    print(f"{'='*70}")
    year_counts = {}
    for occ in occurrences:
        year = occ['year']
        year_counts[year] = year_counts.get(year, 0) + 1

    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        pct = (count / len(occurrences)) * 100
        bar = '█' * int(pct / 5)
        print(f"{year}: {count:>3} ({pct:>5.1f}%) {bar}")

    print(f"\n{'='*70}")
    print("TEST DATA READY")
    print(f"{'='*70}")
    print("\nNext steps:")
    print("1. This script validated the GBIF data loading")
    print("2. Ready to test GEE extraction with gee_sampler.py")
    print("3. Once GEE test passes, run full 100 species with run_pilot.py")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
