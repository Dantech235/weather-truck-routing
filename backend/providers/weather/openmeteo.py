"""Open-Meteo Forecast API client.

Docs: https://open-meteo.com/en/docs
- Requests hourly wind_speed_10m, wind_gusts_10m, rain, showers, snowfall with
  wind_speed_unit=mph, precipitation_unit=inch, timezone=GMT, timeformat=unixtime and an
  explicit start_hour/end_hour window (yyyy-mm-ddThh:mm, UTC).
- `rain` is large-scale rain only; convective rain is reported as `showers`, so the rain rate
  used for classification is rain + showers (documented deviation from the original brief).
- Snowfall is natively centimetres; units are read from `hourly_units` and converted, so a
  value is never misread whatever unit the API returns.
- Multi-location requests return a list in request order; a single location returns an object.
- ≤ 100 locations per request, batches run in parallel (max 4 workers). A failed batch only
  drops its own points (the plan becomes `partial`).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import httpx

from core.geo import LatLon
from core.http import CircuitBreaker, ProviderHTTPError, ProviderUnavailable, request_json

from .base import HourlySeries, ceil_hour, floor_hour

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_WORKERS = 4
HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"

WIND_TO_MPH = {"mp/h": 1.0, "mph": 1.0, "km/h": 0.621371, "m/s": 2.236936, "kn": 1.150779}
PRECIP_TO_IN = {"inch": 1.0, "in": 1.0, "mm": 1 / 25.4, "cm": 1 / 2.54}


class UnitError(ValueError):
    pass


class OpenMeteoWeather:
    name = "open-meteo"

    def __init__(self, client: httpx.Client, base_url: str, breaker: CircuitBreaker) -> None:
        self.client = client
        self.url = base_url.rstrip("/") + "/v1/forecast"
        self.breaker = breaker

    def hourly(
        self, points: list[LatLon], start_utc: datetime, end_utc: datetime
    ) -> dict[LatLon, HourlySeries]:
        unique = list(dict.fromkeys(points))
        batches = [unique[i : i + BATCH_SIZE] for i in range(0, len(unique), BATCH_SIZE)]
        start, end = floor_hour(start_utc), ceil_hour(end_utc)
        out: dict[LatLon, HourlySeries] = {}
        if not batches:
            return out
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
            for result in pool.map(lambda b: self._fetch_batch(b, start, end), batches):
                out.update(result)
        return out

    def _fetch_batch(
        self, batch: list[LatLon], start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        params = {
            "latitude": ",".join(f"{lat:.2f}" for lat, _ in batch),
            "longitude": ",".join(f"{lon:.2f}" for _, lon in batch),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
        }
        try:
            data = request_json(self.client, "GET", self.url, params=params, breaker=self.breaker)
        except (ProviderUnavailable, ProviderHTTPError) as exc:
            logger.warning("weather_batch_failed size=%d error=%s", len(batch), exc)
            return {}
        items = data if isinstance(data, list) else [data]
        if len(items) != len(batch):
            logger.warning("weather_batch_mismatch expected=%d got=%d", len(batch), len(items))
            return {}
        out: dict[LatLon, HourlySeries] = {}
        for point, item in zip(batch, items, strict=True):
            try:
                out[point] = parse_location(item)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("weather_parse_failed point=%s error=%s", point, exc)
        return out


def _scale(values: list[Any], factor: float) -> list[float | None]:
    return [None if v is None else float(v) * factor for v in values]


def _factor(units: dict[str, str], key: str, table: dict[str, float]) -> float:
    unit = units.get(key)
    if unit not in table:
        raise UnitError(f"unexpected unit {unit!r} for {key}")
    return table[unit]


def parse_location(item: dict[str, Any]) -> HourlySeries:
    hourly = item["hourly"]
    units: dict[str, str] = item.get("hourly_units", {})
    times = [datetime.fromtimestamp(int(t), tz=UTC) for t in hourly["time"]]
    if not times:
        raise ValueError("empty hourly series")
    wind_f = _factor(units, "wind_speed_10m", WIND_TO_MPH)
    gust_f = _factor(units, "wind_gusts_10m", WIND_TO_MPH)
    rain_f = _factor(units, "rain", PRECIP_TO_IN)
    showers_f = _factor(units, "showers", PRECIP_TO_IN)
    snow_f = _factor(units, "snowfall", PRECIP_TO_IN)

    rain = _scale(hourly["rain"], rain_f)
    showers = _scale(hourly["showers"], showers_f)
    rain_total = [
        None if r is None or s is None else r + s for r, s in zip(rain, showers, strict=True)
    ]
    return HourlySeries(
        start_utc=times[0],
        wind_mph=_scale(hourly["wind_speed_10m"], wind_f),
        gust_mph=_scale(hourly["wind_gusts_10m"], gust_f),
        rain_in=rain_total,
        snow_in=_scale(hourly["snowfall"], snow_f),
    )
