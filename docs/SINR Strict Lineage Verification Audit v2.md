# SINR `new_gbif` Strict Lineage — Verification-First Forensic Audit

Date: 2026-03-15
Auditor: Independent re-derivation from code, docs, and BigQuery (5 parallel agents)
Method: Every assumption verified via direct BQ queries + code inspection. No prior conclusions trusted.

---

## 1. Assumption Verdicts

### A. Context Accounting

| # | Assumption | Verdict | Evidence |
|---|-----------|---------|----------|
| A1 | Source distinct contexts = 8,838,491 | **CONFIRMED** | BQ count using `lat4dp`/`lon4dp` (pre-truncated columns) with `observation_year IS NOT NULL` = 8,838,491. Note: `ROUND(decimalLatitude,4)` yields 10,173,471 — wrong comparison; lineage scripts use `lat4dp` not `decimalLatitude`. |
| A2 | completed_v1 has 8,838,488 rows/contexts | **CONFIRMED** | Row count = 8,838,488. Distinct `(lat4, lon4, observation_year, emb_year)` = 8,838,488. Every row is a unique context. |
| A3 | Remaining 3 = logged singleton failures | **CONFIRMED** | Gap = 3. Singleton table has exactly 3 rows: all lat=90.0 (North Pole), GEE projection error `SR-ORG:6974 ↔ EPSG:4326`. Failure paths: `0RRRRRRRRRRR`, `1RRRRRRRRRRR`, `2RRRRRRRRRRR` (11 binary splits each). |
| A4 | Effective unresolved = 0 | **CONFIRMED** | `sinr_new_gbif_strict_missing_contexts_v1` = 0 rows. `sinr_new_gbif_strict_missing_patch_lineage_summary_v1.effective_remaining_missing_contexts` = 0. `verify()` function in lineage builder passed (would raise RuntimeError if >0). |
| A5 | 6,000 missing from 3 failed 2,000-row batches | **PARTIALLY CONFIRMED** | 6,000 count exact: `source − deduped_v1 = 6,000`. "3 failed batches" is consistent inference (3×2000=6000) but no surviving log records the original sampler's batch structure. |
| A6 | Repair recovered 5,997 + 3 irreducible | **CONFIRMED** | `patch_raw_v1` = 5,997 rows. `patch_clean_v1` = 5,997 rows. Singleton table = 3 rows. Accounting: 8,832,491 + 5,997 + 3 = 8,838,491 ✓ |

### B. Duplicates

| # | Assumption | Verdict | Evidence |
|---|-----------|---------|----------|
| B1 | strict_full had 18,386 duplicate groups/extra rows | **CONFIRMED** | BQ `GROUP BY ... HAVING cnt>1` on strict_full: `dup_groups=18,386`, `extra_rows=18,386`. Every dup group is exactly a pair (no triples). |
| B2 | Duplicates are replay artifacts, not feature disagreements | **CONFIRMED** | Sampled all 18,386 groups across 10 key fields: `groups_with_any_difference = 0`. Feature values are byte-identical. `system:index` pairs show different batch segments (e.g., `1518_0` vs `1478_0`), confirming GEE export restart writes. |
| B3 | completed_v1 has 0 duplicate groups | **CONFIRMED** | BQ `GROUP BY ... HAVING cnt>1` on completed_v1: `dup_groups = 0`. |

### C. Feature Family Scope — See Section 2 (Feature Family Matrix)

### D. Semantic Integrity

| # | Assumption | Verdict | Evidence | Severity |
|---|-----------|---------|----------|----------|
| D1 | Pre-2001 GPP → NULL | **CONFIRMED** | All 466,518 pre-2001 rows: `modis_gpp_mean IS NULL`, `modis_gpp_available = FALSE`. Repair script's `verify()` asserts `bad_pre_2001_rows = 0`. | Clean |
| D2 | Post-2000 GPP has fill contamination | **CONFIRMED** | 1,996,803 rows (23.9% of post-2001) have `modis_gpp_mean ≥ 65530`. Root cause: MODIS stores fill as valid pixel values, not masked pixels; `.unmask(0)` doesn't catch them. ESA-50 (built): 61.4% fill. Year 2005: 59.5% fill. | **RED** |
| D3 | GEDI has bad semantics | **CONFIRMED — worse than scaling** | `p95` band is height above WGS84 ellipsoid, NOT above ground. GEDI-elevation correlation: r=0.21 overall, **r=0.99 for values >50m**. Dead Sea: GEDI=-188m, elevation=-216m, difference=+28m (correct tree height). Tibet: GEDI=4859m, elevation=4885m. | **RED** |
| D4 | `.unmask(0)` hides missingness | **CONFIRMED** | 10 instances of `.unmask(0)` in sampler (lines 119, 135, 157, 264, 311, 342, 389, 398). Only lines 363/375 use correct `.unmask(-1)` sentinel. Three contamination patterns identified. | **YELLOW** |
| D5 | Xiao repaired enough | **CONFIRMED with caveat** | Planted fraction 15.1% (up from 11.1%), matching backfill benchmark (14.8%). 562,674 values corrected. Caveat: 86K `strict_raw_original` rows remain unverifiable — filterable via `xiao_has_clean_lookup`. | Green |

### E. Release Source

| # | Assumption | Verdict | Evidence |
|---|-----------|---------|----------|
| E1 | Release builders NOT sourcing from completed_v1 | **CONFIRMED** | Both builders: `STRICT_RAW_TABLE = "sinr_v3_features_new_gbif_strict_full"`. `completed_v1` appears nowhere. |
| E2 | They need repointing | **NUANCED** | The xiao overlay comparison shows 0 mismatches across 8,172,288 rows — the overlay approach produces identical xiao values to completed_v1. However: (a) the overlay misses 76K corrections not captured, (b) the GPP null gate was never executed (release has 952K GPP=0 for pre-2001 instead of NULL), (c) 5,997 recovered contexts are unreachable from strict_full. Repointing to completed_v1 or rebuilding is required. |

---

## 2. Feature Family Matrix

Column counts: strict_raw=647, completed_v1=658, release=713.

| Family | Example Columns | In strict_raw? | In completed_v1? | In release? | Canonical strict? | Preview/external? | Known problems |
|--------|----------------|:-:|:-:|:-:|:-:|:-:|---|
| AE temporal (512) | ae_2017_00..ae_2024_63 | YES | YES | YES | YES | — | 0.04% zeros (negligible) |
| AE primary (64) | emb_00..emb_63 | YES | YES | YES | YES | — | — |
| Terrain | elevation, slope, aspect, hillshade | YES | YES | YES | YES | — | — |
| MERIT hydro | merit_hand_m, merit_upstream_area_km2 | YES | YES | YES | YES | — | Log-transform needed for upstream_area |
| BIO climate (19) | bio01..bio19 | YES | YES | YES | YES | — | 241,801 all-zero unmask block (2.7%) |
| Soil (7) | soil_ph, soil_clay_pct, ... | YES | YES | YES | YES | — | 278,512 all-zero unmask block (3.2%); pH=0 impossible |
| TerraClimate (7) | tc_vpd_mean, tc_aet_mean, tc_vpd_delta, ... | YES | YES | YES | YES | — | 18 VPD negatives (clip to 0) |
| Dynamic World | dynamic_world | YES | YES | YES | YES | — | **Label 6 collision: 167K pre-2015 rows** |
| MODIS LC | modis_lc_at_obs, modis_lc_at_ae | YES | YES | YES | YES | — | 33,661 post-2000 rows with sentinel -1 |
| Hansen (3) | treecover2000, lossyear, hansen_gain | YES | YES | YES | YES | — | — |
| JRC (3) | jrc_forest_type, jrc_tmf_status, jrc_tmf_degrad_year | YES | YES | YES | YES | — | — |
| ESA WorldCover | esa_worldcover_2021 | YES | YES | YES | YES | — | — |
| SBTN | sbtn_natural_land | YES | YES | YES | YES | — | — |
| Water (3) | water_occurrence, water_recurrence, water_seasonality | YES | YES | YES | YES | — | — |
| GEDI | gedi_canopy_height_m, gedi_foliage_height_div | YES | YES | YES | YES | — | **canopy_height = absolute altitude (WRONG BAND)** |
| Biomass | biomass_agb_mgha | YES | YES | YES | YES | — | 4.4% zeros (mostly legitimate) |
| Human modification | human_modification | YES | YES | YES | YES | — | — |
| Biome/eco | biome_num, eco_id | YES | YES | YES | YES | — | 267K zero sentinel (outside ecoregion polygons) |
| Xiao | xiao_planted_forest | YES | YES | YES | YES | — | Repaired in completed_v1; release uses overlay |
| Neumann | neumann_natural_prob | YES | YES | YES | YES | — | Zeros are genuine non-forest (confirmed) |
| MODIS GPP | modis_gpp_mean | YES | YES | YES | YES | — | **22.6% fill values (65530-65535)** |
| Fire frequency | fire_frequency_count | YES | YES | YES | YES | — | 96% zeros (genuine no-fire) |
| Nighttime lights | nighttime_lights | YES | YES | YES | YES | — | Pre-2012: synthetic zero (1.35M rows) |
| Xiao repair audit | xiao_planted_forest_raw, xiao_repair_source, ... | — | YES | — | — | — | Correctly stripped from release |
| GPP repair audit | modis_gpp_mean_raw, modis_gpp_available, ... | — | YES | — | — | — | Correctly stripped from release |
| **Carbon extras** | carbon_canopy_height_m, spawn_*, gedi_l4b_*, soc_* | — | — | **NULLED** | — | Preview/legacy | All NULL in strict release |
| **MODIS productivity** | npp_at_obs, gpp_at_obs, lai_*, fpar_*, evi_* | — | — | **NULLED** | — | Preview/legacy | All NULL in strict release |
| **HILDA** | hilda_lulc_at_obs, lulc_changed, forest_to_nonforest | — | — | **NULLED** | — | Preview/legacy | All NULL in strict release |
| **Aridity/ET0** | aridity_index, et0_mm_yr | — | — | **NULLED** | — | Preview/legacy | All NULL in strict release |
| **IPCC** | ipcc_forest_class | — | — | **NULLED** | — | Preview/legacy | All NULL in strict release |
| **is_introduced** | is_introduced | — | — | **FROM PREVIEW** | — | WCVP join | NOT nulled — passes through from preview silently |
| **Land state** | land_state_class, disturbance_intensity, forest_stability, successional_stage, ls_* | — | — | **FROM PREVIEW** | — | land_state_engine | NOT nulled — passes from preview; `serve_parity_ok = FALSE` hardcoded |
| **Verification** | verification_status, wcvp_native, tdwg_region | — | — | **FROM PREVIEW** | — | WCVP metadata | — |
| **Release metadata** | release_id, release_type, release_gate_default, ... | — | — | YES | — | Builder adds | — |

---

## 3. Non-AE Semantic Integrity

| Family | Completeness | Masking | Sentinel issues | Distribution | Trust | Fix |
|--------|-------------|---------|-----------------|-------------|-------|-----|
| **BIO climate** | 97.3% valid | `.unmask(0)` L264 | 241,801 rows all-19-zero (impossible) | Valid range bio01: -158 to 317 (C×10) | **Usable with filter** | `WHERE NOT (bio01=0 AND bio02=0 AND bio12=0)` |
| **TerraClimate** | >99.6% valid | `.unmask(0)` L342 | <0.4% zeros, mostly genuine | tc_vpd_mean: 18 negatives (clip) | **Usable** | Clip 18 VPD negatives to 0 |
| **Soil** | 96.9% valid | `.unmask(0)` L264 | 278,512 rows all-soil-zero; pH=0 impossible | Hard gap at 0-34 range proves artifact | **Usable with filter** | `WHERE soil_ph != 0` |
| **Terrain/SRTM** | ~100% valid | `.unmask(0)` L157 | Sea-level zeros legitimate | Range -415 to 5,421m (valid) | **Usable** | — |
| **MODIS GPP** | 77.4% valid (post-2001) | `.unmask(0)` L311 | **23.9% fill values (65530-65535)** from MODIS QA codes for urban/snow/water | Fill inflates mean 64%, triples std | **Not trustworthy yet** | `WHERE modis_gpp_mean < 32767` or NULL fill values |
| **Dynamic World** | 100% populated | `.unmask(0)` L342 | ESA 50→DW 6 collision (167K rows); pre-2015 uses ESA 2021 proxy | Labels 2,3,8 absent pre-2015 | **Usable with caveat** | Fix remap: ESA 50→DW 2; add `dw_is_esa_proxy` flag |
| **MODIS LC** | 99.6% valid | `.unmask(-1)` ✓ | 33,661 post-2000 rows with -1 sentinel | -1 fed as numeric class to embedding | **Usable with fix** | Remap -1 → 18 ("unknown") |
| **Xiao** | 99% verified | Repaired in completed_v1 | 86K `strict_raw_original` rows unverifiable | 49.4%/35.6%/15.1% distribution matches benchmark | **Usable** | Optional filter: `WHERE xiao_has_clean_lookup = TRUE` |
| **GEDI canopy** | 80% populated | `.unmask(0)` L264 | **WRONG BAND: p95 = absolute altitude, not canopy height** | r=0.99 correlation with elevation for values >50m | **Not trustworthy** | Terrain-subtract: `GREATEST(0, LEAST(80, gedi - elevation))` |
| **GEDI FHD** | 74% non-zero | `.unmask(0)` L264 | Range [0, 2.89] — valid | 26% zeros (mono-layer/bare — legitimate) | **Usable** | — |
| **Biomass** | 95.6% non-zero | `.unmask(0)` L264 | Range [0, 336] — valid | — | **Usable** | — |
| **Neumann** | 100% populated | `.unmask(0)` L264 | **Zeros are genuine non-forest** (confirmed by HM cross-validation: avg HM=0.641 for zeros) | 37.8% zeros ecologically correct | **Usable** | — |
| **Fire frequency** | 100% populated | `.unmask(0)` L342 | 96.3% zeros — genuine no-fire | — | **Usable** | — |
| **Nighttime lights** | 100% populated | `.unmask(0)` L342 | **Pre-2012: 1.35M synthetic zeros** (code assigns `ee.Image.constant(0)`) | Post-2012: 0.004% zeros (genuine dark) | **Usable with flag** | `SET nighttime_lights = NULL WHERE observation_year < 2012` |

---

## 4. External/Manual Family Status

| Family | Historical source | In strict raw? | In completed_v1? | In current release? | Canonical? | Policy needed |
|--------|------------------|:-:|:-:|:-:|:-:|---|
| **Carbon extras** (carbon_canopy_height_m, spawn_*, gedi_l4b_*, soc_*) | Preview/legacy `carbon_gee_sampler.py` | NO | NO | **NULLED** (in UNSAFE set) | NO | Requires separate GEE extraction or BQ join. Training code reads these — must tolerate NULL or exclude from feature contract. |
| **MODIS productivity** (npp_*, gpp_at_*, lai_*, fpar_*, evi_*) | Preview/legacy extraction | NO | NO | **NULLED** | NO | Same as carbon extras — requires separate extraction. |
| **HILDA** (hilda_lulc_*, lulc_changed, forest_to_nonforest) | Legacy assembly join | NO | NO | **NULLED** | NO | No GEE path exists. Either join from HILDA BQ table or drop from feature contract. Training reads `hilda_lulc_at_obs`, `hilda_lulc_at_ae`. |
| **Aridity/ET0** (aridity_index, et0_mm_yr) | `extract_aridity_index.py` (legacy) | NO | NO | **NULLED** | NO | Requires re-extraction. Field integrity: `serve_ok = TRUE` but training data is all-NULL. |
| **IPCC** (ipcc_forest_class) | Legacy assembly join | NO | NO | **NULLED** | NO | Requires re-join. Categorical with vocab_size=10 in training code. |
| **is_introduced** | `compute_is_introduced_bq.py` → WCVP join | NO | NO | **FROM PREVIEW** (not nulled) | **Partially** — uses legacy-era WCVP snapshot | Either: (a) accept preview-inherited values, (b) re-join from current WCVP, or (c) add provenance flag. |
| **Land state** (land_state_class, disturbance_intensity, forest_stability, successional_stage, ls_*) | `land_state_engine.py` → legacy assembly | NO | NO | **FROM PREVIEW** (not nulled) | **NO** — `serve_parity_ok = FALSE` hardcoded | Permanent train/serve gap. `--land-state-mode zero` at inference. Either recompute at strict level or use preview values with flag. |

**Critical finding**: `is_introduced` and `land_state_class` are NOT in `UNSAFE_PREVIEW_FEATURE_ONLY_COLS`. They silently pass through from preview without any annotation. The release table contains these values as if they were canonical strict features — but they are preview-inherited legacy computations.

---

## 5. Exact Fix Plan

### Tier 1 — Blocks training (must fix)

| # | Fix | Where | What | Destructive? | Lines |
|---|-----|-------|------|:---:|---|
| **T1.1** | GPP fill clamp | `train_on_vm.py` | After `nan_to_num`: `cont[:, gpp_idx] = np.where(cont[:, gpp_idx] >= 32767, 0.0, cont[:, gpp_idx])` | No | 5 lines |
| **T1.2** | GEDI terrain-subtract | `train_on_vm.py` | After `nan_to_num`: `cont[:, gedi_idx] = np.clip(cont[:, gedi_idx] - cont[:, elev_idx], 0.0, 80.0)` | No | 5 lines |
| **T1.3** | Bio/soil row exclusion | `train_on_vm.py` or BQ query | `WHERE NOT (bio01=0 AND bio02=0 AND bio12=0) AND soil_ph != 0` | No (filter) | 2 lines |
| **T1.4** | Recompute normalization stats | `build_sinr_v3_global_stats.py` | Run after T1.1-T1.3 — GPP mean drops 64%, std drops 3×; GEDI distribution completely changes | No | Automated |

### Tier 2 — Should fix before final comparison

| # | Fix | Where | What | Destructive? |
|---|-----|-------|------|:---:|
| **T2.1** | Repoint release builders to completed_v1 | `build_sinr_strict_only_release.py` L25, `build_sinr_hybrid_train_release.py` L23 | Change `STRICT_RAW_TABLE` to `...completed_v1`; remove xiao overlay CTE/JOIN; remove GPP CASE; remove strict_one dedup CTE | No |
| **T2.2** | Rebuild releases | Run both builders | Produces new versioned release tables | No |
| **T2.3** | Fix GEDI in inference | `location_predictor_FIXED.py` L518-519 | Same terrain-subtract fix as T1.2 | No |
| **T2.4** | GPP BQ repair | New repair script | `SET modis_gpp_mean = NULL WHERE modis_gpp_mean >= 32767` on completed_v1 (or new `_v2` table) | Creates new table |
| **T2.5** | GEDI BQ repair | New repair script | `SET gedi_canopy_height_m = GREATEST(0, LEAST(80, gedi_canopy_height_m - dem_elevation))` | Creates new table |
| **T2.6** | NTL sentinel | BQ UPDATE or training guard | `SET nighttime_lights = NULL WHERE observation_year < 2012` | Modifies existing or creates new |

### Tier 3 — Fix before next extraction

| # | Fix | Where | What |
|---|-----|-------|------|
| **T3.1** | GPP quality mask | `unified_gee_sampler_v3.py` L304-311 | Add `.updateMask(gpp.lt(32767))` before `.unmask(0)` |
| **T3.2** | GEDI band fix | `unified_gee_sampler_v3.py` L211-212 | Switch to ETH Global Canopy Height or LARSE RH98 specific asset |
| **T3.3** | DW remap fix | `unified_gee_sampler_v3.py` L297-298 | ESA 50→DW 2 (not 6); ESA 40→DW 4 (not 1) |
| **T3.4** | Soil sentinel | `unified_gee_sampler_v3.py` L264 | Use `.unmask(-1)` for soil bands |
| **T3.5** | NTL sentinel | `unified_gee_sampler_v3.py` L333 | Use `ee.Image.constant(-1)` for pre-2012 |
| **T3.6** | Add validity masks | `unified_gee_sampler_v3.py` L264, 342 | Capture `.mask()` before `.unmask(0)` as companion bands |

### Tier 4 — Backlog

| # | Fix | Beads |
|---|-----|-------|
| **T4.1** | Full xiao re-extraction (clean column) | treekipedia-wtt |
| **T4.2** | Recompute is_introduced from current WCVP | (create) |
| **T4.3** | Recompute land_state from strict features | (create) |
| **T4.4** | Re-extract carbon extras for strict contexts | (create) |
| **T4.5** | Re-extract aridity/ET0/IPCC for strict contexts | (create) |
| **T4.6** | Retire legacy tables | treekipedia-9bw |

---

## 6. Training Readiness Verdict

### Is the completed `new_gbif` strict lineage context-complete enough?

**YES.** 8,838,488 of 8,838,491 source contexts are present (99.99997%). The 3 missing are genuinely unsampleable (lat=90.0 projection failures). Zero effective unresolved contexts. Zero duplicate contexts.

### Is it semantically clean enough for a serious model comparison?

**NO — not without the Tier 1 guards.**

Two features are actively corrupted:
- `modis_gpp_mean`: 23.9% fill values inflate mean by 64% and triple std. Model learns fill=65535 as "high GPP."
- `gedi_canopy_height_m`: stores absolute altitude, not canopy height. r=0.99 correlation with terrain for values >50m. All montane species get impossible "canopy heights" of 1,000-5,000m.

With Tier 1 guards applied (GPP clamp, GEDI terrain-subtract, bio/soil row filter, stats recompute), the data is **usable for a serious comparison**. The remaining issues (DW label collision, NTL pre-2012 zeros, 86K unverified xiao) are bounded noise at 1-2% each.

### Are current strict releases sourcing from the right table?

**NO.**

The active release `strict_only_20260314_142707` sources from unrepaired `strict_full`:
- 952,518 pre-2001 rows have GPP=0.0 (should be NULL) — GPP null gate was never executed
- 5,997 recovered contexts are missing (unreachable from strict_full)
- Xiao overlay covers only 487K of 8.8M contexts (76K corrections missed, including 25K planted-forest fixes)

### Top 5 blockers before a trustworthy strict-vs-v3 comparison

| Priority | Blocker | Impact | Effort |
|----------|---------|--------|--------|
| **1** | GPP fill values (23.9% of post-2001 data) | Normalization completely wrong; model learns fill=GPP | 5 lines in `train_on_vm.py` |
| **2** | GEDI wrong band (5% impossible, all montane biomes affected) | Canopy height feature is terrain elevation | 5 lines in `train_on_vm.py` |
| **3** | Release builders stale (GPP null never executed, xiao incomplete, 5,997 contexts missing) | Release tables don't reflect completed repair chain | Repoint + rebuild |
| **4** | Bio/soil unmask zero contamination (~5% of rows) | Model learns impossible pH=0 and all-bio-zero as valid | WHERE filter in training query |
| **5** | Normalization stats computed from corrupted distribution | GPP mean off 64%, GEDI stats meaningless | Recompute after fixing 1-4 |

### Recommended execution order

```
T1.1 (GPP clamp)        → 5 min
T1.2 (GEDI subtract)    → 5 min
T1.3 (bio/soil filter)  → 5 min
T1.4 (recompute stats)  → 30 min
── training is now unblocked ──
T2.1 (repoint builders)  → 30 min
T2.2 (rebuild releases)  → 15 min
T2.3 (fix inference GEDI)→ 5 min
```

Total wall time to unblock training: ~45 minutes of coding + 30 minutes stats computation.

---

## Appendix: Key File References

| File | Key lines | What |
|------|-----------|------|
| `orchestrator/unified_gee_sampler_v3.py` | L211-212 | GEDI wrong band (`p95` = absolute height) |
| | L264 | `.unmask(0)` on all static bands |
| | L297-298 | DW ESA remap (50→6 collision) |
| | L304-311 | GPP missing quality mask |
| | L342 | `.unmask(0)` on all temporal bands |
| | L363, 375 | `.unmask(-1)` correct sentinel (MODIS LC only) |
| `orchestrator/location_predictor_FIXED.py` | L518-519 | Same GEDI wrong band bug |
| `orchestrator/build_sinr_strict_only_release.py` | L25 | `STRICT_RAW_TABLE` stale reference |
| `orchestrator/build_sinr_hybrid_train_release.py` | L23 | Same stale reference |
| `orchestrator/repair_sinr_strict_modis_gpp_semantics.py` | L23-27 | Only fixes pre-2001, not fill values |
| `orchestrator/train_on_vm.py` | L643-644 | Where GPP/GEDI guards should go |
