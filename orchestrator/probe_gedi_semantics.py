#!/usr/bin/env python3
"""Probe GEDI semantics on suspicious and control coords.

This script does a small, read-only GEDI-only probe before any full repair run.

Workflow:
1. Pull a balanced sample of distinct coords from both `new_gbif` and `backfill`
   across suspicious current-value buckets.
2. Re-sample the official GEDI GRIDDEDVEG assets directly from Earth Engine
   without `unmask(0)`.
3. Save the raw probe rows plus a compact summary so we can decide whether a
   GEDI-only re-extract is justified.

The probe is intentionally coordinate-grain and non-destructive.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ee
import pandas as pd
from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"

NEW_GBIF_TABLE = (
    f"{PROJECT}.{DATASET}."
    "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)
BACKFILL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_features_backfill_strict_full"

RH98_ASSET = "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316"
FHD_ASSET = "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_fhd-pai-1m-a0_vf_20190417_20230316"

RH_BANDS = ["mean", "meanbase", "median", "sd", "iqr", "p95", "shan", "countf"]
FHD_BANDS = ["mean", "meanbase", "median", "sd", "iqr", "p95", "shan", "countf"]

BUCKETS = [
    "neg_lowlat",
    "gt213_lowlat",
    "hi_80_213_lowlat",
    "zero_lowlat",
    "zero_highlat",
    "normal_5_60_lowlat",
]


def build_probe_query(per_bucket: int) -> str:
    def branch_sql(label: str, table: str) -> str:
        return f"""
        SELECT
          '{label}' AS data_source,
          latitude,
          longitude,
          ABS(latitude) AS abs_lat,
          gedi_canopy_height_m AS current_gedi_canopy_height_m,
          gedi_foliage_height_div AS current_gedi_foliage_height_div,
          observation_year,
          emb_year
        FROM `{table}`
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY FORMAT('%.4f', ROUND(latitude, 4)), FORMAT('%.4f', ROUND(longitude, 4))
          ORDER BY observation_year DESC, emb_year DESC
        ) = 1
        """.strip()

    return f"""
    WITH base AS (
      {branch_sql('new_gbif', NEW_GBIF_TABLE)}
      UNION ALL
      {branch_sql('backfill', BACKFILL_TABLE)}
    ),
    bucketed AS (
      SELECT
        data_source,
        ROUND(latitude, 4) AS lat4,
        ROUND(longitude, 4) AS lon4,
        latitude,
        longitude,
        abs_lat,
        current_gedi_canopy_height_m,
        current_gedi_foliage_height_div,
        CASE
          WHEN current_gedi_canopy_height_m < 0 AND abs_lat <= 51.6 THEN 'neg_lowlat'
          WHEN current_gedi_canopy_height_m > 213 AND abs_lat <= 51.6 THEN 'gt213_lowlat'
          WHEN current_gedi_canopy_height_m BETWEEN 80 AND 213 AND abs_lat <= 51.6 THEN 'hi_80_213_lowlat'
          WHEN current_gedi_canopy_height_m = 0 AND abs_lat <= 51.6 THEN 'zero_lowlat'
          WHEN current_gedi_canopy_height_m = 0 AND abs_lat > 51.6 THEN 'zero_highlat'
          WHEN current_gedi_canopy_height_m BETWEEN 5 AND 60 AND abs_lat <= 51.6 THEN 'normal_5_60_lowlat'
          ELSE NULL
        END AS probe_bucket
      FROM base
    )
    SELECT
      data_source,
      probe_bucket,
      lat4,
      lon4,
      latitude,
      longitude,
      abs_lat,
      current_gedi_canopy_height_m,
      current_gedi_foliage_height_div
    FROM bucketed
    WHERE probe_bucket IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY data_source, probe_bucket
      ORDER BY RAND()
    ) <= {int(per_bucket)}
    ORDER BY data_source, probe_bucket, lat4, lon4
    """.strip()


def load_probe_manifest(client: bigquery.Client, per_bucket: int) -> pd.DataFrame:
    query = build_probe_query(per_bucket)
    df = client.query(query).to_dataframe()
    if df.empty:
        raise RuntimeError("Probe manifest query returned no rows")
    return df


def build_probe_image() -> ee.Image:
    anchor = ee.Image.constant(1).rename("probe_anchor").toFloat()
    rh_img = ee.Image(RH98_ASSET).select(RH_BANDS, [f"rh_{b}" for b in RH_BANDS]).toFloat()
    fhd_img = ee.Image(FHD_ASSET).select(FHD_BANDS, [f"fhd_{b}" for b in FHD_BANDS]).toFloat()
    return anchor.addBands(rh_img).addBands(fhd_img)


def make_feature_collection(df: pd.DataFrame) -> ee.FeatureCollection:
    features = []
    for idx, row in df.iterrows():
        geom = ee.Geometry.Point([float(row.longitude), float(row.latitude)])
        props = {
            "probe_row_id": int(idx),
            "data_source": str(row.data_source),
            "probe_bucket": str(row.probe_bucket),
            "lat4": float(row.lat4),
            "lon4": float(row.lon4),
            "current_gedi_canopy_height_m": float(row.current_gedi_canopy_height_m),
            "current_gedi_foliage_height_div": float(row.current_gedi_foliage_height_div),
        }
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


def sample_probe(df: pd.DataFrame) -> pd.DataFrame:
    image = build_probe_image()
    fc = make_feature_collection(df)
    sampled = image.reduceRegions(collection=fc, reducer=ee.Reducer.first(), scale=1000)
    result = sampled.getInfo()
    rows: list[dict[str, Any]] = []
    for feature in result.get("features", []):
        props = feature.get("properties", {})
        rows.append(props)
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("GEDI probe returned no sampled rows")
    return out


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["current_invalid_doc_range"] = (
        out["current_gedi_canopy_height_m"].lt(-213)
        | out["current_gedi_canopy_height_m"].gt(213)
    )
    out["current_invalid_practical"] = (
        out["current_gedi_canopy_height_m"].lt(0)
        | out["current_gedi_canopy_height_m"].gt(100)
    )
    out["probe_rh_missing"] = out["rh_p95"].isna()
    out["probe_rh_invalid_doc_range"] = out["rh_p95"].lt(-213) | out["rh_p95"].gt(213)
    out["probe_rh_invalid_practical"] = out["rh_p95"].lt(0) | out["rh_p95"].gt(100)
    out["probe_rh_sane_for_training"] = out["rh_p95"].between(0, 100, inclusive="both")
    out["probe_fhd_missing"] = out["fhd_mean"].isna()
    out["probe_fhd_mean_nonnegative"] = out["fhd_mean"].ge(0)
    out["probe_fhd_shan_nonnegative"] = out["fhd_shan"].ge(0)
    out["probe_rh_countf_ge10"] = out["rh_countf"].fillna(0).ge(10)
    out["probe_rh_countf_ge20"] = out["rh_countf"].fillna(0).ge(20)
    out["probe_recovered_from_bad_current"] = (
        out["current_invalid_practical"] & out["probe_rh_sane_for_training"]
    )
    return out


def summarize(df: pd.DataFrame, per_bucket: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_rows": int(len(df)),
        "per_bucket_requested": int(per_bucket),
        "rh98_asset": RH98_ASSET,
        "rh98_bands": RH_BANDS,
        "fhd_asset": FHD_ASSET,
        "fhd_bands": FHD_BANDS,
        "overall": {
            "current_invalid_practical": int(df["current_invalid_practical"].sum()),
            "probe_rh_missing": int(df["probe_rh_missing"].sum()),
            "probe_rh_invalid_practical": int(df["probe_rh_invalid_practical"].sum()),
            "probe_rh_invalid_doc_range": int(df["probe_rh_invalid_doc_range"].sum()),
            "probe_rh_sane_for_training": int(df["probe_rh_sane_for_training"].sum()),
            "probe_recovered_from_bad_current": int(df["probe_recovered_from_bad_current"].sum()),
            "probe_rh_countf_ge10": int(df["probe_rh_countf_ge10"].sum()),
            "probe_rh_countf_ge20": int(df["probe_rh_countf_ge20"].sum()),
        },
        "by_source_bucket": [],
    }

    grouped = df.groupby(["data_source", "probe_bucket"], dropna=False)
    for (data_source, bucket), grp in grouped:
        summary["by_source_bucket"].append(
            {
                "data_source": data_source,
                "probe_bucket": bucket,
                "rows": int(len(grp)),
                "current_canopy_min": None if grp["current_gedi_canopy_height_m"].isna().all() else float(grp["current_gedi_canopy_height_m"].min()),
                "current_canopy_max": None if grp["current_gedi_canopy_height_m"].isna().all() else float(grp["current_gedi_canopy_height_m"].max()),
                "probe_rh_p95_min": None if grp["rh_p95"].isna().all() else float(grp["rh_p95"].min()),
                "probe_rh_p95_max": None if grp["rh_p95"].isna().all() else float(grp["rh_p95"].max()),
                "probe_rh_missing": int(grp["probe_rh_missing"].sum()),
                "probe_rh_invalid_practical": int(grp["probe_rh_invalid_practical"].sum()),
                "probe_rh_sane_for_training": int(grp["probe_rh_sane_for_training"].sum()),
                "probe_recovered_from_bad_current": int(grp["probe_recovered_from_bad_current"].sum()),
                "probe_rh_countf_ge10": int(grp["probe_rh_countf_ge10"].sum()),
                "probe_rh_countf_ge20": int(grp["probe_rh_countf_ge20"].sum()),
            }
        )

    return summary


def write_outputs(df: pd.DataFrame, summary: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"gedi_probe_rows_{stamp}.csv"
    json_path = out_dir / f"gedi_probe_summary_{stamp}.json"
    df.sort_values(["data_source", "probe_bucket", "lat4", "lon4"]).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2))
    return csv_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe GEDI metrics on suspicious coords")
    parser.add_argument("--per-bucket", type=int, default=10)
    parser.add_argument("--out-dir", default="orchestrator/gedi_probe_outputs")
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)
    ee.Initialize(project=PROJECT)

    manifest = load_probe_manifest(client, args.per_bucket)
    print(f"Loaded probe manifest: {len(manifest):,} coords")
    print(manifest.groupby(["data_source", "probe_bucket"]).size().to_string())

    sampled = sample_probe(manifest)
    merged = sampled.copy()
    merged = add_derived_columns(merged)
    summary = summarize(merged, args.per_bucket)
    csv_path, json_path = write_outputs(merged, summary, Path(args.out_dir))

    print(f"\nWrote row output: {csv_path}")
    print(f"Wrote summary:    {json_path}")
    print("\nOverall summary:")
    print(json.dumps(summary["overall"], indent=2))
    print("\nBy source/bucket:")
    for row in summary["by_source_bucket"]:
        print(
            f"  [{row['data_source']}/{row['probe_bucket']}] rows={row['rows']} | "
            f"probe missing={row['probe_rh_missing']} | "
            f"probe sane={row['probe_rh_sane_for_training']} | "
            f"recovered={row['probe_recovered_from_bad_current']} | "
            f"countf>=10={row['probe_rh_countf_ge10']}"
        )


if __name__ == "__main__":
    main()
