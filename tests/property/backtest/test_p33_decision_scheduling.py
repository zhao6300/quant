from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backtest import (
    BacktestPlan,
    CostRule,
    ManifestPins,
    MarketRuleProfile,
    PriceBar,
    TradeRequest,
    TradingCalendar,
    TradingCalendarDay,
    schedule_requests,
)


def _plan(calendar_day: date) -> BacktestPlan:
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
                day=calendar_day,
                open=True,
                regular_sessions=((datetime(calendar_day.year, calendar_day.month, calendar_day.day, 9, 30), datetime(calendar_day.year, calendar_day.month, calendar_day.day, 16)),),
            ),
        ),
    )
    request = TradeRequest(
        request_id="request-1",
        decision_id="decision-1",
        asset_id="asset-1",
        market="US",
        exchange="NYSE",
        asset_type="EQUITY",
        side="BUY",
        requested_quantity=Decimal("10"),
        requested_price=Decimal("10"),
        currency="USD",
        decision_at=datetime(calendar_day.year, calendar_day.month, calendar_day.day, 13, 30, tzinfo=UTC),
    )
    return BacktestPlan(
        pins=ManifestPins(
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
        ),
        requests=(request,),
        prices=(PriceBar(asset_id="asset-1", market="US", source_date=calendar_day, close=Decimal("10")),),
        calendars=(calendar,),
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


@given(
    day=st.dates(
        min_value=date(2024, 1, 1),
        max_value=date(2024, 12, 1),
    ),
    hour=st.integers(min_value=0, max_value=23),
)
def test_decision_scheduling_is_strictly_later(day: date, hour: int) -> None:
    plan = _plan(day)
    # Force the decision to the day before the only covered session to keep the generated calendar valid.
    pre_open = datetime(day.year, day.month, day.day, min(hour, 8), 0, tzinfo=UTC)
    plan = replace(plan, requests=(replace(plan.requests[0], decision_at=pre_open),))
    scheduled = schedule_requests(plan)
    assert len(scheduled.trades) == 1
    trade = scheduled.trades[0]
    assert trade.execution_at > trade.request.decision_at
    assert trade.market_date == trade.execution_at.date()
