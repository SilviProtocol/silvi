#!/usr/bin/env python3
"""
unified_gee_sampler_v3.py — SINR v3 unified GEE feature sampler.

Samples ALL features for SINR v3 training:
  1. AlphaEarth embeddings for ALL 8 years (2017-2024) → 512 raw values per point
  2. Full environmental feature stack (same 61+ bands as v2.2)
  3. Temporal stack: MODIS LC at obs/AE year, Hansen gain, TerraClimate VPD delta
  4. (Future backfill: HILDA+, ESA CCI, WRI drivers — added as separate columns later)

Two modes:
  --new-gbif        Sample all features at 15.25M new GBIF occurrence locations
  --backfill        Sample AE 8 years + temporal stack at existing training data locations
  --all             Both of the above

Architecture:
  1. Load point populations from BigQuery
  2. Deduplicate to unique (lat4dp, lon4dp, emb_year) pixels (AE is per-pixel)
  3. Group into batches of 2000 points
  4. For each batch:
     a. Sample AlphaEarth at all 8 years (2017-2024) → 512 bands
     b. Sample env features at native scales → ~61 bands
     c. Sample temporal stack features → ~6 bands (MODIS LC at obs, MODIS LC at AE, etc.)
     d. Export combined FeatureCollection to BigQuery
  5. Rolling pool of 25 concurrent GEE tasks with retry logic

Output BQ tables:
  - species_data.sinr_v3_features_new_gbif   (new GBIF data, all features)
  - species_data.sinr_v3_features_backfill   (existing data, AE 8yr + temporal stack)

Usage:
  python3 unified_gee_sampler_v3.py --new-gbif --pool-size 25
  python3 unified_gee_sampler_v3.py --backfill --pool-size 25
  python3 unified_gee_sampler_v3.py --all --pool-size 25
  python3 unified_gee_sampler_v3.py --new-gbif --pool-size 25 --resume-from-bq
"""

import argparse
import ee
import json
import math
import numpy as np
import os
import pandas as pd
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_TABLE_NEW_GBIF = 'sinr_v3_features_new_gbif'
BQ_TABLE_BACKFILL = 'sinr_v3_features_backfill'

AE_SCALE = 10               # AlphaEarth native resolution
STATIC_SCALE = 30           # Finest static dataset (SRTM)
BATCH_SIZE = 2000            # Points per GEE task (proven optimal)
MIN_BATCH_SIZE = 50          # Minimum — smaller batches merged with previous
TASK_TIMEOUT_MIN = 60        # Kill tasks taking longer than this
POLL_INTERVAL_SEC = 30       # How often to check task status
MAX_RETRIES = 5              # Max retries per failed batch

AE_YEARS = list(range(2017, 2025))  # 2017-2024, 8 years
ARCTIC_LAT_THRESHOLD = 59.0

# GEE Asset IDs
SRTM_ASSET = 'USGS/SRTMGL1_003'
COPERNICUS_DEM_ASSET = 'COPERNICUS/DEM/GLO30'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2024_v1_12'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ensure_float(v):
    """Prevent integer coords from causing BQ type conflicts."""
    f = float(v)
    if f == int(f):
        f += 1e-10
    return f


def log(msg):
    """Timestamped logging."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# GEE IMAGE BUILDERS
# =============================================================================

def get_ae_image(year: int) -> ee.Image:
    """Get AlphaEarth mosaic for a specific year with band renaming."""
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    mosaic = col.mosaic()
    # Rename A00-A63 to ae_YYYY_00 through ae_YYYY_63
    old_names = [f'A{i:02d}' for i in range(64)]
    new_names = [f'ae_{year}_{i:02d}' for i in range(64)]
    return mosaic.select(old_names, new_names)


def get_ae_all_years_image() -> ee.Image:
    """Stack all 8 years of AlphaEarth into a single 512-band image."""
    images = [get_ae_image(year) for year in AE_YEARS]
    combined = images[0]
    for img in images[1:]:
        combined = combined.addBands(img)
    # Unmask with 0 so missing years produce 0 (not drop the point)
    return combined.unmask(0)


def get_primary_ae_image(year: int) -> ee.Image:
    """Get the primary AE embedding for a specific observation year.
    
    Returns 64 bands named emb_00..emb_63.
    For years outside 2017-2024, falls back to 2017.
    """
    ae_year = year if 2017 <= year <= 2024 else 2017
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{ae_year}-01-01', f'{ae_year}-12-31'
    )
    mosaic = col.mosaic()
    old_names = [f'A{i:02d}' for i in range(64)]
    new_names = [f'emb_{i:02d}' for i in range(64)]
    return mosaic.select(old_names, new_names).unmask(0)


def get_dem_image(has_arctic: bool = False) -> ee.Image:
    """DEM with arctic fallback to Copernicus."""
    srtm = ee.Image(SRTM_ASSET)
    terrain = ee.Terrain.products(srtm)
    dem_stack = terrain.select(
        ['elevation', 'slope', 'aspect', 'hillshade']
    ).toFloat()  # Cast all bands to float for BQ compatibility
    
    if has_arctic:
        cop_dem = (ee.ImageCollection(COPERNICUS_DEM_ASSET)
                   .select('DEM').mosaic().rename('elevation'))
        cop_terrain = ee.Terrain.products(cop_dem)
        cop_stack = cop_terrain.select(
            ['elevation', 'slope', 'aspect', 'hillshade']
        ).toFloat()
        # Use Copernicus above threshold
        arctic_mask = ee.Image.pixelLonLat().select('latitude').gt(ARCTIC_LAT_THRESHOLD)
        dem_stack = dem_stack.where(arctic_mask, cop_stack)
    
    return dem_stack.unmask(0)


def get_static_env_image() -> ee.Image:
    """All static (year-independent) environmental features."""
    
    # WorldClim BIO variables (19 bands)
    bio = ee.Image('WORLDCLIM/V1/BIO')
    bio_bands = bio.select([f'bio{i:02d}' for i in range(1, 20)])
    
    # Soil (OpenLandMap, all at surface 0cm = band b0)
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')
    soil_clay = ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_clay_pct')
    soil_sand = ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_sand_pct')
    soil_oc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('soil_organic_carbon')
    soil_tex = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture_class')
    soil_bd = ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('soil_bulk_density')
    soil_wc = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01').select('b0').rename('soil_water_content')
    
    # Hansen GFC
    hansen = ee.Image(HANSEN_ASSET)
    hansen_stack = hansen.select(
        ['treecover2000', 'lossyear', 'gain'],
        ['treecover2000', 'lossyear', 'hansen_gain']
    )
    
    # JRC Forest Type
    jrc_type = ee.Image('JRC/GFC2020_subtypes/V1').select('Map').rename('jrc_forest_type')
    
    # JRC TMF
    jrc_tmf = ee.ImageCollection('projects/JRC/TMF/v1_2024/TransitionMap_Subtypes').mosaic()
    jrc_tmf_status = jrc_tmf.select('TransitionMap_Subtypes').rename('jrc_tmf_status')
    jrc_degrad = ee.ImageCollection('projects/JRC/TMF/v1_2024/DegradationYear').mosaic()
    jrc_degrad_yr = jrc_degrad.select('constant').rename('jrc_tmf_degrad_year')
    
    # ESA WorldCover 2021
    esa_wc = ee.ImageCollection('ESA/WorldCover/v200').mosaic()
    esa_wc_band = esa_wc.select('Map').rename('esa_worldcover_2021')
    
    # SBTN Natural Lands
    sbtn = ee.Image('WRI/SBTN/naturalLands/v1_1/2020').select('natural').rename('sbtn_natural_land')
    
    # JRC Surface Water
    jrc_water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
    water_stack = jrc_water.select(
        ['occurrence', 'recurrence', 'seasonality'],
        ['water_occurrence', 'water_recurrence', 'water_seasonality']
    )
    
    # MERIT Hydro
    merit = ee.Image('MERIT/Hydro/v1_0_1')
    merit_stack = merit.select(['hnd', 'upa'], ['merit_hand_m', 'merit_upstream_area_km2'])
    
    # GEDI — use specific metric images, NOT .mosaic() on the full collection
    gedi_rh98 = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
    gedi_fhd = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316')
    gedi_stack = ee.Image.cat(
        gedi_rh98.select('p95').rename('gedi_canopy_height_m'),
        gedi_fhd.select('shan').rename('gedi_foliage_height_div')
    )
    
    # Biomass
    biomass = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic()
    biomass_band = biomass.select('agb').rename('biomass_agb_mgha')
    
    # Human modification
    hm = ee.ImageCollection('CSP/HM/GlobalHumanModification').mosaic()
    hm_band = hm.select('gHM').rename('human_modification')
    
    # Topo diversity
    topo = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').select('constant').rename('topo_diversity')
    
    # RESOLVE ecoregions (rasterized from FeatureCollection)
    eco = ee.FeatureCollection('RESOLVE/ECOREGIONS/2017')
    eco_id = eco.reduceToImage(properties=['ECO_ID'], reducer=ee.Reducer.first()).rename('eco_id')
    biome_num = eco.reduceToImage(properties=['BIOME_NUM'], reducer=ee.Reducer.first()).rename('biome_num')
    
    # Plantation datasets
    # Xiao et al. 2024 Global Natural & Planted Forests (30m)
    # RGB encoding: Green (0,127,0)=natural, Yellow (127,127,0)=planted, White/other=non-forest
    # FIXED 2026-03-08: was incorrectly looking for red (255,0,0) instead of yellow (127,127,0)
    xiao_raw = ee.ImageCollection('projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS').mosaic()
    xiao_b1 = xiao_raw.select('b1')
    xiao_b2 = xiao_raw.select('b2')
    xiao_b3 = xiao_raw.select('b3')
    is_natural = xiao_b1.eq(0).And(xiao_b2.eq(127)).And(xiao_b3.eq(0))      # Green (0,127,0)
    is_planted = xiao_b1.eq(127).And(xiao_b2.eq(127)).And(xiao_b3.eq(0))    # Yellow (127,127,0)
    xiao_band = ee.Image(0).where(is_natural, 1).where(is_planted, 2).rename('xiao_planted_forest').toInt()
    
    neumann = ee.ImageCollection(
        'projects/nature-trace/assets/forest_typology/natural_forest_2020_v1_0_collection'
    ).mosaic()
    neumann_band = neumann.select('B0').rename('neumann_natural_prob')
    
    # Stack everything
    combined = (bio_bands
        .addBands(soil_ph).addBands(soil_clay).addBands(soil_sand)
        .addBands(soil_oc).addBands(soil_tex).addBands(soil_bd).addBands(soil_wc)
        .addBands(hansen_stack)
        .addBands(jrc_type).addBands(jrc_tmf_status).addBands(jrc_degrad_yr)
        .addBands(esa_wc_band).addBands(sbtn)
        .addBands(water_stack)
        .addBands(merit_stack)
        .addBands(gedi_stack)
        .addBands(biomass_band)
        .addBands(hm_band)
        .addBands(topo)
        .addBands(eco_id).addBands(biome_num)
        .addBands(xiao_band).addBands(neumann_band)
    )
    
    return combined.unmask(0)


def get_temporal_env_for_year(year: int) -> ee.Image:
    """Year-specific temporal environmental features."""
    
    # TerraClimate (+/-2yr window)
    center_year = max(1958, min(year, 2024))
    start_year = max(1958, center_year - 2)
    end_year = min(2025, center_year + 3)
    
    tc = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
          .filterDate(f'{start_year}-01-01', f'{end_year}-01-01')
          .select(['vpd', 'aet', 'soil', 'pdsi', 'def', 'srad']))
    tc_mean = tc.mean()
    tc_stack = (tc_mean.select('vpd').rename('tc_vpd_mean')
        .addBands(tc_mean.select('aet').rename('tc_aet_mean'))
        .addBands(tc_mean.select('soil').rename('tc_soil_moisture_mean'))
        .addBands(tc_mean.select('pdsi').rename('tc_pdsi_mean'))
        .addBands(tc_mean.select('def').rename('tc_water_deficit_mean'))
        .addBands(tc_mean.select('srad').rename('tc_solar_rad_mean'))
    )
    
    # Dynamic World (2015+, pre-2015 falls back to ESA WorldCover remapped)
    if year >= 2015:
        dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
              .filterDate(f'{year}-01-01', f'{year}-12-31')
              .select('label'))
        dw_band = dw.mode().rename('dynamic_world')
    else:
        # Remap ESA WorldCover to DW class codes
        esa = ee.ImageCollection('ESA/WorldCover/v200').mosaic().select('Map')
        dw_band = esa.remap(
            [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
            [1, 5, 2, 4, 6, 7, 8, 0, 3, 1, 7]
        ).rename('dynamic_world')
    
    # MODIS GPP (2001+; MOD17A3HGF has no 2000 image)
    if year >= 2001:
        modis_year = min(year, 2023)
        gpp_col = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
                   .filterDate(f'{modis_year}-01-01', f'{modis_year+1}-01-01'))
        # The annual collection is available from 2001 onward. For prediction /
        # historical reconstruction we avoid future leakage and keep a 0 proxy in
        # raw extraction before coverage starts rather than borrowing 2001 values.
        # Downstream semantic repair / release builders are responsible for
        # converting those pre-2001 proxy zeros into NULL + provenance.
        gpp_band = gpp_col.mosaic().select('Gpp').updateMask(
            gpp_col.mosaic().select('Gpp').lt(65530)
        ).unmask(0).rename('modis_gpp_mean')
    else:
        gpp_band = ee.Image.constant(0).rename('modis_gpp_mean')
    
    # Fire frequency (cumulative MODIS burned area, 2001-year)
    if year >= 2001:
        fire_year = min(year, 2024)
        fire = (ee.ImageCollection('MODIS/061/MCD64A1')
                .filterDate('2001-01-01', f'{fire_year}-12-31')
                .select('BurnDate'))
        fire_band = fire.map(lambda img: img.gt(0)).sum().rename('fire_frequency_count')
    else:
        fire_band = ee.Image.constant(0).rename('fire_frequency_count')
    
    # Nighttime lights (VIIRS, 2012+)
    if year >= 2012:
        lights_year = min(year, 2024)
        lights = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
                  .filterDate(f'{lights_year}-01-01', f'{lights_year}-12-31')
                  .select('avg_rad'))
        lights_band = lights.mean().rename('nighttime_lights')
    else:
        lights_band = ee.Image.constant(0).rename('nighttime_lights')
    
    combined = (tc_stack
        .addBands(dw_band)
        .addBands(gpp_band)
        .addBands(fire_band)
        .addBands(lights_band)
    )
    
    return combined.unmask(0)


def get_temporal_stack_features(obs_year: int, ae_year: int) -> ee.Image:
    """NEW v3 temporal stack features: MODIS LC at obs/AE, TerraClimate VPD delta.
    
    These are the temporal stack features available in GEE right now.
    HILDA+ and ESA CCI will be added later as backfill.
    """
    bands = []
    
    # Ensure ae_year is valid
    ae_year = max(2001, min(ae_year, 2024))
    
    # MODIS Land Cover at observation year (2001-2024)
    if obs_year is not None and obs_year >= 2001:
        modis_obs_year = min(obs_year, 2023)
        modis_lc_obs = (ee.ImageCollection('MODIS/061/MCD12Q1')
                        .filterDate(f'{modis_obs_year}-01-01', f'{modis_obs_year+1}-01-01')
                        .mosaic()
                        .select('LC_Type1')
                        .unmask(-1)
                        .rename('modis_lc_at_obs'))
        bands.append(modis_lc_obs)
    else:
        bands.append(ee.Image.constant(-1).rename('modis_lc_at_obs'))  # -1 = unavailable
    
    # MODIS Land Cover at AE year
    modis_ae_year = min(ae_year, 2023)
    modis_lc_ae = (ee.ImageCollection('MODIS/061/MCD12Q1')
                   .filterDate(f'{modis_ae_year}-01-01', f'{modis_ae_year+1}-01-01')
                   .mosaic()
                   .select('LC_Type1')
                   .unmask(-1)
                   .rename('modis_lc_at_ae'))
    bands.append(modis_lc_ae)
    
    # TerraClimate VPD delta (VPD at AE year minus VPD at obs year)
    if obs_year is not None and obs_year >= 1958:
        clamped_obs = max(1958, min(obs_year, 2024))
        tc_obs = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
                  .filterDate(f'{clamped_obs}-01-01', f'{clamped_obs+1}-01-01')
                  .select('vpd').mean())
        clamped_ae = max(1958, min(ae_year, 2024))
        tc_ae = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
                 .filterDate(f'{clamped_ae}-01-01', f'{clamped_ae+1}-01-01')
                 .select('vpd').mean())
        vpd_delta = tc_ae.subtract(tc_obs).unmask(0).rename('tc_vpd_delta')
        bands.append(vpd_delta)
    else:
        bands.append(ee.Image.constant(0).rename('tc_vpd_delta'))
    
    combined = bands[0]
    for b in bands[1:]:
        combined = combined.addBands(b)
    
    return combined.unmask(0)


# =============================================================================
# POINT LOADING FROM BIGQUERY
# =============================================================================

def load_new_gbif_points():
    """Load new GBIF occurrence points from BigQuery."""
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    
    query = f"""
    SELECT
        taxon_id,
        decimallatitude as latitude,
        decimallongitude as longitude,
        observation_year,
        emb_year,
        lat4dp,
        lon4dp,
        basis_of_record,
        coord_uncertainty_m,
        establishmentmeans
    FROM `{PROJECT}.{BQ_DATASET}.gbif_new_occurrences`
    """
    
    log(f"Loading new GBIF points from BigQuery...")
    df = client.query(query).to_dataframe()
    log(f"Loaded {len(df):,} points ({df['taxon_id'].nunique():,} species)")
    return df


def load_existing_coords():
    """Load existing training data coordinates for backfill."""
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    
    query = f"""
    SELECT
        taxon_id,
        latitude,
        longitude,
        occurrence_year as observation_year,
        emb_year,
        CAST(ROUND(latitude, 4) AS FLOAT64) as lat4dp,
        CAST(ROUND(longitude, 4) AS FLOAT64) as lon4dp
    FROM `{PROJECT}.{BQ_DATASET}.existing_training_coords`
    """
    
    log(f"Loading existing coords from BigQuery...")
    df = client.query(query).to_dataframe()
    log(f"Loaded {len(df):,} points ({df['taxon_id'].nunique():,} species)")
    return df


def load_completed_pixels(bq_table: str) -> Set[str]:
    """Load already-completed pixel keys from BQ for resume."""
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    
    try:
        query = f"""
        SELECT DISTINCT
            CONCAT(CAST(latitude AS STRING), '|', CAST(longitude AS STRING))
            as pixel_key
        FROM `{PROJECT}.{BQ_DATASET}.{bq_table}`
        """
        result = client.query(query).to_dataframe()
        keys = set(result['pixel_key'].values)
        log(f"Found {len(keys):,} completed pixels in {bq_table}")
        return keys
    except Exception as e:
        log(f"No existing data in {bq_table} (starting fresh): {e}")
        return set()


# =============================================================================
# PIXEL DEDUP AND BATCHING
# =============================================================================

def dedup_to_pixels(df, mode: str) -> list:
    """Deduplicate to unique sampling pixels.
    
    For new GBIF: dedup to unique (lat4dp, lon4dp) — sample once per pixel,
    rejoin taxon_id/metadata later in BQ.
    
    For backfill: same — we only need to sample GEE features per pixel,
    not per observation.
    
    Returns list of dicts with pixel info for GEE sampling.
    """
    log(f"Deduplicating {len(df):,} rows to unique pixels...")
    
    # Fast dedup: sort by pixel + obs_year desc, then drop_duplicates
    df = df.sort_values('observation_year', ascending=False, na_position='last')
    pixel_groups = df.drop_duplicates(subset=['lat4dp', 'lon4dp'], keep='first')
    
    log(f"Building pixel list from {len(pixel_groups):,} unique pixels...")
    
    # Vectorized conversion to list of dicts
    lats = pixel_groups['lat4dp'].values
    lons = pixel_groups['lon4dp'].values
    obs_years = pixel_groups['observation_year'].values
    emb_years = pixel_groups['emb_year'].values
    
    pixels = []
    for i in range(len(lats)):
        obs_year = int(obs_years[i]) if pd.notna(obs_years[i]) else None
        emb_year = int(emb_years[i]) if pd.notna(emb_years[i]) else 2017
        pixels.append({
            'lat': float(lats[i]),
            'lon': float(lons[i]),
            'obs_year': obs_year,
            'emb_year': emb_year,
        })
    
    log(f"Deduplicated to {len(pixels):,} unique pixels")
    return pixels


def create_batches(pixels: list, batch_size: int = BATCH_SIZE) -> list:
    """Create batches of pixels for GEE tasks.
    
    Shuffles to prevent geographic clustering (which can cause
    GEE memory issues for dense regions).
    """
    random.shuffle(pixels)
    
    batches = []
    for i in range(0, len(pixels), batch_size):
        batch = pixels[i:i + batch_size]
        if len(batch) < MIN_BATCH_SIZE and batches:
            # Merge trailing small batch into previous
            batches[-1].extend(batch)
        else:
            batches.append(batch)
    
    log(f"Created {len(batches)} batches ({batch_size} pixels each)")
    return batches


# =============================================================================
# GEE SAMPLING
# =============================================================================

def sample_batch_new_gbif(batch: list, batch_idx: int, bq_table: str) -> Optional[str]:
    """Submit a GEE task to sample all features for a batch of new GBIF pixels.
    
    Returns the GEE task ID, or None if submission failed.
    """
    # Check if batch has arctic points
    has_arctic = any(p['lat'] > ARCTIC_LAT_THRESHOLD for p in batch)
    
    # Build feature collection from points
    features = []
    for p in batch:
        geom = ee.Geometry.Point([ensure_float(p['lon']), ensure_float(p['lat'])])
        props = {
            'latitude': ensure_float(p['lat']),
            'longitude': ensure_float(p['lon']),
            'observation_year': int(p['obs_year']) if p['obs_year'] is not None else -9999,
            'emb_year': int(p['emb_year']),
        }
        features.append(ee.Feature(geom, props))
    
    fc = ee.FeatureCollection(features)
    
    # Determine representative obs_year for this batch (for temporal features)
    # Use median obs_year of the batch. Default to 2020 if all null.
    obs_years = [p['obs_year'] for p in batch if p['obs_year'] is not None and p['obs_year'] > 0]
    representative_obs_year = int(np.median(obs_years)) if obs_years else 2020
    # Clamp to valid range
    representative_obs_year = max(1958, min(representative_obs_year, 2024))
    representative_ae_year = 2020  # Safe default within all dataset ranges
    
    # ---- Build the image stack ----
    
    # 1. DEM + static env
    dem = get_dem_image(has_arctic=has_arctic)
    static_env = get_static_env_image()
    
    # 2. Temporal env at representative obs year
    temporal_env = get_temporal_env_for_year(representative_obs_year)
    
    # 3. Temporal stack (MODIS LC at obs/AE, VPD delta)
    temporal_stack = get_temporal_stack_features(representative_obs_year, representative_ae_year)
    
    # 4. All 8 years of AlphaEarth (512 bands)
    ae_all = get_ae_all_years_image()
    
    # 5. Primary AE embedding at emb_year
    # Note: we use representative_ae_year for the batch, not per-point
    # The per-point emb_year selection happens in post-processing
    primary_ae = get_primary_ae_image(representative_ae_year)
    
    # Stack everything (DEM at 30m as anchor)
    # Cast to float to ensure BQ compatibility (some bands are int/byte)
    combined = (dem
        .addBands(static_env)
        .addBands(temporal_env)
        .addBands(temporal_stack)
        .addBands(ae_all)
        .addBands(primary_ae)
    ).toFloat()
    
    # Sample at AE_SCALE (10m) — sampleRegions handles multi-scale internally
    sampled = combined.sampleRegions(
        collection=fc,
        scale=AE_SCALE,
        geometries=False,
        tileScale=4
    )
    
    # Export to BigQuery
    task_desc = f'sinr_v3_new_gbif_batch_{batch_idx:05d}'
    full_table = f'{PROJECT}.{BQ_DATASET}.{bq_table}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=task_desc,
        table=full_table,
        append=True,
        overwrite=False
    )
    
    try:
        task.start()
        return task.id
    except Exception as e:
        log(f"  ERROR starting task {task_desc}: {e}")
        return None


def sample_batch_backfill(batch: list, batch_idx: int, bq_table: str) -> Optional[str]:
    """Submit a GEE task to sample AE 8 years + temporal stack for existing data.
    
    Only samples what's NEW for v3 (not the full env stack which already exists).
    """
    features = []
    for p in batch:
        geom = ee.Geometry.Point([ensure_float(p['lon']), ensure_float(p['lat'])])
        props = {
            'latitude': ensure_float(p['lat']),
            'longitude': ensure_float(p['lon']),
            'observation_year': int(p['obs_year']) if p['obs_year'] is not None else -9999,
            'emb_year': int(p['emb_year']),
        }
        features.append(ee.Feature(geom, props))
    
    fc = ee.FeatureCollection(features)
    
    # Representative years for this batch
    obs_years = [p['obs_year'] for p in batch if p['obs_year'] is not None and p['obs_year'] > 0]
    representative_obs_year = int(np.median(obs_years)) if obs_years else 2020
    representative_obs_year = max(1958, min(representative_obs_year, 2024))
    representative_ae_year = 2020
    
    # For backfill: only sample AE 8 years + temporal stack (env already exists)
    ae_all = get_ae_all_years_image()
    temporal_stack = get_temporal_stack_features(representative_obs_year, representative_ae_year)
    
    # AE image is already at 10m so it serves as its own anchor — no extra band needed.
    combined = ae_all.addBands(temporal_stack).toFloat()
    
    sampled = combined.sampleRegions(
        collection=fc,
        scale=AE_SCALE,
        geometries=False,
        tileScale=4
    )
    
    task_desc = f'sinr_v3_backfill_batch_{batch_idx:05d}'
    full_table = f'{PROJECT}.{BQ_DATASET}.{bq_table}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=task_desc,
        table=full_table,
        append=True,
        overwrite=False
    )
    
    try:
        task.start()
        return task.id
    except Exception as e:
        log(f"  ERROR starting task {task_desc}: {e}")
        return None


# =============================================================================
# TASK POOL MANAGEMENT
# =============================================================================

def run_sampling_pool(batches: list, sample_fn, bq_table: str, pool_size: int = 25, resume_mode: bool = False):
    """Run GEE sampling with a rolling pool of concurrent tasks.
    
    Args:
        batches: List of pixel batches to sample
        sample_fn: Function to submit a single batch (returns task_id)
        bq_table: Target BQ table name
        pool_size: Max concurrent GEE tasks
        resume_mode: If True, skip staggered start (BQ table already exists)
    """
    total_batches = len(batches)
    active_tasks: Dict[str, dict] = {}  # task_id → {batch_idx, start_time, batch}
    retry_queue: List[Tuple[int, list, int]] = []  # (batch_idx, batch, retry_count)
    completed = 0
    failed = 0
    batch_queue = list(enumerate(batches))  # (batch_idx, batch)
    
    log(f"\n{'='*60}")
    log(f"Starting GEE sampling: {total_batches} batches, pool size {pool_size}")
    log(f"Target table: {PROJECT}.{BQ_DATASET}.{bq_table}")
    log(f"{'='*60}\n")
    
    # --- Staggered start: submit first batch alone to create BQ table ---
    # This prevents "Failed to create a BigQuery stream" errors from
    # multiple tasks racing to create the table simultaneously.
    if batch_queue and not resume_mode:
        first_idx, first_batch = batch_queue.pop(0)
        log(f"  Submitting first batch (#{first_idx}) to initialize BQ table...")
        first_tid = sample_fn(first_batch, first_idx, bq_table)
        if first_tid:
            # Wait for first batch to complete
            while True:
                time.sleep(POLL_INTERVAL_SEC)
                try:
                    st = ee.data.getTaskStatus([first_tid])[0]
                    state = st.get('state', 'UNKNOWN')
                    if state == 'COMPLETED':
                        completed += 1
                        log(f"  ✓ First batch completed. BQ table ready. Ramping up to pool_size={pool_size}")
                        break
                    elif state in ('FAILED', 'CANCELLED'):
                        err = st.get('error_message', 'unknown')
                        log(f"  ✗ First batch failed: {err}. Retrying...")
                        retry_queue.append((first_idx, first_batch, 1))
                        break
                except Exception as e:
                    log(f"  Warning: status check failed: {e}")
        else:
            retry_queue.append((first_idx, first_batch, 1))
    
    while batch_queue or retry_queue or active_tasks:
        # Submit new tasks to fill the pool
        while len(active_tasks) < pool_size and (batch_queue or retry_queue):
            # Prioritize retries
            if retry_queue:
                batch_idx, batch, retry_count = retry_queue.pop(0)
                log(f"  Retrying batch {batch_idx} (attempt {retry_count + 1}/{MAX_RETRIES})")
            elif batch_queue:
                batch_idx, batch = batch_queue.pop(0)
                retry_count = 0
            else:
                break
            
            task_id = sample_fn(batch, batch_idx, bq_table)
            if task_id:
                active_tasks[task_id] = {
                    'batch_idx': batch_idx,
                    'start_time': time.time(),
                    'batch': batch,
                    'retry_count': retry_count,
                }
            else:
                # Submission failed — retry
                if retry_count < MAX_RETRIES:
                    retry_queue.append((batch_idx, batch, retry_count + 1))
                else:
                    failed += 1
                    log(f"  PERMANENT FAILURE: batch {batch_idx} after {MAX_RETRIES} retries")
        
        if not active_tasks:
            break
        
        # Wait and check status
        time.sleep(POLL_INTERVAL_SEC)
        
        # Check all active tasks
        task_ids = list(active_tasks.keys())
        try:
            statuses = ee.data.getTaskStatus(task_ids)
        except Exception as e:
            log(f"  Warning: status check failed: {e}")
            continue
        
        for status in statuses:
            tid = status['id']
            if tid not in active_tasks:
                continue
            
            state = status.get('state', 'UNKNOWN')
            info = active_tasks[tid]
            
            if state == 'COMPLETED':
                completed += 1
                elapsed = time.time() - info['start_time']
                remaining = total_batches - completed - failed
                log(f"  ✓ Batch {info['batch_idx']} completed ({elapsed:.0f}s). "
                    f"Progress: {completed}/{total_batches} ({completed*100/total_batches:.1f}%), "
                    f"~{remaining} remaining")
                del active_tasks[tid]
            
            elif state in ('FAILED', 'CANCEL_REQUESTED', 'CANCELLED'):
                error_msg = status.get('error_message', 'unknown error')
                log(f"  ✗ Batch {info['batch_idx']} failed: {error_msg}")
                del active_tasks[tid]
                
                # Retry unless it's a data issue
                if info['retry_count'] < MAX_RETRIES and 'empty' not in error_msg.lower():
                    retry_queue.append((info['batch_idx'], info['batch'], info['retry_count'] + 1))
                else:
                    failed += 1
            
            elif state in ('RUNNING', 'READY'):
                # Check for timeout
                elapsed = time.time() - info['start_time']
                if elapsed > TASK_TIMEOUT_MIN * 60:
                    log(f"  ⏱ Batch {info['batch_idx']} timed out ({elapsed/60:.1f}min), cancelling")
                    try:
                        ee.data.cancelTask(tid)
                    except:
                        pass
                    del active_tasks[tid]
                    if info['retry_count'] < MAX_RETRIES:
                        retry_queue.append((info['batch_idx'], info['batch'], info['retry_count'] + 1))
                    else:
                        failed += 1
    
    log(f"\n{'='*60}")
    log(f"Sampling complete: {completed} succeeded, {failed} failed out of {total_batches}")
    log(f"{'='*60}\n")
    
    return completed, failed


# =============================================================================
# MAIN
# =============================================================================

def main():
    import pandas as pd  # Import here to avoid issues if not installed
    
    parser = argparse.ArgumentParser(description='SINR v3 unified GEE sampler')
    parser.add_argument('--new-gbif', action='store_true', help='Sample new GBIF data')
    parser.add_argument('--backfill', action='store_true', help='Backfill existing data')
    parser.add_argument('--all', action='store_true', help='Both new GBIF and backfill')
    parser.add_argument('--pool-size', type=int, default=25, help='Max concurrent GEE tasks')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Points per GEE task')
    parser.add_argument('--resume-from-bq', action='store_true', help='Skip already-completed pixels')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of pixels (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Load data and create batches but don\'t submit')
    args = parser.parse_args()
    
    if args.all:
        args.new_gbif = True
        args.backfill = True
    
    if not args.new_gbif and not args.backfill:
        parser.error("Must specify --new-gbif, --backfill, or --all")
    
    # Initialize GEE
    log("Initializing Google Earth Engine...")
    ee.Initialize(project=PROJECT)
    log("GEE initialized.")
    
    batch_size = args.batch_size
    
    # ---- New GBIF sampling ----
    if args.new_gbif:
        log("\n" + "=" * 60)
        log("MODE: New GBIF sampling")
        log("=" * 60)
        
        df = load_new_gbif_points()
        pixels = dedup_to_pixels(df, mode='new_gbif')
        
        if args.resume_from_bq:
            completed_keys = load_completed_pixels(BQ_TABLE_NEW_GBIF)
            before = len(pixels)
            pixels = [p for p in pixels if f"{p['lat']}|{p['lon']}" not in completed_keys]
            log(f"Skipping {before - len(pixels):,} already-completed pixels")
        
        if args.limit:
            pixels = pixels[:args.limit]
            log(f"Limited to {len(pixels)} pixels")
        
        batches = create_batches(pixels, batch_size)
        
        # Free large objects no longer needed — saves ~5GB RAM
        del df, pixels
        if args.resume_from_bq:
            del completed_keys
        import gc; gc.collect()
        
        if args.dry_run:
            log(f"DRY RUN: would submit {len(batches)} batches ({len(pixels)} pixels)")
            return
        
        run_sampling_pool(batches, sample_batch_new_gbif, BQ_TABLE_NEW_GBIF, args.pool_size, 
                         resume_mode=args.resume_from_bq)
    
    # ---- Backfill sampling ----
    if args.backfill:
        log("\n" + "=" * 60)
        log("MODE: Backfill existing data (AE 8yr + temporal stack)")
        log("=" * 60)
        
        df = load_existing_coords()
        pixels = dedup_to_pixels(df, mode='backfill')
        
        if args.resume_from_bq:
            completed_keys = load_completed_pixels(BQ_TABLE_BACKFILL)
            before = len(pixels)
            pixels = [p for p in pixels if f"{p['lat']}|{p['lon']}" not in completed_keys]
            log(f"Skipping {before - len(pixels):,} already-completed pixels")
        
        if args.limit:
            pixels = pixels[:args.limit]
            log(f"Limited to {len(pixels)} pixels")
        
        batches = create_batches(pixels, batch_size)
        
        # Free large objects no longer needed
        del df, pixels
        if args.resume_from_bq:
            del completed_keys
        import gc; gc.collect()
        
        if args.dry_run:
            log(f"DRY RUN: would submit {len(batches)} batches ({len(pixels)} pixels)")
            return
        
        run_sampling_pool(batches, sample_batch_backfill, BQ_TABLE_BACKFILL, args.pool_size,
                         resume_mode=args.resume_from_bq)


if __name__ == '__main__':
    main()
