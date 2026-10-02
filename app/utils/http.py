"""HTTP client with timeouts, retries, cache, and host checks."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.db import Database
from app.utils.safety import UnsafeURL, assert_public_host, assert_safe_url


class SourceError(Exception):
    """A bibliographic source failed after retries."""


class HttpClient:
    def __init__(self, database: Database, user_agent: str, timeout: float = 12.0, cache_ttl: int = 86400, miss_ttl: int = 3600):
        self.database = database
        self.user_agent = user_agent
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.miss_ttl = miss_ttl
        self._client: httpx.AsyncClient | None = None
        self._pace: dict[str, float] = {}
        self._pace_lock = asyncio.Lock()

    async def __aenter__(self) -> HttpClient:
        async def _guard(request: httpx.Request) -> None:
            try:
                assert_public_host(request.url.host)
            except UnsafeURL as exc:
                raise httpx.RequestError(str(exc), request=request) from exc

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            follow_redirects=True,
            event_hooks={"request": [_guard]},
            limits=httpx.Limits(max_connections=12, max_keepalive_connections=6),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _pace_for(self, key: str, interval: float) -> None:
        async with self._pace_lock:
            now = time.monotonic()
            wait = interval - (now - self._pace.get(key, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._pace[key] = time.monotonic()

    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        cache_key: str | None = None,
        headers: dict | None = None,
        pace_key: str | None = None,
        pace_seconds: float = 0.0,
    ) -> Any:
        if cache_key:
            cached = self.database.cache_get(cache_key)
            if cached is not None:
                if isinstance(cached, dict) and cached.get("__missing__") is True:
                    return None
                return cached
        if pace_key and pace_seconds:
            await self._pace_for(pace_key, pace_seconds)
        payload = await self._request_json(url, params=params, headers=headers)
        if cache_key:
            if payload is None:
                self.database.cache_set(cache_key, {"__missing__": True}, self.miss_ttl)
            else:
                self.database.cache_set(cache_key, payload, self.cache_ttl)
        return payload

    async def _request_json(self, url: str, params: dict | None, headers: dict | None) -> Any:
        if self._client is None:
            raise SourceError("HTTP client is not open.")
        last = "request failed"
        for attempt in range(3):
            try:
                response = await self._client.get(url, params=params, headers=headers)
                if response.status_code == 404:
                    return None
                if response.status_code in {429, 500, 502, 503, 504}:
                    last = f"HTTP {response.status_code}"
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                last = "timed out"
                await asyncio.sleep(0.3 * (attempt + 1))
            except httpx.HTTPError as exc:
                last = str(exc)
                if attempt == 2:
                    break
                await asyncio.sleep(0.2)
        raise SourceError(last)

    async def get_text(self, url: str, limit: int = 1_000_000) -> str | None:
        if self._client is None:
            raise SourceError("HTTP client is not open.")
        safe = assert_safe_url(url)
        try:
            async with self._client.stream(
                "GET",
                safe,
                headers={"Accept": "text/html,application/xhtml+xml"},
            ) as response:
                if response.status_code >= 400:
                    return None
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size > limit:
                        break
                raw = b"".join(chunks)[:limit]
                encoding = response.encoding or "utf-8"
                return raw.decode(encoding, errors="replace")
        except (httpx.HTTPError, UnsafeURL) as exc:
            raise SourceError(str(exc)) from exc
