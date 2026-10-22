"""Weather-risk heatmap along the trip corridor for hours 0–48 — pure, no Django.

Grid: merged route bounding box + 25 mi; keep points within 25 mi of the nearest route point
(routes sampled every 2 mi); spacing starts at 12 mi and grows by 2 mi until ≤ 600 points.

Hour k (0–48) is departure-hour floor + k. Wind is instantaneous at hour k; rain and snow are
preceding-hour sums, so hour k uses the value labelled k + 1 (covering k → k+1). Each point/hour
is classified with the plan's load via `classify_checkpoint`. Unknown values are -1.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from core.geo import LatLon, corridor_grid
from providers.weather.base import HOUR, HourlySeries, floor_hour
from risk.engine import classify_checkpoint
from risk.rules import Level

HOURS = 49
UNKNOWN_VALUE = -1

FetchWeather = Callable[[list[LatLon], datetime, datetime], dict[LatLon, HourlySeries]]


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _round(v: float | None, nd: int) -> float:
    return UNKNOWN_VALUE if v is None else round(v, nd)


def build_heatmap(
    lines: Sequence[Sequence[LatLon]],
    departure_utc: datetime,
    load_lb: int,
    fetch: FetchWeather,
) -> dict[str, Any]:
    grid, spacing = corridor_grid(lines)
    points = list(dict.fromkeys((round(lat, 2), round(lon, 2)) for lat, lon in grid))
    start = floor_hour(departure_utc)
    end = start + HOUR * HOURS  # rain/snow for hour 48 are labelled hour 49
    series = fetch(points, start, end) if points else {}

    risk: list[list[int]] = []
    wind: list[list[float]] = []
    rain: list[list[float]] = []
    snow: list[list[float]] = []
    for p in points:
        s = series.get(p)
        r_row: list[int] = []
        w_row: list[float] = []
        rn_row: list[float] = []
        sn_row: list[float] = []
        for k in range(HOURS):
            h = start + HOUR * k
            w = s.at(s.wind_mph, h) if s else None
            rn = s.at(s.rain_in, h + HOUR) if s else None
            sn = s.at(s.snow_in, h + HOUR) if s else None
            level = classify_checkpoint(w, rn, sn, load_lb).level
            r_row.append(int(level) if isinstance(level, Level) else UNKNOWN_VALUE)
            w_row.append(_round(w, 1))
            rn_row.append(_round(rn, 3))
            sn_row.append(_round(sn, 3))
        risk.append(r_row)
        wind.append(w_row)
        rain.append(rn_row)
        snow.append(sn_row)

    return {
        "points": [[lon, lat] for lat, lon in points],
        "hours": [_iso(start + HOUR * k) for k in range(HOURS)],
        "spacing_mi": spacing,
        "risk": risk,
        "wind": wind,
        "rain": rain,
        "snow": snow,
    }
