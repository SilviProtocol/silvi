#!/usr/bin/env python3
"""Preflight checks for SINR v3.0 strict preview training table."""

from google.cloud import bigquery

PROJECT = "treekipedia-479918"
DATASET = "species_data"
TABLE = "sinr_v3_unified_strict_train_v30_preview_clean"


def q(client: bigquery.Client, sql: str):
    return list(client.query(sql).result())


def main() -> int:
    client = bigquery.Client(project=PROJECT)
    table_ref = f"`{PROJECT}.{DATASET}.{TABLE}`"

    checks = []

    rows = q(client, f"SELECT COUNT(*) AS c FROM {table_ref}")[0]["c"]
    checks.append(("row_count_gt_0", rows > 0, f"rows={rows:,}"))

    dup = q(
        client,
        f"""
        SELECT COUNT(*) AS dup_rows
        FROM (
          SELECT data_source, taxon_id, ROUND(latitude,4) lat4, ROUND(longitude,4) lon4,
                 observation_year, emb_year, COUNT(*) c
          FROM {table_ref}
          GROUP BY data_source, taxon_id, lat4, lon4, observation_year, emb_year
          HAVING c > 1
        )
        """,
    )[0]["dup_rows"]
    checks.append(("canonical_duplicates_zero", dup == 0, f"dup_rows={dup:,}"))

    null_years = q(
        client,
        f"SELECT COUNTIF(observation_year IS NULL OR emb_year IS NULL) AS n FROM {table_ref}",
    )[0]["n"]
    checks.append(("temporal_nulls_zero", null_years == 0, f"null_temporal={null_years:,}"))

    verify = q(
        client,
        f"SELECT COUNTIF(verification_status != 'HIT') AS n FROM {table_ref}",
    )[0]["n"]
    checks.append(("verification_all_hit", verify == 0, f"non_hit_rows={verify:,}"))

    null_intro = q(client, f"SELECT COUNTIF(is_introduced IS NULL) AS n FROM {table_ref}")[0]["n"]
    checks.append(("is_introduced_no_null", null_intro == 0, f"null_is_introduced={null_intro:,}"))

    null_ls = q(
        client,
        f"SELECT COUNTIF(land_state_class IS NULL) AS n FROM {table_ref}",
    )[0]["n"]
    checks.append(("land_state_no_null", null_ls == 0, f"null_land_state={null_ls:,}"))

    # Sentinel quality checks for carbon features in clean table
    sent = q(
        client,
        f"""
        SELECT
          COUNTIF(spawn_agb=-9999) AS s1,
          COUNTIF(gedi_l4b_agbd=-9999) AS s2,
          COUNTIF(cci_agb_at_obs=-9999) AS s3,
          COUNTIF(soc_0cm=-9999) AS s4
        FROM {table_ref}
        """,
    )[0]
    sent_total = int(sent["s1"]) + int(sent["s2"]) + int(sent["s3"]) + int(sent["s4"])
    checks.append(("carbon_sentinel_removed", sent_total == 0, f"sentinel_sum={sent_total:,}"))

    failed = [c for c in checks if not c[1]]

    print(f"Preflight table: {PROJECT}.{DATASET}.{TABLE}")
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"- {name}: {status} ({detail})")

    if failed:
        print(f"\nResult: FAIL ({len(failed)} checks failed)")
        return 1

    print("\nResult: PASS (ready for v3.0 strict preview run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
