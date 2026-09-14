from collections.abc import Sequence
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mmqp.domain.calendars import (
    AlignedObservation,
    AlignmentCandidate,
    CalendarValidationError,
    CalendarVersionLookupError,
    MarketDate,
    TradingCalendarDay,
    TradingCalendarVersion,
    ValuationCalendarVersion,
)
from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.ports.calendars import TradingCalendarRepository, ValuationCalendarRepository

MARKET_TIMEZONES = {
    "A_SHARE": "Asia/Shanghai",
    "HONG_KONG": "Asia/Hong_Kong",
    "UNITED_STATES": "America/New_York",
}


class CalendarService:
    def __init__(
        self,
        trading_repository: TradingCalendarRepository | None = None,
        valuation_repository: ValuationCalendarRepository | None = None,
    ) -> None:
        self._trading_repository = trading_repository
        self._valuation_repository = valuation_repository

    @property
    def timezone_map(self) -> dict[str, str]:
        return dict(MARKET_TIMEZONES)

    def market_time_zone(self, market: str) -> str:
        timezone = MARKET_TIMEZONES.get(market)
        if timezone is None:
            raise DomainError(
                ProblemV1(
                    kind="calendar/market-unsupported",
                    title="Unsupported market",
                    status=400,
                    detail=f"market {market} has no supported calendar timezone",
                )
            )
        return timezone

    def register_trading(self, version: TradingCalendarVersion) -> TradingCalendarVersion:
        self._validate_trading(version)
        if self._trading_repository is None:
            return version
        return self._trading_repository.create(version)

    def register_valuation(self, version: ValuationCalendarVersion) -> ValuationCalendarVersion:
        self._validate_valuation(version)
        if self._valuation_repository is None:
            return version
        return self._valuation_repository.create(version)

    def register(self, version: TradingCalendarVersion) -> TradingCalendarVersion:
        return self.register_trading(version)

    def select_trading(self, market: str, exchange: str, as_of: date) -> TradingCalendarVersion:
        self.market_time_zone(market)
        if self._trading_repository is None:
            raise _resolution_error(400, "trading calendar repository is unavailable")
        versions = self._trading_repository.select(market, exchange, as_of)
        if not versions:
            raise _resolution_error(
                404, f"no effective trading calendar for {market}/{exchange} at {as_of.isoformat()}"
            )
        if len(versions) != 1:
            ids = ", ".join(version.version_id for version in versions)
            raise _resolution_error(409, f"ambiguous trading calendar versions: {ids}")
        version = versions[0]
        if not self.covers_date(version, as_of):
            raise _resolution_error(404, f"calendar does not cover {as_of.isoformat()}")
        return version

    def select_valuation(self, market: str, as_of: date) -> ValuationCalendarVersion:
        if self._valuation_repository is None:
            raise _resolution_error(400, "valuation calendar repository is unavailable")
        versions = self._valuation_repository.select(market, as_of)
        if not versions:
            raise _resolution_error(
                404, f"no effective valuation calendar for {market} at {as_of.isoformat()}"
            )
        if len(versions) != 1:
            ids = ", ".join(version.version_id for version in versions)
            raise _resolution_error(409, f"ambiguous valuation calendar versions: {ids}")
        version = versions[0]
        self._validate_valuation(version)
        return version

    def interpret(self, market: str, exchange: str, timestamp: str, as_of: date) -> MarketDate:
        calendar = self.select_trading(market, exchange, as_of)
        return self.interpret_timestamp(market, exchange, timestamp, calendar)

    def interpret_timestamp(
        self, market: str, exchange: str, timestamp: str, calendar: TradingCalendarVersion
    ) -> MarketDate:
        expected_zone = self.market_time_zone(market)
        if calendar.timezone != expected_zone:
            raise DomainError(
                ProblemV1(
                    kind="calendar/timezone-mismatch",
                    title="Calendar timezone mismatch",
                    status=400,
                    detail=f"calendar timezone {calendar.timezone} does not match market timezone {expected_zone}",
                )
            )
        try:
            zone = ZoneInfo(calendar.timezone)
        except Exception as exc:
            raise _validation_error(["timezone"]) from exc
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainError(
                ProblemV1(
                    kind="calendar/timestamp-invalid",
                    title="Invalid timestamp",
                    status=400,
                    detail=f"timestamp {timestamp} is not a valid ISO timestamp",
                )
            ) from exc
        if parsed.tzinfo is None:
            raise DomainError(
                ProblemV1(
                    kind="calendar/timezone-missing",
                    title="Missing timezone",
                    status=400,
                    detail="timestamp lacks a named IANA time zone or UTC offset",
                )
            )
        localized = parsed.astimezone(zone)
        market_date = localized.date()
        matching_day = self.day_for(calendar, market_date)
        return MarketDate(
            market=market,
            exchange=exchange,
            zone=expected_zone,
            market_date=market_date,
            kind=matching_day.kind,
        )

    def covers_date(self, calendar: TradingCalendarVersion, value: date) -> bool:
        return calendar.effective_from <= value and (
            calendar.effective_to is None or calendar.effective_to >= value
        )

    def day_for(self, calendar: TradingCalendarVersion, value: date) -> TradingCalendarDay:
        for day in calendar.days:
            if day.date == value:
                return day
        raise _resolution_error(404, f"calendar day {value.isoformat()} is not recorded")

    def align_observations(
        self,
        alignment_date: date,
        decision_timestamp: datetime,
        candidates: Sequence[AlignmentCandidate],
        aligned_calendar: TradingCalendarVersion,
    ) -> tuple[AlignedObservation, ...]:
        self.market_time_zone(aligned_calendar.market)
        decision_timestamp = _aware(decision_timestamp)
        if not self.covers_date(aligned_calendar, alignment_date):
            raise _resolution_error(404, f"alignment calendar does not cover {alignment_date.isoformat()}")
        return tuple(
            AlignedObservation(
                source_market_date=candidate.source_market_date,
                alignment_date=alignment_date,
                included=candidate.provider_available_at <= decision_timestamp,
                exclusion_reason=(
                    None
                    if candidate.provider_available_at <= decision_timestamp
                    else "provider-available-after-decision"
                ),
            )
            for candidate in candidates
        )

    def interpret_valuation_timestamp(self, market: str, timestamp: str, as_of: date) -> MarketDate:
        calendar = self.select_valuation(market, as_of)
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _validation_error(["timestamp"]) from exc
        parsed = _aware(parsed)
        return MarketDate(
            market=market,
            exchange=market,
            zone=calendar.timezone,
            market_date=parsed.astimezone(ZoneInfo(calendar.timezone)).date(),
            kind="full",
        )

    def _validate_trading(self, version: TradingCalendarVersion) -> None:
        errors: list[str] = []
        if not version.version_id.strip():
            errors.append("version_id")
        if version.market not in MARKET_TIMEZONES:
            errors.append("market")
        elif version.timezone != MARKET_TIMEZONES[version.market]:
            errors.append("timezone")
        try:
            ZoneInfo(version.timezone)
        except Exception:
            errors.append("timezone")
        if version.effective_to is not None and version.effective_to < version.effective_from:
            errors.append("effective_to")
        if errors:
            raise _validation_error(errors)
        self._validate_days(version, errors)
        if errors:
            raise _validation_error(errors)

    def _validate_days(self, version: TradingCalendarVersion, errors: list[str]) -> None:
        seen_dates: set[date] = set()
        for day in version.days:
            if day.date in seen_dates:
                errors.append("day.date")
                continue
            seen_dates.add(day.date)
            if day.market != version.market:
                errors.append("day.market")
            if day.exchange != version.exchange:
                errors.append("day.exchange")
            if not self.covers_date(version, day.date):
                errors.append("day.date")
            if len(day.sessions) > 8:
                errors.append("day.sessions")
            self._validate_sessions(day, errors)

    def _validate_sessions(self, day: TradingCalendarDay, errors: list[str]) -> None:
        previous: TradingSessionTime | None = None
        for session in day.sessions:
            try:
                start = _time(session.start)
                end = _time(session.end)
            except ValueError:
                errors.append("day.session.time")
                continue
            if end <= start:
                errors.append("day.session.interval")
            if session.kind not in {"regular", "non_regular"}:
                errors.append("day.session.kind")
            if previous is not None and previous[1] > start:
                errors.append("day.session.overlap")
            previous = (start, end)

    def _validate_valuation(self, version: ValuationCalendarVersion) -> None:
        errors: list[str] = []
        if not version.version_id.strip():
            errors.append("version_id")
        if not version.market.strip():
            errors.append("market")
        try:
            ZoneInfo(version.timezone)
        except Exception:
            errors.append("timezone")
        if version.effective_to is not None and version.effective_to < version.effective_from:
            errors.append("effective_to")
        if errors:
            raise _validation_error(errors)


type TradingSessionTime = tuple[datetime, datetime]


def _time(value: str) -> datetime:
    hour, minute = (int(part) for part in value.split(":"))
    return datetime(2000, 1, 1, hour, minute)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise _validation_error(["decision_timestamp"])
    return value


def _legitimate_value(value: datetime) -> datetime:
    return _aware(value)


def _resolution_error(status: int, detail: str) -> DomainError:
    return CalendarVersionLookupError(status=status, detail=detail)


def _validation_error(fields: list[str]) -> DomainError:
    return CalendarValidationError(fields=fields)
