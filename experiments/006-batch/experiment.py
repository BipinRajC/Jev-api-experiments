#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.choice import extract_choice, probabilities_sum as choice_sum  # noqa: E402
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
from src.noul import extract_noul  # noqa: E402
from src.score import extract_score, probabilities_sum as score_sum  # noqa: E402
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    sanitize_headers,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "006-batch"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
STATE = "The sky is blue."
NOUL_Q = {
    "is_sky_blue": {
        "type": "noul",
        "instructions": "Is the sky described as blue?",
    }
}
CHOICE_Q = {
    "sky_color": {
        "type": "choice",
        "instructions": "What color is the sky described as?",
        "criteria": {
            "blue": "The sky is described as blue",
            "grey": "The sky is described as grey, gray, or overcast",
            "unspecified": "The sky color is not stated",
        },
    }
}
SCORE_Q = {
    "sky_blueness": {
        "type": "score",
        "instructions": "How clearly is the sky described as blue?",
        "criteria": [
            "The sky is described as grey, gray, or overcast, not blue",
            "The sky color is not stated",
            "The sky is described as blue",
        ],
    }
}
BATCH_QUESTIONS = {**NOUL_Q, **CHOICE_Q, **SCORE_Q}


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    calls: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            batch = _call(client, "batch", BATCH_QUESTIONS)
            calls.append(batch)
            print(
                f"batch HTTP {batch.get('http_status')} "
                f"tokens={batch.get('input_tokens')}/{batch.get('output_tokens')} "
                f"latency_ms={batch.get('latency_ms')}"
            )
            if batch.get("error"):
                exit_code = 1
            for name, questions in (
                ("separate_noul", NOUL_Q),
                ("separate_choice", CHOICE_Q),
                ("separate_score", SCORE_Q),
            ):
                call = _call(client, name, questions)
                calls.append(call)
                print(
                    f"{name} HTTP {call.get('http_status')} "
                    f"tokens={call.get('input_tokens')}/{call.get('output_tokens')} "
                    f"latency_ms={call.get('latency_ms')}"
                )
                if call.get("error"):
                    exit_code = 1
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    comparison = _compare(calls)
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
                "state": STATE,
                "batch_question_ids": list(BATCH_QUESTIONS),
                "separate_calls": [
                    "separate_noul",
                    "separate_choice",
                    "separate_score",
                ],
                "held_constant": ["state", "model", "question wording"],
                "variable": "one request with three questions vs three single-question requests",
            },
            "comparison": comparison,
            "calls": calls,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print("comparison:", comparison)
    return exit_code


def _call(client: JevClient, call_id: str, questions: dict) -> dict:
    record = {
        "call_id": call_id,
        "question_ids": list(questions),
        "timestamp": utc_now_iso(),
        "http_status": None,
        "request_id": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "model_returned": None,
        "parsed": {},
        "response_headers": {},
        "raw_response": None,
        "error": None,
    }
    try:
        result = client.system_one(state=STATE, questions=questions)
    except (
        JevAuthError,
        JevValidationError,
        JevRateLimitError,
        JevAPIError,
    ) as exc:
        record["error"] = {
            "kind": type(exc).__name__,
            "message": str(exc),
            "status_code": getattr(exc, "status_code", None),
            "body": getattr(exc, "body", None),
        }
        return record
    except JevTimeoutError as exc:
        record["error"] = {"kind": "timeout", "message": str(exc)}
        return record
    except JevMalformedResponseError as exc:
        record["error"] = {"kind": "malformed_response", "message": str(exc)}
        return record

    usage = result.usage if isinstance(result.usage, dict) else {}
    record.update(
        {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": result.latency_ms,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(usage.get("input_tokens")),
            "model_returned": result.model,
            "response_headers": sanitize_headers(result.headers),
            "raw_response": result.body,
        }
    )
    try:
        record["parsed"] = _parse(result.body, questions)
    except ValueError as exc:
        record["error"] = {"kind": "parse", "message": str(exc)}
    return record


def _parse(body: dict, questions: dict) -> dict:
    parsed: dict = {}
    if "is_sky_blue" in questions:
        parsed["is_sky_blue"] = {"noul": extract_noul(body, "is_sky_blue")}
    if "sky_color" in questions:
        choice = extract_choice(body, "sky_color")
        parsed["sky_color"] = {
            **choice,
            "probability_sum": choice_sum(choice["probabilities"]),
        }
    if "sky_blueness" in questions:
        score = extract_score(body, "sky_blueness")
        parsed["sky_blueness"] = {
            "score": score["score"],
            "confidence": score["confidence"],
            "probabilities": score["probabilities"],
            "probability_sum": score_sum(score["probabilities"]),
        }
    return parsed


def _compare(calls: list[dict]) -> dict:
    by_id = {c["call_id"]: c for c in calls}
    batch = by_id.get("batch", {})
    separate = [
        by_id.get("separate_noul"),
        by_id.get("separate_choice"),
        by_id.get("separate_score"),
    ]
    separate = [c for c in separate if c]
    batch_parsed = batch.get("parsed") or {}
    answers_match = {}
    for qid in ("is_sky_blue", "sky_color", "sky_blueness"):
        sep_call = next((c for c in separate if qid in (c.get("parsed") or {})), None)
        if not sep_call:
            continue
        answers_match[qid] = {
            "batch": batch_parsed.get(qid),
            "separate": (sep_call.get("parsed") or {}).get(qid),
            "equal": batch_parsed.get(qid) == (sep_call.get("parsed") or {}).get(qid),
        }
    sep_in = sum(c.get("input_tokens") or 0 for c in separate)
    sep_out = sum(c.get("output_tokens") or 0 for c in separate)
    sep_lat = sum(c.get("latency_ms") or 0 for c in separate)
    batch_in = batch.get("input_tokens")
    batch_out = batch.get("output_tokens")
    batch_lat = batch.get("latency_ms")
    return {
        "answers_match": answers_match,
        "batch_input_tokens": batch_in,
        "separate_input_tokens_sum": sep_in,
        "input_token_ratio_separate_over_batch": (sep_in / batch_in)
        if batch_in
        else None,
        "batch_output_tokens": batch_out,
        "separate_output_tokens_sum": sep_out,
        "batch_latency_ms": batch_lat,
        "separate_latency_ms_sum": sep_lat,
        "latency_ratio_separate_over_batch": (sep_lat / batch_lat)
        if batch_lat
        else None,
        "batch_estimated_cost_usd": batch.get("estimated_cost_usd"),
        "separate_estimated_cost_usd_sum": sum(
            c.get("estimated_cost_usd") or 0 for c in separate
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
