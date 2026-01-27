"""
AlphaEarth Location-to-Species Prediction Service - HYBRID VERSION
Uses real AlphaEarth data when available, falls back to simulated data otherwise
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import time
import random
import numpy as np

# Configuration
PROJECT = 'treekipedia-476404'
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


def generate_realistic_embedding(lat: float, lon: float, year: int) -> dict:
    """
    Generate a realistic-looking embedding based on location.
    Uses location to create deterministic but varied values.
    """
    # Use location as seed for reproducibility
    seed = int(abs(lat * 1000) + abs(lon * 1000) + year)
    np.random.seed(seed)

    # Create base pattern influenced by latitude (climate zones)
    latitude_factor = abs(lat) / 90.0  # 0 at equator, 1 at poles

    # Generate 64D embedding with realistic patterns
    embedding = {}
    for i in range(64):
        band_name = f'a{i:02d}'

        # Mix different patterns
        base_value = np.random.normal(0, 0.15)  # Gaussian noise
        lat_influence = np.sin(latitude_factor * np.pi) * 0.1  # Latitude pattern
        lon_influence = np.cos(lon / 180 * np.pi) * 0.05  # Longitude pattern
        seasonal = np.sin((i / 64) * 2 * np.pi) * 0.08  # Seasonal-like pattern

        value = base_value + lat_influence + lon_influence + seasonal

        # Clamp to realistic range
        value = np.clip(value, -0.5, 0.5)
        embedding[band_name] = float(value)

    return embedding


def sample_alphaearth_with_fallback(lat: float, lon: float, year: int = 2024) -> dict:
    """
    Try to get real AlphaEarth data, fall back to simulated if unavailable.
    """
    print(f"🔍 Sampling location ({lat}, {lon}) for year {year}")

    # First, try to get real AlphaEarth data
    point = ee.Geometry.Point([lon, lat])

    # Years to try (most recent first)
    years_to_try = [year] if year <= 2024 else []
    for y in range(2024, 2016, -1):
        if y not in years_to_try:
            years_to_try.append(y)

    # Try each year
    for try_year in years_to_try[:3]:  # Only try 3 years to be faster
        try:
            print(f"   Trying AlphaEarth year {try_year}...")

            col = ee.ImageCollection(AE_COLLECTION).filterDate(
                f'{try_year}-01-01', f'{try_year}-12-31'
            )
            ae_image = col.mosaic()

            # Sample with a small buffer
            sampled = ae_image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point.buffer(10),
                scale=10,
                bestEffort=True,
                maxPixels=1
            ).getInfo()

            if sampled:
                # Check if we have valid data
                valid_bands = 0
                embedding = {}

                for i in range(64):
                    band_name = f'A{i:02d}'
                    if band_name in sampled and sampled[band_name] is not None:
                        embedding[band_name.lower()] = float(sampled[band_name])
                        valid_bands += 1

                if valid_bands == 64:
                    print(f"   ✅ Found real AlphaEarth data for {try_year}")
                    return {
                        'success': True,
                        'lat': lat,
                        'lon': lon,
                        'year': try_year,
                        'embedding': embedding,
                        'data_source': 'alphaearth_real',
                        'message': f'Using real AlphaEarth data from {try_year}'
                    }
        except Exception as e:
            print(f"   Error trying year {try_year}: {e}")
            continue

    # No real data found - use simulated embedding
    print(f"   ⚠️ No AlphaEarth coverage - using simulated data")

    simulated_embedding = generate_realistic_embedding(lat, lon, year)

    return {
        'success': True,
        'lat': lat,
        'lon': lon,
        'year': year,
        'embedding': simulated_embedding,
        'data_source': 'simulated',
        'message': 'No AlphaEarth coverage at this location. Using simulated habitat signature for demonstration.',
        'demo_mode': True
    }


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Hybrid Predictor',
        'mode': 'hybrid (real + simulated fallback)',
        'ee_initialized': True
    })


@app.route('/sample', methods=['POST'])
def sample_endpoint():
    """
    Sample AlphaEarth or generate simulated embedding.

    Always returns a result - either real or simulated.
    """
    try:
        data = request.get_json()

        if 'lat' not in data or 'lon' not in data:
            return jsonify({
                'error': 'Missing required fields: lat, lon'
            }), 400

        lat = float(data['lat'])
        lon = float(data['lon'])
        year = int(data.get('year', 2024))

        # Validate ranges
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude'}), 400
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude'}), 400

        # Get embedding (real or simulated)
        start_time = time.time()
        result = sample_alphaearth_with_fallback(lat, lon, year)
        elapsed = time.time() - start_time

        result['processing_time'] = round(elapsed, 2)

        return jsonify(result), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth HYBRID Location Predictor")
    print("="*60)
    print("✨ Features:")
    print("   - Uses REAL AlphaEarth data when available")
    print("   - Falls back to SIMULATED data otherwise")
    print("   - Always returns predictions for demo purposes")
    print("="*60)
    print("📍 Endpoints:")
    print("   GET  /health - Health check")
    print("   POST /sample - Get embedding (real or simulated)")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )