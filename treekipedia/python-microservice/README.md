# Treekipedia Python Microservice

**Headless Python backend for GraphFlow functionality**

This microservice provides critical Python-only operations that cannot be replicated in Node.js:
- OWL/RDF ontology generation (owlready2, rdflib)
- PostgreSQL → Apache Fuseki synchronization
- Google Sheets integration for ontology import
- Multi-sheet biodiversity ontology generation

## Architecture

```
Next.js Frontend (port 3000)
        ↓
Express Backend (port 5001) - User-facing API
        ↓
Python Microservice (port 5002) - Internal only, NOT public
```

**Important**: This service should NEVER be exposed to the public internet. It is accessed exclusively by the Express backend via localhost.

## Features

### Sync Operations
- **Full Sync**: Sync all 67,743 species from PostgreSQL to Fuseki
- **Incremental Sync**: Sync only new/updated species since timestamp
- **Progress Streaming**: Real-time progress via Server-Sent Events

### Ontology Generation
- **CSV Upload**: Generate OWL ontologies from uploaded CSV files
- **Google Sheets**: Import and generate ontologies from Google Sheets
- **Field Detection**: Automatic detection of 120+ biodiversity field patterns
- **Multi-Sheet Support**: Process multiple related sheets with relationship detection

### SPARQL Operations
- **Query Execution**: Run SPARQL queries against Fuseki
- **Statistics**: Get triple counts and graph statistics

### Version Management
- **Snapshots**: Create ontology version snapshots
- **History**: Track ontology version history
- **Rollback**: Restore previous ontology versions

## Setup

### 1. Create Virtual Environment

```bash
cd treekipedia/python-microservice
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your actual credentials
```

Required environment variables:
- `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `FUSEKI_BASE_URL`, `FUSEKI_DATASET`, `FUSEKI_SPARQL_ENDPOINT`
- `PORT` (default: 5002)

### 4. Run the Service

**Development**:
```bash
python3 api_only.py
```

**Production (with Gunicorn)**:
```bash
gunicorn -w 4 -b 0.0.0.0:5002 api_only:app
```

**Production (with systemd)**:
See [DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md) for systemd service setup.

## API Endpoints

Full API documentation available in [API_SPEC.yaml](./API_SPEC.yaml).

### Health & Status

- `GET /api/health` - Health check
- `GET /api/status` - Connection status (PostgreSQL, Fuseki)
- `GET /api/status/fuseki` - Detailed Fuseki statistics

### Sync Operations

- `POST /api/sync/species` - Full species sync (returns SSE stream)
  ```json
  {
    "batchSize": 1000,
    "table": "species"
  }
  ```

- `POST /api/sync/incremental` - Incremental sync
  ```json
  {
    "since": "2025-01-01T00:00:00Z"
  }
  ```

### Ontology Generation

- `POST /api/ontology/generate` - Generate from CSV files (multipart/form-data)
- `POST /api/ontology/from-sheets` - Generate from Google Sheets
  ```json
  {
    "spreadsheetId": "abc123...",
    "sheets": ["Sheet1", "Sheet2"]
  }
  ```

### SPARQL

- `POST /api/sparql/query` - Execute SPARQL query
  ```json
  {
    "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
  }
  ```

### Version Management

- `GET /api/versions` - List all versions
- `POST /api/versions/create` - Create new version snapshot

## Usage Examples

### Health Check

```bash
curl http://localhost:5002/api/health
```

### Sync Species to Fuseki

```bash
curl -X POST http://localhost:5002/api/sync/species \
  -H "Content-Type: application/json" \
  -d '{"batchSize": 1000}'
```

The response is a Server-Sent Events stream:
```
data: {"type":"status","message":"Starting sync..."}

data: {"type":"progress","message":"Syncing species..."}

data: {"type":"complete","message":"Sync completed"}
```

### Generate Ontology from CSV

```bash
curl -X POST http://localhost:5002/api/ontology/generate \
  -F "files=@species_data.csv" \
  -F "files=@taxonomy.csv"
```

### Execute SPARQL Query

```bash
curl -X POST http://localhost:5002/api/sparql/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "PREFIX bd: <http://www.example.org/biodiversity-ontology#> SELECT ?s ?name WHERE { ?s bd:scientificName ?name } LIMIT 10"
  }'
```

## Testing

Run unit tests:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html tests/
```

## Dependencies Explained

### Critical Python-Only Libraries

**owlready2** (1,200 lines of GraphFlow code)
- OWL ontology manipulation
- No JavaScript alternative exists
- Used for: Creating OWL classes, properties, instances

**rdflib** (800 lines of GraphFlow code)
- RDF triple generation and serialization
- No JavaScript alternative with same capabilities
- Used for: Converting data to RDF triples, exporting to Turtle/RDF-XML

**gspread** (600 lines of GraphFlow code)
- Google Sheets API integration
- Complex authentication and data reading
- Used for: Importing biodiversity data from Google Sheets

**postgres_to_fuseki_sync.py** (900 lines)
- Custom batch processing logic
- PostgreSQL → RDF conversion
- Used for: Syncing 67k+ species to Fuseki

**Total: ~3,700 lines of Python code that MUST stay in Python**

### Other Dependencies

- **Flask**: Lightweight web framework for API
- **psycopg2**: PostgreSQL database connection
- **pandas/numpy**: Data processing and transformation
- **requests**: HTTP client for Fuseki communication

## Security

### Internal Service Only

This service is designed for internal use ONLY:
- NOT exposed to public internet
- Accessed only by Express backend (localhost:5001)
- CORS restricted to localhost origins

### Authentication

Optional internal authentication via `X-Internal-Auth` header:
```python
INTERNAL_AUTH_TOKEN=your-random-token-here
```

Express backend sends this token with all requests.

### File Uploads

- Maximum file size: 32MB
- Files stored in temporary upload directory
- Automatic cleanup after processing

## Performance

### Sync Performance

**Full Sync (67,743 species)**:
- Time: 20-30 minutes
- Batch size: 1000 species per batch
- Memory usage: ~500MB peak
- Network: ~100 RDF triples per species = ~6.7M triples total

**Incremental Sync**:
- Time: 1-5 minutes (depends on changes)
- Only processes new/updated species

### Optimization Tips

1. **Batch Size**: Increase to 2000 for faster sync (uses more memory)
2. **Parallel Processing**: Run multiple sync processes (experimental)
3. **Fuseki Heap**: Increase Java heap size to 4GB+

## Monitoring

### Logs

Development:
```bash
python3 api_only.py  # Logs to stdout
```

Production:
```bash
journalctl -u treekipedia-python -f  # Follow systemd logs
```

### Health Checks

Express backend should periodically check:
```bash
curl http://localhost:5002/api/health
```

If unhealthy, systemd will auto-restart the service.

## Troubleshooting

### "GraphFlow modules not available"

**Cause**: Python modules not in path or import error

**Fix**:
```bash
# Verify GraphFlow path exists
ls -la ../../graphflow-extracted/silvi-open-graphflow/

# Check Python path
python3 -c "import sys; print(sys.path)"

# Test imports manually
python3 -c "from postgres_to_fuseki_sync import PostgreSQLFusekiSync"
```

### Connection Errors

**PostgreSQL connection failed**:
```bash
# Test PostgreSQL connection
psql -h 167.172.143.162 -U postgres -d treekipedia -c "SELECT COUNT(*) FROM species"
```

**Fuseki connection failed**:
```bash
# Test Fuseki endpoint
curl http://167.172.143.162:3030/$/ping
```

### Sync Hangs or Crashes

**Reduce batch size**:
```json
{"batchSize": 500}
```

**Increase Fuseki heap**:
```bash
# Edit Fuseki service
sudo nano /etc/systemd/system/fuseki.service

# Add:
Environment="JAVA_OPTS=-Xmx4g"

# Restart
sudo systemctl daemon-reload
sudo systemctl restart fuseki
```

## Development

### Adding New Endpoints

1. Add route to `api_only.py`
2. Document in `API_SPEC.yaml`
3. Add tests in `tests/`
4. Update this README

### Code Style

```bash
# Format code
black api_only.py

# Lint code
flake8 api_only.py
```

## Deployment

See [DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md) for:
- Systemd service setup
- Nginx configuration (if needed)
- Production environment variables
- Monitoring and logging setup

## Related Documentation

- [Integration Plan Summary](../../INTEGRATION_PLAN_SUMMARY.md) - Overall architecture
- [API Specification](./API_SPEC.yaml) - OpenAPI 3.0 spec
- [Deployment Guide](../../DEPLOYMENT_GUIDE.md) - Production deployment
- [GraphFlow Documentation](../../graphflow-extracted/silvi-open-graphflow/README.md) - Original GraphFlow

## Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section
- Review logs: `journalctl -u treekipedia-python -f`
- Test connections: `curl http://localhost:5002/api/status`

## License

Part of the Treekipedia project - open source biodiversity knowledge platform.
