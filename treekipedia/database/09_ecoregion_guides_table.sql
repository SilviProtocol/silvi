-- Ecoregion Guides Table
-- Stores LLM-synthesized reforestation guide content per ecoregion

CREATE TABLE IF NOT EXISTS ecoregion_guides (
  eco_id NUMERIC PRIMARY KEY,
  overview_intro TEXT,
  planting_strategy TEXT,
  climate_context TEXT,
  conservation_notes TEXT,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  model_used VARCHAR(100),
  synthesis_version INTEGER DEFAULT 1,
  species_count INTEGER,
  source_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_ecoregion_guides_generated_at ON ecoregion_guides(generated_at);
