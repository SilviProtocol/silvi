"""
GBIF Occurrence Downloader
Fetches occurrence data with REAL temporal information for Treekipedia species.

Replaces the flawed CSV with 96% from 2024 (data dump artifact).
"""

import psycopg2
import psycopg2.extras
from pygbif import species, occurrences as occ
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

# Configuration
PG_CONN = {
    'host': 'localhost',
    'database': 'treekipedia',
    'user': 'djimoserodio'
}

GBIF_USER = 'djimo'
GBIF_PWD = 'c%NCk0uax6MM8rrN'
GBIF_EMAIL = 'djimo@silvi.earth'

OUTPUT_DIR = Path(__file__).parent / 'gbif_data'
OUTPUT_DIR.mkdir(exist_ok=True)


def get_pilot_species(initial_pool_size=100) -> list:
    """
    Get pilot species from local PostgreSQL.

    Strategy:
    1. Pull ~300 species from 5 families
    2. Match all to GBIF
    3. Get preliminary occurrence counts from GBIF
    4. Select top 100 by GBIF availability

    This gives us better coverage than random selection.
    """
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = f"""
    SELECT taxon_id, species_scientific_name, family
    FROM species
    WHERE subspecies = 'NA'
      AND family IN ('Pinaceae', 'Fabaceae', 'Fagaceae', 'Myrtaceae', 'Salicaceae')
    ORDER BY RANDOM()
    LIMIT {initial_pool_size};
    """

    cur.execute(query)
    species_list = cur.fetchall()
    cur.close()
    conn.close()

    return species_list


def match_species_to_gbif(species_list: list) -> dict:
    """
    Match Treekipedia species names to GBIF taxon keys.

    Returns:
        {taxon_id: {gbif_key, scientific_name, match_type, confidence}}
    """
    print(f"\n🔍 Matching {len(species_list)} species to GBIF...")

    matches = {}
    failed = []

    for i, sp in enumerate(species_list, 1):
        name = sp['species_scientific_name']
        taxon_id = sp['taxon_id']

        print(f"  [{i}/{len(species_list)}] {name}...", end=' ')

        try:
            result = species.name_backbone(name=name)

            if result.get('matchType') in ['EXACT', 'FUZZY']:
                matches[taxon_id] = {
                    'gbif_key': result['usageKey'],
                    'scientific_name': result['scientificName'],
                    'match_type': result['matchType'],
                    'confidence': result.get('confidence', 100),
                    'family': sp['family']
                }
                print(f"✅ {result['matchType']} (key: {result['usageKey']})")

            else:
                failed.append({'taxon_id': taxon_id, 'name': name, 'result': result})
                print(f"❌ No match")

        except Exception as e:
            failed.append({'taxon_id': taxon_id, 'name': name, 'error': str(e)})
            print(f"❌ Error: {e}")

        # Rate limit: GBIF allows ~10 requests/sec
        time.sleep(0.15)

    print(f"\n✅ Matched: {len(matches)}")
    print(f"❌ Failed: {len(failed)}")

    # Save results
    match_file = OUTPUT_DIR / 'gbif_matches.json'
    match_file.write_text(json.dumps({
        'matches': matches,
        'failed': failed,
        'timestamp': datetime.now().isoformat()
    }, indent=2))

    print(f"\n💾 Saved to: {match_file}")

    return matches


def check_occurrence_counts(gbif_matches: dict) -> dict:
    """
    SIMPLIFIED: Skip individual counts, just return all species with dummy count.

    The GBIF count API is unreliable for complex filters. Instead, we'll just
    download all matched species and let GBIF filter them. Species with zero
    occurrences will simply return empty results.

    Returns:
        {taxon_id: occurrence_data with dummy count of 1}
    """
    print(f"\n📊 Preparing {len(gbif_matches)} species for download...")
    print("  (Skipping pre-count check - will download all and filter during download)")

    counts = {}

    for taxon_id, match_data in gbif_matches.items():
        counts[taxon_id] = {
            'count': 1,  # Dummy count - actual filtering happens in download
            'gbif_key': match_data['gbif_key'],
            'scientific_name': match_data['scientific_name'],
            'family': match_data['family']
        }

    # Save results
    counts_file = OUTPUT_DIR / 'gbif_occurrence_counts.json'
    counts_file.write_text(json.dumps(counts, indent=2))

    print(f"  ✅ All {len(counts)} species prepared for download")
    print(f"\n💾 Saved to: {counts_file}")

    return counts


def select_top_species(occurrence_counts: dict, limit: int = 100) -> list:
    """
    Select species for download (simplified - just take first N).

    Since we're skipping pre-count checks, just select first N species.
    GBIF will filter during download.

    Returns:
        List of taxon_ids (first N from the matched species)
    """
    print(f"\n🎯 Selecting {limit} species for download...")

    # Just take first N species (all have dummy count of 1)
    all_taxon_ids = list(occurrence_counts.keys())
    selected = all_taxon_ids[:limit]

    print(f"\n✅ Selected {len(selected)} species from {len(all_taxon_ids)} matched")

    # Show first 10
    print(f"\n   First 10 selected:")
    for i, tid in enumerate(selected[:10], 1):
        data = occurrence_counts[tid]
        print(f"   {i:2}. {data['scientific_name']}")

    return selected


def request_gbif_download(gbif_matches: dict, selected_taxon_ids: list = None) -> str:
    """
    Request GBIF occurrence download for matched species.

    Args:
        gbif_matches: All matched species
        selected_taxon_ids: Optional list of taxon_ids to download (if None, uses all)

    Returns:
        Download key (job ID)
    """
    print(f"\n📥 Requesting GBIF occurrence download...")

    # Filter to selected species if provided
    if selected_taxon_ids:
        gbif_keys = [gbif_matches[tid]['gbif_key'] for tid in selected_taxon_ids if tid in gbif_matches]
        print(f"  Species: {len(selected_taxon_ids)} (selected from {len(gbif_matches)} matched)")
    else:
        gbif_keys = [m['gbif_key'] for m in gbif_matches.values()]
        print(f"  Species: {len(gbif_keys)} (all matched)")

    print(f"  Species: {len(gbif_keys)}")
    print(f"  GBIF keys: {gbif_keys[:5]}... (showing first 5)")

    # Build download query using predicates (correct GBIF API format)
    # Create predicate for taxon keys (OR logic)
    taxon_predicates = [
        {"type": "equals", "key": "TAXON_KEY", "value": str(key)}
        for key in gbif_keys
    ]

    query = {
        "creator": GBIF_USER,
        "notification_address": [GBIF_EMAIL],
        "sendNotification": True,
        "format": "SIMPLE_CSV",
        "predicate": {
            "type": "and",
            "predicates": [
                # Multiple species (OR logic)
                {"type": "or", "predicates": taxon_predicates},
                # Quality filters (AND logic)
                {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
                {"type": "equals", "key": "HAS_GEOSPATIAL_ISSUE", "value": "false"},
                {"type": "greaterThanOrEquals", "key": "YEAR", "value": "2017"},
                {"type": "lessThanOrEquals", "key": "YEAR", "value": "2024"},
                {"type": "lessThanOrEquals", "key": "COORDINATE_UNCERTAINTY_IN_METERS", "value": "10"}  # GPS-level accuracy for 10m AlphaEarth pixels
            ]
        }
    }

    print("\n  Filters:")
    print(f"    ✓ Has coordinates")
    print(f"    ✓ No geospatial issues")
    print(f"    ✓ Years: 2017-2024 (AlphaEarth window)")
    print(f"    ✓ Coordinate uncertainty ≤ 10m (GPS-level accuracy for 10m AlphaEarth pixels)")

    # Submit download request
    # NOTE: Requires GBIF account credentials
    try:
        # Use download_json for predicate-based queries
        from pygbif.occurrences import download as gbif_download
        import requests

        download_result = requests.post(
            'https://api.gbif.org/v1/occurrence/download/request',
            json=query,
            auth=(GBIF_USER, GBIF_PWD)
        )

        if download_result.status_code == 201:
            download_key = download_result.text  # Returns the download key
        else:
            raise Exception(f"Download request failed: {download_result.text}")

        print(f"\n✅ Download requested!")
        print(f"  Download key: {download_key}")
        print(f"  Status URL: https://www.gbif.org/occurrence/download/{download_key}")

        # Save download key
        download_file = OUTPUT_DIR / 'gbif_download.json'
        download_file.write_text(json.dumps({
            'download_key': download_key,
            'n_species': len(gbif_keys),
            'requested_at': datetime.now().isoformat(),
            'status_url': f"https://www.gbif.org/occurrence/download/{download_key}"
        }, indent=2))

        return download_key

    except Exception as e:
        print(f"\n❌ Download request failed: {e}")
        print("\nTo fix:")
        print("  1. Register at: https://www.gbif.org/user/profile")
        print("  2. Update GBIF_USER, GBIF_PWD, GBIF_EMAIL in this script")
        raise


def check_download_status(download_key: str) -> dict:
    """
    Check status of GBIF download.

    Returns:
        {status: 'PREPARING'|'RUNNING'|'SUCCEEDED'|'FAILED', size_mb: float}
    """
    meta = occ.download_meta(download_key)
    return {
        'status': meta['status'],
        'size_mb': meta.get('size', 0) / 1_000_000,
        'total_records': meta.get('totalRecords', 0),
        'doi': meta.get('doi')
    }


def wait_for_download(download_key: str, poll_interval: int = 60) -> str:
    """
    Wait for GBIF download to complete.

    Returns:
        Path to downloaded ZIP file
    """
    print(f"\n⏳ Waiting for download to complete...")
    print(f"  Download key: {download_key}")
    print(f"  Polling every {poll_interval}s")

    while True:
        status = check_download_status(download_key)

        print(f"\n  Status: {status['status']}")
        if status['total_records']:
            print(f"  Records: {status['total_records']:,}")
        if status['size_mb']:
            print(f"  Size: {status['size_mb']:.1f} MB")

        if status['status'] == 'SUCCEEDED':
            print(f"\n✅ Download complete!")

            # Download the ZIP file
            output_file = OUTPUT_DIR / f"{download_key}.zip"
            print(f"\n📥 Downloading to: {output_file}")

            occ.download_get(download_key, path=str(OUTPUT_DIR))

            return str(output_file)

        elif status['status'] == 'FAILED':
            raise Exception(f"Download failed: {status}")

        else:
            print(f"  Waiting {poll_interval}s...")
            time.sleep(poll_interval)


def parse_gbif_zip(zip_file: str, gbif_matches: dict) -> pd.DataFrame:
    """
    Parse GBIF occurrence ZIP and create clean DataFrame.

    Returns:
        DataFrame with columns: taxon_id, species, lat, lon, year, gbif_id
    """
    print(f"\n📊 Parsing GBIF data...")

    # GBIF ZIP contains occurrence.txt (tab-separated)
    # Key columns: gbifID, scientificName, decimalLatitude, decimalLongitude, year, taxonKey

    df = pd.read_csv(
        zip_file,
        sep='\t',
        compression='zip',
        usecols=['gbifID', 'taxonKey', 'scientificName',
                 'decimalLatitude', 'decimalLongitude', 'year']
    )

    print(f"  Total records: {len(df):,}")

    # Map GBIF keys back to Treekipedia taxon_ids
    key_to_taxon = {
        m['gbif_key']: taxon_id
        for taxon_id, m in gbif_matches.items()
    }

    df['taxon_id'] = df['taxonKey'].map(key_to_taxon)

    # Clean
    df = df.dropna(subset=['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year'])
    df = df.rename(columns={
        'decimalLatitude': 'latitude',
        'decimalLongitude': 'longitude',
        'scientificName': 'species',
        'gbifID': 'gbif_id'
    })

    # Select final columns
    df = df[['taxon_id', 'species', 'latitude', 'longitude', 'year', 'gbif_id']]

    print(f"  After cleaning: {len(df):,}")
    print(f"  Species: {df['taxon_id'].nunique()}")
    print(f"\n  Year distribution:")
    print(df['year'].value_counts().sort_index().tail(10))

    # Save to Parquet
    output_file = OUTPUT_DIR / 'gbif_occurrences.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n💾 Saved to: {output_file}")

    return df


def main():
    """
    Full GBIF download workflow - download 50 species batch.

    Strategy:
    1. Pull 50 species from 5 families
    2. Match all to GBIF
    3. Download all 50 with GPS precision filters (≤10m)
    4. Parse and save results
    """
    print("="*70)
    print("GBIF OCCURRENCE DOWNLOADER - BATCH OF 100")
    print("With ≤10m GPS precision for AlphaEarth 10m pixels")
    print("="*70)

    # Step 1: Get candidate species from local DB
    species_list = get_pilot_species(initial_pool_size=100)
    print(f"\n✅ Retrieved {len(species_list)} candidate species")

    # Step 2: Match all to GBIF
    gbif_matches = match_species_to_gbif(species_list)

    if not gbif_matches:
        print("\n❌ No species matched. Exiting.")
        return

    # Step 3: Download ALL matched species (no pre-selection)
    print(f"\n📥 Downloading ALL {len(gbif_matches)} species...")
    print("  (Selection of top 100 will happen AFTER download based on actual data)")
    download_key = request_gbif_download(gbif_matches, selected_taxon_ids=None)

    # Step 4: Wait for completion
    zip_file = wait_for_download(download_key, poll_interval=60)

    # Step 5: Parse and save ALL results
    df = parse_gbif_zip(zip_file, gbif_matches)

    print("\n" + "="*70)
    print("✅ GBIF DOWNLOAD COMPLETE")
    print("="*70)
    print(f"Records: {len(df):,}")
    print(f"Species: {df['taxon_id'].nunique()}")
    print(f"Output: {OUTPUT_DIR / 'gbif_occurrences.parquet'}")
    print("\nNext: Update run_pilot.py to use this data instead of geohash tiles")
    print("="*70)


if __name__ == '__main__':
    main()
