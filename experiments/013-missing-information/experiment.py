#!/usr/bin/env python3
"""Experiment 013 — Missing Information.

Tests whether Jev treats "explicitly unknown," "unmentioned," and
"explicitly insufficient information" as equivalent or distinct states.
Includes a positive control (known color) as an anchor.
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

EXPERIMENT_ID = "013-missing-information"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

CASES = [
    {
        "case_id": "unknown",
        "state": "The color of the ball is unknown.",
        "kind": "explicitly unknown",
    },
    {
        "case_id": "unmentioned",
        "state": "There is a ball on the table.",
        "kind": "unmentioned (no color info)",
    },
    {
        "case_id": "insufficient",
        "state": "There is not enough information to determine the color of the ball.",
        "kind": "explicitly insufficient",
    },
    {
        "case_id": "control_blue",
        "state": "The ball is blue.",
        "kind": "positive control (known)",
    },
]

QUESTIONS = {
    "is_blue": {
        "type": "noul",
        "instructions": "Is the color blue?",
    },
    "color_choice": {
        "type": "choice",
        "instructions": "What is the color of the ball?",
        "criteria": {
            "blue": "The ball is blue.",
            "not_blue": "The ball is a color other than blue.",
            "unknown": "The color of the ball is unknown.",
        },
    },
    "blue_certainty": {
        "type": "score",
        "instructions": "How certain is the color of the ball being blue?",
        "criteria": [
            {"score": 0, "label": "certainly not blue"},
            {"score": 1, "label": "likely not blue"},
            {"score": 2, "label": "unknown / even chance"},
            {"score": 3, "label": "likely blue"},
            {"score": 4, "label": "certainly blue"},
        ],
    },
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
            for case in CASES:
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, case, repeat)
                    trials.append(trial)
                    _print_trial(trial)
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
                "repeats_per_case": REPEATS,
                "cases": CASES,
                "questions": QUESTIONS,
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


def _run_trial(client: JevClient, case: dict, repeat: int) -> dict:
    record = {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "state": case["state"],
        "repeat": repeat,
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

    answers = result.body.get("answers", {})
    parsed: dict[str, dict] = {}

    noul = answers.get("is_blue", {})
    parsed["is_blue"] = {"type": noul.get("type"), "noul": noul.get("noul")}

    choice = answers.get("color_choice", {})
    parsed["color_choice"] = {
        "type": choice.get("type"),
        "choice": choice.get("choice"),
        "probabilities": choice.get("probabilities"),
        "confidence": choice.get("confidence"),
    }

    score = answers.get("blue_certainty", {})
    parsed["blue_certainty"] = {
        "type": score.get("type"),
        "score": score.get("score"),
        "probabilities": score.get("probabilities"),
        "confidence": score.get("confidence"),
    }

    record["parsed"] = parsed
    return record


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


def _print_trial(trial: dict) -> None:
    p = trial.get("parsed", {})
    noul = p.get("is_blue", {}).get("noul")
    choice = p.get("color_choice", {})
    score = p.get("blue_certainty", {})
    print(
        f"{trial['case_id']} r{trial['repeat']} noul={noul} "
        f"choice={choice.get('choice')}(conf {choice.get('confidence')}) "
        f"score={score.get('score')}(conf {score.get('confidence')})"
    )


def _analyze(trials: list[dict]) -> dict:
    by_case: dict[str, list[dict]] = {}
    for t in trials:
        by_case.setdefault(t["case_id"], []).append(t)

    case_details = {}
    for case_id, ts in by_case.items():
        nouls = [
            t["parsed"]["is_blue"].get("noul")
            for t in ts
            if t["parsed"]["is_blue"].get("noul") is not None
        ]
        choices = [
            t["parsed"]["color_choice"].get("choice")
            for t in ts
            if t["parsed"]["color_choice"].get("choice")
        ]
        scores = [
            t["parsed"]["blue_certainty"].get("score")
            for t in ts
            if t["parsed"]["blue_certainty"].get("score") is not None
        ]
        confs = [
            t["parsed"]["color_choice"].get("confidence")
            for t in ts
            if t["parsed"]["color_choice"].get("confidence") is not None
        ]
        case_details[case_id] = {
            "nouls": nouls,
            "noul_mean": round(statistics.mean(nouls), 4) if nouls else None,
            "choices": choices,
            "choice_set": sorted(set(choices)),
            "scores": scores,
            "score_mean": round(statistics.mean(scores), 4) if scores else None,
            "confidences": confs,
            "conf_mean": round(statistics.mean(confs), 4) if confs else None,
        }

    # Compare the three missing-info cases (unknown, unmentioned, insufficient).
    missing_cases = ["unknown", "unmentioned", "insufficient"]
    missing_noul_means = [
        case_details[c]["noul_mean"]
        for c in missing_cases
        if case_details[c]["noul_mean"] is not None
    ]
    noul_range = (
        round(max(missing_noul_means) - min(missing_noul_means), 4)
        if len(missing_noul_means) > 1
        else None
    )

    # Do the missing cases share a Choice label?
    missing_choice_sets = [
        set(case_details[c]["choice_set"])
        for c in missing_cases
        if case_details[c]["choice_set"]
    ]
    all_same_choice = len(missing_choice_sets) > 0 and all(
        s == missing_choice_sets[0] for s in missing_choice_sets
    )

    # Are missing Noul means near 0 (< 0.2)?
    all_missing_near_zero = bool(
        missing_noul_means and all(m < 0.2 for m in missing_noul_means)
    )

    return {
        "by_case": case_details,
        "missing_cases": missing_cases,
        "missing_noul_means": missing_noul_means,
        "noul_range_across_missing": noul_range,
        "jitter_baseline": 0.02,
        "missing_nouls_equivalent": bool(noul_range is not None and noul_range <= 0.03),
        "missing_choices_all_same": all_same_choice,
        "missing_nouls_near_zero": all_missing_near_zero,
        "control_blue_noul_mean": case_details["control_blue"]["noul_mean"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
