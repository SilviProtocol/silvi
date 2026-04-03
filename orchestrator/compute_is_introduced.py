#!/usr/bin/env python3
"""
compute_is_introduced.py — Add `is_introduced` column to SINR training parquets.

Approach:
  1. Re-query the original extraction JOIN but only fetch
     (taxon_id, quality_weight, density_weight, embedding_text, env_cols..., tdwg_level3_name)
  2. Compute is_introduced = (tdwg_level3_name NOT IN wcvp_native) per row
  3. Apply the same hard cap, train/val split, species_idx mapping
  4. Save updated parquets with is_introduced column

This is essentially a re-extraction of the training data that adds:
  - tdwg_level3_name (TDWG Level 3 region from spatial join)
  - is_introduced (binary: 1 if species is not native to this TDWG region)

Prerequisites:
  - pixel_environmental_bands.tdwg_level3_name must be populated
    (PostGIS spatial join against tdwg_level3 table)
  - species.wcvp_native in database

Usage:
  python3 compute_is_introduced.py
"""

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "sinr_training_data"

DB_NAME = "treekipedia"
DB_USER = os.environ.get("DB_USER", os.environ.get("USER", "djimoserodio"))
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

HARD_CAP_PER_SPECIES = 50000
VAL_FRACTION = 0.05

# Environmental feature columns (must match train_sinr_model.py)
ENV_FEATURE_COLS = [
    "elevation", "slope", "aspect", "hillshade",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_texture_class", "soil_bulk_density", "soil_water_content",
    "treecover2000", "lossyear",
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


def main():
    print("=" * 70)
    print("RE-EXTRACT TRAINING DATA WITH is_introduced")
    print("=" * 70)

    t0 = time.time()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
    )

    # ── Check TDWG coverage ──────────────────────────────────────────────
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(tdwg_level3_name) as has_tdwg
        FROM pixel_environmental_bands
    """)
    total, has_tdwg = cur.fetchone()
    cur.close()
    print(f"\n  Pixel TDWG coverage: {has_tdwg:,} / {total:,} ({100*has_tdwg/total:.1f}%)")

    if has_tdwg == 0:
        print("  ERROR: No TDWG data! Run the spatial join first:")
        print("    UPDATE pixel_environmental_bands p SET tdwg_level3_name = t.\"LEVEL3_NAM\"")
        print("    FROM tdwg_level3 t WHERE ST_Contains(t.geometry, ...)")
        return

    # ── Load WCVP native ranges ──────────────────────────────────────────
    print("\n  Loading WCVP native ranges...")
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, wcvp_native
        FROM species
        WHERE wcvp_native IS NOT NULL AND wcvp_native != '' AND wcvp_native != 'NA'
    """)
    native_ranges = {}
    for taxon_id, wcvp_native in cur.fetchall():
        regions = {r.strip() for r in wcvp_native.split(";") if r.strip()}
        native_ranges[taxon_id] = regions
    cur.close()
    print(f"    {len(native_ranges):,} species with native range data")

    # ── Load existing species mapping (don't recompute) ──────────────────
    mapping_path = DATA_DIR / "species_mapping.json"
    with open(mapping_path) as f:
        mapping = json.load(f)
    species_to_idx = mapping["species_to_idx"]
    num_species = mapping["num_species"]
    print(f"  Using existing species mapping: {num_species:,} species")

    # ── Extract data with TDWG region ────────────────────────────────────
    print("\n  Extracting features + TDWG region from PostgreSQL...")
    env_select = ", ".join([f"p.{col}" for col in ENV_FEATURE_COLS])

    query = f"""
        SELECT
            e.taxon_id,
            e.quality_weight,
            e.density_weight,
            e.embedding::text as embedding_text,
            {env_select},
            p.tdwg_level3_name
        FROM species_occurrence_embeddings e
        JOIN pixel_environmental_bands p
            ON round(e.latitude::numeric, 4) = round(p.latitude::numeric, 4)
            AND round(e.longitude::numeric, 4) = round(p.longitude::numeric, 4)
            AND e.emb_year = p.occurrence_year
    """

    print("  Running extraction query (this takes several minutes)...")
    cur = conn.cursor("extraction_cursor")
    cur.itersize = 100_000
    cur.execute(query)

    chunks = []
    total_rows = 0
    chunk_idx = 0
    col_names = None

    while True:
        rows = cur.fetchmany(500_000)
        if not rows:
            break

        if col_names is None:
            col_names = [desc[0] for desc in cur.description]

        df_chunk = pd.DataFrame(rows, columns=col_names)

        # Parse embedding text → 64 float columns
        emb_cols = [f"emb_{i:02d}" for i in range(64)]
        emb_matrix = np.array(
            [np.fromstring(s[1:-1], sep=",", dtype=np.float32)
             for s in df_chunk["embedding_text"].values]
        )
        emb_df = pd.DataFrame(emb_matrix, columns=emb_cols, index=df_chunk.index)
        df_chunk = pd.concat([df_chunk.drop(columns=["embedding_text"]), emb_df], axis=1)

        chunks.append(df_chunk)
        total_rows += len(df_chunk)
        chunk_idx += 1

        elapsed = time.time() - t0
        rate = total_rows / elapsed if elapsed > 0 else 0
        print(f"    Chunk {chunk_idx}: {total_rows:,} rows ({rate:,.0f} rows/s)")

    cur.close()
    conn.close()

    print(f"\n  Concatenating {len(chunks)} chunks...")
    df = pd.concat(chunks, ignore_index=True)
    del chunks

    print(f"  Total extracted: {len(df):,} rows")

    # ── Compute is_introduced (vectorized) ─────────────────────────────────
    print("\n  Computing is_introduced...")

    # Build a resolved native_ranges lookup that handles subspecies
    # For each taxon_id in training data, resolve to its WCVP native range
    resolved_ranges = {}
    for tid in df["taxon_id"].unique():
        native = native_ranges.get(tid)
        # Try subspecies variants if not found directly
        if native is None and "-" in tid:
            base_id = tid.rsplit("-", 1)[0]
            for suffix in ["-00", "-01", "-02", "-03", "-04", "-05"]:
                native = native_ranges.get(base_id + suffix)
                if native is not None:
                    break
        resolved_ranges[tid] = native  # None if no WCVP data

    # Build (taxon_id, tdwg_region) → is_introduced lookup
    # Get all unique (taxon_id, tdwg_region) pairs
    pair_df = df[["taxon_id", "tdwg_level3_name"]].drop_duplicates()
    print(f"    Unique (taxon_id, TDWG region) pairs: {len(pair_df):,}")

    pair_results = {}
    n_native, n_intro, n_unk = 0, 0, 0
    for _, row in pair_df.iterrows():
        tid = row["taxon_id"]
        tdwg = row["tdwg_level3_name"]

        if pd.isna(tdwg) or tdwg == "":
            pair_results[(tid, tdwg)] = -1
            n_unk += 1
            continue

        native = resolved_ranges.get(tid)
        if native is None:
            pair_results[(tid, tdwg)] = -1
            n_unk += 1
        elif tdwg in native:
            pair_results[(tid, tdwg)] = 0
            n_native += 1
        else:
            pair_results[(tid, tdwg)] = 1
            n_intro += 1

    print(f"    Unique pairs: {n_native:,} native, {n_intro:,} introduced, {n_unk:,} unknown")

    # Map back to full dataframe
    is_introduced = np.array(
        [pair_results.get((t, r), -1)
         for t, r in zip(df["taxon_id"].values, df["tdwg_level3_name"].values)],
        dtype=np.int8,
    )
    df["is_introduced"] = is_introduced

    # Stats
    n_native = (is_introduced == 0).sum()
    n_introduced = (is_introduced == 1).sum()
    n_unknown = (is_introduced == -1).sum()
    print(f"    Native (0): {n_native:,} ({100*n_native/len(df):.1f}%)")
    print(f"    Introduced (1): {n_introduced:,} ({100*n_introduced/len(df):.1f}%)")
    print(f"    Unknown (-1): {n_unknown:,} ({100*n_unknown/len(df):.1f}%)")

    # Drop tdwg_level3_name (not a training feature)
    df = df.drop(columns=["tdwg_level3_name"])

    # ── Apply hard cap ───────────────────────────────────────────────────
    if HARD_CAP_PER_SPECIES:
        before = len(df)
        df = df.groupby("taxon_id", group_keys=False).apply(
            lambda g: g.sample(n=min(len(g), HARD_CAP_PER_SPECIES), random_state=42)
        )
        df = df.reset_index(drop=True)
        print(f"\n  Hard cap {HARD_CAP_PER_SPECIES}/species: {before:,} → {len(df):,}")

    # ── Species index ────────────────────────────────────────────────────
    df["species_idx"] = df["taxon_id"].map(species_to_idx)
    unmapped = df["species_idx"].isna().sum()
    if unmapped > 0:
        print(f"  WARNING: {unmapped:,} rows have unmapped taxon_ids (dropping)")
        df = df.dropna(subset=["species_idx"])
    df["species_idx"] = df["species_idx"].astype(int)

    # ── Train/val split (same random seed as original) ───────────────────
    print(f"\n  Splitting train/val ({1-VAL_FRACTION:.0%}/{VAL_FRACTION:.0%})...")
    np.random.seed(42)
    val_mask = np.random.rand(len(df)) < VAL_FRACTION
    df_train = df[~val_mask].reset_index(drop=True)
    df_val = df[val_mask].reset_index(drop=True)
    print(f"  Train: {len(df_train):,} rows")
    print(f"  Val:   {len(df_val):,} rows")

    # ── is_introduced stats for train set ────────────────────────────────
    train_intro = df_train["is_introduced"]
    print(f"\n  Train set is_introduced distribution:")
    print(f"    Native (0): {(train_intro == 0).sum():,}")
    print(f"    Introduced (1): {(train_intro == 1).sum():,}")
    print(f"    Unknown (-1): {(train_intro == -1).sum():,}")

    # ── Save to parquet ──────────────────────────────────────────────────
    # Back up old parquets
    train_path = DATA_DIR / "train.parquet"
    val_path = DATA_DIR / "val.parquet"

    if train_path.exists():
        backup = DATA_DIR / "train_v1_no_introduced.parquet"
        if not backup.exists():
            print(f"\n  Backing up old train.parquet → {backup.name}")
            train_path.rename(backup)
    if val_path.exists():
        backup = DATA_DIR / "val_v1_no_introduced.parquet"
        if not backup.exists():
            print(f"  Backing up old val.parquet → {backup.name}")
            val_path.rename(backup)

    df_train.to_parquet(train_path, index=False)
    df_val.to_parquet(val_path, index=False)

    elapsed = time.time() - t0
    print(f"\n  Saved to {DATA_DIR}/")
    print(f"  Train: {train_path} ({train_path.stat().st_size / 1e9:.2f} GB)")
    print(f"  Val:   {val_path} ({val_path.stat().st_size / 1e9:.2f} GB)")
    print(f"  Total time: {elapsed/60:.1f} min")

    # ── Save stats ───────────────────────────────────────────────────────
    stats = {
        "train_rows": len(df_train),
        "val_rows": len(df_val),
        "train_native": int((df_train["is_introduced"] == 0).sum()),
        "train_introduced": int((df_train["is_introduced"] == 1).sum()),
        "train_unknown": int((df_train["is_introduced"] == -1).sum()),
        "val_native": int((df_val["is_introduced"] == 0).sum()),
        "val_introduced": int((df_val["is_introduced"] == 1).sum()),
        "val_unknown": int((df_val["is_introduced"] == -1).sum()),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(DATA_DIR / "is_introduced_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print("\n  Done!")


if __name__ == "__main__":
    main()
