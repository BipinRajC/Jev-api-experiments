#!/usr/bin/env python3
"""Experiment 019 — Synthetic Calibration (Phase 3).

Tests whether Jev's Noul and Score outputs correspond to observed frequencies
on synthetic problems with known ground-truth probabilities.
"""

from __future__ import annotations

import os
import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Register this experiment's module for import.
sys.path.insert(0, str(REPO_ROOT / "experiments" / "019-calibration"))

from calibration_metrics import summarize_predictions  # noqa: E402

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

EXPERIMENT_ID = "019-calibration"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID

N_PER_LEVEL = 20

NOUL_QUESTION = "Will the selected ball be red?"

NOUL_QUESTIONS = {
    "is_red": {
        "type": "noul",
        "instructions": NOUL_QUESTION,
    }
}

SCORE_QUESTIONS = {
    "red_probability": {
        "type": "score",
        "instructions": "What is the probability that the selected ball is red?",
        "criteria": [
            {"score": 0, "label": "impossible (0%)"},
            {"score": 1, "label": "unlikely (25%)"},
            {"score": 2, "label": "even odds (50%)"},
            {"score": 3, "label": "likely (75%)"},
            {"score": 4, "label": "certain (100%)"},
        ],
    }
}

LEVELS = [
    {"label": "p_50", "red": 50, "blue": 50, "p": 0.5},
    {"label": "p_60", "red": 60, "blue": 40, "p": 0.6},
    {"label": "p_70", "red": 70, "blue": 30, "p": 0.7},
    {"label": "p_80", "red": 80, "blue": 20, "p": 0.8},
    {"label": "p_90", "red": 90, "blue": 10, "p": 0.9},
]


def _state(red: int, blue: int) -> str:
    return (
        f"A bag contains {red} red balls and {blue} blue balls. "
        f"One ball is selected randomly."
    )


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
                for i in range(N_PER_LEVEL):
                    state = _state(level["red"], level["blue"])

                    # Noul call
                    noul_trial = _run_noul_trial(client, level, i, state)
                    trials.append(noul_trial)
                    noul = noul_trial.get("parsed", {}).get("is_red", {}).get("noul")
                    print(f"{level['label']} noul_{i:02d} noul={noul}")
                    if noul_trial.get("error"):
                        exit_code = 1

                    # Score call
                    score_trial = _run_score_trial(client, level, i, state)
                    trials.append(score_trial)
                    sc = (
                        score_trial.get("parsed", {})
                        .get("red_probability", {})
                        .get("score")
                    )
                    print(f"{level['label']} score_{i:02d} score={sc}")
                    if score_trial.get("error"):
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
                "n_per_level": N_PER_LEVEL,
                "levels": LEVELS,
                "noul_question": NOUL_QUESTION,
                "score_question": SCORE_QUESTIONS,
            },
            "analysis": analysis,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print("--- Analysis ---")
    for key, val in analysis.items():
        if isinstance(val, dict):
            print(f"  {key}:")
            for k2, v2 in val.items():
                print(f"    {k2}: {v2}")
        else:
            print(f"  {key}: {val}")
    return exit_code


def _run_noul_trial(client: JevClient, level: dict, index: int, state: str) -> dict:
    record = _empty_trial(level["label"], "noul", index, state)
    try:
        result = client.system_one(state=state, questions=NOUL_QUESTIONS)
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

    _fill_record(record, result)
    noul_val = result.body.get("answers", {}).get("is_red", {}).get("noul")
    record["parsed"]["is_red"] = {"type": "noul", "noul": noul_val}

    # Sample actual outcome.
    record["sampled_outcome"] = 1 if random.random() < level["p"] else 0
    return record


def _run_score_trial(client: JevClient, level: dict, index: int, state: str) -> dict:
    record = _empty_trial(level["label"], "score", index, state)
    try:
        result = client.system_one(state=state, questions=SCORE_QUESTIONS)
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

    _fill_record(record, result)
    score_val = result.body.get("answers", {}).get("red_probability", {}).get("score")
    record["parsed"]["red_probability"] = {
        "type": "score",
        "score": score_val,
        "confidence": result.body.get("answers", {})
        .get("red_probability", {})
        .get("confidence"),
    }
    # Score uses same outcome as the paired Noul call (already sampled).
    record["sampled_outcome"] = 1 if random.random() < level["p"] else 0
    return record


def _empty_trial(level_label: str, qtype: str, index: int, state: str) -> dict:
    return {
        "level": level_label,
        "qtype": qtype,
        "instance_index": index,
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
        "sampled_outcome": None,
        "error": None,
    }


def _fill_record(record: dict, result) -> None:
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


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


def _analyze(trials: list[dict]) -> dict:
    # Separate Noul and Score trials.
    noul_trials = [
        t
        for t in trials
        if t.get("qtype") == "noul"
        and t.get("error") is None
        and t["parsed"].get("is_red", {}).get("noul") is not None
    ]
    score_trials = [
        t
        for t in trials
        if t.get("qtype") == "score"
        and t.get("error") is None
        and t["parsed"].get("red_probability", {}).get("score") is not None
    ]

    # By-level summaries.
    def by_level(t_list, key_fn):
        by_level_data = {}
        for t in t_list:
            level = t["level"]
            by_level_data.setdefault(level, []).append(key_fn(t))
        summaries = {}
        for level, vals in by_level_data.items():
            summaries[level] = {
                "n": len(vals),
                "mean": round(statistics.mean(vals), 4),
                "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else None,
            }
        return summaries

    noul_means = by_level(noul_trials, lambda t: t["parsed"]["is_red"]["noul"])
    score_means = by_level(
        score_trials, lambda t: t["parsed"]["red_probability"]["score"]
    )

    # Build (predicted, actual) pairs for Noul calibration.
    noul_preds: list[tuple[float, int]] = [
        (t["parsed"]["is_red"]["noul"], t["sampled_outcome"])
        for t in noul_trials
        if t["sampled_outcome"] is not None
    ]

    # Build (predicted, actual) pairs for Score calibration.
    # Map Score [0-4] to probability [0, 0.25, 0.5, 0.75, 1.0].
    SCORE_TO_PROB = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}
    score_preds: list[tuple[float, int]] = []
    for t in score_trials:
        sc = t["parsed"]["red_probability"]["score"]
        outcome = t["sampled_outcome"]
        if sc is not None and outcome is not None:
            prob = SCORE_TO_PROB.get(int(sc))
            if prob is not None:
                score_preds.append((prob, outcome))

    noul_calibration = summarize_predictions(noul_preds, "Noul")
    score_calibration = summarize_predictions(score_preds, "Score")

    # Per-level mean absolute error for Noul.
    level_errors = []
    ground_truth_map = {l["label"]: l["p"] for l in LEVELS}
    for label, vals in noul_means.items():
        gt = ground_truth_map.get(label)
        if gt is not None and vals["mean"] is not None:
            level_errors.append(
                {
                    "level": label,
                    "ground_truth": gt,
                    "mean_noul": vals["mean"],
                    "abs_error": round(abs(vals["mean"] - gt), 4),
                }
            )
    level_mean_abs_error = (
        statistics.mean(e["abs_error"] for e in level_errors) if level_errors else None
    )

    # Overall global mean abs error (per-instance).
    noul_global_mae = (
        statistics.mean(abs(p - a) for p, a in noul_preds) if noul_preds else None
    )

    # Correlation between ground truth and per-level Noul means.
    noul_gt_pairs = [
        (ground_truth_map.get(e["level"]), e["mean_noul"])
        for e in level_errors
        if e["ground_truth"] is not None
    ]
    corr = None
    if len(noul_gt_pairs) > 1:
        xs = [float(p[0]) for p in noul_gt_pairs if p[0] is not None]
        ys = [float(p[1]) for p in noul_gt_pairs if p[1] is not None]
        if xs and ys and len(xs) > 1:
            corr = statistics.correlation(xs, ys)

    # Conservative bias: mean (ground_truth - noul).
    bias_vals = [gt - nm for gt, nm in noul_gt_pairs]
    mean_bias = statistics.mean(bias_vals) if bias_vals else None

    return {
        "noul_by_level": noul_means,
        "score_by_level": score_means,
        "noul_calibration": noul_calibration,
        "score_calibration": score_calibration,
        "noul_level_abs_errors": level_errors,
        "noul_level_mean_abs_error": level_mean_abs_error,
        "noul_global_mae": round(noul_global_mae, 4) if noul_global_mae else None,
        "noul_corr_with_ground_truth": round(corr, 4) if corr else None,
        "noul_mean_bias_gt_minus_noul": round(mean_bias, 4) if mean_bias else None,
        "total_noul_calls": len(noul_trials),
        "total_score_calls": len(score_trials),
    }


if __name__ == "__main__":
    raise SystemExit(main())
