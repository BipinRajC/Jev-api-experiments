from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.data.http import CachedFetcher, FetchResult

BASE_URL = "https://www.fotmob.com/api/data"
UTC = ZoneInfo("UTC")

COMPETITIONS: dict[str, int] = {
    "EPL": 47,
    "LALIGA": 87,
    "BUNDESLIGA": 54,
    "SERIEA": 55,
    "LIGUE1": 53,
    "UCL": 42,
}

# Results-only competitions (fixture lists, no matchDetails) used to link leagues for cross-league
# ratings: the other UCL feeder leagues plus UEL/UECL. FotMob team ids are shared across competitions.
RATING_COMPETITIONS: dict[str, int] = {
    "TURKEY": 71,
    "PORTUGAL": 61,
    "NETHERLANDS": 57,
    "SCOTLAND": 64,
    "BELGIUM": 40,
    "GREECE": 135,
    "AUSTRIA": 38,
    "NORWAY": 59,
    "CZECH": 122,
    "UKRAINE": 441,
    "SWITZERLAND": 69,
    "DENMARK": 46,
    "UEL": 73,
    "UECL": 10216,
}
ALL_COMPETITIONS: dict[str, int] = {**COMPETITIONS, **RATING_COMPETITIONS}


@dataclass
class FMFixture:
    match_id: str
    competition: str
    season: str  # FotMob label, e.g. "2024/2025"
    round: str | None
    kickoff_utc: datetime
    home_id: str
    home_name: str
    away_id: str
    away_name: str
    finished: bool
    cancelled: bool
    score: str | None  # "2 - 1" as FotMob reports it (after extra time when decided_by is AET/PEN)
    decided_by: str | None = None  # status.reason.shortKey: fulltime_short / afterextratime_short / penalties_short / aborted_short


def season_param(label: str) -> str:
    return label.replace("/", "%2F")


def league_url(competition: str, season: str | None = None) -> str:
    url = f"{BASE_URL}/leagues?id={ALL_COMPETITIONS[competition]}&ccode3=GBR"
    return url + (f"&season={season_param(season)}" if season else "")


def match_url(match_id: str | int) -> str:
    return f"{BASE_URL}/matchDetails?matchId={match_id}"


def league_key(competition: str, season: str) -> str:
    return f"fotmob/league/{competition}/{season.replace('/', '-')}.json"


def match_key(competition: str, season: str, match_id: str | int) -> str:
    return f"fotmob/match/{competition}/{season.replace('/', '-')}/{match_id}.json"


def fetch_league(
    fetcher: CachedFetcher, competition: str, season: str, *, refresh: bool = False
) -> FetchResult:
    return fetcher.get(
        league_url(competition, season), cache_key=league_key(competition, season), refresh=refresh,
        validate=_validate_league,
    )


def fetch_match(
    fetcher: CachedFetcher, competition: str, season: str, match_id: str | int
) -> FetchResult:
    return fetcher.get(
        match_url(match_id), cache_key=match_key(competition, season, match_id),
        validate=lambda raw: _validate_match(raw, str(match_id)),
    )


def _validate_league(raw: bytes) -> None:
    payload = json.loads(raw)
    if not isinstance((payload.get("fixtures") or {}).get("allMatches"), list):
        raise ValueError("unexpected FotMob league payload")


def _validate_match(raw: bytes, expected_id: str) -> None:
    payload = json.loads(raw)
    general = payload.get("general") or {}
    if str(general.get("matchId")) != expected_id:
        raise ValueError(f"FotMob match ID does not match request: expected {expected_id}")
    if not general.get("homeTeam") or not general.get("awayTeam") or not payload.get("header"):
        raise ValueError("unexpected FotMob match detail payload")


def available_seasons(raw: bytes) -> list[str]:
    return list(json.loads(raw).get("allAvailableSeasons", []))


def _parse_utc(text: str) -> datetime:
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in text else "%Y-%m-%dT%H:%M:%SZ"
    return datetime.strptime(text, fmt).replace(tzinfo=UTC)


def parse_fixtures(raw: bytes, competition: str, season: str) -> list[FMFixture]:
    payload: dict[str, Any] = json.loads(raw)
    fixtures: list[FMFixture] = []
    for m in payload.get("fixtures", {}).get("allMatches", []):
        status = m.get("status", {})
        if not status.get("utcTime"):
            continue
        fixtures.append(
            FMFixture(
                match_id=str(m["id"]),
                competition=competition,
                season=season,
                round=str(m["round"]) if m.get("round") is not None else None,
                kickoff_utc=_parse_utc(status["utcTime"]),
                home_id=str(m["home"]["id"]),
                home_name=m["home"]["name"],
                away_id=str(m["away"]["id"]),
                away_name=m["away"]["name"],
                finished=bool(status.get("finished")),
                cancelled=bool(status.get("cancelled")),
                score=status.get("scoreStr"),
                decided_by=(status.get("reason") or {}).get("shortKey"),
            )
        )
    return fixtures
