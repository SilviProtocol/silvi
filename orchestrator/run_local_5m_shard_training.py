#!/usr/bin/env python3
"""
Run strict v3 preview training across deterministic 5M shards on local Apple Silicon.

Flow per shard:
1) Export shard table from BigQuery to GCS parquet.
2) Copy parquet locally into a dedicated shard directory.
3) Train one stage with train_on_vm.py, resuming previous checkpoint.

This keeps RAM pressure lower than loading all 5M rows at once.
"""

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(command: list[str], dry_run: bool, retries: int = 0, retry_delay_s: int = 8) -> None:
    pretty = " ".join(shlex.quote(part) for part in command)
    log(f"$ {pretty}")
    if dry_run:
        return
    attempt = 0
    while True:
        attempt += 1
        try:
            subprocess.run(command, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt > retries:
                raise
            log(f"Command failed (attempt {attempt}/{retries + 1}); retrying in {retry_delay_s}s...")
            time.sleep(retry_delay_s)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential local training over 5 deterministic 1M shards"
    )
    parser.add_argument("--project-id", default="treekipedia-479918")
    parser.add_argument("--dataset", default="species_data")
    parser.add_argument(
        "--table-prefix",
        default="sinr_v3_unified_strict_train_v30_medium_5m_s",
        help="Prefix for shard tables ending in 0..N-1",
    )
    parser.add_argument("--num-shards", type=int, default=5)
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--end-shard", type=int, default=4)
    parser.add_argument(
        "--gcs-prefix",
        default="gs://treekipedia-479918-sinr-v3/local-5m-shards",
        help="GCS prefix used for intermediate parquet export",
    )
    parser.add_argument(
        "--local-data-root",
        default="~/data_5m_shards",
        help="Root containing per-shard directories",
    )
    parser.add_argument("--model-dir", default="~/model_local_5m")
    parser.add_argument("--batch-size", type=int, default=1536)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    parser.add_argument("--mapping-contract", default=None)
    parser.add_argument("--frozen-cont-stats", default=None)
    parser.add_argument("--frozen-temporal-stats", default=None)
    parser.add_argument("--artifact-version", default=None)
    parser.add_argument("--require-full-contract", action="store_true")
    parser.add_argument("--feature-contract", default=None)
    parser.add_argument("--species-frequency-contract", default=None)
    parser.add_argument("--intro-ratio-contract", default=None)
    parser.add_argument("--zero-phylo-input", action="store_true")
    parser.add_argument("--disable-intro-in-gate", action="store_true")
    parser.add_argument("--disable-intro-residual", action="store_true")
    parser.add_argument("--loss-mode", choices=["bce", "an_full"], default="bce")
    parser.add_argument("--an-pos-weight", type=float, default=2048.0)
    parser.add_argument("--hard-cap-per-species", type=int, default=0)
    parser.add_argument("--weight-mode", choices=["gamma", "effective_cap"], default="gamma",
                        help="Species frequency weighting: gamma or effective_cap")
    parser.add_argument("--effective-cap", type=int, default=0,
                        help="Effective sample cap for --weight-mode effective_cap")
    parser.add_argument("--bg-weight", type=float, default=0.0)
    parser.add_argument("--disable-boost-in-training", action="store_true")
    parser.add_argument("--use-location-encoding", action="store_true",
                        help="Add sinusoidal lat/lon encoding as model input")
    parser.add_argument("--use-temporal-magnitude", action="store_true",
                        help="Add inter-year AE magnitude features to temporal branch")
    parser.add_argument("--no-boost", action="store_true",
                        help="Remove planted boost mechanism entirely (v18+)")
    parser.add_argument("--planted-as-land-state", action="store_true",
                        help="Add is_planted as 6th land_state dim (v18+)")
    parser.add_argument("--planted-aux-pos-weight", type=float, default=1.0,
                        help="Positive class weight for planted aux BCE")
    parser.add_argument("--aux-planted-weight", type=float, default=None)
    parser.add_argument("--aux-land-state-weight", type=float, default=None)
    parser.add_argument(
        "--planted-label-mode",
        choices=["legacy_gt1", "strict_planted3", "land_state2"],
        default="legacy_gt1",
    )
    parser.add_argument(
        "--epochs-per-shard",
        type=int,
        default=1,
        help="Epochs added per shard stage (default: 1)",
    )
    parser.add_argument(
        "--initial-epoch",
        type=int,
        default=0,
        help="Set >0 when continuing an already-trained model",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Number of full cycles through all shards (default: 1)",
    )
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--keep-gcs", action="store_true")
    parser.add_argument("--copy-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def ensure_in_range(start: int, end: int, num_shards: int) -> None:
    if not (0 <= start < num_shards):
        raise ValueError(f"start-shard must be in [0, {num_shards - 1}]")
    if not (0 <= end < num_shards):
        raise ValueError(f"end-shard must be in [0, {num_shards - 1}]")
    if end < start:
        raise ValueError("end-shard must be >= start-shard")


def main() -> int:
    args = parse_args()
    ensure_in_range(args.start_shard, args.end_shard, args.num_shards)

    repo_root = Path(__file__).resolve().parent.parent
    trainer = repo_root / "orchestrator" / "train_on_vm.py"
    if not trainer.exists():
        raise FileNotFoundError(f"Missing trainer: {trainer}")

    local_data_root = Path(os.path.expanduser(args.local_data_root))
    model_dir = Path(os.path.expanduser(args.model_dir))
    local_data_root.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    log("Starting local shard training pipeline")
    log(
        "Shards: "
        f"{args.start_shard}..{args.end_shard} | "
        f"batch={args.batch_size} | epochs-per-shard={args.epochs_per_shard} | "
        f"cycles={args.cycles}"
    )

    current_epoch = args.initial_epoch
    for cycle in range(args.cycles):
        if args.cycles > 1:
            log(f"=== Cycle {cycle + 1}/{args.cycles} ===")
        for shard in range(args.start_shard, args.end_shard + 1):
            table = f"{args.table_prefix}{shard}"
            table_ref = f"{args.project_id}:{args.dataset}.{table}"
            shard_data_dir = local_data_root / f"s{shard}"
            shard_data_dir.mkdir(parents=True, exist_ok=True)

            gcs_shard_prefix = f"{args.gcs_prefix}/s{shard}"
            gcs_glob = f"{gcs_shard_prefix}/unified_*.parquet"

            log(f"--- Cycle {cycle + 1} / Shard s{shard} ({table}) ---")
            if not args.skip_export:
                run_cmd(
                    [
                        "bq",
                        "extract",
                        "--destination_format=PARQUET",
                        "--compression=SNAPPY",
                        table_ref,
                        gcs_glob,
                    ],
                    dry_run=args.dry_run,
                )
                run_cmd(
                    [
                        "gsutil",
                        "-o",
                        "GSUtil:parallel_process_count=1",
                        "-m",
                        "cp",
                        gcs_glob,
                        str(shard_data_dir),
                    ],
                    dry_run=args.dry_run,
                    retries=args.copy_retries,
                )

            target_epoch = current_epoch + args.epochs_per_shard
            train_cmd = [
                sys.executable,
                str(trainer),
                "--train",
                "--epochs",
                str(target_epoch),
                "--batch-size",
                str(args.batch_size),
                "--device",
                args.device,
                "--data-dir",
                str(shard_data_dir),
                "--model-dir",
                str(model_dir),
            ]
            if current_epoch > 0:
                train_cmd.extend(["--resume", f"epoch_{current_epoch}"])
            if args.mapping_contract:
                train_cmd.extend(["--mapping-contract", args.mapping_contract])
            if args.frozen_cont_stats:
                train_cmd.extend(["--frozen-cont-stats", args.frozen_cont_stats])
            if args.frozen_temporal_stats:
                train_cmd.extend(["--frozen-temporal-stats", args.frozen_temporal_stats])
            if args.artifact_version:
                train_cmd.extend(["--artifact-version", args.artifact_version])
            if args.require_full_contract:
                train_cmd.append("--require-full-contract")
            if args.feature_contract:
                train_cmd.extend(["--feature-contract", args.feature_contract])
            if args.species_frequency_contract:
                train_cmd.extend(["--species-frequency-contract", args.species_frequency_contract])
            if args.intro_ratio_contract:
                train_cmd.extend(["--intro-ratio-contract", args.intro_ratio_contract])
            if args.zero_phylo_input:
                train_cmd.append("--zero-phylo-input")
            if args.disable_intro_in_gate:
                train_cmd.append("--disable-intro-in-gate")
            if args.disable_intro_residual:
                train_cmd.append("--disable-intro-residual")
            if args.loss_mode:
                train_cmd.extend(["--loss-mode", args.loss_mode])
            if args.loss_mode == "an_full":
                train_cmd.extend(["--an-pos-weight", str(args.an_pos_weight)])
            if args.planted_label_mode:
                train_cmd.extend(["--planted-label-mode", args.planted_label_mode])
            if args.hard_cap_per_species > 0:
                train_cmd.extend(["--hard-cap-per-species", str(args.hard_cap_per_species)])
            if args.weight_mode != "gamma":
                train_cmd.extend(["--weight-mode", args.weight_mode])
            if args.effective_cap > 0:
                train_cmd.extend(["--effective-cap", str(args.effective_cap)])
            if args.bg_weight > 0:
                train_cmd.extend(["--bg-weight", str(args.bg_weight)])
            if args.aux_planted_weight is not None:
                train_cmd.extend(["--aux-planted-weight", str(args.aux_planted_weight)])
            if args.aux_land_state_weight is not None:
                train_cmd.extend(["--aux-land-state-weight", str(args.aux_land_state_weight)])
            if args.disable_boost_in_training:
                train_cmd.append("--disable-boost-in-training")
            if args.use_location_encoding:
                train_cmd.append("--use-location-encoding")
            if args.use_temporal_magnitude:
                train_cmd.append("--use-temporal-magnitude")
            if args.no_boost:
                train_cmd.append("--no-boost")
            if args.planted_as_land_state:
                train_cmd.append("--planted-as-land-state")
            if args.planted_aux_pos_weight != 1.0:
                train_cmd.extend(["--planted-aux-pos-weight", str(args.planted_aux_pos_weight)])

            run_cmd(train_cmd, dry_run=args.dry_run)
            current_epoch = target_epoch

            if not args.keep_gcs and not args.skip_export:
                run_cmd(["gsutil", "-m", "rm", gcs_glob], dry_run=args.dry_run)

    log(
        "Completed shard sequence. "
        f"Final checkpoint target: checkpoint_epoch_{current_epoch}.pt in {model_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
