from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.risk import (
    ReturnSample,
    ValuationPoint,
    annualized_volatility,
    beta,
    maximum_drawdown,
    tracking_error,
)


@given(
    first=st.integers(min_value=-5, max_value=5),
    second=st.integers(min_value=-5, max_value=5),
    benchmark_first=st.integers(min_value=-5, max_value=5),
    benchmark_second=st.integers(min_value=-5, max_value=5),
)
def test_aligned_metrics_equal_reference_formulas(
    first: int,
    second: int,
    benchmark_first: int,
    benchmark_second: int,
) -> None:
    def return_value(value: int) -> Decimal:
        return Decimal(value) / Decimal(100)

    portfolio_first = return_value(first)
    portfolio_second = return_value(second)
    benchmark_first_value = return_value(benchmark_first)
    benchmark_second_value = return_value(benchmark_second)
    samples = (
        ReturnSample(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC), portfolio_first, benchmark_first_value),
        ReturnSample(datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC), portfolio_second, benchmark_second_value),
    )
    mean = sum((portfolio_first, portfolio_second), Decimal(0)) / Decimal(2)
    variance = sum((value - mean) * (value - mean) for value in (portfolio_first, portfolio_second))
    assert annualized_volatility(samples, Decimal(252)) == (variance * Decimal(252)).sqrt()

    difference_mean = sum(
        (
            portfolio_first - benchmark_first_value,
            portfolio_second - benchmark_second_value,
        ),
        Decimal(0),
    ) / Decimal(2)
    difference_variance = sum(
        (
            (portfolio_first - benchmark_first_value - difference_mean) ** 2,
            (portfolio_second - benchmark_second_value - difference_mean) ** 2,
        ),
        Decimal(0),
    )
    assert tracking_error(samples, Decimal(252)) == (difference_variance * Decimal(252)).sqrt()

    assert maximum_drawdown(
        (
            ValuationPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100")),
            ValuationPoint(datetime(2024, 2, 1, tzinfo=UTC), Decimal("80")),
            ValuationPoint(datetime(2024, 3, 1, tzinfo=UTC), Decimal("90")),
        )
    ) == Decimal("0.2")

    assert beta(samples) is None or isinstance(beta(samples), Decimal)
