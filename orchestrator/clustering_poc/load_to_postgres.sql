-- Create AlphaEarth species centroids table in treekipedia database
-- This table stores the k-means cluster centroids for each species

DROP TABLE IF EXISTS species_alphaearth_centroids CASCADE;

CREATE TABLE species_alphaearth_centroids (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,
    cluster_id INTEGER NOT NULL,
    cluster_size INTEGER NOT NULL,
    total_occurrences INTEGER NOT NULL,
    clustering_method VARCHAR(50) NOT NULL,
    representative_lat DOUBLE PRECISION,
    representative_lon DOUBLE PRECISION,
    representative_year INTEGER,

    -- 64-dimensional embedding centroid (A00-A63)
    centroid_a00 DOUBLE PRECISION,
    centroid_a01 DOUBLE PRECISION,
    centroid_a02 DOUBLE PRECISION,
    centroid_a03 DOUBLE PRECISION,
    centroid_a04 DOUBLE PRECISION,
    centroid_a05 DOUBLE PRECISION,
    centroid_a06 DOUBLE PRECISION,
    centroid_a07 DOUBLE PRECISION,
    centroid_a08 DOUBLE PRECISION,
    centroid_a09 DOUBLE PRECISION,
    centroid_a10 DOUBLE PRECISION,
    centroid_a11 DOUBLE PRECISION,
    centroid_a12 DOUBLE PRECISION,
    centroid_a13 DOUBLE PRECISION,
    centroid_a14 DOUBLE PRECISION,
    centroid_a15 DOUBLE PRECISION,
    centroid_a16 DOUBLE PRECISION,
    centroid_a17 DOUBLE PRECISION,
    centroid_a18 DOUBLE PRECISION,
    centroid_a19 DOUBLE PRECISION,
    centroid_a20 DOUBLE PRECISION,
    centroid_a21 DOUBLE PRECISION,
    centroid_a22 DOUBLE PRECISION,
    centroid_a23 DOUBLE PRECISION,
    centroid_a24 DOUBLE PRECISION,
    centroid_a25 DOUBLE PRECISION,
    centroid_a26 DOUBLE PRECISION,
    centroid_a27 DOUBLE PRECISION,
    centroid_a28 DOUBLE PRECISION,
    centroid_a29 DOUBLE PRECISION,
    centroid_a30 DOUBLE PRECISION,
    centroid_a31 DOUBLE PRECISION,
    centroid_a32 DOUBLE PRECISION,
    centroid_a33 DOUBLE PRECISION,
    centroid_a34 DOUBLE PRECISION,
    centroid_a35 DOUBLE PRECISION,
    centroid_a36 DOUBLE PRECISION,
    centroid_a37 DOUBLE PRECISION,
    centroid_a38 DOUBLE PRECISION,
    centroid_a39 DOUBLE PRECISION,
    centroid_a40 DOUBLE PRECISION,
    centroid_a41 DOUBLE PRECISION,
    centroid_a42 DOUBLE PRECISION,
    centroid_a43 DOUBLE PRECISION,
    centroid_a44 DOUBLE PRECISION,
    centroid_a45 DOUBLE PRECISION,
    centroid_a46 DOUBLE PRECISION,
    centroid_a47 DOUBLE PRECISION,
    centroid_a48 DOUBLE PRECISION,
    centroid_a49 DOUBLE PRECISION,
    centroid_a50 DOUBLE PRECISION,
    centroid_a51 DOUBLE PRECISION,
    centroid_a52 DOUBLE PRECISION,
    centroid_a53 DOUBLE PRECISION,
    centroid_a54 DOUBLE PRECISION,
    centroid_a55 DOUBLE PRECISION,
    centroid_a56 DOUBLE PRECISION,
    centroid_a57 DOUBLE PRECISION,
    centroid_a58 DOUBLE PRECISION,
    centroid_a59 DOUBLE PRECISION,
    centroid_a60 DOUBLE PRECISION,
    centroid_a61 DOUBLE PRECISION,
    centroid_a62 DOUBLE PRECISION,
    centroid_a63 DOUBLE PRECISION,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one centroid per (species, cluster_id)
    CONSTRAINT unique_species_cluster UNIQUE (taxon_id, cluster_id)
);

-- Indexes for fast queries
CREATE INDEX idx_centroids_taxon_id ON species_alphaearth_centroids(taxon_id);
CREATE INDEX idx_centroids_cluster_size ON species_alphaearth_centroids(cluster_size);
CREATE INDEX idx_centroids_method ON species_alphaearth_centroids(clustering_method);

-- Comment on table
COMMENT ON TABLE species_alphaearth_centroids IS 'AlphaEarth satellite embedding centroids (64-D) from k-means clustering of species occurrences. Each species has up to 5 centroids representing distinct habitat types.';

-- Grant permissions (adjust as needed)
-- GRANT SELECT ON species_alphaearth_centroids TO treekipedia_app;
