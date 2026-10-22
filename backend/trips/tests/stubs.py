"""Test doubles for providers (tests only)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TypedDict

from core.geo import METERS_PER_MILE, LatLon, cumulative_distances
from providers.routing.base import RouteResult
from providers.weather.base import HourlySeries, ceil_hour, floor_hour

DAL: LatLon = (32.7767, -96.797)
DEN: LatLon = (39.7392, -104.9903)


def line(a: LatLon, b: LatLon, n: int = 50, bow_deg: float = 0.0) -> list[LatLon]:
    """Straight a→b line, optionally bowed sideways by up to `bow_deg` degrees of longitude."""
    out: list[LatLon] = []
    for i in range(n + 1):
        t = i / n
        bow = bow_deg * 4 * t * (1 - t)
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t + bow))
    return out


def make_route(
    coords: list[LatLon], travel_s: int, depart: datetime, provider: str = "stub"
) -> RouteResult:
    length_m = cumulative_distances(coords)[-1] * METERS_PER_MILE
    return RouteResult(
        coords=coords,
        length_m=length_m,
        travel_time_s=travel_s,
        guidance=[(length_m / 2, travel_s / 2)],
        departure_utc=depart,
        arrival_utc=depart + timedelta(seconds=travel_s),
        provider=provider,
    )


class Call(TypedDict):
    max_alternatives: int
    via: list[LatLon] | None


class StubRouting:
    name = "stub"

    def __init__(self, responses: list[list[RouteResult] | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[Call] = []

    def routes(
        self,
        origin: LatLon,
        dest: LatLon,
        depart_utc: datetime,
        load_lb: int,
        max_alternatives: int,
        via: list[LatLon] | None = None,
    ) -> list[RouteResult]:
        self.calls.append({"max_alternatives": max_alternatives, "via": via})
        result = self.responses.pop(0) if self.responses else []
        if isinstance(result, Exception):
            raise result
        return result


WeatherFn = Callable[[LatLon, int], tuple[float, float, float]]  # (wind, rain, snow) at hour k


class StubWeather:
    name = "stub"

    def __init__(self, fn: WeatherFn, drop: Callable[[LatLon], bool] | None = None) -> None:
        self.fn = fn
        self.drop = drop or (lambda _p: False)
        self.requested: list[LatLon] = []

    def hourly(
        self, points: list[LatLon], start_utc: datetime, end_utc: datetime
    ) -> dict[LatLon, HourlySeries]:
        self.requested.extend(points)
        start, end = floor_hour(start_utc), ceil_hour(end_utc)
        hours = int((end - start) / timedelta(hours=1)) + 1
        out: dict[LatLon, HourlySeries] = {}
        for p in points:
            if self.drop(p):
                continue
            vals = [self.fn(p, k) for k in range(hours)]
            out[p] = HourlySeries(
                start_utc=start,
                wind_mph=[v[0] for v in vals],
                gust_mph=[v[0] * 1.3 for v in vals],
                rain_in=[v[1] for v in vals],
                snow_in=[v[2] for v in vals],
            )
        return out


def calm(_p: LatLon, _k: int) -> tuple[float, float, float]:
    return (5.0, 0.0, 0.0)
