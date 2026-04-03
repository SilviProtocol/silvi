from google.cloud import bigquery
client = bigquery.Client(project="treekipedia-479918")
for t in client.list_tables("species_data"):
    if "train" in t.table_id:
        print(t.table_id)
