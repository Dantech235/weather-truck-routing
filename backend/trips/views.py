from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from typing import Any

from django.core.cache import cache
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ApiError
from providers import registry
from providers.geocoding.base import GeocodingUnavailable

from .models import TripPlan
from .serializers import (
    ErrorSerializer,
    GeocodeQuerySerializer,
    PlaceResultSerializer,
    PlanRequestSerializer,
    PlanSerializer,
    RiskRulesSerializer,
)
from .services import PlanInput, build_plan, risk_rules_payload, serialize_plan
from .throttles import GeocodeThrottle, PlanCreateThrottle

GEOCODE_CACHE_TTL_S = 24 * 3600

ERRORS: dict[int | str, Any] = {
    400: OpenApiResponse(ErrorSerializer, description="Validation error"),
    429: OpenApiResponse(ErrorSerializer, description="Rate limited (see Retry-After)"),
}

EXAMPLE_REQUEST = {
    "origin": {"label": "Dallas, TX", "lat": 32.7767, "lon": -96.797},
    "destination": {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
    "departure": "2026-10-22T13:00:00Z",
    "load_lb": 45000,
    "interval_mi": 25,
}


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


class GeocodeView(APIView):
    throttle_classes = [GeocodeThrottle]

    @extend_schema(
        operation_id="geocode",
        parameters=[OpenApiParameter("q", str, required=True, description="At least 3 characters")],
        responses={200: PlaceResultSerializer(many=True), 503: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request) -> Response:
        query = GeocodeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        q = normalize_query(query.validated_data["q"])
        key = f"geocode:{q}"
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)
        try:
            places = registry.geocoding().search(q)
        except GeocodingUnavailable as exc:
            raise ApiError(
                "GEOCODING_UNAVAILABLE",
                "Address search is unavailable. Please try again shortly.",
                status_code=503,
            ) from exc
        body = [asdict(p) for p in places]
        cache.set(key, body, GEOCODE_CACHE_TTL_S)
        return Response(body)


class PlanCreateView(APIView):
    throttle_classes = [PlanCreateThrottle]

    @extend_schema(
        operation_id="plans_create",
        request=PlanRequestSerializer,
        responses={
            201: PlanSerializer,
            422: OpenApiResponse(ErrorSerializer, description="ROUTE_NOT_FOUND"),
            503: OpenApiResponse(ErrorSerializer, description="ROUTING_UNAVAILABLE"),
            **ERRORS,
        },
        examples=[OpenApiExample("Dallas to Denver", value=EXAMPLE_REQUEST, request_only=True)],
    )
    def post(self, request: Request) -> Response:
        ser = PlanRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        plan = build_plan(
            PlanInput(
                origin=dict(data["origin"]),
                destination=dict(data["destination"]),
                departure_utc=data["departure"],
                load_lb=data["load_lb"],
                interval_mi=data["interval_mi"],
            )
        )
        return Response(serialize_plan(plan), status=status.HTTP_201_CREATED)


def get_live_plan(plan_id: uuid.UUID) -> TripPlan:
    plan = TripPlan.objects.filter(id=plan_id, expires_at__gt=timezone.now()).first()
    if plan is None:
        raise ApiError(
            "PLAN_NOT_FOUND", "This plan does not exist or has expired.", status_code=404
        )
    return plan


class PlanDetailView(APIView):
    @extend_schema(
        operation_id="plans_retrieve",
        responses={200: PlanSerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, plan_id: uuid.UUID) -> Response:
        return Response(serialize_plan(get_live_plan(plan_id)))


class RiskRulesView(APIView):
    @extend_schema(operation_id="risk_rules", responses={200: RiskRulesSerializer})
    def get(self, request: Request) -> Response:
        return Response(risk_rules_payload())
