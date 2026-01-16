-- ============================================================================
-- Migration 07: Research Versioning & Token Tracking
-- Created: 2026-01-05
-- Purpose: Add versioning columns for Claude research agent system
-- ============================================================================

-- Add research versioning columns to species table
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_version INTEGER DEFAULT 0;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_date TIMESTAMP;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_agent TEXT;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_confidence REAL;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_sources JSONB;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_flags JSONB;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_token_cost REAL;

-- Add comment for clarity
COMMENT ON COLUMN species.research_version IS 'Version number: 0=unresearched, 1+=Claude researched';
COMMENT ON COLUMN species.research_date IS 'Timestamp of last research completion';
COMMENT ON COLUMN species.research_agent IS 'Agent that performed research (e.g., claude-haiku-3.5)';
COMMENT ON COLUMN species.research_confidence IS 'Overall confidence score 0.0-1.0';
COMMENT ON COLUMN species.research_sources IS 'JSON array of sources with citations';
COMMENT ON COLUMN species.research_flags IS 'JSON array of QC flags/issues';
COMMENT ON COLUMN species.research_token_cost IS 'Total token cost in USD for this research';

-- Create research history table for audit trail
CREATE TABLE IF NOT EXISTS research_history (
  id SERIAL PRIMARY KEY,
  taxon_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  field_name TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  agent TEXT,
  model TEXT,
  confidence REAL,
  source TEXT,
  changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  changed_by TEXT DEFAULT 'claude-research-agent'
);

-- Create indexes for research tracking
CREATE INDEX IF NOT EXISTS idx_species_research_version ON species(research_version);
CREATE INDEX IF NOT EXISTS idx_species_research_date ON species(research_date);
CREATE INDEX IF NOT EXISTS idx_species_research_confidence ON species(research_confidence);
CREATE INDEX IF NOT EXISTS idx_research_history_taxon ON research_history(taxon_id);
CREATE INDEX IF NOT EXISTS idx_research_history_version ON research_history(taxon_id, version);
CREATE INDEX IF NOT EXISTS idx_research_history_field ON research_history(field_name);

-- Create token usage tracking table (PostgreSQL version)
CREATE TABLE IF NOT EXISTS research_token_usage (
  id SERIAL PRIMARY KEY,
  taxon_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cache_read_tokens INTEGER DEFAULT 0,
  cache_write_tokens INTEGER DEFAULT 0,
  cost_usd REAL NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_token_usage_taxon ON research_token_usage(taxon_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON research_token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_date ON research_token_usage(created_at);

-- Create research queue table (PostgreSQL version for backup/sync with SQLite)
CREATE TABLE IF NOT EXISTS research_queue (
  id SERIAL PRIMARY KEY,
  taxon_id TEXT UNIQUE NOT NULL,
  species_name TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  priority INTEGER DEFAULT 50,
  queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_research_queue_status ON research_queue(status);
CREATE INDEX IF NOT EXISTS idx_research_queue_priority ON research_queue(priority DESC);

-- Create aggregation view for token usage summary
CREATE OR REPLACE VIEW research_token_summary AS
SELECT
  taxon_id,
  SUM(input_tokens) as total_input,
  SUM(output_tokens) as total_output,
  SUM(cost_usd) as total_cost,
  COUNT(DISTINCT agent_name) as agents_used,
  MIN(created_at) as first_call,
  MAX(created_at) as last_call
FROM research_token_usage
GROUP BY taxon_id;

-- Create research progress view
CREATE OR REPLACE VIEW research_progress AS
SELECT
  COUNT(*) as total_species,
  COUNT(*) FILTER (WHERE research_version = 0) as unresearched,
  COUNT(*) FILTER (WHERE research_version >= 1) as researched,
  COUNT(*) FILTER (WHERE research_version >= 1 AND research_confidence >= 0.8) as high_confidence,
  COUNT(*) FILTER (WHERE research_version >= 1 AND research_confidence < 0.5) as low_confidence,
  ROUND(AVG(research_confidence) FILTER (WHERE research_version >= 1)::numeric, 3) as avg_confidence,
  ROUND(SUM(research_token_cost)::numeric, 2) as total_cost_usd
FROM species;

-- Function to track field changes in history
CREATE OR REPLACE FUNCTION track_research_changes()
RETURNS TRIGGER AS $$
DECLARE
  field_name TEXT;
  old_val TEXT;
  new_val TEXT;
  ai_fields TEXT[] := ARRAY[
    'general_description_ai', 'habitat_ai', 'elevation_ranges_ai',
    'ecological_function_ai', 'native_adapted_habitats_ai', 'conservation_status_ai',
    'compatible_soil_types_ai', 'agroforestry_use_cases_ai',
    'growth_form_ai', 'leaf_type_ai', 'deciduous_evergreen_ai',
    'flower_color_ai', 'fruit_type_ai', 'bark_characteristics_ai',
    'maximum_height_ai', 'maximum_diameter_ai', 'lifespan_ai', 'maximum_tree_age_ai',
    'stewardship_best_practices_ai', 'planting_recipes_ai', 'pruning_maintenance_ai',
    'disease_pest_management_ai', 'fire_management_ai', 'cultural_significance_ai'
  ];
BEGIN
  -- Only track if research_version increased
  IF NEW.research_version > OLD.research_version THEN
    FOREACH field_name IN ARRAY ai_fields LOOP
      EXECUTE format('SELECT ($1).%I, ($2).%I', field_name, field_name)
        INTO old_val, new_val
        USING OLD, NEW;

      IF old_val IS DISTINCT FROM new_val THEN
        INSERT INTO research_history (
          taxon_id, version, field_name, old_value, new_value,
          agent, confidence, changed_by
        ) VALUES (
          NEW.taxon_id, NEW.research_version, field_name, old_val, new_val,
          NEW.research_agent, NEW.research_confidence, 'claude-research-agent'
        );
      END IF;
    END LOOP;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic history tracking
DROP TRIGGER IF EXISTS trg_track_research_changes ON species;
CREATE TRIGGER trg_track_research_changes
  AFTER UPDATE ON species
  FOR EACH ROW
  EXECUTE FUNCTION track_research_changes();

-- Verify migration
DO $$
BEGIN
  RAISE NOTICE 'Migration 07 completed: Research versioning schema added';
  RAISE NOTICE 'New columns: research_version, research_date, research_agent, research_confidence, research_sources, research_flags, research_token_cost';
  RAISE NOTICE 'New tables: research_history, research_token_usage, research_queue';
  RAISE NOTICE 'New views: research_token_summary, research_progress';
END $$;
