from __future__ import annotations

from dataclasses import replace

import pytest

from risk.metrics import RouteMetrics
from trips.ranking import rank, rank_key
from trips.reasons import NO_SAFE_ROUTE, ONLY_ROUTE, format_minutes, lost_because, winner_reason


def rm(label: str, **kw: float | int | None) -> RouteMetrics:
    base = RouteMetrics(label=label, distance_mi=100.0, travel_time_s=3600, avg_risk=0.5)
    return replace(base, **kw)  # type: ignore[arg-type]


def labels(routes: list[RouteMetrics]) -> list[str]:
    return [r.label for r in routes]


# --- Each criterion decides alone --------------------------------------------------------


def test_fewest_severe_miles_wins() -> None:
    a = rm("A", severe_miles=5.0, high_miles=0.0, avg_risk=0.1, travel_time_s=100)
    b = rm("B", severe_miles=0.0, high_miles=50.0, avg_risk=2.0, travel_time_s=9000)
    ranked, rec = rank([a, b])
    assert labels(ranked) == ["B", "A"]
    assert rec == "B"


def test_fewest_high_miles_wins_when_severe_tied() -> None:
    a = rm("A", high_miles=20.0, avg_risk=0.1, travel_time_s=100)
    b = rm("B", high_miles=10.0, avg_risk=2.0, travel_time_s=9000)
    assert labels(rank([a, b])[0]) == ["B", "A"]


def test_lowest_avg_risk_wins_when_miles_tied() -> None:
    a = rm("A", avg_risk=0.9, travel_time_s=100)
    b = rm("B", avg_risk=0.3, travel_time_s=9000)
    assert labels(rank([a, b])[0]) == ["B", "A"]


def test_shortest_time_wins_when_all_risk_tied() -> None:
    a = rm("A", travel_time_s=5000)
    b = rm("B", travel_time_s=4000)
    assert labels(rank([a, b])[0]) == ["B", "A"]


def test_label_is_final_tie_break() -> None:
    assert labels(rank([rm("C"), rm("A"), rm("B")])[0]) == ["A", "B", "C"]


def test_unknown_avg_ranks_after_known_avg() -> None:
    a = rm("A", avg_risk=None)
    b = rm("B", avg_risk=3.9)
    assert labels(rank([a, b])[0]) == ["B", "A"]


def test_rounding_applies_before_compare() -> None:
    a = rm("A", high_miles=10.04, travel_time_s=100)
    b = rm("B", high_miles=10.0, travel_time_s=200)
    assert rank_key(a)[3] == rank_key(b)[3]
    assert labels(rank([a, b])[0]) == ["A", "B"]


# --- No Travel gate --------------------------------------------------------------------


def test_no_travel_gate_beats_everything() -> None:
    a = rm("A", no_travel_miles=0.1, severe_miles=0.0, high_miles=0.0, avg_risk=0.0)
    b = rm("B", severe_miles=300.0, high_miles=100.0, avg_risk=3.0, travel_time_s=99999)
    ranked, rec = rank([a, b])
    assert labels(ranked) == ["B", "A"]
    assert rec == "B"


def test_fewer_no_travel_miles_ranks_first_among_unsafe() -> None:
    a = rm("A", no_travel_miles=30.0)
    b = rm("B", no_travel_miles=5.0, severe_miles=100.0)
    ranked, rec = rank([a, b])
    assert labels(ranked) == ["B", "A"]
    assert rec is None


def test_all_no_travel_means_no_recommendation() -> None:
    ranked, rec = rank([rm("A", no_travel_miles=1.0), rm("B", no_travel_miles=2.0)])
    assert rec is None
    assert winner_reason(ranked[0], ranked[1]) == NO_SAFE_ROUTE


def test_empty() -> None:
    assert rank([]) == ([], None)


# --- Worked example (section 5.6) -------------------------------------------------------

WORKED = {
    "B": rm("B", distance_mi=431, travel_time_s=7 * 3600 + 5 * 60, high_miles=10.0, avg_risk=0.81),
    "A": rm("A", distance_mi=412, travel_time_s=6 * 3600 + 40 * 60, high_miles=25.0, avg_risk=0.62),
    "C": rm(
        "C", distance_mi=398, travel_time_s=6 * 3600 + 20 * 60, severe_miles=12.5, avg_risk=0.4
    ),
}


def test_worked_example_ranking() -> None:
    ranked, rec = rank([WORKED["A"], WORKED["B"], WORKED["C"]])
    assert labels(ranked) == ["B", "A", "C"]
    assert rec == "B"


def test_worked_example_reasons() -> None:
    ranked, _ = rank(list(WORKED.values()))
    winner, second, third = ranked
    assert winner_reason(winner, second) == (
        "No Severe miles and the fewest High miles (10.0 vs 25.0 on Route A)."
    )
    assert lost_because(second, winner) == "15.0 more High miles than Route B (25.0 vs 10.0)."
    assert lost_because(third, winner) == "12.5 more Severe miles than Route B (12.5 vs 0.0)."


# --- Reason strings ---------------------------------------------------------------------


def test_lost_because_time() -> None:
    w = rm("B", travel_time_s=3600)
    assert lost_because(rm("A", travel_time_s=3600 + 25 * 60), w) == "25 min longer than Route B."
    assert lost_because(rm("A", travel_time_s=3600 + 65 * 60), w) == "1h 05m longer than Route B."
    assert lost_because(rm("A", travel_time_s=3620), w) == "Under 1 min longer than Route B."


def test_lost_because_no_travel_and_avg() -> None:
    w = rm("B")
    assert lost_because(rm("A", no_travel_miles=12.5), w) == (
        "12.5 more No Travel miles than Route B (12.5 vs 0.0)."
    )
    assert lost_because(rm("A", avg_risk=0.81), rm("B", avg_risk=0.62)) == (
        "Higher average risk than Route B (0.81 vs 0.62)."
    )
    assert "forecast coverage" in lost_because(rm("A", avg_risk=None), w)
    assert "Tied with Route B" in lost_because(rm("A"), w)


@pytest.mark.parametrize(
    ("winner", "second", "expected"),
    [
        (
            rm("A", severe_miles=0.0),
            rm("B", severe_miles=12.5),
            "Fewest Severe miles (0.0 vs 12.5 on Route B).",
        ),
        (
            rm("A"),
            rm("B", no_travel_miles=3.0),
            "Only route with no No Travel miles (0.0 vs 3.0 on Route B).",
        ),
        (
            rm("A", avg_risk=0.4),
            rm("B", avg_risk=0.6),
            "No Severe miles, no High miles and the lowest average risk (0.40 vs 0.60 on Route B).",
        ),
        (
            rm("A", travel_time_s=6 * 3600),
            rm("B", travel_time_s=7 * 3600),
            "No Severe miles, no High miles, equal average risk (0.50) and the shortest "
            "travel time (6h 00m vs 7h 00m on Route B).",
        ),
        (
            rm("A", severe_miles=4.0, high_miles=1.0),
            rm("B", severe_miles=4.0, high_miles=2.0),
            "Equal Severe miles (4.0) and the fewest High miles (1.0 vs 2.0 on Route B).",
        ),
        (rm("A"), rm("B"), "Tied with Route B on every criterion; chosen by route label."),
        (rm("A"), None, ONLY_ROUTE),
    ],
)
def test_winner_reason(winner: RouteMetrics, second: RouteMetrics | None, expected: str) -> None:
    assert winner_reason(winner, second) == expected


def test_format_minutes() -> None:
    assert format_minutes(25 * 60) == "25 min"
    assert format_minutes(7 * 3600 + 5 * 60) == "7h 05m"
    assert format_minutes(29) == "0 min"
