#!/bin/bash
# =============================================================================
# TreeKipedia Production Startup Script
# =============================================================================

set -e

echo "🌲 Starting TreeKipedia in Production Mode..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Copy .env.example to .env and configure your settings"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Create necessary directories
mkdir -p data/occurrences generated_ontologies ontology_history Uploads logs

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "✓ Python version: $python_version"

# Activate virtual environment if it exists
if [ -d "myenv" ]; then
    echo "✓ Activating virtual environment..."
    source myenv/bin/activate
fi

# Check dependencies
echo "✓ Checking dependencies..."
pip list | grep -q flask || { echo "❌ Flask not installed"; exit 1; }
pip list | grep -q gunicorn || pip install gunicorn

# Database check
echo "✓ Checking database connection..."
python3 -c "import psycopg2; psycopg2.connect(host='$POSTGRES_HOST', database='$POSTGRES_DB', user='$POSTGRES_USER', password='$POSTGRES_PASSWORD')" || {
    echo "⚠️  Warning: Cannot connect to PostgreSQL"
}

# Start application with gunicorn
echo "🚀 Starting TreeKipedia with Gunicorn..."
echo "📊 Listening on http://0.0.0.0:${PORT:-5001}"
echo ""

exec gunicorn \
    --bind 0.0.0.0:${PORT:-5001} \
    --workers ${WORKERS:-4} \
    --timeout 120 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level ${LOG_LEVEL:-info} \
    wsgi:app
