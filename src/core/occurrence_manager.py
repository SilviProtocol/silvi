# =============================================================================
# occurrence_manager.py - GeoParquet + DuckDB Occurrence Data Management
# =============================================================================

import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from src.core.config import logger

class OccurrenceDataManager:
    """
    Manages biodiversity occurrence data using GeoParquet and DuckDB.

    Features:
    - CSV/Excel → GeoParquet conversion
    - Cloud storage (S3/local) with versioning
    - Efficient spatial queries
    - Version comparison and diffs
    - Integration with existing InsightVersion system
    """

    def __init__(self, storage_path='data/occurrences', s3_bucket=None):
        """
        Initialize occurrence data manager.

        Args:
            storage_path: Local storage path for GeoParquet files
            s3_bucket: Optional S3 bucket name (e.g., 's3://treekipedia-occurrences')
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.s3_bucket = s3_bucket
        self.use_s3 = s3_bucket is not None

        # Initialize DuckDB connection
        self.conn = duckdb.connect(':memory:')  # In-memory for speed

        # Install and load required extensions
        self._setup_duckdb()

        # Version registry
        self.version_file = self.storage_path / 'versions.json'
        self.versions = self._load_versions()

        logger.info(f"OccurrenceDataManager initialized (S3: {self.use_s3})")

    def _setup_duckdb(self):
        """Setup DuckDB with required extensions"""
        try:
            # Install spatial extension for geospatial queries
            self.conn.execute("INSTALL spatial")
            self.conn.execute("LOAD spatial")

            # Install httpfs for S3/cloud access
            if self.use_s3:
                self.conn.execute("INSTALL httpfs")
                self.conn.execute("LOAD httpfs")

                # Configure S3 credentials (from environment)
                aws_key = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
                aws_region = os.getenv('AWS_REGION', 'us-east-1')

                if aws_key and aws_secret:
                    self.conn.execute(f"SET s3_region='{aws_region}'")
                    self.conn.execute(f"SET s3_access_key_id='{aws_key}'")
                    self.conn.execute(f"SET s3_secret_access_key='{aws_secret}'")
                    logger.info("S3 credentials configured")
                else:
                    logger.warning("S3 credentials not found in environment")

            logger.info("DuckDB extensions loaded successfully")

        except Exception as e:
            logger.error(f"Error setting up DuckDB: {e}")
            raise

    def _load_versions(self) -> Dict:
        """Load version registry from disk"""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_versions(self):
        """Save version registry to disk"""
        with open(self.version_file, 'w') as f:
            json.dump(self.versions, f, indent=2)

    def convert_to_geoparquet(self,
                              input_file: str,
                              version: str,
                              lat_col: str = 'latitude',
                              lon_col: str = 'longitude',
                              species_col: str = 'species',
                              metadata: Optional[Dict] = None) -> Tuple[str, Dict]:
        """
        Convert Parquet/CSV/Excel to GeoParquet with versioning.

        Args:
            input_file: Path to Parquet, CSV, or Excel file
            version: Version identifier (e.g., 'v1.0.0')
            lat_col: Name of latitude column
            lon_col: Name of longitude column
            species_col: Name of species column
            metadata: Optional metadata dictionary

        Returns:
            Tuple of (parquet_path, stats_dict)
        """
        try:
            logger.info(f"Converting {input_file} to GeoParquet version {version}")

            # Read input file
            if input_file.endswith('.parquet'):
                df = pd.read_parquet(input_file)
            elif input_file.endswith('.csv'):
                df = pd.read_csv(input_file)
            elif input_file.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(input_file)
            else:
                raise ValueError(f"Unsupported file format: {input_file}")

            # Validate required columns
            if lat_col not in df.columns or lon_col not in df.columns:
                raise ValueError(f"Missing required columns: {lat_col}, {lon_col}")

            # Remove rows with missing coordinates
            original_count = len(df)
            df = df.dropna(subset=[lat_col, lon_col])
            dropped_count = original_count - len(df)

            if dropped_count > 0:
                logger.warning(f"Dropped {dropped_count} rows with missing coordinates")

            # Validate coordinate ranges
            df = df[
                (df[lat_col] >= -90) & (df[lat_col] <= 90) &
                (df[lon_col] >= -180) & (df[lon_col] <= 180)
            ]

            # Convert to GeoDataFrame
            geometry = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')

            # Add metadata columns
            gdf['version'] = version
            gdf['upload_timestamp'] = datetime.utcnow().isoformat()
            gdf['data_hash'] = self._calculate_hash(df)

            # Generate output path
            version_dir = self.storage_path / version
            version_dir.mkdir(parents=True, exist_ok=True)

            parquet_filename = f"occurrences_{version}.parquet"
            parquet_path = version_dir / parquet_filename

            # Write to GeoParquet
            gdf.to_parquet(parquet_path, compression='snappy')

            # Calculate statistics
            stats = {
                'version': version,
                'file_path': str(parquet_path),
                'record_count': len(gdf),
                'species_count': gdf[species_col].nunique() if species_col in gdf.columns else 0,
                'date_range': self._get_date_range(gdf),
                'bbox': self._calculate_bbox(gdf),
                'file_size_mb': os.path.getsize(parquet_path) / (1024 * 1024),
                'created_at': datetime.utcnow().isoformat(),
                'metadata': metadata or {},
                'columns': list(gdf.columns),
                'data_hash': gdf['data_hash'].iloc[0],
                'species_col': species_col,
                'lat_col': lat_col,
                'lon_col': lon_col
            }

            # Register version
            self.versions[version] = stats
            self._save_versions()

            # Upload to S3 if configured
            if self.use_s3:
                s3_path = self._upload_to_s3(parquet_path, version)
                stats['s3_path'] = s3_path
                self._save_versions()

            logger.info(f"GeoParquet created: {parquet_path} ({stats['file_size_mb']:.2f} MB)")
            logger.info(f"  Records: {stats['record_count']}, Species: {stats['species_count']}")

            return str(parquet_path), stats

        except Exception as e:
            logger.error(f"Error converting to GeoParquet: {e}", exc_info=True)
            raise

    def _calculate_hash(self, df: pd.DataFrame) -> str:
        """Calculate hash of dataframe content for change detection"""
        content = df.to_csv(index=False).encode()
        return hashlib.sha256(content).hexdigest()[:16]

    def _detect_column_from_file(self, file_path: str, column_patterns: List[str]) -> Optional[str]:
        """
        Auto-detect column name from parquet file by trying common patterns.

        Args:
            file_path: Path to parquet file
            column_patterns: List of possible column name patterns to try

        Returns:
            Detected column name or None
        """
        try:
            # Use DuckDB to read just the schema
            schema_query = f"DESCRIBE SELECT * FROM read_parquet('{file_path}') LIMIT 0"
            schema_df = self.conn.execute(schema_query).df()
            available_columns = schema_df['column_name'].tolist()

            # Try each pattern (case-insensitive)
            columns_lower = {col.lower(): col for col in available_columns}

            for pattern in column_patterns:
                if pattern.lower() in columns_lower:
                    detected = columns_lower[pattern.lower()]
                    logger.info(f"Auto-detected column '{detected}' for pattern '{pattern}'")
                    return detected

            logger.warning(f"Could not find matching column for patterns {column_patterns} in {available_columns}")
            return None
        except Exception as e:
            logger.warning(f"Could not auto-detect column from file: {e}")
            return None

    def _get_date_range(self, gdf: gpd.GeoDataFrame) -> Optional[Dict]:
        """Extract date range from common date columns"""
        date_columns = ['date', 'observed_date', 'observation_date', 'eventDate']

        for col in date_columns:
            if col in gdf.columns:
                try:
                    dates = pd.to_datetime(gdf[col], errors='coerce')
                    dates = dates.dropna()
                    if len(dates) > 0:
                        return {
                            'min': dates.min().isoformat(),
                            'max': dates.max().isoformat()
                        }
                except:
                    continue

        return None

    def _calculate_bbox(self, gdf: gpd.GeoDataFrame) -> List[float]:
        """Calculate bounding box [min_lon, min_lat, max_lon, max_lat]"""
        bounds = gdf.total_bounds
        return [float(x) for x in bounds]  # [minx, miny, maxx, maxy]

    def _upload_to_s3(self, local_path: Path, version: str) -> str:
        """Upload GeoParquet to S3"""
        try:
            s3_key = f"{version}/{local_path.name}"
            s3_path = f"{self.s3_bucket}/{s3_key}"

            # Use DuckDB to copy to S3
            self.conn.execute(f"""
                COPY (SELECT * FROM read_parquet('{local_path}'))
                TO '{s3_path}' (FORMAT PARQUET, COMPRESSION 'snappy')
            """)

            logger.info(f"Uploaded to S3: {s3_path}")
            return s3_path

        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return ""

    def query_occurrences(self,
                          version: Optional[str] = None,
                          species: Optional[str] = None,
                          bbox: Optional[List[float]] = None,
                          date_range: Optional[Tuple[str, str]] = None,
                          limit: Optional[int] = None) -> pd.DataFrame:
        """
        Query occurrence data with filters.

        Args:
            version: Specific version to query (default: latest)
            species: Filter by species name
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
            date_range: Tuple of (start_date, end_date)
            limit: Maximum number of records

        Returns:
            DataFrame with filtered results
        """
        try:
            # Determine which version to query
            if version is None:
                version = self._get_latest_version()

            if version not in self.versions:
                raise ValueError(f"Version {version} not found")

            # Get file path (S3 or local)
            if self.use_s3 and 's3_path' in self.versions[version]:
                file_path = self.versions[version]['s3_path']
            else:
                file_path = self.versions[version]['file_path']

            # Get species column name with fallback auto-detection
            species_col = self.versions[version].get('species_col')
            if not species_col:
                species_patterns = ['species', 'scientificname', 'scientific_name', 'species_scientific_name',
                                   'taxon', 'taxonname', 'taxon_name', 'organism']
                species_col = self._detect_column_from_file(file_path, species_patterns)
                if not species_col:
                    species_col = 'species'  # Last resort default

            # Build query
            query = f"SELECT * FROM read_parquet('{file_path}')"

            filters = []

            if species:
                filters.append(f'"{species_col}" ILIKE \'%{species}%\'')

            if bbox:
                min_lon, min_lat, max_lon, max_lat = bbox
                filters.append(f"ST_X(geometry) BETWEEN {min_lon} AND {max_lon}")
                filters.append(f"ST_Y(geometry) BETWEEN {min_lat} AND {max_lat}")

            if date_range and len(date_range) == 2:
                start, end = date_range
                # Try common date column names
                for col in ['date', 'observed_date', 'eventDate']:
                    if col in self.versions[version]['columns']:
                        filters.append(f"{col} BETWEEN '{start}' AND '{end}'")
                        break

            if filters:
                query += " WHERE " + " AND ".join(filters)

            if limit:
                query += f" LIMIT {limit}"

            # Execute query
            result = self.conn.execute(query).df()

            logger.info(f"Query returned {len(result)} records from version {version}")
            return result

        except Exception as e:
            logger.error(f"Error querying occurrences: {e}", exc_info=True)
            raise

    def compare_versions(self, v1: str, v2: str) -> Dict:
        """
        Compare two data versions and return statistics.

        Args:
            v1: First version identifier
            v2: Second version identifier

        Returns:
            Dictionary with comparison statistics
        """
        try:
            logger.info(f"Comparing versions {v1} vs {v2}")

            # Get file paths and species column names
            v1_path = self.versions[v1]['file_path']
            v2_path = self.versions[v2]['file_path']

            # Get species column names with fallback auto-detection
            v1_species_col = self.versions[v1].get('species_col')
            if not v1_species_col:
                species_patterns = ['species', 'scientificname', 'scientific_name', 'species_scientific_name',
                                   'taxon', 'taxonname', 'taxon_name', 'organism']
                v1_species_col = self._detect_column_from_file(v1_path, species_patterns) or 'species'

            v2_species_col = self.versions[v2].get('species_col')
            if not v2_species_col:
                species_patterns = ['species', 'scientificname', 'scientific_name', 'species_scientific_name',
                                   'taxon', 'taxonname', 'taxon_name', 'organism']
                v2_species_col = self._detect_column_from_file(v2_path, species_patterns) or 'species'

            # Compare record counts by species
            comparison_query = f"""
            WITH v1_data AS (
                SELECT "{v1_species_col}" as species, COUNT(*) as count
                FROM read_parquet('{v1_path}')
                GROUP BY "{v1_species_col}"
            ),
            v2_data AS (
                SELECT "{v2_species_col}" as species, COUNT(*) as count
                FROM read_parquet('{v2_path}')
                GROUP BY "{v2_species_col}"
            )
            SELECT
                COALESCE(v1.species, v2.species) as species,
                COALESCE(v1.count, 0) as v1_count,
                COALESCE(v2.count, 0) as v2_count,
                COALESCE(v2.count, 0) - COALESCE(v1.count, 0) as diff
            FROM v1_data v1
            FULL OUTER JOIN v2_data v2 ON v1.species = v2.species
            ORDER BY ABS(COALESCE(v2.count, 0) - COALESCE(v1.count, 0)) DESC
            """

            species_diff = self.conn.execute(comparison_query).df()

            # Overall statistics
            v1_total = self.versions[v1]['record_count']
            v2_total = self.versions[v2]['record_count']

            new_species = len(species_diff[species_diff['v1_count'] == 0])
            removed_species = len(species_diff[species_diff['v2_count'] == 0])

            comparison = {
                'v1': v1,
                'v2': v2,
                'v1_total_records': v1_total,
                'v2_total_records': v2_total,
                'record_diff': v2_total - v1_total,
                'new_species': new_species,
                'removed_species': removed_species,
                'species_changes': species_diff.to_dict('records'),
                'comparison_date': datetime.utcnow().isoformat()
            }

            logger.info(f"Version comparison: {v2_total - v1_total:+d} records, "
                       f"+{new_species} species, -{removed_species} species")

            return comparison

        except Exception as e:
            logger.error(f"Error comparing versions: {e}", exc_info=True)
            raise

    def get_statistics(self, version: Optional[str] = None) -> Dict:
        """
        Get comprehensive statistics for a version.

        Args:
            version: Version to analyze (default: latest)

        Returns:
            Dictionary with statistics
        """
        try:
            if version is None:
                version = self._get_latest_version()

            file_path = self.versions[version]['file_path']
            species_col = self.versions[version].get('species_col')

            # Fallback: auto-detect species column if not in metadata
            if not species_col:
                species_patterns = ['species', 'scientificname', 'scientific_name', 'species_scientific_name',
                                   'taxon', 'taxonname', 'taxon_name', 'organism']
                species_col = self._detect_column_from_file(file_path, species_patterns)
                if not species_col:
                    species_col = 'species'  # Last resort default

            stats_query = f"""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT "{species_col}") as species_count,
                MIN(ST_Y(geometry)) as min_lat,
                MAX(ST_Y(geometry)) as max_lat,
                MIN(ST_X(geometry)) as min_lon,
                MAX(ST_X(geometry)) as max_lon,
                AVG(ST_Y(geometry)) as center_lat,
                AVG(ST_X(geometry)) as center_lon
            FROM read_parquet('{file_path}')
            """

            stats = self.conn.execute(stats_query).df().to_dict('records')[0]

            # Top species
            top_species_query = f"""
            SELECT "{species_col}" as species, COUNT(*) as occurrence_count
            FROM read_parquet('{file_path}')
            GROUP BY "{species_col}"
            ORDER BY occurrence_count DESC
            LIMIT 10
            """

            stats['top_species'] = self.conn.execute(top_species_query).df().to_dict('records')

            return stats

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}", exc_info=True)
            raise

    def _get_latest_version(self) -> str:
        """Get the latest version identifier"""
        if not self.versions:
            raise ValueError("No versions available")

        # Sort versions by creation date
        sorted_versions = sorted(
            self.versions.items(),
            key=lambda x: x[1]['created_at'],
            reverse=True
        )

        return sorted_versions[0][0]

    def list_versions(self) -> List[Dict]:
        """List all available versions with metadata"""
        return [
            {
                'version': version,
                **metadata
            }
            for version, metadata in sorted(
                self.versions.items(),
                key=lambda x: x[1]['created_at'],
                reverse=True
            )
        ]

    def export_to_rdf(self, version: str, output_path: str) -> str:
        """
        Export occurrence data to RDF/Turtle for Fuseki.

        Args:
            version: Version to export
            output_path: Path for RDF output file

        Returns:
            Path to generated RDF file
        """
        try:
            from rdflib import Graph, Literal, Namespace, URIRef
            from rdflib.namespace import RDF, RDFS, XSD

            logger.info(f"Exporting version {version} to RDF")

            file_path = self.versions[version]['file_path']

            # Get column names for this version with fallback auto-detection
            species_col = self.versions[version].get('species_col')
            if not species_col:
                species_patterns = ['species', 'scientificname', 'scientific_name', 'species_scientific_name',
                                   'taxon', 'taxonname', 'taxon_name', 'organism']
                species_col = self._detect_column_from_file(file_path, species_patterns) or 'species'

            lat_col = self.versions[version].get('lat_col')
            if not lat_col:
                lat_patterns = ['latitude', 'lat', 'decimallatitude', 'decimal_latitude', 'y']
                lat_col = self._detect_column_from_file(file_path, lat_patterns) or 'latitude'

            lon_col = self.versions[version].get('lon_col')
            if not lon_col:
                lon_patterns = ['longitude', 'lon', 'lng', 'long', 'decimallongitude', 'decimal_longitude', 'x']
                lon_col = self._detect_column_from_file(file_path, lon_patterns) or 'longitude'

            # Query data
            df = self.query_occurrences(version=version)

            # Create RDF graph
            g = Graph()

            # Define namespaces
            TK = Namespace("http://treekipedia.org/ontology/")
            GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
            DWC = Namespace("http://rs.tdwg.org/dwc/terms/")

            g.bind("tk", TK)
            g.bind("geo", GEO)
            g.bind("dwc", DWC)

            # Add occurrences
            for idx, row in df.iterrows():
                occurrence_uri = URIRef(f"http://treekipedia.org/occurrence/{row.get('id', idx)}")

                g.add((occurrence_uri, RDF.type, DWC.Occurrence))

                if species_col in row:
                    g.add((occurrence_uri, DWC.scientificName, Literal(row[species_col])))

                # Geospatial data
                if lat_col in row and lon_col in row:
                    g.add((occurrence_uri, GEO.lat, Literal(row[lat_col], datatype=XSD.decimal)))
                    g.add((occurrence_uri, GEO.long, Literal(row[lon_col], datatype=XSD.decimal)))

                # Date
                if 'date' in row or 'observed_date' in row:
                    date_col = 'date' if 'date' in row else 'observed_date'
                    g.add((occurrence_uri, DWC.eventDate, Literal(row[date_col], datatype=XSD.date)))

            # Serialize to file
            g.serialize(destination=output_path, format='turtle')

            logger.info(f"RDF exported to {output_path} ({len(g)} triples)")

            return output_path

        except Exception as e:
            logger.error(f"Error exporting to RDF: {e}", exc_info=True)
            raise

    def cleanup_old_versions(self, keep_latest: int = 5):
        """
        Remove old versions, keeping only the latest N versions.

        Args:
            keep_latest: Number of recent versions to keep
        """
        try:
            versions_list = self.list_versions()

            if len(versions_list) <= keep_latest:
                logger.info(f"Only {len(versions_list)} versions, nothing to cleanup")
                return

            versions_to_remove = versions_list[keep_latest:]

            for version_info in versions_to_remove:
                version = version_info['version']
                file_path = Path(version_info['file_path'])

                # Remove local file
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Removed {file_path}")

                # Remove version entry
                del self.versions[version]

            self._save_versions()
            logger.info(f"Cleaned up {len(versions_to_remove)} old versions")

        except Exception as e:
            logger.error(f"Error cleaning up versions: {e}", exc_info=True)
            raise
