#!/usr/bin/env python3
"""
train_sinr_model.py — Train a SINR-style species prediction model.

Architecture: ResidualFCNet v2.2 (Cole et al., ICML 2023 + Silvi modifications)
  - Entity embeddings for categoricals (jrc, xiao, eco_id, biome, soil)
  - Gated fusion: 4D gate (jrc_emb + is_introduced) → α blends satellite vs env
  - Planted logit boost: planted_score × species_intro_ratio × learned_scale
  - Subspecies merged into parent species during data extraction
  - Auxiliary planted-score head (weakly supervised)

Loss: Assumed-Negative Binary Cross-Entropy (an_full)
  - For observed species: BCE positive loss (weighted by pos_weight)
  - For all other species: assumed absent (negative loss)
  - Random background locations: all species assumed absent
  - Aux loss: BCE on planted_score (10% weight)

Training data: species_occurrence_embeddings JOIN pixel_environmental_bands
  - 64-D AlphaEarth embedding + 61 env variables = 125 features
  - ~8.6M rows, ~43K species (after subspecies merge)

Usage:
  # Step 1: Extract training data from PostgreSQL to parquet
  python3 train_sinr_model.py --extract-data

  # Step 2: Train the model
  python3 train_sinr_model.py --train

  # Step 3: Evaluate
  python3 train_sinr_model.py --evaluate

  # All steps:
  python3 train_sinr_model.py --extract-data --train --evaluate
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "sinr_training_data"
MODEL_DIR = SCRIPT_DIR / "sinr_model"

DB_NAME = "treekipedia"
DB_USER = os.environ.get("DB_USER", os.environ.get("USER", "djimoserodio"))
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Feature columns: 64 AlphaEarth embedding dims + env variables
# AlphaEarth bands are stored as vector(64) in PG, needs special extraction
#
# CATEGORICAL features (entity embeddings in v2) are listed separately.
# They get nn.Embedding layers instead of z-score normalization.
# CONTINUOUS features get z-score normalization as before.

# Categorical features: column → {vocab_size, emb_dim, value_map}
# value_map remaps raw DB integers to contiguous 0..n indices.
# Index 0 is reserved for unknown/unseen values.
CATEGORICAL_FEATURES = {
    "jrc_forest_type": {
        "vocab_size": 5,   # 0=unknown, 1=no_forest(raw 0), 2=natural(raw 1), 3=primary(raw 10), 4=planted(raw 20)
        "emb_dim": 3,
        "value_map": {0: 1, 1: 2, 10: 3, 20: 4},  # raw_value → index (0 reserved for unknown)
    },
    "xiao_planted_forest": {
        "vocab_size": 4,   # 0=unknown/NULL, 1=non-forest(raw 0), 2=natural(raw 1), 3=planted(raw 2)
        "emb_dim": 3,
        "value_map": {0: 1, 1: 2, 2: 3},  # raw_value → index (0 reserved for unknown/NULL)
    },
    "eco_id": {
        "vocab_size": 850,  # 0=unknown, 1-849 for eco_ids (max observed: 846, +margin)
        "emb_dim": 32,
        "value_map": None,  # Identity mapping (eco_id values are already 0-846); 0 → stays 0 (unknown)
    },
    "biome_num": {
        "vocab_size": 16,  # 0=unknown, 1-14 for biomes, +1 margin
        "emb_dim": 8,
        "value_map": None,  # Identity mapping (values 1-14)
    },
    "soil_texture_class": {
        "vocab_size": 14,  # 0=unknown, 1-12 for soil classes, +1 margin
        "emb_dim": 6,
        "value_map": None,  # Identity mapping (values 1-12)
    },
}

# Features that feed into the gate MLP (plantation-awareness signals)
# v2.2: Reverted to jrc_forest_type only. Xiao/neumann are too noisy for the gate
# (only 24% of P.radiata labeled "planted" by Xiao, 39% labeled "natural").
# These features remain in the env branch as regular features.
GATE_FEATURES = ["jrc_forest_type"]

CATEGORICAL_COLS = list(CATEGORICAL_FEATURES.keys())
TOTAL_EMB_DIM = sum(cf["emb_dim"] for cf in CATEGORICAL_FEATURES.values())  # 3+32+8+6 = 49

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
    "xiao_planted_forest", "neumann_natural_prob",
]

# Continuous env features = all env features MINUS the categorical ones
ENV_CONTINUOUS_COLS = [c for c in ENV_FEATURE_COLS if c not in CATEGORICAL_COLS]

# Training hyperparameters
BATCH_SIZE = 2048
NUM_EPOCHS = 12
LEARNING_RATE = 0.0005
LR_DECAY = 0.98  # ExponentialLR gamma
POS_WEIGHT = 2048.0  # Compensates for 1 positive vs ~44K assumed negatives
DROPOUT = 0.3
HIDDEN_DIM = 256
NUM_RES_BLOCKS = 4
HARD_CAP_PER_SPECIES = 50000  # Max training samples per species (prevent dominance)
VAL_FRACTION = 0.05  # 5% held out for validation
BG_WEIGHT = 1.0  # Weight for background (random location) loss
NUM_WORKERS = 4  # DataLoader workers


# ── Step 1: Data Extraction ──────────────────────────────────────────────────

def extract_training_data():
    """Extract joined embeddings + env data + is_introduced from PostgreSQL to parquet.

    Produces complete v2.1 parquets with all columns:
      - 64 AlphaEarth embedding dims
      - All ENV_FEATURE_COLS (including xiao_planted_forest, neumann_natural_prob)
      - is_introduced (computed from TDWG L3 spatial join + WCVP native ranges)
      - taxon_id, quality_weight, density_weight, species_idx
    """
    import psycopg2

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("STEP 1: EXTRACT TRAINING DATA (v2.1)")
    print("=" * 70)

    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
    )

    # ── 1a. Get species → index mapping ──────────────────────────────────
    print("\n  Building species index...")
    cur = conn.cursor()
    cur.execute("""
        SELECT taxon_id, count(*) as n
        FROM species_occurrence_embeddings e
        WHERE EXISTS (
            SELECT 1 FROM pixel_environmental_bands p
            WHERE round(e.latitude::numeric, 4) = round(p.latitude::numeric, 4)
            AND round(e.longitude::numeric, 4) = round(p.longitude::numeric, 4)
            AND e.emb_year = p.occurrence_year
        )
        GROUP BY taxon_id
        ORDER BY taxon_id
    """)
    species_rows = cur.fetchall()
    cur.close()

    # v2.2: Merge subspecies into parent species
    # Taxon IDs like GymPiPiPnCx50820-01, -02, -03 → GymPiPiPnCx50820-00
    # This concentrates probability into a single output instead of splitting across
    # multiple sigmoid outputs (e.g., P. radiata had 4 outputs: 7917+23+18+10 rows)
    raw_counts = {}
    for taxon_id, count in species_rows:
        raw_counts[taxon_id] = count

    # Build merge map: subspecies → parent (-00)
    subspecies_merge = {}  # maps subspecies taxon_id → parent taxon_id
    merged_count = 0
    for taxon_id in raw_counts:
        if "-" in taxon_id:
            base, suffix = taxon_id.rsplit("-", 1)
            if suffix != "00" and suffix.isdigit():
                parent = base + "-00"
                if parent in raw_counts:
                    subspecies_merge[taxon_id] = parent
                    merged_count += 1

    if merged_count > 0:
        print(f"  Subspecies merge: {merged_count:,} subspecies → parent species")

    # Build merged species counts
    species_counts_merged = {}
    for taxon_id, count in raw_counts.items():
        target = subspecies_merge.get(taxon_id, taxon_id)
        species_counts_merged[target] = species_counts_merged.get(target, 0) + count

    species_to_idx = {}
    species_counts = {}
    for taxon_id in sorted(species_counts_merged.keys()):
        idx = len(species_to_idx)
        species_to_idx[taxon_id] = idx
        species_counts[taxon_id] = species_counts_merged[taxon_id]

    num_species = len(species_to_idx)
    print(f"  Total species after merge: {num_species:,} (was {len(raw_counts):,})")
    print(f"  Total training rows: {sum(species_counts.values()):,}")

    # Save species mapping (includes subspecies merge info for inference)
    mapping_path = DATA_DIR / "species_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump({
            "species_to_idx": species_to_idx,
            "species_counts": species_counts,
            "num_species": num_species,
            "subspecies_merge": subspecies_merge,  # e.g., "-01" → "-00"
        }, f)
    print(f"  Saved species mapping to {mapping_path}")

    # ── 1b. Load WCVP native ranges for is_introduced computation ────────
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

    # ── 1c. Extract features in batches ──────────────────────────────────
    print("\n  Extracting features from PostgreSQL...")
    print(f"  Features: 64 AlphaEarth dims + {len(ENV_FEATURE_COLS)} env vars + tdwg_level3_name")

    # Extract embedding as text (vector→text), parse in Python for speed
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

    print(f"  Running query (this may take several minutes)...")
    t0 = time.time()

    # Use server-side cursor for memory efficiency
    cur = conn.cursor("training_data_cursor")
    cur.itersize = 100_000
    cur.execute(query)

    # Read in chunks
    chunks = []
    total_rows = 0
    chunk_idx = 0
    col_names = None

    while True:
        rows = cur.fetchmany(500_000)
        if not rows:
            break

        # Get column names from cursor description (available after first fetch)
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

    print(f"  Total extracted: {len(df):,} rows, {df.shape[1]} columns")

    # ── 1c2. Apply subspecies merge to taxon_id ─────────────────────────
    if subspecies_merge:
        before_unique = df["taxon_id"].nunique()
        df["taxon_id"] = df["taxon_id"].map(
            lambda tid: subspecies_merge.get(tid, tid)
        )
        after_unique = df["taxon_id"].nunique()
        print(f"  Subspecies taxon_id merge: {before_unique:,} → {after_unique:,} unique taxa")

    # ── 1d. Compute is_introduced from TDWG + WCVP ──────────────────────
    print("\n  Computing is_introduced...")

    # Resolve native ranges (handle subspecies variants)
    resolved_ranges = {}
    for tid in df["taxon_id"].unique():
        native = native_ranges.get(tid)
        if native is None and "-" in tid:
            base_id = tid.rsplit("-", 1)[0]
            for suffix in ["-00", "-01", "-02", "-03", "-04", "-05"]:
                native = native_ranges.get(base_id + suffix)
                if native is not None:
                    break
        resolved_ranges[tid] = native  # None if no WCVP data

    # Build (taxon_id, tdwg_region) → is_introduced lookup
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

    n_native_r = (is_introduced == 0).sum()
    n_intro_r = (is_introduced == 1).sum()
    n_unk_r = (is_introduced == -1).sum()
    print(f"    Native (0): {n_native_r:,} ({100*n_native_r/len(df):.1f}%)")
    print(f"    Introduced (1): {n_intro_r:,} ({100*n_intro_r/len(df):.1f}%)")
    print(f"    Unknown (-1): {n_unk_r:,} ({100*n_unk_r/len(df):.1f}%)")

    # Drop tdwg_level3_name (not a training feature, just used for is_introduced)
    df = df.drop(columns=["tdwg_level3_name"])

    # ── 1e. Apply hard cap per species ───────────────────────────────────
    if HARD_CAP_PER_SPECIES:
        before = len(df)
        df = df.groupby("taxon_id", group_keys=False).apply(
            lambda g: g.sample(n=min(len(g), HARD_CAP_PER_SPECIES), random_state=42)
        )
        df = df.reset_index(drop=True)
        print(f"  Hard cap {HARD_CAP_PER_SPECIES}/species: {before:,} → {len(df):,}")

    # ── 1f. Convert taxon_id to integer index ────────────────────────────
    df["species_idx"] = df["taxon_id"].map(species_to_idx)
    unmapped = df["species_idx"].isna().sum()
    if unmapped > 0:
        print(f"  WARNING: {unmapped:,} rows have unmapped taxon_ids (dropping)")
        df = df.dropna(subset=["species_idx"])
    df["species_idx"] = df["species_idx"].astype(int)

    # ── 1g. Train/val split (stratified by species) ──────────────────────
    print(f"\n  Splitting train/val ({1-VAL_FRACTION:.0%}/{VAL_FRACTION:.0%})...")
    np.random.seed(42)
    val_mask = np.random.rand(len(df)) < VAL_FRACTION
    df_train = df[~val_mask].reset_index(drop=True)
    df_val = df[val_mask].reset_index(drop=True)
    print(f"  Train: {len(df_train):,} rows")
    print(f"  Val:   {len(df_val):,} rows")

    # ── 1h. Save to parquet ──────────────────────────────────────────────
    train_path = DATA_DIR / "train.parquet"
    val_path = DATA_DIR / "val.parquet"
    df_train.to_parquet(train_path, index=False)
    df_val.to_parquet(val_path, index=False)

    elapsed = time.time() - t0
    print(f"\n  Saved to {DATA_DIR}/")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Train: {train_path} ({train_path.stat().st_size / 1e9:.2f} GB)")
    print(f"  Val:   {val_path} ({val_path.stat().st_size / 1e9:.2f} GB)")

    # Print column summary
    print(f"\n  Parquet columns ({len(df_train.columns)}):")
    print(f"    Embeddings: emb_00..emb_63 (64)")
    print(f"    Env features: {len(ENV_FEATURE_COLS)} cols")
    print(f"    Categorical: {', '.join(CATEGORICAL_COLS)}")
    print(f"    Flags: is_introduced")
    print(f"    Meta: taxon_id, quality_weight, density_weight, species_idx")


# ── Step 2: SINR Model ──────────────────────────────────────────────────────

def build_model():
    """Build the SINR ResidualFCNet model with entity embeddings (v2)."""
    import torch
    import torch.nn as nn

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
        """
        SINR-style ResidualFCNet for species prediction (v2.1: improved plantation detection).

        Architecture:
          1. ENTITY EMBEDDINGS: Categorical features (jrc_forest_type, xiao_planted_forest,
             eco_id, biome_num, soil_texture_class) → learned embedding vectors.

          2. GATED FUSION: A small MLP gate takes plantation-awareness signals and
             produces α ∈ [0,1]:
               - Inputs: jrc_emb(3D) + is_introduced(1D) = 4D (v2.2: reverted from 8D)
               - Satellite branch: 64D embedding → Linear(fusion_dim)
               - Env branch: continuous env + entity embeddings → Linear(fusion_dim)
               - Fused = α × satellite_proj + (1-α) × env_proj
             At plantation sites with introduced species, α should learn
             to be high → trust satellite visual signature over env features.

          3. RESIDUAL BLOCKS: fused → Linear(hidden_dim) → ReLU → [ResBlock]×N

          4. SPECIES OUTPUT: Linear(num_species) → Sigmoid (in loss)

           5. AUXILIARY HEAD + PLANTED LOGIT BOOST (v2.2):
              - aux_head: Linear(1) off final hidden layer → planted_score = P(planted)
              - Weakly supervised from xiao=planted OR jrc=20
              - Connected to species logits via post-hoc boost:
                logits += planted_score * species_intro_ratio * boost_scale
              - species_intro_ratio: per-species fraction of is_introduced=1 training obs
              - boost_scale: learned scalar (initialized to 2.0)
              - Only boosts introduced species at plantation sites; native species unaffected.
        """

        # Number of AlphaEarth satellite embedding dimensions
        NUM_SAT_DIMS = 64

        def __init__(
            self,
            num_continuous: int,
            num_species: int,
            categorical_config: Optional[Dict] = None,
            hidden_dim: int = 256,
            num_blocks: int = 4,
            dropout: float = 0.3,
            fusion_dim: int = 128,
            use_gate: bool = True,
            use_aux_head: bool = False,
        ):
            super().__init__()
            self.num_continuous = num_continuous
            self.num_species = num_species
            self.categorical_config = categorical_config or {}
            self.use_gate = use_gate
            self.use_aux_head = use_aux_head
            self.fusion_dim = fusion_dim

            # ── Entity embeddings for categorical features ───────────
            self.embeddings = nn.ModuleDict()
            total_emb_dim = 0
            for col_name, cfg in self.categorical_config.items():
                self.embeddings[col_name] = nn.Embedding(
                    num_embeddings=cfg["vocab_size"],
                    embedding_dim=cfg["emb_dim"],
                    padding_idx=0,  # Index 0 = unknown/missing
                )
                total_emb_dim += cfg["emb_dim"]
            self.total_emb_dim = total_emb_dim

            # ── Gated fusion or simple concatenation ─────────────────
            # Continuous features: first NUM_SAT_DIMS are satellite, rest are env
            num_sat = self.NUM_SAT_DIMS
            num_env_continuous = num_continuous - num_sat  # env continuous features

            if use_gate:
                # Satellite branch projection
                self.sat_proj = nn.Sequential(
                    nn.Linear(num_sat, fusion_dim),
                    nn.ReLU(inplace=True),
                )

                # Env branch projection: env continuous + all entity embeddings
                env_input_dim = num_env_continuous + total_emb_dim
                self.env_proj = nn.Sequential(
                    nn.Linear(env_input_dim, fusion_dim),
                    nn.ReLU(inplace=True),
                )

                # Gate MLP: plantation-awareness signals
                # v2.2: Reverted to 4D — jrc_emb(3D) + is_introduced(1D)
                # Xiao/neumann removed from gate (too noisy — only 24% of P.radiata
                # labeled "planted" by Xiao, poisoning gate learning)
                gate_input_dim = 0
                self.gate_cat_features = []
                for gf in GATE_FEATURES:
                    if gf in self.categorical_config:
                        gate_input_dim += self.categorical_config[gf]["emb_dim"]
                        self.gate_cat_features.append(gf)
                gate_input_dim += 1  # is_introduced flag
                self.gate_input_dim = gate_input_dim

                self.gate = nn.Sequential(
                    nn.Linear(gate_input_dim, 16),
                    nn.ReLU(inplace=True),
                    nn.Linear(16, 1),
                    nn.Sigmoid(),
                )

                # Main projection from fused to hidden_dim
                self.input_layer = nn.Sequential(
                    nn.Linear(fusion_dim, hidden_dim),
                    nn.ReLU(inplace=True),
                )
            else:
                # No gate: simple concatenation (like v1 but with embeddings)
                total_input_dim = num_continuous + total_emb_dim
                self.input_layer = nn.Sequential(
                    nn.Linear(total_input_dim, hidden_dim),
                    nn.ReLU(inplace=True),
                )

            # ── Residual blocks ──────────────────────────────────────
            self.res_blocks = nn.Sequential(
                *[ResidualBlock(hidden_dim, dropout) for _ in range(num_blocks)]
            )

            # ── Species output head (no bias, following SINR) ────────
            self.output_layer = nn.Linear(hidden_dim, num_species, bias=False)

            # ── Auxiliary "is_planted" head + logit boost (v2.2) ────
            if use_aux_head:
                self.aux_head = nn.Linear(hidden_dim, 1)
                # Learned boost scale: how much to boost introduced species at plantations
                # Initialized to 2.0 (moderate boost in logit space ≈ sigmoid shift)
                self.boost_scale = nn.Parameter(torch.tensor(2.0))
                # Per-species introduced ratio: registered as buffer (not trained by gradient)
                # Set externally via set_species_intro_ratio() before training
                self.register_buffer(
                    "species_intro_ratio",
                    torch.zeros(num_species),  # (num_species,)
                )

        def forward(self, x_continuous, x_categorical=None, x_is_introduced=None):
            """
            Returns raw logits (pre-sigmoid).

            Args:
                x_continuous: (batch, num_continuous) float tensor
                    First 64 dims = satellite embedding, rest = env continuous
                x_categorical: (batch, num_cat_features) long tensor
                x_is_introduced: (batch, 1) float tensor — the is_introduced flag
                    Values: 0=native, 1=introduced, 0.5 for unknown(-1)

            Returns:
                logits: (batch, num_species) — species prediction logits
                aux_logits: (batch, 1) — plantation prediction logits (if use_aux_head)
            """
            # ── Compute entity embeddings ────────────────────────────
            cat_embs = {}
            cat_emb_list = []
            if x_categorical is not None and len(self.embeddings) > 0:
                for i, col_name in enumerate(self.categorical_config.keys()):
                    cat_indices = x_categorical[:, i]  # (batch,)
                    emb = self.embeddings[col_name](cat_indices)  # (batch, emb_dim)
                    cat_embs[col_name] = emb
                    cat_emb_list.append(emb)

            if self.use_gate:
                # ── Gated fusion ─────────────────────────────────────
                batch_size = x_continuous.shape[0]

                # Split continuous into satellite and env
                x_sat = x_continuous[:, :self.NUM_SAT_DIMS]  # (batch, 64)
                x_env_cont = x_continuous[:, self.NUM_SAT_DIMS:]  # (batch, num_env)

                # Project satellite and env branches
                sat_h = self.sat_proj(x_sat)  # (batch, fusion_dim)
                env_parts = [x_env_cont] + cat_emb_list
                env_input = torch.cat(env_parts, dim=1)
                env_h = self.env_proj(env_input)  # (batch, fusion_dim)

                # Compute gate α from plantation signals + is_introduced
                # v2.2: Only jrc_emb(3D) + is_introduced(1D) = 4D
                gate_parts = []
                for gf in self.gate_cat_features:
                    emb = cat_embs.get(gf,
                        torch.zeros(batch_size, self.categorical_config[gf]["emb_dim"],
                                    device=x_continuous.device))
                    gate_parts.append(emb)

                if x_is_introduced is None:
                    is_intro = torch.full((batch_size, 1), 0.5, device=x_continuous.device)
                else:
                    is_intro = x_is_introduced  # (batch, 1)
                gate_parts.append(is_intro)

                gate_input = torch.cat(gate_parts, dim=1)
                alpha = self.gate(gate_input)  # (batch, 1)

                # Blend: α=1 → trust satellite, α=0 → trust env
                x = alpha * sat_h + (1 - alpha) * env_h  # (batch, fusion_dim)

                x = self.input_layer(x)
            else:
                # ── Simple concatenation (no gate) ───────────────────
                parts = [x_continuous] + cat_emb_list
                x = torch.cat(parts, dim=1)
                x = self.input_layer(x)

            # ── Residual blocks + output ─────────────────────────────
            x = self.res_blocks(x)
            logits = self.output_layer(x)

            if self.use_aux_head:
                aux_logits = self.aux_head(x)  # (batch, 1)

                # v2.2: Planted logit boost — connect planted_score to species logits
                # planted_score ∈ [0,1] indicates how likely this location is a plantation
                # species_intro_ratio ∈ [0,1] per-species fraction of introduced observations
                # boost = planted_score * species_intro_ratio * boost_scale
                # This ONLY boosts introduced species at plantation sites.
                planted_score = torch.sigmoid(aux_logits)  # (batch, 1)
                boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
                # boost shape: (batch, num_species)
                logits = logits + boost

                return logits, aux_logits

            return logits

        def set_species_intro_ratio(self, ratio_array):
            """Set per-species introduced ratio from training data.

            Args:
                ratio_array: numpy array or tensor of shape (num_species,)
                    Values in [0,1]: fraction of training observations where is_introduced=1
                    e.g., P. radiata ≈ 0.91, most native species ≈ 0.0
            """
            import torch
            if isinstance(ratio_array, np.ndarray):
                ratio_array = torch.from_numpy(ratio_array).float()
            self.species_intro_ratio.copy_(ratio_array)

        @property
        def num_features(self):
            """Total input dimension (for backward compat)."""
            return self.num_continuous + self.total_emb_dim

    return SINRModel


# ── Step 2b: Dataset ─────────────────────────────────────────────────────────

def get_feature_columns():
    """Return ordered list of ALL feature column names (continuous + categorical)."""
    emb_cols = [f"emb_{i:02d}" for i in range(64)]
    return emb_cols + ENV_FEATURE_COLS


def get_continuous_columns():
    """Return ordered list of CONTINUOUS feature column names (z-score normalized)."""
    emb_cols = [f"emb_{i:02d}" for i in range(64)]
    return emb_cols + ENV_CONTINUOUS_COLS


def remap_categorical(series: pd.Series, col_name: str) -> np.ndarray:
    """Remap raw categorical values to contiguous integer indices for embedding lookup.

    Uses value_map from CATEGORICAL_FEATURES if defined, otherwise identity.
    Unknown/unmapped values → 0 (the padding_idx).
    """
    cfg = CATEGORICAL_FEATURES[col_name]
    value_map = cfg["value_map"]
    vocab_size = cfg["vocab_size"]

    raw = series.fillna(0).astype(np.int64).values

    if value_map is not None:
        # Explicit mapping (e.g., jrc_forest_type: 0→1, 1→2, 10→3, 20→4)
        mapped = np.zeros(len(raw), dtype=np.int64)
        for raw_val, idx in value_map.items():
            mapped[raw == raw_val] = idx
        return mapped
    else:
        # Identity mapping — raw value IS the index (eco_id, biome_num, soil_texture_class)
        # Clamp to valid range; anything >= vocab_size → 0 (unknown)
        result = raw.copy()
        result[(result < 0) | (result >= vocab_size)] = 0
        return result


def create_datasets():
    """Load training data and create PyTorch datasets."""
    import torch
    from torch.utils.data import Dataset

    class SpeciesDataset(Dataset):
        """Dataset for SINR v2 training.

        Each sample = (continuous_features, categorical_indices, species_idx, sample_weight).

        Continuous features are z-score normalized.
        Categorical features are integer indices for nn.Embedding lookup.
        """

        def __init__(
            self,
            parquet_path: Path,
            continuous_cols: List[str],
            categorical_cols: List[str],
            normalize_stats=None,
        ):
            print(f"  Loading {parquet_path.name}...")
            df = pd.read_parquet(parquet_path)

            # ── Continuous features (z-score normalized) ─────────────
            self.continuous = df[continuous_cols].values.astype(np.float32)

            nan_count = np.isnan(self.continuous).sum()
            inf_count = np.isinf(self.continuous).sum()
            if nan_count > 0 or inf_count > 0:
                print(f"    Replacing {nan_count:,} NaN and {inf_count:,} inf with 0")
            self.continuous = np.nan_to_num(self.continuous, nan=0.0, posinf=0.0, neginf=0.0)

            if normalize_stats is None:
                self.mean = self.continuous.mean(axis=0)
                self.std = self.continuous.std(axis=0)
                self.std[self.std < 1e-8] = 1.0
            else:
                self.mean = normalize_stats["mean"]
                self.std = normalize_stats["std"]
            self.continuous = (self.continuous - self.mean) / self.std

            # ── Categorical features (integer indices for embedding) ──
            cat_arrays = []
            for col in categorical_cols:
                mapped = remap_categorical(df[col], col)
                cat_arrays.append(mapped)
            if cat_arrays:
                self.categorical = np.stack(cat_arrays, axis=1)  # (N, num_cat)
            else:
                self.categorical = np.zeros((len(df), 0), dtype=np.int64)

            # ── is_introduced flag (for gating) ──────────────────────
            if "is_introduced" in df.columns:
                raw_intro = df["is_introduced"].fillna(-1).values.astype(np.float32)
                # Remap: 0→0 (native), 1→1 (introduced), -1→0.5 (unknown)
                raw_intro[raw_intro == -1] = 0.5
                self.is_introduced = raw_intro.reshape(-1, 1)  # (N, 1)
            else:
                # Fallback: all unknown (0.5)
                self.is_introduced = np.full((len(df), 1), 0.5, dtype=np.float32)

            # ── Species index ────────────────────────────────────────
            self.species_idx = df["species_idx"].values.astype(np.int64)

            # ── Sample weights ───────────────────────────────────────
            qw = df["quality_weight"].fillna(1.0).values.astype(np.float32)
            dw = df["density_weight"].fillna(1.0).values.astype(np.float32)
            self.sample_weight = np.clip(qw * dw, 0.01, 10.0)

            print(
                f"    Loaded {len(self):,} samples: "
                f"{self.continuous.shape[1]} continuous + "
                f"{self.categorical.shape[1]} categorical features"
            )

        def __len__(self):
            return len(self.species_idx)

        def __getitem__(self, idx):
            return (
                torch.from_numpy(self.continuous[idx]),
                torch.from_numpy(self.categorical[idx]),
                torch.from_numpy(self.is_introduced[idx]),
                self.species_idx[idx],
                self.sample_weight[idx],
            )

        def get_normalize_stats(self):
            return {"mean": self.mean, "std": self.std}

    return SpeciesDataset


# ── Step 2c: Loss Function ───────────────────────────────────────────────────

def create_loss_fn():
    """Create the SINR assumed-negative BCE loss."""
    import torch
    import torch.nn.functional as F

    def sinr_an_full_loss(
        logits: torch.Tensor,  # (batch, num_species) — raw logits
        species_idx: torch.Tensor,  # (batch,) — target species index
        sample_weight: torch.Tensor,  # (batch,) — per-sample weight
        bg_logits: Optional[torch.Tensor] = None,  # (batch, num_species) — background logits
        pos_weight: float = POS_WEIGHT,
        bg_weight: float = BG_WEIGHT,
    ) -> torch.Tensor:
        """
        Assumed-Negative Full Loss (SINR an_full).

        For each sample:
          - Positive: -pos_weight * log(sigmoid(logit[species_idx]))
          - Negative: -log(1 - sigmoid(logit[all_others])) for all other species
        
        Background (random locations):
          - -log(1 - sigmoid(logit[all_species])) — all assumed absent
        """
        batch_size, num_species = logits.shape

        # Compute log-sigmoid and log(1-sigmoid) for numerical stability
        # log_sigmoid(x) = -softplus(-x)
        # log(1-sigmoid(x)) = -softplus(x)
        log_pos = F.logsigmoid(logits)  # (batch, num_species)
        log_neg = F.logsigmoid(-logits)  # = log(1-sigmoid(x))

        # Negative loss: assume all species absent
        loss_neg = -log_neg.mean(dim=1)  # (batch,)

        # Positive loss: override for the target species
        # Gather the logit for the target species
        target_log_pos = log_pos.gather(1, species_idx.unsqueeze(1)).squeeze(1)  # (batch,)
        target_log_neg = log_neg.gather(1, species_idx.unsqueeze(1)).squeeze(1)  # (batch,)

        # The full loss per sample:
        # loss_neg already includes the negative for the target species.
        # We need to remove it and add the positive instead.
        # Correction: subtract the negative contribution and add positive
        correction = (-target_log_neg + pos_weight * (-target_log_pos)) / num_species
        loss_per_sample = loss_neg + correction

        # Apply sample weights
        weighted_loss = (loss_per_sample * sample_weight).mean()

        # Background loss (if provided)
        if bg_logits is not None:
            bg_log_neg = F.logsigmoid(-bg_logits)
            loss_bg = -bg_log_neg.mean()
            weighted_loss = weighted_loss + bg_weight * loss_bg

        return weighted_loss

    return sinr_an_full_loss


# ── Step 2d: Training Loop ───────────────────────────────────────────────────

def train_model():
    """Train the SINR model."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    print("=" * 70)
    print("STEP 2: TRAIN SINR MODEL")
    print("=" * 70)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── Device selection ─────────────────────────────────────────────────
    force_cpu = os.environ.get("SINR_FORCE_CPU", "0") == "1"
    if not force_cpu and torch.backends.mps.is_available():
        device = torch.device("mps")
        print(f"  Device: Apple Silicon GPU (MPS)")
    else:
        device = torch.device("cpu")
        torch.set_num_threads(8)
        print(f"  Device: CPU ({torch.get_num_threads()} threads)")

    # ── Load species mapping ─────────────────────────────────────────────
    mapping_path = DATA_DIR / "species_mapping.json"
    with open(mapping_path) as f:
        mapping = json.load(f)
    num_species = mapping["num_species"]
    species_counts = mapping["species_counts"]
    print(f"  Species: {num_species:,}")

    # ── Create datasets ──────────────────────────────────────────────────
    continuous_cols = get_continuous_columns()
    categorical_cols = CATEGORICAL_COLS
    num_continuous = len(continuous_cols)
    print(f"  Continuous features: {num_continuous}")
    print(f"  Categorical features: {len(categorical_cols)} → {TOTAL_EMB_DIM}D embeddings")
    print(f"  Total input dim: {num_continuous + TOTAL_EMB_DIM}")

    SpeciesDataset = create_datasets()

    print("\n  Loading training data...")
    train_dataset = SpeciesDataset(
        DATA_DIR / "train.parquet", continuous_cols, categorical_cols
    )
    normalize_stats = train_dataset.get_normalize_stats()

    print("  Loading validation data...")
    val_dataset = SpeciesDataset(
        DATA_DIR / "val.parquet", continuous_cols, categorical_cols,
        normalize_stats=normalize_stats,
    )

    # Save normalization stats for inference (continuous features only now)
    np.savez(
        MODEL_DIR / "normalize_stats.npz",
        mean=normalize_stats["mean"],
        std=normalize_stats["std"],
        continuous_cols=continuous_cols,
        categorical_cols=categorical_cols,
    )

    # MPS doesn't support pin_memory; multiprocessing workers can be slow on macOS
    # Use num_workers=0 (main process) to avoid pickling issues with inner classes
    use_pin = (device.type == "cuda")
    loader_workers = NUM_WORKERS if device.type == "cuda" else 0

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=loader_workers,
        pin_memory=use_pin,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE * 2,
        shuffle=False,
        num_workers=loader_workers,
        pin_memory=use_pin,
    )

    # ── Compute per-species introduced ratio ────────────────────────────
    # For the planted logit boost: what fraction of each species' training
    # observations have is_introduced=1?
    print("\n  Computing per-species introduced ratio...")
    intro_vals = train_dataset.is_introduced.flatten()  # (N,) values: 0, 0.5, 1
    species_indices = train_dataset.species_idx  # (N,)
    # Only count definitive labels (0=native, 1=introduced), skip 0.5=unknown
    known_mask = (intro_vals == 0) | (intro_vals == 1)
    known_species = species_indices[known_mask]
    known_intro = intro_vals[known_mask]
    # Vectorized aggregation via np.bincount (much faster than Python loop)
    species_intro_sum = np.bincount(known_species, weights=known_intro, minlength=num_species)
    species_intro_count = np.bincount(known_species, minlength=num_species).astype(np.float64)
    # Ratio = sum(is_introduced) / count(known), default 0 for species with no data
    species_intro_ratio = np.where(
        species_intro_count > 0,
        species_intro_sum / species_intro_count,
        0.0,
    ).astype(np.float32)
    n_intro_species = (species_intro_ratio > 0.5).sum()
    print(f"    {n_intro_species:,} species have >50% introduced observations")
    print(f"    Mean intro ratio: {species_intro_ratio.mean():.4f}")
    print(f"    Max intro ratio: {species_intro_ratio.max():.4f}")

    # Save for inference
    np.save(MODEL_DIR / "species_intro_ratio.npy", species_intro_ratio)

    # ── Build model ──────────────────────────────────────────────────────
    SINRModel = build_model()
    model = SINRModel(
        num_continuous=num_continuous,
        num_species=num_species,
        categorical_config=CATEGORICAL_FEATURES,
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_RES_BLOCKS,
        dropout=DROPOUT,
        use_gate=True,
        use_aux_head=True,
    )
    model = model.to(device)

    # Set per-species introduced ratio on the model
    model.set_species_intro_ratio(species_intro_ratio)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n  Model parameters: {total_params:,} ({trainable_params:,} trainable)")
    print(f"  Model size: {total_params * 4 / 1e6:.1f} MB (float32)")

    # ── Optimizer & scheduler ────────────────────────────────────────────
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=LR_DECAY)
    loss_fn = create_loss_fn()

    # ── Training loop ────────────────────────────────────────────────────
    print(f"\n  Training config:")
    print(f"    Batch size: {BATCH_SIZE}")
    print(f"    Epochs: {NUM_EPOCHS}")
    print(f"    LR: {LEARNING_RATE}, decay: {LR_DECAY}")
    print(f"    pos_weight: {POS_WEIGHT}")
    print(f"    Hard cap/species: {HARD_CAP_PER_SPECIES}")
    print(f"    Batches/epoch: {len(train_loader):,}")

    best_val_loss = float("inf")
    train_history = []

    for epoch in range(NUM_EPOCHS):
        epoch_t0 = time.time()

        # ── Train ────────────────────────────────────────────────────
        model.train()
        train_loss_sum = 0.0
        train_batches = 0

        for batch_idx, (cont, cat, is_intro, species_idx, sample_weight) in enumerate(train_loader):
            cont = cont.to(device)
            cat = cat.to(device)
            is_intro = is_intro.to(device)
            species_idx = species_idx.to(device)
            sample_weight = sample_weight.to(device)

            # Forward pass — returns (logits, aux_logits) with aux head
            output = model(cont, cat, is_intro)
            if isinstance(output, tuple):
                logits, aux_logits = output
            else:
                logits = output
                aux_logits = None

            # Background: random features from training set (fast numpy indexing)
            bg_indices = np.random.randint(0, len(train_dataset), BATCH_SIZE)
            bg_cont_np = train_dataset.continuous[bg_indices]
            bg_cat_np = train_dataset.categorical[bg_indices]
            bg_intro_np = train_dataset.is_introduced[bg_indices]
            bg_cont_t = torch.from_numpy(bg_cont_np).to(device)
            bg_cat_t = torch.from_numpy(bg_cat_np).to(device)
            bg_intro_t = torch.from_numpy(bg_intro_np).to(device)
            bg_output = model(bg_cont_t, bg_cat_t, bg_intro_t)
            if isinstance(bg_output, tuple):
                bg_logits, _ = bg_output
            else:
                bg_logits = bg_output

            loss = loss_fn(logits, species_idx, sample_weight, bg_logits)

            # Auxiliary planted-score loss (weak supervision)
            if aux_logits is not None:
                # Weak labels from categorical features already in cat tensor:
                # xiao_planted_forest index in CATEGORICAL_COLS
                xiao_col_idx = list(CATEGORICAL_FEATURES.keys()).index("xiao_planted_forest")
                xiao_vals = cat[:, xiao_col_idx]  # remapped: 3=planted, 2=natural, 1=non-forest, 0=unknown
                # JRC forest type
                jrc_col_idx = list(CATEGORICAL_FEATURES.keys()).index("jrc_forest_type")
                jrc_vals = cat[:, jrc_col_idx]  # remapped: 4=planted, 2=natural, 3=primary, 1=non-forest, 0=unknown

                # Weak planted label: 1 if xiao=planted(3) OR jrc=planted(4), 0 otherwise
                # Only compute loss where we have data (not unknown=0)
                planted_label = ((xiao_vals == 3) | (jrc_vals == 4)).float()
                has_data = (xiao_vals > 0) | (jrc_vals > 0)  # at least one signal

                if has_data.any():
                    aux_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                        aux_logits[has_data].squeeze(-1),
                        planted_label[has_data],
                    )
                    loss = loss + 0.1 * aux_loss  # 10% weight for aux task

            # Backward
            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            train_loss_sum += loss.item()
            train_batches += 1

            if batch_idx % 200 == 0:
                avg_loss = train_loss_sum / train_batches
                elapsed = time.time() - epoch_t0
                eta_epoch = elapsed / max(batch_idx + 1, 1) * (len(train_loader) - batch_idx - 1)
                print(
                    f"    Epoch {epoch+1}/{NUM_EPOCHS} "
                    f"[{batch_idx:,}/{len(train_loader):,}] "
                    f"loss={avg_loss:.6f} "
                    f"lr={scheduler.get_last_lr()[0]:.6f} "
                    f"ETA={eta_epoch/60:.1f}min"
                )

        avg_train_loss = train_loss_sum / train_batches

        # ── Validate ─────────────────────────────────────────────────
        model.eval()
        val_loss_sum = 0.0
        val_batches = 0
        top10_correct = 0
        top50_correct = 0
        val_total = 0

        with torch.no_grad():
            for cont, cat, is_intro, species_idx, sample_weight in val_loader:
                cont = cont.to(device)
                cat = cat.to(device)
                is_intro = is_intro.to(device)
                species_idx = species_idx.to(device)
                sample_weight = sample_weight.to(device)

                output = model(cont, cat, is_intro)
                if isinstance(output, tuple):
                    logits, _ = output
                else:
                    logits = output
                loss = loss_fn(logits, species_idx, sample_weight)
                val_loss_sum += loss.item()
                val_batches += 1

                # Top-k accuracy
                probs = torch.sigmoid(logits)
                _, top50_indices = probs.topk(50, dim=1)
                _, top10_indices = probs.topk(10, dim=1)

                for i in range(len(species_idx)):
                    target = species_idx[i].item()
                    if target in top50_indices[i]:
                        top50_correct += 1
                    if target in top10_indices[i]:
                        top10_correct += 1
                    val_total += 1

        avg_val_loss = val_loss_sum / val_batches
        top10_acc = top10_correct / val_total if val_total > 0 else 0
        top50_acc = top50_correct / val_total if val_total > 0 else 0

        epoch_time = time.time() - epoch_t0
        scheduler.step()

        print(
            f"\n  Epoch {epoch+1}/{NUM_EPOCHS} complete in {epoch_time/60:.1f}min | "
            f"train_loss={avg_train_loss:.6f} | "
            f"val_loss={avg_val_loss:.6f} | "
            f"top10={top10_acc:.4f} | top50={top50_acc:.4f}\n"
        )

        train_history.append({
            "epoch": epoch + 1,
            "train_loss": avg_train_loss,
            "val_loss": avg_val_loss,
            "top10_accuracy": top10_acc,
            "top50_accuracy": top50_acc,
            "lr": scheduler.get_last_lr()[0],
            "time_min": epoch_time / 60,
        })

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "model_version": 4,  # v2.2: 4D gate + planted logit boost + subspecies merge
                "num_continuous": num_continuous,
                "num_species": num_species,
                "categorical_config": CATEGORICAL_FEATURES,
                "hidden_dim": HIDDEN_DIM,
                "num_blocks": NUM_RES_BLOCKS,
                "dropout": DROPOUT,
                "use_gate": True,
                "use_aux_head": True,
                "epoch": epoch + 1,
                "val_loss": avg_val_loss,
                "top10_accuracy": top10_acc,
                "top50_accuracy": top50_acc,
            }, MODEL_DIR / "best_model.pt")
            print(f"    >>> Saved best model (val_loss={avg_val_loss:.6f})")

        # Save latest model
        torch.save({
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "model_version": 4,  # v2.2: 4D gate + planted logit boost + subspecies merge
            "num_continuous": num_continuous,
            "num_species": num_species,
            "categorical_config": CATEGORICAL_FEATURES,
            "hidden_dim": HIDDEN_DIM,
            "num_blocks": NUM_RES_BLOCKS,
            "dropout": DROPOUT,
            "use_gate": True,
            "use_aux_head": True,
            "epoch": epoch + 1,
        }, MODEL_DIR / "latest_checkpoint.pt")

    # Save training history
    with open(MODEL_DIR / "training_history.json", "w") as f:
        json.dump(train_history, f, indent=2)

    print(f"\n  Training complete!")
    print(f"  Best val_loss: {best_val_loss:.6f}")
    print(f"  Model saved to: {MODEL_DIR}/best_model.pt")


# ── Step 3: Evaluation ───────────────────────────────────────────────────────

def evaluate_model():
    """Evaluate the trained model on validation set and specific test locations."""
    import torch

    print("=" * 70)
    print("STEP 3: EVALUATE MODEL")
    print("=" * 70)

    # ── Load model ───────────────────────────────────────────────────────
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    checkpoint = torch.load(MODEL_DIR / "best_model.pt", map_location=device, weights_only=False)

    SINRModel = build_model()
    model_version = checkpoint.get("model_version", 1)

    if model_version >= 2:
        # v2: entity embeddings + gated fusion
        model = SINRModel(
            num_continuous=checkpoint["num_continuous"],
            num_species=checkpoint["num_species"],
            categorical_config=checkpoint.get("categorical_config", {}),
            hidden_dim=checkpoint["hidden_dim"],
            num_blocks=checkpoint["num_blocks"],
            dropout=checkpoint["dropout"],
            use_gate=checkpoint.get("use_gate", True),
            use_aux_head=checkpoint.get("use_aux_head", False),
        )
    else:
        # v1 backward compat: all features treated as continuous, no gate
        model = SINRModel(
            num_continuous=checkpoint["num_features"],
            num_species=checkpoint["num_species"],
            hidden_dim=checkpoint["hidden_dim"],
            num_blocks=checkpoint["num_blocks"],
            dropout=checkpoint["dropout"],
            use_gate=False,
            use_aux_head=False,
        )

    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    # v2.2: Load species_intro_ratio if not already in checkpoint state_dict
    if model_version >= 4 and hasattr(model, 'species_intro_ratio'):
        intro_ratio_path = MODEL_DIR / "species_intro_ratio.npy"
        if intro_ratio_path.exists() and model.species_intro_ratio.sum() == 0:
            ratio = np.load(intro_ratio_path)
            model.set_species_intro_ratio(ratio)
            print(f"  Loaded species_intro_ratio from {intro_ratio_path}")

    print(f"  Loaded model v{model_version} from epoch {checkpoint['epoch']}")
    print(f"  Val loss: {checkpoint['val_loss']:.6f}")
    print(f"  Top-10 accuracy: {checkpoint['top10_accuracy']:.4f}")
    print(f"  Top-50 accuracy: {checkpoint['top50_accuracy']:.4f}")

    # ── Load species mapping ─────────────────────────────────────────────
    with open(DATA_DIR / "species_mapping.json") as f:
        mapping = json.load(f)
    idx_to_species = {v: k for k, v in mapping["species_to_idx"].items()}

    # ── Load normalization stats ─────────────────────────────────────────
    stats = np.load(MODEL_DIR / "normalize_stats.npz", allow_pickle=True)
    mean = stats["mean"]
    std = stats["std"]

    # ── Detailed validation metrics ──────────────────────────────────────
    print("\n  Running detailed evaluation on validation set...")
    continuous_cols = get_continuous_columns()
    categorical_cols = CATEGORICAL_COLS if model_version >= 2 else []
    SpeciesDataset = create_datasets()
    val_dataset = SpeciesDataset(
        DATA_DIR / "val.parquet",
        continuous_cols,
        categorical_cols,
        normalize_stats={"mean": mean, "std": std},
    )

    from torch.utils.data import DataLoader
    val_loader = DataLoader(val_dataset, batch_size=4096, shuffle=False)

    # Per-species metrics
    species_correct_top10 = {}
    species_correct_top50 = {}
    species_total = {}
    rank_sum = 0
    rank_count = 0

    with torch.no_grad():
        for cont, cat, is_intro, species_idx, _ in val_loader:
            cont = cont.to(device)
            cat = cat.to(device) if model_version >= 2 else None
            is_intro = is_intro.to(device) if model_version >= 2 else None
            output = model(cont, cat, is_intro)
            if isinstance(output, tuple):
                logits, _ = output
            else:
                logits = output
            probs = torch.sigmoid(logits)

            # Get ranks
            sorted_indices = probs.argsort(dim=1, descending=True)

            for i in range(len(species_idx)):
                target = species_idx[i].item()
                taxon = idx_to_species.get(target, str(target))

                # Find rank of true species
                rank = (sorted_indices[i] == target).nonzero(as_tuple=True)[0].item()
                rank_sum += rank
                rank_count += 1

                if taxon not in species_total:
                    species_total[taxon] = 0
                    species_correct_top10[taxon] = 0
                    species_correct_top50[taxon] = 0
                species_total[taxon] += 1

                if rank < 10:
                    species_correct_top10[taxon] += 1
                if rank < 50:
                    species_correct_top50[taxon] += 1

    mean_rank = rank_sum / rank_count if rank_count > 0 else 0
    median_pct = mean_rank / checkpoint["num_species"] * 100

    print(f"\n  Overall metrics:")
    print(f"    Mean rank of true species: {mean_rank:.1f} / {checkpoint['num_species']:,} ({median_pct:.2f}%)")
    print(f"    Top-10 recall: {sum(species_correct_top10.values()) / rank_count:.4f}")
    print(f"    Top-50 recall: {sum(species_correct_top50.values()) / rank_count:.4f}")

    # Show P. radiata specifically
    radiata_ids = [k for k in species_total if k.startswith("GymPiPiPnCx50820")]
    if radiata_ids:
        print(f"\n  P. radiata performance:")
        for tid in sorted(radiata_ids):
            t10 = species_correct_top10.get(tid, 0)
            t50 = species_correct_top50.get(tid, 0)
            tot = species_total[tid]
            print(f"    {tid}: top10={t10}/{tot} ({100*t10/tot:.1f}%), top50={t50}/{tot} ({100*t50/tot:.1f}%)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train SINR species prediction model")
    parser.add_argument("--extract-data", action="store_true",
                        help="Extract training data from PostgreSQL")
    parser.add_argument("--train", action="store_true",
                        help="Train the SINR model")
    parser.add_argument("--evaluate", action="store_true",
                        help="Evaluate the trained model")
    parser.add_argument("--all", action="store_true",
                        help="Run all steps")

    args = parser.parse_args()

    if args.all:
        args.extract_data = True
        args.train = True
        args.evaluate = True

    if not args.extract_data and not args.train and not args.evaluate:
        parser.error("Specify --extract-data, --train, --evaluate, or --all")

    if args.extract_data:
        extract_training_data()

    if args.train:
        train_model()

    if args.evaluate:
        evaluate_model()


if __name__ == "__main__":
    main()
