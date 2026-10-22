"""Deterministic fake providers for PROVIDERS_MODE=fake.

TEST-ONLY (Playwright e2e and local UI work without keys). The registry refuses this mode when
DEBUG is False, and production settings refuse to start with it. Nothing here is ever served as
real data.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from core.geo import (
    METERS_PER_MILE,
    LatLon,
    bearing_deg,
    cumulative_distances,
    destination_point,
    haversine_mi,
)

from .geocoding.base import Place
from .routing.base import RouteResult
from .weather.base import HourlySeries, ceil_hour, floor_hour

FAKE_PLACES = [
    Place("Dallas, TX", 32.7767, -96.797),
    Place("Denver, CO", 39.7392, -104.9903),
    Place("Amarillo, TX", 35.222, -101.8313),
    Place("Oklahoma City, OK", 35.4676, -97.5164),
    Place("Kansas City, MO", 39.0997, -94.5786),
    Place("Albuquerque, NM", 35.0844, -106.6504),
]
FAKE_SPEED_MPH = 58.0
_BOWS = (0.0, 0.12, -0.18)  # lateral bow of each fake route, as a fraction of trip distance


class FakeGeocoding:
    name = "fake"

    def search(self, query: str) -> list[Place]:
        q = query.strip().lower()
        return [p for p in FAKE_PLACES if q in p.label.lower()] or FAKE_PLACES[:1]


class FakeRouting:
    name = "fake"

    def routes(
        self,
        origin: LatLon,
        dest: LatLon,
        depart_utc: datetime,
        load_lb: int,
        max_alternatives: int,
        via: list[LatLon] | None = None,
    ) -> list[RouteResult]:
        bows = _BOWS[: 1 + max(0, min(2, max_alternatives))]
        return [self._route(origin, dest, depart_utc, bow) for bow in bows]

    @staticmethod
    def _route(origin: LatLon, dest: LatLon, depart: datetime, bow: float) -> RouteResult:
        straight = haversine_mi(origin, dest)
        brg = bearing_deg(origin, dest)
        coords: list[LatLon] = []
        n = 120
        for i in range(n + 1):
            t = i / n
            base = destination_point(origin, brg, straight * t)
            offset = bow * straight * math.sin(math.pi * t)
            coords.append(destination_point(base, brg + 90, offset) if offset else base)
        length_mi = cumulative_distances(coords)[-1] * 1.04
        travel_s = round(length_mi / FAKE_SPEED_MPH * 3600)
        guidance = [
            (length_mi * METERS_PER_MILE * k / 10, travel_s * k / 10 * (1 + 0.05 * math.sin(k)))
            for k in range(1, 10)
        ]
        return RouteResult(
            coords=coords,
            length_m=length_mi * METERS_PER_MILE,
            travel_time_s=travel_s,
            guidance=guidance,
            departure_utc=depart,
            arrival_utc=depart + timedelta(seconds=travel_s),
            provider="fake",
        )


class FakeWeather:
    """A single storm cell centred on the middle of the requested area, drifting over time.

    The straight route runs through it; bowed alternatives skirt it, so e2e tests see a mix of
    levels and a recommended route.
    """

    name = "fake"
    STORM_RADIUS_MI = 80.0

    def hourly(
        self, points: list[LatLon], start_utc: datetime, end_utc: datetime
    ) -> dict[LatLon, HourlySeries]:
        start, end = floor_hour(start_utc), ceil_hour(end_utc)
        hours = int((end - start) / timedelta(hours=1)) + 1
        unique = list(dict.fromkeys(points))
        if not unique:
            return {}
        center = (
            sum(p[0] for p in unique) / len(unique),
            sum(p[1] for p in unique) / len(unique),
        )
        out: dict[LatLon, HourlySeries] = {}
        for p in unique:
            d = haversine_mi(p, center)
            wind, rain, snow = [], [], []
            for k in range(hours):
                pulse = 0.75 + 0.25 * math.sin((start.timestamp() / 3600 + k) / 5)
                core = math.exp(-((d / self.STORM_RADIUS_MI) ** 2)) * pulse
                wind.append(9.0 + 48.0 * core)
                rain.append(0.9 * core)
                snow.append(1.6 * core if p[0] > 38.5 else 0.0)
            out[p] = HourlySeries(
                start_utc=start,
                wind_mph=wind,
                gust_mph=[w * 1.4 for w in wind],
                rain_in=rain,
                snow_in=snow,
            )
        return out
