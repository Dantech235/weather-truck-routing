"""Segment attribution and per-route risk metrics — pure, no Django.

Rules:
- A segment between two consecutive checkpoints takes the worse of its two endpoint levels.
- With one endpoint UNKNOWN, the segment takes the known level only if it is ≥ HIGH;
  otherwise the segment is UNKNOWN. Both unknown → UNKNOWN.
- Mile buckets are reported at 0.1 mi precision using largest-remainder rounding, so the
  buckets always sum exactly to the route distance rounded to 0.1 mi.
- avg_risk is the distance-weighted mean of segment scores (Level int values), excluding
  unknown miles; None if every mile is unknown.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from .engine import LevelOrUnknown
from .rules import UNKNOWN, Level

LOW_COVERAGE_THRESHOLD = 0.20
WARNING_LOW_FORECAST_COVERAGE = "LOW_FORECAST_COVERAGE"


@dataclass(frozen=True)
class Segment:
    from_mi: float
    to_mi: float
    from_frac: float
    to_frac: float
    level: LevelOrUnknown

    @property
    def length_mi(self) -> float:
        return self.to_mi - self.from_mi


@dataclass(frozen=True)
class RouteMetrics:
    label: str
    distance_mi: float
    travel_time_s: int
    no_travel_miles: float = 0.0
    severe_miles: float = 0.0
    high_miles: float = 0.0
    moderate_miles: float = 0.0
    low_miles: float = 0.0
    unknown_miles: float = 0.0
    avg_risk: float | None = None
    max_level: LevelOrUnknown = UNKNOWN
    warnings: list[str] = field(default_factory=list)


def segment_level(a: LevelOrUnknown, b: LevelOrUnknown) -> LevelOrUnknown:
    if isinstance(a, Level) and isinstance(b, Level):
        return max(a, b)
    known = a if isinstance(a, Level) else (b if isinstance(b, Level) else None)
    if known is None:
        return UNKNOWN
    return known if known >= Level.HIGH else UNKNOWN


def build_segments(
    checkpoints: Sequence[tuple[float, LevelOrUnknown]], distance_mi: float
) -> list[Segment]:
    """Build segments from (mile, level) checkpoints ordered by mile."""
    if distance_mi <= 0:
        return []
    segments: list[Segment] = []
    for (m0, l0), (m1, l1) in itertools.pairwise(checkpoints):
        if m1 <= m0:
            continue
        segments.append(
            Segment(
                from_mi=m0,
                to_mi=m1,
                from_frac=min(1.0, m0 / distance_mi),
                to_frac=min(1.0, m1 / distance_mi),
                level=segment_level(l0, l1),
            )
        )
    return segments


_BUCKETS: tuple[str, ...] = ("NO_TRAVEL", "SEVERE", "HIGH", "MODERATE", "LOW", UNKNOWN)


def _round_buckets(raw: dict[str, float], total: float) -> dict[str, float]:
    """Round to 0.1 mi with largest-remainder so the parts sum to round(total, 1)."""
    target = round(round(total, 1) * 10)  # match the displayed distance exactly
    tenths = {k: v * 10 for k, v in raw.items()}
    floors = {k: math.floor(v + 1e-9) for k, v in tenths.items()}
    remainder = target - sum(floors.values())
    order = sorted(
        (k for k in raw if raw[k] > 0), key=lambda k: tenths[k] - floors[k], reverse=True
    )
    for k in order[: max(0, remainder)]:
        floors[k] += 1
    return {k: floors[k] / 10 for k in raw}


def compute_metrics(
    label: str,
    distance_mi: float,
    travel_time_s: int,
    checkpoint_levels: Sequence[LevelOrUnknown],
    segments: Sequence[Segment],
) -> RouteMetrics:
    raw = dict.fromkeys(_BUCKETS, 0.0)
    weighted = 0.0
    known_miles = 0.0
    for seg in segments:
        length = seg.length_mi
        if isinstance(seg.level, Level):
            raw[seg.level.name] += length
            weighted += int(seg.level) * length
            known_miles += length
        else:
            raw[UNKNOWN] += length
    rounded = _round_buckets(raw, sum(raw.values()))

    known_levels = [lv for lv in checkpoint_levels if isinstance(lv, Level)]
    max_level: LevelOrUnknown = max(known_levels) if known_levels else UNKNOWN
    avg = round(weighted / known_miles, 2) if known_miles > 0 else None

    warnings: list[str] = []
    if distance_mi > 0 and raw[UNKNOWN] / distance_mi > LOW_COVERAGE_THRESHOLD:
        warnings.append(WARNING_LOW_FORECAST_COVERAGE)

    return RouteMetrics(
        label=label,
        distance_mi=round(distance_mi, 1),
        travel_time_s=travel_time_s,
        no_travel_miles=rounded["NO_TRAVEL"],
        severe_miles=rounded["SEVERE"],
        high_miles=rounded["HIGH"],
        moderate_miles=rounded["MODERATE"],
        low_miles=rounded["LOW"],
        unknown_miles=rounded[UNKNOWN],
        avg_risk=avg,
        max_level=max_level,
        warnings=warnings,
    )
