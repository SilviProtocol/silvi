# SINR v3 Situational Awareness Dossier

Date: 2026-03-06
Purpose: single-source briefing for external AI audits and operator handoff.

## 1) Mission State

- Objective: deliver highest-accuracy SINR v3 with strict temporal integrity and strict species-year label confidence.
- Current strategy: run strict full re-extraction in parallel, train a strict-preview model now, then train strict-full v3.1 when extraction completes.

## 2) Source-of-Truth Hierarchy

1. Live BigQuery tables and query results.
2. Executable pipeline/training scripts in `orchestrator/`.
3. Forensic status doc: `docs/SINR March 5 Codex.md`.
4. Planning docs (`docs/SINR March 5 - Claude`, etc.) as intent, not integrity truth.

## 3) What Happened (Condensed)

- v3 data scale-up succeeded (new GBIF + backfill + temporal stacks + enrichment).
- Integrity issues discovered in legacy assembly:
  - row explosion risk in legacy final join path,
  - duplicate pressure,
  - temporal compression in legacy unified sampler,
  - backfill label ambiguity from coordinate-only taxon assignment path.
- Strict rebuild path created clean HIT-only preview training table.
- Strict full re-extraction started to recover full temporal fidelity and avoid historical shortcuts.

## 4) Live Data Snapshot (latest known)

- `species_data.sinr_v3_unified_v2`: 32,323,081 rows (legacy assembled table).
- `species_data.sinr_v3_unified_strict_train`: 22,033,317 rows (strict HIT-only core).
- `species_data.sinr_v3_strict_unified_quarantine`: 9,640,797 rows (strict MISS/uncertain).
- `species_data.sinr_v3_unified_strict_train_v30_preview_clean`: 22,033,317 rows (preview-compatible + carbon sentinels converted to NULL for key fields).
- `species_data.sinr_v3_features_new_gbif_strict_full`: active ingest (strict full extraction in progress).
- `species_data.sinr_v3_strict_unsampleable_contexts`: unsampleable context ledger.
- Accounting: `unified_v2 (32,323,081)` vs `strict_train + quarantine (31,674,114)` leaves `648,967` duplicate-collapse rows (not missing keyspace).
- Species visibility: `732` species exist only in quarantine (no strict-HIT training rows currently).

## 5) Integrity Status By Front

### Temporal integrity

- Strict preview table has valid year fields (`observation_year`, `emb_year`) and no temporal null/sentinel values.
- Full strict extraction is still required for final temporal confidence on all contexts.

### Label integrity

- Strict preview rows are HIT-only, traced to trusted occurrence sources:
  - `existing_training_coords` (backfill branch)
  - `gbif_new_occurrences` (new GBIF branch)

### Join/cardinality integrity

- Strict preview canonical key `(data_source,taxon_id,lat4,lon4,observation_year,emb_year)` is deduped.
- Land-state and introduced/native joins are key-safe in strict path.

### Carbon integrity

- Carbon features are present and consumed by trainer.
- Coverage is not complete for every context.
- Key carbon sentinel values (`-9999`) were NULL-converted in preview-clean table for safer training preprocessing.
- Strict full extraction + strict rebuild remains required for final carbon-temporal confidence.

### Trainer contract readiness

- `train_on_vm.py` schema contract validated against `sinr_v3_unified_strict_train_v30_preview_clean`.
- Preview preflight script exists and passes: `orchestrator/check_v30_preview_readiness.py`.

## 6) Running Jobs and Operational State

- Strict full extractor process: `orchestrator/unified_gee_sampler_v3_strict.py`.
- Resume support: yes (`--resume-from-bq`).
- Unsampleable tracking: yes (`species_data.sinr_v3_strict_unsampleable_contexts` + local JSONL log).
- Live telemetry helper: `orchestrator/monitor_strict_extraction.py`.
- Note: extractor state handling was hardened to recognize `SUCCEEDED` task states from EE operations and avoid queue stalls.

## 7) ETA and Throughput

- Total strict contexts target: ~14.71M.
- As-of 2026-03-05 22:20 local, strict new-GBIF full table has ~124,699 rows; backfill strict-full not started yet.
- Prior 90k/hour estimate came from an early burst and should not be treated as stable throughput.
- Current ETA is **uncertain** and must be computed from rolling live telemetry; use gateboard + live table counts, not fixed-day claims.

## 8) Preview Training Plan (v3.0)

- Train now on `species_data.sinr_v3_unified_strict_train_v30_preview_clean`.
- Use preview as learning cycle for architecture and error discovery.
- Do not treat v3.0 preview as final production candidate.

## 9) Final Training Plan (v3.1 strict-full)

1. Finish strict full extraction.
2. Rebuild strict full unified table from strict outputs.
3. Re-run gateboard and preflight.
4. Train full v3.1 strict model.
5. Compare v3.0 preview vs v3.1 strict-full before promotion.

## 10) Current Blockers and Risks

- GPU quota blocker observed in GCP project (`H100` family limit 0 and `GPUS_ALL_REGIONS` shows 0).
- Extraction runtime variability due GEE task scheduling and retries.
- Carbon/hilda sparsity in some contexts requires robust missingness handling.

## 11) Anti-Drift Controls

- Keep this dossier + `docs/SINR V3 All Fronts Gateboard.md` updated at each major step.
- Treat `.claude/project-management/GO.md` status override as onboarding anchor.
- Every training run requires preflight pass and explicit source table declaration.

## 12) External AI Audit Prompt (drop-in)

Use this prompt with external auditors:

"Audit SINR v3 integrity and readiness using these docs/tables as source-of-truth. Verify: (1) temporal integrity and context grain, (2) label HIT/MISS policy correctness, (3) join/cardinality safety, (4) carbon completeness/sentinel handling, (5) trainer schema compatibility and leakage risks, (6) extraction resume and unsampleable handling, (7) go/no-go for v3.0 preview and v3.1 strict-full. Require explicit evidence references and challenge any unverified claim."

## 13) Key References

- `docs/SINR March 5 Codex.md`
- `docs/SINR V3 All Fronts Gateboard.md`
- `docs/SINR V3.0 Strict Preview Runbook.md`
- `orchestrator/unified_gee_sampler_v3_strict.py`
- `orchestrator/check_v30_preview_readiness.py`
- `orchestrator/train_on_vm.py`
- `orchestrator/train_on_gcp.sh`
- `.claude/project-management/GO.md`
