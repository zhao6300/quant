from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from mmqp.adapters.sqlite.calendars import SqliteTradingCalendarRepository
from mmqp.application.calendars import MARKET_TIMEZONES, CalendarService
from mmqp.domain.calendars import (
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
)
from mmqp.domain.errors import DomainError


def _calendar(version_id: str) -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id=version_id,
        market="A_SHARE",
        exchange="SSE",
        timezone=MARKET_TIMEZONES["A_SHARE"],
        effective_from=date(2024, 1, 1),
        effective_to=None,
        days=(
            TradingCalendarDay(
                market="A_SHARE",
                exchange="SSE",
                date=date(2024, 6, 11),
                kind="full",
                sessions=(TradingSession(start="09:30", end="11:30", kind="regular"),),
            ),
        ),
    )


def test_offline_us_calendar_interprets_dst_transition_across_versions(tmp_path: Path) -> None:
    spring = TradingCalendarVersion(
        version_id="us-spring",
        market="UNITED_STATES",
        exchange="NYSE",
        timezone=MARKET_TIMEZONES["UNITED_STATES"],
        effective_from=date(2024, 3, 1),
        effective_to=date(2024, 3, 10),
        days=(
            TradingCalendarDay(
                market="UNITED_STATES",
                exchange="NYSE",
                date=date(2024, 3, 10),
                kind="closed",
                sessions=(),
            ),
        ),
    )
    autumn = TradingCalendarVersion(
        version_id="us-autumn",
        market="UNITED_STATES",
        exchange="NYSE",
        timezone=MARKET_TIMEZONES["UNITED_STATES"],
        effective_from=date(2024, 10, 1),
        effective_to=date(2024, 12, 31),
        days=(
            TradingCalendarDay(
                market="UNITED_STATES",
                exchange="NYSE",
                date=date(2024, 11, 3),
                kind="closed",
                sessions=(),
            ),
        ),
    )
    repository = SqliteTradingCalendarRepository(tmp_path / "control.sqlite3")
    for version in (spring, autumn):
        repository.create(version)
    service = CalendarService(repository)

    assert service.interpret(
        "UNITED_STATES", "NYSE", "2024-03-10T07:00:00+00:00", date(2024, 3, 10)
    ).market_date == date(2024, 3, 10)
    assert service.interpret(
        "UNITED_STATES", "NYSE", "2024-11-03T05:59:00+00:00", date(2024, 11, 3)
    ).market_date == date(2024, 11, 3)


def test_offline_sse_calendar_rejects_ambiguous_and_missing_efficacy_dates(
    tmp_path: Path,
) -> None:
    first = _calendar("sse-first")
    second = _calendar("sse-second")
    repository = SqliteTradingCalendarRepository(tmp_path / "control.sqlite3")
    service = CalendarService(repository)
    repository.create(first)
    repository.create(second)

    assert repository.select(market="A_SHARE", exchange="SSE", as_of=date(2024, 6, 11)) == [
        first,
        second,
    ]
    with pytest.raises(DomainError):
        service.select_trading("A_SHARE", "SSE", date(2024, 6, 11))
    with pytest.raises(DomainError):
        service.select_trading("A_SHARE", "SSE", date(2025, 1, 1))
