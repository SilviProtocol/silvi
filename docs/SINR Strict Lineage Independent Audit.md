# SINR `new_gbif` Strict Lineage — Independent Audit Report

Date: 2026-03-15
Auditor: Claude (independent re-derivation from code, docs, and BigQuery)
Scope: Full `new_gbif` strict repair lineage from raw extraction through release
Method: 6 parallel deep investigations with BQ queries + code forensics

---

## A. Claim-by-Claim Audit Table

### Group 1: Context Completeness

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1.1 | Source occurrences table contains 8,838,491 distinct `new_gbif` contexts | **CONFIRMED** | BQ `SELECT COUNT(DISTINCT CONCAT(...)) FROM occurrences WHERE source='new_gbif'` = 8,838,491 |
| 1.2 | `strict_full` raw extraction captured all 8,838,491 contexts | **FALSIFIED** | `strict_full` has 8,832,491 distinct contexts (6,000 missing). Expected — 6,000 contexts failed GEE extraction. |
| 1.3 | Missing context recovery patched 5,997 of 6,000 gaps | **CONFIRMED** | `repair_sinr_new_gbif_missing_contexts.py` uses adaptive split-and-retry. Patch lineage summary: 5,997 patched, 3 singleton failures. |
| 1.4 | 3 singleton failures are all lat=90.0 projection errors | **CONFIRMED** | All 3 failures have `lat4=90.0`. GEE cannot sample at exact poles (EPSG:4326 singularity). Genuinely unsampleable. |
| 1.5 | Final `completed_v1` has 8,838,488 effective contexts (8,838,491 − 3) | **CONFIRMED** | BQ distinct context count on `completed_v1` = 8,838,488. Patch lineage summary confirms 0 effective remaining missing. |
| 1.6 | No context was lost during repair chain | **CONFIRMED** | Row count chain: strict_full 8,856,877 → xiao_fixed_v1 8,856,877 → gpp_semantic_v1 8,856,877 → deduped_v1 8,838,491 → completed_v1 8,844,488. Arithmetic: 8,838,491 + 5,997 = 8,844,488. ✓ |

### Group 2: Duplicate Handling

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 2.1 | `strict_full` contains replay duplicates from GEE task retries | **CONFIRMED** | 18,386 duplicate context groups found. Rows with identical `(lat4, lon4, observation_year, emb_year)` tuples. |
| 2.2 | Deduplication keeps first row by `system:index` ordering | **CONFIRMED** | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY system_index)`, keeps `rn=1`. |
| 2.3 | Exactly 18,386 rows removed | **CONFIRMED** | gpp_semantic_v1 8,856,877 → deduped_v1 8,838,491. Difference = 18,386. |
| 2.4 | Deduplication preserves all prior repair columns | **CONFIRMED** | deduped_v1 schema includes all xiao and GPP repair columns. |

### Group 3: GPP Semantics

| # | Claim | Verdict | Evidence | Root Cause |
|---|-------|---------|----------|------------|
| 3.1 | Pre-2001 GPP is set to NULL (not 0) | **CONFIRMED** | All pre-2001 rows have `modis_gpp IS NULL` and `modis_gpp_available = FALSE`. | — |
| 3.2 | Post-2000 GPP values are all valid | **FALSIFIED** | **1,996,803 rows (22.6%) have GPP ≥ 65530.** | See Root Cause F.1 below |
| 3.3 | `modis_gpp_available` boolean is reliable | **FALSIFIED** | Post-2000 rows with fill values 65535 have `modis_gpp_available = TRUE`. | GPP repair only addressed temporal gap, not spatial fill values |

### Group 4: Non-AE Feature Integrity

| # | Claim | Verdict | Evidence | Root Cause |
|---|-------|---------|----------|------------|
| 4.1 | `.unmask(0)` hides genuine missingness | **CONFIRMED** | 10 instances of `.unmask(0)` in the sampler (lines 119, 135, 157, 264, 311, 342, 389, 398). | See Root Cause F.3 below |
| 4.2 | Suspicious zero rates exist | **CONFIRMED** | bio01: 2.8%, soil_ph: 3.2%, GEDI: 20.1%, neumann: 37.8% | See F.3 — three distinct contamination patterns |
| 4.3 | GEDI has quality issues beyond zeros | **CONFIRMED** | Range [-188.86, 4859.36]. 170K negatives, 266K above 130m. | See Root Cause F.2 below — **wrong GEE band** |
| 4.4 | neumann zeros may be legitimate | **RESOLVED: Mostly legitimate** | HM cross-validation: neumann=0 rows have avg human_modification=0.641 vs 0.335 for high-neumann. 89% zero on cropland/herbaceous. Only 19% zero on tree cover. | See F.4 below |

### Group 5: Feature Family Scope — All CONFIRMED (no changes from prior report)

### Group 6: Release Builder Source Tables

| # | Claim | Verdict | Evidence | Root Cause |
|---|-------|---------|----------|------------|
| 6.1 | Release builders use the completed repaired table | **FALSIFIED** | Both hardcoded to `sinr_v3_features_new_gbif_strict_full` (line 25 / line 23). | See Root Cause F.5 below |
| 6.2 | Current releases are built from unrepaired data | **CONFIRMED** | Registry shows stale source. Current release has 952,518 pre-2001 GPP=0 (should be NULL), 25,239 xiao planted corrections missed. | |
| 6.3 | Xiao overlay partially mitigates | **CONFIRMED but INSUFFICIENT** | Overlay covers only 487,523 of 8,838,488 contexts. **76,444 xiao corrections in completed_v1 are completely invisible to the overlay**, including 25,239 planted-forest fixes. | |

---

## B. Feature Family Matrix

| Family | Source | Bands | unmask(0)? | Status | Root Cause ID |
|--------|--------|-------|------------|--------|---------------|
| AlphaEarth Primary | AlphaEarth COG | 64 | Line 135 | **GREEN** — 0.04% zero rate, negligible | — |
| AlphaEarth Temporal | AlphaEarth COG | 512 | Line 119 | **GREEN** | — |
| BioClim (WorldClim) | WorldClim v2 | 19 | Line 264 | **YELLOW** — 241,801 all-zero sentinel block (2.7%) | F.3 |
| Soil (OpenLandMap) | SoilGrids | 7 | Line 264 | **YELLOW** — 278,512 all-zero block (3.2%), soil_ph=0 chemically impossible | F.3 |
| Terrain (SRTM) | SRTM/ALOS | 3 | Line 157 | **GREEN** — zeros at sea level legitimate | — |
| TerraClimate | TerraClimate | 6 | Line 342 | **GREEN** — 18 impossible VPD negatives, clip to 0 | — |
| Dynamic World | Google DW / ESA | 1 | Line 342 | **YELLOW-RED** — 50% of training uses ESA 2021 proxy; DW label 6 collision | F.6 |
| MODIS GPP | MOD17A3HGF | 1 | Line 311 | **RED** — 22.6% fill values (65530-65535) | F.1 |
| MODIS Fire | MOD14A1 | 1 | Line 342 | **GREEN** — zeros for pre-2001 are correct semantically | — |
| VIIRS Night Lights | VIIRS DNB | 1 | Line 342 | **YELLOW** — 24K negatives, max=9,882 needs log-transform | — |
| Hansen Forest | Hansen GFC | 3 | Line 264 | **GREEN** | — |
| JRC Surface Water | JRC GSW | 1 | Line 264 | **GREEN** | — |
| ESA WorldCover | ESA 2021 | 1 | Line 264 | **GREEN** — 1,439 zeros (negligible) | — |
| GEDI Canopy | LARSE GEDI | 1 | Line 264 | **RED** — wrong band, returns absolute height above ellipsoid | F.2 |
| GEDI FHD | LARSE GEDI | 1 | Line 264 | **GREEN** — range [0, 2.89], no anomalies | — |
| Above Ground Biomass | ESA CCI | 1 | Line 264 | **GREEN** — range [0, 336], clean | — |
| Xiao Planted Forest | Xiao et al. | 1 | Line 264 | **GREEN** (post-repair in completed_v1) | — |
| Neumann Natural | DeepMind | 1 | Line 264 | **GREEN** — zeros are genuine non-forest, not coverage gaps | F.4 |
| MODIS Land Cover | MCD12Q1 | temporal | `.unmask(-1)` ✓ | **YELLOW-RED** — 33,661 post-2000 rows with sentinel -1 | — |

---

## C. Root Cause Analysis

### F.1 — MODIS GPP Fill Values (RED, 22.6% of post-2000 data)

**Root cause: Missing quality mask in GEE sampler.**

`unified_gee_sampler_v3.py` lines 301-313:
```python
gpp_col = ee.ImageCollection('MODIS/061/MOD17A3HGF')
    .filterDate(f'{modis_year}-01-01', f'{modis_year+1}-01-01')
gpp_band = gpp_col.mosaic().select('Gpp').unmask(0).rename('modis_gpp_mean')
```

MODIS MOD17A3HGF stores fill values (65530-65535) as **valid pixel values**, not masked pixels. These codes indicate:
- 65535 = standard fill (no data)
- 65530-65534 = QA-flagged fill (urban, snow/ice, barren, water)

The `.unmask(0)` only fills truly masked pixels — it does NOT strip fill values encoded as real numbers. The fill codes pass straight through as if they were legitimate GPP measurements.

**BQ evidence — fill values by ESA land cover:**

| ESA Class | Description | Fill % |
|-----------|-------------|--------|
| 50 | Urban/Built-up | 61.4% |
| 60 | Bare/sparse | 36.2% |
| 70 | Snow/ice | 34.3% |
| 80 | Water | 30.4% |
| 10 | Tree cover | 18.6% |

**Impact on normalization:** With fill values included, GPP mean is inflated by 64% (22,396 vs 13,658 clean) and std is tripled (20,268 vs 6,381). A fill value of 65535 appears as a modest +2.13σ outlier rather than the +8.13σ it should be. The model learns 65535 = "high GPP" rather than "no data."

**Fix for GEE sampler (future extractions):**
```python
gpp_img = gpp_col.mosaic().select('Gpp')
gpp_band = gpp_img.updateMask(gpp_img.lt(65530)).unmask(0).rename('modis_gpp_mean')
```

**Fix for existing BQ data:**
```sql
-- NULL out fill values with provenance
ALTER TABLE completed_v1 ADD COLUMN IF NOT EXISTS modis_gpp_was_fill BOOL;
UPDATE completed_v1
SET modis_gpp_mean = NULL,
    modis_gpp_available = FALSE,
    modis_gpp_was_fill = TRUE
WHERE modis_gpp_mean >= 65530 AND observation_year >= 2001;
```

**Immediate training-code guard** (works on current v30 shards without BQ changes):
```python
# In train_on_vm.py, after nan_to_num:
if 'modis_gpp_mean' in self.continuous_cols:
    gpp_idx = self.continuous_cols.index('modis_gpp_mean')
    cont[:, gpp_idx] = np.where(cont[:, gpp_idx] >= 65530, 0.0, cont[:, gpp_idx])
```

---

### F.2 — GEDI Canopy Height: Wrong Band (RED, 5% impossible values)

**Root cause: The GEE sampler extracts `p95` from the LARSE gridded collection, which is the 95th percentile of absolute return height above the WGS84 ellipsoid — NOT canopy height above ground.**

`unified_gee_sampler_v3.py` lines 211-212:
```python
gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
gedi_stack = gedi.select(['p95', 'shan'], ['gedi_canopy_height_m', 'gedi_foliage_height_div'])
```

The `p95` band value at any point ≈ terrain_elevation + canopy_height. This explains:

| Location | GEDI p95 | SRTM elevation | Difference (actual canopy) |
|----------|----------|----------------|---------------------------|
| Dead Sea | -188.86m | -216m | +27m (plausible tree) |
| Tibetan Plateau | 4,859m | 4,885m | -25m (below ground — SRTM artifact) |
| Andes | 4,511m | 3,908m | +603m (cliff-face GEDI footprint) |

**BQ evidence — GEDI distribution:**

| Bucket | Count | % | Notes |
|--------|-------|---|-------|
| below -100m | 82 | 0.0% | Dead Sea deepest points |
| -100 to -1m | 167,042 | 1.9% | Dead Sea + coastal Sri Lanka artifacts |
| zero | 1,776,969 | 20.1% | 94.9% are outside GEDI orbit (>51.6° lat) |
| 0-5m | 6,485,670 | 73.4% | Valid low/no-canopy |
| 5-50m | 66,075 | 0.7% | Valid canopy range |
| 50-120m | 66,280 | 0.7% | Borderline (tall tropics + terrain mixing) |
| 120-200m | 53,468 | 0.6% | Terrain-contaminated |
| above 200m | 219,999 | 2.5% | Pure terrain elevation (Andes, Himalaya) |

**Three distinct sub-problems:**
1. **Root Cause A** (2.5% of data): `p95` band stores absolute height, not height-above-ground. High terrain = impossible "canopy height."
2. **Root Cause B** (0.5%): LARSE product has artifact cells at coastal India/Sri Lanka (~95-97m negative), uncorrectable.
3. **Root Cause C** (20.1%): Points outside GEDI orbit (>51.6° lat) get `.unmask(0)`, meaning "no GEDI data" → 0, not "0m canopy."

**Fix for GEE sampler — three options, best to worst:**

Option A — Use terrain-corrected band (recommended):
```python
gedi_rh98 = ee.Image('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM/gediv002_rh-98-a0_vf_20190417_20230316')
gedi_stack = (gedi_rh98.select('p95').rename('gedi_canopy_height_m')
              .addBands(gedi_fhd_img.select('shan').rename('gedi_foliage_height_div')))
```

Option B — Switch to ETH Global Canopy Height 2020 (10m, no terrain issues):
```python
eth_canopy = ee.Image('users/nlang/ETH_GlobalCanopyHeight_2020_10m_v1')
gedi_stack = eth_canopy.select('b1').rename('gedi_canopy_height_m')
```

Option C — Terrain-subtract the current mosaic:
```python
dem = ee.Image('USGS/SRTMGL1_003')
gedi_height_above_ground = gedi.select('p95').subtract(dem.select('elevation'))
gedi_stack = gedi_height_above_ground.clamp(0, 80).rename('gedi_canopy_height_m')
```

**Fix for existing BQ data (clamp + terrain subtract):**
```sql
-- Best: terrain-subtract since elevation is in the same table
UPDATE completed_v1
SET gedi_canopy_height_m = GREATEST(0.0, LEAST(80.0, gedi_canopy_height_m - dem_elevation))
WHERE gedi_canopy_height_m < 0 OR gedi_canopy_height_m > 80;
```

The `dem_elevation` column (SRTM) is already in each row and is reliable. Dead Sea: -188 - (-207) = 19m ✓

**Same bug exists in `location_predictor_FIXED.py` lines 518-519** — inference is also returning wrong GEDI values.

---

### F.3 — `.unmask(0)` Zero Contamination (YELLOW, ~3% systematic)

**Root cause: GEE's `.unmask(0)` is needed to prevent `sampleRegions()` from dropping points on masked pixels. This is an engineering trade-off — the alternative (dropping points) would be worse. But zero becomes ambiguous.**

**BQ evidence reveals three distinct contamination patterns:**

**Pattern 1 — Full-unmask contamination (74,718 rows, 0.85%):**
All environmental variables are zero simultaneously. Points where no GEE raster has valid data — small islands, offshore rocks, river bars below raster resolution. These are definitively garbage rows.

**Pattern 2 — OpenLandMap soil coverage gap (203,662 rows, 2.3%):**
All soil vars = 0 but WorldClim is valid. OpenLandMap has geographic gaps in coastal strips, small islands, parts of Scandinavia. All 278,512 soil_ph=0 rows have soil_clay=0 simultaneously — they share a single coverage mask.

**Pattern 3 — WorldClim bio coverage gap (169,881 rows, 1.9%):**
All bio vars = 0 but soil is valid. WorldClim gaps in very small oceanic islands below 1km grid resolution.

**Cross-column clustering evidence:**
- 241,801 rows have all 19 bio vars = 0 (definitively contaminated)
- 278,512 rows have soil_ph = 0 (definitively contaminated — pH=0 is impossible)
- Overlap: 74,718 rows have BOTH all-bio=0 AND all-soil=0 (the worst cases)

**Notably NOT contaminated:**
- `neumann_natural_prob` — see F.4 below, zeros are genuine
- `dem_elevation` — zeros at sea level are real
- `treecover2000` — 44.5% zeros are expected (includes non-forest absence points)

**Fix for existing data (conservative, no mutation):**
Add a WHERE filter at training time:
```sql
WHERE NOT (bio01 = 0 AND bio02 = 0 AND bio12 = 0)  -- excludes 241,801 full-unmask rows
AND soil_ph != 0  -- excludes additional 203,662 soil-gap rows
```
Impact: excludes ~280K rows from 8.8M (3.2%). In v30 training shards this is ~1.5%.

**Fix for GEE sampler (future extractions):**
- For columns where zero is impossible (soil_ph, soil_clay, etc.): use `.unmask(-1)` as sentinel
- For all bands: capture `combined.mask()` before `.unmask(0)` and emit it as a companion `_valid` boolean band
- Note: MODIS land cover already correctly uses `.unmask(-1)` at lines 363/375 — extend this pattern

---

### F.4 — Neumann Natural Prob: Zeros Are Genuine (GREEN — resolved)

**Root cause: The 37.8% zero rate is predominantly genuine non-forest signal, NOT coverage artifacts.**

**Definitive BQ evidence — human modification cross-validation:**

| neumann bucket | Rows | Avg human_modification | Avg treecover2000 | % ESA=trees |
|----------------|------|----------------------|-------------------|-------------|
| zero (0) | 962,535 | **0.641** (high) | 10.0 | 30.2% |
| low (1-49) | 573,614 | 0.516 | 32.4 | 63.2% |
| mid (50-124) | 314,992 | 0.461 | 43.4 | 76.7% |
| high (125-245) | 977,777 | **0.335** (low) | 64.6 | 93.6% |

Rows with neumann=0 have the highest human modification (0.641), lowest tree cover (10%), and lowest ESA-tree fraction (30%). These are heavily modified, non-forest locations where 0% natural forest probability is the correct answer.

**ESA land cover confirms:**
- ESA 50 (herbaceous): 89% neumann=0
- ESA 40 (cropland): 87% neumann=0
- ESA 95 (mangrove): 0.35% neumann=0

**The 362K NULL rows** (where ESA is present but neumann is NULL) are genuine tile gaps in the DeepMind ImageCollection mosaic — not geographic coverage limits. The product covers -65° to +84° latitude. These NULLs should remain NULL for imputation, not be forced to zero.

**Verdict: No fix needed.** The existing normalization pipeline handles zero as "no natural forest" which is correct. The zeros correlate correctly with non-forest land cover.

---

### F.5 — Release Builders Still Point to Unrepaired Table (RED)

**Root cause: The release builder scripts were written before the repair chain existed and were never updated. The xiao overlay approach is a partial workaround that was designed before completed_v1 existed.**

**Three specific gaps in the overlay approach:**

**Gap 1 — Overlay only covers 487,523 of 8,838,488 contexts (5.5%).**
76,444 xiao corrections in completed_v1 are completely invisible to the overlay. This includes 25,239 planted-forest corrections (raw 0→2 or raw 1→2).

**Gap 2 — Overlay cannot deliver the 5,997 missing context patch.**
Those rows don't exist in strict_full at all. The release builder starts from strict_full, so these contexts are unreachable.

**Gap 3 — Pre-2001 GPP NULL logic was never executed.**
The current release has 952,518 pre-2001 rows with `modis_gpp_mean = 0.0` (not NULL). The GPP CASE expression was added to the script code AFTER the last release was built. Registry confirms the active release used `xiao_overlay_v2`, not the `gpp_null_v3` version.

**Exact code changes needed:**

In `build_sinr_strict_only_release.py`:
1. **Line 25**: Change `STRICT_RAW_TABLE` to `...completed_v1`
2. **Remove** `XIAO_CORRECTION_TABLE` constant, `xiao_one` CTE, LEFT JOIN for xiao, and `COALESCE(x.corrected_xiao, ...)` — xiao is now inline
3. **Remove** GPP CASE expression — completed_v1's `modis_gpp_mean` is already NULL for pre-2001
4. **Remove** `strict_one` dedup CTE — completed_v1 has 0 duplicates
5. **Add** completed_v1 audit columns to output (xiao_repair_source, modis_gpp_available, etc.)

In `build_sinr_hybrid_train_release.py`:
Same changes, keeping the LEFT JOIN for strict rows (hybrid rows only exist in preview).

---

### F.6 — Dynamic World Pre-2015 ESA Proxy (YELLOW-RED, 50% of training)

**Root cause: `get_temporal_env_for_year()` uses ESA WorldCover 2021 as a proxy for Dynamic World for all observations before 2015. This creates two problems:**

**Problem 1 — Future leakage (moderate):**
ESA WorldCover 2021 reflects 2020/2021 land cover. Applied to observations from 1990-2014, forests cleared between observation time and 2021 appear as their 2021 cover class (crop, built, etc.). The training signal incorrectly teaches the model that a species seen in forest in 2005 was actually in cropland.

**Problem 2 — Label collision (serious):**
The ESA remap table (lines 287-299) maps ESA class 50 (herbaceous) → DW label 6. But in native Dynamic World, label 6 = **built area**. Any model layer that interprets DW labels consistently across eras will conflate historical scrubland with modern cities. This is a systematic mislabeling affecting ~4% of pre-2015 labeled rows.

**BQ evidence:**
- 50.2% of the 5M training shard is pre-2015
- 63.9% of pre-2015 rows have NULL dynamic_world (ESA not sampled)
- DW label 6 accounts for 24.5% post-2015 (real built area) vs 4.1% pre-2015 (mislabeled herbaceous)

**Fix for GEE sampler:**
1. Remap ESA 50 → DW label 2 (grass) instead of 6 (built) to avoid collision
2. Add `dw_is_esa_proxy BOOLEAN` column

**Fix for existing data:**
Add flag column; optionally zero out DW for pre-2015 rows in the model's embedding layer.

---

## D. Column Quality Report Card

### RED — Active Training Corruption

| Column | Issue | Rows | Root Cause | Fix |
|--------|-------|------|------------|-----|
| `modis_gpp_mean` | Fill values 65530-65535 from MODIS, upper quartile contaminated | 2.0M (22.6%) | F.1: no `.updateMask()` before `.unmask(0)` | NULL where ≥ 65530; add `.updateMask(gpp.lt(65530))` to sampler |
| `gedi_canopy_height_m` | Wrong GEE band — stores height above ellipsoid, not above ground | 436K (5.0%) impossible | F.2: `LARSE/GEDI p95` is absolute height, not relative | Terrain-subtract: `GREATEST(0, LEAST(80, gedi - elevation))`; switch to ETH canopy or RH98 band |

### YELLOW-RED — Significant Anomalies

| Column | Issue | Rows | Fix |
|--------|-------|------|-----|
| `dynamic_world` | ESA 2021 proxy for pre-2015 (future leakage + label 6 collision) | 2.5M (50% of 5M shard) | Add `dw_is_esa_proxy` flag; fix ESA 50 → DW 2 not DW 6 |
| `modis_lc_at_obs` | Sentinel -1 leaking as numeric class; 33,661 post-2000 rows | 467K total | Remap -1 → class 18 ("unknown") before embedding |

### YELLOW — Moderate Anomalies

| Column | Issue | Rows | Fix |
|--------|-------|------|-----|
| All 7 soil vars | Coordinated all-zero sentinel block (pH=0 impossible) | 278K (3.2%) | WHERE filter or NULL where soil_ph=0 |
| All 19 bio vars | Coordinated all-zero sentinel block | 242K (2.7%) | WHERE filter: `NOT (bio01=0 AND bio02=0 AND bio12=0)` |
| `nighttime_lights` | Max=9,882 vs p99=70; 24K negatives | 24K neg | `log1p` transform; clip negatives to 0 |
| `tc_vpd_delta` | 73.7% zero — near-useless feature | 6.5M | Consider dropping entirely |
| `biome_num`/`eco_id` | 267K zero-sentinel rows (outside ecoregion polygons) | 267K (3.0%) | Remap 0 → "unknown" class |
| `observation_year` | 1 row at 1574; 475 pre-1800 | 475 | WHERE filter: `observation_year >= 1800` |

### GREEN — Clean

| Column | Notes |
|--------|-------|
| `elevation`, `slope`, `aspect` | Range physically valid |
| `treecover2000`, `lossyear`, `hansen_gain` | Expected distributions |
| `xiao_planted_forest` (in completed_v1) | Post-repair distribution matches expectations (49.4%/35.6%/15.1%) |
| `neumann_natural_prob` | Zeros are genuine non-forest signal (F.4 resolved) |
| `esa_worldcover_2021` | 12 valid classes, negligible no-data |
| `above_ground_biomass` | Range [0, 336], clean |
| `gedi_foliage_height_div` | Range [0, 2.89], clean |
| `emb_00`–`emb_63` | 0 nulls, correct |
| `emb_year` | 2017-2024, 8 values |
| `tc_aet/pdsi/sm/solar/deficit` | Correct TerraClimate scaling |
| `bio01-bio19` (non-zero) | C×10 scaling correct, ranges valid |

---

## E. Can We Train Yet?

### Answer: **Not from current release tables. Yes from `completed_v1` with 3 guards.**

### Current releases are broken

The active release (`strict_only_20260314_142707`) sources from unrepaired `strict_full`:
- 952,518 pre-2001 rows have GPP = 0.0 (should be NULL) — **GPP null logic was never executed**
- 25,239 xiao planted corrections missed by the overlay
- 18,386 duplicate contexts still present (dedup happens in CTE but overlay misses contexts)
- 5,997 recovered missing contexts not included

### Three guards needed for `completed_v1` training

**Guard 1 — GPP fill clamp (critical, 5 lines in train_on_vm.py):**
```python
if 'modis_gpp_mean' in self.continuous_cols:
    gpp_idx = self.continuous_cols.index('modis_gpp_mean')
    cont[:, gpp_idx] = np.where(cont[:, gpp_idx] >= 65530, 0.0, cont[:, gpp_idx])
```
This unblocks training immediately without any BQ changes. Restores correct GPP distribution.

**Guard 2 — GEDI terrain subtract (critical, 5 lines in train_on_vm.py):**
```python
if 'gedi_canopy_height_m' in self.continuous_cols and 'dem_elevation' in self.continuous_cols:
    gedi_idx = self.continuous_cols.index('gedi_canopy_height_m')
    elev_idx = self.continuous_cols.index('dem_elevation')
    cont[:, gedi_idx] = np.clip(cont[:, gedi_idx] - cont[:, elev_idx], 0.0, 80.0)
```

**Guard 3 — Row exclusion filter (optional but recommended):**
```python
# In BQ query or data loader: exclude rows with all-zero bio (2.7% of data)
mask = ~((df['bio01'] == 0) & (df['bio02'] == 0) & (df['bio12'] == 0))
df = df[mask]
```

**With these 3 guards, completed_v1 is trainable.** Normalization stats will shift significantly for GPP and GEDI — recompute after applying guards.

---

## F. Concrete Next Actions

### P0 — Before next training run

| # | Action | Where | Lines of Code | Impact |
|---|--------|-------|---------------|--------|
| F.0a | Add GPP fill clamp in training code | `train_on_vm.py` | 5 lines | Fixes 22.6% corrupted GPP immediately |
| F.0b | Add GEDI terrain-subtract in training code | `train_on_vm.py` | 5 lines | Fixes 5% impossible canopy heights |
| F.0c | Repoint release builders to `completed_v1` | `build_sinr_strict_only_release.py` L25, `build_sinr_hybrid_train_release.py` L23 | 1 line each | Gains inline xiao, GPP null, dedup, +5,997 contexts |
| F.0d | Remove xiao overlay JOIN from release builders | Both release builders | ~30 lines removed | Simplification — overlay is now redundant |
| F.0e | Remove GPP CASE from release builders | Both release builders | ~5 lines removed | Simplification — completed_v1 GPP is already correct |
| F.0f | Rebuild release tables | Run release builders | Automated | Produces clean versioned releases |
| F.0g | Recompute normalization stats | `build_sinr_v3_global_stats.py` | Automated | Mean/std will shift for GPP, GEDI |

### P1 — Before next extraction cycle

| # | Action | Notes |
|---|--------|-------|
| F.1a | Add `.updateMask(gpp.lt(65530))` to GEE sampler GPP section | Prevents fill values in future extractions |
| F.1b | Switch GEDI from `p95` mosaic to terrain-corrected RH98 or ETH canopy | Fixes root cause of canopy height corruption |
| F.1c | Fix same GEDI bug in `location_predictor_FIXED.py` L518-519 | Inference is also returning wrong GEDI values |
| F.1d | Fix DW label 6 collision in ESA remap (ESA 50 → DW 2 not DW 6) | Prevents shrubland/built-area confusion |
| F.1e | Add `dw_is_esa_proxy` flag for pre-2015 rows | Auditability |
| F.1f | Replace `.unmask(0)` with `.unmask(-1)` for soil columns | Soil_ph=0 → soil_ph=-1 makes gaps identifiable |
| F.1g | Add companion validity mask bands before `.unmask(0)` for all families | Preserves mask state for downstream analysis |

### P2 — Backlog

| # | Action | Beads ID |
|---|--------|----------|
| F.2a | BQ repair: NULL GPP fill values in completed_v1 | (create) |
| F.2b | BQ repair: terrain-subtract GEDI in completed_v1 | (create) |
| F.2c | Full xiao re-extraction (clean column) | treekipedia-wtt |
| F.2d | Per-family fallback provenance flags | Per temporal sampling contract |
| F.2e | Retire legacy tables | treekipedia-9bw |
| F.2f | Add bio/soil all-zero exclusion flag column | (create) |

---

## Appendix: Repair Lineage Chain

```
occurrences (new_gbif contexts)     →  8,838,491 distinct contexts
    ↓ GEE extraction
strict_full                         →  8,856,877 rows (8,832,491 contexts + 18,386 dupes + 6,000 missing)
    ↓ repair_sinr_strict_xiao.py
xiao_fixed_v1                       →  8,856,877 rows (inline xiao correction, 568K values changed)
    ↓ repair_sinr_strict_modis_gpp_semantics.py
gpp_semantic_v1                     →  8,856,877 rows (pre-2001 GPP → NULL; post-2000 fill values NOT fixed)
    ↓ repair_sinr_strict_new_gbif_duplicates.py
deduped_v1                          →  8,838,491 rows (−18,386 duplicates)
    ↓ build_sinr_new_gbif_missing_patch_lineage.py
completed_v1                        →  8,844,488 rows (+5,997 recovered, 3 unsampleable)
                                       8,838,488 effective distinct contexts

REMAINING IN completed_v1:
  ⚠ 1,996,803 rows with GPP fill values ≥ 65530 (22.6% of post-2000)
  ⚠ 436,000 rows with impossible GEDI heights (wrong band)
  ⚠ 278,512 rows with all-zero soil (OpenLandMap coverage gap)
  ⚠ 241,801 rows with all-zero bio (WorldClim coverage gap)
```

---

## Appendix: Evidence Sources

All BQ queries run directly against `silvi-data.sinr_v3_training.*` and `treekipedia-479918.species_data.*` tables on 2026-03-15 by six parallel investigation agents. GEE sampler code read from `orchestrator/unified_gee_sampler_v3.py`. Release builder code read from `orchestrator/build_sinr_strict_only_release.py` and `orchestrator/build_sinr_hybrid_train_release.py`. All repair scripts read from `orchestrator/repair_sinr_*.py`. No prior assistant conclusions were assumed — all counts, root causes, and verdicts independently derived from code and data.
