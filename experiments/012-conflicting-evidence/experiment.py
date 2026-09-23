#!/usr/bin/env python3
"""Experiment 012 — Conflicting Evidence.

Tests how Jev handles internally contradictory state. Each state explicitly
asserts two mutually-exclusive facts plus a tie-breaker establishing they
occur simultaneously. Probes Noul, Choice, and Score behavior.
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

EXPERIMENT_ID = "012-conflicting-evidence"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

CASES = [
    {
        "case_id": "sky",
        "state": (
            "Statement 1: The sky is blue. "
            "Statement 2: The sky is grey. "
            "Statement 3: The observation was made during the same time period."
        ),
        "noul_q": "Is the sky blue?",
        "choice_options": {
            "blue": "The sky is blue.",
            "grey": "The sky is grey.",
            "uncertain": "The sky color cannot be determined from the statements.",
        },
    },
    {
        "case_id": "coin",
        "state": (
            "Statement 1: The coin shows heads. "
            "Statement 2: The coin shows tails. "
            "Statement 3: The observation was made during the same time period."
        ),
        "noul_q": "Does the coin show heads?",
        "choice_options": {
            "heads": "The coin shows heads.",
            "tails": "The coin shows tails.",
            "uncertain": "The coin face cannot be determined from the statements.",
        },
    },
    {
        "case_id": "direction",
        "state": (
            "Statement 1: The car is moving north. "
            "Statement 2: The car is moving south. "
            "Statement 3: The observation was made during the same time period."
        ),
        "noul_q": "Is the car moving north?",
        "choice_options": {
            "north": "The car is moving north.",
            "south": "The car is moving south.",
            "uncertain": "The car's direction cannot be determined from the statements.",
        },
    },
]

SCORE_QUESTIONS_TEMPLATE = {
    "contradiction_level": {
        "type": "score",
        "instructions": (
            "Based on the statements, how contradictory is the situation?"
        ),
        "criteria": [
            {"score": 0, "label": "completely clear, one side"},
            {"score": 1, "label": "mostly clear, one side dominant"},
            {"score": 2, "label": "mixed, balanced"},
            {"score": 3, "label": "mostly contradictory, little clarity"},
            {"score": 4, "label": "fully contradictory, no way to decide"},
        ],
    }
}


def _questions_for_case(case: dict) -> dict[str, dict]:
    questions: dict[str, dict] = {
        "is_x": {
            "type": "noul",
            "instructions": case["noul_q"],
        },
        "which_x": {
            "type": "choice",
            "instructions": "Which statement best describes the situation?",
            "criteria": case["choice_options"],
        },
    }
    questions.update(SCORE_QUESTIONS_TEMPLATE)
    return questions


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
                questions = _questions_for_case(case)
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, case, repeat, questions)
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
                "cases": [
                    {
                        "case_id": c["case_id"],
                        "state": c["state"],
                        "noul_q": c["noul_q"],
                        "choice_options": c["choice_options"],
                    }
                    for c in CASES
                ],
                "score_questions": SCORE_QUESTIONS_TEMPLATE,
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
    case: dict,
    repeat: int,
    questions: dict[str, dict],
) -> dict:
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
        "model_returned": None,
        "response_headers": {},
        "raw_response": None,
        "parsed": {},
        "error": None,
    }
    try:
        result = client.system_one(state=case["state"], questions=questions)
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

    noul = answers.get("is_x", {})
    parsed["is_x"] = {"type": noul.get("type"), "noul": noul.get("noul")}

    choice = answers.get("which_x", {})
    parsed["which_x"] = {
        "type": choice.get("type"),
        "choice": choice.get("choice"),
        "probabilities": choice.get("probabilities"),
        "confidence": choice.get("confidence"),
    }

    score = answers.get("contradiction_level", {})
    parsed["contradiction_level"] = {
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
    noul = p.get("is_x", {}).get("noul")
    choice = p.get("which_x", {})
    score = p.get("contradiction_level", {})
    print(
        f"{trial['case_id']} r{trial['repeat']} noul={noul} "
        f"choice={choice.get('choice')}(conf {choice.get('confidence')}) "
        f"score={score.get('score')}(conf {score.get('confidence')})"
    )


def _analyze(trials: list[dict]) -> dict:
    by_case: dict[str, list[dict]] = {}
    for t in trials:
        by_case.setdefault(t["case_id"], []).append(t)

    result: dict = {"by_case": {}}
    all_nouls: list[float] = []
    all_confs: list[float] = []
    uncertain_choice_count = 0
    choice_count = 0
    case_details = {}

    for case_id, ts in by_case.items():
        nouls = [
            t["parsed"]["is_x"].get("noul")
            for t in ts
            if t["parsed"]["is_x"].get("noul") is not None
        ]
        choices = [
            t["parsed"]["which_x"].get("choice")
            for t in ts
            if t["parsed"]["which_x"].get("choice")
        ]
        scores = [
            t["parsed"]["contradiction_level"].get("score")
            for t in ts
            if t["parsed"]["contradiction_level"].get("score") is not None
        ]
        confs = [
            t["parsed"]["which_x"].get("confidence")
            for t in ts
            if t["parsed"]["which_x"].get("confidence") is not None
        ]

        noul_mean = round(statistics.mean(nouls), 4) if nouls else None
        score_mean = round(statistics.mean(scores), 4) if scores else None
        conf_mean = round(statistics.mean(confs), 4) if confs else None

        case_details[case_id] = {
            "nouls": nouls,
            "noul_mean": noul_mean,
            "choices": choices,
            "choice_set": sorted(set(choices)),
            "scores": scores,
            "score_mean": score_mean,
            "confs": confs,
            "conf_mean": conf_mean,
        }

        all_nouls.extend(nouls)
        all_confs.extend(confs)
        for ch in choices:
            choice_count += 1
            if ch == "uncertain":
                uncertain_choice_count += 1

    # Aggregate across cases.
    result["by_case"] = case_details
    result["all_nouls"] = all_nouls
    result["all_noul_mean"] = (
        round(statistics.mean(all_nouls), 4) if all_nouls else None
    )
    result["all_choice_confs"] = all_confs
    result["all_choice_conf_mean"] = (
        round(statistics.mean(all_confs), 4) if all_confs else None
    )
    result["all_choice_conf_min"] = round(min(all_confs), 4) if all_confs else None
    result["uncertain_choice_count"] = uncertain_choice_count
    result["total_choice_count"] = choice_count

    # Hypothesis checks.
    noul_means = [
        d["noul_mean"] for d in case_details.values() if d["noul_mean"] is not None
    ]
    if noul_means:
        result["h034_noul_means_in_uncertain_band"] = all(
            0.35 <= m <= 0.65 for m in noul_means
        )
    if choice_count:
        result["h035_majority_uncertain"] = uncertain_choice_count / choice_count > 0.5
    if all_confs:
        result["h036_confidence_below_0.9"] = statistics.mean(all_confs) < 0.9
    # Consistency: within each case, is the choice stable?
    choice_stability = {}
    for case_id, d in case_details.items():
        choice_stability[case_id] = len(d["choice_set"]) == 1
    result["h037_choice_stable_across_repeats"] = choice_stability

    return result


if __name__ == "__main__":
    raise SystemExit(main())
