#!/usr/bin/env python3
"""Experiment 009 — Wording Sensitivity.

Holds state, model, and primitive constant while varying question wording,
to measure whether semantically equivalent phrasing changes Noul output.
"""

from __future__ import annotations

import os
import statistics
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

EXPERIMENT_ID = "009-wording-sensitivity"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

STATE = "A bag contains 70 red balls and 30 blue balls. One ball is selected randomly."

WORDINGS = [
    {"id": "will_be_red", "text": "Will the selected ball be red?"},
    {"id": "likely_red", "text": "Is the selected ball likely to be red?"},
    {"id": "chance_red", "text": "What is the chance that the selected ball is red?"},
    {"id": "evidence_red", "text": "Does the evidence support the ball being red?"},
]

QUESTION_ID = "is_red"

GROUND_TRUTH = 0.70


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for wording in WORDINGS:
                questions = {
                    QUESTION_ID: {
                        "type": "noul",
                        "instructions": wording["text"],
                    }
                }
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, wording, repeat, questions)
                    trials.append(trial)
                    noul = trial.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
                    print(
                        f"{wording['id']} r{repeat} noul={noul} "
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
                "repeats_per_wording": REPEATS,
                "state": STATE,
                "question_id": QUESTION_ID,
                "wordings": [{"id": w["id"], "text": w["text"]} for w in WORDINGS],
                "ground_truth_p_red": GROUND_TRUTH,
                "jitter_baseline_from_008": 0.02,
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


def _run_trial(
    client: JevClient,
    wording: dict,
    repeat: int,
    questions: dict[str, dict],
) -> dict:
    record = {
        "wording_id": wording["id"],
        "wording": wording["text"],
        "repeat": repeat,
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
        "parsed": {},
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

    answer_data = result.body.get("answers", {}).get(QUESTION_ID, {})
    record["parsed"] = {
        QUESTION_ID: {
            "type": answer_data.get("type"),
            "noul": answer_data.get("noul"),
        }
    }
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
    # Group Noul values by wording.
    by_wording: dict[str, list[float]] = {}
    for t in trials:
        noul = t.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
        if noul is not None:
            by_wording.setdefault(t["wording_id"], []).append(noul)

    summaries = {}
    means = {}
    for wid, vals in by_wording.items():
        summaries[wid] = {
            "n": len(vals),
            "values": vals,
            "mean": round(statistics.mean(vals), 4),
            "median": round(statistics.median(vals), 4),
            "range": round(max(vals) - min(vals), 4),
        }
        means[wid] = statistics.mean(vals)

    all_vals = [v for vals in by_wording.values() for v in vals]
    wording_means = list(means.values())

    global_mean = statistics.mean(all_vals)
    overall_range = max(all_vals) - min(all_vals)
    mean_range = max(wording_means) - min(wording_means)
    mean_stdev = statistics.stdev(wording_means) if len(wording_means) > 1 else None

    return {
        "wording_means": {k: round(v, 4) for k, v in means.items()},
        "global_mean": round(global_mean, 4),
        "ground_truth": GROUND_TRUTH,
        "overall_range_all_repeats": round(overall_range, 4),
        "range_across_wording_means": round(mean_range, 4),
        "stdev_across_wording_means": round(mean_stdev, 4) if mean_stdev else None,
        "jitter_baseline": 0.02,
        "exceeds_jitter_baseline": mean_range > 0.02,
        "by_wording": summaries,
    }


if __name__ == "__main__":
    raise SystemExit(main())
