# SDM Competitive Analysis Matrix

**Date**: January 21, 2026
**Purpose**: Quick reference for how Treekipedia compares to major SDM platforms

---

## Feature Comparison Matrix

| Feature | Treekipedia (Current) | eBird (Cornell) | Map of Life (Yale) | NatureServe | NASA/ESA | BioDT |
|---------|----------------------|-----------------|-------------------|-------------|----------|-------|
| **Resolution** | **10m** ✅ | 1km | 1km | 30m | 30m-500m | 300m |
| **Tree Species Coverage** | **48,129** ✅ | 0 (birds only) | 46,000 (mixed) | Limited | N/A | N/A |
| **Total Occurrence Records** | **5.7M geohash tiles** | 1.6B+ (birds) | Millions | Rare/endangered only | N/A | N/A |
| **Temporal Predictions** | ❌ Static | ✅ Weekly (52/year) | ❌ Static | ❌ Static | ✅ Seasonal forecasts | ✅ Scenario forecasting |
| **Uncertainty Quantification** | ❌ None | ✅ Full | ⚠️ Partial | ⚠️ Partial | ✅ Gold standard | ✅ Full |
| **Ensemble Methods** | ❌ Single (cosine) | ✅ GAMs + ML | ✅ Multiple | ✅ GIS + AI | ✅ Multiple | ✅ Multiple |
| **Validation Framework** | ❌ None | ✅ Temporal validation | ✅ Independent test sets | ✅ Expert review | ✅ Gold standard | ✅ Scenario validation |
| **Explainable AI** | ❌ None | ⚠️ Partial | ❌ None | ✅ Expert integration | ⚠️ Partial | ⚠️ Partial |
| **Polygon/AOI Support** | ❌ Point-only | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Native Status Data** | ✅ **WCVP 99.99%** | N/A | ⚠️ Partial | ✅ Full (US/Canada) | N/A | N/A |
| **Blockchain Verification** | ✅ **EAS + NFTs** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **API Access** | ✅ REST | ✅ REST + R/Python | ✅ REST | ✅ REST | ✅ GEE + REST | ⚠️ Research-only |
| **Open Source** | ✅ Full | ⚠️ Partial | ⚠️ Partial | ❌ Proprietary | ⚠️ Data only | ⚠️ Research project |
| **Community Incentives** | ✅ **Crypto rewards** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **Historical Analysis** | ❌ 2017-2024 only | ⚠️ Since 2000 | ❌ Current only | ❌ Current only | ✅ 1985+ (Landsat) | ⚠️ Limited |
| **Climate Forecasting** | ❌ None | ❌ None | ❌ None | ❌ None | ✅ Full | ✅ Full |

**Legend**:
- ✅ Implemented and strong
- ⚠️ Partial or limited
- ❌ Not available
- N/A Not applicable

---

## Strengths vs. Weaknesses Grid

### Treekipedia's Unique Strengths (✅)

1. **10m resolution** - Finest globally (3-100× better than competitors)
2. **Tree species specialization** - 48,129 species with geohashes
3. **Blockchain verification** - EAS attestations + NFT provenance (nobody else)
4. **Native status integration** - WCVP 99.99% coverage
5. **Community incentive model** - Sustainable data improvement via crypto
6. **STAC compliance** - Already implemented for geospatial data
7. **LEAF scoring** - Ecological weighting for restoration

### Critical Gaps vs. Industry Standard (❌)

1. **Uncertainty quantification** - All leaders have this, we don't
2. **Ensemble methods** - Single algorithm (cosine) vs. multi-method ensembles
3. **Validation framework** - No independent test sets or published metrics
4. **Explainable AI** - No SHAP or feature importance
5. **Polygon/AOI support** - Point-only vs. landscape-scale
6. **Temporal predictions** - Static vs. weekly/seasonal/forecasted
7. **Historical analysis** - Only 2017-2024 vs. 1985+ Landsat archives

---

## Methodology Comparison

### Treekipedia (Current)

**Algorithm**: Cosine similarity in AlphaEarth embedding space
```
User click → Sample AlphaEarth → Cosine vs. centroids → Top 10
```

**Strengths**:
- Simple, fast
- Leverages state-of-the-art embeddings
- Computationally efficient

**Weaknesses**:
- No uncertainty
- No ensemble
- No validation metrics

---

### eBird (Cornell) - State of the Art

**Algorithm**: Generalized Additive Models (GAMs) + machine learning
```
Citizen science + satellite → GAM ensemble → Weekly predictions → Temporal validation
```

**Strengths**:
- Temporal dynamics (52 weeks/year)
- Accounts for observer skill
- Validated against future data
- 2,974 species coverage (2025)

**Weaknesses**:
- Birds only (not trees)
- 1km resolution (100× coarser than Treekipedia)

---

### Map of Life (Yale)

**Algorithm**: Multi-source integration (expert ranges + occurrences + models)
```
Expert maps + occurrence points + environmental → SDMs → 1km global
```

**Strengths**:
- Global coverage
- Multiple taxa
- API access
- 46,000 tree species

**Weaknesses**:
- 1km resolution (100× coarser)
- Mixed quality across taxa
- No temporal dynamics

---

### NatureServe

**Algorithm**: GIS-based habitat suitability + human-AI collaboration
```
Documented locations + environmental → Habitat suitability → Expert review
```

**Strengths**:
- Expert validation (OneRange project)
- Rare/endangered species focus
- High-quality data for US/Canada

**Weaknesses**:
- 30m resolution (3× coarser)
- Limited geographic coverage
- Proprietary data

---

### NASA/ESA

**Algorithm**: Multi-sensor integration + ecological models
```
MODIS + Landsat + Sentinel → Environmental predictors → Ensemble SDMs → Uncertainty
```

**Strengths**:
- Uncertainty quantification (gold standard)
- Ensemble methods
- Operational forecasting (1-12 month)
- Historical analysis (1985+)

**Weaknesses**:
- Generalist (not tree-specific)
- 30m-500m resolution
- Complexity (high barrier to use)

---

## Performance Benchmarks (Where Available)

| Platform | Validation Metric | Score | Notes |
|----------|------------------|-------|-------|
| **eBird** | Temporal AUC | 0.85-0.95 | Validated on subsequent years |
| **Map of Life** | Not published | N/A | No public validation metrics |
| **NatureServe** | Expert review | Qualitative | Human-in-loop validation |
| **NASA Projects** | TSS | >0.7 | Gold standard requirement |
| **Treekipedia** | **Not tested** | **N/A** | ⚠️ Critical gap |

**Action Required**: Implement validation framework in Phase 1.

---

## Use Case Fit Analysis

### Restoration Practitioners

| Need | eBird | Map of Life | NatureServe | NASA/ESA | **Treekipedia** |
|------|-------|-------------|-------------|----------|----------------|
| Tree species focus | ❌ | ⚠️ | ⚠️ | ❌ | ✅ **Best** |
| Plot-level precision (10m) | ❌ | ❌ | ⚠️ | ❌ | ✅ **Best** |
| Native status data | N/A | ⚠️ | ✅ | ❌ | ✅ **Best** |
| Restoration recommendations | ❌ | ❌ | ⚠️ | ❌ | ✅ **LEAF + native** |
| Uncertainty info | ✅ | ⚠️ | ⚠️ | ✅ | ❌ **Gap** |

**Verdict**: Treekipedia **best-positioned** for restoration IF we add uncertainty quantification.

---

### Researchers

| Need | eBird | Map of Life | NatureServe | NASA/ESA | **Treekipedia** |
|------|-------|-------------|-------------|----------|----------------|
| Published methodology | ✅ | ✅ | ✅ | ✅ | ❌ **Gap** |
| Validation metrics | ✅ | ⚠️ | ✅ | ✅ | ❌ **Gap** |
| Reproducibility | ✅ | ⚠️ | ❌ | ✅ | ⚠️ |
| API access | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fine resolution | ❌ | ❌ | ⚠️ | ❌ | ✅ **Best** |

**Verdict**: Not competitive until Phase 1 complete (validation + methodology paper).

---

### Conservation Organizations

| Need | eBird | Map of Life | NatureServe | NASA/ESA | **Treekipedia** |
|------|-------|-------------|-------------|----------|----------------|
| Institutional trust | ✅ | ✅ | ✅ | ✅ | ⚠️ **Building** |
| Explainability | ⚠️ | ❌ | ✅ | ⚠️ | ❌ **Gap** |
| Blockchain provenance | ❌ | ❌ | ❌ | ❌ | ✅ **Unique** |
| Landscape-scale analysis | ✅ | ✅ | ✅ | ✅ | ❌ **Gap** |
| Climate projections | ❌ | ❌ | ❌ | ✅ | ❌ |

**Verdict**: Blockchain provenance unique advantage, but need explainability + polygon support.

---

### Policy Makers

| Need | eBird | Map of Life | NatureServe | NASA/ESA | **Treekipedia** |
|------|-------|-------------|-------------|----------|----------------|
| Transparency | ✅ | ⚠️ | ✅ | ✅ | ⚠️ |
| Interpretability | ⚠️ | ❌ | ✅ | ⚠️ | ❌ **Gap** |
| Uncertainty info | ✅ | ⚠️ | ⚠️ | ✅ | ❌ **Gap** |
| Auditability | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ **Blockchain** |
| Institutional backing | ✅ | ✅ | ✅ | ✅ | ⚠️ |

**Verdict**: Blockchain auditability is unique selling point, but need explainability + uncertainty.

---

## Competitive Positioning Scenarios

### Scenario 1: If We Do NOTHING (Current State)

**Position**: "Experimental tree species predictor with novel blockchain integration"

**Strengths**:
- Finest resolution (10m)
- Tree specialization
- Blockchain provenance

**Weaknesses**:
- Not scientifically validated
- No uncertainty quantification
- Point-only predictions
- Can't publish methodology
- Can't compete for institutional adoption

**Market Fit**: Hobbyists, crypto enthusiasts, early adopters

**Risk**: Competitors add blockchain faster than we add validation → We lose unique advantage

---

### Scenario 2: If We Complete Phase 1 (16 Weeks)

**Position**: "The world's most precise tree species predictor for restoration ecology"

**Strengths**:
- Finest resolution (10m)
- Tree specialization
- Blockchain provenance
- ✅ **Validated methodology**
- ✅ **Uncertainty quantification**
- ✅ **Explainable predictions**
- ✅ **Ensemble methods**

**Weaknesses**:
- Still point-only (vs. competitors' polygon support)
- No temporal forecasting
- Limited historical analysis

**Market Fit**: Restoration practitioners, conservation orgs, researchers

**Risk Mitigation**: Validated methodology enables institutional adoption + publications

---

### Scenario 3: If We Complete Phases 1-3 (44 Weeks)

**Position**: "Blockchain-verified ecological intelligence at field scale"

**Strengths**:
- All Phase 1 strengths
- ✅ **Landscape-scale predictions**
- ✅ **67,743 species coverage**
- ✅ **Species richness analysis**
- ✅ **Restoration suitability scoring**

**Weaknesses**:
- No temporal forecasting (vs. eBird's weekly, NASA's seasonal)

**Market Fit**: All user segments (restoration, research, conservation, policy)

**Competitive Moat**: Combination of features unavailable elsewhere

---

### Scenario 4: If We Complete All Phases (64 Weeks)

**Position**: "The gold standard for tree species distribution modeling"

**Strengths**:
- All previous strengths
- ✅ **Historical analysis (1985-2024)**
- ✅ **Climate forecasting (2050/2100)**
- ✅ **Temporal range shift predictions**

**Weaknesses**: None significant vs. competitors

**Market Fit**: Industry leader

**Competitive Moat**: Nearly impossible to replicate (requires 15 months + AlphaEarth + blockchain + tree expertise + occurrence data)

---

## Decision Matrix: Where to Invest?

| Feature | Competitive Necessity | Unique Differentiator | User Value | Implementation Cost | **Priority** |
|---------|----------------------|----------------------|------------|---------------------|--------------|
| **Uncertainty Quantification** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Low | **CRITICAL** |
| **Ensemble Methods** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Medium | **CRITICAL** |
| **Validation Framework** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | Low | **CRITICAL** |
| **Explainable AI** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Low | **HIGH** |
| **Polygon Support** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | Medium | **HIGH** |
| **Phylogenetic Borrowing** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | **HIGH** |
| **Temporal Forecasting** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High | MEDIUM |
| **Historical Analysis** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High | MEDIUM |
| **Climate Forecasting** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | High | MEDIUM |

**Interpretation**:
- **5 stars = Essential** for competitive parity
- **4 stars = Important** for differentiation or user value
- **3 stars = Nice to have**
- **2 stars = Low priority**

---

## Recommended Action Plan

### Immediate (Next 4 Months) - Phase 1

**Investment**: 2 FTE × 16 weeks = 32 person-weeks

**ROI**: Enables scientific credibility, institutional adoption, and publication

**Features**:
1. Uncertainty quantification
2. Ensemble methods
3. Validation framework
4. Explainable AI

**Expected Outcome**: Competitive with eBird/Map of Life for restoration use cases

---

### Short-term (Months 5-7) - Phase 2

**Investment**: 1.5 FTE × 12 weeks = 18 person-weeks

**ROI**: Full species coverage, handle data-deficient species

**Features**:
1. Phylogenetic borrowing
2. Climate analogue matching

**Expected Outcome**: 67,743 species coverage, unique capability for rare species

---

### Medium-term (Months 8-11) - Phase 3

**Investment**: 2 FTE × 16 weeks = 32 person-weeks

**ROI**: Landscape-scale analysis, restoration planning tools

**Features**:
1. Polygon/AOI support
2. Species richness analysis
3. Restoration suitability scoring

**Expected Outcome**: Competitive with all major platforms, unique tree specialization

---

### Long-term (Months 12-15) - Phase 4

**Investment**: 2 FTE × 20 weeks = 40 person-weeks

**ROI**: Historical + climate forecasting, cutting-edge capabilities

**Features**:
1. Historical analysis (1985-2024)
2. Climate forecasting (2050/2100)

**Expected Outcome**: Industry leader, gold standard platform

---

## Summary: Our Competitive Position

### Today
- **Strengths**: 10m resolution, tree specialization, blockchain
- **Weaknesses**: No validation, no uncertainty, no polygon support
- **Position**: Experimental platform with unique tech
- **Market Fit**: Early adopters only

### After Phase 1 (16 weeks)
- **Strengths**: All above + validated, explainable, ensemble methods
- **Weaknesses**: Still point-only, no temporal
- **Position**: Scientifically credible tree SDM platform
- **Market Fit**: Restoration practitioners, researchers

### After Phase 3 (44 weeks)
- **Strengths**: All above + landscape-scale, full coverage
- **Weaknesses**: No temporal forecasting
- **Position**: Leading tree species platform
- **Market Fit**: All user segments

### After Phase 4 (64 weeks)
- **Strengths**: All above + historical + climate projections
- **Weaknesses**: None significant
- **Position**: Industry gold standard
- **Market Fit**: Dominant platform for tree SDM

---

**Recommendation**: **Invest in Phase 1 immediately**. It's the minimum viable scientific credibility threshold for 2025+ and unlocks institutional adoption + publication opportunities.

---

**Document Version**: 1.0
**Last Updated**: January 21, 2026
**Next Review**: After Phase 1 completion
