-- BigQuery table schemas for AlphaEarth embeddings project
-- Following treekipedia_alpha_earth_planetary_species_predictor_builders_guide.md

-- 1. Raw occurrences staging table
CREATE TABLE IF NOT EXISTS `treekipedia-476404.alphaearth.occurrences_raw` (
  taxon_id STRING NOT NULL,
  species_scientific_name STRING,
  family STRING,
  subspecies STRING,
  latitude FLOAT64,
  longitude FLOAT64,
  year INT64,
  embedding_year INT64
);

-- 2. Raw embeddings from GEE (will be populated by Earth Engine exports)
CREATE TABLE IF NOT EXISTS `treekipedia-476404.alphaearth.occ_embeddings_raw` (
  taxon_id STRING,
  latitude FLOAT64,
  longitude FLOAT64,
  orig_year INT64,
  emb_year INT64,
  -- AlphaEarth 64-dimensional embedding
  A01 FLOAT64, A02 FLOAT64, A03 FLOAT64, A04 FLOAT64, A05 FLOAT64,
  A06 FLOAT64, A07 FLOAT64, A08 FLOAT64, A09 FLOAT64, A10 FLOAT64,
  A11 FLOAT64, A12 FLOAT64, A13 FLOAT64, A14 FLOAT64, A15 FLOAT64,
  A16 FLOAT64, A17 FLOAT64, A18 FLOAT64, A19 FLOAT64, A20 FLOAT64,
  A21 FLOAT64, A22 FLOAT64, A23 FLOAT64, A24 FLOAT64, A25 FLOAT64,
  A26 FLOAT64, A27 FLOAT64, A28 FLOAT64, A29 FLOAT64, A30 FLOAT64,
  A31 FLOAT64, A32 FLOAT64, A33 FLOAT64, A34 FLOAT64, A35 FLOAT64,
  A36 FLOAT64, A37 FLOAT64, A38 FLOAT64, A39 FLOAT64, A40 FLOAT64,
  A41 FLOAT64, A42 FLOAT64, A43 FLOAT64, A44 FLOAT64, A45 FLOAT64,
  A46 FLOAT64, A47 FLOAT64, A48 FLOAT64, A49 FLOAT64, A50 FLOAT64,
  A51 FLOAT64, A52 FLOAT64, A53 FLOAT64, A54 FLOAT64, A55 FLOAT64,
  A56 FLOAT64, A57 FLOAT64, A58 FLOAT64, A59 FLOAT64, A60 FLOAT64,
  A61 FLOAT64, A62 FLOAT64, A63 FLOAT64, A64 FLOAT64
);

-- 3. Species signatures (aggregated from raw embeddings, populated by Python)
CREATE TABLE IF NOT EXISTS `treekipedia-476404.alphaearth.species_signatures` (
  taxon_id STRING PRIMARY KEY NOT ENFORCED,
  species_scientific_name STRING,
  n_occurrences INT64,
  n_prototypes INT64,
  mean_r FLOAT64,  -- average resultant length across prototypes
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
