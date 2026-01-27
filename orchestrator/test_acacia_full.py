"""
Test AlphaEarth extraction with Acacia pycnantha (100 points).
This validates the full pipeline with real GBIF data before running all 100 species.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from gee_sampler_FINAL import export_batch_to_bigquery, wait_for_tasks

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'

def main():
    print("="*70)
    print("ACACIA PYCNANTHA TEST - 100 POINTS")
    print("="*70)

    # Load GBIF data
    print(f"\n📊 Loading GBIF data...")
    df = pd.read_parquet(GBIF_PARQUET)
    print(f"✅ Loaded {len(df):,} total occurrences")

    # Filter for Acacia pycnantha (taxon_id from GBIF_INTEGRATION_COMPLETE.md)
    # It's the #2 species with 2,853 occurrences
    # Note: GBIF includes author names (e.g., "Acacia pycnantha Benth.")
    acacia_df = df[df['species'].str.contains('Acacia pycnantha', case=False, na=False)].copy()

    if len(acacia_df) == 0:
        print("❌ No Acacia pycnantha found! Checking species names...")
        print("\nTop 10 species by occurrence count:")
        for species in df['species'].value_counts().head(10).index:
            count = df[df['species'] == species].shape[0]
            print(f"  - {species}: {count:,} occurrences")
        return

    print(f"\n✅ Found Acacia pycnantha with {len(acacia_df):,} occurrences")

    # Sample 100 points
    if len(acacia_df) > 100:
        acacia_sample = acacia_df.sample(n=100, random_state=42)
    else:
        acacia_sample = acacia_df

    print(f"📊 Sampled {len(acacia_sample)} points for test")

    # Get taxon_id
    taxon_id = acacia_sample['taxon_id'].iloc[0]
    print(f"🔍 Taxon ID: {taxon_id}")

    # Convert to list of dicts for GEE
    occurrences = []
    for _, row in acacia_sample.iterrows():
        occurrences.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'year': int(row['year']),
            'embedding_year': int(row['year'])  # Direct pass-through (2017-2024)
        })

    # Show temporal distribution
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
        bar = '█' * int(pct / 2)
        print(f"{year}: {count:>3} ({pct:>5.1f}%) {bar}")

    # Submit to GEE
    batch_id = f"acacia_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n{'='*70}")
    print("SUBMITTING TO GEE")
    print(f"{'='*70}")
    print(f"Batch ID: {batch_id}")
    print(f"Points: {len(occurrences)}")
    print(f"Target: treekipedia-476404.alphaearth.occ_embeddings_raw")

    task_ids = export_batch_to_bigquery(batch_id, occurrences, batch_size=2000)
    print(f"\n✅ Submitted {len(task_ids)} GEE task(s)")

    # Wait for completion
    print(f"\n{'='*70}")
    print("MONITORING TASKS")
    print(f"{'='*70}")
    results = wait_for_tasks(task_ids, poll_interval=30)

    # Results
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")
    print(f"✅ Completed: {len(results['completed'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results['failed']:
        print("\nFailed tasks:")
        for task_id, error in results['failed']:
            print(f"  - {task_id}")
            print(f"    Error: {error[:100]}")

    if results['completed']:
        print(f"\n🎉 SUCCESS!")
        print(f"\nNext: Query BigQuery to verify embeddings:")
        print(f"  bq query --use_legacy_sql=false \\")
        print(f"    'SELECT COUNT(*) FROM `treekipedia-476404.alphaearth.occ_embeddings_raw` \\")
        print(f"     WHERE taxon_id = \"{taxon_id}\"'")
        print(f"\nThen: Run full 100-species extraction with run_pilot.py")

    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
