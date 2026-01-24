# GeoParquet + DuckDB Occurrence Data System

## 🎯 Overview

This system provides efficient, versioned storage and querying of biodiversity occurrence data using:
- **GeoParquet**: Columnar geospatial format (10x compression vs CSV)
- **DuckDB**: Fast analytical queries without loading entire datasets
- **Version Control**: Track data evolution over time
- **Cloud Ready**: Optional S3 integration

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_occurrence.txt
```

Or install individually:
```bash
pip install duckdb geopandas shapely pyarrow rdflib
```

### 2. Configure (Optional)

Set environment variables for cloud storage:

```bash
# Optional: S3 storage
export OCCURRENCE_S3_BUCKET="s3://your-bucket-name"
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-east-1"

# Optional: Local storage path (default: data/occurrences)
export OCCURRENCE_STORAGE_PATH="/path/to/occurrences"
```

### 3. Start the Application

```bash
python app.py
```

### 4. Access Occurrence Dashboard

Navigate to: **http://localhost:5000/occurrence/**

## 📊 Features

### 1. **Upload Occurrence Data**
- Upload Parquet, CSV, or Excel files
- Automatic validation and cleaning
- Converts to compressed GeoParquet (with spatial indexing)
- Supports versioning

### 2. **Query Occurrences**
- Filter by species, location (bbox), date range
- Spatial queries without loading entire dataset
- Lightning-fast analytical queries

### 3. **Version Management**
- Track data evolution
- Compare versions
- Rollback to previous versions
- View change history

### 4. **Interactive Maps**
- Visualize occurrences on Leaflet maps
- Cluster markers for performance
- Filter and search capabilities

### 5. **Export Data**
- Download as GeoJSON
- Export to RDF/Turtle for Fuseki integration
- Query via REST API

## 📝 Usage Examples

### Web Interface

1. **Upload Data**:
   - Go to `/occurrence/upload`
   - Select Parquet, CSV, or Excel file with columns: `latitude`, `longitude`, `species`
   - Specify version (e.g., `v1.0.0`)
   - Add description
   - Click "Convert to GeoParquet & Upload"

2. **View Data**:
   - Dashboard: `/occurrence/`
   - Map View: `/occurrence/map/<version>`
   - Version Details: `/occurrence/version/<version>`

3. **Compare Versions**:
   - Go to `/occurrence/compare`
   - Select two versions
   - View differences

### Python API

```python
from occurrence_manager import OccurrenceDataManager

# Initialize manager
manager = OccurrenceDataManager(
    storage_path='data/occurrences',
    s3_bucket='s3://treekipedia-occurrences'  # Optional
)

# Upload new data (supports .parquet, .csv, .xlsx, .xls)
parquet_path, stats = manager.convert_to_geoparquet(
    input_file='my_data.parquet',  # Can also be .csv, .xlsx, or .xls
    version='v1.0.0',
    lat_col='latitude',
    lon_col='longitude',
    species_col='species',
    metadata={'description': 'Initial upload from parquet'}
)

print(f"Uploaded {stats['record_count']} records")
print(f"File size: {stats['file_size_mb']:.2f} MB")

# Query data
results = manager.query_occurrences(
    version='v1.0.0',
    species='Adansonia digitata',
    bbox=[-20, 30, -10, 40],  # [min_lon, min_lat, max_lon, max_lat]
    limit=1000
)

print(f"Found {len(results)} occurrences")

# Compare versions
comparison = manager.compare_versions('v1.0.0', 'v1.1.0')
print(f"New occurrences: {comparison['record_diff']}")
print(f"New species: {comparison['new_species']}")

# Get statistics
stats = manager.get_statistics('v1.0.0')
print(f"Total occurrences: {stats['total_records']}")
print(f"Species count: {stats['species_count']}")
print(f"Geographic extent: {stats['bbox']}")
```

### DuckDB Direct Queries

```python
import duckdb

conn = duckdb.connect()
conn.execute("INSTALL spatial")
conn.execute("LOAD spatial")

# Query GeoParquet directly
results = conn.execute("""
    SELECT
        species,
        COUNT(*) as occurrence_count,
        MIN(ST_Y(geometry)) as min_lat,
        MAX(ST_Y(geometry)) as max_lat,
        AVG(ST_Y(geometry)) as center_lat,
        AVG(ST_X(geometry)) as center_lon
    FROM read_parquet('data/occurrences/v1.0.0/*.parquet')
    GROUP BY species
    HAVING occurrence_count > 10
    ORDER BY occurrence_count DESC
""").df()

print(results)
```

### REST API Endpoints

```bash
# List all versions
curl http://localhost:5000/occurrence/api/versions

# Query occurrences
curl -X POST http://localhost:5000/occurrence/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "version": "v1.0.0",
    "species": "Adansonia digitata",
    "limit": 100
  }'

# Get statistics
curl http://localhost:5000/occurrence/api/statistics/v1.0.0

# Compare versions
curl -X POST http://localhost:5000/occurrence/api/compare \
  -H "Content-Type: application/json" \
  -d '{
    "version1": "v1.0.0",
    "version2": "v1.1.0"
  }'

# Cleanup old versions (keep latest 5)
curl -X POST http://localhost:5000/occurrence/api/cleanup \
  -H "Content-Type: application/json" \
  -d '{"keep_latest": 5}'
```

## 📁 File Structure

```
data/occurrences/
├── versions.json                 # Version registry
├── v1.0.0/
│   └── occurrences_v1.0.0.parquet
├── v1.1.0/
│   └── occurrences_v1.1.0.parquet
└── v2.0.0/
    └── occurrences_v2.0.0.parquet
```

## 📋 Input File Format

Your occurrence data file (Parquet, CSV, or Excel) should have these columns:

**Required:**
- `latitude` (or custom name): Decimal degrees (-90 to 90)
- `longitude` (or custom name): Decimal degrees (-180 to 180)
- `species` (or custom name): Scientific name

**Optional but recommended:**
- `date` or `observed_date`: Observation date (ISO format)
- `observer`: Observer name/ID
- `locality`: Location name
- `habitat`: Habitat type
- `elevation`: Elevation in meters
- Any other fields you want to track

**Example CSV:**
```csv
species,latitude,longitude,date,observer,locality
Adansonia digitata,-15.7833,35.0167,2024-01-15,Field Team A,Liwonde National Park
Adansonia grandidieri,-20.2500,44.4167,2024-01-20,Researcher B,Morondava
Adansonia za,-18.9167,47.5167,2024-02-01,Team C,Ankarafantsika
```

**Parquet Format:**
The system now supports standard Parquet files (optimized for large datasets). Simply ensure your parquet file contains the required columns (latitude, longitude, species). Parquet is recommended for:
- Large datasets (>100K records)
- Faster upload times (10x compression)
- Reduced storage costs
- Better performance for analytical queries

## 🔄 Integration with InsightVersion System

The occurrence data system integrates seamlessly with your existing AI insight versioning:

```python
from occurrence_manager import OccurrenceDataManager
from your_insight_system import InsightVersion

manager = OccurrenceDataManager()

# Upload occurrence data (from parquet file)
parquet_path, stats = manager.convert_to_geoparquet(
    input_file='occurrences.parquet',  # Can be .parquet, .csv, .xlsx, or .xls
    version='v1.0.0'
)

# Link to insight versioning
insight_version = InsightVersion()
insight_version.create_new_version(
    insight={
        'occurrence_count': stats['record_count'],
        'species_count': stats['species_count'],
        'data_source': 'field_observations',
        'parquet_path': parquet_path
    },
    reason="new_occurrence_upload",
    data_version="v1.0.0",
    model_version=None  # No AI extraction for raw occurrence data
)

# Later: Extract AI insights from occurrence data
df = manager.query_occurrences(version='v1.0.0', species='Adansonia digitata')

for idx, occurrence in df.iterrows():
    # Use AI model to extract insights
    ai_insights = your_ai_model.extract(
        location=occurrence['locality'],
        coordinates=(occurrence['latitude'], occurrence['longitude'])
    )

    # Version the AI insights
    insight_version.create_new_version(
        insight=ai_insights,
        reason="ai_extraction_from_occurrence",
        data_version="v1.0.0",
        data_source=parquet_path
    )
```

## 🗺️ Exporting to Fuseki

```python
# Export to RDF
manager = OccurrenceDataManager()
rdf_file = manager.export_to_rdf('v1.0.0', 'output.ttl')

# Or via web interface
# Download from: /occurrence/export/v1.0.0/rdf

# Then import to Fuseki using your existing pipeline
```

## 🐛 Troubleshooting

### Issue: DuckDB spatial extension not found
```bash
# Solution: Install spatial extension manually
python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL spatial')"
```

### Issue: GeoPandas installation fails
```bash
# Solution: Install system dependencies first (Ubuntu/Debian)
sudo apt-get install gdal-bin libgdal-dev
pip install gdal
pip install geopandas
```

### Issue: S3 access denied
```bash
# Solution: Check AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Test connection
python -c "import boto3; s3 = boto3.client('s3'); print(s3.list_buckets())"
```

### Issue: Out of memory errors
```python
# Solution: Use limit parameter for large datasets
manager.query_occurrences(version='v1.0.0', limit=10000)

# Or query with filters to reduce data
manager.query_occurrences(
    version='v1.0.0',
    bbox=[-20, 30, -10, 40],  # Smaller geographic area
    limit=50000
)
```

## 📊 Performance Tips

1. **Use filters**: Always filter by species, bbox, or date when possible
2. **Limit results**: Use `limit` parameter for large queries
3. **Batch operations**: Process data in batches for large uploads
4. **Cloud storage**: Store older versions in S3, keep recent ones local
5. **Compression**: GeoParquet automatically compresses (10x reduction!)

## 🔐 Security Best Practices

1. **Never commit AWS keys**: Use environment variables
2. **Validate inputs**: System validates coordinates automatically
3. **Access control**: Add authentication for production deployments
4. **Version cleanup**: Regularly cleanup old versions to save space

## 📈 Scaling Recommendations

**For small datasets (<1M occurrences):**
- Local storage is fine
- No S3 needed
- Query directly from files

**For medium datasets (1M-10M occurrences):**
- Consider S3 for older versions
- Keep recent versions local
- Use bbox filters for queries

**For large datasets (>10M occurrences):**
- Store all versions in S3
- Use DuckDB's httpfs to query S3 directly
- Implement data partitioning by species/region
- Consider dedicated DuckDB server

## 🤝 Contributing

To extend the occurrence data system:

1. Add new export formats in `occurrence_manager.py`
2. Add new query filters in `routes_occurrence.py`
3. Customize map visualizations in templates
4. Add new statistics/analytics endpoints

## 📚 Additional Resources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [GeoParquet Specification](https://geoparquet.org/)
- [GeoPandas User Guide](https://geopandas.org/)
- [Leaflet.js Documentation](https://leafletjs.com/)

## 🎉 Success!

You now have a production-ready occurrence data system with:
- ✅ Efficient storage (10x compression)
- ✅ Fast queries (DuckDB analytics)
- ✅ Version control (track data evolution)
- ✅ Cloud-ready (S3 integration)
- ✅ Interactive maps (Leaflet visualizations)
- ✅ REST API (programmatic access)
- ✅ RDF export (Fuseki integration)

Start uploading your occurrence data and enjoy the performance benefits! 🚀
