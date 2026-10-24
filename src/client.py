"""HTTP transport for the OpenRouter System One (Decisions) endpoint.

Design notes
------------
* The API key is read from ``OPENROUTER_API_KEY`` only; it is never written to
  disk, never logged and never included in a cached payload.
* Retries happen only for transport failures and for status codes that mean
  "try again later" (429 / 5xx). A 400 or 401 is a bug in the request or the
  key, and retrying it would just burn quota.
* Responses are cached by a hash of (model, payload) so a resumed run never
  pays twice for the same question.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/systemone"
RETRY_STATUS = {429, 500, 502, 503, 504, 524, 529}


class ApiError(Exception):
    def __init__(self, status: int, body: str, retryable: bool = False):
        self.status = status
        self.body = body
        self.retryable = retryable
        super().__init__(f"HTTP {status}: {body[:400]}")


def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Export it before running, e.g.\n"
            '  $env:OPENROUTER_API_KEY = "sk-or-v1-..."'
        )
    return key


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_hash(model: str, payload: dict) -> str:
    raw = model + "\n" + canonical_json(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class Client:
    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 120.0,
        max_retries: int = 5,
        min_interval: float = 0.0,
        cache_dir: Path | None = None,
    ):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval = min_interval
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_call = 0.0
        self.calls = 0
        self.cache_hits = 0
        self.retries = 0

    # ------------------------------------------------------------------ cache
    def _cache_path(self, key: str) -> Path | None:
        return self.cache_dir / f"{key}.json" if self.cache_dir else None

    def _cache_get(self, key: str):
        path = self._cache_path(key)
        if path and path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _cache_put(self, key: str, response: dict) -> None:
        path = self._cache_path(key)
        if path:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)

    # -------------------------------------------------------------- transport
    def _throttle(self) -> None:
        if self.min_interval > 0:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)

    def call(self, payload: dict, use_cache: bool = True) -> tuple[dict, dict]:
        """Send one decision request.

        Returns ``(response, meta)`` where meta carries latency and cache flag.
        Raises :class:`ApiError` on non-retryable failures.
        """
        key = request_hash(payload.get("model", ""), payload)
        if use_cache:
            hit = self._cache_get(key)
            if hit is not None:
                self.cache_hits += 1
                return hit, {"latency_ms": 0, "cached": True, "attempts": 0}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/decision-bench",
            "X-OpenRouter-Title": "Decision Model Bench",
        }

        last_error: ApiError | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            started = time.monotonic()
            req = urllib.request.Request(
                self.endpoint, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                elapsed = (time.monotonic() - started) * 1000
                self._last_call = time.monotonic()
                self.calls += 1
                parsed = json.loads(raw)
                if use_cache:
                    self._cache_put(key, parsed)
                return parsed, {
                    "latency_ms": round(elapsed, 1),
                    "cached": False,
                    "attempts": attempt,
                }
            except urllib.error.HTTPError as exc:
                elapsed = (time.monotonic() - started) * 1000
                text = exc.read().decode("utf-8", errors="replace")
                retryable = exc.code in RETRY_STATUS
                last_error = ApiError(exc.code, text, retryable)
                if not retryable:
                    raise last_error from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = ApiError(0, f"transport: {exc}", True)

            self._last_call = time.monotonic()
            if attempt < self.max_retries:
                self.retries += 1
                backoff = min(60.0, 2.0 * (2 ** (attempt - 1)))
                time.sleep(backoff + random.uniform(0, 0.75))

        assert last_error is not None
        raise last_error
