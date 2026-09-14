from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

CalendarDayKind = Literal["closed", "full", "half"]
TradingSessionKind = Literal["regular", "non_regular"]


@dataclass(frozen=True, slots=True)
class TradingSession:
    start: str
    end: str
    kind: TradingSessionKind


@dataclass(frozen=True, slots=True)
class MarketDate:
    market: str
    exchange: str
    zone: str
    market_date: date
    kind: CalendarDayKind


@dataclass(frozen=True, slots=True)
class TradingCalendarDay:
    market: str
    exchange: str
    date: date
    kind: CalendarDayKind
    sessions: tuple[TradingSession, ...]


@dataclass(frozen=True, slots=True)
class TradingCalendarVersion:
    version_id: str
    market: str
    exchange: str
    timezone: str
    effective_from: date
    effective_to: date | None
    days: tuple[TradingCalendarDay, ...]


@dataclass(frozen=True, slots=True)
class ValuationCalendarVersion:
    version_id: str
    market: str
    timezone: str
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True, slots=True)
class AlignmentCandidate:
    source_market_date: date
    provider_available_at: datetime


@dataclass(frozen=True, slots=True)
class AlignedObservation:
    source_market_date: date
    alignment_date: date
    included: bool
    exclusion_reason: str | None = None


class CalendarValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="calendar/version-invalid",
                title="Invalid trading calendar",
                status=400,
                detail=None if fields is None else f"calendar version invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


class CalendarVersionLookupError(DomainError):
    def __init__(self, status: int, detail: str):
        super().__init__(
            ProblemV1(
                kind="calendar/version-resolution-failed",
                title="Calendar version resolution failed",
                status=status,
                detail=detail,
            )
        )
