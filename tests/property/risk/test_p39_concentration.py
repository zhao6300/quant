from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.risk import concentration


@given(valueA=st.integers(min_value=1, max_value=100), valueB=st.integers(min_value=1, max_value=100))
def test_concentration_uses_weights_and_grouping(valueA: int, valueB: int) -> None:
    def asset(value: int) -> Decimal:
        return Decimal(value)

    first = asset(valueA)
    second = asset(valueB)
    total = first + second
    result = concentration(
        {"A": first, "B": second},
        {"A": "US", "B": "US"},
        {"A": "TECH", "B": "TECH"},
        {"A": "USD", "B": "USD"},
    )
    assert result.single == max(first, second) / total
    assert result.top_five == Decimal(1)
    assert result.markets == {"US": Decimal(1)}
    assert result.industries == {"TECH": Decimal(1)}
    assert result.currencies == {"USD": Decimal(1)}
