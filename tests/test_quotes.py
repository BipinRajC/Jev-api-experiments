from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.data import quotes


def test_espn_pre_event_prices_keep_capture_time_line_and_source_field() -> None:
    payload = {"events": [{
        "id": "espn-1", "date": "2026-10-20T19:00Z", "status": {"type": {"state": "pre"}},
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "team": {"displayName": "Arsenal"}},
                {"homeAway": "away", "team": {"displayName": "Chelsea"}},
            ],
            "odds": [{"provider": {"name": "DraftKings"},
                      "moneyline": {"home": {"close": {"odds": "+150"}},
                                    "draw": {"close": {"odds": "+200"}},
                                    "away": {"close": {"odds": "-110"}}},
                      "total": {"over": {"close": {"line": "o2.5", "odds": "-105"}},
                                "under": {"close": {"line": "u2.5", "odds": "-115"}}}}],
        }],
    }]}
    captured = datetime(2026, 10, 20, 17, 30, tzinfo=timezone.utc)

    rows = quotes.parse_espn_snapshot(json.dumps(payload).encode(), "EPL", captured)

    assert len(rows) == 5
    assert {(r["market"], r["side"]) for r in rows} == {
        ("1x2", "home"), ("1x2", "draw"), ("1x2", "away"),
        ("total_goals", "over"), ("total_goals", "under"),
    }
    home = next(r for r in rows if r["market"] == "1x2" and r["side"] == "home")
    over = next(r for r in rows if r["market"] == "total_goals" and r["side"] == "over")
    assert home["decimal_odds"] == 2.5 and home["source_field"] == "close"
    assert over["line"] == 2.5 and over["decimal_odds"] > 1.9
    assert all(r["captured_at_utc"] == captured for r in rows)


def test_espn_live_or_post_kickoff_snapshot_is_not_an_admissible_quote() -> None:
    event = {"id": "1", "date": "2026-10-20T19:00Z", "status": {"type": {"state": "in"}},
             "competitions": [{"odds": [{"moneyline": {"home": {"close": {"odds": "+100"}}}}]}]}
    captured = datetime(2026, 10, 20, 19, 1, tzinfo=timezone.utc)
    assert quotes.parse_espn_snapshot(json.dumps({"events": [event]}).encode(), "EPL", captured) == []


def test_mismatched_over_under_lines_are_not_paired_as_one_total_market() -> None:
    event = {"id": "1", "date": "2026-10-20T19:00Z", "status": {"type": {"state": "pre"}},
             "competitions": [{
                 "competitors": [{"homeAway": "home", "team": {"displayName": "Arsenal"}},
                                 {"homeAway": "away", "team": {"displayName": "Chelsea"}}],
                 "odds": [{"total": {"over": {"close": {"line": "o2.5", "odds": "-110"}},
                                     "under": {"close": {"line": "u3.5", "odds": "-110"}}}}],
             }]}
    captured = datetime(2026, 10, 20, 17, 30, tzinfo=timezone.utc)

    rows = quotes.parse_espn_snapshot(json.dumps({"events": [event]}).encode(), "EPL", captured)

    assert not any(r["market"] == "total_goals" for r in rows)


def test_quote_join_requires_unique_fixture_names_and_kickoff() -> None:
    fixtures = pd.DataFrame([{
        "match_id": "fm-1", "competition": "EPL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
        "cutoff_utc": pd.Timestamp("2026-10-20T18:00:00Z"),
        "home_name": "Arsenal", "away_name": "Chelsea",
    }])
    q = pd.DataFrame([
        {"espn_event_id": "ok", "competition": "EPL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
         "captured_at_utc": pd.Timestamp("2026-10-20T17:30:00Z"), "home_name": "Arsenal", "away_name": "Chelsea"},
        {"espn_event_id": "other", "competition": "EPL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
         "captured_at_utc": pd.Timestamp("2026-10-20T17:30:00Z"), "home_name": "Arsenal", "away_name": "Different Club"},
    ])

    joined = quotes.match_quotes_to_fixtures(q, fixtures).set_index("espn_event_id")

    assert joined.loc["ok", "match_id"] == "fm-1"
    assert bool(joined.loc["ok", "available_at_cutoff"])
    assert not bool(joined.loc["ok", "near_cutoff_15m"])
    assert pd.isna(joined.loc["other", "match_id"])


def test_verified_espn_team_alias_links_unique_ucl_fixture() -> None:
    fixtures = pd.DataFrame([{
        "match_id": "fm-roma", "competition": "UCL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
        "cutoff_utc": pd.Timestamp("2026-10-20T18:00:00Z"),
        "home_name": "Roma", "away_name": "Slovan Bratislava",
    }])
    q = pd.DataFrame([{
        "espn_event_id": "e-roma", "competition": "UCL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
        "captured_at_utc": pd.Timestamp("2026-10-20T17:30:00Z"),
        "home_name": "AS Roma", "away_name": "Slovan Bratislava",
    }])

    result = quotes.match_quotes_to_fixtures(q, fixtures).iloc[0]

    assert result["match_id"] == "fm-roma"


def test_quote_builder_uses_fetch_metadata_time_and_retains_source_file(tmp_path) -> None:
    event = {"id": "espn-1", "date": "2026-10-20T19:00Z", "status": {"type": {"state": "pre"}},
             "competitions": [{
                 "competitors": [{"homeAway": "home", "team": {"displayName": "Arsenal"}},
                                 {"homeAway": "away", "team": {"displayName": "Chelsea"}}],
                 "odds": [{"provider": {"name": "DraftKings"},
                           "moneyline": {"home": {"close": {"odds": "+150"}}}}],
             }]}
    body = tmp_path / "snapshots" / "espn" / "EPL" / "20261020@20261020T170000Z.json"
    body.parent.mkdir(parents=True)
    body.write_text(json.dumps({"events": [event]}))
    body.with_name(body.name + ".meta.json").write_text(json.dumps({"fetched_at": "2026-10-20T17:45:00Z"}))
    fixtures = pd.DataFrame([{
        "match_id": "fm-1", "competition": "EPL", "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
        "cutoff_utc": pd.Timestamp("2026-10-20T18:00:00Z"),
        "home_name": "Arsenal", "away_name": "Chelsea",
    }])

    result = quotes.build_quotes_from_cache(tmp_path, fixtures)

    assert result.iloc[0]["match_id"] == "fm-1"
    assert result.iloc[0]["captured_at_utc"] == pd.Timestamp("2026-10-20T17:45:00Z")
    assert result.iloc[0]["source_file"].endswith(body.name)
