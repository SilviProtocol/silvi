"""
AlphaEarth Location-to-Species Prediction Service
Multi-year fallback version - tries multiple years to find data
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import time

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


def sample_location_with_fallback(lat: float, lon: float, preferred_year: int = 2024) -> dict:
    """
    Sample AlphaEarth embedding at a location, trying multiple years if needed.

    Args:
        lat: Latitude
        lon: Longitude
        preferred_year: Preferred year to sample (will try others if no data)

    Returns:
        Dictionary with embedding or error
    """
    # Years to try in order (most recent first, skipping future years)
    current_year = 2024  # AlphaEarth only has data up to 2024
    years_to_try = [preferred_year] if preferred_year <= current_year else []

    # Add fallback years
    for year in range(current_year, 2016, -1):  # AlphaEarth starts from 2017
        if year not in years_to_try:
            years_to_try.append(year)

    print(f"🔍 Attempting to sample ({lat}, {lon}), will try years: {years_to_try}")

    point = ee.Geometry.Point([lon, lat])
    errors = []

    for year in years_to_try:
        try:
            print(f"   Trying year {year}...")

            # Get AlphaEarth mosaic for this year
            col = ee.ImageCollection(AE_COLLECTION).filterDate(
                f'{year}-01-01', f'{year}-12-31'
            )
            ae_image = col.mosaic()

            # Sample at location
            sampled = ae_image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point.buffer(10),  # 10m buffer
                scale=10,
                bestEffort=True,
                maxPixels=1
            ).getInfo()

            if sampled and len(sampled) > 0:
                # Check if we have valid data (not all None)
                valid_bands = 0
                embedding = {}

                for i in range(64):
                    band_name = f'A{i:02d}'
                    if band_name in sampled and sampled[band_name] is not None:
                        embedding[band_name.lower()] = float(sampled[band_name])
                        valid_bands += 1

                if valid_bands == 64:
                    print(f"   ✅ Found complete data for year {year}")
                    return {
                        'success': True,
                        'lat': lat,
                        'lon': lon,
                        'year': year,
                        'year_attempted': preferred_year,
                        'embedding': embedding,
                        'message': f'Using data from {year}' if year != preferred_year else None
                    }
                else:
                    errors.append(f"{year}: Only {valid_bands}/64 bands had data")
            else:
                errors.append(f"{year}: No data returned")

        except Exception as e:
            errors.append(f"{year}: {str(e)}")

    # No valid data found for any year
    return {
        'success': False,
        'error': 'No AlphaEarth data available',
        'details': {
            'location': f'({lat}, {lon})',
            'years_tried': years_to_try,
            'errors': errors,
            'message': 'This location may be over water, in an urban area, or outside AlphaEarth coverage. AlphaEarth only covers natural land areas.'
        }
    }


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Location Predictor (Multi-year)',
        'ee_initialized': True,
        'coverage_years': '2017-2024'
    })


@app.route('/sample', methods=['POST'])
def sample_endpoint():
    """
    Sample AlphaEarth embedding at a location with multi-year fallback.

    POST /sample
    Body:
    {
        "lat": 40.7128,
        "lon": -74.0060,
        "year": 2024  // optional, will try other years if no data
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
        year = int(data.get('year', 2024))

        # Validate ranges
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude (must be -90 to 90)'}), 400
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude (must be -180 to 180)'}), 400

        # Sample location with fallback
        print(f"🌍 Sampling AlphaEarth at ({lat}, {lon})")
        start_time = time.time()

        result = sample_location_with_fallback(lat, lon, year)

        elapsed = time.time() - start_time
        print(f"   ⏱️  Sampling took {elapsed:.2f}s")

        if result.get('success'):
            return jsonify(result), 200
        else:
            # Return 200 with error info so frontend can show appropriate message
            return jsonify(result), 200

    except ValueError as e:
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/coverage', methods=['POST'])
def check_coverage():
    """
    Check if a location has AlphaEarth coverage across years.

    POST /coverage
    Body: { "lat": 40.7128, "lon": -74.0060 }

    Returns coverage info for all available years.
    """
    try:
        data = request.get_json()
        lat = float(data['lat'])
        lon = float(data['lon'])

        point = ee.Geometry.Point([lon, lat])
        coverage = {}

        for year in range(2024, 2016, -1):
            try:
                col = ee.ImageCollection(AE_COLLECTION).filterDate(
                    f'{year}-01-01', f'{year}-12-31'
                )
                ae_image = col.mosaic()

                # Quick check - just see if any data exists
                sampled = ae_image.reduceRegion(
                    reducer=ee.Reducer.first(),
                    geometry=point,
                    scale=10,
                    bestEffort=True,
                    maxPixels=1
                ).getInfo()

                has_data = False
                if sampled:
                    for i in range(min(5, 64)):  # Check first 5 bands
                        if f'A{i:02d}' in sampled and sampled[f'A{i:02d}'] is not None:
                            has_data = True
                            break

                coverage[str(year)] = has_data

            except:
                coverage[str(year)] = False

        return jsonify({
            'lat': lat,
            'lon': lon,
            'coverage': coverage,
            'has_any_coverage': any(coverage.values())
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth Location Predictor - Multi-year Version")
    print("="*60)
    print("📅 Coverage: 2017-2024 (will try multiple years)")
    print("📍 Endpoints:")
    print("   GET  /health   - Health check")
    print("   POST /sample   - Sample with multi-year fallback")
    print("   POST /coverage - Check coverage across years")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )