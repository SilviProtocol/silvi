#!/usr/bin/env python3
"""
consolidate_bq_v2.py — Consolidate SINR v3 BQ tables into Master Training Data v2.

FIXES from v1:
  - Backfill taxon_id now comes from `occurrences` table (60K species, 96.5M rows)
    instead of `alphaearth_embeddings_v4` (18K species, 3.37M rows)
  - This recovers ~20K lost species and ~3.4M lost rows
  - `alphaearth_embeddings_v4` kept as LEFT JOIN for emb_NN columns only

Creates NEW table `sinr_v3_unified_v2` by joining:
  1. sinr_v3_features_new_gbif     (9.87M rows) + gbif_new_occurrences (taxon_id)
  2. sinr_v3_features_backfill     (5.26M rows) + occurrences (taxon_id)
     + alphaearth_embeddings_v4    (emb_NN embeddings, LEFT JOIN)
     + v4_env_backfill_v1          (env columns, LEFT JOIN)
  3. sinr_v3_carbon_temporal       (carbon/biomass temporal)
  4. sinr_v3_hilda_lulc            (HILDA land use change)
  5. sinr_v3_aridity_index         (aridity + ET0)

SAFETY: This script ONLY creates new tables. It never modifies or deletes existing data.

Expected output: ~30M rows, ~44K species, ~686 columns

Usage:
  python3 consolidate_bq_v2.py --dry-run     # Print queries without executing
  python3 consolidate_bq_v2.py --execute      # Create the unified table
  python3 consolidate_bq_v2.py --stats        # Show table statistics
  python3 consolidate_bq_v2.py --validate     # Compare v1 vs v2 species counts
"""

import argparse
from datetime import datetime

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
OUTPUT_TABLE = 'sinr_v3_unified_v2'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_table_stats():
    """Show current state of all source tables."""
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)

    tables = [
        'sinr_v3_features_new_gbif',
        'sinr_v3_features_backfill',
        'sinr_v3_carbon_temporal',
        'sinr_v3_hilda_lulc',
        'sinr_v3_aridity_index',
        'alphaearth_embeddings_v4',
        'v4_env_backfill_v1',
        'occurrences',
        'gbif_new_occurrences',
        'sinr_v3_unified_v1',
        OUTPUT_TABLE,
    ]

    log("=== Source Table Statistics ===")
    for tname in tables:
        try:
            t = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{tname}')
            size_gb = t.num_bytes / (1024**3) if t.num_bytes else 0
            log(f"  {tname}: {t.num_rows:>14,} rows, {len(t.schema):>4} cols, {size_gb:.2f} GB")
        except Exception as e:
            log(f"  {tname}: NOT FOUND ({e})")


def validate_v1_vs_v2():
    """Compare v1 and v2 species counts."""
    from google.cloud import bigquery
    client = bigquery.Client(project=BQ_PROJECT)

    q = f"""
    SELECT
        'v1' as version,
        COUNT(*) as rows,
        COUNT(DISTINCT taxon_id) as species
    FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_unified_v1`
    UNION ALL
    SELECT
        'v2' as version,
        COUNT(*) as rows,
        COUNT(DISTINCT taxon_id) as species
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`
    ORDER BY version
    """
    log("=== v1 vs v2 Comparison ===")
    for row in client.query(q).result():
        log(f"  {row.version}: {row.rows:,} rows, {row.species:,} species")


def build_column_lists():
    """Build column lists shared between new_gbif and backfill."""

    env_cols = [
        'bio01', 'bio02', 'bio03', 'bio04', 'bio05', 'bio06', 'bio07', 'bio08',
        'bio09', 'bio10', 'bio11', 'bio12', 'bio13', 'bio14', 'bio15', 'bio16',
        'bio17', 'bio18', 'bio19',
        'soil_ph', 'soil_clay_pct', 'soil_sand_pct', 'soil_organic_carbon',
        'soil_texture_class', 'soil_bulk_density', 'soil_water_content',
        'elevation', 'slope', 'aspect', 'hillshade',
        'treecover2000', 'lossyear', 'hansen_gain',
        'jrc_forest_type', 'jrc_tmf_status', 'jrc_tmf_degrad_year',
        'esa_worldcover_2021', 'sbtn_natural_land',
        'water_occurrence', 'water_recurrence', 'water_seasonality',
        'merit_hand_m', 'merit_upstream_area_km2',
        'gedi_canopy_height_m', 'gedi_foliage_height_div',
        'biomass_agb_mgha', 'human_modification', 'topo_diversity',
        'eco_id', 'biome_num',
        'xiao_planted_forest', 'neumann_natural_prob',
        'tc_vpd_mean', 'tc_aet_mean', 'tc_soil_moisture_mean',
        'tc_pdsi_mean', 'tc_water_deficit_mean', 'tc_solar_rad_mean',
        'dynamic_world', 'fire_frequency_count', 'modis_gpp_mean', 'nighttime_lights',
    ]

    # 8-year AE stack columns
    ae_stack_cols = []
    for year in range(2017, 2025):
        for band in range(64):
            ae_stack_cols.append(f'ae_{year}_{band:02d}')

    # Temporal columns
    temporal_cols = ['modis_lc_at_obs', 'modis_lc_at_ae', 'tc_vpd_delta']

    # Primary AE embedding columns
    emb_cols = [f'emb_{i:02d}' for i in range(64)]

    return env_cols, ae_stack_cols, temporal_cols, emb_cols


def build_unified_query():
    """Build the complete consolidation SQL.

    Key difference from v1:
      - Backfill taxon_id comes from `occurrences` (INNER JOIN on lat+lon)
        instead of `alphaearth_embeddings_v4`
      - `alphaearth_embeddings_v4` becomes LEFT JOIN (for emb_NN only)
      - Occurrences join uses DISTINCT to avoid row explosion
    """
    env_cols, ae_stack_cols, temporal_cols, emb_cols = build_column_lists()

    # ---- Part A: new_gbif (has everything) ----
    new_gbif_select = f"""
    SELECT
        'new_gbif' as data_source,
        g.taxon_id,
        n.latitude,
        n.longitude,
        n.observation_year,
        n.emb_year,
        -- Environment
        {', '.join(f'n.{c}' for c in env_cols)},
        -- 8-year AlphaEarth stack
        {', '.join(f'n.{c}' for c in ae_stack_cols)},
        -- Primary AE embedding at emb_year
        {', '.join(f'n.{c}' for c in emb_cols)},
        -- Temporal
        {', '.join(f'n.{c}' for c in temporal_cols if c != 'tc_vpd_delta')},
        n.tc_vpd_delta
    FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_new_gbif` n
    INNER JOIN `{BQ_PROJECT}.{BQ_DATASET}.gbif_new_occurrences` g
        ON ROUND(n.latitude, 4) = g.lat4dp
        AND ROUND(n.longitude, 4) = g.lon4dp
        AND n.observation_year = g.observation_year
        AND n.emb_year = g.emb_year
    """

    # ---- Part B: backfill ----
    # taxon_id from occurrences (INNER JOIN on lat+lon, deduplicated)
    # emb_NN from alphaearth_embeddings_v4 (LEFT JOIN on lat+lon+emb_year)
    # env from v4_env_backfill_v1 (LEFT JOIN on lat+lon)

    # Map env columns from v4_env_backfill
    env_backfill_cols = []
    for c in env_cols:
        if c == 'hansen_gain':
            env_backfill_cols.append('CAST(e.gain AS FLOAT64) as hansen_gain')
        elif c == 'neumann_natural_prob':
            env_backfill_cols.append('CAST(NULL AS FLOAT64) as neumann_natural_prob')
        elif c == 'xiao_planted_forest':
            env_backfill_cols.append('CAST(NULL AS FLOAT64) as xiao_planted_forest')
        elif c == 'dynamic_world':
            env_backfill_cols.append('CAST(e.dynamic_world AS FLOAT64) as dynamic_world')
        elif c == 'fire_frequency_count':
            env_backfill_cols.append('CAST(e.fire_frequency_count AS FLOAT64) as fire_frequency_count')
        elif c == 'modis_gpp_mean':
            env_backfill_cols.append('CAST(e.modis_gpp_mean AS FLOAT64) as modis_gpp_mean')
        elif c == 'nighttime_lights':
            env_backfill_cols.append('CAST(e.nighttime_lights AS FLOAT64) as nighttime_lights')
        else:
            env_backfill_cols.append(f'e.{c}')

    # Map AE v2.2 embeddings (A00-A63) to emb_NN — now LEFT JOIN
    emb_backfill_cols = [f'a.A{i:02d} as emb_{i:02d}' for i in range(64)]

    # Backfill: taxon_id from occurrences (deduplicated per coordinate)
    # The occurrences table has (decimalLatitude, decimalLongitude, taxon_id, year)
    # We join on lat+lon only (not year) because backfill observation_year
    # doesn't reliably match occurrences.year
    backfill_select = f"""
    SELECT
        'backfill' as data_source,
        occ_dedup.taxon_id,
        b.latitude,
        b.longitude,
        b.observation_year,
        b.emb_year,
        -- Environment (from v4_env_backfill)
        {', '.join(env_backfill_cols)},
        -- 8-year AlphaEarth stack (from v3 backfill)
        {', '.join(f'b.{c}' for c in ae_stack_cols)},
        -- Primary AE embedding (from v2.2 alphaearth_embeddings_v4, LEFT JOIN)
        {', '.join(emb_backfill_cols)},
        -- Temporal (from v3 backfill)
        {', '.join(f'b.{c}' for c in temporal_cols if c != 'tc_vpd_delta')},
        b.tc_vpd_delta
    FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_backfill` b
    INNER JOIN (
        SELECT DISTINCT
            ROUND(decimalLatitude, 4) as lat4,
            ROUND(decimalLongitude, 4) as lon4,
            taxon_id
        FROM `{BQ_PROJECT}.{BQ_DATASET}.occurrences`
        WHERE taxon_id IS NOT NULL
    ) occ_dedup
        ON ROUND(b.latitude, 4) = occ_dedup.lat4
        AND ROUND(b.longitude, 4) = occ_dedup.lon4
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.v4_env_backfill_v1` e
        ON ROUND(b.latitude, 4) = ROUND(e.latitude, 4)
        AND ROUND(b.longitude, 4) = ROUND(e.longitude, 4)
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.alphaearth_embeddings_v4` a
        ON ROUND(b.latitude, 4) = ROUND(a.latitude, 4)
        AND ROUND(b.longitude, 4) = ROUND(a.longitude, 4)
        AND b.emb_year = a.emb_year
    """

    # ---- Phase 2: UNION + LEFT JOIN carbon, HILDA, aridity ----
    full_query = f"""
    CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}` AS

    WITH base AS (
        {new_gbif_select}
        UNION ALL
        {backfill_select}
    )
    SELECT
        base.*,
        -- Carbon temporal features
        c.canopy_height_m as carbon_canopy_height_m,
        c.spawn_agb, c.spawn_agb_unc, c.spawn_bgb, c.spawn_bgb_unc,
        c.gedi_l4b_agbd, c.gedi_l4b_agbd_se, c.gedi_rh98, c.gedi_fhd,
        c.soc_0cm, c.soc_30cm, c.soc_100cm, c.soc_200cm,
        c.ipcc_forest_class,
        c.npp_at_obs, c.gpp_at_obs, c.lai_at_obs, c.fpar_at_obs, c.evi_at_obs,
        c.cci_agb_at_obs, c.cci_agb_sd_at_obs,
        c.npp_at_ae, c.gpp_at_ae, c.lai_at_ae, c.fpar_at_ae, c.evi_at_ae,
        c.cci_agb_at_ae, c.cci_agb_sd_at_ae,
        c.npp_mean_longterm, c.npp_trend,
        -- HILDA land use change
        h.hilda_lulc_at_obs, h.hilda_lulc_at_ae,
        h.lulc_changed, h.forest_to_nonforest, h.has_hilda,
        -- Aridity Index (static, join on 2dp)
        ai.aridity_index, ai.aridity_index_raw,
        ai.et0_mm_yr, ai.et0_mm_yr_raw
    FROM base
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_carbon_temporal` c
        ON ROUND(base.latitude, 4) = ROUND(c.latitude, 4)
        AND ROUND(base.longitude, 4) = ROUND(c.longitude, 4)
        AND base.observation_year = c.observation_year
        AND base.emb_year = c.emb_year
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_hilda_lulc` h
        ON ROUND(base.latitude, 4) = ROUND(h.latitude, 4)
        AND ROUND(base.longitude, 4) = ROUND(h.longitude, 4)
        AND base.observation_year = h.observation_year
        AND base.emb_year = h.emb_year
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_aridity_index` ai
        ON ROUND(base.latitude, 2) = ROUND(ai.latitude, 2)
        AND ROUND(base.longitude, 2) = ROUND(ai.longitude, 2)
    """

    return full_query


def main():
    parser = argparse.ArgumentParser(description='Consolidate SINR v3 BQ tables (v2 — fixed species)')
    parser.add_argument('--dry-run', action='store_true', help='Print queries without executing')
    parser.add_argument('--execute', action='store_true', help='Create the unified table')
    parser.add_argument('--stats', action='store_true', help='Show table statistics')
    parser.add_argument('--validate', action='store_true', help='Compare v1 vs v2')
    args = parser.parse_args()

    if args.stats:
        get_table_stats()
        return

    if args.validate:
        validate_v1_vs_v2()
        return

    query = build_unified_query()

    if args.dry_run:
        log("=== DRY RUN — Query to execute ===")
        print(query)
        log(f"\nThis will create: {BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}")
        log("Run with --execute to create the table")
        return

    if args.execute:
        from google.cloud import bigquery
        client = bigquery.Client(project=BQ_PROJECT)

        # Check if output table already exists
        table_exists = False
        try:
            existing = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}')
            table_exists = True
            log(f"Table {OUTPUT_TABLE} exists ({existing.num_rows:,} rows). Will append remaining chunks.")
        except Exception:
            pass

        # --- Chunked approach: split by observation_year ranges ---
        year_query = """
        SELECT MIN(observation_year) as min_yr, MAX(observation_year) as max_yr
        FROM (
            SELECT observation_year FROM `{p}.{d}.sinr_v3_features_new_gbif`
            WHERE observation_year >= 1900
            UNION ALL
            SELECT observation_year FROM `{p}.{d}.sinr_v3_features_backfill`
            WHERE observation_year >= 1900
        )
        """.format(p=BQ_PROJECT, d=BQ_DATASET)
        yr_result = list(client.query(year_query).result())
        min_yr, max_yr = int(yr_result[0].min_yr), int(yr_result[0].max_yr)
        log(f"Valid year range: {min_yr} to {max_yr}")

        # Count invalid years
        invalid_query = """
        SELECT COUNT(*) as cnt FROM (
            SELECT observation_year FROM `{p}.{d}.sinr_v3_features_new_gbif`
            WHERE observation_year < 1900
            UNION ALL
            SELECT observation_year FROM `{p}.{d}.sinr_v3_features_backfill`
            WHERE observation_year < 1900
        )
        """.format(p=BQ_PROJECT, d=BQ_DATASET)
        inv_result = list(client.query(invalid_query).result())
        invalid_count = int(inv_result[0].cnt)
        log(f"Rows with observation_year < 1900: {invalid_count:,}")

        # Build year chunks
        chunk_size = 5
        chunks = []
        if invalid_count > 0:
            chunks.append((None, min_yr + chunk_size - 1))
            yr = min_yr + chunk_size
        else:
            yr = min_yr
        while yr <= max_yr:
            end_yr = min(yr + chunk_size - 1, max_yr)
            chunks.append((yr, end_yr))
            yr = end_yr + 1
        log(f"Will process {len(chunks)} chunks")

        base_query = query

        for i, (yr_start, yr_end) in enumerate(chunks):
            # WHERE clause goes AFTER all JOINs
            if yr_start is None:
                year_where = f"\n    WHERE base.observation_year <= {yr_end}"
            else:
                year_where = f"\n    WHERE base.observation_year BETWEEN {yr_start} AND {yr_end}"

            if i == 0 and not table_exists:
                chunk_query = base_query + year_where
                log(f"Chunk {i+1}/{len(chunks)}: CREATE TABLE (years {'<1900+' if yr_start is None else yr_start}-{yr_end})...")
            else:
                chunk_query = base_query.replace(
                    f"CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}` AS",
                    f"INSERT INTO `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`"
                ) + year_where
                log(f"Chunk {i+1}/{len(chunks)}: INSERT (years {yr_start}-{yr_end})...")

            try:
                job = client.query(chunk_query)
                log(f"  Job started: {job.job_id}")
                job.result()  # Wait for completion
                table_exists = True

                t = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}')
                log(f"  Done! Running total: {t.num_rows:,} rows, {t.num_bytes / (1024**3):.2f} GB")
            except Exception as e:
                log(f"  ERROR on chunk {i+1}: {e}")
                log("  You can re-run --execute to resume from where it left off.")
                return

        # Final stats
        output = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}')
        log(f"\nDONE! {OUTPUT_TABLE}: {output.num_rows:,} rows, {len(output.schema)} columns")
        log(f"Size: {output.num_bytes / (1024**3):.2f} GB")

        # Quick species count
        q = f"SELECT COUNT(DISTINCT taxon_id) as n FROM `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`"
        for row in client.query(q).result():
            log(f"Distinct species: {row.n:,}")

        return

    parser.print_help()


if __name__ == '__main__':
    main()
