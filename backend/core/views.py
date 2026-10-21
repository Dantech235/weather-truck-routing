from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


@extend_schema(
    operation_id="health",
    responses=inline_serializer(
        name="Health",
        fields={
            "status": serializers.CharField(),
            "providers": inline_serializer(
                name="ProviderHealth",
                fields={"tomtom": serializers.BooleanField(), "ors": serializers.BooleanField()},
            ),
        },
    ),
)
@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness plus whether each routing provider is configured."""
    return Response(
        {
            "status": "ok",
            "providers": {
                "tomtom": bool(settings.TOMTOM_API_KEY),
                "ors": bool(settings.ORS_API_KEY),
            },
        }
    )
