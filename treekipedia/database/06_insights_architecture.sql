-- ============================================================================
-- Migration 06: Insights Architecture + Research Versioning
-- Created: 2026-01-20
-- Purpose: Add atomic insights system with confidence scoring and research tracking
-- ============================================================================
--
-- This migration adds:
-- 1. Helper columns for search optimization (4 columns)
-- 2. Research versioning columns on species table (7 columns)
-- 3. Insights table for atomic knowledge storage
-- 4. Research history and token usage tracking tables
-- 5. Aggregation functions for insights -> species._ai columns
-- 6. Confidence scoring and source tracking
--
-- Run: psql treekipedia -f 06_insights_architecture.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. HELPER COLUMNS FOR SEARCH OPTIMIZATION
-- ============================================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS sci_lower TEXT;
COMMENT ON COLUMN species.sci_lower IS 'Lowercase scientific name for case-insensitive search';

ALTER TABLE species ADD COLUMN IF NOT EXISTS taxon_lower TEXT;
COMMENT ON COLUMN species.taxon_lower IS 'Lowercase taxon for case-insensitive search';

ALTER TABLE species ADD COLUMN IF NOT EXISTS taxon_full_clean TEXT;
COMMENT ON COLUMN species.taxon_full_clean IS 'Cleaned taxon_full for matching (no special chars)';

ALTER TABLE species ADD COLUMN IF NOT EXISTS comercialspecies TEXT;
COMMENT ON COLUMN species.comercialspecies IS 'Commercial species flag';

-- Populate helper columns
UPDATE species SET
  sci_lower = LOWER(species_scientific_name),
  taxon_lower = LOWER(taxon_id),
  taxon_full_clean = REGEXP_REPLACE(LOWER(taxon_full), '[^a-z0-9 ]', '', 'g')
WHERE sci_lower IS NULL;

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_species_sci_lower ON species(sci_lower);
CREATE INDEX IF NOT EXISTS idx_species_taxon_lower ON species(taxon_lower);

-- ============================================================================
-- 2. RESEARCH VERSIONING COLUMNS ON SPECIES TABLE
-- ============================================================================

ALTER TABLE species ADD COLUMN IF NOT EXISTS research_version INTEGER DEFAULT 0;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_date TIMESTAMP;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_agent TEXT;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_confidence REAL;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_sources JSONB;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_flags JSONB;
ALTER TABLE species ADD COLUMN IF NOT EXISTS research_token_cost REAL;

COMMENT ON COLUMN species.research_version IS 'Version number: 0=unresearched, 1+=AI researched';
COMMENT ON COLUMN species.research_date IS 'Timestamp of last research completion';
COMMENT ON COLUMN species.research_agent IS 'Agent that performed research (e.g., grok-4-1-fast)';
COMMENT ON COLUMN species.research_confidence IS 'Overall confidence score 0.0-1.0';
COMMENT ON COLUMN species.research_sources IS 'JSON array of sources with citations';
COMMENT ON COLUMN species.research_flags IS 'JSON array of QC flags/issues';
COMMENT ON COLUMN species.research_token_cost IS 'Total token cost in USD for this research';

-- Create indexes for research tracking
CREATE INDEX IF NOT EXISTS idx_species_research_version ON species(research_version);
CREATE INDEX IF NOT EXISTS idx_species_research_date ON species(research_date);
CREATE INDEX IF NOT EXISTS idx_species_research_confidence ON species(research_confidence);

-- ============================================================================
-- 3. INSIGHTS TABLE - ATOMIC KNOWLEDGE STORAGE
-- ============================================================================

CREATE TABLE IF NOT EXISTS insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  taxon_id TEXT NOT NULL,  -- No FK due to duplicate taxon_ids in species table
  claim_type TEXT NOT NULL,
  claim_value JSONB NOT NULL,
  confidence REAL DEFAULT 0.5,
  sources JSONB DEFAULT '[]'::jsonb,
  corroboration JSONB,
  confidence_breakdown JSONB,
  content_hash VARCHAR(64),
  research_session_id UUID,
  is_current BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE insights IS 'Atomic knowledge claims with confidence scoring';
COMMENT ON COLUMN insights.claim_type IS 'Type of claim (e.g., habitat, conservation_status, growth_form)';
COMMENT ON COLUMN insights.claim_value IS 'JSON value of the claim';
COMMENT ON COLUMN insights.confidence IS 'Confidence score 0.0-1.0';
COMMENT ON COLUMN insights.sources IS 'Array of source citations';
COMMENT ON COLUMN insights.corroboration IS 'Source agreement metadata';
COMMENT ON COLUMN insights.confidence_breakdown IS 'How confidence was calculated';
COMMENT ON COLUMN insights.content_hash IS 'SHA256 hash for deduplication';
COMMENT ON COLUMN insights.is_current IS 'Whether this is the current version';

-- Indexes for insights table
CREATE INDEX IF NOT EXISTS idx_insights_taxon_id ON insights(taxon_id);
CREATE INDEX IF NOT EXISTS idx_insights_claim_type ON insights(claim_type);
CREATE INDEX IF NOT EXISTS idx_insights_confidence ON insights(confidence);
CREATE INDEX IF NOT EXISTS idx_insights_is_current ON insights(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_insights_sources ON insights USING GIN (sources);

-- Unique constraint on content hash (prevents duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_insights_content_hash
ON insights(content_hash) WHERE is_current = TRUE;

-- ============================================================================
-- 4. RESEARCH HISTORY TABLE - AUDIT TRAIL
-- ============================================================================

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
  changed_by TEXT DEFAULT 'research-agent'
);

COMMENT ON TABLE research_history IS 'Audit trail of research changes per field';

CREATE INDEX IF NOT EXISTS idx_research_history_taxon ON research_history(taxon_id);
CREATE INDEX IF NOT EXISTS idx_research_history_version ON research_history(taxon_id, version);
CREATE INDEX IF NOT EXISTS idx_research_history_field ON research_history(field_name);

-- ============================================================================
-- 5. RESEARCH TOKEN USAGE TABLE - COST TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS research_token_usage (
  id SERIAL PRIMARY KEY,
  taxon_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER DEFAULT 0,
  cache_write_tokens INTEGER DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE research_token_usage IS 'Token consumption tracking per research operation';

CREATE INDEX IF NOT EXISTS idx_token_usage_taxon ON research_token_usage(taxon_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON research_token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_date ON research_token_usage(created_at);

-- ============================================================================
-- 6. RESEARCH QUEUE TABLE (replaces species_research_queue)
-- ============================================================================

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

COMMENT ON TABLE research_queue IS 'Queue for pending research tasks';

CREATE INDEX IF NOT EXISTS idx_research_queue_status ON research_queue(status);
CREATE INDEX IF NOT EXISTS idx_research_queue_priority ON research_queue(priority DESC);

-- ============================================================================
-- 7. HASH GENERATION FUNCTION FOR DEDUPLICATION
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_insight_hash(
  p_taxon_id TEXT,
  p_claim_type TEXT,
  p_claim_value JSONB
) RETURNS VARCHAR AS $$
BEGIN
  RETURN encode(
    sha256(
      (p_taxon_id || '::' || p_claim_type || '::' || p_claim_value::text)::bytea
    ),
    'hex'
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-generate hash on insert
CREATE OR REPLACE FUNCTION set_insight_hash() RETURNS TRIGGER AS $$
BEGIN
  NEW.content_hash := generate_insight_hash(NEW.taxon_id, NEW.claim_type, NEW.claim_value);
  NEW.updated_at := CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_set_insight_hash ON insights;
CREATE TRIGGER tr_set_insight_hash
  BEFORE INSERT OR UPDATE ON insights
  FOR EACH ROW
  EXECUTE FUNCTION set_insight_hash();

-- ============================================================================
-- 8. AGGREGATION FUNCTIONS
-- ============================================================================

-- 8a. TEXT AGGREGATION (for fields like habitat, cultural_significance)
CREATE OR REPLACE FUNCTION aggregate_text_insights(
  p_taxon_id TEXT,
  p_claim_type TEXT
) RETURNS TEXT AS $$
DECLARE
  result TEXT;
BEGIN
  SELECT string_agg(
    COALESCE(claim_value->>'text', claim_value::text),
    E'\n\n'
    ORDER BY confidence DESC NULLS LAST
  )
  INTO result
  FROM insights
  WHERE taxon_id = p_taxon_id
    AND claim_type = p_claim_type
    AND is_current = TRUE;

  RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

-- 8b. RANKED LIST AGGREGATION (for common names, synonyms)
CREATE OR REPLACE FUNCTION aggregate_ranked_insights(
  p_taxon_id TEXT,
  p_claim_type TEXT,
  p_name_field TEXT DEFAULT 'name'
) RETURNS TEXT AS $$
BEGIN
  RETURN (
    SELECT string_agg(
      claim_value->>p_name_field,
      '; '
      ORDER BY (claim_value->>'rank')::int NULLS LAST, confidence DESC
    )
    FROM insights
    WHERE taxon_id = p_taxon_id
      AND claim_type = p_claim_type
      AND is_current = TRUE
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- 8c. HIGHEST CONFIDENCE SINGLE VALUE
CREATE OR REPLACE FUNCTION aggregate_top_insight(
  p_taxon_id TEXT,
  p_claim_type TEXT
) RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT claim_value
    FROM insights
    WHERE taxon_id = p_taxon_id
      AND claim_type = p_claim_type
      AND is_current = TRUE
    ORDER BY confidence DESC NULLS LAST
    LIMIT 1
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 9. ANALYTICS VIEWS
-- ============================================================================

-- Token usage summary
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

-- Research progress overview
CREATE OR REPLACE VIEW research_progress AS
SELECT
  COUNT(*) as total_species,
  COUNT(*) FILTER (WHERE research_version = 0 OR research_version IS NULL) as unresearched,
  COUNT(*) FILTER (WHERE research_version >= 1) as researched,
  COUNT(*) FILTER (WHERE research_version >= 1 AND research_confidence >= 0.8) as high_confidence,
  COUNT(*) FILTER (WHERE research_version >= 1 AND research_confidence < 0.5) as low_confidence,
  ROUND(AVG(research_confidence) FILTER (WHERE research_version >= 1)::numeric, 3) as avg_confidence,
  ROUND(SUM(research_token_cost)::numeric, 2) as total_cost_usd
FROM species;

-- Insights needing review (low confidence or missing corroboration)
CREATE OR REPLACE VIEW insights_needing_review AS
SELECT
  i.id,
  i.taxon_id,
  s.species_scientific_name,
  i.claim_type,
  i.confidence,
  i.corroboration,
  jsonb_array_length(i.sources) as source_count,
  i.created_at
FROM insights i
LEFT JOIN species s ON i.taxon_id = s.taxon_id
WHERE i.is_current = TRUE
  AND (
    i.confidence < 0.70
    OR i.corroboration IS NULL
    OR (i.corroboration->>'sources_agree')::boolean = false
  )
ORDER BY i.confidence ASC;

-- Confidence statistics by claim type
CREATE OR REPLACE VIEW confidence_statistics AS
SELECT
  claim_type,
  COUNT(*) as total_insights,
  ROUND(AVG(confidence)::numeric, 3) as avg_confidence,
  ROUND(MIN(confidence)::numeric, 3) as min_confidence,
  ROUND(MAX(confidence)::numeric, 3) as max_confidence,
  COUNT(*) FILTER (WHERE confidence >= 0.85) as high_confidence,
  COUNT(*) FILTER (WHERE confidence >= 0.70 AND confidence < 0.85) as medium_confidence,
  COUNT(*) FILTER (WHERE confidence < 0.70) as low_confidence,
  COUNT(*) FILTER (WHERE corroboration IS NOT NULL) as has_corroboration
FROM insights
WHERE is_current = TRUE
GROUP BY claim_type
ORDER BY avg_confidence DESC;

-- ============================================================================
-- 10. VERIFICATION
-- ============================================================================

DO $$
BEGIN
  RAISE NOTICE 'Migration 06 completed successfully';
  RAISE NOTICE 'New columns on species: sci_lower, taxon_lower, taxon_full_clean, comercialspecies';
  RAISE NOTICE 'New columns on species: research_version, research_date, research_agent, research_confidence, research_sources, research_flags, research_token_cost';
  RAISE NOTICE 'New tables: insights, research_history, research_token_usage, research_queue';
  RAISE NOTICE 'New views: research_token_summary, research_progress, insights_needing_review, confidence_statistics';
END $$;

COMMIT;
