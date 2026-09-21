from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_input_cost_usd(
    input_tokens: int | None, usd_per_million: float = 0.042
) -> float | None:
    if input_tokens is None:
        return None
    return input_tokens * usd_per_million / 1_000_000


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def next_run_path(results_dir: Path, prefix: str = "run") -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(results_dir.glob(f"{prefix}-*.json"))
    next_id = 1
    if existing:
        last = existing[-1].stem.split("-")[-1]
        if last.isdigit():
            next_id = int(last) + 1
    return results_dir / f"{prefix}-{next_id:03d}.json"


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "cookie", "x-api-key"}:
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


def require_api_key() -> str:
    load_env()
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        raise SystemExit(
            "Missing TYPESAFE_API_KEY. Copy .env.example to .env and set the key locally."
        )
    return key
