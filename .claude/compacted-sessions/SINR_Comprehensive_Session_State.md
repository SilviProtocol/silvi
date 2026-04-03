# SINR v3 Recovery & V4 Program — Comprehensive Session Context

**Period Covered**: 2026-03-14 to 2026-03-17 (Session: ses_31349b4a3ffeYcpyGv8lQnhrsl to ses_3014bacfcffeJRVifZCjdt7nuU)
**Core Status**: Backfill strict extraction is **100% COMPLETE and structurally sound**. The V4 training program is transitioning from "thin-slice diagnosis on new_gbif" to the **first merged backfill-inclusive strict-core run (V4.7/V4.8)**.

---

## 1. The V4 Program Pivot & The "Missing Pine" Reality

A massive point of confusion in earlier sessions was why the `V4.1 preview` model performed so poorly on the canonical `Pinus radiata` benchmark (#105 rank). 

The root cause was originally hypothesized to be an AlphaEarth (AE) year-window limitation (2017-2024), but deep BQ analysis revealed it is fundamentally a **source-branch split**.

### The Three Source Regimes
1. **Raw Dec 18 2025 occurrence parquet**: The giant, redundant occurrence universe (`96.5M` rows, `33,961` radiata rows).
2. **Legacy `existing_training_coords`**: The curated legacy training estate. Pine-heavy. (`11.4M` rows, `8,826` radiata rows).
3. **Fresh `gbif_new_occurrences` (new_gbif)**: A newer, stricter, public-GBIF-derived branch created because an older CSV/pilot feed was distrusted. Pine-light. (`15.2M` rows, only `935` radiata rows).

**The Collapse:**
When the program built the `V4.1 preview` using *only* the `new_gbif` branch, radiata support collapsed from `8,826` rows down to `706` rows. 
- *Insight:* The lack of pine is a provenance/source issue, not a temporal/AE artifact. 

---

## 2. The Semantic Change Audit & "Corrupted Data" Confrontation

Tension arose when it appeared the agent was hallucinating "corrupted data" and mutating canonical sources based on aggressive heuristics. A strict audit was performed across all sampler, inference, and training code.

**The Verdict: The core BQ estate was NOT irreversibly corrupted. Most table work was lineage-based and non-destructive.** However, some training/inference guards were too aggressive.

### The Strict Audit Results (Implemented 2026-03-17):

**REVERTED (Removed from code)**
- **GEDI 80m Clip:** `train_on_vm.py` and `v43c_neighbor_probe.py` were actively clipping `gedi_canopy_height_m` to `80.0`. This was an unjustified heuristic (trees *can* exceed 100m). *Action: The clip was removed in both files.*

**REVIEW REQUIRED**
- **GEDI Band Selection:** `unified_gee_sampler_v3.py` moved away from sloppy `.mosaic()` collection behavior to specific image IDs and the `shan` band for FHD. *Action: Better than mosaic, but band choice needs verification against product docs before including GEDI in the merged V4 table.*

**KEEP (Defensible Guards)**
- **GPP Fill Masking:** `modis_gpp_mean >= 65530` are sentinel/fill codes ("could not calculate"), not real productivity. Masking them to `0` in the trainer and `NULL` in the V4.1 preview table is correct.
- **Pre-2001 GPP Nulling:** MOD17A3HGF does not exist before 2001.
- **Dynamic World Remap:** Pre-2015 ESA WorldCover remap to DW codes is a reasonable, explicit proxy.
- **Unmask Artifact Filters:** Excluding rows where all `bio = 0` or `soil_ph = 0`.
- **Nighttime Lights Guard:** Pre-2012 (before VIIRS) set to `NULL`.

---

## 3. Verified Benchmark Progress (Pre-Backfill)

Canonical benchmark point: `lat=-41.1516, lon=175.0997, year=2023, target=GymPiPiPnCx50820-00 (radiata)`

The pre-backfill `new_gbif`-only experiments yielded stable, reproducible results (no 25-rank GEE non-determinism, as was erroneously claimed earlier):

1. **V4.1 (BCE):** Rank #105, Prob 0.608
2. **V4.2 (`an_full` + `hard-cap` + `no-boost` + location ON):** Rank #79, Prob 0.917
3. **V4.3a (V4.2 recipe, but location OFF):** Rank #78, Prob 0.920

**Conclusions from the thin-slice experiments:**
- **Objective matters:** Moving from BCE to `an_full` + capping helped significantly.
- **Location prior is neutral:** Removing location encoding didn't magically fix the plantation ranking. It is not the dominant villain.
- **Data scope is the bottleneck:** The model is starved of radiata support in the `new_gbif` branch.

### V4.3c Probe Status
An AE/hidden-state nearest-neighbor probe (`v43c_neighbor_probe.py`) showed the benchmark point is surrounded by native broadleaf angiosperms in the V4.1 data. 
- *Caveat:* This just proves the `new_gbif` candidate set lacks local plantation examples. It does **not** prove the representation is hopeless, nor does it rule out the need for true background negatives (V4.4).

---

## 4. Current State of the Data Estate

1. **Repaired `new_gbif` strict lineage:** 
   `sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1` (Complete, clean, 8.8M rows).
2. **V4.1 Preview Baseline:** 
   `sinr_v41_preview_strict_core_train_v1` (Retired. Keep for provenance).
3. **Backfill Strict Extraction:** 
   `sinr_v3_features_backfill_strict_full` is **COMPLETE** (5.87M rows). 
   - 0 duplicate context groups.
   - 0 missing contexts vs `existing_training_coords`.
   - *Warning:* Because the sampler code evolved during the run (pauses/resumes), the table contains mixed semantic vintages for things like GEDI image selection. It MUST be normalized/repaired via a strict-core policy before training.

---

## 5. The Immediate Path Forward (What To Do Next)

**STOP** running thin-slice experiments on the `new_gbif` data.
**DO NOT** merge backfill directly into a training run without building a repaired strict-core table first.

### Step 1: Freeze the Pre-Backfill Recipe (V4.6 Lock)
Lock the best recipe to isolate the impact of the data scope change when backfill is added:
- Loss: `an_full`
- Balancing: `effective-cap 1000` (better engineering default than hard-cap)
- Planted aux: `no-boost`
- Location encoding: **ON**

### Step 2: Build the Merged Strict-Core Training-Grain Table (V4.7)
This is the most critical next data task. Create a builder script (e.g., `orchestrator/build_sinr_v47_merged_strict_core_train.py`) that:
- Sources features from the completed `new_gbif` strict table AND the newly completed `backfill` strict table.
- Sources labels/metadata (`taxon_id`, `data_source`, coords, years) from a valid training-grain source (e.g., `sinr_v3_unified_strict_train_v30_preview_clean`).
- Applies the exact same safe strict-core policy used in V4.1:
  - `GPP >= 65530` → `NULL`
  - Pre-2001 GPP → `NULL`
  - Nighttime lights pre-2012 → `NULL`
  - Filter `bio01=0 AND bio02=0 AND bio12=0`
  - Filter `soil_ph=0`
- **Crucial Decision on GEDI:** Either continue to EXCLUDE GEDI entirely (safest, consistent with V4.1), or include it raw after verifying the band semantics in the product docs. *Do not apply the 80m clip.*

### Step 3: Recompute Artifacts (V4.8)
Using ONLY the new merged V4.7 table:
- Recompute species mapping, frequency contracts, intro-ratio contracts, continuous/temporal stats.
- Export the new merged shards.

### Step 4: First Backfill-Inclusive Training Run (V4.9)
Train the model using the frozen recipe on the merged shards. Evaluate against the canonical radiata benchmark. 
- *Hypothesis:* Restoring the 8,800+ radiata rows from the backfill branch will finally provide the local geographic and temporal support needed to rank radiata competitively.

### Parallel Track: Environmental Envelope Frontend
There is a parallel product/tooling effort to build a "Site Inspector" UI that surfaces environmental envelope data (climate, soil, carbon, land state) to users, independent of species prediction. Do not let this derail the core V4 training progression, but support it if requested using the sampled features, not model outputs.