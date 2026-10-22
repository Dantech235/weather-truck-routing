"""Shared outbound HTTP: one httpx client, retries with backoff + jitter, per-provider breaker."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TIMEOUT_S = 8.0
RETRIES = 2
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class ProviderUnavailable(Exception):
    """The provider could not be reached or kept failing (network, 5xx, 429, open breaker)."""


class ProviderHTTPError(Exception):
    """A non-retryable HTTP error response (4xx other than 429)."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code} from {response.request.url.host}")
        self.response = response


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; stays open for `reset_s` seconds."""

    def __init__(
        self,
        name: str,
        threshold: int = 5,
        reset_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.threshold = threshold
        self.reset_s = reset_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if self._clock() - self._opened_at >= self.reset_s:
                # Half-open: allow a trial request; one more failure re-opens immediately.
                self._opened_at = None
                self._failures = self.threshold - 1
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold and self._opened_at is None:
                self._opened_at = self._clock()
                logger.warning("circuit_open provider=%s", self.name)


_client: httpx.Client | None = None
_client_lock = threading.Lock()


def shared_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(
                timeout=TIMEOUT_S,
                headers={"User-Agent": "weather-truck-routing/1.0"},
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return _client


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    breaker: CircuitBreaker,
    retries: int = RETRIES,
    sleep: Callable[[float], None] | None = None,
    **kwargs: Any,
) -> Any:
    """Send a request and return decoded JSON.

    Retries network errors, 429 and 5xx up to `retries` times with exponential backoff and
    jitter (honouring Retry-After). Raises ProviderUnavailable when retries are exhausted or the
    breaker is open, and ProviderHTTPError for other 4xx responses (not counted as failures).
    """
    pause = sleep or time.sleep
    if breaker.is_open:
        raise ProviderUnavailable(f"{breaker.name} circuit open")
    last_error: str = ""
    for attempt in range(retries + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                breaker.record_success()
                return response.json()
            if response.status_code not in RETRY_STATUSES:
                breaker.record_success()  # the provider is up; the request itself was bad
                raise ProviderHTTPError(response)
            last_error = f"HTTP {response.status_code}"
            retry_after = _retry_after(response)
            if attempt < retries:
                pause(retry_after if retry_after is not None else _backoff(attempt))
                continue
        if attempt < retries:
            pause(_backoff(attempt))
    breaker.record_failure()
    raise ProviderUnavailable(f"{breaker.name}: {last_error}")


def _backoff(attempt: int) -> float:
    return float(min(4.0, 0.5 * 2**attempt + random.uniform(0, 0.25)))


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(4.0, max(0.0, float(value)))
    except ValueError:
        return None
