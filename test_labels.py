from google.cloud import bigquery
client = bigquery.Client(project="treekipedia-479918")
sql = "SELECT data_source, COUNT(*) as c FROM `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean` GROUP BY data_source"
for r in client.query(sql).result():
    print(r.data_source, r.c)
