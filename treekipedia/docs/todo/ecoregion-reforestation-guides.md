# Ecoregion Reforestation Guides

**Status**: Phases 1-3 complete — species researched, guide v4 synthesized, frontend live.
**Added**: January 27, 2026
**Updated**: February 4, 2026
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

**Progress**: 29/25 researched (116%) | Guide v4 synthesized | All queue species + top LEAF species complete

| # | Species | taxon_id | Common Name | Affinity | Research Status |
|---|---------|----------|-------------|----------|-----------------|
| 1 | *Pistacia lentiscus* | AngMaSaNcRd46762-00 | Mastic Tree | — | ✅ **Researched** v1 — 68 insights |
| 2 | *Myrtus communis* | AngMaMyMyRt39690-00 | Common Myrtle | 4,132,746 | ✅ **Researched** v2 — 68 insights |
| 3 | *Quercus ilex* | AngMaFaFgCx14759-00 | Holm Oak | 1,040,372 | ✅ **Researched** v2 — 73 insights |
| 4 | *Arbutus unedo* | AngMaErRcCa06930-00 | Strawberry Tree | 1,396,136 | ✅ **Researched** — 91 insights |
| 5 | *Juniperus phoenicea* | GymPiPiCpRs50433-06 | Phoenician Juniper | — | ✅ **Researched** v1 — 63 insights |
| 6 | *Juniperus oxycedrus* | GymPiPiCpRs50432-00 | Prickly Juniper | — | ✅ **Researched** v1 — 69 insights |
| 7 | *Ceratonia siliqua* | AngMaFaFbCx10351-00 | Carob Tree | 559,710 | ✅ **Researched** — 82 insights |
| 8 | *Rhamnus alaternus* | AngMaRoRhMn44052-00 | Mediterranean Buckthorn | 453,200 | ✅ **Researched** — 76 insights |
| 9 | *Viburnum tinus* | AngMaDiVbRn04478-00 | Laurustinus | 323,136 | ✅ **Researched** — 67 insights |
| 10 | *Pinus halepensis* | GymPiPiPnCx50774-00 | Aleppo Pine | 332,100 | ✅ **Researched** — 74 insights |
| 11 | *Olea europaea* | AngMaLaLcXx20795-00 | European Olive | 802,190 | ✅ **Researched** — 223 insights |
| 12 | *Pyrus spinosa* | AngMaRoRsCx44614-00 | Almond-Leaved Pear | 249,696 | ✅ **Researched** — 65 insights |
| 13 | *Erica arborea* | AngMaErRcCa06994-00 | Tree Heath | 190,500 | ✅ **Researched** — 100 insights |
| 14 | *Chamaerops humilis* | AngNAPaRcCx49866-00 | European Fan Palm | 178,407 | ✅ **Researched** — 84 insights |
| 15 | *Pinus pinaster* | GymPiPiPnCx50811-00 | Maritime Pine | 172,666 | ✅ **Researched** — 85 insights |
| 16 | *Tamarix africana* | AngMaCaTmRc03532-00 | African Tamarisk | 112,752 | ✅ **Researched** — 75 insights |
| 17 | *Euphorbia dendroides* | AngMaMaPhRb29612-00 | Tree Spurge | 100,386 | ✅ **Researched** — 66 insights |
| 18 | *Phillyrea latifolia* | AngMaLaLcXx20828-00 | Mock Privet | 93,936 | ✅ **Researched** — 66 insights |
| 19 | *Quercus suber* | AngMaFaFgCx14925-00 | Cork Oak | 84,868 | ✅ **Researched** — 70 insights |
| 20 | *Vitex agnus-castus* | AngMaLaLmCx21234-00 | Chaste Tree | 79,206 | ✅ **Researched** — 129 insights |
| 21 | *Laurus nobilis* | AngMaLaLrCx22770-00 | Bay Laurel | 78,364 | ✅ **Researched** — 70 insights |
| 22 | *Quercus pubescens* | AngMaFaFgCx14877-00 | Downy Oak | 53,055 | ✅ **Researched** — 66 insights |
| 23 | *Celtis australis* | AngMaRoCnNb42825-00 | European Nettle Tree | 44,528 | ✅ **Researched** — 68 insights |
| 24 | *Taxus baccata* | GymPiPiTxCx50907-00 | English Yew | 41,992 | ✅ **Researched** — 67 insights |
| 25 | *Prunus spinosa* | AngMaRoRsCx44529-00 | Blackthorn | 32,980 | ✅ **Researched** — 66 insights |
| 26 | *Cercis siliquastrum* | AngMaFaFbCx10360-00 | Judas Tree | 32,552 | ✅ **Researched** — 67 insights |
| 27 | *Pinus pinea* | GymPiPiPnCx50813-00 | Italian Stone Pine | 27,924 | ✅ **Researched** — 68 insights |
| 28 | *Fraxinus ornus* | AngMaLaLcXx20652-00 | Manna Ash | 19,240 | ✅ **Researched** — 68 insights |

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

### Phase 1: Research Species ✅ COMPLETE (29/25)
- [x] Add 25 pilot species to research queue (queue IDs 1-24)
- [x] Research all 24 queue species (completed Jan 30, 2026)
- [x] Research top LEAF species missing from queue: Pistacia lentiscus, Juniperus phoenicea, Juniperus oxycedrus
- [x] Fix Myrtus communis sync issue (insights existed but weren't synced)
- [x] Re-research Quercus ilex (v2)
- [x] Verify insights populated — all species have 63-223 insights
- [x] Synthesize guide v4 with updated species data (Feb 4, 2026)

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
