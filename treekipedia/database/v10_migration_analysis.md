# Treekipedia v10 Migration Analysis

## Migration Date
November 16, 2025

## Data Source
- File: `Treekipedia_V10_Final_Climate_October_21d.csv` (1.3 GB)
- Location: `/root/silvi-open/treekipedia/`

## Schema Comparison

### ✅ Fields Already in Database (No Action Needed)
These fields exist in both current DB and v10 schema:

- species_scientific_name
- subspecies
- taxon_id_new
- taxon_full
- family
- genus
- common_name
- common_countries
- accepted_scientific_name
- taxon_id
- class
- taxonomic_order
- ecoregions
- biomes
- general_description_human
- ecological_function_human
- elevation_ranges_human
- compatible_soil_types_human
- default_image
- habitat_human
- total_occurrences
- specific_epithet
- conservation_status_ai
- general_description_ai
- ecological_function_ai
- elevation_ranges_ai
- compatible_soil_types_ai
- habitat_ai
- synonyms
- forest_type
- wetland_type
- urban_setting
- climate_change_vulnerability
- associated_species
- native_adapted_habitats_ai
- native_adapted_habitats_human
- agroforestry_use_cases_ai
- agroforestry_use_cases_human
- successional_stage
- tolerances
- forest_layers
- growth_form_ai
- growth_form_human
- leaf_type_ai
- leaf_type_human
- deciduous_evergreen_ai
- deciduous_evergreen_human
- flower_color_ai
- flower_color_human
- fruit_type_ai
- fruit_type_human
- bark_characteristics_ai
- bark_characteristics_human
- maximum_height_ai
- maximum_height_human
- maximum_diameter_ai
- maximum_diameter_human
- lifespan_ai
- lifespan_human
- maximum_tree_age_ai
- maximum_tree_age_human
- allometric_models
- allometric_curve
- national_conservation_status
- verification_status
- threats
- timber_value
- non_timber_products
- cultural_significance_ai
- cultural_significance_human
- cultivars
- nutritional_caloric_value
- cultivation_details
- stewardship_best_practices_ai
- stewardship_best_practices_human
- planting_recipes_ai
- planting_recipes_human
- pruning_maintenance_ai
- pruning_maintenance_human
- disease_pest_management_ai
- disease_pest_management_human
- fire_management_ai
- fire_management_human
- reference_list
- data_sources
- ipfs_cid
- last_updated_date
- researched
- associated_media
- bioregions
- conservation_status_human
- soil_texture_all (DB: lowercase)
- soil_texture_dominant
- soil_texture_prefered
- soil_texture_tolerated
- ph_all (DB: lowercase)
- ph_dominant
- ph_prefered
- ph_tolerated
- oc_all (DB: lowercase)
- oc_dominant
- oc_prefered
- oc_tolerated
- countries_native
- countries_invasive
- countries_introduced
- present_intact_forest (DB: lowercase)
- functional_ecosystem_groups
- vegetationtype (DB: lowercase)
- comercialspecies (DB has: comercialspecies_upper, comercialspecies_lower)

### ⚠️ New Fields in v10 (Need to Add)
These fields are in CONTEXT.md but NOT in current database:

1. **SBTN_LandCover** - Science-Based Targets Network land cover classification
2. **Globi_pollinatedBy** - GloBI interaction: species that pollinate this tree
3. **Globi_eatenBy** - GloBI interaction: species that eat this tree
4. **Globi_flowersVisitedBy** - GloBI interaction: species that visit flowers
5. **Globi_hasParasite** - GloBI interaction: parasites of this species
6. **Globi_hasPathogen** - GloBI interaction: pathogens affecting this species
7. **Globi_hasDispersalVector** - GloBI interaction: seed dispersal agents
8. **Globi_preyedUponBy** - GloBI interaction: predators
9. **Globi_hasParasitoid** - GloBI interaction: parasitoids

### 🔍 Case Sensitivity Note
CONTEXT.md uses different capitalization for some fields:
- `Soil_texture_all` vs DB: `soil_texture_all`
- `pH_all` vs DB: `ph_all`
- `OC_all` vs DB: `oc_all`
- `Present_Intact_Forest` vs DB: `present_intact_forest`
- `ComercialSpecies` vs DB: `comercialspecies_upper`, `comercialspecies_lower`

**Decision**: Keep database lowercase convention, map during CSV import.

## Critical Data Preservation

### 🔐 Must Preserve (21 NFTs across 19 species)
```sql
SELECT taxon_id, COUNT(*) as nft_count
FROM contreebution_nfts
GROUP BY taxon_id;
```

**Strategy**:
- Use `UPDATE` statements instead of truncate/reload
- Match on `taxon_id` which should remain stable
- Preserve `researched` flag, `ipfs_cid` for researched species

### 📊 Current Database Stats
- Total species: 67,743
- Researched species: 19 (tracked via contreebution_nfts)
- Total NFTs: 21
- Total users: 8
- Images linked: 17,276

## Migration Strategy

### Phase 1: Schema Update (ADD columns only)
```sql
ALTER TABLE species
  ADD COLUMN IF NOT EXISTS sbtn_landcover TEXT,
  ADD COLUMN IF NOT EXISTS globi_pollinatedby TEXT,
  ADD COLUMN IF NOT EXISTS globi_eatenby TEXT,
  ADD COLUMN IF NOT EXISTS globi_flowersvisitedby TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasparasite TEXT,
  ADD COLUMN IF NOT EXISTS globi_haspathogen TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasdispersalvector TEXT,
  ADD COLUMN IF NOT EXISTS globi_preyeduponby TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasparasitoid TEXT;
```

### Phase 2: Backup Critical Data
```sql
-- Create backup table for researched species
CREATE TABLE species_backup_researched AS
SELECT * FROM species WHERE taxon_id IN (
  SELECT DISTINCT taxon_id FROM contreebution_nfts
);
```

### Phase 3: CSV Import Strategy
**Method**: UPDATE existing rows by taxon_id

**Node.js Import Script Approach**:
1. Stream CSV file (1.3 GB - too large for memory)
2. For each row:
   - Map CSV column names to DB column names (handle case differences)
   - Build UPDATE statement by taxon_id
   - **Special handling**: Skip updating `ipfs_cid` and `researched` if already set
3. Batch updates in transactions (1000 rows at a time)
4. Log any taxon_ids in CSV not found in DB (new species)
5. Log any taxon_ids in DB not in CSV (potentially removed)

### Phase 4: Verification
1. Confirm all 21 NFT taxon_ids still have correct data
2. Check that `researched` flag preserved for 19 species
3. Verify new GloBI fields populated
4. Count total species before/after
5. Spot-check sample species for data integrity

### Phase 5: Frontend Updates
**TypeScript Interface Updates**:
- Add new fields to `Species` interface in `/frontend/lib/types.ts`
- Update API response types

**UI Component Updates**:
- Species detail pages: Display GloBI ecological interactions
- Create new "Ecological Interactions" section
- Update "Conservation" section with SBTN land cover data
- Update search/filter logic if needed

## Risk Assessment

### 🔴 High Risk
- Overwriting `ipfs_cid` for researched species (MITIGATED: Skip in UPDATE)
- Losing researched flags (MITIGATED: Backup + conditional UPDATE)
- Memory issues with 1.3GB CSV (MITIGATED: Streaming import)

### 🟡 Medium Risk
- taxon_id mismatches between v10 and current DB
- New species in v10 not in current DB (INSERT needed)
- Species removed in v10 (orphaned data)

### 🟢 Low Risk
- Schema changes (additive only, no drops)
- Image links (separate table, unaffected)
- Geohash tiles (separate table, unaffected)

## Rollback Plan

1. Database backup before migration:
   ```bash
   pg_dump -U tree_user -d treekipedia > treekipedia_pre_v10_backup.sql
   ```

2. If migration fails:
   ```bash
   psql -U tree_user -d treekipedia < treekipedia_pre_v10_backup.sql
   ```

## Success Criteria

✅ All 67,743+ species updated with v10 data
✅ 19 researched species retain their research data
✅ 21 NFTs still link to correct species
✅ All 17,276 image links preserved
✅ New GloBI fields populated
✅ Frontend displays new data correctly
✅ No downtime for production site
