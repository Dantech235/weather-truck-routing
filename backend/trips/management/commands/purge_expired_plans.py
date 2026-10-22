from typing import Any

from django.core.management.base import BaseCommand

from trips.services import purge_expired_plans


class Command(BaseCommand):
    help = "Delete trip plans past their expiry (run daily)."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(f"Deleted {purge_expired_plans()} expired plan(s).")
