"""
AlphaEarth Pilot Orchestrator - PRODUCTION VERSION
Reads occurrence data from GBIF Parquet and orchestrates GEE embedding extraction.

FEATURES:
- Automatic retry on failures (3 attempts per species)
- Checkpoint/resume system (survives crashes/interruptions)
- GEE quota monitoring and backoff
- Network error handling
- Progress tracking and ETA estimation
- Can safely Ctrl+C and resume later

Architecture:
  GBIF Parquet (local) → Python Orchestrator → GEE → BigQuery → Python → PostgreSQL (prototypes)

Following: treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md
"""

import pandas as pd
from pathlib import Path
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from gee_sampler_FINAL import export_batch_to_bigquery, wait_for_tasks
import sys

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'
CHECKPOINT_FILE = Path(__file__).parent / 'checkpoints.json'
MAX_RETRIES = 3  # Retry failed species up to 3 times
RETRY_DELAY = 60  # Wait 60 seconds before retrying


def get_embedding_year(occurrence_year: Optional[int]) -> int:
    """
    Temporal alignment logic per Builder's Guide Section 2.2.

    Since GBIF download filters to 2017-2024, we can use exact years.
    No clamping needed - all occurrences match AlphaEarth's temporal window.

    Args:
        occurrence_year: Year of occurrence (2017-2024 from GBIF)

    Returns:
        Embedding year to use (same as occurrence year)
    """
    if occurrence_year is None:
        return 2024  # Default to latest (should not happen with GBIF data)

    # With GBIF 2017-2024 filter, this is just a direct pass-through
    return occurrence_year


def load_gbif_data() -> pd.DataFrame:
    """
    Load GBIF occurrence data from parquet file.

    Returns:
        DataFrame with columns: taxon_id, species, family, latitude, longitude, year, gbif_id
    """
    if not GBIF_PARQUET.exists():
        raise FileNotFoundError(f"GBIF parquet file not found: {GBIF_PARQUET}")

    return pd.read_parquet(GBIF_PARQUET)


def load_checkpoints() -> Dict:
    """Load orchestrator checkpoints from JSON file."""
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {
        'pilot_start': datetime.now().isoformat(),
        'completed': [],
        'failed': [],
        'in_progress': [],
        'retry_queue': []  # Species that need retry
    }


def save_checkpoints(ckpt: Dict):
    """Save checkpoints to JSON file."""
    CHECKPOINT_FILE.write_text(json.dumps(ckpt, indent=2))


def select_pilot_species(df: pd.DataFrame) -> List[Dict]:
    """
    Get list of pilot species from GBIF DataFrame.

    Args:
        df: GBIF occurrence DataFrame

    Returns:
        List of {taxon_id, species_scientific_name, family, occurrence_count}
    """
    # Count occurrences per species
    species_counts = df.groupby(['taxon_id', 'species', 'family']).size().reset_index(name='occurrence_count')
    species_counts = species_counts.sort_values('occurrence_count', ascending=False)

    # Convert to list of dicts
    species_list = []
    for _, row in species_counts.iterrows():
        species_list.append({
            'taxon_id': row['taxon_id'],
            'species_scientific_name': row['species'],
            'family': row['family'],
            'occurrence_count': row['occurrence_count']
        })

    return species_list


def get_occurrences_for_species(
    df: pd.DataFrame,
    taxon_id: str
) -> List[Dict]:
    """
    Fetch occurrence points for a species from GBIF DataFrame.

    Gets ALL occurrences for maximum accuracy - no sampling limit.
    We're already working with filtered high-quality GBIF data (≤10m GPS precision, 2017-2024).

    Args:
        df: GBIF occurrence DataFrame
        taxon_id: Species taxon ID

    Returns:
        List of {taxon_id, latitude, longitude, year, embedding_year}
    """
    # Filter for this species - GET ALL OCCURRENCES (no sampling)
    species_df = df[df['taxon_id'] == taxon_id].copy()

    # Convert to list of dicts
    occurrences = []
    for _, row in species_df.iterrows():
        occurrences.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'year': int(row['year']),
            'embedding_year': get_embedding_year(int(row['year']))
        })

    return occurrences


def process_species(species: Dict, df: pd.DataFrame, ckpt: Dict, retry_count: int = 0) -> bool:
    """
    Process a single species: extract occurrences and submit GEE tasks.

    Args:
        species: Species dict with taxon_id, species_scientific_name, etc.
        df: GBIF occurrence DataFrame
        ckpt: Checkpoints dict
        retry_count: Current retry attempt (0 = first attempt)

    Returns:
        True if successful, False if failed
    """
    taxon_id = species['taxon_id']
    name = species['species_scientific_name']
    occ_count = species['occurrence_count']

    print(f"\n{'='*70}")
    print(f"Processing: {name} ({taxon_id})")
    print(f"Occurrence count: {occ_count:,}")
    if retry_count > 0:
        print(f"🔄 Retry attempt {retry_count}/{MAX_RETRIES}")
    print(f"{'='*70}")

    # Check if already completed
    if any(c['taxon_id'] == taxon_id for c in ckpt['completed']):
        print("  ✅ Already completed, skipping")
        return True

    # Fetch occurrences from GBIF DataFrame
    print("  📊 Fetching occurrences from GBIF data...")

    try:
        occurrences = get_occurrences_for_species(df, taxon_id)  # Get ALL occurrences (no limit)
    except Exception as e:
        print(f"  ❌ Error fetching occurrences: {e}")
        if retry_count < MAX_RETRIES:
            print(f"  ⏰ Will retry after {RETRY_DELAY}s...")
            return False  # Trigger retry
        return False

    if not occurrences:
        print(f"  ⚠️  No occurrences found, skipping")
        return False

    print(f"  ✅ Found {len(occurrences):,} occurrence points")

    # Submit to GEE
    batch_id = f"{taxon_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  🚀 Submitting to GEE (batch: {batch_id})...")

    try:
        task_ids = export_batch_to_bigquery(batch_id, occurrences)

        # Track as in-progress
        ckpt['in_progress'].append({
            'taxon_id': taxon_id,
            'species': name,
            'batch_id': batch_id,
            'n_occurrences': len(occurrences),
            'task_ids': task_ids,
            'retry_count': retry_count,
            'started_at': datetime.now().isoformat()
        })
        save_checkpoints(ckpt)

        # Wait for tasks to complete
        print(f"\n  ⏳ Waiting for {len(task_ids)} GEE tasks...")
        results = wait_for_tasks(task_ids, poll_interval=30)

        # Update checkpoints
        if results['failed']:
            print(f"\n  ❌ {len(results['failed'])} tasks failed")

            # Check if should retry
            if retry_count < MAX_RETRIES:
                print(f"  🔄 Will retry (attempt {retry_count + 1}/{MAX_RETRIES})")
                ckpt['retry_queue'].append({
                    'taxon_id': taxon_id,
                    'species': name,
                    'retry_count': retry_count + 1,
                    'last_error': results['failed'][0][1] if results['failed'] else 'Unknown error',
                    'failed_at': datetime.now().isoformat()
                })
            else:
                print(f"  ❌ Max retries reached, marking as failed")
                ckpt['failed'].append({
                    'taxon_id': taxon_id,
                    'species': name,
                    'batch_id': batch_id,
                    'failed_tasks': results['failed'],
                    'retry_count': retry_count,
                    'failed_at': datetime.now().isoformat()
                })

            # Remove from in_progress
            ckpt['in_progress'] = [
                x for x in ckpt['in_progress'] if x['taxon_id'] != taxon_id
            ]
            save_checkpoints(ckpt)
            return False

        else:
            print(f"\n  ✅ All tasks completed successfully!")
            ckpt['completed'].append({
                'taxon_id': taxon_id,
                'species': name,
                'batch_id': batch_id,
                'n_occurrences': len(occurrences),
                'n_tasks': len(task_ids),
                'retry_count': retry_count,
                'completed_at': datetime.now().isoformat()
            })
            # Remove from in_progress and retry_queue
            ckpt['in_progress'] = [
                x for x in ckpt['in_progress'] if x['taxon_id'] != taxon_id
            ]
            ckpt['retry_queue'] = [
                x for x in ckpt['retry_queue'] if x['taxon_id'] != taxon_id
            ]
            save_checkpoints(ckpt)
            return True

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user! Saving checkpoint...")
        save_checkpoints(ckpt)
        print(f"✅ Progress saved. You can resume by running this script again.")
        sys.exit(0)

    except Exception as e:
        print(f"\n  ❌ Error: {e}")

        # Check if should retry
        if retry_count < MAX_RETRIES:
            print(f"  🔄 Will retry (attempt {retry_count + 1}/{MAX_RETRIES})")
            ckpt['retry_queue'].append({
                'taxon_id': taxon_id,
                'species': name,
                'retry_count': retry_count + 1,
                'last_error': str(e),
                'failed_at': datetime.now().isoformat()
            })
        else:
            print(f"  ❌ Max retries reached, marking as failed")
            ckpt['failed'].append({
                'taxon_id': taxon_id,
                'species': name,
                'error': str(e),
                'retry_count': retry_count,
                'failed_at': datetime.now().isoformat()
            })

        # Remove from in_progress
        ckpt['in_progress'] = [
            x for x in ckpt['in_progress'] if x['taxon_id'] != taxon_id
        ]
        save_checkpoints(ckpt)
        return False


def print_progress_summary(ckpt: Dict, total_species: int, start_time: datetime):
    """Print progress summary with ETA."""
    completed = len(ckpt['completed'])
    failed = len(ckpt['failed'])
    retry_queue = len(ckpt['retry_queue'])
    remaining = total_species - completed - failed

    elapsed = datetime.now() - start_time
    if completed > 0:
        avg_time_per_species = elapsed / completed
        eta_seconds = avg_time_per_species.total_seconds() * remaining
        eta = timedelta(seconds=int(eta_seconds))
    else:
        eta = "calculating..."

    print(f"\n{'='*70}")
    print(f"PROGRESS SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Completed: {completed}/{total_species} ({completed/total_species*100:.1f}%)")
    print(f"❌ Failed: {failed}/{total_species}")
    print(f"🔄 In retry queue: {retry_queue}")
    print(f"⏳ Remaining: {remaining}/{total_species}")
    print(f"⏱️  Elapsed: {elapsed}")
    print(f"🕐 ETA: {eta}")
    print(f"{'='*70}\n")


def main():
    """Run the 100-species pilot extraction."""
    start_time = datetime.now()

    print("="*70)
    print("ALPHAEARTH EMBEDDINGS - 100 SPECIES PILOT (PRODUCTION)")
    print("="*70)
    print(f"\nFeatures:")
    print("  ✓ Auto-retry on failures (up to 3 attempts)")
    print("  ✓ Checkpoint/resume system (survives crashes)")
    print("  ✓ Progress tracking with ETA")
    print("  ✓ Can safely Ctrl+C and resume later")
    print(f"\nArchitecture:")
    print("  GBIF Parquet (local) → Python → GEE → BigQuery")
    print(f"\nGBIF data: {GBIF_PARQUET}")
    print(f"Checkpoint file: {CHECKPOINT_FILE}")
    print("="*70)

    # Load GBIF data
    print(f"\n📊 Loading GBIF occurrence data...")
    try:
        df = load_gbif_data()
        print(f"✅ Loaded {len(df):,} occurrences from {df['taxon_id'].nunique()} species")
    except Exception as e:
        print(f"❌ Error loading GBIF data: {e}")
        return

    # Load checkpoints
    ckpt = load_checkpoints()
    print(f"\nCheckpoint status:")
    print(f"  ✅ Completed: {len(ckpt['completed'])}")
    print(f"  ❌ Failed: {len(ckpt['failed'])}")
    print(f"  ⏳ In progress: {len(ckpt['in_progress'])}")
    print(f"  🔄 Retry queue: {len(ckpt.get('retry_queue', []))}")

    # Clear stale in_progress (from previous crashes)
    if ckpt['in_progress']:
        print(f"\n⚠️  Found {len(ckpt['in_progress'])} stale in-progress entries (from previous run)")
        print("   Moving to retry queue...")
        for item in ckpt['in_progress']:
            if not any(r['taxon_id'] == item['taxon_id'] for r in ckpt.get('retry_queue', [])):
                ckpt.setdefault('retry_queue', []).append({
                    'taxon_id': item['taxon_id'],
                    'species': item['species'],
                    'retry_count': item.get('retry_count', 0),
                    'last_error': 'Stale in-progress from previous run',
                    'failed_at': datetime.now().isoformat()
                })
        ckpt['in_progress'] = []
        save_checkpoints(ckpt)

    # Get species list
    print(f"\n📋 Preparing species list...")
    species_list = select_pilot_species(df)
    total_species = len(species_list)
    print(f"✅ Ready to process {total_species} species")

    # Process each species
    try:
        for i, species in enumerate(species_list, 1):
            print(f"\n\n[{i}/{total_species}] ", end='')

            # Skip if already completed
            if any(c['taxon_id'] == species['taxon_id'] for c in ckpt['completed']):
                print(f"✅ {species['species_scientific_name']} already completed, skipping")
                continue

            # Process species
            process_species(species, df, ckpt)

            # Print progress summary every 5 species
            if i % 5 == 0:
                print_progress_summary(ckpt, total_species, start_time)

        # Process retry queue
        if ckpt.get('retry_queue'):
            print(f"\n\n{'='*70}")
            print(f"PROCESSING RETRY QUEUE ({len(ckpt['retry_queue'])} species)")
            print(f"{'='*70}")

            retry_list = list(ckpt['retry_queue'])
            ckpt['retry_queue'] = []
            save_checkpoints(ckpt)

            for retry_item in retry_list:
                print(f"\n⏰ Waiting {RETRY_DELAY}s before retry...")
                time.sleep(RETRY_DELAY)

                # Find species info
                species = next((s for s in species_list if s['taxon_id'] == retry_item['taxon_id']), None)
                if species:
                    process_species(species, df, ckpt, retry_count=retry_item['retry_count'])

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user! Saving checkpoint...")
        save_checkpoints(ckpt)
        print(f"✅ Progress saved to: {CHECKPOINT_FILE}")
        print(f"   You can resume by running this script again.")
        return

    # Final summary
    elapsed = datetime.now() - start_time
    print("\n\n" + "="*70)
    print("PILOT COMPLETE")
    print("="*70)
    print(f"✅ Success: {len(ckpt['completed'])}/{total_species} ({len(ckpt['completed'])/total_species*100:.1f}%)")
    print(f"❌ Failed: {len(ckpt['failed'])}/{total_species}")
    print(f"⏱️  Total time: {elapsed}")
    print(f"\nCheckpoint saved to: {CHECKPOINT_FILE}")

    if ckpt['failed']:
        print(f"\n⚠️  Failed species:")
        for fail in ckpt['failed']:
            print(f"   - {fail['species']} ({fail['taxon_id']})")
            if 'last_error' in fail:
                print(f"     Error: {fail['last_error'][:80]}")

    print("="*70)


if __name__ == '__main__':
    main()
