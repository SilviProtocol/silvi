-- 08_insights_schema.sql
-- FAIR-Compliant Knowledge Storage for Treekipedia
-- Created: January 6, 2026
-- Purpose: Store research as atomic insights with provenance, sources, and confidence
-- Requires: 07_research_versioning.sql must be run first

-- Enable UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- INSIGHTS TABLE: Atomic units of knowledge
-- ============================================================================
-- Each insight is a single claim about a species with full provenance.
-- This enables:
--   1. Source citations (FAIR principle)
--   2. Confidence tracking per claim
--   3. Re-research with version history
--   4. Multi-model comparison
--
-- VERSIONING: Each insight has a `version` that matches species.research_version
-- at creation time. When re-researching, old insights are marked is_current=FALSE
-- and new insights link via `supersedes` UUID.
-- ============================================================================

CREATE TABLE IF NOT EXISTS insights (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to species (no FK constraint due to duplicate taxon_id in species table)
    -- TODO: Add FK constraint after deduplicating species table
    taxon_id VARCHAR(50) NOT NULL,

    -- The claim
    claim_type VARCHAR(100) NOT NULL,  -- e.g., 'maximum_height', 'habitat', 'conservation_status'
    claim_value JSONB NOT NULL,         -- Flexible structure: {"value": 40, "unit": "meters"} or {"text": "..."}

    -- Confidence and quality
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    methodology VARCHAR(50),            -- 'extraction', 'inference', 'observation', 'expert_opinion'

    -- Provenance (FAIR: Findable, Accessible, Interoperable, Reusable)
    sources JSONB,                      -- Array of source objects (see below)
    model_version VARCHAR(100),         -- e.g., 'claude-3-haiku-20240307', 'claude-3-5-sonnet-20241022'
    agent_type VARCHAR(50),             -- 'identity', 'ecological', 'morphological', 'stewardship', 'synthesis', 'qc'

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Versioning (linked to species.research_version from 07_research_versioning.sql)
    version INTEGER NOT NULL DEFAULT 1,       -- Matches species.research_version when created
    supersedes UUID REFERENCES insights(id),  -- Previous insight this replaces (for re-research)
    is_current BOOLEAN DEFAULT TRUE,          -- FALSE when superseded by newer insight
    research_session_id VARCHAR(100),         -- Groups insights from same research run

    -- Cost tracking
    token_cost JSONB                          -- {"input": 500, "output": 200, "cost_usd": 0.002}
);

-- ============================================================================
-- SOURCE OBJECT SCHEMA (for sources JSONB field)
-- ============================================================================
-- Each source in the array should follow this structure:
-- {
--     "url": "https://example.com/species/quercus-robur",
--     "title": "Flora of Europe - Quercus robur",
--     "type": "database|paper|book|website|observation",
--     "doi": "10.1234/example",           -- optional
--     "authors": ["Smith, J.", "Doe, A."], -- optional
--     "year": 2023,                        -- optional
--     "accessed_date": "2026-01-06",
--     "credibility": 0.9,                  -- 0.0-1.0
--     "quote": "Maximum height reaches 40m" -- optional, relevant excerpt
-- }
-- ============================================================================

-- ============================================================================
-- INDEXES for performance
-- ============================================================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_insights_taxon ON insights(taxon_id);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(claim_type);
CREATE INDEX IF NOT EXISTS idx_insights_current ON insights(is_current) WHERE is_current = TRUE;

-- Compound index for common query pattern
CREATE INDEX IF NOT EXISTS idx_insights_taxon_type_current ON insights(taxon_id, claim_type, is_current)
    WHERE is_current = TRUE;

-- For finding insights by model/agent
CREATE INDEX IF NOT EXISTS idx_insights_model ON insights(model_version);
CREATE INDEX IF NOT EXISTS idx_insights_agent ON insights(agent_type);

-- For re-research candidates (low confidence)
CREATE INDEX IF NOT EXISTS idx_insights_confidence ON insights(confidence) WHERE is_current = TRUE;

-- For session grouping
CREATE INDEX IF NOT EXISTS idx_insights_session ON insights(research_session_id);

-- For version queries
CREATE INDEX IF NOT EXISTS idx_insights_version ON insights(taxon_id, version);

-- GIN index for JSONB source search
CREATE INDEX IF NOT EXISTS idx_insights_sources ON insights USING GIN(sources);

-- ============================================================================
-- CLAIM_TYPES reference (for documentation, not enforced)
-- ============================================================================
-- Identity (4):
--   popular_common_name, etymology, synonyms, identification_features
--
-- Ecological (10):
--   general_description, habitat, elevation_ranges, ecological_function,
--   native_adapted_habitats, conservation_status, compatible_soil_types,
--   climate_tolerance, tolerances, associated_species
--
-- Morphological (10):
--   growth_form, leaf_type, deciduous_evergreen, flower_color, fruit_type,
--   bark_characteristics, maximum_height, maximum_diameter, lifespan, maximum_tree_age
--
-- Stewardship (11):
--   stewardship_best_practices, planting_recipes, pruning_maintenance,
--   disease_pest_management, fire_management, propagation_methods,
--   cultural_significance, agroforestry_use_cases, timber_value,
--   non_timber_products, nutritional_caloric_value
-- ============================================================================

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get current insights for a species as JSONB object
CREATE OR REPLACE FUNCTION get_species_insights(p_taxon_id VARCHAR)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_object_agg(claim_type, jsonb_build_object(
        'value', claim_value,
        'confidence', confidence,
        'sources', sources,
        'model', model_version,
        'updated_at', updated_at
    ))
    INTO result
    FROM insights
    WHERE taxon_id = p_taxon_id AND is_current = TRUE;

    RETURN COALESCE(result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;

-- Function to supersede an insight (for re-research)
-- Gets the current species.research_version for the new insight's version
CREATE OR REPLACE FUNCTION supersede_insight(
    p_old_insight_id UUID,
    p_new_claim_value JSONB,
    p_new_confidence FLOAT,
    p_new_sources JSONB,
    p_new_model VARCHAR,
    p_agent_type VARCHAR DEFAULT NULL,
    p_methodology VARCHAR DEFAULT 'extraction',
    p_session_id VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_taxon_id VARCHAR;
    v_claim_type VARCHAR;
    v_new_version INTEGER;
    v_new_id UUID;
BEGIN
    -- Get info from old insight
    SELECT taxon_id, claim_type INTO v_taxon_id, v_claim_type
    FROM insights WHERE id = p_old_insight_id;

    -- Get current research_version from species table
    SELECT COALESCE(research_version, 0) + 1 INTO v_new_version
    FROM species WHERE taxon_id = v_taxon_id;

    -- Mark old as not current
    UPDATE insights SET is_current = FALSE, updated_at = NOW()
    WHERE id = p_old_insight_id;

    -- Create new insight with version
    INSERT INTO insights (
        taxon_id, claim_type, claim_value, confidence, sources,
        model_version, agent_type, methodology, version, supersedes, research_session_id
    )
    VALUES (
        v_taxon_id, v_claim_type, p_new_claim_value, p_new_confidence, p_new_sources,
        p_new_model, p_agent_type, p_methodology, v_new_version, p_old_insight_id, p_session_id
    )
    RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$ LANGUAGE plpgsql;

-- Function to create a new insight (first research or new claim type)
CREATE OR REPLACE FUNCTION create_insight(
    p_taxon_id VARCHAR,
    p_claim_type VARCHAR,
    p_claim_value JSONB,
    p_confidence FLOAT,
    p_sources JSONB,
    p_model_version VARCHAR,
    p_agent_type VARCHAR DEFAULT NULL,
    p_methodology VARCHAR DEFAULT 'extraction',
    p_session_id VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_version INTEGER;
    v_new_id UUID;
BEGIN
    -- Get current research_version from species table (or 1 if first research)
    SELECT COALESCE(research_version, 0) + 1 INTO v_version
    FROM species WHERE taxon_id = p_taxon_id;

    -- If species not found, default to version 1
    IF v_version IS NULL THEN
        v_version := 1;
    END IF;

    -- Create the insight
    INSERT INTO insights (
        taxon_id, claim_type, claim_value, confidence, sources,
        model_version, agent_type, methodology, version, research_session_id
    )
    VALUES (
        p_taxon_id, p_claim_type, p_claim_value, p_confidence, p_sources,
        p_model_version, p_agent_type, p_methodology, v_version, p_session_id
    )
    RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Aggregate insights back to flat fields (for backward compatibility)
-- ============================================================================

CREATE OR REPLACE VIEW species_insights_flat AS
SELECT
    taxon_id,
    MAX(CASE WHEN claim_type = 'general_description' THEN claim_value->>'text' END) as general_description_insight,
    MAX(CASE WHEN claim_type = 'habitat' THEN claim_value->>'text' END) as habitat_insight,
    MAX(CASE WHEN claim_type = 'maximum_height' THEN (claim_value->>'value')::TEXT END) as maximum_height_insight,
    MAX(CASE WHEN claim_type = 'conservation_status' THEN claim_value->>'text' END) as conservation_status_insight,
    -- Add more fields as needed
    COUNT(*) as insight_count,
    AVG(confidence) as avg_confidence,
    MAX(updated_at) as last_updated
FROM insights
WHERE is_current = TRUE
GROUP BY taxon_id;

-- ============================================================================
-- TRIGGER: Update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_insight_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_insight_timestamp ON insights;
CREATE TRIGGER trigger_insight_timestamp
    BEFORE UPDATE ON insights
    FOR EACH ROW
    EXECUTE FUNCTION update_insight_timestamp();

-- ============================================================================
-- STATISTICS VIEW: Research progress tracking (insights-based)
-- ============================================================================
-- Note: This view is named insights_progress to avoid conflict with
-- research_progress view from 07_research_versioning.sql

CREATE OR REPLACE VIEW insights_progress AS
SELECT
    COUNT(DISTINCT taxon_id) as species_with_insights,
    COUNT(*) as total_insights,
    COUNT(DISTINCT claim_type) as unique_claim_types,
    AVG(confidence) as avg_confidence,
    COUNT(*) FILTER (WHERE confidence >= 0.8) as high_confidence_count,
    COUNT(*) FILTER (WHERE confidence < 0.5) as low_confidence_count,
    COUNT(DISTINCT model_version) as models_used,
    COUNT(DISTINCT version) as versions_created,
    MAX(version) as latest_version,
    MIN(created_at) as first_research,
    MAX(created_at) as latest_research
FROM insights
WHERE is_current = TRUE;

-- ============================================================================
-- VIEW: Insight version history for a species
-- ============================================================================

CREATE OR REPLACE VIEW insight_version_history AS
SELECT
    i.taxon_id,
    i.claim_type,
    i.version,
    i.claim_value,
    i.confidence,
    i.model_version,
    i.is_current,
    i.created_at,
    i.supersedes,
    s.species_scientific_name
FROM insights i
JOIN species s ON i.taxon_id = s.taxon_id
ORDER BY i.taxon_id, i.claim_type, i.version DESC;

-- ============================================================================
-- GRANT PERMISSIONS (adjust as needed for your setup)
-- ============================================================================
-- GRANT SELECT, INSERT, UPDATE ON insights TO treekipedia_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO treekipedia_app;

-- ============================================================================
-- DONE
-- ============================================================================
-- Run with: psql treekipedia < 08_insights_schema.sql
-- Verify with: SELECT * FROM research_progress;
