from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.attribution import (
    ExternalCashFlow,
    asset_contributions,
    periodic_return,
)


@given(beginning=st.integers(min_value=100, max_value=1000), ending=st.integers(min_value=100, max_value=1000))
def test_periodic_return_matches_reference(beginning: int, ending: int) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 2, 1, tzinfo=UTC)
    flow = ExternalCashFlow(datetime(2024, 1, 15, 12, 0, tzinfo=UTC), Decimal("10"))
    remaining_seconds = Decimal((end - flow.timestamp).total_seconds())
    total_seconds = Decimal((end - start).total_seconds())
    fraction_remaining = remaining_seconds / total_seconds
    denominator = Decimal(beginning) + Decimal("10") * fraction_remaining
    value = periodic_return(Decimal(beginning), Decimal(ending), (flow,), start, end)
    expected = (Decimal(ending) - Decimal(beginning) - Decimal("10")) / denominator
    assert value == expected


@given(portfolio_weight=st.integers(min_value=1, max_value=99), asset_return=st.integers(min_value=-99, max_value=99))
def test_asset_contributions_follow_weighted_returns(portfolio_weight: int, asset_return: int) -> None:
    weights = {"A": Decimal(portfolio_weight) / Decimal(100), "B": Decimal(1 - portfolio_weight / 100)}
    returns = {"A": Decimal(asset_return) / Decimal(100), "B": Decimal("0")}
    value = asset_contributions(weights, returns)
    assert value == {
        "A": Decimal(portfolio_weight) / Decimal(100) * Decimal(asset_return) / Decimal(100),
        "B": Decimal("0"),
    }
