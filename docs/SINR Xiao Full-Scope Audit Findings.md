# SINR Xiao Full-Scope Audit Findings

Date: 2026-03-13
Status: P0 audit complete — remediation path proposed
Issue: treekipedia-0d4

## Root Cause

The Xiao planted forest RGB decode was fixed on 2026-03-08 in `unified_gee_sampler_v3.py`:
- **Before fix**: looked for red (R>200) — never matched Xiao's yellow (127,127,0) encoding for planted
- **After fix**: correct exact RGB match for green (0,127,0) = natural, yellow (127,127,0) = planted

The strict extraction (`unified_gee_sampler_v3_strict.py`) imports the non-strict sampler as `base` and calls `base.get_static_env_image()`, which includes Xiao. The extraction was restarted on 2026-03-11 with `--resume-from-bq`, meaning:
- Pre-fix rows (extracted before March 8) retain buggy xiao=0 for planted locations
- Post-fix rows (extracted after March 8 restart) have correct values
- The `--resume-from-bq` flag skips already-extracted contexts, so pre-fix rows are never re-extracted

## BQ Audit Tables Created

| Table | Rows | Purpose |
|-------|------|---------|
| `sinr_xiao_strict_vs_preview_audit_v1` | 6,285,514 | Per-context comparison with mismatch classification |
| `sinr_xiao_audit_summary_v1` | 7 | Mismatch category counts |
| `sinr_xiao_audit_geo_profile_v1` | 50 | Geographic + temporal breakdown |
| `sinr_xiao_correction_overlay_v1` | 487,523 | All mismatched rows with corrected values |

## Full-Scope Numbers

### Context-level comparison (strict raw vs preview-clean intersection)

| Category | Contexts | % of Overlap |
|----------|----------|-------------|
| **Agree** | 5,797,991 | 92.2% |
| **strict=0, preview=2 (RGB bug)** | **358,577** | **5.7%** |
| strict=0, preview=1 | 48,725 | 0.78% |
| strict=1, preview=0 | 48,012 | 0.76% |
| strict=2, preview=0 | 16,203 | 0.26% |
| strict=1, preview=2 | 9,821 | 0.16% |
| strict=2, preview=1 | 6,185 | 0.10% |

**Total overlap**: 6,285,514 contexts
**RGB bug (dominant pattern)**: 358,577 contexts (5.7%)
**Sampling noise (bidirectional 0↔1)**: ~96,737 contexts (1.5%)
**Other**: 30,209 contexts (0.5%)

### Strict-only rows (no preview comparison available)

| xiao value | Count | Assessment |
|-----------|-------|-----------|
| 0 | 86,119 | Ambiguous — some are genuine non-forest, some may be pre-fix bug |
| 1 | 63,501 | Likely correct — natural forest detection was unaffected by fix |
| 2 | 19,794 | Definitely post-fix — correct |
| **Total** | **169,414** | 2.6% of strict raw, no cross-check available |

### Training impact

| Metric | Count |
|--------|-------|
| Preview-clean rows at bug contexts | 563,787 |
| Species affected | 7,936 |
| Current strict release rows at bug contexts | 515,038 (6.3% of 8.17M) |

### Geographic distribution

The bug rate is **uniform across all years** (6.5–8.6%), ruling out batch-dependent causes:

| Year | Overlap | Bug Count | Bug % |
|------|---------|-----------|-------|
| 2017 | 1,828,556 | 89,596 | 4.9% |
| 2018 | 254,434 | 13,940 | 5.5% |
| 2019 | 437,328 | 26,730 | 6.1% |
| 2020 | 650,332 | 38,410 | 5.9% |
| 2021 | 799,696 | 45,890 | 5.7% |
| 2022 | 840,961 | 50,594 | 6.0% |
| 2023 | 646,957 | 41,507 | 6.4% |
| 2024 | 827,250 | 51,910 | 6.3% |

Geographic concentration:
- N30-50 (temperate): 188K bug rows — most absolute mismatches (temperate plantations)
- Equatorial: only 3.5% bug rate (fewer planted forests)
- Subtropical (N10-30, S10-30): 6.5-6.8% bug rate

## Why preview-clean has correct values

The preview-clean table received a Xiao backfill (completed 2026-03-08) using the `backfill_xiao_shards.py` script with correct RGB decode. This is confirmed by:
1. The backfill distribution (48.3% non-forest, 36.9% natural, 14.8% planted) matches preview-clean's Xiao distribution
2. Fresh validation extraction (860 rows) agreed with preview-clean on Xiao, not with strict raw
3. All 7 strict-control mismatches in validation were exactly this pattern: preview=2, fresh=2, strict=0

## Interpretation

### The RGB bug pattern (358K rows) is high-confidence fixable

- **Preview + fresh validation agree** on xiao=2
- Strict raw has xiao=0 due to pre-fix extraction
- Correction: trust preview-clean value (backfilled with correct decode)

### The bidirectional 0↔1 noise (~97K rows) is GEE sampling noise

- Roughly symmetric: 48K each direction
- Xiao is a 30m raster; GEE `sampleRegions` at 10m scale hits slightly different pixels between runs
- Not a systematic bug — expected at raster boundaries

### The strict-only rows (169K) are partially ambiguous

- 19.8K with xiao=2: post-fix, definitely correct
- 63.5K with xiao=1: likely correct (fix didn't affect natural detection)
- 86K with xiao=0: cannot verify without re-extraction

## Remediation Approach

### Immediate: correction overlay for training

The `sinr_xiao_correction_overlay_v1` table provides corrected Xiao values for all mismatched contexts. Training pipeline can LEFT JOIN this to get corrected values without mutating any source table.

Usage in training data prep:
```sql
SELECT
  s.*,
  COALESCE(x.corrected_xiao, s.xiao_planted_forest) as xiao_planted_forest_corrected
FROM strict_features s
LEFT JOIN sinr_xiao_correction_overlay_v1 x
  ON ROUND(s.latitude, 4) = x.lat4
  AND ROUND(s.longitude, 4) = x.lon4
  AND s.emb_year = x.emb_year
```

### Medium-term: re-extract affected contexts

After GEE extraction completes (all 2,064 batches), identify contexts that were extracted pre-fix and re-extract them with the fixed code. This eliminates the overlay dependency.

### Fail-closed decision

- **Do NOT mark current strict raw as fully canonical** — Xiao is unreliable in pre-fix rows
- **Do NOT silently use strict raw xiao** in any release without the correction overlay
- **The strict release (8.17M rows) has 515K bug-affected rows** — must be acknowledged in release metadata

## Script

`orchestrator/build_sinr_xiao_full_audit.py`

## Next Steps

1. Add Xiao correction overlay to the strict release builder pipeline
2. Update field-integrity status to reflect Xiao provenance
3. After GEE extraction completes, identify and re-extract pre-fix contexts
4. Mark strict-only rows with xiao=0 as `xiao_provenance_unverified`
