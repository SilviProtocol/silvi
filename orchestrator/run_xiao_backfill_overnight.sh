#!/bin/bash
# Xiao backfill overnight runner — shard-first, then full BQ
# 2026-03-08 v2 — threaded getInfo() approach
#
# Priority order:
#   1. Backfill 3.78M shard coords (Phase A → B → C) — ~2-3h, enables local retraining
#   2. Expand to full 12.7M BQ coords (Phase A-full → B → C → D) — ~8-10h more, fixes BQ tables
#
set -e
cd "$(dirname "$0")/.."

LOG="orchestrator/backfill_xiao_shards.log"
echo "[$(date)] ============================================" >> "$LOG"
echo "[$(date)] OVERNIGHT RUNNER STARTED (v2 threaded)" >> "$LOG"
echo "[$(date)] ============================================" >> "$LOG"

echo "[$(date)] === STEP 1: Shard-only backfill (a → b → c) ===" >> "$LOG"
python3 orchestrator/backfill_xiao_shards.py --phase all --shard-dir ~/data_5m_shards

echo "[$(date)] === STEP 2: Expand to full 12.7M coords (a-full → b → c → d) ===" >> "$LOG"
python3 orchestrator/backfill_xiao_shards.py --phase a-full
python3 orchestrator/backfill_xiao_shards.py --phase b
python3 orchestrator/backfill_xiao_shards.py --phase d

echo "[$(date)] ============================================" >> "$LOG"
echo "[$(date)] OVERNIGHT RUNNER COMPLETE" >> "$LOG"
echo "[$(date)] ============================================" >> "$LOG"
