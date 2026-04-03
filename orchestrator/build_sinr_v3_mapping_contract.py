#!/usr/bin/env python3
"""Build a versioned SINR v3 species mapping contract from BigQuery strict table."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from google.cloud import bigquery


def mapping_sha256(species_to_idx):
    payload = json.dumps(species_to_idx, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_args():
    p = argparse.ArgumentParser(description="Build SINR v3 mapping contract")
    p.add_argument("--project-id", default="treekipedia-479918")
    p.add_argument("--dataset", default="species_data")
    p.add_argument("--table", default="sinr_v3_unified_strict_train")
    p.add_argument("--version", default="v1")
    p.add_argument(
        "--out-dir",
        default="orchestrator/contracts/sinr_v3",
        help="Directory for versioned contract files",
    )
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    contract_path = out_dir / f"mapping_contract_{args.version}.json"
    mapping_path = out_dir / f"species_mapping_{args.version}.json"

    if (contract_path.exists() or mapping_path.exists()) and not args.overwrite:
        raise FileExistsError(
            f"Version exists. Use --overwrite to replace: {contract_path}"
        )

    client = bigquery.Client(project=args.project_id)
    q = f"""
    SELECT DISTINCT taxon_id
    FROM `{args.project_id}.{args.dataset}.{args.table}`
    WHERE taxon_id IS NOT NULL
    ORDER BY taxon_id
    """
    rows = list(client.query(q).result())
    taxa = [str(r["taxon_id"]) for r in rows]

    species_to_idx = {taxon_id: i for i, taxon_id in enumerate(taxa)}
    idx_to_species = {str(i): taxon_id for taxon_id, i in species_to_idx.items()}
    sha = mapping_sha256(species_to_idx)

    contract = {
        "contract_name": "sinr_v3_species_mapping",
        "version": args.version,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source": {
            "project_id": args.project_id,
            "dataset": args.dataset,
            "table": args.table,
        },
        "num_species": len(species_to_idx),
        "mapping_sha256": sha,
        "species_to_idx": species_to_idx,
        "idx_to_species": idx_to_species,
    }

    mapping_payload = {
        "artifact_version": args.version,
        "num_species": len(species_to_idx),
        "mapping_sha256": sha,
        "species_to_idx": species_to_idx,
        "idx_to_species": idx_to_species,
    }

    with open(contract_path, "w") as f:
        json.dump(contract, f, indent=2)
    with open(mapping_path, "w") as f:
        json.dump(mapping_payload, f)

    latest_contract = out_dir / "mapping_contract_latest.json"
    latest_mapping = out_dir / "species_mapping_latest.json"
    with open(latest_contract, "w") as f:
        json.dump(contract, f, indent=2)
    with open(latest_mapping, "w") as f:
        json.dump(mapping_payload, f)

    print(f"Wrote {contract_path}")
    print(f"Wrote {mapping_path}")
    print(f"num_species={len(species_to_idx):,}")
    print(f"mapping_sha256={sha}")


if __name__ == "__main__":
    main()
