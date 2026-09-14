from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.domain.factor_evaluation import (
    ValuationEndpoint,
    calculate_future_returns,
    evaluate_factor_turnover,
)

# Feature: multi-market-quant-platform, Property 29: Future returns and turnover use specified endpoints/union.


def _expected_future_return(
    decision_at: datetime,
    holding_period: int,
    endpoints: tuple[ValuationEndpoint, ...],
) -> Decimal | None:
    if not 1 <= holding_period <= 10:
        return None
    valid_endpoints = [
        endpoint
        for endpoint in sorted(endpoints, key=lambda endpoint: endpoint.timestamp)
        if endpoint.value is not None and endpoint.value.is_finite() and endpoint.value > 0
    ]
    if len(valid_endpoints) < holding_period + 1:
        return None
    selected = valid_endpoints[: holding_period + 1]
    return selected[-1].value / selected[0].value - Decimal(1)


def _expected_turnover(
    current_weights: dict[str, Decimal],
    previous_weights: dict[str, Decimal],
) -> Decimal:
    total = Decimal(0)
    for asset_id in sorted(set(current_weights) | set(previous_weights)):
        total += abs(current_weights.get(asset_id, Decimal(0)) - previous_weights.get(asset_id, Decimal(0)))
    return total / Decimal(2)


@settings(max_examples=100, deadline=None)
@given(
    holding_period=st.integers(min_value=0, max_value=4),
    values=st.tuples(
        st.decimals(min_value=Decimal("0.01"), allow_nan=False, allow_infinity=False),
        st.decimals(min_value=Decimal("0.01"), allow_nan=False, allow_infinity=False),
        st.one_of(st.none(), st.decimals(allow_nan=False, allow_infinity=False)),
    ),
    current_weight=st.decimals(allow_nan=False, allow_infinity=False),
    previous_weight=st.decimals(allow_nan=False, allow_infinity=False),
)
def test_future_returns_and_turnover_use_specified_endpoints(
    holding_period: int,
    values: tuple[Decimal, Decimal, Decimal | None],
    current_weight: Decimal,
    previous_weight: Decimal,
) -> None:
    decision_at = datetime(2024, 2, 1, 12, tzinfo=UTC)
    valuation = (
        ValuationEndpoint(datetime(2024, 2, 5, 12, tzinfo=UTC), values[0]),
        ValuationEndpoint(datetime(2024, 2, 12, 12, tzinfo=UTC), values[1]),
    )
    if holding_period == 0:
        valuation = (*valuation, ValuationEndpoint(datetime(2024, 2, 4, 12, tzinfo=UTC)))
    actual = calculate_future_returns(
        factor_date=date(2024, 2, 1),
        decision_at=decision_at,
        holding_period=holding_period,
        valuation_endpoints_by_asset={"asset": valuation},
    )
    expected_future = _expected_future_return(decision_at, holding_period, valuation)
    if actual[0].status == "OK":
        assert actual[0].value == expected_future
        assert actual[0].valid_endpoint_count == holding_period + 1
    else:
        assert expected_future is None

    current_weights = {"shared": current_weight}
    previous_weights = {"shared": previous_weight}
    assert evaluate_factor_turnover(current_weights, previous_weights) == _expected_turnover(
        current_weights,
        previous_weights,
    )
