
# =============================================================================
# routes_occurrence.py - Occurrence Data Routes
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from occurrence_manager import OccurrenceDataManager
from config import logger
import os
import json
from datetime import datetime

# Create blueprint
occurrence_bp = Blueprint('occurrence', __name__, url_prefix='/occurrence')

# Global occurrence manager instance
occurrence_manager = None


def init_occurrence_manager(app):
    """Initialize occurrence manager with app config"""
    global occurrence_manager

    storage_path = app.config.get('OCCURRENCE_STORAGE_PATH', 'data/occurrences')
    s3_bucket = app.config.get('OCCURRENCE_S3_BUCKET')

    occurrence_manager = OccurrenceDataManager(
        storage_path=storage_path,
        s3_bucket=s3_bucket
    )

    logger.info("Occurrence data manager initialized")
    return occurrence_manager


@occurrence_bp.route('/')
def index():
    """Occurrence data dashboard"""
    try:
        if occurrence_manager is None:
            flash('Occurrence data system not initialized', 'error')
            return redirect(url_for('main.index'))

        # Get all versions
        versions = occurrence_manager.list_versions()

        # Get latest version statistics
        latest_stats = None
        if versions:
            latest_version = versions[0]['version']
            latest_stats = occurrence_manager.get_statistics(latest_version)
            latest_stats['version'] = latest_version

        return render_template('occurrence_dashboard.html',
                             versions=versions,
                             latest_stats=latest_stats,
                             total_versions=len(versions))

    except Exception as e:
        logger.error(f"Error loading occurrence dashboard: {e}", exc_info=True)
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@occurrence_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload occurrence data"""
    if request.method == 'GET':
        return render_template('occurrence_upload.html')

    try:
        # Get uploaded file
        if 'occurrence_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('occurrence.upload'))

        file = request.files['occurrence_file']

        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('occurrence.upload'))

        # Get form parameters
        version = request.form.get('version', '').strip()
        lat_col = request.form.get('lat_col', 'latitude')
        lon_col = request.form.get('lon_col', 'longitude')
        species_col = request.form.get('species_col', 'species')
        description = request.form.get('description', '')

        # Validate version format
        if not version:
            flash('Version identifier is required', 'error')
            return redirect(url_for('occurrence.upload'))

        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join('/tmp', filename)
        file.save(temp_path)

        # Convert to GeoParquet
        metadata = {
            'description': description,
            'uploaded_by': request.form.get('uploaded_by', 'unknown'),
            'source_filename': filename
        }

        parquet_path, stats = occurrence_manager.convert_to_geoparquet(
            input_file=temp_path,
            version=version,
            lat_col=lat_col,
            lon_col=lon_col,
            species_col=species_col,
            metadata=metadata
        )

        # Clean up temp file
        os.remove(temp_path)

        # Log success
        logger.info(f"Occurrence data uploaded: version {version}, "
                   f"{stats['record_count']} records, {stats['species_count']} species")

        flash(f"Successfully uploaded {stats['record_count']} occurrences (version {version})", 'success')

        return render_template('occurrence_success.html',
                             version=version,
                             stats=stats)

    except Exception as e:
        logger.error(f"Error uploading occurrence data: {e}", exc_info=True)
        flash(f'Upload failed: {str(e)}', 'error')
        return redirect(url_for('occurrence.upload'))


@occurrence_bp.route('/api/query', methods=['POST'])
def api_query():
    """API endpoint to query occurrence data"""
    try:
        data = request.get_json()

        version = data.get('version')
        species = data.get('species')
        bbox = data.get('bbox')  # [min_lon, min_lat, max_lon, max_lat]
        date_range = data.get('date_range')  # [start, end]
        limit = data.get('limit', 1000)

        # Query data
        results = occurrence_manager.query_occurrences(
            version=version,
            species=species,
            bbox=bbox,
            date_range=tuple(date_range) if date_range else None,
            limit=limit
        )

        # Convert to GeoJSON for mapping
        geojson = {
            'type': 'FeatureCollection',
            'features': []
        }

        for idx, row in results.iterrows():
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        row.get('longitude', 0),
                        row.get('latitude', 0)
                    ]
                },
                'properties': {
                    'species': row.get('species', 'Unknown'),
                    'date': str(row.get('date', row.get('observed_date', ''))),
                    **{k: v for k, v in row.items() if k not in ['geometry', 'longitude', 'latitude']}
                }
            }
            geojson['features'].append(feature)

        return jsonify({
            'success': True,
            'record_count': len(results),
            'geojson': geojson
        })

    except Exception as e:
        logger.error(f"Error querying occurrences: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@occurrence_bp.route('/api/statistics/<version>')
def api_statistics(version):
    """Get statistics for a specific version"""
    try:
        stats = occurrence_manager.get_statistics(version)

        return jsonify({
            'success': True,
            'version': version,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@occurrence_bp.route('/api/compare', methods=['POST'])
def api_compare():
    """Compare two versions"""
    try:
        data = request.get_json()

        v1 = data.get('version1')
        v2 = data.get('version2')

        if not v1 or not v2:
            return jsonify({
                'success': False,
                'error': 'Both version1 and version2 are required'
            }), 400

        comparison = occurrence_manager.compare_versions(v1, v2)

        return jsonify({
            'success': True,
            'comparison': comparison
        })

    except Exception as e:
        logger.error(f"Error comparing versions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@occurrence_bp.route('/version/<version>')
def version_detail(version):
    """View details for a specific version"""
    try:
        # Get version info
        versions = occurrence_manager.list_versions()
        version_info = next((v for v in versions if v['version'] == version), None)

        if not version_info:
            flash(f'Version {version} not found', 'error')
            return redirect(url_for('occurrence.index'))

        # Get statistics
        stats = occurrence_manager.get_statistics(version)

        # Sample data (first 100 records)
        sample = occurrence_manager.query_occurrences(version=version, limit=100)

        return render_template('occurrence_version.html',
                             version=version,
                             version_info=version_info,
                             stats=stats,
                             sample=sample.to_dict('records'))

    except Exception as e:
        logger.error(f"Error loading version detail: {e}", exc_info=True)
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('occurrence.index'))


@occurrence_bp.route('/compare')
def compare():
    """Compare versions interface"""
    try:
        versions = occurrence_manager.list_versions()

        # Get comparison if versions specified
        v1 = request.args.get('v1')
        v2 = request.args.get('v2')

        comparison = None
        if v1 and v2:
            comparison = occurrence_manager.compare_versions(v1, v2)

        return render_template('occurrence_compare.html',
                             versions=versions,
                             comparison=comparison,
                             v1=v1,
                             v2=v2)

    except Exception as e:
        logger.error(f"Error loading comparison: {e}", exc_info=True)
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('occurrence.index'))


@occurrence_bp.route('/export/<version>/rdf')
def export_rdf(version):
    """Export occurrence data to RDF"""
    try:
        # Generate RDF file
        output_path = f'/tmp/occurrences_{version}.ttl'
        rdf_file = occurrence_manager.export_to_rdf(version, output_path)

        # Send file
        return send_file(
            rdf_file,
            as_attachment=True,
            download_name=f'occurrences_{version}.ttl',
            mimetype='text/turtle'
        )

    except Exception as e:
        logger.error(f"Error exporting RDF: {e}", exc_info=True)
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('occurrence.version_detail', version=version))


@occurrence_bp.route('/api/versions')
def api_versions():
    """List all versions (API endpoint)"""
    try:
        versions = occurrence_manager.list_versions()

        return jsonify({
            'success': True,
            'versions': versions,
            'count': len(versions)
        })

    except Exception as e:
        logger.error(f"Error listing versions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@occurrence_bp.route('/map/<version>')
def map_view(version):
    """Interactive map view of occurrence data"""
    try:
        # Get version info
        versions = occurrence_manager.list_versions()
        version_info = next((v for v in versions if v['version'] == version), None)

        if not version_info:
            flash(f'Version {version} not found', 'error')
            return redirect(url_for('occurrence.index'))

        # Get bbox for map centering
        bbox = version_info.get('bbox', [-180, -90, 180, 90])
        center_lat = (bbox[1] + bbox[3]) / 2
        center_lon = (bbox[0] + bbox[2]) / 2

        return render_template('occurrence_map.html',
                             version=version,
                             version_info=version_info,
                             center_lat=center_lat,
                             center_lon=center_lon,
                             bbox=bbox)

    except Exception as e:
        logger.error(f"Error loading map: {e}", exc_info=True)
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('occurrence.index'))


@occurrence_bp.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    """Cleanup old versions (keep latest N)"""
    try:
        data = request.get_json()
        keep_latest = data.get('keep_latest', 5)

        occurrence_manager.cleanup_old_versions(keep_latest=keep_latest)

        return jsonify({
            'success': True,
            'message': f'Cleaned up old versions, kept latest {keep_latest}'
        })

    except Exception as e:
        logger.error(f"Error cleaning up versions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
