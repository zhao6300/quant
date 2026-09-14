from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.calendars import MARKET_TIMEZONES, CalendarService
from mmqp.domain.calendars import (
    AlignedObservation,
    AlignmentCandidate,
    TradingCalendarDay,
    TradingCalendarVersion,
)
from mmqp.domain.errors import DomainError

MARKET_EXCHANGES = {
    "A_SHARE": "SSE",
    "HONG_KONG": "HKEX",
    "UNITED_STATES": "NYSE",
}

_UTC_OFFSETS = (
    UTC,
    timezone(timedelta(hours=-4)),
    timezone(timedelta(hours=-5)),
    timezone(timedelta(hours=8)),
)


def _calendar_version(market: str, exchange: str, market_date: date) -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id=f"p08-{market.lower()}-{exchange.lower()}",
        market=market,
        exchange=exchange,
        timezone=MARKET_TIMEZONES[market],
        effective_from=market_date,
        effective_to=None,
        days=(
            TradingCalendarDay(
                market=market,
                exchange=exchange,
                date=market_date,
                kind="full",
                sessions=(),
            ),
            TradingCalendarDay(
                market=market,
                exchange=exchange,
                date=market_date - timedelta(days=1),
                kind="full",
                sessions=(),
            ),
        ),
    )


@given(
    market=st.sampled_from(("A_SHARE", "HONG_KONG", "UNITED_STATES")),
    market_date=st.dates(
        min_value=date(1970, 1, 1),
        max_value=date(2037, 12, 31),
    ),
    local_offset=st.sampled_from(_UTC_OFFSETS),
)
@settings(max_examples=60, deadline=None)
def test_p08_calendar_interpretation_is_unique_and_timezone_correct(
    market: str,
    market_date: date,
    local_offset: timezone,
) -> None:
    service = CalendarService()
    exchange = MARKET_EXCHANGES[market]
    calendar = _calendar_version(market, exchange, market_date)
    instant = datetime.combine(
        market_date,
        time(hour=9, minute=30),
        tzinfo=local_offset,
    )
    naive_timestamp = f"{market_date.isoformat()}T09:30:00"

    explanation = service.interpret_timestamp(
        market,
        exchange,
        instant.isoformat(timespec="seconds"),
        calendar,
    )

    with pytest.raises(DomainError):
        service.interpret_timestamp(
            market,
            exchange,
            naive_timestamp,
            calendar,
        )
    expected_market_date = instant.astimezone(ZoneInfo(MARKET_TIMEZONES[market])).date()
    assert explanation.market_date == expected_market_date
    assert explanation.kind == "full"
    assert explanation.zone == MARKET_TIMEZONES[market]

    alignment = service.align_observations(
        market_date,
        instant,
        (AlignmentCandidate(source_market_date=market_date, provider_available_at=instant),),
        calendar,
    )
    assert alignment == (
        AlignedObservation(
            source_market_date=market_date,
            alignment_date=market_date,
            included=True,
        ),
    )
