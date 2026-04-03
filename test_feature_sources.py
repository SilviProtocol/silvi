from google.cloud import bigquery
client = bigquery.Client(project="treekipedia-479918")
tables = [
  "sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1",
  "sinr_v3_features_backfill_strict_full"
]
for t in tables:
    sql = f"SELECT count(*) as c FROM `treekipedia-479918.species_data.{t}`"
    for r in client.query(sql).result():
        print(t, r.c)
