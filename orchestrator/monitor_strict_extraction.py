#!/usr/bin/env python3
"""Live monitor for SINR strict full extraction progress.

Tracks BigQuery row counts, process status, EE operation states, and rolling ETA.
State is persisted to orchestrator/.strict_extract_monitor_state.json.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone

import ee
from google.cloud import bigquery

PROJECT = "treekipedia-479918"
DATASET = "species_data"
NEW_TABLE = "sinr_v3_features_new_gbif_strict_full"
BACKFILL_TABLE = "sinr_v3_features_backfill_strict_full"
UNSAMPLEABLE_TABLE = "sinr_v3_strict_unsampleable_contexts"
TARGET_TOTAL = 14_710_338
STATE_FILE = "orchestrator/.strict_extract_monitor_state.json"
PROCESS_PATTERN = "unified_gee_sampler_v3_strict.py --all"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_bq_counts(client: bigquery.Client):
    q = f"""
    SELECT table_id, row_count
    FROM `{PROJECT}.{DATASET}.__TABLES__`
    WHERE table_id IN ("{NEW_TABLE}", "{BACKFILL_TABLE}", "{UNSAMPLEABLE_TABLE}")
    """
    rows = list(client.query(q).result())
    counts = {r["table_id"]: int(r["row_count"]) for r in rows}
    return {
        "new_rows": counts.get(NEW_TABLE, 0),
        "backfill_rows": counts.get(BACKFILL_TABLE, 0),
        "unsampleable_rows": counts.get(UNSAMPLEABLE_TABLE, 0),
    }


def get_ee_states():
    ee.Initialize(project=PROJECT)
    ops = ee.data.listOperations(f"projects/{PROJECT}")
    states = {}
    for op in ops:
        desc = (op.get("metadata", {}) or {}).get("description", "")
        if desc.startswith("sinr_v3_strict_new_gbif_") or desc.startswith("sinr_v3_strict_backfill_"):
            st = (op.get("metadata", {}) or {}).get("state", "UNKNOWN")
            states[st] = states.get(st, 0) + 1
    return states


def get_process_status():
    cmd = ["bash", "-lc", f"ps aux | rg '{PROCESS_PATTERN}' | rg -v rg"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.stdout.strip()


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(payload):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    client = bigquery.Client(project=PROJECT)
    t_now = now_utc()
    counts = get_bq_counts(client)
    ee_states = get_ee_states()
    proc = get_process_status()

    total_done = counts["new_rows"] + counts["backfill_rows"]
    total_remaining = max(TARGET_TOTAL - total_done, 0)

    prev = load_state()
    rolling_rph = None
    eta_hours = None

    if prev:
        prev_t = datetime.fromisoformat(prev["timestamp"])
        prev_done = int(prev["total_done"])
        dt_h = max((t_now - prev_t).total_seconds() / 3600.0, 1e-9)
        delta = total_done - prev_done
        if delta > 0:
            rolling_rph = delta / dt_h
            eta_hours = total_remaining / rolling_rph if rolling_rph > 0 else None

    payload = {
        "timestamp": t_now.isoformat(),
        "new_rows": counts["new_rows"],
        "backfill_rows": counts["backfill_rows"],
        "unsampleable_rows": counts["unsampleable_rows"],
        "total_done": total_done,
        "total_remaining": total_remaining,
        "ee_states": ee_states,
        "process_running": bool(proc),
    }
    save_state(payload)

    print(f"timestamp_utc: {payload['timestamp']}")
    print(f"process_running: {payload['process_running']}")
    print(f"new_rows: {counts['new_rows']:,}")
    print(f"backfill_rows: {counts['backfill_rows']:,}")
    print(f"unsampleable_rows: {counts['unsampleable_rows']:,}")
    print(f"total_done: {total_done:,}")
    print(f"total_remaining: {total_remaining:,}")
    print(f"ee_states: {ee_states}")
    if rolling_rph is not None:
        print(f"rolling_rows_per_hour: {rolling_rph:,.2f}")
        if eta_hours is not None:
            print(f"eta_hours: {eta_hours:,.2f}")
            print(f"eta_days: {eta_hours/24.0:,.2f}")
    else:
        print("rolling_rows_per_hour: N/A (need >=2 samples)")


if __name__ == "__main__":
    main()
