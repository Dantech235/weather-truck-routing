from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from django.test import Client

from core.geo import LatLon, corridor_grid, haversine_mi, sample_polyline
from providers import registry
from providers.weather.base import HourlySeries
from trips.heatmap import HOURS, build_heatmap
from trips.models import TripPlan
from trips.services import get_or_build_heatmap

from .stubs import DAL, DEN, StubWeather, calm, line

DEPART = datetime(2026, 10, 22, 13, 40, tzinfo=UTC)


def test_corridor_grid_keeps_points_near_routes_and_caps_count() -> None:
    lines = [line(DAL, DEN, 60, 0.0), line(DAL, DEN, 60, 2.0)]
    points, spacing = corridor_grid(lines)
    assert 0 < len(points) <= 600
    assert spacing >= 12.0
    assert (spacing - 12.0) % 2 == 0
    samples = [p for ln in lines for p in sample_polyline(ln, 2.0)]
    for p in points[::7]:
        assert min(haversine_mi(p, q) for q in samples) <= 25.0 + 1e-6


def test_corridor_grid_short_trip_uses_base_spacing() -> None:
    points, spacing = corridor_grid([line((32.7, -96.8), (33.2, -97.3), 10)])
    assert spacing == 12.0
    assert len(points) > 4


def test_corridor_grid_spacing_grows_until_cap() -> None:
    points, spacing = corridor_grid([line(DAL, DEN, 60)], max_points=40)
    assert len(points) <= 40
    assert spacing > 12.0


def _series_fn(points: list[LatLon], start: datetime, end: datetime) -> dict[LatLon, HourlySeries]:
    n = int((end - start) / timedelta(hours=1)) + 1
    return {
        p: HourlySeries(
            start_utc=start,
            wind_mph=[float(k) for k in range(n)],  # wind = hour index
            gust_mph=[0.0] * n,
            rain_in=[0.3 if k == 5 else 0.0 for k in range(n)],  # labelled hour 5 = 4→5
            snow_in=[0.0] * n,
        )
        for p in points
    }


def test_heatmap_hour_semantics_and_shape() -> None:
    hm = build_heatmap([line((32.7, -96.8), (33.2, -97.3), 10)], DEPART, 45_000, _series_fn)
    n = len(hm["points"])
    assert len(hm["hours"]) == HOURS == 49
    assert hm["hours"][0] == "2026-10-22T13:00:00Z"  # departure hour floor
    assert hm["hours"][-1] == "2026-10-24T13:00:00Z"
    assert len(hm["risk"]) == n
    assert all(len(row) == 49 for row in hm["risk"])
    lon, lat = hm["points"][0]
    assert -98 < lon < -96
    assert 32 < lat < 34
    wind = hm["wind"][0]
    assert wind[0] == 0.0
    assert wind[40] == 40.0
    rain = hm["rain"][0]
    assert rain[4] == 0.3
    assert rain[5] == 0.0
    risk = hm["risk"][0]
    assert risk[4] == 2  # 0.3 in/hr rain → High
    assert risk[36] == 3  # 36 mph with 45,000 lb → Severe (load rule)
    assert risk[46] == 4  # 46 mph with 45,000 lb > 30,000 → No Travel


def test_heatmap_unknown_and_missing_points() -> None:
    def partial(points: list[LatLon], start: datetime, end: datetime) -> dict[LatLon, HourlySeries]:
        full = _series_fn(points, start, start + timedelta(hours=10))  # short horizon
        return dict(list(full.items())[1:])  # first point failed to fetch

    hm = build_heatmap([line((32.7, -96.8), (33.2, -97.3), 10)], DEPART, 1, partial)
    assert set(hm["risk"][0]) == {-1}
    assert hm["wind"][0][0] == -1
    assert hm["risk"][1][3] >= 0
    assert hm["risk"][1][20] == -1  # beyond the series


@pytest.fixture
def _fresh() -> Iterator[None]:
    cache.clear()
    registry.reset()
    yield
    cache.clear()
    registry.reset()


@pytest.mark.django_db
@pytest.mark.usefixtures("_fresh")
def test_heatmap_endpoint_computes_once_then_serves_stored() -> None:
    api = Client()
    from django.utils import timezone

    body = {
        "origin": {"label": "Dallas, TX", "lat": 32.7767, "lon": -96.797},
        "destination": {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
        "departure": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_lb": 45_000,
        "interval_mi": 50,
    }
    plan_id = api.post("/api/v1/plans/", body, content_type="application/json").json()["id"]
    res = api.get(f"/api/v1/plans/{plan_id}/heatmap/", HTTP_ACCEPT_ENCODING="gzip")
    assert res.status_code == 200
    assert res["Content-Encoding"] == "gzip"
    stored = TripPlan.objects.get(id=plan_id).heatmap
    assert stored is not None
    assert len(stored["hours"]) == 49
    assert 0 < len(stored["points"]) <= 600
    assert any(v > 0 for row in stored["risk"] for v in row)

    weather = StubWeather(calm)
    again = get_or_build_heatmap(TripPlan.objects.get(id=plan_id), weather)
    assert weather.requested == []  # served from the plan, no refetch
    assert again["hours"] == stored["hours"]
    assert api.get("/api/v1/plans/00000000-0000-0000-0000-000000000000/heatmap/").status_code == 404
