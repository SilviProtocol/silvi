#!/bin/bash
# Treekipedia SPARQL Endpoint Setup Script
# Sets up Apache Jena Fuseki with Docker and loads initial data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Treekipedia SPARQL Endpoint Setup ==="
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/config"

# Set admin password if not already set
if [ -z "$FUSEKI_ADMIN_PASSWORD" ]; then
    export FUSEKI_ADMIN_PASSWORD="treekipedia2024"
    echo "Using default admin password. Set FUSEKI_ADMIN_PASSWORD for production."
fi

# Start Fuseki with Docker Compose
echo ""
echo "Starting Fuseki..."
cd "$SCRIPT_DIR"

# Use docker compose (v2) or docker-compose (v1)
if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

# Wait for Fuseki to be ready
echo ""
echo "Waiting for Fuseki to start..."
for i in {1..30}; do
    if curl -s -f "http://localhost:3030/\$/ping" > /dev/null 2>&1; then
        echo "Fuseki is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Fuseki failed to start within 30 seconds"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Create the treekipedia dataset
echo ""
echo "Creating treekipedia dataset..."
DATASET_CHECK=$(curl -s -u admin:$FUSEKI_ADMIN_PASSWORD "http://localhost:3030/\$/datasets" | grep -o '"treekipedia"' || true)

if [ -z "$DATASET_CHECK" ]; then
    curl -s -u admin:$FUSEKI_ADMIN_PASSWORD -X POST "http://localhost:3030/\$/datasets" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "dbName=treekipedia&dbType=tdb2"
    echo "Dataset 'treekipedia' created"
else
    echo "Dataset 'treekipedia' already exists"
fi

# Check if we should generate and load data
echo ""
echo "Checking for RDF data..."
RDF_FILE="$SCRIPT_DIR/data/insights.ttl"

if [ ! -f "$RDF_FILE" ]; then
    echo "No RDF data found. Generating from database..."

    # Check if export script exists
    EXPORT_SCRIPT="$PROJECT_ROOT/scripts/export_to_rdf.py"
    if [ -f "$EXPORT_SCRIPT" ]; then
        cd "$PROJECT_ROOT/scripts"
        python3 export_to_rdf.py --format turtle --output "$RDF_FILE"
        echo "RDF data generated: $RDF_FILE"
    else
        echo "Warning: export_to_rdf.py not found at $EXPORT_SCRIPT"
        echo "Please generate RDF data manually:"
        echo "  python3 $PROJECT_ROOT/scripts/export_to_rdf.py --format turtle --output $RDF_FILE"
    fi
fi

# Load data if file exists
if [ -f "$RDF_FILE" ]; then
    echo ""
    echo "Loading RDF data into Fuseki..."
    chmod +x "$SCRIPT_DIR/scripts/load_data.sh"

    # Copy file to staging for Docker container access
    cp "$RDF_FILE" "$SCRIPT_DIR/data/"

    # Load via HTTP API
    RESPONSE=$(curl -s -w "\n%{http_code}" -u admin:$FUSEKI_ADMIN_PASSWORD \
        -X POST "http://localhost:3030/treekipedia/data" \
        -H "Content-Type: text/turtle" \
        --data-binary "@$RDF_FILE")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        echo "Data loaded successfully!"
    else
        echo "Warning: Data load returned HTTP $HTTP_CODE"
    fi
fi

# Print summary
echo ""
echo "=== Setup Complete ==="
echo ""
echo "SPARQL Endpoint: http://localhost:3030/treekipedia/sparql"
echo "Admin UI:        http://localhost:3030"
echo "Admin Password:  $FUSEKI_ADMIN_PASSWORD"
echo ""
echo "Test with:"
echo "  curl 'http://localhost:3030/treekipedia/sparql' \\"
echo "    -H 'Accept: application/json' \\"
echo "    --data-urlencode 'query=SELECT * WHERE { ?s ?p ?o } LIMIT 5'"
echo ""
echo "See example queries in: $SCRIPT_DIR/scripts/example_queries.sparql"
echo ""
echo "To stop: docker compose down (in $SCRIPT_DIR)"
