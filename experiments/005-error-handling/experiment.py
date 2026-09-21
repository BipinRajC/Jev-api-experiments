#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.jev_client import DEFAULT_BASE_URL, DEFAULT_MODEL, SYSTEMONE_PATH  # noqa: E402
from src.utils import load_env, next_run_path, sanitize_headers, utc_now_iso, write_json  # noqa: E402

EXPERIMENT_ID = "005-error-handling"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
VALID_BODY = {
    "state": "The sky is blue.",
    "model": DEFAULT_MODEL,
    "questions": {
        "is_sky_blue": {
            "type": "noul",
            "instructions": "Is the sky described as blue?",
        }
    },
}


def main() -> int:
    load_env()
    real_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not real_key:
        print("CONFIG ERROR: Missing TYPESAFE_API_KEY", file=sys.stderr)
        return 2
    base_url = (os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}{SYSTEMONE_PATH}"
    started_at = utc_now_iso()
    cases = [
        {
            "case_id": "invalid_bearer_token",
            "expected_status": 401,
            "auth": "Bearer not-a-real-typesafe-key",
            "payload": VALID_BODY,
        },
        {
            "case_id": "missing_authorization_header",
            "expected_status": 401,
            "auth": None,
            "payload": VALID_BODY,
        },
        {
            "case_id": "missing_questions",
            "expected_status": 422,
            "auth": f"Bearer {real_key}",
            "payload": {"state": "The sky is blue.", "model": DEFAULT_MODEL},
        },
        {
            "case_id": "unknown_model",
            "expected_status": None,
            "auth": f"Bearer {real_key}",
            "payload": {
                "state": "The sky is blue.",
                "model": "jev-does-not-exist-0.0.0",
                "questions": VALID_BODY["questions"],
            },
        },
    ]
    trials = []
    with httpx.Client(timeout=30.0) as client:
        for case in cases:
            trial = _call(client, url, case)
            trials.append(trial)
            print(
                f"{case['case_id']} HTTP {trial['http_status']} "
                f"expected={case['expected_status']} body={trial['raw_response']}"
            )

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
                "endpoint": SYSTEMONE_PATH,
                "method": "POST",
            },
            "design": {
                "note": "Authorization values are never written. Real key used only for valid-auth negative cases.",
                "cases": [
                    {
                        "case_id": c["case_id"],
                        "expected_status": c["expected_status"],
                        "sends_authorization": c["auth"] is not None,
                        "payload_keys": sorted(c["payload"].keys()),
                        "model": c["payload"].get("model"),
                    }
                    for c in cases
                ],
            },
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return 0


def _call(client: httpx.Client, url: str, case: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if case["auth"] is not None:
        headers["Authorization"] = case["auth"]
    started = time.perf_counter()
    response = client.post(url, json=case["payload"], headers=headers)
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        body = response.json()
    except ValueError:
        body = {"_text": response.text[:2000]}
    request_id = response.headers.get("x-typesafe-request-id")
    return {
        "case_id": case["case_id"],
        "expected_status": case["expected_status"],
        "http_status": response.status_code,
        "request_id": request_id,
        "latency_ms": latency_ms,
        "response_headers": sanitize_headers(dict(response.headers)),
        "raw_response": body,
        "matched_expected": (
            case["expected_status"] is None
            or response.status_code == case["expected_status"]
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
