from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

# Forward-only sources: they only show "now", so the only way to get as-of history is to archive
# a timestamped copy every time we look. Raw bodies are stored untouched; parsing happens later.

ESPN_SLUGS: dict[str, str] = {
    "UCL": "uefa.champions",
    "EPL": "eng.1",
    "LALIGA": "esp.1",
    "BUNDESLIGA": "ger.1",
    "SERIEA": "ita.1",
    "LIGUE1": "fra.1",
}
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
FOOTBALL_DATA_FIXTURES = "https://football-data.co.uk/fixtures.csv"
FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
CLUBELO_RANKING = "https://clubelo.com/Ranking"  # current ratings only; API is dead (502 since 2026-09)


@dataclass(frozen=True)
class SnapshotJob:
    source: str
    url: str
    cache_key: str


def stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def espn_url(slug: str, day: date) -> str:
    # Date ranges return 400; the scoreboard needs one date per request.
    return f"{ESPN_BASE}/{slug}/scoreboard?dates={day:%Y%m%d}"


def snapshot_jobs(now: datetime, days: int = 5) -> list[SnapshotJob]:
    ts = stamp(now)
    today = now.astimezone(timezone.utc).date()
    jobs = [
        SnapshotJob("footballdata", FOOTBALL_DATA_FIXTURES, f"snapshots/footballdata/fixtures/{ts}.csv"),
        SnapshotJob("fpl", FPL_BOOTSTRAP, f"snapshots/fpl/bootstrap-static/{ts}.json"),
        SnapshotJob("clubelo", CLUBELO_RANKING, f"snapshots/clubelo/ranking/{ts}.html"),
    ]
    for name, slug in ESPN_SLUGS.items():
        for offset in range(days):
            day = today + timedelta(days=offset)
            jobs.append(
                SnapshotJob("espn", espn_url(slug, day), f"snapshots/espn/{name}/{day:%Y%m%d}@{ts}.json")
            )
    return jobs


def due_espn_jobs(upcoming: pd.DataFrame, now: datetime, *, window_minutes: int = 15) -> list[SnapshotJob]:
    """One scoreboard fetch per competition/day with a fixture nearing its 60-minute cutoff."""
    if upcoming.empty:
        return []
    deadline = now + timedelta(minutes=window_minutes)
    pairs = {
        (r.competition, r.kickoff_utc.date())
        for r in upcoming.itertuples(index=False)
        if r.competition in ESPN_SLUGS and now <= r.cutoff_utc <= deadline
    }
    ts = stamp(now)
    return [
        SnapshotJob("espn", espn_url(ESPN_SLUGS[comp], day), f"snapshots/espn/{comp}/{day:%Y%m%d}@{ts}.json")
        for comp, day in sorted(pairs)
    ]


def validate_snapshot(job: SnapshotJob, raw: bytes) -> None:
    """Reject obviously wrong 200 responses before they enter the immutable archive."""
    if job.source == "espn":
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ValueError("unexpected ESPN scoreboard payload") from exc
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            raise ValueError("unexpected ESPN scoreboard payload")
    elif job.source == "fpl":
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ValueError("unexpected FPL bootstrap payload") from exc
        if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
            raise ValueError("unexpected FPL bootstrap payload")
    elif job.source == "footballdata":
        columns = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))).fieldnames or []
        if not {"Div", "Date", "HomeTeam", "AwayTeam"}.issubset(columns):
            raise ValueError("unexpected football-data fixtures CSV")
    elif job.source == "clubelo" and b"<html" not in raw[:200].lower():
        raise ValueError("unexpected ClubElo ranking page")
