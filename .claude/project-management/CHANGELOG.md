# CHANGELOG - Treekipedia

Complete history of features, fixes, and improvements. For current status see ACTIVE.md, upcoming work see TODO.md.

**WRITING STYLE**: Use telegraphic style for all entries. Omit articles (a, an, the), conjunctions where possible. Maintain specificity: include file references, error details, technical accuracy.

---

## February 2026

### 2026-02-18 (Session 8) - Scoring v3: Subtaxa Merging, Context-Dependent IDF, Multi-Scale k-NN + 3 New GEE Variables

**SCORING** - prediction.js v3 (`multi-signal-v3-subtaxa-idf-multiscale`)
- Subtaxa merging: All `-XX` suffixed taxon_ids accumulated at species root level. 4,044 species (11.3%) have multiple subtaxa; votes now combine. Best subtaxon tracked as metadata.
- Context-dependent IDF: IDF moved from SQL to JS. When `embedding_homogeneity > 0.85`, IDF softened by blending full IDF (`1/log(1+n)`) with dampened IDF (`1/log(1+sqrt(n))`). Factor ramps 1.0→0.30 across homogeneity 0.85→0.95.
- Multi-scale k-NN: Single k=500 query, split into fine (top-50) and broad (all 500) raw votes, blended 40%/60%.
- Embedding score fix: k-NN now uses `max(knnNorm, centroidNorm) + 0.1*min()` instead of weighted average. k-NN can only boost, never penalize relative to centroid.
- File: `treekipedia/backend/routes/prediction.js` — Channel 1a (L289-500), composite scoring (L1011-1035)

**GEE** - 3 new variables in location_predictor_FIXED.py (v4)
- `embedding_homogeneity`: 3×3 grid at 100m spacing, 9 AlphaEarth samples, mean pairwise cosine similarity. NZ test site: 0.9075 (confirms monoculture signal).
- `ccdc_last_break` + `ccdc_num_breaks`: Google CCDC V1 (Landsat, 30m, 1999-2019). NZ test: 0 breaks (plantation pre-dates CCDC).
- `canopy_height_mean_m` + `canopy_height_stddev_100m`: ETH Global Canopy Height 2020 (10m). NZ test: mean=28.3m, stddev=1.91m (very uniform — strong monoculture signal).
- Processing time increased ~3s→~8.5s per /sample call due to 3 additional GEE requests.
- File: `orchestrator/location_predictor_FIXED.py` — new functions at L198-396

**RESULTS** - P. radiata ranking at NZ plantation site (-41.15236, 175.09987)
- Before: rank #16, score=88, embedding_signal=71
- After: rank #26, score=99.3%, embedding_signal=100
- Score improved dramatically (88→99). Rank dropped because native NZ species now ALSO score higher (many hit 100%) due to the embedding score fix benefiting all species equally.
- P. radiata's WCVP data doesn't list NZ as introduced — genuine data gap affecting range score (90 instead of 95).
- 25 native NZ species correctly rank above P. radiata — they genuinely grow in this ecoregion.
- Next improvement needed: managed-forest probability signal using CCDC + canopy height variance to boost plantation species at monoculture sites.

**DOCS** - Research saved
- Created `RESEARCH_AGB_CARBON_MODELS.md` — TorchGeo, DINOv2, Clay, Prithvi research for future AGB/carbon estimation work. Allometric approach documented as near-term option.

### 2026-02-16 (Session 6) - C1+C2 Production Complete + C3 Reference Pixel Search Built & Running

**DATA** - C1+C2 temporal re-sampling + V4 backfill PRODUCTION RUN
- `temporal_env_sampler.py` ran ~12 hours with 6 bug fixes applied (Session 5)
- Phase C temporal: `phase_c_temporal_env_v1` — 4.89M+ rows, 12 year-matched temporal bands
- V4 backfill: `v4_env_backfill_v1` — 1.53M+ rows, 68 environmental bands
- 99% success rate, 31 failures across 3,095 batches
- Run command: `PYTHONUNBUFFERED=1 nohup python3 -u orchestrator/temporal_env_sampler.py --all --pool-size 25 --resume-from-bq`

**FIX** - AlphaEarth `.first()` vs `.mosaic()` critical bug
- AlphaEarth V1/ANNUAL has 11,074 tiles per year (2023). `.first()` returns ONE arbitrary tile.
- Probability of that tile covering any random global point: ~0.01%
- This was the "AlphaEarth coverage gap" blocker that stalled C3 in Session 5
- Fix: `.mosaic()` merges all tiles into a single global image with full coverage
- Verified: all 10 global test points (Amazon, Congo, Borneo, California, Germany, etc.) return data
- regime2_sampler.py already used `.mosaic()` (line 132) — regression in new C3 code

**FEATURE** - C3 Regime 3 reference pixel search (`regime3_reference_sampler.py`)
- Dual-mode search for 194,824 disturbed pixels (Hansen loss > 0, lossyear > 0):

  **--fast mode (proximity-based)**:
  - Finds nearest undisturbed pixel by physical distance within 10km buffer
  - Constraints: treecover2000 >= 25%, loss == 0, elevation +/-100m
  - 2000 pixels/batch, ~14 min/task, ~5.5 hrs total
  - 99.95% success rate (test: 1999/2000 found), avg reference distance 107m
  - Output: `regime3_reference_fast_v1`
  - RUNNING: PID 46090, 98 batches

  **--spectral mode (spectral-similarity)**:
  - Builds pre-disturbance Landsat composite (2 yrs before lossyear, 11 bands: 6 SR + 5 indices)
  - Finds undisturbed candidate whose CURRENT spectral signature best matches pre-disturbance state
  - 50 pixels/batch at 250m search scale, ~12 min/task, ~10 days total
  - 100% success rate in testing (50/50), but 100px/batch causes GEE OOM
  - Output: `regime3_reference_spectral_v1`
  - Not yet launched (will run in background after fast completes)

  Both versions sample AlphaEarth 2023 `.mosaic()` at reference pixel + add SRTM anchor band

**ARCHITECTURE** - Lossyear cohort batching for spectral mode
- Pixels grouped by lossyear before batching — each batch shares ONE pre-disturbance composite
- Eliminates expensive `ee.Algorithms.If` conditional chain (9+ branches = massive GEE expression tree)
- Measured: mixed-lossyear batch (10px) > 20 min timeout; single-lossyear batch (50px) = 12 min

**DISCOVERY** - GEE throughput characteristics
- GEE allocates ~3-4 concurrent worker slots regardless of pool size (25, 50, etc.)
- sampleRegions tasks: ~7 min/2000px (temporal sampler, no per-pixel reduceRegion)
- Mapped reduceRegion tasks: ~14 min/2000px (C3 fast, per-pixel spatial search)
- Mapped reduceRegion + Landsat: ~12 min/50px (C3 spectral, per-pixel with composites)
- Running two pipelines simultaneously: tasks share the 3-4 GEE worker slots FIFO

**FILES**: regime3_reference_sampler.py (new, ~1100 lines), GO.md (C3 dual strategy documented), CHANGELOG.md

### 2026-02-15 (Session 5) - Phase C GEE Export Complete + Critical Data Quality Audit

**DATA** - Phase C GEE export to BigQuery COMPLETE
- 3 runs total (wifi drops required kill/restart between runs, no data lost)
- Run 1: 273/502 batches before stall, Run 2: 126/447 before stall, Run 3: 447/447 complete
- 4th run (853K remaining pixels): 427/427 complete, confirmed ceiling reached
- Final BQ state: 3,957,403 rows, 3,454,255 unique pixels, 130 columns, zero nulls across all bands
- BQ table: `treekipedia-479918.species_data.phase_c_embeddings_env_v1`
- 503,148 duplicate rows from overlapping restarts (dedup at export, not a data issue)
- AlphaEarth coverage ceiling: ~82% of target pixels (remaining ~18% = no AlphaEarth tile coverage)
- Elevation confirmed: SRTM 30m, 0 nulls, range -412m (Dead Sea) to 5,844m, 33% coastal 0-100m

**AUDIT** - Critical data quality issues identified in Phase C data

Three compounding errors found that must be corrected before loading to k-NN table:

**Issue 1: Temporal environmental variables NOT year-matched to occurrences**
- Phase C sampler uses FIXED date ranges for temporal datasets instead of per-occurrence year
- Occurrences span 1960s-2016 but env data sampled at arbitrary modern windows
- Affected datasets and what sampler currently does vs what it SHOULD do:

| Dataset | GEE Temporal Range | Current Sampling | Correct Sampling | Error Impact |
|---------|-------------------|------------------|------------------|--------------|
| TerraClimate (VPD, AET, soil moisture, PDSI, deficit, solar) | 1958-present (monthly) | Fixed 2015-2020 mean | Year-matched to occurrence year (or +/-2yr window) | HIGH - drought/water conditions vary enormously by decade |
| MODIS GPP | 2000-present (annual) | Fixed 2015-2023 mean | Year-matched (2000+ only; pre-2000 use earliest available) | MEDIUM - productivity varies with climate cycles |
| Dynamic World | 2015-present (10m, near-real-time) | Fixed 2023 mode | Year-matched (2015+ only; pre-2015 use ESA WorldCover as proxy) | MEDIUM - land cover changes over decades |
| MODIS Burned Area | 2000-present (monthly) | Cumulative count 2001-2023 | Cumulative count UP TO occurrence year | MEDIUM - overstates fire at observation time |
| VIIRS Nighttime Lights | 2012-present (monthly) | Fixed 2022 annual | Year-matched (2012+ only; pre-2012 use DMSP-OLS) | LOW-MEDIUM - urbanization proxy changes over time |

- Datasets that are CORRECTLY static (no year-matching needed):
  - WorldClim BIO 1-19 (30-year climate normals, static)
  - OpenLandMap soil (static surface properties)
  - SRTM elevation + terrain derivatives (static)
  - MERIT Hydro (static)
  - Hansen treecover2000 baseline (static, year 2000)
  - Hansen lossyear (static cumulative through 2023 - BUT could be filtered to <=occurrence year)
  - JRC Global Forest Types 2020 (single snapshot)
  - ESA WorldCover 2021 (single snapshot)
  - SBTN Natural Lands 2020 (single snapshot)
  - GEDI canopy height (composite, quasi-static)
  - ORNL Biomass (single snapshot ~2010)
  - CSP Human Modification (single snapshot ~2016)
  - RESOLVE Ecoregions (static)
  - CSP Topographic Diversity (static)
  - JRC Global Surface Water (cumulative summary)

**Issue 2: V4 data (1.78M pixels, 17,924 species) missing 59 environmental bands**
- V4 parquet has: 64 AlphaEarth embeddings + elevation + treecover2000 + lossyear + loss + gain (74 cols)
- V4 is MISSING: bio01-19, soil (7), terrain derivatives (3), GEDI (2), biomass, fire, nightlights, human modification, JRC TMF (2), ESA WorldCover, Dynamic World, SBTN, MERIT Hydro (2), TerraClimate (6), MODIS GPP, ecoregion (2), topo diversity, JRC surface water (3)
- V4 pixels were EXCLUDED from Phase C sampling (line 575 of regime2_sampler.py)
- 1,477,738 v4-only pixels have NO environmental data beyond elevation+treecover
- These are the GOLD STANDARD pixels (year-accurate 2017-2024 embeddings) — cannot be incomplete for neural net training
- Fix: env-only backfill sampler that samples 61 env bands at v4 pixel locations (no AlphaEarth re-sampling needed)
- For v4 pixels: temporal env variables should be year-matched to ORIG_YEAR (which is 2017-2024 for v4)

**Issue 3: Regime 3 (disturbed pixel handling) NOT implemented**
- Phase C sampler treats ALL pixels identically regardless of disturbance status
- 232,214 BQ pixels (5.9%) have Hansen lossyear > 0 (forest loss detected)
- 2,502,121 BQ pixels (63.2%) are SBTN non-natural land
- 440,913 BQ pixels (11.1%) are ESA built-up
- For disturbed pixels, the 2017 AlphaEarth embedding reflects POST-DISTURBANCE state — useless for characterizing original habitat
- Per PRE_ALPHAEARTH_TRIANGULATION_PLAN.md Regime 3, the correct approach is:
  1. Detect disturbance (Hansen lossyear > 0, or lossyear <= occurrence_year for "observed after disturbance")
  2. Search for nearest undisturbed reference pixel within: same ecoregion (RESOLVE), elevation band (SRTM +/-100m), radius 1-5-10km expanding
  3. Sample AlphaEarth at the reference pixel as proxy embedding
  4. Tag with proxy metadata (proxy=true, proxy_type=nearest_undisturbed, proxy_distance_m)
  5. If no undisturbed neighbor found within 10km: fall back to historical Landsat spectral feature vector (Strategy 4)
- This is essential for the Recommender ("what SHOULD grow here") — it needs the REFERENCE habitat, not the current disturbed state
- HILDA+ (1960-2019 land use at 1km) would further improve reference pixel matching but is not a prerequisite

**PROCESS** - Rolling pool sampler resilience on airplane wifi
- Network drops cause `ee.data.getTaskStatus()` to hang indefinitely
- Process stays alive (PID exists) but polling loop stalls, no new tasks submitted
- Diagnosis: memory drops from ~140MB to ~4MB (Python releasing objects during blocked I/O)
- Fix: kill PID, restart with `--resume-from-bq`. No work lost.
- Three restarts needed across ~8 hours total runtime

**FILES**: CHANGELOG.md, TODO.md, GO.md, GEE_PIPELINE_REFERENCE.md (all updated with audit findings)

### 2026-02-11 (Session 4) - k-NN Prediction Live + Phase C Launched (4.2M pixels, 2105 GEE tasks)

**FEATURE** - prediction.js: k-NN + soil scoring fully wired and tested
- /predict Channel 1a: k-NN on species_occurrence_embeddings (HNSW, top-500 neighbors, IDF-weighted)
- /predict Channel 1b: centroid fallback for species not in k-NN top-500
- 6-signal composite scoring: embedding, spatial, range, ecoregion, climate, soil
- Soil scoring (Signal 6): pH categorical matching with adjacency + texture broad group matching
- Dynamic weighting: 4 buckets (strong-embedding, balanced, spatial-only, embedding-only) with 6 weights summing to 1.0
- /recommend endpoint also upgraded to k-NN Channel 1a + centroid Channel 1b
- Scoring version: multi-signal-v2-knn

**FIX** - k-NN embedding score normalization
- Problem: common species with high IDF penalty (e.g. P. radiata, 2808 occ, IDF=0.13) scored poorly via pure k-NN
- P. radiata at Wairarapa plantation: k-NN weighted_score=0.21 → normalized to 0.30, despite centroid similarity 0.92
- Solution: blend 60% k-NN normalized + 40% centroid normalized for k-NN species
- P. radiata after: embScore=0.58 (was 0.30), final score=83 rank #73 (was rank #118)

**FIX** - Column casing: 10 references to quoted "pH_dominant", "Soil_texture_dominant" etc. in SQL
- PostgreSQL columns are lowercase (ph_dominant, soil_texture_dominant) — quoted mixed-case caused query failures
- Fixed in both /predict and /recommend endpoints

**FIX** - Spatial-only species data fetch missing soil columns
- Query at line ~547 fetched climate columns but not ph_dominant, ph_tolerated, soil_texture_dominant, soil_texture_tolerated
- Spatial-only species always got default 0.5 soil score instead of actual match

**FIX** - spatial_min_distance merge bug: addCandidate merge logic didn't overwrite Infinity defaults
- Species discovered by embedding first had spatial_min_distance stuck at Infinity
- Added Infinity to overwrite conditions in merge loop

**FIX** - regime2_sampler.py: 8 GEE dataset errors preventing task submission
- 5 ImageCollection-vs-Image errors: ESA WorldCover v200, NASA ORNL biomass, CSP Human Modification, LARSE GEDI, JRC TMF (TransitionMap + DegradationYear) — all are ImageCollections requiring .mosaic()
- 3 band name errors: NASA ORNL agbd→agb, GEDI rh98→p95 + fhd→shan, JRC TMF Map→TransitionMap_Subtypes + DegradationYear band is 'constant'
- OpenLandMap soil pH path: SOL_PH-H2O_USDA-A614_M→SOL_PH-H2O_USDA-4C1A2A_M (wrong method code)
- MODIS GPP: updated from deprecated 006→061 catalog

**DATA** - Phase C LAUNCHED: 4,209,371 pixels across 2,105 GEE tasks
- Test batch (100 pixels): completed in 2 min, 129 columns in BigQuery confirmed
- Full launch: nohup background process (PID 53478), ~17 tasks/min submission rate
- BQ table: treekipedia-479918.species_data.phase_c_embeddings_env_v1
- Task manifest: orchestrator/expansion_phase_c/phase_c_tasks_*.json
- Known issue: 2 early tasks failed with schema mismatch (jrc_forest_type STRING vs INTEGER), test table deleted
- After completion: export parquet, rejoin species, load to k-NN table (~10-15M rows)

**BENCHMARK** - P. radiata at Wairarapa plantation (-41.153, 175.099)
- Rank #73, score 83 (multi-signal-v2-knn)
- Signals: emb=58, spatial=95, range=90, eco=100, climate=72, soil=85
- k-NN: 3 hits from 500 neighbors, weighted_score=0.21, IDF=0.13
- 211 spatial tiles within 50km, nearest at 3.97km
- native_status=unknown (WCVP doesn't list NZ for P. radiata — data gap)

**FILES**: prediction.js (~2288 lines), regime2_sampler.py (fixes), CHANGELOG.md

### 2026-02-11 (Session 3) - Phase C Sampler Built + Corrected Scope (4.2M pixels, 129 bands)

**BUILD** - regime2_sampler.py: Full Phase C sampling pipeline
- Samples AlphaEarth 2017 + 65 environmental bands at 4,209,371 pre-2017 occurrence pixels not in v4
- Environmental stack organized by resolution for efficient GEE sampling:
  - 10m: AlphaEarth (64), JRC Forest Types, ESA WorldCover, SBTN Natural Lands, Dynamic World 2023
  - 30m: SRTM (elev/slope/aspect/hillshade), Hansen GFC (4 bands), JRC TMF (2), JRC Surface Water (3)
  - 90m: MERIT Hydro (HAND, upstream area)
  - 250m: OpenLandMap soil (pH, clay, sand, OC, texture, bulk density, water content), CSP topo diversity
  - 300m: ORNL Biomass
  - 500m: MODIS GPP, MODIS fire frequency, VIIRS nighttime lights
  - 1km: WorldClim BIO (19), GEDI (canopy height + FHD), CSP Human Modification, RESOLVE Ecoregions (eco_id + biome_num)
  - 4km: TerraClimate (VPD, AET, soil moisture, PDSI, water deficit, solar radiation)
- Total: ~129 bands per pixel (64 embedding + 65 environmental)
- Features: batch export to BigQuery (2000 pts/task), checkpoint/resume, batch range for parallel runs, species rejoin post-export
- Script: orchestrator/regime2_sampler.py (~650 lines)

**CORRECTION** - Phase C scope was massively underestimated
- Previous estimate: 189,233 pixels for 37,605 species (only counted species with zero embeddings)
- Corrected: 4,209,371 pixels covering 59,280 species (37,308 new + 21,972 enriching existing)
- Root cause: previous scoping only asked "which species have no embeddings?" instead of "which occurrence pixels haven't been sampled?"
- Pre-2017 occurrences: 76.4M rows, 58.8M after precision filter (>=3dp), 4.5M unique pixels, 4.2M not in v4
- Coordinate precision filter: rejects <=2dp coordinates (~23% of pre-2017 data), useless at 10m pixel resolution
- After Phase C: ~55,000 species with embeddings (up from 22,604), ~10-15M k-NN rows (up from 3M)
- GEE cost: ~2,105 tasks at 2000 pts/task, within free tier

**ANALYSIS** - Existing data inventory for Phase C
- GBIF occurrence parquet: only coordinates + year + taxon_id useful; elevation 1.8% populated, establishment means 3.8%
- V11 species knowledge: climate/soil/biome preferences at 88-90% coverage, but aggregated per-species, not per-pixel
- Environmental extractions (WorldClim, soil, NDVI): exist for subset of v4 points in separate parquets, not joined
- Conclusion: must sample everything fresh at each pixel via GEE (one-shot opportunity to build complete neural net training dataset)

### 2026-02-11 (Session 2) - k-NN Table Loaded + Provenance + Source Classification

**DATA** - Loaded 3,084,829 individual occurrence embeddings with provenance metadata
- Built HNSW index (m=16, ef_construction=200): 1.2GB, ~60ms per k-NN query on 3M vectors
- Joined GBIF provenance from 96M-row occurrence parquet at 95% match rate (3dp lat/lon join)
- New columns per row: coordinate_uncertainty_m, establishment_means, occurrence_year, gbif_id, source_type, quality_weight
- Source type classification with 5 categories based on emb_year vs orig_year vs Hansen loss:
  - pixel_accurate: 2,862,506 (92.8%) — satellite year == observation year, no disturbance
  - pixel_disturbed: 213,398 (6.9%) — accurate year match, Hansen loss detected at pixel
  - undisturbed_pre2017: 5,141 (0.2%) — Phase A pre-2017 obs, no land change detected
  - triangulated: 3,661 (0.1%) — Phase A borrowed embedding from nearby v4 pixel
  - disturbed_pre2017: 123 (0.0%) — Phase A pre-2017 obs at disturbed pixel (WRONG embedding)
- Quality weight (0-1) per row: coord_uncertainty penalty x temporal_match penalty x source_type penalty
- Fixed year resolution: use orig_year from embedding parquet (authoritative, not GBIF join year which may be different observation)
- IDF weights computed per species: 1/log(1+count), range 0.08-1.44, stored in species_occurrence_stats
- Script: orchestrator/load_knn_embeddings.py (v2, ~750 lines)

**FIX** - Null taxon_id root cause in rejoin_gap_species.py
- 219 rows in Phase A output had null taxon_ids (8 geographic blocks: Hawaii, NZ, S.Africa, Australia, Mexico, French Guiana)
- Root cause: 96M occurrence parquet has null taxon_ids; NaN entered gap_species set via set subtraction, passed through .isin() matching
- Fixed at source: added dropna(subset=['taxon_id']) before gap species computation
- Added defense-in-depth: dropna before dedup in output section
- Script: orchestrator/rejoin_gap_species.py (lines 198, 153)

**INVESTIGATION** - Temporal coverage analysis of embedding data
- Confirmed v4 is 100% pixel-accurate: emb_year == orig_year for all 3.37M rows (range 2017-2024)
- Identified 32,000 species with ONLY pre-2017 observations (unreachable by v4's approach)
- Pre-2017 observations: 68.6M of 96.5M total (71%) — the bulk of GBIF data
- Only 123 disturbed_pre2017 embeddings exist (Phase A only) — v4 is temporally clean

**INVESTIGATION** - HILDA+ dataset for disturbed pre-2017 problem
- HILDA+ (Winkler et al. 2021, Nature Communications): global land use 1960-2019 at 1km, 6 categories, annual
- Available from PANGAEA (~1GB GeoTIFF), NOT in standard GEE catalog (needs upload)
- Enables: "what was this pixel's land use in 1985?" for historical occurrence inference
- For disturbed pre-2017: find nearest pixel with same historical land use that is still intact today

**INVESTIGATION** - BigQuery and remaining AlphaEarth coverage
- BQ table treekipedia-479918.species_data.alphaearth_embeddings_v4 is definitive source (3.37M rows)
- Two approaches to get more embeddings: GEE batch ($0.24/1K points) or GCP VM COG sampling ($1-2 total)
- Phase C (regime2_sampler.py) needed for 32K species: sample 2017 AlphaEarth at pre-2017 undisturbed sites
- COPY-based loading would be 5-10x faster but unnecessary for one-time operations

**FILES**: load_knn_embeddings.py (major rewrite), rejoin_gap_species.py (bugfix), GO.md, TODO.md, CHANGELOG.md

### 2026-02-11 - v3.0 Architecture + Phase A/B Expansion + k-NN Design

**ARCHITECTURE** - Designed v3.0 prediction architecture (MASTER_PREDICTION_ARCHITECTURE_3.md)
- Replaces centroid-based matching with k-NN on individual occurrence embeddings (HNSW index)
- IDF weighting (1/log(1+count)) corrects common species bias — rare species with matching habitats outscore abundant species with loose matches
- 7-signal scoring (added soil compatibility + disturbance congruence to existing 5)
- Forest Stability Index: 6-signal composite (0-100) from LandTrendr, JRC TMF, GEDI, ORNL biomass, NDVI trend, Hansen
- Disturbance-aware dual-embedding: for degraded sites, also sample nearby undisturbed reference pixels for restoration recommendations
- Model progression roadmap: k-NN (immediate) → GMM (after gap-fill) → Neural head (SINR-style, 30-60min GPU training)
- Based on literature review: Sat-SINR (Dollinger 2024), LE-SINR (Hamilton NeurIPS 2024), NicheFlow (Dinnage 2024), GeoLifeCLEF 2024
- Files: MASTER_PREDICTION_ARCHITECTURE_3.md (~1000 lines)

**DATA** - Phase A: Rejoin gap species (COMPLETE)
- Recovered 4,679 species via pixel data join from v4 parquet (no GEE calls)
- 9,144 embedding rows assigned, 6,461 centroids loaded to DB
- Script: orchestrator/rejoin_gap_species.py

**DATA** - Phase B: Geographic DBSCAN re-clustering (COMPLETE)
- Re-clustered 2,257 globally-dispersed species (>2000km geographic span)
- Used DBSCAN on (lat,lon) with eps=5 degrees, then density-weighted embedding centroid per region
- P. radiata: 3 clusters → 9 clusters (NZ now has own centroid at -46.4, 169.4)
- Net -1,452 centroids (DBSCAN finds natural regions vs forcing artificial k)
- DB state after: 49,640 centroids, 22,603 species, IVFFlat index rebuilt (lists=320)
- Script: orchestrator/recluster_expanded.py

**INVESTIGATION** - GEE dataset inventory for Forest Stability Index
- Identified JRC TMF (1990-2024 annual tropical forest state), Google CCDC (change detection 1999-2019), GEDI (canopy height + FHD), NASA ORNL (biomass), LandTrendr (Landsat 1985-present temporal segmentation)
- JRC TMF DegradationYear layer can detect invasive species spread within intact forest canopy (Kakamega guava problem)
- HILDA+ (1960-2019 land use history) extends pre-satellite inference to 1960

**FILES**: MASTER_PREDICTION_ARCHITECTURE_3.md (new), GO.md, GEE_PIPELINE_REFERENCE.md, TODO.md, CHANGELOG.md, rejoin_gap_species.py, recluster_expanded.py

### 2026-02-11 - Climate/Soil Signal Activation + Species Expansion Investigation

**FEATURE** - Activated climate and soil signals in real-time prediction scoring
- Python GEE service v2→v3: Added WorldClim BIO sampling (19 vars), OpenLandMap soil (pH, clay%, sand%, organic carbon), Koppen-Geiger classification, USDA soil texture classification
- prediction.js: Climate Signal 5 now has 4 sub-signals (elevation + precipitation + temperature + Koppen-Geiger), added `climate_type_koppengeiger` to all 4 SQL queries
- safeb-scorer.js: `computeAbioticScore()` expanded to 6 sub-scores (added Koppen-Geiger matching)
- Both endpoints return climate/soil context in response (temperature, precipitation, pH, soil texture)

**FEATURE** - Toggleable native status filter buttons in HabitatPredictionModal
- Native/Introduced/Unknown summary badges are now clickable toggle filters
- Active filter gets highlighted ring, non-active dims; "Clear" button when filtered
- Shows "Showing X of Y species" count; display count resets on filter change

**INVESTIGATION** - Deep analysis of species expansion pipeline and v4 coverage
- Discovered v4 coverage is 99.9% of target population (2017+, good coords), not the misleading 3.5% of all occurrences
- Identified 42,285 gap species (was estimated at 30,205 — occurrence parquet has 60,207 species, not 48,129)
- Found ~4,680 gap species recoverable via pixel rejoin (no GEE calls needed)
- Found P. radiata NZ problem is clustering (k=3 merged 685 NZ points into AU cluster), not missing data
- Measured cross-region cosine similarities: AU↔NZ=0.84, AU↔CA=0.19, NZ↔CA=0.23
- Designed 3-phase expansion: rejoin (free) → re-cluster (free) → Regime 2 sampling (GEE)
- Created GEE_PIPELINE_REFERENCE.md — definitive reference for AlphaEarth/GEE/BigQuery pipeline

**FILES**: location_predictor_FIXED.py (v3), prediction.js, safeb-scorer.js, HabitatPredictionModal.tsx, GEE_PIPELINE_REFERENCE.md, GO.md, TODO.md, CHANGELOG.md

### 2026-02-10 - Multi-Signal Prediction Scoring Tuning
**FIX** - Tuned 5-signal scoring to properly rank introduced/plantation species
- Changed spatial density log base from 1000 to 100 (better discrimination for 10-100 tile range)
- Added partial ecoregion credit (0.5) for spatially-confirmed species with 10+ nearby tiles
- Added "de-facto present" range tier (0.90) for species with spatial score >= 0.85 (WCVP data gap mitigation)
- Boosted introduced+spatially-confirmed range score from 0.8 to 0.95
- Increased spatial weight in "balanced" bucket from 0.35 to 0.40 (reduced embedding from 0.20 to 0.15)
- Increased multi-source bonus: 2 sources +0.06 (was +0.04), 3 sources +0.12 (was +0.08)
- Increased default result limit from 50 to 100
- **Benchmark**: P. radiata moved from rank #103/64% to rank #42/81% at Auckland NZ
- Updated SAFE-B scorer ecosystem scoring with spatial tile count for partial credit
- Added "Show More" pagination to HabitatPredictionModal (initially 30, expandable to 100)
- Updated GO.md, ACTIVE.md, TODO.md with current system state
- Files: prediction.js, safeb-scorer.js, HabitatPredictionModal.tsx

### 2026-02-10 - Multi-Signal Prediction System (Major Architecture)
**FEATURE** - Replaced pure-embedding prediction with 3-channel discovery + 5-signal scoring
- **3 discovery channels**: Embedding (pgvector cosine ≥0.40), Spatial (geohash tiles within 50km), Strategy-specific
- **5 scoring signals**: Embedding similarity, Spatial proximity (log-scale density), WCVP range confirmation, Ecoregion co-occurrence, Climate envelope (elevation)
- **Dynamic weighting**: Weights shift based on signal strength (strong embedding vs spatial-dominant vs spatial-only)
- **SAFE-B Recommender**: Full 5-component scoring engine (Spatial, Abiotic, Functional, Ecosystem, Biotic)
- **7 strategy presets**: General, Rewilding, Agroforestry, Riparian, Carbon, Biodiversity, Erosion Control
- Each strategy produces meaningfully different top-3 species lists
- Frontend: Multi-signal score bars, discovery source badges, expandable signal breakdown, strategy selector
- Added prominent demo mode warning banner with AlertTriangle
- Python service: Multi-year AlphaEarth fallback (2023→2017), SRTM elevation, Hansen forest data
- Files: prediction.js (~1930 lines), safeb-scorer.js (new, 709 lines), HabitatPredictionModal.tsx, SpeciesRecommenderModal.tsx (new), MapClickHandler.tsx

---

## January 2026

### 2026-01-06 - Evidence-Based Confidence Scoring System
**FEATURE** - Replaced AI self-assessment with evidence-based confidence calculation
- Created `confidence_calculator.py` module with transparent scoring algorithm:
  - Source score (50%): Credibility-weighted average × count multiplier × diversity bonus
  - Agreement score (25%): Based on source corroboration (3+ sources = 0.95, 2 = 0.85, 1 = 0.70)
  - Specificity score (25%): Numeric values boost, vague descriptions penalize
- Added database columns: `corroboration` (JSONB), `confidence_breakdown` (JSONB)
- Created `recalculate_insight_confidence()` PostgreSQL function for batch recalculation
- Updated all 4 research agent prompts with evidence-based scoring guidelines
- Added authoritative source registry (IUCN 0.98, GBIF 0.95, POWO 0.96, etc.)
- Frontend DataField shows breakdown on source expand (source count, diversity, scores)
- Schema migration: `08_insights_confidence_schema.sql`
- Files: orchestrator/confidence_calculator.py, orchestrator/research_prompts.py, database/08_insights_confidence_schema.sql

### 2026-01-06 - Per-Insight Confidence & RDF Export Pipeline
**FEATURE** - Knowledge architecture Phase 1 + Phase 2 implementation
- Added per-field confidence bars (color-coded: green ≥85%, amber ≥70%, red <70%)
- Added expandable source citations per insight with credibility scores
- Extended `/species/:taxon_id/insights?full=true` endpoint with confidence_breakdown, corroboration
- Created export_to_rdf.py script supporting 4 formats:
  - Turtle (.ttl) - For SPARQL endpoints
  - N-Quads (.nq) - Nanopublication-compatible with provenance graphs
  - JSONL - For ML training datasets
  - JSON-LD - For web applications
- Mapped 35 claim_types to Darwin Core (dwc:), ENVO, PATO ontology terms
- Updated DataField.tsx with confidence visualization and source expansion
- Files: frontend/components/DataField.tsx, backend/controllers/species.js, scripts/export_to_rdf.py

### 2026-01-05 - V11 Species Knowledge Import
**DATA** - Full V11 data import with 23 new columns
- Created V11 schema migration (06_v11_schema_migration.sql)
- Added WCVP columns: wcvp_native, wcvp_introduced (critical for LEAF)
- Added climate columns: climate_type_koppengeiger, precipitation, temperature
- Added 8 GloBI ecological interaction columns
- Added SBTN land cover column
- Imported 67,743 species with 99.99% WCVP coverage
- Created import_v11_species.js streaming importer (handles 1.3GB CSV)
- NFT research data preserved during import
- Duration: ~28 minutes for full import
- Files: treekipedia/database/06_v11_schema_migration.sql, treekipedia/backend/import_v11_species.js

### 2026-01-05 - Merge origin/latest Branch
**INTEGRATION** - Merged Sev's latest branch with our work
- Resolved CORS conflict: combined callback-based config with localhost ports
- Resolved admin routes: kept both /api/admin (GraphFlow) and /admin-api (monitoring)
- Unified admin UI: 4 tabs (Dashboard, Server Stats, API Usage, Error Logs)
- Preserved AlphaEarth habitat prediction features
- Added LEAF scoring endpoint from Sev's branch
- Added Grok research infrastructure (requires XAI_API_KEY)
- Created BRANCH_COMPARISON.md documenting merge strategy
- Files: treekipedia/backend/server.js, treekipedia/frontend/app/admin/page.tsx

### 2026-01-05 - Sev's Reference Documentation Captured
**DOCUMENTATION** - Preserved Sev's planning docs as reference
- SEV_GO.md - Onboarding procedure
- SEV_TODO.md - Task list
- SEV_ACTIVE.md - System status
- SEV_LEAF.md - LEAF scoring algorithm specification
- SEV_GROK_RESEARCHER.md - Grok agentic research architecture
- SEV_GROK_PROMPTS.js - 25-field research prompts (to be adapted for Claude)
- Files: .claude/project-management/sev-reference/*

### 2026-01-05 - Project Management System
**DOCUMENTATION** - Implemented GO_TEMPLATE.md workflow system
- Created GO.md onboarding procedure for Claude Code
- Created ACTIVE.md with real-time system status and metrics
- Created CHANGELOG.md (this file) with historical record
- Restructured TODO.md with priority-based format
- Added Vision: Species Intelligence Engine (5-layer stack)
- Files: GO.md, ACTIVE.md, CHANGELOG.md, TODO.md

---

## October 2025

### 2025-10-28 - AlphaEarth Frontend Integration Complete
**FEATURE** - Click-to-predict habitat prediction in Analysis map
- Created HabitatPredictionModal.tsx for species predictions
- Created MapClickHandler.tsx for Leaflet click events
- Integrated with Map.tsx at line 878
- Progress bar with manual updates (5% → 30% → 60% → 100%)
- Top 10 species predictions with confidence scores
- Clickable cards linking to species pages
- Files: treekipedia/frontend/app/analysis/components/HabitatPredictionModal.tsx, MapClickHandler.tsx, Map.tsx

### 2025-10-28 - Location Prediction Backend Complete
**FEATURE** - Python GEE microservice for AlphaEarth sampling
- Created location_predictor_service.py (Port 5002)
- POST /sample endpoint samples AlphaEarth at clicked location
- POST /sample-stream endpoint with SSE progress (optional)
- GET /health endpoint for service monitoring
- Returns 64-D embedding vector in ~3-8 seconds
- Files: orchestrator/location_predictor_service.py, orchestrator/location_predictor_FIXED.py

### 2025-10-28 - Embeddings API Endpoints
**FEATURE** - Node.js backend endpoints for species prediction
- Created embeddings controller with predict, stats, similar endpoints
- POST /api/embeddings/predict - predict species from 64-D vector
- GET /api/embeddings/:taxon_id - get species habitat centroids
- GET /api/embeddings/similar/:taxon_id - find similar species
- Cosine similarity search against species_alphaearth_centroids table
- Files: treekipedia/backend/controllers/embeddings.js, routes added to server.js

### 2025-10-28 - 100 Species Pilot Extraction Complete
**DATA** - AlphaEarth embeddings extraction for pilot species
- Extracted 45,677 clean embeddings from 100 species
- GBIF occurrences: 95,934 points across 2017-2024
- Success rate: 47.6% (AlphaEarth coverage limitation)
- Fixed coordinate type errors (Quercus rotundifolia, Eucalyptus caliginosa, Eucalyptus placita)
- Mosaic discovery critical for AlphaEarth tiled structure
- BigQuery table: treekipedia-476404.alphaearth.occ_embeddings_clean
- Files: orchestrator/gee_sampler_FIXED.py, run_pilot_PRODUCTION_FIXED.py

### 2025-10-27 - K-Prototypes Clustering POC
**FEATURE** - Species habitat signature computation
- Implemented spherical k-means with k=5 prototypes per species
- Computed centroids (64-D vectors), r (concentration), q10/q50/q90 quantiles
- Created species_alphaearth_centroids PostgreSQL table (500 rows)
- Files: orchestrator/clustering_poc/build_centroids.py

### 2025-10-27 - GBIF Integration Complete
**DATA** - Replaced flawed CSV with GBIF API data
- Downloaded 6,153 occurrences from 40 species (first pilot batch)
- Temporal distribution 2017-2024 with real collection years
- Quality filters: hasCoordinates, uncertainty ≤1000m
- GBIF Download Key: 0002042-251025141854904
- Files: orchestrator/gbif_downloader.py, gbif_data/gbif_occurrences.parquet

### 2025-10-27 - GEE + GCS + BigQuery Setup Complete
**INFRASTRUCTURE** - Cloud infrastructure for AlphaEarth pipeline
- Google Cloud SDK authenticated (project: treekipedia-476404)
- Earth Engine API enabled and tested
- Created BigQuery dataset: alphaearth
- Test scripts passing
- Files: test_ee_simple.py, authenticate_ee.py

### 2025-10-20 - GraphFlow Phase 3 Complete
**FEATURE** - Next.js Admin UI integrated into Treekipedia
- Created 7 admin pages: dashboard, sync, upload, sheets, SPARQL, monitor, versions
- Created 4 shared components: StatusCard, ProgressBar, DataTable, FileDropzone
- Total ~1,790 lines TypeScript/React code
- Matches Treekipedia emerald/black design system
- Auto-refresh status monitoring
- SSE streaming infrastructure ready
- Files: treekipedia/frontend/app/admin/

### 2025-10-20 - GraphFlow Phase 2 Complete
**FEATURE** - Express backend admin proxy routes
- Created controllers/admin.js with proxy to Python microservice
- Created routes/admin.js with all admin endpoints
- Added multer for file uploads
- SSE streaming support for sync progress
- Files: treekipedia/backend/controllers/admin.js, routes/admin.js

### 2025-10-20 - GraphFlow Phase 1 Complete
**FEATURE** - Python microservice for ontology generation
- Created api_only.py Flask headless API
- Health checks, status endpoints, ontology generation
- PostgreSQL → Fuseki sync capability
- CORS restricted to localhost:5001
- Files: treekipedia/python-microservice/api_only.py, API_SPEC.yaml

### 2025-10-18 - Local Database Sync Complete
**INFRASTRUCTURE** - Full production sync to local development
- Imported full database from Digital Ocean VM (167.172.143.162)
- 67,743 species records with all metadata
- 5,786,835 geohash tiles with PostGIS geometries
- 31,796 Wikimedia images
- Database size: 1.9GB compressed, 8.5GB uncompressed
- Files: treekipedia_custom.dump

### 2025-10-18 - STATE.md Created
**DOCUMENTATION** - Comprehensive project status document
- Documented all local services and ports
- Database statistics and data quality insights
- Known issues including species search bug
- Development workflow and troubleshooting
- Files: STATE.md

---

## Earlier History (Compressed)

### September 2025
- **Native Status Analysis**: Started backend/frontend integration for native status cross-analysis
- **Ecoregion Integration**: Planned ecoregion assignment for geohash tiles
- **PostGIS Integration**: Added STAC-compliant geospatial endpoints

### Pre-September 2025
- **v8 Species Import**: Complete v8 species data with comprehensive database updates
- **Analysis Page**: Complete geospatial species plotting feature
- **Treekipedia v6**: Initial launch with core features
- **Ontology Generator**: Original Flask application for RDF/OWL ontology building
- **Smart Contracts**: ResearchSponsorshipPayment.sol and ContreebutionNFT.sol deployed

---

## Documentation References

- **GO.md** - Onboarding procedure (this folder)
- **ACTIVE.md** - Current system status (this folder)
- **TODO.md** - Development roadmap (this folder)
- **[CLAUDE.md](../CLAUDE.md)** - Development guide (parent folder)
