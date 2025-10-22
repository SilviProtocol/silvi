# Comprehensive Free Leaflet Tile Providers Guide (2025)

A comprehensive list of free base layers (tile providers) for Leaflet maps, organized by category with tile URLs, attribution requirements, and usage notes.

---

## Table of Contents
1. [Satellite & Imagery Layers](#satellite--imagery-layers)
2. [Terrain & Topographic Layers](#terrain--topographic-layers)
3. [Street Map Alternatives](#street-map-alternatives)
4. [Dark Mode Maps](#dark-mode-maps)
5. [Specialized Layers](#specialized-layers)
6. [Weather Layers](#weather-layers)

---

## Satellite & Imagery Layers

### ESRI World Imagery
**Tile URL:**
```
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
```

**Attribution:**
```
Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community
```

**API Key:** Requires free ArcGIS Developer account for production use
**Free Tier:** Free for non-commercial use (no revenue from ads/subscriptions)
**Max Zoom:** 19
**Best Use Case:** High-quality satellite imagery, global coverage
**Notes:** Must display proper attribution for Esri and all data providers

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
  attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
  maxZoom={19}
/>
```

---

### Mapbox Satellite
**Tile URL (Raster):**
```
https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}.jpg?access_token={accessToken}
```

**Tile URL (Static Tiles API):**
```
https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token={accessToken}
```

**Attribution:**
```
&copy; Mapbox &copy; OpenStreetMap
```

**API Key:** Required (obtain from Mapbox)
**Free Tier:** 50,000 map loads per month
**Max Zoom:** 22 (varies by region - global to zoom 16, regional to zoom 18, select to zoom 21+)
**Coverage:** Global 1-2m resolution, regional 0.6-0.3m, select 7.5cm+
**Best Use Case:** High-quality satellite with generous free tier

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token=YOUR_MAPBOX_TOKEN"
  attribution='&copy; Mapbox &copy; OpenStreetMap'
  tileSize={512}
  zoomOffset={-1}
  maxZoom={22}
/>
```

---

### USGS Satellite Imagery
**Tile URL:**
```
https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}
```

**Attribution:**
```
Tiles courtesy of the U.S. Geological Survey
```

**API Key:** None required
**Free Tier:** Completely free, public domain
**Max Zoom:** 16
**Best Use Case:** US-focused satellite imagery, public domain data
**Notes:** USGS requests (but doesn't require) attribution: "Map services and data available from U.S. Geological Survey, National Geospatial Program"

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"
  attribution='Tiles courtesy of the U.S. Geological Survey'
  maxZoom={16}
/>
```

---

### Stadia Alidade Satellite
**Tile URL:**
```
https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}@2x.jpg
```

**Attribution:**
```
&copy; CNES, Distribution Airbus DS, &copy; Airbus DS, &copy; PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors
```

**API Key:** Not required for localhost; optional domain auth or API key for production
**Free Tier:** 14-day trial, then free tier available (no credit card required)
**Max Zoom:** 20
**Best Use Case:** Satellite imagery with no API key needed for most web deployments

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}@2x.jpg"
  attribution='&copy; CNES, Distribution Airbus DS, &copy; Airbus DS, &copy; PlanetObserver (Contains Copernicus Data) | &copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap contributors'
  maxZoom={20}
/>
```

---

### TomTom Satellite
**Tile URL:**
```
https://{s}.api.tomtom.com/map/1/tile/sat/main/{z}/{x}/{y}.jpg?key={apiKey}
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; TomTom
```

**API Key:** Required (register at TomTom Developer Portal)
**Free Tier:** 50,000 tile requests per day
**Max Zoom:** 19
**Pricing:** $0.08 per 1,000 tile requests over free tier
**Best Use Case:** Satellite imagery with generous daily free tier

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.api.tomtom.com/map/1/tile/sat/main/{z}/{x}/{y}.jpg?key=YOUR_API_KEY"
  attribution='&copy; TomTom'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={19}
/>
```

---

### HERE Satellite (Raster Tile API v3)
**Tile URL:**
```
https://maps.hereapi.com/v3/base/mc/{z}/{x}/{y}/png?style=satellite.day&size=512&apiKey={apiKey}
```

**Attribution:**
```
Map &copy; HERE
```

**API Key:** Required (obtain from HERE Developer Portal)
**Free Tier:** Available (check HERE Developer Portal for current limits)
**Styles:** `satellite.day`, `explore.satellite.day` (hybrid)
**Best Use Case:** Satellite imagery with multiple viewing options
**Notes:** HERE deprecated old Maps Tile API; must use new Raster Tile API v3

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://maps.hereapi.com/v3/base/mc/{z}/{x}/{y}/png?style=satellite.day&size=512&apiKey=YOUR_API_KEY"
  attribution='Map &copy; HERE'
  maxZoom={20}
/>
```

---

## Terrain & Topographic Layers

### OpenTopoMap
**Tile URL:**
```
https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 17
**Best Use Case:** Topographic maps with contour lines and shading
**Notes:** Project not actively updated as of 2024, but tiles still available

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
  attribution='Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)'
  subdomains={['a', 'b', 'c']}
  maxZoom={17}
/>
```

---

### USGS Topo
**Tile URL:**
```
https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}
```

**Attribution:**
```
Tiles courtesy of the U.S. Geological Survey
```

**API Key:** None required
**Free Tier:** Completely free, public domain
**Max Zoom:** 16
**Best Use Case:** US topographic maps, trail maps, elevation data

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}"
  attribution='Tiles courtesy of the U.S. Geological Survey'
  maxZoom={16}
/>
```

---

### USGS Imagery + Topo (Hybrid)
**Tile URL:**
```
https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}
```

**Attribution:**
```
Tiles courtesy of the U.S. Geological Survey
```

**API Key:** None required
**Free Tier:** Completely free, public domain
**Max Zoom:** 16
**Best Use Case:** Satellite imagery with topographic overlays

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}"
  attribution='Tiles courtesy of the U.S. Geological Survey'
  maxZoom={16}
/>
```

---

### Thunderforest Landscape (Terrain)
**Tile URL:**
```
https://{s}.tile.thunderforest.com/landscape/{z}/{x}/{y}.png?apikey={apiKey}
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
&copy; Thunderforest, &copy; OpenStreetMap contributors
```

**API Key:** Required (register at Thunderforest)
**Free Tier:** Available with API key registration
**Max Zoom:** 22
**Best Use Case:** Detailed terrain visualization with hillshade

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile.thunderforest.com/landscape/{z}/{x}/{y}.png?apikey=YOUR_API_KEY"
  attribution='&copy; Thunderforest, &copy; OpenStreetMap contributors'
  subdomains={['a', 'b', 'c']}
  maxZoom={22}
/>
```

---

### Mundialis SRTM Hillshade (WMS)
**WMS URL:**
```
http://ows.mundialis.de/services/service
```

**Layers:** `SRTM30-Colored-Hillshade`

**Attribution:**
```
&copy; Mundialis
```

**API Key:** None required
**Free Tier:** Completely free
**Best Use Case:** Hillshade elevation visualization as overlay

**React-Leaflet Example (using WMS):**
```jsx
import { WMSTileLayer } from 'react-leaflet';

<WMSTileLayer
  url="http://ows.mundialis.de/services/service"
  layers="SRTM30-Colored-Hillshade"
  attribution='&copy; Mundialis'
  format="image/png"
  transparent={true}
/>
```

---

### TomTom Hillshade
**Tile URL:**
```
https://{s}.api.tomtom.com/map/1/tile/hill/main/{z}/{x}/{y}.png?key={apiKey}
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; TomTom
```

**API Key:** Required
**Free Tier:** 50,000 tile requests per day
**Best Use Case:** Professional hillshade overlay

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.api.tomtom.com/map/1/tile/hill/main/{z}/{x}/{y}.png?key=YOUR_API_KEY"
  attribution='&copy; TomTom'
  subdomains={['a', 'b', 'c', 'd']}
  opacity={0.6}
/>
```

---

## Street Map Alternatives

### OpenStreetMap Standard
**Tile URL:**
```
https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 19
**Best Use Case:** Standard street maps, most widely used
**Notes:** Must follow OSM tile usage policy (provide attribution, valid User-Agent, etc.)

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  subdomains={['a', 'b', 'c']}
  maxZoom={19}
/>
```

---

### OpenStreetMap.HOT (Humanitarian)
**Tile URL:**
```
https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b']`

**Attribution:**
```
&copy; OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 19
**Best Use Case:** Humanitarian/crisis mapping with enhanced POI visibility

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
  attribution='&copy; OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France'
  subdomains={['a', 'b']}
  maxZoom={19}
/>
```

---

### Wikimedia Maps
**Tile URL:**
```
https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png
```

**Attribution:**
```
Wikimedia maps beta | Map data &copy; <a href="http://openstreetmap.org/copyright">OpenStreetMap contributors</a>
```

**API Key:** None required
**Free Tier:** Free for Wikimedia projects and limited community tools only
**Max Zoom:** 19
**Best Use Case:** Clean, internationalized street maps
**Notes:** May NOT be used by third-party services outside Wikimedia projects without permission. Requires valid HTTP User-Agent.

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png"
  attribution='Wikimedia maps beta | Map data &copy; OpenStreetMap contributors'
  maxZoom={19}
/>
```

---

### Stadia Alidade Smooth
**Tile URL:**
```
https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}@2x.png
```

**Attribution:**
```
&copy; <a href="https://stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors
```

**API Key:** Not required for localhost; optional for production
**Free Tier:** 14-day trial, then free tier
**Max Zoom:** 20
**Best Use Case:** Clean, modern street maps with retina support

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}@2x.png"
  attribution='&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap contributors'
  maxZoom={20}
/>
```

---

### Stamen Watercolor (via Stadia)
**Tile URL:**
```
https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg
```

**Attribution:**
```
Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://creativecommons.org/licenses/by-sa/3.0">CC BY SA</a>
```

**API Key:** Required (register at Stadia Maps and whitelist domain)
**Free Tier:** Available after registration
**Max Zoom:** 18
**Best Use Case:** Artistic, hand-painted style maps
**Notes:** As of July 2023, Stamen tiles hosted by Stadia Maps

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg"
  attribution='Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under CC BY SA'
  maxZoom={18}
/>
```

---

### Stamen Toner (via Stadia)
**Tile URL:**
```
https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png
```

**Attribution:**
```
Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://creativecommons.org/licenses/by-sa/3.0">CC BY SA</a>
```

**API Key:** Required (register at Stadia Maps)
**Free Tier:** Available
**Max Zoom:** 20
**Best Use Case:** High-contrast black and white maps

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png"
  attribution='Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under CC BY SA'
  maxZoom={20}
/>
```

---

### Hydda Full
**Tile URL:**
```
https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
Tiles courtesy of <a href="http://openstreetmap.se/" target="_blank">OpenStreetMap Sweden</a> &mdash; Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 18
**Best Use Case:** Balanced mix of roads and terrain

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png"
  attribution='Tiles courtesy of OpenStreetMap Sweden &mdash; Map data &copy; OpenStreetMap contributors'
  subdomains={['a', 'b', 'c']}
  maxZoom={18}
/>
```

---

## Dark Mode Maps

### CARTO Dark Matter
**Tile URL:**
```
https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 20
**License:** BSD 3-Clause and CC-BY 4.0
**Best Use Case:** Dark theme data visualization, excellent for overlays

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"
  attribution='&copy; OpenStreetMap contributors &copy; CARTO'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={20}
/>
```

---

### CARTO Dark Matter (No Labels)
**Tile URL:**
```
https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; OpenStreetMap contributors &copy; CARTO
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 20
**Best Use Case:** Dark base layer without labels (add custom markers/data on top)

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}@2x.png"
  attribution='&copy; OpenStreetMap contributors &copy; CARTO'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={20}
/>
```

---

### Stadia Alidade Smooth Dark
**Tile URL:**
```
https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}@2x.png
```

**Attribution:**
```
&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap contributors
```

**API Key:** Not required for localhost
**Free Tier:** Available
**Max Zoom:** 20
**Best Use Case:** Modern dark mode street maps

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}@2x.png"
  attribution='&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap contributors'
  maxZoom={20}
/>
```

---

### CARTO Voyager
**Tile URL:**
```
https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; OpenStreetMap contributors &copy; CARTO
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 20
**Best Use Case:** Balanced color scheme, good for general purpose

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png"
  attribution='&copy; OpenStreetMap contributors &copy; CARTO'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={20}
/>
```

---

### CARTO Positron
**Tile URL:**
```
https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png
```

**Subdomains:** `['a', 'b', 'c', 'd']`

**Attribution:**
```
&copy; OpenStreetMap contributors &copy; CARTO
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 20
**Best Use Case:** Light theme maps, clean background for data visualization

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"
  attribution='&copy; OpenStreetMap contributors &copy; CARTO'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={20}
/>
```

---

## Specialized Layers

### CyclOSM (Cycling)
**Tile URL:**
```
https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
<a href="https://github.com/cyclosm/cyclosm-cartocss-style/releases" title="CyclOSM - Open Bicycle render">CyclOSM</a> | Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
```

**API Key:** None required
**Free Tier:** Free under fair use policy
**Max Zoom:** 20
**Best Use Case:** Bicycle routing and cycling infrastructure

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png"
  attribution='CyclOSM | Map data: &copy; OpenStreetMap contributors'
  subdomains={['a', 'b', 'c']}
  maxZoom={20}
/>
```

---

### OpenRailwayMap
**Tile URL:**
```
https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png
```

**Subdomains:** `['a', 'b', 'c']`

**Attribution:**
```
&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Style: <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA 2.0</a> <a href="http://www.openrailwaymap.org/">OpenRailwayMap</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 19
**Best Use Case:** Railway infrastructure overlay, use as overlay on base map
**Variants:** standard, signals, maxspeed

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"
  attribution='&copy; OpenStreetMap contributors, Style: CC-BY-SA 2.0 OpenRailwayMap'
  subdomains={['a', 'b', 'c']}
  maxZoom={19}
  opacity={0.7}
/>
```

---

### OpenSeaMap (Nautical)
**Tile URL:**
```
https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png
```

**Attribution:**
```
All maps &copy; <a href="https://www.openseamap.org/">OpenSeaMap</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Best Use Case:** Nautical charts, use as overlay on satellite/street maps
**Notes:** Typically used as an overlay layer

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"
  attribution='All maps &copy; OpenSeaMap'
  opacity={0.6}
/>
```

---

### WaymarkedTrails (Hiking/MTB)
**Tile URL (MTB):**
```
https://tile.waymarkedtrails.org/mtb/{z}/{x}/{y}.png
```

**Tile URL (Hiking):**
```
https://tile.waymarkedtrails.org/hiking/{z}/{x}/{y}.png
```

**Attribution:**
```
&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://waymarkedtrails.org">Waymarked Trails</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Best Use Case:** Hiking/biking trail overlays
**Variants:** hiking, cycling, mtb, riding, skating, slopes (winter sports)

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tile.waymarkedtrails.org/hiking/{z}/{x}/{y}.png"
  attribution='&copy; OpenStreetMap contributors, &copy; Waymarked Trails'
  opacity={0.6}
/>
```

---

### ÖPNVKarte (Public Transport)
**Tile URL:**
```
https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png
```

**Attribution:**
```
Map <a href="https://memomaps.de/">memomaps.de</a> <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
```

**API Key:** None required
**Free Tier:** Completely free
**Max Zoom:** 18
**Best Use Case:** Public transportation networks

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png"
  attribution='Map memomaps.de CC-BY-SA, map data &copy; OpenStreetMap contributors'
  maxZoom={18}
/>
```

---

### SafeCast (Radiation Monitoring)
**Tile URL:**
```
https://s3.amazonaws.com/te512.safecast.org/{z}/{x}/{y}.png
```

**Attribution:**
```
&copy; <a href="https://safecast.org">Safecast</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Best Use Case:** Radiation monitoring overlay
**Notes:** Use as overlay on base maps

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://s3.amazonaws.com/te512.safecast.org/{z}/{x}/{y}.png"
  attribution='&copy; Safecast'
  opacity={0.6}
/>
```

---

### JusticeMap (Demographics)
**Tile URL:**
```
https://www.justicemap.org/tile/512/{variant}/{z}/{x}/{y}.png
```

**Variants:** `income`, `americanIndian`, `asian`, `black`, `hispanic`, `multi`, `nonWhite`, `white`, `plurality`

**Attribution:**
```
&copy; <a href="http://www.justicemap.org/terms.php">JusticeMap</a>
```

**API Key:** None required
**Free Tier:** Completely free
**Best Use Case:** US demographic data visualization

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://www.justicemap.org/tile/512/income/{z}/{x}/{y}.png"
  attribution='&copy; JusticeMap'
  opacity={0.6}
/>
```

---

## Weather Layers

### OpenWeatherMap - Clouds
**Tile URL:**
```
https://tile.openweathermap.org/map/clouds_new/{z}/{x}/{y}.png?appid={apiKey}
```

**Attribution:**
```
Map data &copy; <a href="https://openweathermap.org">OpenWeatherMap</a>
```

**API Key:** Required (obtain from OpenWeatherMap)
**Free Tier:** Available with registration
**Best Use Case:** Current cloud coverage overlay

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tile.openweathermap.org/map/clouds_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY"
  attribution='Map data &copy; OpenWeatherMap'
  opacity={0.5}
/>
```

---

### OpenWeatherMap - Precipitation
**Tile URL:**
```
https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid={apiKey}
```

**Attribution:**
```
Map data &copy; OpenWeatherMap
```

**API Key:** Required
**Free Tier:** Available
**Best Use Case:** Current precipitation overlay

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY"
  attribution='Map data &copy; OpenWeatherMap'
  opacity={0.5}
/>
```

---

### OpenWeatherMap - Temperature
**Tile URL:**
```
https://tile.openweathermap.org/map/temp_new/{z}/{x}/{y}.png?appid={apiKey}
```

**Attribution:**
```
Map data &copy; OpenWeatherMap
```

**API Key:** Required
**Free Tier:** Available
**Best Use Case:** Temperature overlay

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tile.openweathermap.org/map/temp_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY"
  attribution='Map data &copy; OpenWeatherMap'
  opacity={0.5}
/>
```

---

### OpenWeatherMap - Wind Speed
**Tile URL:**
```
https://tile.openweathermap.org/map/wind_new/{z}/{x}/{y}.png?appid={apiKey}
```

**Attribution:**
```
Map data &copy; OpenWeatherMap
```

**API Key:** Required
**Free Tier:** Available
**Best Use Case:** Wind speed and direction overlay

**React-Leaflet Example:**
```jsx
<TileLayer
  url="https://tile.openweathermap.org/map/wind_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY"
  attribution='Map data &copy; OpenWeatherMap'
  opacity={0.5}
/>
```

---

## Google Maps (Unofficial - Use with Caution)

**IMPORTANT:** These URLs are against Google Maps Terms of Service. Use at your own risk or use the official Google Maps API with proper authentication.

### Google Satellite
**Tile URL:**
```
http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}
```

**Subdomains:** `['mt0', 'mt1', 'mt2', 'mt3']`

**Max Zoom:** 20
**Notes:** Violates ToS - consider using official API or alternatives

### Google Terrain
**Tile URL:**
```
http://{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}
```

**Subdomains:** `['mt0', 'mt1', 'mt2', 'mt3']`

**Max Zoom:** 20
**Notes:** Violates ToS - consider using official API or alternatives

### Google Hybrid (Satellite + Labels)
**Tile URL:**
```
http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}
```

**Subdomains:** `['mt0', 'mt1', 'mt2', 'mt3']`

**Max Zoom:** 20
**Notes:** Violates ToS - consider using official API or alternatives

### Google Streets
**Tile URL:**
```
http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}
```

**Subdomains:** `['mt0', 'mt1', 'mt2', 'mt3']`

**Max Zoom:** 20
**Notes:** Violates ToS - consider using official API or alternatives

**Recommended Alternative:** Use `leaflet.googleMutant` plugin with proper Google Maps API key for ToS compliance.

---

## Usage Notes & Best Practices

### General Guidelines

1. **Attribution Requirements**: Always include proper attribution. Most providers require it by license.

2. **Tile Usage Policies**: Follow each provider's tile usage policy. Don't abuse free services:
   - Implement caching where possible
   - Use appropriate zoom levels
   - Provide valid User-Agent headers
   - Don't download tiles in bulk

3. **API Keys**: Store API keys securely in environment variables, never commit them to public repositories.

4. **Free Tier Limits**: Monitor your usage to stay within free tier limits. Set up alerts if approaching limits.

5. **Retina/HiDPI Support**: Many providers offer @2x tiles for retina displays (double resolution).

6. **Layer Combinations**: Many specialized layers work best as overlays on base maps:
   - Weather layers
   - OpenRailwayMap
   - OpenSeaMap
   - WaymarkedTrails
   - Hillshade

### React-Leaflet Setup Example

```jsx
import { MapContainer, TileLayer, LayersControl } from 'react-leaflet';

const { BaseLayer, Overlay } = LayersControl;

function Map() {
  return (
    <MapContainer center={[51.505, -0.09]} zoom={13}>
      <LayersControl position="topright">
        {/* Base Layers */}
        <BaseLayer checked name="OpenStreetMap">
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap contributors'
          />
        </BaseLayer>

        <BaseLayer name="ESRI Satellite">
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; Esri'
          />
        </BaseLayer>

        <BaseLayer name="CARTO Dark Matter">
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
            subdomains={['a', 'b', 'c', 'd']}
          />
        </BaseLayer>

        {/* Overlay Layers */}
        <Overlay name="OpenRailwayMap">
          <TileLayer
            url="https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"
            attribution='&copy; OpenRailwayMap'
            opacity={0.7}
          />
        </Overlay>

        <Overlay name="Weather - Clouds">
          <TileLayer
            url="https://tile.openweathermap.org/map/clouds_new/{z}/{x}/{y}.png?appid=YOUR_KEY"
            opacity={0.5}
          />
        </Overlay>
      </LayersControl>
    </MapContainer>
  );
}
```

### Environment Variables (.env.local)

```bash
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token
NEXT_PUBLIC_TOMTOM_API_KEY=your_tomtom_key
NEXT_PUBLIC_THUNDERFOREST_API_KEY=your_thunderforest_key
NEXT_PUBLIC_OPENWEATHERMAP_API_KEY=your_openweather_key
NEXT_PUBLIC_HERE_API_KEY=your_here_key
```

---

## Provider Comparison Table

| Provider | Type | API Key Required | Free Tier | Max Zoom | Best For |
|----------|------|------------------|-----------|----------|----------|
| OpenStreetMap | Street | No | Unlimited | 19 | General purpose maps |
| ESRI World Imagery | Satellite | Yes (free) | Non-commercial | 19 | High-quality satellite |
| Mapbox Satellite | Satellite | Yes | 50k/month | 22 | Modern satellite imagery |
| USGS Imagery | Satellite | No | Unlimited | 16 | US satellite (public domain) |
| Stadia Alidade Satellite | Satellite | No (localhost) | Free tier | 20 | Easy satellite access |
| OpenTopoMap | Terrain | No | Unlimited | 17 | Topographic maps |
| USGS Topo | Terrain | No | Unlimited | 16 | US topo maps |
| CARTO Dark Matter | Street (Dark) | No | Unlimited | 20 | Dark mode base layer |
| CARTO Positron | Street (Light) | No | Unlimited | 20 | Light mode base layer |
| Stamen Watercolor | Artistic | Yes | Free tier | 18 | Artistic visualization |
| CyclOSM | Cycling | No | Fair use | 20 | Cycling infrastructure |
| OpenRailwayMap | Railways | No | Unlimited | 19 | Railway overlay |
| OpenSeaMap | Nautical | No | Unlimited | - | Nautical charts |
| OpenWeatherMap | Weather | Yes | Free tier | - | Weather overlays |
| TomTom | Street/Satellite | Yes | 50k/day | 19-22 | Commercial quality |

---

## Quick Reference

### Best Free Satellite Providers (No API Key)
1. Stadia Alidade Satellite (localhost)
2. USGS Imagery (US only)

### Best Free Satellite Providers (With Free API Key)
1. Mapbox Satellite (50k/month)
2. ESRI World Imagery (non-commercial)
3. TomTom Satellite (50k/day)

### Best Free Street Map Providers
1. OpenStreetMap Standard
2. CARTO Positron/Dark Matter
3. Stadia Alidade Smooth

### Best Dark Mode Providers
1. CARTO Dark Matter (no API key)
2. Stadia Alidade Smooth Dark (localhost free)

### Best Terrain/Topo Providers
1. OpenTopoMap (completely free)
2. USGS Topo (US only, public domain)
3. Thunderforest Landscape (with API key)

---

## Resources

- **Leaflet Providers Preview**: https://leaflet-extras.github.io/leaflet-providers/preview/
- **Leaflet Providers NPM**: https://www.npmjs.com/package/leaflet-providers
- **React-Leaflet Docs**: https://react-leaflet.js.org/
- **OpenStreetMap Tile Usage Policy**: https://operations.osmfoundation.org/policies/tiles/

---

**Last Updated:** January 2025

**Note:** Tile URLs, attribution requirements, and free tier limits may change. Always verify current terms of service before production use.
