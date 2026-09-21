from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.schemas import SystemOneRequest

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-1.13.0"
SYSTEMONE_PATH = "/v1/systemone"


class JevError(Exception):
    pass


class JevConfigError(JevError):
    pass


class JevAPIError(JevError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.request_id = request_id


class JevAuthError(JevAPIError):
    pass


class JevValidationError(JevAPIError):
    pass


class JevRateLimitError(JevAPIError):
    pass


class JevTimeoutError(JevError):
    pass


class JevMalformedResponseError(JevError):
    pass


@dataclass
class SystemOneResult:
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]
    latency_ms: float
    request_id: str | None = None
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


class JevClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
        if not key:
            raise JevConfigError(
                "Missing TYPESAFE_API_KEY. Copy .env.example to .env and set the key locally."
            )
        self.api_key = key
        self.base_url = (
            base_url or os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def system_one(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
        *,
        model: str | None = None,
    ) -> SystemOneResult:
        payload = SystemOneRequest(
            state=state,
            model=model or self.model,
            questions=questions,
        ).to_payload()
        url = f"{self.base_url}{SYSTEMONE_PATH}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise JevTimeoutError(
                f"Request to {url} timed out after {self.timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise JevAPIError(f"Network error calling {url}: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000
        request_id = response.headers.get("x-request-id") or response.headers.get(
            "request-id"
        )
        body = self._parse_json(response)
        if response.status_code == 401:
            raise JevAuthError(
                "Authentication failed. Check TYPESAFE_API_KEY.",
                status_code=401,
                body=body,
                request_id=request_id,
            )
        if response.status_code == 422:
            raise JevValidationError(
                f"Request failed validation: {body}",
                status_code=422,
                body=body,
                request_id=request_id,
            )
        if response.status_code == 429:
            raise JevRateLimitError(
                f"Rate limited: {body}",
                status_code=429,
                body=body,
                request_id=request_id,
            )
        if response.status_code >= 400:
            raise JevAPIError(
                f"TypeSafe API error HTTP {response.status_code}: {body}",
                status_code=response.status_code,
                body=body,
                request_id=request_id,
            )
        if not isinstance(body, dict):
            raise JevMalformedResponseError(
                f"Expected JSON object, got {type(body).__name__}"
            )
        return SystemOneResult(
            status_code=response.status_code,
            body=body,
            headers=dict(response.headers),
            latency_ms=latency_ms,
            request_id=request_id,
            model=body.get("model"),
            usage=body.get("usage") or {},
            raw_text=response.text,
        )

    def _parse_json(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise JevMalformedResponseError(
                f"Response was not valid JSON (HTTP {response.status_code}): {response.text[:500]}"
            ) from exc
