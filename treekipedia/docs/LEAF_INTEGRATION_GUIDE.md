# LEAF API Integration Guide

**For**: Silvi Protocol Integration
**Endpoint**: `https://treekipedia-api.silvi.earth/api/geospatial/leaf/score`
**Last Updated**: December 2025

---

## What is LEAF?

**LEAF** = **Location-based Ecological Aptness Forecast**

LEAF answers the question: **"What trees should I plant here?"**

It provides scientifically-grounded species recommendations for any location on Earth, combining:
- **89.3M GBIF species occurrences** (where species actually grow)
- **WCVP native/introduced status** (authoritative Kew Gardens data)
- **847 WWF ecoregions** (ecological boundaries)

---

## Quick Start

### By Ecoregion Name
```bash
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_name=Appalachian-Blue%20Ridge%20forests"
```

### By Ecoregion ID
```bash
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331"
```

### By Coordinates
```bash
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?lat=35.5951&lng=-82.5515"
```

---

## API Reference

### Endpoint
```
GET  https://treekipedia-api.silvi.earth/api/geospatial/leaf/score
POST https://treekipedia-api.silvi.earth/api/geospatial/leaf/score
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `eco_id` | integer | One of these | WWF ecoregion ID (e.g., `331`) |
| `eco_name` | string | required | Exact ecoregion name (e.g., `Appalachian-Blue Ridge forests`) |
| `lat` | float | | Latitude for point lookup |
| `lng` | float | | Longitude for point lookup |
| `limit` | integer | No | Max species to return (default: 500) |
| `min_score` | float | No | Minimum LEAF score filter (default: 0) |

**Note**: Provide ONE of: `eco_id`, `eco_name`, `lat`+`lng`, or POST with geometry.

### POST Body (for polygons)
```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lng1, lat1], [lng2, lat2], ...]]
  }
}
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
    "total_in_pool": 3292,
    "introduced_excluded": 468,
    "native_species": 98,
    "unknown_status": 2,
    "qualifying_species": 100
  },
  "species": [
    {
      "taxon_id": "AngMaFaFaLg47652-00",
      "scientific_name": "Quercus alba",
      "common_name": "White Oak",
      "family": "Fagaceae",
      "genus": "Quercus",
      "leaf_score": 100.0,
      "tier": "BEST",
      "is_native": true,
      "occurrence_count": 120816,
      "tile_count": 12307,
      "ecoregion_count": 1
    },
    ...
  ]
}
```

### Species Fields

| Field | Type | Description |
|-------|------|-------------|
| `taxon_id` | string | Unique species identifier. Suffix `-00` = species, `-01`+ = subspecies |
| `scientific_name` | string | Scientific name (will migrate to `taxon_full` in future) |
| `common_name` | string | Common name(s), semicolon-separated |
| `family` | string | Taxonomic family |
| `genus` | string | Taxonomic genus |
| `leaf_score` | float | 0-100 percentile score (higher = more recommended) |
| `tier` | string | `BEST` (90-100), `GOOD` (70-89), `ACCEPTABLE` (50-69), `LOW` (<50) |
| `is_native` | boolean | True if WCVP lists as native to region |
| `occurrence_count` | integer | Total GBIF occurrences in ecoregion |
| `tile_count` | integer | Number of ~150m tiles where species observed |
| `ecoregion_count` | integer | Number of ecoregions (>1 for polygon queries) |

---

## The LEAF Algorithm

### Step 1: Build Species Pool
```
Pool = (WCVP native species for region)
       UNION
       (All species with GBIF occurrences in ecoregion)
       MINUS
       (Species marked as introduced in WCVP)
```

### Step 2: Calculate Weighted Affinity
```
For species with occurrences:
  base_affinity = occurrence_count × tile_count
  weighted_affinity = base_affinity × native_multiplier

For WCVP-only natives (no occurrences):
  weighted_affinity = 100 × native_multiplier

Where:
  native_multiplier = 2.0 (native species)
                      1.0 (unknown status)
```

### Step 3: Convert to Percentile Score
```
LEAF Score = percentile_rank(weighted_affinity) × 100
```

A score of 85 means "this species ranks higher than 85% of species in this ecoregion."

### Step 4: Assign Tier
| Tier | Score Range | Meaning |
|------|-------------|---------|
| **BEST** | 90-100 | Top 10% - Highly recommended |
| **GOOD** | 70-89 | Next 20% - Appropriate choice |
| **ACCEPTABLE** | 50-69 | Middle tier - Viable option |
| **LOW** | <50 | Below threshold |

---

## Target Ecoregions (12 Bioregional Campaigns)

These are the priority ecoregions for the $100K bioregional campaigns:

| Ecoregion Name | eco_id | Region |
|----------------|--------|--------|
| Appalachian-Blue Ridge forests | 331 | USA |
| Central African mangroves | 118 | Africa |
| Cross-Niger transition forests | 112 | Nigeria |
| Cross-Sanaga-Bioko coastal forests | 111 | W. Africa |
| Guinean forest-savanna | 1 | W. Africa |
| Niger Delta swamp forests | 113 | Nigeria |
| Nigerian lowland forests | 110 | Nigeria |
| Dry Chaco | 586 | S. America |
| Southern Andean Yungas | 578 | Argentina/Bolivia |
| Eastern Cordillera Real montane forests | 571 | S. America |
| Serra do Mar coastal forests | 569 | Brazil |
| Tyrrhenian-Adriatic sclerophyllous forests | 490 | Mediterranean |

---

## Example: Generate Species List for Ecoregion

```bash
# Get top 200 species for Appalachian-Blue Ridge, BEST tier only
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_name=Appalachian-Blue%20Ridge%20forests&limit=200&min_score=90" \
  | jq '.species[] | {taxon_id, scientific_name, common_name, leaf_score, tier}'
```

### Expected Output
```json
{
  "taxon_id": "AngMaFaFaLg47652-00",
  "scientific_name": "Quercus alba",
  "common_name": "White Oak",
  "leaf_score": 100.0,
  "tier": "BEST"
}
{
  "taxon_id": "AngMaSaSpNd47964-00",
  "scientific_name": "Acer rubrum",
  "common_name": "Red Maple",
  "leaf_score": 100.0,
  "tier": "BEST"
}
...
```

---

## Lookup Ecoregion IDs

To find the eco_id for an ecoregion name:

```bash
# Search by partial name
curl "https://treekipedia-api.silvi.earth/api/geospatial/ecoregions/at-point?lat=35.5&lng=-82.5"
```

Or query the database directly:
```sql
SELECT eco_id, eco_name, biome_name, realm
FROM ecoregions
WHERE eco_name ILIKE '%chaco%';
```

---

## Notes

- **No authentication required** for this endpoint
- Response time: typically 2-5 seconds depending on ecoregion size
- Species are sorted by `leaf_score` descending (best first)
- Introduced species (invasives like Tree of Heaven, Mimosa) are automatically excluded
- For polygons spanning multiple ecoregions, scores are weighted by intersection area

---

## Contact

API Base URL: `https://treekipedia-api.silvi.earth`
Documentation: `https://github.com/silvi-open/treekipedia`
