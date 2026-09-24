#!/usr/bin/env python3
"""Experiment 015 — Alias Resolution (Add-on A).

Determines what model version the `jev-latest` alias resolves to and whether
it matches the pinned `jev-1.13.0` output. Does not mix aliases with the
pinned experiments.
"""

from __future__ import annotations

import os
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

EXPERIMENT_ID = "015-alias-resolution"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID

STATE = "A bag contains 70 red balls and 30 blue balls. One ball is selected randomly."

QUESTION_ID = "is_red"
QUESTIONS = {
    QUESTION_ID: {
        "type": "noul",
        "instructions": "Will the selected ball be red?",
    }
}

MODEL_ALIAS = "jev-latest"
MODEL_PINNED = DEFAULT_MODEL  # jev-1.13.0


def main() -> int:
    load_env()
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        # The client pins a default model; override per-call via system_one(model=...).
        with JevClient(base_url=base_url) as client:
            for label, model in [("alias", MODEL_ALIAS), ("pinned", MODEL_PINNED)]:
                trial = _run_trial(client, label, model)
                trials.append(trial)
                noul = trial.get("parsed", {}).get(QUESTION_ID, {}).get("noul")
                print(
                    f"{label} requested={model} returned={trial.get('model_returned')} "
                    f"noul={noul} status={trial.get('http_status')}"
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
            "api": {
                "provider": "typesafe_direct",
                "base_url": base_url,
                "endpoint": "/v1/systemone",
                "method": "POST",
            },
            "design": {
                "state": STATE,
                "questions": QUESTIONS,
                "model_alias": MODEL_ALIAS,
                "model_pinned": MODEL_PINNED,
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


def _run_trial(client: JevClient, label: str, model: str) -> dict:
    record = {
        "label": label,
        "model_requested": model,
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
        result = client.system_one(state=STATE, questions=QUESTIONS, model=model)
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
    alias = next((t for t in trials if t["label"] == "alias"), None)
    pinned = next((t for t in trials if t["label"] == "pinned"), None)

    alias_model = alias.get("model_returned") if alias else None
    pinned_model = pinned.get("model_returned") if pinned else None
    alias_noul = (
        alias.get("parsed", {}).get(QUESTION_ID, {}).get("noul") if alias else None
    )
    pinned_noul = (
        pinned.get("parsed", {}).get(QUESTION_ID, {}).get("noul") if pinned else None
    )

    alias_resolves_to_versioned = bool(
        alias_model
        and alias_model.startswith("jev-")
        and not alias_model.startswith("jev-latest")
    )
    noul_diff = None
    if alias_noul is not None and pinned_noul is not None:
        noul_diff = round(abs(alias_noul - pinned_noul), 4)

    return {
        "alias_requested": MODEL_ALIAS,
        "alias_model_returned": alias_model,
        "pinned_model_returned": pinned_model,
        "alias_resolves_to_versioned": alias_resolves_to_versioned,
        "alias_noul": alias_noul,
        "pinned_noul": pinned_noul,
        "noul_diff": noul_diff,
        "within_jitter_baseline": bool(noul_diff is not None and noul_diff <= 0.02),
    }


if __name__ == "__main__":
    raise SystemExit(main())
