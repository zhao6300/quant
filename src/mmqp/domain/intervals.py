from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True, kw_only=True)
class InclusiveDateInterval:
    effective_from: date
    effective_to: date | None

    def __post_init__(self) -> None:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be earlier than effective_from")

    @property
    def inclusive(self) -> tuple[date, date]:
        if self.effective_to is None:
            return self.effective_from, date.max
        return self.effective_from, self.effective_to

    def contains(self, value: date) -> bool:
        effective_from, effective_to = self.inclusive
        return effective_from <= value <= effective_to

    def overlaps(self, other: InclusiveDateInterval) -> bool:
        return max(self.effective_from, other.effective_from) <= min(
            self.effective_to if self.effective_to is not None else date.max,
            other.effective_to if other.effective_to is not None else date.max,
        )
