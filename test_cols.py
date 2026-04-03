from google.cloud import bigquery
import orchestrator.build_sinr_v41_preview_strict_core as preview_core
client = bigquery.Client(project="treekipedia-479918")
required = set(preview_core.build_column_list())
required.add("modis_gpp_mean")
required.add("nighttime_lights")

def check(t):
    schema = {f.name for f in client.get_table(f"treekipedia-479918.species_data.{t}").schema}
    missing = required - schema
    if missing:
        print(f"Missing in {t}: {missing}")
    else:
        print(f"All good for {t}")

check("sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1")
check("sinr_v3_features_backfill_strict_full")
