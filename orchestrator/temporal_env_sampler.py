#!/usr/bin/env python3
"""
temporal_env_sampler.py — Year-matched temporal environmental variable sampler.

Corrects Phase C data quality issue: temporal datasets (TerraClimate, MODIS GPP,
Dynamic World, fire, nightlights) were sampled at fixed modern windows instead of
at the occurrence year. This sampler re-samples ONLY the temporal bands at the
correct year for each occurrence.

Also backfills V4 pixels (1.48M) with ALL 61 environmental bands they're missing.

Two modes:
  --phase-c-temporal   Re-sample 5 temporal datasets at Phase C pixel occurrence years
  --v4-backfill        Sample full 61-band env stack at V4 pixels (static + temporal year-matched)
  --all                Both of the above

Architecture:
  1. Load pixel populations with occurrence years
  2. Group into year cohorts (all pixels with same occurrence year)
  3. For each cohort: build year-specific image stack, sample, export to BQ
  4. Rolling pool of 25 concurrent GEE tasks (same as regime2_sampler.py)

Output BQ tables:
  - phase_c_temporal_env_v1: temporal bands re-sampled at correct years
  - v4_env_backfill_v1: full env stack for V4-only pixels

Usage:
  python3 temporal_env_sampler.py --all --pool-size 25
  python3 temporal_env_sampler.py --phase-c-temporal --pool-size 25
  python3 temporal_env_sampler.py --v4-backfill --pool-size 25
"""

import argparse
import ee
import json
import numpy as np
import os
import pandas as pd
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
BQ_TABLE_TEMPORAL = 'phase_c_temporal_env_v1'
BQ_TABLE_V4_BACKFILL = 'v4_env_backfill_v1'
BQ_TABLE_V4_MISSING = 'v4_env_backfill_v2'
BQ_TABLE_ARCTIC = 'arctic_env_backfill_v1'

AE_SCALE = 10              # AlphaEarth native resolution (for sampleRegions scale)
TEMPORAL_SCALE = 1000      # Scale for temporal-only sampling (coarsest: TerraClimate 4km)
STATIC_SCALE = 30          # Scale for static+temporal sampling (finest static: SRTM 30m)
BATCH_SIZE = 2000           # Pixels per GEE task (2K optimal: GEE completes in ~7min vs 30+ for 10K)
MIN_BATCH_SIZE = 50         # Minimum pixels per batch — smaller batches merged with previous
MIN_COHORT_SIZE = 200       # Minimum pixels per year cohort — smaller cohorts merged temporally
COORD_DECIMALS = 4          # 4dp = ~11m precision
TASK_TIMEOUT_MIN = 45       # Kill tasks taking longer than this
POLL_INTERVAL_SEC = 30      # How often to check task status

# Paths
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
OCC_PARQUET = ROOT_DIR / 'Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet'
V4_PARQUET = SCRIPT_DIR / 'bigquery_exports' / 'alphaearth_embeddings_v4' / 'alphaearth_embeddings_v4_COMPLETE.parquet'
V4_MISSING_PARQUET = SCRIPT_DIR / 'v4_missing_env_pixels.parquet'

# GEE asset IDs
SRTM_ASSET = 'USGS/SRTMGL1_003'
COPERNICUS_DEM_ASSET = 'COPERNICUS/DEM/GLO30'  # 30m, covers to 84°N (vs SRTM 60°N)
ARCTIC_LAT_THRESHOLD = 59.0  # Use Copernicus DEM above this latitude
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'

# =============================================================================
# TEMPORAL IMAGE BUILDERS (year-specific)
# =============================================================================

def get_terraclimate_for_year(year: int) -> ee.Image:
    """TerraClimate at occurrence year (+/-2yr window for smoothing).
    
    Available 1958-present. For years before 1958, uses 1958-1962.
    """
    # Clamp to available range
    center_year = max(1958, min(year, 2024))
    start_year = max(1958, center_year - 2)
    end_year = min(2025, center_year + 3)  # +3 because filterDate end is exclusive
    
    tc = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
          .filterDate(f'{start_year}-01-01', f'{end_year}-01-01')
          .select(['vpd', 'aet', 'soil', 'pdsi', 'def', 'srad']))
    
    tc_mean = tc.mean()
    return (
        tc_mean.select('vpd').rename('tc_vpd_mean')
        .addBands(tc_mean.select('aet').rename('tc_aet_mean'))
        .addBands(tc_mean.select('soil').rename('tc_soil_moisture_mean'))
        .addBands(tc_mean.select('pdsi').rename('tc_pdsi_mean'))
        .addBands(tc_mean.select('def').rename('tc_water_deficit_mean'))
        .addBands(tc_mean.select('srad').rename('tc_solar_rad_mean'))
    )


def get_modis_gpp_for_year(year: int) -> ee.Image:
    """MODIS GPP at occurrence year. Available 2000-present.
    
    Pre-2000: uses 2000 (earliest available).
    """
    target_year = max(2000, min(year, 2024))
    gpp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filterDate(f'{target_year}-01-01', f'{target_year + 1}-01-01')
           .select('Gpp'))
    # If single year has no data, expand to +/-1yr
    return ee.Algorithms.If(
        gpp.size().gt(0),
        gpp.mean().rename('modis_gpp_mean'),
        ee.ImageCollection('MODIS/061/MOD17A3HGF')
          .filterDate(f'{max(2000, target_year-1)}-01-01', f'{min(2025, target_year+2)}-01-01')
          .select('Gpp').mean().rename('modis_gpp_mean')
    )


def get_modis_gpp_for_year_safe(year: int) -> ee.Image:
    """MODIS GPP — simplified version that always returns an image.
    
    Masks sentinel/fill values (65530-65535) before computing mean.
    Raw integer units (multiply by 0.0001 for kg C/m²/yr).
    """
    target_year = max(2000, min(year, 2023))
    start = max(2000, target_year - 1)
    end = min(2025, target_year + 2)
    gpp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filterDate(f'{start}-01-01', f'{end}-01-01')
           .select('Gpp')
           .map(lambda img: img.updateMask(img.lt(65530))))
    return gpp.mean().rename('modis_gpp_mean')


def get_dynamic_world_for_year(year: int) -> ee.Image:
    """Dynamic World land cover at occurrence year. Available 2015-present.
    
    Pre-2015: uses ESA WorldCover 2021 as static proxy (returned with same band name).
    """
    if year >= 2015:
        target_year = min(year, 2024)
        dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
              .filterDate(f'{target_year}-01-01', f'{target_year + 1}-01-01')
              .select('label'))
        return dw.mode().rename('dynamic_world')
    else:
        # Pre-2015: use ESA WorldCover as proxy, remapped to DW classes (0-8)
        esa = (ee.ImageCollection('ESA/WorldCover/v200')
               .mosaic().select('Map'))
        return esa.remap(
            [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
            [ 1,  5,  2,  4,  6,  7,  8,  0,  3,  1,   7]
        ).rename('dynamic_world')


def get_modis_fire_for_year(year: int) -> ee.Image:
    """MODIS Burned Area — cumulative count from 2001 to occurrence year.
    
    Pre-2001: returns 0 (no MODIS data).
    """
    if year < 2001:
        return ee.Image.constant(0).rename('fire_frequency_count').toInt()
    
    end_year = min(year + 1, 2024)
    burned = (ee.ImageCollection('MODIS/061/MCD64A1')
              .filterDate('2001-01-01', f'{end_year}-01-01')
              .select('BurnDate'))
    burn_count = burned.map(lambda img: img.gt(0).unmask(0)).sum()
    return burn_count.rename('fire_frequency_count')


def get_viirs_for_year(year: int) -> ee.Image:
    """VIIRS Nighttime Lights at occurrence year. Available 2012-present.
    
    Pre-2012: returns 0 (no VIIRS data; DMSP-OLS not on GEE in usable form).
    """
    if year < 2012:
        return ee.Image.constant(0).rename('nighttime_lights').toFloat()
    
    target_year = min(year, 2024)
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
             .filterDate(f'{target_year}-01-01', f'{target_year + 1}-01-01')
             .select('avg_rad'))
    return viirs.mean().unmask(0).rename('nighttime_lights')


def get_hansen_loss_for_year(year: int) -> ee.Image:
    """Hansen lossyear filtered to only show loss BEFORE or AT occurrence year.
    
    lossyear encodes year as 1-23 (meaning 2001-2023).
    If occurrence was in 2005, only loss from 2001-2005 (lossyear 1-5) is relevant.
    
    IMPORTANT: unmask(0) on all outputs to prevent masked pixels from making
    the entire combined image return empty in sampleRegions.
    """
    hansen = ee.Image(HANSEN_ASSET)
    max_lossyear = max(0, min(year - 2000, 23))
    
    if max_lossyear <= 0:
        # Pre-2001: no Hansen loss data — return constant 0
        return (ee.Image.constant(0).rename('lossyear_at_obs').toFloat()
                .addBands(ee.Image.constant(0).rename('loss_at_obs').toFloat()))
    
    lossyear = hansen.select('lossyear').unmask(0)
    # loss_at_obs: 1 if loss occurred at or before observation year, 0 otherwise
    loss_at_obs = lossyear.gt(0).And(lossyear.lte(max_lossyear)).unmask(0)
    # lossyear_at_obs: the actual loss year if before obs, 0 otherwise
    lossyear_at_obs = lossyear.where(lossyear.gt(max_lossyear), 0).unmask(0)
    
    return (lossyear_at_obs.rename('lossyear_at_obs').toFloat()
            .addBands(loss_at_obs.rename('loss_at_obs').toFloat()))


# =============================================================================
# STATIC IMAGE BUILDERS (same for all years — used for V4 backfill)
# =============================================================================

def build_static_env_image(arctic: bool = False) -> ee.Image:
    """Build the static environmental image stack (year-independent).
    
    These are the 55 bands that DON'T change by year. Used for V4 backfill
    where pixels are missing all env data.
    
    Args:
        arctic: If True, use Copernicus DEM GLO-30 instead of SRTM for terrain
                (elevation, slope, aspect, hillshade). SRTM has no coverage
                above 60°N; Copernicus covers to 84°N.
                Also sets topo_diversity=0 (SRTM-derived, no arctic coverage)
                and GEDI=0 (ISS orbit limited to 51.6°N).
    """
    # --- 10m native ---
    jrc_forest = ee.Image('JRC/GFC2020_subtypes/V1').select('Map').unmask(0).rename('jrc_forest_type')
    worldcover = ee.ImageCollection('ESA/WorldCover/v200').mosaic().select('Map').unmask(0).rename('esa_worldcover_2021')
    sbtn = ee.Image('WRI/SBTN/naturalLands/v1_1/2020').select('natural').unmask(0).rename('sbtn_natural_land')
    
    # --- 30m native ---
    if arctic:
        # Copernicus DEM GLO-30: covers to 84°N, same 30m resolution as SRTM
        cop_dem = ee.ImageCollection(COPERNICUS_DEM_ASSET).select('DEM').mosaic().rename('elevation')
        terrain = ee.Terrain.products(cop_dem)  # elevation, slope, aspect, hillshade
    else:
        srtm = ee.Image(SRTM_ASSET).select('elevation')
        terrain = ee.Terrain.products(srtm)  # elevation, slope, aspect, hillshade
    
    hansen = ee.Image(HANSEN_ASSET)
    hansen_stack = (hansen.select('treecover2000')
                    .addBands(hansen.select('lossyear').unmask(0))
                    .addBands(hansen.select('loss'))
                    .addBands(hansen.select('gain')))
    
    # JRC TMF: tropics-only dataset. Above 59°N it returns 0 (via unmask).
    jrc_tmf = (ee.ImageCollection('projects/JRC/TMF/v1_2024/TransitionMap_Subtypes')
               .mosaic().select('TransitionMap_Subtypes').unmask(0).rename('jrc_tmf_status'))
    jrc_degrad = (ee.ImageCollection('projects/JRC/TMF/v1_2024/DegradationYear')
                  .mosaic().select('constant').unmask(0).rename('jrc_tmf_degrad_year'))
    
    gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
    hydro = (gsw.select('occurrence').unmask(0).rename('water_occurrence')
             .addBands(gsw.select('recurrence').unmask(0).rename('water_recurrence'))
             .addBands(gsw.select('seasonality').unmask(0).rename('water_seasonality')))
    
    # --- 90m native ---
    merit = ee.Image('MERIT/Hydro/v1_0_1')
    merit_stack = (merit.select('hnd').unmask(0).rename('merit_hand_m')
                   .addBands(merit.select('upa').unmask(0).rename('merit_upstream_area_km2')))
    
    # --- 250m native ---
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')
    soil_clay = ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_clay_pct')
    soil_sand = ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_sand_pct')
    soil_oc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('soil_organic_carbon')
    soil_texture = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture_class')
    soil_bulk = ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('soil_bulk_density')
    soil_water = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01').select('b0').rename('soil_water_content')
    
    if arctic:
        # SRTM topo diversity not available above 60°N — use constant 0
        topo_div = ee.Image.constant(0).rename('topo_diversity').toFloat()
    else:
        topo_div = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').select('constant').rename('topo_diversity')
    
    # --- 300m native ---
    biomass = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic().select('agb').unmask(0).rename('biomass_agb_mgha')
    
    # --- 1km native ---
    worldclim = ee.Image('WORLDCLIM/V1/BIO')  # 19 bio bands
    
    if arctic:
        # GEDI: ISS orbit limited to 51.6° — no data above ~52°N
        gedi_canopy = ee.Image.constant(0).rename('gedi_canopy_height_m').toFloat()
        gedi_fhd = ee.Image.constant(0).rename('gedi_foliage_height_div').toFloat()
    else:
        gedi_rh98 = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
        gedi_fhd_img = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316')
        gedi_canopy = gedi_rh98.select('p95').unmask(0).rename('gedi_canopy_height_m')
        gedi_fhd = gedi_fhd_img.select('shan').unmask(0).rename('gedi_foliage_height_div')
    
    human_mod = ee.ImageCollection('CSP/HM/GlobalHumanModification').mosaic().select('gHM').unmask(0).rename('human_modification')
    
    ecoregions = ee.FeatureCollection('RESOLVE/ECOREGIONS/2017')
    eco_id = ecoregions.reduceToImage(properties=['ECO_ID'], reducer=ee.Reducer.first()).rename('eco_id')
    biome_num = ecoregions.reduceToImage(properties=['BIOME_NUM'], reducer=ee.Reducer.first()).rename('biome_num')
    
    # Chain all static bands
    combined = (
        jrc_forest
        .addBands(worldcover)
        .addBands(sbtn)
        .addBands(terrain)
        .addBands(hansen_stack)
        .addBands(jrc_tmf)
        .addBands(jrc_degrad)
        .addBands(hydro)
        .addBands(merit_stack)
        .addBands(soil_ph).addBands(soil_clay).addBands(soil_sand)
        .addBands(soil_oc).addBands(soil_texture).addBands(soil_bulk).addBands(soil_water)
        .addBands(topo_div)
        .addBands(biomass)
        .addBands(worldclim)
        .addBands(gedi_canopy).addBands(gedi_fhd)
        .addBands(human_mod)
        .addBands(eco_id).addBands(biome_num)
    )
    
    return combined.toFloat()


def build_temporal_image_for_year(year: int, include_anchor: bool = True, arctic: bool = False) -> ee.Image:
    """Build the temporal-only image stack for a specific occurrence year.
    
    These are the bands that MUST be year-matched:
    - TerraClimate (6 bands): VPD, AET, soil moisture, PDSI, water deficit, solar rad
    - MODIS GPP (1 band)
    - Dynamic World (1 band)
    - MODIS fire (1 band): cumulative to year
    - VIIRS nightlights (1 band)
    - Hansen loss filtered to year (2 bands): lossyear_at_obs, loss_at_obs
    
    Total: 12 temporal bands (+ 1 anchor if include_anchor=True)
    
    IMPORTANT: include_anchor adds a 30m DEM elevation as an anchor band.
    Without it, sampleRegions at any scale returns empty for temporal-only
    image stacks — GEE's sampling grid at coarse (1km) resolution causes
    points to fall between grid cells. The 30m anchor forces proper spatial
    intersection. We sample at scale=30 with the anchor (DEM native res).
    The anchor band is dropped downstream during BQ processing.
    
    Args:
        arctic: If True, use Copernicus DEM GLO-30 as anchor instead of SRTM
                (SRTM has no coverage above 60°N).
    """
    tc = get_terraclimate_for_year(year)
    gpp = get_modis_gpp_for_year_safe(year)
    dw = get_dynamic_world_for_year(year)
    fire = get_modis_fire_for_year(year)
    viirs = get_viirs_for_year(year)
    hansen_yr = get_hansen_loss_for_year(year)
    
    combined = (
        tc
        .addBands(gpp)
        .addBands(dw)
        .addBands(fire)
        .addBands(viirs)
        .addBands(hansen_yr)
    )
    
    # unmask(0) on the entire combined image prevents masked pixels from
    # causing sampleRegions to return empty. Some locations (oceans, poles,
    # pre-satellite-era) have no data for certain bands — 0 is acceptable
    # as a null indicator for these edge cases.
    combined = combined.unmask(0)
    
    if include_anchor:
        if arctic:
            # Copernicus DEM GLO-30: covers to 84°N (vs SRTM 60°N)
            anchor = (ee.ImageCollection(COPERNICUS_DEM_ASSET)
                      .select('DEM').mosaic().unmask(0).rename('anchor_elevation'))
        else:
            # SRTM as anchor band to force 30m sampling grid
            anchor = ee.Image(SRTM_ASSET).select('elevation').unmask(0).rename('anchor_elevation')
        combined = combined.addBands(anchor)
    
    return combined.toFloat()


def build_full_env_image_for_year(year: int, arctic: bool = False) -> ee.Image:
    """Build the complete env image (static + temporal) for V4 backfill.
    
    V4 pixels need ALL 61+ env bands since they have none beyond elevation+treecover.
    
    Args:
        arctic: If True, use Copernicus DEM instead of SRTM for terrain/anchor.
    """
    static = build_static_env_image(arctic=arctic)
    temporal = build_temporal_image_for_year(year, arctic=arctic)
    return static.addBands(temporal)


# =============================================================================
# PIXEL POPULATION LOADERS
# =============================================================================

def load_phase_c_pixels_with_years() -> pd.DataFrame:
    """Load Phase C pixel population with their occurrence years.
    
    For pixels with multiple occurrence years, we keep the MOST RECENT year
    (closest to the 2017 AlphaEarth sampling year — least temporal drift).
    
    For unknown-year pixels, we assign year 2000 (midpoint of the distribution,
    and TerraClimate/MODIS both have good coverage there).
    """
    import pyarrow.parquet as pq
    
    print("  Loading occurrence parquet...")
    occ = pq.read_table(
        OCC_PARQUET,
        columns=['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year']
    ).to_pandas()
    occ = occ.dropna(subset=['taxon_id'])
    
    # Filter to pre-2017 + unknown year
    mask = (occ['year'].isna()) | ((occ['year'] > 0) & (occ['year'] < 2017))
    occ = occ[mask].copy()
    print(f"  Pre-2017 + unknown year: {len(occ):,} rows")
    
    # Round coordinates
    occ['lat4'] = (occ['decimalLatitude'] * 10000).round().astype(np.int64)
    occ['lon4'] = (occ['decimalLongitude'] * 10000).round().astype(np.int64)
    
    # For each unique pixel, get the most recent occurrence year
    # (closest to 2017 AlphaEarth = least temporal assumption)
    occ['year_clean'] = occ['year'].fillna(0).astype(int)
    pixel_years = occ.groupby(['lat4', 'lon4'])['year_clean'].max().reset_index()
    pixel_years.columns = ['lat4', 'lon4', 'occurrence_year']
    
    # Unknown year (0) → default to 2000
    pixel_years.loc[pixel_years['occurrence_year'] == 0, 'occurrence_year'] = 2000
    
    # Convert back to float coords
    pixel_years['latitude'] = pixel_years['lat4'] / 10000.0
    pixel_years['longitude'] = pixel_years['lon4'] / 10000.0
    
    print(f"  Unique pixels with years: {len(pixel_years):,}")
    print(f"  Year range: {pixel_years['occurrence_year'].min()} to {pixel_years['occurrence_year'].max()}")
    
    return pixel_years


def load_v4_pixels_with_years() -> pd.DataFrame:
    """Load V4 pixel locations with their embedding years.
    
    V4 data has emb_year (= orig_year for v4, always pixel-accurate).
    We need to sample env bands at these locations, year-matched to emb_year.
    """
    import pyarrow.parquet as pq
    
    print("  Loading v4 parquet...")
    v4 = pq.read_table(
        V4_PARQUET,
        columns=['latitude', 'longitude', 'emb_year']
    ).to_pandas()
    
    # Deduplicate to unique pixels (keep year for temporal matching)
    v4['lat4'] = (v4['latitude'] * 10000).round().astype(np.int64)
    v4['lon4'] = (v4['longitude'] * 10000).round().astype(np.int64)
    
    # For pixels with multiple years, keep the most common year
    pixel_years = v4.groupby(['lat4', 'lon4'])['emb_year'].agg(lambda x: x.mode()[0]).reset_index()
    pixel_years.columns = ['lat4', 'lon4', 'occurrence_year']
    
    pixel_years['latitude'] = pixel_years['lat4'] / 10000.0
    pixel_years['longitude'] = pixel_years['lon4'] / 10000.0
    
    print(f"  V4 unique pixels: {len(pixel_years):,}")
    print(f"  Year range: {pixel_years['occurrence_year'].min()} to {pixel_years['occurrence_year'].max()}")
    
    return pixel_years


def load_v4_missing_pixels() -> pd.DataFrame:
    """Load V4 pixels that are missing env data from pre-exported parquet.
    
    This parquet was generated by querying PG for V4 embeddings without
    matching pixel_environmental_bands rows. Already deduplicated to
    unique (lat4dp, lon4dp, year) pixels.
    """
    import pyarrow.parquet as pq
    
    print(f"  Loading missing V4 pixels from {V4_MISSING_PARQUET}...")
    df = pq.read_table(V4_MISSING_PARQUET).to_pandas()
    
    # Ensure lat4/lon4 columns exist
    if 'lat4' not in df.columns:
        df['lat4'] = (df['latitude'] * 10000).round().astype(np.int64)
        df['lon4'] = (df['longitude'] * 10000).round().astype(np.int64)
    
    print(f"  Missing V4 pixels: {len(df):,}")
    print(f"  Year range: {df['occurrence_year'].min()} to {df['occurrence_year'].max()}")
    
    return df


def load_arctic_pixels() -> pd.DataFrame:
    """Load >59°N pixels that need env data from PG.
    
    These are embeddings above 59°N that have NO matching row in
    pixel_environmental_bands. Root cause: SRTM (used as anchor band)
    has no coverage above 60°N, causing sampleRegions to return empty.
    
    Fix: Use Copernicus DEM GLO-30 as anchor (covers to 84°N).
    """
    import psycopg2
    
    print(f"  Loading Arctic (>{ARCTIC_LAT_THRESHOLD}°N) pixels from PG...")
    
    conn = psycopg2.connect(
        dbname="treekipedia",
        user=os.environ.get("DB_USER", os.environ.get("USER", "djimoserodio")),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
    )
    
    query = f"""
        SELECT DISTINCT
            round(e.latitude::numeric, 4)::float AS latitude,
            round(e.longitude::numeric, 4)::float AS longitude,
            e.emb_year AS occurrence_year
        FROM species_occurrence_embeddings e
        LEFT JOIN pixel_environmental_bands p
            ON round(e.latitude::numeric, 4) = round(p.latitude::numeric, 4)
            AND round(e.longitude::numeric, 4) = round(p.longitude::numeric, 4)
            AND e.emb_year = p.occurrence_year
        WHERE e.latitude > {ARCTIC_LAT_THRESHOLD}
            AND p.id IS NULL
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Add lat4/lon4 for dedup tracking
    df['lat4'] = (df['latitude'] * 10000).round().astype(np.int64)
    df['lon4'] = (df['longitude'] * 10000).round().astype(np.int64)
    
    print(f"  Arctic pixels needing env data: {len(df):,}")
    if len(df) > 0:
        print(f"  Latitude range: {df['latitude'].min():.4f} to {df['latitude'].max():.4f}")
        print(f"  Year range: {df['occurrence_year'].min()} to {df['occurrence_year'].max()}")
    
    return df


# =============================================================================
# YEAR COHORT BUILDER
# =============================================================================

def build_year_cohorts(
    pixels: pd.DataFrame,
    bin_width: int = 5,
    min_cohort_size: int = 200,
) -> Dict[int, pd.DataFrame]:
    """Group pixels into year cohorts for efficient GEE sampling.
    
    Instead of one GEE image stack per year (297 unique years!), we bin into
    cohorts of `bin_width` years. A 5-year bin means the TerraClimate window
    for a 2003-2007 cohort uses the 2003-2007 mean — still year-appropriate
    but much more efficient than per-year image builds.
    
    For TerraClimate (which already uses a +/-2yr window), this is equivalent
    to extending the window slightly. For MODIS/DW/fire, we use the cohort
    midpoint year.
    
    Small cohorts (< min_cohort_size) are merged into their nearest temporal
    neighbor to avoid tiny GEE batches that return empty results. This was
    the cause of 11/30 batch failures in the 2000-pixel test run — all were
    sparse pre-1960 cohorts with 1-17 pixels that sampleRegions couldn't
    resolve at coarse temporal-only scale.
    """
    pixels = pixels.copy()
    
    # Bin years into cohorts (e.g., 5-year bins: 1980-1984, 1985-1989, ...)
    pixels['year_cohort'] = (pixels['occurrence_year'] // bin_width) * bin_width
    
    # Initial grouping
    raw_cohorts = {}
    for cohort_year, group in pixels.groupby('year_cohort'):
        raw_cohorts[int(cohort_year)] = group.copy()
    
    print(f"\n  Raw year cohorts ({bin_width}-year bins): {len(raw_cohorts)}")
    
    # Merge small cohorts into nearest temporal neighbor
    sorted_years = sorted(raw_cohorts.keys())
    cohorts = {}
    merge_log = []
    
    for yr in sorted_years:
        if len(raw_cohorts[yr]) >= min_cohort_size:
            cohorts[yr] = raw_cohorts[yr]
        else:
            # Find nearest cohort that is large enough (or already exists in merged)
            best_target = None
            best_dist = float('inf')
            # Prefer merging forward (into nearest future cohort) to minimize temporal drift
            for candidate_yr in sorted_years:
                if candidate_yr == yr:
                    continue
                if len(raw_cohorts[candidate_yr]) >= min_cohort_size or candidate_yr in cohorts:
                    dist = abs(candidate_yr - yr)
                    if dist < best_dist:
                        best_dist = dist
                        best_target = candidate_yr
            
            if best_target is not None and best_target in cohorts:
                # Merge into existing cohort
                cohorts[best_target] = pd.concat([cohorts[best_target], raw_cohorts[yr]], ignore_index=True)
                merge_log.append(f"    MERGED {yr} ({len(raw_cohorts[yr]):,} px) → {best_target} (dist={best_dist}yr)")
            elif best_target is not None:
                # Target not yet in cohorts — it will be added later, so buffer this one
                # Add as its own entry for now; will merge at end
                cohorts[yr] = raw_cohorts[yr]
                merge_log.append(f"    KEPT {yr} ({len(raw_cohorts[yr]):,} px, no merge target yet)")
            else:
                # No merge target found — keep as-is (shouldn't happen)
                cohorts[yr] = raw_cohorts[yr]
    
    # Second pass: first add all large cohorts, then merge small ones into nearest large
    final_cohorts = {}
    sorted_merged = sorted(cohorts.keys())
    
    # Step 1: add all large cohorts
    for yr in sorted_merged:
        if len(cohorts[yr]) >= min_cohort_size:
            final_cohorts[yr] = cohorts[yr]
    
    # Step 2: merge small cohorts into nearest large cohort
    for yr in sorted_merged:
        if len(cohorts[yr]) < min_cohort_size:
            best_target = None
            best_dist = float('inf')
            for candidate_yr in final_cohorts:
                dist = abs(candidate_yr - yr)
                if dist < best_dist:
                    best_dist = dist
                    best_target = candidate_yr
            if best_target is not None:
                final_cohorts[best_target] = pd.concat([final_cohorts[best_target], cohorts[yr]], ignore_index=True)
                merge_log.append(f"    MERGED(pass2) {yr} ({len(cohorts[yr]):,} px) → {best_target} (dist={best_dist}yr)")
            else:
                # No large cohorts at all — keep as-is (edge case)
                final_cohorts[yr] = cohorts[yr]
                merge_log.append(f"    KEPT(pass2) {yr} ({len(cohorts[yr]):,} px, no large cohort exists)")
    
    if merge_log:
        print(f"  Small cohort merges (min_cohort_size={min_cohort_size}):")
        for msg in merge_log:
            print(msg)
    
    print(f"  Final cohorts: {len(final_cohorts)}")
    for yr in sorted(final_cohorts.keys()):
        print(f"    {yr}-{yr+bin_width-1}: {len(final_cohorts[yr]):,} pixels")
    
    return final_cohorts


# =============================================================================
# SAMPLING ENGINE
# =============================================================================

def split_into_batches(df: pd.DataFrame, batch_size: int, min_batch_size: int) -> List[pd.DataFrame]:
    """Split a DataFrame into batches, merging tiny trailing batches.
    
    If the last batch has fewer than min_batch_size rows, merge it into the
    previous batch (making that batch slightly larger than batch_size). This
    prevents GEE sampleRegions from failing on tiny feature collections.
    """
    batches = []
    for i in range(0, len(df), batch_size):
        batches.append(df.iloc[i:i + batch_size])
    
    # Merge trailing runt batch into previous
    if len(batches) > 1 and len(batches[-1]) < min_batch_size:
        last = batches.pop()
        batches[-1] = pd.concat([batches[-1], last], ignore_index=True)
    
    return batches


def sample_cohort_batch(
    batch_df: pd.DataFrame,
    batch_idx: int,
    cohort_year: int,
    image: ee.Image,
    bq_table: str,
    mode: str,
) -> Optional[str]:
    """Sample one batch of pixels against a year-specific image stack.
    
    Scale selection:
    - Both modes use STATIC_SCALE (30m) because the temporal image now
      includes an SRTM anchor band (_anchor_elevation) to force proper
      point-to-pixel intersection. Without this anchor, sampleRegions at
      any coarse scale returns empty for temporal-only image stacks.
    - The anchor_elevation band is a harmless extra column in BQ that
      gets dropped during downstream processing.
    
    Args:
        batch_df: DataFrame with latitude, longitude, occurrence_year columns
        batch_idx: Global batch index for naming
        cohort_year: The year cohort (for naming)
        image: Year-specific ee.Image with all bands to sample
        bq_table: Target BigQuery table
        mode: 'tc' (temporal) or 'v4bf' (v4 backfill)
    
    Returns:
        GEE task ID
    """
    lats = batch_df['latitude'].values
    lons = batch_df['longitude'].values
    years = batch_df['occurrence_year'].values
    
    # Force lat/lon to have fractional part to prevent GEE from inferring
    # INTEGER type (which causes BQ schema conflict with existing FLOAT64 columns).
    # Adding 1e-10 to any exact integer doesn't affect precision at 4dp.
    def ensure_float(v):
        f = float(v)
        if f == int(f):
            f += 1e-10
        return f
    
    features = [
        ee.Feature(
            ee.Geometry.Point([float(lon), float(lat)]),
            {'latitude': ensure_float(lat), 'longitude': ensure_float(lon), 'occurrence_year': int(yr)}
        )
        for lat, lon, yr in zip(lats, lons, years)
    ]
    
    fc = ee.FeatureCollection(features)
    
    # Always use 30m (SRTM native) — temporal images include anchor band
    sample_scale = STATIC_SCALE
    
    sampled = image.sampleRegions(
        collection=fc,
        scale=sample_scale,
        geometries=False,
        tileScale=4
    )
    
    # Strip anchor_elevation band (used only for sampling grid alignment,
    # not needed in output). If we don't strip it, BQ schema conflicts
    # with tables that were created without it.
    def drop_anchor(feature):
        props = feature.propertyNames()
        keep = props.filter(ee.Filter.neq('item', 'anchor_elevation'))
        return feature.select(keep)
    
    sampled = sampled.map(drop_anchor)
    
    task_desc = f'{mode}_y{cohort_year}_{datetime.now().strftime("%Y%m%d")}_{batch_idx:05d}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=task_desc,
        table=f'{PROJECT}.{BQ_DATASET}.{bq_table}',
        append=True,
        overwrite=False
    )
    task.start()
    
    return task.id


# =============================================================================
# ROLLING POOL (same pattern as regime2_sampler.py)
# =============================================================================

def run_rolling_pool(
    all_batches: List[Tuple[pd.DataFrame, int, int, ee.Image, str, str]],
    pool_size: int = 25,
    max_retries: int = 3,
):
    """Run batches with a rolling pool of concurrent GEE tasks.
    
    Each tuple in all_batches: (batch_df, batch_idx, cohort_year, image, bq_table, mode)
    """
    total = len(all_batches)
    if total == 0:
        print("  No batches to process.")
        return
    
    print(f"\n{'=' * 60}")
    print(f"SAMPLING {total} BATCHES")
    print(f"{'=' * 60}")
    print(f"  Pool size: {pool_size} concurrent tasks")
    print(f"  Max retries per batch: {max_retries}")
    
    # Task tracking
    active_tasks = {}  # task_id -> (batch_info, start_time, retry_count)
    queue = list(range(total))  # Indices into all_batches
    completed = 0
    failed_permanent = 0
    retry_queue = []
    start_time = time.time()
    
    def submit_one(batch_info_idx, retry_count=0):
        batch_df, batch_idx, cohort_year, image, bq_table, mode = all_batches[batch_info_idx]
        try:
            task_id = sample_cohort_batch(batch_df, batch_idx, cohort_year, image, bq_table, mode)
            active_tasks[task_id] = (batch_info_idx, time.time(), retry_count)
            return True
        except Exception as e:
            print(f"  ERROR submitting batch {batch_idx}: {e}")
            if retry_count < max_retries:
                retry_queue.append((batch_info_idx, retry_count + 1))
            else:
                failed_permanent += 1
            return False
    
    # Submit initial pool
    initial_count = min(pool_size, len(queue))
    for _ in range(initial_count):
        if queue:
            submit_one(queue.pop(0))
    print(f"\n  Initial pool: {initial_count} tasks submitted")
    
    # Poll loop
    while active_tasks or queue or retry_queue:
        time.sleep(POLL_INTERVAL_SEC)
        
        if not active_tasks:
            # Submit from queues
            while (queue or retry_queue) and len(active_tasks) < pool_size:
                if retry_queue:
                    idx, rc = retry_queue.pop(0)
                    submit_one(idx, rc)
                elif queue:
                    submit_one(queue.pop(0))
            continue
        
        # Check task status
        try:
            task_ids = list(active_tasks.keys())
            statuses = ee.data.getTaskStatus(task_ids)
        except Exception as e:
            print(f"  WARNING: getTaskStatus failed: {e}")
            continue
        
        done_ids = []
        for status in statuses:
            tid = status['id']
            state = status.get('state', 'UNKNOWN')
            
            if state == 'COMPLETED':
                done_ids.append(tid)
                completed += 1
            elif state == 'FAILED':
                done_ids.append(tid)
                batch_info_idx, _, retry_count = active_tasks[tid]
                err = status.get('error_message', 'unknown')
                if retry_count < max_retries and 'empty' not in err.lower():
                    retry_queue.append((batch_info_idx, retry_count + 1))
                else:
                    failed_permanent += 1
            elif state in ('CANCEL_REQUESTED', 'CANCELLED'):
                done_ids.append(tid)
                failed_permanent += 1
            else:
                # Check timeout
                _, task_start, _ = active_tasks[tid]
                elapsed_min = (time.time() - task_start) / 60
                if elapsed_min > TASK_TIMEOUT_MIN:
                    try:
                        ee.data.cancelTask(tid)
                    except:
                        pass
                    done_ids.append(tid)
                    batch_info_idx, _, retry_count = active_tasks[tid]
                    if retry_count < max_retries:
                        retry_queue.append((batch_info_idx, retry_count + 1))
                    else:
                        failed_permanent += 1
        
        # Remove done tasks
        for tid in done_ids:
            del active_tasks[tid]
        
        # Submit new tasks
        while len(active_tasks) < pool_size and (queue or retry_queue):
            if retry_queue:
                idx, rc = retry_queue.pop(0)
                submit_one(idx, rc)
            elif queue:
                submit_one(queue.pop(0))
        
        # Progress report
        elapsed = (time.time() - start_time) / 60
        remaining = total - completed - failed_permanent
        rate = completed / elapsed if elapsed > 0 else 0
        eta = remaining / rate / 60 if rate > 0 else 0
        n_retry = len(retry_queue)
        n_queued = len(queue)
        n_active = len(active_tasks)
        pixels_done = completed * BATCH_SIZE
        
        print(f"  [{completed}/{total}] {completed} ok, {failed_permanent} fail, "
              f"{n_active} active, {n_retry} retry, {n_queued} queued | "
              f"~{pixels_done:,} pixels | {elapsed:.0f}min elapsed, ~{eta:.1f}hr left")
    
    # Final summary
    elapsed = (time.time() - start_time) / 60
    print(f"\n{'=' * 60}")
    print(f"SAMPLING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total completed: {completed}")
    print(f"  Total failed (permanent): {failed_permanent}")
    print(f"  Total time: {elapsed:.1f} min ({elapsed/60:.1f} hours)")
    print(f"  Success rate: {completed/(completed+failed_permanent)*100:.1f}%" if (completed+failed_permanent) > 0 else "")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Year-matched temporal env sampler')
    parser.add_argument('--phase-c-temporal', action='store_true',
                        help='Re-sample temporal bands for Phase C pixels at occurrence year')
    parser.add_argument('--v4-backfill', action='store_true',
                        help='Sample full env stack for V4-only pixels (original parquet)')
    parser.add_argument('--v4-missing', action='store_true',
                        help='Sample full env stack for V4 pixels missing from PG env table')
    parser.add_argument('--arctic-backfill', action='store_true',
                        help='Sample full env stack for >59°N pixels using Copernicus DEM (no SRTM coverage)')
    parser.add_argument('--all', action='store_true',
                        help='Both --phase-c-temporal and --v4-backfill')
    parser.add_argument('--pool-size', type=int, default=25,
                        help='Max concurrent GEE tasks (default: 25)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Max retries per failed batch (default: 3)')
    parser.add_argument('--year-bin-width', type=int, default=5,
                        help='Year cohort bin width (default: 5)')
    parser.add_argument('--min-cohort-size', type=int, default=MIN_COHORT_SIZE,
                        help=f'Min pixels per year cohort before merging (default: {MIN_COHORT_SIZE})')
    parser.add_argument('--resume-from-bq', action='store_true',
                        help='Skip pixels already in target BQ table (dedup on lat4/lon4)')
    parser.add_argument('--test', type=int, default=0,
                        help='Test with N random pixels only (0 = full run)')
    
    args = parser.parse_args()
    
    if args.all:
        args.phase_c_temporal = True
        args.v4_backfill = True
    
    if not args.phase_c_temporal and not args.v4_backfill and not args.v4_missing and not args.arctic_backfill:
        parser.error("Specify --phase-c-temporal, --v4-backfill, --v4-missing, --arctic-backfill, or --all")
    
    print("=" * 70)
    print("TEMPORAL ENVIRONMENTAL SAMPLER")
    print("Year-matched re-sampling for Phase C + V4 backfill")
    print("=" * 70)
    
    # Initialize GEE
    print("\nInitializing Google Earth Engine...")
    ee.Initialize(project=PROJECT)
    print(f"  GEE initialized (project: {PROJECT})")
    
    all_batches = []
    global_batch_idx = 0
    
    # -------------------------------------------------------------------------
    # RESUME FROM BQ: load already-completed pixels to skip them
    # -------------------------------------------------------------------------
    done_pixels_tc = set()   # (lat4, lon4) tuples already in temporal BQ table
    done_pixels_v4 = set()   # (lat4, lon4) tuples already in v4 backfill BQ table
    
    if args.resume_from_bq:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=PROJECT)
        
        if args.phase_c_temporal:
            print(f"\n  Loading completed pixels from {BQ_TABLE_TEMPORAL}...")
            try:
                query = f"""
                    SELECT DISTINCT
                        CAST(ROUND(latitude * 10000) AS INT64) AS lat4,
                        CAST(ROUND(longitude * 10000) AS INT64) AS lon4
                    FROM `{PROJECT}.{BQ_DATASET}.{BQ_TABLE_TEMPORAL}`
                """
                df_done = bq_client.query(query).to_dataframe()
                done_pixels_tc = set(zip(df_done['lat4'], df_done['lon4']))
                print(f"    Found {len(done_pixels_tc):,} completed pixels in {BQ_TABLE_TEMPORAL}")
            except Exception as e:
                print(f"    WARNING: Could not read {BQ_TABLE_TEMPORAL}: {e}")
                print(f"    Proceeding without resume (will process all pixels)")
        
        if args.v4_backfill:
            print(f"\n  Loading completed pixels from {BQ_TABLE_V4_BACKFILL}...")
            try:
                query = f"""
                    SELECT DISTINCT
                        CAST(ROUND(latitude * 10000) AS INT64) AS lat4,
                        CAST(ROUND(longitude * 10000) AS INT64) AS lon4
                    FROM `{PROJECT}.{BQ_DATASET}.{BQ_TABLE_V4_BACKFILL}`
                """
                df_done = bq_client.query(query).to_dataframe()
                done_pixels_v4 = set(zip(df_done['lat4'], df_done['lon4']))
                print(f"    Found {len(done_pixels_v4):,} completed pixels in {BQ_TABLE_V4_BACKFILL}")
            except Exception as e:
                print(f"    WARNING: Could not read {BQ_TABLE_V4_BACKFILL}: {e}")
                print(f"    Proceeding without resume (will process all pixels)")
    
    # -------------------------------------------------------------------------
    # MODE 1: Phase C temporal re-sampling
    # -------------------------------------------------------------------------
    if args.phase_c_temporal:
        print(f"\n{'=' * 60}")
        print("PHASE C: TEMPORAL ENV RE-SAMPLING")
        print(f"{'=' * 60}")
        
        pixels = load_phase_c_pixels_with_years()
        
        # Filter out already-completed pixels (vectorized for speed)
        if done_pixels_tc:
            before = len(pixels)
            done_df = pd.DataFrame(list(done_pixels_tc), columns=['lat4', 'lon4'])
            done_df['_done'] = True
            pixels = pixels.merge(done_df, on=['lat4', 'lon4'], how='left')
            pixels = pixels[pixels['_done'].isna()].drop(columns=['_done']).copy()
            print(f"  Resume: {before:,} → {len(pixels):,} pixels (skipped {before - len(pixels):,} already done)")
        
        if args.test > 0:
            pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
            print(f"  TEST MODE: random sample of {len(pixels)} pixels")
        
        if len(pixels) == 0:
            print("  All Phase C temporal pixels already completed!")
        else:
            cohorts = build_year_cohorts(pixels, bin_width=args.year_bin_width,
                                         min_cohort_size=args.min_cohort_size)
            
            print("\n  Building temporal image stacks per cohort...")
            for cohort_year in sorted(cohorts.keys()):
                cohort_pixels = cohorts[cohort_year]
                # Use cohort midpoint for temporal image
                midpoint_year = cohort_year + args.year_bin_width // 2
                
                print(f"    Cohort {cohort_year}-{cohort_year + args.year_bin_width - 1}: "
                      f"{len(cohort_pixels):,} pixels, temporal year={midpoint_year}")
                
                image = build_temporal_image_for_year(midpoint_year)
                
                # Split cohort into batches (merge tiny trailing batches)
                batches = split_into_batches(cohort_pixels, BATCH_SIZE, MIN_BATCH_SIZE)
                for batch_df in batches:
                    all_batches.append((
                        batch_df, global_batch_idx, cohort_year,
                        image, BQ_TABLE_TEMPORAL, 'tc'
                    ))
                    global_batch_idx += 1
    
    # -------------------------------------------------------------------------
    # MODE 2: V4 environmental backfill
    # -------------------------------------------------------------------------
    if args.v4_backfill:
        print(f"\n{'=' * 60}")
        print("V4: ENVIRONMENTAL BACKFILL")
        print(f"{'=' * 60}")
        
        pixels = load_v4_pixels_with_years()
        
        # Filter out already-completed pixels (vectorized for speed)
        if done_pixels_v4:
            before = len(pixels)
            done_df = pd.DataFrame(list(done_pixels_v4), columns=['lat4', 'lon4'])
            done_df['_done'] = True
            pixels = pixels.merge(done_df, on=['lat4', 'lon4'], how='left')
            pixels = pixels[pixels['_done'].isna()].drop(columns=['_done']).copy()
            print(f"  Resume: {before:,} → {len(pixels):,} pixels (skipped {before - len(pixels):,} already done)")
        
        if args.test > 0:
            pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
            print(f"  TEST MODE: random sample of {len(pixels)} pixels")
        
        if len(pixels) == 0:
            print("  All V4 backfill pixels already completed!")
        else:
            cohorts = build_year_cohorts(pixels, bin_width=args.year_bin_width,
                                         min_cohort_size=args.min_cohort_size)
            
            print("\n  Building static env image stack (shared across all cohorts)...")
            static_image = build_static_env_image()
            n_static = static_image.bandNames().size().getInfo()
            print(f"    Static bands: {n_static}")
            
            print("  Building full (static + temporal) image stacks per cohort...")
            for cohort_year in sorted(cohorts.keys()):
                cohort_pixels = cohorts[cohort_year]
                midpoint_year = cohort_year + args.year_bin_width // 2
                
                print(f"    Cohort {cohort_year}-{cohort_year + args.year_bin_width - 1}: "
                      f"{len(cohort_pixels):,} pixels, temporal year={midpoint_year}")
                
                temporal_image = build_temporal_image_for_year(midpoint_year)
                full_image = static_image.addBands(temporal_image)
                
                # Split cohort into batches (merge tiny trailing batches)
                batches = split_into_batches(cohort_pixels, BATCH_SIZE, MIN_BATCH_SIZE)
                for batch_df in batches:
                    all_batches.append((
                        batch_df, global_batch_idx, cohort_year,
                        full_image, BQ_TABLE_V4_BACKFILL, 'v4bf'
                    ))
                    global_batch_idx += 1
    
    # -------------------------------------------------------------------------
    # MODE 3: V4 missing env pixels (from pre-exported parquet)
    # -------------------------------------------------------------------------
    if args.v4_missing:
        print(f"\n{'=' * 60}")
        print("V4 MISSING: ENV BACKFILL FOR PG-MISSING PIXELS")
        print(f"{'=' * 60}")
        
        v4m_batch_size = 4000  # Larger batches for this run
        
        pixels = load_v4_missing_pixels()
        
        # Filter out already-completed pixels if resuming
        if done_pixels_v4:
            before = len(pixels)
            done_df = pd.DataFrame(list(done_pixels_v4), columns=['lat4', 'lon4'])
            done_df['_done'] = True
            pixels = pixels.merge(done_df, on=['lat4', 'lon4'], how='left')
            pixels = pixels[pixels['_done'].isna()].drop(columns=['_done']).copy()
            print(f"  Resume: {before:,} → {len(pixels):,} pixels (skipped {before - len(pixels):,} already done)")
        
        if args.test > 0:
            pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
            print(f"  TEST MODE: random sample of {len(pixels)} pixels")
        
        if len(pixels) == 0:
            print("  All V4 missing pixels already completed!")
        else:
            cohorts = build_year_cohorts(pixels, bin_width=args.year_bin_width,
                                         min_cohort_size=args.min_cohort_size)
            
            print("\n  Building static env image stack (shared across all cohorts)...")
            static_image = build_static_env_image()
            n_static = static_image.bandNames().size().getInfo()
            print(f"    Static bands: {n_static}")
            
            print("  Building full (static + temporal) image stacks per cohort...")
            for cohort_year in sorted(cohorts.keys()):
                cohort_pixels = cohorts[cohort_year]
                midpoint_year = cohort_year + args.year_bin_width // 2
                
                print(f"    Cohort {cohort_year}-{cohort_year + args.year_bin_width - 1}: "
                      f"{len(cohort_pixels):,} pixels, temporal year={midpoint_year}")
                
                temporal_image = build_temporal_image_for_year(midpoint_year)
                full_image = static_image.addBands(temporal_image)
                
                # Split cohort into batches at 4000 (larger for this run)
                batches = split_into_batches(cohort_pixels, v4m_batch_size, MIN_BATCH_SIZE)
                for batch_df in batches:
                    all_batches.append((
                        batch_df, global_batch_idx, cohort_year,
                        full_image, BQ_TABLE_V4_MISSING, 'v4m'
                    ))
                    global_batch_idx += 1
    
    # -------------------------------------------------------------------------
    # MODE 4: Arctic backfill (>59°N pixels using Copernicus DEM)
    # -------------------------------------------------------------------------
    if args.arctic_backfill:
        print(f"\n{'=' * 60}")
        print(f"ARCTIC: ENV BACKFILL FOR >{ARCTIC_LAT_THRESHOLD}°N PIXELS (Copernicus DEM)")
        print(f"{'=' * 60}")
        
        arctic_batch_size = 2000  # Standard batch size
        
        pixels = load_arctic_pixels()
        
        if args.test > 0:
            pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
            print(f"  TEST MODE: random sample of {len(pixels)} pixels")
        
        if len(pixels) == 0:
            print("  All Arctic pixels already have env data!")
        else:
            cohorts = build_year_cohorts(pixels, bin_width=args.year_bin_width,
                                         min_cohort_size=args.min_cohort_size)
            
            print("\n  Building ARCTIC static env image stack (Copernicus DEM)...")
            static_image = build_static_env_image(arctic=True)
            n_static = static_image.bandNames().size().getInfo()
            print(f"    Static bands: {n_static}")
            
            print("  Building full (static + temporal) image stacks per cohort...")
            for cohort_year in sorted(cohorts.keys()):
                cohort_pixels = cohorts[cohort_year]
                midpoint_year = cohort_year + args.year_bin_width // 2
                
                print(f"    Cohort {cohort_year}-{cohort_year + args.year_bin_width - 1}: "
                      f"{len(cohort_pixels):,} pixels, temporal year={midpoint_year}")
                
                temporal_image = build_temporal_image_for_year(midpoint_year, arctic=True)
                full_image = static_image.addBands(temporal_image)
                
                batches = split_into_batches(cohort_pixels, arctic_batch_size, MIN_BATCH_SIZE)
                for batch_df in batches:
                    all_batches.append((
                        batch_df, global_batch_idx, cohort_year,
                        full_image, BQ_TABLE_ARCTIC, 'arc'
                    ))
                    global_batch_idx += 1
    
    # -------------------------------------------------------------------------
    # RUN
    # -------------------------------------------------------------------------
    print(f"\n  Total batches across all modes: {len(all_batches)}")
    
    if len(all_batches) == 0:
        print("  Nothing to do!")
        return
    
    # Show batch size distribution
    batch_sizes = [len(b[0]) for b in all_batches]
    print(f"  Batch sizes: min={min(batch_sizes)}, max={max(batch_sizes)}, "
          f"mean={sum(batch_sizes)/len(batch_sizes):.0f}, total_pixels={sum(batch_sizes):,}")
    
    # Shuffle batches to distribute cohorts (prevents geographic clustering within cohorts)
    import random
    random.seed(42)
    random.shuffle(all_batches)
    
    run_rolling_pool(
        all_batches,
        pool_size=args.pool_size,
        max_retries=args.max_retries,
    )


if __name__ == '__main__':
    main()
