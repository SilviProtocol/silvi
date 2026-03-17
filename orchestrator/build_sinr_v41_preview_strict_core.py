"""
Build the SINR V4.1 preview strict-core feature-grain table.

Sources from the canonical repaired new_gbif strict lineage:
  sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1

Applies:
  - Explicit inclusion of only trusted strict-core feature families
  - GPP high-code masking (65530-65535 → NULL)
  - Bio/soil zero-contamination row filter
  - GEDI exclusion (semantics unresolved)
  - External/manual family exclusion (carbon extras, HILDA, aridity, etc.)

Output: sinr_v41_preview_strict_core_{timestamp}

Important: this table is feature-grain (one row per context), not training-grain.
It is suitable for feature auditing / preview feature design, but trainer-ready
rows with `taxon_id` live in `sinr_v41_preview_strict_core_train_v1`.

This is a V4.1 preview — not final. Designed to train while backfill continues toward V4.2.
"""

import argparse
import datetime
import sys

from google.cloud import bigquery

PROJECT = "treekipedia-479918"
DATASET = "species_data"

# Canonical repaired source
SOURCE_TABLE = (
    f"{PROJECT}.{DATASET}."
    "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1"
)

# ── Feature families: INCLUDE ───────────────────────────────────────────────

# Labels / metadata / coordinates
META_COLS = [
    "latitude", "longitude", "observation_year", "emb_year",
]

# AE embeddings (64D static)
AE_EMB_COLS = [f"emb_{i:02d}" for i in range(64)]

# AE temporal (8 years × 64D = 512D)
AE_TEMPORAL_COLS = [f"ae_{y}_{b:02d}" for y in range(2017, 2025) for b in range(64)]

# Terrain + hydro
TERRAIN_COLS = [
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
]

# WorldClim bioclimatic
BIO_COLS = [f"bio{i:02d}" for i in range(1, 20)]

# Soil
SOIL_COLS = [
    "soil_ph", "soil_clay_pct", "soil_sand_pct",
    "soil_organic_carbon", "soil_bulk_density", "soil_water_content",
]

# Hansen
HANSEN_COLS = ["treecover2000", "lossyear", "hansen_gain"]

# JRC water + forest
JRC_COLS = [
    "water_occurrence", "water_recurrence", "water_seasonality",
    "jrc_tmf_status", "jrc_tmf_degrad_year", "jrc_forest_type",
]

# Biomass
BIOMASS_COLS = ["biomass_agb_mgha"]

# Human modification
HM_COLS = ["human_modification"]

# SBTN
SBTN_COLS = ["sbtn_natural_land"]

# Land cover
LC_COLS = [
    "esa_worldcover_2021", "dynamic_world",
    "modis_lc_at_ae", "modis_lc_at_obs",
]

# Xiao + Neumann (plantation/forest type)
FOREST_TYPE_COLS = ["xiao_planted_forest", "neumann_natural_prob"]

# TerraClimate
TC_COLS = [
    "tc_aet_mean", "tc_pdsi_mean", "tc_soil_moisture_mean",
    "tc_solar_rad_mean", "tc_vpd_delta", "tc_vpd_mean",
    "tc_water_deficit_mean",
]

# Fire
FIRE_COLS = ["fire_frequency_count"]

# Categorical (eco/biome)
CAT_COLS = ["eco_id", "biome_num", "soil_texture_class"]

# ── GPP: include with guard ─────────────────────────────────────────────────
# 65530-65535 are land-cover fill codes, not valid GPP. Replace with NULL.
GPP_EXPR = """
    CASE
        WHEN modis_gpp_mean >= 65530 THEN NULL
        WHEN modis_gpp_mean IS NULL THEN NULL
        ELSE modis_gpp_mean
    END AS modis_gpp_mean
"""

# Nighttime lights: pre-2012 is suspect, but keep with NULL guard
NIGHTTIME_EXPR = """
    CASE
        WHEN observation_year < 2012 THEN NULL
        ELSE nighttime_lights
    END AS nighttime_lights
"""

# ── Feature families: EXCLUDE ───────────────────────────────────────────────
# GEDI (semantics unresolved — .mosaic() bug, band confusion)
# gedi_canopy_height_m, gedi_foliage_height_div

# External/manual/preview-backed families:
# carbon_canopy_height_m, spawn_*, gedi_l4b_*, soc_*
# HILDA, aridity, ET0, IPCC
# land_state_class, is_introduced (preview-backed, heuristic)

# ── Row filters ─────────────────────────────────────────────────────────────
ROW_FILTERS = """
    -- Exclude unmask(0) full-contamination rows (all bio = 0)
    NOT (bio01 = 0 AND bio02 = 0 AND bio12 = 0)
    -- Exclude impossible soil pH = 0 (real pH is 3-10; 0 = unmask artifact)
    AND (soil_ph IS NULL OR soil_ph != 0)
"""


def build_column_list():
    """Build the SELECT column list for the preview table."""
    cols = []
    for group in [META_COLS, AE_EMB_COLS, AE_TEMPORAL_COLS, TERRAIN_COLS,
                  BIO_COLS, SOIL_COLS, HANSEN_COLS, JRC_COLS, BIOMASS_COLS,
                  HM_COLS, SBTN_COLS, LC_COLS, FOREST_TYPE_COLS, TC_COLS,
                  FIRE_COLS, CAT_COLS]:
        cols.extend(group)
    return cols


def build_sql(dest_table: str, dry_run: bool = False) -> str:
    """Build the CREATE TABLE AS SELECT query."""
    plain_cols = build_column_list()
    select_parts = []
    for c in plain_cols:
        select_parts.append(f"    {c}")
    # Add guarded columns
    select_parts.append(f"    {GPP_EXPR.strip()}")
    select_parts.append(f"    {NIGHTTIME_EXPR.strip()}")

    select_clause = ",\n".join(select_parts)

    sql = f"""
CREATE TABLE `{dest_table}` AS
SELECT
{select_clause}
FROM `{SOURCE_TABLE}`
WHERE
    {ROW_FILTERS.strip()}
"""
    return sql.strip()


def main():
    parser = argparse.ArgumentParser(description="Build SINR V4.1 preview strict-core table")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    parser.add_argument("--dest-suffix", default=None,
                        help="Custom suffix (default: timestamp)")
    args = parser.parse_args()

    ts = args.dest_suffix or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_table = f"{PROJECT}.{DATASET}.sinr_v41_preview_strict_core_{ts}"

    sql = build_sql(dest_table)

    if args.dry_run:
        print("=== DRY RUN — SQL to execute ===")
        print(sql)
        print(f"\n=== Destination: {dest_table} ===")
        print(f"=== Source: {SOURCE_TABLE} ===")
        print(f"=== Included columns: {len(build_column_list()) + 2} ===")  # +2 for GPP/nighttime
        print(f"=== Excluded: gedi_canopy_height_m, gedi_foliage_height_div, "
              "external/manual families ===")
        return

    client = bigquery.Client(project=PROJECT)

    print(f"Building V4.1 preview strict-core table...")
    print(f"  Source: {SOURCE_TABLE}")
    print(f"  Dest:   {dest_table}")
    print(f"  Columns: {len(build_column_list()) + 2}")
    print(f"  Excluded: GEDI, external/manual families")
    print(f"  Guards: GPP >= 65530 → NULL, nighttime_lights pre-2012 → NULL")
    print(f"  Filters: bio zero-contamination, soil_ph = 0")
    print()

    job = client.query(sql)
    result = job.result()

    # Verify
    verify_sql = f"SELECT COUNT(*) AS n FROM `{dest_table}`"
    rows = list(client.query(verify_sql).result())
    count = rows[0].n

    source_count_sql = f"SELECT COUNT(*) AS n FROM `{SOURCE_TABLE}`"
    source_rows = list(client.query(source_count_sql).result())
    source_count = source_rows[0].n

    excluded = source_count - count
    print(f"\n=== V4.1 Preview Strict-Core Table Built ===")
    print(f"  Source rows:   {source_count:,}")
    print(f"  Preview rows:  {count:,}")
    print(f"  Excluded rows: {excluded:,} ({100*excluded/source_count:.2f}%)")
    print(f"  Table: {dest_table}")


if __name__ == "__main__":
    main()
