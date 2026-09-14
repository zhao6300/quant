from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mmqp.domain.factor_evaluation import average_tie_rank as kernel_average_tie_rank
from mmqp.domain.factor_evaluation import spearman_information_coefficient as kernel_spearman
from mmqp.kernels.evaluation import (
    pearson_information_coefficient as kernel_pearson,
)

# Feature: multi-market-quant-platform, Property 27: Correlation kernels use exact aligned sets and tie ranks.


# Feature: multi-market-quant-platform, Property 27: Correlation kernels use exact aligned sets and tie ranks.


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def _pearson(values: Sequence[Decimal], returns: Sequence[Decimal]) -> Decimal:
    value_center = _mean(values)
    return_center = _mean(returns)
    numerator = sum(
        (value - value_center) * (future_return - return_center)
        for value, future_return in zip(values, returns, strict=True)
    )
    value_dispersion = sum((value - value_center) ** 2 for value in values)
    return_dispersion = sum((future_return - return_center) ** 2 for future_return in returns)
    return numerator / (value_dispersion * return_dispersion) ** Decimal("0.5")


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    values=st.lists(st.decimals(allow_nan=False, allow_infinity=False), min_size=2, max_size=6),
    returns=st.lists(st.decimals(allow_nan=False, allow_infinity=False), min_size=2, max_size=6),
)
def test_pearson_information_coefficient_uses_exact_formula(
    values: list[Decimal], returns: list[Decimal]
) -> None:
    value_dispersion = sum((value - _mean(values)) ** 2 for value in values)
    return_dispersion = sum((future - _mean(returns)) ** 2 for future in returns)
    if len(values) == len(returns) and value_dispersion > 0 and return_dispersion > 0:
        assert kernel_pearson(values, returns) == _pearson(values, returns)
    else:
        assert kernel_pearson(values, returns) == "UNDEFINED"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    values=st.lists(st.decimals(allow_nan=False, allow_infinity=False), min_size=2, max_size=5),
    returns=st.lists(st.decimals(allow_nan=False, allow_infinity=False), min_size=2, max_size=5),
)
def test_spearman_information_coefficient_uses_average_tie_ranks(
    values: list[Decimal],
    returns: list[Decimal],
) -> None:
    if len(values) == len(returns):
        expected_ranks = kernel_average_tie_rank(values)
        expected_return_ranks = kernel_average_tie_rank(returns)
        actual = kernel_spearman(values, returns)
        if expected_ranks is not None and expected_return_ranks is not None and actual is not None:
            assert actual == kernel_pearson(expected_ranks, expected_return_ranks)
    else:
        assert kernel_spearman(values, returns) == "UNDEFINED"
