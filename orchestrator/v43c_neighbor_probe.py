#!/usr/bin/env python3
"""
V4.3c Nearest-Neighbor Probe — representation vs classifier diagnostic.

Caches the canonical benchmark feature vector once, then probes nearest
neighbors in three representation spaces:
  1. AE primary embedding (64D)
  2. AE temporal sequence (512D)
  3. Trained pre-logit hidden space (384D)

Compares neighbor composition against model logit ranking to determine
whether the problem is in the representation or the classifier/fusion/head.

Usage:
  # Step 1: Cache benchmark features (runs GEE sampling once)
  python3 orchestrator/v43c_neighbor_probe.py cache \
    --model-dir ~/model_v42_anfull_hardcap_full \
    --cache-file orchestrator/v43c_benchmark_cache.npz

  # Step 2: Run neighbor probe (no GEE needed, uses cached features)
  python3 orchestrator/v43c_neighbor_probe.py probe \
    --model-dir ~/model_v42_anfull_hardcap_full \
    --cache-file orchestrator/v43c_benchmark_cache.npz \
    --data-dir ~/data_v41_preview_train_shards \
    --top-k 200

Issue: treekipedia-xz2 (V4.2 comparison)
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


# ── Constants ────────────────────────────────────────────────────────────────

CANONICAL_LAT = -41.151583464812404
CANONICAL_LON = 175.09968969862783
CANONICAL_YEAR = 2023
CANONICAL_TARGET = "GymPiPiPnCx50820-00"

AE_EMB_COLS = [f"emb_{i:02d}" for i in range(64)]
AE_TEMPORAL_COLS = [f"ae_{y}_{b:02d}" for y in range(2017, 2025) for b in range(64)]

# Species taxonomy classification for NZ context
# Built from the V4.2 analysis: docs/SINR V4.2 Comparison Analysis.md
NZ_NATIVE_PREFIXES = [
    # Podocarpaceae (NZ native conifers)
    "GymPiPiPdCr",
    # Phyllocladaceae
    "GymPiPiPhYa",
    # Araucariaceae (NZ native)
    "GymPiPiArCx",
]

PINACEAE_PREFIX = "GymPiPiPnCx"
CUPRESSACEAE_PREFIX = "GymPiPiCpRs"


# ── Taxonomy classifier ─────────────────────────────────────────────────────

def classify_taxon(taxon_id: str, intro_ratios: dict = None) -> dict:
    """Classify a taxon_id into diagnostic categories."""
    is_gymnosperm = taxon_id.startswith("Gym")
    is_angiosperm = taxon_id.startswith("Ang")

    is_pinaceae = taxon_id.startswith(PINACEAE_PREFIX)
    is_pinus = is_pinaceae  # all GymPiPiPnCx are Pinus in this encoding
    is_cupressaceae = taxon_id.startswith(CUPRESSACEAE_PREFIX)
    is_conifer = is_gymnosperm

    is_nz_native_gymnosperm = any(taxon_id.startswith(p) for p in NZ_NATIVE_PREFIXES)

    is_radiata = (taxon_id == CANONICAL_TARGET)

    # Broad category
    if is_radiata:
        category = "radiata"
    elif is_pinus:
        category = "other_pinus"
    elif is_pinaceae:
        category = "other_pinaceae"
    elif is_nz_native_gymnosperm:
        category = "nz_native_conifer"
    elif is_conifer:
        category = "other_conifer"
    elif is_angiosperm:
        category = "angiosperm"
    else:
        category = "unknown"

    return {
        "taxon_id": taxon_id,
        "category": category,
        "is_gymnosperm": is_gymnosperm,
        "is_conifer": is_conifer,
        "is_pinaceae": is_pinaceae,
        "is_pinus": is_pinus,
        "is_radiata": is_radiata,
        "is_nz_native_conifer": is_nz_native_gymnosperm,
    }


def categorize_neighbors(neighbors: list, intro_ratios: dict = None) -> dict:
    """Summarize neighbor composition by category."""
    cats = {}
    for n in neighbors:
        c = n["category"]
        cats[c] = cats.get(c, 0) + 1
    return cats


# ── Model hidden state extraction ───────────────────────────────────────────

class HiddenStateCapture:
    """Register a hook to capture pre-logit hidden representations."""

    def __init__(self):
        self.hidden = None
        self._hook = None

    def _pre_hook(self, module, input):
        # input is a tuple; input[0] is the hidden state going into output_layer
        self.hidden = input[0].detach()

    def register(self, model):
        # Hook the output_layer (Linear) to capture its input = pre-logit hidden
        self._hook = model.output_layer.register_forward_pre_hook(self._pre_hook)

    def remove(self):
        if self._hook:
            self._hook.remove()


# ── Cosine similarity ───────────────────────────────────────────────────────

def cosine_sim_batch(query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query (1D) and candidates (2D)."""
    q = query / (np.linalg.norm(query) + 1e-10)
    norms = np.linalg.norm(candidates, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    c_normed = candidates / norms
    return c_normed @ q


# ── Step 1: Cache benchmark features ────────────────────────────────────────

def cache_benchmark(args):
    """Sample GEE features at canonical benchmark, run model, save everything."""
    print("=" * 72)
    print("V4.3c: Caching canonical benchmark features")
    print(f"  Coordinate: ({CANONICAL_LAT}, {CANONICAL_LON})")
    print(f"  Year: {CANONICAL_YEAR}")
    print(f"  Model: {args.model_dir}")
    print("=" * 72)

    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "orchestrator"))

    # Load modules
    from v3_point_inference import (
        load_training_module, load_sampling_module,
        build_feature_inputs, align_normalization, compute_land_state,
        sample_ae_year
    )

    tvm = load_training_module(repo_root)
    locfix = load_sampling_module(repo_root)

    # Apply feature contract
    fc_path = Path(args.feature_contract).expanduser()
    with open(fc_path) as f:
        feature_contract = json.load(f)
    tvm.ENV_CONTINUOUS_COLS = [str(c) for c in feature_contract["env_continuous_cols"]]

    model_dir = Path(args.model_dir).expanduser()

    # Sample raw features (before normalization)
    print("\nSampling GEE features (this calls AlphaEarth + WorldClim + soil)...")
    x_cont_raw, x_cat_np, x_temporal_raw, x_land_np = build_feature_inputs(
        tvm, locfix, CANONICAL_LAT, CANONICAL_LON, CANONICAL_YEAR,
        land_state_mode="zero", strict_feature_contract=False,
        planted_as_land_state=False,
    )

    # Save raw features before normalization
    ae_primary_raw = x_cont_raw[:64].copy()   # emb_00..emb_63
    env_raw = x_cont_raw[64:].copy()          # env continuous
    temporal_raw = x_temporal_raw.copy()       # ae_2017_00..ae_2024_63

    # Normalize continuous
    stats_path = model_dir / "normalize_stats_v3.npz"
    cont_cols = tvm.AE_EMB_COLS + tvm.ENV_CONTINUOUS_COLS
    cont_mean, cont_std = align_normalization(stats_path, cont_cols)
    x_cont_norm = (x_cont_raw - cont_mean) / cont_std

    # Normalize temporal
    temporal_stats_path = model_dir / "normalize_temporal_v3.npz"
    if temporal_stats_path.exists():
        ts = np.load(temporal_stats_path, allow_pickle=True)
        tmean = ts["mean"].astype(np.float32)
        tstd = ts["std"].astype(np.float32)
        tstd[tstd < 1e-8] = 1.0
        x_temporal_norm = (x_temporal_raw - tmean) / tstd
    else:
        x_temporal_norm = x_temporal_raw.copy()

    # Location encoding
    loc_enc = tvm.encode_location_sinusoidal(CANONICAL_LAT, CANONICAL_LON)

    # Load model and get hidden state + logits
    print("Loading model and computing hidden state + logits...")
    mapping_path = model_dir / "species_mapping_v3.json"
    with open(mapping_path) as f:
        species_mapping = json.load(f)
    species_to_idx = species_mapping["species_to_idx"]
    idx_to_species = {int(k): v for k, v in species_mapping["idx_to_species"].items()}
    num_species = len(species_to_idx)

    SINRModelV3 = tvm.build_model()
    model = SINRModelV3(
        num_env_continuous=len(tvm.ENV_CONTINUOUS_COLS),
        num_species=num_species,
        categorical_config=tvm.CATEGORICAL_FEATURES,
        hidden_dim=tvm.HIDDEN_DIM,
        num_blocks=tvm.NUM_RES_BLOCKS,
        dropout=tvm.DROPOUT,
        fusion_dim=tvm.FUSION_DIM,
        temporal_dim=tvm.TEMPORAL_HIDDEN,
        phylo_dim=tvm.PHYLO_DIMS,
        gate_use_intro=False,  # disable_intro_in_gate
        location_enc_dim=tvm.LOCATION_ENC_DIM,
        land_state_input_dim=5,
    )
    model._no_boost = True
    ckpt = torch.load(model_dir / "best_model.pt", map_location="cpu")
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    # Register hidden state hook
    capture = HiddenStateCapture()
    capture.register(model)

    # Forward pass
    x_cont_t = torch.from_numpy(x_cont_norm.astype(np.float32)).unsqueeze(0)
    x_cat_t = torch.from_numpy(x_cat_np.astype(np.int64)).unsqueeze(0)
    x_intro_t = torch.tensor([[0.5]], dtype=torch.float32)
    x_temporal_t = torch.from_numpy(x_temporal_norm.astype(np.float32)).unsqueeze(0)
    x_land_t = torch.from_numpy(x_land_np.astype(np.float32)).unsqueeze(0)
    x_phylo_t = torch.zeros(1, tvm.PHYLO_DIMS, dtype=torch.float32)
    x_loc_t = torch.from_numpy(loc_enc.astype(np.float32)).reshape(1, -1)

    with torch.no_grad():
        logits, _, _ = model(x_cont_t, x_cat_t, x_intro_t, x_temporal_t,
                            x_land_t, x_phylo_t, x_loc_t)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
        logits_np = logits.squeeze(0).cpu().numpy()

    hidden_np = capture.hidden.squeeze(0).cpu().numpy()  # 384D
    capture.remove()

    # Rank target
    target_idx = species_to_idx.get(CANONICAL_TARGET)
    target_prob = float(probs[target_idx])
    target_rank = int((probs > target_prob).sum() + 1)

    print(f"\nBenchmark result: {CANONICAL_TARGET}")
    print(f"  Rank: #{target_rank:,}/{num_species:,}")
    print(f"  Prob: {target_prob:.6f}")
    print(f"  AE primary shape: {ae_primary_raw.shape}")
    print(f"  AE temporal shape: {temporal_raw.shape}")
    print(f"  Hidden state shape: {hidden_np.shape}")

    # Save cache
    cache_path = Path(args.cache_file).expanduser()
    np.savez_compressed(
        cache_path,
        # Raw features (pre-normalization)
        ae_primary_raw=ae_primary_raw,
        env_raw=env_raw,
        temporal_raw=temporal_raw,
        # Normalized features
        ae_primary_norm=x_cont_norm[:64],
        env_norm=x_cont_norm[64:],
        cont_norm=x_cont_norm,
        temporal_norm=x_temporal_norm,
        # Model internal state
        hidden=hidden_np,
        logits=logits_np,
        probs=probs,
        # Metadata
        categorical=x_cat_np,
        land_state=x_land_np,
        location_enc=loc_enc,
        # Normalization stats (needed for training data alignment)
        cont_mean=cont_mean,
        cont_std=cont_std,
        # Benchmark result
        target_rank=np.array([target_rank]),
        target_prob=np.array([target_prob]),
    )
    print(f"\nCached to: {cache_path}")
    print("This file is deterministic — reuse it for all probes.")


# ── Step 2: Neighbor probe ──────────────────────────────────────────────────

def run_probe(args):
    """Load cached benchmark, scan training shards, find nearest neighbors."""
    print("=" * 72)
    print("V4.3c: Nearest-Neighbor Probe")
    print(f"  Cache: {args.cache_file}")
    print(f"  Model: {args.model_dir}")
    print(f"  Data: {args.data_dir}")
    print(f"  Top-K: {args.top_k}")
    print("=" * 72)

    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "orchestrator"))

    tvm = __import__("train_on_vm")

    # Load cache
    cache = np.load(Path(args.cache_file).expanduser(), allow_pickle=True)
    q_ae_primary_norm = cache["ae_primary_norm"]      # 64D normalized
    q_ae_primary_raw = cache["ae_primary_raw"]         # 64D raw
    q_temporal_norm = cache["temporal_norm"]            # 512D normalized
    q_temporal_raw = cache["temporal_raw"]              # 512D raw
    q_hidden = cache["hidden"]                         # 384D
    q_probs = cache["probs"]                           # 19043D
    q_logits = cache["logits"]                         # 19043D
    q_cont_norm = cache["cont_norm"]                   # 119D
    cont_mean = cache["cont_mean"]
    cont_std = cache["cont_std"]
    target_rank = int(cache["target_rank"][0])
    target_prob = float(cache["target_prob"][0])

    print(f"\nBenchmark (cached): {CANONICAL_TARGET}")
    print(f"  Rank: #{target_rank:,}, Prob: {target_prob:.6f}")

    # Load species mapping
    model_dir = Path(args.model_dir).expanduser()
    mapping_path = model_dir / "species_mapping_v3.json"
    with open(mapping_path) as f:
        species_mapping = json.load(f)
    species_to_idx = species_mapping["species_to_idx"]
    idx_to_species = {int(k): v for k, v in species_mapping["idx_to_species"].items()}
    num_species = len(species_to_idx)

    # Load feature contract
    fc_path = Path(args.feature_contract).expanduser()
    with open(fc_path) as f:
        feature_contract = json.load(f)
    tvm.ENV_CONTINUOUS_COLS = [str(c) for c in feature_contract["env_continuous_cols"]]

    # Load frozen normalization stats for training data
    frozen_cont_path = Path(args.frozen_cont_stats).expanduser()
    frozen_temp_path = Path(args.frozen_temporal_stats).expanduser()
    frozen_cont = np.load(frozen_cont_path, allow_pickle=True)
    frozen_temp = np.load(frozen_temp_path, allow_pickle=True)
    train_cont_mean = frozen_cont["mean"].astype(np.float32)
    train_cont_std = frozen_cont["std"].astype(np.float32)
    train_cont_std[train_cont_std < 1e-8] = 1.0
    train_temp_mean = frozen_temp["mean"].astype(np.float32)
    train_temp_std = frozen_temp["std"].astype(np.float32)
    train_temp_std[train_temp_std < 1e-8] = 1.0

    # Load model for hidden state extraction
    print("\nLoading model for hidden-state extraction...")
    SINRModelV3 = tvm.build_model()
    model = SINRModelV3(
        num_env_continuous=len(tvm.ENV_CONTINUOUS_COLS),
        num_species=num_species,
        categorical_config=tvm.CATEGORICAL_FEATURES,
        hidden_dim=tvm.HIDDEN_DIM,
        num_blocks=tvm.NUM_RES_BLOCKS,
        dropout=tvm.DROPOUT,
        fusion_dim=tvm.FUSION_DIM,
        temporal_dim=tvm.TEMPORAL_HIDDEN,
        phylo_dim=tvm.PHYLO_DIMS,
        gate_use_intro=False,
        location_enc_dim=tvm.LOCATION_ENC_DIM,
        land_state_input_dim=5,
    )
    model._no_boost = True
    ckpt = torch.load(model_dir / "best_model.pt", map_location="cpu")
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    capture = HiddenStateCapture()
    capture.register(model)

    # Scan training shards
    data_dir = Path(args.data_dir).expanduser()
    shard_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    K = args.top_k

    # Heaps: (similarity, shard_idx, row_idx, taxon_id, lat, lon)
    # Use negative similarity for min-heap (we want top-K highest)
    import heapq
    heap_ae_primary = []   # top-K by AE primary cosine sim
    heap_ae_temporal = []  # top-K by AE temporal cosine sim
    heap_hidden = []       # top-K by pre-logit hidden cosine sim

    total_rows = 0
    t0 = time.time()

    for si, shard_dir in enumerate(shard_dirs):
        parquet_files = list(shard_dir.glob("*.parquet"))
        if not parquet_files:
            continue

        import pandas as pd
        print(f"\n  Processing shard {shard_dir.name}...", end="", flush=True)
        df = pd.read_parquet(parquet_files[0])
        n = len(df)
        total_rows += n

        # Extract raw AE primary (64D) and temporal (512D)
        ae_cols = [c for c in AE_EMB_COLS if c in df.columns]
        ae_temp_cols = [c for c in AE_TEMPORAL_COLS if c in df.columns]

        ae_primary = df[ae_cols].values.astype(np.float32)
        ae_primary = np.nan_to_num(ae_primary, nan=0.0)

        ae_temporal = df[ae_temp_cols].values.astype(np.float32)
        ae_temporal = np.nan_to_num(ae_temporal, nan=0.0)

        taxon_ids = df["taxon_id"].values
        lats = df["latitude"].values.astype(np.float32) if "latitude" in df.columns else np.zeros(n)
        lons = df["longitude"].values.astype(np.float32) if "longitude" in df.columns else np.zeros(n)

        # --- AE primary cosine similarity (raw space, no normalization) ---
        sims_ae = cosine_sim_batch(q_ae_primary_raw, ae_primary)
        top_idx_ae = np.argsort(sims_ae)[-K:]
        for idx in top_idx_ae:
            entry = (-float(sims_ae[idx]), si, int(idx),
                     str(taxon_ids[idx]), float(lats[idx]), float(lons[idx]))
            if len(heap_ae_primary) < K:
                heapq.heappush(heap_ae_primary, entry)
            elif entry[0] < heap_ae_primary[0][0]:
                heapq.heapreplace(heap_ae_primary, entry)

        # --- AE temporal cosine similarity (raw space) ---
        sims_temp = cosine_sim_batch(q_temporal_raw, ae_temporal)
        top_idx_temp = np.argsort(sims_temp)[-K:]
        for idx in top_idx_temp:
            entry = (-float(sims_temp[idx]), si, int(idx),
                     str(taxon_ids[idx]), float(lats[idx]), float(lons[idx]))
            if len(heap_ae_temporal) < K:
                heapq.heappush(heap_ae_temporal, entry)
            elif entry[0] < heap_ae_temporal[0][0]:
                heapq.heapreplace(heap_ae_temporal, entry)

        # --- Hidden-state cosine similarity (requires model forward) ---
        # Prepare full input tensors for the model
        env_cols = [c for c in tvm.ENV_CONTINUOUS_COLS if c in df.columns]
        cont_cols_actual = ae_cols + env_cols
        cont_data = df[cont_cols_actual].values.astype(np.float32)
        cont_data = np.nan_to_num(cont_data, nan=0.0)

        # Clamp GPP fill codes
        if 'modis_gpp_mean' in cont_cols_actual:
            gpp_idx = cont_cols_actual.index('modis_gpp_mean')
            cont_data[:, gpp_idx] = np.where(cont_data[:, gpp_idx] >= 65530, 0.0, cont_data[:, gpp_idx])
        # NOTE: GEDI canopy height is NOT clipped. Trees can exceed 80m/100m.
        # Previous 0..80 clip removed (2026-03-17 audit).

        # Normalize continuous
        cont_data = (cont_data - train_cont_mean) / train_cont_std

        # Normalize temporal
        ae_temporal_norm = (ae_temporal - train_temp_mean) / train_temp_std

        # Categorical
        cat_data = np.zeros((n, len(tvm.CATEGORICAL_FEATURES)), dtype=np.int64)
        for ci, (col, cfg) in enumerate(tvm.CATEGORICAL_FEATURES.items()):
            if col in df.columns:
                raw = df[col].fillna(0).astype(np.int64).values
                if cfg["value_map"]:
                    mapped = np.zeros(len(raw), dtype=np.int64)
                    for raw_val, midx in cfg["value_map"].items():
                        mapped[raw == int(raw_val)] = midx
                    cat_data[:, ci] = mapped
                else:
                    cat_data[:, ci] = np.clip(raw, 0, cfg["vocab_size"] - 1)

        # Location encoding
        loc_encs = np.zeros((n, tvm.LOCATION_ENC_DIM), dtype=np.float32)
        for ri in range(n):
            loc_encs[ri] = tvm.encode_location_sinusoidal(float(lats[ri]), float(lons[ri]))

        # Forward in batches
        batch_size = 2048
        all_hidden = np.zeros((n, tvm.HIDDEN_DIM), dtype=np.float32)

        for b_start in range(0, n, batch_size):
            b_end = min(b_start + batch_size, n)
            with torch.no_grad():
                b_cont = torch.from_numpy(cont_data[b_start:b_end])
                b_cat = torch.from_numpy(cat_data[b_start:b_end])
                b_intro = torch.full((b_end - b_start, 1), 0.5)
                b_temp = torch.from_numpy(ae_temporal_norm[b_start:b_end])
                b_land = torch.zeros(b_end - b_start, 5)
                b_phylo = torch.zeros(b_end - b_start, tvm.PHYLO_DIMS)
                b_loc = torch.from_numpy(loc_encs[b_start:b_end])

                _ = model(b_cont, b_cat, b_intro, b_temp, b_land, b_phylo, b_loc)
                all_hidden[b_start:b_end] = capture.hidden.cpu().numpy()

        sims_hidden = cosine_sim_batch(q_hidden, all_hidden)
        top_idx_h = np.argsort(sims_hidden)[-K:]
        for idx in top_idx_h:
            entry = (-float(sims_hidden[idx]), si, int(idx),
                     str(taxon_ids[idx]), float(lats[idx]), float(lons[idx]))
            if len(heap_hidden) < K:
                heapq.heappush(heap_hidden, entry)
            elif entry[0] < heap_hidden[0][0]:
                heapq.heapreplace(heap_hidden, entry)

        print(f" {n:,} rows ({time.time()-t0:.0f}s elapsed)", flush=True)

    capture.remove()

    elapsed = time.time() - t0
    print(f"\n  Total: {total_rows:,} rows scanned in {elapsed:.0f}s")

    # ── Analyze results ──────────────────────────────────────────────────

    def heap_to_sorted(heap):
        """Convert min-heap to sorted list (highest similarity first)."""
        items = sorted(heap, key=lambda x: x[0])  # most negative = highest sim
        results = []
        for neg_sim, si, ri, tid, lat, lon in items:
            info = classify_taxon(tid)
            info["similarity"] = -neg_sim
            info["shard"] = si
            info["lat"] = lat
            info["lon"] = lon
            info["is_nz"] = (-48.0 <= lat <= -34.0 and 166.0 <= lon <= 179.0)
            results.append(info)
        return results

    neighbors_ae = heap_to_sorted(heap_ae_primary)
    neighbors_temp = heap_to_sorted(heap_ae_temporal)
    neighbors_hidden = heap_to_sorted(heap_hidden)

    # ── Report ───────────────────────────────────────────────────────────

    def print_space_report(name, neighbors, top_n=50):
        print(f"\n{'='*72}")
        print(f"  {name} — Top-{len(neighbors)} Nearest Neighbors")
        print(f"{'='*72}")

        # Composition summary
        cats = {}
        nz_count = 0
        for n in neighbors:
            c = n["category"]
            cats[c] = cats.get(c, 0) + 1
            if n["is_nz"]:
                nz_count += 1

        print(f"\n  Category composition ({len(neighbors)} neighbors):")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            pct = 100 * count / len(neighbors)
            print(f"    {cat:25s}: {count:4d} ({pct:5.1f}%)")
        print(f"    {'NZ-local (lat/lon)':25s}: {nz_count:4d} ({100*nz_count/len(neighbors):5.1f}%)")

        # Top-N individual neighbors
        print(f"\n  Top-{top_n} closest:")
        print(f"  {'Rank':>4s}  {'Similarity':>10s}  {'Taxon ID':25s}  {'Category':20s}  {'Lat':>8s}  {'Lon':>8s}  {'NZ?':>4s}")
        print(f"  {'─'*4}  {'─'*10}  {'─'*25}  {'─'*20}  {'─'*8}  {'─'*8}  {'─'*4}")
        for i, n in enumerate(neighbors[:top_n]):
            nz_flag = " ✓" if n["is_nz"] else ""
            print(f"  {i+1:4d}  {n['similarity']:10.6f}  {n['taxon_id']:25s}  {n['category']:20s}  {n['lat']:8.2f}  {n['lon']:8.2f}  {nz_flag}")

        return cats

    cats_ae = print_space_report("AE Primary Embedding (64D, raw)", neighbors_ae)
    cats_temp = print_space_report("AE Temporal Sequence (512D, raw)", neighbors_temp)
    cats_hidden = print_space_report("Pre-Logit Hidden Space (384D, V4.2)", neighbors_hidden)

    # ── Logit comparison ─────────────────────────────────────────────────

    print(f"\n{'='*72}")
    print(f"  Model Logit Ranking (for comparison)")
    print(f"{'='*72}")

    top_logit_idx = np.argsort(q_probs)[::-1][:args.top_k]
    logit_cats = {}
    print(f"\n  Top-{min(50, args.top_k)} by model probability:")
    print(f"  {'Rank':>4s}  {'Prob':>10s}  {'Taxon ID':25s}  {'Category':20s}")
    print(f"  {'─'*4}  {'─'*10}  {'─'*25}  {'─'*20}")
    for rank, idx in enumerate(top_logit_idx[:50]):
        tid = idx_to_species[int(idx)]
        info = classify_taxon(tid)
        c = info["category"]
        logit_cats[c] = logit_cats.get(c, 0) + 1
        print(f"  {rank+1:4d}  {float(q_probs[idx]):10.6f}  {tid:25s}  {c:20s}")

    print(f"\n  Logit top-{args.top_k} composition:")
    for cat, count in sorted(logit_cats.items(), key=lambda x: -x[1]):
        pct = 100 * count / min(50, args.top_k)
        print(f"    {cat:25s}: {count:4d} ({pct:5.1f}%)")

    # ── Diagnosis ────────────────────────────────────────────────────────

    print(f"\n{'='*72}")
    print(f"  V4.3c DIAGNOSIS")
    print(f"{'='*72}")

    # Key question: do neighbors look plantation/radiata-like?
    ae_radiata = cats_ae.get("radiata", 0) + cats_ae.get("other_pinus", 0) + cats_ae.get("other_pinaceae", 0)
    ae_conifer = ae_radiata + cats_ae.get("other_conifer", 0) + cats_ae.get("nz_native_conifer", 0)
    ae_total = len(neighbors_ae)

    hidden_radiata = cats_hidden.get("radiata", 0) + cats_hidden.get("other_pinus", 0) + cats_hidden.get("other_pinaceae", 0)
    hidden_conifer = hidden_radiata + cats_hidden.get("other_conifer", 0) + cats_hidden.get("nz_native_conifer", 0)
    hidden_total = len(neighbors_hidden)

    logit_radiata = logit_cats.get("radiata", 0) + logit_cats.get("other_pinus", 0) + logit_cats.get("other_pinaceae", 0)

    print(f"""
  AE Primary neighbors:
    Pinaceae (radiata+pinus+pinaceae): {ae_radiata}/{ae_total} = {100*ae_radiata/ae_total:.1f}%
    All conifers:                      {ae_conifer}/{ae_total} = {100*ae_conifer/ae_total:.1f}%
    Angiosperms:                       {cats_ae.get('angiosperm',0)}/{ae_total} = {100*cats_ae.get('angiosperm',0)/ae_total:.1f}%

  Pre-logit hidden neighbors:
    Pinaceae (radiata+pinus+pinaceae): {hidden_radiata}/{hidden_total} = {100*hidden_radiata/hidden_total:.1f}%
    All conifers:                      {hidden_conifer}/{hidden_total} = {100*hidden_conifer/hidden_total:.1f}%
    Angiosperms:                       {cats_hidden.get('angiosperm',0)}/{hidden_total} = {100*cats_hidden.get('angiosperm',0)/hidden_total:.1f}%

  Model logit top-{min(50, args.top_k)}:
    Pinaceae:                          {logit_radiata}
    Angiosperms:                       {logit_cats.get('angiosperm',0)}
""")

    # Decision rule
    if ae_radiata / ae_total > 0.10 or hidden_radiata / hidden_total > 0.10:
        print("  CONCLUSION: Representation CONTAINS plantation/conifer signal")
        print("  → Classifier/fusion/head is the bottleneck")
        print("  → V4.4 (true background negatives) or V4.5 (loss tuning) likely helpful")
    else:
        if cats_ae.get("angiosperm", 0) / ae_total > 0.70:
            print("  CONCLUSION: Representation does NOT contain plantation signal")
            print("  → AE embeddings see this location as native broadleaf forest")
            print("  → Data scope / feature representation is the bottleneck")
            print("  → Backfill data (V4.3a) more important than loss tuning")
        else:
            print("  CONCLUSION: Mixed signal — further analysis needed")
            print("  → Check NZ-local vs global neighbor breakdown")

    # Save structured results
    report = {
        "benchmark": {
            "lat": CANONICAL_LAT, "lon": CANONICAL_LON, "year": CANONICAL_YEAR,
            "target": CANONICAL_TARGET,
            "rank": target_rank, "prob": target_prob,
        },
        "composition": {
            "ae_primary": cats_ae,
            "ae_temporal": {c: categorize_neighbors(neighbors_temp).get(c, 0) for c in set(n["category"] for n in neighbors_temp)},
            "hidden": cats_hidden,
            "logit_top50": logit_cats,
        },
        "top_neighbors": {
            "ae_primary_top20": [{"taxon_id": n["taxon_id"], "similarity": n["similarity"],
                                   "category": n["category"], "lat": n["lat"], "lon": n["lon"],
                                   "is_nz": n["is_nz"]}
                                  for n in neighbors_ae[:20]],
            "hidden_top20": [{"taxon_id": n["taxon_id"], "similarity": n["similarity"],
                              "category": n["category"], "lat": n["lat"], "lon": n["lon"],
                              "is_nz": n["is_nz"]}
                             for n in neighbors_hidden[:20]],
        },
        "total_rows_scanned": total_rows,
        "elapsed_seconds": elapsed,
    }

    report_path = Path(args.report_file).expanduser() if args.report_file else None
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Structured report saved to: {report_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="V4.3c Neighbor Probe")
    sub = parser.add_subparsers(dest="command")

    # Cache subcommand
    p_cache = sub.add_parser("cache", help="Cache benchmark features from GEE")
    p_cache.add_argument("--model-dir", required=True)
    p_cache.add_argument("--cache-file", default="orchestrator/v43c_benchmark_cache.npz")
    p_cache.add_argument("--feature-contract",
                         default="orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json")

    # Probe subcommand
    p_probe = sub.add_parser("probe", help="Run neighbor probe on training data")
    p_probe.add_argument("--model-dir", required=True)
    p_probe.add_argument("--cache-file", default="orchestrator/v43c_benchmark_cache.npz")
    p_probe.add_argument("--data-dir", required=True)
    p_probe.add_argument("--top-k", type=int, default=200)
    p_probe.add_argument("--feature-contract",
                         default="orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json")
    p_probe.add_argument("--frozen-cont-stats",
                         default="orchestrator/contracts/sinr_v3/normalize_stats_v41_preview_train.npz")
    p_probe.add_argument("--frozen-temporal-stats",
                         default="orchestrator/contracts/sinr_v3/normalize_temporal_v41_preview_train.npz")
    p_probe.add_argument("--report-file", default="orchestrator/v43c_probe_report.json")

    args = parser.parse_args()
    if args.command == "cache":
        cache_benchmark(args)
    elif args.command == "probe":
        run_probe(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
