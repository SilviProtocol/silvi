# Handoff: Building a Species Suitability & Compatibility Engine on SINR v3

## The Big Picture

We have a **species prediction model (SINR)** that answers: "what tree species are likely at this GPS coordinate?" We want to evolve this into a **species suitability and compatibility engine** that answers much richer questions:

- "What species would THRIVE here, not just survive?"
- "What MIX of species optimizes for carbon sequestration on this degraded site?"
- "What native species could replace this plantation over a 30-year transition?"
- "What agroforestry arrangement maximizes food production + soil restoration here?"
- "What species are compatible with each other at this site for a multi-strata system?"

The prediction model is the foundation. Everything else is scoring, optimization, and strategy layers on top.

## Context: What We've Been Building

### SINR — Species Identification Neural Ranker

**SINR v2.2** (trained, not yet in production):
- ResidualFCNet with gated fusion (satellite + environmental branches)
- Input: 64-dim AlphaEarth satellite embedding + 56 continuous env features + 5 categorical embeddings + is_introduced flag = 130 features
- Output: 35,561 independent sigmoid probabilities (one per species) — NOT softmax, so multiple species can score high simultaneously
- Best results: top-10 accuracy 59.34%, top-50 accuracy 90.08%
- Trained on 7.9M occurrence rows from GBIF + USDA FIA

**SINR v3** (data pipeline running now, training not started):
- ~3x training data: ~23.6M rows (15.25M new GBIF + 8.3M existing)
- ~349 features (up from 130), key additions:
  - **AlphaEarth temporal trajectory** (8 years 2017-2024): mean/std/trend per embedding dim — captures landscape CHANGE over time
  - **Temporal awareness**: observation_year and emb_year as features
  - **Temporal LULC stack**: MODIS land cover at observation time vs AlphaEarth time, Hansen forest gain, VPD delta
  - **Derived change features**: lulc_changed, forest_to_nonforest, years_since_disturbance, ae_post_obs_change
  - **GBIF metadata**: basis_of_record, coordinate_uncertainty
- Architecture: FiLM gate, 512 hidden dim, ~40-50M params, hierarchical subspecies (dual-label single head with ~43,500 outputs)
- Training on Windows NVIDIA GPU, expected ~1-2 weeks from now

### Data Pipeline Status (RIGHT NOW)
- **New GBIF GEE sampling**: COMPLETE. 9,868,255 rows, 647 columns in BigQuery
- **Backfill existing data**: RUNNING (~2,617 batches). Sampling 8 years of AlphaEarth + temporal stack for existing training coordinates
- **Remaining**: compute derived features in BQ, merge, export to parquet, spatial block split, update training script, train, benchmark

### Current Production System (k-NN, NOT SINR)
The live system at `treekipedia/backend/routes/prediction.js` still uses k-NN:
1. Python service (port 5002) samples AlphaEarth embedding + env features from GEE at query point
2. Backend does k-NN over 11.4M occurrence embeddings (HNSW index)
3. Multi-signal composite scoring: embedding similarity, spatial proximity, WCVP range confirmation, ecoregion match, climate envelope, soil compatibility
4. Returns ranked species list

### SAFE-B Recommender (LIVE — the current strategy layer)
`treekipedia/backend/services/safeb-scorer.js` provides strategy-based recommendations with **7 modes**:
- **general**, **rewilding**, **agroforestry**, **riparian**, **carbon**, **biodiversity**, **erosion_control**
- Each strategy weights 5 signal components: **S**patial, **A**biotic, **F**unctional, **E**cosystem, **B**iotic
- Strategy examples:
  - **Agroforestry** (Functional=0.40): checks agroforestry_use_cases, food/fruit/nut production, nitrogen fixing, fast growth
  - **Carbon** (Functional=0.50): uses maximum_height, lifespan, timber_value as PROXIES (no actual carbon numbers)
  - **Rewilding** (Ecosystem=0.35): excludes introduced species, favors late-successional, intact forest presence
  - **Biodiversity** (Biotic=0.30): GloBI interaction richness, pollinator support
- Invasive species always excluded; introduced excluded for rewilding/biodiversity

### Species Database (133 columns, 67,743 records)
Relevant fields already available:
- **Agroforestry**: `agroforestry_use_cases_ai/_human`, `non_timber_products`, `uses`
- **Carbon/Growth**: `maximum_height_ai/_human`, `lifespan_ai/_human`, `growth_form_ai/_human`, `allometric_models`, `allometric_curve` (sparsely populated)
- **Ecology**: `successional_stage`, `nitrogen_fixation_capacity`, `root_type`, `tolerances` (drought/shade/frost/etc.)
- **Site matching**: `soil_texture_prefered`, `ph_prefered`, `climate_type_koppengeiger`, `annual_precipitation_mm`, `annual_temperature_range_c`, `elevation_ranges`
- **Geography**: `countries_native`, `countries_introduced`, WCVP native/introduced ranges (99.99% coverage)
- **Conservation**: `conservation_status`, `threatened_status`, `present_intact_forest`
- **Interactions**: GloBI data — pollinators, herbivores, dispersers, parasites (8 columns)
- **Dual-field pattern**: `field_ai` and `field_human` (human takes precedence)

## What v3 Unlocks That Changes Everything

### 1. Temporal Awareness = Restoration Potential Detection
v3 sees landscape CHANGE. A pixel that was forest in 2017 but grassland in 2024 (high AE trajectory variance, forest_to_nonforest=true) is fundamentally different from stable grassland. The model learns which species historically occurred at sites with similar disturbance profiles — which is exactly what you want for restoration site assessment.

### 2. Disturbance History = Successional Stage Matching
Features like `years_since_disturbance`, `lulc_changed`, `ae_post_obs_change` let the model implicitly learn successional dynamics. Pioneer species show up at recently disturbed sites. Late-successional species show up at stable, mature sites. This opens the door to **successional planning**: recommend pioneer species for year 0-5, transitional species for year 5-15, climax species for year 15+.

### 3. Multi-Year Satellite = Site Quality Signal
The 8-year AlphaEarth trajectory (mean/std/trend per dimension) is a proxy for site productivity and stability. High mean + low std = stable productive site. Low mean + high trend = recovering site. This is a site quality signal the model learns implicitly.

### 4. Hierarchical Subspecies = Fine-Grained Variety Matching
The dual-label system (-00 species level, -01+ subspecies) means the model can potentially distinguish locally-adapted varieties — relevant for selecting the right provenance for a planting site.

## The Vision: A Composable Suitability Engine

### Layer 1: Species Presence Probability (SINR)
"What CAN grow here?" — sigmoid probabilities per species. This is the foundation.

### Layer 2: Site-Species Compatibility Scoring
"How WELL would it grow here?" — goes beyond binary presence to gradient suitability. Components:
- **Climate envelope fit**: how close is this site to the species' optimum? (use climate features vs species preferences)
- **Soil compatibility**: pH match, texture match, drainage
- **Elevation fit**: within the species' documented range?
- **Disturbance compatibility**: does the species' successional stage match the site's disturbance history?
- **Native range proximity**: is this within or near the species' documented native range?

### Layer 3: Strategy-Weighted Optimization
"What's BEST for my goal?" — the user's intent shapes the ranking. But unlike the current SAFE-B binary strategies, this should be a **continuous, composable weighting system** where users can:
- Slide between strategies (60% carbon, 40% biodiversity)
- Set hard constraints (must be native, must fix nitrogen, must tolerate drought)
- Optimize for compound objectives (maximize carbon AND food production AND soil restoration)

Possible strategy dimensions (not exhaustive):
- **Carbon sequestration**: growth rate, max biomass, longevity, wood density
- **Soil restoration**: nitrogen fixation, root architecture, litter quality, mycorrhizal associations
- **Food/economic production**: fruit, nut, timber, NTFP value
- **Biodiversity support**: interaction richness, pollinator support, wildlife habitat
- **Native ecosystem recovery**: native status, successional stage, intact forest association
- **Erosion control**: root depth/spread, canopy density, ground cover compatibility
- **Climate resilience**: drought tolerance, heat tolerance, flood tolerance
- **Invasiveness risk**: introduced status, known invasive behavior (negative weight)

### Layer 4: Multi-Species Compatibility & Optimization
"What COMBINATION works?" — this is the real agroforestry/silvopasture/restoration value. Given top-N suitable species, find optimal subsets:
- **Canopy stratification**: emergent + canopy + understory + ground cover layers based on max height and shade tolerance
- **Functional complementarity**: nitrogen fixers + deep rooters + shallow rooters + fruit producers
- **Temporal sequencing**: pioneer → transitional → climax species for phased planting
- **Allelopathy/competition avoidance**: species that don't suppress each other
- **Successional transitions**: commodity plantation (fast-growing timber) → gradual enrichment with native species → native forest over 20-40 years

### Layer 5: Projection & Quantification (Future)
"What outcomes can I expect?" — this requires additional data/models:
- Predicted above-ground biomass over time (needs allometric equations + growth curves per species)
- Carbon sequestration projections (tonnes CO2/ha/yr)
- Economic yield projections (timber volume, fruit yield, NTFP revenue)
- Biodiversity outcome metrics (species richness supported, habitat quality index)

## What Exists Today vs What Needs Building

| Capability | Status | Where |
|-----------|--------|-------|
| Species presence prediction | v2.2 trained, v3 in progress | `orchestrator/train_sinr_model.py` |
| Basic strategy scoring (SAFE-B) | LIVE, 7 strategies | `treekipedia/backend/services/safeb-scorer.js` |
| Species functional trait data | Partial (133 cols, many sparse) | PostgreSQL `species` table |
| Climate/soil site matching | Basic (in SAFE-B abiotic scoring) | `prediction.js` climate envelope |
| Multi-species combination optimization | NOT BUILT | — |
| Composable strategy weighting (sliders) | NOT BUILT (SAFE-B is discrete) | — |
| Successional planning / temporal sequencing | NOT BUILT | — |
| Carbon quantification per species | NOT BUILT (height/longevity proxies only) | — |
| Growth rate / site quality prediction | NOT BUILT | — |
| Allometric equations database | SPARSE (`allometric_models` field) | Species table |
| Native/introduced two-pass inference | DESIGNED, NOT IMPLEMENTED | GO.md |

## Thinking Points for This Session

### 1. Evolving SAFE-B into a Composable Engine
The current SAFE-B has 7 discrete strategies with fixed weights. The evolution is:
- Make weights continuous and user-adjustable
- Allow compound objectives (carbon + food + native)
- Add hard constraints (must-have / must-not-have filters)
- How does the UI expose this without overwhelming users? Progressive disclosure? Presets that users can tweak?

### 2. Site Assessment from v3 Features
v3's temporal features could power an automatic "site assessment" before species recommendation:
- Is this site recently deforested? Stable forest? Agricultural? Urban edge?
- What's the disturbance history?
- What successional stage is appropriate?
- This assessment could auto-configure strategy weights (recently deforested → pioneer species, stable degraded → full restoration mix)

### 3. Species Compatibility Matrix
For multi-species recommendations, we need to know which species work well together. Sources:
- Canopy height stratification (from max_height data)
- Shade tolerance relationships (from tolerances field)
- Nitrogen fixation (benefits neighbors)
- Known agroforestry combinations from literature
- GloBI interaction data (shared pollinators = synergy)
- Could we mine co-occurrence patterns from GBIF? Species that frequently occur together at the same pixels may be naturally compatible.

### 4. Successional Planning Framework
A restoration project isn't a single planting — it's a 20-40 year trajectory:
- Phase 1 (0-3 yr): Pioneer/nurse species — fast canopy closure, nitrogen fixation, soil stabilization
- Phase 2 (3-10 yr): Transitional species — timber, fruit, building structure
- Phase 3 (10-30 yr): Climax species — biodiversity, long-term carbon storage
- The `successional_stage` field in the DB directly supports this, but needs to be operationalized into a planning framework

### 5. The Carbon Gap
No species-level carbon data exists in the system. To close this gap:
- **Quick win**: IPCC Tier 1 default AGB values by biome + growth form (coarse but universal)
- **Medium effort**: Populate `allometric_models` field from GlobAllomeTree database + FIA equations
- **Long term**: Train a model (v4) with GEDI lidar AGB + forest inventory data to predict site-specific biomass

### 6. Commodity-to-Native Transition Modeling
One powerful use case: a farmer has a timber plantation (e.g., Eucalyptus) and wants to transition to native forest over time while maintaining income. The engine could:
- Identify which native species can establish under the existing canopy
- Plan progressive thinning of the commodity species
- Recommend understory natives that tolerate current shade levels
- Project when the canopy transitions from commodity-dominant to native-dominant
- Estimate carbon credit eligibility at each phase

### 7. How This Connects to Silvi's Mission
Silvi does tree planting verification and carbon credits. The suitability engine directly supports:
- **Project design**: recommend species mixes for new planting projects
- **Planting verification**: does the species planted match what's suitable for the site?
- **Carbon estimation**: project-level carbon projections from species mix + site conditions
- **Methodology compliance**: ensure species selection meets Verra/Gold Standard requirements (native species, biodiversity co-benefits)

## Key Files to Read

### Prediction & Recommendation (current system)
- `treekipedia/backend/routes/prediction.js` (~2100 lines) — All prediction/recommendation API endpoints, multi-signal scoring, candidate discovery
- `treekipedia/backend/services/safeb-scorer.js` (~741 lines) — SAFE-B scoring engine, all 7 strategies and their weights
- `orchestrator/location_predictor_FIXED.py` (~1338 lines) — Python GEE sampling service (port 5002)
- `treekipedia/frontend/app/analysis/components/SpeciesRecommenderModal.tsx` (~530 lines) — Frontend recommendation UI

### Model & Training
- `orchestrator/train_sinr_model.py` (~1434 lines) — v2.2 training script
- `orchestrator/unified_gee_sampler_v3.py` (~940 lines) — v3 data pipeline (backfill currently running)
- `orchestrator/sinr_model/` — Model checkpoints, normalization stats, species mapping

### Planning & Research
- `.claude/project-management/GO.md` (~1400 lines) — Master planning doc, full v3 plan, hierarchical subspecies design
- `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md` — v3.0 system design
- `.claude/project-management/RESEARCH_AGB_CARBON_MODELS.md` — Carbon/biomass model research
- `.claude/project-management/RESEARCH_FUNCTIONAL_TRAITS.md` — Functional traits for restoration matching
- `.claude/project-management/DYNAMIC_WEIGHTING_FRAMEWORK.md` — Strategy weighting research
- `.claude/project-management/PREDICTION_RECOMMENDER_IMPLEMENTATION_PLAN.md` — Implementation plan
- `SPECIES_TABLE_COLUMNS.md` — Full 133-column species schema reference

### Database
- `treekipedia/database/current-schema.sql` — Core schema
- `treekipedia/database/06_v11_schema_migration.sql` — Latest migration (climate, WCVP, GloBI, SBTN)

## Important Technical Notes

- **Location predictor on port 5002 uses `lon` NOT `lng`** as query parameter
- **At inference time, sample features at the EXACT query point from GEE**, not nearest training pixel
- **SINR output is independent sigmoids, not softmax** — this is important because it means the model can say "10 species are all highly likely here" which is exactly what you want for recommendations
- **AlphaEarth GEE band names are `A00`, `A01`, ... `A63`**
- **GEE project: `treekipedia-479918`**
- **Species table has dual fields**: `field_ai` and `field_human` — human takes precedence
- **v3 training hasn't started yet** — design work done now should be architecture/strategy-agnostic and work with v2.2 today, getting better when v3 drops
