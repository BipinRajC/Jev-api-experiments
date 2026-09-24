#!/usr/bin/env python3
"""Experiment 018 — Rate-Limit Behavior (Add-on B).

Observes whether a moderate burst of rapid requests (within documented
limits) triggers HTTP 429, and captures any rate-limit headers. Deliberately
does NOT exceed documented limits to avoid manufacturing an outage.
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
    JevClient,
    JevConfigError,
)
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    sanitize_headers,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "018-rate-limit"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
N_REQUESTS = 10

STATE = "A bag contains 70 red balls and 30 blue balls. One ball is selected randomly."

QUESTIONS = {
    "is_red": {
        "type": "noul",
        "instructions": "Will the selected ball be red?",
    }
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
            # Use post_raw so a 429 is captured without raising.
            for i in range(1, N_REQUESTS + 1):
                trial = _run_trial(client, i)
                trials.append(trial)
                print(
                    f"req {i:02d} status={trial.get('http_status')} "
                    f"lat={trial.get('latency_ms'):.0f} "
                    f"retry_after={trial.get('retry_after')}"
                )
                if trial.get("http_status") != 200:
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
                "n_requests": N_REQUESTS,
                "state": STATE,
                "questions": QUESTIONS,
                "interval": "back-to-back (no delay)",
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


def _run_trial(client: JevClient, index: int) -> dict:
    record = {
        "request_index": index,
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
        "retry_after": None,
        "error": None,
    }
    try:
        result = client.post_raw(
            {
                "state": STATE,
                "model": client.model,
                "questions": QUESTIONS,
            }
        )
    except Exception as exc:  # noqa: BLE001 - capture all for analysis
        record["error"] = {"kind": "exception", "message": str(exc)}
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
            "retry_after": (
                result.headers.get("retry-after")
                or result.headers.get("x-ratelimit-reset")
                or result.headers.get("ratelimit-reset")
            ),
        }
    )
    return record


def _analyze(trials: list[dict]) -> dict:
    statuses = [t["http_status"] for t in trials]
    ok_count = sum(1 for s in statuses if s == 200)
    non_200 = [
        (t["request_index"], t["http_status"])
        for t in trials
        if t["http_status"] != 200
    ]
    latencies = [t["latency_ms"] for t in trials if t["latency_ms"] is not None]
    retry_afters = [t["retry_after"] for t in trials if t["retry_after"]]

    return {
        "total_requests": len(trials),
        "ok_200_count": ok_count,
        "non_200": non_200,
        "any_429": any(t["http_status"] == 429 for t in trials),
        "latency_mean_ms": round(sum(latencies) / len(latencies), 1)
        if latencies
        else None,
        "retry_after_values": retry_afters,
        "documented_limits": {"rpm": 1200, "tokens_per_s": 250000},
    }


if __name__ == "__main__":
    raise SystemExit(main())
