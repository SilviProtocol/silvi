#!/usr/bin/env python3
"""Build versioned SINR v3 feature contracts."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import train_on_vm as tvm


OFFLINE_ONLY_ENV = {
    "carbon_canopy_height_m",
    "spawn_agb", "spawn_agb_unc", "spawn_bgb", "spawn_bgb_unc",
    "gedi_l4b_agbd", "gedi_l4b_agbd_se", "gedi_rh98", "gedi_fhd",
    "soc_0cm", "soc_30cm", "soc_100cm", "soc_200cm",
    "npp_at_obs", "gpp_at_obs", "lai_at_obs", "fpar_at_obs", "evi_at_obs",
    "cci_agb_at_obs", "cci_agb_sd_at_obs",
    "npp_at_ae", "gpp_at_ae", "lai_at_ae", "fpar_at_ae", "evi_at_ae",
    "cci_agb_at_ae", "cci_agb_sd_at_ae",
    "npp_mean_longterm", "npp_trend",
    "hilda_lulc_at_obs", "hilda_lulc_at_ae",
}


def parse_args():
    p = argparse.ArgumentParser(description="Build SINR v3 feature contract")
    p.add_argument("--version", default="v1_online")
    p.add_argument("--mode", choices=["full", "online"], default="online")
    p.add_argument("--out-dir", default="orchestrator/contracts/sinr_v3")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def sha256_list(values):
    payload = json.dumps(values, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env_cols_full = list(tvm.ENV_CONTINUOUS_COLS)
    if args.mode == "online":
        env_cols = [c for c in env_cols_full if c not in OFFLINE_ONLY_ENV]
    else:
        env_cols = env_cols_full

    payload = {
        "contract_name": "sinr_v3_feature_contract",
        "version": args.version,
        "mode": args.mode,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "num_ae_embeddings": len(tvm.AE_EMB_COLS),
        "num_ae_temporal": len(tvm.AE_TEMPORAL_COLS),
        "num_env_continuous": len(env_cols),
        "env_continuous_sha256": sha256_list(env_cols),
        "env_continuous_cols": env_cols,
        "categorical_features": list(tvm.CATEGORICAL_FEATURES.keys()),
        "land_state_cols": list(tvm.LAND_STATE_COLS),
        "excluded_offline_env": sorted(list(OFFLINE_ONLY_ENV if args.mode == "online" else [])),
    }

    contract_path = out_dir / f"feature_contract_{args.version}.json"
    latest_path = out_dir / "feature_contract_latest.json"
    if contract_path.exists() and not args.overwrite:
        raise FileExistsError(f"Version exists: {contract_path}")

    with open(contract_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {contract_path}")
    print(f"num_env_continuous={len(env_cols)} mode={args.mode}")


if __name__ == "__main__":
    main()
