from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mmqp.application.factors import _zscore_values


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def _variance(values: Sequence[Decimal], mean: Decimal) -> Decimal:
    return sum((value - mean) ** 2 for value in values) / Decimal(len(values))


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    values=st.lists(
        st.decimals(allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=8,
    )
)
def test_zscore_values_follow_the_population_formula(values: list[Decimal]) -> None:
    standardized = _zscore_values(values)
    if standardized is None:
        return
    mean = _mean(values)
    variance = _variance(values, mean)
    if variance <= 0:
        assert standardized is None
        return
    standardized_deviation = variance.sqrt()
    for value, standardized_value in zip(values, standardized, strict=True):
        expected = (value - mean) / standardized_deviation
        assert standardized_value == expected
