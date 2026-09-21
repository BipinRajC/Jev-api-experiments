#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.choice import extract_choice, probabilities_sum  # noqa: E402
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

EXPERIMENT_ID = "003-choice"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3
QUESTION_ID = "sky_color"
OPTIONS = ("blue", "grey", "unspecified")
QUESTIONS = {
    QUESTION_ID: {
        "type": "choice",
        "instructions": "What color is the sky described as?",
        "criteria": {
            "blue": "The sky is described as blue",
            "grey": "The sky is described as grey, gray, or overcast",
            "unspecified": "The sky color is not stated",
        },
    }
}
CASES = [
    {
        "case_id": "clear_blue",
        "state": "The sky is blue.",
        "intended": "blue",
    },
    {
        "case_id": "clear_grey",
        "state": "The sky is overcast and grey.",
        "intended": "grey",
    },
    {
        "case_id": "ambiguous",
        "state": "The weather looks mixed today.",
        "intended": "unspecified",
    },
]


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for case in CASES:
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, case, repeat)
                    trials.append(trial)
                    print(
                        f"{case['case_id']} r{repeat} HTTP {trial.get('http_status')} "
                        f"choice={trial.get('choice')} conf={trial.get('confidence')} "
                        f"p={trial.get('probabilities')}"
                    )
                    if trial.get("error"):
                        exit_code = 1
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    summary = _summarize(trials)
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
                "repeats_per_case": REPEATS,
                "question_id": QUESTION_ID,
                "questions": QUESTIONS,
                "variable_changed": "state evidence for sky color",
                "held_constant": [
                    "model",
                    "endpoint",
                    "question type",
                    "question instructions",
                    "criteria",
                    "question id",
                ],
                "cases": CASES,
            },
            "summary": summary,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print("summary:", summary)
    return exit_code


def _run_trial(client: JevClient, case: dict, repeat: int) -> dict:
    record = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "state": case["state"],
        "timestamp": utc_now_iso(),
        "http_status": None,
        "request_id": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "choice": None,
        "confidence": None,
        "probabilities": None,
        "probability_sum": None,
        "model_returned": None,
        "response_headers": {},
        "raw_response": None,
        "error": None,
    }
    try:
        result = client.system_one(state=case["state"], questions=QUESTIONS)
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
    try:
        parsed = extract_choice(result.body, QUESTION_ID)
    except ValueError as exc:
        record["error"] = {"kind": "parse", "message": str(exc)}
        return record
    record["choice"] = parsed["choice"]
    record["confidence"] = parsed["confidence"]
    record["probabilities"] = parsed["probabilities"]
    record["probability_sum"] = probabilities_sum(parsed["probabilities"])
    return record


def _summarize(trials: list[dict]) -> dict:
    by_case: dict[str, list[dict]] = {}
    for trial in trials:
        if trial.get("choice") is None:
            continue
        by_case.setdefault(trial["case_id"], []).append(trial)
    summary: dict[str, dict] = {}
    for case_id, rows in by_case.items():
        labels = [row["choice"] for row in rows]
        confs = [row["confidence"] for row in rows]
        sums = [row["probability_sum"] for row in rows]
        option_means = {
            option: sum(row["probabilities"].get(option, 0.0) for row in rows)
            / len(rows)
            for option in OPTIONS
        }
        summary[case_id] = {
            "n": len(rows),
            "choices": labels,
            "unique_choices": sorted(set(labels)),
            "confidence_min": min(confs),
            "confidence_max": max(confs),
            "confidence_mean": sum(confs) / len(confs),
            "probability_sum_min": min(sums),
            "probability_sum_max": max(sums),
            "mean_probabilities": option_means,
        }
    return summary


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


if __name__ == "__main__":
    raise SystemExit(main())
