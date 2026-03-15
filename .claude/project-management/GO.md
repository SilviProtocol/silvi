# GO.md - Treekipedia Project Onboarding

Last updated: 2026-03-12

Purpose: fast onboarding for any AI agent or human developer. Covers project management workflow, then domain-specific operational context.

---

## 1) Project Management: Dual System

Two systems, two jobs. Together they prevent the two failure modes of AI coding agents: **losing context** (forgetting what the project is) and **losing track** (forgetting what to do next).

| System | Source of Truth For | Survives Context Decay? |
|--------|-------------------|------------------------|
| **Beads (`bd`)** | Task state, dependencies, blockers — the *what's next* | Yes (queried live via CLI) |
| **Markdown docs** | Architecture, conventions, decisions — the *why* | Yes (re-read on demand) |

### Beads = Task Authority

```bash
bd ready                              # What's unblocked RIGHT NOW (sorted by priority)
bd show <id>                          # Full context for a task
bd list                               # All open issues
bd list --status in_progress          # Currently claimed work
bd update <id> --claim                # Claim a task (sets in_progress)
bd close <id>                         # Mark complete
bd create --title="..." --type=task --priority=2  # New task (0=critical, 4=backlog)
bd dep add <issue> <depends-on>       # Add dependency
bd sync                               # End-of-session sync
```

### Markdown Docs = Architecture & Context

| File | Purpose |
|------|---------|
| **GO.md** (this file) | Onboarding + operational context |
| **CLAUDE.md** | Development guide, conventions, environment |
| **TODO.md** | Architectural vision & phase checklists (reference only — tasks live in `bd`) |
| **ACTIVE.md** | Production status, endpoints, live metrics |
| **CHANGELOG.md** | Version history of completed work |

### When to Use Which

| Need | Use |
|------|-----|
| "What should I work on next?" | `bd ready` |
| "How does X work?" | Read GO.md, CLAUDE.md |
| "What blocks this task?" | `bd show <id>` |
| "Is this task done?" | `bd show <id>` |
| "What happened recently?" | `bd list --status closed` + CHANGELOG.md |
| "What's the project vision?" | TODO.md (reference) |

### Tool-Specific Integrations

Beads has built-in setup recipes for AI tools. Each tool gets its own hooks/rules:

```bash
bd setup claude    # Claude Code (SessionStart + PreCompact hooks)
bd setup cursor    # Cursor IDE rules
bd setup gemini    # Gemini CLI hooks
bd setup aider     # Aider config
bd setup codex     # Codex AGENTS.md
bd setup windsurf  # Windsurf rules
bd setup --list    # See all 12+ recipes
```

The workflow is identical regardless of tool — only the integration layer differs.

---

## 2) Onboarding Checklist

### Step 1: Read Core Docs
1. **This file (GO.md)** — workflow + operational context
2. **CLAUDE.md** — codebase guide, conventions, environment setup
3. **CHANGELOG.md** — last 10 entries for recent history

### Step 2: Check Task State
```bash
bd ready                       # Unblocked tasks by priority
bd list --status in_progress   # What's currently claimed
```

### Step 3: Brief Assessment
- Summarize ready tasks from `bd ready`
- Note any in-progress work
- Mention recent completions from CHANGELOG.md

### Step 4: Ask What to Work On
Present `bd ready` output grouped by priority (P0/P1/P2). Wait for direction.

---

## 3) During Development

### Task Lifecycle (PRIMARY)
```bash
bd update <id> --claim                                    # Start a task
# ... do the work ...
bd create --title="Discovered issue" --type=bug -p 2      # Track discovered work
bd close <id>                                             # Finish the task
bd sync                                                   # End of session
```

### Markdown Maintenance (SECONDARY)
Keep docs in sync, but beads is the task authority:
- Update CHANGELOG.md when features ship
- Update ACTIVE.md when infrastructure changes
- Don't manually track task state in markdown — that's beads' job

### Session Lifecycle

**Start**: Read `bd ready`, ask user what to work on.
**During**: Claim tasks, stay focused (beads hooks remind you of active task). Create new issues for discovered work instead of drifting.
**End**: `bd close` finished tasks, `bd sync`, commit code, push.

### Commit Messages
Include beads issue ID for traceability:
```
feat: add location encoding to SINR model (treekipedia-a3f2dd)
```

---

## 4) Source of Truth — SINR Documentation

**START HERE** for SINR work — the master recovery plan supersedes all prior audit docs:

1. **`docs/SINR Claude V4.1 Preview Handoff.md`** — ACTIVE handoff for the current program focus (`V3` frozen as baseline, `V4.1` strict-core preview while backfill finishes)
2. **`docs/SINR V4.1 Data Confidence Matrix.md`** — ACTIVE trust boundary for what may enter `V4.1 preview`
3. **`docs/SINR v3 Master Recovery Plan.md`** — ACTIVE source of truth for the broader recovery / governance program
4. `docs/SINR Versioning Registry.md` — contract/artifact versions
5. `docs/SINR March 7 Comprehensive State + Audit Request Packet.md` — operational context
6. `docs/SINR BigQuery Lineage Map.md` — current strict vs legacy table lineage
7. `docs/SINR Forensic Program History + Master Dataset Plan.md` — long-form forensic synthesis + master dataset plan
8. `docs/SINR Master Dataset v1 README.md` — proposed canonical masters / release layout
9. `docs/SINR Legacy Backfill Salvage Plan.md` — occurrence-grain salvage strategy for legacy extraction
10. `docs/SINR Occurrence-Grain Master Training Schema.md` — recommended future train-table grain
11. `docs/SINR Field-Family Integrity Audit Plan.md` — field-family and temporal semantics integrity layer
12. `docs/SINR Data Estate Audit Handoff.md` — full-estate audit packet + Claude handoff prompt
13. `docs/SINR Claude Audit Adjudication.md` — claim-by-claim assessment of external Claude audit
14. `docs/SINR Strict-Only Release Builder.md` — implemented enforced strict-only release path
15. `docs/SINR Hybrid Override System.md` — fail-closed hybrid override governance tables
16. `docs/SINR Hybrid Train-Only Release Builder.md` — implemented hybrid release builder with zero approvals by default
17. `docs/SINR Deletion Readiness Matrix.md` — conservative keep/review/delete-later matrix for BQ tables
18. `docs/SINR Hybrid Review Batch.md` — 100-row manual review queue for hybrid override decisions
19. `docs/SINR Fresh Validation Sampling Plan.md` — 1,000-row fresh re-extraction validation sample weighted to high-risk rows
20. `docs/SINR Fresh Validation Findings.md` — first findings from fresh validation, including Xiao inconsistency and year-2000 GPP failure
21. `docs/SINR Temporal Sampling Contract.md` — recommended temporal semantics by feature family
22. `docs/SINR Claude Continuation Handoff.md` — older continuation handoff; read only for historical continuity

Prior audit docs (for reference only, superseded by master plan):
- `docs/SINR March 6 claude.md` — Claude forensic audit
- `docs/SINR March 6 gemini.md` — Gemini forensic audit
- `docs/SINR March 7 Deep Root Cause + Action Plan.md` — Codex deep-dive

If docs conflict, trust the Master Recovery Plan, then live BigQuery + executable scripts over prose.

Do not claim model quality from memory. Always reference versioned artifacts and current run logs.

## 4.1) Current SINR Program Mode (2026-03-15)

This section supersedes the old instinct to keep iterating `v3.x` models on mixed-trust data.

### Program framing

- Treat **`V3` as a frozen benchmark family**, not the destination.
- Treat **`V4.0` as the data-governance / lineage cleanup phase**.
- Treat **`V4.1 preview` as the next deliberate model-facing step**:
  - `new_gbif` only,
  - strict-core feature surface only,
  - fail-closed exclusions for unresolved families,
  - trained from repaired strict lineage rather than legacy preview inheritance.
- Treat **`V4.2+` as the full strict estate** after backfill finishes and external/manual families are either canonicalized or explicitly excluded.

### Version numbering disambiguation

**Do not confuse program versions (V3, V4.0, V4.1) with V3 experiment numbers (v1-v18).**

- Program versions (V3, V4.x): describe the data governance and release program.
- V3 experiment numbers (v1-v18): internal training experiment IDs, all using V3 data/stats. Directories like `~/model_local_contract_v4_gatefix_5m` and `~/model_local_contract_v14_location_5m` are V3 experiments #4 and #14, NOT V4.x program models.
- The V3 frozen benchmark = experiment v4 (rank #16). The best V3 model = experiment v14 (rank #2).
- The first actual V4.1 model does not exist yet.
- All V3 experiment data (shards, stats, contracts) is reproducible from BQ + repo scripts. Only trained weights are seed-dependent.

### Current canonical `new_gbif` strict lineage

- Use `species_data.sinr_v3_features_new_gbif_strict_full_xiao_fixed_gpp_semantic_deduped_completed_v1` as the canonical repaired `new_gbif` strict source.
- It has:
  - `8,838,488` rows,
  - `8,838,488` distinct `(lat4, lon4, observation_year, emb_year)` contexts,
  - `0` effective unresolved contexts,
  - `0` duplicate context groups,
  - `3` explicit singleton unsampleables logged separately at exact-pole coordinates.
- Supporting lineage / audit tables:
  - `species_data.sinr_v3_features_new_gbif_strict_missing_patch_raw_v1`
  - `species_data.sinr_v3_features_new_gbif_strict_missing_patch_clean_v1`
  - `species_data.sinr_new_gbif_strict_missing_singleton_failures_v1`
  - `species_data.sinr_new_gbif_strict_missing_patch_lineage_summary_v1`

### What is safe enough for `V4.1 preview`

- Safe source table: `...completed_v1` above.
- Confidence boundary doc: `docs/SINR V4.1 Data Confidence Matrix.md`.
- Safe current direction:
  - repoint strict/hybrid release builders to the completed lineage,
  - build a **strict-core preview table** from repaired strict raw + preview labels/meta,
  - exclude unresolved families rather than pretending they are canonical.
- Current built preview artifact:
  - `species_data.sinr_v41_preview_strict_core_v1`
  - `8,392,893` rows
  - `643` columns
  - `445,595` rows excluded relative to `completed_v1`
- Current temporal design for `V4.1 preview` is **intentionally narrow**:
  - the true temporal branch is AE-only (`2017-2024` AlphaEarth sequence = `512D`),
  - non-AE temporal-ish signals currently enter only as year-matched or summary scalar features,
  - richer multi-source temporal intelligence is deferred to `V4.2+` / `V4.3` after provenance design is explicit.
- Current strict-core preview should prefer:
  - AE embeddings,
  - terrain / hydro / Hansen / JRC water / biomass / human modification / Xiao,
  - most BIO / soil / TerraClimate families with contamination guards,
  - Dynamic World only with corrected ESA remap semantics for pre-2015 proxy rows,
  - MODIS GPP only after explicit high-code fill masking.
- Current strict-core preview should **exclude or quarantine**:
  - `gedi_canopy_height_m` until GEDI semantics are verified,
  - `gedi_foliage_height_div` until the correct FHD band semantics are confirmed,
  - external/manual/preview-backed families that are still non-canonical (`carbon extras`, `HILDA`, `aridity/ET0/IPCC`, `land_state`, `introduced/native` unless rejoined with explicit provenance).

### Current unresolved semantic risks

- `MODIS GPP`:
  - pre-2001 NULL semantics are repaired,
  - explicit high-code contamination at `65530-65535` is real and must be masked/guarded,
  - the broader `30000-49999` range is **not** yet proven to be fill and should not be wiped blindly.
- `GEDI`:
  - collection-level `.mosaic()` behavior was a real risk and code has been moved toward specific image assets,
  - exact canopy/FHD band semantics still require one more verification pass before treating GEDI as canonical.
- `.unmask(0)`:
  - still a real source of hidden missingness for some non-AE families;
  - treat row filters / sentinels / validity flags as part of `V4.0` cleanup, not optional polish.
- External/manual families:
  - still not canonical strict raw; either rebuild them or fail closed in preview.

### Active beads pipeline for the current program

- `treekipedia-bj7` — keep backfill strict extraction running to completion.
- `treekipedia-cl3` — repoint release builders to completed `new_gbif` strict lineage and rebuild release artifacts.
- `treekipedia-9vo` — verify/fix non-AE strict raw semantics (GPP, GEDI, masked-zero families, DW proxy semantics).
- `treekipedia-8b2` — canonicalize or explicitly exclude external/manual families.
- `treekipedia-bfc` — build the reduced-scope `V4.1` strict-core preview dataset and preview-model run.
- `treekipedia-2t9` — design the future multi-source temporal intelligence expansion for `V4.2+`.
- `treekipedia-csc` — after backfill completes, build the full strict unified training table from strict feature outputs.

### Operational rule

- Do **not** drift back into generic `v3.x` model tweaking until `V4.1 preview` has a documented confidence matrix, strict-core contract, fresh normalization stats, and a rebuilt release path.

## 4.2) Current Data Governance Findings (2026-03-12 to 2026-03-15)

- `species_data.sinr_v3_unified_v2_final` is deleted and should stay retired.
- `species_data.sinr_v3_features_new_gbif_strict_full` is currently the cleanest active raw strict feature table for the `new_gbif` branch.
- `species_data.sinr_v3_unified_strict_train_v30_preview_clean` remains the safest current training table, but it still inherits old pre-strict extraction feature values.
- Current preview training rows show no multi-year coordinate preservation by `(data_source, lat4, lon4)`, while strict raw `new_gbif` does preserve multi-year contexts.
- Final canonical training data should be rebuilt from strict raw outputs, not from preview-clean or legacy unified tables.
- Master future row grain should be occurrence/example based, with context attached per `(lat4, lon4, observation_year, emb_year)`.
- Do not delete further legacy tables until retirement review is complete; salvageability must be assessed first.
- **Xiao bug (2026-03-13)**: 358K contexts in `sinr_v3_features_new_gbif_strict_full` have xiao=0 instead of xiao=2 due to pre-fix extraction. Correction overlay: `sinr_xiao_correction_overlay_v1` (LEFT JOIN for training). Long-term: rebuild clean xiao column against ALL occurrences after GEE extraction completes (`treekipedia-wtt`). Findings: `docs/SINR Xiao Full-Scope Audit Findings.md`.

### Beads issues tracking this work

- `treekipedia-xi6` — forensic audit SINR data lineage and master dataset
- `treekipedia-cz6` — design SINR master dataset v1
- `treekipedia-csc` — rebuild strict-full unified training table from strict feature outputs
- `treekipedia-qhs` — version species knowledge schema and releases
- `treekipedia-9bw` — plan legacy SINR table retirement and archive policy
- `treekipedia-08v` — audit legacy context salvageability

### Non-destructive salvage audit tables now available

- `species_data.sinr_occurrence_unified_source_v1`
- `species_data.sinr_occurrence_salvage_status_v1`
- `species_data.sinr_occurrence_salvage_candidates_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_v1`
- `species_data.sinr_occurrence_salvage_audit_sample_legacy90_v1`
- `species_data.sinr_occurrence_salvage_summary_v1`
- `species_data.sinr_occurrence_field_integrity_status_v1`
- `species_data.sinr_occurrence_integrity_reconciliation_v1`
- `species_data.sinr_hybrid_override_registry_v1`
- `species_data.sinr_hybrid_override_candidate_queue_v1`
- `species_data.sinr_hybrid_override_duplicate_audit_v1`
- `species_data.sinr_hybrid_override_orphan_audit_v1`
- `species_data.sinr_occurrence_release_eligibility_v1`

Notes:

- These are audit/decision-support tables only; they are not yet promoted training releases.
- `strict_full` counts will move while `sinr_v3_features_new_gbif_strict_full` is still extracting.
- Backfill currently has no strict-full raw table yet, so its rows cannot yet land in `strict_full`.
- `sinr_occurrence_field_integrity_status_v1` is a coarse first-pass field-family scaffold, not the final feature-family truth layer.
- Hybrid rows are now fail-closed by default via `release_gate_default='block_pending_audit_override'` until explicit audit promotion.
- Important: release gates are still advisory until an enforced release builder exists.
- First enforced release builder now exists: `orchestrator/build_sinr_strict_only_release.py` producing `sinr_train_release__strict_only_*` tables from gate-approved rows only.
- Hybrid override system now exists but has zero approvals by default; no hybrid rows are release-eligible until explicitly entered into `sinr_hybrid_override_registry_v1`.
- Hybrid train-only release builder now exists, but currently resolves to the same rows as strict-only because `allow_hybrid_release = 0`.
- Temporal contract work is now tracked separately: `emb_year` should be treated narrowly as AE anchor year, while non-AE temporal families need per-family sampled-year and fallback provenance.

## 5) Hard Safety Rules

- Never train from `species_data.sinr_v3_unified_v2_final`.
- Preview training table: `species_data.sinr_v3_unified_strict_train_v30_preview_clean`.
- Keep strict HIT/MISS separation:
  - HIT train: `species_data.sinr_v3_unified_strict_train`
  - MISS quarantine: `species_data.sinr_v3_strict_unified_quarantine`
- Canonical dedup key: `(data_source, taxon_id, lat4, lon4, observation_year, emb_year)`.

## 6) Current Program State

For current SINR work, the `V4.0 -> V4.1 preview -> V4.2 full` framing in section `4.1` supersedes the historical `v3` experiment queue below. Keep the older `v3` notes as benchmark context only.

- **Best model**: v14_location_5m = radiata rank **#2 / 45,247** (prob=0.9395, zero land-state, location encoding ON)
- **Previous best**: v8_hardcap_5m_full = rank #2 (prob=0.9785, but seed variance — no location encoding)
- **Baseline**: v4_gatefix_5m = rank #12 (zero land-state)
- **CRITICAL FINDING**: Model has NO coordinate inputs (no lat/lon/geohash). It is 100% niche-based — cannot distinguish NZ from Chile if climate matches. AlphaEarth embeddings encode land cover appearance, NOT location.
- **Key finding**: Hard cap per-shard is USELESS (0 rows removed). v8 improvement over v4 is seed variance.
- **Key finding**: Single-coordinate benchmark has ~10-rank variance across random seeds.
- **Key finding**: Aux heads ARE useful — v11 (no aux) regressed to #106 despite best val. Aux heads provide signal.
- **Key finding**: bg-weight 1.0 is a good regularizer (val top10=50.3%) without hurting rank.
- **Feature parity FIXED**: aridity_index, et0_mm_yr, ipcc_forest_class now wired in GEE sampler.
- **Critical inference flags**: Always use `--land-state-mode zero`, `--zero-phylo-input`, `--disable-intro-in-gate`.
- v5/v6 AN-Full both regressed — REJECTED.
- All recovery runs use versioned contracts under `orchestrator/contracts/sinr_v3/`.

### Full Run Results (all 5-shard, benchmarked with --land-state-mode zero --strict-feature-contract)

| Version | Config | Val Top10 | Rank | Prob | Notes |
|---------|--------|-----------|------|------|-------|
| **v14_location_5m** | **BCE + bg 1.0 + location enc** | **46.3%** | **#2** | **0.9395** | **Location encoding — geographic identity!** |
| v8_hardcap_5m_full | BCE + 50K cap (no-op) | 42.0% | #2 | 0.9785 | Seed variance only (no location) |
| v4_gatefix_5m | BCE baseline | ~42% | #12 | 0.9499 | Original trusted baseline |
| v12_bgweight_5m | BCE + bg-weight 1.0 | 50.3% | #12 | 0.8602 | bg loss = good regularizer |
| v8b_2epoch_5m | BCE + 2 ep/shard | 46.9% | #18 | 0.9526 | Better val but seed noise |
| v5_anfull_5m | AN-Full (buggy sign) | — | #23 | — | Regressed |
| v13_cyclic_5m | BCE + bg 1.0 + 3 cycles | 52.9% | #49 | 0.689 | Cyclical hurt — over-smoothed |
| v15_corrxiao_5m | BCE + bg 1.0 + loc enc + fixed xiao | 46.18% | #57 | — | Xiao decode neutral (was #58 w/ buggy) |
| v6_anfullfix_5m | AN-Full sign-fixed | — | #59 | — | Regressed worse |
| v17_tempmag_5m | BCE + bg 1.0 + loc enc + temporal mag | 44.77% | #83 | — | REJECTED — temporal magnitude no help |
| v11_noaux_5m | BCE + no aux + 2 ep | 50.3% | #106 | 0.7667 | REJECTED — aux heads needed |
| v16a_strictplanted_5m | strict_planted3 label | — | #919 | — | REJECTED — planted label broken |

### Experiment Queue (single-variable, sequential)

1. v8b: 2 epochs/shard — DONE (#18)
2. v11: disable aux heads — DONE (#106 — REJECTED)
3. v12: bg-weight 1.0 — DONE (#12, val top10=50.3%)
4. v13: cyclical shard training (3 cycles × 5 shards × 1 ep) — DONE (#49 — regressed, over-smoothed)
5. **v14: sinusoidal location encoding (`--use-location-encoding`)** — DONE (**#2**, val top10=46.3%)
6. v15: corrected xiao decode (v14 config) — DONE (#57, val 46.18%). Xiao decode neutral.
7. v16a: strict_planted3 label mode — DONE (#919 — REJECTED)
8. v16b: disable planted aux — DONE (#264 — REJECTED)
9. v17: temporal magnitude features — DONE (#83, val 44.77% — REJECTED, no help)
10. **v18: Fix planted signal** — IN PROGRESS. Remove broken boost, add is_planted as 6th land_state dim, fix value_map save, strict_planted3 + pos_weight=5.7. See `memory/SINR_V3_IMPROVEMENT_PLAN.md` for 6-bug chain.
11. **BQ hard cap 50K per species** — NEXT (Tier 1, Gemini audit confirmed critical)
12. **True background sampling** — Tier 1 (requires GEE extraction of 1M random land coords)
13. **Imbalance-Aware Loss (Zbinden 2024)** — Tier 2 (per-class negative weighting)
14. **Multi-point benchmark suite** — Tier 2 (100-1000 diverse coords, MRR tracking)
14. TDWG frequency prior (post-logit, no retrain)
15. H100 full-dataset run with best config (LAST — after exhausting local experiments)

### Location Encoding (v14 — DONE, rank #2)

The model has had NO geographic signal — same predictions for any two locations with identical climate/soil. v14 adds sinusoidal positional encoding:
- `latitude` and `longitude` columns already exist in training data (no BQ changes)
- 10 Fourier frequencies (2^0..2^9), sin+cos for lat and lon = 40D input
- Projected through 40→64 linear layer, concatenated into trunk fusion
- Flag: `--use-location-encoding` on train_on_vm.py and v3_point_inference.py
- This is the single biggest missing signal in the model.

### TDWG Frequency Prior (implemented, awaiting BQ contract build)

Post-logit spatial boost using per-region species occurrence frequency:
- Script: `orchestrator/build_tdwg_frequency_contract.py` (BQ query → JSON contract)
- Inference: `--tdwg-contract` flag on v3_point_inference.py
- Boost: `weight * log(1 + alpha * freq_ratio)` per species (defaults: weight=2.0, alpha=10.0)
- Uses local `orchestrator/tdwg_l3/level3.geojson` for point-in-polygon lookup
- No retraining needed — works on any existing model

### GEE Extraction Status (as of 2026-03-08 00:22)

- **Main extraction**: PAUSED at 207/3,595 batches (~11% total, 1.6M/14.7M rows)
  - Killed PID 99537 on 2026-03-08 to fix Xiao RGB decode bug
  - Will resume with `--resume-from-bq` after xiao backfill completes
  - Last log: `orchestrator/strict_full_reextract_20260307_163230.log`
  - Unsampleable contexts tracked in BQ: `sinr_v3_strict_unsampleable_contexts`

- **Xiao backfill** (in progress): PID 44049
  - **Bug found**: `unified_gee_sampler_v3.py` RGB decode was WRONG for Xiao dataset
    - WRONG: looked for red (R>200, G<50) for planted → matched NOTHING
    - CORRECT: planted = yellow (127,127,0), natural = green (0,127,0)
    - Result: xiao_planted_forest=2 (planted) had ZERO rows in ALL training data
    - Fix committed to `unified_gee_sampler_v3.py` line 230-238
  - **Phase A**: Uploaded 3,778,738 unique coords to `xiao_backfill_coords` (DONE)
  - **Phase B**: 1,890 EE tasks sampling corrected Xiao → `xiao_backfill_results` (IN PROGRESS, ~5h ETA)
  - **Phase C**: Download BQ results → update local parquet shards (pending)
  - Script: `orchestrator/backfill_xiao_shards.py`
  - After local shards updated: resume main extraction with corrected Xiao decode

- **After backfill completes**:
  1. Run Phase C to update local training shards
  2. Resume main extraction: `nohup caffeinate -s python3 orchestrator/unified_gee_sampler_v3_strict.py --all --pool-size 25 --batch-size 2000 --resume-from-bq > orchestrator/strict_full_reextract_$(date +%Y%m%d_%H%M%S).log 2>&1 &`
  3. Main extraction will use corrected Xiao decode for remaining 89% of batches
  4. After main extraction completes, backfill xiao for the 11% extracted with bad decode

## 7) Mandatory Pre-Run Checks

Run before any training or status claim:

```bash
python3 orchestrator/check_v30_preview_readiness.py
bq query --nouse_legacy_sql 'SELECT COUNT(*) AS rows FROM `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_preview_clean`'
```

## 8) Strict Extraction Operations

Script:

- `orchestrator/unified_gee_sampler_v3_strict.py`

Outputs:

- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_features_backfill_strict_full`

Failure ledger:

- `species_data.sinr_v3_strict_unsampleable_contexts`

Restart command:

```bash
nohup python3 orchestrator/unified_gee_sampler_v3_strict.py --all --pool-size 25 --batch-size 2000 --resume-from-bq > orchestrator/strict_full_reextract_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

## 9) Training Paths

### v3.0 strict preview (now)

- Table: `species_data.sinr_v3_unified_strict_train_v30_preview_clean`
- Runbook: `docs/SINR V3.0 Strict Preview Runbook.md`
- Versioning registry: `docs/SINR Versioning Registry.md`

### v3.x recovery branch (contract-aligned)

- Use versioned contracts under `orchestrator/contracts/sinr_v3/`.
- Minimum required references for any run claim:
  1. mapping contract file + mapping SHA,
  2. feature contract file,
  3. normalization stats contract,
  4. intro-ratio contract file (if introduced boost used),
  5. training log path.

Recovery experiment sequence (updated 2026-03-07):
1. P0-A: `--land-state-mode zero` — DONE. #16 → #12.
2. P0-B: Wire missing GEE features — DONE. aridity_index, et0_mm_yr, ipcc_forest_class.
3. P1-A: `--hard-cap-per-species 50000` — DONE but NO-OP. v8=#2 (seed variance).
4. Training depth: `--epochs-per-shard 2` (v8b) — DONE. #18, val top10=46.9%.
5. P1-B: `--aux-planted-weight 0 --aux-land-state-weight 0` — DONE. #106 — REJECTED.
6. P1-C: `--bg-weight 1.0` — DONE. #12, val top10=50.3%. Good regularizer.
7. P2-A: `--cycles 3` cyclical shard training — DONE (v13). #49 — regressed, over-smoothed.
8. **P3-A: `--use-location-encoding` sinusoidal lat/lon** — DONE (v14). **#2** — location encoding works!
9. P3-B: TDWG frequency prior (`--tdwg-contract`) — NEXT. Post-logit, no retrain needed.
10. H100 full-dataset run with v14 config (location enc + bg-weight 1.0).

Critical warnings:

- Do not use per-sample taxon phylo vectors as model input. Use `--zero-phylo-input`.
- Do not use `--land-state-mode heuristic` at inference. Use `--land-state-mode zero`.
- Do not stack multiple changes per experiment. Single-variable only.
- Do not use smoke (s0) rankings as go/no-go for 45K species tasks.
- Hard cap per-shard is useless — must be applied BEFORE sharding at BQ level.
- Training data columns `latitude`/`longitude` exist but were NOT fed to model until v14.
- AlphaEarth embeddings encode land cover appearance, NOT geographic location.

### v3.1 strict full (after extraction complete)

1. Rebuild strict unified full table from strict extraction outputs.
2. Re-run gateboard + preflight.
3. Train final model and compare against preview.

## 10) SINR v3 Improvement Roadmap

**Reference docs**: `memory/SINR_V3_IMPROVEMENT_PLAN.md`, `memory/RESEARCH_SYNTHESIS_AE_EMBEDDINGS.md`

### Key Research Findings (March 7, 2026)

- **AE embeddings are NOT redundant with WorldClim** — AEF predicts temperature FROM satellite imagery (reconstruction target, not input). R²=0.97 = 10m microhabitat ecology. Do NOT orthogonal condition.
- **Imbalance-Aware Loss** (Zbinden 2024) — most promising loss function upgrade for rare species.
- **AE vectors on unit hypersphere** — cosine similarity correct, not Euclidean.

### v3 Phase 0: Inference Improvements (current v14 model, no retraining)
- [ ] **0A**: Expose aux outputs (planted_score, land_state_pred) from `/sinr-infer`
- [ ] **0B**: Two-pass inference (is_introduced=0 and 1, take MAX per species)
- [ ] **0C**: Probability + rank blend scoring (not just inverse-log rank)
- [ ] **0D**: Phylogenetic coherence re-ranking (adaptive threshold, full distribution)

### v3 Phase 1: Training Improvements (single-variable, one at a time)
- [ ] **1A**: Temporal magnitude features (||e_{t+1} - e_t|| scalars — plantation detection)
- [ ] **1B**: Per-dimension gating (replace scalar alpha with 64D gate vector)
- [ ] **1C**: BQ-level hard cap per species (50K BEFORE sharding)
- [ ] **1D**: TDWG frequency prior (post-logit boost, no retrain)
- [ ] **1E**: Imbalance-Aware Loss (Zbinden et al. 2024)
- [ ] **1F**: Phylogenetic output-layer regularization (bake phylo into weights)

### v3 Phase 2: Architecture Fixes (medium risk)
- [ ] **2A**: FiLM conditioning (context-dependent AE embedding interpretation)
- [ ] **2B**: Cosine diffs in temporal module (respect hyperspherical geometry)
- [ ] **2C**: Fix planted label using JRC forest type (jrc_forest_type=4)
- [ ] **2D**: Land state parity (train = serve)
- [ ] **2E**: Add ALOS PALSAR HH/HV (L-band SAR biomass proxy)

---

## 11) SINR v4 Future Work (separate from v3)

**Reference docs**: `.claude/project-management/KNOWLEDGE_SCHEMA_FOR_V4_TRAINING.md`

### v4 Model Architecture (requires new training pipeline)
- [ ] LE-SINR text embeddings — 6th branch, 384D sentence transformer per species
- [ ] ControlNet-style middle fusion (Sat-SINR paper, ISPRS 2024)
- [ ] Stable/dynamic subspace decomposition (split 64D AE by temporal variance)
- [ ] Species-conditioned temporal queries (phylo → attention)
- [ ] Hybrid spatial hashgrid (multiresolution, replaces implicit FCNet)
- [ ] Carbon regression aux head (AGB, NPP, SOC)
- [ ] Species-level trait features as model inputs (wood density, SLA, root depth)

### AI Researcher Knowledge Pipeline (can start now, feeds v4)
- [ ] **Week 1-4**: Fill 8 missing functional traits for 48K researched species (mycorrhizal type, N-fixation, light req, seed dispersal, SLA, wood density, drought/frost tolerance, root depth)
- [ ] **Week 1-12**: Process 19,614 unresearched species (multi-model consensus)
- [ ] **Week 12-16**: Expert review of low-confidence species
- [ ] **Week 16-24**: Generate sentence transformer embeddings for all 67K species
- [ ] Schema expansion: Add 8 new fields to species table (see KNOWLEDGE_SCHEMA_FOR_V4_TRAINING.md)

## 12) Anti-Drift Protocol

After any major step (rebuild/extraction/training):

1. Close the relevant beads issue: `bd close <id>`
2. Update `docs/SINR V3 All Fronts Gateboard.md`.
3. Update `docs/SINR V3 Situational Awareness Dossier.md`.
4. Update `docs/SINR Versioning Registry.md` with new `vN` artifacts.
5. Write/append iteration doc (`docs/SINR March 6 Recovery Iteration v*.md`) with exact paths.
6. Keep benchmark coordinate results tied to explicit model/checkpoint + contract versions.
7. Record top-20 benchmark species and local introduced/native evidence in audit docs when rankings materially change.
8. Keep this GO.md short and current (do not append historical logs here).
9. `bd sync` — ensure task state is persisted.

Historical notes should go to dedicated archive docs, not GO.md.
