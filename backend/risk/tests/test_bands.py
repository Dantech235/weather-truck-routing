"""Every threshold edge in all three tables: edge − 0.01, edge, edge + 0.01."""

from __future__ import annotations

import pytest

from risk.engine import band
from risk.rules import RAIN_BANDS, SNOW_BANDS, WIND_BANDS, Level

L, M, H, S, NT = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL

WIND_CASES = [
    (24.99, L), (25.0, M), (25.01, M),
    (34.99, M), (35.0, H), (35.01, H),
    (44.99, H), (45.0, S), (45.01, S),
    (54.99, S), (55.0, NT), (55.01, NT),
]  # fmt: skip

RAIN_CASES = [
    (0.09, L), (0.10, M), (0.11, M),
    (0.24, M), (0.25, H), (0.26, H),
    (0.49, H), (0.50, S), (0.51, S),
    (0.99, S), (1.00, S), (1.01, NT),
]  # fmt: skip

SNOW_CASES = [
    (0.49, L), (0.5, M), (0.51, M),
    (0.99, M), (1.0, H), (1.01, H),
    (1.99, H), (2.0, S), (2.01, S),
    (2.99, S), (3.0, S), (3.01, NT),
]  # fmt: skip


@pytest.mark.parametrize(("mph", "expected"), WIND_CASES)
def test_wind_edges(mph: float, expected: Level) -> None:
    assert band(mph, WIND_BANDS) is expected


@pytest.mark.parametrize(("in_hr", "expected"), RAIN_CASES)
def test_rain_edges(in_hr: float, expected: Level) -> None:
    assert band(in_hr, RAIN_BANDS) is expected


@pytest.mark.parametrize(("in_hr", "expected"), SNOW_CASES)
def test_snow_edges(in_hr: float, expected: Level) -> None:
    assert band(in_hr, SNOW_BANDS) is expected


@pytest.mark.parametrize(
    "bands", [WIND_BANDS, RAIN_BANDS, SNOW_BANDS], ids=["wind", "rain", "snow"]
)
@pytest.mark.parametrize("value", [0.0, -0.01, -5.0, -1000.0])
def test_zero_and_negative_are_low(bands: list[tuple[float, bool, Level]], value: float) -> None:
    assert band(value, bands) is Level.LOW


def test_values_are_not_rounded() -> None:
    assert band(34.6, WIND_BANDS) is Level.MODERATE
    assert band(0.0999, RAIN_BANDS) is Level.LOW
    assert band(1.0001, RAIN_BANDS) is Level.NO_TRAVEL
    assert band(3.0001, SNOW_BANDS) is Level.NO_TRAVEL


@pytest.mark.parametrize(
    ("bands", "value"),
    [(WIND_BANDS, 200.0), (RAIN_BANDS, 10.0), (SNOW_BANDS, 12.0)],
    ids=["wind", "rain", "snow"],
)
def test_extreme_values_are_no_travel(bands: list[tuple[float, bool, Level]], value: float) -> None:
    assert band(value, bands) is Level.NO_TRAVEL
