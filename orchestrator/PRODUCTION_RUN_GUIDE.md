# AlphaEarth Extraction - Production Run Guide
**Last Updated**: October 27, 2025
**Status**: Ready for Production Deployment

---

## Quick Start (Safe to Leave Unattended)

```bash
# Navigate to orchestrator directory
cd "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/orchestrator"

# Run production version (can safely close laptop/disconnect)
python3 run_pilot_PRODUCTION.py

# If interrupted, just run it again - it will resume from checkpoint!
```

---

## Safety Features

### ✅ You CAN safely:
1. **Close your laptop** - Script will resume from checkpoint when you restart
2. **Ctrl+C to stop** - Progress is saved, resume anytime
3. **Let it run overnight** - Automatic retry handles transient failures
4. **Disconnect from internet briefly** - Will retry failed tasks up to 3 times
5. **Run multiple times** - Skips already-completed species

### ⚠️ You SHOULD NOT:
1. **Delete `checkpoints.json`** while running - This tracks all progress
2. **Run multiple instances simultaneously** - Could cause duplicate GEE tasks
3. **Delete BigQuery table mid-run** - Completed embeddings would be lost

---

## Production Features

### 1. Automatic Retry (Up to 3 Attempts)
```
Species fails → Waits 60s → Retries → If fails 3x → Marks as permanently failed
```

**Handles:**
- Network timeouts
- GEE quota errors (temporary)
- BigQuery connection issues
- Transient API failures

### 2. Checkpoint/Resume System
**File:** `checkpoints.json`

**Tracks:**
- ✅ Completed species (with timestamps)
- ❌ Failed species (with error messages)
- 🔄 Retry queue (species awaiting retry)
- ⏳ In-progress species (cleaned up on restart)

**Example checkpoint:**
```json
{
  "pilot_start": "2025-10-27T05:45:00",
  "completed": [
    {
      "taxon_id": "AngMaFaFbCx09400-00",
      "species": "Acacia pycnantha Benth.",
      "batch_id": "AngMaFaFbCx09400-00_20251027_054530",
      "n_occurrences": 100,
      "n_tasks": 1,
      "retry_count": 0,
      "completed_at": "2025-10-27T05:47:15"
    }
  ],
  "failed": [],
  "retry_queue": []
}
```

### 3. Progress Tracking with ETA
**Printed every 5 species:**
```
======================================================================
PROGRESS SUMMARY
======================================================================
✅ Completed: 15/100 (15.0%)
❌ Failed: 2/100
🔄 In retry queue: 1
⏳ Remaining: 82/100
⏱️  Elapsed: 1:23:45
🕐 ETA: 6:15:30
======================================================================
```

### 4. Graceful Interruption Handling
**Ctrl+C behavior:**
```
^C
⚠️  Interrupted by user! Saving checkpoint...
✅ Progress saved. You can resume by running this script again.
```

**Computer sleep/crash:**
- Checkpoint saved after each species completes
- On restart, stale "in_progress" entries moved to retry queue
- No data loss

---

## Expected Runtime

### Conservative Estimates (Sequential Processing)

**Per Species:**
- Small species (< 500 occurrences): ~2-3 minutes
- Medium species (500-2000 occurrences): ~3-5 minutes
- Large species (> 2000 occurrences): ~5-10 minutes

**Full 100-Species Pilot:**
- **Optimistic**: 3-4 hours (if most species are small)
- **Realistic**: 5-8 hours (mixed sizes, some retries)
- **Pessimistic**: 10-12 hours (many large species, multiple retries)

**Why the variance?**
1. GEE processing time varies by data complexity
2. Network conditions affect task submission/monitoring
3. Retry delays add 60s per failure
4. BigQuery export speed varies

### Parallel Optimization Potential
**Not implemented yet**, but could reduce runtime to 2-4 hours by:
- Submitting multiple species to GEE concurrently
- Monitoring all tasks in parallel
- Dynamic concurrency adjustment based on quota

---

## Monitoring Progress

### Check Status While Running

**Option 1: Watch checkpoint file**
```bash
# In a separate terminal
watch -n 10 'jq ".completed | length" checkpoints.json'

# Shows: 15 (updates every 10 seconds)
```

**Option 2: Check BigQuery directly**
```bash
# Count total embeddings extracted
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as total FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`'

# Count species with embeddings
bq query --use_legacy_sql=false \
  'SELECT COUNT(DISTINCT taxon_id) as species_count
   FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`'
```

**Option 3: Check GEE task status**
```bash
# List active GEE tasks
python3 -c "
import ee
ee.Initialize(project='treekipedia-476404')
tasks = ee.batch.Task.list()
print(f'Active tasks: {len([t for t in tasks[:50] if t.status()[\"state\"] in [\"READY\", \"RUNNING\"]])}')
"
```

---

## Handling Failures

### If Script Crashes

**Just restart it:**
```bash
python3 run_pilot_PRODUCTION.py
```

The script will:
1. Load checkpoint
2. Report current status
3. Clean up stale in-progress entries
4. Resume from where it left off

### If Too Many Species Fail

**Check error messages in checkpoint:**
```bash
jq '.failed' checkpoints.json
```

**Common failures and fixes:**

**1. BigQuery quota exceeded**
```json
{"last_error": "Quota exceeded: BigQueryInsertOperations"}
```
**Fix:** Wait 24 hours for quota reset, then resume

**2. GEE compute quota exceeded**
```json
{"last_error": "Too many concurrent operations"}
```
**Fix:** Reduce concurrent tasks (already handled by retry logic)

**3. Network timeout**
```json
{"last_error": "Connection timeout"}
```
**Fix:** Already retries automatically, check internet connection

**4. Empty FeatureCollection (shouldn't happen with .mosaic() fix)**
```json
{"last_error": "FeatureCollection is empty"}
```
**Fix:** Verify gee_sampler_FINAL.py is being used (not gee_sampler.py)

### Manually Retry Failed Species

**Extract failed taxon_ids:**
```bash
jq -r '.failed[].taxon_id' checkpoints.json > failed_species.txt
```

**Remove from failed list (to retry):**
```bash
# Edit checkpoints.json - move failed entries to retry_queue
# Then rerun script
```

---

## Post-Completion Verification

### 1. Check Completion Rate
```bash
# From checkpoint file
jq '{completed: (.completed | length), failed: (.failed | length)}' checkpoints.json
```

**Expected:** 95-100 species completed, 0-5 failed

### 2. Verify BigQuery Data Integrity
```bash
# Check for null embeddings (should be 0)
bq query --use_legacy_sql=false \
  'SELECT
     COUNT(*) as total_rows,
     COUNT(CASE WHEN A00 IS NULL THEN 1 END) as null_A00,
     COUNT(CASE WHEN A63 IS NULL THEN 1 END) as null_A63
   FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`'
```

**Expected:**
```
total_rows: ~95,000
null_A00: 0
null_A63: 0
```

### 3. Verify Temporal Coverage
```bash
# Check year distribution
bq query --use_legacy_sql=false \
  'SELECT emb_year, COUNT(*) as count
   FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`
   GROUP BY emb_year
   ORDER BY emb_year'
```

**Expected:** All years 2017-2024 represented

### 4. Verify Species Coverage
```bash
# Check species counts
bq query --use_legacy_sql=false \
  'SELECT taxon_id, COUNT(*) as occurrence_count
   FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`
   GROUP BY taxon_id
   ORDER BY occurrence_count DESC
   LIMIT 10'
```

**Expected:** Castanea sativa should have ~5000 rows (sampled from 69,651 total)

---

## Troubleshooting

### Issue: "GEE quota exceeded"
**Symptoms:** Many failures with "Quota exceeded" error

**Solutions:**
1. Check current quota usage:
   ```bash
   # Go to: https://code.earthengine.google.com/
   # Check: Assets → Quota tab
   ```
2. Wait for quota reset (daily at midnight Pacific Time)
3. Resume script after reset

### Issue: "BigQuery table already exists"
**Symptoms:** First task fails with table exists error

**Solution:** This is expected! The table was created during testing. Script uses WRITE_APPEND mode automatically.

If truly stuck, delete and recreate:
```bash
bq rm -f treekipedia-476404:alphaearth.occ_embeddings_raw
# Then restart script
```

### Issue: Script hangs during "Waiting for GEE tasks"
**Symptoms:** No progress for > 5 minutes during task monitoring

**Likely causes:**
1. GEE task is actually still processing (large species can take 5-10 minutes)
2. Network connection lost

**Solutions:**
1. Wait - check GEE console: https://code.earthengine.google.com/tasks
2. If task is FAILED in console, Ctrl+C and restart (will retry)
3. If network lost, Ctrl+C and restart when reconnected

### Issue: Checkpoint file corrupted
**Symptoms:** Script crashes with JSON parse error

**Solution:**
```bash
# Backup corrupt checkpoint
cp checkpoints.json checkpoints.json.backup

# Check what's extractable
jq '.' checkpoints.json

# If totally broken, check BigQuery for completed species
bq query --use_legacy_sql=false \
  'SELECT DISTINCT taxon_id FROM `treekipedia-476404.alphaearth.occ_embeddings_raw`' \
  > completed_species.txt

# Manually reconstruct checkpoint (worst case)
```

---

## Optimization Tips

### 1. Run During Off-Peak Hours
GEE quota is shared across all users. Best times:
- **US West Coast**: 10 PM - 6 AM Pacific
- **Europe**: 2 AM - 10 AM CET
- **Asia**: 6 AM - 2 PM JST

### 2. Monitor BigQuery Storage Costs
**Current pilot:** ~30GB total (free tier covers this)

**To check usage:**
```bash
bq ls --format=pretty treekipedia-476404:alphaearth
```

### 3. Clean Up Test Data (Optional)
```bash
# Remove test embeddings from previous runs
bq query --use_legacy_sql=false \
  "DELETE FROM \`treekipedia-476404.alphaearth.occ_embeddings_raw\`
   WHERE taxon_id = 'TEST-FINAL'"
```

---

## Next Steps After Completion

### 1. Implement K-Prototypes Clustering
**Script:** `cluster_prototypes.py` (to be created)

**Process:**
1. Query BigQuery for each species
2. Run k-means clustering (k=1-5 based on sample size)
3. Compute spherical statistics (r, q10/q50/q90)
4. Store centroids in PostgreSQL

### 2. Validate Prototypes
**Questions to answer:**
- Do prototypes capture species niche?
- Are spherical variances reasonable?
- Do similar species have similar prototypes?

### 3. Integrate with Treekipedia API
**New endpoint:** `/api/species/:taxon_id/alphaearth-prototypes`

**Returns:**
```json
{
  "taxon_id": "AngMaFaFbCx09400-00",
  "n_prototypes": 3,
  "prototypes": [
    {
      "centroid_64d": [0.12, -0.05, ...],
      "count": 45,
      "spherical_r": 0.82,
      "q10_radius": 0.05,
      "q50_radius": 0.12,
      "q90_radius": 0.24
    }
  ]
}
```

---

## File References

**Production script:** [run_pilot_PRODUCTION.py](run_pilot_PRODUCTION.py)
**GEE sampler:** [gee_sampler_FINAL.py](gee_sampler_FINAL.py)
**GBIF data:** [gbif_data/gbif_occurrences_top100_gps.parquet](gbif_data/gbif_occurrences_top100_gps.parquet)
**Checkpoints:** `checkpoints.json` (created on first run)
**Status doc:** [ALPHAEARTH_EXTRACTION_STATUS.md](ALPHAEARTH_EXTRACTION_STATUS.md)

---

## Emergency Contacts & Resources

**GEE Console:** https://code.earthengine.google.com/
**BigQuery Console:** https://console.cloud.google.com/bigquery?project=treekipedia-476404
**GEE Quota Docs:** https://developers.google.com/earth-engine/guides/usage
**AlphaEarth Paper:** https://arxiv.org/abs/2501.15127

---

**Document Created**: October 27, 2025
**For Questions**: Check [ALPHAEARTH_EXTRACTION_STATUS.md](ALPHAEARTH_EXTRACTION_STATUS.md) or [CLAUDE.md](../.claude/CLAUDE.md)
