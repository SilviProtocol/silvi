#!/usr/bin/env python3
"""Run isolated fresh strict extraction for a validation batch.

This uses the same strict extraction logic as the main strict sampler,
but writes to a dedicated validation table so it does not pollute active
strict-full outputs.
"""

from __future__ import annotations

import argparse

import ee
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

import unified_gee_sampler_v3_strict as strict


PROJECT = strict.PROJECT
DATASET = strict.BQ_DATASET


def load_batch(batch_table: str) -> pd.DataFrame:
    client = bigquery.Client(project=PROJECT)
    q = f"""
    SELECT DISTINCT
      CAST(lat4 AS FLOAT64) AS lat4dp,
      CAST(lon4 AS FLOAT64) AS lon4dp,
      observation_year,
      emb_year
    FROM `{PROJECT}.{DATASET}.{batch_table}`
    """
    return client.query(q).to_dataframe()


def load_completed_contexts(out_table: str) -> set[str]:
    client = bigquery.Client(project=PROJECT)
    try:
        client.get_table(f"{PROJECT}.{DATASET}.{out_table}")
    except NotFound:
        return set()

    q = f"""
    SELECT DISTINCT CONCAT(
      FORMAT('%.4f', ROUND(latitude, 4)), '|',
      FORMAT('%.4f', ROUND(longitude, 4)), '|',
      CAST(observation_year AS STRING), '|',
      CAST(emb_year AS STRING)
    ) AS k
    FROM `{PROJECT}.{DATASET}.{out_table}`
    """
    df = client.query(q).to_dataframe()
    return set(df["k"].tolist())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--batch-table", required=True)
    p.add_argument("--out-table", required=True)
    p.add_argument("--pool-size", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    strict.log("Initializing Earth Engine for validation extraction...")
    ee.Initialize(project=PROJECT)
    strict.ensure_unsampleable_table()

    df = load_batch(args.batch_table)
    if args.resume:
        done = load_completed_contexts(args.out_table)
        if done:
            mask = df.apply(
                lambda r: strict.to_key(float(r.lat4dp), float(r.lon4dp), int(r.observation_year), int(r.emb_year)) not in done,
                axis=1,
            )
            df = df.loc[mask].reset_index(drop=True)
            strict.log(f"Resume enabled: filtered to {len(df):,} remaining contexts after excluding completed rows")
    strict.log(f"Loaded validation batch contexts: {len(df):,}")
    batches = strict.build_batches(df, args.batch_size)
    strict.log(f"Prepared validation extraction: {len(df):,} contexts into {len(batches):,} batches")
    strict.run_pool(batches, args.out_table, mode="validation", pool_size=args.pool_size)


if __name__ == "__main__":
    main()
