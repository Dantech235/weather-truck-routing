from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from core.http import CircuitBreaker
from providers.weather.base import HourlySeries, ceil_hour, floor_hour, weather_at_eta
from providers.weather.openmeteo import OpenMeteoWeather, UnitError, parse_location

from .conftest import load_fixture

BASE = "https://api.open-meteo.com"
URL = f"{BASE}/v1/forecast"
T0 = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)
P1, P2 = (32.78, -96.8), (39.74, -104.99)


def series() -> HourlySeries:
    #           13:00 14:00 15:00 16:00
    return HourlySeries(
        start_utc=T0,
        wind_mph=[10.0, 20.0, 30.0, 40.0],
        gust_mph=[15.0, 25.0, 35.0, 45.0],
        rain_in=[0.0, 0.1, 0.3, 0.6],
        snow_in=[0.0, 0.0, 1.0, 2.0],
    )


# --- ETA selection semantics ---------------------------------------------------------------


def test_hour_helpers() -> None:
    t = datetime(2026, 10, 22, 14, 20, tzinfo=UTC)
    assert floor_hour(t) == datetime(2026, 10, 22, 14, tzinfo=UTC)
    assert ceil_hour(t) == datetime(2026, 10, 22, 15, tzinfo=UTC)
    assert ceil_hour(T0) == T0


def test_precip_uses_preceding_hour_label_and_wind_interpolates() -> None:
    eta = datetime(2026, 10, 22, 14, 15, tzinfo=UTC)  # inside 14:00–15:00 → labelled 15:00
    w = weather_at_eta(series(), eta)
    assert w.forecast_hour_utc == datetime(2026, 10, 22, 15, tzinfo=UTC)
    assert w.rain_in_hr == 0.3
    assert w.snow_in_hr == 1.0
    assert w.gust_mph == 35.0  # gusts are a preceding-hour max too
    assert w.wind_mph == pytest.approx(22.5)  # 20 → 30, a quarter of the way


def test_eta_exactly_on_the_hour_uses_that_hour() -> None:
    w = weather_at_eta(series(), datetime(2026, 10, 22, 15, tzinfo=UTC))
    assert w.forecast_hour_utc == datetime(2026, 10, 22, 15, tzinfo=UTC)
    assert w.wind_mph == 30.0
    assert w.rain_in_hr == 0.3


def test_beyond_horizon_is_none() -> None:
    late = weather_at_eta(series(), datetime(2026, 10, 22, 16, 30, tzinfo=UTC))
    assert late.wind_mph is None
    assert late.rain_in_hr is None
    early = weather_at_eta(series(), T0 - timedelta(minutes=30))
    assert early.wind_mph is None
    assert early.rain_in_hr == 0.0  # the 13:00 label covers 12:00–13:00


def test_missing_values_propagate() -> None:
    s = HourlySeries(T0, [10.0, None], [None, None], [None, 0.1], [0.0, 0.0])
    w = weather_at_eta(s, T0 + timedelta(minutes=30))
    assert w.wind_mph is None
    assert w.rain_in_hr == 0.1


def test_non_hour_lookup_is_none() -> None:
    s = series()
    assert s.at(s.wind_mph, T0 + timedelta(minutes=30)) is None


# --- Client --------------------------------------------------------------------------------


@respx.mock
def test_multi_location_request_and_parse(client: httpx.Client) -> None:
    route = respx.get(URL).respond(json=load_fixture("openmeteo_multi.json"))
    wx = OpenMeteoWeather(client, BASE + "/", CircuitBreaker("om"))
    out = wx.hourly([P1, P2, P1], T0 + timedelta(minutes=10), T0 + timedelta(hours=2, minutes=5))
    params = route.calls.last.request.url.params
    assert params["latitude"] == "32.78,39.74"  # de-duplicated, request order kept
    assert params["longitude"] == "-96.80,-104.99"
    assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timezone"] == "GMT"
    assert params["start_hour"] == "2026-10-22T13:00"
    assert params["end_hour"] == "2026-10-22T16:00"
    s1 = out[P1]
    assert s1.start_utc == T0
    assert s1.wind_mph == [10, 20, 30, 40]
    assert s1.rain_in == pytest.approx([0.0, 0.1, 0.3, 0.6])  # rain + showers
    assert out[P2].snow_in == [0.0, 0.5, 2.0, 3.5]


@respx.mock
def test_single_location_object_and_cm_snow_conversion(client: httpx.Client) -> None:
    respx.get(URL).respond(json=load_fixture("openmeteo_single_cm.json"))
    out = OpenMeteoWeather(client, BASE, CircuitBreaker("om")).hourly([(35.2, -101.8)], T0, T0)
    assert out[(35.2, -101.8)].snow_in == pytest.approx([0.0, 1.0, 2.0, None])


@respx.mock
def test_batches_of_100_in_parallel(client: httpx.Client) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        lats = request.url.params["latitude"].split(",")
        item = load_fixture("openmeteo_multi.json")[0]
        return httpx.Response(200, json=[item] * len(lats))

    route = respx.get(URL).mock(side_effect=respond)
    points = [(30 + i * 0.01, -97.0) for i in range(250)]
    out = OpenMeteoWeather(client, BASE, CircuitBreaker("om")).hourly(points, T0, T0)
    assert route.call_count == 3
    sizes = sorted(len(c.request.url.params["latitude"].split(",")) for c in route.calls)
    assert sizes == [50, 100, 100]
    assert len(out) == 250


@respx.mock
def test_failed_batch_drops_only_its_points(client: httpx.Client) -> None:
    item = load_fixture("openmeteo_multi.json")[0]
    calls = {"n": 0}

    def respond(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.params["latitude"].startswith("30.00"):
            return httpx.Response(500)
        return httpx.Response(200, json=[item] * len(request.url.params["latitude"].split(",")))

    respx.get(URL).mock(side_effect=respond)
    points = [(30 + i * 0.01, -97.0) for i in range(150)]
    out = OpenMeteoWeather(client, BASE, CircuitBreaker("om", threshold=99)).hourly(points, T0, T0)
    assert len(out) == 50
    assert (30.0, -97.0) not in out


@respx.mock
def test_mismatched_and_malformed_responses(client: httpx.Client) -> None:
    good = load_fixture("openmeteo_multi.json")
    bad_units = {**good[1], "hourly_units": {**good[1]["hourly_units"], "snowfall": "furlong"}}
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=good[:1]),
            httpx.Response(200, json=[good[0], bad_units]),
        ]
    )
    wx = OpenMeteoWeather(client, BASE, CircuitBreaker("om"))
    assert wx.hourly([P1, P2], T0, T0) == {}  # 1 result for 2 points → whole batch dropped
    out = wx.hourly([P1, P2], T0, T0)
    assert list(out) == [P1]  # bad unit only drops that location
    assert wx.hourly([], T0, T0) == {}


def test_parse_location_rejects_bad_input() -> None:
    item = load_fixture("openmeteo_multi.json")[0]
    with pytest.raises(UnitError):
        parse_location({**item, "hourly_units": {}})
    with pytest.raises(ValueError, match="empty"):
        parse_location({**item, "hourly": {**item["hourly"], "time": []}})
