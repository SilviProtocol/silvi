#!/usr/bin/env python3
"""Build a clean Xiao lookup and repaired strict new_gbif table."""

from __future__ import annotations

import argparse
import pickle
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import ee
import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

STRICT_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full"
EXISTING_XIAO_TABLE = f"{PROJECT}.{DATASET}.xiao_backfill_results"
PREVIEW_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"

MISSING_COORDS_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_missing_strict_coords_v1"
MISSING_RESULTS_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_missing_strict_results_v1"
LOOKUP_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_clean_lookup_v1"
FIXED_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full_xiao_fixed_v1"
SUMMARY_TABLE = f"{PROJECT}.{DATASET}.sinr_xiao_strict_fixed_summary_v1"

XIAO_ASSET = "projects/sat-io/open-datasets/GLOBAL-NATURAL-PLANTED-FORESTS"

CACHE_DIR = Path("orchestrator/.xiao_strict_repair_cache")
RESULTS_CACHE = CACHE_DIR / "missing_results.pkl"
LOG_FILE = CACHE_DIR / "repair.log"


def log(message: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}Z] {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def build_xiao_image() -> ee.Image:
    xiao_raw = ee.ImageCollection(XIAO_ASSET).mosaic()
    b1 = xiao_raw.select("b1")
    b2 = xiao_raw.select("b2")
    b3 = xiao_raw.select("b3")

    is_natural = b1.eq(0).And(b2.eq(127)).And(b3.eq(0))
    is_planted = b1.eq(127).And(b2.eq(127)).And(b3.eq(0))

    return (
        ee.Image(0)
        .where(is_natural, 1)
        .where(is_planted, 2)
        .rename("xiao_planted_forest")
        .toInt()
    )


def create_missing_coords_table(client: bigquery.Client) -> int:
    sql = f"""
    CREATE OR REPLACE TABLE `{MISSING_COORDS_TABLE}` AS
    WITH strict_coords AS (
      SELECT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude
      FROM `{STRICT_TABLE}`
      GROUP BY 1, 2
    ),
    existing_xiao AS (
      SELECT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude
      FROM `{EXISTING_XIAO_TABLE}`
      GROUP BY 1, 2
    )
    SELECT
      s.latitude,
      s.longitude,
      ABS(s.latitude) > 59 AS sample_singleton
    FROM strict_coords s
    LEFT JOIN existing_xiao x
      USING (latitude, longitude)
    WHERE x.latitude IS NULL
    ORDER BY latitude, longitude
    """
    client.query(sql).result()
    table = client.get_table(MISSING_COORDS_TABLE)
    log(f"Prepared missing strict Xiao coords: {table.num_rows:,}")
    return int(table.num_rows)


def load_missing_coords(client: bigquery.Client) -> list[dict]:
    sql = f"""
    SELECT latitude, longitude, sample_singleton
    FROM `{MISSING_COORDS_TABLE}`
    ORDER BY sample_singleton DESC, latitude, longitude
    """
    df = client.query(sql).to_dataframe()
    return [
        {
            "lat": float(row.latitude),
            "lon": float(row.longitude),
            "sample_singleton": bool(row.sample_singleton),
        }
        for row in df.itertuples()
    ]


def load_results_from_bq(client: bigquery.Client) -> dict[str, int]:
    try:
        client.get_table(MISSING_RESULTS_TABLE)
    except NotFound:
        return {}

    sql = f"SELECT latitude, longitude, xiao_planted_forest FROM `{MISSING_RESULTS_TABLE}`"
    df = client.query(sql).to_dataframe()
    return {
        key_for(float(row.latitude), float(row.longitude)): int(row.xiao_planted_forest)
        for row in df.itertuples()
    }


def key_for(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def load_cached_results() -> dict[str, int]:
    if not RESULTS_CACHE.exists():
        return {}
    with open(RESULTS_CACHE, "rb") as handle:
        return pickle.load(handle)


def save_cached_results(results: dict[str, int]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_CACHE, "wb") as handle:
        pickle.dump(results, handle)


def sample_point(lat: float, lon: float, xiao_img: ee.Image) -> int | None:
    feature = ee.Feature(ee.Geometry.Point([lon, lat]), {"latitude": lat, "longitude": lon})
    result = xiao_img.sampleRegions(collection=ee.FeatureCollection([feature]), scale=30, geometries=False).getInfo()
    features = result.get("features", [])
    if not features:
        return None
    props = features[0].get("properties", {})
    value = props.get("xiao_planted_forest")
    return None if value is None else int(value)


def sample_point_with_retry(lat: float, lon: float, xiao_img: ee.Image, max_retries: int) -> int | None:
    for attempt in range(max_retries):
        try:
            return sample_point(lat, lon, xiao_img)
        except Exception:
            if attempt == max_retries - 1:
                return None
            time.sleep((2 ** attempt) + random.random())
    return None


def upload_results_to_bq(client: bigquery.Client, results: dict[str, int]) -> None:
    rows = []
    for key, value in sorted(results.items()):
        lat_s, lon_s = key.split(",")
        rows.append(
            {
                "latitude": float(lat_s),
                "longitude": float(lon_s),
                "xiao_planted_forest": int(value),
            }
        )

    df = pd.DataFrame(rows)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("latitude", "FLOAT64"),
            bigquery.SchemaField("longitude", "FLOAT64"),
            bigquery.SchemaField("xiao_planted_forest", "INT64"),
        ],
    )
    client.load_table_from_dataframe(df, MISSING_RESULTS_TABLE, job_config=job_config).result()
    log(f"Uploaded strict-missing Xiao results: {len(df):,}")


def run_sampling(client: bigquery.Client, threads: int, max_retries: int) -> None:
    coords = load_missing_coords(client)
    if not coords:
        log("No missing strict Xiao coords found")
        upload_results_to_bq(client, {})
        return

    results = load_results_from_bq(client)
    cached = load_cached_results()
    results.update(cached)

    remaining = [coord for coord in coords if key_for(coord["lat"], coord["lon"]) not in results]
    log(f"Missing strict coords total: {len(coords):,}")
    log(f"Already sampled from cache/BQ: {len(results):,}")
    log(f"Remaining to sample from GEE: {len(remaining):,}")
    if not remaining:
        upload_results_to_bq(client, results)
        return

    ee.Initialize(project=PROJECT)
    xiao_img = build_xiao_image()
    start = time.time()
    completed = 0
    failed = 0
    last_save = 0.0

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(
                sample_point_with_retry,
                coord["lat"],
                coord["lon"],
                xiao_img,
                max_retries,
            ): coord
            for coord in remaining
        }

        for future in as_completed(futures):
            coord = futures[future]
            key = key_for(coord["lat"], coord["lon"])
            value = future.result()
            if value is None:
                failed += 1
            else:
                results[key] = value
                completed += 1

            done = completed + failed
            now = time.time()
            if done % 100 == 0 or done == len(remaining) or now - last_save >= 60:
                elapsed = max(now - start, 1.0)
                rate = done / elapsed
                eta = (len(remaining) - done) / rate / 60 if rate else float("inf")
                log(
                    f"Sampling progress: {done:,}/{len(remaining):,} done, "
                    f"{completed:,} ok, {failed:,} failed, {rate:.1f} pts/sec, ETA {eta:.1f}m"
                )
                save_cached_results(results)
                last_save = now

    save_cached_results(results)
    upload_results_to_bq(client, results)
    if failed:
        raise RuntimeError(f"Failed to sample {failed} strict Xiao coords")


def build_lookup_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{LOOKUP_TABLE}` AS
    WITH unioned AS (
      SELECT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude,
        CAST(xiao_planted_forest AS INT64) AS xiao_planted_forest,
        'xiao_backfill_results' AS xiao_lookup_source
      FROM `{EXISTING_XIAO_TABLE}`

      UNION ALL

      SELECT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude,
        CAST(xiao_planted_forest AS INT64) AS xiao_planted_forest,
        'strict_missing_coords_repair_v1' AS xiao_lookup_source
      FROM `{MISSING_RESULTS_TABLE}`
    )
    SELECT
      latitude,
      longitude,
      ANY_VALUE(xiao_planted_forest) AS xiao_planted_forest,
      ARRAY_AGG(DISTINCT xiao_lookup_source ORDER BY xiao_lookup_source) AS xiao_lookup_sources,
      COUNT(*) AS source_row_count,
      COUNT(DISTINCT xiao_planted_forest) AS distinct_xiao_count
    FROM unioned
    GROUP BY 1, 2
    """
    client.query(sql).result()

    validation_sql = f"SELECT COUNT(*) AS conflict_count FROM `{LOOKUP_TABLE}` WHERE distinct_xiao_count > 1"
    conflict_count = int(next(client.query(validation_sql).result()).conflict_count)
    if conflict_count:
        raise RuntimeError(f"Xiao lookup has {conflict_count} conflicting coordinates")
    log("Built clean Xiao lookup table")


def build_fixed_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{FIXED_TABLE}` AS
    SELECT
      t.* EXCEPT(xiao_planted_forest),
      t.xiao_planted_forest AS xiao_planted_forest_raw,
      COALESCE(CAST(l.xiao_planted_forest AS FLOAT64), t.xiao_planted_forest) AS xiao_planted_forest,
      l.latitude IS NOT NULL AS xiao_has_clean_lookup,
      COALESCE(CAST(l.xiao_planted_forest AS FLOAT64), t.xiao_planted_forest) != t.xiao_planted_forest AS xiao_value_changed,
      CASE
        WHEN EXISTS (
          SELECT 1
          FROM UNNEST(IFNULL(l.xiao_lookup_sources, ARRAY<STRING>[])) AS src
          WHERE src = 'strict_missing_coords_repair_v1'
        ) THEN 'strict_missing_coords_repair_v1'
        WHEN l.latitude IS NOT NULL THEN 'xiao_backfill_results'
        ELSE 'strict_raw_original'
      END AS xiao_repair_source,
      l.xiao_lookup_sources,
      l.source_row_count AS xiao_lookup_source_row_count
    FROM `{STRICT_TABLE}` t
    LEFT JOIN `{LOOKUP_TABLE}` l
      ON ROUND(t.latitude, 4) = l.latitude
     AND ROUND(t.longitude, 4) = l.longitude
    """
    client.query(sql).result()
    log("Built repaired strict Xiao table")


def build_summary_table(client: bigquery.Client) -> None:
    sql = f"""
    CREATE OR REPLACE TABLE `{SUMMARY_TABLE}` AS
    WITH preview_ctx AS (
      SELECT DISTINCT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude,
        emb_year,
        CAST(xiao_planted_forest AS INT64) AS preview_xiao
      FROM `{PREVIEW_TABLE}`
    ),
    fixed_ctx AS (
      SELECT DISTINCT
        ROUND(latitude, 4) AS latitude,
        ROUND(longitude, 4) AS longitude,
        emb_year,
        CAST(xiao_planted_forest AS INT64) AS fixed_xiao
      FROM `{FIXED_TABLE}`
    )
    SELECT
      CASE
        WHEN fixed_xiao = preview_xiao THEN 'agree'
        WHEN fixed_xiao = 0 AND preview_xiao = 2 THEN 'strict0_preview2_bug'
        WHEN fixed_xiao = 0 AND preview_xiao = 1 THEN 'strict0_preview1'
        WHEN fixed_xiao = 1 AND preview_xiao = 0 THEN 'strict1_preview0'
        WHEN fixed_xiao = 2 AND preview_xiao = 0 THEN 'strict2_preview0'
        WHEN fixed_xiao = 1 AND preview_xiao = 2 THEN 'strict1_preview2'
        WHEN fixed_xiao = 2 AND preview_xiao = 1 THEN 'strict2_preview1'
        ELSE 'other'
      END AS mismatch_class,
      COUNT(*) AS row_count
    FROM fixed_ctx f
    JOIN preview_ctx p
      USING (latitude, longitude, emb_year)
    GROUP BY 1
    ORDER BY row_count DESC
    """
    client.query(sql).result()
    log("Built repaired Xiao summary table")


def verify(client: bigquery.Client) -> None:
    coverage_sql = f"""
    WITH strict_coords AS (
      SELECT ROUND(latitude, 4) AS latitude, ROUND(longitude, 4) AS longitude
      FROM `{STRICT_TABLE}`
      GROUP BY 1, 2
    )
    SELECT COUNT(*) AS missing_lookup_coords
    FROM strict_coords s
    LEFT JOIN `{LOOKUP_TABLE}` l
      USING (latitude, longitude)
    WHERE l.latitude IS NULL
    """
    missing_lookup_coords = int(next(client.query(coverage_sql).result()).missing_lookup_coords)
    if missing_lookup_coords:
        raise RuntimeError(f"Strict Xiao lookup still misses {missing_lookup_coords} coords")

    changed_sql = f"""
    SELECT
      xiao_planted_forest_raw AS old_xiao,
      xiao_planted_forest AS new_xiao,
      COUNT(*) AS row_count
    FROM `{FIXED_TABLE}`
    WHERE xiao_value_changed
    GROUP BY 1, 2
    ORDER BY row_count DESC
    """
    changed_rows = list(client.query(changed_sql).result())
    total_changed = sum(int(row.row_count) for row in changed_rows)
    log(f"Changed strict Xiao rows: {total_changed:,}")
    for row in changed_rows[:10]:
        log(f"  {row.old_xiao} -> {row.new_xiao}: {int(row.row_count):,}")

    summary_rows = list(client.query(f"SELECT mismatch_class, row_count FROM `{SUMMARY_TABLE}` ORDER BY row_count DESC").result())
    for row in summary_rows:
        log(f"  Preview overlap {row.mismatch_class}: {int(row.row_count):,}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["prepare", "sample", "build", "all"], default="all")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-retries", type=int, default=4)
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)

    if args.phase in {"prepare", "all", "sample"}:
        create_missing_coords_table(client)

    if args.phase in {"sample", "all"}:
        run_sampling(client, threads=args.threads, max_retries=args.max_retries)

    if args.phase in {"build", "all"}:
        build_lookup_table(client)
        build_fixed_table(client)
        build_summary_table(client)
        verify(client)


if __name__ == "__main__":
    main()
