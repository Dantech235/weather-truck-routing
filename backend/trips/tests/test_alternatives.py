from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.geo import bearing_deg, cumulative_distances, haversine_mi, point_at_distance
from providers.routing.base import RouteNotFound, RoutingUnavailable
from trips.alternatives import find_routes, is_duplicate, via_points

from .stubs import DAL, DEN, StubRouting, line, make_route

DEPART = datetime(2026, 10, 22, 13, tzinfo=UTC)


def r(bow: float, secs: int):  # type: ignore[no-untyped-def]
    return make_route(line(DAL, DEN, 60, bow), secs, DEPART)


def test_duplicate_detection() -> None:
    a = r(0.0, 100)
    assert is_duplicate(a, r(0.0, 120))
    assert is_duplicate(a, r(0.002, 120))  # ~0.1 mi apart
    assert not is_duplicate(a, r(1.0, 120))  # tens of miles apart in the middle


def test_three_distinct_from_first_request_labelled_by_time() -> None:
    stub = StubRouting([[r(0.0, 300), r(1.0, 100), r(-1.0, 200)]])
    out = find_routes(stub, DAL, DEN, DEPART, 45_000)
    assert [x.label for x in out] == ["A", "B", "C"]
    assert [x.route.travel_time_s for x in out] == [100, 200, 300]
    assert stub.calls == [{"max_alternatives": 2, "via": None}]


def test_duplicates_trigger_via_requests_alternating_sides() -> None:
    stub = StubRouting(
        [
            [r(0.0, 100), r(0.001, 110)],  # alternative is a duplicate
            [r(0.0005, 140)],  # via 1: duplicate again
            [r(1.2, 150)],  # via 2: distinct
            [r(-1.2, 160)],  # via 3: distinct → 3 routes, stop
        ]
    )
    out = find_routes(stub, DAL, DEN, DEPART, 1)
    assert len(out) == 3
    assert len(stub.calls) == 4
    vias = [c["via"] for c in stub.calls[1:]]
    assert all(v is not None and len(v) == 1 for v in vias)
    assert all(c["max_alternatives"] == 0 for c in stub.calls[1:])


def test_never_more_than_four_extra_requests_and_never_invents_routes() -> None:
    stub = StubRouting([[r(0.0, 100)], [], [], [], [], [r(2.0, 1)]])
    out = find_routes(stub, DAL, DEN, DEPART, 1)
    assert len(out) == 1
    assert len(stub.calls) == 5


def test_via_route_not_found_continues_and_unavailable_stops() -> None:
    stub = StubRouting([[r(0.0, 100)], RouteNotFound("x"), [r(1.0, 200)], RoutingUnavailable("y")])
    out = find_routes(stub, DAL, DEN, DEPART, 1)
    assert [x.route.travel_time_s for x in out] == [100, 200]
    assert len(stub.calls) == 4


def test_first_request_without_routes_raises() -> None:
    with pytest.raises(RouteNotFound):
        find_routes(StubRouting([[]]), DAL, DEN, DEPART, 1)


def test_via_points_are_perpendicular_offsets_of_the_midpoint() -> None:
    fastest = r(0.0, 100)
    vias = via_points(fastest, DAL, DEN)
    straight = haversine_mi(DAL, DEN)
    cum = cumulative_distances(fastest.coords)
    mid = point_at_distance(fastest.coords, cum, cum[-1] / 2)
    dists = [haversine_mi(mid, v) / straight for v in vias]
    assert dists == pytest.approx([0.08, 0.08, 0.15, 0.15], abs=0.01)
    brg = bearing_deg(DAL, DEN)
    sides = [((bearing_deg(mid, v) - brg + 540) % 360) - 180 for v in vias]
    assert sides[0] == pytest.approx(-90, abs=0.01)
    assert sides[1] == pytest.approx(90, abs=0.01)
