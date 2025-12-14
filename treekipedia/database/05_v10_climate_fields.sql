-- Treekipedia v10 Climate Fields Migration
-- Migration Date: November 16, 2025
-- Purpose: Add climate-related fields discovered in v10 CSV

-- These fields were not in CONTEXT.md but exist in the actual CSV data
-- Climate data appears to be Köppen-Geiger climate classification and precipitation metrics

BEGIN;

-- Add new climate-related fields
ALTER TABLE public.species
  ADD COLUMN IF NOT EXISTS climate_type_koppengeiger TEXT,
  ADD COLUMN IF NOT EXISTS annual_temperature_range_c NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS annual_precipitation_mm NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS wettest_month_precipitation_mm NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS driest_month_precipitation_mm NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS precipitation_seasonality_cv NUMERIC(10,4),
  ADD COLUMN IF NOT EXISTS wettest_quarter_precipitation_mm NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS driest_quarter_precipitation_mm NUMERIC(10,2);

-- Add comments for documentation
COMMENT ON COLUMN public.species.climate_type_koppengeiger IS 'Köppen-Geiger climate classification for species distribution';
COMMENT ON COLUMN public.species.annual_temperature_range_c IS 'Annual temperature range in Celsius';
COMMENT ON COLUMN public.species.annual_precipitation_mm IS 'Annual precipitation in millimeters';
COMMENT ON COLUMN public.species.wettest_month_precipitation_mm IS 'Precipitation in wettest month (mm)';
COMMENT ON COLUMN public.species.driest_month_precipitation_mm IS 'Precipitation in driest month (mm)';
COMMENT ON COLUMN public.species.precipitation_seasonality_cv IS 'Precipitation seasonality coefficient of variation';
COMMENT ON COLUMN public.species.wettest_quarter_precipitation_mm IS 'Precipitation in wettest quarter (mm)';
COMMENT ON COLUMN public.species.driest_quarter_precipitation_mm IS 'Precipitation in driest quarter (mm)';

-- Create index for climate type queries
CREATE INDEX IF NOT EXISTS idx_species_climate_type ON public.species(climate_type_koppengeiger);

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
        'climate_type_koppengeiger',
        'annual_temperature_range_c',
        'annual_precipitation_mm',
        'wettest_month_precipitation_mm',
        'driest_month_precipitation_mm',
        'precipitation_seasonality_cv',
        'wettest_quarter_precipitation_mm',
        'driest_quarter_precipitation_mm'
    );

    IF column_count = 8 THEN
        RAISE NOTICE '✅ Migration successful: All 8 climate fields added to species table';
    ELSE
        RAISE WARNING '⚠️ Migration incomplete: Only % of 8 columns found', column_count;
    END IF;
END $$;

-- Display current column count
SELECT COUNT(*) as total_columns
FROM information_schema.columns
WHERE table_name = 'species';
