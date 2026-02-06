"""
AlphaEarth debugging V3 - The collection has 86K tiles!
Need to either use mosaic() or find the specific tile for our location.
"""

import ee

PROJECT = 'treekipedia-476404'
ee.Initialize(project=PROJECT)

print("="*80)
print("ALPHAEARTH DEBUGGING V3 - Using mosaic()")
print("="*80)

# Load collection
print("\n1. Loading AlphaEarth collection...")
ae_collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
print(f"   ✅ Collection loaded")

# Filter to 2023
print("\n2. Filtering to 2023...")
ae_2023 = ae_collection.filterDate('2023-01-01', '2023-12-31')
count_2023 = ae_2023.size().getInfo()
print(f"   ✅ Found {count_2023:,} tiles for 2023")

# Create MOSAIC (combines all tiles)
print("\n3. Creating mosaic (combines all tiles)...")
mosaic_2023 = ae_2023.mosaic()
print(f"   ✅ Mosaic created")

# Test point
print("\n4. Testing at Google HQ...")
lat, lon = 37.4220, -122.0841
test_point = ee.Geometry.Point([lon, lat])

# Sample from mosaic
print("\n5. Sampling from mosaic...")
try:
    result = mosaic_2023.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=test_point,
        scale=10
    ).getInfo()

    print(f"   ✅ reduceRegion completed")

    # Check for actual values
    bands = [k for k in result.keys() if k.startswith('A')]
    print(f"   Embedding bands: {len(bands)}")

    # Check if we have non-None values
    non_none = [k for k, v in result.items() if v is not None and k.startswith('A')]
    print(f"   Non-None values: {len(non_none)}")

    if non_none:
        print(f"\n   ✅ SUCCESS! Got real embeddings!")
        print(f"\n   Sample values (first 10 bands):")
        for band in non_none[:10]:
            print(f"      {band}: {result[band]:.6f}")

        print(f"\n{'='*80}")
        print("✅ SOLUTION FOUND: USE .mosaic() BEFORE SAMPLING")
        print(f"{'='*80}")
        print(f"\nCorrect approach:")
        print(f"  1. Filter collection to year")
        print(f"  2. Use .mosaic() to combine tiles")
        print(f"  3. Then use sampleRegions() on the mosaic")

    else:
        print(f"   ⚠️  All values are None at this location")

        # Try different location - somewhere with more land coverage
        print(f"\n6. Trying different location (Kansas, USA - center of US)...")
        lat2, lon2 = 39.0119, -98.4842
        test_point2 = ee.Geometry.Point([lon2, lat2])

        result2 = mosaic_2023.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=test_point2,
            scale=10
        ).getInfo()

        non_none2 = [k for k, v in result2.items() if v is not None and k.startswith('A')]
        print(f"   Non-None values: {len(non_none2)}")

        if non_none2:
            print(f"\n   ✅ GOT DATA at Kansas location!")
            print(f"   Sample values:")
            for band in non_none2[:5]:
                print(f"      {band}: {result2[band]:.6f}")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}\n")
