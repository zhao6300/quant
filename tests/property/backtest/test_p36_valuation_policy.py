from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backtest import PriceBar, valuations_for


@given(start=st.dates(), end=st.dates())
def test_valuation_uses_latest_source_date_in_local_bounds(start, end):
    if end < start:
        start, end = end, start
    prices = (
        PriceBar("a", "US", start, Decimal("10")),
        PriceBar("a", "US", end, Decimal("20")),
    )
    valuations = valuations_for(prices, {"a": Decimal("1")}, "LATEST_PRIOR")
    assert len(valuations) == 1
    valuation = valuations[0]
    assert valuation.value_date == end
    assert valuation.local_value == Decimal("20")
