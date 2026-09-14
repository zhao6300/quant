from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.attribution import local_fx_effect, local_fx_return


@given(
    weight=st.integers(min_value=0, max_value=100),
    local=st.integers(min_value=-95, max_value=95),
    fx=st.integers(min_value=-95, max_value=95),
)
def test_local_fx_effects_keep_multiplicative_identity(weight: int, local: int, fx: int) -> None:
    weight_decimal = Decimal(weight) / Decimal(100)
    local_decimal = Decimal(local) / Decimal(100)
    fx_decimal = Decimal(fx) / Decimal(100)
    effect = local_fx_effect(weight_decimal, local_decimal, fx_decimal)
    base_return = local_fx_return(local_decimal, fx_decimal)
    assert base_return == (Decimal(1) + local_decimal) * (Decimal(1) + fx_decimal) - Decimal(1)
    assert effect.local + effect.fx == (
        weight_decimal * local_decimal
        + weight_decimal * (Decimal(1) + local_decimal) * fx_decimal
    )
