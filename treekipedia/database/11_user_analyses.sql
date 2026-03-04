-- User Analyses: Persistent storage for site analysis sessions
-- Migration: 11_user_analyses.sql

CREATE TABLE IF NOT EXISTS user_analyses (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  aoi_type VARCHAR(20) NOT NULL,
  aoi_geometry GEOMETRY(Polygon, 4326) NOT NULL,
  aoi_label VARCHAR(255),
  aoi_center GEOMETRY(Point, 4326),
  area_hectares DECIMAL(12,2),
  summary_data JSONB,
  prediction_data JSONB,
  recommendation_data JSONB,
  recommendation_strategy VARCHAR(30),
  ecoregion_ids INTEGER[],
  status VARCHAR(20) DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_analyses_user ON user_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_analyses_created ON user_analyses(created_at DESC);
