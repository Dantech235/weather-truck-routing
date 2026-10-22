from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.db import models
from django.utils import timezone

PLAN_TTL = timedelta(days=7)


def default_expiry() -> Any:
    return timezone.now() + PLAN_TTL


class TripPlan(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "ready"
        PARTIAL = "partial", "partial"
        FAILED = "failed", "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origin = models.JSONField()
    destination = models.JSONField()
    departure_utc = models.DateTimeField()
    load_lb = models.PositiveIntegerField()
    interval_mi = models.PositiveSmallIntegerField(choices=[(10, "10"), (25, "25"), (50, "50")])
    status = models.CharField(max_length=10, choices=Status.choices)
    result = models.JSONField()
    heatmap = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True, default=default_expiry)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"TripPlan {self.id} ({self.status})"
