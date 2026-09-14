from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from mmqp.domain.backtest import (
    BacktestPlan,
    CostRule,
    ManifestPins,
    MarketRuleProfile,
    PriceBar,
    TradeFill,
    TradeRequest,
    TradingCalendar,
    TradingCalendarDay,
    execute_trades,
    max_affordable_lots,
    run_backtest,
    total_cost,
    trade_cost,
)


def test_backtest_costs_reconcile() -> None:
    fill = _fill("BUY", "100", "1")
    assert total_cost(fill.cost_components) == fill.total_cost


def test_backtest_affordable_lots_are_whole() -> None:
    components = trade_cost(Decimal("200"), _rule())
    assert max_affordable_lots(Decimal("100"), 1, Decimal("200"), components) == 1


def test_backtest_trades_settle_cash() -> None:
    fill = _fill("SELL", "100", "1")
    assert fill.base_value + fill.total_cost == Decimal("101")


def test_trades_fill_update_ledgers() -> None:
    fills, cash, _unsettled_cash, positions = execute_trades(_plan())
    assert [fill.terminal_status for fill in fills] == ["FILLED", "FILLED"]
    assert cash == Decimal("120")
    assert positions["asset-1"].quantity == Decimal("10")
    assert positions["asset-2"].quantity == Decimal("0")


def test_purchase_limited_to_available_cash() -> None:
    request = replace(_request("buy", "BUY", "asset-1"), requested_quantity=Decimal("100"))
    plan = _plan()
    frame = replace(plan, requests=(request,), initial_cash=Decimal("29"))
    result = run_backtest(frame)
    assert result.trades[0].filled_quantity == Decimal("2")
    assert result.trades[0].valid_lot_quantity == Decimal("2")
    assert result.settled_cash == Decimal("9")


def test_blocked_request_uses_zero_fill() -> None:
    request = replace(_request("blocked", "BUY", "asset-1"), halt_status="DELISTED")
    plan = _plan()
    frame = replace(plan, requests=(request,))
    result = run_backtest(frame)
    assert result.trades[0].terminal_status == "ZERO"
    assert result.trades[0].filled_quantity == Decimal("0")
    assert result.trades[0].gross_value == Decimal("0")
    assert result.settled_cash == Decimal("120")


def test_excess_sell_is_zero_filled() -> None:
    request = replace(_request("sell", "SELL", "asset-2"), requested_quantity=Decimal("20"))
    plan = _plan()
    frame = replace(plan, requests=(request,))
    result = run_backtest(frame)
    assert result.trades[0].terminal_status == "ZERO"


def test_run_backtest_returns_ledger_snapshot() -> None:
    plan = _plan()
    result = run_backtest(plan)
    assert result.settled_cash == Decimal("120")
    assert result.unsettled_cash == Decimal("0")
    assert result.holdings == (("asset-1", Decimal("10")),)
    assert len(result.trades) == 2


def test_unavailable_valuation_policy_marks_all_held_assets() -> None:
    plan = _plan()
    frame = replace(plan, valuation_policy="UNAVAILABLE")
    result = run_backtest(frame)
    assert result.valuations == ()
    assert len(result.unavailable_values) == 1
    assert result.unavailable_values[0].asset_id == "asset-1"


def test_latest_prior_valuation_policy_uses_price_history() -> None:
    plan = _plan()
    frame = replace(plan, valuation_policy="LATEST_PRIOR")
    result = run_backtest(frame)
    assert len(result.valuations) == 1
    assert result.unavailable_values == ()


def _rule() -> CostRule:
    return CostRule(
        version_id="1",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        commission_rate=Decimal("0.01"),
    )


def _calendar() -> TradingCalendar:
    return TradingCalendar(
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


def _request(request_id: str, side: str, asset_id: str) -> TradeRequest:
    return TradeRequest(
        request_id=request_id,
        decision_id="decision-1",
        asset_id=asset_id,
        market="US",
        exchange="NYSE",
        asset_type="EQUITY",
        side=side,
        requested_quantity=Decimal("10"),
        requested_price=Decimal("10"),
        currency="USD",
        decision_at=datetime(2024, 1, 2, 13, 30, tzinfo=UTC),
    )


def _plan() -> BacktestPlan:
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
        requests=(_request("buy", "BUY", "asset-1"), _request("sell", "SELL", "asset-2")),
        prices=(
            PriceBar(asset_id="asset-1", market="US", source_date=date(2024, 1, 1), close=Decimal("10")),
        ),
        calendars=(_calendar(),),
        market_rules=(
            MarketRuleProfile(
                version_id="market-rule-1",
                market="US",
                exchange="NYSE",
                asset_type="EQUITY",
                effective_from=date(2024, 1, 1),
                cash_settlement_open_dates=1,
            ),
        ),
        cost_rules=(CostRule(version_id="cost-model-1", effective_from=date(2024, 1, 1)),),
        initial_cash=Decimal("120"),
        initial_positions=(("asset-2", Decimal("10")),),
    )


def _fill(side: str, gross: str, cost: str) -> TradeFill:
    return TradeFill(
        fill_id="1",
        request_id="1",
        asset_id="asset1",
        side=side,
        requested_quantity=Decimal(1),
        valid_lot_quantity=Decimal(1),
        filled_quantity=Decimal(1),
        local_execution_price=Decimal(gross),
        trading_currency="USD",
        base_currency="USD",
        fx_rate_version_id=None,
        gross_value=Decimal(gross),
        base_value=Decimal(gross),
        cost_components=(("commission", Decimal(cost)),),
        total_cost=Decimal(cost),
        trade_timestamp=datetime(2024, 1, 1, 9, 30),
        source_market_date=date(2024, 1, 1),
        sell_available_date=None,
        settlement_date=date(2024, 1, 2),
        terminal_status="FILLED",
        reason=None,
    )
