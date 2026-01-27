"""
GEE AlphaEarth Sampler
Samples 64-D embeddings from AlphaEarth at occurrence points and exports to BigQuery.
Following: treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md Section 3
"""

import ee
from typing import List, Dict
import time

# Configuration
PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE_RAW = 'occ_embeddings_raw'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

# Initialize Earth Engine
ee.Initialize(project=PROJECT)


def ae_image_for_year(year: int) -> ee.Image:
    """
    Get AlphaEarth image for a given year.

    Args:
        year: Year (2017-2024)

    Returns:
        ee.Image with 64 bands (A01-A64)
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    return ee.Image(col.first())


def export_batch_to_bigquery(
    batch_id: str,
    points: List[Dict],
    max_points_per_task: int = 5000
) -> List[str]:
    """
    Export AlphaEarth embeddings for occurrence points to BigQuery.

    Architecture:
      Local PostgreSQL → Python → GEE sampling → BigQuery export

    Args:
        batch_id: Unique batch identifier (e.g., 'AngMaFaFgCx14809-00_001')
        points: List of {taxon_id, latitude, longitude, embedding_year}
        max_points_per_task: GEE export size limit

    Returns:
        List of GEE task IDs
    """
    # Split into chunks if needed (GEE export limit ~5000 features)
    task_ids = []
    for i, chunk_start in enumerate(range(0, len(points), max_points_per_task)):
        chunk = points[chunk_start:chunk_start + max_points_per_task]

        # Create Earth Engine features
        feats = [
            ee.Feature(
                ee.Geometry.Point([p['longitude'], p['latitude']]),
                {
                    'taxon_id': str(p['taxon_id']),
                    'emb_year': int(p['embedding_year']),
                    'orig_year': int(p.get('year', p['embedding_year'])),
                    'latitude': float(p['latitude']),
                    'longitude': float(p['longitude'])
                }
            )
            for p in chunk
        ]
        fc = ee.FeatureCollection(feats)

        # Group by embedding year and sample
        years = sorted({p['embedding_year'] for p in chunk})
        sampled = ee.FeatureCollection([])

        for y in years:
            img = ae_image_for_year(y)
            fc_y = fc.filter(ee.Filter.eq('emb_year', y))

            # Sample AlphaEarth at 10m scale
            # Returns features with bands A01..A64
            s_y = img.sampleRegions(
                collection=fc_y,
                scale=10,
                geometries=False
            )
            sampled = sampled.merge(s_y)

        # Export directly to BigQuery
        task_desc = f'ae_{batch_id}_chunk{i:03d}'
        task = ee.batch.Export.table.toBigQuery(
            collection=sampled,
            description=task_desc,
            table=f'{PROJECT}:{BQ_DATASET}.{BQ_TABLE_RAW}',
            writeDisposition='WRITE_APPEND'
        )
        task.start()
        task_ids.append(task.id)

        print(f"  Started GEE task: {task_desc} (ID: {task.id})")
        print(f"    Points: {len(chunk)}, Years: {years}")

    return task_ids


def check_task_status(task_id: str) -> Dict:
    """
    Check GEE task status.

    Returns:
        {state: 'READY'|'RUNNING'|'COMPLETED'|'FAILED', error_message: str|None}
    """
    status = ee.data.getTaskStatus(task_id)[0]
    return {
        'state': status['state'],
        'error_message': status.get('error_message')
    }


def wait_for_tasks(task_ids: List[str], poll_interval: int = 30) -> Dict:
    """
    Wait for GEE tasks to complete with status monitoring.

    Args:
        task_ids: List of task IDs to monitor
        poll_interval: Seconds between status checks

    Returns:
        {completed: [ids], failed: [(id, error)]}
    """
    pending = set(task_ids)
    completed = []
    failed = []

    print(f"\nMonitoring {len(task_ids)} GEE tasks...")

    while pending:
        time.sleep(poll_interval)

        for task_id in list(pending):
            status = check_task_status(task_id)

            if status['state'] == 'COMPLETED':
                completed.append(task_id)
                pending.remove(task_id)
                print(f"  ✅ {task_id}: COMPLETED")

            elif status['state'] == 'FAILED':
                failed.append((task_id, status['error_message']))
                pending.remove(task_id)
                print(f"  ❌ {task_id}: FAILED - {status['error_message']}")

            elif status['state'] in ['READY', 'RUNNING']:
                print(f"  ⏳ {task_id}: {status['state']}")

        if pending:
            print(f"\n  Waiting for {len(pending)} tasks... (next check in {poll_interval}s)")

    return {'completed': completed, 'failed': failed}


if __name__ == '__main__':
    # Test with dummy point
    test_points = [
        {
            'taxon_id': 'TEST-001',
            'latitude': 37.4220,
            'longitude': -122.0841,
            'year': 2024,
            'embedding_year': 2024
        }
    ]

    print("Testing GEE sampler...")
    task_ids = export_batch_to_bigquery('test_001', test_points)
    print(f"\nSubmitted {len(task_ids)} tasks")

    # Wait for completion
    results = wait_for_tasks(task_ids, poll_interval=10)
    print(f"\n✅ Completed: {len(results['completed'])}")
    print(f"❌ Failed: {len(results['failed'])}")
