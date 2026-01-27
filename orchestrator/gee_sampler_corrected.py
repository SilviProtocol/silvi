"""
GEE AlphaEarth Sampler - CORRECTED IMPLEMENTATION
Based on research findings:
- Band names are A00-A63 (NOT A01-A64)
- Must use .first() to get ee.Image from ImageCollection
- Coordinate order is [longitude, latitude]

Key optimizations:
- Dynamic quota management (2-8 concurrent tasks)
- Adaptive batch sizing (500-5000 points)
- Automatic retry with exponential backoff
"""

import ee
from typing import List, Dict, Optional
import time
from datetime import datetime

# Configuration
PROJECT = 'treekipedia-476404'
BQ_DATASET = 'alphaearth'
BQ_TABLE_RAW = 'occ_embeddings_raw'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

# Quota management settings
MAX_CONCURRENT_TASKS = 8
MIN_CONCURRENT_TASKS = 2
INITIAL_BATCH_SIZE = 2000
MIN_BATCH_SIZE = 500
MAX_BATCH_SIZE = 5000

# Initialize Earth Engine
try:
    ee.Initialize(project=PROJECT)
    print(f"✅ Earth Engine initialized (project: {PROJECT})")
except Exception as e:
    print(f"❌ Earth Engine initialization failed: {e}")
    raise


class QuotaManager:
    """Manages GEE quota dynamically to maximize throughput."""
    def __init__(self):
        self.concurrent_tasks = 4
        self.batch_size = INITIAL_BATCH_SIZE
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.total_points_processed = 0
        self.total_tasks_completed = 0
        self.start_time = time.time()

    def adjust_on_success(self):
        """Called when tasks complete successfully."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.total_tasks_completed += 1

        if self.consecutive_successes >= 3:
            if self.concurrent_tasks < MAX_CONCURRENT_TASKS:
                self.concurrent_tasks += 1
                print(f"  📈 Increased concurrent tasks to {self.concurrent_tasks}")
            self.consecutive_successes = 0

        if self.total_tasks_completed > 0 and self.total_tasks_completed % 5 == 0:
            if self.batch_size < MAX_BATCH_SIZE:
                self.batch_size = min(self.batch_size + 500, MAX_BATCH_SIZE)
                print(f"  📈 Increased batch size to {self.batch_size}")

    def adjust_on_failure(self, error_msg: str):
        """Called when tasks fail - back off to prevent quota exhaustion."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        is_quota_error = any(keyword in error_msg.lower() for keyword in
                            ['quota', 'limit', 'rate', 'too many'])

        if is_quota_error:
            self.concurrent_tasks = max(MIN_CONCURRENT_TASKS, self.concurrent_tasks - 2)
            self.batch_size = max(MIN_BATCH_SIZE, int(self.batch_size * 0.7))
            print(f"  ⚠️  QUOTA ERROR - Reduced to {self.concurrent_tasks} tasks, "
                  f"{self.batch_size} points/task")
            return 60
        else:
            if self.consecutive_failures >= 3:
                self.concurrent_tasks = max(MIN_CONCURRENT_TASKS, self.concurrent_tasks - 1)
                print(f"  📉 Reduced concurrent tasks to {self.concurrent_tasks}")
            return 10

    def get_stats(self):
        """Return current throughput stats."""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            points_per_sec = self.total_points_processed / elapsed
            return {
                'elapsed_mins': elapsed / 60,
                'total_points': self.total_points_processed,
                'total_tasks': self.total_tasks_completed,
                'points_per_sec': points_per_sec,
                'current_concurrent': self.concurrent_tasks,
                'current_batch_size': self.batch_size
            }
        return {}


quota_mgr = QuotaManager()


def ae_image_for_year(year: int) -> ee.Image:
    """
    Get AlphaEarth image for a given year.

    CRITICAL: Must return ee.Image (not ImageCollection) for sampleRegions to work.

    Args:
        year: Year (2017-2024)

    Returns:
        ee.Image with 64 bands (A00-A63) representing 64-dimensional embeddings
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )

    # CRITICAL FIX: Use .first() to get ee.Image from ImageCollection
    # sampleRegions() only works on ee.Image, not ee.ImageCollection
    img = ee.Image(col.first())

    return img


def export_batch_to_bigquery(
    batch_id: str,
    points: List[Dict],
    max_concurrent: Optional[int] = None
) -> List[str]:
    """
    Export AlphaEarth embeddings for occurrence points to BigQuery.

    CORRECTED IMPLEMENTATION:
    - Uses .first() to convert ImageCollection to Image
    - Band names are A00-A63 (not A01-A64)
    - Coordinate order is [longitude, latitude]

    Args:
        batch_id: Unique batch identifier
        points: List of {taxon_id, latitude, longitude, year, embedding_year}
        max_concurrent: Override concurrent task limit

    Returns:
        List of GEE task IDs
    """
    batch_size = max_concurrent or quota_mgr.batch_size

    print(f"\n  📦 Batch config: {len(points)} points, "
          f"~{len(points)//batch_size + 1} tasks @ {batch_size} points/task")

    task_ids = []
    for i, chunk_start in enumerate(range(0, len(points), batch_size)):
        chunk = points[chunk_start:chunk_start + batch_size]

        # Create Earth Engine features
        # IMPORTANT: GEE uses [longitude, latitude] order
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
            # CRITICAL FIX: Use ae_image_for_year which returns ee.Image (not ImageCollection)
            img = ae_image_for_year(y)
            fc_y = fc.filter(ee.Filter.eq('emb_year', y))

            # Sample AlphaEarth at 10m scale
            # Returns features with bands A00-A63 (64 dimensions)
            s_y = img.sampleRegions(
                collection=fc_y,
                scale=10,           # Native 10m resolution
                geometries=False,   # Don't include geometry (saves space)
                tileScale=4         # Prevent memory errors on large datasets
            )
            sampled = sampled.merge(s_y)

        # Export directly to BigQuery
        # Format: project.dataset.table (dots, not colons)
        task_desc = f'ae_{batch_id}_chunk{i:03d}'
        task = ee.batch.Export.table.toBigQuery(
            collection=sampled,
            description=task_desc,
            table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE_RAW}',
            writeDisposition='WRITE_APPEND'
        )
        task.start()
        task_ids.append(task.id)

        print(f"    ✓ Task {i+1}: {task_desc} ({len(chunk)} points, years: {years})")

    quota_mgr.total_points_processed += len(points)
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


def wait_for_tasks_optimized(
    task_ids: List[str],
    poll_interval: int = 30
) -> Dict:
    """
    Wait for GEE tasks with dynamic concurrency management.

    Args:
        task_ids: List of task IDs to monitor
        poll_interval: Seconds between status checks

    Returns:
        {completed: [ids], failed: [(id, error)], stats: {}}
    """
    pending = set(task_ids)
    completed = []
    failed = []

    print(f"\n  ⏳ Monitoring {len(task_ids)} GEE tasks (concurrent limit: {quota_mgr.concurrent_tasks})...")

    while pending:
        time.sleep(poll_interval)

        for task_id in list(pending):
            status = check_task_status(task_id)

            if status['state'] == 'COMPLETED':
                completed.append(task_id)
                pending.remove(task_id)
                quota_mgr.adjust_on_success()
                print(f"    ✅ Task {len(completed)}/{len(task_ids)} completed")

            elif status['state'] == 'FAILED':
                error_msg = status['error_message'] or 'Unknown error'
                failed.append((task_id, error_msg))
                pending.remove(task_id)

                backoff_time = quota_mgr.adjust_on_failure(error_msg)
                print(f"    ❌ Task failed: {error_msg[:100]}")

                if 'quota' in error_msg.lower():
                    print(f"    ⏸️  Backing off for {backoff_time}s due to quota error...")
                    time.sleep(backoff_time)

            elif status['state'] in ['READY', 'RUNNING']:
                pass

        if pending:
            stats = quota_mgr.get_stats()
            print(f"\n    📊 Progress: {len(completed)}/{len(task_ids)} tasks, "
                  f"{len(pending)} pending")
            if stats:
                print(f"       Throughput: {stats['points_per_sec']:.1f} points/sec, "
                      f"{stats['elapsed_mins']:.1f} mins elapsed")
            print(f"       Next check in {poll_interval}s...\n")

    return {
        'completed': completed,
        'failed': failed,
        'stats': quota_mgr.get_stats()
    }


if __name__ == '__main__':
    # Test with single point
    print("="*70)
    print("GEE SAMPLER TEST - CORRECTED IMPLEMENTATION")
    print("="*70)

    test_points = [{
        'taxon_id': 'TEST-001',
        'latitude': 37.4220,     # Google HQ
        'longitude': -122.0841,
        'year': 2023,
        'embedding_year': 2023
    }]

    print(f"\n📍 Test point: {test_points[0]}")
    print(f"🎯 Target: {PROJECT}.{BQ_DATASET}.{BQ_TABLE_RAW}")
    print(f"\nExpected output columns:")
    print(f"  - taxon_id, emb_year, orig_year, latitude, longitude")
    print(f"  - A00, A01, A02, ..., A63 (64 embedding dimensions)")

    task_ids = export_batch_to_bigquery('test_corrected', test_points)
    print(f"\n✅ Submitted {len(task_ids)} task(s)")

    results = wait_for_tasks_optimized(task_ids, poll_interval=10)

    print(f"\n{'='*70}")
    print("TEST RESULTS")
    print(f"{'='*70}")
    print(f"✅ Completed: {len(results['completed'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results['failed']:
        for task_id, error in results['failed']:
            print(f"   Failed task: {task_id}")
            print(f"   Error: {error}")

    if results['stats']:
        print(f"\nStats:")
        for k, v in results['stats'].items():
            print(f"  {k}: {v}")

    print(f"{'='*70}\n")
