from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from mmqp.adapters.sqlite.calendars import SqliteTradingCalendarRepository
from mmqp.adapters.sqlite.market_rules import SqliteMarketRuleRepository
from mmqp.application.calendars import MARKET_TIMEZONES
from mmqp.domain.calendars import (
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
)
from mmqp.domain.market_rules import (
    MarketRuleProfile,
    PriceLimitRule,
    SellAvailabilityRule,
    SessionKind,
    SubmittedTrade,
    TradeSide,
)
from mmqp.kernels.market_rules import PureMarketRuleEvaluator

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "markets"


def _fixture_market(market: str) -> str:
    return {"A_SHARE": "a_share", "HONG_KONG": "hk", "UNITED_STATES": "us"}[market]


def _exchange(market: str) -> str:
    return {"A_SHARE": "SSE", "HONG_KONG": "HKEX", "UNITED_STATES": "NYSE"}[market]


def _profile(market: str, exchange: str) -> MarketRuleProfile:
    folder = _fixture_market(market)
    values = json.loads((FIXTURE_ROOT / folder / "rule.json").read_text())
    assert isinstance(values, dict)
    return MarketRuleProfile(
        version_id=str(values["version_id"]),
        market=str(values["market"]),
        exchange=str(values["exchange"]),
        asset_type=str(values["asset_type"]),
        effective_from=date.fromisoformat(str(values["effective_from"])),
        effective_to=None,
        trading_lot=int(values["trading_lot"]),
        tick_size=Decimal(str(values["tick_size"])),
        price_limit_rule=cast("PriceLimitRule", str(values["price_limit_rule"])),
        price_limit_percent=(
            Decimal(str(values["price_limit_percent"])) if values["price_limit_percent"] is not None else None
        ),
        sell_availability_rule=cast("SellAvailabilityRule", str(values["sell_availability_rule"])),
        security_settlement_open_dates=int(values["security_settlement_open_dates"]),
        cash_settlement_open_dates=int(values["cash_settlement_open_dates"]),
        permitted_session_types=tuple(values["permitted_session_types"]),
    )


def _calendar(
    version_id: str,
    market: str,
    exchange: str,
    days: tuple[TradingCalendarDay, ...],
) -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id=version_id,
        market=market,
        exchange=exchange,
        timezone=MARKET_TIMEZONES[market],
        effective_from=date(2024, 1, 1),
        effective_to=None,
        days=days,
    )


@pytest.mark.parametrize(
    "market,exchange",
    [
        ("A_SHARE", "SSE"),
        ("HONG_KONG", "HKEX"),
        ("UNITED_STATES", "NYSE"),
    ],
)
def test_offline_market_calendars_fixtures_retained_in_sqlite(
    tmp_path: Path, market: str, exchange: str
) -> None:
    calendar = _calendar(
        version_id=f"{market}-2024",
        market=market,
        exchange=exchange,
        days=(
            TradingCalendarDay(
                market=market, exchange=exchange, date=date(2024, 3, 1), kind="half", sessions=()
            ),
            TradingCalendarDay(
                market=market,
                exchange=exchange,
                date=date(2024, 3, 2),
                kind="closed",
                sessions=(TradingSession(start="09:00", end="10:00", kind="non_regular"),),
            ),
        ),
    )
    repository = SqliteTradingCalendarRepository(tmp_path / "control.sqlite3")
    repository.create(calendar)
    assert repository.select(market=market, exchange=exchange, as_of=date(2024, 3, 1)) == [calendar]


def _trade(market: str, exchange: str, side: str, session: str = "regular") -> SubmittedTrade:
    return SubmittedTrade(
        market=market,
        exchange=exchange,
        asset_type="EQUITY",
        trade_date=date(2024, 3, 1),
        side=cast("TradeSide", side),
        requested_quantity=Decimal("1005"),
        requested_price=Decimal("10.017"),
        session_kind=cast("SessionKind", session),
        market_data_price_limit_percent=Decimal("0.10"),
        market_data_price_band_percent=Decimal("0.10"),
        halt_status="ACTIVE",
        reference_price=Decimal("10.00"),
        sellable_quantity=Decimal("1000"),
    )


def _calendar_days(
    market: str, exchange: str
) -> tuple[TradingCalendarDay, TradingCalendarDay, TradingCalendarDay]:
    return (
        TradingCalendarDay(
            market=market,
            exchange=exchange,
            date=date(2024, 3, 1),
            kind="full",
            sessions=(TradingSession(start="09:30", end="16:00", kind="regular"),),
        ),
        TradingCalendarDay(
            market=market,
            exchange=exchange,
            date=date(2024, 3, 2),
            kind="closed",
            sessions=(),
        ),
        TradingCalendarDay(
            market=market,
            exchange=exchange,
            date=date(2024, 3, 4),
            kind="full",
            sessions=(TradingSession(start="09:30", end="16:00", kind="regular"),),
        ),
    )


@pytest.mark.parametrize(
    ("market", "expected_sell_date", "expected_settlement", "expected_quantity"),
    [
        ("A_SHARE", date(2024, 3, 4), date(2024, 3, 4), Decimal("1000")),
        ("HONG_KONG", date(2024, 3, 1), date(2024, 3, 4), Decimal("1000")),
        ("UNITED_STATES", date(2024, 3, 1), date(2024, 3, 4), Decimal("1005")),
    ],
)
def test_offline_golden_rules_for_share_hk_us_markets(
    tmp_path: Path,
    market: str,
    expected_sell_date: date,
    expected_settlement: date,
    expected_quantity: Decimal,
) -> None:
    exchange = _exchange(market)
    profile = _profile(market, exchange)
    exchange = profile.exchange
    rule_repository = SqliteMarketRuleRepository(tmp_path / "rules.sqlite3")
    calendar_repository = SqliteTradingCalendarRepository(tmp_path / "calendars.sqlite3")
    calendar = _calendar(
        version_id=f"{market.lower()}-equity-2024",
        market=market,
        exchange=exchange,
        days=_calendar_days(market, exchange),
    )
    calendar_repository.create(calendar)
    rule_repository.create(profile)
    result = PureMarketRuleEvaluator().evaluate_trade(
        _trade(market, profile.exchange, "BUY"),
        profile,
        calendar_repository.select(market=market, exchange=profile.exchange, as_of=date(2024, 3, 1))[0],
    )
    assert result.filled_quantity == expected_quantity
    assert result.valid_price == Decimal("10.01")
    assert result.sell_available_date == expected_sell_date
    assert result.security_settlement_date == expected_settlement
    assert result.rule_source_version_id == profile.version_id
