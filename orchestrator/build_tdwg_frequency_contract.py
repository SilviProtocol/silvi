#!/usr/bin/env python3
"""
Build a TDWG Region Frequency Contract for SINR v3.

Queries BigQuery to compute per-species occurrence frequency within each
TDWG Level 3 region, then saves a JSON contract that can be used as a
post-logit spatial prior at inference time.

The contract maps each TDWG region code to a dict of {taxon_id: freq_ratio},
where freq_ratio = species_count / total_occurrences_in_region.

Usage:
    python3 build_tdwg_frequency_contract.py \
        --species-mapping ~/model_local_contract_v13_cyclic_5m/species_mapping_v3.json \
        --output orchestrator/contracts/sinr_v3/tdwg_frequency_contract_v1.json

    # Dry-run (print SQL only):
    python3 build_tdwg_frequency_contract.py --dry-run
"""

import argparse
import json
import math
import sys
from pathlib import Path


BQ_PROJECT = "treekipedia-479918"
BQ_DATASET = "species_data"

QUERY = f"""
WITH occ_tdwg AS (
    SELECT
        o.taxon_id,
        t.LEVEL3_COD AS tdwg_code,
        COUNT(*) AS occ_count
    FROM `{BQ_PROJECT}.{BQ_DATASET}.occurrences` o
    JOIN `{BQ_PROJECT}.{BQ_DATASET}.tdwg_level3` t
        ON ST_CONTAINS(t.geometry, ST_GEOGPOINT(o.decimalLongitude, o.decimalLatitude))
    WHERE o.decimalLatitude IS NOT NULL
      AND o.decimalLongitude IS NOT NULL
      AND o.decimalLatitude BETWEEN -90 AND 90
      AND o.decimalLongitude BETWEEN -180 AND 180
    GROUP BY o.taxon_id, t.LEVEL3_COD
),
region_totals AS (
    SELECT
        tdwg_code,
        SUM(occ_count) AS total_occ
    FROM occ_tdwg
    GROUP BY tdwg_code
)
SELECT
    ot.tdwg_code,
    ot.taxon_id,
    ot.occ_count,
    rt.total_occ,
    SAFE_DIVIDE(ot.occ_count, rt.total_occ) AS freq_ratio
FROM occ_tdwg ot
JOIN region_totals rt USING (tdwg_code)
ORDER BY ot.tdwg_code, ot.occ_count DESC
"""


def parse_args():
    p = argparse.ArgumentParser(description="Build TDWG frequency contract")
    p.add_argument(
        "--species-mapping",
        default=None,
        help="Path to species_mapping_v3.json to filter to known species only",
    )
    p.add_argument(
        "--output",
        default="orchestrator/contracts/sinr_v3/tdwg_frequency_contract_v1.json",
        help="Output JSON path",
    )
    p.add_argument("--dry-run", action="store_true", help="Print SQL and exit")
    p.add_argument(
        "--min-count",
        type=int,
        default=3,
        help="Minimum occurrences to include a species in a region (noise filter)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if args.dry_run:
        print(QUERY)
        return 0

    try:
        from google.cloud import bigquery
    except ImportError:
        print("ERROR: google-cloud-bigquery not installed", file=sys.stderr)
        print("  pip install google-cloud-bigquery", file=sys.stderr)
        return 1

    known_species = None
    if args.species_mapping:
        mp = Path(args.species_mapping).expanduser()
        with open(mp) as f:
            mapping = json.load(f)
        known_species = set(mapping["species_to_idx"].keys())
        print(f"Loaded species mapping: {len(known_species):,} species")

    print("Running BQ query (this may take 5-15 minutes on 96.5M rows)...")
    client = bigquery.Client(project=BQ_PROJECT)
    df = client.query(QUERY).to_dataframe()
    print(f"Query returned {len(df):,} rows across {df['tdwg_code'].nunique()} regions")

    # Filter to known species and minimum count
    if known_species:
        before = len(df)
        df = df[df["taxon_id"].isin(known_species)]
        print(f"Filtered to known species: {len(df):,} rows (dropped {before - len(df):,})")

    df = df[df["occ_count"] >= args.min_count]
    print(f"After min_count={args.min_count} filter: {len(df):,} rows")

    # Build contract: {tdwg_code: {taxon_id: freq_ratio}}
    contract = {}
    for _, row in df.iterrows():
        code = row["tdwg_code"]
        if code not in contract:
            contract[code] = {}
        contract[code][row["taxon_id"]] = round(float(row["freq_ratio"]), 8)

    # Add metadata
    output = {
        "version": "v1",
        "description": "TDWG L3 region species frequency ratios from GBIF occurrences",
        "source_table": f"{BQ_PROJECT}.{BQ_DATASET}.occurrences",
        "tdwg_table": f"{BQ_PROJECT}.{BQ_DATASET}.tdwg_level3",
        "min_count": args.min_count,
        "num_regions": len(contract),
        "total_entries": sum(len(v) for v in contract.values()),
        "regions": contract,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=None, separators=(",", ":"))

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nContract written: {out_path} ({size_mb:.1f} MB)")
    print(f"  Regions: {len(contract)}")
    print(f"  Total species-region entries: {output['total_entries']:,}")

    # Print sample for NZ
    for code in ["NZN", "NZS"]:
        if code in contract:
            top5 = sorted(contract[code].items(), key=lambda x: -x[1])[:5]
            print(f"\n  Sample {code}:")
            for tid, fr in top5:
                print(f"    {tid}: {fr:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
