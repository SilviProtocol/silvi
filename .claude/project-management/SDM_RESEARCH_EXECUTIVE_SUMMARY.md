# SDM Research: Executive Summary & Action Items

**Date**: January 21, 2026
**Full Report**: [SDM_INSTITUTIONAL_RESEARCH.md](./SDM_INSTITUTIONAL_RESEARCH.md)

---

## What We Learned (60-Second Version)

The world's leading organizations (NASA, ESA, eBird, Map of Life, NatureServe) are converging on **7 critical trends** for species distribution modeling in 2025-2026:

1. **Uncertainty quantification** - Now mandatory, not optional
2. **Ensemble methods** - Random Forest + MaxEnt + BART outperform single algorithms
3. **Explainable AI** - SHAP for interpreting black-box predictions
4. **Data-deficient species** - Phylogenetic borrowing from related species
5. **Temporal forecasting** - Moving beyond static snapshots
6. **Multi-modal integration** - Remote sensing + occurrence + traits + phylogeny
7. **STAC compliance** - Geospatial data standardization (we already have this ✅)

**Treekipedia's Unique Advantage**: 10m AlphaEarth resolution (3-100× finer than industry), blockchain verification, tree species specialization, and 48,129 species with occurrence data.

**Critical Gap**: We lack uncertainty quantification, ensemble methods, and validation framework. These are **table stakes** for scientific credibility in 2025+.

---

## Top 5 Competitors and What They Do Better

| Organization | Their Strength | Our Gap | Priority |
|--------------|----------------|---------|----------|
| **eBird (Cornell)** | Weekly temporal predictions, 2,974 species | No temporal dimension | MEDIUM |
| **Map of Life (Yale)** | 1km global coverage, all taxa | Point-only predictions | HIGH |
| **NatureServe** | Human-AI collaboration, expert review | Pure algorithmic, no expert validation | MEDIUM |
| **NASA/ESA** | Uncertainty quantification, ensemble methods | Single method (cosine similarity) | **CRITICAL** |
| **All of the above** | Validation frameworks, published methodologies | No validation, no paper | **CRITICAL** |

---

## What We Do Better Than Anyone

1. **10m resolution** - eBird/Map of Life use 1km, NatureServe uses 30m → We're 3-100× finer
2. **Tree species specialization** - 48,129 species with occurrence data vs. generalist platforms
3. **Blockchain verification** - EAS attestations + NFT provenance (nobody else has this)
4. **Native status integration** - WCVP 99.99% coverage + LEAF scoring for restoration
5. **Community incentive model** - Sustainable data improvement via crypto rewards

---

## Critical Improvements (Prioritized)

### Phase 1: Scientific Foundation (16 weeks) - **START IMMEDIATELY**

**Why**: Without these, we're not competitive with 2025+ standards.

| Task | Duration | Impact | Effort |
|------|----------|--------|--------|
| **1. Uncertainty Quantification** | 4 weeks | Credibility, publication-ready | 1 FTE |
| **2. Ensemble Methods** (RF + MaxEnt + Cosine) | 6 weeks | More robust predictions | 1.5 FTE |
| **3. Validation Framework** | 4 weeks | Trust, transparency | 1 FTE |
| **4. Explainable AI (SHAP)** | 4 weeks | User trust, interpretability | 1 FTE |

**Deliverables**:
- Scientific paper draft
- Validation report with TSS/AUC metrics
- Enhanced API with confidence intervals
- "Why this prediction?" UI component

---

### Phase 2: Coverage Expansion (12 weeks)

**Why**: Handle all 67,743 species, not just 48,129 with embeddings.

| Task | Duration | Impact | Effort |
|------|----------|--------|--------|
| **5. Phylogenetic Borrowing** | 6 weeks | Extend to data-deficient species | 1.5 FTE |
| **6. Climate Analogue Matching** | 6 weeks | Cover all species in database | 1.5 FTE |

**Deliverables**:
- 67,743 species coverage (from 48,129)
- Lower confidence for inferred species (transparent)

---

### Phase 3: Spatial Features (16 weeks)

**Why**: Restoration planning requires landscape-scale analysis.

| Task | Duration | Impact | Effort |
|------|----------|--------|--------|
| **7. Polygon/AOI Support** | 8 weeks | Landscape-scale predictions | 2 FTE |
| **8. Spatial Analysis Tools** | 8 weeks | Species richness, restoration suitability | 2 FTE |

**Deliverables**:
- Predictions for areas up to 1000 km²
- KML/GeoJSON upload
- Species richness heatmaps

---

### Phase 4: Temporal Analysis (20 weeks)

**Why**: "What used to grow here?" and "What will grow in 2050?" are high-value questions.

| Task | Duration | Impact | Effort |
|------|----------|--------|--------|
| **9. Historical Analysis (1985-2024)** | 10 weeks | Predict pre-deforestation species | 2 FTE |
| **10. Climate Forecasting** | 10 weeks | Range shift predictions | 2 FTE |

**Deliverables**:
- Forest loss year detection (Hansen dataset)
- 2050/2100 suitability projections
- Climate adaptation planning tool

---

## Algorithm Comparison: What Works Best (2025-2026 Research)

Based on comparative studies of 2,299 species (January 2026):

| Method | Performance | Best For | Treekipedia Status |
|--------|-------------|----------|-------------------|
| **BART** (Bayesian) | ⭐⭐⭐⭐⭐ Slight edge | Uncertainty quantification | ❌ Not implemented |
| **Random Forest** | ⭐⭐⭐⭐⭐ Best for 87% of species | General purpose | ❌ Not implemented |
| **Ensemble** (RF + MaxEnt + BART) | ⭐⭐⭐⭐⭐ Gold standard | All scenarios | ❌ Not implemented |
| **MaxEnt** | ⭐⭐⭐⭐ Competitive | Traditional SDM | ❌ Not implemented |
| **Cosine Similarity** | ⭐⭐⭐ Good | Environmental matching | ✅ **Current method** |
| **Deep Learning** | ⭐⭐⭐ Does NOT outperform classical | Data-rich scenarios | ❌ Not needed |

**Recommendation**: Add Random Forest + BART to existing cosine similarity → Create ensemble weighted by cross-validation.

---

## Key Research Findings: Uncertainty Quantification

**Finding**: Uncertainty quantification is **mandatory** in 2025+ SDM research, not optional.

**Methods Used by Leaders**:

1. **Bayesian Approaches (BART)**:
   - Provides prediction intervals automatically
   - Dramatically faster than bootstrap
   - Used by NASA for marine species

2. **Ensemble Variance**:
   - Multiple models → variance across predictions
   - Shows method-choice uncertainty

3. **Gold Standard** (Science Advances, 2018):
   - Full exploration of modeling choices
   - Quantifies variability from data + methods
   - Required for climate change projections

**Current Treekipedia**: ❌ Single-point predictions with no confidence intervals

**Action**: Implement BART or ensemble-based uncertainty in Phase 1

---

## Key Research Findings: Data-Deficient Species

**Challenge**: 19,614 Treekipedia species lack occurrence data (mostly subspecies).

**Solutions from Research (2025)**:

1. **"Borrowing Strength"** (June 2025):
   - Use data-rich species to improve data-deficient predictions
   - Incorporate traits + phylogenies
   - Multi-species joint models

2. **CISO Deep Learning** (August 2025):
   - Conditions on incomplete observations
   - Handles sparse + heterogeneous data

3. **CORAL Transfer Learning** (September 2025):
   - Joint modeling of millions of species
   - Improves rare species predictions

**Action**: Implement phylogenetic borrowing in Phase 2 to cover all 67,743 species

---

## Key Research Findings: Explainability

**Problem**: Black-box models (Random Forest, Neural Networks) lack interpretability.

**Solution**: **SHAP (Shapley Additive Explanations)** - consistently best performer across studies.

**Benefits**:
- Shows which environmental factors drive each prediction
- Reveals nonlinear relationships
- Critical for policymaker trust

**Example Output**:
```
Species: Araucaria angustifolia
Prediction: 0.89 suitability

Why?
- Temperature range: +0.35 (strong positive)
- Elevation: +0.25 (matches known habitat)
- Precipitation: +0.15 (sufficient)
- Native status: +0.14 (native to region)
```

**Action**: Integrate SHAP in Phase 1 for "Why this prediction?" feature

---

## Competitive Positioning

### Current Positioning (Weak)
"Tree species predictor using satellite data"

### Recommended Positioning (Strong)
**Primary**: "The world's most precise tree species predictor for restoration ecology"

**Secondary**: "Blockchain-verified ecological intelligence at field scale"

**Unique Value Props**:
1. 10m resolution (3-100× finer than competitors)
2. Blockchain-verified data provenance
3. Tree species specialization (not generalist)
4. Restoration-ready (native status + LEAF scores)
5. Community-driven (sustainable data improvement)

---

## Timeline and Resource Requirements

**Total Duration**: 64 weeks (~15 months)
**Concurrent Team**: 2-3 full-time developers

| Phase | Weeks | FTE | Priority | Start |
|-------|-------|-----|----------|-------|
| Phase 1: Scientific Foundation | 16 | 2 | **CRITICAL** | **Immediately** |
| Phase 2: Coverage Expansion | 12 | 1.5 | **HIGH** | Week 17 |
| Phase 3: Spatial Features | 16 | 2 | **HIGH** | Week 29 |
| Phase 4: Temporal Analysis | 20 | 2 | MEDIUM | Week 45 |

**Critical Path**: Phase 1 must complete before publication/external validation possible.

---

## Success Metrics

### Phase 1 Success Criteria (Week 16)
- [ ] Uncertainty quantification for all predictions
- [ ] Ensemble methods outperform single method by >15%
- [ ] Validation framework: TSS >0.7, AUC >0.8 for top 500 species
- [ ] SHAP explanations for all predictions
- [ ] Draft methodology paper ready for submission

### Phase 2 Success Criteria (Week 28)
- [ ] Coverage: 67,743 species (up from 48,129)
- [ ] Phylogenetic borrowing tested on 1,000 data-deficient species
- [ ] Confidence levels correctly calibrated (lower for inferred species)

### Phase 3 Success Criteria (Week 44)
- [ ] Polygon predictions work for areas <1000 km²
- [ ] Response time <60 seconds for landscape-scale queries
- [ ] Species richness heatmaps validated against known hotspots

### Phase 4 Success Criteria (Week 64)
- [ ] Historical analysis for post-1985 deforestation
- [ ] Climate forecasting for 2050/2100
- [ ] Validation against known restoration sites

---

## Decision Points

### Should We Prioritize Phase 1 Now?

**YES** - Here's why:

1. **Scientific Credibility**: Without uncertainty quantification + validation, we can't publish or get institutional adoption.

2. **Competitive Necessity**: eBird, Map of Life, NatureServe all have these features. We're behind 2025+ standards.

3. **User Trust**: Showing confidence intervals + explanations ("why this prediction?") builds trust.

4. **Foundation for Future**: Phases 2-4 build on Phase 1 infrastructure.

**Recommendation**: Allocate 2 FTE for 16 weeks starting immediately.

---

### Should We Use Deep Learning?

**NO** - Here's why:

**Research Finding** (January 2026, 2,299 species study):
- Deep learning **does NOT outperform** classical methods on average
- **Weaker** for narrow ranges, few data points, threatened species
- Random Forest + BART outperform CNNs/MLPs

**Exception**: Only use DL if:
- We have >100 occurrence records per species
- Wide geographic ranges
- Need image-based habitat classification (not species prediction)

**Recommendation**: Stick with ensemble of Random Forest + BART + Cosine Similarity.

---

### Should We Build Our Own Foundation Model?

**NO** - Here's why:

**Research Finding**: AlphaEarth (Google/DeepMind) is:
- 10m resolution (finest available)
- 64-D embeddings (efficient)
- 2017-2024 coverage (sufficient for current predictions)
- Free via Google Earth Engine

**Building our own would require**:
- Petabyte-scale compute
- Years of development
- Minimal differentiation vs. AlphaEarth

**Recommendation**: Continue using AlphaEarth. Differentiate on:
- Species-level predictions (not foundation model)
- Restoration intelligence (native status, LEAF scores)
- Blockchain verification
- Tree species specialization

---

## Next Steps (Immediate Actions)

### Week 1-2: Planning
1. Review full research report: [SDM_INSTITUTIONAL_RESEARCH.md](./SDM_INSTITUTIONAL_RESEARCH.md)
2. Approve Phase 1 scope and budget
3. Assign 2 FTE developers
4. Set up project tracking

### Week 3-6: Uncertainty Quantification
1. Research BART implementation (Python `bartpy` or `scikit-learn` surrogate)
2. Adapt to AlphaEarth embedding space
3. Integrate with existing cosine similarity endpoint
4. Add `confidence_interval` field to API response

### Week 7-12: Ensemble Methods
1. Implement Random Forest on occurrence data + environmental variables
2. Implement MaxEnt (or use `maxnet` R package via API)
3. Weight ensemble by 5-fold spatial cross-validation
4. A/B test vs. current single-method approach

### Week 13-16: Validation + Explainability
1. Create 80/20 spatial block train/test split
2. Calculate TSS, AUC, partial ROC for all species with >20 occurrences
3. Integrate SHAP for feature importance
4. Build "Why this prediction?" UI component
5. Draft methodology paper

---

## References

See full research report for 50+ sources: [SDM_INSTITUTIONAL_RESEARCH.md](./SDM_INSTITUTIONAL_RESEARCH.md)

**Key Papers** (2025-2026):
- [Deep Learning Performance for SDMs](https://onlinelibrary.wiley.com/doi/10.1111/geb.70184) - January 2026
- [Uncertainty Quantification](https://besjournals.onlinelibrary.wiley.com/doi/full/10.1111/2041-210X.14505) - 2025
- [Data-Deficient Species](https://www.sciencedirect.com/science/article/pii/S0169534725000990) - June 2025
- [Explainable AI for SDMs](https://nsojournals.onlinelibrary.wiley.com/doi/full/10.1111/ecog.05360) - 2021 (still current)

---

**Document Version**: 1.0
**Last Updated**: January 21, 2026
**Next Review**: Weekly during Phase 1 implementation
