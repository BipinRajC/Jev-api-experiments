from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from src.data import tables, teams


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


def test_extra_time_corner_stats_use_regulation_periods_only() -> None:
    doc = json.loads(payload(reason={"shortKey": "afterextratime_short"}, home_goal_times=[], away_goal_times=[]))
    def corner_group(home: int, away: int) -> dict:
        return {"stats": [{"stats": [{"key": "corners", "type": "text", "stats": [home, away]}]}]}
    doc["content"]["stats"]["Periods"] = {
        "All": corner_group(9, 1),
        "FirstHalf": corner_group(3, 0),
        "SecondHalf": corner_group(5, 0),
        "FirstExtraHalf": corner_group(1, 0),
        "SecondExtraHalf": corner_group(0, 1),
    }

    home, away = tables.parse_match_details(json.dumps(doc).encode(), "UCL", "2024/2025")["team_stats"]

    assert (home["corners"], away["corners"]) == (9.0, 1.0)
    assert (home["corners_90"], away["corners_90"]) == (8.0, 0.0)


def test_extra_time_corners_without_period_split_have_no_90_minute_label() -> None:
    doc = json.loads(payload(reason={"shortKey": "afterextratime_short"}, home_goal_times=[], away_goal_times=[]))
    doc["content"]["stats"]["Periods"]["All"]["stats"][0]["stats"].append(
        {"key": "corners", "type": "text", "stats": [9, 1]}
    )

    home, away = tables.parse_match_details(json.dumps(doc).encode(), "UCL", "2014/2015")["team_stats"]

    assert home["corners"] == 9.0 and away["corners"] == 1.0
    assert home.get("corners_90") is None and away.get("corners_90") is None


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


def test_domestic_source_joins_distinguish_regular_match_from_later_playoff(tmp_path, monkeypatch) -> None:
    """The same home/away pair met twice in Serie A 2022/23; source rows describe March, not June."""
    fixtures = pd.DataFrame(
        [
            {"match_id": "regular", "competition": "SERIEA", "season_start": 2022, "home_id": "1", "away_id": "2",
             "kickoff_utc": datetime(2023, 3, 5, 11, 30, tzinfo=timezone.utc),
             "final_home_goals": 0, "final_away_goals": 0, "decided_by": "fulltime_short"},
            {"match_id": "playoff", "competition": "SERIEA", "season_start": 2022, "home_id": "1", "away_id": "2",
             "kickoff_utc": datetime(2023, 6, 11, 18, 45, tzinfo=timezone.utc),
             "final_home_goals": 1, "final_away_goals": 3, "decided_by": "fulltime_short"},
        ]
    )
    links = {
        "1": teams.TeamLink("1", "Spezia", football_data="Spezia", understat_aliases=("Spezia",)),
        "2": teams.TeamLink("2", "Hellas Verona", football_data="Verona", understat_aliases=("Verona",)),
    }
    monkeypatch.setattr(teams, "link_league", lambda *_: links)
    fd = tmp_path / "footballdata" / "I1" / "2223.csv"
    fd.parent.mkdir(parents=True)
    fd.write_text("Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,PSCH\n05/03/2023,11:30,Spezia,Verona,0,0,2.50\n")
    us = tmp_path / "understat" / "league" / "Serie_A" / "2022.json"
    us.parent.mkdir(parents=True)
    us.write_text(json.dumps({
        "dates": [{"id": "18830", "isResult": True, "datetime": "2023-03-05 11:30:00",
                   "h": {"title": "Spezia"}, "a": {"title": "Verona"},
                   "goals": {"h": "0", "a": "0"}, "xG": {"h": "0.96", "a": "1.17"}}],
        "teams": {}, "players": [],
    }))

    odds, odds_counts = tables.build_odds(tmp_path, fixtures, range(2022, 2023))
    us_match, _, us_counts = tables.build_understat(tmp_path, fixtures, range(2022, 2023))

    assert odds_counts["joined"] == us_counts["matches_joined"] == 1
    assert odds.iloc[0]["match_id"] == "regular"
    assert us_match.iloc[0]["match_id"] == "regular"
    assert bool(odds.iloc[0]["fd_score_agrees"])
    assert bool(us_match.iloc[0]["us_score_agrees"])


def test_understat_history_follows_its_match_when_source_date_is_stale(tmp_path, monkeypatch) -> None:
    fixtures = pd.DataFrame([{
        "match_id": "resumed", "competition": "SERIEA", "season_start": 2023,
        "home_id": "1", "away_id": "2", "kickoff_utc": datetime(2024, 4, 25, 18, 0, tzinfo=timezone.utc),
        "final_home_goals": 1, "final_away_goals": 2, "decided_by": "fulltime_short",
    }])
    links = {
        "1": teams.TeamLink("1", "Udinese", understat_aliases=("Udinese",)),
        "2": teams.TeamLink("2", "Roma", understat_aliases=("Roma",)),
    }
    monkeypatch.setattr(teams, "link_league", lambda *_: links)
    us = tmp_path / "understat" / "league" / "Serie_A" / "2023.json"
    us.parent.mkdir(parents=True)
    def history(side: str, scored: int, missed: int, xg: float, xga: float) -> dict:
        return {"date": "2024-04-14 16:00:00", "h_a": side, "scored": scored, "missed": missed,
                "xG": xg, "xGA": xga, "npxG": xg, "npxGA": xga,
                "ppda": {"att": 100, "def": 10}, "deep": 4, "deep_allowed": 5, "xpts": 1.0}
    us.write_text(json.dumps({
        "dates": [{"id": "22621", "isResult": True, "datetime": "2024-04-14 16:00:00",
                   "h": {"title": "Udinese"}, "a": {"title": "Roma"},
                   "goals": {"h": "1", "a": "2"}, "xG": {"h": "0.94", "a": "1.61"}}],
        "teams": {
            "1": {"title": "Udinese", "history": [history("h", 1, 2, 0.94, 1.61)]},
            "2": {"title": "Roma", "history": [history("a", 2, 1, 1.61, 0.94)]},
        }, "players": [],
    }))

    us_match, us_team, counts = tables.build_understat(tmp_path, fixtures, range(2023, 2024))

    assert counts["matches_joined"] == 1
    assert counts["team_rows_joined"] == 2
    assert us_match.iloc[0]["match_id"] == "resumed"
    assert set(us_team.match_id) == {"resumed"}
    assert us_match.iloc[0]["us_source_datetime_text"] == "2024-04-14 16:00:00"
    assert us_match.iloc[0]["us_date_gap_days"] == 11


def test_cutoff_uses_earliest_recorded_kickoff_and_flags_large_disagreement() -> None:
    fixtures = pd.DataFrame([
        {"match_id": "delayed", "kickoff_utc": datetime(2024, 9, 1, 18, 0, tzinfo=timezone.utc)},
        {"match_id": "fm_only", "kickoff_utc": datetime(2024, 9, 1, 20, 0, tzinfo=timezone.utc)},
    ])
    odds = pd.DataFrame([{
        "match_id": "delayed", "fd_kickoff_utc": datetime(2024, 9, 1, 16, 0, tzinfo=timezone.utc)
    }])

    timed = tables.attach_source_timing(fixtures, odds).set_index("match_id")

    assert timed.loc["delayed", "cutoff_utc"] == datetime(2024, 9, 1, 15, 0, tzinfo=timezone.utc)
    assert timed.loc["delayed", "fd_kickoff_delta_min"] == 120
    assert bool(timed.loc["delayed", "kickoff_disagreement"])
    assert timed.loc["fm_only", "cutoff_utc"] == datetime(2024, 9, 1, 19, 0, tzinfo=timezone.utc)
    assert not bool(timed.loc["fm_only", "kickoff_disagreement"])


def test_upcoming_table_contains_only_future_target_fixtures(tmp_path) -> None:
    now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    def fixture(mid: str, kickoff: datetime, *, finished: bool = False, cancelled: bool = False) -> dict:
        return {"id": mid, "home": {"id": "1", "name": "Home"}, "away": {"id": "2", "name": "Away"},
                "status": {"utcTime": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "finished": finished,
                           "cancelled": cancelled, "scoreStr": "1 - 0" if finished else None}}
    for comp in ("EPL", "TURKEY"):
        path = tmp_path / "fotmob" / "league" / comp / "2026-2027.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"fixtures": {"allMatches": [
            fixture(f"{comp}-future", now + pd.Timedelta(days=2)),
            fixture(f"{comp}-past", now - pd.Timedelta(days=2)),
            fixture(f"{comp}-done", now - pd.Timedelta(days=1), finished=True),
            fixture(f"{comp}-cancelled", now + pd.Timedelta(days=1), cancelled=True),
        ]}}))

    upcoming = tables.build_upcoming(tmp_path, as_of=now)

    assert upcoming.match_id.tolist() == ["EPL-future"]
    assert upcoming.iloc[0]["cutoff_utc"] == now + pd.Timedelta(days=2, minutes=-60)
