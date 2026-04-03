#!/usr/bin/env python3
"""
land_state_engine.py — Land State Engine v1 for SINR v3.

Two-tier design:
  Tier 1: Deterministic heuristic from existing environmental features
  Tier 2: Neural head on AlphaEarth 8-year temporal stack (trained with Tier 1 pseudo-labels)

Tier 1 computes 4 land state features per observation:
  1. land_state_class (0-5): categorical land state
  2. disturbance_intensity (0-1): how disturbed the landscape is
  3. forest_stability (-1 to 1): temporal stability of forest cover
  4. successional_stage (0-4): estimated successional stage

Tier 2 trains a small neural network to predict these from AlphaEarth temporal
embeddings, learning to detect disturbance patterns that heuristics miss.

Input: sinr_v3_unified_v1 BigQuery table
Output: BQ table with land state features per observation

Usage:
  python3 land_state_engine.py --tier1 --dry-run     # Show Tier 1 SQL
  python3 land_state_engine.py --tier1 --execute      # Run Tier 1 on BQ
  python3 land_state_engine.py --tier2-data           # Export AE temporal + labels for Tier 2
  python3 land_state_engine.py --tier2-train          # Train Tier 2 neural head
"""

import argparse
from datetime import datetime

BQ_PROJECT = 'treekipedia-479918'
BQ_DATASET = 'species_data'
INPUT_TABLE = 'sinr_v3_unified_v2'
OUTPUT_TABLE_T1 = 'sinr_v3_land_state_t1'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# TIER 1: DETERMINISTIC HEURISTIC
# =============================================================================

def build_tier1_query():
    """Build the Tier 1 heuristic SQL.

    Uses Hansen, HILDA, JRC TMF, Neumann natural probability, carbon/biomass,
    fire, and human modification to classify land state.

    Land State Classes:
      0 = Old-growth / undisturbed natural forest
      1 = Mature natural forest (some disturbance history)
      2 = Regenerating / secondary forest
      3 = Plantation / cultivated forest
      4 = Recently disturbed / deforested
      5 = Non-forest (grassland, cropland, urban, water)
    """

    query = f"""
    CREATE TABLE `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE_T1}` AS

    WITH features AS (
        SELECT
            latitude,
            longitude,
            observation_year,
            emb_year,
            data_source,

            -- Hansen forest change
            COALESCE(treecover2000, 0) as tc2000,
            COALESCE(lossyear, 0) as loss_yr,
            COALESCE(hansen_gain, 0) as gain,

            -- HILDA land use
            COALESCE(hilda_lulc_at_obs, 0) as hilda_obs,
            COALESCE(hilda_lulc_at_ae, 0) as hilda_ae,
            COALESCE(lulc_changed, 0) as lulc_changed,
            COALESCE(forest_to_nonforest, 0) as f2nf,

            -- JRC Tropical Moist Forest
            COALESCE(jrc_tmf_status, 0) as tmf_status,
            COALESCE(jrc_tmf_degrad_year, 0) as tmf_degrad_yr,

            -- Neumann natural forest probability
            COALESCE(neumann_natural_prob, -1) as natural_prob,

            -- Xiao planted forest detection
            COALESCE(xiao_planted_forest, -1) as planted_prob,

            -- Carbon / biomass indicators
            COALESCE(carbon_canopy_height_m, 0) as canopy_h,
            COALESCE(spawn_agb, 0) as agb,
            COALESCE(npp_at_obs, 0) as npp_obs,
            COALESCE(npp_trend, 0) as npp_trend,

            -- Human pressure
            COALESCE(human_modification, 0) as hmod,
            COALESCE(fire_frequency_count, 0) as fire_freq,
            COALESCE(nighttime_lights, 0) as ntl,

            -- Land cover
            COALESCE(esa_worldcover_2021, 0) as esa_lc,
            COALESCE(sbtn_natural_land, 0) as sbtn_natural,

            -- AE temporal bands (first 8 of 2017 and 2024 for temporal change signal)
            ae_2017_00, ae_2017_01, ae_2017_02, ae_2017_03,
            ae_2017_04, ae_2017_05, ae_2017_06, ae_2017_07,
            ae_2024_00, ae_2024_01, ae_2024_02, ae_2024_03,
            ae_2024_04, ae_2024_05, ae_2024_06, ae_2024_07,

        FROM `{BQ_PROJECT}.{BQ_DATASET}.{INPUT_TABLE}`
    ),

    -- Step 1: Compute intermediate signals
    signals AS (
        SELECT
            *,

            -- Is this a forest location? (ESA tree cover or high Hansen treecover)
            CASE
                WHEN esa_lc = 10 THEN 1  -- ESA: tree cover
                WHEN tc2000 >= 30 THEN 1  -- Hansen: >=30% canopy
                WHEN hilda_obs BETWEEN 40 AND 45 THEN 1  -- HILDA: forest classes
                ELSE 0
            END as is_forest,

            -- Years since Hansen loss (0 = no loss)
            CASE
                WHEN loss_yr > 0 THEN (2024 - (2000 + loss_yr))
                ELSE 0
            END as years_since_loss,

            -- Is it a HILDA forest class?
            CASE WHEN hilda_obs BETWEEN 40 AND 45 THEN 1 ELSE 0 END as hilda_is_forest,

            -- HILDA agriculture classes
            CASE WHEN hilda_obs IN (22, 23, 24, 33) THEN 1 ELSE 0 END as hilda_is_agri,

            -- Natural forest signal (high if multiple indicators agree)
            (
                CASE WHEN natural_prob > 0.7 THEN 0.3 ELSE 0 END +
                CASE WHEN planted_prob >= 0 AND planted_prob < 0.3 THEN 0.2 ELSE 0 END +
                CASE WHEN sbtn_natural > 0 THEN 0.2 ELSE 0 END +
                CASE WHEN hmod < 0.2 THEN 0.2 ELSE 0 END +
                CASE WHEN fire_freq <= 1 THEN 0.1 ELSE 0 END
            ) as natural_score,

            -- Plantation signal
            (
                CASE WHEN planted_prob > 0.7 THEN 0.4 ELSE 0 END +
                CASE WHEN hilda_obs = 23 THEN 0.3 ELSE 0 END +  -- tree crops
                CASE WHEN natural_prob >= 0 AND natural_prob < 0.3 THEN 0.2 ELSE 0 END +
                CASE WHEN hmod > 0.4 THEN 0.1 ELSE 0 END
            ) as plantation_score

        FROM features
    )

    -- Step 2: Classify land state
    SELECT
        latitude,
        longitude,
        observation_year,
        emb_year,
        data_source,

        -- LAND STATE CLASS (0-5)
        CASE
            -- Non-forest
            WHEN is_forest = 0 AND NOT (tc2000 >= 20) THEN 5

            -- Recently disturbed (lost forest in last 10 years)
            WHEN loss_yr > 0 AND years_since_loss < 10 AND f2nf = 1 THEN 4
            WHEN tmf_degrad_yr > 0 AND (2024 - tmf_degrad_yr) < 10 THEN 4

            -- Plantation / cultivated
            WHEN plantation_score >= 0.5 THEN 3
            WHEN hilda_obs IN (23, 24) AND is_forest = 1 THEN 3  -- tree crops or agroforestry

            -- Regenerating / secondary
            WHEN loss_yr > 0 AND years_since_loss BETWEEN 10 AND 30 AND gain > 0 THEN 2
            WHEN lulc_changed = 1 AND is_forest = 1 THEN 2
            WHEN canopy_h > 0 AND canopy_h < 15 AND agb < 100 AND is_forest = 1 THEN 2

            -- Mature natural forest
            WHEN natural_score >= 0.5 AND canopy_h >= 15 AND loss_yr = 0 THEN 1
            WHEN natural_score >= 0.3 AND is_forest = 1 AND loss_yr = 0 THEN 1

            -- Old-growth (strongest natural signals)
            WHEN natural_score >= 0.7 AND canopy_h >= 25 AND agb >= 150
                 AND loss_yr = 0 AND lulc_changed = 0 AND hmod < 0.15 THEN 0

            -- Default: if forest → mature, if not → non-forest
            WHEN is_forest = 1 THEN 1
            ELSE 5
        END as land_state_class,

        -- DISTURBANCE INTENSITY (0-1)
        LEAST(1.0, GREATEST(0.0,
            0.3 * hmod +
            0.25 * CASE WHEN loss_yr > 0 THEN (1.0 - years_since_loss / 30.0) ELSE 0 END +
            0.2 * CASE WHEN f2nf = 1 THEN 1.0 ELSE 0.0 END +
            0.15 * LEAST(1.0, fire_freq / 5.0) +
            0.1 * LEAST(1.0, ntl / 30.0)
        )) as disturbance_intensity,

        -- FOREST STABILITY (-1 to 1)
        -- -1 = recently deforested, 0 = changing, 1 = stable undisturbed
        CASE
            WHEN f2nf = 1 AND years_since_loss < 5 THEN -1.0
            WHEN f2nf = 1 THEN -0.7
            WHEN lulc_changed = 1 THEN -0.3
            WHEN loss_yr > 0 AND gain > 0 THEN 0.0  -- disturbed but recovering
            WHEN is_forest = 1 AND loss_yr = 0 AND lulc_changed = 0
                 AND hmod < 0.2 THEN 1.0  -- stable forest
            WHEN is_forest = 1 AND loss_yr = 0 THEN 0.7
            WHEN is_forest = 0 THEN 0.0  -- non-forest neutral
            ELSE 0.3
        END as forest_stability,

        -- SUCCESSIONAL STAGE (0-4)
        -- 0=pioneer, 1=early, 2=mid, 3=late, 4=old-growth
        CASE
            WHEN is_forest = 0 THEN -1  -- not applicable
            WHEN loss_yr > 0 AND years_since_loss < 5 THEN 0
            WHEN loss_yr > 0 AND years_since_loss < 15 THEN 1
            WHEN (loss_yr > 0 AND years_since_loss < 30) OR (canopy_h < 15 AND agb < 100) THEN 2
            WHEN canopy_h >= 25 AND agb >= 150 AND hmod < 0.15 AND loss_yr = 0 THEN 4
            ELSE 3
        END as successional_stage,

        -- AlphaEarth temporal change signal (cosine distance between first and last year)
        -- This is a simple heuristic; Tier 2 will learn the full temporal patterns
        -- We compute L2 norm of ae_2017 vs ae_2024 embedding difference
        -- (Only first 8 bands for efficiency in SQL)
        SQRT(
            POW(COALESCE(ae_2024_00, 0) - COALESCE(ae_2017_00, 0), 2) +
            POW(COALESCE(ae_2024_01, 0) - COALESCE(ae_2017_01, 0), 2) +
            POW(COALESCE(ae_2024_02, 0) - COALESCE(ae_2017_02, 0), 2) +
            POW(COALESCE(ae_2024_03, 0) - COALESCE(ae_2017_03, 0), 2) +
            POW(COALESCE(ae_2024_04, 0) - COALESCE(ae_2017_04, 0), 2) +
            POW(COALESCE(ae_2024_05, 0) - COALESCE(ae_2017_05, 0), 2) +
            POW(COALESCE(ae_2024_06, 0) - COALESCE(ae_2017_06, 0), 2) +
            POW(COALESCE(ae_2024_07, 0) - COALESCE(ae_2017_07, 0), 2)
        ) as ae_temporal_change_l2,

        -- Raw signals for Tier 2 training labels
        natural_score,
        plantation_score,
        is_forest,
        years_since_loss

    FROM signals
    """

    return query


def build_tier2_export_query(limit=500000):
    """Export AE temporal stack + Tier 1 labels for Tier 2 training.

    For each observation, exports:
    - 512 AE temporal features (8 years × 64 bands)
    - Tier 1 land state labels
    - Location for grouping
    """

    ae_cols = []
    for year in range(2017, 2025):
        for band in range(64):
            ae_cols.append(f'u.ae_{year}_{band:02d}')

    query = f"""
    SELECT
        u.latitude, u.longitude, u.observation_year, u.emb_year,
        -- Tier 1 labels
        t.land_state_class,
        t.disturbance_intensity,
        t.forest_stability,
        t.successional_stage,
        t.ae_temporal_change_l2,
        -- AlphaEarth 8-year temporal stack (512 features)
        {', '.join(ae_cols)}
    FROM `{BQ_PROJECT}.{BQ_DATASET}.{INPUT_TABLE}` u
    JOIN `{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE_T1}` t
        ON ROUND(u.latitude, 4) = ROUND(t.latitude, 4)
        AND ROUND(u.longitude, 4) = ROUND(t.longitude, 4)
        AND u.observation_year = t.observation_year
        AND u.emb_year = t.emb_year
    WHERE t.land_state_class IS NOT NULL
        AND t.is_forest = 1  -- Only forest observations for Tier 2
    ORDER BY RAND()
    LIMIT {limit}
    """
    return query


# =============================================================================
# TIER 2: NEURAL HEAD ON AE TEMPORAL STACK
# =============================================================================

def build_tier2_model():
    """Build the Tier 2 neural network.

    Input: 512D (8 years × 64 AE bands)
    Output: 4 regression targets (land_state_class, disturbance, stability, succession)

    Architecture: Simple MLP with temporal attention
    - Reshape 512D → 8×64 (time × embedding)
    - 1D temporal attention across 8 years
    - Pool to fixed-size → MLP → 4 outputs
    """
    import torch
    import torch.nn as nn

    class TemporalAttention(nn.Module):
        """Attention over 8 temporal steps of 64D AlphaEarth embeddings."""

        def __init__(self, embed_dim=64, n_years=8, hidden_dim=128):
            super().__init__()
            self.n_years = n_years
            self.embed_dim = embed_dim

            # Temporal attention
            self.query = nn.Linear(embed_dim, embed_dim)
            self.key = nn.Linear(embed_dim, embed_dim)
            self.value = nn.Linear(embed_dim, embed_dim)
            self.scale = embed_dim ** 0.5

            # Year-level features
            self.year_embed = nn.Embedding(n_years, embed_dim)

            # Temporal difference features
            self.diff_proj = nn.Linear(embed_dim, hidden_dim // 2)

        def forward(self, x):
            # x: (batch, 512) → (batch, 8, 64)
            B = x.shape[0]
            x = x.view(B, self.n_years, self.embed_dim)

            # Add year embeddings
            year_ids = torch.arange(self.n_years, device=x.device)
            x = x + self.year_embed(year_ids).unsqueeze(0)

            # Self-attention over time
            Q = self.query(x)
            K = self.key(x)
            V = self.value(x)
            attn = torch.softmax(Q @ K.transpose(-1, -2) / self.scale, dim=-1)
            attended = attn @ V  # (B, 8, 64)

            # Pool: mean + max
            pooled_mean = attended.mean(dim=1)  # (B, 64)
            pooled_max = attended.max(dim=1).values  # (B, 64)

            # Temporal differences (captures change)
            diffs = x[:, 1:] - x[:, :-1]  # (B, 7, 64)
            diff_features = self.diff_proj(diffs).mean(dim=1)  # (B, hidden//2)

            # First and last year
            first_year = x[:, 0]  # (B, 64)
            last_year = x[:, -1]  # (B, 64)

            return torch.cat([pooled_mean, pooled_max, diff_features, first_year, last_year], dim=-1)

    class LandStateNet(nn.Module):
        """Predicts land state from AE temporal stack."""

        def __init__(self, embed_dim=64, n_years=8, hidden_dim=128):
            super().__init__()
            self.temporal = TemporalAttention(embed_dim, n_years, hidden_dim)

            # Input: pooled_mean(64) + pooled_max(64) + diff(64) + first(64) + last(64) = 320
            feat_dim = embed_dim * 4 + hidden_dim // 2

            self.head = nn.Sequential(
                nn.Linear(feat_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(0.1),
            )

            # Multi-task outputs
            self.land_state_head = nn.Linear(hidden_dim // 2, 6)  # 6-class classification
            self.disturbance_head = nn.Linear(hidden_dim // 2, 1)  # regression 0-1
            self.stability_head = nn.Linear(hidden_dim // 2, 1)   # regression -1 to 1
            self.succession_head = nn.Linear(hidden_dim // 2, 5)  # 5-class classification

        def forward(self, ae_temporal):
            features = self.temporal(ae_temporal)
            h = self.head(features)

            return {
                'land_state': self.land_state_head(h),
                'disturbance': torch.sigmoid(self.disturbance_head(h)),
                'stability': torch.tanh(self.stability_head(h)),
                'succession': self.succession_head(h),
            }

    return LandStateNet()


def train_tier2(data_path, epochs=50, batch_size=1024, lr=1e-3):
    """Train the Tier 2 model on exported data."""
    import torch
    import torch.nn as nn
    import numpy as np
    from torch.utils.data import DataLoader, TensorDataset

    log("Loading Tier 2 training data...")
    data = np.load(data_path)
    ae_features = data['ae_features']  # (N, 512)
    labels = data['labels']            # (N, 4): class, disturbance, stability, succession

    # Split 90/10
    n = len(ae_features)
    idx = np.random.permutation(n)
    split = int(0.9 * n)

    train_ae = torch.FloatTensor(ae_features[idx[:split]])
    train_labels = torch.FloatTensor(labels[idx[:split]])
    val_ae = torch.FloatTensor(ae_features[idx[split:]])
    val_labels = torch.FloatTensor(labels[idx[split:]])

    train_ds = TensorDataset(train_ae, train_labels)
    val_ds = TensorDataset(val_ae, val_labels)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size)

    model = build_tier2_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    ce_loss = nn.CrossEntropyLoss()
    mse_loss = nn.MSELoss()

    log(f"Training Tier 2: {n:,} samples, {epochs} epochs")

    best_val_loss = float('inf')
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for ae_batch, label_batch in train_dl:
            out = model(ae_batch)

            # Multi-task loss
            loss_class = ce_loss(out['land_state'], label_batch[:, 0].long())
            loss_dist = mse_loss(out['disturbance'].squeeze(), label_batch[:, 1])
            loss_stab = mse_loss(out['stability'].squeeze(), label_batch[:, 2])
            loss_succ = ce_loss(out['succession'], label_batch[:, 3].long().clamp(0, 4))

            loss = loss_class + loss_dist + loss_stab + loss_succ

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for ae_batch, label_batch in val_dl:
                out = model(ae_batch)
                loss_class = ce_loss(out['land_state'], label_batch[:, 0].long())
                loss_dist = mse_loss(out['disturbance'].squeeze(), label_batch[:, 1])
                loss_stab = mse_loss(out['stability'].squeeze(), label_batch[:, 2])
                loss_succ = ce_loss(out['succession'], label_batch[:, 3].long().clamp(0, 4))
                val_loss += (loss_class + loss_dist + loss_stab + loss_succ).item()

        train_avg = total_loss / len(train_dl)
        val_avg = val_loss / len(val_dl)

        if (epoch + 1) % 5 == 0:
            log(f"  Epoch {epoch+1}/{epochs}: train={train_avg:.4f}, val={val_avg:.4f}")

        if val_avg < best_val_loss:
            best_val_loss = val_avg
            torch.save(model.state_dict(), 'sinr_training_data/land_state_tier2.pt')

    log(f"Best validation loss: {best_val_loss:.4f}")
    log("Saved model to sinr_training_data/land_state_tier2.pt")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Land State Engine v1')
    parser.add_argument('--tier1', action='store_true', help='Run Tier 1 heuristic')
    parser.add_argument('--tier2-data', action='store_true', help='Export data for Tier 2')
    parser.add_argument('--tier2-train', action='store_true', help='Train Tier 2 model')
    parser.add_argument('--dry-run', action='store_true', help='Print SQL without executing')
    parser.add_argument('--execute', action='store_true', help='Execute on BigQuery')
    args = parser.parse_args()

    if args.tier1:
        query = build_tier1_query()

        if args.dry_run:
            log("=== TIER 1 — Land State Heuristic SQL ===")
            print(query)
            log(f"\nWill create: {BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE_T1}")
            return

        if args.execute:
            from google.cloud import bigquery
            client = bigquery.Client(project=BQ_PROJECT)

            # Safety check
            try:
                existing = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE_T1}')
                log(f"ERROR: {OUTPUT_TABLE_T1} already exists ({existing.num_rows:,} rows)!")
                log("Delete it first or use a different name.")
                return
            except Exception:
                pass

            log(f"Creating {OUTPUT_TABLE_T1}...")
            job = client.query(query)
            log(f"Job started: {job.job_id}")
            result = job.result()

            output = client.get_table(f'{BQ_PROJECT}.{BQ_DATASET}.{OUTPUT_TABLE_T1}')
            log(f"DONE! {OUTPUT_TABLE_T1}: {output.num_rows:,} rows, {len(output.schema)} cols")
            return

    if args.tier2_data:
        query = build_tier2_export_query()
        if args.dry_run:
            log("=== TIER 2 — Export Query ===")
            print(query)
            return

        if args.execute:
            log("Exporting Tier 2 training data from BQ...")
            from google.cloud import bigquery
            import numpy as np
            client = bigquery.Client(project=BQ_PROJECT)

            df = client.query(query).to_dataframe()
            log(f"Got {len(df):,} rows")

            # Extract AE columns
            ae_cols = [f'ae_{y}_{b:02d}' for y in range(2017, 2025) for b in range(64)]
            ae_features = df[ae_cols].values.astype('float32')

            # Extract labels
            labels = df[['land_state_class', 'disturbance_intensity',
                         'forest_stability', 'successional_stage']].values.astype('float32')

            output_path = 'sinr_training_data/land_state_tier2_data.npz'
            np.savez_compressed(output_path, ae_features=ae_features, labels=labels)
            log(f"Saved to {output_path}: {ae_features.shape[0]:,} samples")
            return

    if args.tier2_train:
        train_tier2('sinr_training_data/land_state_tier2_data.npz')
        return

    parser.print_help()


if __name__ == '__main__':
    main()
