from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MAX_RESULTS = 6


class GeocodingUnavailable(Exception):
    """No geocoding provider could be reached."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


class GeocodingProvider(Protocol):
    name: str

    def search(self, query: str) -> list[Place]: ...


class FallbackGeocoding:
    def __init__(self, providers: list[GeocodingProvider]) -> None:
        if not providers:
            raise ValueError("at least one geocoding provider is required")
        self.providers = providers
        self.name = providers[0].name

    def search(self, query: str) -> list[Place]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.search(query)[:MAX_RESULTS]
            except GeocodingUnavailable as exc:
                errors.append(f"{provider.name}: {exc}")
        raise GeocodingUnavailable("; ".join(errors))
