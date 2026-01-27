"""
AlphaEarth Location-to-Species Prediction Service - NO DEBUG MODE
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


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth Location-to-Species Prediction Service")
    print("="*60)
    print(f"📍 Endpoints:")
    print(f"   GET  /health       - Health check")
    print(f"   POST /sample       - Sample single location")
    print("="*60 + "\n")

    # Run Flask app WITHOUT debug mode
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False  # IMPORTANT: No debug mode to avoid process conflicts
    )
