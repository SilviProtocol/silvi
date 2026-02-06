"""
AlphaEarth Pilot Orchestrator
Reads occurrence data from GBIF Parquet and orchestrates GEE embedding extraction.

Architecture (per user specification):
  GBIF Parquet (local) → Python Orchestrator → GEE → BigQuery → Python → PostgreSQL (prototypes)

Following: treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict, Optional
from gee_sampler import export_batch_to_bigquery, wait_for_tasks

# Configuration
GBIF_PARQUET = Path(__file__).parent / 'gbif_data' / 'gbif_occurrences_top100_gps.parquet'
CHECKPOINT_FILE = Path(__file__).parent / 'checkpoints.json'


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
        'in_progress': []
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
    taxon_id: str,
    max_points: int = 5000
) -> List[Dict]:
    """
    Fetch occurrence points for a species from GBIF DataFrame.

    Args:
        df: GBIF occurrence DataFrame
        taxon_id: Species taxon ID
        max_points: Maximum occurrences to sample (to avoid GEE limits)

    Returns:
        List of {taxon_id, latitude, longitude, year, embedding_year}
    """
    # Filter for this species
    species_df = df[df['taxon_id'] == taxon_id].copy()

    # Sample if too many occurrences
    if len(species_df) > max_points:
        species_df = species_df.sample(n=max_points, random_state=42)

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


def process_species(species: Dict, df: pd.DataFrame, ckpt: Dict) -> bool:
    """
    Process a single species: extract occurrences and submit GEE tasks.

    Args:
        species: Species dict with taxon_id, species_scientific_name, etc.
        df: GBIF occurrence DataFrame
        ckpt: Checkpoints dict

    Returns:
        True if successful, False if failed
    """
    taxon_id = species['taxon_id']
    name = species['species_scientific_name']
    occ_count = species['occurrence_count']

    print(f"\n{'='*70}")
    print(f"Processing: {name} ({taxon_id})")
    print(f"Occurrence count: {occ_count:,}")
    print(f"{'='*70}")

    # Check if already completed
    if any(c['taxon_id'] == taxon_id for c in ckpt['completed']):
        print("  ✅ Already completed, skipping")
        return True

    # Fetch occurrences from GBIF DataFrame
    print("  📊 Fetching occurrences from GBIF data...")
    occurrences = get_occurrences_for_species(df, taxon_id, max_points=5000)

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
            'started_at': datetime.now().isoformat()
        })
        save_checkpoints(ckpt)

        # Wait for tasks to complete
        print(f"\n  ⏳ Waiting for {len(task_ids)} GEE tasks...")
        results = wait_for_tasks(task_ids, poll_interval=30)

        # Update checkpoints
        if results['failed']:
            print(f"\n  ❌ {len(results['failed'])} tasks failed")
            ckpt['failed'].append({
                'taxon_id': taxon_id,
                'species': name,
                'batch_id': batch_id,
                'failed_tasks': results['failed'],
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
                'completed_at': datetime.now().isoformat()
            })
            # Remove from in_progress
            ckpt['in_progress'] = [
                x for x in ckpt['in_progress'] if x['taxon_id'] != taxon_id
            ]
            save_checkpoints(ckpt)
            return True

    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        ckpt['failed'].append({
            'taxon_id': taxon_id,
            'species': name,
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        })
        save_checkpoints(ckpt)
        return False


def main():
    """Run the 100-species pilot extraction."""
    print("="*70)
    print("ALPHAEARTH EMBEDDINGS - 100 SPECIES PILOT")
    print("="*70)
    print(f"\nArchitecture:")
    print("  GBIF Parquet (local) → Python → GEE → BigQuery")
    print(f"\nGBIF data: {GBIF_PARQUET}")
    print(f"Checkpoint file: {CHECKPOINT_FILE}")
    print("="*70)

    # Load GBIF data
    print(f"\n📊 Loading GBIF occurrence data...")
    df = load_gbif_data()
    print(f"✅ Loaded {len(df):,} occurrences from {df['taxon_id'].nunique()} species")

    # Load checkpoints
    ckpt = load_checkpoints()
    print(f"\nCheckpoint status:")
    print(f"  Completed: {len(ckpt['completed'])}")
    print(f"  Failed: {len(ckpt['failed'])}")
    print(f"  In progress: {len(ckpt['in_progress'])}")

    # Get species list
    print(f"\n📋 Preparing species list...")
    species_list = select_pilot_species(df)
    print(f"✅ Ready to process {len(species_list)} species")

    # Process each species
    success_count = 0
    for i, species in enumerate(species_list, 1):
        print(f"\n\n[{i}/{len(species_list)}] ", end='')

        if process_species(species, df, ckpt):
            success_count += 1

        # Save progress
        save_checkpoints(ckpt)

    # Final summary
    print("\n\n" + "="*70)
    print("PILOT COMPLETE")
    print("="*70)
    print(f"Success: {success_count}/{len(species_list)}")
    print(f"Failed: {len(species_list) - success_count}")
    print(f"\nCheckpoint saved to: {CHECKPOINT_FILE}")
    print("="*70)


if __name__ == '__main__':
    main()
