#!/bin/bash
# Load RDF data into Fuseki SPARQL endpoint
# Usage: ./load_data.sh [turtle_file]

set -e

FUSEKI_URL="${FUSEKI_URL:-http://localhost:3030}"
DATASET="${DATASET:-treekipedia}"
ADMIN_PASSWORD="${FUSEKI_ADMIN_PASSWORD:-treekipedia2024}"

# Default file path
RDF_FILE="${1:-/staging/insights.ttl}"

echo "=== Treekipedia SPARQL Data Loader ==="
echo "Fuseki URL: $FUSEKI_URL"
echo "Dataset: $DATASET"
echo "RDF File: $RDF_FILE"

# Check if Fuseki is available
echo ""
echo "Checking Fuseki availability..."
if ! curl -s -f "$FUSEKI_URL/\$/ping" > /dev/null; then
    echo "Error: Fuseki is not available at $FUSEKI_URL"
    exit 1
fi
echo "Fuseki is available"

# Check if dataset exists
echo ""
echo "Checking dataset..."
DATASETS=$(curl -s -u admin:$ADMIN_PASSWORD "$FUSEKI_URL/\$/datasets" | grep -o "\"$DATASET\"" || true)
if [ -z "$DATASETS" ]; then
    echo "Creating dataset '$DATASET'..."
    curl -s -u admin:$ADMIN_PASSWORD -X POST "$FUSEKI_URL/\$/datasets" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "dbName=$DATASET&dbType=tdb2"
    echo "Dataset created"
else
    echo "Dataset '$DATASET' exists"
fi

# Get current triple count
echo ""
echo "Current triple count:"
curl -s "$FUSEKI_URL/$DATASET/sparql" \
    -H "Accept: application/json" \
    --data-urlencode "query=SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d['results']['bindings'][0]['count']['value'])" 2>/dev/null || echo "0"

# Load the RDF file
echo ""
echo "Loading RDF data..."
if [ -f "$RDF_FILE" ]; then
    # Determine content type based on file extension
    case "${RDF_FILE##*.}" in
        ttl)
            CONTENT_TYPE="text/turtle"
            ;;
        nq)
            CONTENT_TYPE="application/n-quads"
            ;;
        nt)
            CONTENT_TYPE="application/n-triples"
            ;;
        rdf|xml)
            CONTENT_TYPE="application/rdf+xml"
            ;;
        jsonld|json)
            CONTENT_TYPE="application/ld+json"
            ;;
        *)
            CONTENT_TYPE="text/turtle"
            ;;
    esac

    echo "Content-Type: $CONTENT_TYPE"

    # Upload the file
    RESPONSE=$(curl -s -w "\n%{http_code}" -u admin:$ADMIN_PASSWORD \
        -X POST "$FUSEKI_URL/$DATASET/data" \
        -H "Content-Type: $CONTENT_TYPE" \
        --data-binary "@$RDF_FILE")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        echo "Data loaded successfully (HTTP $HTTP_CODE)"
    else
        echo "Error loading data (HTTP $HTTP_CODE)"
        echo "$BODY"
        exit 1
    fi
else
    echo "Error: File not found: $RDF_FILE"
    echo "Please generate RDF data first with:"
    echo "  python3 ../scripts/export_to_rdf.py --format turtle --output insights.ttl"
    exit 1
fi

# Get new triple count
echo ""
echo "New triple count:"
curl -s "$FUSEKI_URL/$DATASET/sparql" \
    -H "Accept: application/json" \
    --data-urlencode "query=SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d['results']['bindings'][0]['count']['value'])"

echo ""
echo "=== Data load complete ==="
echo ""
echo "SPARQL endpoint available at: $FUSEKI_URL/$DATASET/sparql"
echo "Try a query:"
echo "  curl '$FUSEKI_URL/$DATASET/sparql' --data-urlencode 'query=SELECT * WHERE { ?s ?p ?o } LIMIT 10'"
