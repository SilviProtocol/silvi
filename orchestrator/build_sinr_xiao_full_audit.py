#!/usr/bin/env python3
"""Full-scope Xiao inconsistency audit between strict raw and preview-clean tables.

Creates BQ tables quantifying:
1. Per-context Xiao value comparison (strict raw vs preview-clean)
2. Geographic and temporal clustering of mismatches
3. Summary statistics

Background:
- The Xiao RGB decode was fixed 2026-03-08 in unified_gee_sampler_v3.py
- Strict extraction used --resume-from-bq, so pre-fix rows retained buggy xiao=0
- Preview-clean received correct values via Xiao backfill
- Fresh validation confirmed: preview + fresh agree, strict raw disagrees on xiao=2
"""

from __future__ import annotations

import argparse
from datetime import datetime

from google.cloud import bigquery


PROJECT = "treekipedia-479918"
DATASET = "species_data"
STRICT_RAW = f"{PROJECT}.{DATASET}.sinr_v3_features_new_gbif_strict_full"
PREVIEW = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    args = p.parse_args()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    audit_table = f"{PROJECT}.{DATASET}.sinr_xiao_strict_vs_preview_audit_v1"
    summary_table = f"{PROJECT}.{DATASET}.sinr_xiao_audit_summary_v1"
    geo_table = f"{PROJECT}.{DATASET}.sinr_xiao_audit_geo_profile_v1"

    client = bigquery.Client(project=PROJECT)

    # ── Table 1: Per-context comparison ──
    audit_sql = f"""
    CREATE OR REPLACE TABLE `{audit_table}` AS
    WITH strict_ctx AS (
      SELECT
        ROUND(latitude, 4) as lat4,
        ROUND(longitude, 4) as lon4,
        latitude,
        longitude,
        emb_year,
        observation_year,
        xiao_planted_forest as strict_xiao
      FROM `{STRICT_RAW}`
    ),
    preview_ctx AS (
      SELECT DISTINCT
        ROUND(latitude, 4) as lat4,
        ROUND(longitude, 4) as lon4,
        emb_year,
        xiao_planted_forest as preview_xiao
      FROM `{PREVIEW}`
    )
    SELECT
      s.lat4,
      s.lon4,
      s.latitude,
      s.longitude,
      s.emb_year,
      s.observation_year,
      s.strict_xiao,
      p.preview_xiao,
      CASE
        WHEN s.strict_xiao = p.preview_xiao THEN 'agree'
        WHEN s.strict_xiao = 0 AND p.preview_xiao = 2 THEN 'strict0_preview2_bug'
        WHEN s.strict_xiao = 0 AND p.preview_xiao = 1 THEN 'strict0_preview1'
        WHEN s.strict_xiao = 1 AND p.preview_xiao = 0 THEN 'strict1_preview0'
        WHEN s.strict_xiao = 2 AND p.preview_xiao = 0 THEN 'strict2_preview0'
        WHEN s.strict_xiao = 1 AND p.preview_xiao = 2 THEN 'strict1_preview2'
        WHEN s.strict_xiao = 2 AND p.preview_xiao = 1 THEN 'strict2_preview1'
        ELSE 'other'
      END as mismatch_class,
      CASE
        WHEN s.strict_xiao = 0 AND p.preview_xiao = 2 THEN TRUE
        ELSE FALSE
      END as is_rgb_bug_pattern,
      -- Corrected value: trust preview (backfilled with correct RGB decode)
      p.preview_xiao as corrected_xiao
    FROM strict_ctx s
    JOIN preview_ctx p USING (lat4, lon4, emb_year)
    """

    # ── Table 2: Summary ──
    summary_sql = f"""
    CREATE OR REPLACE TABLE `{summary_table}` AS
    SELECT
      mismatch_class,
      is_rgb_bug_pattern,
      COUNT(*) as row_count,
      ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 2) as pct_of_total,
      MIN(emb_year) as min_year,
      MAX(emb_year) as max_year
    FROM `{audit_table}`
    GROUP BY 1, 2
    ORDER BY row_count DESC
    """

    # ── Table 3: Geographic profile ──
    geo_sql = f"""
    CREATE OR REPLACE TABLE `{geo_table}` AS
    SELECT
      CASE
        WHEN latitude BETWEEN -60 AND -30 THEN 'S30-60'
        WHEN latitude BETWEEN -30 AND -10 THEN 'S10-30'
        WHEN latitude BETWEEN -10 AND 10 THEN 'Equatorial'
        WHEN latitude BETWEEN 10 AND 30 THEN 'N10-30'
        WHEN latitude BETWEEN 30 AND 50 THEN 'N30-50'
        WHEN latitude > 50 THEN 'N50+'
        ELSE 'Other'
      END as lat_band,
      emb_year,
      COUNT(*) as total_contexts,
      COUNTIF(mismatch_class != 'agree') as total_mismatches,
      COUNTIF(is_rgb_bug_pattern) as rgb_bug_count,
      ROUND(COUNTIF(is_rgb_bug_pattern) / COUNT(*) * 100, 2) as rgb_bug_pct,
      COUNTIF(mismatch_class = 'strict0_preview1') as strict0_prev1,
      COUNTIF(mismatch_class = 'strict1_preview0') as strict1_prev0
    FROM `{audit_table}`
    GROUP BY 1, 2
    ORDER BY 1, 2
    """

    queries = [
        ("audit", audit_table, audit_sql),
        ("summary", summary_table, summary_sql),
        ("geo_profile", geo_table, geo_sql),
    ]

    for name, table, sql in queries:
        print(f"\n{'='*60}")
        print(f"Creating {name}: {table}")
        print(f"{'='*60}")

        if args.dry_run:
            print(sql)
            continue

        job = client.query(sql)
        job.result()
        result_table = client.get_table(table)
        print(f"  -> {result_table.num_rows:,} rows")

    if not args.dry_run:
        # Print summary
        print(f"\n{'='*60}")
        print("AUDIT SUMMARY")
        print(f"{'='*60}")
        rows = list(client.query(f"SELECT * FROM `{summary_table}` ORDER BY row_count DESC").result())
        for r in rows:
            print(f"  {r.mismatch_class:30s}  {r.row_count:>10,}  ({r.pct_of_total}%)")

        total = sum(r.row_count for r in rows)
        bug_rows = sum(r.row_count for r in rows if r.is_rgb_bug_pattern)
        other_mismatches = sum(r.row_count for r in rows if r.mismatch_class != 'agree' and not r.is_rgb_bug_pattern)
        print(f"\n  Total overlap:     {total:>10,}")
        print(f"  RGB bug (s0→p2):   {bug_rows:>10,}  ({bug_rows/total*100:.1f}%)")
        print(f"  Other mismatches:  {other_mismatches:>10,}  ({other_mismatches/total*100:.1f}%)")
        print(f"  Agreement:         {total-bug_rows-other_mismatches:>10,}  ({(total-bug_rows-other_mismatches)/total*100:.1f}%)")


if __name__ == "__main__":
    main()
