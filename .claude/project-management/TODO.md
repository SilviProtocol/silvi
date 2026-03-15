# TODO.md - Treekipedia Implementation Plan

> **Reference only** — active task state lives in Beads (`bd ready`). This file preserves architectural vision and phase checklists. Do not manually track task progress here.

See CHANGELOG.md for completed features.

**Reference Docs**:
- [CLAUDE_RESEARCH_AGENTS.md](CLAUDE_RESEARCH_AGENTS.md) - **Expanded 35-field research agents with token tracking**
- [sev-reference/](sev-reference/) - Sev's `latest` branch docs (LEAF scoring, Grok research)
- [TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md](../../TREEKIPEDIA_KNOWLEDGE_ARCHITECTURE.md) - Knowledge model
- [species predictor discussions.md](../../species%20predictor%20discussions.md) - Predictor/recommender vision

---

## Vision: Species Intelligence Engine

Treekipedia is evolving from a static database to a **Species Prediction & Recommendation Engine**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TREEKIPEDIA INTELLIGENCE STACK                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LAYER 1: SPECIES PREDICTOR (AlphaEarth)                                │
│  "Where can this species survive?"                                       │
│  └── 64-band embeddings × cosine similarity → habitat match             │
│                                                                          │
│  LAYER 2: SPECIES RECOMMENDER (LEAF Score)                              │
│  "What trees should I plant here?"                                       │
│  └── Native status × occurrence density × environmental match           │
│                                                                          │
│  LAYER 3: STRATEGY FILTER                                                │
│  "What's the best approach for my goals?"                               │
│  └── Rewilding | Agroforestry | Riparian | Carbon | Biodiversity        │
│                                                                          │
│  LAYER 4: BIODIVERSITY INTELLIGENCE                                      │
│  "What ecological interactions exist?"                                   │
│  └── GloBI data → trophic networks → species interaction richness       │
│                                                                          │
│  LAYER 5: AI RESEARCH ENRICHMENT                                        │
│  "Fill knowledge gaps automatically"                                     │
│  └── Claude agents → 35-field extraction → quality synthesis            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**The "Million-Dollar Question"**: What tree to plant where?

---

## [COMPLETED] - V11 Data Import (Jan 2026)

- [x] Merge `origin/latest` into `djimotreekipedia`
- [x] Create V11 schema migration (23 new columns)
- [x] Import V11 species knowledge (67,743 species, 133 columns)
- [x] Verify WCVP native/introduced data (99.99% coverage)
- [x] Unified admin UI with monitoring tabs

---

## [IMMEDIATE] - Claude Research Agent System

**Status**: Architecture complete, versioning schema created
**Docs**: [CLAUDE_RESEARCH_AGENTS.md](CLAUDE_RESEARCH_AGENTS.md)
**Goal**: Replace broken Research button with specialized Claude agents

### Current Reality
- **67,743 species with AI fields = "NA"** (zero actual research)
- All _ai columns populated with placeholder "NA" values
- No versioning system exists (`researched` column = "NA" for all)

### Expanded Field Coverage (35 fields vs Sev's 25)

| Group | Fields | Agent | Priority |
|-------|--------|-------|----------|
| Identity | 4 | Haiku | HIGH |
| Ecological | 10 | Haiku | HIGH |
| Morphological | 10 | Haiku | HIGH |
| Stewardship + Economic | 11 | Haiku (2 calls) | HIGH/MEDIUM |
| **Synthesis** | All | Sonnet | Required |
| **QC (5% of species)** | All | Opus | As needed |

### Specialized Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RESEARCH ORCHESTRATOR (Port 5003)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │  Identity   │ │  Ecological │ │Morphological│ │ Stewardship │  HAIKU │
│  │  (4 fields) │ │ (10 fields) │ │ (10 fields) │ │ (11 fields) │  70%   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘        │
│         └───────────────┴───────────────┴───────────────┘               │
│                                   │                                      │
│                    ┌──────────────▼──────────────┐                       │
│                    │     SYNTHESIS AGENT         │  SONNET 25%           │
│                    │  Validate + Merge + Score   │                       │
│                    └──────────────┬──────────────┘                       │
│                                   │ (if flagged)                         │
│                    ┌──────────────▼──────────────┐                       │
│                    │        QC AGENT             │  OPUS 5%              │
│                    │   Deep research + Sources   │                       │
│                    └─────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Token Tracking (Per Species)

| Agent | Model | Input | Output | Cost |
|-------|-------|-------|--------|------|
| Identity | Haiku | 800 | 400 | $0.002 |
| Ecological | Haiku | 1,200 | 1,500 | $0.007 |
| Morphological | Haiku | 800 | 800 | $0.004 |
| Stewardship | Haiku | 1,000 | 1,200 | $0.006 |
| Synthesis | Sonnet | 2,000 | 500 | $0.014 |
| **Standard Total** | | 5,800 | 4,400 | **$0.032** |
| QC (if needed) | Opus | 3,000 | 2,000 | $0.195 |
| **Average with 5% QC** | | | | **$0.042** |

### Phase 1: Infrastructure [COMPLETED]
- [x] Create versioning schema (`07_research_versioning.sql`)
- [x] Run versioning migration on local database
- [x] Create `research_queue` table in PostgreSQL (replaces SQLite)
- [x] Create `research_orchestrator.py` service (port 5003)
- [x] Implement `/queue` and `/status/:taxon_id` endpoints
- [x] Connect to Claude Code CLI with WebSearch (via hook auto-approve)

### Phase 1.5: Insight Model (FAIR-Compliant Knowledge Storage)

**Goal**: Store research as atomic insights with provenance, not just flat text fields.

**Why**: Enables source citations, confidence tracking, re-research, and multi-model comparison.

**Schema**: `08_insights_schema.sql`
```sql
-- Atomic units of knowledge with full provenance
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taxon_id VARCHAR(50) REFERENCES species(taxon_id),
    claim_type VARCHAR(100) NOT NULL,  -- e.g., 'maximum_height', 'habitat'
    claim_value JSONB NOT NULL,         -- flexible structure per claim type
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    sources JSONB,                       -- array of {url, title, type, accessed_date}
    model_version VARCHAR(50),           -- e.g., 'claude-3-haiku-20240307'
    created_at TIMESTAMP DEFAULT NOW(),
    supersedes UUID REFERENCES insights(id),  -- for re-research
    is_current BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_insights_taxon ON insights(taxon_id);
CREATE INDEX idx_insights_type ON insights(claim_type);
CREATE INDEX idx_insights_current ON insights(is_current) WHERE is_current = TRUE;
```

**Tasks**:
- [x] Create `08_insights_schema.sql` migration
- [x] Run migration on local database
- [x] Update research agents to output insight format (not just flat JSON)
- [x] Create `/api/insights/:taxon_id` endpoint (GET /species/:taxon_id/insights)
- [x] Sync insights to `*_ai` columns for backward compatibility
- [x] Create auto-sync trigger (`tr_sync_insights_on_insert`)

**Insight Output Format** (per agent):
```json
{
  "insights": [
    {
      "claim_type": "maximum_height",
      "claim_value": {"value": 40, "unit": "meters"},
      "confidence": 0.85,
      "sources": [
        {"url": "https://...", "title": "Flora of Europe", "type": "database"}
      ]
    }
  ]
}
```

### Phase 2: Research via Claude Code CLI [CURRENT]
**Status**: Using Max 5x subscription through Claude Code CLI with WebSearch

Current workflow:
1. User clicks "Research" → Added to `research_queue`
2. Claude Code CLI processes queue with web search enabled
3. Insights saved to `insights` table with provenance
4. Auto-sync trigger updates `species.*_ai` columns

**Model Usage** (via Claude Code subscription):
- Primary: Claude Opus 4.5 (comprehensive research with citations)
- Web search enabled for real-time source verification

**Completed for 6 species**: 200 insights with per-insight confidence + sources

### Phase 3: Frontend Insight Integration [NEXT]
- [x] Research metadata panel (version, avg confidence, insight count)
- [ ] Per-field confidence display with color coding
- [ ] Expandable source citations per insight
- [ ] "Synthetic Knowledge" vs "Verified Knowledge" styling (done)
- [ ] Research button → queue integration (done)

### Phase 4: Scale Research
- [x] 6-species test (complete)
- [ ] 100-species pilot batch
- [ ] Batch research from admin UI
- [ ] Priority queue for user-requested species
- [ ] Sync researched species to production database

---

## [HIGH PRIORITY] - LEAF Scoring Enhancement

**Status**: MVP implemented, needs testing with V11 data

### Current LEAF Algorithm
```
Pool = WCVP natives for region UNION occurrence species
     MINUS species in wcvp_introduced

Affinity = (occurrence_count × tile_count) × native_multiplier
  - Native: ×2.0 boost
  - Unknown: ×1.0 neutral
  - Introduced: EXCLUDED

LEAF Score = percentile rank (0-100)
```

### Enhancements Needed
- [ ] Test LEAF endpoint with V11 WCVP data locally
- [ ] Add invasive species exclusion (integrate GRIIS data)
- [ ] Implement "continuous biome" filtering to prevent cross-biome recommendations
- [ ] Add elevation range filtering (use V11 climate data)
- [ ] Create LEAF score visualization on species page
- [ ] Build frontend component for "What to plant here?" query

### Validation
- [ ] Compare recommendations against Mata Atlantica bio-regional campaign data
- [ ] Document methodology for scientific paper

---

## [COMPLETED] - Species Predictor/Recommender System (Feb 2026)

**Status**: ✅ LIVE — Multi-signal prediction + SAFE-B recommendation system operational
**Master Doc**: [MASTER_PREDICTION_ARCHITECTURE_2.md](MASTER_PREDICTION_ARCHITECTURE_2.md) (v2.0)
**Implementation Doc**: [PREDICTION_RECOMMENDER_IMPLEMENTATION_PLAN.md](PREDICTION_RECOMMENDER_IMPLEMENTATION_PLAN.md)

### Completed

| Component | Status | Details |
|-----------|--------|---------|
| **AlphaEarth v4** | ✅ COMPLETE | 277MB, 3.37M rows, 17,924 species |
| **Habitat Centroids** | ✅ LOADED | 44,625 centroids in pgvector with IVFFlat index |
| **Multi-Signal Predictor** | ✅ LIVE | 3-channel discovery, 5-signal scoring, dynamic weighting |
| **SAFE-B Recommender** | ✅ LIVE | 5-component scoring, 7 strategy presets |
| **Frontend Modals** | ✅ LIVE | Predictor + Recommender + signal breakdowns + pagination |
| **Scoring Tuning** | ✅ DONE | P. radiata rank #42/81% at Auckland NZ (was #103/64%) |

### Prediction Architecture v3.0 Roadmap
**Reference**: [MASTER_PREDICTION_ARCHITECTURE_3.md](MASTER_PREDICTION_ARCHITECTURE_3.md)

- [x] **Phase A: Rejoin gap species** — recovered 4,679 species via pixel data join (DONE Feb 11)
- [x] **Phase B: Re-cluster with DBSCAN** — 2,257 species re-clustered, P. radiata 3→9 clusters (DONE Feb 11)
- [x] **Climate signal completion** — WorldClim BIO (19 vars) + OpenLandMap soil in GEE service (DONE Feb 11)
- [x] **k-NN occurrence table** — 3,084,829 individual occurrence embeddings loaded with HNSW index (DONE Feb 11)
- [x] **Provenance metadata** — GBIF join (95% match), coordinate_uncertainty, establishment_means, occurrence_year, gbif_id per row (DONE Feb 11)
- [x] **Source type classification** — pixel_accurate (92.8%), pixel_disturbed (6.9%), undisturbed_pre2017, triangulated, disturbed_pre2017 (DONE Feb 11)
- [x] **Quality weights** — composite 0-1 per occurrence: coord_uncertainty × temporal_match × source_type (DONE Feb 11)
- [x] **IDF weighting** — 1/log(1+count) per species in species_occurrence_stats table (DONE Feb 11)
- [x] **Update prediction.js Channel 1** — k-NN vote + IDF + quality_weight + centroid blend 60/40 (DONE Feb 11 Session 4)
- [x] **Wire soil signal into /predict** — pH + texture scoring wired as Signal 6 (DONE Feb 11 Session 4)
- [x] **Phase C: GEE export to BigQuery** — 3,454,255 unique pixels with 125 bands exported to BQ (DONE Feb 15)

#### Phase C Data Corrections (BLOCKING — must fix before loading to k-NN)

- [ ] **C1: Year-matched temporal env re-sampling** — Phase C sampled temporal datasets at FIXED modern windows instead of per-occurrence year. Must re-sample TerraClimate, MODIS GPP, Dynamic World, MODIS Burned Area, VIIRS at year-matched dates. Affects all 3.45M Phase C pixels AND 1.48M v4 pixels. Architecture: group pixels by occurrence year, build per-year image stacks, sample in year cohorts.
  - TerraClimate (1958-present): sample at occurrence_year +/-2yr window (not fixed 2015-2020)
  - MODIS GPP (2000-present): sample at occurrence_year (pre-2000: use earliest available)
  - Dynamic World (2015-present): sample at occurrence_year (pre-2015: use ESA WorldCover proxy)
  - MODIS Burned Area (2000-present): cumulative count UP TO occurrence_year (not through 2023)
  - VIIRS (2012-present): sample at occurrence_year (pre-2012: use DMSP-OLS or omit)
  - Hansen lossyear: filter to lossyear <= occurrence_year (only count loss that happened BEFORE observation)
- [ ] **C2: V4 environmental backfill** — 1,477,738 v4-only pixels missing 59 environmental bands. Sample env-only stack (no AlphaEarth re-sampling needed). Year-match temporal vars to v4 orig_year (2017-2024). These are gold-standard year-accurate pixels — must be complete for neural net training.
- [ ] **C3: Regime 3 — nearest undisturbed reference pixels** — For pixels where Hansen lossyear > 0 AND disturbance occurred BEFORE or AT occurrence year: find nearest undisturbed reference pixel within same ecoregion (RESOLVE 2017) + elevation band (SRTM +/-100m) + expanding radius (1km → 5km → 10km). Sample AlphaEarth at reference pixel. Tag with proxy metadata. Essential for Recommender's "what SHOULD grow here" logic.
- [ ] **C4: Disturbance classification during load** — Classify each occurrence using Hansen lossyear vs occurrence_year + SBTN + JRC TMF + ESA WorldCover into source_type categories (pixel_accurate, pixel_disturbed, undisturbed_pre2017, disturbed_pre2017). Apply quality_weight penalties per source_type.
- [ ] **C5: BQ deduplication + export to parquet** — Dedup 503K duplicate rows (from overlapping restarts) on (lat4, lon4), export to local parquet
- [ ] **C6: Rejoin to species** — `regime2_sampler.py --rejoin`: fan out pixel-level data to all species observed at each location. One row per (taxon_id, lat4, lon4) in final output.
- [ ] **C7: Load to k-NN table** — Load corrected Phase C + backfilled v4 data into `species_occurrence_embeddings`. Recompute IDF weights. Rebuild HNSW index. Expected: ~10-15M rows, ~55K species.

#### Remaining Architecture Items

- [ ] **HILDA+ integration** — upload to GEE assets, use for pre-2017 disturbed site reference pixel lookup (1960-2019 annual LUC at 1km, already in PANGAEA). Improves Regime 3 reference pixel matching but NOT a prerequisite for C3.
- [ ] **Forest Stability Index** — 6-signal composite from JRC TMF + CCDC + GEDI + ORNL + LandTrendr + Hansen. Signal 7 in prediction.js.
- [ ] **Disturbance-aware invasive prediction** — at disturbed sites: upweight invasive/introduced occurrences at disturbed pixels, downweight native-at-intact; at intact sites: reverse. Use GRIIS + establishment_means for species-level native/invasive classification
- [ ] **Ecoregion-constrained search** — tag occurrences with WWF/RESOLVE ecoregion, constrain k-NN reference pixel search to same ecoregion
- [ ] **GRIIS invasive species data** — join Global Register of Introduced and Invasive Species per country per species
- [ ] **GMM extension** — diagonal Gaussian Mixture Models for species with >100 occurrences
- [ ] **Neural prediction head** — SINR-style (64-D → 256 → ResBlock×4 → 60K species), trains on k-NN table. BLOCKED on C1-C7 completion (need correct, complete training data).
- [ ] **Foundation model Phase 2** — Clay v1.5 for pre-2013 Landsat (if projection quality < threshold)
- [ ] Migrate legacy `/api/embeddings/predict` to multi-signal (deferred)

### Key Files
| File | Purpose | Lines |
|------|---------|-------|
| `treekipedia/backend/routes/prediction.js` | Multi-signal predict + recommend endpoints | ~1930 |
| `treekipedia/backend/services/safeb-scorer.js` | SAFE-B scoring engine (5 components, 7 strategies) | ~710 |
| `treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx` | Point prediction UI with signal bars + pagination | ~685 |
| `treekipedia/frontend/app/analysis/components/SpeciesRecommenderModal.tsx` | Recommender UI with strategy selector | ~400 |
| `treekipedia/frontend/app/analysis/components/MapClickHandler.tsx` | Map click → Predict/Recommend mode selector | ~220 |
| `orchestrator/location_predictor_FIXED.py` | Python GEE service (multi-year AlphaEarth + SRTM + Hansen) | ~280 |

### External Datasets to Acquire / Integrate
| Dataset | Priority | GEE ID / Source | Status |
|---------|----------|-----------------|--------|
| WorldClim V1 BIO (19 vars) | 🔴 P0 | `WORLDCLIM/V1/BIO` (on GEE) | Ready to integrate |
| OpenLandMap Soil (6 props) | 🔴 P0 | `OpenLandMap/SOL/*` (on GEE) | Ready to integrate |
| Hansen GFC v1.11 | ✅ Done | `UMD/hansen/global_forest_change_2023_v1_11` | Already in pipeline |
| SRTM Elevation | ✅ Done | `USGS/SRTMGL1_003` | Already in pipeline |
| Landsat 5/7/8/9 (historical) | 🟡 P1 | `LANDSAT/L*/C02/T1_L2` | For triangulation Phase 4 |
| MODIS NDVI/EVI | 🟡 P1 | `MODIS/061/MOD13A1` | For triangulation Phase 4 |
| Dynamic World | 🟡 P1 | `GOOGLE/DYNAMICWORLD/V1` (2015+) | For triangulation Phase 4 |
| TRY Traits | 🟡 P2 | https://www.try-db.org/ | Application pending |
| GRooT Root Traits | 🟢 P3 | https://github.com/MathieuTWOTWO/GRooT | Future |
| Human Footprint Index | 🟢 P3 | https://wcshumanfootprint.org/ | Future |

### Foundation Models Evaluated
| Model | Status | Viability for Our Use Case |
|-------|--------|---------------------------|
| **Clay v1.5** (632M) | Best candidate | Wavelength-parameterized, multi-sensor, 1024-D. Best for pre-2013 but untested on Landsat 5/7 |
| **Prithvi-EO-2.0** (600M-TL) | Good for 2013+ | Location+time aware, trained on HLS. Cannot handle pre-2013 Landsat |
| **SatMAE** | Skip | Academic, no Landsat support, superseded by Prithvi/Clay |
| **AlphaEarth** | Current production | 64-D, 2017-2024, on GEE. Our primary embedding space |

---

## [COMPLETED] - Strategy Layer Implementation (Feb 2026)

**Status**: ✅ LIVE — 7 strategies with distinct weight profiles and trait scoring

### Implemented Strategies
| Strategy | Focus | Include Introduced? | Key Traits Boosted |
|----------|-------|---------------------|-------------------|
| **General** | Balanced restoration | Yes | Tree growth form |
| **Rewilding** | Native, ecological integrity | No | Late-successional, wildlife support |
| **Agroforestry** | Food/timber production | Yes | Multi-use, nitrogen fixing, food production |
| **Riparian** | Water quality, bank stabilization | Native preferred | Flood tolerance, bank stabilization |
| **Carbon** | Maximum sequestration | Depends on region | Tall trees, long-lived, timber quality |
| **Biodiversity** | Species diversity | No | Interaction richness, structural diversity |
| **Erosion Control** | Soil stabilization | Yes | Pioneer/fast establishing, deep roots |

### Completed Tasks
- [x] Strategy weight presets in SAFE-B scorer (7 strategies × 5 components)
- [x] Strategy-specific candidate discovery (Channel 3: WCVP-native, agroforestry, flood-tolerant, etc.)
- [x] Frontend strategy selector in SpeciesRecommenderModal
- [x] Verified different top-3 per strategy (general: Kauri, rewilding: Manuka, carbon: Quercus robur)

---

## [MEDIUM PRIORITY] - Biodiversity Intelligence Features

**Status**: GloBI data imported in V11, frontend needs update

### Available Data (V11)
- `globi_pollinatedby` - Pollinators
- `globi_eatenby` - Herbivores
- `globi_flowersvisitedby` - Flower visitors
- `globi_hasparasite` - Parasites
- `globi_haspathogen` - Pathogens
- `globi_hasdispersalvector` - Seed dispersers
- `globi_preyeduponby` - Predators
- `globi_hasparasitoid` - Parasitoids

### Tasks
- [ ] Create species interaction visualization component
- [ ] Build trophic network graph view
- [ ] Implement "Species Interaction Richness" calculation
- [ ] Add interaction search ("Show species that attract pollinators")
- [ ] Calculate connectivity potential for restoration planning

### Future: Josh Adler Collaboration
- [ ] Explore SIRU (Species Interaction Richness Unit) integration
- [ ] Consider RCF Tensor approach for network monitoring
- [ ] Potential biodiversity credit methodology pilot

---

## [MEDIUM PRIORITY] - Occurrence Data Import (96.5M)

**Status**: Parquet file ready, import script needs adaptation

### Data Source
- File: `Treekipedia_LatLong_ONLY_TaxonId_CORRECT_december_18d_2025.parquet`
- Records: 96.5 million occurrences
- Size: 526 MB compressed

### Tasks
- [ ] Adapt Sev's `import_geohash_parquet.py` script
- [ ] Run test import with 1M records
- [ ] Verify geohash tile generation at L7 precision
- [ ] Full import (estimate: 4-6 hours)
- [ ] Rebuild spatial indexes
- [ ] Update occurrence counts in species table
- [ ] Verify LEAF scoring uses new data

---

## [HIGH PRIORITY] - Knowledge Architecture & Ontology

**Status**: Insights table operational, needs RDF/nanopub structure for scaling
**Goal**: Build FAIR-compliant knowledge that can train ML models and enable semantic queries

### Current Insight Structure (Working)
Each insight already has:
- `claim_type` - Field being described (e.g., "maximum_height", "habitat")
- `claim_value` - Structured JSONB data with text/values
- `confidence` - 0.0-1.0 per-insight confidence score
- `sources` - Array of citations with URLs, titles, types, credibility scores
- `model_version` - Which AI model generated the insight

### Architecture Decision: Nanopublications vs RDF Triples

**Option A: Nanopublications** (Recommended for provenance-rich data)
```
Nanopub = {
  assertion: "Adansonia digitata maximum_height 25m",
  provenance: {model: "claude-opus-4-5", date: "2026-01-06", confidence: 0.92},
  publication_info: {sources: [...], license: "CC-BY"}
}
```
- Better for tracking provenance, versioning, and retractions
- Well-suited for AI-generated knowledge with uncertainty
- Established standard in life sciences (FAIR principles)

**Option B: RDF Triples** (Simpler, wider tooling)
```turtle
:species_baobab :hasMaximumHeight "25m"^^xsd:string .
:species_baobab :nativeToEcoregion :ecoregion_african_savanna .
```
- Simpler query patterns (SPARQL)
- Better integration with existing ontologies (Darwin Core, ENVO)
- Easier for ML model training

**Recommended Hybrid Approach:**
- PostgreSQL + PostGIS for operational queries (current)
- Export to nanopublications for provenance-rich knowledge sharing
- RDF triples for ML training datasets and semantic queries

### Phase 1: Frontend Insight Display [COMPLETE]
- [x] Show per-insight confidence in species page (not just average)
- [x] Display source citations with clickable links per field
- [x] Color-code confidence levels (green ≥85%, amber ≥70%, red <70%)
- [x] Add "View Sources" expandable section per insight
- **Implementation**: DataField.tsx shows confidence bar + expandable sources per AI field

### Phase 2: Ontology Export Pipeline [IN PROGRESS]
- [x] Create `export_to_rdf.py` script for insights → triples conversion
- [x] Map claim_types to Darwin Core / ENVO / PATO ontology terms (35 fields mapped)
- [x] Generate N-Quads with provenance graphs for nanopub compatibility
- [x] Export JSONL format for ML training datasets
- [ ] Design formal Treekipedia OWL ontology file (species, traits, habitats, interactions)
- **Script**: `treekipedia/scripts/export_to_rdf.py` supports turtle, nquads, jsonl, jsonld

### Phase 3: Knowledge Graph Infrastructure [IN PROGRESS]

**Completed (Jan 7, 2026):**
- [x] Atomic insights architecture (multiple insights per claim_type)
- [x] Database migration: `08_atomic_insights_architecture.sql`
- [x] Aggregation functions + triggers (insights → species._ai auto-sync)
- [x] Content hash deduplication for insights
- [x] Lean RDF exporter: `orchestrator/lean_rdf_exporter.py`
- [x] IPFS version archiver: `orchestrator/ipfs_archiver.py`
- [x] Atomic research prompts: `orchestrator/atomic_research_prompts.py`

**Blocked - Need Credentials:**
- [ ] **FUSEKI_PASSWORD** - Get from server admin (Fuseki at 167.172.143.162:3030 requires auth)
- [ ] **LIGHTHOUSE_API_KEY** - Get from Lighthouse dashboard for IPFS uploads

**Once credentials obtained:**
- [ ] Upload lean RDF to production Fuseki
- [ ] Test SPARQL federation queries
- [ ] Archive first species versions to IPFS
- [ ] Document RDF schema and SPARQL query patterns

### Phase 4: ML Training Dataset Generation
- [x] Export cleaned insights as JSONL for fine-tuning (via export_to_rdf.py --format jsonl)
- [ ] Create species embeddings from trait vectors
- [ ] Build training set: (species, location, traits) → survival probability
- [ ] Version datasets with DVC or similar

### Ontology Alignment Targets
| Treekipedia Field | Darwin Core | ENVO | Notes |
|-------------------|-------------|------|-------|
| species_scientific_name | dwc:scientificName | - | Core taxonomy |
| habitat | dwc:habitat | ENVO:habitat | Map to ENVO terms |
| maximum_height | dwc:measurementValue | - | Add units ontology |
| wcvp_native | dwc:countryCode | - | Geographic distribution |
| conservation_status | dwc:occurrenceStatus | - | IUCN status mapping |
| elevation_ranges | - | ENVO:elevation | Numeric ranges |

### GraphFlow Admin UI (Existing)
- Admin UI at `/admin` with 7 pages
- Python microservice for ontology generation
- Fuseki SPARQL endpoint configured (needs activation)

---

## [LOW PRIORITY] - Technical Debt & Infrastructure

### Code Quality
- [ ] Fix species search endpoint (column name mismatch)
- [ ] Add comprehensive error handling
- [ ] Write tests for critical endpoints
- [ ] Document API changes

### Database Optimization
- [x] Add indexes on WCVP columns (done in V11 migration)
- [ ] Optimize cross-analysis query performance
- [ ] Archive backup tables to separate schema
- [ ] Monitor query performance with larger analyses

### Monitoring
- [ ] Set up query performance monitoring
- [ ] Add logging for analysis usage patterns
- [ ] Implement rate limiting if needed

---

## Backlog (Unprioritized)

- [ ] Mobile app or PWA
- [ ] Increase image coverage from 20% to 50%
- [ ] Pre-compute predictions for popular locations
- [ ] Show prediction confidence as heatmap overlay
- [ ] E2E tests with Playwright
- [ ] Unit tests for Python endpoints
- [ ] API rate limiting for public access
- [ ] Historical embedding analysis (predict past species composition)

---

## Key Metrics to Track

| Metric | Current | Target |
|--------|---------|--------|
| Species with WCVP data | 67,742 (99.99%) | 100% |
| Species researched | 6 (0.01%) | 10% by Q2 2026 |
| Total insights | 200 | 350k (35 per species × 10k) |
| **Species with centroids** | **22,603 (Phase A+B complete)** | **60,000+ (after Phase C)** |
| **Habitat centroids** | **49,640** | ~150k (expanded + re-clustered) |
| **Prediction signals** | **5 (upgrading to 7)** | 7 (emb+spatial+range+eco+climate+soil+FSI) |
| **k-NN occurrence embeddings** | **3,084,829 (with provenance)** | ~10-15M (after Phase C: 4.2M pixels × ~3 species/pixel) |
| **Matching method** | **k-NN loaded (HNSW built), prediction.js update pending** | k-NN → GMM → Neural head (129-D input after Phase C) |
| **Recommender strategies** | **7** | 7+ |
| **P. radiata benchmark** | **Rank #42, 81% @ Auckland (9 clusters incl NZ)** | Top 20 (after k-NN + FSI) |
| AlphaEarth embeddings | 3.37M records (v4) + 9K Phase A | ~10M (after Phase C) |
| Occurrence records | 5.7M tiles | 96.5M processed |

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LOCAL DEVELOPMENT                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)          http://localhost:3001                      │
│  Backend API (Express)       http://localhost:5001                      │
│  Location Predictor (Python) http://localhost:5002                      │
│  Research Orchestrator       http://localhost:5003 ✅ RUNNING           │
│  PostgreSQL 17 + PostGIS     localhost:5432                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Sync
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION (Digital Ocean)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  API: https://treekipedia-api.silvi.earth                               │
│  Frontend: https://treekipedia.silvi.earth (Vercel)                     │
│  Database: PostgreSQL 17 + PostGIS                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Documentation References

| Document | Purpose | Location |
|----------|---------|----------|
| GO.md | Onboarding procedure | This folder |
| ACTIVE.md | Current system status | This folder |
| CHANGELOG.md | Version history | This folder |
| CLAUDE_RESEARCH_AGENTS.md | Research agent architecture | This folder |
| CLAUDE.md | Development guide | Parent folder |
| 07_research_versioning.sql | Database versioning schema | database/ |
| species predictor discussions.md | Vision document | Root |
| Djimo x Josh notes | Biodiversity intelligence | Root |

---

*Last Updated: February 11, 2026 (v3.0 Architecture)*
