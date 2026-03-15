"""
Compute normalization stats for SINR V4.1 preview strict-core table.

Reads directly from BigQuery — no local parquet download needed.
Handles NULL → 0.0 to match train_on_vm.py's nan_to_num behavior.
Excludes GEDI and external/manual families (they're not in the preview table).

Output: normalize_stats_v41_preview.npz, normalize_temporal_v41_preview.npz
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from google.cloud import bigquery

PROJECT = "treekipedia-479918"
DATASET = "species_data"
PREVIEW_TABLE = f"{PROJECT}.{DATASET}.sinr_v41_preview_strict_core_v1"

# ── V4.1 preview continuous columns ─────────────────────────────────────────
# Must match what train_on_vm.py will use. GEDI and external/manual excluded.
AE_EMB_COLS = [f"emb_{i:02d}" for i in range(64)]

V41_ENV_CONTINUOUS_COLS = [
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    "treecover2000", "lossyear",
    # GEDI excluded: gedi_canopy_height_m, gedi_foliage_height_div
    "biomass_agb_mgha",
    "water_occurrence", "water_recurrence", "water_seasonality",
    "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world", "sbtn_natural_land",
    "neumann_natural_prob",
    "tc_vpd_mean", "tc_vpd_delta", "tc_aet_mean", "tc_soil_moisture_mean",
    "tc_pdsi_mean", "tc_water_deficit_mean", "tc_solar_rad_mean",
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "modis_gpp_mean",
]

AE_TEMPORAL_COLS = [f"ae_{y}_{b:02d}" for y in range(2017, 2025) for b in range(64)]

CONT_COLS = AE_EMB_COLS + V41_ENV_CONTINUOUS_COLS


def compute_stats_from_bq(client, table: str, columns: list[str], batch_size: int = 50):
    """Compute mean and std for each column directly in BQ.

    Uses IFNULL(col, 0.0) to match train_on_vm.py nan_to_num behavior.
    Processes columns in batches to stay under BQ query limits.
    """
    means = np.zeros(len(columns), dtype=np.float64)
    stds = np.zeros(len(columns), dtype=np.float64)
    row_count = 0

    for batch_start in range(0, len(columns), batch_size):
        batch_cols = columns[batch_start:batch_start + batch_size]
        select_parts = []
        for col in batch_cols:
            select_parts.append(
                f"AVG(IFNULL(CAST({col} AS FLOAT64), 0.0)) AS mean_{col}"
            )
            select_parts.append(
                f"STDDEV_POP(IFNULL(CAST({col} AS FLOAT64), 0.0)) AS std_{col}"
            )
        if batch_start == 0:
            select_parts.append("COUNT(*) AS n")

        sep = ",\n  "
        sql = f"SELECT\n  {sep.join(select_parts)}\nFROM `{table}`"

        rows = list(client.query(sql).result())
        row = rows[0]

        if batch_start == 0:
            row_count = row.n

        for i, col in enumerate(batch_cols):
            idx = batch_start + i
            means[idx] = getattr(row, f"mean_{col}") or 0.0
            stds[idx] = getattr(row, f"std_{col}") or 1.0

    # Clamp near-zero std to 1.0 (same as train_on_vm.py)
    stds[stds < 1e-8] = 1.0

    return means.astype(np.float32), stds.astype(np.float32), row_count


def main():
    parser = argparse.ArgumentParser(description="Compute V4.1 preview normalization stats")
    parser.add_argument("--out-dir", default="orchestrator/contracts/sinr_v3")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cont_path = out_dir / "normalize_stats_v41_preview.npz"
    temp_path = out_dir / "normalize_temporal_v41_preview.npz"
    manifest_path = out_dir / "stats_contract_v41_preview.json"

    if args.dry_run:
        print(f"=== DRY RUN ===")
        print(f"Source: {PREVIEW_TABLE}")
        print(f"Continuous columns: {len(CONT_COLS)} ({len(AE_EMB_COLS)} AE + {len(V41_ENV_CONTINUOUS_COLS)} env)")
        print(f"Temporal columns: {len(AE_TEMPORAL_COLS)}")
        print(f"Output: {cont_path}, {temp_path}")
        print(f"\nEnv cols ({len(V41_ENV_CONTINUOUS_COLS)}):")
        for c in V41_ENV_CONTINUOUS_COLS:
            print(f"  {c}")
        return

    client = bigquery.Client(project=PROJECT)

    print(f"Computing V4.1 preview normalization stats from BQ...")
    print(f"  Source: {PREVIEW_TABLE}")
    print(f"  Continuous: {len(CONT_COLS)} columns")
    print(f"  Temporal: {len(AE_TEMPORAL_COLS)} columns")

    # Continuous stats
    print("\nComputing continuous stats...")
    cont_mean, cont_std, n_rows = compute_stats_from_bq(client, PREVIEW_TABLE, CONT_COLS)
    print(f"  Rows: {n_rows:,}")

    # Temporal stats
    print("Computing temporal stats...")
    temp_mean, temp_std, _ = compute_stats_from_bq(client, PREVIEW_TABLE, AE_TEMPORAL_COLS)

    # Save
    np.savez(cont_path, mean=cont_mean, std=cont_std, columns=np.array(CONT_COLS))
    np.savez(temp_path, mean=temp_mean, std=temp_std, columns=np.array(AE_TEMPORAL_COLS))

    manifest = {
        "contract_name": "sinr_v41_preview_normalization",
        "version": "v41_preview",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_table": PREVIEW_TABLE,
        "total_rows": int(n_rows),
        "continuous_cols": len(CONT_COLS),
        "ae_emb_cols": len(AE_EMB_COLS),
        "env_continuous_cols": len(V41_ENV_CONTINUOUS_COLS),
        "temporal_cols": len(AE_TEMPORAL_COLS),
        "continuous_stats": cont_path.name,
        "temporal_stats": temp_path.name,
        "excluded_families": [
            "gedi_canopy_height_m", "gedi_foliage_height_div",
            "carbon_canopy_height_m", "spawn_agb", "spawn_agb_unc",
            "spawn_bgb", "spawn_bgb_unc", "gedi_l4b_agbd", "gedi_l4b_agbd_se",
            "gedi_rh98", "gedi_fhd", "soc_0cm", "soc_30cm", "soc_100cm", "soc_200cm",
            "aridity_index", "et0_mm_yr", "hilda_lulc_at_obs", "hilda_lulc_at_ae",
            "npp_at_obs", "gpp_at_obs", "lai_at_obs", "fpar_at_obs", "evi_at_obs",
            "cci_agb_at_obs", "cci_agb_sd_at_obs", "npp_at_ae", "gpp_at_ae",
            "lai_at_ae", "fpar_at_ae", "evi_at_ae", "cci_agb_at_ae", "cci_agb_sd_at_ae",
            "npp_mean_longterm", "npp_trend",
        ],
        "guards_applied": {
            "modis_gpp_mean": "65530+ nulled in source table",
            "nighttime_lights": "pre-2012 nulled in source table",
            "bio_soil_filter": "bio01=0 AND bio02=0 AND bio12=0 rows excluded; soil_ph=0 rows excluded",
        },
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nWrote {cont_path}")
    print(f"Wrote {temp_path}")
    print(f"Wrote {manifest_path}")

    # Quick sanity check: print a few env col stats
    env_start = len(AE_EMB_COLS)
    print(f"\n=== Sample env stats (first 10) ===")
    for i, col in enumerate(V41_ENV_CONTINUOUS_COLS[:10]):
        idx = env_start + i
        print(f"  {col:30s}  mean={cont_mean[idx]:12.4f}  std={cont_std[idx]:12.4f}")


if __name__ == "__main__":
    main()
