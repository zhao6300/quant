from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from mmqp.kernels.evaluation import (
    pearson_information_coefficient as evaluate_factor_pearson_information_coefficient,
)
from mmqp.kernels.evaluation import (
    spearman_information_coefficient as evaluate_factor_spearman_information_coefficient,
)

HALF = Decimal("0.5")


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


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
    return numerator / (value_dispersion * return_dispersion) ** HALF


def test_pearson_uses_exact_two_aligned_values() -> None:
    factor_values = [Decimal("1"), Decimal("2")]
    returns = [Decimal("10"), Decimal("20")]
    coefficient = evaluate_factor_pearson_information_coefficient(factor_values, returns)
    assert coefficient == Decimal("1")


def test_pearson_uses_the_documented_cross_section_formula() -> None:
    factor_values = [Decimal("1"), Decimal("2"), Decimal("3")]
    factor_returns = [Decimal("2"), Decimal("4"), Decimal("3")]
    factor_returns = [Decimal("1"), Decimal("3"), Decimal("2")]
    assert evaluate_factor_pearson_information_coefficient(factor_values, factor_returns) == _pearson(
        factor_values, factor_returns
    )


def test_spearman_assigns_average_tie_ranks() -> None:
    factor_values = [Decimal("1"), Decimal("2"), Decimal("2")]
    returns = [Decimal("3"), Decimal("2"), Decimal("1")]
    coefficient = evaluate_factor_spearman_information_coefficient(factor_values, returns)
    assert coefficient == _pearson(
        [Decimal("1"), Decimal("2.5"), Decimal("2.5")],
        [Decimal("3"), Decimal("2"), Decimal("1")],
    )
