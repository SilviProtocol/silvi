#!/usr/bin/env python3
"""
Train an AlphaEarth → Environmental Variable decoder.

Takes 64D AE embeddings as input and predicts all environmental variables
in a single multi-output model. This eliminates the need for most GEE calls
in the Site Inspector — just sample AE from COG and decode locally.

Data sources:
  1. SINR v3 training shards (5×1M rows, forest-biased from GBIF occurrences)
  2. Random background points (uniform global sample, unbiased)

Usage:
  # Phase 1: Train on existing BQ data (biased but immediate)
  python3 train_ae_env_decoder.py --from-bq --shards 0,1,2,3,4

  # Phase 2: After background sampling is done, retrain with both
  python3 train_ae_env_decoder.py --from-bq --shards 0,1,2,3,4 --background-parquet background_env_samples.parquet

  # Evaluate only
  python3 train_ae_env_decoder.py --evaluate --model-path ae_env_decoder.pt
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# ─── Constants ────────────────────────────────────────────────────────────────

PROJECT = "treekipedia-479918"
DATASET = "species_data"

# 5M training shards
SHARD_TABLE_TEMPLATE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_medium_5m_s{{shard}}"

# Full training table (12M+)
FULL_TABLE = f"{PROJECT}.{DATASET}.sinr_v3_unified_strict_train_v30_preview_clean"

# AE embedding columns
AE_COLS = [f"emb_{i:02d}" for i in range(64)]

# Environmental continuous targets (from v4.1 feature contract)
ENV_CONTINUOUS_COLS = [
    "elevation", "slope", "aspect", "hillshade", "topo_diversity",
    "merit_hand_m", "merit_upstream_area_km2",
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    "treecover2000", "lossyear", "biomass_agb_mgha",
    "water_occurrence", "water_recurrence", "water_seasonality",
    "jrc_tmf_status", "jrc_tmf_degrad_year",
    "esa_worldcover_2021", "dynamic_world",
    "sbtn_natural_land", "neumann_natural_prob",
    "tc_vpd_mean", "tc_vpd_delta", "tc_aet_mean",
    "tc_soil_moisture_mean", "tc_pdsi_mean",
    "tc_water_deficit_mean", "tc_solar_rad_mean",
    "human_modification", "nighttime_lights", "fire_frequency_count",
    "modis_gpp_mean",
]

# Categorical targets (predicted as classification heads)
CATEGORICAL_COLS = {
    "jrc_forest_type": 6,       # 0-5
    "xiao_planted_forest": 4,   # 0-3
    "biome_num": 17,            # 0-16
    "soil_texture_class": 15,   # 0-14
}
# Note: eco_id has 850 classes — too sparse for a decoder, skip it

# Variables where AE should have strong signal (spectral/visual)
# vs weak signal (underground/historical) — for reporting
EXPECTED_STRONG = {
    "bio01", "bio02", "bio03", "bio04", "bio05", "bio06", "bio07",
    "bio08", "bio09", "bio10", "bio11", "bio12", "bio13", "bio14",
    "bio15", "bio16", "bio17", "bio18", "bio19",
    "elevation", "slope", "treecover2000", "biomass_agb_mgha",
    "esa_worldcover_2021", "dynamic_world", "neumann_natural_prob",
    "human_modification", "modis_gpp_mean", "sbtn_natural_land",
    "tc_vpd_mean", "tc_aet_mean", "tc_solar_rad_mean",
}

EXPECTED_WEAK = {
    "soil_ph", "soil_clay_pct", "soil_sand_pct", "soil_organic_carbon",
    "soil_bulk_density", "soil_water_content",
    "jrc_tmf_degrad_year", "fire_frequency_count", "lossyear",
    "nighttime_lights",
}

OUTPUT_DIR = Path(__file__).parent / "ae_env_decoder"


# ─── Model ────────────────────────────────────────────────────────────────────

class AEEnvDecoder(nn.Module):
    """Multi-output decoder: AE_64D → environmental variables."""

    def __init__(self, n_continuous: int, categorical_vocab: dict[str, int],
                 hidden: int = 256, dropout: float = 0.1):
        super().__init__()
        self.continuous_cols = ENV_CONTINUOUS_COLS[:n_continuous]
        self.categorical_vocab = categorical_vocab

        # Shared trunk
        self.trunk = nn.Sequential(
            nn.Linear(64, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Continuous regression head
        self.continuous_head = nn.Linear(hidden, n_continuous)

        # Categorical classification heads
        self.categorical_heads = nn.ModuleDict({
            name: nn.Linear(hidden, vocab_size)
            for name, vocab_size in categorical_vocab.items()
        })

    def forward(self, x):
        h = self.trunk(x)
        continuous_out = self.continuous_head(h)
        categorical_out = {
            name: head(h) for name, head in self.categorical_heads.items()
        }
        return continuous_out, categorical_out


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_from_bigquery(shards: list[int] | None = None, use_full: bool = False,
                       max_rows: int | None = None) -> "pd.DataFrame":
    """Load training data from BigQuery."""
    import pandas as pd
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    all_cols = AE_COLS + ENV_CONTINUOUS_COLS + list(CATEGORICAL_COLS.keys()) + ["latitude", "longitude"]
    col_str = ", ".join(all_cols)

    if use_full:
        tables = [FULL_TABLE]
    elif shards is not None:
        tables = [SHARD_TABLE_TEMPLATE.format(shard=s) for s in shards]
    else:
        tables = [SHARD_TABLE_TEMPLATE.format(shard=s) for s in range(5)]

    dfs = []
    for table in tables:
        print(f"  Loading {table}...")
        limit_clause = f"LIMIT {max_rows}" if max_rows else ""
        query = f"SELECT {col_str} FROM `{table}` {limit_clause}"
        df = client.query(query).to_dataframe()
        print(f"    → {len(df):,} rows")
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    print(f"  Total: {len(combined):,} rows from {len(tables)} table(s)")
    return combined


def load_from_parquet(paths: list[str]) -> "pd.DataFrame":
    """Load data from local parquet files."""
    import pandas as pd

    dfs = []
    for path in paths:
        print(f"  Loading {path}...")
        df = pd.read_parquet(path)
        print(f"    → {len(df):,} rows")
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def prepare_tensors(df: "pd.DataFrame", fit_stats: dict | None = None):
    """Convert DataFrame to normalized tensors. Returns X, Y_cont, Y_cat, stats."""
    import pandas as pd

    # Extract AE inputs
    X = df[AE_COLS].values.astype(np.float32)

    # Extract continuous targets
    Y_cont_raw = df[ENV_CONTINUOUS_COLS].values.astype(np.float32)

    # Handle NaN/inf in targets — replace with column median
    for col_idx in range(Y_cont_raw.shape[1]):
        col = Y_cont_raw[:, col_idx]
        mask = ~np.isfinite(col)
        if mask.any():
            median_val = np.nanmedian(col[~mask]) if (~mask).any() else 0.0
            col[mask] = median_val

    # Handle NaN/inf in inputs
    for col_idx in range(X.shape[1]):
        col = X[:, col_idx]
        mask = ~np.isfinite(col)
        if mask.any():
            median_val = np.nanmedian(col[~mask]) if (~mask).any() else 0.0
            col[mask] = median_val

    # Compute or reuse normalization stats for targets
    if fit_stats is None:
        target_mean = np.nanmean(Y_cont_raw, axis=0)
        target_std = np.nanstd(Y_cont_raw, axis=0)
        target_std[target_std < 1e-6] = 1.0  # avoid div-by-zero
        fit_stats = {
            "target_mean": target_mean.tolist(),
            "target_std": target_std.tolist(),
            "ae_mean": np.mean(X, axis=0).tolist(),
            "ae_std": np.std(X, axis=0).tolist(),
        }
    else:
        target_mean = np.array(fit_stats["target_mean"], dtype=np.float32)
        target_std = np.array(fit_stats["target_std"], dtype=np.float32)

    # Normalize targets (z-score)
    Y_cont = (Y_cont_raw - target_mean) / target_std

    # Extract categorical targets
    Y_cat = {}
    for col_name in CATEGORICAL_COLS:
        if col_name in df.columns:
            vals = df[col_name].fillna(0).astype(int).values
            # Clamp to valid range
            vocab_size = CATEGORICAL_COLS[col_name]
            vals = np.clip(vals, 0, vocab_size - 1)
            Y_cat[col_name] = vals
        else:
            Y_cat[col_name] = np.zeros(len(df), dtype=int)

    return (
        torch.from_numpy(X),
        torch.from_numpy(Y_cont),
        {k: torch.from_numpy(v).long() for k, v in Y_cat.items()},
        fit_stats,
    )


# ─── Training ────────────────────────────────────────────────────────────────

def train_model(X_train, Y_cont_train, Y_cat_train,
                X_val, Y_cont_val, Y_cat_val,
                n_epochs: int = 30, batch_size: int = 4096,
                lr: float = 1e-3, hidden: int = 256, dropout: float = 0.1,
                device: str = "cpu"):
    """Train the decoder model."""

    n_continuous = Y_cont_train.shape[1]
    model = AEEnvDecoder(n_continuous, CATEGORICAL_COLS, hidden=hidden, dropout=dropout)
    model = model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_epochs)

    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()

    # Build DataLoader
    cat_tensors = [Y_cat_train[k] for k in CATEGORICAL_COLS]
    train_ds = TensorDataset(X_train, Y_cont_train, *cat_tensors)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(n_epochs):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        for batch in train_loader:
            x_batch = batch[0].to(device)
            y_cont_batch = batch[1].to(device)
            y_cat_batches = {k: batch[2 + i].to(device) for i, k in enumerate(CATEGORICAL_COLS)}

            cont_pred, cat_pred = model(x_batch)

            # MSE for continuous
            loss = mse_loss(cont_pred, y_cont_batch)

            # CE for categorical (weighted lower since fewer targets)
            for k in CATEGORICAL_COLS:
                loss += 0.1 * ce_loss(cat_pred[k], y_cat_batches[k])

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        scheduler.step()

        # Validation
        model.eval()
        with torch.no_grad():
            X_v = X_val.to(device)
            Y_v = Y_cont_val.to(device)
            cont_pred_v, cat_pred_v = model(X_v)
            val_mse = mse_loss(cont_pred_v, Y_v).item()

            val_loss = val_mse
            for k in CATEGORICAL_COLS:
                val_loss += 0.1 * ce_loss(cat_pred_v[k], Y_cat_val[k].to(device)).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{n_epochs}  "
                  f"train_loss={epoch_loss/n_batches:.4f}  "
                  f"val_mse={val_mse:.4f}  val_total={val_loss:.4f}  "
                  f"lr={scheduler.get_last_lr()[0]:.6f}")

    # Load best
    model.load_state_dict(best_state)
    return model


# ─── Evaluation ───────────────────────────────────────────────────────────────

def evaluate_model(model, X_val, Y_cont_val, Y_cat_val, stats, device="cpu"):
    """Compute per-variable R² and categorical accuracy."""
    model.eval()

    target_mean = np.array(stats["target_mean"], dtype=np.float32)
    target_std = np.array(stats["target_std"], dtype=np.float32)

    with torch.no_grad():
        cont_pred, cat_pred = model(X_val.to(device))
        cont_pred = cont_pred.cpu().numpy()

    Y_val_np = Y_cont_val.numpy()

    # Denormalize
    pred_raw = cont_pred * target_std + target_mean
    true_raw = Y_val_np * target_std + target_mean

    results = {}
    print("\n" + "=" * 80)
    print(f"{'Variable':<30} {'R²':>8} {'MAE':>10} {'Signal':>10}")
    print("=" * 80)

    for i, col_name in enumerate(ENV_CONTINUOUS_COLS):
        y_true = true_raw[:, i]
        y_pred = pred_raw[:, i]

        # R²
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # MAE
        mae = np.mean(np.abs(y_true - y_pred))

        signal = "STRONG" if col_name in EXPECTED_STRONG else (
            "WEAK" if col_name in EXPECTED_WEAK else "?")
        marker = "✓" if r2 > 0.7 else ("~" if r2 > 0.4 else "✗")

        results[col_name] = {"r2": float(r2), "mae": float(mae), "signal": signal}
        print(f"  {marker} {col_name:<28} {r2:>8.4f} {mae:>10.2f} {signal:>10}")

    # Categorical accuracy
    print("\n" + "-" * 80)
    print(f"{'Categorical':<30} {'Accuracy':>8}")
    print("-" * 80)
    for k in CATEGORICAL_COLS:
        with torch.no_grad():
            preds = cat_pred[k].cpu().argmax(dim=1).numpy()
            true = Y_cat_val[k].numpy()
            acc = np.mean(preds == true)
            results[k] = {"accuracy": float(acc)}
            marker = "✓" if acc > 0.7 else ("~" if acc > 0.4 else "✗")
            print(f"  {marker} {k:<28} {acc:>8.4f}")

    # Summary
    r2_values = [v["r2"] for k, v in results.items() if "r2" in v]
    decodable = sum(1 for r in r2_values if r > 0.7)
    partial = sum(1 for r in r2_values if 0.4 < r <= 0.7)
    weak = sum(1 for r in r2_values if r <= 0.4)

    print(f"\n{'='*80}")
    print(f"  Decodable (R²>0.7): {decodable}/{len(r2_values)} variables")
    print(f"  Partial (0.4<R²≤0.7): {partial}/{len(r2_values)} variables")
    print(f"  Needs GEE (R²≤0.4): {weak}/{len(r2_values)} variables")
    print(f"{'='*80}\n")

    return results


# ─── Save/Load ────────────────────────────────────────────────────────────────

def save_model(model, stats, results, output_dir: Path):
    """Save model, normalization stats, and evaluation results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Model weights
    torch.save(model.state_dict(), output_dir / "ae_env_decoder.pt")

    # Stats for inference-time denormalization
    stats["env_continuous_cols"] = ENV_CONTINUOUS_COLS
    stats["categorical_cols"] = CATEGORICAL_COLS
    stats["ae_cols"] = AE_COLS
    with open(output_dir / "decoder_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # Per-variable R² report
    with open(output_dir / "decoder_eval.json", "w") as f:
        json.dump(results, f, indent=2)

    # Decodable variable list (R² > 0.5)
    decodable = {k: v for k, v in results.items() if v.get("r2", 0) > 0.5}
    needs_gee = {k: v for k, v in results.items()
                 if "r2" in v and v["r2"] <= 0.5}
    summary = {
        "decodable_from_ae": sorted(decodable.keys()),
        "needs_gee_call": sorted(needs_gee.keys()),
        "total_decodable": len(decodable),
        "total_needs_gee": len(needs_gee),
    }
    with open(output_dir / "decoder_routing.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved to {output_dir}/")
    print(f"  Model: ae_env_decoder.pt ({os.path.getsize(output_dir / 'ae_env_decoder.pt') / 1024:.0f} KB)")
    print(f"  Stats: decoder_stats.json")
    print(f"  Eval: decoder_eval.json")
    print(f"  Routing: decoder_routing.json")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train AE → Env decoder")
    parser.add_argument("--from-bq", action="store_true", help="Load from BigQuery")
    parser.add_argument("--from-parquet", nargs="+", help="Load from local parquet files")
    parser.add_argument("--background-parquet", help="Additional background samples parquet")
    parser.add_argument("--shards", default="0,1,2,3,4", help="Comma-separated shard indices")
    parser.add_argument("--full-table", action="store_true", help="Use full 12M+ table instead of shards")
    parser.add_argument("--max-rows", type=int, default=None, help="Limit rows per table (for testing)")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--hidden", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--val-frac", type=float, default=0.1)
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--evaluate", action="store_true", help="Evaluate existing model")
    parser.add_argument("--model-path", type=str, help="Path to existing model for evaluation")
    parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = parser.parse_args()

    print(f"Device: {args.device}")
    print(f"Targets: {len(ENV_CONTINUOUS_COLS)} continuous + {len(CATEGORICAL_COLS)} categorical")

    # ── Load data ──
    import pandas as pd

    dfs = []
    if args.from_bq:
        print("\n── Loading from BigQuery ──")
        shards = [int(s) for s in args.shards.split(",")]
        df_bq = load_from_bigquery(shards=shards, use_full=args.full_table,
                                   max_rows=args.max_rows)
        dfs.append(df_bq)

    if args.from_parquet:
        print("\n── Loading from parquet ──")
        df_pq = load_from_parquet(args.from_parquet)
        dfs.append(df_pq)

    if args.background_parquet:
        print("\n── Loading background samples ──")
        df_bg = load_from_parquet([args.background_parquet])
        print(f"  Background samples: {len(df_bg):,}")
        dfs.append(df_bg)

    if not dfs:
        print("ERROR: No data source specified. Use --from-bq or --from-parquet")
        sys.exit(1)

    df = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal rows: {len(df):,}")

    # Drop rows where AE embeddings are all NaN
    ae_null_mask = df[AE_COLS].isnull().all(axis=1)
    if ae_null_mask.any():
        print(f"Dropping {ae_null_mask.sum():,} rows with null AE embeddings")
        df = df[~ae_null_mask].reset_index(drop=True)

    # ── Train/val split (stratified by geography) ──
    n = len(df)
    np.random.seed(42)
    val_mask = np.random.random(n) < args.val_frac

    df_train = df[~val_mask].reset_index(drop=True)
    df_val = df[val_mask].reset_index(drop=True)
    print(f"Train: {len(df_train):,}  Val: {len(df_val):,}")

    # ── Prepare tensors ──
    print("\nPreparing tensors...")
    X_train, Y_cont_train, Y_cat_train, stats = prepare_tensors(df_train)
    X_val, Y_cont_val, Y_cat_val, _ = prepare_tensors(df_val, fit_stats=stats)

    print(f"  X shape: {X_train.shape}")
    print(f"  Y_cont shape: {Y_cont_train.shape}")
    print(f"  Y_cat keys: {list(Y_cat_train.keys())}")

    # ── Train ──
    print(f"\n── Training ({args.epochs} epochs, hidden={args.hidden}, "
          f"lr={args.lr}, batch_size={args.batch_size}) ──")
    t0 = time.time()

    model = train_model(
        X_train, Y_cont_train, Y_cat_train,
        X_val, Y_cont_val, Y_cat_val,
        n_epochs=args.epochs, batch_size=args.batch_size,
        lr=args.lr, hidden=args.hidden, dropout=args.dropout,
        device=args.device,
    )

    elapsed = time.time() - t0
    print(f"\nTraining completed in {elapsed:.1f}s")

    # ── Evaluate ──
    print("\n── Evaluation ──")
    results = evaluate_model(model, X_val, Y_cont_val, Y_cat_val, stats,
                             device=args.device)

    # ── Save ──
    output_dir = Path(args.output_dir)
    save_model(model, stats, results, output_dir)


if __name__ == "__main__":
    main()
