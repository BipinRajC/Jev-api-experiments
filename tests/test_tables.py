from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data import tables


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("408 (85%)", (408.0, 85.0)),
        ("2.43", (2.43, None)),
        (14, (14.0, None)),
        (None, (None, None)),
        ("n/a", (None, None)),
        ("0 (0%)", (0.0, 0.0)),
    ],
)
def test_parse_stat_value(value, expected) -> None:
    assert tables.parse_stat_value(value) == expected


def payload(*, reason: dict, home_goal_times: list[int], away_goal_times: list[int]) -> bytes:
    def goals(times: list[int], prefix: str) -> dict:
        return {f"{prefix}{i}": [{"time": t, "overloadTime": None}] for i, t in enumerate(times)}

    return json.dumps(
        {
            "general": {"matchId": "77", "homeTeam": {"id": 1, "name": "Inter"}, "awayTeam": {"id": 2, "name": "Barca"}},
            "header": {
                "status": {"reason": reason, "scoreStr": "4 - 3"},
                "events": {
                    "homeTeamGoals": goals(home_goal_times, "h"),
                    "awayTeamGoals": goals(away_goal_times, "a"),
                },
            },
            "content": {
                "matchFacts": {"infoBox": {"Referee": {"text": "S Marciniak"}, "Attendance": 60000, "Stadium": {"name": "San Siro"}}},
                "stats": {
                    "Periods": {
                        "All": {
                            "stats": [
                                {
                                    "stats": [
                                        {"key": "BallPossesion", "type": "graph", "stats": [55, 45]},
                                        {"key": "expected_goals", "type": "text", "stats": ["2.43", "0.44"]},
                                        {"key": "accurate_passes", "type": "text", "stats": ["408 (85%)", "306 (80%)"]},
                                        {"key": "shots", "type": "title", "stats": [None, None]},
                                        {"key": "some_unknown_stat", "type": "text", "stats": [1, 2]},
                                    ]
                                }
                            ]
                        }
                    }
                },
                "lineup": {
                    "homeTeam": {
                        "formation": "3-5-2",
                        "rating": 7.1,
                        "coach": {"id": 9, "name": "S Inzaghi"},
                        "starters": [{"id": 10, "name": "Lautaro", "positionId": 115, "performance": {"rating": 7.9}}],
                        "subs": [
                            {
                                "id": 11,
                                "name": "Thuram",
                                "performance": {"rating": 6.5, "substitutionEvents": [{"type": "subIn", "time": 60}]},
                            }
                        ],
                        "unavailable": [{"id": 12, "name": "X", "unavailability": {"type": "injury", "expectedReturn": "Doubtful"}}],
                    },
                    "awayTeam": {"starters": [], "subs": []},
                },
                "shotmap": {"shots": [{"id": 5, "teamId": 1, "playerId": 10, "playerName": "Lautaro", "min": 12, "expectedGoals": 0.31, "eventType": "Goal"}]},
            },
        }
    ).encode()


def test_extra_time_match_uses_goal_events_for_the_90_minute_score() -> None:
    raw = payload(
        reason={"shortKey": "afterextratime_short"},
        home_goal_times=[21, 60, 90, 99],  # 90 counts as regulation (stoppage time), 99 is extra time
        away_goal_times=[3, 70, 87],
    )
    match = tables.parse_match_details(raw, "UCL", "2024/2025")["match"]
    assert (match["events_home_goals"], match["events_away_goals"]) == (4, 3)
    assert (match["home_goals_90"], match["away_goals_90"]) == (3, 3)
    assert match["decided_by"] == "afterextratime_short"


def test_penalty_shootout_scores_are_captured() -> None:
    raw = payload(
        reason={"shortKey": "penalties_short", "penalties": [1, 4]}, home_goal_times=[], away_goal_times=[12]
    )
    match = tables.parse_match_details(raw, "UCL", "2024/2025")["match"]
    assert (match["pens_home"], match["pens_away"]) == (1, 4)


def test_parse_match_details_builds_all_row_types() -> None:
    parsed = tables.parse_match_details(
        payload(reason={"shortKey": "fulltime_short"}, home_goal_times=[10], away_goal_times=[]), "EPL", "2024/2025"
    )
    home, away = parsed["team_stats"]
    assert (home["team_id"], home["is_home"], away["team_id"], away["is_home"]) == ("1", True, "2", False)
    assert home["possession"] == 55.0 and away["xg"] == 0.44
    assert home["passes_accurate"] == 408.0 and home["passes_accurate_pct"] == 85.0
    assert "some_unknown_stat" not in home and "shots" not in home  # unknown keys and title rows are ignored
    assert (home["formation"], home["coach_name"], home["lineup_rating"]) == ("3-5-2", "S Inzaghi", 7.1)
    assert parsed["match"]["referee"] == "S Marciniak" and parsed["match"]["stadium"] == "San Siro"

    starter, sub = parsed["players"]
    assert (starter["starter"], starter["rating"], starter["sub_on_minute"]) == (True, 7.9, None)
    assert (sub["starter"], sub["sub_on_minute"]) == (False, 60)
    assert parsed["shots"][0]["xg"] == 0.31 and parsed["unavailable"][0]["type"] == "injury"


def test_attach_goals_90_prefers_events_only_when_extra_time_was_played() -> None:
    matches = pd.DataFrame(
        {
            "match_id": ["a", "b", "c"],
            "decided_by": ["fulltime_short", "afterextratime_short", "afterextratime_short"],
            "final_home_goals": [2, 4, 5],
            "final_away_goals": [1, 3, 0],
        }
    )
    details = pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "home_goals_90": [9, 3],  # for a regulation match the details value must be ignored
            "away_goals_90": [9, 3],
            "referee": ["r", "r"],
            "attendance": [1, 1],
            "stadium": ["s", "s"],
        }
    )
    out = tables.attach_goals_90(matches, details).set_index("match_id")
    assert (out.loc["a", "goals_90_home"], out.loc["a", "goals_90_away"]) == (2, 1)
    assert (out.loc["b", "goals_90_home"], out.loc["b", "goals_90_away"]) == (3, 3)
    assert pd.isna(out.loc["c", "goals_90_home"])  # extra time, but no details file -> unknown, not guessed


def test_players_and_unavailable_entries_without_ids_are_skipped_not_fatal() -> None:
    doc = json.loads(payload(reason={"shortKey": "fulltime_short"}, home_goal_times=[], away_goal_times=[]))
    team = doc["content"]["lineup"]["homeTeam"]
    team["starters"].append({"name": "No Id"})
    team["unavailable"].append({"name": "Also No Id", "unavailability": {"type": "injury"}})
    parsed = tables.parse_match_details(json.dumps(doc).encode(), "EPL", "2014/2015")
    assert [p["name"] for p in parsed["players"]] == ["Lautaro", "Thuram"]
    assert [u["name"] for u in parsed["unavailable"]] == ["X"]


def test_apply_score_conflicts_blanks_disputed_scores_instead_of_guessing() -> None:
    matches = pd.DataFrame(
        {
            "match_id": ["ok", "awarded", "forfeit", "et"],
            "decided_by": ["fulltime_short", "fulltime_short", "unspecified", "afterextratime_short"],
            "goals_90_home": [2, 0, 3, 3],
            "goals_90_away": [1, 2, 0, 3],
        }
    )
    odds = pd.DataFrame(
        {"match_id": ["ok", "awarded"], "fd_fthg": [2, 1], "fd_ftag": [1, 1], "fd_score_agrees": [True, False]}
    )
    us = pd.DataFrame(
        {"match_id": ["awarded", None], "us_goals_home": [1, 5], "us_goals_away": [1, 5], "us_score_agrees": [False, False]}
    )
    out = tables.apply_score_conflicts(matches, odds, us).set_index("match_id")
    assert pd.isna(out.loc["awarded", "goals_90_home"]) and pd.isna(out.loc["awarded", "goals_90_away"])
    assert bool(out.loc["awarded", "score_conflict"]) and bool(out.loc["awarded", "result_unreliable"])
    assert (out.loc["ok", "goals_90_home"], bool(out.loc["ok", "result_unreliable"])) == (2, False)
    assert bool(out.loc["forfeit", "result_unreliable"]) and out.loc["forfeit", "goals_90_home"] == 3
    assert out.loc["et", "goals_90_home"] == 3 and not bool(out.loc["et", "score_conflict"])
