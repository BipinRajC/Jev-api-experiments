#!/usr/bin/env python3
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

EXPERIMENT_ID = "001-api-sanity"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID

STATE = "The sky is blue."
QUESTIONS = {
    "is_sky_blue": {
        "type": "noul",
        "instructions": "Is the sky described as blue?",
    }
}


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    request_payload = {"state": STATE, "model": model, "questions": QUESTIONS}
    started_at = utc_now_iso()
    error_record: dict | None = None
    result = None

    try:
        with JevClient(model=model, base_url=base_url) as client:
            result = client.system_one(state=STATE, questions=QUESTIONS)
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    except JevAuthError as exc:
        error_record = _error("auth", exc)
        print(f"AUTH ERROR HTTP {exc.status_code}: {exc}", file=sys.stderr)
    except JevValidationError as exc:
        error_record = _error("validation", exc)
        print(f"VALIDATION ERROR HTTP {exc.status_code}: {exc}", file=sys.stderr)
    except JevRateLimitError as exc:
        error_record = _error("rate_limit", exc)
        print(f"RATE LIMIT HTTP {exc.status_code}: {exc}", file=sys.stderr)
    except JevTimeoutError as exc:
        error_record = {"kind": "timeout", "message": str(exc)}
        print(f"TIMEOUT: {exc}", file=sys.stderr)
    except JevMalformedResponseError as exc:
        error_record = {"kind": "malformed_response", "message": str(exc)}
        print(f"MALFORMED RESPONSE: {exc}", file=sys.stderr)
    except JevAPIError as exc:
        error_record = _error("api", exc)
        print(f"API ERROR HTTP {exc.status_code}: {exc}", file=sys.stderr)

    path = next_run_path(RESULTS_DIR)
    usage = result.usage if result else {}
    input_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
    record = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": path.stem,
        "timestamp": started_at,
        "model_requested": model,
        "model_returned": result.model if result else None,
        "api": {
            "provider": "typesafe_direct",
            "base_url": base_url,
            "endpoint": "/v1/systemone",
            "method": "POST",
        },
        "http_status": result.status_code
        if result
        else error_record and error_record.get("status_code"),
        "request_id": result.request_id if result else None,
        "latency_ms": result.latency_ms if result else None,
        "input_tokens": input_tokens,
        "output_tokens": usage.get("output_tokens")
        if isinstance(usage, dict)
        else None,
        "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
        "pricing_note": "Official docs (2026-09-21): $0.042 per million input tokens; output tokens free. UNVERIFIED experimentally until billed usage is compared.",
        "request": request_payload,
        "response_headers": sanitize_headers(result.headers) if result else {},
        "raw_response": result.body if result else None,
        "error": error_record,
    }
    write_json(path, record)
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    if result:
        answer = result.body.get("answers", {}).get("is_sky_blue")
        print(f"HTTP {result.status_code} model={result.model} noul={answer}")
        print(f"latency_ms={result.latency_ms:.1f} usage={result.usage}")
        return 0
    return 1


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


if __name__ == "__main__":
    raise SystemExit(main())
