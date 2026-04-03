from google.cloud import bigquery
client = bigquery.Client(project="treekipedia-479918")
for f in client.get_table("treekipedia-479918.species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1").schema:
    if f.name == "data_source": print("Found in new_gbif")
for f in client.get_table("treekipedia-479918.species_data.sinr_v3_features_backfill_strict_full").schema:
    if f.name == "data_source": print("Found in backfill")
