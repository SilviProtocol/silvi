#!/usr/bin/env python3
"""
Export BigQuery AlphaEarth Embeddings to Local Parquet Files
=============================================================
Exports the full dataset from BigQuery to local Parquet files for:
1. Backup/archival
2. Local compute (free clustering)
3. Faster iteration during development

Output: orchestrator/bigquery_exports/alphaearth_embeddings_v4/
        - Partitioned by taxon_id prefix for efficient loading
        - Parquet format for compression + fast reads

Usage:
    python export_bigquery_local.py [--output-dir PATH] [--batch-size 100000]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = "treekipedia-479918"
DATASET_ID = "species_data"
TABLE_ID = "alphaearth_embeddings_v4"
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "bigquery_exports" / "alphaearth_embeddings_v4"


def get_bigquery_client():
    """Initialize BigQuery client."""
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=PROJECT_ID)
    except ImportError:
        logger.error("google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
        sys.exit(1)


def get_table_stats(client):
    """Get table statistics."""
    query = f"""
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT taxon_id) as unique_species,
            MIN(emb_year) as min_year,
            MAX(emb_year) as max_year,
            COUNTIF(elevation IS NOT NULL) as with_elevation,
            COUNTIF(A00 IS NOT NULL) as with_embedding
        FROM `{FULL_TABLE_ID}`
    """
    result = client.query(query).result()
    row = list(result)[0]
    return {
        'total_rows': row.total_rows,
        'unique_species': row.unique_species,
        'min_year': row.min_year,
        'max_year': row.max_year,
        'with_elevation': row.with_elevation,
        'with_embedding': row.with_embedding
    }


def export_to_parquet_batched(client, output_dir: Path, batch_size: int = 100000, start_batch: int = 1):
    """Export data in batches to Parquet files.

    Args:
        client: BigQuery client
        output_dir: Output directory for Parquet files
        batch_size: Number of rows per batch
        start_batch: Batch number to start from (for resuming interrupted exports)
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build column list (schema uses A00-A63 for embeddings)
    embedding_cols = ", ".join([f"A{i:02d}" for i in range(64)])

    # Get total count
    count_query = f"SELECT COUNT(*) as cnt FROM `{FULL_TABLE_ID}`"
    total_rows = list(client.query(count_query).result())[0].cnt

    logger.info(f"Total rows to export: {total_rows:,}")
    logger.info(f"Batch size: {batch_size:,}")
    logger.info(f"Estimated batches: {(total_rows + batch_size - 1) // batch_size}")

    # Calculate number of batches needed
    num_batches = (total_rows + batch_size - 1) // batch_size
    total_exported = 0

    if start_batch > 1:
        logger.info(f"Resuming from batch {start_batch} of {num_batches}...")

    # Export using modulo on hash for memory-efficient batching
    # This avoids ORDER BY + OFFSET which exhausts memory at high offsets
    for batch_num in range(start_batch, num_batches + 1):
        logger.info(f"Exporting batch {batch_num}/{num_batches}...")

        # Use FARM_FINGERPRINT for deterministic partitioning without ORDER BY
        query = f"""
            SELECT
                taxon_id,
                latitude,
                longitude,
                emb_year,
                orig_year,
                elevation,
                treecover2000,
                lossyear,
                loss,
                gain,
                {embedding_cols}
            FROM `{FULL_TABLE_ID}`
            WHERE MOD(ABS(FARM_FINGERPRINT(CONCAT(taxon_id, CAST(latitude AS STRING), CAST(longitude AS STRING)))), {num_batches}) = {batch_num - 1}
        """

        # Execute query and convert to DataFrame
        df = client.query(query).to_dataframe()

        if len(df) == 0:
            logger.warning(f"  Batch {batch_num} returned 0 rows, skipping...")
            continue

        # Save to Parquet
        output_file = output_dir / f"batch_{batch_num:04d}.parquet"
        df.to_parquet(output_file, index=False, compression='snappy')

        total_exported += len(df)
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        logger.info(f"  Saved {len(df):,} rows to {output_file.name} ({file_size_mb:.1f} MB)")

    return total_exported, num_batches


def export_to_gcs_then_download(client, output_dir: Path):
    """
    Alternative: Export to GCS first, then download.
    This is faster for very large tables (>10M rows).
    """
    from google.cloud import storage

    # This requires a GCS bucket - implement if needed
    raise NotImplementedError("GCS export not implemented. Use batched export for now.")


def export_by_species(client, output_dir: Path, min_occurrences: int = 10):
    """
    Export data grouped by species to individual Parquet files.
    Better for clustering pipeline that processes one species at a time.
    """
    import pandas as pd

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get species list with counts
    logger.info("Getting species list...")
    species_query = f"""
        SELECT taxon_id, COUNT(*) as occ_count
        FROM `{FULL_TABLE_ID}`
        WHERE taxon_id IS NOT NULL
        GROUP BY taxon_id
        HAVING COUNT(*) >= {min_occurrences}
        ORDER BY occ_count DESC
    """
    species_df = client.query(species_query).to_dataframe()

    logger.info(f"Found {len(species_df):,} species with >= {min_occurrences} occurrences")
    total_occurrences = species_df['occ_count'].sum()
    logger.info(f"Total occurrences to export: {total_occurrences:,}")

    # Build embedding columns (schema uses A00-A63)
    embedding_cols = ", ".join([f"A{i:02d}" for i in range(64)])

    # Export each species
    exported_species = 0
    exported_rows = 0
    start_time = datetime.now()

    for idx, row in species_df.iterrows():
        taxon_id = row['taxon_id']
        expected_count = row['occ_count']

        # Create safe filename
        safe_taxon = taxon_id.replace('/', '_').replace(':', '_')
        output_file = output_dir / f"{safe_taxon}.parquet"

        # Skip if already exported
        if output_file.exists():
            exported_species += 1
            exported_rows += expected_count
            if exported_species % 1000 == 0:
                logger.info(f"  Skipped {exported_species:,} (already exist)...")
            continue

        # Query this species
        query = f"""
            SELECT
                taxon_id,
                latitude,
                longitude,
                emb_year,
                orig_year,
                elevation,
                treecover2000,
                lossyear,
                loss,
                gain,
                {embedding_cols}
            FROM `{FULL_TABLE_ID}`
            WHERE taxon_id = @taxon_id
        """

        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("taxon_id", "STRING", taxon_id)
            ]
        )

        df = client.query(query, job_config=job_config).to_dataframe()

        # Save to Parquet
        df.to_parquet(output_file, index=False, compression='snappy')

        exported_species += 1
        exported_rows += len(df)

        # Progress logging
        if exported_species % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = exported_species / elapsed * 3600
            logger.info(f"  Exported {exported_species:,}/{len(species_df):,} species ({rate:.0f}/hour)")

    return exported_species, exported_rows


def create_combined_parquet(output_dir: Path):
    """Combine individual species files into a single large Parquet file."""
    import pandas as pd
    import pyarrow.parquet as pq

    parquet_files = list(output_dir.glob("*.parquet"))
    if not parquet_files:
        logger.warning("No Parquet files found to combine")
        return

    logger.info(f"Combining {len(parquet_files):,} Parquet files...")

    # Use PyArrow for efficient concatenation
    tables = []
    for pf in parquet_files:
        tables.append(pq.read_table(pf))

    combined = pa.concat_tables(tables)

    output_file = output_dir.parent / "alphaearth_embeddings_v4_combined.parquet"
    pq.write_table(combined, output_file, compression='snappy')

    file_size_gb = output_file.stat().st_size / (1024 ** 3)
    logger.info(f"Combined file: {output_file} ({file_size_gb:.2f} GB)")

    return output_file


def main():
    parser = argparse.ArgumentParser(description="Export BigQuery data to local Parquet")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help="Output directory for Parquet files")
    parser.add_argument("--mode", choices=["batched", "by-species"], default="batched",
                        help="Export mode: batched (single large export) or by-species (one file per species)")
    parser.add_argument("--batch-size", type=int, default=100000,
                        help="Rows per batch (for batched mode)")
    parser.add_argument("--start-batch", type=int, default=1,
                        help="Batch number to start from (for resuming interrupted exports)")
    parser.add_argument("--min-occurrences", type=int, default=10,
                        help="Minimum occurrences per species (for by-species mode)")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only show table statistics, don't export")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    logger.info("=" * 60)
    logger.info("BigQuery to Local Parquet Export")
    logger.info("=" * 60)
    logger.info(f"Source: {FULL_TABLE_ID}")
    logger.info(f"Output: {output_dir}")

    # Initialize client
    client = get_bigquery_client()

    # Get and display stats
    logger.info("\nTable Statistics:")
    stats = get_table_stats(client)
    for key, value in stats.items():
        logger.info(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")

    if args.stats_only:
        return

    # Export
    start_time = datetime.now()

    if args.mode == "batched":
        total_rows, num_batches = export_to_parquet_batched(
            client, output_dir, args.batch_size, args.start_batch
        )
        logger.info(f"\nExported {total_rows:,} rows in {num_batches} batches")
    else:
        num_species, total_rows = export_by_species(
            client, output_dir, args.min_occurrences
        )
        logger.info(f"\nExported {total_rows:,} rows for {num_species:,} species")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Total time: {elapsed/60:.1f} minutes")

    # Calculate total size
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.parquet"))
    logger.info(f"Total size: {total_size / (1024**3):.2f} GB")


if __name__ == "__main__":
    main()
