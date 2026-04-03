#!/usr/bin/env python3
"""
Fast COG Sampler Test - Comparing Approaches
=============================================

Based on research: https://rdrn.me/optimising-sampling/
Key insight: 250,000x speedup by using direct numpy indexing vs rasterio

Test approaches:
1. Remote COG via rasterio (current slow approach)
2. Download COG locally + numpy indexing (potentially much faster)

Usage:
    python3 fast_sampler_test.py
"""

import time
import numpy as np

# Test configuration
PROJECT_ID = "treekipedia-479918"
# Real COG from index
TEST_COG = "gs://alphaearth_foundations/satellite_embedding/v1/annual/2017/60S/x3ovkk6ox9v2f2iqv-0000000000-0000000000.tiff"
NUM_TEST_POINTS = 100

print("="*60)
print("FAST COG SAMPLER - APPROACH COMPARISON")
print("="*60)

# Generate random test points within this COG's bounds
# Bounds: West=175.12, East=176.07, South=-38.48, North=-37.73
np.random.seed(42)
test_lons = np.random.uniform(175.2, 176.0, NUM_TEST_POINTS)
test_lats = np.random.uniform(-38.4, -37.8, NUM_TEST_POINTS)

print(f"Test points: {NUM_TEST_POINTS}")
print(f"COG: {TEST_COG}")
print()

# =============================================================================
# APPROACH 1: Remote COG via rasterio (current slow method)
# =============================================================================
print("="*60)
print("APPROACH 1: Remote COG via /vsigs/ (current)")
print("="*60)

try:
    import rasterio
    from rasterio.windows import Window
    from pyproj import Transformer

    start = time.time()
    results_remote = []

    # Convert gs:// to /vsigs/
    full_path = "/vsigs/" + TEST_COG[5:]  # Remove "gs://"

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
        GS_USER_PROJECT=PROJECT_ID,
        GDAL_HTTP_TIMEOUT=120,
        GDAL_HTTP_MAX_RETRY=3,
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
    ):
        with rasterio.open(full_path) as src:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

            for i in range(NUM_TEST_POINTS):
                try:
                    x, y = transformer.transform(test_lons[i], test_lats[i])
                    row, col = src.index(x, y)

                    if 0 <= row < src.height and 0 <= col < src.width:
                        window = Window(int(col), int(row), 1, 1)
                        data = src.read(window=window)
                        results_remote.append(data.flatten())
                except Exception as e:
                    pass

    elapsed_remote = time.time() - start
    print(f"  Results: {len(results_remote)} points")
    print(f"  Time: {elapsed_remote:.2f}s")
    print(f"  Rate: {len(results_remote)/elapsed_remote:.1f} pts/sec")

except Exception as e:
    print(f"  Error: {e}")
    elapsed_remote = None

# =============================================================================
# APPROACH 2: Download COG locally, then numpy indexing
# =============================================================================
print()
print("="*60)
print("APPROACH 2: Download locally + numpy indexing")
print("="*60)

try:
    import subprocess
    import tempfile
    import os

    # Step 1: Download COG
    print("  Downloading COG...")
    start_download = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "test.tiff")

        # Use gcloud storage for fast download (requester pays)
        cmd = f"gcloud storage cp {TEST_COG} {local_path} --billing-project={PROJECT_ID}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

        download_time = time.time() - start_download

        if result.returncode != 0:
            print(f"  Download failed: {result.stderr}")
        else:
            file_size = os.path.getsize(local_path) / (1024*1024)
            print(f"  Downloaded: {file_size:.1f} MB in {download_time:.1f}s")

            # Step 2: Sample using local file
            print("  Sampling locally...")
            start_sample = time.time()
            results_local = []

            with rasterio.open(local_path) as src:
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

                # Read entire raster into memory
                data = src.read()

                for i in range(NUM_TEST_POINTS):
                    try:
                        x, y = transformer.transform(test_lons[i], test_lats[i])
                        row, col = src.index(x, y)

                        if 0 <= row < src.height and 0 <= col < src.width:
                            results_local.append(data[:, int(row), int(col)])
                    except Exception:
                        pass

            sample_time = time.time() - start_sample
            total_time = download_time + sample_time

            print(f"  Results: {len(results_local)} points")
            print(f"  Download time: {download_time:.2f}s")
            print(f"  Sample time: {sample_time:.4f}s")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Rate: {len(results_local)/total_time:.1f} pts/sec")

except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# APPROACH 3: Batch read bounding box remotely
# =============================================================================
print()
print("="*60)
print("APPROACH 3: Remote batch bounding box read")
print("="*60)

try:
    start = time.time()
    results_batch = []

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
        GS_USER_PROJECT=PROJECT_ID,
        GDAL_HTTP_TIMEOUT=120,
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
    ):
        with rasterio.open(full_path) as src:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

            # Convert all points to pixel coords
            pixel_coords = []
            for i in range(NUM_TEST_POINTS):
                try:
                    x, y = transformer.transform(test_lons[i], test_lats[i])
                    row, col = src.index(x, y)
                    if 0 <= row < src.height and 0 <= col < src.width:
                        pixel_coords.append((int(row), int(col)))
                except:
                    pass

            if pixel_coords:
                # Find bounding box
                rows = [p[0] for p in pixel_coords]
                cols = [p[1] for p in pixel_coords]
                min_row, max_row = min(rows), max(rows)
                min_col, max_col = min(cols), max(cols)

                # Read bounding box
                window = Window(min_col, min_row, max_col - min_col + 1, max_row - min_row + 1)
                batch_data = src.read(window=window)

                # Extract individual points
                for row, col in pixel_coords:
                    local_row = row - min_row
                    local_col = col - min_col
                    results_batch.append(batch_data[:, local_row, local_col])

    elapsed_batch = time.time() - start
    print(f"  Results: {len(results_batch)} points")
    print(f"  Time: {elapsed_batch:.2f}s")
    print(f"  Rate: {len(results_batch)/elapsed_batch:.1f} pts/sec")

except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# SUMMARY
# =============================================================================
print()
print("="*60)
print("SUMMARY")
print("="*60)
print("The winning approach for 16.5M points depends on:")
print("1. If points cluster in few COGs: Download COGs + local sampling")
print("2. If points spread across many COGs: Remote batch bbox reads")
print()
print("Key insight from research (rdrn.me/optimising-sampling/):")
print("  - Direct numpy indexing is 250,000x faster than rasterstats")
print("  - Avoid rasterio per-point overhead in hot loops")
print("  - Use affine transform directly with numpy")
