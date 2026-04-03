#!/usr/bin/env python3
"""
train_sinr_emb_only.py — Train SINR model on AlphaEarth embeddings ONLY (64-D).

Same architecture and loss as the full model, but without the 59 environmental
features. Tests whether the satellite embedding alone (which captures visual
plantation signature) outperforms the full 123-feature model for cases like
planted P. radiata where environmental features argue against the species.

Reuses existing training data parquets — just selects only the emb_XX columns.
Saves to a separate model directory (sinr_model_emb_only/) so nothing is overwritten.

Usage:
  python3 train_sinr_emb_only.py --train
  python3 train_sinr_emb_only.py --evaluate
  python3 train_sinr_emb_only.py --train --evaluate
"""

import argparse
import json
import numpy as np
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "sinr_training_data"       # reuse existing parquets
MODEL_DIR = SCRIPT_DIR / "sinr_model_emb_only"     # separate output

# Only embedding features — no environmental data
EMB_FEATURE_COLS = [f"emb_{i:02d}" for i in range(64)]

# Same hyperparameters as full model
BATCH_SIZE = 2048
NUM_EPOCHS = 12
LEARNING_RATE = 0.0005
LR_DECAY = 0.98
POS_WEIGHT = 2048.0
DROPOUT = 0.3
HIDDEN_DIM = 256
NUM_RES_BLOCKS = 4
BG_WEIGHT = 1.0


# ── Import shared components from full training script ───────────────────────

sys.path.insert(0, str(SCRIPT_DIR))
from train_sinr_model import build_model, create_datasets, create_loss_fn


# ── Training ─────────────────────────────────────────────────────────────────

def train_emb_only():
    """Train SINR on embedding features only."""
    import torch
    from torch.utils.data import DataLoader

    print("=" * 70)
    print("EMBEDDING-ONLY SINR TRAINING")
    print("=" * 70)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        print("  Device: Apple Silicon GPU (MPS)")
    else:
        device = torch.device("cpu")
        torch.set_num_threads(8)
        print("  Device: CPU (%d threads)" % torch.get_num_threads())

    # Species mapping
    with open(DATA_DIR / "species_mapping.json") as f:
        mapping = json.load(f)
    num_species = mapping["num_species"]
    print("  Species: %d" % num_species)

    # Datasets — only 64 embedding features
    feature_cols = EMB_FEATURE_COLS
    num_features = len(feature_cols)
    print("  Features: %d (embedding only, no env)" % num_features)

    SpeciesDataset = create_datasets()

    print("\n  Loading training data...")
    train_dataset = SpeciesDataset(DATA_DIR / "train.parquet", feature_cols)
    normalize_stats = train_dataset.get_normalize_stats()

    print("  Loading validation data...")
    val_dataset = SpeciesDataset(
        DATA_DIR / "val.parquet", feature_cols, normalize_stats=normalize_stats
    )

    # Save normalization stats
    np.savez(
        MODEL_DIR / "normalize_stats.npz",
        mean=normalize_stats["mean"],
        std=normalize_stats["std"],
        feature_cols=feature_cols,
    )

    use_pin = (device.type == "cuda")
    loader_workers = 0  # MPS/CPU safe

    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=loader_workers, pin_memory=use_pin, drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=BATCH_SIZE * 2, shuffle=False,
        num_workers=loader_workers, pin_memory=use_pin,
    )

    # Model
    SINRModel = build_model()
    model = SINRModel(
        num_features=num_features,
        num_species=num_species,
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_RES_BLOCKS,
        dropout=DROPOUT,
    )
    model = model.to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print("\n  Model parameters: %d" % total_params)
    print("  Model size: %.1f MB" % (total_params * 4 / 1e6))
    print("  Input: 64 (vs 123 for full model)")

    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=LR_DECAY)
    loss_fn = create_loss_fn()

    print("\n  Training config:")
    print("    Batch size: %d" % BATCH_SIZE)
    print("    Epochs: %d" % NUM_EPOCHS)
    print("    LR: %s, decay: %s" % (LEARNING_RATE, LR_DECAY))
    print("    pos_weight: %s" % POS_WEIGHT)
    print("    Batches/epoch: %d" % len(train_loader))

    best_val_loss = float("inf")
    train_history = []

    for epoch in range(NUM_EPOCHS):
        epoch_t0 = time.time()

        # Train
        model.train()
        train_loss_sum = 0.0
        train_batches = 0

        for batch_idx, (features, species_idx, sample_weight) in enumerate(train_loader):
            features = features.to(device)
            species_idx = species_idx.to(device)
            sample_weight = sample_weight.to(device)

            logits = model(features)

            bg_indices = np.random.randint(0, len(train_dataset), BATCH_SIZE)
            bg_features_np = train_dataset.features[bg_indices]
            bg_features_t = torch.from_numpy(bg_features_np).to(device)
            bg_logits = model(bg_features_t)

            loss = loss_fn(logits, species_idx, sample_weight, bg_logits)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss_sum += loss.item()
            train_batches += 1

            if batch_idx % 200 == 0:
                avg_loss = train_loss_sum / train_batches
                elapsed = time.time() - epoch_t0
                eta = elapsed / max(batch_idx + 1, 1) * (len(train_loader) - batch_idx - 1)
                print(
                    "    Epoch %d/%d [%d/%d] loss=%.6f lr=%.6f ETA=%.1fmin"
                    % (epoch+1, NUM_EPOCHS, batch_idx, len(train_loader),
                       avg_loss, scheduler.get_last_lr()[0], eta/60)
                )

        avg_train_loss = train_loss_sum / train_batches

        # Validate
        model.eval()
        val_loss_sum = 0.0
        val_batches = 0
        top10_correct = 0
        top50_correct = 0
        val_total = 0

        with torch.no_grad():
            for features, species_idx, sample_weight in val_loader:
                features = features.to(device)
                species_idx = species_idx.to(device)
                sample_weight = sample_weight.to(device)

                logits = model(features)
                loss = loss_fn(logits, species_idx, sample_weight)
                val_loss_sum += loss.item()
                val_batches += 1

                probs = torch.sigmoid(logits)
                _, top50_indices = probs.topk(50, dim=1)
                _, top10_indices = probs.topk(10, dim=1)

                for i in range(len(species_idx)):
                    target = species_idx[i].item()
                    if target in top50_indices[i]:
                        top50_correct += 1
                    if target in top10_indices[i]:
                        top10_correct += 1
                    val_total += 1

        avg_val_loss = val_loss_sum / val_batches
        top10_acc = top10_correct / val_total if val_total > 0 else 0
        top50_acc = top50_correct / val_total if val_total > 0 else 0

        epoch_time = time.time() - epoch_t0
        scheduler.step()

        print(
            "\n  Epoch %d/%d complete in %.1fmin | train_loss=%.6f | "
            "val_loss=%.6f | top10=%.4f | top50=%.4f\n"
            % (epoch+1, NUM_EPOCHS, epoch_time/60, avg_train_loss,
               avg_val_loss, top10_acc, top50_acc)
        )

        train_history.append({
            "epoch": epoch + 1,
            "train_loss": avg_train_loss,
            "val_loss": avg_val_loss,
            "top10_accuracy": top10_acc,
            "top50_accuracy": top50_acc,
            "lr": scheduler.get_last_lr()[0],
            "time_min": epoch_time / 60,
        })

        # Save best
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "num_features": num_features,
                "num_species": num_species,
                "hidden_dim": HIDDEN_DIM,
                "num_blocks": NUM_RES_BLOCKS,
                "dropout": DROPOUT,
                "epoch": epoch + 1,
                "val_loss": avg_val_loss,
                "top10_accuracy": top10_acc,
                "top50_accuracy": top50_acc,
            }, MODEL_DIR / "best_model.pt")
            print("    >>> Saved best model (val_loss=%.6f)" % avg_val_loss)

        # Save latest
        torch.save({
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "num_features": num_features,
            "num_species": num_species,
            "hidden_dim": HIDDEN_DIM,
            "num_blocks": NUM_RES_BLOCKS,
            "dropout": DROPOUT,
            "epoch": epoch + 1,
        }, MODEL_DIR / "latest_checkpoint.pt")

    # Save history
    with open(MODEL_DIR / "training_history.json", "w") as f:
        json.dump(train_history, f, indent=2)

    print("\n  Training complete!")
    print("  Best val_loss: %.6f" % best_val_loss)
    print("  Model saved to: %s/best_model.pt" % MODEL_DIR)


# ── Evaluation ───────────────────────────────────────────────────────────────

def evaluate_emb_only():
    """Evaluate the embedding-only model."""
    import torch
    from torch.utils.data import DataLoader

    print("=" * 70)
    print("EMBEDDING-ONLY MODEL EVALUATION")
    print("=" * 70)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    checkpoint = torch.load(MODEL_DIR / "best_model.pt", map_location=device, weights_only=True)

    SINRModel = build_model()
    model = SINRModel(
        num_features=checkpoint["num_features"],
        num_species=checkpoint["num_species"],
        hidden_dim=checkpoint["hidden_dim"],
        num_blocks=checkpoint["num_blocks"],
        dropout=checkpoint["dropout"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    print("  Loaded model from epoch %d" % checkpoint["epoch"])
    print("  Val loss: %.6f" % checkpoint["val_loss"])
    print("  Top-10 accuracy: %.4f" % checkpoint["top10_accuracy"])
    print("  Top-50 accuracy: %.4f" % checkpoint["top50_accuracy"])

    # Species mapping
    with open(DATA_DIR / "species_mapping.json") as f:
        mapping = json.load(f)
    idx_to_species = {v: k for k, v in mapping["species_to_idx"].items()}

    # Normalization stats
    stats = np.load(MODEL_DIR / "normalize_stats.npz", allow_pickle=True)
    mean = stats["mean"]
    std = stats["std"]

    # Validation metrics
    print("\n  Running detailed evaluation on validation set...")
    SpeciesDataset = create_datasets()
    val_dataset = SpeciesDataset(
        DATA_DIR / "val.parquet", EMB_FEATURE_COLS,
        normalize_stats={"mean": mean, "std": std}
    )
    val_loader = DataLoader(val_dataset, batch_size=4096, shuffle=False)

    species_correct_top10 = {}
    species_correct_top50 = {}
    species_total = {}
    rank_sum = 0
    rank_count = 0

    with torch.no_grad():
        for features, species_idx, _ in val_loader:
            features = features.to(device)
            probs = torch.sigmoid(model(features))
            sorted_indices = probs.argsort(dim=1, descending=True)

            for i in range(len(species_idx)):
                target = species_idx[i].item()
                taxon = idx_to_species.get(target, str(target))
                rank = (sorted_indices[i] == target).nonzero(as_tuple=True)[0].item()
                rank_sum += rank
                rank_count += 1

                if taxon not in species_total:
                    species_total[taxon] = 0
                    species_correct_top10[taxon] = 0
                    species_correct_top50[taxon] = 0
                species_total[taxon] += 1

                if rank < 10:
                    species_correct_top10[taxon] += 1
                if rank < 50:
                    species_correct_top50[taxon] += 1

    mean_rank = rank_sum / rank_count if rank_count > 0 else 0

    print("\n  Overall metrics (embedding-only):")
    print("    Mean rank of true species: %.1f / %d (%.2f%%)" % (
        mean_rank, checkpoint["num_species"],
        mean_rank / checkpoint["num_species"] * 100))
    print("    Top-10 recall: %.4f" % (sum(species_correct_top10.values()) / rank_count))
    print("    Top-50 recall: %.4f" % (sum(species_correct_top50.values()) / rank_count))

    # P. radiata
    radiata_ids = [k for k in species_total if k.startswith("GymPiPiPnCx50820")]
    if radiata_ids:
        print("\n  P. radiata performance:")
        for tid in sorted(radiata_ids):
            t10 = species_correct_top10.get(tid, 0)
            t50 = species_correct_top50.get(tid, 0)
            tot = species_total[tid]
            print("    %s: top10=%d/%d (%.1f%%), top50=%d/%d (%.1f%%)" % (
                tid, t10, tot, 100*t10/tot, t50, tot, 100*t50/tot))

    # Compare with full model
    full_model_path = SCRIPT_DIR / "sinr_model" / "best_model.pt"
    if full_model_path.exists():
        full_ckpt = torch.load(full_model_path, map_location="cpu", weights_only=True)
        print("\n  Comparison with full model (123 features):")
        print("    Full model  — top10=%.4f, top50=%.4f, val_loss=%.6f" % (
            full_ckpt["top10_accuracy"], full_ckpt["top50_accuracy"], full_ckpt["val_loss"]))
        print("    Emb-only    — top10=%.4f, top50=%.4f, val_loss=%.6f" % (
            checkpoint["top10_accuracy"], checkpoint["top50_accuracy"], checkpoint["val_loss"]))


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train embedding-only SINR model")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate the model")
    args = parser.parse_args()

    if not args.train and not args.evaluate:
        parser.error("Specify --train, --evaluate, or both")

    if args.train:
        train_emb_only()
    if args.evaluate:
        evaluate_emb_only()


if __name__ == "__main__":
    main()
