"""Builds the configured providers once per process. Keys come from settings only."""

from __future__ import annotations

from functools import cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.http import CircuitBreaker, shared_client

from .geocoding.base import FallbackGeocoding, GeocodingProvider
from .geocoding.nominatim import NominatimGeocoding
from .geocoding.tomtom import TomTomGeocoding
from .routing.base import FallbackRouting, RoutingProvider
from .routing.ors import OrsRouting
from .routing.tomtom import TomTomRouting
from .weather.base import WeatherProvider
from .weather.openmeteo import OpenMeteoWeather


def _fake_mode() -> bool:
    if settings.PROVIDERS_MODE == "fake":
        if not settings.DEBUG:
            raise ImproperlyConfigured("PROVIDERS_MODE=fake is test-only; refused when DEBUG=False")
        return True
    return False


@cache
def breaker(name: str) -> CircuitBreaker:
    return CircuitBreaker(name)


@cache
def routing() -> RoutingProvider:
    if _fake_mode():
        from .fake import FakeRouting

        return FakeRouting()
    client = shared_client()
    return FallbackRouting(
        [
            TomTomRouting(client, settings.TOMTOM_API_KEY, breaker("tomtom-routing")),
            OrsRouting(client, settings.ORS_API_KEY, breaker("ors-routing")),
        ]
    )


@cache
def geocoding() -> GeocodingProvider:
    if _fake_mode():
        from .fake import FakeGeocoding

        return FakeGeocoding()
    client = shared_client()
    providers: list[GeocodingProvider] = []
    if settings.TOMTOM_API_KEY:
        providers.append(TomTomGeocoding(client, settings.TOMTOM_API_KEY, breaker("tomtom-search")))
    providers.append(NominatimGeocoding(client, breaker("nominatim")))
    return FallbackGeocoding(providers)


@cache
def weather() -> WeatherProvider:
    if _fake_mode():
        from .fake import FakeWeather

        return FakeWeather()
    return OpenMeteoWeather(shared_client(), settings.OPEN_METEO_BASE_URL, breaker("open-meteo"))


def reset() -> None:
    """Forget cached providers (tests, settings changes)."""
    for fn in (routing, geocoding, weather, breaker):
        clear = getattr(fn, "cache_clear", None)  # may be monkeypatched in tests
        if clear is not None:
            clear()
