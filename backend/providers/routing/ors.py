"""OpenRouteService fallback (driving-hgv, GeoJSON).

Limits (documented in README): ORS has no departure-time / live-traffic input, so ETAs assume
the requested departure with typical speeds; alternative routes are only offered for short
trips (ORS caps them at ~100 km), so longer trips rely on via-point requests for alternatives.
Coordinates are sent and returned as [lon, lat].
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from core.geo import LatLon, haversine_mi
from core.http import CircuitBreaker, ProviderHTTPError, ProviderUnavailable, request_json

from .base import LB_TO_KG, RouteNotFound, RouteResult, RoutingUnavailable

URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
ALTERNATIVES_MAX_STRAIGHT_MI = 55.0  # stay under ORS's ~100 km alternative-route limit


class OrsRouting:
    name = "ors"

    def __init__(self, client: httpx.Client, api_key: str, breaker: CircuitBreaker) -> None:
        self.client = client
        self.api_key = api_key
        self.breaker = breaker

    def routes(
        self,
        origin: LatLon,
        dest: LatLon,
        depart_utc: datetime,
        load_lb: int,
        max_alternatives: int,
        via: list[LatLon] | None = None,
    ) -> list[RouteResult]:
        if not self.api_key:
            raise RoutingUnavailable("ORS API key not configured")
        points = [origin, *(via or []), dest]
        body: dict[str, Any] = {
            "coordinates": [[lon, lat] for lat, lon in points],
            "instructions": True,
            "units": "m",
            "options": {
                "profile_params": {
                    "restrictions": {"weight": round(load_lb * LB_TO_KG / 1000, 1)},
                },
            },
        }
        if (
            max_alternatives > 0
            and not via
            and haversine_mi(origin, dest) <= (ALTERNATIVES_MAX_STRAIGHT_MI)
        ):
            body["alternative_routes"] = {
                "target_count": min(3, max_alternatives + 1),
                "weight_factor": 1.6,
                "share_factor": 0.6,
            }
        try:
            data = request_json(
                self.client, "POST", URL, json=body,
                headers={"Authorization": self.api_key}, breaker=self.breaker,
            )  # fmt: skip
        except ProviderUnavailable as exc:
            raise RoutingUnavailable(str(exc)) from exc
        except ProviderHTTPError as exc:
            if exc.response.status_code in (401, 403):
                raise RoutingUnavailable("ORS rejected the API key") from exc
            raise RouteNotFound(f"ORS could not route (HTTP {exc.response.status_code})") from exc
        routes = [parse_feature(f, depart_utc) for f in data.get("features", [])]
        if not routes:
            raise RouteNotFound("ORS returned no routes")
        return routes


def parse_feature(feature: dict[str, Any], depart_utc: datetime) -> RouteResult:
    props = feature["properties"]
    summary = props.get("summary", {})
    length_m = float(summary.get("distance", 0.0))
    travel_s = round(float(summary.get("duration", 0.0)))
    coords: list[LatLon] = [
        (float(lat), float(lon)) for lon, lat, *_ in feature["geometry"]["coordinates"]
    ]

    guidance: list[tuple[float, float]] = []
    dist = dur = 0.0
    for segment in props.get("segments", []):
        for step in segment.get("steps", []):
            dist += float(step.get("distance", 0.0))
            dur += float(step.get("duration", 0.0))
            guidance.append((dist, dur))

    return RouteResult(
        coords=coords,
        length_m=length_m,
        travel_time_s=travel_s,
        guidance=guidance,
        departure_utc=depart_utc,
        arrival_utc=depart_utc + timedelta(seconds=travel_s),
        provider="ors",
    )
