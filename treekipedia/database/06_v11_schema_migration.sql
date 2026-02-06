-- Treekipedia V11 Schema Migration
-- Date: January 2026
-- Description: Adds new columns for V11 species data import
--
-- New columns:
-- - Climate data (Köppen-Geiger, temperature, precipitation)
-- - WCVP native/introduced status (critical for LEAF scoring)
-- - GloBI ecological interactions (8 columns)
-- - SBTN Land Cover
-- - Helper columns (sci_lower, taxon_lower, taxon_full_clean)

-- =====================================================
-- Climate Data Fields
-- =====================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS climate_type_koppengeiger TEXT;
COMMENT ON COLUMN species.climate_type_koppengeiger IS 'Köppen-Geiger climate classification';

ALTER TABLE species ADD COLUMN IF NOT EXISTS annual_temperature_range_c TEXT;
COMMENT ON COLUMN species.annual_temperature_range_c IS 'Annual temperature range in Celsius';

ALTER TABLE species ADD COLUMN IF NOT EXISTS annual_precipitation_mm TEXT;
COMMENT ON COLUMN species.annual_precipitation_mm IS 'Annual precipitation in millimeters';

ALTER TABLE species ADD COLUMN IF NOT EXISTS wettest_month_precipitation_mm TEXT;
COMMENT ON COLUMN species.wettest_month_precipitation_mm IS 'Wettest month precipitation in mm';

ALTER TABLE species ADD COLUMN IF NOT EXISTS driest_month_precipitation_mm TEXT;
COMMENT ON COLUMN species.driest_month_precipitation_mm IS 'Driest month precipitation in mm';

ALTER TABLE species ADD COLUMN IF NOT EXISTS precipitation_seasonality_cv TEXT;
COMMENT ON COLUMN species.precipitation_seasonality_cv IS 'Precipitation seasonality coefficient of variation';

ALTER TABLE species ADD COLUMN IF NOT EXISTS wettest_quarter_precipitation_mm TEXT;
COMMENT ON COLUMN species.wettest_quarter_precipitation_mm IS 'Wettest quarter precipitation in mm';

ALTER TABLE species ADD COLUMN IF NOT EXISTS driest_quarter_precipitation_mm TEXT;
COMMENT ON COLUMN species.driest_quarter_precipitation_mm IS 'Driest quarter precipitation in mm';

-- =====================================================
-- WCVP Native/Introduced Status (CRITICAL for LEAF scoring)
-- =====================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS wcvp_native TEXT;
COMMENT ON COLUMN species.wcvp_native IS 'WCVP native regions (semicolon-separated WGSRPD L3 codes)';

ALTER TABLE species ADD COLUMN IF NOT EXISTS wcvp_introduced TEXT;
COMMENT ON COLUMN species.wcvp_introduced IS 'WCVP introduced regions (semicolon-separated WGSRPD L3 codes)';

-- =====================================================
-- GloBI Ecological Interactions
-- =====================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_pollinatedby TEXT;
COMMENT ON COLUMN species.globi_pollinatedby IS 'GloBI: Species that pollinate this tree';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_eatenby TEXT;
COMMENT ON COLUMN species.globi_eatenby IS 'GloBI: Species that eat this tree (herbivores)';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_flowersvisitedby TEXT;
COMMENT ON COLUMN species.globi_flowersvisitedby IS 'GloBI: Species that visit flowers';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_hasparasite TEXT;
COMMENT ON COLUMN species.globi_hasparasite IS 'GloBI: Parasites of this species';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_haspathogen TEXT;
COMMENT ON COLUMN species.globi_haspathogen IS 'GloBI: Pathogens affecting this species';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_hasdispersalvector TEXT;
COMMENT ON COLUMN species.globi_hasdispersalvector IS 'GloBI: Seed dispersal agents';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_preyeduponby TEXT;
COMMENT ON COLUMN species.globi_preyeduponby IS 'GloBI: Predators of this species';

ALTER TABLE species ADD COLUMN IF NOT EXISTS globi_hasparasitoid TEXT;
COMMENT ON COLUMN species.globi_hasparasitoid IS 'GloBI: Parasitoids of this species';

-- =====================================================
-- SBTN Land Cover
-- =====================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS sbtn_landcover TEXT;
COMMENT ON COLUMN species.sbtn_landcover IS 'Science-Based Targets Network land cover classification';

-- =====================================================
-- Helper/Index Columns
-- =====================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS sci_lower TEXT;
COMMENT ON COLUMN species.sci_lower IS 'Lowercase scientific name for case-insensitive search';

ALTER TABLE species ADD COLUMN IF NOT EXISTS taxon_lower TEXT;
COMMENT ON COLUMN species.taxon_lower IS 'Lowercase taxon for case-insensitive search';

ALTER TABLE species ADD COLUMN IF NOT EXISTS taxon_full_clean TEXT;
COMMENT ON COLUMN species.taxon_full_clean IS 'Cleaned taxon_full for matching';

-- Also add comercialspecies if not exists (different from comercialspecies_upper/lower)
ALTER TABLE species ADD COLUMN IF NOT EXISTS comercialspecies TEXT;
COMMENT ON COLUMN species.comercialspecies IS 'Commercial species flag from V11';

-- =====================================================
-- Create Indexes for WCVP columns (important for LEAF queries)
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_species_wcvp_native ON species USING GIN (to_tsvector('simple', COALESCE(wcvp_native, '')));
CREATE INDEX IF NOT EXISTS idx_species_wcvp_introduced ON species USING GIN (to_tsvector('simple', COALESCE(wcvp_introduced, '')));

-- Simple text indexes for LIKE queries
CREATE INDEX IF NOT EXISTS idx_species_wcvp_native_text ON species (wcvp_native);
CREATE INDEX IF NOT EXISTS idx_species_wcvp_introduced_text ON species (wcvp_introduced);

-- =====================================================
-- Verification Queries
-- =====================================================

-- Run these after migration to verify:
-- SELECT COUNT(*) FROM species WHERE wcvp_native IS NOT NULL;
-- SELECT COUNT(*) FROM species WHERE climate_type_koppengeiger IS NOT NULL;
-- SELECT COUNT(*) FROM species WHERE globi_eatenby IS NOT NULL;

-- =====================================================
-- Migration Complete
-- =====================================================
-- Total new columns: 23
-- - Climate: 8
-- - WCVP: 2
-- - GloBI: 8
-- - SBTN: 1
-- - Helper: 4
