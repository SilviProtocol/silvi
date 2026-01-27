"""
AlphaEarth Location-to-Species Prediction Service - DEMO VERSION
Returns MOCK DATA for testing the frontend flow
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import random

app = Flask(__name__)
CORS(app)

# Mock embedding generator
def generate_mock_embedding():
    """Generate a plausible mock 64-D embedding"""
    embedding = {}
    for i in range(64):
        band_name = f'a{i:02d}'
        # Generate realistic values similar to AlphaEarth (typically -0.5 to 0.5 range)
        embedding[band_name] = random.uniform(-0.3, 0.3)
    return embedding

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AlphaEarth Location Predictor (DEMO)',
        'mode': 'DEMO - Returns mock data for testing'
    })

@app.route('/sample', methods=['POST'])
def sample_endpoint():
    """
    DEMO: Always returns a mock embedding after simulated delay
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

        print(f"🌍 DEMO: Simulating AlphaEarth sampling at ({lat}, {lon}) for year {year}")

        # Simulate GEE processing time
        time.sleep(2)  # Shorter delay for demo

        # Always return success with mock embedding
        result = {
            'success': True,
            'lat': lat,
            'lon': lon,
            'year': year,
            'embedding': generate_mock_embedding(),
            'demo_mode': True,
            'message': 'This is mock data for testing'
        }

        print(f"   ✅ DEMO: Returning mock embedding")
        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 AlphaEarth Location Predictor - DEMO MODE")
    print("="*60)
    print("⚠️  RETURNS MOCK DATA FOR TESTING")
    print("📍 Endpoints:")
    print("   GET  /health - Health check")
    print("   POST /sample - Returns mock embedding")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False
    )