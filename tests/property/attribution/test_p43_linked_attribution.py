from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.attribution import linked_attribution


@given(
    first=st.integers(min_value=-9, max_value=9),
    second=st.integers(min_value=-9, max_value=9),
)
def test_linked_attribution_periods_reconcile(first: int, second: int) -> None:
    period_return = Decimal(first) / Decimal(100)
    second_return = Decimal(second) / Decimal(100)
    first_contributions = {
        "A": period_return / Decimal(2),
        "B": period_return / Decimal(2),
    }
    second_contributions = {
        "A": second_return / Decimal(2),
        "B": second_return / Decimal(2),
    }
    value = linked_attribution(
        [
            (period_return, first_contributions),
            (second_return, second_contributions),
        ]
    )
    total_return = Decimal(1) + period_return
    total_return *= Decimal(1) + second_return
    total_return -= Decimal(1)
    assert abs(value.residual) <= Decimal("1e-10")
    assert abs(value.total_return - total_return) <= Decimal("1e-10")
