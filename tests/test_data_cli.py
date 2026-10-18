from __future__ import annotations

from argparse import Namespace
import json

import pandas as pd
import httpx

from src.data import audit, cli, snapshots
from src.data.http import CachedFetcher, FetchError


def test_football_data_command_reports_a_partial_download_as_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_fetcher", lambda interval: object())
    def fail(*args, **kwargs):
        raise FetchError("network failure", url="https://football-data.co.uk/example.csv")
    monkeypatch.setattr(cli.footballdata, "fetch_season", fail)

    code = cli.cmd_footballdata(Namespace(interval=0, divisions=["E0"], from_year=2026, to_year=2026, refresh_current=False))

    assert code == 1


def test_snapshot_command_reports_a_partial_capture_as_failure(monkeypatch) -> None:
    class FailingFetcher:
        def get(self, *args, **kwargs):
            raise FetchError("network failure", url="https://example.test/odds")
    monkeypatch.setattr(cli, "_fetcher", lambda interval: FailingFetcher())
    monkeypatch.setattr(snapshots, "snapshot_jobs", lambda now, days: [snapshots.SnapshotJob("espn", "https://example.test/odds", "snapshots/espn/EPL/x@now.json")])

    code = cli.cmd_snapshot(Namespace(interval=0, days=1))

    assert code == 1


def test_status_counts_timestamped_snapshot_bodies(tmp_path, monkeypatch, capsys) -> None:
    folder = tmp_path / "snapshots" / "espn" / "EPL"
    folder.mkdir(parents=True)
    (folder / "20261018@20261018T120000Z.json").write_text("{}")
    (folder / "20261018@20261018T120000Z.json.meta.json").write_text("{}")
    monkeypatch.setattr(cli, "RAW_DIR", tmp_path)

    cli.cmd_status(Namespace())

    assert "snapshots: 1" in capsys.readouterr().out


def test_state_command_exports_an_upcoming_match_without_labels(tmp_path, monkeypatch, capsys) -> None:
    kickoff = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)
    future = pd.DataFrame([{
        "match_id": "future", "competition": "EPL", "season_start": 2026,
        "kickoff_utc": kickoff,
        "cutoff_utc": kickoff - pd.Timedelta(minutes=60),
        "home_elo": 1550.0, "away_elo": 1480.0,
    }])
    meta = pd.DataFrame([{"match_id": "future", "home_name": "Arsenal", "away_name": "Chelsea"}])
    future.to_parquet(tmp_path / "upcoming_inputs.parquet", index=False)
    meta.to_parquet(tmp_path / "upcoming.parquet", index=False)
    monkeypatch.setattr(cli, "DERIVED_DIR", tmp_path)

    assert cli.main(["state", "--match-id", "future", "--upcoming"]) == 0

    state = json.loads(capsys.readouterr().out)
    assert state["fixture"]["home_team"] == "Arsenal"
    assert state["teams"]["home"]["elo"] == 1550.0
    assert "result_90" not in json.dumps(state)


def test_capture_due_archives_and_parses_quote_for_a_near_cutoff_fixture(tmp_path, monkeypatch) -> None:
    now = pd.Timestamp("2026-10-20T17:40:00Z").to_pydatetime()
    future = pd.DataFrame([{
        "match_id": "fm-1", "competition": "EPL", "kickoff_utc": pd.Timestamp("2026-10-20T18:45:00Z"),
        "cutoff_utc": pd.Timestamp("2026-10-20T17:45:00Z"),
        "home_name": "Arsenal", "away_name": "Chelsea",
    }])
    future.to_parquet(tmp_path / "upcoming.parquet", index=False)
    payload = {"events": [{
        "id": "espn-1", "date": "2026-10-20T18:45Z", "status": {"type": {"state": "pre"}},
        "competitions": [{
            "competitors": [{"homeAway": "home", "team": {"displayName": "Arsenal"}},
                            {"homeAway": "away", "team": {"displayName": "Chelsea"}}],
            "odds": [{"provider": {"name": "DraftKings"},
                      "moneyline": {"home": {"close": {"odds": "+150"}}}}],
        }],
    }]}
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    monkeypatch.setattr(cli, "RAW_DIR", tmp_path)
    monkeypatch.setattr(cli, "DERIVED_DIR", tmp_path)
    monkeypatch.setattr(cli, "_fetcher", lambda interval: CachedFetcher(tmp_path, client=client, min_interval_s=0))

    code = cli.cmd_capture_due(Namespace(interval=0, window_minutes=15), now=now)

    assert code == 0
    quotes = pd.read_parquet(tmp_path / "forward_quotes.parquet")
    assert quotes.iloc[0]["match_id"] == "fm-1"
    assert quotes.iloc[0]["decimal_odds"] == 2.5
    assert len(list((tmp_path / "snapshots" / "espn" / "EPL").glob("*.json"))) == 2  # body + sidecar


def test_upcoming_state_refuses_a_request_after_its_cutoff(tmp_path, monkeypatch) -> None:
    row = pd.DataFrame([{
        "match_id": "late", "competition": "EPL", "season_start": 2026,
        "kickoff_utc": pd.Timestamp("2026-10-20T19:00:00Z"),
        "cutoff_utc": pd.Timestamp("2026-10-20T18:00:00Z"),
        "home_elo": 1500.0, "away_elo": 1500.0,
    }])
    row.to_parquet(tmp_path / "upcoming_inputs.parquet", index=False)
    pd.DataFrame([{"match_id": "late", "home_name": "A", "away_name": "B"}]).to_parquet(tmp_path / "upcoming.parquet", index=False)
    monkeypatch.setattr(cli, "DERIVED_DIR", tmp_path)

    code = cli.cmd_state(Namespace(match_id="late", upcoming=True, anonymized=False),
                         now=pd.Timestamp("2026-10-20T18:01:00Z").to_pydatetime())

    assert code == 1


def test_audit_command_returns_failure_for_unsafe_derived_tables(monkeypatch, capsys) -> None:
    monkeypatch.setattr(audit, "audit_derived", lambda path: {"errors": ["one stale missing detail"]})

    code = cli.cmd_audit(Namespace())

    assert code == 1
    assert "one stale missing detail" in capsys.readouterr().out
