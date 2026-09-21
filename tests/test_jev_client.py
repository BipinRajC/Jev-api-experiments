import json

import httpx
import pytest

from src.jev_client import (
    JevAPIError,
    JevAuthError,
    JevClient,
    JevConfigError,
    JevMalformedResponseError,
    JevRateLimitError,
    JevTimeoutError,
    JevValidationError,
)
from src.schemas import SystemOneRequest


def _handler(request: httpx.Request) -> httpx.Response:
    assert request.method == "POST"
    assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["content-type"] == "application/json"
    body = json.loads(request.content)
    assert body["model"] == "jev-1.13.0"
    assert body["state"] == "The sky is blue."
    assert body["questions"]["is_sky_blue"]["type"] == "noul"
    return httpx.Response(
        200,
        json={
            "model": "jev-1.13.0",
            "answers": {"is_sky_blue": {"type": "noul", "noul": 0.99}},
            "usage": {"input_tokens": 100, "output_tokens": 10},
        },
        headers={"x-request-id": "req-123"},
    )


def test_system_one_posts_authenticated_json_and_parses_noul_response():
    client = JevClient(
        api_key="test-key",
        model="jev-1.13.0",
        transport=httpx.MockTransport(_handler),
    )
    result = client.system_one(
        state="The sky is blue.",
        questions={
            "is_sky_blue": {
                "type": "noul",
                "instructions": "Is the sky described as blue?",
            }
        },
    )
    assert result.status_code == 200
    assert result.model == "jev-1.13.0"
    assert result.request_id == "req-123"
    assert result.body["answers"]["is_sky_blue"]["noul"] == 0.99
    assert result.usage["input_tokens"] == 100


def test_missing_api_key_raises_config_error():
    with pytest.raises(JevConfigError, match="TYPESAFE_API_KEY"):
        JevClient(api_key="")


def test_401_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = JevClient(api_key="bad", transport=httpx.MockTransport(handler))
    with pytest.raises(JevAuthError) as exc:
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )
    assert exc.value.status_code == 401


def test_422_raises_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": "missing questions"})

    client = JevClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(JevValidationError) as exc:
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )
    assert exc.value.status_code == 422


def test_429_raises_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": "rate limited"}, headers={"retry-after": "1"}
        )

    client = JevClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(JevRateLimitError) as exc:
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )
    assert exc.value.status_code == 429


def test_529_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"error": "overloaded"})

    client = JevClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(JevAPIError) as exc:
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )
    assert exc.value.status_code == 529


def test_non_json_200_raises_malformed_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = JevClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(JevMalformedResponseError):
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )


def test_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = JevClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(JevTimeoutError):
        client.system_one(
            state="x", questions={"q": {"type": "noul", "instructions": "y"}}
        )


def test_request_schema_requires_state_model_and_questions():
    req = SystemOneRequest(
        state="The sky is blue.",
        model="jev-1.13.0",
        questions={"is_sky_blue": {"type": "noul", "instructions": "Is the sky blue?"}},
    )
    payload = req.to_payload()
    assert payload["state"] == "The sky is blue."
    assert payload["model"] == "jev-1.13.0"
    assert payload["questions"]["is_sky_blue"]["type"] == "noul"
