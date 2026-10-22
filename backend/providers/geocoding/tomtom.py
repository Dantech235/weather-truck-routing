"""TomTom Fuzzy Search in typeahead mode, restricted to the US and Canada.

Docs: https://docs.tomtom.com/search-api/documentation/search-service/fuzzy-search
"""

from __future__ import annotations

from urllib.parse import quote

import httpx

from core.http import CircuitBreaker, ProviderHTTPError, ProviderUnavailable, request_json

from .base import MAX_RESULTS, GeocodingUnavailable, Place

BASE_URL = "https://api.tomtom.com/search/2/search"


class TomTomGeocoding:
    name = "tomtom"

    def __init__(self, client: httpx.Client, api_key: str, breaker: CircuitBreaker) -> None:
        self.client = client
        self.api_key = api_key
        self.breaker = breaker

    def search(self, query: str) -> list[Place]:
        if not self.api_key:
            raise GeocodingUnavailable("TomTom API key not configured")
        try:
            data = request_json(
                self.client,
                "GET",
                f"{BASE_URL}/{quote(query, safe='')}.json",
                params={
                    "key": self.api_key,
                    "typeahead": "true",
                    "limit": MAX_RESULTS,
                    "countrySet": "US,CA",
                },
                breaker=self.breaker,
            )
        except (ProviderUnavailable, ProviderHTTPError) as exc:
            raise GeocodingUnavailable(str(exc)) from exc
        places: list[Place] = []
        for r in data.get("results", []):
            pos = r.get("position") or {}
            label = (r.get("poi") or {}).get("name")
            address = (r.get("address") or {}).get("freeformAddress")
            text = f"{label}, {address}" if label and address else (address or label)
            if text and "lat" in pos and "lon" in pos:
                places.append(Place(label=text, lat=float(pos["lat"]), lon=float(pos["lon"])))
        return places
