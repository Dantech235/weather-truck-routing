"""TomTom Routing API (Calculate Route, travelMode=truck).

Docs: https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route
- vehicleWeight is in kilograms; maxAlternatives is 0–5; departAt is RFC 3339 and must be in
  the future, so a departure at or before "now" is sent without departAt (TomTom default: now).
- Errors: {"formatVersion", "detailedError": {"code", "message"}}; auth/quota errors are XML,
  so only the HTTP status is relied on for those.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from core.geo import LatLon
from core.http import CircuitBreaker, ProviderHTTPError, ProviderUnavailable, request_json

from .base import LB_TO_KG, RouteNotFound, RouteResult, RoutingUnavailable

BASE_URL = "https://api.tomtom.com/routing/1/calculateRoute"


def _now() -> datetime:
    return datetime.now(UTC)


class TomTomRouting:
    name = "tomtom"

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        breaker: CircuitBreaker,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.breaker = breaker
        self.now = now

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
            raise RoutingUnavailable("TomTom API key not configured")
        points = [origin, *(via or []), dest]
        locations = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in points)
        params: dict[str, str | int] = {
            "key": self.api_key,
            "travelMode": "truck",
            "vehicleWeight": round(load_lb * LB_TO_KG),
            "maxAlternatives": max(0, min(5, max_alternatives)),
            "traffic": "true",
            "routeRepresentation": "polyline",
            "instructionsType": "coded",
            "computeTravelTimeFor": "all",
        }
        if depart_utc > self.now() + timedelta(minutes=1):
            params["departAt"] = depart_utc.astimezone(UTC).isoformat(timespec="seconds")
        try:
            data = request_json(
                self.client, "GET", f"{BASE_URL}/{locations}/json", params=params,
                breaker=self.breaker,
            )  # fmt: skip
        except ProviderUnavailable as exc:
            raise RoutingUnavailable(str(exc)) from exc
        except ProviderHTTPError as exc:
            if exc.response.status_code in (401, 403):
                raise RoutingUnavailable("TomTom rejected the API key") from exc
            raise RouteNotFound(_error_message(exc.response)) from exc
        routes = [parse_route(r, depart_utc) for r in data.get("routes", [])]
        if not routes:
            raise RouteNotFound("TomTom returned no routes")
        return routes


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"TomTom HTTP {response.status_code}"
    detail = body.get("detailedError") or body.get("error") or {}
    return str(detail.get("message") or detail.get("description") or "No route found")


def _parse_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value).astimezone(UTC)


def parse_route(route: dict[str, Any], requested_departure: datetime) -> RouteResult:
    summary = route["summary"]
    length_m = float(summary["lengthInMeters"])
    travel_s = int(summary["travelTimeInSeconds"])
    departure = _parse_time(summary.get("departureTime"), requested_departure)
    arrival = _parse_time(summary.get("arrivalTime"), departure + timedelta(seconds=travel_s))

    coords: list[LatLon] = []
    for leg in route.get("legs", []):
        for p in leg.get("points", []):
            pt = (float(p["latitude"]), float(p["longitude"]))
            if not coords or coords[-1] != pt:  # legs share their joining point
                coords.append(pt)

    guidance: list[tuple[float, float]] = []
    for ins in (route.get("guidance") or {}).get("instructions", []):
        if "routeOffsetInMeters" in ins and "travelTimeInSeconds" in ins:
            guidance.append((float(ins["routeOffsetInMeters"]), float(ins["travelTimeInSeconds"])))

    return RouteResult(
        coords=coords,
        length_m=length_m,
        travel_time_s=travel_s,
        guidance=guidance,
        departure_utc=departure,
        arrival_utc=arrival,
        provider="tomtom",
    )
