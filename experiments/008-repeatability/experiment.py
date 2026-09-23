#!/usr/bin/env python3
"""Experiment 008 — Repeatability.

Measures whether Jev produces deterministic outputs when the exact same
request is repeated many times (n=20 each for Noul and Score).
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

EXPERIMENT_ID = "008-repeatability"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
REPEATS = 20

STATE = (
    "A biased coin lands heads 50% of the time and tails 50% of the time. "
    "The coin is flipped once."
)

NOUL_QUESTIONS = {
    "heads_noul": {
        "type": "noul",
        "instructions": "Will the next flip land heads?",
    }
}

SCORE_QUESTIONS = {
    "coin_score": {
        "type": "score",
        "instructions": "How likely is it that the coin lands heads?",
        "criteria": [
            {"score": 0, "label": "impossible"},
            {"score": 1, "label": "unlikely"},
            {"score": 2, "label": "even odds"},
            {"score": 3, "label": "likely"},
            {"score": 4, "label": "certain"},
        ],
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
            for i in range(1, REPEATS + 1):
                # Interleave Noul and Score to avoid serial bias.
                noul_trial = _run_trial(client, i, "noul", NOUL_QUESTIONS)
                trials.append(noul_trial)
                print(
                    f"r{i:02d} noul={noul_trial.get('parsed', {}).get('heads_noul', {}).get('noul')} "
                    f"lat={noul_trial.get('latency_ms'):.0f} in={noul_trial.get('input_tokens')}"
                )
                if noul_trial.get("error"):
                    exit_code = 1

                score_trial = _run_trial(client, i, "score", SCORE_QUESTIONS)
                trials.append(score_trial)
                score = score_trial.get("parsed", {}).get("coin_score", {})
                print(
                    f"r{i:02d} score={score.get('score')} conf={score.get('confidence')} "
                    f"lat={score_trial.get('latency_ms'):.0f} in={score_trial.get('input_tokens')}"
                )
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
                "repeats": REPEATS,
                "state": STATE,
                "noul_questions": NOUL_QUESTIONS,
                "score_questions": SCORE_QUESTIONS,
                "ordering": "interleaved noul/score per repeat",
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
    repeat: int,
    qtype: str,
    questions: dict[str, dict],
) -> dict:
    record = {
        "case_id": f"repeat_{repeat}",
        "repeat": repeat,
        "qtype": qtype,
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

    parsed: dict[str, dict] = {}
    for qid, qdata in questions.items():
        answer_data = result.body.get("answers", {}).get(qid, {})
        answer_type = answer_data.get("type", "unknown")
        parsed[qid] = {"type": answer_type}
        if answer_type == "noul":
            parsed[qid]["noul"] = answer_data.get("noul")
        elif answer_type == "score":
            parsed[qid]["score"] = answer_data.get("score")
            parsed[qid]["probabilities"] = answer_data.get("probabilities")
            parsed[qid]["confidence"] = answer_data.get("confidence")
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


def _analyze(trials: list[dict]) -> dict:
    nouls = [
        t["parsed"]["heads_noul"]["noul"]
        for t in trials
        if t.get("qtype") == "noul"
        and t["parsed"].get("heads_noul", {}).get("type") == "noul"
        and t["parsed"]["heads_noul"].get("noul") is not None
    ]
    scores = [
        t["parsed"]["coin_score"]
        for t in trials
        if t.get("qtype") == "score"
        and t["parsed"].get("coin_score", {}).get("type") == "score"
    ]
    noul_lat = [
        t["latency_ms"]
        for t in trials
        if t.get("qtype") == "noul" and t.get("latency_ms") is not None
    ]
    score_lat = [
        t["latency_ms"]
        for t in trials
        if t.get("qtype") == "score" and t.get("latency_ms") is not None
    ]
    noul_tok = [
        t["input_tokens"]
        for t in trials
        if t.get("qtype") == "noul" and t.get("input_tokens") is not None
    ]

    def summarize(vals: list[float]) -> dict | None:
        if not vals:
            return None
        return {
            "n": len(vals),
            "min": round(min(vals), 6),
            "max": round(max(vals), 6),
            "mean": round(statistics.mean(vals), 6),
            "median": round(statistics.median(vals), 6),
            "stdev": round(statistics.stdev(vals), 6) if len(vals) > 1 else None,
            "range": round(max(vals) - min(vals), 6),
            "unique_count": len(set(vals)),
            "unique_values": sorted(set(vals)),
            "frequency": {str(round(v, 6)): vals.count(v) for v in sorted(set(vals))},
        }

    score_vals = [s.get("score") for s in scores if s.get("score") is not None]
    score_confs = [
        s.get("confidence") for s in scores if s.get("confidence") is not None
    ]

    return {
        "noul": summarize(nouls),
        "score": summarize(score_vals),
        "score_confidence": summarize(score_confs),
        "noul_latency_ms": summarize(noul_lat),
        "score_latency_ms": summarize(score_lat),
        "noul_input_tokens": summarize(noul_tok),
        "noul_deterministic": len(set(nouls)) == 1,
        "score_deterministic": len(set(score_vals)) == 1,
        "score_confidence_deterministic": len(set(score_confs)) == 1,
    }


if __name__ == "__main__":
    raise SystemExit(main())
