import sys
import subprocess
import json
import re

taxons = set()
lines = sys.stdin.read().splitlines()
for line in lines:
    m = re.search(r'(Ang[A-Za-z0-9-]+|Gym[A-Za-z0-9-]+|Cy[A-Za-z0-9-]+)', line)
    if m:
        taxons.add(m.group(1))

# chunk query to 100 taxons at a time
taxons = list(taxons)
taxon_to_name = {}

for i in range(0, len(taxons), 100):
    chunk = taxons[i:i+100]
    quoted = [f"'{t}'" for t in chunk]
    query = f"SELECT taxon_id, any_value(species_name) as name FROM `treekipedia-479918.species_data.gbif_new_occurrences` WHERE taxon_id IN ({','.join(quoted)}) GROUP BY taxon_id"
    cmd = ["bq", "query", "--use_legacy_sql=false", "--format=json", query]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(res.stdout)
        for row in data:
            taxon_to_name[row["taxon_id"]] = row["name"]
    except:
        pass

for line in lines:
    m = re.search(r'(Ang[A-Za-z0-9-]+|Gym[A-Za-z0-9-]+|Cy[A-Za-z0-9-]+)', line)
    if m:
        taxon = m.group(1)
        name = taxon_to_name.get(taxon, "UNKNOWN")
        line = line.replace(taxon, f"{name} ({taxon})")
    print(line)
