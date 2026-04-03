#!/usr/bin/env python3
"""Build versioned SINR v3 species introduced-ratio contract from BigQuery."""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from google.cloud import bigquery


def parse_args():
    p = argparse.ArgumentParser(description="Build SINR v3 intro-ratio contract")
    p.add_argument("--project-id", default="treekipedia-479918")
    p.add_argument("--dataset", default="species_data")
    p.add_argument("--table", default="sinr_v3_unified_strict_train")
    p.add_argument("--mapping-contract", required=True)
    p.add_argument("--version", default="v1")
    p.add_argument("--out-dir", default="orchestrator/contracts/sinr_v3")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(Path(args.mapping_contract).expanduser()) as f:
        mapping = json.load(f)
    species_to_idx = {str(k): int(v) for k, v in mapping["species_to_idx"].items()}
    num_species = len(species_to_idx)
    mapping_sha = mapping.get("mapping_sha256")

    q = f"""
    SELECT
      taxon_id,
      AVG(CASE WHEN is_introduced IN (0,1) THEN CAST(is_introduced AS FLOAT64) ELSE NULL END) AS intro_ratio,
      COUNTIF(is_introduced IN (0,1)) AS n_known
    FROM `{args.project_id}.{args.dataset}.{args.table}`
    WHERE taxon_id IS NOT NULL
    GROUP BY taxon_id
    """

    client = bigquery.Client(project=args.project_id)
    rows = list(client.query(q).result())

    ratios = np.zeros(num_species, dtype=np.float32)
    known_counts = np.zeros(num_species, dtype=np.int64)
    in_mapping = 0
    out_mapping = 0
    for r in rows:
        tid = str(r["taxon_id"])
        if tid not in species_to_idx:
            out_mapping += 1
            continue
        idx = species_to_idx[tid]
        n_known = int(r["n_known"] or 0)
        ratio = float(r["intro_ratio"] or 0.0)
        ratios[idx] = max(0.0, min(1.0, ratio))
        known_counts[idx] = n_known
        in_mapping += 1

    payload = {
        "contract_name": "sinr_v3_intro_ratio_contract",
        "version": args.version,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source": {
            "project_id": args.project_id,
            "dataset": args.dataset,
            "table": args.table,
        },
        "mapping_sha256": mapping_sha,
        "num_species": num_species,
        "taxa_seen_in_mapping": in_mapping,
        "taxa_seen_outside_mapping": out_mapping,
        "species_intro_ratio": ratios.tolist(),
        "species_known_counts": known_counts.tolist(),
    }

    contract_path = out_dir / f"intro_ratio_contract_{args.version}.json"
    latest_path = out_dir / "intro_ratio_contract_latest.json"
    if contract_path.exists() and not args.overwrite:
        raise FileExistsError(f"Version exists: {contract_path}")

    with open(contract_path, "w") as f:
        json.dump(payload, f)
    with open(latest_path, "w") as f:
        json.dump(payload, f)

    nonzero = int((ratios > 0).sum())
    print(f"Wrote {contract_path}")
    print(f"num_species={num_species} nonzero_intro_ratio={nonzero}")
    print(f"intro_ratio min={float(ratios.min()):.4f} mean={float(ratios.mean()):.4f} max={float(ratios.max()):.4f}")


if __name__ == "__main__":
    main()
