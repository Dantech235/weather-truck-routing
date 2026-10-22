"""Live end-to-end check (Phase 3 gate): builds a real Dallas → Denver plan and prints it.

Requires network access to the providers and TOMTOM_API_KEY (or ORS_API_KEY) in the env.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand

from trips.reasons import format_minutes
from trips.services import PlanInput, build_plan, serialize_plan


class Command(BaseCommand):
    help = "Build a live Dallas → Denver plan (45,000 lb, 25 mi) and print a summary."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--load", type=int, default=45_000)
        parser.add_argument("--interval", type=int, default=25, choices=[10, 25, 50])
        parser.add_argument("--hours-ahead", type=float, default=1.0)

    def handle(self, *args: Any, **options: Any) -> None:
        depart = datetime.now(UTC) + timedelta(hours=options["hours_ahead"])
        plan = build_plan(
            PlanInput(
                origin={"label": "Dallas, TX", "lat": 32.7767, "lon": -96.797},
                destination={"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
                departure_utc=depart.replace(second=0, microsecond=0),
                load_lb=options["load"],
                interval_mi=options["interval"],
            )
        )
        body = serialize_plan(plan)
        self.stdout.write(f"plan {body['id']} status={body['status']}")
        self.stdout.write(f"routes_found={body['routes_found']} recommended={body['recommended']}")
        self.stdout.write(f"reason: {body['recommendation_reason']}")
        for r in body["routes"]:
            m = r["metrics"]
            self.stdout.write(
                f"  #{r['rank']} Route {r['label']} [{r['provider']}] {r['distance_mi']} mi, "
                f"{format_minutes(r['travel_time_s'])}, checkpoints={len(r['checkpoints'])}, "
                f"NT={m['no_travel_miles']} S={m['severe_miles']} H={m['high_miles']} "
                f"avg={m['avg_risk']} unknown={m['unknown_miles']}"
            )
            if r["lost_because"]:
                self.stdout.write(f"     lost because: {r['lost_because']}")
        self.stdout.write(f"timings_ms={body['meta']['timings_ms']}")
