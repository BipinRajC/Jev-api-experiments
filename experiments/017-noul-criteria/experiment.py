#!/usr/bin/env python3
"""Experiment 017 — Noul Criteria Behavior (Add-on F).

Compares Noul output with and without explicit criteria.{true,false} to
determine whether the optional criteria fields materially affect the value.
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

EXPERIMENT_ID = "017-noul-criteria"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

STATE = "A bag contains 55 red balls and 45 blue balls. One ball is selected randomly."

QUESTION_ID = "is_red"

FORMULATIONS = [
    {
        "id": "instruction_only",
        "description": "instruction only, no criteria",
        "question": {
            "type": "noul",
            "instructions": "Is the ball red?",
        },
    },
    {
        "id": "criteria_plain",
        "description": "plain true/false criteria",
        "question": {
            "type": "noul",
            "instructions": "Is the ball red?",
            "criteria": {
                "true": "The ball is red.",
                "false": "The ball is not red.",
            },
        },
    },
    {
        "id": "criteria_reworded",
        "description": "reworded criteria",
        "question": {
            "type": "noul",
            "instructions": "Decide whether the ball is red.",
            "criteria": {
                "true": "Return a high probability if the ball is red.",
                "false": "Return a low probability if the ball is not red.",
            },
        },
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
            for formulation in FORMULATIONS:
                questions = {QUESTION_ID: formulation["question"]}
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, formulation, repeat, questions)
                    trials.append(trial)
                    noul = trial.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
                    print(
                        f"{formulation['id']} r{repeat} noul={noul} "
                        f"lat={trial.get('latency_ms'):.0f} in={trial.get('input_tokens')}"
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
                "repeats_per_formulation": REPEATS,
                "state": STATE,
                "question_id": QUESTION_ID,
                "formulations": [
                    {
                        "id": f["id"],
                        "description": f["description"],
                        "question": f["question"],
                    }
                    for f in FORMULATIONS
                ],
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
    formulation: dict,
    repeat: int,
    questions: dict[str, dict],
) -> dict:
    record = {
        "formulation": formulation["id"],
        "formulation_description": formulation["description"],
        "state": STATE,
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
    by_formulation: dict[str, list[float]] = {}
    for t in trials:
        noul = t.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
        if noul is not None:
            by_formulation.setdefault(t["formulation"], []).append(noul)

    means = {}
    details = {}
    for fid in ["instruction_only", "criteria_plain", "criteria_reworded"]:
        vals = by_formulation.get(fid, [])
        if vals:
            means[fid] = round(statistics.mean(vals), 4)
            details[fid] = {
                "values": vals,
                "mean": round(statistics.mean(vals), 4),
                "range": round(max(vals) - min(vals), 4),
            }
        else:
            details[fid] = {"values": [], "mean": None, "range": None}

    mean_vals = [m for m in means.values() if m is not None]
    range_across = (
        round(max(mean_vals) - min(mean_vals), 4) if len(mean_vals) > 1 else None
    )

    return {
        "means": means,
        "details": details,
        "range_across_formulations": range_across,
        "jitter_baseline": 0.02,
        "exceeds_jitter_baseline": bool(
            range_across is not None and range_across > 0.03
        ),
        "criteria_changes_output": bool(
            range_across is not None and range_across > 0.03
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
