from __future__ import annotations

import pandas as pd

from src.data import markets


def match(mid: str, home: float, away: float, *, competition: str = "EPL", unreliable: bool = False) -> dict:
    return {"match_id": mid, "competition": competition, "goals_90_home": home,
            "goals_90_away": away, "result_unreliable": unreliable}


def test_goal_markets_use_only_reliable_90_minute_scores() -> None:
    matches = pd.DataFrame([match("played", 2, 1), match("disputed", float("nan"), float("nan"), unreliable=True)])
    labels = markets.build_market_labels(matches, pd.DataFrame(), pd.DataFrame()).set_index("match_id")

    assert labels.loc["played", "result_90"] == "H"
    assert labels.loc["played", "total_goals_90"] == 3
    assert bool(labels.loc["played", "over_2_5"])
    assert bool(labels.loc["played", "btts_yes"])
    assert pd.isna(labels.loc["disputed", "result_90"])
    assert pd.isna(labels.loc["disputed", "over_2_5"])


def test_corner_total_requires_source_agreement_when_both_are_present() -> None:
    matches = pd.DataFrame([match("agree", 1, 0), match("conflict", 0, 0)])
    stats = pd.DataFrame([
        {"match_id": "agree", "is_home": True, "corners_90": 4},
        {"match_id": "agree", "is_home": False, "corners_90": 5},
        {"match_id": "conflict", "is_home": True, "corners_90": 6},
        {"match_id": "conflict", "is_home": False, "corners_90": 4},
    ])
    odds = pd.DataFrame([
        {"match_id": "agree", "fd_stat_HC": 4, "fd_stat_AC": 5},
        {"match_id": "conflict", "fd_stat_HC": 5, "fd_stat_AC": 4},
    ])
    labels = markets.build_market_labels(matches, stats, odds).set_index("match_id")

    assert labels.loc["agree", "corner_total_90"] == 9
    assert labels.loc["agree", "corner_source"] == "fotmob+footballdata"
    assert not bool(labels.loc["agree", "corner_conflict"])
    assert pd.isna(labels.loc["conflict", "corner_total_90"])
    assert bool(labels.loc["conflict", "corner_conflict"])


def test_extra_time_without_regulation_corner_split_does_not_get_a_corner_label() -> None:
    matches = pd.DataFrame([match("old_ucl", 1, 1, competition="UCL")])
    stats = pd.DataFrame([
        {"match_id": "old_ucl", "is_home": True, "corners": 9, "corners_90": None},
        {"match_id": "old_ucl", "is_home": False, "corners": 1, "corners_90": None},
    ])
    labels = markets.build_market_labels(matches, stats, pd.DataFrame()).iloc[0]

    assert pd.isna(labels["corner_total_90"])
    assert pd.isna(labels["corner_source"])
