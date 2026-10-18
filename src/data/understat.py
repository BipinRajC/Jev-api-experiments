from __future__ import annotations

import json
from typing import Any

from src.data.http import CachedFetcher, FetchResult

BASE_URL = "https://understat.com"
# The site returns 404 without this header (verified 2026-10-12).
HEADERS = {"X-Requested-With": "XMLHttpRequest"}

LEAGUES: dict[str, str] = {
    "EPL": "Premier League",
    "La_liga": "La Liga",
    "Bundesliga": "Bundesliga",
    "Serie_A": "Serie A",
    "Ligue_1": "Ligue 1",
}
FIRST_SEASON = 2014  # Understat's coverage starts with 2014/15; no Champions League.


def league_url(league: str, start_year: int) -> str:
    return f"{BASE_URL}/getLeagueData/{league}/{start_year}"


def match_url(match_id: str | int) -> str:
    return f"{BASE_URL}/getMatchData/{match_id}"


def league_key(league: str, start_year: int) -> str:
    return f"understat/league/{league}/{start_year}.json"


def match_key(league: str, start_year: int, match_id: str | int) -> str:
    return f"understat/match/{league}/{start_year}/{match_id}.json"


def fetch_league(
    fetcher: CachedFetcher, league: str, start_year: int, *, refresh: bool = False
) -> FetchResult:
    return fetcher.get(
        league_url(league, start_year),
        cache_key=league_key(league, start_year),
        headers=HEADERS,
        refresh=refresh,
        validate=parse_league,
    )


def fetch_match(
    fetcher: CachedFetcher, league: str, start_year: int, match_id: str | int
) -> FetchResult:
    return fetcher.get(
        match_url(match_id), cache_key=match_key(league, start_year, match_id), headers=HEADERS,
        validate=json.loads,
    )


def parse_league(raw: bytes) -> dict[str, Any]:
    """Returns {'teams': {...}, 'players': [...], 'dates': [...]} (match list is under 'dates')."""
    data = json.loads(raw)
    if not isinstance(data, dict) or "dates" not in data or "teams" not in data:
        raise ValueError("unexpected Understat league payload")
    return data


def match_ids(raw: bytes) -> list[str]:
    return [str(m["id"]) for m in parse_league(raw)["dates"] if m.get("isResult")]
