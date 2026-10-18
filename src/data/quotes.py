"""Timestamped football market quotes from saved forward snapshots."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _decimal_odds(american: Any) -> float | None:
    try:
        value = int(str(american))
    except (TypeError, ValueError):
        return None
    if value > 0:
        return 1.0 + value / 100.0
    if value < 0:
        return 1.0 + 100.0 / abs(value)
    return None


def _line(value: Any, side: str) -> float | None:
    text = str(value or "")
    match = re.fullmatch(rf"{side[0]}(\d+(?:\.\d+)?)", text.lower())
    return float(match.group(1)) if match else None


def parse_espn_snapshot(raw: bytes, competition: str, captured_at: datetime) -> list[dict[str, Any]]:
    """Only prices displayed on a pre-event page before kickoff; source calls the field 'close'."""
    captured_at = pd.Timestamp(captured_at).to_pydatetime()
    rows = []
    for event in json.loads(raw).get("events") or []:
        if ((event.get("status") or {}).get("type") or {}).get("state") != "pre":
            continue
        kickoff = pd.Timestamp(event["date"]).to_pydatetime()
        if captured_at >= kickoff:
            continue
        comp = (event.get("competitions") or [{}])[0]
        names = {x.get("homeAway"): (x.get("team") or {}).get("displayName") for x in comp.get("competitors") or []}
        if not names.get("home") or not names.get("away"):
            continue
        base = {
            "espn_event_id": str(event["id"]), "competition": competition,
            "kickoff_utc": kickoff, "captured_at_utc": captured_at,
            "home_name": names["home"], "away_name": names["away"],
            "source_field": "close", "price_semantics": "displayed_pre_event_unverified",
        }
        for offer in comp.get("odds") or []:
            if not isinstance(offer, dict):
                continue
            provider = (offer.get("provider") or {}).get("name")
            for side in ("home", "draw", "away"):
                price = _decimal_odds((((offer.get("moneyline") or {}).get(side) or {}).get("close") or {}).get("odds"))
                if price is not None:
                    rows.append(base | {"provider": provider, "market": "1x2", "side": side, "line": None, "decimal_odds": price})
            total = offer.get("total") or {}
            total_quotes = {}
            for side in ("over", "under"):
                displayed = ((total.get(side) or {}).get("close") or {})
                line, price = _line(displayed.get("line"), side), _decimal_odds(displayed.get("odds"))
                if line is not None and price is not None:
                    total_quotes[side] = (line, price)
            if set(total_quotes) == {"over", "under"} and total_quotes["over"][0] == total_quotes["under"][0]:
                for side, (line, price) in total_quotes.items():
                    rows.append(base | {"provider": provider, "market": "total_goals", "side": side, "line": line, "decimal_odds": price})
    return rows


def _name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold()).replace("ø", "o").replace("ß", "ss")
    return "".join(ch for ch in normalized if ch.isalnum() and not unicodedata.combining(ch))


ESPN_NAME_ALIASES = {
    "asroma": "roma",
    "vikingfk": "viking",
    "bayernmunich": "bayernmunchen",
    "feyenoordrotterdam": "feyenoord",
    "lasklinz": "lask",
}


def _espn_name(value: str) -> str:
    normalized = _name(value)
    return ESPN_NAME_ALIASES.get(normalized, normalized)


def match_quotes_to_fixtures(quotes: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Attach a FotMob id only if competition, both names, and kickoff identify one fixture."""
    if quotes.empty:
        return quotes.assign(match_id=pd.Series(dtype="string"), available_at_cutoff=pd.Series(dtype="bool"), near_cutoff_15m=pd.Series(dtype="bool"))
    index: dict[tuple[str, str, str], list[tuple[str, datetime, datetime]]] = {}
    for r in fixtures.itertuples(index=False):
        key = (r.competition, _name(r.home_name), _name(r.away_name))
        index.setdefault(key, []).append((r.match_id, r.kickoff_utc, r.cutoff_utc))
    match_ids, eligible, near = [], [], []
    for r in quotes.itertuples(index=False):
        candidates = [x for x in index.get((r.competition, _espn_name(r.home_name), _espn_name(r.away_name)), [])
                      if abs((x[1] - r.kickoff_utc).total_seconds()) <= 30 * 60]
        match_id, cutoff = (candidates[0][0], candidates[0][2]) if len(candidates) == 1 else (None, None)
        match_ids.append(match_id)
        before = bool(match_id is not None and r.captured_at_utc <= cutoff)
        eligible.append(before)
        near.append(bool(before and (cutoff - r.captured_at_utc).total_seconds() <= 15 * 60))
    out = quotes.copy()
    out["match_id"] = match_ids
    out["available_at_cutoff"] = eligible
    out["near_cutoff_15m"] = near
    return out


def build_quotes_from_cache(raw_dir: Path, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Parse archived ESPN bodies with their actual fetch timestamps and conservative fixture IDs."""
    rows: list[dict[str, Any]] = []
    for path in sorted((raw_dir / "snapshots" / "espn").glob("*/*.json")):
        if path.name.endswith(".meta.json"):
            continue
        meta_path = path.with_name(path.name + ".meta.json")
        if not meta_path.exists():
            continue  # no trustworthy capture timestamp
        fetched_at = json.loads(meta_path.read_text(encoding="utf-8")).get("fetched_at")
        if not fetched_at:
            continue
        captured = pd.Timestamp(fetched_at).to_pydatetime()
        for quote in parse_espn_snapshot(path.read_bytes(), path.parent.name, captured):
            rows.append(quote | {"source_file": str(path.relative_to(raw_dir))})
    columns = ["espn_event_id", "competition", "kickoff_utc", "captured_at_utc", "home_name", "away_name",
               "source_field", "price_semantics", "provider", "market", "side", "line", "decimal_odds", "source_file"]
    frame = pd.DataFrame(rows, columns=columns)
    return match_quotes_to_fixtures(frame, fixtures)
