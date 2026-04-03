#!/usr/bin/env python3
"""
consolidate_bq_v1.py — Consolidate all SINR v3 BQ tables into Master Training Data v1.

Creates a NEW table `sinr_v3_unified_v1` by LEFT JOINing:
  1. sinr_v3_features_new_gbif     (9.87M rows, 645 cols — full env + 8-year AE stack)
  2. sinr_v3_features_backfill     (5.26M rows, 520 cols — 8-year AE stack only)
     + alphaearth_embeddings_v4    (3.37M rows — v2.2 base: AE + taxon_id)
     + v4_env_backfill_v1          (1.59M rows — env columns for backfill)
  3. sinr_v3_carbon_temporal       (12.93M rows — carbon/biomass temporal)
  4. sinr_v3_hilda_lulc            (14.0M rows — HILDA land use change)
  5. sinr_v3_aridity_index         (in progress — aridity + ET0)

SAFETY: This script ONLY creates new tables. It never modifies or deletes existing data.

Column naming conventions:
  - v3 new_gbif: ae_YYYY_NN (8-year stack), emb_NN (primary embedding), observation_year
  - v2.2 backfill: A00-A63 (single-year AE at emb_year), orig_year → observation_year
  - Both: latitude, longitude, emb_year

Strategy:
  Phase 1: UNION new_gbif + enriched backfill → base table
  Phase 2: LEFT JOIN carbon, HILDA, aridity onto base

Usage:
  python3 consolidate_bq_v1.py --dry-run     # Print queries without executing
  python3 consolidate_bq_v1.py --execute      # Create the unified table
  python3 consolidate_bq_v1.py --stats        # Show table statistics
"""

import argparse
from datetime import datetime

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
OUTPUT_TABLE = 'sinr_v3_unified_v1'

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
        'v4_env_backfill_v2',
    ]

    log("=== Source Table Statistics ===")
    for tname in tables:
        try:
            t = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{tname}')
            size_gb = t.num_bytes / (1024**3) if t.num_bytes else 0
            log(f"  {tname}: {t.num_rows:>12,} rows, {len(t.schema):>4} cols, {size_gb:.2f} GB")
        except Exception as e:
            log(f"  {tname}: NOT FOUND ({e})")


def build_phase1_query():
    """Build the UNION query for new_gbif + enriched backfill.

    The backfill table has the 8-year AE stack but is missing env columns.
    We LEFT JOIN it with v4_env_backfill_v1 to get env columns.
    The v2.2 AE embeddings (A00-A63) map to the emb_NN columns in v3.
    """

    # Columns that new_gbif has but backfill doesn't
    # These come from v4_env_backfill_v1 for backfill rows
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

    # 8-year AE stack columns (both tables have these)
    ae_stack_cols = []
    for year in range(2017, 2025):
        for band in range(64):
            ae_stack_cols.append(f'ae_{year}_{band:02d}')

    # Temporal columns (both have these)
    temporal_cols = ['modis_lc_at_obs', 'modis_lc_at_ae', 'tc_vpd_delta']

    # emb_NN columns (new_gbif has these, backfill doesn't)
    emb_cols = [f'emb_{i:02d}' for i in range(64)]

    return env_cols, ae_stack_cols, temporal_cols, emb_cols


def build_unified_query():
    """Build the complete consolidation SQL.

    IMPORTANT: Uses CREATE TABLE ... AS SELECT to create a new table.
    Never modifies existing tables.
    """
    env_cols, ae_stack_cols, temporal_cols, emb_cols = build_phase1_query()

    # ---- Part A: new_gbif (has everything) ----
    # JOIN with gbif_new_occurrences to get taxon_id (species label)
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

    # ---- Part B: backfill (AE stack from v3 table, env from v4_env_backfill) ----
    # Map v4 env columns, handling column name differences
    env_backfill_cols = []
    for c in env_cols:
        if c == 'hansen_gain':
            env_backfill_cols.append('CAST(e.gain AS FLOAT64) as hansen_gain')
        elif c == 'neumann_natural_prob':
            env_backfill_cols.append('CAST(NULL AS FLOAT64) as neumann_natural_prob')  # not in v4
        elif c == 'xiao_planted_forest':
            env_backfill_cols.append('CAST(NULL AS FLOAT64) as xiao_planted_forest')  # not in v4
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

    # Map AE v2.2 embeddings (A00-A63 from alphaearth_embeddings_v4) to emb_NN
    emb_backfill_cols = [f'a.A{i:02d} as emb_{i:02d}' for i in range(64)]

    # JOIN with alphaearth_embeddings_v4 which has taxon_id for backfill rows
    backfill_select = f"""
    SELECT
        'backfill' as data_source,
        a.taxon_id,
        b.latitude,
        b.longitude,
        b.observation_year,
        b.emb_year,
        -- Environment (from v4_env_backfill)
        {', '.join(env_backfill_cols)},
        -- 8-year AlphaEarth stack (from v3 backfill)
        {', '.join(f'b.{c}' for c in ae_stack_cols)},
        -- Primary AE embedding (from v2.2 alphaearth_embeddings_v4)
        {', '.join(emb_backfill_cols)},
        -- Temporal (from v3 backfill)
        {', '.join(f'b.{c}' for c in temporal_cols if c != 'tc_vpd_delta')},
        b.tc_vpd_delta
    FROM `{BQ_PROJECT}.{BQ_DATASET}.sinr_v3_features_backfill` b
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.v4_env_backfill_v1` e
        ON ROUND(b.latitude, 4) = ROUND(e.latitude, 4)
        AND ROUND(b.longitude, 4) = ROUND(e.longitude, 4)
    INNER JOIN `{BQ_PROJECT}.{BQ_DATASET}.alphaearth_embeddings_v4` a
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
    parser = argparse.ArgumentParser(description='Consolidate SINR v3 BQ tables')
    parser.add_argument('--dry-run', action='store_true', help='Print queries without executing')
    parser.add_argument('--execute', action='store_true', help='Create the unified table')
    parser.add_argument('--stats', action='store_true', help='Show table statistics')
    args = parser.parse_args()

    if args.stats:
        get_table_stats()
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
        # First, find the VALID year range (exclude sentinel values like -9999)
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

        # Also count invalid years to include them
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

        # Build year chunks: first chunk includes all invalid years + early valid years
        chunk_size = 5  # years per chunk
        chunks = []
        # Chunk 0: everything < min_yr (invalid years) + first valid range
        if invalid_count > 0:
            chunks.append((None, min_yr + chunk_size - 1))  # None = no lower bound
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
            # Build WHERE clause — goes AFTER all JOINs
            if yr_start is None:
                # First chunk: includes invalid years + early valid years
                year_where = f"\n    WHERE base.observation_year <= {yr_end}"
            else:
                year_where = f"\n    WHERE base.observation_year BETWEEN {yr_start} AND {yr_end}"

            if i == 0 and not table_exists:
                # First chunk: CREATE TABLE
                chunk_query = base_query + year_where
                log(f"Chunk {i+1}/{len(chunks)}: CREATE TABLE (years {'<1900+' if yr_start is None else yr_start}-{yr_end})...")
            else:
                # Subsequent chunks: INSERT INTO
                chunk_query = base_query.replace(
                    f"CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}` AS",
                    f"INSERT INTO `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE}`"
                ) + year_where
                log(f"Chunk {i+1}/{len(chunks)}: INSERT (years {yr_start}-{yr_end})...")

            try:
                job = client.query(chunk_query)
                log(f"  Job started: {job.job_id}")
                job.result()  # Wait
                table_exists = True

                # Check progress
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
        return

    parser.print_help()


if __name__ == '__main__':
    main()
