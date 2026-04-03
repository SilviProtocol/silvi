#!/usr/bin/env python3
"""Check status of a fresh validation extraction run."""

from __future__ import annotations

import argparse
import sys

import ee
from google.api_core.exceptions import NotFound
from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-table", required=True)
    args = p.parse_args()

    client = bigquery.Client(project=PROJECT)
    full_table = f"{PROJECT}.{DATASET}.{args.out_table}"
    try:
        tbl = client.get_table(full_table)
        print(f"bq_rows={tbl.num_rows} cols={len(tbl.schema)} bytes={tbl.num_bytes or 0}")
    except NotFound:
        print("bq_table=NOT_FOUND")

    ee.Initialize(project=PROJECT)
    ops = ee.data.listOperations()
    prefix = "sinr_v3_strict_validation_"
    matched = []
    for op in ops:
        md = op.get("metadata", {})
        desc = md.get("description", "")
        if desc.startswith(prefix):
            matched.append((desc, md.get("state")))

    print(f"ee_validation_ops={len(matched)}")
    for desc, state in matched[:50]:
        print(f"{state}\t{desc}")


if __name__ == "__main__":
    main()
