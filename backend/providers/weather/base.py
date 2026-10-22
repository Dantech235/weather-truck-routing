"""Weather series types and ETA selection with Open-Meteo hour semantics. Pure, no Django.

- wind_speed_10m is instantaneous at the timestamp → linear interpolation between
  floor(ETA) and ceil(ETA).
- rain, showers, snowfall and wind_gusts_10m describe the *preceding* hour (the value at 15:00
  covers 14:00–15:00), so the hour containing the ETA is labelled ceil(ETA); an ETA exactly on
  the hour uses that hour. That label is reported as forecast_hour_utc.
- An hour outside the returned series yields None for that field (→ UNKNOWN risk).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from core.geo import LatLon

HOUR = timedelta(hours=1)


def floor_hour(t: datetime) -> datetime:
    return t.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def ceil_hour(t: datetime) -> datetime:
    f = floor_hour(t)
    return f if f == t.astimezone(UTC) else f + HOUR


@dataclass(frozen=True)
class HourlySeries:
    start_utc: datetime  # first hour (on the hour, UTC)
    wind_mph: Sequence[float | None]
    gust_mph: Sequence[float | None]
    rain_in: Sequence[float | None]  # rain + showers, preceding-hour sum, inches
    snow_in: Sequence[float | None]  # snowfall, preceding-hour sum, inches

    def _index(self, hour: datetime) -> int | None:
        k = (hour - self.start_utc) / HOUR
        if k != math.floor(k):
            return None
        i = int(k)
        return i if 0 <= i < len(self.wind_mph) else None

    def at(self, values: Sequence[float | None], hour: datetime) -> float | None:
        i = self._index(hour)
        return None if i is None else values[i]


@dataclass(frozen=True)
class WeatherAtEta:
    wind_mph: float | None
    gust_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None
    forecast_hour_utc: datetime


def weather_at_eta(series: HourlySeries, eta: datetime) -> WeatherAtEta:
    eta = eta.astimezone(UTC)
    h0, h1 = floor_hour(eta), ceil_hour(eta)
    w0, w1 = series.at(series.wind_mph, h0), series.at(series.wind_mph, h1)
    if w0 is None or w1 is None:
        wind: float | None = None
    elif h0 == h1:
        wind = w0
    else:
        f = (eta - h0) / HOUR
        wind = w0 + (w1 - w0) * f
    return WeatherAtEta(
        wind_mph=wind,
        gust_mph=series.at(series.gust_mph, h1),
        rain_in_hr=series.at(series.rain_in, h1),
        snow_in_hr=series.at(series.snow_in, h1),
        forecast_hour_utc=h1,
    )


class WeatherProvider(Protocol):
    name: str

    def hourly(
        self, points: list[LatLon], start_utc: datetime, end_utc: datetime
    ) -> dict[LatLon, HourlySeries]:
        """Series for each point that was fetched successfully; failed points are omitted."""
        ...
