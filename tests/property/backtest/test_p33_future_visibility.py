from dataclasses import replace
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backtest import StrategyInput
from tests.property.backtest.test_p33_decision_scheduling import _plan


@given(seconds_after=st.integers(min_value=1, max_value=10_000))
def test_future_strategy_input_rejects_rebalance(seconds_after):
    plan = _plan(date(2024, 1, 1))
    future = plan.requests[0].decision_at + timedelta(seconds=seconds_after)
    future_plan = replace(
        plan,
        requests=(
            replace(
                plan.requests[0],
                inputs=(StrategyInput(plan.requests[0].asset_id, future, "ahead"),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="visible after its decision timestamp"):
        future_plan.validate()
