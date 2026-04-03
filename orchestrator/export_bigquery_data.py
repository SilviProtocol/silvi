#!/usr/bin/env python3
"""
Export BigQuery tables to local Parquet files.

This script exports AlphaEarth embedding data from BigQuery to local files
for migration to a new Google Cloud account.

Usage:
    python export_bigquery_data.py                    # Export all tables
    python export_bigquery_data.py --table v2        # Export specific table
    python export_bigquery_data.py --chunk-size 100000  # Custom chunk size

Author: Treekipedia Team
Created: January 2026
"""

import pandas as pd
import pandas_gbq
import argparse
import os
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT = 'treekipedia-476404'
DATASET = 'alphaearth'
OUTPUT_DIR = Path(__file__).parent / 'bigquery_exports'

# Tables to export (name, approximate rows)
TABLES = {
    'v2': ('occ_embeddings_hansen_v2', 1691022),
    'v3': ('occ_embeddings_hansen_elev_v3', 1153976),
    'elev': ('occ_elevation_backfill', 1526000),
    'raw': ('occ_embeddings_raw', 196809),
    'clean': ('occ_embeddings_clean', 45677),
}


def export_table(table_name: str, chunk_size: int = 200000, start_offset: int = 0):
    """
    Export a BigQuery table to local Parquet files.

    Args:
        table_name: Name of the table in BigQuery
        chunk_size: Number of rows per chunk
        start_offset: Starting row offset (for resuming)
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get total row count
    count_query = f"SELECT COUNT(*) as cnt FROM `{PROJECT}.{DATASET}.{table_name}`"
    count_df = pandas_gbq.read_gbq(count_query, project_id=PROJECT, progress_bar_type=None)
    total_rows = count_df['cnt'].iloc[0]

    print(f"\n{'='*60}")
    print(f"EXPORTING: {table_name}")
    print(f"{'='*60}")
    print(f"Total rows: {total_rows:,}")
    print(f"Chunk size: {chunk_size:,}")
    print(f"Estimated chunks: {(total_rows - start_offset) // chunk_size + 1}")

    offset = start_offset
    chunk_num = start_offset // chunk_size
    all_files = []

    while offset < total_rows:
        # Query with LIMIT and OFFSET
        query = f"""
        SELECT *
        FROM `{PROJECT}.{DATASET}.{table_name}`
        ORDER BY taxon_id, latitude, longitude
        LIMIT {chunk_size}
        OFFSET {offset}
        """

        print(f"\n  Chunk {chunk_num}: rows {offset:,} to {min(offset + chunk_size, total_rows):,}...")

        try:
            df = pandas_gbq.read_gbq(query, project_id=PROJECT, progress_bar_type=None)

            if len(df) == 0:
                print(f"  No more rows, stopping.")
                break

            # Save to parquet
            output_file = OUTPUT_DIR / f"{table_name}_chunk_{chunk_num:04d}.parquet"
            df.to_parquet(output_file, index=False, compression='snappy')

            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"  Saved {len(df):,} rows to {output_file.name} ({file_size_mb:.1f} MB)")

            all_files.append(str(output_file))

            offset += chunk_size
            chunk_num += 1

        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            print(f"  Resume with: --start-offset {offset}")
            break

    # Create manifest file
    manifest = {
        'table': table_name,
        'project': PROJECT,
        'dataset': DATASET,
        'total_rows': total_rows,
        'exported_at': datetime.now().isoformat(),
        'files': all_files,
        'chunk_size': chunk_size,
    }

    manifest_file = OUTPUT_DIR / f"{table_name}_manifest.json"
    import json
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest saved to: {manifest_file}")
    print(f"  Total files: {len(all_files)}")

    return all_files


def merge_chunks(table_name: str):
    """Merge all chunks for a table into a single parquet file."""
    chunk_files = sorted(OUTPUT_DIR.glob(f"{table_name}_chunk_*.parquet"))

    if not chunk_files:
        print(f"No chunk files found for {table_name}")
        return None

    print(f"\nMerging {len(chunk_files)} chunks for {table_name}...")

    dfs = []
    for f in chunk_files:
        dfs.append(pd.read_parquet(f))

    merged = pd.concat(dfs, ignore_index=True)

    output_file = OUTPUT_DIR / f"{table_name}_full.parquet"
    merged.to_parquet(output_file, index=False, compression='snappy')

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Merged {len(merged):,} rows to {output_file.name} ({file_size_mb:.1f} MB)")

    return output_file


def main():
    parser = argparse.ArgumentParser(description='Export BigQuery tables to Parquet')
    parser.add_argument('--table', choices=list(TABLES.keys()) + ['all'], default='all',
                       help='Table to export (v2, v3, elev, raw, clean, or all)')
    parser.add_argument('--chunk-size', type=int, default=200000,
                       help='Rows per chunk (default: 200000)')
    parser.add_argument('--start-offset', type=int, default=0,
                       help='Starting row offset for resuming')
    parser.add_argument('--merge', action='store_true',
                       help='Merge chunk files after export')
    parser.add_argument('--merge-only', action='store_true',
                       help='Only merge existing chunks (no export)')

    args = parser.parse_args()

    if args.merge_only:
        if args.table == 'all':
            for key, (table_name, _) in TABLES.items():
                merge_chunks(table_name)
        else:
            table_name, _ = TABLES[args.table]
            merge_chunks(table_name)
        return

    print("="*60)
    print("BIGQUERY DATA EXPORT")
    print("="*60)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Chunk size: {args.chunk_size:,}")

    if args.table == 'all':
        tables_to_export = list(TABLES.items())
    else:
        tables_to_export = [(args.table, TABLES[args.table])]

    for key, (table_name, approx_rows) in tables_to_export:
        export_table(table_name, chunk_size=args.chunk_size, start_offset=args.start_offset)

        if args.merge:
            merge_chunks(table_name)

    print("\n" + "="*60)
    print("EXPORT COMPLETE")
    print("="*60)
    print(f"\nFiles saved to: {OUTPUT_DIR}")
    print("\nTo upload to new BigQuery account:")
    print("  1. Create new dataset in new project")
    print("  2. Use bq load or BigQuery console to import parquet files")
    print("  3. Or use: bq load --source_format=PARQUET new_project:dataset.table file.parquet")


if __name__ == '__main__':
    main()
