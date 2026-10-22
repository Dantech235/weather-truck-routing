from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import polyline
import pytest
from django.core.cache import cache

from core.exceptions import ApiError
from core.geo import LatLon
from providers.routing.base import RouteNotFound, RoutingUnavailable
from trips.models import TripPlan
from trips.services import PlanInput, build_plan, get_weather, risk_rules_payload, serialize_plan

from .stubs import DAL, DEN, StubRouting, StubWeather, calm, line, make_route

pytestmark = pytest.mark.django_db
DEPART = datetime(2026, 10, 22, 13, 7, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


def inp(load: int = 45_000, interval: int = 25) -> PlanInput:
    return PlanInput(
        origin={"label": "Dallas, TX", "lat": DAL[0], "lon": DAL[1]},
        destination={"label": "Denver, CO", "lat": DEN[0], "lon": DEN[1]},
        departure_utc=DEPART,
        load_lb=load,
        interval_mi=interval,
    )


def three_routes() -> StubRouting:
    return StubRouting(
        [
            [
                make_route(line(DAL, DEN, 80, 0.0), 40_000, DEPART),
                make_route(line(DAL, DEN, 80, 1.5), 42_000, DEPART),
                make_route(line(DAL, DEN, 80, -1.5), 44_000, DEPART),
            ]
        ]
    )


def windy_west_of(lon_cut: float, mph: float) -> StubWeather:
    """Strong wind wherever lon < lon_cut (the west-bowed route passes through more of it)."""
    return StubWeather(lambda p, _k: (mph if p[1] < lon_cut else 5.0, 0.0, 0.0))


def test_plan_shape_checkpoints_and_eta() -> None:
    plan = build_plan(inp(), three_routes(), StubWeather(calm))
    body = serialize_plan(plan)
    assert body["status"] == "ready"
    assert body["routes_found"] == 3
    assert body["recommended"] == "A"  # all calm → shortest time wins
    route = body["routes"][0]
    cps = route["checkpoints"]
    assert [c["mile"] for c in cps[:4]] == [0.0, 25.0, 50.0, 75.0]
    assert cps[-1]["mile"] == route["distance_mi"]
    assert cps[0]["eta_utc"] == "2026-10-22T13:07:00Z"
    assert cps[-1]["eta_utc"] == route["arrival_utc"]
    assert cps[-1]["elapsed_s"] == route["travel_time_s"]
    assert cps[1]["eta_method"] == "guidance"
    assert cps[1]["weather"]["forecast_hour_utc"].endswith(":00:00Z")
    assert cps[1]["risk"]["level"] == "LOW"
    decoded = polyline.decode(route["geometry"], 5)
    assert decoded[0] == pytest.approx(DAL, abs=1e-5)
    assert len(decoded) < 81  # simplified for display
    m = route["metrics"]
    total = sum(
        m[k]
        for k in (
            "no_travel_miles",
            "severe_miles",
            "high_miles",
            "moderate_miles",
            "low_miles",
            "unknown_miles",
        )
    )
    assert total == pytest.approx(route["distance_mi"], abs=0.1)
    assert route["segments"][0]["from_frac"] == 0.0
    assert route["segments"][-1]["to_frac"] == 1.0
    assert body["meta"]["interval_mi"] == 25
    assert set(body["meta"]["timings_ms"]) >= {
        "routing",
        "sampling_eta",
        "weather",
        "risk",
        "ranking",
    }
    assert body["warnings"] == []
    assert TripPlan.objects.count() == 1


def test_weather_is_selected_at_each_eta_not_departure() -> None:
    # Wind ramps up 5 mph per hour from the departure hour.
    weather = StubWeather(lambda _p, k: (5.0 * k, 0.0, 0.0))
    body = serialize_plan(build_plan(inp(), three_routes(), weather))
    cps = body["routes"][0]["checkpoints"]
    assert cps[0]["weather"]["wind_mph"] < cps[-1]["weather"]["wind_mph"]
    assert cps[-1]["weather"]["wind_mph"] > 40  # ~11 h later


def test_load_rule_changes_recommendation() -> None:
    # 40 mph west of -100.5: Severe for 45,000 lb (load rule), High for 29,000 lb.
    heavy = serialize_plan(build_plan(inp(45_000), three_routes(), windy_west_of(-100.5, 40.0)))
    cache.clear()
    light = serialize_plan(build_plan(inp(29_000), three_routes(), windy_west_of(-100.5, 40.0)))
    heavy_cp = next(
        c for r in heavy["routes"] for c in r["checkpoints"] if c["risk"]["level"] == "SEVERE"
    )
    assert heavy_cp["risk"]["load_rule_applied"] == "35–44 mph with 45,000 lb > 40,000 lb → Severe"
    assert all(c["risk"]["level"] != "SEVERE" for r in light["routes"] for c in r["checkpoints"])
    assert any(r["metrics"]["severe_miles"] > 0 for r in heavy["routes"])
    assert all(r["metrics"]["severe_miles"] == 0 for r in light["routes"])


def test_no_safe_route() -> None:
    body = serialize_plan(
        build_plan(inp(), three_routes(), StubWeather(lambda _p, _k: (60.0, 0, 0)))
    )
    assert body["recommended"] is None
    assert body["recommendation_reason"] == "No route is safe to drive at this departure time."
    assert body["routes"][0]["reason"] == body["recommendation_reason"]


def test_fetch_failure_makes_plan_partial_and_unknown() -> None:
    def drop(p: LatLon) -> bool:
        return p[1] < -103.0

    body = serialize_plan(build_plan(inp(), three_routes(), StubWeather(calm, drop=drop)))
    assert body["status"] == "partial"
    last = body["routes"][0]["checkpoints"][-1]
    assert last["risk"]["level"] == "UNKNOWN"
    assert last["weather"]["wind_mph"] is None
    assert body["routes"][0]["metrics"]["unknown_miles"] > 0


def test_beyond_horizon_is_unknown_but_not_partial() -> None:
    class ShortSeries(StubWeather):
        def hourly(self, points, start_utc, end_utc):  # type: ignore[no-untyped-def]
            return super().hourly(points, start_utc, start_utc + timedelta(hours=3))

    body = serialize_plan(build_plan(inp(), three_routes(), ShortSeries(calm)))
    assert body["status"] == "ready"
    assert body["routes"][0]["checkpoints"][-1]["risk"]["level"] == "UNKNOWN"
    assert "LOW_FORECAST_COVERAGE" in body["routes"][0]["warnings"]


def test_coordinates_are_rounded_and_deduplicated_for_weather() -> None:
    weather = StubWeather(calm)
    build_plan(inp(interval=10), three_routes(), weather)
    assert len(weather.requested) == len(set(weather.requested))
    assert all(round(lat, 2) == lat and round(lon, 2) == lon for lat, lon in weather.requested)


def test_weather_cache_reuses_points() -> None:
    weather = StubWeather(calm)
    start, end = DEPART, DEPART + timedelta(hours=2)
    get_weather(weather, [(1.0, 2.0), (3.0, 4.0)], start, end)
    get_weather(weather, [(1.0, 2.0), (5.0, 6.0)], start, end)
    assert weather.requested == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_route_cache_reuses_routes() -> None:
    routing = three_routes()
    build_plan(inp(45_000), routing, StubWeather(calm))
    build_plan(inp(41_000), routing, StubWeather(calm))  # same 10k bucket
    assert len(routing.calls) == 1


def test_heavy_load_warning_and_fewer_routes() -> None:
    routing = StubRouting([[make_route(line(DAL, DEN, 40), 40_000, DEPART)], [], [], [], []])
    body = serialize_plan(build_plan(inp(90_000), routing, StubWeather(calm)))
    assert body["warnings"] == ["LOAD_ABOVE_80000_LB"]
    assert body["routes_found"] == 1
    assert body["recommendation_reason"] == "Only route found for this trip."


def test_routing_errors_map_to_api_errors() -> None:
    with pytest.raises(ApiError) as nf:
        build_plan(inp(), StubRouting([RouteNotFound("nope")]), StubWeather(calm))
    assert (nf.value.code, nf.value.status_code) == ("ROUTE_NOT_FOUND", 422)
    with pytest.raises(ApiError) as un:
        build_plan(inp(), StubRouting([RoutingUnavailable("down")]), StubWeather(calm))
    assert (un.value.code, un.value.status_code) == ("ROUTING_UNAVAILABLE", 503)


def test_risk_rules_payload() -> None:
    rules = risk_rules_payload()
    assert rules["scores"]["NO_TRAVEL"] == 4
    assert rules["colors"]["UNKNOWN"] == "#94A3B8"
    nt = rules["rain_in_hr"][-1]
    assert (nt["level"], nt["min"], nt["min_inclusive"]) == ("NO_TRAVEL", 1.0, False)
    wind_nt = rules["wind_mph"][-1]
    assert (wind_nt["min"], wind_nt["min_inclusive"]) == (55, True)
    assert [r["load_over_lb"] for r in rules["load_rules"]] == [0, 30_000, 40_000]
