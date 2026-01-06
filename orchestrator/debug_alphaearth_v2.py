"""
AlphaEarth debugging V2 - Try reduceRegion instead of sampleRegions
"""

import ee

PROJECT = 'treekipedia-476404'
ee.Initialize(project=PROJECT)

print("="*80)
print("ALPHAEARTH DEBUGGING V2 - Using reduceRegion")
print("="*80)

# Load collection and get 2023 image
print("\n1. Loading AlphaEarth 2023 image...")
ae_collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
img_2023 = ae_collection.filterDate('2023-01-01', '2023-12-31').first()
print("   ✅ Image loaded")

# Test point
print("\n2. Creating test point (Google HQ)...")
lat, lon = 37.4220, -122.0841
test_point = ee.Geometry.Point([lon, lat])
print(f"   ✅ Point: [{lon}, {lat}]")

# Try reduceRegion
print("\n3. Trying reduceRegion (instead of sampleRegions)...")
try:
    result = img_2023.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=test_point,
        scale=10
    ).getInfo()

    print(f"   ✅ reduceRegion completed")
    print(f"   Result keys: {list(result.keys())}")

    if result:
        print(f"\n   ✅ GOT DATA!")
        print(f"   Number of values: {len(result)}")

        # Show first 5 bands
        bands = [k for k in result.keys() if k.startswith('A')]
        print(f"   Embedding bands: {len(bands)}")
        print(f"\n   Sample values (first 5 bands):")
        for band in bands[:5]:
            print(f"      {band}: {result[band]}")

        print(f"\n{'='*80}")
        print("✅ ALPHAEARTH ACCESS WORKS WITH reduceRegion!")
        print(f"{'='*80}")
        print(f"\nConclusion: Need to use reduceRegion, not sampleRegions")
        print(f"Or there's an issue with how sampleRegions exports to BigQuery")

    else:
        print(f"   ❌ Result is empty")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Try checking collection properties
print(f"\n4. Checking collection availability...")
try:
    count = ae_collection.size().getInfo()
    print(f"   Images in collection: {count}")

    if count > 0:
        print(f"\n5. Getting first image info...")
        first_img_info = ee.Image(ae_collection.first()).getInfo()
        print(f"   ✅ First image properties:")
        if 'properties' in first_img_info:
            for k, v in first_img_info['properties'].items():
                if not k.startswith('system:'):
                    print(f"      {k}: {v}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print(f"\n{'='*80}\n")
