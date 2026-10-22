"""Plan orchestration (section 6.5): routes → checkpoints + ETA → weather at ETA → risk →
segments + metrics → ranking + reasons → persist. Stage durations are logged and returned."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import polyline
from django.core.cache import cache

from core.exceptions import ApiError
from core.geo import METERS_PER_MILE, LatLon, simplify
from providers import registry
from providers.routing.base import RouteNotFound, RoutingProvider, RoutingUnavailable
from providers.weather.base import (
    HOUR,
    HourlySeries,
    WeatherProvider,
    ceil_hour,
    floor_hour,
    weather_at_eta,
)
from risk.engine import Assessment, LevelOrUnknown, classify_checkpoint, level_name
from risk.metrics import RouteMetrics, build_segments, compute_metrics
from risk.rules import (
    LEVEL_COLORS,
    LOAD_NO_TRAVEL_WIND,
    LOAD_SEVERE_WIND,
    RAIN_BANDS,
    SNOW_BANDS,
    WIND_BANDS,
    WIND_NO_TRAVEL_ANY_LOAD,
    Band,
    Level,
)

from .alternatives import LabeledRoute, find_routes
from .eta import EtaModel, etas_for_fractions
from .heatmap import build_heatmap
from .models import TripPlan
from .ranking import rank
from .reasons import NO_SAFE_ROUTE, lost_because, winner_reason
from .sampling import sample_checkpoints
from .serializers import HEAVY_LOAD_LB

logger = logging.getLogger(__name__)

ROUTE_CACHE_TTL_S = 15 * 60
WEATHER_CACHE_TTL_S = 30 * 60
DISPLAY_TOLERANCE_DEG = 0.0005
WARNING_HEAVY_LOAD = "LOAD_ABOVE_80000_LB"


@dataclass(frozen=True)
class PlanInput:
    origin: dict[str, Any]  # {label, lat, lon}
    destination: dict[str, Any]
    departure_utc: datetime
    load_lb: int
    interval_mi: int

    @property
    def origin_ll(self) -> LatLon:
        return (float(self.origin["lat"]), float(self.origin["lon"]))

    @property
    def dest_ll(self) -> LatLon:
        return (float(self.destination["lat"]), float(self.destination["lon"]))


@dataclass
class Timer:
    timings_ms: dict[str, int] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            ms = round((time.perf_counter() - t0) * 1000)
            self.timings_ms[name] = ms
            logger.info("plan_stage stage=%s duration_ms=%d", name, ms)


@dataclass
class _CheckpointWork:
    index: int
    mile: float
    frac: float
    lat: float
    lon: float
    key: LatLon
    eta: datetime
    elapsed_s: float
    eta_method: str
    weather: dict[str, Any] | None = None
    assessment: Assessment | None = None
    fetch_failed: bool = False


# --- Cached provider access --------------------------------------------------------------


def _round15(t: datetime) -> datetime:
    t = t.astimezone(UTC)
    return t.replace(minute=t.minute - t.minute % 15, second=0, microsecond=0)


def route_cache_key(inp: PlanInput) -> str:
    o, d = inp.origin_ll, inp.dest_ll
    raw = (
        f"{o[0]:.4f},{o[1]:.4f}|{d[0]:.4f},{d[1]:.4f}|{_round15(inp.departure_utc).isoformat()}"
        f"|{inp.load_lb // 10_000}|via:auto"
    )
    return "routes:" + hashlib.sha1(raw.encode()).hexdigest()


def get_routes(provider: RoutingProvider, inp: PlanInput) -> list[LabeledRoute]:
    key = route_cache_key(inp)
    cached: list[LabeledRoute] | None = cache.get(key)
    if cached is not None:
        return cached
    routes = find_routes(provider, inp.origin_ll, inp.dest_ll, inp.departure_utc, inp.load_lb)
    cache.set(key, routes, ROUTE_CACHE_TTL_S)
    return routes


def _weather_key(point: LatLon, start: datetime, end: datetime) -> str:
    return f"wx:{point[0]:.2f}:{point[1]:.2f}:{start:%Y%m%d%H}:{end:%Y%m%d%H}"


def get_weather(
    provider: WeatherProvider, points: list[LatLon], start: datetime, end: datetime
) -> dict[LatLon, HourlySeries]:
    keys = {p: _weather_key(p, start, end) for p in points}
    found: dict[str, HourlySeries] = cache.get_many(list(keys.values()))
    out = {p: found[k] for p, k in keys.items() if k in found}
    missing = [p for p in points if p not in out]
    if missing:
        fetched = provider.hourly(missing, start, end)
        cache.set_many({keys[p]: s for p, s in fetched.items()}, WEATHER_CACHE_TTL_S)
        out.update(fetched)
    return out


# --- Formatting helpers ------------------------------------------------------------------


def iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def _component(lv: Level | None) -> str | None:
    return None if lv is None else lv.name


# --- Build -------------------------------------------------------------------------------


def build_plan(
    inp: PlanInput,
    routing: RoutingProvider | None = None,
    weather: WeatherProvider | None = None,
) -> TripPlan:
    routing = routing or registry.routing()
    weather = weather or registry.weather()
    timer = Timer()

    with timer.stage("routing"):
        try:
            labeled = get_routes(routing, inp)
        except RouteNotFound as exc:
            raise ApiError("ROUTE_NOT_FOUND", str(exc), status_code=422) from exc
        except RoutingUnavailable as exc:
            logger.error("routing_unavailable error=%s", exc)
            raise ApiError(
                "ROUTING_UNAVAILABLE",
                "Routing providers are unavailable. Please try again shortly.",
                status_code=503,
            ) from exc

    with timer.stage("sampling_eta"):
        work: dict[str, list[_CheckpointWork]] = {}
        for lr in labeled:
            r = lr.route
            cps = sample_checkpoints(r.coords, inp.interval_mi, r.length_m / METERS_PER_MILE)
            model = EtaModel.build(r.length_m, r.travel_time_s, r.guidance)
            etas = etas_for_fractions(inp.departure_utc, model, [c.frac for c in cps])
            work[lr.label] = [
                _CheckpointWork(
                    index=c.index,
                    mile=c.mile,
                    frac=c.frac,
                    lat=c.lat,
                    lon=c.lon,
                    key=(round(c.lat, 2), round(c.lon, 2)),
                    eta=e.eta_utc,
                    elapsed_s=e.elapsed_s,
                    eta_method=e.method,
                )
                for c, e in zip(cps, etas, strict=True)
            ]

    all_cps = [c for cps in work.values() for c in cps]
    start = floor_hour(min(c.eta for c in all_cps))
    end = ceil_hour(max(c.eta for c in all_cps)) + HOUR
    points = list(dict.fromkeys(c.key for c in all_cps))

    with timer.stage("weather"):
        series = get_weather(weather, points, start, end)

    with timer.stage("risk"):
        for c in all_cps:
            s = series.get(c.key)
            if s is None:
                c.fetch_failed = True
                c.weather = {
                    "wind_mph": None,
                    "gust_mph": None,
                    "rain_in_hr": None,
                    "snow_in_hr": None,
                    "forecast_hour_utc": None,
                }
                c.assessment = classify_checkpoint(None, None, None, inp.load_lb)
                continue
            w = weather_at_eta(s, c.eta)
            c.weather = {
                "wind_mph": _r(w.wind_mph, 2),
                "gust_mph": _r(w.gust_mph, 2),
                "rain_in_hr": _r(w.rain_in_hr, 3),
                "snow_in_hr": _r(w.snow_in_hr, 3),
                "forecast_hour_utc": iso(w.forecast_hour_utc),
            }
            c.assessment = classify_checkpoint(w.wind_mph, w.rain_in_hr, w.snow_in_hr, inp.load_lb)

        metrics: dict[str, RouteMetrics] = {}
        segments: dict[str, list[dict[str, Any]]] = {}
        for lr in labeled:
            route_cps = work[lr.label]
            distance_mi = lr.route.length_m / METERS_PER_MILE
            levels: list[LevelOrUnknown] = [_level(c) for c in route_cps]
            segs = build_segments(
                [(c.mile, lv) for c, lv in zip(route_cps, levels, strict=True)], distance_mi
            )
            metrics[lr.label] = compute_metrics(
                lr.label, distance_mi, lr.route.travel_time_s, levels, segs
            )
            segments[lr.label] = [
                {
                    "from_mi": round(s.from_mi, 1),
                    "to_mi": round(s.to_mi, 1),
                    "from_frac": round(s.from_frac, 6),
                    "to_frac": round(s.to_frac, 6),
                    "level": level_name(s.level),
                }
                for s in segs
            ]

    with timer.stage("ranking"):
        ranked, recommended = rank(list(metrics.values()))
        winner = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else None
        reason = winner_reason(winner, runner_up) if recommended else NO_SAFE_ROUTE

    by_label = {lr.label: lr for lr in labeled}
    routes_out: list[dict[str, Any]] = []
    for position, m in enumerate(ranked, start=1):
        lr = by_label[m.label]
        r = lr.route
        display = simplify(r.coords, DISPLAY_TOLERANCE_DEG)
        routes_out.append(
            {
                "label": m.label,
                "rank": position,
                "provider": r.provider,
                "distance_mi": m.distance_mi,
                "travel_time_s": r.travel_time_s,
                "departure_utc": iso(inp.departure_utc),
                "arrival_utc": iso(inp.departure_utc + timedelta(seconds=r.travel_time_s)),
                "geometry": polyline.encode(display, 5),
                "metrics": {
                    "no_travel_miles": m.no_travel_miles,
                    "severe_miles": m.severe_miles,
                    "high_miles": m.high_miles,
                    "moderate_miles": m.moderate_miles,
                    "low_miles": m.low_miles,
                    "unknown_miles": m.unknown_miles,
                    "avg_risk": m.avg_risk,
                    "max_level": level_name(m.max_level),
                },
                "reason": reason if position == 1 else None,
                "lost_because": None if position == 1 else lost_because(m, winner),
                "warnings": list(m.warnings),
                "segments": segments[m.label],
                "checkpoints": [_checkpoint_out(c) for c in work[m.label]],
            }
        )

    partial = any(c.fetch_failed for c in all_cps)
    warnings = [WARNING_HEAVY_LOAD] if inp.load_lb > HEAVY_LOAD_LB else []
    result: dict[str, Any] = {
        "inputs": {
            "origin": inp.origin,
            "destination": inp.destination,
            "departure_utc": iso(inp.departure_utc),
            "load_lb": inp.load_lb,
            "interval_mi": inp.interval_mi,
        },
        "warnings": warnings,
        "routes_found": len(routes_out),
        "recommended": recommended,
        "recommendation_reason": reason,
        "routes": routes_out,
        "meta": {
            "timings_ms": timer.timings_ms,
            "interval_mi": inp.interval_mi,
            "weather_points": len(points),
            "forecast_window_utc": [iso(start), iso(end)],
        },
    }

    with timer.stage("save"):
        plan = TripPlan.objects.create(
            origin=inp.origin,
            destination=inp.destination,
            departure_utc=inp.departure_utc,
            load_lb=inp.load_lb,
            interval_mi=inp.interval_mi,
            status=TripPlan.Status.PARTIAL if partial else TripPlan.Status.READY,
            result=result,
        )
    return plan


def _level(c: _CheckpointWork) -> LevelOrUnknown:
    assert c.assessment is not None
    return c.assessment.level


def _checkpoint_out(c: _CheckpointWork) -> dict[str, Any]:
    a = c.assessment
    assert a is not None
    return {
        "index": c.index,
        "mile": round(c.mile, 1),
        "lat": round(c.lat, 5),
        "lon": round(c.lon, 5),
        "eta_utc": iso(c.eta),
        "elapsed_s": round(c.elapsed_s),
        "eta_method": c.eta_method,
        "weather": c.weather,
        "risk": {
            "level": level_name(a.level),
            "wind": _component(a.wind),
            "rain": _component(a.rain),
            "snow": _component(a.snow),
            "drivers": list(a.drivers),
            "load_rule_applied": a.load_rule_applied,
        },
    }


def serialize_plan(plan: TripPlan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "status": plan.status,
        "created_at": iso(plan.created_at),
        "expires_at": iso(plan.expires_at),
        **plan.result,
    }


# --- Risk rules payload (single source of truth for the frontend legend) ---------------------

LEVEL_LABELS = {
    "LOW": "Low",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "SEVERE": "Severe",
    "NO_TRAVEL": "No Travel",
    "UNKNOWN": "Unknown",
}


def _bands(bands: list[Band]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lower, lower_inclusive = 0.0, True
    for upper, upper_inclusive, level in bands:
        out.append(
            {
                "level": level.name,
                "min": lower,
                "max": upper,
                "min_inclusive": lower_inclusive,
                "max_inclusive": upper_inclusive,
            }
        )
        lower, lower_inclusive = upper, not upper_inclusive
    out.append(
        {
            "level": Level.NO_TRAVEL.name,
            "min": lower,
            "max": None,
            "min_inclusive": lower_inclusive,
            "max_inclusive": False,
        }
    )
    return out


def risk_rules_payload() -> dict[str, Any]:
    levels = [lv.name for lv in Level] + ["UNKNOWN"]
    return {
        "levels": levels,
        "colors": dict(LEVEL_COLORS),
        "scores": {lv.name: int(lv) for lv in Level},
        "labels": LEVEL_LABELS,
        "wind_mph": _bands(WIND_BANDS),
        "rain_in_hr": _bands(RAIN_BANDS),
        "snow_in_hr": _bands(SNOW_BANDS),
        "load_rules": [
            {
                "wind_min_mph": WIND_NO_TRAVEL_ANY_LOAD,
                "wind_max_mph": None,
                "load_over_lb": 0,
                "result": "NO_TRAVEL",
                "text": "≥ 55 mph → No Travel for any load",
            },
            {
                "wind_min_mph": LOAD_NO_TRAVEL_WIND[0],
                "wind_max_mph": LOAD_NO_TRAVEL_WIND[1],
                "load_over_lb": LOAD_NO_TRAVEL_WIND[2],
                "result": "NO_TRAVEL",
                "text": "45–54 mph with load > 30,000 lb → No Travel",
            },
            {
                "wind_min_mph": LOAD_SEVERE_WIND[0],
                "wind_max_mph": LOAD_SEVERE_WIND[1],
                "load_over_lb": LOAD_SEVERE_WIND[2],
                "result": "SEVERE",
                "text": "35–44 mph with load > 40,000 lb → Severe",
            },
        ],
    }


# --- Heatmap ----------------------------------------------------------------------------------


def get_or_build_heatmap(plan: TripPlan, weather: WeatherProvider | None = None) -> dict[str, Any]:
    """Compute the corridor heatmap on first request, then serve it from the plan."""
    if plan.heatmap is not None:
        return dict(plan.heatmap)
    provider = weather or registry.weather()
    lines = [polyline.decode(r["geometry"], 5) for r in plan.result["routes"]]
    timer = Timer()
    with timer.stage("heatmap"):
        payload = build_heatmap(
            lines,
            plan.departure_utc,
            plan.load_lb,
            lambda pts, start, end: get_weather(provider, pts, start, end),
        )
    plan.heatmap = payload
    plan.save(update_fields=["heatmap"])
    return payload


def purge_expired_plans() -> int:
    """Delete plans past `expires_at`. Returns the number of plans deleted."""
    from django.utils import timezone

    deleted, _ = TripPlan.objects.filter(expires_at__lte=timezone.now()).delete()
    logger.info("purge_expired_plans deleted=%d", deleted)
    return int(deleted)
