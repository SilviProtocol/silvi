# SINR March 7 Comprehensive State + Audit Request Packet

Date: 2026-03-07
Owner: Codex session handoff
Audience: external auditors (Claude, Gemini, other ML/SDM agents)
Intent: provide full operational context, exact references, and reproducible evidence for fresh external diagnosis after recent regressions.

## 0) Executive Snapshot

Current truth:

- Strict GEE extraction is running and progressing.
- The strongest trustworthy radiata benchmark result in this phase is currently **v4 gate-fix + Xiao parity: rank #16 / 45,247**.
- Follow-up AN-Full iteration (v5) regressed benchmark to **#23 / 45,247**.
- Team sentiment: regression is unacceptable; next steps must be tightly controlled and auditable.

Canonical benchmark coordinate:

- `lat=-41.151583464812404`
- `lon=175.09968969862783`
- target taxon: `GymPiPiPnCx50820-00` (radiata key in current mapping)

## 1) Non-Negotiables

- Do not corrupt or overwrite strict BQ/GEE data.
- Keep strict HIT/MISS integrity.
- Version all material model/data contracts and runs.
- No quality claims without explicit model/checkpoint/contract references.

## 2) Core Program References (read first)

Primary docs:

1. `docs/SINR March 5 Codex.md`
2. `docs/SINR March 6.md`
3. `docs/SINR March 6 Recovery Iteration v2.md`
4. `docs/SINR March 6 Cultivation Introduced Audit Handoff.md`
5. `docs/SINR March 6 External Audit Packet.md`
6. `docs/SINR Versioning Registry.md`
7. `.claude/project-management/GO.md`
8. `.claude/project-management/MASTER_PREDICTION_ARCHITECTURE_3.md`

Core code:

- `orchestrator/train_on_vm.py`
- `orchestrator/v3_point_inference.py`
- `orchestrator/location_predictor_FIXED.py`
- `orchestrator/run_local_5m_shard_training.py`
- `orchestrator/unified_gee_sampler_v3_strict.py`

## 3) Data State (BigQuery)

Validated strict table counts used in this phase:

- `species_data.sinr_v3_unified_strict_train`: `22,033,317` rows, `45,247` species
- `species_data.sinr_v3_strict_unified_quarantine`: `9,640,797` rows

Important operational tables:

- `species_data.sinr_v3_features_new_gbif_strict_full`
- `species_data.sinr_v3_features_backfill_strict_full`
- `species_data.sinr_v3_strict_unsampleable_contexts`

## 4) GEE Strict Extraction Status (post-reboot)

Process:

- `orchestrator/unified_gee_sampler_v3_strict.py` (running)

Monitor snapshot (latest during this packet creation):

- `new_rows=1,175,856`
- `total_remaining=13,534,482`
- EE states: `PENDING 23`, `RUNNING 2`, `SUCCEEDED 611`, `FAILED 6`, `CANCELLED 25`
- rolling rate ~`51,902 rows/hour`
- ETA ~`10.87 days`

Restart log after machine reboot:

- `orchestrator/strict_full_reextract_20260306_194321.log`

Safety note:

- strict sampler path is append/resume oriented; no destructive overwrite command path was used in this session.

## 5) Versioned Contracts in Use

Directory:

- `orchestrator/contracts/sinr_v3/`

Current key contracts:

- mapping: `mapping_contract_v1.json` (`45,247` species)
- feature: `feature_contract_v2_online56.json` (58 env continuous)
- frequency: `species_frequency_contract_v2_strict_full.json`
- introduced ratio: `intro_ratio_contract_v1_strict_full.json`
- stats: `normalize_stats_v3_v2_online56_preview4m.npz`
- temporal stats: `normalize_temporal_v3_v2_online56_preview4m.npz`

Registry:

- `docs/SINR Versioning Registry.md`

## 6) Timeline of Key Iterations and Outcomes

### v3_nophylo_5m (phylo leakage mitigation)

- model dir: `~/model_local_contract_v3_nophylo_5m`
- log: `orchestrator/local_contract_v3_nophylo_5m_20260306_1502.log`
- benchmark result: roughly `#71 / #66 / #67` (native/unknown/introduced)

### v4_gatefix_5m (introduced removed from gate routing)

- model dir: `~/model_local_contract_v4_gatefix_5m`
- log: `orchestrator/local_contract_v4_gatefix_5m_20260306_1734.log`
- initial benchmark (pre Xiao parity alignment): `#5`
- benchmark after Xiao parity alignment: **`#16` (trusted)**

### v5_anfull_5m (AN-Full loss ablation)

- model dir: `~/model_local_contract_v5_anfull_5m`
- log: `orchestrator/local_contract_v5_anfull_5m_20260306_1953.log`
- status: completed (`checkpoint_epoch_1..5`)
- benchmark result: **`#23`** (regression vs v4 trusted `#16`)

## 7) Critical Findings (Confirmed)

1. **Train/serve phylo mismatch existed and was severe**
- training previously consumed per-sample taxon phylo; rank-all inference cannot know true species phylo.
- mitigation applied: `--zero-phylo-input`.

2. **Introduced boost path was dead until intro-ratio contracts were loaded**
- prior buffer all-zero behavior observed.
- contract loading enabled path, but effect remains weak/unstable.

3. **Introduced conditioning in old gate setup behaved backward at benchmark point**
- higher introduced input lowered planted probability and lowered boost term.

4. **Xiao categorical train/serve decode mismatch existed**
- point inference decode was not aligned with extractor logic.
- alignment removed a misleading shortcut and changed benchmark from `#5` to trusted `#16` on v4.

5. **Confuser set remains strong and introduced flag is not sufficiently discriminative**
- top local confusers in NZ are also introduced-labeled in many cases.
- introduced alone cannot separate radiata from those confusers.

## 8) Current Benchmark Context (why this is hard)

At and around benchmark coordinate:

- local top-20 is mixed introduced/native set, not a simple split.
- local density and global frequency of confusers matter.
- model still needs better congener discrimination under plantation-like context.

See detailed evidence in:

- `docs/SINR March 6 Cultivation Introduced Audit Handoff.md`

## 9) What External Auditors Should Focus On Now

Please prioritize root-cause ranking for:

1. Why AN-Full port regressed from `#16` to `#23` under otherwise similar settings.
2. Whether aux planted/land-state coupling is still harming primary species ranking.
3. Whether introduced should remain only as post-logit prior and never in feature routing.
4. Best low-risk way to improve congener discrimination (Pinus/Pseudotsuga confusers).
5. Whether current AN-Full implementation in `train_on_vm.py` is mathematically equivalent to intended v2.2 behavior, or missing terms.

## 10) Repro Commands (single-point eval)

v4 trusted benchmark command:

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 \
  --lon 175.09968969862783 \
  --year 2023 \
  --model-dir ~/model_local_contract_v4_gatefix_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all \
  --top-k 20 \
  --disable-intro-in-gate
```

v5 AN-Full benchmark command:

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 \
  --lon 175.09968969862783 \
  --year 2023 \
  --model-dir ~/model_local_contract_v5_anfull_5m \
  --mapping-contract orchestrator/contracts/sinr_v3/mapping_contract_v1.json \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v2_online56.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v1_strict_full.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all \
  --top-k 20 \
  --disable-intro-in-gate
```

## 11) Safety Constraints for Any Proposed Next Steps

Allowed:

- read-only BQ analysis queries,
- local code patches and local training runs,
- new versioned artifacts/docs.

Disallowed unless explicitly approved:

- destructive BQ operations,
- changing strict extractor destination semantics,
- stopping strict extractor without explicit instruction.

## 12) Requested External Deliverable Format

For each recommendation:

1. expected direction/magnitude on benchmark rank,
2. risk level and rollback path,
3. exact files/functions to patch,
4. one-line verification command.

## 13) Current Decision Gate

No further broad changes should be stacked blindly.

Current control:

- `v4_gatefix_5m` with Xiao parity-aligned inference (`#16`) is the trusted baseline.

Current candidate (regressed):

- `v5_anfull_5m` (`#23`).

Next iteration should be single-variable, benchmark-gated, and only promoted if it beats `#16`.
