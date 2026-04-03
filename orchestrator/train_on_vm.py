#!/usr/bin/env python3
"""
train_on_vm.py — Self-contained SINR v3.0 training script for GCP H100 VM.

This runs entirely on the VM. All data files should already be in ~/data/ and ~/:
  - ~/data/unified_*.parquet    (exported from BQ)
  - ~/species_phylo_embeddings.npz
  - ~/species_mapping.json

Outputs saved to ~/model/:
  - best_model.pt              (best validation loss)
  - checkpoint_epochN.pt       (every epoch)
  - normalize_stats_v3.npz     (for inference)
  - normalize_temporal_v3.npz
  - model_config_v3.json
  - training_log.json          (per-epoch metrics)
  - species_mapping_v3.json    (species→index mapping)

Usage:
  python3 train_on_vm.py --train                    # Full training
  python3 train_on_vm.py --train --epochs 5         # Quick test run
  python3 train_on_vm.py --train --resume epoch_5   # Resume from checkpoint
"""

import argparse
import hashlib
import json
import os
import sys
import time
from contextlib import nullcontext
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

DATA_DIR = Path(os.path.expanduser("~/data"))
MODEL_DIR = Path(os.path.expanduser("~/model"))
HOME = Path(os.path.expanduser("~"))

# Hyperparameters
BATCH_SIZE = 16384       # H100 can handle this easily
NUM_EPOCHS = 30
LEARNING_RATE = 3e-4
LR_DECAY = 0.97         # per-epoch LR decay
WARMUP_EPOCHS = 2       # linear warmup
POS_WEIGHT = 2048.0     # BCEWithLogitsLoss weight for rare species
DROPOUT = 0.25
HIDDEN_DIM = 384
NUM_RES_BLOCKS = 6
FUSION_DIM = 192
TEMPORAL_HIDDEN = 128
PHYLO_DIMS = 32
LOCATION_ENC_FREQS = 10    # num Fourier frequencies for lat/lon encoding (2^0..2^9)
LOCATION_ENC_DIM = LOCATION_ENC_FREQS * 2 * 2  # sin+cos for lat and lon = 40D
VAL_FRACTION = 0.05
NUM_WORKERS = 8
PATIENCE = 7            # early stopping patience
GRAD_CLIP = 1.0

# Feature columns (must match BQ schema)
AE_EMB_COLS = [f"emb_{i:02d}" for i in range(64)]
AE_TEMPORAL_COLS = [f"ae_{y}_{b:02d}" for y in range(2017, 2025) for b in range(64)]

ENV_CONTINUOUS_COLS = [
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    "treecover2000", "lossyear",
    "gedi_canopy_height_m", "gedi_foliage_height_div",
    "biomass_agb_mgha",
    "water_occurrence", "water_recurrence", "water_seasonality",
    "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world", "sbtn_natural_land",
    "neumann_natural_prob",
    "tc_vpd_mean", "tc_aet_mean", "tc_soil_moisture_mean",
    "tc_pdsi_mean", "tc_water_deficit_mean", "tc_solar_rad_mean",
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "modis_gpp_mean",
    "carbon_canopy_height_m",
    "spawn_agb", "spawn_agb_unc", "spawn_bgb", "spawn_bgb_unc",
    "gedi_l4b_agbd", "gedi_l4b_agbd_se", "gedi_rh98", "gedi_fhd",
    "soc_0cm", "soc_30cm", "soc_100cm", "soc_200cm",
    "npp_at_obs", "gpp_at_obs", "lai_at_obs", "fpar_at_obs", "evi_at_obs",
    "cci_agb_at_obs", "cci_agb_sd_at_obs",
    "npp_at_ae", "gpp_at_ae", "lai_at_ae", "fpar_at_ae", "evi_at_ae",
    "cci_agb_at_ae", "cci_agb_sd_at_ae",
    "npp_mean_longterm", "npp_trend",
    "aridity_index", "et0_mm_yr",
    "hilda_lulc_at_obs", "hilda_lulc_at_ae",
]

CATEGORICAL_FEATURES = {
    "jrc_forest_type": {"vocab_size": 5, "emb_dim": 3,
                         "value_map": {0: 1, 1: 2, 10: 3, 20: 4}},
    "xiao_planted_forest": {"vocab_size": 4, "emb_dim": 3,
                             "value_map": {0: 1, 1: 2, 2: 3}},
    "eco_id": {"vocab_size": 850, "emb_dim": 32, "value_map": None},
    "biome_num": {"vocab_size": 16, "emb_dim": 8, "value_map": None},
    "soil_texture_class": {"vocab_size": 14, "emb_dim": 6, "value_map": None},
    "ipcc_forest_class": {"vocab_size": 10, "emb_dim": 4, "value_map": None},
}

LAND_STATE_COLS = [
    "land_state_class", "disturbance_intensity", "forest_stability",
    "successional_stage", "ae_temporal_change_l2",
]

# Test locations for per-epoch inference demo
TEST_LOCATIONS = {
    "NZ Radiata Pine": {"lat": -41.1508, "lon": 175.0997},  # Introduced Pinus radiata plantation
    "Amazon (Manaus)": {"lat": -3.12, "lon": -60.02},
    "Congo Basin": {"lat": 1.45, "lon": 25.20},
    "Borneo": {"lat": 1.50, "lon": 110.35},
    "Pacific NW (Oregon)": {"lat": 44.05, "lon": -122.75},
}


def encode_location_sinusoidal(lat, lon, num_freqs=LOCATION_ENC_FREQS):
    """Sinusoidal positional encoding for geographic coordinates.

    Converts lat/lon to multi-scale Fourier features. Each frequency captures
    geographic patterns at a different scale: low frequencies distinguish
    continents, high frequencies distinguish neighborhoods.

    Args:
        lat: latitude(s) in degrees, scalar or numpy array
        lon: longitude(s) in degrees, scalar or numpy array
        num_freqs: number of frequency bands (default 16 -> 64D output)

    Returns:
        numpy array of shape (..., num_freqs * 4) with sin/cos of lat and lon
        at exponentially spaced frequencies.
    """
    lat = np.asarray(lat, dtype=np.float32)
    lon = np.asarray(lon, dtype=np.float32)
    # Normalize to [-1, 1] range
    lat_norm = lat / 90.0
    lon_norm = lon / 180.0
    # Exponentially spaced frequencies: 2^0 to 2^(num_freqs-1)
    # Default 10 freqs: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    # Low freqs capture continents, high freqs capture ~100km-scale patterns
    freqs = 2.0 ** np.arange(num_freqs, dtype=np.float32)
    freqs_pi = freqs * np.pi
    # Outer product: each coordinate × each frequency
    lat_enc = lat_norm[..., None] * freqs_pi[None, :]  # (..., num_freqs)
    lon_enc = lon_norm[..., None] * freqs_pi[None, :]
    # Sin and cos for both
    result = np.concatenate([
        np.sin(lat_enc), np.cos(lat_enc),
        np.sin(lon_enc), np.cos(lon_enc),
    ], axis=-1)  # (..., num_freqs * 4)
    return result.astype(np.float32)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _mapping_sha256(species_to_idx):
    payload = json.dumps(species_to_idx, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_species_mapping(species_to_idx):
    idx_values = sorted(set(int(v) for v in species_to_idx.values()))
    if not idx_values:
        raise ValueError("Species mapping is empty")
    expected = list(range(len(idx_values)))
    if idx_values != expected:
        raise ValueError("Species mapping indices must be contiguous 0..N-1")


def _load_species_mapping(mapping_path, mapping_contract_path=None):
    source_path = mapping_contract_path if mapping_contract_path else mapping_path
    with open(source_path) as f:
        payload = json.load(f)

    if "species_to_idx" not in payload:
        raise ValueError(f"Invalid mapping payload (missing species_to_idx): {source_path}")

    species_to_idx = {str(k): int(v) for k, v in payload["species_to_idx"].items()}
    _validate_species_mapping(species_to_idx)

    idx_to_species = {int(v): str(k) for k, v in species_to_idx.items()}
    mapping_meta = {
        "source_path": str(source_path),
        "num_species": len(idx_to_species),
        "mapping_sha256": _mapping_sha256(species_to_idx),
    }
    return species_to_idx, idx_to_species, mapping_meta


def _load_frozen_stats(stats_path, expected_len):
    stats = np.load(stats_path, allow_pickle=True)
    mean = stats["mean"].astype(np.float32)
    std = stats["std"].astype(np.float32)
    std[std < 1e-8] = 1.0
    if len(mean) != expected_len or len(std) != expected_len:
        raise ValueError(
            f"Frozen stats shape mismatch for {stats_path}: "
            f"got {len(mean)}, expected {expected_len}"
        )
    return mean, std


def _load_feature_contract(feature_contract_path):
    with open(feature_contract_path) as f:
        payload = json.load(f)
    cols = payload.get("env_continuous_cols")
    if cols is None or not isinstance(cols, list):
        raise ValueError(f"Invalid feature contract: {feature_contract_path}")
    cols = [str(c) for c in cols]
    if len(set(cols)) != len(cols):
        raise ValueError("Feature contract env_continuous_cols must be unique")
    categorical_features = payload.get("categorical_features")
    if categorical_features is None or not isinstance(categorical_features, list):
        raise ValueError(f"Invalid feature contract categorical_features: {feature_contract_path}")
    categorical_features = [str(c) for c in categorical_features]

    land_state_cols = payload.get("land_state_cols")
    if land_state_cols is None or not isinstance(land_state_cols, list):
        raise ValueError(f"Invalid feature contract land_state_cols: {feature_contract_path}")
    land_state_cols = [str(c) for c in land_state_cols]

    return payload, cols, categorical_features, land_state_cols


def _load_species_frequency_contract(freq_contract_path, mapping_sha, num_species,
                                      weight_mode="gamma", effective_cap=0):
    with open(freq_contract_path) as f:
        payload = json.load(f)

    contract_sha = payload.get("mapping_sha256")
    if contract_sha and contract_sha != mapping_sha:
        raise ValueError(
            "Species frequency contract mapping hash mismatch: "
            f"expected={mapping_sha}, got={contract_sha}"
        )

    counts = payload.get("class_counts")
    if counts is None:
        raise ValueError("Species frequency contract missing class_counts")

    if isinstance(counts, dict):
        class_counts = np.zeros(num_species, dtype=np.float32)
        for k, v in counts.items():
            idx = int(k)
            if 0 <= idx < num_species:
                class_counts[idx] = float(v)
    else:
        class_counts = np.asarray(counts, dtype=np.float32)

    if class_counts.shape[0] != num_species:
        raise ValueError(
            f"Frequency contract class_counts size mismatch: got={class_counts.shape[0]}, expected={num_species}"
        )

    class_counts = np.clip(class_counts, 1.0, None)

    if weight_mode == "effective_cap" and effective_cap > 0:
        # Soft cap: weight = min(cap, count) / count
        # Mathematically equivalent to hard-cap in gradient contribution
        # but preserves all data (no rows deleted).
        # Species below cap: weight = 1.0 (unchanged)
        # Species above cap: weight = cap/count (downweighted proportionally)
        cap = float(effective_cap)
        weights = np.minimum(cap, class_counts) / class_counts
        weights = weights.astype(np.float32)
        log(f"  Weight mode: effective_cap={effective_cap} "
            f"(species above cap: {int((class_counts > cap).sum()):,}, "
            f"below: {int((class_counts <= cap).sum()):,})")
    else:
        # Legacy gamma mode: weight = (median/count)^gamma, clamped
        median_count = float(np.median(class_counts))
        gamma = float(payload.get("weight_gamma", 0.5))
        weights = np.power(median_count / class_counts, gamma).astype(np.float32)
        weights = np.clip(weights, 0.25, 16.0)

    return payload, class_counts, weights


def _load_intro_ratio_contract(intro_ratio_contract_path, mapping_sha, num_species):
    with open(intro_ratio_contract_path) as f:
        payload = json.load(f)

    contract_sha = payload.get("mapping_sha256")
    if contract_sha and contract_sha != mapping_sha:
        raise ValueError(
            "Intro-ratio contract mapping hash mismatch: "
            f"expected={mapping_sha}, got={contract_sha}"
        )

    ratios = payload.get("species_intro_ratio")
    if ratios is None:
        raise ValueError("Intro-ratio contract missing species_intro_ratio")

    intro_ratio = np.asarray(ratios, dtype=np.float32)
    if intro_ratio.shape[0] != num_species:
        raise ValueError(
            "Intro-ratio contract length mismatch: "
            f"got={intro_ratio.shape[0]}, expected={num_species}"
        )
    intro_ratio = np.clip(intro_ratio, 0.0, 1.0)
    return payload, intro_ratio


def _compute_species_weighted_bce_loss(criterion_no_reduce, logits, target_one_hot, targets, species_weights=None):
    import torch
    per_elem = criterion_no_reduce(logits, target_one_hot)  # [B, C]
    per_sample = per_elem.mean(dim=1)  # [B]

    if species_weights is not None:
        valid = targets >= 0
        if valid.any():
            w = species_weights[targets.clamp(min=0)]
            w = torch.where(valid, w, torch.ones_like(w))
            per_sample = per_sample * w

    return per_sample.mean()


def _compute_an_full_loss(logits, targets, species_weights=None, pos_weight=POS_WEIGHT):
    """Assumed-negative full loss (SINR-style), with optional per-species sample weighting."""
    import torch
    import torch.nn.functional as F

    batch_size, num_species = logits.shape
    valid = targets >= 0
    if not valid.any():
        return logits.sum() * 0.0

    v_logits = logits[valid]
    v_targets = targets[valid]

    log_pos = F.logsigmoid(v_logits)
    log_neg = F.logsigmoid(-v_logits)

    # Mean assumed-negative over all species
    loss_neg = -log_neg.mean(dim=1)

    # Replace target's negative term with weighted positive term
    t_log_pos = log_pos.gather(1, v_targets.unsqueeze(1)).squeeze(1)
    t_log_neg = log_neg.gather(1, v_targets.unsqueeze(1)).squeeze(1)
    correction = (t_log_neg + pos_weight * (-t_log_pos)) / num_species
    loss_per = loss_neg + correction

    if species_weights is not None:
        loss_per = loss_per * species_weights[v_targets]

    return loss_per.mean()


# ── Model Architecture ──────────────────────────────────────────────────────

def build_model():
    import torch
    import torch.nn as nn

    class ResidualBlock(nn.Module):
        def __init__(self, dim, dropout):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(dim, dim),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(dim, dim),
                nn.GELU(),
            )

        def forward(self, x):
            return x + self.net(x)

    class TemporalAttentionModule(nn.Module):
        def __init__(self, embed_dim=64, n_years=8, output_dim=128,
                     use_magnitude=False):
            super().__init__()
            self.embed_dim = embed_dim
            self.n_years = n_years
            self.use_magnitude = use_magnitude
            self.year_embed = nn.Embedding(n_years, embed_dim)
            self.attn = nn.MultiheadAttention(embed_dim, num_heads=4,
                                               batch_first=True, dropout=0.1)
            self.diff_proj = nn.Linear(embed_dim, output_dim // 4)
            self.first_last_proj = nn.Linear(embed_dim, output_dim // 4)
            pre_proj_dim = embed_dim * 2 + output_dim // 4 + output_dim // 4
            if use_magnitude:
                # 7 inter-year L2 norms + variance + max = 9 scalars
                self.mag_proj = nn.Linear(9, output_dim // 4)
                pre_proj_dim += output_dim // 4
            self.output_proj = nn.Linear(pre_proj_dim, output_dim)

        def forward(self, ae_temporal):
            B = ae_temporal.shape[0]
            x = ae_temporal.view(B, self.n_years, self.embed_dim)
            year_ids = torch.arange(self.n_years, device=x.device)
            x = x + self.year_embed(year_ids).unsqueeze(0)
            attended, _ = self.attn(x, x, x)
            pooled_mean = attended.mean(dim=1)
            pooled_max = attended.max(dim=1).values
            diffs = x[:, 1:] - x[:, :-1]
            diff_feat = self.diff_proj(diffs.mean(dim=1))
            first_last = self.first_last_proj(x[:, -1] - x[:, 0])
            parts = [pooled_mean, pooled_max, diff_feat, first_last]
            if self.use_magnitude:
                # Inter-year L2 distances (7 scalars)
                mag = torch.norm(diffs, dim=2)  # (B, 7)
                mag_var = mag.var(dim=1, keepdim=True)    # (B, 1)
                mag_max = mag.max(dim=1, keepdim=True).values  # (B, 1)
                mag_feat = torch.cat([mag, mag_var, mag_max], dim=1)  # (B, 9)
                parts.append(self.mag_proj(mag_feat))
            combined = torch.cat(parts, dim=-1)
            return self.output_proj(combined)

    class SINRModelV3(nn.Module):
        NUM_SAT_DIMS = 64

        def __init__(self, num_env_continuous, num_species, categorical_config=None,
                     hidden_dim=384, num_blocks=6, dropout=0.25, fusion_dim=192,
                     temporal_dim=128, phylo_dim=32, land_state_dim=32,
                     gate_use_intro=True, intro_residual=False,
                     location_enc_dim=0, use_temporal_magnitude=False,
                     land_state_input_dim=5, **kwargs):
            super().__init__()
            self.num_env_continuous = num_env_continuous
            self.num_species = num_species
            self.categorical_config = categorical_config or {}
            self.hidden_dim = hidden_dim
            self.fusion_dim = fusion_dim
            self.gate_use_intro = gate_use_intro
            self.intro_residual = intro_residual
            self.location_enc_dim = location_enc_dim

            # Entity embeddings
            self.embeddings = nn.ModuleDict()
            total_emb_dim = 0
            for col_name, cfg in self.categorical_config.items():
                self.embeddings[col_name] = nn.Embedding(
                    cfg["vocab_size"], cfg["emb_dim"], padding_idx=0)
                total_emb_dim += cfg["emb_dim"]
            self.total_emb_dim = total_emb_dim

            # Branch 1: Satellite
            self.sat_proj = nn.Sequential(
                nn.Linear(self.NUM_SAT_DIMS, fusion_dim), nn.GELU())

            # Branch 2: Temporal
            self.temporal_module = TemporalAttentionModule(
                embed_dim=64, n_years=8, output_dim=temporal_dim,
                use_magnitude=use_temporal_magnitude)

            # Branch 3: Environment
            self.env_input_dim = num_env_continuous + total_emb_dim
            if self.env_input_dim > 0:
                self.env_proj = nn.Sequential(
                    nn.Linear(self.env_input_dim, fusion_dim), nn.GELU())
            else:
                self.env_proj = None

            # Branch 4: Land State (6D when planted_as_land_state, else 5D)
            self.land_state_input_dim = land_state_input_dim
            self.land_state_dim = land_state_dim if land_state_input_dim > 0 else 0
            if land_state_input_dim > 0:
                self.land_state_proj = nn.Sequential(
                    nn.Linear(land_state_input_dim, self.land_state_dim), nn.GELU())
            else:
                self.land_state_proj = None

            # Branch 5: Location encoding (sinusoidal, optional)
            loc_dim = 0
            if location_enc_dim > 0:
                loc_dim = 64  # projection output dim
                self.location_proj = nn.Sequential(
                    nn.Linear(location_enc_dim, loc_dim), nn.GELU())

            # Gate
            gate_input_dim = 0
            self.gate_cat_features = []
            for gf in ["jrc_forest_type"]:
                if gf in self.categorical_config:
                    gate_input_dim += self.categorical_config[gf]["emb_dim"]
                    self.gate_cat_features.append(gf)
            if self.gate_use_intro:
                gate_input_dim += 1
            self.gate_input_dim = gate_input_dim
            if gate_input_dim > 0:
                self.gate = nn.Sequential(
                    nn.Linear(gate_input_dim, 16), nn.GELU(),
                    nn.Linear(16, 1), nn.Sigmoid())
            else:
                self.gate = None

            # Main trunk
            trunk_input = fusion_dim + temporal_dim + self.land_state_dim + loc_dim
            self.input_layer = nn.Sequential(
                nn.Linear(trunk_input, hidden_dim), nn.GELU())
            self.res_blocks = nn.Sequential(
                *[ResidualBlock(hidden_dim, dropout) for _ in range(num_blocks)])

            # Separate introduced residual path (kept out of gate routing)
            if self.intro_residual:
                self.intro_proj = nn.Sequential(
                    nn.Linear(1, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, hidden_dim)
                )
                self.intro_scale = nn.Parameter(torch.tensor(0.2))

            # Phylogenetic injection
            self.phylo_proj = nn.Sequential(
                nn.Linear(phylo_dim, hidden_dim), nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim))
            self.phylo_gate = nn.Sequential(
                nn.Linear(hidden_dim * 2, 1), nn.Sigmoid())

            # Output heads
            self.output_layer = nn.Linear(hidden_dim, num_species, bias=False)
            self.aux_planted_head = nn.Linear(hidden_dim, 1)
            self.aux_land_state_head = nn.Linear(hidden_dim, 6)
            self.boost_scale = nn.Parameter(torch.tensor(2.0))
            self.register_buffer("species_intro_ratio", torch.zeros(num_species))

        def forward(self, x_continuous, x_categorical, x_is_introduced,
                    x_ae_temporal, x_land_state, x_phylo, x_location=None):
            B = x_continuous.shape[0]
            cat_embs = {}
            cat_emb_list = []
            if x_categorical is not None:
                for i, col_name in enumerate(self.categorical_config.keys()):
                    emb = self.embeddings[col_name](x_categorical[:, i])
                    cat_embs[col_name] = emb
                    cat_emb_list.append(emb)

            x_sat = x_continuous[:, :self.NUM_SAT_DIMS]
            sat_h = self.sat_proj(x_sat)
            temporal_h = self.temporal_module(x_ae_temporal)
            x_env = x_continuous[:, self.NUM_SAT_DIMS:]
            if self.env_input_dim > 0:
                env_input = torch.cat([x_env] + cat_emb_list, dim=1)
                env_h = self.env_proj(env_input)
            else:
                env_h = torch.zeros(B, self.fusion_dim, device=x_continuous.device)
            if self.land_state_proj is not None:
                land_h = self.land_state_proj(x_land_state)
            else:
                land_h = None

            # Gate
            gate_parts = []
            for gf in self.gate_cat_features:
                gate_parts.append(cat_embs.get(gf,
                    torch.zeros(B, self.categorical_config[gf]["emb_dim"],
                                device=x_continuous.device)))
            is_intro = x_is_introduced if x_is_introduced is not None else \
                       torch.full((B, 1), 0.5, device=x_continuous.device)
            if self.gate_use_intro:
                gate_parts.append(is_intro)
            if self.gate is not None:
                alpha = self.gate(torch.cat(gate_parts, dim=1))
            else:
                alpha = torch.full((B, 1), 0.5, device=x_continuous.device)

            fused = alpha * sat_h + (1 - alpha) * env_h
            trunk_parts = [fused, temporal_h]
            if land_h is not None:
                trunk_parts.append(land_h)
            if self.location_enc_dim > 0 and x_location is not None:
                trunk_parts.append(self.location_proj(x_location))
            trunk_input = torch.cat(trunk_parts, dim=1)
            x = self.input_layer(trunk_input)
            x = self.res_blocks(x)

            if self.intro_residual:
                x = x + self.intro_scale * self.intro_proj(is_intro)

            # Phylo injection
            phylo_h = self.phylo_proj(x_phylo)
            gate_val = self.phylo_gate(torch.cat([x, phylo_h], dim=-1))
            x = x + gate_val * phylo_h

            logits = self.output_layer(x)
            aux_planted = self.aux_planted_head(x)
            if not getattr(self, '_no_boost', False):
                planted_score = torch.sigmoid(aux_planted)
                if self.training and getattr(self, '_disable_boost_in_training', False):
                    boost = torch.zeros_like(logits)
                else:
                    boost = planted_score * self.species_intro_ratio.unsqueeze(0) * self.boost_scale
                logits = logits + boost
            aux_land_state = self.aux_land_state_head(x)

            return logits, aux_planted, aux_land_state

    return SINRModelV3


# ── Dataset ──────────────────────────────────────────────────────────────────

class SINRDataset:
    """Memory-efficient dataset that loads parquet chunks on demand."""

    def __init__(
        self,
        data_dir,
        species_to_idx,
        phylo_map,
        require_full_contract=False,
        frozen_cont_stats=None,
        frozen_temporal_stats=None,
        zero_phylo_input=False,
        hard_cap_per_species=0,
        planted_as_land_state=False,
    ):
        import torch
        self.torch = torch
        self.species_to_idx = species_to_idx
        self.phylo_map = phylo_map
        self.num_species = len(species_to_idx)
        self.require_full_contract = require_full_contract
        self.frozen_cont_stats = frozen_cont_stats
        self.frozen_temporal_stats = frozen_temporal_stats
        self.zero_phylo_input = zero_phylo_input
        self.hard_cap_per_species = hard_cap_per_species
        self.planted_as_land_state = planted_as_land_state

        # Load all parquet files
        parquet_files = sorted(data_dir.glob("unified_*.parquet"))
        if not parquet_files:
            parquet_files = sorted(data_dir.glob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files in {data_dir}")

        log(f"Loading {len(parquet_files)} parquet files...")
        dfs = []
        for f in parquet_files:
            dfs.append(pd.read_parquet(f))
            log(f"  {f.name}: {len(dfs[-1]):,} rows")
        self.df = pd.concat(dfs, ignore_index=True)
        log(f"Total: {len(self.df):,} rows, {len(self.df.columns)} columns")

        # Filter to rows with valid taxon_id that maps to a known species
        if 'taxon_id' in self.df.columns:
            valid_mask = self.df['taxon_id'].isin(species_to_idx)
            before = len(self.df)
            self.df = self.df[valid_mask].reset_index(drop=True)
            log(f"Filtered to known species: {len(self.df):,} / {before:,} rows")
        else:
            log("WARNING: No taxon_id column. Cannot create species labels.")

        # Filter out rows with observation_year < 1900 (sentinel values)
        if 'observation_year' in self.df.columns:
            valid_yr = self.df['observation_year'] >= 1900
            before = len(self.df)
            self.df = self.df[valid_yr].reset_index(drop=True)
            log(f"Filtered valid years (>=1900): {len(self.df):,} / {before:,} rows")

        # Apply hard cap per species (v2.2 used 50000 to prevent dominant species)
        if self.hard_cap_per_species > 0 and 'taxon_id' in self.df.columns:
            before = len(self.df)
            self.df = self.df.groupby("taxon_id", group_keys=False).apply(
                lambda g: g.sample(n=min(len(g), self.hard_cap_per_species), random_state=42)
            )
            self.df = self.df.reset_index(drop=True)
            log(f"Hard cap {self.hard_cap_per_species}/species: {before:,} → {len(self.df):,} rows")

        self._prepare_arrays()

    def _prepare_arrays(self):
        """Convert dataframe to numpy arrays for fast tensor creation."""
        log("Preparing feature arrays...")

        # Continuous: primary AE (64D) + env
        if self.require_full_contract:
            missing_ae = [c for c in AE_EMB_COLS if c not in self.df.columns]
            missing_env = [c for c in ENV_CONTINUOUS_COLS if c not in self.df.columns]
            if missing_ae or missing_env:
                raise ValueError(
                    "Missing required continuous columns for strict contract. "
                    f"AE missing={len(missing_ae)}, Env missing={len(missing_env)}"
                )
            ae_cols = list(AE_EMB_COLS)
            env_cols = list(ENV_CONTINUOUS_COLS)
        else:
            ae_cols = [c for c in AE_EMB_COLS if c in self.df.columns]
            env_cols = [c for c in ENV_CONTINUOUS_COLS if c in self.df.columns]
        self.continuous_cols = ae_cols + env_cols
        self.num_ae = len(ae_cols)
        self.num_env = len(env_cols)

        cont = self.df[self.continuous_cols].values.astype(np.float32)
        cont = np.nan_to_num(cont, nan=0.0, posinf=0.0, neginf=0.0)

        # Clamp MODIS GPP fill codes (65530-65535 are land-cover fill, not valid GPP)
        if 'modis_gpp_mean' in self.continuous_cols:
            gpp_idx = self.continuous_cols.index('modis_gpp_mean')
            cont[:, gpp_idx] = np.where(cont[:, gpp_idx] >= 65530, 0.0, cont[:, gpp_idx])

        # NOTE: GEDI canopy height is NOT clipped. Trees can exceed 80m and even 100m.
        # Previous 0..80 clip was unjustified and has been removed (2026-03-17 audit).
        # If GEDI semantics need guarding, exclude the column at the table-build level
        # (as V4.1 preview does) rather than silently clipping valid values here.

        # Z-score normalize
        if self.frozen_cont_stats is not None:
            self.cont_mean, self.cont_std = self.frozen_cont_stats
        else:
            self.cont_mean = cont.mean(axis=0)
            self.cont_std = cont.std(axis=0)
            self.cont_std[self.cont_std < 1e-8] = 1.0
        self.continuous = (cont - self.cont_mean) / self.cont_std

        # AE temporal (512D)
        if self.require_full_contract:
            missing_temp = [c for c in AE_TEMPORAL_COLS if c not in self.df.columns]
            if missing_temp:
                raise ValueError(
                    f"Missing required AE temporal columns for strict contract: {len(missing_temp)}"
                )
            ae_temp_cols = list(AE_TEMPORAL_COLS)
        else:
            ae_temp_cols = [c for c in AE_TEMPORAL_COLS if c in self.df.columns]
        if ae_temp_cols:
            ae_temp = self.df[ae_temp_cols].values.astype(np.float32)
            ae_temp = np.nan_to_num(ae_temp, nan=0.0, posinf=0.0, neginf=0.0)
            if self.frozen_temporal_stats is not None:
                self.ae_temp_mean, self.ae_temp_std = self.frozen_temporal_stats
            else:
                self.ae_temp_mean = ae_temp.mean(axis=0)
                self.ae_temp_std = ae_temp.std(axis=0)
                self.ae_temp_std[self.ae_temp_std < 1e-8] = 1.0
            self.ae_temporal = (ae_temp - self.ae_temp_mean) / self.ae_temp_std
        else:
            self.ae_temporal = np.zeros((len(self.df), 512), dtype=np.float32)
            self.ae_temp_mean = np.zeros(512, dtype=np.float32)
            self.ae_temp_std = np.ones(512, dtype=np.float32)

        # Categorical
        self.cat_data = np.zeros((len(self.df), len(CATEGORICAL_FEATURES)), dtype=np.int64)
        for i, (col, cfg) in enumerate(CATEGORICAL_FEATURES.items()):
            if col in self.df.columns:
                raw = self.df[col].fillna(0).astype(np.int64).values
                if cfg["value_map"]:
                    mapped = np.zeros(len(raw), dtype=np.int64)
                    for raw_val, idx in cfg["value_map"].items():
                        mapped[raw == int(raw_val)] = idx
                    self.cat_data[:, i] = mapped
                else:
                    raw[(raw < 0) | (raw >= cfg["vocab_size"])] = 0
                    self.cat_data[:, i] = raw

        # Land state
        ls_cols = [c for c in LAND_STATE_COLS if c in self.df.columns]
        if LAND_STATE_COLS and ls_cols:
            self.land_state = self.df[ls_cols].fillna(0).values.astype(np.float32)
            # Pad to 5 cols if fewer
            if self.land_state.shape[1] < 5:
                pad = np.zeros((len(self.df), 5 - self.land_state.shape[1]), dtype=np.float32)
                self.land_state = np.hstack([self.land_state, pad])
        else:
            width = 6 if self.planted_as_land_state else (5 if LAND_STATE_COLS else 0)
            self.land_state = np.zeros((len(self.df), width), dtype=np.float32)

        # Append is_planted as 6th land_state dimension if requested
        if self.planted_as_land_state and 'xiao_planted_forest' in CATEGORICAL_FEATURES:
            xiao_idx = list(CATEGORICAL_FEATURES.keys()).index('xiao_planted_forest')
            is_planted = (self.cat_data[:, xiao_idx] == 3).astype(np.float32).reshape(-1, 1)
            if self.land_state.shape[1] == 0:
                self.land_state = is_planted
            elif self.land_state.shape[1] == 5:
                self.land_state = np.hstack([self.land_state, is_planted])
            n_planted = int(is_planted.sum())
            log(f"  is_planted appended to land_state: {n_planted:,}/{len(is_planted):,} = {100*n_planted/len(is_planted):.1f}%")

        # is_introduced
        if 'is_introduced' in self.df.columns:
            is_intro = self.df['is_introduced'].fillna(-1).values.astype(np.float32)
            is_intro[is_intro == -1] = 0.5
            self.is_introduced = is_intro.reshape(-1, 1)
        else:
            self.is_introduced = np.full((len(self.df), 1), 0.5, dtype=np.float32)

        # Species labels (target)
        if 'taxon_id' in self.df.columns:
            self.species_idx = np.array(
                [self.species_to_idx.get(tid, -1) for tid in self.df['taxon_id'].values],
                dtype=np.int64)
        else:
            self.species_idx = np.zeros(len(self.df), dtype=np.int64)

        # Per-species introduced ratio from this dataset slice
        valid_species = self.species_idx >= 0
        intro_known = np.isin(self.is_introduced[:, 0], [0.0, 1.0])
        ratio_mask = valid_species & intro_known
        if ratio_mask.any():
            sp = self.species_idx[ratio_mask]
            intro_vals = self.is_introduced[ratio_mask, 0]
            denom = np.bincount(sp, minlength=self.num_species).astype(np.float32)
            numer = np.bincount(sp, weights=intro_vals, minlength=self.num_species).astype(np.float32)
            self.species_intro_ratio = np.divide(
                numer,
                np.maximum(denom, 1.0),
                out=np.zeros_like(numer, dtype=np.float32),
                where=denom > 0,
            ).astype(np.float32)
        else:
            self.species_intro_ratio = np.zeros(self.num_species, dtype=np.float32)

        # Phylogenetic embeddings per sample
        if self.phylo_map and 'taxon_id' in self.df.columns and not self.zero_phylo_input:
            default_phylo = np.zeros(PHYLO_DIMS, dtype=np.float32)
            self.phylo = np.array(
                [self.phylo_map.get(tid, default_phylo) for tid in self.df['taxon_id'].values],
                dtype=np.float32)
        else:
            self.phylo = np.zeros((len(self.df), PHYLO_DIMS), dtype=np.float32)

        # Location encoding (sinusoidal from lat/lon)
        if 'latitude' in self.df.columns and 'longitude' in self.df.columns:
            lat = self.df['latitude'].fillna(0).values.astype(np.float32)
            lon = self.df['longitude'].fillna(0).values.astype(np.float32)
            self.location_enc = encode_location_sinusoidal(lat, lon)
        else:
            self.location_enc = np.zeros(
                (len(self.df), LOCATION_ENC_DIM), dtype=np.float32)

        # Free the dataframe
        del self.df
        log(f"Arrays ready: {self.continuous.shape[0]:,} samples")
        log(f"  Continuous: {self.continuous.shape} (AE:{self.num_ae} + Env:{self.num_env})")
        log(f"  AE temporal: {self.ae_temporal.shape}")
        log(f"  Categorical: {self.cat_data.shape}")
        log(f"  Land state: {self.land_state.shape}")
        log(f"  Location enc: {self.location_enc.shape}")

    def __len__(self):
        return len(self.species_idx)

    def get_batch(self, indices):
        """Get a batch of tensors for given indices."""
        torch = self.torch
        return {
            'continuous': torch.from_numpy(self.continuous[indices]),
            'categorical': torch.from_numpy(self.cat_data[indices]),
            'is_introduced': torch.from_numpy(self.is_introduced[indices]),
            'ae_temporal': torch.from_numpy(self.ae_temporal[indices]),
            'land_state': torch.from_numpy(self.land_state[indices]),
            'phylo': torch.from_numpy(self.phylo[indices]),
            'location_enc': torch.from_numpy(self.location_enc[indices]),
            'species_idx': torch.from_numpy(self.species_idx[indices]),
        }


# ── Training Loop ────────────────────────────────────────────────────────────

def train(args):
    import torch
    import torch.nn as nn
    global ENV_CONTINUOUS_COLS
    global CATEGORICAL_FEATURES
    global LAND_STATE_COLS

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else DATA_DIR
    model_dir = Path(args.model_dir).expanduser() if args.model_dir else MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)

    batch_size = args.batch_size if args.batch_size else BATCH_SIZE

    requested_device = getattr(args, 'device', 'auto')
    if requested_device == 'cuda':
        if not torch.cuda.is_available():
            log("ERROR: --device cuda requested but CUDA is unavailable")
            return
        device = torch.device("cuda")
    elif requested_device == 'mps':
        if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            log("ERROR: --device mps requested but MPS is unavailable")
            return
        device = torch.device("mps")
    elif requested_device == 'cpu':
        device = torch.device("cpu")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    log(f"Device: {device}")
    if device.type == "cuda":
        log(f"GPU: {torch.cuda.get_device_name(0)}")
        log(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
    elif device.type == "mps":
        log("Using Apple Silicon MPS backend")

    feature_contract_meta = None
    if args.feature_contract:
        feature_contract_path = Path(args.feature_contract).expanduser()
        if not feature_contract_path.exists():
            log(f"ERROR: feature contract not found: {feature_contract_path}")
            return
        feature_contract_meta, contract_env_cols, contract_cat_cols, contract_land_state_cols = _load_feature_contract(feature_contract_path)
        ENV_CONTINUOUS_COLS = contract_env_cols
        CATEGORICAL_FEATURES = {k: v for k, v in CATEGORICAL_FEATURES.items() if k in contract_cat_cols}
        LAND_STATE_COLS = [c for c in LAND_STATE_COLS if c in contract_land_state_cols]
        log(
            f"Feature contract: {feature_contract_meta.get('version', 'unknown')} | "
            f"env_continuous={len(ENV_CONTINUOUS_COLS)} | "
            f"categorical={len(CATEGORICAL_FEATURES)} | land_state={len(LAND_STATE_COLS)} | "
            f"source={feature_contract_path}"
        )

    # Load species mapping (versioned contract can override legacy mapping path)
    mapping_path = Path(args.mapping_path).expanduser() if args.mapping_path else (HOME / 'species_mapping.json')
    mapping_contract_path = Path(args.mapping_contract).expanduser() if args.mapping_contract else None
    if not mapping_path.exists() and mapping_contract_path is None:
        log("ERROR: mapping file not found. Provide --mapping-path or --mapping-contract.")
        return
    if mapping_contract_path is not None and not mapping_contract_path.exists():
        log(f"ERROR: mapping contract not found: {mapping_contract_path}")
        return

    species_to_idx, idx_to_species, mapping_meta = _load_species_mapping(
        mapping_path, mapping_contract_path=mapping_contract_path
    )
    num_species = len(idx_to_species)
    log(
        f"Species mapping: {num_species:,} species | "
        f"sha={mapping_meta['mapping_sha256'][:12]} | source={mapping_meta['source_path']}"
    )

    frozen_cont_stats = None
    frozen_temporal_stats = None
    if args.frozen_cont_stats:
        cont_stats_path = Path(args.frozen_cont_stats).expanduser()
        frozen_cont_stats = _load_frozen_stats(cont_stats_path, len(AE_EMB_COLS) + len(ENV_CONTINUOUS_COLS))
        log(f"Using frozen continuous stats: {cont_stats_path}")
    if args.frozen_temporal_stats:
        temp_stats_path = Path(args.frozen_temporal_stats).expanduser()
        frozen_temporal_stats = _load_frozen_stats(temp_stats_path, len(AE_TEMPORAL_COLS))
        log(f"Using frozen temporal stats: {temp_stats_path}")

    # Load phylogenetic embeddings
    phylo_path = HOME / 'species_phylo_embeddings.npz'
    phylo_map = {}
    if phylo_path.exists():
        phylo_data = np.load(phylo_path, allow_pickle=True)
        for tid, emb in zip(phylo_data['taxon_ids'], phylo_data['embeddings']):
            phylo_map[str(tid)] = emb.astype(np.float32)
        log(f"Phylo embeddings: {len(phylo_map):,} species, {PHYLO_DIMS}D")

    # Load dataset
    planted_as_ls = getattr(args, 'planted_as_land_state', False)
    dataset = SINRDataset(
        data_dir,
        species_to_idx,
        phylo_map,
        require_full_contract=args.require_full_contract,
        frozen_cont_stats=frozen_cont_stats,
        frozen_temporal_stats=frozen_temporal_stats,
        zero_phylo_input=args.zero_phylo_input,
        hard_cap_per_species=args.hard_cap_per_species,
        planted_as_land_state=planted_as_ls,
    )
    n = len(dataset)

    # Train/val split (random, stratified would be better but this is simpler)
    np.random.seed(42)
    val_size = int(n * VAL_FRACTION)
    indices = np.random.permutation(n)
    val_indices = indices[:val_size]
    train_indices = indices[val_size:]
    log(f"Train: {len(train_indices):,}, Val: {len(val_indices):,}")

    # Build model
    use_location = getattr(args, 'use_location_encoding', False)
    use_temporal_mag = getattr(args, 'use_temporal_magnitude', False)
    if LAND_STATE_COLS:
        land_state_dim_in = 6 if planted_as_ls else 5
    else:
        land_state_dim_in = 1 if planted_as_ls else 0
    SINRModelV3 = build_model()
    model = SINRModelV3(
        num_env_continuous=dataset.num_env,
        num_species=num_species,
        categorical_config=CATEGORICAL_FEATURES,
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_RES_BLOCKS,
        dropout=DROPOUT,
        fusion_dim=FUSION_DIM,
        temporal_dim=TEMPORAL_HIDDEN,
        phylo_dim=PHYLO_DIMS,
        gate_use_intro=(not args.disable_intro_in_gate),
        land_state_input_dim=land_state_dim_in,
        intro_residual=(args.enable_intro_residual and (not args.disable_intro_residual)),
        location_enc_dim=LOCATION_ENC_DIM if use_location else 0,
        use_temporal_magnitude=use_temporal_mag,
    ).to(device)
    if use_location:
        log(f"Location encoding ENABLED: {LOCATION_ENC_DIM}D sinusoidal ({LOCATION_ENC_FREQS} freqs)")
    if use_temporal_mag:
        log("Temporal magnitude features ENABLED: 9 inter-year scalars → temporal branch")

    if getattr(args, 'no_boost', False):
        model._no_boost = True
        log("Planted boost mechanism REMOVED entirely (v18+)")
    elif args.disable_boost_in_training:
        model._disable_boost_in_training = True
        log("Boost disabled during training (inference-only boost)")
    if planted_as_ls:
        log(f"Planted signal as 6th land_state dim (land_state_input_dim={land_state_dim_in})")

    total_params = sum(p.numel() for p in model.parameters())
    log(f"Model: {total_params:,} parameters ({total_params * 4 / 1e6:.1f} MB fp32)")

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)

    use_amp = device.type == "cuda"
    if use_amp:
        from torch.cuda.amp import GradScaler
        scaler = GradScaler()
        autocast_ctx = torch.cuda.amp.autocast
    else:
        class DummyScaler:
            def scale(self, loss):
                return loss

            def unscale_(self, _optimizer):
                return None

            def step(self, optimizer):
                optimizer.step()

            def update(self):
                return None

        scaler = DummyScaler()
        autocast_ctx = nullcontext

    # Loss
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([POS_WEIGHT], device=device),
        reduction='none',
    )
    loss_mode = args.loss_mode
    planted_pos_wt = getattr(args, 'planted_aux_pos_weight', 1.0)
    aux_planted_loss = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([planted_pos_wt]).to(device) if planted_pos_wt != 1.0 else None
    )
    aux_land_state_loss = nn.CrossEntropyLoss(ignore_index=-1)

    species_weights_t = None
    species_frequency_meta = None
    if args.species_frequency_contract:
        freq_contract_path = Path(args.species_frequency_contract).expanduser()
        if not freq_contract_path.exists():
            log(f"ERROR: species frequency contract not found: {freq_contract_path}")
            return
        weight_mode = getattr(args, 'weight_mode', 'gamma')
        effective_cap = getattr(args, 'effective_cap', 0)
        species_frequency_meta, class_counts, species_weights_np = _load_species_frequency_contract(
            freq_contract_path, mapping_meta['mapping_sha256'], num_species,
            weight_mode=weight_mode, effective_cap=effective_cap,
        )
        species_weights_t = torch.from_numpy(species_weights_np).to(device)
        log(
            "Species-frequency weighting enabled | "
            f"min={species_weights_np.min():.3f} median={np.median(species_weights_np):.3f} max={species_weights_np.max():.3f}"
        )

    intro_ratio_meta = None
    intro_ratio_np = dataset.species_intro_ratio
    if args.intro_ratio_contract:
        intro_ratio_contract_path = Path(args.intro_ratio_contract).expanduser()
        if not intro_ratio_contract_path.exists():
            log(f"ERROR: intro-ratio contract not found: {intro_ratio_contract_path}")
            return
        intro_ratio_meta, intro_ratio_np = _load_intro_ratio_contract(
            intro_ratio_contract_path, mapping_meta['mapping_sha256'], num_species
        )
        log(
            "Intro-ratio contract loaded | "
            f"nonzero={(intro_ratio_np > 0).sum()} mean={intro_ratio_np.mean():.4f}"
        )
    else:
        log(
            "Intro-ratio from dataset slice | "
            f"nonzero={(intro_ratio_np > 0).sum()} mean={intro_ratio_np.mean():.4f}"
        )

    with torch.no_grad():
        model.species_intro_ratio.copy_(torch.from_numpy(intro_ratio_np).to(device))

    # Resume from checkpoint if requested
    start_epoch = 0
    if args.resume:
        ckpt_path = model_dir / f'checkpoint_{args.resume}.pt'
        if ckpt_path.exists():
            checkpoint = torch.load(ckpt_path, map_location=device)
            model.load_state_dict(checkpoint['model_state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            start_epoch = checkpoint['epoch'] + 1
            log(f"Resumed from {ckpt_path}, starting at epoch {start_epoch}")
        else:
            log(f"WARNING: Checkpoint {ckpt_path} not found. Starting fresh.")

    # Save config
    artifact_version = args.artifact_version if args.artifact_version else datetime.now().strftime("%Y%m%d_%H%M%S")

    config = {
        'version': '3.0',
        'artifact_version': artifact_version,
        'num_species': num_species,
        'num_env_continuous': dataset.num_env,
        'continuous_cols': dataset.continuous_cols,
        'categorical_config': {k: {kk: (vv if kk != 'value_map' or vv is None
                                         else {str(rk): rv for rk, rv in vv.items()})
                                    for kk, vv in v.items()}
                                for k, v in CATEGORICAL_FEATURES.items()},
        'hidden_dim': HIDDEN_DIM,
        'num_blocks': NUM_RES_BLOCKS,
        'fusion_dim': FUSION_DIM,
        'temporal_dim': TEMPORAL_HIDDEN,
        'phylo_dim': PHYLO_DIMS,
        'total_params': total_params,
        'batch_size': batch_size,
        'num_epochs': args.epochs,
        'mapping_sha256': mapping_meta['mapping_sha256'],
        'mapping_source_path': mapping_meta['source_path'],
        'require_full_contract': args.require_full_contract,
        'frozen_cont_stats': bool(args.frozen_cont_stats),
        'frozen_temporal_stats': bool(args.frozen_temporal_stats),
        'feature_contract': feature_contract_meta,
        'species_frequency_contract': species_frequency_meta,
        'intro_ratio_contract': intro_ratio_meta,
        'zero_phylo_input': args.zero_phylo_input,
        'gate_use_intro': (not args.disable_intro_in_gate),
        'intro_residual': (args.enable_intro_residual and (not args.disable_intro_residual)),
        'loss_mode': loss_mode,
        'an_pos_weight': args.an_pos_weight,
        'aux_planted_weight': args.aux_planted_weight,
        'aux_land_state_weight': args.aux_land_state_weight,
        'use_location_encoding': use_location,
        'location_enc_dim': LOCATION_ENC_DIM if use_location else 0,
        'location_enc_freqs': LOCATION_ENC_FREQS if use_location else 0,
        'use_temporal_magnitude': use_temporal_mag,
        'no_boost': getattr(args, 'no_boost', False),
        'planted_as_land_state': planted_as_ls,
        'land_state_input_dim': land_state_dim_in,
    }

    # Versioned artifacts (preserve history)
    with open(model_dir / f'model_config_v3_{artifact_version}.json', 'w') as f:
        json.dump(config, f, indent=2)

    np.savez(
        model_dir / f'normalize_stats_v3_{artifact_version}.npz',
        mean=dataset.cont_mean,
        std=dataset.cont_std,
        columns=np.array(dataset.continuous_cols),
    )
    np.savez(
        model_dir / f'normalize_temporal_v3_{artifact_version}.npz',
        mean=dataset.ae_temp_mean,
        std=dataset.ae_temp_std,
        columns=np.array(AE_TEMPORAL_COLS),
    )

    mapping_payload = {
        'artifact_version': artifact_version,
        'mapping_sha256': mapping_meta['mapping_sha256'],
        'source_path': mapping_meta['source_path'],
        'num_species': num_species,
        'species_to_idx': species_to_idx,
        'idx_to_species': {str(k): v for k, v in idx_to_species.items()},
    }
    with open(model_dir / f'species_mapping_v3_{artifact_version}.json', 'w') as f:
        json.dump(mapping_payload, f)

    manifest = {
        'artifact_version': artifact_version,
        'created_at_utc': datetime.utcnow().isoformat() + 'Z',
        'model_config': f'model_config_v3_{artifact_version}.json',
        'continuous_stats': f'normalize_stats_v3_{artifact_version}.npz',
        'temporal_stats': f'normalize_temporal_v3_{artifact_version}.npz',
        'species_mapping': f'species_mapping_v3_{artifact_version}.json',
    }
    with open(model_dir / f'artifact_manifest_v3_{artifact_version}.json', 'w') as f:
        json.dump(manifest, f, indent=2)

    # Stable "latest" aliases (kept for existing scripts)
    with open(model_dir / 'model_config_v3.json', 'w') as f:
        json.dump(config, f, indent=2)

    # Save normalization stats
    np.savez(model_dir / 'normalize_stats_v3.npz',
             mean=dataset.cont_mean, std=dataset.cont_std,
             columns=np.array(dataset.continuous_cols))
    np.savez(model_dir / 'normalize_temporal_v3.npz',
             mean=dataset.ae_temp_mean, std=dataset.ae_temp_std,
             columns=np.array(AE_TEMPORAL_COLS))

    # Save species mapping for v3
    with open(model_dir / 'species_mapping_v3.json', 'w') as f:
        json.dump(mapping_payload, f)

    # ── Training ──────────────────────────────────────────────────────────
    best_val_loss = float('inf')
    epochs_no_improve = 0
    training_log = []
    n_train_batches = (len(train_indices) + batch_size - 1) // batch_size
    n_val_batches = (len(val_indices) + batch_size - 1) // batch_size

    log(f"\n{'='*60}")
    log(f"Starting training: {args.epochs} epochs, {n_train_batches} batches/epoch")
    log(f"Batch size: {batch_size}, LR: {LEARNING_RATE}, Device: {device}")
    log(f"{'='*60}\n")

    for epoch in range(start_epoch, args.epochs):
        t_epoch = time.time()
        model.train()

        # Shuffle training indices
        np.random.shuffle(train_indices)

        # LR schedule: linear warmup then decay
        if epoch < WARMUP_EPOCHS:
            lr = LEARNING_RATE * (epoch + 1) / WARMUP_EPOCHS
        else:
            lr = LEARNING_RATE * (LR_DECAY ** (epoch - WARMUP_EPOCHS))
        for pg in optimizer.param_groups:
            pg['lr'] = lr

        # Training pass
        train_loss_sum = 0
        train_correct = 0
        train_total = 0

        for batch_idx in range(n_train_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(train_indices))
            batch_indices = train_indices[start:end]
            batch = dataset.get_batch(batch_indices)

            # Move to GPU
            x_cont = batch['continuous'].to(device)
            x_cat = batch['categorical'].to(device)
            x_intro = batch['is_introduced'].to(device)
            x_temporal = batch['ae_temporal'].to(device)
            x_land = batch['land_state'].to(device)
            x_phylo = batch['phylo'].to(device)
            x_loc = batch['location_enc'].to(device) if use_location else None
            targets = batch['species_idx'].to(device)

            optimizer.zero_grad(set_to_none=True)

            with autocast_ctx():
                logits, aux_pl, aux_ls = model(
                    x_cont, x_cat, x_intro, x_temporal, x_land, x_phylo, x_loc)

                # Multi-label BCEWithLogits
                target_one_hot = torch.zeros(
                    logits.shape[0], num_species, device=device)
                valid_mask = targets >= 0
                if valid_mask.any():
                    target_one_hot[valid_mask, targets[valid_mask]] = 1.0

                if loss_mode == 'an_full':
                    loss = _compute_an_full_loss(
                        logits,
                        targets,
                        species_weights=species_weights_t,
                        pos_weight=args.an_pos_weight,
                    )
                else:
                    loss = _compute_species_weighted_bce_loss(
                        criterion, logits, target_one_hot, targets, species_weights=species_weights_t
                    )

                # Aux losses (smaller weight)
                # Planted detection: use xiao_planted_forest > 0 as proxy label
                if 'xiao_planted_forest' in CATEGORICAL_FEATURES and args.aux_planted_weight > 0:
                    xiao_idx = list(CATEGORICAL_FEATURES.keys()).index('xiao_planted_forest')
                    if args.planted_label_mode == 'strict_planted3':
                        # mapped class 3 corresponds to raw Xiao planted class 2
                        planted_label = (x_cat[:, xiao_idx] == 3).float().unsqueeze(1)
                    elif args.planted_label_mode == 'land_state2' and x_land.shape[1] > 0:
                        # land_state_class=2 as plantation proxy
                        planted_label = (x_land[:, 0] == 2).float().unsqueeze(1)
                    else:
                        # legacy behavior retained for reproducibility
                        planted_label = (x_cat[:, xiao_idx] > 1).float().unsqueeze(1)
                    loss = loss + args.aux_planted_weight * aux_planted_loss(aux_pl, planted_label)

                # Land state classification
                if x_land.shape[1] > 0:
                    ls_target = x_land[:, 0].long()  # land_state_class
                    ls_valid = (ls_target >= 0) & (ls_target < 6)
                    if ls_valid.any() and args.aux_land_state_weight > 0:
                        loss = loss + args.aux_land_state_weight * aux_land_state_loss(
                            aux_ls[ls_valid], ls_target[ls_valid])

                # Background loss: random locations → all species absent (canonical SINR)
                if args.bg_weight > 0:
                    bg_idx = np.random.randint(0, len(train_indices), len(batch_indices))
                    bg_batch = dataset.get_batch(bg_idx)
                    bg_cont = bg_batch['continuous'].to(device)
                    bg_cat = bg_batch['categorical'].to(device)
                    bg_intro = bg_batch['is_introduced'].to(device)
                    bg_temporal = bg_batch['ae_temporal'].to(device)
                    bg_land = bg_batch['land_state'].to(device)
                    bg_phylo = bg_batch['phylo'].to(device)
                    bg_loc = bg_batch['location_enc'].to(device) if use_location else None
                    bg_logits, _, _ = model(
                        bg_cont, bg_cat, bg_intro, bg_temporal, bg_land, bg_phylo, bg_loc)
                    bg_loss = -torch.nn.functional.logsigmoid(-bg_logits).mean()
                    loss = loss + args.bg_weight * bg_loss

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            scaler.step(optimizer)
            scaler.update()

            train_loss_sum += loss.item() * len(batch_indices)
            train_total += len(batch_indices)

            # Top-k accuracy
            with torch.no_grad():
                _, top_k = logits.topk(10, dim=1)
                for k_val in [1]:
                    train_correct += (top_k[:, :k_val] == targets.unsqueeze(1)).any(1).sum().item()

            if (batch_idx + 1) % 100 == 0:
                avg_loss = train_loss_sum / train_total
                acc = train_correct / train_total * 100
                log(f"  Epoch {epoch+1} [{batch_idx+1}/{n_train_batches}] "
                    f"loss={avg_loss:.4f} top1={acc:.2f}% lr={lr:.6f}")

        # ── Validation ────────────────────────────────────────────────────
        model.eval()
        val_loss_sum = 0
        val_correct_top1 = 0
        val_correct_top5 = 0
        val_correct_top10 = 0
        val_total = 0

        with torch.no_grad():
            for batch_idx in range(n_val_batches):
                start = batch_idx * batch_size
                end = min(start + batch_size, len(val_indices))
                batch_indices = val_indices[start:end]
                batch = dataset.get_batch(batch_indices)

                x_cont = batch['continuous'].to(device)
                x_cat = batch['categorical'].to(device)
                x_intro = batch['is_introduced'].to(device)
                x_temporal = batch['ae_temporal'].to(device)
                x_land = batch['land_state'].to(device)
                x_phylo = batch['phylo'].to(device)
                x_loc = batch['location_enc'].to(device) if use_location else None
                targets = batch['species_idx'].to(device)

                with autocast_ctx():
                    logits, _, _ = model(
                        x_cont, x_cat, x_intro, x_temporal, x_land, x_phylo, x_loc)
                    target_one_hot = torch.zeros(
                        logits.shape[0], num_species, device=device)
                    valid_mask = targets >= 0
                    if valid_mask.any():
                        target_one_hot[valid_mask, targets[valid_mask]] = 1.0
                    if loss_mode == 'an_full':
                        loss = _compute_an_full_loss(
                            logits,
                            targets,
                            species_weights=species_weights_t,
                            pos_weight=args.an_pos_weight,
                        )
                    else:
                        loss = _compute_species_weighted_bce_loss(
                            criterion, logits, target_one_hot, targets, species_weights=species_weights_t
                        )

                val_loss_sum += loss.item() * len(batch_indices)
                val_total += len(batch_indices)

                _, top_k = logits.topk(10, dim=1)
                val_correct_top1 += (top_k[:, :1] == targets.unsqueeze(1)).any(1).sum().item()
                val_correct_top5 += (top_k[:, :5] == targets.unsqueeze(1)).any(1).sum().item()
                val_correct_top10 += (top_k[:, :10] == targets.unsqueeze(1)).any(1).sum().item()

        train_loss = train_loss_sum / train_total
        val_loss = val_loss_sum / val_total
        train_acc = train_correct / train_total * 100
        val_top1 = val_correct_top1 / val_total * 100
        val_top5 = val_correct_top5 / val_total * 100
        val_top10 = val_correct_top10 / val_total * 100
        epoch_time = time.time() - t_epoch

        log(f"\n{'─'*60}")
        log(f"Epoch {epoch+1}/{args.epochs} — {epoch_time:.0f}s ({epoch_time/60:.1f} min)")
        log(f"  Train loss: {train_loss:.4f}  top1: {train_acc:.2f}%")
        log(f"  Val loss:   {val_loss:.4f}  top1: {val_top1:.2f}%  top5: {val_top5:.2f}%  top10: {val_top10:.2f}%")
        log(f"  LR: {lr:.6f}")

        # Save checkpoint every epoch
        ckpt = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'train_loss': train_loss,
            'val_loss': val_loss,
            'val_top1': val_top1,
            'val_top5': val_top5,
            'val_top10': val_top10,
        }
        torch.save(ckpt, model_dir / f'checkpoint_epoch_{epoch+1}.pt')
        log(f"  Saved checkpoint_epoch_{epoch+1}.pt")

        # Best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_no_improve = 0
            torch.save(ckpt, model_dir / 'best_model.pt')
            log(f"  ★ New best model! val_loss={val_loss:.4f}")
        else:
            epochs_no_improve += 1
            log(f"  No improvement for {epochs_no_improve}/{PATIENCE} epochs")

        # Training log
        epoch_log = {
            'epoch': epoch + 1,
            'train_loss': train_loss,
            'val_loss': val_loss,
            'train_top1': train_acc,
            'val_top1': val_top1,
            'val_top5': val_top5,
            'val_top10': val_top10,
            'lr': lr,
            'time_s': epoch_time,
        }
        training_log.append(epoch_log)
        with open(model_dir / 'training_log.json', 'w') as f:
            json.dump(training_log, f, indent=2)

        # ── Per-epoch inference test ──────────────────────────────────────
        log(f"\n  📊 Inference test (epoch {epoch+1}):")
        run_inference_test(model, dataset, idx_to_species, species_to_idx, device)

        log(f"{'─'*60}\n")

        # Early stopping
        if epochs_no_improve >= PATIENCE:
            log(f"Early stopping after {PATIENCE} epochs without improvement.")
            break

    log(f"\nTraining complete! Best val_loss: {best_val_loss:.4f}")
    log(f"Model saved to {model_dir}/best_model.pt")


def run_inference_test(model, dataset, idx_to_species, species_to_idx, device):
    """Run quick inference on test locations to show species predictions evolving."""
    import torch
    if device.type == "cuda":
        autocast_ctx = torch.cuda.amp.autocast
    else:
        autocast_ctx = nullcontext

    model.eval()

    # Find Pinus radiata index (try common taxon_id formats)
    radiata_idx = None
    radiata_name = None
    for tid, idx in species_to_idx.items():
        sp_name = idx_to_species.get(idx, '')
        if 'pinus' in str(tid).lower() and 'radiata' in str(tid).lower():
            radiata_idx = idx
            radiata_name = tid
            break
        if 'pinus' in sp_name.lower() and 'radiata' in sp_name.lower():
            radiata_idx = idx
            radiata_name = sp_name
            break
    # Also try the species name directly as key
    for candidate in ['Pinus radiata', 'pinus_radiata', 'Pinus_radiata']:
        if candidate in species_to_idx:
            radiata_idx = species_to_idx[candidate]
            radiata_name = candidate
            break

    np.random.seed(int(time.time()) % 10000)
    sample_idx = np.random.choice(len(dataset), size=min(100, len(dataset)), replace=False)
    batch = dataset.get_batch(sample_idx)

    x_loc = batch.get('location_enc')
    if x_loc is not None:
        x_loc = x_loc.to(device)

    with torch.no_grad():
        with autocast_ctx():
            logits, _, _ = model(
                batch['continuous'].to(device),
                batch['categorical'].to(device),
                batch['is_introduced'].to(device),
                batch['ae_temporal'].to(device),
                batch['land_state'].to(device),
                batch['phylo'].to(device),
                x_location=x_loc,
            )
        probs = torch.sigmoid(logits)
        top_vals, top_idx = probs.topk(5, dim=1)

        # Get full ranking for Pinus radiata
        if radiata_idx is not None:
            # Rank = how many species have higher probability + 1
            radiata_probs = probs[:, radiata_idx]  # (B,)
            radiata_ranks = (probs > radiata_probs.unsqueeze(1)).sum(dim=1) + 1  # (B,)

    # Show predictions for first 3 samples
    for i in range(min(3, len(sample_idx))):
        true_sp = idx_to_species.get(int(batch['species_idx'][i]), '?')
        preds = []
        for j in range(5):
            sp = idx_to_species.get(int(top_idx[i, j]), '?')
            prob = top_vals[i, j].item()
            preds.append(f"{sp}({prob:.3f})")
        is_correct = int(top_idx[i, 0]) == int(batch['species_idx'][i])
        mark = "✓" if is_correct else "✗"
        log(f"    {mark} True: {true_sp} → Top5: {', '.join(preds)}")

        # Show Pinus radiata rank for this sample
        if radiata_idx is not None:
            rank = int(radiata_ranks[i])
            prob = float(radiata_probs[i])
            log(f"      🌲 P. radiata: rank #{rank:,} / {model.num_species:,} (p={prob:.4f})")

    # Summary: average radiata rank across all samples
    if radiata_idx is not None:
        avg_rank = float(radiata_ranks.float().mean())
        median_rank = float(radiata_ranks.float().median())
        avg_prob = float(radiata_probs.mean())
        log(f"    🌲 P. radiata avg rank: #{avg_rank:,.0f} (median #{median_rank:,.0f}, avg p={avg_prob:.4f})")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='SINR v3.0 Training (VM)')
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--epochs', type=int, default=NUM_EPOCHS)
    parser.add_argument('--batch-size', type=int, default=None,
                        help='Override training batch size')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda', 'mps'], default='auto',
                        help='Execution device (default: auto)')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Path containing unified_*.parquet')
    parser.add_argument('--model-dir', type=str, default=None,
                        help='Output directory for checkpoints/artifacts')
    parser.add_argument('--resume', type=str, default=None,
                        help='Resume from checkpoint, e.g. "epoch_5"')
    parser.add_argument('--mapping-path', type=str, default='~/species_mapping.json',
                        help='Legacy species mapping path (used when no contract is supplied)')
    parser.add_argument('--mapping-contract', type=str, default=None,
                        help='Versioned mapping contract JSON (preferred)')
    parser.add_argument('--require-full-contract', action='store_true',
                        help='Fail if required v3 columns are missing in training parquet')
    parser.add_argument('--frozen-cont-stats', type=str, default=None,
                        help='Use precomputed continuous normalization stats .npz')
    parser.add_argument('--frozen-temporal-stats', type=str, default=None,
                        help='Use precomputed temporal normalization stats .npz')
    parser.add_argument('--artifact-version', type=str, default=None,
                        help='Version tag used for artifact filenames')
    parser.add_argument('--feature-contract', type=str, default=None,
                        help='Feature contract JSON specifying env_continuous_cols')
    parser.add_argument('--species-frequency-contract', type=str, default=None,
                        help='Species frequency contract JSON for per-species loss weighting')
    parser.add_argument('--intro-ratio-contract', type=str, default=None,
                        help='Versioned species introduced-ratio contract JSON')
    parser.add_argument('--zero-phylo-input', action='store_true',
                        help='Disable per-sample taxon phylo input to avoid label-leakage path')
    parser.add_argument('--disable-intro-in-gate', action='store_true',
                        help='Do not use is_introduced in gate routing input')
    parser.add_argument('--enable-intro-residual', action='store_true',
                        help='Enable separate introduced residual conditioning path')
    parser.add_argument('--disable-intro-residual', action='store_true',
                        help='Disable separate introduced residual conditioning path')
    parser.add_argument('--loss-mode', choices=['bce', 'an_full'], default='bce',
                        help='Primary species loss function')
    parser.add_argument('--an-pos-weight', type=float, default=POS_WEIGHT,
                        help='Positive term weight for AN-Full loss')
    parser.add_argument('--aux-planted-weight', type=float, default=0.1,
                        help='Aux planted loss coefficient')
    parser.add_argument('--planted-label-mode',
                        choices=['legacy_gt1', 'strict_planted3', 'land_state2'],
                        default='legacy_gt1',
                        help='Target definition used for planted auxiliary labels')
    parser.add_argument('--aux-land-state-weight', type=float, default=0.05,
                        help='Aux land-state loss coefficient')
    parser.add_argument('--disable-boost-in-training', action='store_true',
                        help='Zero out planted boost during training, apply only at inference')
    parser.add_argument('--no-boost', action='store_true',
                        help='Remove planted boost mechanism entirely (v18+)')
    parser.add_argument('--planted-as-land-state', action='store_true',
                        help='Add is_planted as 6th land_state dimension (v18+)')
    parser.add_argument('--planted-aux-pos-weight', type=float, default=1.0,
                        help='Positive class weight for planted aux BCE (5.7 for 14.8%% planted)')
    parser.add_argument('--hard-cap-per-species', type=int, default=0,
                        help='Max training samples per species (0=no cap, v2.2 used 50000)')
    parser.add_argument('--weight-mode', choices=['gamma', 'effective_cap'], default='gamma',
                        dest='weight_mode',
                        help='Species frequency weighting mode: gamma=(median/count)^0.5 clamped, '
                             'effective_cap=min(cap,count)/count (soft cap, preserves all data)')
    parser.add_argument('--effective-cap', type=int, default=0,
                        help='Effective sample cap for --weight-mode effective_cap (e.g. 1000)')
    parser.add_argument('--bg-weight', type=float, default=0.0,
                        help='Background loss weight (v2.2 used 1.0, 0=disabled)')
    parser.add_argument('--use-location-encoding', action='store_true',
                        help='Add sinusoidal lat/lon encoding as model input branch')
    parser.add_argument('--use-temporal-magnitude', action='store_true',
                        help='Add inter-year AE embedding magnitude features to temporal branch')
    args = parser.parse_args()

    if args.train:
        train(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
