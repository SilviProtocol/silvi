-- Migration 12: Structured common names table + display_common_name column
-- Replaces messy semicolon-separated common_name blob with structured, searchable rows
-- Supports language codes, regional tagging, user contributions, and primary name flagging

-- Enable pg_trgm for fuzzy text search indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Structured common names table
CREATE TABLE IF NOT EXISTS species_common_names (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    taxon_id TEXT NOT NULL,
    name TEXT NOT NULL,
    language_code VARCHAR(10),              -- ISO 639-1: 'en', 'es', 'id', 'ja', or NULL if unknown
    region_codes TEXT[],                    -- ISO 3166-1 alpha-2: ['ID', 'MY'], or NULL if global
    source TEXT NOT NULL DEFAULT 'bulk_import',  -- 'bulk_import', 'ai_research', 'user', 'wcvp'
    is_primary BOOLEAN DEFAULT false,       -- primary name for this language+species combination
    submitted_by TEXT,                      -- user attribution for user-contributed names
    staging BOOLEAN DEFAULT false,          -- user-submitted, pending review
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_common_names_species FOREIGN KEY (taxon_id) REFERENCES species(taxon_id),
    CONSTRAINT uq_common_name_lang UNIQUE (taxon_id, name, language_code)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_common_names_taxon ON species_common_names(taxon_id);
CREATE INDEX IF NOT EXISTS idx_common_names_lang ON species_common_names(language_code);
CREATE INDEX IF NOT EXISTS idx_common_names_region ON species_common_names USING GIN(region_codes);
CREATE INDEX IF NOT EXISTS idx_common_names_search ON species_common_names USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_common_names_staging ON species_common_names(staging) WHERE staging = true;

-- Add display_common_name to species table (pre-computed best English name)
ALTER TABLE species ADD COLUMN IF NOT EXISTS display_common_name TEXT;

-- Index for searching by display name
CREATE INDEX IF NOT EXISTS idx_species_display_name ON species USING gin(display_common_name gin_trgm_ops);

-- Updated_at trigger for common names
CREATE OR REPLACE FUNCTION update_common_names_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_common_names_updated_at ON species_common_names;
CREATE TRIGGER trigger_common_names_updated_at
    BEFORE UPDATE ON species_common_names
    FOR EACH ROW
    EXECUTE FUNCTION update_common_names_updated_at();
