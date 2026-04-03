# Hybrid Override System Audit - Complete Report Index

**Audit Date**: March 12, 2026  
**Status**: COMPLETE - All systems approved for operational use  
**Scope**: BigQuery hybrid override tables (3 tables, 24.5M+ occurrences)

---

## Report Files

### 1. AUDIT_SUMMARY.txt (Quick Reference)
**Location**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/AUDIT_SUMMARY.txt`  
**Size**: 7.5 KB (183 lines)  
**Best For**: Executive overview, quick status checks, key metrics at a glance

**Contains**:
- Table metadata summary
- Release gate distribution (verified exact counts)
- Data integrity checks
- Failure root cause analysis
- System state summary
- Confirmed expectations
- Notable observations
- Recommendations (immediate/short/long term)
- Status and sign-off

---

### 2. HYBRID_OVERRIDE_AUDIT_REPORT.md (Comprehensive Report)
**Location**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/HYBRID_OVERRIDE_AUDIT_REPORT.md`  
**Size**: 12 KB (323 lines)  
**Best For**: Detailed analysis, stakeholder documentation, detailed findings

**Contains**:
- Executive summary with key findings
- Complete table metadata (schema + metadata for each table)
- Release gate distribution with validation results
- Detailed data integrity checks (registry, queue, field completeness, leakage)
- Failure root cause analysis
- Field integrity reconciliation
- System overview and statistics
- Audit findings summary (confirmed expectations and notable observations)
- Recommendations (organized by priority)
- Comprehensive conclusion
- Appendix with query verification results

---

### 3. AUDIT_QUERY_RESULTS.txt (Technical Deep Dive)
**Location**: `/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/AUDIT_QUERY_RESULTS.txt`  
**Size**: 15 KB (371 lines)  
**Best For**: Technical validation, query reproducibility, detailed evidence

**Contains**:
- All 17 queries executed with full results
- Query 1-3: Table metadata for all three tables
- Query 4-5: Release gate distribution verification
- Query 6-8: Override registry and queue analysis
- Query 9-10: Cross-validation and leakage detection
- Query 11-13: Quality flag analysis and failure patterns
- Query 14-17: Field completeness, system statistics, summary
- Complete schema documentation
- Evidence for every finding

---

## Key Findings Summary

### Table Metadata
| Table | Rows | Columns | Size | Status |
|-------|------|---------|------|--------|
| sinr_hybrid_override_registry_v1 | 0 | 12 | 0 B | Empty (expected) |
| sinr_hybrid_override_candidate_queue_v1 | 13,428,663 | 26 | 4.8 GB | Fully populated |
| sinr_occurrence_release_eligibility_v1 | 24,483,023 | 77 | 12.6 GB | Master table |

### Release Gate Breakdown (24,483,023 Total)
- **allow_hybrid_release**: 0 (0.00%) - None approved yet
- **allow_strict_release**: 8,579,371 (35.04%) - Production ready
- **block_pending_audit_override**: 13,428,663 (54.85%) - In candidate queue
- **block**: 2,474,989 (10.11%) - Permanently blocked

### Critical Finding: Monolithic Failure Pattern
All 13,428,663 candidate rows fail the **exact same three serve-time requirements**:
1. `land_state_serve_parity_ok = FALSE` (100%)
2. `carbon_family_serve_ok = FALSE` (100%)
3. `hilda_family_serve_ok = FALSE` (100%)

All failures are coterminous with single context class: `legacy_safe_candidate`

### Data Integrity Status
- ✓ Override registry perfectly empty (0 rows)
- ✓ Candidate queue perfectly synchronized with eligibility (100% match)
- ✓ Zero data leakage (no orphaned approved records)
- ✓ All critical fields 100% populated
- ✓ No NULL values in core identifiers

---

## Audit Checklist

### Metadata Verification
- [x] sinr_hybrid_override_registry_v1 - Row count, columns, schema
- [x] sinr_hybrid_override_candidate_queue_v1 - Row count, columns, schema
- [x] sinr_occurrence_release_eligibility_v1 - Row count, columns, schema

### Release Eligibility Breakdown
- [x] allow_hybrid_release = 0 (confirmed)
- [x] allow_strict_release = 8,579,371 (confirmed)
- [x] block_pending_audit_override = 13,428,663 (confirmed)
- [x] block = 2,474,989 (confirmed)

### Data Quality Checks
- [x] Override registry is truly empty (0 rows)
- [x] Candidate queue includes ONLY block_pending_audit_override rows
- [x] 100% synchronization between queue and eligibility table
- [x] All critical fields populated (0 NULLs)
- [x] No data leakage (no unapproved allow_hybrid_release rows)

### Cross-Validation
- [x] Candidate queue = release eligibility block_pending rows (13.4M matches exactly)
- [x] No discrepancies in field completeness
- [x] Field integrity table synced (24.5M rows each)

### Failure Analysis
- [x] Quality flag distribution analyzed
- [x] Root cause identified: serve-time feature unavailability
- [x] Monolithic pattern confirmed (all 3 failures together)
- [x] Context classification verified (single legacy_safe_candidate class)

---

## Recommendations by Priority

### Immediate (No Action Required)
System is fully operational. No structural changes needed.

### Short Term (1-2 Weeks)
1. Consider batch override workflow for 13.4M legacy_safe_candidate rows
2. Investigate root cause of serve-time feature unavailability
3. Document explicit override decision criteria

### Long Term (1+ Months)
1. Implement serve-time feature validation in pipeline
2. Add monitoring and alerting for candidate queue
3. Establish SLA for override review timeline

---

## Technical Details Reference

### Serve-Time Failures (13.4M candidates)
- **land_state_serve_parity_ok = FALSE**: Land state features have parity issues
- **carbon_family_serve_ok = FALSE**: Carbon family completely unavailable at serve time
- **hilda_family_serve_ok = FALSE**: HILDA family completely unavailable at serve time

### Context Classification
- **legacy_safe_candidate**: 13,428,663 rows (100% of candidates)
  - All pass strict training validation
  - All fail serve-time feature requirements
  - Suitable for standardized batch override

### Temporal Coverage
- All 24.5M occurrence records have observation_year data (100%)
- Data from 2 distinct sources
- 45,903 unique species

---

## How to Use These Reports

**For Quick Status Check**:
→ Read AUDIT_SUMMARY.txt (7.5 KB, 5 min read)

**For Stakeholder Communication**:
→ Use HYBRID_OVERRIDE_AUDIT_REPORT.md (12 KB, detailed but digestible)

**For Technical Verification**:
→ Reference AUDIT_QUERY_RESULTS.txt (15 KB, all queries with results)

**For Implementation Details**:
→ Consult all three documents together for complete picture

---

## Sign-Off

**Audit Status**: ✓ COMPLETE

**System Status**: ✓ APPROVED FOR OPERATIONAL USE

**Key Assertion**: The hybrid override system is fully initialized, structurally sound, internally consistent, and ready for production override workflow use.

**No Blocking Issues Identified**

---

**Report Generated**: March 12, 2026  
**Audit Tool**: Python (google.cloud.bigquery)  
**Project**: Treekipedia SINR v3  
**BigQuery**: treekipedia-479918 / species_data  
**Execution Time**: ~5 minutes  
**Queries**: 17+ executed and verified
