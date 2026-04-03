{# disableFinding(METADATA_ABSENT) #}
{# disableFinding(METADATA_BOOK) #}
{# disableFinding(METADATA_PROJECT) #}
# AlphaEarth Foundations GCS data

The `gs://alphaearth_foundations` GCS bucket contains COG (Cloud Optimized
GeoTIFF) files that together make up the AlphaEarth Foundations annual
[Satellite
Embedding](developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
dataset. It contains the annual embeddings for the years from 2017 to 2024,
inclusive.

## License

This dataset is licensed under 
[CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) and requires the 
following attribution text: "The AlphaEarth Foundations Satellite Embedding 
[dataset](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL) 
is produced by Google and Google DeepMind."

This bucket is set up as "requester pays", so downloading data may incur egress
and other charges.

## Directory structure

They are divided into directories by year; each year's directory is divided into
120 subdirectories, one per UTM zone, whose names reflect the zone number and
hemisphere (`N` or `S`).

Within each directory are a number of COG files. These files contain all the
pixel data for that UTM zone.

## File structure

Each file is 8192x8192 pixels, with 64 channels. The magnitude of each pixel,
after the de-quantization mapping has been applied (see below), has been
normalized so that it has a Euclidean length of 1.

The files contain overview layers at 4096x4096 pixels, 2048x2048 pixels, and so
on down to a 1x1 top-level overview layer. These overview layers are constructed
so that each overview pixel is the mean of the highest-resolution pixels under
that overview pixel, where the mean's magnitude has been normalized to have
length 1.

The channels correspond, in order, to the `A00` through `A63` axes of the
Satellite Embedding dataset. The COGs also contain this naming for the channels.

Each pixel's value for each channel is a signed 8-bit integer. The way in which
these values are mapped to the native values (in the range \[-1, 1\]) of the
embeddings is described below.

The value -128 corresponds to a masked pixel. If it is present in one channel,
it will be present in all channels. The COGs reflect this (i.e., they have the
`NoData` value set to -128).

The name of each file also carries some information. For example, consider the
file named
`gs://alphaearth_foundations/satellite_embedding/v1/annual/2019/1S/x8qqwcsisbgygl2ry-0000008192-0000000000.tiff`.
As described above, this file is part of the 2019 annual embedding, and is in
UTM zone 1S (zone 1, southern hemisphere). The base filename,
`x8qqwcsisbgygl2ry-0000008192-0000000000`, serves to link this file to the
corresponding Earth Engine Satellite Embedding Image name. In this example, this
file corresponds to a portion of the Earth Engine image
`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL/x8qqwcsisbgygl2ry`. The two decimal parts
of the filename specify where this COG's values are relative to that Earth
Engine Image, as an offset in Y followed by an offset in X. In this case, the
COG's pixel origin is at (0, 8192) relative to the Earth Engine Image's origin.
This is because it was necessary to subdivide each Earth Engine Image (which are
16384x16384 pixels) so that the resulting COGs would not be too unwieldy.

## De-quantization

To transform the raw signed 8-bit value (which will be between -127 and 127
inclusive, as -128 is reserved as the "no data" value) in each channel of each
pixel to the analysis-ready floating-point value (which will be between -1 and
1), the mapping to perform is

- divide by 127.5
- square
- multiply by the sign of the original value

This would be expressed in NumPy as

```python
  # values is a NumPy array of raw pixel values
  de_quantized_values = ((values / 127.5) ** 2) * np.sign(values)
```

In Earth Engine, the corresponding operation would be

```javascript
  var de_quantized_values = values.divide(127.5).pow(2).multiply(values.signum());
```

## Manifest and index

A list of the files in this dataset can be found in
`gs://alphaearth_foundations/satellite_embedding/v1/annual/manifest.txt`.

As it is not possible to determine from the file names what area of the world
they cover, an index has also been provided, in three forms (GeoParquet,
GeoPackage, and CSV) in the files
`gs://alphaearth_foundations/satellite_embedding/v1/annual/aef_index.parquet`,
`gs://alphaearth_foundations/satellite_embedding/v1/annual/aef_index.gpkg`, and
`gs://alphaearth_foundations/satellite_embedding/v1/annual/aef_index.csv`. This
index contains one entry for each file in the dataset. The information provided
for each file is

- the geometry of the file as a WGS84 (i.e., EPSG:4326) polygon. In the CSV
  form, this is in the column `WKT`. See below for details on how this geometry
  is computed.
- `crs`: The CRS of the UTM zone this image belongs to as an EPSG code, like
  `EPSG:32610`.
- `year`: The year that the image covers.
- `utm_zone`: The UTM zone of the image, like `10N`.
- `utm_west`, `utm_south`, `utm_east`, `utm_north`: The UTM bounds of the raw
  pixel array. This does not reflect any geometry processing, and includes all
  pixels whether or not they are valid.
- `wgs84_west`, `wgs84_south`, `wgs84_east`, `wgs84_north`: The min/max
  longitude and latitude of the WGS84 geometry.

### Geometry processing

The pixel array is natively in some UTM zone, so in that UTM zone the bounding
box of the pixel array is a simple rectangle. That bounding box is transformed
into a polygon in WGS84. This polygon includes a number of extra points so that
its edges closely follow the curved lines in WGS84 that the straight lines in
UTM transform into. This polygon does not take into account the
validity/invalidity of pixels in the image, just the bounds of the image's pixel
array.

The polygon is then clipped to the minimum and maximum longitude of the image's
UTM zone. In practice, this may cause it to not include a few valid pixels that
hang over the edge of the UTM zone. Omitting these pixels from the index
shouldn't cause any problems: some image from the neighbouring UTM zone should
cover that area.

Note that clipping to the min/max longitude of the UTM zone means that no
polygon crosses the antimeridian, which should make processing this file a
little simpler.
