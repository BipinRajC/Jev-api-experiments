#!/usr/bin/env python3
"""Experiment 016 — Large Fan-out (Add-on D).

Tests how Jev handles large batches of questions (3/5/10/20) in a single
request, measuring token usage, latency, response structure, and failures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

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
    sanitize_headers,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "016-fan-out"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID

STATE = (
    "An urn contains 60 red, 25 blue, and 15 green balls. One ball is drawn randomly."
)

# Pool of distinct Noul propositions about the draw. Slice per batch size.
PROPOSITIONS = [
    "Will the drawn ball be red?",
    "Will the drawn ball be blue?",
    "Will the drawn ball be green?",
    "Will the drawn ball be a warm color (red)?",
    "Will the drawn ball be a cool color (blue or green)?",
    "Is red the most likely outcome?",
    "Is blue more likely than green?",
    "Is green the least likely outcome?",
    "Will the ball not be blue?",
    "Will the ball not be green?",
    "Is there more than a 50% chance the ball is red?",
    "Is the chance of blue over 20%?",
    "Is the chance of green under 20%?",
    "Will the ball be either red or blue?",
    "Will the ball be either red or green?",
    "Is the drawn ball more likely to be red than non-red?",
    "Is the probability of green less than 25%?",
    "Is the probability of blue less than 30%?",
    "Is the probability of red above 50%?",
    "Will the ball be one of the two more common colors?",
]

BATCH_SIZES = [3, 5, 10, 20]


def _questions_for_count(n: int) -> dict[str, dict]:
    return {
        f"q{i:02d}": {"type": "noul", "instructions": PROPOSITIONS[i]} for i in range(n)
    }


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for n in BATCH_SIZES:
                questions = _questions_for_count(n)
                trial = _run_trial(client, n, questions)
                trials.append(trial)
                n_answers = trial.get("n_answers_returned")
                print(
                    f"n_questions={n} status={trial.get('http_status')} "
                    f"n_answers_returned={n_answers} "
                    f"in={trial.get('input_tokens')} out={trial.get('output_tokens')} "
                    f"lat={trial.get('latency_ms'):.0f}"
                )
                if trial.get("error"):
                    exit_code = 1
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    analysis = _analyze(trials)

    path = next_run_path(RESULTS_DIR)
    write_json(
        path,
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": path.stem,
            "timestamp": started_at,
            "model_requested": model,
            "api": {
                "provider": "typesafe_direct",
                "base_url": base_url,
                "endpoint": "/v1/systemone",
                "method": "POST",
            },
            "design": {
                "state": STATE,
                "batch_sizes": BATCH_SIZES,
                "propositions": PROPOSITIONS,
            },
            "analysis": analysis,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print("--- Analysis ---")
    for key, val in analysis.items():
        print(f"  {key}: {val}")
    return exit_code


def _run_trial(client: JevClient, n: int, questions: dict[str, dict]) -> dict:
    record = {
        "n_questions": n,
        "state": STATE,
        "timestamp": utc_now_iso(),
        "http_status": None,
        "request_id": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "model_returned": None,
        "response_headers": {},
        "raw_response": None,
        "n_answers_returned": None,
        "answers_parsed": None,
        "error": None,
    }
    try:
        result = client.system_one(state=STATE, questions=questions)
    except JevAuthError as exc:
        record["error"] = _error("auth", exc)
        return record
    except JevValidationError as exc:
        record["error"] = _error("validation", exc)
        return record
    except JevRateLimitError as exc:
        record["error"] = _error("rate_limit", exc)
        return record
    except JevTimeoutError as exc:
        record["error"] = {"kind": "timeout", "message": str(exc)}
        return record
    except JevMalformedResponseError as exc:
        record["error"] = {"kind": "malformed_response", "message": str(exc)}
        return record
    except JevAPIError as exc:
        record["error"] = _error("api", exc)
        return record

    usage = result.usage if isinstance(result.usage, dict) else {}
    input_tokens = usage.get("input_tokens")
    record.update(
        {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": result.latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
            "model_returned": result.model,
            "response_headers": sanitize_headers(result.headers),
            "raw_response": result.body,
        }
    )

    answers = result.body.get("answers", {})
    record["n_answers_returned"] = len(answers)
    record["answers_parsed"] = {qid: ans.get("noul") for qid, ans in answers.items()}
    return record


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


def _analyze(trials: list[dict]) -> dict:
    details = []
    for t in trials:
        n = t["n_questions"]
        details.append(
            {
                "n_questions": n,
                "http_status": t.get("http_status"),
                "input_tokens": t.get("input_tokens"),
                "output_tokens": t.get("output_tokens"),
                "latency_ms": t.get("latency_ms"),
                "n_answers_returned": t.get("n_answers_returned"),
            }
        )

    # Token per question ratio (scaling).
    token_scaling = []
    for d in details:
        if d["input_tokens"] and d["n_questions"]:
            token_scaling.append(
                {
                    "n_questions": d["n_questions"],
                    "tokens_per_question": round(
                        d["input_tokens"] / d["n_questions"], 1
                    ),
                }
            )

    all_success = all(d["http_status"] == 200 for d in details)
    all_complete = all(d["n_answers_returned"] == d["n_questions"] for d in details)
    latency_increases = (
        all(
            details[i]["latency_ms"] <= details[i + 1]["latency_ms"]
            for i in range(len(details) - 1)
        )
        if len(details) > 1
        else None
    )

    return {
        "details": details,
        "all_success": all_success,
        "all_answers_complete": all_complete,
        "latency_increases_with_count": latency_increases,
        "token_scaling": token_scaling,
        "input_tokens_3": details[0]["input_tokens"] if details else None,
        "input_tokens_20": details[-1]["input_tokens"] if details else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
