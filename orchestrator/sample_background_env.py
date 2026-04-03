#!/usr/bin/env python3
"""
Sample random background points with both AlphaEarth embeddings AND environmental
variables from GEE. These points provide unbiased global coverage to complement
the forest-biased GBIF occurrence data in the SINR training tables.

The combined dataset (GBIF occurrences + random backgrounds) trains a better
AE → Env decoder that works across all terrestrial environments.

Strategy:
  - Uniform random lat/lon sampling within land areas
  - Uses a simple land mask (ESA WorldCover ≠ water) to skip ocean points
  - Samples AE embeddings from AlphaEarth COGs via GEE
  - Samples all env variables via the same GEE stack as SINR training
  - Outputs parquet file compatible with train_ae_env_decoder.py

Usage:
  # Sample 2M random land points (will take hours due to GEE rate limits)
  python3 sample_background_env.py --n-points 2000000 --batch-size 500 --output background_env_2m.parquet

  # Quick test with 1000 points
  python3 sample_background_env.py --n-points 1000 --batch-size 100 --output background_test.parquet

  # Resume from checkpoint
  python3 sample_background_env.py --n-points 2000000 --resume background_env_2m_checkpoint.parquet
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# ─── Constants ────────────────────────────────────────────────────────────────

AE_COLS = [f"emb_{i:02d}" for i in range(64)]

ENV_CONTINUOUS_COLS = [
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    "treecover2000", "lossyear", "biomass_agb_mgha",
    "water_occurrence", "water_recurrence", "water_seasonality",
    "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world",
    "sbtn_natural_land", "neumann_natural_prob",
    "tc_vpd_mean", "tc_vpd_delta", "tc_aet_mean",
    "tc_soil_moisture_mean", "tc_pdsi_mean",
    "tc_water_deficit_mean", "tc_solar_rad_mean",
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "modis_gpp_mean",
]

CATEGORICAL_COLS = [
    "jrc_forest_type", "xiao_planted_forest", "biome_num", "soil_texture_class",
]


def init_ee():
    """Initialize Earth Engine."""
    import ee
    try:
        ee.Initialize(project="treekipedia-479918")
        print("Earth Engine initialized")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project="treekipedia-479918")


def generate_random_land_points(n_points: int, seed: int = 42) -> list[tuple[float, float]]:
    """
    Generate random lat/lon points biased toward land areas.

    Uses rejection sampling with approximate land fraction by latitude band.
    Not perfectly uniform but much better than pure random (70% would hit ocean).
    """
    rng = np.random.RandomState(seed)

    # Over-generate to account for ocean rejection (~30% land surface)
    # Also apply cosine weighting for latitude (equal-area sampling)
    points = []
    batch_multiplier = 4  # generate 4x to account for ocean

    while len(points) < n_points:
        n_gen = min((n_points - len(points)) * batch_multiplier, 500000)

        # Latitude: cosine-weighted for equal area
        # P(lat) ∝ cos(lat) — sample via inverse CDF
        u = rng.uniform(0, 1, n_gen)
        lats = np.degrees(np.arcsin(2 * u - 1))

        # Longitude: uniform
        lons = rng.uniform(-180, 180, n_gen)

        # Simple land mask: reject obvious ocean points
        # Antarctica below -60, most of Pacific between 150-240 at tropics, etc.
        for lat, lon in zip(lats, lons):
            if len(points) >= n_points:
                break
            # Skip deep ocean / antarctica (crude filter — GEE will do the real check)
            if lat < -60:
                continue  # Antarctica
            if lat > 83:
                continue  # Arctic ocean
            points.append((round(float(lat), 4), round(float(lon), 4)))

    return points[:n_points]


def build_env_image(year: int = 2023):
    """Build the same multi-band env stack used for SINR training."""
    import ee

    # ── SRTM Terrain ──
    srtm = ee.Image("USGS/SRTMGL1_003").select("elevation")
    slope = ee.Terrain.slope(srtm)
    aspect = ee.Terrain.aspect(srtm)
    hillshade = ee.Terrain.hillshade(srtm)

    # Topographic diversity (terrain ruggedness)
    topo_div = srtm.reduceNeighborhood(
        reducer=ee.Reducer.stdDev(),
        kernel=ee.Kernel.circle(radius=500, units="meters")
    ).rename("topo_diversity")

    # ── MERIT Hydro ──
    merit = ee.Image("MERIT/Hydro/v1_0_1")
    merit_hand = merit.select("hnd").rename("merit_hand_m")
    merit_upstream = merit.select("upa").rename("merit_upstream_area_km2")

    # ── WorldClim ──
    bio = ee.Image("WORLDCLIM/V2/BIO")
    bio_bands = bio.select([f"bio{i:02d}" for i in range(1, 20)])

    # ── Soil (OpenLandMap) ──
    soil_ph = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02").select("b0").rename("soil_ph")
    soil_clay = ee.Image("OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02").select("b0").rename("soil_clay_pct")
    soil_sand = ee.Image("OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02").select("b0").rename("soil_sand_pct")
    soil_oc = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02").select("b0").rename("soil_organic_carbon")
    soil_bd = ee.Image("OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02").select("b0").rename("soil_bulk_density")
    soil_wc = ee.Image("OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01").select("b0").rename("soil_water_content")
    soil_tex = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select("b0").rename("soil_texture_class")

    # ── Hansen ──
    hansen = ee.Image("UMD/hansen/global_forest_change_2023_v1_11")
    treecover = hansen.select("treecover2000")
    lossyear = hansen.select("lossyear")

    # ── Biomass ──
    biomass = ee.ImageCollection("NASA/ORNL/biomass_carbon_density/v1").first()
    agb = biomass.select("agb").rename("biomass_agb_mgha")

    # ── Water ──
    water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    water_occ = water.select("occurrence").rename("water_occurrence")
    water_rec = water.select("recurrence").rename("water_recurrence")
    water_sea = water.select("seasonality").rename("water_seasonality")

    # ── JRC TMF ──
    jrc_tmf = ee.ImageCollection("JRC/TMF/v1_2022/TransitionMap_Subtypes")
    jrc_main = jrc_tmf.first().select("Value").rename("jrc_tmf_status")
    jrc_degrad = ee.ImageCollection("JRC/TMF/v1_2022/DegradationYear").first().select("Value").rename("jrc_tmf_degrad_year")

    # ── Land cover ──
    esa = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").rename("esa_worldcover_2021")
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate(f"{year}-01-01", f"{year}-12-31").mode().select("label").rename("dynamic_world")
    sbtn = ee.Image("projects/sat-io/open-datasets/SBTN/SBTN_Natural_Lands_Map_20240307").rename("sbtn_natural_land")

    # ── Forest type / origin ──
    neumann = ee.Image("projects/JRC/TMF/v1_2022/NaturalForestProbability").rename("neumann_natural_prob")
    xiao = ee.Image("users/resourcewatch/for_plantations_2021").select("b1").rename("xiao_planted_forest")
    jrc_ft = ee.Image("JRC/GFC2020/V2").select("Map").rename("jrc_forest_type")

    # ── TerraClimate ──
    tc = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterDate(f"{year}-01-01", f"{year}-12-31")
    tc_vpd = tc.select("vpd").mean().rename("tc_vpd_mean")
    tc_vpd_delta = tc.select("vpd").reduce(ee.Reducer.stdDev()).rename("tc_vpd_delta")
    tc_aet = tc.select("aet").mean().rename("tc_aet_mean")
    tc_sm = tc.select("soil").mean().rename("tc_soil_moisture_mean")
    tc_pdsi = tc.select("pdsi").mean().rename("tc_pdsi_mean")
    tc_def = tc.select("def").mean().rename("tc_water_deficit_mean")
    tc_srad = tc.select("srad").mean().rename("tc_solar_rad_mean")

    # ── Human / disturbance ──
    human_mod = ee.ImageCollection("CSP/HM/GlobalHumanModification").first().select("gHM").rename("human_modification")
    nightlights = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG").filterDate(f"{year}-01-01", f"{year}-12-31").mean().select("avg_rad").rename("nighttime_lights")
    fire = ee.ImageCollection("MODIS/061/MCD64A1").filterDate("2001-01-01", f"{year}-12-31").select("BurnDate").reduce(ee.Reducer.count()).rename("fire_frequency_count")
    modis_gpp = ee.ImageCollection("MODIS/061/MOD17A2H").filterDate(f"{year}-01-01", f"{year}-12-31").select("Gpp").mean().rename("modis_gpp_mean")

    # ── Biome ──
    ecoregions = ee.FeatureCollection("RESOLVE/ECOREGIONS/2017")
    biome_img = ecoregions.reduceToImage(properties=["BIOME_NUM"], reducer=ee.Reducer.first()).rename("biome_num")
    eco_img = ecoregions.reduceToImage(properties=["ECO_ID"], reducer=ee.Reducer.first()).rename("eco_id")

    # Stack all bands
    stack = (srtm.rename("elevation")
             .addBands(slope).addBands(aspect).addBands(hillshade).addBands(topo_div)
             .addBands(merit_hand).addBands(merit_upstream)
             .addBands(bio_bands)
             .addBands(soil_ph).addBands(soil_clay).addBands(soil_sand)
             .addBands(soil_oc).addBands(soil_bd).addBands(soil_wc).addBands(soil_tex)
             .addBands(treecover).addBands(lossyear).addBands(agb)
             .addBands(water_occ).addBands(water_rec).addBands(water_sea)
             .addBands(jrc_main).addBands(jrc_degrad)
             .addBands(esa).addBands(dw).addBands(sbtn)
             .addBands(neumann).addBands(xiao).addBands(jrc_ft)
             .addBands(tc_vpd).addBands(tc_vpd_delta).addBands(tc_aet)
             .addBands(tc_sm).addBands(tc_pdsi).addBands(tc_def).addBands(tc_srad)
             .addBands(human_mod).addBands(nightlights).addBands(fire).addBands(modis_gpp)
             .addBands(biome_img).addBands(eco_img)
             )

    return stack


def sample_ae_embedding(lat: float, lon: float, year: int = 2023):
    """Sample 64D AlphaEarth embedding at a point."""
    import ee

    point = ee.Geometry.Point(lon, lat)
    for try_year in [year, year - 1, year - 2, year + 1, 2021, 2020, 2019]:
        try:
            ae_image = ee.Image(f"projects/sat-io/open-datasets/AlphaEarth/v1/{try_year}")
            bands = [f"b{i}" for i in range(64)]
            result = ae_image.select(bands).sample(region=point, scale=10, numPixels=1).first().getInfo()
            if result and "properties" in result:
                props = result["properties"]
                return {f"emb_{i:02d}": props.get(f"b{i}", None) for i in range(64)}
        except Exception:
            continue
    return None


def sample_batch(points: list[tuple[float, float]], env_stack, batch_size: int = 500,
                 year: int = 2023) -> list[dict]:
    """Sample a batch of points using a single getInfo call for env, individual for AE."""
    import ee
    import concurrent.futures

    results = []

    # ── Env: batch sample via FeatureCollection ──
    features = [ee.Feature(ee.Geometry.Point(lon, lat), {"idx": i})
                for i, (lat, lon) in enumerate(points)]
    fc = ee.FeatureCollection(features)

    try:
        sampled = env_stack.sampleRegions(
            collection=fc,
            scale=250,
            geometries=False,
        ).getInfo()
    except Exception as e:
        print(f"    Env batch failed: {e}")
        return []

    if not sampled or "features" not in sampled:
        return []

    env_by_idx = {}
    for feat in sampled["features"]:
        props = feat.get("properties", {})
        idx = props.get("idx")
        if idx is not None:
            env_by_idx[idx] = props

    # ── AE: parallel individual samples ──
    ae_by_idx = {}

    def _sample_ae(idx_lat_lon):
        idx, lat, lon = idx_lat_lon
        try:
            ae = sample_ae_embedding(lat, lon, year)
            return idx, ae
        except Exception:
            return idx, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_sample_ae, (i, lat, lon))
                   for i, (lat, lon) in enumerate(points)]
        for f in concurrent.futures.as_completed(futures):
            idx, ae = f.result()
            if ae is not None:
                ae_by_idx[idx] = ae

    # ── Merge ──
    for i, (lat, lon) in enumerate(points):
        env = env_by_idx.get(i)
        ae = ae_by_idx.get(i)

        if env is None:
            continue  # Ocean point or GEE failure

        # Check if this is a land point (elevation exists)
        if env.get("elevation") is None:
            continue

        row = {"latitude": lat, "longitude": lon}

        # Env continuous
        for col in ENV_CONTINUOUS_COLS:
            row[col] = env.get(col)

        # Env categorical
        for col in CATEGORICAL_COLS:
            row[col] = env.get(col)

        # AE embeddings
        if ae:
            for col in AE_COLS:
                row[col] = ae.get(col)
        else:
            # No AE coverage — still useful for env distribution but skip for decoder training
            for col in AE_COLS:
                row[col] = None

        results.append(row)

    return results


def main():
    parser = argparse.ArgumentParser(description="Sample random background points with AE + Env")
    parser.add_argument("--n-points", type=int, default=100000, help="Target number of valid land points")
    parser.add_argument("--batch-size", type=int, default=500, help="Points per GEE batch")
    parser.add_argument("--output", type=str, default="background_env_samples.parquet")
    parser.add_argument("--resume", type=str, help="Resume from checkpoint parquet")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint-every", type=int, default=5000, help="Save checkpoint every N points")
    args = parser.parse_args()

    import pandas as pd

    init_ee()

    # Generate candidate points
    # Over-generate by 2x to account for ocean/failed points
    print(f"Generating {args.n_points * 2} candidate random points...")
    all_points = generate_random_land_points(args.n_points * 2, seed=args.seed)
    print(f"  Generated {len(all_points)} candidates")

    # Resume from checkpoint
    existing_rows = []
    start_idx = 0
    if args.resume and os.path.exists(args.resume):
        existing_df = pd.read_parquet(args.resume)
        existing_rows = existing_df.to_dict("records")
        start_idx = len(existing_rows)
        print(f"Resuming from checkpoint: {start_idx} existing rows")

    # Build env stack
    print("Building GEE env stack...")
    env_stack = build_env_image(year=args.year)
    print("  Stack ready")

    # Sample in batches
    all_rows = list(existing_rows)
    total_attempted = start_idx
    t0 = time.time()

    remaining_points = all_points[start_idx:]
    batches = [remaining_points[i:i + args.batch_size]
               for i in range(0, len(remaining_points), args.batch_size)]

    for batch_idx, batch_points in enumerate(batches):
        if len(all_rows) >= args.n_points:
            break

        try:
            results = sample_batch(batch_points, env_stack,
                                   batch_size=args.batch_size, year=args.year)
            all_rows.extend(results)
            total_attempted += len(batch_points)

            elapsed = time.time() - t0
            rate = len(all_rows) / elapsed if elapsed > 0 else 0
            eta_min = (args.n_points - len(all_rows)) / rate / 60 if rate > 0 else 0

            print(f"  Batch {batch_idx + 1}/{len(batches)}: "
                  f"{len(results)}/{len(batch_points)} valid | "
                  f"Total: {len(all_rows):,}/{args.n_points:,} | "
                  f"{rate:.1f} pts/sec | ETA: {eta_min:.0f} min")

        except Exception as e:
            print(f"  Batch {batch_idx + 1} error: {e}")
            traceback.print_exc()
            time.sleep(5)
            continue

        # Checkpoint
        if len(all_rows) % args.checkpoint_every < args.batch_size:
            checkpoint_path = args.output.replace(".parquet", "_checkpoint.parquet")
            pd.DataFrame(all_rows).to_parquet(checkpoint_path, index=False)
            print(f"  Checkpoint saved: {checkpoint_path} ({len(all_rows):,} rows)")

    # Save final
    df = pd.DataFrame(all_rows[:args.n_points])
    df.to_parquet(args.output, index=False)

    elapsed = time.time() - t0
    print(f"\nDone! {len(df):,} points saved to {args.output}")
    print(f"  Time: {elapsed / 60:.1f} min")
    print(f"  Land hit rate: {len(df) / total_attempted:.1%}")

    # Quick stats
    ae_valid = df[AE_COLS[0]].notna().sum()
    print(f"  AE coverage: {ae_valid:,}/{len(df):,} ({ae_valid/len(df):.1%})")


if __name__ == "__main__":
    main()
