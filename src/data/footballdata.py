from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.data.http import CachedFetcher, FetchResult

BASE_URL = "https://football-data.co.uk"
# `Time` is UK local time in every league (verified against FotMob UTC kickoffs, 2024-25).
KICKOFF_TZ = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

DIVISIONS: dict[str, str] = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}

# Post-match stat columns (home/away pairs). Everything else numeric is treated as odds.
STAT_COLUMNS = (
    "HTHG", "HTAG", "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR",
)
NON_ODDS_COLUMNS = {
    "Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTR", "Referee",
    "Attendance", *STAT_COLUMNS,
}


@dataclass
class FDMatch:
    division: str
    season: str  # e.g. "2024-25"
    date: date
    kickoff_utc: datetime | None  # None when the file has no usable Time column
    home: str
    away: str
    fthg: int
    ftag: int
    ftr: str
    referee: str | None
    stats: dict[str, float] = field(default_factory=dict)
    odds: dict[str, float] = field(default_factory=dict)
    source_line: int = 0  # 1-based line in the CSV including the header


def season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def csv_url(division: str, start_year: int) -> str:
    return f"{BASE_URL}/mmz4281/{season_code(start_year)}/{division}.csv"


def cache_key(division: str, start_year: int) -> str:
    return f"footballdata/{division}/{season_code(start_year)}.csv"


def fetch_season(
    fetcher: CachedFetcher, division: str, start_year: int, *, refresh: bool = False
) -> FetchResult:
    return fetcher.get(
        csv_url(division, start_year), cache_key=cache_key(division, start_year), refresh=refresh
    )


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _parse_date(text: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {text!r}")


def _to_float(text: str | None) -> float | None:
    if text is None or not text.strip():
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_csv(raw: bytes, division: str, start_year: int) -> list[FDMatch]:
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    matches: list[FDMatch] = []
    for index, row in enumerate(reader, start=2):
        home = (row.get("HomeTeam") or "").strip()
        away = (row.get("AwayTeam") or "").strip()
        if not home or not away or not (row.get("Date") or "").strip():
            continue
        fthg, ftag = _to_float(row.get("FTHG")), _to_float(row.get("FTAG"))
        if fthg is None or ftag is None:
            continue  # unplayed / abandoned row
        day = _parse_date(row["Date"])
        kickoff = None
        time_text = (row.get("Time") or "").strip()
        if time_text:
            hh, mm = time_text.split(":")
            kickoff = datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=KICKOFF_TZ).astimezone(UTC)
        stats = {c: v for c in STAT_COLUMNS if (v := _to_float(row.get(c))) is not None}
        odds = {
            c: v
            for c, raw_value in row.items()
            if c and c not in NON_ODDS_COLUMNS and (v := _to_float(raw_value)) is not None
        }
        matches.append(
            FDMatch(
                division=division,
                season=season_label(start_year),
                date=day,
                kickoff_utc=kickoff,
                home=home,
                away=away,
                fthg=int(fthg),
                ftag=int(ftag),
                ftr=(row.get("FTR") or "").strip(),
                referee=(row.get("Referee") or "").strip() or None,
                stats=stats,
                odds=odds,
                source_line=index,
            )
        )
    return matches
