from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from risk.engine import LevelOrUnknown
from risk.metrics import (
    WARNING_LOW_FORECAST_COVERAGE,
    build_segments,
    compute_metrics,
    segment_level,
)
from risk.rules import UNKNOWN, Level

L, M, H, S, NT = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL
U = UNKNOWN


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (L, L, L),
        (L, M, M),
        (H, L, H),
        (S, NT, NT),
        (U, H, H),  # known ≥ HIGH wins over unknown
        (S, U, S),
        (NT, U, NT),
        (U, M, U),  # known < HIGH → unknown
        (L, U, U),
        (U, U, U),
    ],
)
def test_segment_level(a: LevelOrUnknown, b: LevelOrUnknown, expected: LevelOrUnknown) -> None:
    assert segment_level(a, b) == expected


def test_build_segments_worse_endpoint_and_fracs() -> None:
    segs = build_segments([(0.0, L), (25.0, H), (50.0, M), (60.0, L)], 60.0)
    assert [s.level for s in segs] == [H, H, M]
    assert [(s.from_mi, s.to_mi) for s in segs] == [(0.0, 25.0), (25.0, 50.0), (50.0, 60.0)]
    assert segs[1].from_frac == pytest.approx(25 / 60)
    assert segs[-1].to_frac == 1.0


def test_build_segments_skips_zero_length_and_handles_zero_distance() -> None:
    assert len(build_segments([(0.0, L), (0.0, H), (10.0, L)], 10.0)) == 1
    assert build_segments([(0.0, L), (0.0, L)], 0.0) == []


def test_metrics_buckets_and_avg_exclude_unknown() -> None:
    cps: list[tuple[float, LevelOrUnknown]] = [(0, L), (25, L), (50, U), (75, M), (100, M)]
    segs = build_segments(cps, 100.0)
    # segments: L(25), U(25: L+U), U(25: U+M), M(25)
    m = compute_metrics("A", 100.0, 3600, [c[1] for c in cps], segs)
    assert m.low_miles == 25.0
    assert m.unknown_miles == 50.0
    assert m.moderate_miles == 25.0
    assert m.avg_risk == 0.5  # (0*25 + 1*25) / 50 known miles
    assert m.max_level is M
    assert m.warnings == [WARNING_LOW_FORECAST_COVERAGE]


def test_metrics_all_unknown() -> None:
    segs = build_segments([(0, U), (10, U)], 10.0)
    m = compute_metrics("A", 10.0, 600, [U, U], segs)
    assert m.avg_risk is None
    assert m.max_level == UNKNOWN
    assert m.unknown_miles == 10.0


def test_metrics_coverage_warning_threshold_is_strictly_above_20_percent() -> None:
    cps: list[tuple[float, LevelOrUnknown]] = [(0, L), (80, L), (90, U), (100, U)]
    m = compute_metrics("A", 100.0, 1, [c[1] for c in cps], build_segments(cps, 100.0))
    assert m.unknown_miles == 20.0
    assert m.warnings == []


def test_metrics_max_level_is_worst_checkpoint() -> None:
    cps: list[tuple[float, LevelOrUnknown]] = [(0, L), (10, S), (20, U)]
    m = compute_metrics("A", 20.0, 1, [c[1] for c in cps], build_segments(cps, 20.0))
    assert m.max_level is S
    assert m.severe_miles == 20.0  # S + U → S on second segment


def test_avg_is_distance_weighted() -> None:
    cps: list[tuple[float, LevelOrUnknown]] = [(0, H), (10, L), (100, L)]
    m = compute_metrics("A", 100.0, 1, [c[1] for c in cps], build_segments(cps, 100.0))
    assert m.avg_risk == 0.2  # (2*10 + 0*90) / 100


levels: st.SearchStrategy[LevelOrUnknown] = st.sampled_from([L, M, H, S, NT, U])


@given(
    gaps=st.lists(st.floats(min_value=0.05, max_value=60.0), min_size=1, max_size=40),
    lvls=st.data(),
)
def test_buckets_sum_to_distance(gaps: list[float], lvls: st.DataObject) -> None:
    miles = [0.0]
    for g in gaps:
        miles.append(miles[-1] + g)
    total = miles[-1]
    cps: list[tuple[float, LevelOrUnknown]] = [(mi, lvls.draw(levels)) for mi in miles]
    m = compute_metrics("A", total, 1, [c[1] for c in cps], build_segments(cps, total))
    parts = (
        m.no_travel_miles
        + m.severe_miles
        + m.high_miles
        + m.moderate_miles
        + m.low_miles
        + m.unknown_miles
    )
    assert abs(parts - total) <= 0.1 + 1e-9
    assert round(parts, 1) == round(total, 1)
    if m.avg_risk is not None:
        assert 0.0 <= m.avg_risk <= 4.0
