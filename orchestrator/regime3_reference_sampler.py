#!/usr/bin/env python3
"""
Regime 3: Spectral-Similarity Guided Reference Pixel Search
============================================================

For disturbed pixels (Hansen loss > 0), find the nearest undisturbed reference
pixel that has the most similar spectral signature to the pre-disturbance state.

This combines Strategy 3 (nearest undisturbed neighbor) with Strategy 4
(spectral similarity matching) from PRE_ALPHAEARTH_TRIANGULATION_PLAN.md.

Architecture:
    1. For each disturbed pixel, build a pre-disturbance Landsat spectral vector
       (median composite from 2 years before lossyear)
    2. Within a search radius (1-10km), constrained by:
       - Same RESOLVE ecoregion
       - Elevation within ±100m (SRTM)
       - loss == 0 (undisturbed in Hansen)
       - treecover2000 >= 25%
    3. Compute spectral distance between pre-disturbance signature and each
       candidate pixel's current Landsat signature
    4. Select the best-match reference pixel
    5. Sample AlphaEarth at the reference pixel
    6. Export to BQ with proxy metadata

Input:  Disturbed pixels from phase_c_embeddings_env_v1 (232K pixels)
Output: BQ table with reference pixel AlphaEarth embeddings + proxy metadata

Usage:
    python3 regime3_reference_sampler.py --test 100
    python3 regime3_reference_sampler.py --pool-size 25 --resume-from-bq
"""

import argparse
import ee
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from google.cloud import bigquery

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_SOURCE_TABLE = 'phase_c_embeddings_env_v1'
BQ_OUTPUT_TABLE_FAST = 'regime3_reference_fast_v1'       # Proximity-based (fast, ~20 hours)
BQ_OUTPUT_TABLE_SPECTRAL = 'regime3_reference_spectral_v1'  # Spectral-similarity (slow, ~10 days)

# GEE assets
ALPHAEARTH_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
SRTM_ASSET = 'USGS/SRTMGL1_003'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2024_v1_12'
RESOLVE_ASSET = 'RESOLVE/ECOREGIONS/2017'

# Search parameters
SEARCH_RADIUS_M = 10000                   # 10km search buffer radius
SEARCH_SCALE_M = 250                      # Scale for reduceRegion search (250m = ~5K px per 10km buffer)
                                          # Reference coords at 250m precision, AE sampled at 10m
ELEVATION_TOLERANCE_M = 100               # ±100m elevation band
MIN_TREECOVER = 25                        # Minimum Hansen treecover2000 (%)
MIN_CANDIDATES = 5                         # Minimum candidate pixels needed

# Landsat spectral features (11 features per pixel)
SPECTRAL_BANDS = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
SPECTRAL_INDICES = ['NDVI', 'EVI', 'NBR', 'NDMI', 'SAVI']

# Processing
BATCH_SIZE = 50           # Pixels per GEE task (small because each pixel requires neighbor search)
POOL_SIZE = 25
TASK_TIMEOUT_MIN = 60
MAX_RETRIES = 3
POLL_INTERVAL_SEC = 30

# AlphaEarth bands
AE_BANDS = [f'A{i:02d}' for i in range(64)]


# =============================================================================
# LANDSAT COMPOSITE BUILDERS
# =============================================================================

def get_landsat_collection_for_year(year: int) -> ee.ImageCollection:
    """Get the appropriate Landsat surface reflectance collection for a given year.
    
    Harmonizes band names across Landsat 5/7/8/9 to a common set:
    Blue, Green, Red, NIR, SWIR1, SWIR2
    
    Uses Collection 2 Level-2 (surface reflectance).
    """
    start = f'{year}-01-01'
    end = f'{year}-12-31'
    
    def mask_clouds_l457(image):
        """Cloud mask for Landsat 4/5/7 using QA_PIXEL."""
        qa = image.select('QA_PIXEL')
        cloud = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud bit
        shadow = qa.bitwiseAnd(1 << 4).eq(0)  # Cloud shadow bit
        return image.updateMask(cloud).updateMask(shadow)
    
    def mask_clouds_l89(image):
        """Cloud mask for Landsat 8/9 using QA_PIXEL."""
        qa = image.select('QA_PIXEL')
        cloud = qa.bitwiseAnd(1 << 3).eq(0)
        shadow = qa.bitwiseAnd(1 << 4).eq(0)
        cirrus = qa.bitwiseAnd(1 << 2).eq(0)
        return image.updateMask(cloud).updateMask(shadow).updateMask(cirrus)
    
    def rename_l457(image):
        """Rename Landsat 5/7 bands to common names."""
        return image.select(
            ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
            ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
        ).multiply(0.0000275).add(-0.2)  # Scale to reflectance
    
    def rename_l89(image):
        """Rename Landsat 8/9 bands to common names."""
        return image.select(
            ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
            ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
        ).multiply(0.0000275).add(-0.2)  # Scale to reflectance
    
    collections = []
    
    if year <= 2012:
        # Landsat 5 (1984-2012)
        l5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
              .filterDate(start, end)
              .map(mask_clouds_l457)
              .map(rename_l457))
        collections.append(l5)
    
    if 1999 <= year <= 2022:
        # Landsat 7 (1999-present, SLC-off from 2003)
        l7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
              .filterDate(start, end)
              .map(mask_clouds_l457)
              .map(rename_l457))
        collections.append(l7)
    
    if year >= 2013:
        # Landsat 8 (2013-present)
        l8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
              .filterDate(start, end)
              .map(mask_clouds_l89)
              .map(rename_l89))
        collections.append(l8)
    
    if year >= 2022:
        # Landsat 9 (2021-present)
        l9 = (ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
              .filterDate(start, end)
              .map(mask_clouds_l89)
              .map(rename_l89))
        collections.append(l9)
    
    if not collections:
        # Fallback: use earliest available
        l5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
              .filterDate('1984-01-01', '1986-12-31')
              .map(mask_clouds_l457)
              .map(rename_l457))
        collections.append(l5)
    
    # Merge all applicable collections
    merged = collections[0]
    for c in collections[1:]:
        merged = merged.merge(c)
    
    return merged


def build_spectral_composite(year: int, window: int = 2) -> ee.Image:
    """Build a median Landsat spectral composite for a year window.
    
    Produces 11 bands: 6 surface reflectance + 5 spectral indices.
    Uses a +/-window year range to maximize cloud-free coverage.
    """
    # Collect across the window
    all_collections = []
    for y in range(year - window, year + window + 1):
        all_collections.append(get_landsat_collection_for_year(y))
    
    merged = all_collections[0]
    for c in all_collections[1:]:
        merged = merged.merge(c)
    
    # Median composite
    composite = merged.median()
    
    # Compute spectral indices
    ndvi = composite.normalizedDifference(['NIR', 'Red']).rename('NDVI')
    evi = composite.expression(
        '2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))',
        {'NIR': composite.select('NIR'),
         'Red': composite.select('Red'),
         'Blue': composite.select('Blue')}
    ).rename('EVI')
    nbr = composite.normalizedDifference(['NIR', 'SWIR2']).rename('NBR')
    ndmi = composite.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')
    savi = composite.expression(
        '1.5 * (NIR - Red) / (NIR + Red + 0.5)',
        {'NIR': composite.select('NIR'),
         'Red': composite.select('Red')}
    ).rename('SAVI')
    
    return composite.addBands([ndvi, evi, nbr, ndmi, savi]).unmask(0).toFloat()


# =============================================================================
# REFERENCE PIXEL SEARCH
# =============================================================================

def build_candidate_mask(eco_id: int, center_elev: float) -> ee.Image:
    """Build a binary mask of valid reference pixel candidates.
    
    Criteria:
    - Same RESOLVE ecoregion
    - Elevation within ±100m
    - Hansen treecover2000 >= 25%
    - Hansen loss == 0 (never disturbed)
    
    Returns a binary mask (1 = valid candidate, 0 = not).
    """
    # Ecoregion mask
    ecoregions = ee.FeatureCollection(RESOLVE_ASSET)
    eco_mask = ecoregions.filter(ee.Filter.eq('ECO_ID', eco_id)).reduceToImage(
        properties=['ECO_ID'],
        reducer=ee.Reducer.first()
    ).gt(0).unmask(0)
    
    # Elevation mask (±100m)
    srtm = ee.Image(SRTM_ASSET).select('elevation')
    elev_mask = (srtm.gte(center_elev - ELEVATION_TOLERANCE_M)
                 .And(srtm.lte(center_elev + ELEVATION_TOLERANCE_M)))
    
    # Hansen forest mask
    hansen = ee.Image(HANSEN_ASSET)
    forest_mask = hansen.select('treecover2000').gte(MIN_TREECOVER)
    undisturbed_mask = hansen.select('loss').eq(0)
    
    # Combine all criteria
    return eco_mask.And(elev_mask).And(forest_mask).And(undisturbed_mask)


def find_reference_pixel_for_point(
    lat: float,
    lon: float, 
    lossyear: int,
    eco_id: int,
    elevation: float,
) -> dict:
    """Find the best spectrally-similar undisturbed reference pixel (ad-hoc test version).
    
    This is the single-pixel interactive test version of the core C3 algorithm.
    For batch processing, use batch_find_references() instead.
    
    Returns a dict with reference coordinates, spectral distance, and AE embedding.
    """
    point = ee.Geometry.Point([lon, lat])
    
    # Pre-disturbance year (2 years before Hansen loss)
    pre_disturbance_year = 2000 + int(lossyear) - 2
    if pre_disturbance_year < 1984:
        pre_disturbance_year = 1984
    
    # Build spectral composites
    pre_composite = build_spectral_composite(pre_disturbance_year, window=2)
    current_composite = build_spectral_composite(2023, window=1)
    
    # Get the pre-disturbance spectral vector at this pixel
    all_spectral_bands = SPECTRAL_BANDS + SPECTRAL_INDICES
    pre_values = pre_composite.select(all_spectral_bands).reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=30,
        bestEffort=True
    ).getInfo()
    
    # Build candidate mask
    candidate_mask = build_candidate_mask(int(eco_id), float(elevation))
    
    # Compute spectral distance image
    distance_bands = []
    for band in all_spectral_bands:
        pre_val = pre_values.get(band, 0) or 0
        diff = current_composite.select(band).subtract(ee.Number(pre_val)).pow(2)
        distance_bands.append(diff)
    
    spectral_distance = ee.ImageCollection(distance_bands).toBands().reduce(
        ee.Reducer.sum()
    ).sqrt().rename('spectral_dist')
    
    # Mask to valid candidates
    spectral_distance = spectral_distance.updateMask(candidate_mask)
    
    # Search within 10km buffer
    buffer = point.buffer(10000)
    lon_img = ee.Image.pixelLonLat().select('longitude')
    lat_img = ee.Image.pixelLonLat().select('latitude')
    srtm = ee.Image(SRTM_ASSET).select('elevation')
    
    # Build candidate: spectral_dist + coords + elev
    candidate = (spectral_distance
                .addBands(lon_img.rename('ref_lon'))
                .addBands(lat_img.rename('ref_lat'))
                .addBands(srtm.rename('ref_elev'))
                .updateMask(candidate_mask))
    
    ref_data = candidate.reduceRegion(
        reducer=ee.Reducer.min(4),
        geometry=buffer,
        scale=30,
        bestEffort=True,
        maxPixels=1e8
    ).getInfo()
    
    result = {
        'latitude': lat,
        'longitude': lon,
        'lossyear': lossyear,
        'eco_id': eco_id,
        'elevation': elevation,
        'pre_disturbance_year': pre_disturbance_year,
        'pre_spectral': pre_values,
    }
    
    if ref_data.get('min') is not None and ref_data['min'] >= 0:
        ref_lon = ref_data['min1']
        ref_lat = ref_data['min2']
        ref_elev = ref_data['min3']
        spec_dist = ref_data['min']
        
        # Physical distance
        dx = (ref_lon - lon) * 111320
        dy = (ref_lat - lat) * 110540
        phys_dist = (dx**2 + dy**2) ** 0.5
        
        result.update({
            'reference_found': True,
            'reference_lat': ref_lat,
            'reference_lon': ref_lon,
            'reference_elevation': ref_elev,
            'spectral_distance': spec_dist,
            'proxy_distance_m': phys_dist,
        })
        
        # Sample AlphaEarth at reference pixel
        ae = (ee.ImageCollection(ALPHAEARTH_COLLECTION)
              .filterDate('2023-01-01', '2023-12-31')
              .mosaic())
        ref_point = ee.Geometry.Point([ref_lon, ref_lat])
        ae_val = ae.sample(region=ref_point, scale=10, numPixels=1).first().getInfo()
        if ae_val:
            result['ae_embedding'] = {k: v for k, v in ae_val['properties'].items() 
                                       if k.startswith('A')}
    else:
        result['reference_found'] = False
    
    return result


def batch_find_references(
    disturbed_pixels: pd.DataFrame,
    batch_idx: int,
    lossyear: int = None,
) -> Optional[str]:
    """Process a batch of disturbed pixels to find spectrally-similar reference pixels.
    
    Combines Strategy 3 (nearest undisturbed neighbor) with Strategy 4 (spectral
    similarity matching) from PRE_ALPHAEARTH_TRIANGULATION_PLAN.md.
    
    IMPORTANT: All pixels in a batch MUST share the same lossyear. This is enforced
    by the main loop which groups by lossyear before batching. Sharing a lossyear
    means ONE pre-disturbance Landsat composite serves the entire batch, avoiding
    the expensive ee.Algorithms.If conditional chain that caused 20+ min task times.
    
    Architecture:
        Pass 1: Build ONE pre-disturbance Landsat composite (2 years before lossyear).
                For each disturbed pixel, sample the pre-disturbance spectral vector
                at its location, then find the undisturbed candidate within 10km whose
                CURRENT spectral signature best matches the pre-disturbance signature.
                Uses ee.Reducer.min(4) on spectral distance (Euclidean across 11 bands).
        
        Pass 2: Sample AlphaEarth (.mosaic()) at all found reference pixel locations.
                Export to BigQuery with proxy metadata (spectral_distance, physical
                distance, proxy type, etc).
    
    Args:
        disturbed_pixels: DataFrame with latitude, longitude, lossyear, eco_id,
                         elevation, occurrence_year. All rows must have same lossyear.
        batch_idx: Unique batch index for GEE task naming.
        lossyear: Hansen lossyear value (1-24 = 2001-2024). If None, inferred from data.
    """
    if lossyear is None:
        lossyear = int(disturbed_pixels['lossyear'].iloc[0])
    
    # Pre-disturbance year: 2 years before loss event
    pre_disturbance_year = 2000 + lossyear - 2
    if pre_disturbance_year < 1984:
        pre_disturbance_year = 1984
    
    # Build features
    features = []
    for _, row in disturbed_pixels.iterrows():
        lat = float(row['latitude'])
        lon = float(row['longitude'])
        elevation = float(row['elevation'])
        
        # Prevent GEE INTEGER type inference for exact-integer coordinates
        def ensure_float(v):
            f = float(v)
            if f == int(f):
                f += 1e-10
            return f
        
        feat = ee.Feature(
            ee.Geometry.Point([lon, lat]),
            {
                'latitude': ensure_float(lat),
                'longitude': ensure_float(lon),
                'lossyear': lossyear,
                'eco_id': int(row['eco_id']),
                'elevation': elevation,
                'occurrence_year': int(row.get('occurrence_year', 2000 + lossyear)),
            }
        )
        features.append(feat)
    
    fc = ee.FeatureCollection(features)
    
    # --- Shared datasets (constructed once, used by all pixels in batch) ---
    hansen = ee.Image(HANSEN_ASSET)
    srtm = ee.Image(SRTM_ASSET).select('elevation')
    
    # Global candidate mask: forested + undisturbed
    forest_mask = hansen.select('treecover2000').gte(MIN_TREECOVER)
    undisturbed_mask = hansen.select('loss').eq(0)
    base_mask = forest_mask.And(undisturbed_mask)
    
    # ONE pre-disturbance composite for all pixels in this batch (same lossyear)
    pre_composite = build_spectral_composite(pre_disturbance_year, window=2)
    all_spectral_bands = SPECTRAL_BANDS + SPECTRAL_INDICES
    
    # Current Landsat composite (2022-2024 window)
    current_composite = build_spectral_composite(2023, window=1)
    
    # Pixel coordinate images
    lon_img = ee.Image.pixelLonLat().select('longitude')
    lat_img = ee.Image.pixelLonLat().select('latitude')
    
    # --- PASS 1: Find best spectrally-similar reference pixel ---
    def find_reference(feature):
        """GEE-side: find undisturbed pixel with best spectral match to pre-disturbance state.
        
        For this pixel's pre-disturbance spectral vector (sampled at its location
        from the shared pre_composite), find the candidate within 10km whose current
        spectral signature has minimum Euclidean distance.
        
        Candidate criteria: treecover2000 >= 25%, loss == 0, elevation ±100m.
        """
        geom = feature.geometry()
        elev = ee.Number(feature.get('elevation'))
        center_lat = ee.Number(feature.get('latitude'))
        center_lon = ee.Number(feature.get('longitude'))
        
        # Elevation band mask (±100m of source pixel)
        elev_mask = (srtm.gte(elev.subtract(ELEVATION_TOLERANCE_M))
                     .And(srtm.lte(elev.add(ELEVATION_TOLERANCE_M))))
        
        # Combined validity: forested + undisturbed + similar elevation
        valid_mask = base_mask.And(elev_mask)
        
        # Search buffer
        buffer = geom.buffer(SEARCH_RADIUS_M)
        
        # Sample pre-disturbance spectral vector at this pixel
        pre_values = pre_composite.select(all_spectral_bands).reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=geom,
            scale=30,
            bestEffort=True
        )
        
        # Compute spectral distance: Euclidean distance across 11 bands
        # between each candidate pixel's CURRENT spectra and this pixel's
        # PRE-DISTURBANCE spectra. Lower = better match.
        distance_bands = []
        for band in all_spectral_bands:
            pre_val = ee.Number(ee.Algorithms.If(
                pre_values.get(band), pre_values.get(band), 0
            ))
            diff_sq = current_composite.select(band).subtract(pre_val).pow(2)
            distance_bands.append(diff_sq)
        
        spectral_dist = (ee.ImageCollection(distance_bands)
                         .toBands()
                         .reduce(ee.Reducer.sum())
                         .sqrt()
                         .rename('spectral_dist'))
        
        # Build candidate image: spectral_dist + coordinates + elevation
        # Masked to valid candidates only. Ranked by spectral_dist (band 0).
        candidate = (spectral_dist
                    .addBands(lon_img.rename('ref_lon'))
                    .addBands(lat_img.rename('ref_lat'))
                    .addBands(srtm.rename('ref_elev'))
                    .updateMask(valid_mask))
        
        # ee.Reducer.min(4): pixel with minimum spectral_dist, return all 4 bands.
        # Use SEARCH_SCALE_M (250m) instead of 30m for the search grid.
        # This reduces the search from ~350K pixels to ~5K pixels per 10km buffer,
        # making each reduceRegion ~70x faster. Reference pixel coordinates will be
        # at 250m precision, but AE is sampled at 10m at those coords.
        ref_data = candidate.reduceRegion(
            reducer=ee.Reducer.min(4),
            geometry=buffer,
            scale=SEARCH_SCALE_M,
            bestEffort=True,
            maxPixels=1e8
        )
        
        # min(4) keys: min=spectral_dist, min1=lon, min2=lat, min3=elev
        spec_dist = ee.Number(ee.Algorithms.If(
            ref_data.get('min'), ref_data.get('min'), -1
        )).float()
        ref_lon = ee.Number(ee.Algorithms.If(
            ref_data.get('min1'), ref_data.get('min1'), 0
        )).float()
        ref_lat = ee.Number(ee.Algorithms.If(
            ref_data.get('min2'), ref_data.get('min2'), 0
        )).float()
        ref_elev = ee.Number(ee.Algorithms.If(
            ref_data.get('min3'), ref_data.get('min3'), 0
        )).float()
        
        found = spec_dist.gte(0)
        
        # Physical distance to chosen reference (metadata only)
        ref_phys_dx = ref_lon.subtract(center_lon).multiply(111320)
        ref_phys_dy = ref_lat.subtract(center_lat).multiply(110540)
        ref_phys_dist = ref_phys_dx.pow(2).add(ref_phys_dy.pow(2)).sqrt()
        
        return feature.set({
            'reference_lat': ref_lat,
            'reference_lon': ref_lon,
            'proxy_distance_m': ref_phys_dist,
            'reference_elevation': ref_elev,
            'spectral_distance': spec_dist,
            'reference_found': found,
            'pre_disturbance_year': pre_disturbance_year,
        })
    
    # Apply reference search to all features in batch
    referenced = fc.map(find_reference)
    
    # --- PASS 2: Sample AlphaEarth at reference pixels ---
    found_features = referenced.filter(ee.Filter.eq('reference_found', 1))
    
    def set_ref_geometry(feature):
        ref_lon = ee.Number(feature.get('reference_lon'))
        ref_lat = ee.Number(feature.get('reference_lat'))
        return feature.setGeometry(ee.Geometry.Point([ref_lon, ref_lat]))
    
    ref_points = found_features.map(set_ref_geometry)
    
    # AlphaEarth: .mosaic() merges all 11K+ tiles for global coverage
    ae = (ee.ImageCollection(ALPHAEARTH_COLLECTION)
          .filterDate('2023-01-01', '2023-12-31')
          .mosaic())
    
    # SRTM anchor band prevents empty sampleRegions when points fall between
    # AE grid cells (same fix proven in temporal_env_sampler.py)
    anchor = ee.Image(SRTM_ASSET).select('elevation').rename('anchor_elevation')
    ae_with_anchor = ae.addBands(anchor).unmask(0)
    
    sampled = ae_with_anchor.sampleRegions(
        collection=ref_points,
        scale=10,
        geometries=False,
        tileScale=4
    )
    
    # Add proxy metadata, then strip anchor + system properties
    def finalize_for_bq(feature):
        feat = feature.set({
            'proxy_type': 'nearest_spectral_match',
            'proxy_ae_year': 2023,
        })
        # Get property names AFTER setting new properties
        return feat.select(
            feat.propertyNames()
                .filter(ee.Filter.neq('item', 'system:index'))
                .filter(ee.Filter.neq('item', 'anchor_elevation'))
        )
    
    sampled = sampled.map(finalize_for_bq)
    
    # Export to BigQuery
    ly_str = f'ly{lossyear:02d}'
    task_desc = f'r3_{ly_str}_{datetime.now().strftime("%Y%m%d")}_{batch_idx:05d}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        table=f'{PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE_SPECTRAL}',
        description=task_desc,
        append=True,
    )
    task.start()
    
    return task.id


# =============================================================================
# FAST (PROXIMITY-BASED) REFERENCE SEARCH
# =============================================================================

def batch_find_references_fast(
    disturbed_pixels: pd.DataFrame,
    batch_idx: int,
) -> Optional[str]:
    """FAST proximity-based reference pixel search.
    
    Finds the NEAREST undisturbed pixel (by physical distance) within a 10km
    buffer, constrained by elevation (±100m), treecover (>=25%), and undisturbed
    (Hansen loss==0). Then samples AlphaEarth at that reference location.
    
    This is ~10-20x faster than the spectral-similarity version because:
    - No Landsat composite construction
    - No spectral distance computation (11 bands per pixel)
    - Simpler candidate image (1 distance band vs 11 spectral bands)
    
    Trade-off: The reference pixel is the nearest valid neighbor, not the
    best spectral match. Within the same elevation band and forest type,
    nearby pixels are usually ecologically similar, so this is a reasonable
    approximation for initial model training.
    
    Output goes to BQ_OUTPUT_TABLE_FAST (separate from spectral version).
    """
    features = []
    for _, row in disturbed_pixels.iterrows():
        lat = float(row['latitude'])
        lon = float(row['longitude'])
        
        def ensure_float(v):
            f = float(v)
            if f == int(f):
                f += 1e-10
            return f
        
        feat = ee.Feature(
            ee.Geometry.Point([lon, lat]),
            {
                'latitude': ensure_float(lat),
                'longitude': ensure_float(lon),
                'lossyear': int(row['lossyear']),
                'eco_id': int(row['eco_id']),
                'elevation': float(row['elevation']),
                'occurrence_year': int(row.get('occurrence_year', 2000 + int(row['lossyear']))),
            }
        )
        features.append(feat)
    
    fc = ee.FeatureCollection(features)
    
    # Shared datasets
    hansen = ee.Image(HANSEN_ASSET)
    srtm = ee.Image(SRTM_ASSET).select('elevation')
    forest_mask = hansen.select('treecover2000').gte(MIN_TREECOVER)
    undisturbed_mask = hansen.select('loss').eq(0)
    base_mask = forest_mask.And(undisturbed_mask)
    lon_img = ee.Image.pixelLonLat().select('longitude')
    lat_img = ee.Image.pixelLonLat().select('latitude')
    
    def find_nearest_reference(feature):
        """Find nearest undisturbed pixel by physical distance only."""
        geom = feature.geometry()
        elev = ee.Number(feature.get('elevation'))
        center_lat = ee.Number(feature.get('latitude'))
        center_lon = ee.Number(feature.get('longitude'))
        
        # Elevation band (±100m)
        elev_mask = (srtm.gte(elev.subtract(ELEVATION_TOLERANCE_M))
                     .And(srtm.lte(elev.add(ELEVATION_TOLERANCE_M))))
        valid_mask = base_mask.And(elev_mask)
        
        buffer = geom.buffer(SEARCH_RADIUS_M)
        
        # Physical distance only
        dx = lon_img.subtract(center_lon).multiply(111320)
        dy = lat_img.subtract(center_lat).multiply(110540)
        dist_m = dx.pow(2).add(dy.pow(2)).sqrt().rename('dist_m')
        
        # Candidate: dist + coords + elev, masked to valid
        candidate = (dist_m
                    .addBands(lon_img.rename('ref_lon'))
                    .addBands(lat_img.rename('ref_lat'))
                    .addBands(srtm.rename('ref_elev'))
                    .updateMask(valid_mask))
        
        # Nearest candidate (min physical distance)
        ref_data = candidate.reduceRegion(
            reducer=ee.Reducer.min(4),
            geometry=buffer,
            scale=30,  # 30m for proximity (fast, no spectral computation)
            bestEffort=True,
            maxPixels=1e8
        )
        
        ref_dist = ee.Number(ee.Algorithms.If(
            ref_data.get('min'), ref_data.get('min'), -1
        )).float()
        ref_lon = ee.Number(ee.Algorithms.If(
            ref_data.get('min1'), ref_data.get('min1'), 0
        )).float()
        ref_lat = ee.Number(ee.Algorithms.If(
            ref_data.get('min2'), ref_data.get('min2'), 0
        )).float()
        ref_elev = ee.Number(ee.Algorithms.If(
            ref_data.get('min3'), ref_data.get('min3'), 0
        )).float()
        
        found = ref_dist.gte(0)
        
        return feature.set({
            'reference_lat': ref_lat,
            'reference_lon': ref_lon,
            'proxy_distance_m': ref_dist,
            'reference_elevation': ref_elev,
            'reference_found': found,
        })
    
    # Apply search
    referenced = fc.map(find_nearest_reference)
    found_features = referenced.filter(ee.Filter.eq('reference_found', 1))
    
    def set_ref_geometry(feature):
        ref_lon = ee.Number(feature.get('reference_lon'))
        ref_lat = ee.Number(feature.get('reference_lat'))
        return feature.setGeometry(ee.Geometry.Point([ref_lon, ref_lat]))
    
    ref_points = found_features.map(set_ref_geometry)
    
    # Sample AlphaEarth at reference locations (mosaic, not first!)
    ae = (ee.ImageCollection(ALPHAEARTH_COLLECTION)
          .filterDate('2023-01-01', '2023-12-31')
          .mosaic())
    anchor = ee.Image(SRTM_ASSET).select('elevation').rename('anchor_elevation')
    ae_with_anchor = ae.addBands(anchor).unmask(0)
    
    sampled = ae_with_anchor.sampleRegions(
        collection=ref_points,
        scale=10,
        geometries=False,
        tileScale=4
    )
    
    def finalize_for_bq(feature):
        feat = feature.set({
            'proxy_type': 'nearest_undisturbed',
            'proxy_ae_year': 2023,
        })
        return feat.select(
            feat.propertyNames()
                .filter(ee.Filter.neq('item', 'system:index'))
                .filter(ee.Filter.neq('item', 'anchor_elevation'))
        )
    
    sampled = sampled.map(finalize_for_bq)
    
    task_desc = f'r3fast_{datetime.now().strftime("%Y%m%d")}_{batch_idx:05d}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        table=f'{PROJECT}.{BQ_DATASET}.{BQ_OUTPUT_TABLE_FAST}',
        description=task_desc,
        append=True,
    )
    task.start()
    
    return task.id


# =============================================================================
# DATA LOADING
# =============================================================================

def load_disturbed_pixels() -> pd.DataFrame:
    """Load disturbed pixels from BQ (Phase C data with Hansen loss > 0)."""
    print("  Loading disturbed pixels from BigQuery...")
    client = bigquery.Client(project=PROJECT)
    
    query = f"""
        SELECT DISTINCT
            latitude,
            longitude,
            CAST(ROUND(latitude * 10000) AS INT64) AS lat4,
            CAST(ROUND(longitude * 10000) AS INT64) AS lon4,
            lossyear,
            elevation,
            CAST(eco_id AS INT64) as eco_id,
            treecover2000
        FROM `{PROJECT}.{BQ_DATASET}.{BQ_SOURCE_TABLE}`
        WHERE loss > 0 AND lossyear > 0
        ORDER BY eco_id, lossyear
    """
    
    df = client.query(query).to_dataframe()
    print(f"  Loaded {len(df):,} disturbed pixels")
    print(f"  Lossyear range: {df['lossyear'].min()} - {df['lossyear'].max()}")
    print(f"  Ecoregions: {df['eco_id'].nunique()}")
    print(f"  Elevation range: {df['elevation'].min():.0f} - {df['elevation'].max():.0f}m")
    
    return df


# =============================================================================
# ROLLING POOL (same pattern as temporal_env_sampler.py)
# =============================================================================

def run_rolling_pool(
    all_batches: List[Tuple],
    pool_size: int = POOL_SIZE,
    max_retries: int = MAX_RETRIES,
    mode: str = 'fast',
):
    """Run batches through a rolling pool of GEE export tasks.
    
    Args:
        mode: 'fast' for proximity-only or 'spectral' for spectral-similarity.
    """
    
    total = len(all_batches)
    mode_label = 'PROXIMITY (FAST)' if mode == 'fast' else 'SPECTRAL SIMILARITY (SLOW)'
    print(f"\n{'=' * 60}")
    print(f"SAMPLING {total} BATCHES — {mode_label}")
    print(f"{'=' * 60}")
    print(f"  Pool size: {pool_size} concurrent tasks")
    print(f"  Max retries per batch: {max_retries}")
    
    active_tasks = {}  # task_id -> (batch_info, submit_time, retry_count)
    queue = list(range(total))
    completed = 0
    failed_permanent = 0
    retry_queue = []
    start_time = time.time()
    
    def submit_one(batch_idx, retries=0):
        """Submit a single batch using the appropriate function."""
        if mode == 'fast':
            batch_df, global_idx = all_batches[batch_idx][:2]
            try:
                task_id = batch_find_references_fast(batch_df, global_idx)
                if task_id:
                    active_tasks[task_id] = (batch_idx, time.time(), retries)
                    return True
            except Exception as e:
                print(f"  ERROR submitting fast batch {global_idx}: {e}")
        else:
            batch_df, global_idx, lossyear = all_batches[batch_idx]
            try:
                task_id = batch_find_references(batch_df, global_idx, lossyear=lossyear)
                if task_id:
                    active_tasks[task_id] = (batch_idx, time.time(), retries)
                    return True
            except Exception as e:
                print(f"  ERROR submitting spectral batch {global_idx} (ly={lossyear}): {e}")
        return False
    
    # Initial pool fill
    initial_count = min(pool_size, len(queue))
    for _ in range(initial_count):
        if queue:
            idx = queue.pop(0)
            submit_one(idx)
    
    print(f"\n  Initial pool: {len(active_tasks)} tasks submitted")
    
    # Poll loop
    while active_tasks or queue or retry_queue:
        time.sleep(POLL_INTERVAL_SEC)
        
        # Check task status
        try:
            task_list = ee.data.getTaskList()
            task_map = {t['id']: t for t in task_list}
        except Exception:
            continue
        
        completed_this_cycle = []
        failed_this_cycle = []
        
        for task_id, (batch_idx, submit_time, retries) in list(active_tasks.items()):
            if task_id not in task_map:
                continue
            
            status = task_map[task_id]
            state = status['state']
            
            if state == 'COMPLETED':
                completed_this_cycle.append(task_id)
                completed += 1
                
            elif state == 'FAILED':
                error = status.get('error_message', 'unknown')
                if retries < max_retries:
                    retry_queue.append((batch_idx, retries + 1))
                else:
                    failed_permanent += 1
                    print(f"  PERMANENT FAIL batch {batch_idx}: {error[:100]}")
                failed_this_cycle.append(task_id)
                
            elif state in ('RUNNING', 'READY'):
                # Check timeout
                elapsed = (time.time() - submit_time) / 60
                if elapsed > TASK_TIMEOUT_MIN:
                    try:
                        ee.data.cancelTask(task_id)
                    except:
                        pass
                    if retries < max_retries:
                        retry_queue.append((batch_idx, retries + 1))
                    else:
                        failed_permanent += 1
                    failed_this_cycle.append(task_id)
        
        # Remove finished tasks
        for tid in completed_this_cycle + failed_this_cycle:
            if tid in active_tasks:
                del active_tasks[tid]
        
        # Fill pool from retry queue first, then main queue
        while len(active_tasks) < pool_size and (retry_queue or queue):
            if retry_queue:
                batch_idx, retries = retry_queue.pop(0)
                submit_one(batch_idx, retries=retries)
            elif queue:
                idx = queue.pop(0)
                submit_one(idx)
        
        # Progress
        n_active = len(active_tasks)
        n_retry = len(retry_queue)
        n_queued = len(queue)
        elapsed = (time.time() - start_time) / 60
        # Use actual batch sizes from all_batches (may differ from BATCH_SIZE constant)
        pixels_done = sum(len(all_batches[i][0]) for i in range(min(completed, total)))
        
        if completed > 0:
            rate = completed / elapsed
            remaining = total - completed - failed_permanent
            eta = remaining / rate / 60 if rate > 0 else 0
        else:
            eta = 0
        
        print(f"  [{completed}/{total}] {completed} ok, {failed_permanent} fail, "
              f"{n_active} active, {n_retry} retry, {n_queued} queued | "
              f"~{pixels_done:,} px | {elapsed:.0f}min, ~{eta:.1f}hr left")
    
    elapsed = (time.time() - start_time) / 60
    print(f"\n{'=' * 60}")
    print(f"REGIME 3 SAMPLING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed_permanent}")
    print(f"  Time: {elapsed:.1f} min")
    if completed + failed_permanent > 0:
        print(f"  Success rate: {completed/(completed+failed_permanent)*100:.1f}%")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Regime 3: Reference pixel search for disturbed pixels',
        epilog="""
MODES:
  --fast      Proximity-based nearest undisturbed pixel (default, ~20 hrs)
              Output: regime3_reference_fast_v1
  --spectral  Landsat spectral-similarity ranking (~10 days)
              Output: regime3_reference_spectral_v1

EXAMPLES:
  # Test fast mode with 200 random pixels
  python3 regime3_reference_sampler.py --fast --test 200

  # Full fast production run
  PYTHONUNBUFFERED=1 nohup python3 -u regime3_reference_sampler.py --fast \\
    --pool-size 25 --resume-from-bq > regime3_fast_production.log 2>&1 &

  # Full spectral production run (long!)
  PYTHONUNBUFFERED=1 nohup python3 -u regime3_reference_sampler.py --spectral \\
    --pool-size 10 --resume-from-bq > regime3_spectral_production.log 2>&1 &
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--pool-size', type=int, default=POOL_SIZE)
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES)
    parser.add_argument('--test', type=int, default=0,
                        help='Test with N random pixels (0 = full run)')
    parser.add_argument('--resume-from-bq', action='store_true',
                        help='Skip pixels already in output BQ table')
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--fast', action='store_true',
                           help='Fast proximity-based search (~20 hrs for 232K pixels)')
    mode_group.add_argument('--spectral', action='store_true',
                           help='Slow spectral-similarity search (~10 days for 232K pixels)')
    
    args = parser.parse_args()
    mode = 'fast' if args.fast else 'spectral'
    bq_output = BQ_OUTPUT_TABLE_FAST if mode == 'fast' else BQ_OUTPUT_TABLE_SPECTRAL
    
    # Batch size: fast can handle larger batches (no Landsat composites).
    # Tested: 2000 px in 13.6 min (147 px/min), 500 px in 9.4 min (53 px/min).
    # 2000 is optimal — the reduceRegion per pixel dominates, batch overhead is amortized.
    batch_size = 2000 if mode == 'fast' else BATCH_SIZE
    
    mode_label = 'PROXIMITY (FAST)' if mode == 'fast' else 'SPECTRAL SIMILARITY (SLOW)'
    print("=" * 70)
    print(f"REGIME 3: {mode_label} REFERENCE PIXEL SEARCH")
    print("For disturbed pixels, find undisturbed reference neighbors")
    print(f"Output: {bq_output}")
    print("=" * 70)
    
    # Initialize GEE
    print("\nInitializing Google Earth Engine...")
    ee.Initialize(project=PROJECT)
    print(f"  GEE initialized (project: {PROJECT})")
    
    # Load disturbed pixels
    pixels = load_disturbed_pixels()
    
    # Resume from BQ
    if args.resume_from_bq:
        print(f"\n  Loading completed pixels from {bq_output}...")
        try:
            client = bigquery.Client(project=PROJECT)
            query = f"""
                SELECT DISTINCT
                    CAST(ROUND(latitude * 10000) AS INT64) AS lat4,
                    CAST(ROUND(longitude * 10000) AS INT64) AS lon4
                FROM `{PROJECT}.{BQ_DATASET}.{bq_output}`
            """
            done_df = client.query(query).to_dataframe()
            before = len(pixels)
            done_merge = pd.DataFrame({'lat4': done_df['lat4'], 'lon4': done_df['lon4']})
            done_merge['_done'] = True
            pixels = pixels.merge(done_merge, on=['lat4', 'lon4'], how='left')
            pixels = pixels[pixels['_done'].isna()].drop(columns=['_done']).copy()
            print(f"    Resume: {before:,} -> {len(pixels):,} (skipped {before - len(pixels):,})")
        except Exception as e:
            print(f"    No existing data to resume from: {e}")
    
    # Test mode
    if args.test > 0:
        pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
        print(f"  TEST MODE: {len(pixels)} random pixels")
    
    if len(pixels) == 0:
        print("  No pixels to process!")
        return
    
    # Build batches
    if mode == 'spectral':
        # Spectral mode: group by lossyear (shared pre-disturbance composite)
        all_batches = []
        batch_counter = 0
        lossyear_groups = pixels.groupby('lossyear')
        
        print(f"\n  Lossyear distribution:")
        for ly, group in sorted(lossyear_groups):
            n_batches = (len(group) + batch_size - 1) // batch_size
            print(f"    ly={int(ly)} (year {2000+int(ly)}): {len(group):,} pixels -> {n_batches} batches")
            group_shuffled = group.sample(frac=1, random_state=42)
            for i in range(0, len(group_shuffled), batch_size):
                batch_df = group_shuffled.iloc[i:i + batch_size]
                all_batches.append((batch_df, batch_counter, int(ly)))
                batch_counter += 1
    else:
        # Fast mode: no lossyear grouping needed, just shuffle and batch
        pixels_shuffled = pixels.sample(frac=1, random_state=42)
        all_batches = []
        for i in range(0, len(pixels_shuffled), batch_size):
            batch_df = pixels_shuffled.iloc[i:i + batch_size]
            all_batches.append((batch_df, i // batch_size))
    
    print(f"\n  Mode: {mode_label}")
    print(f"  Total batches: {len(all_batches)}")
    print(f"  Batch size: {batch_size} pixels")
    print(f"  Total pixels: {len(pixels):,}")
    
    # Run
    run_rolling_pool(
        all_batches,
        pool_size=args.pool_size,
        max_retries=args.max_retries,
        mode=mode,
    )


if __name__ == '__main__':
    main()
