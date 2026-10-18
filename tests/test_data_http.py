from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.data.http import BlockedError, CachedFetcher, FetchError


def make_fetcher(tmp_path: Path, handler, **kwargs) -> tuple[CachedFetcher, list[float]]:
    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = CachedFetcher(
        tmp_path, client=client, sleep=sleeps.append, clock=lambda: 0.0, **kwargs
    )
    return fetcher, sleeps


def test_get_caches_body_and_metadata(tmp_path: Path) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"hello")

    fetcher, _ = make_fetcher(tmp_path, handler)
    first = fetcher.get("https://x.test/a", cache_key="src/a.txt")
    second = fetcher.get("https://x.test/a", cache_key="src/a.txt")

    assert (first.body, first.from_cache) == (b"hello", False)
    assert (second.body, second.from_cache) == (b"hello", True)
    assert len(calls) == 1
    meta = json.loads((tmp_path / "src/a.txt.meta.json").read_text())
    assert meta["url"] == "https://x.test/a" and meta["size"] == 5 and len(meta["sha256"]) == 64


def test_refresh_archives_changed_content_and_skips_unchanged(tmp_path: Path) -> None:
    bodies = iter([b"v1", b"v1", b"v2"])
    fetcher, _ = make_fetcher(tmp_path, lambda r: httpx.Response(200, content=next(bodies)))

    fetcher.get("https://x.test/a", cache_key="a.csv")
    unchanged = fetcher.get("https://x.test/a", cache_key="a.csv", refresh=True)
    changed = fetcher.get("https://x.test/a", cache_key="a.csv", refresh=True)

    assert unchanged.changed is False and changed.changed is True
    assert (tmp_path / "a.csv").read_bytes() == b"v2"
    archived = [p for p in tmp_path.iterdir() if p.name.startswith("a.csv@") and not p.name.endswith(".meta.json")]
    assert len(archived) == 1 and archived[0].read_bytes() == b"v1"


@pytest.mark.parametrize("status", [403, 429])
def test_blocked_status_stops_immediately_without_retry(tmp_path: Path, status: int) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status)

    fetcher, _ = make_fetcher(tmp_path, handler)
    with pytest.raises(BlockedError):
        fetcher.get("https://x.test/a", cache_key="a")
    assert len(calls) == 1
    assert not (tmp_path / "a").exists()


def test_404_raises_fetch_error_without_retry_or_cache(tmp_path: Path) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    fetcher, _ = make_fetcher(tmp_path, handler)
    with pytest.raises(FetchError) as info:
        fetcher.get("https://x.test/a", cache_key="a")
    assert info.value.status_code == 404 and not isinstance(info.value, BlockedError)
    assert len(calls) == 1 and not (tmp_path / "a").exists()


def test_retries_5xx_with_backoff_then_succeeds(tmp_path: Path) -> None:
    statuses = iter([502, 503, 200])
    fetcher, sleeps = make_fetcher(
        tmp_path, lambda r: httpx.Response(next(statuses), content=b"ok"), min_interval_s=0.0
    )
    result = fetcher.get("https://x.test/a", cache_key="a")
    assert result.body == b"ok"
    assert [s for s in sleeps if s >= 1.0] == [1.0, 2.0]


def test_gives_up_after_max_retries(tmp_path: Path) -> None:
    fetcher, _ = make_fetcher(tmp_path, lambda r: httpx.Response(502), max_retries=2)
    with pytest.raises(FetchError):
        fetcher.get("https://x.test/a", cache_key="a")
    assert fetcher.network_calls == 3


def test_throttle_waits_min_interval_between_requests(tmp_path: Path) -> None:
    fetcher, sleeps = make_fetcher(
        tmp_path, lambda r: httpx.Response(200, content=b"x"), min_interval_s=1.5
    )
    fetcher.get("https://x.test/a", cache_key="a")
    fetcher.get("https://x.test/b", cache_key="b")
    assert sleeps == [1.5]  # clock is frozen, so the second call must wait the full interval


def test_custom_headers_are_sent(tmp_path: Path) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, content=b"x")

    fetcher, _ = make_fetcher(tmp_path, handler)
    fetcher.get("https://x.test/a", cache_key="a", headers={"X-Requested-With": "XMLHttpRequest"})
    assert seen["x-requested-with"] == "XMLHttpRequest"


def test_invalid_200_response_is_not_cached(tmp_path: Path) -> None:
    fetcher, _ = make_fetcher(tmp_path, lambda r: httpx.Response(200, content=b"<html>not JSON</html>"))

    with pytest.raises(FetchError):
        fetcher.get("https://x.test/data", cache_key="bad.json", validate=lambda body: json.loads(body))

    assert not (tmp_path / "bad.json").exists()
