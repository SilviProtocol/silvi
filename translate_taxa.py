import json
import sys
import re

with open("orchestrator/contracts/sinr_v3/species_mapping_v41_preview_train.json") as f:
    mapping = json.load(f)

# The mapping is: species_name -> {"taxon": "AngMa...", "index": X}
taxon_to_name = {}
for name, data in mapping.items():
    if isinstance(data, dict) and "taxon" in data:
        taxon_to_name[data["taxon"]] = name
    elif isinstance(data, str): # if it's flat
        taxon_to_name[data] = name

for line in sys.stdin:
    m = re.search(r'(Ang[A-Z][a-z][A-Za-z0-9-]+|Gym[A-Z][a-z][A-Za-z0-9-]+)', line)
    if m:
        taxon = m.group(1)
        name = taxon_to_name.get(taxon, "UNKNOWN")
        line = line.replace(taxon, f"{name} ({taxon})")
    print(line.strip())
