# SINR March 4 Codex

Date: 2026-03-04
Purpose: Clarify and tighten SINR into a high-accuracy ecological intelligence engine that can power point decisions now and area-scale planning next.

## 1) What this is

SINR is the AI/science layer for Treekipedia and future Silvi workflows. Its core job is to transform satellite/environmental signals and species knowledge into decision-grade outputs for restoration and land strategy.

This document defines:
- exact product intent
- architecture boundaries
- point-first then area-scale plan
- required data additions (minimal viable set)
- model strategy (without training a giant foundation model)
- CAPEX/OPEX framework

## 2) Clarifications that matter

### 2.1 Three different questions (must be separate)

1. What is growing there now?
- State estimation / current composition inference.
- Dominated by current remote sensing + disturbance + land cover context.

2. What can grow there?
- Biophysical suitability under current conditions.
- Dominated by climate, soil, topography, hydrology, and analog habitats.

3. What should we grow there?
- Strategy-constrained recommendation.
- Dominated by objective function (native restoration, carbon, agroforestry, riparian, biodiversity), constraints, and time horizon.

These are not interchangeable. The engine must output all three separately.

### 2.2 Point system first, area system on top

Yes: area-based planning should be built on the point pipeline.

Practical implementation:
- point engine computes per-pixel outputs
- area job runs over all pixels in AOI (with tiling/chunking)
- polygon analytics aggregate pixel outputs into management units and strategy plans

This preserves architectural simplicity and avoids bifurcated logic.

## 3) Product intent (for Silvi context)

SINR should provide the intelligence layer that Silvi can call for:
- baseline ecological state
- restoration strategy generation
- scenario comparison
- confidence/risk-aware projections

Silvi can own MRV orchestration and workflow lifecycle; SINR provides scientific inference primitives and scenario outputs.

## 4) Target architecture (tightened)

## Layer A: Data and Feature Fabric
- Inputs: AlphaEarth (current + temporal trajectory), climate, soils, terrain, disturbance, land cover, hydrology, ecoregion, species knowledge.
- Outputs: standardized per-pixel feature vectors with provenance and missingness flags.

## Layer B: Land State Engine (new required core)
- Purpose: classify land condition independent of species recommendation.
- Outputs per pixel:
  - disturbance status
  - successional stage class
  - restoration readiness score
  - degradation pressure score
  - intervention difficulty score

## Layer C: Ecological Inference Engine
- C1. Current Composition Estimator: probable current species/group composition.
- C2. Suitability Estimator: species that can persist/grow now.
- C3. Restoration Target Estimator: species/assemblages suited to post-intervention trajectory.

## Layer D: Strategy Engine
- Applies strategy objective and constraints to C1-C3 outputs.
- Generates recommendation portfolios with rationale:
  - native restoration
  - carbon-maximizing
  - biodiversity-first
  - agroforestry mixed utility
  - riparian stabilization

## Layer E: Area Planner and Scenario Engine
- Runs point inference over AOI.
- Segments AOI into management units.
- Simulates outcomes under interventions and time horizons.
- Produces maps, heat layers, and plan-level KPIs.

## Layer F: API/Serving
- Point APIs (real-time)
- AOI job APIs (async)
- Raster/vector outputs and heatmaps

## 5) Data strategy: minimal additions, maximum leverage

Constraint: avoid massive new corpus and avoid training a giant general foundation model.

### 5.1 Keep and harden what already works
- AlphaEarth embeddings (including temporal stack)
- climate/soil stack
- disturbance stack
- species occurrence embeddings and stats

### 5.2 Minimal additional datasets needed for strong land-state performance

Required additions (small set, high value):
- road/building/impervious proxy: ESA WorldCover + Dynamic World built class (already partly present)
- riparian proximity: JRC water + HAND (already available)
- erosion pressure: slope + soil texture + land cover + rainfall intensity proxy
- restoration soil pressure: SOC + soil pH/texture mismatch + bare/cropland cover

Optional additions (later):
- high quality local road/building datasets where available
- region-specific restoration constraints

Key point: you do not need a giant new dataset regime to model roads/buildings/land pressure at useful resolution.

## 6) Model strategy (accurate without giant foundation training)

### 6.1 Use foundation embeddings as frozen features
- Keep AlphaEarth as primary habitat representation.
- Optionally test Clay/Prithvi as additional frozen feature channels in ablations.
- Do not pretrain a new foundation model.

### 6.2 Multi-head structured modeling

Use shared trunk + specialized heads:
- Land State Head
- Current Composition Head
- Suitability Head
- Strategy-conditioned Recommendation Head
- Carbon/Biomass Head

Benefits:
- shared signal learning
- lower deployment complexity
- explicit decomposition of outputs

### 6.3 Keep k-NN as live baseline and fallback
- k-NN remains interpretable and robust fallback.
- neural head can replace/rerank only when quality gates pass.

### 6.4 Explicit uncertainty at output level
- predict confidence bands per output family
- separate data coverage uncertainty from model uncertainty
- expose confidence in API and map layers

## 7) Land State Engine design (why it helps whole pipeline)

It helps by preventing category errors:
- avoids recommending climax species on highly disturbed/compacted sites without intervention
- avoids overtrusting current pixel appearance when temporal context says site recently changed

Core outputs:
- Disturbance class: intact / modified / recently disturbed / heavily altered
- Successional stage: early / mid / late / mature
- Restoration readiness: low to high
- Limiting factors: hydrology, soil, slope/erosion, human pressure

Pipeline impact:
- gates recommendations
- conditions strategy weights
- improves calibration for carbon and biodiversity projections

## 8) Point engine output contract (must-have)

Per point, return five separate products:

1. Current State
- likely current cover condition
- probable current species assemblage (or nearest analog set)

2. Suitability
- ranked species that can persist under current conditions

3. Strategy Recommendations
- ranked species and mixes by chosen strategy

4. Projections
- expected 3/5/10/20 year trajectory under selected intervention package

5. Confidence and Risk
- uncertainty, key assumptions, major risk factors

## 9) Area engine design (heatmaps and planning)

### 9.1 Processing
- AOI tiled into raster chunks
- per-pixel inference via point engine
- aggregate into management units based on eco-homogeneity

### 9.2 Heatmaps
- baseline: disturbance, successional stage, restoration readiness, carbon state
- strategy: suitability score by strategy, intervention priority, expected gain
- projection: expected carbon gain, expected biodiversity gain, risk-adjusted confidence

### 9.3 Planning outputs
- intervention map
- unit-wise prescriptions
- KPI dashboard by scenario
- uncertainty/risk map

## 10) Biodiversity outputs beyond species count

Using existing Treekipedia schema fields (ecoregions, biomes, functional groups, tolerances, successional stage, interaction fields), compute:
- native integrity index
- functional diversity index
- structural diversity proxy
- interaction potential proxy
- compositional turnover risk

Note: this is feasible now from schema + predictions; no need to wait for full food-web completeness.

## 11) CAPEX/OPEX framework

## 11.1 CAPEX (build cost)

Components:
- engineering build (pipelines, model code, APIs, AOI processing)
- data engineering hardening (versioning, lineage, QA)
- initial model training cycles and benchmarking
- productization (map layers, job orchestration, dashboard)

Simple model:
- CAPEX_total = Eng_build + Data_build + ML_build + Product_build + QA_validation

Where each term can be estimated as:
- people_time_months x loaded monthly cost
- one-time compute + storage setup costs

## 11.2 OPEX (run cost)

Per-period operating cost buckets:
- inference compute (point + AOI jobs)
- GEE/BQ/query/storage operations
- retraining cadence cost
- monitoring/ops/oncall
- support and model governance

Per-AOI variable cost estimate:
- OPEX_aoi = N_pixels x (c_sampling + c_inference + c_storage_write + c_postproc)

Monthly total:
- OPEX_month = OPEX_fixed + sum(OPEX_aoi_jobs) + OPEX_retraining

## 11.3 Unit economics metrics to track
- cost per point query
- cost per km2 assessed
- cost per scenario run
- time-to-result per km2
- confidence-weighted value per assessment (business KPI)

## 11.4 Pricing linkage (later)
- base assessment tier (screening)
- strategy planning tier (multi-scenario)
- high-integrity science tier (enhanced uncertainty + audit artifacts)

## 12) Execution plan

### Phase 1: Accuracy core (now)
- finalize point contracts (state vs suitability vs recommendation)
- implement Land State Engine v1
- harden temporal and feature pipelines
- lock data versioning
- benchmark against known sites

### Phase 2: Area engine
- AOI tiling/job system
- heatmap outputs
- management unit aggregation
- strategy portfolio layer

### Phase 3: Projection and optimization
- intervention simulation
- multi-objective optimization
- scenario comparison and uncertainty surfaces

### Phase 4: Silvi integration
- expose stable APIs/artifacts for Silvi MRV orchestration
- add run metadata and audit trails

## 13) Quality bar and go/no-go gates

Before calling it production-grade:
- clear separation of state/suitability/recommendation outputs
- uncertainty shown and used in ranking
- robust AOI processing at target scale
- reproducible data/model versions
- regression suite on benchmark locations

## 14) Practical answer to foundation model question

Best approach now:
- keep AlphaEarth as main embedding backbone
- optionally run Clay as an additive feature experiment on a subset
- do not attempt to train a broad new foundation model

Why:
- better ROI
- faster iteration
- preserves ecological focus
- less infra and data burden

## 15) Immediate next actions (recommended)

1. Lock output taxonomy in code and docs:
- current state
- can grow
- should grow (strategy)

2. Implement Land State Engine v1 with existing features.

3. Define AOI async job spec and heatmap layer schema.

4. Add biodiversity composite indices from current schema fields.

5. Implement cost telemetry now (per-point and per-km2), so CAPEX/OPEX model is data-driven from day one.

---

This is the path to a cutting-edge product without overextending into unnecessary foundation model training. Build accuracy and decision separation first, then scale to area planning and scenario optimization on top of the same point engine.
