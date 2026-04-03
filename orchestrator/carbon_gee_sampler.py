#!/usr/bin/env python3
"""
Temporally-Aware Carbon/Biomass GEE Sampler for SINR v3
========================================================
Samples carbon-related features from GEE for all training pixels,
with DUAL TIMESTAMP sampling: features at OBSERVATION YEAR and at
AE EMBEDDING YEAR, plus static features.

Runs on the main GEE account (dev@silvi.earth, project treekipedia-479918).

Target BQ tables:
  - species_data.sinr_v3_carbon_temporal

Datasets sampled:
  STATIC (same for all obs):
    1. Spawn AGB/BGB carbon density (300m, ~2010)
    2. GEDI L4B gridded biomass (1km, 2019-2021)
    3. GEDI GriddedVeg RH98 + FHD (1km, 2019-2023) — FIXED: specific images, not .mosaic()
    4. ETH Global Canopy Height 2020 (10m)
    5. Soil organic carbon at 4 depths: 0, 30, 100, 200cm (250m)
    6. IPCC Forest Classification (30m, 2020)

  TEMPORAL AT OBS YEAR (matched to observation_year):
    7. MODIS Annual NPP (500m, 2001-2024)
    8. MODIS Annual GPP (500m, 2001-2024)
    9. MODIS LAI/FPAR (500m, 2000-2024)
   10. MODIS EVI (500m, 2000-2024)
   11. ESA CCI Biomass v6.0 — AGB + SD (100m, nearest epoch from 2007-2022)

  TEMPORAL AT AE YEAR (matched to emb_year):
   12. Same as 7-11 but for the AE embedding year

  LONGTERM SUMMARY:
   13. NPP mean over full record (2001-2024)
   14. NPP trend (linear fit slope over 2001-2024)

Usage:
  python3 carbon_gee_sampler.py --new-gbif --pool-size 25
  python3 carbon_gee_sampler.py --existing --pool-size 25
  python3 carbon_gee_sampler.py --all --pool-size 25
  python3 carbon_gee_sampler.py --new-gbif --resume-from-bq --pool-size 25
"""

import argparse
import ee
import time
import random
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

GEE_PROJECT = 'treekipedia-479918'

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_TABLE = 'sinr_v3_carbon_temporal'
BQ_FAILED_TABLE = 'sinr_v3_carbon_unsampleable'
LOCAL_FAILED_KEYS_FILE = Path('/tmp/carbon_unsampleable_keys.txt')
FAILED_TABLE_BQ_AVAILABLE = None

BATCH_SIZE = 2500       # Optimized: was 1500, increased for throughput
MIN_BATCH_SIZE = 100
SAMPLE_SCALE = 250      # 250m — matches soil carbon resolution
TASK_TIMEOUT_MIN = 60
POLL_INTERVAL_SEC = 15  # Optimized: was 30, reduced for faster completion detection
MAX_RETRIES = 5

# =============================================================================
# GEE DATASET ASSETS
# =============================================================================

# Static datasets
SPAWN_BIOMASS = 'NASA/ORNL/biomass_carbon_density/v1'
GEDI_L4B = 'LARSE/GEDI/GEDI04_B_002'
# GEDI GriddedVeg — select SPECIFIC metric images, NOT .mosaic() on the collection
GEDI_RH98_IMG = 'LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316'
GEDI_FHD_IMG = 'LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316'
ETH_CANOPY_HEIGHT = 'users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1'
SOIL_ORGANIC_CARBON = 'OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02'
IPCC_FOREST_CLASS = 'NASA/ORNL/global_forest_classification_2020/V1'

# Temporal datasets
MODIS_NPP = 'MODIS/061/MOD17A3HGF'
MODIS_LAI_FPAR = 'MODIS/061/MOD15A2H'
MODIS_EVI = 'MODIS/061/MOD13A1'
ESA_CCI_AGB = 'projects/sat-io/open-datasets/ESA/ESA_CCI_AGB'

# ESA CCI Biomass available epochs
CCI_EPOCHS = [2007, 2010, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]

# =============================================================================
# HELPERS
# =============================================================================

def ensure_float(v):
    """Prevent integer coords from causing BQ type conflicts."""
    f = float(v)
    if f == int(f):
        f += 1e-10
    return f


def log(msg):
    """Timestamped logging."""
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


def make_resume_key(lat, lon, observation_year):
    """Build resume key exactly as used in filtering logic."""
    return f"{round(float(lat), 4)}|{round(float(lon), 4)}|{int(observation_year)}"


def ensure_failed_table_exists():
    """Create BQ table for unsampleable keys if it doesn't exist."""
    global FAILED_TABLE_BQ_AVAILABLE

    if FAILED_TABLE_BQ_AVAILABLE is True:
        return True
    if FAILED_TABLE_BQ_AVAILABLE is False:
        return False

    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    query = f"""
    CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{BQ_DATASET}.{BQ_FAILED_TABLE}` (
      key STRING,
      latitude FLOAT64,
      longitude FLOAT64,
      observation_year INT64,
      emb_year INT64,
      mode STRING,
      reason STRING,
      recorded_at TIMESTAMP
    )
    """
    try:
        client.query(query).result()
        FAILED_TABLE_BQ_AVAILABLE = True
        return True
    except Exception as e:
        FAILED_TABLE_BQ_AVAILABLE = False
        log(f"  Warning: cannot create/use {BQ_FAILED_TABLE} in BQ ({e}). Using local unsampleable key file.")
        return False


def record_unsampleable_local(batch):
    """Persist unsampleable keys locally when BQ table is unavailable."""
    keys = [make_resume_key(p['lat'], p['lon'], p['observation_year']) for p in batch]
    if not keys:
        return
    with LOCAL_FAILED_KEYS_FILE.open('a', encoding='utf-8') as f:
        for k in keys:
            f.write(k + '\n')
    log(f"  Marked {len(keys):,} keys as unsampleable (local file)")


def record_unsampleable_batch(batch, obs_year, emb_year, mode, reason):
    """Persist batch keys that failed with empty FeatureCollection.

    This prevents re-attempting the same unsampleable keys on every restart.
    """
    from google.cloud import bigquery
    if not ensure_failed_table_exists():
        record_unsampleable_local(batch)
        return
    client = bigquery.Client(project=BQ_PROJECT)

    rows = []
    for p in batch:
        rows.append({
            'key': make_resume_key(p['lat'], p['lon'], p['observation_year']),
            'latitude': ensure_float(p['lat']),
            'longitude': ensure_float(p['lon']),
            'observation_year': int(p['observation_year']),
            'emb_year': int(p['emb_year']),
            'mode': mode,
            'reason': reason,
            'recorded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    if not rows:
        return

    table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_FAILED_TABLE}"
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        log(f"  Warning: failed to record unsampleable keys in BQ ({len(errors)} row errors). Falling back to local file.")
        record_unsampleable_local(batch)
    else:
        log(f"  Marked {len(rows):,} keys as unsampleable ({reason})")


def nearest_cci_epoch(year):
    """Find the nearest ESA CCI Biomass epoch for a given year."""
    if year < 2007:
        return None
    best = min(CCI_EPOCHS, key=lambda e: abs(e - year))
    return best


# =============================================================================
# IMAGE CONSTRUCTION
# =============================================================================

def build_static_image():
    """Build composite image with ALL STATIC carbon features.
    
    These features are the same regardless of observation year.
    Returns ee.Image with ~14 bands.
    
    IMPORTANT: All bands are .unmask(-9999) to prevent sampleRegions from
    dropping features when any single band is masked at a location.
    Sentinel value -9999 must be converted to NULL in post-processing.
    """
    bands = []
    
    # 1. Spawn AGB/BGB carbon density (300m, ~2010)
    spawn = ee.ImageCollection(SPAWN_BIOMASS).first()
    bands.append(spawn.select('agb').rename('spawn_agb').unmask(-9999))
    bands.append(spawn.select('agb_uncertainty').rename('spawn_agb_unc').unmask(-9999))
    bands.append(spawn.select('bgb').rename('spawn_bgb').unmask(-9999))
    bands.append(spawn.select('bgb_uncertainty').rename('spawn_bgb_unc').unmask(-9999))
    
    # 2. GEDI L4B gridded biomass (1km, 2019-2021) — this is a single Image, NOT ImageCollection
    gedi_l4b = ee.Image(GEDI_L4B)
    bands.append(gedi_l4b.select('MU').rename('gedi_l4b_agbd').unmask(-9999))
    bands.append(gedi_l4b.select('SE').rename('gedi_l4b_agbd_se').unmask(-9999))
    
    # 3. GEDI GriddedVeg — FIXED: select specific metric images by asset ID
    gedi_rh98 = ee.Image(GEDI_RH98_IMG)
    bands.append(gedi_rh98.select('p95').rename('gedi_rh98').unmask(-9999))
    
    gedi_fhd = ee.Image(GEDI_FHD_IMG)
    bands.append(gedi_fhd.select('shan').rename('gedi_fhd').unmask(-9999))
    
    # 4. ETH Global Canopy Height 2020 (10m)
    canopy = ee.Image(ETH_CANOPY_HEIGHT).rename('canopy_height_m')
    bands.append(canopy.unmask(-9999))
    
    # 5. Soil organic carbon at 4 depths (250m) — skip b10, b60 (correlated)
    soc = ee.Image(SOIL_ORGANIC_CARBON)
    bands.append(soc.select('b0').divide(5.0).rename('soc_0cm').unmask(-9999))
    bands.append(soc.select('b30').divide(5.0).rename('soc_30cm').unmask(-9999))
    bands.append(soc.select('b100').divide(5.0).rename('soc_100cm').unmask(-9999))
    bands.append(soc.select('b200').divide(5.0).rename('soc_200cm').unmask(-9999))
    
    # 6. IPCC Forest Classification (30m, 2020) — tiled collection, need .mosaic()
    ipcc = ee.ImageCollection(IPCC_FOREST_CLASS).mosaic()
    bands.append(ipcc.select('classification').rename('ipcc_forest_class').unmask(-9999))
    
    # Stack all static bands
    combined = bands[0]
    for b in bands[1:]:
        combined = combined.addBands(b)
    
    return combined.toFloat()


def build_temporal_image_for_year(year, suffix):
    """Build composite image with TEMPORAL carbon features for a specific year.
    
    Args:
        year: The target year (int)
        suffix: Band name suffix ('_at_obs' or '_at_ae')
    
    Returns ee.Image with 7 bands, named with suffix.
    All bands .unmask(-9999) to prevent sampleRegions from dropping features.
    """
    bands = []
    
    # Clamp year to available MODIS range (2001-2024)
    modis_year = max(2001, min(2024, year))
    
    # 7. MODIS Annual NPP for this year (500m)
    # MOD17A3HGF has annual images, filter to the target year
    # Fill values: Npp >= 32700 is fill, Gpp >= 65530 is fill
    npp_col = ee.ImageCollection(MODIS_NPP).filter(
        ee.Filter.calendarRange(modis_year, modis_year, 'year')
    )
    npp_raw = npp_col.select('Npp').mean()
    npp_img = npp_raw.updateMask(npp_raw.lt(32700)).multiply(0.0001)
    bands.append(npp_img.rename(f'npp{suffix}').unmask(-9999))
    
    # 8. MODIS Annual GPP for this year (from same MOD17A3HGF product)
    gpp_raw = npp_col.select('Gpp').mean()
    gpp_img = gpp_raw.updateMask(gpp_raw.lt(65530)).multiply(0.0001)
    bands.append(gpp_img.rename(f'gpp{suffix}').unmask(-9999))
    
    # 9. MODIS LAI/FPAR — annual mean for this year (500m)
    # Fill values: LAI >= 249 is fill/saturated, FPAR >= 249 is fill
    lai_year_start = f'{modis_year}-01-01'
    lai_year_end = f'{modis_year}-12-31'
    lai_fpar = ee.ImageCollection(MODIS_LAI_FPAR).filterDate(lai_year_start, lai_year_end)
    lai_raw = lai_fpar.select('Lai_500m').mean()
    lai_img = lai_raw.updateMask(lai_raw.lt(249)).multiply(0.1)
    bands.append(lai_img.rename(f'lai{suffix}').unmask(-9999))
    fpar_raw = lai_fpar.select('Fpar_500m').mean()
    fpar_img = fpar_raw.updateMask(fpar_raw.lt(249)).multiply(0.01)
    bands.append(fpar_img.rename(f'fpar{suffix}').unmask(-9999))
    
    # 10. MODIS EVI — annual mean for this year (500m)
    evi_year_start = f'{modis_year}-01-01'
    evi_year_end = f'{modis_year}-12-31'
    evi_col = ee.ImageCollection(MODIS_EVI).filterDate(evi_year_start, evi_year_end).select('EVI')
    evi_img = evi_col.mean().multiply(0.0001)
    bands.append(evi_img.rename(f'evi{suffix}').unmask(-9999))
    
    # 11. ESA CCI Biomass v6.0 — nearest epoch AGB + SD (100m)
    cci_epoch = nearest_cci_epoch(year)
    if cci_epoch is not None:
        cci_id = f'CCI_BIOMASS_100m_AGB_{cci_epoch}_V6'
        cci_col = ee.ImageCollection(ESA_CCI_AGB)
        cci_img = cci_col.filter(ee.Filter.eq('system:index', cci_id)).first()
        bands.append(cci_img.select('AGB').rename(f'cci_agb{suffix}').unmask(-9999))
        bands.append(cci_img.select('SD').rename(f'cci_agb_sd{suffix}').unmask(-9999))
    else:
        # Pre-2007: fill with -9999 sentinel (will be masked by has_cci_biomass flag)
        bands.append(ee.Image.constant(-9999).toFloat().rename(f'cci_agb{suffix}'))
        bands.append(ee.Image.constant(-9999).toFloat().rename(f'cci_agb_sd{suffix}'))
    
    # Stack temporal bands
    combined = bands[0]
    for b in bands[1:]:
        combined = combined.addBands(b)
    
    return combined.toFloat()


def build_longterm_image():
    """Build composite image with long-term NPP summary features.
    
    Returns ee.Image with 2 bands:
      - npp_mean_longterm: mean NPP over full MODIS record (kgC/m²/yr)
      - npp_trend: linear trend slope over time (kgC/m²/yr per year)
    """
    npp_col = ee.ImageCollection(MODIS_NPP).select('Npp')
    
    # Mask fill values (>= 32700) BEFORE computing stats
    npp_masked = npp_col.map(lambda img: img.updateMask(img.lt(32700)))
    
    # Long-term mean (in scaled units: multiply by 0.0001 → kgC/m²/yr)
    npp_mean = npp_masked.mean().multiply(0.0001).rename('npp_mean_longterm')
    
    # Linear trend over time — needs [year, npp] band order for linearFit
    def add_time_band(img):
        year = ee.Number(img.date().get('year'))
        return img.addBands(ee.Image.constant(year).float().rename('year'))
    
    npp_with_time = npp_masked.map(add_time_band)
    npp_trend = npp_with_time.select(['year', 'Npp']).reduce(
        ee.Reducer.linearFit()
    ).select('scale').multiply(0.0001).rename('npp_trend')
    
    return npp_mean.unmask(-9999).addBands(npp_trend.unmask(-9999)).toFloat()


# =============================================================================
# DATA LOADING
# =============================================================================

def load_pixels_with_years(mode):
    """Load pixels with observation_year and emb_year from BQ.
    
    Unlike the old version that only loaded (lat, lon), this loads
    (lat, lon, observation_year, emb_year) because we need temporal matching.
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    
    if mode == 'new_gbif':
        log("Loading new GBIF pixels with years from BigQuery...")
        query = f"""
        SELECT 
            ROUND(latitude, 4) as lat,
            ROUND(longitude, 4) as lon,
            CAST(observation_year AS INT64) as observation_year,
            CAST(emb_year AS INT64) as emb_year
        FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_new_gbif`
        """
    elif mode == 'existing':
        log("Loading existing training pixels with years from BigQuery...")
        # For existing data, we need to join with the backfill table or v2.2 train
        # to get observation_year and emb_year
        query = f"""
        SELECT 
            ROUND(latitude, 4) as lat,
            ROUND(longitude, 4) as lon,
            CAST(observation_year AS INT64) as observation_year,
            CAST(emb_year AS INT64) as emb_year
        FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_backfill`
        """
    else:
        raise ValueError(f"Unknown mode: {mode}")
    
    df = client.query(query).to_dataframe()
    log(f"Loaded {len(df):,} pixels with temporal info")
    return df


def load_completed_keys(bq_table):
    """Load already-completed pixel keys from BQ for resume."""
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)
    
    try:
        query = f"""
        SELECT DISTINCT 
            CONCAT(
                CAST(ROUND(latitude, 4) AS STRING), '|', 
                CAST(ROUND(longitude, 4) AS STRING), '|',
                CAST(observation_year AS STRING)
            ) as key
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{bq_table}`
        """
        df = client.query(query).to_dataframe()
        keys = set(df['key'].values)
        log(f"Found {len(keys):,} completed pixel-years in {bq_table}")
        return keys
    except Exception as e:
        log(f"No completed pixels found (table may not exist): {e}")
        return set()


def load_unsampleable_keys():
    """Load keys previously marked unsampleable (empty FeatureCollection)."""
    keys = set()

    # Try BQ-backed unsampleable keys first
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=BQ_PROJECT)
        query = f"""
        SELECT DISTINCT key
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_FAILED_TABLE}`
        """
        df = client.query(query).to_dataframe()
        keys.update(df['key'].values)
        log(f"Found {len(df):,} unsampleable pixel-years in {BQ_FAILED_TABLE}")
    except Exception as e:
        log(f"No unsampleable key table found (or empty): {e}")

    # Also include local fallback file keys
    if LOCAL_FAILED_KEYS_FILE.exists():
        with LOCAL_FAILED_KEYS_FILE.open('r', encoding='utf-8') as f:
            for line in f:
                k = line.strip()
                if k:
                    keys.add(k)
        log(f"Found local unsampleable key file with {len(keys):,} total keys")

    return keys


# =============================================================================
# YEAR GROUPING STRATEGY
# =============================================================================

def group_pixels_by_year_pair(df):
    """Group pixels by (observation_year, emb_year) pair.
    
    Since we build temporal images per year, we group all pixels that share
    the same (obs_year, emb_year) so we can build one combined image per group.
    
    Returns dict of {(obs_year, emb_year): list of pixel dicts}
    """
    groups = {}
    for _, row in df.iterrows():
        obs_year = int(row['observation_year'])
        emb_year = int(row['emb_year'])
        key = (obs_year, emb_year)
        if key not in groups:
            groups[key] = []
        groups[key].append({
            'lat': float(row['lat']),
            'lon': float(row['lon']),
            'observation_year': obs_year,
            'emb_year': emb_year,
        })
    
    log(f"Grouped into {len(groups)} unique (obs_year, emb_year) pairs")
    # Show top 10 groups by size
    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))
    for (oy, ey), pixels in sorted_groups[:10]:
        log(f"  obs={oy}, ae={ey}: {len(pixels):,} pixels")
    
    return groups


# =============================================================================
# GEE SAMPLING
# =============================================================================

def build_combined_image(obs_year, emb_year, static_img, longterm_img):
    """Build the full sampling image for a specific (obs_year, emb_year) pair.
    
    Combines:
      - Static features (always the same)
      - Temporal features at obs_year (_at_obs suffix)
      - Temporal features at emb_year (_at_ae suffix)
      - Longterm summary features
    """
    obs_temporal = build_temporal_image_for_year(obs_year, '_at_obs')
    ae_temporal = build_temporal_image_for_year(emb_year, '_at_ae')
    
    combined = static_img.addBands(obs_temporal).addBands(ae_temporal).addBands(longterm_img)
    return combined


def sample_batch(batch, batch_idx, bq_table, combined_image):
    """Submit a GEE task to sample carbon features for a batch of pixels."""
    features = []
    for p in batch:
        geom = ee.Geometry.Point([ensure_float(p['lon']), ensure_float(p['lat'])])
        props = {
            'latitude': ensure_float(p['lat']),
            'longitude': ensure_float(p['lon']),
            'observation_year': p['observation_year'],
            'emb_year': p['emb_year'],
        }
        features.append(ee.Feature(geom, props))
    
    fc = ee.FeatureCollection(features)
    
    sampled = combined_image.sampleRegions(
        collection=fc,
        scale=SAMPLE_SCALE,
        geometries=False,
        tileScale=4
    )
    
    task_desc = f'sinr_v3_carbon_{batch_idx:05d}'
    full_table = f'{BQ_PROJECT}.{BQ_DATASET}.{bq_table}'
    
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

def run_sampling_pool(year_batches, bq_table, static_img, longterm_img, pool_size=25, resume_mode=False, mode='unknown'):
    """Run GEE sampling with a rolling pool of concurrent tasks.
    
    year_batches: list of ((obs_year, emb_year), batch_of_pixels, batch_idx)
    """
    total_batches = len(year_batches)
    active_tasks: Dict[str, dict] = {}
    retry_queue: List[Tuple] = []
    completed = 0
    failed = 0
    batch_queue = list(year_batches)
    
    # Cache of built combined images per (obs_year, emb_year)
    image_cache: Dict[Tuple[int, int], ee.Image] = {}
    
    log(f"\n{'='*60}")
    log(f"Starting temporal carbon sampling: {total_batches} batches, pool size {pool_size}")
    log(f"Target table: {BQ_PROJECT}.{BQ_DATASET}.{bq_table}")
    log(f"{'='*60}\n")
    
    def get_combined_image(obs_year, emb_year):
        """Get or build the combined image for this year pair."""
        key = (obs_year, emb_year)
        if key not in image_cache:
            image_cache[key] = build_combined_image(obs_year, emb_year, static_img, longterm_img)
            # Keep cache bounded (GEE doesn't hold these in memory, it's just the expression tree)
        return image_cache[key]
    
    # Staggered start: submit first batch alone to create BQ table
    if batch_queue and not resume_mode:
        first_entry = batch_queue.pop(0)
        (obs_y, emb_y), first_batch, first_idx = first_entry
        combined_img = get_combined_image(obs_y, emb_y)
        log(f"  Submitting first batch (#{first_idx}, obs={obs_y}, ae={emb_y}) to initialize BQ table...")
        first_tid = sample_batch(first_batch, first_idx, bq_table, combined_img)
        if first_tid:
            while True:
                time.sleep(POLL_INTERVAL_SEC)
                try:
                    st = ee.data.getTaskStatus([first_tid])[0]
                    state = st.get('state', 'UNKNOWN')
                    if state == 'COMPLETED':
                        completed += 1
                        log(f"  First batch completed. BQ table ready. Ramping up to pool_size={pool_size}")
                        break
                    elif state in ('FAILED', 'CANCELLED'):
                        err = st.get('error_message', 'unknown')
                        log(f"  First batch failed: {err}. Retrying...")
                        retry_queue.append(((obs_y, emb_y), first_batch, first_idx, 1))
                        break
                except Exception as e:
                    log(f"  Warning: status check failed: {e}")
        else:
            retry_queue.append(((obs_y, emb_y), first_batch, first_idx, 1))
    
    while batch_queue or retry_queue or active_tasks:
        # Submit new tasks to fill the pool
        while len(active_tasks) < pool_size and (batch_queue or retry_queue):
            if retry_queue:
                (obs_y, emb_y), batch, batch_idx, retry_count = retry_queue.pop(0)
                log(f"  Retrying batch {batch_idx} (attempt {retry_count + 1}/{MAX_RETRIES})")
            elif batch_queue:
                (obs_y, emb_y), batch, batch_idx = batch_queue.pop(0)
                retry_count = 0
            else:
                break
            
            combined_img = get_combined_image(obs_y, emb_y)
            task_id = sample_batch(batch, batch_idx, bq_table, combined_img)
            if task_id:
                active_tasks[task_id] = {
                    'batch_idx': batch_idx,
                    'start_time': time.time(),
                    'batch': batch,
                    'retry_count': retry_count,
                    'obs_year': obs_y,
                    'emb_year': emb_y,
                }
            else:
                if retry_count < MAX_RETRIES:
                    retry_queue.append(((obs_y, emb_y), batch, batch_idx, retry_count + 1))
                else:
                    failed += 1
                    log(f"  PERMANENT FAILURE: batch {batch_idx} after {MAX_RETRIES} retries")
        
        if not active_tasks:
            break
        
        time.sleep(POLL_INTERVAL_SEC)
        
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
                
                if info['retry_count'] < MAX_RETRIES and 'empty' not in error_msg.lower():
                    retry_queue.append((
                        (info['obs_year'], info['emb_year']),
                        info['batch'],
                        info['batch_idx'],
                        info['retry_count'] + 1
                    ))
                else:
                    if 'empty' in error_msg.lower():
                        record_unsampleable_batch(
                            info['batch'],
                            info['obs_year'],
                            info['emb_year'],
                            mode,
                            'empty_feature_collection'
                        )
                    failed += 1
            
            elif state in ('RUNNING', 'READY'):
                elapsed = time.time() - info['start_time']
                if elapsed > TASK_TIMEOUT_MIN * 60:
                    log(f"  ⏱ Batch {info['batch_idx']} timed out ({elapsed/60:.1f}min), cancelling")
                    try:
                        ee.data.cancelTask(tid)
                    except:
                        pass
                    del active_tasks[tid]
                    if info['retry_count'] < MAX_RETRIES:
                        retry_queue.append((
                            (info['obs_year'], info['emb_year']),
                            info['batch'],
                            info['batch_idx'],
                            info['retry_count'] + 1
                        ))
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
    import pandas as pd
    
    parser = argparse.ArgumentParser(description='SINR v3 temporal carbon/biomass GEE sampler')
    parser.add_argument('--new-gbif', action='store_true', help='Sample new GBIF pixels')
    parser.add_argument('--existing', action='store_true', help='Sample existing training pixels')
    parser.add_argument('--all', action='store_true', help='Both new GBIF and existing')
    parser.add_argument('--pool-size', type=int, default=25, help='Max concurrent GEE tasks')
    parser.add_argument('--resume-from-bq', action='store_true', help='Skip already-completed pixels')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of pixels (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Load data but don\'t submit')
    parser.add_argument('--gee-project', type=str, default=GEE_PROJECT, help='GEE project ID')
    args = parser.parse_args()
    
    if args.all:
        args.new_gbif = True
        args.existing = True
    
    if not args.new_gbif and not args.existing:
        parser.error("Must specify --new-gbif, --existing, or --all")
    
    # Initialize GEE
    log(f"Initializing GEE with project: {args.gee_project}")
    ee.Initialize(project=args.gee_project)
    log("GEE initialized.")
    
    # Build static and longterm images once (reused for all year groups)
    log("Building static carbon image...")
    static_img = build_static_image()
    log(f"Static image built (14 bands).")
    
    log("Building longterm NPP summary image...")
    longterm_img = build_longterm_image()
    log(f"Longterm image built (2 bands).")
    
    modes = []
    if args.new_gbif:
        modes.append('new_gbif')
    if args.existing:
        modes.append('existing')
    
    for mode in modes:
        log(f"\n{'='*60}")
        log(f"MODE: Carbon sampling for {mode}")
        log(f"{'='*60}")
        
        # Load pixels with temporal info
        df = load_pixels_with_years(mode)
        
        if args.limit:
            df = df.head(args.limit)
            log(f"Limited to {len(df)} pixels")
        
        # Resume: skip completed pixels
        if args.resume_from_bq:
            completed_keys = load_completed_keys(BQ_TABLE)
            unsampleable_keys = load_unsampleable_keys()
            excluded_keys = completed_keys | unsampleable_keys
            before = len(df)
            df['_key'] = (
                df['lat'].round(4).astype(str) + '|' + 
                df['lon'].round(4).astype(str) + '|' +
                df['observation_year'].astype(str)
            )
            df = df[~df['_key'].isin(excluded_keys)]
            df = df.drop(columns=['_key'])
            skipped = before - len(df)
            log(f"Skipping {skipped:,} pixels (completed + unsampleable)")
            del completed_keys
            del unsampleable_keys
            del excluded_keys
        
        if len(df) == 0:
            log("No pixels to sample. Skipping.")
            continue
        
        # Group by (obs_year, emb_year) for efficient image reuse
        groups = group_pixels_by_year_pair(df)
        del df
        import gc; gc.collect()
        
        # Create batches within each year group
        all_batches = []
        batch_idx = 0
        for (obs_year, emb_year), pixels in sorted(groups.items()):
            random.shuffle(pixels)
            for i in range(0, len(pixels), BATCH_SIZE):
                chunk = pixels[i:i + BATCH_SIZE]
                if len(chunk) < MIN_BATCH_SIZE and all_batches:
                    # Append tiny remainder to previous batch (same year group ideally)
                    # But since year groups differ, just make it its own batch
                    pass
                all_batches.append(((obs_year, emb_year), chunk, batch_idx))
                batch_idx += 1
        
        log(f"Created {len(all_batches)} total batches across {len(groups)} year groups")
        del groups
        gc.collect()
        
        if args.dry_run:
            log(f"DRY RUN: would submit {len(all_batches)} batches")
            continue
        
        run_sampling_pool(
            all_batches, BQ_TABLE, static_img, longterm_img,
            args.pool_size, resume_mode=args.resume_from_bq, mode=mode
        )


if __name__ == '__main__':
    main()
