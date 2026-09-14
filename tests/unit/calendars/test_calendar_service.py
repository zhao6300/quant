from datetime import date

import pytest

from mmqp.application.calendars import CalendarService
from mmqp.domain.calendars import (
    CalendarValidationError,
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
)
from mmqp.domain.errors import DomainError


def _calendar(*sessions: TradingSession) -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id="1",
        market="A_SHARE",
        exchange="SSE",
        timezone="Asia/Shanghai",
        effective_from=date(2023, 1, 1),
        effective_to=None,
        days=(
            TradingCalendarDay(
                market="A_SHARE",
                exchange="SSE",
                date=date(2023, 1, 1),
                kind="full" if sessions else "closed",
                sessions=sessions,
            ),
        ),
    )


def test_market_time_zone_uses_supported_market_timezones() -> None:
    service = CalendarService()
    assert service.market_time_zone("A_SHARE") == "Asia/Shanghai"
    assert service.market_time_zone("HONG_KONG") == "Asia/Hong_Kong"
    assert service.market_time_zone("UNITED_STATES") == "America/New_York"

    with pytest.raises(DomainError):
        service.market_time_zone("UNSUPPORTED")


def test_service_validates_trading_calendar_version() -> None:
    service = CalendarService()
    assert service.register(_calendar()).version_id == "1"
    invalid = TradingCalendarVersion(
        version_id="",
        market="A_SHARE",
        exchange="SSE",
        timezone="Asia/Shanghai",
        effective_from=date(2023, 1, 2),
        effective_to=None,
        days=(),
    )
    with pytest.raises(CalendarValidationError):
        service.register(invalid)


def test_calendar_calendar_version_idempotency() -> None:
    service = CalendarService()
    version = _calendar()
    assert service.register(version) == version
