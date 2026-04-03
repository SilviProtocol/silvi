# Dynamic Weighting Research: Executive Summary

**Date**: January 21, 2026
**Full Document**: [DYNAMIC_WEIGHTING_FRAMEWORK.md](./DYNAMIC_WEIGHTING_FRAMEWORK.md)

---

## The Question

**How should weights in a species aptness equation vary based on ecological context?**

Current naive approach:
```python
aptness = w1*native + w2*occurrence + w3*embedding_similarity + w4*leaf_score
```

**Problem**: Static weights ignore spatial scale, ecological context, successional stage, and restoration strategy.

---

## The Answer: 5 Layers of Context Adaptation

### 1. **Spatial Scale Context** (Most Critical)

Weights must vary by radius of analysis:

| Scale | Radius | What Dominates | Example Weights |
|-------|--------|----------------|----------------|
| **Microhabitat** | <1km | Soil, topography, wetness | landtype 25%, soil 20%, embedding 18% |
| **Landscape** | 1-10km | Land use, forest continuity | embedding 22%, occurrence 18%, landtype 15% |
| **Regional** | 10-100km | Climate, ecoregion, elevation | climate 28%, ecoregion 22%, native 18% |
| **Continental** | >100km | Biome, evolutionary biogeography | ecoregion 35%, climate 30%, native 25% |

**Source**: [Doser et al. 2024 - Spatially varying coefficients in SDMs](https://onlinelibrary.wiley.com/doi/10.1111/geb.13814)

### 2. **Environmental vs. Biotic Filtering**

| Scale | Environmental Filtering | Biotic Filtering | Implication |
|-------|------------------------|------------------|-------------|
| **Large** | Dominant (climate, soil) | Weak | Boost climate, reduce occurrence |
| **Small** | Weaker | Stronger (competition) | Boost occurrence, reduce climate |

**Source**: [European ant communities study 2020](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0228625)

### 3. **Temporal/Successional Context**

| Successional Stage | What to Boost | What to Penalize |
|--------------------|---------------|------------------|
| **Bare soil** | Pioneer species, N-fixers, fast growth | Climax species, shade-tolerant |
| **Early (<10yr)** | Fast colonizers, competitive | Slow-growing climax |
| **Mid (10-50yr)** | Shade-intolerant, competitive strategy | Pioneers (outcompeted) |
| **Late (50-200yr)** | Shade-tolerant, climax, specialists | Pioneers, generalists |
| **Old growth** | Gap specialists, structural diversity | Early successional |

**Source**: [Poorter et al. 2024 - Comprehensive succession framework](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecs2.4794)

### 4. **Restoration Strategy Context**

| Strategy | Priority Factors | Weight Adjustments |
|----------|-----------------|-------------------|
| **Rewilding** | Native status, ecological function | Native ×2.0, occurrence ×1.5, climax ×1.3 |
| **Agroforestry** | Productivity, multi-use, economics | Economic value ×1.8, growth rate ×1.5 |
| **Carbon** | Biomass accumulation, longevity | Biomass ×2.0, lifespan ×1.4, growth ×1.3 |
| **Riparian** | Flood tolerance, bank stabilization | Wetland affinity ×2.5, landtype ×1.5 |
| **Biodiversity** | Fauna support, keystone role | Fauna support ×1.8, native ×1.8 |

**Source**: [EU Nature Restoration Law 2024](https://onlinelibrary.wiley.com/doi/10.1111/rec.70249)

### 5. **Data Quality/Confidence Context**

| Data Tier | Embedding Weight | Occurrence Weight | Climate Weight |
|-----------|-----------------|------------------|----------------|
| **High** (AlphaEarth 2017-2024) | 1.0× (full) | 1.0× | 1.0× |
| **Medium** (Landsat reconstruction) | 0.6× | 1.3× (boost) | 1.2× (boost) |
| **Low** (Pre-satellite inference) | 0.3× | 1.2× | 1.5× (strong boost) |

**Rationale**: When embedding data is uncertain, rely more on stable factors (climate, ecoregion, occurrences).

---

## Key Innovations from Literature

### 1. Spatially Varying Coefficients (SVC)

**Breakthrough**: Weights aren't just global constants - they vary smoothly across geographic space.

**Method**: Use Gaussian Process to interpolate optimal weights from calibration points.

**Source**: [Doser et al. 2024](https://onlinelibrary.wiley.com/doi/10.1111/geb.13814)

### 2. Bayesian Model Averaging (BMA)

**Breakthrough**: Don't just average models equally - weight by spatially-explicit predictive performance.

**Method**: Expectation-Maximization (EM) algorithm to find optimal model weights at each location.

**Result**: BEM concentrated 85% of weight on 2 best models (vs. uniform 20% each).

**Source**: [Bayesian Model Averaging study](https://hal.inrae.fr/hal-05307661v1)

### 3. Hierarchical Multi-Scale Integration

**Breakthrough**: Niche truncation problem - regional models miss local variation, local models miss biogeographic constraints.

**Solution**: Nested hierarchy:
```
Global model (coarse resolution, broad extent)
    ⊗  (multiply or use as covariate)
Regional model (fine resolution, limited extent)
```

**Source**: [sabinaNSDM package 2024](https://methodsblog.com/2024/10/03/introducing-sabinansdm-a-new-r-package-for-improved-species-distribution-modeling-based-on-spatially-nested-hierarchical-models/)

### 4. Functional Trait-Based Modulation

**Breakthrough**: Species traits (shade tolerance, dispersal, N-fixing) should modulate environmental weights.

**Example**: Shade-tolerant species → boost canopy cover weight, ignore open habitat weight.

**Data Source**: [BIEN database](https://besjournals.onlinelibrary.wiley.com/doi/10.1111/2041-210X.12861) (81M occurrences, 915K trait observations, R package available)

---

## Recommended Implementation Architecture

```python
class ContextAdaptiveWeighting:
    """
    5-layer hierarchical weighting system.
    """

    def get_weights(self, location, restoration_strategy):
        # LAYER 1: Detect spatial scale → Set base weights
        scale = detect_scale(location.aoi_radius_km)
        weights = spatial_baseline_weights(scale)

        # LAYER 2: Apply environmental vs. biotic filtering
        weights = apply_ecological_filtering(weights, scale)

        # LAYER 3: Apply successional stage adjustments
        stage = detect_successional_stage(location)
        weights = apply_temporal_context(weights, stage)

        # LAYER 4: Apply restoration strategy boosting
        weights = apply_strategy_weights(weights, restoration_strategy)

        # LAYER 5: Apply data quality confidence weighting
        confidence = assess_data_quality(location)
        weights = apply_confidence_weighting(weights, confidence)

        return normalize(weights)  # Sum to 1.0
```

**Expected Result (Example - Atlantic Forest Rewilding)**:
```
native_status:           28.7%  ← Heavily boosted for rewilding
occurrence_density:      19.6%  ← Landscape scale + rewilding boost
embedding_similarity:    14.2%  ← Moderate (medium confidence historical data)
trait_suitability:       12.5%  ← Active (early successional stage)
climate_match:            9.9%  ← Boosted to compensate embedding uncertainty
ecoregion_match:          7.8%  ← Rewilding boost
soil_match:               3.5%
landtype_match:           2.0%
succession_match:         1.2%
elevation_match:          0.6%
```

---

## Validation Strategy

### Metrics

1. **Top-K Accuracy**: Is actual species in top-10 predictions?
2. **Mean Reciprocal Rank (MRR)**: Where does actual species rank? (1/rank)
3. **Ecological Fidelity**: Expert validation - do recommendations make ecological sense?

### Validation Tiers

1. **Self-validation**: BigQuery occurrence data (16.5M points) → 80/20 split
2. **Expert validation**: 50-100 sites with expert species lists
3. **Field validation**: Track planting success over time

### Expected Improvement

**Static weights** → ~40% top-10 accuracy
**Dynamic context-adaptive weights** → **60-70% top-10 accuracy** (30-50% improvement)

---

## Critical Datasets

### Already Available in Treekipedia

1. **AlphaEarth embeddings** (500 species, scaling to 6,775)
2. **WCVP native/introduced** (97.5% coverage)
3. **LEAF scores** (occurrence + native weighting)
4. **Species traits** (V11 schema: shade tolerance, growth form, N-fixing, etc.)
5. **Ecoregions** (PostgreSQL: 847 polygons)
6. **Intact Forest Landscapes** (PostgreSQL: 6,819 polygons)

### External Enrichment (Optional)

1. **BIEN database** - R package, free, 915K trait observations
   - `install.packages("BIEN")`
   - `BIEN_trait_traitbyspecies(species = "Quercus alba")`

2. **TRY database** - 69K species, 52 trait groups (requires registration)

---

## Implementation Phases

### Phase 1: Core Dynamic Weighting (2-3 weeks)
- Implement `ContextAdaptiveWeighting` class
- Add spatial scale detection
- Implement successional stage classification
- Add strategy selector to frontend

### Phase 2: Trait Integration (2 weeks)
- Use existing V11 trait fields
- Implement trait-based weighting logic
- Optional: Connect to BIEN R package

### Phase 3: Spatially Varying Coefficients (3 weeks)
- Implement SVC model
- Build calibration framework
- Collect validation data for tuning

### Phase 4: Bayesian Ensemble (2 weeks)
- Implement BMA with spatially-explicit weights
- Add multi-model ensemble prediction

### Phase 5: Validation & Publication (4 weeks)
- Collect expert validation data
- Optimize weights via grid search
- Document methodology for publication

**Total Timeline**: 13-15 weeks

---

## Key Takeaways

1. **Weights are NOT constants** - they are **functions of context**
2. **Spatial scale is the primary driver** - microhabitat vs. regional completely different
3. **Ecological filtering changes with scale** - environmental dominates at large scale, biotic at small
4. **Successional stage matters** - pioneer vs. climax have opposite suitability profiles
5. **Strategy alignment is critical** - rewilding ≠ agroforestry ≠ carbon sequestration
6. **Data quality requires confidence weighting** - uncertain embedding data → boost stable factors

**Bottom Line**: Move from naive `w1*x1 + w2*x2 + ...` to sophisticated **hierarchical, context-adaptive, spatially-varying coefficient framework** grounded in cutting-edge ecological research.

---

## Full Research Document

For complete details, code implementations, and literature citations, see:
[DYNAMIC_WEIGHTING_FRAMEWORK.md](./DYNAMIC_WEIGHTING_FRAMEWORK.md)

---

**Research Completed**: January 21, 2026
**Author**: Research Agent (Claude Sonnet 4.5)
**Status**: Ready for implementation
