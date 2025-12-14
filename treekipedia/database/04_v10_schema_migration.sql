-- Treekipedia v10 Schema Migration
-- Migration Date: November 16, 2025
-- Purpose: Add new fields from v10 dataset (GloBI interactions + SBTN land cover)

-- This migration is SAFE and ADDITIVE ONLY (no data loss)
-- Adds 9 new columns to the species table

BEGIN;

-- Add new GloBI (Global Biotic Interactions) fields
-- These fields contain ecological interaction data from the GloBI database
-- Format: Text fields containing interaction data (likely JSON or comma-separated)

ALTER TABLE public.species
  ADD COLUMN IF NOT EXISTS sbtn_landcover TEXT,
  ADD COLUMN IF NOT EXISTS globi_pollinatedby TEXT,
  ADD COLUMN IF NOT EXISTS globi_eatenby TEXT,
  ADD COLUMN IF NOT EXISTS globi_flowersvisitedby TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasparasite TEXT,
  ADD COLUMN IF NOT EXISTS globi_haspathogen TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasdispersalvector TEXT,
  ADD COLUMN IF NOT EXISTS globi_preyeduponby TEXT,
  ADD COLUMN IF NOT EXISTS globi_hasparasitoid TEXT;

-- Add comments for documentation
COMMENT ON COLUMN public.species.sbtn_landcover IS 'Science-Based Targets Network land cover classification';
COMMENT ON COLUMN public.species.globi_pollinatedby IS 'GloBI: Species that pollinate this tree';
COMMENT ON COLUMN public.species.globi_eatenby IS 'GloBI: Species that consume parts of this tree';
COMMENT ON COLUMN public.species.globi_flowersvisitedby IS 'GloBI: Species that visit flowers of this tree';
COMMENT ON COLUMN public.species.globi_hasparasite IS 'GloBI: Parasites affecting this species';
COMMENT ON COLUMN public.species.globi_haspathogen IS 'GloBI: Pathogens affecting this species';
COMMENT ON COLUMN public.species.globi_hasdispersalvector IS 'GloBI: Species that disperse seeds of this tree';
COMMENT ON COLUMN public.species.globi_preyeduponby IS 'GloBI: Species that prey upon this tree';
COMMENT ON COLUMN public.species.globi_hasparasitoid IS 'GloBI: Parasitoids affecting this species';

-- Create indexes for the new fields to support search/filtering
-- Only index fields likely to be queried
CREATE INDEX IF NOT EXISTS idx_species_sbtn_landcover ON public.species(sbtn_landcover);

-- Note: GloBI fields are likely large text and not commonly filtered, so we don't index them
-- If needed later, we can add GIN indexes for text search

COMMIT;

-- Verify migration success
DO $$
DECLARE
    column_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'species'
    AND column_name IN (
        'sbtn_landcover',
        'globi_pollinatedby',
        'globi_eatenby',
        'globi_flowersvisitedby',
        'globi_hasparasite',
        'globi_haspathogen',
        'globi_hasdispersalvector',
        'globi_preyeduponby',
        'globi_hasparasitoid'
    );

    IF column_count = 9 THEN
        RAISE NOTICE '✅ Migration successful: All 9 new columns added to species table';
    ELSE
        RAISE WARNING '⚠️ Migration incomplete: Only % of 9 columns found', column_count;
    END IF;
END $$;

-- Display current column count
SELECT COUNT(*) as total_columns
FROM information_schema.columns
WHERE table_name = 'species';
