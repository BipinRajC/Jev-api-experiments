#!/usr/bin/env python3
"""Experiment 024 — Prospective 2026/27 cutoff-time prediction runner.

For every upcoming fixture whose 60-minute information cutoff is approaching
(window: kickoff is 62–80 minutes away), builds the frozen allowlisted as-of
state, calls all six core arms (Noul/Score/Choice x 1X2/binary markets,
question set QSET-020-v1), and appends one immutable prediction record per arm
to results/024-prospective-series/predictions.jsonl BEFORE the cutoff.

Design contract (phase-4 plan sections 3–4):
  - Append-only: prediction records are never rewritten. Settlement happens
    later in settlements.jsonl via settle.py.
  - Idempotent: fixtures with a successful prediction record are skipped; a
    failed attempt is logged to attempts.jsonl and retried on a later timer
    tick only while the fixture is still pre-cutoff.
  - The same-cutoff market comparison needs a quote captured within 15 minutes
    before the request with matching fixture/line/settlement; quotes are
    recorded when present and marked missing otherwise (never force-matched).
  - The quote-capture timer does NOT perform inference; this is an explicit,
    separate prediction/archival path.

Run by the footyquant-predict.timer (every 5 minutes). `--dry-run` validates
due-fixture selection, states, and question payloads without calling the API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import pandas as pd  # noqa: E402

import parsing as P20  # noqa: E402
import questions as Q20  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exp020_pipeline",
    REPO_ROOT / "experiments" / "020-football-pilot" / "experiment.py",
)
exp020 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp020)

# Experiment 026 extension markets (protocol revision 2 of the prospective runner).
_spec26 = importlib.util.spec_from_file_location(
    "exp026_questions",
    REPO_ROOT / "experiments" / "026-market-extension" / "questions.py",
)
Q26 = importlib.util.module_from_spec(_spec26)
_spec26.loader.exec_module(Q26)

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.jev_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    JevClient,
    JevConfigError,
)
from src.utils import load_env, utc_now_iso  # noqa: E402

EXPERIMENT_ID = "024-prospective-series"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PREDICTIONS_PATH = RESULTS_DIR / "predictions.jsonl"
ATTEMPTS_PATH = RESULTS_DIR / "attempts.jsonl"
ARMS = (
    "noul_1x2",
    "noul_binary",
    "score_1x2",
    "score_binary",
    "choice_1x2",
    "choice_binary",
    # 026 extension markets (QSET-026-v1): team goals, handicap, first-half goals
    "noul_ext",
    "score_ext",
    "choice_ext",
)


def arm_questions_for(arm: str) -> tuple[dict[str, dict[str, Any]], str]:
    """Return (questions, question_set_version) for an arm."""
    if arm in ("noul_ext", "score_ext", "choice_ext"):
        builder = {
            "noul_ext": Q26.noul_ext_questions,
            "score_ext": Q26.score_ext_questions,
            "choice_ext": Q26.choice_ext_questions,
        }[arm]
        return builder(), Q26.QUESTION_SET_VERSION
    return exp020.arm_questions(arm), Q20.QUESTION_SET_VERSION


# Due window: state assembled and calls started between 80 and 62 minutes before
# kickoff; all calls must finish by the 60-minute cutoff.
WINDOW_START_MIN = 80.0
WINDOW_END_MIN = 62.0
QUOTE_MATCH_WINDOW_MIN = 15.0


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


def git_sha() -> str | None:
    from subprocess import run

    try:
        out = run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load_due_fixtures(now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (due_fixtures, diagnostic_counts)."""
    upcoming = pd.read_parquet(DERIVED_DIR / "upcoming.parquet")
    inputs = pd.read_parquet(DERIVED_DIR / "upcoming_inputs.parquet")
    inputs_by_id = inputs.set_index("match_id")

    diagnostics = {
        "now_utc": now.isoformat(),
        "n_upcoming": len(upcoming),
        "n_missing_inputs": 0,
        "n_cutoff_passed": 0,
        "n_not_due_yet": 0,
        "n_already_predicted": 0,
        "n_due": 0,
    }
    done = predicted_keys()
    due: list[dict[str, Any]] = []
    for _, u in upcoming.iterrows():
        match_id = u["match_id"]
        if match_id not in inputs_by_id.index:
            diagnostics["n_missing_inputs"] += 1
            continue
        kickoff = pd.Timestamp(u["kickoff_utc"]).to_pydatetime()
        minutes_to_kickoff = (kickoff - now).total_seconds() / 60.0
        if minutes_to_kickoff <= 60.0:
            diagnostics["n_cutoff_passed"] += 1
            continue
        if minutes_to_kickoff > WINDOW_START_MIN:
            diagnostics["n_not_due_yet"] += 1
            continue
        if match_id in done:
            diagnostics["n_already_predicted"] += 1
            continue
        row = inputs_by_id.loc[match_id]
        if not isinstance(row, pd.Series) or isinstance(row, pd.DataFrame):
            diagnostics["n_missing_inputs"] += 1  # ambiguous or duplicated id
            continue
        state = build_state(row)
        missing_arms = [arm for arm in ARMS if f"{match_id}:{arm}" not in done]
        if not missing_arms:
            diagnostics["n_already_predicted"] += 1
            continue
        due.append(
            {
                "match_id": match_id,
                "competition": u["competition"],
                "season_start": int(u["season_start"]),
                "round": u.get("round"),
                "kickoff_utc": kickoff.isoformat(),
                "cutoff_utc": pd.Timestamp(u["cutoff_utc"]).isoformat(),
                "home_name": u["home_name"],
                "away_name": u["away_name"],
                "minutes_to_kickoff_at_selection": round(minutes_to_kickoff, 2),
                "missing_arms": missing_arms,
                "state": state,
                "state_sha256": canonical_hash(state),
            }
        )
    diagnostics["n_due"] = len(due)
    return due, diagnostics


def build_state(row: pd.Series) -> dict[str, Any]:
    from src.features import state as state_mod

    return state_mod.state_from_row(row.to_dict(), row.to_dict(), anonymized=False)


def predicted_keys() -> set[str]:
    """(match_id, arm) keys with a validated prediction record."""
    if not PREDICTIONS_PATH.exists():
        return set()
    done: set[str] = set()
    with PREDICTIONS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("validation") == "ok":
                done.add(rec["run_local_id"])
    return done


def matching_quotes(match_id: str, request_time: datetime) -> list[dict[str, Any]]:
    """Quotes for this fixture captured within 15 minutes before the request."""
    quotes_path = DERIVED_DIR / "forward_quotes.parquet"
    if not quotes_path.exists():
        return []
    quotes = pd.read_parquet(quotes_path)
    rows = quotes[quotes["match_id"] == match_id]
    out = []
    for _, q in rows.iterrows():
        captured = pd.Timestamp(q["captured_at_utc"])
        if captured.tz is None:
            captured = captured.tz_localize(timezone.utc)
        captured = captured.to_pydatetime()
        if request_time.tzinfo is None:
            request_time = request_time.replace(tzinfo=timezone.utc)
        if (
            timedelta(0)
            <= request_time - captured
            <= timedelta(minutes=QUOTE_MATCH_WINDOW_MIN)
        ):
            out.append(
                {
                    "captured_at_utc": captured.isoformat(),
                    "provider": q["provider"],
                    "market": q["market"],
                    "side": q["side"],
                    "line": None if pd.isna(q["line"]) else float(q["line"]),
                    "decimal_odds": None
                    if pd.isna(q["decimal_odds"])
                    else float(q["decimal_odds"]),
                    "price_semantics": q["price_semantics"],
                    "source_file": q["source_file"],
                }
            )
    return out


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        fh.flush()
        os_sync(fh)


def os_sync(fh: Any) -> None:
    try:
        import os

        os.fsync(fh.fileno())
    except Exception:
        pass


def run_fixture(client: JevClient, model: str, fixture: dict[str, Any]) -> None:
    state = fixture["state"]
    kickoff = datetime.fromisoformat(fixture["kickoff_utc"])
    cutoff = datetime.fromisoformat(fixture["cutoff_utc"])
    for arm in fixture.get("missing_arms", ARMS):
        request_time = utc_now_iso()
        questions, qset_version = arm_questions_for(arm)
        started = datetime.now(timezone.utc)
        try:
            result = client.system_one(state=state, questions=questions)
        except Exception as exc:
            append_record(
                ATTEMPTS_PATH,
                {
                    "match_id": fixture["match_id"],
                    "arm": arm,
                    "attempt_time_utc": request_time,
                    "error_kind": type(exc).__name__,
                    "message": str(exc)[:500],
                    "minutes_to_kickoff": round(
                        (kickoff - started).total_seconds() / 60.0, 2
                    ),
                },
            )
            continue
        response_time = datetime.now(timezone.utc)
        usage = result.usage if isinstance(result.usage, dict) else {}
        input_tokens = usage.get("input_tokens")
        try:
            parsed = exp020.parse_call(arm, result.body)
        except Exception as exc:
            append_record(
                ATTEMPTS_PATH,
                {
                    "match_id": fixture["match_id"],
                    "arm": arm,
                    "attempt_time_utc": request_time,
                    "error_kind": "parser_exception",
                    "message": str(exc)[:500],
                },
            )
            continue
        record = {
            "experiment_id": EXPERIMENT_ID,
            "run_local_id": f"{fixture['match_id']}:{arm}",
            "match_id": fixture["match_id"],
            "competition": fixture["competition"],
            "season_start": fixture["season_start"],
            "round": fixture["round"],
            "cohort": "prospective_2026_27",
            "arm": arm,
            "state": state,
            "state_sha256": fixture["state_sha256"],
            "question_set_version": qset_version,
            "model_requested": model,
            "model_returned": result.model,
            "kickoff_utc": fixture["kickoff_utc"],
            "cutoff_utc": fixture["cutoff_utc"],
            "request_time_utc": request_time,
            "response_time_utc": response_time.isoformat(),
            "pre_cutoff": bool(response_time <= cutoff),
            "minutes_before_kickoff_at_response": round(
                (kickoff - response_time).total_seconds() / 60.0, 2
            ),
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": round(result.latency_ms, 1),
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": None
            if input_tokens is None
            else round(estimate_cost(input_tokens), 8),
            "git_sha": git_sha(),
            "quotes_near_request": matching_quotes(fixture["match_id"], response_time),
            "raw_response": result.body,
            "parsed": parsed,
            "validation": parsed.get("validation", "parser_error"),
            "settlement": None,  # appended later by settle.py in settlements.jsonl
        }
        append_record(PREDICTIONS_PATH, record)


def estimate_cost(input_tokens: int, usd_per_million: float = 0.042) -> float:
    return input_tokens * usd_per_million / 1_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate selection/states without API calls",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="max fixtures per invocation (0 = all due)"
    )
    args = parser.parse_args(argv)

    load_env()
    now = datetime.now(timezone.utc)
    due, diagnostics = load_due_fixtures(now)
    print(json.dumps(diagnostics))
    if args.dry_run:
        for fixture in due:
            questions = exp020.arm_questions("noul_1x2")
            print(
                json.dumps(
                    {
                        "match_id": fixture["match_id"],
                        "kickoff_utc": fixture["kickoff_utc"],
                        "cutoff_utc": fixture["cutoff_utc"],
                        "minutes_to_kickoff_at_selection": fixture[
                            "minutes_to_kickoff_at_selection"
                        ],
                        "state_sha256": fixture["state_sha256"],
                        "state_fixture_block": fixture["state"]["fixture"],
                        "question_set_versions": {
                            arm: arm_questions_for(arm)[1] for arm in ARMS
                        },
                    },
                    ensure_ascii=False,
                )
            )
        print(f"DRY RUN: {len(due)} fixtures would be predicted; no API calls made.")
        return 0

    if not due:
        return 0
    if args.limit:
        due = due[: args.limit]
    model = DEFAULT_MODEL
    try:
        with JevClient(model=model, base_url=DEFAULT_BASE_URL) as client:
            for fixture in due:
                cutoff = datetime.fromisoformat(fixture["cutoff_utc"])
                if datetime.now(timezone.utc) >= cutoff:
                    print(
                        f"SKIP {fixture['match_id']}: cutoff passed before this fixture's turn.",
                        flush=True,
                    )
                    continue
                run_fixture(client, model, fixture)
                print(
                    f"PREDICTED {fixture['match_id']} ({fixture['competition']}) at {utc_now_iso()}",
                    flush=True,
                )
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
