# AlphaEarth Environmental Embeddings Pilot: Strategic Species Selection Plan

**Version:** 1.0
**Date:** October 27, 2025
**Author:** Research Agent
**Purpose:** Scientific strategy for selecting 100 tree species to test AlphaEarth environmental embeddings for predicting species distributions

---

## Executive Summary

This document outlines a rigorous, scientifically-grounded strategy for selecting 100 tree species from the Treekipedia database (67,743 total records, 50,797 species-level records) to test the effectiveness of AlphaEarth 64-dimensional environmental embeddings in predicting species presence from environmental conditions.

**Key Design Principles:**
1. **Ecological Stratification**: Represent diverse biomes, growth forms, and niche breadths
2. **Data Quality Balance**: Select species with 100-50,000 occurrence points (avoid sparse data and computational limits)
3. **Hypothesis Testing**: Enable tests of niche conservatism, competitive exclusion, and phylogenetic signal
4. **Geographic Diversity**: Cover multiple continents and environmental gradients
5. **Conservation Relevance**: Include threatened and common species to test model discrimination

---

## 1. Database Analysis Summary

### Available Data (Species-level only, subspecies='NA')
- **Total species:** 50,797
- **Species with occurrence data:** ~48,129 (estimated)
- **Total geohash tiles:** 5,786,835 (Level 7, ~150m resolution)
- **Species with ecoregion data:** 44,396 (87.3%)
- **Species with biome data:** 44,396 (87.3%)
- **Species with intact forest classification:** 44,615 (87.8%)

### Data Quality Characteristics

**Occurrence Distribution:**
- Sample data shows range from 1 to 466,280 tiles per species
- Pinaceae species have highest occurrence counts (e.g., Pinus sylvestris: 466k tiles)
- Many tropical species have moderate counts (10-5,000 tiles)
- Target range: 100-50,000 tiles (avoids sparse data and GEE API limits)

**Intact Forest Classification:**
- NO (disturbed only): 28,053 species (55.2%)
- NO;YES (both): 12,452 species (24.5%)
- YES;NO (both): 3,151 species (6.2%)
- YES (intact only): 959 species (1.9%)
- NA (no data): 6,182 species (12.2%)

**Taxonomic Distribution (Top families):**
1. Fabaceae (6,412 species)
2. Rubiaceae (5,092 species)
3. Myrtaceae (4,640 species)
4. Lauraceae (2,654 species)
5. Euphorbiaceae (2,414 species)
6. Malvaceae (2,011 species)
7. Sapindaceae (1,699 species)
8. Fagaceae (1,257 species)
9. Salicaceae (1,268 species)
10. Pinaceae (~140 species with excellent occurrence data)

**Ecoregion Breadth (Generalist vs Specialist):**
- Specialists (1 ecoregion): 10,022 species (19.7%)
- Moderate (2-5 ecoregions): 19,027 species (37.5%)
- Generalist (6-10 ecoregions): 7,239 species (14.3%)
- Widespread (11+ ecoregions): 8,108 species (16.0%)

**Geographic Coverage:**
- Tropical hotspots well-represented (Amazon, SE Asia, Central Africa)
- Temperate regions (North America, Europe) have high-quality data
- Some species endemic to single countries (10,496 species)

---

## 2. Scientific Literature Review: Key Findings

### A. Species Selection Best Practices

Based on recent research (2024-2025), effective species selection for distribution modeling requires:

1. **Addressing Sampling Bias** (Aiello-Lammens et al. 2015, Steen et al. 2021)
   - Geographic sampling bias creates spatially autocorrelated occurrences
   - Solution: Spatial thinning to reduce clustering (e.g., min 10km separation)
   - Tool: spThin R package or GeoThinneR

2. **Background Point Selection** (Barbet-Massin et al. 2012)
   - For presence-only models (MaxEnt), background point selection is critical
   - Theory suggests stratified sampling in environmental space for species at equilibrium
   - Random geographic sampling can introduce bias

3. **Model Complexity and Regularization** (Warren & Seifert 2011)
   - MaxEnt requires appropriate regularization to avoid overfitting
   - Information criteria (AIC, BIC) help select optimal model complexity
   - Small sample sizes (<100 points) require higher regularization

4. **Spatial Autocorrelation** (Dormann et al. 2007)
   - Clustered occurrences inflate model accuracy statistics
   - Can cause models to overfit environmental correlates of sampling bias
   - Important: Geographic bias ≠ environmental bias (Vollering et al. 2019)

### B. Representative Species Selection Criteria

Research suggests selecting species that:

1. **Span environmental gradients** (temperature, precipitation, elevation)
2. **Represent different equilibrium states** (established vs expanding ranges)
3. **Include phylogenetic diversity** (test for niche conservatism)
4. **Have sufficient sample sizes** (>50 occurrences minimum, ideally 100+)
5. **Cover diverse biomes and ecoregions**

### C. Testing Strategy Recommendations

1. **Cross-validation approaches:**
   - Geographic blocking (k-fold with spatial partitions)
   - Temporal holdout (if occurrence data has dates)
   - Environmental stratification

2. **Validation metrics** (Velazco et al. 2021):
   - Use multiple metrics: AUC, TSS, continuous Boyce index
   - Avoid threshold-dependent metrics with presence-only data
   - Consider spatial predictions at unsampled locations

3. **Handling data-poor species:**
   - Ensemble models can improve performance
   - Transfer models from data-rich congeners
   - Account for detection probability

---

## 3. Selection Framework: Multi-Criteria Stratification

### Design Philosophy

Instead of random selection or "most data" approach, we use **ecological stratification** to create a designed experiment that maximizes scientific insight. The 100 species will be distributed across multiple dimensions:

### A. Dimension 1: Biome Representation (30 species)

Target distribution across major biomes:
- **Tropical Moist Broadleaf** (15 species): Amazon, Congo, SE Asia rainforests
- **Temperate Broadleaf & Mixed** (8 species): Eastern US, Europe, China
- **Boreal Forests/Taiga** (3 species): Northern conifers
- **Tropical Dry Forests** (4 species): Savanna woodlands
- **Mediterranean** (3 species): Sclerophyll vegetation
- **Montane** (4 species): High-elevation specialists
- **Mangroves** (3 species): Coastal specialists

**Rationale:** Environmental embeddings should capture distinct climatic and ecological conditions across biomes. This distribution tests the model's ability to discriminate biome-specific niches.

### B. Dimension 2: Niche Breadth (25 species)

- **Specialists** (10 species): 1-2 ecoregions, narrow niches
- **Moderate generalists** (10 species): 3-6 ecoregions
- **Generalists** (5 species): 7-15 ecoregions
- **Cosmopolitan** (0 species): >15 ecoregions (excluded - may violate model assumptions)

**Rationale:** Tests whether environmental embeddings can distinguish between narrow specialists (strong environmental filtering) vs generalists (broader tolerance). Expected: specialists should have tighter environmental clusters.

### C. Dimension 3: Conservation Status (20 species)

- **Threatened/Endangered** (10 species): IUCN Red List species
- **Least Concern/Common** (10 species): Widespread, abundant species

**Rationale:** Tests if the model can identify restricted ranges of threatened species vs widespread distributions of common species. This has direct conservation applications.

### D. Dimension 4: Intact Forest Association (15 species)

- **Intact forest only (YES)** (5 species): Old-growth specialists
- **Disturbed areas only (NO)** (5 species): Early successional, disturbance-adapted
- **Both environments (NO;YES or YES;NO)** (5 species): Habitat generalists

**Rationale:** Tests if environmental embeddings capture habitat integrity gradients. Intact forest specialists should cluster in low-disturbance environmental conditions.

### E. Dimension 5: Phylogenetic Diversity (20 species)

Select congeners (same genus) across different families:
- **Quercus** (oaks - Fagaceae): 4 species across continents
- **Pinus** (pines - Pinaceae): 4 species (boreal to subtropical)
- **Eucalyptus** (Myrtaceae): 3 species (Australian endemics)
- **Ficus** (figs - Moraceae): 3 species (tropical generalists)
- **Acacia** (Fabaceae): 3 species (arid to tropical)
- **Other genera** (1 species each): Salix, Nothofagus, Dipterocarpus

**Rationale:** Tests phylogenetic niche conservatism (PNC) hypothesis. Closely related species should have similar environmental niches unless adaptive radiation occurred. This identifies whether AlphaEarth captures phylogenetically constrained vs evolutionarily labile traits.

### F. Dimension 6: Geographic Diversity (15 species)

Ensure continental representation:
- **South America** (4 species): Amazon, Andes, Cerrado
- **Africa** (3 species): Congo, Madagascar, Sahel
- **Asia** (3 species): SE Asia, India, temperate China
- **North America** (2 species): Eastern forests, western mountains
- **Europe** (1 species): Mediterranean or temperate
- **Oceania** (2 species): Australia, New Guinea

**Rationale:** Geographic isolation can lead to convergent evolution (similar environments, unrelated species). Tests if environmental embeddings predict presence based on environmental similarity alone.

### G. Dimension 7: Occurrence Data Quality (10 species)

Stratify by occurrence count:
- **Sparse data** (100-500 tiles): 2 species (tests model performance with limited data)
- **Moderate data** (500-5,000 tiles): 4 species (typical scenario)
- **Rich data** (5,000-50,000 tiles): 4 species (high confidence benchmarks)

**Rationale:** Assesses how occurrence sample size affects model performance. Rich-data species serve as positive controls.

---

## 4. Testing Location Selection Strategy

### A. Define 30 Strategic Test Points

Instead of random test locations, select points that represent:

1. **Environmental Gradient Extremes (10 points)**
   - Coldest: Boreal Canada (Yukon)
   - Hottest: Sahel dry season
   - Wettest: Western Ghats monsoon zone
   - Driest: Atacama fringe
   - Highest elevation: Andean treeline
   - Sea level: Mangrove estuaries
   - Most seasonal: Mediterranean-climate region
   - Least seasonal: Equatorial rainforest
   - High soil diversity: Amazon terra firme vs várzea
   - Extreme disturbance: Recently logged area

2. **Biogeographic Transition Zones (10 points)**
   - **Ecotones** where multiple biomes meet:
     - Cerrado-Amazon transition (Brazil)
     - Forest-savanna mosaic (Central Africa)
     - Temperate-boreal transition (Canada)
     - Mediterranean-desert transition (Morocco)
     - Montane-lowland transition (Andes)
   - **Islands** (oceanic vs continental):
     - Madagascar (ancient isolation)
     - Borneo (high endemism)
     - New Guinea (montane diversity)
   - **Climate boundaries**:
     - Köppen climate transitions (e.g., Cfa/Cfb boundary)

3. **Known Presence/Absence Locations (10 points)**
   - For 10 selected "benchmark species," identify:
     - 5 points at range center (high probability presence)
     - 3 points at range edge (marginal habitat)
     - 2 points outside range (environmental suitable but absent)

   **Purpose:** Validate model predictions against known distributions. Tests if environmental embeddings alone can predict presence, or if dispersal limitation and historical contingency matter.

### B. Test Point Selection Algorithm

For each of the 100 species:

1. **Extract occurrence locations** from geohash tiles
2. **Spatially thin occurrences** (10km minimum distance) to reduce autocorrelation
3. **Generate pseudo-absences/background points**:
   - Option A: Random within convex hull of occurrences
   - Option B: Environmentally stratified (sample across environmental PCA space)
   - Option C: Bias-corrected (weight by sampling intensity)

4. **Reserve holdout data**:
   - 70% training occurrences
   - 30% test occurrences (spatial block cross-validation)

5. **Extract AlphaEarth embeddings** at:
   - All training occurrence locations
   - All test occurrence locations
   - All 30 strategic test points
   - Background points

6. **Build k-prototype models**:
   - Cluster occurrences in 64-dimensional embedding space
   - Identify centroid and radius for each species
   - Predict presence at test points based on distance to centroid

### C. Environmental Space Coverage

The 30 test points should collectively cover:

- **Temperature range:** -20°C to +40°C annual mean
- **Precipitation range:** 100mm to 10,000mm annual
- **Elevation range:** 0m to 4,500m
- **Soil types:** Sandy, clay, loam, peat, laterite
- **Disturbance gradient:** Intact primary forest → logged → agricultural edge
- **Seasonality gradient:** Aseasonal equatorial → strongly seasonal Mediterranean

**Validation:** Use PCA on environmental variables to ensure test points span the full environmental space occupied by the 100 selected species.

---

## 5. Expected Outcomes & Validation Framework

### A. Hypothesis Testing

**Hypothesis 1: Environmental Niche Detection**
- *Prediction*: Species with narrow niches (specialists) will cluster tightly in AlphaEarth embedding space
- *Test*: Compare intra-species variance in embedding space for specialists vs generalists
- *Expected result*: Specialists have smaller standard deviation in embedding dimensions

**Hypothesis 2: Phylogenetic Niche Conservatism**
- *Prediction*: Congeners (same genus) will occupy similar regions of embedding space
- *Test*: Calculate phylogenetic signal (Blomberg's K or Pagel's λ) for embedding centroids
- *Expected result*: K > 1 indicates strong conservatism

**Hypothesis 3: Biome Discrimination**
- *Prediction*: Species from different biomes occupy distinct regions of embedding space
- *Test*: Discriminant analysis on embeddings with biome as grouping variable
- *Expected result*: >80% correct classification of species to biomes

**Hypothesis 4: Conservation Status Signal**
- *Prediction*: Threatened species have smaller environmental niche volumes
- *Test*: Compare convex hull volume in embedding space for threatened vs common species
- *Expected result*: Threatened species have significantly smaller volumes (t-test p < 0.05)

**Hypothesis 5: Habitat Integrity Discrimination**
- *Prediction*: Intact-forest specialists cluster in distinct embedding regions vs disturbed-area species
- *Test*: PCA on embeddings colored by intact forest category, test for clustering
- *Expected result*: Distinct clusters for "YES", "NO", "BOTH" categories

**Hypothesis 6: Geographic Convergence**
- *Prediction*: Species from different continents but similar biomes have similar embeddings
- *Test*: Compare embedding distance vs geographic distance vs environmental distance
- *Expected result*: Environmental distance predicts embedding distance better than geographic distance

### B. Model Performance Metrics

For each of the 100 species, calculate:

1. **Discrimination Metrics**
   - AUC (Area Under ROC Curve): >0.7 = good, >0.8 = excellent
   - TSS (True Skill Statistic): >0.4 = good
   - Continuous Boyce Index: >0.5 = good

2. **Prediction Accuracy at Test Points**
   - Sensitivity (true positive rate at known presence locations)
   - Specificity (true negative rate at known absence locations)
   - Omission error rate at 30 strategic test points

3. **Environmental Niche Characterization**
   - Niche breadth (volume of convex hull in embedding space)
   - Niche position (centroid coordinates in 64 dimensions)
   - Niche overlap (Schoener's D) between congeners

4. **Spatial Prediction Accuracy**
   - Compare predicted distribution maps to:
     - Actual occurrence data (withheld 30%)
     - IUCN range maps (if available)
     - Expert range maps (e.g., Botanic Gardens data)

### C. Success Criteria

The pilot is successful if:

1. **>70% of species** achieve AUC > 0.7 on test data
2. **Specialists outperform generalists** (higher AUC, lower omission error)
3. **Phylogenetic signal detected** (K significantly > 0)
4. **Biome discrimination** achieves >75% accuracy
5. **Test point predictions** match known presence/absence >70% of time
6. **Intact forest species** cluster distinctly in embedding space (PERMANOVA p < 0.05)

### D. Failure Analysis

If success criteria not met, diagnose whether failure is due to:

1. **AlphaEarth embedding limitations**
   - Insufficient resolution (64 dimensions inadequate)
   - Missing key environmental variables (e.g., fire frequency, soil chemistry)
   - Temporal mismatch (embeddings don't capture seasonality)

2. **Occurrence data quality issues**
   - Sampling bias overwhelms environmental signal
   - Taxonomic errors (misidentified species)
   - Spatial precision errors (geohash L7 ~150m too coarse)

3. **Model architecture problems**
   - K-prototype clustering inappropriate
   - Need for non-linear decision boundaries
   - Insufficient training data for rare species

4. **Biological reality**
   - Dispersal limitation dominates (presence ≠ environmental suitability)
   - Biotic interactions critical (predators, competitors, mutualists)
   - Historical contingency (past climate, land bridges)

---

## 6. Implementation: SQL Queries for Species Selection

### Step 1: Create Candidate Pool

```sql
-- Filter species to those with good occurrence data and ecological metadata
CREATE TEMP TABLE candidate_species AS
WITH species_with_metadata AS (
  SELECT
    s.taxon_id,
    s.species_scientific_name,
    s.family,
    s.genus,
    s.present_intact_forest,
    s.ecoregions,
    s.biomes,
    s.countries_native,
    -- Calculate niche breadth
    CASE
      WHEN s.ecoregions = 'NA' OR s.ecoregions IS NULL THEN 0
      ELSE array_length(string_to_array(s.ecoregions, ','), 1)
    END as num_ecoregions,
    -- Calculate geographic breadth
    CASE
      WHEN s.countries_native = 'NA' OR s.countries_native IS NULL THEN 0
      ELSE array_length(string_to_array(s.countries_native, ','), 1)
    END as num_countries,
    -- Extract dominant biome
    CASE
      WHEN s.biomes LIKE '%Tropical & Subtropical Moist Broadleaf%' THEN 'Tropical Moist'
      WHEN s.biomes LIKE '%Temperate Broadleaf%' THEN 'Temperate Broadleaf'
      WHEN s.biomes LIKE '%Boreal%' THEN 'Boreal'
      WHEN s.biomes LIKE '%Tropical & Subtropical Dry%' THEN 'Tropical Dry'
      WHEN s.biomes LIKE '%Mediterranean%' THEN 'Mediterranean'
      WHEN s.biomes LIKE '%Montane Grasslands%' THEN 'Montane'
      WHEN s.biomes LIKE '%Mangroves%' THEN 'Mangroves'
      ELSE 'Other'
    END as dominant_biome,
    -- Count occurrence tiles (requires join - see next query)
    NULL::integer as tile_count
  FROM species s
  WHERE s.subspecies = 'NA'
    AND s.family IS NOT NULL
    AND s.ecoregions IS NOT NULL
    AND s.ecoregions != 'NA'
);

-- Add occurrence counts (slow query - run separately if needed)
UPDATE candidate_species cs
SET tile_count = (
  SELECT COUNT(*)
  FROM geohash_species_tiles g
  WHERE g.species_data ? cs.taxon_id
);

-- Filter to target occurrence range
DELETE FROM candidate_species
WHERE tile_count < 100 OR tile_count > 50000 OR tile_count IS NULL;

-- Add derived categories
ALTER TABLE candidate_species ADD COLUMN niche_breadth TEXT;
ALTER TABLE candidate_species ADD COLUMN forest_category TEXT;

UPDATE candidate_species
SET niche_breadth = CASE
  WHEN num_ecoregions <= 2 THEN 'specialist'
  WHEN num_ecoregions BETWEEN 3 AND 6 THEN 'moderate'
  WHEN num_ecoregions BETWEEN 7 AND 15 THEN 'generalist'
  ELSE 'widespread'
END;

UPDATE candidate_species
SET forest_category = CASE
  WHEN present_intact_forest = 'YES' THEN 'intact_only'
  WHEN present_intact_forest = 'NO' THEN 'disturbed_only'
  WHEN present_intact_forest IN ('NO;YES', 'YES;NO') THEN 'both'
  ELSE 'unknown'
END;

SELECT COUNT(*) as total_candidates FROM candidate_species;
```

### Step 2: Stratified Selection

```sql
-- Select species across multiple dimensions

-- DIMENSION 1: Biome representation (30 species)
CREATE TEMP TABLE selected_biome AS
(SELECT * FROM candidate_species WHERE dominant_biome = 'Tropical Moist' ORDER BY RANDOM() LIMIT 15)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Temperate Broadleaf' ORDER BY RANDOM() LIMIT 8)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Boreal' ORDER BY RANDOM() LIMIT 3)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Tropical Dry' ORDER BY RANDOM() LIMIT 4)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Mediterranean' ORDER BY RANDOM() LIMIT 3)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Montane' ORDER BY RANDOM() LIMIT 4)
UNION ALL
(SELECT * FROM candidate_species WHERE dominant_biome = 'Mangroves' ORDER BY RANDOM() LIMIT 3);

-- DIMENSION 2: Niche breadth (25 species, avoid overlap with biome selection)
CREATE TEMP TABLE selected_niche AS
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'specialist'
 ORDER BY RANDOM() LIMIT 10)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'moderate'
 ORDER BY RANDOM() LIMIT 10)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome)
   AND niche_breadth = 'generalist'
 ORDER BY RANDOM() LIMIT 5);

-- DIMENSION 3: Intact forest category (15 species)
CREATE TEMP TABLE selected_forest AS
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome UNION SELECT taxon_id FROM selected_niche)
   AND forest_category = 'intact_only'
 ORDER BY RANDOM() LIMIT 5)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome UNION SELECT taxon_id FROM selected_niche)
   AND forest_category = 'disturbed_only'
 ORDER BY RANDOM() LIMIT 5)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (SELECT taxon_id FROM selected_biome UNION SELECT taxon_id FROM selected_niche)
   AND forest_category = 'both'
 ORDER BY RANDOM() LIMIT 5);

-- DIMENSION 4: Phylogenetic diversity - select congeners
CREATE TEMP TABLE selected_phylo AS
-- Quercus (oaks)
(SELECT * FROM candidate_species WHERE genus = 'Quercus' ORDER BY tile_count DESC LIMIT 4)
UNION ALL
-- Pinus (pines)
(SELECT * FROM candidate_species WHERE genus = 'Pinus' ORDER BY tile_count DESC LIMIT 4)
UNION ALL
-- Eucalyptus
(SELECT * FROM candidate_species WHERE genus = 'Eucalyptus' ORDER BY tile_count DESC LIMIT 3)
UNION ALL
-- Ficus
(SELECT * FROM candidate_species WHERE genus = 'Ficus' ORDER BY tile_count DESC LIMIT 3)
UNION ALL
-- Acacia
(SELECT * FROM candidate_species WHERE genus = 'Acacia' ORDER BY tile_count DESC LIMIT 3)
UNION ALL
-- Other key genera (1 species each)
(SELECT * FROM candidate_species WHERE genus = 'Salix' ORDER BY tile_count DESC LIMIT 1)
UNION ALL
(SELECT * FROM candidate_species WHERE genus = 'Nothofagus' ORDER BY tile_count DESC LIMIT 1)
UNION ALL
(SELECT * FROM candidate_species WHERE genus = 'Dipterocarpus' ORDER BY tile_count DESC LIMIT 1);

-- DIMENSION 5: Occurrence data quality (10 species)
CREATE TEMP TABLE selected_occurrence AS
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (
   SELECT taxon_id FROM selected_biome UNION
   SELECT taxon_id FROM selected_niche UNION
   SELECT taxon_id FROM selected_forest UNION
   SELECT taxon_id FROM selected_phylo
 )
 AND tile_count BETWEEN 100 AND 500
 ORDER BY RANDOM() LIMIT 2)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (
   SELECT taxon_id FROM selected_biome UNION
   SELECT taxon_id FROM selected_niche UNION
   SELECT taxon_id FROM selected_forest UNION
   SELECT taxon_id FROM selected_phylo
 )
 AND tile_count BETWEEN 500 AND 5000
 ORDER BY RANDOM() LIMIT 4)
UNION ALL
(SELECT * FROM candidate_species
 WHERE taxon_id NOT IN (
   SELECT taxon_id FROM selected_biome UNION
   SELECT taxon_id FROM selected_niche UNION
   SELECT taxon_id FROM selected_forest UNION
   SELECT taxon_id FROM selected_phylo
 )
 AND tile_count BETWEEN 5000 AND 50000
 ORDER BY RANDOM() LIMIT 4);

-- FINAL SELECTION: Combine all dimensions
CREATE TABLE alphaearth_pilot_species AS
SELECT DISTINCT * FROM (
  SELECT *, 'biome' as selection_dimension FROM selected_biome
  UNION ALL
  SELECT *, 'niche' as selection_dimension FROM selected_niche
  UNION ALL
  SELECT *, 'forest' as selection_dimension FROM selected_forest
  UNION ALL
  SELECT *, 'phylo' as selection_dimension FROM selected_phylo
  UNION ALL
  SELECT *, 'occurrence' as selection_dimension FROM selected_occurrence
) combined
LIMIT 100;

-- Export final list
\copy (SELECT taxon_id, species_scientific_name, family, genus, dominant_biome, niche_breadth, forest_category, tile_count, selection_dimension FROM alphaearth_pilot_species ORDER BY family, species_scientific_name) TO '/tmp/alphaearth_pilot_species.csv' WITH CSV HEADER;
```

### Step 3: Extract Occurrence Data

```sql
-- For each selected species, extract geohash tiles and coordinates
CREATE TABLE alphaearth_occurrences AS
SELECT
  aps.taxon_id,
  aps.species_scientific_name,
  g.geohash_l7,
  ST_Y(g.center_point::geometry) as latitude,
  ST_X(g.center_point::geometry) as longitude,
  (g.species_data ->> aps.taxon_id)::integer as occurrence_count
FROM alphaearth_pilot_species aps
JOIN geohash_species_tiles g ON g.species_data ? aps.taxon_id;

-- Export occurrence data
\copy (SELECT * FROM alphaearth_occurrences ORDER BY taxon_id, geohash_l7) TO '/tmp/alphaearth_occurrences.csv' WITH CSV HEADER;
```

### Step 4: Define Test Points

```sql
-- Create test points table (manually curated for strategic locations)
CREATE TABLE alphaearth_test_points (
  point_id SERIAL PRIMARY KEY,
  point_name TEXT,
  category TEXT, -- 'gradient_extreme', 'ecotone', 'known_location'
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  description TEXT,
  environmental_notes TEXT
);

-- Example insertions (30 total, showing 10)
INSERT INTO alphaearth_test_points (point_name, category, latitude, longitude, description, environmental_notes) VALUES
('Yukon_Boreal', 'gradient_extreme', 64.0, -135.0, 'Coldest: Boreal Canada treeline', 'Mean annual temp -5C, short growing season'),
('Sahel_Dry', 'gradient_extreme', 13.0, 2.0, 'Hottest/driest: Sahel dry season', 'Mean annual temp 28C, <500mm precip'),
('Western_Ghats', 'gradient_extreme', 11.5, 76.0, 'Wettest: Western Ghats monsoon', '>7000mm annual rainfall'),
('Atacama_Fringe', 'gradient_extreme', -23.0, -68.0, 'Driest: Atacama desert fringe', '<50mm annual rainfall'),
('Andes_Treeline', 'gradient_extreme', -13.0, -72.0, 'Highest: Andean treeline', '3800m elevation, Polylepis forests'),
('Mangrove_Estuary', 'gradient_extreme', 10.0, -84.0, 'Sea level: Mangrove estuaries', 'Saltwater tolerance, tidal flooding'),
('Cerrado_Amazon', 'ecotone', -10.0, -52.0, 'Cerrado-Amazon transition', 'Savanna-forest mosaic, fire regime'),
('Cameroon_Ecotone', 'ecotone', 5.0, 11.0, 'Forest-savanna mosaic Central Africa', 'Guinea-Congolia boundary'),
('Canada_Transition', 'ecotone', 54.0, -105.0, 'Temperate-boreal transition', 'Mixed deciduous-conifer'),
('Madagascar_Central', 'known_location', -19.0, 47.0, 'Madagascar central highlands', 'High endemism, degraded forest');

-- Export test points
\copy (SELECT * FROM alphaearth_test_points ORDER BY category, point_id) TO '/tmp/alphaearth_test_points.csv' WITH CSV HEADER;
```

---

## 7. Python Implementation Workflow

### Step 1: Data Preparation

```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances
import geopandas as gpd

# Load selected species and occurrences
species_list = pd.read_csv('alphaearth_pilot_species.csv')
occurrences = pd.read_csv('alphaearth_occurrences.csv')
test_points = pd.read_csv('alphaearth_test_points.csv')

print(f"Selected {len(species_list)} species")
print(f"Total occurrences: {len(occurrences)}")
print(f"Test points: {len(test_points)}")
```

### Step 2: Spatial Thinning (Reduce Autocorrelation)

```python
from scipy.spatial import cKDTree

def spatial_thin(coords, min_distance_km=10):
    """
    Thin occurrence points to minimum distance threshold
    """
    # Convert lat/lon to approximate km (rough approximation)
    km_per_degree = 111.0
    coords_km = coords * km_per_degree

    # Build KD-tree for efficient nearest neighbor search
    tree = cKDTree(coords_km)

    # Greedy thinning: keep points that are >min_distance from all previously kept
    kept_indices = []
    remaining_indices = list(range(len(coords)))

    while remaining_indices:
        # Pick random point from remaining
        idx = np.random.choice(remaining_indices)
        kept_indices.append(idx)

        # Remove all points within min_distance
        neighbors = tree.query_ball_point(coords_km[idx], r=min_distance_km)
        remaining_indices = [i for i in remaining_indices if i not in neighbors]

    return kept_indices

# Apply thinning to each species
thinned_occurrences = []

for taxon_id in species_list['taxon_id']:
    species_occ = occurrences[occurrences['taxon_id'] == taxon_id]
    coords = species_occ[['latitude', 'longitude']].values

    if len(coords) > 100:  # Only thin if many points
        kept_idx = spatial_thin(coords, min_distance_km=10)
        species_occ_thinned = species_occ.iloc[kept_idx]
    else:
        species_occ_thinned = species_occ

    thinned_occurrences.append(species_occ_thinned)
    print(f"{taxon_id}: {len(coords)} → {len(species_occ_thinned)} points")

thinned_df = pd.concat(thinned_occurrences, ignore_index=True)
thinned_df.to_csv('alphaearth_occurrences_thinned.csv', index=False)
```

### Step 3: Extract AlphaEarth Embeddings (Google Earth Engine)

```python
import ee
ee.Initialize()

# This is pseudocode - actual AlphaEarth API calls depend on implementation
def extract_alphaearth_embeddings(lat, lon):
    """
    Extract 64-dimensional AlphaEarth embedding at given coordinates
    """
    # Query AlphaEarth image collection
    point = ee.Geometry.Point([lon, lat])

    # Get embedding values (64 bands)
    embedding_image = ee.ImageCollection('AlphaEarth_Embeddings').mosaic()
    embedding_values = embedding_image.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=30  # 30m resolution
    ).getInfo()

    # Return as numpy array
    return np.array([embedding_values[f'embedding_{i}'] for i in range(64)])

# Extract embeddings for all thinned occurrences
embeddings_list = []

for idx, row in thinned_df.iterrows():
    try:
        emb = extract_alphaearth_embeddings(row['latitude'], row['longitude'])
        embeddings_list.append({
            'taxon_id': row['taxon_id'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            **{f'emb_{i}': emb[i] for i in range(64)}
        })
    except Exception as e:
        print(f"Error at ({row['latitude']}, {row['longitude']}): {e}")

    if idx % 100 == 0:
        print(f"Processed {idx}/{len(thinned_df)} points")

embeddings_df = pd.DataFrame(embeddings_list)
embeddings_df.to_csv('alphaearth_embeddings.csv', index=False)
```

### Step 4: Build K-Prototype Models

```python
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import roc_auc_score, confusion_matrix

def build_species_model(species_embeddings):
    """
    Build k-prototype model for a single species
    Returns centroid and covariance for environmental niche
    """
    # Standardize embeddings
    scaler = StandardScaler()
    embeddings_scaled = scaler.fit_transform(species_embeddings)

    # Fit elliptic envelope (outlier-robust covariance)
    model = EllipticEnvelope(contamination=0.1)
    model.fit(embeddings_scaled)

    # Return centroid and decision function threshold
    centroid = embeddings_scaled.mean(axis=0)

    return {
        'scaler': scaler,
        'centroid': centroid,
        'model': model
    }

# Build models for all 100 species
species_models = {}

for taxon_id in species_list['taxon_id']:
    species_emb = embeddings_df[embeddings_df['taxon_id'] == taxon_id]
    emb_values = species_emb[[f'emb_{i}' for i in range(64)]].values

    if len(emb_values) >= 20:  # Minimum samples for model
        species_models[taxon_id] = build_species_model(emb_values)
    else:
        print(f"Insufficient data for {taxon_id}: {len(emb_values)} samples")

print(f"Built models for {len(species_models)} species")
```

### Step 5: Predict at Test Points

```python
# Extract embeddings at 30 test points
test_embeddings_list = []

for idx, row in test_points.iterrows():
    emb = extract_alphaearth_embeddings(row['latitude'], row['longitude'])
    test_embeddings_list.append({
        'point_id': row['point_id'],
        'point_name': row['point_name'],
        **{f'emb_{i}': emb[i] for i in range(64)}
    })

test_embeddings_df = pd.DataFrame(test_embeddings_list)

# Predict presence for each species at each test point
predictions = []

for taxon_id, model_dict in species_models.items():
    scaler = model_dict['scaler']
    model = model_dict['model']

    # Get test embeddings
    test_emb = test_embeddings_df[[f'emb_{i}' for i in range(64)]].values
    test_emb_scaled = scaler.transform(test_emb)

    # Predict (1 = inlier/suitable, -1 = outlier/unsuitable)
    predictions_species = model.predict(test_emb_scaled)
    decision_function = model.decision_function(test_emb_scaled)

    for point_id, pred, score in zip(test_embeddings_df['point_id'], predictions_species, decision_function):
        predictions.append({
            'taxon_id': taxon_id,
            'point_id': point_id,
            'predicted_presence': int(pred == 1),
            'suitability_score': score
        })

predictions_df = pd.DataFrame(predictions)
predictions_df.to_csv('alphaearth_predictions.csv', index=False)
```

### Step 6: Validation & Performance Metrics

```python
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, accuracy_score

# Cross-validation for each species
results = []

for taxon_id, model_dict in species_models.items():
    species_emb = embeddings_df[embeddings_df['taxon_id'] == taxon_id]
    emb_values = species_emb[[f'emb_{i}' for i in range(64)]].values

    # Generate pseudo-absences (background points from other species)
    other_species_emb = embeddings_df[embeddings_df['taxon_id'] != taxon_id]
    background_sample = other_species_emb.sample(n=len(emb_values))
    background_values = background_sample[[f'emb_{i}' for i in range(64)]].values

    # Combine presences and absences
    X = np.vstack([emb_values, background_values])
    y = np.hstack([np.ones(len(emb_values)), np.zeros(len(background_values))])

    # 5-fold cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc_scores = []

    for train_idx, test_idx in skf.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Re-fit model on training fold
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model = EllipticEnvelope(contamination=0.1)
        model.fit(X_train_scaled[y_train == 1])  # Fit only on presences

        # Predict on test fold
        y_pred_scores = model.decision_function(X_test_scaled)
        auc = roc_auc_score(y_test, y_pred_scores)
        auc_scores.append(auc)

    # Store results
    species_info = species_list[species_list['taxon_id'] == taxon_id].iloc[0]
    results.append({
        'taxon_id': taxon_id,
        'species': species_info['species_scientific_name'],
        'family': species_info['family'],
        'niche_breadth': species_info['niche_breadth'],
        'forest_category': species_info['forest_category'],
        'n_occurrences': len(emb_values),
        'mean_auc': np.mean(auc_scores),
        'std_auc': np.std(auc_scores)
    })

results_df = pd.DataFrame(results)
results_df.to_csv('alphaearth_performance_metrics.csv', index=False)

# Summary statistics
print(f"\nOverall Performance:")
print(f"Mean AUC: {results_df['mean_auc'].mean():.3f} ± {results_df['mean_auc'].std():.3f}")
print(f"Species with AUC > 0.7: {(results_df['mean_auc'] > 0.7).sum()}/100 ({(results_df['mean_auc'] > 0.7).mean()*100:.1f}%)")
print(f"\nBy Niche Breadth:")
print(results_df.groupby('niche_breadth')['mean_auc'].agg(['mean', 'std', 'count']))
```

---

## 8. Timeline & Resource Estimation

### Phase 1: Data Preparation (Week 1-2)
- Execute SQL queries to select 100 species ✓
- Export occurrence data from PostGIS database ✓
- Apply spatial thinning to reduce autocorrelation ✓
- Validate species selection against stratification criteria ✓

**Deliverables:**
- `alphaearth_pilot_species.csv` (100 species with metadata)
- `alphaearth_occurrences_thinned.csv` (spatially-thinned occurrences)
- `alphaearth_test_points.csv` (30 strategic test locations)

### Phase 2: Embedding Extraction (Week 3-4)
- Set up Google Earth Engine API access
- Extract AlphaEarth 64-dimensional embeddings for all occurrence points
- Extract embeddings for 30 test points
- Handle missing data and API errors

**Estimated API Calls:**
- ~50,000-200,000 occurrences (after thinning)
- ~30 test points
- Total: ~200,000 GEE requests

**Deliverables:**
- `alphaearth_embeddings.csv` (occurrence embeddings)
- `alphaearth_test_embeddings.csv` (test point embeddings)

### Phase 3: Model Building (Week 5)
- Build k-prototype models for each species
- Cross-validation within species
- Hyperparameter tuning (contamination rate, clustering method)
- Generate predicted distributions

**Deliverables:**
- `species_models.pkl` (pickled scikit-learn models)
- `alphaearth_predictions.csv` (predictions at test points)

### Phase 4: Validation & Analysis (Week 6-7)
- Calculate performance metrics (AUC, TSS, Boyce index)
- Hypothesis testing (PNC, biome discrimination, etc.)
- Compare performance across ecological categories
- Failure analysis for poorly-performing species

**Deliverables:**
- `alphaearth_performance_metrics.csv`
- `alphaearth_hypothesis_tests.csv`
- Visualizations (PCA plots, heatmaps, distribution maps)

### Phase 5: Reporting & Recommendations (Week 8)
- Write technical report
- Create presentation for stakeholders
- Recommend next steps (scale to more species, improve models, etc.)

**Deliverables:**
- Technical report (PDF)
- Jupyter notebook with full analysis
- Recommendations for production deployment

---

## 9. Risk Mitigation

### Technical Risks

**Risk 1: Google Earth Engine API rate limits**
- *Mitigation*: Batch requests, implement exponential backoff, cache embeddings
- *Fallback*: Use Planetary Computer or other cloud compute platforms

**Risk 2: AlphaEarth embeddings not available or incomplete**
- *Mitigation*: Validate embedding coverage before full extraction
- *Fallback*: Use alternative environmental layers (WorldClim, SoilGrids, MODIS)

**Risk 3: K-prototype clustering inappropriate for 64-dimensional space**
- *Mitigation*: Test alternatives (PCA → clustering, t-SNE, UMAP, autoencoders)
- *Fallback*: Use MaxEnt or Random Forest as baseline comparison

### Data Risks

**Risk 4: Occurrence data spatial bias overwhelms environmental signal**
- *Mitigation*: Aggressive spatial thinning, bias-file approach
- *Fallback*: Model sampling bias explicitly (target-group background)

**Risk 5: Taxonomic errors in Treekipedia database**
- *Mitigation*: Validate scientific names against GBIF backbone taxonomy
- *Fallback*: Exclude species with uncertain taxonomy

### Scientific Risks

**Risk 6: Environmental embeddings insufficient (missing key variables)**
- *Mitigation*: Compare to models using traditional environmental layers
- *Fallback*: Augment embeddings with additional layers (fire, soil nutrients, etc.)

**Risk 7: Dispersal limitation dominates (habitat suitable but species absent)**
- *Mitigation*: Interpret results as "habitat suitability" not "presence/absence"
- *Fallback*: Include dispersal kernels or range maps as constraints

---

## 10. Next Steps After Pilot

### If Successful (>70% species AUC > 0.7)

1. **Scale to Full Database**
   - Expand to 1,000+ species (all families represented)
   - Build species-distribution atlas

2. **Improve Model Architecture**
   - Test deep learning approaches (CNNs on embedding "images")
   - Incorporate phylogenetic priors (hierarchical models)

3. **Conservation Applications**
   - Predict climate refugia for threatened species
   - Identify priority areas for reforestation
   - Model assisted migration targets

4. **Real-time Monitoring**
   - Integrate with Treekipedia web platform
   - Provide species recommendations for land managers
   - Dynamic updates as new occurrence data arrives

### If Partially Successful (40-70% species)

1. **Diagnose Failure Modes**
   - Which species/families performed poorly?
   - Are failures correlated with niche breadth, biome, data quality?

2. **Hybrid Approach**
   - Combine AlphaEarth embeddings with traditional variables
   - Use embeddings as features in Random Forest models

3. **Targeted Improvements**
   - Focus on specific biomes (e.g., tropical forests only)
   - Develop custom embeddings for tree species

### If Unsuccessful (<40% species)

1. **Fundamental Re-evaluation**
   - Are environmental variables sufficient for predicting tree distributions?
   - Does AlphaEarth capture relevant environmental gradients?

2. **Alternative Approaches**
   - Joint species distribution models (incorporate co-occurrence)
   - Process-based models (mechanistic understanding of tree physiology)
   - Ensemble approaches (combine multiple data sources)

3. **Publication of Negative Results**
   - Document limitations for scientific community
   - Identify gaps in environmental data products

---

## 11. Conclusion

This strategic plan provides a rigorous, scientifically-grounded framework for testing AlphaEarth environmental embeddings on tree species distributions. By using **ecological stratification** rather than random or convenience sampling, we create a designed experiment that:

1. **Maximizes scientific insight** across multiple ecological dimensions
2. **Enables hypothesis testing** (phylogenetic niche conservatism, biome discrimination, etc.)
3. **Balances data quality** (avoids sparse data and computational limits)
4. **Ensures reproducibility** (SQL queries, Python code fully documented)
5. **Provides actionable results** (clear success criteria, next steps defined)

The 100 selected species will serve as a benchmark dataset for evaluating not just AlphaEarth embeddings, but any environmental data product aimed at predicting species distributions. The strategic test points will enable validation in diverse ecological contexts, from tropical rainforests to boreal taiga.

**Key Innovation:** This is not just a "pick the species with the most data" approach. It is a carefully designed experiment that treats species selection as a stratified sampling problem across multiple ecological, phylogenetic, and geographic dimensions. This approach ensures the pilot results will be generalizable and scientifically meaningful.

---

## Appendices

### Appendix A: Key References

1. Aiello-Lammens et al. (2015). "spThin: an R package for spatial thinning of species occurrence records." *Ecography* 38(5): 541-545.

2. Barbet-Massin et al. (2012). "Selecting pseudo-absences for species distribution models: how, where and how many?" *Methods in Ecology and Evolution* 3(2): 327-338.

3. Dormann et al. (2007). "Methods to account for spatial autocorrelation in the analysis of species distributional data: a review." *Ecography* 30(5): 609-628.

4. Steen et al. (2021). "Spatial thinning and class balancing: Key choices lead to variation in the performance of species distribution models with citizen science data." *Methods in Ecology and Evolution* 12(2): 216-226.

5. Velazco et al. (2021). "Evaluation metrics and validation of presence-only species distribution models based on distributional maps with varying coverage." *Scientific Reports* 11: 1459.

6. Vollering et al. (2019). "Is geographic sampling bias representative of environmental space?" *Ecological Applications* 29(7): e01997.

7. Warren & Seifert (2011). "Ecological niche modeling in Maxent: the importance of model complexity and the performance of model selection criteria." *Ecological Applications* 21(2): 335-342.

### Appendix B: Glossary

- **AlphaEarth Embeddings**: 64-dimensional environmental representations extracted from satellite imagery and environmental data
- **AUC (Area Under ROC Curve)**: Discrimination metric, >0.7 = good, >0.8 = excellent
- **Geohash Level 7**: Geographic hash code with ~150m × 150m spatial precision
- **K-prototype**: Clustering algorithm for mixed categorical and continuous data
- **MaxEnt**: Maximum Entropy species distribution modeling algorithm
- **Niche Breadth**: Number of distinct ecoregions a species occupies
- **PNC (Phylogenetic Niche Conservatism)**: Tendency for related species to occupy similar environmental niches
- **Spatial Thinning**: Removing clustered occurrence points to reduce spatial autocorrelation
- **TSS (True Skill Statistic)**: Threshold-independent performance metric for presence/absence models

### Appendix C: Contact & Collaboration

For questions, collaborations, or access to pilot data:
- **Project Repository**: [Link to GitHub/GitLab]
- **Data Portal**: [Link to Treekipedia API]
- **Principal Investigator**: [Contact information]

---

**Document Version History:**
- v1.0 (2025-10-27): Initial strategic plan created by Research Agent
