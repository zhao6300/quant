from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.attribution import brinson_fachler


@given(
    portfolio_weight=st.integers(min_value=1, max_value=99),
    benchmark_weight=st.integers(min_value=1, max_value=99),
    portfolio_return=st.integers(min_value=-95, max_value=95),
    benchmark_return=st.integers(min_value=-95, max_value=95),
    total_portfolio_return=st.integers(min_value=-95, max_value=95),
    total_benchmark_return=st.integers(min_value=-95, max_value=95),
)
def test_brinson_fachler_effects_follow_formula(
    portfolio_weight: int,
    benchmark_weight: int,
    portfolio_return: int,
    benchmark_return: int,
    total_portfolio_return: int,
    total_benchmark_return: int,
) -> None:
    def percent(value: int) -> Decimal:
        return Decimal(value) / Decimal(100)

    effects, residual = brinson_fachler(
        ("growth",),
        {"growth": percent(portfolio_weight)},
        {"growth": percent(benchmark_weight)},
        {"growth": percent(portfolio_return)},
        {"growth": percent(benchmark_return)},
        percent(total_portfolio_return),
        percent(total_benchmark_return),
    )
    effect = effects["growth"]
    expected_allocation = (percent(portfolio_weight) - percent(benchmark_weight)) * (
        percent(benchmark_return) - percent(total_benchmark_return)
    )
    expected_selection = percent(benchmark_weight) * (percent(portfolio_return) - percent(benchmark_return))
    expected_interaction = (percent(portfolio_weight) - percent(benchmark_weight)) * (
        percent(portfolio_return) - percent(benchmark_return)
    )
    assert effect.allocation == expected_allocation
    assert effect.selection == expected_selection
    assert effect.interaction == expected_interaction
    assert residual == percent(total_portfolio_return) - percent(total_benchmark_return) - (
        expected_allocation + expected_selection + expected_interaction
    )
