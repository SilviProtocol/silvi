-- ============================================================================
-- Atomic Insights Architecture Migration
-- ============================================================================
--
-- This migration updates the system to support multiple atomic insights per
-- claim_type, with proper aggregation to species._ai columns.
--
-- Key changes:
-- 1. Add insight_hash for deduplication
-- 2. Create aggregation functions for each field type
-- 3. Create sync triggers to populate species._ai columns
-- 4. Add views for common queries
--
-- Run: psql treekipedia -f 08_atomic_insights_architecture.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD INSIGHT HASH FOR DEDUPLICATION
-- ============================================================================
-- Prevents storing duplicate insights (same claim for same species)

ALTER TABLE insights ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

-- Generate hash from taxon_id + claim_type + claim_value
CREATE OR REPLACE FUNCTION generate_insight_hash(
    p_taxon_id VARCHAR,
    p_claim_type VARCHAR,
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

-- Add unique constraint on hash (prevents exact duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_insights_content_hash
ON insights(content_hash)
WHERE is_current = TRUE;

-- Trigger to auto-generate hash on insert
CREATE OR REPLACE FUNCTION set_insight_hash() RETURNS TRIGGER AS $$
BEGIN
    NEW.content_hash := generate_insight_hash(NEW.taxon_id, NEW.claim_type, NEW.claim_value);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_set_insight_hash ON insights;
CREATE TRIGGER tr_set_insight_hash
    BEFORE INSERT OR UPDATE ON insights
    FOR EACH ROW
    EXECUTE FUNCTION set_insight_hash();

-- ============================================================================
-- 2. AGGREGATION FUNCTIONS BY FIELD TYPE
-- ============================================================================

-- 2a. TEXT AGGREGATION (for fields like cultural_significance, habitat)
-- Combines multiple insights into bullet points, ordered by confidence
CREATE OR REPLACE FUNCTION aggregate_text_insights(
    p_taxon_id VARCHAR,
    p_claim_type VARCHAR
) RETURNS TEXT AS $$
DECLARE
    result TEXT;
BEGIN
    SELECT string_agg(
        COALESCE(claim_value->>'text', claim_value::text),
        E'\n\n• '
        ORDER BY confidence DESC NULLS LAST
    )
    INTO result
    FROM insights
    WHERE taxon_id = p_taxon_id
      AND claim_type = p_claim_type
      AND is_current = TRUE;

    IF result IS NOT NULL THEN
        result := '• ' || result;
    END IF;

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

-- 2b. RANKED LIST AGGREGATION (for common names, synonyms)
-- Returns semicolon-separated list ordered by rank
CREATE OR REPLACE FUNCTION aggregate_ranked_insights(
    p_taxon_id VARCHAR,
    p_claim_type VARCHAR,
    p_name_field VARCHAR DEFAULT 'name'
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

-- 2c. HIGHEST CONFIDENCE SINGLE VALUE (for fields like conservation_status)
-- Returns the single highest-confidence value
CREATE OR REPLACE FUNCTION aggregate_top_insight(
    p_taxon_id VARCHAR,
    p_claim_type VARCHAR
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

-- 2d. PRIMARY NAME (highest ranked common name)
CREATE OR REPLACE FUNCTION get_primary_common_name(
    p_taxon_id VARCHAR
) RETURNS TEXT AS $$
BEGIN
    RETURN (
        SELECT claim_value->>'name'
        FROM insights
        WHERE taxon_id = p_taxon_id
          AND claim_type = 'popular_common_name'
          AND is_current = TRUE
        ORDER BY (claim_value->>'rank')::int NULLS LAST, confidence DESC
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 3. MASTER SYNC FUNCTION: insights -> species._ai columns
-- ============================================================================

CREATE OR REPLACE FUNCTION sync_insights_to_species(p_taxon_id VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE species SET
        -- Identity fields
        popular_common_name_ai = aggregate_ranked_insights(p_taxon_id, 'popular_common_name', 'name'),
        etymology_ai = (aggregate_top_insight(p_taxon_id, 'etymology'))->>'text',
        synonyms_ai = aggregate_ranked_insights(p_taxon_id, 'synonyms', 'name'),
        identification_features_ai = aggregate_text_insights(p_taxon_id, 'identification_features'),

        -- Ecological fields
        general_description_ai = aggregate_text_insights(p_taxon_id, 'general_description'),
        habitat_ai = aggregate_text_insights(p_taxon_id, 'habitat'),
        elevation_ranges_ai = (aggregate_top_insight(p_taxon_id, 'elevation_ranges'))->>'text',
        ecological_function_ai = aggregate_text_insights(p_taxon_id, 'ecological_function'),
        native_adapted_habitats_ai = aggregate_text_insights(p_taxon_id, 'native_adapted_habitats'),
        conservation_status_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'conservation_status'))->>'iucn_status',
            (aggregate_top_insight(p_taxon_id, 'conservation_status'))->>'text'
        ),
        compatible_soil_types_ai = aggregate_text_insights(p_taxon_id, 'compatible_soil_types'),
        climate_tolerance_ai = aggregate_text_insights(p_taxon_id, 'climate_tolerance'),
        tolerances_ai = aggregate_text_insights(p_taxon_id, 'tolerances'),
        associated_species_ai = aggregate_text_insights(p_taxon_id, 'associated_species'),

        -- Morphological fields
        growth_form_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'growth_form'))->>'primary',
            (aggregate_top_insight(p_taxon_id, 'growth_form'))->>'text'
        ),
        leaf_type_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'leaf_type'))->>'type',
            (aggregate_top_insight(p_taxon_id, 'leaf_type'))->>'text'
        ),
        deciduous_evergreen_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'deciduous_evergreen'))->>'type',
            (aggregate_top_insight(p_taxon_id, 'deciduous_evergreen'))->>'text'
        ),
        flower_color_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'flower_color'))->>'primary',
            (aggregate_top_insight(p_taxon_id, 'flower_color'))->>'text'
        ),
        fruit_type_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'fruit_type'))->>'type',
            (aggregate_top_insight(p_taxon_id, 'fruit_type'))->>'text'
        ),
        bark_characteristics_ai = aggregate_text_insights(p_taxon_id, 'bark_characteristics'),
        maximum_height_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'maximum_height'))->>'value' || 'm',
            (aggregate_top_insight(p_taxon_id, 'maximum_height'))->>'text'
        ),
        maximum_diameter_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'maximum_diameter'))->>'value' || 'm',
            (aggregate_top_insight(p_taxon_id, 'maximum_diameter'))->>'text'
        ),
        lifespan_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'lifespan'))->>'category',
            (aggregate_top_insight(p_taxon_id, 'lifespan'))->>'text'
        ),
        maximum_tree_age_ai = COALESCE(
            (aggregate_top_insight(p_taxon_id, 'maximum_tree_age'))->>'value' || ' years',
            (aggregate_top_insight(p_taxon_id, 'maximum_tree_age'))->>'text'
        ),

        -- Stewardship fields
        stewardship_best_practices_ai = aggregate_text_insights(p_taxon_id, 'stewardship_best_practices'),
        planting_recipes_ai = aggregate_text_insights(p_taxon_id, 'planting_recipes'),
        pruning_maintenance_ai = aggregate_text_insights(p_taxon_id, 'pruning_maintenance'),
        disease_pest_management_ai = aggregate_text_insights(p_taxon_id, 'disease_pest_management'),
        fire_management_ai = aggregate_text_insights(p_taxon_id, 'fire_management'),
        propagation_methods_ai = aggregate_text_insights(p_taxon_id, 'propagation_methods'),
        cultural_significance_ai = aggregate_text_insights(p_taxon_id, 'cultural_significance'),
        agroforestry_use_cases_ai = aggregate_text_insights(p_taxon_id, 'agroforestry_use_cases'),
        timber_value_ai = aggregate_text_insights(p_taxon_id, 'timber_value'),
        non_timber_products_ai = aggregate_text_insights(p_taxon_id, 'non_timber_products'),
        nutritional_caloric_value_ai = aggregate_text_insights(p_taxon_id, 'nutritional_caloric_value'),

        -- Update research metadata
        researched = TRUE,
        updated_at = NOW()
    WHERE taxon_id = p_taxon_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. TRIGGER: Auto-sync on insight insert/update
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_sync_insights_to_species()
RETURNS TRIGGER AS $$
BEGIN
    -- Sync after insert or update
    PERFORM sync_insights_to_species(NEW.taxon_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Replace existing trigger
DROP TRIGGER IF EXISTS tr_sync_insights_on_insert ON insights;
CREATE TRIGGER tr_sync_insights_on_insert
    AFTER INSERT ON insights
    FOR EACH ROW
    EXECUTE FUNCTION trigger_sync_insights_to_species();

DROP TRIGGER IF EXISTS tr_sync_insights_on_update ON insights;
CREATE TRIGGER tr_sync_insights_on_update
    AFTER UPDATE OF claim_value, confidence, is_current ON insights
    FOR EACH ROW
    EXECUTE FUNCTION trigger_sync_insights_to_species();

-- ============================================================================
-- 5. USEFUL VIEWS
-- ============================================================================

-- View: All current insights with species name
CREATE OR REPLACE VIEW v_current_insights AS
SELECT
    i.*,
    s.species_scientific_name,
    s.family
FROM insights i
JOIN species s ON i.taxon_id = s.taxon_id
WHERE i.is_current = TRUE;

-- View: Insight counts per species
CREATE OR REPLACE VIEW v_species_insight_counts AS
SELECT
    taxon_id,
    COUNT(*) as total_insights,
    COUNT(DISTINCT claim_type) as unique_claim_types,
    AVG(confidence) as avg_confidence,
    MIN(created_at) as first_insight,
    MAX(created_at) as last_insight
FROM insights
WHERE is_current = TRUE
GROUP BY taxon_id;

-- View: Insights per claim_type (for multi-insight fields)
CREATE OR REPLACE VIEW v_multi_insight_counts AS
SELECT
    taxon_id,
    claim_type,
    COUNT(*) as insight_count,
    AVG(confidence) as avg_confidence
FROM insights
WHERE is_current = TRUE
GROUP BY taxon_id, claim_type
HAVING COUNT(*) > 1
ORDER BY insight_count DESC;

-- ============================================================================
-- 6. HELPER: Batch re-sync all species from insights
-- ============================================================================

CREATE OR REPLACE FUNCTION resync_all_species_from_insights()
RETURNS TABLE(taxon_id VARCHAR, insights_synced INTEGER) AS $$
DECLARE
    rec RECORD;
    count INTEGER;
BEGIN
    FOR rec IN
        SELECT DISTINCT i.taxon_id
        FROM insights i
        WHERE i.is_current = TRUE
    LOOP
        PERFORM sync_insights_to_species(rec.taxon_id);
        SELECT COUNT(*) INTO count
        FROM insights
        WHERE insights.taxon_id = rec.taxon_id AND is_current = TRUE;

        taxon_id := rec.taxon_id;
        insights_synced := count;
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check hash generation
-- SELECT id, taxon_id, claim_type, content_hash FROM insights LIMIT 5;

-- Test aggregation functions
-- SELECT aggregate_text_insights('GymGiGiGnKg50344-00', 'cultural_significance');
-- SELECT aggregate_ranked_insights('GymGiGiGnKg50344-00', 'popular_common_name', 'name');
-- SELECT get_primary_common_name('GymGiGiGnKg50344-00');

-- Check multi-insight counts
-- SELECT * FROM v_multi_insight_counts LIMIT 20;

-- Re-sync all (run after migration)
-- SELECT * FROM resync_all_species_from_insights();
