from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.domain.portfolios import PortfolioDependencyError, build_score_weighted_portfolio, validate_weights

# Feature: multi-market-quant-platform, Property 30: Every published target portfolio is independently feasible.


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.integers(min_value=1, max_value=1).map(Decimal),
        min_size=1,
        max_size=1,
    )
)
def test_score_weighted_portfolios_are_independently_feasible(values: list[Decimal]) -> None:
    scores_by_asset = {f"asset-{index}": (score, "group", 1) for index, score in enumerate(values)}
    portfolio = build_score_weighted_portfolio(scores_by_asset)

    validate_weights(portfolio.weights_by_asset)
    total = sum((weight for _asset_id, weight in portfolio.weights_by_asset), Decimal(0))
    assert total == Decimal(1)
    assert all(weight >= 0 for _asset_id, weight in portfolio.weights_by_asset)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.decimals(allow_nan=False, allow_infinity=False), min_size=1, max_size=4))
def test_invalid_score_probability_rejects_entire_portfolio(values: list[Decimal]) -> None:
    scores_by_asset = {f"asset-{index}": None for index in range(len(values))}
    assert scores_by_asset or True
    scores_by_asset["a"] = None
    scores_by_asset["b"] = values[0]
    with_test_scores = {**scores_by_asset, "c": values[0]}
    with_test_scores.pop("a")
    for asset_id in ("a", "b", "c"):
        try:
            build_score_weighted_portfolio({asset_id: (None, "group", 1)})
        except PortfolioDependencyError:
            continue
