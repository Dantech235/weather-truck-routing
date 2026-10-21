from __future__ import annotations

import pytest

from core.geo import (
    bearing_deg,
    cumulative_distances,
    destination_point,
    haversine_mi,
    interpolate_point,
    point_at_distance,
)


def test_haversine_known_distance() -> None:
    # Dallas → Denver great-circle ≈ 663 mi
    assert haversine_mi((32.7767, -96.797), (39.7392, -104.9903)) == pytest.approx(663, abs=3)
    assert haversine_mi((10.0, 10.0), (10.0, 10.0)) == 0.0


def test_cumulative_and_point_at_distance() -> None:
    coords = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = cumulative_distances(coords)
    assert cum[0] == 0.0
    assert cum[2] == pytest.approx(2 * cum[1])
    mid = point_at_distance(coords, cum, cum[1] * 1.5)
    assert mid == pytest.approx((0.0, 1.5))
    assert point_at_distance(coords, cum, -1) == coords[0]
    assert point_at_distance(coords, cum, 1e9) == coords[-1]
    assert point_at_distance(coords, cum, cum[1]) == pytest.approx((0.0, 1.0))


def test_point_at_distance_edge_cases() -> None:
    assert point_at_distance([(1.0, 1.0)], [0.0], 5.0) == (1.0, 1.0)
    dup = [(0.0, 0.0), (0.0, 0.0), (0.0, 1.0)]
    assert point_at_distance(dup, cumulative_distances(dup), 10.0) == pytest.approx(
        (0.0, 0.145), abs=1e-3
    )
    with pytest.raises(ValueError, match="empty"):
        point_at_distance([], [], 1.0)


def test_interpolate_point() -> None:
    assert interpolate_point((0.0, 0.0), (10.0, 20.0), 0.25) == (2.5, 5.0)


def test_bearing_and_destination_round_trip() -> None:
    assert bearing_deg((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)
    assert bearing_deg((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)
    start = (32.7767, -96.797)
    end = destination_point(start, 300.0, 100.0)
    assert haversine_mi(start, end) == pytest.approx(100.0, rel=1e-6)
    assert bearing_deg(start, end) == pytest.approx(300.0, abs=1e-6)
