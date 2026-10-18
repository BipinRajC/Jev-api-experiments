#!/usr/bin/env python3
"""Experiment 024 — Settlement appender.

For every prospective prediction whose fixture has finished, appends one
settlement record per (match_id, arm) to
results/024-prospective-series/settlements.jsonl, joining the frozen market
labels by match_id. Settlement records NEVER modify predictions.jsonl; each
record contains the label values, the label-source row identity, and the
settlement time. Running it repeatedly is safe: (match_id, arm) keys already
settled are skipped.

Labels are the 90-minute market labels from data/derived/market_labels.parquet:
result_90 (H/D/A), goals per team, over_2_5, btts_yes, corner_total_90 (nullable
on conflicts). A settlement with label_valid_90 false or a null corner label
records the label as unavailable rather than guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.utils import utc_now_iso  # noqa: E402

EXPERIMENT_ID = "024-prospective-series"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PREDICTIONS_PATH = RESULTS_DIR / "predictions.jsonl"
SETTLEMENTS_PATH = RESULTS_DIR / "settlements.jsonl"


def labels_sha256(labels_path: Path) -> str:
    return hashlib.sha256(labels_path.read_bytes()).hexdigest()


def settled_keys() -> set[str]:
    if not SETTLEMENTS_PATH.exists():
        return set()
    keys: set[str] = set()
    with SETTLEMENTS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                keys.add(rec["run_local_id"])
    return keys


def append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        fh.flush()
        import os

        os.fsync(fh.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would settle without writing",
    )
    args = parser.parse_args(argv)

    if not PREDICTIONS_PATH.exists():
        print("No prediction records yet; nothing to settle.")
        return 0

    labels_path = DERIVED_DIR / "market_labels.parquet"
    labels = pd.read_parquet(labels_path)
    label_rows = labels.set_index("match_id")
    done = settled_keys()

    predictions: dict[str, list[dict[str, Any]]] = {}
    with PREDICTIONS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            predictions.setdefault(rec["match_id"], []).append(rec)

    settled = skipped = 0
    labels_hash = labels_sha256(labels_path)
    for match_id, recs in predictions.items():
        if match_id not in label_rows.index:
            continue  # not finished (or not in labels); try again after later refreshes
        row = label_rows.loc[match_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]  # duplicate ids are audited to zero; defensive
        settlement = {
            "experiment_id": EXPERIMENT_ID,
            "match_id": match_id,
            "settled_at_utc": utc_now_iso(),
            "labels_source": "data/derived/market_labels.parquet",
            "labels_sha256": labels_hash,
            "kickoff_utc": str(row.get("kickoff_utc", ""))
            if "kickoff_utc" in row
            else None,
            "label_valid_90": bool(row["label_valid_90"])
            if pd.notna(row["label_valid_90"])
            else False,
            "goals_home_90": None
            if pd.isna(row["goals_home_90"])
            else float(row["goals_home_90"]),
            "goals_away_90": None
            if pd.isna(row["goals_away_90"])
            else float(row["goals_away_90"]),
            "result_90": None if pd.isna(row["result_90"]) else str(row["result_90"]),
            "over_2_5": None if pd.isna(row["over_2_5"]) else bool(row["over_2_5"]),
            "btts_yes": None if pd.isna(row["btts_yes"]) else bool(row["btts_yes"]),
            "corner_total_90": None
            if pd.isna(row["corner_total_90"])
            else float(row["corner_total_90"]),
            "corner_conflict": bool(row["corner_conflict"])
            if pd.notna(row["corner_conflict"])
            else False,
        }
        for rec in recs:
            key = rec["run_local_id"]
            if key in done:
                skipped += 1
                continue
            record = dict(settlement)
            record["run_local_id"] = key
            record["arm"] = rec["arm"]
            record["prediction_validation"] = rec.get("validation")
            record["pre_cutoff"] = rec.get("pre_cutoff")
            if not args.dry_run:
                append(SETTLEMENTS_PATH, record)
            settled += 1
    print(
        f"settlement records written: {settled}, already settled (skipped): {skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
