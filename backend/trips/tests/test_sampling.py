from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.geo import cumulative_distances, haversine_mi
from trips.sampling import checkpoint_marks, sample_checkpoints

# A straight north-south line: 1° of latitude ≈ 69.09 mi.
NORTH = [(30.0, -97.0), (31.0, -97.0), (32.0, -97.0), (33.0, -97.0)]


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_marks_spacing(interval: int) -> None:
    marks = checkpoint_marks(207.0, interval)
    assert marks[0] == 0.0
    assert marks[-1] == 207.0
    inner = marks[1:-1]
    assert inner == [interval * k for k in range(1, len(inner) + 1)]
    assert 207.0 - inner[-1] >= 2.0


def test_marks_merge_when_last_regular_is_within_2_mi() -> None:
    assert checkpoint_marks(51.5, 25) == [0.0, 25.0, 51.5]  # 50 dropped (1.5 mi before dest)
    assert checkpoint_marks(52.0, 25) == [0.0, 25.0, 50.0, 52.0]  # exactly 2 mi: kept


def test_marks_exact_multiple() -> None:
    assert checkpoint_marks(50.0, 25) == [0.0, 25.0, 50.0]


def test_short_trip_has_two_checkpoints() -> None:
    assert checkpoint_marks(8.0, 10) == [0.0, 8.0]
    assert checkpoint_marks(1.5, 50) == [0.0, 1.5]


def test_marks_degenerate() -> None:
    assert checkpoint_marks(0.0, 10) == [0.0, 0.0]
    with pytest.raises(ValueError, match="positive"):
        checkpoint_marks(10.0, 0)


def test_sample_places_points_by_interpolation() -> None:
    cps = sample_checkpoints(NORTH, 25)
    total = cumulative_distances(NORTH)[-1]
    assert cps[0].lat == 30.0
    assert cps[-1].lat == 33.0
    assert cps[-1].mile == pytest.approx(total)
    assert cps[-1].frac == 1.0
    # Mark 25 is on the first vertex segment: lat ≈ 30 + 25/69.09
    assert cps[1].lat == pytest.approx(30.0 + 25 / haversine_mi((30, -97), (31, -97)), abs=1e-6)
    assert cps[1].lon == pytest.approx(-97.0)
    assert [c.index for c in cps] == list(range(len(cps)))


def test_sample_uses_provider_length_for_marks() -> None:
    geom = cumulative_distances(NORTH)[-1]
    provider_len = geom * 1.02  # provider says the road is 2% longer than the polyline
    cps = sample_checkpoints(NORTH, 50, route_length_mi=provider_len)
    assert cps[1].mile == 50.0
    assert cps[1].frac == pytest.approx(50.0 / provider_len)
    assert cps[-1].mile == provider_len
    # Placed at the same fraction along the geometry
    placed = haversine_mi(NORTH[0], (cps[1].lat, cps[1].lon))
    assert placed / geom == pytest.approx(cps[1].frac, rel=1e-6)


def test_sample_rejects_single_point() -> None:
    with pytest.raises(ValueError, match="two coordinates"):
        sample_checkpoints([(30.0, -97.0)], 10)


@given(
    length=st.floats(min_value=0.5, max_value=3000.0),
    interval=st.sampled_from([10, 25, 50]),
)
def test_marks_properties(length: float, interval: int) -> None:
    marks = checkpoint_marks(length, interval)
    assert marks[0] == 0.0
    assert marks[-1] == length
    assert all(b > a for a, b in itertools.pairwise(marks))
    assert all(m % interval == 0 for m in marks[:-1])
    if len(marks) > 2:
        assert length - marks[-2] >= 2.0
    assert len(marks) >= 2
