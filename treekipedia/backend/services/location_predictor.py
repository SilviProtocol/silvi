"""
AlphaEarth Location-to-Species Prediction Service - FIXED VERSION
Uses the correct sampling method that actually retrieves AlphaEarth data
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import time
import random
import numpy as np

# Configuration
PROJECT = 'treekipedia'
AE_COLLECTION = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'

app = Flask(__name__)
CORS(app)

# Initialize Earth Engine
try:
    ee.Initialize(project=PROJECT)
    print(f"✅ Earth Engine initialized (project: {PROJECT})")
except Exception as e:
    print(f"❌ Earth Engine initialization failed: {e}")
    raise


def sample_alphaearth_properly(lat: float, lon: float, year: int = 2023) -> dict:
    """
    Properly sample AlphaEarth using the sample() method that works.
    """
    print(f"🔍 Sampling AlphaEarth at ({lat:.4f}, {lon:.4f}) for year {year}")

    try:
        # Get AlphaEarth collection for the specified year
        col = ee.ImageCollection(AE_COLLECTION).filterDate(
            f'{year}-01-01', f'{year}-12-31'
        )
        ae_image = col.mosaic()

        # Create point geometry
        point = ee.Geometry.Point([lon, lat])

        # Use sample() method which WORKS for AlphaEarth
        sample = ae_image.sample(
            region=point,
            scale=10,
            numPixels=1
        )

        # Get the first (and only) sample
        first_sample = sample.first().getInfo()

        if first_sample and 'properties' in first_sample:
            props = first_sample['properties']

            # Extract all 64 bands
            embedding = {}
            valid_bands = 0

            for i in range(64):
                band_name = f'A{i:02d}'
                if band_name in props and props[band_name] is not None:
                    embedding[f'a{i:02d}'] = float(props[band_name])
                    valid_bands += 1

            # Build array form for Node backend compatibility
            embedding_array = [embedding[f'a{i:02d}'] for i in range(valid_bands)]

            if valid_bands == 64:
                print(f"   ✅ SUCCESS: Retrieved all 64 bands from AlphaEarth")
                return {
                    'success': True,
                    'lat': lat,
                    'lon': lon,
                    'year': year,
                    'embedding': embedding,
                    'alphaearth_embedding': embedding_array,
                    'data_source': 'alphaearth_real',
                    'message': f'Real AlphaEarth data from {year}'
                }
            elif valid_bands > 0:
                print(f"   ⚠️ PARTIAL: Only {valid_bands}/64 bands had data")
                return {
                    'success': True,
                    'lat': lat,
                    'lon': lon,
                    'year': year,
                    'embedding': embedding,
                    'alphaearth_embedding': embedding_array,
                    'data_source': 'alphaearth_partial',
                    'valid_bands': valid_bands,
                    'message': f'Partial AlphaEarth data ({valid_bands}/64 bands)'
                }
            else:
                print(f"   ❌ NO DATA: Location may be over water or urban area")
                return {
                    'success': False,
                    'error': 'No AlphaEarth coverage at this location',
                    'details': 'This location may be over water or in an urban area'
                }

        else:
            print(f"   ❌ NO SAMPLE: Could not retrieve data")
            return {
                'success': False,
                'error': 'Could not sample AlphaEarth at this location'
            }

    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        return {
            'success': False,
            'error': f'Error sampling AlphaEarth: {str(e)}'
        }


def generate_realistic_embedding(lat: float, lon: float) -> dict:
    """
    Generate realistic simulated embedding as fallback.
    """
    seed = int(abs(lat * 1000) + abs(lon * 1000))
    np.random.seed(seed)

    embedding = {}
    for i in range(64):
        # Generate values similar to real AlphaEarth range
        value = np.random.normal(0, 0.08)  # Most values between -0.2 and 0.2
        value = np.clip(value, -0.3, 0.3)
        embedding[f'a{i:02d}'] = float(value)

    return embedding


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Location Predictor (FIXED)',
        'method': 'Using sample() method that works',
        'ee_initialized': True
    })


@app.route('/sample', methods=['GET', 'POST'])
def sample_endpoint():
    """
    Sample AlphaEarth embedding at a location.

    GET  /sample?lat=-14.2644&lon=-52.7344&year=2023
    POST /sample  { "lat": -14.2644, "lon": -52.7344, "year": 2023 }
    """
    try:
        if request.method == 'GET':
            lat_str = request.args.get('lat')
            lon_str = request.args.get('lon')
            year_str = request.args.get('year', '2023')
            if not lat_str or not lon_str:
                return jsonify({'error': 'Missing required parameters: lat, lon'}), 400
            lat = float(lat_str)
            lon = float(lon_str)
            year = int(year_str)
        else:
            data = request.get_json()
            if 'lat' not in data or 'lon' not in data:
                return jsonify({'error': 'Missing required fields: lat, lon'}), 400
            lat = float(data['lat'])
            lon = float(data['lon'])
            year = int(data.get('year', 2023))

        # Validate ranges
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude'}), 400
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude'}), 400

        # Try to get real AlphaEarth data
        start_time = time.time()
        result = sample_alphaearth_properly(lat, lon, year)

        # If no real data, try different years
        if not result.get('success') and year != 2023:
            print(f"   Trying fallback year 2023...")
            result = sample_alphaearth_properly(lat, lon, 2023)

        # If still no data, use simulated embedding
        if not result.get('success'):
            print(f"   Using simulated embedding as fallback")
            sim_embedding = generate_realistic_embedding(lat, lon)
            sim_array = [sim_embedding[f'a{i:02d}'] for i in range(64)]
            result = {
                'success': True,
                'lat': lat,
                'lon': lon,
                'year': year,
                'embedding': sim_embedding,
                'alphaearth_embedding': sim_array,
                'data_source': 'simulated',
                'demo_mode': True,
                'message': 'No AlphaEarth coverage - using simulated data for demo'
            }

        elapsed = time.time() - start_time
        result['processing_time'] = round(elapsed, 2)

        return jsonify(result), 200

    except Exception as e:
        print(f"Error in sample endpoint: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test-amazon', methods=['GET'])
def test_amazon():
    """Quick test endpoint for Amazon locations"""
    test_locs = [
        {"name": "Manaus", "lat": -3.4653, "lon": -62.2159},
        {"name": "Mato Grosso", "lat": -14.2644, "lon": -52.7344}
    ]

    results = []
    for loc in test_locs:
        result = sample_alphaearth_properly(loc['lat'], loc['lon'], 2023)
        results.append({
            'location': loc['name'],
            'coordinates': f"({loc['lat']}, {loc['lon']})",
            'success': result.get('success'),
            'data_source': result.get('data_source', 'none'),
            'sample_values': list(result.get('embedding', {}).items())[:3] if result.get('embedding') else []
        })

    return jsonify(results), 200


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth Location Predictor - FIXED VERSION")
    print("="*60)
    print("✅ Uses correct sample() method that retrieves data")
    print("✅ Successfully gets AlphaEarth data from Amazon")
    print("✅ Falls back to simulated data only when needed")
    print("="*60)
    print("📍 Endpoints:")
    print("   GET  /health       - Health check")
    print("   POST /sample       - Get embedding (real or simulated)")
    print("   GET  /test-amazon  - Test Amazon locations")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )