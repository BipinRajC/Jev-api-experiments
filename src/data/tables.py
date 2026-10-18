from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.data import footballdata, fotmob, teams, understat

# Stat key in FotMob's matchDetails -> output column. Values like "408 (85%)" produce <col> and <col>_pct.
STAT_COLUMNS: dict[str, str] = {
    "BallPossesion": "possession",
    "expected_goals": "xg",
    "expected_goals_open_play": "xg_open_play",
    "expected_goals_set_play": "xg_set_play",
    "expected_goals_non_penalty": "npxg",
    "expected_goals_on_target": "xgot",
    "total_shots": "shots",
    "ShotsOnTarget": "shots_on_target",
    "ShotsOffTarget": "shots_off_target",
    "blocked_shots": "shots_blocked",
    "shots_woodwork": "woodwork",
    "shots_inside_box": "shots_inside_box",
    "shots_outside_box": "shots_outside_box",
    "big_chance": "big_chances",
    "big_chance_missed_title": "big_chances_missed",
    "passes": "passes",
    "accurate_passes": "passes_accurate",
    "own_half_passes": "passes_own_half",
    "opposition_half_passes": "passes_opp_half",
    "long_balls_accurate": "long_balls_accurate",
    "accurate_crosses": "crosses_accurate",
    "player_throws": "throw_ins",
    "touches_opp_box": "touches_opp_box",
    "Offsides": "offsides",
    "matchstats.headers.tackles": "tackles",
    "interceptions": "interceptions",
    "shot_blocks": "blocks",
    "clearances": "clearances",
    "keeper_saves": "keeper_saves",
    "duel_won": "duels_won",
    "ground_duels_won": "ground_duels_won",
    "aerials_won": "aerials_won",
    "dribbles_succeeded": "dribbles_succeeded",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "fouls": "fouls",
    "corners": "corners",
}
_COUNT_PCT = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*\(\s*(-?\d+(?:\.\d+)?)%\s*\)\s*$")
REG_TIME_MINUTES = 90  # goal events with time <= 90 (incl. stoppage, stored as 90 + overloadTime) are 90-minute goals


def parse_stat_value(value: Any) -> tuple[float | None, float | None]:
    """'408 (85%)' -> (408.0, 85.0); '2.43' -> (2.43, None); None -> (None, None)."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    match = _COUNT_PCT.match(str(value))
    if match:
        return float(match.group(1)), float(match.group(2))
    try:
        return float(value), None
    except ValueError:
        return None, None


def _utc(text: str) -> datetime:
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in text else "%Y-%m-%dT%H:%M:%SZ"
    return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)


def _goals_by_side(events: dict[str, Any]) -> tuple[list[int], list[int]]:
    def times(key: str) -> list[int]:
        out: list[int] = []
        for goals in (events.get(key) or {}).values():
            for goal in goals:
                if goal.get("time") is not None:
                    out.append(int(goal["time"]))
        return out

    return times("homeTeamGoals"), times("awayTeamGoals")


def parse_match_details(raw: bytes, competition: str, season: str) -> dict[str, Any]:
    """Pure parser: one matchDetails payload -> rows for matches/team_stats/shots/players/unavailable."""
    d = json.loads(raw)
    general, header, content = d["general"], d["header"], d.get("content") or {}
    match_id = str(general["matchId"])
    status = header["status"]
    reason = status.get("reason") or {}
    home_id, away_id = str(general["homeTeam"]["id"]), str(general["awayTeam"]["id"])
    home_goals_ev, away_goals_ev = _goals_by_side(header.get("events") or {})
    info = (content.get("matchFacts") or {}).get("infoBox") or {}
    stadium = info.get("Stadium")
    decided_by = reason.get("shortKey")
    pens = reason.get("penalties") or [None, None]

    match = {
        "match_id": match_id,
        "competition": competition,
        "season": season,
        "home_id": home_id,
        "away_id": away_id,
        "events_home_goals": len(home_goals_ev),
        "events_away_goals": len(away_goals_ev),
        "home_goals_90": sum(1 for t in home_goals_ev if t <= REG_TIME_MINUTES),
        "away_goals_90": sum(1 for t in away_goals_ev if t <= REG_TIME_MINUTES),
        "decided_by": decided_by,
        "pens_home": pens[0],
        "pens_away": pens[1],
        "referee": (info.get("Referee") or {}).get("text") if isinstance(info.get("Referee"), dict) else info.get("Referee"),
        "attendance": info.get("Attendance"),
        "stadium": stadium.get("name") if isinstance(stadium, dict) else stadium,
        "has_details": True,
    }

    stats: list[dict[str, Any]] = [
        {"match_id": match_id, "team_id": home_id, "is_home": True},
        {"match_id": match_id, "team_id": away_id, "is_home": False},
    ]
    periods = ((content.get("stats") or {}).get("Periods") or {}) if isinstance(content.get("stats"), dict) else {}
    for group in (periods.get("All") or {}).get("stats", []):
        for item in group.get("stats", []):
            column = STAT_COLUMNS.get(item.get("key"))
            values = item.get("stats")
            if column is None or item.get("type") == "title" or not values or len(values) != 2:
                continue
            for row, raw_value in zip(stats, values):
                count, pct = parse_stat_value(raw_value)
                if count is not None:
                    row[column] = count
                if pct is not None:
                    row[f"{column}_pct"] = pct

    lineup = content.get("lineup") or {}
    players: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for row, side in zip(stats, ("homeTeam", "awayTeam")):
        team = lineup.get(side) or {}
        coach = team.get("coach") or {}
        row["formation"] = team.get("formation")
        row["coach_id"] = str(coach["id"]) if isinstance(coach, dict) and coach.get("id") is not None else None
        row["coach_name"] = coach.get("name") if isinstance(coach, dict) else None
        row["lineup_rating"] = team.get("rating")
        # market value / age are *current at fetch time*, not as-of the match: kept only for inspection.
        row["starter_market_value_fetchtime"] = team.get("totalStarterMarketValue")
        for is_starter, key in ((True, "starters"), (False, "subs")):
            for p in team.get(key) or []:
                if p.get("id") is None:
                    continue
                perf = p.get("performance") or {}
                subs = perf.get("substitutionEvents") or []
                players.append(
                    {
                        "match_id": match_id,
                        "team_id": row["team_id"],
                        "player_id": str(p["id"]),
                        "name": p.get("name"),
                        "starter": is_starter,
                        "position_id": p.get("positionId"),
                        "usual_position_id": p.get("usualPlayingPositionId"),
                        "rating": perf.get("rating"),
                        "sub_on_minute": next((e.get("time") for e in subs if e.get("type") == "subIn"), None),
                        "sub_off_minute": next((e.get("time") for e in subs if e.get("type") == "subOut"), None),
                    }
                )
        for u in team.get("unavailable") or []:
            if u.get("id") is None:
                continue
            info_u = u.get("unavailability") or {}
            unavailable.append(
                {
                    "match_id": match_id,
                    "team_id": row["team_id"],
                    "player_id": str(u["id"]),
                    "name": u.get("name"),
                    "type": info_u.get("type"),
                    "expected_return": info_u.get("expectedReturn"),
                }
            )

    shots: list[dict[str, Any]] = []
    for s in (content.get("shotmap") or {}).get("shots") or []:
        shots.append(
            {
                "match_id": match_id,
                "shot_id": str(s.get("id")),
                "team_id": str(s.get("teamId")),
                "player_id": str(s.get("playerId")),
                "player_name": s.get("playerName"),
                "minute": s.get("min"),
                "minute_added": s.get("minAdded"),
                "x": s.get("x"),
                "y": s.get("y"),
                "xg": s.get("expectedGoals"),
                "xgot": s.get("expectedGoalsOnTarget"),
                "event_type": s.get("eventType"),
                "shot_type": s.get("shotType"),
                "situation": s.get("situation"),
                "period": s.get("period"),
                "is_blocked": s.get("isBlocked"),
                "is_on_target": s.get("isOnTarget"),
                "is_own_goal": s.get("isOwnGoal"),
                "is_inside_box": s.get("isFromInsideBox"),
            }
        )
    return {"match": match, "team_stats": stats, "players": players, "shots": shots, "unavailable": unavailable}


def _season_start(label: str) -> int:
    return int(label[:4])


def iter_fixture_files(raw_dir: Path) -> Iterator[tuple[str, str, Path]]:
    for comp_dir in sorted((raw_dir / "fotmob" / "league").glob("*")):
        for path in sorted(comp_dir.glob("*.json")):
            if path.name.endswith(".meta.json") or "@" in path.name:
                continue
            yield comp_dir.name, path.stem.replace("-", "/"), path


def build_matches(raw_dir: Path) -> pd.DataFrame:
    """All finished matches of all collected competitions, from FotMob fixture lists."""
    rows = []
    for competition, season, path in iter_fixture_files(raw_dir):
        for fx in fotmob.parse_fixtures(path.read_bytes(), competition, season):
            if fx.cancelled or not fx.finished or not fx.score or " - " not in fx.score:
                continue
            goals_home, goals_away = (int(x) for x in fx.score.split(" - ")[:2])
            row = asdict(fx)
            row.update(
                {
                    "season_start": _season_start(season),
                    "final_home_goals": goals_home,
                    "final_away_goals": goals_away,
                    "kickoff_utc": fx.kickoff_utc,
                }
            )
            row.pop("score")
            row.pop("finished")
            row.pop("cancelled")
            rows.append(row)
    df = pd.DataFrame(rows)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    # Calendar-year leagues (e.g. Norway) come back under both "2026" and "2026/2027": keep one copy,
    # preferring the calendar-year label.
    df = df.assign(_slash=df["season"].str.contains("/")).sort_values(["_slash", "match_id"])
    df = df.drop_duplicates("match_id", keep="first").drop(columns="_slash")
    # An empty status reason (seen on awarded 0-3 forfeits) is kept visible rather than guessed at.
    df["decided_by"] = df["decided_by"].replace("", "unspecified")
    return df.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)


def build_details_tables(raw_dir: Path, matches: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Parse every saved matchDetails file for the matches known in `matches`."""
    keep = matches[["match_id", "competition", "season"]].astype(str).itertuples(index=False)
    match_rows, stat_rows, player_rows, shot_rows, unavailable_rows = [], [], [], [], []
    missing = 0
    for match_id, competition, season in keep:
        path = raw_dir / fotmob.match_key(competition, season, match_id)
        if not path.exists():
            missing += 1
            continue
        parsed = parse_match_details(path.read_bytes(), competition, season)
        match_rows.append(parsed["match"])
        stat_rows += parsed["team_stats"]
        player_rows += parsed["players"]
        shot_rows += parsed["shots"]
        unavailable_rows += parsed["unavailable"]
    return {
        "details": pd.DataFrame(match_rows),
        "team_stats": pd.DataFrame(stat_rows),
        "players": pd.DataFrame(player_rows),
        "shots": pd.DataFrame(shot_rows),
        "unavailable_partial": pd.DataFrame(unavailable_rows),
    }


def attach_goals_90(matches: pd.DataFrame, details: pd.DataFrame) -> pd.DataFrame:
    """90-minute score: the final score unless extra time was played, in which case use goal events."""
    out = matches.merge(
        details[["match_id", "home_goals_90", "away_goals_90", "referee", "attendance", "stadium"]],
        on="match_id",
        how="left",
    )
    regulation = out["decided_by"].isin(["fulltime_short", None]) | out["decided_by"].isna()
    out["goals_90_home"] = out["final_home_goals"].where(regulation, out["home_goals_90"])
    out["goals_90_away"] = out["final_away_goals"].where(regulation, out["away_goals_90"])
    return out.drop(columns=["home_goals_90", "away_goals_90"])


def apply_score_conflicts(matches: pd.DataFrame, odds: pd.DataFrame, us_match: pd.DataFrame) -> pd.DataFrame:
    """Flags matches whose score differs between sources and blanks their 90' score.

    Awarded and abandoned matches are recorded differently by each source: FotMob and football-data
    each sometimes hold the awarded score and sometimes the on-field one (Bastia-Lyon 2016/17 vs
    Union Berlin-Bochum 2024/25), so no source can be trusted by rule. A disputed match gets
    `score_conflict = True`, `result_unreliable = True` and a missing 90' score: excluded from labels
    instead of guessed.
    """
    disputed = set(odds.loc[~odds["fd_score_agrees"], "match_id"])
    disputed |= set(us_match.loc[us_match["match_id"].notna() & ~us_match["us_score_agrees"], "match_id"])
    out = matches.copy()
    out["score_conflict"] = out["match_id"].isin(disputed)
    regulation = out["decided_by"].isin(["fulltime_short", "unspecified"])
    blank = out["score_conflict"] & regulation
    out["goals_90_home"] = out["goals_90_home"].mask(blank)
    out["goals_90_away"] = out["goals_90_away"].mask(blank)
    out["result_unreliable"] = out["score_conflict"] | (out["decided_by"] == "unspecified")
    return out


FOOTBALL_DATA_LEAGUES = {spec.football_data: spec for spec in teams.LEAGUE_SPECS}


def build_odds(raw_dir: Path, matches: pd.DataFrame, years: range) -> tuple[pd.DataFrame, dict[str, int]]:
    """football-data odds/stats joined to FotMob match ids on (competition, season, home id, away id)."""
    lookup = matches[matches["decided_by"].fillna("fulltime_short") != "aborted_short"]
    final_score = {r.match_id: (r.final_home_goals, r.final_away_goals) for r in matches.itertuples(index=False)}
    key_to_match = {
        (r.competition, r.season_start, r.home_id, r.away_id): r.match_id
        for r in lookup.itertuples(index=False)
    }
    counts = {"rows": 0, "joined": 0, "no_team_link": 0, "no_match": 0}
    rows = []
    for spec in teams.LEAGUE_SPECS:
        links = teams.link_league(raw_dir, spec, years)
        fd_to_id = {link.football_data: team_id for team_id, link in links.items() if link.football_data}
        for year in years:
            path = raw_dir / footballdata.cache_key(spec.football_data, year)
            if not path.exists():
                continue
            for m in footballdata.parse_csv(path.read_bytes(), spec.football_data, year):
                counts["rows"] += 1
                home_id, away_id = fd_to_id.get(m.home), fd_to_id.get(m.away)
                if home_id is None or away_id is None:
                    counts["no_team_link"] += 1
                    continue
                match_id = key_to_match.get((spec.fotmob, year, home_id, away_id))
                if match_id is None:
                    counts["no_match"] += 1
                    continue
                counts["joined"] += 1
                row: dict[str, Any] = {
                    "match_id": match_id,
                    "fd_division": m.division,
                    "fd_source_line": m.source_line,
                    "fd_kickoff_utc": m.kickoff_utc,
                    "fd_referee": m.referee,
                    "fd_fthg": m.fthg,
                    "fd_ftag": m.ftag,
                    # False where the two sources disagree (awarded / abandoned results): never silently trusted.
                    "fd_score_agrees": final_score[match_id] == (m.fthg, m.ftag),
                }
                row.update({f"fd_stat_{k}": v for k, v in m.stats.items()})
                row.update({f"odds_{k}": v for k, v in m.odds.items()})
                rows.append(row)
    return pd.DataFrame(rows), counts


def build_understat(raw_dir: Path, matches: pd.DataFrame, years: range) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Understat match xG and per-team match metrics (npxG, PPDA, deep, xPts) joined to FotMob ids."""
    by_key = {
        (r.competition, r.season_start, r.home_id, r.away_id): r.match_id
        for r in matches[matches["decided_by"].fillna("fulltime_short") != "aborted_short"].itertuples(index=False)
    }
    final_score = {r.match_id: (r.final_home_goals, r.final_away_goals) for r in matches.itertuples(index=False)}
    by_team_day: dict[tuple[str, date], list[str]] = {}
    for r in matches.itertuples(index=False):
        for team_id in (r.home_id, r.away_id):
            by_team_day.setdefault((team_id, r.kickoff_utc.date()), []).append(r.match_id)
    match_rows, team_rows = [], []
    counts = {"matches": 0, "matches_joined": 0, "team_rows": 0, "team_rows_joined": 0}
    for spec in teams.LEAGUE_SPECS:
        links = teams.link_league(raw_dir, spec, years)
        title_to_id = {alias: team_id for team_id, link in links.items() for alias in (link.understat_aliases or ())}
        for year in years:
            path = raw_dir / understat.league_key(spec.understat, year)
            if not path.exists():
                continue
            data = understat.parse_league(path.read_bytes())
            for m in data["dates"]:
                if not m.get("isResult"):
                    continue
                counts["matches"] += 1
                home_id, away_id = title_to_id.get(m["h"]["title"]), title_to_id.get(m["a"]["title"])
                match_id = by_key.get((spec.fotmob, year, home_id, away_id))
                if match_id:
                    counts["matches_joined"] += 1
                match_rows.append(
                    {
                        "match_id": match_id,
                        "understat_match_id": str(m["id"]),
                        "us_xg_home": float(m["xG"]["h"]),
                        "us_xg_away": float(m["xG"]["a"]),
                        "us_goals_home": int(m["goals"]["h"]),
                        "us_goals_away": int(m["goals"]["a"]),
                        "us_score_agrees": match_id is not None
                        and final_score[match_id] == (int(m["goals"]["h"]), int(m["goals"]["a"])),
                    }
                )
            for team in data["teams"].values():
                team_id = title_to_id.get(team["title"])
                for h in team["history"]:
                    counts["team_rows"] += 1
                    day = date.fromisoformat(h["date"][:10])
                    candidates: list[str] = []
                    for offset in (0, -1, 1):
                        candidates += by_team_day.get((team_id, day + timedelta(days=offset)), [])
                    candidates = [c for c in dict.fromkeys(candidates)]
                    match_id = candidates[0] if len(candidates) == 1 else None
                    if match_id:
                        counts["team_rows_joined"] += 1
                    team_rows.append(
                        {
                            "match_id": match_id,
                            "team_id": team_id,
                            "us_xg": float(h["xG"]),
                            "us_xga": float(h["xGA"]),
                            "us_npxg": float(h["npxG"]),
                            "us_npxga": float(h["npxGA"]),
                            "us_ppda_att": (h.get("ppda") or {}).get("att"),
                            "us_ppda_def": (h.get("ppda") or {}).get("def"),
                            "us_deep": h.get("deep"),
                            "us_deep_allowed": h.get("deep_allowed"),
                            "us_xpts": h.get("xpts"),
                        }
                    )
    return pd.DataFrame(match_rows), pd.DataFrame(team_rows), counts


def build_teams(raw_dir: Path, years: range) -> pd.DataFrame:
    rows = []
    for spec in teams.LEAGUE_SPECS:
        for link in teams.link_league(raw_dir, spec, years).values():
            rows.append(asdict(link) | {"understat_aliases": "|".join(link.understat_aliases)})
    return pd.DataFrame(rows)


def build_all(raw_dir: Path, out_dir: Path, *, first_year: int = 2014, last_year: int | None = None) -> dict[str, Any]:
    """Rebuilds every derived table from the raw cache. Deterministic and safe to re-run."""
    last_year = last_year or datetime.now(timezone.utc).year
    years = range(first_year, last_year + 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    matches = build_matches(raw_dir)
    tables = build_details_tables(raw_dir, matches)
    matches = attach_goals_90(matches, tables["details"])
    odds, odds_counts = build_odds(raw_dir, matches, years)
    us_match, us_team, us_counts = build_understat(raw_dir, matches, years)
    matches = apply_score_conflicts(matches, odds, us_match)
    outputs = {
        "matches": matches,
        "team_stats": tables["team_stats"],
        "players": tables["players"],
        "shots": tables["shots"],
        "unavailable_partial": tables["unavailable_partial"],
        "odds": odds,
        "understat_match": us_match,
        "understat_team_match": us_team,
        "teams": build_teams(raw_dir, years),
    }
    for name, df in outputs.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    return {
        "rows": {name: len(df) for name, df in outputs.items()},
        "odds_join": odds_counts,
        "understat_join": us_counts,
        "details_files_parsed": len(tables["details"]),
    }
