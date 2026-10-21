"""Geodesy helpers in miles. Coordinates are (lat, lon) tuples in degrees. Pure, no Django."""

from __future__ import annotations

import bisect
import itertools
import math
from collections.abc import Sequence

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_distances(coords: Sequence[LatLon]) -> list[float]:
    """Cumulative distance in miles at each vertex; first element is 0."""
    out = [0.0]
    for prev, cur in itertools.pairwise(coords):
        out.append(out[-1] + haversine_mi(prev, cur))
    return out


def interpolate_point(a: LatLon, b: LatLon, t: float) -> LatLon:
    """Linear interpolation of lat/lon between a (t=0) and b (t=1)."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def point_at_distance(coords: Sequence[LatLon], cumulative: Sequence[float], d: float) -> LatLon:
    """Point `d` miles along the polyline, given precomputed cumulative distances."""
    if not coords:
        raise ValueError("empty polyline")
    if d <= 0 or len(coords) == 1:
        return coords[0]
    if d >= cumulative[-1]:
        return coords[-1]
    i = bisect.bisect_right(cumulative, d)  # cumulative[i-1] <= d < cumulative[i]
    span = cumulative[i] - cumulative[i - 1]
    t = 0.0 if span == 0 else (d - cumulative[i - 1]) / span
    return interpolate_point(coords[i - 1], coords[i], t)


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """Initial great-circle bearing from a to b, degrees clockwise from north in [0, 360)."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin: LatLon, bearing: float, distance_mi: float) -> LatLon:
    """Point reached travelling `distance_mi` from origin on the given initial bearing."""
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    brg = math.radians(bearing)
    delta = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(
        math.sin(lat1) * math.cos(delta) + math.cos(lat1) * math.sin(delta) * math.cos(brg)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)
