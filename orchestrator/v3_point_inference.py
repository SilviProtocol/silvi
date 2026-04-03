#!/usr/bin/env python3
"""
SINR v3 point inference (local model artifacts).

Uses the trained v3 model (`best_model.pt`) and samples GEE features at a point.
This is a real v3 forward path (all model heads active), not the old v2.2 endpoint.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch


def parse_args():
    p = argparse.ArgumentParser(description="Run SINR v3 point inference")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--year", type=int, default=2023)
    p.add_argument("--model-dir", default="~/model_local_5m")
    p.add_argument("--artifact-version", default=None,
                   help="Load versioned artifacts: *_<version>.*")
    p.add_argument("--feature-contract", default=None,
                   help="Feature contract JSON specifying env_continuous_cols")
    p.add_argument("--mapping-contract", default=None,
                   help="Optional mapping contract JSON for hash validation")
    p.add_argument("--intro-ratio-contract", default=None,
                   help="Optional species introduced-ratio contract JSON")
    p.add_argument("--species-frequency-contract", default=None,
                   help="Optional species frequency contract JSON for logit adjustment")
    p.add_argument("--logit-adjust-tau", type=float, default=0.0,
                   help="Subtract tau*log(class_count) from logits at inference")
    p.add_argument("--tdwg-contract", default=None,
                   help="TDWG frequency contract JSON for spatial prior boost")
    p.add_argument("--tdwg-boost-weight", type=float, default=2.0,
                   help="Strength of TDWG frequency boost (default: 2.0)")
    p.add_argument("--tdwg-alpha", type=float, default=10.0,
                   help="Scaling factor inside log for TDWG boost (default: 10.0)")
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--target-taxon", default="GymPiPiPnCx50820-00")
    p.add_argument(
        "--introduced-mode",
        choices=["native", "introduced", "unknown", "all"],
        default="all",
        help="Value used for is_introduced input",
    )
    p.add_argument(
        "--land-state-mode",
        choices=["zero", "heuristic", "planted_only"],
        default="heuristic",
        help="How to populate land-state inputs (planted_only: zero base + is_planted dim)",
    )
    p.add_argument(
        "--strict-feature-contract",
        action="store_true",
        help="Fail if required v3 point features are missing at sampling time",
    )
    p.add_argument("--disable-intro-in-gate", action="store_true",
                   help="Instantiate model without is_introduced in gate input")
    p.add_argument("--enable-intro-residual", action="store_true",
                   help="Instantiate model with separate introduced residual path")
    p.add_argument("--use-location-encoding", action="store_true",
                   help="Enable sinusoidal location encoding (must match training)")
    p.add_argument("--use-temporal-magnitude", action="store_true",
                   help="Enable temporal magnitude features (must match training)")
    p.add_argument("--no-boost", action="store_true",
                   help="Remove planted boost mechanism entirely (v18+)")
    p.add_argument("--planted-as-land-state", action="store_true",
                   help="Model expects 6D land_state with is_planted as 6th dim (v18+)")
    return p.parse_args()


def mapping_sha256(species_to_idx):
    payload = json.dumps(species_to_idx, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_versioned(base: Path, stem: str, suffix: str, version: str):
    candidate = base / f"{stem}_{version}{suffix}"
    return candidate if candidate.exists() else (base / f"{stem}{suffix}")


def load_intro_ratio_contract(path: Path, expected_mapping_sha: str, num_species: int):
    with open(path) as f:
        payload = json.load(f)
    got_sha = payload.get("mapping_sha256")
    if got_sha and expected_mapping_sha and got_sha != expected_mapping_sha:
        raise ValueError(
            f"Intro-ratio mapping hash mismatch: expected={expected_mapping_sha}, got={got_sha}"
        )
    ratios = np.asarray(payload.get("species_intro_ratio"), dtype=np.float32)
    if ratios.shape[0] != num_species:
        raise ValueError(
            f"Intro-ratio length mismatch: got={ratios.shape[0]}, expected={num_species}"
        )
    return np.clip(ratios, 0.0, 1.0)


def load_frequency_contract(path: Path, expected_mapping_sha: str, num_species: int):
    with open(path) as f:
        payload = json.load(f)
    got_sha = payload.get("mapping_sha256")
    if got_sha and expected_mapping_sha and got_sha != expected_mapping_sha:
        raise ValueError(
            f"Frequency mapping hash mismatch: expected={expected_mapping_sha}, got={got_sha}"
        )
    counts = np.asarray(payload.get("class_counts"), dtype=np.float32)
    if counts.shape[0] != num_species:
        raise ValueError(
            f"Frequency length mismatch: got={counts.shape[0]}, expected={num_species}"
        )
    return np.clip(counts, 1.0, None)


def load_tdwg_contract(path: Path):
    with open(path) as f:
        payload = json.load(f)
    return payload.get("regions", payload)


def lookup_tdwg_region(lat: float, lon: float, repo_root: Path):
    """Find the TDWG L3 region code for a (lat, lon) point using local shapefile."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        return None
    geojson = repo_root / "orchestrator" / "tdwg_l3" / "level3.geojson"
    if not geojson.exists():
        return None
    gdf = gpd.read_file(geojson)
    pt = Point(lon, lat)
    for _, row in gdf.iterrows():
        if row.geometry.contains(pt):
            return row.get("LEVEL3_COD") or row.get("Level3_cod")
    return None


def build_tdwg_boost(
    tdwg_regions: dict,
    tdwg_code: str,
    species_to_idx: dict,
    num_species: int,
    weight: float = 2.0,
    alpha: float = 10.0,
):
    """Build a per-species logit boost vector from TDWG frequency data."""
    boost = np.zeros(num_species, dtype=np.float32)
    if tdwg_code is None or tdwg_code not in tdwg_regions:
        return boost
    region_freqs = tdwg_regions[tdwg_code]
    for taxon_id, freq_ratio in region_freqs.items():
        idx = species_to_idx.get(taxon_id)
        if idx is not None:
            boost[idx] = weight * math.log(1 + alpha * freq_ratio)
    return boost


def load_training_module(repo_root: Path):
    import importlib.util

    mod_path = repo_root / "orchestrator" / "train_on_vm.py"
    spec = importlib.util.spec_from_file_location("train_on_vm", str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_sampling_module(repo_root: Path):
    import importlib.util

    mod_path = repo_root / "orchestrator" / "location_predictor_FIXED.py"
    spec = importlib.util.spec_from_file_location("location_predictor_fixed", str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sample_ae_year(locfix, lat: float, lon: float, year: int) -> np.ndarray:
    out = np.zeros(64, dtype=np.float32)
    res = locfix.sample_alphaearth_properly(lat, lon, year)
    if not res.get("success"):
        return out
    emb = res.get("embedding", {})
    for i in range(64):
        out[i] = float(emb.get(f"a{i:02d}", 0.0) or 0.0)
    return out


def compute_land_state(feat: dict, ae_temporal_flat: np.ndarray, mode: str, year: int,
                       planted_as_land_state: bool = False) -> np.ndarray:
    xiao = int(round(float(feat.get("xiao_planted_forest", 0.0) or 0.0)))
    is_planted = 1.0 if xiao == 2 else 0.0

    if mode == "zero":
        base = np.zeros(5, dtype=np.float32)
        if planted_as_land_state:
            return np.append(base, is_planted).astype(np.float32)
        return base

    if mode == "planted_only":
        base = np.zeros(5, dtype=np.float32)
        return np.append(base, is_planted).astype(np.float32)

    treecover = float(feat.get("treecover2000", 0.0) or 0.0)
    lossyear = float(feat.get("lossyear", 0.0) or 0.0)
    fire = float(feat.get("fire_frequency_count", 0.0) or 0.0)

    if xiao == 2:
        land_state_class = 2.0
    elif treecover >= 20.0:
        land_state_class = 1.0
    else:
        land_state_class = 0.0

    disturbance_intensity = min(1.0, fire / 5.0 + (0.5 if lossyear > 0 else 0.0))

    yearly = ae_temporal_flat.reshape(8, 64)
    diffs = yearly[1:] - yearly[:-1]
    l2 = np.linalg.norm(diffs, axis=1)
    ae_temporal_change_l2 = float(np.mean(l2)) if len(l2) else 0.0

    forest_stability = max(0.0, 1.0 - disturbance_intensity)

    if lossyear > 0:
        loss_abs_year = 2000 + int(lossyear)
        years_since_loss = max(0, year - loss_abs_year)
        successional_stage = float(min(5, years_since_loss // 5))
    else:
        successional_stage = 5.0 if treecover >= 20.0 else 0.0

    base = np.array(
        [
            land_state_class,
            disturbance_intensity,
            forest_stability,
            successional_stage,
            ae_temporal_change_l2,
        ],
        dtype=np.float32,
    )
    if planted_as_land_state:
        return np.append(base, is_planted).astype(np.float32)
    return base


def build_feature_inputs(
    tvm,
    locfix,
    lat: float,
    lon: float,
    year: int,
    land_state_mode: str,
    strict_feature_contract: bool,
    planted_as_land_state: bool = False,
):
    # Point sampling
    elev = locfix.sample_srtm_elevation(lat, lon)
    hansen = locfix.sample_hansen_forest(lat, lon)
    worldclim = locfix.sample_worldclim_bio(lat, lon)
    soil = locfix.sample_openlandmap_soil(lat, lon)
    sinr_env = locfix.sample_sinr_env_features(lat, lon, year)

    # Primary embedding (year requested)
    emb_year = sample_ae_year(locfix, lat, lon, year)

    # Temporal embeddings 2017..2024 (8*64)
    temporal_parts = []
    for y in range(2017, 2025):
        temporal_parts.append(sample_ae_year(locfix, lat, lon, y))
    ae_temporal = np.concatenate(temporal_parts, axis=0).astype(np.float32)

    feat = {}

    # emb_00..emb_63
    for i in range(64):
        feat[f"emb_{i:02d}"] = float(emb_year[i])

    # core top-level fields
    feat["elevation"] = float(elev.get("elevation", 0.0) or 0.0)
    feat["treecover2000"] = float(hansen.get("treecover2000", 0.0) or 0.0)
    feat["lossyear"] = float(hansen.get("lossyear", 0.0) or 0.0)

    # WorldClim: convert temp vars to x10 scale expected by training table
    for i in range(1, 20):
        key = f"bio{i:02d}"
        val = float(worldclim.get(key, 0.0) or 0.0)
        if i <= 11:
            val *= 10.0
        feat[key] = val

    # Soil: soil_ph expected in x10 scale
    feat["soil_ph"] = float(soil.get("soil_ph", 0.0) or 0.0) * 10.0
    feat["soil_clay_pct"] = float(soil.get("soil_clay_pct", 0.0) or 0.0)
    feat["soil_sand_pct"] = float(soil.get("soil_sand_pct", 0.0) or 0.0)
    feat["soil_organic_carbon"] = float(soil.get("soil_organic_carbon_g_kg", 0.0) or 0.0)

    # Bulk env from batched SINR sampler
    for k, v in sinr_env.items():
        try:
            feat[k] = float(v) if v is not None else 0.0
        except Exception:
            feat[k] = 0.0
    feat.setdefault("tc_vpd_delta", 0.0)

    # Continuous vector
    cont_cols = tvm.AE_EMB_COLS + tvm.ENV_CONTINUOUS_COLS
    x_cont = np.array([float(feat.get(c, 0.0) or 0.0) for c in cont_cols], dtype=np.float32)

    active_cat = getattr(tvm, "CATEGORICAL_FEATURES", {})

    # Categorical indices
    cat_values = []
    for col, cfg in active_cat.items():
        raw = int(round(float(feat.get(col, 0.0) or 0.0)))
        if cfg["value_map"]:
            mapped = int(cfg["value_map"].get(raw, 0))
        else:
            mapped = raw if 0 <= raw < cfg["vocab_size"] else 0
        cat_values.append(mapped)
    x_cat = np.array(cat_values, dtype=np.int64)

    # Land-state inputs
    if getattr(tvm, "LAND_STATE_COLS", []):
        x_land = compute_land_state(feat, ae_temporal, land_state_mode, year,
                                    planted_as_land_state=planted_as_land_state)
    else:
        x_land = np.zeros(1 if planted_as_land_state else 0, dtype=np.float32)

    missing_cont = [c for c in tvm.ENV_CONTINUOUS_COLS if c not in feat]
    missing_cat = [c for c in active_cat.keys() if c not in feat]
    if strict_feature_contract and (missing_cont or missing_cat):
        raise ValueError(
            f"Missing required feature-contract fields: env_missing={len(missing_cont)}, "
            f"cat_missing={len(missing_cat)}"
        )

    return x_cont, x_cat, ae_temporal, x_land


def align_normalization(stats_path: Path, current_cols: list):
    stats = np.load(stats_path, allow_pickle=True)
    mean = stats["mean"].astype(np.float32)
    std = stats["std"].astype(np.float32)
    std[std < 1e-8] = 1.0
    saved_cols = [str(x) for x in stats["columns"]]

    if saved_cols == current_cols:
        return mean, std

    aligned_mean = np.zeros(len(current_cols), dtype=np.float32)
    aligned_std = np.ones(len(current_cols), dtype=np.float32)
    idx = {c: i for i, c in enumerate(saved_cols)}
    for i, c in enumerate(current_cols):
        if c in idx:
            j = idx[c]
            aligned_mean[i] = mean[j]
            aligned_std[i] = std[j]
    return aligned_mean, aligned_std


def run_one_pass(
    model,
    idx_to_species,
    x_cont,
    x_cat,
    x_intro,
    x_temporal,
    x_land,
    x_phylo,
    top_k,
    logit_adjust=None,
    tau=0.0,
    tdwg_boost=None,
    x_location=None,
):
    with torch.no_grad():
        logits, _, _ = model(x_cont, x_cat, x_intro, x_temporal, x_land, x_phylo, x_location)
        if logit_adjust is not None and tau > 0:
            logits = logits - tau * logit_adjust
        if tdwg_boost is not None:
            logits = logits + torch.from_numpy(tdwg_boost).unsqueeze(0)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

    top_idx = np.argsort(probs)[::-1][:top_k]
    top = [(rank + 1, idx_to_species[int(i)], float(probs[i])) for rank, i in enumerate(top_idx)]
    return probs, top


def main():
    args = parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    tvm = load_training_module(repo_root)
    locfix = load_sampling_module(repo_root)

    if args.feature_contract:
        fc_path = Path(args.feature_contract).expanduser()
        with open(fc_path) as f:
            feature_contract = json.load(f)
        tvm.ENV_CONTINUOUS_COLS = [str(c) for c in feature_contract["env_continuous_cols"]]
        contract_cat_cols = [str(c) for c in feature_contract.get("categorical_features", [])]
        contract_land_state_cols = [str(c) for c in feature_contract.get("land_state_cols", [])]
        tvm.CATEGORICAL_FEATURES = {
            k: v for k, v in tvm.CATEGORICAL_FEATURES.items() if k in contract_cat_cols
        }
        tvm.LAND_STATE_COLS = [c for c in tvm.LAND_STATE_COLS if c in contract_land_state_cols]

    model_dir = Path(args.model_dir).expanduser()
    ckpt_path = model_dir / "best_model.pt"
    version = args.artifact_version
    if version:
        stats_path = resolve_versioned(model_dir, "normalize_stats_v3", ".npz", version)
        temporal_stats_path = resolve_versioned(model_dir, "normalize_temporal_v3", ".npz", version)
        mapping_path = resolve_versioned(model_dir, "species_mapping_v3", ".json", version)
    else:
        stats_path = model_dir / "normalize_stats_v3.npz"
        temporal_stats_path = model_dir / "normalize_temporal_v3.npz"
        mapping_path = model_dir / "species_mapping_v3.json"

    if not ckpt_path.exists():
        raise FileNotFoundError(f"Missing model checkpoint: {ckpt_path}")
    if not stats_path.exists() or not mapping_path.exists():
        raise FileNotFoundError("Missing normalization stats or species mapping")

    with open(mapping_path) as f:
        species_mapping = json.load(f)
    species_to_idx = species_mapping["species_to_idx"]
    if args.mapping_contract:
        with open(Path(args.mapping_contract).expanduser()) as f:
            contract = json.load(f)
        expected_sha = contract.get("mapping_sha256")
        if expected_sha:
            actual_sha = mapping_sha256(species_to_idx)
            if actual_sha != expected_sha:
                raise ValueError(
                    "Mapping hash mismatch against contract: "
                    f"expected={expected_sha}, actual={actual_sha}"
                )
    idx_to_species = {int(k): v for k, v in species_mapping["idx_to_species"].items()}
    num_species = len(species_to_idx)
    mapping_sha = species_mapping.get("mapping_sha256")

    planted_as_ls = getattr(args, 'planted_as_land_state', False)
    x_cont_np, x_cat_np, x_temporal_np, x_land_np = build_feature_inputs(
        tvm,
        locfix,
        args.lat,
        args.lon,
        args.year,
        args.land_state_mode,
        strict_feature_contract=args.strict_feature_contract,
        planted_as_land_state=planted_as_ls,
    )

    cont_cols = tvm.AE_EMB_COLS + tvm.ENV_CONTINUOUS_COLS
    cont_mean, cont_std = align_normalization(stats_path, cont_cols)
    x_cont_np = (x_cont_np - cont_mean) / cont_std

    if temporal_stats_path.exists():
        ts = np.load(temporal_stats_path, allow_pickle=True)
        tmean = ts["mean"].astype(np.float32)
        tstd = ts["std"].astype(np.float32)
        tstd[tstd < 1e-8] = 1.0
        x_temporal_np = (x_temporal_np - tmean) / tstd

    # Phylo vector is not available from point query -> zero vector
    x_phylo_np = np.zeros((1, tvm.PHYLO_DIMS), dtype=np.float32)

    x_cont = torch.from_numpy(x_cont_np.astype(np.float32)).unsqueeze(0)
    x_cat = torch.from_numpy(x_cat_np.astype(np.int64)).unsqueeze(0)
    x_temporal = torch.from_numpy(x_temporal_np.astype(np.float32)).unsqueeze(0)
    x_land = torch.from_numpy(x_land_np.astype(np.float32)).unsqueeze(0)
    x_phylo = torch.from_numpy(x_phylo_np)

    use_location = args.use_location_encoding
    use_temporal_mag = args.use_temporal_magnitude
    if getattr(tvm, "LAND_STATE_COLS", []):
        land_state_dim_in = 6 if planted_as_ls else 5
    else:
        land_state_dim_in = 1 if planted_as_ls else 0
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
        gate_use_intro=(not args.disable_intro_in_gate),
        intro_residual=args.enable_intro_residual,
        location_enc_dim=tvm.LOCATION_ENC_DIM if use_location else 0,
        use_temporal_magnitude=use_temporal_mag,
        land_state_input_dim=land_state_dim_in,
    )
    if getattr(args, 'no_boost', False):
        model._no_boost = True
    ckpt = torch.load(ckpt_path, map_location="cpu")
    model.load_state_dict(ckpt["model_state_dict"])
    if args.intro_ratio_contract:
        intro_ratio = load_intro_ratio_contract(
            Path(args.intro_ratio_contract).expanduser(), mapping_sha, num_species
        )
        with torch.no_grad():
            model.species_intro_ratio.copy_(torch.from_numpy(intro_ratio))

    logit_adjust = None
    if args.species_frequency_contract:
        class_counts = load_frequency_contract(
            Path(args.species_frequency_contract).expanduser(), mapping_sha, num_species
        )
        logit_adjust = torch.from_numpy(np.log(class_counts)).unsqueeze(0)

    tdwg_boost = None
    tdwg_code = None
    if args.tdwg_contract:
        tdwg_regions = load_tdwg_contract(Path(args.tdwg_contract).expanduser())
        tdwg_code = lookup_tdwg_region(args.lat, args.lon, repo_root)
        if tdwg_code:
            tdwg_boost = build_tdwg_boost(
                tdwg_regions, tdwg_code, species_to_idx, num_species,
                weight=args.tdwg_boost_weight, alpha=args.tdwg_alpha,
            )
            nonzero = int((tdwg_boost > 0).sum())
            print(f"TDWG region: {tdwg_code} ({nonzero} species with boost)")
        else:
            print("TDWG region: not found (ocean or missing shapefile)")

    model.eval()

    intro_modes = {
        "native": [0.0],
        "unknown": [0.5],
        "introduced": [1.0],
        "all": [0.0, 0.5, 1.0],
    }[args.introduced_mode]

    target_idx = species_to_idx.get(args.target_taxon)

    # Location encoding
    x_location = None
    if use_location:
        loc_enc = tvm.encode_location_sinusoidal(args.lat, args.lon)
        x_location = torch.from_numpy(loc_enc).reshape(1, -1)

    print("=" * 72)
    print(f"SINR v3 point inference at ({args.lat}, {args.lon}), year={args.year}")
    print(f"model: {ckpt_path}")
    print(f"species space: {num_species:,}")
    print(f"land_state_mode: {args.land_state_mode}")
    if use_location:
        print(f"location_encoding: ON ({tvm.LOCATION_ENC_DIM}D)")
    if tdwg_code:
        print(f"tdwg_region: {tdwg_code} (boost_weight={args.tdwg_boost_weight}, alpha={args.tdwg_alpha})")
    print("=" * 72)

    for val in intro_modes:
        probs, top = run_one_pass(
            model,
            idx_to_species,
            x_cont,
            x_cat,
            torch.tensor([[val]], dtype=torch.float32),
            x_temporal,
            x_land,
            x_phylo,
            args.top_k,
            logit_adjust=logit_adjust,
            tau=args.logit_adjust_tau,
            tdwg_boost=tdwg_boost,
            x_location=x_location,
        )

        print(f"\n-- is_introduced={val:.1f} --")
        if target_idx is not None:
            tp = float(probs[target_idx])
            trank = int((probs > tp).sum() + 1)
            print(
                f"target {args.target_taxon}: rank {trank:,}/{num_species:,}, prob={tp:.6f}"
            )
        else:
            print(f"target {args.target_taxon}: not found in species mapping")

        print("top predictions:")
        for rank, taxon, p in top:
            print(f"  {rank:2d}. {taxon} ({p:.6f})")


if __name__ == "__main__":
    main()
