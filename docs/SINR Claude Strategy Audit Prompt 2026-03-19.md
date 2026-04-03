# SINR Claude Strategy Audit Prompt 2026-03-19

Use this prompt to get an external Claude-style opinion on the current SINR V4 strategy.

## Prompt

You are auditing the current SINR V4 radiata-recovery strategy.

Do not assume the current team strategy is correct.
Be blunt, skeptical, and specific.

We are trying to improve the canonical `Pinus radiata` plantation benchmark in New Zealand under the current strict V4 data-governance program.

### Read these first

1. `docs/SINR Current Program State.md`
2. `.claude/project-management/GO.md`
3. `docs/SINR Radiata Rank-1 Program.md`
4. `docs/SINR P1-P2-D1-T1 Runbook.md`
5. `docs/SINR Radiata Suite Benchmark Report 2026-03-19.md`
6. `docs/SINR V4.1 Data Confidence Matrix.md`
7. `docs/SINR GEDI Probe Findings 2026-03-18.md`
8. `docs/SINR Claude Opinion Handoff - Post-Merge Radiata Forensics.md`

Historical reference docs:

9. `docs/SINR_V3_EXPERIMENT_HISTORY.md`
10. `docs/SINR v3 Master Recovery Plan.md`
11. `docs/SINR V4.2 Comparison Analysis.md`
12. `docs/march 16/report claude.md`

Artifact/config anchors:

13. `~/model_v47_merged_anfull/model_config_v3.json`
14. `~/model_v42_anfull_hardcap_full/model_config_v3.json`
15. `~/model_v43a_nolocation/model_config_v3.json`
16. `~/model_local_contract_v4_gatefix_5m/model_config_v3.json`
17. `~/model_local_contract_v14_location_5m/model_config_v3.json`

### Core facts you should use

- Current canonical merged no-GEDI training table:
  - `species_data.sinr_v47_merged_strict_core_train_v2`
- Current merged no-GEDI model:
  - `~/model_v47_merged_anfull`
- Current recipe-faithful canonical result:
  - around `#74 / 45,096`
- Restored radiata support in the merged line:
  - about `9,090` matched rows
  - about `37` within `25km`
- Strong version of “more data is the missing piece” is now falsified
- Current merged non-GEDI data does not look broadly corrupt
- Remaining non-GEDI data questions are narrow:
  - `modis_gpp_mean` `NULL` vs `0`
  - pre-2015 `Dynamic World` / `ESA` proxy mismatches
  - smaller `xiao_planted_forest` branch mismatches
  - tiny `modis_lc_at_obs = -1` residue

### GEDI status

- GEDI is excluded from the current canonical merged training path
- Probe showed current raw GEDI in both branches is contaminated by historical collection-mosaic misuse
- A GEDI-only coord-grain repair lookup is being built in parallel
- GEDI is not the current blocker for the no-GEDI radiata failure

### New local benchmark suite results you must consider

Target taxon: `GymPiPiPnCx50820-00`

Points (`year=2023`):

- canonical: `(-41.151583464812404, 175.09968969862783)`
- nearby_1: `(-41.15417025743087, 175.09915476475814)`
- nearby_2: `(-41.15504998747567, 175.1065715571766)`
- nearby_3: `(-41.15927635199013, 175.09953576436868)`
- nearby_4: `(-41.18626808111574, 175.0509971829668)`

Current replay suite summary:

- `v47_merged`: canonical `#74`, nearby ranks `83/90/75/84`, median `83`, worst `90`
- `v41_preview`: canonical `#105`, nearby ranks `115/111/114/125`
- `v42_anfull`: canonical `#105`, nearby ranks `120/95/110/117`
- `v43a_nolocation`: canonical `#100`, nearby ranks `106/95/99/99`
- `v4_gatefix_legacy`: canonical `#4`, nearby ranks `163/172/5/3`
- `v14_location_legacy`: canonical `#54`, nearby ranks `146/153/43/42`

This means:

- the merged V4 model is the best current stable local-suite model, but still weak
- historical `v14 #2` is not reproducing under current replay
- legacy `v4_gatefix` looks extremely strong on some nearby points and terrible on others
- benchmark/inference parity is a major unresolved issue

### What we want from you

Audit the strategy itself.

Answer these questions:

1. Is the current rank-1 program ordering sensible?
   - parity -> narrow data validation -> BCE baseline -> background negatives -> plantation-aware supervision -> retrieval/head diagnosis -> GEDI later
2. What is most likely wrong now?
   - data integrity
   - inference parity
   - representation
   - ranking head / objective
   - plantation supervision
   - missing true negatives
3. Which current assumptions look strongest, and which still look weak or under-justified?
4. Is `T1 = merged BCE baseline` the right first training experiment after `P1/P2/D1`, or would you change the order?
5. How should we interpret the fact that `v4_gatefix_legacy` is brilliant at some nearby points and awful at others?
6. What old `v2/v3` clues are worth reviving, and which are probably legacy artifacts or harness accidents?
7. What are the top 3 smallest falsifying experiments you would run next?
8. What are we still missing from the strategy?

### Important constraints

- Do not recommend broad destructive data churn unless you can justify it
- Do not fall back to “just add more data”
- Treat the current merged non-GEDI table as provisionally sound unless you can point to a specific still-open failure family
- Assume the team wants a disciplined, one-change-at-a-time program

### Output format

Return:

1. A blunt diagnosis of the current strategy
2. What you agree with
3. What you think is wrong or incomplete
4. The 3 next experiments you would run, in order
5. Any doc / benchmark / harness changes you would require before trusting future comparisons
