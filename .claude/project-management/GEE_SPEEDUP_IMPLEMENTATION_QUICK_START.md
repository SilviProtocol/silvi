# GEE Extraction Speedup — Quick Start Implementation

**TL;DR**: You're already using the right export method. Get 3-5x speedup by reducing computation, not changing infrastructure.

---

## Phase 1: This Week (Verify Baseline)

### Step 1: Check SINR Feature Contract (30 min)
```bash
cd /Users/djimoserodio/Documents/Treekipedia\ vibes/silvi-open

# Look at what features SINR v3 actually uses
grep -n "continuous_features\|feature_names\|input_shape" orchestrator/train_on_vm.py | head -20

# Query training data schema
bq query --nouse_legacy_sql --max_rows=1000 "SELECT * FROM \`treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_medium_5m_s0\` LIMIT 1" | head -100

# Count actual columns in training data
bq query --nouse_legacy_sql "SELECT STRING_AGG(column_name) FROM \`treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_medium_5m_s0\` INFORMATION_SCHEMA.COLUMNS"
```

**Decision**: If SINR only uses 70-100 of your 150+ sampled bands → proceed to Phase 2.

### Step 2: Profile a Single Batch (30 min)
```bash
cd orchestrator

# Create test script: profile_batch_timing.py
cat > profile_batch_timing.py << 'EOF'
#!/usr/bin/env python3
import ee
import pandas as pd
import time
from google.cloud import bigquery
import unified_gee_sampler_v3_strict as sampler

ee.Initialize(project='treekipedia-479918')
client = bigquery.Client(project='treekipedia-479918')

# Load 1 small batch (200 points only for fast testing)
df = client.query("""
    SELECT DISTINCT lat4dp, lon4dp, observation_year, emb_year
    FROM `treekipedia-479918.species_data.gbif_new_occurrences`
    WHERE observation_year IS NOT NULL
    LIMIT 200
""").to_dataframe()

batch = [{"lat": row.lat4dp, "lon": row.lon4dp} for row in df.itertuples()]
obs_year = int(df.observation_year.iloc[0])
emb_year = int(df.emb_year.iloc[0])

print(f"Profiling batch of {len(batch)} points...")
print(f"Obs year: {obs_year}, Emb year: {emb_year}")

start = time.time()
task = sampler.sample_batch(obs_year, emb_year, 0, batch, "test_profile_table", "test")
if task:
    print(f"Task submitted: {task.id}")
    # Poll until complete
    while True:
        time.sleep(30)
        status = task.status()
        state = status.get('state')
        print(f"  State: {state}")
        if state in ('COMPLETED', 'FAILED', 'CANCELLED'):
            elapsed = time.time() - start
            print(f"Task completed in {elapsed/60:.1f} minutes")
            print(f"Task result: {status}")
            break
EOF

python3 profile_batch_timing.py
```

**Expected output**:
- 200 points × 150 bands ≈ 30K values
- Estimated time: 1-2 minutes
- If 1-2 min: can try 5K batch
- If 3+ min: stick with 2K, focus on band reduction

---

## Phase 2: Next Week (Band Reduction)

### Step 3: Identify & Remove Unused Bands (1 hour)

Edit `orchestrator/unified_gee_sampler_v3.py`:

**Current `get_static_env_image()` function**:
- Lines 160-264
- Includes ~50 static bands

**Recommended cuts** (unless SINR proves they're needed):
```python
# CURRENT (expensive, remove):
# - WorldClim bio02-bio19 (except bio01 = annual mean temp)
#   Keep only: bio01 (annual mean temp)
# - All 7 soil bands: keep only soil_ph
# - Water seasonality, water recurrence: keep only water_occurrence
# - GEDI canopy height, foliage diversity: REMOVE (not in most SINR features)
# - Biomass AGB: REMOVE if not in SINR
# - Human modification: REMOVE if not core
# - Topographic diversity: REMOVE if not core

# KEEP ESSENTIALS:
# - DEM: elevation, slope, aspect (topo structure)
# - WorldClim: bio01 (temperature)
# - Soil: soil_ph (acidity)
# - Hansen: treecover2000, gain (forest baseline + regrowth)
# - JRC: forest type, TMF status (forest classification)
# - ESA WorldCover: LC type
# - SBTN: natural lands
# - Water: occurrence (hydrography)
# - MODIS: LC at obs/ae year (temporal LC)
# - TerraClimate: temporal VPD
# - Dynamic World: ongoing LC
# - Fire: frequency
# - Nighttime lights: human presence
```

**Implementation**:
```python
def get_static_env_image_REDUCED() -> ee.Image:
    """Reduced static env: 30 bands instead of 50+"""

    # DEM (4 bands)
    srtm = ee.Image('USGS/SRTMGL1_003')
    terrain = ee.Terrain.products(srtm)
    dem_stack = terrain.select(['elevation', 'slope', 'aspect', 'hillshade']).toFloat()

    # WorldClim - ONLY bio01 (temperature)
    bio = ee.Image('WORLDCLIM/V1/BIO')
    bio_band = bio.select('bio01')

    # Soil - ONLY soil_ph
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')

    # Hansen GFC
    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    hansen_stack = hansen.select(['treecover2000', 'gain'])

    # [... other essential bands ...]

    # Stack all (should be ~30 bands total vs 50+)
    combined = (dem_stack
        .addBands(bio_band)
        .addBands(soil_ph)
        .addBands(hansen_stack)
        # ... add only proven necessary bands
    )
    return combined.unmask(0)
```

**Testing**:
```bash
# Update unified_gee_sampler_v3_strict.py to use reduced version
# Re-run profile_batch_timing.py with reduced bands
# Expected: 50% faster (1 min vs 2 min for 200 points)
```

### Step 4: Measure Throughput Improvement (1 hour)
```bash
# Run actual extraction with reduced bands
python3 orchestrator/unified_gee_sampler_v3_strict.py --new-gbif --limit 10000 --pool-size 25

# Monitor progress
python3 orchestrator/monitor_strict_extraction.py

# Expected: 75K-100K points/hour (vs 50K baseline)
# Confirm: check rolling_rph metric
```

---

## Phase 3: Optional Experiments (Week 3)

### Step 5: Test Larger Batch Size (Advanced)
**Only if Phase 2 successful and throughput still < 100K pts/hr**

```bash
# Create: orchestrator/unified_gee_sampler_v3_strict_LARGE_BATCH.py
# Copy from unified_gee_sampler_v3_strict.py and modify:

# Line 34: DEFAULT_BATCH_SIZE = 5000  # Was 2000
# Line 37: TASK_TIMEOUT_MIN = 240      # Was 180 (allow more time for larger batch)

# Run test:
python3 orchestrator/unified_gee_sampler_v3_strict_LARGE_BATCH.py \
  --new-gbif --limit 25000 --pool-size 25

# Measure success rate:
# - If >95% batches succeed in <5min: try 10K batch
# - If 80-95% succeed: keep 5K
# - If <80% succeed: revert to 2K
```

---

## Phase 4: Deploy Optimized Version (Week 4)

### Step 6: Create Production-Ready Optimized Sampler

```bash
# Create: orchestrator/unified_gee_sampler_v3_strict_OPTIMIZED.py
# Incorporate:
# 1. Reduced bands (Phase 2)
# 2. Optimal batch size from experiments (Phase 3)
# 3. Keep same retry/pool logic
# 4. Update documentation

# Full extraction:
nohup caffeinate -s python3 orchestrator/unified_gee_sampler_v3_strict_OPTIMIZED.py \
  --all --pool-size 25 --resume-from-bq > orchestrator/strict_full_optimized_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Monitor:
watch -n 60 'python3 orchestrator/monitor_strict_extraction.py'
```

---

## Expected Timeline & Results

| Phase | Effort | Timeline | Expected Result |
|-------|--------|----------|-----------------|
| 1: Verify | 1 hour | This week | Baseline measurements |
| 2: Band reduction | 1 hour | Week 2 | 75K-100K pts/hr |
| 3: Batch experiments | 4 hours | Week 3 | Optional 150K pts/hr |
| 4: Production deploy | 1 hour | Week 4 | Continuous extraction |
| **Total 6.5M points** | | **1-2 days** | ✅ Complete |

---

## Monitoring During Extraction

```bash
# Create: monitor_loop.sh
#!/bin/bash
while true; do
  clear
  echo "=== SINR v3 Extraction Monitor ==="
  echo "Time: $(date)"
  python3 orchestrator/monitor_strict_extraction.py
  sleep 60
done

# Run in background
nohup bash monitor_loop.sh > orchestrator/monitor.log 2>&1 &

# Key metrics to watch:
# - rolling_rph: rolling rate (points/hour)
# - total_done: cumulative points sampled
# - ee_states: active task count
# - eta_hours: estimated time remaining
```

---

## Troubleshooting

### Issue: Tasks timing out at larger batch sizes
**Solution**: Revert batch size, increase timeout by 60 minutes, proceed with band reduction instead

### Issue: BigQuery append errors
**Solution**: This is rare but indicates task is writing malformed data
- Check error in task status
- May be related to NaN/null values in large batches
- Can work around by pre-filtering null values

### Issue: Memory exceeded in GEE
**Solution**: GEE task killed due to memory (only if batch size > 10K)
- Revert to working batch size
- No other fix without changing architecture

---

## Key Files to Update

1. **orchestrator/unified_gee_sampler_v3_strict.py** (lines 160-264)
   - Replace `get_static_env_image()` function

2. **orchestrator/unified_gee_sampler_v3_strict.py** (lines 33-34)
   - Update `DEFAULT_BATCH_SIZE` and `TASK_TIMEOUT_MIN` if applicable

3. **.claude/project-management/ACTIVE.md**
   - Update extraction status once complete

---

## When to Consider Stopping

- **If band reduction alone reaches 150K pts/hr**: Stop, you're done
- **If batch size experiments show diminishing returns**: Stick with band reduction approach
- **If hitting GEE quota errors**: You're at infrastructure limit; consider BigQuery-only alternatives

---

## References

- Full analysis: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/.claude/project-management/GEE_BATCH_EXPORT_VIABILITY_ANALYSIS.md`
- Current code: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator/unified_gee_sampler_v3_strict.py`
- GEE docs: https://developers.google.com/earth-engine/guides/exporting_to_bigquery

---

**Ready to start? Begin with Phase 1, Step 1 above.**
