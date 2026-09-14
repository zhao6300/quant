from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from mmqp.kernels.evaluation import (
    pearson_information_coefficient as evaluate_factor_pearson_information_coefficient,
)


def _pearson(
    values: Sequence[Decimal],
    returns: Sequence[Decimal],
) -> Decimal:
    value_mean = _mean(values)
    return_mean = _mean(returns)
    numerator = sum(
        (value - value_mean) * (future_return - return_mean)
        for value, future_return in zip(values, returns, strict=True)
    )
    value_dispersion = sum((value - value_mean) ** 2 for value in values)
    return_dispersion = sum((future_return - return_mean) ** 2 for future_return in returns)
    return numerator / (value_dispersion * return_dispersion) ** Decimal("0.5")


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def test_pearson_information_coefficient_uses_documented_formula() -> None:
    factor_values = [Decimal("1"), Decimal("2"), Decimal("3")]
    future_returns = [Decimal("1"), Decimal("3"), Decimal("2")]
    result = evaluate_factor_pearson_information_coefficient(factor_values, future_returns)
    assert result == _pearson(factor_values, future_returns)
