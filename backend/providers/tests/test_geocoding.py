from __future__ import annotations

import httpx
import pytest
import respx

from core.http import CircuitBreaker
from providers.geocoding.base import FallbackGeocoding, GeocodingUnavailable, Place
from providers.geocoding.nominatim import URL as NOMINATIM_URL
from providers.geocoding.nominatim import NominatimGeocoding
from providers.geocoding.tomtom import BASE_URL, TomTomGeocoding

from .conftest import load_fixture


@respx.mock
def test_tomtom_typeahead_params_and_parse(client: httpx.Client) -> None:
    route = respx.get(url__startswith=BASE_URL).respond(json=load_fixture("tomtom_search.json"))
    places = TomTomGeocoding(client, "k", CircuitBreaker("s")).search("dallas tx")
    req = route.calls.last.request
    assert "/search/2/search/dallas%20tx.json?" in str(req.url)
    assert req.url.params["typeahead"] == "true"
    assert req.url.params["limit"] == "6"
    assert req.url.params["countrySet"] == "US,CA"
    assert places == [
        Place("Dallas, TX", 32.77815, -96.7954),
        Place("Dallas Love Field, 8008 Herb Kelleher Way, Dallas, TX 75235", 32.8471, -96.8518),
    ]


@respx.mock
def test_tomtom_errors_are_unavailable(client: httpx.Client) -> None:
    respx.get(url__startswith=BASE_URL).respond(403)
    with pytest.raises(GeocodingUnavailable):
        TomTomGeocoding(client, "k", CircuitBreaker("s")).search("dallas")
    with pytest.raises(GeocodingUnavailable, match="not configured"):
        TomTomGeocoding(client, "", CircuitBreaker("s")).search("dallas")


@respx.mock
def test_nominatim_parse_and_rate_limit(client: httpx.Client) -> None:
    route = respx.get(url__startswith=NOMINATIM_URL).respond(
        json=load_fixture("nominatim_search.json")
    )
    now = [100.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    geo = NominatimGeocoding(client, CircuitBreaker("n"), clock=lambda: now[0], sleep=sleep)
    first = geo.search("dallas")
    now[0] += 0.3
    geo.search("dallas")
    assert first == [Place("Dallas, Dallas County, Texas, United States", 32.7762719, -96.7968559)]
    assert slept == [pytest.approx(0.7)]  # second call waited to keep 1 req/s
    params = route.calls.last.request.url.params
    assert params["countrycodes"] == "us,ca"
    assert params["format"] == "jsonv2"
    assert "weather-truck-routing" in route.calls.last.request.headers["User-Agent"]


@respx.mock
def test_nominatim_failure(client: httpx.Client) -> None:
    respx.get(url__startswith=NOMINATIM_URL).respond(503)
    with pytest.raises(GeocodingUnavailable):
        NominatimGeocoding(client, CircuitBreaker("n")).search("dallas")


class Stub:
    def __init__(self, name: str, result: list[Place] | Exception) -> None:
        self.name = name
        self.result = result

    def search(self, query: str) -> list[Place]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_fallback_geocoding() -> None:
    many = [Place(str(i), 0, 0) for i in range(10)]
    fb = FallbackGeocoding([Stub("tt", GeocodingUnavailable("x")), Stub("nom", many)])
    assert len(fb.search("abc")) == 6
    with pytest.raises(GeocodingUnavailable, match="tt: x"):
        FallbackGeocoding([Stub("tt", GeocodingUnavailable("x"))]).search("abc")
    with pytest.raises(ValueError, match="at least one"):
        FallbackGeocoding([])
