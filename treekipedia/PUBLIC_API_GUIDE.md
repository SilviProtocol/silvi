# Treekipedia Public API Guide

**Base URL**: `https://treekipedia-api.silvi.earth`
**Authentication**: None required for LEAF endpoint
**Rate Limit**: No limit (be reasonable)
**Last Updated**: January 2026

---

## LEAF API - Species Recommendations

**LEAF** = **Location-based Ecological Aptness Forecast**

Returns ranked species recommendations for any location on Earth, answering: **"What trees should I plant here?"**

### Endpoint

```
GET  /api/geospatial/leaf/score
POST /api/geospatial/leaf/score
```

### Input Methods (choose one)

| Method | Parameters | Example |
|--------|------------|---------|
| Ecoregion ID | `eco_id` | `?eco_id=331` |
| Ecoregion Name | `eco_name` | `?eco_name=Appalachian-Blue%20Ridge%20forests` |
| Coordinates | `lat`, `lng` | `?lat=35.5&lng=-82.5` |
| Polygon | POST body with `geometry` | GeoJSON Polygon |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 500 | Max species to return |
| `min_score` | float | 0 | Minimum LEAF score (0-100) |

---

## Quick Examples

### cURL

```bash
# By ecoregion ID
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331"

# By ecoregion name
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_name=Appalachian-Blue%20Ridge%20forests"

# By coordinates
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?lat=35.5951&lng=-82.5515"

# Top 50 BEST tier only
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331&limit=50&min_score=90"

# By polygon (POST)
curl -X POST "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score" \
  -H "Content-Type: application/json" \
  -d '{
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[-83.5, 35.0], [-82.0, 35.0], [-82.0, 36.5], [-83.5, 36.5], [-83.5, 35.0]]]
    }
  }'
```

### JavaScript/Node.js

```javascript
// By ecoregion ID
const response = await fetch(
  'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331&limit=100'
);
const data = await response.json();

console.log(`Found ${data.statistics.qualifying_species} species`);
console.log(`Top species: ${data.species[0].scientific_name} (LEAF: ${data.species[0].leaf_score})`);

// Filter to BEST tier natives
const bestNatives = data.species.filter(s => s.tier === 'BEST' && s.is_native);
```

```javascript
// By polygon
const polygon = {
  type: 'Polygon',
  coordinates: [[[-83.5, 35.0], [-82.0, 35.0], [-82.0, 36.5], [-83.5, 36.5], [-83.5, 35.0]]]
};

const response = await fetch(
  'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ geometry: polygon })
  }
);
const data = await response.json();
```

### Python

```python
import requests

# By ecoregion ID
response = requests.get(
    'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score',
    params={'eco_id': 331, 'limit': 100}
)
data = response.json()

print(f"Found {data['statistics']['qualifying_species']} species")
for species in data['species'][:5]:
    print(f"{species['scientific_name']}: {species['leaf_score']} ({species['tier']})")
```

```python
# By polygon
polygon = {
    "type": "Polygon",
    "coordinates": [[[-83.5, 35.0], [-82.0, 35.0], [-82.0, 36.5], [-83.5, 36.5], [-83.5, 35.0]]]
}

response = requests.post(
    'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score',
    json={'geometry': polygon}
)
data = response.json()
```

---

## Response Format

```json
{
  "ecoregions": [
    {
      "eco_id": "331",
      "eco_name": "Appalachian-Blue Ridge forests",
      "biome_name": "Temperate Broadleaf & Mixed Forests",
      "realm": "Nearctic",
      "weight": 1.0
    }
  ],
  "countries": ["United States"],
  "methodology": {
    "version": "1.0",
    "formula": "weighted_affinity = (occurrence_count × tile_count) × native_multiplier",
    "native_boost": 2.0,
    "introduced": "excluded",
    "data_sources": ["GBIF occurrences via geohash tiles", "WCVP native/introduced status"]
  },
  "statistics": {
    "total_in_pool": 3332,
    "introduced_excluded": 497,
    "native_species": 2835,
    "unknown_status": 0,
    "qualifying_species": 500
  },
  "species": [
    {
      "taxon_id": "AngMaSaSpNd47964-00",
      "scientific_name": "Acer rubrum",
      "common_name": "Red Maple",
      "family": "Sapindaceae",
      "genus": "Acer",
      "leaf_score": 100.0,
      "tier": "BEST",
      "is_native": true,
      "occurrence_count": 156789,
      "tile_count": 15234,
      "ecoregion_count": 1
    }
  ]
}
```

### Species Fields

| Field | Type | Description |
|-------|------|-------------|
| `taxon_id` | string | Unique identifier. `-00` = species, `-01`+ = subspecies |
| `scientific_name` | string | Scientific name |
| `common_name` | string | Common name(s), semicolon-separated |
| `family` | string | Taxonomic family |
| `genus` | string | Taxonomic genus |
| `leaf_score` | float | 0-100 percentile rank (higher = better) |
| `tier` | string | BEST (90-100), GOOD (70-89), ACCEPTABLE (50-69), LOW (<50) |
| `is_native` | boolean | True if WCVP lists as native to region |
| `occurrence_count` | integer | Total GBIF occurrences in ecoregion(s) |
| `tile_count` | integer | Number of ~150m geohash tiles with occurrences |
| `ecoregion_count` | integer | Ecoregions where species found (>1 for polygons spanning multiple) |

---

## Algorithm

```
1. POOL = (WCVP native species for region)
         UNION (species with GBIF occurrences in ecoregion)
         MINUS (species marked as introduced in WCVP)

2. AFFINITY = occurrence_count × tile_count × native_multiplier
   - Native species: ×2.0 boost
   - Unknown status: ×1.0 neutral
   - Introduced: EXCLUDED

3. LEAF SCORE = percentile_rank(affinity) × 100

4. TIER = BEST (≥90) | GOOD (≥70) | ACCEPTABLE (≥50) | LOW (<50)
```

A score of 85 means "this species ranks higher than 85% of species in this ecoregion."

---

## Ecoregion Reference

### Priority Bioregional Campaign Ecoregions

| eco_id | eco_name | Region |
|--------|----------|--------|
| 331 | Appalachian-Blue Ridge forests | USA |
| 118 | Central African mangroves | Africa |
| 112 | Cross-Niger transition forests | Nigeria |
| 111 | Cross-Sanaga-Bioko coastal forests | W. Africa |
| 1 | Guinean forest-savanna | W. Africa |
| 113 | Niger Delta swamp forests | Nigeria |
| 110 | Nigerian lowland forests | Nigeria |
| 586 | Dry Chaco | S. America |
| 578 | Southern Andean Yungas | Argentina/Bolivia |
| 571 | Eastern Cordillera Real montane forests | S. America |
| 569 | Serra do Mar coastal forests | Brazil |
| 490 | Tyrrhenian-Adriatic sclerophyllous forests | Mediterranean |

### Find Ecoregion for Coordinates

```bash
curl "https://treekipedia-api.silvi.earth/api/geospatial/ecoregions/at-point?lat=35.5&lng=-82.5"
```

Returns:
```json
{
  "location": { "lat": 35.5, "lng": -82.5 },
  "ecoregion": {
    "eco_id": "331",
    "eco_name": "Appalachian-Blue Ridge forests",
    "biome_name": "Temperate Broadleaf & Mixed Forests",
    "realm": "Nearctic",
    "area_km2": 163311
  }
}
```

---

## Data Coverage

| Metric | Value |
|--------|-------|
| Species | 67,927 |
| Geohash tiles | 6.46M (Level 7, ~150m resolution) |
| Occurrences | 96.5M |
| WWF Ecoregions | 847 |
| Ecoregion coverage | 97.2% of tiles |
| WCVP native status | 97.5% of species |
| WCVP introduced status | 8.4% of species |

---

## Common Use Cases

### Get Top Native Species for Reforestation

```javascript
const response = await fetch(
  'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331&min_score=90'
);
const { species } = await response.json();

// Filter to confirmed natives only
const natives = species.filter(s => s.is_native);
console.log(`Top ${natives.length} native species for planting`);
```

### Analyze a Project Site Polygon

```javascript
const sitePolygon = {
  type: 'Polygon',
  coordinates: [/* your site boundary coordinates */]
};

const response = await fetch(
  'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?limit=100',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ geometry: sitePolygon })
  }
);

const data = await response.json();
// Multi-ecoregion sites will show weighted scores
console.log(`Site spans ${data.ecoregions.length} ecoregion(s)`);
```

### Export Species List as CSV

```javascript
const response = await fetch(
  'https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331'
);
const { species } = await response.json();

// Convert to CSV
const csv = [
  'taxon_id,scientific_name,common_name,family,leaf_score,tier,is_native',
  ...species.map(s =>
    `${s.taxon_id},"${s.scientific_name}","${s.common_name || ''}",${s.family},${s.leaf_score},${s.tier},${s.is_native}`
  )
].join('\n');

// Write to file or download
```

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Missing required parameters |
| 404 | Ecoregion not found / No ecoregion at coordinates |
| 500 | Server error |

Example error:
```json
{
  "error": "Must provide one of: eco_id, eco_name, lat/lng coordinates, or GeoJSON geometry in request body"
}
```

---

## Notes

- Response time: typically 2-5 seconds depending on ecoregion size
- Species are sorted by `leaf_score` descending (best recommendations first)
- Introduced species (e.g., Tree of Heaven, Mimosa) are automatically excluded
- For polygons spanning multiple ecoregions, scores are weighted by intersection area
- The `ecoregion_count` field helps identify species present across multiple ecoregions

---

## Related Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/geospatial/ecoregions/at-point?lat=&lng=` | Find ecoregion for coordinates |
| `GET /species/:taxon_id` | Get full species details |
| `GET /species?search=` | Search species by name |

---

## Contact

- API: https://treekipedia-api.silvi.earth
- Frontend: https://treekipedia.silvi.earth
- Repository: https://github.com/silvi-open/treekipedia
