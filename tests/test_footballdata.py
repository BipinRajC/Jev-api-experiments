from __future__ import annotations

from datetime import datetime, timezone

from src.data import footballdata, fotmob, understat

HEADER = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HS,AS,Referee,PSH,PSD,PSA,PSCH,AHh\n"


def csv_bytes(*rows: str, bom: bool = True) -> bytes:
    text = HEADER + "".join(r + "\n" for r in rows)
    return (("﻿" if bom else "") + text).encode("utf-8")


def test_season_helpers() -> None:
    assert footballdata.season_code(2024) == "2425"
    assert footballdata.season_code(1999) == "9900"
    assert footballdata.season_label(2024) == "2024-25"
    assert footballdata.csv_url("SP1", 2025) == "https://football-data.co.uk/mmz4281/2526/SP1.csv"


def test_parse_converts_uk_local_kickoff_to_utc_in_bst_and_gmt() -> None:
    raw = csv_bytes(
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,14,10,R Jones,1.63,4.38,5.30,1.65,-1",
        "E0,05/01/2025,16:30,Liverpool,Man United,2,2,D,19,13,M Oliver,1.29,6.14,9.37,1.36,-1.75",
    )
    bst, gmt = footballdata.parse_csv(raw, "E0", 2024)
    assert bst.kickoff_utc == datetime(2024, 8, 16, 19, 0, tzinfo=timezone.utc)
    assert gmt.kickoff_utc == datetime(2025, 1, 5, 16, 30, tzinfo=timezone.utc)


def test_parse_splits_stats_odds_and_keeps_core_fields() -> None:
    raw = csv_bytes("E0,16/08/2024,20:00,Man United,Fulham,1,0,H,14,10,R Jones,1.63,4.38,5.30,1.65,-1")
    (m,) = footballdata.parse_csv(raw, "E0", 2024)
    assert (m.home, m.away, m.fthg, m.ftag, m.ftr, m.referee) == ("Man United", "Fulham", 1, 0, "H", "R Jones")
    assert m.stats == {"HS": 14.0, "AS": 10.0}
    assert m.odds == {"PSH": 1.63, "PSD": 4.38, "PSA": 5.30, "PSCH": 1.65, "AHh": -1.0}
    assert m.season == "2024-25" and m.source_line == 2


def test_parse_skips_blank_and_unplayed_rows_and_tolerates_missing_values() -> None:
    raw = csv_bytes(
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,,,,,,,,",
        ",,,,,,,,,,,,,,,",
        "E0,17/08/2024,12:30,Arsenal,Wolves,,,,,,,,,,,",
    )
    (m,) = footballdata.parse_csv(raw, "E0", 2024)
    assert m.referee is None and m.stats == {} and m.odds == {}


def test_parse_handles_two_digit_years_missing_time_and_no_bom() -> None:
    header = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    raw = (header + "E0,09/08/14,Man United,Swansea,1,2,A\n").encode("utf-8")
    (m,) = footballdata.parse_csv(raw, "E0", 2014)
    assert m.date.isoformat() == "2014-08-09" and m.kickoff_utc is None


def test_parse_falls_back_to_cp1252() -> None:
    raw = (HEADER + "SP1,20/08/2023,19:00,Alavés,Valencia,1,0,H,,,,,,,,\n").encode("cp1252")
    (m,) = footballdata.parse_csv(raw, "SP1", 2023)
    assert m.home == "Alavés"


def test_fotmob_parse_fixtures_and_season_param() -> None:
    import json

    payload = {
        "allAvailableSeasons": ["2026/2027", "2025/2026"],
        "fixtures": {
            "allMatches": [
                {
                    "round": "1",
                    "id": "6106404",
                    "home": {"name": "AEK Athens", "id": "8563"},
                    "away": {"name": "LASK", "id": "9977"},
                    "status": {
                        "utcTime": "2026-09-08T16:45:00Z",
                        "finished": True,
                        "cancelled": False,
                        "scoreStr": "1 - 0",
                    },
                },
                {"id": "1", "home": {"name": "A", "id": "1"}, "away": {"name": "B", "id": "2"}, "status": {}},
            ]
        },
    }
    raw = json.dumps(payload).encode()
    (fx,) = fotmob.parse_fixtures(raw, "UCL", "2026/2027")
    assert (fx.match_id, fx.home_id, fx.away_id, fx.finished, fx.score) == ("6106404", "8563", "9977", True, "1 - 0")
    assert fx.kickoff_utc == datetime(2026, 9, 8, 16, 45, tzinfo=timezone.utc)
    assert fotmob.available_seasons(raw) == ["2026/2027", "2025/2026"]
    assert fotmob.league_url("UCL", "2024/2025").endswith("id=42&ccode3=GBR&season=2024%2F2025")
    assert fotmob.match_key("UCL", "2024/2025", 7) == "fotmob/match/UCL/2024-2025/7.json"


def test_understat_urls_and_match_ids() -> None:
    import json

    raw = json.dumps(
        {"teams": {}, "players": [], "dates": [{"id": "1", "isResult": True}, {"id": "2", "isResult": False}]}
    ).encode()
    assert understat.league_url("La_liga", 2025) == "https://understat.com/getLeagueData/La_liga/2025"
    assert understat.match_ids(raw) == ["1"]


def test_current_start_year_rolls_over_in_july() -> None:
    from datetime import date

    from src.data.cli import current_start_year

    assert current_start_year(date(2026, 10, 18)) == 2026
    assert current_start_year(date(2027, 3, 1)) == 2026
    assert current_start_year(date(2027, 6, 30)) == 2026
    assert current_start_year(date(2027, 7, 1)) == 2027


def test_fotmob_match_jobs_skip_unsettled_and_unfinished_matches(tmp_path, monkeypatch) -> None:
    import json
    from datetime import timedelta

    from src.data import cli

    def fixture(match_id: str, kickoff: datetime, *, finished: bool, cancelled: bool = False) -> dict:
        return {
            "id": match_id,
            "round": "1",
            "home": {"id": "1", "name": "A"},
            "away": {"id": "2", "name": "B"},
            "status": {
                "utcTime": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finished": finished,
                "cancelled": cancelled,
                "scoreStr": "1 - 0",
            },
        }

    now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    matches = [
        fixture("old", now - timedelta(hours=30), finished=True),
        fixture("fresh", now - timedelta(hours=2), finished=True),  # ended moments ago
        fixture("live", now - timedelta(hours=1), finished=False),
        fixture("cancelled", now - timedelta(hours=40), finished=True, cancelled=True),
    ]
    league = tmp_path / "fotmob" / "league" / "EPL"
    league.mkdir(parents=True)
    (league / "2026-2027.json").write_text(json.dumps({"fixtures": {"allMatches": matches}}))
    (league / "2026-2027.json.meta.json").write_text("{}")
    monkeypatch.setattr(cli, "RAW_DIR", tmp_path)

    settled = cli._fotmob_match_jobs(["EPL"], 2026, 2026, settle_hours=4, now=now)
    everything = cli._fotmob_match_jobs(["EPL"], 2026, 2026, settle_hours=0, now=now)
    assert [j[2] for j in settled] == ["old"]
    assert sorted(j[2] for j in everything) == ["fresh", "old"]
