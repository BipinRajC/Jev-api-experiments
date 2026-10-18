"""Integrity gates for the derived football data layer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

DETAIL_OVERDUE_AFTER = pd.Timedelta(hours=28)  # 4-hour settle rule plus the daily refresh interval


def audit_frames(
    matches: pd.DataFrame,
    model_inputs: pd.DataFrame,
    upcoming: pd.DataFrame,
    upcoming_inputs: pd.DataFrame,
    market_labels: pd.DataFrame,
    forward_quotes: pd.DataFrame,
    *,
    now: datetime | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Return a machine-readable report; errors mean the derived release is unsafe to ingest."""
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    errors: list[str] = []
    duplicates = {
        name: int(df.match_id.duplicated().sum())
        for name, df in (("matches", matches), ("model_inputs", model_inputs),
                         ("upcoming", upcoming), ("upcoming_inputs", upcoming_inputs),
                         ("market_labels", market_labels))
    }
    for name, count in duplicates.items():
        if count:
            errors.append(f"{name} has {count} duplicate match IDs")
    stale_missing = int((
        matches["detail_expected"] & ~matches["has_match_details"]
        & (matches["kickoff_utc"] <= now - DETAIL_OVERDUE_AFTER)
    ).sum())
    if stale_missing:
        errors.append(f"{stale_missing} finished target matches older than 28 hours lack match details")
    late_cutoffs = int((matches["cutoff_utc"] > matches["kickoff_utc"] - pd.Timedelta(minutes=60)).sum())
    if late_cutoffs:
        errors.append(f"{late_cutoffs} historical cutoffs are later than kickoff minus 60 minutes")
    leaked = [c for c in model_inputs if c.startswith("y_") or c in {"result_90", "result_unreliable"}]
    leaked += [c for c in upcoming_inputs if (c.startswith("y_") or c in {"result_90", "result_unreliable"}) and c not in leaked]
    if leaked:
        errors.append(f"outcome columns are present in model inputs: {leaked}")
    if set(model_inputs.columns) != set(upcoming_inputs.columns):
        errors.append("historical and upcoming model input schemas differ")
    if set(market_labels.match_id) != set(matches.match_id):
        errors.append("market labels do not cover exactly the matches table")
    if set(upcoming_inputs.match_id) != set(upcoming.match_id):
        errors.append("upcoming inputs do not cover exactly the upcoming fixture table")
    quote_errors = 0
    if not forward_quotes.empty:
        quote_errors = int((forward_quotes.captured_at_utc >= forward_quotes.kickoff_utc).sum())
        if quote_errors:
            errors.append(f"{quote_errors} quote rows were captured at or after kickoff")
        attached = set(forward_quotes.match_id.dropna())
        if not attached.issubset(set(matches.match_id) | set(upcoming.match_id)):
            errors.append("quotes reference unknown match IDs")
    return {
        "rows": {"matches": len(matches), "model_inputs": len(model_inputs),
                 "upcoming": len(upcoming), "upcoming_inputs": len(upcoming_inputs),
                 "market_labels": len(market_labels), "forward_quotes": len(forward_quotes)},
        "stale_missing_details": stale_missing,
        "pending_details": int((matches["detail_expected"] & ~matches["has_match_details"]).sum()),
        "score_conflicts": int(matches["score_conflict"].sum()) if "score_conflict" in matches else 0,
        "kickoff_disagreements": int(matches["kickoff_disagreement"].sum()) if "kickoff_disagreement" in matches else 0,
        "corner_conflicts": int(market_labels["corner_conflict"].sum()) if "corner_conflict" in market_labels else 0,
        "unmatched_quote_rows": int(forward_quotes.match_id.isna().sum()) if "match_id" in forward_quotes else 0,
        "late_cutoffs": late_cutoffs,
        "duplicate_ids": duplicates,
        "leaked_input_columns": leaked,
        "invalid_quote_capture_times": quote_errors,
        "errors": errors,
    }


def audit_derived(derived_dir: Path) -> dict[str, Any]:
    read = lambda name: pd.read_parquet(derived_dir / f"{name}.parquet")  # noqa: E731
    return audit_frames(
        read("matches"), read("model_inputs"), read("upcoming"), read("upcoming_inputs"),
        read("market_labels"), read("forward_quotes"),
    )
