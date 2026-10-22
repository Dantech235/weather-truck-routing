from __future__ import annotations

import httpx
import pytest
import respx

from core.http import (
    CircuitBreaker,
    ProviderHTTPError,
    ProviderUnavailable,
    request_json,
    shared_client,
)

URL = "https://example.test/x"


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@respx.mock
def test_success_returns_json(client: httpx.Client) -> None:
    respx.get(URL).respond(json={"ok": True})
    assert request_json(client, "GET", URL, breaker=CircuitBreaker("t")) == {"ok": True}


@respx.mock
def test_retries_5xx_then_succeeds(client: httpx.Client) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json=[1])]
    )
    sleeps: list[float] = []
    assert request_json(client, "GET", URL, breaker=CircuitBreaker("t"), sleep=sleeps.append) == [1]
    assert route.call_count == 3
    assert len(sleeps) == 2


@respx.mock
def test_retry_after_is_honoured_and_capped(client: httpx.Client) -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(429, headers={"Retry-After": "120"}),
            httpx.Response(200, json={}),
        ]
    )
    sleeps: list[float] = []
    request_json(client, "GET", URL, breaker=CircuitBreaker("t"), sleep=sleeps.append)
    assert sleeps == [2.0, 4.0]


@respx.mock
def test_bad_retry_after_falls_back_to_backoff(client: httpx.Client) -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "soon"}),
            httpx.Response(200, json={}),
        ]
    )
    sleeps: list[float] = []
    request_json(client, "GET", URL, breaker=CircuitBreaker("t"), sleep=sleeps.append)
    assert 0.5 <= sleeps[0] <= 0.75


@respx.mock
def test_exhausted_retries_raise_unavailable_and_count_failure(client: httpx.Client) -> None:
    route = respx.get(URL).respond(500)
    breaker = CircuitBreaker("t", threshold=1)
    with pytest.raises(ProviderUnavailable, match="HTTP 500"):
        request_json(client, "GET", URL, breaker=breaker)
    assert route.call_count == 3
    assert breaker.is_open


@respx.mock
def test_network_errors_are_retried(client: httpx.Client) -> None:
    route = respx.get(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ProviderUnavailable, match="ConnectError"):
        request_json(client, "GET", URL, breaker=CircuitBreaker("t"))
    assert route.call_count == 3


@respx.mock
def test_4xx_is_not_retried_and_not_a_failure(client: httpx.Client) -> None:
    route = respx.get(URL).respond(400, json={"detail": "bad"})
    breaker = CircuitBreaker("t", threshold=1)
    with pytest.raises(ProviderHTTPError) as info:
        request_json(client, "GET", URL, breaker=breaker)
    assert info.value.response.status_code == 400
    assert route.call_count == 1
    assert not breaker.is_open


@respx.mock
def test_open_breaker_short_circuits(client: httpx.Client) -> None:
    route = respx.get(URL).respond(200, json={})
    breaker = CircuitBreaker("t", threshold=1)
    breaker.record_failure()
    with pytest.raises(ProviderUnavailable, match="circuit open"):
        request_json(client, "GET", URL, breaker=breaker)
    assert route.call_count == 0


def test_breaker_opens_after_threshold_and_half_opens_after_reset() -> None:
    clock = FakeClock()
    b = CircuitBreaker("t", threshold=5, reset_s=60, clock=clock)
    for _ in range(4):
        b.record_failure()
    assert not b.is_open
    b.record_failure()
    assert b.is_open
    clock.t = 59.9
    assert b.is_open
    clock.t = 60.0
    assert not b.is_open  # half-open trial allowed
    b.record_failure()  # trial fails → open again immediately
    assert b.is_open
    clock.t = 200.0
    assert not b.is_open
    b.record_success()
    for _ in range(4):
        b.record_failure()
    assert not b.is_open


def test_shared_client_is_singleton() -> None:
    assert shared_client() is shared_client()
