from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from core.geo import LatLon

LB_TO_KG = 0.45359237


class RouteNotFound(Exception):
    """The provider answered but found no drivable route for these inputs."""


class RoutingUnavailable(Exception):
    """No routing provider could be reached."""


@dataclass(frozen=True)
class RouteResult:
    coords: list[LatLon]  # (lat, lon)
    length_m: float
    travel_time_s: int
    guidance: list[tuple[float, float]]  # (offset_m, elapsed_s), monotonic; may be empty
    departure_utc: datetime
    arrival_utc: datetime
    provider: str  # "tomtom" | "ors" | "fake"


class RoutingProvider(Protocol):
    name: str

    def routes(
        self,
        origin: LatLon,
        dest: LatLon,
        depart_utc: datetime,
        load_lb: int,
        max_alternatives: int,
        via: list[LatLon] | None = None,
    ) -> list[RouteResult]: ...


class FallbackRouting:
    """Try each provider in order; move on only when a provider is unavailable."""

    def __init__(self, providers: list[RoutingProvider]) -> None:
        if not providers:
            raise ValueError("at least one routing provider is required")
        self.providers = providers
        self.name = providers[0].name

    def routes(
        self,
        origin: LatLon,
        dest: LatLon,
        depart_utc: datetime,
        load_lb: int,
        max_alternatives: int,
        via: list[LatLon] | None = None,
    ) -> list[RouteResult]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.routes(origin, dest, depart_utc, load_lb, max_alternatives, via)
            except RoutingUnavailable as exc:
                errors.append(f"{provider.name}: {exc}")
        raise RoutingUnavailable("; ".join(errors))
