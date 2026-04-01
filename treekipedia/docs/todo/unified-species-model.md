# Unified Species Model — Treekipedia as Single Source of Truth

**Status**: Phases 0-3 complete, Phases 4-5 pending (Silvi side)
**Created**: 2026-04-01
**Last Updated**: 2026-04-01
**Goal**: Consolidate Silvi's static `core_species` table and Treekipedia's 67,927-species database into a single species model, with Treekipedia as the authoritative source.

---

## Problem Statement

Silvi currently maintains a **static snapshot** (`core_species`, 50,765 rows, 11 columns) derived from Treekipedia but never synced. Treekipedia has 67,927 species with 140+ fields, AI research, geospatial data, images, and LEAF scoring. The two systems diverge over time:

- Silvi is missing ~17,000 species that Treekipedia has
- Silvi has no access to AI-researched data, images, native status, or LEAF scores
- Common names in Silvi are a single flat field per species; Treekipedia has richer (but still messy) data
- 95 user-submitted staging species in Silvi have no `taxon_id` and aren't in Treekipedia
- The only live integration is runtime LEAF API calls for species prediction — these don't update `core_species`

## Architecture: Treekipedia as Source + Silvi Light Cache

```
┌─────────────────────────────────────────────────────────┐
│  Treekipedia PostgreSQL (source of truth)               │
│  67,927+ species, 140+ fields                           │
│  species_common_names table (structured, regional)      │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
     Sync endpoint                  Live API
     GET /api/species/light-list    (rich data on demand)
     (bulk download, versioned)           │
               │                          │
               ▼                          │
┌──────────────────────────────┐          │
│  Silvi core_species (cache)  │          │
│  ──────────────────────────  │          │
│  id (PK, integer — keep)     │          │
│  taxon_id (unique, indexed)  │          │
│  scientific_name             │          │
│  display_common_name         │◄── pre-computed best English name
│  common_names (JSONB)        │◄── [{name, lang, regions, primary}]
│  family                      │          │
│  genus                       │          │
│  staging (bool)              │          │
│  synced_at (timestamp)       │          │
└──────────┬───────────────────┘          │
           │                              │
    Silvi frontend                        │
    (search from IndexedDB               │
     offline cache)                       │
           │                              │
           └──── Deep species info ───────┘
                 (images, research, LEAF)
                 fetched from Treekipedia API
```

### Key Decisions

1. **Keep `core_species.id` as integer PK** — 6,874+ trees reference it via FK. No migration needed.
2. **`taxon_id` becomes the cross-system key** — used for Treekipedia API lookups and dedup.
3. **Offline cache uses the light list** — ~67K rows × 6 small columns + JSONB common names ≈ 10-15MB in IndexedDB.
4. **Search happens client-side** against the cached light list — instant, no network dependency.
5. **Rich data fetched on demand** from Treekipedia API — species details, images, research, LEAF scores.

---

## Phase 1: `species_common_names` Table in Treekipedia

**Goal**: Structured, regional common name storage replacing the messy `common_name` text blob.

### 1.1 Create Table

```sql
CREATE TABLE species_common_names (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    taxon_id TEXT NOT NULL,
    name TEXT NOT NULL,
    language_code VARCHAR(10),          -- ISO 639-1: 'en', 'es', 'id', 'ja'
    region_codes TEXT[],                -- ISO 3166-1 alpha-2: ['ID', 'MY']
    source TEXT NOT NULL DEFAULT 'bulk_import',  -- 'bulk_import', 'ai_research', 'user', 'wcvp'
    is_primary BOOLEAN DEFAULT false,   -- primary name for this language+species
    submitted_by TEXT,                  -- user attribution
    staging BOOLEAN DEFAULT false,      -- user-submitted, pending review
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_species FOREIGN KEY (taxon_id) REFERENCES species(taxon_id),
    CONSTRAINT uq_name_lang UNIQUE (taxon_id, name, language_code)
);

CREATE INDEX idx_common_names_taxon ON species_common_names(taxon_id);
CREATE INDEX idx_common_names_lang ON species_common_names(language_code);
CREATE INDEX idx_common_names_region ON species_common_names USING GIN(region_codes);
CREATE INDEX idx_common_names_search ON species_common_names USING gin(name gin_trgm_ops);
```

### 1.2 Bulk Parse Existing `common_name` Field

Write a script to parse the semicolon-separated `common_name` blob into structured rows:

**Parsing strategy:**
- Split by `;` → individual name blocks
- Detect language markers: `"Oak (en)"` → name="Oak", lang="en"
- Names without markers → lang=NULL (unknown), source='bulk_import'
- Skip empty strings, "NA", pure whitespace
- Dedup within same taxon_id + name + language

**Expected yield:** ~300K-500K name rows from 67K species (avg 4-7 names each).

### 1.3 Pre-compute `display_common_name` on Species Table

Add a computed column or materialized view:

```sql
ALTER TABLE species ADD COLUMN display_common_name TEXT;
```

**Priority logic (matches current frontend heuristic):**
1. `popular_common_name_ai` if exists (AI-researched, highest trust)
2. Primary English name from `species_common_names` where `is_primary = true AND language_code = 'en'`
3. First-position name from original `common_name` field (fallback)

Run a one-time update + trigger to keep it current.

---

## Phase 2: Treekipedia Light List Endpoint

**Goal**: Efficient bulk endpoint for Silvi to sync species data.

### 2.1 `GET /api/species/light-list`

```
GET /api/species/light-list?since=2026-03-01T00:00:00Z&page=1&per_page=10000

Response:
{
  "total": 67927,
  "page": 1,
  "per_page": 10000,
  "updated_since": "2026-03-01T00:00:00Z",
  "data": [
    {
      "taxon_id": "AngMaMyMyRt37476-00",
      "scientific_name": "Myrtus communis",
      "display_common_name": "Common Myrtle",
      "family": "Myrtaceae",
      "genus": "Myrtus",
      "common_names": [
        {"name": "Common Myrtle", "lang": "en", "regions": null, "primary": true},
        {"name": "Arrayán", "lang": "es", "regions": ["ES", "AR"], "primary": true},
        {"name": "ミルツス", "lang": "ja", "regions": ["JP"], "primary": true}
      ]
    }
  ],
  "version": "2026-04-01T12:00:00Z"
}
```

**Features:**
- Paginated (10K per page) for initial bulk sync
- `since` parameter for incremental sync (only changed species)
- `version` timestamp for cache invalidation
- Common names pre-aggregated from `species_common_names` table as JSONB array
- Lightweight — only fields needed for search/display, not all 140+

### 2.2 Optimize the `/species` Search Endpoint

Currently returns `SELECT *` (140+ columns, 500-800KB per query). Add a `fields` parameter or create a dedicated search response:

```
GET /species?search=mango&fields=taxon_id,species_scientific_name,display_common_name,family,genus
```

Or better, make the default response lightweight and require `?full=true` for all fields.

---

## Phase 3: Common Name Contribution Endpoint

**Goal**: Let Silvi users contribute common names that flow into Treekipedia.

### 3.1 `POST /api/species/:taxon_id/common-names`

```
POST /api/species/AngMaMyMyRt37476-00/common-names
{
  "name": "Mirto",
  "language_code": "it",
  "region_codes": ["IT"],
  "submitted_by": "user@silvi.earth"
}

Response:
{
  "id": "uuid",
  "taxon_id": "AngMaMyMyRt37476-00",
  "name": "Mirto",
  "language_code": "it",
  "staging": true,
  "created_at": "2026-04-01T..."
}
```

**Behavior:**
- Inserts with `staging: true` and `source: 'user'`
- Immediately visible to the submitting user (client-side optimistic update)
- Flows to other users on next sync cycle
- Future: moderation queue for staging → confirmed promotion

### 3.2 User-Submitted Species (New Species Not in Treekipedia)

When a Silvi user creates a species that doesn't exist:
- Currently creates a `core_species` row with `staging=true` in Django
- New flow: POST to Treekipedia staging endpoint, get back a temporary `taxon_id`
- Or: keep staging in Django, batch-reconcile with Treekipedia periodically

**Decision**: Keep staging species in Django for now. Add a reconciliation script later that matches staging species to Treekipedia records by scientific name and promotes them.

---

## Phase 4: Django Sync + Schema Evolution

**Goal**: Evolve `core_species` to sync from Treekipedia light list.

### 4.1 Schema Migration

```python
# Django migration
class Migration(migrations.Migration):
    operations = [
        # Add new fields
        migrations.AddField('Species', 'display_common_name', models.CharField(max_length=256, null=True)),
        migrations.AddField('Species', 'common_names', models.JSONField(default=list)),
        migrations.AddField('Species', 'synced_at', models.DateTimeField(null=True)),

        # Keep existing fields for backward compat during transition:
        # species_common_name, species_scientific_name, subspecies, genus, family,
        # taxonomic_class, taxonomic_order, taxon_id, taxon_full, staging

        # Add unique constraint on taxon_id (after fixing nulls)
        migrations.AddConstraint('Species', models.UniqueConstraint(
            fields=['taxon_id'],
            condition=models.Q(taxon_id__isnull=False),
            name='unique_taxon_id'
        )),
    ]
```

### 4.2 Sync Management Command

```bash
python manage.py sync_species --full        # Full sync (initial or reset)
python manage.py sync_species --incremental # Only changes since last sync
```

**Logic:**
1. Fetch from Treekipedia `GET /api/species/light-list?since=<last_synced_at>`
2. For each species:
   - Match by `taxon_id`
   - Upsert: update `display_common_name`, `common_names`, `scientific_name`, `family`, `genus`, `synced_at`
   - New species: create with next auto-increment `id`
3. Don't touch `staging=true` records (user-submitted, not from Treekipedia)
4. Log: created, updated, skipped counts

**Frequency**: Manual trigger or weekly cron. Species list changes rarely.

### 4.3 Update SpeciesSerializer

```python
class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = ['id', 'taxon_id', 'species_scientific_name', 'display_common_name',
                  'common_names', 'genus', 'family', 'staging']
```

---

## Phase 5: Frontend — Regional Name Display + Updated Cache

**Goal**: Show the best common name for the user's region/language.

### 5.1 Regional Name Resolution (Client-Side)

```typescript
interface CommonName {
  name: string;
  lang: string | null;
  regions: string[] | null;
  primary: boolean;
}

function getBestCommonName(
  commonNames: CommonName[],
  userCountry: string,   // ISO 3166-1 alpha-2 from GPS → reverse geocode
  userLangs: string[]    // from device locale, e.g. ['id', 'en']
): { primary: string; alternatives: string[] } {
  // 1. Exact region + language match
  const regionLangMatch = commonNames.find(n =>
    n.regions?.includes(userCountry) && userLangs.includes(n.lang)
  );
  if (regionLangMatch) return { primary: regionLangMatch.name, alternatives: ... };

  // 2. Language match (primary for that language)
  const langMatch = commonNames.find(n =>
    userLangs.includes(n.lang) && n.primary
  );
  if (langMatch) return { primary: langMatch.name, alternatives: ... };

  // 3. Any language match
  const anyLangMatch = commonNames.find(n => userLangs.includes(n.lang));
  if (anyLangMatch) return { primary: anyLangMatch.name, alternatives: ... };

  // 4. English fallback
  const englishName = commonNames.find(n => n.lang === 'en' && n.primary);
  if (englishName) return { primary: englishName.name, alternatives: ... };

  // 5. First available
  return { primary: commonNames[0]?.name ?? '', alternatives: ... };
}
```

### 5.2 Offline Cache Update

Update IndexedDB schema to store the light list with common names JSONB:

```typescript
interface CachedSpecies {
  id: number;               // Django PK (for FK references)
  taxon_id: string;
  scientific_name: string;
  display_common_name: string;
  family: string;
  genus: string;
  common_names: CommonName[];
}
```

**Cache size estimate**: 67K species × ~200 bytes avg (with 3-5 common names) ≈ **13MB**. Acceptable for IndexedDB.

**Search**: Client-side search over `scientific_name`, `display_common_name`, and all `common_names[].name`. Use a pre-built search index (e.g., Fuse.js or simple trie) for sub-50ms results.

### 5.3 User's Region Detection

- GPS coordinates already available (tree logging requires location)
- Reverse geocode to country code: use device locale as primary signal, GPS-based country as secondary
- Cache the user's country code in app state — doesn't change often

### 5.4 Species Search UX

```
┌─────────────────────────────────────┐
│ 🔍 Search species...                │
├─────────────────────────────────────┤
│ Recent:                             │
│   🕐 Jati (Tectona grandis)        │
│   🕐 Mahoni (Swietenia macrophylla)│
├─────────────────────────────────────┤
│ Results:                            │
│   🌳 Jati                           │
│      Tectona grandis · Lamiaceae    │
│      Also: Teak, Sagwan             │
│                                     │
│   🌳 Jati Putih                     │
│      Gmelina arborea · Lamiaceae    │
│      Also: White Teak, Gamhar       │
│                                     │
│   ＋ Add new species...              │
└─────────────────────────────────────┘
```

- Primary display: regional common name (large)
- Subtitle: scientific name + family
- "Also known as": 2-3 alternative common names
- All search and display runs from local cache — instant

---

## Phase 6: Future Enhancements

### 6.1 AI-Powered Common Name Enrichment
Expand Grok research prompt to return common names by language/region instead of just one English name. Store results in `species_common_names` with `source: 'ai_research'`.

### 6.2 Common Name Moderation
Admin interface to review `staging=true` user-submitted names. Bulk approve/reject. Auto-promote after N identical submissions from different users.

### 6.3 Treekipedia Species Detail in Silvi
When user taps a species in Silvi, show Treekipedia-powered species card: image, AI research summary, native status, LEAF score for their location. Fetched live from Treekipedia API.

### 6.4 Bidirectional Species Sync
Staging species created in Silvi that get confirmed → automatically create in Treekipedia if they don't exist (new species discovery from field data).

---

## Implementation Order

| Phase | Effort | Depends On | Status | Description |
|-------|--------|------------|--------|-------------|
| **1.1** | Medium | Nothing | **DONE** | Create `species_common_names` table |
| **1.2** | Medium | 1.1 | **DONE** | Bulk parse existing `common_name` data (175,179 rows) |
| **1.3** | Small | 1.2 | **DONE** | Pre-compute `display_common_name` (19,980 species) |
| **2.1** | Medium | 1.3 | **DONE** | Light list endpoint (`GET /api/common-names/light-list`) |
| **2.2** | Small | Nothing | **DONE** | Optimize search endpoint (41KB vs 831KB, 20x reduction) |
| **3.1** | Small | 1.1 | **DONE** | Common name contribution endpoint |
| **3.2** | Deferred | — | Pending | Staging species reconciliation |
| **4.1** | Medium | 2.1 | Pending | Django schema migration |
| **4.2** | Medium | 4.1 + 2.1 | Pending | Sync management command |
| **4.3** | Small | 4.1 | Pending | Update serializer |
| **5.1** | Medium | 4.1 | Pending | Regional name resolution logic |
| **5.2** | Medium | 4.2 | Pending | Offline cache update |
| **5.3** | Small | 5.1 | Pending | Region detection |
| **5.4** | Medium | 5.1 + 5.2 | Pending | Species search UX redesign |

**Critical path**: 1.1 → 1.2 → 1.3 → 2.1 → 4.1 → 4.2 → 5.2 → 5.4

---

## Open Questions

- **Language detection for bulk parse**: How accurate can we be inferring language from the raw `common_name` field? Many entries have no markers. May need AI assistance for ambiguous names.
- **Region-to-language mapping**: Should we maintain a country→primary-language lookup table, or rely entirely on device locale?
- **Cache refresh trigger**: Pull-based (app checks on launch) vs push-based (notification when light list changes)?
- **Search ranking**: When searching in the light list, should results be ranked by relevance to user's region (Indonesian names first for Indonesian users)?
