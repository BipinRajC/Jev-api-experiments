from __future__ import annotations

import pandas as pd

from src.data import audit


def test_audit_rejects_stale_missing_details_and_labels_in_model_inputs() -> None:
    now = pd.Timestamp("2026-10-20T20:00:00Z")
    matches = pd.DataFrame([{
        "match_id": "m1", "competition": "EPL", "kickoff_utc": now - pd.Timedelta(hours=32),
        "cutoff_utc": now - pd.Timedelta(hours=33), "detail_expected": True,
        "has_match_details": False, "details_pending": True,
    }])
    model_inputs = pd.DataFrame([{"match_id": "m1", "y_goals_home": 2}])
    upcoming = pd.DataFrame(columns=["match_id"])
    future_inputs = pd.DataFrame(columns=model_inputs.columns)
    market_labels = pd.DataFrame([{"match_id": "m1"}])
    quotes = pd.DataFrame(columns=["match_id", "kickoff_utc", "captured_at_utc", "available_at_cutoff"])

    report = audit.audit_frames(matches, model_inputs, upcoming, future_inputs, market_labels, quotes, now=now)

    assert report["stale_missing_details"] == 1
    assert "y_goals_home" in report["leaked_input_columns"]
    assert report["errors"]


def test_missing_detail_inside_the_daily_refresh_window_is_pending_not_overdue() -> None:
    now = pd.Timestamp("2026-10-20T20:00:00Z")
    matches = pd.DataFrame([{
        "match_id": "m1", "competition": "EPL", "kickoff_utc": now - pd.Timedelta(hours=8),
        "cutoff_utc": now - pd.Timedelta(hours=9), "detail_expected": True,
        "has_match_details": False, "details_pending": True,
    }])
    inputs = pd.DataFrame([{"match_id": "m1", "home_elo": 1500.0}])
    future = inputs.iloc[0:0].copy()
    upcoming = pd.DataFrame(columns=["match_id"])
    labels = pd.DataFrame([{"match_id": "m1"}])
    quotes = pd.DataFrame(columns=["match_id", "kickoff_utc", "captured_at_utc"])

    report = audit.audit_frames(matches, inputs, upcoming, future, labels, quotes, now=now)

    assert report["pending_details"] == 1
    assert report["stale_missing_details"] == 0
    assert report["errors"] == []
