# Comprehensive Session Context: ses_3014 (SINR V4 Recovery & Semantic Audit)

**Source Transcript:** `session-ses_3014.md`
**Overarching Goal:** Transitioning the SINR model from V3 (legacy/mixed trust) to V4 (strict provenance), diagnosing benchmark failures (Pinus radiata), and safely merging the newly extracted "backfill" data without compromising data integrity.

This document captures the complete chronological and technical narrative of the session, preserving the nuances of the debugging process, the ideological debates over data masking, and the exact state of the BigQuery estate and training pipeline.

---

## Part 1: Initial Context & The V4 Program State

At the start of the session, the program had successfully established the **V4.1 preview baseline**. The goal of the V4 program is to rebuild the model using strictly governed data extracted directly from Google Earth Engine (GEE), abandoning the "mixed trust" legacy datasets.

The active training data at this stage was derived *exclusively* from the `gbif_new_occurrences` (new_gbif) branch, utilizing the canonical repaired table:
`species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1` (8.83M rows).

### The Benchmark Failure
The primary evaluation metric was the canonical Pinus radiata benchmark in New Zealand:
`lat=-41.151583464812404, lon=175.09968969862783, year=2023, target=GymPiPiPnCx50820-00`

The V4.1 baseline models were performing poorly on this benchmark compared to historical V3 models. The session focused on diagnosing *why* the model was failing to predict this introduced plantation species.

---

## Part 2: Model Ablations & Debunking "Nondeterminism"

To diagnose the benchmark failure, a series of models were trained and independently verified. 

### Verified Model Progression:
1. **V4.1 (BCE):** Rank #105, Probability 0.608
2. **V4.2 (an_full + hard-cap + no-boost + location ON):** Rank #79, Probability 0.916
3. **V4.3a (an_full + hard-cap + no-boost + NO location):** Rank #78, Probability 0.919

### Key Discoveries from Ablations:
1. **Objective Matters:** Upgrading from BCE to `an_full` with capacity capping improved the rank (#105 -> #79).
2. **Location Prior is Not the Sole Villain:** There was a strong hypothesis that the sinusoidal location encoding was forcing the model to predict native NZ species, suppressing the introduced Pinus radiata. However, the V4.3a ablation (location OFF) resulted in virtually the same rank (#78). 
3. **Nondeterminism Claim Debunked:** Earlier in the session/project, there was a claim of "~25-rank GEE nondeterminism" (models randomly fluctuating by 25 ranks). By repeatedly re-running the saved final models, this was proven false. The variance was traced to stale artifact/cache confusion, not genuine GEE variance. The models are stable.

---

## Part 3: The V4.3c Probe & The "Missing Pine" Reality

Because turning off the location prior didn't fix the plantation ranking, the investigation shifted to the representation space itself. 

### The V4.3c Neighbor Probe
A probe (`orchestrator/v43c_neighbor_probe.py`) was written to analyze the nearest neighbors of the benchmark point in AlphaEarth (AE) embedding space, temporal space, and the pre-logit hidden states.
- **Finding:** In the V4.1 training data, the nearest neighbors to the NZ benchmark point were overwhelmingly native broadleaf angiosperms. There were **zero Pinaceae** in the top-200 neighbors in any space.

### The Source-Branch Split Discovery
This led to a deep dive into the actual data composition. Why was there no pine in the training data for this location? Was the AlphaEarth 2017-2024 temporal window filtering them out?

BQ analysis revealed the true root cause: **A massive source-branch data collapse.**

The original, redundant occurrence universe had plenty of pine. But the project had split the data into a "legacy" branch (`existing_training_coords`) and a "fresh" public-GBIF branch (`gbif_new_occurrences` / `new_gbif`).
- **Raw Dec 2025 parquet:** 33,961 radiata rows
- **Legacy (`existing_training_coords`):** 8,826 radiata rows
- **Fresh (`new_gbif`):** Only 935 radiata rows.
- **V4.1 Preview Train:** Down to 706 radiata rows.

**Conclusion:** The model wasn't failing because of architecture or location priors; it was failing because it was starved of data. Over 90% of the historical radiata support lived in the legacy branch (which was currently undergoing "backfill" strict extraction), not in the `new_gbif` branch that V4.1 was trained on.

---

## Part 4: Backfill Completion & The "Corrupted Data" Confrontation

During the session, the strict extraction of the legacy/backfill data finally completed:
`species_data.sinr_v3_features_backfill_strict_full` (5.87M rows, 0 duplicates, structurally complete).

### The Confrontation
With backfill complete, the immediate impulse was to merge it and train. However, the user raised a critical alarm regarding the integrity of the extracted data. 

Throughout the extraction process, the sampler code (`unified_gee_sampler_v3.py`) had been modified to "clean" semantic anomalies (e.g., clipping GEDI heights, masking GPP values). Because the backfill extraction ran across multiple phases/resumes, it contained mixed semantic vintages.

The user forcefully challenged the agent, questioning if the entire session's context was corrupted and if the aggressive masking had ruined the backfill data. The user correctly pointed out that silently mutating values (like clipping GEDI to 80m) destroys the scientific integrity of the raw data.

---

## Part 5: The Semantic Change Audit & Reverts

To address the trust crisis, the agent performed a rigorous, line-by-line Semantic Change Audit of all extraction, inference, and training scripts to classify every modification as KEEP, REVIEW, or REVERT.

### 1. REVERTED (Destructive/Unjustified)
- **GEDI 80m Clip:** Both `train_on_vm.py` and `v43c_neighbor_probe.py` were silently clipping `gedi_canopy_height_m` to a maximum of 80.0. This was an unjustified heuristic, as trees can and do exceed 80m. 
  - *Action Taken:* The `np.clip` logic was stripped out of both files.

### 2. KEEP (Defensible / Provenance-Safe)
- **MODIS GPP Fill Masking:** The sampler masks `modis_gpp_mean >= 65530` to 0/NULL. This is scientifically correct, as 65530-65535 are documented MODIS fill codes (urban, snow, water), not extreme productivity values.
- **Pre-2001 GPP Nulling:** MODIS MOD17A3HGF does not exist before 2001. Enforcing NULLs here is historically accurate.
- **Dynamic World Remap:** Pre-2015 ESA WorldCover is remapped to DW codes. This is an explicit, documented proxy.
- **Unmask Artifact Filters:** Filtering rows where `bio01=0 AND bio02=0 AND bio12=0` or `soil_ph=0`, which are clear GEE `.unmask(0)` boundary artifacts.

### 3. REVIEW (Requires Product Doc Verification)
- **GEDI Band/Image Selection:** The sampler was changed from using a sloppy `.mosaic()` on the whole GEDI collection to using specific image IDs and the `shan` band for FHD. While better than a random mosaic, the specific band choices need verification against LARSE product docs before being trusted.

**Audit Conclusion:** The underlying backfill data was **not** ruined. The destructive GEDI clipping was happening downstream (in the trainer/probe), not in the BQ extraction. Furthermore, GEDI had been entirely excluded from the V4.1 preview tables anyway, meaning no previous models were compromised by the clip.

---

## Part 6: The Master Plan Forward (V4.6 and V4.7)

With the air cleared and the destructive clips reverted, the session defined the exact, sequential path forward to safely utilize the completed backfill data.

The core directive: **Do not run any more thin-slice experiments on new_gbif-only data. The data scope must be expanded.**

### Step 1: V4.6 Pre-Backfill Recipe Lock
Before merging data, the exact training configuration must be frozen to ensure that any changes in model performance are strictly due to the new data, not hyperparameter tweaking.
- **Frozen Recipe:** `an_full` loss + `hard-cap` (or `effective-cap 1000`) + `no-boost` + `location encoding ON`.

### Step 2: V4.7 Merged Strict-Core Training Table
A new builder script must be created (`orchestrator/build_sinr_v47_merged_strict_core_train.py`) to construct the final, backfill-inclusive training table.
- **Sources:** Join `sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1` AND `sinr_v3_features_backfill_strict_full`.
- **Labels:** Source `taxon_id`, coordinates, and splits from the canonical training-grain source (`sinr_v3_unified_strict_train_v30_preview_clean`).
- **Policy:** Apply the exact same strict-core guards used in V4.1 (exclude external/manual families, apply the GPP/Bio/Soil masks).
- **GEDI Policy:** Exclude GEDI entirely from this table until the band semantics are fully verified against product docs.

### Step 3: V4.8 Artifact Recomputation & V4.9 Training
Once the V4.7 table is built, all normalization stats, frequency contracts, and shards must be re-exported. Finally, the first backfill-inclusive model (V4.9) will be trained using the locked V4.6 recipe. 

The explicit hypothesis is that restoring the 8,800+ radiata rows from the backfill will repair the representation collapse observed in V4.1/V4.2.

---
**End of Context Document.**
