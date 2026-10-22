from __future__ import annotations

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class _IpThrottle(SimpleRateThrottle):
    def get_cache_key(self, request: Request, view: APIView) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PlanCreateThrottle(_IpThrottle):
    scope = "plans"
    rate = "20/min"


class GeocodeThrottle(_IpThrottle):
    scope = "geocode"
    rate = "120/min"
