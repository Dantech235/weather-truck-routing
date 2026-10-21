"""Checkpoint risk classification — pure, no I/O, no Django."""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import (
    LOAD_NO_TRAVEL_WIND,
    LOAD_SEVERE_WIND,
    RAIN_BANDS,
    SNOW_BANDS,
    UNKNOWN,
    WIND_BANDS,
    WIND_NO_TRAVEL_ANY_LOAD,
    Band,
    Level,
)

LevelOrUnknown = Level | str  # a Level, or the UNKNOWN sentinel


def band(value: float, bands: list[Band]) -> Level:
    """Classify a value against ordered bands. Values are not rounded; negatives clamp to 0."""
    v = max(0.0, value)
    for upper, inclusive, level in bands:
        if v < upper or (inclusive and v == upper):
            return level
    return Level.NO_TRAVEL


def apply_load_rules(level: Level, wind_mph: float, load_lb: int) -> tuple[Level, str | None]:
    """Escalate the wind level for heavy loads. Never lowers a level."""
    nt_lo, nt_hi, nt_load = LOAD_NO_TRAVEL_WIND
    sv_lo, sv_hi, sv_load = LOAD_SEVERE_WIND
    if wind_mph >= WIND_NO_TRAVEL_ANY_LOAD:
        return Level.NO_TRAVEL, f"{wind_mph:.1f} mph ≥ 55 mph → No Travel for any load"
    if nt_lo <= wind_mph < nt_hi and load_lb > nt_load:
        return (
            max(level, Level.NO_TRAVEL),
            f"45–54 mph with {load_lb:,} lb > 30,000 lb → No Travel",
        )
    if sv_lo <= wind_mph < sv_hi and load_lb > sv_load:
        return max(level, Level.SEVERE), f"35–44 mph with {load_lb:,} lb > 40,000 lb → Severe"
    return level, None


@dataclass(frozen=True)
class Assessment:
    level: LevelOrUnknown
    wind: Level | None = None
    rain: Level | None = None
    snow: Level | None = None
    drivers: list[str] = field(default_factory=list)
    load_rule_applied: str | None = None


def classify_checkpoint(
    wind_mph: float | None,
    rain_in_hr: float | None,
    snow_in_hr: float | None,
    load_lb: int,
) -> Assessment:
    """Overall level = worst of wind (after load rules), rain and snow. Missing data → UNKNOWN."""
    if wind_mph is None or rain_in_hr is None or snow_in_hr is None:
        return Assessment(level=UNKNOWN, drivers=["missing_forecast"])
    wind = band(wind_mph, WIND_BANDS)
    wind, rule = apply_load_rules(wind, wind_mph, load_lb)
    rain = band(rain_in_hr, RAIN_BANDS)
    snow = band(snow_in_hr, SNOW_BANDS)
    level = max(wind, rain, snow)
    drivers = [
        name
        for name, lv in (("wind", wind), ("rain", rain), ("snow", snow))
        if lv == level and level > Level.LOW
    ]
    return Assessment(level, wind, rain, snow, drivers, rule)


def level_name(level: LevelOrUnknown) -> str:
    return level.name if isinstance(level, Level) else UNKNOWN
