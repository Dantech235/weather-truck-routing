from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from core.http import CircuitBreaker
from providers.routing.base import (
    FallbackRouting,
    RouteNotFound,
    RouteResult,
    RoutingUnavailable,
)
from providers.routing.ors import URL as ORS_URL
from providers.routing.ors import OrsRouting
from providers.routing.tomtom import BASE_URL, TomTomRouting

from .conftest import load_fixture

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
DEPART = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)
DAL, DEN = (32.7767, -96.797), (39.7392, -104.9903)
TT_PATTERN = respx.route(method="GET", url__startswith=BASE_URL)


def tomtom(client: httpx.Client, key: str = "k") -> TomTomRouting:
    return TomTomRouting(client, key, CircuitBreaker("tt"), now=lambda: NOW)


# --- TomTom --------------------------------------------------------------------------------


@respx.mock
def test_tomtom_parses_routes_and_sends_truck_params(client: httpx.Client) -> None:
    route = respx.get(url__startswith=BASE_URL).respond(json=load_fixture("tomtom_route.json"))
    results = tomtom(client).routes(DAL, DEN, DEPART, 45_000, max_alternatives=2)

    params = route.calls.last.request.url.params
    assert params["travelMode"] == "truck"
    assert params["vehicleWeight"] == str(round(45_000 * 0.45359237))  # kg
    assert params["maxAlternatives"] == "2"
    assert params["departAt"] == "2026-10-22T13:00:00+00:00"
    assert params["instructionsType"] == "coded"
    assert params["routeRepresentation"] == "polyline"
    assert params["computeTravelTimeFor"] == "all"
    assert "32.776700,-96.797000:39.739200,-104.990300/json" in str(route.calls.last.request.url)

    first = results[0]
    assert first.provider == "tomtom"
    assert first.length_m == 1_265_000
    assert first.travel_time_s == 45_000
    assert first.departure_utc == datetime(2026, 10, 22, 13, 0, tzinfo=UTC)
    assert first.arrival_utc == datetime(2026, 10, 22, 20, 30, tzinfo=UTC)
    assert len(first.coords) == 41  # 21 + 21 points, joining point de-duplicated
    assert first.guidance[1] == (400_000.0, 13_000.0)
    assert results[1].guidance == []  # no guidance → proportional ETA later


@respx.mock
def test_tomtom_via_points_go_in_path_and_past_departure_omits_departat(
    client: httpx.Client,
) -> None:
    route = respx.get(url__startswith=BASE_URL).respond(json=load_fixture("tomtom_route.json"))
    tomtom(client).routes(DAL, DEN, NOW - timedelta(minutes=5), 10_000, 0, via=[(35.0, -100.0)])
    url = str(route.calls.last.request.url)
    assert ":35.000000,-100.000000:" in url
    assert "departAt" not in route.calls.last.request.url.params


@respx.mock
def test_tomtom_no_route_maps_to_route_not_found(client: httpx.Client) -> None:
    respx.get(url__startswith=BASE_URL).respond(400, json=load_fixture("tomtom_no_route.json"))
    with pytest.raises(RouteNotFound, match="MAP_MATCHING_FAILURE"):
        tomtom(client).routes(DAL, DEN, DEPART, 1, 2)


@respx.mock
def test_tomtom_non_json_error_and_empty_routes(client: httpx.Client) -> None:
    respx.get(url__startswith=BASE_URL).mock(
        side_effect=[httpx.Response(404, text="<xml/>"), httpx.Response(200, json={"routes": []})]
    )
    with pytest.raises(RouteNotFound, match="HTTP 404"):
        tomtom(client).routes(DAL, DEN, DEPART, 1, 2)
    with pytest.raises(RouteNotFound, match="no routes"):
        tomtom(client).routes(DAL, DEN, DEPART, 1, 2)


@respx.mock
def test_tomtom_auth_error_and_outage_are_unavailable(client: httpx.Client) -> None:
    respx.get(url__startswith=BASE_URL).mock(
        side_effect=[httpx.Response(403, text="<xml>forbidden</xml>"), *[httpx.Response(503)] * 3]
    )
    with pytest.raises(RoutingUnavailable, match="API key"):
        tomtom(client).routes(DAL, DEN, DEPART, 1, 2)
    with pytest.raises(RoutingUnavailable, match="503"):
        tomtom(client).routes(DAL, DEN, DEPART, 1, 2)


def test_tomtom_without_key_is_unavailable(client: httpx.Client) -> None:
    with pytest.raises(RoutingUnavailable, match="not configured"):
        tomtom(client, key="").routes(DAL, DEN, DEPART, 1, 2)


# --- ORS -----------------------------------------------------------------------------------


@respx.mock
def test_ors_parses_geojson_and_builds_cumulative_guidance(client: httpx.Client) -> None:
    route = respx.post(ORS_URL).respond(json=load_fixture("ors_route.json"))
    (r,) = OrsRouting(client, "ors-key", CircuitBreaker("ors")).routes(DAL, DEN, DEPART, 45_000, 2)
    req = route.calls.last.request
    body = json.loads(req.content)
    assert req.headers["Authorization"] == "ors-key"
    assert body["coordinates"][0] == [DAL[1], DAL[0]]  # [lon, lat]
    assert body["options"]["profile_params"]["restrictions"]["weight"] == pytest.approx(20.4)
    assert "alternative_routes" not in body  # long trip: ORS caps alternatives at ~100 km
    assert r.provider == "ors"
    assert r.coords[0] == pytest.approx(DAL)
    assert r.length_m == 1_280_000
    assert r.travel_time_s == 50_000
    assert r.guidance == [(500_000.0, 18_000.0), (1_280_000.0, 50_000.0)]
    assert r.departure_utc == DEPART
    assert r.arrival_utc == DEPART + timedelta(seconds=50_000)


@respx.mock
def test_ors_requests_alternatives_only_for_short_trips(client: httpx.Client) -> None:
    route = respx.post(ORS_URL).respond(json=load_fixture("ors_route.json"))
    OrsRouting(client, "k", CircuitBreaker("ors")).routes(DAL, (32.9, -97.3), DEPART, 1, 2)
    alt = json.loads(route.calls.last.request.content)["alternative_routes"]
    assert alt["target_count"] == 3


@respx.mock
def test_ors_errors(client: httpx.Client) -> None:
    respx.post(ORS_URL).mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(404, json={"error": {"code": 2010}}),
            httpx.Response(200, json={"features": []}),
        ]
    )
    ors = OrsRouting(client, "k", CircuitBreaker("ors"))
    with pytest.raises(RoutingUnavailable):
        ors.routes(DAL, DEN, DEPART, 1, 0)
    with pytest.raises(RouteNotFound, match="404"):
        ors.routes(DAL, DEN, DEPART, 1, 0)
    with pytest.raises(RouteNotFound, match="no routes"):
        ors.routes(DAL, DEN, DEPART, 1, 0)
    with pytest.raises(RoutingUnavailable, match="not configured"):
        OrsRouting(client, "", CircuitBreaker("x")).routes(DAL, DEN, DEPART, 1, 0)


@respx.mock
def test_ors_outage_is_unavailable(client: httpx.Client) -> None:
    respx.post(ORS_URL).respond(502)
    with pytest.raises(RoutingUnavailable):
        OrsRouting(client, "k", CircuitBreaker("ors")).routes(DAL, DEN, DEPART, 1, 0)


# --- Fallback ------------------------------------------------------------------------------


class Stub:
    def __init__(self, name: str, result: list[RouteResult] | Exception) -> None:
        self.name = name
        self.result = result
        self.calls = 0

    def routes(self, *args: object, **kwargs: object) -> list[RouteResult]:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _route(provider: str) -> RouteResult:
    return RouteResult([DAL, DEN], 1000.0, 60, [], DEPART, DEPART, provider)


def test_fallback_uses_second_provider_when_first_unavailable() -> None:
    primary = Stub("tomtom", RoutingUnavailable("down"))
    secondary = Stub("ors", [_route("ors")])
    out = FallbackRouting([primary, secondary]).routes(DAL, DEN, DEPART, 1, 2)
    assert out[0].provider == "ors"
    assert (primary.calls, secondary.calls) == (1, 1)


def test_fallback_does_not_mask_route_not_found() -> None:
    secondary = Stub("ors", [_route("ors")])
    with pytest.raises(RouteNotFound):
        FallbackRouting([Stub("tomtom", RouteNotFound("x")), secondary]).routes(
            DAL, DEN, DEPART, 1, 2
        )
    assert secondary.calls == 0


def test_fallback_all_unavailable() -> None:
    fb = FallbackRouting([Stub("a", RoutingUnavailable("1")), Stub("b", RoutingUnavailable("2"))])
    with pytest.raises(RoutingUnavailable, match="a: 1; b: 2"):
        fb.routes(DAL, DEN, DEPART, 1, 2)
    with pytest.raises(ValueError, match="at least one"):
        FallbackRouting([])
