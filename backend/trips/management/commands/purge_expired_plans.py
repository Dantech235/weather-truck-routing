from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from trips.models import TripPlan


class Command(BaseCommand):
    help = "Delete trip plans past their expiry (run daily)."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = TripPlan.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"Deleted {deleted} expired plan(s).")
