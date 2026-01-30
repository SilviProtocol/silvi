# Ecoregion Reforestation Guides

**Status**: Phases 2-3 complete — backend API + frontend pages live. Phase 1 species research ongoing.
**Added**: January 27, 2026
**Updated**: January 28, 2026
**First Target**: Tyrrhenian-Adriatic sclerophyllous and mixed forests (eco_id 806, Sicily/Southern Italy)

---

## Overview

Generate data-driven reforestation guides per ecoregion using Treekipedia's LEAF scoring, species knowledge, and AI research. Guides will be accessible as frontend pages and eventually feed into a ReFi Reforestation Playbook for Regen Coordination.

---

## Guide Content Structure

Each ecoregion guide contains:

1. **Ecoregion Header** — name, biome, realm, geographic description
2. **Top Recommended Species** — LEAF-ranked, grouped by tier (BEST/GOOD/ACCEPTABLE)
   - Common name, scientific name, image
   - LEAF score + tier
   - Key attributes: max height, growth rate, ecological function, native status
   - AI research summary (general_description_ai, stewardship_ai, ecological_function_ai)
3. **Planting Strategy** — species grouped by ecological role (canopy, understory, pioneer, nitrogen-fixer)
4. **Climate Context** — temperature/precipitation ranges for the ecoregion
5. **Conservation Notes** — threatened species in the list

---

## Frontend Implementation

### New Routes
- `/guides` — index page listing available ecoregion guides
- `/guides/ecoregion/[eco_id]` — individual guide page

### Components Needed
- `GuideCard.tsx` — ecoregion card for index page
- `GuideSpeciesRow.tsx` — species entry within a guide
- `GuideHeader.tsx` — ecoregion header with metadata
- Reuse existing: ImageCarousel patterns, DataField, map components

### Navigation
- Add "Guides" to navbar routes array in `components/navbar.tsx`

### Data Fetching
- **Guide endpoint**: `GET /api/guides/ecoregion/:eco_id` — bundles everything in one call
- **Search endpoint**: `GET /api/geospatial/ecoregions/search?q=` — autocomplete
- **Synthesis endpoint**: `POST /api/guides/ecoregion/:eco_id/synthesize` — trigger LLM generation

---

## Pilot: Tyrrhenian-Adriatic (eco_id 806)

### Ecoregion Info
- **Name**: Tyrrhenian-Adriatic sclerophyllous and mixed forests
- **Biome**: Mediterranean Forests, Woodlands & Scrub
- **Realm**: Palearctic
- **Tiles**: 19,240

### Top 25 LEAF Species — Research Tracker

**Progress**: 2/25 researched (8%) | 23 pending in research queue

| # | Species | taxon_id | Common Name | Affinity | Research Status |
|---|---------|----------|-------------|----------|-----------------|
| 1 | *Myrtus communis* | AngMaMyMyRt39690-00 | Common Myrtle | 4,132,746 | **Researched** v1 — 67 insights, 0.84 confidence |
| 2 | *Arbutus unedo* | AngMaErRcCa06930-00 | Strawberry Tree | 1,396,136 | Queued (queue #2) |
| 3 | *Quercus ilex* | AngMaFaFgCx14759-00 | Holm Oak | 1,040,372 | **Researched** v1 — 73 insights, 0.87 confidence |
| 4 | *Olea europaea* | AngMaLaLcXx20795-00 | European Olive | 802,190 | Queued (queue #3) |
| 5 | *Ceratonia siliqua* | AngMaFaFbCx10351-00 | Carob Tree | 559,710 | Queued (queue #4) |
| 6 | *Rhamnus alaternus* | AngMaRoRhMn44052-00 | Italian Buckthorn | 453,200 | Queued (queue #5) |
| 7 | *Pinus halepensis* | GymPiPiPnCx50774-00 | Aleppo Pine | 332,100 | Queued (queue #6) |
| 8 | *Viburnum tinus* | AngMaDiVbRn04478-00 | Laurustinus | 323,136 | Queued (queue #7) |
| 9 | *Pyrus spinosa* | AngMaRoRsCx44614-00 | Almond-Leaved Pear | 249,696 | Queued (queue #8) |
| 10 | *Erica arborea* | AngMaErRcCa06994-00 | Tree Heath | 190,500 | Queued (queue #9) |
| 11 | *Chamaerops humilis* | AngNAPaRcCx49866-00 | European Fan Palm | 178,407 | Queued (queue #10) |
| 12 | *Pinus pinaster* | GymPiPiPnCx50811-00 | Maritime Pine | 172,666 | Queued (queue #11) |
| 13 | *Tamarix africana* | AngMaCaTmRc03532-00 | African Tamarisk | 112,752 | Queued (queue #12) |
| 14 | *Euphorbia dendroides* | AngMaMaPhRb29612-00 | Tree Spurge | 100,386 | Queued (queue #13) |
| 15 | *Phillyrea latifolia* | AngMaLaLcXx20828-00 | Mock Privet | 93,936 | Queued (queue #14) |
| 16 | *Quercus suber* | AngMaFaFgCx14925-00 | Cork Oak | 84,868 | Queued (queue #15) |
| 17 | *Vitex agnus-castus* | AngMaLaLmCx21234-00 | Chaste Tree | 79,206 | Queued (queue #16) |
| 18 | *Laurus nobilis* | AngMaLaLrCx22770-00 | Bay Laurel | 78,364 | Queued (queue #17) |
| 19 | *Quercus pubescens* | AngMaFaFgCx14877-00 | Downy Oak | 53,055 | Queued (queue #18) |
| 20 | *Celtis australis* | AngMaRoCnNb42825-00 | European Nettle Tree | 44,528 | Queued (queue #19) |
| 21 | *Taxus baccata* | GymPiPiTxCx50907-00 | English Yew | 41,992 | Queued (queue #20) |
| 22 | *Prunus spinosa* | AngMaRoRsCx44529-00 | Blackthorn | 32,980 | Queued (queue #21) |
| 23 | *Cercis siliquastrum* | AngMaFaFbCx10360-00 | Judas Tree | 32,552 | Queued (queue #22) |
| 24 | *Pinus pinea* | GymPiPiPnCx50813-00 | Italian Stone Pine | 27,924 | Queued (queue #23) |
| 25 | *Fraxinus ornus* | AngMaLaLcXx20652-00 | Manna Ash | 19,240 | Queued (queue #24) |

### Research Approach
- All 25 species added to `research_queue` table (queue IDs 1-24; Quercus ilex researched directly via API)
- Research queue API enables multi-session processing — see [PUBLIC_API_GUIDE.md](../../PUBLIC_API_GUIDE.md#research-queue-api--batch-species-research) for workflow
- Two research paths available:
  1. **Queue workflow**: `GET /research/queue/next` → `POST .../start` → research → `POST /research/{taxon_id}/save` → `POST .../complete`
  2. **Direct research**: `POST /species/{taxon_id}/research` (Grok Atomic v2, instant)
- 35 fields, 50-80+ atomic insights per species
- Track completion in table above

---

## Implementation Phases

### Phase 1: Research Species (current — 2/25 complete)
- [x] Add 25 pilot species to research queue (queue IDs 1-24)
- [x] Research Myrtus communis (67 insights, 0.84 confidence)
- [x] Research Quercus ilex (73 insights, 0.87 confidence)
- [ ] Research remaining 23 species (via queue workflow or direct Grok API)
- [ ] Verify insights populated in database for all 25
- [ ] Review quality of research output

### Phase 2: Backend API ✅ COMPLETE
- [x] Create `GET /api/guides/ecoregion/:eco_id` endpoint
  - Returns: ecoregion metadata, synthesized content (if exists), LEAF-ranked species by tier, top 10 enriched with _ai fields
- [x] Create `POST /api/guides/ecoregion/:eco_id/synthesize` endpoint
  - Triggers Grok 4.1 Fast synthesis, stores in `ecoregion_guides` table
  - Supports `?force=true` to regenerate
- [x] Create `GET /api/geospatial/ecoregions/search?q=` endpoint
  - ILIKE search on eco_name for autocomplete
- [x] Create `ecoregion_guides` database table (migration: `database/09_ecoregion_guides_table.sql`)
- [x] Create guide synthesis service (`backend/services/guideSynthesis.js`)

### Phase 3: Frontend Guide Pages ✅ COMPLETE
- [x] Create `/guide` search page with type-ahead autocomplete (300ms debounce)
- [x] Create `/guide/[eco_id]` detail page with accordion sections
- [ ] Add "Guides" to navbar (deferred — no navbar link yet per plan)
- [x] Components: Accordion, TierBadge, SpeciesCard, CompactSpeciesRow
- [x] Follow existing design system (emerald accents, dark theme, backdrop blur cards)

**Frontend Routes** (accessible now):
- `/guide` — Ecoregion search with autocomplete
- `/guide/806` — Tyrrhenian-Adriatic guide (or any eco_id)

### Phase 4: Polish & Expand
- [ ] Add map visualization showing ecoregion boundary
- [ ] Add planting strategy section (species by ecological role)
- [ ] Add climate context section
- [ ] Generate guides for additional ecoregions (12 bioregional campaign targets)

---

## Future: ReFi Reforestation Playbook

The ecoregion guides become a key resource within a broader Regen Coordination playbook. The playbook would follow their template (Introduction, Description, Business Model, How It Works, Case Studies, Scaling) and explain how to use Treekipedia + Silvi tools for science-backed reforestation planning. Separate planning doc TBD.

---

## Related Documentation
- [LEAF.md](LEAF.md) — LEAF scoring algorithm
- [frontend-v10-implementation.md](frontend-v10-implementation.md) — Frontend field implementation
- [docs/RECOMMENDATION_SERVICE.md](../RECOMMENDATION_SERVICE.md) — Species recommendation spec
- [docs/REFI_PLAYBOOK.md](../REFI_PLAYBOOK.md) — Regen Coordination playbook template
