from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.data import footballdata, fotmob, quotes, snapshots, understat
from src.data.http import BlockedError, CachedFetcher, FetchError
from src.utils import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw"
DERIVED_DIR = REPO_ROOT / "data" / "derived"


def current_start_year(today: date) -> int:
    """European seasons start in August: 2026-10 -> 2026, 2027-03 -> 2026."""
    return today.year if today.month >= 7 else today.year - 1


CURRENT_START_YEAR = current_start_year(date.today())


def _fetcher(interval: float) -> CachedFetcher:
    return CachedFetcher(RAW_DIR, min_interval_s=interval)


class Progress:
    def __init__(self, label: str, total: int) -> None:
        self.label, self.total = label, total
        self.done = self.cached = self.failed = 0

    def tick(self, item: str, *, from_cache: bool, error: str | None = None) -> None:
        self.done += 1
        if error:
            self.failed += 1
            print(f"[{self.label}] {self.done}/{self.total} FAIL {item}: {error}", flush=True)
        else:
            self.cached += from_cache
            if not from_cache:
                print(f"[{self.label}] {self.done}/{self.total} fetched {item}", flush=True)

    def summary(self) -> str:
        return (
            f"[{self.label}] done={self.done}/{self.total} from_cache={self.cached} failed={self.failed}"
        )


def _years(first: int, last: int) -> list[int]:
    return list(range(first, last + 1))


def cmd_footballdata(args: argparse.Namespace) -> int:
    fetcher = _fetcher(args.interval)
    jobs = [(d, y) for d in args.divisions for y in _years(args.from_year, args.to_year)]
    progress = Progress("footballdata", len(jobs))
    for division, year in jobs:
        refresh = args.refresh_current and year == CURRENT_START_YEAR
        try:
            result = footballdata.fetch_season(fetcher, division, year, refresh=refresh)
            progress.tick(f"{division}/{year}", from_cache=result.from_cache)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(f"{division}/{year}", from_cache=False, error=str(exc))
    print(progress.summary())
    return int(progress.failed > 0)


def cmd_understat_leagues(args: argparse.Namespace) -> int:
    fetcher = _fetcher(args.interval)
    jobs = [
        (lg, y)
        for lg in args.leagues
        for y in _years(max(args.from_year, understat.FIRST_SEASON), args.to_year)
    ]
    progress = Progress("understat-leagues", len(jobs))
    for league, year in jobs:
        refresh = args.refresh_current and year == CURRENT_START_YEAR
        try:
            result = understat.fetch_league(fetcher, league, year, refresh=refresh)
            progress.tick(f"{league}/{year}", from_cache=result.from_cache)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(f"{league}/{year}", from_cache=False, error=str(exc))
    print(progress.summary())
    return int(progress.failed > 0)


def _understat_match_jobs(leagues: Iterable[str], first: int, last: int) -> list[tuple[str, int, str]]:
    jobs: list[tuple[str, int, str]] = []
    for league in leagues:
        for year in _years(max(first, understat.FIRST_SEASON), last):
            path = RAW_DIR / understat.league_key(league, year)
            if path.exists():
                jobs += [(league, year, mid) for mid in understat.match_ids(path.read_bytes())]
    return jobs


def cmd_understat_matches(args: argparse.Namespace) -> int:
    fetcher = _fetcher(args.interval)
    jobs = _understat_match_jobs(args.leagues, args.from_year, args.to_year)
    pending = [j for j in jobs if not fetcher.cached(understat.match_key(*j))]
    if args.limit:
        pending = pending[: args.limit]
    print(f"[understat-matches] {len(jobs)} known results, {len(pending)} to fetch", flush=True)
    progress = Progress("understat-matches", len(pending))
    for league, year, match_id in pending:
        try:
            result = understat.fetch_match(fetcher, league, year, match_id)
            progress.tick(f"{league}/{year}/{match_id}", from_cache=result.from_cache)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(f"{league}/{year}/{match_id}", from_cache=False, error=str(exc))
    print(progress.summary())
    return int(progress.failed > 0)


def _fotmob_seasons(fetcher: CachedFetcher, competition: str, first_year: int, last_year: int) -> list[str]:
    """Discover FotMob's season labels via the current-season payload (one cached call)."""
    current = f"{CURRENT_START_YEAR}/{CURRENT_START_YEAR + 1}"
    raw = fotmob.fetch_league(fetcher, competition, current).body
    labels = fotmob.available_seasons(raw)
    return [s for s in labels if first_year <= int(s[:4]) <= last_year]


def cmd_fotmob_leagues(args: argparse.Namespace) -> int:
    fetcher = _fetcher(args.interval)
    try:
        jobs = [
            (c, s)
            for c in args.competitions
            for s in _fotmob_seasons(fetcher, c, args.from_year, args.to_year)
        ]
        progress = Progress("fotmob-leagues", len(jobs))
        for competition, season in jobs:
            refresh = args.refresh_current and int(season[:4]) == CURRENT_START_YEAR
            try:
                result = fotmob.fetch_league(fetcher, competition, season, refresh=refresh)
                progress.tick(f"{competition}/{season}", from_cache=result.from_cache)
            except FetchError as exc:
                if isinstance(exc, BlockedError):
                    raise
                progress.tick(f"{competition}/{season}", from_cache=False, error=str(exc))
    except BlockedError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(progress.summary())
    return int(progress.failed > 0)


def _fotmob_match_jobs(
    competitions: Iterable[str],
    first: int,
    last: int,
    *,
    settle_hours: float = 0.0,
    now: datetime | None = None,
) -> list[tuple[str, str, str]]:
    """Newest season first (competitions in the order given within a season), so an interrupted
    backfill leaves the most recent seasons complete for every competition."""
    competitions = list(competitions)
    # Skip matches that ended moments ago: ratings/xG can still be provisional right after full time.
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=settle_hours)
    jobs: list[tuple[str, str, str]] = []
    for competition in competitions:
        folder = RAW_DIR / "fotmob" / "league" / competition
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            if path.name.endswith(".meta.json") or "@" in path.name:
                continue  # sidecars and archived older copies
            season = path.stem.replace("-", "/")
            if not first <= int(season[:4]) <= last:
                continue
            for fx in fotmob.parse_fixtures(path.read_bytes(), competition, season):
                if fx.finished and not fx.cancelled and fx.kickoff_utc <= cutoff:
                    jobs.append((competition, season, fx.match_id))
    order = {c: i for i, c in enumerate(competitions)}
    jobs.sort(key=lambda j: (-int(j[1][:4]), order[j[0]]))
    return jobs


def cmd_fotmob_matches(args: argparse.Namespace) -> int:
    fetcher = _fetcher(args.interval)
    jobs = _fotmob_match_jobs(
        args.competitions, args.from_year, args.to_year, settle_hours=args.settle_hours
    )
    pending = [j for j in jobs if not fetcher.cached(fotmob.match_key(*j))]
    if args.limit:
        pending = pending[: args.limit]
    print(f"[fotmob-matches] {len(jobs)} finished matches known, {len(pending)} to fetch", flush=True)
    progress = Progress("fotmob-matches", len(pending))
    for competition, season, match_id in pending:
        try:
            result = fotmob.fetch_match(fetcher, competition, season, match_id)
            progress.tick(f"{competition}/{season}/{match_id}", from_cache=result.from_cache)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(f"{competition}/{season}/{match_id}", from_cache=False, error=str(exc))
    print(progress.summary())
    return int(progress.failed > 0)


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Archive forward-only sources (odds, injuries, current ratings) with a fetch timestamp."""
    fetcher = _fetcher(args.interval)
    jobs = snapshots.snapshot_jobs(datetime.now(timezone.utc), args.days)
    progress = Progress("snapshot", len(jobs))
    for job in jobs:
        try:
            fetcher.get(job.url, cache_key=job.cache_key, validate=lambda body: snapshots.validate_snapshot(job, body))
            progress.tick(f"{job.source} {job.cache_key}", from_cache=False)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(job.cache_key, from_cache=False, error=str(exc))
    print(progress.summary())
    return int(progress.failed > 0)


def cmd_capture_due(args: argparse.Namespace, *, now: datetime | None = None) -> int:
    """Archive near-cutoff ESPN pages and refresh the parsed quote table without a full rebuild."""
    import pandas as pd

    now = now or datetime.now(timezone.utc)
    upcoming = pd.read_parquet(DERIVED_DIR / "upcoming.parquet")
    jobs = snapshots.due_espn_jobs(upcoming, now, window_minutes=args.window_minutes)
    fetcher = _fetcher(args.interval)
    progress = Progress("capture-due", len(jobs))
    for job in jobs:
        try:
            result = fetcher.get(job.url, cache_key=job.cache_key, validate=lambda body: snapshots.validate_snapshot(job, body))
            progress.tick(job.cache_key, from_cache=result.from_cache)
        except BlockedError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except FetchError as exc:
            progress.tick(job.cache_key, from_cache=False, error=str(exc))
    if jobs:
        columns = ["match_id", "competition", "kickoff_utc", "cutoff_utc", "home_name", "away_name"]
        history_path = DERIVED_DIR / "matches.parquet"
        history = pd.read_parquet(history_path, columns=columns) if history_path.exists() else upcoming.iloc[0:0][columns]
        fixtures = pd.concat([history, upcoming[columns]], ignore_index=True)
        quotes.build_quotes_from_cache(RAW_DIR, fixtures).to_parquet(DERIVED_DIR / "forward_quotes.parquet", index=False)
    print(progress.summary())
    return int(progress.failed > 0)


def cmd_daily(args: argparse.Namespace) -> int:
    """Incremental update: refresh current-season files, fetch newly finished matches, snapshot odds.

    Safe to run any time and as often as wanted: everything already saved is skipped, and changed
    files are archived rather than overwritten. Exit code 2 = a host blocked us (run stopped),
    1 = some step failed, 0 = all steps completed.
    """
    year, interval = CURRENT_START_YEAR, args.interval
    steps = [
        ("footballdata", cmd_footballdata, dict(
            divisions=list(footballdata.DIVISIONS), from_year=year, to_year=year, refresh_current=True)),
        ("understat-leagues", cmd_understat_leagues, dict(
            leagues=list(understat.LEAGUES), from_year=year, to_year=year, refresh_current=True)),
        ("fotmob-leagues", cmd_fotmob_leagues, dict(
            competitions=list(fotmob.ALL_COMPETITIONS), from_year=year, to_year=year, refresh_current=True)),
        ("fotmob-matches", cmd_fotmob_matches, dict(
            competitions=list(fotmob.COMPETITIONS), from_year=year, to_year=year, limit=0,
            settle_hours=args.settle_hours)),
        ("snapshot", cmd_snapshot, dict(days=args.days)),
        ("build-tables", cmd_build_tables, dict(from_year=2014)),
        ("build-features", cmd_build_features, dict()),
        ("audit", cmd_audit, dict()),
    ]
    print(f"=== daily update {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ} season {year}-{(year + 1) % 100:02d} ===", flush=True)
    worst = 0
    for name, func, kwargs in steps:
        print(f"--- {name}", flush=True)
        try:
            code = func(argparse.Namespace(interval=interval, **kwargs))
        except Exception as exc:  # one failing step must not stop the others
            print(f"[{name}] ERROR {exc!r}", file=sys.stderr, flush=True)
            code = 1
        if code == 2:
            print("stopping: blocked by a host", file=sys.stderr, flush=True)
            return 2
        worst = max(worst, code)
    print(f"=== daily update finished with code {worst} ===", flush=True)
    return worst


def cmd_build_tables(args: argparse.Namespace) -> int:
    """Rebuild the parquet tables in data/derived from the raw cache (deterministic, re-runnable)."""
    import json

    from src.data import tables

    summary = tables.build_all(RAW_DIR, DERIVED_DIR, first_year=args.from_year)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_build_features(_: argparse.Namespace) -> int:
    """Build data/derived/features.parquet (as-of features + labels) from the derived tables."""
    from src.features import build

    features = build.run(DERIVED_DIR)
    print(f"features: {len(features)} rows x {features.shape[1]} columns -> {DERIVED_DIR / 'features.parquet'}")
    return 0


def cmd_state(args: argparse.Namespace, *, now: datetime | None = None) -> int:
    """Print an allowlisted Jev state for one historical or upcoming match."""
    import pandas as pd

    from src.features import state

    input_name = "upcoming_inputs" if args.upcoming else "model_inputs"
    meta_name = "upcoming" if args.upcoming else "matches"
    selected = pd.read_parquet(DERIVED_DIR / f"{input_name}.parquet", filters=[("match_id", "==", args.match_id)])
    meta = pd.read_parquet(DERIVED_DIR / f"{meta_name}.parquet", filters=[("match_id", "==", args.match_id)])
    if len(selected) != 1 or len(meta) != 1:
        print(f"match {args.match_id!r} is not present in {input_name}", file=sys.stderr)
        return 1
    if args.upcoming and pd.Timestamp(now or datetime.now(timezone.utc)) >= selected.iloc[0]["cutoff_utc"]:
        print(f"match {args.match_id!r} has passed its 60-minute information cutoff", file=sys.stderr)
        return 1
    record = state.state_from_row(selected.iloc[0].to_dict(), meta.iloc[0].to_dict(), anonymized=args.anonymized)
    print(json.dumps(record, indent=2, allow_nan=False))
    return 0


def cmd_audit(_: argparse.Namespace) -> int:
    from src.data import audit

    report = audit.audit_derived(DERIVED_DIR)
    print(json.dumps(report, indent=2))
    return int(bool(report["errors"]))


def cmd_status(_: argparse.Namespace) -> int:
    def count(pattern: str) -> int:
        return sum(1 for p in RAW_DIR.glob(pattern) if not p.name.endswith(".meta.json") and "@" not in p.name)

    print("football-data CSVs:", count("footballdata/*/*.csv"))
    print("understat league files:", count("understat/league/*/*.json"))
    print("understat match files:", count("understat/match/*/*/*.json"))
    print("fotmob league files:", count("fotmob/league/*/*.json"))
    print("fotmob match files:", count("fotmob/match/*/*/*.json"))
    expected_details = _fotmob_match_jobs(fotmob.COMPETITIONS, 2014, CURRENT_START_YEAR)
    pending_details = sum(1 for job in expected_details if not (RAW_DIR / fotmob.match_key(*job)).exists())
    print("fotmob details pending for finished target fixtures:", pending_details)
    print("snapshots:", sum(
        1 for p in RAW_DIR.glob("snapshots/*/*/*") if p.is_file() and not p.name.endswith(".meta.json")
    ))
    size = sum(p.stat().st_size for p in RAW_DIR.rglob("*") if p.is_file()) if RAW_DIR.exists() else 0
    print(f"raw cache size: {size / 1e6:.1f} MB at {RAW_DIR}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.data.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, *, matches: bool = False) -> None:
        p.add_argument("--from-year", type=int, default=2014, help="first season start year")
        p.add_argument("--to-year", type=int, default=CURRENT_START_YEAR)
        p.add_argument("--interval", type=float, default=1.0, help="min seconds between requests")
        if matches:
            p.add_argument("--limit", type=int, default=0, help="max matches to fetch (0 = all)")
            p.add_argument(
                "--settle-hours",
                type=float,
                default=0.0,
                help="only fetch matches that kicked off at least this many hours ago",
            )
        else:
            p.add_argument(
                "--refresh-current", action="store_true", help="re-fetch current-season files"
            )

    p = sub.add_parser("footballdata")
    p.add_argument("--divisions", nargs="+", default=list(footballdata.DIVISIONS))
    common(p)
    p.set_defaults(func=cmd_footballdata)

    p = sub.add_parser("understat-leagues")
    p.add_argument("--leagues", nargs="+", default=list(understat.LEAGUES))
    common(p)
    p.set_defaults(func=cmd_understat_leagues)

    p = sub.add_parser("understat-matches", help="shot-level data, one request per finished match")
    p.add_argument("--leagues", nargs="+", default=list(understat.LEAGUES))
    common(p, matches=True)
    p.set_defaults(func=cmd_understat_matches)

    p = sub.add_parser("fotmob-leagues", help="fixture lists (core six + rating-only competitions)")
    p.add_argument("--competitions", nargs="+", default=list(fotmob.ALL_COMPETITIONS))
    common(p)
    p.set_defaults(func=cmd_fotmob_leagues)

    p = sub.add_parser("fotmob-matches", help="matchDetails, one request per finished match")
    p.add_argument("--competitions", nargs="+", default=list(fotmob.COMPETITIONS))
    common(p, matches=True)
    p.set_defaults(func=cmd_fotmob_matches)

    p = sub.add_parser("snapshot", help="timestamped archive of forward-only sources")
    p.add_argument("--days", type=int, default=5, help="days of ESPN fixtures/odds to archive")
    p.add_argument("--interval", type=float, default=1.0)
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("capture-due", help="snapshot ESPN prices near upcoming match cutoffs")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--window-minutes", type=int, default=15)
    p.set_defaults(func=cmd_capture_due)

    p = sub.add_parser("daily", help="incremental update of everything (what the timer runs)")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--days", type=int, default=5, help="days of ESPN odds to snapshot")
    p.add_argument("--settle-hours", type=float, default=4.0)
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("build-tables", help="parse raw files into parquet tables in data/derived")
    p.add_argument("--from-year", type=int, default=2014)
    p.set_defaults(func=cmd_build_tables)

    p = sub.add_parser("build-features", help="as-of features + labels from the derived tables")
    p.set_defaults(func=cmd_build_features)

    p = sub.add_parser("state", help="print an allowlisted JSON state for a match")
    p.add_argument("--match-id", required=True)
    p.add_argument("--upcoming", action="store_true", help="read upcoming inputs instead of historical inputs")
    p.add_argument("--anonymized", action="store_true", help="hide team names and calendar date")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("audit", help="check derived tables for unsafe joins, missing details, and label leakage")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
