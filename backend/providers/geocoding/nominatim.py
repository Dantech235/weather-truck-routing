"""Nominatim fallback, server-side only, throttled to 1 request/second per process.

Usage policy: https://operations.osmfoundation.org/policies/nominatim/ (identify the app via
User-Agent, max 1 req/s, cache results — geocode results are cached for 24 h upstream).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import httpx

from core.http import CircuitBreaker, ProviderHTTPError, ProviderUnavailable, request_json

from .base import MAX_RESULTS, GeocodingUnavailable, Place

URL = "https://nominatim.openstreetmap.org/search"
MIN_INTERVAL_S = 1.0


class NominatimGeocoding:
    name = "nominatim"

    def __init__(
        self,
        client: httpx.Client,
        breaker: CircuitBreaker,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.breaker = breaker
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last = -MIN_INTERVAL_S

    def _wait_turn(self) -> None:
        with self._lock:
            wait = self._last + MIN_INTERVAL_S - self._clock()
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()

    def search(self, query: str) -> list[Place]:
        self._wait_turn()
        try:
            data = request_json(
                self.client,
                "GET",
                URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": MAX_RESULTS,
                    "countrycodes": "us,ca",
                },
                headers={"User-Agent": "weather-truck-routing/1.0 (server-side geocoding)"},
                breaker=self.breaker,
                retries=0,
            )
        except (ProviderUnavailable, ProviderHTTPError) as exc:
            raise GeocodingUnavailable(str(exc)) from exc
        return [
            Place(label=str(r["display_name"]), lat=float(r["lat"]), lon=float(r["lon"]))
            for r in data
            if "display_name" in r and "lat" in r and "lon" in r
        ]
