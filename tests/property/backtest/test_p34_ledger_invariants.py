from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backtest import CostRule, MarketRuleProfile, max_affordable_lots, trade_cost


@given(
    price=st.decimals(min_value="1", max_value="100", places=2),
    cash=st.integers(min_value=0, max_value=100_000),
)
def test_affordable_fill_never_breaks_ledgers(price, cash):
    rule = MarketRuleProfile("m", "US", "NYSE", "EQUITY", date(2024, 1, 1))
    cost = CostRule("c", date(2024, 1, 1), minimum_cost=Decimal("0.10"))
    lots = max_affordable_lots(price, rule.trading_lot, Decimal(cash), trade_cost(price, cost))
    fill_cost = Decimal(sum((total for _name, total in trade_cost(price, cost)), Decimal(0)))
    if lots:
        assert Decimal(cash) - lots * price - fill_cost >= Decimal("1e-10")
