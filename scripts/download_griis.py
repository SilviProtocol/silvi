#!/usr/bin/env python3
"""
GRIIS (Global Register of Introduced and Invasive Species) Data Downloader

Downloads all GRIIS checklists from GBIF and compiles them into a unified dataset
with invasive status by country for each species.

Output fields:
- scientific_name: Species scientific name
- kingdom: Taxonomic kingdom
- family: Taxonomic family
- country_code: ISO 2-letter country code
- country_name: Full country name
- establishment_means: alien/native/uncertain
- is_invasive: invasive/null/not invasive
- habitat: terrestrial/freshwater/marine/brackish
- occurrence_status: present/absent/etc.

Usage:
    python download_griis.py

Author: Djimo Serodio (djimo@silvi.earth)
"""

import os
import json
import requests
import zipfile
import io
import csv
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "griis_data"
GBIF_API = "https://api.gbif.org/v1"
GRIIS_IPT = "https://cloud.gbif.org/griis"

# Country code to name mapping (ISO 3166-1 alpha-2)
COUNTRY_NAMES = {}

def get_griis_datasets():
    """Fetch all GRIIS checklist datasets from GBIF API."""
    datasets = []
    offset = 0
    limit = 100

    print("Fetching GRIIS dataset list from GBIF...")

    while True:
        url = f"{GBIF_API}/dataset/search?q=GRIIS&type=CHECKLIST&limit={limit}&offset={offset}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        results = data.get('results', [])
        if not results:
            break

        for ds in results:
            title = ds.get('title', '')
            key = ds.get('key', '')

            # Extract country/region from title
            if ' - ' in title:
                region = title.split(' - ')[-1].strip()
            else:
                region = title.replace('GRIIS', '').replace('Global Register of Introduced and Invasive Species', '').strip()

            # Construct DwCA URL from the GRIIS IPT pattern
            # Format: https://cloud.gbif.org/griis/archive.do?r={resource_id}
            # We need to get the resource ID from the dataset details
            datasets.append({
                'key': key,
                'title': title,
                'region': region,
                'dwca_url': None  # Will be fetched later
            })

        offset += limit
        if offset >= data.get('count', 0):
            break

    print(f"Found {len(datasets)} GRIIS datasets")

    # Now fetch DwCA URLs for each dataset
    print("Fetching DwCA URLs for each dataset...")
    valid_datasets = []

    for i, ds in enumerate(datasets):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(datasets)}")

        try:
            detail_url = f"{GBIF_API}/dataset/{ds['key']}"
            resp = requests.get(detail_url, timeout=30)
            resp.raise_for_status()
            detail = resp.json()

            # Get DwCA endpoint
            endpoints = detail.get('endpoints', [])
            for ep in endpoints:
                if ep.get('type') == 'DWC_ARCHIVE':
                    ds['dwca_url'] = ep.get('url')
                    valid_datasets.append(ds)
                    break

            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"  Error fetching {ds['key']}: {e}")

    print(f"Found {len(valid_datasets)} datasets with DwCA URLs")
    return valid_datasets

def download_and_extract_dwca(dataset):
    """Download and extract Darwin Core Archive for a dataset."""
    try:
        response = requests.get(dataset['dwca_url'], timeout=60)
        response.raise_for_status()

        # Extract zip in memory
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            files = {}
            for name in zf.namelist():
                if name.endswith('.txt'):
                    content = zf.read(name).decode('utf-8', errors='replace')
                    files[name] = content
            return files
    except Exception as e:
        print(f"  Error downloading {dataset['region']}: {e}")
        return None

def parse_tsv(content):
    """Parse tab-separated content into list of dicts."""
    lines = content.strip().split('\n')
    if not lines:
        return []

    reader = csv.DictReader(lines, delimiter='\t')
    return list(reader)

def process_griis_archive(files, region):
    """Process extracted DwCA files into normalized records."""
    records = []

    # Parse core taxon file
    taxon_data = {}
    if 'taxon.txt' in files:
        for row in parse_tsv(files['taxon.txt']):
            taxon_id = row.get('id') or row.get('taxonID')
            if taxon_id:
                taxon_data[taxon_id] = {
                    'scientific_name': row.get('scientificName', ''),
                    'kingdom': row.get('kingdom', ''),
                    'phylum': row.get('phylum', ''),
                    'class': row.get('class', ''),
                    'order': row.get('order', ''),
                    'family': row.get('family', ''),
                    'taxon_rank': row.get('taxonRank', ''),
                    'taxonomic_status': row.get('taxonomicStatus', '')
                }

    # Parse distribution extension
    distribution_data = defaultdict(dict)
    if 'distribution.txt' in files:
        for row in parse_tsv(files['distribution.txt']):
            taxon_id = row.get('id') or row.get('coreid')
            if taxon_id:
                distribution_data[taxon_id] = {
                    'country_code': row.get('countryCode', ''),
                    'occurrence_status': row.get('occurrenceStatus', ''),
                    'establishment_means': row.get('establishmentMeans', '')
                }

    # Parse species profile extension
    profile_data = defaultdict(dict)
    if 'speciesprofile.txt' in files:
        for row in parse_tsv(files['speciesprofile.txt']):
            taxon_id = row.get('id') or row.get('coreid')
            if taxon_id:
                profile_data[taxon_id] = {
                    'is_invasive': row.get('isInvasive', ''),
                    'habitat': row.get('habitat', '')
                }

    # Combine data
    for taxon_id, taxon in taxon_data.items():
        # Skip synonyms - only use accepted names
        if taxon.get('taxonomic_status', '').upper() == 'SYNONYM':
            continue

        dist = distribution_data.get(taxon_id, {})
        profile = profile_data.get(taxon_id, {})

        record = {
            'scientific_name': taxon.get('scientific_name', ''),
            'kingdom': taxon.get('kingdom', ''),
            'phylum': taxon.get('phylum', ''),
            'class': taxon.get('class', ''),
            'order': taxon.get('order', ''),
            'family': taxon.get('family', ''),
            'taxon_rank': taxon.get('taxon_rank', ''),
            'country_code': dist.get('country_code', ''),
            'country_region': region,
            'occurrence_status': dist.get('occurrence_status', ''),
            'establishment_means': dist.get('establishment_means', ''),
            'is_invasive': profile.get('is_invasive', ''),
            'habitat': profile.get('habitat', '')
        }
        records.append(record)

    return records

def download_all_griis(max_workers=10):
    """Download and process all GRIIS datasets."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    datasets = get_griis_datasets()
    all_records = []
    failed = []

    print(f"\nDownloading {len(datasets)} GRIIS archives...")

    def process_dataset(ds):
        files = download_and_extract_dwca(ds)
        if files:
            records = process_griis_archive(files, ds['region'])
            return ds['region'], records
        return ds['region'], None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_dataset, ds): ds for ds in datasets}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            region, records = future.result()

            if records:
                all_records.extend(records)
                print(f"  [{completed}/{len(datasets)}] {region}: {len(records)} species")
            else:
                failed.append(region)
                print(f"  [{completed}/{len(datasets)}] {region}: FAILED")

    print(f"\nTotal records: {len(all_records)}")
    print(f"Failed downloads: {len(failed)}")

    return all_records, failed

def aggregate_by_species(records):
    """
    Aggregate GRIIS records by species, creating country lists for invasive status.

    Output structure per species:
    - scientific_name
    - kingdom, family
    - countries_alien: list of countries where species is alien/introduced
    - countries_invasive: list of countries where species is marked invasive
    - habitats: combined habitat types
    """
    species_data = defaultdict(lambda: {
        'scientific_name': '',
        'kingdom': '',
        'phylum': '',
        'class': '',
        'order': '',
        'family': '',
        'countries_alien': set(),
        'countries_invasive': set(),
        'habitats': set()
    })

    for rec in records:
        name = rec.get('scientific_name', '').strip()
        if not name:
            continue

        # Normalize scientific name (remove author, lowercase for matching)
        # Keep original for display
        species = species_data[name.lower()]
        species['scientific_name'] = name
        species['kingdom'] = rec.get('kingdom', '') or species['kingdom']
        species['phylum'] = rec.get('phylum', '') or species['phylum']
        species['class'] = rec.get('class', '') or species['class']
        species['order'] = rec.get('order', '') or species['order']
        species['family'] = rec.get('family', '') or species['family']

        country = (rec.get('country_region') or '').strip()
        if not country:
            country = (rec.get('country_code') or '').strip()

        # Track alien/introduced species
        establishment = (rec.get('establishment_means') or '').lower()
        if establishment in ('alien', 'introduced', 'naturalised', 'naturalized'):
            if country:
                species['countries_alien'].add(country)

        # Track invasive species
        invasive_status = (rec.get('is_invasive') or '').lower()
        if invasive_status == 'invasive':
            if country:
                species['countries_invasive'].add(country)

        # Track habitats
        habitat = rec.get('habitat', '')
        if habitat:
            for h in habitat.split('|'):
                h = h.strip()
                if h:
                    species['habitats'].add(h)

    # Convert sets to sorted lists
    result = []
    for name_lower, data in species_data.items():
        result.append({
            'scientific_name': data['scientific_name'],
            'scientific_name_lower': name_lower,
            'kingdom': data['kingdom'],
            'phylum': data['phylum'],
            'class': data['class'],
            'order': data['order'],
            'family': data['family'],
            'countries_alien': '; '.join(sorted(data['countries_alien'])),
            'countries_invasive': '; '.join(sorted(data['countries_invasive'])),
            'habitats': '; '.join(sorted(data['habitats'])),
            'num_countries_alien': len(data['countries_alien']),
            'num_countries_invasive': len(data['countries_invasive'])
        })

    return result

def save_outputs(records, aggregated):
    """Save processed data to files."""

    # Raw records (all country-species combinations)
    raw_file = OUTPUT_DIR / "griis_raw_records.csv"
    print(f"\nSaving raw records to {raw_file}...")

    fieldnames = ['scientific_name', 'kingdom', 'phylum', 'class', 'order', 'family',
                  'taxon_rank', 'country_code', 'country_region', 'occurrence_status',
                  'establishment_means', 'is_invasive', 'habitat']

    with open(raw_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"  Saved {len(records)} raw records")

    # Aggregated by species
    agg_file = OUTPUT_DIR / "griis_species_invasive_status.csv"
    print(f"Saving aggregated species data to {agg_file}...")

    agg_fieldnames = ['scientific_name', 'scientific_name_lower', 'kingdom', 'phylum',
                      'class', 'order', 'family', 'countries_alien', 'countries_invasive',
                      'habitats', 'num_countries_alien', 'num_countries_invasive']

    with open(agg_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=agg_fieldnames)
        writer.writeheader()
        writer.writerows(sorted(aggregated, key=lambda x: x['scientific_name_lower']))

    print(f"  Saved {len(aggregated)} unique species")

    # Summary statistics
    plants = [s for s in aggregated if s['kingdom'] == 'Plantae']
    invasive_plants = [s for s in plants if s['num_countries_invasive'] > 0]

    print(f"\n=== GRIIS Summary ===")
    print(f"Total unique species: {len(aggregated)}")
    print(f"  Plants (Plantae): {len(plants)}")
    print(f"  Plants marked invasive: {len(invasive_plants)}")
    print(f"  Multi-country invasives (>5 countries): {len([s for s in invasive_plants if s['num_countries_invasive'] > 5])}")

    return raw_file, agg_file

def main():
    """Main entry point."""
    print("=" * 60)
    print("GRIIS Data Downloader")
    print("=" * 60)

    # Download all datasets
    records, failed = download_all_griis(max_workers=15)

    if not records:
        print("No records downloaded!")
        return

    # Aggregate by species
    print("\nAggregating by species...")
    aggregated = aggregate_by_species(records)

    # Save outputs
    raw_file, agg_file = save_outputs(records, aggregated)

    print(f"\n=== Output Files ===")
    print(f"Raw records: {raw_file}")
    print(f"Aggregated species: {agg_file}")
    print("\nDone!")

if __name__ == "__main__":
    main()
