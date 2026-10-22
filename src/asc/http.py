"""A very small HTTP client.

It only relies on the standard library so that the dataset setup can run in
minimal environments.  Features:

* polite defaults (custom User-Agent, minimum interval between requests)
* exponential back-off retries
* optional on-disk cache
* transparent gzip handling
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


class HttpError(RuntimeError):
    """Raised when a request could not be completed after all retries."""


class HttpClient:
    def __init__(
        self,
        user_agent: str = "AutoStoryCreationAI-dataset-builder/0.1",
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff: float = 2.0,
        request_interval: float = 1.0,
        cache_dir: Optional[Path] = None,
        cache_ttl_seconds: int = 60 * 60 * 24 * 7,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.request_interval = request_interval
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl_seconds = cache_ttl_seconds
        self._last_request = 0.0

    # ------------------------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self._last_request = time.monotonic()

    def _cache_path(self, url: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / f"{digest}.bin"

    def _read_cache(self, url: str) -> Optional[bytes]:
        path = self._cache_path(url)
        if path is None or not path.exists():
            return None
        if self.cache_ttl_seconds and (time.time() - path.stat().st_mtime) > self.cache_ttl_seconds:
            return None
        try:
            return path.read_bytes()
        except OSError:  # pragma: no cover - defensive
            return None

    def _write_cache(self, url: str, payload: bytes) -> None:
        path = self._cache_path(url)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        except OSError:  # pragma: no cover - defensive
            pass

    # ------------------------------------------------------------------
    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
        timeout: Optional[float] = None,
    ) -> bytes:
        """GET ``url`` and return the raw body."""
        if use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                LOGGER.debug("cache hit: %s", url)
                return cached

        request_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip",
            "Accept": "*/*",
        }
        if headers:
            request_headers.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                request = urllib.request.Request(url, headers=request_headers)
                with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                    payload = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        payload = gzip.decompress(payload)
                if use_cache:
                    self._write_cache(url, payload)
                return payload
            except (urllib.error.URLError, OSError, ValueError) as exc:
                last_error = exc
                LOGGER.warning("request failed (%s/%s): %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff * attempt)
        raise HttpError(f"GET {url} failed: {last_error}") from last_error

    def get_text(self, url: str, encoding: str = "utf-8", **kwargs: Any) -> str:
        return self.get(url, **kwargs).decode(encoding, errors="replace")

    def get_json(self, url: str, **kwargs: Any) -> Any:
        import json

        payload = self.get(url, **kwargs)
        return json.loads(payload.decode("utf-8"))
