#!/usr/bin/env python3
"""
train_sinr_v3.py — SINR v3.0 Species Prediction Model.

Major changes from v2.2:
  1. Data source: BigQuery unified table (15M+ rows) instead of local PostgreSQL
  2. AlphaEarth temporal stack: 8-year × 64D with temporal attention (was single-year 64D)
  3. Phylogenetic embeddings: 32D per-species from OToL tree MDS
  4. Land State features: 4 features from Tier 1 heuristic
  5. Carbon/biomass temporal: GEDI, SPAWN, NPP trends
  6. Aridity: aridity index + ET0

Architecture:
  - Temporal Attention Module: 8×64 AE stack → temporal-aware 128D representation
  - Phylogenetic Branch: 32D per-species → merged after residual blocks
  - Expanded env features: 80+ continuous + 5 categorical + land state
  - Multi-task heads: species prediction + land state + planted detection

Training data: sinr_v3_unified_v1 + sinr_v3_land_state_t1 from BigQuery
  - ~15M rows, ~50K species
  - Export to local parquet for GPU training

Usage:
  python3 train_sinr_v3.py --extract-data     # Export BQ → local parquet
  python3 train_sinr_v3.py --train            # Train v3.0 model
  python3 train_sinr_v3.py --evaluate         # Evaluate
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "sinr_training_data"
MODEL_DIR = SCRIPT_DIR / "sinr_model_v3"

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
UNIFIED_TABLE = 'sinr_v3_unified_v1'
LAND_STATE_TABLE = 'sinr_v3_land_state_t1'

# ── Feature Configuration ────────────────────────────────────────────────────

# AlphaEarth: primary 64D embedding at emb_year
AE_EMB_COLS = [f"emb_{i:02d}" for i in range(64)]

# AlphaEarth: 8-year temporal stack (8 × 64 = 512D)
AE_TEMPORAL_COLS = [f"ae_{y}_{b:02d}" for y in range(2017, 2025) for b in range(64)]

# Environmental continuous features (from v2.2 + new v3 additions)
ENV_CONTINUOUS_COLS = [
    # Topography
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
    # Climate (BioClim)
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    # Soil
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    # Forest structure
    "treecover2000", "lossyear",
    "gedi_canopy_height_m", "gedi_foliage_height_div",
    "biomass_agb_mgha",
    # Water
    "water_occurrence", "water_recurrence", "water_seasonality",
    # Land cover / classification
    "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world", "sbtn_natural_land",
    "neumann_natural_prob",
    # Microclimate
    "tc_vpd_mean", "tc_aet_mean", "tc_soil_moisture_mean",
    "tc_pdsi_mean", "tc_water_deficit_mean", "tc_solar_rad_mean",
    # Human pressure
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "modis_gpp_mean",
    # NEW in v3: Carbon/biomass temporal
    "carbon_canopy_height_m",
    "spawn_agb", "spawn_agb_unc", "spawn_bgb", "spawn_bgb_unc",
    "gedi_l4b_agbd", "gedi_l4b_agbd_se", "gedi_rh98", "gedi_fhd",
    "soc_0cm", "soc_30cm", "soc_100cm", "soc_200cm",
    "npp_at_obs", "gpp_at_obs", "lai_at_obs", "fpar_at_obs", "evi_at_obs",
    "cci_agb_at_obs", "cci_agb_sd_at_obs",
    "npp_at_ae", "gpp_at_ae", "lai_at_ae", "fpar_at_ae", "evi_at_ae",
    "cci_agb_at_ae", "cci_agb_sd_at_ae",
    "npp_mean_longterm", "npp_trend",
    # NEW in v3: Aridity
    "aridity_index", "et0_mm_yr",
    # NEW in v3: HILDA
    "hilda_lulc_at_obs", "hilda_lulc_at_ae",
]

# Categorical features (entity embeddings)
CATEGORICAL_FEATURES = {
    "jrc_forest_type": {"vocab_size": 5, "emb_dim": 3,
                         "value_map": {0: 1, 1: 2, 10: 3, 20: 4}},
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                             "value_map": {0: 1, 1: 2, 2: 3}},
    "eco_id": {"vocab_size": 850, "emb_dim": 32, "value_map": None},
    "biome_num": {"vocab_size": 16, "emb_dim": 8, "value_map": None},
    "soil_texture_class": {"vocab_size": 14, "emb_dim": 6, "value_map": None},
    "ipcc_forest_class": {"vocab_size": 10, "emb_dim": 4, "value_map": None},  # NEW v3
}

# Land state features (from Tier 1 heuristic)
LAND_STATE_COLS = [
    "land_state_class",       # categorical (0-5)
    "disturbance_intensity",  # continuous (0-1)
    "forest_stability",       # continuous (-1 to 1)
    "successional_stage",     # categorical (0-4, -1 for non-forest)
    "ae_temporal_change_l2",  # continuous
]

# Phylogenetic embedding
PHYLO_DIMS = 32  # From species_phylo_embeddings.npz

# Hyperparameters
BATCH_SIZE = 2048
NUM_EPOCHS = 15
LEARNING_RATE = 0.0003
LR_DECAY = 0.97
POS_WEIGHT = 2048.0
DROPOUT = 0.25
HIDDEN_DIM = 384  # Increased from 256 for more capacity
NUM_RES_BLOCKS = 6  # Increased from 4
FUSION_DIM = 192  # Increased from 128
TEMPORAL_HIDDEN = 128
VAL_FRACTION = 0.05
NUM_WORKERS = 4


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Step 1: Data Extraction from BQ ─────────────────────────────────────────

def extract_training_data():
    """Export unified BQ table to local parquet for training."""
    from google.cloud import bigquery

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=BQ_PROJECT)

    # Build column list
    all_cols = (
        ['latitude', 'longitude', 'observation_year', 'emb_year', 'data_source'] +
        AE_EMB_COLS + ENV_CONTINUOUS_COLS +
        list(CATEGORICAL_FEATURES.keys()) +
        AE_TEMPORAL_COLS
    )

    # Remove duplicates while preserving order
    seen = set()
    unique_cols = []
    for c in all_cols:
        if c not in seen:
            unique_cols.append(c)
            seen.add(c)

    log(f"Extracting {len(unique_cols)} columns from {UNIFIED_TABLE}...")

    # Export in chunks to manage memory
    chunk_size = 2_000_000
    total_query = f"""
    SELECT COUNT(*) as n FROM `{BQ_PROJECT}.{BQ_DATASET}.{UNIFIED_TABLE}`
    """
    total_rows = list(client.query(total_query).result())[0].n
    log(f"Total rows: {total_rows:,}")

    n_chunks = (total_rows + chunk_size - 1) // chunk_size
    log(f"Exporting in {n_chunks} chunks of {chunk_size:,}")

    # Add taxon_id via species_occurrence_embeddings JOIN or direct from BQ
    # For v3, taxon_id should be in the unified table
    # Let's check if it exists
    try:
        check_q = f"""
        SELECT column_name FROM `{BQ_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{UNIFIED_TABLE}' AND column_name = 'taxon_id'
        """
        has_taxon_id = len(list(client.query(check_q).result())) > 0
    except Exception:
        has_taxon_id = False

    if not has_taxon_id:
        log("WARNING: taxon_id not in unified table. Will need to join with occurrence data.")
        log("For now, exporting location data only. Species mapping needed separately.")

    # Export query with land state join
    export_cols = ', '.join(f'u.{c}' for c in unique_cols)
    land_state_select = ', '.join(f't.{c}' for c in LAND_STATE_COLS)

    query = f"""
    SELECT
        {export_cols},
        {land_state_select}
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{UNIFIED_TABLE}` u
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.{LAND_STATE_TABLE}` t
        ON ROUND(u.latitude, 4) = ROUND(t.latitude, 4)
        AND ROUND(u.longitude, 4) = ROUND(t.longitude, 4)
        AND u.observation_year = t.observation_year
        AND u.emb_year = t.emb_year
    """

    log("Running export query...")
    log("(This is a large query — may take 10-20 minutes)")

    df = client.query(query).to_dataframe()
    log(f"Got {len(df):,} rows, {len(df.columns)} columns")

    # Save to parquet (chunked for large datasets)
    output_path = DATA_DIR / 'sinr_v3_training_data.parquet'
    df.to_parquet(output_path, index=False, engine='pyarrow')
    log(f"Saved to {output_path} ({output_path.stat().st_size / 1e9:.2f} GB)")


# ── Step 2: Model Architecture ──────────────────────────────────────────────

def build_model_classes():
    """Build v3.0 model classes."""
    import torch
    import torch.nn as nn

    class ResidualBlock(nn.Module):
        def __init__(self, dim, dropout):
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

    class TemporalAttentionModule(nn.Module):
        """Attention over 8 years of 64D AlphaEarth embeddings.

        Captures:
        - Which years are most informative for species prediction
        - Temporal change patterns (disturbance, succession, stability)
        - Year-specific context via learned year embeddings
        """

        def __init__(self, embed_dim=64, n_years=8, output_dim=128):
            super().__init__()
            self.embed_dim = embed_dim
            self.n_years = n_years

            # Year-level positional embeddings
            self.year_embed = nn.Embedding(n_years, embed_dim)

            # Self-attention
            self.attn = nn.MultiheadAttention(embed_dim, num_heads=4, batch_first=True, dropout=0.1)

            # Temporal difference feature projection
            self.diff_proj = nn.Linear(embed_dim, output_dim // 4)

            # Output projection: attended_mean(64) + attended_max(64) + diff(32) + first_last_diff(32)
            self.output_proj = nn.Linear(embed_dim * 2 + output_dim // 4 + output_dim // 4, output_dim)

            # First-last difference projection
            self.first_last_proj = nn.Linear(embed_dim, output_dim // 4)

        def forward(self, ae_temporal):
            """
            Args:
                ae_temporal: (batch, 512) — flattened 8×64 AE stack
            Returns:
                (batch, output_dim) temporal representation
            """
            B = ae_temporal.shape[0]
            x = ae_temporal.view(B, self.n_years, self.embed_dim)  # (B, 8, 64)

            # Add year positional embeddings
            year_ids = torch.arange(self.n_years, device=x.device)
            x = x + self.year_embed(year_ids).unsqueeze(0)

            # Self-attention
            attended, _ = self.attn(x, x, x)  # (B, 8, 64)

            # Pool: mean + max
            pooled_mean = attended.mean(dim=1)  # (B, 64)
            pooled_max = attended.max(dim=1).values  # (B, 64)

            # Temporal differences (year-over-year changes)
            diffs = x[:, 1:] - x[:, :-1]  # (B, 7, 64)
            diff_feat = self.diff_proj(diffs.mean(dim=1))  # (B, output_dim//4)

            # First-last difference (overall change 2017→2024)
            first_last = self.first_last_proj(x[:, -1] - x[:, 0])  # (B, output_dim//4)

            combined = torch.cat([pooled_mean, pooled_max, diff_feat, first_last], dim=-1)
            return self.output_proj(combined)  # (B, output_dim)

    class SINRModelV3(nn.Module):
        """SINR v3.0 Species Prediction Model.

        Branches:
          1. Satellite (primary AE at emb_year): 64D → 128D
          2. Temporal (8-year AE stack): 512D → temporal attention → 128D
          3. Environment: ~80 continuous + entity embeddings → 192D
          4. Land State: 5 features → 32D

        Fusion:
          - Gated: gate(jrc_emb + is_introduced) → α blends sat vs env
          - Temporal concatenated (always included)
          - Land state concatenated

        Post-fusion:
          - Linear → hidden_dim → ResBlocks
          - Phylogenetic embedding injected via additive after ResBlocks
          - Species output head
        """

        NUM_SAT_DIMS = 64

        def __init__(
            self,
            num_env_continuous,
            num_species,
            categorical_config=None,
            hidden_dim=384,
            num_blocks=6,
            dropout=0.25,
            fusion_dim=192,
            temporal_dim=128,
            phylo_dim=32,
            land_state_dim=32,
        ):
            super().__init__()
            self.num_env_continuous = num_env_continuous
            self.num_species = num_species
            self.categorical_config = categorical_config or {}
            self.hidden_dim = hidden_dim
            self.fusion_dim = fusion_dim
            self.phylo_dim = phylo_dim

            # ── Entity embeddings ────────────────────────────────────
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

            # ── Branch 1: Satellite (primary AE) ─────────────────────
            self.sat_proj = nn.Sequential(
                nn.Linear(self.NUM_SAT_DIMS, fusion_dim),
                nn.ReLU(inplace=True),
            )

            # ── Branch 2: Temporal AE stack ──────────────────────────
            self.temporal_module = TemporalAttentionModule(
                embed_dim=64, n_years=8, output_dim=temporal_dim
            )

            # ── Branch 3: Environment ────────────────────────────────
            env_input_dim = num_env_continuous + total_emb_dim
            self.env_proj = nn.Sequential(
                nn.Linear(env_input_dim, fusion_dim),
                nn.ReLU(inplace=True),
            )

            # ── Branch 4: Land State ─────────────────────────────────
            # 2 continuous + 3 categorical-ish features
            self.land_state_proj = nn.Sequential(
                nn.Linear(5, land_state_dim),
                nn.ReLU(inplace=True),
            )

            # ── Gate ─────────────────────────────────────────────────
            gate_input_dim = 0
            self.gate_cat_features = []
            for gf in ["jrc_forest_type"]:
                if gf in self.categorical_config:
                    gate_input_dim += self.categorical_config[gf]["emb_dim"]
                    self.gate_cat_features.append(gf)
            gate_input_dim += 1  # is_introduced
            self.gate = nn.Sequential(
                nn.Linear(gate_input_dim, 16),
                nn.ReLU(inplace=True),
                nn.Linear(16, 1),
                nn.Sigmoid(),
            )

            # ── Main trunk ───────────────────────────────────────────
            # Input: fusion_dim (gated sat/env) + temporal_dim + land_state_dim
            trunk_input = fusion_dim + temporal_dim + land_state_dim
            self.input_layer = nn.Sequential(
                nn.Linear(trunk_input, hidden_dim),
                nn.ReLU(inplace=True),
            )

            self.res_blocks = nn.Sequential(
                *[ResidualBlock(hidden_dim, dropout) for _ in range(num_blocks)]
            )

            # ── Phylogenetic injection ───────────────────────────────
            # Project phylo embeddings to hidden_dim, then add after res blocks
            self.phylo_proj = nn.Sequential(
                nn.Linear(phylo_dim, hidden_dim),
                nn.ReLU(inplace=True),
                nn.Linear(hidden_dim, hidden_dim),
            )
            self.phylo_gate = nn.Sequential(
                nn.Linear(hidden_dim * 2, 1),
                nn.Sigmoid(),
            )

            # ── Species output ───────────────────────────────────────
            self.output_layer = nn.Linear(hidden_dim, num_species, bias=False)

            # ── Auxiliary heads ───────────────────────────────────────
            self.aux_planted_head = nn.Linear(hidden_dim, 1)
            self.aux_land_state_head = nn.Linear(hidden_dim, 6)  # 6 land state classes
            self.boost_scale = nn.Parameter(torch.tensor(2.0))
            self.register_buffer("species_intro_ratio", torch.zeros(num_species))

        def forward(self, x_continuous, x_categorical, x_is_introduced,
                    x_ae_temporal, x_land_state, x_phylo):
            """
            Args:
                x_continuous: (B, num_env_continuous + 64) — primary AE + env
                x_categorical: (B, num_cat) — integer indices
                x_is_introduced: (B, 1) — 0/0.5/1
                x_ae_temporal: (B, 512) — 8-year AE stack
                x_land_state: (B, 5) — land state features
                x_phylo: (B, 32) — phylogenetic embedding for each sample's species
            """
            B = x_continuous.shape[0]

            # Entity embeddings
            cat_embs = {}
            cat_emb_list = []
            if x_categorical is not None:
                for i, col_name in enumerate(self.categorical_config.keys()):
                    emb = self.embeddings[col_name](x_categorical[:, i])
                    cat_embs[col_name] = emb
                    cat_emb_list.append(emb)

            # Branch 1: Satellite (primary AE)
            x_sat = x_continuous[:, :self.NUM_SAT_DIMS]
            sat_h = self.sat_proj(x_sat)

            # Branch 2: Temporal
            temporal_h = self.temporal_module(x_ae_temporal)

            # Branch 3: Environment
            x_env = x_continuous[:, self.NUM_SAT_DIMS:]
            env_parts = [x_env] + cat_emb_list
            env_input = torch.cat(env_parts, dim=1)
            env_h = self.env_proj(env_input)

            # Branch 4: Land State
            land_h = self.land_state_proj(x_land_state)

            # Gate: blend sat vs env
            gate_parts = []
            for gf in self.gate_cat_features:
                gate_parts.append(cat_embs.get(gf,
                    torch.zeros(B, self.categorical_config[gf]["emb_dim"],
                                device=x_continuous.device)))
            is_intro = x_is_introduced if x_is_introduced is not None else \
                       torch.full((B, 1), 0.5, device=x_continuous.device)
            gate_parts.append(is_intro)
            alpha = self.gate(torch.cat(gate_parts, dim=1))

            # Fuse
            fused = alpha * sat_h + (1 - alpha) * env_h
            trunk_input = torch.cat([fused, temporal_h, land_h], dim=1)

            # Main trunk
            x = self.input_layer(trunk_input)
            x = self.res_blocks(x)

            # Phylogenetic injection (gated residual)
            phylo_h = self.phylo_proj(x_phylo)
            gate_val = self.phylo_gate(torch.cat([x, phylo_h], dim=-1))
            x = x + gate_val * phylo_h

            # Species output
            logits = self.output_layer(x)

            # Aux planted head + boost
            aux_planted = self.aux_planted_head(x)
            planted_score = torch.sigmoid(aux_planted)
            boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
            logits = logits + boost

            # Aux land state head
            aux_land_state = self.aux_land_state_head(x)

            return logits, aux_planted, aux_land_state

        def set_species_intro_ratio(self, ratio_array):
            import torch
            if isinstance(ratio_array, np.ndarray):
                ratio_array = torch.from_numpy(ratio_array).float()
            self.species_intro_ratio.copy_(ratio_array)

    return SINRModelV3, TemporalAttentionModule, ResidualBlock


# ── Step 3: Training Loop ───────────────────────────────────────────────────

def train_model():
    """Train SINR v3.0 model."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    data_path = DATA_DIR / 'sinr_v3_training_data.parquet'
    if not data_path.exists():
        log(f"ERROR: {data_path} not found. Run --extract-data first.")
        return

    log(f"Loading training data from {data_path}...")
    df = pd.read_parquet(data_path)
    log(f"Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Load phylogenetic embeddings
    phylo_path = DATA_DIR / 'species_phylo_embeddings.npz'
    if phylo_path.exists():
        phylo_data = np.load(phylo_path, allow_pickle=True)
        phylo_taxon_ids = phylo_data['taxon_ids']
        phylo_embeddings = phylo_data['embeddings']
        phylo_map = {tid: emb for tid, emb in zip(phylo_taxon_ids, phylo_embeddings)}
        log(f"Loaded phylo embeddings: {len(phylo_map):,} species, {PHYLO_DIMS}D")
    else:
        log("WARNING: No phylo embeddings found. Using zeros.")
        phylo_map = {}

    # Load species mapping
    mapping_path = DATA_DIR / 'species_mapping.json'
    if mapping_path.exists():
        with open(mapping_path) as f:
            species_mapping = json.load(f)
        species_to_idx = species_mapping['species_to_idx']
        num_species = len(species_to_idx)
        log(f"Loaded species mapping: {num_species:,} species")
    else:
        log("WARNING: No species mapping. Building from data.")
        # This would need taxon_id column in the data
        num_species = 50000  # placeholder

    # Prepare features
    log("Preparing feature tensors...")

    # Primary AE + env continuous
    ae_emb_cols_present = [c for c in AE_EMB_COLS if c in df.columns]
    env_cont_present = [c for c in ENV_CONTINUOUS_COLS if c in df.columns]
    continuous_cols = ae_emb_cols_present + env_cont_present
    continuous_data = df[continuous_cols].fillna(0).values.astype(np.float32)
    continuous_data = np.nan_to_num(continuous_data, nan=0.0, posinf=0.0, neginf=0.0)

    # Z-score normalize
    mean = continuous_data.mean(axis=0)
    std = continuous_data.std(axis=0)
    std[std < 1e-8] = 1.0
    continuous_data = (continuous_data - mean) / std

    # Save normalization stats
    np.savez(MODEL_DIR / 'normalize_stats_v3.npz',
             mean=mean, std=std, columns=np.array(continuous_cols))

    # AE temporal stack
    ae_temp_present = [c for c in AE_TEMPORAL_COLS if c in df.columns]
    if ae_temp_present:
        ae_temporal = df[ae_temp_present].fillna(0).values.astype(np.float32)
        ae_temporal = np.nan_to_num(ae_temporal, nan=0.0, posinf=0.0, neginf=0.0)
        # Normalize temporal stack independently
        ae_mean = ae_temporal.mean(axis=0)
        ae_std = ae_temporal.std(axis=0)
        ae_std[ae_std < 1e-8] = 1.0
        ae_temporal = (ae_temporal - ae_mean) / ae_std
        np.savez(MODEL_DIR / 'normalize_temporal_v3.npz', mean=ae_mean, std=ae_std)
    else:
        ae_temporal = np.zeros((len(df), 512), dtype=np.float32)
        log("WARNING: No AE temporal columns found")

    # Categorical features
    cat_cols_present = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    cat_data = np.zeros((len(df), len(CATEGORICAL_FEATURES)), dtype=np.int64)
    for i, col in enumerate(CATEGORICAL_FEATURES.keys()):
        if col in df.columns:
            cfg = CATEGORICAL_FEATURES[col]
            raw = df[col].fillna(0).astype(np.int64).values
            if cfg["value_map"]:
                mapped = np.zeros(len(raw), dtype=np.int64)
                for raw_val, idx in cfg["value_map"].items():
                    mapped[raw == raw_val] = idx
                cat_data[:, i] = mapped
            else:
                raw[(raw < 0) | (raw >= cfg["vocab_size"])] = 0
                cat_data[:, i] = raw

    # Land state features
    ls_cols_present = [c for c in LAND_STATE_COLS if c in df.columns]
    if ls_cols_present:
        land_state = df[ls_cols_present].fillna(0).values.astype(np.float32)
        land_state = np.nan_to_num(land_state, nan=0.0)
    else:
        land_state = np.zeros((len(df), 5), dtype=np.float32)
        log("WARNING: No land state columns found")

    # is_introduced
    if 'is_introduced' in df.columns:
        is_intro = df['is_introduced'].fillna(-1).values.astype(np.float32)
        is_intro[is_intro == -1] = 0.5
        is_intro = is_intro.reshape(-1, 1)
    else:
        is_intro = np.full((len(df), 1), 0.5, dtype=np.float32)

    log(f"Feature shapes:")
    log(f"  Continuous: {continuous_data.shape}")
    log(f"  AE temporal: {ae_temporal.shape}")
    log(f"  Categorical: {cat_data.shape}")
    log(f"  Land state: {land_state.shape}")
    log(f"  is_introduced: {is_intro.shape}")

    # Build model
    SINRModelV3, _, _ = build_model_classes()

    num_env_continuous = len(env_cont_present)
    model = SINRModelV3(
        num_env_continuous=num_env_continuous,
        num_species=num_species,
        categorical_config=CATEGORICAL_FEATURES,
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_RES_BLOCKS,
        dropout=DROPOUT,
        fusion_dim=FUSION_DIM,
        temporal_dim=TEMPORAL_HIDDEN,
        phylo_dim=PHYLO_DIMS,
    )

    total_params = sum(p.numel() for p in model.parameters())
    log(f"Model: {total_params:,} parameters")

    # Save model config
    config = {
        'version': '3.0',
        'num_species': num_species,
        'num_env_continuous': num_env_continuous,
        'continuous_cols': continuous_cols,
        'ae_temporal_cols': ae_temp_present,
        'categorical_config': {k: {kk: vv for kk, vv in v.items() if kk != 'value_map'}
                                for k, v in CATEGORICAL_FEATURES.items()},
        'hidden_dim': HIDDEN_DIM,
        'num_blocks': NUM_RES_BLOCKS,
        'fusion_dim': FUSION_DIM,
        'temporal_dim': TEMPORAL_HIDDEN,
        'phylo_dim': PHYLO_DIMS,
        'total_params': total_params,
    }
    with open(MODEL_DIR / 'model_config_v3.json', 'w') as f:
        json.dump(config, f, indent=2)

    log(f"\nModel architecture saved to {MODEL_DIR / 'model_config_v3.json'}")
    log("Full training loop would run here with species labels from BQ data.")
    log("Requires: species-level labels (taxon_id/species_idx) in the training data.")
    log("\nArchitecture is ready — waiting for consolidated BQ data with species labels.")


def main():
    parser = argparse.ArgumentParser(description='Train SINR v3.0')
    parser.add_argument('--extract-data', action='store_true', help='Export BQ → parquet')
    parser.add_argument('--train', action='store_true', help='Train model')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate model')
    args = parser.parse_args()

    if args.extract_data:
        extract_training_data()

    if args.train:
        train_model()

    if args.evaluate:
        log("Evaluation not yet implemented for v3.0")

    if not any([args.extract_data, args.train, args.evaluate]):
        parser.print_help()


if __name__ == '__main__':
    main()
