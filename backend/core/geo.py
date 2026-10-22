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


def sample_polyline(coords: Sequence[LatLon], step_mi: float) -> list[LatLon]:
    """Points every `step_mi` along the polyline, including both ends."""
    if not coords:
        return []
    cumulative = cumulative_distances(coords)
    total = cumulative[-1]
    if total == 0:
        return [coords[0]]
    n = max(1, math.ceil(total / step_mi))
    return [point_at_distance(coords, cumulative, total * i / n) for i in range(n + 1)]


class NearIndex:
    """Grid index answering "is any indexed point within `radius_mi` of p?"."""

    def __init__(self, points: Sequence[LatLon], radius_mi: float) -> None:
        self.radius_mi = radius_mi
        self._cell_lat = radius_mi / 69.0  # degrees of latitude per cell
        self._cells: dict[tuple[int, int], list[LatLon]] = {}
        for p in points:
            self._cells.setdefault(self._key(p), []).append(p)

    def _key(self, p: LatLon) -> tuple[int, int]:
        # Longitude cells use a fixed latitude-independent size and the lookup widens the
        # search by cos(lat), so cells never under-cover the radius.
        return (math.floor(p[0] / self._cell_lat), math.floor(p[1] / self._cell_lat))

    def near(self, p: LatLon) -> bool:
        ky, kx = self._key(p)
        cos_lat = max(0.05, math.cos(math.radians(p[0])))
        span_x = math.ceil(1 / cos_lat)
        for dy in (-1, 0, 1):
            for dx in range(-span_x, span_x + 1):
                for q in self._cells.get((ky + dy, kx + dx), ()):
                    if haversine_mi(p, q) <= self.radius_mi:
                        return True
        return False


def simplify(coords: Sequence[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Douglas–Peucker simplification in degree space (iterative; keeps both ends)."""
    n = len(coords)
    if n <= 2:
        return list(coords)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_deg * tolerance_deg
    while stack:
        i, j = stack.pop()
        (ay, ax), (by, bx) = coords[i], coords[j]
        dy, dx = by - ay, bx - ax
        seg2 = dx * dx + dy * dy
        worst, worst_d = -1, tol2
        for k in range(i + 1, j):
            py, px = coords[k]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > worst_d:
                worst, worst_d = k, d2
        if worst >= 0:
            keep[worst] = True
            stack.append((i, worst))
            stack.append((worst, j))
    return [c for c, k in zip(coords, keep, strict=True) if k]


def buffer_bbox(
    lines: Sequence[Sequence[LatLon]], buffer_mi: float
) -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) of all lines, expanded by `buffer_mi` on every side."""
    pts = [p for line in lines for p in line]
    if not pts:
        raise ValueError("no coordinates")
    min_lat, max_lat = min(p[0] for p in pts), max(p[0] for p in pts)
    min_lon, max_lon = min(p[1] for p in pts), max(p[1] for p in pts)
    dlat = buffer_mi / 69.0
    widest = max(abs(min_lat - dlat), abs(max_lat + dlat))
    dlon = buffer_mi / (69.172 * max(0.05, math.cos(math.radians(widest))))
    return (min_lat - dlat, min_lon - dlon, max_lat + dlat, max_lon + dlon)


def corridor_grid(
    lines: Sequence[Sequence[LatLon]],
    buffer_mi: float = 25.0,
    spacing_mi: float = 12.0,
    sample_step_mi: float = 2.0,
    max_points: int = 600,
    spacing_step_mi: float = 2.0,
) -> tuple[list[LatLon], float]:
    """Grid points within `buffer_mi` of any route (routes sampled every `sample_step_mi`).

    Spacing starts at `spacing_mi` and grows by `spacing_step_mi` until ≤ `max_points` remain.
    Returns (points, spacing_mi used).
    """
    min_lat, min_lon, max_lat, max_lon = buffer_bbox(lines, buffer_mi)
    samples = [p for line in lines for p in sample_polyline(line, sample_step_mi)]
    index = NearIndex(samples, buffer_mi)
    mid_lat = math.radians((min_lat + max_lat) / 2)
    spacing = spacing_mi
    while True:
        dlat = spacing / 69.0
        dlon = spacing / (69.172 * max(0.05, math.cos(mid_lat)))
        points: list[LatLon] = []
        lat = min_lat
        while lat <= max_lat + 1e-9:
            lon = min_lon
            while lon <= max_lon + 1e-9:
                if index.near((lat, lon)):
                    points.append((lat, lon))
                lon += dlon
            lat += dlat
        if len(points) <= max_points:
            return points, spacing
        spacing += spacing_step_mi
