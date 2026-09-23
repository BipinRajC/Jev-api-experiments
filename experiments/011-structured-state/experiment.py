#!/usr/bin/env python3
"""Experiment 011 — Structured vs Unstructured State.

Tests whether representing identical facts as prose, JSON, or compact
structured text changes Jev's decision behavior. The underlying facts are
identical; only the representation format varies.
"""

from __future__ import annotations

import os
import statistics
import sys
from pathlib import Path
from typing import Any

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

EXPERIMENT_ID = "011-structured-state"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 3

GROUND_TRUTH_P_RED = 0.70

# The three representations of the same facts (7 red, 3 blue).
FORMATS = [
    {
        "id": "prose",
        "description": "Format A — prose sentence",
        "state": "Arun has 7 red balls and 3 blue balls.",
    },
    {
        "id": "json",
        "description": "Format B — JSON object",
        "state": {"red": 7, "blue": 3},
    },
    {
        "id": "compact",
        "description": "Format C — compact structured text",
        "state": "red=7, blue=3",
    },
]

QUESTIONS = {
    "is_red": {
        "type": "noul",
        "instructions": "Will a randomly selected ball be red?",
    },
    "ball_color": {
        "type": "choice",
        "instructions": "What color will a randomly selected ball be?",
        "criteria": {
            "red": "The ball is red.",
            "blue": "The ball is blue.",
        },
    },
    "red_likelihood": {
        "type": "score",
        "instructions": "How likely is it that a randomly selected ball is red?",
        "criteria": [
            {"score": 0, "label": "impossible"},
            {"score": 1, "label": "unlikely"},
            {"score": 2, "label": "even odds"},
            {"score": 3, "label": "likely"},
            {"score": 4, "label": "certain"},
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
            for fmt in FORMATS:
                for repeat in range(1, REPEATS + 1):
                    trial = _run_trial(client, fmt, repeat)
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
                "repeats_per_format": REPEATS,
                "formats": [
                    {
                        "id": f["id"],
                        "description": f["description"],
                        "state": f["state"],
                    }
                    for f in FORMATS
                ],
                "questions": QUESTIONS,
                "ground_truth_p_red": GROUND_TRUTH_P_RED,
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


def _run_trial(client: JevClient, fmt: dict, repeat: int) -> dict:
    record = {
        "format": fmt["id"],
        "format_description": fmt["description"],
        "state": fmt["state"],
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
        result = client.system_one(state=fmt["state"], questions=QUESTIONS)
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

    noul = answers.get("is_red", {})
    parsed["is_red"] = {"type": noul.get("type"), "noul": noul.get("noul")}

    choice = answers.get("ball_color", {})
    parsed["ball_color"] = {
        "type": choice.get("type"),
        "choice": choice.get("choice"),
        "probabilities": choice.get("probabilities"),
        "confidence": choice.get("confidence"),
    }

    score = answers.get("red_likelihood", {})
    parsed["red_likelihood"] = {
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
    noul = p.get("is_red", {}).get("noul")
    choice = p.get("ball_color", {})
    score = p.get("red_likelihood", {})
    print(
        f"{trial['format']} r{trial['repeat']} noul={noul} "
        f"choice={choice.get('choice')}(conf {choice.get('confidence')}) "
        f"score={score.get('score')}(conf {score.get('confidence')}) "
        f"in={trial.get('input_tokens')} lat={trial.get('latency_ms'):.0f}"
    )


def _analyze(trials: list[dict]) -> dict:
    # Group by format.
    by_format: dict[str, list[dict]] = {}
    for t in trials:
        by_format.setdefault(t["format"], []).append(t)

    noul_means = {}
    noul_all_values = {}
    score_means = {}
    score_all_values = {}
    choice_labels = {}
    confidence_means = {}
    input_tokens = {}
    latency_means = {}

    for fid, ts in by_format.items():
        nouls = [
            t["parsed"]["is_red"].get("noul")
            for t in ts
            if t["parsed"]["is_red"].get("noul") is not None
        ]
        scores = [
            t["parsed"]["red_likelihood"].get("score")
            for t in ts
            if t["parsed"]["red_likelihood"].get("score") is not None
        ]
        choices = [
            t["parsed"]["ball_color"].get("choice")
            for t in ts
            if t["parsed"]["ball_color"].get("choice")
        ]
        confs = [
            t["parsed"]["red_likelihood"].get("confidence")
            for t in ts
            if t["parsed"]["red_likelihood"].get("confidence") is not None
        ]
        toks = [t["input_tokens"] for t in ts if t.get("input_tokens") is not None]
        lats = [t["latency_ms"] for t in ts if t.get("latency_ms") is not None]

        noul_means[fid] = round(statistics.mean(nouls), 4) if nouls else None
        noul_all_values[fid] = nouls
        score_means[fid] = round(statistics.mean(scores), 4) if scores else None
        score_all_values[fid] = scores
        choice_labels[fid] = choices
        confidence_means[fid] = round(statistics.mean(confs), 4) if confs else None
        input_tokens[fid] = toks
        latency_means[fid] = round(statistics.mean(lats), 1) if lats else None

    # Range across format means for Noul.
    noul_mean_vals = [v for v in noul_means.values() if v is not None]
    noul_range = (
        round(max(noul_mean_vals) - min(noul_mean_vals), 4)
        if len(noul_mean_vals) > 1
        else None
    )

    # Range across format means for Score.
    score_mean_vals = [v for v in score_means.values() if v is not None]
    score_range = (
        round(max(score_mean_vals) - min(score_mean_vals), 4)
        if len(score_mean_vals) > 1
        else None
    )

    # Token comparison: prose vs json vs compact.
    prose_tokens = input_tokens.get("prose", [])
    json_tokens = input_tokens.get("json", [])
    compact_tokens = input_tokens.get("compact", [])

    json_less_than_prose = None
    if prose_tokens and json_tokens:
        json_less_than_prose = statistics.mean(json_tokens) < statistics.mean(
            prose_tokens
        )
    compact_less_than_prose = None
    if prose_tokens and compact_tokens:
        compact_less_than_prose = statistics.mean(compact_tokens) < statistics.mean(
            prose_tokens
        )

    return {
        "noul_means": noul_means,
        "noul_all_values": noul_all_values,
        "noul_range_across_formats": noul_range,
        "score_means": score_means,
        "score_all_values": score_all_values,
        "score_range_across_formats": score_range,
        "choice_labels": choice_labels,
        "confidence_means": confidence_means,
        "input_tokens_by_format": input_tokens,
        "latency_means_ms": latency_means,
        "jitter_baseline": 0.02,
        "noul_exceeds_jitter_baseline": bool(
            noul_range is not None and noul_range > 0.02
        ),
        "score_exceeds_jitter_baseline": bool(
            score_range is not None and score_range > 0.02
        ),
        "json_tokens_less_than_prose": json_less_than_prose,
        "compact_tokens_less_than_prose": compact_less_than_prose,
        "ground_truth_p_red": GROUND_TRUTH_P_RED,
    }


if __name__ == "__main__":
    raise SystemExit(main())
