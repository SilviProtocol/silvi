# Frontend v10 Implementation Plan

**Status**: IN PROGRESS
**Priority**: High
**Started**: November 2025
**Related TODO Section**: `[IN PROGRESS] - Frontend v10 Field Implementation`

---

## Overview

Backend v10 data migration completed November 18, 2025. Frontend needs to display the 17 new fields added to species data.

## New Fields to Display

### Climate Data (8 fields)
| Field | Type | Population | Display Location |
|-------|------|------------|------------------|
| `koppen_geiger` | TEXT | 88% | ClimateProfile component |
| `temperature_annual_c` | TEXT | 60% | ClimateProfile component |
| `precipitation_annual_mm` | TEXT | 65% | ClimateProfile component |
| `temperature_min_c` | TEXT | 60% | ClimateProfile component |
| `temperature_max_c` | TEXT | 60% | ClimateProfile component |
| `precipitation_min_mm` | TEXT | 65% | ClimateProfile component |
| `precipitation_max_mm` | TEXT | 65% | ClimateProfile component |
| `precipitation_seasonality` | TEXT | 60% | ClimateProfile component |

### GloBI Ecological Interactions (8 fields)
| Field | Type | Population | Display Location |
|-------|------|------------|------------------|
| `globi_pollinatedby` | TEXT | sparse | EcologicalInteractions |
| `globi_eatenby` | TEXT | 24% | EcologicalInteractions |
| `globi_flowersvisitedby` | TEXT | sparse | EcologicalInteractions |
| `globi_hasparasite` | TEXT | sparse | EcologicalInteractions |
| `globi_haspathogen` | TEXT | sparse | EcologicalInteractions |
| `globi_hostof` | TEXT | sparse | EcologicalInteractions |
| `globi_parasiteof` | TEXT | sparse | EcologicalInteractions |
| `globi_pathogenof` | TEXT | sparse | EcologicalInteractions |

### SBTN Land Cover (1 field)
| Field | Type | Population | Display Location |
|-------|------|------------|------------------|
| `sbtn_landcover` | TEXT | 85% | SpeciesInfobox or new section |

---

## Implementation Tasks

### 1. TypeScript Types Update
- [ ] Update `frontend/lib/types.ts` with v10 field interfaces
- [ ] Add proper typing for climate data (handle semicolon-separated ranges)
- [ ] Add typing for GloBI interaction arrays

### 2. ClimateProfile Component
- [ ] Component already exists at `frontend/app/species/[taxon_id]/components/ClimateProfile.tsx`
- [ ] Verify it handles all 8 climate fields
- [ ] Add proper formatting for temperature (°C) and precipitation (mm)
- [ ] Handle "NA" values gracefully
- [ ] Display Köppen-Geiger classification with explanation

### 3. EcologicalInteractions Component
- [ ] Component exists at `frontend/app/species/[taxon_id]/components/EcologicalInteractions.tsx`
- [ ] Verify all 8 GloBI fields are displayed
- [ ] Group interactions by type (beneficial vs threats)
- [ ] Handle sparse data - show "No data available" appropriately
- [ ] Use emerald for beneficial (pollinators), red for threats (parasites, pathogens)

### 4. SBTN Land Cover Display
- [ ] Add to SpeciesInfobox or create dedicated section
- [ ] Format land cover classification nicely
- [ ] Handle 15% missing data

### 5. Integration & Testing
- [ ] Test with species that have full v10 data
- [ ] Test with species that have partial data
- [ ] Test with species that have no v10 data
- [ ] Verify mobile responsiveness

---

## Reference Documentation

- **SPECIES_FIELDS_FRONTEND_GUIDE.md** - Complete 130-field reference with data patterns
- **database/04_v10_schema_migration.sql** - GloBI and SBTN field definitions
- **database/05_v10_climate_fields.sql** - Climate field definitions

---

## Completion Criteria

- [ ] All 17 v10 fields displayed on species pages
- [ ] Proper handling of missing/NA data
- [ ] TypeScript types updated
- [ ] Mobile responsive
- [ ] Tested across species with varying data coverage

---

**When complete**: Move this file to `docs/completed/` and update CHANGELOG.md
