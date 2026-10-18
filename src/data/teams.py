from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.data import footballdata, fotmob, understat

# (date, home goals, away goals) -> list of (home name, away name)
MatchIndex = dict[tuple[date, int, int], list[tuple[str, str]]]


@dataclass(frozen=True)
class LeagueSpec:
    football_data: str
    understat: str
    fotmob: str


LEAGUE_SPECS = (
    LeagueSpec("E0", "EPL", "EPL"),
    LeagueSpec("SP1", "La_liga", "LALIGA"),
    LeagueSpec("D1", "Bundesliga", "BUNDESLIGA"),
    LeagueSpec("I1", "Serie_A", "SERIEA"),
    LeagueSpec("F1", "Ligue_1", "LIGUE1"),
)


def _add(index: MatchIndex, day: date, hg: int, ag: int, home: str, away: str) -> None:
    index.setdefault((day, hg, ag), []).append((home, away))


def football_data_index(raw_dir: Path, division: str, year: int) -> MatchIndex:
    path = raw_dir / footballdata.cache_key(division, year)
    index: MatchIndex = {}
    if path.exists():
        for m in footballdata.parse_csv(path.read_bytes(), division, year):
            _add(index, m.date, m.fthg, m.ftag, m.home, m.away)
    return index


def understat_index(raw_dir: Path, league: str, year: int) -> MatchIndex:
    path = raw_dir / understat.league_key(league, year)
    index: MatchIndex = {}
    if path.exists():
        for m in understat.parse_league(path.read_bytes())["dates"]:
            if m.get("isResult"):
                day = date.fromisoformat(m["datetime"][:10])
                _add(index, day, int(m["goals"]["h"]), int(m["goals"]["a"]), m["h"]["title"], m["a"]["title"])
    return index


def fotmob_index(raw_dir: Path, competition: str, year: int) -> tuple[MatchIndex, dict[str, str]]:
    """Index keyed on team *ids* as strings; also returns id -> display name."""
    path = raw_dir / fotmob.league_key(competition, f"{year}/{year + 1}")
    index: MatchIndex = {}
    names: dict[str, str] = {}
    if path.exists():
        for fx in fotmob.parse_fixtures(path.read_bytes(), competition, f"{year}/{year + 1}"):
            if not fx.finished or fx.cancelled or not fx.score or " - " not in fx.score:
                continue
            hg, ag = (int(x) for x in fx.score.split(" - ")[:2])
            names[fx.home_id], names[fx.away_id] = fx.home_name, fx.away_name
            _add(index, fx.kickoff_utc.date(), hg, ag, fx.home_id, fx.away_id)
    return index, names


def vote_names(reference: MatchIndex, other: MatchIndex) -> dict[str, Counter[str]]:
    """For every (date, score) that is unique in *both* indexes, vote reference-name -> other-name.

    Ambiguous keys (two matches on one day with the same score) are skipped rather than guessed.
    """
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for key, ref_matches in reference.items():
        other_matches = other.get(key)
        if len(ref_matches) == 1 and other_matches is not None and len(other_matches) == 1:
            (ref_home, ref_away), (oth_home, oth_away) = ref_matches[0], other_matches[0]
            votes[ref_home][oth_home] += 1
            votes[ref_away][oth_away] += 1
    return votes


@dataclass
class TeamLink:
    fotmob_id: str
    fotmob_name: str
    football_data: str | None = None
    understat: str | None = None
    division: str | None = None
    fd_confidence: float = 0.0
    understat_confidence: float = 0.0
    # Understat sometimes renames a club mid-history (e.g. "Parma" -> "Parma Calcio 1913").
    understat_aliases: tuple[str, ...] = ()


MIN_ALIAS_VOTES = 2
MIN_ALIAS_SHARE = 0.05


def resolve_aliases(votes: dict[str, Counter[str]]) -> dict[str, tuple[str, ...]]:
    """Turns raw name votes into one clean alias set per team.

    A name keeps its place only with >= MIN_ALIAS_VOTES votes and >= MIN_ALIAS_SHARE of its team's
    votes (drops coincidental (date, score) matches), and a name claimed by several teams goes to the
    team that voted for it most (a club rename stays a genuine second alias of the same team).
    """
    owner: dict[str, tuple[str, int]] = {}
    for team_id, counter in votes.items():
        total = sum(counter.values())
        for name, count in counter.items():
            if count < MIN_ALIAS_VOTES or count < MIN_ALIAS_SHARE * total:
                continue
            if name not in owner or count > owner[name][1]:
                owner[name] = (team_id, count)
    return {
        team_id: tuple(sorted(name for name, (owner_id, _) in owner.items() if owner_id == team_id))
        for team_id in votes
    }


def _winner(counter: Counter[str]) -> tuple[str, float]:
    name, count = counter.most_common(1)[0]
    return name, count / sum(counter.values())


def link_league(raw_dir: Path, spec: LeagueSpec, years: range) -> dict[str, TeamLink]:
    """Links FotMob team ids to football-data names and Understat titles for one league."""
    fd_votes: dict[str, Counter[str]] = defaultdict(Counter)
    us_votes: dict[str, Counter[str]] = defaultdict(Counter)
    names: dict[str, str] = {}
    for year in years:
        fm_index, fm_names = fotmob_index(raw_dir, spec.fotmob, year)
        names.update(fm_names)
        for team_id, counter in vote_names(fm_index, football_data_index(raw_dir, spec.football_data, year)).items():
            fd_votes[team_id].update(counter)
        for team_id, counter in vote_names(fm_index, understat_index(raw_dir, spec.understat, year)).items():
            us_votes[team_id].update(counter)

    clean_aliases = resolve_aliases(us_votes)
    links: dict[str, TeamLink] = {}
    for team_id, name in names.items():
        link = TeamLink(team_id, name, division=spec.football_data)
        if fd_votes[team_id]:
            link.football_data, link.fd_confidence = _winner(fd_votes[team_id])
        if us_votes[team_id]:
            link.understat, link.understat_confidence = _winner(us_votes[team_id])
            link.understat_aliases = clean_aliases[team_id]
        links[team_id] = link
    return links
