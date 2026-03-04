# Treekipedia API Documentation

This document outlines all API endpoints available for the Treekipedia frontend to interact with the backend services. The API provides access to tree species data, user management, leaderboard information, and research functionality.

## Base URL

All API requests should be made to the base URL of the backend server:

```
https://treekipedia-api.silvi.earth
```

---

## Species Endpoints

### Get Species by Search Term

Used for searching tree species by common or scientific name.

**Endpoint:** `GET /species`

**Query Parameters:**
- `search` (required): Search term to match against common_name or species field (scientific name)

**Response:**
```json
[
  {
    "taxon_id": "string",
    "common_name": "string",
    "species": "string",
    "accepted_scientific_name": "string",
    "family": "string",
    "genus": "string",
    // Additional species fields
  }
]
```

**Usage:** Primary search functionality on the homepage and search pages.

---

### Get Species Name Suggestions

Used for autocomplete functionality in search inputs.

**Endpoint:** `GET /species/suggest`

**Query Parameters:**
- `query` (required): Partial term to get suggestions for
- `field` (optional): Specify which field to search in ("common_name" or "species"). If not provided, searches in both fields.

**Response:**
```json
[
  {
    "taxon_id": "string",
    "common_name": "string",
    "species": "string",
    "accepted_scientific_name": "string"
  }
]
```

**Usage:** Powers the autocomplete dropdown in search fields.

---

### Get Species Details

Retrieve comprehensive information about a specific tree species with image data.

**Endpoint:** `GET /species/:taxon_id`

**URL Parameters:**
- `taxon_id` (required): Unique identifier for the species

**Response:**
```json
{
  "taxon_id": "string",
  "common_name": "string",
  "species": "string",
  "accepted_scientific_name": "string",
  "family": "string",
  "genus": "string",
  "general_description": "string",
  "habitat": "string",
  "image_count": "number",
  "primary_image_url": "string",
  "primary_image_license": "string", 
  "primary_image_photographer": "string",
  "primary_image_page_url": "string",
  "primary_image_source": "string",
  // All other species fields
}
```

**Usage:** Display detailed species information on the Species Page with primary image.

**Note:** The `common_name` field may contain very long strings with many names in different languages. When displaying common names in the UI, it's recommended to use the `getTopCommonNames` utility function (located in `/frontend/utils/commonNames.ts` and `/backend/utils/commonNames.js`) to optimize the display. This utility:
1. Properly splits the names by semicolons and commas
2. Prioritizes names based on their position in the list (first names are most important)
3. Ensures linguistic diversity in the displayed names
4. Limits the total character count for API calls and UI display

---

### Get Species Images

Retrieve all images for a specific species (used for image carousel display).

**Endpoint:** `GET /species/:taxon_id/images`

**URL Parameters:**
- `taxon_id` (required): Unique identifier for the species

**Response:**
```json
{
  "taxon_id": "string",
  "image_count": "number",
  "images": [
    {
      "id": "number",
      "taxon_id": "string",
      "image_url": "string",
      "license": "string",
      "photographer": "string",
      "page_url": "string", 
      "source": "string",
      "is_primary": "boolean",
      "created_at": "string"
    }
  ]
}
```

**Usage:** 
- Power image carousels on species pages
- Display image attribution information
- Handle multiple images per species
- Images are ordered with primary image first

**Notes:**
- Returns empty `images` array if species has no images
- `photographer` field may contain HTML formatting for links
- `page_url` should be used for click-through to original image source
- All images are sourced from Wikimedia Commons with proper licensing

---

## Treederboard Endpoints

### Get Leaderboard

Retrieves the top contributors ranked by tree points.

**Endpoint:** `GET /treederboard`

**Query Parameters:**
- `limit` (optional): Maximum number of users to return (default: 20, max: 100)

**Response:**
```json
[
  {
    "id": "number",
    "wallet_address": "string",
    "total_points": "number",
    "contribution_count": "number",
    "first_contribution_at": "string",
    "last_contribution_at": "string"
  }
]
```

**Usage:** Display the Treederboard (leaderboard) page.

---

### Get User Profile

Retrieve a specific user's profile information and NFT collection.

**Endpoint:** `GET /treederboard/user/:wallet_address`

**URL Parameters:**
- `wallet_address` (required): User's blockchain wallet address

**Response:**
```json
{
  "id": "number",
  "wallet_address": "string",
  "total_points": "number",
  "contribution_count": "number",
  "first_contribution_at": "string",
  "last_contribution_at": "string",
  "nfts": [
    {
      "id": "number",
      "global_id": "number",
      "taxon_id": "string",
      "points": "number",
      "ipfs_cid": "string",
      "transaction_hash": "string",
      "created_at": "string"
    }
  ]
}
```

**Usage:** Display user profile page and NFT collection.

---

### Update User Profile

Updates a user's profile information, such as display name.

**Endpoint:** `PUT /treederboard/user/profile`

**Request Body:**
```json
{
  "wallet_address": "string",
  "display_name": "string"
}
```

**Response:**
```json
{
  "id": "number",
  "wallet_address": "string",
  "display_name": "string",
  "total_points": "number",
  "contribution_count": "number"
}
```

**Usage:** Allow users to update their display name for the Treederboard.

---

## Research Endpoints

### Fund Research (Legacy Method - Deprecated)

Initiates AI research for a tree species by funding through an NFT.

**Note:** This endpoint is deprecated in favor of the new payment system. New applications should use the payment contract and sponsorship webhook instead.

**Endpoint:** `POST /research/fund-research`

**Request Body:**
```json
{
  "taxon_id": "string",
  "wallet_address": "string",
  "chain": "string",
  "transaction_hash": "string",
  "ipfs_cid": "string",
  "scientific_name": "string"
}
```

**Parameters:**
- `taxon_id` (required): Unique identifier for the species
- `wallet_address` (required): User's blockchain wallet address
- `chain` (required): Blockchain chain to use for NFT minting - must be one of: `base`, `celo`, `optimism`, `arbitrum`
- `transaction_hash` (required): Transaction hash from the funding transaction
- `ipfs_cid` (optional): IPFS CID for the NFT metadata (can be empty, will be generated by the backend)
- `scientific_name` (required): Value from `species_scientific_name` or `species` field

**Error Responses:**
- `400 Bad Request`: Missing required fields or invalid chain selection
- `404 Not Found`: Species not found with provided taxon_id
- `409 Conflict`: Research for this species has already been funded

**Response:**
```json
{
  "success": true,
  "research_data": {
    "conservation_status": "string",
    "general_description": "string",
    "habitat": "string",
    // Other research fields
  },
  "ipfs_cid": "string",
  "attestation_uid": "string",
  "nft_details": {
    "id": "number",
    "taxon_id": "string",
    "wallet_address": "string",
    "points": "number",
    "ipfs_cid": "string",
    "transaction_hash": "string",
    "metadata": {
      "species": "string",
      "chain": "string",
      "attestation_uid": "string",
      "mint_receipt": "object",
      "research_date": "string"
    }
  }
}
```

**Usage:** This endpoint is now called internally by the sponsorship webhook handler when a payment is confirmed. It is no longer recommended for direct use by frontend applications.

---

### Get Research Data

Retrieve research data for a specific species.

**Endpoint:** `GET /research/research/:taxon_id`

**URL Parameters:**
- `taxon_id` (required): Unique identifier for the species

**Response:**
```json
{
  "taxon_id": "string",
  "species_scientific_name": "string",
  "researched": "boolean",
  "conservation_status_ai": "string",
  "conservation_status_human": "string",
  "general_description_ai": "string",
  "general_description_human": "string",
  "habitat_ai": "string",
  "habitat_human": "string",
  "elevation_ranges_ai": "string",
  "elevation_ranges_human": "string",
  "compatible_soil_types_ai": "string",
  "compatible_soil_types_human": "string",
  "ecological_function_ai": "string",
  "ecological_function_human": "string",
  "native_adapted_habitats_ai": "string",
  "native_adapted_habitats_human": "string",
  "agroforestry_use_cases_ai": "string",
  "agroforestry_use_cases_human": "string",
  "growth_form_ai": "string",
  "growth_form_human": "string",
  "leaf_type_ai": "string",
  "leaf_type_human": "string",
  "deciduous_evergreen_ai": "string",
  "deciduous_evergreen_human": "string",
  "flower_color_ai": "string",
  "flower_color_human": "string",
  "fruit_type_ai": "string",
  "fruit_type_human": "string",
  "bark_characteristics_ai": "string",
  "bark_characteristics_human": "string",
  "maximum_height_ai": "number",
  "maximum_height_human": "number",
  "maximum_diameter_ai": "number",
  "maximum_diameter_human": "number",
  "lifespan_ai": "string",
  "lifespan_human": "string",
  "maximum_tree_age_ai": "number",
  "maximum_tree_age_human": "number",
  "stewardship_best_practices_ai": "string",
  "stewardship_best_practices_human": "string",
  "planting_recipes_ai": "string",
  "planting_recipes_human": "string",
  "pruning_maintenance_ai": "string",
  "pruning_maintenance_human": "string",
  "disease_pest_management_ai": "string",
  "disease_pest_management_human": "string",
  "fire_management_ai": "string",
  "fire_management_human": "string",
  "cultural_significance_ai": "string",
  "cultural_significance_human": "string",
  "verification_status": "string",
  "ipfs_cid": "string"
}
```

**Note:** If a species has no AI research data, this endpoint will return a 404 status code with a message indicating the species needs research.

**Usage:** Display research results on the Species Page.

---

## Server Information Endpoints

### Get Server Status

Basic endpoint to check if the server is running.

**Endpoint:** `GET /`

**Response:**
```json
{
  "message": "Treekipedia Backend is running!"
}
```

### Get API Information

Returns information about available API endpoints.

**Endpoint:** `GET /api`

**Response:**
```json
{
  "message": "Welcome to Treekipedia API",
  "version": "1.0.0",
  "endpoints": [
    "/species - Species search and details",
    "/treederboard - User contributions leaderboard",
    "/research - AI research and NFT minting",
    "/sponsorships - Sponsorship payment tracking and webhooks"
  ]
}
```

---

## Sponsorship Endpoints

### Webhook for Payment Events

Receives webhook events from Infura about sponsorship transactions.

**Endpoint:** `POST /sponsorships/webhook`

**Headers:**
- `x-infura-signature`: HMAC SHA-256 signature to verify authenticity

**Request Body:** (From Infura)
```json
{
  "network": "string",
  "chainId": "string",
  "event": "SponsorshipReceived",
  "transactionHash": "string",
  "args": {
    "sender": "string",
    "taxon_id": "string",
    "amount": "string",
    "transaction_hash": "string"
  }
}
```

**Response:**
```json
{
  "success": true
}
```

**Usage:** This endpoint is called by Infura when a payment is made through the payment contract. It is not meant to be called directly by frontend clients.

---

### Get Sponsorship by Transaction Hash

Retrieve details about a sponsorship by its transaction hash.

**Endpoint:** `GET /sponsorships/transaction/:transaction_hash`

**URL Parameters:**
- `transaction_hash` (required): Transaction hash from the blockchain

**Response:**
```json
{
  "transaction_hash": "string",
  "status": "string",
  "total_amount": "number",
  "wallet_address": "string",
  "chain": "string",
  "payment_timestamp": "string",
  "species_count": "number",
  "completed_count": "number",
  "species": [
    {
      "id": "number",
      "sponsorship_id": "number",
      "taxon_id": "string",
      "amount": "number",
      "research_status": "string",
      "nft_token_id": "number",
      "ipfs_cid": "string",
      "common_name": "string",
      "species_scientific_name": "string"
    }
  ]
}
```

**Usage:** Used to check the status of a payment after submission, typically on the transaction confirmation page.

---

### Get User Sponsorships

Retrieve all sponsorships made by a specific wallet address.

**Endpoint:** `GET /sponsorships/user/:wallet_address`

**URL Parameters:**
- `wallet_address` (required): User's blockchain wallet address

**Query Parameters:**
- `limit` (optional): Maximum number of sponsorships to return (default: 20)
- `offset` (optional): Number of sponsorships to skip (default: 0)

**Response:**
```json
[
  {
    "sponsorship_id": "number",
    "wallet_address": "string",
    "chain": "string",
    "transaction_hash": "string",
    "total_amount": "number",
    "payment_timestamp": "string",
    "payment_status": "string",
    "species_count": "number",
    "completed_count": "number",
    "taxon_ids": ["string"]
  }
]
```

**Usage:** Display a user's sponsorship history on their profile page.

---

### Get Species Sponsorships

Retrieve all sponsorships for a specific species.

**Endpoint:** `GET /sponsorships/species/:taxon_id`

**URL Parameters:**
- `taxon_id` (required): Unique identifier for the species

**Query Parameters:**
- `limit` (optional): Maximum number of sponsorships to return (default: 20)
- `offset` (optional): Number of sponsorships to skip (default: 0)

**Response:**
```json
[
  {
    "id": "number",
    "wallet_address": "string",
    "transaction_hash": "string",
    "chain": "string",
    "total_amount": "number",
    "payment_timestamp": "string",
    "status": "string",
    "research_status": "string",
    "nft_token_id": "number",
    "ipfs_cid": "string"
  }
]
```

**Usage:** Show who has sponsored a particular species on the species details page.

---

## Geospatial API Endpoints

The geospatial API provides location-based queries using PostGIS and level 7 geohash tiles containing compressed species occurrence data.

### Find Species Near Location

Find species occurring within a specified radius of a geographic point.

**Endpoint:** `GET /api/geospatial/species/nearby`

**Query Parameters:**
- `lat` (required): Latitude of the center point
- `lng` (required): Longitude of the center point
- `radius` (optional): Search radius in kilometers (default: 5)

**Response:**
```json
{
  "location": {
    "lat": 37.7749,
    "lng": -122.4194
  },
  "radius_km": 5,
  "species_count": 23,
  "species": [
    {
      "taxon_id": "12345",
      "scientific_name": "Quercus agrifolia",
      "common_name": "Coast Live Oak"
    }
  ]
}
```

**Usage:** Display species found near a user's location or a clicked map point.

---

### Get Species Distribution

Retrieve the geographic distribution of a species as geohash tiles.

**Endpoint:** `GET /api/geospatial/species/:taxon_id/distribution`

**URL Parameters:**
- `taxon_id` (required): Species identifier

**Response:**
```json
{
  "taxon_id": "12345",
  "tile_count": 150,
  "total_occurrences": 3420,
  "distribution": [
    {
      "type": "Feature",
      "properties": {
        "geohash": "dr5ru6j",
        "occurrences": 45,
        "datetime": "2024-12-31T23:59:59Z",
        "data_source": "gbif"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[...]]]
      }
    }
  ]
}
```

**Usage:** Create distribution maps for species pages.

---

### Get Occurrence Heatmap

Get a heatmap of species occurrences within a bounding box.

**Endpoint:** `GET /api/geospatial/heatmap`

**Query Parameters:**
- `minLat` (required): Minimum latitude
- `minLng` (required): Minimum longitude
- `maxLat` (required): Maximum latitude
- `maxLng` (required): Maximum longitude

**Response:**
```json
{
  "bbox": {
    "min": [-123, 37],
    "max": [-122, 38]
  },
  "tile_count": 85,
  "features": [
    {
      "type": "Feature",
      "properties": {
        "geohash": "dr5ru6j",
        "total_occurrences": 234,
        "species_count": 15,
        "datetime": "2024-12-31T23:59:59Z"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[...]]]
      }
    }
  ]
}
```

**Usage:** Generate biodiversity heatmaps for visualization.

---

### Get Species in Tile

Get all species occurring in a specific geohash tile.

**Endpoint:** `GET /api/geospatial/tiles/:geohash`

**URL Parameters:**
- `geohash` (required): Level 7 geohash (exactly 7 characters)

**Response:**
```json
{
  "geohash": "dr5ru6j",
  "tile_info": {
    "total_occurrences": 234,
    "species_count": 15,
    "datetime": "2024-12-31T23:59:59Z",
    "data_source": "gbif",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[...]]]
    }
  },
  "species": [
    {
      "taxon_id": "12345",
      "scientific_name": "Quercus agrifolia",
      "common_name": "Coast Live Oak",
      "occurrence_count": 45
    }
  ]
}
```

**Usage:** Show species details when clicking on a map tile.

---

### Get Tiles by Time Range

STAC-compliant temporal query for geohash tiles.

**Endpoint:** `GET /api/geospatial/tiles`

**Query Parameters:**
- `start` (required): Start date (ISO 8601 format)
- `end` (required): End date (ISO 8601 format)
- `bbox` (optional): Bounding box as "minLng,minLat,maxLng,maxLat"

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "id": "dr5ru6j",
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[...]]]
      },
      "properties": {
        "datetime": "2024-12-31T23:59:59Z",
        "species_count": 15,
        "total_occurrences": 234,
        "data_source": "gbif"
      }
    }
  ],
  "numberReturned": 42,
  "timeRange": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-12-31T23:59:59Z"
  }
}
```

**Usage:** Temporal analysis and STAC-compliant data access.

---

### Get Geospatial Statistics

Get overall statistics about the geospatial data.

**Endpoint:** `GET /api/geospatial/stats`

**Response:**
```json
{
  "tiles": {
    "total": 150000,
    "tile_size_m": 150
  },
  "species": {
    "unique_count": 12500
  },
  "occurrences": {
    "total": 4500000
  },
  "temporal": {
    "earliest": "2020-01-01T00:00:00Z",
    "latest": "2024-12-31T23:59:59Z"
  },
  "spatial": {
    "coverage_km2": 520000,
    "bounding_box": {
      "type": "Polygon",
      "coordinates": [[[...]]]
    }
  },
  "data_sources": ["gbif", "inaturalist", "mixed"]
}
```

**Usage:** Display data coverage and statistics on an about page.

---

### LEAF™ Score - Species Recommendations

Get species recommendations ranked by LEAF™ (Location-based Ecological Aptness Forecast) score for any location. Supports ecoregion ID, point coordinates, or polygon geometry.

**Authentication:** Required (Django JWT via `Authorization: Bearer <token>`)

**Credits:** Polygon requests use area-based cost via `calculateSiteAnalysisCost(hectares)` (10-685 credits). Point and ecoregion requests cost flat 10 credits. Returns 402 with `required`/`balance` on insufficient credits.

**Endpoints:**
- `GET /api/geospatial/leaf/score` - For eco_id or lat/lng queries
- `POST /api/geospatial/leaf/score` - For polygon geometry

**Query Parameters:**
- `eco_id` (optional): Direct ecoregion ID lookup (e.g., "331")
- `lat` (optional): Latitude for point lookup
- `lng` (optional): Longitude for point lookup
- `limit` (optional): Maximum species to return (default: 500)
- `min_score` (optional): Minimum LEAF score threshold (default: 0)

**Request Body (POST only):**
```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-83.5, 35.0], [-82.0, 35.0], [-82.0, 36.5], [-83.5, 36.5], [-83.5, 35.0]]]
  }
}
```

**Response:**
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
      "taxon_id": "AngMaFaFgCx14604-00",
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
    }
  ]
}
```

**Algorithm:**
1. **Pool**: Union of WCVP native species + species with GBIF occurrences
2. **Exclusion**: Species marked as introduced in WCVP are excluded
3. **Affinity**: `occurrence_count × tile_count × native_multiplier`
   - Native species: ×2.0 boost
   - Unknown status: ×1.0 (neutral)
4. **Score**: Percentile rank (0-100) within the pool

**Tier Classification:**
| Tier | Score Range | Meaning |
|------|-------------|---------|
| BEST | 90-100 | Top 10% - Highly recommended |
| GOOD | 70-89 | Next 20% - Appropriate choice |
| ACCEPTABLE | 50-69 | Middle tier - Viable option |
| LOW | <50 | Below threshold |

**Multi-Ecoregion Support:**
For polygons spanning multiple ecoregions, scores are weighted by intersection area. Species appearing in multiple ecoregions show `ecoregion_count > 1`.

**Example Requests:**
```bash
# By ecoregion ID
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?eco_id=331&limit=50"

# By coordinates
curl "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score?lat=35.5951&lng=-82.5515"

# By polygon
curl -X POST "https://treekipedia-api.silvi.earth/api/geospatial/leaf/score" \
  -H "Content-Type: application/json" \
  -d '{"geometry": {"type": "Polygon", "coordinates": [...]}}'
```

**Usage:** Bioregional reforestation campaigns, native species recommendations, ecological restoration planning.

---

## Credit System Endpoints

### Get Credit Balance

**Endpoint:** `GET /api/credits/balance`

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "success": true,
  "balance": 150,
  "lifetime_purchased": 200,
  "lifetime_spent": 50
}
```

New users auto-receive 50 credit signup bonus on first balance check.

---

### Get Transaction History

**Endpoint:** `GET /api/credits/transactions`

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `limit` (optional): Max records (default 50, max 100)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "success": true,
  "transactions": [
    {
      "id": 1,
      "amount": -25,
      "type": "species_research",
      "reference_id": "AngMaApPtTs00001-00",
      "description": "species_research: 25 credits",
      "balance_after": 125,
      "metadata": {"taxon_id": "AngMaApPtTs00001-00"},
      "created_at": "2026-02-27T10:00:00Z"
    }
  ],
  "total": 5,
  "limit": 50,
  "offset": 0
}
```

Transaction types: `purchase`, `signup_bonus`, `site_analysis`, `guide`, `species_research`, `refund`, `admin_grant`

---

### Get Credit Packs

**Endpoint:** `GET /api/credits/packs`

**Authentication:** None

**Response:**
```json
{
  "success": true,
  "packs": [
    {"id": "starter", "name": "Starter", "credits": 100, "price_usd": "10.00"},
    {"id": "pro", "name": "Pro", "credits": 500, "price_usd": "40.00"},
    {"id": "enterprise", "name": "Enterprise", "credits": 2000, "price_usd": "120.00"}
  ]
}
```

---

### Estimate Analysis Cost

**Endpoint:** `POST /api/credits/estimate-analysis`

**Authentication:** None

**Request Body:**
```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lng, lat], ...]]
  }
}
```

**Response:**
```json
{
  "success": true,
  "area_hectares": 42.5,
  "cost_credits": 26
}
```

Cost formula (tiered): 10 credits (≤10ha), scales to 685+ at 10,000+ ha.

---

## Payment Endpoints

### Create Payment Invoice

**Endpoint:** `POST /api/payments/create-invoice`

**Authentication:** Required (Bearer token)

**Request Body:**
```json
{
  "pack_id": "pro"
}
```

**Response:**
```json
{
  "success": true,
  "invoice_url": "https://nowpayments.io/payment/...",
  "invoice_id": 1,
  "pack": {"id": "pro", "name": "Pro", "credits": 500, "price_usd": "40.00"}
}
```

Frontend redirects user to `invoice_url` for crypto payment. On completion, NOWPayments redirects to `/credits?purchased=true`.

---

### NOWPayments Webhook

**Endpoint:** `POST /api/payments/webhooks/nowpayments`

**Authentication:** HMAC-SHA512 signature via `x-nowpayments-sig` header

Automatically grants credits when `payment_status === 'finished'`. Idempotent — duplicate webhooks are safely ignored.

---

## Credit-Gated Endpoints

These existing endpoints now require authentication and deduct credits:

| Endpoint | Credits | Notes |
|----------|---------|-------|
| `POST /api/geospatial/analyze-plot` | **Free** | Public endpoint (optionalAuth for tracking) |
| `GET/POST /api/geospatial/leaf/score` | 10-685 (polygon by area) or 10 flat (point/ecoregion) | Auth required, returns 402 on insufficient |
| `POST /api/guides/ecoregion/:eco_id/synthesize` | 200 flat | |
| `POST /species/:taxon_id/research` | 25 flat | |

All gated responses include `credits_charged` and `balance_after` fields.

**402 Response (insufficient credits):**
```json
{
  "error": "Insufficient credits",
  "required": 25,
  "balance": 10,
  "cost_credits": 25
}
```

---

## Missing API Endpoints

Based on the frontend requirements in the spec sheet, these endpoints may be needed but aren't currently implemented:

1. **User Authentication** - There's no explicit endpoint for authenticating users or verifying wallet connections.

2. **Display Name Retrieval** - While you can update a display name, there's no dedicated endpoint to just retrieve the display name for a wallet address (though it could be included in user profile data).

3. **Chain/Network Information** - An endpoint to retrieve available blockchain networks and their configuration details would be helpful.

4. **NFT Image/Metadata Retrieval** - There's no direct endpoint to fetch NFT images or complete metadata, which would be useful for the Profile page to display the NFTs visually.

These potential gaps should be discussed with the team to determine if they're necessary and how they should be implemented.