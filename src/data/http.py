from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) footyquant-research/0.1"
RETRY_STATUSES = {500, 502, 503, 504}
STOP_STATUSES = {403, 429}


class FetchError(Exception):
    def __init__(self, message: str, *, url: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class BlockedError(FetchError):
    """403/429: the host is refusing us. Callers must stop the whole run, not retry."""


@dataclass
class FetchResult:
    body: bytes
    from_cache: bool
    path: Path
    changed: bool = False


class CachedFetcher:
    """Polite, resumable HTTP GET with an immutable raw-response cache.

    Every response is stored at ``cache_dir / cache_key`` next to a ``.meta.json`` sidecar
    (url, status, fetched_at, sha256, size). With ``refresh=True`` the URL is fetched again; if the
    content changed, the previous copy is archived as ``<key>@<fetched_at>`` instead of overwritten.
    """

    def __init__(
        self,
        cache_dir: Path,
        *,
        min_interval_s: float = 1.0,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        base_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "gzip"}
        base_headers.update(headers or {})
        self._client = client or httpx.Client(
            headers=base_headers, timeout=timeout_s, follow_redirects=True
        )
        if client is not None:
            self._client.headers.update(base_headers)
        self.network_calls = 0

    def close(self) -> None:
        self._client.close()

    def path_for(self, cache_key: str) -> Path:
        return self.cache_dir / cache_key

    def cached(self, cache_key: str) -> bool:
        return self.path_for(cache_key).exists()

    def get(
        self,
        url: str,
        *,
        cache_key: str,
        headers: dict[str, str] | None = None,
        refresh: bool = False,
        validate: Callable[[bytes], None] | None = None,
    ) -> FetchResult:
        path = self.path_for(cache_key)
        if path.exists() and not refresh:
            body = path.read_bytes()
            self._validate(url, body, validate)
            return FetchResult(body, from_cache=True, path=path)

        body = self._fetch(url, headers)
        self._validate(url, body, validate)
        changed = True
        if path.exists():
            old = path.read_bytes()
            if hashlib.sha256(old).digest() == hashlib.sha256(body).digest():
                changed = False
            else:
                self._archive(path)
        if changed:
            self._store(url, path, body)
        return FetchResult(body, from_cache=False, path=path, changed=changed)

    @staticmethod
    def _validate(url: str, body: bytes, validate: Callable[[bytes], None] | None) -> None:
        if validate is None:
            return
        try:
            validate(body)
        except Exception as exc:
            raise FetchError(f"invalid response body from {url}: {exc}", url=url, status_code=200) from exc

    def _fetch(self, url: str, headers: dict[str, str] | None) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self.network_calls += 1
            try:
                response = self._client.get(url, headers=headers)
            except httpx.TransportError as exc:
                last_error = exc
            else:
                status = response.status_code
                if status in STOP_STATUSES:
                    raise BlockedError(
                        f"HTTP {status} from {url}; stopping to avoid hammering",
                        url=url,
                        status_code=status,
                    )
                if status == 200:
                    return response.content
                if status not in RETRY_STATUSES:
                    raise FetchError(f"HTTP {status} from {url}", url=url, status_code=status)
                last_error = FetchError(f"HTTP {status} from {url}", url=url, status_code=status)
            if attempt < self.max_retries:
                self._sleep(2.0**attempt)
        raise FetchError(f"giving up on {url}: {last_error}", url=url) from last_error

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            wait = self.min_interval_s - (self._clock() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()

    def _archive(self, path: Path) -> None:
        meta_path = path.with_name(path.name + ".meta.json")
        stamp = "unknown"
        if meta_path.exists():
            stamp = json.loads(meta_path.read_text(encoding="utf-8")).get("fetched_at", stamp)
        stamp = "".join(ch for ch in stamp if ch.isalnum())
        path.rename(path.with_name(f"{path.name}@{stamp}"))
        if meta_path.exists():
            meta_path.rename(meta_path.with_name(f"{path.name}@{stamp}.meta.json"))

    def _store(self, url: str, path: Path, body: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        meta = {
            "url": url,
            "status": 200,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "size": len(body),
        }
        path.with_name(path.name + ".meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
