"""As-of feature engine: every feature is computed from information available before the cutoff.

One chronological pass over two kinds of events per match:

* RESULT at kickoff + FINISHED_AFTER (the match counts as played only from then on)
* QUERY  at kickoff - CUTOFF_BEFORE  (features for the match are read here)

A match's own RESULT is always later than its own QUERY, and RESULT sorts before QUERY at equal
timestamps, so nothing that happens at or after the cutoff can reach a feature.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

CUTOFF_BEFORE = timedelta(minutes=60)  # lineups are public about an hour before kickoff
FINISHED_AFTER = timedelta(minutes=150)  # a match counts as played this long after kickoff

EUROPE = {"UCL", "UEL", "UECL"}
TARGETS = {"EPL", "LALIGA", "BUNDESLIGA", "SERIEA", "LIGUE1", "UCL"}

# per-match team stats averaged over a rolling window, as (source column, feature name)
FM_ROLLING = (
    ("xg", "fm_xg_for"),
    ("shots", "shots_for"),
    ("shots_on_target", "sot_for"),
    ("possession", "possession"),
    ("passes_accurate_pct", "pass_pct"),
    ("corners", "corners_for"),
    ("yellow_cards", "yellow"),
    ("big_chances", "big_chances_for"),
    ("lineup_rating", "lineup_rating"),
)
FM_AGAINST = (("xg", "fm_xg_against"), ("shots", "shots_against"), ("shots_on_target", "sot_against"))
US_ROLLING = (
    ("us_xg", "us_xg_for"),
    ("us_xga", "us_xg_against"),
    ("us_npxg", "us_npxg_for"),
    ("us_ppda_att", "us_ppda_att"),
    ("us_deep", "us_deep_for"),
)


@dataclass(frozen=True)
class EloParams:
    start: float = 1500.0
    k: float = 20.0
    k_europe_multiplier: float = 1.5
    home_advantage: float = 65.0
    season_regression: float = 0.25  # share pulled toward the league mean at each new season
    newcomer_offset: float = -30.0  # newly seen team in a known league starts below that league's mean


def goal_multiplier(goal_diff: int) -> float:
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


def expected_home_score(elo_home: float, elo_away: float, home_advantage: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(elo_home + home_advantage - elo_away) / 400.0))


def _isnan(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _clean(value: Any) -> Any:
    return None if _isnan(value) else value


@dataclass
class Played:
    kickoff: datetime
    competition: str
    gf: int | None  # 90-minute goals when known
    ga: int | None
    own: dict[str, Any]
    opp: dict[str, Any]
    us: dict[str, Any]


class AsOfEngine:
    def __init__(self, params: EloParams | None = None) -> None:
        self.params = params or EloParams()
        self.elo: dict[str, float] = {}
        self.elo_games: dict[str, int] = defaultdict(int)
        self.elo_season: dict[str, int] = {}
        self._mean_cache: dict[tuple[str, int], float] = {}
        self.hist: dict[str, list[Played]] = defaultdict(list)
        self.tables: dict[tuple[str, int], dict[str, list[int]]] = defaultdict(dict)  # (comp, season) -> team -> [P,W,D,L,GF,GA,PTS]
        self.team_league: dict[str, str] = {}
        self.members: dict[tuple[str, int], set[str]] = defaultdict(set)
        self.h2h: dict[frozenset[str], list[tuple[datetime, str, int, int]]] = defaultdict(list)
        self.player_ratings: dict[str, list[float]] = defaultdict(list)
        self.last_xi: dict[str, frozenset[str]] = {}

    # ---------- Elo ----------
    def _league_mean(self, league: str, season_start: int) -> float | None:
        """Mean rating of the league's previous-season members, fixed the first time a season needs it.

        Caching matters: recomputing it per team would make each team's pull depend on which teams
        had already been pulled (order dependence).
        """
        key = (league, season_start)
        if key in self._mean_cache:
            return self._mean_cache[key]
        teams = self.members.get((league, season_start - 1)) or self.members.get((league, season_start))
        ratings = [self.elo[t] for t in teams or () if t in self.elo]
        if not ratings:
            return None  # nothing known yet: do not cache, a later call may know more
        self._mean_cache[key] = sum(ratings) / len(ratings)
        return self._mean_cache[key]

    def _elo_for(self, team: str, competition: str, season_start: int) -> float:
        """Current Elo of a team, applying the once-per-season pull toward its league mean lazily."""
        league = self.team_league.get(team) or (competition if competition not in EUROPE else None)
        if team not in self.elo:
            mean = self._league_mean(league, season_start) if league else None
            self.elo[team] = (mean + self.params.newcomer_offset) if mean is not None else self.params.start
            self.elo_season[team] = season_start
        elif self.elo_season.get(team, season_start) < season_start:
            mean = self._league_mean(league, season_start) if league else None
            if mean is not None:
                self.elo[team] += self.params.season_regression * (mean - self.elo[team])
            self.elo_season[team] = season_start
        return self.elo[team]

    # ---------- events ----------
    def apply_result(self, m: dict[str, Any], stats: dict[str, dict[str, Any]], us: dict[str, dict[str, Any]],
                     starters: dict[str, list[str]], ratings: dict[str, dict[str, float]]) -> None:
        home, away, comp, season = m["home_id"], m["away_id"], m["competition"], m["season_start"]
        elo_h, elo_a = self._elo_for(home, comp, season), self._elo_for(away, comp, season)
        g_home, g_away = _clean(m["goals_90_home"]), _clean(m["goals_90_away"])
        if g_home is None or g_away is None:
            g_home = g_away = None  # a half-known score is treated as unknown
        if g_home is not None and g_away is not None:
            g_home, g_away = int(g_home), int(g_away)
            score = 1.0 if g_home > g_away else 0.5 if g_home == g_away else 0.0
            k = self.params.k * (self.params.k_europe_multiplier if comp in EUROPE else 1.0)
            delta = k * goal_multiplier(g_home - g_away) * (score - expected_home_score(elo_h, elo_a, self.params.home_advantage))
            self.elo[home], self.elo[away] = elo_h + delta, elo_a - delta
            self.elo_games[home] += 1
            self.elo_games[away] += 1
        for team, opp, gf, ga in ((home, away, g_home, g_away), (away, home, g_away, g_home)):
            self.hist[team].append(
                Played(m["kickoff_utc"], comp, gf, ga, stats.get(team, {}), stats.get(opp, {}), us.get(team, {}))
            )
        # official table: awarded results count, so use the final score
        if comp not in EUROPE:
            table = self.tables[(comp, season)]
            fh, fa = int(m["final_home_goals"]), int(m["final_away_goals"])
            for team, gf, ga in ((home, fh, fa), (away, fa, fh)):
                row = table.setdefault(team, [0, 0, 0, 0, 0, 0, 0])
                row[0] += 1
                row[4] += gf
                row[5] += ga
                if gf > ga:
                    row[1] += 1
                    row[6] += 3
                elif gf == ga:
                    row[2] += 1
                    row[6] += 1
                else:
                    row[3] += 1
                self.team_league[team] = comp
                self.members[(comp, season)].add(team)
        fh, fa = int(m["final_home_goals"]), int(m["final_away_goals"])
        self.h2h[frozenset((home, away))].append((m["kickoff_utc"], home, fh, fa))
        for team in (home, away):
            if starters.get(team):
                self.last_xi[team] = frozenset(starters[team])
            for pid, rating in (ratings.get(team) or {}).items():
                self.player_ratings[pid].append(rating)

    def _team_features(self, team: str, side: str, m: dict[str, Any], cutoff: datetime,
                       starters: list[str] | None) -> dict[str, Any]:
        comp, season = m["competition"], m["season_start"]
        out: dict[str, Any] = {}
        out[f"{side}_elo"] = self._elo_for(team, comp, season)
        out[f"{side}_elo_games"] = self.elo_games[team]
        history = self.hist[team]
        last5, last10 = history[-5:], history[-10:]

        def points(played: list[Played]) -> list[float]:
            return [3.0 if p.gf > p.ga else 1.0 if p.gf == p.ga else 0.0 for p in played if p.gf is not None]

        out[f"{side}_form_pts_5"] = _mean(points(last5))
        out[f"{side}_form_pts_10"] = _mean(points(last10))
        out[f"{side}_gf_5"] = _mean([p.gf for p in last5 if p.gf is not None])
        out[f"{side}_ga_5"] = _mean([p.ga for p in last5 if p.ga is not None])
        out[f"{side}_gf_10"] = _mean([p.gf for p in last10 if p.gf is not None])
        out[f"{side}_ga_10"] = _mean([p.ga for p in last10 if p.ga is not None])
        out[f"{side}_form_str5"] = "".join("W" if p.gf > p.ga else "D" if p.gf == p.ga else "L" for p in last5 if p.gf is not None)
        out[f"{side}_matches_played_total"] = len(history)
        out[f"{side}_rest_days"] = (cutoff - history[-1].kickoff).total_seconds() / 86400.0 if history else float("nan")
        out[f"{side}_matches_14d"] = sum(1 for p in history[-12:] if cutoff - p.kickoff <= timedelta(days=14))
        out[f"{side}_matches_30d"] = sum(1 for p in history[-20:] if cutoff - p.kickoff <= timedelta(days=30))

        for window, label in ((history[-5:], "5"), (history[-10:], "10")):
            for column, name in FM_ROLLING:
                out[f"{side}_{name}_{label}"] = _mean([p.own[column] for p in window if not _isnan(p.own.get(column))])
            for column, name in FM_AGAINST:
                out[f"{side}_{name}_{label}"] = _mean([p.opp[column] for p in window if not _isnan(p.opp.get(column))])
            for column, name in US_ROLLING:
                out[f"{side}_{name}_{label}"] = _mean([p.us[column] for p in window if not _isnan(p.us.get(column))])

        # domestic league standing (official table, as of the cutoff)
        league = comp if comp not in EUROPE else self.team_league.get(team)
        row = self.tables.get((league, season), {}).get(team) if league else None
        out[f"{side}_dom_league"] = league
        if row:
            table = self.tables[(league, season)]
            better = sum(1 for r in table.values() if (r[6], r[4] - r[5], r[4]) > (row[6], row[4] - row[5], row[4]))
            out.update({f"{side}_dom_pos": better + 1, f"{side}_dom_played": row[0], f"{side}_dom_pts": row[6],
                        f"{side}_dom_gd": row[4] - row[5], f"{side}_dom_gf": row[4], f"{side}_dom_ga": row[5],
                        f"{side}_dom_ppg": row[6] / row[0]})
        else:
            out.update({f"{side}_{k}": float("nan") for k in ("dom_pos", "dom_played", "dom_pts", "dom_gd", "dom_gf", "dom_ga", "dom_ppg")})

        # lineup (known ~1h before kickoff): continuity with the previous XI and the starters' prior ratings
        if starters:
            previous = self.last_xi.get(team)
            out[f"{side}_xi_continuity"] = len(previous & set(starters)) if previous else float("nan")
            prior = [_mean(self.player_ratings[p][-10:]) for p in starters if self.player_ratings.get(p)]
            out[f"{side}_xi_prior_rating"] = _mean(prior)
            out[f"{side}_xi_known_players"] = len(prior)
        else:
            out[f"{side}_xi_continuity"] = out[f"{side}_xi_prior_rating"] = float("nan")
            out[f"{side}_xi_known_players"] = 0
        return out

    def query(self, m: dict[str, Any], starters: dict[str, list[str]]) -> dict[str, Any]:
        cutoff = m["kickoff_utc"] - CUTOFF_BEFORE
        home, away = m["home_id"], m["away_id"]
        row: dict[str, Any] = {"match_id": m["match_id"], "competition": m["competition"], "season_start": m["season_start"],
                               "round": m.get("round"), "kickoff_utc": m["kickoff_utc"], "cutoff_utc": cutoff,
                               "home_id": home, "away_id": away,
                               "is_europe": m["competition"] in EUROPE}
        row.update(self._team_features(home, "home", m, cutoff, starters.get(home)))
        row.update(self._team_features(away, "away", m, cutoff, starters.get(away)))
        row["elo_diff"] = row["home_elo"] + self.params.home_advantage - row["away_elo"]
        row["elo_exp_home"] = expected_home_score(row["home_elo"], row["away_elo"], self.params.home_advantage)
        meetings = self.h2h.get(frozenset((home, away)), [])[-5:]
        row["h2h_n"] = len(meetings)
        if meetings:
            pts = [3.0 if (gh > ga if h == home else ga > gh) else 1.0 if gh == ga else 0.0 for _, h, gh, ga in meetings]
            diff = [(gh - ga) if h == home else (ga - gh) for _, h, gh, ga in meetings]
            row["h2h_home_ppg"], row["h2h_home_gd_avg"] = _mean(pts), _mean(diff)
        else:
            row["h2h_home_ppg"] = row["h2h_home_gd_avg"] = float("nan")
        return row


def build_features(
    matches: pd.DataFrame,
    team_stats: pd.DataFrame,
    us_team: pd.DataFrame,
    players: pd.DataFrame,
    *,
    targets: set[str] = frozenset(TARGETS),
    params: EloParams | None = None,
) -> pd.DataFrame:
    """One row per target match with as-of features and (separately named) labels."""
    stats_by_match: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for rec in team_stats.to_dict("records"):
        stats_by_match[rec["match_id"]][rec["team_id"]] = rec
    us_by_match: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for rec in us_team[us_team["match_id"].notna()].to_dict("records"):
        us_by_match[rec["match_id"]][rec["team_id"]] = rec
    starters_by_match: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    ratings_by_match: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for rec in players[["match_id", "team_id", "player_id", "starter", "rating"]].itertuples(index=False):
        if rec.starter:
            starters_by_match[rec.match_id][rec.team_id].append(rec.player_id)
        if not _isnan(rec.rating):
            ratings_by_match[rec.match_id][rec.team_id][rec.player_id] = float(rec.rating)

    records = matches.sort_values(["kickoff_utc", "match_id"]).to_dict("records")
    for r in records:
        r["kickoff_utc"] = pd.Timestamp(r["kickoff_utc"]).to_pydatetime()
    events: list[tuple[datetime, int, int]] = []
    for i, r in enumerate(records):
        events.append((r["kickoff_utc"] + FINISHED_AFTER, 0, i))  # RESULT sorts before QUERY at ties
        if r["competition"] in targets:
            events.append((r["kickoff_utc"] - CUTOFF_BEFORE, 1, i))
    events.sort()

    engine = AsOfEngine(params)
    rows: list[dict[str, Any]] = []
    for _, kind, i in events:
        m = records[i]
        mid = m["match_id"]
        if kind == 0:
            engine.apply_result(m, stats_by_match.get(mid, {}), us_by_match.get(mid, {}),
                                starters_by_match.get(mid, {}), ratings_by_match.get(mid, {}))
        else:
            rows.append(engine.query(m, starters_by_match.get(mid, {})))
    features = pd.DataFrame(rows)
    labels = matches[["match_id", "goals_90_home", "goals_90_away", "result_unreliable", "decided_by"]].copy()
    labels["result_90"] = pd.Series(
        ["H" if h > a else "D" if h == a else "A" for h, a in zip(labels["goals_90_home"], labels["goals_90_away"])],
        index=labels.index,
    ).where(labels["goals_90_home"].notna() & labels["goals_90_away"].notna())
    labels = labels.rename(columns={"goals_90_home": "y_goals_home", "goals_90_away": "y_goals_away", "decided_by": "y_decided_by"})
    return features.merge(labels, on="match_id", how="left").sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
