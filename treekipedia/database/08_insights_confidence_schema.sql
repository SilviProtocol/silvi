-- Migration: Add evidence-based confidence tracking to insights table
-- Date: 2026-01-06
-- Purpose: Support cross-reference metadata and transparent confidence scoring

-- Add corroboration metadata (tracks source agreement)
ALTER TABLE insights
ADD COLUMN IF NOT EXISTS corroboration JSONB;

COMMENT ON COLUMN insights.corroboration IS 'Source agreement metadata: {sources_agree, agreement_note, cross_referenced, conflicting_info}';

-- Add confidence breakdown for transparency
ALTER TABLE insights
ADD COLUMN IF NOT EXISTS confidence_breakdown JSONB;

COMMENT ON COLUMN insights.confidence_breakdown IS 'How confidence was calculated: {source_score, agreement_score, specificity_score, methodology}';

-- Example corroboration structure:
-- {
--   "sources_agree": true,
--   "agreement_note": "Both IUCN and GBIF report Least Concern status",
--   "cross_referenced": ["IUCN Red List", "GBIF"],
--   "conflicting_info": null
-- }

-- Example confidence_breakdown structure:
-- {
--   "source_score": 0.92,
--   "agreement_score": 0.85,
--   "specificity_score": 0.88,
--   "source_count": 3,
--   "source_diversity": 2,
--   "methodology": "evidence-based: source_score × 50% + agreement × 25% + specificity × 25%"
-- }

-- Create index for querying by corroboration
CREATE INDEX IF NOT EXISTS idx_insights_corroboration
ON insights USING GIN (corroboration)
WHERE is_current = TRUE;

-- Create partial index for low-confidence insights (for review queue)
CREATE INDEX IF NOT EXISTS idx_insights_low_confidence
ON insights (taxon_id, claim_type, confidence)
WHERE is_current = TRUE AND confidence < 0.70;

-- View for insights needing review (low confidence or no corroboration)
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

-- Summary stats view
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

-- Function to recalculate confidence for an insight based on sources
-- This can be called when sources are updated
CREATE OR REPLACE FUNCTION recalculate_insight_confidence(insight_id UUID)
RETURNS JSONB AS $$
DECLARE
    source_count INTEGER;
    source_diversity INTEGER;
    avg_credibility NUMERIC;
    source_score NUMERIC;
    agreement_score NUMERIC;
    final_confidence NUMERIC;
    result JSONB;
BEGIN
    -- Get source statistics
    SELECT
        jsonb_array_length(sources),
        (SELECT COUNT(DISTINCT s->>'type') FROM jsonb_array_elements(sources) s),
        (SELECT AVG((s->>'credibility')::numeric) FROM jsonb_array_elements(sources) s)
    INTO source_count, source_diversity, avg_credibility
    FROM insights WHERE id = insight_id;

    -- Calculate source score (similar to Python calculator)
    IF source_count = 0 THEN
        source_score := 0.30;
    ELSE
        -- Base: average credibility with count multiplier
        source_score := LEAST(0.98,
            COALESCE(avg_credibility, 0.5) * (1.0 + LEAST(0.18, (source_count - 1) * 0.06))
            + LEAST(0.10, (source_diversity - 1) * 0.03)
        );
    END IF;

    -- Agreement score based on source count
    IF source_count >= 3 THEN
        agreement_score := 0.95;
    ELSIF source_count = 2 THEN
        agreement_score := 0.85;
    ELSE
        agreement_score := 0.70;
    END IF;

    -- Final weighted calculation (source 50%, agreement 25%, specificity 25%)
    -- Specificity would need claim analysis, default to 0.80
    final_confidence := ROUND(
        source_score * 0.50 + agreement_score * 0.25 + 0.80 * 0.25
    , 2);

    -- Build result
    result := jsonb_build_object(
        'source_score', ROUND(source_score::numeric, 2),
        'agreement_score', ROUND(agreement_score::numeric, 2),
        'specificity_score', 0.80,
        'source_count', source_count,
        'source_diversity', source_diversity,
        'methodology', 'database-calculated: source_score × 50% + agreement × 25% + specificity × 25%'
    );

    -- Update the insight
    UPDATE insights
    SET
        confidence = final_confidence,
        confidence_breakdown = result
    WHERE id = insight_id;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Batch recalculate all insights (run once after migration)
-- DO $$
-- DECLARE
--     insight_record RECORD;
-- BEGIN
--     FOR insight_record IN SELECT id FROM insights WHERE is_current = TRUE LOOP
--         PERFORM recalculate_insight_confidence(insight_record.id);
--     END LOOP;
-- END $$;

SELECT 'Migration 08_insights_confidence_schema.sql completed' as status;
