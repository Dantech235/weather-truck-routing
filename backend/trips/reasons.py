"""Human-readable recommendation and lost-because explanations — pure, no Django.

Numbers in these strings come from the same rounded metrics shown on route cards
(miles at 0.1, average risk at 0.01, durations in whole minutes).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from risk.metrics import RouteMetrics

from .ranking import UNKNOWN_AVG_SENTINEL

NO_SAFE_ROUTE = "No route is safe to drive at this departure time."
ONLY_ROUTE = "Only route found for this trip."


def format_minutes(seconds: float) -> str:
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h {minutes % 60:02d}m"


@dataclass(frozen=True)
class _MilesCriterion:
    name: str  # display name, e.g. "Severe"
    get: Callable[[RouteMetrics], float]


_MILES_CRITERIA: tuple[_MilesCriterion, ...] = (
    _MilesCriterion("No Travel", lambda m: round(m.no_travel_miles, 1)),
    _MilesCriterion("Severe", lambda m: round(m.severe_miles, 1)),
    _MilesCriterion("High", lambda m: round(m.high_miles, 1)),
)


def _avg(m: RouteMetrics) -> float:
    return round(m.avg_risk, 2) if m.avg_risk is not None else UNKNOWN_AVG_SENTINEL


def _fmt_avg(m: RouteMetrics) -> str:
    return f"{m.avg_risk:.2f}" if m.avg_risk is not None else "n/a"


def lost_because(loser: RouteMetrics, winner: RouteMetrics) -> str:
    """Explain the first ranking criterion on which `loser` differs from `winner`."""
    w = winner.label
    for c in _MILES_CRITERIA:
        lv, wv = c.get(loser), c.get(winner)
        if lv != wv:
            return f"{lv - wv:.1f} more {c.name} miles than Route {w} ({lv:.1f} vs {wv:.1f})."
    if _avg(loser) != _avg(winner):
        if loser.avg_risk is None:
            return f"Too little forecast coverage to score average risk; Route {w} has full data."
        return f"Higher average risk than Route {w} ({_fmt_avg(loser)} vs {_fmt_avg(winner)})."
    if loser.travel_time_s != winner.travel_time_s:
        diff = loser.travel_time_s - winner.travel_time_s
        if round(diff / 60) == 0:
            return f"Under 1 min longer than Route {w}."
        return f"{format_minutes(diff)} longer than Route {w}."
    return f"Tied with Route {w} on every criterion; ordered by route label."


def winner_reason(winner: RouteMetrics, runner_up: RouteMetrics | None) -> str:
    """Explain why `winner` beats `runner_up` (the rank-2 route)."""
    if winner.no_travel_miles > 0:
        return NO_SAFE_ROUTE
    if runner_up is None:
        return ONLY_ROUTE
    other = runner_up.label
    tied: list[str] = []
    for c in _MILES_CRITERIA:
        wv, rv = c.get(winner), c.get(runner_up)
        if wv != rv:
            if c.name == "No Travel":
                decider = f"the only route with no No Travel miles ({wv:.1f} vs {rv:.1f}"
            else:
                decider = f"the fewest {c.name} miles ({wv:.1f} vs {rv:.1f}"
            return _join(tied, f"{decider} on Route {other}).")
        if c.name != "No Travel":
            tied.append(f"no {c.name} miles" if wv == 0 else f"equal {c.name} miles ({wv:.1f})")
    if _avg(winner) != _avg(runner_up):
        decider = (
            f"the lowest average risk ({_fmt_avg(winner)} vs {_fmt_avg(runner_up)} "
            f"on Route {other})."
        )
        return _join(tied, decider)
    tied.append(f"equal average risk ({_fmt_avg(winner)})")
    if winner.travel_time_s != runner_up.travel_time_s:
        decider = (
            f"the shortest travel time ({format_minutes(winner.travel_time_s)} vs "
            f"{format_minutes(runner_up.travel_time_s)} on Route {other})."
        )
        return _join(tied, decider)
    return f"Tied with Route {other} on every criterion; chosen by route label."


def _join(tied: list[str], decider: str) -> str:
    if not tied:
        text = decider.removeprefix("the ")
        return text[0].upper() + text[1:]
    head = ", ".join(tied)
    return f"{head[0].upper()}{head[1:]} and {decider}"
