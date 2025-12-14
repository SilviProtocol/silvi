# Treekipedia Species Fields - Frontend Implementation Guide

**Date**: November 18, 2025
**Database Version**: v10
**Total Species**: 67,927
**Total Fields**: 130

---

## Executive Summary

The Treekipedia species table now contains **130 fields** after the v10 migration, with significant new additions including:
- **Climate data** (Köppen-Geiger classification, precipitation, temperature)
- **GloBI ecological interactions** (pollinators, predators, parasites, seed dispersers)
- **SBTN land cover** classification
- **Soil characteristics** (texture, pH, organic content)

**Key Data Pattern**: Most text fields use semicolon (`;`) as a delimiter for multiple values. The string `"NA"` indicates missing/not available data (not SQL NULL).

---

## Table of Contents

1. [Taxonomy & Identity Fields](#taxonomy--identity-fields)
2. [Geographic & Distribution Fields](#geographic--distribution-fields)
3. [Ecological Context Fields](#ecological-context-fields)
4. [Climate & Environmental Fields (NEW v10)](#climate--environmental-fields-new-v10)
5. [Soil Characteristics Fields](#soil-characteristics-fields)
6. [Morphological Characteristics](#morphological-characteristics)
7. [Conservation & Status](#conservation--status)
8. [Economic & Cultural Value](#economic--cultural-value)
9. [Management & Stewardship](#management--stewardship)
10. [GloBI Ecological Interactions (NEW v10)](#globi-ecological-interactions-new-v10)
11. [Research & Metadata](#research--metadata)

---

## 1. Taxonomy & Identity Fields

### Core Identity
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `taxon_id` | TEXT | 100% | Primary key, unique species identifier | `"AngMaMyMyRt37741-00"` |
| `species_scientific_name` | VARCHAR(500) | 100% | Scientific name | `"Eucalyptus grandis"` |
| `taxon_full` | TEXT | 100% | Full taxon name including subspecies | `"Eucalyptus grandis NA"` |
| `genus` | VARCHAR(500) | ~100% | Genus name | `"Eucalyptus"` |
| `family` | VARCHAR(500) | ~100% | Family name | `"Myrtaceae"` |
| `specific_epithet` | VARCHAR(500) | ~100% | Species epithet | `"grandis"` |

### Taxonomic Classification
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `class` | VARCHAR(500) | ~100% | Taxonomic class | `"Magnoliopsida"` |
| `taxonomic_order` | VARCHAR(500) | ~100% | Taxonomic order | `"Myrtales"` |
| `subspecies` | TEXT | Varies | Subspecies designation | `"NA"` or subspecies name |
| `accepted_scientific_name` | TEXT | Varies | Accepted synonym | `"Eucalyptus grandis W.Hill"` |
| `synonyms` | TEXT | Low | Alternative scientific names | Semicolon-separated list or `"NA"` |

### Common Names
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `common_name` | TEXT | ~70% | Common names in various languages | `"Flooded Gum; Eucalipto; Rose Gum"` |
| `common_countries` | TEXT | Varies | Countries where common names apply | `"Australia; Brazil; United States"` |

**Display Recommendations**:
- Show `species_scientific_name` prominently with italics
- Parse `common_name` by semicolons, display as comma-separated list
- `taxon_id` should be visible but not prominent (for debugging/support)

---

## 2. Geographic & Distribution Fields

### Native Range
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `countries_native` | TEXT | 26% (17,415) | Native countries | `"Australia; France; Sri Lanka; Zimbabwe"` |
| `countries_introduced` | TEXT | Low | Introduced/naturalized countries | Semicolon-separated |
| `countries_invasive` | TEXT | Low | Countries where species is invasive | Semicolon-separated or `"NA"` |

### Ecological Regions
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `ecoregions` | TEXT | High | WWF ecoregion names | `"Eastern Australian temperate forests, Cerrado, Southeast US conifer savannas"` |
| `biomes` | TEXT | High | Biome classifications | `"Temperate Broadleaf & Mixed Forests, Tropical & Subtropical Moist Broadleaf Forests"` |
| `bioregions` | TEXT | Low | Bioregion codes | `"NE08;NO09;NO14;OC01"` |

### Occurrence Data
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `total_occurrences` | TEXT | Varies | Number of recorded occurrences | `"1293"` |
| `associated_media` | TEXT | Varies | URLs to observation/specimen records | Semicolon-separated URLs |

**Display Recommendations**:
- Create interactive map showing native range from `countries_native`
- Display `ecoregions` and `biomes` as filterable tags
- Link `associated_media` URLs as external references

---

## 3. Ecological Context Fields

### Habitat & Setting
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `habitat_human` | TEXT | Varies | Detailed habitat descriptions | Long text (can be 1000+ chars) |
| `habitat_ai` | TEXT | Very Low | AI-generated habitat summary | Usually `"NA"` |
| `forest_type` | TEXT | Low | Forest type classification | `"NA"` or specific type |
| `wetland_type` | TEXT | Low | Wetland classification | `"NA"` or wetland type |
| `urban_setting` | TEXT | Low | Urban tolerance/presence | `"NA"` or description |

### Functional Ecology
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `ecological_function_human` | TEXT | Low | Human-curated ecological role | Usually `"NA"` |
| `ecological_function_ai` | TEXT | Low | AI-generated ecological function | Usually `"NA"` |
| `functional_ecosystem_groups` | TEXT | Varies | Ecosystem functional groups | `"Tropical-subtropical lowland rainforests; Temperate broadleaf deciduous forests"` |
| `successional_stage` | VARCHAR(500) | Low | Successional classification | Usually `"NA"` |
| `forest_layers` | TEXT | Low | Forest layer occupation | Usually `"NA"` |

### Associated Species
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `associated_species` | TEXT | Low | Species commonly found together | Usually `"NA"` |

**Display Recommendations**:
- `habitat_human` is extremely detailed - consider collapsible section or "Read more"
- Most _ai fields are unpopulated - hide if `"NA"`
- Parse `functional_ecosystem_groups` by semicolons for tags

---

## 4. Climate & Environmental Fields (NEW v10)

### 🆕 Köppen-Geiger Climate Classification
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `climate_type_koppengeiger` | TEXT | **88% (60,111)** | Climate zones where species occurs | `"Cfa - Humid subtropical; Cfb - Oceanic; Aw - Tropical savanna"` |

**Format**: Semicolon-separated list of climate codes with descriptive names
- `Cfa` = Humid subtropical
- `Cfb` = Oceanic
- `Aw` = Tropical savanna
- `BSh` = Semi-arid steppe hot
- `Dfb` = Continental warm summer
- See [Köppen Climate Classification](https://en.wikipedia.org/wiki/K%C3%B6ppen_climate_classification)

### 🆕 Precipitation Metrics
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `annual_precipitation_mm` | TEXT | High | Annual rainfall in millimeters | `"984.2;1047"` (range or multiple values) |
| `wettest_month_precipitation_mm` | TEXT | High | Wettest month rainfall | `"129;135.8"` |
| `driest_month_precipitation_mm` | TEXT | High | Driest month rainfall | `"12.6;16"` |
| `precipitation_seasonality_cv` | TEXT | High | Coefficient of variation (seasonality) | `"14.85;16.19"` |
| `wettest_quarter_precipitation_mm` | TEXT | High | Wettest 3-month period | `"352.6;373"` |
| `driest_quarter_precipitation_mm` | TEXT | High | Driest 3-month period | `"68;79.4"` |

**Format**: Semicolon-separated numbers representing ranges or multiple measurement points

### 🆕 Temperature Metrics
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `annual_temperature_range_c` | TEXT | High | Annual temp range in Celsius | `"12.6;15.84"` |

### 🆕 Elevation
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `elevation_ranges_human` | TEXT | Low | Human-curated elevation data | Usually `"NA"` |
| `elevation_ranges_ai` | TEXT | Low | AI-generated elevation data | Usually `"NA"` |

**Display Recommendations**:
- Create a "Climate Profile" section with:
  - Visual Köppen climate zone map/badges
  - Precipitation chart (annual, wettest/driest month)
  - Temperature range visualization
- Parse semicolon-separated values as ranges or averages
- Consider using chart library (Chart.js, Recharts) for precipitation bars

**Example UI Component**:
```
Climate Profile
├─ Climate Zones: [Humid subtropical] [Oceanic] [Tropical savanna]
├─ Annual Rainfall: 984-1047mm
├─ Temperature Range: 12.6-15.8°C
└─ Seasonality: Moderate (CV: 14.9-16.2)
```

---

## 5. Soil Characteristics Fields

### Soil Texture
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `soil_texture_all` | TEXT | Varies | All observed soil textures | `"Clay;Clay Loam;Loam;Loamy Sand;Sand"` |
| `soil_texture_dominant` | TEXT | Low | Most common soil texture | Usually NULL or single value |
| `soil_texture_prefered` | TEXT | Low | Preferred soil texture | Usually NULL |
| `soil_texture_tolerated` | TEXT | Varies | Tolerated soil textures | `"Clay Loam;Loam;Sand"` |

### Soil pH
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `ph_all` | TEXT | Varies | All observed pH levels | `"moderately acidic;neutral;strongly acidic"` |
| `ph_dominant` | TEXT | Low | Most common pH | `"strongly acidic"` |
| `ph_prefered` | TEXT | Low | Preferred pH | Usually NULL |
| `ph_tolerated` | TEXT | Low | Tolerated pH | `"moderately acidic"` |

### Soil Organic Content (OC)
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `oc_all` | TEXT | Varies | All observed OC levels | `"high;low;medium"` |
| `oc_dominant` | TEXT | Low | Most common OC level | `"medium"` |
| `oc_prefered` | TEXT | Low | Preferred OC level | Usually NULL |
| `oc_tolerated` | TEXT | Low | Tolerated OC level | `"high"` |

### Compiled Soil Data
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `compatible_soil_types_human` | TEXT | Low | Human-curated soil compatibility | Usually `"NA"` |
| `compatible_soil_types_ai` | TEXT | Low | AI-generated soil compatibility | Usually `"NA"` |

**Display Recommendations**:
- Create "Soil Requirements" section
- Show `soil_texture_tolerated` as primary (most useful for growers)
- Display pH as text categories (strongly acidic, moderately acidic, neutral, etc.)
- Use color coding: Acidic (red), Neutral (green), Alkaline (blue)
- If dominant fields are populated, highlight them

---

## 6. Morphological Characteristics

All morphology fields follow `_ai` / `_human` suffix pattern. Human-curated fields are generally more reliable when populated.

### Growth Form
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `growth_form_human` | VARCHAR(500) | Very Low | Human-verified growth form | Usually `"NA"` |
| `growth_form_ai` | VARCHAR(500) | Very Low | AI-generated growth form | Usually `"NA"` |

### Foliage
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `leaf_type_human` | VARCHAR(500) | Very Low | Leaf type (human) | Usually `"NA"` |
| `leaf_type_ai` | VARCHAR(500) | Very Low | Leaf type (AI) | Usually `"NA"` |
| `deciduous_evergreen_human` | VARCHAR(500) | Very Low | Deciduous/Evergreen (human) | Usually `"NA"` |
| `deciduous_evergreen_ai` | VARCHAR(500) | Very Low | Deciduous/Evergreen (AI) | Usually `"NA"` |

### Reproductive Features
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `flower_color_human` | VARCHAR(500) | Very Low | Flower color (human) | Usually `"NA"` |
| `flower_color_ai` | VARCHAR(500) | Very Low | Flower color (AI) | Usually `"NA"` |
| `fruit_type_human` | VARCHAR(500) | Very Low | Fruit type (human) | Usually `"NA"` |
| `fruit_type_ai` | VARCHAR(500) | Very Low | Fruit type (AI) | Usually `"NA"` |

### Bark
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `bark_characteristics_human` | TEXT | Very Low | Bark description (human) | Usually `"NA"` |
| `bark_characteristics_ai` | TEXT | Very Low | Bark description (AI) | Usually `"NA"` |

### Size & Age
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `maximum_height_human` | TEXT | Very Low | Maximum height (human) | Usually `"NA"` |
| `maximum_height_ai` | TEXT | Very Low | Maximum height (AI) | Usually `"NA"` |
| `maximum_diameter_human` | TEXT | Very Low | Maximum diameter (human) | Usually `"NA"` |
| `maximum_diameter_ai` | TEXT | Very Low | Maximum diameter (AI) | Usually `"NA"` |
| `lifespan_human` | VARCHAR(500) | Very Low | Lifespan (human) | Usually `"NA"` |
| `lifespan_ai` | VARCHAR(500) | Very Low | Lifespan (AI) | Usually `"NA"` |
| `maximum_tree_age_human` | TEXT | Very Low | Max age (human) | Usually `"NA"` |
| `maximum_tree_age_ai` | TEXT | Very Low | Max age (AI) | Usually `"NA"` |

### Physical Characteristics
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `allometric_models` | TEXT | Very Low | Allometric model references | Usually `"NA"` |
| `allometric_curve` | TEXT | Very Low | Allometric curve data | Usually `"NA"` |

**Display Recommendations**:
- **Most morphology fields are unpopulated** - check for `"NA"` before displaying
- Prefer `_human` over `_ai` when both are available
- Consider placeholder text: "Morphological data not yet available"
- These fields may be populated in future data updates

---

## 7. Conservation & Status

### Conservation Status
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `conservation_status_human` | VARCHAR(500) | Low | Human-curated IUCN status | Usually `"NA"` |
| `conservation_status_ai` | VARCHAR(500) | Low | AI-generated conservation status | Usually `"NA"` |
| `national_conservation_status` | TEXT | Low | Country-specific status | Usually `"NA"` |

### Threats & Vulnerability
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `climate_change_vulnerability` | VARCHAR(500) | Low | Climate vulnerability assessment | Usually `"NA"` |
| `threats` | TEXT | Low | Documented threats | Usually `"NA"` |

### 🆕 SBTN Land Cover (v10)
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `sbtn_landcover` | TEXT | **85% (57,950)** | Science-Based Targets Network land cover types | `"Forest plantation;Grassland;Cropland;Plantations"` |

**SBTN Land Cover Categories**:
- Forest plantation
- Grassland
- Cropland
- Plantations
- Wetland
- Mangroves
- Urban
- Water bodies
- Permanent snow/ice
- Sparse vegetation
- Shrubland
- Other
- Bare areas

### Forest Presence
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `present_intact_forest` | TEXT | Low | Present in intact forests? | Usually `"NA"` |
| `vegetationtype` | TEXT | Low | Vegetation type classification | Usually `"NA"` |

**Display Recommendations**:
- SBTN land cover should be prominent - use badge/tag UI
- Parse by semicolons, display as filterable categories
- Conservation status should use standard IUCN color coding when available
- Consider icons for land cover types (forest, grassland, water, etc.)

---

## 8. Economic & Cultural Value

### Commercial Value
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `comercialspecies_lower` | TEXT | Varies | Commercial species designation | `"YES"` or `"NA"` |
| `comercialspecies_upper` | TEXT | Varies | (Legacy field) | Usually `"NA"` |
| `timber_value` | TEXT | Low | Timber use and value | Usually `"NA"` |

### Non-Timber Uses
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `non_timber_products` | TEXT | Low | Non-timber forest products | Usually `"NA"` |
| `nutritional_caloric_value` | TEXT | Low | Nutritional information | Usually `"NA"` |
| `cultivars` | TEXT | Low | Known cultivated varieties | Usually `"NA"` |

### Cultural Significance
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `cultural_significance_human` | TEXT | Low | Human-curated cultural info | Usually `"NA"` |
| `cultural_significance_ai` | TEXT | Low | AI-generated cultural info | Usually `"NA"` |

### Agriculture
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `agroforestry_use_cases_human` | TEXT | Low | Human-curated agroforestry uses | Usually `"NA"` |
| `agroforestry_use_cases_ai` | TEXT | Low | AI-generated agroforestry uses | Usually `"NA"` |
| `cultivation_details` | TEXT | Low | Cultivation information | Usually `"NA"` |

**Display Recommendations**:
- Show commercial status prominently if `"YES"`
- Economic/cultural fields mostly unpopulated - hide sections if all `"NA"`
- Consider "Uses & Value" collapsible section

---

## 9. Management & Stewardship

All management fields follow `_ai` / `_human` suffix pattern and are largely unpopulated.

### Best Practices
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `stewardship_best_practices_human` | TEXT | Very Low | Human-curated best practices | Usually `"NA"` |
| `stewardship_best_practices_ai` | TEXT | Very Low | AI-generated best practices | Usually `"NA"` |

### Planting & Establishment
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `planting_recipes_human` | TEXT | Very Low | Planting guidelines (human) | Usually `"NA"` |
| `planting_recipes_ai` | TEXT | Very Low | Planting guidelines (AI) | Usually `"NA"` |
| `native_adapted_habitats_human` | TEXT | Low | Native habitat info (human) | Usually `"NA"` |
| `native_adapted_habitats_ai` | TEXT | Low | Native habitat info (AI) | Usually `"NA"` |

### Maintenance
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `pruning_maintenance_human` | TEXT | Very Low | Pruning guidelines (human) | Usually `"NA"` |
| `pruning_maintenance_ai` | TEXT | Very Low | Pruning guidelines (AI) | Usually `"NA"` |

### Pest & Disease Management
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `disease_pest_management_human` | TEXT | Very Low | Pest/disease info (human) | Usually `"NA"` |
| `disease_pest_management_ai` | TEXT | Very Low | Pest/disease info (AI) | Usually `"NA"` |

### Fire Management
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `fire_management_human` | TEXT | Very Low | Fire response info (human) | Usually `"NA"` |
| `fire_management_ai` | TEXT | Very Low | Fire response info (AI) | Usually `"NA"` |

### Environmental Tolerances
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `tolerances` | TEXT | Low | Environmental tolerances | Usually `"NA"` |

**Display Recommendations**:
- These fields are almost entirely unpopulated
- Consider hiding entire "Management & Stewardship" section if all fields are `"NA"`
- Future opportunity for community contributions

---

## 10. GloBI Ecological Interactions (NEW v10)

**GloBI** = [Global Biotic Interactions Database](https://www.globalbioticinteractions.org/)

### 🆕 Interaction Fields
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `globi_pollinatedby` | TEXT | **100%** | Species that pollinate this tree | Usually `"NA"`, some populated |
| `globi_eatenby` | TEXT | **24% (16,063)** | Species that consume this tree | `"Pseudotargionia comata;Euselasia hygenius"` |
| `globi_flowersvisitedby` | TEXT | **100%** | Species visiting flowers | Usually `"NA"` |
| `globi_hasparasite` | TEXT | **100%** | Parasites of this species | Species names semicolon-separated |
| `globi_haspathogen` | TEXT | **100%** | Pathogens affecting species | `"Botryosphaeria dothidea;Teratosphaeria"` |
| `globi_hasdispersalvector` | TEXT | **100%** | Seed dispersal agents | Usually `"NA"` |
| `globi_preyeduponby` | TEXT | **100%** | Predators | Usually `"NA"` |
| `globi_hasparasitoid` | TEXT | **100%** | Parasitoids | Usually `"NA"` |

**Data Pattern**:
- All fields are present (100% populated in schema)
- Most contain `"NA"` indicating no known interactions
- When populated, contains semicolon-separated scientific names
- `globi_eatenby` has highest actual population rate (24%)

**Example (Eucalyptus grandis)**:
```
globi_eatenby: "Pseudotargionia comata;Euselasia hygenius;Cardiaspina maniformis;
                Mnesampela privata;Strepsicrates ejectana;Thyrinteina arnobia"

globi_hasparasite: "Discocriconemella limitanea;Selitrichodes neseri;Leptocybe invasa"

globi_haspathogen: "Botryosphaeria dothidea;Teratosphaeria zuluensis;
                    Chrysoporthe austroafricana"
```

**Display Recommendations**:
- Create dedicated "Ecological Interactions" section
- Only show categories with actual data (not `"NA"`)
- Parse semicolon-separated species names
- Consider linking species names to external databases (GloBI, iNaturalist, GBIF)
- Use icons for interaction types:
  - 🐝 Pollinators
  - 🐛 Herbivores (eaten by)
  - 🦋 Flower visitors
  - 🦠 Pathogens
  - 🐜 Parasites
  - 🐦 Seed dispersers
  - 🦅 Predators

**Example UI Component**:
```
Ecological Interactions (from GloBI)
├─ 🐛 Eaten by (12 species)
│   ├─ Pseudotargionia comata
│   ├─ Euselasia hygenius
│   └─ + 10 more...
├─ 🐜 Parasites (11 species)
│   ├─ Leptocybe invasa
│   └─ + 10 more...
└─ 🦠 Pathogens (8 species)
    ├─ Botryosphaeria dothidea
    └─ + 7 more...
```

---

## 11. Research & Metadata

### Research Status
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `researched` | TEXT | Most are `"NA"` | Has AI research been generated? | `"NA"` or `"true"` |
| `ipfs_cid` | VARCHAR(500) | Very Low | IPFS content ID for research | CID string or `"NA"` |
| `verification_status` | VARCHAR(500) | Very Low | Data verification status | Usually `"NA"` |

### References & Sources
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `reference_list` | TEXT | Low | Scientific references | Usually `"NA"` |
| `data_sources` | TEXT | Low | Data source citations | Usually `"NA"` |

### General Description
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `general_description_human` | TEXT | Very Low | Human-written species description | Usually `"NA"` |
| `general_description_ai` | TEXT | Very Low | AI-generated description | Usually `"NA"` |

### System Fields
| Field | Type | Populated | Description | Example |
|-------|------|-----------|-------------|---------|
| `taxon_id_new` | TEXT | 100% | (Mapping field from v10 import) | Same as `taxon_id` |
| `last_updated_date` | TEXT | Low | Last update timestamp | Usually `"NA"` |
| `created_at` | TIMESTAMP | 100% | Row creation timestamp | `2025-11-16 14:33:40` |
| `updated_at` | TIMESTAMP | 100% | Row update timestamp | `2025-11-18 16:09:03` |

**Display Recommendations**:
- Most research fields are `"NA"` - hide if not populated
- `created_at` / `updated_at` can be shown in footer or metadata section
- Link IPFS CIDs when present

---

## Data Handling Guidelines

### 1. Handling "NA" Values

**Important**: The string `"NA"` (not SQL NULL) indicates missing data across most fields.

```typescript
// TypeScript example
function isDataAvailable(value: string | null): boolean {
  return value !== null && value !== "NA" && value.trim() !== "";
}

// Usage
if (isDataAvailable(species.climate_type_koppengeiger)) {
  // Display climate data
}
```

### 2. Parsing Semicolon-Separated Values

Many fields use semicolons as delimiters:

```typescript
function parseMultiValue(value: string): string[] {
  if (!isDataAvailable(value)) return [];
  return value.split(';').map(v => v.trim()).filter(v => v !== "");
}

// Example
const climates = parseMultiValue(species.climate_type_koppengeiger);
// ["Cfa - Humid subtropical", "Cfb - Oceanic", "Aw - Tropical savanna"]
```

### 3. Numeric Ranges

Climate and soil fields often contain ranges:

```typescript
function parseNumericRange(value: string): { min: number, max: number } | null {
  if (!isDataAvailable(value)) return null;
  const parts = value.split(';').map(p => parseFloat(p)).filter(n => !isNaN(n));
  if (parts.length === 0) return null;
  return {
    min: Math.min(...parts),
    max: Math.max(...parts)
  };
}

// Example
const precip = parseNumericRange(species.annual_precipitation_mm);
// { min: 984.2, max: 1047 }
```

### 4. Handling Subspecies

Species can have multiple subspecies rows (same species_scientific_name, different subspecies values).

**Decision Required**:
- Should subspecies data be aggregated?
- Display separately on species detail pages?
- Filter to show only species-level records?

---

## Population Statistics Summary

| Category | Fields | Population Rate | Notes |
|----------|--------|----------------|-------|
| **Taxonomy** | 11 | ~100% | Core identity fields |
| **Climate (v10)** | 8 | **60-88%** | Well-populated, new in v10 |
| **SBTN Land Cover (v10)** | 1 | **85%** | Excellent coverage |
| **GloBI Interactions (v10)** | 8 | 0-24% actual | Present but mostly "NA" |
| **Soil Characteristics** | 12 | 5-40% | Varies by field |
| **Geographic** | 6 | 25-100% | ecoregions/biomes high, countries low |
| **Morphology** | 18 | <5% | Largely unpopulated |
| **Management** | 12 | <5% | Largely unpopulated |
| **Economic/Cultural** | 8 | <10% | Low population |
| **Research** | 6 | <10% | Low population |

---

## Recommended UI Sections for Species Detail Page

### Priority 1: Always Display
1. **Header**: Scientific name, common names, family, genus
2. **Images**: From separate images table
3. **Overview**:
   - Geographic distribution (countries_native)
   - Occurrence count
   - Commercial status
4. **🆕 Climate Profile**: Köppen zones, precipitation, temperature
5. **🆕 Land Cover**: SBTN categories
6. **Taxonomy**: Full classification with subspecies

### Priority 2: Display if Available
7. **Habitat**: Detailed habitat_human descriptions
8. **🆕 Ecological Interactions**: GloBI data (if not all "NA")
9. **Ecoregions & Biomes**: As filterable tags
10. **Soil Requirements**: Texture, pH, organic content
11. **Conservation Status**: If populated

### Priority 3: Future / Low Priority
12. **Morphology**: Show if any fields populated
13. **Management & Stewardship**: Show if populated
14. **Economic & Cultural Value**: Show if populated

### Hidden Unless Populated
- All _ai fields (prefer _human)
- All fields with "NA" values
- Management/stewardship fields (mostly empty)

---

## TypeScript Interface Template

```typescript
interface Species {
  // Core Identity
  taxon_id: string;
  species_scientific_name: string;
  taxon_full: string;
  genus: string | null;
  family: string | null;
  specific_epithet: string | null;
  common_name: string | null;

  // NEW v10: Climate
  climate_type_koppengeiger: string | null;
  annual_temperature_range_c: string | null;
  annual_precipitation_mm: string | null;
  wettest_month_precipitation_mm: string | null;
  driest_month_precipitation_mm: string | null;
  precipitation_seasonality_cv: string | null;
  wettest_quarter_precipitation_mm: string | null;
  driest_quarter_precipitation_mm: string | null;

  // NEW v10: SBTN
  sbtn_landcover: string | null;

  // NEW v10: GloBI Interactions
  globi_pollinatedby: string | null;
  globi_eatenby: string | null;
  globi_flowersvisitedby: string | null;
  globi_hasparasite: string | null;
  globi_haspathogen: string | null;
  globi_hasdispersalvector: string | null;
  globi_preyeduponby: string | null;
  globi_hasparasitoid: string | null;

  // Geographic
  countries_native: string | null;
  countries_introduced: string | null;
  countries_invasive: string | null;
  ecoregions: string | null;
  biomes: string | null;

  // Soil
  soil_texture_all: string | null;
  soil_texture_tolerated: string | null;
  ph_all: string | null;
  ph_dominant: string | null;

  // Habitat
  habitat_human: string | null;
  total_occurrences: string | null;

  // Timestamps
  created_at: string;
  updated_at: string;

  // ... (add other fields as needed)
}
```

---

## API Response Example

```json
{
  "taxon_id": "AngMaMyMyRt37741-00",
  "species_scientific_name": "Eucalyptus grandis",
  "common_name": "Flooded Gum; Eucalipto; Rose Gum",
  "family": "Myrtaceae",
  "genus": "Eucalyptus",

  "climate_type_koppengeiger": "Cfa - Humid subtropical; Cfb - Oceanic; Aw - Tropical savanna",
  "annual_precipitation_mm": "984.2;1047",
  "annual_temperature_range_c": "12.6;15.84",

  "sbtn_landcover": "Forest plantation;Grassland;Cropland;Plantations",

  "globi_eatenby": "Pseudotargionia comata;Euselasia hygenius;Cardiaspina maniformis",
  "globi_hasparasite": "Leptocybe invasa;Discocriconemella limitanea",
  "globi_haspathogen": "Botryosphaeria dothidea;Teratosphaeria zuluensis",

  "countries_native": "Australia;France;Sri Lanka;Zimbabwe",
  "ecoregions": "Eastern Australian temperate forests, Cerrado",
  "biomes": "Temperate Broadleaf & Mixed Forests",

  "total_occurrences": "1293"
}
```

---

## Migration Notes for Frontend Team

### What Changed in v10

1. **17 New Fields Added**:
   - 8 climate fields (well-populated)
   - 8 GloBI interaction fields (present but mostly "NA")
   - 1 SBTN land cover field (well-populated)

2. **Database Structure**:
   - Total fields increased from 113 → 130
   - All existing fields preserved
   - No breaking changes to field names

3. **Population Rates**:
   - Climate data: 60-88% populated
   - SBTN land cover: 85% populated
   - GloBI interactions: Present but mostly "NA" (24% for eaten_by)

### Frontend Action Items

1. **Update TypeScript interfaces** to include new v10 fields
2. **Add Climate Profile section** to species detail pages
3. **Add Ecological Interactions section** (GloBI data)
4. **Add SBTN Land Cover badges/tags**
5. **Update API calls** to fetch new fields
6. **Consider chart/visualization libraries** for climate data
7. **Test with subspecies** (multiple rows per species_scientific_name)

### Testing Recommendations

**Well-Populated Test Species**:
- `Eucalyptus grandis` - Has climate, SBTN, GloBI interactions
- `Quercus robur` - Multiple subspecies, various climate zones
- `Pinus ponderosa` - North American distribution

**Edge Cases to Test**:
- Species with all fields as "NA"
- Species with very long `habitat_human` text
- Species with 10+ GloBI interactions
- Subspecies handling (multiple rows)

---

## Questions for Design/Frontend Team

1. **Subspecies Display**: How should we handle multiple subspecies of the same species?
   - Aggregate data across subspecies?
   - Separate tabs/sections?
   - Show only species-level records?

2. **Climate Visualization**: What chart library should we use?
   - Chart.js, Recharts, Victory, D3?
   - Static or interactive?

3. **GloBI Interactions**: Should species names link externally?
   - Link to GloBI website?
   - Link to iNaturalist/GBIF?
   - Internal links (if species exists in our DB)?

4. **"NA" Handling**: How to display sections with no data?
   - Hide entirely?
   - Show placeholder: "Data not available"?
   - Show "Contribute data" link?

5. **Mobile Optimization**: Priority for responsive design?
   - Which sections are mobile-critical?
   - Collapsible sections on mobile?

---

## Support & Resources

**Database Connection**: Use existing species API endpoints
**Field Validation**: See `database/current-schema.sql` for schema definitions
**Sample Queries**: Available in `API.md`
**Migration Documentation**: See `database/v10_migration_analysis.md`

**External Resources**:
- [Köppen Climate Classification](https://en.wikipedia.org/wiki/K%C3%B6ppen_climate_classification)
- [GloBI Database](https://www.globalbioticinteractions.org/)
- [SBTN Technical Guidance](https://sciencebasedtargetsnetwork.org/)
- [GBIF](https://www.gbif.org/)
- [iNaturalist](https://www.inaturalist.org/)

---

**Document Version**: 1.0
**Last Updated**: November 18, 2025
**Contact**: Backend team for API questions, database queries
