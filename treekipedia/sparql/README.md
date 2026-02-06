# Treekipedia SPARQL Endpoint

This directory contains the configuration and scripts for running a SPARQL endpoint for the Treekipedia Knowledge Graph using Apache Jena Fuseki.

## Quick Start

```bash
# Make setup script executable
chmod +x setup.sh scripts/*.sh

# Run setup (starts Docker, creates dataset, loads data)
./setup.sh
```

The SPARQL endpoint will be available at: **http://localhost:3030/treekipedia/sparql**

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PostgreSQL    │────▶│  export_to_rdf   │────▶│  Apache Jena    │
│   (insights)    │     │     (Python)     │     │    Fuseki       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                        │
                              ▼                        ▼
                        insights.ttl             SPARQL Endpoint
                        (RDF/Turtle)          /treekipedia/sparql
```

## Components

- **docker-compose.yml**: Docker configuration for Fuseki
- **config/treekipedia.ttl**: Fuseki dataset configuration
- **scripts/load_data.sh**: Script to load RDF data
- **scripts/example_queries.sparql**: Sample SPARQL queries
- **data/**: Directory for RDF data files

## Usage

### Starting the Endpoint

```bash
# Start Fuseki
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f fuseki
```

### Loading Data

```bash
# Generate RDF from database
cd ../scripts
python3 export_to_rdf.py --format turtle --output ../sparql/data/insights.ttl

# Load into Fuseki
cd ../sparql
./scripts/load_data.sh data/insights.ttl
```

### Querying

**Via curl:**
```bash
curl 'http://localhost:3030/treekipedia/sparql' \
  -H 'Accept: application/sparql-results+json' \
  --data-urlencode 'query=SELECT * WHERE { ?s ?p ?o } LIMIT 10'
```

**Via browser:**
Navigate to http://localhost:3030 and use the query interface.

**Via Python:**
```python
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:3030/treekipedia/sparql")
sparql.setQuery("""
    PREFIX tkp: <https://treekipedia.silvi.earth/ontology#>
    PREFIX dwc: <http://rs.tdwg.org/dwc/terms/>

    SELECT ?species ?scientificName ?habitat
    WHERE {
      ?species dwc:scientificName ?scientificName .
      ?insight tkp:aboutTaxon ?species ;
               dwc:habitat ?habitat .
    }
    LIMIT 20
""")
sparql.setReturnFormat(JSON)
results = sparql.query().convert()

for result in results["results"]["bindings"]:
    print(f"{result['scientificName']['value']}: {result['habitat']['value']}")
```

## Example Queries

See `scripts/example_queries.sparql` for comprehensive examples including:

1. **List species with scientific names**
2. **Find insights for a specific species**
3. **High-confidence habitat information**
4. **Conservation status queries**
5. **Agroforestry use cases**
6. **Count insights by type**
7. **Provenance tracking**
8. **Cross-species ecological analysis**
9. **Confidence statistics**

## Ontology Namespaces

| Prefix | Namespace | Description |
|--------|-----------|-------------|
| `treekipedia:` | `https://treekipedia.silvi.earth/species/` | Species identifiers |
| `tkp:` | `https://treekipedia.silvi.earth/ontology#` | Treekipedia ontology terms |
| `dwc:` | `http://rs.tdwg.org/dwc/terms/` | Darwin Core terms |
| `envo:` | `http://purl.obolibrary.org/obo/ENVO_` | Environment Ontology |
| `pato:` | `http://purl.obolibrary.org/obo/PATO_` | Phenotype And Trait Ontology |
| `prov:` | `http://www.w3.org/ns/prov#` | W3C Provenance Ontology |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/treekipedia/sparql` | GET/POST | SPARQL query endpoint |
| `/treekipedia/query` | GET/POST | Alias for SPARQL queries |
| `/treekipedia/update` | POST | SPARQL update endpoint |
| `/treekipedia/data` | GET | Graph Store Protocol (read) |
| `/treekipedia/data` | POST | Graph Store Protocol (write) |

## Administration

**Access Admin UI:** http://localhost:3030

**Default credentials:**
- Username: `admin`
- Password: `treekipedia2024` (or `$FUSEKI_ADMIN_PASSWORD`)

**Manage datasets:**
```bash
# List datasets
curl -u admin:treekipedia2024 http://localhost:3030/$/datasets

# Get dataset statistics
curl http://localhost:3030/treekipedia/sparql \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }'
```

## Data Refresh

To update the knowledge graph with new insights:

```bash
# 1. Export latest data from PostgreSQL
python3 ../scripts/export_to_rdf.py --format turtle --output data/insights.ttl

# 2. Clear existing data (optional - for full refresh)
curl -u admin:treekipedia2024 -X POST \
  'http://localhost:3030/treekipedia/update' \
  -H 'Content-Type: application/sparql-update' \
  -d 'CLEAR ALL'

# 3. Load new data
./scripts/load_data.sh data/insights.ttl
```

## Production Deployment

For production, consider:

1. **Set secure admin password:**
   ```bash
   export FUSEKI_ADMIN_PASSWORD="your-secure-password"
   ```

2. **Configure memory allocation** in docker-compose.yml:
   ```yaml
   environment:
     - JVM_ARGS=-Xmx4g -Xms2g
   ```

3. **Add reverse proxy** (nginx) for HTTPS

4. **Enable query timeouts** in Fuseki config

5. **Set up automated data refresh** (cron job)

## Troubleshooting

**Fuseki won't start:**
```bash
# Check Docker logs
docker compose logs fuseki

# Verify port 3030 is available
lsof -i :3030
```

**Data not loading:**
```bash
# Verify RDF file is valid Turtle
rapper -i turtle -c data/insights.ttl

# Check Fuseki error logs
docker compose logs fuseki | grep -i error
```

**Queries returning empty:**
```bash
# Verify data is loaded
curl 'http://localhost:3030/treekipedia/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }'
```

## Stopping

```bash
# Stop Fuseki (preserves data)
docker compose down

# Stop and remove all data
docker compose down -v
```
