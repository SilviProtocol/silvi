#!/usr/bin/env python3
"""
Overnight local training over the full strict-good SINR v3 table.

Strategy:
1) Export full strict table to GCS parquet once.
2) Split parquet objects into balanced byte-size chunks.
3) For each chunk: copy to local, train one epoch stage, optionally clean chunk files.

This keeps per-stage RAM bounded while letting training see the full dataset.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(
    command: List[str],
    dry_run: bool,
    input_text: Optional[str] = None,
    allow_fail: bool = False,
) -> str:
    pretty = " ".join(shlex.quote(part) for part in command)
    log(f"$ {pretty}")
    if dry_run:
        return ""
    result = subprocess.run(
        command,
        check=False,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", flush=True)
    if result.returncode != 0 and not allow_fail:
        raise subprocess.CalledProcessError(
            result.returncode, command, output=result.stdout, stderr=result.stderr
        )
    return result.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full strict local overnight training")
    parser.add_argument("--project-id", default="treekipedia-479918")
    parser.add_argument("--dataset", default="species_data")
    parser.add_argument("--table", default="sinr_v3_unified_strict_train")
    parser.add_argument(
        "--gcs-prefix",
        default="gs://treekipedia-479918-sinr-v3/strict-full-export/overnight",
    )
    parser.add_argument("--target-chunks", type=int, default=24)
    parser.add_argument("--start-chunk", type=int, default=0)
    parser.add_argument("--end-chunk", type=int, default=None)
    parser.add_argument("--epochs-per-chunk", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1536)
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
    parser.add_argument(
        "--planted-label-mode",
        choices=["legacy_gt1", "strict_planted3", "land_state2"],
        default="legacy_gt1",
    )
    parser.add_argument("--model-dir", default="~/model_local_5m")
    parser.add_argument("--local-chunk-root", default="~/data_strict_full_chunks")
    parser.add_argument("--reuse-export", action="store_true")
    parser.add_argument("--keep-local-chunks", action="store_true")
    parser.add_argument("--wait-for-idle", action="store_true")
    parser.add_argument("--wait-interval-seconds", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def find_latest_epoch(model_dir: Path) -> int:
    pat = re.compile(r"^checkpoint_epoch_(\d+)\.pt$")
    latest = 0
    if not model_dir.exists():
        return 0
    for p in model_dir.iterdir():
        m = pat.match(p.name)
        if m:
            latest = max(latest, int(m.group(1)))
    return latest


def wait_for_no_active_train(interval_s: int, dry_run: bool) -> None:
    if dry_run:
        return
    while True:
        proc = subprocess.run(
            ["pgrep", "-f", "train_on_vm.py"],
            text=True,
            capture_output=True,
            check=False,
        )
        pids = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not pids:
            return
        log(f"Detected active train_on_vm.py pid(s): {', '.join(pids)}; waiting...")
        time.sleep(interval_s)


def list_objects_with_sizes(gcs_glob: str, dry_run: bool) -> List[Tuple[int, str]]:
    if dry_run:
        return []
    out = run_cmd(["gsutil", "du", gcs_glob], dry_run=False)
    entries: List[Tuple[int, str]] = []
    for line in out.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        size_s, url = parts
        if not size_s.isdigit():
            continue
        entries.append((int(size_s), url))
    if not entries:
        raise RuntimeError(f"No parquet objects found at {gcs_glob}")
    return entries


def make_balanced_chunks(entries: List[Tuple[int, str]], n_chunks: int) -> List[List[str]]:
    buckets: List[List[str]] = [[] for _ in range(n_chunks)]
    bucket_sizes = [0 for _ in range(n_chunks)]

    for size, url in sorted(entries, key=lambda x: x[0], reverse=True):
        i = min(range(n_chunks), key=lambda idx: bucket_sizes[idx])
        buckets[i].append(url)
        bucket_sizes[i] += size

    non_empty = [b for b in buckets if b]
    return non_empty


def main() -> int:
    args = parse_args()

    if args.target_chunks < 1:
        raise ValueError("target-chunks must be >= 1")

    model_dir = Path(os.path.expanduser(args.model_dir))
    local_chunk_root = Path(os.path.expanduser(args.local_chunk_root))
    model_dir.mkdir(parents=True, exist_ok=True)
    local_chunk_root.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parent.parent
    trainer = repo_root / "orchestrator" / "train_on_vm.py"
    if not trainer.exists():
        raise FileNotFoundError(f"Missing trainer script: {trainer}")

    if args.wait_for_idle:
        wait_for_no_active_train(args.wait_interval_seconds, args.dry_run)

    table_ref = f"{args.project_id}:{args.dataset}.{args.table}"
    gcs_glob = f"{args.gcs_prefix}/unified_*.parquet"

    if not args.reuse_export:
        run_cmd(["gsutil", "-m", "rm", gcs_glob], args.dry_run, allow_fail=True)
        run_cmd(
            [
                "bq",
                "extract",
                "--destination_format=PARQUET",
                "--compression=SNAPPY",
                table_ref,
                gcs_glob,
            ],
            args.dry_run,
        )

    if args.dry_run:
        log("Dry run complete.")
        return 0

    entries = list_objects_with_sizes(gcs_glob, args.dry_run)
    chunks = make_balanced_chunks(entries, args.target_chunks)
    if not chunks:
        raise RuntimeError("No chunk assignments were created")

    start_chunk = args.start_chunk
    end_chunk = args.end_chunk if args.end_chunk is not None else len(chunks) - 1
    if start_chunk < 0 or end_chunk < start_chunk or end_chunk >= len(chunks):
        raise ValueError(
            f"Chunk range invalid. start={start_chunk}, end={end_chunk}, available=0..{len(chunks)-1}"
        )

    latest_epoch = find_latest_epoch(model_dir)
    current_epoch = latest_epoch

    total_bytes = sum(size for size, _ in entries)
    log(
        f"Objects: {len(entries)} | total size: {total_bytes / (1024**3):.2f} GiB | "
        f"chunks: {len(chunks)}"
    )
    log(
        f"Running chunks {start_chunk}..{end_chunk} | batch={args.batch_size} | "
        f"resume epoch base={current_epoch}"
    )

    for chunk_idx in range(start_chunk, end_chunk + 1):
        chunk_urls = chunks[chunk_idx]
        chunk_dir = local_chunk_root / f"chunk_{chunk_idx:03d}"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        log(f"--- Chunk {chunk_idx}/{len(chunks)-1}: {len(chunk_urls)} parquet objects ---")

        if not args.keep_local_chunks:
            for f in chunk_dir.glob("*.parquet"):
                if not args.dry_run:
                    f.unlink()

        manifest = "\n".join(chunk_urls) + "\n"
        run_cmd(["gsutil", "-m", "cp", "-I", str(chunk_dir)], args.dry_run, input_text=manifest)

        target_epoch = current_epoch + args.epochs_per_chunk
        train_cmd = [
            sys.executable,
            str(trainer),
            "--train",
            "--epochs",
            str(target_epoch),
            "--batch-size",
            str(args.batch_size),
            "--data-dir",
            str(chunk_dir),
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

        run_cmd(train_cmd, args.dry_run)
        current_epoch = target_epoch

        if not args.keep_local_chunks:
            for f in chunk_dir.glob("*.parquet"):
                if not args.dry_run:
                    f.unlink()

    log(
        f"Completed chunk range. Latest expected checkpoint: checkpoint_epoch_{current_epoch}.pt"
    )
    log(f"Model dir: {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
