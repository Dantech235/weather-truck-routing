from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone

from providers import registry
from providers.geocoding.base import GeocodingUnavailable, Place
from trips.models import TripPlan

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    cache.clear()
    registry.reset()
    yield
    cache.clear()
    registry.reset()


@pytest.fixture
def api() -> Client:
    return Client()


def body(**overrides: Any) -> dict[str, Any]:
    departure = (timezone.now() + timedelta(hours=2)).replace(microsecond=0)
    base: dict[str, Any] = {
        "origin": {"label": "Dallas, TX", "lat": 32.7767, "lon": -96.797},
        "destination": {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
        "departure": departure.isoformat(),
        "load_lb": 45_000,
        "interval_mi": 25,
    }
    base.update(overrides)
    return base


def post(api: Client, data: dict[str, Any]) -> Any:
    return api.post("/api/v1/plans/", data, content_type="application/json")


def test_create_and_retrieve_plan_in_fake_mode(api: Client) -> None:
    res = post(api, body())
    assert res.status_code == 201
    plan = res.json()
    assert plan["routes_found"] == 3
    assert plan["recommended"] in {"A", "B", "C"}
    assert {r["provider"] for r in plan["routes"]} == {"fake"}
    got = api.get(f"/api/v1/plans/{plan['id']}/")
    assert got.status_code == 200
    assert got.json()["routes"] == plan["routes"]


def test_plan_not_found_and_expired(api: Client) -> None:
    res = api.get("/api/v1/plans/00000000-0000-0000-0000-000000000000/")
    assert res.status_code == 404
    assert res.json() == {
        "error": {
            "code": "PLAN_NOT_FOUND",
            "message": "This plan does not exist or has expired.",
            "field": None,
        }
    }
    plan_id = post(api, body()).json()["id"]
    TripPlan.objects.filter(id=plan_id).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert api.get(f"/api/v1/plans/{plan_id}/").status_code == 404
    call_command("purge_expired_plans")
    assert TripPlan.objects.count() == 0


@pytest.mark.parametrize(
    ("overrides", "code", "field"),
    [
        ({"departure": "2020-01-01T00:00:00Z"}, "DEPARTURE_OUT_OF_RANGE", "departure"),
        (
            {"departure": (timezone.now() + timedelta(days=15)).isoformat()},
            "DEPARTURE_OUT_OF_RANGE",
            "departure",
        ),
        (
            {"destination": {"label": "Dallas", "lat": 32.7768, "lon": -96.7971}},
            "SAME_LOCATION",
            "destination",
        ),
        ({"load_lb": 0}, "VALIDATION_ERROR", "load_lb"),
        ({"load_lb": 120_001}, "VALIDATION_ERROR", "load_lb"),
        ({"interval_mi": 30}, "VALIDATION_ERROR", "interval_mi"),
        ({"origin": {"label": "x", "lat": 95, "lon": 0}}, "VALIDATION_ERROR", "origin.lat"),
    ],
)
def test_validation_errors(api: Client, overrides: dict[str, Any], code: str, field: str) -> None:
    res = post(api, body(**overrides))
    assert res.status_code == 400
    err = res.json()["error"]
    assert (err["code"], err["field"]) == (code, field)
    assert err["message"]


def test_departure_grace_window_allows_recent_past(api: Client) -> None:
    recent = (timezone.now() - timedelta(minutes=10)).isoformat()
    assert post(api, body(departure=recent)).status_code == 201


def test_heavy_load_flag(api: Client) -> None:
    assert post(api, body(load_lb=85_000)).json()["warnings"] == ["LOAD_ABOVE_80000_LB"]


def test_plan_throttle_returns_429_with_retry_after(api: Client) -> None:
    for _ in range(20):
        assert post(api, body(interval_mi=50)).status_code == 201
    res = post(api, body(interval_mi=50))
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"
    assert int(res["Retry-After"]) >= 1


def test_geocode(api: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    res = api.get("/api/v1/geocode/", {"q": "denv"})
    assert res.status_code == 200
    assert res.json() == [{"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903}]

    short = api.get("/api/v1/geocode/", {"q": "de"})
    assert short.status_code == 400
    assert short.json()["error"]["field"] == "q"

    calls: list[str] = []

    class Counting:
        name = "counting"

        def search(self, q: str) -> list[Place]:
            calls.append(q)
            return [Place("X", 1.0, 2.0)]

    monkeypatch.setattr(registry, "geocoding", lambda: Counting())
    api.get("/api/v1/geocode/", {"q": "  Austin   TX "})
    api.get("/api/v1/geocode/", {"q": "austin tx"})
    assert calls == ["austin tx"]  # normalised + cached

    class Down:
        name = "down"

        def search(self, q: str) -> list[Place]:
            raise GeocodingUnavailable("x")

    monkeypatch.setattr(registry, "geocoding", lambda: Down())
    res = api.get("/api/v1/geocode/", {"q": "boise"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "GEOCODING_UNAVAILABLE"


def test_risk_rules_and_health(api: Client) -> None:
    rules = api.get("/api/v1/risk-rules/").json()
    assert rules["levels"][-1] == "UNKNOWN"
    health = api.get("/api/health/").json()
    assert health == {"status": "ok", "providers": {"tomtom": False, "ors": False}}


def test_schema_endpoint(api: Client) -> None:
    res = api.get("/api/schema/", HTTP_ACCEPT="application/json")
    assert res.status_code == 200
    assert b"/api/v1/plans/" in res.content


def test_fake_mode_refused_without_debug() -> None:
    with override_settings(DEBUG=False, PROVIDERS_MODE="fake"), pytest.raises(ImproperlyConfigured):
        registry.routing()


@override_settings(PROVIDERS_MODE="live", TOMTOM_API_KEY="", ORS_API_KEY="")
def test_live_mode_without_keys_is_routing_unavailable(api: Client) -> None:
    res = post(api, body())
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "ROUTING_UNAVAILABLE"


@override_settings(PROVIDERS_MODE="live", TOMTOM_API_KEY="k")
def test_live_registry_builds_real_clients() -> None:
    assert [p.name for p in registry.routing().providers] == ["tomtom", "ors"]  # type: ignore[attr-defined]
    assert [p.name for p in registry.geocoding().providers] == ["tomtom", "nominatim"]  # type: ignore[attr-defined]
    assert registry.weather().name == "open-meteo"


def test_error_handler_for_unknown_route_and_method(api: Client) -> None:
    res = api.delete("/api/v1/risk-rules/")
    assert res.status_code == 405
    assert res.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_departure_is_stored_in_utc(api: Client) -> None:
    local = (datetime.now(UTC) + timedelta(hours=3)).astimezone().replace(microsecond=0)
    plan = post(api, body(departure=local.isoformat())).json()
    assert plan["inputs"]["departure_utc"].endswith("Z")
