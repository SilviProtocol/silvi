#!/usr/bin/env python3
"""
Backfill pixel_environmental_bands from BigQuery.

Two sources:
1. phase_c_embeddings_env_v1 (3.96M rows, ~3.4M unique pixels missing env)
2. v4_env_backfill_v1 (1.59M rows, ~829K pixels missing env)

Strategy:
- Export env-only columns from BQ to local parquet (skip embeddings A00-A63)
- Deduplicate to unique (lat4dp, lon4dp, year) pixels
- Filter out pixels already in PG pixel_environmental_bands
- COPY into PG in batches

Machine constraints: 18 GB RAM, 11 CPU cores, ~50 GB free disk
"""

import os
import sys
import time
import io
import tempfile
import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import sql
from google.cloud import bigquery
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it

# ── Config ──────────────────────────────────────────────────────────────
DB_NAME = "treekipedia"
DB_USER = os.environ.get("DB_USER", os.environ.get("USER", "djimoserodio"))
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
BQ_PROJECT = "treekipedia-479918"
BQ_DATASET = "species_data"

# Columns in PG pixel_environmental_bands (excluding 'id' which is SERIAL)
PG_ENV_COLS = [
    "latitude", "longitude", "occurrence_year",
    "elevation", "slope", "aspect", "hillshade",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_texture_class", "soil_bulk_density", "soil_water_content",
    "treecover2000", "loss", "lossyear", "gain",
    "loss_at_obs", "lossyear_at_obs",
    "jrc_forest_type", "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world", "sbtn_natural_land",
    "water_occurrence", "water_recurrence", "water_seasonality",
    "merit_hand_m", "merit_upstream_area_km2",
    "gedi_canopy_height_m", "gedi_foliage_height_div",
    "modis_gpp_mean", "biomass_agb_mgha",
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "eco_id", "biome_num", "topo_diversity",
    "tc_vpd_mean", "tc_aet_mean", "tc_soil_moisture_mean",
    "tc_pdsi_mean", "tc_water_deficit_mean", "tc_solar_rad_mean",
]

# BQ column name mapping (BQ name → PG name)
BQ_TO_PG_RENAME = {
    "emb_year": "occurrence_year",
    "dynamic_world_2023": "dynamic_world",
}

BATCH_SIZE = 500_000  # rows per COPY batch


def get_pg_conn():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)


def get_existing_pixels(conn):
    """Load set of existing (lat4dp, lon4dp, year) from PG to avoid duplicates."""
    print("Loading existing pixel keys from PG...")
    t0 = time.time()
    cur = conn.cursor()
    cur.execute("""
        SELECT round(latitude::numeric, 4)::float, 
               round(longitude::numeric, 4)::float, 
               occurrence_year
        FROM pixel_environmental_bands
    """)
    existing = set()
    for row in cur:
        existing.add((round(float(row[0]), 4), round(float(row[1]), 4), int(row[2])))
    cur.close()
    print(f"  Loaded {len(existing):,} existing pixels in {time.time()-t0:.1f}s")
    return existing


def export_phase_c_env(client):
    """Export Phase C env data from BQ (skip embedding columns A00-A63)."""
    print("\n=== Exporting Phase C env data from BigQuery ===")
    
    # Build SELECT with column renaming
    env_cols_bq = []
    for pg_col in PG_ENV_COLS:
        # Find BQ equivalent
        bq_col = None
        for bq_name, pg_name in BQ_TO_PG_RENAME.items():
            if pg_name == pg_col:
                bq_col = bq_name
                break
        if bq_col is None:
            bq_col = pg_col
        
        # Check if column exists in Phase C (loss_at_obs and lossyear_at_obs don't)
        if pg_col in ("loss_at_obs", "lossyear_at_obs"):
            # These are computed columns: loss before the observation year
            # Phase C is all emb_year=2017, so loss_at_obs = loss AND lossyear <= 2017
            if pg_col == "loss_at_obs":
                env_cols_bq.append("CASE WHEN loss = 1 AND lossyear > 0 AND lossyear <= 17 THEN true ELSE false END AS loss_at_obs")
            else:
                env_cols_bq.append("CASE WHEN loss = 1 AND lossyear > 0 AND lossyear <= 17 THEN CAST(lossyear AS INT64) ELSE 0 END AS lossyear_at_obs")
        elif bq_col != pg_col:
            env_cols_bq.append(f"`{bq_col}` AS `{pg_col}`")
        else:
            env_cols_bq.append(f"`{bq_col}`")
    
    query = f"""
    SELECT {', '.join(env_cols_bq)}
    FROM `{BQ_PROJECT}.{BQ_DATASET}.phase_c_embeddings_env_v1`
    """
    
    print(f"  Running BQ query ({len(PG_ENV_COLS)} columns)...")
    t0 = time.time()
    df = client.query(query).to_dataframe()
    print(f"  Got {len(df):,} rows in {time.time()-t0:.1f}s")
    
    return df


def export_v4_env(client):
    """Export V4 env backfill data from BQ."""
    print("\n=== Exporting V4 env backfill data from BigQuery ===")
    
    # V4 backfill table uses occurrence_year directly (no emb_year rename needed)
    # and dynamic_world (not dynamic_world_2023)
    V4_RENAME = {
        # V4 table already has 'occurrence_year' and 'dynamic_world' matching PG
    }
    
    env_cols_bq = []
    for pg_col in PG_ENV_COLS:
        bq_col = V4_RENAME.get(pg_col, pg_col)  # No renames needed for V4
        
        if pg_col in ("loss_at_obs", "lossyear_at_obs"):
            if pg_col == "loss_at_obs":
                env_cols_bq.append("""
                    CASE WHEN loss = 1 AND lossyear > 0 AND lossyear <= (occurrence_year - 2000)
                    THEN true ELSE false END AS loss_at_obs
                """)
            else:
                env_cols_bq.append("""
                    CASE WHEN loss = 1 AND lossyear > 0 AND lossyear <= (occurrence_year - 2000)
                    THEN CAST(lossyear AS INT64) ELSE 0 END AS lossyear_at_obs
                """)
        elif bq_col != pg_col:
            env_cols_bq.append(f"`{bq_col}` AS `{pg_col}`")
        else:
            env_cols_bq.append(f"`{bq_col}`")
    
    query = f"""
    SELECT {', '.join(env_cols_bq)}
    FROM `{BQ_PROJECT}.{BQ_DATASET}.v4_env_backfill_v1`
    """
    
    print(f"  Running BQ query ({len(PG_ENV_COLS)} columns)...")
    t0 = time.time()
    df = client.query(query).to_dataframe()
    print(f"  Got {len(df):,} rows in {time.time()-t0:.1f}s")
    
    return df


def dedup_and_filter(df, existing_pixels, source_name):
    """Deduplicate to unique pixels and filter out those already in PG."""
    print(f"\n  Deduplicating {source_name}...")
    t0 = time.time()
    
    # Round lat/lon to 4 decimal places
    df["latitude"] = df["latitude"].round(4)
    df["longitude"] = df["longitude"].round(4)
    df["occurrence_year"] = df["occurrence_year"].astype(int)
    
    # Dedup: keep first occurrence per (lat4dp, lon4dp, year)
    before = len(df)
    df = df.drop_duplicates(subset=["latitude", "longitude", "occurrence_year"], keep="first")
    print(f"  Deduped: {before:,} → {len(df):,} unique pixels")
    
    # Filter out pixels already in PG
    print(f"  Filtering against {len(existing_pixels):,} existing PG pixels...")
    mask = df.apply(
        lambda row: (round(row["latitude"], 4), round(row["longitude"], 4), int(row["occurrence_year"])) not in existing_pixels,
        axis=1
    )
    df_new = df[mask].copy()
    print(f"  New pixels to load: {len(df_new):,} (filtered {len(df) - len(df_new):,} existing)")
    print(f"  Dedup+filter took {time.time()-t0:.1f}s")
    
    return df_new


def dedup_and_filter_fast(df, existing_pixels, source_name):
    """Vectorized dedup and filter — much faster than row-by-row apply."""
    print(f"\n  Deduplicating {source_name}...")
    t0 = time.time()
    
    # Round lat/lon to 4 decimal places
    df["latitude"] = df["latitude"].round(4)
    df["longitude"] = df["longitude"].round(4)
    df["occurrence_year"] = df["occurrence_year"].astype(int)
    
    # Dedup: keep first occurrence per (lat4dp, lon4dp, year)
    before = len(df)
    df = df.drop_duplicates(subset=["latitude", "longitude", "occurrence_year"], keep="first")
    print(f"  Deduped: {before:,} → {len(df):,} unique pixels")
    
    # Filter out pixels already in PG using vectorized key construction
    print(f"  Filtering against {len(existing_pixels):,} existing PG pixels...")
    keys = list(zip(df["latitude"].values, df["longitude"].values, df["occurrence_year"].values))
    mask = np.array([k not in existing_pixels for k in keys])
    df_new = df[mask].copy()
    print(f"  New pixels to load: {len(df_new):,} (filtered {len(df) - len(df_new):,} existing)")
    print(f"  Dedup+filter took {time.time()-t0:.1f}s")
    
    return df_new


def cast_types_for_pg(df):
    """Cast DataFrame columns to match PG pixel_environmental_bands types."""
    # Smallint columns: must be int, NaN → None
    smallint_cols = [
        "occurrence_year", "elevation", "soil_texture_class", "treecover2000",
        "lossyear", "lossyear_at_obs", "jrc_forest_type", "jrc_tmf_status",
        "jrc_tmf_degrad_year", "esa_worldcover_2021", "dynamic_world",
        "sbtn_natural_land", "eco_id", "biome_num",
    ]
    for col in smallint_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # Clip to smallint range and convert
            df[col] = df[col].clip(-32768, 32767)
            df[col] = df[col].where(df[col].notna(), other=np.nan)
            # Convert to nullable Int16
            df[col] = df[col].round(0).astype("Int16")
    
    # Boolean columns: 0/1/NaN → False/True/None
    bool_cols = ["loss", "gain", "loss_at_obs"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else bool(int(x)))
    
    return df


def load_to_pg(conn, df, source_name):
    """COPY dataframe into pixel_environmental_bands using fast CSV COPY."""
    if len(df) == 0:
        print(f"  No new rows to load from {source_name}")
        return 0
    
    print(f"\n  Casting types for PG compatibility...")
    df = cast_types_for_pg(df)
    
    print(f"  Loading {len(df):,} rows from {source_name} into PG...")
    t0 = time.time()
    total_loaded = 0
    
    cur = conn.cursor()
    
    # Process in batches
    n_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(n_batches):
        batch = df.iloc[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        
        # Build CSV buffer for COPY
        buf = io.StringIO()
        # Ensure column order matches PG_ENV_COLS
        batch_ordered = batch[PG_ENV_COLS]
        batch_ordered.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        
        copy_sql = sql.SQL("COPY pixel_environmental_bands ({}) FROM STDIN WITH (FORMAT csv, NULL '\\N')").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in PG_ENV_COLS)
        )
        
        cur.copy_expert(copy_sql.as_string(conn), buf)
        conn.commit()
        total_loaded += len(batch)
        
        elapsed = time.time() - t0
        rate = total_loaded / elapsed if elapsed > 0 else 0
        print(f"    Batch {i+1}/{n_batches}: {total_loaded:,} loaded ({rate:,.0f} rows/s)")
    
    cur.close()
    print(f"  Loaded {total_loaded:,} rows in {time.time()-t0:.1f}s")
    return total_loaded


def main():
    print("=" * 70)
    print("Backfill pixel_environmental_bands from BigQuery")
    print("=" * 70)
    
    # Connect to PG and BQ
    conn = get_pg_conn()
    client = bigquery.Client(project=BQ_PROJECT)
    
    # Load existing pixels to avoid duplicates
    existing_pixels = get_existing_pixels(conn)
    
    total_loaded = 0
    
    # ── Phase C ──────────────────────────────────────────────────────────
    df_c = export_phase_c_env(client)
    df_c_new = dedup_and_filter_fast(df_c, existing_pixels, "Phase C")
    
    if len(df_c_new) > 0:
        loaded = load_to_pg(conn, df_c_new, "Phase C")
        total_loaded += loaded
        # Update existing set for V4 dedup
        for _, row in df_c_new[["latitude", "longitude", "occurrence_year"]].iterrows():
            existing_pixels.add((round(row["latitude"], 4), round(row["longitude"], 4), int(row["occurrence_year"])))
        del df_c_new  # free memory
    del df_c  # free memory
    
    # ── V4 Backfill ──────────────────────────────────────────────────────
    df_v4 = export_v4_env(client)
    df_v4_new = dedup_and_filter_fast(df_v4, existing_pixels, "V4 Backfill")
    
    if len(df_v4_new) > 0:
        loaded = load_to_pg(conn, df_v4_new, "V4 Backfill")
        total_loaded += loaded
    del df_v4, df_v4_new
    
    # ── Verify ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Verification")
    print("=" * 70)
    
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM pixel_environmental_bands")
    total_env = cur.fetchone()[0]
    
    cur.execute("""
        SELECT count(DISTINCT e.id) 
        FROM species_occurrence_embeddings e
        JOIN pixel_environmental_bands p
          ON round(e.latitude::numeric, 4) = round(p.latitude::numeric, 4)
          AND round(e.longitude::numeric, 4) = round(p.longitude::numeric, 4)
          AND e.emb_year = p.occurrence_year
    """)
    joinable = cur.fetchone()[0]
    
    cur.execute("SELECT count(*) FROM species_occurrence_embeddings")
    total_emb = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"  Total env rows: {total_env:,}")
    print(f"  Joinable embeddings: {joinable:,} / {total_emb:,} ({100*joinable/total_emb:.1f}%)")
    print(f"  New rows loaded this run: {total_loaded:,}")
    print("\nDone!")


if __name__ == "__main__":
    main()
