# Treekipedia Database Migration Guide

**Last Updated**: January 2026
**Target**: Production deployment of research versioning and atomic insights architecture

---

## Overview

This guide covers deploying migrations 07 and 08, which add:
- Research versioning and tracking columns to the `species` table
- Atomic `insights` table for FAIR-compliant knowledge storage
- Aggregation functions that sync insights back to `species._ai` columns
- Confidence tracking and review workflows

---

## Prerequisites

- SSH access to production server (167.172.143.162)
- PostgreSQL superuser or database owner privileges
- Database: `treekipedia`
- Estimated downtime: None (all migrations use `IF NOT EXISTS` clauses)

---

## Pre-Migration Checklist

```bash
# 1. SSH into production
ssh user@167.172.143.162

# 2. Check current database state
psql treekipedia -c "SELECT COUNT(*) FROM species;"
# Expected: ~67,743 rows

# 3. Verify PostGIS is enabled
psql treekipedia -c "SELECT PostGIS_Version();"
# Expected: 3.x.x

# 4. Check if migrations already applied
psql treekipedia -c "SELECT column_name FROM information_schema.columns WHERE table_name='species' AND column_name='research_version';"
# If 0 rows: migrations NOT applied (proceed)
# If 1 row: migration 07 already applied (skip to 08)

# 5. Backup (recommended)
pg_dump -Fc treekipedia > treekipedia_backup_$(date +%Y%m%d).dump
```

---

## Migration Scripts

Run these in order. Each script is idempotent (safe to run multiple times).

### Migration 07: Research Versioning

**File**: `07_research_versioning.sql`
**Purpose**: Add versioning columns for Claude research agent system

```bash
cd /path/to/silvi-open/treekipedia/database
psql treekipedia -f 07_research_versioning.sql
```

**What it creates**:
- Columns on `species`: `research_version`, `research_date`, `research_agent`, `research_confidence`, `research_sources`, `research_flags`, `research_token_cost`
- Tables: `research_history`, `research_token_usage`, `research_queue`
- Views: `research_token_summary`, `research_progress`
- Trigger: `trg_track_research_changes` (auto-tracks field changes)

**Verify**:
```bash
psql treekipedia -c "SELECT * FROM research_progress;"
# Expected output:
#  total_species | unresearched | researched | high_confidence | ...
# ---------------+--------------+------------+-----------------+
#          67743 |        67743 |          0 |               0 | ...
```

---

### Migration 08a: Insights Schema

**File**: `08_insights_schema.sql`
**Purpose**: Create atomic insights table for FAIR-compliant knowledge storage
**Requires**: Migration 07 must be run first

```bash
psql treekipedia -f 08_insights_schema.sql
```

**What it creates**:
- Table: `insights` (UUID primary key, JSONB claim values, source tracking)
- Functions: `get_species_insights()`, `supersede_insight()`, `create_insight()`
- Views: `species_insights_flat`, `insights_progress`, `insight_version_history`
- Indexes: Multiple for taxon_id, claim_type, confidence, sources

**Verify**:
```bash
psql treekipedia -c "\d insights"
# Should show ~16 columns including id, taxon_id, claim_type, claim_value, confidence, sources
```

---

### Migration 08b: Confidence Schema

**File**: `08_insights_confidence_schema.sql`
**Purpose**: Add evidence-based confidence tracking

```bash
psql treekipedia -f 08_insights_confidence_schema.sql
```

**What it creates**:
- Columns on `insights`: `corroboration`, `confidence_breakdown`
- Views: `insights_needing_review`, `confidence_statistics`
- Function: `recalculate_insight_confidence()`
- Indexes: For corroboration and low-confidence queries

**Verify**:
```bash
psql treekipedia -c "SELECT * FROM confidence_statistics;"
# Will be empty until insights are created
```

---

### Migration 08c: Atomic Insights Architecture

**File**: `08_atomic_insights_architecture.sql`
**Purpose**: Aggregation functions and auto-sync triggers

```bash
psql treekipedia -f 08_atomic_insights_architecture.sql
```

**What it creates**:
- Column on `insights`: `content_hash` (for deduplication)
- Functions: `aggregate_text_insights()`, `aggregate_ranked_insights()`, `aggregate_top_insight()`, `get_primary_common_name()`, `sync_insights_to_species()`
- Triggers: Auto-sync insights to `species._ai` columns on insert/update
- Views: `v_current_insights`, `v_species_insight_counts`, `v_multi_insight_counts`

**Verify**:
```bash
psql treekipedia -c "\df sync_insights_to_species"
# Should show the function exists

psql treekipedia -c "SELECT * FROM v_species_insight_counts LIMIT 5;"
# Will be empty until insights are created
```

---

## Post-Migration Verification

Run this comprehensive check after all migrations:

```bash
psql treekipedia << 'EOF'
-- Check species table has new columns
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'species'
  AND column_name IN ('research_version', 'research_date', 'research_confidence')
ORDER BY column_name;

-- Check insights table exists with correct structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'insights'
ORDER BY ordinal_position;

-- Check all views exist
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name IN ('research_progress', 'insights_progress', 'confidence_statistics', 'insights_needing_review')
ORDER BY table_name;

-- Check triggers exist
SELECT trigger_name, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;

-- Final status
SELECT 'Migration complete' as status;
EOF
```

**Expected output**:
- 3 columns from species check
- ~18 columns from insights check
- 4 views
- Multiple triggers on `species` and `insights` tables

---

## Rollback Procedures

If something goes wrong, here are rollback commands. **Use with caution**.

### Rollback 08c (Atomic Architecture)
```sql
DROP TRIGGER IF EXISTS tr_sync_insights_on_insert ON insights;
DROP TRIGGER IF EXISTS tr_sync_insights_on_update ON insights;
DROP TRIGGER IF EXISTS tr_set_insight_hash ON insights;
DROP FUNCTION IF EXISTS sync_insights_to_species(VARCHAR);
DROP FUNCTION IF EXISTS trigger_sync_insights_to_species();
DROP FUNCTION IF EXISTS aggregate_text_insights(VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS aggregate_ranked_insights(VARCHAR, VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS aggregate_top_insight(VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS get_primary_common_name(VARCHAR);
DROP FUNCTION IF EXISTS set_insight_hash();
DROP FUNCTION IF EXISTS generate_insight_hash(VARCHAR, VARCHAR, JSONB);
DROP VIEW IF EXISTS v_current_insights;
DROP VIEW IF EXISTS v_species_insight_counts;
DROP VIEW IF EXISTS v_multi_insight_counts;
ALTER TABLE insights DROP COLUMN IF EXISTS content_hash;
```

### Rollback 08b (Confidence Schema)
```sql
DROP VIEW IF EXISTS insights_needing_review;
DROP VIEW IF EXISTS confidence_statistics;
DROP FUNCTION IF EXISTS recalculate_insight_confidence(UUID);
DROP INDEX IF EXISTS idx_insights_corroboration;
DROP INDEX IF EXISTS idx_insights_low_confidence;
ALTER TABLE insights DROP COLUMN IF EXISTS corroboration;
ALTER TABLE insights DROP COLUMN IF EXISTS confidence_breakdown;
```

### Rollback 08a (Insights Schema)
```sql
DROP VIEW IF EXISTS insight_version_history;
DROP VIEW IF EXISTS insights_progress;
DROP VIEW IF EXISTS species_insights_flat;
DROP FUNCTION IF EXISTS create_insight(VARCHAR, VARCHAR, JSONB, FLOAT, JSONB, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS supersede_insight(UUID, JSONB, FLOAT, JSONB, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS get_species_insights(VARCHAR);
DROP FUNCTION IF EXISTS update_insight_timestamp();
DROP TABLE IF EXISTS insights;
```

### Rollback 07 (Research Versioning)
```sql
DROP TRIGGER IF EXISTS trg_track_research_changes ON species;
DROP FUNCTION IF EXISTS track_research_changes();
DROP VIEW IF EXISTS research_progress;
DROP VIEW IF EXISTS research_token_summary;
DROP TABLE IF EXISTS research_queue;
DROP TABLE IF EXISTS research_token_usage;
DROP TABLE IF EXISTS research_history;
ALTER TABLE species DROP COLUMN IF EXISTS research_version;
ALTER TABLE species DROP COLUMN IF EXISTS research_date;
ALTER TABLE species DROP COLUMN IF EXISTS research_agent;
ALTER TABLE species DROP COLUMN IF EXISTS research_confidence;
ALTER TABLE species DROP COLUMN IF EXISTS research_sources;
ALTER TABLE species DROP COLUMN IF EXISTS research_flags;
ALTER TABLE species DROP COLUMN IF EXISTS research_token_cost;
```

---

## Troubleshooting

### Error: "column already exists"
This is safe to ignore - the `IF NOT EXISTS` clause handles this.

### Error: "function does not exist"
Run migrations in order. Migration 08 depends on 07.

### Error: "permission denied"
Ensure you're connecting as database owner or superuser:
```bash
psql -U postgres treekipedia -f migration.sql
```

### Insights not syncing to species table
Check triggers are enabled:
```sql
SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = 'insights'::regclass;
-- All should show 'O' (origin) or 'A' (always)
```

---

## Production Server Details

- **Host**: 167.172.143.162 (Digital Ocean)
- **Database**: treekipedia
- **PostgreSQL Version**: 14+ with PostGIS 3.x
- **Backend API**: https://treekipedia-api.silvi.earth
- **Frontend**: https://treekipedia.silvi.earth (Vercel)

---

## Contact

For issues with these migrations, check:
1. `.claude/project-management/CHANGELOG.md` for recent changes
2. `.claude/project-management/TODO.md` for known issues
3. `treekipedia/database/README.md` for schema documentation
