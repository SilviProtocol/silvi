#!/usr/bin/env python3
"""Quick COG read test - compare remote vs local"""

import time
import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import Transformer
import subprocess
import tempfile
import os

PROJECT_ID = "treekipedia-479918"
COG_PATH = "gs://alphaearth_foundations/satellite_embedding/v1/annual/2017/60S/x3ovkk6ox9v2f2iqv-0000000000-0000000000.tiff"
VSIGS_PATH = "/vsigs/" + COG_PATH[5:]

# Test points in this COG
np.random.seed(42)
LONS = np.random.uniform(175.2, 176.0, 50)
LATS = np.random.uniform(-38.4, -37.8, 50)

print("="*50)
print("QUICK COG TEST")
print("="*50)

# Test 1: Remote individual reads
print("\n[1] Remote COG - individual pixel reads...")
t0 = time.time()
count = 0

try:
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
        GS_USER_PROJECT=PROJECT_ID,
        GDAL_HTTP_TIMEOUT=60,
    ):
        with rasterio.open(VSIGS_PATH) as src:
            tfm = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            for i in range(10):  # Only 10 points
                x, y = tfm.transform(LONS[i], LATS[i])
                row, col = src.index(x, y)
                if 0 <= row < src.height and 0 <= col < src.width:
                    data = src.read(window=Window(int(col), int(row), 1, 1))
                    count += 1
    print(f"    {count} points in {time.time()-t0:.1f}s = {count/(time.time()-t0):.1f} pts/s")
except Exception as e:
    print(f"    Error: {e}")

# Test 2: Remote bbox read
print("\n[2] Remote COG - single bbox read...")
t0 = time.time()
count = 0

try:
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',
        GS_USER_PROJECT=PROJECT_ID,
        GDAL_HTTP_TIMEOUT=60,
    ):
        with rasterio.open(VSIGS_PATH) as src:
            tfm = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

            # Convert all to pixels
            pixels = []
            for i in range(50):
                x, y = tfm.transform(LONS[i], LATS[i])
                row, col = src.index(x, y)
                if 0 <= row < src.height and 0 <= col < src.width:
                    pixels.append((int(row), int(col)))

            if pixels:
                rows = [p[0] for p in pixels]
                cols = [p[1] for p in pixels]
                min_r, max_r = min(rows), max(rows)
                min_c, max_c = min(cols), max(cols)

                # Single read
                data = src.read(window=Window(min_c, min_r, max_c-min_c+1, max_r-min_r+1))

                for r, c in pixels:
                    _ = data[:, r-min_r, c-min_c]
                    count += 1

    print(f"    {count} points in {time.time()-t0:.1f}s = {count/(time.time()-t0):.1f} pts/s")
except Exception as e:
    print(f"    Error: {e}")

# Test 3: Download + local read
print("\n[3] Download COG + local read...")
t0 = time.time()
count = 0

try:
    with tempfile.TemporaryDirectory() as tmp:
        local = f"{tmp}/test.tiff"

        # Download
        t_dl = time.time()
        cmd = f"gcloud storage cp {COG_PATH} {local} --billing-project={PROJECT_ID}"
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
        dl_time = time.time() - t_dl

        if r.returncode == 0:
            size_mb = os.path.getsize(local) / (1024*1024)
            print(f"    Downloaded {size_mb:.1f}MB in {dl_time:.1f}s")

            # Sample locally
            t_sample = time.time()
            with rasterio.open(local) as src:
                data = src.read()  # Load all into memory
                tfm = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

                for i in range(50):
                    x, y = tfm.transform(LONS[i], LATS[i])
                    row, col = src.index(x, y)
                    if 0 <= row < src.height and 0 <= col < src.width:
                        _ = data[:, int(row), int(col)]
                        count += 1

            sample_time = time.time() - t_sample
            total = time.time() - t0
            print(f"    {count} points: dl={dl_time:.1f}s, sample={sample_time:.3f}s")
            print(f"    Total: {total:.1f}s = {count/total:.1f} pts/s")
        else:
            print(f"    Download failed: {r.stderr}")

except Exception as e:
    print(f"    Error: {e}")

print("\n" + "="*50)
print("KEY INSIGHT: If processing many points per COG,")
print("downloading locally can be much faster than")
print("thousands of individual remote HTTP requests.")
print("="*50)
