"""Canonical outcome labels for football market experiments."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _number(value: Any) -> bool:
    return value is not None and bool(pd.notna(value))


def build_market_labels(matches: pd.DataFrame, team_stats: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """One row per fixture; disputed results or inconsistent corner sources have no label."""
    fm_corners: dict[str, dict[bool, float]] = {}
    if not team_stats.empty:
        for rec in team_stats.itertuples(index=False):
            value = getattr(rec, "corners_90", None)
            if _number(value):
                fm_corners.setdefault(rec.match_id, {})[bool(rec.is_home)] = float(value)
    fd_corners: dict[str, tuple[float, float]] = {}
    if not odds.empty:
        for rec in odds.itertuples(index=False):
            home, away = getattr(rec, "fd_stat_HC", None), getattr(rec, "fd_stat_AC", None)
            if _number(home) and _number(away):
                fd_corners[rec.match_id] = (float(home), float(away))

    rows: list[dict[str, Any]] = []
    for rec in matches.itertuples(index=False):
        home, away = rec.goals_90_home, rec.goals_90_away
        valid = _number(home) and _number(away) and not bool(rec.result_unreliable)
        row: dict[str, Any] = {
            "match_id": rec.match_id,
            "competition": rec.competition,
            "label_valid_90": valid,
            "result_90": None,
            "goals_home_90": None,
            "goals_away_90": None,
            "total_goals_90": None,
            "over_2_5": None,
            "btts_yes": None,
            "corner_total_90": None,
            "corner_source": None,
            "corner_conflict": False,
        }
        if valid:
            gh, ga = int(home), int(away)
            row.update({
                "result_90": "H" if gh > ga else "D" if gh == ga else "A",
                "goals_home_90": gh,
                "goals_away_90": ga,
                "total_goals_90": gh + ga,
                "over_2_5": gh + ga >= 3,
                "btts_yes": gh > 0 and ga > 0,
            })
            fm = fm_corners.get(rec.match_id, {})
            fm_total = fm[True] + fm[False] if True in fm and False in fm else None
            fd = fd_corners.get(rec.match_id)
            fd_total = fd[0] + fd[1] if fd else None
            if fm_total is not None and fd_total is not None:
                row["corner_conflict"] = fm_total != fd_total
                if not row["corner_conflict"]:
                    row["corner_total_90"] = fm_total
                    row["corner_source"] = "fotmob+footballdata"
            elif fm_total is not None:
                row["corner_total_90"] = fm_total
                row["corner_source"] = "fotmob"
            elif fd_total is not None:
                row["corner_total_90"] = fd_total
                row["corner_source"] = "footballdata"
        rows.append(row)
    return pd.DataFrame(rows)
