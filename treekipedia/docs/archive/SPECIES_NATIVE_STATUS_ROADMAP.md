# Species Native Status Scoring Engine
## From MVP to Full Biodiversity Impact Prediction

**Version**: 2.0
**Date**: December 2025
**Goal**: Build a bias-resistant, multi-dimensional system to score species native/invasive status and predict biodiversity impact for any geographic location

---

## Executive Summary

This roadmap outlines the development of a Species Native Status Scoring Engine that evolves through three stages:

1. **MVP (Weeks 1-6)**: Occurrence-based native status classification using `establishmentMeans` tags and checklist validation
2. **Enhanced System (Weeks 7-14)**: Environmental variable matching using your 120-field species knowledge schema
3. **Full Model (Weeks 15-26)**: Machine learning regression with temporal remote sensing and AlphaEarth embeddings

The ultimate vision is a **Species-Location Aptness Score** that predicts whether a tree species will thrive at a location AND benefit local biodiversity, using the intersection of:
- Occurrence-derived native status
- Species environmental preferences (soil, pH, elevation, climate)
- Location environmental characteristics (WorldClim, SoilGrids, Copernicus)
- Ecological function compatibility (functional ecosystem groups, biotic interactions)
- Remote sensing validation (current habitat state)

---

## Current Data Assets

### Species Knowledge Schema (120 Fields)

Your schema represents one of the most comprehensive tree species databases. Key environmental fields:

| Category | Fields | Coverage |
|----------|--------|----------|
| **Taxonomy** | species_scientific_name, family, genus, class, taxonomic_order | 67,743 species |
| **Geography** | ecoregions, biomes, bioregions, countries_native/introduced/invasive | 61,142 with biomes |
| **Soil Preferences** | soil_texture_prefered/tolerated/dominant, pH_prefered/tolerated, OC_prefered | 23,077 with soil data |
| **Functional Groups** | functional_ecosystem_groups, vegetationType, forest_type, SBTN_LandCover | 48,081 with func groups |
| **Ecological Function** | ecological_function_ai/human, tolerances, successional_stage | Varies |
| **Biotic Interactions** | Globi_pollinatedBy, eatenBy, flowersVisitedBy, hasParasite, hasDispersalVector | Linked to GloBI |
| **Climate** | climate_change_vulnerability, elevation_ranges | Growing |
| **Morphology** | growth_form, leaf_type, deciduous_evergreen, maximum_height, lifespan | Researched species |

### Environmental Layers Available

Based on your folder structure, you have access to:

| Layer | Source | Resolution | Use in Model |
|-------|--------|------------|--------------|
| **Bioclimatic Variables** | WorldClim | 1km | 19 BIOCLIM variables for climate envelope |
| **Climate Type** | Köppen-Geiger | 1km | Climate zone classification |
| **Land Cover** | Copernicus | 100m | Current habitat state |
| **Functional Ecosystem Groups** | IUCN GET | Ecoregion | Ecological function matching |
| **Intact Forest** | GFW | Polygon | Forest quality indicator |
| **One Earth Ecoregions** | One Earth 2017 | Polygon | Alternative biogeographic boundaries |
| **SBTN Land Cover** | SBTN | Variable | Science-based target validation |
| **Soil Properties** | SoilGrids 250m | 250m | Soil texture, pH, organic carbon |

### Occurrence Data Schema (Enhanced)

**Current Schema** (from parquet):
```
species_scientific_name, year, family, decimalLatitude, decimalLongitude,
subspecies, taxon_full, taxon_id_new
```

**Enhanced Schema** (to be added):
```python
# New fields to add
enhanced_occurrence_fields = {
    # Establishment status
    'establishmentMeans': str,  # NATIVE, INTRODUCED, NATURALISED, INVASIVE, MANAGED, UNCERTAIN

    # Location accuracy
    'coordinateUncertaintyInMeters': float,  # <10, <100, <1000, <10000, etc.
    'coordinatePrecision': float,  # Decimal precision indicator

    # Data quality
    'basisOfRecord': str,  # PRESERVED_SPECIMEN, HUMAN_OBSERVATION, MACHINE_OBSERVATION
    'identificationVerificationStatus': str,  # Verified, Unverified
    'identifiedBy': str,  # Identifier name (for specialist weighting)

    # Temporal precision
    'eventDate': date,  # Full date when available
    'dateIdentified': date,  # When ID was made

    # Source tracking
    'datasetKey': str,  # GBIF dataset identifier
    'institutionCode': str,  # Source institution
    'collectionCode': str,  # Collection identifier
}
```

---

## MVP Definition (Weeks 1-6)

### MVP Scope

The MVP delivers a **working native status API** that can answer:
> "Is species X native, introduced, or invasive at location Y?"

**In Scope:**
- Occurrence-based status classification using `establishmentMeans`
- External checklist validation (GRIIS, countries_native)
- Confidence scoring with 4 tiers
- Conflict resolution for mixed status
- Location accuracy weighting
- API endpoints for queries
- Basic frontend integration

**Out of Scope for MVP:**
- Environmental variable matching
- ML regression model
- Remote sensing validation
- AlphaEarth embeddings
- Habitat suitability prediction

### MVP Data Requirements

| Data Source | Records Needed | Priority |
|-------------|----------------|----------|
| GBIF occurrences with establishmentMeans | ~20-40M | P0 |
| GBIF coordinateUncertaintyInMeters | Same | P0 |
| GRIIS checklists | 196 countries | P1 |
| Existing countries_native field | 17,405 species | P1 |
| WWF Ecoregions (already have) | 847 | Done |

### MVP Confidence Formula

```python
def calculate_mvp_confidence(
    occurrence_count: int,
    tagged_count: int,
    dominant_status_count: int,
    earliest_year: int,
    has_checklist_match: bool,
    avg_coordinate_accuracy: float,  # meters
    high_accuracy_ratio: float  # % of records <100m accuracy
) -> float:
    """
    MVP confidence score: 0.0 to 1.0

    Components (sum to 1.0):
    - Occurrence volume: 0.20
    - Status tag agreement: 0.25
    - Temporal depth: 0.10
    - Checklist match: 0.20
    - Coordinate accuracy: 0.15
    - Spatial distribution: 0.10
    """
    score = 0.0

    # 1. Occurrence volume (log scale, max 0.20)
    # 10 records = 0.10, 100 = 0.15, 1000 = 0.20
    volume_score = min(0.20, np.log10(max(1, occurrence_count)) * 0.067)
    score += volume_score

    # 2. Status tag agreement (max 0.25)
    if tagged_count > 0:
        agreement_ratio = dominant_status_count / tagged_count
        agreement_score = agreement_ratio * 0.25
        score += agreement_score

    # 3. Temporal depth (max 0.10)
    # Older records = more likely to be truly native
    if earliest_year:
        age = 2025 - earliest_year
        temporal_score = min(0.10, (age / 200) * 0.10)  # Max at 200 years
        score += temporal_score

    # 4. Checklist match (max 0.20)
    if has_checklist_match:
        score += 0.20

    # 5. Coordinate accuracy (max 0.15)
    # <100m = full credit, <1000m = 75%, <10000m = 50%, worse = 25%
    if avg_coordinate_accuracy < 100:
        accuracy_score = 0.15
    elif avg_coordinate_accuracy < 1000:
        accuracy_score = 0.11
    elif avg_coordinate_accuracy < 10000:
        accuracy_score = 0.075
    else:
        accuracy_score = 0.04
    score += accuracy_score

    # 6. High accuracy ratio bonus (max 0.10)
    # Reward datasets with many precise records
    spatial_score = high_accuracy_ratio * 0.10
    score += spatial_score

    return round(score, 3)
```

---

## Core Algorithm: Invasive-First Elimination + Sub-Country Clustering

### The Problem with Country-Level Data

Country-level native/invasive classifications fail when:
- A species is **native in one biome** but **invasive in another biome** within the same country
- Example: *Eucalyptus* species native to Australian dry sclerophyll forests but invasive in Australian tropical rainforests
- Example: A species native to Brazil's Atlantic Forest but invasive in Brazil's Cerrado

**Solution**: Analyze at **ecoregion/biome level** (sub-country continuous boundaries) and use **invasive-first elimination**.

### Step 1: Invasive-First Elimination (Process of Elimination)

```python
def apply_invasive_elimination(
    taxon_id: str,
    eco_id: int,
    country_code: str
) -> dict:
    """
    FIRST PASS: Check authoritative invasive lists before any occurrence analysis.

    If a species is on an invasive list for this region, it's invasive - full stop.
    This prevents occurrence data (which may be biased toward cultivation sites)
    from incorrectly classifying known invasives as native.

    Priority order for invasive lists:
    1. GRIIS (Global Register of Introduced and Invasive Species) - country level
    2. GISD (Global Invasive Species Database) - regional level
    3. CABI Invasive Species Compendium
    4. Regional/national invasive lists (USDA PLANTS, EPPO, etc.)
    """

    # Check GRIIS first (most comprehensive)
    griis_record = query_griis(taxon_id, country_code)
    if griis_record:
        if griis_record['is_invasive']:
            return {
                'eliminated_as_invasive': True,
                'status': 'invasive',
                'confidence': 0.95,
                'source': 'GRIIS',
                'evidence': griis_record,
                'skip_occurrence_analysis': True  # No need to analyze occurrences
            }
        elif griis_record['is_introduced']:
            # Introduced but not invasive - continue with caution
            return {
                'eliminated_as_invasive': False,
                'known_introduced': True,
                'source': 'GRIIS',
                'proceed_with_analysis': True,
                'baseline_status': 'introduced'
            }

    # Check GISD (more detailed impact info)
    gisd_record = query_gisd(taxon_id)
    if gisd_record and gisd_record.get('invasive_in_regions'):
        # Check if our ecoregion overlaps with known invasive regions
        ecoregion = get_ecoregion(eco_id)
        if region_overlaps(ecoregion, gisd_record['invasive_in_regions']):
            return {
                'eliminated_as_invasive': True,
                'status': 'invasive',
                'confidence': 0.90,
                'source': 'GISD',
                'impact_info': gisd_record.get('impact_description'),
                'skip_occurrence_analysis': True
            }

    # Check CABI Compendium
    cabi_record = query_cabi(taxon_id)
    if cabi_record and cabi_record.get('invasive_status') == 'invasive':
        if country_code in cabi_record.get('invasive_countries', []):
            return {
                'eliminated_as_invasive': True,
                'status': 'invasive',
                'confidence': 0.88,
                'source': 'CABI',
                'skip_occurrence_analysis': True
            }

    # Not on any invasive list - proceed with occurrence analysis
    return {
        'eliminated_as_invasive': False,
        'proceed_with_analysis': True,
        'checked_sources': ['GRIIS', 'GISD', 'CABI']
    }
```

### Step 2: Sub-Country Biome/Ecoregion Clustering

```python
def analyze_subcountry_clustering(
    taxon_id: str,
    country_code: str
) -> dict:
    """
    Analyze occurrence patterns at SUB-COUNTRY level using continuous
    ecological boundaries (biomes, ecoregions, bioregions).

    This resolves conflicts where a species appears both native AND invasive
    at the country level by identifying which BIOMES it's native to vs invasive in.

    Hierarchy of continuous boundaries (finest to coarsest):
    1. Ecoregion (847 globally) - ~50-500km scale
    2. Biome (14 globally) - continental scale
    3. Realm (8 globally) - intercontinental scale
    """

    # Get all occurrences for this species in this country
    occurrences = get_occurrences_by_country(taxon_id, country_code)

    # Get all ecoregions that intersect this country
    country_ecoregions = get_ecoregions_in_country(country_code)

    # Cluster occurrences by ecoregion
    ecoregion_clusters = {}
    for eco in country_ecoregions:
        eco_occurrences = [o for o in occurrences
                          if point_in_ecoregion(o['lat'], o['lng'], eco['eco_id'])]

        if not eco_occurrences:
            continue

        # Aggregate status tags within this ecoregion
        status_counts = {
            'native': sum(1 for o in eco_occurrences if o['establishment_means'] == 'NATIVE'),
            'introduced': sum(1 for o in eco_occurrences if o['establishment_means'] == 'INTRODUCED'),
            'invasive': sum(1 for o in eco_occurrences if o['establishment_means'] == 'INVASIVE'),
            'naturalised': sum(1 for o in eco_occurrences if o['establishment_means'] == 'NATURALISED'),
            'untagged': sum(1 for o in eco_occurrences if o['establishment_means'] is None)
        }

        # Calculate weighted status (by coordinate accuracy)
        weighted_native = sum(o['weight'] for o in eco_occurrences
                             if o['establishment_means'] == 'NATIVE')
        weighted_introduced = sum(o['weight'] for o in eco_occurrences
                                  if o['establishment_means'] in ['INTRODUCED', 'INVASIVE'])

        ecoregion_clusters[eco['eco_id']] = {
            'eco_name': eco['eco_name'],
            'biome': eco['biome_name'],
            'realm': eco['realm'],
            'occurrence_count': len(eco_occurrences),
            'status_counts': status_counts,
            'weighted_native': weighted_native,
            'weighted_introduced': weighted_introduced,
            'dominant_status': determine_dominant_status(status_counts, weighted_native, weighted_introduced),
            'confidence': calculate_cluster_confidence(eco_occurrences, status_counts),
            'earliest_year': min(o['year'] for o in eco_occurrences if o['year']),
            'spatial_dispersion': calculate_spatial_dispersion(eco_occurrences)
        }

    # Aggregate to biome level (for broader patterns)
    biome_summary = aggregate_to_biome(ecoregion_clusters)

    return {
        'ecoregion_clusters': ecoregion_clusters,
        'biome_summary': biome_summary,
        'has_mixed_status': detect_mixed_status(ecoregion_clusters),
        'country_conflict_resolved': len(set(c['dominant_status'] for c in ecoregion_clusters.values())) > 1
    }


def determine_dominant_status(
    status_counts: dict,
    weighted_native: float,
    weighted_introduced: float
) -> str:
    """
    Determine dominant status for a cluster using weighted voting.

    Rules:
    1. If >80% of weighted occurrences are native → native
    2. If >80% of weighted occurrences are introduced/invasive → introduced
    3. If weighted_native > 2x weighted_introduced AND earliest records are native → native
    4. Otherwise → uncertain (needs review)
    """
    total_weighted = weighted_native + weighted_introduced

    if total_weighted == 0:
        # No tagged occurrences - use counts
        total_tagged = status_counts['native'] + status_counts['introduced'] + status_counts['invasive']
        if total_tagged == 0:
            return 'uncertain'
        if status_counts['native'] / total_tagged > 0.8:
            return 'native'
        if (status_counts['introduced'] + status_counts['invasive']) / total_tagged > 0.8:
            return 'introduced'
        return 'uncertain'

    native_ratio = weighted_native / total_weighted

    if native_ratio > 0.8:
        return 'native'
    elif native_ratio < 0.2:
        return 'introduced'
    elif native_ratio > 0.6:
        return 'likely_native'
    elif native_ratio < 0.4:
        return 'likely_introduced'
    else:
        return 'uncertain'


def detect_mixed_status(ecoregion_clusters: dict) -> dict:
    """
    Detect if a species has DIFFERENT status in different ecoregions/biomes.

    This is the KEY insight: a species can be native in one biome and
    invasive in another within the same country.
    """
    statuses_by_biome = {}

    for eco_id, cluster in ecoregion_clusters.items():
        biome = cluster['biome']
        status = cluster['dominant_status']

        if biome not in statuses_by_biome:
            statuses_by_biome[biome] = []
        statuses_by_biome[biome].append({
            'eco_id': eco_id,
            'eco_name': cluster['eco_name'],
            'status': status,
            'confidence': cluster['confidence'],
            'occurrence_count': cluster['occurrence_count']
        })

    # Check for conflicts within same country
    native_biomes = [b for b, ecos in statuses_by_biome.items()
                     if any(e['status'] in ['native', 'likely_native'] for e in ecos)]
    introduced_biomes = [b for b, ecos in statuses_by_biome.items()
                         if any(e['status'] in ['introduced', 'likely_introduced', 'invasive'] for e in ecos)]

    has_conflict = bool(set(native_biomes) & set(introduced_biomes)) or \
                   (len(native_biomes) > 0 and len(introduced_biomes) > 0)

    return {
        'has_mixed_status': has_conflict,
        'native_biomes': native_biomes,
        'introduced_biomes': introduced_biomes,
        'biome_breakdown': statuses_by_biome,
        'recommendation': generate_mixed_status_recommendation(native_biomes, introduced_biomes)
    }


def generate_mixed_status_recommendation(native_biomes: list, introduced_biomes: list) -> str:
    """Generate human-readable recommendation for mixed-status species."""
    if not native_biomes and not introduced_biomes:
        return "Insufficient data to determine native range"
    elif native_biomes and not introduced_biomes:
        return f"Native across all analyzed biomes: {', '.join(native_biomes)}"
    elif introduced_biomes and not native_biomes:
        return f"Introduced/invasive across all analyzed biomes: {', '.join(introduced_biomes)}"
    else:
        return f"MIXED STATUS: Native in {', '.join(native_biomes)}; " \
               f"Introduced/invasive in {', '.join(introduced_biomes)}. " \
               f"Use biome-specific status for planting decisions."
```

### Step 3: Complete Native Status Pipeline

```python
def compute_native_status_complete(
    taxon_id: str,
    location: Tuple[float, float]
) -> dict:
    """
    Complete pipeline combining invasive elimination + sub-country clustering.

    Order of operations:
    1. ELIMINATE known invasives first (process of elimination)
    2. CLUSTER occurrences by ecoregion/biome (sub-country analysis)
    3. RESOLVE conflicts using ecological boundaries
    4. SCORE confidence based on evidence quality
    """
    lat, lng = location
    eco_id = get_ecoregion_for_point(lat, lng)
    ecoregion = get_ecoregion(eco_id)
    country_code = get_country_for_point(lat, lng)

    # ========================================
    # STEP 1: Invasive-first elimination
    # ========================================
    invasive_check = apply_invasive_elimination(taxon_id, eco_id, country_code)

    if invasive_check['eliminated_as_invasive']:
        # Known invasive - no need for further analysis
        return {
            'status': 'invasive',
            'confidence_score': invasive_check['confidence'],
            'confidence_tier': 1,  # High confidence from authoritative list
            'determination_method': 'invasive_list_elimination',
            'source': invasive_check['source'],
            'message': f"Species is on {invasive_check['source']} invasive list for this region",
            'biome_specific': False  # Applies to whole country/region
        }

    # ========================================
    # STEP 2: Sub-country clustering
    # ========================================
    clustering = analyze_subcountry_clustering(taxon_id, country_code)

    # Get status for THIS specific ecoregion
    this_ecoregion_status = clustering['ecoregion_clusters'].get(eco_id)

    if this_ecoregion_status:
        # We have occurrence data for this exact ecoregion
        status = this_ecoregion_status['dominant_status']
        confidence = this_ecoregion_status['confidence']

        # Check if status differs from other biomes in same country
        mixed_status = clustering['has_mixed_status']

        return {
            'status': normalize_status(status),
            'confidence_score': confidence,
            'confidence_tier': assign_tier(confidence),
            'determination_method': 'ecoregion_occurrence_clustering',
            'ecoregion': ecoregion['eco_name'],
            'biome': ecoregion['biome_name'],
            'biome_specific': True,
            'occurrence_count': this_ecoregion_status['occurrence_count'],
            'earliest_record': this_ecoregion_status['earliest_year'],
            'mixed_status_warning': mixed_status,
            'country_level_conflict': clustering['country_conflict_resolved'],
            'biome_breakdown': clustering['biome_summary'] if mixed_status else None
        }

    # ========================================
    # STEP 3: Infer from same-biome ecoregions
    # ========================================
    # No direct occurrence data for this ecoregion
    # Look at other ecoregions in the SAME biome
    same_biome_ecoregions = [
        c for eco_id, c in clustering['ecoregion_clusters'].items()
        if c['biome'] == ecoregion['biome_name']
    ]

    if same_biome_ecoregions:
        # Aggregate status from same biome
        biome_status = aggregate_biome_status(same_biome_ecoregions)

        return {
            'status': biome_status['status'],
            'confidence_score': biome_status['confidence'] * 0.8,  # Reduce for inference
            'confidence_tier': assign_tier(biome_status['confidence'] * 0.8),
            'determination_method': 'biome_inference',
            'inferred_from_biome': ecoregion['biome_name'],
            'supporting_ecoregions': len(same_biome_ecoregions),
            'message': f"Inferred from {len(same_biome_ecoregions)} ecoregions in same biome"
        }

    # ========================================
    # STEP 4: Fall back to country-level data
    # ========================================
    countries_native = get_species_native_countries(taxon_id)

    if country_code in countries_native:
        return {
            'status': 'likely_native',
            'confidence_score': 0.5,
            'confidence_tier': 3,
            'determination_method': 'country_native_list',
            'message': f"Listed as native to {country_code} but no ecoregion-level data"
        }

    return {
        'status': 'uncertain',
        'confidence_score': 0.2,
        'confidence_tier': 4,
        'determination_method': 'insufficient_data',
        'message': "No occurrence data or checklist entries for this region"
    }
```

### Invasive List Data Sources

| Source | Coverage | Granularity | Access |
|--------|----------|-------------|--------|
| **GRIIS** | 196 countries, ~30K species | Country | griis.org (free) |
| **GISD** | Global, 900+ species | Regional/habitat | iucngisd.org (free) |
| **CABI ISC** | Global, 1,500+ species | Country + habitat | cabi.org (partial free) |
| **EPPO** | Europe, Mediterranean | Country | eppo.int (free) |
| **USDA PLANTS** | USA only | State level | plants.usda.gov (free) |
| **GIATAR** | 827K taxon-country pairs | Country | Nature Scientific Data |

### Database Schema for Sub-Country Analysis

```sql
-- Track status at ecoregion level (not just country)
CREATE TABLE species_ecoregion_native_status (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    eco_id INTEGER NOT NULL,
    biome_name VARCHAR(100),
    realm VARCHAR(50),
    country_codes TEXT[],  -- Countries this ecoregion spans

    -- Status from clustering analysis
    status VARCHAR(20),  -- native, introduced, invasive, naturalised, uncertain
    status_confidence DECIMAL(4,3),

    -- Evidence
    occurrence_count INTEGER,
    native_tagged_count INTEGER,
    introduced_tagged_count INTEGER,
    invasive_tagged_count INTEGER,
    untagged_count INTEGER,

    -- Weighted scores (by coordinate accuracy)
    weighted_native DECIMAL(10,3),
    weighted_introduced DECIMAL(10,3),

    -- Temporal
    earliest_year INTEGER,
    latest_year INTEGER,

    -- Spatial clustering
    spatial_dispersion DECIMAL(4,3),  -- 0=clustered, 1=dispersed
    centroid GEOMETRY(Point, 4326),

    -- Invasive list checks
    on_griis_invasive BOOLEAN DEFAULT FALSE,
    on_gisd BOOLEAN DEFAULT FALSE,
    on_cabi_invasive BOOLEAN DEFAULT FALSE,
    invasive_list_source VARCHAR(50),

    -- Cross-biome conflict detection
    conflicts_with_other_biomes BOOLEAN DEFAULT FALSE,
    conflicting_biomes TEXT[],

    -- Metadata
    computed_at TIMESTAMP DEFAULT NOW(),
    algorithm_version VARCHAR(10) DEFAULT '2.0',

    UNIQUE(taxon_id, eco_id)
);

-- Biome-level summary (aggregated from ecoregions)
CREATE TABLE species_biome_native_status (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    biome_name VARCHAR(100) NOT NULL,
    realm VARCHAR(50),

    -- Aggregated status
    status VARCHAR(20),
    confidence DECIMAL(4,3),

    -- Evidence
    ecoregion_count INTEGER,
    total_occurrences INTEGER,

    -- Conflict tracking
    has_internal_conflict BOOLEAN DEFAULT FALSE,  -- Different status in same biome
    conflicting_with_country_data BOOLEAN DEFAULT FALSE,

    UNIQUE(taxon_id, biome_name)
);

-- Indexes for fast lookup
CREATE INDEX idx_eco_status_taxon ON species_ecoregion_native_status(taxon_id);
CREATE INDEX idx_eco_status_eco ON species_ecoregion_native_status(eco_id);
CREATE INDEX idx_eco_status_biome ON species_ecoregion_native_status(biome_name);
CREATE INDEX idx_eco_status_invasive ON species_ecoregion_native_status(status)
    WHERE status = 'invasive';
CREATE INDEX idx_biome_status_taxon ON species_biome_native_status(taxon_id);
```

---

### MVP Accuracy Weighting

Location accuracy dramatically affects confidence:

```python
def weight_occurrence_by_accuracy(
    occurrence: dict,
    accuracy_meters: float
) -> float:
    """
    Weight individual occurrences by coordinate accuracy.

    Accuracy Tiers:
    - <10m (GPS precise): weight 1.0
    - <100m (GPS standard): weight 0.9
    - <1000m (locality): weight 0.6
    - <10000m (region): weight 0.3
    - >10000m (country centroid): weight 0.1
    """
    if accuracy_meters is None:
        return 0.5  # Unknown = median weight

    accuracy_weights = [
        (10, 1.0),
        (100, 0.9),
        (1000, 0.6),
        (10000, 0.3),
        (float('inf'), 0.1)
    ]

    for threshold, weight in accuracy_weights:
        if accuracy_meters <= threshold:
            return weight

    return 0.1
```

### MVP Database Schema

```sql
-- Enhanced occurrence table with accuracy
CREATE TABLE occurrences_enhanced (
    id BIGSERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) REFERENCES species(taxon_id),

    -- Location
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    geom GEOMETRY(Point, 4326),
    geohash_l7 VARCHAR(12),
    eco_id INTEGER REFERENCES ecoregions(eco_id),

    -- Status
    establishment_means VARCHAR(20),  -- NATIVE, INTRODUCED, NATURALISED, INVASIVE, MANAGED, UNCERTAIN

    -- Accuracy
    coordinate_uncertainty_m DECIMAL(10,2),
    accuracy_tier INTEGER,  -- 1=<10m, 2=<100m, 3=<1km, 4=<10km, 5=>10km

    -- Temporal
    observation_year INTEGER,
    observation_date DATE,

    -- Quality
    basis_of_record VARCHAR(30),
    identified_by VARCHAR(200),
    verification_status VARCHAR(30),

    -- Source
    gbif_id BIGINT,
    dataset_key UUID,
    institution_code VARCHAR(50),

    -- Computed
    occurrence_weight DECIMAL(4,3),  -- Pre-computed weight based on accuracy

    -- Metadata
    imported_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_occ_taxon ON occurrences_enhanced(taxon_id);
CREATE INDEX idx_occ_eco ON occurrences_enhanced(eco_id);
CREATE INDEX idx_occ_status ON occurrences_enhanced(establishment_means);
CREATE INDEX idx_occ_accuracy ON occurrences_enhanced(accuracy_tier);
CREATE INDEX idx_occ_geom ON occurrences_enhanced USING GIST(geom);
CREATE INDEX idx_occ_geohash ON occurrences_enhanced(geohash_l7);

-- Aggregated status per species-ecoregion
CREATE TABLE species_ecoregion_status (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) REFERENCES species(taxon_id),
    eco_id INTEGER REFERENCES ecoregions(eco_id),
    biome_name VARCHAR(100),
    realm VARCHAR(50),

    -- Status (MVP output)
    status VARCHAR(20),  -- native, introduced, naturalised, invasive, uncertain
    confidence_score DECIMAL(4,3),
    confidence_tier INTEGER,  -- 1-4

    -- Evidence counts (weighted by accuracy)
    total_occurrences INTEGER,
    weighted_occurrence_sum DECIMAL(10,3),
    native_weighted DECIMAL(10,3) DEFAULT 0,
    introduced_weighted DECIMAL(10,3) DEFAULT 0,
    naturalised_weighted DECIMAL(10,3) DEFAULT 0,
    invasive_weighted DECIMAL(10,3) DEFAULT 0,
    untagged_weighted DECIMAL(10,3) DEFAULT 0,

    -- Accuracy breakdown
    high_accuracy_count INTEGER,  -- <100m
    medium_accuracy_count INTEGER,  -- 100m-1km
    low_accuracy_count INTEGER,  -- >1km

    -- Temporal
    earliest_year INTEGER,
    latest_year INTEGER,
    temporal_span INTEGER,

    -- Checklist validation
    griis_status VARCHAR(20),
    iucn_origin VARCHAR(10),
    countries_native_match BOOLEAN,

    -- Conflict tracking
    has_conflict BOOLEAN DEFAULT FALSE,
    conflict_ratio DECIMAL(4,3),
    conflict_details JSONB,

    -- Metadata
    computed_at TIMESTAMP DEFAULT NOW(),
    algorithm_version VARCHAR(10) DEFAULT '1.0'
);
```

---

## Long-Term Scoring Formula (Full Model)

### The Species-Location Aptness Score

The full model produces a **composite score from -10 to +10** predicting:
1. Whether the species is native/invasive at the location
2. Whether the species will thrive (habitat suitability)
3. Whether the species will benefit local biodiversity

```python
def compute_species_location_aptness_score(
    taxon_id: str,
    location: Tuple[float, float],  # (lat, lng)
    include_components: bool = True
) -> dict:
    """
    Full Species-Location Aptness Score.

    Output range: -10 (highly detrimental) to +10 (highly beneficial)

    Components:
    1. Native Status Score (weight: 0.30) - Is it native here?
    2. Environmental Match Score (weight: 0.25) - Will it thrive here?
    3. Ecological Function Score (weight: 0.20) - Does it fill needed roles?
    4. Biotic Compatibility Score (weight: 0.15) - Will it integrate with local species?
    5. Remote Sensing Validation (weight: 0.10) - Is current habitat suitable?
    """
    eco_id = get_ecoregion_for_location(location)

    # ============================================================
    # COMPONENT 1: Native Status Score (-1.0 to +1.0)
    # ============================================================
    native_status = get_native_status_mvp(taxon_id, eco_id)
    native_scores = {
        'native': 1.0,
        'naturalised': 0.3,  # Established but not native
        'introduced': -0.2,  # Intentional introduction
        'invasive': -1.0,    # Documented harmful
        'uncertain': 0.0,
        'managed': 0.1       # Cultivated, controlled
    }
    native_component = native_scores.get(native_status['status'], 0.0)

    # Apply confidence adjustment
    native_component *= native_status['confidence_score']

    # ============================================================
    # COMPONENT 2: Environmental Match Score (0.0 to 1.0)
    # ============================================================
    env_match = compute_environmental_match(taxon_id, location)
    # Details in section below

    # ============================================================
    # COMPONENT 3: Ecological Function Score (0.0 to 1.0)
    # ============================================================
    eco_function = compute_ecological_function_score(taxon_id, eco_id)
    # Details in section below

    # ============================================================
    # COMPONENT 4: Biotic Compatibility Score (0.0 to 1.0)
    # ============================================================
    biotic_compat = compute_biotic_compatibility(taxon_id, eco_id)
    # Details in section below

    # ============================================================
    # COMPONENT 5: Remote Sensing Validation (0.0 to 1.0)
    # ============================================================
    rs_validation = compute_remote_sensing_validation(location)
    # Details in section below

    # ============================================================
    # WEIGHTED COMBINATION
    # ============================================================
    weights = {
        'native_status': 0.30,
        'environmental_match': 0.25,
        'ecological_function': 0.20,
        'biotic_compatibility': 0.15,
        'remote_sensing': 0.10
    }

    # Raw score: -1.0 to +1.0
    raw_score = (
        weights['native_status'] * native_component +
        weights['environmental_match'] * (env_match['score'] - 0.5) * 2 +  # Center at 0
        weights['ecological_function'] * (eco_function['score'] - 0.5) * 2 +
        weights['biotic_compatibility'] * (biotic_compat['score'] - 0.5) * 2 +
        weights['remote_sensing'] * (rs_validation['score'] - 0.5) * 2
    )

    # Scale to -10 to +10
    final_score = round(raw_score * 10, 1)

    # Calculate overall confidence
    overall_confidence = (
        native_status['confidence_score'] * 0.40 +
        env_match['confidence'] * 0.30 +
        eco_function['confidence'] * 0.15 +
        biotic_compat['confidence'] * 0.10 +
        rs_validation['confidence'] * 0.05
    )

    result = {
        'aptness_score': final_score,
        'interpretation': interpret_aptness_score(final_score),
        'confidence': round(overall_confidence, 3),
        'confidence_tier': assign_confidence_tier(overall_confidence),
        'recommendation': generate_recommendation(final_score, native_status['status'])
    }

    if include_components:
        result['components'] = {
            'native_status': {
                'status': native_status['status'],
                'score': native_component,
                'confidence': native_status['confidence_score'],
                'weight': weights['native_status']
            },
            'environmental_match': {
                'score': env_match['score'],
                'confidence': env_match['confidence'],
                'details': env_match['details'],
                'weight': weights['environmental_match']
            },
            'ecological_function': {
                'score': eco_function['score'],
                'confidence': eco_function['confidence'],
                'functions': eco_function['functions'],
                'weight': weights['ecological_function']
            },
            'biotic_compatibility': {
                'score': biotic_compat['score'],
                'confidence': biotic_compat['confidence'],
                'interactions': biotic_compat['interactions'],
                'weight': weights['biotic_compatibility']
            },
            'remote_sensing': {
                'score': rs_validation['score'],
                'confidence': rs_validation['confidence'],
                'habitat_state': rs_validation['habitat_state'],
                'weight': weights['remote_sensing']
            }
        }

    return result


def interpret_aptness_score(score: float) -> str:
    """Human-readable interpretation of aptness score."""
    if score >= 8:
        return "Excellent - Native species ideally suited to this location"
    elif score >= 5:
        return "Good - Species likely to thrive and benefit ecosystem"
    elif score >= 2:
        return "Acceptable - Species compatible but not optimal"
    elif score >= -2:
        return "Neutral - Limited data or mixed indicators"
    elif score >= -5:
        return "Caution - Potential negative impact, consider alternatives"
    elif score >= -8:
        return "Avoid - High risk of invasive behavior or ecosystem harm"
    else:
        return "Do Not Plant - Documented invasive with severe impacts"
```

### Component 2: Environmental Match Score

```python
def compute_environmental_match(
    taxon_id: str,
    location: Tuple[float, float]
) -> dict:
    """
    Match species environmental preferences to location characteristics.

    Uses fields from species knowledge schema:
    - elevation_ranges_ai/human
    - compatible_soil_types_ai/human
    - soil_texture_prefered/tolerated
    - pH_prefered/tolerated
    - habitat_ai/human
    - climate_change_vulnerability

    Uses environmental layers:
    - WorldClim bioclimatic variables
    - SoilGrids 250m
    - Copernicus Land Cover
    - SRTM Elevation
    """
    species = get_species_profile(taxon_id)
    location_env = extract_environmental_variables(location)

    scores = []
    confidences = []
    details = {}

    # ---- ELEVATION MATCH ----
    if species.get('elevation_ranges'):
        elev_range = parse_elevation_range(species['elevation_ranges'])
        location_elev = location_env['elevation_m']

        elev_score = compute_range_match(
            value=location_elev,
            preferred_min=elev_range['preferred_min'],
            preferred_max=elev_range['preferred_max'],
            tolerated_min=elev_range.get('tolerated_min'),
            tolerated_max=elev_range.get('tolerated_max')
        )
        scores.append(('elevation', elev_score, 0.20))
        confidences.append(0.9 if 'human' in species.get('elevation_source', '') else 0.7)
        details['elevation'] = {
            'species_range': elev_range,
            'location_value': location_elev,
            'match_score': elev_score
        }

    # ---- SOIL TEXTURE MATCH ----
    if species.get('soil_texture_prefered'):
        preferred_soils = parse_soil_list(species['soil_texture_prefered'])
        tolerated_soils = parse_soil_list(species.get('soil_texture_tolerated', ''))
        location_soil = location_env['soil_texture']

        if location_soil in preferred_soils:
            soil_score = 1.0
        elif location_soil in tolerated_soils:
            soil_score = 0.6
        else:
            soil_score = 0.2

        scores.append(('soil_texture', soil_score, 0.20))
        confidences.append(0.85)
        details['soil_texture'] = {
            'preferred': preferred_soils,
            'tolerated': tolerated_soils,
            'location': location_soil,
            'match_score': soil_score
        }

    # ---- pH MATCH ----
    if species.get('ph_prefered'):
        ph_pref = parse_ph_category(species['ph_prefered'])
        ph_tolerated = parse_ph_category(species.get('ph_tolerated', ''))
        location_ph = location_env['soil_ph']

        ph_score = compute_categorical_match(
            value=categorize_ph(location_ph),
            preferred=ph_pref,
            tolerated=ph_tolerated
        )
        scores.append(('soil_ph', ph_score, 0.15))
        confidences.append(0.8)
        details['soil_ph'] = {
            'preferred': ph_pref,
            'location_value': location_ph,
            'match_score': ph_score
        }

    # ---- CLIMATE / BIOCLIM MATCH ----
    # Use Köppen-Geiger climate classification
    if species.get('biomes') or species.get('habitat'):
        species_climate_zones = infer_climate_zones(species)
        location_climate = location_env['koppen_climate']

        climate_score = compute_climate_compatibility(
            species_zones=species_climate_zones,
            location_zone=location_climate
        )
        scores.append(('climate', climate_score, 0.25))
        confidences.append(0.75)
        details['climate'] = {
            'species_zones': species_climate_zones,
            'location_zone': location_climate,
            'match_score': climate_score
        }

    # ---- LAND COVER MATCH ----
    if species.get('habitat') or species.get('forest_type'):
        preferred_landcover = infer_landcover_types(species)
        location_landcover = location_env['copernicus_landcover']

        landcover_score = compute_landcover_match(
            preferred=preferred_landcover,
            location=location_landcover
        )
        scores.append(('land_cover', landcover_score, 0.20))
        confidences.append(0.85)
        details['land_cover'] = {
            'preferred': preferred_landcover,
            'location': location_landcover,
            'match_score': landcover_score
        }

    # ---- AGGREGATE ----
    if scores:
        # Weighted average
        total_weight = sum(s[2] for s in scores)
        weighted_score = sum(s[1] * s[2] for s in scores) / total_weight
        avg_confidence = np.mean(confidences)
    else:
        weighted_score = 0.5  # No data = neutral
        avg_confidence = 0.3

    return {
        'score': round(weighted_score, 3),
        'confidence': round(avg_confidence, 3),
        'details': details,
        'variables_matched': len(scores)
    }


def extract_environmental_variables(location: Tuple[float, float]) -> dict:
    """
    Extract environmental variables for a location from all available layers.

    Sources:
    - SRTM: elevation_m
    - WorldClim: bio1-bio19, koppen_climate
    - SoilGrids: soil_texture, soil_ph, soil_oc
    - Copernicus: landcover class
    - One Earth: ecoregion, biome, realm
    """
    lat, lng = location

    return {
        # Topography
        'elevation_m': extract_srtm_elevation(lat, lng),
        'slope_degrees': extract_slope(lat, lng),
        'aspect': extract_aspect(lat, lng),

        # Climate (WorldClim BIO variables)
        'bio1_annual_mean_temp': extract_worldclim(lat, lng, 'bio1'),
        'bio4_temp_seasonality': extract_worldclim(lat, lng, 'bio4'),
        'bio12_annual_precip': extract_worldclim(lat, lng, 'bio12'),
        'bio15_precip_seasonality': extract_worldclim(lat, lng, 'bio15'),
        'koppen_climate': extract_koppen_geiger(lat, lng),

        # Soil (SoilGrids 250m)
        'soil_texture': extract_soilgrids(lat, lng, 'texture'),
        'soil_ph': extract_soilgrids(lat, lng, 'phh2o'),
        'soil_oc': extract_soilgrids(lat, lng, 'soc'),
        'soil_clay_pct': extract_soilgrids(lat, lng, 'clay'),
        'soil_sand_pct': extract_soilgrids(lat, lng, 'sand'),

        # Land Cover
        'copernicus_landcover': extract_copernicus_landcover(lat, lng),
        'sbtn_landcover': extract_sbtn_landcover(lat, lng),
        'forest_cover_pct': extract_forest_cover(lat, lng),

        # Biogeography
        'wwf_ecoregion': get_wwf_ecoregion(lat, lng),
        'one_earth_bioregion': get_one_earth_bioregion(lat, lng),
        'biome': get_biome(lat, lng),
        'realm': get_realm(lat, lng),

        # Forest quality
        'in_intact_forest': check_intact_forest(lat, lng),
        'distance_to_intact_forest_km': distance_to_intact_forest(lat, lng)
    }
```

### Component 3: Ecological Function Score

```python
def compute_ecological_function_score(
    taxon_id: str,
    eco_id: int
) -> dict:
    """
    Assess how well species' ecological functions match ecoregion needs.

    Uses species fields:
    - ecological_function_ai/human
    - functional_ecosystem_groups
    - successional_stage
    - forest_layers
    - tolerances

    Uses ecoregion data:
    - Current functional group composition
    - Degradation indicators
    - Restoration priorities
    """
    species = get_species_profile(taxon_id)
    ecoregion = get_ecoregion_profile(eco_id)

    functions = []
    score = 0.5  # Start neutral

    # ---- FUNCTIONAL ECOSYSTEM GROUP MATCH ----
    if species.get('functional_ecosystem_groups'):
        species_groups = parse_functional_groups(species['functional_ecosystem_groups'])
        ecoregion_groups = ecoregion.get('native_functional_groups', [])

        overlap = set(species_groups) & set(ecoregion_groups)
        if overlap:
            score += 0.15
            functions.append(f"Matches native functional groups: {', '.join(overlap)}")

    # ---- ECOLOGICAL FUNCTION ASSESSMENT ----
    eco_function = species.get('ecological_function_ai') or species.get('ecological_function_human')
    if eco_function:
        eco_function_lower = eco_function.lower()

        # Nitrogen fixation (high value for degraded lands)
        if 'nitrogen' in eco_function_lower or 'fix' in eco_function_lower:
            score += 0.10
            functions.append("Nitrogen fixation")

        # Carbon sequestration
        if 'carbon' in eco_function_lower or 'sequester' in eco_function_lower:
            score += 0.05
            functions.append("Carbon sequestration")

        # Soil stabilization
        if 'erosion' in eco_function_lower or 'soil stabil' in eco_function_lower:
            score += 0.08
            functions.append("Soil stabilization")

        # Water regulation
        if 'water' in eco_function_lower or 'watershed' in eco_function_lower:
            score += 0.05
            functions.append("Water regulation")

        # Pollinator support
        if 'pollinat' in eco_function_lower:
            score += 0.07
            functions.append("Pollinator support")

    # ---- SUCCESSIONAL STAGE APPROPRIATENESS ----
    if species.get('successional_stage'):
        species_stage = species['successional_stage'].lower()
        ecoregion_need = ecoregion.get('restoration_stage_need', 'unknown')

        if ecoregion_need == 'pioneer' and 'pioneer' in species_stage:
            score += 0.10
            functions.append("Pioneer species for early restoration")
        elif ecoregion_need == 'climax' and ('climax' in species_stage or 'late' in species_stage):
            score += 0.10
            functions.append("Climax species for mature forest")

    # ---- FOREST LAYER ----
    if species.get('forest_layers'):
        # Multi-layer species contribute more to ecosystem structure
        layers = species['forest_layers']
        if 'canopy' in layers.lower() and 'understory' in layers.lower():
            score += 0.05
            functions.append("Multi-layer contribution")

    # Cap score at 1.0
    score = min(1.0, score)

    # Confidence based on data availability
    data_fields = sum([
        bool(species.get('ecological_function_ai') or species.get('ecological_function_human')),
        bool(species.get('functional_ecosystem_groups')),
        bool(species.get('successional_stage')),
        bool(species.get('forest_layers'))
    ])
    confidence = 0.4 + (data_fields * 0.15)  # 0.4 to 1.0

    return {
        'score': round(score, 3),
        'confidence': round(confidence, 3),
        'functions': functions,
        'data_completeness': data_fields / 4
    }
```

### Component 4: Biotic Compatibility Score

```python
def compute_biotic_compatibility(
    taxon_id: str,
    eco_id: int
) -> dict:
    """
    Assess species' biotic interactions with ecoregion species.

    Uses GloBI fields:
    - Globi_pollinatedBy
    - Globi_flowersVisitedBy
    - Globi_eatenBy
    - Globi_hasParasite
    - Globi_hasPathogen
    - Globi_hasDispersalVector
    - Globi_preyedUponBy
    - Globi_hasParasitoid

    Also uses:
    - associated_species
    """
    species = get_species_profile(taxon_id)
    ecoregion_species = get_ecoregion_species_list(eco_id)

    interactions = []
    score = 0.5  # Start neutral
    confidence_factors = []

    # ---- POLLINATOR AVAILABILITY ----
    pollinators = species.get('Globi_pollinatedBy', '').split(';')
    pollinators = [p.strip() for p in pollinators if p.strip()]

    if pollinators:
        # Check if any pollinators exist in ecoregion
        pollinator_overlap = check_species_overlap(pollinators, ecoregion_species)
        if pollinator_overlap > 0:
            score += 0.10 * min(1.0, pollinator_overlap / len(pollinators))
            interactions.append(f"Pollinators present: {pollinator_overlap}/{len(pollinators)}")
        confidence_factors.append(0.8)

    # ---- SEED DISPERSERS ----
    dispersers = species.get('Globi_hasDispersalVector', '').split(';')
    dispersers = [d.strip() for d in dispersers if d.strip()]

    if dispersers:
        disperser_overlap = check_species_overlap(dispersers, ecoregion_species)
        if disperser_overlap > 0:
            score += 0.08 * min(1.0, disperser_overlap / len(dispersers))
            interactions.append(f"Seed dispersers present: {disperser_overlap}/{len(dispersers)}")
        confidence_factors.append(0.75)

    # ---- HERBIVORE PRESSURE ----
    herbivores = species.get('Globi_eatenBy', '').split(';')
    herbivores = [h.strip() for h in herbivores if h.strip()]

    if herbivores:
        # Some herbivore presence is natural; too many might be problematic for introduced species
        herbivore_overlap = check_species_overlap(herbivores, ecoregion_species)
        # Native species can handle native herbivores
        # This is context-dependent on native status
        confidence_factors.append(0.6)

    # ---- PARASITE/PATHOGEN RISK ----
    parasites = species.get('Globi_hasParasite', '').split(';')
    pathogens = species.get('Globi_hasPathogen', '').split(';')

    # Novel pathogens in new locations can be devastating
    # This is more relevant for introduced species

    # ---- ASSOCIATED SPECIES ----
    associated = species.get('associated_species', '').split(';')
    associated = [a.strip() for a in associated if a.strip()]

    if associated:
        assoc_overlap = check_species_overlap(associated, ecoregion_species)
        if assoc_overlap > 0:
            score += 0.12 * min(1.0, assoc_overlap / min(5, len(associated)))
            interactions.append(f"Associated species present: {assoc_overlap}")
        confidence_factors.append(0.7)

    # Cap at 1.0
    score = min(1.0, max(0.0, score))

    # Average confidence from available data
    confidence = np.mean(confidence_factors) if confidence_factors else 0.4

    return {
        'score': round(score, 3),
        'confidence': round(confidence, 3),
        'interactions': interactions,
        'data_sources': len(confidence_factors)
    }
```

### Component 5: Remote Sensing Validation

```python
def compute_remote_sensing_validation(
    location: Tuple[float, float]
) -> dict:
    """
    Validate location habitat state using remote sensing.

    Uses:
    - Copernicus Land Cover (current state)
    - Intact Forest Landscapes (forest quality)
    - SBTN Land Cover (science-based targets)
    - AlphaEarth embeddings (environmental context)

    This component answers: "Is this location suitable for tree planting?"
    """
    lat, lng = location

    # ---- CURRENT LAND COVER ----
    landcover = extract_copernicus_landcover(lat, lng)

    # Score based on current state
    landcover_scores = {
        'forest': 0.9,  # Already forested - good for native species
        'shrubland': 0.8,  # Natural vegetation
        'grassland': 0.7,  # Potential restoration site
        'cropland': 0.4,  # Agricultural - need conversion
        'urban': 0.2,  # Limited potential
        'barren': 0.5,  # Could be natural or degraded
        'wetland': 0.75,  # Specialized habitat
    }
    landcover_score = landcover_scores.get(landcover, 0.5)

    # ---- INTACT FOREST PROXIMITY ----
    in_intact = check_intact_forest(lat, lng)
    distance_to_intact = distance_to_intact_forest(lat, lng)

    if in_intact:
        intact_score = 1.0  # Prime habitat
    elif distance_to_intact < 1:  # Within 1km
        intact_score = 0.85
    elif distance_to_intact < 10:  # Within 10km
        intact_score = 0.7
    elif distance_to_intact < 50:  # Within 50km
        intact_score = 0.5
    else:
        intact_score = 0.3  # Isolated from intact forests

    # ---- SBTN LAND COVER TARGET ----
    sbtn_cover = extract_sbtn_landcover(lat, lng)
    # SBTN indicates what the land SHOULD be
    sbtn_is_forest_target = sbtn_cover in ['natural_forest', 'plantation_potential']
    sbtn_score = 0.8 if sbtn_is_forest_target else 0.4

    # ---- ALPHA EARTH EMBEDDING (if available) ----
    try:
        alpha_embedding = get_alphaearth_embedding(lat, lng)
        # Compare to typical forest embeddings
        forest_similarity = compute_forest_embedding_similarity(alpha_embedding)
        alpha_score = forest_similarity
        alpha_confidence = 0.9
    except:
        alpha_score = 0.5
        alpha_confidence = 0.3

    # ---- AGGREGATE ----
    weights = [0.25, 0.30, 0.20, 0.25]  # landcover, intact, sbtn, alpha
    scores = [landcover_score, intact_score, sbtn_score, alpha_score]

    weighted_score = sum(w * s for w, s in zip(weights, scores))

    # Confidence based on data availability
    confidence = 0.7 + (0.2 if in_intact is not None else 0) + (0.1 * alpha_confidence)

    return {
        'score': round(weighted_score, 3),
        'confidence': round(min(1.0, confidence), 3),
        'habitat_state': {
            'current_landcover': landcover,
            'in_intact_forest': in_intact,
            'distance_to_intact_km': distance_to_intact,
            'sbtn_classification': sbtn_cover
        },
        'sub_scores': {
            'landcover': landcover_score,
            'intact_forest': intact_score,
            'sbtn': sbtn_score,
            'alpha_earth': alpha_score
        }
    }
```

---

## Missing Datasets for Full Model

### Critical (Required for Full Model)

| Dataset | Purpose | Source | Integration Effort |
|---------|---------|--------|-------------------|
| **GBIF with establishmentMeans** | Native status ground truth | GBIF API | Medium - new download |
| **GBIF coordinateUncertaintyInMeters** | Accuracy weighting | GBIF API | Same download |
| **GRIIS country checklists** | Invasive validation | griis.org | Medium - taxonomy mapping |
| **WorldClim BIO variables** | Climate matching | worldclim.org | Low - raster extraction |
| **SoilGrids 250m** | Soil matching | soilgrids.org | Medium - API integration |
| **Köppen-Geiger classification** | Climate zones | Already have folder | Low - integrate existing |

### High Priority (Improves Accuracy)

| Dataset | Purpose | Source | Integration Effort |
|---------|---------|--------|-------------------|
| **IUCN Range Polygons** | Native range validation | IUCN API | High - requires token |
| **GIATAR invasive traits** | Impact severity | Nature Scientific Data | Medium |
| **GloBI interaction data** | Biotic compatibility | globalbioticinteractions.org | Medium - API |
| **Functional ecosystem groups** | Ecological function | Already have folder | Low - integrate |
| **SBTN Land Cover** | Target habitat | Already have folder | Low - integrate |

### Medium Priority (Enhances Model)

| Dataset | Purpose | Source | Integration Effort |
|---------|---------|--------|-------------------|
| **One Earth Bioregions 2023** | Alternative boundaries | Already have folder | Low |
| **Copernicus Land Cover** | Current habitat | Already have folder | Low |
| **Hansen Tree Cover** | Forest change detection | GEE | Medium |
| **AlphaEarth embeddings** | Environmental similarity | Your existing work | Medium - scale up |

### Nice to Have (Future Enhancements)

| Dataset | Purpose | Source | Integration Effort |
|---------|---------|--------|-------------------|
| **PREDICTS biodiversity data** | Impact validation | NHM London | High |
| **TRY plant traits** | Functional traits | try-db.org | High - requires application |
| **BIEN occurrence data** | Additional occurrences | bien.nceas.ucsb.edu | Medium |
| **Historical Landsat archive** | Temporal validation | GEE | High |

---

## Implementation Phases (Updated)

### Phase 1: MVP Data & Basic Scoring (Weeks 1-6)

**Week 1-2: Enhanced GBIF Download**
- [ ] Download GBIF occurrences with: establishmentMeans, coordinateUncertaintyInMeters, basisOfRecord
- [ ] Filter to Treekipedia species taxonomy
- [ ] Create enhanced parquet: `Treekipedia_occ_enhanced_v2.parquet`
- [ ] Expected: 20-40M records with ~30-50% having establishmentMeans

**Week 2-3: Data Loading & Schema**
- [ ] Create `occurrences_enhanced` table
- [ ] Load enhanced occurrence data
- [ ] Pre-compute accuracy weights
- [ ] Create `species_ecoregion_status` aggregation table

**Week 3-4: MVP Scoring Implementation**
- [ ] Implement `calculate_mvp_confidence()` function
- [ ] Implement accuracy-weighted status aggregation
- [ ] Implement conflict resolution algorithm
- [ ] Integrate GRIIS checklist validation

**Week 5-6: API & Testing**
- [ ] API endpoint: `GET /api/species/{taxon_id}/native-status`
- [ ] API endpoint: `GET /api/location/{lat}/{lng}/native-species`
- [ ] Unit tests with known invasive species
- [ ] Validation against GRIIS (target >85% agreement)
- [ ] Basic frontend integration

**MVP Deliverables:**
- Native status API with confidence scores
- Accuracy-weighted occurrence analysis
- Conflict detection and resolution
- GRIIS validation layer

### Phase 2: Environmental Matching (Weeks 7-14)

**Week 7-8: Environmental Layer Integration**
- [ ] Integrate WorldClim BIO variables
- [ ] Integrate SoilGrids 250m API
- [ ] Integrate Köppen-Geiger from existing folder
- [ ] Create `extract_environmental_variables()` function

**Week 9-10: Species-Environment Matching**
- [ ] Parse species soil/pH/elevation preferences from schema
- [ ] Implement `compute_environmental_match()` function
- [ ] Create species environment profiles for 23,077 species with soil data
- [ ] Validate against known species distributions

**Week 11-12: Ecological Function Integration**
- [ ] Parse functional_ecosystem_groups data
- [ ] Implement `compute_ecological_function_score()` function
- [ ] Create ecoregion function profiles
- [ ] Match species functions to ecoregion needs

**Week 13-14: Biotic Compatibility**
- [ ] Parse GloBI interaction fields
- [ ] Build ecoregion species lists
- [ ] Implement `compute_biotic_compatibility()` function
- [ ] Test interaction overlap calculations

**Phase 2 Deliverables:**
- Environmental match scoring
- Ecological function assessment
- Biotic compatibility analysis
- Extended API with component breakdown

### Phase 3: Full Model & Validation (Weeks 15-26)

**Week 15-18: Remote Sensing Integration**
- [ ] Integrate Copernicus Land Cover
- [ ] Integrate SBTN Land Cover
- [ ] Implement intact forest proximity calculation
- [ ] Implement `compute_remote_sensing_validation()` function

**Week 19-22: AlphaEarth Integration**
- [ ] Scale AlphaEarth embedding extraction
- [ ] Create forest/habitat similarity metrics
- [ ] Implement temporal embedding comparison
- [ ] Validate historical occurrence data

**Week 23-24: Model Calibration**
- [ ] Calibrate component weights using validation data
- [ ] Test against PREDICTS biodiversity outcomes (if available)
- [ ] Refine confidence calculations
- [ ] Expert review of methodology

**Week 25-26: Production Release**
- [ ] Full `compute_species_location_aptness_score()` implementation
- [ ] Frontend integration with component visualization
- [ ] API documentation
- [ ] Performance optimization
- [ ] User testing and feedback

**Full Model Deliverables:**
- Complete Species-Location Aptness Score
- All 5 component scores
- Confidence tiers with transparency
- Frontend visualization
- Production API

---

## Database Schema (Complete)

```sql
-- ============================================================
-- ENHANCED OCCURRENCE DATA
-- ============================================================
CREATE TABLE occurrences_enhanced (
    id BIGSERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,

    -- Location
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    geom GEOMETRY(Point, 4326),
    geohash_l7 VARCHAR(12),
    eco_id INTEGER,
    biome_name VARCHAR(100),
    realm VARCHAR(50),

    -- Status
    establishment_means VARCHAR(20),

    -- Accuracy
    coordinate_uncertainty_m DECIMAL(10,2),
    accuracy_tier INTEGER,
    occurrence_weight DECIMAL(4,3),

    -- Temporal
    observation_year INTEGER,
    observation_date DATE,

    -- Quality
    basis_of_record VARCHAR(30),
    identified_by VARCHAR(200),
    verification_status VARCHAR(30),

    -- Source
    gbif_id BIGINT,
    dataset_key UUID,

    -- Metadata
    imported_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SPECIES-ECOREGION STATUS (MVP OUTPUT)
-- ============================================================
CREATE TABLE species_ecoregion_status (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    eco_id INTEGER NOT NULL,
    biome_name VARCHAR(100),
    realm VARCHAR(50),

    -- MVP Status
    status VARCHAR(20),
    confidence_score DECIMAL(4,3),
    confidence_tier INTEGER,

    -- Occurrence evidence (weighted)
    total_occurrences INTEGER,
    weighted_sum DECIMAL(10,3),
    native_weighted DECIMAL(10,3) DEFAULT 0,
    introduced_weighted DECIMAL(10,3) DEFAULT 0,
    naturalised_weighted DECIMAL(10,3) DEFAULT 0,
    invasive_weighted DECIMAL(10,3) DEFAULT 0,

    -- Accuracy breakdown
    high_accuracy_count INTEGER,
    medium_accuracy_count INTEGER,
    low_accuracy_count INTEGER,
    avg_accuracy_m DECIMAL(10,2),

    -- Temporal
    earliest_year INTEGER,
    latest_year INTEGER,

    -- Validation
    griis_status VARCHAR(20),
    countries_native_match BOOLEAN,

    -- Conflict
    has_conflict BOOLEAN DEFAULT FALSE,
    conflict_ratio DECIMAL(4,3),

    -- Metadata
    computed_at TIMESTAMP DEFAULT NOW(),
    algorithm_version VARCHAR(10) DEFAULT '2.0',

    UNIQUE(taxon_id, eco_id)
);

-- ============================================================
-- ENVIRONMENTAL PROFILES (FOR FULL MODEL)
-- ============================================================
CREATE TABLE location_environment_cache (
    geohash_l5 VARCHAR(8) PRIMARY KEY,  -- ~5km resolution cache

    -- Topography
    elevation_m INTEGER,
    slope_degrees DECIMAL(4,1),

    -- Climate (WorldClim)
    bio1_annual_temp DECIMAL(4,1),
    bio4_temp_seasonality DECIMAL(6,1),
    bio12_annual_precip INTEGER,
    bio15_precip_seasonality DECIMAL(5,1),
    koppen_climate VARCHAR(5),

    -- Soil (SoilGrids)
    soil_texture VARCHAR(30),
    soil_ph DECIMAL(3,1),
    soil_oc DECIMAL(4,2),

    -- Land Cover
    copernicus_landcover VARCHAR(50),
    sbtn_landcover VARCHAR(50),
    forest_cover_pct DECIMAL(4,1),

    -- Forest Quality
    in_intact_forest BOOLEAN,
    distance_to_intact_km DECIMAL(6,2),

    -- Metadata
    extracted_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SPECIES ENVIRONMENT PROFILES (PARSED FROM SCHEMA)
-- ============================================================
CREATE TABLE species_environment_profile (
    taxon_id VARCHAR(50) PRIMARY KEY,

    -- Elevation
    elevation_min_m INTEGER,
    elevation_max_m INTEGER,
    elevation_optimal_m INTEGER,

    -- Soil
    soil_textures_preferred TEXT[],
    soil_textures_tolerated TEXT[],
    ph_preferred VARCHAR(20),
    ph_tolerated VARCHAR(20),

    -- Climate
    climate_zones TEXT[],
    biomes TEXT[],

    -- Habitat
    habitat_types TEXT[],
    forest_types TEXT[],

    -- Functional
    functional_groups TEXT[],
    successional_stage VARCHAR(30),
    ecological_functions TEXT[],

    -- Confidence
    data_completeness DECIMAL(3,2),

    -- Metadata
    parsed_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- APTNESS SCORES (FULL MODEL OUTPUT)
-- ============================================================
CREATE TABLE species_location_aptness_scores (
    id BIGSERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    geohash_l5 VARCHAR(8) NOT NULL,  -- ~5km resolution

    -- Final Score
    aptness_score DECIMAL(4,1),  -- -10 to +10
    confidence DECIMAL(4,3),
    confidence_tier INTEGER,

    -- Component Scores
    native_status_component DECIMAL(4,3),
    environmental_match_component DECIMAL(4,3),
    ecological_function_component DECIMAL(4,3),
    biotic_compatibility_component DECIMAL(4,3),
    remote_sensing_component DECIMAL(4,3),

    -- Recommendation
    recommendation VARCHAR(100),

    -- Metadata
    computed_at TIMESTAMP DEFAULT NOW(),
    algorithm_version VARCHAR(10) DEFAULT '2.0',

    UNIQUE(taxon_id, geohash_l5)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_occ_enh_taxon ON occurrences_enhanced(taxon_id);
CREATE INDEX idx_occ_enh_eco ON occurrences_enhanced(eco_id);
CREATE INDEX idx_occ_enh_status ON occurrences_enhanced(establishment_means);
CREATE INDEX idx_occ_enh_geom ON occurrences_enhanced USING GIST(geom);

CREATE INDEX idx_ses_taxon ON species_ecoregion_status(taxon_id);
CREATE INDEX idx_ses_eco ON species_ecoregion_status(eco_id);
CREATE INDEX idx_ses_status ON species_ecoregion_status(status);
CREATE INDEX idx_ses_confidence ON species_ecoregion_status(confidence_score DESC);

CREATE INDEX idx_aptness_taxon ON species_location_aptness_scores(taxon_id);
CREATE INDEX idx_aptness_geohash ON species_location_aptness_scores(geohash_l5);
CREATE INDEX idx_aptness_score ON species_location_aptness_scores(aptness_score DESC);
```

---

## API Endpoints (Complete)

### MVP Endpoints

```yaml
# Native Status for Species at Location
GET /api/v2/species/{taxon_id}/native-status
  Parameters:
    - lat: float (required if no eco_id)
    - lng: float (required if no eco_id)
    - eco_id: int (alternative to lat/lng)
  Response:
    status: "native" | "introduced" | "naturalised" | "invasive" | "uncertain"
    confidence_score: 0.0-1.0
    confidence_tier: 1-4
    evidence:
      occurrence_count: int
      weighted_native: float
      weighted_introduced: float
      earliest_year: int
      griis_match: bool
      accuracy_breakdown: {...}

# Native Species for Location
GET /api/v2/location/{lat}/{lng}/native-species
  Parameters:
    - status: "native" | "introduced" | "invasive" | "all"
    - min_confidence: float (default 0.5)
    - limit: int (default 100)
  Response:
    species: [
      {taxon_id, species_scientific_name, status, confidence_score}
    ]

# Ecoregion Species Summary
GET /api/v2/ecoregion/{eco_id}/species-status
  Response:
    native_count: int
    introduced_count: int
    invasive_count: int
    uncertain_count: int
    species: [...]
```

### Full Model Endpoints

```yaml
# Full Aptness Score
GET /api/v2/species/{taxon_id}/aptness-score
  Parameters:
    - lat: float (required)
    - lng: float (required)
    - include_components: bool (default true)
  Response:
    aptness_score: -10 to +10
    interpretation: string
    confidence: 0.0-1.0
    confidence_tier: 1-4
    recommendation: string
    components:
      native_status: {...}
      environmental_match: {...}
      ecological_function: {...}
      biotic_compatibility: {...}
      remote_sensing: {...}

# Batch Aptness Scores
POST /api/v2/aptness-scores/batch
  Body:
    queries: [
      {taxon_id, lat, lng},
      ...
    ]
  Response:
    results: [
      {taxon_id, lat, lng, aptness_score, confidence, recommendation}
    ]

# Location Recommendations
GET /api/v2/location/{lat}/{lng}/recommended-species
  Parameters:
    - min_score: float (default 5.0)
    - purpose: "restoration" | "agroforestry" | "urban" | "any"
    - limit: int (default 20)
  Response:
    species: [
      {taxon_id, species_scientific_name, aptness_score, recommendation, key_functions}
    ]
```

---

## Success Metrics (Updated)

### MVP Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Species with native status | 50,000+ (74%) | Database query |
| Ecoregions with status data | 600+ (71%) | Database query |
| Average confidence score | >0.55 | Database aggregate |
| Tier 1-2 coverage | >35% of pairs | Database query |
| GRIIS agreement rate | >85% | Validation script |
| API response time (p95) | <200ms | Monitoring |

### Full Model Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Species with aptness scores | 60,000+ (89%) | Database query |
| Locations (geohash_l5) covered | 500,000+ | Database query |
| Environmental match coverage | 40,000+ species | Based on 23K with soil data |
| Component score availability | >80% have 4+ components | Database query |
| Validation vs known outcomes | >75% correlation | External validation |
| User satisfaction | >4.2/5.0 | Survey |

---

## Appendix: Weight Calibration Strategy

### Initial Weights (Expert-Derived)

```python
initial_weights = {
    'native_status': 0.30,  # Most important for biodiversity impact
    'environmental_match': 0.25,  # Will it survive?
    'ecological_function': 0.20,  # Will it contribute?
    'biotic_compatibility': 0.15,  # Will it integrate?
    'remote_sensing': 0.10  # Is habitat suitable now?
}
```

### Calibration Approach

1. **Collect validation data** from:
   - Known successful reforestation projects
   - Documented invasion cases
   - Expert assessments

2. **Fit regression model**:
   ```python
   # Use logistic regression to predict success/failure
   from sklearn.linear_model import LogisticRegression

   model = LogisticRegression()
   model.fit(X=component_scores, y=outcomes)

   # Extract calibrated weights
   calibrated_weights = normalize_to_sum_1(model.coef_)
   ```

3. **Validate and iterate** with cross-validation

4. **Regional variants** may be needed:
   - Tropical vs temperate
   - Island vs continental
   - Degraded vs intact landscapes

---

## Related Documents

- [Species knowledge schema.md](./ontology-generator/Species%20knowledge%20schema.md) - Full 120-field schema
- [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](./TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) - Long-term vision
- [treekipedia/API.md](./treekipedia/API.md) - Current API documentation
- [STATE.md](./STATE.md) - Deployment status

---

**Document Version**: 2.0
**Last Updated**: December 2025
**Authors**: Treekipedia Development Team
