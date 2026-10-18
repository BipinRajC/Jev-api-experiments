"""Jev-ready state construction from verified as-of features."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from src.features import asof

TEAM_BASE = (
    "elo", "elo_games", "dom_league", "dom_pos", "dom_played", "dom_pts", "dom_gd", "dom_gf", "dom_ga", "dom_ppg",
    "form_pts_5", "form_pts_10", "form_str5", "gf_5", "ga_5", "gf_10", "ga_10",
    "matches_played_total", "rest_days", "matches_14d", "matches_30d",
    "xi_continuity", "xi_prior_rating", "xi_known_players",
)
TEAM_ROLLING = tuple(
    f"{name}_{window}" for window in (5, 10)
    for _, name in (*asof.FM_ROLLING, *asof.FM_AGAINST, *asof.US_ROLLING)
)
MATCH_FIELDS = ("elo_diff", "elo_exp_home", "h2h_n", "h2h_home_ppg", "h2h_home_gd_avg")


def _clean(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def state_from_row(row: Mapping[str, Any], meta: Mapping[str, Any], *, anonymized: bool = False) -> dict[str, Any]:
    """Serialize an allowlisted as-of row; never include outcome, current-match stats, or odds."""
    fixture: dict[str, Any] = {
        "competition": _clean(row.get("competition")),
        "home_team": "Home team" if anonymized else _clean(meta.get("home_name")),
        "away_team": "Away team" if anonymized else _clean(meta.get("away_name")),
    }
    if not anonymized:
        fixture.update({
            "season_start": _clean(row.get("season_start")),
            "kickoff_utc": _clean(row.get("kickoff_utc")),
            "information_cutoff_utc": _clean(row.get("cutoff_utc")),
        })
    sides = {}
    for side in ("home", "away"):
        sides[side] = {
            key: cleaned
            for key in (*TEAM_BASE, *TEAM_ROLLING)
            if (cleaned := _clean(row.get(f"{side}_{key}"))) is not None
        }
    comparison = {
        key: cleaned for key in MATCH_FIELDS if (cleaned := _clean(row.get(key))) is not None
    }
    return {
        "schema_version": 1,
        "fixture": fixture,
        "teams": sides,
        "comparison": comparison,
        "coverage_note": "Form, rest and congestion use only competitions present in the local results cache.",
    }
