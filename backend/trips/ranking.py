"""Route ranking — pure, no Django.

Order: No Travel gate → No Travel miles → fewest Severe miles → fewest High miles →
lowest average risk → shortest travel time → label (deterministic tie-break).
"""

from __future__ import annotations

from risk.metrics import RouteMetrics

UNKNOWN_AVG_SENTINEL = 99.0

RankKey = tuple[bool, float, float, float, float, int, str]


def rank_key(m: RouteMetrics) -> RankKey:
    return (
        m.no_travel_miles > 0,  # gate: No Travel ranks below all routes without it
        round(m.no_travel_miles, 1),
        round(m.severe_miles, 1),  # 1. fewest Severe miles
        round(m.high_miles, 1),  # 2. fewest High miles
        round(m.avg_risk, 2) if m.avg_risk is not None else UNKNOWN_AVG_SENTINEL,  # 3.
        m.travel_time_s,  # 4. shortest travel time
        m.label,  # deterministic tie-break
    )


def rank(routes: list[RouteMetrics]) -> tuple[list[RouteMetrics], str | None]:
    ranked = sorted(routes, key=rank_key)
    recommended = ranked[0].label if ranked and ranked[0].no_travel_miles == 0 else None
    return ranked, recommended
