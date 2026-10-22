"""Three-route guarantee — pure orchestration over a RoutingProvider (no Django).

1. Ask for the fastest route plus 2 alternatives.
2. De-duplicate: X duplicates Y if ≥ 90% of X's points (sampled every 1 mi) lie within
   0.5 mi of Y (Y sampled every 0.2 mi, so the point-to-line error is ≤ 0.1 mi).
3. While fewer than 3 distinct routes and fewer than 4 extra requests: request again with one
   via-point = the midpoint of the fastest route, offset perpendicular to the origin→destination
   bearing by 8%, then 15%, of the straight-line distance, alternating left and right.
4. Return what exists (never invent a route); label A, B, C by ascending travel time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from core.geo import (
    LatLon,
    NearIndex,
    bearing_deg,
    cumulative_distances,
    destination_point,
    haversine_mi,
    point_at_distance,
    sample_polyline,
)
from providers.routing.base import RouteNotFound, RouteResult, RoutingProvider, RoutingUnavailable

logger = logging.getLogger(__name__)

TARGET_ROUTES = 3
MAX_EXTRA_REQUESTS = 4
DUPLICATE_SHARE = 0.90
DUPLICATE_RADIUS_MI = 0.5
SAMPLE_STEP_MI = 1.0
INDEX_STEP_MI = 0.2
VIA_OFFSETS: tuple[tuple[float, int], ...] = ((0.08, -1), (0.08, 1), (0.15, -1), (0.15, 1))
LABELS = "ABC"


@dataclass(frozen=True)
class LabeledRoute:
    label: str
    route: RouteResult


def is_duplicate(x: RouteResult, y: RouteResult) -> bool:
    samples = sample_polyline(x.coords, SAMPLE_STEP_MI)
    if not samples:
        return True
    index = NearIndex(sample_polyline(y.coords, INDEX_STEP_MI), DUPLICATE_RADIUS_MI)
    close = sum(1 for p in samples if index.near(p))
    return close / len(samples) >= DUPLICATE_SHARE


def add_distinct(distinct: list[RouteResult], candidates: list[RouteResult]) -> None:
    for c in candidates:
        if len(c.coords) < 2:
            continue
        if not any(is_duplicate(c, d) or is_duplicate(d, c) for d in distinct):
            distinct.append(c)


def via_points(fastest: RouteResult, origin: LatLon, dest: LatLon) -> list[LatLon]:
    cumulative = cumulative_distances(fastest.coords)
    mid = point_at_distance(fastest.coords, cumulative, cumulative[-1] / 2)
    straight = haversine_mi(origin, dest)
    brg = bearing_deg(origin, dest)
    return [destination_point(mid, brg + 90 * side, straight * frac) for frac, side in VIA_OFFSETS]


def find_routes(
    provider: RoutingProvider,
    origin: LatLon,
    dest: LatLon,
    depart_utc: datetime,
    load_lb: int,
) -> list[LabeledRoute]:
    """Up to three distinct routes. Raises RouteNotFound if the first request finds none."""
    first = provider.routes(origin, dest, depart_utc, load_lb, max_alternatives=2)
    distinct: list[RouteResult] = []
    add_distinct(distinct, sorted(first, key=lambda r: r.travel_time_s))
    if not distinct:
        raise RouteNotFound("No drivable route found between these locations.")

    fastest = distinct[0]
    for i, via in enumerate(via_points(fastest, origin, dest)[:MAX_EXTRA_REQUESTS]):
        if len(distinct) >= TARGET_ROUTES:
            break
        try:
            extra = provider.routes(origin, dest, depart_utc, load_lb, 0, via=[via])
        except RouteNotFound:
            logger.info("via_request_no_route attempt=%d", i + 1)
            continue
        except RoutingUnavailable as exc:  # keep what we already have
            logger.warning("via_request_unavailable attempt=%d error=%s", i + 1, exc)
            break
        add_distinct(distinct, extra)

    chosen = sorted(distinct[:TARGET_ROUTES], key=lambda r: r.travel_time_s)
    return [LabeledRoute(LABELS[i], r) for i, r in enumerate(chosen)]
