from google.cloud import bigquery
client = bigquery.Client(project="treekipedia-479918")
sql = "SELECT COUNT(*) as c FROM `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean`"
r = next(client.query(sql).result())
print(f"Total labels: {r.c}")
