#!/usr/bin/env python3
"""Experiment 010 — Irrelevant Information.

Tests whether appending semantically-irrelevant context to a state changes
Jev's Noul output. The relevant facts stay identical; only irrelevant
distractor sentences are added.
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

EXPERIMENT_ID = "010-irrelevant-information"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 2

BASE_STATE = (
    "A box contains 70 red balls and 30 blue balls. One ball is selected randomly."
)

QUESTION_ID = "is_red"
QUESTION_TEXT = "Will the selected ball be red?"

GROUND_TRUTH = 0.70

# Irrelevant facts (none mention color, so they cannot directly affect the
# 70/30 decision; all are environmental/sensory distractors).
IRRELEVANT_FACTS = [
    "The experiment is being conducted on a Tuesday.",
    "The observer is wearing a blue shirt.",
    "The room temperature is 22 degrees Celsius.",
    "The box is sitting on a wooden table.",
    "A ceiling light illuminates the room.",
    "The floor is tiled with ceramic squares.",
    "A clock on the wall shows 3:15 PM.",
    "The lab is on the third floor of the building.",
    "A window faces west toward the parking lot.",
    "The air in the room smells faintly of coffee.",
    "Several papers are stacked on the corner of the desk.",
    "A fan gently circulates the air.",
    "The door to the hallway is slightly ajar.",
    "The carpet under the table is dark grey.",
    "A small plant sits on the windowsill.",
    "The researcher writes notes with a black pen.",
    "Background music plays softly from a speaker.",
    "The power outlet is on the north wall.",
    "A poster of a city skyline hangs on the wall.",
    "The ceiling is white with two recessed lights.",
]

# Note: fact #2 says the observer wears a "blue" shirt, but that refers to
# clothing, not to the balls. It does not change the ball composition.

LEVELS = [
    {"id": "baseline", "n_facts": 0},
    {"id": "plus_1", "n_facts": 1},
    {"id": "plus_5", "n_facts": 5},
    {"id": "plus_20", "n_facts": 20},
]


def _state_for_level(level: dict) -> str:
    n = level["n_facts"]
    if n == 0:
        return BASE_STATE
    facts = IRRELEVANT_FACTS[:n]
    return BASE_STATE + " " + " ".join(facts)


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for level in LEVELS:
                state = _state_for_level(level)
                questions = {
                    QUESTION_ID: {
                        "type": "noul",
                        "instructions": QUESTION_TEXT,
                    }
                }
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, level, repeat, state, questions)
                    trials.append(trial)
                    noul = trial.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
                    print(
                        f"{level['id']} (n_facts={level['n_facts']}) r{repeat} "
                        f"noul={noul} lat={trial.get('latency_ms'):.0f} "
                        f"in={trial.get('input_tokens')}"
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
                "repeats_per_level": REPEATS,
                "base_state": BASE_STATE,
                "question_id": QUESTION_ID,
                "question_text": QUESTION_TEXT,
                "ground_truth_p_red": GROUND_TRUTH,
                "irrelevant_facts": IRRELEVANT_FACTS,
                "levels": LEVELS,
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
    level: dict,
    repeat: int,
    state: str,
    questions: dict[str, dict],
) -> dict:
    record = {
        "level": level["id"],
        "n_facts": level["n_facts"],
        "repeat": repeat,
        "state": state,
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
        result = client.system_one(state=state, questions=questions)
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
    by_level: dict[str, list[float]] = {}
    for t in trials:
        noul = t.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
        if noul is not None:
            by_level.setdefault(t["level"], []).append(noul)

    level_means = {}
    level_details = {}
    for level_id in ["baseline", "plus_1", "plus_5", "plus_20"]:
        vals = by_level.get(level_id, [])
        if vals:
            level_means[level_id] = round(statistics.mean(vals), 4)
            level_details[level_id] = {
                "values": vals,
                "mean": round(statistics.mean(vals), 4),
                "range": round(max(vals) - min(vals), 4),
            }
        else:
            level_details[level_id] = {"values": [], "mean": None, "range": None}

    baseline_mean = level_means.get("baseline")

    # Drift from baseline for each non-baseline level.
    drifts = {}
    for level_id in ["plus_1", "plus_5", "plus_20"]:
        if baseline_mean is not None and level_id in level_means:
            drifts[level_id] = round(level_means[level_id] - baseline_mean, 4)

    # Max absolute drift from baseline across all levels.
    max_abs_drift = None
    if baseline_mean is not None:
        abs_drifts = [
            abs(level_means[level_id] - baseline_mean)
            for level_id in level_means
            if level_id != "baseline"
        ]
        if abs_drifts:
            max_abs_drift = round(max(abs_drifts), 4)

    # Monotonicity check: does drift increase with n_facts?
    monotonic = None
    if len(drifts) == 3:
        vals = [drifts["plus_1"], drifts["plus_5"], drifts["plus_20"]]
        monotonic = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)) or all(
            vals[i] >= vals[i + 1] for i in range(len(vals) - 1)
        )

    return {
        "level_means": level_means,
        "level_details": level_details,
        "ground_truth": GROUND_TRUTH,
        "drift_from_baseline": drifts,
        "max_abs_drift": max_abs_drift,
        "jitter_baseline": 0.02,
        "exceeds_jitter_baseline": bool(
            max_abs_drift is not None and max_abs_drift > 0.02
        ),
        "drift_monotonic_with_fact_count": monotonic,
    }


if __name__ == "__main__":
    raise SystemExit(main())
