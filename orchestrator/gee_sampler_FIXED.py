"""
GEE AlphaEarth Sampler - FIXED VERSION for coordinate type issues
KEY FIXES:
1. Use .mosaic() to combine all tiles before sampling (from FINAL version)
2. Ensure coordinates are always cast as proper floats for Earth Engine

The coordinate issue: When coordinates are exact integers (e.g., -4.0, 152.0),
Earth Engine can misinterpret them as integers instead of floats when creating
Features, causing "incompatible type for property [longitude/latitude]" errors
during BigQuery export.

Solution: Add explicit float casting with small epsilon to ensure decimal representation.
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


def ensure_float_coordinate(value: float) -> float:
    """
    Ensure coordinate is a proper float, not interpretable as integer.

    Earth Engine can misinterpret exact integer values (like -4.0, 152.0) as integers,
    causing type incompatibility errors during BigQuery export.

    Solution: If value is exactly an integer, add a tiny epsilon to force decimal representation.
    The epsilon (1e-10) is negligible for geographic coordinates (~0.01mm at equator).

    Args:
        value: Coordinate value (latitude or longitude)

    Returns:
        Float value that won't be misinterpreted as integer
    """
    float_val = float(value)
    # Check if it's an exact integer (like -4.0, 152.0)
    if float_val == int(float_val):
        # Add tiny epsilon to force decimal representation
        # 1e-10 degrees is ~0.01mm at the equator, completely negligible
        return float_val + 1e-10
    return float_val


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

    FIXES:
    1. Uses mosaic() to handle tiled AlphaEarth data
    2. Ensures coordinates are proper floats to avoid type errors

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

        # Create Earth Engine features with coordinate type fix
        feats = []
        for p in chunk:
            # FIX: Ensure coordinates are proper floats
            lat = ensure_float_coordinate(p['latitude'])
            lon = ensure_float_coordinate(p['longitude'])

            # Create feature with properly typed coordinates
            feat = ee.Feature(
                ee.Geometry.Point([lon, lat]),
                {
                    'taxon_id': str(p['taxon_id']),
                    'emb_year': int(p['embedding_year']),
                    'orig_year': int(p.get('year', p['embedding_year'])),
                    # Store original coordinates as properties with explicit float casting
                    'latitude': ee.Number(lat).toFloat(),
                    'longitude': ee.Number(lon).toFloat()
                }
            )
            feats.append(feat)

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
    # Test with coordinates that previously failed
    print("="*80)
    print("GEE ALPHAEARTH SAMPLER - TESTING COORDINATE FIX")
    print("="*80)

    # Test with exact integer coordinates that previously caused errors
    test_points = [
        {
            'taxon_id': 'TEST-EXACT-LON',
            'latitude': 38.16,
            'longitude': -4.0,  # Exact integer - previously failed
            'year': 2018,
            'embedding_year': 2018
        },
        {
            'taxon_id': 'TEST-EXACT-LON2',
            'latitude': -29.041,
            'longitude': 152.0,  # Exact integer - previously failed
            'year': 2018,
            'embedding_year': 2018
        },
        {
            'taxon_id': 'TEST-EXACT-LAT',
            'latitude': -32.0,  # Exact integer - previously failed
            'longitude': 151.919511,
            'year': 2020,
            'embedding_year': 2020
        },
        {
            'taxon_id': 'TEST-NORMAL',
            'latitude': 37.4220,
            'longitude': -122.0841,
            'year': 2023,
            'embedding_year': 2023
        }
    ]

    print(f"\n📍 Test points (including previously failing exact integers):")
    for pt in test_points:
        print(f"  - {pt['taxon_id']}: ({pt['latitude']}, {pt['longitude']})")
        # Show how coordinates are transformed
        lat_fixed = ensure_float_coordinate(pt['latitude'])
        lon_fixed = ensure_float_coordinate(pt['longitude'])
        if lat_fixed != pt['latitude'] or lon_fixed != pt['longitude']:
            print(f"    → Fixed to: ({lat_fixed:.10f}, {lon_fixed:.10f})")

    print(f"\n🎯 Target: {PROJECT}.{BQ_DATASET}.{BQ_TABLE_RAW}")

    task_ids = export_batch_to_bigquery('test_coordinate_fix', test_points)
    print(f"\n✅ Submitted {len(task_ids)} task(s)")

    results = wait_for_tasks(task_ids, poll_interval=15)

    print(f"\n{'='*80}")
    print("TEST RESULTS")
    print(f"{'='*80}")
    print(f"✅ Completed: {len(results['completed'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results['failed']:
        print(f"\n⚠️ Failed tasks:")
        for task_id, error in results['failed']:
            print(f"   Task: {task_id}")
            print(f"   Error: {error}")

    if results['completed'] and not results['failed']:
        print(f"\n🎉 SUCCESS! Coordinate fix works - exact integers are now handled properly")
        print(f"\nFix applied:")
        print(f"  - Exact integer coordinates (e.g., -4.0, 152.0) get tiny epsilon added")
        print(f"  - Epsilon (1e-10 degrees) is ~0.01mm at equator - completely negligible")
        print(f"  - Prevents Earth Engine from misinterpreting as integer type")
        print(f"\nNext: Update production script to use this fixed version")

    print(f"{'='*80}\n")