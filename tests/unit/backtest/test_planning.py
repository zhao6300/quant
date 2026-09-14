from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mmqp.domain.backtest import (
    BacktestPlan,
    CostRule,
    ManifestPins,
    MarketRuleProfile,
    PriceBar,
    StrategyInput,
    TradeRequest,
    TradingCalendar,
    TradingCalendarDay,
    schedule_requests,
)


def _pins() -> ManifestPins:
    return ManifestPins(
        experiment_id="experiment-1",
        strategy_version_id="strategy-1",
        data_snapshot_id="snapshot-1",
        universe_version_id="universe-1",
        portfolio_definition_version_id="portfolio-1",
        trading_calendar_version_id="calendar-1",
        market_rule_profile_version_id="market-rule-1",
        fx_policy_version_id="fx-policy-1",
        fx_rate_version_id=None,
        corporate_action_version_id=None,
        transaction_cost_model_version_id="cost-model-1",
    )


def _request(request_id: str = "request-1") -> TradeRequest:
    return TradeRequest(
        request_id=request_id,
        decision_id="decision-1",
        asset_id="asset-1",
        market="US",
        exchange="NYSE",
        asset_type="EQUITY",
        side="BUY",
        requested_quantity=Decimal("100"),
        requested_price=Decimal("100"),
        currency="USD",
        decision_at=datetime(2024, 1, 2, 13, 30, tzinfo=UTC),
        inputs=(
            StrategyInput(
                asset_id="asset-1",
                available_at=datetime(2024, 1, 1, tzinfo=UTC),
                version_id="input-1",
            ),
        ),
    )


def _plan(duplicate_calendars: bool = False) -> BacktestPlan:
    calendar = TradingCalendar(
        version_id="calendar-1",
        market="US",
        exchange="NYSE",
        timezone="America/New_York",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        days=(
            TradingCalendarDay(
                market="US",
                exchange="NYSE",
                day=date(2024, 1, 2),
                open=True,
                regular_sessions=((datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 16)),),
            ),
            TradingCalendarDay(
                market="US",
                exchange="NYSE",
                day=date(2024, 1, 3),
                open=True,
                regular_sessions=((datetime(2024, 1, 3, 9, 30), datetime(2024, 1, 3, 16)),),
            ),
        ),
    )
    calendar_versions = (
        (
            calendar,
            TradingCalendar(
                version_id="calendar-2",
                market=calendar.market,
                exchange=calendar.exchange,
                timezone=calendar.timezone,
                effective_from=calendar.effective_from,
                effective_to=None,
                days=calendar.days,
            ),
        )
        if duplicate_calendars
        else (calendar,)
    )
    return BacktestPlan(
        pins=_pins(),
        requests=(_request(),),
        prices=(PriceBar(asset_id="asset-1", market="US", source_date=date(2024, 1, 1), close=Decimal("100")),),
        calendars=calendar_versions,
        market_rules=(
            MarketRuleProfile(
                version_id="market-rule-1",
                market="US",
                exchange="NYSE",
                asset_type="EQUITY",
                effective_from=date(2024, 1, 1),
            ),
        ),
        cost_rules=(CostRule(version_id="cost-model-1", effective_from=date(2024, 1, 1)),),
    )


def test_schedule_requests_uses_strictly_later_session() -> None:
    plan = schedule_requests(_plan())
    assert plan.trades[0].execution_at.day == 2
    assert plan.trades[0].market_date == date(2024, 1, 2)
    assert plan.trades[0].request.request_id == "request-1"


def test_multiple_calendar_versions_are_rejected() -> None:
    with pytest.raises(ValueError, match="ambiguous trading calendars"):
        schedule_requests(_plan(duplicate_calendars=True))


def test_missing_market_rule_is_rejected() -> None:
    plan = _plan()
    with pytest.raises(ValueError, match="no market rules"):
        schedule_requests(
            BacktestPlan(
                pins=plan.pins,
                requests=plan.requests,
                prices=plan.prices,
                calendars=plan.calendars,
                market_rules=(),
                cost_rules=plan.cost_rules,
            )
        )
