"""Risk thresholds and load rules. Pure data — do not edit without product sign-off.

Edge resolution: each band includes its lower bound and excludes its upper bound, except that
rain and snow No Travel begin *strictly above* 1.00 / 3.00 in/hr, so Severe includes 1.00 / 3.00.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class Level(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


UNKNOWN: Final = "UNKNOWN"  # not a Level: excluded from averages, counted separately

LEVEL_COLORS: Final[dict[str, str]] = {
    "LOW": "#22C55E",
    "MODERATE": "#EAB308",
    "HIGH": "#F97316",
    "SEVERE": "#DC2626",
    "NO_TRAVEL": "#4C1D95",
    "UNKNOWN": "#94A3B8",
}

# (upper_bound, upper_inclusive, level). Anything beyond the last band is NO_TRAVEL.
Band = tuple[float, bool, Level]

WIND_BANDS: Final[list[Band]] = [
    (25, False, Level.LOW),
    (35, False, Level.MODERATE),
    (45, False, Level.HIGH),
    (55, False, Level.SEVERE),
]
RAIN_BANDS: Final[list[Band]] = [
    (0.10, False, Level.LOW),
    (0.25, False, Level.MODERATE),
    (0.50, False, Level.HIGH),
    (1.00, True, Level.SEVERE),
]
SNOW_BANDS: Final[list[Band]] = [
    (0.5, False, Level.LOW),
    (1.0, False, Level.MODERATE),
    (2.0, False, Level.HIGH),
    (3.0, True, Level.SEVERE),
]

LOAD_NO_TRAVEL_WIND: Final = (45.0, 55.0, 30_000)  # 45 <= w < 55 and load > 30,000 -> NO_TRAVEL
LOAD_SEVERE_WIND: Final = (35.0, 45.0, 40_000)  # 35 <= w < 45 and load > 40,000 -> SEVERE
WIND_NO_TRAVEL_ANY_LOAD: Final = 55.0
