"""
AlphaEarth Location-to-Species Prediction Service
Flask microservice that samples AlphaEarth embeddings at clicked locations
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import ee
import time
import json

# Configuration
PROJECT = 'treekipedia-476404'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
CURRENT_YEAR = 2024

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Initialize Earth Engine
try:
    ee.Initialize(project=PROJECT)
    print(f"✅ Earth Engine initialized (project: {PROJECT})")
except Exception as e:
    print(f"❌ Earth Engine initialization failed: {e}")
    raise


def get_alphaearth_mosaic(year: int = CURRENT_YEAR) -> ee.Image:
    """
    Get AlphaEarth global mosaic for a specific year.

    Uses .mosaic() to combine ~11K tiles into single queryable image.
    """
    col = ee.ImageCollection(AE_COLLECTION).filterDate(
        f'{year}-01-01', f'{year}-12-31'
    )
    return col.mosaic()


def sample_location(lat: float, lon: float, year: int = CURRENT_YEAR, radius: int = 10) -> dict:
    """
    Sample AlphaEarth embedding at a specific location.

    Args:
        lat: Latitude
        lon: Longitude
        year: Year to sample (2017-2024)
        radius: Sampling radius in meters (default: 10m for single pixel)

    Returns:
        Dictionary with 64-D embedding vector or error
    """
    try:
        # Create point geometry
        point = ee.Geometry.Point([lon, lat])

        # Get AlphaEarth mosaic
        ae_image = get_alphaearth_mosaic(year)

        # Sample at location
        # Use reduceRegion with a small buffer to ensure we get data
        sampled = ae_image.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point.buffer(radius),
            scale=10,  # 10m resolution
            bestEffort=True,
            maxPixels=1
        ).getInfo()

        if not sampled or len(sampled) == 0:
            return {
                'error': 'No AlphaEarth data at this location',
                'details': 'Location may be over water or outside coverage area'
            }

        # Extract A00-A63 bands
        embedding = {}
        for i in range(64):
            band_name = f'A{i:02d}'
            if band_name in sampled and sampled[band_name] is not None:
                embedding[band_name.lower()] = float(sampled[band_name])
            else:
                return {
                    'error': f'Missing or null band {band_name}',
                    'details': 'Incomplete data at location - may be over water or outside AlphaEarth coverage'
                }

        return {
            'success': True,
            'lat': lat,
            'lon': lon,
            'year': year,
            'embedding': embedding
        }

    except Exception as e:
        return {
            'error': str(e),
            'details': 'Earth Engine sampling failed'
        }


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Location Predictor',
        'ee_initialized': True
    })


@app.route('/sample', methods=['POST'])
def sample_endpoint():
    """
    Sample AlphaEarth embedding at a location.

    POST /sample
    Body:
    {
        "lat": 40.7128,
        "lon": -74.0060,
        "year": 2024  // optional, defaults to 2024
    }

    Response:
    {
        "success": true,
        "lat": 40.7128,
        "lon": -74.0060,
        "year": 2024,
        "embedding": {
            "a00": 0.123,
            "a01": -0.456,
            ...
            "a63": 0.789
        }
    }
    """
    try:
        data = request.get_json()

        # Validate input
        if 'lat' not in data or 'lon' not in data:
            return jsonify({
                'error': 'Missing required fields: lat, lon'
            }), 400

        lat = float(data['lat'])
        lon = float(data['lon'])
        year = int(data.get('year', CURRENT_YEAR))

        # Validate ranges
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude (must be -90 to 90)'}), 400
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude (must be -180 to 180)'}), 400
        if not (2017 <= year <= 2024):
            return jsonify({'error': 'Invalid year (must be 2017-2024)'}), 400

        # Sample location
        print(f"🌍 Sampling AlphaEarth at ({lat}, {lon}) for year {year}")
        start_time = time.time()

        result = sample_location(lat, lon, year)

        elapsed = time.time() - start_time
        print(f"   ⏱️  Sampling took {elapsed:.2f}s")

        if 'error' in result:
            return jsonify(result), 404

        return jsonify(result), 200

    except ValueError as e:
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sample-stream', methods=['POST'])
def sample_stream_endpoint():
    """
    Sample location with real-time progress updates via Server-Sent Events.

    POST /sample-stream
    Body: { "lat": 40.7128, "lon": -74.0060, "year": 2024 }

    Returns: text/event-stream with progress updates
    """
    def generate():
        try:
            data = request.get_json()

            lat = float(data['lat'])
            lon = float(data['lon'])
            year = int(data.get('year', CURRENT_YEAR))

            # Send initial progress
            yield f"data: {json.dumps({'status': 'started', 'message': 'Initializing AlphaEarth sampling...', 'progress': 10})}\n\n"
            time.sleep(0.1)

            # Create point geometry
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Creating point geometry...', 'progress': 20})}\n\n"
            point = ee.Geometry.Point([lon, lat])

            # Get AlphaEarth mosaic
            yield f"data: {json.dumps({'status': 'progress', 'message': f'Loading AlphaEarth {year} mosaic...', 'progress': 40})}\n\n"
            ae_image = get_alphaearth_mosaic(year)

            # Sample at location
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Sampling satellite embeddings...', 'progress': 60})}\n\n"
            sampled = ae_image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point.buffer(10),
                scale=10,
                bestEffort=True,
                maxPixels=1
            ).getInfo()

            if not sampled or len(sampled) == 0:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No data at this location', 'progress': 100})}\n\n"
                return

            # Extract embedding
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Extracting 64-D embedding vector...', 'progress': 80})}\n\n"
            embedding = {}
            for i in range(64):
                band_name = f'A{i:02d}'
                if band_name in sampled:
                    embedding[band_name.lower()] = float(sampled[band_name])
                else:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Missing band {band_name}', 'progress': 100})}\n\n"
                    return

            # Success!
            yield f"data: {json.dumps({'status': 'complete', 'message': 'Sampling complete!', 'progress': 100, 'data': {'lat': lat, 'lon': lon, 'year': year, 'embedding': embedding}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e), 'progress': 100})}\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')


@app.route('/sample-batch', methods=['POST'])
def sample_batch_endpoint():
    """
    Sample multiple locations (for future optimization).

    POST /sample-batch
    Body:
    {
        "locations": [
            {"lat": 40.7128, "lon": -74.0060},
            {"lat": 34.0522, "lon": -118.2437}
        ],
        "year": 2024
    }
    """
    try:
        data = request.get_json()

        if 'locations' not in data:
            return jsonify({'error': 'Missing required field: locations'}), 400

        locations = data['locations']
        year = int(data.get('year', CURRENT_YEAR))

        if len(locations) > 100:
            return jsonify({'error': 'Maximum 100 locations per batch'}), 400

        results = []
        for loc in locations:
            result = sample_location(loc['lat'], loc['lon'], year)
            results.append(result)

        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth Location-to-Species Prediction Service")
    print("="*60)
    print(f"📍 Endpoints:")
    print(f"   GET  /health       - Health check")
    print(f"   POST /sample       - Sample single location")
    print(f"   POST /sample-batch - Sample multiple locations")
    print("="*60 + "\n")

    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=True
    )
