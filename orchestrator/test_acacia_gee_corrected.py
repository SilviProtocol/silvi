"""
Test Acacia pycnantha with CORRECTED GEE AlphaEarth extraction.
Uses 100 points (sampled from 2,853 total) to test the fixed implementation.
"""

import pandas as pd
from pathlib import Path
from gee_sampler_corrected import export_batch_to_bigquery, wait_for_tasks_optimized
from datetime import datetime

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'
TEST_SPECIES_TAXON_ID = 'AngMaFaFbCx09400-00'  # Acacia pycnantha
TEST_SAMPLE_SIZE = 100

def main():
    print("="*80)
    print("ACACIA PYCNANTHA - CORRECTED GEE + BIGQUERY TEST")
    print("="*80)
    print(f"\nTest configuration:")
    print(f"  Species: Acacia pycnantha (Golden wattle)")
    print(f"  Taxon ID: {TEST_SPECIES_TAXON_ID}")
    print(f"  Sample size: {TEST_SAMPLE_SIZE} points")
    print(f"  Target: treekipedia-476404.alphaearth.occ_embeddings_raw")
    print(f"\nKey fixes:")
    print(f"  ✅ Using .first() to get ee.Image from ImageCollection")
    print(f"  ✅ Band names A00-A63 (not A01-A64)")
    print(f"  ✅ Coordinate order [longitude, latitude]")
    print("="*80)

    # Load GBIF data
    print(f"\n📊 Loading GBIF data...")
    df = pd.read_parquet(GBIF_PARQUET)
    print(f"✅ Loaded {len(df):,} total occurrences")

    # Filter for test species
    species_df = df[df['taxon_id'] == TEST_SPECIES_TAXON_ID]
    print(f"✅ Found {len(species_df)} occurrences for Acacia pycnantha")

    # Sample down to test size
    if len(species_df) > TEST_SAMPLE_SIZE:
        species_df = species_df.sample(n=TEST_SAMPLE_SIZE, random_state=42)
        print(f"✅ Sampled down to {TEST_SAMPLE_SIZE} points")

    # Convert to list of dicts for GEE
    occurrences = []
    for _, row in species_df.iterrows():
        occurrences.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'year': int(row['year']),
            'embedding_year': int(row['year'])
        })

    # Show sample
    print(f"\n📍 Sample occurrences (first 3):")
    for i, occ in enumerate(occurrences[:3], 1):
        print(f"   {i}. Lat: {occ['latitude']:.4f}, Lon: {occ['longitude']:.4f}, Year: {occ['year']}")

    # Show temporal distribution
    year_counts = species_df['year'].value_counts().sort_index()
    print(f"\n📅 Temporal distribution:")
    for year, count in year_counts.items():
        print(f"   {int(year)}: {count} points")

    # Submit to GEE
    batch_id = f"acacia_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n{'='*80}")
    print("SUBMITTING TO GEE")
    print(f"{'='*80}")
    print(f"\n🚀 Batch ID: {batch_id}")

    try:
        task_ids = export_batch_to_bigquery(batch_id, occurrences)
        print(f"\n✅ Submitted {len(task_ids)} GEE task(s)")
        print(f"\n⏳ Waiting for tasks to complete (this may take 2-5 minutes)...")

        results = wait_for_tasks_optimized(task_ids, poll_interval=15)

        # Show results
        print(f"\n{'='*80}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*80}")
        print(f"\n✅ Completed tasks: {len(results['completed'])}")
        print(f"❌ Failed tasks: {len(results['failed'])}")

        if results['failed']:
            print(f"\n⚠️  Failed tasks:")
            for task_id, error in results['failed']:
                print(f"   Task: {task_id}")
                print(f"   Error: {error[:200]}")

        if results['completed']:
            print(f"\n✅ SUCCESS! AlphaEarth embeddings exported to BigQuery")

            if results['stats']:
                stats = results['stats']
                print(f"\n📊 Performance stats:")
                print(f"   Points processed: {stats.get('total_points', 0):,}")
                print(f"   Tasks completed: {stats.get('total_tasks', 0)}")
                print(f"   Elapsed time: {stats.get('elapsed_mins', 0):.2f} minutes")
                print(f"   Throughput: {stats.get('points_per_sec', 0):.2f} points/second")

            print(f"\n{'='*80}")
            print("NEXT STEPS - VERIFY IN BIGQUERY")
            print(f"{'='*80}")
            print(f"\n1. Check table exists and has data:")
            print(f"   bq query --use_legacy_sql=false \\")
            print(f"     'SELECT COUNT(*) as total_rows ")
            print(f"      FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`'")

            print(f"\n2. View sample embeddings:")
            print(f"   bq query --use_legacy_sql=false \\")
            print(f"     'SELECT taxon_id, emb_year, latitude, longitude, ")
            print(f"      A00, A01, A02, A03, A04 ")
            print(f"      FROM `treekipedia-476404.alphaearth.occ_embeddings_raw` ")
            print(f"      WHERE taxon_id = \"{TEST_SPECIES_TAXON_ID}\" ")
            print(f"      LIMIT 5'")

            print(f"\n3. Check all 64 dimensions are present:")
            print(f"   bq show --schema treekipedia-476404:alphaearth.occ_embeddings_raw")

            print(f"\n4. If successful, proceed with full 100 species:")
            print(f"   python3 run_pilot.py")

            print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nTroubleshooting:")
        print(f"  1. Check GEE authentication: earthengine authenticate")
        print(f"  2. Verify BigQuery dataset exists:")
        print(f"     bq mk --dataset treekipedia-476404:alphaearth")
        print(f"  3. Check GEE quota: https://code.earthengine.google.com/")


if __name__ == '__main__':
    main()
