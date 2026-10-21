from __future__ import annotations

import pytest

from risk.engine import apply_load_rules, classify_checkpoint, level_name
from risk.rules import UNKNOWN, Level

L, M, H, S, NT = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


# --- Load rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wind", "load", "expected", "rule_applied"),
    [
        (50.0, 29_999, S, False),
        (50.0, 30_000, S, False),  # strict ">" 30,000
        (50.0, 30_001, NT, True),
        (40.0, 39_999, H, False),
        (40.0, 40_000, H, False),  # strict ">" 40,000
        (40.0, 40_001, S, True),
        (55.0, 1, NT, True),
        (60.0, 1, NT, True),
        (34.99, 80_000, M, False),  # below every load band → unchanged
        (35.0, 40_001, S, True),  # lower edge of 35–44 band is inclusive
        (44.99, 40_001, S, True),
        (45.0, 30_001, NT, True),  # lower edge of 45–54 band is inclusive
        (54.99, 30_001, NT, True),
        (45.0, 30_000, S, False),
        (24.0, 120_000, L, False),
    ],
)
def test_load_rules(wind: float, load: int, expected: Level, rule_applied: bool) -> None:
    a = classify_checkpoint(wind, 0.0, 0.0, load)
    assert a.level is expected
    assert a.wind is expected
    assert (a.load_rule_applied is not None) is rule_applied


def test_load_rule_text_is_verbatim() -> None:
    assert classify_checkpoint(50.0, 0, 0, 45_000).load_rule_applied == (
        "45–54 mph with 45,000 lb > 30,000 lb → No Travel"
    )
    assert classify_checkpoint(40.0, 0, 0, 45_000).load_rule_applied == (
        "35–44 mph with 45,000 lb > 40,000 lb → Severe"
    )
    assert classify_checkpoint(56.25, 0, 0, 1).load_rule_applied == (
        "56.2 mph ≥ 55 mph → No Travel for any load"
    )


@pytest.mark.parametrize("start", list(Level))
@pytest.mark.parametrize(("wind", "load"), [(40.0, 45_000), (50.0, 45_000), (10.0, 45_000)])
def test_apply_load_rules_never_lowers(start: Level, wind: float, load: int) -> None:
    result, _ = apply_load_rules(start, wind, load)
    assert result >= start


def test_load_rule_never_lowers_rain_driven_level() -> None:
    a = classify_checkpoint(40.0, 1.5, 0.0, 45_000)  # wind → Severe via load, rain → No Travel
    assert a.level is NT
    assert a.wind is S
    assert a.rain is NT
    assert a.drivers == ["rain"]


def test_load_rule_never_lowers_snow_driven_level() -> None:
    a = classify_checkpoint(36.0, 0.0, 3.5, 45_000)
    assert a.level is NT
    assert a.drivers == ["snow"]


# --- Combination and drivers ---------------------------------------------------------------


def test_overall_is_worst_component() -> None:
    a = classify_checkpoint(30.0, 0.3, 0.6, 10_000)
    assert (a.wind, a.rain, a.snow) == (M, H, M)
    assert a.level is H
    assert a.drivers == ["rain"]


def test_drivers_list_all_tied_components() -> None:
    a = classify_checkpoint(40.0, 0.30, 1.5, 10_000)
    assert a.level is H
    assert a.drivers == ["wind", "rain", "snow"]


def test_all_low_has_no_drivers() -> None:
    a = classify_checkpoint(5.0, 0.0, 0.0, 80_000)
    assert a.level is L
    assert a.drivers == []
    assert a.load_rule_applied is None


def test_load_driven_wind_is_named_driver() -> None:
    a = classify_checkpoint(40.0, 0.0, 0.0, 45_000)
    assert a.level is S
    assert a.drivers == ["wind"]


@pytest.mark.parametrize(
    ("wind", "rain", "snow"),
    [(None, 0.0, 0.0), (10.0, None, 0.0), (10.0, 0.0, None), (None, None, None)],
)
def test_missing_any_component_is_unknown(
    wind: float | None, rain: float | None, snow: float | None
) -> None:
    a = classify_checkpoint(wind, rain, snow, 45_000)
    assert a.level == UNKNOWN
    assert a.drivers == ["missing_forecast"]
    assert a.wind is None
    assert a.rain is None
    assert a.snow is None


def test_unknown_is_not_low() -> None:
    assert classify_checkpoint(None, 0.0, 0.0, 1).level != Level.LOW


def test_level_name() -> None:
    assert level_name(Level.NO_TRAVEL) == "NO_TRAVEL"
    assert level_name(UNKNOWN) == "UNKNOWN"
