# Treekipedia Species Prediction & Recommendation: Ultimate Architecture

**Date**: January 21, 2026
**Version**: 1.0
**Status**: Synthesis of Claude Research + Critical Analysis of Gemini Proposals

---

## Executive Summary

This document synthesizes:
1. **7 comprehensive research documents** (~270KB) covering hydrological, topographic, soil, microclimate, functional traits, disturbance, and restoration tool variables
2. **Audit of existing Treekipedia data** (88-100% coverage in most categories)
3. **Critical analysis of Gemini's SAFE-B framework** (valid conceptually, but oversimplified in places)
4. **Practical implementation roadmap** based on what we actually have and can realistically build

**Key Finding**: Treekipedia already has **exceptional environmental data coverage** (leads in 7 of 10 categories vs competitors). The gap is not data—it's **integration and operationalization**. The critical path is:
1. Complete AlphaEarth sampling (48K species, not 100)
2. Add numeric elevation (currently text-only)
3. Build the ensemble prediction pipeline (not just cosine similarity)
4. Layer recommendation logic on top

---

## Part 1: Critical Analysis of Gemini's SAFE-B Framework

### What Gemini Got Right

| Concept | Assessment | Our Research Support |
|---------|------------|---------------------|
| **Prediction vs Recommendation split** | ✅ Correct and important | Matches SDM research: scientific suitability ≠ restoration recommendation |
| **Hybrid explainable + vector scoring** | ✅ Excellent architecture | Research shows ensemble (RF + MaxEnt + embedding) outperforms single method |
| **Native status as primary filter** | ✅ Absolutely critical | All restoration tools use invasive-first-elimination |
| **Biogeography/proximity bonus** | ✅ Well-conceived | Research shows local abundance is strong predictor |
| **pgvector for similarity search** | ✅ Correct tool choice | Already implemented in production |

### What Gemini Oversimplified or Missed

| Issue | Gemini's Gap | Our Research Finding | Impact |
|-------|-------------|---------------------|--------|
| **Variable depth** | Lists "Soil (SOC, CEC, AWC)" generically | We researched 15+ soil variables with GEE availability, depth layers (0-5cm to 200cm), POLARIS vs SoilGrids tradeoffs | HIGH - wrong variables = wrong predictions |
| **Hydrological variables** | Completely missing | TWI, HAND, distance to water, water table depth are critical for riparian/phreatophyte species (1000+ in our DB) | HIGH - misses entire species guild |
| **Disturbance context** | Mentions "fire-intolerant species" but no data plan | Hansen forest loss, LANDFIRE MFRI, Human Footprint all in GEE with concrete implementation | MEDIUM - affects restoration sites |
| **Microclimate** | Missing entirely | Frost days, GDD, CHILI heat load index, cold hardiness zones critical for temperate species | HIGH - kills species matching accuracy |
| **Functional traits** | Says "ingest from GRooT and TRY" | TRY requires formal data request (weeks), BIEN has API, GRooT is CSV download - actual access varies | MEDIUM - implementation blocked if not planned |
| **AlphaEarth status** | Assumes it's future work | We have 100 species done, COG pipeline available, can scale to 48K for <$50 | CRITICAL - Gemini underestimates our progress |
| **Existing data richness** | Underestimates | We have 88% climate, 82% soil, 100% traits, 100% biotic interactions already | HIGH - don't rebuild what exists |

### What Gemini Added That We Should Adopt

| Concept | Value | Integration Plan |
|---------|-------|------------------|
| **SAFE-B naming/structure** | Clear mental model for stakeholders | Adopt as user-facing terminology |
| **Weight percentages (S:35%, A:15%, F:20%, E:15%, B:10%)** | Starting point for scoring | Use as defaults, make configurable |
| **LightGBM for explainable model** | Proven for SDM, fast, handles mixed types | Add alongside cosine similarity |
| **Phase-based rollout** | Practical delivery | Align with our detailed variable research |

---

## Part 2: The Actual Variable Inventory (From Our Research)

### Tier 1: Already Have (Use Immediately)

| Category | Variables | Coverage | Format | Action |
|----------|-----------|----------|--------|--------|
| **Climate** | 8 vars (temp, precip, seasonality) | 88.6% | Percentile ranges | Parse to numeric |
| **Soil** | 12 vars (pH, texture, OC) | 66-82% | Categories + ranges | Encode categoricals |
| **Native Status** | WCVP native/introduced | 99.99% | ISO codes | Already queryable |
| **Biogeography** | Ecoregions, biomes, IFL | 85-100% | Semicolon lists | Join to zone table |
| **Traits** | 35+ functional traits | 100% AI | Text (needs parsing) | Extract numeric where possible |
| **Biotic Interactions** | 8 GloBI interaction types | 100% | Semicolon taxa | Count for scoring |
| **Occurrences** | 5.7M L7 geohash tiles | 71% species | JSONB | Direct query |

### Tier 2: In Progress (Complete ASAP)

| Category | Variables | Current Status | Gap | Action |
|----------|-----------|----------------|-----|--------|
| **AlphaEarth** | 64-D embeddings | 100 species (0.15%) | 47,900 species | Run COG pipeline |
| **Elevation** | SRTM 30m | Text prose only | Numeric percentiles | Intersect occurrences with SRTM |
| **Hansen Forest** | Loss year, gain, treecover | 17.9% sampled | 82.1% remaining | Sample with AlphaEarth |

### Tier 3: Add from GEE (High Value, Moderate Effort)

| Category | Variables | Data Source | Resolution | GEE Asset |
|----------|-----------|-------------|------------|-----------|
| **Topographic** | Slope, aspect, TPI, roughness | SRTM/ALOS | 30m | `USGS/SRTMGL1_003` |
| **Heat/Cold** | CHILI, frost days | CSP ERGo, ERA5 | 90m-11km | `CSP/ERGo/1_0/Global/ALOS_CHILI` |
| **Hydrological** | TWI, HAND, flow accumulation | MERIT Hydro | 90m | Community catalog |
| **Soil (extended)** | CEC, AWC, Ksat, N | SoilGrids 2.0 | 250m | `ISRIC/SoilGrids250m_v2_0` |
| **Disturbance** | Human Footprint, fire freq | HII, MODIS | 1km-500m | `CSP/HM/GlobalHumanModification` |

### Tier 4: Add Later (Specialized)

| Category | Variables | When Needed | Complexity |
|----------|-----------|-------------|------------|
| **Climate Projections** | CMIP6 2050/2100 | Climate adaptation features | HIGH |
| **P50 Hydraulic Traits** | Xylem vulnerability | Drought resilience scoring | HIGH (limited data) |
| **Fire Return Interval** | LANDFIRE MFRI | US fire-adapted species | MEDIUM (US only) |
| **Historical Land Use** | HILDA+ | Agricultural legacy | MEDIUM |

---

## Part 3: The Unified Architecture

### 3.1 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER (PostgreSQL + PostGIS)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  species (67,743 records)                                                   │
│  ├── Climate percentiles (88%)                                              │
│  ├── Soil categories (66-82%)                                               │
│  ├── Native status (99.99%)                                                 │
│  ├── Traits (100% AI)                                                       │
│  └── Biotic interactions (100%)                                             │
│                                                                             │
│  species_alphaearth_centroids (48K target)                                  │
│  ├── 64-D embedding vectors (pgvector)                                      │
│  ├── Habitat cluster IDs (3-10 per species)                                 │
│  └── Representative lat/lon/year                                            │
│                                                                             │
│  species_environmental_profiles (NEW)                                       │
│  ├── Elevation percentiles (min/p25/median/p75/max)                         │
│  ├── Derived topographic (slope, TWI, TPI)                                  │
│  ├── Microclimate (frost_days, GDD)                                         │
│  └── Disturbance context (HFI, fire_freq)                                   │
│                                                                             │
│  treekipedia_zones (Unified Zone Schema)                                    │
│  ├── L7 geohash centroids                                                   │
│  ├── Pre-computed environmental values                                      │
│  └── Zone connectivity graph                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PREDICTION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. VECTOR SIMILARITY (AlphaEarth)                                          │
│     ├── Sample 64-D embedding at query point                                │
│     ├── Cosine similarity to species centroids (pgvector)                   │
│     └── Return top-K matches with similarity scores                         │
│                                                                             │
│  2. EXPLAINABLE MODEL (LightGBM/XGBoost)                                    │
│     ├── Input: environmental variables at query point                       │
│     ├── Predict P(species present | environment)                            │
│     ├── SHAP values for "why this prediction"                               │
│     └── Return probability scores with explanations                         │
│                                                                             │
│  3. ENSEMBLE COMBINATION                                                    │
│     ├── Weighted average: (0.6 × vector) + (0.4 × explainable)              │
│     ├── Uncertainty quantification (variance across methods)                │
│     └── Habitat Suitability Index (HSI): 0-100 scale                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RECOMMENDATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. NATIVE STATUS FILTER (Externality)                                      │
│     ├── Check WCVP native/introduced for query country                      │
│     ├── ELIMINATE if invasive                                               │
│     ├── BOOST if native (+20%)                                              │
│     └── NEUTRAL if introduced-not-invasive                                  │
│                                                                             │
│  2. BIOGEOGRAPHY BONUS                                                      │
│     ├── Check species presence in query ecoregion                           │
│     ├── Calculate proximity to nearest occurrence                           │
│     ├── Score: high density + close proximity = +15%                        │
│     └── Penalty for >500km from any occurrence: -10%                        │
│                                                                             │
│  3. FUNCTIONALITY MATCH (Goal-Oriented)                                     │
│     ├── User selects goal: erosion, nitrogen, carbon, biodiversity          │
│     ├── Match to species traits/functional groups                           │
│     ├── Boost: nitrogen-fixer for fertility goal (+10%)                     │
│     └── Boost: high root depth for erosion goal (+10%)                      │
│                                                                             │
│  4. RISK ASSESSMENT                                                         │
│     ├── Commercial species flag → greenwashing warning                      │
│     ├── Disturbance mismatch → lower confidence                             │
│     └── Data quality flags → uncertainty indicator                          │
│                                                                             │
│  OUTPUT: SAFE-B Score (-10 to +10) with breakdown                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 API Design

```
GET /api/v2/predict/species?lat={lat}&lon={lon}
Response:
{
  "location": { "lat": -23.5, "lon": -46.6, "country": "BRA", "ecoregion": "Atlantic Forest" },
  "environment": {
    "elevation_m": 823,
    "annual_precip_mm": 1420,
    "mean_temp_c": 19.2,
    "soil_ph": 5.8,
    "soil_texture": "Sandy Loam",
    "twi": 8.4,
    "human_footprint": 42
  },
  "predictions": [
    {
      "taxon_id": "wfo-0000123456",
      "species": "Araucaria angustifolia",
      "hsi_score": 0.87,
      "vector_similarity": 0.91,
      "explainable_probability": 0.82,
      "explanation": ["Elevation match (good)", "Precipitation match (excellent)", "Soil pH slightly acidic (acceptable)"]
    }
  ]
}

GET /api/v2/recommend/species?lat={lat}&lon={lon}&goal={goal}
Response:
{
  "location": { ... },
  "goal": "erosion_control",
  "recommendations": [
    {
      "taxon_id": "wfo-0000123456",
      "species": "Araucaria angustifolia",
      "safeb_score": 7.2,
      "breakdown": {
        "suitability": 4.3,
        "adaptability": 0.8,
        "functionality": 1.5,
        "externality": 0.4,
        "biogeography": 0.2
      },
      "native_status": "native",
      "distance_to_nearest_km": 12.4,
      "traits_match": ["deep_rooting", "erosion_resistant"],
      "warnings": []
    }
  ]
}
```

---

## Part 4: Implementation Roadmap

### Phase 1: Complete AlphaEarth & Elevation (Weeks 1-4)

| Week | Task | Deliverable | Cost |
|------|------|-------------|------|
| 1 | Set up GCS COG pipeline | `orchestrator/gcs_sampler.py` functional | $0 |
| 1 | Process 2024 COGs (most recent) | 10M pixel extractions | ~$5 |
| 2 | Process 2020-2023 COGs | 30M pixel extractions | ~$15 |
| 2 | SRTM elevation intersection | `species_elevation_profiles` table | $0 (local) |
| 3-4 | Habitat clustering | 48K species with 3-10 centroids each | $0 (local) |

**Success Criteria**:
- 48,000+ species with AlphaEarth centroids
- Numeric elevation for all species with occurrences
- Total cost < $25

### Phase 2: Explainable Model Training (Weeks 5-8)

| Week | Task | Deliverable |
|------|------|-------------|
| 5 | Feature engineering | Environmental variables matrix (species × locations) |
| 5-6 | Train LightGBM on 80% data | Model artifact + SHAP explainer |
| 7 | Validate on 20% holdout | AUC > 0.8, TSS > 0.6 for top 1000 species |
| 8 | Integrate into API | `/predict` endpoint with explanations |

**Success Criteria**:
- Explainable model matches or exceeds vector-only baseline
- SHAP explanations meaningful to ecologists
- API response < 500ms

### Phase 3: Recommendation Layer (Weeks 9-12)

| Week | Task | Deliverable |
|------|------|-------------|
| 9 | Native status filter | Country-level invasive elimination |
| 9-10 | Biogeography scoring | Ecoregion presence + proximity bonus |
| 11 | Goal-based matching | Trait filters for erosion/nitrogen/carbon/biodiversity |
| 12 | Risk assessment | Commercial flags, disturbance warnings |

**Success Criteria**:
- Invasive species never recommended in native range
- Goal filters produce relevant species lists
- SAFE-B scores intuitive to restoration practitioners

### Phase 4: Validation & Launch (Weeks 13-16)

| Week | Task | Deliverable |
|------|------|-------------|
| 13 | Expert validation | Ecologist review of 100 test locations |
| 14 | A/B test vs current system | User preference data |
| 15 | Documentation | API docs, methodology paper draft |
| 16 | Production deployment | v2 API live |

---

## Part 5: New Datasets to Acquire

### Immediate (Before Phase 1)

| Dataset | Source | Variables | Resolution | Access |
|---------|--------|-----------|------------|--------|
| **AlphaEarth COGs** | `gs://alphaearth_foundations/` | 64-D embeddings | 10m | HTTP range requests |
| **SRTM** | USGS/GEE | Elevation | 30m | Already available |

### Phase 2 (GEE Sampling)

| Dataset | GEE Asset | Variables | Priority |
|---------|-----------|-----------|----------|
| **SoilGrids v2** | `ISRIC/SoilGrids250m_v2_0` | CEC, AWC, N, bulk density | HIGH |
| **CHILI** | `CSP/ERGo/1_0/Global/ALOS_CHILI` | Heat load index | HIGH |
| **MERIT Hydro** | Community catalog | HAND, TWI | HIGH |
| **ERA5-Land** | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | Frost days, GDD | MEDIUM |
| **Human Modification** | `CSP/HM/GlobalHumanModification` | Human footprint | MEDIUM |

### Phase 3 (Trait Databases)

| Database | Access Method | Coverage | Priority |
|----------|--------------|----------|----------|
| **BIEN** | R API (`BIEN` package) | 93K species | HIGH |
| **TRY** | Formal data request | Largest global | MEDIUM |
| **GRooT** | CSV download | Root traits | HIGH |

---

## Part 6: How to Best Leverage AlphaEarth

### Current State
- 64-dimensional embeddings capturing spectral, textural, and contextual satellite features
- 10m resolution (3-100× finer than any competitor)
- Available as COGs on GCS (cheap, fast access)
- 100 species completed in proof-of-concept

### Optimal Usage Strategy

1. **Primary Use: Habitat Prototype Matching**
   - Cluster species occurrences in embedding space
   - Store 3-10 centroids per species (habitat types)
   - Query: cosine similarity between location and centroids
   - This captures "environmental character" without explicit variables

2. **Secondary Use: Ensemble Component**
   - Combine with explainable model (LightGBM)
   - Vector captures nonlinear patterns, explainable provides interpretability
   - Research shows ensemble outperforms either alone by 15-25%

3. **Future Use: Transfer Learning**
   - Use embeddings as input features for other models
   - Train species-specific fine-tuned layers
   - Temporal analysis (compare 2017 vs 2024 embeddings)

### What AlphaEarth Cannot Do (Use Explicit Variables Instead)

| Limitation | Why | Solution |
|------------|-----|----------|
| **Soil chemistry** | Below-ground, not visible | SoilGrids 250m |
| **Historical state** | Only 2017-2024 | Hansen loss year + Landsat archive |
| **Climate projections** | Past satellite, not future | CMIP6 scenarios |
| **Human modification detail** | 10m captures structure, not intensity | Human Footprint Index |

---

## Part 7: Key Differences from Gemini's Proposal

| Aspect | Gemini Proposal | Our Approach | Rationale |
|--------|-----------------|--------------|-----------|
| **Data acquisition** | "Ingest from GEE" (generic) | Specific GEE assets with code | Actionable implementation |
| **AlphaEarth timeline** | Phase 4 (future) | Phase 1 (now) | We're 0.15% done, not 0% |
| **Trait databases** | "Query TRY/GRooT" | BIEN API first, TRY formal request | TRY access takes weeks |
| **Model architecture** | LightGBM only for explainable | LightGBM + XGBoost + cosine ensemble | Research shows ensemble wins |
| **Hydrological variables** | Missing | TWI, HAND, distance to water | Critical for 1000+ riparian species |
| **Microclimate** | Missing | CHILI, frost days, GDD | Critical for temperate/montane species |
| **Cost estimates** | "$5-20 for training" | <$50 total for AlphaEarth + training | More realistic |
| **Existing data leverage** | Underestimates | 88% climate, 82% soil already done | Don't rebuild |

---

## Part 8: Success Metrics

### Technical Metrics

| Metric | Target | Current | Measurement |
|--------|--------|---------|-------------|
| Species with AlphaEarth | 48,000 | 100 | `species_alphaearth_centroids` count |
| Prediction AUC (top 1000 species) | >0.8 | N/A | Holdout validation |
| API latency (p95) | <500ms | ~200ms (current) | Monitoring |
| Uncertainty coverage | 90% | N/A | Predictions in confidence interval |

### User Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recommendation relevance | >80% "useful" | User feedback survey |
| Explanation clarity | >70% "understandable" | User feedback survey |
| Goal matching accuracy | >90% trait-matched | Expert review |

### Scientific Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| TSS (True Skill Statistic) | >0.6 | Holdout validation |
| Variable importance stability | <10% variance | Bootstrap resampling |
| Publication readiness | Methodology paper | Peer review |

---

## Appendix: Research Document Index

| Document | Size | Key Findings |
|----------|------|--------------|
| [RESEARCH_HYDROLOGICAL_VARIABLES.md](./RESEARCH_HYDROLOGICAL_VARIABLES.md) | 48KB | TWI, HAND, TerraClimate, phreatophyte thresholds |
| [RESEARCH_TOPOGRAPHIC_VARIABLES.md](./RESEARCH_TOPOGRAPHIC_VARIABLES.md) | 48KB | CHILI > raw aspect, TPI for landforms, ALOS > SRTM |
| [RESEARCH_SOIL_VARIABLES.md](./RESEARCH_SOIL_VARIABLES.md) | 42KB | SoilGrids v2 in GEE, CEC/AWC/Ksat important |
| [RESEARCH_MICROCLIMATE_VARIABLES.md](./RESEARCH_MICROCLIMATE_VARIABLES.md) | 39KB | ERA5-Land frost/GDD, NicheMapR for downscaling |
| [RESEARCH_FUNCTIONAL_TRAITS.md](./RESEARCH_FUNCTIONAL_TRAITS.md) | 34KB | BIEN API best, TRY requires request, P50 limited |
| [RESEARCH_DISTURBANCE_VARIABLES.md](./RESEARCH_DISTURBANCE_VARIABLES.md) | 34KB | Hansen + LANDFIRE + HFI, recovery trajectories |
| [RESEARCH_RESTORATION_TOOLS.md](./RESEARCH_RESTORATION_TOOLS.md) | 25KB | D4R most sophisticated, all miss hydrology/microclimate |
| [AUDIT_EXISTING_VARIABLES.md](./AUDIT_EXISTING_VARIABLES.md) | 39KB | 88% climate, 82% soil, 99.99% native status |

**Total Research**: ~270KB across 8 documents

---

## Conclusion

Treekipedia is **exceptionally well-positioned** to build a world-class species prediction and recommendation system. The foundation exists:
- **88-100% coverage** for most environmental variables
- **AlphaEarth pipeline** proven at 10m resolution
- **pgvector** already deployed for similarity search
- **Native status data** unmatched at 99.99%

The critical path is not data collection (mostly done) but **integration and operationalization**:
1. Scale AlphaEarth to 48K species (4 weeks, <$25)
2. Add numeric elevation (2-3 days)
3. Train ensemble model (3 weeks)
4. Build recommendation layer (4 weeks)

Gemini's SAFE-B framework provides a useful **conceptual structure** and **user-facing terminology**, but this document provides the **actionable technical specification** grounded in actual data availability, GEE asset IDs, and realistic cost/timeline estimates.

**Next Step**: Begin Phase 1 - AlphaEarth COG pipeline setup.
