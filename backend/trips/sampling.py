"""Checkpoint placement along a route polyline — pure, no Django.

Checkpoints are placed at mile 0, every N miles, and at the destination. If the last regular
checkpoint is less than 2 mi before the destination, it is merged into the destination.

Mile marks are expressed in the routing provider's distance (`route_length_mi`), so that
segment miles sum to the route distance shown to the user. The polyline's haversine length can
differ slightly from the provider's length; marks are mapped onto the geometry proportionally.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.geo import LatLon, cumulative_distances, point_at_distance

ALLOWED_INTERVALS_MI: tuple[int, ...] = (10, 25, 50)
MERGE_THRESHOLD_MI = 2.0


@dataclass(frozen=True)
class Checkpoint:
    index: int
    mile: float  # in route (provider) miles
    frac: float  # 0..1 along the route
    lat: float
    lon: float


def checkpoint_marks(route_length_mi: float, interval_mi: float) -> list[float]:
    """Mile marks for checkpoints, including 0 and the destination."""
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    if route_length_mi <= 0:
        return [0.0, 0.0]
    marks: list[float] = []
    k = 0
    while k * interval_mi < route_length_mi:
        marks.append(float(k * interval_mi))
        k += 1
    if len(marks) > 1 and route_length_mi - marks[-1] < MERGE_THRESHOLD_MI:
        marks.pop()
    marks.append(route_length_mi)
    return marks


def sample_checkpoints(
    coords: Sequence[LatLon],
    interval_mi: float,
    route_length_mi: float | None = None,
) -> list[Checkpoint]:
    if len(coords) < 2:
        raise ValueError("a route needs at least two coordinates")
    cumulative = cumulative_distances(coords)
    geom_len = cumulative[-1]
    length = route_length_mi if route_length_mi is not None else geom_len
    scale = geom_len / length if length > 0 else 0.0

    checkpoints: list[Checkpoint] = []
    marks = checkpoint_marks(length, interval_mi)
    for i, mark in enumerate(marks):
        is_last = i == len(marks) - 1
        if i == 0:
            lat, lon = coords[0]
        elif is_last:
            lat, lon = coords[-1]
        else:
            lat, lon = point_at_distance(coords, cumulative, mark * scale)
        frac = 1.0 if is_last else (mark / length if length > 0 else 0.0)
        checkpoints.append(Checkpoint(index=i, mile=mark, frac=frac, lat=lat, lon=lon))
    return checkpoints
