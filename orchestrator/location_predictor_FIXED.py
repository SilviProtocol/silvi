"""
AlphaEarth Location-to-Species Prediction Service - FIXED VERSION v4
Uses the correct sampling method that actually retrieves AlphaEarth data.
Includes SRTM elevation, multi-year fallback, WorldClim BIO, OpenLandMap soil,
3x3 embedding homogeneity grid, Google CCDC change detection, and ETH canopy height.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import time
import random
import numpy as np

# Configuration
PROJECT = 'treekipedia-479918'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
SRTM_ASSET = 'USGS/SRTMGL1_003'
HANSEN_ASSET = 'UMD/hansen/global_forest_change_2023_v1_11'
WORLDCLIM_BIO_ASSET = 'WORLDCLIM/V1/BIO'

# OpenLandMap soil assets (static, 250m resolution)
OPENLANDMAP_SOIL = {
    'ph': 'OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02',      # pH in H2O
    'clay': 'OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02',  # Clay %
    'sand': 'OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02',  # Sand %
    'organic_carbon': 'OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02',  # SOC g/kg
}

# Plantation / forest type datasets (v2.1)
XIAO_ASSET = 'projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS'     # 30m, ImageCollection (1010 tiles)
NEUMANN_ASSET = 'projects/nature-trace/assets/forest_typology/natural_forest_2020_v1_0_collection'  # 10m, ImageCollection (37166 tiles)
JRC_FOREST_ASSET = 'JRC/GFC2020_subtypes/V1'  # 10m, single Image

# Years to try for AlphaEarth (most recent first)
ALPHAEARTH_YEARS = [2023, 2022, 2021, 2020, 2019, 2018, 2017]

app = Flask(__name__)
CORS(app)

# Initialize Earth Engine
try:
    ee.Initialize(project=PROJECT)
    print(f"Earth Engine initialized (project: {PROJECT})")
except Exception as e:
    print(f"Earth Engine initialization failed: {e}")
    raise


def sample_srtm_elevation(lat: float, lon: float) -> dict:
    """Sample SRTM 30m elevation at a point."""
    try:
        point = ee.Geometry.Point([lon, lat])
        srtm = ee.Image(SRTM_ASSET)
        sample = srtm.sample(region=point, scale=30, numPixels=1)
        first = sample.first().getInfo()
        if first and 'properties' in first and 'elevation' in first['properties']:
            return {'elevation': float(first['properties']['elevation'])}
    except Exception as e:
        print(f"   SRTM elevation failed: {e}")
    return {}


def sample_hansen_forest(lat: float, lon: float) -> dict:
    """Sample Hansen Global Forest Change data at a point."""
    try:
        point = ee.Geometry.Point([lon, lat])
        hansen = ee.Image(HANSEN_ASSET)
        sample = hansen.select(['treecover2000', 'lossyear', 'loss', 'gain']).sample(
            region=point, scale=30, numPixels=1
        )
        first = sample.first().getInfo()
        if first and 'properties' in first:
            props = first['properties']
            return {
                'treecover2000': float(props.get('treecover2000', 0)),
                'lossyear': int(props.get('lossyear', 0)),
                'loss': bool(props.get('loss', 0)),
                'gain': bool(props.get('gain', 0))
            }
    except Exception as e:
        print(f"   Hansen forest data failed: {e}")
    return {}


def sample_worldclim_bio(lat: float, lon: float) -> dict:
    """
    Sample WorldClim V1 BIO variables at a point.
    Returns 19 bioclimatic variables. Key ones:
      bio01: Annual Mean Temperature (°C × 10)
      bio05: Max Temp of Warmest Month (°C × 10)
      bio06: Min Temp of Coldest Month (°C × 10)
      bio12: Annual Precipitation (mm)
      bio13: Precipitation of Wettest Month (mm)
      bio14: Precipitation of Driest Month (mm)
      bio15: Precipitation Seasonality (CV)
    WorldClim stores temperature as °C × 10 (integers), we convert to actual °C.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        bio = ee.Image(WORLDCLIM_BIO_ASSET)
        # Select the key bands we need
        bands = [f'bio{i:02d}' for i in range(1, 20)]  # bio01 through bio19
        sample = bio.select(bands).sample(
            region=point, scale=1000, numPixels=1
        )
        first = sample.first().getInfo()
        if first and 'properties' in first:
            props = first['properties']
            result = {}
            for band in bands:
                val = props.get(band)
                if val is not None:
                    # Temperature variables (bio01-bio11) are stored as °C × 10
                    band_num = int(band[3:])
                    if band_num <= 11:
                        result[band] = float(val) / 10.0  # Convert to actual °C
                    else:
                        result[band] = float(val)  # Precipitation vars in mm already
            if result:
                print(f"   WorldClim: {len(result)} BIO vars sampled (temp={result.get('bio01', 'N/A')}°C, precip={result.get('bio12', 'N/A')}mm)")
                return result
    except Exception as e:
        print(f"   WorldClim BIO sampling failed: {e}")
    return {}


def sample_openlandmap_soil(lat: float, lon: float) -> dict:
    """
    Sample OpenLandMap soil properties at a point.
    Returns soil pH, clay%, sand%, and organic carbon at surface (0cm depth).
    
    Depth bands: b0 (0cm), b10 (10cm), b30 (30cm), b60 (60cm), b100 (100cm), b200 (200cm)
    We sample b0 (surface) for matching against species preferences.
    
    pH is stored as pH × 10 (integer), we convert to actual pH.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        result = {}
        
        # Sample pH (surface layer = b0)
        try:
            ph_img = ee.Image(OPENLANDMAP_SOIL['ph'])
            ph_sample = ph_img.select('b0').sample(region=point, scale=250, numPixels=1)
            ph_first = ph_sample.first().getInfo()
            if ph_first and 'properties' in ph_first and 'b0' in ph_first['properties']:
                raw_ph = float(ph_first['properties']['b0'])
                result['soil_ph'] = round(raw_ph / 10.0, 1)  # pH × 10 → actual pH
        except Exception as e:
            print(f"   Soil pH sampling failed: {e}")
        
        # Sample clay content (surface layer = b0)
        try:
            clay_img = ee.Image(OPENLANDMAP_SOIL['clay'])
            clay_sample = clay_img.select('b0').sample(region=point, scale=250, numPixels=1)
            clay_first = clay_sample.first().getInfo()
            if clay_first and 'properties' in clay_first and 'b0' in clay_first['properties']:
                result['soil_clay_pct'] = float(clay_first['properties']['b0'])
        except Exception as e:
            print(f"   Soil clay sampling failed: {e}")
        
        # Sample sand content (surface layer = b0)
        try:
            sand_img = ee.Image(OPENLANDMAP_SOIL['sand'])
            sand_sample = sand_img.select('b0').sample(region=point, scale=250, numPixels=1)
            sand_first = sand_sample.first().getInfo()
            if sand_first and 'properties' in sand_first and 'b0' in sand_first['properties']:
                result['soil_sand_pct'] = float(sand_first['properties']['b0'])
        except Exception as e:
            print(f"   Soil sand sampling failed: {e}")
        
        # Sample organic carbon (surface layer = b0)
        try:
            soc_img = ee.Image(OPENLANDMAP_SOIL['organic_carbon'])
            soc_sample = soc_img.select('b0').sample(region=point, scale=250, numPixels=1)
            soc_first = soc_sample.first().getInfo()
            if soc_first and 'properties' in soc_first and 'b0' in soc_first['properties']:
                result['soil_organic_carbon_g_kg'] = float(soc_first['properties']['b0'])
        except Exception as e:
            print(f"   Soil organic carbon sampling failed: {e}")
        
        # Derive soil texture category from clay/sand percentages
        if 'soil_clay_pct' in result and 'soil_sand_pct' in result:
            result['soil_texture'] = classify_soil_texture(
                result['soil_clay_pct'], result['soil_sand_pct']
            )
        
        # Derive pH category for species matching
        if 'soil_ph' in result:
            result['soil_ph_category'] = classify_ph(result['soil_ph'])
        
        if result:
            print(f"   Soil: pH={result.get('soil_ph', 'N/A')}"
                  f" ({result.get('soil_ph_category', 'N/A')})"
                  f", clay={result.get('soil_clay_pct', 'N/A')}%"
                  f", texture={result.get('soil_texture', 'N/A')}")
            return result
    except Exception as e:
        print(f"   OpenLandMap soil sampling failed: {e}")
    return {}


def sample_embedding_homogeneity(lat: float, lon: float, year: int = 2023) -> dict:
    """
    Sample a 3x3 grid of AlphaEarth embeddings at ~100m spacing around the target pixel.
    Compute mean pairwise cosine similarity as a monoculture/homogeneity signal.
    
    High homogeneity (>0.90) suggests monoculture plantation or uniform habitat.
    Low homogeneity (<0.85) suggests mixed species / natural forest.
    
    This is a single batched GEE call: samples 9 points from one image, returning
    9 × 64 values in one getInfo() round-trip (~3s additional latency).
    """
    try:
        # 100m offset ≈ 0.0009° at mid-latitudes (more precise at equator)
        # Using geographic degrees — close enough for 100m at most latitudes
        offset = 0.0009  # ~100m

        # Build 3x3 grid as a MultiPoint geometry (9 points, single GEE call)
        coords = [[lon + dx * offset, lat + dy * offset]
                   for dy in [-1, 0, 1] for dx in [-1, 0, 1]]
        grid = ee.Geometry.MultiPoint(coords)

        col = ee.ImageCollection(AE_COLLECTION).filterDate(f'{year}-01-01', f'{year}-12-31')
        ae_image = col.mosaic()

        # Sample all 9 points in one call
        sample_fc = ae_image.sample(region=grid, scale=10, geometries=True)
        features = sample_fc.getInfo()

        if not features or 'features' not in features:
            return {}

        # Extract embedding vectors
        embeddings = []
        for feat in features['features']:
            props = feat.get('properties', {})
            vec = []
            for i in range(64):
                val = props.get(f'A{i:02d}')
                if val is None:
                    break
                vec.append(float(val))
            if len(vec) == 64:
                embeddings.append(vec)

        if len(embeddings) < 4:
            # Need at least 4 valid points for meaningful homogeneity
            print(f"   Homogeneity: only {len(embeddings)}/9 valid points, skipping")
            return {}

        # Compute mean pairwise cosine similarity
        emb_array = np.array(embeddings)
        # Normalize rows to unit vectors
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        unit = emb_array / norms

        # Pairwise cosine = dot product of unit vectors
        sim_matrix = unit @ unit.T
        n = len(embeddings)
        # Extract upper triangle (excluding diagonal)
        total_sim = 0.0
        pair_count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total_sim += sim_matrix[i][j]
                pair_count += 1

        mean_homogeneity = total_sim / pair_count if pair_count > 0 else 0.0

        print(f"   Homogeneity: {mean_homogeneity:.4f} from {n} valid points ({pair_count} pairs)")
        return {
            'embedding_homogeneity': round(float(mean_homogeneity), 4),
            'homogeneity_points': n,
            'homogeneity_pairs': pair_count
        }

    except Exception as e:
        print(f"   Embedding homogeneity sampling failed: {e}")
        return {}


def sample_ccdc(lat: float, lon: float) -> dict:
    """
    Sample Google Continuous Change Detection and Classification (CCDC) data.
    Dataset: GOOGLE/GLOBAL_CCDC/V1 (Landsat-based, 30m, global, 1999-2019)
    
    Returns:
      ccdc_num_breaks: Number of detected breakpoints (land cover changes) since 1999
      ccdc_last_break: Fractional year of most recent breakpoint (e.g., 2015.5)
    
    Breakpoints indicate disturbance events (logging, fire, clearing, planting).
    A pixel with recent breakpoints + high current treecover suggests active
    management (plantation establishment or replanting).
    """
    try:
        point = ee.Geometry.Point([lon, lat])

        # CCDC V1 stores results as arrays of segments per pixel.
        # Each segment has tStart, tEnd, tBreak, numObs, changeProb, etc.
        # We need the tBreak values to count breakpoints and find the latest.
        ccdc = ee.ImageCollection('GOOGLE/GLOBAL_CCDC/V1') \
            .filterBounds(point) \
            .mosaic()

        # The CCDC dataset stores time series segments. Each pixel has arrays of
        # segment properties. We extract tBreak (breakpoint time in fractional years).
        # Get number of breaks and latest break time.
        
        # Select the tBreak band which contains breakpoint times
        t_break = ccdc.select('tBreak')
        
        # Sample at the point
        sample = t_break.sample(region=point, scale=30, numPixels=1)
        first = sample.first().getInfo()

        result = {
            'ccdc_num_breaks': 0,
            'ccdc_last_break': None
        }

        if first and 'properties' in first:
            props = first['properties']
            # tBreak can be a single value or an array depending on the number of segments
            t_break_val = props.get('tBreak')
            
            if t_break_val is not None:
                # Could be a list (multiple segments) or single value
                if isinstance(t_break_val, list):
                    # Filter out 0 or null values (no break)
                    breaks = [b for b in t_break_val if b and b > 0]
                    result['ccdc_num_breaks'] = len(breaks)
                    if breaks:
                        result['ccdc_last_break'] = round(max(breaks), 2)
                elif t_break_val > 0:
                    result['ccdc_num_breaks'] = 1
                    result['ccdc_last_break'] = round(float(t_break_val), 2)

        print(f"   CCDC: {result['ccdc_num_breaks']} breaks, last={result.get('ccdc_last_break', 'none')}")
        return result

    except Exception as e:
        error_str = str(e)
        # CCDC may not cover all areas
        if 'no features' in error_str.lower() or 'Collection.first' in error_str:
            print(f"   CCDC: no coverage at this location")
        else:
            print(f"   CCDC sampling failed: {e}")
        return {'ccdc_num_breaks': 0, 'ccdc_last_break': None}


def sample_canopy_height_variance(lat: float, lon: float) -> dict:
    """
    Sample canopy height mean and standard deviation in a 100m radius.
    Uses ETH Global Canopy Height 2020 (10m resolution) with stddev band.
    
    Low stddev + high mean height = uniform tall canopy (monoculture signal).
    High stddev = variable heights (mixed age/species, natural forest).
    
    This signal is useful for confirming managed forest ONLY when temporal
    context confirms no recent disturbance (i.e., the height is stable).
    For older occurrences (pre-2020), this height represents current state,
    which should only be used if Hansen/CCDC confirm no disturbance since
    the occurrence year.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        # 100m radius buffer
        buffer = point.buffer(100)

        # ETH Global Canopy Height 2020 (10m resolution)
        # Asset path via community catalog
        canopy = ee.Image('users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1')
        canopy_sd = ee.Image('users/nlang/ETH_GlobalCanopyHeightSD_2020_10m_v1')

        # Reduce within 100m buffer: mean and stddev of height
        stats = canopy.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=buffer,
            scale=10,
            maxPixels=1000
        ).getInfo()

        # Also get the stddev layer's mean (model uncertainty)
        sd_stats = canopy_sd.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=10,
            maxPixels=1000
        ).getInfo()

        result = {}
        if stats:
            # Band name is 'b1' in the ETH dataset
            mean_height = stats.get('b1_mean')
            height_stddev = stats.get('b1_stdDev')
            if mean_height is not None:
                result['canopy_height_mean_m'] = round(float(mean_height), 1)
            if height_stddev is not None:
                result['canopy_height_stddev_100m'] = round(float(height_stddev), 2)

        if sd_stats:
            model_sd = sd_stats.get('b1_mean')
            if model_sd is not None:
                result['canopy_height_model_uncertainty'] = round(float(model_sd), 2)

        if result:
            print(f"   Canopy height: mean={result.get('canopy_height_mean_m', 'N/A')}m, "
                  f"stddev={result.get('canopy_height_stddev_100m', 'N/A')}m")
        else:
            print(f"   Canopy height: no coverage at this location")
        return result

    except Exception as e:
        error_str = str(e)
        if 'no features' in error_str.lower() or 'not found' in error_str.lower():
            print(f"   Canopy height: no coverage at this location")
        else:
            print(f"   Canopy height sampling failed: {e}")
        return {}


def sample_sinr_env_features(lat: float, lon: float, year: int = 2023) -> dict:
    """Sample ALL environmental features needed for SINR model inference in one GEE call.

    This builds a multi-band image stack covering the 32 features that were previously
    missing at inference time, plus the 3 plantation features (xiao, neumann, jrc).
    One API call samples everything at once for efficiency.

    Returns dict with keys matching training column names.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        is_arctic = lat > 59.0

        bands = []

        # ── Terrain (slope, aspect, hillshade) ───────────────────────────
        if is_arctic:
            dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic()
        else:
            dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
        terrain = ee.Terrain.products(dem)
        bands.append(terrain.select('slope').rename('slope').toFloat())
        bands.append(terrain.select('aspect').rename('aspect').toFloat())
        bands.append(terrain.select('hillshade').rename('hillshade').toFloat())

        # ── Soil (texture class, bulk density, water content) ────────────
        bands.append(
            ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')
            .select('b0').rename('soil_texture_class').unmask(0).toFloat()
        )
        bands.append(
            ee.Image('OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02')
            .select('b0').rename('soil_bulk_density').unmask(0).toFloat()
        )
        bands.append(
            ee.Image('OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01')
            .select('b0').rename('soil_water_content').unmask(0).toFloat()
        )

        # ── JRC Tropical Moist Forest ────────────────────────────────────
        bands.append(
            ee.ImageCollection('projects/JRC/TMF/v1_2024/TransitionMap_Subtypes')
            .mosaic().select('TransitionMap_Subtypes')
            .unmask(0).rename('jrc_tmf_status').toFloat()
        )
        bands.append(
            ee.ImageCollection('projects/JRC/TMF/v1_2024/DegradationYear')
            .mosaic().select('constant')
            .unmask(0).rename('jrc_tmf_degrad_year').toFloat()
        )

        # ── ESA WorldCover 2021 ──────────────────────────────────────────
        bands.append(
            ee.ImageCollection('ESA/WorldCover/v200').mosaic()
            .select('Map').unmask(0).rename('esa_worldcover_2021').toFloat()
        )

        # ── Dynamic World (year-matched) ─────────────────────────────────
        if year >= 2015:
            dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
                  .filterDate(f'{year}-01-01', f'{year + 1}-01-01')
                  .select('label').mode().unmask(0).rename('dynamic_world').toFloat())
        else:
            # Pre-2015 fallback: remap ESA WorldCover to DW classes
            dw = (ee.ImageCollection('ESA/WorldCover/v200').mosaic()
                  .select('Map')
                  .remap([10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
                         [1, 5, 2, 4, 6, 7, 8, 0, 3, 1, 7])
                  .unmask(0).rename('dynamic_world').toFloat())
        bands.append(dw)

        # ── SBTN Natural Lands ───────────────────────────────────────────
        bands.append(
            ee.Image('WRI/SBTN/naturalLands/v1_1/2020')
            .select('natural').unmask(0).rename('sbtn_natural_land').toFloat()
        )

        # ── JRC Global Surface Water ─────────────────────────────────────
        gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
        bands.append(gsw.select('occurrence').unmask(0).rename('water_occurrence').toFloat())
        bands.append(gsw.select('recurrence').unmask(0).rename('water_recurrence').toFloat())
        bands.append(gsw.select('seasonality').unmask(0).rename('water_seasonality').toFloat())

        # ── MERIT Hydro ──────────────────────────────────────────────────
        merit = ee.Image('MERIT/Hydro/v1_0_1')
        bands.append(merit.select('hnd').unmask(0).rename('merit_hand_m').toFloat())
        bands.append(merit.select('upa').unmask(0).rename('merit_upstream_area_km2').toFloat())

        # ── GEDI Canopy Height ───────────────────────────────────────────
        if is_arctic or lat > 51.6:
            bands.append(ee.Image.constant(0).rename('gedi_canopy_height_m').toFloat())
            bands.append(ee.Image.constant(0).rename('gedi_foliage_height_div').toFloat())
        else:
            gedi_rh98 = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
            gedi_fhd = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316')
            bands.append(gedi_rh98.select('p95').unmask(0).rename('gedi_canopy_height_m').toFloat())
            bands.append(gedi_fhd.select('shan').unmask(0).rename('gedi_foliage_height_div').toFloat())

        # ── MODIS GPP (year-matched) ─────────────────────────────────────
        gpp_year = max(2000, min(year, 2023))
        gpp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
               .filterDate(f'{gpp_year}-01-01', f'{gpp_year + 1}-01-01')
               .select('Gpp'))
        if gpp_year < 2000:
            bands.append(ee.Image.constant(0).rename('modis_gpp_mean').toFloat())
        else:
            # Mean GPP, masking fill values (>=65530) before unmask
            gpp_img = gpp.mean()
            bands.append(
                gpp_img.updateMask(gpp_img.lt(65530)).unmask(0).rename('modis_gpp_mean').toFloat()
            )

        # ── Biomass AGB ──────────────────────────────────────────────────
        bands.append(
            ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1')
            .mosaic().select('agb').unmask(0).rename('biomass_agb_mgha').toFloat()
        )

        # ── Human Modification ───────────────────────────────────────────
        bands.append(
            ee.ImageCollection('CSP/HM/GlobalHumanModification')
            .mosaic().select('gHM').unmask(0).rename('human_modification').toFloat()
        )

        # ── VIIRS Nighttime Lights (year-matched) ────────────────────────
        if year >= 2012:
            ntl = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
                   .filterDate(f'{year}-01-01', f'{year + 1}-01-01')
                   .select('avg_rad').mean().unmask(0).rename('nighttime_lights').toFloat())
        else:
            ntl = ee.Image.constant(0).rename('nighttime_lights').toFloat()
        bands.append(ntl)

        # ── MODIS Fire Frequency (cumulative to year) ────────────────────
        if year >= 2001:
            fire = (ee.ImageCollection('MODIS/061/MCD64A1')
                    .filterDate('2001-01-01', f'{min(year + 1, 2024)}-01-01')
                    .select('BurnDate')
                    .reduce(ee.Reducer.count())
                    .rename('fire_frequency_count').unmask(0).toFloat())
        else:
            fire = ee.Image.constant(0).rename('fire_frequency_count').toFloat()
        bands.append(fire)

        # ── RESOLVE Ecoregions (eco_id, biome_num) ───────────────────────
        ecoregions = ee.FeatureCollection('RESOLVE/ECOREGIONS/2017')
        bands.append(
            ecoregions.reduceToImage(properties=['ECO_ID'], reducer=ee.Reducer.first())
            .unmask(0).rename('eco_id').toFloat()
        )
        bands.append(
            ecoregions.reduceToImage(properties=['BIOME_NUM'], reducer=ee.Reducer.first())
            .unmask(0).rename('biome_num').toFloat()
        )

        # ── Topographic Diversity ────────────────────────────────────────
        if is_arctic:
            bands.append(ee.Image.constant(0).rename('topo_diversity').toFloat())
        else:
            bands.append(
                ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity')
                .select('constant').unmask(0).rename('topo_diversity').toFloat()
            )

        # ── TerraClimate (year-matched, +/-2yr window) ──────────────────
        tc_year = max(1958, min(year, 2024))
        tc_start = max(1958, tc_year - 2)
        tc_end = min(2025, tc_year + 3)
        tc = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
              .filterDate(f'{tc_start}-01-01', f'{tc_end}-01-01')
              .select(['vpd', 'aet', 'soil', 'pdsi', 'def', 'srad'])
              .mean())
        bands.append(tc.select('vpd').rename('tc_vpd_mean').unmask(0).toFloat())
        bands.append(tc.select('aet').rename('tc_aet_mean').unmask(0).toFloat())
        bands.append(tc.select('soil').rename('tc_soil_moisture_mean').unmask(0).toFloat())
        bands.append(tc.select('pdsi').rename('tc_pdsi_mean').unmask(0).toFloat())
        bands.append(tc.select('def').rename('tc_water_deficit_mean').unmask(0).toFloat())
        bands.append(tc.select('srad').rename('tc_solar_rad_mean').unmask(0).toFloat())

        # ── Xiao Planted Forest ──────────────────────────────────────────
        # Keep decode aligned with training extractor (unified_gee_sampler_v3.get_static_env_image)
        # to avoid train/serve categorical drift.
        xiao_mosaic = ee.ImageCollection(XIAO_ASSET).mosaic()
        xb1 = xiao_mosaic.select('b1')
        xb2 = xiao_mosaic.select('b2')
        xb3 = xiao_mosaic.select('b3')
        is_planted = xb1.eq(127).And(xb2.eq(127)).And(xb3.eq(0))   # Yellow (127,127,0)
        is_natural = xb1.eq(0).And(xb2.eq(127)).And(xb3.eq(0))     # Green (0,127,0)
        xiao_class = (is_planted.multiply(2).add(is_natural)
                      .rename('xiao_planted_forest').toFloat())
        bands.append(xiao_class)

        # ── Neumann Natural Prob ─────────────────────────────────────────
        bands.append(
            ee.ImageCollection(NEUMANN_ASSET).mosaic()
            .select('B0').unmask(0).rename('neumann_natural_prob').toFloat()
        )

        # ── JRC Forest Type ──────────────────────────────────────────────
        bands.append(
            ee.Image(JRC_FOREST_ASSET).select('Map')
            .unmask(0).rename('jrc_forest_type').toFloat()
        )

        # ── Global Aridity Index + ET0 (Trabucco & Zomer 2022, ~1km) ───
        ai_img = ee.Image('projects/sat-io/open-datasets/global_ai/global_ai_yearly')
        bands.append(ai_img.select('b1').divide(10000).rename('aridity_index').unmask(0).toFloat())
        et0_img = ee.Image('projects/sat-io/open-datasets/global_et0/global_et0_yearly')
        bands.append(et0_img.select('b1').divide(10).rename('et0_mm_yr').unmask(0).toFloat())

        # ── IPCC Forest Classification (30m, 2020) ─────────────────────
        ipcc = ee.ImageCollection('NASA/ORNL/global_forest_classification_2020/V1').mosaic()
        bands.append(ipcc.select('classification').rename('ipcc_forest_class').unmask(0).toFloat())

        # ── Stack all bands and sample ───────────────────────────────────
        combined = bands[0]
        for b in bands[1:]:
            combined = combined.addBands(b)

        sample = combined.sample(region=point, scale=30, numPixels=1)
        first = sample.first().getInfo()

        if first and 'properties' in first:
            props = first['properties']
            result = {}
            for key, val in props.items():
                result[key] = val if val is not None else 0
            print(f"   SINR env features: {len(result)} bands sampled")
            print(f"   eco_id={result.get('eco_id', 0)}, biome_num={result.get('biome_num', 0)}, "
                  f"xiao={result.get('xiao_planted_forest', 0)}, neumann={result.get('neumann_natural_prob', 0)}, "
                  f"jrc={result.get('jrc_forest_type', 0)}")
            return result

    except Exception as e:
        print(f"   SINR env features sampling failed: {e}")
    return {}


def sample_xiao_planted_forest(lat: float, lon: float) -> dict:
    """Sample Xiao et al. 2024 Global Natural & Planted Forests (30m).

    Decode aligned with training extractor:
    - planted: b1 > 200 and b2 < 50
    - natural: b2 > 100 and b1 < 50
    Returns xiao_planted_forest: 0=non-forest, 1=natural, 2=planted.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        xiao_mosaic = ee.ImageCollection(XIAO_ASSET).mosaic()
        b1 = xiao_mosaic.select('b1')
        b2 = xiao_mosaic.select('b2')
        is_planted = b1.gt(200).And(b2.lt(50))
        is_natural = b2.gt(100).And(b1.lt(50))

        xiao_class = is_planted.multiply(2).add(is_natural).rename('xiao_planted_forest').toInt()

        sample = xiao_class.sample(region=point, scale=30, numPixels=1)
        first = sample.first().getInfo()
        if first and 'properties' in first:
            val = int(first['properties'].get('xiao_planted_forest', 0))
            labels = {0: 'non-forest', 1: 'natural', 2: 'planted'}
            print(f"   Xiao planted forest: {val} ({labels.get(val, 'unknown')})")
            return {'xiao_planted_forest': val}
    except Exception as e:
        error_str = str(e)
        if 'no features' in error_str.lower():
            print(f"   Xiao planted forest: no coverage at this location")
        else:
            print(f"   Xiao planted forest sampling failed: {e}")
    return {}


def sample_neumann_natural_prob(lat: float, lon: float) -> dict:
    """Sample Neumann/DeepMind 2025 Natural Forests of the World (10m).

    B0 = probability of natural forest (0-255). 0 = definitely not natural,
    255 = definitely natural. Plantations typically score 0-30.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        neumann_mosaic = ee.ImageCollection(NEUMANN_ASSET).mosaic()
        neumann_prob = neumann_mosaic.select('B0').rename('neumann_natural_prob') \
            .unmask(0).toInt()

        sample = neumann_prob.sample(region=point, scale=10, numPixels=1)
        first = sample.first().getInfo()
        if first and 'properties' in first:
            val = int(first['properties'].get('neumann_natural_prob', 0))
            print(f"   Neumann natural prob: {val}/255")
            return {'neumann_natural_prob': val}
    except Exception as e:
        error_str = str(e)
        if 'no features' in error_str.lower():
            print(f"   Neumann natural prob: no coverage at this location")
        else:
            print(f"   Neumann natural prob sampling failed: {e}")
    return {}


def sample_jrc_forest_type(lat: float, lon: float) -> dict:
    """Sample JRC GFC2020 forest subtypes (10m).

    Map band values: 0=no forest, 1=naturally regenerating, 10=primary, 20=planted.
    NOTE: Known misclassification issue at some plantation sites (e.g. Wairarapa NZ).
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        jrc = ee.Image(JRC_FOREST_ASSET).select('Map').unmask(0)
        sample = jrc.sample(region=point, scale=10, numPixels=1)
        first = sample.first().getInfo()
        if first and 'properties' in first:
            val = int(first['properties'].get('Map', 0))
            labels = {0: 'no forest', 1: 'natural', 10: 'primary', 20: 'planted'}
            print(f"   JRC forest type: {val} ({labels.get(val, 'unknown')})")
            return {'jrc_forest_type': val}
    except Exception as e:
        error_str = str(e)
        if 'no features' in error_str.lower():
            print(f"   JRC forest type: no coverage at this location")
        else:
            print(f"   JRC forest type sampling failed: {e}")
    return {}


def classify_soil_texture(clay_pct: float, sand_pct: float) -> str:
    """
    Classify soil texture from clay and sand percentages using USDA texture triangle.
    Returns categories that match Treekipedia species preferences:
    'sandy', 'loamy', 'clayey', 'silty', 'sandy loam', 'clay loam', 'silt loam'
    """
    silt_pct = 100 - clay_pct - sand_pct
    
    if clay_pct >= 40:
        if sand_pct >= 45:
            return 'sandy clay'
        elif silt_pct >= 40:
            return 'silty clay'
        else:
            return 'clayey'
    elif clay_pct >= 27:
        if sand_pct >= 20 and sand_pct < 45:
            return 'clay loam'
        elif sand_pct >= 45:
            return 'sandy clay loam'
        else:
            return 'silty clay loam'
    elif clay_pct >= 7:
        if sand_pct >= 52:
            return 'sandy loam'
        elif silt_pct >= 50 and silt_pct < 80:
            return 'silt loam'
        elif silt_pct >= 80:
            return 'silty'
        else:
            return 'loamy'
    else:
        if sand_pct >= 85:
            return 'sandy'
        elif silt_pct >= 80:
            return 'silty'
        else:
            return 'loamy sand'


def classify_koppen_geiger(bio_data: dict) -> dict:
    """
    Classify Koppen-Geiger climate zone from WorldClim BIO variables.
    Uses the standard Koppen-Geiger classification scheme.
    
    Returns dict with 'code' (e.g., 'Af') and 'description' (e.g., 'Tropical rainforest')
    matching the format in the species database.
    
    BIO variables used:
      bio01: Annual Mean Temperature (°C, already converted)
      bio05: Max Temp of Warmest Month (°C)
      bio06: Min Temp of Coldest Month (°C)
      bio12: Annual Precipitation (mm)
      bio13: Precipitation of Wettest Month (mm)
      bio14: Precipitation of Driest Month (mm)
    """
    t_ann = bio_data.get('bio01')  # Annual mean temp °C
    t_hot = bio_data.get('bio05')  # Hottest month max temp °C  
    t_cold = bio_data.get('bio06')  # Coldest month min temp °C
    p_ann = bio_data.get('bio12')  # Annual precipitation mm
    p_wet = bio_data.get('bio13')  # Wettest month mm
    p_dry = bio_data.get('bio14')  # Driest month mm
    
    if any(v is None for v in [t_ann, t_hot, t_cold, p_ann, p_wet, p_dry]):
        return {}
    
    # Additional BIO vars for better classification
    p_seasonality = bio_data.get('bio15', 0)  # Precipitation seasonality (CV)
    t_warmest_q = bio_data.get('bio10', t_hot)  # Mean temp of warmest quarter
    t_coldest_q = bio_data.get('bio11', t_cold)  # Mean temp of coldest quarter
    
    # Estimate precipitation concentration for arid threshold
    # Koppen uses 3 rules depending on precipitation timing
    # With BIO vars, we approximate: if seasonality is high, use adjusted threshold
    # Conservative approach: use middle threshold for ambiguous cases
    p_threshold_arid = 20 * t_ann + 280  # Default "evenly distributed" threshold
    if p_seasonality > 60:  # High seasonality
        p_threshold_arid = 20 * t_ann + 280 + 140  # Summer-dominant bias
    
    # === GROUP A: Tropical (t_cold >= 18°C) ===
    if t_cold >= 18:
        if p_dry >= 60:
            return {'code': 'Af', 'description': 'Tropical rainforest'}
        elif p_ann >= 25 * (100 - p_dry):
            return {'code': 'Am', 'description': 'Tropical monsoon'}
        else:
            return {'code': 'Aw', 'description': 'Tropical savanna'}
    
    # === GROUP B: Arid (precipitation < threshold) ===
    if p_ann < p_threshold_arid:
        if p_ann < p_threshold_arid / 2:
            # BW - Desert
            if t_ann >= 18:
                return {'code': 'BWh', 'description': 'Hot desert'}
            else:
                return {'code': 'BWk', 'description': 'Cold desert'}
        else:
            # BS - Steppe  
            if t_ann >= 18:
                return {'code': 'BSh', 'description': 'Hot semi-arid'}
            else:
                return {'code': 'BSk', 'description': 'Cold semi-arid'}
    
    # === GROUP C: Temperate (t_hot > 10°C, t_cold > 0°C) ===
    if t_hot > 10 and t_cold > 0:
        # Dry season detection using BIO13 (wettest) vs BIO14 (driest)
        # and seasonality. The key question: is the dry period in summer or winter?
        dry_ratio = p_dry / max(p_wet, 1)  # 0 = extreme, 1 = even
        
        # Cs (dry summer): driest month in summer, wettest in winter
        # Cw (dry winter): driest month in winter, wettest in summer
        # Use temperature seasonality as proxy: if warmest quarter ≠ wettest quarter
        
        if dry_ratio < 0.33 and p_dry < 40:
            # Significant dry season exists
            # Estimate if dry season is summer or winter
            # If mean temp of warmest quarter is high and seasonality is high, likely Cs
            # For subtropical locations (t_cold > 10°C), if precip seasonality < 50, likely Cw
            if p_seasonality > 40 and t_warmest_q > 20:
                # Dry summer (Cs) - Mediterranean
                if t_hot >= 22:
                    return {'code': 'Csa', 'description': 'Mediterranean hot summer'}
                else:
                    return {'code': 'Csb', 'description': 'Mediterranean warm summer'}
            else:
                # Dry winter (Cw) - Subtropical with winter dry
                if t_hot >= 22:
                    return {'code': 'Cwa', 'description': 'Humid subtropical dry winter hot summer'}
                else:
                    return {'code': 'Cwb', 'description': 'Subtropical highland'}
        else:
            # No significant dry season (Cf)
            if t_hot >= 22:
                return {'code': 'Cfa', 'description': 'Humid subtropical'}
            else:
                return {'code': 'Cfb', 'description': 'Oceanic'}
    
    # === GROUP D: Continental (t_hot > 10°C, t_cold <= 0°C) ===
    if t_hot > 10 and t_cold <= 0:
        dry_ratio = p_dry / max(p_wet, 1)
        
        if dry_ratio < 0.1:
            # Dry winter (Dw)
            if t_hot >= 22:
                return {'code': 'Dwa', 'description': 'Humid continental dry winter hot summer'}
            elif t_cold < -38:
                return {'code': 'Dwd', 'description': 'Subarctic dry winter very cold'}
            else:
                return {'code': 'Dwb', 'description': 'Humid continental dry winter warm summer'}
        elif dry_ratio < 0.33 and p_dry < 40:
            # Dry summer (Ds)
            if t_hot >= 22:
                return {'code': 'Dsa', 'description': 'Continental dry summer hot summer'}
            else:
                return {'code': 'Dsb', 'description': 'Continental dry summer warm summer'}
        else:
            # No dry season (Df)
            if t_hot >= 22:
                return {'code': 'Dfa', 'description': 'Humid continental hot summer'}
            elif t_cold < -38:
                return {'code': 'Dfd', 'description': 'Subarctic very cold winter'}
            else:
                return {'code': 'Dfb', 'description': 'Humid continental warm summer'}
    
    # === GROUP E: Polar (t_hot < 10°C) ===
    if t_hot <= 10:
        if t_hot > 0:
            return {'code': 'ET', 'description': 'Tundra'}
        else:
            return {'code': 'EF', 'description': 'Ice cap'}
    
    return {}


def classify_ph(ph_value: float) -> str:
    """
    Classify pH into categories matching Treekipedia species preference values.
    Categories from species data: 'very strongly acidic', 'strongly acidic',
    'moderately acidic', 'slightly acidic', 'neutral', 'slightly alkaline',
    'moderately alkaline', 'strongly alkaline'
    """
    if ph_value < 4.5:
        return 'very strongly acidic'
    elif ph_value < 5.0:
        return 'strongly acidic'
    elif ph_value < 5.5:
        return 'moderately acidic'
    elif ph_value < 6.5:
        return 'slightly acidic'
    elif ph_value < 7.5:
        return 'neutral'
    elif ph_value < 8.0:
        return 'slightly alkaline'
    elif ph_value < 8.5:
        return 'moderately alkaline'
    else:
        return 'strongly alkaline'


def sample_alphaearth_properly(lat: float, lon: float, year: int = 2023) -> dict:
    """
    Properly sample AlphaEarth using the sample() method that works.
    """
    print(f"   Sampling AlphaEarth at ({lat:.4f}, {lon:.4f}) for year {year}")

    try:
        # Get AlphaEarth collection for the specified year
        col = ee.ImageCollection(AE_COLLECTION).filterDate(
            f'{year}-01-01', f'{year}-12-31'
        )
        ae_image = col.mosaic()

        # Create point geometry
        point = ee.Geometry.Point([lon, lat])

        # Use sample() method which WORKS for AlphaEarth
        sample = ae_image.sample(
            region=point,
            scale=10,
            numPixels=1
        )

        # Get the first (and only) sample
        first_sample = sample.first().getInfo()

        if first_sample and 'properties' in first_sample:
            props = first_sample['properties']

            # Extract all 64 bands
            embedding = {}
            valid_bands = 0

            for i in range(64):
                band_name = f'A{i:02d}'
                if band_name in props and props[band_name] is not None:
                    embedding[f'a{i:02d}'] = float(props[band_name])
                    valid_bands += 1

            if valid_bands == 64:
                print(f"   SUCCESS: Retrieved all 64 bands from year {year}")
                return {
                    'success': True,
                    'year': year,
                    'embedding': embedding,
                    'data_source': 'alphaearth_real',
                    'message': f'Real AlphaEarth data from {year}'
                }
            elif valid_bands > 0:
                print(f"   PARTIAL: Only {valid_bands}/64 bands had data (year {year})")
                return {
                    'success': True,
                    'year': year,
                    'embedding': embedding,
                    'data_source': 'alphaearth_partial',
                    'valid_bands': valid_bands,
                    'message': f'Partial AlphaEarth data ({valid_bands}/64 bands) from {year}'
                }
            else:
                return {
                    'success': False,
                    'error': f'No AlphaEarth coverage for year {year}'
                }

        else:
            return {
                'success': False,
                'error': f'Could not sample AlphaEarth for year {year}'
            }

    except Exception as e:
        error_str = str(e)
        # Don't log full stack for common "no data" errors
        if 'Collection.first' in error_str or 'no features' in error_str.lower():
            return {'success': False, 'error': f'No AlphaEarth data for year {year}'}
        print(f"   ERROR for year {year}: {error_str}")
        return {'success': False, 'error': f'Error sampling AlphaEarth: {error_str}'}


def sample_alphaearth_multiyear(lat: float, lon: float, preferred_year: int = 2023) -> dict:
    """
    Try multiple years for AlphaEarth coverage, starting with the preferred year.
    This handles the common case where a location has satellite coverage in some
    years but not others.
    """
    # Reorder years to try preferred first
    years = [preferred_year] + [y for y in ALPHAEARTH_YEARS if y != preferred_year]

    for year in years:
        result = sample_alphaearth_properly(lat, lon, year)
        if result.get('success'):
            return result

    return {
        'success': False,
        'error': 'No AlphaEarth coverage at this location for any year (2017-2023)',
        'years_tried': years
    }


def generate_realistic_embedding(lat: float, lon: float) -> dict:
    """
    Generate realistic simulated embedding as fallback.
    """
    seed = int(abs(lat * 1000) + abs(lon * 1000))
    np.random.seed(seed)

    embedding = {}
    for i in range(64):
        # Generate values similar to real AlphaEarth range
        value = np.random.normal(0, 0.08)  # Most values between -0.2 and 0.2
        value = np.clip(value, -0.3, 0.3)
        embedding[f'a{i:02d}'] = float(value)

    return embedding


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Location Predictor (FIXED v4)',
        'features': [
            'Multi-year AlphaEarth fallback (2023-2017)',
            'SRTM 30m elevation sampling',
            'Hansen forest change data',
            'WorldClim BIO (19 bioclimatic variables)',
            'OpenLandMap soil (pH, clay, sand, organic carbon, texture)',
            '3x3 embedding homogeneity grid (monoculture signal)',
            'Google CCDC change detection (breakpoints 1999-2019)',
            'ETH canopy height variance (10m, 100m radius)',
            'Simulated embedding fallback'
        ],
        'ee_initialized': True,
        'ee_project': PROJECT
    })


@app.route('/sample', methods=['POST', 'GET'])
def sample_endpoint():
    """
    Sample AlphaEarth embedding + environmental data at a location.

    POST /sample
    Body: { "lat": -14.2644, "lon": -52.7344, "year": 2023 }

    GET /sample?lat=-14.2644&lon=-52.7344&year=2023

    Returns:
    {
        "success": true,
        "lat": -14.2644,
        "lon": -52.7344,
        "year": 2023,
        "embedding": {"a00": 0.1, "a01": 0.2, ...},  // 64-D AlphaEarth
        "elevation": 450,                               // SRTM meters
        "treecover2000": 85,                            // Hansen %
        "lossyear": 0,                                  // Hansen year
        "loss": false,
        "gain": false,
        "data_source": "alphaearth_real",
        "demo_mode": false
    }
    """
    try:
        # Handle both GET and POST
        if request.method == 'POST':
            data = request.get_json() or {}
            lat = float(data.get('lat', 0))
            lon = float(data.get('lon', 0))
            year = int(data.get('year', 2023))
        else:
            lat = float(request.args.get('lat', 0))
            lon = float(request.args.get('lon', 0))
            year = int(request.args.get('year', 2023))

        if lat == 0 and lon == 0:
            return jsonify({'error': 'Missing required fields: lat, lon'}), 400

        # Validate ranges
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude'}), 400
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude'}), 400

        print(f"\n{'='*50}")
        print(f"Sampling location: ({lat:.4f}, {lon:.4f})")
        start_time = time.time()

        # Sample all environmental data
        # (GEE requests are sequential per call, but we batch them)

        # 1. AlphaEarth embedding (multi-year fallback)
        ae_result = sample_alphaearth_multiyear(lat, lon, year)

        # 2. SRTM elevation
        elev_data = sample_srtm_elevation(lat, lon)

        # 3. Hansen forest change
        hansen_data = sample_hansen_forest(lat, lon)

        # 4. WorldClim BIO variables (temperature, precipitation, bioclimatic)
        worldclim_data = sample_worldclim_bio(lat, lon)

        # 5. OpenLandMap soil properties (pH, clay, sand, texture, organic carbon)
        soil_data = sample_openlandmap_soil(lat, lon)

        # 6. Embedding homogeneity (3x3 grid monoculture signal)
        ae_year = ae_result.get('year', year) if ae_result.get('success') else year
        homogeneity_data = sample_embedding_homogeneity(lat, lon, ae_year)

        # 7. CCDC change detection (breakpoints since 1999)
        ccdc_data = sample_ccdc(lat, lon)

        # 8. Canopy height variance (ETH 10m, 100m radius)
        canopy_data = sample_canopy_height_variance(lat, lon)

        # 9. ALL SINR environmental features (single batched GEE call)
        #    Covers: terrain, soil, water, ecoregions, climate, plantation,
        #    land cover, fire, biomass, human modification, etc.
        sinr_env = sample_sinr_env_features(lat, lon, year)

        # Build response
        result = {
            'success': True,
            'lat': lat,
            'lon': lon,
        }

        # Add elevation and forest data
        result.update(elev_data)
        result.update(hansen_data)

        # Add climate data in a structured sub-object
        if worldclim_data:
            climate_obj = {
                'annual_mean_temp_c': worldclim_data.get('bio01'),       # BIO1
                'max_temp_warmest_month_c': worldclim_data.get('bio05'), # BIO5
                'min_temp_coldest_month_c': worldclim_data.get('bio06'), # BIO6
                'annual_precipitation_mm': worldclim_data.get('bio12'),  # BIO12
                'precip_wettest_month_mm': worldclim_data.get('bio13'),  # BIO13
                'precip_driest_month_mm': worldclim_data.get('bio14'),   # BIO14
                'precip_seasonality_cv': worldclim_data.get('bio15'),    # BIO15
                'mean_diurnal_range_c': worldclim_data.get('bio02'),     # BIO2
                'isothermality': worldclim_data.get('bio03'),            # BIO3
                'temp_seasonality': worldclim_data.get('bio04'),         # BIO4
                'temp_annual_range_c': worldclim_data.get('bio07'),      # BIO7
                'mean_temp_wettest_quarter_c': worldclim_data.get('bio08'),  # BIO8
                'mean_temp_driest_quarter_c': worldclim_data.get('bio09'),   # BIO9
                'mean_temp_warmest_quarter_c': worldclim_data.get('bio10'),  # BIO10
                'mean_temp_coldest_quarter_c': worldclim_data.get('bio11'),  # BIO11
                'precip_wettest_quarter_mm': worldclim_data.get('bio16'),    # BIO16
                'precip_driest_quarter_mm': worldclim_data.get('bio17'),     # BIO17
                'precip_warmest_quarter_mm': worldclim_data.get('bio18'),    # BIO18
                'precip_coldest_quarter_mm': worldclim_data.get('bio19'),    # BIO19
            }
            
            # Derive Koppen-Geiger climate zone
            koppen = classify_koppen_geiger(worldclim_data)
            if koppen:
                climate_obj['koppen_code'] = koppen['code']
                climate_obj['koppen_description'] = koppen['description']
                print(f"   Koppen-Geiger: {koppen['code']} - {koppen['description']}")
            
            result['climate'] = climate_obj

        # Add soil data in a structured sub-object
        if soil_data:
            result['soil'] = soil_data

        # Add new signals (homogeneity, CCDC, canopy height)
        if homogeneity_data:
            result['embedding_homogeneity'] = homogeneity_data.get('embedding_homogeneity')
            result['homogeneity_detail'] = homogeneity_data

        if ccdc_data:
            result['ccdc'] = ccdc_data

        if canopy_data:
            result['canopy_height'] = canopy_data

        # SINR environmental features (all 35 bands from batched GEE call)
        if sinr_env:
            result['sinr_env'] = sinr_env

        if ae_result.get('success'):
            result['year'] = ae_result.get('year', year)
            result['embedding'] = ae_result['embedding']
            result['data_source'] = ae_result.get('data_source', 'alphaearth_real')
            result['demo_mode'] = False
            result['message'] = ae_result.get('message', 'AlphaEarth data retrieved')
        else:
            # Fallback to simulated embedding
            print(f"   Using simulated embedding (no real data available)")
            result['year'] = year
            result['embedding'] = generate_realistic_embedding(lat, lon)
            result['data_source'] = 'simulated'
            result['demo_mode'] = True
            result['message'] = 'No AlphaEarth coverage - using simulated data for demo'
            if ae_result.get('years_tried'):
                result['years_tried'] = ae_result['years_tried']

        elapsed = time.time() - start_time
        result['processing_time'] = round(elapsed, 2)

        elev_str = f", elev={result.get('elevation', 'N/A')}m" if 'elevation' in result else ""
        tc_str = f", tc={result.get('treecover2000', 'N/A')}%" if 'treecover2000' in result else ""
        climate_str = ""
        if 'climate' in result:
            t = result['climate'].get('annual_mean_temp_c')
            p = result['climate'].get('annual_precipitation_mm')
            climate_str = f", temp={t}°C, precip={p}mm" if t and p else ""
        soil_str = ""
        if 'soil' in result:
            ph = result['soil'].get('soil_ph')
            tex = result['soil'].get('soil_texture')
            soil_str = f", pH={ph} ({tex})" if ph and tex else ""
        print(f"   Done in {elapsed:.1f}s — source={result['data_source']}{elev_str}{tc_str}{climate_str}{soil_str}")

        return jsonify(result), 200

    except Exception as e:
        print(f"Error in sample endpoint: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test-amazon', methods=['GET'])
def test_amazon():
    """Quick test endpoint for Amazon locations"""
    test_locs = [
        {"name": "Manaus", "lat": -3.4653, "lon": -62.2159},
        {"name": "Mato Grosso", "lat": -14.2644, "lon": -52.7344}
    ]

    results = []
    for loc in test_locs:
        result = sample_alphaearth_properly(loc['lat'], loc['lon'], 2023)
        results.append({
            'location': loc['name'],
            'coordinates': f"({loc['lat']}, {loc['lon']})",
            'success': result.get('success'),
            'data_source': result.get('data_source', 'none'),
            'sample_values': list(result.get('embedding', {}).items())[:3] if result.get('embedding') else []
        })

    return jsonify(results), 200


@app.route('/test-nz', methods=['GET'])
def test_nz():
    """Test endpoint for New Zealand locations (pine plantations)"""
    test_locs = [
        {"name": "Canterbury Plains (pine)", "lat": -43.53, "lon": 172.47},
        {"name": "Kaingaroa Forest", "lat": -38.48, "lon": 176.65},
        {"name": "Nelson Forests", "lat": -41.27, "lon": 173.28}
    ]

    results = []
    for loc in test_locs:
        result = sample_alphaearth_multiyear(loc['lat'], loc['lon'], 2023)
        elev = sample_srtm_elevation(loc['lat'], loc['lon'])
        results.append({
            'location': loc['name'],
            'coordinates': f"({loc['lat']}, {loc['lon']})",
            'success': result.get('success'),
            'data_source': result.get('data_source', 'none'),
            'year': result.get('year'),
            'elevation': elev.get('elevation'),
            'sample_values': list(result.get('embedding', {}).items())[:3] if result.get('embedding') else []
        })

    return jsonify(results), 200


# ══════════════════════════════════════════════════════════════════════════════
# SINR v3 INFERENCE ENGINE (with v2.2 fallback)
# ══════════════════════════════════════════════════════════════════════════════

import torch
import torch.nn as nn
import json
import importlib.util
from pathlib import Path
from typing import Optional, Dict

SCRIPT_DIR = Path(__file__).parent
MODEL_DIR = SCRIPT_DIR / "sinr_model"
DATA_DIR = SCRIPT_DIR / "sinr_training_data"

# v3 model directory (v14 with location encoding)
V3_MODEL_DIR = Path.home() / "model_local_contract_v14_location_5m"
V3_CONTRACTS_DIR = SCRIPT_DIR / "contracts" / "sinr_v3"

# ── Model definition (must match training code exactly) ──────────────────────

class ResidualBlock(nn.Module):
    def __init__(self, dim: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return x + self.net(x)


class SINRModel(nn.Module):
    NUM_SAT_DIMS = 64

    def __init__(self, num_continuous, num_species, categorical_config=None,
                 hidden_dim=256, num_blocks=4, dropout=0.3, fusion_dim=128,
                 use_gate=True, use_aux_head=False):
        super().__init__()
        self.num_continuous = num_continuous
        self.num_species = num_species
        self.categorical_config = categorical_config or {}
        self.use_gate = use_gate
        self.use_aux_head = use_aux_head
        self.fusion_dim = fusion_dim

        self.embeddings = nn.ModuleDict()
        total_emb_dim = 0
        for col_name, cfg in self.categorical_config.items():
            self.embeddings[col_name] = nn.Embedding(
                num_embeddings=cfg["vocab_size"],
                embedding_dim=cfg["emb_dim"],
                padding_idx=0,
            )
            total_emb_dim += cfg["emb_dim"]
        self.total_emb_dim = total_emb_dim

        num_sat = self.NUM_SAT_DIMS
        num_env_continuous = num_continuous - num_sat

        if use_gate:
            self.sat_proj = nn.Sequential(
                nn.Linear(num_sat, fusion_dim), nn.ReLU(inplace=True))
            env_input_dim = num_env_continuous + total_emb_dim
            self.env_proj = nn.Sequential(
                nn.Linear(env_input_dim, fusion_dim), nn.ReLU(inplace=True))

            # Gate: jrc_emb(3D) + is_introduced(1D) = 4D
            gate_input_dim = self.categorical_config.get(
                "jrc_forest_type", {}).get("emb_dim", 3) + 1
            self.gate_input_dim = gate_input_dim
            self.gate = nn.Sequential(
                nn.Linear(gate_input_dim, 16), nn.ReLU(inplace=True),
                nn.Linear(16, 1), nn.Sigmoid())
            self.input_layer = nn.Sequential(
                nn.Linear(fusion_dim, hidden_dim), nn.ReLU(inplace=True))
        else:
            total_input_dim = num_continuous + total_emb_dim
            self.input_layer = nn.Sequential(
                nn.Linear(total_input_dim, hidden_dim), nn.ReLU(inplace=True))

        self.res_blocks = nn.Sequential(
            *[ResidualBlock(hidden_dim, dropout) for _ in range(num_blocks)])
        self.output_layer = nn.Linear(hidden_dim, num_species, bias=False)

        if use_aux_head:
            self.aux_head = nn.Linear(hidden_dim, 1)
            self.boost_scale = nn.Parameter(torch.tensor(2.0))
            self.register_buffer("species_intro_ratio", torch.zeros(num_species))

    def forward(self, x_continuous, x_categorical=None, x_is_introduced=None):
        cat_embs = {}
        cat_emb_list = []
        if x_categorical is not None and len(self.embeddings) > 0:
            for i, col_name in enumerate(self.categorical_config.keys()):
                cat_indices = x_categorical[:, i]
                emb = self.embeddings[col_name](cat_indices)
                cat_embs[col_name] = emb
                cat_emb_list.append(emb)

        if self.use_gate:
            batch_size = x_continuous.shape[0]
            x_sat = x_continuous[:, :self.NUM_SAT_DIMS]
            x_env_cont = x_continuous[:, self.NUM_SAT_DIMS:]
            sat_h = self.sat_proj(x_sat)
            env_parts = [x_env_cont] + cat_emb_list
            env_input = torch.cat(env_parts, dim=1)
            env_h = self.env_proj(env_input)

            gate_parts = []
            jrc_emb = cat_embs.get("jrc_forest_type",
                torch.zeros(batch_size, 3, device=x_continuous.device))
            gate_parts.append(jrc_emb)
            if x_is_introduced is None:
                is_intro = torch.full((batch_size, 1), 0.5, device=x_continuous.device)
            else:
                is_intro = x_is_introduced
            gate_parts.append(is_intro)
            gate_input = torch.cat(gate_parts, dim=1)
            alpha = self.gate(gate_input)
            x = alpha * sat_h + (1 - alpha) * env_h
            x = self.input_layer(x)
        else:
            parts = [x_continuous] + cat_emb_list
            x = torch.cat(parts, dim=1)
            x = self.input_layer(x)

        x = self.res_blocks(x)
        logits = self.output_layer(x)

        if self.use_aux_head:
            aux_logits = self.aux_head(x)
            planted_score = torch.sigmoid(aux_logits)
            boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
            logits = logits + boost
            return logits, aux_logits
        return logits


# ── Categorical remapping (same as training) ─────────────────────────────────

CATEGORICAL_FEATURES = {
    "jrc_forest_type": {"vocab_size": 5, "emb_dim": 3,
                        "value_map": {0: 1, 1: 2, 10: 3, 20: 4}},
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                            "value_map": {0: 1, 1: 2, 2: 3}},
    "eco_id": {"vocab_size": 850, "emb_dim": 32, "value_map": None},
    "biome_num": {"vocab_size": 16, "emb_dim": 8, "value_map": None},
    "soil_texture_class": {"vocab_size": 14, "emb_dim": 6, "value_map": None},
}


def remap_categorical_value(raw_val: int, col_name: str) -> int:
    """Remap a raw categorical value to its embedding index."""
    cfg = CATEGORICAL_FEATURES[col_name]
    value_map = cfg["value_map"]
    vocab_size = cfg["vocab_size"]
    if value_map is not None:
        return value_map.get(raw_val, 0)
    else:
        return raw_val if 0 <= raw_val < vocab_size else 0


# ── Feature assembly from /sample response ───────────────────────────────────

# Mapping from climate dict keys back to raw GEE WorldClim values
BIO_CLIMATE_MAP = [
    ('bio01', 'annual_mean_temp_c', 10),
    ('bio02', 'mean_diurnal_range_c', 10),
    ('bio03', 'isothermality', 10),
    ('bio04', 'temp_seasonality', 10),
    ('bio05', 'max_temp_warmest_month_c', 10),
    ('bio06', 'min_temp_coldest_month_c', 10),
    ('bio07', 'temp_annual_range_c', 10),
    ('bio08', 'mean_temp_wettest_quarter_c', 10),
    ('bio09', 'mean_temp_driest_quarter_c', 10),
    ('bio10', 'mean_temp_warmest_quarter_c', 10),
    ('bio11', 'mean_temp_coldest_quarter_c', 10),
    ('bio12', 'annual_precipitation_mm', 1),
    ('bio13', 'precip_wettest_month_mm', 1),
    ('bio14', 'precip_driest_month_mm', 1),
    ('bio15', 'precip_seasonality_cv', 1),
    ('bio16', 'precip_wettest_quarter_mm', 1),
    ('bio17', 'precip_driest_quarter_mm', 1),
    ('bio18', 'precip_warmest_quarter_mm', 1),
    ('bio19', 'precip_coldest_quarter_mm', 1),
]

SINR_ENV_TAIL_COLS = [
    'jrc_tmf_status', 'jrc_tmf_degrad_year',
    'esa_worldcover_2021', 'dynamic_world', 'sbtn_natural_land',
    'water_occurrence', 'water_recurrence', 'water_seasonality',
    'merit_hand_m', 'merit_upstream_area_km2',
    'gedi_canopy_height_m', 'gedi_foliage_height_div',
    'modis_gpp_mean', 'biomass_agb_mgha',
    'human_modification', 'nighttime_lights', 'fire_frequency_count',
    'topo_diversity',
    'tc_vpd_mean', 'tc_aet_mean', 'tc_soil_moisture_mean',
    'tc_pdsi_mean', 'tc_water_deficit_mean', 'tc_solar_rad_mean',
    'neumann_natural_prob',
]


def map_sample_to_features(sample_data: dict):
    """Convert /sample response → (continuous_120, categorical_5_raw) arrays."""
    emb = sample_data.get('embedding', {})
    climate = sample_data.get('climate', {})
    soil = sample_data.get('soil', {})
    sinr_env = sample_data.get('sinr_env', {})

    continuous = []

    # 0-63: AlphaEarth embedding
    for i in range(64):
        continuous.append(float(emb.get(f'a{i:02d}', 0.0)))

    # 64: elevation
    continuous.append(float(sample_data.get('elevation', sinr_env.get('elevation', 0.0)) or 0.0))

    # 65-67: slope, aspect, hillshade
    for col in ['slope', 'aspect', 'hillshade']:
        continuous.append(float(sinr_env.get(col, 0.0) or 0.0))

    # 68-86: bio01-bio19 (reverse temp conversion: × 10 for bio01-bio11)
    for bio_name, climate_key, multiplier in BIO_CLIMATE_MAP:
        val = climate.get(climate_key)
        continuous.append(float(val * multiplier) if val is not None else 0.0)

    # 87: soil_ph (× 10 to restore raw GEE scale)
    soil_ph = soil.get('soil_ph')
    continuous.append(float(soil_ph * 10) if soil_ph is not None else 0.0)

    # 88-89: soil_clay_pct, soil_sand_pct (no conversion needed)
    continuous.append(float(soil.get('soil_clay_pct', 0.0) or 0.0))
    continuous.append(float(soil.get('soil_sand_pct', 0.0) or 0.0))

    # 90: soil_organic_carbon
    continuous.append(float(soil.get('soil_organic_carbon_g_kg', 0.0) or 0.0))

    # 91-92: soil_bulk_density, soil_water_content (from sinr_env)
    continuous.append(float(sinr_env.get('soil_bulk_density', 0.0) or 0.0))
    continuous.append(float(sinr_env.get('soil_water_content', 0.0) or 0.0))

    # 93-94: treecover2000, lossyear (from top-level Hansen)
    continuous.append(float(sample_data.get('treecover2000', 0.0) or 0.0))
    continuous.append(float(sample_data.get('lossyear', 0.0) or 0.0))

    # 95-119: remaining env features from sinr_env
    for col in SINR_ENV_TAIL_COLS:
        continuous.append(float(sinr_env.get(col, 0.0) or 0.0))

    # Categorical raw values
    cat_raw = {
        'jrc_forest_type': int(sinr_env.get('jrc_forest_type', 0) or 0),
        'xiao_planted_forest': int(sinr_env.get('xiao_planted_forest', 0) or 0),
        'eco_id': int(sinr_env.get('eco_id', 0) or 0),
        'biome_num': int(sinr_env.get('biome_num', 0) or 0),
        'soil_texture_class': int(sinr_env.get('soil_texture_class', 0) or 0),
    }

    return continuous, cat_raw


# ── Model loading and inference ──────────────────────────────────────────────

sinr_model = None
sinr_norm_mean = None
sinr_norm_std = None
sinr_species_mapping = None
sinr_idx_to_species = None


def load_sinr_model():
    """Load SINR v2.2 model and artifacts at startup."""
    global sinr_model, sinr_norm_mean, sinr_norm_std
    global sinr_species_mapping, sinr_idx_to_species

    model_path = MODEL_DIR / "best_model.pt"
    stats_path = MODEL_DIR / "normalize_stats.npz"
    mapping_path = DATA_DIR / "species_mapping.json"

    if not model_path.exists():
        print(f"  SINR model not found at {model_path}")
        return False

    print(f"\n  Loading SINR v2.2 model...")

    # Load checkpoint
    ckpt = torch.load(model_path, map_location='cpu', weights_only=False)
    print(f"    Epoch {ckpt['epoch']}, top-10={ckpt['top10_accuracy']:.1%}, "
          f"top-50={ckpt['top50_accuracy']:.1%}")

    # Reconstruct model from saved hyperparameters
    model = SINRModel(
        num_continuous=ckpt['num_continuous'],
        num_species=ckpt['num_species'],
        categorical_config=ckpt['categorical_config'],
        hidden_dim=ckpt['hidden_dim'],
        num_blocks=ckpt['num_blocks'],
        dropout=ckpt['dropout'],
        use_gate=ckpt['use_gate'],
        use_aux_head=ckpt['use_aux_head'],
    )
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    sinr_model = model
    print(f"    Model loaded: {ckpt['num_species']:,} species, "
          f"{ckpt['num_continuous']} continuous features")

    # Load normalization stats
    stats = np.load(stats_path, allow_pickle=True)
    sinr_norm_mean = stats['mean'].astype(np.float32)
    sinr_norm_std = stats['std'].astype(np.float32)
    # Avoid division by zero
    sinr_norm_std[sinr_norm_std < 1e-8] = 1.0
    print(f"    Normalization stats loaded: {len(sinr_norm_mean)} features")

    # Load species mapping
    with open(mapping_path) as f:
        sinr_species_mapping = json.load(f)
    sinr_idx_to_species = {v: k for k, v in sinr_species_mapping['species_to_idx'].items()}
    print(f"    Species mapping loaded: {sinr_species_mapping['num_species']:,} species")

    return True


@torch.no_grad()
def run_sinr_inference(sample_data: dict, top_k: int = 100, is_introduced_val: float = 0.5):
    """Run SINR v2.2 inference on sampled environmental data.

    Args:
        sample_data: Response from /sample endpoint
        top_k: Number of top species to return
        is_introduced_val: 0.0=native, 1.0=introduced, 0.5=unknown

    Returns:
        List of (taxon_id, probability) tuples, sorted by probability descending
    """
    if sinr_model is None:
        return []

    # Map sample data to feature vectors
    continuous, cat_raw = map_sample_to_features(sample_data)

    # Remap categorical values to embedding indices
    cat_indices = []
    for col_name in CATEGORICAL_FEATURES:
        cat_indices.append(remap_categorical_value(cat_raw[col_name], col_name))

    # Build tensors
    x_cont = np.array(continuous, dtype=np.float32)

    # Z-score normalize
    x_cont = (x_cont - sinr_norm_mean) / sinr_norm_std

    x_cont_t = torch.from_numpy(x_cont).unsqueeze(0)  # (1, 120)
    x_cat_t = torch.tensor([cat_indices], dtype=torch.long)  # (1, 5)
    x_intro_t = torch.tensor([[is_introduced_val]], dtype=torch.float32)  # (1, 1)

    # Forward pass
    result = sinr_model(x_cont_t, x_cat_t, x_intro_t)
    if isinstance(result, tuple):
        logits, aux_logits = result
    else:
        logits = result

    # Convert logits to probabilities (independent sigmoids)
    probs = torch.sigmoid(logits).squeeze(0).numpy()  # (num_species,)

    # Get top-K species
    top_indices = np.argsort(probs)[::-1][:top_k]
    results = []
    for idx in top_indices:
        taxon_id = sinr_idx_to_species.get(int(idx), f"unknown_{idx}")
        results.append({
            'taxon_id': taxon_id,
            'probability': round(float(probs[idx]), 6),
            'rank': len(results) + 1,
        })

    return results


@torch.no_grad()
def run_sinr_two_pass(sample_data: dict, top_k: int = 100):
    """Run two-pass SINR inference: once as native, once as introduced.

    Returns per-species results with both probabilities. The backend can
    then select the appropriate one based on WCVP native status at the
    query location.
    """
    if sinr_model is None:
        return []

    continuous, cat_raw = map_sample_to_features(sample_data)
    cat_indices = []
    for col_name in CATEGORICAL_FEATURES:
        cat_indices.append(remap_categorical_value(cat_raw[col_name], col_name))

    x_cont = np.array(continuous, dtype=np.float32)
    x_cont = (x_cont - sinr_norm_mean) / sinr_norm_std
    x_cont_t = torch.from_numpy(x_cont).unsqueeze(0)
    x_cat_t = torch.tensor([cat_indices], dtype=torch.long)

    # Pass 1: is_introduced = 0 (native)
    x_native = torch.tensor([[0.0]], dtype=torch.float32)
    result_native = sinr_model(x_cont_t, x_cat_t, x_native)
    logits_native = result_native[0] if isinstance(result_native, tuple) else result_native
    probs_native = torch.sigmoid(logits_native).squeeze(0).numpy()

    # Pass 2: is_introduced = 1 (introduced)
    x_intro = torch.tensor([[1.0]], dtype=torch.float32)
    result_intro = sinr_model(x_cont_t, x_cat_t, x_intro)
    logits_intro = result_intro[0] if isinstance(result_intro, tuple) else result_intro
    probs_intro = torch.sigmoid(logits_intro).squeeze(0).numpy()

    # Combine: use max of native/introduced as the "best" probability for ranking
    # Backend will refine based on actual WCVP data per species
    probs_best = np.maximum(probs_native, probs_intro)
    top_indices = np.argsort(probs_best)[::-1][:top_k]

    results = []
    for idx in top_indices:
        taxon_id = sinr_idx_to_species.get(int(idx), f"unknown_{idx}")
        results.append({
            'taxon_id': taxon_id,
            'prob_native': round(float(probs_native[idx]), 6),
            'prob_introduced': round(float(probs_intro[idx]), 6),
            'prob_best': round(float(probs_best[idx]), 6),
            'rank': len(results) + 1,
        })

    return results


# ── SINR inference endpoint ──────────────────────────────────────────────────

@app.route('/sinr-infer', methods=['POST'])
def sinr_infer_endpoint():
    """Run SINR species prediction at a location.

    Uses v3 (v14 location-encoded) model if available, falls back to v2.2.

    POST /sinr-infer
    Body: {
        "sample_data": { ... },   // Pre-sampled /sample response (v2.2 only)
        // OR
        "lat": -14.2644,          // Will call sampling functions directly
        "lon": -52.7344,
        "year": 2023,
        "top_k": 100,             // Number of species to return (default 100)
        "two_pass": true           // Enable two-pass native/introduced inference (v2.2 only)
    }
    """
    try:
        data = request.get_json() or {}
        top_k = int(data.get('top_k', 100))
        two_pass = data.get('two_pass', True)
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        year = int(data.get('year', 2023))

        # === Try v3 first (needs lat/lon for location encoding) ===
        if sinr_v3_model is not None and lat != 0 and lon != 0:
            print(f"\n{'='*50}")
            print(f"SINR v3 inference at ({lat:.4f}, {lon:.4f})")
            start_time = time.time()

            v3_result = run_sinr_v3_inference(lat, lon, year, top_k)
            total_time = time.time() - start_time

            predictions = v3_result.get('predictions', []) if isinstance(v3_result, dict) else v3_result
            aux_outputs = v3_result.get('aux', {}) if isinstance(v3_result, dict) else {}
            inf_mode = v3_result.get('inference_mode', 'v3_location_enc') if isinstance(v3_result, dict) else 'v3_location_enc'

            if predictions:
                print(f"   SINR v3 done in {total_time:.1f}s "
                      f"(top-1: {predictions[0]['taxon_id']} "
                      f"p={predictions[0]['prob_best']:.4f}, "
                      f"mode={predictions[0].get('best_mode', 'n/a')}, "
                      f"planted={aux_outputs.get('planted_score', 'n/a')})")

                return jsonify({
                    'success': True,
                    'lat': lat,
                    'lon': lon,
                    'model_version': 'sinr_v3_v14_location',
                    'inference_mode': inf_mode,
                    'num_species_total': len(sinr_v3_idx_to_species),
                    'top_k': top_k,
                    'predictions': predictions,
                    'aux_outputs': aux_outputs,
                    'timing': {
                        'sampling_s': round(total_time, 2),
                        'inference_ms': round(total_time * 1000, 1),
                    },
                    'data_source': 'alphaearth_gee',
                }), 200

        # === Fallback to v2.2 ===
        if sinr_model is None:
            return jsonify({'error': 'No SINR model loaded'}), 503

        sample_data = data.get('sample_data')

        if sample_data is None:
            if lat == 0 and lon == 0:
                return jsonify({'error': 'Provide sample_data or lat/lon'}), 400

            print(f"\n{'='*50}")
            print(f"SINR v2.2 inference: sampling ({lat:.4f}, {lon:.4f})")
            start_time = time.time()

            ae_result = sample_alphaearth_multiyear(lat, lon, year)
            elev_data = sample_srtm_elevation(lat, lon)
            hansen_data = sample_hansen_forest(lat, lon)
            worldclim_data = sample_worldclim_bio(lat, lon)
            soil_data = sample_openlandmap_soil(lat, lon)
            sinr_env = sample_sinr_env_features(lat, lon, year)

            sample_data = {'success': True, 'lat': lat, 'lon': lon}
            sample_data.update(elev_data)
            sample_data.update(hansen_data)
            if worldclim_data:
                climate_obj = {}
                for bio_name, climate_key, mult in BIO_CLIMATE_MAP:
                    val = worldclim_data.get(bio_name)
                    if val is not None:
                        climate_obj[climate_key] = val
                koppen = classify_koppen_geiger(worldclim_data)
                if koppen:
                    climate_obj['koppen_code'] = koppen['code']
                sample_data['climate'] = climate_obj
            if soil_data:
                sample_data['soil'] = soil_data
            if sinr_env:
                sample_data['sinr_env'] = sinr_env
            if ae_result.get('success'):
                sample_data['embedding'] = ae_result['embedding']
                sample_data['data_source'] = ae_result.get('data_source')
            else:
                sample_data['embedding'] = generate_realistic_embedding(lat, lon)
                sample_data['data_source'] = 'simulated'

            sampling_time = time.time() - start_time
            print(f"   Sampling done in {sampling_time:.1f}s")
        else:
            sampling_time = 0
            lat = sample_data.get('lat', 0)
            lon = sample_data.get('lon', 0)

        # Run v2.2 inference
        infer_start = time.time()
        if two_pass:
            predictions = run_sinr_two_pass(sample_data, top_k)
        else:
            predictions = run_sinr_inference(sample_data, top_k)
        infer_time = time.time() - infer_start

        print(f"   SINR v2.2 inference done in {infer_time*1000:.0f}ms "
              f"({'two-pass' if two_pass else 'single-pass'}, "
              f"top-1: {predictions[0]['taxon_id'] if predictions else 'none'} "
              f"p={predictions[0].get('prob_best', predictions[0].get('probability', 0)):.4f})")

        return jsonify({
            'success': True,
            'lat': lat,
            'lon': lon,
            'model_version': 'sinr_v2.2',
            'inference_mode': 'two_pass' if two_pass else 'single_pass',
            'num_species_total': sinr_species_mapping['num_species'],
            'top_k': top_k,
            'predictions': predictions,
            'timing': {
                'sampling_s': round(sampling_time, 2),
                'inference_ms': round(infer_time * 1000, 1),
            },
            'data_source': sample_data.get('data_source', 'unknown'),
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# SINR v3 MODEL (v14 with location encoding)
# ══════════════════════════════════════════════════════════════════════════════

sinr_v3_model = None
sinr_v3_mapping = None
sinr_v3_idx_to_species = None
sinr_v3_cont_mean = None
sinr_v3_cont_std = None
sinr_v3_temporal_mean = None
sinr_v3_temporal_std = None
sinr_v3_tvm = None  # train_on_vm module reference
sinr_v3_env_cols = None  # from feature contract
sinr_v3_cat_config = None  # from model config


def load_sinr_v3_model():
    """Load SINR v3 (v14 location-encoding) model and artifacts."""
    global sinr_v3_model, sinr_v3_mapping, sinr_v3_idx_to_species
    global sinr_v3_cont_mean, sinr_v3_cont_std
    global sinr_v3_temporal_mean, sinr_v3_temporal_std, sinr_v3_tvm
    global sinr_v3_env_cols, sinr_v3_cat_config

    ckpt_path = V3_MODEL_DIR / "best_model.pt"
    stats_path = V3_MODEL_DIR / "normalize_stats_v3.npz"
    temporal_stats_path = V3_MODEL_DIR / "normalize_temporal_v3.npz"
    mapping_path = V3_MODEL_DIR / "species_mapping_v3.json"

    if not ckpt_path.exists():
        print(f"  SINR v3 model not found at {ckpt_path}")
        return False

    print(f"\n  Loading SINR v3 model (v14 location encoding)...")

    # Import train_on_vm module for model class and constants
    tvm_path = SCRIPT_DIR / "train_on_vm.py"
    spec = importlib.util.spec_from_file_location("train_on_vm", str(tvm_path))
    tvm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tvm)
    sinr_v3_tvm = tvm

    # Load species mapping
    with open(mapping_path) as f:
        sinr_v3_mapping = json.load(f)
    species_to_idx = sinr_v3_mapping["species_to_idx"]
    sinr_v3_idx_to_species = {int(k): v for k, v in sinr_v3_mapping["idx_to_species"].items()}
    num_species = len(species_to_idx)

    # Load saved model config to ensure exact architecture match
    config_path = V3_MODEL_DIR / "model_config_v3.json"
    with open(config_path) as f:
        model_cfg = json.load(f)

    # Build model from saved config
    SINRModelV3 = tvm.build_model()
    model = SINRModelV3(
        num_env_continuous=model_cfg["num_env_continuous"],
        num_species=num_species,
        categorical_config=model_cfg["categorical_config"],
        hidden_dim=model_cfg.get("hidden_dim", tvm.HIDDEN_DIM),
        num_blocks=model_cfg.get("num_blocks", tvm.NUM_RES_BLOCKS),
        dropout=model_cfg.get("dropout", tvm.DROPOUT),
        fusion_dim=model_cfg.get("fusion_dim", tvm.FUSION_DIM),
        temporal_dim=model_cfg.get("temporal_dim", tvm.TEMPORAL_HIDDEN),
        phylo_dim=model_cfg.get("phylo_dim", tvm.PHYLO_DIMS),
        gate_use_intro=model_cfg.get("gate_use_intro", False),
        intro_residual=model_cfg.get("intro_residual", False),
        location_enc_dim=model_cfg.get("location_enc_dim", 0),
    )

    # Store config for inference
    sinr_v3_cat_config = model_cfg["categorical_config"]

    # Load feature contract for env cols
    fc_path = V3_CONTRACTS_DIR / "feature_contract_v2_online56.json"
    if fc_path.exists():
        with open(fc_path) as f:
            fc = json.load(f)
        sinr_v3_env_cols = fc["env_continuous_cols"]
        print(f"    Feature contract: {len(sinr_v3_env_cols)} env continuous cols")
    else:
        sinr_v3_env_cols = tvm.ENV_CONTINUOUS_COLS
        print(f"    Using default ENV_CONTINUOUS_COLS: {len(sinr_v3_env_cols)}")

    # Load weights
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])

    # Load intro ratio contract
    intro_ratio_path = V3_CONTRACTS_DIR / "intro_ratio_contract_v1_strict_full.json"
    if intro_ratio_path.exists():
        with open(intro_ratio_path) as f:
            intro_contract = json.load(f)
        ratio_arr = np.asarray(
            intro_contract.get("species_intro_ratio", [0.0] * num_species),
            dtype=np.float32,
        )
        with torch.no_grad():
            model.species_intro_ratio.copy_(torch.from_numpy(ratio_arr))
        print(f"    Intro ratio contract loaded: {int((ratio_arr > 0).sum())} species")

    model.eval()
    sinr_v3_model = model

    # Load normalization stats
    stats = np.load(stats_path, allow_pickle=True)
    sinr_v3_cont_mean = stats["mean"].astype(np.float32)
    sinr_v3_cont_std = stats["std"].astype(np.float32)
    sinr_v3_cont_std[sinr_v3_cont_std < 1e-8] = 1.0

    if temporal_stats_path.exists():
        ts = np.load(temporal_stats_path, allow_pickle=True)
        sinr_v3_temporal_mean = ts["mean"].astype(np.float32)
        sinr_v3_temporal_std = ts["std"].astype(np.float32)
        sinr_v3_temporal_std[sinr_v3_temporal_std < 1e-8] = 1.0

    print(f"    Model loaded: {num_species:,} species, location_enc=40D")
    print(f"    Normalization: {len(sinr_v3_cont_mean)} continuous features")
    return True


def sample_ae_year_direct(lat, lon, year):
    """Sample AlphaEarth embedding for a single year, returning 64D array."""
    result = sample_alphaearth_properly(lat, lon, year)
    if result.get("success") and result.get("embedding"):
        emb = result["embedding"]
        # Embedding is a dict with keys like 'a00', 'a01', ... 'a63'
        return np.array([float(emb.get(f"a{i:02d}", 0.0)) for i in range(64)], dtype=np.float32)
    return np.zeros(64, dtype=np.float32)


@torch.no_grad()
def run_sinr_v3_inference(lat, lon, year, top_k=100):
    """Run SINR v3 inference with full feature pipeline."""
    if sinr_v3_model is None:
        return []

    tvm = sinr_v3_tvm

    # === Sample environmental features ===
    elev = sample_srtm_elevation(lat, lon)
    hansen = sample_hansen_forest(lat, lon)
    worldclim = sample_worldclim_bio(lat, lon)
    soil = sample_openlandmap_soil(lat, lon)
    sinr_env = sample_sinr_env_features(lat, lon, year)

    # Primary embedding
    emb_year = sample_ae_year_direct(lat, lon, year)

    # Temporal embeddings 2017..2024
    temporal_parts = []
    for y in range(2017, 2025):
        temporal_parts.append(sample_ae_year_direct(lat, lon, y))
    ae_temporal = np.concatenate(temporal_parts, axis=0).astype(np.float32)

    # Build feature dict
    feat = {}
    for i in range(64):
        feat[f"emb_{i:02d}"] = float(emb_year[i])

    feat["elevation"] = float(elev.get("elevation", 0.0) or 0.0)
    feat["treecover2000"] = float(hansen.get("treecover2000", 0.0) or 0.0)
    feat["lossyear"] = float(hansen.get("lossyear", 0.0) or 0.0)

    for i in range(1, 20):
        key = f"bio{i:02d}"
        val = float(worldclim.get(key, 0.0) or 0.0)
        if i <= 11:
            val *= 10.0
        feat[key] = val

    feat["soil_ph"] = float(soil.get("soil_ph", 0.0) or 0.0) * 10.0
    feat["soil_clay_pct"] = float(soil.get("soil_clay_pct", 0.0) or 0.0)
    feat["soil_sand_pct"] = float(soil.get("soil_sand_pct", 0.0) or 0.0)
    feat["soil_organic_carbon"] = float(soil.get("soil_organic_carbon_g_kg", 0.0) or 0.0)

    for k, v in sinr_env.items():
        try:
            feat[k] = float(v) if v is not None else 0.0
        except Exception:
            feat[k] = 0.0

    # === Build model input tensors ===

    # Continuous: AE 64D + env continuous (from feature contract)
    ae_cols = [f"emb_{i:02d}" for i in range(64)]
    cont_cols = ae_cols + sinr_v3_env_cols
    x_cont = np.array([float(feat.get(c, 0.0) or 0.0) for c in cont_cols], dtype=np.float32)

    # Align normalization
    stats_path = V3_MODEL_DIR / "normalize_stats_v3.npz"
    stats = np.load(stats_path, allow_pickle=True)
    saved_cols = [str(x) for x in stats["columns"]]
    if saved_cols == cont_cols:
        x_cont = (x_cont - sinr_v3_cont_mean) / sinr_v3_cont_std
    else:
        idx_map = {c: i for i, c in enumerate(saved_cols)}
        for i, c in enumerate(cont_cols):
            if c in idx_map:
                j = idx_map[c]
                x_cont[i] = (x_cont[i] - sinr_v3_cont_mean[j]) / sinr_v3_cont_std[j]

    # Categorical indices (from model config)
    cat_values = []
    for col, cfg in sinr_v3_cat_config.items():
        raw = int(round(float(feat.get(col, 0.0) or 0.0)))
        vmap = cfg.get("value_map") or {}
        if vmap:
            mapped = int(vmap.get(str(raw), vmap.get(raw, 0)))
        else:
            mapped = raw if 0 <= raw < cfg["vocab_size"] else 0
        cat_values.append(mapped)
    x_cat = np.array(cat_values, dtype=np.int64)

    # Temporal normalization
    if sinr_v3_temporal_mean is not None:
        ae_temporal = (ae_temporal - sinr_v3_temporal_mean) / sinr_v3_temporal_std

    # Land state: zero mode
    x_land = np.zeros(5, dtype=np.float32)

    # Phylo: zero
    x_phylo = np.zeros((1, tvm.PHYLO_DIMS), dtype=np.float32)

    # Location encoding
    loc_enc = tvm.encode_location_sinusoidal(lat, lon)
    x_location = torch.from_numpy(loc_enc).reshape(1, -1)

    # Convert to tensors
    x_cont_t = torch.from_numpy(x_cont).unsqueeze(0)
    x_cat_t = torch.from_numpy(x_cat).unsqueeze(0)
    x_temporal_t = torch.from_numpy(ae_temporal).unsqueeze(0)
    x_land_t = torch.from_numpy(x_land).unsqueeze(0)
    x_phylo_t = torch.from_numpy(x_phylo)

    # === Phase 0A: Expose aux outputs ===
    # === Phase 0B: Two-pass inference (native + introduced, take MAX) ===

    # Pass 1: is_introduced=0.0 (native mode)
    x_intro_native = torch.tensor([[0.0]], dtype=torch.float32)
    logits_native, planted_score_native, land_state_pred_native = sinr_v3_model(
        x_cont_t, x_cat_t, x_intro_native, x_temporal_t, x_land_t, x_phylo_t,
        x_location=x_location,
    )
    probs_native = torch.sigmoid(logits_native).squeeze(0).numpy()

    # Pass 2: is_introduced=1.0 (introduced mode)
    x_intro_introduced = torch.tensor([[1.0]], dtype=torch.float32)
    logits_intro, planted_score_intro, land_state_pred_intro = sinr_v3_model(
        x_cont_t, x_cat_t, x_intro_introduced, x_temporal_t, x_land_t, x_phylo_t,
        x_location=x_location,
    )
    probs_intro = torch.sigmoid(logits_intro).squeeze(0).numpy()

    # Take MAX probability per species across both passes
    probs = np.maximum(probs_native, probs_intro)

    # Extract aux outputs from native pass (planted_score is location-based, same either way)
    planted_score_val = float(torch.sigmoid(planted_score_native).squeeze().mean().item()) if planted_score_native is not None else None
    land_state_pred_val = land_state_pred_native.squeeze().detach().numpy().tolist() if land_state_pred_native is not None else None

    # Top-K results
    top_indices = np.argsort(probs)[::-1][:top_k]
    results = []
    for idx in top_indices:
        taxon_id = sinr_v3_idx_to_species.get(int(idx), f"unknown_{idx}")
        prob_n = float(probs_native[idx])
        prob_i = float(probs_intro[idx])
        best_mode = 'native' if prob_n >= prob_i else 'introduced'
        results.append({
            'taxon_id': taxon_id,
            'probability': round(float(probs[idx]), 6),
            'prob_native': round(prob_n, 6),
            'prob_introduced': round(prob_i, 6),
            'prob_best': round(float(probs[idx]), 6),
            'best_mode': best_mode,
            'rank': len(results) + 1,
        })

    return {
        'predictions': results,
        'aux': {
            'planted_score': round(planted_score_val, 4) if planted_score_val is not None else None,
            'land_state_pred': [round(v, 4) for v in land_state_pred_val] if land_state_pred_val is not None else None,
        },
        'inference_mode': 'two_pass_max',
    }


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

# Load SINR models at import time
sinr_loaded = load_sinr_model()  # v2.2 fallback
sinr_v3_loaded = load_sinr_v3_model()  # v3 primary


if __name__ == '__main__':
    print("\n" + "="*60)
    print("AlphaEarth Location Predictor v6 + SINR v3 (v14 location enc)")
    print("="*60)
    print("Features:")
    print("  - Multi-year AlphaEarth fallback (2023 -> 2017)")
    print("  - SRTM 30m elevation sampling")
    print("  - Hansen Global Forest Change data")
    print("  - WorldClim BIO (19 bioclimatic variables)")
    print("  - OpenLandMap soil (pH, clay, sand, SOC, texture)")
    print("  - 3x3 embedding homogeneity grid (monoculture signal)")
    print("  - Google CCDC change detection (breakpoints)")
    print("  - ETH canopy height variance (10m, 100m radius)")
    print(f"  - SINR v3 neural species prediction (45,247 species, location enc)")
    print("  - SINR v2.2 fallback (35,561 species)")
    print("  - Simulated embedding fallback for demo")
    print("="*60)
    print("Endpoints:")
    print("  GET  /health        - Health check")
    print("  POST /sample        - Get embedding + env data")
    print("  GET  /sample        - Same (query params)")
    print("  POST /sinr-infer    - SINR species prediction (v3 primary, v2.2 fallback)")
    print("  GET  /test-amazon   - Test Amazon locations")
    print("  GET  /test-nz       - Test New Zealand locations")
    print(f"  SINR v3: {'LOADED' if sinr_v3_loaded else 'NOT LOADED'}")
    print(f"  SINR v2.2: {'LOADED' if sinr_loaded else 'NOT LOADED'}")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )
