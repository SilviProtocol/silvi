#!/bin/bash

# =============================================================================
# Quick Install Script for GeoParquet + DuckDB Occurrence Data System
# =============================================================================

echo "🌲 TreeKipedia - Occurrence Data System Installer"
echo "=================================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "✓ Python version: $python_version"

# Create virtual environment (optional but recommended)
read -p "Create virtual environment? (recommended) [y/N]: " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv_occurrence
    source venv_occurrence/bin/activate
    echo "✓ Virtual environment created and activated"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
echo "========================="

pip install --upgrade pip

echo "Installing DuckDB..."
pip install duckdb>=0.10.0

echo "Installing geospatial packages..."
pip install geopandas>=0.14.0 shapely>=2.0.0

echo "Installing Parquet support..."
pip install pyarrow>=14.0.0 fastparquet>=2023.10.0

echo "Installing RDF support..."
pip install rdflib>=7.0.0

echo "Installing data processing libraries..."
pip install pandas>=2.0.0 numpy>=1.24.0

# Optional: AWS support
read -p "Install AWS S3 support (for cloud storage)? [y/N]: " install_aws
if [[ $install_aws =~ ^[Yy]$ ]]; then
    echo "Installing AWS libraries..."
    pip install boto3>=1.34.0 s3fs>=2023.12.0
fi

echo ""
echo "✓ All dependencies installed!"
echo ""

# Create data directory
echo "Creating data directories..."
mkdir -p data/occurrences
echo "✓ Created: data/occurrences/"

# Test DuckDB installation
echo ""
echo "Testing DuckDB installation..."
python3 -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL spatial'); conn.execute('LOAD spatial'); print('✓ DuckDB + Spatial extension working!')" 2>&1

# Test GeoPandas
echo "Testing GeoPandas installation..."
python3 -c "import geopandas; print('✓ GeoPandas working!')" 2>&1

echo ""
echo "=================================================="
echo "🎉 Installation Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Start the app: python app.py"
echo "2. Open browser: http://localhost:5000/occurrence/"
echo "3. Upload your first CSV with occurrence data"
echo ""
echo "Documentation:"
echo "- Setup guide: OCCURRENCE_DATA_SETUP.md"
echo "- System overview: OCCURRENCE_SYSTEM_SUMMARY.md"
echo ""
echo "Optional: Configure S3 storage"
echo "  export OCCURRENCE_S3_BUCKET='s3://your-bucket'"
echo "  export AWS_ACCESS_KEY_ID='your-key'"
echo "  export AWS_SECRET_ACCESS_KEY='your-secret'"
echo ""
echo "Happy occurrence data management! 🌍🌳"
