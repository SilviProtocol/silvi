"""
Test single species with GEE AlphaEarth extraction and BigQuery upload.
Uses Acacia pycnantha (2,853 occurrences) but samples down to 100 points for quick test.
"""

import pandas as pd
from pathlib import Path
from gee_sampler_optimized import export_batch_to_bigquery, wait_for_tasks_optimized
from datetime import datetime

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'
TEST_SPECIES_TAXON_ID = 'AngMaFaFbCx09400-00'  # Acacia pycnantha
TEST_SAMPLE_SIZE = 100  # Points to test (out of 2,853 total)

def main():
    print("="*80)
    print("ALPHAEARTH SINGLE SPECIES TEST WITH GEE + BIGQUERY")
    print("="*80)
    print(f"\nTest configuration:")
    print(f"  Species: Acacia pycnantha (Golden wattle)")
    print(f"  Taxon ID: {TEST_SPECIES_TAXON_ID}")
    print(f"  Sample size: {TEST_SAMPLE_SIZE} points (from 2,853 total)")
    print(f"  Target: treekipedia-476404:alphaearth.occ_embeddings_raw")
    print("="*80)

    # Load GBIF data
    print(f"\n📊 Loading GBIF data...")
    df = pd.read_parquet(GBIF_PARQUET)
    print(f"✅ Loaded {len(df):,} total occurrences")

    # Filter for test species
    species_df = df[df['taxon_id'] == TEST_SPECIES_TAXON_ID]
    print(f"✅ Found {len(species_df)} occurrences for {TEST_SPECIES_TAXON_ID}")

    # Sample down to test size
    if len(species_df) > TEST_SAMPLE_SIZE:
        species_df = species_df.sample(n=TEST_SAMPLE_SIZE, random_state=42)
        print(f"✅ Sampled down to {TEST_SAMPLE_SIZE} points for testing")

    # Convert to list of dicts for GEE
    occurrences = []
    for _, row in species_df.iterrows():
        occurrences.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'year': int(row['year']),
            'embedding_year': int(row['year'])  # Direct mapping (2017-2024)
        })

    # Show temporal distribution
    year_counts = species_df['year'].value_counts().sort_index()
    print(f"\n📅 Temporal distribution:")
    for year, count in year_counts.items():
        print(f"   {int(year)}: {count} occurrences")

    # Show spatial extent
    print(f"\n🗺️  Spatial extent:")
    print(f"   Lat range: {species_df['latitude'].min():.2f} to {species_df['latitude'].max():.2f}")
    print(f"   Lon range: {species_df['longitude'].min():.2f} to {species_df['longitude'].max():.2f}")

    # Confirm before proceeding
    print(f"\n{'='*80}")
    print("READY TO SUBMIT TO GEE")
    print(f"{'='*80}")
    print(f"\nThis will:")
    print(f"  1. Submit {len(occurrences)} points to Google Earth Engine")
    print(f"  2. Sample AlphaEarth 64-D embeddings at 10m resolution")
    print(f"  3. Export results to BigQuery table: alphaearth.occ_embeddings_raw")
    print(f"  4. Wait for completion (~1-5 minutes)")

    # Submit to GEE
    batch_id = f"{TEST_SPECIES_TAXON_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n🚀 Submitting batch: {batch_id}")

    try:
        task_ids = export_batch_to_bigquery(batch_id, occurrences)
        print(f"\n✅ Submitted {len(task_ids)} GEE task(s)")

        # Wait for completion
        print(f"\n⏳ Waiting for tasks to complete...")
        results = wait_for_tasks_optimized(task_ids, poll_interval=15)

        # Show results
        print(f"\n{'='*80}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*80}")
        print(f"\n✅ Completed tasks: {len(results['completed'])}")
        print(f"❌ Failed tasks: {len(results['failed'])}")

        if results['failed']:
            print(f"\nFailed tasks:")
            for task_id, error in results['failed']:
                print(f"  Task: {task_id}")
                print(f"  Error: {error[:200]}")

        if results['stats']:
            stats = results['stats']
            print(f"\n📊 Performance stats:")
            print(f"   Total points processed: {stats.get('total_points', 0):,}")
            print(f"   Total tasks completed: {stats.get('total_tasks', 0)}")
            print(f"   Elapsed time: {stats.get('elapsed_mins', 0):.2f} minutes")
            print(f"   Throughput: {stats.get('points_per_sec', 0):.2f} points/second")

        print(f"\n{'='*80}")
        print("NEXT STEPS")
        print(f"{'='*80}")
        print(f"\n1. Verify data in BigQuery:")
        print(f"   bq query --use_legacy_sql=false \\")
        print(f"     'SELECT COUNT(*) as total_rows, ")
        print(f"      COUNT(DISTINCT taxon_id) as unique_species ")
        print(f"      FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`'")
        print(f"\n2. Check embeddings structure:")
        print(f"   bq query --use_legacy_sql=false \\")
        print(f"     'SELECT taxon_id, emb_year, orig_year, latitude, longitude, ")
        print(f"      A01, A02, A03 FROM `treekipedia-476404.alphaearth.occ_embeddings_raw` ")
        print(f"      LIMIT 5'")
        print(f"\n3. If successful, run full 100 species extraction:")
        print(f"   python3 run_pilot.py")
        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nTroubleshooting:")
        print(f"  1. Check GEE authentication: earthengine authenticate")
        print(f"  2. Verify BigQuery dataset exists:")
        print(f"     bq ls treekipedia-476404:alphaearth")
        print(f"  3. Check GEE quota: https://code.earthengine.google.com/")


if __name__ == '__main__':
    main()
