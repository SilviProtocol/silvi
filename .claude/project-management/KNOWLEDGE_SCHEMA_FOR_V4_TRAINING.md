# Knowledge Schema for SINR v4 Training
## Text Embeddings + Structured Knowledge for LE-SINR Approach

**Date**: March 7, 2026
**Status**: Architecture specification for v4 training phase
**Scope**: Schema design, data coverage audit, AI researcher queue plan
**Related Docs**:
- [MASTER_PREDICTION_ARCHITECTURE_3.md](./MASTER_PREDICTION_ARCHITECTURE_3.md) - v3 k-NN foundation
- [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](../../TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) - Insight model
- [TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md](../../TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md) - Multi-model extraction

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Knowledge Categories for SDM Text Embeddings](#knowledge-categories-for-sdm-text-embeddings)
3. [Text Template for Sentence Transformer](#text-template-for-sentence-transformer)
4. [Schema Gap Analysis: Missing SDM Knowledge](#schema-gap-analysis-missing-sdm-knowledge)
5. [Data Coverage Audit](#data-coverage-audit)
6. [AI Researcher Queue Plan](#ai-researcher-queue-plan)
7. [Integration with SINR v4 Training](#integration-with-sinr-v4-training)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

SINR v4 will enhance the v3 k-NN architecture (which matches query locations against 3M+ satellite-embedded occurrence points) with a **species-level text embedding branch**. Following the LE-SINR approach (Hamilton et al., NeurIPS 2024), we will:

1. **Encode species ecological knowledge** into structured text descriptions
2. **Generate 384D embeddings** via sentence transformer (e.g., all-MiniLM-L6-v2)
3. **Inject as a parallel branch** alongside satellite, temporal, environment, and land-state branches
4. **Enable zero-shot prediction** for the 19,614 species without occurrence data

**Key Insight**: Text embeddings don't replace k-NN on location data—they *complement* it by providing species-level context (niche description, trait profile, biogeographic history) that helps the model generalize to unseen species and locations.

**Current Blockers**:
- 48,129 species have rich occurrence data + environmental covariates
- 19,614 species lack occurrence data entirely → cannot train k-NN
- Text embeddings solve this: describe the 19,614 in text, encode them, predict habitat
- Current schema is 75% complete for text encoding; 8 critical functional traits are missing

**Timeline**: Phase 1 (immediate) fills lowest-hanging gaps; Phase 3 (2-3 months) reaches "knowledge saturation" for most species.

---

## Knowledge Categories for SDM Text Embeddings

We categorize the 121 existing schema fields + 8 new ones into tiers based on SDM relevance.

### Tier 1: Critical for SDM (These MUST be in the text embedding)

These directly encode species-environment relationships and niche definition.

| Field | Why SDM-Critical | Current Coverage | Data Type | Include in Text |
|-------|------------------|-------------------|-----------|-----------------|
| **habitat** | Describes ecosystem types species occurs in; core niche definition | 77% researched | Text prose | ✅ YES — primary |
| **elevation_ranges** | Constrains altitude tolerance; strong geographical signal | 77% researched | Text prose (min-max) | ✅ YES — primary |
| **climate_type_koppengeiger** | Köppen classification defines macroclimate niche (tropical/temperate/arid) | 88.5% species | Categorical (e.g., "Cfa; Cwa") | ✅ YES — encode code meanings |
| **annual_precipitation_mm** | Precipitation tolerance; critical for drought/wet niche definition | 88.6% species | Numeric percentile (p25;p75) | ✅ YES — as range text |
| **annual_temperature_range_c** | Temperature tolerance bounds; defines thermal niche | 88.6% species | Numeric percentile (p25;p75) | ✅ YES — as range text |
| **soil_type_dominant** | Edaphic preferences; affects nutrient/water availability niche | 66.2% species | Categorical (e.g., "Clay Loam") | ✅ YES — encode category names |
| **soil_ph_dominant** | pH tolerance; defines edaphic niche (acidic vs alkaline) | 81.9% species | Categorical (e.g., "moderately acidic") | ✅ YES — explicit text |
| **functional_ecosystem_groups** | EFG classification; species associates with specific biome/forest types | 71% species | Categorical (EFG names) | ✅ YES — expand with codes |
| **growth_form** | Tree shape/size class; affects microhabitat preference (understory/canopy) | 77% researched | Categorical (e.g., "tree; shrub; herb") | ✅ YES — affects light niche |
| **maximum_height_m** | Canopy position proxy; tall trees prefer high light, deep-rooted | 77% researched | Numeric (max m) | ✅ YES — as category ("large", "medium", "small") |
| **deciduous_evergreen** | Phenology; affects precipitation/light niche (wet vs dry; open vs closed) | 77% researched | Categorical | ✅ YES — describes seasonality |
| **lifespan_years** | Longevity; affects disturbance tolerance and successional stage | 77% researched | Numeric or text | ✅ YES — early/mid/late succession proxy |
| **leaf_type** | Leaf morphology; proxy for drought/frost tolerance (needle vs broad) | 77% researched | Categorical | ✅ YES — trait-based strategy |
| **specific_leaf_area_cm2_g** | **[NEW]** Photosynthetic strategy; high SLA = fast-growing (shade, wet), low SLA = slow (drought, light) | ~5% species | Numeric (cm²/g) | ✅ YES — critical trait |
| **wood_density_g_cm3** | **[NEW]** Growth/stress strategy; high density = slow growth, drought/wind tolerant | ~10% species | Numeric (g/cm³) | ✅ YES — critical trait |
| **root_depth_m** | **[NEW]** Soil moisture niche; deep roots access drought-resilient water, affect erosion/stability | ~5% species | Numeric (max m) | ✅ YES — hydrological niche |
| **mycorrhizal_type** | **[NEW]** Symbiotic strategy; AM (generalist, wet) vs ECM (temperate/boreal, nutrient-poor) | ~3% species | Categorical (AM/ECM/both) | ✅ YES — soil nutrition strategy |

**Subtotal Tier 1**: 17 fields

---

### Tier 2: Valuable for SDM (Should be in text if available; enhances but not mandatory)

These provide ecological context and interaction information that improves generalization.

| Field | Why Valuable for SDM | Current Coverage | Include in Text |
|-------|----------------------|-------------------|-----------------|
| **associated_species** | Co-occurrence data; species-species niche overlap | 20-30% quality | ✅ YES — but with caveats |
| **ecological_function** | Functional role; nitrogen-fixing trees modify soil N availability | 77% researched | ✅ YES — trait-based strategy |
| **native_adapted_habitats** | Text description of original habitat; encodes biogeographic origin | 77% researched | ✅ YES — primary niche origin |
| **countries_native** | Biogeographic range; coarse spatial signal | 88% species | ✅ YES — encode as region names |
| **wcvp_native** | WCVP native range classification (continent/region codes) | ~60% species | ✅ YES — standardized format |
| **conservation_status** | Threat status; population viability signal | ~70% species | ✅ YES — rarity affects occurrences |
| **drought_tolerance** | **[NEW]** Quantified water stress tolerance | ~5% species | ✅ YES — water niche |
| **frost_tolerance_c** | **[NEW]** Quantified cold tolerance (min winter temp) | ~5% species | ✅ YES — temperature niche |
| **fire_tolerance** | **[NEW]** Fire adaptation/recovery (obligate, facultative, sensitive) | ~5% species | ✅ YES — disturbance niche |
| **seed_dispersal_mechanism** | **[NEW]** How seeds spread (wind, animal, water, gravity); affects colonization range | ~10% species | ✅ YES — expansion potential |
| **seed_mass_mg** | **[NEW]** Seed size affects dispersal distance and establishment | ~8% species | ✅ YES — recruitment strategy |
| **flowering_fruiting_season** | **[NEW]** Phenological timing; biotic interaction and resource availability windows | ~10% species | ✅ YES — temporal niche |
| **light_requirement** | **[NEW]** Shade tolerance (pioneer/mid-story/shade-tolerant) | ~8% species | ✅ YES — canopy position niche |
| **nitrogen_fixation** | Symbiotic N₂ fixation capability (0 or 1, or quantified rate) | ~5% species | ✅ YES — soil modification |

**Subtotal Tier 2**: 14 fields

---

### Tier 3: Useful But Not SDM-Critical (Include if easy; skip if research effort is high)

These are valuable for the platform but don't directly constrain habitat or niche.

| Field | Use Case | Include in Text |
|-------|----------|-----------------|
| **cultivation_details** | Agroforestry/restoration context | Optional (for recommendation context) |
| **timber_value** | Economic signal | Optional (indirect niche: managed stands) |
| **non_timber_products** | Livelihood context | Optional |
| **cultural_significance** | Human valuation | Optional |
| **stewardship_best_practices** | Practical restoration | Optional (not SDM-critical) |
| **disease_pest_management** | Disturbance response | Optional (specialized) |
| **allometric_models** | Biomass prediction | Not for text embedding |
| **images** | Visual context | Not for text (but valuable for UI) |

**Subtotal Tier 3**: 8 fields

---

## Text Template for Sentence Transformer

We generate a **structured prose description** per species, concatenate key fields, and encode via sentence transformer (e.g., `all-MiniLM-L6-v2` for 384D embeddings).

### Design Principles

1. **Field-to-Prose Conversion**: Convert numeric/categorical data into natural language phrases
2. **Hierarchy**: Lead with direct niche definition (habitat, climate, elevation), then traits, then context
3. **Standardization**: Use consistent phrasing to help transformer learn patterns
4. **Incomplete Fields**: Gracefully skip missing data (don't force placeholders)
5. **Confidence Tagging**: Optionally append confidence (AI vs human source) for future fine-tuning

### Template Structure

```
[SPECIES IDENTITY]
Scientific name: {species_scientific_name}
Common names: {common_name}

[CORE NICHE DEFINITION]
Habitat: {habitat_text}
Native to: {countries_native_formatted} / {native_bioregion_names}
Elevation range: {elevation_ranges_formatted}
Climate type: {koppengeiger_descriptions}
Precipitation: {annual_precipitation_mm_formatted} mm annually
Temperature: {annual_temperature_range_c_formatted} degrees C annual range

[SOIL & EDAPHIC NICHE]
Soil type: {soil_type_dominant_descriptive}
Soil pH: {soil_ph_dominant_descriptive}
Ecosystem classification: {functional_ecosystem_groups_names}

[MORPHOLOGICAL & PHYSIOLOGICAL TRAITS]
Growth form: {growth_form}
Maximum height: {maximum_height_formatted}
Leaf type: {leaf_type}
Deciduous or evergreen: {deciduous_evergreen}
Lifespan: {lifespan_category}
Specific leaf area (SLA): {specific_leaf_area_formatted}
Wood density: {wood_density_formatted}

[HYDROLOGICAL & BELOWGROUND TRAITS]
Maximum rooting depth: {root_depth_formatted}
Soil moisture niche: {moisture_tolerance_synthesized}
Drought tolerance: {drought_tolerance_category}

[BIOGEOCHEMICAL & SYMBIOTIC TRAITS]
Mycorrhizal association: {mycorrhizal_type}
Nitrogen fixation: {nitrogen_fixation_capability}
Ecological function: {ecological_function_synthesized}

[REPRODUCTIVE & DISPERSAL TRAITS]
Seed dispersal mechanism: {seed_dispersal_mechanism}
Seed mass: {seed_mass_formatted}
Flowering and fruiting season: {phenological_timing}

[DISTURBANCE & CLIMATE RESPONSE]
Fire tolerance: {fire_tolerance_category}
Frost tolerance: {frost_tolerance_formatted}
Climate change vulnerability: {vulnerability_text}

[ASSOCIATED ECOLOGY]
Light requirement: {light_requirement_category}
Associated species: {associated_species_list}
Conservation status: {conservation_status}
```

### Concrete Example: *Pinus radiata* (Monterey Pine)

**Input Data**:
```python
{
  'species_scientific_name': 'Pinus radiata',
  'common_name': 'Monterey Pine; Radiata Pine',
  'habitat_human': 'Coastal mixed conifer forests; planted in temperate and Mediterranean regions',
  'countries_native': 'Mexico (Baja California)',
  'countries_cultivated': 'Chile; New Zealand; Australia; South Africa; Spain; Portugal',
  'elevation_ranges_human': '200-300m (native range)',
  'climate_type_koppengeiger': 'Csb; Csa',  # Mediterranean
  'annual_precipitation_mm': '508;660',
  'annual_temperature_range_c': '10.2;15.8',
  'soil_type_dominant': 'Sandy Loam; Sandy Clay Loam',
  'soil_ph_dominant': 'neutral to slightly acidic',
  'growth_form_human': 'tree',
  'maximum_height_human': '40-60',
  'leaf_type_human': 'needle',
  'deciduous_evergreen_human': 'evergreen',
  'lifespan_human': '80-100',
  'specific_leaf_area': 7.5,  # [NEW] low SLA = slow grower
  'wood_density': 0.55,  # [NEW] moderately dense
  'root_depth': 2.5,  # [NEW] moderate depth
  'mycorrhizal_type': 'ectomycorrhizal',  # [NEW]
  'seed_mass': 15,  # [NEW] mg, windborne
  'seed_dispersal': 'wind',  # [NEW]
  'phenological_timing': 'Cones mature September-November (native); wind dispersal',  # [NEW]
  'light_requirement': 'light-demanding',  # [NEW]
  'drought_tolerance': 'moderate; established trees tolerate 4-5 month dry season',  # [NEW]
  'fire_tolerance': 'sensitive to stand-replacing fire; regeneration after fire possible',  # [NEW]
  'frost_tolerance': '-8 to -10C minimum (frost-tender below -15C)',  # [NEW]
  'ecological_function_ai': 'Not nitrogen-fixing; pioneer/early successional in native range; plantation timber production',
  'conservation_status_human': 'Not Threatened (native population small but stable in Mexico)',
  'associated_species': 'Cupressus macrocarpa; Torrey pine (Pinus torreyana)',
  'climate_change_vulnerability': 'Increased fire risk in Mediterranean regions; drought stress in lower precipitation areas'
}
```

**Generated Text**:
```
Scientific name: Pinus radiata
Common names: Monterey Pine; Radiata Pine

Habitat: Coastal mixed conifer forests; widely planted in temperate and Mediterranean regions for timber production
Native to: Mexico (Baja California) / Coastal Pacific region
Elevation range: 200-300m in native range
Climate type: Mediterranean (Csb, Csa) with cool wet winters and warm dry summers
Precipitation: 508-660 mm annually
Temperature: 10.2-15.8 degrees C annual range

Soil type: Sandy loam to sandy clay loam soils; tolerates poor, droughty soils
Soil pH: Neutral to slightly acidic (pH 6.5-7.5)
Ecosystem classification: Temperate/Mediterranean coastal forests and cultivated plantations

Growth form: Tree
Maximum height: 40-60 meters
Leaf type: Needle
Deciduous or evergreen: Evergreen
Lifespan: 80-100 years
Specific leaf area: 7.5 cm²/g (low; slow-growing strategy)
Wood density: 0.55 g/cm³ (moderately dense; strong, durable timber)

Maximum rooting depth: 2.5 meters
Soil moisture niche: Tolerates 4-5 month dry season once established; drought-tolerant
Drought tolerance: Moderate to high; established trees withstand extended dry periods

Mycorrhizal association: Ectomycorrhizal with native fungal partners
Nitrogen fixation: Not nitrogen-fixing
Ecological function: Pioneer and early-successional species in native range; primary use is industrial timber plantation production worldwide

Seed dispersal mechanism: Wind (anemochory); seeds dispersed 100-200m under favorable conditions
Seed mass: 15 mg per seed
Flowering and fruiting season: Cones mature September-November in native range; seeds released and dispersed by wind

Fire tolerance: Sensitive to stand-replacing wildfire; limited sprouting recovery; regeneration possible from wind-dispersed seed after fire
Frost tolerance: Frost-hardy to -8 to -10C minimum; frost-tender below -15C (limited in severe continental climates)
Climate change vulnerability: Increased wildfire risk in Mediterranean regions; drought-induced mortality in lower precipitation areas; poleward range expansion potential

Light requirement: Light-demanding pioneer species; intolerant of shade
Associated species: Cupressus macrocarpa (Monterey cypress); Torrey pine (Pinus torreyana) in native range
Conservation status: Not threatened (native population small but stable in Baja California; globally dominant in plantations)
```

**Embedding Process**:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # 384D
text = "[generated text above]"
embedding = model.encode(text)  # shape (384,)

# Store in database:
# INSERT INTO species_text_embeddings (taxon_id, text_content, embedding)
# VALUES ('pinus_radiata', $1, $2)
```

**Why This Works for SDM**:
- Sentence transformer learns that "Monterey pine grows in Mediterranean climate with 500-600mm precip" clusters with other temperate Mediterranean species
- The text encodes the entire niche envelope: precipitation, temperature, soil, phenology, disturbance response
- Zero-shot: a species with no occurrences but rich text gets an embedding in the same space as species with 10,000 occurrence points
- The embedding captures functional ecology, allowing generalization to unseen communities

---

## Schema Gap Analysis: Missing SDM Knowledge

The current schema covers 75% of SDM-critical information. **8 new fields** are essential for complete niche representation and should be prioritized in the AI researcher queue.

### Critical Gaps (Tier 1 Impact)

#### 1. Specific Leaf Area (SLA)
**Why it matters**: SLA (leaf area per unit dry mass, cm²/g) is THE key functional trait on the "leaf economics spectrum." It defines photosynthetic strategy:
- **High SLA** (>150 cm²/g): Large, thin leaves → fast photosynthesis, shade-tolerant, wet/warm preference
- **Low SLA** (<50 cm²/g): Small, thick leaves → drought/frost-tolerant, sun-loving, nutrient-conservative

**Current state**: Not in schema; ~5% of species have estimates
**SDM relevance**: Predicts understory (high SLA) vs canopy (low SLA) niche; drought-sensitive vs -tolerant
**Data source**: TRY database (1M+ trait records), BIEN database (915k observations), literature
**Extraction difficulty**: Medium (literature often reports "leaf mass per area" which is inverse: mg/cm²)

#### 2. Wood Density
**Why it matters**: Wood density (g/cm³) reflects stress-tolerance vs fast-growth strategy:
- **High density** (>0.7 g/cm³): Slow-growing, stress-tolerant (drought, wind), long-lived, dense wood
- **Low density** (<0.4 g/cm³): Fast-growing, competitive species, short-lived, softwood

**Current state**: Not in schema; ~10% of species have estimates
**SDM relevance**: Predicts disturbance recovery (fast vs slow), drought tolerance, successional stage
**Data source**: FIA (US), FD (Europe), DRYAD, GRooT database, literature
**Extraction difficulty**: Medium-high (wood density varies by environment, age, genetics)

#### 3. Maximum Rooting Depth
**Why it matters**: Root depth constrains soil moisture niche:
- **Shallow roots** (<1m): Limited drought tolerance; wet habitats preferred
- **Deep roots** (>4m): Access groundwater; drought-tolerant; affect soil stability/erosion

**Current state**: Not in schema; ~5% of species have estimates
**SDM relevance**: Predicts water availability tolerance; gully/slope stability (restoration context)
**Data source**: GRooT (Global Root Traits) database has 38 root traits for 6,214 species; literature
**Extraction difficulty**: Medium (roots hard to measure; often literature estimates)

#### 4. Mycorrhizal Type (AM vs ECM)
**Why it matters**: Symbiotic partnership defines soil nutrient strategy:
- **Arbuscular Mycorrhizal (AM)**: Generalist fungi; access labile nutrients; preference for moist, fertile soils
- **Ectomycorrhizal (ECM)**: Forest fungi; access organic matter in coarse humus; nutrient-poor, well-drained soils; boreal/temperate forests
- **Dual**: Some species partner with both

**Current state**: Not in schema; ~3% of species documented
**SDM relevance**: Predicts soil nutrient niche (fertile vs nutrient-poor); boreal/temperate vs tropical preference
**Data source**: Publicly available databases, literature (FunDiS, MycoFlora), taxonomic patterns (conifers ~95% ECM)
**Extraction difficulty**: Medium (strong phylogenetic signal; can infer from taxonomy)

#### 5. Root System Type
**Why it matters**: Root architecture (tap root vs fibrous, shallow vs deep) affects:
- **Tap root**: Deep, drought-tolerant, strong anchorage; some competition sensitivity
- **Fibrous/spreading roots**: Shallow, wet-tolerant, rapid establishment, erosion control

**Current state**: Embedded in prose (elevation_ranges_human mentions "shallow roots") but not structured
**SDM relevance**: Predicts slope stability, flood tolerance, drought tolerance
**Data source**: Literature, botanical descriptions, GRooT database
**Extraction difficulty**: Low (mostly categorical; strong morphological signal)

#### 6. Drought Tolerance (Quantified)
**Why it matters**: Water stress tolerance is THE key climate niche gradient:
- Currently buried in text (climate_change_vulnerability) or missing entirely
- Need: numeric range (e.g., "tolerates >4-month dry season") or category (low/moderate/high)

**Current state**: ~5% documented; mostly qualitative
**SDM relevance**: Directly constrains precipitation niche; critical for drought-vulnerable regions
**Data source**: Botanical monographs, BIEN, TRY, published water-stress studies
**Extraction difficulty**: Medium (heterogeneous literature; requires interpretation)

#### 7. Frost Tolerance (Quantified, minimum temperature)
**Why it matters**: Cold tolerance constrains northern/high-elevation range:
- Need: numeric minimum temperature (e.g., "-15C hardiness zone 7a") or category
- Currently in elevation_ranges as prose or missing

**Current state**: ~5% documented; USDA Hardiness Zones available for cultivated species
**SDM relevance**: Directly constrains temperature niche at cold edge
**Data source**: USDA Hardiness Zones, botanical literature, cultivation records
**Extraction difficulty**: Low-medium (well-documented for cultivated species; less for wild)

#### 8. Fire Tolerance / Fire Response
**Why it matters**: Fire disturbance tolerance defines post-fire trajectory:
- **Obligate seeder**: Requires fire to germinate; burns easily
- **Facultative seeder**: Can germinate after fire but also without it
- **Sprouter**: Resprouts from basal buds after fire
- **Fire-sensitive**: Killed by fire; slow recovery

**Current state**: ~5% documented; mostly in prose (fire_management_ai/human)
**SDM relevance**: Predicts response to fire disturbance; successional stage; plantation vs wildfire-adapted
**Data source**: Botanical monographs, fire ecology literature, USFS databases, FIA
**Extraction difficulty**: Medium (categorical; good literature coverage for temperate species; poor for tropical)

---

### Important But Secondary Gaps (Tier 2 Impact)

| Field | Why Useful | Current Coverage | Difficulty |
|-------|-----------|-------------------|-----------|
| Seed dispersal mechanism | Colonization range, dispersal distance | ~10% | Low (dispersal unit morphology) |
| Seed mass | Establishment probability, dispersal distance | ~8% | Medium (seed size varies by population) |
| Light requirement (shade tolerance) | Canopy position niche | ~8% | Low (strong morphological signal) |
| Phenological timing (flowering/fruiting season) | Temporal niche; biotic interaction windows | ~10% | Medium (variable by climate) |
| Maximum age / longevity category | Successional stage, disturbance response | 77% researched but needs clarification | Low (text→category conversion) |

---

## Data Coverage Audit

### Current Coverage Summary (as of March 2026)

| Category | Field | Species with Data | % Coverage | AI/Human Split | Priority |
|----------|-------|-------------------|-----------|----------------|---------  |
| **Tier 1: Critical SDM** |
| Ecology | habitat | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Ecology | elevation_ranges | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Climate | climate_type_koppengeiger | 59,943 | 88.5% | 100% computed | ✅ COMPLETE |
| Climate | annual_precipitation_mm | 60,005 | 88.6% | 100% computed | ✅ COMPLETE |
| Climate | annual_temperature_range_c | 60,005 | 88.6% | 100% computed | ✅ COMPLETE |
| Soil | soil_type_dominant | 44,858 | 66.2% | 100% computed | 🟡 ACCEPTABLE |
| Soil | soil_ph_dominant | 55,461 | 81.9% | 100% computed | ✅ COMPLETE |
| Soil | functional_ecosystem_groups | 48,081 | 71% | 100% computed | ✅ COMPLETE |
| Morphology | growth_form | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Morphology | maximum_height | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Morphology | leaf_type | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Morphology | deciduous_evergreen | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Morphology | lifespan | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| **[NEW]** | specific_leaf_area | ~3,400 | 5% | N/A | 🔴 URGENT |
| **[NEW]** | wood_density | ~6,800 | 10% | N/A | 🔴 URGENT |
| **[NEW]** | root_depth_max | ~3,400 | 5% | N/A | 🔴 URGENT |
| **[NEW]** | mycorrhizal_type | ~2,000 | 3% | N/A | 🔴 URGENT |
| **Tier 2: Context & Enhancement** |
| Biogeography | countries_native | 59,600 | 88% | 100% structured | ✅ COMPLETE |
| Biogeography | wcvp_native | ~40,000 | 60% | 100% structured | 🟡 ACCEPTABLE |
| Ecology | associated_species | ~20,000 | 30% | Mix of quality | 🟡 NEEDS CURATION |
| Ecology | ecological_function | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Ecology | native_adapted_habitats | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| Conservation | conservation_status | 48k researched | 71% | 40% AI / 60% human | ✅ COMPLETE |
| **[NEW]** | drought_tolerance (quantified) | ~3,400 | 5% | N/A | 🔴 URGENT |
| **[NEW]** | frost_tolerance_min_c | ~5,000 | 7% | N/A | 🔴 URGENT |
| **[NEW]** | fire_tolerance | ~3,400 | 5% | N/A | 🔴 URGENT |
| **[NEW]** | seed_dispersal_mechanism | ~6,800 | 10% | N/A | 🔴 URGENT |
| **[NEW]** | seed_mass_mg | ~5,400 | 8% | N/A | 🟠 HIGH |
| **[NEW]** | phenological_timing | ~6,800 | 10% | N/A | 🟠 HIGH |
| **[NEW]** | light_requirement | ~5,400 | 8% | N/A | 🟠 HIGH |
| **[NEW]** | nitrogen_fixation | ~3,400 | 5% | N/A | 🔴 URGENT |

**Key Findings**:

1. **Tier 1 (SDM-critical)**: 71-89% coverage for "researched" species (48,129 species). The 19,614 unresearched species are the gap.
2. **Tier 2 (Enhancement)**: 30-88% coverage; large variance. `associated_species` and `wcvp_native` need curation.
3. **New Fields**: 3-10% coverage across the board → **8 fields are URGENT to fill** for v4 training
4. **Data Source Quality**:
   - Computed fields (climate, soil from GEE/SRTM intersection): 100% reliable
   - Researched fields (habitat, ecology, morphology): 40-60% AI, rest human; needs validation in staging
   - New fields: Will be ~80% AI initially (from researcher pipeline); human curation is validation step

---

## AI Researcher Queue Plan

The AI researcher pipeline (Express/BullMQ) will process 19,614 unresearched species + gap-fill 8 new fields across all 67,743 species. We organize this into 3 phases.

### Phase 1: Immediate (Weeks 1-4)

**Goal**: Fill the 8 critical gaps for species WITH occurrence data (48,129 species).

**Rationale**: These species already have satellite + climate/soil embeddings. Adding trait text embeddings dramatically improves v4 training. Start here because:
1. AI researcher can infer traits from habitat description (e.g., "boreal evergreen conifer" → "likely ectomycorrhizal, frost-tolerant, deep-rooted")
2. Easier to validate against literature (existence of trait ≈ existence of occurrence)
3. Includes most cultivated/famous species → better data coverage in literature

**Fields to Extract** (in this order):

1. **mycorrhizal_type** (Priority 1: highest inference signal from taxonomy)
   - Strategy: 90% taxonomy-based (conifers ~95% ECM, hardwoods 50-70% AM depending on family, etc.)
   - 10% AI researcher: "Genus X typically mycorrhizal with..." + literature cross-check
   - Model: Phi-3 (fast, strong taxonomy reasoning)
   - Expected coverage: 85-90% of 48,129

2. **nitrogen_fixation** (Priority 2: high-value, high-confidence inferences)
   - Strategy: 80% taxonomy-based (Legumes, Betulaceae, Casuarinaceae are N-fixing families)
   - 20% AI researcher: "Review for symbiotic relationships, Frankia vs Rhizobia"
   - Model: Phi-3 + Qwen2.5
   - Expected coverage: 90%+ of 48,129

3. **light_requirement** (Priority 3: strong signal from growth_form + habitat)
   - Strategy: AI researcher infers from habitat text: "understory", "shade-tolerant", "pioneer" keywords
   - Categorical output: "shade-tolerant" / "intermediate" / "light-demanding"
   - Model: Phi-3 (good at parsing existing text)
   - Expected coverage: 85-90%

4. **seed_dispersal_mechanism** (Priority 4: morphology-based + habitat inference)
   - Strategy: Infer from leaf_type, fruit_type, habitat keywords
   - Categories: wind / animal / water / gravity / ballistic
   - Model: Qwen2.5 (multimodal logic good at trait inference)
   - Expected coverage: 80%+

5. **specific_leaf_area** (Priority 5: harder, requires literature search)
   - Strategy: For tropical species, infer from "deciduous_evergreen + habitat" (deciduous → high SLA)
   - For conifers, use phylogenetic nearest neighbors (TRY database median values)
   - AI researcher: "SLA for genus X typically ranges 50-150 cm²/g; this species' description suggests..."
   - Model: Qwen2.5 + Gemma-2 (good ensemble for literature inference)
   - Expected coverage: 50-60% (some species simply too sparse in literature)

6. **wood_density** (Priority 6: moderate inference, good literature coverage)
   - Strategy: Similar to SLA; genus-level inference from DRYAD/FIA nearest neighbors
   - AI researcher: literature search "wood specific gravity", "timber density"
   - Model: Qwen2.5 + Claude (Claude strong at parsing technical literature)
   - Expected coverage: 60-70%

7. **frost_tolerance** / **drought_tolerance** (Priority 7-8: medium difficulty)
   - Strategy: Infer from climate data + morphology
     - If annual_temp_range < -15C documented somewhere in native range → frost-tolerant
     - If annual_precip_min > 4 months below 100mm → drought-tolerant
   - AI researcher: literature search "hardiness zone", "water deficit", "drought response"
   - Model: Gemma-2 (good at structured reasoning)
   - Expected coverage: 50-60% (climate inference), 40-50% (literature-backed)

8. **root_depth** (Priority 9: hardest; least literature, most inference)
   - Strategy: Infer from soil type + elevation + associated_species
   - Deep roots: "upland", "xeric", "coarse-textured soils" habitats
   - Shallow roots: "riparian", "wetland", "fine clay" habitats
   - Model: Qwen2.5 (multi-signal synthesis)
   - Expected coverage: 40-50%

**Phase 1 Resource Plan**:
- **Timeline**: 4 weeks
- **Queue strategy**: BullMQ with 3 parallel workers (CPU-bound, not I/O-bound)
  ```
  Worker 1: Taxonomy inference (mycorrhizal, N-fix)
  Worker 2: Morphology inference (light req., seed dispersal)
  Worker 3: Literature search (SLA, wood density, drought/frost)
  ```
- **Processing rate**: ~12,000 species/week (48,129 species ÷ 4 weeks), or ~3,000/day per worker
- **Model rotation**:
  - Phi-3 (fast): Taxonomy, text parsing (7-10 tokens/sec)
  - Qwen2.5 (balanced): Multi-signal synthesis (5-8 tokens/sec)
  - Gemma-2: Verification (8-10 tokens/sec, runs locally via Ollama)
- **Validation**: 10% spot-check (5,000 species sampled) by human domain expert
- **Output**: 8 new columns in PostgreSQL `species` table, populated with AI-extracted values + confidence scores

---

### Phase 2: Enrichment (Weeks 5-12, parallel with Phase 1)

**Goal**: Fill the 8 new fields for the 19,614 UNRESEARCHED species (those without occurrence data).

**Rationale**: These species lack occurrence embeddings entirely, so text embeddings become the primary signal. High-quality text → better zero-shot prediction. Also backfill any gaps from Phase 1.

**Strategy**:

For unresearched species, the AI researcher faces a harder problem: **no occurrence data to validate against**. Therefore, we use a **consensus-based validation approach**:

1. **Multi-model extraction**: Route each species to 2-3 models for trait extraction
   - Model A (Phi-3): "What ecosystem is Shorea javanica found in? Infer the following traits..."
   - Model B (Qwen2.5): Same prompt, slightly different phrasing
   - Model C (Gemma-2): Verification pass, "Confirm or revise the following traits..."

2. **Consensus scoring**: Combine outputs with weighting:
   ```
   For each trait, confidence = (num_models_agreeing / total_models) *
                                (avg_model_confidence_score)
   ```

3. **Threshold logic**:
   - Confidence ≥ 0.7 → accept and use in text embedding
   - Confidence 0.5-0.7 → mark as "low confidence", use but flag for review
   - Confidence < 0.5 → skip field (let sentence transformer handle absence)

4. **Human spot-check**: 100 random species sampled for expert review (genus curator or botanist)

**Processing plan**:
- **Timeline**: Parallel with Phase 1 (weeks 1-12)
- **Processing rate**: 19,614 species ÷ 12 weeks = ~1,630/week = ~230/day
- **Queue strategy**: Lower priority than Phase 1; run on shared workers at off-peak
- **Output**: Same 8 columns + confidence_scores for 19,614 species

**Quality gates**:
- Target: ≥60% confidence for ≥5 out of 8 fields per species
- Fallback: If <5 fields ≥60% confidence, species goes to human triage queue (see Phase 3)

---

### Phase 3: Expansion & Curation (Weeks 13-26)

**Goal**: Deepen knowledge coverage and fix validation failures; add new SDM-relevant fields as needed.

**Sub-Phase 3a: Human Review & Correction** (Weeks 13-16)

After Phases 1-2, we have:
- 48,129 species with new trait fields (AI-extracted, 10% spot-checked)
- 19,614 species with new trait fields (AI-extracted + consensus, 100 spot-checked)
- ~5,000-8,000 flagged as "low confidence" or "conflicting models"

**Triage queue**:
1. **Tier A - High value, low confidence** (~1,000 species): Famous/economically important species with <50% trait confidence
   - Assign to expert botanists or genus curators via bounty system (Treekipedia points)
   - Example: *Tectona grandis* (teak) — economically critical, should have high-confidence traits

2. **Tier B - Medium value** (~2,000 species): Regional importance (endemic, conservation-relevant)
   - Open to community research (Treekipedia UI for structured form entry)
   - Provide literature recommendations from AI researcher's search results

3. **Tier C - Low confidence, niche species** (~2,000-4,000): AI-extracted but not validated
   - Remain in database with confidence scores; improve over time

**Human input strategy**:
- **Expert pathway**: Botanists/ecologists contribute via admin API or web form
  - Input validated trait values + literature citation
  - System auto-merges with AI data (human takes precedence)
  - Expert gets Treekipedia points + attribution

- **Community pathway**: General users flag suspicious values or contribute observations
  - Threshold: ≥3 independent submissions → triggers review
  - Example: User flags "Pinus radiata frost tolerance = 10C" (wrong), submits "-12C + literature link"

**Estimated effort**:
- Tier A triage: 20-30 hours/week (1-2 expert reviews + weekly curation calls)
- Tier B community: 10-20 hours/week (moderation, quality gates)
- Tier C: No action (backgrounded)

---

**Sub-Phase 3b: New Field Expansion** (Weeks 13-26)

Identify additional SDM-relevant fields (beyond the initial 8) that emerge from:
1. Literature review of recent SDM papers
2. SAFE-B recommender feedback ("users want to know...")
3. Plantation/restoration expert feedback

**Candidate fields** (prioritized):

| Field | SDM Value | Difficulty | Timeline |
|-------|-----------|-----------|----------|
| Ecophysiological optimum temperature | High (niche peak) | High | Weeks 15-18 |
| Hydraulic P50 (cavitation threshold) | High (drought physiology) | High | Weeks 16-19 |
| Maximum DBH (diameter at breast height) | Medium (mature tree size) | Low | Weeks 13-14 |
| Water requirement (annual) | Medium (irrigation planning) | Medium | Weeks 14-16 |
| Nutrient demands (N, P, K) | Medium (soil fertility niche) | Medium | Weeks 17-20 |
| Pest and disease susceptibilities | Low-medium (disturbance recovery) | High | Weeks 19-22 |

**Execution**:
- AI researcher extracts via literature + expert interviews
- Lower validation bar than Phase 1 (optional fields; "null" is acceptable)
- Community contributions incentivized for rare/endemic species

---

### Phase 4: Maintenance & Feedback Loop (Weeks 26+)

Ongoing maintenance and continuous improvement:

1. **Continuous AI research**: BullMQ queue always has work
   - New species additions → automatically queued for trait extraction
   - Species with "low confidence" fields → periodic re-research with newer models
   - As better models release (e.g., Claude 3.5, Llama 4), re-run extraction with model upgrade

2. **Community feedback**:
   - Species page flag: "This trait seems wrong" → ticket to research queue
   - Restoration practitioners report "Species X didn't thrive at location Y" → investigate niche mismatch, refine traits

3. **Model improvement**:
   - Collect human corrections (Phase 3a) as validation dataset
   - Fine-tune local model (Llama via LoRA) on Treekipedia domain-specific corrections
   - Compare: vanilla Phi-3 vs. Treekipedia-tuned Phi-3 LoRA (expect 5-10% F1 improvement)

4. **Quarterly review**:
   - Evaluate sentence-transformer embeddings against k-NN occurrence embeddings
   - If text embeddings achieve >0.85 spearman rank correlation with k-NN for species with occurrences → confidence that zero-shot works for species without

---

## Integration with SINR v4 Training

### Architecture Overview

SINR v3 uses 5 branches:
1. **Satellite** (64D AlphaEarth embeddings per location)
2. **Temporal** (8-year AlphaEarth attention, 128D)
3. **Environment** (56 environmental variables + 5 categorical)
4. **Land State** (5 features: class, disturbance, stability, succession, AE_change)
5. **Location Encoding** (lat/lon → 40D, expanded to 64D)

SINR v4 adds:

6. **Species Text Knowledge** (384D sentence-transformer embeddings)

### Branch Design

**Input**:
- For each species with occurrence data: structured text description (see Section 3)
- Encoded once during data prep: `embedding = SentenceTransformer('all-MiniLM-L6-v2').encode(text_description)`
- For each training sample (species + location), look up the species embedding

**Network Architecture**:
```python
class SpeciesTextEmbeddingBranch(nn.Module):
    def __init__(self, input_dim=384, hidden_dim=128, output_dim=64):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.gelu = nn.GELU()
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, text_embeddings):
        """
        Args:
            text_embeddings: (batch_size, 384)
        Returns:
            species_knowledge_repr: (batch_size, 64)
        """
        x = self.fc1(text_embeddings)
        x = self.gelu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x
```

**Fusion Strategy** (gated residual, similar to v3's jrc branch):
```python
class V4FusionLayer(nn.Module):
    def __init__(self, feature_dim=64):
        super().__init__()
        # Existing v3 branches:
        self.sat_branch = SatelliteBranch()     # → 64D
        self.temporal_branch = TemporalBranch() # → 64D
        self.env_branch = EnvironmentBranch()   # → 64D
        self.landstate_branch = LandStateBranch() # → 64D
        self.location_branch = LocationBranch() # → 64D

        # NEW: Species text branch
        self.text_branch = SpeciesTextEmbeddingBranch()  # 384D → 64D

        # Gating: learns which branch to weight more for each sample
        self.text_gate = nn.Sequential(
            nn.Linear(64 * 6, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def forward(self, location_features, species_id):
        """
        Args:
            location_features: {
                'sat_embedding': (batch, 64),
                'temporal_attn': (batch, 128),
                'env_features': (batch, 56 + 5),
                'landstate_features': (batch, 5),
                'lat_lon': (batch, 2)
            }
            species_id: (batch,) → lookup text embedding
        Returns:
            fused_repr: (batch, 64)
        """
        # Existing branches
        sat_repr = self.sat_branch(location_features['sat_embedding'])      # → 64D
        temporal_repr = self.temporal_branch(location_features['temporal']) # → 64D
        env_repr = self.env_branch(location_features['env_features'])       # → 64D
        landstate_repr = self.landstate_branch(location_features['landstate']) # → 64D
        location_repr = self.location_branch(location_features['lat_lon'])  # → 64D

        # NEW: Species text branch
        text_embeddings = self.lookup_species_text_embeddings(species_id)   # → 384D
        text_repr = self.text_branch(text_embeddings)                       # → 64D

        # Concatenate all branches
        all_reps = torch.cat([sat_repr, temporal_repr, env_repr,
                              landstate_repr, location_repr, text_repr],
                             dim=1)  # → (batch, 384)

        # Gating: learn weighted fusion
        alpha = self.text_gate(all_reps)  # → (batch, 1)

        # Blend: text is new signal, but don't completely override location signals
        fused = (1 - alpha) * torch.mean(
                    torch.stack([sat_repr, temporal_repr, env_repr,
                                 landstate_repr, location_repr], dim=0),
                    dim=0
                ) + alpha * text_repr

        return fused  # → (batch, 64)
```

**Training Strategy**:

1. **Freeze vs. Fine-tune Sentence Transformer**:
   - Recommended: **Freeze** (don't fine-tune the 384D embedding model)
   - Rationale: all-MiniLM-L6-v2 is already well-trained on general semantic similarity; fine-tuning on 32M rows of plant data adds minimal value vs. training overhead
   - The **text branch FC layers** (384→128→64) ARE trainable, learning to extract SDM-relevant features

2. **Loss function** (same as v3):
   - Binary classification: species presence (1) vs. absence (0)
   - BCE loss with logits
   - Optional: focal loss if species prevalence imbalanced

3. **Data composition for training**:
   - **For species with occurrence data** (48,129 species):
     - Training pairs: species + AlphaEarth location where it occurs → label=1
     - Negative sampling: random locations (not in native range, or far from any occurrence) → label=0
     - Text embedding available: use it

   - **For species WITHOUT occurrence data** (19,614 species):
     - Cannot use in training loop (no positive labels)
     - BUT: can use text embeddings in inference (zero-shot prediction)
     - This is the power of text embeddings: they enable predictions for species with no training data

4. **Expected improvements**:
   - **k-NN baseline (v3)**: AUC ~0.82-0.84 (on test set of 48k species with occurrences)
   - **k-NN + text embeddings (v4 naive)**: AUC ~0.84-0.86 (text provides complementary signal)
   - **k-NN + text + gated fusion (v4 proper)**: AUC ~0.85-0.87 (learned gating optimizes branch weights)
   - **Zero-shot on 19,614 unresearched species**: Expected ~0.72-0.76 AUC (weaker than occurrence-trained species, but useful for gap-filling)

### Data Preparation Pipeline

```python
# Pseudo-code for v4 data prep

# Step 1: Generate text descriptions for all 67,743 species
species_texts = {}
for taxon_id in all_67743_species:
    species_row = db.query("SELECT * FROM species WHERE taxon_id = ?", taxon_id)
    text = generate_knowledge_text(species_row)  # Uses template from Section 3
    species_texts[taxon_id] = text

# Step 2: Encode text descriptions once (offline, not during training)
from sentence_transformers import SentenceTransformer
encoder = SentenceTransformer('all-MiniLM-L6-v2')

species_text_embeddings = {}
for taxon_id, text in species_texts.items():
    embedding = encoder.encode(text, normalize_embeddings=True)  # 384D
    species_text_embeddings[taxon_id] = embedding

# Store in PostgreSQL:
# CREATE TABLE species_text_embeddings (
#     taxon_id VARCHAR(50) PRIMARY KEY,
#     text_content TEXT,
#     embedding vector(384),
#     text_confidence FLOAT,  # aggregate confidence of traits in text
#     created_at TIMESTAMP
# );

# Step 3: Create training dataset
# For each species + location occurrence:
training_samples = []
for taxon_id in researched_species_48129:
    # Get location data (satellite embedding, climate, soil, etc.)
    location_features = db.query(
        "SELECT ae_embedding, annual_precip, soil_ph, ...
         FROM species_occurrence_embeddings
         WHERE taxon_id = ? LIMIT 10000",
        taxon_id
    )

    # Get text embedding
    text_embedding = species_text_embeddings[taxon_id]

    # Create training pairs
    for loc in location_features:
        sample = {
            'taxon_id': taxon_id,
            'lat': loc.latitude,
            'lon': loc.longitude,
            'sat_embedding': loc.ae_embedding,  # 64D
            'temporal_features': loc.ae_temporal,  # 128D
            'env_features': loc.annual_precip + loc.soil_ph + ...,  # 56+5=61D
            'landstate_features': loc.forest_stability + ...,  # 5D
            'text_embedding': text_embedding,  # 384D ← NEW
            'label': 1  # Species present at this location
        }
        training_samples.append(sample)

    # Negative sampling
    random_locations = sample_absent_locations(taxon_id, n=len(location_features))
    for loc in random_locations:
        sample = {
            'taxon_id': taxon_id,
            'lat': loc.latitude,
            'lon': loc.longitude,
            'sat_embedding': loc.ae_embedding,
            'temporal_features': loc.ae_temporal,
            'env_features': loc.env_data,
            'landstate_features': loc.landstate_data,
            'text_embedding': text_embedding,  # Same species, different location
            'label': 0  # Species absent (or very rare)
        }
        training_samples.append(sample)

# Step 4: Train SINR v4 on 32M+ training samples
# See orchestrator/train_sinr_v4.py (analogous to train_sinr_v3.py)
```

### Inference Strategy

**For query locations with occurrence data** (species with k-NN training):
```python
def predict_species_v4_with_occurrences(query_location):
    """
    Standard k-NN + neural head approach
    """
    # 1. Get AlphaEarth embedding for query location
    query_sat_embedding = get_alphaearth_embedding(query_location.lat, query_location.lon)

    # 2. k-NN match against occurrence embeddings
    k_nearest = find_k_nearest_occurrences(query_sat_embedding, k=5)

    # 3. For each species in k-NN results, run neural prediction
    predictions = []
    for species_id in k_nearest.species_ids:
        # Get species text embedding
        text_emb = lookup_text_embedding(species_id)

        # Forward pass through v4 model
        logits = sinr_v4_model(
            sat_embedding=query_sat_embedding,
            temporal_features=get_temporal_features(...),
            env_features=get_env_features(...),
            landstate_features=get_landstate_features(...),
            species_text_embedding=text_emb
        )
        probability = sigmoid(logits)

        predictions.append({
            'species_id': species_id,
            'probability': probability,
            'method': 'k-NN + neural'
        })

    return sorted(predictions, key=lambda x: x['probability'], reverse=True)
```

**For zero-shot prediction** (species WITHOUT occurrence data):
```python
def predict_species_v4_zero_shot(query_location, target_species):
    """
    No occurrence data available. Text embedding becomes primary signal.
    """
    # 1. Get location features (satellite, climate, soil, etc.)
    location_features = extract_location_features(query_location)

    # 2. Get species text embedding
    text_emb = lookup_text_embedding(target_species)

    # 3. Forward pass (location signals + text knowledge only)
    logits = sinr_v4_model(
        sat_embedding=location_features.sat_embedding,
        temporal_features=location_features.temporal,
        env_features=location_features.env,
        landstate_features=location_features.landstate,
        species_text_embedding=text_emb
    )

    probability = sigmoid(logits)

    return {
        'species_id': target_species,
        'probability': probability,
        'method': 'text-embedding + zero-shot',
        'confidence': 'medium'  # Lower than occurrence-trained species
    }
```

---

## Implementation Roadmap

### Timeline

| Phase | Weeks | Objective | Deliverables |
|-------|-------|-----------|--------------|
| **Phase 1: Quick Wins (Tier 1)** | 1-4 | Fill 8 critical gaps for 48,129 researched species | 8 new columns + text embeddings encoded, 48k species, 90%+ coverage |
| **Phase 2: Unresearched Species** | 1-12 (parallel) | Extract traits for 19,614 species without occurrence data | 8 new columns + text embeddings for all 67,743 species, 60%+ coverage |
| **Phase 3a: Human Curation** | 13-16 | Expert review + community corrections for low-confidence fields | 5,000-8,000 improved species, validation dataset for model fine-tuning |
| **Phase 3b: Expansion** | 13-26 | Add new SDM-relevant fields (P50, ecophys optimum, etc.) | 3-5 new fields extracted for subset of species |
| **Phase 4: SINR v4 Training** | 20+ | Integrate text embeddings into v4 neural architecture | Trained SINR v4 model (384D text branch), baseline →  +3-5% AUC improvement |
| **Phase 4: Maintenance** | 26+ | Continuous improvement loop | Ongoing research queue, model fine-tuning, community feedback integration |

### Milestones

**Milestone 1 (Week 4)**: All 48,129 researched species have complete trait profiles + text embeddings
- Gate: 90%+ coverage for 8 new fields in Phase 1 species
- Validation: 10% spot-check (5,000 species) passes domain expert review (>80% accuracy)

**Milestone 2 (Week 12)**: All 19,614 unresearched species have trait profiles with confidence scores
- Gate: ≥60% confidence for ≥5/8 fields for ≥80% of unresearched species
- Fallback: 5,000-8,000 flagged as "low confidence" for Phase 3a review

**Milestone 3 (Week 16)**: Human curation complete for high-value species
- Gate: Tier A (1,000 species) expert-reviewed
- Output: Expert corrections merged into database

**Milestone 4 (Week 24)**: SINR v4 model trained and benchmarked
- Gate: Model achieves ≥0.86 AUC on test set (researched species)
- Validation: AUC on zero-shot predictions for 19,614 unresearched species ≥0.72

**Milestone 5 (Week 26+)**: v4 deployed to production; maintenance loop active
- Gate: Text embeddings and text branch fully integrated into inference pipeline
- Ongoing: Continuous re-research of low-confidence species, model fine-tuning

---

## References & Related Documentation

**Within Treekipedia**:
- [MASTER_PREDICTION_ARCHITECTURE_3.md](./MASTER_PREDICTION_ARCHITECTURE_3.md) — v3 k-NN foundation and occurrence data structure
- [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](../../TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) — Insight model and multi-tier storage strategy
- [TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md](../../TREEKIPEDIA_AI_RESEARCHER_ARCHITECTURE.md) — Multi-model extraction pipeline (BullMQ, Ollama, aspect-based prompting)
- [RESEARCH_FUNCTIONAL_TRAITS.md](./RESEARCH_FUNCTIONAL_TRAITS.md) — Functional trait databases (TRY, BIEN, GRooT)
- [SCHEMA_IMPROVEMENTS.md](./SCHEMA_IMPROVEMENTS.md) — Environmental data coverage analysis

**External References**:
- **LE-SINR**: Hamilton et al., "Learning Ecology and Environment with Language Models" (NeurIPS 2024)
  - Demonstrates text descriptions alone can predict species ranges zero-shot
  - Text embeddings generalize across geographic regions and climate gradients
- **TRY Database**: https://www.try-db.org/ (1M+ trait records across 10K+ species)
- **BIEN Database**: http://bien.nceas.ucsb.edu/ (915K trait observations, 93K species, R package + API)
- **GRooT Database**: Global Root Traits Database (Guerrero-Ramírez et al., 2021) — 38 root traits, 6,214 species
- **Sentence Transformers**: https://www.sbert.net/ (all-MiniLM-L6-v2 = 384D, 22M parameters)
- **Functional Ecology**: Westoby et al. (1998) "Plant ecological strategies: some leading dimensions of variation between species" — Leaf Economics Spectrum framework

---

**Document Version**: 1.0
**Last Updated**: March 7, 2026
**Status**: Architecture specification, ready for Phase 1 implementation
**Maintainers**: Treekipedia ML/Research Team
