#!/usr/bin/env python3
"""
Phase C: Regime 2 Sampler — Full Environmental Stack
=====================================================

Samples AlphaEarth 2017 embeddings + 65 environmental bands at pre-2017
occurrence pixels that are NOT in the v4 dataset.

This is the "one shot" extraction: since GEE compute is bottlenecked by
AlphaEarth sampleRegions(), piggybacking ~65 static/temporal environmental
bands adds negligible cost and gives us the complete training dataset for
the neural prediction head (SINR-style, ~129-D input).

Scope (corrected Feb 11, 2026):
  - 4,733,903 unique pixels at 4dp (~11m) from pre-2017 + unknown-year
    occurrences, NOT already in v4
  - Covering 59,280 species (37,308 new + 21,972 enriching existing)
  - After Hansen loss filter: ~4M usable pixels
  - GEE tasks at 2000 pts/task: ~2,000 tasks
  - Cost: $1-10 (GEE free tier + minimal BQ)

Output: BigQuery table with 129 bands per pixel:
  - 64 AlphaEarth embedding bands (A00-A63)
  - 65 environmental bands (climate, soil, terrain, forest, hydro, human, ecosystem)

Pipeline:
  1. Load 96M occurrence parquet, filter to pre-2017 + unknown year
  2. Deduplicate to unique pixels at 4dp
  3. Exclude pixels already in v4
  4. Filter to >= 3dp coordinate precision (usable for pixel-level matching)
  5. Sample AlphaEarth 2017 + full env stack at each pixel via GEE
  6. Export to BigQuery in batches of 2000
  7. After export: rejoin embeddings to species, load to k-NN table

Usage:
    # Dry run — show scope and cost estimate
    python3 regime2_sampler.py --dry-run

    # Test with 100 pixels
    python3 regime2_sampler.py --test 100

    # Submit all tasks (don't wait)
    python3 regime2_sampler.py --all --no-wait

    # Submit and monitor
    python3 regime2_sampler.py --all

    # Resume from checkpoint (skip already-exported pixels)
    python3 regime2_sampler.py --all --resume

    # Submit specific batch range (for parallel runs)
    python3 regime2_sampler.py --all --batch-start 0 --batch-end 500

Author: Treekipedia Team
Created: February 11, 2026
"""

import ee
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Set, Tuple
import time
import json
from pathlib import Path
from datetime import datetime
import argparse
import sys

# =============================================================================
# CONFIGURATION
# =============================================================================

# GCP / BigQuery
PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
BQ_TABLE = 'phase_c_embeddings_env_v1'

# GEE data sources
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'
SRTM_ASSET = 'USGS/SRTMGL1_003'

# Processing settings
BATCH_SIZE = 2000           # Points per GEE export task
AE_SCALE = 10              # AlphaEarth native resolution (10m)
HANSEN_SCALE = 30           # Hansen resolution
SRTM_SCALE = 30             # SRTM resolution
ENV_SCALE_COARSE = 250      # For soil, topo diversity
ENV_SCALE_MED = 30          # For water, terrain derivatives
ENV_SCALE_CLIMATE = 1000    # For WorldClim, TerraClimate, ERA5
TARGET_YEAR = 2017          # AlphaEarth year for pre-2017 occurrences

COORD_DECIMALS = 4          # 4dp = ~11m precision, matches v4
MIN_COORD_PRECISION = 3     # Reject coordinates with < 3dp in either axis

# Paths
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent

V4_PARQUET = SCRIPT_DIR / "bigquery_exports/alphaearth_embeddings_v4/alphaearth_embeddings_v4_COMPLETE.parquet"
OCC_PARQUET = ROOT_DIR / "Treekipedia_occ_YEAR_CoordinateUncertainty_EstablishmentMeans_LatLong_TaxonId_CORRECT_december_18d_2025.parquet"

OUTPUT_DIR = SCRIPT_DIR / "expansion_phase_c"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"

AE_BANDS = [f"A{i:02d}" for i in range(64)]


# =============================================================================
# GEE INITIALIZATION
# =============================================================================

def initialize_gee():
    """Initialize Google Earth Engine."""
    try:
        ee.Initialize(project=PROJECT)
        print(f"GEE initialized (project: {PROJECT})")
        return True
    except Exception as e:
        print(f"GEE initialization failed: {e}")
        print("Run 'earthengine authenticate' if needed")
        return False


# =============================================================================
# IMAGE STACK BUILDERS
# =============================================================================

def get_alphaearth_2017() -> ee.Image:
    """Get AlphaEarth mosaic for 2017 (target year for pre-2017 occurrences)."""
    col = ee.ImageCollection(AE_COLLECTION).filterDate('2017-01-01', '2017-12-31')
    return col.mosaic()


def get_hansen_image() -> ee.Image:
    """Hansen Global Forest Change — treecover, loss, lossyear, gain."""
    hansen = ee.Image(HANSEN_ASSET)
    return (
        hansen.select('treecover2000')
        .addBands(hansen.select('lossyear').unmask(0))
        .addBands(hansen.select('loss'))
        .addBands(hansen.select('gain'))
    )


def get_srtm_with_terrain() -> ee.Image:
    """SRTM elevation + terrain derivatives (slope, aspect, hillshade)."""
    srtm = ee.Image(SRTM_ASSET).select('elevation')
    terrain = ee.Terrain.products(srtm)
    # terrain has: elevation, slope, aspect, hillshade
    return terrain


def get_worldclim_bio() -> ee.Image:
    """WorldClim V1 BIO — 19 bioclimatic variables."""
    return ee.Image('WORLDCLIM/V1/BIO')


def get_soil_stack() -> ee.Image:
    """OpenLandMap soil properties — pH, clay, sand, OC, texture, bulk density, water content.
    
    All have multiple depth bands (b0=0cm, b10=10cm, etc.). We take b0 (surface).
    """
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')
    soil_clay = ee.Image('OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_clay_pct')
    soil_sand = ee.Image('OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02').select('b0').rename('soil_sand_pct')
    soil_oc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0').rename('soil_organic_carbon')
    soil_texture = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02').select('b0').rename('soil_texture_class')
    soil_bulk = ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02').select('b0').rename('soil_bulk_density')
    soil_water = ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01').select('b0').rename('soil_water_content')
    
    return (soil_ph.addBands(soil_clay).addBands(soil_sand)
            .addBands(soil_oc).addBands(soil_texture)
            .addBands(soil_bulk).addBands(soil_water))


def get_forest_stack() -> ee.Image:
    """Forest/vegetation structure layers.
    
    - JRC Global Forest Types 2020: primary forest flag (value 10 = primary)
    - JRC TMF Transition Subtypes: tropical moist forest status
    - JRC TMF Degradation Year: when degradation first detected
    - GEDI Gridded: canopy height (rh98) + foliage height diversity
    - ORNL Biomass: aboveground biomass carbon density (Mg C/ha)
    - ESA WorldCover 2021: baseline land cover class
    """
    jrc_forest = ee.Image('JRC/GFC2020_subtypes/V1').select('Map').rename('jrc_forest_type')
    
    # JRC TMF — only exists for tropical moist forest zone, unmask to 0
    jrc_tmf = ee.ImageCollection('projects/JRC/TMF/v1_2024/TransitionMap_Subtypes').mosaic().select('TransitionMap_Subtypes').unmask(0).rename('jrc_tmf_status')
    jrc_degrad = ee.ImageCollection('projects/JRC/TMF/v1_2024/DegradationYear').mosaic().select('constant').unmask(0).rename('jrc_tmf_degrad_year')
    
    # GEDI gridded at 1km — canopy height and foliage height diversity
    gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
    gedi_rh98 = gedi.select('rh98').unmask(0).rename('gedi_canopy_height_m')
    gedi_fhd = gedi.select('fhd').unmask(0).rename('gedi_foliage_height_div')
    
    # ORNL Biomass (ImageCollection — mosaic)
    biomass = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic().select('agb').unmask(0).rename('biomass_agb_mgha')
    
    # ESA WorldCover 2021 (ImageCollection — mosaic to single Image)
    worldcover = ee.ImageCollection('ESA/WorldCover/v200').mosaic().select('Map').rename('esa_worldcover_2021')
    
    return (jrc_forest.addBands(jrc_tmf).addBands(jrc_degrad)
            .addBands(gedi_rh98).addBands(gedi_fhd)
            .addBands(biomass).addBands(worldcover))


def get_hydrology_stack() -> ee.Image:
    """JRC Global Surface Water — occurrence, recurrence, seasonality."""
    gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
    return (
        gsw.select('occurrence').unmask(0).rename('water_occurrence')
        .addBands(gsw.select('recurrence').unmask(0).rename('water_recurrence'))
        .addBands(gsw.select('seasonality').unmask(0).rename('water_seasonality'))
    )


def get_human_stack() -> ee.Image:
    """Human impact layers.
    
    - CSP Human Modification Index (0-1)
    - SBTN Natural Lands (natural/non-natural)
    - VIIRS Nighttime Lights (urbanization proxy, 2022 annual composite)
    """
    human_mod = ee.ImageCollection('CSP/HM/GlobalHumanModification').mosaic().select('gHM').rename('human_modification')
    sbtn = ee.Image('WRI/SBTN/naturalLands/v1_1/2020').select('natural').unmask(0).rename('sbtn_natural_land')
    
    # VIIRS annual composite — use 2022 (recent, complete)
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
             .filterDate('2022-01-01', '2022-12-31')
             .select('avg_rad')
             .mean()
             .rename('nighttime_lights'))
    
    return human_mod.addBands(sbtn).addBands(viirs)


def get_topo_diversity() -> ee.Image:
    """CSP Topographic Diversity (270m)."""
    return ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').select('constant').rename('topo_diversity')


def get_merit_hydro() -> ee.Image:
    """MERIT Hydro — Height Above Nearest Drainage (HAND) + flow accumulation."""
    merit = ee.Image('MERIT/Hydro/v1_0_1')
    return (
        merit.select('hnd').unmask(0).rename('merit_hand_m')
        .addBands(merit.select('upa').unmask(0).rename('merit_upstream_area_km2'))
    )


def get_ecoregion_image() -> ee.Image:
    """RESOLVE Ecoregions 2017 — ECO_ID and BIOME_NUM as raster bands.
    
    We rasterize from the FeatureCollection to get per-pixel values.
    """
    ecoregions = ee.FeatureCollection('RESOLVE/ECOREGIONS/2017')
    eco_id = ecoregions.reduceToImage(properties=['ECO_ID'], reducer=ee.Reducer.first()).rename('eco_id')
    biome_num = ecoregions.reduceToImage(properties=['BIOME_NUM'], reducer=ee.Reducer.first()).rename('biome_num')
    return eco_id.addBands(biome_num)


def get_terraclimate_annual() -> ee.Image:
    """TerraClimate annual means (2015-2020 climatology).
    
    Key variables for plant ecology:
    - VPD (vapor pressure deficit) — drought stress
    - AET (actual evapotranspiration) — water availability
    - Soil moisture
    - PDSI (Palmer Drought Severity Index)
    - Climatic water deficit
    - Solar radiation (srad)
    """
    tc = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
          .filterDate('2015-01-01', '2020-12-31')
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


def get_dynamic_world_2023() -> ee.Image:
    """Dynamic World — mode land cover class for 2023."""
    dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
          .filterDate('2023-01-01', '2023-12-31')
          .select('label'))
    return dw.mode().rename('dynamic_world_2023')


def get_modis_productivity() -> ee.Image:
    """MODIS GPP — mean annual gross primary productivity (2015-2023).
    
    Masks sentinel/fill values (65530-65535) before computing mean.
    Raw integer units (multiply by 0.0001 for kg C/m²/yr).
    """
    gpp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filterDate('2015-01-01', '2023-12-31')
           .select('Gpp')
           .map(lambda img: img.updateMask(img.lt(65530))))
    return gpp.mean().rename('modis_gpp_mean')


def get_modis_fire_frequency() -> ee.Image:
    """MODIS Burned Area — count of burn events 2001-2023."""
    burned = (ee.ImageCollection('MODIS/061/MCD64A1')
              .filterDate('2001-01-01', '2023-12-31')
              .select('BurnDate'))
    # Count months with any burn detected
    burn_count = burned.map(lambda img: img.gt(0).unmask(0)).sum()
    return burn_count.rename('fire_frequency_count')


def build_combined_image() -> ee.Image:
    """Build a single combined image with ALL environmental bands.
    
    Returns a single ee.Image with all bands merged. GEE's sampleRegions()
    at 10m scale will sample each band at its native resolution — a 1km band
    returns the 1km pixel value at the point, no resolution loss.
    
    This approach uses ONE sampleRegions() call instead of 1 sampleRegions +
    9 reduceRegions, reducing EECU from ~4000 to ~500 per task.
    
    All categorical/integer bands are explicitly cast with .toInt() and all
    float bands with .toFloat() to prevent BigQuery schema mismatches across
    batches (e.g. jrc_forest_type appearing as STRING in some regions).
    """
    print("  Building combined image stack...")
    
    # --- 10m native ---
    jrc_forest = ee.Image('JRC/GFC2020_subtypes/V1').select('Map').unmask(0).rename('jrc_forest_type').toInt()
    worldcover = ee.ImageCollection('ESA/WorldCover/v200').mosaic().select('Map').unmask(0).rename('esa_worldcover_2021').toInt()
    sbtn = ee.Image('WRI/SBTN/naturalLands/v1_1/2020').select('natural').unmask(0).rename('sbtn_natural_land').toInt()
    dw = get_dynamic_world_2023().toInt()
    
    # --- 30m native ---
    srtm_terrain = get_srtm_with_terrain()  # elevation(int), slope(int), aspect(int), hillshade(int)
    hansen = get_hansen_image()  # treecover2000(int), lossyear(int), loss(int), gain(int)
    jrc_tmf = ee.ImageCollection('projects/JRC/TMF/v1_2024/TransitionMap_Subtypes').mosaic().select('TransitionMap_Subtypes').unmask(0).rename('jrc_tmf_status').toInt()
    jrc_degrad = ee.ImageCollection('projects/JRC/TMF/v1_2024/DegradationYear').mosaic().select('constant').unmask(0).rename('jrc_tmf_degrad_year').toInt()
    hydro = get_hydrology_stack()  # water_occurrence(int), water_recurrence(int), water_seasonality(int)
    
    # --- 90m native ---
    merit = get_merit_hydro()  # merit_hand_m(float), merit_upstream_area_km2(float)
    
    # --- 250m native ---
    soil = get_soil_stack()  # 7 soil bands (int)
    topo_div = get_topo_diversity()  # topo_diversity(float)
    
    # --- 300m native ---
    biomass = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic().select('agb').unmask(0).rename('biomass_agb_mgha').toFloat()
    
    # --- 500m native ---
    gpp = get_modis_productivity().toFloat()  # modis_gpp_mean(float)
    fire = get_modis_fire_frequency().toInt()  # fire_frequency_count(int)
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
             .filterDate('2022-01-01', '2022-12-31')
             .select('avg_rad')
             .mean()
             .unmask(0)
             .rename('nighttime_lights')
             .toFloat())
    
    # --- 1km native ---
    worldclim = get_worldclim_bio()  # 19 bio bands (float)
    gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
    gedi_canopy = gedi.select('p95').unmask(0).rename('gedi_canopy_height_m').toFloat()
    gedi_fhd = gedi.select('shan').unmask(0).rename('gedi_foliage_height_div').toFloat()
    human_mod = ee.ImageCollection('CSP/HM/GlobalHumanModification').mosaic().select('gHM').unmask(0).rename('human_modification').toFloat()
    ecoregions = get_ecoregion_image()  # eco_id(int), biome_num(int/float)
    
    # --- 4km native ---
    terraclimate = get_terraclimate_annual()  # 6 tc_ bands (float)
    
    # Chain all bands into one image
    combined = (
        jrc_forest
        .addBands(worldcover)
        .addBands(sbtn)
        .addBands(dw)
        .addBands(srtm_terrain)
        .addBands(hansen)
        .addBands(jrc_tmf)
        .addBands(jrc_degrad)
        .addBands(hydro)
        .addBands(merit)
        .addBands(soil)
        .addBands(topo_div)
        .addBands(biomass)
        .addBands(gpp)
        .addBands(fire)
        .addBands(viirs)
        .addBands(worldclim)
        .addBands(gedi_canopy)
        .addBands(gedi_fhd)
        .addBands(human_mod)
        .addBands(ecoregions)
        .addBands(terraclimate)
    )
    
    # Cast ALL bands to float64 to guarantee consistent BigQuery schema across batches.
    # Without this, bands like jrc_forest_type can appear as STRING in some regions
    # and INTEGER in others, causing schema mismatch failures.
    # Integer codes (forest type 10, ecoregion 171) are stored as 10.0, 171.0 — fine.
    combined = combined.toFloat()
    
    n_bands = combined.bandNames().size().getInfo()
    band_names = combined.bandNames().getInfo()
    print(f"    Combined environmental image: {n_bands} bands (all float64)")
    print(f"    Bands: {', '.join(band_names[:10])}... {', '.join(band_names[-5:])}")
    
    return combined


# =============================================================================
# COORDINATE UTILITIES
# =============================================================================

def ensure_float_coordinate(value: float) -> float:
    """Ensure coordinate is a proper float, not interpretable as integer."""
    float_val = float(value)
    if float_val == int(float_val):
        return float_val + 1e-10
    return float_val


def filter_low_precision_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out coordinates with < MIN_COORD_PRECISION decimal places.
    
    A coordinate like 45.1 (1dp) represents ~10km precision — useless for
    10m pixel-level sampling. We require >= 3dp on BOTH lat and lon.
    
    Method: at 4dp integer representation, low-precision coordinates end
    in trailing zeros:
      1dp (45.1)    -> 451000 -> mod 1000 == 0
      2dp (45.12)   -> 451200 -> mod 100 == 0
      3dp (45.123)  -> 451230 -> mod 10 == 0  (acceptable)
      4dp+ (45.1234) -> 451234 -> no pattern  (good)
    """
    before = len(df)
    
    lat4 = (df['decimalLatitude'] * 10000).round().astype(np.int64)
    lon4 = (df['decimalLongitude'] * 10000).round().astype(np.int64)
    
    # Either lat or lon at 1dp (~10km) = reject
    is_1dp_lat = (lat4 % 1000 == 0)
    is_1dp_lon = (lon4 % 1000 == 0)
    
    # Either at 2dp (~1km) = reject  
    is_2dp_lat = (lat4 % 100 == 0) & ~is_1dp_lat
    is_2dp_lon = (lon4 % 100 == 0) & ~is_1dp_lon
    
    # Reject if either axis is <= 2dp
    low_precision = (is_1dp_lat | is_1dp_lon | is_2dp_lat | is_2dp_lon)
    
    df_filtered = df[~low_precision].copy()
    after = len(df_filtered)
    
    print(f"  Coordinate precision filter (>= 3dp): {before:,} -> {after:,} "
          f"(removed {before - after:,}, {(before - after) / before * 100:.1f}%)")
    
    return df_filtered


# =============================================================================
# DATA LOADING & DEDUPLICATION
# =============================================================================

def load_v4_pixel_set() -> Set[Tuple[int, int]]:
    """Load v4 pixel coordinates as integer keys for fast lookup."""
    import pyarrow.parquet as pq
    
    print(f"  Loading v4 parquet: {V4_PARQUET.name}")
    v4 = pq.read_table(V4_PARQUET, columns=['latitude', 'longitude']).to_pandas()
    v4['lat4'] = (v4['latitude'] * 10000).round().astype(np.int64)
    v4['lon4'] = (v4['longitude'] * 10000).round().astype(np.int64)
    
    pixel_set = set(zip(v4['lat4'].values, v4['lon4'].values))
    print(f"  V4 pixels loaded: {len(pixel_set):,}")
    return pixel_set


def load_processed_pixel_set() -> Set[Tuple[int, int]]:
    """Load already-processed Phase C pixels from checkpoint files."""
    processed = set()
    
    if not CHECKPOINT_DIR.exists():
        return processed
    
    checkpoint_files = sorted(CHECKPOINT_DIR.glob("phase_c_batch_*.json"))
    for f in checkpoint_files:
        try:
            with open(f) as fh:
                data = json.load(fh)
                if data.get('status') == 'submitted':
                    # Add all pixels in this batch as "in progress"
                    for px in data.get('pixels', []):
                        processed.add((px[0], px[1]))
        except Exception:
            continue
    
    if processed:
        print(f"  Loaded {len(processed):,} already-submitted pixels from checkpoints")
    
    return processed


def load_bq_pixel_set() -> Set[Tuple[int, int]]:
    """Load already-exported pixels from BigQuery Phase C table.
    
    Queries the BQ table for all distinct (lat, lon) pairs already written,
    so we can skip them on resume. This is the definitive source of truth
    (checkpoints only track submissions, not successful writes).
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=PROJECT)
        
        query = f"""
        SELECT DISTINCT 
            CAST(ROUND(latitude * 10000) AS INT64) as lat4,
            CAST(ROUND(longitude * 10000) AS INT64) as lon4
        FROM `{PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        """
        
        print(f"  Querying BigQuery for already-exported pixels...")
        df = client.query(query).to_dataframe()
        pixel_set = set(zip(df['lat4'].values, df['lon4'].values))
        print(f"  Already in BQ: {len(pixel_set):,} unique pixels")
        return pixel_set
        
    except Exception as e:
        print(f"  WARNING: Could not query BQ ({e})")
        print(f"  Proceeding without BQ resume — may re-sample already-exported pixels")
        return set()


def load_and_prepare_pixels(resume: bool = False, resume_from_bq: bool = False) -> pd.DataFrame:
    """Load occurrence data, deduplicate to unique pixels, filter.
    
    Returns DataFrame with columns: lat4, lon4, latitude, longitude
    (one row per unique pixel to sample)
    
    Args:
        resume: Skip pixels in checkpoint files (tracks submissions, not completions)
        resume_from_bq: Skip pixels already in BigQuery (definitive, tracks actual data)
    """
    import pyarrow.parquet as pq
    
    # Step 1: Load v4 pixel set
    print("\n1. LOADING V4 PIXEL SET:")
    v4_pixels = load_v4_pixel_set()
    
    # Step 2: Load occurrence data
    print("\n2. LOADING OCCURRENCE PARQUET:")
    print(f"  File: {OCC_PARQUET.name}")
    
    occ = pq.read_table(
        OCC_PARQUET,
        columns=['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year']
    ).to_pandas()
    
    # Drop null taxon_ids
    null_count = occ['taxon_id'].isna().sum()
    if null_count > 0:
        occ = occ.dropna(subset=['taxon_id'])
        print(f"  Dropped {null_count:,} rows with null taxon_id")
    
    print(f"  Total rows: {len(occ):,}")
    print(f"  Total species: {occ['taxon_id'].nunique():,}")
    
    # Step 3: Filter to pre-2017 + unknown year
    print("\n3. FILTERING TO PRE-2017 + UNKNOWN YEAR:")
    mask = (occ['year'].isna()) | ((occ['year'] > 0) & (occ['year'] < 2017))
    phase_c_occ = occ[mask].copy()
    print(f"  Pre-2017 + unknown year: {len(phase_c_occ):,} rows")
    print(f"  Species: {phase_c_occ['taxon_id'].nunique():,}")
    
    # Step 4: Filter low-precision coordinates
    print("\n4. COORDINATE PRECISION FILTER:")
    phase_c_occ = filter_low_precision_coords(phase_c_occ)
    
    # Step 5: Create integer pixel keys
    print("\n5. DEDUPLICATING TO UNIQUE PIXELS:")
    phase_c_occ['lat4'] = (phase_c_occ['decimalLatitude'] * 10000).round().astype(np.int64)
    phase_c_occ['lon4'] = (phase_c_occ['decimalLongitude'] * 10000).round().astype(np.int64)
    
    # Deduplicate to unique pixels (species-independent)
    pixels = phase_c_occ[['lat4', 'lon4', 'decimalLatitude', 'decimalLongitude']].copy()
    pixels = pixels.drop_duplicates(subset=['lat4', 'lon4'], keep='first')
    pixels = pixels.rename(columns={
        'decimalLatitude': 'latitude',
        'decimalLongitude': 'longitude'
    })
    print(f"  Unique pixels (4dp): {len(pixels):,}")
    
    # Step 6: Exclude v4 pixels
    print("\n6. EXCLUDING V4 PIXELS:")
    pixels['pixel_key'] = list(zip(pixels['lat4'].values, pixels['lon4'].values))
    v4_mask = pixels['pixel_key'].isin(v4_pixels)
    n_in_v4 = v4_mask.sum()
    pixels = pixels[~v4_mask].drop(columns=['pixel_key'])
    print(f"  Already in v4: {n_in_v4:,}")
    print(f"  New pixels to sample: {len(pixels):,}")
    
    # Step 7a: Resume from BigQuery (definitive — skip already-exported pixels)
    if resume_from_bq:
        print("\n7. RESUMING FROM BIGQUERY (definitive):")
        bq_pixels = load_bq_pixel_set()
        if bq_pixels:
            pixels['pixel_key'] = list(zip(pixels['lat4'].values, pixels['lon4'].values))
            already_done = pixels['pixel_key'].isin(bq_pixels).sum()
            pixels = pixels[~pixels['pixel_key'].isin(bq_pixels)].drop(columns=['pixel_key'])
            print(f"  Already exported to BQ: {already_done:,}")
            print(f"  Remaining: {len(pixels):,}")
    
    # Step 7b: Resume from checkpoints (tracks submissions, not completions)
    elif resume:
        print("\n7. CHECKING CHECKPOINTS:")
        processed = load_processed_pixel_set()
        if processed:
            pixels['pixel_key'] = list(zip(pixels['lat4'].values, pixels['lon4'].values))
            already_done = pixels['pixel_key'].isin(processed).sum()
            pixels = pixels[~pixels['pixel_key'].isin(processed)].drop(columns=['pixel_key'])
            print(f"  Already submitted: {already_done:,}")
            print(f"  Remaining: {len(pixels):,}")
    
    # Step 8: Summary stats
    print(f"\n{'=' * 60}")
    print(f"PHASE C SCOPE")
    print(f"{'=' * 60}")
    print(f"  Pixels to sample: {len(pixels):,}")
    print(f"  GEE tasks at {BATCH_SIZE}/task: {len(pixels) // BATCH_SIZE + 1:,}")
    print(f"  Target: AlphaEarth {TARGET_YEAR} + ~65 environmental bands")
    
    # Lat/lon ranges
    print(f"\n  Latitude range: {pixels['latitude'].min():.2f} to {pixels['latitude'].max():.2f}")
    print(f"  Longitude range: {pixels['longitude'].min():.2f} to {pixels['longitude'].max():.2f}")
    
    # Shuffle pixels globally so batches aren't geographically clustered.
    # Without this, consecutive batches can all fall in an AlphaEarth coverage
    # gap (e.g. 2000 pixels in rural France with no AE tile) → entire batch
    # returns empty FeatureCollection → wasted retries.
    # Shuffling distributes gaps across all batches: each gets ~1400-2000 rows.
    print(f"\n  Shuffling pixels (random_state=42)...")
    pixels = pixels.sample(frac=1, random_state=42).reset_index(drop=True)
    
    return pixels


# =============================================================================
# SAMPLING
# =============================================================================

def sample_batch(
    batch_df: pd.DataFrame,
    batch_idx: int,
    combined_img: ee.Image,
    dry_run: bool = False
) -> Optional[str]:
    """Sample one batch of pixels: AlphaEarth + full environmental stack.
    
    Strategy:
    1. Create FeatureCollection from pixel coordinates
    2. Single sampleRegions() at 10m with the combined image (AE + all env)
    3. Export to BigQuery
    
    Using ONE sampleRegions() call with a combined image instead of chained
    reduceRegions() calls. GEE samples each band at its native resolution 
    regardless of the scale parameter — no resolution loss.
    
    Args:
        batch_df: DataFrame with latitude, longitude columns
        batch_idx: Batch index for naming
        combined_img: Single ee.Image with AlphaEarth + all environmental bands
        dry_run: If True, don't submit task
        
    Returns:
        GEE task ID, or None if dry run
    """
    # Build feature collection — vectorized for speed.
    # Using list comprehension over .values instead of iterrows() (50x faster).
    lats = batch_df['latitude'].values
    lons = batch_df['longitude'].values
    
    features = [
        ee.Feature(
            ee.Geometry.Point([float(lon), float(lat)]),
            {'latitude': float(lat), 'longitude': float(lon), 'emb_year': TARGET_YEAR}
        )
        for lat, lon in zip(lats, lons)
    ]
    
    fc = ee.FeatureCollection(features)
    
    # Single sampleRegions call — samples ALL bands at the point location.
    # Each band is sampled at its native resolution (10m AE, 30m SRTM, 1km WorldClim, etc.)
    sampled = combined_img.sampleRegions(
        collection=fc,
        scale=AE_SCALE,
        geometries=False,
        tileScale=4
    )
    
    if dry_run:
        return None
    
    # Export to BigQuery
    task_desc = f'phase_c_{datetime.now().strftime("%Y%m%d")}_{batch_idx:05d}'
    
    task = ee.batch.Export.table.toBigQuery(
        collection=sampled,
        description=task_desc,
        table=f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}',
        append=True,
        overwrite=False
    )
    task.start()
    
    return task.id


def run_sampling(
    pixels: pd.DataFrame,
    batch_size: int = BATCH_SIZE,
    dry_run: bool = False,
    no_wait: bool = False,
    batch_start: Optional[int] = None,
    batch_end: Optional[int] = None,
    pool_size: int = 25,
    max_retries: int = 3,
) -> List[str]:
    """Run the full Phase C sampling pipeline.
    
    Rolling pool approach: maintains up to `pool_size` concurrent GEE tasks.
    As each task completes, a new one is immediately submitted. Failed tasks
    are re-queued individually with backoff — no waiting for entire waves.
    
    This maximizes throughput: one slow task never blocks new submissions,
    and failed tasks get retried without stalling the pipeline.
    
    Args:
        pixels: DataFrame of unique pixels to sample
        batch_size: Points per GEE task
        dry_run: Show plan without submitting
        no_wait: Submit all tasks without monitoring (fire-and-forget, NOT recommended)
        batch_start: Start batch index
        batch_end: End batch index
        pool_size: Max concurrent GEE tasks (default 25)
        max_retries: Max retry attempts per individual batch
    """
    n_total = len(pixels)
    n_tasks = (n_total - 1) // batch_size + 1
    
    # Apply batch range filter
    if batch_start is not None or batch_end is not None:
        start = batch_start or 0
        end = min(batch_end or n_tasks, n_tasks)
        print(f"\n  Batch range: {start}-{end} (of {n_tasks} total)")
    else:
        start = 0
        end = n_tasks
    
    actual_batches = end - start
    
    print(f"\n{'=' * 60}")
    print(f"SAMPLING {n_total:,} PIXELS IN {actual_batches:,} BATCHES")
    print(f"{'=' * 60}")
    print(f"  Batch size: {batch_size}")
    print(f"  Pool size: {pool_size} concurrent tasks")
    print(f"  Max retries per batch: {max_retries}")
    print(f"  Target: AlphaEarth {TARGET_YEAR} + environmental stack")
    print(f"  Destination: {PROJECT}.{BQ_DATASET}.{BQ_TABLE}")
    
    if dry_run:
        # ~8 min avg per task, pool_size concurrent = pool_size tasks per 8 min
        avg_task_min = 8
        throughput = pool_size / avg_task_min  # tasks/min
        est_hours = actual_batches / throughput / 60
        print(f"\n  Estimated time: {actual_batches} tasks / {throughput:.1f} tasks/min = ~{est_hours:.1f} hours")
        print(f"\n  [DRY RUN — no tasks submitted]")
        return []
    
    # Build image stack (one-time GEE computation)
    print("\n  Building GEE image stack...")
    ae_img = get_alphaearth_2017()
    env_img = build_combined_image()
    
    # Combine AlphaEarth + environmental into ONE image
    combined_img = ae_img.addBands(env_img)
    total_bands = combined_img.bandNames().size().getInfo()
    print(f"  Final combined image: {total_bands} bands (AlphaEarth + environmental)")
    
    # Create output/checkpoint directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    global_start_time = time.time()
    
    # ─── Fire-and-forget mode ───
    # Submit ALL tasks to GEE's queue at once, then exit.
    # GEE processes them serverside (~3 concurrent). No local process needed.
    # Use this when you can't keep the local machine running (e.g. before a flight).
    # Failed tasks can be recovered later with --resume-from-bq.
    if no_wait:
        print(f"\n  FIRE-AND-FORGET: submitting all {actual_batches} tasks to GEE queue...")
        print(f"  GEE will process ~3 concurrently. No local monitoring needed.")
        print(f"  Run failed tasks later with: --all --resume-from-bq\n")
        
        all_task_ids = []
        failed_submits = []
        
        for i, batch_idx in enumerate(range(start, end)):
            chunk_start = batch_idx * batch_size
            chunk_end = min(chunk_start + batch_size, n_total)
            batch_df = pixels.iloc[chunk_start:chunk_end]
            
            if len(batch_df) == 0:
                continue
            
            try:
                task_id = sample_batch(batch_df, batch_idx, combined_img, dry_run=False)
                all_task_ids.append(task_id)
            except Exception as e:
                failed_submits.append((batch_idx, str(e)))
                time.sleep(1)
            
            if (i + 1) % 100 == 0 or i == 0:
                print(f"  Submitted {i + 1}/{actual_batches} tasks...")
        
        elapsed = time.time() - global_start_time
        print(f"\n  Done. Submitted {len(all_task_ids)} tasks in {elapsed/60:.1f} min.")
        if failed_submits:
            print(f"  Submit failures: {len(failed_submits)}")
        print(f"\n  Monitor: https://code.earthengine.google.com/tasks")
        print(f"  Check BQ: bq query 'SELECT COUNT(*) FROM {BQ_DATASET}.{BQ_TABLE}'")
        print(f"  After completion, recover failures with:")
        print(f"    python3 regime2_sampler.py --all --resume-from-bq")
        
        # Save manifest
        task_file = OUTPUT_DIR / f"phase_c_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(task_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'mode': 'fire-and-forget',
                'n_tasks_submitted': len(all_task_ids),
                'n_submit_failures': len(failed_submits),
                'batch_range': [start, end],
                'bq_table': f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}',
            }, f, indent=2)
        
        return all_task_ids
    
    # ─── Rolling pool state ───
    # pool: dict of task_id -> {batch_idx, batch_df, attempt, submit_time}
    pool = {}
    
    # Queue of batch indices still to submit
    submit_queue = list(range(start, end))
    
    # Retry queue: list of (batch_idx, batch_df, attempt)
    retry_queue = []
    
    # Counters
    all_completed = 0
    all_failed_permanent = []
    all_task_ids = []
    last_progress_time = 0
    
    POLL_INTERVAL = 30  # seconds between status checks
    TASK_TIMEOUT = 45 * 60  # 45 min per individual task (30 min caused ~110 false timeouts)
    
    print(f"\n  Starting rolling pool (poll every {POLL_INTERVAL}s)...\n")
    
    def _submit_one(batch_idx: int, batch_df: pd.DataFrame, attempt: int = 1) -> bool:
        """Submit one batch to GEE. Returns True if submitted successfully."""
        try:
            task_id = sample_batch(batch_df, batch_idx, combined_img, dry_run=False)
            pool[task_id] = {
                'batch_idx': batch_idx,
                'batch_df': batch_df,
                'attempt': attempt,
                'submit_time': time.time(),
            }
            all_task_ids.append(task_id)
            
            # Save checkpoint
            checkpoint = {
                'batch_idx': batch_idx,
                'task_id': task_id,
                'n_pixels': len(batch_df),
                'status': 'submitted',
                'attempt': attempt,
                'timestamp': datetime.now().isoformat(),
            }
            cp_file = CHECKPOINT_DIR / f"phase_c_batch_{batch_idx:05d}.json"
            with open(cp_file, 'w') as f:
                json.dump(checkpoint, f)
            return True
            
        except Exception as e:
            print(f"  SUBMIT ERROR batch {batch_idx} (attempt {attempt}): {e}")
            if attempt < max_retries:
                retry_queue.append((batch_idx, batch_df, attempt + 1))
            else:
                all_failed_permanent.append((batch_idx, f"Submit failed: {e}"))
            return False
    
    def _fill_pool():
        """Fill the pool up to pool_size from submit_queue and retry_queue."""
        while len(pool) < pool_size:
            # Prioritize retries (they've already been computed once, just BQ failed)
            if retry_queue:
                bidx, bdf, attempt = retry_queue.pop(0)
                _submit_one(bidx, bdf, attempt)
            elif submit_queue:
                bidx = submit_queue.pop(0)
                chunk_start = bidx * batch_size
                chunk_end = min(chunk_start + batch_size, n_total)
                batch_df = pixels.iloc[chunk_start:chunk_end]
                if len(batch_df) > 0:
                    _submit_one(bidx, batch_df)
            else:
                break  # nothing left to submit
    
    # Initial fill
    _fill_pool()
    print(f"  Initial pool: {len(pool)} tasks submitted")
    
    # Main poll loop
    while pool or submit_queue or retry_queue:
        time.sleep(POLL_INTERVAL)
        
        now = time.time()
        
        # Check status of all tasks in pool
        for task_id in list(pool.keys()):
            info = pool[task_id]
            try:
                status = ee.data.getTaskStatus(task_id)[0]
                state = status['state']
            except Exception:
                continue  # GEE API hiccup, try next cycle
            
            if state == 'COMPLETED':
                all_completed += 1
                bidx = info['batch_idx']
                del pool[task_id]
                
                # Update checkpoint
                cp_file = CHECKPOINT_DIR / f"phase_c_batch_{bidx:05d}.json"
                try:
                    with open(cp_file) as f:
                        cp = json.load(f)
                    cp['status'] = 'completed'
                    with open(cp_file, 'w') as f:
                        json.dump(cp, f)
                except Exception:
                    pass
                    
            elif state in ('FAILED', 'CANCEL_REQUESTED', 'CANCELLED'):
                error = status.get('error_message', state)
                bidx = info['batch_idx']
                bdf = info['batch_df']
                attempt = info['attempt']
                del pool[task_id]
                
                if attempt < max_retries:
                    # Re-queue for retry
                    retry_queue.append((bidx, bdf, attempt + 1))
                    print(f"  FAILED batch {bidx} (attempt {attempt}): {error[:80]} → retry queued")
                else:
                    all_failed_permanent.append((bidx, error))
                    print(f"  FAILED batch {bidx} (attempt {attempt}/{max_retries}): {error[:80]} → permanent")
                    
                    # Update checkpoint
                    cp_file = CHECKPOINT_DIR / f"phase_c_batch_{bidx:05d}.json"
                    try:
                        with open(cp_file) as f:
                            cp = json.load(f)
                        cp['status'] = 'failed'
                        cp['error'] = error[:200]
                        with open(cp_file, 'w') as f:
                            json.dump(cp, f)
                    except Exception:
                        pass
            
            elif state in ('RUNNING', 'READY'):
                # Check for individual task timeout
                task_elapsed = now - info['submit_time']
                if task_elapsed > TASK_TIMEOUT:
                    bidx = info['batch_idx']
                    bdf = info['batch_df']
                    attempt = info['attempt']
                    try:
                        ee.data.cancelTask(task_id)
                    except Exception:
                        pass
                    del pool[task_id]
                    
                    if attempt < max_retries:
                        retry_queue.append((bidx, bdf, attempt + 1))
                        print(f"  TIMEOUT batch {bidx} ({task_elapsed/60:.0f} min) → retry queued")
                    else:
                        all_failed_permanent.append((bidx, f"Timeout after {TASK_TIMEOUT//60} min"))
                        print(f"  TIMEOUT batch {bidx} → permanent failure")
        
        # Refill pool after processing completions/failures
        _fill_pool()
        
        # Progress report every 60 seconds
        elapsed = now - global_start_time
        if elapsed - last_progress_time >= 60:
            last_progress_time = elapsed
            total_done = all_completed + len(all_failed_permanent)
            remaining = len(submit_queue) + len(retry_queue) + len(pool)
            
            if all_completed > 0:
                rate = all_completed / (elapsed / 3600)  # tasks/hour
                eta_hours = remaining / rate if rate > 0 else 0
                pixels_done = all_completed * batch_size
                print(f"  [{total_done}/{actual_batches}] "
                      f"{all_completed} ok, {len(all_failed_permanent)} fail, "
                      f"{len(pool)} active, {len(retry_queue)} retry, "
                      f"{len(submit_queue)} queued | "
                      f"~{pixels_done:,} pixels | "
                      f"{elapsed/60:.0f}min elapsed, ~{eta_hours:.1f}hr left")
    
    # Final summary
    elapsed = time.time() - global_start_time
    print(f"\n{'=' * 60}")
    print(f"SAMPLING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total completed: {all_completed}")
    print(f"  Total failed (permanent): {len(all_failed_permanent)}")
    print(f"  Total time: {elapsed / 60:.1f} min ({elapsed / 3600:.1f} hours)")
    print(f"  Success rate: {all_completed / max(all_completed + len(all_failed_permanent), 1) * 100:.1f}%")
    print(f"  Pixels exported: ~{all_completed * batch_size:,}")
    
    if all_failed_permanent:
        print(f"\n  Permanently failed batches ({len(all_failed_permanent)}):")
        for bidx, err in all_failed_permanent[:20]:
            print(f"    Batch {bidx}: {err[:80]}")
        if len(all_failed_permanent) > 20:
            print(f"    ... and {len(all_failed_permanent) - 20} more")
    
    # Save manifest
    task_file = OUTPUT_DIR / f"phase_c_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(task_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'n_pixels': n_total,
            'n_tasks_submitted': len(all_task_ids),
            'n_completed': all_completed,
            'n_failed_permanent': len(all_failed_permanent),
            'batch_range': [start, end],
            'pool_size': pool_size,
            'max_retries': max_retries,
            'total_time_seconds': elapsed,
            'failed_batches': [(bidx, err) for bidx, err in all_failed_permanent],
            'bq_table': f'{PROJECT}.{BQ_DATASET}.{BQ_TABLE}',
            'target_year': TARGET_YEAR,
        }, f, indent=2)
    print(f"  Manifest: {task_file}")
    
    return all_task_ids


# =============================================================================
# POST-PROCESSING: REJOIN TO SPECIES
# =============================================================================

def rejoin_to_species(bq_export_path: Optional[str] = None):
    """After BQ export, rejoin pixel embeddings back to all species observed at each pixel.
    
    This maps pixel-level data (one row per location) to species-level data
    (one row per species × location), matching the v4 parquet schema.
    
    Run this AFTER all GEE tasks complete and BQ data is exported to parquet.
    
    Args:
        bq_export_path: Path to exported Phase C parquet from BigQuery
    """
    import pyarrow.parquet as pq
    
    if bq_export_path is None:
        print("Usage: regime2_sampler.py --rejoin <path_to_phase_c_parquet>")
        return
    
    print(f"\n{'=' * 60}")
    print("REJOINING PIXEL DATA TO SPECIES")
    print(f"{'=' * 60}")
    
    # Load Phase C pixel data (from BQ export)
    print(f"\n  Loading Phase C pixels: {bq_export_path}")
    phase_c = pd.read_parquet(bq_export_path)
    print(f"  Rows (pixels): {len(phase_c):,}")
    
    # Create integer pixel keys
    phase_c['lat4'] = (phase_c['latitude'] * 10000).round().astype(np.int64)
    phase_c['lon4'] = (phase_c['longitude'] * 10000).round().astype(np.int64)
    
    # Load occurrence data to get species → pixel mapping
    print(f"\n  Loading occurrence parquet for species mapping...")
    occ = pq.read_table(
        OCC_PARQUET,
        columns=['taxon_id', 'decimalLatitude', 'decimalLongitude', 'year']
    ).to_pandas()
    occ = occ.dropna(subset=['taxon_id'])
    
    # Filter to pre-2017 + unknown year (same as sampling population)
    mask = (occ['year'].isna()) | ((occ['year'] > 0) & (occ['year'] < 2017))
    occ = occ[mask].copy()
    
    occ['lat4'] = (occ['decimalLatitude'] * 10000).round().astype(np.int64)
    occ['lon4'] = (occ['decimalLongitude'] * 10000).round().astype(np.int64)
    
    # Deduplicate: one row per species × pixel
    species_pixels = occ[['taxon_id', 'lat4', 'lon4']].drop_duplicates()
    print(f"  Unique species × pixel combinations: {len(species_pixels):,}")
    
    # Join: species_pixels × phase_c_data
    print(f"\n  Joining species to pixel data...")
    rejoined = species_pixels.merge(phase_c, on=['lat4', 'lon4'], how='inner')
    print(f"  Rejoined rows: {len(rejoined):,}")
    print(f"  Species recovered: {rejoined['taxon_id'].nunique():,}")
    
    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"phase_c_rejoined_{timestamp}.parquet"
    rejoined.to_parquet(output_path, index=False, compression='snappy')
    print(f"\n  Saved: {output_path}")
    print(f"  Size: {output_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Stats
    pts_per_species = rejoined.groupby('taxon_id').size()
    print(f"\n  Points per species:")
    print(f"    Mean: {pts_per_species.mean():.1f}")
    print(f"    Median: {pts_per_species.median():.0f}")
    print(f"    Min: {pts_per_species.min()}")
    print(f"    Max: {pts_per_species.max():,}")
    for t in [1, 3, 5, 10, 50, 100]:
        n = (pts_per_species >= t).sum()
        print(f"    >= {t}: {n:,} species")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Phase C: Regime 2 Sampler — AlphaEarth 2017 + Full Env Stack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show scope without submitting
    python3 regime2_sampler.py --dry-run

    # Test with 100 pixels
    python3 regime2_sampler.py --test 100

    # Submit all tasks and monitor
    python3 regime2_sampler.py --all

    # Submit and don't wait
    python3 regime2_sampler.py --all --no-wait

    # Resume from checkpoints
    python3 regime2_sampler.py --all --resume

    # Submit specific batch range (for parallel runs)
    python3 regime2_sampler.py --all --batch-start 0 --batch-end 500

    # After BQ export, rejoin to species
    python3 regime2_sampler.py --rejoin path/to/phase_c_export.parquet
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show scope and cost without submitting tasks')
    parser.add_argument('--test', type=int, metavar='N',
                        help='Test with N pixels')
    parser.add_argument('--all', action='store_true',
                        help='Process all remaining pixels')
    parser.add_argument('--resume', action='store_true',
                        help='Skip pixels already submitted (from checkpoints)')
    parser.add_argument('--resume-from-bq', action='store_true',
                        help='Skip pixels already in BigQuery (definitive, queries BQ)')
    parser.add_argument('--no-wait', action='store_true',
                        help='Submit all tasks without monitoring (NOT recommended, use --wave-size)')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'Points per GEE task (default: {BATCH_SIZE})')
    parser.add_argument('--pool-size', type=int, default=25,
                        help='Max concurrent GEE tasks in rolling pool (default: 25)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Max retry attempts for BQ stream failures (default: 3)')
    parser.add_argument('--batch-start', type=int, metavar='N',
                        help='Start batch index (for parallel runs)')
    parser.add_argument('--batch-end', type=int, metavar='N',
                        help='End batch index (for parallel runs)')
    parser.add_argument('--rejoin', type=str, metavar='PATH',
                        help='Post-processing: rejoin BQ export parquet to species')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("PHASE C: REGIME 2 SAMPLER")
    print("AlphaEarth 2017 + Full Environmental Stack (~129 bands)")
    print("=" * 70)
    
    # Rejoin mode
    if args.rejoin:
        rejoin_to_species(args.rejoin)
        return
    
    # Check that at least one action is specified
    if not (args.dry_run or args.test or args.all):
        parser.print_help()
        print("\nSpecify --dry-run, --test N, or --all")
        return
    
    # Initialize GEE (not needed for dry-run pixel loading, but needed for image stack)
    if not args.dry_run:
        if not initialize_gee():
            return
    
    # Load and prepare pixels
    pixels = load_and_prepare_pixels(
        resume=args.resume,
        resume_from_bq=args.resume_from_bq
    )
    
    if len(pixels) == 0:
        print("\nNo pixels to process!")
        return
    
    # Test mode
    if args.test:
        print(f"\n  [TEST MODE: {args.test} pixels]")
        pixels = pixels.sample(n=min(args.test, len(pixels)), random_state=42)
    
    # Initialize GEE for dry run (needed for band count)
    if args.dry_run:
        if not initialize_gee():
            print("\n  [GEE not available — skipping band count]")
            return
    
    # Run sampling
    task_ids = run_sampling(
        pixels,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        no_wait=args.no_wait,
        batch_start=args.batch_start,
        batch_end=args.batch_end,
        pool_size=args.pool_size,
        max_retries=args.max_retries,
    )
    
    if task_ids:
        print(f"\n{'=' * 60}")
        print("NEXT STEPS")
        print(f"{'=' * 60}")
        print(f"  1. Monitor: https://code.earthengine.google.com/tasks")
        print(f"  2. Export from BQ: bq extract --destination_format=PARQUET "
              f"{PROJECT}:{BQ_DATASET}.{BQ_TABLE} gs://bucket/phase_c_*.parquet")
        print(f"  3. Download parquet and run:")
        print(f"     python3 regime2_sampler.py --rejoin <path_to_parquet>")
        print(f"  4. Load to k-NN table:")
        print(f"     python3 load_knn_embeddings.py  (update to include Phase C)")


if __name__ == '__main__':
    main()
