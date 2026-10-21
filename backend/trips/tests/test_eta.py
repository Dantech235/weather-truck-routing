from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trips.eta import EtaModel, etas_for_fractions, normalize_guidance

DEPART = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)


def test_normalize_adds_endpoints_and_drops_non_monotonic() -> None:
    raw = [(0.0, 0.0), (1000.0, 60.0), (900.0, 50.0), (2000.0, 40.0), (3000.0, 200.0), (9e9, 1.0)]
    # (900, 50) sorts before (1000, 60) and is kept; (2000, 40) goes back in time → dropped
    assert normalize_guidance(raw, 5000.0, 300.0) == [
        (0.0, 0.0),
        (900.0, 50.0),
        (1000.0, 60.0),
        (3000.0, 200.0),
        (5000.0, 300.0),
    ]


def test_normalize_drops_time_beyond_total() -> None:
    assert normalize_guidance([(100.0, 999.0)], 1000.0, 100.0) == [(0.0, 0.0), (1000.0, 100.0)]


def test_guidance_interpolation() -> None:
    m = EtaModel.build(10_000.0, 1000, [(2000.0, 100.0), (8000.0, 900.0)])
    assert m.method == "guidance"
    assert m.elapsed_at_offset(0.0) == 0.0
    assert m.elapsed_at_offset(1000.0) == pytest.approx(50.0)
    assert m.elapsed_at_offset(5000.0) == pytest.approx(500.0)
    assert m.elapsed_at_offset(9000.0) == pytest.approx(950.0)
    assert m.elapsed_at_offset(10_000.0) == 1000
    assert m.elapsed_at_offset(-5.0) == 0.0
    assert m.elapsed_at_offset(20_000.0) == 1000


def test_proportional_fallback() -> None:
    m = EtaModel.build(10_000.0, 1000, None)
    assert m.method == "proportional"
    assert m.elapsed_at_fraction(0.25) == pytest.approx(250.0)
    assert m.elapsed_at_fraction(1.0) == 1000
    assert EtaModel.build(10_000.0, 1000, []).method == "proportional"


def test_build_rejects_zero_length() -> None:
    with pytest.raises(ValueError, match="positive"):
        EtaModel.build(0.0, 10, None)


def test_destination_eta_equals_provider_total_exactly() -> None:
    total_s = 25_500  # 7h05
    m = EtaModel.build(693_000.0, total_s, [(100_000.0, 3000.0), (500_000.0, 18_000.0)])
    etas = etas_for_fractions(DEPART, m, [0.0, 0.3, 1.0])
    assert etas[0].eta_utc == DEPART
    assert etas[-1].eta_utc == DEPART + timedelta(seconds=total_s)
    assert etas[-1].elapsed_s == total_s
    assert {e.method for e in etas} == {"guidance"}


guidance_strategy = st.lists(
    st.tuples(st.floats(0, 1_000_000), st.floats(0, 50_000)), min_size=0, max_size=60
)


@given(
    total_m=st.floats(min_value=1_000, max_value=1_000_000),
    total_s=st.integers(min_value=60, max_value=50_000),
    raw=guidance_strategy,
    fracs=st.lists(st.floats(0, 1), min_size=1, max_size=40),
)
def test_etas_monotonic_and_final_is_total(
    total_m: float, total_s: int, raw: list[tuple[float, float]], fracs: list[float]
) -> None:
    m = EtaModel.build(total_m, total_s, raw)
    ordered = [*sorted(fracs), 1.0]
    etas = etas_for_fractions(DEPART, m, ordered)
    elapsed = [e.elapsed_s for e in etas]
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(elapsed))
    assert elapsed[-1] == total_s
    assert etas[-1].eta_utc == DEPART + timedelta(seconds=total_s)
    assert all(0 <= x <= total_s for x in elapsed)
