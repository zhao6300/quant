from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from mmqp.adapters.sqlite.calendars import (
    SqliteTradingCalendarRepository,
    SqliteValuationCalendarRepository,
)
from mmqp.adapters.sqlite.market_rules import SqliteMarketRuleRepository
from mmqp.domain.calendars import (
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
    ValuationCalendarVersion,
)
from mmqp.domain.market_rules import MarketRuleProfile

BASELINE_CALENDAR_VERSION_ID = "baseline-weekdays"
BASELINE_CALENDAR_EFFECTIVE_FROM = date(2024, 1, 1)
BASELINE_CALENDAR_EFFECTIVE_TO = date(2099, 12, 31)
BASELINE_CALENDAR_SESSIONS = (TradingSession(start="09:30", end="16:00", kind="regular"),)

BASELINE_MARKETS: tuple[tuple[str, str, str], ...] = (
    ("A_SHARE", "SSE", "sse-equity-baseline"),
    ("HONG_KONG", "HKEX", "hkex-equity-baseline"),
    ("UNITED_STATES", "NYSE", "nyse-equity-baseline"),
)


def _timezone(market: str) -> str:
    return {
        "A_SHARE": "Asia/Shanghai",
        "HONG_KONG": "Asia/Hong_Kong",
        "UNITED_STATES": "America/New_York",
    }[market]


def _trading_calendar(market: str, exchange: str) -> TradingCalendarVersion:
    current = BASELINE_CALENDAR_EFFECTIVE_FROM
    days: list[TradingCalendarDay] = []
    while current <= BASELINE_CALENDAR_EFFECTIVE_TO:
        if current.weekday() < 5:
            days.append(
                TradingCalendarDay(
                    market=market,
                    exchange=exchange,
                    date=current,
                    kind="full",
                    sessions=BASELINE_CALENDAR_SESSIONS,
                )
            )
        current += timedelta(days=1)
    return TradingCalendarVersion(
        version_id=f"{market.lower()}-{BASELINE_CALENDAR_VERSION_ID}",
        market=market,
        exchange=exchange,
        timezone=_timezone(market),
        effective_from=BASELINE_CALENDAR_EFFECTIVE_FROM,
        effective_to=BASELINE_CALENDAR_EFFECTIVE_TO,
        days=tuple(days),
    )


def _valuation_calendar(market: str) -> ValuationCalendarVersion:
    return ValuationCalendarVersion(
        version_id=f"{market.lower()}-{BASELINE_CALENDAR_VERSION_ID}",
        market=market,
        timezone=_timezone(market),
        effective_from=BASELINE_CALENDAR_EFFECTIVE_FROM,
        effective_to=BASELINE_CALENDAR_EFFECTIVE_TO,
    )


def _profile(market: str, exchange: str, version_id: str) -> MarketRuleProfile:
    price_limit_rule: Literal["NONE", "STATIC_PERCENTAGE_BASE_REFERENCE", "PROVIDER_BAND_REQUIRED"] = (
        "STATIC_PERCENTAGE_BASE_REFERENCE" if market == "A_SHARE" else "PROVIDER_BAND_REQUIRED"
    )
    sell_availability_rule: Literal["SAME_MARKET_DATE", "NEXT_OPEN_MARKET_DATE"] = (
        "NEXT_OPEN_MARKET_DATE" if market == "A_SHARE" else "SAME_MARKET_DATE"
    )
    return MarketRuleProfile(
        version_id=version_id,
        market=market,
        exchange=exchange,
        asset_type="EQUITY",
        effective_from=BASELINE_CALENDAR_EFFECTIVE_FROM,
        effective_to=BASELINE_CALENDAR_EFFECTIVE_TO,
        trading_lot=100 if market == "A_SHARE" else 1,
        tick_size=Decimal("0.01"),
        price_limit_rule=price_limit_rule,
        price_limit_percent=Decimal("0.10") if market == "A_SHARE" else None,
        sell_availability_rule=sell_availability_rule,
        security_settlement_open_dates=1,
        cash_settlement_open_dates=1,
        permitted_session_types=("regular",),
    )


def seed_market_baseline(database_path: Path) -> None:
    trading_repository = SqliteTradingCalendarRepository(database_path)
    valuation_repository = SqliteValuationCalendarRepository(database_path)
    market_rule_repository = SqliteMarketRuleRepository(database_path)
    try:
        for market, exchange, rule_version_id in BASELINE_MARKETS:
            calendar_version_id = f"{market.lower()}-{BASELINE_CALENDAR_VERSION_ID}"
            if not any(
                calendar.version_id == calendar_version_id
                for calendar in trading_repository.list(market=market, exchange=exchange)
            ):
                trading_repository.create(_trading_calendar(market, exchange))
            if not any(
                calendar.version_id == calendar_version_id
                for calendar in valuation_repository.list(market=market)
            ):
                valuation_repository.create(_valuation_calendar(market))
            if not any(
                profile.market == market
                and profile.exchange == exchange
                and profile.asset_type == "EQUITY"
                and profile.version_id == rule_version_id
                for profile in market_rule_repository.list(market=market)
            ):
                market_rule_repository.create(_profile(market, exchange, rule_version_id))
    finally:
        trading_repository.close()
        valuation_repository.close()
        market_rule_repository.close()
