from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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
