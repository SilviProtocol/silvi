"""
Test AlphaEarth coverage in the Amazon rainforest
Let's verify if AlphaEarth actually has data there
"""

import ee

# Initialize Earth Engine
PROJECT = 'treekipedia-476404'
ee.Initialize(project=PROJECT)

def test_amazon_coverage():
    """Test multiple Amazon locations for AlphaEarth coverage"""

    # Test locations in the Amazon
    test_locations = [
        {"name": "Central Amazon (Manaus area)", "lat": -3.4653, "lon": -62.2159},
        {"name": "Southern Amazon (Mato Grosso)", "lat": -14.2644, "lon": -52.7344},
        {"name": "Western Amazon (Acre)", "lat": -9.0238, "lon": -70.8120},
        {"name": "Eastern Amazon (Para)", "lat": -5.5, "lon": -52.5},
        {"name": "Northern Amazon (Roraima)", "lat": 1.5, "lon": -61.5}
    ]

    # Get AlphaEarth collection
    collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')

    print("Testing AlphaEarth coverage in the Amazon...")
    print("=" * 60)

    for loc in test_locations:
        print(f"\n📍 {loc['name']}")
        print(f"   Coordinates: ({loc['lat']}, {loc['lon']})")

        point = ee.Geometry.Point([loc['lon'], loc['lat']])

        # Test year 2023 (should have good coverage)
        year = 2023
        image = collection.filterDate(f'{year}-01-01', f'{year}-12-31').mosaic()

        # Sample at the point
        sample = image.sample(
            region=point,
            scale=10,
            numPixels=1
        )

        # Get the first sample
        first = sample.first()

        # Check if we have data
        try:
            # Get info about the sample
            sample_info = first.getInfo()

            if sample_info and 'properties' in sample_info:
                props = sample_info['properties']

                # Count valid bands
                valid_bands = 0
                sample_values = []

                for i in range(8):  # Just check first 8 bands
                    band_name = f'A{i:02d}'
                    if band_name in props and props[band_name] is not None:
                        valid_bands += 1
                        sample_values.append(f"{band_name}={props[band_name]:.4f}")

                if valid_bands > 0:
                    print(f"   ✅ HAS DATA: {valid_bands}/64 bands have values")
                    print(f"   Sample values: {', '.join(sample_values[:3])}...")
                else:
                    print(f"   ❌ NO DATA: All bands are null")
            else:
                print(f"   ❌ NO DATA: No sample returned")

        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")

    print("\n" + "=" * 60)

    # Now let's check the actual image collection metadata
    print("\nChecking AlphaEarth collection metadata...")

    # Get collection info for 2023
    col_2023 = collection.filterDate('2023-01-01', '2023-12-31')
    size = col_2023.size()
    print(f"Number of images in 2023: {size.getInfo()}")

    # Get the footprint of the mosaic
    mosaic_2023 = col_2023.mosaic()

    # Test a specific point with different methods
    test_point = ee.Geometry.Point([-62.2159, -3.4653])  # Near Manaus

    print(f"\nTesting different sampling methods near Manaus...")

    # Method 1: reduceRegion
    print("Method 1: reduceRegion with point...")
    reduced = mosaic_2023.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=test_point,
        scale=10,
        maxPixels=1
    )
    result = reduced.getInfo()

    if result:
        valid = sum(1 for k, v in result.items() if v is not None)
        print(f"   Found {valid} non-null bands")
        if valid > 0:
            # Show first few values
            for band, value in list(result.items())[:5]:
                if value is not None:
                    print(f"   {band} = {value:.6f}")

    # Method 2: reduceRegion with buffer
    print("\nMethod 2: reduceRegion with 100m buffer...")
    reduced_buffer = mosaic_2023.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=test_point.buffer(100),
        scale=10,
        maxPixels=10
    )
    result_buffer = reduced_buffer.getInfo()

    if result_buffer:
        valid = sum(1 for k, v in result_buffer.items() if v is not None)
        print(f"   Found {valid} non-null bands")

if __name__ == "__main__":
    test_amazon_coverage()