#!/usr/bin/env python3
"""Experiment 021 — Locked retrospective primitive comparison.

Runs the six core arms (Noul/Score/Choice x 1X2/binary markets) on ALL eligible
2025/26 and already-played 2026/27 fixtures (retrospective cohort) using the
frozen question set QSET-020-v1 and derivation PROB-DERIVE-020-v1 from
Experiment 020. No calibration is fitted (no earlier out-of-sample football
predictions exist); raw scores only.

Resumable and append-only: completed calls stream one JSON object per line to
results/021-retrospective-locked/stream-001.jsonl. An interrupted run continues
from the stream (done keys are skipped); the final summary is written to
run-NNN.json once all calls finish. Stream lines are never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import parsing as P20  # noqa: E402
import questions as Q20  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exp020_pipeline",
    REPO_ROOT / "experiments" / "020-football-pilot" / "experiment.py",
)
exp020 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp020)  # reuses 020's frozen parse_call/analyze verbatim

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.jev_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    JevAPIError,
    JevAuthError,
    JevClient,
    JevConfigError,
    JevMalformedResponseError,
    JevRateLimitError,
    JevTimeoutError,
    JevValidationError,
)
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "021-retrospective-locked"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PROTOCOL_PATH = RESULTS_DIR / "protocol-v1.json"
STATES_PATH = RESULTS_DIR / "states-001.json"
STREAM_PATH = RESULTS_DIR / "stream-001.jsonl"
COHORTS = ("retrospective_2025_26", "retrospective_2026_27_played")
SEASON_STARTS = (2025, 2026)
ARMS = (
    "noul_1x2",
    "noul_binary",
    "score_1x2",
    "score_binary",
    "choice_1x2",
    "choice_binary",
)
RETRY_DELAYS_S = (2.0, 5.0, 10.0)
SEED = 20261021

QUESTIONS_020_SHA256 = hashlib.sha256(
    (REPO_ROOT / "experiments" / "020-football-pilot" / "questions.py").read_bytes()
).hexdigest()


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


def load_and_select() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    labels = pd.read_parquet(DERIVED_DIR / "market_labels.parquet")
    matches = pd.read_parquet(DERIVED_DIR / "matches.parquet")
    season = inputs[inputs["season_start"].isin(SEASON_STARTS)].copy()
    lab = labels[[c for c in labels.columns if c != "competition"]]
    frame = season.merge(lab, on="match_id", validate="one_to_one").merge(
        matches[
            [
                "match_id",
                "kickoff_disagreement",
                "details_pending",
                "home_name",
                "away_name",
            ]
        ],
        on="match_id",
        validate="one_to_one",
    )
    eligible = frame[
        frame["label_valid_90"].fillna(False).astype(bool)
        & frame["corner_total_90"].notna()
        & ~frame["corner_conflict"].fillna(False).astype(bool)
        & ~frame["kickoff_disagreement"].fillna(False).astype(bool)
        & ~frame["details_pending"].fillna(False).astype(bool)
    ].sort_values("kickoff_utc")
    exclusions = [
        {
            "stage": "eligibility",
            "reason": "failed one of label_valid_90 / corner label / corner_conflict / kickoff_disagreement / details_pending",
            "n_excluded": int(len(frame) - len(eligible)),
        }
    ]
    return eligible, exclusions


def freeze_protocol(
    eligible: pd.DataFrame, exclusions: list[dict[str, Any]]
) -> dict[str, Any]:
    meta = eligible.set_index("match_id")
    fixtures: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    for match_id, row in meta.iterrows():
        state = build_state(row)
        states[match_id] = state
        fixtures.append(
            {
                "match_id": match_id,
                "competition": row["competition"],
                "season_start": int(row["season_start"]),
                "cohort": "retrospective_2025_26"
                if row["season_start"] == 2025
                else "retrospective_2026_27_played",
                "round": row.get("round"),
                "kickoff_utc": row["kickoff_utc"].isoformat(),
                "cutoff_utc": row["cutoff_utc"].isoformat(),
                "home_name": row["home_name"],
                "away_name": row["away_name"],
                "state_sha256": canonical_hash(state),
                "labels": {
                    "result_90": row["result_90"],
                    "goals_home_90": row["goals_home_90"],
                    "goals_away_90": row["goals_away_90"],
                    "over_2_5": bool(row["over_2_5"]),
                    "btts_yes": bool(row["btts_yes"]),
                    "corner_total_90": row["corner_total_90"],
                    "corner_source": row["corner_source"],
                    "corner_over_9_5": bool(row["corner_total_90"] > Q20.CORNER_LINE),
                },
            }
        )
    protocol = {
        "protocol_version": "021-protocol-v1",
        "frozen_at_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "model_requested": DEFAULT_MODEL,
        "question_set_version": Q20.QUESTION_SET_VERSION,
        "questions_020_sha256": QUESTIONS_020_SHA256,
        "prob_derivation_version": P20.PROB_DERIVATION_VERSION,
        "corner_line": Q20.CORNER_LINE,
        "season_starts": list(SEASON_STARTS),
        "cohorts": list(COHORTS),
        "arms": list(ARMS),
        "arm_questions": {arm: arm_questions(arm) for arm in ARMS},
        "request_order_rotation": "per fixture, seeded shuffle of ARMS using RandomState(seed+2) at fixture index",
        "seed": SEED,
        "metrics": {
            "brier_1x2": "mean over classes of (p_k - y_k)^2",
            "brier_binary": "(p - y)^2",
            "log_loss_floor": P20.LOG_LOSS_FLOOR,
            "calibration": "raw scores only; no calibration map fitted (no earlier out-of-sample football predictions)",
        },
        "retries": {
            "max_retries": len(RETRY_DELAYS_S),
            "delays_s": list(RETRY_DELAYS_S),
        },
        "budget_decision": (
            "pilot 020 measured 2,284 mean input tokens/call; ~13.7k calls project to ~31M tokens "
            "~= $1.32 at $0.042/Mtok. Proceeding now because the reported $5 promo credit expires "
            "2026-10-19; no balance endpoint is documented, so credit sufficiency cannot be verified in-repo."
        ),
        "eligibility_exclusions": exclusions,
        "n_fixtures": len(fixtures),
        "fixtures": fixtures,
    }
    write_json(STATES_PATH, states)
    return protocol


def build_state(row: pd.Series) -> dict[str, Any]:
    from src.features import state as state_mod

    return state_mod.state_from_row(row.to_dict(), row.to_dict(), anonymized=False)


def arm_questions(arm: str) -> dict[str, dict[str, Any]]:
    if arm.endswith("_1x2"):
        if "noul" in arm:
            return {
                e: q
                for e, q in Q20.noul_questions().items()
                if e in Q20.ONE_X_TWO_EVENTS
            }
        return {
            e: q for e, q in Q20.score_questions().items() if e in Q20.ONE_X_TWO_EVENTS
        }
    if arm == "noul_binary":
        return {e: q for e, q in Q20.noul_questions().items() if e in Q20.BINARY_EVENTS}
    if arm == "score_binary":
        return {
            e: q for e, q in Q20.score_questions().items() if e in Q20.BINARY_EVENTS
        }
    if arm == "choice_binary":
        return Q20.choice_binary_questions()
    if arm == "choice_1x2":
        return Q20.choice_1x2_question()
    raise ValueError(f"unknown arm {arm}")


def call_with_retry(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1 + len(RETRY_DELAYS_S)):
        request_time = utc_now_iso()
        try:
            result = client.system_one(state=state, questions=questions)
        except (JevAuthError, JevValidationError, JevMalformedResponseError) as exc:
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "request_time_utc": request_time,
                    "error_kind": type(exc).__name__,
                    "message": str(exc)[:500],
                    "status_code": getattr(exc, "status_code", None),
                }
            )
            return None, attempts
        except (JevTimeoutError, JevRateLimitError, JevAPIError) as exc:
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "request_time_utc": request_time,
                    "error_kind": type(exc).__name__,
                    "message": str(exc)[:500],
                    "status_code": getattr(exc, "status_code", None),
                    "request_id": getattr(exc, "request_id", None),
                }
            )
            if attempt < len(RETRY_DELAYS_S):
                time.sleep(RETRY_DELAYS_S[attempt])
            continue
        response_time = utc_now_iso()
        usage = result.usage if isinstance(result.usage, dict) else {}
        input_tokens = usage.get("input_tokens")
        return {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": round(result.latency_ms, 1),
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
            "model_returned": result.model,
            "response_time_utc": response_time,
            "raw_response": result.body,
        }, attempts
    return None, attempts


def run_one_call(
    client: JevClient,
    model: str,
    fixture: dict[str, Any],
    fx_index: int,
    state: dict[str, Any],
    arm: str,
) -> dict[str, Any]:
    questions = arm_questions(arm)
    request_time = utc_now_iso()
    body, attempts = call_with_retry(client, state, questions)
    trial: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "run_local_id": f"{fixture['match_id']}:{arm}",
        "fixture_index": fx_index,
        "match_id": fixture["match_id"],
        "competition": fixture["competition"],
        "season_start": fixture["season_start"],
        "cohort": fixture["cohort"],
        "round": fixture["round"],
        "arm": arm,
        "state_variant": "named_full",
        "state_sha256": fixture["state_sha256"],
        "question_set_version": Q20.QUESTION_SET_VERSION,
        "model_requested": model,
        "kickoff_utc": fixture["kickoff_utc"],
        "cutoff_utc": fixture["cutoff_utc"],
        "request_time_utc": request_time,
        "attempts": attempts,
        "retries": max(0, len(attempts) - 1) if body is not None else len(attempts),
        "repeat_index": 1,
        "error": None,
        "parsed": {},
        "fixture_labels": fixture["labels"],
    }
    if body is None:
        trial["error"] = {
            "kind": attempts[-1]["error_kind"] if attempts else "unknown",
            "attempts": attempts,
        }
        trial["parsed"] = {"validation": "not_attempted"}
        return trial
    trial.update(body)
    try:
        trial["parsed"] = exp020.parse_call(arm, body["raw_response"])
    except Exception as exc:
        trial["parsed"] = {
            "validation": "parser_error",
            "rejections": [f"{type(exc).__name__}: {exc}"],
        }
        trial["error"] = {"kind": "parser_exception", "message": str(exc)[:300]}
    return trial


def summarize(
    stream_lines: list[dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, Any]:
    return exp020.analyze(stream_lines, protocol)


def main() -> int:
    freeze_only = "--freeze-only" in sys.argv[1:]
    load_env()
    model = DEFAULT_MODEL
    base_url = DEFAULT_BASE_URL
    started = utc_now_iso()

    eligible, exclusions = load_and_select()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if PROTOCOL_PATH.exists():
        protocol = json.loads(PROTOCOL_PATH.read_text())
        if protocol["n_fixtures"] != len(eligible) or protocol["fixtures"][0][
            "match_id"
        ] != canonical_fixture_id(eligible):
            print(
                "FATAL: frozen 021 protocol no longer matches the eligible set; refusing to run.",
                file=sys.stderr,
            )
            return 2
        print(
            f"Protocol already frozen at {protocol['frozen_at_utc']} ({protocol['n_fixtures']} fixtures); reusing."
        )
    else:
        protocol = freeze_protocol(eligible, exclusions)
        write_json(PROTOCOL_PATH, protocol)
        print(
            f"Froze 021 protocol: {protocol['n_fixtures']} fixtures, {protocol['n_fixtures'] * len(ARMS)} planned calls."
        )
    if freeze_only:
        print("Freeze-only mode: no API calls made.")
        return 0

    # Resume support: load completed trial keys from the append-only stream.
    done: set[str] = set()
    stream_lines: list[dict[str, Any]] = []
    if STREAM_PATH.exists():
        with STREAM_PATH.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                stream_lines.append(rec)
                done.add(rec["run_local_id"])
        print(f"Resuming: {len(done)} calls already recorded in {STREAM_PATH.name}.")

    rng = np.random.RandomState(SEED + 2)
    fixtures_by_id = {f["match_id"]: f for f in protocol["fixtures"]}
    if not STATES_PATH.exists():
        print(
            "FATAL: frozen states file missing; cannot replay faithfully.",
            file=sys.stderr,
        )
        return 2
    frozen_states: dict[str, dict[str, Any]] = json.loads(STATES_PATH.read_text())
    exit_code = 0

    try:
        with (
            JevClient(model=model, base_url=base_url) as client,
            STREAM_PATH.open("a") as stream,
        ):
            for fx_index, fixture in enumerate(protocol["fixtures"]):
                match_id = fixture["match_id"]
                state = frozen_states.get(match_id)
                if state is None or canonical_hash(state) != fixture["state_sha256"]:
                    print(
                        f"FATAL: frozen state missing or corrupt for {match_id}.",
                        file=sys.stderr,
                    )
                    return 2
                arm_order = list(ARMS)
                rng.shuffle(arm_order)
                for arm in arm_order:
                    if f"{match_id}:{arm}" in done:
                        continue
                    trial = run_one_call(client, model, fixture, fx_index, state, arm)
                    stream.write(
                        json.dumps(trial, ensure_ascii=False, allow_nan=False) + "\n"
                    )
                    stream.flush()
                    stream_lines.append(trial)
                    status = (
                        trial["parsed"]["validation"]
                        if trial["error"] is None
                        else "ERROR"
                    )
                    if fx_index % 25 == 0 or status != "ok":
                        print(
                            f"[{fx_index + 1}/{len(fixtures_by_id)}] {arm} {match_id} -> {status}",
                            flush=True,
                        )
                    if trial["error"] is not None or status != "ok":
                        exit_code = 1
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    analysis = summarize(stream_lines, protocol)
    path = next_run_path(RESULTS_DIR)
    write_json(
        path,
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": path.stem,
            "timestamp_utc": started,
            "protocol_version": protocol["protocol_version"],
            "stream_path": str(STREAM_PATH.relative_to(REPO_ROOT)),
            "model_requested": model,
            "git_sha": git_sha(),
            "question_set_version": Q20.QUESTION_SET_VERSION,
            "summary": analysis,
            "note": "Per-call records live in stream-001.jsonl (append-only); this file holds the run summary.",
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print(json.dumps(analysis["totals"], indent=2))
    return exit_code


def canonical_fixture_id(eligible: pd.DataFrame) -> str:
    return eligible.iloc[0]["match_id"]


if __name__ == "__main__":
    raise SystemExit(main())
