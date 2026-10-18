from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.features import state


def test_state_uses_only_allowed_pre_match_fields_and_omits_missing_values() -> None:
    row = {
        "competition": "EPL", "season_start": 2026,
        "kickoff_utc": datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc),
        "cutoff_utc": datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc),
        "home_elo": 1550.0, "away_elo": 1480.0,
        "home_fm_xg_for_5": 1.8, "home_xi_prior_rating": float("nan"),
        "elo_diff": 135.0,
        "y_goals_home": 4, "result_90": "H", "odds_PSCH": 1.2,
    }
    meta = {"home_name": "Arsenal", "away_name": "Chelsea", "final_home_goals": 4}

    result = state.state_from_row(row, meta)
    raw = json.dumps(result, allow_nan=False)

    assert result["fixture"]["home_team"] == "Arsenal"
    assert result["teams"]["home"]["elo"] == 1550.0
    assert result["teams"]["home"]["fm_xg_for_5"] == 1.8
    assert "xi_prior_rating" not in result["teams"]["home"]
    assert all(secret not in raw for secret in ("y_goals_home", "result_90", "odds_PSCH", "final_home_goals"))


def test_state_can_anonymize_identity_for_memorization_control() -> None:
    row = {"competition": "UCL", "season_start": 2026, "home_elo": 1600, "away_elo": 1500,
           "kickoff_utc": pd.Timestamp("2026-11-01T20:00:00Z"),
           "cutoff_utc": pd.Timestamp("2026-11-01T19:00:00Z")}
    meta = {"home_name": "Barcelona", "away_name": "Galatasaray"}

    result = state.state_from_row(row, meta, anonymized=True)
    raw = json.dumps(result, allow_nan=False)

    assert result["fixture"]["home_team"] == "Home team"
    assert result["fixture"]["away_team"] == "Away team"
    assert "Barcelona" not in raw and "Galatasaray" not in raw
