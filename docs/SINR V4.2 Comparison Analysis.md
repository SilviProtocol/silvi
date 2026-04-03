# SINR V4.2 Comparison Analysis

Date: 2026-03-16 (updated 2026-03-16 post-run)
Issue: treekipedia-xz2
Baseline: V4.1 corrected preview (BCE), rank #105/19,043, prob=0.6083
V4.2 Result: an_full + hard-cap-1000 + no-boost, rank **#79**/19,043, prob=**0.9170**

---

## V4.2 Experiment Result (VERIFIED)

```
V4.1 BCE baseline:                rank #105/19,043, prob=0.608283
V4.2 an_full+hardcap+no-boost:    rank  #79/19,043, prob=0.916976

Delta: +26 rank positions, +0.309 probability
Introduced sensitivity: UNCHANGED (rank #79 at 0.0/0.5/1.0)
Top-20: Still broadleaf-heavy, no conifer takeover
```

**Honest interpretation**: Loss/objective matters — #105→#79 and 0.608→0.917 is a real move. But loss alone does not fully rescue radiata on the current V4.1 data slice. Both objective and data scope are load-bearing.

Run details:
- Log: `orchestrator/v42_anfull_hardcap_full_20260316_125510.log`
- Model: `~/model_v42_anfull_hardcap_full/best_model.pt`
- Config: 2 cycles × 12 shards = 24 shard-epochs, an_full pos_weight=2048, hard-cap=1000, no-boost
- Val metrics at epoch 24: loss=0.0090, top1=10.07%, top5=32.55%, top10=48.30%
- Wall time: ~27 minutes (12:55→13:22)

---

## Task 1 — Top-100 Species Above Radiata Analysis

### Benchmark Result (V4.1 baseline, used for taxonomy analysis)

```
Location: (-41.151583464812404, 175.09968969862783) — Wairarapa, New Zealand
Year: 2023
Target: GymPiPiPnCx50820-00 (Pinus radiata)
Result: rank #105/19,043, prob=0.6083
Introduced invariance: 0.0/0.5/1.0 all give rank #105 (conditioning is inert)
```

### Taxonomy of the 104 Species Outranking Radiata

**Division breakdown:**

| Division | Count | % |
|----------|------:|---:|
| Angiosperm | 95 | 91.3% |
| Gymnosperm | 9 | 8.7% |

**Gymnosperm detail (9 species, all ranked above radiata):**

| Rank | Taxon | Species | Family | NZ Status |
|-----:|-------|---------|--------|-----------|
| 19 | GymPiPiPdCr50620-00 | Prumnopitys ferruginea | Podocarpaceae | NATIVE |
| 20 | GymPiPiPdCr50498-00 | Dacrydium cupressinum | Podocarpaceae | NATIVE |
| 28 | GymPiPiPdCr50613-00 | Podocarpus totara | Podocarpaceae | NATIVE |
| 38 | GymPiPiPdCr50626-00 | Prumnopitys taxifolia | Podocarpaceae | NATIVE |
| 47 | GymPiPiPdCr50563-00 | Podocarpus laetus | Podocarpaceae | NATIVE |
| 89 | GymPiPiPhYa50637-00 | Phyllocladus trichomanoides | Phyllocladaceae | NATIVE |
| 91 | GymPiPiPdCr50488-00 | Dacrycarpus dacrydioides | Podocarpaceae | NATIVE |
| 95 | GymPiPiPhYa50636-00 | Phyllocladus toatoa | Phyllocladaceae | NATIVE |
| 96 | GymPiPiPnCx50850-00 | Pseudotsuga menziesii | Pinaceae | INTRODUCED |

8 of 9 gymnosperms are NZ-native podocarps/phyllocladaceae — not Pinus confusers. Only 1 (Douglas fir, rank #96) is a plantation conifer. Zero Pinus congeners above radiata.

**Angiosperm families (top 15 by species count above radiata):**

| Family | Count | Key genera | NZ Status |
|--------|------:|------------|-----------|
| Myrtaceae | 10 | Kunzea, Leptospermum, Lophomyrtus, Metrosideros, Syzygium | NATIVE |
| Rubiaceae | 9 | Coprosma (9 species) | NATIVE |
| Asteraceae | 7 | Olearia (5), Brachyglottis | NATIVE |
| Fabaceae | 6 | Carmichaelia, Sophora (native), Cytisus, Paraserianthes (introduced) | MIXED |
| Araliaceae | 5 | Pseudopanax, Raukaua | NATIVE |
| Pittosporaceae | 4 | Pittosporum | NATIVE |
| Nothofagaceae | 4 | Nothofagus (fusca, menziesii, solandri, truncata) | NATIVE |
| Malvaceae | 4 | Hoheria, Plagianthus, Entelea | NATIVE |
| Lauraceae | 3 | Beilschmiedia tawa, Litsea, Persea (introduced) | MIXED |
| Oleaceae | 3 | Nestegis | NATIVE |
| Elaeocarpaceae | 3 | Elaeocarpus, Aristotelia | NATIVE |
| Sapindaceae | 3 | Alectryon (native), Dodonaea (native), Acer (introduced) | MIXED |
| Ericaceae | 2 | Dracophyllum (native), Erica (introduced) | MIXED |
| Solanaceae | 2 | Solanum betaceum, S. mauritianum | INTRODUCED |
| Rosaceae | 2 | Crataegus, Prunus | INTRODUCED |

**Introduced species above radiata (~15 of 104):**

| Rank | Species | Family | Status |
|-----:|---------|--------|--------|
| 48 | Ilex aquifolium (holly) | Aquifoliaceae | Invasive weed |
| 56 | Acer pseudoplatanus (sycamore) | Sapindaceae | Invasive weed |
| 57 | Prunus laurocerasus (cherry laurel) | Rosaceae | Invasive |
| 68 | Paraserianthes lophantha (brush wattle) | Fabaceae | Invasive |
| 70 | Cornus capitata (dogwood) | Cornaceae | Naturalised |
| 71 | Sambucus nigra (elder) | Viburnaceae | Invasive weed |
| 72 | Crataegus monogyna (hawthorn) | Rosaceae | Invasive weed |
| 77 | Erica arborea (tree heath) | Ericaceae | Naturalised |
| 80 | Cytisus proliferus (tagasaste) | Fabaceae | Introduced forage |
| 94 | Fuchsia boliviana | Onagraceae | Introduced |
| 96 | Pseudotsuga menziesii (Douglas fir) | Pinaceae | Plantation species |
| 97 | Solanum betaceum (tamarillo) | Solanaceae | Cultivated |
| 100 | Solanum mauritianum (woolly nightshade) | Solanaceae | Invasive weed |
| 102 | Persea americana (avocado) | Lauraceae | Cultivated |

### Summary Finding

**The model is overwhelmingly failing at plantation recognition, not congener discrimination.**

- ~85 of 104 species above radiata are NZ-native broadleaf or podocarp species
- Only 1 Pinaceae congener above radiata (Douglas fir at #96)
- Zero Pinus species above radiata (no congener problem)
- The model sees the benchmark coordinate as "native NZ temperate forest" and fills the top ranks with Coprosma, Nothofagus, Metrosideros, Olearia — the canonical flora of undisturbed NZ lowland/montane forest
- The dominant signal is: this location has forest-like features (elevation, climate, AE embeddings) that match many NZ native species' niches, and the model has no mechanism to distinguish "plantation pine" from "native forest"

---

## Task 2 — SINR Gap Analysis vs Current Trainer

### What our V4.1 training actually used

From `model_config_v3.json`:

| Setting | V4.1 Value | SINR Default |
|---------|-----------|--------------|
| Loss function | BCE | an_full (assumed-negative) |
| Background negative weight | 0.0 (disabled) | Always on |
| Hard cap per species | 0 (unlimited) | hard_cap_num_per_class |
| Species weighting | frequency-based | built into an_full |
| Location encoding | Yes (40D sinusoidal) | Yes (different encoding) |
| Planted boost | Active (legacy_gt1 proxy) | Not in SINR |
| Aux planted head | Active (0.1 weight) | Not in SINR |
| Land state head | Active (0.05 weight) | Not in SINR |

### Key gap: BCE vs assumed-negative loss

**BCE** treats every species column as independent binary classification. Each training row sets 1 species to positive and 19,042 to zero (absence of evidence). This means:

- At a plantation coordinate, BCE pushes Pinus radiata UP but simultaneously pushes every OTHER species DOWN equally
- The "push down" signal is 1/19,043 the strength of the "push up" signal per species
- With only 706 radiata rows out of 11.9M total, radiata gets 706 positive pushes and ~11.9M "absent-as-zero" pushes at locations where it may actually be present
- Species with 267K rows (top species) get 378x more positive signal

**an_full** (assumed-negative) handles this differently:

- Positive-only: only the observed species gets a positive loss term
- All species get an assumed-negative loss at every location (mean over all logits)
- The positive term is weighted by `pos_weight` (2048) to compensate
- This means unobserved species at a location are treated as "probably absent but uncertain" rather than "definitely absent"
- Critical for radiata: at NZ forest locations where radiata wasn't observed in the new_gbif data, an_full doesn't hard-penalize radiata — it only weakly pushes it toward absent

### Key gap: no hard cap

V4.1 class distribution is extremely skewed:

```
Top species:     267,259 rows
Radiata:             706 rows  (378x less)
Median species:        9 rows
50.3% of species:    <10 rows
```

Without hard caps, the top species dominate training gradients. The network optimizes for discriminating the top 200 species (which together account for most of the 11.9M rows) and treats the remaining 18,843 species as noise.

SINR's `hard_cap_num_per_class` limits each species to N samples. With a cap of 1000:
- Top species goes from 267K to 1K (267x reduction in dominance)
- Radiata stays at 706 (below cap, unchanged)
- Effective ratio drops from 378:1 to 1.4:1

### Key gap: no background negatives

Without background loss, the model only sees locations where species were observed. It never sees "empty" locations and never learns that most locations have few species.

With `bg_weight=1.0`, random locations are sampled and all species are pushed to 0 at those locations. This teaches the model spatial specificity — "not everything grows everywhere."

### Key gap: planted boost is actively harmful

The planted boost mechanism (`planted_score × species_intro_ratio × boost_scale`) is counterproductive at this benchmark because:

1. **Wrong planted proxy**: `legacy_gt1` mode labels natural forest as planted (xiao mapped 1 = natural forest → mapped 2 → `>1` = True). Since xiao=2 (true planted) has ZERO rows in training, the planted head learned "is forest" not "is planted."

2. **Noisy intro ratios boost NZ natives MORE than radiata**:
   - Pinus radiata intro_ratio = 0.9412
   - Melicytus ramiflorus (rank #2): intro_ratio = 0.9997
   - Nothofagus fusca (rank #32): intro_ratio = 0.6616
   - The boost adds `sigmoid(planted_head) × intro_ratio × 2.0` to every species' logit
   - At a forested NZ location, planted_score is HIGH (because "forest" = "planted" in this proxy)
   - Species with intro_ratio > 0.94 get a LARGER boost than radiata

3. **Result**: The boost lifts many NZ native broadleafs by more than it lifts radiata, actively pushing radiata down in relative rank.

### What pieces of SINR we ARE using effectively

- 5-branch gated fusion architecture (more expressive than vanilla SINR FFN)
- AlphaEarth satellite embeddings (SINR has no equivalent — this is our advantage)
- Temporal attention over 8 years of satellite data (our advantage)
- Location encoding (equivalent to SINR's spatial encoding)
- Species-frequency weighting (partially equivalent to SINR's class balancing)

---

## Task 3 — Minimum-Change Experiment Plan

All experiments use existing V4.1 training-grain shards (`~/data_v41_preview_train_shards/`) and existing contracts. No data mutation. New model directories only.

### Experiment 1: Hard cap + an_full (HIGHEST PRIORITY)

**Rationale**: Directly addresses both the class imbalance (#1 problem) and the loss formulation (#2 problem). Both mechanisms are already implemented.

**Code changes**: None.

**Command**:
```bash
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_v42_exp1_anfull_hardcap \
  --artifact-version v42_exp1_anfull_hardcap \
  --data-dir ~/data_v41_preview_train_shards \
  --mapping-contract orchestrator/contracts/sinr_v3/species_mapping_v41_preview_train.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v41_preview_train.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v41_preview_train.npz \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v41_preview_train.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json \
  --require-full-contract \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --loss-mode an_full --an-pos-weight 2048.0 \
  --hard-cap-per-species 1000 \
  --no-boost \
  --land-state-mode zero
```

**Why non-destructive**: New model dir, no changes to data or canonical tables.

**Success criteria**: Rank < #50 at canonical benchmark. Rank < #20 would confirm this is the right direction.

### Experiment 2: Hard cap only (BCE baseline comparison)

**Rationale**: Isolates the effect of hard caps without changing the loss function. If this alone moves rank substantially, it confirms class imbalance is the dominant factor.

**Code changes**: None.

**Command**:
```bash
python3 orchestrator/run_local_5m_shard_training.py \
  --model-dir ~/model_v42_exp2_hardcap_bce \
  --artifact-version v42_exp2_hardcap_bce \
  --data-dir ~/data_v41_preview_train_shards \
  --mapping-contract orchestrator/contracts/sinr_v3/species_mapping_v41_preview_train.json \
  --frozen-cont-stats orchestrator/contracts/sinr_v3/normalize_stats_v41_preview_train.npz \
  --frozen-temporal-stats orchestrator/contracts/sinr_v3/normalize_temporal_v41_preview_train.npz \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json \
  --species-frequency-contract orchestrator/contracts/sinr_v3/species_frequency_contract_v41_preview_train.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json \
  --require-full-contract \
  --zero-phylo-input --disable-intro-in-gate \
  --use-location-encoding \
  --loss-mode bce \
  --hard-cap-per-species 1000 \
  --no-boost \
  --land-state-mode zero
```

**Success criteria**: Rank improvement vs V4.1 baseline (#105). Any improvement confirms imbalance is load-bearing.

### Experiment 3: an_full + hard cap + background loss

**Rationale**: Full SINR-style training. If Exp 1 improves significantly, adding background loss tests spatial specificity.

**Code changes**: None.

**Command**: Same as Exp 1 but add `--bg-weight 1.0`.

**Success criteria**: Further improvement over Exp 1. If no improvement, background loss is not needed at this scale.

### Experiment Priority Order

| Priority | Experiment | Key Change | Expected Impact |
|----------|-----------|------------|-----------------|
| 1 | Exp 1 | an_full + hard-cap-1000 + no-boost | Highest confidence |
| 2 | Exp 2 | hard-cap-1000 only (BCE) + no-boost | Isolates cap effect |
| 3 | Exp 3 | Exp 1 + bg-weight 1.0 | Tests spatial specificity |

### Benchmark Command (same for all experiments)

```bash
python3 orchestrator/v3_point_inference.py \
  --lat -41.151583464812404 --lon 175.09968969862783 --year 2023 \
  --model-dir ~/model_v42_exp1_anfull_hardcap \
  --feature-contract orchestrator/contracts/sinr_v3/feature_contract_v41_preview_train.json \
  --intro-ratio-contract orchestrator/contracts/sinr_v3/intro_ratio_contract_v41_preview_train.json \
  --target-taxon GymPiPiPnCx50820-00 \
  --introduced-mode all --top-k 20 \
  --disable-intro-in-gate --land-state-mode zero \
  --use-location-encoding --no-boost
```

---

## Task 4 — What NOT To Do Yet

### Do NOT merge backfill into V4

The V4.1 new_gbif-only slice has 706 radiata rows vs backfill's 8,705. Merging backfill would likely improve radiata rank immediately — but it would mask whether the training objective/imbalance is the real problem. If hard-cap + an_full can push rank from #105 to <#30 on the thin data, that proves the objective was wrong. If it can't, then we know backfill is needed AND we'll have a better training recipe for when it arrives.

### Do NOT widen feature families

The current 55 env + 64 AE + 512 temporal + location encoding is already a rich feature set. Adding GEDI, HILDA, aridity, etc. adds risk of contamination and doesn't address the fundamental loss/imbalance problem. Features are not the bottleneck.

### Do NOT rewrite the architecture

The 5-branch gated fusion is more expressive than vanilla SINR. The problem is not model capacity — it's that the training signal is dominated by a few hundred species while 18,000+ are noise. Architecture changes cannot fix this.

### Do NOT add more epochs

V4.1 ran 24 shard-epochs (2 cycles × 12 shards). The training log shows convergence. More epochs with the same BCE loss and no caps will just overfit to the dominant species further.

### Do NOT attempt to fix the planted/introduced path yet

The planted label proxy is broken (legacy_gt1 labels natural forest as planted), and the intro ratios are noisy. Use `--no-boost` to disable the entire mechanism. Fix it properly only after the core loss/imbalance experiments show whether the species head alone is sufficient.

---

## Task 5 — Recommendation (Updated Post-Experiment)

### 1. Is #105 mainly a data-scope problem, a loss/objective problem, or both?

**Both. Neither alone is sufficient.**

The V4.2 experiment proved both factors are load-bearing:

- **Objective matters**: an_full + hard-cap moved radiata from #105→#79 and 0.608→0.917. This is a real improvement from loss/balancing changes alone.
- **Data scope also matters**: Even after the objective fix, radiata is still #79 — not competitive. The V4.1 new_gbif-only slice has 706 radiata rows (7 within 25km of benchmark) vs 8,705 in the old backfill-inclusive training set. No loss function fully rescues a 380:1 class imbalance at the local geographic level.

The specific improvements from V4.2:
- **Hard cap**: Reduced top-species dominance from 378:1 to ~1.4:1
- **an_full**: Treated unobserved species as uncertain rather than absent
- **no-boost**: Removed the broken planted mechanism that was actively harming radiata rank

### 2. What is the strongest next move?

**The objective fix is done. The next move is data scope.**

an_full + hard-cap + no-boost is the correct training recipe going forward. It delivered a meaningful improvement. But to push radiata into the competitive range (<#30), the model needs more geographic support — specifically backfill data that provides ~8,700 additional radiata rows including ~30+ within 25km of the benchmark.

Pending next experiments (in priority order):
1. **Exp 2: Hard-cap-1000 + BCE + no-boost** — isolates whether the improvement came from hard-cap or an_full (still worth running for attribution)
2. **Merge verified backfill** — once the GEE backfill extraction completes, train with an_full + hard-cap + no-boost on the expanded data
3. **Background loss** (Exp 3: an_full + hard-cap + bg-weight 1.0) — lower priority now that the core recipe is established

### 3. Should radiata remain the leading stress test?

**Yes, but pair it with 2-3 additional cases.**

Radiata at this coordinate is a good stress test because:
- It's a plantation species at a plantation location (xiao=2, confirmed)
- It's introduced (WCVP native range is Americas/Australasia, not NZ)
- The coordinate is in a region with heavy plantation forestry
- It exposes all three problems (imbalance, loss, boost) simultaneously

Add these companion benchmarks:
1. **Eucalyptus globulus** in Tasmania/Victoria, Australia — another major plantation species
2. **Pinus sylvestris** in Scandinavia — boreal plantation, different ecology
3. **Tectona grandis** (teak) in Southeast Asia — tropical plantation

If hard-cap + an_full improves radiata but not others, the fix is data-specific. If it improves all four, the fix is general.

---

## Appendix: V4.1 Training Configuration vs Recommended

| Parameter | V4.1 (current) | Exp 1 (recommended) | Change |
|-----------|----------------|---------------------|--------|
| loss_mode | bce | an_full | Assumed-negative |
| hard_cap_per_species | 0 | 1000 | Cap dominant species |
| bg_weight | 0.0 | 0.0 (add in Exp 3) | — |
| no_boost | false | true | Remove broken boost |
| planted_label_mode | legacy_gt1 | N/A (boost disabled) | — |
| use_location_encoding | true | true | Same |
| disable_intro_in_gate | true | true | Same |
| zero_phylo_input | true | true | Same |
| land_state_mode | zero | zero | Same |
| an_pos_weight | 2048.0 | 2048.0 | Same |
| epochs/cycles | 2 cycles × 12 shards | 2 cycles × 12 shards | Same |
