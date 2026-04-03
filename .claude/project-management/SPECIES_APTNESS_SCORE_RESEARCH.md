# Species Aptness Score System: Comprehensive Research Report

**Date**: January 19, 2026
**Project**: Treekipedia Species Recommender
**Status**: Research & Planning Phase

---

## Executive Summary

This report analyzes the current LEAF score system and proposes an enhanced "Species Aptness Score" that integrates environmental matching, habitat heterogeneity, and the existing AlphaEarth-based prediction system. The goal is to move from "what trees ARE/WERE here" (predictor) to "how WELL-SUITED is this species for planting" (recommender).

**Key Finding**: The existing infrastructure provides an excellent foundation. We have:
- **LEAF score** (0-100 percentile) for native status + occurrence density
- **AlphaEarth embeddings** (64-D) for habitat matching via cosine similarity
- **Climate/soil data** in species table (Köppen-Geiger, precipitation, temperature)
- **500 species centroids** already extracted with 5 habitats each

**Recommendation**: Build a weighted composite score that combines these existing assets rather than importing massive new datasets.

---

## 1. Current LEAF Score Analysis

### 1.1 What LEAF Does Well

The LEAF™ (Location-based Ecological Aptness Forecast) system provides:

**Algorithm**:
```
Species Pool = (WCVP native species) ∪ (species with GBIF occurrences)
               − (WCVP introduced species)

Weighted Affinity = occurrence_count × tile_count × native_multiplier

Where:
  native_multiplier = 2.0 (native species)
                    = 1.0 (unknown status)
                    = 0   (introduced → excluded)

LEAF Score = percentile_rank(weighted_affinity) × 100
```

**Strengths**:
- ✅ Native/introduced filtering using authoritative WCVP data
- ✅ Occurrence-based (89.3M GBIF records via 5.3M geohash tiles)
- ✅ Percentile scoring (0-100 scale, easy to interpret)
- ✅ Ecoregion-specific (fair comparison within biogeographic zones)
- ✅ Already excludes invasives

### 1.2 LEAF Limitations

**What LEAF doesn't consider**:
1. **Environmental matching**: Climate/soil compatibility beyond occurrence
2. **Habitat heterogeneity**: Assumes homogeneous conditions within ecoregion
3. **Elevation matching**: Species may occur in ecoregion but at different elevations
4. **Microclimate suitability**: Local site conditions vs. regional patterns
5. **Restoration strategy**: Pioneer vs. climax, agroforestry vs. rewilding

---

## 2. Available Environmental Data

### 2.1 Already in Database (V11 Schema)

#### Climate Data (8 fields):
- `climate_type_koppengeiger` - Köppen-Geiger classification
- `annual_temperature_range_c` - Temperature range (°C)
- `annual_precipitation_mm` - Annual precipitation
- `precipitation_seasonality_cv` - Seasonality coefficient

#### Soil Data (12 fields):
- `soil_texture_all/dominant/preferred/tolerated`
- `ph_all/dominant/preferred/tolerated`
- `oc_all/dominant/preferred/tolerated` (Organic carbon)

#### Ecological Context:
- `habitat_ai/habitat_human`
- `elevation_ranges_ai/elevation_ranges_human`
- `native_adapted_habitats_ai/_human`
- `compatible_soil_types_ai/_human`
- `ecoregions` (semicolon-separated)
- `biomes`

#### WCVP Native/Introduced:
- `wcvp_native` - 97.5% coverage
- `wcvp_introduced` - 8.4% coverage

---

## 3. Free Environmental Datasets (All in GEE)

| Dataset | Resolution | GEE Asset | Use Case |
|---------|------------|-----------|----------|
| **WorldClim v2.1** | ~1km | `WORLDCLIM/V1/BIO` | 19 bioclimatic variables |
| **SRTM Elevation** | 30m | `USGS/SRTMGL1_003` | Elevation + terrain derivatives |
| **SoilGrids 250m** | 250m | `projects/soilgrids-isric/*` | pH, texture, organic carbon |
| **Hansen Forest** | 30m | `UMD/hansen/global_forest_change_2024_v1_12` | Forest loss year |
| **Global Surface Water** | 30m | `JRC/GSW1_4/GlobalSurfaceWater` | Wetland/riparian detection |
| **HydroSHEDS** | 90m | `WWF/HydroSHEDS/*` | Distance to water |

**Total Additional Storage Required**: **0 GB** (all queried on-demand via GEE)

---

## 4. Heterogeneity Problem & Solution

### The Challenge
- Homogeneous areas (flat Amazon) vs. heterogeneous areas (mountain valleys)
- LEAF is ecoregion-wide but species occupy specific niches
- Example: Water Tupelo has high LEAF in Appalachia but only grows in swamps

### Solution: Weighted Multi-Scale Sampling

Simple 3×3 grid at 100m is too small (only 300m). Better approach with distance-weighted rings:

```python
def compute_heterogeneity(lat, lon):
    """
    Multi-scale sampling with distance-weighted contributions.
    Captures both microhabitat (100m) and landscape context (1km).
    """
    samples = []

    # Inner ring: 100m spacing, 3×3 grid = 9 points, weight 1.0
    for dx in [-100, 0, 100]:
        for dy in [-100, 0, 100]:
            emb = sample_alphaearth(lat + dy/111000, lon + dx/111000)
            samples.append({'embedding': emb, 'weight': 1.0, 'distance': 100})

    # Middle ring: 500m radius, 8 cardinal+diagonal points, weight 0.5
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        dx = 500 * cos(radians(angle))
        dy = 500 * sin(radians(angle))
        emb = sample_alphaearth(lat + dy/111000, lon + dx/111000)
        samples.append({'embedding': emb, 'weight': 0.5, 'distance': 500})

    # Outer ring: 1km radius, 8 points, weight 0.25
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        dx = 1000 * cos(radians(angle))
        dy = 1000 * sin(radians(angle))
        emb = sample_alphaearth(lat + dy/111000, lon + dx/111000)
        samples.append({'embedding': emb, 'weight': 0.25, 'distance': 1000})

    # Total: 25 points covering ~1km radius

    # Compute weighted variance
    weighted_embeddings = [s['embedding'] * s['weight'] for s in samples]
    total_weight = sum(s['weight'] for s in samples)

    weighted_variance = compute_weighted_variance(weighted_embeddings, total_weight)

    # Convert to confidence score
    if weighted_variance > 0.05:  # High heterogeneity
        return 0.7, 'HIGH_HETEROGENEITY'
    elif weighted_variance > 0.02:  # Medium
        return 0.85, 'MEDIUM_HETEROGENEITY'
    else:  # Homogeneous
        return 1.0, 'LOW_HETEROGENEITY'
```

**Why 25 points?**
- Inner ring (9 pts): Microhabitat - immediate surroundings
- Middle ring (8 pts): Local landscape - 500m context
- Outer ring (8 pts): Regional landscape - 1km context
- Diminishing weights capture "relevance decreases with distance"

---

## 5. Proposed Aptness Score Formula

### 5.1 Multi-Factor Weighted Approach

```python
def calculate_aptness_score(species, location, strategy='rewilding'):
    """
    Calculate comprehensive species aptness score (0-100)
    """

    # Factor 1: Habitat Similarity (AlphaEarth) - 25%
    embedding = sample_alphaearth(location)
    habitat_similarity = cosine_similarity(embedding, species.centroids)

    # Factor 2: LEAF Score (Native + Occurrence) - 20%
    leaf_score = query_leaf_score(ecoregion, species.taxon_id) / 100.0

    # Factor 3: Climate Compatibility - 20%
    site_climate = query_worldclim(location)
    species_climate = get_species_climate_prefs(species)
    climate_match = compute_climate_overlap(site_climate, species_climate)

    # Factor 4: Elevation Compatibility - 10%
    site_elevation = query_srtm(location)
    elevation_match = check_elevation_range(site_elevation, species.elevation_ranges)

    # Factor 5: Soil Compatibility - 10%
    site_soil = query_soilgrids(location)
    soil_match = compute_soil_match(site_soil, species.soil_prefs)

    # Factor 6: Ecosystem Proximity - 15%
    nearby_forest = find_nearby_intact_forest(location, radius_km=50)
    proximity_boost = 1.0 if species in nearby_forest.species else 0.5

    # Base score (additive)
    base_score = (
        habitat_similarity * 0.25 +
        leaf_score * 0.20 +
        climate_match * 0.20 +
        elevation_match * 0.10 +
        soil_match * 0.10 +
        proximity_boost * 0.15
    )

    # Multiplicative adjustments
    heterogeneity_confidence = compute_heterogeneity(location)  # 0.7-1.0
    strategy_weight = get_strategy_weight(species, strategy)     # 0.5-1.5

    aptness_score = base_score * heterogeneity_confidence * strategy_weight * 100

    return min(100, aptness_score)
```

### 5.2 Revised Factor List (Including Missing Factors)

| Factor | Weight | Data Source | Notes |
|--------|--------|-------------|-------|
| **Habitat Similarity** | 20% | AlphaEarth cosine | Core spectral match |
| **LEAF Score** | 15% | Existing endpoint | Native + occurrence |
| **Climate Match** | 15% | WorldClim via GEE | Temp, precip, Köppen |
| **Elevation Match** | 10% | SRTM via GEE | Species range vs site |
| **Soil Match** | 10% | SoilGrids via GEE | pH, texture |
| **Ecoregion Match** | 10% | DB ecoregions field | Explicit ecoregion check |
| **Land Type Match** | 10% | Derive from embedding | Wetland/ridge/valley/etc |
| **Ecological Function** | 5% | DB growth_form field | Pioneer vs climax |
| **Proximity to Occurrences** | 5% | Geohash tiles | Species in nearby tiles |

**Note on AlphaEarth and Proximity:**
AlphaEarth embeddings capture spectral/vegetation characteristics but do NOT encode:
- "Species X observed 5km away" (occurrence data)
- Distance to intact forest
- Occurrence density

So proximity factors remain valuable - they're occurrence-based, not spectral-based.

### 5.3 Additional Factors Explained

#### Ecoregion Match
```python
def ecoregion_match(species, location):
    """Check if species' known ecoregions include this location's ecoregion."""
    site_ecoregion = get_ecoregion(location)  # From WWF layer
    species_ecoregions = parse_list(species.ecoregions)  # From DB

    if site_ecoregion in species_ecoregions:
        return 1.0  # Perfect match
    elif same_biome(site_ecoregion, species_ecoregions):
        return 0.5  # Same biome, different ecoregion
    else:
        return 0.1  # Different biome (penalize but don't exclude)
```

#### Land Type Match
```python
def land_type_match(species, location):
    """
    Detect microhabitat type from AlphaEarth + terrain derivatives.
    Match against species habitat preferences.
    """
    # Derive land type from:
    # - TWI (Topographic Wetness Index) → wetland detection
    # - TPI (Topographic Position Index) → ridge/valley classification
    # - Slope → flat/steep
    # - Distance to water → riparian

    site_land_type = classify_land_type(location)
    # Returns: 'wetland', 'riparian', 'ridge', 'valley', 'slope', 'flat_upland'

    species_habitats = parse_habitats(species.habitat_ai or species.native_adapted_habitats_ai)

    if site_land_type in species_habitats:
        return 1.0
    elif compatible_habitat(site_land_type, species_habitats):
        return 0.6
    else:
        return 0.2
```

#### Ecological Function Group
```python
def ecological_function_match(species, site_condition, strategy):
    """
    Match species' ecological role to site needs and restoration strategy.
    """
    species_role = classify_ecological_role(species)
    # Based on: growth_form, lifespan, shade_tolerance, nitrogen_fixing

    # Roles: 'pioneer', 'early_successional', 'mid_successional', 'climax'

    if strategy == 'rewilding':
        if site_condition == 'bare_soil' and species_role == 'pioneer':
            return 1.2  # Boost pioneers on degraded land
        elif site_condition == 'young_forest' and species_role == 'climax':
            return 1.0  # Climax species for enrichment
    elif strategy == 'agroforestry':
        # Favor productive species regardless of succession
        return 1.0
    # ...

    return 1.0  # Default neutral
```

---

## 5.4 Continuous Boundary Analysis (NEW)

### The Core Insight

**Data from within a continuous ecological boundary is more trustworthy than data from fragmented areas.**

Example scenarios:
- Species occurrence 10km away **within same continuous forest** → HIGH confidence
- Species occurrence 10km away **across river/mountain/farmland** → LOWER confidence
- Species occurrence 50km away **but same continuous Atlantic Forest remnant** → MEDIUM-HIGH confidence

This is critical for the **Recommender** when dealing with:
1. Deforested areas - where was the continuous forest before?
2. Historical reconstruction - what was connected vs isolated?
3. Edge effects - interior species vs edge species

### Available Boundary Data

#### Already in PostgreSQL Database

| Boundary Type | Table | Records | Use Case |
|---------------|-------|---------|----------|
| **Intact Forest Landscapes** | `intact_forest_landscapes_2021` | 6,819 polygons | Undisturbed forest patches >500km² |
| **Ecoregions** | `ecoregions` | 847 polygons | WWF biogeographic boundaries |
| **Intact Forest Tiles** | `intact_forest_z*` | Multiple zoom levels | Tiled for fast queries |

#### Available in GEE (Free)

| Dataset | Asset ID | Use Case |
|---------|----------|----------|
| **IUCN Ecosystem Functional Groups** | `IUCN/GlobalEcosystemTypology/current` | 110 functional ecosystem types |
| **HydroSHEDS Basins** | `WWF/HydroSHEDS/v1/Basins/hybas_*` | Watershed boundaries (levels 1-12) |
| **Hansen Forest Change** | `UMD/hansen/global_forest_change_2024_v1_12` | Forest cover for connectivity analysis |
| **HydroSHEDS Rivers** | `WWF/HydroSHEDS/v1/FreeFlowingRivers` | River network barriers |

### IUCN Global Ecosystem Typology (GET) - KEY ADDITION

**Source**: [IUCN GET in GEE](https://developers.google.com/earth-engine/datasets/catalog/IUCN_GlobalEcosystemTypology_current)

The [IUCN Global Ecosystem Typology](https://global-ecosystems.org/) provides a **function-based classification** of Earth's ecosystems:

**Hierarchy:**
- **Level 1**: 5 Realms (Terrestrial, Freshwater, Marine, Subterranean, Transitional)
- **Level 2**: 25 Biomes (e.g., T1 Tropical Forests, T2 Temperate Forests)
- **Level 3**: 110 Ecosystem Functional Groups (EFGs)

**Terrestrial Forest EFGs (most relevant for Treekipedia):**

| Code | Ecosystem Functional Group | Key Characteristics |
|------|---------------------------|---------------------|
| **T1.1** | Tropical/subtropical lowland rainforests | High rainfall, tall canopy, high diversity |
| **T1.2** | Tropical/subtropical dry forests | Seasonal drought, deciduous canopy |
| **T1.3** | Tropical/subtropical montane rainforests | Cloud forests, cooler temps, epiphytes |
| **T1.4** | Tropical heath forests | Nutrient-poor soils, stunted growth |
| **T2.1** | Boreal/temperate montane forests | Cold, coniferous, fire-adapted |
| **T2.2** | Deciduous temperate forests | Seasonal leaf drop, broadleaf |
| **T2.3** | Oceanic cool temperate rainforests | High moisture, ferns, mosses |
| **T2.4** | Warm temperate laurophyll forests | Evergreen broadleaf, mild climate |
| **T2.5** | Temperate pyric humid forests | Fire-dependent, eucalyptus-type |
| **T2.6** | Temperate pyric sclerophyll forests | Mediterranean-type, drought+fire |
| **T4.4** | Temperate woodlands | Open canopy, grass understory |

**Why This is Critical:**

1. **Function-based matching**: Species in T1.1 (lowland rainforest) have different traits than T1.3 (montane rainforest)
2. **Finer than ecoregion**: Same ecoregion can contain multiple EFGs (valley vs ridge)
3. **Restoration guidance**: EFG tells you what ecosystem TYPE to restore to
4. **Species filtering**: Only recommend species known from compatible EFGs

**GEE Query Example:**
```python
# Get EFG at a location
efg_collection = ee.FeatureCollection('IUCN/GlobalEcosystemTypology/current')
point = ee.Geometry.Point([lon, lat])
efg = efg_collection.filterBounds(point).first()
efg_code = efg.get('efg_code')  # e.g., 'T1.1'
occurrence = efg.get('occurrence')  # 1=major, 2=minor
```

### Continuous Boundary Scoring Algorithm

```python
def continuous_boundary_score(target_location, occurrence_location, species):
    """
    Score how "connected" an occurrence is to the target location.
    Higher score = more confident the occurrence data is relevant.

    Returns: 0.0 - 1.0 (confidence multiplier)
    """

    # Check multiple boundary types
    scores = []

    # 1. Intact Forest Landscape (IFL) - strongest signal
    target_ifl = get_containing_ifl(target_location)
    occurrence_ifl = get_containing_ifl(occurrence_location)

    if target_ifl and occurrence_ifl:
        if target_ifl == occurrence_ifl:
            scores.append(('ifl_same', 1.0))  # Same intact forest
        else:
            scores.append(('ifl_different', 0.5))  # Different IFLs
    elif target_ifl or occurrence_ifl:
        scores.append(('ifl_partial', 0.6))  # One in IFL, one not
    else:
        scores.append(('ifl_none', 0.4))  # Neither in IFL

    # 2. Connected Forest Patch (from Hansen)
    same_forest_patch = check_forest_connectivity(
        target_location, occurrence_location,
        min_treecover=25  # % canopy threshold
    )
    if same_forest_patch:
        scores.append(('forest_connected', 1.0))
    else:
        # Check if forest existed historically but is now fragmented
        historical_connection = check_historical_forest_connectivity(
            target_location, occurrence_location,
            year=2000  # Hansen baseline
        )
        if historical_connection:
            scores.append(('forest_historical', 0.7))
        else:
            scores.append(('forest_fragmented', 0.4))

    # 3. Same Watershed/Catchment
    target_basin = get_hydrosheds_basin(target_location, level=7)
    occurrence_basin = get_hydrosheds_basin(occurrence_location, level=7)

    if target_basin == occurrence_basin:
        scores.append(('watershed_same', 0.9))
    elif same_parent_basin(target_basin, occurrence_basin, level=5):
        scores.append(('watershed_parent', 0.7))
    else:
        scores.append(('watershed_different', 0.5))

    # 4. Same Ecoregion (already have this)
    target_eco = get_ecoregion(target_location)
    occurrence_eco = get_ecoregion(occurrence_location)

    if target_eco == occurrence_eco:
        scores.append(('ecoregion_same', 0.9))
    elif same_biome(target_eco, occurrence_eco):
        scores.append(('ecoregion_biome', 0.6))
    else:
        scores.append(('ecoregion_different', 0.3))

    # 4b. Same Ecosystem Functional Group (NEW - from IUCN GET)
    target_efg = get_ecosystem_functional_group(target_location)  # e.g., 'T1.1'
    occurrence_efg = get_ecosystem_functional_group(occurrence_location)

    if target_efg == occurrence_efg:
        scores.append(('efg_same', 1.0))  # Same functional group = very confident
    elif same_biome_code(target_efg, occurrence_efg):  # e.g., T1.1 vs T1.3
        scores.append(('efg_biome', 0.7))  # Same biome, different function
    elif same_realm(target_efg, occurrence_efg):  # e.g., T1.1 vs T2.2
        scores.append(('efg_realm', 0.4))  # Same realm (Terrestrial)
    else:
        scores.append(('efg_different', 0.2))  # Different realm entirely

    # 5. Elevation Band Continuity
    target_elev = get_elevation(target_location)
    occurrence_elev = get_elevation(occurrence_location)
    elev_diff = abs(target_elev - occurrence_elev)

    if elev_diff <= 100:
        scores.append(('elevation_same', 1.0))
    elif elev_diff <= 300:
        scores.append(('elevation_close', 0.8))
    elif elev_diff <= 500:
        scores.append(('elevation_moderate', 0.6))
    else:
        scores.append(('elevation_different', 0.3))

    # 6. Check for Barriers
    barriers = detect_barriers(target_location, occurrence_location)
    # Returns: ['river', 'mountain_ridge', 'urban', 'highway', etc.]

    barrier_penalty = 1.0
    for barrier in barriers:
        if barrier == 'major_river':
            barrier_penalty *= 0.7
        elif barrier == 'mountain_ridge':
            barrier_penalty *= 0.6
        elif barrier == 'urban_area':
            barrier_penalty *= 0.5
        elif barrier == 'highway':
            barrier_penalty *= 0.9

    scores.append(('barriers', barrier_penalty))

    # Weighted combination (now includes EFG)
    weights = {
        'ifl': 0.15,        # Intact forest landscape
        'forest': 0.20,     # Connected forest patch
        'watershed': 0.10,  # Hydrological connection
        'ecoregion': 0.10,  # Biogeographic zone
        'efg': 0.20,        # Ecosystem Functional Group (NEW - high weight)
        'elevation': 0.15,  # Altitudinal band
        'barriers': 0.10    # Physical barriers
    }

    # Aggregate scores by category
    category_scores = {}
    for name, value in scores:
        category = name.split('_')[0]
        category_scores[category] = value

    final_score = sum(
        category_scores.get(cat, 0.5) * weight
        for cat, weight in weights.items()
    )

    return final_score, dict(scores)  # Return score + breakdown
```

### How This Integrates with Aptness Score

The continuous boundary score becomes a **confidence multiplier** on proximity-based factors:

```python
def calculate_aptness_score_v2(species, location, strategy='rewilding'):
    """
    Enhanced aptness score with continuous boundary analysis.
    """

    # Get nearby occurrences for this species
    nearby_occurrences = get_species_occurrences(
        species.taxon_id,
        near=location,
        radius_km=100
    )

    # Score each occurrence by boundary continuity
    weighted_occurrences = []
    for occ in nearby_occurrences:
        boundary_score, breakdown = continuous_boundary_score(
            target_location=location,
            occurrence_location=occ,
            species=species
        )
        weighted_occurrences.append({
            'occurrence': occ,
            'boundary_score': boundary_score,
            'distance_km': haversine(location, occ),
            'effective_weight': boundary_score / (1 + occ.distance_km / 10)
        })

    # Use boundary-weighted occurrences for proximity factor
    if weighted_occurrences:
        best_occurrence = max(weighted_occurrences, key=lambda x: x['effective_weight'])
        proximity_factor = best_occurrence['effective_weight']
        boundary_confidence = best_occurrence['boundary_score']
    else:
        proximity_factor = 0.0
        boundary_confidence = 0.5  # No data = uncertain

    # Standard factors...
    habitat_similarity = ...
    leaf_score = ...
    climate_match = ...
    elevation_match = ...
    soil_match = ...
    ecoregion_match = ...
    landtype_match = ...
    ecological_function = ...

    # Base score with continuous boundary as a factor
    base_score = (
        habitat_similarity * 0.18 +
        leaf_score * 0.12 +
        climate_match * 0.12 +
        elevation_match * 0.08 +
        soil_match * 0.08 +
        ecoregion_match * 0.08 +
        landtype_match * 0.08 +
        ecological_function * 0.04 +
        proximity_factor * 0.12 +      # Proximity weighted by boundary
        boundary_confidence * 0.10     # NEW: Overall boundary confidence
    )

    # Apply heterogeneity and strategy multipliers
    heterogeneity_confidence = compute_heterogeneity(location)
    strategy_weight = get_strategy_weight(species, strategy)

    aptness_score = base_score * heterogeneity_confidence * strategy_weight * 100

    return min(100, aptness_score)
```

### Why This Matters for Historical/Deforested Areas

For **Scenario 2** (recently deforested) and **Scenario 3** (pre-satellite):

1. **Deforested site**: We don't have direct embedding data
2. **Nearby intact forest**: We DO have embedding + species data
3. **Question**: Is that nearby forest "connected" to our deforested site?

If the answer is YES (same watershed, same elevation band, same IFL boundary):
→ We can confidently use species from that nearby forest as recommendations

If the answer is NO (across mountain ridge, different watershed, different ecoregion):
→ We should be less confident, apply penalty to those recommendations

### Implementation Priority

| Phase | Task | Data Source |
|-------|------|-------------|
| **Now** | Ecoregion boundary check | PostgreSQL `ecoregions` table |
| **Now** | IFL boundary check | PostgreSQL `intact_forest_landscapes_2021` |
| **Phase 2** | Watershed boundary | GEE `WWF/HydroSHEDS/v1/Basins/hybas_7` |
| **Phase 2** | Forest connectivity | GEE Hansen + morphological analysis |
| **Phase 3** | Barrier detection | Derived from DEM + land cover |

---

## 6. Comparison: LEAF vs. Aptness Score

| Aspect | LEAF Score | Aptness Score |
|--------|-----------|---------------|
| **Question** | "What's commonly native here?" | "How well-suited is this species HERE?" |
| **Scope** | Ecoregion-wide | Site-specific |
| **Factors** | Occurrence + native status | 8 factors |
| **Heterogeneity** | Ignores | Detects & adjusts |
| **Strategy** | Agnostic | Strategy-aware |

**They are complementary**:
```
LEAF → Get candidate species pool (top 200)
    ↓
Aptness → Rank candidates for specific site
    ↓
Return top 20 with detailed breakdown
```

---

## 7. Implementation Phases

### Phase 1: Core Integration (2-3 weeks)
- Integrate LEAF into recommender pipeline
- Add WorldClim climate matching via GEE
- Add SRTM elevation matching via GEE
- Implement weighted composite score

### Phase 2: Heterogeneity Detection (1-2 weeks)
- 9-point grid sampling
- Embedding variance calculation
- UI warning for complex terrain

### Phase 3: Soil Matching (1 week)
- Query SoilGrids via GEE
- Parse species soil preferences
- Add soil match factor

### Phase 4: Proximity Analysis (2 weeks)
- Find nearby intact forest
- Check species presence in nearby forest
- Add proximity boost factor

### Phase 5: Strategy Weights (1 week)
- Rewilding: native, ecologically functional
- Agroforestry: productive, multi-use
- Carbon: fast-growing, high-biomass
- Riparian: flood-tolerant

### Phase 6: Validation (2-3 weeks)
- Test on known restoration sites
- Tune weights
- Expert review

---

## 8. Example Output

**Location**: Asheville, NC (35.5951°N, 82.5515°W)
**Species**: *Quercus alba* (White Oak)
**Strategy**: Rewilding

```json
{
  "aptness_score": 94.7,
  "confidence": 0.95,
  "tier": "EXCELLENT",
  "breakdown": {
    "habitat_similarity": 0.87,
    "leaf_score": 1.00,
    "climate_match": 0.92,
    "elevation_match": 0.95,
    "soil_match": 0.78,
    "proximity_boost": 1.00
  },
  "is_native": true,
  "nearby_forest": {
    "distance_km": 8.2,
    "name": "Pisgah National Forest",
    "species_present": true
  }
}
```

---

## 9. Key Conclusions

1. **No massive downloads needed** - All datasets available via GEE
2. **Leverage existing infrastructure** - LEAF, AlphaEarth, DB fields
3. **Address heterogeneity** via multi-scale weighted sampling (25 points, 1km radius)
4. **Interpretable scores** - users see why each recommendation
5. **Strategy-aware** - different weights for different goals

---

## 10. Weight Tuning Framework (Using Phase 1 Data)

### 10.1 The Idea

Once Phase 1 BigQuery data is ready (~16.5M occurrence points with embeddings), we can use it as ground truth to test different weight combinations:

```
For each occurrence point:
  - We KNOW the species (ground truth)
  - We HAVE the embedding at that location
  - We can compute all aptness factors
  - We predict top-10 species
  - Check: Is actual species in top-10? Top-5? Top-1?
```

### 10.2 Testing Script

```python
def test_weight_combination(weights: dict, test_points: list) -> dict:
    """
    Test a weight combination against known occurrence points.

    Args:
        weights: {'habitat': 0.20, 'leaf': 0.15, 'climate': 0.15, ...}
        test_points: List of (taxon_id, lat, lon, embedding) tuples

    Returns:
        Accuracy metrics
    """
    top1_hits = 0
    top5_hits = 0
    top10_hits = 0
    mrr_sum = 0  # Mean Reciprocal Rank

    for actual_taxon_id, lat, lon, embedding in test_points:
        # Compute aptness for all candidate species
        predictions = []
        for species in candidate_species:
            score = compute_aptness_score(
                species, lat, lon, embedding, weights
            )
            predictions.append((species.taxon_id, score))

        # Rank by score
        predictions.sort(key=lambda x: x[1], reverse=True)
        ranked_ids = [p[0] for p in predictions]

        # Check where actual species landed
        if actual_taxon_id in ranked_ids:
            rank = ranked_ids.index(actual_taxon_id) + 1
            mrr_sum += 1.0 / rank

            if rank == 1:
                top1_hits += 1
            if rank <= 5:
                top5_hits += 1
            if rank <= 10:
                top10_hits += 1

    n = len(test_points)
    return {
        'top1_accuracy': top1_hits / n,
        'top5_accuracy': top5_hits / n,
        'top10_accuracy': top10_hits / n,
        'mrr': mrr_sum / n,  # Mean Reciprocal Rank
        'weights': weights
    }


def grid_search_weights():
    """
    Test multiple weight combinations to find optimal.
    """
    # Sample 10,000 points from BigQuery (stratified by species)
    test_points = sample_test_points(n=10000, stratify_by='taxon_id')

    weight_combinations = [
        # Baseline: Balanced
        {'habitat': 0.20, 'leaf': 0.15, 'climate': 0.15, 'elevation': 0.10,
         'soil': 0.10, 'ecoregion': 0.10, 'landtype': 0.10, 'function': 0.05, 'proximity': 0.05},

        # Habitat-heavy (test AlphaEarth value)
        {'habitat': 0.35, 'leaf': 0.15, 'climate': 0.15, 'elevation': 0.05,
         'soil': 0.05, 'ecoregion': 0.10, 'landtype': 0.10, 'function': 0.02, 'proximity': 0.03},

        # LEAF-heavy
        {'habitat': 0.15, 'leaf': 0.30, 'climate': 0.15, 'elevation': 0.05,
         'soil': 0.05, 'ecoregion': 0.15, 'landtype': 0.10, 'function': 0.02, 'proximity': 0.03},

        # No habitat (baseline without AlphaEarth)
        {'habitat': 0.00, 'leaf': 0.25, 'climate': 0.25, 'elevation': 0.10,
         'soil': 0.10, 'ecoregion': 0.15, 'landtype': 0.10, 'function': 0.02, 'proximity': 0.03},

        # Ecoregion-heavy
        {'habitat': 0.15, 'leaf': 0.10, 'climate': 0.10, 'elevation': 0.05,
         'soil': 0.05, 'ecoregion': 0.35, 'landtype': 0.10, 'function': 0.05, 'proximity': 0.05},
    ]

    results = []
    for weights in weight_combinations:
        metrics = test_weight_combination(weights, test_points)
        results.append(metrics)
        print(f"Top-10: {metrics['top10_accuracy']:.1%} | MRR: {metrics['mrr']:.3f}")

    best = max(results, key=lambda x: x['top10_accuracy'])
    print(f"Best: {best['weights']}")
    return results
```

### 10.3 Key Questions to Answer

| Question | Test Method |
|----------|-------------|
| Does AlphaEarth add value? | habitat=0.20 vs habitat=0.00 |
| Is climate > ecoregion? | climate=0.30 vs ecoregion=0.30 |
| Do soil/landtype matter? | Include vs exclude |
| Optimal heterogeneity threshold? | Vary: 0.02, 0.05, 0.10 |

### 10.4 Validation Levels

1. **Self-validation**: Use BigQuery occurrence as ground truth (80/20 split)
2. **Expert validation**: 50-100 locations with expert species lists
3. **Field validation**: Track predicted vs. actual planting success

---

## 11. Updated Implementation Phases

### Phase 1: Build Aptness Function (Now - While GEE runs)
- Implement all 9 factors in Python
- Query GEE for climate/elevation/soil
- No centroids needed yet - just the scoring logic

### Phase 2: Weight Tuning (After Phase 1 data complete)
- Run grid search on 10K sample points
- Find optimal weights
- Validate on held-out test set

### Phase 3: Integration (After weights validated)
- Update frontend prediction modal
- Add aptness breakdown display
- Add strategy selector

---

---

## 12. Local Datasets Integration

**Date Added**: January 19, 2026

The following datasets have been extracted to `/Sources_Data/Sources (.shp, rasters)/` (~16GB total) and can serve as local alternatives or supplements to GEE queries.

### 12.1 Dataset Inventory

| Dataset | Size | Format | Resolution | CRS | Primary Use |
|---------|------|--------|------------|-----|-------------|
| **WorldClim Bioclimatics** | 10 GB | GeoTIFF (19 files) | 30 arc-sec (~1km) | EPSG:4326 | Climate matching |
| **IUCN EFG Rasters** | 269 MB | GeoTIFF (109 files) | 30 arc-sec (~1km) | EPSG:4326 | Ecosystem function |
| **One Earth Ecoregions** | 242 MB | Shapefile (847 polygons) | Vector | EPSG:4326 | Ecoregion matching |
| **Intact Forest Landscapes** | 1.1 GB | Shapefile (6,819 polygons) | Vector | EPSG:4326 | Boundary analysis |
| **Köppen-Geiger Climate** | 12 MB | GeoTIFF (4 resolutions) | 30 arc-sec (~1km) | EPSG:4326 | Climate classification |
| **SoilGrids pH** | 1.4 GB | GeoTIFF | 250m | EPSG:4326 | Soil matching |
| **Copernicus Land Cover** | 2.4 GB | GeoTIFF (by continent) | 100m | EPSG:4326 | Land type matching |
| **SBTN Land Cover** | 277 MB | GeoTIFF (tiles) | Various | EPSG:4326 | Land type matching |

### 12.2 WorldClim Bioclimatics (19 Variables)

**Location**: `Bioclimatics_WorldClim/wc2.1_30s_bio_*.tif`

| Variable | File | Description | Units |
|----------|------|-------------|-------|
| BIO1 | bio_1.tif | Annual Mean Temperature | °C × 10 |
| BIO2 | bio_2.tif | Mean Diurnal Range | °C × 10 |
| BIO3 | bio_3.tif | Isothermality (BIO2/BIO7) | % |
| BIO4 | bio_4.tif | Temperature Seasonality | std × 100 |
| BIO5 | bio_5.tif | Max Temp of Warmest Month | °C × 10 |
| BIO6 | bio_6.tif | Min Temp of Coldest Month | °C × 10 |
| BIO7 | bio_7.tif | Temperature Annual Range | °C × 10 |
| BIO8 | bio_8.tif | Mean Temp of Wettest Quarter | °C × 10 |
| BIO9 | bio_9.tif | Mean Temp of Driest Quarter | °C × 10 |
| BIO10 | bio_10.tif | Mean Temp of Warmest Quarter | °C × 10 |
| BIO11 | bio_11.tif | Mean Temp of Coldest Quarter | °C × 10 |
| BIO12 | bio_12.tif | Annual Precipitation | mm |
| BIO13 | bio_13.tif | Precip of Wettest Month | mm |
| BIO14 | bio_14.tif | Precip of Driest Month | mm |
| BIO15 | bio_15.tif | Precipitation Seasonality | CV |
| BIO16 | bio_16.tif | Precip of Wettest Quarter | mm |
| BIO17 | bio_17.tif | Precip of Driest Quarter | mm |
| BIO18 | bio_18.tif | Precip of Warmest Quarter | mm |
| BIO19 | bio_19.tif | Precip of Coldest Quarter | mm |

**Use Case**: Climate matching factor (15% weight)

**Sample Query (Python with rasterio)**:
```python
import rasterio

def get_worldclim_values(lat, lon):
    """Sample all 19 bioclimatic variables at a point."""
    values = {}
    base_path = 'Sources_Data/Sources (.shp, rasters)/Bioclimatics_WorldClim'

    for i in range(1, 20):
        with rasterio.open(f'{base_path}/wc2.1_30s_bio_{i}.tif') as src:
            # Convert lat/lon to row/col
            row, col = src.index(lon, lat)
            value = src.read(1)[row, col]
            values[f'bio{i}'] = value

    # Convert temperature values (stored as °C × 10)
    for key in ['bio1', 'bio2', 'bio5', 'bio6', 'bio7', 'bio8', 'bio9', 'bio10', 'bio11']:
        if key in values:
            values[key] = values[key] / 10.0

    return values
```

### 12.3 IUCN Ecosystem Functional Groups (109 Rasters)

**Location**: `Functional_ecosystem_groups/raster_extracted/*.tif`

**Naming Convention**: `{EFG_CODE}.web.{type}_v{version}.tif`
- Example: `T1.1.web.mix_v2.0.tif` = Tropical lowland rainforests

**EFG Codes in Dataset**:

| Realm | Count | Examples |
|-------|-------|----------|
| **T** (Terrestrial) | ~40 | T1.1-T7.5 (Forests, woodlands, shrublands) |
| **F** (Freshwater) | ~15 | F1.1-F3.5 (Rivers, lakes, wetlands) |
| **M** (Marine) | ~25 | M1.1-M4.2 (Coastal, pelagic, deep sea) |
| **FM** (Freshwater-Marine) | 3 | FM1.1-FM1.3 (Estuaries, deltas) |
| **MT** (Marine-Terrestrial) | 5 | MT1.1-MT3.1 (Coastal, intertidal) |
| **TF** (Terrestrial-Freshwater) | 7 | TF1.1-TF1.7 (Floodplains, peatlands) |
| **SF** (Subterranean-Freshwater) | 2 | SF1.1-SF2.2 (Aquifers, caves) |
| **SM** (Subterranean-Marine) | 3 | SM1.1-SM1.3 (Sea caves) |
| **S** (Subterranean) | 2 | S1.1-S2.1 (Caves, aquifers) |

**Forest-Relevant EFGs (Priority for Treekipedia)**:
- T1.1: Tropical/subtropical lowland rainforests
- T1.2: Tropical/subtropical dry forests
- T1.3: Tropical/subtropical montane rainforests
- T1.4: Tropical heath forests
- T2.1: Boreal/temperate montane forests
- T2.2: Deciduous temperate forests
- T2.3: Oceanic cool temperate rainforests
- T2.4: Warm temperate laurophyll forests
- T2.5: Temperate pyric humid forests
- T2.6: Temperate pyric sclerophyll forests
- TF1.1: Tropical flooded forests
- TF1.3: Permanent marshes

**Sample Query**:
```python
def get_efg_at_point(lat, lon):
    """Find which EFG(s) are present at a location."""
    import glob

    efgs_present = []
    base_path = 'Sources_Data/Sources (.shp, rasters)/Functional_ecosystem_groups/raster_extracted'

    for tif_path in glob.glob(f'{base_path}/*.tif'):
        efg_code = tif_path.split('/')[-1].split('.web')[0]

        with rasterio.open(tif_path) as src:
            row, col = src.index(lon, lat)
            value = src.read(1)[row, col]

            if value > 0:  # Presence threshold
                efgs_present.append({
                    'code': efg_code,
                    'probability': value
                })

    return sorted(efgs_present, key=lambda x: x['probability'], reverse=True)
```

### 12.4 One Earth Ecoregions (847 Polygons)

**Location**: `One_Earth_ecoregions_2017/Ecoregions2017.shp`

**Attributes**:
| Field | Type | Description |
|-------|------|-------------|
| ECO_NAME | String | Ecoregion name |
| BIOME_NUM | Integer | Biome number (1-14) |
| BIOME_NAME | String | Biome name |
| REALM | String | Biogeographic realm |
| ECO_ID | Integer | Unique ecoregion ID |
| NNH | Integer | Nature Needs Half classification |
| NNH_NAME | String | NNH category name |

**Already in PostgreSQL**: Yes - `ecoregions` table with 847 polygons

**Sample Query**:
```python
import geopandas as gpd

ecoregions = gpd.read_file(
    'Sources_Data/Sources (.shp, rasters)/One_Earth_ecoregions_2017/Ecoregions2017.shp'
)

def get_ecoregion(lat, lon):
    from shapely.geometry import Point
    point = Point(lon, lat)
    for _, row in ecoregions.iterrows():
        if row.geometry.contains(point):
            return {
                'eco_name': row['ECO_NAME'],
                'biome': row['BIOME_NAME'],
                'realm': row['REALM'],
                'eco_id': row['ECO_ID']
            }
    return None
```

### 12.5 Intact Forest Landscapes 2021 (6,819 Polygons)

**Location**: `Intact_forest/ifl_intact_forest_landscapes_v2021.shp`

**Attributes**:
| Field | Type | Description |
|-------|------|-------------|
| gfw_fid | Integer | Global Forest Watch ID |
| ifl_id | String | IFL unique ID |
| year | Integer | Year of assessment |
| layer | String | Layer type |
| gfw_area__ | Float | Area in km² |
| gfw_geosto | String | Geostorage reference |

**Already in PostgreSQL**: Yes - `intact_forest_landscapes_2021` table with 6,819 polygons

**Use Case**: Continuous boundary analysis (15% weight in boundary scoring)

### 12.6 Köppen-Geiger Climate Classification

**Location**: `ClimateType_KoppenGeiger/1991_2020/`

| File | Resolution | Description |
|------|------------|-------------|
| koppen_geiger_0p00833333.tif | ~1km (30 arc-sec) | Full resolution |
| koppen_geiger_0p1.tif | ~10km | Aggregated |
| koppen_geiger_0p5.tif | ~50km | Coarse |
| koppen_geiger_1p0.tif | ~100km | Very coarse |

**Climate Zones (Value → Classification)**:
| Value | Code | Description |
|-------|------|-------------|
| 1 | Af | Tropical rainforest |
| 2 | Am | Tropical monsoon |
| 3 | Aw | Tropical savanna |
| 4 | BWh | Hot desert |
| 5 | BWk | Cold desert |
| 6 | BSh | Hot steppe |
| 7 | BSk | Cold steppe |
| 8 | Csa | Mediterranean hot summer |
| 9 | Csb | Mediterranean warm summer |
| 10 | Csc | Mediterranean cold summer |
| 11 | Cwa | Humid subtropical |
| 12 | Cwb | Subtropical highland |
| 13 | Cwc | Cold subtropical highland |
| 14 | Cfa | Humid subtropical |
| 15 | Cfb | Oceanic |
| 16 | Cfc | Subpolar oceanic |
| 17 | Dsa | Mediterranean continental |
| 18 | Dsb | Warm continental |
| 19 | Dsc | Subarctic |
| 20 | Dsd | Subarctic extreme |
| 21 | Dwa | Monsoon continental |
| 22 | Dwb | Warm continental |
| 23 | Dwc | Subarctic |
| 24 | Dwd | Subarctic extreme |
| 25 | Dfa | Hot continental |
| 26 | Dfb | Warm continental |
| 27 | Dfc | Subarctic |
| 28 | Dfd | Extreme subarctic |
| 29 | ET | Tundra |
| 30 | EF | Ice cap |

**Use Case**: Climate matching - compare with species' `climate_type_koppengeiger` field

### 12.7 SoilGrids pH (0-5cm depth)

**Location**: `Soil_grids250_SoilSources/ph_0_5cm_merged.tif`

**Specifications**:
- Resolution: 250m (0.002245° pixel size)
- Size: 160,302 × 80,152 pixels
- Coverage: Global
- Units: pH × 10 (divide by 10 for actual pH)

**Use Case**: Soil matching factor (10% weight)

**Sample Query**:
```python
def get_soil_ph(lat, lon):
    with rasterio.open('Sources_Data/Sources (.shp, rasters)/Soil_grids250_SoilSources/ph_0_5cm_merged.tif') as src:
        row, col = src.index(lon, lat)
        value = src.read(1)[row, col]
        return value / 10.0  # Convert to actual pH
```

### 12.8 Land Cover Datasets

**Copernicus Land Cover 2019**:
- Location: `Copernicus_LandCover/Copernicus/`
- Format: Tiled by continent (Africa, Asia, Australia_Oceania, Europe, North_America, South_America)
- Resolution: 100m
- Classes: ESA CCI LC classification (30+ classes)

**SBTN Land Cover 2020**:
- Location: `SBTN_LandCover/`
- Format: Tiled by lat/lon (10° × 10° tiles)
- Naming: `SBTN_CLASS_2020_LON{lon1}_{lon2}_LAT{lat1}_{lat2}.tif`

**Use Case**: Land type matching factor (8% weight)

### 12.9 Dataset Integration Decision Matrix

| Factor | GEE Query | Local Query | Recommendation |
|--------|-----------|-------------|----------------|
| **Climate (WorldClim)** | ✅ Fast, on-demand | ✅ 10GB local | **GEE** for single points, **Local** for batch |
| **EFG** | ✅ IUCN GEE asset | ✅ 269MB local | **Local** (smaller, faster startup) |
| **Ecoregion** | ✅ WWF GEE | ✅ PostgreSQL | **PostgreSQL** (already loaded) |
| **IFL** | ❌ Not in GEE | ✅ PostgreSQL | **PostgreSQL** (already loaded) |
| **Köppen-Geiger** | ❌ Not in GEE | ✅ 12MB local | **Local** (tiny, fast) |
| **Soil pH** | ✅ SoilGrids GEE | ✅ 1.4GB local | **GEE** (avoid large local reads) |
| **Land Cover** | ✅ Copernicus GEE | ✅ 2.4GB local | **GEE** (official asset, tiled) |
| **Elevation** | ✅ SRTM GEE | ❌ Not local | **GEE** (30m resolution) |

### 12.10 Python Loader Module

```python
"""
local_datasets.py - Load and query local environmental datasets
"""

import rasterio
import geopandas as gpd
from functools import lru_cache
from pathlib import Path

BASE_PATH = Path('Sources_Data/Sources (.shp, rasters)')

@lru_cache(maxsize=1)
def load_ecoregions():
    return gpd.read_file(BASE_PATH / 'One_Earth_ecoregions_2017/Ecoregions2017.shp')

@lru_cache(maxsize=1)
def load_ifl():
    return gpd.read_file(BASE_PATH / 'Intact_forest/ifl_intact_forest_landscapes_v2021.shp')

class LocalDatasetSampler:
    """Sample environmental data at a point from local rasters."""

    def __init__(self):
        self.koppen_path = BASE_PATH / 'ClimateType_KoppenGeiger/1991_2020/koppen_geiger_0p00833333.tif'
        self.worldclim_path = BASE_PATH / 'Bioclimatics_WorldClim'
        self.efg_path = BASE_PATH / 'Functional_ecosystem_groups/raster_extracted'
        self.soil_path = BASE_PATH / 'Soil_grids250_SoilSources/ph_0_5cm_merged.tif'

    def sample_koppen(self, lat: float, lon: float) -> int:
        """Get Köppen-Geiger climate code (1-30)."""
        with rasterio.open(self.koppen_path) as src:
            row, col = src.index(lon, lat)
            return int(src.read(1)[row, col])

    def sample_worldclim(self, lat: float, lon: float) -> dict:
        """Get all 19 bioclimatic variables."""
        values = {}
        for i in range(1, 20):
            path = self.worldclim_path / f'wc2.1_30s_bio_{i}.tif'
            with rasterio.open(path) as src:
                row, col = src.index(lon, lat)
                val = src.read(1)[row, col]
                # Convert temperature variables (stored × 10)
                if i in [1, 2, 5, 6, 7, 8, 9, 10, 11]:
                    val = val / 10.0
                values[f'bio{i}'] = val
        return values

    def sample_efg(self, lat: float, lon: float) -> list:
        """Get EFGs present at location, sorted by probability."""
        import glob
        results = []
        for tif in glob.glob(str(self.efg_path / '*.tif')):
            code = Path(tif).stem.split('.web')[0]
            with rasterio.open(tif) as src:
                row, col = src.index(lon, lat)
                val = src.read(1)[row, col]
                if val > 0:
                    results.append({'code': code, 'probability': float(val)})
        return sorted(results, key=lambda x: x['probability'], reverse=True)

    def sample_soil_ph(self, lat: float, lon: float) -> float:
        """Get soil pH at 0-5cm depth."""
        with rasterio.open(self.soil_path) as src:
            row, col = src.index(lon, lat)
            return src.read(1)[row, col] / 10.0

    def sample_all(self, lat: float, lon: float) -> dict:
        """Sample all local datasets at a point."""
        return {
            'koppen': self.sample_koppen(lat, lon),
            'worldclim': self.sample_worldclim(lat, lon),
            'efg': self.sample_efg(lat, lon),
            'soil_ph': self.sample_soil_ph(lat, lon)
        }
```

---

## Sources

**Free Environmental Datasets (GEE)**:
- [WorldClim in GEE](https://developers.google.com/earth-engine/datasets/catalog/WORLDCLIM_V1_BIO)
- [SRTM Elevation](https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003)
- [SoilGrids GEE Community](https://gee-community-catalog.org/projects/isric/)
- [Hansen Global Forest Change](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12)
- [IUCN Global Ecosystem Typology](https://developers.google.com/earth-engine/datasets/catalog/IUCN_GlobalEcosystemTypology_current)

**Local Datasets**:
- [WorldClim v2.1](https://www.worldclim.org/data/worldclim21.html)
- [IUCN GET Rasters](https://global-ecosystems.org/explore/groups)
- [One Earth Ecoregions](https://www.oneearth.org/bioregions/)
- [Intact Forest Landscapes](https://intactforests.org/)
- [Köppen-Geiger Climate Classification](http://koeppen-geiger.vu-wien.ac.at/)
- [SoilGrids 250m](https://soilgrids.org/)
- [Copernicus Land Cover](https://land.copernicus.eu/global/products/lc)

**Heterogeneity Research**:
- [Landscape heterogeneity metrics](https://link.springer.com/article/10.1007/s10980-022-01533-6)
- [Terrain complexity indices](https://www.sciencedirect.com/science/article/pii/S2666017225000719)
