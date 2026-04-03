# SINR v3 Recovery Handoff — Compacted Session Context

**Session**: ses_31349b4a3ffeYcpyGv8lQnhrsl
**Period**: 2026-03-14 to 2026-03-17
**Status**: backfill extraction complete, pre-backfill hypothesis work in progress

---

## 1. Current program state

- V3 = frozen benchmark family
- V4.0 = governance / lineage cleanup
- V4.1 = completed preview baseline (retired, keep for provenance)
- V4.2 = active comparison / SINR alignment phase
- V4.3 = location-prior / representation diagnosis (in progress)
- V4.4 = true background negatives (not yet started)
- V4.5 = retrieval / regional calibration probes (not yet started)
- V4.6 = pre-backfill recipe lock + benchmark suite (not yet started)
- V4.7+ = first backfill-inclusive run (after V4.6 gate)

Do not merge backfill into V4 before V4.6 unless explicitly decided.

---

## 2. Verified benchmark results

Canonical benchmark:
- lat = -41.151583464812404, lon = 175.09968969862783, year = 2023
- target = GymPiPiPnCx50820-00 (Pinus radiata)

| Model | Config | Rank | Prob | Model Dir |
|---|---|---:|---|---|
| V4.1 | BCE | #105 | 0.608283 | ~/model_v41_preview |
| V4.2 | an_full + hard-cap + no-boost + location | #79 | 0.916976 | ~/model_v42_anfull_hardcap_full |
| V4.3a | an_full + hard-cap + no-boost + NO location | #78 | 0.919605 | ~/model_v43a_nolocation |

These results are from repeated direct reruns of saved final models. They are stable.

Key findings:
- Objective matters (#105 -> #79 is real)
- Location encoding is approximately neutral (#79 vs #78)
- Top ranks remain broadleaf/native-heavy
- Introduced sensitivity is inert (identical outputs across 0.0/0.5/1.0)
- Data scope is probably the next major lever

Important correction:
- Earlier reports claimed V4.2=#105 and V4.3a=#100 in a "same-session" comparison.
- That is NOT reproducible from the saved final models.
- The "~25-rank GEE nondeterminism" claim is NOT established.
- Likely cause was stale artifact/cache confusion, not genuine GEE variance.

---

## 3. V4.3c probe status

Artifacts:
- orchestrator/v43c_neighbor_probe.py
- orchestrator/v43c_probe_report.json
- orchestrator/v43c_probe_run.log

Findings:
- In current V4.1 training data, the benchmark point's nearest neighbors (AE primary, AE temporal, pre-logit hidden) are overwhelmingly NZ native broadleaf angiosperms.
- Zero Pinaceae in top-200 neighbors in any space.

Caveats (do NOT overinterpret):
- The probe used only the V4.1 new_gbif-only training set, which has very thin pine support.
- "No plantation neighbors" may reflect candidate-set composition, not representation quality.
- This does NOT prove V4.4 (background negatives) won't help.
- This does NOT prove backfill is the only possible lever.

---

## 4. Data lineage — key tables

### new_gbif strict (canonical repaired)
- `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1`
- 8,838,488 rows, 0 duplicates, 0 missing contexts

### V4.1 preview training-grain
- `species_data.sinr_v41_preview_strict_core_train_v1`
- 11,920,314 rows, 19,043 species

### Backfill strict (NEWLY COMPLETE)
- `species_data.sinr_v3_features_backfill_strict_full`
- 5,871,847 rows
- 0 duplicate context groups
- 0 missing contexts vs existing_training_coords
- Structurally complete and deduped

### Occurrence source branches
- `species_data.gbif_new_occurrences`: 15,252,981 rows, 20,256 species
- `species_data.existing_training_coords`: 11,396,890 rows, 43,992 species
- Species overlap: 18,139. Legacy-only: 25,853. GBIF-only: 2,117.

---

## 5. Pine / radiata source composition

The main reason V4.1 has so little pine is the source-branch split.
new_gbif is a fresh public-GBIF branch that is dramatically less pine-heavy than the legacy training estate.

| Source | Pine rows | Pine species | Radiata rows | Radiata NZ rows |
|---|---:|---:|---:|---:|
| Raw Dec 2025 parquet | ~2,638,791 | 567 | 33,961 | 1,385 |
| existing_training_coords | 2,638,791 | 567 | 8,826 | 685 |
| gbif_new_occurrences | 244,241 | 173 | 935 | 459 |
| V4.1 preview train | — | — | 706 | — |

The collapse is mostly a source-branch issue, not primarily an AE year-window issue.

---

## 6. Semantic change audit (2026-03-17)

### KEEP
| Location | What | Why |
|---|---|---|
| unified_gee_sampler_v3.py:315-317 | GPP >= 65530 masked at sampling | Fill/no-calc codes, not real GPP |
| unified_gee_sampler_v3.py:318-319 | Pre-2001 GPP = constant 0 | Product unavailable before 2001 |
| unified_gee_sampler_v3.py:291-303 | DW pre-2015 ESA remap | Reasonable proxy, explicit |
| train_on_vm.py:663-666 | GPP >= 65530 → 0.0 | Defensive fill-code guard in training |
| build_sinr_v41_preview_strict_core.py:107-113 | GPP >= 65530 → NULL | Training table guard |
| build_sinr_v41_preview_strict_core.py:117-121 | Nighttime pre-2012 → NULL | VIIRS starts 2012 |
| build_sinr_v41_preview_strict_core.py:134-138 | Bio=0 / soil_ph=0 row filter | Unmask artifact removal |
| build_sinr_v41_preview_strict_core.py:125-126 | GEDI excluded entirely | Conservative, semantics unresolved |
| repair_sinr_strict_modis_gpp_semantics.py | Pre-2001 GPP → NULL + provenance | Non-destructive lineage repair |

### REVIEW
| Location | What | Why |
|---|---|---|
| unified_gee_sampler_v3.py:210-215 | GEDI specific image IDs + shan band | Better than .mosaic() but band choice unverified against product docs |

### REVERTED (2026-03-17)
| Location | What | Why |
|---|---|---|
| train_on_vm.py:668-671 | GEDI clip 0..80m | Trees CAN exceed 80m/100m. Unjustified clip removed. |
| v43c_neighbor_probe.py:474-476 | GEDI clip 0..80m | Same unjustified clip removed. |

The V4.1 preview was NOT affected by the GEDI clip because GEDI was excluded entirely from the V4.1 preview strict-core table.

For the merged V4.7+ table:
- Either continue excluding GEDI (same as V4.1)
- Or include GEDI raw (no clip) after verifying the band semantics

### Backfill semantic consistency
The backfill extraction ran across multiple launch/resume phases. The sampler code (`unified_gee_sampler_v3.py`) changed between phases.

Safe across all phases:
- GPP fill masking (was present throughout)
- DW pre-2015 remap (was present throughout)
- Terrain/climate/soil (unchanged)

Potentially mixed:
- GEDI image/band selection (may vary if initial launch used old .mosaic() code)

Recommendation: exclude GEDI from merged V4 table until verified, same as V4.1.

---

## 7. Active beads

| Bead | Title | Status |
|---|---|---|
| treekipedia-xz2 | V4.2 radiata comparison and SINR alignment | in_progress |
| treekipedia-xrj | V4.3 location-prior and representation diagnosis | in_progress |
| treekipedia-37w | V4.4 true background negatives | open |
| treekipedia-e0p | V4.5 retrieval / regional calibration probes | open |
| treekipedia-03y | V4.6 pre-backfill recipe lock + benchmark suite | open |
| treekipedia-bj7 | Backfill strict extraction | COMPLETE |
| treekipedia-bfc | V4.1 preview baseline | closed |

---

## 8. Key file references

Training:
- orchestrator/train_on_vm.py — main trainer
- orchestrator/run_local_5m_shard_training.py — shard training orchestrator
- orchestrator/v3_point_inference.py — benchmark inference

Sampling:
- orchestrator/unified_gee_sampler_v3.py — base GEE image builder
- orchestrator/unified_gee_sampler_v3_strict.py — strict re-extraction sampler

Data builders:
- orchestrator/build_sinr_v41_preview_strict_core.py — V4.1 preview table builder
- orchestrator/build_sinr_v41_preview_train_table.py — V4.1 training-grain builder
- orchestrator/repair_sinr_strict_modis_gpp_semantics.py — GPP lineage repair
- orchestrator/repair_sinr_strict_xiao.py — Xiao lineage repair
- orchestrator/repair_sinr_strict_new_gbif_duplicates.py — duplicate cleanup

Diagnostics:
- orchestrator/v43c_neighbor_probe.py — V4.3c AE/hidden-state probe

Docs (read in order):
- .claude/project-management/GO.md
- docs/SINR Claude V4.2 Comparison Handoff.md
- docs/SINR V4.1 Data Confidence Matrix.md
- docs/SINR BigQuery Lineage Map.md
- docs/SINR Forensic Program History + Master Dataset Plan.md

---

## 9. What NOT to do

- Do not merge backfill into V4 before V4.6 gate
- Do not clip GEDI values (the 80m clip has been removed)
- Do not claim GEE nondeterminism is established
- Do not assume V4.3c proves representation is hopeless
- Do not run more full training on new_gbif-only just to test weighting in isolation
- Do not delete legacy comparison tables
- Do not change multiple knobs at once when adding backfill

---

## 10. Recommended next steps

1. Verify GEDI image/band choices against product docs before including in merged table
2. Freeze pre-backfill recipe (an_full + hard-cap or effective-cap + no-boost + location on)
3. Build merged strict-core training-grain table (new_gbif + backfill, same policy as V4.1)
4. Recompute all contracts/stats from merged table
5. Export merged shards
6. Train first backfill-inclusive V4 model
7. Evaluate against benchmark suite

The first backfill-inclusive run should isolate data scope change only — not simultaneously change loss, weighting, architecture, etc.
