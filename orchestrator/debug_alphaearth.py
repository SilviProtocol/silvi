"""
Minimal AlphaEarth debugging script.
Tests step-by-step to identify where the sampling fails.
"""

import ee

# Initialize
PROJECT = 'treekipedia-476404'
ee.Initialize(project=PROJECT)

print("="*80)
print("ALPHAEARTH DEBUGGING - STEP BY STEP")
print("="*80)

# Step 1: Load AlphaEarth collection
print("\n1. Loading AlphaEarth ImageCollection...")
ae_collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
print(f"   ✅ Collection loaded: {ae_collection}")

# Step 2: Get 2023 image
print("\n2. Getting 2023 image...")
img_2023 = ae_collection.filterDate('2023-01-01', '2023-12-31').first()
print(f"   ✅ Image retrieved")

# Step 3: Check image properties
print("\n3. Checking image properties...")
try:
    info = img_2023.getInfo()
    print(f"   ✅ Image info retrieved")
    print(f"   Bands: {len(info['bands'])} bands")
    print(f"   Band names (first 5): {[b['id'] for b in info['bands'][:5]]}")
    print(f"   Band names (last 5): {[b['id'] for b in info['bands'][-5:]]}")

    # Check if bands are A00-A63
    band_ids = [b['id'] for b in info['bands']]
    if 'A00' in band_ids:
        print(f"   ✅ Bands start with A00 (correct)")
    else:
        print(f"   ⚠️  Bands do NOT start with A00")

    if 'A63' in band_ids:
        print(f"   ✅ Bands end with A63 (correct)")
    else:
        print(f"   ⚠️  Bands do NOT end with A63")

except Exception as e:
    print(f"   ❌ Error getting image info: {e}")

# Step 4: Create a test point (Google HQ - known location)
print("\n4. Creating test point (Google HQ, Mountain View, CA)...")
lat, lon = 37.4220, -122.0841
test_point = ee.Geometry.Point([lon, lat])  # [longitude, latitude]
test_feature = ee.Feature(test_point, {'test_id': 'google_hq', 'year': 2023})
test_fc = ee.FeatureCollection([test_feature])
print(f"   ✅ Point: [{lon}, {lat}]")

# Step 5: Sample at the point
print("\n5. Sampling AlphaEarth at test point...")
try:
    sampled = img_2023.sampleRegions(
        collection=test_fc,
        scale=10,
        geometries=False,
        tileScale=1
    )
    print(f"   ✅ sampleRegions completed")

    # Step 6: Check if result is empty
    print("\n6. Checking sampled FeatureCollection...")
    size = sampled.size().getInfo()
    print(f"   Size: {size} features")

    if size > 0:
        print(f"   ✅ SUCCESS! Got {size} sample(s)")

        # Get the actual data
        print("\n7. Getting sample data...")
        data = sampled.first().getInfo()
        print(f"   Properties: {list(data['properties'].keys())}")

        # Check for embedding bands
        props = data['properties']
        embedding_bands = [k for k in props.keys() if k.startswith('A')]
        print(f"   Embedding bands found: {len(embedding_bands)}")
        print(f"   First 5 bands: {embedding_bands[:5]}")
        print(f"   Last 5 bands: {embedding_bands[-5:]}")

        # Show sample values
        print(f"\n   Sample values:")
        for i in range(min(5, len(embedding_bands))):
            band = embedding_bands[i]
            value = props.get(band)
            print(f"      {band}: {value}")

        print(f"\n{'='*80}")
        print("✅ ALPHAEARTH SAMPLING WORKS!")
        print(f"{'='*80}")
        print(f"\nConclusion: The sampling code is correct.")
        print(f"Issue with Acacia points must be:")
        print(f"  - Points falling on masked/no-data pixels")
        print(f"  - Points outside AlphaEarth coverage")
        print(f"  - Coordinate precision issues")

    else:
        print(f"   ❌ FeatureCollection is EMPTY")
        print(f"\n   Possible causes:")
        print(f"   1. Point falls on masked pixel (no satellite data)")
        print(f"   2. Point outside AlphaEarth coverage")
        print(f"   3. Scale/projection mismatch")

        # Try unmasking
        print(f"\n8. Trying with unmasked image...")
        img_unmasked = img_2023.unmask(-9999)
        sampled_unmasked = img_unmasked.sampleRegions(
            collection=test_fc,
            scale=10,
            geometries=False
        )
        size_unmasked = sampled_unmasked.size().getInfo()
        print(f"   Unmasked size: {size_unmasked}")

        if size_unmasked > 0:
            print(f"   ✅ Unmasking helped! Points were on masked pixels")
        else:
            print(f"   ❌ Still empty - points may be outside coverage")

except Exception as e:
    print(f"   ❌ Error during sampling: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}\n")
