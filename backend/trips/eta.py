"""ETA per checkpoint from the provider's guidance — pure, no Django.

Guidance is a list of (route_offset_m, elapsed_s) pairs. It is normalised to a monotonic list
that starts at (0, 0) and ends at exactly (total_length_m, total_travel_time_s), so the
destination ETA always equals the provider's total time. Without guidance the ETA is
proportional to distance (eta_method = "proportional").
"""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

EtaMethod = Literal["guidance", "proportional"]
GuidancePoint = tuple[float, float]


def normalize_guidance(
    raw: Sequence[GuidancePoint], total_length_m: float, total_time_s: float
) -> list[GuidancePoint]:
    """Monotonic in both offset and time, bounded by the totals, with fixed endpoints."""
    out: list[GuidancePoint] = [(0.0, 0.0)]
    for offset, elapsed in sorted(raw):
        last_off, last_t = out[-1]
        if offset <= last_off or offset >= total_length_m:
            continue
        if elapsed < last_t or elapsed > total_time_s:
            continue
        out.append((float(offset), float(elapsed)))
    out.append((float(total_length_m), float(total_time_s)))
    return out


@dataclass(frozen=True)
class EtaModel:
    total_length_m: float
    total_time_s: float
    guidance: tuple[GuidancePoint, ...] | None

    @classmethod
    def build(
        cls,
        total_length_m: float,
        total_time_s: float,
        raw_guidance: Sequence[GuidancePoint] | None,
    ) -> EtaModel:
        if total_length_m <= 0:
            raise ValueError("route length must be positive")
        if not raw_guidance:
            return cls(total_length_m, total_time_s, None)
        norm = normalize_guidance(raw_guidance, total_length_m, total_time_s)
        return cls(total_length_m, total_time_s, tuple(norm))

    @property
    def method(self) -> EtaMethod:
        return "guidance" if self.guidance is not None else "proportional"

    def elapsed_at_offset(self, offset_m: float) -> float:
        d = min(max(offset_m, 0.0), self.total_length_m)
        if d == self.total_length_m:
            return self.total_time_s
        if self.guidance is None:
            return self.total_time_s * d / self.total_length_m
        offsets = [p[0] for p in self.guidance]
        i = bisect.bisect_right(offsets, d)  # offsets[i-1] <= d < offsets[i]
        (o0, t0), (o1, t1) = self.guidance[i - 1], self.guidance[i]
        return t0 + (t1 - t0) * (d - o0) / (o1 - o0)

    def elapsed_at_fraction(self, frac: float) -> float:
        if frac >= 1.0:
            return self.total_time_s
        return self.elapsed_at_offset(frac * self.total_length_m)


@dataclass(frozen=True)
class Eta:
    eta_utc: datetime
    elapsed_s: float
    method: EtaMethod


def etas_for_fractions(
    departure_utc: datetime, model: EtaModel, fractions: Sequence[float]
) -> list[Eta]:
    out: list[Eta] = []
    for frac in fractions:
        elapsed = model.elapsed_at_fraction(frac)
        out.append(Eta(departure_utc + timedelta(seconds=elapsed), elapsed, model.method))
    return out
