from __future__ import annotations

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
    max_affordable_lots,
    run_backtest,
    total_cost,
    trade_cost,
)


@given(
    start_date=st.dates(
        min_value=date(2024, 1, 1),
        max_value=date(2024, 12, 1),
    ),
    initial_cash=st.integers(min_value=100, max_value=10_000),
    requested_quantity=st.integers(min_value=1, max_value=100),
)
def test_affordable_lot_matches_market_and_cost_rule(
    start_date: date,
    initial_cash: int,
    requested_quantity: int,
) -> None:
    calendar = TradingCalendar(
        version_id="calendar-1",
        market="US",
        exchange="NYSE",
        timezone="America/New_York",
        effective_from=start_date,
        effective_to=None,
        days=(
            TradingCalendarDay(
                market="US",
                exchange="NYSE",
                day=start_date,
                open=True,
                regular_sessions=((datetime(start_date.year, start_date.month, start_date.day, 9, 30), datetime(start_date.year, start_date.month, start_date.day, 16)),),
            ),
        ),
    )
    market_rule = MarketRuleProfile(
        version_id="market-rule-1",
        market="US",
        exchange="NYSE",
        asset_type="EQUITY",
        effective_from=start_date,
    )
    cost_rule = CostRule(version_id="cost-model-1", effective_from=start_date)
    request = TradeRequest(
        request_id="request-1",
        decision_id="decision-1",
        asset_id="asset-1",
        market="US",
        exchange="NYSE",
        asset_type="EQUITY",
        side="BUY",
        requested_quantity=Decimal(requested_quantity),
        requested_price=Decimal("10"),
        currency="USD",
        decision_at=datetime(start_date.year, start_date.month, start_date.day, 8, 0, tzinfo=UTC),
    )
    plan = BacktestPlan(
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
        prices=(PriceBar(asset_id="asset-1", market="US", source_date=start_date, close=Decimal("10")),),
        calendars=(calendar,),
        market_rules=(market_rule,),
        cost_rules=(cost_rule,),
        initial_cash=Decimal(initial_cash),
    )
    result = run_backtest(plan)
    fill = result.trades[0]
    requested_gross_value = request.requested_quantity * request.requested_price
    requested_components = trade_cost(requested_gross_value, cost_rule)
    expected_lots = max_affordable_lots(
        price=request.requested_price,
        trading_lot=market_rule.trading_lot,
        cash=plan.initial_cash,
        components=requested_components,
    )
    assert fill.filled_quantity == Decimal(min(requested_quantity, expected_lots))
    assert total_cost(fill.cost_components) == fill.total_cost
    assert result.settled_cash == plan.initial_cash - fill.gross_value - fill.total_cost
