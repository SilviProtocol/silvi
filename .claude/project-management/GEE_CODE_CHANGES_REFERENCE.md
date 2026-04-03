# GEE Extraction Code Changes — Technical Reference

**Purpose**: Specific file paths and code modifications needed to implement speedup recommendations

**Files Modified**:
- `orchestrator/unified_gee_sampler_v3.py` (base module — used by v3_strict)
- `orchestrator/unified_gee_sampler_v3_strict.py` (production sampler)

---

## File 1: orchestrator/unified_gee_sampler_v3.py

### Location: Lines 160-264 — get_static_env_image() Function

**Current Status**: Samples ~50 static environmental bands

**Change Type**: Reduce to ~25-30 essential bands (50% reduction)

### Specific Lines to Modify

```python
# CURRENT FUNCTION (Lines 160-264)
def get_static_env_image() -> ee.Image:
    """All static (year-independent) environmental features."""

    # WorldClim BIO variables (19 bands) — REDUCE TO 1
    bio = ee.Image('WORLDCLIM/V1/BIO')
    bio_bands = bio.select([f'bio{i:02d}' for i in range(1, 20)])  # ← REMOVE THIS
    # REPLACE WITH:
    bio_bands = bio.select('bio01')  # Only annual mean temperature

    # Soil layers (7 bands) — REDUCE TO 1
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')
    soil_clay = ee.Image(...)  # ← REMOVE
    soil_sand = ee.Image(...)  # ← REMOVE
    soil_oc = ee.Image(...)    # ← REMOVE
    soil_tex = ee.Image(...)   # ← REMOVE
    soil_bd = ee.Image(...)    # ← REMOVE
    soil_wc = ee.Image(...)    # ← REMOVE
    # REPLACE WITH ONLY:
    soil_ph = ee.Image('OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02').select('b0').rename('soil_ph')

    # Water layers (3 bands) — REDUCE TO 1
    water_stack = jrc_water.select(['occurrence', 'recurrence', 'seasonality'], [...])  # ← REMOVE
    # REPLACE WITH:
    water_stack = jrc_water.select('occurrence').rename('water_occurrence')

    # GEDI layers (2 bands) — REMOVE (REMOVE ENTIRELY UNLESS IN SINR)
    gedi = ee.ImageCollection('LARSE/GEDI/GRIDDEDVEG_002/V1/1KM').mosaic()
    gedi_stack = gedi.select(['p95', 'shan'], [...])  # ← REMOVE ENTIRE GEDI BLOCK

    # Biomass (1 band) — REMOVE (REMOVE ENTIRELY UNLESS IN SINR)
    biomass = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic()
    biomass_band = biomass.select('agb').rename('biomass_agb_mgha')  # ← REMOVE ENTIRE BIOMASS BLOCK

    # Human modification (1 band) — REMOVE (REMOVE ENTIRELY UNLESS IN SINR)
    hm = ee.ImageCollection('CSP/HM/GlobalHumanModification').mosaic()
    hm_band = hm.select('gHM').rename('human_modification')  # ← REMOVE ENTIRE HM BLOCK

    # Topo diversity (1 band) — REMOVE (REMOVE ENTIRELY UNLESS IN SINR)
    topo = ee.Image('CSP/ERGo/1_0/Global/SRTM_topoDiversity').select('constant').rename('topo_diversity')
    # ← REMOVE ENTIRE TOPO BLOCK

    # Stack everything — SIMPLIFIED
    combined = (bio_bands                    # 1 band (was 19)
        .addBands(soil_ph)                   # 1 band (was 7)
        .addBands(hansen_stack)              # 3 bands (unchanged)
        .addBands(jrc_type)                  # 1 band (unchanged)
        .addBands(jrc_tmf_status)            # 1 band (unchanged)
        .addBands(jrc_degrad_yr)             # 1 band (unchanged)
        .addBands(esa_wc_band)               # 1 band (unchanged)
        .addBands(sbtn)                      # 1 band (unchanged)
        .addBands(water_stack)               # 1 band (was 3)
        .addBands(merit_stack)               # 2 bands (unchanged)
        # REMOVED: gedi_stack, biomass_band, hm_band, topo
        .addBands(eco_id)                    # 1 band (unchanged)
        .addBands(biome_num)                 # 1 band (unchanged)
        .addBands(xiao_band)                 # 1 band (unchanged)
        .addBands(neumann_band)              # 1 band (unchanged)
    )

    return combined.unmask(0)
```

**Total band count after reduction**: 16 bands (was ~50)

---

## File 2: orchestrator/unified_gee_sampler_v3_strict.py

### Change Type 1: Use Reduced Static Env (Lines 260-267)

```python
# CURRENT (Line 261)
static_env = base.get_static_env_image()

# CHANGE TO:
static_env = base.get_static_env_image_reduced()  # New function with 50% fewer bands
```

**Note**: Must define `get_static_env_image_reduced()` in `unified_gee_sampler_v3.py` OR inline the reduced version here.

### Change Type 2: Optional — Increase Batch Size (Line 33)

```python
# CURRENT
DEFAULT_BATCH_SIZE = 2000

# OPTION A (Safe): No change, keep 2K
# OPTION B (Test): Change to 5K for testing
# OPTION C (Aggressive): Change to 10K if 5K proves stable

DEFAULT_BATCH_SIZE = 5000  # Requires testing first
```

### Change Type 3: Optional — Increase Task Timeout (Line 37)

**Only if increasing batch size above 2K**:

```python
# CURRENT
TASK_TIMEOUT_MIN = 180

# IF BATCH SIZE 5K:
TASK_TIMEOUT_MIN = 240  # Add 60 minutes (larger batches take longer)

# IF BATCH SIZE 10K:
TASK_TIMEOUT_MIN = 300  # Add another 60 minutes
```

---

## Implementation Checklist

### Phase 1: Band Reduction (Low Risk)

- [ ] Review unified_gee_sampler_v3.py lines 160-264
- [ ] Create `get_static_env_image_reduced()` function OR copy reduced version to unified_gee_sampler_v3_strict.py
- [ ] Verify SINR doesn't use removed bands (check training data schema)
- [ ] Test with --limit 2000 (1 batch of 2K points)
- [ ] Verify bands are reduced in BigQuery table (SELECT * LIMIT 1, count columns)
- [ ] Run --limit 100000 test and measure throughput (expect 75K+ pts/hr)
- [ ] If successful, update production call to use reduced version

### Phase 2: Batch Size Testing (Medium Risk)

**Only proceed if Phase 1 successful**

- [ ] Create backup: cp unified_gee_sampler_v3_strict.py unified_gee_sampler_v3_strict_BACKUP.py
- [ ] Create test variant: cp unified_gee_sampler_v3_strict.py unified_gee_sampler_v3_strict_5K_TEST.py
- [ ] Modify test variant:
  - [ ] DEFAULT_BATCH_SIZE = 5000
  - [ ] TASK_TIMEOUT_MIN = 240
  - [ ] Append "_5K_TEST" to output table name
- [ ] Run --limit 50000 test (10 batches of 5K)
- [ ] Measure success rate (expect >95%)
- [ ] Measure avg task time (expect 4-6 minutes)
- [ ] Calculate throughput (expect 120K+ pts/hr if linear)
- [ ] If successful, test with 10K batch if throughput < 150K pts/hr
- [ ] Finalize batch size based on results

### Phase 3: Production Deployment

- [ ] Merge optimal settings into production unified_gee_sampler_v3_strict.py
- [ ] Update --resume-from-bq to account for any output table renames
- [ ] Run full extraction with monitor_strict_extraction.py
- [ ] Document final throughput and time to completion
- [ ] Update ACTIVE.md with completion status

---

## Testing Scripts

### Script 1: Feature Count Verification

```bash
# After modifying get_static_env_image(), verify band count

# In orchestrator/test_band_count.py:
import ee
import unified_gee_sampler_v3 as sampler

ee.Initialize(project='treekipedia-479918')
static = sampler.get_static_env_image_reduced()
print(f"Band names: {static.bandNames().getInfo()}")
print(f"Total bands: {len(static.bandNames().getInfo())}")

# Expected: 25-30 bands (vs 50+ original)
```

### Script 2: Batch Performance Profiler

```bash
# In orchestrator/profile_batch.py (see GEE_SPEEDUP_IMPLEMENTATION_QUICK_START.md for full code)
# Submits single batch and times it
# Run with different batch sizes:
# - python3 profile_batch.py --batch-size 2000
# - python3 profile_batch.py --batch-size 5000
# - python3 profile_batch.py --batch-size 10000
```

### Script 3: Throughput Calculator

```bash
# After batch completes, calculate rate
python3 orchestrator/monitor_strict_extraction.py | grep "rolling_rph\|eta_hours"

# rolling_rph: points per hour
# eta_hours: estimated hours remaining
```

---

## Validation Queries

### Query 1: Verify Reduced Bands in Output

```sql
-- Run after first batch with reduced bands
SELECT COUNT(*) as row_count, ARRAY_LENGTH(ARRAY_KEYS(CAST(t AS JSON))) as property_count
FROM `treekipedia-479918.species_data.sinr_v3_features_new_gbif_strict_full` t
LIMIT 1

-- Expected: property_count = 160-180 (was 200+)
```

### Query 2: Verify Feature Contract

```sql
-- Check which columns SINR training actually uses
SELECT column_name
FROM `treekipedia-479918.species_data.sinr_v3_unified_strict_train_v30_medium_5m_s0`.INFORMATION_SCHEMA.COLUMNS
WHERE column_name LIKE '%bio%' OR column_name LIKE '%soil%' OR column_name LIKE '%gedi%'
ORDER BY column_name

-- Decisions:
-- - If bio02-bio19 unused: remove them
-- - If soil_clay/sand/etc unused: remove them
-- - If gedi/biomass unused: remove them
```

---

## Rollback Plan

If band reduction or batch size increase causes issues:

```bash
# Immediately revert:
cp orchestrator/unified_gee_sampler_v3_strict_BACKUP.py orchestrator/unified_gee_sampler_v3_strict.py

# Kill running process:
lsof -ti:5002 | xargs kill -9

# Restart with original config:
python3 orchestrator/unified_gee_sampler_v3_strict.py --all --pool-size 25 --resume-from-bq

# Query unsampleable table to see what failed:
# (These will be skipped on resume)
```

---

## Success Metrics

| Metric | Current | Target | Threshold |
|--------|---------|--------|-----------|
| Throughput (pts/hr) | 50K | 100K+ | >75K |
| Avg task time (min) | 2.5 | 1.25 | <2.0 |
| Batch success rate | ~99% | >95% | ≥90% |
| 6.5M completion time | 5.5 days | 1-2 days | ≤2 days |

---

## File Location Summary

```
orchestrator/
├── unified_gee_sampler_v3.py
│   └── get_static_env_image() [Line 160-264] ← MODIFY
│   └── get_static_env_image_reduced() [NEW] ← ADD
├── unified_gee_sampler_v3_strict.py
│   └── sample_batch() [Line 245-287] ← Reference static_env call
│   └── DEFAULT_BATCH_SIZE [Line 33] ← Optional change
│   └── TASK_TIMEOUT_MIN [Line 37] ← Optional change
├── monitor_strict_extraction.py
│   └── Use for monitoring (NO CHANGES)
└── [tests]
    ├── test_band_count.py ← CREATE
    └── profile_batch.py ← CREATE (or use existing)
```

---

## Timeline Reference

- **Phase 1 (Band Reduction)**: 2-3 hours work + 2 hours testing = same day deployment
- **Phase 2 (Batch Testing)**: 4 hours setup + 24-48 hours execution = week 2-3
- **Phase 3 (Deploy)**: 1 hour + 1-2 days extraction = completion by day 14

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Removed band used by SINR | Verify feature usage before removing |
| Large batch hits memory limit | Test with 5K first, add safeguards |
| Task timeout exceeded | Increase TASK_TIMEOUT_MIN proportionally |
| BigQuery table corruption | Always append to new table, not overwrite |
| Pool quota exceeded | Don't change pool size (at 25-task limit) |

---

**Status**: Ready for implementation
**Last Updated**: March 9, 2026
