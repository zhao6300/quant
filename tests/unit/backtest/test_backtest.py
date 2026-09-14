from __future__ import annotations

from datetime import date

from mmqp.domain.backtest import (
    TradingCalendar,
    TradingCalendarDay,
)


def _calendar() -> TradingCalendar:
    return TradingCalendar(
        version_id="1",
        market="US",
        exchange="NYSE",
        timezone="America/New_York",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        days=(
            TradingCalendarDay(market="US", exchange="NYSE", day=date(2024, 1, 1), open=True),
            TradingCalendarDay(market="US", exchange="NYSE", day=date(2024, 1, 2), open=True),
            TradingCalendarDay(market="US", exchange="NYSE", day=date(2024, 1, 3), open=True),
        ),
    )
