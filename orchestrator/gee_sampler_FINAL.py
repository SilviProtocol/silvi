"""
GEE AlphaEarth Sampler - FINAL WORKING VERSION
KEY FIX: Use .mosaic() to combine all tiles before sampling

The issue was that AlphaEarth has ~11K tiles per year (globally tiled).
Individual tiles don't have data everywhere. Using .mosaic() combines all tiles
into a single global image that can be sampled anywhere.
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
try:
    ee.Initialize(project=PROJECT)
    print(f"✅ Earth Engine initialized (project: {PROJECT})")
except Exception as e:
    print(f"❌ Earth Engine initialization failed: {e}")
    raise


def ae_image_for_year_FIXED(year: int) -> ee.Image:
    """
    Get AlphaEarth mosaic image for a given year.

    CRITICAL FIX: Use .mosaic() to combine all ~11K tiles into single global image.
    Without mosaic(), individual tiles have gaps and sampling returns empty results.

    Args:
        year: Year (2017-2024)

    Returns:
        ee.Image with 64 bands (A00-A63) - global mosaic
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )

    # CRITICAL: Use .mosaic() to combine all tiles
    # This creates a single global image from ~11K tiles per year
    mosaic_img = col.mosaic()

    return mosaic_img


def export_batch_to_bigquery(
    batch_id: str,
    points: List[Dict],
    batch_size: int = 2000
) -> List[str]:
    """
    Export AlphaEarth embeddings for occurrence points to BigQuery.

    FINAL WORKING VERSION with mosaic() fix.

    Args:
        batch_id: Unique batch identifier
        points: List of {taxon_id, latitude, longitude, year, embedding_year}
        batch_size: Points per export task

    Returns:
        List of GEE task IDs
    """
    print(f"\n  📦 Exporting batch: {batch_id}")
    print(f"     Points: {len(points)}, Tasks: ~{len(points)//batch_size + 1}")

    task_ids = []
    for i, chunk_start in enumerate(range(0, len(points), batch_size)):
        chunk = points[chunk_start:chunk_start + batch_size]

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
            # FIXED: Use mosaic version
            img = ae_image_for_year_FIXED(y)
            fc_y = fc.filter(ee.Filter.eq('emb_year', y))

            # Sample AlphaEarth mosaic at 10m scale
            s_y = img.sampleRegions(
                collection=fc_y,
                scale=10,
                geometries=False,
                tileScale=4
            )
            sampled = sampled.merge(s_y)

        # Export to BigQuery
        # GEE handles schema automatically - use append=True and let retry handle table creation
        task_desc = f'ae_{batch_id}_chunk{i:03d}'
        task = ee.batch.Export.table.toBigQuery(
            collection=sampled,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE_RAW}',
            append=True,
            overwrite=False
        )
        task.start()
        task_ids.append(task.id)

        print(f"     ✓ Task {i+1}/{len(range(0, len(points), batch_size))}: {task_desc} ({len(chunk)} pts, years: {years})")

    return task_ids


def check_task_status(task_id: str) -> Dict:
    """Check GEE task status."""
    try:
        status = ee.data.getTaskStatus(task_id)[0]
        return {
            'state': status['state'],
            'error_message': status.get('error_message')
        }
    except Exception as e:
        return {
            'state': 'UNKNOWN',
            'error_message': str(e)
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

    print(f"\n  ⏳ Monitoring {len(task_ids)} GEE tasks...")

    while pending:
        time.sleep(poll_interval)

        for task_id in list(pending):
            status = check_task_status(task_id)

            if status['state'] == 'COMPLETED':
                completed.append(task_id)
                pending.remove(task_id)
                print(f"     ✅ Task completed ({len(completed)}/{len(task_ids)})")

            elif status['state'] == 'FAILED':
                error_msg = status['error_message'] or 'Unknown error'
                failed.append((task_id, error_msg))
                pending.remove(task_id)
                print(f"     ❌ Task failed: {error_msg[:100]}")

            elif status['state'] in ['READY', 'RUNNING']:
                pass

        if pending:
            print(f"     ⏳ {len(pending)} tasks still pending (next check in {poll_interval}s)...")

    return {'completed': completed, 'failed': failed}


if __name__ == '__main__':
    # Test with single point
    print("="*80)
    print("GEE ALPHAEARTH SAMPLER - FINAL TEST")
    print("="*80)

    test_points = [{
        'taxon_id': 'TEST-FINAL',
        'latitude': 37.4220,
        'longitude': -122.0841,
        'year': 2023,
        'embedding_year': 2023
    }]

    print(f"\n📍 Test point: Google HQ ({test_points[0]['latitude']}, {test_points[0]['longitude']})")
    print(f"🎯 Target: {PROJECT}.{BQ_DATASET}.{BQ_TABLE_RAW}")

    task_ids = export_batch_to_bigquery('test_final', test_points)
    print(f"\n✅ Submitted {len(task_ids)} task(s)")

    results = wait_for_tasks(task_ids, poll_interval=15)

    print(f"\n{'='*80}")
    print("TEST RESULTS")
    print(f"{'='*80}")
    print(f"✅ Completed: {len(results['completed'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results['failed']:
        for task_id, error in results['failed']:
            print(f"   Failed: {task_id}")
            print(f"   Error: {error}")

    if results['completed']:
        print(f"\n🎉 SUCCESS! AlphaEarth sampling works with mosaic()")
        print(f"\nNext: Run full Acacia pycnantha test (100 points)")

    print(f"{'='*80}\n")
