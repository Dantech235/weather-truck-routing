"""Request validation and response shapes (the latter document the OpenAPI schema)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers, status

from core.exceptions import ApiError
from core.geo import haversine_mi
from risk.rules import Level

RISK_LEVEL_CHOICES = [lv.name for lv in Level] + ["UNKNOWN"]
COMPONENT_LEVEL_CHOICES = [lv.name for lv in Level]
INTERVAL_CHOICES = [10, 25, 50]
MAX_LOAD_LB = 120_000
HEAVY_LOAD_LB = 80_000
DEPARTURE_PAST_GRACE = timedelta(minutes=15)
DEPARTURE_MAX_AHEAD = timedelta(days=14)
MIN_TRIP_MI = 1.0


# --- Request -------------------------------------------------------------------------------


class PlaceSerializer(serializers.Serializer[dict[str, Any]]):
    # DRF's stubs type Field.label as str; a field named `label` is valid at runtime.
    label = serializers.CharField(max_length=200)  # type: ignore[assignment]
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer[dict[str, Any]]):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.DateTimeField(help_text="ISO 8601; converted to UTC.")
    load_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=INTERVAL_CHOICES)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        now = timezone.now()
        departure = attrs["departure"]
        if departure < now - DEPARTURE_PAST_GRACE or departure > now + DEPARTURE_MAX_AHEAD:
            raise ApiError(
                "DEPARTURE_OUT_OF_RANGE",
                "Departure must be between 15 minutes ago and 14 days from now.",
                field="departure",
            )
        o, d = attrs["origin"], attrs["destination"]
        if haversine_mi((o["lat"], o["lon"]), (d["lat"], d["lon"])) < MIN_TRIP_MI:
            raise ApiError(
                "SAME_LOCATION",
                "Origin and destination must be at least 1 mile apart.",
                field="destination",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        attrs["interval_mi"] = int(attrs["interval_mi"])
        return attrs


class GeocodeQuerySerializer(serializers.Serializer[dict[str, Any]]):
    q = serializers.CharField(min_length=3, max_length=200, trim_whitespace=True)


# --- Response ------------------------------------------------------------------------------


class ErrorDetailSerializer(serializers.Serializer[dict[str, Any]]):
    code = serializers.CharField()
    message = serializers.CharField()
    field = serializers.CharField(allow_null=True)


class ErrorSerializer(serializers.Serializer[dict[str, Any]]):
    error = ErrorDetailSerializer()


class PlaceResultSerializer(PlaceSerializer):
    pass


class WeatherSerializer(serializers.Serializer[dict[str, Any]]):
    wind_mph = serializers.FloatField(allow_null=True)
    gust_mph = serializers.FloatField(allow_null=True)
    rain_in_hr = serializers.FloatField(allow_null=True)
    snow_in_hr = serializers.FloatField(allow_null=True)
    forecast_hour_utc = serializers.DateTimeField(allow_null=True)


class RiskSerializer(serializers.Serializer[dict[str, Any]]):
    level = serializers.ChoiceField(choices=RISK_LEVEL_CHOICES)
    wind = serializers.ChoiceField(choices=COMPONENT_LEVEL_CHOICES, allow_null=True)
    rain = serializers.ChoiceField(choices=COMPONENT_LEVEL_CHOICES, allow_null=True)
    snow = serializers.ChoiceField(choices=COMPONENT_LEVEL_CHOICES, allow_null=True)
    drivers = serializers.ListField(child=serializers.CharField())
    load_rule_applied = serializers.CharField(allow_null=True)


class CheckpointSerializer(serializers.Serializer[dict[str, Any]]):
    index = serializers.IntegerField()
    mile = serializers.FloatField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    eta_utc = serializers.DateTimeField()
    elapsed_s = serializers.IntegerField()
    eta_method = serializers.ChoiceField(choices=["guidance", "proportional"])
    weather = WeatherSerializer()
    risk = RiskSerializer()


class SegmentSerializer(serializers.Serializer[dict[str, Any]]):
    from_mi = serializers.FloatField()
    to_mi = serializers.FloatField()
    from_frac = serializers.FloatField()
    to_frac = serializers.FloatField()
    level = serializers.ChoiceField(choices=RISK_LEVEL_CHOICES)


class MetricsSerializer(serializers.Serializer[dict[str, Any]]):
    no_travel_miles = serializers.FloatField()
    severe_miles = serializers.FloatField()
    high_miles = serializers.FloatField()
    moderate_miles = serializers.FloatField()
    low_miles = serializers.FloatField()
    unknown_miles = serializers.FloatField()
    avg_risk = serializers.FloatField(allow_null=True)
    max_level = serializers.ChoiceField(choices=RISK_LEVEL_CHOICES)


class RouteSerializer(serializers.Serializer[dict[str, Any]]):
    label = serializers.CharField()  # type: ignore[assignment]
    rank = serializers.IntegerField()
    provider = serializers.CharField()
    distance_mi = serializers.FloatField()
    travel_time_s = serializers.IntegerField()
    departure_utc = serializers.DateTimeField()
    arrival_utc = serializers.DateTimeField()
    geometry = serializers.CharField(help_text="Encoded polyline, precision 5, simplified.")
    metrics = MetricsSerializer()
    reason = serializers.CharField(allow_null=True)
    lost_because = serializers.CharField(allow_null=True)
    warnings = serializers.ListField(child=serializers.CharField())
    segments = SegmentSerializer(many=True)
    checkpoints = CheckpointSerializer(many=True)


class PlanInputsSerializer(serializers.Serializer[dict[str, Any]]):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_utc = serializers.DateTimeField()
    load_lb = serializers.IntegerField()
    interval_mi = serializers.IntegerField()


class PlanMetaSerializer(serializers.Serializer[dict[str, Any]]):
    timings_ms = serializers.DictField(child=serializers.IntegerField())
    interval_mi = serializers.IntegerField()
    weather_points = serializers.IntegerField()
    forecast_window_utc = serializers.ListField(child=serializers.DateTimeField())


class PlanSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["ready", "partial", "failed"])
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    inputs = PlanInputsSerializer()
    warnings = serializers.ListField(child=serializers.CharField())
    routes_found = serializers.IntegerField()
    recommended = serializers.CharField(allow_null=True)
    recommendation_reason = serializers.CharField()
    routes = RouteSerializer(many=True)
    meta = PlanMetaSerializer()


class BandSerializer(serializers.Serializer[dict[str, Any]]):
    level = serializers.ChoiceField(choices=COMPONENT_LEVEL_CHOICES)
    min = serializers.FloatField(
        help_text="Inclusive lower bound (strictly above for rain/snow No Travel)."
    )
    max = serializers.FloatField(allow_null=True)
    min_inclusive = serializers.BooleanField()
    max_inclusive = serializers.BooleanField()


class LoadRuleSerializer(serializers.Serializer[dict[str, Any]]):
    wind_min_mph = serializers.FloatField()
    wind_max_mph = serializers.FloatField(allow_null=True)
    load_over_lb = serializers.IntegerField()
    result = serializers.ChoiceField(choices=COMPONENT_LEVEL_CHOICES)
    text = serializers.CharField()


class RiskRulesSerializer(serializers.Serializer[dict[str, Any]]):
    levels = serializers.ListField(child=serializers.ChoiceField(choices=RISK_LEVEL_CHOICES))
    colors = serializers.DictField(child=serializers.CharField())
    scores = serializers.DictField(child=serializers.IntegerField())
    labels = serializers.DictField(child=serializers.CharField())
    wind_mph = BandSerializer(many=True)
    rain_in_hr = BandSerializer(many=True)
    snow_in_hr = BandSerializer(many=True)
    load_rules = LoadRuleSerializer(many=True)
