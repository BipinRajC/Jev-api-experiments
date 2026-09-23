#!/usr/bin/env python3
"""Experiment 014 — Score Interpolation.

Determines whether Jev's Score primitive produces intermediate (fractional)
values when evidence falls between rubric levels, and whether those values
are stable across repeats.
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

EXPERIMENT_ID = "014-score-interpolation"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

SCORE_QUESTION = {
    "evidence_level": {
        "type": "score",
        "instructions": "What level of evidence supports this hypothesis?",
        "criteria": [
            {"score": 0, "label": "no evidence"},
            {"score": 1, "label": "very weak evidence"},
            {"score": 2, "label": "weak evidence"},
            {"score": 3, "label": "moderate evidence"},
            {"score": 4, "label": "strong evidence"},
            {"score": 5, "label": "overwhelming evidence"},
        ],
    }
}

CASES = [
    {
        "case_id": "no_evidence",
        "state": "Hypothesis: The compound affects memory. There is no evidence either way about the hypothesis.",
        "intended_level": 0,
    },
    {
        "case_id": "very_weak",
        "state": "Hypothesis: The compound affects memory. A single tiny anecdotal report suggests the hypothesis might be true, but it is completely unconvincing and there is no data.",
        "intended_level": 1,
    },
    {
        "case_id": "weak",
        "state": "Hypothesis: The compound affects memory. One small exploratory study with a nonsignificant result slightly hints at the hypothesis. No replication.",
        "intended_level": 2,
    },
    {
        "case_id": "moderate",
        "state": "Hypothesis: The compound affects memory. Two independent studies find moderate effects, but with wide confidence intervals and one failed replication.",
        "intended_level": 3,
    },
    {
        "case_id": "strong",
        "state": "Hypothesis: The compound affects memory. Five large, well-powered studies consistently confirm the hypothesis. Effect sizes are small but stable.",
        "intended_level": 4,
    },
    {
        "case_id": "overwhelming",
        "state": "Hypothesis: The compound affects memory. Dozens of independent replications across many labs confirm the hypothesis with large, precise effect sizes. It is scientific consensus.",
        "intended_level": 5,
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
                "score_question": SCORE_QUESTION,
                "cases": CASES,
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
        "intended_level": case["intended_level"],
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
        result = client.system_one(state=case["state"], questions=SCORE_QUESTION)
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

    score = result.body.get("answers", {}).get("evidence_level", {})
    record["parsed"] = {
        "evidence_level": {
            "type": score.get("type"),
            "score": score.get("score"),
            "probabilities": score.get("probabilities"),
            "confidence": score.get("confidence"),
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


def _print_trial(trial: dict) -> None:
    p = trial.get("parsed", {}).get("evidence_level", {})
    print(
        f"{trial['case_id']} r{trial['repeat']} "
        f"score={p.get('score')} conf={p.get('confidence')} "
        f"probs={p.get('probabilities')}"
    )


def _analyze(trials: list[dict]) -> dict:
    by_case: dict[str, list[dict]] = {}
    for t in trials:
        by_case.setdefault(t["case_id"], []).append(t)

    case_details = {}
    case_means = {}
    for case_id, ts in by_case.items():
        scores = [
            t["parsed"]["evidence_level"].get("score")
            for t in ts
            if t["parsed"]["evidence_level"].get("score") is not None
        ]
        confs = [
            t["parsed"]["evidence_level"].get("confidence")
            for t in ts
            if t["parsed"]["evidence_level"].get("confidence") is not None
        ]
        intended = ts[0]["intended_level"]
        mean = statistics.mean(scores) if scores else None
        case_means[case_id] = mean
        case_details[case_id] = {
            "intended_level": intended,
            "scores": scores,
            "mean": round(mean, 4) if mean is not None else None,
            "range": round(max(scores) - min(scores), 4) if scores else None,
            "confidences": confs,
            "conf_mean": round(statistics.mean(confs), 4) if confs else None,
        }

    all_scores = [
        t["parsed"]["evidence_level"].get("score")
        for t in trials
        if t["parsed"]["evidence_level"].get("score") is not None
    ]

    # Are any scores non-integer?
    non_integer_count = sum(1 for s in all_scores if s != int(s))

    # Monotonic increase in means with intended level?
    ordered_means = [
        case_means[c["case_id"]]
        for c in CASES
        if case_means.get(c["case_id"]) is not None
    ]
    monotonic = (
        all(
            ordered_means[i] <= ordered_means[i + 1]
            for i in range(len(ordered_means) - 1)
        )
        if len(ordered_means) > 1
        else None
    )

    # Coverage of levels (mean approximates intended level)?
    # Fractional stability: max within-case range across all cases.
    within_case_ranges = [
        d["range"] for d in case_details.values() if d["range"] is not None
    ]
    max_within_case_range = (
        round(max(within_case_ranges), 4) if within_case_ranges else None
    )

    return {
        "by_case": case_details,
        "all_scores": all_scores,
        "non_integer_count": non_integer_count,
        "total_scores": len(all_scores),
        "any_non_integer": non_integer_count > 0,
        "means_by_intended_level": {
            case_id: case_means[case_id] for case_id in case_means
        },
        "monotonic_with_intended": monotonic,
        "max_within_case_range": max_within_case_range,
    }


if __name__ == "__main__":
    raise SystemExit(main())
